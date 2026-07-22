from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QProgressDialog, QFrame, QHeaderView, QSizePolicy,
    QGraphicsDropShadowEffect, QAbstractItemView
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QIcon
import sys
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from src.f1_data import (
    get_race_weekends_by_year, get_race_weekends_by_place,
    get_all_unique_race_names
)
from src.gui.settings_dialog import SettingsDialog
from src.lib.season import get_season


# ── Premium dark theme ────────────────────────────────────────────────────

RACE_SELECTION_THEME = """
QMainWindow {
    background: #0d1117;
}
QWidget {
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Combo Boxes ──────────────────────────────────────────────────── */
QComboBox {
    background: rgba(255, 255, 255, 0.05);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: rgba(225, 6, 0, 0.45);
    background: rgba(255, 255, 255, 0.07);
}
QComboBox:focus {
    border-color: #e10600;
}
QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
}
QComboBox QAbstractItemView {
    background: #161b22;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    selection-background-color: rgba(225, 6, 0, 0.2);
    selection-color: white;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background: rgba(255, 255, 255, 0.06);
}

/* ── Labels ───────────────────────────────────────────────────────── */
QLabel {
    color: #e6edf3;
}

/* ── Tree Widget (Schedule) ──────────────────────────────────────── */
QTreeWidget {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 4px;
    font-size: 13px;
    alternate-background-color: rgba(255, 255, 255, 0.015);
    outline: none;
}
QTreeWidget::item {
    padding: 8px 6px;
    border-radius: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
QTreeWidget::item:hover {
    background: rgba(225, 6, 0, 0.08);
}
QTreeWidget::item:selected {
    background: rgba(225, 6, 0, 0.18);
    color: white;
}
QHeaderView::section {
    background: rgba(255, 255, 255, 0.04);
    color: rgba(255, 255, 255, 0.55);
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
QPushButton {
    background: rgba(255, 255, 255, 0.05);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background: rgba(225, 6, 0, 0.12);
    border-color: rgba(225, 6, 0, 0.45);
    color: white;
}
QPushButton:pressed {
    background: rgba(225, 6, 0, 0.22);
}

/* ── Scroll Bars ──────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: rgba(255,255,255,0.02);
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.2);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ── Progress Dialog ──────────────────────────────────────────────── */
QProgressDialog {
    background: #161b22;
    color: #e6edf3;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
}
QProgressBar {
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 4px;
    height: 6px;
}
QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #e10600, stop:1 #ff4444
    );
    border-radius: 4px;
}
"""


# ── Session button styling ────────────────────────────────────────────────

SESSION_ICONS = {
    "Race": "🏁",
    "Qualifying": "⏱️",
    "Sprint": "🏎️",
    "Sprint Qualifying": "⚡",
}

SESSION_ACCENTS = {
    "Race": "#e10600",
    "Qualifying": "#42a5f5",
    "Sprint": "#00e676",
    "Sprint Qualifying": "#ffa726",
}


