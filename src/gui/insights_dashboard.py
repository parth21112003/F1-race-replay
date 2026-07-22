"""
Unified AI Insights Dashboard — replaces the pattern of opening a new
window for every insight. All AI panels live inside one premium dashboard
with a sidebar for navigation.

Architecture:
  - One shared TelemetryStreamClient (no duplicate TCP connections)
  - QStackedWidget for zero-lag panel switching
  - Sidebar nav buttons highlight the active panel
  - Connection status + message counter shown in the sidebar footer
"""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy,
    QSpacerItem,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor

from src.services.stream import TelemetryStreamClient
from src.gui.pit_wall_window import PITWALL_DARK_THEME


# ── Sidebar nav button ────────────────────────────────────────────────────

class NavButton(QPushButton):
    """Sidebar navigation button with active/idle states."""

    def __init__(self, icon: str, label: str, accent: str = "#e10600",
                 parent=None):
        super().__init__(parent)
        self._accent = accent
        self._active = False
        self._icon = icon
        self._label = label

        self.setCheckable(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Layout inside button: icon + label
        btn_layout = QHBoxLayout(self)
        btn_layout.setContentsMargins(14, 0, 14, 0)
        btn_layout.setSpacing(10)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setFont(QFont("Segoe UI Emoji", 16))
        self._icon_lbl.setFixedWidth(26)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        btn_layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(QFont("Inter", 12))
        self._text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        btn_layout.addWidget(self._text_lbl)
        btn_layout.addStretch()

        self._apply_style(False)

    def set_active(self, active: bool):
        if self._active == active:
            return
        self._active = active
        self._apply_style(active)

    def _apply_style(self, active: bool):
        if active:
            accent = self._accent
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(30,30,50,1), stop:1 rgba(20,20,40,1));
                    border: none;
                    border-left: 3px solid {accent};
                    border-radius: 0px;
                    text-align: left;
                    padding: 0;
                }}
            """)
            self._text_lbl.setStyleSheet(f"color: white; font-weight: 700; background: transparent;")
            self._icon_lbl.setStyleSheet("background: transparent;")
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    text-align: left;
                    padding: 0;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.04);
                }
            """)
            self._text_lbl.setStyleSheet("color: rgba(255,255,255,0.55); font-weight: 400; background: transparent;")
            self._icon_lbl.setStyleSheet("background: transparent;")


# ── Panel wrapper ─────────────────────────────────────────────────────────

class PanelDefinition:
    """Describes one panel in the dashboard."""
    def __init__(self, icon: str, label: str, accent: str,
                 widget: QWidget, on_telemetry=None):
        self.icon = icon
        self.label = label
        self.accent = accent
        self.widget = widget
        self.on_telemetry = on_telemetry   # callable(data)
        self.nav_btn: Optional[NavButton] = None


# ── Main dashboard ────────────────────────────────────────────────────────

