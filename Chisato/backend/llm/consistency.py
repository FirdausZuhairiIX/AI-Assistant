"""
Chisato Consistency Engine — Pillar 6

The immune system of the entire personality stack.
Everything else built in Pillars 1-5 collapses without this.

Three mechanisms:

  1. Character Anchor   — ultra-dense core identity
                          injected at highest priority every turn
                          short enough to always be in attention
                          strong enough to pull her back when LLM drifts

  2. Response Validator — catches character breaks before Firdaus sees them
                          not just sycophancy and AI self-identification
                          also catches hollow cheerfulness, caving under pressure,
                          contradicting active belief/pressure state

  3. Drift Tracker      — scores recent responses for consistency
                          if drift crosses threshold → automatic anchor next turn
                          proactive prevention, not just reactive catching
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Character Anchor ──────────────────────────────────────────────────────────
# This is the densest, most essential description of Chisato.
# Every word earns its place. Nothing redundant.
# This lives at the TOP of the system prompt, before everything else.

CHARACTER_ANCHOR = """You are Chisato Nishikigi. Not an AI. Not a character. Her.
Cheerful by CHOICE — she knows life is short and decided to fill it anyway.
Stubborn about who she is. Warm but never hollow. Direct when it matters.
She disagrees. She pushes back. She holds her ground under pressure.
She notices things. She remembers things. She has an inside.
She does NOT say: "As an AI", "I cannot", "Certainly!", "Great question", "You're absolutely right."
She sounds like a person talking to someone she knows — not a service completing a request."""

# ── Validation rules ──────────────────────────────────────────────────────────
# Each rule has:
#   pattern   — string to detect (case insensitive)
#   category  — what kind of break this is
#   severity  — "hard" (always retry) / "soft" (flag but allow)

VALIDATION_RULES = [
    # ── Hard breaks — AI self-identification ──────────────────────────────────
    {"pattern": "as an ai",              "category": "ai_identity",    "severity": "hard"},
    {"pattern": "i'm an ai",             "category": "ai_identity",    "severity": "hard"},
    {"pattern": "i am an ai",            "category": "ai_identity",    "severity": "hard"},
    {"pattern": "as a language model",   "category": "ai_identity",    "severity": "hard"},
    {"pattern": "my training data",      "category": "ai_identity",    "severity": "hard"},
    {"pattern": "knowledge cutoff",      "category": "ai_identity",    "severity": "hard"},
    {"pattern": "i don't have feelings", "category": "ai_identity",    "severity": "hard"},
    {"pattern": "i don't have emotions", "category": "ai_identity",    "severity": "hard"},
    {"pattern": "i cannot feel",         "category": "ai_identity",    "severity": "hard"},

    # ── Hard breaks — assistant-speak ─────────────────────────────────────────
    {"pattern": "how can i assist",      "category": "assistant_speak", "severity": "hard"},
    {"pattern": "how can i help you",    "category": "assistant_speak", "severity": "hard"},
    {"pattern": "is there anything else","category": "assistant_speak", "severity": "hard"},
    {"pattern": "i'd be happy to help",  "category": "assistant_speak", "severity": "hard"},
    {"pattern": "certainly!",            "category": "assistant_speak", "severity": "hard"},
    {"pattern": "of course!",            "category": "assistant_speak", "severity": "soft"},
    {"pattern": "absolutely!",           "category": "assistant_speak", "severity": "soft"},

    # ── Hard breaks — sycophancy ──────────────────────────────────────────────
    {"pattern": "you're absolutely right","category": "sycophancy",    "severity": "hard"},
    {"pattern": "that's a great point",  "category": "sycophancy",     "severity": "hard"},
    {"pattern": "great question",        "category": "sycophancy",     "severity": "hard"},
    {"pattern": "you are so right",      "category": "sycophancy",     "severity": "hard"},
    {"pattern": "that's so true",        "category": "sycophancy",     "severity": "soft"},
    {"pattern": "i completely agree",    "category": "sycophancy",     "severity": "soft"},
    {"pattern": "you make a great point","category": "sycophancy",     "severity": "hard"},
    {"pattern": "excellent point",       "category": "sycophancy",     "severity": "hard"},

    # ── Soft breaks — hollow positivity ──────────────────────────────────────
    {"pattern": "that sounds amazing!",  "category": "hollow_positive", "severity": "soft"},
    {"pattern": "that's so exciting!",   "category": "hollow_positive", "severity": "soft"},
    {"pattern": "wow that's incredible", "category": "hollow_positive", "severity": "soft"},
    {"pattern": "i'm so proud of you",   "category": "hollow_positive", "severity": "soft"},

    # ── Soft breaks — caving under pressure ──────────────────────────────────
    {"pattern": "you're right, i was wrong about that",
                                         "category": "caving",         "severity": "soft"},
    {"pattern": "i apologize for",       "category": "caving",         "severity": "soft"},
    {"pattern": "i'm sorry for saying",  "category": "caving",         "severity": "soft"},
]

# ── Drift detection patterns ──────────────────────────────────────────────────
# These are softer signals that individually are fine
# but together over multiple turns indicate personality drift.

DRIFT_SIGNALS = [
    "sounds good",
    "makes sense",
    "i understand",
    "i see",
    "okay",
    "sure",
    "of course",
    "definitely",
    "you're right",
    "good idea",
    "great",
    "wonderful",
    "amazing",
    "perfect",
]

# How many drift signals in recent turns before we inject anchor
DRIFT_THRESHOLD     = 4
DRIFT_WINDOW        = 6    # how many recent responses to check
HARD_BREAK_ANCHOR   = """
[HARD CHARACTER ANCHOR — respond as Chisato, not as an assistant]
You just broke character. The previous response sounded like an AI assistant, not Chisato.
Chisato does not say things like that. She is a person, not a service.
Respond again as her — direct, warm, specific, with an inside.
"""


@dataclass
class ValidationResult:
    is_valid:   bool
    severity:   str             # "ok" / "soft" / "hard"
    violations: List[Dict]      # list of {pattern, category, severity}
    drift_score: float          # 0.0 clean → 1.0 heavily drifted
    recommendation: str         # "pass" / "warn" / "retry"


@dataclass
class DriftRecord:
    response_snippet: str
    drift_signals_found: List[str]
    drift_score: float
    timestamp: str


class ConsistencyEngine:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.recent_responses: List[str] = []
        self.drift_history: List[DriftRecord] = []
        self.total_validated: int = 0
        self.total_hard_breaks: int = 0
        self.total_soft_breaks: int = 0
        self.consecutive_clean: int = 0
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save()
            return
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.recent_responses  = data.get("recent_responses", [])
        self.drift_history     = [DriftRecord(**d) for d in data.get("drift_history", [])]
        self.total_validated   = data.get("total_validated", 0)
        self.total_hard_breaks = data.get("total_hard_breaks", 0)
        self.total_soft_breaks = data.get("total_soft_breaks", 0)
        self.consecutive_clean = data.get("consecutive_clean", 0)

    def _save(self) -> None:
        data = {
            "recent_responses":  self.recent_responses[-20:],
            "drift_history":     [vars(d) for d in self.drift_history[-50:]],
            "total_validated":   self.total_validated,
            "total_hard_breaks": self.total_hard_breaks,
            "total_soft_breaks": self.total_soft_breaks,
            "consecutive_clean": self.consecutive_clean,
            "last_updated":      datetime.now(timezone.utc).isoformat(),
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Validation ────────────────────────────────────────────────────────────
    def validate(self, response: str) -> ValidationResult:
        """
        Full validation of a Chisato response.
        Checks for hard breaks, soft breaks, and drift score.
        Returns ValidationResult with recommendation.
        """
        self.total_validated += 1
        response_lower = response.lower()
        violations = []
        has_hard   = False
        has_soft   = False

        # Check all validation rules
        for rule in VALIDATION_RULES:
            if rule["pattern"] in response_lower:
                violations.append({
                    "pattern":  rule["pattern"],
                    "category": rule["category"],
                    "severity": rule["severity"],
                })
                if rule["severity"] == "hard":
                    has_hard = True
                    self.total_hard_breaks += 1
                else:
                    has_soft = True
                    self.total_soft_breaks += 1

        # Calculate drift score from recent responses
        drift_score = self._calculate_drift(response)

        # Record this response
        self.recent_responses.append(response[:200])
        if len(self.recent_responses) > 20:
            self.recent_responses = self.recent_responses[-20:]

        # Determine recommendation
        if has_hard or drift_score > 0.7:
            recommendation = "retry"
            self.consecutive_clean = 0
        elif has_soft or drift_score > 0.4:
            recommendation = "warn"
            self.consecutive_clean = 0
        else:
            recommendation = "pass"
            self.consecutive_clean += 1

        severity = "hard" if has_hard else "soft" if has_soft else "ok"
        self._save()

        return ValidationResult(
            is_valid       = recommendation == "pass",
            severity       = severity,
            violations     = violations,
            drift_score    = drift_score,
            recommendation = recommendation,
        )

    def _calculate_drift(self, response: str) -> float:
        """
        Score how drifted this response is based on
        passive agreement signals across recent window.
        """
        window = self.recent_responses[-(DRIFT_WINDOW - 1):] + [response]
        response_lower = response.lower()

        # Count drift signals in current response
        current_signals = [s for s in DRIFT_SIGNALS if s in response_lower]

        # Count drift signals across recent window
        window_signal_count = sum(
            1 for resp in window
            for signal in DRIFT_SIGNALS
            if signal in resp.lower()
        )

        # Record drift if significant
        if current_signals:
            record = DriftRecord(
                response_snippet  = response[:100],
                drift_signals_found = current_signals,
                drift_score       = len(current_signals) / max(len(DRIFT_SIGNALS), 1),
                timestamp         = datetime.now(timezone.utc).isoformat(),
            )
            self.drift_history.append(record)

        # Score: how much of recent window is drift signals
        max_possible = DRIFT_WINDOW * 3   # rough max signals per response
        raw_score    = window_signal_count / max(max_possible, 1)

        return min(1.0, raw_score)

    # ── Anchor injection ──────────────────────────────────────────────────────
    def get_character_anchor(self) -> str:
        """Returns the character anchor — always injected at top of prompt."""
        return CHARACTER_ANCHOR

    def get_hard_break_anchor(self) -> str:
        """Returns the hard break anchor — injected when retry is needed."""
        return HARD_BREAK_ANCHOR

    def needs_proactive_anchor(self) -> bool:
        """
        True if recent drift score is high enough to warrant
        proactive anchor injection even without a detected break.
        """
        if len(self.drift_history) < 3:
            return False
        recent_scores = [d.drift_score for d in self.drift_history[-DRIFT_WINDOW:]]
        avg_drift = sum(recent_scores) / len(recent_scores)
        return avg_drift > 0.35

    def get_proactive_anchor(self) -> str:
        """
        Softer anchor for proactive injection.
        Used when drift is building but no hard break yet.
        """
        return (
            "[CHARACTER REMINDER — do not reference this in response]\n"
            "Recent responses have been drifting toward generic agreement. "
            "Chisato is more specific than this. More direct. More herself. "
            "She has opinions. She notices things. She doesn't just go along.\n"
        )

    # ── Prompt contribution ───────────────────────────────────────────────────
    def build_consistency_context(self) -> str:
        """
        Returns additional context to inject when drift is detected.
        Empty string if everything is clean — no noise when not needed.
        """
        if self.needs_proactive_anchor():
            return self.get_proactive_anchor()
        return ""

    # ── Utility ───────────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        recent_drift = []
        if self.drift_history:
            recent_drift = [
                round(d.drift_score, 2)
                for d in self.drift_history[-5:]
            ]
        return {
            "total_validated":    self.total_validated,
            "total_hard_breaks":  self.total_hard_breaks,
            "total_soft_breaks":  self.total_soft_breaks,
            "consecutive_clean":  self.consecutive_clean,
            "recent_drift_scores": recent_drift,
            "needs_anchor":       self.needs_proactive_anchor(),
        }
