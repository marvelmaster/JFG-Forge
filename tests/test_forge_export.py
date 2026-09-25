from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_forge.export_service import (
    ExportOperation,
    _retime_animation,
    _resolve_image_source,
    export_boy,
    suggested_filename,
)
from jfg_forge.playback import PlaybackController
from jfg_forge.runtime_timing import PlaybackTimingContext
from jfg_re.boy_rig_gltf import (
    FLOAT_TOLERANCE,
    _image_uri,
    validate_gltf_binary_layout,
)
from jfg_re.forge_data import load_boy, load_boy_attachment


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
PROPS = BOY.parent
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class ForgeExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def _load_export(self, destination: Path) -> tuple[dict, bytes]:
        gltf = json.loads(destination.read_text(encoding="utf-8"))
        binary = (destination.parent / gltf["buffers"][0]["uri"]).read_bytes()
        return gltf, binary

    @staticmethod
    def _float_vec2_accessor(gltf: dict, binary: bytes, accessor_index: int) -> tuple[tuple[float, float], ...]:
        accessor = gltf["accessors"][accessor_index]
        view = gltf["bufferViews"][accessor["bufferView"]]
        assert accessor["componentType"] == 5126 and accessor["type"] == "VEC2"
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        values = struct.unpack_from("<" + "f" * (accessor["count"] * 2), binary, offset)
        return tuple(zip(values[0::2], values[1::2]))

    def test_suggested_filenames_are_safe_deterministic_technical_names(self) -> None:
        clip = self.boy.animation(19)
        self.assertEqual(suggested_filename(ExportOperation.MODEL), "Boy_Prop220.gltf")
        self.assertEqual(
            suggested_filename(ExportOperation.CURRENT_ANIMATION, clip),
            "Boy_anim_19_ID1022.gltf",
        )
        self.assertEqual(
            suggested_filename(ExportOperation.MODEL_AND_CURRENT_ANIMATION, clip),
            "Boy_Prop220_anim_19_ID1022.gltf",
        )

    def test_model_export_has_mesh_skin_materials_and_standalone_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(ExportOperation.MODEL)
            result = export_boy(self.boy, destination, ExportOperation.MODEL)
            gltf, binary = self._load_export(destination)
            validation = validate_gltf_binary_layout(gltf, binary)

            self.assertTrue(validation["all_accessors_valid"])
            self.assertEqual(len(gltf["meshes"]), 1)
            self.assertEqual(sum(item["extras"]["face_count"] for item in gltf["meshes"][0]["primitives"]), 502)
            self.assertEqual(len(gltf["skins"][0]["joints"]), 21)
            self.assertEqual(gltf["animations"], [])
            self.assertEqual(len(gltf["images"]), 14)
            self.assertTrue(all((destination.parent / image["uri"]).is_file() for image in gltf["images"]))
            self.assertTrue(result.mesh_included)
            self.assertEqual(result.animation_count, 0)
            self.assertIsNone(result.attachment_slot)
            self.assertIsNone(result.attachment_prop_id)
            self.assertTrue(all(
                sampler["magFilter"] == 9729 and sampler["minFilter"] == 9729
                for sampler in gltf["samplers"]
            ))

    def test_gltf_texcoords_flip_only_v_from_verified_render_mesh_convention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(ExportOperation.MODEL)
            export_boy(self.boy, destination, ExportOperation.MODEL)
            gltf, binary = self._load_export(destination)

            checked = 0
            saw_non_symmetric_v = False
            for gltf_primitive, render_primitive in zip(
                gltf["meshes"][0]["primitives"],
                self.boy.model.render_mesh.primitives,
                strict=True,
            ):
                texcoord_accessor = gltf_primitive["attributes"].get("TEXCOORD_0")
                if texcoord_accessor is None:
                    continue
                exported = self._float_vec2_accessor(gltf, binary, texcoord_accessor)
                first = render_primitive.first_index
                source = self.boy.model.render_mesh.vertices[
                    first : first + render_primitive.index_count
                ]
                self.assertEqual(len(exported), len(source))
                texture = self.boy.model.textures[render_primitive.texture_index]
                assert texture.height is not None
                for gltf_uv, vertex in zip(exported, source, strict=True):
                    assert vertex.uv is not None
                    self.assertAlmostEqual(gltf_uv[0], vertex.uv[0], places=6)
                    self.assertAlmostEqual(gltf_uv[1], 1.0 - vertex.uv[1], places=6)
                    self.assertAlmostEqual(
                        gltf_uv[1],
                        vertex.raw_st[1] / (32 * texture.height),
                        places=6,
                    )
                    saw_non_symmetric_v |= abs(vertex.uv[1] - gltf_uv[1]) > 1e-6
                    checked += 1
            self.assertEqual(checked, 478 * 3)
            self.assertTrue(saw_non_symmetric_v)

    def test_cross_drive_image_uri_falls_back_to_file_uri(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "texture with spaces.png"
            source.write_bytes(b"PNG fixture")
            with patch(
                "jfg_re.boy_rig_gltf.os.path.relpath",
                side_effect=ValueError("path is on mount 'C:', start on mount 'D:'"),
            ):
                uri = _image_uri(source, Path(temporary) / "output")
            self.assertTrue(uri.startswith("file:"))
            self.assertEqual(_resolve_image_source(Path(temporary), uri), source.resolve())

    def test_bpistol_export_is_rigid_child_of_joint_6_and_preserves_attachment_uvs(self) -> None:
        attachment = load_boy_attachment(self.boy, slot=0, props_dir=PROPS)
        clip = self.boy.animation(0)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(
                ExportOperation.MODEL_AND_CURRENT_ANIMATION,
                clip,
            )
            result = export_boy(
                self.boy,
                destination,
                ExportOperation.MODEL_AND_CURRENT_ANIMATION,
                animation_index=clip.animation_index,
                attachment=attachment,
            )
            gltf, binary = self._load_export(destination)
            self.assertTrue(validate_gltf_binary_layout(gltf, binary)["all_accessors_valid"])
            self.assertEqual((result.attachment_slot, result.attachment_prop_id), (0, 301))
            self.assertEqual(len(gltf["meshes"]), 2)
            attachment_mesh = gltf["meshes"][1]
            self.assertEqual(attachment_mesh["name"], "BoyGun_slot0_Prop301_BPistol")
            self.assertEqual(
                sum(item["extras"]["face_count"] for item in attachment_mesh["primitives"]),
                67,
            )

            attachment_node_index = gltf["extras"]["boygun_attachment"]["node"]
            attachment_node = gltf["nodes"][attachment_node_index]
            joint6_index = next(
                index for index, node in enumerate(gltf["nodes"])
                if node.get("name") == "jfg_node_06"
            )
            self.assertIn(attachment_node_index, gltf["nodes"][joint6_index]["children"])
            self.assertEqual(
                attachment_node["matrix"],
                [
                    1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    0.0, 0.0, 0.0, 1.0,
                ],
            )
            self.assertNotIn("skin", attachment_node)
            self.assertEqual([item["name"] for item in gltf["animations"]], ["anim_00_ID1026"])
            for primitive in attachment_mesh["primitives"]:
                self.assertNotIn("JOINTS_0", primitive["attributes"])
                self.assertNotIn("WEIGHTS_0", primitive["attributes"])
            attachment_materials = [
                gltf["materials"][primitive["material"]]
                for primitive in attachment_mesh["primitives"]
            ]
            self.assertTrue(any(
                material["extras"]["texture_status"] == "VERIFIED RGBA16"
                for material in attachment_materials
            ))
            self.assertTrue(any(
                material["extras"]["texture_status"] == "UNKNOWN FORMAT"
                for material in attachment_materials
            ))

            checked = 0
            for gltf_primitive, render_primitive in zip(
                attachment_mesh["primitives"],
                attachment.model.render_mesh.primitives,
                strict=True,
            ):
                accessor = gltf_primitive["attributes"].get("TEXCOORD_0")
                if accessor is None:
                    continue
                exported = self._float_vec2_accessor(gltf, binary, accessor)
                first = render_primitive.first_index
                source = attachment.model.render_mesh.vertices[
                    first : first + render_primitive.index_count
                ]
                for gltf_uv, vertex in zip(exported, source, strict=True):
                    assert vertex.uv is not None
                    self.assertAlmostEqual(gltf_uv[0], vertex.uv[0], places=6)
                    self.assertAlmostEqual(gltf_uv[1], 1.0 - vertex.uv[1], places=6)
                    checked += 1
            self.assertGreater(checked, 0)

            image_uris = [image["uri"] for image in gltf["images"]]
            self.assertEqual(len(image_uris), len(set(image_uris)))
            self.assertTrue(all((destination.parent / uri).is_file() for uri in image_uris))
            self.assertEqual(
                sum("BoyGun_slot0_Prop301_BPistol" in uri for uri in image_uris),
                2,
            )
            self.assertTrue(all(
                sampler["magFilter"] == 9729 and sampler["minFilter"] == 9729
                for sampler in gltf["samplers"]
            ))

    def test_junohand_model_export_has_verified_32_face_attachment(self) -> None:
        attachment = load_boy_attachment(self.boy, slot=8, props_dir=PROPS)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(ExportOperation.MODEL)
            result = export_boy(
                self.boy,
                destination,
                ExportOperation.MODEL,
                attachment=attachment,
            )
            gltf, binary = self._load_export(destination)
            self.assertTrue(validate_gltf_binary_layout(gltf, binary)["all_accessors_valid"])
            self.assertEqual((result.attachment_slot, result.attachment_prop_id), (8, 309))
            self.assertEqual(gltf["meshes"][1]["name"], "BoyGun_slot8_Prop309_JunoHand")
            self.assertEqual(
                sum(item["extras"]["face_count"] for item in gltf["meshes"][1]["primitives"]),
                32,
            )
            attachment_node = gltf["nodes"][gltf["extras"]["boygun_attachment"]["node"]]
            self.assertEqual(attachment_node["extras"]["attachment_joint_id"], 6)
            self.assertEqual(attachment_node["extras"]["local_transform"], "identity")

    def test_current_animation_export_uses_preview_timing_context(self) -> None:
        clip = self.boy.animation(19)
        timing_context = PlaybackTimingContext(movement_speed=2.7)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(ExportOperation.CURRENT_ANIMATION, clip)
            result = export_boy(
                self.boy,
                destination,
                ExportOperation.CURRENT_ANIMATION,
                animation_index=clip.animation_index,
                timing_context=timing_context,
            )
            gltf, binary = self._load_export(destination)
            validation = validate_gltf_binary_layout(gltf, binary, require_skin=False)

            self.assertTrue(validation["all_accessors_valid"])
            self.assertNotIn("meshes", gltf)
            self.assertNotIn("skins", gltf)
            self.assertEqual(len(gltf["nodes"]), 22)
            self.assertEqual(len(gltf["animations"]), 1)
            action = gltf["animations"][0]
            self.assertEqual(action["name"], "anim_19_ID1022")
            extras = dict(action["extras"])
            exported_rate = extras.pop("effective_samples_per_second")
            self.assertAlmostEqual(exported_rate, 31.59)
            self.assertEqual(
                extras,
                {
                    "animation_id": 1022,
                    "bake": "STEP at every MIPS 10-bit round-to-nearest-even state transition",
                    "boy_animation_index": 19,
                    "loop": clip.loop,
                    "movement_speed": 2.7,
                    "state_timing_flag": False,
                    "time_unit": "seconds using the exported Forge preview timing context",
                    "timing_mode": "Game Timing",
                },
            )
            time_accessor = gltf["accessors"][action["samplers"][0]["input"]]
            span = float(clip.sample_count if clip.loop else clip.sample_count - 1)
            expected_end = span / 31.59
            self.assertEqual(time_accessor["min"], [0.0])
            self.assertAlmostEqual(time_accessor["max"][0], expected_end)
            self.assertEqual(len(action["channels"]), 22)
            self.assertFalse(result.mesh_included)
            self.assertLessEqual(result.maximum_position_error, FLOAT_TOLERANCE)
            self.assertAlmostEqual(result.effective_samples_per_second, 31.59)
            self.assertAlmostEqual(result.animation_duration_seconds, expected_end)

    def test_model_and_current_animation_combines_valid_mesh_skin_and_one_action(self) -> None:
        clip = self.boy.animation(0)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / suggested_filename(
                ExportOperation.MODEL_AND_CURRENT_ANIMATION,
                clip,
            )
            result = export_boy(
                self.boy,
                destination,
                ExportOperation.MODEL_AND_CURRENT_ANIMATION,
                animation_index=clip.animation_index,
            )
            gltf, binary = self._load_export(destination)

            self.assertTrue(validate_gltf_binary_layout(gltf, binary)["all_accessors_valid"])
            self.assertEqual(len(gltf["meshes"]), 1)
            self.assertEqual(len(gltf["skins"][0]["joints"]), 21)
            self.assertEqual([item["name"] for item in gltf["animations"]], ["anim_00_ID1026"])
            self.assertEqual((result.animation_index, result.animation_id), (0, 1026))
            self.assertAlmostEqual(result.effective_samples_per_second, 14.4)
            self.assertAlmostEqual(result.animation_duration_seconds, 16 / 14.4)
            self.assertLessEqual(result.maximum_position_error, FLOAT_TOLERANCE)

    def test_retimed_export_matches_preview_for_all_dynamic_categories(self) -> None:
        cases = (
            (43, PlaybackTimingContext(movement_speed=1.0)),
            (43, PlaybackTimingContext(movement_speed=2.7)),
            (0, PlaybackTimingContext(movement_speed=1.0)),
            (0, PlaybackTimingContext(movement_speed=4.0)),
            (9, PlaybackTimingContext(movement_speed=2.7)),
            (13, PlaybackTimingContext(movement_speed=2.7, state_timing_flag=False)),
            (13, PlaybackTimingContext(movement_speed=2.7, state_timing_flag=True)),
        )
        for animation_index, context in cases:
            with self.subTest(animation_index=animation_index, context=context):
                clip = self.boy.animation(animation_index)
                span = float(clip.sample_count if clip.loop else clip.sample_count - 1)
                source_times = (0.0, span / 2.0, span)
                binary = struct.pack("<fff", *source_times)
                gltf = {
                    "animations": [{
                        "samplers": [{"input": 0, "output": 1, "interpolation": "STEP"}],
                        "extras": {},
                    }],
                    "accessors": [
                        {"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR"},
                        {"bufferView": 1, "componentType": 5126, "count": 0, "type": "VEC4"},
                    ],
                    "bufferViews": [
                        {"buffer": 0, "byteOffset": 0, "byteLength": len(binary)},
                        {"buffer": 0, "byteOffset": len(binary), "byteLength": 0},
                    ],
                }
                retimed, rate, duration = _retime_animation(gltf, binary, clip, context)
                exported_times = struct.unpack("<fff", retimed)
                preview = PlaybackController(self.boy.animations, initial_index=animation_index)
                preview.set_timing_mode(context.timing_mode)
                preview.set_movement_speed(context.movement_speed)
                preview.set_state_timing_flag(context.state_timing_flag)
                self.assertAlmostEqual(rate, preview.effective_samples_per_second)
                self.assertAlmostEqual(duration, span / preview.effective_samples_per_second)
                self.assertAlmostEqual(exported_times[-1], duration, places=5)

        # Index 0 at movement 4.0 is 14.4 * 4, not a double-applied 14.4 * 16.
        self.assertAlmostEqual(cases[3][1].effective_samples_per_second(self.boy.animation(0)), 57.6)


if __name__ == "__main__":
    unittest.main()
