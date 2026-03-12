from __future__ import annotations

from stt import transcribe


if __name__ == "__main__":
    print("Speak now...")
    text = transcribe(duration_sec=10)
    print("Recognized:", text)

