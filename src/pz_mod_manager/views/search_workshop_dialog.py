from __future__ import annotations

import re

import requests

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pz_mod_manager.models.mod import Mod
from pz_mod_manager.services.steam_api_service import SteamApiError, SteamApiService
from pz_mod_manager.services.workshop_scanner import extract_mod_id_from_description

# Known PZ workshop tags — used when the Steam tag API is unavailable.
_FALLBACK_TAGS = [
    "Build 42",
    "Build 41",
    "Map",
    "Clothing",
    "Weapons",
    "Items",
    "NPC",
    "Trait",
    "Occupation",
    "Vehicles",
    "Building",
    "Characters",
    "Skills",
    "Sounds",
    "Translations",
    "UI",
    "Utility",
    "Mechanics",
]

# BBCode tags that map directly to an HTML tag.
_BB_SIMPLE: list[tuple[str, str]] = [
    ("b", "b"),
    ("i", "i"),
    ("u", "u"),
    ("s", "s"),
    ("strike", "s"),
    ("h1", "h2"),
    ("h2", "h3"),
    ("h3", "h4"),
    ("code", "code"),
    ("table", "table"),
    ("tr", "tr"),
    ("th", "th"),
    ("td", "td"),
]



def _bbcode_to_html(text: str) -> str:
    """Convert Steam Workshop BBCode markup to HTML for display in QTextBrowser."""
    # Escape HTML entities first so literal < > & in descriptions survive.
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Simple open/close paired tags.
    for bb, html in _BB_SIMPLE:
        text = re.sub(rf"\[{bb}\]", f"<{html}>", text, flags=re.IGNORECASE)
        text = re.sub(rf"\[/{bb}\]", f"</{html}>", text, flags=re.IGNORECASE)

    # [url=link]label[/url]
    text = re.sub(
        r"\[url=([^\]]+)\](.*?)\[/url\]",
        r'<a href="\1">\2</a>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # [url]link[/url]
    text = re.sub(
        r"\[url\](.*?)\[/url\]",
        r'<a href="\1">\1</a>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # [img]url[/img] — show as a clickable placeholder rather than loading inline.
    text = re.sub(
        r"\[img\](.*?)\[/img\]",
        r'<a href="\1">[image]</a>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # [quote] / [quote=user]
    text = re.sub(r"\[quote=[^\]]+\]", "<blockquote>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[quote\]", "<blockquote>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/quote\]", "</blockquote>", text, flags=re.IGNORECASE)

    # Lists
    text = re.sub(r"\[list\]", "<ul>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/list\]", "</ul>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[olist\]", "<ol>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/olist\]", "</ol>", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\*\]", "<li>", text, flags=re.IGNORECASE)

    # [hr]
    text = re.sub(r"\[hr\]", "<hr>", text, flags=re.IGNORECASE)

    # [noparse]...[/noparse] — content is already HTML-escaped above; just unwrap.
    text = re.sub(
        r"\[noparse\](.*?)\[/noparse\]",
        r"\1",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # [spoiler]...[/spoiler]
    text = re.sub(
        r"\[spoiler\](.*?)\[/spoiler\]",
        r"<i>\1</i>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip any remaining unknown [tags].
    text = re.sub(r"\[/?[a-zA-Z][^\]]*\]", "", text)

    # Newlines → <br>.
    text = text.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")

    return text


class _FetchTagsWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api_service: SteamApiService):
        super().__init__()
        self._api_service = api_service

    def run(self):
        try:
            tags = self._api_service.fetch_tags()
            self.finished.emit(tags)
        except SteamApiError as e:
            self.error.emit(str(e))


class _SearchWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        api_service: SteamApiService,
        text: str,
        tags: list[str],
        page: int,
    ):
        super().__init__()
        self._api_service = api_service
        self._text = text
        self._tags = tags
        self._page = page

    def run(self):
        try:
            result = self._api_service.search_mods(
                text=self._text,
                tags=self._tags or None,
                page=self._page,
            )
            self.finished.emit(result)
        except SteamApiError as e:
            self.error.emit(str(e))


class _FetchImageWorker(QObject):
    finished = Signal(bytes)
    error = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, timeout=10)
            resp.raise_for_status()
            self.finished.emit(resp.content)
        except requests.RequestException as e:
            self.error.emit(str(e))


class SearchWorkshopDialog(QDialog):
    mod_selected = Signal(object)  # Mod

    def __init__(
        self,
        api_service: SteamApiService,
        ws_to_mods: dict[str, list[str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_service = api_service
        self._ws_to_mods = ws_to_mods or {}
        self._current_page = 1
        self._total_results = 0
        self._results: list[dict] = []
        self._selected_item: dict | None = None
        self._image_generation = 0

        self._worker: _FetchTagsWorker | None = None
        self._worker_thread: QThread | None = None
        self._search_worker: _SearchWorker | None = None
        self._search_thread: QThread | None = None
        self._image_worker: _FetchImageWorker | None = None
        self._image_thread: QThread | None = None
        # Old image threads are kept here until they finish to prevent
        # "Destroyed while thread is still running" crashes.
        self._old_image_threads: list[QThread] = []

        self.setWindowTitle("Search Steam Workshop")
        self.setMinimumSize(900, 650)
        self._setup_ui()
        self._fetch_tags()

    # ── UI Setup ──────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Search bar ---
        search_bar = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search Workshop...")
        self._search_edit.returnPressed.connect(self._on_search)
        self._tag_combo = QComboBox()
        self._tag_combo.setMinimumWidth(160)
        self._tag_combo.addItem("Any tag", userData=None)
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        search_bar.addWidget(self._search_edit, stretch=1)
        search_bar.addWidget(self._tag_combo)
        search_bar.addWidget(self._search_btn)
        layout.addLayout(search_bar)

        # --- Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: results list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._results_list = QListWidget()
        self._results_list.currentItemChanged.connect(self._on_result_selected)
        left_layout.addWidget(self._results_list)
        self._load_more_btn = QPushButton("Load More")
        self._load_more_btn.setVisible(False)
        self._load_more_btn.clicked.connect(self._on_load_more)
        left_layout.addWidget(self._load_more_btn)
        splitter.addWidget(left_widget)

        # Right: detail panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(6)

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(268, 151)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(
            "background: #252540; border: 1px solid #404060; border-radius: 3px;"
        )
        right_layout.addWidget(self._preview_label)

        self._title_label = QLabel("Select a result to see details")
        self._title_label.setWordWrap(True)
        right_layout.addWidget(self._title_label)

        self._tags_label = QLabel()
        self._tags_label.setWordWrap(True)
        self._tags_label.setObjectName("hintLabelItalic")
        right_layout.addWidget(self._tags_label)

        self._subs_label = QLabel()
        self._subs_label.setObjectName("hintLabel")
        right_layout.addWidget(self._subs_label)

        self._desc_browser = QTextBrowser()
        self._desc_browser.setOpenLinks(False)
        self._desc_browser.anchorClicked.connect(
            lambda url: QDesktopServices.openUrl(url)
        )
        right_layout.addWidget(self._desc_browser, stretch=1)

        self._mod_id_hint = QLabel()
        self._mod_id_hint.setWordWrap(True)
        self._mod_id_hint.setObjectName("hintLabel")
        self._mod_id_hint.setVisible(False)
        right_layout.addWidget(self._mod_id_hint)

        self._add_btn = QPushButton("Add to Mod List")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._on_add_mod)
        right_layout.addWidget(self._add_btn)

        splitter.addWidget(right_widget)
        splitter.setSizes([340, 540])
        layout.addWidget(splitter, stretch=1)

        # --- Bottom bar ---
        bottom_bar = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setObjectName("hintLabel")
        bottom_bar.addWidget(self._status_label, stretch=1)
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        bottom_bar.addWidget(close_box)
        layout.addLayout(bottom_bar)

    # ── Tag Fetching ──────────────────────────────────────────

    def _fetch_tags(self):
        self._tag_combo.setEnabled(False)
        self._worker = _FetchTagsWorker(self._api_service)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_tags_fetched)
        self._worker.error.connect(self._on_tags_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.start()

    def _on_tags_fetched(self, tags: list[str]):
        self._populate_tag_combo(tags if tags else _FALLBACK_TAGS)
        self._tag_combo.setEnabled(True)

    def _on_tags_error(self, msg: str):
        self._populate_tag_combo(_FALLBACK_TAGS)
        self._tag_combo.setEnabled(True)

    def _populate_tag_combo(self, tags: list[str]):
        for tag in tags:
            self._tag_combo.addItem(tag, userData=tag)

    # ── Search ────────────────────────────────────────────────

    def _on_search(self):
        text = self._search_edit.text().strip()
        if not text:
            return
        self._current_page = 1
        self._results.clear()
        self._results_list.clear()
        self._load_more_btn.setVisible(False)
        self._total_results = 0
        self._run_search(text, page=1)

    def _on_load_more(self):
        self._current_page += 1
        self._run_search(self._search_edit.text().strip(), page=self._current_page)

    def _run_search(self, text: str, page: int):
        self._search_btn.setEnabled(False)
        self._load_more_btn.setEnabled(False)
        self._status_label.setText("Searching...")

        selected_tag = self._tag_combo.currentData()
        tags = [selected_tag] if selected_tag else []

        self._search_worker = _SearchWorker(self._api_service, text, tags, page)
        self._search_thread = QThread()
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.finished.connect(self._search_thread.quit)
        self._search_worker.error.connect(self._search_thread.quit)
        self._search_thread.start()

    def _on_search_finished(self, result: dict):
        self._search_btn.setEnabled(True)
        self._load_more_btn.setEnabled(True)

        self._total_results = result["total"]
        new_items = result["results"]
        self._results.extend(new_items)

        for item in new_items:
            subs = item["subscriptions"]
            display = f"{item['title']}\n{subs:,} subscribers"
            list_item = QListWidgetItem(display)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self._results_list.addItem(list_item)

        loaded = len(self._results)
        self._status_label.setText(
            f"{loaded:,} of {self._total_results:,} results"
        )

        has_more = loaded < self._total_results
        self._load_more_btn.setVisible(has_more)

    def _on_search_error(self, msg: str):
        self._search_btn.setEnabled(True)
        self._load_more_btn.setEnabled(True)
        self._status_label.setText(f"Search failed: {msg}")

    # ── Result Selection ──────────────────────────────────────

    def _on_result_selected(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ):
        if current is None:
            self._selected_item = None
            self._clear_detail()
            self._update_add_button_state()
            return

        item = current.data(Qt.ItemDataRole.UserRole)
        self._selected_item = item

        self._title_label.setText(f"<b>{item['title']}</b>")
        tags_text = ", ".join(item.get("tags", [])) or "No tags"
        self._tags_label.setText(tags_text)
        subs = item.get("subscriptions", 0)
        self._subs_label.setText(f"{subs:,} subscribers")

        desc = (
            item.get("file_description")
            or item.get("short_description")
            or "(No description)"
        )
        self._desc_browser.setHtml(_bbcode_to_html(desc))

        preview_url = item.get("preview_url", "")
        self._preview_label.clear()
        self._preview_label.setText("Loading...")
        if preview_url:
            self._fetch_image_async(preview_url)
        else:
            self._preview_label.setText("No preview")

        self._update_add_button_state()

    def _clear_detail(self):
        self._title_label.setText("Select a result to see details")
        self._tags_label.clear()
        self._subs_label.clear()
        self._desc_browser.clear()
        self._preview_label.clear()
        self._mod_id_hint.setVisible(False)

    def _update_add_button_state(self):
        self._add_btn.setEnabled(self._selected_item is not None)

    # ── Image Fetching ────────────────────────────────────────

    def _fetch_image_async(self, url: str):
        self._image_generation += 1
        gen = self._image_generation

        # Retire the previous thread into the holding list so Python doesn't
        # GC it while it's still running.  It will remove itself when done.
        if self._image_thread is not None:
            old = self._image_thread
            if old.isRunning():
                self._old_image_threads.append(old)
                old.finished.connect(
                    lambda t=old: self._old_image_threads.remove(t)
                    if t in self._old_image_threads
                    else None
                )

        self._image_worker = _FetchImageWorker(url)
        self._image_thread = QThread()
        self._image_worker.moveToThread(self._image_thread)
        self._image_thread.started.connect(self._image_worker.run)
        self._image_worker.finished.connect(
            lambda data, g=gen: self._on_image_fetched(data, g)
        )
        self._image_worker.error.connect(
            lambda _, g=gen: self._on_image_error(g)
        )
        self._image_worker.finished.connect(self._image_thread.quit)
        self._image_worker.error.connect(self._image_thread.quit)
        self._image_thread.start()

    def _on_image_fetched(self, data: bytes, generation: int):
        if generation != self._image_generation:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                self._preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)
        else:
            self._preview_label.setText("No preview")

    def _on_image_error(self, generation: int):
        if generation != self._image_generation:
            return
        self._preview_label.setText("No preview")

    # ── Add Mod ───────────────────────────────────────────────

    def _on_add_mod(self):
        if not self._selected_item:
            return

        workshop_id = self._selected_item["publishedfileid"]

        # 1. Try local workshop scan (most reliable).
        local_ids = self._ws_to_mods.get(workshop_id, [])
        mod_id = local_ids[0] if local_ids else ""
        hint_source = "local"

        # 2. Fall back to parsing the description.
        if not mod_id:
            raw_desc = (
                self._selected_item.get("file_description", "")
                or self._selected_item.get("short_description", "")
            )
            mod_id = extract_mod_id_from_description(raw_desc) or ""
            hint_source = "description" if mod_id else "none"

        mod = Mod(
            mod_id=mod_id,
            workshop_id=workshop_id,
            name=self._selected_item.get("title", ""),
            enabled=True,
        )
        self.mod_selected.emit(mod)

        if hint_source == "local":
            self._mod_id_hint.setText(f"Mod ID auto-filled from local files: {mod_id}")
        elif hint_source == "description":
            self._mod_id_hint.setText(
                f"Mod ID extracted from description: {mod_id} — verify it's correct."
            )
        else:
            self._mod_id_hint.setText(
                "Mod ID is blank — double-click the Mod ID cell in the table to "
                "fill it in from the mod's mod.info file."
            )
        self._mod_id_hint.setVisible(True)
        self._add_btn.setText("Added!")
        self._add_btn.setEnabled(False)
        QTimer.singleShot(1500, self._reset_add_button)

    def _reset_add_button(self):
        self._add_btn.setText("Add to Mod List")
        self._update_add_button_state()

    # ── Cleanup ───────────────────────────────────────────────

    def closeEvent(self, event):
        threads = [
            self._worker_thread,
            self._search_thread,
            self._image_thread,
            *self._old_image_threads,
        ]
        for thread in threads:
            if thread and thread.isRunning():
                thread.quit()
                thread.wait()
        super().closeEvent(event)
