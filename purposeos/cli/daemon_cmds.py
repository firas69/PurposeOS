"""
cli/daemon_cmds.py — Daemon lifecycle commands

Handles all commands that communicate directly with the running daemon:
start, stop, restart, reload (SIGHUP), status, logs, enable, disable.

Daemon communication is via PID file + os.kill(pid, signal).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from purposeos.cli._output import GR, RE, B, R, _err, _info, _ok
from purposeos.core.config import LOGS_DIR, PID_FILE

# ── PID helpers ───────────────────────────────────────────────────


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _daemon_running() -> tuple[bool, int | None]:
    pid = _read_pid()
    if pid is None:
        return False, None
    running = _is_running(pid)
    return running, pid if running else None


# ── Commands ──────────────────────────────────────────────────────


def cmd_start(_args) -> None:
    running, pid = _daemon_running()
    if running:
        _info(f"Daemon already running (pid {pid}).")
        return
    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", "purposeos.service"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _ok("PurposeOS daemon started via systemd.")
        else:
            proc = subprocess.Popen(
                [sys.executable, "-m", "purposeos.main"],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _ok(f"PurposeOS daemon started (pid {proc.pid}).")
    except Exception as exc:
        _err(f"Failed to start daemon: {exc}")


def cmd_stop(_args) -> None:
    running, pid = _daemon_running()
    if not running:
        _info("Daemon is not running.")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        _ok(f"Sent SIGTERM to pid {pid}.")
    except Exception as exc:
        _err(f"Failed to stop daemon: {exc}")


def cmd_restart(_args) -> None:
    cmd_stop(_args)
    import time

    time.sleep(1)
    cmd_start(_args)


def cmd_reload(_args) -> None:
    running, pid = _daemon_running()
    if not running:
        _err("Daemon is not running.")
        return
    try:
        os.kill(pid, signal.SIGHUP)
        _ok(f"Sent SIGHUP (reload) to pid {pid}.")
    except Exception as exc:
        _err(f"Failed to reload: {exc}")


def cmd_status(_args) -> None:
    running, pid = _daemon_running()
    if running:
        print(f"\n  {GR}{B}● PurposeOS daemon is running{R}  (pid {pid})\n")
    else:
        print(f"\n  {RE}{B}○ PurposeOS daemon is stopped{R}\n")


def cmd_logs(args) -> None:
    log_file = LOGS_DIR / "daemon.log"
    if not log_file.exists():
        _err(f"Log file not found: {log_file}")
        return
    n = getattr(args, "lines", 50)
    try:
        subprocess.run(["tail", f"-n{n}", str(log_file)])
    except Exception:
        lines = log_file.read_text(encoding="utf-8").splitlines()
        print("\n".join(lines[-n:]))


def cmd_enable(_args) -> None:
    result = subprocess.run(
        ["systemctl", "--user", "enable", "purposeos.service"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        _ok("purposeos.service enabled (will start at login).")
    else:
        _err(result.stderr.strip())


def cmd_disable(_args) -> None:
    result = subprocess.run(
        ["systemctl", "--user", "disable", "purposeos.service"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        _ok("purposeos.service disabled.")
    else:
        _err(result.stderr.strip())
