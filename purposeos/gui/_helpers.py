"""
gui/_helpers.py — Shared GUI utility functions and i18n bindings

This module owns:
  - The i18n import block (3-level fallback: package → source tree → stubs).
    ALL other gui/ modules import t(), is_rtl(), set_language() etc. from here
    so the fallback logic lives in exactly one place.
  - Stateless helper functions used across all panels and dialogs.

No widget construction happens here — pure functions only.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────
# i18n — package-relative import with flat-layout fallback
# ─────────────────────────────────────────────────────────────────

try:
    from purposeos.i18n import (
        get_all_languages,
        get_language,
        get_layout_direction,
        is_rtl,
        set_language,
    )
    from purposeos.i18n import (  # type: ignore[import]
        t as _t,
    )
except ImportError:
    try:
        import importlib.util as _ilu
        import os as _os

        _i18n_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "i18n",
            "__init__.py",
        )
        _spec = _ilu.spec_from_file_location("purposeos._i18n_local", _i18n_path)
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        _t = _mod.t
        set_language = _mod.set_language
        get_language = _mod.get_language
        get_all_languages = _mod.get_all_languages
        is_rtl = _mod.is_rtl
        get_layout_direction = _mod.get_layout_direction
    except Exception:

        def _t(key: str, default: str = "") -> str:
            return default  # type: ignore[misc]

        def set_language(lang: str) -> None:
            pass  # type: ignore[misc]

        def get_language() -> str:
            return "en"  # type: ignore[misc]

        def get_all_languages() -> dict[str, str]:  # type: ignore[misc]
            return {"en": "English", "fr": "Français", "ar": "العربية", "ru": "Русский"}

        def is_rtl() -> bool:
            return False  # type: ignore[misc]

        def get_layout_direction() -> str:
            return "ltr"  # type: ignore[misc]


def t(key: str, default: str = "") -> str:
    return _t(key, default)


# ─────────────────────────────────────────────────────────────────
# RTL helper
# ─────────────────────────────────────────────────────────────────


def _apply_rtl(widget) -> None:
    """Mirror a widget's layout direction when Arabic is active."""
    from PySide6.QtCore import Qt

    if is_rtl():
        widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)


# ─────────────────────────────────────────────────────────────────
# Shortcut helper
# ─────────────────────────────────────────────────────────────────


def _make_shortcut(key: str, parent, callback):
    """Create a QShortcut scoped to *parent* (WidgetWithChildrenShortcut).

    Prevents Ctrl+N/E/D/R/S from firing across all sections simultaneously —
    the shortcut only activates when *parent* or a child has keyboard focus.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence, QShortcut

    sc = QShortcut(QKeySequence(key), parent)
    sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    sc.activated.connect(callback)
    return sc


# ─────────────────────────────────────────────────────────────────
# Trigger description (translated)
# ─────────────────────────────────────────────────────────────────

_DOW_NAMES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def _friendly_trigger(trigger: str, trigger_value) -> str:
    if trigger == "boot":
        return t("trigger.boot", "On boot")
    if trigger == "daily":
        if trigger_value:
            return t("trigger.daily_at", "Daily at {time}").replace("{time}", str(trigger_value))
        return t("trigger.daily", "Daily")
    if trigger == "interval_minutes":
        if trigger_value:
            return t("trigger.interval", "Every {n} min").replace("{n}", str(trigger_value))
        return t("trigger.interval", "Every {n} min").replace("{n}", "?")
    if trigger == "weekly":
        day = _DOW_NAMES.get(str(trigger_value).lower(), str(trigger_value).capitalize())
        return t("trigger.weekly", "Weekly — {day}").replace("{day}", day)
    return f"{trigger} {trigger_value}".strip()


# ─────────────────────────────────────────────────────────────────
# Path normalisation
# ─────────────────────────────────────────────────────────────────


def _normalise_path(raw: str) -> str:
    import os
    import re

    if not raw:
        return raw
    home = os.path.expanduser("~")
    username = os.path.basename(home)
    raw = re.sub(rf"^~/home/{re.escape(username)}/", "~/", raw)
    raw = re.sub(rf"^~/home/{re.escape(username)}$", "~", raw)
    raw = re.sub(rf"^{re.escape(home)}/home/{re.escape(username)}/", f"{home}/", raw)
    return raw
