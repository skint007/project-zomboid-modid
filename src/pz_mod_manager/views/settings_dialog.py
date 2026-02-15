from __future__ import annotations

import webbrowser

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from pz_mod_manager.services.settings_service import SettingsService


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsService, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Workshop path
        ws_layout = QHBoxLayout()
        self._workshop_edit = QLineEdit()
        self._workshop_edit.setPlaceholderText("Path to Steam workshop content directory")
        self._workshop_edit.setText(self._settings.workshop_path)
        ws_layout.addWidget(self._workshop_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_workshop)
        ws_layout.addWidget(browse_btn)
        form.addRow("Workshop Path:", ws_layout)

        ws_hint = QLabel(
            "Path to the Steam workshop directory containing downloaded mods.\n"
            "e.g. /path/to/steamapps/workshop/ or /path/to/workshop-mods/\n"
            "Used to resolve correct Mod ID <-> Workshop ID pairings."
        )
        ws_hint.setWordWrap(True)
        ws_hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", ws_hint)

        # Steam API Key
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText("Enter your Steam Web API key")
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setText(self._settings.api_key)
        form.addRow("Steam API Key:", self._api_key_edit)

        get_key_btn = QPushButton("Get API Key from Steam")
        get_key_btn.clicked.connect(
            lambda: webbrowser.open("https://steamcommunity.com/dev/apikey")
        )
        form.addRow("", get_key_btn)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_workshop(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Workshop Directory", self._workshop_edit.text()
        )
        if path:
            self._workshop_edit.setText(path)

    def _on_accept(self):
        self._settings.api_key = self._api_key_edit.text().strip()
        self._settings.workshop_path = self._workshop_edit.text().strip()
        self.accept()
