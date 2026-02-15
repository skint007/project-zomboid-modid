from __future__ import annotations

from PySide6.QtCore import QSettings

from pz_mod_manager.utils.constants import APP_NAME


class SettingsService:
    def __init__(self):
        self._settings = QSettings(APP_NAME, APP_NAME)

    @property
    def api_key(self) -> str:
        return self._settings.value("steam_api_key", "", type=str)

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._settings.setValue("steam_api_key", value)

    @property
    def last_ini_path(self) -> str:
        return self._settings.value("last_ini_path", "", type=str)

    @last_ini_path.setter
    def last_ini_path(self, value: str) -> None:
        self._settings.setValue("last_ini_path", value)

    @property
    def recent_files(self) -> list[str]:
        val = self._settings.value("recent_files", [], type=list)
        return val if isinstance(val, list) else []

    @property
    def workshop_path(self) -> str:
        return self._settings.value("workshop_path", "", type=str)

    @workshop_path.setter
    def workshop_path(self, value: str) -> None:
        self._settings.setValue("workshop_path", value)

    def add_recent_file(self, path: str, max_items: int = 10) -> None:
        files = self.recent_files
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._settings.setValue("recent_files", files[:max_items])
