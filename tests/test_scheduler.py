"""
test_scheduler.py — Tests for purposeos.daemon.scheduler.

Uses freezegun for time control. State file is isolated to tmp_path.
All calls to notifications and actions modules are mocked.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml
from freezegun import freeze_time

from apscheduler.triggers.cron     import CronTrigger
from apscheduler.triggers.date     import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Correctly pulls from the new modular package
from purposeos.daemon.scheduler import build_scheduler, _make_trigger, _DOW

# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Redirect DATA_DIR so scheduler_state.yaml writes to tmp_path."""
    # Ensure this accurately targets DATA_DIR inside the new daemon.scheduler namespace
    monkeypatch.setattr("purposeos.daemon.scheduler.DATA_DIR", tmp_path)
    return tmp_path / "scheduler_state.yaml"

@pytest.fixture
def empty_cfg():
    """Minimal DaemonConfig-like object with empty reminders and actions."""
    cfg = MagicMock()
    cfg.reminders = []
    cfg.actions   = []
    return cfg

# ─────────────────────────────────────────────────────────────────
# _make_trigger
# ─────────────────────────────────────────────────────────────────

def test_make_trigger_boot_returns_date_trigger():
    """boot trigger produces a DateTrigger scheduled a few seconds ahead."""
    trig = _make_trigger("boot", None)
    assert isinstance(trig, DateTrigger)
    assert trig.run_date > datetime.now(tz=timezone.utc)

def test_make_trigger_daily_valid():
    """daily trigger with HH:MM produces a CronTrigger at the right hour/minute."""
    trig = _make_trigger("daily", "14:30")
    assert isinstance(trig, CronTrigger)
    assert str(trig.fields[5]) == "14"   # hour
    assert str(trig.fields[6]) == "30"   # minute

def test_make_trigger_daily_defaults_to_0900():
    """daily trigger with no value defaults to 09:00."""
    trig = _make_trigger("daily", None)
    assert str(trig.fields[5]) == "9"
    assert str(trig.fields[6]) == "0"

@pytest.mark.parametrize("bad_time", ["25:00", "12:60", "abc"])
def test_make_trigger_daily_malformed_raises(bad_time):
    """daily trigger raises on malformed time strings."""
    with pytest.raises((ValueError, IndexError)):
        _make_trigger("daily", bad_time)

def test_make_trigger_interval():
    """interval_minutes trigger produces correct IntervalTrigger duration."""
    trig = _make_trigger("interval_minutes", 20)
    assert isinstance(trig, IntervalTrigger)
    assert trig.interval_length == 20 * 60

def test_make_trigger_weekly():
    """weekly trigger produces a CronTrigger with the correct day_of_week."""
    trig = _make_trigger("weekly", "wed")
    assert isinstance(trig, CronTrigger)
    assert str(trig.fields[4]) == "wed"   # day_of_week

def test_make_trigger_unknown_falls_back_to_daily_0900():
    """Unknown trigger type logs a warning and returns daily 09:00 CronTrigger."""
    trig = _make_trigger("random-junk", "whatever")
    assert isinstance(trig, CronTrigger)
    assert str(trig.fields[5]) == "9"
    assert str(trig.fields[6]) == "0"

# ─────────────────────────────────────────────────────────────────
# Boot trigger behaviour
# ─────────────────────────────────────────────────────────────────

@freeze_time("2025-03-15 13:45:00+01:00")
def test_boot_trigger_fires_on_first_call(tmp_state, empty_cfg):
    """Boot reminder is scheduled on the first call (new boot session)."""
    empty_cfg.reminders = [
        MagicMock(trigger="boot", message="Welcome", enabled=True)
    ]
    with patch("purposeos.daemon.scheduler.open",
               mock_open(read_data="boot-abc123")):
        sched = build_scheduler(empty_cfg, Path("fake.db"), is_initial_start=True)
    assert sched.get_job("reminder_0") is not None

@freeze_time("2025-03-15 13:45:00+01:00")
def test_boot_trigger_skipped_on_same_boot(tmp_state, empty_cfg):
    """Boot reminder is NOT re-scheduled when boot_id hasn't changed."""
    empty_cfg.reminders = [
        MagicMock(trigger="boot", enabled=True, message="Welcome")
    ]

    def smart_open(path, *args, **kwargs):
        if "boot_id" in str(path) or "proc" in str(path):
            return mock_open(read_data="boot-stable")()
        return open(path, *args, **kwargs)   # real open for state yaml

    with patch("purposeos.daemon.scheduler.open", side_effect=smart_open):
        build_scheduler(empty_cfg, Path("fake.db"), is_initial_start=True)
        sched = build_scheduler(empty_cfg, Path("fake.db"), is_initial_start=True)

    assert sched.get_job("reminder_0") is None

# ─────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────

@freeze_time("2025-03-15 13:45:00+01:00")
def test_interval_resumes_from_persisted_start_date(tmp_state, empty_cfg):
    """Interval trigger uses the start_date stored in scheduler_state.yaml."""
    last_run = "2025-03-15T10:15:00+01:00"
    tmp_state.write_text(yaml.dump({"action_0": last_run}))

    empty_cfg.actions = [
        MagicMock(
            trigger="interval_minutes", trigger_value=30,
            enabled=True, action_type="test", target="test",
        )
    ]
    sched = build_scheduler(empty_cfg, Path("fake.db"))
    job = sched.get_job("action_0")
    assert job is not None
    assert job.trigger.start_date == datetime.fromisoformat(last_run)

def test_state_file_created_after_build(tmp_state, empty_cfg):
    """build_scheduler() writes a scheduler_state.yaml on first run."""
    empty_cfg.actions = [
        MagicMock(
            trigger="interval_minutes", trigger_value=10,
            enabled=True, action_type="test", target="test",
        )
    ]
    build_scheduler(empty_cfg, Path("fake.db"))
    assert tmp_state.exists()
    data = yaml.safe_load(tmp_state.read_text())
    assert "action_0" in data

# ─────────────────────────────────────────────────────────────────
# Enabled flag
# ─────────────────────────────────────────────────────────────────

def test_disabled_reminder_not_scheduled(tmp_state, empty_cfg):
    """Reminders with enabled=False are not added to the scheduler."""
    empty_cfg.reminders = [
        MagicMock(trigger="daily", trigger_value="09:00", enabled=False, message="Skip me")
    ]
    sched = build_scheduler(empty_cfg, Path("fake.db"))
    assert sched.get_job("reminder_0") is None

def test_disabled_action_not_scheduled(tmp_state, empty_cfg):
    """Actions with enabled=False are not added to the scheduler."""
    empty_cfg.actions = [
        MagicMock(
            trigger="interval_minutes", trigger_value=30,
            enabled=False, action_type="test", target="test",
        )
    ]
    sched = build_scheduler(empty_cfg, Path("fake.db"))
    assert sched.get_job("action_0") is None