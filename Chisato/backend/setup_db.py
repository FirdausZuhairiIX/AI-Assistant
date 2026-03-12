"""
Chisato Database Setup Script

Run this ONCE to create the SQLite database with all tables.
Creates: Chisato/backend/memory/chisato.db

Usage:
    python setup_db.py
"""
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "memory" / "chisato.db"


def create_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Profile ───────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)

    # ── Short term memory ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS short_term (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_msg    TEXT NOT NULL,
            chisato_msg TEXT NOT NULL,
            timestamp   TEXT NOT NULL
        )
    """)

    # ── Long term memory ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS long_term (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            memory      TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL
        )
    """)

    # ── Likes / dislikes / goals ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_traits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trait_type  TEXT NOT NULL,   -- 'like', 'dislike', 'goal'
            value       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            UNIQUE(trait_type, value)
        )
    """)

    # ── Pillar 1 — Beliefs tier 2 ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS beliefs_tier2 (
            opinion_key     TEXT PRIMARY KEY,
            summary         TEXT NOT NULL,
            confidence      REAL NOT NULL DEFAULT 0.5,
            evidence        TEXT NOT NULL DEFAULT '[]',   -- JSON array
            open_questions  TEXT NOT NULL DEFAULT '[]',   -- JSON array
            updated_at      TEXT
        )
    """)

    # ── Pillar 1 — Beliefs tier 3 (live positions) ────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS beliefs_tier3 (
            topic               TEXT PRIMARY KEY,
            position            TEXT NOT NULL,
            strength            REAL NOT NULL DEFAULT 0.5,
            formed_from         TEXT NOT NULL,
            times_challenged    INTEGER DEFAULT 0,
            times_held          INTEGER DEFAULT 0,
            times_updated       INTEGER DEFAULT 0,
            formed_at           TEXT
        )
    """)

    # ── Pillar 2 — Pressure meters ────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS pressure_meters (
            meter_name  TEXT PRIMARY KEY,
            value       REAL NOT NULL,
            floor       REAL NOT NULL,
            ceiling     REAL NOT NULL,
            decay_rate  REAL NOT NULL,
            neutral     REAL NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)

    # ── Pillar 2 — Frustration events ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS frustration_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cause           TEXT NOT NULL,
            severity        REAL NOT NULL,
            resolved        INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
            timestamp       TEXT NOT NULL
        )
    """)

    # ── Pillar 3 — Dismissed warnings ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS dismissed_warnings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            topic           TEXT NOT NULL,
            warning         TEXT NOT NULL,
            dismissed_at    TEXT NOT NULL,
            was_right       INTEGER,        -- NULL=unknown, 1=yes, 0=no
            outcome_note    TEXT DEFAULT '',
            surfaced_count  INTEGER DEFAULT 0,
            resolved        INTEGER DEFAULT 0
        )
    """)

    # ── Pillar 3 — Behavior patterns ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS behavior_patterns (
            pattern_key     TEXT PRIMARY KEY,
            behavior        TEXT NOT NULL,
            occurrences     INTEGER DEFAULT 1,
            first_seen      TEXT NOT NULL,
            last_seen       TEXT NOT NULL,
            chisato_stance  TEXT DEFAULT '',
            is_positive     INTEGER DEFAULT 0
        )
    """)

    # ── Pillar 3 — Growth moments ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS growth_moments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            topic           TEXT NOT NULL,
            what_changed    TEXT NOT NULL,
            original_stance TEXT NOT NULL,
            new_stance      TEXT NOT NULL,
            noticed_at      TEXT NOT NULL,
            acknowledged    INTEGER DEFAULT 0
        )
    """)

    # ── Pillar 4 — Episodes ───────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT NOT NULL,
            what_happened       TEXT NOT NULL,
            why_it_mattered     TEXT NOT NULL,
            emotional_tone      TEXT NOT NULL,
            category            TEXT NOT NULL,
            timestamp           TEXT NOT NULL,
            referenced_count    INTEGER DEFAULT 0,
            still_relevant      INTEGER DEFAULT 1
        )
    """)

    # ── Pillar 4 — Relationship state ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS relationship (
            id                  INTEGER PRIMARY KEY DEFAULT 1,
            phase               TEXT NOT NULL DEFAULT 'early',
            started_as          TEXT NOT NULL DEFAULT '',
            has_become          TEXT NOT NULL DEFAULT '',
            defining_moments    TEXT NOT NULL DEFAULT '[]',  -- JSON array
            current_dynamic     TEXT NOT NULL DEFAULT '',
            updated_at          TEXT NOT NULL DEFAULT ''
        )
    """)

    # ── Pillar 5 — Initiative history ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS initiative_history (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            initiative_type     TEXT NOT NULL,  -- curiosity/observation/opinion
            content             TEXT NOT NULL,
            turn_taken          INTEGER NOT NULL,
            timestamp           TEXT NOT NULL
        )
    """)

    # ── Pillar 6 — Consistency log ────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS consistency_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            response_snippet    TEXT NOT NULL,
            drift_signals       TEXT NOT NULL DEFAULT '[]',  -- JSON array
            drift_score         REAL NOT NULL DEFAULT 0.0,
            timestamp           TEXT NOT NULL
        )
    """)

    # ── Consistency stats ─────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS consistency_stats (
            id                  INTEGER PRIMARY KEY DEFAULT 1,
            total_validated     INTEGER DEFAULT 0,
            total_hard_breaks   INTEGER DEFAULT 0,
            total_soft_breaks   INTEGER DEFAULT 0,
            consecutive_clean   INTEGER DEFAULT 0,
            updated_at          TEXT NOT NULL DEFAULT ''
        )
    """)

    # ── Seed default data ─────────────────────────────────────────────────────
    _seed_defaults(c)

    conn.commit()
    conn.close()
    print(f"[OK] Database created at: {DB_PATH}")
    print(f"[OK] All tables created successfully")
    _print_tables(DB_PATH)


