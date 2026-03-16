"""
cli/_output.py — ANSI colour constants and print helpers

All terminal output formatting for adctl lives here.
Imported by every other cli/ module — the only shared dependency
that all command files take on.

No business logic. No purposeos imports.
"""

from __future__ import annotations

import sys

# ── ANSI escape codes ─────────────────────────────────────────────
R = "\033[0m"  # reset
B = "\033[1m"  # bold
GR = "\033[32m"  # green
YE = "\033[33m"  # yellow
RE = "\033[31m"  # red
CY = "\033[36m"  # cyan
BL = "\033[34m"  # blue
DI = "\033[2m"  # dim
WH = "\033[37m"  # white


def _ok(msg: str) -> None:
    print(f"{GR}✓{R}  {msg}")


def _err(msg: str) -> None:
    print(f"{RE}✗{R}  {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"{CY}→{R}  {msg}")
