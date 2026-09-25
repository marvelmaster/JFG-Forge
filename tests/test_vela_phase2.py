from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "research" / "vela" / "analyze_vela_phase2.py"
ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
PROP = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0218_Girl.bin"
PHASE1 = PROJECT_ROOT / "research" / "vela" / "phase1-structural-map.json"
REPORT = PROJECT_ROOT / "research" / "vela" / "phase2-runtime-map.json"


@unittest.skipUnless(
    all(path.is_file() for path in (ROM, PROP, PHASE1, REPORT)),
    "Vela Phase-2 regression requires ignored local ROM and canonical extraction fixtures.",
)
class VelaPhase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("analyze_vela_phase2", HELPER)
        if spec is None or spec.loader is None:
            raise AssertionError("Could not load Vela Phase-2 helper.")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.rom = ROM.read_bytes()
        cls.prop = PROP.read_bytes()
        cls.actual = cls.module.analyze(ROM, PROP, PHASE1)

    def test_catalog_and_channel_layout(self) -> None:
        catalog = self.actual["catalog"]
        self.assertEqual(catalog["counts"]["animations"], 53)
        self.assertEqual(catalog["counts"]["unique_animation_ids"], 52)
        self.assertEqual((catalog["counts"]["looping"], catalog["counts"]["non_looping"]), (28, 25))
        self.assertEqual(catalog["counts"]["with_runtime_scale_streams"], 35)
        self.assertEqual(catalog["counts"]["with_nonidentity_channel_map"], 1)
        self.assertEqual(catalog["counts"]["requiring_one_byte_contiguous_asset_lookahead"], 2)
        self.assertEqual(
            catalog["animation_ids_in_index_order"],
            [
                1097, 1098, 1099, 1096, 1104, 1110, 1111, 1112, 1109, 1113,
                1114, 1102, 1107, 1100, 1101, 1115, 1090, 1091, 1092, 1093,
                1094, 1095, 1121, 1106, 1141, 1119, 1120, 1124, 1123, 1125,
                1126, 1127, 1128, 1129, 1130, 1116, 1117, 1118, 1131, 1132,
                1133, 1124, 1134, 1135, 1137, 1136, 1138, 1139, 1140, 1122,
                1103, 1108, 1142,
            ],
        )
        reference = catalog["animations"][0]
        self.assertEqual((reference["animation_id"], reference["sample_count"]), (1097, 16))
        self.assertEqual((reference["sample_stride_bytes"], reference["transform_channel_slots"]), (37, 29))
        self.assertEqual((reference["runtime_decoded_channel_count"], reference["scratch_channel_index"]), (28, 28))
        self.assertEqual((reference["runtime_descriptor_count"], reference["serialized_descriptor_count"]), (84, 87))
        self.assertEqual(reference["runtime_scale_stream_scalar_indices"], [81, 82, 83])
        self.assertEqual(reference["channel_map"], list(range(26)) + [27, 28])
        self.assertEqual(
            [catalog["animations"][index]["cross_blob_lookahead_hex"] for index in (17, 22)],
            ["00", "00"],
        )

    def test_reference_interpolation_and_scratch_channel(self) -> None:
        blob, lookahead = self.module._animation_blob(self.rom, 1097)
        expected = {
            0.0: (0, 0, 0),
            1.0: (1, 1, 0),
            7.5: (7, 8, 512),
            8.0: (8, 8, 0),
            15.0: (15, 15, 0),
            15.5: (15, 0, 512),
        }
        for time_value, state in expected.items():
            frame = self.module.decode_vela_animation_time(blob, time_value, lookahead)
            self.assertEqual(
                (frame["current_sample"], frame["next_sample"], frame["fraction_10bit"]),
                state,
            )
            scratch = frame["channels"][28]
            self.assertEqual(scratch["rotation_raw_s16_abc"], [0, 0, 0])
            self.assertEqual(scratch["scale_raw_u16_xyz"], [0, 0, 0])
        with self.assertRaises(Exception):
            self.module.decode_vela_animation_time(blob, 16.0, lookahead)

    def test_pose_hierarchy_geometry_and_attachment(self) -> None:
        reference = self.actual["reference_animation"]
        matrices = reference["reference_time_7_5_world_matrices"]
        self.assertEqual(len(matrices), 28)
        self.assertEqual([item["matrix_id"] for item in matrices], list(range(28)))
        self.assertEqual([item["parent_id"] for item in matrices], [
            0xFF, 0, 1, 2, 3, 4, 5, 3, 7, 8, 2, 10, 10, 2,
            0, 14, 15, 16, 17, 18, 14, 20, 21, 22, 23, 24, 14, 14,
        ])
        self.assertTrue(all(sample["all_finite"] for sample in reference["pose_samples"]))
        self.assertEqual(
            {sample["transformed_referenced_vertex_count"] for sample in reference["pose_samples"]},
            {551},
        )
        geometry = self.actual["geometry_validation"]
        self.assertEqual((geometry["admitted_groups"], geometry["runtime_visible_faces"]), (51, 452))
        self.assertEqual(geometry["matrix_assignment_conflicts"], [])
        overlay = self.actual["runtime_evidence"]["girl_overlay"]
        self.assertEqual(overlay["modGenAnimMatrices_call"], "0x00F01740")
        self.assertEqual(overlay["objMakeGunMtx_call"], "0x00F01778")
        self.assertEqual(overlay["lightObject_call"], "0x00F017B0")
        self.assertEqual(
            self.actual["runtime_evidence"]["geometry"]["makeModelGfx_calls"],
            ["0x8003BF10", "0x8003BF58", "0x8003BF7C", "0x8003BFAC"],
        )
        girlgun = self.actual["runtime_evidence"]["girlgun"]
        self.assertEqual(girlgun["attachment_matrix_id"], 6)
        self.assertEqual(girlgun["result"], "GirlGun_world = Vela_matrix_6; GirlGun_local = identity")
        attachments = self.actual["girlgun_attachment_models"]
        self.assertEqual([item["prop_id"] for item in attachments], list(range(283, 292)))
        self.assertTrue(all(item["transform_record_count"] == 0 for item in attachments))
        self.assertTrue(all(item["active_group_matrix_ids"] == [0] for item in attachments))
        self.assertEqual(attachments[8]["name"], "VelaHand")

    def test_checked_in_report_is_reproducible(self) -> None:
        expected = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(self.actual, expected)


if __name__ == "__main__":
    unittest.main()
