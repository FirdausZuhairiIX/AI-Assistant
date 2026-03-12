"""
Chisato JSON → SQLite Migration Script

Reads all existing JSON files and imports everything into chisato.db.
Safe to run multiple times — uses INSERT OR IGNORE everywhere.

Put this in: Chisato/backend/
Run with:    python migrate_to_db.py

JSON files read from: Chisato/backend/memory/
Database written to:  Chisato/backend/memory/chisato.db
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path(__file__).resolve().parent / "memory"
DB_PATH    = MEMORY_DIR / "chisato.db"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(filename: str) -> dict:
    path = MEMORY_DIR / filename
    if not path.exists():
        print(f"[SKIP] {filename} not found")
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[READ] {filename}")
    return data


def migrate_memory_json(c: sqlite3.Cursor) -> None:
    """memory.json → profile, user_traits, short_term, long_term"""
    data = load_json("memory.json")
    if not data:
        return

    # ── Profile ───────────────────────────────────────────────────────────────
    profile = data.get("profile", {})
    if profile.get("name"):
        c.execute("""
            INSERT OR REPLACE INTO profile (key, value, updated_at)
            VALUES ('name', ?, ?)
        """, (profile["name"], now()))
        print(f"  Profile name: {profile['name']}")

    # ── Likes / dislikes / goals ──────────────────────────────────────────────
    for like in profile.get("likes", []):
        c.execute("""
            INSERT OR IGNORE INTO user_traits (trait_type, value, created_at)
            VALUES ('like', ?, ?)
        """, (like, now()))

    for dislike in profile.get("dislikes", []):
        c.execute("""
            INSERT OR IGNORE INTO user_traits (trait_type, value, created_at)
            VALUES ('dislike', ?, ?)
        """, (dislike, now()))

    for goal in profile.get("goals", []):
        c.execute("""
            INSERT OR IGNORE INTO user_traits (trait_type, value, created_at)
            VALUES ('goal', ?, ?)
        """, (goal, now()))

    likes_count    = len(profile.get("likes", []))
    dislikes_count = len(profile.get("dislikes", []))
    goals_count    = len(profile.get("goals", []))
    print(f"  Traits: {likes_count} likes, {dislikes_count} dislikes, {goals_count} goals")

    # ── Short term ────────────────────────────────────────────────────────────
    short_term = data.get("short_term", [])
    inserted   = 0
    for entry in short_term:
        if isinstance(entry, dict):
            user_msg    = entry.get("user", "")
            chisato_msg = entry.get("assistant", "")
            timestamp   = entry.get("ts", now())
            if user_msg and chisato_msg:
                c.execute("""
                    INSERT OR IGNORE INTO short_term
                    (user_msg, chisato_msg, timestamp)
                    VALUES (?, ?, ?)
                """, (user_msg, chisato_msg, timestamp))
                inserted += 1
    print(f"  Short term: {inserted} entries")

    # ── Long term ─────────────────────────────────────────────────────────────
    long_term = data.get("long_term", [])
    inserted  = 0
    for memory in long_term:
        if isinstance(memory, str) and memory.strip():
            c.execute("""
                INSERT OR IGNORE INTO long_term (memory, created_at)
                VALUES (?, ?)
            """, (memory.strip(), now()))
            inserted += 1
    print(f"  Long term: {inserted} memories")


def migrate_beliefs_json(c: sqlite3.Cursor) -> None:
    """beliefs.json → beliefs_tier2, beliefs_tier3"""
    data = load_json("beliefs.json")
    if not data:
        return

    # ── Tier 2 ────────────────────────────────────────────────────────────────
    tier2    = data.get("tier2", {})
    inserted = 0
    for key, opinion in tier2.items():
        c.execute("""
            INSERT OR REPLACE INTO beliefs_tier2
            (opinion_key, summary, confidence, evidence, open_questions, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            key,
            opinion.get("summary", ""),
            opinion.get("confidence", 0.5),
            json.dumps(opinion.get("evidence", [])),
            json.dumps(opinion.get("open_questions", [])),
            opinion.get("last_updated") or now(),
        ))
        inserted += 1
    print(f"  Beliefs tier2: {inserted} opinions")

    # ── Tier 3 ────────────────────────────────────────────────────────────────
    tier3    = data.get("tier3", {})
    inserted = 0
    for topic, pos in tier3.items():
        c.execute("""
            INSERT OR REPLACE INTO beliefs_tier3
            (topic, position, strength, formed_from,
             times_challenged, times_held, times_updated, formed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            topic,
            pos.get("position", ""),
            pos.get("strength", 0.5),
            pos.get("formed_from", ""),
            pos.get("times_challenged", 0),
            pos.get("times_held", 0),
            pos.get("times_updated", 0),
            pos.get("formed_at") or now(),
        ))
        inserted += 1
    print(f"  Beliefs tier3: {inserted} live positions")


def migrate_pressure_json(c: sqlite3.Cursor) -> None:
    """pressure.json → pressure_meters, frustration_events"""
    data = load_json("pressure.json")
    if not data:
        return

    # ── Meters ────────────────────────────────────────────────────────────────
    meters   = data.get("meters", {})
    inserted = 0
    for name, meter in meters.items():
        c.execute("""
            INSERT OR REPLACE INTO pressure_meters
            (meter_name, value, floor, ceiling, decay_rate, neutral, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            meter.get("value", 0.5),
            meter.get("floor", 0.0),
            meter.get("ceiling", 1.0),
            meter.get("decay_rate", 0.0),
            meter.get("neutral", 0.5),
            now(),
        ))
        inserted += 1
    print(f"  Pressure meters: {inserted} meters")

    # ── Frustration events ────────────────────────────────────────────────────
    events   = data.get("frustration_events", [])
    inserted = 0
    for event in events:
        c.execute("""
            INSERT OR IGNORE INTO frustration_events
            (cause, severity, resolved, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            event.get("cause", ""),
            event.get("severity", 0.0),
            1 if event.get("resolved", False) else 0,
            event.get("timestamp") or now(),
        ))
        inserted += 1
    print(f"  Frustration events: {inserted} events")


def migrate_consequences_json(c: sqlite3.Cursor) -> None:
    """consequences.json → dismissed_warnings, behavior_patterns, growth_moments"""
    data = load_json("consequences.json")
    if not data:
        return

    # ── Dismissed warnings ────────────────────────────────────────────────────
    warnings = data.get("dismissed_warnings", [])
    inserted = 0
    for w in warnings:
        was_right = w.get("was_right")
        if was_right is True:
            was_right = 1
        elif was_right is False:
            was_right = 0
        else:
            was_right = None
        c.execute("""
            INSERT OR IGNORE INTO dismissed_warnings
            (topic, warning, dismissed_at, was_right,
             outcome_note, surfaced_count, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            w.get("topic", ""),
            w.get("warning", ""),
            w.get("dismissed_at") or now(),
            was_right,
            w.get("outcome_note", ""),
            w.get("surfaced_count", 0),
            1 if w.get("resolved", False) else 0,
        ))
        inserted += 1
    print(f"  Dismissed warnings: {inserted}")

    # ── Behavior patterns ─────────────────────────────────────────────────────
    patterns = data.get("patterns", {})
    inserted = 0
    for key, pattern in patterns.items():
        c.execute("""
            INSERT OR REPLACE INTO behavior_patterns
            (pattern_key, behavior, occurrences,
             first_seen, last_seen, chisato_stance, is_positive)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            key,
            pattern.get("behavior", ""),
            pattern.get("occurrences", 1),
            pattern.get("first_seen") or now(),
            pattern.get("last_seen") or now(),
            pattern.get("chisato_stance", ""),
            1 if pattern.get("is_positive", False) else 0,
        ))
        inserted += 1
    print(f"  Behavior patterns: {inserted}")

    # ── Growth moments ────────────────────────────────────────────────────────
    growth   = data.get("growth_moments", [])
    inserted = 0
    for g in growth:
        c.execute("""
            INSERT OR IGNORE INTO growth_moments
            (topic, what_changed, original_stance,
             new_stance, noticed_at, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            g.get("topic", ""),
            g.get("what_changed", ""),
            g.get("original_stance", ""),
            g.get("new_stance", ""),
            g.get("noticed_at") or now(),
            1 if g.get("acknowledged", False) else 0,
        ))
        inserted += 1
    print(f"  Growth moments: {inserted}")


