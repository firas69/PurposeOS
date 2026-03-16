"""
gui/dialogs/action.py — Add/Edit Action dialog and action type utilities

Owns the action type label/key mappings used in both the dialog and the
actions table in main.py, plus the action status checker.

The dialog factory _make_action_dialog() builds and returns a QDialog
with a get_data() method for retrieving form values after exec().
"""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from purposeos.gui._helpers import _apply_rtl, _normalise_path, t

# ─────────────────────────────────────────────────────────────────
# Action type label ↔ key mappings
# ─────────────────────────────────────────────────────────────────

_ACTION_TYPE_LABELS: dict[str, str] = {
    "open_file": "Open File",
    "open_app": "Launch App",
    "run_command": "Run Command",
    "open_url": "Open URL",
    "show_notification": "Show Notification",
}
_ACTION_TYPE_KEYS: dict[str, str] = {v: k for k, v in _ACTION_TYPE_LABELS.items()}


def _type_label(key: str) -> str:
    return _ACTION_TYPE_LABELS.get(key, key)


def _type_key(label: str) -> str:
    return _ACTION_TYPE_KEYS.get(label, label)


# ─────────────────────────────────────────────────────────────────
# Action status checker (translated)
# ─────────────────────────────────────────────────────────────────


def _check_action_status(a: dict) -> str:
    action_type = a.get("action_type")
    target = a.get("target", "").strip()

    if action_type == "open_file":
        if not target:
            return t("actions.status.no_target", "⚠ No target")
        return (
            t("actions.status.ok", "✓")
            if os.path.isfile(os.path.expanduser(target))
            else t("actions.status.file_not_found", "⚠ File not found")
        )

    if action_type == "open_app":
        if not target:
            return t("actions.status.no_target", "⚠ No target")
        if os.path.isabs(target) or target.startswith("~/"):
            return (
                t("actions.status.ok", "✓")
                if os.path.isfile(os.path.expanduser(target))
                else t("actions.status.app_not_found", "⚠ App not found")
            )
        return (
            t("actions.status.ok", "✓")
            if shutil.which(target)
            else t("actions.status.app_not_in_path", "⚠ App not in PATH")
        )

    if action_type == "open_url":
        if not target:
            return t("actions.status.no_url", "⚠ No URL")
        return (
            t("actions.status.ok", "✓")
            if target.startswith(("http://", "https://", "ftp://"))
            else t("actions.status.invalid_url", "⚠ Invalid URL")
        )

    if action_type in ("run_command", "show_notification"):
        return (
            t("actions.status.ok", "✓")
            if target
            else t("actions.status.no_command", "⚠ No command")
        )

    return "?"


# ─────────────────────────────────────────────────────────────────
# Add/Edit Action Dialog
# ─────────────────────────────────────────────────────────────────


