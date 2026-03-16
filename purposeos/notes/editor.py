"""
notes/editor.py — Terminal curses editor

A full-terminal multi-line text editor built on Python's curses module.
Supports arrow keys, Home/End, Backspace, Delete, Enter, Ctrl+S (save),
Ctrl+Q (quit with unsaved-changes guard), and a status bar.

No GUI deps, no CLI formatting. The only purposeos import is save_note
from storage, which is called on Ctrl+S.
"""

from __future__ import annotations

import contextlib
import curses
import sys
from pathlib import Path

from purposeos.notes.storage import save_note

# _STATUS_ATTR is set to curses.A_REVERSE; kept here for reference.
# _draw() uses curses.A_REVERSE directly since curses constants
# are not available until curses.wrapper() initialises the display.
_STATUS_ATTR = curses.A_REVERSE


class _Editor:
    """Minimal multi-line text editor built on curses."""

    def __init__(self, stdscr, initial_text: str, filepath: Path | None) -> None:
        self.stdscr = stdscr
        self.lines: list[str] = initial_text.split("\n") if initial_text else [""]
        self.filepath = filepath
        self.cursor_row = 0
        self.cursor_col = 0
        self.scroll_offset = 0  # first visible line
        self.modified = False
        self.saved_path: Path | None = None

    # --- Drawing ----------------------------------------------------------

    def _draw(self) -> None:
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        text_area_h = h - 1  # bottom row is status bar

        # Render visible lines
        for screen_row in range(text_area_h):
            line_idx = self.scroll_offset + screen_row
            if line_idx >= len(self.lines):
                break
            line = self.lines[line_idx]
            display = line[: w - 1]
            with contextlib.suppress(curses.error):
                self.stdscr.addstr(screen_row, 0, display)

        # Status bar
        fname = str(self.filepath.name) if self.filepath else "[new note]"
        modified_flag = " [modified]" if self.modified else ""
        position = f"  Ln {self.cursor_row + 1}:{self.cursor_col + 1}"
        shortcuts = "  ^S Save  ^Q Quit"
        status = f" {fname}{modified_flag}{position}{shortcuts}"
        status = status[: w - 1].ljust(w - 1)
        try:
            self.stdscr.attron(curses.A_REVERSE)
            self.stdscr.addstr(h - 1, 0, status)
            self.stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

        # Position hardware cursor
        visible_row = self.cursor_row - self.scroll_offset
        cursor_col = min(self.cursor_col, w - 1)
        with contextlib.suppress(curses.error):
            self.stdscr.move(visible_row, cursor_col)

        self.stdscr.refresh()

    def _scroll_to_cursor(self) -> None:
        h, _ = self.stdscr.getmaxyx()
        text_area_h = h - 1
        if self.cursor_row < self.scroll_offset:
            self.scroll_offset = self.cursor_row
        elif self.cursor_row >= self.scroll_offset + text_area_h:
            self.scroll_offset = self.cursor_row - text_area_h + 1

    # --- Cursor movement --------------------------------------------------

    def _clamp_col(self) -> None:
        self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))

    def _move_up(self) -> None:
        if self.cursor_row > 0:
            self.cursor_row -= 1
            self._clamp_col()

    def _move_down(self) -> None:
        if self.cursor_row < len(self.lines) - 1:
            self.cursor_row += 1
            self._clamp_col()

    def _move_left(self) -> None:
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_row > 0:
            self.cursor_row -= 1
            self.cursor_col = len(self.lines[self.cursor_row])

    def _move_right(self) -> None:
        line = self.lines[self.cursor_row]
        if self.cursor_col < len(line):
            self.cursor_col += 1
        elif self.cursor_row < len(self.lines) - 1:
            self.cursor_row += 1
            self.cursor_col = 0

    def _home(self) -> None:
        self.cursor_col = 0

    def _end(self) -> None:
        self.cursor_col = len(self.lines[self.cursor_row])

    # --- Text editing -----------------------------------------------------

    def _insert_char(self, ch: str) -> None:
        line = self.lines[self.cursor_row]
        self.lines[self.cursor_row] = line[: self.cursor_col] + ch + line[self.cursor_col :]
        self.cursor_col += 1
        self.modified = True

    def _newline(self) -> None:
        line = self.lines[self.cursor_row]
        self.lines[self.cursor_row] = line[: self.cursor_col]
        self.lines.insert(self.cursor_row + 1, line[self.cursor_col :])
        self.cursor_row += 1
        self.cursor_col = 0
        self.modified = True

    def _backspace(self) -> None:
        if self.cursor_col > 0:
            line = self.lines[self.cursor_row]
            self.lines[self.cursor_row] = line[: self.cursor_col - 1] + line[self.cursor_col :]
            self.cursor_col -= 1
            self.modified = True
        elif self.cursor_row > 0:
            # Merge with previous line
            prev = self.lines[self.cursor_row - 1]
            curr = self.lines[self.cursor_row]
            self.cursor_col = len(prev)
            self.lines[self.cursor_row - 1] = prev + curr
            del self.lines[self.cursor_row]
            self.cursor_row -= 1
            self.modified = True

    def _delete(self) -> None:
        line = self.lines[self.cursor_row]
        if self.cursor_col < len(line):
            self.lines[self.cursor_row] = line[: self.cursor_col] + line[self.cursor_col + 1 :]
            self.modified = True
        elif self.cursor_row < len(self.lines) - 1:
            # Merge next line into current
            self.lines[self.cursor_row] = line + self.lines[self.cursor_row + 1]
            del self.lines[self.cursor_row + 1]
            self.modified = True

    # --- Save / quit prompts ----------------------------------------------

    def _prompt_quit(self) -> bool:
        """Return True if we should actually quit."""
        if not self.modified:
            return True
        h, w = self.stdscr.getmaxyx()
        prompt = " Unsaved changes. Quit? [y/N]: "
        prompt = prompt[: w - 1]
        try:
            self.stdscr.attron(curses.A_REVERSE)
            self.stdscr.addstr(h - 1, 0, prompt.ljust(w - 1))
            self.stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass
        self.stdscr.refresh()
        key = self.stdscr.getch()
        return key in (ord("y"), ord("Y"))

    def _do_save(self) -> None:
        content = "\n".join(self.lines)
        if not content.strip():
            # Flash a warning in the status bar — don't save
            h, w = self.stdscr.getmaxyx()
            msg = " ⚠ Cannot save an empty note. Add some text first. "[: w - 1].ljust(w - 1)
            try:
                self.stdscr.attron(curses.A_REVERSE)
                self.stdscr.addstr(h - 1, 0, msg)
                self.stdscr.attroff(curses.A_REVERSE)
                self.stdscr.refresh()
            except curses.error:
                pass
            self.stdscr.getch()  # wait for any keypress to dismiss
            return
        self.saved_path = save_note(content, self.filepath)
        self.filepath = self.saved_path
        self.modified = False

    # --- Main loop --------------------------------------------------------

    def run(self) -> Path | None:
        curses.curs_set(1)
        self.stdscr.keypad(True)

        while True:
            self._scroll_to_cursor()
            self._draw()
            key = self.stdscr.getch()

            if key == curses.KEY_UP:
                self._move_up()
            elif key == curses.KEY_DOWN:
                self._move_down()
            elif key == curses.KEY_LEFT:
                self._move_left()
            elif key == curses.KEY_RIGHT:
                self._move_right()
            elif key == curses.KEY_HOME:
                self._home()
            elif key == curses.KEY_END:
                self._end()
            elif key == curses.KEY_BACKSPACE or key == 127:
                self._backspace()
            elif key == curses.KEY_DC:
                self._delete()
            elif key == ord("\n") or key == curses.KEY_ENTER:
                self._newline()
            elif key == 19:  # Ctrl+S
                self._do_save()
                return self.saved_path
            elif key == 17:  # Ctrl+Q
                if self._prompt_quit():
                    return None
            elif 32 <= key <= 126:
                self._insert_char(chr(key))
            # Ignore other keys silently


def open_editor(initial_text: str = "", filepath: Path | None = None) -> Path | None:
    """Launch the curses editor. Returns saved path or None if quit without saving."""
    result: list = [None]

    def _run(stdscr) -> None:
        editor = _Editor(stdscr, initial_text, filepath)
        result[0] = editor.run()

    try:
        curses.wrapper(_run)
    except Exception as exc:
        print(f"Editor error: {exc}", file=sys.stderr)
    return result[0]
