"""
cli/parser.py — Argument parser, command dispatch table, and entry point

No business logic lives here. This file:
  1. Defines the full CLI surface via build_parser()
  2. Maps command names to handler functions in _COMMAND_MAP
  3. Provides main() which dispatches to the right handler

All handler functions are imported from their respective cmd modules.
"""

from __future__ import annotations

import argparse

from purposeos.cli._output import CY, DI, B, R
from purposeos.cli.action_cmds import cmd_actions
from purposeos.cli.daemon_cmds import (
    cmd_disable,
    cmd_enable,
    cmd_logs,
    cmd_reload,
    cmd_restart,
    cmd_start,
    cmd_status,
    cmd_stop,
)
from purposeos.cli.gui_cmds import cmd_gui, cmd_quicknote
from purposeos.cli.meta_cmds import cmd_uninstall, cmd_update, cmd_version
from purposeos.cli.notes_cmds import cmd_notes
from purposeos.cli.reminder_cmds import cmd_reminders
from purposeos.cli.stats_cmds import cmd_stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adctl",
        description=f"{B}{CY}PurposeOS{R} daemon control tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"  {DI}Examples:{R}\n"
            f"  adctl start\n"
            f"  adctl status\n"
            f"  adctl reminders list\n"
            f'  adctl reminders add --message "Drink water" --every 60 --urgency low\n'
            f'  adctl reminders add --message "Stand up" --at 14:00\n'
            f"  adctl reminders remove 2\n"
            f"  adctl actions add --type open_app --target firefox --at 09:00\n"
            f"  adctl actions remove 1\n"
            f"  adctl stats today\n"
            f"  adctl notes new\n"
            f"  adctl gui\n"
            f"  adctl gui --notes\n"
            f"  adctl update\n"
            f"  adctl uninstall\n"
            f"  adctl version\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start the daemon")
    sub.add_parser("stop", help="Stop the daemon")
    sub.add_parser("restart", help="Restart the daemon")
    sub.add_parser("reload", help="Live-reload config (SIGHUP)")
    sub.add_parser("status", help="Show daemon status")
    sub.add_parser("enable", help="Enable daemon at login (systemd)")
    sub.add_parser("disable", help="Disable daemon at login")

    gui_p = sub.add_parser("gui", help="Open the GUI")
    gui_p.add_argument("--notes", action="store_true", help="Open directly to the Notes tab")

    sub.add_parser("quicknote", help="Open the quick-note floating window (Ctrl+Shift+P)")
    sub.add_parser("update", help="Sync source updates into the installed package")
    sub.add_parser("uninstall", help="Remove PurposeOS completely")
    sub.add_parser("version", help="Show installed version")

    logs_p = sub.add_parser("logs", help="Show recent log lines")
    logs_p.add_argument("-n", "--lines", type=int, default=50, help="Number of lines (default 50)")

    # ── Reminders ─────────────────────────────────────────────────
    rem_p = sub.add_parser("reminders", help="Manage reminders")
    rem_sub = rem_p.add_subparsers(dest="reminders_cmd")
    rem_sub.add_parser("list", help="List all reminders")

    rem_add = rem_sub.add_parser("add", help="Add a reminder")
    rem_add.add_argument("--message", required=True, help="Reminder message text")
    rem_add.add_argument("--title", default="Reminder", help="Overlay title (default: Reminder)")
    rem_add.add_argument("--urgency", default="normal", choices=["low", "normal", "critical"])
    rem_add.add_argument("--sound", default=None, help="Sound name or path (e.g. bell)")
    rem_add.add_argument(
        "--no-overlay",
        action="store_true",
        help="Use standard notification instead of full-screen overlay",
    )
    rem_add.add_argument(
        "--close", type=int, default=30, help="Auto-close seconds for non-critical (default: 30)"
    )
    trig_grp = rem_add.add_mutually_exclusive_group()
    trig_grp.add_argument("--at", metavar="HH:MM", help="Daily at time, e.g. 09:00")
    trig_grp.add_argument("--every", metavar="MINS", help="Every N minutes, e.g. 90")
    trig_grp.add_argument("--day", metavar="DAY", help="Weekly on day, e.g. mon")

    rem_rm = rem_sub.add_parser("remove", help="Remove a reminder by number")
    rem_rm.add_argument("index", type=int, help="Reminder number from 'adctl reminders list'")
    rem_en = rem_sub.add_parser("enable", help="Enable a reminder")
    rem_en.add_argument("index", type=int)
    rem_dis = rem_sub.add_parser("disable", help="Disable a reminder without deleting it")
    rem_dis.add_argument("index", type=int)

    # ── Actions ───────────────────────────────────────────────────
    act_p = sub.add_parser("actions", help="Manage actions")
    act_sub = act_p.add_subparsers(dest="actions_cmd")
    act_sub.add_parser("list", help="List all actions")

    act_add = act_sub.add_parser("add", help="Add an action")
    act_add.add_argument(
        "--type",
        required=True,
        choices=["open_file", "open_app", "run_command", "open_url", "show_notification"],
        help="Action type",
    )
    act_add.add_argument("--target", required=True, help="File path / app name / command / URL")
    atrig = act_add.add_mutually_exclusive_group()
    atrig.add_argument("--at", metavar="HH:MM", help="Daily at time")
    atrig.add_argument("--every", metavar="MINS", help="Every N minutes")
    atrig.add_argument("--day", metavar="DAY", help="Weekly on day")

    act_rm = act_sub.add_parser("remove", help="Remove an action by number")
    act_rm.add_argument("index", type=int)
    act_en = act_sub.add_parser("enable", help="Enable an action")
    act_en.add_argument("index", type=int)
    act_dis = act_sub.add_parser("disable", help="Disable an action")
    act_dis.add_argument("index", type=int)

    # ── Stats ─────────────────────────────────────────────────────
    stats_p = sub.add_parser("stats", help="Show usage statistics")
    stats_sub = stats_p.add_subparsers(dest="stats_cmd")
    stats_sub.add_parser("today", help="App usage today")
    stats_sub.add_parser("week", help="App usage this week")
    stats_sub.add_parser("notifications", help="Notification interaction stats")
    stats_sub.add_parser("diagnose", help="Test window detection + show DB status")

    range_p = stats_sub.add_parser("range", help="App usage for a date range")
    range_p.add_argument("start", help="Start date YYYY-MM-DD")
    range_p.add_argument("end", help="End date YYYY-MM-DD")

    app_p = stats_sub.add_parser("app", help="Per-app daily breakdown")
    app_p.add_argument("app_name", help="App name to look up")
    app_p.add_argument("--days", type=int, default=7, help="Number of days (default 7)")

    # ── Notes ─────────────────────────────────────────────────────
    notes_p = sub.add_parser("notes", help="Manage notes")
    notes_sub = notes_p.add_subparsers(dest="notes_cmd")
    notes_sub.add_parser("list", help="List all notes")
    notes_sub.add_parser("new", help="Create a new note in the terminal editor")

    edit_p = notes_sub.add_parser("edit", help="Edit a note by index")
    edit_p.add_argument("index", type=int)
    show_p = notes_sub.add_parser("show", help="Print a note to stdout")
    show_p.add_argument("index", type=int)
    del_p = notes_sub.add_parser("delete", help="Delete a note by index")
    del_p.add_argument("index", type=int)

    return parser


# ── Command dispatch ──────────────────────────────────────────────

_COMMAND_MAP = {
    "start": cmd_start,
    "stop": cmd_stop,
    "restart": cmd_restart,
    "reload": cmd_reload,
    "status": cmd_status,
    "logs": cmd_logs,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "reminders": cmd_reminders,
    "actions": cmd_actions,
    "stats": cmd_stats,
    "notes": cmd_notes,
    "gui": cmd_gui,
    "quicknote": cmd_quicknote,
    "update": cmd_update,
    "uninstall": cmd_uninstall,
    "version": cmd_version,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    fn = _COMMAND_MAP.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
