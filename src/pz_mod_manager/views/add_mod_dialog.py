from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from pz_mod_manager.models.mod import Mod
from pz_mod_manager.services.steam_api_service import SteamApiError, SteamApiService
from pz_mod_manager.utils.url_parser import extract_workshop_id


class AddModDialog(QDialog):
    def __init__(self, api_service: SteamApiService | None, parent=None):
        super().__init__(parent)
        self._api_service = api_service
        self._mod: Mod | None = None
        self.setWindowTitle("Add Mod")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Workshop URL/ID input
        form = QFormLayout()

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("Paste Steam Workshop URL or numeric ID...")
        form.addRow("Workshop URL/ID:", self._url_edit)

        self._fetch_btn = QPushButton("Fetch Details")
        self._fetch_btn.setEnabled(self._api_service is not None)
        form.addRow("", self._fetch_btn)

        if not self._api_service:
            hint = QLabel("Set your Steam API key in Settings to enable fetching.")
            hint.setStyleSheet("color: gray; font-style: italic;")
            form.addRow("", hint)

        form.addRow("", QLabel(""))  # spacer

        # Fetched / manual fields
        self._workshop_id_edit = QLineEdit()
        self._workshop_id_edit.setPlaceholderText("Numeric workshop ID")
        form.addRow("Workshop ID:", self._workshop_id_edit)

        self._name_edit = QLineEdit()
        self._name_edit.setReadOnly(True)
        self._name_edit.setPlaceholderText("(fetched from Steam)")
        form.addRow("Name:", self._name_edit)

        self._mod_id_edit = QLineEdit()
        self._mod_id_edit.setPlaceholderText("e.g. Hydrocraft (from mod.info id= field)")
        form.addRow("Mod ID:", self._mod_id_edit)

        hint_label = QLabel(
            "The Mod ID is the internal identifier from the mod's mod.info file.\n"
            "It is often (but not always) the same as the mod's display name."
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", hint_label)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Connections
        self._fetch_btn.clicked.connect(self._on_fetch)
        self._url_edit.textChanged.connect(self._on_url_changed)

    def _on_url_changed(self, text: str):
        wid = extract_workshop_id(text)
        if wid:
            self._workshop_id_edit.setText(wid)

    def _on_fetch(self):
        wid = self._workshop_id_edit.text().strip()
        if not wid:
            QMessageBox.warning(self, "Input Required", "Enter a Workshop URL or ID first.")
            return

        if not self._api_service:
            return

        try:
            result = self._api_service.fetch_single_mod(wid)
        except SteamApiError as e:
            QMessageBox.critical(self, "API Error", str(e))
            return

        if result:
            self._name_edit.setText(result.get("title", ""))
        else:
            QMessageBox.warning(self, "Not Found", f"No workshop item found for ID {wid}.")

    def _on_accept(self):
        mod_id = self._mod_id_edit.text().strip()
        workshop_id = self._workshop_id_edit.text().strip()

        if not mod_id:
            QMessageBox.warning(self, "Mod ID Required", "Please enter a Mod ID.")
            return
        if not workshop_id:
            QMessageBox.warning(self, "Workshop ID Required", "Please enter a Workshop ID.")
            return

        self._mod = Mod(
            mod_id=mod_id,
            workshop_id=workshop_id,
            name=self._name_edit.text().strip(),
            enabled=True,
        )
        self.accept()

    def get_mod(self) -> Mod | None:
        return self._mod