def _make_action_dialog(parent, existing: dict | None = None):
    from PySide6.QtCore import QTime
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSpinBox,
        QTimeEdit,
        QVBoxLayout,
        QWidget,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(
        t("actions.dialog.edit_title", "Edit Action")
        if existing
        else t("actions.dialog.add_title", "Add Action")
    )
    dlg.setMinimumWidth(520)
    _apply_rtl(dlg)

    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    form.setSpacing(12)

    type_combo = QComboBox()
    type_combo.addItems(list(_ACTION_TYPE_LABELS.values()))
    current_key = existing.get("action_type", "open_app") if existing else "open_app"
    type_combo.setCurrentText(_type_label(current_key))

    target_row = QWidget()
    target_row_layout = QHBoxLayout(target_row)
    target_row_layout.setContentsMargins(0, 0, 0, 0)
    target_row_layout.setSpacing(6)

    target_edit = QLineEdit(existing.get("target", "") if existing else "")
    target_edit.setPlaceholderText(
        t("actions.placeholder.target", "File path / app name / command / URL")
    )
    target_browse_btn = QPushButton(t("actions.btn.browse", "Browse…"))
    target_browse_btn.setObjectName("secondary")
    target_browse_btn.setFixedWidth(90)
    target_row_layout.addWidget(target_edit)
    target_row_layout.addWidget(target_browse_btn)

    path_warn = QLabel("")
    path_warn.setStyleSheet("color: #F59E0B; font-size: 12px;")
    path_warn.setWordWrap(True)
    path_warn.setVisible(False)

    notif_title_edit = QLineEdit(
        existing.get("notification_title", "Reminder") if existing else "Reminder"
    )
    notif_msg_edit = QLineEdit(existing.get("notification_message", "") if existing else "")

    trigger_combo = QComboBox()
    trigger_combo.addItems(["boot", "daily", "interval_minutes", "weekly"])
    trigger_combo.setCurrentText(existing.get("trigger", "boot") if existing else "boot")

    time_edit = QTimeEdit()
    time_edit.setDisplayFormat("HH:mm")

    interval_spin = QSpinBox()
    interval_spin.setRange(1, 1440)
    interval_spin.setSuffix(" " + t("common.min", "min"))
    interval_spin.setValue(30)

    dow_combo = QComboBox()
    dow_combo.addItems(["mon", "tue", "wed", "thu", "fri", "sat", "sun"])

    if existing:
        tv = existing.get("trigger_value")
        trig = existing.get("trigger", "boot")
        if trig == "daily" and tv:
            try:
                parts = str(tv).split(":")
                time_edit.setTime(QTime(int(parts[0]), int(parts[1] if len(parts) > 1 else 0)))
            except Exception:
                pass
        elif trig == "interval_minutes" and tv:
            with contextlib.suppress(Exception):
                interval_spin.setValue(int(tv))
        elif trig == "weekly" and tv:
            dow_combo.setCurrentText(str(tv))

    enabled_check = QCheckBox(t("actions.check.enabled", "Enabled"))
    enabled_check.setChecked(existing.get("enabled", True) if existing else True)

    def _on_trigger(text):
        time_edit.setVisible(text == "daily")
        interval_spin.setVisible(text == "interval_minutes")
        dow_combo.setVisible(text == "weekly")

    def _on_type(label):
        key = _type_key(label)
        is_notif = key == "show_notification"
        is_file = key == "open_file"
        is_app = key == "open_app"
        notif_title_edit.setVisible(is_notif)
        notif_msg_edit.setVisible(is_notif)
        target_row.setVisible(not is_notif)
        target_browse_btn.setVisible(is_file or is_app)
        path_warn.setVisible(False)
        if is_file:
            target_edit.setPlaceholderText(
                t("actions.placeholder.file", "File path (e.g. ~/Documents/todo.txt)")
            )
            _check_path(target_edit.text())
        elif is_app:
            target_edit.setPlaceholderText(
                t("actions.placeholder.app", "App binary or .desktop ID (e.g. firefox)")
            )
        elif key == "open_url":
            target_edit.setPlaceholderText(
                t("actions.placeholder.url", "URL (e.g. https://example.com)")
            )
        elif key == "run_command":
            target_edit.setPlaceholderText(
                t("actions.placeholder.command", "Shell command (e.g. notify-send 'Hello')")
            )
        else:
            target_edit.setPlaceholderText(t("actions.placeholder.target_gen", "Target"))

    def _browse_target():
        key = _type_key(type_combo.currentText())
        current = target_edit.text().strip()
        if current:
            try:
                candidate = Path(current).expanduser()
                start = str(candidate.parent if candidate.is_file() else candidate)
            except Exception:
                start = str(Path.home())
        else:
            start = str(Path.home())
        if key == "open_file":
            chosen, _ = QFileDialog.getOpenFileName(
                dlg, "Select File to Open", start, "All files (*)"
            )
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                dlg, "Select Application Binary", "/usr/bin", "All files (*)"
            )
        if chosen:
            target_edit.setText(chosen)

    target_browse_btn.clicked.connect(_browse_target)

    def _check_path(text):
        if not text or _type_key(type_combo.currentText()) != "open_file":
            path_warn.setVisible(False)
            return
        normalised = _normalise_path(text)
        if normalised != text:
            path_warn.setText(
                t("common.path_warn_mean", "⚠ Did you mean: {path}").replace("{path}", normalised)
            )
            path_warn.setVisible(True)
        else:
            expanded = os.path.expanduser(text)
            if not os.path.exists(expanded):
                path_warn.setText(
                    t("common.path_warn_missing", "⚠ Path not found: {path}").replace(
                        "{path}", expanded
                    )
                )
                path_warn.setVisible(True)
            else:
                path_warn.setVisible(False)

    trigger_combo.currentTextChanged.connect(_on_trigger)
    type_combo.currentTextChanged.connect(_on_type)
    target_edit.textChanged.connect(_check_path)
    _on_trigger(trigger_combo.currentText())
    _on_type(type_combo.currentText())

    form.addRow(t("actions.field.type", "Type:"), type_combo)
    form.addRow(t("actions.field.target", "Target:"), target_row)
    form.addRow("", path_warn)
    form.addRow(t("actions.field.notif_title", "Notif. Title:"), notif_title_edit)
    form.addRow(t("actions.field.notif_message", "Notif. Message:"), notif_msg_edit)
    form.addRow(t("actions.field.trigger", "Trigger:"), trigger_combo)
    form.addRow(t("actions.field.time", "Time:"), time_edit)
    form.addRow(t("actions.field.interval", "Interval:"), interval_spin)
    form.addRow(t("actions.field.day_of_week", "Day of week:"), dow_combo)
    form.addRow("", enabled_check)

    layout.addLayout(form)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    def get_data() -> dict:
        trigger = trigger_combo.currentText()
        if trigger == "daily":
            tv = time_edit.time().toString("HH:mm")
        elif trigger == "interval_minutes":
            tv = interval_spin.value()
        elif trigger == "weekly":
            tv = dow_combo.currentText()
        else:
            tv = None
        target = _normalise_path(target_edit.text())
        return {
            "action_type": _type_key(type_combo.currentText()),
            "target": target,
            "trigger": trigger,
            "trigger_value": tv,
            "notification_title": notif_title_edit.text(),
            "notification_message": notif_msg_edit.text(),
            "enabled": enabled_check.isChecked(),
        }

    dlg.get_data = get_data
    return dlg
