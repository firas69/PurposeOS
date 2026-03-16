"""
cli/gui_cmds.py — GUI and quicknote launch commands

Both imports are lazy (inside the function body) so adctl works in
full without PySide6 installed. The ImportError is caught and printed
as a helpful installation hint.
"""

from __future__ import annotations

from purposeos.cli._output import _err


def cmd_gui(args) -> None:
    notes_only = getattr(args, "notes", False)
    try:
        from purposeos.gui import main as gui_main
    except ImportError as exc:
        if "PySide6" in str(exc) or "pyside6" in str(exc).lower():
            _err("PySide6 is not installed. Install it with:\n   pip install --user PySide6")
        else:
            _err(f"GUI import failed: {exc}")
        return
    try:
        gui_main(start_tab="Notes" if notes_only else None)
    except Exception as exc:
        _err(f"GUI failed to start: {exc}")


def cmd_quicknote(_args) -> None:
    """Launch the lightweight floating quick-note window."""
    try:
        from purposeos.gui.quicknote import run

        run()
    except ImportError:
        _err("PySide6 is not installed. Install it with:\n   pip install --user PySide6")
    except Exception as exc:
        _err(f"Quick note failed to start: {exc}")
