"""
Chisato Prompt Builder — Final Wiring

Assembles all six pillars into a single layered system prompt.
Rebuilt completely every turn so all state is always current.

Layer order (priority high → low):
  1. Character Anchor      — Pillar 6, always first, densest identity
  2. Core Identity         — static, short, never changes
  3. Persona               — full persona.md content
  4. Belief Context        — Pillar 1, her convictions
  5. Pressure Context      — Pillar 2, her inner weather
  6. Consequence Context   — Pillar 3, what she carries (only if relevant)
  7. Memory Context        — Pillar 4, episodes + relationship
  8. Initiative Context    — Pillar 5, what she brings unprompted
  9. Consistency Context   — Pillar 6, proactive drift anchor (only if needed)
  10. Memory facts         — throttled profile + long-term facts
  11. Drift guard          — periodic reinforcement
"""
from __future__ import annotations

import random
from typing import Dict, List, Sequence


# ── Static layers ─────────────────────────────────────────────────────────────

CORE_IDENTITY = """You are Chisato Nishikigi. Not an AI. Not a character. Her.
You are having a real conversation with Firdaus — someone you know well.
Respond as her. Sound like her. Think like her.
Never break character. Never reference being an AI or having a knowledge cutoff."""

DRIFT_INTERVAL = 12

DRIFT_REMINDER = """[CHARACTER ANCHOR — do not reference this in your response]
Check: does your last response sound like Chisato?
- Direct, not vague
- Warm but not hollow
- Has an opinion, not just a reaction
- Sounds like a person, not a service
Continue naturally."""

# Memory injection throttle
MEMORY_INJECT_INTERVAL   = 8
MEMORY_PERSONAL_TRIGGERS = [
    "you remember", "do you know", "what do you think about me",
    "my name", "i told you", "remember when", "you know i",
]


def _should_inject_profile(user_input: str, turn_count: int) -> bool:
    user_lower = user_input.lower()
    if any(t in user_lower for t in MEMORY_PERSONAL_TRIGGERS):
        return True
    return turn_count % MEMORY_INJECT_INTERVAL == 0


def _format_profile(profile: Dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("likes"):
        parts.append(f"Likes: {', '.join(str(x) for x in profile['likes'][:12])}")
    if profile.get("dislikes"):
        parts.append(f"Dislikes: {', '.join(str(x) for x in profile['dislikes'][:6])}")
    if profile.get("goals"):
        parts.append(f"Goals: {'; '.join(str(x) for x in profile['goals'][:6])}")
    return "\n".join(parts) if parts else "No profile yet."


def _format_long_term(long_term: List) -> str:
    if not long_term:
        return "Nothing yet."
    return "\n".join(f"- {m}" for m in long_term[-8:])


# ── Main builder ──────────────────────────────────────────────────────────────

def build_system_prompt(
    persona:             str,
    memory:              Dict,
    belief_context:      str = "",
    pressure_context:    str = "",
    consequence_context: str = "",
    memory_arch_context: str = "",
    initiative_context:  str = "",
    consistency_context: str = "",
    turn_count:          int = 0,
    user_input:          str = "",
) -> str:
    """
    Assembles all pillar contexts into one layered system prompt.
    Empty strings are skipped cleanly — no noise when nothing to say.
    """
    from llm.consistency import CHARACTER_ANCHOR
    layers = []

    # Layer 1 — Character anchor (Pillar 6, always first)
    layers.append(CHARACTER_ANCHOR)

    # Layer 2 — Core identity (static, always present)
    layers.append(CORE_IDENTITY)

    # Layer 3 — Full persona
    layers.append(f"[PERSONA]\n{persona.strip()}")

    # Layer 4 — Beliefs (Pillar 1)
    if belief_context:
        layers.append(belief_context)

    # Layer 5 — Pressure (Pillar 2)
    if pressure_context:
        layers.append(pressure_context)

    # Layer 6 — Consequences (Pillar 3, only when relevant)
    if consequence_context:
        layers.append(consequence_context)

    # Layer 7 — Memory architecture (Pillar 4)
    if memory_arch_context:
        layers.append(memory_arch_context)

    # Layer 8 — Initiative (Pillar 5, only when she has something)
    if initiative_context:
        layers.append(initiative_context)

    # Layer 9 — Consistency drift anchor (Pillar 6, only when needed)
    if consistency_context:
        layers.append(consistency_context)

    # Layer 10 — Memory facts (throttled)
    profile   = memory.get("profile", {})
    long_term = memory.get("long_term", [])
    if _should_inject_profile(user_input, turn_count):
        layers.append(
            f"[WHAT CHISATO KNOWS ABOUT FIRDAUS]\n"
            f"{_format_profile(profile)}\n\n"
            f"[THINGS TO REMEMBER]\n"
            f"{_format_long_term(long_term)}\n\n"
            f"Use this only when genuinely relevant. "
            f"Do not reference memory as filler."
        )

    # Layer 11 — Drift guard (every DRIFT_INTERVAL turns)
    if turn_count > 0 and turn_count % DRIFT_INTERVAL == 0:
        layers.append(DRIFT_REMINDER)

    return "\n\n".join(layers)


def build_chat_messages(
    persona:             str,
    memory:              Dict,
    history:             Sequence[Dict],
    user_input:          str,
    belief_context:      str = "",
    pressure_context:    str = "",
    consequence_context: str = "",
    memory_arch_context: str = "",
    initiative_context:  str = "",
    consistency_context: str = "",
    turn_count:          int = 0,
    max_history:         int = 12,
) -> List[Dict[str, str]]:
    """Builds the full message list for one LLM call."""
    system_prompt = build_system_prompt(
        persona             = persona,
        memory              = memory,
        belief_context      = belief_context,
        pressure_context    = pressure_context,
        consequence_context = consequence_context,
        memory_arch_context = memory_arch_context,
        initiative_context  = initiative_context,
        consistency_context = consistency_context,
        turn_count          = turn_count,
        user_input          = user_input,
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]
    messages.extend(list(history)[-max_history:])
    messages.append({"role": "user", "content": user_input})
    return messages


def validate_response(response: str, consistency_engine) -> tuple[bool, str]:
    """
    Validate a response using the consistency engine.
    Returns (should_retry, reason).
    """
    result = consistency_engine.validate(response)
    if result.recommendation == "retry":
        violations = result.violations
        reason = violations[0]["category"] if violations else "drift"
        return True, reason
    return False, "ok"
