"""Initial JFG Forge desktop shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFormLayout,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from jfg_re.forge_data import load_boy_attachment
from jfg_re.forge_scene import (
    evaluate_attachment_positions,
    evaluate_boy_scene,
    evaluate_rigid_mesh_positions,
)
from jfg_re.forge_types import BoyAsset, BoySceneSnapshot, LoadedAttachment
from jfg_forge.attachment_browser import AttachmentBrowserController, inspect_attachment
from jfg_forge.animation_browser import AnimationBrowserEntry, browser_entries, sample_display
from jfg_forge.debug_view import (
    DEFAULT_VIEW_MODE,
    ViewMode,
    prepare_skeleton_debug,
    selected_joint_information,
)
from jfg_forge.export_service import ExportOperation, export_boy, suggested_filename
from jfg_forge.playback import (
    MAX_MOVEMENT_SPEED_TICK,
    MIN_MOVEMENT_SPEED_TICK,
    PlaybackController,
    PlaybackTimingMode,
    animation_label,
    movement_speed_from_slider,
    movement_speed_label,
)
from jfg_forge.runtime_timing import NOMINAL_NTSC_VI_HZ
from jfg_forge.render_data import (
    ModelInformation,
    PreparedRenderData,
    prepare_attachment_render_data,
)
from jfg_forge.viewport import ModelViewport


class MainWindow(QMainWindow):
    def __init__(
        self,
        boy: BoyAsset,
        initial_scene: BoySceneSnapshot,
        data: PreparedRenderData,
        information: ModelInformation,
    ) -> None:
        super().__init__()
        self._boy = boy
        self._scene = initial_scene
        self._playback = PlaybackController(boy.animations)
        self._attachment_browser = AttachmentBrowserController(boy.attachment)
        self._attachment_cache: dict[int, LoadedAttachment] = {}
        self._attachment_render_cache: dict[int, PreparedRenderData] = {}
        self._selected_attachment: LoadedAttachment | None = None
        self._viewport_attachment_slot: int | None = None
        self._browser_entries = {
            entry.animation_index: entry for entry in browser_entries(boy.animations)
        }
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance_playback)
        self._elapsed = QElapsedTimer()
        self.setWindowTitle("JFG Forge")
        self.resize(1180, 760)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_information_panel(information))
        self.viewport = ModelViewport(data, prepare_skeleton_debug(initial_scene.skeleton_debug))
        self.viewport.initialization_failed.connect(self._show_renderer_error)
        splitter.addWidget(self.viewport)
        splitter.setSizes([260, 920])
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self._build_export_menu()
        self.previous_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        self.previous_shortcut.activated.connect(lambda: self._navigate_animation(-1))
        self.next_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        self.next_shortcut.activated.connect(lambda: self._navigate_animation(1))
        self.view_mode_combo.currentIndexChanged.connect(self._select_view_mode)
        self.joint_combo.currentIndexChanged.connect(self._select_joint)
        self._update_joint_display()
        self._update_attachment_display()
        self._update_time_display()

    def _build_export_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        export_menu = file_menu.addMenu("Export")
        operations = (
            ("Export Model...", ExportOperation.MODEL),
            ("Export Current Animation...", ExportOperation.CURRENT_ANIMATION),
            ("Export Model + Current Animation...", ExportOperation.MODEL_AND_CURRENT_ANIMATION),
        )
        self.export_actions: list[QAction] = []
        for label, operation in operations:
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, selected=operation: self._export(selected)
            )
            export_menu.addAction(action)
            self.export_actions.append(action)

    def _export(self, operation: ExportOperation) -> None:
        clip = None if operation is ExportOperation.MODEL else self._playback.clip
        filename = suggested_filename(operation, clip)
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Boy glTF",
            filename,
            "glTF 2.0 (*.gltf)",
        )
        if not destination:
            return
        path = Path(destination)
        if path.suffix.lower() != ".gltf":
            path = path.with_suffix(".gltf")
        try:
            result = export_boy(
                self._boy,
                path,
                operation,
                animation_index=None if clip is None else clip.animation_index,
                timing_context=self._playback.timing_context,
                attachment=(
                    self._selected_attachment
                    if operation is not ExportOperation.CURRENT_ANIMATION
                    else None
                ),
            )
        except Exception as error:
            QMessageBox.critical(self, "JFG Forge export error", str(error))
            self.statusBar().showMessage(f"Export failed: {error}")
            return
        identity = "model"
        if result.animation_index is not None:
            identity = f"animation index {result.animation_index} / ID {result.animation_id}"
            if result.mesh_included:
                identity = f"model + {identity}"
        if result.attachment_prop_id is not None:
            identity = (
                f"{identity} + BoyGun slot {result.attachment_slot} / "
                f"Prop {result.attachment_prop_id}"
            )
        self.statusBar().showMessage(f"Exported {identity} to {result.destination}", 15000)

    def _build_information_panel(self, information: ModelInformation) -> QWidget:
        panel = QFrame()
        panel.setMinimumWidth(220)
        layout = QVBoxLayout(panel)
        heading = QLabel("Asset / Model Info")
        heading.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(heading)
        form = QFormLayout()
        form.addRow("Name", QLabel(information.name or "(unknown)"))
        form.addRow("Prop", QLabel(str(information.prop_id)))
        form.addRow("Source vertices", QLabel(str(information.source_vertices)))
        form.addRow("Render vertices", QLabel(str(information.render_vertices)))
        form.addRow("Faces", QLabel(str(information.faces)))
        form.addRow("Groups", QLabel(str(information.groups)))
        form.addRow("Joints", QLabel(str(information.joints)))
        form.addRow("Textures", QLabel(f"{information.verified_textures} VERIFIED\n{information.unknown_textures} UNKNOWN"))
        form.addRow("Attachment", QLabel(information.attachment_status))
        layout.addLayout(form)
        animation_heading = QLabel("Animation Browser")
        animation_heading.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(animation_heading)
        self.animation_combo = QComboBox()
        self.animation_combo.setMinimumContentsLength(24)
        self.animation_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        for clip in self._boy.animations:
            self.animation_combo.addItem(animation_label(clip), clip.animation_index)
        layout.addWidget(self.animation_combo)
        navigation_row = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.previous_button.setToolTip("Previous animation (Ctrl+Left)")
        self.next_button = QPushButton("Next")
        self.next_button.setToolTip("Next animation (Ctrl+Right)")
        navigation_row.addWidget(self.previous_button)
        navigation_row.addWidget(self.next_button)
        layout.addLayout(navigation_row)
        button_row = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        button_row.addWidget(self.play_button)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, self._playback.slider_maximum)
        self.time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.time_slider.setTickInterval(1000)
        layout.addWidget(self.time_slider)
        self.time_label = QLabel()
        layout.addWidget(self.time_label)
        self.sample_label = QLabel()
        layout.addWidget(self.sample_label)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Movement / Speed:"))
        self.movement_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.movement_speed_slider.setRange(MIN_MOVEMENT_SPEED_TICK, MAX_MOVEMENT_SPEED_TICK)
        self.movement_speed_slider.setSingleStep(1)
        self.movement_speed_slider.setPageStep(1)
        self.movement_speed_slider.setValue(MIN_MOVEMENT_SPEED_TICK)
        self.movement_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.movement_speed_slider.setTickInterval(1)
        self.movement_speed_slider.setToolTip(
            "Movement input for movement-dependent Game Timing; otherwise a preview/export speed multiplier."
        )
        self.movement_speed_value = QLabel(movement_speed_label(1.0))
        self.movement_speed_value.setMinimumWidth(34)
        speed_row.addWidget(self.movement_speed_slider)
        speed_row.addWidget(self.movement_speed_value)
        layout.addLayout(speed_row)
        timing_form = QFormLayout()
        self.timing_mode_combo = QComboBox()
        for mode in PlaybackTimingMode:
            self.timing_mode_combo.addItem(mode.value, mode.value)
        self.timing_mode_combo.setCurrentIndex(
            self.timing_mode_combo.findData(PlaybackTimingMode.GAME.value)
        )
        timing_form.addRow("Timing mode", self.timing_mode_combo)
        self.state_timing_flag_check = QCheckBox("bit 0x10 set")
        self.state_timing_flag_check.setToolTip(
            "Runtime simulation input used by animation index 13 only."
        )
        timing_form.addRow("State timing flag", self.state_timing_flag_check)
        self.timing_status_value = QLabel()
        self.timing_status_value.setWordWrap(True)
        timing_form.addRow("Timing status", self.timing_status_value)
        layout.addLayout(timing_form)
        technical_form = QFormLayout()
        self.animation_index_value = QLabel()
        self.animation_id_value = QLabel()
        self.animation_samples_value = QLabel()
        self.animation_loop_value = QLabel()
        self.animation_stride_value = QLabel()
        self.animation_root_widths_value = QLabel()
        self.animation_root_value = QLabel()
        self.animation_context_value = QLabel()
        self.animation_context_value.setWordWrap(True)
        technical_form.addRow("Index", self.animation_index_value)
        technical_form.addRow("ID", self.animation_id_value)
        technical_form.addRow("Samples", self.animation_samples_value)
        technical_form.addRow("Domain", self.animation_loop_value)
        technical_form.addRow("Sample stride", self.animation_stride_value)
        technical_form.addRow("Root encoding", self.animation_root_widths_value)
        technical_form.addRow("Root XYZ", self.animation_root_value)
        technical_form.addRow("Gameplay context", self.animation_context_value)
        layout.addLayout(technical_form)

        self.mark_reference_button = QPushButton("Mark Current as Reference")
        layout.addWidget(self.mark_reference_button)
        comparison_form = QFormLayout()
        self.selected_clip_value = QLabel()
        self.reference_clip_value = QLabel("none")
        self.selected_clip_value.setWordWrap(True)
        self.reference_clip_value.setWordWrap(True)
        comparison_form.addRow("Selected", self.selected_clip_value)
        comparison_form.addRow("Reference", self.reference_clip_value)
        layout.addLayout(comparison_form)
        self.animation_combo.currentIndexChanged.connect(self._select_animation)
        self.previous_button.clicked.connect(lambda _checked=False: self._navigate_animation(-1))
        self.next_button.clicked.connect(lambda _checked=False: self._navigate_animation(1))
        self.play_button.clicked.connect(self._toggle_playback)
        self.stop_button.clicked.connect(self._stop_playback)
        self.time_slider.valueChanged.connect(self._scrub)
        self.movement_speed_slider.valueChanged.connect(self._set_movement_speed)
        self.timing_mode_combo.currentIndexChanged.connect(self._set_timing_mode)
        self.state_timing_flag_check.toggled.connect(self._set_state_timing_flag)
        self.mark_reference_button.clicked.connect(self._mark_reference)

        attachment_heading = QLabel("BoyGun / Attachment")
        attachment_heading.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(attachment_heading)
        attachment_form = QFormLayout()
        self.attachment_combo = QComboBox()
        self.attachment_combo.setToolTip(
            "The selected BoyGun model is included automatically in model-bearing glTF exports."
        )
        for entry in self._attachment_browser.entries:
            self.attachment_combo.addItem(entry.label, entry.slot)
        attachment_form.addRow("Selection", self.attachment_combo)
        self.attachment_slot_value = QLabel("none")
        self.attachment_prop_value = QLabel("none")
        self.attachment_name_value = QLabel("none")
        self.attachment_faces_value = QLabel("0")
        self.attachment_textures_value = QLabel("none")
        self.attachment_transform_value = QLabel("none")
        self.attachment_socket_value = QLabel("Joint 6 — BoyGun attachment socket [VERIFIED]")
        self.attachment_socket_value.setWordWrap(True)
        attachment_form.addRow("Slot", self.attachment_slot_value)
        attachment_form.addRow("Prop", self.attachment_prop_value)
        attachment_form.addRow("Name", self.attachment_name_value)
        attachment_form.addRow("Active faces", self.attachment_faces_value)
        attachment_form.addRow("Textures", self.attachment_textures_value)
        attachment_form.addRow("Transform", self.attachment_transform_value)
        attachment_form.addRow("Socket", self.attachment_socket_value)
        layout.addLayout(attachment_form)
        self.attachment_combo.currentIndexChanged.connect(self._select_attachment)

        debug_heading = QLabel("Viewport Debug")
        debug_heading.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        layout.addWidget(debug_heading)
        debug_form = QFormLayout()
        self.view_mode_combo = QComboBox()
        for mode in ViewMode:
            self.view_mode_combo.addItem(mode.value, mode.value)
        self.view_mode_combo.setCurrentIndex(list(ViewMode).index(DEFAULT_VIEW_MODE))
        debug_form.addRow("View", self.view_mode_combo)
        self.joint_combo = QComboBox()
        for joint in self._boy.model.skeleton.joints:
            self.joint_combo.addItem(str(joint.joint_id), joint.joint_id)
        debug_form.addRow("Joint", self.joint_combo)
        self.joint_id_value = QLabel()
        self.joint_parent_value = QLabel()
        self.joint_position_value = QLabel()
        self.joint_static_value = QLabel()
        self.joint_context_value = QLabel()
        self.joint_geometry_value = QLabel()
        self.joint_position_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.joint_static_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.joint_context_value.setWordWrap(True)
        debug_form.addRow("Joint ID", self.joint_id_value)
        debug_form.addRow("Parent ID", self.joint_parent_value)
        debug_form.addRow("Position XYZ", self.joint_position_value)
        debug_form.addRow("Static local XYZ", self.joint_static_value)
        debug_form.addRow("Active geometry", self.joint_geometry_value)
        debug_form.addRow("Context", self.joint_context_value)
        layout.addLayout(debug_form)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(300)
        scroll.setMaximumWidth(460)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _select_view_mode(self, _combo_index: int = -1) -> None:
        self.viewport.set_view_mode(ViewMode(self.view_mode_combo.currentData()))

    def _select_joint(self, _combo_index: int = -1) -> None:
        joint_id = int(self.joint_combo.currentData())
        self.viewport.set_selected_joint(joint_id)
        self._update_joint_display()

    def _select_attachment(self, _combo_index: int = -1) -> None:
        raw_slot = self.attachment_combo.currentData()
        slot = None if raw_slot is None else int(raw_slot)
        try:
            self._attachment_browser.select(slot)
            if slot is None:
                self._selected_attachment = None
            else:
                loaded = self._attachment_cache.get(slot)
                if loaded is None:
                    loaded = load_boy_attachment(self._boy, slot=slot)
                    self._attachment_cache[slot] = loaded
                self._selected_attachment = loaded
                joint_index = self.joint_combo.findData(self._boy.attachment.attachment_joint_id)
                if joint_index >= 0:
                    self.joint_combo.setCurrentIndex(joint_index)
            self._evaluate_current_pose()
        except Exception as error:
            blocker = QSignalBlocker(self.attachment_combo)
            self.attachment_combo.setCurrentIndex(0)
            del blocker
            self._attachment_browser.select(None)
            self._selected_attachment = None
            self._evaluate_current_pose()
            QMessageBox.critical(self, "JFG Forge attachment error", str(error))

    def _update_joint_display(self) -> None:
        joint_id = int(self.joint_combo.currentData())
        information = selected_joint_information(self._scene, joint_id)
        self.joint_id_value.setText(str(information.joint_id))
        self.joint_parent_value.setText("none" if information.parent_id is None else str(information.parent_id))
        self.joint_position_value.setText(
            ", ".join(f"{value:.3f}" for value in information.evaluated_position)
        )
        self.joint_static_value.setText(
            ", ".join(f"{value:.3f}" for value in information.static_local_translation)
        )
        if information.has_active_rendered_geometry:
            self.joint_geometry_value.setText(
                f"yes — {information.rendered_source_vertex_count} source vertices / "
                f"{information.rendered_corner_count} rendered corners"
            )
        else:
            self.joint_geometry_value.setText("no")
        self.joint_context_value.setText(information.context or "—")

    def _select_animation(self, _combo_index: int = -1) -> None:
        was_playing = self._playback.playing
        self._playback.select(int(self.animation_combo.currentData()))
        self.time_slider.setRange(0, self._playback.slider_maximum)
        if was_playing:
            self._elapsed.restart()
            self._timer.start()
            self.play_button.setText("Pause")
        else:
            self._timer.stop()
            self.play_button.setText("Play")
        self._evaluate_current_pose()

    def _navigate_animation(self, offset: int) -> None:
        target = self._playback.adjacent_index(offset)
        combo_index = self.animation_combo.findData(target)
        if combo_index < 0:
            raise KeyError(f"Animation index {target} is unavailable in the selector.")
        self.animation_combo.setCurrentIndex(combo_index)

    @staticmethod
    def _clip_summary(entry: AnimationBrowserEntry) -> str:
        loop_text = "loop" if entry.loop else "non-loop"
        return (
            f"Index {entry.animation_index} / ID {entry.animation_id}\n"
            f"{entry.sample_count} samples, {entry.sample_stride_bytes}-byte stride, {loop_text}"
        )

    def _mark_reference(self, _checked: bool = False) -> None:
        self._playback.mark_reference()
        reference = self._playback.reference_clip
        if reference is None:
            return
        entry = self._browser_entries[reference.animation_index]
        self.reference_clip_value.setText(self._clip_summary(entry))

    def _toggle_playback(self, _checked: bool = False) -> None:
        if self._playback.playing:
            self._playback.pause()
            self._timer.stop()
            self.play_button.setText("Play")
        else:
            self._playback.play()
            self._elapsed.start()
            self._timer.start()
            self.play_button.setText("Pause")
            self._evaluate_current_pose()

    def _stop_playback(self, _checked: bool = False) -> None:
        self._timer.stop()
        self._playback.stop()
        self.play_button.setText("Play")
        self._evaluate_current_pose()

    def _scrub(self, slider_value: int) -> None:
        self._playback.set_time(self._playback.time_from_slider(slider_value))
        if self._playback.playing:
            self._elapsed.restart()
        self._evaluate_current_pose(update_slider=False)

    def _set_movement_speed(self, slider_value: int) -> None:
        value = movement_speed_from_slider(slider_value)
        self._playback.set_movement_speed(value)
        self.movement_speed_value.setText(movement_speed_label(value))
        if self._playback.playing:
            self._elapsed.restart()
        self._update_timing_display()

    def _set_timing_mode(self, _combo_index: int = -1) -> None:
        self._playback.set_timing_mode(PlaybackTimingMode(self.timing_mode_combo.currentData()))
        if self._playback.playing:
            self._elapsed.restart()
        self._update_timing_display()

    def _set_state_timing_flag(self, enabled: bool) -> None:
        self._playback.set_state_timing_flag(bool(enabled))
        if self._playback.playing:
            self._elapsed.restart()
        self._update_timing_display()

    def _advance_playback(self) -> None:
        self._playback.advance(self._elapsed.restart() / 1000.0)
        self._evaluate_current_pose()
        if not self._playback.playing:
            self._timer.stop()
            self.play_button.setText("Play")

    def _evaluate_current_pose(self, *, update_slider: bool = True) -> None:
        try:
            scene = evaluate_boy_scene(
                self._boy,
                animation_index=self._playback.animation_index,
                time=self._playback.time,
                loaded_attachment=self._selected_attachment,
            )
            positions = evaluate_rigid_mesh_positions(scene.model.render_mesh, scene.pose)
            self.viewport.set_scene_data(positions, prepare_skeleton_debug(scene.skeleton_debug))
            if scene.attachment is None:
                if self._viewport_attachment_slot is not None:
                    self.viewport.set_attachment_data(None)
                    self._viewport_attachment_slot = None
            else:
                slot = scene.attachment.attachment.slot.slot
                if self._viewport_attachment_slot != slot:
                    render_data = self._attachment_render_cache.get(slot)
                    if render_data is None:
                        render_data = prepare_attachment_render_data(scene.attachment)
                        self._attachment_render_cache[slot] = render_data
                    self.viewport.set_attachment_data(render_data)
                    self._viewport_attachment_slot = slot
                self.viewport.set_attachment_positions(
                    evaluate_attachment_positions(scene.attachment)
                )
            self._scene = scene
            self._update_joint_display()
            self._update_attachment_display()
        except Exception as error:
            self._timer.stop()
            self._playback.pause()
            self.play_button.setText("Play")
            QMessageBox.critical(self, "JFG Forge animation error", str(error))
            return
        self._update_time_display(update_slider=update_slider)

    def _update_attachment_display(self) -> None:
        if self._selected_attachment is None or self._scene.attachment is None:
            self.attachment_slot_value.setText("none")
            self.attachment_prop_value.setText("none")
            self.attachment_name_value.setText("none")
            self.attachment_faces_value.setText("0")
            self.attachment_textures_value.setText("none")
            self.attachment_transform_value.setText("none")
            return
        information = inspect_attachment(self._selected_attachment, self._scene.attachment)
        self.attachment_slot_value.setText(str(information.slot))
        self.attachment_prop_value.setText(str(information.prop_id))
        self.attachment_name_value.setText(information.name)
        self.attachment_faces_value.setText(str(information.active_faces))
        self.attachment_textures_value.setText(
            f"{information.verified_textures} VERIFIED / "
            f"{information.unknown_textures} UNKNOWN"
        )
        self.attachment_transform_value.setText(information.transform_status.value)

    def _update_time_display(self, *, update_slider: bool = True) -> None:
        if update_slider:
            blocker = QSignalBlocker(self.time_slider)
            self.time_slider.setValue(self._playback.slider_from_time())
            del blocker
        end_text = f"<{self._playback.end_time:.3f}" if self._playback.clip.loop else f"{self._playback.end_time:.3f}"
        self.time_label.setText(f"{self._playback.time:.3f} / {end_text} samples")
        clip = self._playback.clip
        entry = self._browser_entries[clip.animation_index]
        position = sample_display(self._scene.pose)
        self.sample_label.setText(
            f"sample {position.current_sample} -> {position.next_sample}; "
            f"fraction {position.fraction_10bit}/1024 ({position.fraction:.6f})"
        )
        self.animation_index_value.setText(str(entry.animation_index))
        self.animation_id_value.setText(str(entry.animation_id))
        self.animation_samples_value.setText(str(entry.sample_count))
        if entry.loop:
            self.animation_loop_value.setText(f"loop [0, {entry.sample_count})")
        else:
            self.animation_loop_value.setText(f"non-loop [0, {entry.sample_count - 1}]")
        self.animation_stride_value.setText(f"{entry.sample_stride_bytes} bytes")
        self.animation_root_widths_value.setText(entry.root_translation_description)
        self.animation_root_value.setText(
            ", ".join(f"{value:.3f}" for value in self._scene.pose.root_translation)
        )
        self.animation_context_value.setText(
            f"{entry.context_status.value}: {entry.gameplay_context}"
        )
        self.selected_clip_value.setText(self._clip_summary(entry))
        self._update_timing_display()
        self.statusBar().showMessage(
            f"Boy / Prop 220 — animation index {clip.animation_index} — "
            f"ID {clip.animation_id} — time {self._playback.time:.3f} — "
            f"{self._playback.timing_mode.value}"
        )

    def _update_timing_display(self) -> None:
        timing = self._playback.game_timing
        self.state_timing_flag_check.setEnabled(
            self._playback.timing_mode is PlaybackTimingMode.GAME
            and timing.requires_state_timing_flag
        )
        if self._playback.timing_mode is PlaybackTimingMode.TECHNICAL:
            self.timing_status_value.setText(
                f"Technical timing: {self._playback.effective_samples_per_second:.6g} "
                f"samples/s at Movement / Speed {self._playback.movement_speed:.1f}."
            )
            return
        if self._playback.uses_technical_fallback:
            self.timing_status_value.setText(
                "UNKNOWN Game Timing — explicit Technical fallback multiplied by Movement / Speed."
            )
            return
        dependency = (
            f"; Movement / Speed supplies runtime input {self._playback.movement_speed:.1f} "
            f"for {timing.dependency.value}"
            if timing.requires_movement_metric
            else (
                f"; runtime flag 0x10 = {'set' if self._playback.state_timing_flag else 'clear'}; "
                "slider is a preview/export multiplier"
                if timing.requires_state_timing_flag
                else "; fixed state scale; slider is a preview/export multiplier"
            )
        )
        base_rate = self._playback.base_samples_per_second
        effective_rate = self._playback.effective_samples_per_second
        self.timing_status_value.setText(
            f"VERIFIED Game Timing: {base_rate:.6g} samples/s at 1x "
            f"(nominal NTSC {NOMINAL_NTSC_VI_HZ:g} VI/s){dependency}; "
            f"Movement / Speed {self._playback.movement_speed:.1f} gives "
            f"{effective_rate:.6g} samples/s."
        )

    def _show_renderer_error(self, message: str) -> None:
        self.statusBar().showMessage("OpenGL initialization failed")
        QMessageBox.critical(self, "JFG Forge renderer error", message)
