"""
cli/__init__.py — PurposeOS CLI sub-package

Re-exports main() and build_parser() so the package entry point
and test imports continue to work:

    from purposeos.cli import main
    from purposeos.cli.parser import build_parser

Internal layout:
    _output.py       — ANSI colours, _ok/_err/_info
    _config_io.py    — _load_cfg_safe, _save_cfg_safe
    daemon_cmds.py   — start/stop/restart/reload/status/logs/enable/disable
    stats_cmds.py    — cmd_stats, _stats_diagnose
    notes_cmds.py    — cmd_notes
    reminder_cmds.py — cmd_reminders, _toggle_reminder
    action_cmds.py   — cmd_actions, _toggle_action
    gui_cmds.py      — cmd_gui, cmd_quicknote
    meta_cmds.py     — cmd_update, cmd_uninstall, cmd_version
    parser.py        — build_parser, _COMMAND_MAP, main
"""

from purposeos.cli.parser import build_parser, main  # noqa: F401

__all__ = ["main", "build_parser"]
