"""
test_adctl.py — Tests for purposeos.cli command handlers.

Calls handler functions directly via argparse, using tmp_path for config
isolation. No systemd, no real processes, no PySide6 imported.
"""
import sys
import yaml
import pytest
from unittest.mock import MagicMock

# Import the new modular CLI handlers
from purposeos.cli import parser
from purposeos.cli import daemon_cmds
from purposeos.cli import reminder_cmds
from purposeos.cli import action_cmds
from purposeos.cli import gui_cmds
from purposeos.cli import notes_cmds
from purposeos.cli import meta_cmds


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def args(*cmd_args):
    """Parse CLI args into a Namespace using the real argument parser."""
    return parser.build_parser().parse_args(list(cmd_args))


# ─────────────────────────────────────────────────────────────────
# Autouse fixture — applied to every test in this file
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_env(monkeypatch, tmp_path):
    """
    Isolate every test from the real filesystem, OS signals, and subprocesses.
    Returns the tmp config path so individual tests can write YAML into it.
    """
    # 1. Block real signals
    monkeypatch.setattr("os.kill", MagicMock(), raising=False)

    # 2. Block real subprocesses
    mock_run = MagicMock()
    mock_run.returncode = 0
    monkeypatch.setattr("subprocess.run",  MagicMock(return_value=mock_run))
    monkeypatch.setattr("subprocess.Popen", MagicMock())

    # 3. Fake PID file
    mock_pid = MagicMock()
    mock_pid.read_text.return_value = "9999"
    monkeypatch.setattr("purposeos.cli.daemon_cmds.PID_FILE", mock_pid, raising=False)
    monkeypatch.setattr("purposeos.core.config.PID_FILE", mock_pid, raising=False)

    # 4. Redirect path constants to tmp_path
    monkeypatch.setattr("purposeos.cli.daemon_cmds.LOGS_DIR", tmp_path, raising=False)
    monkeypatch.setattr("purposeos.core.config.LOGS_DIR", tmp_path, raising=False)
    monkeypatch.setattr("purposeos.core.config.DATA_DIR", tmp_path, raising=False)

    # 5. Redirect CONFIG_PATH so YAML reads/writes go to tmp_path
    cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr("purposeos.core.config.CONFIG_PATH", cfg_path, raising=False)
    monkeypatch.setattr("purposeos.cli._config_io.CONFIG_PATH", cfg_path, raising=False)

    return cfg_path


# ─────────────────────────────────────────────────────────────────
# Daemon lifecycle (skipped — requires systemd)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="requires systemd")
def test_cmd_start():
    daemon_cmds.cmd_start(args("start"))


@pytest.mark.skip(reason="requires systemd")
def test_cmd_stop():
    daemon_cmds.cmd_stop(args("stop"))


# ─────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────

def test_status_running(capfd):
    daemon_cmds.cmd_status(args("status"))
    out, _ = capfd.readouterr()
    assert "running" in out.lower()
    assert "9999" in out


def test_status_stopped(monkeypatch, capfd):
    monkeypatch.setattr("os.kill", MagicMock(side_effect=ProcessLookupError))
    daemon_cmds.cmd_status(args("status"))
    out, _ = capfd.readouterr()
    assert "stopped" in out.lower()


# ─────────────────────────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────────────────────────

def test_logs_pure_python_fallback(tmp_path, monkeypatch, capfd):
    log_file = tmp_path / "daemon.log"
    log_file.write_text("L1\nL2\nL3\nL4\nL5\n", encoding="utf-8")
    monkeypatch.setattr("subprocess.run", MagicMock(side_effect=Exception("blocked")))
    daemon_cmds.cmd_logs(args("logs", "-n", "3"))
    out, _ = capfd.readouterr()
    assert "L3" in out
    assert "L4" in out
    assert "L5" in out


# ─────────────────────────────────────────────────────────────────
# Reminders
# ─────────────────────────────────────────────────────────────────

def test_reminders_list_empty(capfd):
    reminder_cmds.cmd_reminders(args("reminders", "list"))
    out, _ = capfd.readouterr()
    assert "No reminders" in out


