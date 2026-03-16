"""
notifications/notifications.py — Notification orchestration

Decides whether to fire a screen-wide overlay or a standard desktop
notification, launches the appropriate subprocess, and starts a background
thread to poll for the interaction result.

This is the only file in the notifications sub-package that imports from
other purposeos modules at runtime (sound and interactions).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from purposeos.notifications.interactions import _poll_result
from purposeos.notifications.sound import _play_sound

if TYPE_CHECKING:
    from purposeos.core.config import ReminderConfig

log = logging.getLogger("purposeos.notifications")

# Path to overlay script — lives in the ui/ sub-package next to overlay.py
_OVERLAY_SCRIPT = Path(__file__).parent.parent / "ui" / "overlay.py"


def _user_env() -> dict:
    """Build a complete environment dict for GUI/audio subprocesses."""
    env = os.environ.copy()
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in result.stdout.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                if key in (
                    "DISPLAY",
                    "WAYLAND_DISPLAY",
                    "DBUS_SESSION_BUS_ADDRESS",
                    "XDG_RUNTIME_DIR",
                    "XAUTHORITY",
                    "HOME",
                    "USER",
                    "PULSE_SERVER",
                    "PIPEWIRE_REMOTE",
                ):
                    env.setdefault(key, val)
    except Exception:
        pass
    env.setdefault("DISPLAY", ":0")
    return env


def fire_reminder(reminder: ReminderConfig, db_path: Path) -> None:
    """Called by the scheduler when a reminder fires."""
    try:
        from purposeos.notifications.interactions import _record_interaction

        notif_id = str(uuid.uuid4())
        shown_at = datetime.now().isoformat()

        # Determine timeout
        if reminder.urgency == "critical":
            timeout_ms = 0  # no auto-close
        elif reminder.urgency == "low":
            timeout_ms = 15000
        else:
            timeout_ms = reminder.auto_close_sec * 1000

        # Record in DB
        _record_interaction(db_path, notif_id, reminder.title, reminder.message, shown_at)

        if reminder.screen_wide:
            _fire_screen_wide(reminder, notif_id, shown_at, timeout_ms, db_path)
        else:
            _fire_standard(reminder.title, reminder.message, reminder.urgency, reminder.sound_file)

    except Exception as exc:
        log.error("fire_reminder unhandled exception: %s", exc)


def _fire_screen_wide(
    reminder: ReminderConfig,
    notif_id: str,
    shown_at: str,
    timeout_ms: int,
    db_path: Path,
) -> None:
    result_path = Path(tempfile.gettempdir()) / f"purposeos_overlay_{notif_id}.json"

    cmd = [
        sys.executable,
        str(_OVERLAY_SCRIPT),
        "--title",
        reminder.title,
        "--message",
        reminder.message,
        "--urgency",
        reminder.urgency,
        "--timeout-ms",
        str(timeout_ms),
        "--notification-id",
        notif_id,
        "--result-path",
        str(result_path),
    ]
    if reminder.sound_file:
        cmd += ["--sound-file", reminder.sound_file]

    try:
        subprocess.Popen(
            cmd,
            env=_user_env(),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Screen-wide overlay launched for: %s", reminder.message[:60])
    except Exception as exc:
        log.error("Failed to launch overlay: %s", exc)
        # Fall back to standard notification
        _fire_standard(reminder.title, reminder.message, reminder.urgency, reminder.sound_file)
        return

    # Poll for result in a daemon thread (does not block scheduler)
    poll_timeout = max(timeout_ms / 1000, 300) if timeout_ms > 0 else 3600
    t = threading.Thread(
        target=_poll_result,
        args=(result_path, notif_id, db_path, poll_timeout),
        daemon=True,
        name=f"overlay-poll-{notif_id[:8]}",
    )
    t.start()


def _fire_standard(
    title: str,
    message: str,
    urgency: str,
    sound_file: str | None,
) -> None:
    """Send a standard desktop notification."""
    try:
        import notify2  # type: ignore

        if not notify2.is_initted():
            notify2.init("PurposeOS")
        n = notify2.Notification(title, message)
        urgency_map = {
            "low": notify2.URGENCY_LOW,
            "normal": notify2.URGENCY_NORMAL,
            "critical": notify2.URGENCY_CRITICAL,
        }
        n.set_urgency(urgency_map.get(urgency, notify2.URGENCY_NORMAL))
        n.show()
    except Exception:
        try:
            subprocess.run(
                [
                    "notify-send",
                    "-u",
                    urgency if urgency in ("low", "normal", "critical") else "normal",
                    title,
                    message,
                ],
                env=_user_env(),
                start_new_session=True,
                timeout=5,
            )
        except Exception as exc2:
            log.error("Standard notification failed: %s", exc2)

    if sound_file:
        _play_sound(sound_file, _user_env())
