"""
Screen capture and vision description utilities.

Captures the desktop (via mss if available) and forwards the image to a
Qwen3-VL endpoint for captioning. Networking is stub-friendly: if requests
is missing or the server is unreachable, returns None.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional


def capture_screen() -> Path:
    """
    Capture the current screen to a temporary PNG file.
    Uses mss if available; otherwise writes an empty placeholder file.
    """
    tmp_path = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=str(tmp_path))
    except Exception:
        tmp_path.write_bytes(b"")
    return tmp_path


def describe_with_qwen(image_path: Path, api_url: str = "http://localhost:8000/vl") -> Optional[str]:
    """
    Send the image to a Qwen3-VL endpoint and return its description.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        return None

    files = {"image": image_path.open("rb")}
    try:
        resp = requests.post(api_url, files=files, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("description") or data.get("text")
    except Exception:
        return None
    finally:
        files["image"].close()


def read_screen(api_url: str = "http://localhost:8000/vl") -> Optional[str]:
    """
    Capture the screen and request a description from Qwen3-VL.
    """
    image_path = capture_screen()
    return describe_with_qwen(image_path, api_url=api_url)
