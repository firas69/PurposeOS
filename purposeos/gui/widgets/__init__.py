"""
gui/__init__.py — PurposeOS GUI sub-package

Re-exports main() so that the existing adctl lazy import continues to work:

    from purposeos.gui import main as gui_main
    gui_main(start_tab=...)

Internal layout:
    _style.py          — _STYLESHEET constant
    _helpers.py        — t(), is_rtl(), _apply_rtl(), _make_shortcut(),
                          _friendly_trigger(), _normalise_path(), _DOW_NAMES
                          and the i18n import block with fallbacks
    _config_bridge.py  — _load_raw_config(), _save_raw_config(),
                          _reload_daemon(), _daemon_status()
    dialogs/reminder.py — _make_reminder_dialog()
    dialogs/action.py   — _make_action_dialog(), _check_action_status(),
                          _type_label(), _type_key()
    dialogs/note.py     — _make_note_dialog()
    widgets/stats_chart.py — _make_stats_widget()
    main.py             — PurposeOSWindow, main()
    quicknote.py        — standalone floating note window (unchanged)
"""

from purposeos.gui.main import main  # noqa: F401

__all__ = ["main"]
