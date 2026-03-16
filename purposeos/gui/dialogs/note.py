"""
gui/dialogs/note.py — Note viewer/editor modal dialog

Builds a QDialog for viewing (read-only) or editing a note file.
The dialog attaches a saved_path() accessor when in edit mode so the
caller can find where the note was written after exec() returns.
"""

from __future__ import annotations

from pathlib import Path

from purposeos.gui._helpers import _apply_rtl, t


def _make_note_dialog(parent, filepath: Path | None = None, read_only: bool = False):
    from PySide6.QtGui import QFont, QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QDialog,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
    )

    try:
        from purposeos.notes import read_note, save_note
    except ImportError:
        from notes import read_note, save_note  # type: ignore[no-redef]

    dlg = QDialog(parent)
    dlg.resize(720, 520)
    _apply_rtl(dlg)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(8)

    if read_only:
        dlg.setWindowTitle(filepath.name if filepath else t("notes.dialog.new_title", "Note"))
        fname = filepath.name if filepath else ""
        header = QLabel(t("notes.dialog.view_prefix", "📄  ") + fname)
    elif filepath:
        dlg.setWindowTitle(t("notes.dialog.edit_prefix", "Edit — ") + filepath.name)
        header = QLabel(t("notes.dialog.edit_prefix", "✏️  Editing: ") + filepath.name)
    else:
        dlg.setWindowTitle(t("notes.dialog.new_title", "New Note"))
        header = QLabel(t("notes.dialog.new_header", "✏️  New Note"))
    header.setStyleSheet("color: #94A3B8; font-size: 12px; padding-bottom: 2px;")
    layout.addWidget(header)

    editor = QPlainTextEdit()
    editor.setFont(QFont("Monospace", 12))
    editor.setReadOnly(read_only)
    if filepath and filepath.exists():
        editor.setPlainText(read_note(filepath))
    layout.addWidget(editor)

    bottom = QHBoxLayout()
    char_lbl = QLabel(t("notes.dialog.chars", "0 chars").replace("{n}", "0"))
    char_lbl.setStyleSheet("color: #475569; font-size: 11px;")
    bottom.addWidget(char_lbl)
    bottom.addStretch()

    def _update_counter():
        n = len(editor.toPlainText().strip())
        char_lbl.setText(t("notes.dialog.chars", "{n} chars").replace("{n}", str(n)))
        char_lbl.setStyleSheet(
            "color: #EF4444; font-size: 11px;" if n == 0 else "color: #475569; font-size: 11px;"
        )

    editor.textChanged.connect(_update_counter)
    _update_counter()

    if read_only:
        close_btn = QPushButton(t("notes.btn.close", "Close"))
        close_btn.clicked.connect(dlg.accept)
        bottom.addWidget(close_btn)
    else:
        save_btn = QPushButton(t("notes.dialog.save_btn", "Save  (Ctrl+S)"))
        cancel_btn = QPushButton(t("notes.dialog.cancel_btn", "Cancel"))
        cancel_btn.setObjectName("secondary")
        bottom.addWidget(save_btn)
        bottom.addWidget(cancel_btn)

        _saved_path: list = [None]

        def _save():
            content = editor.toPlainText().strip()
            if not content:
                char_lbl.setText(t("notes.dialog.empty_warning", "⚠ Cannot save an empty note"))
                char_lbl.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
                editor.setFocus()
                return
            _saved_path[0] = save_note(editor.toPlainText(), filepath)
            dlg.accept()

        save_btn.clicked.connect(_save)
        cancel_btn.clicked.connect(dlg.reject)
        QShortcut(QKeySequence("Ctrl+S"), dlg).activated.connect(_save)
        QShortcut(QKeySequence("Ctrl+Q"), dlg).activated.connect(dlg.reject)

        dlg.saved_path = lambda: _saved_path[0]

    layout.addLayout(bottom)
    return dlg
