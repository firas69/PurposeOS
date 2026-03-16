"""
test_config_i18n.py — Tests for purposeos.core.config and purposeos.i18n.

All filesystem operations use tmp_path. Module-level state in i18n is
reset before and after every i18n test via the reset_i18n fixture.
"""
import os
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

import purposeos.core.config as config
import purposeos.i18n as i18n
from purposeos.i18n import t, set_language, get_language, is_rtl


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_config(monkeypatch, tmp_path):
    """
    Redirect every config path constant to tmp_path so no test touches
    the real ~/.config/purposeos/ directory.
    """
    fake_home   = tmp_path / "home"
    # Updated to new PurposeOS runtime directory convention
    config_dir  = fake_home / ".config"  / "purposeos"
    data_dir    = fake_home / ".local"   / "share" / "purposeos"

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr(os.path, "expanduser", lambda p: (
        str(fake_home) if p == "~" else
        str(fake_home / p[2:].lstrip("/")) if p.startswith("~/") else p
    ))

    monkeypatch.setattr(config, "CONFIG_DIR",  config_dir)
    monkeypatch.setattr(config, "CONFIG_PATH", config_dir / "config.yaml")
    monkeypatch.setattr(config, "DATA_DIR",    data_dir)
    monkeypatch.setattr(config, "LOGS_DIR",    data_dir / "logs")
    monkeypatch.setattr(config, "NOTES_DIR",   config_dir / "notes")
    monkeypatch.setattr(config, "PID_FILE",    data_dir  / "daemon.pid")


@pytest.fixture
def reset_i18n():
    """Capture and restore i18n module-level state around each test."""
    saved_lang  = i18n._current_lang
    saved_trans = {k: dict(v) for k, v in i18n._translations.items()}
    yield
    i18n._current_lang   = saved_lang
    i18n._translations   = saved_trans


# ─────────────────────────────────────────────────────────────────
# config.py — loading
# ─────────────────────────────────────────────────────────────────

def test_load_creates_skeleton_when_missing():
    assert not config.CONFIG_PATH.exists()
    cfg = config.load_config()
    assert config.CONFIG_PATH.exists()
    text = config.CONFIG_PATH.read_text(encoding="utf-8")
    assert text.strip().startswith("# PurposeOS daemon configuration")
    assert isinstance(cfg, config.DaemonConfig)
    assert cfg.settings.log_level == "INFO"


def test_load_parses_valid_yaml():
    content = {
        "settings": {"log_level": "DEBUG", "language": "ar"},
        "reminders": [{
            "message": "Drink water",
            "trigger": "interval_minutes",
            "trigger_value": 45,
            "sound_file": "bell",
        }],
        "actions": [{"action_type": "open_url", "target": "https://example.com"}],
    }
    config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(yaml.dump(content), encoding="utf-8")

    cfg = config.load_config()
    assert cfg.settings.log_level == "DEBUG"
    assert cfg.settings.language  == "ar"
    assert len(cfg.reminders) == 1
    assert cfg.reminders[0].message       == "Drink water"
    assert cfg.reminders[0].trigger_value == 45
    assert cfg.reminders[0].sound_file    == "bell"
    assert cfg.actions[0].target == "https://example.com"


def test_load_coerces_null_sections_to_empty_lists():
    content = {"settings": {}, "reminders": None, "actions": None}
    config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(yaml.dump(content), encoding="utf-8")

    cfg = config.load_config()
    assert cfg.reminders == []
    assert cfg.actions   == []


# ─────────────────────────────────────────────────────────────────
# config.py — parsing edge cases
# ─────────────────────────────────────────────────────────────────

def test_parse_action_normalises_double_home_path():
    username = os.path.basename(os.path.expanduser("~"))
    bad_path = f"~/home/{username}/Documents/todo.txt"
    action = config._parse_action({"action_type": "open_file", "target": bad_path})
    assert f"/home/{username}/home/{username}/" not in action.target
    assert "Documents/todo.txt" in action.target


