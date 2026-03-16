"""
scheduler.py — PurposeOS Scheduling Engine

Builds and returns an APScheduler BackgroundScheduler populated with jobs
derived from the DaemonConfig. Supports boot, daily, interval_minutes, and
weekly triggers.

Design decisions:
- Timezone is always resolved via tzlocal.get_localzone() — never the string
  'local', which APScheduler rejects on some distros.
- coalesce=True + max_instances=1 prevent duplicate job pile-up after suspend/
  resume cycles.
- The scheduler object is returned un-started so callers decide when to begin.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from tzlocal import get_localzone

from purposeos.core.config import DATA_DIR

if TYPE_CHECKING:
    from purposeos.core.config import DaemonConfig

log = logging.getLogger("purposeos.scheduler")

# Mapping of weekday abbreviations to APScheduler day_of_week values
_DOW = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}


def _make_trigger(trigger: str, value, start_date=None):
    """Build an APScheduler trigger from config trigger type + value."""
    tz = get_localzone()

    if trigger == "boot":
        run_at = datetime.now(tz=tz) + timedelta(seconds=3)
        return DateTrigger(run_date=run_at, timezone=tz)

    if trigger in ("time", "daily"):
        # value expected as "HH:MM" or "HH:MM:SS"
        parts = str(value or "09:00").split(":")
        hour = int(parts[0]) if len(parts) > 0 else 9
        minute = int(parts[1]) if len(parts) > 1 else 0
        return CronTrigger(hour=hour, minute=minute, timezone=tz)

    if trigger == "interval_minutes":
        minutes = int(value or 30)
        return IntervalTrigger(minutes=minutes, start_date=start_date, timezone=tz)

    if trigger == "weekly":
        dow = _DOW.get(str(value or "mon").lower(), "mon")
        return CronTrigger(day_of_week=dow, hour=9, minute=0, timezone=tz)

    log.warning("Unknown trigger type '%s'; defaulting to daily at 09:00", trigger)
    return CronTrigger(hour=9, minute=0, timezone=tz)


def build_scheduler(
    cfg: DaemonConfig, db_path: Path, reload: bool = False, is_initial_start: bool = False
) -> BackgroundScheduler:
    """Construct a fully-populated BackgroundScheduler from DaemonConfig."""
    from purposeos.daemon.actions import execute_action
    from purposeos.notifications import fire_reminder

    executors = {"default": ThreadPoolExecutor(max_workers=5)}
    job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 60}
    tz = get_localzone()

    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone=tz,
    )

    # Load scheduler state
    state = {}
    state_path = DATA_DIR / "scheduler_state.yaml"
    if state_path.exists():
        try:
            with open(state_path) as f:
                state = yaml.safe_load(f) or {}
        except Exception as exc:
            log.warning("Failed to load scheduler state: %s", exc)

    # Determine if boot actions should run
    should_run_boot = False
    if is_initial_start:
        try:
            with open("/proc/sys/kernel/random/boot_id") as f:
                current_boot_id = f.read().strip()
            stored_boot_id = state.get("boot_id")
            if stored_boot_id != current_boot_id:
                should_run_boot = True
                state["boot_id"] = current_boot_id
                log.info("System boot detected (boot_id changed), boot actions will run.")
            else:
                log.info("Daemon restart detected (same boot_id), boot actions will NOT run.")
        except Exception as exc:
            log.warning("Failed to detect boot: %s", exc)
            should_run_boot = True  # Fallback to run on error

    # --- Reminder jobs ---
    for idx, reminder in enumerate(cfg.reminders):
        if not reminder.enabled:
            continue
        if reminder.trigger == "boot" and (reload or (is_initial_start and not should_run_boot)):
            continue  # Skip boot reminders
        try:
            job_id = f"reminder_{idx}"
            start_date = None
            if reminder.trigger == "interval_minutes" and job_id in state:
                with contextlib.suppress(Exception):
                    start_date = datetime.fromisoformat(state[job_id])
            trigger = _make_trigger(reminder.trigger, reminder.trigger_value, start_date)
            job = scheduler.add_job(
                func=fire_reminder,
                trigger=trigger,
                args=[reminder, db_path],
                id=job_id,
                name=f"Reminder: {reminder.message[:40]}",
            )
            if reminder.trigger == "interval_minutes":
                state[job_id] = job.trigger.start_date.isoformat()
            log.debug("Scheduled reminder[%d]: %s", idx, reminder.message[:40])
        except Exception as exc:
            log.error("Failed to schedule reminder[%d]: %s", idx, exc)

    # --- Action jobs ---
    for idx, action in enumerate(cfg.actions):
        if not action.enabled:
            continue
        if action.trigger == "boot" and (reload or (is_initial_start and not should_run_boot)):
            continue  # Skip boot actions
        try:
            job_id = f"action_{idx}"
            start_date = None
            if action.trigger == "interval_minutes" and job_id in state:
                with contextlib.suppress(Exception):
                    start_date = datetime.fromisoformat(state[job_id])
            trigger = _make_trigger(action.trigger, action.trigger_value, start_date)
            job = scheduler.add_job(
                func=execute_action,
                trigger=trigger,
                args=[action, db_path],
                id=job_id,
                name=f"Action: {action.action_type} {action.target[:30]}",
            )
            if action.trigger == "interval_minutes":
                state[job_id] = job.trigger.start_date.isoformat()
            log.debug("Scheduled action[%d]: %s %s", idx, action.action_type, action.target[:30])
        except Exception as exc:
            log.error("Failed to schedule action[%d]: %s", idx, exc)

    # Save scheduler state
    try:
        with open(state_path, "w") as f:
            yaml.dump(state, f)
    except Exception as exc:
        log.warning("Failed to save scheduler state: %s", exc)

    return scheduler
