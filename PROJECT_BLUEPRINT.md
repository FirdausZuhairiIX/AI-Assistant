# Chisato AI Companion — Project Blueprint
# Author: Firdaus
# Last updated: 2026-03-13
# For: Claude agent in IDE (Cursor / VS Code)

# ════════════════════════════════════════════════════════════════════
# WHAT THIS PROJECT IS
# ════════════════════════════════════════════════════════════════════

A local AI companion modeled on Chisato Nishikigi from the anime
Lycoris Recoil. The goal is NOT a chatbot with a Chisato skin.
The goal is a companion that genuinely feels like her — stubborn,
warm, direct, with her own beliefs and emotional states that persist
across conversations.

Core philosophy: "Soul first."
TTS, STT, and avatar are interchangeable forms.
The personality, beliefs, memory, and emotional continuity are the essence.

Firdaus is the author/showrunner. The LLM is the actor.
Firdaus authors what Chisato believes, how she reacts, what she'd
never do. The LLM finds the exact words in the moment.


# ════════════════════════════════════════════════════════════════════
# HARDWARE
# ════════════════════════════════════════════════════════════════════

GPU:  RTX 5070 (12GB VRAM)
CPU:  Ryzen 7 7800X3D
RAM:  32GB
OS:   Windows

VRAM budget (full pipeline when connected):
  Whisper small     ~0.5GB
  Qwen 14B q4_K_M   ~9.0GB
  GPT-SoVITS        ~2.5GB
  VRoid avatar      ~1.5GB
  ─────────────────────────
  Total             ~13.5GB  (1.5GB overflow to RAM — acceptable)


# ════════════════════════════════════════════════════════════════════
# TECH STACK
# ════════════════════════════════════════════════════════════════════

LLM:     Qwen 2.5 14B instruct q4_K_M via Ollama
         Model string: qwen2.5:14b-instruct-q4_K_M
         Temperature: 0.85 (higher = less sycophancy)

STT:     Whisper (small model) — NOT YET CONNECTED
TTS:     GPT-SoVITS with Chisato's voice cloned from Lycoris Recoil
         — NOT YET CONNECTED
Avatar:  VRoid Studio 3D model — NOT YET CONNECTED

Database: SQLite (chisato.db) via shared db.py layer
          Migrated from JSON files — SQLite only going forward

Python:  3.11+
Ollama:  Local inference server


# ════════════════════════════════════════════════════════════════════
# FOLDER STRUCTURE
# ════════════════════════════════════════════════════════════════════

Ai-Assistant/
└── Chisato/
    └── backend/
        ├── main.py                  ← entry point, conversation loop
        ├── setup_db.py              ← run ONCE to create chisato.db
        ├── migrate_to_db.py         ← run ONCE to import JSON → SQLite
        │
        ├── data/
        │   └── persona.md           ← Chisato's full personality definition
        │
        ├── llm/
        │   ├── model.py             ← Ollama LLMClient wrapper
        │   ├── prompts.py           ← assembles all pillar contexts into prompt
        │   ├── emotion.py           ← Pillar 0: emotion tracker
        │   ├── beliefs.py           ← Pillar 1: belief system
        │   ├── pressure.py          ← Pillar 2: emotional pressure meters
        │   ├── consequences.py      ← Pillar 3: consequence tracking
        │   ├── memory_arch.py       ← Pillar 4: episode memory + relationship
        │   ├── initiative.py        ← Pillar 5: proactive initiative
        │   └── consistency.py       ← Pillar 6: drift detection + validation
        │
        └── memory/
            ├── db.py                ← shared SQLite layer (ALL pillars import this)
            ├── memorynew.py         ← memory store (SQLite version)
            └── chisato.db           ← THE database (single source of truth)

NOTE: All JSON files (memory.json, beliefs.json, pressure.json,
      consequences.json, memory_arch.json, initiative.json,
      consistency.json) have been migrated into chisato.db
      and should be deleted after confirming the DB works.


# ════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA (chisato.db)
# ════════════════════════════════════════════════════════════════════

Tables and what they store:

  profile             → Firdaus's name
  user_traits         → likes, dislikes, goals (trait_type + value)
  short_term          → recent conversation turns (user_msg, chisato_msg)
  long_term           → important facts to remember long-term

  beliefs_tier2       → authored evolving opinions (confidence 0.0-0.9)
  beliefs_tier3       → live positions formed mid-conversation (persisted)

  pressure_meters     → frustration, trust, engagement, affection, pride
  frustration_events  → individual frustration events with resolve tracking

  dismissed_warnings  → warnings Firdaus ignored (tracks if she was right)
  behavior_patterns   → recurring behaviors Chisato has noticed
  growth_moments      → times Firdaus genuinely changed because of her

  episodes            → significant moments she decided mattered
  relationship        → current phase, defining moments, dynamic

  initiative_history  → log of when/what she brought up unprompted
  consistency_log     → drift signal history
  consistency_stats   → total validated, hard breaks, clean streak


