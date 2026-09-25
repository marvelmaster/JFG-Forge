from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_anim0_frame0 import _transform, build_matrices
from jfg_re.boy_anim0_temporal import decode_time as decode_animation0_time
import jfg_re.boy_animation_catalog as animation_catalog
from jfg_re.forge_data import load_boy
from jfg_re.forge_scene import (
    evaluate_attachment_positions,
    evaluate_boy_scene,
    evaluate_rigid_mesh_positions,
)
from jfg_re.forge_types import EvidenceStatus


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
PROPS = BOY.parent
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
FLOAT_TOLERANCE = 1e-4


@dataclass(frozen=True)
class _ReferencePoint:
    x: float
    y: float
    z: float


class ForgeSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def test_animation0_scene_without_attachment(self) -> None:
        scene = evaluate_boy_scene(self.boy, animation_index=0, time=7.5)
        self.assertEqual(scene.model.active_face_count, 502)
        self.assertEqual(len(scene.model.render_mesh.vertices), 1506)
        self.assertEqual(len(scene.pose.joints), 21)
        self.assertEqual(len(scene.joint_world_matrices), 21)
        self.assertEqual(len(scene.skeleton_debug.joints), 21)
        self.assertEqual(len(scene.skeleton_debug.edges), 20)
        self.assertIsNone(scene.attachment)

    def test_animation0_scene_with_bpistol_socket(self) -> None:
        scene = evaluate_boy_scene(
            self.boy,
            animation_index=0,
            time=7.5,
            attachment_slot=0,
            props_dir=PROPS,
        )
        attachment = scene.attachment
        self.assertEqual(attachment.parent_joint_id, 6)
        self.assertEqual((attachment.attachment.slot.slot, attachment.attachment.model.prop_id), (0, 301))
        self.assertEqual(attachment.attachment.model.active_face_count, 67)
        self.assertEqual(attachment.socket_world_matrix, scene.pose.joints[6].world_matrix)
        self.assertEqual(
            attachment.local_transform,
            (
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
        )
        self.assertEqual(attachment.final_world_transform, scene.pose.joints[6].world_matrix)
        self.assertIs(attachment.transform_status, EvidenceStatus.VERIFIED)
        self.assertTrue(attachment.exact_transform_available)
        positions = evaluate_attachment_positions(attachment)
        self.assertEqual(len(positions), 67 * 3)
        first, _ = _transform(
            _ReferencePoint(*attachment.attachment.model.render_mesh.vertices[0].position),
            scene.pose.joints[6].world_matrix,
        )
        self.assertEqual(positions[0], tuple(first))

    def test_animation43_scene_with_junohand_socket(self) -> None:
        scene = evaluate_boy_scene(
            self.boy,
            animation_index=43,
            time=37.5,
            attachment_slot=8,
            props_dir=PROPS,
        )
        attachment = scene.attachment
        self.assertEqual(scene.pose.animation_id, 1069)
        self.assertEqual(attachment.parent_joint_id, 6)
        self.assertEqual((attachment.attachment.slot.slot, attachment.attachment.model.prop_id), (8, 309))
        self.assertEqual(attachment.attachment.model.active_face_count, 32)
        self.assertEqual(attachment.socket_world_matrix, scene.pose.joints[6].world_matrix)
        self.assertEqual(attachment.final_world_transform, scene.pose.joints[6].world_matrix)
        self.assertIs(attachment.transform_status, EvidenceStatus.VERIFIED)
        self.assertEqual(len(evaluate_attachment_positions(attachment)), 32 * 3)

    def test_attachment_and_boy_share_one_sampled_pose(self) -> None:
        scene = evaluate_boy_scene(
            self.boy,
            animation_index=19,
            time=30.41998291015625,
            attachment_slot=0,
            props_dir=PROPS,
        )
        self.assertIs(scene.attachment.socket_world_matrix, scene.pose.joints[6].world_matrix)
        self.assertEqual(scene.joint_world_matrices[6], scene.attachment.final_world_transform)

    def test_cpu_positions_match_existing_verified_transform_path(self) -> None:
        maximum_error = 0.0
        for animation_index, time_value in ((0, 7.5), (43, 37.5)):
            scene = evaluate_boy_scene(self.boy, animation_index=animation_index, time=time_value)
            actual = evaluate_rigid_mesh_positions(scene.model.render_mesh, scene.pose)
            clip = self.boy.animation(animation_index)
            frame = (
                decode_animation0_time(clip.blob, time_value)
                if animation_index == 0
                else animation_catalog.decode_animation_time(clip.blob, time_value)
            )
            records = build_matrices(self.boy.raw_prop, frame, self.boy.raw_rom, list(clip.channel_map))
            matrices = {record["matrix_id"]: record["world_model_matrix"] for record in records}
            for render_vertex, position in zip(scene.model.render_mesh.vertices, actual):
                reference, _ = _transform(_ReferencePoint(*render_vertex.position), matrices[render_vertex.joint_id])
                maximum_error = max(maximum_error, math.dist(position, reference))
        self.assertLessEqual(maximum_error, FLOAT_TOLERANCE)

    def test_skeleton_debug_positions_are_pose_translations(self) -> None:
        scene = evaluate_boy_scene(self.boy, animation_index=43, time=37.5)
        self.assertEqual(
            [joint.position for joint in scene.skeleton_debug.joints],
            [tuple(joint.world_matrix[3][:3]) for joint in scene.pose.joints],
        )
        for edge in scene.skeleton_debug.edges:
            self.assertEqual(edge.start, scene.skeleton_debug.joints[edge.parent_joint_id].position)
            self.assertEqual(edge.end, scene.skeleton_debug.joints[edge.child_joint_id].position)


if __name__ == "__main__":
    unittest.main()
