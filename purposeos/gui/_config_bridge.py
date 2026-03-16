"""
gui/_config_bridge.py — Raw YAML config I/O for the GUI

All config file access the GUI needs in one place:
  - loading and saving raw YAML (dict-level, not dataclasses)
  - triggering a daemon reload via adctl
  - querying daemon status

No GUI widgets are imported here. This is the only file in gui/ that
touches the config file or runs subprocesses.
"""

from __future__ import annotations

import contextlib
import subprocess
from typing import Any


def _load_raw_config() -> dict[str, Any]:
    try:
        from purposeos.core.config import CONFIG_PATH
    except ImportError:
        from config import CONFIG_PATH  # type: ignore[no-redef]
    import yaml

    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}
    if not isinstance(raw.get("reminders"), list):
        raw["reminders"] = []
    if not isinstance(raw.get("actions"), list):
        raw["actions"] = []
    if not isinstance(raw.get("settings"), dict):
        raw["settings"] = {}
    return raw


def _save_raw_config(data: dict[str, Any]) -> None:
    try:
        from purposeos.core.config import CONFIG_PATH
    except ImportError:
        from config import CONFIG_PATH  # type: ignore[no-redef]
    import yaml

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("reminders", [])
    data.setdefault("actions", [])
    data.setdefault("settings", {})
    CONFIG_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _reload_daemon() -> None:
    with contextlib.suppress(Exception):
        subprocess.run(["adctl", "reload"], timeout=5, capture_output=True)


def _daemon_status() -> str:
    try:
        result = subprocess.run(["adctl", "status"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return "unknown"
