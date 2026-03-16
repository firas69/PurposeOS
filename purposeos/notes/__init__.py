"""
notes/__init__.py — PurposeOS notes sub-package

Re-exports the complete public API so that all existing imports continue
to work without change:

    from purposeos.notes import list_notes, read_note, save_note, delete_note
    from purposeos.notes import open_editor
    from purposeos.notes import cmd_notes_list, cmd_notes_show, cmd_notes_delete

Internal layout:
    storage.py  — file I/O (list, read, save, delete)
    editor.py   — curses terminal editor (_Editor, open_editor)
    cli.py      — ANSI-formatted output for adctl commands
"""

from purposeos.notes.cli import (
    cmd_notes_delete,
    cmd_notes_list,
    cmd_notes_show,
)
from purposeos.notes.editor import open_editor
from purposeos.notes.storage import (
    delete_note,
    list_notes,
    read_note,
    save_note,
)

__all__ = [
    # storage
    "list_notes",
    "read_note",
    "save_note",
    "delete_note",
    # editor
    "open_editor",
    # cli formatters
    "cmd_notes_list",
    "cmd_notes_show",
    "cmd_notes_delete",
]
