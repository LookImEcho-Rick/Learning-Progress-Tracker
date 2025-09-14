import sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import datetime as dt

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QPropertyAnimation
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QGraphicsOpacityEffect

import pandas as pd

from services.storage import (
    init_db,
    get_all_entries_df,
    upsert_entry,
    get_entry_by_date,
    delete_entry,
    get_setting,
    set_setting,
)
from services.metrics import compute_streaks, weekly_minutes
from services.validation import validate_entry_fields, MAX_TOPIC_LEN, MAX_TEXT_LEN, MAX_TAGS, MAX_TAG_LEN
from services.filesync import (
    create_or_sync_on_launch,
    register_atexit_export,
    export_db_to_json,
    import_json_to_db,
)
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


def _build_stylesheet(theme: str = "dark", accent: str = "#2F6FEB") -> str:
    if theme == "light":
        bg = "#FAFAFA"; fg = "#1F1F1F"; surface = "#FFFFFF"; border = "#E5E5E5"; alt = "#F3F3F3"; header = "#F5F5F7"
    else:
        bg = "#121212"; fg = "#EDEDED"; surface = "#1E1E1E"; border = "#2A2A2A"; alt = "#181818"; header = "#1B1B1B"
    return f"""
    * {{ font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial; font-size: 10pt; }}
    QWidget {{ background-color: {bg}; color: {fg}; }}
    QFrame#Card {{ background-color: {surface}; border: 1px solid {border}; border-radius: 14px; }}
    QLabel[heading="true"] {{ font-size: 14pt; font-weight: 600; padding: 4px 0 8px 0; }}
    QGroupBox {{ border: 1px solid {border}; border-radius: 10px; margin-top: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
        background-color: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 8px 10px;
        selection-background-color: {accent}; selection-color: #FFFFFF;
    }}
    QPlainTextEdit, QTextEdit {{ padding: 8px; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
        border: 1px solid {accent};
    }}
    QPushButton {{ background-color: {alt}; border: 1px solid {border}; border-radius: 12px; padding: 8px 14px; }}
    QPushButton:hover {{ background-color: {header}; border-color: {border}; }}
    QPushButton:pressed {{ background-color: #0E63A6; border-color: #0E63A6; color: #FFFFFF; }}
    QPushButton[accent="true"] {{ background-color: {accent}; border: 1px solid {accent}; color: #FFFFFF; }}
    QTabWidget::pane {{ border: 1px solid {border}; border-radius: 12px; padding: 6px; }}
    QTabBar::tab {{ background: {header}; border: 1px solid {border}; padding: 8px 16px; border-top-left-radius: 12px; border-top-right-radius: 12px; margin-right: 4px; }}
    QTabBar::tab:selected {{ background: {alt}; color: #FFFFFF; }}
    QHeaderView::section {{ background-color: {header}; color: #E0E0E0; padding: 8px; border: none; border-bottom: 1px solid {border}; }}
    QTableView {{ background-color: {alt}; alternate-background-color: {surface}; gridline-color: {border}; selection-background-color: {accent}; selection-color: #FFFFFF; }}
    QListWidget#Sidebar {{ background: {alt}; border: none; padding: 8px; outline: 0; }}
    QListWidget#Sidebar::item {{ color: #D0D0D0; padding: 10px 12px; margin: 4px 6px; border-radius: 10px; }}
    QListWidget#Sidebar::item:hover {{ background: {header}; }}
    QListWidget#Sidebar::item:selected {{ background: {accent}; color: #FFFFFF; font-weight: 600; }}
    QListWidget#Sidebar[compact=\"true\"] {{ padding: 6px; }}
    QListWidget#Sidebar[compact=\"true\"]::item {{ padding: 8px; margin: 2px 4px; }}
    QSplitter::handle {{ background: {header}; width: 2px; }}
    QScrollBar:vertical {{ background: {alt}; width: 10px; margin: 6px; border-radius: 5px; }}
    QScrollBar::handle:vertical {{ background: {accent}; min-height: 30px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: {alt}; height: 10px; margin: 6px; border-radius: 5px; }}
    QScrollBar::handle:horizontal {{ background: {accent}; min-width: 30px; border-radius: 5px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {accent}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}
    QToolTip {{ background-color: {header}; color: #FFFFFF; border: 1px solid {border}; padding: 6px; border-radius: 6px; }}
    QMessageBox {{ background-color: {surface}; }}
    QCalendarWidget QWidget {{ background-color: {surface}; }}
    QCalendarWidget QToolButton {{ background: transparent; border: none; color: {fg}; padding: 6px 8px; border-radius: 8px; }}
    QCalendarWidget QToolButton:hover {{ background: {header}; }}
    QCalendarWidget QAbstractItemView:enabled {{ selection-background-color: {accent}; selection-color: #FFFFFF; }}
    """


class LogEntryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        heading = QtWidgets.QLabel("Log Today", self); heading.setProperty("heading", True)
        outer.addWidget(heading)
        card = QtWidgets.QFrame(self); card.setObjectName("Card")
        layout = QtWidgets.QFormLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.date_edit = QtWidgets.QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QtCore.QDate.currentDate())

        self.topic_edit = QtWidgets.QLineEdit(self)
        self.topic_edit.setMaxLength(MAX_TOPIC_LEN)
        self.topic_edit.setPlaceholderText("e.g., Algorithms, React hooks, SQL joins")
        self.topic_edit.setToolTip("Short title for what you studied today")

        self.minutes_spin = QtWidgets.QSpinBox(self)
        self.minutes_spin.setRange(0, 1440)
        self.minutes_spin.setSingleStep(5)
        self.minutes_spin.setToolTip("How many minutes you studied")

        self.conf_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.conf_slider.setRange(1, 5)
        self.conf_slider.setValue(3)
        self.conf_slider.setToolTip("Confidence level for today (1-5)")

        self.practiced_edit = QtWidgets.QPlainTextEdit(self)
        self.practiced_edit.setPlaceholderText("What you practiced…")
        self.challenges_edit = QtWidgets.QPlainTextEdit(self)
        self.challenges_edit.setPlaceholderText("Any blockers or challenges…")
        self.wins_edit = QtWidgets.QPlainTextEdit(self)
        self.wins_edit.setPlaceholderText("Wins, insights, or notes…")
        self.tags_edit = QtWidgets.QLineEdit(self)
        self.tags_edit.setMaxLength(MAX_TAGS * (MAX_TAG_LEN + 2))
        self.tags_edit.setPlaceholderText("e.g., python, data, leetcode")
        self.tags_edit.setToolTip("Comma-separated tags (up to 10)")

        self.save_btn = QtWidgets.QPushButton("Save Entry", self)
        self.save_btn.clicked.connect(self.save_entry)
        self.save_btn.setProperty("accent", True)

        layout.addRow("Date", self.date_edit)
        layout.addRow("Topic", self.topic_edit)
        layout.addRow("Minutes", self.minutes_spin)
        layout.addRow("Confidence (1-5)", self.conf_slider)
        layout.addRow("What you practiced", self.practiced_edit)
        layout.addRow("Challenges", self.challenges_edit)
        layout.addRow("Wins", self.wins_edit)
        layout.addRow("Tags (comma-separated)", self.tags_edit)
        layout.addRow(self.save_btn)
        outer.addWidget(card)

    def save_entry(self):
        date_q = self.date_edit.date()
        date_py = dt.date(date_q.year(), date_q.month(), date_q.day())
        topic = self.topic_edit.text()
        minutes = self.minutes_spin.value()
        confidence = self.conf_slider.value()
        practiced = self.practiced_edit.toPlainText()
        challenges = self.challenges_edit.toPlainText()
        wins = self.wins_edit.toPlainText()
        tags = self.tags_edit.text()

        sanitized, messages = validate_entry_fields(
            topic=topic,
            minutes=minutes,
            confidence=confidence,
            practiced=practiced,
            challenges=challenges,
            wins=wins,
            tags=tags,
        )
        errors = [m for m in messages if "required" in m or "must be" in m]
        warnings = [m for m in messages if m not in errors]
        if errors:
            QtWidgets.QMessageBox.critical(self, "Validation Error", "\n".join(errors))
            return
        if warnings:
            QtWidgets.QMessageBox.information(self, "Note", "\n".join(warnings))

        upsert_entry(
            date=date_py,
            topic=sanitized["topic"],
            minutes=sanitized["minutes"],
            practiced=sanitized["practiced"],
            challenges=sanitized["challenges"],
            wins=sanitized["wins"],
            confidence=sanitized["confidence"],
            tags=sanitized["tags"],
        )
        QtWidgets.QMessageBox.information(self, "Saved", "Entry saved.")

    def new_entry(self):
        self.date_edit.setDate(QtCore.QDate.currentDate())
        self.topic_edit.clear()
        self.minutes_spin.setValue(0)
        self.conf_slider.setValue(3)
        self.practiced_edit.clear()
        self.challenges_edit.clear()
        self.wins_edit.clear()
        self.tags_edit.clear()


