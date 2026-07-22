import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QColor, QLinearGradient, QPalette, QPainter


# ── Premium dark theme ────────────────────────────────────────────────────

INSIGHTS_DARK_THEME = """
QMainWindow {
    background: #0d1117;
}
QWidget {
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: rgba(255,255,255,0.02);
    width: 6px;
    border-radius: 3px;
    margin: 0;
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
    height: 0px;
}
"""


class InsightTile(QPushButton):
    """A premium insight launch tile with icon, title, description, and glow hover."""

    def __init__(self, icon: str, name: str, description: str, accent: str = "#e10600",
                 callback=None, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._accent = accent

        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                padding: 10px 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.06);
                border-color: {accent}60;
            }}
            QPushButton:pressed {{
                background: {accent}18;
                border-color: {accent}80;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        icon_label.setFixedWidth(34)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)

        # Text column
        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        name_label = QLabel(name)
        name_label.setFont(QFont("Inter", 12, QFont.Bold))
        name_label.setStyleSheet("color: rgba(255,255,255,0.92);")
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_col.addWidget(name_label)

        desc_label = QLabel(description)
        desc_label.setFont(QFont("Inter", 10))
        desc_label.setStyleSheet("color: rgba(255,255,255,0.42);")
        desc_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_col.addWidget(desc_label)

        layout.addLayout(text_col, 1)

        # Arrow indicator
        arrow = QLabel("›")
        arrow.setFont(QFont("Inter", 18))
        arrow.setStyleSheet(f"color: {accent}60;")
        arrow.setFixedWidth(16)
        arrow.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(arrow)

        if callback:
            self.clicked.connect(callback)


class CategorySection(QFrame):
    """A labelled category group containing InsightTiles."""

    def __init__(self, title: str, accent: str = "#e10600", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 4)
        self._layout.setSpacing(6)

        # Category label
        lbl = QLabel(title.upper())
        lbl.setFont(QFont("Inter", 10, QFont.Bold))
        lbl.setStyleSheet(f"color: {accent}; letter-spacing: 1.5px; padding-left: 4px;")
        self._layout.addWidget(lbl)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {accent}30;")
        self._layout.addWidget(sep)

    def add_tile(self, tile: InsightTile):
        self._layout.addWidget(tile)


class InsightsMenu(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Insights")
        self.setGeometry(50, 50, 340, 680)
        self.setMinimumWidth(300)
        
        # Keep references to opened windows
        self.opened_windows = []
        
        self.setStyleSheet(INSIGHTS_DARK_THEME)
        self.setup_ui()
    
    def _is_window_alive(self, w):
        """Check if a Qt window reference is still valid and not destroyed."""
        try:
            from shiboken6 import isValid
            return isValid(w)
        except ImportError:
            pass
        try:
            # Fallback: accessing any property will throw if the C++ object is deleted
            w.isVisible()
            return True
        except RuntimeError:
            return False

    def _cleanup_dead_windows(self):
        """Remove destroyed window references from the opened_windows list."""
        self.opened_windows = [w for w in self.opened_windows if self._is_window_alive(w)]

    def setup_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background: #0d1117;")
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ── Header ─────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(90)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:0.5 #16213e, stop:1 #0f3460
                );
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
        """)
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(20, 14, 20, 14)
        h_layout.setSpacing(4)

        title = QLabel("🏎️ F1 Insights")
        title.setFont(QFont("Inter", 22, QFont.Bold))
        title.setStyleSheet("color: white;")
        h_layout.addWidget(title)

        subtitle = QLabel("Telemetry analysis & visualization tools")
        subtitle.setFont(QFont("Inter", 11))
        subtitle.setStyleSheet("color: rgba(255,255,255,0.45);")
        h_layout.addWidget(subtitle)

        main_layout.addWidget(header)
        
        # ── Scrollable content ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: #0d1117;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(14, 14, 14, 14)

        # ── AI Insights category ─────────────────────────────────────
        ai_section = CategorySection("AI Insights", accent="#ab47bc")
        ai_section.add_tile(InsightTile(
            "🎮", "AI Insights Dashboard",
            "Commentary, Strategist & more — all in one window",
            accent="#ab47bc",
            callback=self.launch_insights_dashboard
        ))
        content_layout.addWidget(ai_section)

        # ── Live Telemetry category ──────────────────────────────────
        tele_section = CategorySection("Live Telemetry", accent="#42a5f5")
        tele_section.add_tile(InsightTile(
            "📡", "Telemetry Stream Viewer",
            "View raw telemetry data",
            accent="#42a5f5",
            callback=self.launch_telemetry_viewer
        ))
        tele_section.add_tile(InsightTile(
            "📊", "Driver Live Telemetry",
            "Speed, gear, throttle & braking for selected driver",
            accent="#42a5f5",
            callback=self.launch_driver_telemetry
        ))
        content_layout.addWidget(tele_section)

        # ── Track category ───────────────────────────────────────────
        track_section = CategorySection("Track", accent="#00e676")
        track_section.add_tile(InsightTile(
            "🗺️", "Track Position Map",
            "Live driver positions on track map",
            accent="#00e676",
            callback=self.launch_track_position
        ))
        content_layout.addWidget(track_section)

        # ── Race Events category ─────────────────────────────────────
        events_section = CategorySection("Race Events", accent="#ffa726")
        events_section.add_tile(InsightTile(
            "🚩", "Race Control Feed",
            "Live FIA flags, penalties, safety car & DRS status",
            accent="#ffa726",
            callback=self.launch_race_control_feed
        ))
        content_layout.addWidget(events_section)

        # ── Example category ─────────────────────────────────────────
        example_section = CategorySection("Developer", accent="#78909c")
        example_section.add_tile(InsightTile(
            "🧪", "Example Insight Window",
            "Template for building custom insight windows",
            accent="#78909c",
            callback=self.launch_example_window
        ))
        content_layout.addWidget(example_section)
        
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)
        
        # ── Footer ─────────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(44)
        footer.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.02);
                border-top: 1px solid rgba(255,255,255,0.06);
            }
        """)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 0, 16, 0)

        info = QLabel("Requires telemetry stream enabled")
        info.setFont(QFont("Inter", 10))
        info.setStyleSheet("color: rgba(255,255,255,0.35);")
        f_layout.addWidget(info)
        f_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.setFixedHeight(28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.1);
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        f_layout.addWidget(close_btn)

        main_layout.addWidget(footer)
    
    # ── Insight launchers ──────────────────────────────────────────────

    def launch_insights_dashboard(self):
        self._cleanup_dead_windows()
        # Only allow one dashboard at a time
        for w in self.opened_windows:
            if hasattr(w, '_panels'):  # it's a dashboard
                w.activateWindow()
                w.raise_()
                return
        print("🚀 Launching: AI Insights Dashboard")
        from src.gui.insights_dashboard import InsightsDashboard
        window = InsightsDashboard()
        window.show()
        self.opened_windows.append(window)

    def launch_ai_commentary(self):
        """Legacy — now opens the dashboard instead."""
        self.launch_insights_dashboard()

    def launch_ai_strategist(self):
        """Legacy — now opens the dashboard instead."""
        self.launch_insights_dashboard()

    def launch_example_window(self):
        self._cleanup_dead_windows()
        print("🚀 Launching: Example Insight Window")
        from src.insights.example_pit_wall_window import ExamplePitWallWindow
        example_window = ExamplePitWallWindow()
        example_window.show()
        self.opened_windows.append(example_window)

    def launch_driver_telemetry(self):
        self._cleanup_dead_windows()
        print("🚀 Launching: Driver Live Telemetry")
        from src.insights.driver_telemetry_window import DriverTelemetryWindow
        window = DriverTelemetryWindow()
        window.show()
        self.opened_windows.append(window)

    def launch_track_position(self):
        self._cleanup_dead_windows()
        print("🚀 Launching: Track Position Map")
        from src.insights.track_position_window import TrackPositionWindow
        window = TrackPositionWindow()
        window.show()
        self.opened_windows.append(window)

    def launch_race_control_feed(self):
        self._cleanup_dead_windows()
        print("🚀 Launching: Race Control Feed")
        from src.insights.race_control_feed_window import RaceControlFeedWindow
        window = RaceControlFeedWindow()
        window.show()
        self.opened_windows.append(window)

    def launch_telemetry_viewer(self):
        print("🚀 Launching: Telemetry Stream Viewer")
        try:
            import subprocess
            import sys
            subprocess.Popen([sys.executable, "-m", "src.insights.telemetry_stream_viewer"])
        except Exception as e:
            print(f"Failed to launch telemetry viewer: {e}")
            self.show_placeholder_message("Telemetry Stream Viewer")
    
    def show_placeholder_message(self, insight_name):
        from PySide6.QtWidgets import QMessageBox
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Coming Soon")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"{insight_name} will be available soon!")
        msg.setInformativeText(
            "This insight is planned for a future release.\n\n"
            "Developers can use PitWallWindow to create custom insights.\n"
            "See docs/PitWallWindow.md for more information."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()


def launch_insights_menu():
    # Check if QApplication instance already exists
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    menu = InsightsMenu()
    menu.show()
    
    return menu


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("F1 Insights Menu")
    
    menu = InsightsMenu()
    menu.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
