"""
data/tracker/detection.py — Active window detection strategies

Four independent strategies for finding the currently focused application,
tried in order until one succeeds:

  1. GNOME Shell D-Bus via gdbus (FocusedApp)  — Wayland + X11, no extra deps
  2. GNOME Shell D-Bus via gdbus (eval)         — Wayland fallback for older GNOME
  3. python-wnck via GObject                    — X11 only, needs python3-wnck
  4. xdotool + xprop                            — X11 only, last resort

NOTE: xdotool getwindowclassname is intentionally NOT used — it has a known
heap-corruption bug (segfault in xdo_get_window_classname → XFree).
xprop is used instead for WM_CLASS lookups.

App name normalisation maps common window class names and titles to
consistent canonical names (e.g. "Mozilla Firefox" → "firefox").

No database imports. No purposeos imports. The only output is a
(app_name, window_title) tuple.
"""

from __future__ import annotations

import logging
import os
import re
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


def _is_wayland(env: dict) -> bool:
    return bool(env.get("WAYLAND_DISPLAY"))


# ---------------------------------------------------------------------------
# Detection strategies
# ---------------------------------------------------------------------------


def _get_active_window_gnome_dbus_focused_app(env: dict) -> tuple[str, str]:
    """
    Strategy 1: GNOME Shell FocusedApp property via D-Bus.
    Works on Wayland and X11. Returns app_id like 'org.gnome.Nautilus'.
    Only gives app name, not window title.
    """
    result = subprocess.run(
        [
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Shell",
            "--object-path", "/org/gnome/Shell",
            "--method", "org.freedesktop.DBus.Properties.Get",
            "org.gnome.Shell", "FocusedApp",
        ],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gdbus FocusedApp failed: {result.stderr.strip()}")

    m = re.search(r"'([^']+)'", result.stdout)
    if not m:
        raise RuntimeError("gdbus FocusedApp: no app id in output")

    app_id = m.group(1)  # e.g. "org.gnome.Nautilus"
    app_name = _normalise_app(app_id.split(".")[-1].lower())
    return (app_name, app_id)


def _get_active_window_gnome_dbus_eval(env: dict) -> tuple[str, str]:
    """
    Strategy 2: GNOME Shell JavaScript eval via D-Bus.
    More reliable on newer GNOME — returns both app id and window title.
    Wayland + X11. Requires GNOME Shell with Eval enabled (most distros allow it).
    """
    js = (
        "global.display.focus_window "
        "? [global.display.focus_window.get_wm_class(), "
        "   global.display.focus_window.get_title()] "
        ": ['', '']"
    )
    result = subprocess.run(
        [
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Shell",
            "--object-path", "/org/gnome/Shell",
            "--method", "org.gnome.Shell.Eval",
            js,
        ],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gdbus Eval failed: {result.stderr.strip()}")

    # Output looks like: (true, "['Firefox', 'GitHub - Mozilla Firefox']")
    m = re.search(r"\(true,\s*\"(.+)\"\s*\)", result.stdout, re.DOTALL)
    if not m:
        raise RuntimeError("gdbus Eval: unexpected output format")

    inner = m.group(1).replace('\\"', '"')
    parts = re.findall(r'"([^"]*)"', inner)
    if len(parts) < 2:
        raise RuntimeError("gdbus Eval: could not parse app/title")

    app_raw, window_title = parts[0], parts[1]
    if not app_raw:
        raise RuntimeError("gdbus Eval: empty app name")

    return (_normalise_app(app_raw), window_title)


def _get_active_window_wnck(env: dict) -> tuple[str, str]:
    """
    Strategy 3: libwnck via GObject — X11 only, needs python3-wnck.
    Skipped automatically on pure Wayland sessions.
    """
    if _is_wayland(env) and not env.get("DISPLAY"):
        raise RuntimeError("wnck: skipped on pure Wayland (no DISPLAY)")

    import gi
    gi.require_version("Wnck", "3.0")
    from gi.repository import Wnck  # type: ignore

    screen = Wnck.Screen.get_default()
    if screen is None:
        raise RuntimeError("wnck: no screen")
    screen.force_update()
    win = screen.get_active_window()
    if win is None:
        raise RuntimeError("wnck: no active window")
    app = win.get_application()
    app_name = app.get_name() if app else win.get_name()
    return (_normalise_app(app_name), win.get_name())


def _get_active_window_xdotool(env: dict) -> tuple[str, str]:
    """
    Strategy 4: xdotool + xprop — X11 only, last resort.
    Skipped automatically on pure Wayland sessions.

    NOTE: xdotool getwindowclassname is deliberately avoided — it has a
    known heap-corruption bug (segfault inside xdo_get_window_classname →
    XFree). WM_CLASS is read via xprop instead, which is stable.
    """
    if _is_wayland(env) and not env.get("DISPLAY"):
        raise RuntimeError("xdotool: skipped on pure Wayland (no DISPLAY)")

    wid_result = subprocess.run(
        ["xdotool", "getactivewindow"],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    wid = wid_result.stdout.strip()
    if not wid or not wid.isdigit():
        raise RuntimeError("xdotool: no active window id")

    title_result = subprocess.run(
        ["xdotool", "getwindowname", wid],
        capture_output=True,
        text=True,
        timeout=3,
        env=env,
    )
    window_title = title_result.stdout.strip()

    # Use xprop for WM_CLASS — intentionally NOT using xdotool getwindowclassname
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

    app_raw = app_raw or window_title
    return (_normalise_app(app_raw), window_title)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _get_active_window_info() -> tuple[str, str]:
    """
    Try all strategies in order; return the first that succeeds.

    Order:
      1. GNOME Shell D-Bus FocusedApp  (Wayland + X11)
      2. GNOME Shell D-Bus Eval        (Wayland + X11, richer data)
      3. python-wnck                   (X11 / XWayland)
      4. xdotool + xprop              (X11 / XWayland, last resort)
    """
    env = _full_env()
    errors: list[str] = []

    for label, fn in [
        ("gdbus:FocusedApp", _get_active_window_gnome_dbus_focused_app),
        ("gdbus:Eval",       _get_active_window_gnome_dbus_eval),
        ("wnck",             _get_active_window_wnck),
        ("xdotool+xprop",   _get_active_window_xdotool),
    ]:
        try:
            return fn(env)
        except Exception as e:
            errors.append(f"{label}:{e}")

    log.debug("All window-detection strategies failed: %s", "; ".join(errors))
    return ("unknown", "")



    