class EntryCalendarWidget(QtWidgets.QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: dict[dt.date, dict] = {}
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)

    def set_entries(self, entries: dict[dt.date, dict]):
        self._entries = entries or {}
        # QCalendarWidget does not expose viewport(); request a repaint of cells
        try:
            self.updateCells()
        except Exception:
            self.update()

    def paintCell(self, painter: QtGui.QPainter, rect: QtCore.QRect, date: QtCore.QDate):
        super().paintCell(painter, rect, date)
        d = dt.date(date.year(), date.month(), date.day())
        if d in self._entries:
            # Draw a rounded badge and topic snippet
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            bg = QtGui.QColor(47, 111, 235, 34)
            rounded = rect.adjusted(3, 20, -3, -3)
            path = QtGui.QPainterPath()
            path.addRoundedRect(rounded, 8, 8)
            painter.fillPath(path, bg)
            painter.setPen(QtGui.QPen(QtGui.QColor(47, 111, 235)))
            topic = str(self._entries[d].get("topic", "")).strip()
            snippet = topic[:22] + ("…" if len(topic) > 22 else "")
            painter.drawText(rounded.adjusted(6, 4, -6, -4), Qt.TextWordWrap, snippet)
            # Confidence dot
            try:
                conf = int(self._entries[d].get("confidence", 0))
            except Exception:
                conf = 0
            if conf:
                colors = {1: QtGui.QColor(220, 76, 70), 2: QtGui.QColor(244, 154, 52), 3: QtGui.QColor(255, 204, 0), 4: QtGui.QColor(76, 175, 80), 5: QtGui.QColor(67, 160, 71)}
                dot = QtCore.QRect(rounded.right()-12, rounded.top()-12, 10, 10)
                painter.setBrush(colors.get(conf, QtGui.QColor(47,111,235)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(dot)
            painter.restore()


class HistoryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        heading = QtWidgets.QLabel("History", self); heading.setProperty("heading", True)
        root.addWidget(heading)

        # Controls
        ctrl = QtWidgets.QHBoxLayout()
        ctrl.setSpacing(8)
        self.sort_combo = QtWidgets.QComboBox(self)
        self.sort_combo.addItems(["Date", "Minutes (desc)", "Confidence (desc)", "Progress (desc)"])
        self.sort_combo.currentIndexChanged.connect(self._rebuild_sorted)
        ctrl.addWidget(QtWidgets.QLabel("Sort"))
        ctrl.addWidget(self.sort_combo)
        ctrl.addStretch(1)
        root.addLayout(ctrl)

        # Split calendar and side panel
        split = QtWidgets.QSplitter(self)
        # Calendar card
        cal_card = QtWidgets.QFrame(self); cal_card.setObjectName("Card")
        cal_v = QtWidgets.QVBoxLayout(cal_card); cal_v.setContentsMargins(8,8,8,8)
        self.calendar = EntryCalendarWidget(cal_card)
        self.calendar.selectionChanged.connect(self._on_day_selected)
        cal_v.addWidget(self.calendar)
        split.addWidget(cal_card)

        right = QtWidgets.QFrame(self); right.setObjectName("Card")
        rlayout = QtWidgets.QVBoxLayout(right); rlayout.setSpacing(8); rlayout.setContentsMargins(12,12,12,12)
        self.details_btn = QtWidgets.QPushButton("View Details", right)
        self.edit_btn = QtWidgets.QPushButton("Edit", right)
        self.delete_btn = QtWidgets.QPushButton("Delete", right)
        self.details_btn.clicked.connect(self.open_details)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.delete_btn.clicked.connect(self.delete_selected)
        btnrow = QtWidgets.QHBoxLayout(); btnrow.addWidget(self.details_btn); btnrow.addWidget(self.edit_btn); btnrow.addWidget(self.delete_btn)
        rlayout.addLayout(btnrow)
        rlayout.addWidget(QtWidgets.QLabel("Sorted Dates", right))
        self.sorted_list = QtWidgets.QListWidget(right)
        self.sorted_list.itemClicked.connect(self._on_sorted_item)
        rlayout.addWidget(self.sorted_list, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

    def refresh(self):
        df = get_all_entries_df()
        self._hist_df = pd.DataFrame(columns=["date","topic","minutes","confidence","progress","tags","practiced","challenges","wins"]) if df.empty else df.copy()
        if not self._hist_df.empty:
            self._hist_df["date"] = pd.to_datetime(self._hist_df["date"]).dt.date
            for c in ["practiced","challenges","wins","tags","topic"]:
                if c not in self._hist_df.columns:
                    self._hist_df[c] = ""
            self._hist_df["minutes"] = self._hist_df["minutes"].astype(int)
            self._hist_df["confidence"] = self._hist_df["confidence"].astype(int)
            self._hist_df["progress"] = self._hist_df["minutes"].astype(int) * self._hist_df["confidence"].astype(int)

        # Feed calendar entries
        entries = {row["date"]: row for _, row in self._hist_df.iterrows()} if not self._hist_df.empty else {}
        self.calendar.set_entries(entries)
        self._rebuild_sorted()

    def _selected_date(self) -> dt.date | None:
        qd = self.calendar.selectedDate()
        if not qd.isValid():
            return None
        return dt.date(qd.year(), qd.month(), qd.day())

    def _selected_row_dict(self) -> dict | None:
        if self._hist_df is None or self._hist_df.empty:
            return None
        d = self._selected_date()
        if not d:
            return None
        row = self._hist_df[self._hist_df["date"] == d]
        if row.empty:
            return None
        row = row.iloc[0]
        return {k: ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}

    def _on_day_selected(self):
        # No-op for now; selection used by buttons
        pass

    def _rebuild_sorted(self):
        self.sorted_list.clear()
        if self._hist_df is None or self._hist_df.empty:
            return
        mode = self.sort_combo.currentText()
        df = self._hist_df.copy()
        if mode == "Minutes (desc)":
            df = df.sort_values(["minutes","date"], ascending=[False, False])
        elif mode == "Confidence (desc)":
            df = df.sort_values(["confidence","date"], ascending=[False, False])
        elif mode == "Progress (desc)":
            df = df.sort_values(["progress","date"], ascending=[False, False])
        else:
            df = df.sort_values("date", ascending=False)
        for _, r in df.iterrows():
            item = QtWidgets.QListWidgetItem(f"{r['date']} — {str(r.get('topic',''))[:40]}")
            item.setData(Qt.UserRole, r["date"])
            self.sorted_list.addItem(item)

    def _on_sorted_item(self, item: QtWidgets.QListWidgetItem):
        d = item.data(Qt.UserRole)
        if isinstance(d, dt.date):
            self.calendar.setSelectedDate(QtCore.QDate(d.year, d.month, d.day))

    def open_details(self):
        data = self._selected_row_dict()
        if not data:
            return
        dlg = EntryDetailsDialog(data, self)
        dlg.exec()

    def edit_selected(self):
        d = self._selected_date()
        if not d:
            QtWidgets.QMessageBox.information(self, "Edit", "Select a row to edit.")
            return
        row = get_entry_by_date(d)
        if not row:
            QtWidgets.QMessageBox.warning(self, "Edit", "Entry not found.")
            return
        dlg = EditDialog(row)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()

    def delete_selected(self):
        d = self._selected_date()
        if not d:
            QtWidgets.QMessageBox.information(self, "Delete", "Select a row to delete.")
            return
        resp = QtWidgets.QMessageBox.question(self, "Confirm Delete", f"Delete entry for {d}?")
        if resp == QtWidgets.QMessageBox.Yes:
            delete_entry(d)
            self.refresh()


class EditDialog(QtWidgets.QDialog):
    def __init__(self, row):
        super().__init__()
        self.setWindowTitle("Edit Entry")
        self.row = row
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        d = pd.to_datetime(self.row["date"]).date()
        self.date_label = QtWidgets.QLabel(str(d), self)
        self.topic_edit = QtWidgets.QLineEdit(self.row["topic"] or "", self)
        self.topic_edit.setMaxLength(MAX_TOPIC_LEN)
        self.topic_edit.setPlaceholderText("e.g., Algorithms, React hooks, SQL joins")
        self.minutes = QtWidgets.QSpinBox(self); self.minutes.setRange(0,1440); self.minutes.setValue(int(self.row["minutes"]))
        self.conf = QtWidgets.QSlider(QtCore.Qt.Horizontal, self); self.conf.setRange(1,5); self.conf.setValue(int(self.row["confidence"]))
        self.prac = QtWidgets.QPlainTextEdit(self.row["practiced"] or "", self)
        self.chal = QtWidgets.QPlainTextEdit(self.row["challenges"] or "", self)
        self.wins = QtWidgets.QPlainTextEdit(self.row["wins"] or "", self)
        self.tags = QtWidgets.QLineEdit(self.row["tags"] or "", self)
        self.tags.setMaxLength(MAX_TAGS * (MAX_TAG_LEN + 2))
        self.tags.setPlaceholderText("e.g., python, data, leetcode")
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)

        layout.addRow("Date", self.date_label)
        layout.addRow("Topic", self.topic_edit)
        layout.addRow("Minutes", self.minutes)
        layout.addRow("Confidence", self.conf)
        layout.addRow("What you practiced", self.prac)
        layout.addRow("Challenges", self.chal)
        layout.addRow("Wins", self.wins)
        layout.addRow("Tags", self.tags)
        layout.addRow(btns)

    def save(self):
        d = pd.to_datetime(self.row["date"]).date()
        sanitized, messages = validate_entry_fields(
            topic=self.topic_edit.text(),
            minutes=int(self.minutes.value()),
            confidence=int(self.conf.value()),
            practiced=self.prac.toPlainText(),
            challenges=self.chal.toPlainText(),
            wins=self.wins.toPlainText(),
            tags=self.tags.text(),
        )
        errors = [m for m in messages if "required" in m or "must be" in m]
        warnings = [m for m in messages if m not in errors]
        if errors:
            QtWidgets.QMessageBox.critical(self, "Validation Error", "\n".join(errors))
            return
        if warnings:
            QtWidgets.QMessageBox.information(self, "Note", "\n".join(warnings))

        upsert_entry(
            date=d,
            topic=sanitized["topic"],
            minutes=sanitized["minutes"],
            practiced=sanitized["practiced"],
            challenges=sanitized["challenges"],
            wins=sanitized["wins"],
            confidence=sanitized["confidence"],
            tags=sanitized["tags"],
        )
        self.accept()


class EntryDetailsDialog(QtWidgets.QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Entry Details")
        self.setMinimumSize(600, 500)
        self._data = data
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        title = QtWidgets.QLabel(self)
        date = str(self._data.get("date", ""))
        topic = str(self._data.get("topic", "")).strip()
        title.setText(f"<b>{date}</b> — {QtGui.QGuiApplication.translate('EntryDetails', topic or '(No topic)')}")
        layout.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        def add_row(row, label, value):
            lab = QtWidgets.QLabel(f"{label}", self)
            lab.setAlignment(Qt.AlignRight | Qt.AlignTop)
            grid.addWidget(lab, row, 0)
            if isinstance(value, QtWidgets.QWidget):
                grid.addWidget(value, row, 1)
            else:
                val = QtWidgets.QLabel(str(value), self)
                val.setWordWrap(True)
                grid.addWidget(val, row, 1)

        # Key stats
        minutes = self._data.get("minutes", "")
        confidence = self._data.get("confidence", "")
        try:
            progress = int(minutes) * int(confidence)
        except Exception:
            progress = ""
        add_row(0, "Minutes", minutes)
        add_row(1, "Confidence", confidence)
        add_row(2, "Progress", progress)
        add_row(3, "Tags", self._data.get("tags", ""))

        # Long text fields with read-only boxes
        practiced = QtWidgets.QTextEdit(self); practiced.setReadOnly(True); practiced.setPlainText(str(self._data.get("practiced", "") or ""))
        challenges = QtWidgets.QTextEdit(self); challenges.setReadOnly(True); challenges.setPlainText(str(self._data.get("challenges", "") or ""))
        wins = QtWidgets.QTextEdit(self); wins.setReadOnly(True); wins.setPlainText(str(self._data.get("wins", "") or ""))
        practiced.setMinimumHeight(80); challenges.setMinimumHeight(80); wins.setMinimumHeight(80)
        add_row(4, "Practiced", practiced)
        add_row(5, "Challenges", challenges)
        add_row(6, "Wins", wins)

        layout.addLayout(grid)

        # Buttons
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, self)
        copy_btn = QtWidgets.QPushButton("Copy JSON", self)
        btns.addButton(copy_btn, QtWidgets.QDialogButtonBox.ActionRole)
        btns.rejected.connect(self.reject)
        copy_btn.clicked.connect(self.copy_json)
        layout.addWidget(btns)

    def copy_json(self):
        import json
        try:
            text = json.dumps(self._data, ensure_ascii=False, indent=2, default=str)
            QtWidgets.QApplication.clipboard().setText(text)
            QtWidgets.QMessageBox.information(self, "Copied", "Entry copied as JSON to clipboard.")
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "Copy Failed", str(ex))


class DataTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        heading = QtWidgets.QLabel("Data", self); heading.setProperty("heading", True)
        v.addWidget(heading)
        card = QtWidgets.QFrame(self); card.setObjectName("Card")
        card_layout = QtWidgets.QVBoxLayout(card)
        self.table = QtWidgets.QTableView(card)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        card_layout.addWidget(self.table)

        hb = QtWidgets.QHBoxLayout()
        self.export_btn = QtWidgets.QPushButton("Export JSON")
        self.import_btn = QtWidgets.QPushButton("Import JSON")
        hb.addWidget(self.export_btn)
        hb.addWidget(self.import_btn)
        card_layout.addLayout(hb)
        v.addWidget(card)

        self.export_btn.clicked.connect(self.export_csv)
        self.import_btn.clicked.connect(self.import_csv)
        self.import_btn.setProperty("accent", True)

    def refresh(self):
        df = get_all_entries_df()
        if df.empty:
            self.table.setModel(None)
            return
        df = df.sort_values("date", ascending=False).reset_index(drop=True)
        df["progress"] = df["minutes"].astype(int) * df["confidence"].astype(int)
        for c in ["practiced", "challenges", "wins"]:
            if c not in df.columns:
                df[c] = ""
        self._data_df = df[["date", "topic", "minutes", "confidence", "progress", "tags", "practiced", "challenges", "wins"]].copy()
        self.table.setModel(DataFrameModel(self._data_df))

    def export_csv(self):
        try:
            path = export_db_to_json()
            QtWidgets.QMessageBox.information(self, "Export", "JSON exported successfully.")
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(ex))

    def import_csv(self):
        dlg = QtWidgets.QFileDialog(self)
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dlg.setNameFilter("JSON Files (*.json)")
        if dlg.exec():
            path = dlg.selectedFiles()[0]
            # Background validation via dry-run
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("Invalid JSON format: expected a list of entries")
                df = pd.DataFrame(data)
                from services.storage import import_dataframe
                ins, upd, msgs = import_dataframe(df, dry_run=True)
                fatals = [m for m in msgs if ("required" in m.lower() or "must be" in m.lower() or "missing date" in m.lower())]
                if fatals:
                    QtWidgets.QMessageBox.critical(self, "Import Failed", "\n".join(fatals[:20]))
                    return
                # Commit
                import_json_to_db(path)
                self.refresh()
                QtWidgets.QMessageBox.information(self, "Import", "Import completed.")
            except Exception as ex:
                QtWidgets.QMessageBox.critical(self, "Import Failed", str(ex))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Learning Progress Tracker")
        # Sidebar navigation + stacked pages
        self.nav = QtWidgets.QListWidget(self)
        self.nav.setObjectName("Sidebar")
        self.nav.setIconSize(QtCore.QSize(20, 20))
        self.nav.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.nav.setUniformItemSizes(True)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setFrameShape(QtWidgets.QFrame.NoFrame)
        names = ["Log Entry", "History", "Insights", "Data", "Settings"]
        icons = [
            self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon),
            self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView),
            self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon),
            self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon),
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogYesButton),
        ]
        for name, icon in zip(names, icons):
            item = QtWidgets.QListWidgetItem(icon, name)
            self.nav.addItem(item)
        self.pages = QtWidgets.QStackedWidget(self)
        self.log_tab = LogEntryTab(); self.pages.addWidget(self.log_tab)
        self.hist_tab = HistoryTab(); self.pages.addWidget(self.hist_tab)
        self.insights_tab = InsightsTab(); self.pages.addWidget(self.insights_tab)
        self.data_tab = DataTab(); self.pages.addWidget(self.data_tab)
        self.settings_tab = SettingsTab(self); self.pages.addWidget(self.settings_tab)
        self.nav.currentRowChanged.connect(self._navigate_to)
        self.nav.setCurrentRow(0)
        splitter = QtWidgets.QSplitter(self)
        splitter.addWidget(self.nav)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 1200])
        self.setCentralWidget(splitter)
        # Keyboard shortcuts (no visible toolbar)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._focus_new_entry)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.data_tab.export_csv)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.data_tab.import_csv)
        QShortcut(QKeySequence("F5"), self, activated=self._refresh_current)
        # Load and apply compact sidebar preference
        try:
            s = QtCore.QSettings("LPT", "LearningProgressTracker")
            compact_pref = bool(int(s.value("ui/compactSidebar", "0")))
        except Exception:
            compact_pref = False
        self._toggle_sidebar_compact(compact_pref)
        # Status bar
        self.status = self.statusBar()
        self.status.showMessage("Ready")
        # Mark window state not yet loaded; main() decides default size vs saved
        self._state_loaded = False

    def _focus_new_entry(self):
        self.nav.setCurrentRow(0)
        try:
            # Clear form for a fresh entry, then focus
            if hasattr(self, "log_tab") and hasattr(self.log_tab, "new_entry"):
                self.log_tab.new_entry()
            self.log_tab.topic_edit.setFocus(Qt.OtherFocusReason)
        except Exception:
            pass

    def _refresh_current(self):
        idx = self.pages.currentIndex()
        try:
            if idx == 1:
                self.hist_tab.refresh()
            elif idx == 2:
                self.insights_tab.refresh()
            elif idx == 3:
                self.data_tab.refresh()
        except Exception:
            pass

    def _navigate_to(self, idx: int):
        # Animate fade-in transition on page change
        try:
            widget = self.pages.widget(idx)
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            self.pages.setCurrentIndex(idx)
            anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        except Exception:
            self.pages.setCurrentIndex(idx)

    def _toggle_sidebar_compact(self, compact: bool):
        try:
            if not hasattr(self, "_nav_names"):
                self._nav_names = [self.nav.item(i).text() for i in range(self.nav.count())]
            if compact:
                for i in range(self.nav.count()):
                    it = self.nav.item(i)
                    it.setToolTip(self._nav_names[i])
                    it.setText("")
                self.nav.setFixedWidth(64)
                self.nav.setProperty("compact", True)
            else:
                for i in range(self.nav.count()):
                    self.nav.item(i).setText(self._nav_names[i])
                    self.nav.item(i).setToolTip("")
                self.nav.setFixedWidth(240)
                self.nav.setProperty("compact", False)
            # Save preference
            try:
                s = QtCore.QSettings("LPT", "LearningProgressTracker")
                s.setValue("ui/compactSidebar", "1" if compact else "0")
            except Exception:
                pass
            # Refresh style for property-based selector
            self.nav.style().unpolish(self.nav)
            self.nav.style().polish(self.nav)
            self.nav.update()
        except Exception:
            pass

    def _load_window_state(self) -> bool:
        try:
            s = QtCore.QSettings("LPT", "LearningProgressTracker")
            geo = s.value("win/geometry")
            if geo:
                self.restoreGeometry(geo)
            state = s.value("win/state")
            if state:
                self.restoreState(state)
            self._state_loaded = bool(geo or state)
            return self._state_loaded
        except Exception:
            return False

    def closeEvent(self, event):
        try:
            s = QtCore.QSettings("LPT", "LearningProgressTracker")
            s.setValue("win/geometry", self.saveGeometry())
            s.setValue("win/state", self.saveState())
        except Exception:
            pass
        super().closeEvent(event)


class InsightsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        # Metrics row
        self.metrics_label = QtWidgets.QLabel("", self)
        v.addWidget(self.metrics_label)
        # Three figures stacked
        self.fig1 = Figure(figsize=(6, 3), tight_layout=True)
        self.canvas1 = FigureCanvas(self.fig1)
        self.fig2 = Figure(figsize=(6, 3), tight_layout=True)
        self.canvas2 = FigureCanvas(self.fig2)
        self.fig3 = Figure(figsize=(6, 3), tight_layout=True)
        self.canvas3 = FigureCanvas(self.fig3)
        v.addWidget(QtWidgets.QLabel("Minutes per Day"))
        v.addWidget(self.canvas1)
        v.addWidget(QtWidgets.QLabel("Confidence Over Time"))
        v.addWidget(self.canvas2)
        v.addWidget(QtWidgets.QLabel("Progress Score Over Time"))
        v.addWidget(self.canvas3)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        v.addWidget(refresh_btn)

    def refresh(self):
        df = get_all_entries_df()
        self.fig1.clear(); self.fig2.clear(); self.fig3.clear()
        if df.empty:
            # Metrics (no data)
            goal_str = get_setting("weekly_goal_minutes", None) or "0"
            try:
                goal = int(goal_str)
            except Exception:
                goal = 0
            self.metrics_label.setText(f"This week: 0/{goal} min · Current streak: 0 · Longest streak: 0")
            for fig in (self.fig1, self.fig2, self.fig3):
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, "No data yet", ha='center', va='center')
                ax.axis('off')
            self.canvas1.draw(); self.canvas2.draw(); self.canvas3.draw()
            return
        # Prep
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.sort_values("date")
        # Metrics
        goal_str = get_setting("weekly_goal_minutes", None) or "0"
        try:
            goal = int(goal_str)
        except Exception:
            goal = 0
        this_week = weekly_minutes(df)
        dates = df["date"].tolist()
        cur_streak, longest = compute_streaks(dates)
        self.metrics_label.setText(f"This week: {this_week}/{goal} min · Current streak: {cur_streak} · Longest streak: {longest}")
        # Minutes per day (bar)
        ax1 = self.fig1.add_subplot(111)
        ax1.bar(df["date"].astype(str), df["minutes"].astype(int), color="#4C78A8")
        ax1.set_xticks(ax1.get_xticks()[::max(1, int(len(df)/10))])
        ax1.set_ylabel("Minutes")
        ax1.tick_params(axis='x', rotation=45)
        # Confidence over time (line)
        ax2 = self.fig2.add_subplot(111)
        ax2.plot(df["date"].astype(str), df["confidence"].astype(int), marker='o', color="#F58518")
        ax2.set_ylim(1, 5)
        ax2.set_ylabel("Confidence")
        ax2.tick_params(axis='x', rotation=45)
        # Progress score (line)
        if "progress_score" not in df.columns:
            df["progress_score"] = df["minutes"].astype(int) * df["confidence"].astype(int)
        ax3 = self.fig3.add_subplot(111)
        ax3.plot(df["date"].astype(str), df["progress_score"].astype(int), marker='o', color="#54A24B")
        ax3.set_ylabel("Progress")
        ax3.tick_params(axis='x', rotation=45)
        # Draw
        self.canvas1.draw(); self.canvas2.draw(); self.canvas3.draw()

    # Helper to allow MainWindow to call refresh
    def do_refresh(self):
        self.refresh()


