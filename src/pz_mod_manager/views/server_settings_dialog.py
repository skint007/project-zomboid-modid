from __future__ import annotations

import re

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pz_mod_manager.services.ini_service import IniService, IniSetting
from pz_mod_manager.utils.constants import APP_NAME


class ServerSettingsDialog(QDialog):
    def __init__(self, ini_service: IniService, file_path: str, parent=None):
        super().__init__(parent)
        self._ini_service = ini_service
        self._file_path = file_path
        self._widgets: dict[str, QWidget] = {}
        self._original: dict[str, str] = {}
        self._qsettings = QSettings(APP_NAME, APP_NAME)

        self.setWindowTitle("Server Settings")
        self.setMinimumSize(650, 500)
        self._restore_geometry()

        settings = self._ini_service.read_all_settings(file_path)
        self._setup_ui(settings)

    def _setup_ui(self, settings: list[IniSetting]):
        layout = QVBoxLayout(self)

        # Scrollable area for all the settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for setting in settings:
            self._original[setting.key] = setting.value
            widget = self._create_widget(setting)
            self._widgets[setting.key] = widget

            label_text = self._key_to_label(setting.key)

            # Build a label with bold header and normal-weight description
            desc = ""
            if setting.comment:
                desc = re.sub(
                    r"\s*(?:Min|Max|Default):\s*\S+", "", setting.comment
                ).strip().rstrip(".")

            if desc:
                rich = f"<b>{label_text}</b><br>{desc}"
            else:
                rich = f"<b>{label_text}</b>"

            label = QLabel(rich)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.setMinimumWidth(350)
            form.addRow(label, widget)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_widget(self, setting: IniSetting) -> QWidget:
        vtype = setting.value_type

        if vtype == "bool":
            cb = QCheckBox()
            cb.setChecked(setting.value.lower() == "true")
            return cb

        if vtype == "int":
            spin = QSpinBox()
            spin.setMinimum(int(setting.min_val) if setting.min_val is not None else -2_147_483_648)
            spin.setMaximum(int(setting.max_val) if setting.max_val is not None else 2_147_483_647)
            spin.setValue(int(setting.value))
            return spin

        if vtype == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setMinimum(setting.min_val if setting.min_val is not None else -1_000_000.0)
            spin.setMaximum(setting.max_val if setting.max_val is not None else 1_000_000.0)
            spin.setValue(float(setting.value))
            return spin

        # Default: text field
        edit = QLineEdit(setting.value)
        return edit

    def _get_widget_value(self, key: str) -> str:
        widget = self._widgets[key]
        if isinstance(widget, QCheckBox):
            return "true" if widget.isChecked() else "false"
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            val = widget.value()
            if val == int(val) and "." in self._original.get(key, ""):
                return f"{val:.1f}"
            return f"{val:.2f}" if val != int(val) else f"{val:.1f}"
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    def _on_save(self):
        changes: dict[str, str] = {}
        for key in self._widgets:
            new_val = self._get_widget_value(key)
            if new_val != self._original[key]:
                changes[key] = new_val

        if changes:
            self._ini_service.write_settings(self._file_path, changes)

        self.accept()

    def _restore_geometry(self):
        geom = self._qsettings.value("server_settings_geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(750, 600)

    def closeEvent(self, event):
        self._qsettings.setValue("server_settings_geometry", self.saveGeometry())
        super().closeEvent(event)

    def accept(self):
        self._qsettings.setValue("server_settings_geometry", self.saveGeometry())
        super().accept()

    def reject(self):
        self._qsettings.setValue("server_settings_geometry", self.saveGeometry())
        super().reject()

    @staticmethod
    def _key_to_label(key: str) -> str:
        """Convert CamelCase key to a readable label."""
        spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)
        spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
        return spaced
