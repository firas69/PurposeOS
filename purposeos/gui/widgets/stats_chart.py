"""
gui/widgets/stats_chart.py — App-usage bar chart widget

Builds a QWidget containing a date-range selector, a Refresh button,
and a horizontal bar chart showing the top-10 apps by usage duration.

Uses QChart (PySide6.QtCharts) when available, with an inline QPainter
fallback when the optional QtCharts module is not installed.

Note: this widget shows APP USAGE (tracker.db → app_sessions table).
It is distinct from the notification interaction stats shown in the
Stats section of PurposeOSWindow, which uses the notification_interactions
table and is built inline in _build_stats / _refresh_stats.
"""

from __future__ import annotations

from datetime import date, timedelta

from purposeos.gui._helpers import t


def _make_stats_widget(parent):
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)

    header = QHBoxLayout()
    title_lbl = QLabel(t("stats.heading", "App Usage"))
    title_lbl.setObjectName("heading")
    days_lbl = QLabel(t("stats.last", "Last"))
    days_spin = QSpinBox()
    days_spin.setRange(1, 90)
    days_spin.setValue(7)
    days_lbl2 = QLabel(t("stats.days", "days"))
    refresh_btn = QPushButton(t("stats.btn.refresh", "Refresh"))
    header.addWidget(title_lbl)
    header.addStretch()
    header.addWidget(days_lbl)
    header.addWidget(days_spin)
    header.addWidget(days_lbl2)
    header.addWidget(refresh_btn)
    layout.addLayout(header)

    chart_container = QWidget()
    chart_layout = QVBoxLayout(chart_container)
    layout.addWidget(chart_container, stretch=1)

    def _refresh():
        try:
            from purposeos.core.config import DATA_DIR
        except ImportError:
            from config import DATA_DIR  # type: ignore[no-redef]
        db_path = DATA_DIR / "tracker.db"
        days = days_spin.value()
        end = date.today()
        start = end - timedelta(days=days - 1)

        for i in reversed(range(chart_layout.count())):
            w = chart_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        try:
            import sqlite3

            if not db_path.exists():
                chart_layout.addWidget(
                    QLabel(t("stats.no_data", "No data yet. Run the daemon for a while first."))
                )
                return
            with sqlite3.connect(str(db_path)) as conn:
                rows = conn.execute(
                    """SELECT app_name, SUM(COALESCE(duration_sec,0)) AS total
                       FROM app_sessions WHERE date>=? AND date<=?
                       GROUP BY app_name ORDER BY total DESC LIMIT 10""",
                    (start.isoformat(), end.isoformat()),
                ).fetchall()
            if not rows:
                chart_layout.addWidget(QLabel(t("stats.no_range", "No data in selected range.")))
                return
        except Exception as e:
            chart_layout.addWidget(QLabel(f"DB error: {e}"))
            return

        try:
            from PySide6.QtCharts import (  # type: ignore
                QBarCategoryAxis,
                QBarSet,
                QChart,
                QChartView,
                QHorizontalBarSeries,
                QValueAxis,
            )
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QColor

            bar_set = QBarSet("Duration (s)")
            bar_set.setColor(QColor("#3B82F6"))
            categories = []
            for app, total in rows:
                bar_set.append(total)
                categories.append(app)

            series = QHorizontalBarSeries()
            series.append(bar_set)

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle(f"App Usage ({start} – {end})")
            chart.setBackgroundBrush(QColor("#1E293B"))
            chart.setTitleBrush(QColor("#E2E8F0"))
            chart.legend().setVisible(False)

            cat_axis = QBarCategoryAxis()
            cat_axis.append(categories)
            cat_axis.setLabelsColor(QColor("#94A3B8"))
            chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(cat_axis)

            val_axis = QValueAxis()
            val_axis.setLabelsColor(QColor("#94A3B8"))
            chart.addAxis(val_axis, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(val_axis)

            view = QChartView(chart)
            view.setRenderHint(view.renderHints())
            chart_layout.addWidget(view)

        except ImportError:
            _add_painter_chart(chart_layout, rows)

    def _add_painter_chart(target_layout, rows):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QFont, QPainter
        from PySide6.QtWidgets import QWidget

        max_val = max(r[1] for r in rows) or 1

        class BarChart(QWidget):
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = self.width(), self.height()
                bar_h = max(24, (h - 40) // len(rows))
                label_w = 140
                for i, (app, total) in enumerate(rows):
                    y = 20 + i * bar_h
                    bar_w = int((total / max_val) * (w - label_w - 80))
                    painter.setPen(QColor("#94A3B8"))
                    painter.setFont(QFont("Monospace", 11))
                    painter.drawText(QRect(4, y, label_w - 8, bar_h - 4), 0x0082, app[:18])
                    painter.fillRect(label_w, y + 4, bar_w, bar_h - 12, QColor("#3B82F6"))
                    secs = int(total)
                    h2, rem = divmod(secs, 3600)
                    m2, s2 = divmod(rem, 60)
                    dur = f"{h2}h{m2:02d}m" if h2 else f"{m2}m{s2:02d}s"
                    painter.setPen(QColor("#E2E8F0"))
                    painter.drawText(label_w + bar_w + 8, y + bar_h - 8, dur)

        bc = BarChart()
        bc.setMinimumHeight(len(rows) * 36 + 40)
        target_layout.addWidget(bc)

    refresh_btn.clicked.connect(_refresh)
    _refresh()
    return widget
