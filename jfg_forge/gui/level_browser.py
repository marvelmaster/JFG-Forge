"""The "Levels" tab: browse the ROM's levels and look at their textured geometry."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from jfg_forge.core.level_data import LevelDataError, LevelEntry, LevelGeometry, list_levels, load_level_geometry
from jfg_forge.core.rom_source import RomSource
from jfg_forge.gui.debug_view import PreparedSkeletonDebug, ViewMode
from jfg_forge.gui.render_data import prepare_level_render_data
from jfg_forge.gui.viewport import ModelViewport

SORT_NUMBER = "Level number"
SORT_NAME = "Name"
SORT_BLOCK = "Geometry block"

# One joint at the origin: the viewport needs a skeleton, levels have none.
_NO_SKELETON = PreparedSkeletonDebug(joint_ids=(0,), joint_positions=((0.0, 0.0, 0.0),), edge_positions=())


def filter_levels(entries: tuple[LevelEntry, ...], *, text: str = "", sort: str = SORT_NUMBER) -> list[LevelEntry]:
    """Apply the tab's search text and sort order (Qt-free, testable)."""
    needle = text.strip().lower()
    chosen = list(entries)
    if needle:
        chosen = [entry for entry in chosen if needle in entry.name.lower() or needle == str(entry.index)]
    keys = {
        SORT_NAME: lambda entry: (entry.name.lower(), entry.index),
        SORT_BLOCK: lambda entry: (entry.block_id, entry.index),
    }
    return sorted(chosen, key=keys.get(sort, lambda entry: entry.index))


