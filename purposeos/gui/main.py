"""
gui/main.py — PurposeOS main window and application entry point

PurposeOSWindow assembles the sidebar, navigation list, and page stack.
Each page is built by a _build_*() method that constructs its widgets,
wires its local signals, and registers its per-section keyboard shortcuts.

main() reads the language preference before creating QApplication so the
RTL layout direction is set correctly from the very first widget draw.

All helper functions, dialogs, and the stylesheet live in sub-modules:
  _style.py          — _STYLESHEET constant
  _helpers.py        — t(), is_rtl(), _apply_rtl(), _make_shortcut(), etc.
  _config_bridge.py  — _load_raw_config(), _save_raw_config(), etc.
  dialogs/reminder.py — _make_reminder_dialog()
  dialogs/action.py   — _make_action_dialog(), _check_action_status(), _type_label()
  dialogs/note.py     — _make_note_dialog()
  widgets/stats_chart.py — _make_stats_widget()
"""

from __future__ import annotations

import sys

from purposeos.gui._config_bridge import (
    _daemon_status,
    _load_raw_config,
    _reload_daemon,
    _save_raw_config,
)
from purposeos.gui._helpers import (
    _apply_rtl,
    _friendly_trigger,
    _make_shortcut,
    get_all_languages,
    get_language,
    is_rtl,
    set_language,
    t,
)
from purposeos.gui._style import _STYLESHEET
from purposeos.gui.dialogs.action import (
    _check_action_status,
    _make_action_dialog,
    _type_label,
)
from purposeos.gui.dialogs.note import _make_note_dialog
from purposeos.gui.dialogs.reminder import _make_reminder_dialog


def _check_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(
            "ERROR: PySide6 is not installed. Install it with:\n  pip install --user PySide6",
            file=sys.stderr,
        )
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────


