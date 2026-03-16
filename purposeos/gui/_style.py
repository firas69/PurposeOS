"""
gui/_style.py — PurposeOS Qt stylesheet

Dark base with selective glassmorphism on input surfaces.
QMainWindow and QWidget get a solid background — transparency is only
applied by quicknote.py, which sets WA_TranslucentBackground itself.
"""

_STYLESHEET = """

/* ── Base ────────────────────────────────────────────────────── */

QMainWindow {
    background-color: #060A12;
}

QWidget {
    background-color: #060A12;
    color: #E2E8F0;
    font-family: "Inter", "Segoe UI", "Noto Sans Arabic", sans-serif;
    font-size: 14px;
}

QDialog {
    background-color: #0B1628;
    color: #E2E8F0;
}

/* ── Sidebar (set inline in main.py, but keep consistent) ────── */

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 10px 18px;
    border-radius: 6px;
    margin: 2px 6px;
    color: #64748B;
}

QListWidget::item:selected {
    background-color: rgba(0, 242, 255, 0.12);
    color: #00F2FF;
    border: 1px solid rgba(0, 242, 255, 0.3);
}

QListWidget::item:hover:!selected {
    background-color: rgba(255, 255, 255, 0.04);
    color: #CBD5E1;
}

/* ── Tables ──────────────────────────────────────────────────── */

QTableWidget {
    background-color: #0B1628;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.06);
    color: #E2E8F0;
    outline: none;
}

QTableWidget::item {
    padding: 6px 10px;
    background-color: transparent;
}

QTableWidget::item:selected {
    background-color: rgba(0, 242, 255, 0.15);
    color: #00F2FF;
}

QHeaderView::section {
    background-color: #060A12;
    color: #475569;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Inputs (glassmorphism surfaces) ─────────────────────────── */

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox, QTimeEdit {
    background-color: #1E293B;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: #E2E8F0;
    padding: 6px 10px;
    outline: none;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus, QTimeEdit:focus {
    border-color: rgba(0, 242, 255, 0.6);
    background-color: #243044;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #E2E8F0;
    selection-background-color: rgba(0, 242, 255, 0.15);
    selection-color: #00F2FF;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: transparent;
    border: none;
}

/* ── Buttons ─────────────────────────────────────────────────── */

QPushButton {
    background-color: rgba(0, 242, 255, 0.1);
    color: #00F2FF;
    border: 1px solid rgba(0, 242, 255, 0.35);
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: rgba(0, 242, 255, 0.2);
    border-color: rgba(0, 242, 255, 0.7);
}

QPushButton:pressed {
    background-color: rgba(0, 242, 255, 0.08);
}

QPushButton:disabled {
    color: #334155;
    border-color: rgba(255, 255, 255, 0.08);
    background-color: transparent;
}

QPushButton#secondary {
    background-color: transparent;
    color: #94A3B8;
    border: 1px solid rgba(255, 255, 255, 0.12);
}

QPushButton#secondary:hover {
    background-color: rgba(255, 255, 255, 0.06);
    color: #E2E8F0;
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton#danger {
    background-color: rgba(239, 68, 68, 0.1);
    color: #F87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
}

QPushButton#danger:hover {
    background-color: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.7);
}

/* ── Typography ──────────────────────────────────────────────── */

QLabel {
    background-color: transparent;
    color: #CBD5E1;
}

QLabel#heading {
    font-size: 20px;
    font-weight: 700;
    color: #F1F5F9;
}

QLabel#subheading {
    font-size: 12px;
    color: #64748B;
}

/* ── Checkboxes ──────────────────────────────────────────────── */

QCheckBox {
    color: #CBD5E1;
    spacing: 8px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    background-color: #1E293B;
}

QCheckBox::indicator:checked {
    background-color: rgba(0, 242, 255, 0.25);
    border-color: rgba(0, 242, 255, 0.7);
}

/* ── Scroll bars ─────────────────────────────────────────────── */

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(0, 242, 255, 0.4);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}

QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-width: 20px;
}

/* ── Misc ────────────────────────────────────────────────────── */

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QSplitter::handle {
    background: rgba(255, 255, 255, 0.08);
}

QProgressBar {
    background-color: #0F172A;
    border: none;
    border-radius: 6px;
}

QProgressBar::chunk {
    background-color: #22C55E;
    border-radius: 6px;
}

QToolTip {
    background-color: #1E293B;
    color: #E2E8F0;
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 4px 8px;
    border-radius: 4px;
}

QMessageBox {
    background-color: #0B1628;
}

QMessageBox QLabel {
    color: #E2E8F0;
}
"""
