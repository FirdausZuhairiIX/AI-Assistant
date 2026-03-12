"""
System-level helper stubs for local actions (launch apps, play audio, etc.).

These are intentionally conservative so they are safe to run by default;
expand them to fit your environment.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


def open_path(target: str) -> bool:
    """
    Open a file or application using the OS default handler.
    """
    path = Path(target).expanduser()
    if not path.exists():
        return False
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def play_audio(path: str) -> bool:
    """
    Play an audio file via the default system player (blocking).
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return False
    try:
        os.startfile(str(file_path))  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def run_command(command: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess[str] | None:
    """
    Run a shell command and return the completed process. Returns None on failure.
    """
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=True,
            check=False,
        )
    except Exception:
        return None
