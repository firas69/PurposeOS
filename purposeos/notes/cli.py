"""
notes/cli.py — CLI output formatters for adctl notes commands

Produces ANSI-formatted strings for list, show, and delete operations.
These functions are called by adctl's cmd_notes() handler and print
their return values to stdout.

No curses, no GUI, no config access — purely formats data from storage.
"""

from __future__ import annotations

from purposeos.notes.storage import delete_note, list_notes, read_note


def cmd_notes_list() -> str:
    """Return a formatted list of notes."""
    notes = list_notes()
    if not notes:
        return "\033[33mNo notes found. Create one with: adctl notes new\033[0m\n"

    lines = ["\033[2m" + "─" * 56 + "\033[0m"]
    lines.append(f"  \033[1m{'#':<5} {'Filename':<28} {'Preview'}\033[0m")
    lines.append("  " + "─" * 52)
    for i, path in enumerate(notes, 1):
        try:
            preview = path.read_text(encoding="utf-8")[:40].replace("\n", " ")
        except Exception:
            preview = "[unreadable]"
        lines.append(f"  {str(i):<5} \033[36m{path.name:<28}\033[0m {preview}")
    lines.append("\033[2m" + "─" * 56 + "\033[0m")
    return "\n".join(lines) + "\n"


def cmd_notes_show(index: int) -> str:
    notes = list_notes()
    if not notes or index < 1 or index > len(notes):
        return f"\033[31mNote #{index} not found.\033[0m\n"
    path = notes[index - 1]
    content = read_note(path)
    separator = "\033[2m" + "─" * 56 + "\033[0m"
    return f"{separator}\n\033[1m {path.name}\033[0m\n{separator}\n{content}\n{separator}\n"


def cmd_notes_delete(index: int) -> str:
    notes = list_notes()
    if not notes or index < 1 or index > len(notes):
        return f"\033[31mNote #{index} not found.\033[0m\n"
    path = notes[index - 1]
    name = path.name
    delete_note(path)
    return f"\033[32mDeleted note: {name}\033[0m\n"
