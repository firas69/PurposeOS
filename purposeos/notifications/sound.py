"""
notifications/sound.py — Audio playback pipeline

Handles all sound playback for notifications:
  - freedesktop event names (via canberra-gtk-play or /usr/share/sounds/)
  - custom file paths (.mp3, .ogg, .oga, .wav, .flac)
  - ffmpeg → paplay pipeline with fade-out for long files
  - ffprobe / ffmpeg fallback for duration detection

The env dict (from _user_env in notifications.py) is passed as an argument
so this module has no purposeos imports and no dependency on the daemon.
"""

from __future__ import annotations

import glob
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger("purposeos.notifications")


def _play_sound(sound_file: str, env: dict) -> None:
    """Play a sound — supports .mp3, .ogg, .oga, .wav, .flac and freedesktop
    event names.  All files are trimmed to the first 5 seconds via ffmpeg so
    that a long custom track never blocks the notification for an unexpected
    duration.  ffmpeg converts to WAV on the fly and streams it to paplay so no
    temp file is needed for most formats.  MP3 files require the extra decode
    step via ffmpeg as paplay / PipeWire does not support MP3 directly.

    If sound_file starts with '/' or '~' it is treated as a file path.
    Otherwise it is treated as a freedesktop sound event name.
    """
    if not sound_file:
        return
    try:
        if sound_file.startswith("/") or sound_file.startswith("~"):
            # ── Custom file path ───────────────────────────────────────────
            path = Path(sound_file).expanduser()
            if not path.exists():
                log.warning("Sound file not found: %s", path)
                return
            _play_file(str(path), env)
        else:
            # ── Freedesktop event name ─────────────────────────────────────
            played = False
            try:
                subprocess.Popen(
                    ["canberra-gtk-play", "--id", sound_file],
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                played = True
            except FileNotFoundError:
                pass
            if not played:
                matches = glob.glob(f"/usr/share/sounds/**/{sound_file}.oga", recursive=True)
                if not matches:
                    matches = glob.glob(f"/usr/share/sounds/**/{sound_file}.ogg", recursive=True)
                if matches:
                    _play_file(matches[0], env)
                else:
                    log.warning(
                        "Sound '%s' not found and canberra-gtk-play unavailable",
                        sound_file,
                    )
    except Exception as exc:
        log.debug("Sound playback failed: %s", exc)


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
            result = subprocess.run(
                ["ffmpeg", "-i", path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result.stderr)
            if m:
                h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return h * 3600 + mn * 60 + s
    except Exception:
        pass
    return 0.0


def _play_file(path: str, env: dict) -> None:
    """Play *path* using ffmpeg piped to paplay.

    ffmpeg decodes and resamples to stereo 44100 Hz WAV and passes it on
    stdout; paplay reads from stdin.  Handles mp3, ogg, oga, wav, flac, and
    any other format ffmpeg understands, without writing temp files.

    A 5-second fade-out is applied at the end of files longer than 5 seconds
    so playback ends smoothly.  The sound plays to its natural end — no
    artificial time cap.
    """
    import shutil

    if not shutil.which("ffmpeg"):
        # ffmpeg unavailable — fall back to direct paplay (no MP3 support)
        try:
            subprocess.Popen(
                ["paplay", path],
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            log.debug("paplay fallback failed: %s", exc)
        return

    try:
        # Build optional fade-out filter
        FADE_SEC = 5.0
        duration = _get_duration(path)
        if duration > FADE_SEC:
            fade_start = duration - FADE_SEC
            af_filter = ["-af", f"afade=t=out:st={fade_start:.3f}:d={FADE_SEC}"]
        else:
            af_filter = []

        # ffmpeg → stdout (raw WAV) → paplay stdin
        # -vn  : drop any video streams (e.g. cover art in MP3)
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
            env=env,
            start_new_session=True,
        )
        subprocess.Popen(
            ["paplay", "--raw", "--format=s16le", "--rate=44100", "--channels=2"],
            stdin=ffmpeg_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        # Allow ffmpeg's stdout to be consumed by paplay
        if ffmpeg_proc.stdout:
            ffmpeg_proc.stdout.close()
    except Exception as exc:
        log.debug("ffmpeg/paplay pipeline failed for %s: %s", path, exc)
