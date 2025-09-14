import sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import datetime as dt

from PySide6 import QtWidgets, QtCore, QtGui

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
from services.filesync import create_or_sync_on_launch, register_atexit_export, export_db_to_csv, import_csv_to_db
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class LogEntryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)

        self.date_edit = QtWidgets.QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QtCore.QDate.currentDate())

        self.topic_edit = QtWidgets.QLineEdit(self)
        self.topic_edit.setMaxLength(MAX_TOPIC_LEN)

        self.minutes_spin = QtWidgets.QSpinBox(self)
        self.minutes_spin.setRange(0, 1440)
        self.minutes_spin.setSingleStep(5)

        self.conf_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.conf_slider.setRange(1, 5)
        self.conf_slider.setValue(3)

        self.practiced_edit = QtWidgets.QPlainTextEdit(self)
        self.challenges_edit = QtWidgets.QPlainTextEdit(self)
        self.wins_edit = QtWidgets.QPlainTextEdit(self)
        self.tags_edit = QtWidgets.QLineEdit(self)
        self.tags_edit.setMaxLength(MAX_TAGS * (MAX_TAG_LEN + 2))

        self.save_btn = QtWidgets.QPushButton("Save Entry", self)
        self.save_btn.clicked.connect(self.save_entry)

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


class HistoryTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        vbox = QtWidgets.QVBoxLayout(self)
        filters = QtWidgets.QHBoxLayout()

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

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Topic", "Minutes", "Confidence", "Progress", "Tags"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)

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
            self.table.setRowCount(0)
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
        self.table.setRowCount(len(rows))
        for i, row in rows.iterrows():
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(row["date"])) )
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(row["topic"])) )
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(int(row["minutes"])) ))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(int(row["confidence"])) ))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(int(row["progress"])) ))
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.get("tags", ""))) )

    def _selected_date(self) -> dt.date | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        date_str = self.table.item(r, 0).text()
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
        self.minutes = QtWidgets.QSpinBox(self); self.minutes.setRange(0,1440); self.minutes.setValue(int(self.row["minutes"]))
        self.conf = QtWidgets.QSlider(QtCore.Qt.Horizontal, self); self.conf.setRange(1,5); self.conf.setValue(int(self.row["confidence"]))
        self.prac = QtWidgets.QPlainTextEdit(self.row["practiced"] or "", self)
        self.chal = QtWidgets.QPlainTextEdit(self.row["challenges"] or "", self)
        self.wins = QtWidgets.QPlainTextEdit(self.row["wins"] or "", self)
        self.tags = QtWidgets.QLineEdit(self.row["tags"] or "", self)
        self.tags.setMaxLength(MAX_TAGS * (MAX_TAG_LEN + 2))
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
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Topic", "Minutes", "Confidence", "Progress", "Tags"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSortingEnabled(True)
        v.addWidget(self.table)

        hb = QtWidgets.QHBoxLayout()
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.import_btn = QtWidgets.QPushButton("Import CSV")
        hb.addWidget(self.export_btn)
        hb.addWidget(self.import_btn)
        v.addLayout(hb)

        self.export_btn.clicked.connect(self.export_csv)
        self.import_btn.clicked.connect(self.import_csv)

    def refresh(self):
        df = get_all_entries_df()
        if df.empty:
            self.table.setRowCount(0)
            return
        df["progress"] = df["minutes"].astype(int) * df["confidence"].astype(int)
        self.table.setRowCount(len(df))
        for i, row in df.sort_values("date", ascending=False).iterrows():
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(row["date"])) )
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(row["topic"])) )
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(int(row["minutes"])) ))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(int(row["confidence"])) ))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(int(row["progress"])) ))
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(row.get("tags", ""))) )

    def export_csv(self):
        try:
            path = export_db_to_csv()
            QtWidgets.QMessageBox.information(self, "Export", "CSV exported successfully.")
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(ex))

    def import_csv(self):
        dlg = QtWidgets.QFileDialog(self)
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dlg.setNameFilter("CSV Files (*.csv)")
        if dlg.exec():
            path = dlg.selectedFiles()[0]
            # Background validation via dry-run
            try:
                df = pd.read_csv(path)
                from services.storage import import_dataframe
                ins, upd, msgs = import_dataframe(df, dry_run=True)
                fatals = [m for m in msgs if ("required" in m.lower() or "must be" in m.lower() or "missing date" in m.lower())]
                if fatals:
                    QtWidgets.QMessageBox.critical(self, "Import Failed", "\n".join(fatals[:20]))
                    return
                # Commit
                import_dataframe(df, dry_run=False)
                self.refresh()
                QtWidgets.QMessageBox.information(self, "Import", "Import completed.")
            except Exception as ex:
                QtWidgets.QMessageBox.critical(self, "Import Failed", str(ex))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Learning Progress Tracker")
        tabs = QtWidgets.QTabWidget(self)
        self.setCentralWidget(tabs)
        self.log_tab = LogEntryTab()
        self.hist_tab = HistoryTab()
        self.data_tab = DataTab()
        self.insights_tab = InsightsTab()
        self.settings_tab = SettingsTab()
        tabs.addTab(self.log_tab, "Log Entry")
        tabs.addTab(self.hist_tab, "History")
        tabs.addTab(self.insights_tab, "Insights")
        tabs.addTab(self.data_tab, "Data")
        tabs.addTab(self.settings_tab, "Settings")


class InsightsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
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


class SettingsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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
        save_btn = QtWidgets.QPushButton("Save", self)
        save_btn.clicked.connect(self.save)
        layout.addRow("Weekly goal (minutes)", self.goal_spin)
        layout.addRow(save_btn)

    def save(self):
        set_setting("weekly_goal_minutes", str(int(self.goal_spin.value())))
        QtWidgets.QMessageBox.information(self, "Settings", "Saved weekly goal.")


def apply_theme(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    dark = QtGui.QPalette()
    dark.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    dark.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
    dark.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    dark.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    dark.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(dark)


def setup_highdpi():
    # Must be called before creating QApplication
    try:
        if hasattr(QtWidgets.QApplication, "setHighDpiScaleFactorRoundingPolicy"):
            QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
                QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
    except Exception:
        pass
    try:
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
    except Exception:
        pass


def main():
    init_db()
    create_or_sync_on_launch()
    register_atexit_export()
    setup_highdpi()
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    win = MainWindow()
    win.resize(1000, 700)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
