"""
Persistence and lightweight memory utilities for Chisato.

The store keeps a JSON document on disk and offers helpers for recording
turns, promoting summaries to long-term memory, updating the profile,
and retrieving memory intelligently to allow dynamic conversation topics.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import re

DEFAULT_MEMORY: Dict[str, Any] = {
    "profile": {"name": "", "likes": [], "dislikes": [], "goals": []},
    "long_term": [],
    "short_term": [],
}

class MemoryStore:
    def __init__(self, path: Path, max_short_term: int = 20) -> None:
        self.path = Path(path)
        self.max_short_term = max_short_term
        self.data: Dict[str, Any] = {}
        self._ensure_file()

    # ---------------- File Operations ---------------- #
    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.data = json.loads(json.dumps(DEFAULT_MEMORY))
            self.save()
        else:
            self.load()

    def load(self) -> Dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            self.data = json.load(handle)
        return self.data

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2)

    def snapshot(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self.data))

    # ---------------- Short-Term Memory ---------------- #
    def record_turn(self, user: str, assistant: str) -> None:
        """Record a conversation turn - filters out system messages and commands."""
        # Skip empty messages
        if not user or not user.strip():
            return
            
        # Filter out system commands and file paths
        user_lower = user.strip().lower()
        
        # Skip if it looks like a file path or system command
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
        
        entry = {
            "user": user,
            "assistant": assistant,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.add_short_term(entry)

    def add_short_term(self, entry: Any) -> None:
        self.data.setdefault("short_term", []).append(entry)
        if len(self.data["short_term"]) > self.max_short_term:
            overflow = len(self.data["short_term"]) - self.max_short_term
            self.data["short_term"] = self.data["short_term"][overflow:]
        self.save()

    # ---------------- Long-Term Memory ---------------- #
    def add_long_term(self, summary: str) -> None:
        """Add a memory to long-term storage, avoiding duplicates."""
        self.data.setdefault("long_term", [])
        # Normalize for comparison
        summary_clean = summary.strip()
        if not summary_clean:
            return
        # Check for duplicates (case-insensitive)
        existing_lower = [m.lower() for m in self.data["long_term"]]
        if summary_clean.lower() not in existing_lower:
            self.data["long_term"].append(summary_clean)
            self.save()

    def promote_short_to_long_term(self, llm=None, n: int = 5) -> None:
        """
        Promote the most important recent short-term conversations to long-term memory.
        Uses LLM to intelligently decide what's important to remember.
        """
        recent_entries = self.data.get("short_term", [])[-n:]
        if not recent_entries:
            return

        text_block = "\n".join([
            f"User: {e['user']}\nChisato: {e['assistant']}" 
            for e in recent_entries
        ])

        if llm:
            prompt = f"""Analyze this recent conversation and extract ONLY truly important facts worth remembering long-term about the user.

Recent conversation:
{text_block}

Rules:
- Only extract facts about the USER (not about you/Chisato)
- Only include things that would be useful to remember in future conversations
- Each fact should be ONE short sentence
- Examples of good facts: "User's name is John", "User loves anime", "User is learning Python"
- Examples of bad facts: Generic statements, your own responses, temporary context
- Return ONLY the facts, one per line
- If nothing important to remember, return "NONE"

