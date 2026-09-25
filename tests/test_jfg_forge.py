from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_forge.camera import OrbitCamera
from jfg_forge.animation_browser import (
    UNKNOWN_CONTEXT,
    VERIFIED_GAMEPLAY_CONTEXTS,
    browser_entries,
    research_context,
    sample_display,
)
from jfg_forge.debug_view import (
    DEFAULT_VIEW_MODE,
    JOINT_6_CONTEXT,
    ViewMode,
    prepare_skeleton_debug,
    selected_joint_information,
)
from jfg_forge.playback import (
    PlaybackController,
    PlaybackTimingMode,
    SUPPORTED_SPEEDS,
    animation_label,
    movement_speed_label,
)
from jfg_forge.render_data import NEUTRAL_FALLBACK_RGBA, model_information, prepare_render_data
from jfg_re.forge_data import load_boy
from jfg_re.forge_scene import evaluate_boy_scene, evaluate_rigid_mesh_positions


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class JfgForgeRenderDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)
        cls.scene = evaluate_boy_scene(cls.boy, animation_index=0, time=0.0)
        cls.data = prepare_render_data(cls.scene)

    def test_prepares_verified_static_reference_mesh(self) -> None:
        self.assertEqual(len(self.data.positions), 1506)
        self.assertEqual(len(self.data.uvs), 1506)
        self.assertEqual(sum(batch.face_count for batch in self.data.batches), 502)
        self.assertEqual(len(self.data.textures), 14)
        self.assertTrue(all(len(texture.rgba) == texture.width * texture.height * 4 for texture in self.data.textures))

    def test_material_batches_only_reference_uploaded_verified_textures(self) -> None:
        uploaded = {texture.texture_index for texture in self.data.textures}
        verified_batches = [batch for batch in self.data.batches if batch.uses_verified_texture]
        self.assertTrue(verified_batches)
        self.assertTrue(all(batch.texture_index in uploaded for batch in verified_batches))

    def test_unknown_formats_receive_neutral_fallback(self) -> None:
        fallback = [batch for batch in self.data.batches if not batch.uses_verified_texture]
        self.assertEqual(sum(batch.face_count for batch in fallback), 24)
        self.assertTrue(all(batch.texture_index is None for batch in fallback))
        self.assertTrue(all(batch.fallback_rgba == NEUTRAL_FALLBACK_RGBA for batch in fallback))
        self.assertTrue(all(batch.fallback_reason == "UNKNOWN texture format" for batch in fallback))

    def test_model_information_comes_from_scene_objects(self) -> None:
        information = model_information(self.scene)
        self.assertEqual(
            (
                information.name,
                information.prop_id,
                information.source_vertices,
                information.render_vertices,
                information.faces,
                information.groups,
                information.joints,
                information.verified_textures,
                information.unknown_textures,
                information.attachment_status,
            ),
            ("Boy", 220, 660, 1506, 502, 82, 21, 14, 4, "matrix 6 placement VERIFIED"),
        )

    def test_skeleton_debug_has_verified_topology(self) -> None:
        skeleton = prepare_skeleton_debug(self.scene.skeleton_debug)
        self.assertEqual(skeleton.joint_count, 21)
        self.assertEqual(skeleton.edge_count, 20)
        self.assertEqual(skeleton.joint_ids, tuple(range(21)))
        self.assertEqual(len(skeleton.edge_positions), 40)

    def test_view_modes_have_explicit_mesh_and_skeleton_state(self) -> None:
        self.assertIs(DEFAULT_VIEW_MODE, ViewMode.MESH_SKELETON)
        self.assertEqual(
            [(mode.value, mode.shows_mesh, mode.shows_skeleton) for mode in ViewMode],
            [
                ("Mesh", True, False),
                ("Skeleton", False, True),
                ("Mesh + Skeleton", True, True),
            ],
        )

    def test_selected_joint_metadata_and_joint6_context(self) -> None:
        information = selected_joint_information(self.scene, 6)
        self.assertEqual(information.joint_id, 6)
        self.assertEqual(information.parent_id, 5)
        self.assertEqual(information.evaluated_position, self.scene.skeleton_debug.joints[6].position)
        self.assertEqual(
            information.static_local_translation,
            self.scene.model.skeleton.joints[6].static_local_translation,
        )
        self.assertEqual(information.context, JOINT_6_CONTEXT)
        self.assertFalse(information.has_active_rendered_geometry)
        self.assertEqual(information.rendered_corner_count, 0)
        hand = selected_joint_information(self.scene, 9)
        self.assertTrue(hand.has_active_rendered_geometry)
        self.assertGreater(hand.rendered_source_vertex_count, 0)
        self.assertIsNone(selected_joint_information(self.scene, 5).context)

    def test_mesh_and_skeleton_update_from_the_same_evaluated_scene(self) -> None:
        later = evaluate_boy_scene(self.boy, animation_index=0, time=7.5)
        initial_skeleton = prepare_skeleton_debug(self.scene.skeleton_debug)
        later_skeleton = prepare_skeleton_debug(later.skeleton_debug)
        later_mesh = evaluate_rigid_mesh_positions(later.model.render_mesh, later.pose)
        self.assertNotEqual(later_skeleton.joint_positions, initial_skeleton.joint_positions)
        self.assertNotEqual(later_mesh, self.data.positions)
        self.assertEqual(
            later_skeleton.joint_positions,
            tuple(tuple(joint.world_matrix[3][:3]) for joint in later.pose.joints),
        )
        self.assertEqual(len(later_mesh), len(later.model.render_mesh.vertices))


