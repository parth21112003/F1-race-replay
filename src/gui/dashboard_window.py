from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.f1_data import (
    get_all_unique_race_names,
    get_race_weekends_by_place,
)
from src.gui.pit_wall_window import PITWALL_DARK_THEME
from src.gui.race_selection import FetchScheduleWorker, SessionButton
from src.gui.settings_dialog import SettingsDialog
from src.lib.season import get_season
from src.services.stream import TelemetryStreamClient


DASHBOARD_STYLE = PITWALL_DARK_THEME + """
QMainWindow { background: #080c12; }
QFrame#Sidebar {
    background: #0d1117;
    border-right: 1px solid rgba(255,255,255,0.08);
}
QFrame#Stage {
    background: #101722;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
}
QFrame#PanelFrame {
    background: #0d1117;
    border-left: 1px solid rgba(255,255,255,0.08);
}
QPushButton#NavButton {
    border-radius: 6px;
    text-align: left;
    padding: 10px 12px;
}
QPushButton#NavButton:checked {
    background: rgba(225, 6, 0, 0.18);
    border-color: rgba(225, 6, 0, 0.5);
    color: white;
}
QTreeWidget {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
}
"""


class DashboardWindow(QMainWindow):
    """Single app shell for race selection, replay launch, and embedded insights."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Race Replay Dashboard")
        self.setMinimumSize(1180, 720)
        self.resize(1320, 820)
        self.setStyleSheet(DASHBOARD_STYLE)

        self.current_year = get_season()
        self.selected_year: int | None = self.current_year
        self.selected_event: dict | None = None
        self.selected_session_label: str | None = None
        self.schedule_worker = None
        self._panel_windows: list[object] = []
        self._panel_handlers: list[tuple[str, object]] = []
        self._nav_buttons: list[QPushButton] = []
        self._message_count = 0

        self._build_ui()
        self._build_panels()
        self._setup_telemetry_client()
        self.load_schedule(self.current_year)

    # ------------------------------------------------------------------
    # UI shell
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = QFrame()
        self._sidebar.setObjectName("Sidebar")
        self._sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        title = QLabel("F1 Dashboard")
        title.setFont(QFont("Inter", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        sidebar_layout.addWidget(title)

        subtitle = QLabel("Replay control and live insights")
        subtitle.setFont(QFont("Inter", 10))
        subtitle.setStyleSheet("color: rgba(255,255,255,0.45);")
        subtitle.setWordWrap(True)
        sidebar_layout.addWidget(subtitle)

        sidebar_layout.addSpacing(10)
        self._add_nav_button(sidebar_layout, "Race Setup", 0)
        self._add_nav_button(sidebar_layout, "AI Commentary", 1)
        self._add_nav_button(sidebar_layout, "AI Strategist", 2)
        self._add_nav_button(sidebar_layout, "Track Map", 3)
        self._add_nav_button(sidebar_layout, "Race Control", 4)
        self._add_nav_button(sidebar_layout, "Settings", 5)

        sidebar_layout.addStretch()

        self._conn_label = QLabel("Telemetry: disconnected")
        self._conn_label.setFont(QFont("Inter", 10, QFont.Bold))
        self._conn_label.setStyleSheet("color: #f85149;")
        sidebar_layout.addWidget(self._conn_label)

        self._frame_label = QLabel("Frames: 0")
        self._frame_label.setFont(QFont("Inter", 9))
        self._frame_label.setStyleSheet("color: rgba(255,255,255,0.4);")
        sidebar_layout.addWidget(self._frame_label)

        layout.addWidget(self._sidebar)

        self._stage = QFrame()
        self._stage.setObjectName("Stage")
        stage_layout = QVBoxLayout(self._stage)
        stage_layout.setContentsMargins(22, 22, 22, 22)
        stage_layout.setSpacing(14)

        self._stage_title = QLabel("No session launched")
        self._stage_title.setFont(QFont("Inter", 22, QFont.Bold))
        self._stage_title.setStyleSheet("color: white;")
        stage_layout.addWidget(self._stage_title)

        self._stage_meta = QLabel("Choose a race and session from Race Setup.")
        self._stage_meta.setFont(QFont("Inter", 12))
        self._stage_meta.setStyleSheet("color: rgba(255,255,255,0.55);")
        self._stage_meta.setWordWrap(True)
        stage_layout.addWidget(self._stage_meta)

        stage_layout.addStretch()

        self._stage_hint = QLabel(
            "Milestone 1 keeps the existing Arcade replay viewer as the race "
            "visualization engine. This center stage is ready for the native "
            "embedded replay widget in the next milestone."
        )
        self._stage_hint.setFont(QFont("Inter", 11))
        self._stage_hint.setStyleSheet("color: rgba(255,255,255,0.42);")
        self._stage_hint.setWordWrap(True)
        stage_layout.addWidget(self._stage_hint)

        layout.addWidget(self._stage, 1)

        self._panel_frame = QFrame()
        self._panel_frame.setObjectName("PanelFrame")
        self._panel_frame.setFixedWidth(430)
        panel_layout = QVBoxLayout(self._panel_frame)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self._panel_stack = QStackedWidget()
        panel_layout.addWidget(self._panel_stack)
        layout.addWidget(self._panel_frame)

    def _add_nav_button(self, layout: QVBoxLayout, label: str, index: int):
        btn = QPushButton(label)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, i=index: self._switch_panel(i))
        layout.addWidget(btn)
        self._nav_buttons.append(btn)
        if index == 0:
            btn.setChecked(True)

    def _build_panels(self):
        self._panel_stack.addWidget(self._build_race_setup_panel())
        self._panel_stack.addWidget(self._embed_commentary_panel())
        self._panel_stack.addWidget(self._embed_strategist_panel())
        self._panel_stack.addWidget(self._placeholder_panel(
            "Track Map",
            "The track position map will be embedded here in the next pass. "
            "For now, AI panels are already live inside this dashboard.",
        ))
        self._panel_stack.addWidget(self._placeholder_panel(
            "Race Control",
            "Race-control feed, driver telemetry, and raw telemetry panels "
            "will move into this stack after the replay renderer migration.",
        ))
        self._panel_stack.addWidget(self._build_settings_panel())

    def _switch_panel(self, index: int):
        self._panel_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    # ------------------------------------------------------------------
    # Race selection
    # ------------------------------------------------------------------

    def _build_race_setup_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("Race Setup")
        header.setFont(QFont("Inter", 16, QFont.Bold))
        layout.addWidget(header)

        self.year_combo = QComboBox()
        self.year_combo.addItem("All Years")
        for year in range(2018, self.current_year + 1):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(self.current_year))
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        layout.addWidget(self.year_combo)

        self.place_combo = QComboBox()
        self.place_combo.addItem("All Races")
        self.place_combo.addItems(get_all_unique_race_names())
        self.place_combo.currentTextChanged.connect(self._on_place_changed)
        layout.addWidget(self.place_combo)

        self.schedule_tree = QTreeWidget()
        self.schedule_tree.setHeaderLabels(["Rnd", "Event", "Country"])
        self.schedule_tree.setRootIsDecorated(False)
        self.schedule_tree.itemClicked.connect(self._on_race_clicked)
        self.schedule_tree.setColumnWidth(0, 44)
        self.schedule_tree.setColumnWidth(1, 180)
        layout.addWidget(self.schedule_tree, 1)

        session_title = QLabel("Sessions")
        session_title.setFont(QFont("Inter", 12, QFont.Bold))
        layout.addWidget(session_title)

        self.session_buttons = QWidget()
        self.session_buttons_layout = QVBoxLayout(self.session_buttons)
        self.session_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.session_buttons_layout.setSpacing(8)
        layout.addWidget(self.session_buttons)

        self._selection_label = QLabel("Select a race weekend.")
        self._selection_label.setWordWrap(True)
        self._selection_label.setStyleSheet("color: rgba(255,255,255,0.45);")
        layout.addWidget(self._selection_label)

        self._launch_btn = QPushButton("Launch Selected Session")
        self._launch_btn.setEnabled(False)
        self._launch_btn.setCursor(Qt.PointingHandCursor)
        self._launch_btn.clicked.connect(self._launch_selected_session)
        layout.addWidget(self._launch_btn)

        return panel

    def load_schedule(self, year: int):
        self.schedule_tree.clear()
        self._clear_session_buttons()
        self.schedule_worker = FetchScheduleWorker(year)
        self.schedule_worker.result.connect(self._populate_schedule)
        self.schedule_worker.error.connect(self._show_schedule_error)
        self.schedule_worker.start()

    def _populate_schedule(self, events):
        self.schedule_tree.clear()
        for event in events:
            item = QTreeWidgetItem([
                str(event.get("round_number", "")),
                str(event.get("event_name", "")),
                str(event.get("country", "")),
            ])
            item.setData(0, Qt.UserRole, event)
            self.schedule_tree.addTopLevelItem(item)
        self.schedule_tree.resizeColumnToContents(0)

    def _on_year_changed(self, year_text: str):
        if year_text == "All Years":
            self.selected_year = None
            self.schedule_tree.clear()
            self._clear_session_buttons()
            return
        if not year_text.isdigit():
            return
        self.selected_year = int(year_text)
        self.place_combo.blockSignals(True)
        self.place_combo.setCurrentText("All Races")
        self.place_combo.blockSignals(False)
        self.load_schedule(self.selected_year)

    def _on_place_changed(self, race_name: str):
        self._clear_session_buttons()
        if race_name == "All Races":
            if self.selected_year is not None:
                self.load_schedule(self.selected_year)
            return
        self.year_combo.blockSignals(True)
        self.year_combo.setCurrentText("All Years")
        self.year_combo.blockSignals(False)
        self.selected_year = None
        self._populate_schedule(get_race_weekends_by_place(race_name))

    def _on_race_clicked(self, item, column):
        event = item.data(0, Qt.UserRole)
        self.selected_event = event
        self.selected_session_label = None
        self._launch_btn.setEnabled(False)
        self._clear_session_buttons()

        sessions = ["Qualifying", "Race"]
        if "sprint" in str(event.get("type", "")).lower():
            sessions = ["Sprint Qualifying", "Qualifying", "Sprint", "Race"]

        available = self._available_sessions(event, sessions)
        for session_label in sessions:
            if session_label not in available:
                continue
            btn = SessionButton(session_label)
            btn.clicked.connect(
                lambda checked=False, label=session_label: self._select_session(label)
            )
            self.session_buttons_layout.addWidget(btn)

        if available:
            self._selection_label.setText("Choose a session, then launch the replay.")
        else:
            self._selection_label.setText("No sessions are available for this race yet.")

    def _available_sessions(self, event: dict, sessions: list[str]) -> list[str]:
        now = datetime.now(timezone.utc)
        session_dates = event.get("session_dates", {})
        available = []
        for session in sessions:
            session_date_str = session_dates.get(session)
            if not session_date_str:
                available.append(session)
                continue
            try:
                if datetime.fromisoformat(session_date_str) <= now:
                    available.append(session)
            except Exception:
                available.append(session)
        return available

    def _select_session(self, session_label: str):
        self.selected_session_label = session_label
        event_name = self.selected_event.get("event_name", "Selected race") if self.selected_event else "Selected race"
        year = self.selected_event.get("year") or self.selected_year if self.selected_event else self.selected_year
        self._selection_label.setText(f"Selected: {event_name} - {session_label}")
        self._launch_btn.setEnabled(True)
        self._stage_title.setText(f"{event_name} - {session_label}")
        self._stage_meta.setText(
            f"Season {year or 'unknown'}, Round "
            f"{self.selected_event.get('round_number', '?') if self.selected_event else '?'}."
        )

    def _clear_session_buttons(self):
        while self.session_buttons_layout.count():
            item = self.session_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_schedule_error(self, message: str):
        QMessageBox.critical(self, "Schedule error", f"Failed to load schedule:\n{message}")

    # ------------------------------------------------------------------
    # Viewer launch
    # ------------------------------------------------------------------

    def _launch_selected_session(self):
        if not self.selected_event or not self.selected_session_label:
            return

        year = self.selected_event.get("year") or self.selected_year
        round_no = self.selected_event.get("round_number")

        flag = None
        if self.selected_session_label == "Qualifying":
            flag = "--qualifying"
        elif self.selected_session_label == "Sprint Qualifying":
            flag = "--sprint-qualifying"
        elif self.selected_session_label == "Sprint":
            flag = "--sprint"

        main_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
        )
        cmd = [sys.executable, main_path, "--viewer", "--no-insights-menu"]
        if year is not None:
            cmd += ["--year", str(year)]
        if round_no is not None:
            cmd += ["--round", str(int(round_no))]
        if flag:
            cmd.append(flag)
        if "--verbose" in sys.argv:
            cmd.append("--verbose")

        ready_path = os.path.join(tempfile.gettempdir(), f"f1_ready_{uuid.uuid4().hex}")
        cmd += ["--ready-file", ready_path]

        dlg = QProgressDialog("Loading replay session...", None, 0, 0, self)
        dlg.setWindowTitle("Launching Replay")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setRange(0, 0)
        dlg.show()
        QApplication.processEvents()

        try:
            proc = subprocess.Popen(cmd)
        except Exception as exc:
            dlg.close()
            QMessageBox.critical(self, "Playback error", f"Failed to start playback:\n{exc}")
            return

        timer = QTimer(self)

        def check_ready():
            if os.path.exists(ready_path):
                dlg.close()
                timer.stop()
                try:
                    os.remove(ready_path)
                except Exception:
                    pass
                self._stage_meta.setText("Replay is running. Feature panels will update when telemetry connects.")
                return
            if proc.poll() is not None:
                dlg.close()
                timer.stop()
                QMessageBox.critical(self, "Playback error", "Playback exited before signaling readiness.")

        timer.timeout.connect(check_ready)
        timer.start(200)
        self._play_proc = proc
        self._ready_timer = timer

    # ------------------------------------------------------------------
    # Embedded panels and telemetry
    # ------------------------------------------------------------------

    def _embed_commentary_panel(self) -> QWidget:
        from src.insights.ai_commentary_window import AICommentaryWindow

        window = AICommentaryWindow(auto_start_client=False)
        widget = window.takeCentralWidget()
        widget.setParent(None)
        self._panel_windows.append(window)
        self._panel_handlers.append(("AI Commentary", window.on_telemetry_data))
        return widget

    def _embed_strategist_panel(self) -> QWidget:
        from src.insights.ai_strategist_window import AIStrategistWindow

        window = AIStrategistWindow(auto_start_client=False)
        widget = window.takeCentralWidget()
        widget.setParent(None)
        self._panel_windows.append(window)
        self._panel_handlers.append(("AI Strategist", window.on_telemetry_data))
        return widget

    def _setup_telemetry_client(self):
        self._client = TelemetryStreamClient()
        self._client.data_received.connect(self._dispatch_telemetry)
        self._client.connection_status.connect(self._on_connection_status)
        self._client.error_occurred.connect(self._on_stream_error)
        self._client.start()

    def _dispatch_telemetry(self, data: dict):
        self._message_count += 1
        self._frame_label.setText(f"Frames: {self._message_count:,}")
        for label, handler in self._panel_handlers:
            try:
                handler(data)
            except Exception as exc:
                print(f"Dashboard panel '{label}' error: {exc}")

    def _on_connection_status(self, status: str):
        if status == "Connected":
            self._conn_label.setText("Telemetry: connected")
            self._conn_label.setStyleSheet("color: #3fb950;")
        elif status == "Connecting...":
            self._conn_label.setText("Telemetry: connecting")
            self._conn_label.setStyleSheet("color: #d29922;")
        else:
            self._conn_label.setText("Telemetry: disconnected")
            self._conn_label.setStyleSheet("color: #f85149;")

    def _on_stream_error(self, error_msg: str):
        self.statusBar().showMessage(error_msg, 3500)

    # ------------------------------------------------------------------
    # Other panels
    # ------------------------------------------------------------------

    def _placeholder_panel(self, title: str, body: str) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setFont(QFont("Inter", 16, QFont.Bold))
        layout.addWidget(label)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setStyleSheet("color: rgba(255,255,255,0.55);")
        layout.addWidget(text)
        layout.addStretch()
        return panel

    def _build_settings_panel(self) -> QWidget:
        panel = self._placeholder_panel(
            "Settings",
            "Use the button below to edit cache paths and AI provider settings.",
        )
        button = QPushButton("Open Settings")
        button.clicked.connect(lambda: SettingsDialog(self).exec())
        panel.layout().insertWidget(2, button)
        return panel

    def closeEvent(self, event):
        try:
            if self._client.isRunning():
                self._client.stop()
                self._client.wait(2000)
            for window in self._panel_windows:
                window.stop_telemetry_client()
                window.deleteLater()
        except Exception as exc:
            print(f"Dashboard cleanup error: {exc}")
        finally:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
