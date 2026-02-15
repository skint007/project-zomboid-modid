from __future__ import annotations

import webbrowser

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

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

    def _on_accept(self):
        self._settings.api_key = self._api_key_edit.text().strip()
        self.accept()
