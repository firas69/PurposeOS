"""
config.py — PurposeOS Configuration Layer

Defines all dataclasses for reminders, actions, and global settings.
Handles loading from ~/.config/automation-daemon/config.yaml, auto-creating
a commented skeleton if the file is missing, and parsing/validating fields.

Design decisions:
- All path fields use Path objects; ~ is expanded at parse time.
- Unknown YAML keys are silently ignored so old configs stay forward-compatible.
- Dataclass defaults mirror the documented YAML schema defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Well-known paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "automation-daemon"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DATA_DIR = Path.home() / ".local" / "share" / "automation-daemon"
LOGS_DIR = DATA_DIR / "logs"
NOTES_DIR = CONFIG_DIR / "notes"
PID_FILE = DATA_DIR / "daemon.pid"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReminderConfig:
    message: str
    title: str = "Reminder"
    trigger: str = "daily"  # boot | daily | interval_minutes | weekly
    trigger_value: Any = None  # time str "HH:MM", int minutes, or weekday str
    urgency: str = "normal"  # low | normal | critical
    sound_file: str | None = None
    screen_wide: bool = True
    auto_close_sec: int = 30  # ignored when urgency=critical
    enabled: bool = True


@dataclass
class ActionConfig:
    action_type: str  # open_file | open_app | run_command | open_url | show_notification
    trigger: str = "daily"
    trigger_value: Any = None
    target: str = ""  # file path, app name, command, or URL
    notification_title: str = "Reminder"
    notification_message: str = ""
    urgency: str = "normal"
    sound_file: str | None = None
    enabled: bool = True


@dataclass
class SettingsConfig:
    log_level: str = "INFO"
    sound_command: str = "paplay"
    notification_timeout_ms: int = 30000  # default for screen-wide normal urgency
    screen_wide_default: bool = True
    tracker_poll_interval_sec: int = 5
    notes_dir: str = ""  # empty = use default
    language: str = "en"  # i18n language code (en | fr | ar | ru)


def get_notes_dir() -> Path:
    """Return the active notes directory, respecting config override if set."""
    try:
        cfg = load_config()
        nd = cfg.settings.notes_dir.strip()
        if nd:
            p = Path(nd).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            return p
    except Exception:
        pass
    return NOTES_DIR


@dataclass
class DaemonConfig:
    reminders: list[ReminderConfig] = field(default_factory=list)
    actions: list[ActionConfig] = field(default_factory=list)
    settings: SettingsConfig = field(default_factory=SettingsConfig)


# ---------------------------------------------------------------------------
# Skeleton YAML (written on first run)
# ---------------------------------------------------------------------------

SKELETON_YAML = """\
# PurposeOS daemon configuration
# Edit this file; the daemon reloads it automatically on save.

settings:
  log_level: INFO                    # DEBUG | INFO | WARNING | ERROR
  sound_command: paplay              # command used to play sounds
  notification_timeout_ms: 30000    # auto-close timeout for normal urgency screen-wide overlays
  screen_wide_default: true          # show overlays full-screen by default
  tracker_poll_interval_sec: 5       # how often to poll the active window (seconds)
  language: en                       # GUI language: en | fr | ar | ru

reminders:
  # Example: daily reminder at 09:00
  # - message: "Good morning! Check your tasks."
  #   title: "Morning Check-in"
  #   trigger: daily
  #   trigger_value: "09:00"
  #   urgency: normal          # low | normal | critical
  #   sound_file: bell         # freedesktop event name or /abs/path/to/sound.ogg
  #   screen_wide: true
  #   auto_close_sec: 30       # ignored when urgency is critical
  #   enabled: true

  # Example: reminder every 90 minutes
  # - message: "Take a short break and stretch."
  #   title: "Break Time"
  #   trigger: interval_minutes
  #   trigger_value: 90
  #   urgency: low
  #   screen_wide: true
  #   auto_close_sec: 15
  #   enabled: true

  # Example: weekly reminder on Monday morning
  # - message: "Weekly planning session!"
  #   title: "Weekly Review"
  #   trigger: weekly
  #   trigger_value: mon        # mon|tue|wed|thu|fri|sat|sun
  #   urgency: normal
  #   enabled: true

actions:
  # Example: open a file on boot
  # - action_type: open_file
  #   trigger: boot
  #   target: ~/Documents/todo.txt
  #   enabled: true

  # Example: open an app daily
  # - action_type: open_app
  #   trigger: daily
  #   trigger_value: "08:55"
  #   target: firefox
  #   enabled: true

  # Example: run a command every hour
  # - action_type: run_command
  #   trigger: interval_minutes
  #   trigger_value: 60
  #   target: "notify-send 'Hourly ping' 'Still running'"
  #   enabled: true
