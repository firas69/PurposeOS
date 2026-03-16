"""
cli/reminder_cmds.py — Reminder management commands

Handles adctl reminders list/add/remove/enable/disable.
Config read/write goes through _config_io; daemon reload
goes through daemon_cmds.cmd_reload.
"""

from __future__ import annotations

from purposeos.cli._config_io import _load_cfg_safe, _save_cfg_safe
from purposeos.cli._output import CY, GR, RE, YE, B, R, _err, _ok
from purposeos.cli.daemon_cmds import cmd_reload


def cmd_reminders(args) -> None:
    sub = getattr(args, "reminders_cmd", None)

    if sub == "list" or sub is None:
        cfg = _load_cfg_safe()
        reminders = cfg["reminders"]
        if not reminders:
            print(f"  {YE}No reminders configured.{R}")
            return
        print(f"\n  {B}{'#':<4} {'Title':<22} {'Trigger':<22} {'Urgency':<10} {'On/Off'}{R}")
        print("  " + "─" * 68)
        for i, r in enumerate(reminders, 1):
            tv = r.get("trigger_value", "")
            trig = f"{r.get('trigger', '')} {tv}".strip()
            enabled = f"{GR}on{R}" if r.get("enabled", True) else f"{RE}off{R}"
            print(
                f"  {str(i):<4} {CY}{str(r.get('title', '')):<22}{R} "
                f"{trig:<22} {r.get('urgency', 'normal'):<10} {enabled}"
            )
        print()

    elif sub == "add":
        cfg = _load_cfg_safe()
        if args.at:
            trigger = "daily"
            trigger_value = args.at
        elif args.every:
            trigger = "interval_minutes"
            trigger_value = int(args.every)
        elif args.day:
            trigger = "weekly"
            trigger_value = args.day
        else:
            trigger = "boot"
            trigger_value = None

        entry = {
            "message": args.message,
            "title": args.title,
            "trigger": trigger,
            "urgency": args.urgency,
            "screen_wide": not args.no_overlay,
            "auto_close_sec": args.close,
            "enabled": True,
        }
        if trigger_value is not None:
            entry["trigger_value"] = trigger_value
        if args.sound:
            entry["sound_file"] = args.sound

        cfg["reminders"].append(entry)
        _save_cfg_safe(cfg)
        cmd_reload(args)
        _ok(f'Reminder added: "{args.message}"')

    elif sub == "remove":
        cfg = _load_cfg_safe()
        idx = args.index - 1
        if idx < 0 or idx >= len(cfg["reminders"]):
            _err(f"No reminder #{args.index}. Use 'adctl reminders list' to see indices.")
            return
        removed = cfg["reminders"].pop(idx)
        _save_cfg_safe(cfg)
        cmd_reload(args)
        _ok(f'Removed reminder: "{removed.get("message", "")}"')

    elif sub == "enable":
        _toggle_reminder(args.index, True)

    elif sub == "disable":
        _toggle_reminder(args.index, False)


def _toggle_reminder(index: int, enabled: bool) -> None:
    cfg = _load_cfg_safe()
    idx = index - 1
    if idx < 0 or idx >= len(cfg["reminders"]):
        _err(f"No reminder #{index}.")
        return
    cfg["reminders"][idx]["enabled"] = enabled
    _save_cfg_safe(cfg)
    state = "enabled" if enabled else "disabled"
    _ok(f"Reminder #{index} {state}.")
