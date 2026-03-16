"""
cli/_config_io.py — Raw YAML config read/write for CLI commands

Provides safe config load/save for reminder and action management commands.
Intentionally separate from gui/_config_bridge.py — the CLI's config I/O
does not depend on the GUI sub-package, keeping adctl usable without PySide6.
"""

from __future__ import annotations


def _load_cfg_safe() -> dict:
    """Load config ensuring reminders/actions are always lists."""
    import yaml

    from purposeos.core.config import CONFIG_PATH

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


def _save_cfg_safe(data: dict) -> None:
    import yaml

    from purposeos.core.config import CONFIG_PATH

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("reminders", [])
    data.setdefault("actions", [])
    CONFIG_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