Important facts to remember:"""

            try:
                response = llm.chat([{"role": "user", "content": prompt}])
                result = response.text.strip()
                
                if result and result.upper() != "NONE":
                    lines = result.split("\n")
                    for line in lines:
                        clean = line.strip().lstrip("-•*").strip()
                        if clean and len(clean) > 5:  # Ignore very short lines
                            self.add_long_term(clean)
            except Exception as e:
                print(f"[Memory] Error promoting to long-term: {e}")
                pass

    # ---------------- Profile ---------------- #
    def update_profile(
        self,
        name: str | None = None,
        likes: Iterable[str] | None = None,
        dislikes: Iterable[str] | None = None,
        goals: Iterable[str] | None = None,
    ) -> None:
        """Update user profile with new information."""
        profile = self.data.setdefault("profile", {})
        
        if name:
            profile["name"] = name
            self.add_long_term(f"User's name is {name}")
            print(f"[Memory] Saved name: {name}")

        def _extend(key: str, values: Iterable[str] | None) -> None:
            if not values:
                return
            profile.setdefault(key, [])
            existing = {str(v).lower() for v in profile[key]}
            for v in values:
                v_str = str(v).strip()
                if v_str and v_str.lower() not in existing:
                    profile[key].append(v_str)
                    existing.add(v_str.lower())

        _extend("likes", likes)
        _extend("dislikes", dislikes)
        _extend("goals", goals)
        self.save()

    # ---------------- Memory Extraction ---------------- #
    def extract_new_memory(self, text: str) -> str:
        """Fallback memory extraction if LLM is unavailable."""
        sentences = text.strip().split(".")
        candidate = ".".join(sentences[:2]).strip()
        return candidate if candidate else text.strip()[:280]

    # ---------------- Helpers ---------------- #
    def get_memory_for_prompt(self, n: int = 5) -> dict:
        """Get recent memory formatted for prompt context."""
        short_mem = self.data.get("short_term", [])[-n:]
        long_mem = self.data.get("long_term", [])
        profile = self.data.get("profile", {})
        
        return {
            "profile": profile,
            "long_term": long_mem,
            "recent_conversation": short_mem
        }

    # ---------------- Intelligent Name Detection ---------------- #
    def detect_and_save_user_info(self, user_input: str, assistant_response: str, llm=None) -> None:
        """
        Intelligently detect if user is sharing personal information (name, likes, etc.)
        and save it appropriately.
        """
        if not user_input or not user_input.strip():
            return

        # Skip if it's a system command
        if self._is_system_command(user_input):
            return

        # Try simple name detection first
        name = self._detect_name_simple(user_input)
        if name and not self.data.get("profile", {}).get("name"):
            self.update_profile(name=name)
            return

        # Use LLM for more intelligent detection if available
        if llm:
            self._detect_info_with_llm(user_input, assistant_response, llm)

    def _is_system_command(self, text: str) -> bool:
        """Check if text is a system command or file path."""
        text_lower = text.strip().lower()
        return any([
            text.strip().startswith('"C:\\'),
            text.strip().startswith('C:\\'),
            'python.exe' in text_lower,
            'main.py' in text_lower,
            text.strip().startswith('/'),
            text.strip().startswith('\\'),
        ])

    def _detect_name_simple(self, user_input: str) -> str | None:
        """Simple regex-based name detection."""
        patterns = [
            r"\bmy name is (\w+)\b",
            r"\bi am (\w+)\b",
            r"\bi'm (\w+)\b",
            r"\bcall me (\w+)\b",
            r"\byou can call me (\w+)\b",
            r"\bthis is (\w+)\b",
            r"\bname'?s (\w+)\b",
        ]
        
        for pat in patterns:
            match = re.search(pat, user_input, re.IGNORECASE)
            if match:
                name = match.group(1).capitalize()
                # Filter out common words that aren't names
                common_words = {'the', 'this', 'that', 'your', 'my', 'his', 'her'}
                if name.lower() not in common_words:
                    return name
        
        return None

    def _detect_info_with_llm(self, user_input: str, assistant_response: str, llm) -> None:
        """Use LLM to detect personal information in conversation."""
        try:
            prompt = f"""Analyze this conversation turn and extract any personal information about the user.

User said: "{user_input}"
Assistant replied: "{assistant_response}"

Extract and format as JSON:
{{
  "name": "name if mentioned, else null",
  "likes": ["things they like"],
  "dislikes": ["things they dislike"],
  "goals": ["their goals or plans"]
}}

Only include information explicitly stated by the user. If nothing found, return empty arrays/null.
Return ONLY the JSON, no other text."""

            response = llm.chat([{"role": "user", "content": prompt}])
            result_text = response.text.strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                info = json.loads(json_match.group())
                
                # Update profile with detected information
                if info.get("name") and not self.data.get("profile", {}).get("name"):
                    self.update_profile(name=info["name"])
                
                if info.get("likes"):
                    self.update_profile(likes=info["likes"])
                
                if info.get("dislikes"):
                    self.update_profile(dislikes=info["dislikes"])
                
                if info.get("goals"):
                    self.update_profile(goals=info["goals"])
                    
        except Exception as e:
            print(f"[Memory] Info detection error: {e}")
            pass

    # Deprecated - keeping for backward compatibility
    def detect_user_name(self, user_input: str, llm=None) -> str | None:
        """Deprecated: Use detect_and_save_user_info instead."""
        return self._detect_name_simple(user_input)