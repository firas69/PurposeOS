"""
data/stats.py — PurposeOS Statistics Query Engine

Single meaningful metric: per-reminder average response time, with a
this-week vs last-week trend so you can see whether you're engaging
faster or slower over time.

response_sec is written when the user clicks Done on a notification.
A lower average = you responded faster = higher focus.

All duration_sec / launch-count references removed.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
WHITE = "\033[37m"


def _col(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}"


def _fmt_sec(seconds: float) -> str:
    s = int(seconds)
    m, sec = divmod(s, 60)
    return f"{m}m {sec:02d}s" if m else f"{sec}s"


def _trend_symbol(this_week: float | None, last_week: float | None) -> str:
    """↓ faster (good), ↑ slower (bad), — no comparison data."""
    if this_week is None or last_week is None:
        return _col("  —", DIM)
    diff = this_week - last_week
    if abs(diff) < 2:  # < 2s difference: no meaningful change
        return _col("  ≈", DIM)
    if diff < 0:
        return _col(f"  ↓ {_fmt_sec(abs(diff))} faster", GREEN)
    return _col(f"  ↑ {_fmt_sec(diff)} slower", RED)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _db_exists(db_path: Path) -> bool:
    return db_path.exists()


# ---------------------------------------------------------------------------
# Core query — avg response time per reminder over a date range
# ---------------------------------------------------------------------------


def _query_response_times(db_path: Path, start: str, end: str) -> list[tuple[str, float, int]]:
    """
    Returns [(label, avg_response_sec, interaction_count), ...]
    Only rows where action='done' and response_sec is not null.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT
                  COALESCE(NULLIF(title,''), message, '(unknown)') AS label,
                  AVG(response_sec)  AS avg_sec,
                  COUNT(*)           AS interactions
               FROM notification_interactions
               WHERE action      = 'done'
                 AND response_sec IS NOT NULL
                 AND DATE(shown_at) >= ?
                 AND DATE(shown_at) <= ?
               GROUP BY label
               ORDER BY avg_sec ASC""",
            (start, end),
        ).fetchall()
    return [(r["label"], float(r["avg_sec"]), int(r["interactions"])) for r in rows]


# ---------------------------------------------------------------------------
# Public API (called by stats_cmds.py — signatures unchanged)
# ---------------------------------------------------------------------------


def stats_today(db_path: Path) -> str:
    """Today's reminder response times."""
    if not _db_exists(db_path):
        return _col("No tracking data found yet. Run the daemon first.", YELLOW)

    today = date.today().isoformat()
    rows = _query_response_times(db_path, today, today)

    if not rows:
        return _col(f"No reminder responses recorded today ({today}).", YELLOW)

    return _format_response_table(rows, f"Reminder Response Times — Today ({today})")


def stats_week(db_path: Path) -> str:
    """
    This week's per-reminder avg response time, with a trend vs last week.
    Lower avg = faster response = better focus.
    """
    if not _db_exists(db_path):
        return _col("No tracking data found yet.", YELLOW)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    last_start = week_start - timedelta(days=7)
    last_end = week_start - timedelta(days=1)

    this_week = _query_response_times(db_path, week_start.isoformat(), today.isoformat())
    last_week = {
        label: avg
        for label, avg, _ in _query_response_times(
            db_path, last_start.isoformat(), last_end.isoformat()
        )
    }

    if not this_week:
        return _col("No reminder responses recorded this week.", YELLOW)

    name_width = max(len(label) for label, _, _ in this_week)
    name_width = max(name_width, 12)
    width = name_width + 42

    lines = [
        _col(f"\n{'─' * width}", DIM),
        f"  {_col('Reminder Response Times — This Week (vs Last Week)', BOLD + WHITE)}",
        f"  {_col('Lower = faster response = better focus', DIM)}",
        _col(f"{'─' * width}", DIM),
        f"  {_col('Reminder', BOLD):<{name_width + 12}} "
        f"{_col('Avg', BOLD):<14} "
        f"{_col('Count', BOLD):<10} "
        f"{_col('Trend', BOLD)}",
        "  " + "─" * (width - 2),
    ]

    for label, avg_sec, count in this_week:
        trend = _trend_symbol(avg_sec, last_week.get(label))
        lines.append(
            f"  {_col(label, CYAN):<{name_width + len(CYAN) + len(RESET)}} "
            f"{_col(_fmt_sec(avg_sec), GREEN):<14} "
            f"{_col(str(count), DIM):<10}"
            f"{trend}"
        )

    lines.append(_col(f"{'─' * width}\n", DIM))
    return "\n".join(lines)


def stats_range(db_path: Path, start: str, end: str) -> str:
    if not _db_exists(db_path):
        return _col("No tracking data found yet.", YELLOW)

    rows = _query_response_times(db_path, start, end)
    if not rows:
        return _col(f"No reminder responses between {start} and {end}.", YELLOW)

    return _format_response_table(rows, f"Reminder Response Times — {start} to {end}")


def stats_app_detail(db_path: Path, app_name: str, days: int = 7) -> str:
    """Daily avg response time for a specific reminder (matched by title/message)."""
    if not _db_exists(db_path):
        return _col("No tracking data found yet.", YELLOW)

    end = date.today()
    start = end - timedelta(days=days - 1)

    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT
                  DATE(shown_at) AS day,
                  AVG(response_sec) AS avg_sec,
                  COUNT(*) AS interactions
               FROM notification_interactions
               WHERE action = 'done'
                 AND response_sec IS NOT NULL
                 AND (title LIKE ? OR message LIKE ?)
                 AND DATE(shown_at) >= ?
                 AND DATE(shown_at) <= ?
               GROUP BY day
               ORDER BY day DESC""",
            (f"%{app_name}%", f"%{app_name}%", start.isoformat(), end.isoformat()),
        ).fetchall()

    if not rows:
        return _col(f"No responses found for '{app_name}' in the last {days} days.", YELLOW)

    lines = [
        _col(f"\n{'─' * 46}", DIM),
        f"  {_col(f'{app_name} — Last {days} days', BOLD + WHITE)}",
        _col(f"{'─' * 46}", DIM),
    ]
    for row in rows:
        lines.append(
            f"  {row['day']}  "
            f"{_col(_fmt_sec(row['avg_sec']), GREEN):<18} "
            f"{_col(str(row['interactions']) + 'x', DIM)}"
        )
    lines.append(_col(f"{'─' * 46}\n", DIM))
    return "\n".join(lines)


def stats_notifications(db_path: Path) -> str:
    """Alias for stats_week — the most useful single-screen summary."""
    return stats_week(db_path)


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------


def _format_response_table(rows: list[tuple[str, float, int]], title: str) -> str:
    name_width = max(len(label) for label, _, _ in rows)
    name_width = max(name_width, 12)
    width = name_width + 28

    lines = [
        _col(f"\n{'─' * width}", DIM),
        f"  {_col(title, BOLD + WHITE)}",
        _col(f"{'─' * width}", DIM),
        f"  {_col('Reminder', BOLD):<{name_width + 12}} "
        f"{_col('Avg response', BOLD):<18} "
        f"{_col('Count', BOLD)}",
        "  " + "─" * (width - 2),
    ]
    for label, avg_sec, count in rows:
        lines.append(
            f"  {_col(label, CYAN):<{name_width + len(CYAN) + len(RESET)}} "
            f"{_col(_fmt_sec(avg_sec), GREEN):<18} "
            f"{_col(str(count), DIM)}"
        )
    lines.append(_col(f"{'─' * width}\n", DIM))
    return "\n".join(lines)
