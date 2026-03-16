"""
notifications/interactions.py — Notification interaction recording

Handles all SQLite read/write for the notification_interactions table:
  - recording when a notification is shown
  - updating it when the user responds (done / timeout)
  - polling a temp JSON file written by the overlay process

No purposeos imports — db_path is passed as an argument to every function.
No GUI, no sound, no subprocess launching.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("purposeos.notifications")


def _record_interaction(
    db_path: Path,
    notif_id: str,
    title: str,
    message: str,
    shown_at: str,
) -> None:
    """Insert a new row into notification_interactions."""
    try:
        import sqlite3

        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO notification_interactions
                   (notification_id, title, message, shown_at)
                   VALUES (?, ?, ?, ?)""",
                (notif_id, title, message, shown_at),
            )
            conn.commit()
    except Exception as exc:
        log.debug("DB insert notification_interactions failed: %s", exc)


def _update_interaction(
    db_path: Path,
    notif_id: str,
    dismissed_at: str,
    response_sec: float,
    action: str,
) -> None:
    try:
        import sqlite3

        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """UPDATE notification_interactions
                   SET dismissed_at=?, response_sec=?, action=?
                   WHERE notification_id=?""",
                (dismissed_at, response_sec, action, notif_id),
            )
            conn.commit()
    except Exception as exc:
        log.debug("DB update notification_interactions failed: %s", exc)


def _poll_result(
    result_path: Path,
    notif_id: str,
    db_path: Path,
    timeout: float,
) -> None:
    """Background thread: waits for the overlay to write its result JSON."""
    deadline = time.monotonic() + timeout + 10  # extra grace
    while time.monotonic() < deadline:
        if result_path.exists():
            try:
                data = json.loads(result_path.read_text())
                dismissed_at = data.get("dismissed_at", datetime.now().isoformat())
                response_sec = float(data.get("response_sec", 0))
                action = data.get("action", "timeout")
                _update_interaction(db_path, notif_id, dismissed_at, response_sec, action)
                log.debug(
                    "Notification %s result: action=%s response_sec=%.1f",
                    notif_id,
                    action,
                    response_sec,
                )
            except Exception as exc:
                log.debug("Failed to parse overlay result: %s", exc)
            finally:
                with contextlib.suppress(Exception):
                    result_path.unlink(missing_ok=True)
            return
        time.sleep(0.5)
    # Timed out waiting for result
    log.debug("No result received for notification %s within deadline", notif_id)
    with contextlib.suppress(Exception):
        result_path.unlink(missing_ok=True)