class SessionButton(QPushButton):
    """Premium session launch button with icon and accent colour."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        icon = SESSION_ICONS.get(label, "🏁")
        accent = SESSION_ACCENTS.get(label, "#e10600")

        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-left: 3px solid {accent};
                border-radius: 8px;
                padding: 0 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 600;
                color: rgba(255,255,255,0.9);
            }}
            QPushButton:hover {{
                background: {accent}18;
                border-color: {accent}50;
                color: white;
            }}
            QPushButton:pressed {{
                background: {accent}28;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 18))
        icon_label.setFixedWidth(28)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)

        text_label = QLabel(label)
        text_label.setFont(QFont("Inter", 13, QFont.Bold))
        text_label.setStyleSheet("color: rgba(255,255,255,0.9);")
        text_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(text_label, 1)

        arrow = QLabel("›")
        arrow.setFont(QFont("Inter", 18))
        arrow.setStyleSheet(f"color: {accent}60;")
        arrow.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(arrow)


# Worker thread to fetch schedule without blocking UI
class FetchScheduleWorker(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, year, parent=None):
        super().__init__(parent)
        self.year = year

    def run(self): #check
        try:
            # enable cache if available in project
            try:
                from src.f1_data import enable_cache
                enable_cache()
            except Exception:
                pass
            events = get_race_weekends_by_year(self.year)
            self.result.emit(events)
        except Exception as e:
            self.error.emit(str(e))

class RaceSelectionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.loading_session = False
        self.selected_session_title = None
        self.current_year = get_season()
        self.selected_year=self.current_year 

        self.setWindowTitle("F1 Race Replay")
        self.setStyleSheet(RACE_SELECTION_THEME)
        self._setup_ui()
        self.resize(1100, 750)
        self.setMinimumSize(800, 600)
        self.setWindowState(self.windowState())

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background: #0d1117;")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)

        # ── Header banner ─────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.4 #16213e, stop:1 #0f3460
                );
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)

        # Title area
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel("🏎️ F1 Race Replay")
        title_label.setFont(QFont("Inter", 22, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        title_col.addWidget(title_label)
        subtitle_label = QLabel("Select a session to begin replay")
        subtitle_label.setFont(QFont("Inter", 11))
        subtitle_label.setStyleSheet("color: rgba(255,255,255,0.4);")
        title_col.addWidget(subtitle_label)
        h_layout.addLayout(title_col)
        h_layout.addStretch()

        # Settings button
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setFixedHeight(36)
        settings_btn.setFixedWidth(110)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                color: rgba(255,255,255,0.7);
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: white;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)
        h_layout.addWidget(settings_btn)

        main_layout.addWidget(header)

        # ── Filter bar ────────────────────────────────────────────────
        filter_bar = QFrame()
        filter_bar.setFixedHeight(60)
        filter_bar.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.02);
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }
        """)
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(24, 10, 24, 10)
        filter_layout.setSpacing(16)

        # Year selector
        year_label = QLabel("Season")
        year_label.setFont(QFont("Inter", 11, QFont.Bold))
        year_label.setStyleSheet("color: rgba(255,255,255,0.55);")
        filter_layout.addWidget(year_label)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(140)
        self.year_combo.addItem("All Years")
        for year in range(2018, self.current_year + 1):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(self.current_year))
        self.year_combo.currentTextChanged.connect(self.load_by_year)
        filter_layout.addWidget(self.year_combo)

        # Separator
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        sep.setStyleSheet("background: rgba(255,255,255,0.08);")
        filter_layout.addWidget(sep)

        # Race selector
        race_label = QLabel("Circuit")
        race_label.setFont(QFont("Inter", 11, QFont.Bold))
        race_label.setStyleSheet("color: rgba(255,255,255,0.55);")
        filter_layout.addWidget(race_label)

        self.place_combo = QComboBox()
        self.place_combo.setFixedWidth(200)
        self.place_combo.addItem("All Races")
        self.place_combo.addItems(get_all_unique_race_names())
        self.place_combo.currentTextChanged.connect(self.load_by_place)
        filter_layout.addWidget(self.place_combo)

        filter_layout.addStretch()
        main_layout.addWidget(filter_bar)

        # ── Content area ──────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setStyleSheet("background: #0d1117;")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)

        # Schedule tree (left)
        tree_container = QVBoxLayout()
        tree_header = QLabel("Race Calendar")
        tree_header.setFont(QFont("Inter", 13, QFont.Bold))
        tree_header.setStyleSheet("color: rgba(255,255,255,0.7); padding-bottom: 6px;")
        tree_container.addWidget(tree_header)

        self.schedule_tree = QTreeWidget()
        self.schedule_tree.setHeaderLabels(["Round", "Event", "Country", "Start Date"])
        self.schedule_tree.setRootIsDecorated(False)
        self.schedule_tree.setAlternatingRowColors(True)
        self.schedule_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.schedule_tree.header().setStretchLastSection(True)
        self.schedule_tree.setColumnWidth(0, 60)
        self.schedule_tree.setColumnWidth(1, 220)
        self.schedule_tree.setColumnWidth(2, 140)
        tree_container.addWidget(self.schedule_tree)

        content_layout.addLayout(tree_container, 3)

        # Session panel (right)
        self.session_panel = QFrame()
        self.session_panel.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }
        """)
        session_panel_layout = QVBoxLayout(self.session_panel)
        session_panel_layout.setContentsMargins(16, 16, 16, 16)
        session_panel_layout.setSpacing(8)
        session_panel_layout.setAlignment(Qt.AlignTop)

        sessions_header = QLabel("Sessions")
        sessions_header.setFont(QFont("Inter", 15, QFont.Bold))
        sessions_header.setStyleSheet("color: rgba(255,255,255,0.85);")
        session_panel_layout.addWidget(sessions_header)

        # Separator
        panel_sep = QFrame()
        panel_sep.setFixedHeight(1)
        panel_sep.setStyleSheet("background: rgba(255,255,255,0.06);")
        session_panel_layout.addWidget(panel_sep)

        # Session list container
        self.session_list_container = QWidget()
        self.session_list_layout = QVBoxLayout()
        self.session_list_layout.setSpacing(8)
        self.session_list_container.setLayout(self.session_list_layout)
        session_panel_layout.addWidget(self.session_list_container)

        self.session_panel_layout = session_panel_layout

        content_layout.addWidget(self.session_panel, 1)

        main_layout.addWidget(content_frame, 1)

        # Connect click handler
        self.schedule_tree.itemClicked.connect(self.on_race_clicked)

        # Hide sessions panel until a weekend is selected
        self.session_panel.hide()
        self.load_schedule(year=self.current_year)
        
    def load_schedule(self, year=None, events=None):
        if self.loading_session:
            return
        
        self.schedule_tree.clear()
        # hide sessions panel while loading / when nothing selected
        try:
            self.session_panel.hide()
        except Exception:
            pass
        
        #Race filter
        if events is not None:
            self.populate_schedule(events)
            self.loading_session = False
            return
        
        #Year filter
        if year is not None:
            self.loading_session = True
            self.worker = FetchScheduleWorker(int(year))
            self.worker.result.connect(self.populate_schedule)
            self.worker.error.connect(self.show_error)
            self.worker.start()
            return
        
        self.loading_session=False

    def load_by_year(self, year_text):
        if self.loading_session:
            return
        
        #Reset by_race filter
        if year_text!="All Years":
            self.place_combo.blockSignals(True)
            self.place_combo.setCurrentText("All Races")
            self.place_combo.blockSignals(False)

        if year_text=="All Years":
            self.selected_year=None
            self.schedule_tree.clear()
            return
        
        if not year_text.isdigit():
            return
        
        self.selected_year=int(year_text)
        self.load_schedule(year=self.selected_year)

    def load_by_place(self,race_name):
        if race_name=="All Races":
            if self.selected_year is not None:
                self.load_schedule(year=self.selected_year)
            return
        
        #Reset year filter
        self.year_combo.blockSignals(True)
        self.year_combo.setCurrentText("All Years")
        self.year_combo.blockSignals(False)
        self.selected_year=None

        self.schedule_tree.clear()
        
        events=get_race_weekends_by_place(race_name)
        self.load_schedule(events=events)

    def populate_schedule(self, events):
        for event in events:
            # Ensure all columns are strings (QTreeWidgetItem expects text)
            round_str = str(event.get("round_number", ""))
            name = str(event.get("event_name", ""))
            country = str(event.get("country", ""))
            date = str(event.get("date", ""))

            event_item = QTreeWidgetItem([round_str, name, country, date])
            event_item.setData(0, Qt.UserRole, event)
            self.schedule_tree.addTopLevelItem(event_item)

        # Make sure the round column is wide enough to be visible
        try:
            self.schedule_tree.resizeColumnToContents(0)
            self.schedule_tree.resizeColumnToContents(1)
        except Exception:
            pass

        self.loading_session = False

    def on_race_clicked(self, item, column):
        ev = item.data(0, Qt.UserRole)
        # ensure the sessions panel is visible when a race is selected
        try:
            self.session_panel.show()
        except Exception:
            pass
        # determine sessions to show
        ev_type = (ev.get("type") or "").lower()
        sessions = ["Qualifying", "Race"]
        if "sprint" in ev_type:
            sessions.insert(0, "Sprint Qualifying")
            # show sprint-related session
            sessions.insert(2, "Sprint")

        # clear existing session widgets
        for i in reversed(range(self.session_list_layout.count())):
            w = self.session_list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # determine which sessions have already occurred (data available)
        now = datetime.now(timezone.utc)
        session_dates = ev.get("session_dates", {})

        available_sessions = []
        for s in sessions:
            session_date_str = session_dates.get(s)
            if session_date_str:
                try:
                    session_dt = datetime.fromisoformat(session_date_str)
                    if session_dt <= now:
                        available_sessions.append(s)
                except Exception:
                    available_sessions.append(s)
            else:
                # no date info means historical data — assume available
                available_sessions.append(s)

        if not available_sessions:
            label = QLabel("Sessions not yet available")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Inter", 12))
            label.setStyleSheet("color: rgba(255,255,255,0.4); padding: 20px;")
            self.session_list_layout.addWidget(label)
        else:
            for s in sessions:
                if s in available_sessions:
                    btn = SessionButton(s)
                    btn.clicked.connect(
                        lambda _, sname=s, e=ev: self._on_session_button_clicked(e, sname)
                    )
                    self.session_list_layout.addWidget(btn)

    def _on_session_button_clicked(self, ev, session_label):
        """Launch main.py in a separate process to run the selected session.

        Uses the same CLI flags that `main.py` understands: `--qualifying`,
        `--sprint-qualifying`, `--sprint`. Runs the command detached so the
        Qt UI remains responsive.
        """
        try:
            year = ev.get("year") or self.selected_year
        except Exception:
            year = None

        try:
            round_no = int(ev.get("round_number"))
        except Exception:
            round_no = None

        # map button labels to CLI flags
        flag = None
        if session_label == "Qualifying":
            flag = "--qualifying"
        elif session_label == "Sprint Qualifying":
            flag = "--sprint-qualifying"
        elif session_label == "Sprint":
            flag = "--sprint"

        main_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
        )
        cmd = [sys.executable, main_path, "--viewer"]
        if year is not None:
            cmd += ["--year", str(year)]
        if round_no is not None:
            cmd += ["--round", str(round_no)]
        if flag:
            cmd.append(flag)
        if "--verbose" in sys.argv:
            cmd.append("--verbose")

        # Show a styled loading dialog
        dlg = QProgressDialog("Loading session data…", None, 0, 0, self)
        dlg.setWindowTitle("Loading")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setRange(0, 0)
        dlg.setFixedSize(320, 100)
        dlg.setStyleSheet("""
            QProgressDialog {
                background: #161b22;
                color: #e6edf3;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
            }
            QLabel {
                color: #e6edf3;
                font-size: 13px;
            }
        """)
        dlg.show()
        QApplication.processEvents()

        # Create a unique ready-file path and pass it to the child viewer.
        # The viewer process owns FastF1 session loading and signals readiness.
        ready_path = os.path.join(tempfile.gettempdir(), f"f1_ready_{uuid.uuid4().hex}")
        cmd_with_ready = list(cmd) + ["--ready-file", ready_path]

        try:
            proc = subprocess.Popen(cmd_with_ready)
        except Exception as exc:
            try:
                dlg.close()
            except Exception:
                pass
            QMessageBox.critical(self, "Playback error", f"Failed to start playback:\n{exc}")
            return

        # Poll for ready file or child exit
        timer = QTimer(self)

        def _check_ready():
            try:
                if os.path.exists(ready_path):
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    timer.stop()
                    try:
                        os.remove(ready_path)
                    except Exception:
                        pass
                    return
                # if process exited early, show error
                if proc.poll() is not None:
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    timer.stop()
                    QMessageBox.critical(self, "Playback error", "Playback process exited before signaling readiness")
            except Exception:
                # ignore transient file-system errors
                pass

        timer.timeout.connect(_check_ready)
        timer.start(200)
        # keep references
        self._play_proc = proc
        self._ready_timer = timer

    def show_error(self, message):
        QMessageBox.critical(self, "Error", f"Failed to load schedule: {message}")
        self.loading_session = False

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
