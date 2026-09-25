from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest

from jfg_re.scene_ripper_glr import (
    EXPECTED_CAPTURE_SHA256,
    GLRValidationError,
    analyze_capture,
    build_artifacts,
    parse_glr,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "jfg-re/data/source/scene-ripper/boy-test-001"
BOY = ROOT / "extracted/characters/0220_Boy.bin"
ROM = ROOT / "rom/jetforcegemini.z64"
TEXTURED_REPORT = ROOT / "jfg-re/data/generated/boy-prop220-textured-static/boy-textured-export-report.json"
TEXTURE_ROOT = ROOT / "jfg-re/data/generated/rgba16-us-verified"


class SceneRipperTests(unittest.TestCase):
    def test_glr_parser_rejects_bad_magic_and_truncation(self) -> None:
        data = bytearray(0x24)
        data[:6] = b"GL64R\0"
        struct.pack_into("<H", data, 6, 4)
        struct.pack_into("<I", data, 0x1C, 1)
        with self.assertRaisesRegex(GLRValidationError, "requires"):
            parse_glr(bytes(data))
        data[:6] = b"BROKEN"
        with self.assertRaisesRegex(GLRValidationError, "magic"):
            parse_glr(bytes(data))

    def test_real_capture_and_boy_comparison_is_pinned_and_deterministic(self) -> None:
        glr = (CAPTURE / "n64_scene.glr").read_bytes()
        self.assertEqual(sha256_bytes(glr), EXPECTED_CAPTURE_SHA256)
        scene = parse_glr(glr)
        self.assertEqual((scene.version, scene.game_name, scene.triangle_count), (4, "JET FORCE GEMINI", 784))

        report = analyze_capture(CAPTURE, BOY, ROM, TEXTURED_REPORT, TEXTURE_ROOT)
        self.assertEqual(report["texture_summary"]["png_count"], 57)
        self.assertEqual(len(report["boy_texture_correlations"]), 14)
        self.assertTrue(all(item["rgba5551_codes_equal"] for item in report["boy_texture_correlations"]))
        geometry = report["geometry_comparison"]
        self.assertEqual(geometry["captured_triangle_records"], 494)
        self.assertEqual(geometry["decoded_source_triangles_represented"], 494)
        self.assertEqual(geometry["decoded_active_source_vertices_represented"], 629)
        self.assertEqual(geometry["unrepresented_group_indices"], [79])
        self.assertLess(geometry["maximum_positional_error_after_per_matrix_affine"], 5e-6)
        self.assertEqual(len(report["runtime_hand_evidence"]["additional_instances"]), 2)

        first = build_artifacts(CAPTURE, BOY, ROM, TEXTURED_REPORT, TEXTURE_ROOT)
        second = build_artifacts(CAPTURE, BOY, ROM, TEXTURED_REPORT, TEXTURE_ROOT)
        self.assertEqual(first, second)
        parsed = json.loads(first["scene-ripper-validation.json"])
        self.assertEqual(parsed["boy_identification"]["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