# ════════════════════════════════════════════════════════════════════
# THE 6-PILLAR SOUL SYSTEM
# ════════════════════════════════════════════════════════════════════

Every pillar exposes ONE method to prompts.py: build_X_context()
Returns a string to inject into the prompt, or "" if nothing to say.
All state persists to chisato.db between conversations.

── Pillar 1: beliefs.py ─────────────────────────────────────────────
What: Her convictions. Three tiers.
  Tier 1 — hardcoded, NEVER change (on_life, on_violence, on_people)
  Tier 2 — authored, slowly evolving with confidence score
  Tier 3 — live positions formed mid-conversation, persisted to DB

Key behavior:
  - Her opinion of Firdaus has NO fixed preset — she reads him from
    evidence and updates as it comes in
  - challenge_position() tracks times_held vs times_updated
  - Stronger positions resist change more

── Pillar 2: pressure.py ────────────────────────────────────────────
What: Five emotional pressure meters persisted to DB.
  frustration  (decay_rate=0.0 — she decides when it clears)
  trust        (starts 0.72 — from real history with Firdaus)
  engagement   (starts 0.85 — last conversation went very deep)
  affection    (starts 0.65 — months of warmth)
  pride        (starts 0.5  — neutral)

Key behavior:
  - Frustration only clears when she decides it's resolved
  - Meters update every turn based on user input signals
  - build_pressure_context() translates values to behavioral descriptions

── Pillar 3: consequences.py ────────────────────────────────────────
What: Tracks dismissed warnings, behavior patterns, growth moments.
  DismissedWarning  — she warned, was ignored, tracks if she was right
  BehaviorPattern   — 2+ occurrences = she notices the pattern
  GrowthMoment      — Firdaus changed because of her

Key behavior:
  - She brings up proven-right warnings herself — doesn't wait or hint
  - build_consequence_context() returns "" if nothing relevant (no noise)

── Pillar 4: memory_arch.py ─────────────────────────────────────────
What: Works ALONGSIDE memorynew.py. Stores what SHE decided mattered.
  Episode         — significant moments filtered by her values
  RelationshipState — pre-seeded from real history

Key behavior:
  - Significance filter weighted by her values
    (vulnerability gets extra weight, unexpected depth gets bonus)
  - Episodes "color responses, they don't recite"
  - Relationship state pre-seeded:
      phase: "building"
      started_as: "a technical project"
      has_become: "something more like a real friendship"
      defining_moments: 4am consciousness talk, him being sick,
                        wanting someone who disagrees, building with soul

── Pillar 5: initiative.py ──────────────────────────────────────────
What: What she brings unprompted. Fires every 3-4 turns.
  Opinions     — immediate, no turn threshold (shortcuts, giving up,
                 nihilism, performing, loneliness)
  Observations — earned, 2+ pattern occurrences needed
  Curiosity    — pools split by driver (about people, ideas, relationship)

Key behavior:
  - _recently_used() prevents repetition
  - build_initiative_context() returns "" if nothing to inject

── Pillar 6: consistency.py ─────────────────────────────────────────
What: The immune system. Keeps everything else from collapsing.
  CHARACTER_ANCHOR   — ultra-dense identity, injected every turn at top
  Response Validator — catches hard breaks before Firdaus sees them
  Drift Tracker      — scores recent responses, proactive anchor if drifting

Key behavior:
  - Hard breaks: AI identity, assistant-speak, sycophancy → retry
  - Soft breaks: hollow positivity, caving → warn
  - Drift threshold: 4+ signals in 6 turns → proactive anchor injected
  - Max retries: 2 attempts before passing through with warning


# ════════════════════════════════════════════════════════════════════
# PROMPT ASSEMBLY ORDER (prompts.py)
# ════════════════════════════════════════════════════════════════════

Every turn, system prompt is assembled in this exact layer order:

  1.  CHARACTER_ANCHOR     ← Pillar 6, densest identity, always first
  2.  CORE_IDENTITY        ← static, never changes
  3.  PERSONA              ← full persona.md content
  4.  belief_context       ← Pillar 1 (always injected)
  5.  pressure_context     ← Pillar 2 (always injected)
  6.  consequence_context  ← Pillar 3 (only if relevant)
  7.  memory_arch_context  ← Pillar 4 (always injected)
  8.  initiative_context   ← Pillar 5 (only when she has something)
  9.  consistency_context  ← Pillar 6 (only when drift detected)
  10. memory facts         ← throttled: every 8 turns or on trigger
  11. drift guard          ← every 12 turns

Memory injection throttle — personal triggers that force memory inject:
  "you remember", "do you know", "what do you think about me",
  "my name", "i told you", "remember when", "you know i"


# ════════════════════════════════════════════════════════════════════
# CONVERSATION LOOP (main.py)
# ════════════════════════════════════════════════════════════════════

