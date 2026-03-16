"""
gui/dialogs/reminder.py — Add/Edit Reminder modal dialog

Builds and returns a QDialog for creating or editing a reminder entry.
The dialog attaches a get_data() method to itself so the caller can
retrieve the form values after exec() returns.

All strings go through t(). RTL is applied via _apply_rtl().
"""

from __future__ import annotations

from pathlib import Path

from purposeos.gui._helpers import _apply_rtl, t


def _make_reminder_dialog(parent, existing: dict | None = None):
    from PySide6.QtCore import QTime
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QSpinBox,
        QTimeEdit,
        QVBoxLayout,
        QWidget,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(
        t("reminders.dialog.edit_title", "Edit Reminder")
        if existing
        else t("reminders.dialog.add_title", "Add Reminder")
    )
    dlg.setMinimumWidth(500)
    _apply_rtl(dlg)

    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    form.setSpacing(12)

    title_edit = QLineEdit(existing.get("title", "Reminder") if existing else "Reminder")
    message_edit = QLineEdit(existing.get("message", "") if existing else "")
    urgency_combo = QComboBox()
    urgency_combo.addItems(["low", "normal", "critical"])
    urgency_combo.setCurrentText(existing.get("urgency", "normal") if existing else "normal")

    trigger_combo = QComboBox()
    trigger_combo.addItems(["boot", "daily", "interval_minutes", "weekly"])
    trigger_combo.setCurrentText(existing.get("trigger", "daily") if existing else "daily")

    time_edit = QTimeEdit()
    time_edit.setDisplayFormat("HH:mm")
    if existing and existing.get("trigger") == "daily" and existing.get("trigger_value"):
        try:
            parts = str(existing["trigger_value"]).split(":")
            time_edit.setTime(QTime(int(parts[0]), int(parts[1] if len(parts) > 1 else 0)))
        except Exception:
            pass

    interval_spin = QSpinBox()
    interval_spin.setRange(1, 1440)
    interval_spin.setSuffix(" " + t("common.min", "min"))
    if existing and existing.get("trigger") == "interval_minutes":
        interval_spin.setValue(int(existing.get("trigger_value", 30)))
    else:
        interval_spin.setValue(30)

    dow_combo = QComboBox()
    dow_combo.addItems(["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    if existing and existing.get("trigger") == "weekly":
        dow_combo.setCurrentText(str(existing.get("trigger_value", "mon")))

    screen_wide_check = QCheckBox(t("reminders.check.screen_wide", "Full-screen overlay"))
    screen_wide_check.setChecked(existing.get("screen_wide", True) if existing else True)

    auto_close_spin = QSpinBox()
    auto_close_spin.setRange(5, 300)
    auto_close_spin.setSuffix(" " + t("common.sec_suffix", "sec"))
    auto_close_spin.setValue(existing.get("auto_close_sec", 30) if existing else 30)

    # ── Sound section ──────────────────────────────────────────────
    sound_check = QCheckBox(t("reminders.check.sound", "Sound"))
    sound_names = [
        "bell",
        "message-new-instant",
        "message-sent",
        "dialog-warning",
        "dialog-error",
        "complete",
        "phone-incoming-call",
        "window-attention",
        "audio-volume-change",
        "battery-low",
        "device-added",
        "device-removed",
        "power-plug",
        "suspend-resume",
        "Custom file",
    ]
    sound_combo = QComboBox()
    sound_combo.addItems(sound_names)

    sound_custom_row = QWidget()
    sound_custom_layout = QHBoxLayout(sound_custom_row)
    sound_custom_layout.setContentsMargins(0, 0, 0, 0)
    sound_custom_layout.setSpacing(6)
    sound_custom = QLineEdit()
    sound_custom.setPlaceholderText("/path/to/sound.mp3  or  ~/Music/alert.ogg")
    sound_browse_btn = QPushButton(t("reminders.btn.browse", "Browse…"))
    sound_browse_btn.setObjectName("secondary")
    sound_browse_btn.setFixedWidth(90)
    sound_custom_layout.addWidget(sound_custom)
    sound_custom_layout.addWidget(sound_browse_btn)
    sound_custom_row.setVisible(False)

    def _browse_sound():
        chosen, _ = QFileDialog.getOpenFileName(
            dlg,
            "Select Sound File",
            str(Path.home()),
            "Audio files (*.mp3 *.ogg *.oga *.wav *.flac);;All files (*)",
        )
        if chosen:
            sound_custom.setText(chosen)

    sound_browse_btn.clicked.connect(_browse_sound)

    if existing and existing.get("sound_file"):
        sf = existing["sound_file"]
        sound_check.setChecked(True)
        if sf in sound_names:
            sound_combo.setCurrentText(sf)
        else:
            sound_combo.setCurrentText("Custom file")
            sound_custom.setText(sf)
            sound_custom_row.setVisible(True)
    else:
        sound_combo.setVisible(False)
        sound_custom_row.setVisible(False)

    def _on_sound_toggle(checked):
        sound_combo.setVisible(checked)
        sound_custom_row.setVisible(checked and sound_combo.currentText() == "Custom file")

    def _on_sound_name_change(text):
        sound_custom_row.setVisible(text == "Custom file")

    def _on_trigger_change(text):
        time_edit.setVisible(text == "daily")
        interval_spin.setVisible(text == "interval_minutes")
        dow_combo.setVisible(text == "weekly")

    sound_check.toggled.connect(_on_sound_toggle)
    sound_combo.currentTextChanged.connect(_on_sound_name_change)
    trigger_combo.currentTextChanged.connect(_on_trigger_change)
    _on_trigger_change(trigger_combo.currentText())

    enabled_check = QCheckBox(t("reminders.check.enabled", "Enabled"))
    enabled_check.setChecked(existing.get("enabled", True) if existing else True)

    form.addRow(t("reminders.field.title", "Title:"), title_edit)
    form.addRow(t("reminders.field.message", "Message:"), message_edit)
    form.addRow(t("reminders.field.trigger", "Trigger:"), trigger_combo)
    form.addRow(t("reminders.field.time", "Time:"), time_edit)
    form.addRow(t("reminders.field.interval", "Interval:"), interval_spin)
    form.addRow(t("reminders.field.day_of_week", "Day of week:"), dow_combo)
    form.addRow(t("reminders.field.urgency", "Urgency:"), urgency_combo)
    form.addRow("", screen_wide_check)
    form.addRow(t("reminders.field.auto_close", "Auto-close:"), auto_close_spin)
    form.addRow("", sound_check)
    form.addRow(t("reminders.field.sound", "Sound:"), sound_combo)
    form.addRow("", sound_custom_row)
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
        sound_file = None
        if sound_check.isChecked():
            sn = sound_combo.currentText()
            sound_file = sound_custom.text().strip() if sn == "Custom file" else sn
        return {
            "title": title_edit.text(),
            "message": message_edit.text(),
            "trigger": trigger,
            "trigger_value": tv,
            "urgency": urgency_combo.currentText(),
            "screen_wide": screen_wide_check.isChecked(),
            "auto_close_sec": auto_close_spin.value(),
            "sound_file": sound_file,
            "enabled": enabled_check.isChecked(),
        }

    dlg.get_data = get_data
    return dlg
