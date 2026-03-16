"""
cli/notes_cmds.py — Notes CLI commands

Thin wrapper around purposeos.notes. Imports the notes module lazily
inside the function so adctl works without the notes directory existing.
"""

from __future__ import annotations

from purposeos.cli._output import _err, _info, _ok


def cmd_notes(args) -> None:
    try:
        from purposeos.notes import (
            cmd_notes_delete,
            cmd_notes_list,
            cmd_notes_show,
            list_notes,
            open_editor,
        )
    except ImportError as exc:
        _err(f"Notes module unavailable: {exc}")
        return

    sub = getattr(args, "notes_cmd", "list")

    if sub == "list" or sub is None:
        print(cmd_notes_list())
    elif sub == "new":
        path = open_editor()
        if path:
            _ok(f"Note saved: {path.name}")
        else:
            _info("Note discarded.")
    elif sub == "edit":
        notes = list_notes()
        idx = getattr(args, "index", 1) - 1
        if idx < 0 or idx >= len(notes):
            _err(f"Note #{idx + 1} not found.")
            return
        path = open_editor(notes[idx].read_text(encoding="utf-8"), notes[idx])
        if path:
            _ok(f"Note saved: {path.name}")
        else:
            _info("Note unchanged.")
    elif sub == "show":
        print(cmd_notes_show(args.index))
    elif sub == "delete":
        print(cmd_notes_delete(args.index))
    else:
        print(cmd_notes_list())
