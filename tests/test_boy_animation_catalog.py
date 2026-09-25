from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import jfg_re.boy_animation_catalog as subject
from jfg_re.boy_export import BoyExportError


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
OUTPUT = PROJECT_ROOT / "data" / "generated" / "boy-animation-catalog-test-not-created"


class BoyAnimationCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = BOY.read_bytes()
        cls.rom = ROM.read_bytes()
        cls.catalog = subject.catalog_boy_animations(cls.rom)
        tables = subject._tables(cls.rom)
        start, end = struct.unpack_from(">II", tables["asset42"], subject.SELECTED_ID * 4)
        cls.selected_blob = tables["asset43"][start:end]

    def test_all_52_entries_and_samples_parse(self) -> None:
        self.assertEqual(self.catalog["counts"]["animations"], 52)
        self.assertEqual(self.catalog["counts"]["with_scale_streams"], 0)
        self.assertEqual(self.catalog["counts"]["with_nonidentity_channel_map"], 0)
        tables = subject._tables(self.rom)
        for record in self.catalog["animations"]:
            start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
            blob = tables["asset43"][start:end]
            structure = subject._structure(blob)
            for sample_index in range(structure["sample_count"]):
                subject._packed(blob, structure, sample_index)

    def test_selected_animation_is_structurally_distinct(self) -> None:
        record = self.catalog["animations"][43]
        self.assertEqual(record["animation_id"], 1069)
        self.assertEqual(record["sample_count"], 76)
        self.assertEqual(record["sample_stride_bytes"], 49)
        self.assertEqual(record["root"]["bit_widths_xyz"], [5, 1, 7])
        self.assertFalse(record["loop_enabled"])

    def test_selected_integer_endpoint_and_half_frame(self) -> None:
        expected_roots = {
            0.0: [-1.0, -1.0, 0.0],
            1.0: [-1.0, -1.0, 0.0],
            37.0: [-1.0, -1.0, 0.0],
            37.5: [-1.0, -1.0, 0.0],
            75.0: [-26.0, -2.0, 78.0],
        }
        for time_value, root in expected_roots.items():
            frame = subject.decode_animation_time(self.selected_blob, time_value)
            self.assertEqual(frame["root_translation_model_xyz"], root)
        half = subject.decode_animation_time(self.selected_blob, 37.5)
        self.assertEqual(half["fraction_10bit"], 512)
        self.assertEqual(half["u16_angle_boundary_crossing_count"], 2)
        self.assertEqual(half["active_scale_scalar_count"], 0)
        with self.assertRaises(BoyExportError):
            subject.decode_animation_time(self.selected_blob, 75.5)

    def test_artifacts_are_deterministic_and_only_one_second_animation_is_exported(self) -> None:
        first = subject.build_catalog_and_selected_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        second = subject.build_catalog_and_selected_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        self.assertEqual(first, second)
        objects = sorted(name for name in first if name.endswith(".obj"))
        self.assertEqual(objects, [
            "boy-anim43-time-00.obj", "boy-anim43-time-01.obj", "boy-anim43-time-37.obj",
            "boy-anim43-time-37_5.obj", "boy-anim43-time-75.obj",
        ])
        report = json.loads(first["boy-anim43-validation-report.json"])
        for sample in report["samples"]:
            self.assertEqual(sample["snapshot"]["counts"]["vertices"], 638)
            self.assertEqual(sample["snapshot"]["counts"]["faces"], 502)


if __name__ == "__main__":
    unittest.main()