"""

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_settings(raw: dict[str, Any]) -> SettingsConfig:
    s = SettingsConfig()
    if not raw:
        return s
    s.log_level = str(raw.get("log_level", s.log_level))
    s.sound_command = str(raw.get("sound_command", s.sound_command))
    s.notification_timeout_ms = int(raw.get("notification_timeout_ms", s.notification_timeout_ms))
    s.screen_wide_default = bool(raw.get("screen_wide_default", s.screen_wide_default))
    s.tracker_poll_interval_sec = int(
        raw.get("tracker_poll_interval_sec", s.tracker_poll_interval_sec)
    )
    s.notes_dir = str(raw.get("notes_dir", s.notes_dir) or "")
    s.language = str(raw.get("language", s.language) or "en")  # i18n fix
    return s


def _parse_reminder(raw: dict[str, Any]) -> ReminderConfig:
    r = ReminderConfig(message=str(raw.get("message", "")))
    r.title = str(raw.get("title", r.title))
    r.trigger = str(raw.get("trigger", r.trigger))
    r.trigger_value = raw.get("trigger_value", r.trigger_value)
    r.urgency = str(raw.get("urgency", r.urgency))
    sf = raw.get("sound_file")
    r.sound_file = str(sf) if sf else None
    r.screen_wide = bool(raw.get("screen_wide", r.screen_wide))
    r.auto_close_sec = int(raw.get("auto_close_sec", r.auto_close_sec))
    r.enabled = bool(raw.get("enabled", r.enabled))
    return r


def _parse_action(raw: dict[str, Any]) -> ActionConfig:
    a = ActionConfig(action_type=str(raw.get("action_type", "run_command")))
    a.trigger = str(raw.get("trigger", a.trigger))
    a.trigger_value = raw.get("trigger_value", a.trigger_value)
    # Normalise and expand ~ in file/app targets at parse time.
    # Guard against a common mistake: ~/home/username/... (double home).
    import os
    import re as _re

    target = str(raw.get("target", ""))
    if target.startswith("~"):
        _home = os.path.expanduser("~")
        _user = os.path.basename(_home)
        target = _re.sub(rf"^~/home/{_re.escape(_user)}/", "~/", target)
        target = _re.sub(rf"^~/home/{_re.escape(_user)}$", "~", target)
        a.target = str(Path(target).expanduser())
    else:
        a.target = target
    a.notification_title = str(raw.get("notification_title", a.notification_title))
    a.notification_message = str(raw.get("notification_message", a.notification_message))
    a.urgency = str(raw.get("urgency", a.urgency))
    sf = raw.get("sound_file")
    a.sound_file = str(sf) if sf else None
    a.enabled = bool(raw.get("enabled", a.enabled))
    return a


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config() -> DaemonConfig:
    """Load (or auto-create) the YAML config and return a DaemonConfig."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(SKELETON_YAML, encoding="utf-8")

    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    reminders = [_parse_reminder(r) for r in (raw.get("reminders") or []) if isinstance(r, dict)]
    actions = [_parse_action(a) for a in (raw.get("actions") or []) if isinstance(a, dict)]
    settings = _parse_settings(raw.get("settings") or {})

    return DaemonConfig(reminders=reminders, actions=actions, settings=settings)


def write_config(cfg: DaemonConfig) -> None:
    """Serialise a DaemonConfig back to config.yaml (for GUI use)."""
    data: dict[str, Any] = {
        "settings": {
            "log_level": cfg.settings.log_level,
            "sound_command": cfg.settings.sound_command,
            "notification_timeout_ms": cfg.settings.notification_timeout_ms,
            "screen_wide_default": cfg.settings.screen_wide_default,
            "tracker_poll_interval_sec": cfg.settings.tracker_poll_interval_sec,
            "notes_dir": cfg.settings.notes_dir,
            "language": cfg.settings.language,  # i18n fix
        },
        "reminders": [],
        "actions": [],
    }
    for r in cfg.reminders:
        entry: dict[str, Any] = {
            "message": r.message,
            "title": r.title,
            "trigger": r.trigger,
            "urgency": r.urgency,
            "screen_wide": r.screen_wide,
            "auto_close_sec": r.auto_close_sec,
            "enabled": r.enabled,
        }
        if r.trigger_value is not None:
            entry["trigger_value"] = r.trigger_value
        if r.sound_file:
            entry["sound_file"] = r.sound_file
        data["reminders"].append(entry)
    for a in cfg.actions:
        entry = {
            "action_type": a.action_type,
            "trigger": a.trigger,
            "target": a.target,
            "enabled": a.enabled,
        }
        if a.trigger_value is not None:
            entry["trigger_value"] = a.trigger_value
        if a.notification_title:
            entry["notification_title"] = a.notification_title
        if a.notification_message:
            entry["notification_message"] = a.notification_message
        if a.sound_file:
            entry["sound_file"] = a.sound_file
        data["actions"].append(entry)

    CONFIG_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8"
    )