class SettingsTab(QtWidgets.QWidget):
    def __init__(self, main_window: QtWidgets.QMainWindow):
        super().__init__()
        self._main = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        heading = QtWidgets.QLabel("Settings", self); heading.setProperty("heading", True)
        layout.addRow(heading)
        self.goal_spin = QtWidgets.QSpinBox(self)
        self.goal_spin.setRange(0, 10000)
        self.goal_spin.setSingleStep(10)
        # Load existing value
        try:
            val = int(get_setting("weekly_goal_minutes", "0") or 0)
        except Exception:
            val = 0
        self.goal_spin.setValue(val)
        # Compact sidebar toggle
        self.compact_chk = QtWidgets.QCheckBox("Compact sidebar", self)
        try:
            s = QtCore.QSettings("LPT", "LearningProgressTracker")
            compact_pref = bool(int(s.value("ui/compactSidebar", "0")))
        except Exception:
            compact_pref = False
        self.compact_chk.setChecked(compact_pref)
        self.compact_chk.toggled.connect(self._main._toggle_sidebar_compact)
        # Theme selection
        self.theme_combo = QtWidgets.QComboBox(self)
        self.theme_combo.addItems(["Dark", "Light"])
        try:
            current = (get_setting("theme", "dark") or "dark").lower()
            self.theme_combo.setCurrentIndex(1 if current == "light" else 0)
        except Exception:
            pass
        save_btn = QtWidgets.QPushButton("Save", self)
        save_btn.clicked.connect(self.save)
        layout.addRow("Weekly goal (minutes)", self.goal_spin)
        layout.addRow(self.compact_chk)
        layout.addRow("Theme", self.theme_combo)
        layout.addRow(save_btn)

    def save(self):
        set_setting("weekly_goal_minutes", str(int(self.goal_spin.value())))
        # Save theme and apply immediately
        theme = "light" if self.theme_combo.currentIndex() == 1 else "dark"
        set_setting("theme", theme)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            apply_theme(app)
        QtWidgets.QMessageBox.information(self, "Settings", "Saved weekly goal.")


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df.reset_index(drop=True)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._df.iat[index.row(), index.column()]
            return "" if pd.isna(val) else str(val)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section]).title()
        return str(section + 1)

    def sort(self, column, order):
        col = self._df.columns[column]
        try:
            self.layoutAboutToBeChanged.emit()
            self._df = self._df.sort_values(col, ascending=(order == Qt.AscendingOrder)).reset_index(drop=True)
            self.layoutChanged.emit()
        except Exception:
            pass


