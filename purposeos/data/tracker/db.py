"""
data/tracker/db.py — SQLite schema, initialisation, and session I/O

Owns the tracker.db schema and all direct database writes:
  - table creation and migrations
  - opening and closing app sessions
  - recording daemon-launched app entries

A module-level threading.Lock serialises all writes so the tracker thread
and other callers (actions.py) never corrupt the database concurrently.

All queries use parameterised placeholders — no string interpolation into SQL.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger("purposeos.tracker")

# Shared lock for all DB writers in this process
_db_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name        TEXT    NOT NULL,
    window_title    TEXT,
    started_at      TEXT    NOT NULL,
    ended_at        TEXT,
    duration_sec    REAL,
    date            TEXT    NOT NULL,
    is_daemon_launch INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_app_sessions_date ON app_sessions(date);
CREATE INDEX IF NOT EXISTS idx_app_sessions_app  ON app_sessions(app_name);

CREATE TABLE IF NOT EXISTS notification_interactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id  TEXT    UNIQUE NOT NULL,
    title            TEXT,
    message          TEXT,
    shown_at         TEXT    NOT NULL,
    dismissed_at     TEXT,
    response_sec     REAL,
    action           TEXT    DEFAULT 'pending'
);
"""

_MIGRATIONS = [
    # Add title column if upgrading from an older DB that didn't have it
    "ALTER TABLE notification_interactions ADD COLUMN title TEXT;",
    # Backfill title from message for any rows recorded before title was tracked
    "UPDATE notification_interactions SET title = message WHERE title IS NULL OR title = '';",
]


def init_db(db_path: Path) -> None:
    """Create tables if they don't exist, and run any pending migrations."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _db_lock, sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_SCHEMA_SQL)
        for migration in _MIGRATIONS:
            try:
                conn.execute(migration)
                conn.commit()
            except Exception:
                pass  # column already exists — safe to ignore

        # Backfill title for rows where title still equals message
        # by matching against the current config.yaml reminders.
        try:
            from purposeos.core.config import CONFIG_PATH, load_config

            if CONFIG_PATH.exists():
                cfg = load_config(CONFIG_PATH)
                for reminder in cfg.reminders:
                    if reminder.title and reminder.message:
                        conn.execute(
                            """UPDATE notification_interactions
                                   SET title = ?
                                   WHERE message = ? AND (title IS NULL OR title = '' OR title = message)""",
                            (reminder.title, reminder.message),
                        )
                conn.commit()
        except Exception as exc:
            log.debug("Title backfill skipped: %s", exc)

    log.debug("tracker DB initialised at %s", db_path)


# ---------------------------------------------------------------------------
# Session management helpers (called from AppTrackerThread)
# ---------------------------------------------------------------------------


def _open_session(db_path: Path, app_name: str, window_title: str) -> int:
    now = datetime.now().isoformat()
    date = now[:10]
    with _db_lock, sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            """INSERT INTO app_sessions (app_name, window_title, started_at, date)
                   VALUES (?, ?, ?, ?)""",
            (app_name, window_title, now, date),
        )
        conn.commit()
        return cur.lastrowid


def _close_session(db_path: Path, session_id: int) -> None:
    now = datetime.now().isoformat()
    with _db_lock, sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT started_at FROM app_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if row:
            try:
                started = datetime.fromisoformat(row[0])
                duration = (datetime.now() - started).total_seconds()
            except Exception:
                duration = 0.0
            conn.execute(
                """UPDATE app_sessions
                       SET ended_at=?, duration_sec=?
                       WHERE id=?""",
                (now, duration, session_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Public helper: called by actions.py
# ---------------------------------------------------------------------------


def record_daemon_launch(app_name: str, db_path: Path) -> None:
    """Open a session row flagged as a daemon launch."""
    try:
        now = datetime.now().isoformat()
        date = now[:10]
        with _db_lock, sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """INSERT INTO app_sessions
                       (app_name, window_title, started_at, date, is_daemon_launch)
                       VALUES (?, ?, ?, ?, 1)""",
                (app_name, f"[daemon-launched] {app_name}", now, date),
            )
            conn.commit()
    except Exception as exc:
        log.debug("record_daemon_launch error: %s", exc)
