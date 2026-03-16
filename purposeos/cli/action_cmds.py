"""
cli/action_cmds.py — Action management commands

Handles adctl actions list/add/remove/enable/disable.
Config read/write goes through _config_io; daemon reload
goes through daemon_cmds.cmd_reload.
"""

from __future__ import annotations

from purposeos.cli._config_io import _load_cfg_safe, _save_cfg_safe
from purposeos.cli._output import CY, GR, RE, YE, B, R, _err, _ok
from purposeos.cli.daemon_cmds import cmd_reload


def cmd_actions(args) -> None:
    sub = getattr(args, "actions_cmd", None)

    if sub == "list" or sub is None:
        cfg = _load_cfg_safe()
        actions = cfg["actions"]
        if not actions:
            print(f"  {YE}No actions configured.{R}")
            return
        print(f"\n  {B}{'#':<4} {'Type':<18} {'Target':<30} {'Trigger':<20} {'On/Off'}{R}")
        print("  " + "─" * 76)
        for i, a in enumerate(actions, 1):
            tv = a.get("trigger_value", "")
            trig = f"{a.get('trigger', '')} {tv}".strip()
            enabled = f"{GR}on{R}" if a.get("enabled", True) else f"{RE}off{R}"
            target = str(a.get("target", ""))[:28]
            print(
                f"  {str(i):<4} {CY}{str(a.get('action_type', '')):<18}{R} "
                f"{target:<30} {trig:<20} {enabled}"
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
            "action_type": args.type,
            "target": args.target,
            "trigger": trigger,
            "enabled": True,
        }
        if trigger_value is not None:
            entry["trigger_value"] = trigger_value

        cfg["actions"].append(entry)
        _save_cfg_safe(cfg)
        cmd_reload(args)
        _ok(f"Action added: {args.type} → {args.target}")

    elif sub == "remove":
        cfg = _load_cfg_safe()
        idx = args.index - 1
        if idx < 0 or idx >= len(cfg["actions"]):
            _err(f"No action #{args.index}. Use 'adctl actions list' to see indices.")
            return
        removed = cfg["actions"].pop(idx)
        _save_cfg_safe(cfg)
        cmd_reload(args)
        _ok(f"Removed action: {removed.get('action_type', '')} → {removed.get('target', '')}")

    elif sub == "enable":
        _toggle_action(args.index, True)

    elif sub == "disable":
        _toggle_action(args.index, False)


def _toggle_action(index: int, enabled: bool) -> None:
    cfg = _load_cfg_safe()
    idx = index - 1
    if idx < 0 or idx >= len(cfg["actions"]):
        _err(f"No action #{index}.")
        return
    cfg["actions"][idx]["enabled"] = enabled
    _save_cfg_safe(cfg)
    state = "enabled" if enabled else "disabled"
    _ok(f"Action #{index} {state}.")
