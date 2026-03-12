"""
Webcam capture and vision description utilities.

Captures a single frame from the default webcam (via OpenCV if available) and
forwards it to a Qwen3-VL endpoint for mood/face analysis.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional


def capture_frame() -> Path:
    """
    Capture one frame from the default webcam to a temporary PNG file.
    Falls back to an empty file if OpenCV is not available.
    """
    tmp_path = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(0)
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            cv2.imwrite(str(tmp_path), frame)
        else:
            tmp_path.write_bytes(b"")
    except Exception:
        tmp_path.write_bytes(b"")
    return tmp_path


def describe_with_qwen(image_path: Path, api_url: str = "http://localhost:8000/vl") -> Optional[str]:
    """
    Send the webcam image to Qwen3-VL for description.
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


def read_camera(api_url: str = "http://localhost:8000/vl") -> Optional[str]:
    """
    Capture a webcam frame and request a description/mood analysis.
    """
    image_path = capture_frame()
    return describe_with_qwen(image_path, api_url=api_url)