def test_reminders_add_interval(mock_env):
    reminder_cmds.cmd_reminders(args(
        "reminders", "add",
        "--message", "Drink water",
        "--every", "60",
        "--urgency", "low",
    ))
    cfg = yaml.safe_load(mock_env.read_text())
    assert len(cfg["reminders"]) == 1
    r = cfg["reminders"][0]
    assert r["message"] == "Drink water"
    assert r["trigger"] == "interval_minutes"
    assert r["trigger_value"] == 60


def test_reminders_add_daily(mock_env):
    reminder_cmds.cmd_reminders(args(
        "reminders", "add",
        "--message", "Stand up",
        "--title", "Stand Up",
        "--at", "14:00",
    ))
    cfg = yaml.safe_load(mock_env.read_text())
    r = cfg["reminders"][0]
    assert r["trigger"] == "daily"
    assert r["trigger_value"] == "14:00"


def test_reminders_list_populated(mock_env, capfd):
    reminder_cmds.cmd_reminders(args("reminders", "add", "--message", "Stretch", "--title", "Stretch Break", "--at", "10:00"))
    capfd.readouterr()
    reminder_cmds.cmd_reminders(args("reminders", "list"))
    out, _ = capfd.readouterr()
    assert "Stretch Break" in out


def test_reminders_remove(mock_env):
    reminder_cmds.cmd_reminders(args("reminders", "add", "--message", "Delete me", "--every", "10"))
    reminder_cmds.cmd_reminders(args("reminders", "remove", "1"))
    cfg = yaml.safe_load(mock_env.read_text())
    assert len(cfg["reminders"]) == 0


def test_reminders_enable_disable(mock_env):
    reminder_cmds.cmd_reminders(args("reminders", "add", "--message", "Toggle", "--every", "10"))
    reminder_cmds.cmd_reminders(args("reminders", "disable", "1"))
    assert yaml.safe_load(mock_env.read_text())["reminders"][0]["enabled"] is False
    reminder_cmds.cmd_reminders(args("reminders", "enable", "1"))
    assert yaml.safe_load(mock_env.read_text())["reminders"][0]["enabled"] is True


# ─────────────────────────────────────────────────────────────────
# Actions
# ─────────────────────────────────────────────────────────────────

def test_actions_list_empty(capfd):
    action_cmds.cmd_actions(args("actions", "list"))
    out, _ = capfd.readouterr()
    assert "No actions" in out


def test_actions_add(mock_env):
    action_cmds.cmd_actions(args("actions", "add", "--type", "open_app", "--target", "firefox", "--at", "09:00"))
    cfg = yaml.safe_load(mock_env.read_text())
    assert len(cfg["actions"]) == 1
    a = cfg["actions"][0]
    assert a["action_type"] == "open_app"


def test_actions_list_populated(mock_env, capfd):
    action_cmds.cmd_actions(args("actions", "add", "--type", "open_app", "--target", "firefox"))
    capfd.readouterr()
    action_cmds.cmd_actions(args("actions", "list"))
    out, _ = capfd.readouterr()
    assert "open_app" in out


def test_actions_remove(mock_env):
    action_cmds.cmd_actions(args("actions", "add", "--type", "open_app", "--target", "firefox"))
    action_cmds.cmd_actions(args("actions", "remove", "1"))
    cfg = yaml.safe_load(mock_env.read_text())
    assert len(cfg["actions"]) == 0


def test_actions_enable_disable(mock_env):
    action_cmds.cmd_actions(args("actions", "add", "--type", "open_app", "--target", "firefox"))
    action_cmds.cmd_actions(args("actions", "disable", "1"))
    assert yaml.safe_load(mock_env.read_text())["actions"][0]["enabled"] is False
    action_cmds.cmd_actions(args("actions", "enable", "1"))
    assert yaml.safe_load(mock_env.read_text())["actions"][0]["enabled"] is True


# ─────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────

def test_cmd_gui_calls_main(monkeypatch):
    mock_gui = MagicMock()
    monkeypatch.setitem(sys.modules, "purposeos.gui", mock_gui)
    gui_cmds.cmd_gui(args("gui"))
    mock_gui.main.assert_called_once_with(start_tab=None)


