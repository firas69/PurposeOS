"""
notifications/__init__.py — PurposeOS notifications sub-package

Re-exports the public API so that the existing import continues to work:

    from purposeos.notifications import fire_reminder

Internal layout:
    notifications.py  — orchestration (fire_reminder, _fire_screen_wide,
                         _fire_standard, _user_env, _OVERLAY_SCRIPT)
    interactions.py   — SQLite recording (_record_interaction,
                         _update_interaction, _poll_result)
    sound.py          — audio pipeline (_play_sound, _get_duration, _play_file)
"""

from purposeos.notifications.notifications import fire_reminder

__all__ = ["fire_reminder"]