def migrate_memory_arch_json(c: sqlite3.Cursor) -> None:
    """memory_arch.json → episodes, relationship"""
    data = load_json("memory_arch.json")
    if not data:
        return

    # ── Episodes ──────────────────────────────────────────────────────────────
    episodes = data.get("episodes", [])
    inserted = 0
    for ep in episodes:
        c.execute("""
            INSERT OR IGNORE INTO episodes
            (title, what_happened, why_it_mattered,
             emotional_tone, category, timestamp,
             referenced_count, still_relevant)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ep.get("title", ""),
            ep.get("what_happened", ""),
            ep.get("why_it_mattered", ""),
            ep.get("emotional_tone", "neutral"),
            ep.get("category", ""),
            ep.get("timestamp") or now(),
            ep.get("referenced_count", 0),
            1 if ep.get("still_relevant", True) else 0,
        ))
        inserted += 1
    print(f"  Episodes: {inserted}")

    # ── Relationship ──────────────────────────────────────────────────────────
    rel = data.get("relationship", {})
    if rel:
        defining = rel.get("defining_moments", [])
        c.execute("""
            INSERT OR REPLACE INTO relationship
            (id, phase, started_as, has_become,
             defining_moments, current_dynamic, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        """, (
            rel.get("phase", "building"),
            rel.get("started_as", ""),
            rel.get("has_become", ""),
            json.dumps(defining),
            rel.get("current_dynamic", ""),
            rel.get("last_updated") or now(),
        ))
        print(f"  Relationship: phase={rel.get('phase')}, "
              f"{len(defining)} defining moments")


def migrate_initiative_json(c: sqlite3.Cursor) -> None:
    """initiative.json → initiative_history"""
    data = load_json("initiative.json")
    if not data:
        return

    history  = data.get("history", [])
    inserted = 0
    for record in history:
        c.execute("""
            INSERT OR IGNORE INTO initiative_history
            (initiative_type, content, turn_taken, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            record.get("initiative_type", ""),
            record.get("content", ""),
            record.get("turn_taken", 0),
            record.get("timestamp") or now(),
        ))
        inserted += 1
    print(f"  Initiative history: {inserted} records")


def migrate_consistency_json(c: sqlite3.Cursor) -> None:
    """consistency.json → consistency_log, consistency_stats"""
    data = load_json("consistency.json")
    if not data:
        return

    # ── Drift history ─────────────────────────────────────────────────────────
    drift    = data.get("drift_history", [])
    inserted = 0
    for record in drift:
        signals = record.get("drift_signals_found", [])
        c.execute("""
            INSERT OR IGNORE INTO consistency_log
            (response_snippet, drift_signals, drift_score, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            record.get("response_snippet", "")[:200],
            json.dumps(signals),
            record.get("drift_score", 0.0),
            record.get("timestamp") or now(),
        ))
        inserted += 1
    print(f"  Consistency log: {inserted} records")

    # ── Stats ─────────────────────────────────────────────────────────────────
    c.execute("""
        INSERT OR REPLACE INTO consistency_stats
        (id, total_validated, total_hard_breaks,
         total_soft_breaks, consecutive_clean, updated_at)
        VALUES (1, ?, ?, ?, ?, ?)
    """, (
        data.get("total_validated", 0),
        data.get("total_hard_breaks", 0),
        data.get("total_soft_breaks", 0),
        data.get("consecutive_clean", 0),
        now(),
    ))
    print(f"  Consistency stats: migrated")


def verify(conn: sqlite3.Connection) -> None:
    """Print row counts for all tables after migration."""
    c      = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [t[0] for t in c.fetchall()]
    print("\n[VERIFICATION — Row counts]")
    for table in tables:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"  {table:<25} {count} rows")


def main() -> None:
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        print("[ERROR] Run setup_db.py first")
        return

    print(f"[START] Migrating JSON → {DB_PATH}\n")
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    print("── memory.json ──────────────────────────────")
    migrate_memory_json(c)

    print("\n── beliefs.json ─────────────────────────────")
    migrate_beliefs_json(c)

    print("\n── pressure.json ────────────────────────────")
    migrate_pressure_json(c)

    print("\n── consequences.json ────────────────────────")
    migrate_consequences_json(c)

    print("\n── memory_arch.json ─────────────────────────")
    migrate_memory_arch_json(c)

    print("\n── initiative.json ──────────────────────────")
    migrate_initiative_json(c)

    print("\n── consistency.json ─────────────────────────")
    migrate_consistency_json(c)

    conn.commit()
    verify(conn)
    conn.close()

    print("\n[DONE] Migration complete.")
    print("[NOTE] Your JSON files are untouched — kept as backup.")


if __name__ == "__main__":
    main()
