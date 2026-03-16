"""
watcher.py — PurposeOS Configuration File Watcher

Monitors config.yaml for changes and calls the on_change callback. Uses the
watchdog library's inotify observer when available; falls back to mtime polling
so the daemon works on filesystems where inotify is unavailable.

Design decisions:
- The callback only sets a boolean flag in the daemon; no heavy logic runs here.
- Polling interval is 2 seconds — fast enough to feel responsive, slow enough
  not to waste CPU.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("purposeos.watcher")


class ConfigWatcher:
    """Watches a single file for modifications and calls on_change."""

    def __init__(self, path: Path, on_change: Callable[[], None]) -> None:
        self._path = path
        self._on_change = on_change
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        # Try watchdog inotify first
        try:
            self._start_watchdog()
            log.debug("ConfigWatcher using watchdog inotify observer.")
            return
        except Exception as exc:
            log.debug("watchdog unavailable (%s); falling back to mtime polling.", exc)
        # Fallback: mtime polling
        self._start_polling()
        log.debug("ConfigWatcher using mtime polling.")

    def _start_watchdog(self) -> None:
        from watchdog.events import FileSystemEventHandler  # type: ignore
        from watchdog.observers import Observer  # type: ignore

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory and event.src_path == str(watcher._path):
                    log.info("Config file changed (inotify); triggering reload.")
                    watcher._on_change()

            def on_created(self, event):
                if not event.is_directory and event.src_path == str(watcher._path):
                    log.info("Config file created (inotify); triggering reload.")
                    watcher._on_change()

        observer = Observer()
        observer.schedule(Handler(), path=str(self._path.parent), recursive=False)
        observer.daemon = True
        observer.start()
        self._watchdog_observer = observer

    def _start_polling(self) -> None:
        last_mtime = self._path.stat().st_mtime if self._path.exists() else 0.0

        def _poll() -> None:
            nonlocal last_mtime
            while not self._stop_event.is_set():
                try:
                    mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
                    if mtime != last_mtime:
                        last_mtime = mtime
                        log.info("Config file changed (mtime poll); triggering reload.")
                        self._on_change()
                except Exception as exc:
                    log.debug("ConfigWatcher poll error: %s", exc)
                self._stop_event.wait(timeout=2.0)

        self._thread = threading.Thread(target=_poll, daemon=True, name="config-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if hasattr(self, "_watchdog_observer"):
            try:
                self._watchdog_observer.stop()
                self._watchdog_observer.join(timeout=2)
            except Exception:
                pass
