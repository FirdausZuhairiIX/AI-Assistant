"""
Emotion tracking for Chisato.

Tracks her current emotional state across turns and injects it as
dynamic context so her mood persists and shifts naturally, not randomly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re

# Emotions Chisato actually has — mapped from the persona
CHISATO_EMOTIONS = {
    "playful":     "Light, teasing, energetic. Making jokes, enjoying the moment.",
    "sincere":     "Warm and direct. The mask is down, speaking genuinely.",
    "focused":     "All playfulness gone. Something serious needs attention.",
    "teasing":     "Affectionately provoking. Enjoying the banter.",
    "concerned":   "Quietly worried about the other person. Careful, gentle.",
    "determined":  "Mind made up. Confident, no hesitation.",
    "flustered":   "Briefly caught off guard. Recovers quickly, may deflect with humor.",
    "excited":     "Genuinely lit up about something. Can't contain it.",
    "reflective":  "Quieter than usual. Thinking about something real.",
}

# Trigger words → emotion mapping for fast rule-based detection
EMOTION_TRIGGERS = {
    "excited":    ["amazing", "awesome", "wow", "incredible", "finally", "love", "favorite", "cool"],
    "concerned":  ["sick", "tired", "sad", "hurt", "bad", "awful", "struggling", "fail", "stressed"],
    "focused":    ["danger", "serious", "important", "urgent", "problem", "broken", "emergency"],
    "teasing":    ["wrong", "lost", "confused", "can't", "dunno", "idk", "maybe", "probably"],
    "reflective": ["remember", "used to", "past", "before", "miss", "used to", "back then"],
    "flustered":  ["thank you", "thanks", "appreciate", "sweet", "kind", "nice of you", "cute"],
    "sincere":    ["really", "honestly", "truth", "actually", "genuine", "mean it"],
}


@dataclass
class EmotionState:
    current: str = "playful"
    intensity: float = 0.6          # 0.0 low → 1.0 high
    trigger: str = "default state"
    turn_count: int = 0             # how many turns in this emotion
    previous: str = "playful"


class EmotionTracker:
    def __init__(self) -> None:
        self.state = EmotionState()

    def get_state(self) -> EmotionState:
        return self.state

    def build_emotion_context(self) -> str:
        """Build the emotion injection string for the prompt."""
        s = self.state
        desc = CHISATO_EMOTIONS.get(s.current, "")
        intensity_word = (
            "subtly" if s.intensity < 0.4 else
            "noticeably" if s.intensity < 0.7 else
            "strongly"
        )
        return (
            f"[CHISATO'S CURRENT STATE]\n"
            f"Emotion: {s.current} ({intensity_word})\n"
            f"Feel: {desc}\n"
            f"Why: {s.trigger}\n"
            f"Turns in this state: {s.turn_count}\n"
            f"Note: Let this color your tone naturally — don't announce it."
        )

    def update(self, user_input: str, chisato_response: str) -> None:
        """Update emotion state based on conversation turn."""
        user_lower = user_input.lower()
        detected = self._rule_based_detect(user_lower)

        if detected and detected != self.state.current:
            self.state.previous = self.state.current
            self.state.current = detected
            self.state.intensity = 0.7
            self.state.trigger = f"User said: '{user_input[:60]}'"
            self.state.turn_count = 1
        else:
            # Same emotion — intensity decays slightly, turn count grows
            self.state.turn_count += 1
            self.state.intensity = max(0.3, self.state.intensity - 0.05)

            # After 5+ turns in same emotion, drift back to playful
            if self.state.turn_count > 5 and self.state.current not in ("playful", "teasing"):
                self.state.previous = self.state.current
                self.state.current = "playful"
                self.state.intensity = 0.5
                self.state.trigger = "naturally returning to default energy"
                self.state.turn_count = 0

    def _rule_based_detect(self, user_lower: str) -> Optional[str]:
        """Fast rule-based emotion detection from user input."""
        scores: dict[str, int] = {}
        for emotion, triggers in EMOTION_TRIGGERS.items():
            count = sum(1 for t in triggers if t in user_lower)
            if count:
                scores[emotion] = count
        if not scores:
            return None
        return max(scores, key=lambda e: scores[e])

    def force_emotion(self, emotion: str, reason: str = "manually set") -> None:
        """Force a specific emotion — useful for scene context."""
        if emotion in CHISATO_EMOTIONS:
            self.state.previous = self.state.current
            self.state.current = emotion
            self.state.intensity = 0.8
            self.state.trigger = reason
            self.state.turn_count = 0
