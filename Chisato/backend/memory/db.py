"""
Chisato Shared Database Layer — db.py

Single connection point for all pillar files.
Every pillar imports this instead of managing its own file I/O.

Usage in any pillar:
    from memory.db import ChisatoDB
    db = ChisatoDB()

    # Then use the methods directly
    db.get_pressure_meters()
    db.save_episode(...)
    db.get_long_term_memories()

One connection. One place to fix if something breaks.
Pillars focus on logic — this handles all database work.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DB_PATH = Path(__file__).resolve().parent / "chisato.db"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChisatoDB:
    """
    Shared database layer for all Chisato pillars.
    One instance, one connection, all pillars share it.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}\n"
                f"Run setup_db.py first."
            )
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,   # allow access from multiple pillars
        )
        self.conn.row_factory = sqlite3.Row  # rows behave like dicts
        self.conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent writes
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self):
        """Context manager for safe atomic writes."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ═════════════════════════════════════════════════════════════════════════
    # PROFILE
    # ═════════════════════════════════════════════════════════════════════════

    def get_profile(self) -> Dict[str, Any]:
        """Returns full profile as dict with name, likes, dislikes, goals."""
        c = self.conn.cursor()

        # Name
        c.execute("SELECT value FROM profile WHERE key = 'name'")
        row  = c.fetchone()
        name = row["value"] if row else ""

        # Traits
        c.execute("SELECT trait_type, value FROM user_traits ORDER BY created_at")
        likes    = []
        dislikes = []
        goals    = []
        for row in c.fetchall():
            if row["trait_type"] == "like":
                likes.append(row["value"])
            elif row["trait_type"] == "dislike":
                dislikes.append(row["value"])
            elif row["trait_type"] == "goal":
                goals.append(row["value"])

        return {"name": name, "likes": likes, "dislikes": dislikes, "goals": goals}

    def save_profile_name(self, name: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR REPLACE INTO profile (key, value, updated_at)
                VALUES ('name', ?, ?)
            """, (name, now()))

    def add_trait(self, trait_type: str, value: str) -> None:
        """trait_type: 'like' | 'dislike' | 'goal'"""
        with self.transaction():
            self.conn.execute("""
                INSERT OR IGNORE INTO user_traits (trait_type, value, created_at)
                VALUES (?, ?, ?)
            """, (trait_type, value, now()))

    # ═════════════════════════════════════════════════════════════════════════
    # SHORT TERM MEMORY
    # ═════════════════════════════════════════════════════════════════════════

    def add_short_term(self, user_msg: str, chisato_msg: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO short_term (user_msg, chisato_msg, timestamp)
                VALUES (?, ?, ?)
            """, (user_msg, chisato_msg, now()))

    def get_short_term(self, n: int = 10) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT user_msg, chisato_msg, timestamp
            FROM short_term
            ORDER BY timestamp DESC
            LIMIT ?
        """, (n,))
        rows = c.fetchall()
        # Return in chronological order (oldest first)
        return [dict(r) for r in reversed(rows)]

    def trim_short_term(self, max_entries: int = 20) -> None:
        """Keep only the most recent N entries."""
        with self.transaction():
            self.conn.execute("""
                DELETE FROM short_term
                WHERE id NOT IN (
                    SELECT id FROM short_term
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
            """, (max_entries,))

    # ═════════════════════════════════════════════════════════════════════════
    # LONG TERM MEMORY
    # ═════════════════════════════════════════════════════════════════════════

    def add_long_term(self, memory: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR IGNORE INTO long_term (memory, created_at)
                VALUES (?, ?)
            """, (memory.strip(), now()))

    def get_long_term(self, n: int = 8) -> List[str]:
        c = self.conn.cursor()
        c.execute("""
            SELECT memory FROM long_term
            ORDER BY created_at DESC
            LIMIT ?
        """, (n,))
        return [r["memory"] for r in c.fetchall()]

    def get_memory_for_prompt(self, n: int = 5) -> Dict:
        """Returns combined memory dict for prompt injection."""
        return {
            "profile":    self.get_profile(),
            "long_term":  self.get_long_term(n),
            "short_term": self.get_short_term(n),
        }

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 1 — BELIEFS
    # ═════════════════════════════════════════════════════════════════════════

    def get_beliefs_tier2(self) -> Dict[str, Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM beliefs_tier2")
        result = {}
        for row in c.fetchall():
            result[row["opinion_key"]] = {
                "summary":        row["summary"],
                "confidence":     row["confidence"],
                "evidence":       json.loads(row["evidence"]),
                "open_questions": json.loads(row["open_questions"]),
                "updated_at":     row["updated_at"],
            }
        return result

    def save_belief_tier2(self, key: str, summary: str, confidence: float,
                          evidence: List, open_questions: List) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR REPLACE INTO beliefs_tier2
                (opinion_key, summary, confidence, evidence, open_questions, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (key, summary, confidence,
                  json.dumps(evidence), json.dumps(open_questions), now()))

    def get_beliefs_tier3(self) -> Dict[str, Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM beliefs_tier3")
        result = {}
        for row in c.fetchall():
            result[row["topic"]] = {
                "position":        row["position"],
                "strength":        row["strength"],
                "formed_from":     row["formed_from"],
                "times_challenged": row["times_challenged"],
                "times_held":      row["times_held"],
                "times_updated":   row["times_updated"],
                "formed_at":       row["formed_at"],
            }
        return result

    def save_belief_tier3(self, topic: str, position: str, strength: float,
                          formed_from: str, times_challenged: int,
                          times_held: int, times_updated: int,
                          formed_at: Optional[str] = None) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR REPLACE INTO beliefs_tier3
                (topic, position, strength, formed_from,
                 times_challenged, times_held, times_updated, formed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (topic, position, strength, formed_from,
                  times_challenged, times_held, times_updated,
                  formed_at or now()))

    def delete_belief_tier3(self, topic: str) -> None:
        with self.transaction():
            self.conn.execute(
                "DELETE FROM beliefs_tier3 WHERE topic = ?", (topic,))

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 2 — PRESSURE
    # ═════════════════════════════════════════════════════════════════════════

    def get_pressure_meters(self) -> Dict[str, Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM pressure_meters")
        result = {}
        for row in c.fetchall():
            result[row["meter_name"]] = {
                "value":      row["value"],
                "floor":      row["floor"],
                "ceiling":    row["ceiling"],
                "decay_rate": row["decay_rate"],
                "neutral":    row["neutral"],
                "updated_at": row["updated_at"],
            }
        return result

    def save_pressure_meter(self, name: str, value: float) -> None:
        with self.transaction():
            self.conn.execute("""
                UPDATE pressure_meters
                SET value = ?, updated_at = ?
                WHERE meter_name = ?
            """, (value, now(), name))

    def save_all_pressure_meters(self, meters: Dict[str, float]) -> None:
        """Save multiple meters in one transaction."""
        with self.transaction():
            for name, value in meters.items():
                self.conn.execute("""
                    UPDATE pressure_meters
                    SET value = ?, updated_at = ?
                    WHERE meter_name = ?
                """, (value, now(), name))

    def add_frustration_event(self, cause: str, severity: float) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO frustration_events (cause, severity, resolved, timestamp)
                VALUES (?, ?, 0, ?)
            """, (cause, severity, now()))

    def get_unresolved_frustration_events(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM frustration_events
            WHERE resolved = 0
            ORDER BY timestamp DESC
        """)
        return [dict(r) for r in c.fetchall()]

    def resolve_frustration_event(self, event_id: int) -> None:
        with self.transaction():
            self.conn.execute("""
                UPDATE frustration_events SET resolved = 1 WHERE id = ?
            """, (event_id,))

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 3 — CONSEQUENCES
    # ═════════════════════════════════════════════════════════════════════════

    def add_dismissed_warning(self, topic: str, warning: str) -> int:
        """Returns the new warning's id."""
        with self.transaction():
            c = self.conn.execute("""
                INSERT INTO dismissed_warnings
                (topic, warning, dismissed_at, resolved)
                VALUES (?, ?, ?, 0)
            """, (topic, warning, now()))
            return c.lastrowid

    def get_unresolved_warnings(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM dismissed_warnings
            WHERE resolved = 0
            ORDER BY dismissed_at DESC
        """)
        return [dict(r) for r in c.fetchall()]

    def update_warning_outcome(self, warning_id: int,
                                was_right: bool, outcome_note: str = "") -> None:
        with self.transaction():
            self.conn.execute("""
                UPDATE dismissed_warnings
                SET was_right = ?, outcome_note = ?, resolved = 1
                WHERE id = ?
            """, (1 if was_right else 0, outcome_note, warning_id))

    def increment_warning_surfaced(self, warning_id: int) -> None:
        with self.transaction():
            self.conn.execute("""
                UPDATE dismissed_warnings
                SET surfaced_count = surfaced_count + 1
                WHERE id = ?
            """, (warning_id,))

    def get_behavior_patterns(self) -> Dict[str, Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM behavior_patterns")
        result = {}
        for row in c.fetchall():
            result[row["pattern_key"]] = {
                "behavior":       row["behavior"],
                "occurrences":    row["occurrences"],
                "first_seen":     row["first_seen"],
                "last_seen":      row["last_seen"],
                "chisato_stance": row["chisato_stance"],
                "is_positive":    bool(row["is_positive"]),
            }
        return result

    def upsert_behavior_pattern(self, key: str, behavior: str,
                                 is_positive: bool = False,
                                 chisato_stance: str = "") -> None:
        with self.transaction():
            existing = self.conn.execute("""
                SELECT occurrences FROM behavior_patterns WHERE pattern_key = ?
            """, (key,)).fetchone()

            if existing:
                self.conn.execute("""
                    UPDATE behavior_patterns
                    SET occurrences = occurrences + 1,
                        last_seen = ?,
                        chisato_stance = CASE
                            WHEN ? != '' THEN ? ELSE chisato_stance END
                    WHERE pattern_key = ?
                """, (now(), chisato_stance, chisato_stance, key))
            else:
                self.conn.execute("""
                    INSERT INTO behavior_patterns
                    (pattern_key, behavior, occurrences,
                     first_seen, last_seen, chisato_stance, is_positive)
                    VALUES (?, ?, 1, ?, ?, ?, ?)
                """, (key, behavior, now(), now(),
                      chisato_stance, 1 if is_positive else 0))

    def add_growth_moment(self, topic: str, what_changed: str,
                          original_stance: str, new_stance: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO growth_moments
                (topic, what_changed, original_stance, new_stance,
                 noticed_at, acknowledged)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (topic, what_changed, original_stance, new_stance, now()))

    def get_growth_moments(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM growth_moments ORDER BY noticed_at DESC")
        return [dict(r) for r in c.fetchall()]

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 4 — MEMORY ARCHITECTURE
    # ═════════════════════════════════════════════════════════════════════════

    def add_episode(self, title: str, what_happened: str,
                    why_it_mattered: str, emotional_tone: str,
                    category: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO episodes
                (title, what_happened, why_it_mattered,
                 emotional_tone, category, timestamp,
                 referenced_count, still_relevant)
                VALUES (?, ?, ?, ?, ?, ?, 0, 1)
            """, (title, what_happened, why_it_mattered,
                  emotional_tone, category, now()))

    def get_episodes(self, limit: int = 5,
                     category: Optional[str] = None) -> List[Dict]:
        c    = self.conn.cursor()
        if category:
            c.execute("""
                SELECT * FROM episodes
                WHERE still_relevant = 1 AND category = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (category, limit))
        else:
            c.execute("""
                SELECT * FROM episodes
                WHERE still_relevant = 1
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_relevant_episodes(self, user_input: str,
                               limit: int = 3) -> List[Dict]:
        """
        Basic keyword relevance — finds episodes where the title
        or what_happened contains words from user input.
        Good enough without a vector DB.
        """
        words = [w.lower() for w in user_input.split() if len(w) > 4]
        if not words:
            return self.get_episodes(limit)

        c = self.conn.cursor()
        results = []
        seen_ids = set()

        for word in words[:5]:  # check top 5 meaningful words
            c.execute("""
                SELECT * FROM episodes
                WHERE still_relevant = 1
                AND (LOWER(title) LIKE ? OR LOWER(what_happened) LIKE ?)
                ORDER BY referenced_count DESC, timestamp DESC
                LIMIT ?
            """, (f"%{word}%", f"%{word}%", limit))
            for row in c.fetchall():
                if row["id"] not in seen_ids:
                    results.append(dict(row))
                    seen_ids.add(row["id"])
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break

        # Fall back to recent if no keyword match
        if not results:
            return self.get_episodes(limit)

        return results

    def increment_episode_referenced(self, episode_id: int) -> None:
        with self.transaction():
            self.conn.execute("""
                UPDATE episodes
                SET referenced_count = referenced_count + 1
                WHERE id = ?
            """, (episode_id,))

    def get_relationship(self) -> Dict:
        c = self.conn.cursor()
        c.execute("SELECT * FROM relationship WHERE id = 1")
        row = c.fetchone()
        if not row:
            return {}
        data = dict(row)
        data["defining_moments"] = json.loads(data.get("defining_moments", "[]"))
        return data

    def save_relationship(self, phase: str, started_as: str,
                          has_become: str, defining_moments: List,
                          current_dynamic: str) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR REPLACE INTO relationship
                (id, phase, started_as, has_become,
                 defining_moments, current_dynamic, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (phase, started_as, has_become,
                  json.dumps(defining_moments), current_dynamic, now()))

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 5 — INITIATIVE
    # ═════════════════════════════════════════════════════════════════════════

    def add_initiative_record(self, initiative_type: str,
                               content: str, turn_taken: int) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO initiative_history
                (initiative_type, content, turn_taken, timestamp)
                VALUES (?, ?, ?, ?)
            """, (initiative_type, content, turn_taken, now()))

    def get_recent_initiatives(self, n: int = 10) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM initiative_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (n,))
        return [dict(r) for r in c.fetchall()]

    def get_last_initiative_turn(self) -> int:
        c = self.conn.cursor()
        c.execute("""
            SELECT turn_taken FROM initiative_history
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = c.fetchone()
        return row["turn_taken"] if row else 0

    # ═════════════════════════════════════════════════════════════════════════
    # PILLAR 6 — CONSISTENCY
    # ═════════════════════════════════════════════════════════════════════════

    def add_consistency_log(self, response_snippet: str,
                             drift_signals: List, drift_score: float) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT INTO consistency_log
                (response_snippet, drift_signals, drift_score, timestamp)
                VALUES (?, ?, ?, ?)
            """, (response_snippet[:200],
                  json.dumps(drift_signals), drift_score, now()))

    def get_recent_consistency_logs(self, n: int = 6) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM consistency_log
            ORDER BY timestamp DESC LIMIT ?
        """, (n,))
        rows = c.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["drift_signals"] = json.loads(d["drift_signals"])
            result.append(d)
        return result

    def get_consistency_stats(self) -> Dict:
        c = self.conn.cursor()
        c.execute("SELECT * FROM consistency_stats WHERE id = 1")
        row = c.fetchone()
        return dict(row) if row else {}

    def save_consistency_stats(self, total_validated: int,
                                total_hard_breaks: int,
                                total_soft_breaks: int,
                                consecutive_clean: int) -> None:
        with self.transaction():
            self.conn.execute("""
                INSERT OR REPLACE INTO consistency_stats
                (id, total_validated, total_hard_breaks,
                 total_soft_breaks, consecutive_clean, updated_at)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (total_validated, total_hard_breaks,
                  total_soft_breaks, consecutive_clean, now()))

    # ═════════════════════════════════════════════════════════════════════════
    # UTILITY
    # ═════════════════════════════════════════════════════════════════════════

    def table_counts(self) -> Dict[str, int]:
        """Returns row count for every table. Useful for debugging."""
        c = self.conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r["name"] for r in c.fetchall()]
        counts = {}
        for table in tables:
            c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            counts[table] = c.fetchone()["cnt"]
        return counts

    def snapshot(self) -> Dict:
        """Full readable snapshot for debug command in main.py."""
        return {
            "profile":       self.get_profile(),
            "long_term":     self.get_long_term(10),
            "short_term":    self.get_short_term(5),
            "table_counts":  self.table_counts(),
        }


# ── Singleton helper ──────────────────────────────────────────────────────────
# All pillars can import and call get_db() to get the shared instance.
# Only one connection is created for the entire session.

_db_instance: Optional[ChisatoDB] = None


def get_db(db_path: Path = DB_PATH) -> ChisatoDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = ChisatoDB(db_path)
    return _db_instance
