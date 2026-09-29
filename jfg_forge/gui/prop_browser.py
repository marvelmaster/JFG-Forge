"""The "Models" tab: browse every static model Prop in the ROM with its textures."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from jfg_forge.core.prop_catalog import PropEntry, StaticModel, list_props, load_static_model
from jfg_forge.core.rom_source import RomSource
from jfg_forge.gui.debug_view import PreparedSkeletonDebug, ViewMode
from jfg_forge.gui.render_data import prepare_static_render_data
from jfg_forge.gui.viewport import ModelViewport

FILTER_STATIC = "Static models"
FILTER_ANIMATED = "Animated props (rest pose)"
FILTER_ALL = "All props"
SORT_ID = "Prop number"
SORT_NAME = "Name"

# One joint at the origin: the viewport needs a skeleton, static models have none.
_NO_SKELETON = PreparedSkeletonDebug(joint_ids=(0,), joint_positions=((0.0, 0.0, 0.0),), edge_positions=())


def filter_props(
    entries: tuple[PropEntry, ...],
    *,
    mode: str,
    text: str = "",
    sort: str = SORT_ID,
    known_empty: frozenset[int] = frozenset(),
) -> list[PropEntry]:
    """Apply the tab's filter, search text and sort order (Qt-free, testable).

    Props without drawable geometry (hit boxes and other helper models) appear
    only under "All props".
    """
    visible = [entry for entry in entries if entry.drawable and entry.prop_id not in known_empty]
    if mode == FILTER_STATIC:
        chosen = [entry for entry in visible if not entry.animated]
    elif mode == FILTER_ANIMATED:
        chosen = [entry for entry in visible if entry.animated]
    else:
        chosen = list(entries)
    needle = text.strip().lower()
    if needle:
        chosen = [
            entry for entry in chosen if needle in entry.name.lower() or needle == str(entry.prop_id)
        ]
    key = (lambda entry: (entry.name.lower(), entry.prop_id)) if sort == SORT_NAME else (lambda entry: entry.prop_id)
    return sorted(chosen, key=key)


class PropBrowser(QWidget):
    status_message = Signal(str)

    def __init__(self, source: RomSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._entries = list_props(source)
        self._viewport: ModelViewport | None = None
        self._current: StaticModel | None = None
        self._known_empty: set[int] = set()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_side_panel())
        self._view_area = QFrame()
        self._view_layout = QVBoxLayout(self._view_area)
        self._view_layout.setContentsMargins(0, 0, 0, 0)
        self._message = QLabel("Select a model from the list.")
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
        heading = QLabel("Models")
        heading.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(heading)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name or Prop number")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)
        form = QFormLayout()
        self.filter_combo = QComboBox()
        for label in (FILTER_STATIC, FILTER_ANIMATED, FILTER_ALL):
            self.filter_combo.addItem(label, label)
        self.sort_combo = QComboBox()
        for label in (SORT_ID, SORT_NAME):
            self.sort_combo.addItem(label, label)
        form.addRow("Show", self.filter_combo)
        form.addRow("Sort by", self.sort_combo)
        layout.addLayout(form)
        self.count_label = QLabel("")
        layout.addWidget(self.count_label)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, stretch=1)

        info = QFormLayout()
        self.name_value = QLabel("-")
        self.prop_value = QLabel("-")
        self.kind_value = QLabel("-")
        self.kind_value.setWordWrap(True)
        self.faces_value = QLabel("-")
        self.vertices_value = QLabel("-")
        self.groups_value = QLabel("-")
        self.joints_value = QLabel("-")
        self.animations_value = QLabel("-")
        self.textures_value = QLabel("-")
        self.textures_value.setWordWrap(True)
        for label, widget in (
            ("Name", self.name_value),
            ("Prop", self.prop_value),
            ("Type", self.kind_value),
            ("Faces", self.faces_value),
            ("Vertices", self.vertices_value),
            ("Groups", self.groups_value),
            ("Joints", self.joints_value),
            ("Animations", self.animations_value),
            ("Textures", self.textures_value),
        ):
            info.addRow(label, widget)
        layout.addLayout(info)
        hint = QLabel("Drag to orbit, middle-drag to pan, wheel to zoom.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search_edit.textChanged.connect(self._refresh_list)
        self.filter_combo.currentIndexChanged.connect(self._refresh_list)
        self.sort_combo.currentIndexChanged.connect(self._refresh_list)
        self.list_widget.currentItemChanged.connect(self._select_item)
        return panel

    # ------------------------------------------------------------------ list
    def _refresh_list(self, *_args: object) -> None:
        keep = None if self._current is None else self._current.entry.prop_id
        rows = filter_props(
            self._entries,
            mode=str(self.filter_combo.currentData()),
            text=self.search_edit.text(),
            sort=str(self.sort_combo.currentData()),
            known_empty=frozenset(self._known_empty),
        )
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        selected_row = -1
        for row, entry in enumerate(rows):
            empty = not entry.drawable or entry.prop_id in self._known_empty
            item = QListWidgetItem(f"{entry.name}   (#{entry.prop_id})" + ("   [no geometry]" if empty else ""))
            item.setData(Qt.ItemDataRole.UserRole, entry.prop_id)
            item.setToolTip(entry.kind)
            self.list_widget.addItem(item)
            if entry.prop_id == keep:
                selected_row = row
        if selected_row >= 0:
            self.list_widget.setCurrentRow(selected_row)
        self.list_widget.blockSignals(False)
        self.count_label.setText(f"{len(rows)} of {len(self._entries)} Props")

    def _select_item(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if item is not None:
            self.show_prop(int(item.data(Qt.ItemDataRole.UserRole)))

    # ------------------------------------------------------------------ view
    def show_prop(self, prop_id: int) -> None:
        entry = next(item for item in self._entries if item.prop_id == prop_id)
        self._set_entry_info(entry)
        try:
            static = load_static_model(self._source, prop_id)
        except Exception as error:
            self._show_message(f"{entry.name} (#{prop_id}) cannot be shown: {error}")
            self.status_message.emit(f"Models / Prop {prop_id} — {entry.name} — no geometry to show")
            self.faces_value.setText("0")
            if "no drawable faces" in str(error) and prop_id not in self._known_empty:
                self._known_empty.add(prop_id)
                self._refresh_list()
            return
        self._current = static
        data = prepare_static_render_data(static.model, static.positions)
        if self._viewport is None:
            self._viewport = ModelViewport(data, _NO_SKELETON)
            self._viewport.initialization_failed.connect(lambda text: self._show_message(text, keep_view=False))
            self._viewport.set_view_mode(ViewMode.MESH)
            self._view_layout.addWidget(self._viewport)
        else:
            self._viewport.set_model_data(data, _NO_SKELETON)
        self._message.hide()
        self._viewport.show()
        model = static.model
        self.status_message.emit(
            f"Models / Prop {prop_id} — {entry.name} — {static.faces} faces — {entry.kind}"
        )
        self.faces_value.setText(str(static.faces))
        self.vertices_value.setText(f"{len(model.source_vertices)} source / {len(model.render_mesh.vertices)} render")
        self.groups_value.setText(str(len(model.groups)))
        decoded = sum(texture.supported for texture in model.textures)
        text = f"{decoded} of {len(model.textures)} decoded"
        if static.drawn_unknown_textures:
            text += f"; {static.drawn_unknown_textures} undecoded (drawn grey)"
        self.textures_value.setText(text)

    def _show_message(self, text: str, *, keep_view: bool = True) -> None:
        self._message.setText(text)
        self._message.show()
        if self._viewport is not None and not keep_view:
            self._viewport.hide()
        elif self._viewport is not None:
            self._viewport.hide()

    def _set_entry_info(self, entry: PropEntry) -> None:
        self.name_value.setText(entry.name)
        self.prop_value.setText(str(entry.prop_id))
        self.kind_value.setText(entry.kind)
        self.joints_value.setText(str(entry.joints))
        self.animations_value.setText(str(entry.clips))
        self.faces_value.setText("-")
        self.vertices_value.setText("-")
        self.groups_value.setText("-")
        self.textures_value.setText("-")

    # ------------------------------------------------------------------ API
    def select_first(self) -> None:
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)


__all__ = [
    "FILTER_ALL",
    "FILTER_ANIMATED",
    "FILTER_STATIC",
    "PropBrowser",
    "SORT_ID",
    "SORT_NAME",
    "filter_props",
]
