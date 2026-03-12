"""
Text-to-speech hooks targeting SoVITS (or a compatible TTS pipeline).

The functions here are thin wrappers: they call an HTTP endpoint to synthesize
audio, save the WAV to disk, and provide a hook for Unity interop. Replace the
stubbed HTTP call and Unity sender with your actual implementations.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional


def synthesize_with_sovits(
    text: str,
    speaker: str = "chisato",
    api_url: str = "http://localhost:5000/tts",
    output_path: Path | None = None,
) -> Optional[Path]:
    """
    Send text to a SoVITS server and write the WAV result to output_path.
    Returns the path on success, None otherwise.
    """
    target = output_path or Path(tempfile.mkstemp(suffix=".wav")[1])
    try:
        import requests  # type: ignore
    except ImportError:
        return None

    payload = {"text": text, "speaker": speaker}
    try:
        resp = requests.post(api_url, json=payload, timeout=60)
        resp.raise_for_status()
        audio_bytes = resp.content
        target.write_bytes(audio_bytes)
        return target
    except Exception:
        return None


def send_to_unity(audio_path: Path) -> None:
    """
    Placeholder for sending the generated WAV to Unity.
    Implement via socket, REST, or filesystem watch depending on your Unity side.
    """
    # TODO: Replace with Unity IPC/bridge.
    _ = audio_path


def speak(
    text: str,
    speaker: str = "chisato",
    api_url: str = "http://localhost:5000/tts",
) -> Optional[Path]:
    """
    High-level helper: call SoVITS, then notify Unity.
    """
    audio_path = synthesize_with_sovits(text=text, speaker=speaker, api_url=api_url)
    if audio_path:
        send_to_unity(audio_path)
    return audio_path
