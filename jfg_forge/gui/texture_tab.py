"""The "Textures" tab: the ROM's texture bank with derived names, preview and PNG export."""

from __future__ import annotations

import re
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from jfg_forge.core.rom_source import RomSource
from jfg_forge.core.texture_bank import (
    TextureEntry,
    apply_usage,
    decode_texture_entry,
    find_usage,
    list_textures,
)
from jfg_forge.core.texture_rgba16 import encode_png_rgba

BANK_ALL = "Both banks"
SHOW_ALL = "All textures"
SHOW_DECODED = "Decoded only"
SHOW_UNDECODED = "Not decoded"
SHOW_USED = "Used by a model or level"
SHOW_UNUSED = "Unused"
SORT_NUMBER = "Bank and number"
SORT_NAME = "Name"
SORT_SIZE = "Size (largest first)"


def filter_textures(
    entries: tuple[TextureEntry, ...],
    *,
    text: str = "",
    bank: str = BANK_ALL,
    show: str = SHOW_ALL,
    sort: str = SORT_NUMBER,
) -> list[TextureEntry]:
    """Apply the tab's filters and sort order (Qt-free, testable)."""
    chosen = list(entries)
    if bank in ("A", "B"):
        chosen = [entry for entry in chosen if entry.bank == bank]
    if show == SHOW_DECODED:
        chosen = [entry for entry in chosen if entry.decodable]
    elif show == SHOW_UNDECODED:
        chosen = [entry for entry in chosen if not entry.decodable]
    elif show == SHOW_USED:
        chosen = [entry for entry in chosen if entry.used_by]
    elif show == SHOW_UNUSED:
        chosen = [entry for entry in chosen if not entry.used_by]
    needle = text.strip().lower()
    if needle:
        chosen = [
            entry
            for entry in chosen
            if needle in entry.title.lower()
            or needle in f"{entry.bank}{entry.index}".lower()
            or any(needle in user.lower() for user in entry.used_by)
        ]
    keys = {
        SORT_NAME: lambda entry: (entry.title.lower(), entry.bank, entry.index),
        SORT_SIZE: lambda entry: (-entry.width * entry.height, entry.bank, entry.index),
    }
    return sorted(chosen, key=keys.get(sort, lambda entry: (entry.bank, entry.index)))


def safe_file_stem(entry: TextureEntry) -> str:
    label = re.sub(r"[^A-Za-z0-9]+", "_", entry.title.split("·")[0]).strip("_") or "texture"
    return f"{entry.bank}{entry.index:04d}_{label[:40]}"


