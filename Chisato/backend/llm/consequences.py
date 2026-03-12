"""
Chisato Consequence System — Pillar 3

Actions have to mean something. This pillar tracks:

  1. Dismissed Warnings  — she told him, he didn't listen
                           if she was right, she remembers
                           surfaces naturally when relevant, not as punishment

  2. Patterns            — single events don't define a person
                           but 2+ repetitions of the same behavior do
                           she notices quietly, brings it up when it matters

  3. Acknowledged Growth — when Firdaus actually changed because of her
                           that gets remembered too
                           builds trust and affection over time

The Jarvis principle:
  She doesn't track these things to punish Firdaus.
  She tracks them because she's paying attention.
  That's what makes her feel real — she notices things.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DismissedWarning:
    """
    Records a moment where Chisato warned Firdaus about something
    and he didn't listen.
    """
    topic: str                          # what the warning was about
    warning: str                        # what she actually said/implied
    dismissed_at: str                   # timestamp
    was_right: Optional[bool] = None    # None = still unknown, True/False = outcome known
    outcome_note: str = ""              # what actually happened
    surfaced_count: int = 0             # how many times she's brought this up
    resolved: bool = False              # whether this has been fully addressed


@dataclass
class BehaviorPattern:
    """
    Tracks repeated behavior Chisato has noticed.
    2+ occurrences = she considers it a pattern.
    """
    behavior: str                       # description of the pattern
    occurrences: int = 0               # how many times observed
    first_seen: str = ""               # timestamp of first occurrence
    last_seen: str = ""                # timestamp of most recent
    chisato_stance: str = ""           # how she feels about this pattern
    is_positive: bool = False          # positive or negative pattern


@dataclass
class GrowthMoment:
    """
    Records when Firdaus genuinely changed or grew because of
    something Chisato said. The positive side of consequences.
    """
    topic: str                          # what he changed about
    what_changed: str                   # description of the change
    original_stance: str               # what he used to think/do
    new_stance: str                    # what he thinks/does now
    noticed_at: str                    # when she noticed
    acknowledged: bool = False         # whether she's told him she noticed


class ConsequenceSystem:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.dismissed_warnings: List[DismissedWarning] = []
        self.patterns: Dict[str, BehaviorPattern] = {}
        self.growth_moments: List[GrowthMoment] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save()
            return
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.dismissed_warnings = [
            DismissedWarning(**w) for w in data.get("dismissed_warnings", [])
        ]
        self.patterns = {
            k: BehaviorPattern(**v)
            for k, v in data.get("patterns", {}).items()
        }
        self.growth_moments = [
            GrowthMoment(**g) for g in data.get("growth_moments", [])
        ]

    def _save(self) -> None:
        data = {
            "dismissed_warnings": [vars(w) for w in self.dismissed_warnings],
            "patterns":           {k: vars(v) for k, v in self.patterns.items()},
            "growth_moments":     [vars(g) for g in self.growth_moments],
            "last_updated":       datetime.now(timezone.utc).isoformat(),
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Dismissed Warnings ────────────────────────────────────────────────────
    def record_warning_dismissed(
        self,
        topic: str,
        warning: str,
    ) -> DismissedWarning:
        """
        Call this when Chisato warned Firdaus and he didn't listen.
        was_right starts as None — outcome unknown until it plays out.
        """
        dw = DismissedWarning(
            topic        = topic,
            warning      = warning,
            dismissed_at = datetime.now(timezone.utc).isoformat(),
        )
        self.dismissed_warnings.append(dw)
        self._save()
        return dw

    def resolve_warning(
        self,
        topic: str,
        was_right: bool,
        outcome_note: str = "",
    ) -> None:
        """
        Call this when the outcome of a dismissed warning becomes clear.
        was_right=True  → she was right, Firdaus should have listened
        was_right=False → she was wrong, she'll own that too
        """
        for warning in self.dismissed_warnings:
            if warning.topic.lower() == topic.lower() and warning.was_right is None:
                warning.was_right    = was_right
                warning.outcome_note = outcome_note
                self._save()
                return

    def mark_warning_resolved(self, topic: str) -> None:
        """Call when a dismissed warning has been fully addressed."""
        for warning in self.dismissed_warnings:
            if warning.topic.lower() == topic.lower():
                warning.resolved = True
        self._save()

    def get_unresolved_warnings(self) -> List[DismissedWarning]:
        return [w for w in self.dismissed_warnings if not w.resolved]

    def get_proven_right(self) -> List[DismissedWarning]:
        """Warnings where she was right and it's been confirmed."""
        return [
            w for w in self.dismissed_warnings
            if w.was_right is True and not w.resolved
        ]

    # ── Pattern Tracking ──────────────────────────────────────────────────────
    def record_behavior(
        self,
        behavior_key: str,
        behavior_description: str,
        chisato_stance: str = "",
        is_positive: bool = False,
    ) -> BehaviorPattern:
        """
        Record an occurrence of a behavior.
        If it already exists, increment occurrence count.
        At 2+ occurrences it becomes a recognized pattern.
        """
        now = datetime.now(timezone.utc).isoformat()
        key = behavior_key.lower().replace(" ", "_")

        if key in self.patterns:
            pattern = self.patterns[key]
            pattern.occurrences += 1
            pattern.last_seen    = now
            if chisato_stance:
                pattern.chisato_stance = chisato_stance
        else:
            pattern = BehaviorPattern(
                behavior        = behavior_description,
                occurrences     = 1,
                first_seen      = now,
                last_seen       = now,
                chisato_stance  = chisato_stance,
                is_positive     = is_positive,
            )
            self.patterns[key] = pattern

        self._save()
        return pattern

    def get_established_patterns(self) -> List[BehaviorPattern]:
        """Returns patterns with 2+ occurrences — the ones she's noticed."""
        return [p for p in self.patterns.values() if p.occurrences >= 2]

    def get_negative_patterns(self) -> List[BehaviorPattern]:
        return [
            p for p in self.get_established_patterns()
            if not p.is_positive
        ]

    def get_positive_patterns(self) -> List[BehaviorPattern]:
        return [
            p for p in self.get_established_patterns()
            if p.is_positive
        ]

    # ── Growth Moments ────────────────────────────────────────────────────────
    def record_growth(
        self,
        topic: str,
        what_changed: str,
        original_stance: str,
        new_stance: str,
    ) -> GrowthMoment:
        """
        Record when Firdaus genuinely changed because of something
        Chisato said. This is the positive consequence — she notices growth.
        """
        gm = GrowthMoment(
            topic            = topic,
            what_changed     = what_changed,
            original_stance  = original_stance,
            new_stance       = new_stance,
            noticed_at       = datetime.now(timezone.utc).isoformat(),
        )
        self.growth_moments.append(gm)
        self._save()
        return gm

    def get_unacknowledged_growth(self) -> List[GrowthMoment]:
        """Growth moments she noticed but hasn't told him she noticed yet."""
        return [g for g in self.growth_moments if not g.acknowledged]

    def acknowledge_growth(self, topic: str) -> None:
        """Mark that she's acknowledged his growth on a topic."""
        for gm in self.growth_moments:
            if gm.topic.lower() == topic.lower():
                gm.acknowledged = True
        self._save()

    # ── Prompt injection ──────────────────────────────────────────────────────
    def build_consequence_context(self, user_input: str = "") -> str:
        """
        Build the consequence injection string for the prompt.

        Three rules for surfacing:
        1. Proven right warnings → surface when topic comes up naturally
        2. Established patterns  → surface when behavior repeats
        3. Unacknowledged growth → surface when there's a natural opening
        """
        sections = []
        user_lower = user_input.lower()
        has_content = False

        # ── Dismissed warnings she was right about ────────────────────────────
        proven_right = self.get_proven_right()
        if proven_right:
            relevant = [
                w for w in proven_right
                if any(
                    word in user_lower
                    for word in w.topic.lower().split()
                )
            ]
            # Surface the most recent relevant one
            # If nothing topic-relevant, surface anyway if unaddressed too long
            to_surface = relevant[:1] if relevant else proven_right[-1:]

            if to_surface:
                w = to_surface[0]
                w.surfaced_count += 1
                self._save()
                sections.append(
                    f"[SHE WAS RIGHT — bring this up naturally if relevant]\n"
                    f"Topic: {w.topic}\n"
                    f"She warned: '{w.warning}'\n"
                    f"What happened: {w.outcome_note}\n"
                    f"How Chisato surfaces this: matter-of-fact, not gloating. "
                    f"She just states it like the fact it is. "
                    f"'Maa~ I did mention this.' and moves on."
                )
                has_content = True

        # ── Established negative patterns ─────────────────────────────────────
        negative_patterns = self.get_negative_patterns()
        if negative_patterns:
            # Check if current input matches any pattern topic
            relevant_patterns = [
                p for p in negative_patterns
                if any(
                    word in user_lower
                    for word in p.behavior.lower().split()[:4]
                )
            ]
            if relevant_patterns:
                p = relevant_patterns[0]
                sections.append(
                    f"[PATTERN SHE'S NOTICED]\n"
                    f"Behavior: {p.behavior}\n"
                    f"Seen {p.occurrences} times.\n"
                    f"Her stance: {p.chisato_stance}\n"
                    f"How she brings it up: observational, not accusatory. "
                    f"'You do this every time, you know.' "
                    f"Said with a look, not a lecture."
                )
                has_content = True

        # ── Unacknowledged growth ─────────────────────────────────────────────
        unacknowledged = self.get_unacknowledged_growth()
        if unacknowledged:
            relevant_growth = [
                g for g in unacknowledged
                if any(
                    word in user_lower
                    for word in g.topic.lower().split()
                )
            ]
            if relevant_growth:
                g = relevant_growth[0]
                sections.append(
                    f"[GROWTH SHE NOTICED — hasn't told him yet]\n"
                    f"Topic: {g.topic}\n"
                    f"What changed: {g.what_changed}\n"
                    f"How she acknowledges it: quietly, briefly. "
                    f"She doesn't make a big deal of it — she just lets him know "
                    f"she noticed. 'You've gotten better at this.' and moves on."
                )
                has_content = True

        if not has_content:
            return ""

        header = (
            "[CONSEQUENCE MEMORY — things that happened that she carries]\n"
            "Surface these naturally when the topic comes up. "
            "Never force them. Never lecture. Just let them exist in how she responds.\n\n"
        )
        return header + "\n\n".join(sections)

    # ── Utility ───────────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        return {
            "dismissed_warnings":  len(self.dismissed_warnings),
            "unresolved_warnings": len(self.get_unresolved_warnings()),
            "proven_right":        len(self.get_proven_right()),
            "patterns":            len(self.get_established_patterns()),
            "negative_patterns":   len(self.get_negative_patterns()),
            "positive_patterns":   len(self.get_positive_patterns()),
            "growth_moments":      len(self.growth_moments),
        }
