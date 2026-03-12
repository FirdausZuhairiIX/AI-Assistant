"""
Chisato Memory Store — memorynew.py (SQLite Final)

All JSON references removed.
All reads/writes go through chisato.db via db.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from memory.db import get_db


class MemoryStore:
    def __init__(self, path=None, max_short_term: int = 20) -> None:
        # path kept for backward compatibility — no longer used
        self.max_short_term = max_short_term
        self.db = get_db()
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Pull current state from DB into self.data cache."""
        self.data: Dict[str, Any] = {
            "profile":    self.db.get_profile(),
            "long_term":  self.db.get_long_term(n=100),
            "short_term": self.db.get_short_term(n=self.max_short_term),
        }

    def save(self) -> None:
        """No-op — SQLite writes on every operation automatically."""
        pass

    def snapshot(self) -> Dict[str, Any]:
        self._refresh_cache()
        return self.data

    # ── Short term memory ─────────────────────────────────────────────────────
    def record_turn(self, user: str, assistant: str) -> None:
        """Record a conversation turn — filters system commands and empty input."""
        if not user or not user.strip():
            return

        user_lower = user.strip().lower()
        if any([
            user.strip().startswith('"C:\\'),
            user.strip().startswith('C:\\'),
            user.strip().startswith('"c:\\'),
            user.strip().startswith('c:\\'),
            'python.exe' in user_lower,
            'main.py' in user_lower,
            user.strip().startswith('/'),
            user.strip().startswith('\\'),
        ]):
            return

        self.db.add_short_term(user.strip(), assistant.strip())
        self.db.trim_short_term(self.max_short_term)
        self._refresh_cache()

    def add_short_term(self, entry: Any) -> None:
        """Legacy support — entry is dict with user/assistant keys."""
        if isinstance(entry, dict):
            user_msg    = entry.get("user", "")
            chisato_msg = entry.get("assistant", "")
            if user_msg and chisato_msg:
                self.db.add_short_term(user_msg, chisato_msg)
                self.db.trim_short_term(self.max_short_term)
                self._refresh_cache()

    # ── Long term memory ──────────────────────────────────────────────────────
    def add_long_term(self, summary: str) -> None:
        """Add to long-term memory, avoiding duplicates."""
        summary_clean = summary.strip()
        if not summary_clean:
            return
        self.db.add_long_term(summary_clean)
        self._refresh_cache()

    def promote_short_to_long_term(self, llm=None, n: int = 5) -> None:
        """
        Promote important recent short-term turns to long-term memory.
        Uses LLM to decide what's worth keeping.
        """
        # Always fetch fresh from DB — not stale cache
        recent_entries = self.db.get_short_term(n=n)
        if not recent_entries:
            return

        # DB returns user_msg / chisato_msg — correct column names
        text_block = "\n".join([
            f"User: {e['user_msg']}\nChisato: {e['chisato_msg']}"
            for e in recent_entries
        ])

        if llm:
            prompt = f"""Analyze this recent conversation and extract ONLY truly important facts worth remembering long-term about the user.

Recent conversation:
{text_block}

Rules:
- Only extract facts about the USER (not about Chisato)
- Only include things useful to remember in future conversations
- Each fact should be ONE short sentence
- Examples of good facts: "User's name is Firdaus", "User loves anime"
- Examples of bad facts: Generic statements, Chisato's own responses
- Return ONLY the facts, one per line
- If nothing important, return "NONE"

Important facts to remember:"""

            try:
                response = llm.chat([{"role": "user", "content": prompt}])
                result   = response.text.strip()

                if result and result.upper() != "NONE":
                    for line in result.split("\n"):
                        clean = line.strip().lstrip("-•*").strip()
                        if clean and len(clean) > 5:
                            self.add_long_term(clean)
            except Exception as e:
                print(f"[Memory] Error promoting to long-term: {e}")

    # ── Profile ───────────────────────────────────────────────────────────────
    def update_profile(
        self,
        name: Optional[str]     = None,
        likes: Iterable[str]    = None,
        dislikes: Iterable[str] = None,
        goals: Iterable[str]    = None,
    ) -> None:
        if name:
            self.db.save_profile_name(name)
            self.add_long_term(f"User's name is {name}")
            print(f"[Memory] Saved name: {name}")

        if likes:
            for v in likes:
                if str(v).strip():
                    self.db.add_trait("like", str(v).strip())

        if dislikes:
            for v in dislikes:
                if str(v).strip():
                    self.db.add_trait("dislike", str(v).strip())

        if goals:
            for v in goals:
                if str(v).strip():
                    self.db.add_trait("goal", str(v).strip())

        self._refresh_cache()

    # ── Memory for prompt ─────────────────────────────────────────────────────
    def get_memory_for_prompt(self, n: int = 5) -> Dict:
        """Returns memory dict for prompt injection."""
        return self.db.get_memory_for_prompt(n=n)

    # ── User info detection ───────────────────────────────────────────────────
    def detect_and_save_user_info(
        self, user_input: str, assistant_response: str, llm=None
    ) -> None:
        if not user_input or not user_input.strip():
            return
        if self._is_system_command(user_input):
            return

        # Simple name detection first
        name = self._detect_name_simple(user_input)
        if name and not self.db.get_profile().get("name"):
            self.update_profile(name=name)
            return

        # LLM-based detection
        if llm:
            self._detect_info_with_llm(user_input, assistant_response, llm)

    def _is_system_command(self, text: str) -> bool:
        text_lower = text.strip().lower()
        return any([
            text.strip().startswith('"C:\\'),
            text.strip().startswith('C:\\'),
            'python.exe' in text_lower,
            'main.py' in text_lower,
            text.strip().startswith('/'),
            text.strip().startswith('\\'),
        ])

    def _detect_name_simple(self, user_input: str) -> Optional[str]:
        patterns = [
            r"\bmy name is (\w+)\b",
            r"\bi am (\w+)\b",
            r"\bi'm (\w+)\b",
            r"\bcall me (\w+)\b",
            r"\byou can call me (\w+)\b",
            r"\bthis is (\w+)\b",
            r"\bname'?s (\w+)\b",
        ]
        common_words = {'the', 'this', 'that', 'your', 'my', 'his', 'her'}
        for pat in patterns:
            match = re.search(pat, user_input, re.IGNORECASE)
            if match:
                name = match.group(1).capitalize()
                if name.lower() not in common_words:
                    return name
        return None

    def _detect_info_with_llm(
        self, user_input: str, assistant_response: str, llm
    ) -> None:
        try:
            prompt = f"""Analyze this conversation turn and extract personal information about the user.

User said: "{user_input}"
Assistant replied: "{assistant_response}"

Extract and format as JSON:
{{
  "name": "name if mentioned, else null",
  "likes": ["things they like"],
  "dislikes": ["things they dislike"],
  "goals": ["their goals or plans"]
}}

Only include information explicitly stated by the user.
Return ONLY the JSON, nothing else."""

            response    = llm.chat([{"role": "user", "content": prompt}])
            result_text = response.text.strip()

            # Parse JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                info = json.loads(json_match.group())

                if info.get("name") and not self.db.get_profile().get("name"):
                    self.update_profile(name=info["name"])
                if info.get("likes"):
                    self.update_profile(likes=info["likes"])
                if info.get("dislikes"):
                    self.update_profile(dislikes=info["dislikes"])
                if info.get("goals"):
                    self.update_profile(goals=info["goals"])

        except Exception as e:
            print(f"[Memory] Info detection error: {e}")

    # ── Legacy ────────────────────────────────────────────────────────────────
    def extract_new_memory(self, text: str) -> str:
        """Fallback memory extraction if LLM unavailable."""
        sentences = text.strip().split(".")
        candidate = ".".join(sentences[:2]).strip()
        return candidate if candidate else text.strip()[:280]

    def detect_user_name(self, user_input: str, llm=None) -> Optional[str]:
        """Deprecated — use detect_and_save_user_info instead."""
        return self._detect_name_simple(user_input)