class InsightsDashboard(QMainWindow):
    """
    Single-window AI Insights Dashboard.

    All insight panels are embedded in a QStackedWidget.
    One TelemetryStreamClient is shared across all panels.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏎 F1 AI Insights Dashboard")
        self.setGeometry(80, 60, 1160, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(PITWALL_DARK_THEME + """
            QMainWindow { background: #0a0e1a; }
        """)

        self._panels: list[PanelDefinition] = []
        self._active_index = 0
        self._message_count = 0

        # Build UI first (stacked widget must exist before panels are added)
        self._build_skeleton()

        # Import and add panels
        self._add_commentary_panel()
        self._add_strategist_panel()

        # Wire up stream client (one shared client for all panels)
        self._client = TelemetryStreamClient()
        self._client.data_received.connect(self._dispatch_telemetry)
        self._client.connection_status.connect(self._on_connection_status)
        self._client.error_occurred.connect(self._on_stream_error)
        self._client.start()

        # Select first panel
        if self._panels:
            self._switch_to(0)

    # ── Skeleton UI ───────────────────────────────────────────────────────

    def _build_skeleton(self):
        root = QWidget()
        root.setStyleSheet("background: #0a0e1a;")
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(200)
        self._sidebar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #111827, stop:1 #0d1117);
                border-right: 1px solid rgba(255,255,255,0.06);
            }
        """)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo area
        logo_frame = QFrame()
        logo_frame.setFixedHeight(70)
        logo_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(225,6,0,0.15), stop:1 transparent);
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
        """)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(14, 0, 14, 0)

        logo_title = QLabel("🏎 AI Insights")
        logo_title.setFont(QFont("Inter", 14, QFont.Bold))
        logo_title.setStyleSheet("color: white; background: transparent;")
        logo_layout.addWidget(logo_title)

        logo_sub = QLabel("Race Intelligence Hub")
        logo_sub.setFont(QFont("Inter", 9))
        logo_sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        logo_layout.addWidget(logo_sub)

        sidebar_layout.addWidget(logo_frame)

        # Divider label
        section_lbl = QLabel("PANELS")
        section_lbl.setFont(QFont("Inter", 8, QFont.Bold))
        section_lbl.setStyleSheet("""
            color: rgba(255,255,255,0.25);
            background: transparent;
            padding: 12px 14px 4px 14px;
            letter-spacing: 2px;
        """)
        sidebar_layout.addWidget(section_lbl)

        # Nav buttons container (filled by _add_*_panel)
        self._nav_container = QVBoxLayout()
        self._nav_container.setContentsMargins(0, 0, 0, 0)
        self._nav_container.setSpacing(2)
        sidebar_layout.addLayout(self._nav_container)

        sidebar_layout.addStretch()

        # Footer: connection status
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("""
            QFrame {
                background: rgba(0,0,0,0.2);
                border-top: 1px solid rgba(255,255,255,0.06);
            }
        """)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(14, 6, 14, 6)
        footer_layout.setSpacing(2)

        self._conn_label = QLabel("⬤  Disconnected")
        self._conn_label.setFont(QFont("Inter", 10, QFont.Bold))
        self._conn_label.setStyleSheet("color: #f85149; background: transparent;")
        footer_layout.addWidget(self._conn_label)

        self._msg_label = QLabel("Frames: 0")
        self._msg_label.setFont(QFont("Inter", 9))
        self._msg_label.setStyleSheet("color: rgba(255,255,255,0.3); background: transparent;")
        footer_layout.addWidget(self._msg_label)

        sidebar_layout.addWidget(footer)
        root_layout.addWidget(self._sidebar)

        # ── Content area ───────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setStyleSheet("QFrame { background: #0d1117; }")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: #0d1117; }")
        content_layout.addWidget(self._stack)

        root_layout.addWidget(content_frame, 1)

    # ── Panel registration ────────────────────────────────────────────────

    def _register_panel(self, panel: PanelDefinition):
        """Add a panel to the sidebar and stacked widget."""
        idx = len(self._panels)
        self._panels.append(panel)

        # Nav button
        btn = NavButton(panel.icon, panel.label, accent=panel.accent)
        btn.clicked.connect(lambda checked, i=idx: self._switch_to(i))
        panel.nav_btn = btn
        self._nav_container.addWidget(btn)

        # Content widget in stack
        self._stack.addWidget(panel.widget)

    def _switch_to(self, index: int):
        """Switch the active panel."""
        self._active_index = index
        self._stack.setCurrentIndex(index)
        for i, p in enumerate(self._panels):
            if p.nav_btn:
                p.nav_btn.set_active(i == index)

    # ── Panel factories ───────────────────────────────────────────────────

    def _add_commentary_panel(self):
        """Build the AI Commentary panel and register it."""
        from src.insights.ai_commentary_window import AICommentaryWindow
        # Create window but don't show it — extract its central widget
        self._commentary_win = AICommentaryWindow(auto_start_client=False)
        widget = self._commentary_win.takeCentralWidget()
        # Reparent into the dashboard
        widget.setParent(None)

        panel = PanelDefinition(
            icon="🧠",
            label="AI Commentary",
            accent="#ab47bc",
            widget=widget,
            on_telemetry=self._commentary_win.on_telemetry_data,
        )
        self._register_panel(panel)

    def _add_strategist_panel(self):
        """Build the AI Strategist chat panel and register it."""
        from src.insights.ai_strategist_window import AIStrategistWindow
        self._strategist_win = AIStrategistWindow(auto_start_client=False)
        widget = self._strategist_win.takeCentralWidget()
        widget.setParent(None)

        panel = PanelDefinition(
            icon="🤖",
            label="AI Strategist",
            accent="#e10600",
            widget=widget,
            on_telemetry=self._strategist_win.on_telemetry_data,
        )
        self._register_panel(panel)

    # ── Telemetry routing ─────────────────────────────────────────────────

    def _dispatch_telemetry(self, data: dict):
        """Route incoming telemetry to every registered panel."""
        self._message_count += 1
        self._msg_label.setText(f"Frames: {self._message_count:,}")

        for panel in self._panels:
            if panel.on_telemetry:
                try:
                    panel.on_telemetry(data)
                except Exception as e:
                    print(f"Panel '{panel.label}' error: {e}")

    def _on_connection_status(self, status: str):
        if status == "Connected":
            self._conn_label.setText("⬤  Connected")
            self._conn_label.setStyleSheet("color: #3fb950; font-weight: bold; background: transparent;")
        elif status == "Connecting...":
            self._conn_label.setText("⬤  Connecting…")
            self._conn_label.setStyleSheet("color: #d29922; font-weight: bold; background: transparent;")
        else:
            self._conn_label.setText("⬤  Disconnected")
            self._conn_label.setStyleSheet("color: #f85149; font-weight: bold; background: transparent;")

    def _on_stream_error(self, error_msg: str):
        print(f"InsightsDashboard stream error: {error_msg}")

    # ── Cleanup ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        try:
            for panel_window in (
                getattr(self, "_commentary_win", None),
                getattr(self, "_strategist_win", None),
            ):
                if panel_window is not None:
                    panel_window.stop_telemetry_client()
                    panel_window.deleteLater()
            if self._client.isRunning():
                self._client.stop()
                self._client.wait(2000)
        except Exception as e:
            print(f"Dashboard cleanup error: {e}")
        finally:
            event.accept()


# ── Standalone launch ─────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    win = InsightsDashboard()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
