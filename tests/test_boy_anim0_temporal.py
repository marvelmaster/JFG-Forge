from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_anim0_frame0 import locate_boy_animation0
from jfg_re.boy_anim0_temporal import TIMES, animation_metadata, build_temporal_artifacts, decode_time
from jfg_re.boy_export import BoyExportError


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
OUTPUT = PROJECT_ROOT / "data" / "generated" / "boy-anim0-temporal-test-not-created"


class BoyAnimation0TemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = BOY.read_bytes()
        cls.rom = ROM.read_bytes()
        cls.blob = locate_boy_animation0(cls.rom)["blob"]

    def test_metadata_and_loop_domain(self) -> None:
        metadata = animation_metadata(self.blob)
        self.assertEqual(metadata["stored_sample_count"], 16)
        self.assertEqual(metadata["stored_sample_indices"], [0, 15])
        self.assertEqual(metadata["frame_stride_bytes"], 25)
        self.assertTrue(metadata["loop_enabled"])
        self.assertEqual(metadata["next_sample_after_15"], 0)
        self.assertIsNone(metadata["fixed_fps"])

    def test_integer_roots_use_runtime_q10_sample_shift(self) -> None:
        roots = {time: decode_time(self.blob, time)["root_translation_model_xyz"] for time in (0.0, 1.0, 8.0, 15.0)}
        self.assertEqual(roots[0.0], [0.0, -9.0, 0.0])
        self.assertEqual(roots[1.0], [0.0, -6.0, 0.0])
        self.assertEqual(roots[8.0], [0.0, -9.0, 0.0])
        self.assertEqual(roots[15.0], [0.0, -10.0, 0.0])

    def test_half_frame_reproduces_fraction_and_signed_wrap(self) -> None:
        frame = decode_time(self.blob, 7.5)
        self.assertEqual(frame["fraction_10bit"], 512)
        self.assertEqual(frame["root_translation_model_xyz"], [0.0, -9.5, 0.0])
        self.assertEqual(frame["signed_11bit_wraparound_scalar_count"], 0)
        self.assertGreater(frame["u16_angle_boundary_crossing_count"], 0)
        self.assertEqual(frame["active_scale_scalar_count"], 0)
        wrapped = {item["scalar_index"]: item for item in frame["interpolation"] if item["u16_angle_boundary_crossed"]}
        self.assertEqual(wrapped[43]["signed_11bit_delta"], -1)
        self.assertEqual(wrapped[44]["signed_11bit_delta"], -1)

    def test_invalid_times_are_rejected(self) -> None:
        for value in (-0.5, 16.0, float("inf")):
            with self.assertRaises(BoyExportError):
                decode_time(self.blob, value)

    def test_artifacts_are_deterministic_and_complete(self) -> None:
        first = build_temporal_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        second = build_temporal_artifacts(self.boy, self.rom, MANIFEST, OUTPUT)
        self.assertEqual(first, second)
        self.assertEqual(sorted(name for name in first if name.endswith(".obj")), [
            "boy-anim0-time-00.obj",
            "boy-anim0-time-01.obj",
            "boy-anim0-time-07_5.obj",
            "boy-anim0-time-08.obj",
            "boy-anim0-time-15.obj",
        ])
        report = json.loads(first["boy-anim0-temporal-report.json"])
        self.assertEqual(report["selected_times"], list(TIMES))
        for sample in report["samples"]:
            self.assertEqual(sample["snapshot"]["counts"], {"faces": 502, "textured_faces": 478, "vertices": 638, "vt": 1434})
            obj = first[sample["snapshot"]["obj_file"]]
            self.assertEqual(hashlib.sha256(obj).hexdigest(), hashlib.sha256(obj).hexdigest())


if __name__ == "__main__":
    unittest.main()
