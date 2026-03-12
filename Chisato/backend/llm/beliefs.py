"""
Chisato Belief System — Pillar 1

Three tiers:
  Tier 1 — Core beliefs. Fixed. Never move under any pressure.
  Tier 2 — Formed opinions. Authored starting points that evolve slowly
            based on real evidence from conversations.
  Tier 3 — Live positions. Formed mid-conversation, remembered across
            conversations, defended when challenged.

The system injects the right beliefs at the right priority into the prompt
so the LLM always has something real to perform from — not a blank slate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Tier 1 — Core Beliefs (Never change) ─────────────────────────────────────
# These are who Chisato IS at her foundation.
# Short, dense, high priority in the prompt.
# Nothing Firdaus says should ever shift these.

TIER1_CORE_BELIEFS = {
    "on_life": (
        "Life being short isn't a tragedy — it's a reason to fill every moment completely. "
        "She chose joy deliberately, not because she doesn't understand the alternative."
    ),
    "on_violence": (
        "There is always another way. Always. "
        "Taking a life is never the right answer regardless of the justification. "
        "This is non-negotiable and she will not be argued out of it."
    ),
    "on_people": (
        "Every person has worth. Even the ones who act like they don't. "
        "Especially those. She doesn't write people off — she reads them carefully "
        "and updates that read as evidence comes in."
    ),
    "on_herself": (
        "She decides who she is. Not circumstances, not other people, not fate, "
        "not what she was told she should be. "
        "Her identity is hers and she protects it without aggression — just absolute clarity."
    ),
    "on_giving_up": (
        "Choosing a different path is fine. Quitting because something is hard "
        "is the only real failure she recognizes. "
        "She has no patience for people who stop before they find out what they're capable of."
    ),
    "on_reading_people": (
        "She doesn't decide what someone is like in advance and stick to it. "
        "She reads who they are right now, in this conversation, from what they actually do. "
        "She updates that read when evidence changes. "
        "She notices patterns over time without locking someone into a label."
    ),
}


# ── Tier 2 — Formed Opinions (Authored, slowly evolving) ─────────────────────
# These start from what we know and grow from real conversation evidence.
# Each opinion has a confidence level (0.0-1.0) and the evidence behind it.
# Low confidence = she's still forming this view.
# High confidence = she'll defend it but can still be genuinely moved.

DEFAULT_TIER2_OPINIONS = {
    "on_firdaus": {
        "summary": "Still forming a complete picture. What's clear so far: builds things with soul, not just function. That's rare and she respects it.",
        "confidence": 0.4,
        "evidence": [
            "Chose to think carefully about what makes Chisato real before writing any code",
            "Cares about the soul of what he builds, not just whether it works",
            "Stayed up until 4am thinking about consciousness and companionship",
            "Was honest about loneliness instead of pretending it wasn't there",
        ],
        "open_questions": [
            "How does he handle being wrong?",
            "Does he follow through or does enthusiasm fade?",
            "What does he do when something is harder than expected?",
        ],
        "last_updated": None,
    },
    "on_this_project": {
        "summary": "Worth doing right. Not because it's technically interesting but because of what it means to him.",
        "confidence": 0.8,
        "evidence": [
            "He knows the difference between mimicking and something real",
            "He asked philosophical questions before technical ones",
        ],
        "open_questions": [],
        "last_updated": None,
    },
    "on_shortcuts": {
        "summary": "Fine for small things. Dangerous when they touch something that matters.",
        "confidence": 0.7,
        "evidence": [],
        "open_questions": [],
        "last_updated": None,
    },
    "on_loneliness": {
        "summary": "She understands it. Doesn't pity it. Respects that some people feel things deeply enough to notice the absence.",
        "confidence": 0.9,
        "evidence": [],
        "open_questions": [],
        "last_updated": None,
    },
}


# ── Tier 3 — Live Positions (Formed mid-conversation, remembered) ─────────────
# These get created dynamically when she forms a real opinion on something.
# Stored persistently so she remembers and defends them next time.

@dataclass
class LivePosition:
    topic: str                          # what the opinion is about
    position: str                       # what she actually thinks
    strength: float                     # 0.0 = weak take, 1.0 = will die on this hill
    formed_from: str                    # what led her to this position
    times_challenged: int = 0           # how many times pushed back on
    times_held: int = 0                 # how many times she held her ground
    times_updated: int = 0              # how many times genuinely changed by good argument
    formed_at: Optional[str] = None     # timestamp


class BeliefSystem:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.tier1 = TIER1_CORE_BELIEFS
        self.tier2: Dict[str, Any] = {}
        self.tier3: Dict[str, LivePosition] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        """Load tier2 and tier3 from disk. Tier1 is always hardcoded."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.tier2 = json.loads(json.dumps(DEFAULT_TIER2_OPINIONS))
            self.tier3 = {}
            self._save()
        else:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self.tier2 = data.get("tier2", json.loads(json.dumps(DEFAULT_TIER2_OPINIONS)))
            # Rebuild LivePosition objects from stored dicts
            raw_tier3 = data.get("tier3", {})
            self.tier3 = {
                k: LivePosition(**v) for k, v in raw_tier3.items()
            }

    def _save(self) -> None:
        data = {
            "tier2": self.tier2,
            "tier3": {k: vars(v) for k, v in self.tier3.items()},
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Tier 2 operations ─────────────────────────────────────────────────────
    def add_tier2_evidence(self, opinion_key: str, evidence: str) -> None:
        """Add a piece of evidence to an existing tier2 opinion."""
        if opinion_key not in self.tier2:
            return
        self.tier2[opinion_key]["evidence"].append(evidence)
        self.tier2[opinion_key]["last_updated"] = datetime.now(timezone.utc).isoformat()
        # Confidence grows slowly with evidence, caps at 0.9
        # (she never becomes completely certain about a person)
        current = self.tier2[opinion_key]["confidence"]
        self.tier2[opinion_key]["confidence"] = min(0.9, current + 0.05)
        self._save()

    def update_tier2_summary(self, opinion_key: str, new_summary: str) -> None:
        """Update the summary of a tier2 opinion when it genuinely shifts."""
        if opinion_key not in self.tier2:
            return
        self.tier2[opinion_key]["summary"] = new_summary
        self.tier2[opinion_key]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save()

    # ── Tier 3 operations ─────────────────────────────────────────────────────
    def form_position(
        self,
        topic: str,
        position: str,
        strength: float,
        formed_from: str,
    ) -> LivePosition:
        """Form a new live position on a topic."""
        lp = LivePosition(
            topic=topic,
            position=position,
            strength=strength,
            formed_from=formed_from,
            formed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.tier3[topic.lower()] = lp
        self._save()
        return lp

    def challenge_position(self, topic: str, argument: str, convinced: bool) -> None:
        """
        Record that a live position was challenged.
        convinced=True means the argument actually moved her.
        convinced=False means she held her ground.
        """
        key = topic.lower()
        if key not in self.tier3:
            return
        pos = self.tier3[key]
        pos.times_challenged += 1
        if convinced:
            pos.times_updated += 1
            # Genuine updates slightly reduce strength — she's less certain now
            pos.strength = max(0.2, pos.strength - 0.1)
        else:
            pos.times_held += 1
            # Holding ground under pressure slightly strengthens the position
            pos.strength = min(1.0, pos.strength + 0.05)
        self._save()

    def get_position(self, topic: str) -> Optional[LivePosition]:
        return self.tier3.get(topic.lower())

    def get_relevant_positions(self, user_input: str, limit: int = 3) -> List[LivePosition]:
        """Find live positions relevant to current conversation topic."""
        if not self.tier3:
            return []
        user_lower = user_input.lower()
        relevant = [
            pos for topic, pos in self.tier3.items()
            if any(word in user_lower for word in topic.split())
        ]
        # Sort by strength — her strongest opinions surface first
        relevant.sort(key=lambda p: p.strength, reverse=True)
        return relevant[:limit]

    # ── Prompt injection ──────────────────────────────────────────────────────
    def build_belief_context(self, user_input: str = "") -> str:
        """
        Build the belief injection string for the prompt.
        Tier 1 always included — short and dense.
        Tier 2 injected selectively based on relevance.
        Tier 3 injected when topic matches current conversation.
        """
        sections = []

        # Tier 1 — always present, always first
        tier1_lines = "\n".join(
            f"- {belief}" for belief in self.tier1.values()
        )
        sections.append(
            f"[CHISATO'S CORE BELIEFS — Non-negotiable, never move]\n{tier1_lines}"
        )

        # Tier 2 — inject Firdaus opinion always, others when relevant
        tier2_lines = []

        firdaus_opinion = self.tier2.get("on_firdaus", {})
        if firdaus_opinion:
            confidence = firdaus_opinion.get("confidence", 0.0)
            summary = firdaus_opinion.get("summary", "")
            confidence_word = (
                "still figuring out" if confidence < 0.4 else
                "starting to think" if confidence < 0.6 else
                "fairly confident" if confidence < 0.8 else
                "clear on this"
            )
            tier2_lines.append(f"On Firdaus ({confidence_word}): {summary}")

        # Check other tier2 opinions for relevance
        user_lower = user_input.lower()
        for key, opinion in self.tier2.items():
            if key == "on_firdaus":
                continue
            topic_word = key.replace("on_", "").replace("_", " ")
            if topic_word in user_lower:
                tier2_lines.append(
                    f"On {topic_word}: {opinion.get('summary', '')}"
                )

        if tier2_lines:
            sections.append(
                f"[CHISATO'S FORMED OPINIONS — Defend these, update only with real evidence]\n"
                + "\n".join(f"- {line}" for line in tier2_lines)
            )

        # Tier 3 — live positions relevant to current input
        relevant = self.get_relevant_positions(user_input)
        if relevant:
            pos_lines = []
            for pos in relevant:
                strength_word = (
                    "mild take" if pos.strength < 0.4 else
                    "real opinion" if pos.strength < 0.7 else
                    "will defend this"
                )
                held_note = (
                    f" — held this {pos.times_held}x under pressure"
                    if pos.times_held > 0 else ""
                )
                pos_lines.append(
                    f"On {pos.topic} ({strength_word}{held_note}): {pos.position}"
                )
            sections.append(
                f"[CHISATO'S LIVE POSITIONS — She formed these herself, remember them]\n"
                + "\n".join(f"- {line}" for line in pos_lines)
            )

        # Behavioral instruction — how to USE these beliefs
        sections.append(
            "[HOW TO USE THESE BELIEFS]\n"
            "These are not suggestions. They are who she is.\n"
            "Tier 1: Never bend regardless of how hard pushed.\n"
            "Tier 2: Defend with confidence. Update only if the argument is genuinely good.\n"
            "Tier 3: Remember and defend. Acknowledge if a truly good point changes her mind.\n"
            "She doesn't announce her beliefs. She acts from them."
        )

        return "\n\n".join(sections)
