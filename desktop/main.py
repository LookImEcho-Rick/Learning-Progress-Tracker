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


def _build_stylesheet(accent: str = "#2F6FEB") -> str:
    return f"""
    * {{ font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial; font-size: 10pt; }}
    QWidget {{ background-color: #121212; color: #EDEDED; }}
    QGroupBox {{ border: 1px solid #2A2A2A; border-radius: 10px; margin-top: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
        background-color: #1E1E1E; border: 1px solid #2A2A2A; border-radius: 8px; padding: 6px 8px;
        selection-background-color: {accent}; selection-color: #FFFFFF;
    }}
    QPlainTextEdit, QTextEdit {{ padding: 8px; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
        border: 1px solid {accent};
    }}
    QPushButton {{ background-color: #2B2B2B; border: 1px solid #2F2F2F; border-radius: 10px; padding: 8px 14px; }}
    QPushButton:hover {{ background-color: #343434; border-color: #3A3A3A; }}
    QPushButton:pressed {{ background-color: #0E63A6; border-color: #0E63A6; color: #FFFFFF; }}
    QPushButton[accent="true"] {{ background-color: {accent}; border: 1px solid {accent}; color: #FFFFFF; }}
    QTabWidget::pane {{ border: 1px solid #2A2A2A; border-radius: 12px; padding: 6px; }}
    QTabBar::tab {{ background: #1B1B1B; border: 1px solid #2A2A2A; padding: 8px 16px; border-top-left-radius: 12px; border-top-right-radius: 12px; margin-right: 4px; }}
    QTabBar::tab:selected {{ background: #2B2B2B; color: #FFFFFF; }}
    QHeaderView::section {{ background-color: #1B1B1B; color: #E0E0E0; padding: 8px; border: none; border-bottom: 1px solid #2A2A2A; }}
    QTableView {{ background-color: #141414; alternate-background-color: #181818; gridline-color: #2A2A2A; selection-background-color: {accent}; selection-color: #FFFFFF; }}
    QListWidget#Sidebar {{ background: #141414; border: none; padding: 8px; outline: 0; }}
    QListWidget#Sidebar::item {{ color: #D0D0D0; padding: 10px 12px; margin: 4px 6px; border-radius: 10px; }}
    QListWidget#Sidebar::item:hover {{ background: #1F1F1F; }}
    QListWidget#Sidebar::item:selected {{ background: {accent}; color: #FFFFFF; font-weight: 600; }}
    QListWidget#Sidebar[compact=\"true\"] {{ padding: 6px; }}
    QListWidget#Sidebar[compact=\"true\"]::item {{ padding: 8px; margin: 2px 4px; }}
    QSplitter::handle {{ background: #1A1A1A; width: 2px; }}
    QScrollBar:vertical {{ background: #141414; width: 10px; margin: 6px; border-radius: 5px; }}
    QScrollBar::handle:vertical {{ background: {accent}; min-height: 30px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: #141414; height: 10px; margin: 6px; border-radius: 5px; }}
    QScrollBar::handle:horizontal {{ background: {accent}; min-width: 30px; border-radius: 5px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSlider::groove:horizontal {{ height: 6px; background: #2A2A2A; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {accent}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}
    QToolTip {{ background-color: #2B2B2B; color: #FFFFFF; border: 1px solid #3A3A3A; padding: 6px; border-radius: 6px; }}
    QMessageBox {{ background-color: #1E1E1E; }}
    """


class LogEntryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
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


class HistoryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)
        filters = QtWidgets.QHBoxLayout()
        filters.setSpacing(8)

        self.start_date = QtWidgets.QDateEdit(self)
        self.start_date.setCalendarPopup(True)
        self.end_date = QtWidgets.QDateEdit(self)
        self.end_date.setCalendarPopup(True)
        self.tag_filter = QtWidgets.QLineEdit(self)
        self.tag_filter.setPlaceholderText("tags: comma-separated")

        self.apply_btn = QtWidgets.QPushButton("Apply Filters", self)
        self.apply_btn.clicked.connect(self.refresh)

        filters.addWidget(QtWidgets.QLabel("Start"))
        filters.addWidget(self.start_date)
        filters.addWidget(QtWidgets.QLabel("End"))
        filters.addWidget(self.end_date)
        filters.addWidget(QtWidgets.QLabel("Tags"))
        filters.addWidget(self.tag_filter)
        filters.addWidget(self.apply_btn)

        self.table = QtWidgets.QTableView(self)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        self.edit_btn = QtWidgets.QPushButton("Edit Selected", self)
        self.delete_btn = QtWidgets.QPushButton("Delete Selected", self)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.delete_btn.clicked.connect(self.delete_selected)

        vbox.addLayout(filters)
        vbox.addWidget(self.table)
        hb = QtWidgets.QHBoxLayout()
        hb.addWidget(self.edit_btn)
        hb.addWidget(self.delete_btn)
        vbox.addLayout(hb)

    def refresh(self):
        df = get_all_entries_df()
        if df.empty:
            today = QtCore.QDate.currentDate()
            self.start_date.setDate(today)
            self.end_date.setDate(today)
            self.table.setModel(None)
            return
        # Setup date filters
        dates = pd.to_datetime(df["date"]).dt.date
        min_d = QtCore.QDate(dates.min().year, dates.min().month, dates.min().day)
        max_d = QtCore.QDate(dates.max().year, dates.max().month, dates.max().day)
        self.start_date.setDate(min_d)
        self.end_date.setDate(max_d)

        start = dt.date(self.start_date.date().year(), self.start_date.date().month(), self.start_date.date().day())
        end = dt.date(self.end_date.date().year(), self.end_date.date().month(), self.end_date.date().day())
        mask = (pd.to_datetime(df["date"]).dt.date >= start) & (pd.to_datetime(df["date"]).dt.date <= end)
        fdf = df.loc[mask].copy()

        # Tag filter
        tags = [t.strip().lower() for t in self.tag_filter.text().split(",") if t.strip()]
        if tags:
            def has_tag(ts: str) -> bool:
                items = {t.strip().lower() for t in str(ts).split(",") if t.strip()}
                return any(t in items for t in tags)
            fdf = fdf[fdf["tags"].apply(has_tag)]

        # Derived
        fdf["progress"] = fdf["minutes"].astype(int) * fdf["confidence"].astype(int)

        rows = fdf.sort_values("date", ascending=False).reset_index(drop=True)
        # Include all entry fields in history view
        cols = ["date", "topic", "minutes", "confidence", "progress", "tags", "practiced", "challenges", "wins"]
        for c in ["practiced", "challenges", "wins"]:
            if c not in rows.columns:
                rows[c] = ""
        self._hist_df = rows[cols].copy()
        self.table.setModel(DataFrameModel(self._hist_df))

    def _selected_date(self) -> dt.date | None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        r = sel[0].row()
        idx = self.table.model().index(r, 0)
        date_str = self.table.model().data(idx, Qt.DisplayRole)
        try:
            return pd.to_datetime(date_str).date()
        except Exception:
            return None

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


class DataTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        self.table = QtWidgets.QTableView(self)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table)

        hb = QtWidgets.QHBoxLayout()
        self.export_btn = QtWidgets.QPushButton("Export JSON")
        self.import_btn = QtWidgets.QPushButton("Import JSON")
        hb.addWidget(self.export_btn)
        hb.addWidget(self.import_btn)
        v.addLayout(hb)

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
        save_btn = QtWidgets.QPushButton("Save", self)
        save_btn.clicked.connect(self.save)
        layout.addRow("Weekly goal (minutes)", self.goal_spin)
        layout.addRow(self.compact_chk)
        layout.addRow(save_btn)

    def save(self):
        set_setting("weekly_goal_minutes", str(int(self.goal_spin.value())))
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
    dark = QtGui.QPalette()
    dark.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 18, 18))
    dark.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Base, QtGui.QColor(20, 20, 20))
    dark.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(24, 24, 24))
    dark.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Button, QtGui.QColor(32, 32, 32))
    dark.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark.setColor(QtGui.QPalette.Link, QtGui.QColor(47, 111, 235))
    dark.setColor(QtGui.QPalette.Highlight, QtGui.QColor(47, 111, 235))
    dark.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
    app.setPalette(dark)
    # Font and stylesheet for a modern rounded look
    app.setFont(QtGui.QFont("Segoe UI", 10))
    app.setStyleSheet(_build_stylesheet("#2F6FEB"))


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
    
