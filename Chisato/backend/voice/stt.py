"""
Speech-to-text utilities using Whisper (or any compatible local endpoint).

This module is intentionally lightweight: it records microphone audio, writes
it to a temporary WAV file, and offers a hook to send that audio to Whisper.
Fill in `transcribe_with_whisper` with your chosen Whisper runtime.
"""
from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import Optional


def record_microphone(
    duration_sec: int = 5,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """
    Record audio from the default microphone to a temporary WAV file.
    Uses sounddevice if available; otherwise writes silence as a placeholder.
    """
    tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore

        frames = int(duration_sec * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="int16")
        sd.wait()
        data = audio.flatten().tolist()
    except Exception:
        # Fallback: generate silence so the rest of the pipeline still runs.
        import array

        data = array.array("h", [0] * int(duration_sec * sample_rate * channels))

    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(data))
    return tmp


def transcribe_with_whisper(audio_path: Path, api_url: str = "http://localhost:9000") -> Optional[str]:
    """
    Send an audio file to a Whisper server and return its text.
    Replace this stub with your actual Whisper client (e.g., faster-whisper, openai/whisper, etc.).
    """
    try:
        import requests  # type: ignore
    except ImportError:
        return None

    try:
        with audio_path.open("rb") as f:
            files = {"file": f}
            resp = requests.post(api_url, files=files, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data.get("text") or data.get("transcript")
    except Exception:
        return None


def transcribe(duration_sec: int = 5, whisper_url: str = "http://localhost:9000") -> Optional[str]:
    """
    Convenience helper: record audio, send to Whisper, and return text.
    """
    audio_path = record_microphone(duration_sec=duration_sec)
    return transcribe_with_whisper(audio_path, api_url=whisper_url)
