from PySide6.QtWidgets import QMainWindow, QStatusBar, QLabel
from PySide6.QtCore import Qt
from src.services.stream import TelemetryStreamClient


# ── Premium dark-theme stylesheet (shared by all PitWallWindow subclasses) ──
PITWALL_DARK_THEME = """
QMainWindow {
    background: #0d1117;
    color: #e6edf3;
}
QWidget {
    background: transparent;
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QStatusBar {
    background: rgba(255, 255, 255, 0.03);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.5);
    font-size: 11px;
    padding: 2px 8px;
}
QLabel {
    color: #e6edf3;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: rgba(255, 255, 255, 0.03);
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QPushButton {
    background: rgba(255, 255, 255, 0.06);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(225, 6, 0, 0.4);
}
QPushButton:pressed {
    background: rgba(225, 6, 0, 0.15);
}
QComboBox {
    background: rgba(255, 255, 255, 0.06);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: rgba(225, 6, 0, 0.4);
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #161b22;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    selection-background-color: rgba(225, 6, 0, 0.25);
    outline: none;
}
QLineEdit {
    background: rgba(255, 255, 255, 0.06);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: rgba(225, 6, 0, 0.5);
}
QGroupBox {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-size: 13px;
    font-weight: 600;
    color: #e6edf3;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: rgba(255, 255, 255, 0.7);
}
"""


class PitWallWindow(QMainWindow):
    def __init__(self, auto_start_client: bool = True):
        super().__init__()
        self._auto_start_client = auto_start_client
        
        # Default window properties
        self.setGeometry(100, 100, 1000, 700)
        
        # Apply premium dark theme
        self.setStyleSheet(PITWALL_DARK_THEME)
        
        # Data tracking
        self.message_count = 0
        
        # Initialize telemetry client
        self.client = TelemetryStreamClient()
        self.client.data_received.connect(self._handle_data_received)
        self.client.connection_status.connect(self._handle_connection_status)
        self.client.error_occurred.connect(self._handle_error)
        
        # Setup status bar
        self._setup_status_bar()
        
        # Call subclass UI setup
        self.setup_ui()
        
        if self._auto_start_client:
            self.start_telemetry_client()

    def start_telemetry_client(self):
        """Start the telemetry client if it is not already running."""
        if self.client and not self.client.isRunning():
            self.client.start()

    def stop_telemetry_client(self):
        """Stop the telemetry client and wait briefly for shutdown."""
        if self.client and self.client.isRunning():
            self.client.stop()
            if not self.client.wait(2000):  # Wait max 2 seconds
                print("Warning: Telemetry client did not stop in time")
    
    def _setup_status_bar(self):
        """Initialize the status bar with connection indicator."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.connection_label = QLabel("⬤ Disconnected")
        self.connection_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 11px;")
        self.status_bar.addPermanentWidget(self.connection_label)
        
        self.messages_label = QLabel("Messages: 0")
        self.messages_label.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        self.status_bar.addPermanentWidget(self.messages_label)
    
    def _handle_data_received(self, data):
        """Internal handler for received telemetry data."""
        self.message_count += 1
        self.messages_label.setText(f"Messages: {self.message_count}")
        
        # Call subclass implementation
        self.on_telemetry_data(data)
    
    def _handle_connection_status(self, status):
        """Internal handler for connection status changes."""
        if status == "Connected":
            self.connection_label.setText("⬤ Connected")
            self.connection_label.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 11px;")
        elif status == "Connecting...":
            self.connection_label.setText("⬤ Connecting…")
            self.connection_label.setStyleSheet("color: #d29922; font-weight: bold; font-size: 11px;")
        else:
            self.connection_label.setText("⬤ Disconnected")
            self.connection_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 11px;")
        
        # Notify subclass
        self.on_connection_status_changed(status)
    
    def _handle_error(self, error_msg):
        """Internal handler for stream errors."""
        self.status_bar.showMessage(f"Error: {error_msg}", 5000)
        
        # Notify subclass
        self.on_stream_error(error_msg)
    
    def closeEvent(self, event):
        """Handle window close event - cleanup telemetry client."""
        try:
            self.stop_telemetry_client()
        except Exception as e:
            print(f"Error during telemetry cleanup: {e}")
        finally:
            event.accept()
    
    # Abstract methods for subclasses to implement
    
    def setup_ui(self):
        """
        Override this method to create your custom UI.
        
        Called during __init__ after the status bar is set up but before
        the telemetry client starts.
        
        Example:
            def setup_ui(self):
                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                layout = QVBoxLayout(central_widget)
                self.data_label = QLabel("Waiting for data...")
                layout.addWidget(self.data_label)
        """
        pass
    
    def on_telemetry_data(self, data):
        """
        Override this method to process incoming telemetry data.
        
        This is called automatically whenever new telemetry data arrives
        from the stream. The data dictionary contains the current frame's
        telemetry information.
        
        Args:
            data: Dictionary containing telemetry data with keys like:
                - frame_index: Current frame number
                - frame: Telemetry frame with driver data
                - track_status: Current track status
                - playback_speed: Current playback speed
                - is_paused: Whether playback is paused
                - total_frames: Total number of frames in session
        
        Example:
            def on_telemetry_data(self, data):
                if 'frame_index' in data:
                    self.frame_label.setText(f"Frame: {data['frame_index']}")
                if 'frame' in data and 'drivers' in data['frame']:
                    driver_count = len(data['frame']['drivers'])
                    self.driver_label.setText(f"Drivers: {driver_count}")
        """
        pass
    
    def on_connection_status_changed(self, status):
        """
        Override this method to respond to connection status changes.
        
        This is called whenever the connection state changes (Connected,
        Connecting..., Disconnected).
        
        Args:
            status: String indicating the current connection state
        
        Example:
            def on_connection_status_changed(self, status):
                if status == "Connected":
                    self.enable_controls()
                else:
                    self.disable_controls()
        """
        pass
    
    def on_stream_error(self, error_msg):
        """
        Override this method to handle stream errors.
        
        This is called when an error occurs during streaming (e.g.,
        connection errors, data parsing errors).
        
        Args:
            error_msg: String describing the error that occurred
        
        Example:
            def on_stream_error(self, error_msg):
                self.error_log.append(f"ERROR: {error_msg}")
        """
        pass
