"""
Settings dialog for F1 Race Replay application.
Provides UI for configuring application settings like cache location.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QFrame,
    QCheckBox,
    QComboBox,
)
from PySide6.QtGui import QFont

from src.lib.settings import get_settings


# ── Premium dark theme for the settings dialog ───────────────────────────

SETTINGS_DARK_THEME = """
QDialog {
    background: #0d1117;
    color: #e6edf3;
}
QWidget {
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
QLabel {
    color: #e6edf3;
}
QGroupBox {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    margin-top: 14px;
    padding: 20px 14px 14px 14px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.8);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: rgba(255, 255, 255, 0.6);
}
QLineEdit {
    background: rgba(255, 255, 255, 0.05);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: rgba(225, 6, 0, 0.5);
}
QLineEdit::placeholder {
    color: rgba(255, 255, 255, 0.3);
}
QPushButton {
    background: rgba(255, 255, 255, 0.05);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background: rgba(225, 6, 0, 0.1);
    border-color: rgba(225, 6, 0, 0.4);
    color: white;
}
QPushButton:pressed {
    background: rgba(225, 6, 0, 0.2);
}
QDialogButtonBox QPushButton {
    min-width: 80px;
    padding: 8px 20px;
}
"""


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings()
        self.setStyleSheet(SETTINGS_DARK_THEME)
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(540)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)

        # Header
        header_label = QLabel("⚙ Settings")
        header_label.setFont(QFont("Inter", 18, QFont.Bold))
        header_label.setStyleSheet("color: white; padding-bottom: 4px;")
        layout.addWidget(header_label)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.06);")
        layout.addWidget(sep)

        # Cache Settings Group
        cache_group = QGroupBox("Cache Settings")
        cache_layout = QFormLayout()
        cache_layout.setSpacing(10)
        cache_group.setLayout(cache_layout)

        # FastF1 Cache Location
        cache_path_layout = QHBoxLayout()
        self.cache_path_edit = QLineEdit()
        self.cache_path_edit.setPlaceholderText("Path to FastF1 cache folder...")
        self.cache_browse_btn = QPushButton("Browse…")
        self.cache_browse_btn.setFixedWidth(90)
        self.cache_browse_btn.setCursor(Qt.PointingHandCursor)
        self.cache_browse_btn.clicked.connect(self._browse_cache_location)
        cache_path_layout.addWidget(self.cache_path_edit)
        cache_path_layout.addWidget(self.cache_browse_btn)

        cache_label = QLabel("FastF1 Cache:")
        cache_label.setFont(QFont("Inter", 11, QFont.Bold))
        cache_label.setStyleSheet("color: rgba(255,255,255,0.6);")
        cache_layout.addRow(cache_label, cache_path_layout)

        # Help text for cache
        cache_help = QLabel(
            "Where FastF1 stores downloaded session data. "
            "Changing this won't move existing cached data."
        )
        cache_help.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
        cache_help.setWordWrap(True)
        cache_layout.addRow("", cache_help)

        # Computed Data Location
        computed_path_layout = QHBoxLayout()
        self.computed_path_edit = QLineEdit()
        self.computed_path_edit.setPlaceholderText("Path to computed data folder...")
        self.computed_browse_btn = QPushButton("Browse…")
        self.computed_browse_btn.setFixedWidth(90)
        self.computed_browse_btn.setCursor(Qt.PointingHandCursor)
        self.computed_browse_btn.clicked.connect(self._browse_computed_location)
        computed_path_layout.addWidget(self.computed_path_edit)
        computed_path_layout.addWidget(self.computed_browse_btn)

        computed_label = QLabel("Computed Data:")
        computed_label.setFont(QFont("Inter", 11, QFont.Bold))
        computed_label.setStyleSheet("color: rgba(255,255,255,0.6);")
        cache_layout.addRow(computed_label, computed_path_layout)

        # Help text for computed data
        computed_help = QLabel(
            "Where pre-processed telemetry data is stored. "
            "Speeds up loading previously viewed sessions."
        )
        computed_help.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
        computed_help.setWordWrap(True)
        cache_layout.addRow("", computed_help)

        layout.addWidget(cache_group)

        # AI Settings Group
        ai_group = QGroupBox("AI Commentary (Groq)")
        ai_layout = QFormLayout()
        ai_layout.setSpacing(10)
        ai_group.setLayout(ai_layout)

        # Enable AI checkbox
        self.ai_enabled_checkbox = QCheckBox("Enable AI-powered commentary")
        self.ai_enabled_checkbox.setStyleSheet("""
            QCheckBox {
                color: rgba(255, 255, 255, 0.85);
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background: rgba(255, 255, 255, 0.05);
            }
            QCheckBox::indicator:checked {
                background: rgba(171, 71, 188, 0.5);
                border-color: #ab47bc;
            }
        """)
        ai_layout.addRow(self.ai_enabled_checkbox)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Enter your Groq API key...")
        self.api_key_edit.setEchoMode(QLineEdit.Password)

        api_key_label = QLabel("API Key:")
        api_key_label.setFont(QFont("Inter", 11, QFont.Bold))
        api_key_label.setStyleSheet("color: rgba(255,255,255,0.6);")
        ai_layout.addRow(api_key_label, self.api_key_edit)

        api_key_help = QLabel(
            "Get a free API key from "
            "<a href='https://console.groq.com/keys' "
            "style='color: #ab47bc;'>Groq Console</a>. "
            "Your key is stored locally and never shared."
        )
        api_key_help.setOpenExternalLinks(True)
        api_key_help.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
        api_key_help.setWordWrap(True)
        ai_layout.addRow("", api_key_help)

        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "llama-3.3-70b-versatile",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768"
        ])
        self.model_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.05);
                color: #e6edf3;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox:focus {
                border-color: rgba(171, 71, 188, 0.5);
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #161b22;
                color: #e6edf3;
                border: 1px solid rgba(255,255,255,0.1);
                selection-background-color: rgba(171, 71, 188, 0.3);
            }
        """)

        model_label = QLabel("Model:")
        model_label.setFont(QFont("Inter", 11, QFont.Bold))
        model_label.setStyleSheet("color: rgba(255,255,255,0.6);")
        ai_layout.addRow(model_label, self.model_combo)

        model_help = QLabel(
            "Llama-3.3-70b is recommended for best quality. "
            "8b models are faster but may produce less accurate reasoning."
        )
        model_help.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 11px;")
        model_help.setWordWrap(True)
        ai_layout.addRow("", model_help)

        layout.addWidget(ai_group)

        # Spacer
        layout.addStretch()

        # Bottom actions
        bottom = QHBoxLayout()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background: rgba(248, 81, 73, 0.08);
                color: #f85149;
                border: 1px solid rgba(248, 81, 73, 0.2);
            }
            QPushButton:hover {
                background: rgba(248, 81, 73, 0.15);
                border-color: rgba(248, 81, 73, 0.4);
            }
        """)
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        bottom.addWidget(self.reset_btn)
        bottom.addStretch()

        # Save / Cancel
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(225, 6, 0, 0.15);
                color: white;
                border: 1px solid rgba(225, 6, 0, 0.4);
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(225, 6, 0, 0.25);
                border-color: rgba(225, 6, 0, 0.6);
            }
        """)
        save_btn.clicked.connect(self._save_settings)
        bottom.addWidget(save_btn)

        layout.addLayout(bottom)

    def _load_current_settings(self):
        """Load current settings values into the UI."""
        self.cache_path_edit.setText(self.settings.cache_location)
        self.computed_path_edit.setText(self.settings.computed_data_location)
        self.ai_enabled_checkbox.setChecked(self.settings.enable_ai_commentary)
        self.api_key_edit.setText(self.settings.groq_api_key)

        # Set model combo to current value
        model = self.settings.ai_model
        idx = self.model_combo.findText(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            # Model not in list — add it and select
            self.model_combo.addItem(model)
            self.model_combo.setCurrentText(model)

    def _browse_cache_location(self):
        """Open a folder browser for cache location."""
        current_path = self.cache_path_edit.text() or "."
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select FastF1 Cache Location",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.cache_path_edit.setText(folder)

    def _browse_computed_location(self):
        """Open a folder browser for computed data location."""
        current_path = self.computed_path_edit.text() or "."
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Computed Data Location",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.computed_path_edit.setText(folder)

    def _reset_to_defaults(self):
        """Reset settings to default values."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.settings.reset_to_defaults()
            self._load_current_settings()

    def _save_settings(self):
        """Save the settings and close the dialog."""
        # Validate paths (basic validation - just check they're not empty)
        cache_path = self.cache_path_edit.text().strip()
        computed_path = self.computed_path_edit.text().strip()

        if not cache_path:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                "FastF1 cache location cannot be empty.",
            )
            return

        if not computed_path:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                "Computed data location cannot be empty.",
            )
            return

        # Save settings
        self.settings.cache_location = cache_path
        self.settings.computed_data_location = computed_path
        self.settings.enable_ai_commentary = self.ai_enabled_checkbox.isChecked()
        self.settings.groq_api_key = self.api_key_edit.text().strip()
        self.settings.ai_model = self.model_combo.currentText()
        self.settings.save()

        QMessageBox.information(
            self,
            "Settings Saved",
            "Settings have been saved successfully.\n\n"
            "Note: AI commentary changes will apply to the next data processing run.\n"
            "Cache location changes will take effect for new data downloads.",
        )

        self.accept()