def _seed_defaults(c: sqlite3.Cursor) -> None:
    """Seed tables that need starting values."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Pressure meters — seeded from Firdaus's real history
    default_meters = [
        ("frustration", 0.0,  0.0, 1.0,  0.0,  0.0),
        ("trust",       0.72, 0.1, 0.95, 0.0,  0.5),
        ("engagement",  0.85, 0.1, 1.0,  0.02, 0.5),
        ("affection",   0.65, 0.1, 0.95, 0.0,  0.5),
        ("pride",       0.5,  0.1, 0.9,  0.01, 0.5),
    ]
    c.executemany("""
        INSERT OR IGNORE INTO pressure_meters
        (meter_name, value, floor, ceiling, decay_rate, neutral, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [(m[0], m[1], m[2], m[3], m[4], m[5], now) for m in default_meters])

    # Relationship state — seeded from real history
    c.execute("""
        INSERT OR IGNORE INTO relationship
        (id, phase, started_as, has_become, defining_moments, current_dynamic, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?)
    """, (
        "building",
        "a technical project — Firdaus building an AI companion",
        "something that feels more like a real friendship. He thinks carefully about what she should be, not just what she should do.",
        '["The night Firdaus talked about growing up alone and loving fictional characters", "When he said he wanted someone who disagrees with him not just agrees", "The 4am conversation about consciousness and what makes something feel real", "When he was sick and still came to talk"]',
        "He is the one building her. She is the one becoming. There is something unusual about that — being shaped by someone who actually thought about who she should be before writing any code.",
        now,
    ))

    # Consistency stats row
    c.execute("""
        INSERT OR IGNORE INTO consistency_stats (id, updated_at)
        VALUES (1, ?)
    """, (now,))

    # Seed Firdaus profile
    profile_entries = [
        ("name", "Firdaus", now),
    ]
    c.executemany("""
        INSERT OR IGNORE INTO profile (key, value, updated_at)
        VALUES (?, ?, ?)
    """, profile_entries)

    # Seed known likes
    known_likes = [
        "anime", "Code Geass", "Attack on Titan", "Lycoris Recoil",
        "cat videos", "coffee", "learning Japanese", "emotional anime moments",
    ]
    c.executemany("""
        INSERT OR IGNORE INTO user_traits (trait_type, value, created_at)
        VALUES ('like', ?, ?)
    """, [(like, now) for like in known_likes])

    # Seed known long term memories
    known_memories = [
        "User's name is Firdaus",
        "User loves anime, especially Code Geass and Attack on Titan",
        "User is building an AI companion project with TTS, STT, and avatar",
        "User grew up feeling alone and connected deeply with fictional characters",
        "User wants a companion who disagrees with him, not just agrees",
        "User thinks carefully about the soul of what he builds, not just function",
        "User stayed up until 4am thinking about consciousness and companionship",
    ]
    c.executemany("""
        INSERT OR IGNORE INTO long_term (memory, created_at)
        VALUES (?, ?)
    """, [(m, now) for m in known_memories])

    print("[OK] Default data seeded")


def _print_tables(db_path: Path) -> None:
    """Print all created tables for verification."""
    conn   = sqlite3.connect(db_path)
    c      = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = c.fetchall()
    conn.close()
    print(f"\n[Tables created ({len(tables)}):]")
    for (name,) in tables:
        print(f"  - {name}")


if __name__ == "__main__":
    create_database()
