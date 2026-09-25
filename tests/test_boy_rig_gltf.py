from __future__ import annotations

import json
import copy
import struct
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_export import BoyExportError
from jfg_re.boy_rig_gltf import FLOAT_TOLERANCE, _bake_states, build_rig_artifacts, validate_gltf_binary_layout


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
OUTPUT = PROJECT_ROOT / "data" / "generated" / "boy-rig-test-not-created"


class BoyRigGltfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = build_rig_artifacts(BOY.read_bytes(), ROM.read_bytes(), MANIFEST, OUTPUT)
        cls.gltf = json.loads(cls.artifacts["boy-rig-validation.gltf"])
        cls.report = json.loads(cls.artifacts["boy-rig-validation-report.json"])

    def test_complete_10bit_step_grids(self) -> None:
        self.assertEqual(len(_bake_states(16, True)), 16386)
        self.assertEqual(len(_bake_states(76, False)), 76802)
        self.assertEqual(self.report["animations"][0]["baked_state_count"], 16386)
        self.assertEqual(self.report["animations"][1]["baked_state_count"], 76802)

    def test_technical_skin_has_21_identity_inverse_binds_and_stable_names(self) -> None:
        self.assertEqual(len(self.gltf["skins"]), 1)
        self.assertEqual(len(self.gltf["skins"][0]["joints"]), 21)
        self.assertEqual([node["name"] for node in self.gltf["nodes"][1:]], [f"jfg_node_{i:02d}" for i in range(21)])
        self.assertIn("TECHNICAL REPRESENTATION", self.gltf["skins"][0]["extras"]["status"])

    def test_every_accessor_span_is_readable_and_inverse_bind_is_1344_bytes(self) -> None:
        binary = self.artifacts["boy-rig-validation.bin"]
        validation = validate_gltf_binary_layout(self.gltf, binary)
        self.assertTrue(validation["all_accessors_valid"])
        self.assertEqual(validation["accessor_count"], len(self.gltf["accessors"]))
        inverse = validation["inverse_bind_accessor"]
        self.assertEqual((inverse["count"], inverse["type"], inverse["component_type"]), (21, "MAT4", 5126))
        self.assertEqual(inverse["required_bytes"], 21 * 16 * 4)
        self.assertGreaterEqual(inverse["buffer_view_byte_length"], inverse["required_bytes"])
        start = inverse["absolute_start"]
        values = struct.unpack_from("<" + "f" * (21 * 16), binary, start)
        identity = (1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    0.0, 0.0, 0.0, 1.0)
        self.assertEqual(values, identity * 21)

    def test_original_1260_byte_inverse_bind_regression_is_rejected(self) -> None:
        broken = copy.deepcopy(self.gltf)
        inverse_index = broken["skins"][0]["inverseBindMatrices"]
        view_index = broken["accessors"][inverse_index]["bufferView"]
        broken["bufferViews"][view_index]["byteLength"] = 21 * 15 * 4
        with self.assertRaisesRegex(BoyExportError, "requires 1344 bytes"):
            validate_gltf_binary_layout(broken, self.artifacts["boy-rig-validation.bin"])

    def test_accessor_offset_overrun_is_rejected(self) -> None:
        broken = copy.deepcopy(self.gltf)
        broken["accessors"][0]["byteOffset"] = broken["bufferViews"][0]["byteLength"]
        with self.assertRaisesRegex(BoyExportError, "requires .* bytes"):
            validate_gltf_binary_layout(broken, self.artifacts["boy-rig-validation.bin"])

    def test_buffer_view_overrun_is_rejected(self) -> None:
        broken = copy.deepcopy(self.gltf)
        view = broken["bufferViews"][0]
        view["byteOffset"] = len(self.artifacts["boy-rig-validation.bin"])
        with self.assertRaisesRegex(BoyExportError, "reads beyond"):
            validate_gltf_binary_layout(broken, self.artifacts["boy-rig-validation.bin"])

    def test_invalid_stride_and_alignment_are_rejected(self) -> None:
        broken_stride = copy.deepcopy(self.gltf)
        broken_stride["bufferViews"][0]["byteStride"] = 2
        with self.assertRaisesRegex(BoyExportError, "invalid byteStride"):
            validate_gltf_binary_layout(broken_stride, self.artifacts["boy-rig-validation.bin"])
        broken_alignment = copy.deepcopy(self.gltf)
        broken_alignment["bufferViews"][0]["byteOffset"] += 1
        with self.assertRaisesRegex(BoyExportError, "misaligned"):
            validate_gltf_binary_layout(broken_alignment, self.artifacts["boy-rig-validation.bin"])

    def test_only_two_actions_and_step_interpolation(self) -> None:
        self.assertEqual([item["name"] for item in self.gltf["animations"]], ["boy_anim_00_id_1026", "boy_anim_43_id_1069"])
        self.assertTrue(all(sampler["interpolation"] == "STEP" for animation in self.gltf["animations"] for sampler in animation["samplers"]))

    def test_geometry_is_rigid_and_preserves_counts(self) -> None:
        self.assertEqual(self.report["geometry"]["active_source_vertices"], 638)
        self.assertEqual(self.report["geometry"]["faces"], 502)
        self.assertEqual(self.report["geometry"]["render_corner_vertices"], 1506)
        self.assertEqual(self.report["representation"]["skin"], "one joint per render vertex; WEIGHTS_0 exactly [1,0,0,0]")

    def test_all_ten_reference_times_are_within_float_tolerance(self) -> None:
        summary = self.report["validation_summary"]
        self.assertEqual(len(self.report["validation_times"]), 10)
        self.assertEqual(summary["vertices_compared"], 6380)
        self.assertEqual(summary["within_tolerance"], 6380)
        self.assertLessEqual(summary["maximum_position_error"], FLOAT_TOLERANCE)


if __name__ == "__main__":
    unittest.main()
