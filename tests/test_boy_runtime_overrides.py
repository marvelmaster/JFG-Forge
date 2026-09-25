from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_export import BoyExportError
from jfg_re.boy_runtime_overrides import (
    apply_additive_angle,
    build_override_report,
    math_sin,
    movement_step,
    pulse_value,
    report_bytes,
    selector_parts,
    wrap_s16,
)


ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"


class BoyRuntimeOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.report = build_override_report(cls.rom)

    def test_selector_layout(self) -> None:
        self.assertEqual(selector_parts(0x0014), (0x0000, 0x14, 3, 1))
        self.assertEqual(selector_parts(0x0044), (0x0000, 0x44, 11, 1))
        self.assertEqual(selector_parts(0x4028), (0x4000, 0x28, 6, 2))

    def test_math_sin_and_node3_pulse(self) -> None:
        self.assertEqual(math_sin(self.rom, 0), 0)
        self.assertEqual(math_sin(self.rom, 0x4000), 65536)
        self.assertEqual(math_sin(self.rom, 0x8000), 0)
        self.assertEqual(math_sin(self.rom, 15 << 11), 12686)
        self.assertEqual(pulse_value(self.rom, 15, 5), 396)

    def test_additive_s16_wrap(self) -> None:
        self.assertEqual(apply_additive_angle(32760, 20), -32756)
        self.assertEqual(apply_additive_angle(-32760, -20), 32756)
        self.assertEqual(wrap_s16(0x10000), 0)

    def test_movement_smoothing_is_history_dependent(self) -> None:
        self.assertEqual(movement_step(160, 0), 150)
        self.assertEqual(movement_step(-16, 0), -15)
        for value in range(-15, 0):
            self.assertEqual(movement_step(value, 0), value)
        proof = self.report["other_angles"]["history_dependence_proof"]
        self.assertEqual(proof["fixed_negative_residuals"], list(range(-15, 0)))

    def test_scale_paths(self) -> None:
        scales = self.report["scales"]
        self.assertEqual(scales["node6_flag_path"]["raw_value"], 32)
        self.assertEqual(scales["node6_flag_path"]["factor_xyz"], 1 / 1024)
        deform = scales["deformation_path"]
        self.assertEqual(deform["channels"], [0, 6, 9, 10, 14, 18])
        self.assertEqual(deform["raw_scale_values"], [26214, 50790, 50790, 50790, 50790, 50790])
        self.assertEqual(deform["rom_initializer"], 0)
        self.assertIn("consumed later", scales["ordering"])

    def test_conclusion_and_minimal_capture(self) -> None:
        self.assertEqual(self.report["conclusion"]["code"], "B")
        self.assertFalse(self.report["conclusion"]["synthetic_pose_generated"])
        fields = {item["field"] for item in self.report["minimal_runtime_capture"]["smallest_raw_unknowns_for_the_constrained_case"]}
        self.assertEqual(fields, {"racer+0x580", "racer+0x540"})

    def test_report_is_deterministic(self) -> None:
        first = report_bytes(self.report)
        second = report_bytes(build_override_report(self.rom))
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())
        self.assertEqual(json.loads(first), self.report)

    def test_wrong_rom_is_rejected(self) -> None:
        damaged = bytearray(self.rom)
        damaged[0] ^= 1
        with self.assertRaises(BoyExportError):
            build_override_report(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
