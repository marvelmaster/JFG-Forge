from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_anim0_frame0 import (
    EXPECTED_ANIMATION_ID,
    EXPECTED_ANIMATION_SHA256,
    build_artifacts,
    build_matrices,
    decode_frame0,
    locate_boy_animation0,
)


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
OUTPUT = PROJECT_ROOT / "data" / "generated" / "boy-anim0-frame0-test-not-created"


class BoyAnimation0Frame0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = BOY.read_bytes()
        cls.rom = ROM.read_bytes()
        cls.located = locate_boy_animation0(cls.rom)
        cls.frame = decode_frame0(cls.located["blob"])

    def test_asset_lookup_is_pinned_to_boy_animation_zero(self) -> None:
        self.assertEqual(self.located["animation_count"], 52)
        self.assertEqual(self.located["animation_id"], EXPECTED_ANIMATION_ID)
        self.assertEqual(self.located["channel_map"], list(range(21)))
        self.assertEqual(hashlib.sha256(self.located["blob"]).hexdigest(), EXPECTED_ANIMATION_SHA256)
        self.assertEqual(
            self.located["evidence"]["asset43_animation_blob_rom_range_hex"],
            ["0x16E37C0", "0x16E39E0"],
        )

    def test_frame_zero_bitstream_and_channels(self) -> None:
        self.assertEqual(self.frame["frame_data_offset"], 0x8E)
        self.assertEqual(self.frame["frame_stride"], 25)
        self.assertEqual(self.frame["consumed_frame_bits"], 193)
        self.assertEqual(self.frame["padding_frame_bits"], 7)
        self.assertEqual(self.frame["root_translation_raw_xyz"], [0, -9216, 0])
        self.assertEqual(self.frame["root_translation_model_xyz"], [0.0, -9.0, 0.0])
        expected = {
            2: [-1152, -416, 0],
            4: [-3680, -3552, -8000],
            7: [96, -5728, 7328],
            12: [4736, 0, -1824],
            19: [2464, 0, 0],
            20: [0, 0, 0],
        }
        for channel, values in expected.items():
            self.assertEqual(self.frame["channels"][channel]["rotation_raw_s16_abc"], values)
        self.assertTrue(all(value == 0 for channel in self.frame["channels"] for value in channel["scale_raw_u16_xyz"]))

    def test_matrix_hierarchy_uses_all_records(self) -> None:
        matrices = build_matrices(self.boy, self.frame, self.rom, self.located["channel_map"])
        self.assertEqual(len(matrices), 21)
        self.assertEqual([record["matrix_id"] for record in matrices], list(range(21)))
        self.assertEqual(matrices[0]["world_model_matrix"][3], [0.0, 128.72930908203125, 0.0, 1.0])
        self.assertEqual(matrices[20]["parent_id"], 19)

    def test_export_is_deterministic_and_structurally_valid(self) -> None:
        first = build_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        second = build_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        self.assertEqual(first, second)
        report = json.loads(first["boy-anim0-frame0-report.json"])
        self.assertEqual(report["counts"]["transformed_active_vertices"], 638)
        self.assertEqual(report["counts"]["exported_faces"], 502)
        self.assertEqual(report["counts"]["verified_rgba16_textured_faces"], 478)
        # This snapshot changed because the former value was generated with
        # stored A/C/B angles passed directly to an A/B/C matrix helper.  The
        # index-19 runtime capture independently verifies the corrected order.
        self.assertEqual(
            report["bounding_boxes"]["active_transformed_s16"],
            {"minimum": [-43, -5, -67], "maximum": [44, 216, 87]},
        )
        obj = first["boy-anim0-frame0-experimental.obj"].decode("utf-8")
        self.assertEqual(sum(line.startswith("v ") for line in obj.splitlines()), 638)
        self.assertEqual(sum(line.startswith("f ") for line in obj.splitlines()), 502)


if __name__ == "__main__":
    unittest.main()
