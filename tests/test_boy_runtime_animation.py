from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_animation import build_runtime_report, report_bytes
from jfg_re.boy_export import BoyExportError


ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"


class BoyRuntimeAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.report = build_runtime_report(cls.rom)

    def test_pinned_animation_identity_and_context(self) -> None:
        a0 = self.report["animations"]["index_0_id_1026"]
        a43 = self.report["animations"]["index_43_id_1069"]
        self.assertEqual(a0["identity"]["animation_id"], 1026)
        self.assertTrue(a0["identity"]["loop_enabled"])
        self.assertEqual(a43["identity"]["animation_id"], 1069)
        self.assertFalse(a43["identity"]["loop_enabled"])
        self.assertIn("controlPlayerOpenChest", a43["selection"]["path"])

    def test_concrete_timing_case(self) -> None:
        case = self.report["animations"]["index_0_id_1026"]["timing"]["concrete_case"]
        self.assertAlmostEqual(case["phase_per_update"], 0.015)
        self.assertAlmostEqual(case["sample_time_per_update"], 0.24)
        # The ROM stores 0.015 as IEEE-754 binary32, so retain its tiny
        # representation difference rather than replacing runtime data by an
        # ideal decimal rational.
        self.assertAlmostEqual(case["vi_ticks_per_sample"], 25 / 6, places=6)
        self.assertAlmostEqual(case["vi_ticks_per_16_sample_cycle"], 200 / 3, places=5)
        self.assertAlmostEqual(case["nominal_ntsc_60hz_seconds_per_cycle"], 10 / 9, places=6)

    def test_blend_and_arm_override_facts(self) -> None:
        blend = self.report["transition_blend"]
        self.assertEqual(blend["header_low_nibble"], {"animation_0": 4, "animation_43": 4})
        self.assertIn("previous", blend["formula"])
        overrides = self.report["player_overrides"]
        selectors = {item["selector"] for item in overrides["angle_selectors"]}
        self.assertEqual(selectors, {"0x0006", "0x0008", "0x0014", "0x003C", "0x0044"})
        self.assertFalse(self.report["blender_interpretation"]["complete_runtime_pose"])

    def test_report_is_deterministic(self) -> None:
        first = report_bytes(self.report)
        second = report_bytes(build_runtime_report(self.rom))
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())
        self.assertEqual(json.loads(first), self.report)

    def test_wrong_rom_is_rejected(self) -> None:
        damaged = bytearray(self.rom)
        damaged[0] ^= 1
        with self.assertRaises(BoyExportError):
            build_runtime_report(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
