"""
Chisato AI Companion — main.py (SQLite Final)

All JSON file references removed.
All pillars connect directly to chisato.db via db.py.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

# ── Core ──────────────────────────────────────────────────────────────────────
from llm.model        import LLMClient, LLMResponse
from llm.prompts      import build_chat_messages, validate_response
from memory.memorynew import MemoryStore

# ── Pillars ───────────────────────────────────────────────────────────────────
from llm.emotion      import EmotionTracker
from llm.beliefs      import BeliefSystem
from llm.pressure     import PressureSystem
from llm.consequences import ConsequenceSystem
from llm.memory_arch  import MemoryArchitecture
from llm.initiative   import InitiativeSystem
from llm.consistency  import ConsistencyEngine


# ── Config ────────────────────────────────────────────────────────────────────
MAX_HISTORY          = 20
MAX_SHORT_TERM       = 50
MEMORY_PROMOTE_EVERY = 4
MAX_RETRIES          = 2


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_persona(path: Path) -> str:
    if not path.exists():
        return (
            "You are Chisato Nishikigi from Lycoris Recoil. "
            "Cheerful by choice, stubbornly yourself, warm but never hollow. "
            "Never break character. Never say you are an AI."
        )
    return path.read_text(encoding="utf-8").strip()


def print_response(response: LLMResponse) -> None:
    print(f"\nChisato: {response.text}")


def print_debug(
    emotion,
    pressure,
    beliefs,
    consequences,
    memory_arch,
    initiative,
    consistency,
    turn_count: int,
    history_len: int,
) -> None:
    print("\n" + "=" * 60)
    print("DEBUG SNAPSHOT")
    print("=" * 60)

    e = emotion.get_state()
    print(f"Emotion     : {e.current} ({e.intensity:.2f}) — {e.trigger}")

    ps = pressure.summary()
    print(f"Pressure    : {ps}")

    tier3 = beliefs.tier3
    print(f"Live positions: {len(tier3)}")
    for topic, pos in list(tier3.items())[:3]:
        print(f"  [{topic}] {pos.position[:60]}... (strength {pos.strength:.2f})")

    cs = consequences.summary()
    print(f"Consequences: {cs}")

    ms = memory_arch.summary()
    print(f"Episodes    : {ms['total_episodes']} total, "
          f"phase={ms['relationship_phase']}")

    ins = initiative.summary()
    print(f"Initiative  : {ins['total_initiatives']} total, "
          f"{ins['turns_since_last']} turns since last")

    con = consistency.summary()
    print(f"Consistency : {con['consecutive_clean']} clean turns, "
          f"hard breaks={con['total_hard_breaks']}, "
          f"drift={con['recent_drift_scores']}")

    print(f"Turn        : {turn_count}")
    print(f"History     : {history_len} messages")
    print("=" * 60)


def print_memory_snapshot(memory_store: MemoryStore) -> None:
    print("\n" + "=" * 60)
    print("MEMORY SNAPSHOT")
    print("=" * 60)
    data    = memory_store.snapshot()
    profile = data.get("profile", {})

    if profile.get("name"):
        print(f"Name    : {profile['name']}")
    if profile.get("likes"):
        print(f"Likes   : {', '.join(profile['likes'])}")
    if profile.get("goals"):
        print(f"Goals   : {'; '.join(profile['goals'])}")

    long_term = data.get("long_term", [])
    if long_term:
        print(f"\nLong-term ({len(long_term)}):")
        for i, m in enumerate(long_term[-8:], 1):
            print(f"  {i}. {m}")

    short_term = data.get("short_term", [])
    print(f"\nShort-term: {len(short_term)} entries")
    print("=" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    repo_root    = CURRENT_DIR.parent
    persona_path = repo_root / "data" / "persona.md"

    persona = load_persona(persona_path)

    # ── Initialize all pillars ────────────────────────────────────────────────
    # No file paths — all pillars use get_db() internally
    memory_store  = MemoryStore(max_short_term=MAX_SHORT_TERM)
    emotion       = EmotionTracker()
    beliefs       = BeliefSystem()
    pressure      = PressureSystem()
    consequences  = ConsequenceSystem()
    memory_arch   = MemoryArchitecture()
    initiative    = InitiativeSystem()
    consistency   = ConsistencyEngine()
    llm_client    = LLMClient()

    history:             List[Dict[str, str]] = []
    turn_count:          int = 0
    memory_turn_counter: int = 0

    print("=" * 60)
    print("Chisato — Lycoris Recoil Companion")
    print("=" * 60)
    print("Commands: quit | memory | debug | emotion | pressure")
    print("-" * 60)

    # ── Greeting ──────────────────────────────────────────────────────────────
    user_name = memory_store.data.get("profile", {}).get("name", "")
    if user_name:
        print(f"\nChisato: Ah, {user_name}. You're back~ I was wondering when you'd show up.")
    else:
        print("\nChisato: Hey! I'm Chisato. What's your name?")

    # ── Conversation loop ─────────────────────────────────────────────────────
    while True:

        # ── STT hook ──────────────────────────────────────────────────────────
        # TODO: Replace with Whisper STT
        # user_input = stt_client.listen()
        try:
            user_input = input("\nYou: ").strip()
        except KeyboardInterrupt:
            print("\n\nChisato: ...Fine. Take care of yourself, okay?")
            break

        if not user_input:
            continue

        # ── Commands ──────────────────────────────────────────────────────────
        if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
            name = memory_store.data.get("profile", {}).get("name", "")
            print(f"\nChisato: {'See you later, ' + name + '~' if name else 'Bye~'}. "
                  f"Don't disappear too long.")
            break

        if user_input.lower() == "memory":
            print_memory_snapshot(memory_store)
            continue

        if user_input.lower() == "debug":
            print_debug(
                emotion, pressure, beliefs, consequences,
                memory_arch, initiative, consistency,
                turn_count, len(history)
            )
            continue

        if user_input.lower() == "emotion":
            e = emotion.get_state()
            print(f"\n[Emotion: {e.current} | intensity: {e.intensity:.2f} | "
                  f"turns: {e.turn_count} | trigger: {e.trigger}]")
            continue

        if user_input.lower() == "pressure":
            ps = pressure.summary()
            print(f"\n[Pressure: {ps}]")
            continue

        # ── Build all pillar contexts ─────────────────────────────────────────
        memory_context      = memory_store.get_memory_for_prompt(n=5)
        emotion_context     = emotion.build_emotion_context()
        belief_context      = beliefs.build_belief_context(user_input)
        pressure_context    = pressure.build_pressure_context()
        consequence_context = consequences.build_consequence_context(user_input)
        memory_arch_context = memory_arch.build_memory_context(user_input)
        initiative_context  = initiative.build_initiative_context(user_input)
        consistency_context = consistency.build_consistency_context()

        # ── Build messages ────────────────────────────────────────────────────
        messages = build_chat_messages(
            persona             = persona,
            memory              = memory_context,
            history             = history[-MAX_HISTORY:],
            user_input          = user_input,
            belief_context      = belief_context,
            pressure_context    = pressure_context,
            consequence_context = consequence_context,
            memory_arch_context = memory_arch_context,
            initiative_context  = initiative_context,
            consistency_context = consistency_context,
            turn_count          = turn_count,
        )

        # ── LLM call with retry on character break ────────────────────────────
        response = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = llm_client.chat(messages)
            except Exception as e:
                print(f"\nChisato: Mou~ something went wrong... ({e})")
                break

            should_retry, reason = validate_response(response.text, consistency)

            if not should_retry:
                break

            if attempt < MAX_RETRIES:
                print(f"[WARN] Character break: {reason} — retrying ({attempt + 1}/{MAX_RETRIES})")
                anchor = consistency.get_hard_break_anchor()
                messages_with_anchor = messages.copy()
                messages_with_anchor.insert(1, {
                    "role":    "system",
                    "content": anchor,
                })
                messages = messages_with_anchor
            else:
                print(f"[WARN] Could not recover after {MAX_RETRIES} retries")

        if response is None:
            continue

        # ── Output ────────────────────────────────────────────────────────────
        print_response(response)

        # ── TTS hook ──────────────────────────────────────────────────────────
        # TODO: Send response.text to GPT-SoVITS
        # tts_client.speak(response.text)

        # ── Avatar hook ───────────────────────────────────────────────────────
        # TODO: Send emotion + pressure state to Unity/VRoid
        # emotion_state  = emotion.get_state()
        # pressure_state = pressure.summary()
        # avatar_client.animate(emotion_state, pressure_state)

        # ── Update all pillars ────────────────────────────────────────────────
        emotion.update(user_input, response.text)
        pressure.update(user_input, response.text)
        initiative.update(user_input, response.text)

        current_emotion = emotion.get_state().current
        memory_arch.process_turn(user_input, response.text, current_emotion)

        memory_store.record_turn(user_input, response.text)
        memory_store.detect_and_save_user_info(user_input, response.text, llm_client)

        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant",  "content": response.text})
        if len(history) > MAX_HISTORY * 2:
            history = history[-MAX_HISTORY * 2:]

        turn_count          += 1
        memory_turn_counter += 1

        if memory_turn_counter >= MEMORY_PROMOTE_EVERY and random.random() > 0.4:
            memory_store.promote_short_to_long_term(llm=llm_client, n=10)
            memory_turn_counter = 0


if __name__ == "__main__":
    main()