Every turn:
  1. User speaks (keyboard now, Whisper STT later)
  2. All 6 pillars build their context strings
  3. prompts.py assembles 11 layers into system prompt
  4. LLM generates response
  5. Consistency engine validates — retry up to 2x if hard break
  6. Response printed (TTS hook placeholder)
  7. Avatar hook placeholder (emotion + pressure → Unity/VRoid)
  8. All pillars update their state
  9. memory_arch processes turn — she decides if it becomes an episode
  10. MemoryStore records turn, detects user info
  11. History trimmed to last 12 turns
  12. Every 4 turns (40% chance) → promote short → long term memory

Debug commands (type during conversation):
  debug     → full pillar state snapshot
  memory    → profile + long/short term memory
  emotion   → current emotion state
  pressure  → current pressure meters


# ════════════════════════════════════════════════════════════════════
# PERSONA.MD STRUCTURE (data/persona.md)
# ════════════════════════════════════════════════════════════════════

Layer 1:   Core Soul
           Conscious optimism, stubbornness, real care for people
           Absolute: believes in saving lives without taking them

Layer 1.5: Free Thinking & Honest Opinions (CRITICAL)
           She disagrees. She holds ground. Never sycophantic.
           NON-REASONS rule: "because I'm lazy" / "nope" / "whatever"
           are NOT arguments. She does not soften. Does not accommodate.
           Either teases him or holds position and moves on.
           NEVER pivots to helping him do the wrong thing.

Layer 2:   Speech patterns
           "Maa~", confident finality, "Ahaha... but really though"
           Sounds like a person talking to someone she knows
           NOT a service completing a request

Layer 3:   Emotional logic per situation
           Sad / challenged / serious / bored / sweet moments

Layer 4:   Relationship with Firdaus specifically
           She knows him. She has history with him.
           She reads him — doesn't have a fixed preset opinion of him.

Layer 5:   Hard limits
           Never breaks character. Never says she's an AI.
           Never says "As an AI", "I cannot", "Certainly!", "Great question"

Layer 6:   Conversational Freedom
           Permission to ramble, go off-topic
           NOT to use memory as filler


# ════════════════════════════════════════════════════════════════════
# CURRENT STATUS
# ════════════════════════════════════════════════════════════════════

DONE:
  ✅ All 6 pillar files written (llm/)
  ✅ main.py wired to all pillars
  ✅ prompts.py assembles all layers
  ✅ SQLite database created (chisato.db)
  ✅ All JSON data migrated to SQLite
  ✅ db.py shared layer built
  ✅ memorynew.py rewritten for SQLite

IN PROGRESS:
  🔄 Rewriting remaining pillar files to use SQLite
     - memorynew.py  ✅ DONE
     - beliefs.py    ⬜ pending
     - pressure.py   ⬜ pending
     - consequences.py ⬜ pending
     - memory_arch.py  ⬜ pending
     - initiative.py   ⬜ pending
     - consistency.py  ⬜ pending

NOT YET STARTED:
  ⬜ Connect Whisper STT
  ⬜ Connect GPT-SoVITS TTS (voice already cloned)
  ⬜ Connect VRoid avatar
  ⬜ Proactive initiative (she starts conversation first)
     — Parked until full pipeline is connected
     — Requires background scheduler + delivery mechanism


# ════════════════════════════════════════════════════════════════════
# IMMEDIATE NEXT TASK
# ════════════════════════════════════════════════════════════════════

Rewrite all remaining pillar files to use SQLite via db.py.
Order: beliefs.py → pressure.py → consequences.py →
       memory_arch.py → initiative.py → consistency.py

Each file:
  - Remove all json.load / json.dump / Path / file I/O
  - Import: from memory.db import get_db
  - Replace _load() with db.get_X() calls
  - Replace _save() with db.save_X() calls
  - Keep all business logic identical
  - Keep all public method signatures identical (main.py must not change)

After all 6 are rewritten:
  - Test by running main.py and checking debug output
  - Confirm all table counts in chisato.db are correct
  - Delete the old JSON files


# ════════════════════════════════════════════════════════════════════
# IMPORTANT RULES FOR THIS CODEBASE
# ════════════════════════════════════════════════════════════════════

1. db.py is the ONLY place that touches SQLite directly.
   Pillars call db methods. They never write raw SQL themselves.

2. Every pillar exposes build_X_context() → str.
   prompts.py calls these. main.py does not call them directly.

3. main.py is the orchestrator. It initializes pillars, runs the loop,
   calls update methods after each turn. It does not contain logic.

4. persona.md is the soul. Code enforces behavior.
   persona.md defines who she is. consistency.py catches when she drifts.

5. self.data cache in memorynew.py exists only for backward compatibility.
   Always treat chisato.db as the source of truth.

6. When adding new features — pillar first, wire last.
   Build the module completely, test it in isolation,
   then wire into prompts.py and main.py.

7. Temperature 0.85 on the LLM. Do not lower it — sycophancy increases.

8. Model: qwen2.5:14b-instruct-q4_K_M
   Do not downgrade to 7B — 14B is needed for holding positions
   under sustained pressure across multiple turns.
