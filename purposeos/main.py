"""
main.py — PurposeOS Daemon Entry Point

Bootstraps the daemon: loads config, initialises logging, starts the
AppTrackerThread, wires up the scheduler, installs signal handlers, and
enters the main event loop. Every subsystem failure is caught so the daemon
never dies because of a single bad component.

Design decisions:
- Signal handlers only flip boolean flags; no logic runs inside them.
- Config is loaded once at startup; SIGHUP triggers an atomic live reload.
- db_path is resolved once here and passed into every subsystem that needs it,
  avoiding global mutable state.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import sys
import time
from pathlib import Path

from purposeos.core.config import CONFIG_PATH, DATA_DIR, LOGS_DIR, PID_FILE, load_config
from purposeos.daemon.scheduler import build_scheduler
from purposeos.daemon.watcher import ConfigWatcher
from purposeos.data.tracker import AppTrackerThread

# ---------------------------------------------------------------------------
# Logging bootstrap (before anything else so early errors are captured)
# ---------------------------------------------------------------------------


def _setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger("purposeos")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh = RotatingFileHandler(LOGS_DIR / "daemon.log", maxBytes=5 * 1024 * 1024, backupCount=5)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------------------
# DaemonController — owns all mutable daemon state as instance attributes
# ---------------------------------------------------------------------------


class DaemonController:
    """Central controller that owns signal flags and subsystem references."""

    def __init__(self) -> None:
        self._stop = False
        self._reload = False
        self.logger = _setup_logging()
        self.cfg = None
        self.scheduler = None
        self.watcher = None
        self.tracker = None

    # --- Signal handlers (must only set flags) ----------------------------

    def handle_sigterm(self, signum, frame) -> None:  # noqa: ARG002
        self._stop = True

    def handle_sigint(self, signum, frame) -> None:  # noqa: ARG002
        self._stop = True

    def handle_sighup(self, signum, frame) -> None:  # noqa: ARG002
        self._reload = True

    # --- Lifecycle --------------------------------------------------------

    def _write_pid(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

    def _remove_pid(self) -> None:
        with contextlib.suppress(Exception):
            PID_FILE.unlink(missing_ok=True)

    def _atomic_reload(self) -> None:
        """Load fresh config atomically; swap only on success."""
        try:
            new_cfg = load_config()
            old_scheduler = self.scheduler
            new_scheduler = build_scheduler(new_cfg, self._db_path(), reload=True)
            new_scheduler.start()
            self.cfg = new_cfg
            if old_scheduler:
                old_scheduler.shutdown(wait=False)
            self.scheduler = new_scheduler
            self.logger.info("Config reloaded successfully.")
        except Exception as exc:
            self.logger.error("Config reload failed — keeping old config: %s", exc)

    def _db_path(self) -> Path:
        return DATA_DIR / "tracker.db"

    def start(self) -> None:
        self.logger.info("PurposeOS daemon starting (pid=%d)", os.getpid())
        self._write_pid()

        signal.signal(signal.SIGTERM, self.handle_sigterm)
        signal.signal(signal.SIGINT, self.handle_sigint)
        signal.signal(signal.SIGHUP, self.handle_sighup)

        # Initial config load
        try:
            self.cfg = load_config()
        except Exception as exc:
            self.logger.critical("Failed to load config: %s", exc)
            sys.exit(1)

        db_path = self._db_path()

        # Start app tracker thread
        try:
            self.tracker = AppTrackerThread(db_path)
            self.tracker.start()
        except Exception as exc:
            self.logger.warning("AppTrackerThread failed to start: %s", exc)

        # Build and start scheduler (always pass is_initial_start=True on first start)
        try:
            self.scheduler = build_scheduler(self.cfg, db_path, reload=False, is_initial_start=True)
            self.scheduler.start()
        except Exception as exc:
            self.logger.critical("Scheduler failed to start: %s", exc)
            self._shutdown()
            sys.exit(1)

        # Config file watcher
        try:
            self.watcher = ConfigWatcher(
                CONFIG_PATH, on_change=lambda: self.__setattr__("_reload", True)
            )
            self.watcher.start()
        except Exception as exc:
            self.logger.warning("ConfigWatcher failed to start: %s", exc)

        self.logger.info("PurposeOS daemon running.")
        self._main_loop()

    def _main_loop(self) -> None:
        while not self._stop:
            if self._reload:
                self._reload = False
                self.logger.info("Reload flag set — reloading config.")
                self._atomic_reload()
            time.sleep(1)
        self._shutdown()

    def _shutdown(self) -> None:
        self.logger.info("PurposeOS daemon shutting down.")
        if self.watcher:
            with contextlib.suppress(Exception):
                self.watcher.stop()
        if self.tracker:
            try:
                self.tracker.stop()
                self.tracker.join(timeout=5)
            except Exception:
                pass
        if self.scheduler:
            with contextlib.suppress(Exception):
                self.scheduler.shutdown(wait=False)
        self._remove_pid()
        self.logger.info("PurposeOS daemon stopped.")


def main() -> None:
    DaemonController().start()


if __name__ == "__main__":
    main()
