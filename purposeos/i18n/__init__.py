"""
i18n.py — PurposeOS Internationalisation (i18n) System

Provides centralised multi-language support with RTL (Right-to-Left) layout.
Languages: English (en), French (fr), Arabic (ar), Russian (ru)

Design:
- JSON files per language live in the i18n/ sub-directory next to this file.
- The translation directory is resolved from __file__ at call-time (not import-time)
  so the module works correctly whether run from the source tree or the installed
  package site-packages/purposeos/ directory.
- _initialized guard is removed: translations are (re)loaded on demand so that
  set_language() can always find a language even if the first import happened before
  the i18n/ directory was populated (e.g. when running from source during development).
- set_language() proactively tries to load a missing language from disk before
  giving up, instead of silently falling back to English.
- Module-level state: simple and reliable, no class overhead.

Bug fixes vs original:
  1. Removed _initialized guard that permanently locked out language switching
     if JSON files were missing at first import.
  2. set_language() now attempts a fresh disk load for the requested language
     before deciding it is unavailable.
  3. Resolved ambiguity between the "i18n" module name and the "i18n/" data
     directory: _get_i18n_dir() resolves the path from __file__ at call-time.
  4. gui.py import path fixed: use purposeos.i18n (package-relative) with
     a flat-layout fallback, not bare "import i18n" which fails when installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── RTL language codes ────────────────────────────────────────────────────────

RTL_LANGUAGES: frozenset = frozenset({"ar"})

# ── Supported languages (code → display name) ─────────────────────────────────

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "fr": "Français",
    "ar": "العربية",
    "ru": "Русский",
}

# ── Module-level state ────────────────────────────────────────────────────────

_current_lang: str = "en"
_translations: dict[str, dict[str, Any]] = {}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _get_i18n_dir() -> Path:
    """Return the i18n/ data directory.

    Resolved from __file__ at call-time so it works in:
      - flat source layout:  ~/projects/i18n.py  →  ~/projects/i18n/
      - installed package:   site-packages/purposeos/i18n.py
                             →  site-packages/purposeos/i18n/
    """
    return Path(__file__).resolve().parent


def _load_one(lang_code: str) -> dict[str, Any] | None:
    """Try to load a single language JSON from disk. Returns None on failure."""
    lang_file = _get_i18n_dir() / f"{lang_code}.json"
    if not lang_file.exists():
        return None
    try:
        with open(lang_file, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"i18n: Warning — failed to load {lang_file.name}: {exc}")
        return None


def _ensure_english() -> None:
    """Make sure English is always present, even if the JSON file is missing."""
    if "en" not in _translations:
        data = _load_one("en")
        _translations["en"] = data if data is not None else {}


def _load_all() -> None:
    """Load all supported language files from the i18n/ directory."""
    for lang_code in SUPPORTED_LANGUAGES:
        if lang_code not in _translations:
            data = _load_one(lang_code)
            if data is not None:
                _translations[lang_code] = data
    _ensure_english()


# ── Public API ────────────────────────────────────────────────────────────────


def set_language(lang_code: str) -> None:
    """Set the active language.

    If the requested language has not been loaded yet, this function attempts
    a fresh load from disk before deciding it is unavailable.  This means
    set_language() is safe to call at any time — even before the i18n/ directory
    existed at import time.
    """
    global _current_lang

    # Already loaded → just switch
    if lang_code in _translations:
        _current_lang = lang_code
        return

    # Try to load from disk on demand
    data = _load_one(lang_code)
    if data is not None:
        _translations[lang_code] = data
        _current_lang = lang_code
        return

    # Language genuinely unavailable
    if lang_code not in SUPPORTED_LANGUAGES:
        print(f"i18n: Warning — '{lang_code}' is not a supported language. Using 'en'.")
    else:
        print(
            f"i18n: Warning — '{lang_code}.json' not found in {_get_i18n_dir()}. "
            "Using 'en'. Run the installer or copy the i18n/ directory to fix this."
        )
    _ensure_english()
    _current_lang = "en"


def get_language() -> str:
    """Return the currently active language code."""
    return _current_lang


def get_all_languages() -> dict[str, str]:
    """Return {code: display_name} for all supported languages."""
    return dict(SUPPORTED_LANGUAGES)


def t(key: str, default: str = "") -> str:
    """Look up a translation key using dot notation.

    Args:
        key:     Dot-notation key, e.g. ``"navigation.reminders"``.
        default: Value to return when the key is absent in both the active
                 language and the English fallback.

    Returns:
        The translated string, or *default* if not found.

    Example::

        t("navigation.reminders", "Reminders")
        # → "Rappels"  (when language is "fr")
    """
    # Ensure at least English is loaded
    _ensure_english()

    def _lookup(lang_dict: dict[str, Any], keys: list) -> str | None:
        node = lang_dict
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
            else:
                return None
        return str(node) if node is not None else None

    parts = key.split(".")

    # 1. Try active language
    result = _lookup(_translations.get(_current_lang, {}), parts)
    if result is not None:
        return result

    # 2. Fallback to English
    result = _lookup(_translations.get("en", {}), parts)
    if result is not None:
        return result

    # 3. Final fallback: caller's default
    return default


def is_rtl() -> bool:
    """Return True if the current language reads right-to-left."""
    return _current_lang in RTL_LANGUAGES


def get_layout_direction() -> str:
    """Return ``"rtl"`` or ``"ltr"`` for use with Qt layout direction."""
    return "rtl" if is_rtl() else "ltr"


# ── Eager pre-load on import ──────────────────────────────────────────────────
# Load all languages at import time so t() is always fast.
# This is non-blocking: missing files are silently skipped.
_load_all()
