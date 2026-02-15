from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, QAbstractTableModel

from pz_mod_manager.models.mod import Mod
from pz_mod_manager.utils.constants import (
    COLUMN_ENABLED,
    COLUMN_HEADERS,
    COLUMN_MOD_ID,
    COLUMN_NAME,
    COLUMN_WORKSHOP_ID,
)


class ModListModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mods: list[Mod] = []

    @property
    def mods(self) -> list[Mod]:
        return list(self._mods)

    def set_mods(self, mods: list[Mod]) -> None:
        self.beginResetModel()
        self._mods = list(mods)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._mods)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMN_HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._mods):
            return None

        mod = self._mods[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COLUMN_MOD_ID:
                return mod.mod_id
            if col == COLUMN_WORKSHOP_ID:
                return mod.workshop_id
            if col == COLUMN_NAME:
                return mod.name
            return None

        if role == Qt.ItemDataRole.CheckStateRole and col == COLUMN_ENABLED:
            return Qt.CheckState.Checked if mod.enabled else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.EditRole and col == COLUMN_MOD_ID:
            return mod.mod_id

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.row() >= len(self._mods):
            return False

        mod = self._mods[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.CheckStateRole and col == COLUMN_ENABLED:
            mod.enabled = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role])
            return True

        if role == Qt.ItemDataRole.EditRole and col == COLUMN_MOD_ID:
            mod.mod_id = str(value)
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if not index.isValid():
            return base

        col = index.column()
        if col == COLUMN_ENABLED:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        if col == COLUMN_MOD_ID:
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(COLUMN_HEADERS):
                return COLUMN_HEADERS[section]
        return None

    def add_mod(self, mod: Mod) -> None:
        row = len(self._mods)
        self.beginInsertRows(QModelIndex(), row, row)
        self._mods.append(mod)
        self.endInsertRows()

    def remove_rows(self, rows: list[int]) -> None:
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self._mods):
                self.beginRemoveRows(QModelIndex(), row, row)
                self._mods.pop(row)
                self.endRemoveRows()

    def move_up(self, row: int) -> bool:
        if row <= 0 or row >= len(self._mods):
            return False
        self.beginMoveRows(QModelIndex(), row, row, QModelIndex(), row - 1)
        self._mods[row], self._mods[row - 1] = self._mods[row - 1], self._mods[row]
        self.endMoveRows()
        return True

    def move_down(self, row: int) -> bool:
        if row < 0 or row >= len(self._mods) - 1:
            return False
        self.beginMoveRows(QModelIndex(), row, row, QModelIndex(), row + 2)
        self._mods[row], self._mods[row + 1] = self._mods[row + 1], self._mods[row]
        self.endMoveRows()
        return True

    def enabled_mods(self) -> list[Mod]:
        return [m for m in self._mods if m.enabled]

    def update_mod_name(self, workshop_id: str, name: str) -> None:
        """Update the name for all mods with the given workshop_id."""
        for row, mod in enumerate(self._mods):
            if mod.workshop_id == workshop_id:
                mod.name = name
                idx = self.index(row, COLUMN_NAME)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