class TextureTab(QWidget):
    status_message = Signal(str)

    def __init__(self, source: RomSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._entries: tuple[TextureEntry, ...] = ()
        self._current: TextureEntry | None = None
        self._current_rgba: tuple[int, int, bytes] | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._usage_job: Future | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._poll_usage)
        self.loaded = False

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_side_panel())
        splitter.addWidget(self._build_view())
        splitter.setSizes([340, 840])
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # ------------------------------------------------------------------ UI
    def _build_side_panel(self) -> QWidget:
        panel = QFrame()
        panel.setMinimumWidth(260)
        layout = QVBoxLayout(panel)
        heading = QLabel("Texture bank")
        heading.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(heading)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name, number (A12) or user")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        form = QFormLayout()
        self.bank_combo = QComboBox()
        for label, value in ((BANK_ALL, BANK_ALL), ("Bank A (levels and models)", "A"), ("Bank B (models)", "B")):
            self.bank_combo.addItem(label, value)
        self.show_combo = QComboBox()
        for label in (SHOW_ALL, SHOW_DECODED, SHOW_UNDECODED, SHOW_USED, SHOW_UNUSED):
            self.show_combo.addItem(label, label)
        self.sort_combo = QComboBox()
        for label in (SORT_NUMBER, SORT_NAME, SORT_SIZE):
            self.sort_combo.addItem(label, label)
        form.addRow("Bank", self.bank_combo)
        form.addRow("Show", self.show_combo)
        form.addRow("Sort by", self.sort_combo)
        layout.addLayout(form)
        self.count_label = QLabel("Loading the texture bank...")
        layout.addWidget(self.count_label)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, stretch=1)

        info = QFormLayout()
        self.name_value = QLabel("-")
        self.name_value.setWordWrap(True)
        self.id_value = QLabel("-")
        self.size_value = QLabel("-")
        self.format_value = QLabel("-")
        self.format_value.setWordWrap(True)
        self.used_value = QLabel("-")
        self.used_value.setWordWrap(True)
        self.offset_value = QLabel("-")
        for label, widget in (
            ("Name (derived)", self.name_value),
            ("Texture", self.id_value),
            ("Size", self.size_value),
            ("Format", self.format_value),
            ("Used by", self.used_value),
            ("ROM offset", self.offset_value),
        ):
            info.addRow(label, widget)
        layout.addLayout(info)
        note = QLabel("The ROM stores no texture names. Names are derived from the first model or level that uses the texture.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.search_edit.textChanged.connect(self._refresh_list)
        for combo in (self.bank_combo, self.show_combo, self.sort_combo):
            combo.currentIndexChanged.connect(self._refresh_list)
        self.list_widget.currentItemChanged.connect(self._select_item)
        return panel

    def _build_view(self) -> QWidget:
        area = QFrame()
        layout = QVBoxLayout(area)
        self.image_label = QLabel("Select a texture from the list.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_label)
        layout.addWidget(scroll, stretch=1)

        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_row = QWidget()
        frame_form = QFormLayout(self.frame_row)
        frame_form.setContentsMargins(0, 0, 0, 0)
        self.frame_spin = QSpinBox()
        frame_form.addRow("Frame", self.frame_spin)
        row_layout.addWidget(self.frame_row)
        self.export_button = QPushButton("Export PNG...")
        self.export_all_button = QPushButton("Export shown list as PNG files...")
        row_layout.addWidget(self.export_button)
        row_layout.addWidget(self.export_all_button)
        layout.addWidget(row)
        self.frame_row.hide()
        self.export_button.setEnabled(False)
        self.export_all_button.setEnabled(False)

        self.frame_spin.valueChanged.connect(self._frame_changed)
        self.export_button.clicked.connect(self._export_current)
        self.export_all_button.clicked.connect(self._export_shown)
        return area

    # ------------------------------------------------------------------ loading
    def ensure_loaded(self) -> None:
        if self.loaded:
            return
        self.loaded = True
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._entries = list_textures(self._source)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._refresh_list()
        self.export_all_button.setEnabled(True)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._usage_job = self._executor.submit(find_usage, self._source)
        self._timer.start()
        self.status_message.emit("Textures — finding which models and levels use each texture...")
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _poll_usage(self) -> None:
        job = self._usage_job
        if job is None or not job.done():
            return
        self._timer.stop()
        self._usage_job = None
        try:
            self._entries = apply_usage(self._entries, job.result())
        except Exception as error:  # names stay generic; the bank is still usable
            self.status_message.emit(f"Textures — could not derive names: {error}")
            return
        keep = None if self._current is None else self._current.key
        self._current = next((entry for entry in self._entries if entry.key == keep), None)
        self._refresh_list()
        if self._current is not None:
            self._set_info(self._current)
        self.status_message.emit(f"Textures — {len(self._entries):,} textures with derived names")

    def close_workers(self) -> None:
        self._timer.stop()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ list
    def shown(self) -> list[TextureEntry]:
        return filter_textures(
            self._entries,
            text=self.search_edit.text(),
            bank=str(self.bank_combo.currentData()),
            show=str(self.show_combo.currentData()),
            sort=str(self.sort_combo.currentData()),
        )

    def _refresh_list(self, *_args: object) -> None:
        keep = None if self._current is None else self._current.key
        rows = self.shown()
        self.list_widget.blockSignals(True)
        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.clear()
        selected_row = -1
        for row, entry in enumerate(rows):
            marker = "" if entry.decodable else "   [not decoded]"
            item = QListWidgetItem(f"{entry.bank}{entry.index}  {entry.title}{marker}")
            item.setData(Qt.ItemDataRole.UserRole, (entry.bank, entry.index))
            self.list_widget.addItem(item)
            if entry.key == keep:
                selected_row = row
        if selected_row >= 0:
            self.list_widget.setCurrentRow(selected_row)
        self.list_widget.setUpdatesEnabled(True)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(rows):,} of {len(self._entries):,} textures")

    def _select_item(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if item is None:
            return
        key = tuple(item.data(Qt.ItemDataRole.UserRole))
        entry = next((candidate for candidate in self._entries if candidate.key == key), None)
        if entry is not None:
            self.show_texture(entry)

    # ------------------------------------------------------------------ view
    def show_texture(self, entry: TextureEntry) -> None:
        self._current = entry
        self._set_info(entry)
        self.frame_spin.blockSignals(True)
        self.frame_spin.setValue(0)
        self.frame_spin.blockSignals(False)
        self._draw(entry, 0)

    def _draw(self, entry: TextureEntry, frame: int) -> None:
        try:
            decoded = decode_texture_entry(self._source, entry, frame)
        except Exception as error:
            self._current_rgba = None
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(f"{entry.title} cannot be shown: {error}")
            self.frame_row.hide()
            self.export_button.setEnabled(False)
            self.status_message.emit(f"Textures / {entry.bank}{entry.index} — {entry.format_name}, not decoded")
            return
        width, height = decoded.header.width, decoded.header.height
        self._current_rgba = (width, height, decoded.rgba)
        image = QImage(decoded.rgba, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
        zoom = max(1, min(16, 384 // max(width, height)))
        pixmap = QPixmap.fromImage(image).scaled(
            width * zoom, height * zoom, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        self.image_label.setText("")
        self.image_label.setPixmap(pixmap)
        self.frame_spin.blockSignals(True)
        self.frame_spin.setRange(0, max(decoded.frame_count - 1, 0))
        self.frame_spin.blockSignals(False)
        self.frame_row.setVisible(decoded.frame_count > 1)
        self.export_button.setEnabled(True)
        extra = f", {decoded.frame_count} frames" if decoded.frame_count > 1 else ""
        self.status_message.emit(
            f"Textures / {entry.bank}{entry.index} — {entry.title} — {decoded.format_name}{extra}"
        )

    def _frame_changed(self, frame: int) -> None:
        if self._current is not None:
            self._draw(self._current, frame)

    def _set_info(self, entry: TextureEntry) -> None:
        self.name_value.setText(entry.title)
        self.id_value.setText(f"Bank {entry.bank}, number {entry.index}")
        self.size_value.setText(f"{entry.width} × {entry.height}")
        self.format_value.setText(
            entry.format_name if entry.decodable else f"{entry.format_name} (not decoded yet)"
        )
        users = ", ".join(user.replace("model ", "model ").replace("level ", "level ") for user in entry.used_by[:8])
        if len(entry.used_by) > 8:
            users += f" (+{len(entry.used_by) - 8} more)"
        self.used_value.setText(users or ("-" if self._usage_job is None else "still searching..."))
        self.offset_value.setText(f"0x{entry.rom_offset - 32:X}")

    # ------------------------------------------------------------------ export
    def _export_current(self) -> None:
        if self._current is None or self._current_rgba is None:
            return
        entry = self._current
        path, _ = QFileDialog.getSaveFileName(
            self, "Export texture", f"{safe_file_stem(entry)}.png", "PNG image (*.png)"
        )
        if not path:
            return
        width, height, rgba = self._current_rgba
        try:
            Path(path).write_bytes(encode_png_rgba(width, height, rgba))
        except OSError as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        self.status_message.emit(f"Textures — saved {Path(path).name}")

    def _export_shown(self) -> None:
        rows = [entry for entry in self.shown() if entry.decodable]
        if not rows:
            QMessageBox.information(self, "Nothing to export", "No decodable textures are shown.")
            return
        folder = QFileDialog.getExistingDirectory(self, f"Export {len(rows):,} textures to folder")
        if not folder:
            return
        target = Path(folder)
        progress = QProgressDialog("Exporting textures...", "Cancel", 0, len(rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        saved = failed = 0
        for number, entry in enumerate(rows):
            progress.setValue(number)
            QGuiApplication.processEvents()
            if progress.wasCanceled():
                break
            try:
                decoded = decode_texture_entry(self._source, entry, 0)
                png = encode_png_rgba(decoded.header.width, decoded.header.height, decoded.rgba)
                (target / f"{safe_file_stem(entry)}.png").write_bytes(png)
                saved += 1
            except Exception:
                failed += 1
        progress.setValue(len(rows))
        message = f"Saved {saved:,} textures to {target}."
        if failed:
            message += f" {failed} could not be decoded."
        self.status_message.emit(f"Textures — {message}")
        QMessageBox.information(self, "Export finished", message)


__all__ = [
    "BANK_ALL",
    "SHOW_ALL",
    "SHOW_DECODED",
    "SHOW_UNDECODED",
    "SHOW_UNUSED",
    "SHOW_USED",
    "SORT_NAME",
    "SORT_NUMBER",
    "SORT_SIZE",
    "TextureTab",
    "filter_textures",
    "safe_file_stem",
]
