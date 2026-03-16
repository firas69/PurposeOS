"""
notes/storage.py — Note file I/O

All filesystem operations for notes: list, read, save, delete.
Notes are plain UTF-8 .txt files named YYYY-MM-DD_HH-MM-SS.txt
in the configured notes directory.

No terminal, no GUI, no CLI formatting here — pure file operations only.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from purposeos.core.config import get_notes_dir


def _ensure_notes_dir() -> Path:
    d = get_notes_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamp_filename() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"


def list_notes() -> list[Path]:
    """Return all note files sorted newest-first."""
    d = _ensure_notes_dir()
    return sorted(d.glob("*.txt"), reverse=True)


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def delete_note(path: Path) -> None:
    path.unlink()


def save_note(content: str, path: Path | None = None) -> Path:
    """Write content to path (or a new timestamped file). Returns final path.
    Raises ValueError if content is empty or whitespace-only.
    """
    if not content or not content.strip():
        raise ValueError("Cannot save an empty note.")
    d = _ensure_notes_dir()
    if path is None:
        path = d / _timestamp_filename()
    path.write_text(content, encoding="utf-8")
    return path
