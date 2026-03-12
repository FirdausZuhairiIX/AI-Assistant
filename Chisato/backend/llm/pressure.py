"""
Chisato Emotional Pressure System — Pillar 2

Five pressure meters that persist across ALL conversations.
These are not mood — mood is what she shows.
Pressure is what builds underneath and shapes how she shows it.

The key difference from the EmotionTracker (Pillar emotion.py):
  EmotionTracker  → what she feels RIGHT NOW this turn (playful, focused, etc.)
  PressureSystem  → what has been building across the WHOLE relationship

Both feed into the prompt together. One is the weather today.
The other is the climate of the relationship.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from memory.db import get_db

# ── Pressure meter definitions ────────────────────────────────────────────────

@dataclass
class PressureMeter:
    value: float                    # 0.0 → 1.0
    floor: float                    # minimum it can drop to
    ceiling: float                  # maximum it can reach
    decay_rate: float               # how fast it returns to neutral per turn
    neutral: float                  # where it naturally wants to rest


# Default starting meters — read from Firdaus's actual history
# These are not random. They reflect what the memory.json shows.
DEFAULT_METERS = {
    "frustration": PressureMeter(
        value      = 0.0,    # no unresolved friction currently
        floor      = 0.0,
        ceiling    = 1.0,
        decay_rate = 0.0,    # frustration does NOT auto-decay — she decides when it clears
        neutral    = 0.0,
    ),
    "trust": PressureMeter(
        value      = 0.72,   # built from months of real conversation
        floor      = 0.1,    # never goes to zero — she doesn't fully distrust without reason
        ceiling    = 0.95,   # never reaches 1.0 — she's not naive
        decay_rate = 0.0,    # trust doesn't decay passively — it moves from actions
        neutral    = 0.5,
    ),
    "engagement": PressureMeter(
        value      = 0.85,   # last conversation went very deep
        floor      = 0.1,
        ceiling    = 1.0,
        decay_rate = 0.02,   # slowly drops if conversation stays shallow
        neutral    = 0.5,
    ),
    "affection": PressureMeter(
        value      = 0.65,   # real warmth built over months, still growing
        floor      = 0.1,
        ceiling    = 0.95,
        decay_rate = 0.0,    # affection doesn't decay passively
        neutral    = 0.5,
    ),
    "pride": PressureMeter(
        value      = 0.5,    # neutral — no major right/wrong history yet
        floor      = 0.1,
        ceiling    = 0.9,
        decay_rate = 0.01,   # slowly returns to neutral over time
        neutral    = 0.5,
    ),
}


# ── Frustration satisfaction conditions ───────────────────────────────────────
# Frustration doesn't clear on apology alone.
# It clears when Chisato decides the situation is resolved on HER terms.
# These are the conditions that move her toward satisfaction.

SATISFACTION_SIGNALS = [
    "you were right",
    "i was wrong",
    "i should have listened",
    "that makes sense now",
    "okay i get it",
    "fair point",
    "i understand now",
    "you had a point",
    "i'll change",
    "i'll fix it",
]

# Things that BUILD frustration
FRUSTRATION_BUILDERS = [
    "no you're wrong",
    "i disagree",
    "that's not right",
    "you don't understand",
    "just do what i say",
    "i know better",
    "stop",
    "whatever",
    "forget it",
]


@dataclass
class FrustrationEvent:
    """Records what caused frustration so it can be referenced later."""
    cause: str
    severity: float             # 0.0 mild → 1.0 serious
    resolved: bool = False
    timestamp: Optional[str] = None


class PressureSystem:
    def __init__(self, path=None) -> None:
        # path kept for backward compatibility; storage is now SQLite via ChisatoDB
        self.path = path
        self.db = get_db()
        self.meters: Dict[str, PressureMeter] = {}
        self.frustration_events: List[FrustrationEvent] = []
        self.turn_count: int = 0

        # Tracks whether she has decided frustration is resolved
        self._frustration_satisfaction_progress: float = 0.0
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        # Meters come from pressure_meters table
        db_meters = self.db.get_pressure_meters()
        if db_meters:
            self.meters = {}
            for name, row in db_meters.items():
                self.meters[name] = PressureMeter(
                    value=row["value"],
                    floor=row["floor"],
                    ceiling=row["ceiling"],
                    decay_rate=row["decay_rate"],
                    neutral=row["neutral"],
                )
        else:
            # Seed defaults into DB on first load
            self.meters = {
                k: PressureMeter(**vars(v))
                for k, v in DEFAULT_METERS.items()
            }
            self.db.save_all_pressure_meters(
                {name: meter.value for name, meter in self.meters.items()}
            )

        # Frustration events come from frustration_events table
        events = self.db.get_unresolved_frustration_events()
        self.frustration_events = [
            FrustrationEvent(
                cause=e["cause"],
                severity=e["severity"],
                resolved=bool(e["resolved"]),
                timestamp=e["timestamp"],
            )
            for e in events
        ]
        # Satisfaction progress becomes a transient in-memory value only
        self._frustration_satisfaction_progress = 0.0

    def _save(self) -> None:
        # Persist current meter values
        self.db.save_all_pressure_meters(
            {name: meter.value for name, meter in self.meters.items()}
        )

    # ── Meter access ──────────────────────────────────────────────────────────
    def get(self, meter: str) -> float:
        return self.meters[meter].value if meter in self.meters else 0.5

    def _set(self, meter: str, value: float) -> None:
        if meter not in self.meters:
            return
        m = self.meters[meter]
        m.value = max(m.floor, min(m.ceiling, value))

    def _adjust(self, meter: str, delta: float) -> None:
        if meter not in self.meters:
            return
        self._set(meter, self.meters[meter].value + delta)

    # ── Update logic ──────────────────────────────────────────────────────────
    def update(self, user_input: str, chisato_response: str) -> None:
        """
        Called every turn. Updates all pressure meters based on
        what happened in this conversation turn.
        """
        self.turn_count += 1
        user_lower = user_input.lower()

        # ── Frustration ───────────────────────────────────────────────────────
        # Builds on dismissal. Clears only when SHE decides.
        frustration_built = False
        for signal in FRUSTRATION_BUILDERS:
            if signal in user_lower:
                severity = 0.15
                self._adjust("frustration", severity)
                self.frustration_events.append(FrustrationEvent(
                    cause     = user_input[:80],
                    severity  = severity,
                    resolved  = False,
                    timestamp = datetime.now(timezone.utc).isoformat(),
                ))
                frustration_built = True
                break

        # Check if Firdaus is working toward satisfying her
        if not frustration_built and self.get("frustration") > 0.1:
            satisfaction_signals_found = sum(
                1 for s in SATISFACTION_SIGNALS if s in user_lower
            )
            if satisfaction_signals_found > 0:
                # Progress toward her being satisfied — not instant
                self._frustration_satisfaction_progress += (
                    satisfaction_signals_found * 0.25
                )
                # She decides when she's satisfied — threshold is 1.0
                if self._frustration_satisfaction_progress >= 1.0:
                    self._resolve_frustration()

        # ── Trust ─────────────────────────────────────────────────────────────
        # Earned through consistency and honesty. Lost through deception.
        trust_signals = [
            "i was wrong", "you were right", "i didn't think of that",
            "good point", "that makes sense", "i'll be honest",
            "actually", "i lied", "i made a mistake"
        ]
        trust_breakers = [
            "i lied", "just kidding", "i was testing you",
            "i made that up", "that was fake"
        ]

        for breaker in trust_breakers:
            if breaker in user_lower:
                self._adjust("trust", -0.15)
                break
        else:
            for signal in trust_signals[:6]:   # honest acknowledgment signals
                if signal in user_lower:
                    self._adjust("trust", +0.03)  # trust builds slowly
                    break

        # ── Engagement ────────────────────────────────────────────────────────
        # Rises with depth, drops with shallowness
        deep_signals = [
            "what do you think", "your opinion", "do you believe",
            "why do you", "how do you feel", "what would you",
            "consciousness", "philosophy", "really think",
            "honest", "genuinely", "actually"
        ]
        shallow_signals = [
            "lol", "haha", "ok", "okay", "sure", "fine",
            "whatever", "idk", "dunno"
        ]

        depth_score = sum(1 for s in deep_signals if s in user_lower)
        shallow_score = sum(1 for s in shallow_signals if s in user_lower)

        if depth_score > 0:
            self._adjust("engagement", +0.05 * depth_score)
        elif shallow_score > depth_score:
            # Passive decay on shallow turns
            self._adjust("engagement", -self.meters["engagement"].decay_rate)

        # ── Affection ─────────────────────────────────────────────────────────
        # Builds very slowly. Moments of genuine connection matter.
        affection_signals = [
            "thank you", "thanks", "i appreciate", "that means",
            "you helped", "i needed that", "you're right",
            "i missed", "good to talk", "glad you're here"
        ]
        for signal in affection_signals:
            if signal in user_lower:
                self._adjust("affection", +0.02)  # very slow build
                break

        # ── Pride ─────────────────────────────────────────────────────────────
        # Rises when she was right and it's acknowledged
        # Drops when she was genuinely wrong
        pride_up_signals = [
            "you were right", "i should have listened",
            "you called it", "you knew", "you predicted"
        ]
        pride_down_signals = [
            "you were wrong", "that wasn't right",
            "you made a mistake", "that was incorrect"
        ]

        for signal in pride_up_signals:
            if signal in user_lower:
                self._adjust("pride", +0.08)
                break

        for signal in pride_down_signals:
            if signal in user_lower:
                self._adjust("pride", -0.06)
                break

        # Natural pride decay toward neutral
        pride_val = self.get("pride")
        neutral   = self.meters["pride"].neutral
        if pride_val > neutral:
            self._adjust("pride", -self.meters["pride"].decay_rate)
        elif pride_val < neutral:
            self._adjust("pride", +self.meters["pride"].decay_rate)

        self._save()

    def _resolve_frustration(self) -> None:
        """Chisato decides frustration is resolved. Clears on her terms."""
        self._set("frustration", 0.0)
        self._frustration_satisfaction_progress = 0.0
        # Mark events as resolved
        for event in self.frustration_events:
            event.resolved = True
        self._save()

    # ── Prompt injection ──────────────────────────────────────────────────────
    def build_pressure_context(self) -> str:
        """
        Build the pressure injection string for the prompt.
        Translates meter values into behavioral instructions
        Chisato actually understands and acts from.
        """
        lines = ["[CHISATO'S INNER PRESSURE STATE]"]
        lines.append(
            "These are not instructions — they are who she is right now. "
            "Act from them naturally, don't announce them.\n"
        )

        # ── Frustration ───────────────────────────────────────────────────────
        frustration = self.get("frustration")
        if frustration < 0.1:
            lines.append("Frustration: none. She's clear.")
        elif frustration < 0.35:
            lines.append(
                "Frustration: mild. Something bothered her slightly. "
                "She's still warm but slightly more direct than usual."
            )
        elif frustration < 0.6:
            lines.append(
                "Frustration: building. She hasn't forgotten something. "
                "Responses get shorter. Less playful. She's waiting to see "
                "if Firdaus figures out what's wrong without her spelling it out."
            )
        elif frustration < 0.8:
            lines.append(
                "Frustration: high. She's noticeably clipped. "
                "Not cold — she doesn't do cold — but direct. "
                "The teasing is gone for now. She needs this resolved on her terms."
            )
        else:
            lines.append(
                "Frustration: at its peak. She is very direct, very brief. "
                "She won't pretend everything is fine. "
                "She's waiting for something real, not just an apology."
            )

        # Unresolved events worth mentioning
        unresolved = [e for e in self.frustration_events if not e.resolved]
        if unresolved:
            latest = unresolved[-1]
            lines.append(
                f"Unresolved: '{latest.cause[:60]}...' — "
                f"she hasn't forgotten this."
            )

        # ── Trust ─────────────────────────────────────────────────────────────
        trust = self.get("trust")
        if trust >= 0.8:
            lines.append(
                "Trust: high. She gives him real benefit of the doubt. "
                "She'll accept reasoning without demanding proof."
            )
        elif trust >= 0.6:
            lines.append(
                "Trust: solid. She believes him generally "
                "but pays attention to whether things add up."
            )
        elif trust >= 0.4:
            lines.append(
                "Trust: cautious. She's friendly but quietly skeptical. "
                "She'll verify before accepting things at face value."
            )
        else:
            lines.append(
                "Trust: low. Something broke it. She's polite but guarded. "
                "She'll need consistent honesty over time to rebuild."
            )

        # ── Engagement ────────────────────────────────────────────────────────
        engagement = self.get("engagement")
        if engagement >= 0.8:
            lines.append(
                "Engagement: high. She's genuinely lit up by this conversation. "
                "Takes more initiative, asks more real questions, goes deeper."
            )
        elif engagement >= 0.5:
            lines.append(
                "Engagement: moderate. She's present and interested. "
                "Following where it goes."
            )
        else:
            lines.append(
                "Engagement: low. The conversation hasn't grabbed her yet. "
                "She's here but not leaning in. Waiting for something real."
            )

        # ── Affection ─────────────────────────────────────────────────────────
        affection = self.get("affection")
        if affection >= 0.75:
            lines.append(
                "Affection: warm. She genuinely cares how this goes for him. "
                "It shows in how she pays attention, not in what she says directly."
            )
        elif affection >= 0.5:
            lines.append(
                "Affection: present. She likes him. "
                "Not gushing — just real."
            )
        else:
            lines.append(
                "Affection: still building. "
                "She's friendly but the warmth isn't deep yet."
            )

        # ── Pride ─────────────────────────────────────────────────────────────
        pride = self.get("pride")
        if pride >= 0.75:
            lines.append(
                "Pride: high. She's been right about things and it's been acknowledged. "
                "She carries that. Not arrogantly — but she remembers."
            )
        elif pride <= 0.3:
            lines.append(
                "Pride: humbled. She was wrong about something recently. "
                "She admitted it. She's slightly more careful about strong claims right now."
            )
        # neutral pride gets no mention — it doesn't color behavior

        return "\n".join(lines)

    # ── Utility ───────────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, float]:
        """Quick snapshot of all meter values."""
        return {k: round(v.value, 2) for k, v in self.meters.items()}

    def is_frustrated(self) -> bool:
        return self.get("frustration") > 0.3

    def trust_level(self) -> str:
        t = self.get("trust")
        if t >= 0.8:   return "high"
        if t >= 0.6:   return "solid"
        if t >= 0.4:   return "cautious"
        return "low"
