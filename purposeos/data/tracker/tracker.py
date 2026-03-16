"""
data/tracker/tracker.py — AppTrackerThread

Background thread that polls the active window every N seconds.
Delegates all database writes to db.py and all window detection to detection.py.

Design decisions:
- If xdotool is absent the thread logs a warning and exits cleanly without
  crashing the daemon.
- Session open/close is edge-triggered: only when the focused window changes.
- Daemon threads do not block process exit.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import threading
from pathlib import Path

from purposeos.data.tracker.db import _close_session, _open_session, init_db
from purposeos.data.tracker.detection import _get_active_window_info

log = logging.getLogger("purposeos.tracker")


class AppTrackerThread(threading.Thread):
    """Background thread that polls the active window every poll_interval seconds."""

    def __init__(self, db_path: Path, poll_interval: int = 5) -> None:
        super().__init__(name="app-tracker", daemon=True)
        self._db_path = db_path
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._current_session_id: int | None = None
        self._current_app: str | None = None
        self._xdotool_available = bool(shutil.which("xdotool"))

    def run(self) -> None:
        if not self._xdotool_available:
            log.warning(
                "xdotool not found — app tracking disabled. Install with: sudo dnf install xdotool"
            )
            return

        try:
            init_db(self._db_path)
        except Exception as exc:
            log.error("Failed to init tracker DB: %s", exc)
            return

        log.info("AppTrackerThread started (poll interval: %ds)", self._poll_interval)

        while not self._stop_event.is_set():
            try:
                app_name, window_title = _get_active_window_info()
                if app_name != self._current_app:
                    # Close old session
                    if self._current_session_id is not None:
                        try:
                            _close_session(self._db_path, self._current_session_id)
                        except Exception as exc:
                            log.debug("Error closing session: %s", exc)
                    # Open new session
                    try:
                        self._current_session_id = _open_session(
                            self._db_path, app_name, window_title
                        )
                        self._current_app = app_name
                    except Exception as exc:
                        log.debug("Error opening session: %s", exc)
                        self._current_session_id = None
            except FileNotFoundError:
                log.warning("xdotool disappeared from PATH — tracking disabled.")
                return
            except Exception as exc:
                log.debug("AppTrackerThread poll error: %s", exc)

            self._stop_event.wait(timeout=self._poll_interval)

        # Close open session on shutdown
        if self._current_session_id is not None:
            with contextlib.suppress(Exception):
                _close_session(self._db_path, self._current_session_id)
        log.info("AppTrackerThread stopped.")

    def stop(self) -> None:
        self._stop_event.set()
