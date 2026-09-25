from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from jfg_forge.animation_browser import UNKNOWN_CONTEXT, browser_entries
from jfg_forge.export_service import ExportOperation, export_vela
from jfg_re.forge_scene import (
    evaluate_attachment_positions,
    evaluate_vela_scene,
)
from jfg_re.vela_data import load_vela, load_vela_attachment


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
PROP = PROJECT_ROOT / "data/generated/props-us-verified/bins/0218_Girl.bin"
PROPS = PROP.parent
MANIFEST = PROJECT_ROOT / "data/generated/rgba16-us-verified/textures-manifest.json"


@unittest.skipUnless(
    all(path.is_file() for path in (ROM, PROP, MANIFEST)),
    "Vela Forge regression requires ignored local ROM and extraction fixtures.",
)
class VelaForgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vela = load_vela(PROP, ROM, MANIFEST)

    def test_model_skeleton_textures_and_catalog(self) -> None:
        vela = self.vela
        self.assertEqual((vela.model.prop_id, vela.model.name), (218, "Girl"))
        self.assertEqual(len(vela.model.source_vertices), 588)
        self.assertEqual(vela.model.active_face_count, 452)
        self.assertEqual(sum(not group.runtime_skipped for group in vela.model.groups), 51)
        self.assertEqual(sum(group.runtime_skipped for group in vela.model.groups), 18)
        self.assertEqual(len(vela.model.skeleton.joints), 28)
        self.assertEqual(len(vela.animations), 53)
        self.assertEqual(len({clip.animation_id for clip in vela.animations}), 52)
        self.assertEqual(
            sum(bool(clip.metadata["runtime_scale_stream_count"]) for clip in vela.animations),
            35,
        )
        self.assertEqual(sum(texture.supported for texture in vela.model.textures), 14)
        self.assertEqual(sum(not texture.supported for texture in vela.model.textures), 2)
        self.assertEqual(len(vela.model.rigid_joint_assignments), 551)
        entries = browser_entries(vela.animations, include_boy_gameplay_context=False)
        self.assertTrue(all(entry.gameplay_context == UNKNOWN_CONTEXT for entry in entries))

    def test_reference_pose_matches_phase2_regression(self) -> None:
        scene = evaluate_vela_scene(self.vela, animation_index=0, time=7.5)
        pose = scene.pose
        self.assertEqual((pose.current_sample, pose.next_sample, pose.fraction_10bit), (7, 8, 512))
        self.assertEqual(pose.root_translation, (0.0, -5.5, 0.0))
        self.assertEqual((len(pose.joints), len(scene.skeleton_debug.edges)), (28, 27))
        self.assertTrue(all(math.isfinite(value) for joint in pose.joints for row in joint.world_matrix for value in row))
        payload = b"".join(
            struct.pack(">f", value)
            for joint in pose.joints
            for row in joint.world_matrix
            for value in row
        )
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "919427edd9f17c3dc11863406c422236057774980aefdb881c378edf603d2ca7",
        )
        matrix_by_id = {joint.joint_id: joint.world_matrix for joint in pose.joints}
        points = []
        for source, joint_id in self.vela.model.rigid_joint_assignments.items():
            xyz = self.vela.model.source_vertices[source].position
            matrix = matrix_by_id[joint_id]
            points.append(tuple(
                sum(float(xyz[row]) * matrix[row][column] for row in range(3)) + matrix[3][column]
                for column in range(3)
            ))
        minimum = tuple(min(point[axis] for point in points) for axis in range(3))
        maximum = tuple(max(point[axis] for point in points) for axis in range(3))
        self.assertEqual(len(points), 551)
        expected_min = (-30.4464168548584, -1.6986865997314453, -62.40933609008789)
        expected_max = (25.72008514404297, 206.2480010986328, 60.70246505737305)
        for actual, expected in zip(minimum + maximum, expected_min + expected_max):
            self.assertAlmostEqual(actual, expected, delta=1e-5)

    def test_girlgun_slots_follow_joint_6(self) -> None:
        self.assertEqual([slot.prop_id for slot in self.vela.attachment.slots], list(range(283, 292)))
        hand = load_vela_attachment(self.vela, slot=8, props_dir=PROPS)
        self.assertEqual((hand.model.name, hand.model.active_face_count), ("VelaHand", 32))
        scene = evaluate_vela_scene(
            self.vela,
            animation_index=0,
            time=7.5,
            loaded_attachment=hand,
        )
        self.assertEqual(scene.attachment.parent_joint_id, 6)
        self.assertEqual(scene.attachment.final_world_transform, pose_matrix(scene, 6))
        self.assertEqual(len(evaluate_attachment_positions(scene.attachment)), 96)

    def test_model_and_scale_animation_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_path = root / "Vela.gltf"
            hand = load_vela_attachment(self.vela, slot=8, props_dir=PROPS)
            model_result = export_vela(
                self.vela,
                model_path,
                ExportOperation.MODEL,
                attachment=hand,
            )
            model = json.loads(model_path.read_text(encoding="utf-8"))
            self.assertEqual(len(model["skins"][0]["joints"]), 28)
            self.assertEqual(sum(item["extras"]["face_count"] for item in model["meshes"][0]["primitives"]), 452)
            self.assertIn("UNKNOWN FORMAT", {item["extras"]["texture_status"] for item in model["materials"]})
            self.assertEqual(model["extras"]["girlgun_attachment"]["parent_joint_id"], 6)
            self.assertEqual(model_result.attachment_prop_id, 291)
            self.assertEqual(model_result.animation_count, 0)

            animation_path = root / "Vela_anim46.gltf"
            animation_result = export_vela(
                self.vela,
                animation_path,
                ExportOperation.CURRENT_ANIMATION,
                animation_index=46,
            )
            animation = json.loads(animation_path.read_text(encoding="utf-8"))["animations"][0]
            self.assertEqual(animation_result.animation_count, 1)
            self.assertTrue(animation["extras"]["scale_streams_preserved"])
            self.assertEqual(animation["extras"]["timing_mode"], "Game Timing")
            self.assertEqual(sum(channel["target"]["path"] == "scale" for channel in animation["channels"]), 28)


def pose_matrix(scene, joint_id: int):
    return next(joint.world_matrix for joint in scene.pose.joints if joint.joint_id == joint_id)


if __name__ == "__main__":
    unittest.main()