def test_cmd_gui_notes_tab(monkeypatch):
    mock_gui = MagicMock()
    monkeypatch.setitem(sys.modules, "purposeos.gui", mock_gui)
    gui_cmds.cmd_gui(args("gui", "--notes"))
    mock_gui.main.assert_called_once_with(start_tab="Notes")


# ─────────────────────────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────────────────────────

def test_cmd_notes_list(monkeypatch, capfd):
    mock_notes = MagicMock()
    mock_notes.cmd_notes_list.return_value = "Note 1\nNote 2"
    mock_notes.list_notes.return_value = []
    # Reflects the new purposeos.notes package
    monkeypatch.setitem(sys.modules, "purposeos.notes", mock_notes)
    monkeypatch.setitem(sys.modules, "purposeos.notes.cli", mock_notes)
    
    notes_cmds.cmd_notes(args("notes", "list"))
    out, _ = capfd.readouterr()
    assert "Note 1" in out


# ─────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────

def test_cmd_update_no_manifest(tmp_path, monkeypatch, capfd):
    monkeypatch.setattr(meta_cmds, "_manifest_dir", lambda: tmp_path, raising=False)
    meta_cmds.cmd_update(args("update"))
    _, err = capfd.readouterr()
    assert "Source path not recorded" in err or "not recorded" in err


def test_cmd_update_missing_update_sh(tmp_path, monkeypatch, capfd):
    source_path_file = tmp_path / "source_path"
    source_path_file.write_text(str(tmp_path), encoding="utf-8")
    monkeypatch.setattr(meta_cmds, "_manifest_dir", lambda: tmp_path, raising=False)
    meta_cmds.cmd_update(args("update"))
    _, err = capfd.readouterr()
    assert "update.sh not found" in err or "not found" in err


def test_cmd_update_calls_update_sh(tmp_path, monkeypatch):
    fake_update = tmp_path / "update.sh"
    fake_update.write_text("#!/usr/bin/env bash\nexit 0\n")
    fake_update.chmod(0o755)

    source_path_file = tmp_path / "source_path"
    source_path_file.write_text(str(tmp_path), encoding="utf-8")
    monkeypatch.setattr(meta_cmds, "_manifest_dir", lambda: tmp_path, raising=False)

    mock_run = MagicMock()
    mock_run.returncode = 0
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=mock_run))

    with pytest.raises(SystemExit) as exc_info:
        meta_cmds.cmd_update(args("update"))
    assert exc_info.value.code == 0


# ─────────────────────────────────────────────────────────────────
# Uninstall
# ─────────────────────────────────────────────────────────────────

def test_cmd_uninstall_no_manifest(tmp_path, monkeypatch, capfd):
    monkeypatch.setattr(meta_cmds, "_manifest_dir", lambda: tmp_path, raising=False)
    meta_cmds.cmd_uninstall(args("uninstall"))
    _, err = capfd.readouterr()
    assert "not found" in err.lower() or "Uninstaller not found" in err


def test_cmd_uninstall_execs_script(tmp_path, monkeypatch):
    fake_uninstall = tmp_path / "uninstall.sh"
    fake_uninstall.write_text("#!/usr/bin/env bash\nexit 0\n")
    fake_uninstall.chmod(0o755)
    monkeypatch.setattr(meta_cmds, "_manifest_dir", lambda: tmp_path, raising=False)

    execv_calls = []
    monkeypatch.setattr("os.execv", lambda path, argv: execv_calls.append((path, argv)))

    meta_cmds.cmd_uninstall(args("uninstall"))

    assert len(execv_calls) == 1
    called_path, called_argv = execv_calls[0]
    assert called_path == "/bin/bash"
    assert str(fake_uninstall) in called_argv


# ─────────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────────

def test_cmd_version_prints_version(capfd):
    meta_cmds.cmd_version(args("version"))
    out, _ = capfd.readouterr()
    assert "PurposeOS" in out
    assert "v" in out


def test_cmd_version_handles_missing_version(monkeypatch, capfd):
    import purposeos as _pkg
    monkeypatch.delattr(_pkg, "__version__", raising=False)
    meta_cmds.cmd_version(args("version"))
    out, _ = capfd.readouterr()
    assert "PurposeOS" in out