"""
Lightweight LLM client wrapper for Ollama chat endpoint.

The client posts chat-formatted messages and returns a structured response,
including a minimal tool-call detector for future voice/control hooks.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


@dataclass
class LLMResponse:
    text: str
    tool_calls: List[Dict[str, Any]]
    raw: Dict[str, Any] | None = None


def detect_tool_calls(text: str) -> List[Dict[str, Any]]:
    """
    Heuristic tool-call detector.
    Looks for JSON snippets inside a fenced block, e.g. ```json { "tool": "..."} ```.
    This keeps Unity/audio integrations pluggable without forcing a schema yet.
    """
    pattern = re.compile(r"```json(.*?)```", re.DOTALL)
    tool_calls: List[Dict[str, Any]] = []
    for match in pattern.findall(text):
        try:
            parsed = json.loads(match.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            tool_calls.append(parsed)
        elif isinstance(parsed, list):
            tool_calls.extend([item for item in parsed if isinstance(item, dict)])
    return tool_calls


class LLMClient:
    def __init__(
        self,
        model_name: str | None = None,
        api_url: str | None = None,
        timeout: int = 300,
    ) -> None:
        # Default to the locally available Qwen2.5 7B instruct quant; allow env overrides
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL") or "qwen2.5:14b-instruct-q4_K_M"
        self.api_url = api_url or os.environ.get("OLLAMA_API_URL") or "http://localhost:11434/api/chat"
        self.timeout = timeout

    def _sanitize_content(self, content: str) -> str:
        """
        Normalize common escaped newlines from some model outputs.
        """
        if not isinstance(content, str):
            return ""
        cleaned = content.replace("\\n", "\n")
        return cleaned.strip()

    def chat(
        self,
        messages: Sequence[Dict[str, str]],
        temperature: float = 0.7,
    ) -> LLMResponse:
        payload = {
            "model": self.model_name,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            import requests
        except ImportError:
            return self._offline_stub(messages, "requests not installed")

        try:
            response = requests.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            return self._offline_stub(messages, str(exc))

        content = self._sanitize_content(self._extract_content(data))
        tool_calls = detect_tool_calls(content)
        return LLMResponse(text=content, tool_calls=tool_calls, raw=data)

    def _extract_content(self, data: Dict[str, Any]) -> str:
        # Ollama returns {"message": {"content": "...", ...}}
        message = data.get("message") or {}
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        if "content" in data and isinstance(data["content"], str):
            return data["content"]
        return ""

    def _offline_stub(
        self,
        messages: Sequence[Dict[str, str]],
        reason: str,
    ) -> LLMResponse:
        fallback = (
            f"(offline stub: {reason}) Could not reach Ollama at {self.api_url} using model '{self.model_name}'."
        )
        return LLMResponse(text=fallback, tool_calls=[], raw={"error": reason})
