"""
data/tracker/detection.py — Active window detection strategies

Three independent strategies for finding the currently focused application,
tried in order until one succeeds:

  1. GNOME Shell D-Bus via gdbus — works on Wayland and X11, no extra deps
  2. python-wnck via GObject — X11 only, needs python3-wnck package
  3. xdotool + xprop — X11 only fallback

App name normalisation maps common window class names and titles to
consistent canonical names (e.g. "Mozilla Firefox" → "firefox").

No database imports. No purposeos imports. The only output is a
(app_name, window_title) tuple.
"""

from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger("purposeos.tracker")

# ---------------------------------------------------------------------------
# App name normalisation
# ---------------------------------------------------------------------------

_APP_NAME_MAP = {
    "mozilla firefox": "firefox",
    "firefox": "firefox",
    "google-chrome": "chrome",
    "google chrome": "chrome",
    "chromium": "chromium",
    "chromium-browser": "chromium",
    "gnome-terminal": "terminal",
    "gnome terminal": "terminal",
    "code": "vscode",
    "visual studio code": "vscode",
    "jetbrains": "jetbrains",
    "nautilus": "files",
    "thunar": "files",
}


def _normalise_app(raw: str) -> str:
    """Strip suffixes, lowercase, and map common variants to canonical names."""
    if not raw:
        return "unknown"
    # Take the last token after " — " or " - " (common title separators)
    for sep in (" — ", " - ", " | "):
        if sep in raw:
            raw = raw.split(sep)[-1]
            break
    normalised = raw.strip().lower()
    return _APP_NAME_MAP.get(normalised, normalised)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _full_env() -> dict:
    """Full graphical-session environment for subprocesses."""
    env = os.environ.copy()
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in result.stdout.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                if key in (
                    "DISPLAY",
                    "WAYLAND_DISPLAY",
                    "XAUTHORITY",
                    "DBUS_SESSION_BUS_ADDRESS",
                    "XDG_RUNTIME_DIR",
                    "HOME",
                ):
                    env.setdefault(key, val)
    except Exception:
        pass
    env.setdefault("DISPLAY", ":0")
    return env


# ---------------------------------------------------------------------------
# Detection strategies
# ---------------------------------------------------------------------------


def _get_active_window_gnome_wayland(env: dict) -> tuple[str, str]:
    """Query GNOME Shell focused app via gdbus — works on Wayland, no extra deps."""
    result = subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Shell",
            "--object-path",
            "/org/gnome/Shell",
            "--method",
            "org.freedesktop.DBus.Properties.Get",
            "org.gnome.Shell",
            "FocusedApp",
        ],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    if result.returncode == 0:
        import re

        m = re.search(r"'([^']+)'", result.stdout)
        if m:
            app_id = m.group(1)  # e.g. "org.gnome.Nautilus"
            app_name = app_id.split(".")[-1].lower()
            return (_normalise_app(app_name), app_id)
    raise RuntimeError("gdbus FocusedApp failed")


def _get_active_window_wnck(env: dict) -> tuple[str, str]:
    """libwnck via GObject — works on X11, needs python3-wnck package."""
    import gi

    gi.require_version("Wnck", "3.0")
    from gi.repository import Wnck  # type: ignore

    screen = Wnck.Screen.get_default()
    if screen is None:
        raise RuntimeError("No Wnck screen")
    screen.force_update()
    win = screen.get_active_window()
    if win is None:
        raise RuntimeError("No active window")
    app = win.get_application()
    app_name = app.get_name() if app else win.get_name()
    return (_normalise_app(app_name), win.get_name())


def _get_active_window_xdotool(env: dict) -> tuple[str, str]:
    """xdotool + xprop — X11 only fallback."""
    wid_result = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    wid = wid_result.stdout.strip()
    if not wid or not wid.isdigit():
        raise RuntimeError("No active window id from xdotool")

    title_result = subprocess.run(
        ["xdotool", "getwindowname", wid],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    window_title = title_result.stdout.strip()

    app_raw = ""
    try:
        xprop_result = subprocess.run(
            ["xprop", "-id", wid, "WM_CLASS"],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
        )
        xprop_out = xprop_result.stdout.strip()
        if "=" in xprop_out:
            tokens = [t.strip().strip('"') for t in xprop_out.split("=", 1)[1].split(",")]
            app_raw = tokens[-1] if tokens else ""
    except Exception:
        pass

    if not app_raw:
        try:
            class_result = subprocess.run(
                ["xdotool", "getwindowclassname", wid],
                capture_output=True,
                text=True,
                timeout=3,
                env=env,
            )
            app_raw = class_result.stdout.strip()
        except Exception:
            pass

    app_raw = app_raw or window_title
    return (_normalise_app(app_raw), window_title)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _get_active_window_info() -> tuple[str, str]:
    """Try GNOME D-Bus → wnck → xdotool in order; return first that works."""
    env = _full_env()
    errors = []

    # Strategy 1: GNOME Shell D-Bus (Wayland + X11, no extra deps)
    try:
        return _get_active_window_gnome_wayland(env)
    except Exception as e:
        errors.append(f"gdbus:{e}")

    # Strategy 2: python-wnck (X11, needs python3-wnck)
    try:
        return _get_active_window_wnck(env)
    except Exception as e:
        errors.append(f"wnck:{e}")

    # Strategy 3: xdotool + xprop (X11 only)
    try:
        return _get_active_window_xdotool(env)
    except FileNotFoundError:
        raise
    except Exception as e:
        errors.append(f"xdotool:{e}")

    log.debug("All window-detection strategies failed: %s", "; ".join(errors))
    return ("unknown", "")
