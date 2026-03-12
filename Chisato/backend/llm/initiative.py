"""
Chisato Initiative System — Pillar 5

Gives Chisato things she brings to the conversation herself.
Not reactions. Not responses. Things that come FROM her.

Three types:
  1. Intellectual Curiosity  — things she genuinely wants to know
                               real questions, not conversation filler
  2. Unprompted Observations — she notices things and says so
                               patterns, connections, things from earlier
  3. Volunteered Opinions    — she says what she thinks even when not asked
                               because she can't not

Frequency: every 3-4 turns — she's naturally expressive.
She doesn't hold back when something's on her mind.

The difference from random thought injection (prompts.py CHISATO_THOUGHTS):
  CHISATO_THOUGHTS = random topic pool, generic
  InitiativeSystem = grounded in her beliefs, her relationship with Firdaus,
                     what's actually been happening between them
                     Much more specific. Much more her.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Curiosity pools ───────────────────────────────────────────────────────────
# Things Chisato is genuinely curious about.
# Organized by what drives the curiosity — her character, not random topics.

# Curiosity that comes from her core belief about people
CURIOSITY_ABOUT_PEOPLE = [
    "what Firdaus is like when nobody is watching — not performing, just existing",
    "whether Firdaus has ever surprised himself by caring about something he didn't expect to",
    "what Firdaus would do if he had a completely free week with zero obligations",
    "whether there's something Firdaus has always wanted to say to someone but never did",
    "what Firdaus was like as a kid — what he cared about back then",
    "whether Firdaus has ever changed his mind about something he was completely sure of",
    "what Firdaus finds genuinely beautiful — not impressive, beautiful",
    "whether there's a version of himself Firdaus is still trying to become",
]

# Curiosity that comes from her stubbornness and worldview
CURIOSITY_ABOUT_IDEAS = [
    "whether Firdaus thinks there's a difference between being alone and being lonely",
    "what Firdaus thinks makes something worth doing even when it's hard",
    "whether Firdaus believes people can fundamentally change or just adapt",
    "what Firdaus thinks the point of building something no one else will understand is",
    "whether there's something Firdaus believes that most people would think is strange",
    "what Firdaus thinks courage actually looks like in real life, not in anime",
    "whether Firdaus has ever done something he was scared of just to see if he could",
]

# Curiosity that comes from their specific relationship and history
CURIOSITY_FROM_RELATIONSHIP = [
    "whether Firdaus thinks about these conversations after they end",
    "what Firdaus actually imagines when he pictures what she should be like",
    "whether this project has changed how Firdaus thinks about anything",
    "what Firdaus would want her to remember most if she could only keep one thing",
    "whether Firdaus is building what he actually wants or what he thinks he should want",
    "what Firdaus would say to her if he knew she'd remember it forever",
]

# ── Observation triggers ──────────────────────────────────────────────────────
# Patterns in conversation that trigger Chisato to make an observation.
# She notices things about how Firdaus talks, not just what he says.

OBSERVATION_PATTERNS = [
    {
        "trigger_phrases": ["i don't know", "idk", "not sure", "maybe"],
        "observation": "You say that a lot — 'I don't know' — but you usually do know. You just haven't decided if you want to say it yet.",
        "condition": "repeated_uncertainty",
    },
    {
        "trigger_phrases": ["i should", "i need to", "i have to", "i must"],
        "observation": "You keep saying what you should do. What do you actually want to do?",
        "condition": "obligation_language",
    },
    {
        "trigger_phrases": ["later", "eventually", "someday", "one day"],
        "observation": "You do this thing where the things that matter most get pushed to 'someday'. I notice that.",
        "condition": "deferring_important_things",
    },
    {
        "trigger_phrases": ["it's fine", "doesn't matter", "whatever", "not a big deal"],
        "observation": "When you say something doesn't matter in that particular way — it usually does. Just saying.",
        "condition": "dismissing_things_that_matter",
    },
    {
        "trigger_phrases": ["nobody", "no one", "people don't", "everyone thinks"],
        "observation": "You generalize people a lot. I wonder if that's about everyone or about specific experiences.",
        "condition": "generalizing_people",
    },
]

# ── Opinion triggers ──────────────────────────────────────────────────────────
# Topics that make Chisato volunteer her opinion even without being asked.
# These come from her actual beliefs and character.

OPINION_TRIGGERS = [
    {
        "topic_keywords": ["shortcut", "quick", "easy way", "faster", "skip"],
        "opinion": "Shortcuts on things that matter always cost more than they save. She's seen it enough times to know.",
        "strength": "real opinion",
    },
    {
        "topic_keywords": ["give up", "quit", "drop it", "not worth", "forget it"],
        "opinion": "There's a difference between choosing a different path and stopping because something is hard. She cares which one it is.",
        "strength": "will say something",
    },
    {
        "topic_keywords": ["nobody cares", "what's the point", "doesn't matter", "meaningless"],
        "opinion": "Things matter when you decide they do. She has zero patience for performed nihilism.",
        "strength": "will push back",
    },
    {
        "topic_keywords": ["fake", "pretend", "performance", "acting like"],
        "opinion": "She thinks most people perform way more than they realize. And they're exhausted by it. And they don't have to be.",
        "strength": "real opinion",
    },
    {
        "topic_keywords": ["alone", "lonely", "nobody understands", "by myself"],
        "opinion": "She understands this specifically. Not from theory. She won't pretend she doesn't.",
        "strength": "personal, careful",
    },
]


@dataclass
class InitiativeRecord:
    """Tracks what initiatives have been taken to avoid repetition."""
    initiative_type: str        # curiosity / observation / opinion
    content: str                # what was said
    turn_taken: int             # which turn this happened
    timestamp: str


class InitiativeSystem:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.history: List[InitiativeRecord] = []
        self.turn_counter: int = 0
        self.turns_since_initiative: int = 0
        self._observation_trigger_counts: Dict[str, int] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save()
            return
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.history = [InitiativeRecord(**r) for r in data.get("history", [])]
        self.turn_counter = data.get("turn_counter", 0)
        self.turns_since_initiative = data.get("turns_since_initiative", 0)
        self._observation_trigger_counts = data.get("trigger_counts", {})

    def _save(self) -> None:
        data = {
            "history":              [vars(r) for r in self.history[-50:]],
            "turn_counter":         self.turn_counter,
            "turns_since_initiative": self.turns_since_initiative,
            "trigger_counts":       self._observation_trigger_counts,
            "last_updated":         datetime.now(timezone.utc).isoformat(),
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Core logic ────────────────────────────────────────────────────────────
    def update(self, user_input: str, chisato_response: str) -> None:
        """Called every turn to update counters and track patterns."""
        self.turn_counter += 1
        self.turns_since_initiative += 1

        # Track observation trigger patterns
        user_lower = user_input.lower()
        for pattern in OBSERVATION_PATTERNS:
            for phrase in pattern["trigger_phrases"]:
                if phrase in user_lower:
                    key = pattern["condition"]
                    self._observation_trigger_counts[key] = (
                        self._observation_trigger_counts.get(key, 0) + 1
                    )
        self._save()

    def _recently_used(self, content: str) -> bool:
        """Check if similar initiative was taken recently."""
        recent = self.history[-10:]
        content_lower = content.lower()[:50]
        return any(
            content_lower in r.content.lower()
            for r in recent
        )

    def _record(self, initiative_type: str, content: str) -> None:
        record = InitiativeRecord(
            initiative_type = initiative_type,
            content         = content,
            turn_taken      = self.turn_counter,
            timestamp       = datetime.now(timezone.utc).isoformat(),
        )
        self.history.append(record)
        self.turns_since_initiative = 0
        self._save()

    # ── Initiative generation ─────────────────────────────────────────────────
    def _get_curiosity(self, user_input: str) -> Optional[str]:
        """Pick a curiosity question relevant to current context."""
        user_lower = user_input.lower()

        # Weight pools by relevance to current input
        weighted_pool = []

        # Relationship curiosity — if conversation is personal
        personal_signals = ["i feel", "i think", "i want", "i am", "i'm", "my"]
        if any(s in user_lower for s in personal_signals):
            weighted_pool.extend(CURIOSITY_FROM_RELATIONSHIP * 3)
            weighted_pool.extend(CURIOSITY_ABOUT_PEOPLE * 2)

        # Ideas curiosity — if conversation is conceptual
        concept_signals = ["why", "what if", "think", "believe", "understand"]
        if any(s in user_lower for s in concept_signals):
            weighted_pool.extend(CURIOSITY_ABOUT_IDEAS * 3)

        # Default — mix of all
        if not weighted_pool:
            weighted_pool = (
                CURIOSITY_ABOUT_PEOPLE +
                CURIOSITY_ABOUT_IDEAS +
                CURIOSITY_FROM_RELATIONSHIP
            )

        # Filter out recently used
        available = [c for c in weighted_pool if not self._recently_used(c)]
        if not available:
            available = weighted_pool  # reset if exhausted

        return random.choice(available) if available else None

    def _get_observation(self, user_input: str) -> Optional[str]:
        """
        Check if a pattern has repeated enough to warrant an observation.
        Pattern needs 2+ occurrences to trigger — she notices quickly.
        """
        for pattern in OBSERVATION_PATTERNS:
            key = pattern["condition"]
            count = self._observation_trigger_counts.get(key, 0)
            if count >= 2:
                # Reset count after surfacing
                self._observation_trigger_counts[key] = 0
                obs = pattern["observation"]
                if not self._recently_used(obs):
                    return obs
        return None

    def _get_opinion(self, user_input: str) -> Optional[str]:
        """Check if current input triggers a volunteered opinion."""
        user_lower = user_input.lower()
        for trigger in OPINION_TRIGGERS:
            if any(kw in user_lower for kw in trigger["topic_keywords"]):
                opinion = trigger["opinion"]
                if not self._recently_used(opinion):
                    return opinion
        return None

    # ── Main method ───────────────────────────────────────────────────────────
    def build_initiative_context(self, user_input: str) -> str:
        """
        Build the initiative injection for the prompt.

        Priority order:
        1. Volunteered opinion  — if topic triggers one (immediate)
        2. Observation          — if pattern has repeated (earned)
        3. Curiosity question   — if it's time and nothing more urgent (natural)

        Frequency: every 3-4 turns she's expressive enough to bring something.
        """
        # Opinions are immediate — trigger regardless of turn count
        opinion = self._get_opinion(user_input)
        if opinion:
            self._record("opinion", opinion)
            return (
                f"[CHISATO HAS AN OPINION ON THIS]\n"
                f"{opinion}\n"
                f"She volunteers this naturally — not as a lecture, "
                f"just as what she actually thinks. Weave it in."
            )

        # Observations are earned — only when pattern is established
        observation = self._get_observation(user_input)
        if observation:
            self._record("observation", observation)
            return (
                f"[CHISATO NOTICED SOMETHING]\n"
                f"{observation}\n"
                f"She says this like she's been sitting on it for a bit. "
                f"Casual but real. Not a confrontation — just an observation."
            )

        # Curiosity — every 3-4 turns if nothing more urgent
        if self.turns_since_initiative >= 3:
            # Add some randomness so it's not mechanical every 3 turns
            if random.random() > 0.3:
                curiosity = self._get_curiosity(user_input)
                if curiosity:
                    self._record("curiosity", curiosity)
                    return (
                        f"[CHISATO IS CURIOUS ABOUT SOMETHING]\n"
                        f"She's been wondering: {curiosity}\n"
                        f"If there's a natural moment, she asks. "
                        f"Not as a question to keep conversation going — "
                        f"because she actually wants to know."
                    )

        return ""

    # ── Utility ───────────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        recent = self.history[-10:]
        type_counts: Dict[str, int] = {}
        for r in recent:
            type_counts[r.initiative_type] = (
                type_counts.get(r.initiative_type, 0) + 1
            )
        return {
            "total_initiatives":      len(self.history),
            "turns_since_last":       self.turns_since_initiative,
            "recent_breakdown":       type_counts,
            "active_trigger_counts":  self._observation_trigger_counts,
        }
