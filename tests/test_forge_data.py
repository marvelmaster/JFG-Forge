from __future__ import annotations

from pathlib import Path
import math
import struct
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import jfg_re.boy_animation_catalog as animation_catalog
from jfg_re.boy_anim0_frame0 import _matrix_multiply, build_matrices
from jfg_re.boy_anim0_temporal import decode_time as decode_animation0_time
from jfg_re.boy_transform_analysis import build_transform_analysis
from jfg_re.boy_runtime_capture import unpack_runtime_matrices
from jfg_re.forge_data import BOYGUN_ATTACHMENT, load_boy, load_boy_attachment, sample_animation
from jfg_re.forge_types import EvidenceStatus


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
PROPS = BOY.parent
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
INDEX19_CAPTURE = PROJECT_ROOT / "research" / "boy" / "runtime-captures" / "index19-id1022"


class ForgeDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def test_boy_model_is_renderer_neutral_and_complete(self) -> None:
        model = self.boy.model
        self.assertEqual((model.prop_id, model.name), (220, "Boy"))
        self.assertEqual(len(model.source_vertices), 660)
        self.assertEqual(len(model.groups), 82)
        self.assertEqual(model.active_face_count, 502)
        self.assertEqual(len(model.render_mesh.vertices), 1506)
        self.assertEqual(model.render_mesh.indices, tuple(range(1506)))
        self.assertEqual(len(model.skeleton.joints), 21)
        self.assertEqual(sum(texture.supported for texture in model.textures), 14)
        self.assertEqual(sum(texture.status is EvidenceStatus.UNKNOWN for texture in model.textures), 4)
        self.assertEqual(sum(vertex.uv is not None for vertex in model.render_mesh.vertices), 478 * 3)
        for texture in model.textures:
            if texture.supported:
                self.assertEqual(len(texture.rgba), texture.width * texture.height * 4)
                self.assertEqual(texture.decoder_id, "rgba16-blockswap-v1")
            else:
                self.assertIsNone(texture.rgba)

    def test_skeleton_matches_existing_transform_analysis(self) -> None:
        reference = build_transform_analysis(self.boy.raw_prop)["transform_records"]
        joints = self.boy.model.skeleton.joints
        self.assertEqual([joint.joint_id for joint in joints], list(range(21)))
        self.assertEqual(
            [joint.parent_id for joint in joints],
            [None if record["parent_id"] == 0xFF else record["parent_id"] for record in reference],
        )
        self.assertEqual(
            [joint.static_local_translation for joint in joints],
            [tuple(record["local_translation_xyz"]) for record in reference],
        )

    def test_reference_animation_samples_match_existing_decoders_and_matrices(self) -> None:
        times = {
            0: (0.0, 1.0, 7.5, 8.0, 15.0),
            43: (0.0, 1.0, 37.0, 37.5, 75.0),
        }
        self.assertEqual(self.boy.animation(0).animation_id, 1026)
        self.assertEqual(self.boy.animation(43).animation_id, 1069)
        for animation_index, sample_times in times.items():
            clip = self.boy.animation(animation_index)
            for time_value in sample_times:
                pose = sample_animation(self.boy, animation_index, time_value)
                reference_frame = (
                    decode_animation0_time(clip.blob, time_value)
                    if animation_index == 0
                    else animation_catalog.decode_animation_time(clip.blob, time_value)
                )
                reference_matrices = build_matrices(
                    self.boy.raw_prop,
                    reference_frame,
                    self.boy.raw_rom,
                    list(clip.channel_map),
                )
                self.assertEqual(pose.root_translation, tuple(reference_frame["root_translation_model_xyz"]))
                self.assertEqual(pose.root_translation_raw_q10, tuple(reference_frame["root_translation_raw_q10_xyz"]))
                self.assertEqual(
                    [joint.world_matrix for joint in pose.joints],
                    [tuple(tuple(row) for row in record["world_model_matrix"]) for record in reference_matrices],
                )

    def test_index19_production_pose_uses_runtime_verified_component_order(self) -> None:
        instance = (INDEX19_CAPTURE / "instance_n64.bin").read_bytes()
        effective_time = struct.unpack_from(">f", instance, 0x28)[0]
        pose = sample_animation(self.boy, 19, effective_time)
        object_values = struct.unpack(">16f", (INDEX19_CAPTURE / "object_matrix_n64.bin").read_bytes())
        object_matrix = [list(object_values[row * 4 : row * 4 + 4]) for row in range(4)]
        captured, _, _ = unpack_runtime_matrices((INDEX19_CAPTURE / "matrices_n64.bin").read_bytes())

        # The only captured selector targets joint 11, so matrices 0..10 are
        # an independent oracle for sample_animation + object composition.
        maximum_error = 0.0
        for joint in pose.joints[:11]:
            composed = _matrix_multiply([list(row) for row in joint.world_matrix], object_matrix)
            runtime = captured[joint.joint_id]
            maximum_error = max(
                maximum_error,
                *(abs(composed[row][column] - runtime[row][column]) for row in range(4) for column in range(3)),
            )
        self.assertTrue(math.isfinite(maximum_error))
        self.assertLessEqual(maximum_error, 1.0e-5)

    def test_boygun_metadata_and_required_models(self) -> None:
        self.assertEqual(BOYGUN_ATTACHMENT.attachment_joint_id, 6)
        self.assertEqual([slot.slot for slot in BOYGUN_ATTACHMENT.slots], list(range(9)))
        self.assertEqual([slot.prop_id for slot in BOYGUN_ATTACHMENT.slots], list(range(301, 310)))
        self.assertEqual(
            [slot.name for slot in BOYGUN_ATTACHMENT.slots],
            ["BPistol", "BAutomatic", "BUzi", "BUzi1", "BShrinkBeam", "BRocket", "BFlameThrower", "BSniper", "JunoHand"],
        )
        pistol = load_boy_attachment(self.boy, slot=0, props_dir=PROPS)
        hand = load_boy_attachment(self.boy, slot=8, props_dir=PROPS)
        self.assertEqual((pistol.model.prop_id, pistol.model.name, pistol.model.active_face_count), (301, "BPistol", 67))
        self.assertEqual((hand.model.prop_id, hand.model.name, hand.model.active_face_count), (309, "JunoHand", 32))
        self.assertIsNone(pistol.model.skeleton)
        self.assertIsNone(hand.model.skeleton)


if __name__ == "__main__":
    unittest.main()