class LevelBrowser(QWidget):
    status_message = Signal(str)

    def __init__(self, source: RomSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._entries = list_levels(source)
        self._viewport: ModelViewport | None = None
        self._current: LevelEntry | None = None
        self._cache: dict[int, LevelGeometry] = {}

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_side_panel())
        self._view_area = QFrame()
        self._view_layout = QVBoxLayout(self._view_area)
        self._view_layout.setContentsMargins(0, 0, 0, 0)
        self._message = QLabel("Select a level from the list.")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        self._view_layout.addWidget(self._message)
        splitter.addWidget(self._view_area)
        splitter.setSizes([300, 880])
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self._refresh_list()

    # ------------------------------------------------------------------ UI
    def _build_side_panel(self) -> QWidget:
        panel = QFrame()
        panel.setMinimumWidth(240)
        layout = QVBoxLayout(panel)
        heading = QLabel("Levels")
        heading.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(heading)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name or level number")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        form = QFormLayout()
        self.sort_combo = QComboBox()
        for label in (SORT_NUMBER, SORT_NAME, SORT_BLOCK):
            self.sort_combo.addItem(label, label)
        form.addRow("Sort by", self.sort_combo)
        layout.addLayout(form)
        self.count_label = QLabel("")
        layout.addWidget(self.count_label)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, stretch=1)

        info = QFormLayout()
        self.name_value = QLabel("-")
        self.name_value.setWordWrap(True)
        self.number_value = QLabel("-")
        self.block_value = QLabel("-")
        self.shared_value = QLabel("-")
        self.shared_value.setWordWrap(True)
        self.faces_value = QLabel("-")
        self.vertices_value = QLabel("-")
        self.segments_value = QLabel("-")
        self.textures_value = QLabel("-")
        self.textures_value.setWordWrap(True)
        for label, widget in (
            ("Name", self.name_value),
            ("Level", self.number_value),
            ("Geometry block", self.block_value),
            ("Same geometry", self.shared_value),
            ("Faces", self.faces_value),
            ("Vertices", self.vertices_value),
            ("Segments", self.segments_value),
            ("Textures", self.textures_value),
        ):
            info.addRow(label, widget)
        layout.addLayout(info)
        hint = QLabel(
            "Geometry only: no objects, sky or water yet; the baked vertex shading is applied. "
            "Drag to orbit, middle-drag to pan, wheel to zoom."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search_edit.textChanged.connect(self._refresh_list)
        self.sort_combo.currentIndexChanged.connect(self._refresh_list)
        self.list_widget.currentItemChanged.connect(self._select_item)
        return panel

    # ------------------------------------------------------------------ list
    def _refresh_list(self, *_args: object) -> None:
        keep = None if self._current is None else self._current.index
        rows = filter_levels(
            self._entries, text=self.search_edit.text(), sort=str(self.sort_combo.currentData())
        )
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        selected_row = -1
        for row, entry in enumerate(rows):
            item = QListWidgetItem(f"{entry.name}   (#{entry.index})")
            item.setData(Qt.ItemDataRole.UserRole, entry.index)
            item.setToolTip(f"Geometry block {entry.block_id}")
            self.list_widget.addItem(item)
            if entry.index == keep:
                selected_row = row
        if selected_row >= 0:
            self.list_widget.setCurrentRow(selected_row)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(rows)} of {len(self._entries)} levels")

    def _select_item(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if item is not None:
            self.show_level(int(item.data(Qt.ItemDataRole.UserRole)))

    # ------------------------------------------------------------------ view
    def _geometry(self, block_id: int) -> LevelGeometry:
        if block_id not in self._cache:
            if len(self._cache) >= 4:
                self._cache.pop(next(iter(self._cache)))
            self._cache[block_id] = load_level_geometry(self._source, block_id)
        return self._cache[block_id]

    def show_level(self, index: int) -> None:
        entry = next(item for item in self._entries if item.index == index)
        self._current = entry
        self._set_entry_info(entry)
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            geometry = self._geometry(entry.block_id)
            data = prepare_level_render_data(geometry)
        except (LevelDataError, ValueError, OSError) as error:
            self._show_message(f"{entry.name} (#{index}) cannot be shown: {error}")
            self.status_message.emit(f"Levels / {entry.name} — no geometry to show")
            return
        finally:
            QGuiApplication.restoreOverrideCursor()
        if self._viewport is None:
            self._viewport = ModelViewport(data, _NO_SKELETON)
            self._viewport.initialization_failed.connect(self._show_message)
            self._viewport.set_view_mode(ViewMode.MESH)
            self._view_layout.addWidget(self._viewport)
        else:
            self._viewport.set_model_data(data, _NO_SKELETON)
        self._message.hide()
        self._viewport.show()
        self.faces_value.setText(f"{geometry.faces:,}")
        self.vertices_value.setText(f"{geometry.source_vertices:,}")
        self.segments_value.setText(str(geometry.segments))
        text = f"{geometry.decoded_textures} of {len(geometry.textures)} decoded"
        missing = len(geometry.textures) - geometry.decoded_textures
        if missing:
            text += f"; {missing} undecoded (drawn grey)"
        self.textures_value.setText(text)
        self.status_message.emit(
            f"Levels / #{entry.index} {entry.name} — block {entry.block_id} — {geometry.faces:,} faces"
        )

    def _show_message(self, text: str) -> None:
        self._message.setText(text)
        self._message.show()
        if self._viewport is not None:
            self._viewport.hide()

    def _set_entry_info(self, entry: LevelEntry) -> None:
        names = {item.index: item.name for item in self._entries}
        self.name_value.setText(entry.name)
        self.number_value.setText(str(entry.index))
        self.block_value.setText(str(entry.block_id))
        shared = ", ".join(names[other] for other in entry.shared_with[:6])
        if len(entry.shared_with) > 6:
            shared += f" (+{len(entry.shared_with) - 6} more)"
        self.shared_value.setText(shared or "-")
        for label in (self.faces_value, self.vertices_value, self.segments_value, self.textures_value):
            label.setText("-")

    # ------------------------------------------------------------------ API
    def select_first(self) -> None:
        """Open the first level with real geometry (the front-end entries are nearly empty)."""
        for row in range(self.list_widget.count()):
            if self.list_widget.item(row).data(Qt.ItemDataRole.UserRole) >= 2:
                self.list_widget.setCurrentRow(row)
                return


__all__ = ["LevelBrowser", "SORT_BLOCK", "SORT_NAME", "SORT_NUMBER", "filter_levels"]
