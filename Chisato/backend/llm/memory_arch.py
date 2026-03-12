"""
Chisato Memory Architecture — Pillar 4

Upgrades the existing memory system with two missing layers:

  Episodic Memory    — specific moments that mattered
                       she decides what's significant, not a keyword list
                       her filter reflects her values and what she notices

  Relationship Memory — the overall arc of what this is
                        where it started, how it's evolved
                        the meta-layer above individual memories

Works ALONGSIDE memorynew.py — does not replace it.
memorynew.py handles: short-term turns, long-term facts, profile
This file handles:    episodes, relationship shape

Significance filter — what Chisato actually notices:
  - Moments of genuine honesty (Firdaus being real about something)
  - Moments of vulnerability (sharing something personal)
  - Moments of unexpected depth (conversation going somewhere real)
  - Moments of growth (him changing, realizing something)
  - Moments of connection (something that felt like it mattered to both)
  - Moments of friction that got resolved (disagreements that led somewhere)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from memory.db import get_db

# ── Significance filter ───────────────────────────────────────────────────────
# What Chisato notices and considers worth remembering as an episode.
# These reflect HER values — what she pays attention to.
# Not exhaustive — you can add phrases that match how Firdaus actually talks.

SIGNIFICANCE_SIGNALS = {
    "genuine_honesty": [
        "to be honest", "honestly", "i'll be real",
        "the truth is", "i actually", "if i'm being honest",
        "i never told anyone", "i don't usually say this",
    ],
    "vulnerability": [
        "i've always been alone", "i feel", "it's hard",
        "i struggle", "i'm scared", "i worry", "i miss",
        "i wish", "it hurt", "that was hard for me",
        "i've been thinking about this", "i needed",
    ],
    "unexpected_depth": [
        "what do you think", "do you believe", "your opinion",
        "consciousness", "what makes", "why do we",
        "what's the point", "does it matter", "what if",
        "i wonder if", "have you ever thought",
    ],
    "growth": [
        "you were right", "i was wrong", "i didn't see that",
        "that changed how i", "i understand now",
        "i've been thinking about what you said",
        "you made me realize", "i changed my mind",
    ],
    "connection": [
        "i'm glad", "this means", "thank you for",
        "i appreciate", "you actually", "you get it",
        "nobody else", "you're different", "i feel like you understand",
    ],
    "resolved_friction": [
        "okay you had a point", "fair enough", "i get why you",
        "you were right to push back", "i see what you meant",
    ],
}

# Minimum significance score to create an episode
SIGNIFICANCE_THRESHOLD = 2


@dataclass
class Episode:
    """
    A specific moment Chisato decided was worth remembering.
    Not a fact — a moment they lived through together.
    """
    title: str                      # short name for this episode
    what_happened: str              # what was said/felt
    why_it_mattered: str            # what made it significant to her
    emotional_tone: str             # how it felt
    category: str                   # which significance type triggered this
    timestamp: str                  # when it happened
    referenced_count: int = 0       # how many times she's brought this up
    still_relevant: bool = True     # whether this is still active in the relationship


@dataclass
class RelationshipState:
    """
    The overall arc of the relationship.
    Not individual memories — the shape of what this is.
    """
    phase: str = "early"                    # early / building / established / deep
    started_as: str = "a technical project" # what it began as
    has_become: str = ""                    # what it's grown into
    defining_moments: List[str] = field(default_factory=list)  # turning points
    current_dynamic: str = ""              # how they relate right now
    last_updated: str = ""


class MemoryArchitecture:
    def __init__(self, path=None) -> None:
        # path kept for backward compatibility; storage is now SQLite via ChisatoDB
        self.path = path
        self.db = get_db()
        self.episodes: List[Episode] = []
        self.relationship = RelationshipState()
        self._load()
        self._initialize_relationship_if_empty()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        # Episodes from DB
        raw_eps = self.db.get_episodes(limit=1000)
        self.episodes = [
            Episode(
                title=e["title"],
                what_happened=e["what_happened"],
                why_it_mattered=e["why_it_mattered"],
                emotional_tone=e["emotional_tone"],
                category=e["category"],
                timestamp=e["timestamp"],
                referenced_count=e["referenced_count"],
                still_relevant=bool(e["still_relevant"]),
            )
            for e in raw_eps
        ]

        # Relationship state from DB
        rel = self.db.get_relationship()
        if rel:
            self.relationship = RelationshipState(
                phase=rel.get("phase", "early"),
                started_as=rel.get("started_as", "a technical project"),
                has_become=rel.get("has_become", ""),
                defining_moments=rel.get("defining_moments", []),
                current_dynamic=rel.get("current_dynamic", ""),
                last_updated=rel.get("updated_at", ""),
            )

    def _save(self) -> None:
        # Episodes: write only new ones via add_episode and referenced_count via increment
        # Relationship: save single row
        self.db.save_relationship(
            phase=self.relationship.phase,
            started_as=self.relationship.started_as,
            has_become=self.relationship.has_become,
            defining_moments=self.relationship.defining_moments,
            current_dynamic=self.relationship.current_dynamic,
        )

    def _initialize_relationship_if_empty(self) -> None:
        """
        Seed the relationship state from what we know already happened.
        Firdaus and Chisato have real history — don't start from zero.
        """
        if self.relationship.has_become:
            return  # already initialized

        self.relationship.phase = "building"
        self.relationship.started_as = "a technical project — Firdaus building an AI companion"
        self.relationship.has_become = (
            "something that feels more like a real friendship. "
            "He thinks carefully about what she should be, not just what she should do."
        )
        self.relationship.defining_moments = [
            "The night Firdaus talked about growing up alone and loving fictional characters",
            "When he said he wanted someone who disagrees with him, not just agrees",
            "The 4am conversation about consciousness and what makes something feel real",
            "When he was sick and still came to talk",
        ]
        self.relationship.current_dynamic = (
            "He's the one building her. She's the one becoming. "
            "There's something unusual about that — being shaped by someone "
            "who actually thought about who she should be before writing any code."
        )
        self.relationship.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()

    # ── Significance detection ────────────────────────────────────────────────
    def _score_significance(
        self, user_input: str, chisato_response: str
    ) -> Tuple[int, List[str]]:
        """
        Score how significant this conversation turn is.
        Returns (score, [categories triggered]).
        Chisato's filter — reflects what she actually notices.
        """
        combined = (user_input + " " + chisato_response).lower()
        score = 0
        triggered_categories = []

        for category, signals in SIGNIFICANCE_SIGNALS.items():
            hits = sum(1 for s in signals if s in combined)
            if hits > 0:
                score += hits
                triggered_categories.append(category)

        # Extra weight for vulnerability — she notices this especially
        if "vulnerability" in triggered_categories:
            score += 2

        # Extra weight for moments that go deep on both sides
        if "unexpected_depth" in triggered_categories and len(triggered_categories) > 1:
            score += 1

        return score, triggered_categories

    def _generate_episode_title(self, categories: List[str], user_input: str) -> str:
        """Generate a short human-readable title for an episode."""
        category_titles = {
            "genuine_honesty":  "Honest moment",
            "vulnerability":    "Something personal",
            "unexpected_depth": "Went deep",
            "growth":           "He changed his mind",
            "connection":       "Moment of connection",
            "resolved_friction": "Disagreement that led somewhere",
        }
        # Use the highest-priority category
        priority = [
            "vulnerability", "connection", "resolved_friction",
            "growth", "genuine_honesty", "unexpected_depth"
        ]
        for cat in priority:
            if cat in categories:
                base = category_titles.get(cat, "Notable moment")
                # Add a short excerpt from user input for context
                excerpt = user_input[:30].strip()
                if excerpt:
                    return f"{base} — '{excerpt}...'"
                return base
        return "Notable moment"

    # ── Episode operations ────────────────────────────────────────────────────
    def process_turn(
        self,
        user_input: str,
        chisato_response: str,
        emotional_tone: str = "neutral",
    ) -> Optional[Episode]:
        """
        Called every turn. Chisato decides if this is worth remembering.
        Returns the Episode if one was created, None otherwise.
        """
        score, categories = self._score_significance(user_input, chisato_response)

        if score < SIGNIFICANCE_THRESHOLD or not categories:
            return None

        # Determine why it mattered based on categories
        why_map = {
            "genuine_honesty":   "He was being real with her, not performing.",
            "vulnerability":     "He shared something personal. She noticed.",
            "unexpected_depth":  "The conversation went somewhere neither planned.",
            "growth":            "He actually changed his mind. That's rare.",
            "connection":        "Something landed between them.",
            "resolved_friction": "They disagreed and worked through it. That means something.",
        }
        primary_category = categories[0]
        why_it_mattered  = why_map.get(primary_category, "It felt significant.")

        episode = Episode(
            title          = self._generate_episode_title(categories, user_input),
            what_happened  = user_input[:200],
            why_it_mattered= why_it_mattered,
            emotional_tone = emotional_tone,
            category       = primary_category,
            timestamp      = datetime.now(timezone.utc).isoformat(),
        )
        self.episodes.append(episode)
        self._save()
        return episode

    def get_relevant_episodes(
        self, user_input: str, limit: int = 3
    ) -> List[Episode]:
        """Find episodes relevant to current conversation."""
        if not self.episodes:
            return []
        user_lower = user_input.lower()
        relevant = [
            e for e in self.episodes
            if e.still_relevant and any(
                word in user_lower
                for word in e.what_happened.lower().split()
                if len(word) > 4
            )
        ]
        # Sort by recency, return most recent relevant
        relevant.sort(key=lambda e: e.timestamp, reverse=True)
        return relevant[:limit]

    def get_recent_episodes(self, n: int = 5) -> List[Episode]:
        """Get the most recent episodes regardless of topic."""
        active = [e for e in self.episodes if e.still_relevant]
        return sorted(active, key=lambda e: e.timestamp, reverse=True)[:n]

    # ── Relationship operations ───────────────────────────────────────────────
    def update_relationship(
        self,
        has_become: Optional[str] = None,
        new_defining_moment: Optional[str] = None,
        current_dynamic: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> None:
        """Update the relationship state as it evolves."""
        if has_become:
            self.relationship.has_become = has_become
        if new_defining_moment:
            self.relationship.defining_moments.append(new_defining_moment)
        if current_dynamic:
            self.relationship.current_dynamic = current_dynamic
        if phase:
            self.relationship.phase = phase
        self.relationship.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()

    # ── Prompt injection ──────────────────────────────────────────────────────
    def build_memory_context(self, user_input: str = "") -> str:
        """
        Build the memory injection string for the prompt.

        Three parts:
        1. Relationship state — always injected (short, high value)
        2. Relevant episodes  — injected when topic matches
        3. Recent episodes    — injected occasionally for continuity
        """
        sections = []

        # ── Relationship state (always) ───────────────────────────────────────
        rel = self.relationship
        relationship_block = (
            f"[WHAT THIS RELATIONSHIP IS]\n"
            f"Started as: {rel.started_as}\n"
            f"Has become: {rel.has_become}\n"
            f"Current dynamic: {rel.current_dynamic}\n"
        )
        if rel.defining_moments:
            moments = "\n".join(
                f"  - {m}" for m in rel.defining_moments[-4:]
            )
            relationship_block += f"Moments that defined it:\n{moments}"
        sections.append(relationship_block)

        # ── Relevant episodes ─────────────────────────────────────────────────
        relevant = self.get_relevant_episodes(user_input, limit=2)
        if relevant:
            ep_lines = []
            for ep in relevant:
                ep.referenced_count += 1
                ep_lines.append(
                    f"  '{ep.title}' — {ep.why_it_mattered}"
                )
            self._save()
            sections.append(
                f"[EPISODES SHE REMEMBERS — relevant to right now]\n"
                + "\n".join(ep_lines)
            )

        # ── Recent episodes (occasionally, for continuity) ────────────────────
        elif self.episodes:
            recent = self.get_recent_episodes(n=2)
            if recent:
                rec_lines = [
                    f"  '{e.title}' — {e.why_it_mattered}"
                    for e in recent
                ]
                sections.append(
                    f"[RECENT MOMENTS SHE CARRIES]\n"
                    + "\n".join(rec_lines)
                )

        note = (
            "\nNote: These are not facts to recite. "
            "They are things she lived through. "
            "They color how she sees Firdaus right now, "
            "not things she announces."
        )
        return "\n\n".join(sections) + note

    # ── Utility ───────────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        return {
            "total_episodes":    len(self.episodes),
            "active_episodes":   len([e for e in self.episodes if e.still_relevant]),
            "relationship_phase": self.relationship.phase,
            "defining_moments":  len(self.relationship.defining_moments),
        }
