from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


def _save_note(content: str) -> Path:
    """Save to the configured notes directory. Returns saved path."""
    from purposeos.core.config import get_notes_dir

    d = get_notes_dir()
    d.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    path = d / filename
    path.write_text(content, encoding="utf-8")
    return path


_STYLE = """
/* The main floating HUD container */
QWidget#quicknote {
    background-color: rgba(5, 7, 10, 0.85); /* Obsidian base */
    border: 1px solid rgba(0, 242, 255, 0.3); /* Cyber Cyan edge */
    border-radius: 12px;
}

QPlainTextEdit {
    background-color: rgba(30, 41, 59, 0.5); /* Deep glass */
    color: #E2E8F0;
    border: 1px solid rgba(255, 255, 255, 0.1); /* Light-leak inner border */
    border-radius: 8px;
    font-family: "JetBrains Mono", "Fira Code", "Monospace";
    font-size: 14px;
    padding: 10px;
    selection-background-color: rgba(0, 242, 255, 0.3);
    selection-color: #FFFFFF;
}
QPlainTextEdit:focus {
    border-color: rgba(0, 242, 255, 0.6);
    background-color: rgba(30, 41, 59, 0.7);
}

QLabel#hint {
    color: #64748B;
    font-size: 11px;
    font-family: "Inter", sans-serif;
}
QLabel#warn {
    color: #D946EF; /* Electric Violet for warnings */
    font-size: 11px;
    font-weight: bold;
}

QPushButton#save {
    background-color: rgba(0, 242, 255, 0.15);
    color: #00F2FF;
    border: 1px solid rgba(0, 242, 255, 0.4);
    border-radius: 6px;
    padding: 7px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#save:hover  {
    background-color: rgba(0, 242, 255, 0.3);
    border-color: #00F2FF;
}
QPushButton#save:pressed { background-color: rgba(0, 242, 255, 0.1); }

QPushButton#discard {
    background-color: transparent;
    color: #94A3B8;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 7px 20px;
    font-size: 13px;
}
QPushButton#discard:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #E2E8F0;
}
"""


def run() -> None:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PurposeOS Quick Note")
    app.setStyleSheet(_STYLE)

    win = QWidget()
    win.setObjectName("quicknote")
    win.setWindowTitle("Quick Note")
    win.resize(560, 340)
    win.setMinimumSize(QSize(400, 240))

    # --- TECHNICAL REQUIREMENTS FOR TRANSPARENCY ---
    # 1. FramelessWindowHint removes OS chrome, allowing our border-radius and alpha channel to show.
    # 2. WA_TranslucentBackground tells Qt not to paint the underlying opaque layer.
    win.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # Centre on screen
    screen = app.primaryScreen().availableGeometry()
    win.move(
        screen.center().x() - win.width() // 2,
        screen.center().y() - win.height() // 2,
    )

    layout = QVBoxLayout(win)
    layout.setContentsMargins(14, 14, 14, 14)  # Slightly thicker margins for the border glow
    layout.setSpacing(8)

    editor = QPlainTextEdit()
    editor.setPlaceholderText("Write your note here…")
    layout.addWidget(editor)

    # Bottom bar
    bar = QHBoxLayout()
    bar.setSpacing(8)

    status_lbl = QLabel("Ctrl+S to save  ·  Esc to discard")
    status_lbl.setObjectName("hint")
    bar.addWidget(status_lbl)
    bar.addStretch()

    discard_btn = QPushButton("Discard")
    discard_btn.setObjectName("discard")
    save_btn = QPushButton("Save")
    save_btn.setObjectName("save")
    bar.addWidget(discard_btn)
    bar.addWidget(save_btn)
    layout.addLayout(bar)

    saved = [False]

    def _save() -> None:
        content = editor.toPlainText().strip()
        if not content:
            status_lbl.setText("⚠  Write something first.")
            status_lbl.setObjectName("warn")
            status_lbl.setStyleSheet("color: #D946EF; font-size: 11px; font-weight: bold;")
            editor.setFocus()
            return
        _save_note(editor.toPlainText())
        saved[0] = True
        win.close()

    def _discard() -> None:
        win.close()

    save_btn.clicked.connect(_save)
    discard_btn.clicked.connect(_discard)

    QShortcut(QKeySequence("Ctrl+S"), win).activated.connect(_save)
    QShortcut(QKeySequence("Escape"), win).activated.connect(_discard)

    win.show()
    editor.setFocus()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
