"""
overlay.py — PurposeOS Full-Screen Notification Overlay

Standalone script launched as a subprocess by notifications.py. Displays a
semi-transparent dark full-screen overlay with title, message, and a Done
button. Writes a result JSON file on close so the daemon can record the
interaction.

Design decisions:
- GTK4 is the primary toolkit; PySide6 is the fallback.
- The window uses set_decorated(False) + fullscreen() rather than a splash hint
  because GTK4 removed WINDOW_TYPE_HINT_SPLASHSCREEN.
- CSS provides the semi-transparent background with RGBA colour.
- A GLib timeout fires auto-close for non-critical urgency.
- On close the result JSON is written before the process exits.
- Sound is started after the window is presented and killed when the window
  closes (Done button or auto-close timer), so it never outlives the overlay.

Usage (called by notifications.py):
    python overlay.py --title TEXT --message TEXT --urgency low|normal|critical
                      --timeout-ms MS --notification-id UUID
                      --result-path /tmp/purposeos_overlay_UUID.json
                      [--sound-file NAME_OR_PATH]
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import json
import os
import subprocess
import sys
from datetime import datetime


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PurposeOS screen-wide overlay")
    p.add_argument("--title", default="Reminder")
    p.add_argument("--message", default="")
    p.add_argument("--urgency", default="normal", choices=["low", "normal", "critical"])
    p.add_argument("--timeout-ms", type=int, default=30000)
    p.add_argument("--notification-id", default="unknown")
    p.add_argument("--result-path", default="")
    p.add_argument("--sound-file", default="")
    return p.parse_args()


def _write_result(result_path: str, action: str, shown_at: str) -> None:
    if not result_path:
        return
    now = datetime.now().isoformat()
    try:
        shown_dt = datetime.fromisoformat(shown_at)
        response_sec = (datetime.now() - shown_dt).total_seconds()
    except Exception:
        response_sec = 0.0
    data = {
        "action": action,
        "dismissed_at": now,
        "response_sec": round(response_sec, 2),
    }
    try:
        with open(result_path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"overlay: failed to write result: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Sound helpers — return Popen handles so callers can terminate early
# ---------------------------------------------------------------------------


def _start_sound(sound_file: str) -> list:
    """Start playing *sound_file* and return the list of Popen objects.

    Returns an empty list if sound_file is empty or playback cannot start.
    The caller should call p.terminate() on each returned process when it
    wants to stop playback (e.g. when Done is clicked or the timer fires).

    Supports .mp3, .ogg, .oga, .wav, .flac via an ffmpeg -> paplay pipeline,
    trimmed to the first 5 seconds.  Freedesktop event names go via
    canberra-gtk-play with a .oga/.ogg file fallback.
    """
    if not sound_file:
        return []
    try:
        if sound_file.startswith("/") or sound_file.startswith("~"):
            path = os.path.expanduser(sound_file)
            return _start_file_pipeline(path)
        else:
            # Freedesktop event name
            try:
                p = subprocess.Popen(
                    ["canberra-gtk-play", "--id", sound_file],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return [p]
            except FileNotFoundError:
                pass
            matches = glob.glob(f"/usr/share/sounds/**/{sound_file}.oga", recursive=True)
            if not matches:
                matches = glob.glob(f"/usr/share/sounds/**/{sound_file}.ogg", recursive=True)
            if matches:
                return _start_file_pipeline(matches[0])
    except Exception:
        pass
    return []


def _get_duration(path: str) -> float:
    """Return the duration of *path* in seconds, or 0.0 on any failure.

    Uses ffprobe when available; falls back to parsing ffmpeg's stderr output.
    """
    import shutil

    try:
        if shutil.which("ffprobe"):
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return float(result.stdout.strip())
        else:
            # ffmpeg fallback: parse "Duration: HH:MM:SS.ss" from stderr
            result = subprocess.run(
                ["ffmpeg", "-i", path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            import re

            m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result.stderr)
            if m:
                h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return h * 3600 + mn * 60 + s
    except Exception:
        pass
    return 0.0


def _start_file_pipeline(path: str) -> list:
    """Decode *path* with ffmpeg and pipe raw PCM to paplay.

    If the file is longer than 5 seconds a fade-out is applied over the final
    5 seconds so playback ends smoothly rather than cutting abruptly.
    The sound plays to its natural end OR until the caller terminates the
    returned processes via _stop_sound() — whichever comes first.  The
    overlay's Done-button and auto-close timer call _stop_sound() when the
    window closes.

    Returns [ffmpeg_proc, paplay_proc] so the caller can terminate both.
    Falls back to a bare paplay call if ffmpeg is unavailable.
    """
    import shutil

    if not shutil.which("ffmpeg"):
        try:
            p = subprocess.Popen(
                ["paplay", path],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return [p]
        except Exception:
            return []
    try:
        # Build the audio filter chain: add a 5-second fade-out if the file
        # is long enough to warrant one.
        FADE_SEC = 5.0
        duration = _get_duration(path)
        if duration > FADE_SEC:
            fade_start = duration - FADE_SEC
            af_filter = ["-af", f"afade=t=out:st={fade_start:.3f}:d={FADE_SEC}"]
        else:
            af_filter = []

        ffmpeg_proc = subprocess.Popen(
            [
                "ffmpeg",
                "-loglevel",
                "quiet",
                "-i",
                path,
                "-vn",
                *af_filter,
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        paplay_proc = subprocess.Popen(
            ["paplay", "--raw", "--format=s16le", "--rate=44100", "--channels=2"],
            stdin=ffmpeg_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if ffmpeg_proc.stdout:
            ffmpeg_proc.stdout.close()
        return [ffmpeg_proc, paplay_proc]
    except Exception:
        return []


def _stop_sound(procs: list) -> None:
    """Terminate every process in *procs*, ignoring all errors."""
    for p in procs:
        with contextlib.suppress(Exception):
            p.terminate()
    procs.clear()


# ---------------------------------------------------------------------------
# GTK4 implementation
# ---------------------------------------------------------------------------


def _run_gtk4(args: argparse.Namespace) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, GLib, Gtk  # type: ignore

    shown_at = datetime.now().isoformat()
    sound_procs: list = []

    app = Gtk.Application(application_id="io.purposeos.overlay")

    def on_activate(application: Gtk.Application) -> None:
        win = Gtk.ApplicationWindow(application=application)
        win.set_decorated(False)
        win.fullscreen()

        css = b"""
        window {
            background-color: rgba(0, 0, 0, 0.85);
        }
        .title-label {
            color: white;
            font-size: 48px;
            font-weight: bold;
        }
        .message-label {
            color: #cccccc;
            font-size: 32px;
        }
        .countdown-label {
            color: #888888;
            font-size: 18px;
            margin-top: 8px;
        }
        .done-button {
            all: unset;
            background-color: #3B82F6;
            color: white;
            border-radius: 12px;
            font-size: 22px;
            font-weight: bold;
            padding: 12px 40px;
            min-width: 200px;
            min-height: 60px;
        }
        .done-button:hover {
            background-color: #2563EB;
        }
        .done-button:active {
            background-color: #1D4ED8;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)

        title_lbl = Gtk.Label(label=args.title)
        title_lbl.add_css_class("title-label")
        title_lbl.set_wrap(True)
        title_lbl.set_max_width_chars(50)
        vbox.append(title_lbl)

        msg_lbl = Gtk.Label(label=args.message)
        msg_lbl.add_css_class("message-label")
        msg_lbl.set_wrap(True)
        msg_lbl.set_max_width_chars(70)
        vbox.append(msg_lbl)

        done_btn = Gtk.Button(label="Done")
        done_btn.add_css_class("done-button")
        done_btn.set_halign(Gtk.Align.CENTER)
        vbox.append(done_btn)

        remaining_sec = [args.timeout_ms // 1000]

        if args.urgency != "critical" and args.timeout_ms > 0:
            countdown_lbl = Gtk.Label(label=f"(auto-closes in {remaining_sec[0]}s)")
            countdown_lbl.add_css_class("countdown-label")
            countdown_lbl.set_halign(Gtk.Align.CENTER)
            vbox.append(countdown_lbl)

            def tick() -> bool:
                remaining_sec[0] -= 1
                if remaining_sec[0] <= 0:
                    _stop_sound(sound_procs)
                    _write_result(args.result_path, "timeout", shown_at)
                    application.quit()
                    return False
                countdown_lbl.set_text(f"(auto-closes in {remaining_sec[0]}s)")
                return True

            GLib.timeout_add(1000, tick)

        def on_done(_btn) -> None:
            _stop_sound(sound_procs)
            _write_result(args.result_path, "done", shown_at)
            application.quit()

        done_btn.connect("clicked", on_done)
        win.set_child(vbox)
        win.present()

        # Start sound after the window is presented so the UI is responsive first
        sound_procs.extend(_start_sound(args.sound_file))

    app.connect("activate", on_activate)
    app.run([])


# ---------------------------------------------------------------------------
# PySide6 fallback
# ---------------------------------------------------------------------------


def _run_pyside6(args: argparse.Namespace) -> None:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (  # type: ignore
        QApplication,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    shown_at = datetime.now().isoformat()
    sound_procs: list = []
    app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    win.showFullScreen()
    win.setStyleSheet("background-color: rgba(0, 0, 0, 216);")

    layout = QVBoxLayout(win)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(24)

    title_lbl = QLabel(args.title)
    title_lbl.setStyleSheet("color: white; font-size: 48px; font-weight: bold;")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_lbl.setWordWrap(True)
    layout.addWidget(title_lbl)

    msg_lbl = QLabel(args.message)
    msg_lbl.setStyleSheet("color: #cccccc; font-size: 32px;")
    msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    msg_lbl.setWordWrap(True)
    layout.addWidget(msg_lbl)

    done_btn = QPushButton("Done")
    done_btn.setObjectName("doneBtn")
    done_btn.setStyleSheet(
        "#doneBtn { background-color: #3B82F6; color: #FFFFFF; border-radius: 12px;"
        " font-size: 22px; font-weight: bold; padding: 12px 40px;"
        " min-width: 200px; min-height: 60px; border: none; }"
        "#doneBtn:hover { background-color: #2563EB; color: #FFFFFF; }"
        "#doneBtn:pressed { background-color: #1D4ED8; color: #FFFFFF; }"
    )
    layout.addWidget(done_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    remaining_sec = [args.timeout_ms // 1000]

    if args.urgency != "critical" and args.timeout_ms > 0:
        countdown_lbl = QLabel(f"(auto-closes in {remaining_sec[0]}s)")
        countdown_lbl.setStyleSheet("color: #888888; font-size: 18px;")
        countdown_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(countdown_lbl)

        tick_timer = QTimer()
        tick_timer.setInterval(1000)

        def tick() -> None:
            remaining_sec[0] -= 1
            if remaining_sec[0] <= 0:
                tick_timer.stop()
                _stop_sound(sound_procs)
                _write_result(args.result_path, "timeout", shown_at)
                app.quit()
                return
            countdown_lbl.setText(f"(auto-closes in {remaining_sec[0]}s)")

        tick_timer.timeout.connect(tick)
        tick_timer.start()

    def on_done() -> None:
        _stop_sound(sound_procs)
        _write_result(args.result_path, "done", shown_at)
        app.quit()

    done_btn.clicked.connect(on_done)

    # Start sound after the event loop begins (delay=0 fires on first iteration)
    QTimer.singleShot(0, lambda: sound_procs.extend(_start_sound(args.sound_file)))

    app.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    # Try GTK4 first
    try:
        import gi  # noqa: F401

        _run_gtk4(args)
        return
    except Exception:
        pass

    # Try PySide6 fallback
    try:
        _run_pyside6(args)
        return
    except Exception:
        print("overlay: both GTK4 and PySide6 unavailable. Cannot show overlay.", file=sys.stderr)
        _write_result(args.result_path, "timeout", datetime.now().isoformat())
        sys.exit(1)


if __name__ == "__main__":
    main()