def apply_theme(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    # Determine theme from settings
    theme = "dark"
    try:
        theme = (get_setting("theme", "dark") or "dark").lower()
        if theme not in ("dark", "light"):
            theme = "dark"
    except Exception:
        theme = "dark"
    pal = QtGui.QPalette()
    if theme == "light":
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor(250, 250, 250))
        pal.setColor(QtGui.QPalette.WindowText, QtCore.Qt.black)
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(255, 255, 255))
        pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(243, 243, 243))
        pal.setColor(QtGui.QPalette.Text, QtCore.Qt.black)
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(245, 245, 247))
        pal.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.black)
        pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(47, 111, 235))
        pal.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
    else:
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 18, 18))
        pal.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(20, 20, 20))
        pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(24, 24, 24))
        pal.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(32, 32, 32))
        pal.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
        pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(47, 111, 235))
        pal.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
    app.setPalette(pal)
    # Font and stylesheet for a modern rounded look
    app.setFont(QtGui.QFont("Segoe UI", 10))
    app.setStyleSheet(_build_stylesheet(theme, "#2F6FEB"))


def setup_highdpi():
    # Must be called before creating QApplication
    try:
        if hasattr(QtWidgets.QApplication, "setHighDpiScaleFactorRoundingPolicy"):
            QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
                QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
    except Exception:
        pass
    # Avoid deprecated AA_UseHighDpiPixmaps attribute to prevent warnings


def main():
    init_db()
    create_or_sync_on_launch()
    register_atexit_export()
    setup_highdpi()
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    win = MainWindow()
    # Ensure windowed (not maximized/fullscreen), then size
    win.setWindowState(Qt.WindowNoState)
    loaded = win._load_window_state()  # Load saved size if any
    if not loaded:
        win.resize(1920, 1080)
    win.showNormal()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    
