from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt, QThread, Signal, QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pz_mod_manager.models.mod import Mod
from pz_mod_manager.models.mod_list_model import ModListModel
from pz_mod_manager.services.ini_service import IniService
from pz_mod_manager.services.settings_service import SettingsService
from pz_mod_manager.services.steam_api_service import SteamApiError, SteamApiService
from pz_mod_manager.services.workshop_scanner import (
    scan_workshop_content,
    build_mod_id_to_workshop_map,
    build_workshop_to_mod_ids_map,
)
from pz_mod_manager.utils.constants import COLUMN_WORKSHOP_ID


class _FetchNamesWorker(QObject):
    finished = Signal(list)  # list of dicts from Steam API
    error = Signal(str)

    def __init__(self, api_service: SteamApiService, workshop_ids: list[str]):
        super().__init__()
        self._api_service = api_service
        self._workshop_ids = workshop_ids

    def run(self):
        try:
            results = self._api_service.fetch_mod_details(self._workshop_ids)
            self.finished.emit(results)
        except SteamApiError as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PZ Mod Manager")
        self.resize(900, 600)

        self._ini_service = IniService()
        self._settings = SettingsService()
        self._current_file: str | None = None
        self._dirty = False
        self._worker_thread: QThread | None = None

        self._model = ModListModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search all columns

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_connections()
        self._update_status()

        # Auto-open last INI if it still exists
        last = self._settings.last_ini_path
        if last and Path(last).is_file():
            self._load_file(last)

    # ── UI Setup ──────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter mods by name, mod ID, or workshop ID...")
        self._search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)

        # Table
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 85)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        # Status bar
        self._status_file = QLabel("No file loaded")
        self._status_count = QLabel("")
        self.statusBar().addWidget(self._status_file, 1)
        self.statusBar().addPermanentWidget(self._status_count)

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        self._act_open = file_menu.addAction("&Open INI...")
        self._act_open.setShortcut(QKeySequence.StandardKey.Open)
        self._act_save = file_menu.addAction("&Save")
        self._act_save.setShortcut(QKeySequence.StandardKey.Save)
        self._act_save_as = file_menu.addAction("Save &As...")
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        self._act_close = file_menu.addAction("&Close INI")
        self._act_close.setShortcut(QKeySequence("Ctrl+W"))
        file_menu.addSeparator()
        self._act_exit = file_menu.addAction("E&xit")
        self._act_exit.setShortcut(QKeySequence.StandardKey.Quit)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        self._act_add = edit_menu.addAction("&Add Mod...")
        self._act_add.setShortcut(QKeySequence("Ctrl+N"))
        self._act_search_workshop = edit_menu.addAction("&Search Workshop...")
        self._act_search_workshop.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self._act_search_workshop.setEnabled(bool(self._settings.api_key))
        if not self._settings.api_key:
            self._act_search_workshop.setToolTip(
                "Set a Steam API key in Settings to enable Workshop search"
            )
        self._act_remove = edit_menu.addAction("&Remove Selected")
        self._act_remove.setShortcut(QKeySequence.StandardKey.Delete)
        edit_menu.addSeparator()
        self._act_enable_all = edit_menu.addAction("&Enable All")
        self._act_disable_all = edit_menu.addAction("&Disable All")
        edit_menu.addSeparator()
        copy_menu = edit_menu.addMenu("Copy for &Docker")
        self._act_copy_docker_mods = copy_menu.addAction("Copy Mod IDs")
        self._act_copy_docker_workshop = copy_menu.addAction("Copy Workshop IDs")
        edit_menu.addSeparator()
        self._act_server_settings = edit_menu.addAction("Server Se&ttings...")
        self._act_server_settings.setEnabled(False)
        edit_menu.addSeparator()
        self._act_settings = edit_menu.addAction("App S&ettings...")

        # Help menu
        help_menu = menubar.addMenu("&Help")
        self._act_about = help_menu.addAction("&About")

    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(self._act_open)
        toolbar.addAction(self._act_save)
        toolbar.addSeparator()
        toolbar.addAction(self._act_add)
        toolbar.addAction(self._act_remove)
        toolbar.addSeparator()
        self._act_scan = toolbar.addAction("Scan Workshop")
        toolbar.addAction(self._act_search_workshop)
        self._act_refresh = toolbar.addAction("Refresh Names")

    def _setup_connections(self):
        self._search_edit.textChanged.connect(self._proxy.setFilterFixedString)
        self._act_open.triggered.connect(self._on_open)
        self._act_save.triggered.connect(self._on_save)
        self._act_save_as.triggered.connect(self._on_save_as)
        self._act_close.triggered.connect(self._on_close)
        self._act_exit.triggered.connect(self.close)
        self._act_add.triggered.connect(self._on_add_mod)
        self._act_remove.triggered.connect(self._on_remove_selected)
        self._act_enable_all.triggered.connect(self._on_enable_all)
        self._act_disable_all.triggered.connect(self._on_disable_all)
        self._act_copy_docker_mods.triggered.connect(self._on_copy_docker_mods)
        self._act_copy_docker_workshop.triggered.connect(self._on_copy_docker_workshop)
        self._act_server_settings.triggered.connect(self._on_server_settings)
        self._act_settings.triggered.connect(self._on_settings)
        self._act_scan.triggered.connect(self._on_scan_workshop)
        self._act_search_workshop.triggered.connect(self._on_search_workshop)
        self._act_refresh.triggered.connect(self._on_refresh_names)
        self._act_about.triggered.connect(self._on_about)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._model.dataChanged.connect(self._on_data_changed)
        self._model.rowsInserted.connect(self._on_data_changed)
        self._model.rowsRemoved.connect(self._on_data_changed)

    # ── File Operations ───────────────────────────────────────

    def _on_open(self):
        if not self._check_unsaved():
            return
        start_dir = self._settings.last_ini_path or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Server INI", start_dir, "INI Files (*.ini);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            mod_ids, workshop_ids = self._ini_service.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
            return

        # Load disabled mods from sidecar
        disabled_mods = self._load_sidecar(path)

        # Try to resolve correct pairings via workshop scanner
        mod_to_ws = self._get_workshop_mapping()

        mods: list[Mod] = []
        if mod_to_ws:
            # Scanner available - use it for correct pairings
            ws_to_mods = build_workshop_to_mod_ids_map(
                scan_workshop_content(Path(self._settings.workshop_path))
            )
            for mid in mod_ids:
                # Try exact match, then try with backslash escapes removed
                # (PZ INI sometimes escapes & as \&)
                wid = mod_to_ws.get(mid, "")
                if not wid:
                    clean_mid = mid.replace("\\", "")
                    wid = mod_to_ws.get(clean_mid, "")
                mods.append(Mod(mod_id=mid, workshop_id=wid, enabled=True))
            # Add any workshop IDs not accounted for by the mods
            # (e.g. library/dependency workshop items, or mods not in the Mods= list)
            used_ws = {m.workshop_id for m in mods if m.workshop_id}
            for wid in workshop_ids:
                if wid and wid not in used_ws:
                    # Look up what mod(s) this workshop item provides
                    known_mods = ws_to_mods.get(wid, [])
                    if known_mods:
                        for km_id in known_mods:
                            mods.append(Mod(mod_id=km_id, workshop_id=wid, enabled=True))
                    else:
                        mods.append(Mod(mod_id="", workshop_id=wid, enabled=True))
        else:
            # No scanner - fall back to positional pairing with warning
            if mod_ids and workshop_ids and len(mod_ids) != len(workshop_ids):
                QMessageBox.warning(
                    self,
                    "Mismatched Lists",
                    f"The Mods= list has {len(mod_ids)} entries but "
                    f"WorkshopItems= has {len(workshop_ids)} entries.\n\n"
                    "In Project Zomboid, these are independent lists. "
                    "The Workshop IDs shown may not correspond to the correct mods.\n\n"
                    "Set your Workshop Path in Settings and click 'Scan Workshop' "
                    "to auto-resolve the correct pairings.",
                )
            max_len = max(len(mod_ids), len(workshop_ids), 1) if mod_ids or workshop_ids else 0
            for i in range(max_len):
                mods.append(
                    Mod(
                        mod_id=mod_ids[i] if i < len(mod_ids) else "",
                        workshop_id=workshop_ids[i] if i < len(workshop_ids) else "",
                        enabled=True,
                    )
                )

        # Re-add disabled mods
        for dm in disabled_mods:
            mods.append(
                Mod(
                    mod_id=dm.get("mod_id", ""),
                    workshop_id=dm.get("workshop_id", ""),
                    name=dm.get("name", ""),
                    enabled=False,
                )
            )

        self._model.set_mods(mods)
        self._current_file = path
        self._dirty = False
        self._settings.last_ini_path = path
        self._settings.add_recent_file(path)
        self._act_server_settings.setEnabled(True)
        self._update_status()

        # Auto-fetch names if API key is set
        if self._settings.api_key:
            self._fetch_names_async()

    def _on_save(self):
        if self._current_file:
            self._save_file(self._current_file)
        else:
            self._on_save_as()

    def _on_save_as(self):
        start_dir = self._current_file or ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Server INI", start_dir, "INI Files (*.ini);;All Files (*)"
        )
        if path:
            self._save_file(path)

    def _on_close(self):
        if not self._check_unsaved():
            return
        self._model.set_mods([])
        self._current_file = None
        self._dirty = False
        self._settings.last_ini_path = ""
        self._act_server_settings.setEnabled(False)
        self._update_status()

    def _save_file(self, path: str):
        enabled = self._model.enabled_mods()
        mod_ids = [m.mod_id for m in enabled if m.mod_id]
        # Workshop IDs are an independent list - deduplicate and filter empties
        # (a single workshop item can provide multiple mods)
        workshop_ids = list(dict.fromkeys(
            m.workshop_id for m in enabled if m.workshop_id
        ))

        try:
            # If file doesn't exist yet (Save As to new location), create minimal content
            if not Path(path).exists():
                Path(path).write_text("Mods=\nWorkshopItems=\n", encoding="utf-8")
            self._ini_service.save(path, mod_ids, workshop_ids)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
            return

        # Save disabled mods to sidecar
        self._save_sidecar(path)

        self._current_file = path
        self._dirty = False
        self._settings.last_ini_path = path
        self._settings.add_recent_file(path)
        self._update_status()
        self.statusBar().showMessage("Saved successfully", 3000)

    # ── Sidecar JSON ──────────────────────────────────────────

    def _sidecar_path(self, ini_path: str) -> Path:
        return Path(ini_path).parent / ".pz_mod_manager.json"

    def _load_sidecar(self, ini_path: str) -> list[dict]:
        sp = self._sidecar_path(ini_path)
        if sp.exists():
            try:
                data = json.loads(sp.read_text(encoding="utf-8"))
                return data.get("disabled_mods", [])
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def _save_sidecar(self, ini_path: str):
        disabled = [
            {"mod_id": m.mod_id, "workshop_id": m.workshop_id, "name": m.name}
            for m in self._model.mods
            if not m.enabled
        ]
        sp = self._sidecar_path(ini_path)
        if disabled:
            sp.write_text(
                json.dumps({"disabled_mods": disabled}, indent=2),
                encoding="utf-8",
            )
        elif sp.exists():
            sp.unlink()

    # ── Mod Operations ────────────────────────────────────────

    def _on_add_mod(self):
        from pz_mod_manager.views.add_mod_dialog import AddModDialog

        api_service = None
        if self._settings.api_key:
            api_service = SteamApiService(self._settings.api_key)

        dialog = AddModDialog(api_service, self)
        if dialog.exec():
            mod = dialog.get_mod()
            if mod:
                self._model.add_mod(mod)

    def _on_remove_selected(self):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        # Map proxy indexes back to source
        source_rows = sorted(
            {self._proxy.mapToSource(idx).row() for idx in indexes},
            reverse=True,
        )
        self._model.remove_rows(source_rows)

    def _on_enable_all(self):
        mods = self._model.mods
        for mod in mods:
            mod.enabled = True
        self._model.set_mods(mods)
        self._dirty = True
        self._update_status()

    def _on_disable_all(self):
        mods = self._model.mods
        for mod in mods:
            mod.enabled = False
        self._model.set_mods(mods)
        self._dirty = True
        self._update_status()

    # ── Docker Copy ─────────────────────────────────────────────

    @staticmethod
    def _escape_docker_mod_id(mod_id: str) -> str:
        """Escape a mod ID for Docker env vars.

        Double backslash prefix (``\\\\ModA``) so Docker produces ``\\ModA``
        in the container.  Special characters like ``&`` are escaped with a
        single backslash.
        """
        # Escape special chars that need a backslash in env strings
        escaped = mod_id.replace("&", "\\&")
        return f"\\\\{escaped}"

    def _on_copy_docker_mods(self):
        enabled = self._model.enabled_mods()
        mod_ids = [self._escape_docker_mod_id(m.mod_id) for m in enabled if m.mod_id]
        text = ";".join(mod_ids)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied {len(mod_ids)} mod IDs for Docker", 3000)

    def _on_copy_docker_workshop(self):
        enabled = self._model.enabled_mods()
        workshop_ids = list(dict.fromkeys(
            m.workshop_id for m in enabled if m.workshop_id
        ))
        text = ";".join(workshop_ids)
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied {len(workshop_ids)} workshop IDs for Docker", 3000)

    # ── Workshop Scanner ───────────────────────────────────────

    def _get_workshop_mapping(self) -> dict[str, str]:
        """Return mod_id -> workshop_id mapping from scanner, or empty dict."""
        ws_path = self._settings.workshop_path
        if not ws_path:
            return {}
        results = scan_workshop_content(Path(ws_path))
        if not results:
            return {}
        return build_mod_id_to_workshop_map(results)

    def _on_scan_workshop(self):
        ws_path = self._settings.workshop_path
        if not ws_path:
            QMessageBox.information(
                self,
                "Workshop Path Required",
                "Set your Workshop Path in Edit > Settings first.\n\n"
                "This should point to the Steam workshop directory where "
                "PZ mod files are downloaded (e.g. /path/to/workshop-mods/).",
            )
            return

        results = scan_workshop_content(Path(ws_path))
        if not results:
            QMessageBox.warning(
                self,
                "No Mods Found",
                f"No mod.info files found under:\n{ws_path}\n\n"
                "Make sure the path points to the Steam workshop directory.",
            )
            return

        mod_to_ws = build_mod_id_to_workshop_map(results)
        ws_to_mods = build_workshop_to_mod_ids_map(results)

        # Update workshop IDs and names for existing mods in the model
        mods = self._model.mods
        updated = 0
        for mod in mods:
            if mod.mod_id and mod.mod_id in mod_to_ws:
                info = next(r for r in results if r.mod_id == mod.mod_id)
                if mod.workshop_id != info.workshop_id or not mod.name:
                    mod.workshop_id = info.workshop_id
                    if info.name:
                        mod.name = info.name
                    updated += 1

        self._model.set_mods(mods)
        self._dirty = True
        self._update_status()

        self.statusBar().showMessage(
            f"Scanned {len(results)} mods from workshop, updated {updated} pairings",
            5000,
        )

    # ── Steam API ─────────────────────────────────────────────

    def _on_refresh_names(self):
        if not self._settings.api_key:
            QMessageBox.information(
                self,
                "API Key Required",
                "Set your Steam API key in Edit > Settings to fetch mod names.",
            )
            return
        self._fetch_names_async()

    def _fetch_names_async(self):
        workshop_ids = list({m.workshop_id for m in self._model.mods if m.workshop_id})
        if not workshop_ids:
            return

        api_service = SteamApiService(self._settings.api_key)
        self._worker = _FetchNamesWorker(api_service, workshop_ids)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_names_fetched)
        self._worker.error.connect(self._on_names_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)

        self.statusBar().showMessage("Fetching mod names from Steam...")
        self._worker_thread.start()

    def _on_names_fetched(self, results: list[dict]):
        was_dirty = self._dirty
        for item in results:
            wid = item.get("publishedfileid", "")
            title = item.get("title", "")
            if wid and title:
                self._model.update_mod_name(wid, title)
        self._dirty = was_dirty
        self._update_status()
        self.statusBar().showMessage(f"Updated {len(results)} mod name(s)", 3000)

    def _on_names_error(self, msg: str):
        self.statusBar().showMessage(f"Failed to fetch names: {msg}", 5000)

    # ── Server Settings ───────────────────────────────────────

    def _on_server_settings(self):
        if not self._current_file:
            return
        from pz_mod_manager.views.server_settings_dialog import ServerSettingsDialog

        dialog = ServerSettingsDialog(self._ini_service, self._current_file, self)
        if dialog.exec():
            self.statusBar().showMessage("Server settings saved", 3000)

    def _on_search_workshop(self):
        from pz_mod_manager.views.search_workshop_dialog import SearchWorkshopDialog

        api_service = SteamApiService(self._settings.api_key)
        dialog = SearchWorkshopDialog(api_service, self)
        dialog.mod_selected.connect(self._on_mod_from_search)
        dialog.exec()

    def _on_mod_from_search(self, mod: Mod):
        self._model.add_mod(mod)
        self.statusBar().showMessage(
            f"Added mod: {mod.name or mod.mod_id}", 3000
        )

    # ── Settings / About ──────────────────────────────────────

    def _on_settings(self):
        from pz_mod_manager.views.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self._settings, self)
        dialog.exec()

        has_key = bool(self._settings.api_key)
        self._act_search_workshop.setEnabled(has_key)
        self._act_search_workshop.setToolTip(
            "" if has_key else "Set a Steam API key in Settings to enable Workshop search"
        )

    def _on_about(self):
        version = QApplication.applicationVersion() or "dev"
        QMessageBox.about(
            self,
            "About PZ Mod Manager",
            f"PZ Mod Manager v{version}\n\n"
            "A tool for managing Project Zomboid server mod IDs.\n\n"
            "Load a servertest.ini file to get started.",
        )

    # ── Context Menu ──────────────────────────────────────────

    def _on_context_menu(self, pos):
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        act_enable = menu.addAction("Enable")
        act_disable = menu.addAction("Disable")
        menu.addSeparator()
        act_remove = menu.addAction("Remove")
        menu.addSeparator()
        act_open_ws = menu.addAction("Open in Steam Workshop")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action is None:
            return

        source_idx = self._proxy.mapToSource(index)
        row = source_idx.row()
        mods = self._model.mods
        mod = mods[row]

        if action == act_enable:
            mod.enabled = True
            self._model.set_mods(mods)
            self._dirty = True
        elif action == act_disable:
            mod.enabled = False
            self._model.set_mods(mods)
            self._dirty = True
        elif action == act_remove:
            self._model.remove_rows([row])
        elif action == act_open_ws and mod.workshop_id:
            webbrowser.open(
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod.workshop_id}"
            )

        self._update_status()

    # ── Helpers ────────────────────────────────────────────────

    def _on_data_changed(self):
        self._dirty = True
        self._update_status()

    def _update_status(self):
        if self._current_file:
            marker = " *" if self._dirty else ""
            self._status_file.setText(f"{self._current_file}{marker}")
            self.setWindowTitle(f"PZ Mod Manager - {Path(self._current_file).name}{marker}")
        else:
            self._status_file.setText("No file loaded")
            self.setWindowTitle("PZ Mod Manager")

        all_mods = self._model.mods
        enabled = sum(1 for m in all_mods if m.enabled)
        self._status_count.setText(f"{len(all_mods)} mods ({enabled} enabled)")

    def _check_unsaved(self) -> bool:
        """Returns True if it's OK to proceed (no unsaved changes or user chose to discard)."""
        if not self._dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Do you want to discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        if self._check_unsaved():
            event.accept()
        else:
            event.ignore()