class PurposeOSWindow:
    def __init__(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QStackedWidget,
            QVBoxLayout,
            QWidget,
        )

        self.window = QMainWindow()
        self.window.setWindowTitle(t("app.title", "PurposeOS"))
        self.window.resize(1100, 720)
        _apply_rtl(self.window)

        central = QWidget()
        self.window.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet("background-color: #0B1628; border-right: 1px solid #1E293B;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 16, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("⚡ " + t("app.name", "PurposeOS"))
        # Aligned to QListWidget inner text (24px) and matching _style.py primary color (#00F2FF)
        logo.setStyleSheet(
            "font-size:16px; font-weight:700; color:#00F2FF; padding:0 24px 16px 24px;"
        )
        sidebar_layout.addWidget(logo)

        nav = QListWidget()
        # Removed redundant inline styles to allow _style.py QListWidget rules to apply natively
        section_names = [
            t("navigation.reminders", "Reminders"),
            t("navigation.actions", "Actions"),
            t("navigation.notes", "Notes"),
            t("navigation.stats", "Stats"),
            t("navigation.settings", "Settings"),
        ]
        shortcuts_keys = ["Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5"]
        for item_name, shortcut in zip(section_names, shortcuts_keys, strict=False):
            nav.addItem(QListWidgetItem(f"{item_name}  ({shortcut})"))
        nav.setCurrentRow(0)
        sidebar_layout.addWidget(nav)
        sidebar_layout.addStretch()
        self._nav = nav

        # Keyboard shortcuts guide
        guide_label = QLabel(t("navigation.keyboard_shortcuts", "Keyboard Shortcuts"))
        guide_label.setStyleSheet(
            "font-size:11px; font-weight:600; color:#00F2FF; padding:8px 24px 4px 24px;"
        )
        sidebar_layout.addWidget(guide_label)

        guide_text = QLabel(
            f"<span style='font-size:10px; line-height:1.6;'>"
            f"<b style='color:#94A3B8;'>Alt+1</b> – {t('navigation.reminders', 'Reminders')}<br>"
            f"<b style='color:#94A3B8;'>Alt+2</b> – {t('navigation.actions', 'Actions')}<br>"
            f"<b style='color:#94A3B8;'>Alt+3</b> – {t('navigation.notes', 'Notes')}<br>"
            f"<b style='color:#94A3B8;'>Alt+4</b> – {t('navigation.stats', 'Stats')}<br>"
            f"<b style='color:#94A3B8;'>Alt+5</b> – {t('navigation.settings', 'Settings')}"
            f"</span>"
        )
        guide_text.setTextFormat(Qt.TextFormat.RichText)
        guide_text.setStyleSheet("padding:0 24px 8px 24px; color:#64748B;")
        guide_text.setWordWrap(True)
        sidebar_layout.addWidget(guide_text)

        status_lbl = QLabel(t("status.checking", "● Checking…"))
        status_lbl.setStyleSheet("color:#64748B; font-size:11px; padding:8px 24px;")
        sidebar_layout.addWidget(status_lbl)
        self._status_lbl = status_lbl

        root_layout.addWidget(sidebar)

        # ── Content stack ────────────────────────────────────────
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack)

        self._pages: dict[str, QWidget] = {}
        self._build_reminders()
        self._build_actions()
        self._build_notes()
        self._build_stats()
        self._build_settings()

        for page_name in ["Reminders", "Actions", "Notes", "Stats", "Settings"]:
            self.stack.addWidget(self._pages[page_name])

        nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Alt+1-5 global shortcuts (WindowShortcut — fires regardless of focus)
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence, QShortcut

        for idx, key in enumerate(["Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5"]):
            sc = QShortcut(QKeySequence(key), self.window)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(lambda i=idx: self._nav.setCurrentRow(i))

        self._refresh_status()

    def _page_frame(self, title: str) -> tuple:
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        page = QWidget()
        _apply_rtl(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        lbl = QLabel(title)
        lbl.setObjectName("heading")
        layout.addWidget(lbl)
        return page, layout

    def _shortcut_hint(self, keys_and_labels: list) -> str:
        """Build the rich-text shortcut hint bar: [(key, label), ...]"""
        parts = "  •  ".join(
            f"<b style='color:#94A3B8;'>{k}</b> {lbl}" for k, lbl in keys_and_labels
        )
        return f"<span style='font-size:11px; color:#64748B;'>{parts}</span>"

    # ── Reminders ────────────────────────────────────────────────

    def _build_reminders(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
        )

        page, layout = self._page_frame(t("navigation.reminders", "Reminders"))

        hint = QLabel(
            self._shortcut_hint(
                [
                    ("Ctrl+N", t("reminders.btn.add", "Add")),
                    ("Ctrl+E", t("reminders.btn.edit", "Edit")),
                    ("Ctrl+D", t("reminders.btn.delete", "Delete")),
                ]
            )
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        btn_bar = QHBoxLayout()
        add_btn = QPushButton(t("reminders.btn.add", "+ Add Reminder"))
        edit_btn = QPushButton(t("reminders.btn.edit", "Edit"))
        del_btn = QPushButton(t("reminders.btn.delete", "Delete"))
        edit_btn.setObjectName("secondary")
        del_btn.setObjectName("danger")
        btn_bar.addWidget(add_btn)
        btn_bar.addWidget(edit_btn)
        btn_bar.addWidget(del_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            [
                t("reminders.table.title", "Title"),
                t("reminders.table.message", "Message"),
                t("reminders.table.trigger", "Trigger"),
                t("reminders.table.urgency", "Urgency"),
                t("reminders.table.enabled", "Enabled"),
            ]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table)

        def _load():
            cfg = _load_raw_config()
            reminders = cfg.get("reminders") or []
            table.setRowCount(len(reminders))
            for i, r in enumerate(reminders):
                trigger_str = _friendly_trigger(r.get("trigger", ""), r.get("trigger_value", ""))
                table.setItem(i, 0, QTableWidgetItem(str(r.get("title", ""))))
                table.setItem(i, 1, QTableWidgetItem(str(r.get("message", ""))[:60]))
                table.setItem(i, 2, QTableWidgetItem(trigger_str))
                table.setItem(i, 3, QTableWidgetItem(str(r.get("urgency", "normal"))))
                table.setItem(
                    i,
                    4,
                    QTableWidgetItem(
                        t("common.yes", "Yes") if r.get("enabled", True) else t("common.no", "No")
                    ),
                )

        def _add():
            dlg = _make_reminder_dialog(page)
            if dlg.exec():
                cfg = _load_raw_config()
                cfg.setdefault("reminders", []).append(dlg.get_data())
                _save_raw_config(cfg)
                _reload_daemon()
                _load()

        def _edit():
            row = table.currentRow()
            if row < 0:
                return
            cfg = _load_raw_config()
            reminders = cfg.get("reminders") or []
            if row >= len(reminders):
                return
            dlg = _make_reminder_dialog(page, existing=reminders[row])
            if dlg.exec():
                reminders[row] = dlg.get_data()
                cfg["reminders"] = reminders
                _save_raw_config(cfg)
                _reload_daemon()
                _load()

        def _delete():
            row = table.currentRow()
            if row < 0:
                return
            reply = QMessageBox.question(
                page,
                t("reminders.delete.title", "Delete"),
                t("reminders.delete.confirm", "Delete this reminder?"),
            )
            if reply == QMessageBox.StandardButton.Yes:
                cfg = _load_raw_config()
                reminders = cfg.get("reminders") or []
                if row < len(reminders):
                    del reminders[row]
                    cfg["reminders"] = reminders
                    _save_raw_config(cfg)
                    _reload_daemon()
                    _load()

        add_btn.clicked.connect(_add)
        edit_btn.clicked.connect(_edit)
        del_btn.clicked.connect(_delete)
        _make_shortcut("Ctrl+N", page, _add)
        _make_shortcut("Ctrl+E", page, _edit)
        _make_shortcut("Ctrl+D", page, _delete)
        _load()
        self._pages["Reminders"] = page

    # ── Actions ──────────────────────────────────────────────────

    def _build_actions(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
        )

        page, layout = self._page_frame(t("navigation.actions", "Actions"))

        hint = QLabel(
            self._shortcut_hint(
                [
                    ("Ctrl+N", t("actions.btn.add", "Add")),
                    ("Ctrl+E", t("actions.btn.edit", "Edit")),
                    ("Ctrl+D", t("actions.btn.delete", "Delete")),
                ]
            )
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        btn_bar = QHBoxLayout()
        add_btn = QPushButton(t("actions.btn.add", "+ Add Action"))
        edit_btn = QPushButton(t("actions.btn.edit", "Edit"))
        del_btn = QPushButton(t("actions.btn.delete", "Delete"))
        edit_btn.setObjectName("secondary")
        del_btn.setObjectName("danger")
        btn_bar.addWidget(add_btn)
        btn_bar.addWidget(edit_btn)
        btn_bar.addWidget(del_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            [
                t("actions.table.type", "Type"),
                t("actions.table.target", "Target"),
                t("actions.table.trigger", "Trigger"),
                t("actions.table.status", "Status"),
                t("actions.table.enabled", "Enabled"),
            ]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table)

        def _load():
            cfg = _load_raw_config()
            actions = cfg.get("actions") or []
            table.setRowCount(len(actions))
            for i, a in enumerate(actions):
                trigger_str = _friendly_trigger(a.get("trigger", ""), a.get("trigger_value", ""))
                table.setItem(i, 0, QTableWidgetItem(_type_label(str(a.get("action_type", "")))))
                table.setItem(i, 1, QTableWidgetItem(str(a.get("target", ""))[:50]))
                table.setItem(i, 2, QTableWidgetItem(trigger_str))
                table.setItem(i, 3, QTableWidgetItem(_check_action_status(a)))
                table.setItem(
                    i,
                    4,
                    QTableWidgetItem(
                        t("common.yes", "Yes") if a.get("enabled", True) else t("common.no", "No")
                    ),
                )

        def _add():
            dlg = _make_action_dialog(page)
            if dlg.exec():
                cfg = _load_raw_config()
                cfg.setdefault("actions", []).append(dlg.get_data())
                _save_raw_config(cfg)
                _reload_daemon()
                _load()

        def _edit():
            row = table.currentRow()
            if row < 0:
                return
            cfg = _load_raw_config()
            actions = cfg.get("actions") or []
            if row >= len(actions):
                return
            dlg = _make_action_dialog(page, existing=actions[row])
            if dlg.exec():
                actions[row] = dlg.get_data()
                cfg["actions"] = actions
                _save_raw_config(cfg)
                _reload_daemon()
                _load()

        def _delete():
            row = table.currentRow()
            if row < 0:
                return
            reply = QMessageBox.question(
                page,
                t("actions.delete.title", "Delete"),
                t("actions.delete.confirm", "Delete this action?"),
            )
            if reply == QMessageBox.StandardButton.Yes:
                cfg = _load_raw_config()
                actions = cfg.get("actions") or []
                if row < len(actions):
                    del actions[row]
                    cfg["actions"] = actions
                    _save_raw_config(cfg)
                    _reload_daemon()
                    _load()

        add_btn.clicked.connect(_add)
        edit_btn.clicked.connect(_edit)
        del_btn.clicked.connect(_delete)
        _make_shortcut("Ctrl+N", page, _add)
        _make_shortcut("Ctrl+E", page, _edit)
        _make_shortcut("Ctrl+D", page, _delete)
        _load()
        self._pages["Actions"] = page

    # ── Notes ────────────────────────────────────────────────────

    def _build_notes(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
        )

        try:
            from purposeos.notes import delete_note, list_notes
        except ImportError:
            from notes import delete_note, list_notes  # type: ignore[no-redef]

        page, layout = self._page_frame(t("navigation.notes", "Notes"))

        hint = QLabel(
            self._shortcut_hint(
                [
                    ("Ctrl+N", t("notes.btn.new", "New")),
                    ("Ctrl+V", t("notes.btn.view", "View")),
                    ("Ctrl+E", t("notes.btn.edit", "Edit")),
                    ("Ctrl+D", t("notes.btn.delete", "Delete")),
                ]
            )
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        dbl_hint = QLabel(t("notes.hint.double_click", "Double-click a note to view it."))
        dbl_hint.setStyleSheet("color: #475569; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(dbl_hint)

        btn_bar = QHBoxLayout()
        new_btn = QPushButton(t("notes.btn.new", "+ New"))
        view_btn = QPushButton(t("notes.btn.view", "View"))
        edit_btn = QPushButton(t("notes.btn.edit", "Edit"))
        del_btn = QPushButton(t("notes.btn.delete", "Delete"))
        view_btn.setObjectName("secondary")
        edit_btn.setObjectName("secondary")
        del_btn.setObjectName("danger")
        for b in (new_btn, view_btn, edit_btn, del_btn):
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(
            [
                t("notes.table.date", "Date"),
                t("notes.table.filename", "Filename"),
                t("notes.table.preview", "Preview"),
            ]
        )
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table)

        def _load():
            notes = list_notes()
            table.setRowCount(len(notes))
            for i, path in enumerate(notes):
                try:
                    preview = path.read_text(encoding="utf-8")[:80].replace("\n", " ").strip()
                except Exception:
                    preview = "[unreadable]"
                try:
                    date_str = path.stem[:10]
                    time_str = path.stem[11:].replace("-", ":")
                    display_date = f"{date_str}  {time_str}"
                except Exception:
                    display_date = path.stem
                table.setItem(i, 0, QTableWidgetItem(display_date))
                table.setItem(i, 1, QTableWidgetItem(path.name))
                table.setItem(i, 2, QTableWidgetItem(preview))
            if table.rowCount() > 0:
                table.selectRow(0)

        def _selected_note():
            row = table.currentRow()
            if row < 0:
                return None
            notes = list_notes()
            return notes[row] if row < len(notes) else None

        def _new():
            _make_note_dialog(page).exec()
            _load()

        def _view():
            path = _selected_note()
            if path:
                _make_note_dialog(page, filepath=path, read_only=True).exec()

        def _edit():
            path = _selected_note()
            if path:
                _make_note_dialog(page, filepath=path).exec()
                _load()

        def _delete():
            path = _selected_note()
            if not path:
                return
            name = path.name
            reply = QMessageBox.question(
                page,
                t("notes.delete.title", "Delete Note"),
                t("notes.delete.confirm", 'Delete "{name}"?\nThis cannot be undone.').replace(
                    "{name}", name
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Yes:
                delete_note(path)
                _load()

        def _on_double_click(row, _col):
            notes = list_notes()
            if row < len(notes):
                _make_note_dialog(page, filepath=notes[row], read_only=True).exec()

        new_btn.clicked.connect(_new)
        view_btn.clicked.connect(_view)
        edit_btn.clicked.connect(_edit)
        del_btn.clicked.connect(_delete)
        table.cellDoubleClicked.connect(_on_double_click)
        _make_shortcut("Ctrl+N", page, _new)
        _make_shortcut("Ctrl+V", page, _view)
        _make_shortcut("Ctrl+E", page, _edit)
        _make_shortcut("Ctrl+D", page, _delete)
        _load()
        self._pages["Notes"] = page

    # ── Stats ────────────────────────────────────────────────────

    # ── Stats ────────────────────────────────────────────────────
    #
    # Shows per-reminder average response time with a this-week vs
    # last-week trend. Lower avg = faster response = better focus.
    # One scroll area, one Refresh button, nothing else.

    def _build_stats(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
            QVBoxLayout,
            QWidget,
        )

        page, layout = self._page_frame(t("navigation.stats", "Stats"))

        hint = QLabel(
            self._shortcut_hint(
                [
                    ("Ctrl+R", t("stats.btn.refresh", "Refresh")),
                ]
            )
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        container = QWidget()
        self._stats_inner = QVBoxLayout(container)
        self._stats_inner.setSpacing(8)
        self._stats_inner.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton(t("stats.btn.refresh", "↻  Refresh"))
        # Removed hardcoded blue style so _style.py primary style maps natively here too
        refresh_btn.clicked.connect(self._refresh_stats)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

        _make_shortcut("Ctrl+R", page, self._refresh_stats)
        self._pages["Stats"] = page
        self._refresh_stats()

    def _refresh_stats(self):
        import sqlite3
        from datetime import date, timedelta

        try:
            from purposeos.core.config import DATA_DIR
        except ImportError:
            from config import DATA_DIR  # type: ignore[no-redef]

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

        while self._stats_inner.count():
            item = self._stats_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        db_path = DATA_DIR / "tracker.db"

        if not db_path.exists():
            lbl = QLabel(
                t("stats.no_daemon", "No data yet — start the daemon so reminders can fire.")
            )
            lbl.setStyleSheet("color: #94A3B8; padding: 16px;")
            self._stats_inner.addWidget(lbl)
            return

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        last_start = week_start - timedelta(days=7)
        last_end = week_start - timedelta(days=1)

        def _query(start: str, end: str):
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    """SELECT
                          COALESCE(NULLIF(title,''), message, '(unknown)') AS label,
                          AVG(response_sec)  AS avg_sec,
                          COUNT(*)           AS interactions
                       FROM notification_interactions
                       WHERE action      = 'done'
                         AND response_sec IS NOT NULL
                         AND DATE(shown_at) >= ?
                         AND DATE(shown_at) <= ?
                       GROUP BY label
                       ORDER BY avg_sec ASC""",
                    (start, end),
                ).fetchall()

        try:
            this_week_rows = _query(week_start.isoformat(), today.isoformat())
            last_week_map = {
                row["label"]: float(row["avg_sec"])
                for row in _query(last_start.isoformat(), last_end.isoformat())
            }
        except Exception as exc:
            lbl = QLabel(f"DB error: {exc}")
            lbl.setStyleSheet("color: #EF4444; padding: 16px;")
            self._stats_inner.addWidget(lbl)
            return

        # Section heading
        heading = QLabel(t("stats.response_heading", "REMINDER RESPONSE TIMES — THIS WEEK"))
        heading.setStyleSheet(
            "color: #94A3B8; font-size: 11px; font-weight: 600;"
            " letter-spacing: 1px; padding: 4px 2px 8px 2px;"
        )
        self._stats_inner.addWidget(heading)

        sub = QLabel(t("stats.response_sub", "Lower avg = faster response = better focus"))
        sub.setStyleSheet("color: #334155; font-size: 11px; padding: 0 2px 10px 2px;")
        self._stats_inner.addWidget(sub)

        if not this_week_rows:
            lbl = QLabel(t("stats.no_interactions", "No reminder responses recorded this week."))
            lbl.setStyleSheet("color: #475569; padding: 4px 2px; font-size: 13px;")
            self._stats_inner.addWidget(lbl)
            return

        def _fmt(seconds: float) -> str:
            s = int(seconds)
            m, sec = divmod(s, 60)
            return f"{m}m {sec:02d}s" if m else f"{s}s"

        for row in this_week_rows:
            label = str(row["label"])
            avg_sec = float(row["avg_sec"])
            count = int(row["interactions"])
            prev_avg = last_week_map.get(label)

            # Trend
            if prev_avg is None:
                trend_text = "—"
                trend_color = "#475569"
            elif abs(avg_sec - prev_avg) < 2:
                trend_text = "≈ same as last week"
                trend_color = "#475569"
            elif avg_sec < prev_avg:
                trend_text = f"↓ {_fmt(prev_avg - avg_sec)} faster"
                trend_color = "#22C55E"
            else:
                trend_text = f"↑ {_fmt(avg_sec - prev_avg)} slower"
                trend_color = "#EF4444"

            card = QFrame()
            card.setStyleSheet("QFrame { background-color: #1E293B; border-radius: 8px; }")
            row_layout = QHBoxLayout(card)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(12)

            name_lbl = QLabel(label[:50] + ("…" if len(label) > 50 else ""))
            name_lbl.setStyleSheet("color: #E2E8F0; font-size: 13px;")
            row_layout.addWidget(name_lbl, stretch=3)

            avg_lbl = QLabel(
                f"<b style='color:#3B82F6'>{_fmt(avg_sec)}</b>"
                f"<span style='color:#475569'> avg</span>"
            )
            avg_lbl.setTextFormat(Qt.TextFormat.RichText)
            avg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_layout.addWidget(avg_lbl, stretch=1)

            trend_lbl = QLabel(
                f"<span style='color:{trend_color}'>{trend_text}</span>"
                f"<span style='color:#334155'>  ·  {count}×</span>"
            )
            trend_lbl.setTextFormat(Qt.TextFormat.RichText)
            trend_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            trend_lbl.setStyleSheet("font-size: 12px;")
            row_layout.addWidget(trend_lbl, stretch=2)

            self._stats_inner.addWidget(card)

    # ── Settings ─────────────────────────────────────────────────

    def _build_settings(self):
        from pathlib import Path

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QSpinBox,
            QWidget,
        )

        page, layout = self._page_frame(t("navigation.settings", "Settings"))

        hint = QLabel(
            self._shortcut_hint(
                [
                    ("Ctrl+S", t("settings.save", "Save")),
                ]
            )
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setSpacing(12)

        log_edit = QLineEdit()
        log_edit.setPlaceholderText("INFO")
        sound_cmd_edit = QLineEdit()
        sound_cmd_edit.setPlaceholderText("paplay")
        timeout_spin = QSpinBox()
        timeout_spin.setRange(1000, 300000)
        timeout_spin.setSuffix(" " + t("settings.ms", "ms"))
        screen_wide_check = QCheckBox(t("settings.screen_wide_default", "Screen-wide by default"))
        poll_spin = QSpinBox()
        poll_spin.setRange(1, 60)
        poll_spin.setSuffix(" " + t("settings.sec", "sec"))

        notes_row = QWidget()
        notes_row_layout = QHBoxLayout(notes_row)
        notes_row_layout.setContentsMargins(0, 0, 0, 0)
        notes_row_layout.setSpacing(6)
        notes_dir_edit = QLineEdit()
        notes_dir_edit.setPlaceholderText("Default (~/.config/automation-daemon/notes)")
        notes_browse_btn = QPushButton("Browse…")
        notes_browse_btn.setObjectName("secondary")
        notes_browse_btn.setFixedWidth(90)
        notes_row_layout.addWidget(notes_dir_edit)
        notes_row_layout.addWidget(notes_browse_btn)

        language_combo = QComboBox()
        all_langs = get_all_languages()
        for lang_code, lang_name in all_langs.items():
            language_combo.addItem(lang_name, lang_code)

        def _browse_notes():
            current = notes_dir_edit.text().strip()
            start = current if current else str(Path.home())
            chosen = QFileDialog.getExistingDirectory(page, "Select Notes Folder", start)
            if chosen:
                notes_dir_edit.setText(chosen)

        notes_browse_btn.clicked.connect(_browse_notes)

        def _load_settings():
            cfg = _load_raw_config()
            s = cfg.get("settings") or {}
            log_edit.setText(str(s.get("log_level", "INFO")))
            sound_cmd_edit.setText(str(s.get("sound_command", "paplay")))
            timeout_spin.setValue(int(s.get("notification_timeout_ms", 30000)))
            screen_wide_check.setChecked(bool(s.get("screen_wide_default", True)))
            poll_spin.setValue(int(s.get("tracker_poll_interval_sec", 5)))
            notes_dir_edit.setText(str(s.get("notes_dir", "") or ""))
            current_lang = s.get("language", "en")
            idx = language_combo.findData(current_lang)
            if idx >= 0:
                language_combo.setCurrentIndex(idx)

        def _save_settings():
            cfg = _load_raw_config()
            selected_lang = language_combo.currentData() or "en"
            old_lang = get_language()
            set_language(selected_lang)
            cfg["settings"] = {
                "log_level": log_edit.text() or "INFO",
                "sound_command": sound_cmd_edit.text() or "paplay",
                "notification_timeout_ms": timeout_spin.value(),
                "screen_wide_default": screen_wide_check.isChecked(),
                "tracker_poll_interval_sec": poll_spin.value(),
                "notes_dir": notes_dir_edit.text().strip(),
                "language": selected_lang,
            }
            _save_raw_config(cfg)
            _reload_daemon()

            if selected_lang != old_lang:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.information(
                    page,
                    t("dialogs.language_changed", "Language Changed"),
                    t(
                        "dialogs.language_restart_message",
                        "Language preference has been saved.\n"
                        "Please restart the application to see the changes in effect.",
                    ),
                )

        form.addRow(t("settings.log_level", "Log level:"), log_edit)
        form.addRow(t("settings.sound_command", "Sound command:"), sound_cmd_edit)
        form.addRow(t("settings.notification_timeout", "Notification timeout:"), timeout_spin)
        form.addRow("", screen_wide_check)
        form.addRow(t("settings.tracker_poll_interval", "Tracker poll interval:"), poll_spin)
        form.addRow(t("settings.notes_folder", "Notes folder:"), notes_row)
        form.addRow(t("settings.language", "Language:"), language_combo)

        layout.addWidget(form_widget)
        save_btn = QPushButton(t("settings.save", "Save & Reload Daemon"))
        save_btn.clicked.connect(_save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

        _make_shortcut("Ctrl+S", page, _save_settings)
        _load_settings()
        self._pages["Settings"] = page

    # ── Status bar ───────────────────────────────────────────────

    def _refresh_status(self):
        status = _daemon_status()
        running = "running" in status.lower()
        colour = "#22C55E" if running else "#EF4444"
        indicator = "●" if running else "○"
        status_text = (
            t("status.daemon_running", "Daemon running")
            if running
            else t("status.daemon_stopped", "Daemon stopped")
        )
        self._status_lbl.setText(f"{indicator} {status_text}")
        # Keep horizontal padding at 24px here as well
        self._status_lbl.setStyleSheet(f"color:{colour}; font-size:11px; padding:8px 24px;")

    def show(self, start_tab: str | None = None):
        if start_tab:
            tab_names = ["Reminders", "Actions", "Notes", "Stats", "Settings"]
            if start_tab in tab_names:
                idx = tab_names.index(start_tab)
                self.stack.setCurrentIndex(idx)
                self._nav.setCurrentRow(idx)
        self.window.show()


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────


def main(start_tab: str | None = None) -> None:
    _check_pyside6()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    # Read language BEFORE creating QApplication so RTL direction is set correctly
    user_lang = "en"
    try:
        cfg = _load_raw_config()
        user_lang = cfg.get("settings", {}).get("language", "en") or "en"
        set_language(user_lang)
    except Exception as exc:
        print(f"Warning: Could not load language preference: {exc}", file=sys.stderr)
        set_language("en")

    app = QApplication(sys.argv)
    app.setApplicationName("PurposeOS")
    app.setStyleSheet(_STYLESHEET)

    if is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    win = PurposeOSWindow()
    win.show(start_tab=start_tab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()