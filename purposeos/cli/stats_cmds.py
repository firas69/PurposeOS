"""
cli/stats_cmds.py — Stats display commands

Handles adctl stats today/week/range/notifications/app/diagnose.
The diagnose subcommand runs all three window-detection strategies live
and reports the DB state, useful for troubleshooting tracker issues.
"""

from __future__ import annotations

from purposeos.cli._output import CY, GR, RE, YE, B, R
from purposeos.core.config import DATA_DIR


def cmd_stats(args) -> None:
    from purposeos.data.stats import (
        stats_app_detail,
        stats_notifications,
        stats_range,
        stats_today,
        stats_week,
    )

    db_path = DATA_DIR / "tracker.db"
    sub = getattr(args, "stats_cmd", "today")

    if sub == "today" or sub is None:
        print(stats_today(db_path))
    elif sub == "week":
        print(stats_week(db_path))
    elif sub == "range":
        print(stats_range(db_path, args.start, args.end))
    elif sub == "notifications":
        print(stats_notifications(db_path))
    elif sub == "app":
        days = getattr(args, "days", 7)
        print(stats_app_detail(db_path, args.app_name, days))
    elif sub == "diagnose":
        _stats_diagnose(db_path)
    else:
        print(stats_today(db_path))


def _stats_diagnose(db_path) -> None:
    """Test each window-detection strategy and show what's in the DB."""
    import os
    import sqlite3

    print(f"\n  {B}{CY}PurposeOS Stats Diagnostics{R}\n")

    # 1. DB status
    if not db_path.exists():
        print(f"  {RE}✗ Tracker DB not found:{R} {db_path}")
        print("    → Is the daemon running? Try: adctl start\n")
    else:
        print(f"  {GR}✓ DB found:{R} {db_path}")
        try:
            with sqlite3.connect(str(db_path)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM app_sessions").fetchone()[0]
                unknown = conn.execute(
                    "SELECT COUNT(*) FROM app_sessions WHERE app_name='unknown'"
                ).fetchone()[0]
                known = total - unknown
                print(
                    f"    Total sessions: {CY}{total}{R}  |  "
                    f"known: {GR}{known}{R}  |  unknown: {RE}{unknown}{R}"
                )
                recent = conn.execute(
                    "SELECT app_name, started_at FROM app_sessions ORDER BY started_at DESC LIMIT 5"
                ).fetchall()
                if recent:
                    print(f"\n  {B}Last 5 sessions:{R}")
                    for row in recent:
                        print(f"    {row[1][:19]}  {CY}{row[0]}{R}")
        except Exception as e:
            print(f"  {RE}DB read error: {e}{R}")

    # 2. Environment
    print(f"\n  {B}Graphical session environment:{R}")
    for var in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
        val = os.environ.get(var, "")
        status = f"{GR}✓{R}" if val else f"{YE}✗{R}"
        print(f"    {status} {var}={val or '(not set)'}")

    # 3. Try each strategy live
    print(f"\n  {B}Window detection strategies:{R}")
    try:
        from purposeos.data.tracker.detection import (
            _full_env,
            _get_active_window_gnome_wayland,
            _get_active_window_wnck,
            _get_active_window_xdotool,
        )

        env = _full_env()
        for name, fn in [
            ("GNOME D-Bus (gdbus)", lambda: _get_active_window_gnome_wayland(env)),
            ("wnck (python3-wnck)", lambda: _get_active_window_wnck(env)),
            ("xdotool + xprop", lambda: _get_active_window_xdotool(env)),
        ]:
            try:
                app, title = fn()
                print(f"    {GR}✓{R} {name}: app={CY}{app}{R}  title={title[:40]}")
            except Exception as e:
                print(f"    {RE}✗{R} {name}: {e}")
    except ImportError as e:
        print(f"  {RE}Import error: {e}{R}")

    print()