def test_parse_settings_language_defaults_to_en():
    s = config._parse_settings({})
    assert s.language == "en"


def test_parse_settings_language_explicit():
    s = config._parse_settings({"language": "fr"})
    assert s.language == "fr"


def test_parse_settings_language_empty_string_falls_back():
    s = config._parse_settings({"language": ""})
    assert s.language == "en"


# ─────────────────────────────────────────────────────────────────
# config.py — write / round-trip
# ─────────────────────────────────────────────────────────────────

def test_write_config_round_trip():
    cfg = config.DaemonConfig(
        settings=config.SettingsConfig(
            log_level="WARNING",
            language="ru",
            notes_dir="~/special-notes",
        ),
        reminders=[config.ReminderConfig(
            message="Stand up",
            trigger="interval_minutes",
            trigger_value=30,
            urgency="critical",
        )],
        actions=[config.ActionConfig(
            action_type="run_command",
            target="echo hello",
            notification_title="Ran",
        )],
    )
    config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.write_config(cfg)
    loaded = config.load_config()

    assert asdict(loaded.settings) == asdict(cfg.settings)
    assert loaded.reminders[0].message       == "Stand up"
    assert loaded.reminders[0].trigger_value == 30
    assert loaded.actions[0].notification_title == "Ran"


def test_get_notes_dir_respects_override():
    cfg = config.load_config()
    cfg.settings.notes_dir = "~/custom-notes"
    config.write_config(cfg)
    result = config.get_notes_dir()
    assert "custom-notes" in str(result)
    assert result.exists()


def test_get_notes_dir_falls_back_to_default():
    cfg = config.load_config()
    cfg.settings.notes_dir = ""
    config.write_config(cfg)
    result = config.get_notes_dir()
    assert result == config.CONFIG_DIR / "notes"


# ─────────────────────────────────────────────────────────────────
# i18n — translation lookup
# ─────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("reset_i18n")
def test_t_returns_default_when_key_missing():
    assert t("nonexistent.deep.key", "My Default") == "My Default"


@pytest.mark.usefixtures("reset_i18n")
def test_t_falls_back_to_english_for_missing_key_in_active_lang():
    i18n._translations["fr"] = {"app": {"name": "PurposeOS"}}
    set_language("fr")
    result = t("navigation.reminders", "Reminders")
    assert result 


@pytest.mark.usefixtures("reset_i18n")
def test_t_resolves_nested_dot_notation():
    i18n._translations["en"] = {
        "gui":    {"title": "Main Window"},
        "errors": {"not_found": "Item not found"},
    }
    assert t("gui.title")         == "Main Window"
    assert t("errors.not_found")  == "Item not found"


# ─────────────────────────────────────────────────────────────────
# i18n — language switching
# ─────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("reset_i18n")
def test_set_language_switches_language():
    set_language("fr")
    assert get_language() == "fr"
    set_language("en")
    assert get_language() == "en"


@pytest.mark.usefixtures("reset_i18n")
def test_set_language_unknown_falls_back_to_english():
    set_language("xx")
    assert get_language() == "en"


@pytest.mark.usefixtures("reset_i18n")
def test_set_language_triggers_disk_reload_for_missing_lang(monkeypatch, tmp_path):
    fake_dir = tmp_path / "i18n"
    fake_dir.mkdir()
    (fake_dir / "de.json").write_text('{"hello": "Hallo"}', encoding="utf-8")

    monkeypatch.setattr(i18n, "_get_i18n_dir", lambda: fake_dir)
    i18n._translations.pop("de", None)

    set_language("de")
    assert get_language() == "de"
    assert i18n._translations.get("de", {}).get("hello") == "Hallo"


# ─────────────────────────────────────────────────────────────────
# i18n — RTL
# ─────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("reset_i18n")
def test_is_rtl_only_true_for_arabic():
    for lang in ("en", "fr", "ru"):
        set_language(lang)
        assert is_rtl() is False, f"Expected LTR for {lang}"
    set_language("ar")
    assert is_rtl() is True