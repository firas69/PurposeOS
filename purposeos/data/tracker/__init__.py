"""
data/tracker/__init__.py — PurposeOS app-tracker sub-package

Re-exports the public API so all existing imports continue to work:

    from purposeos.data.tracker import AppTrackerThread
    from purposeos.data.tracker import init_db, record_daemon_launch

Internal layout:
    db.py        — schema, init_db, migrations, session I/O,
                   record_daemon_launch
    detection.py — window detection strategies (GNOME D-Bus, wnck, xdotool)
    tracker.py   — AppTrackerThread background thread
"""

from purposeos.data.tracker.db import init_db, record_daemon_launch
from purposeos.data.tracker.tracker import AppTrackerThread

__all__ = [
    "AppTrackerThread",
    "init_db",
    "record_daemon_launch",
]