class OrbitCameraTests(unittest.TestCase):
    def test_auto_frame_uses_bounds_and_produces_finite_matrices(self) -> None:
        camera = OrbitCamera.from_points(((-2.0, -4.0, -6.0), (4.0, 8.0, 10.0)))
        self.assertEqual(camera.target, (1.0, 2.0, 2.0))
        self.assertGreater(camera.distance, camera.scene_radius)
        values = (*sum(camera.view_matrix(), ()), *sum(camera.projection_matrix(16 / 9), ()))
        self.assertTrue(all(math.isfinite(value) for value in values))

    def test_orbit_pan_and_zoom_change_camera(self) -> None:
        camera = OrbitCamera.from_points(((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)))
        original_eye = camera.eye
        camera.orbit(20.0, -10.0)
        self.assertNotEqual(camera.eye, original_eye)
        original_target = camera.target
        camera.pan(12.0, -4.0)
        self.assertNotEqual(camera.target, original_target)
        original_distance = camera.distance
        camera.zoom(1.0)
        self.assertLess(camera.distance, original_distance)

    def test_projection_rejects_invalid_aspect(self) -> None:
        with self.assertRaises(ValueError):
            OrbitCamera().projection_matrix(0.0)


class PlaybackControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def setUp(self) -> None:
        self.playback = PlaybackController(self.boy.animations)

    def test_all_52_catalogued_clips_have_technical_selection_metadata(self) -> None:
        self.assertEqual(len(self.playback.clips), 52)
        self.assertEqual([clip.animation_index for clip in self.playback.clips], list(range(52)))
        self.assertEqual(self.playback.clips[0].animation_id, 1026)
        self.assertEqual(self.playback.clips[43].animation_id, 1069)
        self.assertEqual(animation_label(self.playback.clips[0]), "Index 0 — ID 1026 — 16 samples — loop")
        self.assertEqual(animation_label(self.playback.clips[43]), "Index 43 — ID 1069 — 76 samples — non-loop")

    def test_slider_preserves_fractional_sample_positions(self) -> None:
        self.playback.set_time(7.501)
        self.assertEqual(self.playback.slider_from_time(), 7501)
        self.assertEqual(self.playback.time_from_slider(7501), 7.501)
        pose = evaluate_boy_scene(self.boy, animation_index=0, time=7.501).pose
        self.assertEqual(pose.time, 7.501)
        self.assertNotEqual(pose.fraction_10bit, 0)

    def test_loop_playback_wraps_in_existing_runtime_domain(self) -> None:
        self.playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        self.playback.set_time(15.75)
        self.playback.play()
        self.playback.advance(0.5)
        self.assertAlmostEqual(self.playback.time, 0.25)
        self.assertTrue(self.playback.playing)

    def test_nonloop_playback_clamps_and_stops_at_final_sample(self) -> None:
        self.playback.select(43)
        self.playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        self.playback.set_time(74.75)
        self.playback.play()
        self.playback.advance(1.0)
        self.assertEqual(self.playback.time, 75.0)
        self.assertFalse(self.playback.playing)

    def test_single_movement_speed_control_changes_progression(self) -> None:
        self.assertEqual(SUPPORTED_SPEEDS, tuple(value / 10 for value in range(10, 51)))
        self.assertEqual(
            [movement_speed_label(speed) for speed in (1.0, 2.7, 5.0)],
            ["1.0", "2.7", "5.0"],
        )
        self.playback.set_movement_speed(4.0)
        self.playback.play()
        self.playback.advance(0.25)
        self.assertAlmostEqual(self.playback.time, 14.4)
        self.assertEqual(self.playback.clip.animation_index, 0)

    def test_switching_and_stop_reset_time_and_playback(self) -> None:
        self.playback.set_time(4.25)
        self.playback.play()
        self.playback.select(43)
        self.assertEqual((self.playback.animation_index, self.playback.time, self.playback.playing), (43, 0.0, True))
        self.playback.set_time(12.5)
        self.playback.stop()
        self.assertEqual((self.playback.time, self.playback.playing), (0.0, False))

    def test_switching_while_paused_preserves_paused_state_and_speed(self) -> None:
        self.playback.set_movement_speed(2.7)
        self.playback.set_time(3.0)
        self.playback.select(1)
        self.assertEqual(
            (self.playback.time, self.playback.playing, self.playback.movement_speed),
            (0.0, False, 2.7),
        )

    def test_previous_next_navigation_wraps_at_catalog_boundaries(self) -> None:
        self.assertEqual(self.playback.adjacent_index(-1), 51)
        self.playback.select_previous()
        self.assertEqual(self.playback.animation_index, 51)
        self.assertEqual(self.playback.adjacent_index(1), 0)
        self.playback.select_next()
        self.assertEqual(self.playback.animation_index, 0)

    def test_reference_clip_keeps_technical_identity(self) -> None:
        self.assertIsNone(self.playback.reference_clip)
        self.playback.select(19)
        self.playback.mark_reference()
        self.playback.select(43)
        self.assertEqual(self.playback.reference_clip.animation_index, 19)
        self.assertEqual(self.playback.reference_clip.animation_id, 1022)


class AnimationBrowserMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)
        cls.entries = browser_entries(cls.boy.animations)

    def test_all_52_entries_expose_catalog_metadata(self) -> None:
        self.assertEqual(tuple(entry.animation_index for entry in self.entries), tuple(range(52)))
        self.assertTrue(all(entry.sample_stride_bytes >= 0 for entry in self.entries))
        self.assertTrue(all(len(entry.root_widths_xyz) == 3 for entry in self.entries))
        self.assertEqual(self.entries[0].root_widths_xyz, (0, 3, 0))
        self.assertEqual(self.entries[43].root_widths_xyz, (5, 1, 7))

    def test_context_mapping_contains_only_research_verified_indices(self) -> None:
        self.assertEqual(set(VERIFIED_GAMEPLAY_CONTEXTS), {0, 1, 3, 9, 10, 16, 17, 18, 19, 43})
        for index in VERIFIED_GAMEPLAY_CONTEXTS:
            self.assertEqual(research_context(index).status.value, "VERIFIED")
            self.assertNotEqual(research_context(index).text, UNKNOWN_CONTEXT)
        self.assertEqual(research_context(2).status.value, "UNKNOWN")
        self.assertEqual(research_context(2).text, UNKNOWN_CONTEXT)

    def test_sample_display_uses_actual_decoder_indices_and_fraction(self) -> None:
        pose = evaluate_boy_scene(self.boy, animation_index=0, time=7.5).pose
        display = sample_display(pose)
        self.assertEqual((display.current_sample, display.next_sample), (7, 8))
        self.assertEqual(display.fraction_10bit, 512)
        self.assertEqual(display.fraction, 0.5)

        endpoint = sample_display(evaluate_boy_scene(self.boy, animation_index=43, time=75.0).pose)
        self.assertEqual((endpoint.current_sample, endpoint.next_sample, endpoint.fraction_10bit), (75, 75, 0))


if __name__ == "__main__":
    unittest.main()
