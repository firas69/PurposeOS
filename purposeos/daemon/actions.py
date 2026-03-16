"""
actions.py — PurposeOS Action Executor

Handles all five action types: open_file, open_app, run_command, open_url,
show_notification. All child processes are launched with start_new_session=True
and the user's graphical environment variables so they can reach the display.

Design decisions:
- Every action is wrapped in a broad try/except so a single failing job never
  crashes the scheduler thread.
- tracker.record_daemon_launch() is called for open_app so the tracker can flag
  those sessions with is_daemon_launch=1.
- _user_env() is called for every subprocess that touches the GUI.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from purposeos.core.config import ActionConfig

log = logging.getLogger("purposeos.actions")


def _user_env() -> dict:
    """Build a complete environment dict for GUI subprocesses.

    When the daemon runs under systemd --user, variables like DISPLAY,
    WAYLAND_DISPLAY and DBUS_SESSION_BUS_ADDRESS are not inherited from the
    shell that started the session. We always query `systemctl --user
    show-environment` and overlay those values so child processes can reach
    the graphical session regardless of how the daemon was started.
    """
    env = os.environ.copy()
    # Always pull the graphical-session vars from systemd's user environment.
    # This is a no-op when they are already present (direct launch), and
    # essential when they are absent (systemd unit launch).
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
                # Only override vars the kernel-env is missing or empty
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
    # Absolute last resort defaults
    env.setdefault("DISPLAY", ":0")
    return env


def _launch(cmd: list[str], shell: bool = False) -> None:
    """Launch a detached subprocess."""
    subprocess.Popen(
        cmd,
        shell=shell,
        env=_user_env(),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_command(cmd: str) -> str:
    """Run a shell command with timeout; return combined output."""
    result = subprocess.run(
        cmd,
        shell=True,
        env=_user_env(),
        capture_output=True,
        text=True,
        timeout=10,
        start_new_session=True,
    )
    return (result.stdout + result.stderr).strip()


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------


def do_open_file(target: str) -> None:
    path = Path(target).expanduser()
    if not path.exists():
        log.warning("open_file: path does not exist: %s", path)
    _launch(["xdg-open", str(path)])
    log.info("open_file: %s", path)


def do_open_app(target: str, db_path: Path) -> None:
    """Open an app and record it in the tracker as a daemon launch."""
    binary = shutil.which(target)
    if binary:
        _launch([binary])
        log.info("open_app (binary): %s", binary)
    else:
        # Fallback: try gtk-launch for .desktop IDs
        _launch(["gtk-launch", target])
        log.info("open_app (gtk-launch): %s", target)

    # Notify tracker
    try:
        from purposeos.data.tracker import record_daemon_launch

        record_daemon_launch(target, db_path)
    except Exception as exc:
        log.debug("tracker.record_daemon_launch failed: %s", exc)


def do_run_command(cmd: str) -> None:
    try:
        output = _run_command(cmd)
        log.info("run_command: %s\noutput: %s", cmd, output[:500])
    except subprocess.TimeoutExpired:
        log.warning("run_command timed out: %s", cmd)
    except Exception as exc:
        log.error("run_command error: %s", exc)


def do_open_url(url: str) -> None:
    _launch(["xdg-open", url])
    log.info("open_url: %s", url)


def do_show_notification(title: str, message: str, urgency: str = "normal") -> None:
    """Send a standard desktop notification (not a screen-wide overlay)."""
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
        log.info("show_notification (notify2): %s — %s", title, message)
        return
    except Exception:
        pass
    # Fallback: notify-send
    try:
        urgency_arg = urgency if urgency in ("low", "normal", "critical") else "normal"
        subprocess.run(
            ["notify-send", "-u", urgency_arg, title, message],
            env=_user_env(),
            start_new_session=True,
            timeout=5,
        )
        log.info("show_notification (notify-send): %s — %s", title, message)
    except Exception as exc:
        log.error("show_notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def execute_action(action: ActionConfig, db_path: Path) -> None:
    """Top-level dispatcher — never raises; all errors are logged."""
    try:
        t = action.action_type
        if t == "open_file":
            do_open_file(action.target)
        elif t == "open_app":
            do_open_app(action.target, db_path)
        elif t == "run_command":
            do_run_command(action.target)
        elif t == "open_url":
            do_open_url(action.target)
        elif t == "show_notification":
            do_show_notification(
                action.notification_title, action.notification_message, action.urgency
            )
        else:
            log.warning("Unknown action_type '%s'", t)
    except Exception as exc:
        log.error("execute_action unhandled exception [%s]: %s", action.action_type, exc)
