from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_textured_export import build_textured_boy_artifacts
from jfg_re.boy_export import BoyExportError


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
POWER_BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0221_PowerBoy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class BoyTexturedExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = BOY.read_bytes()
        cls.rom = ROM.read_bytes()

    def _artifacts(self) -> dict[str, bytes]:
        return build_textured_boy_artifacts(self.boy, self.rom, MANIFEST, Path("output"))

    def test_counts_uv_indices_and_unknown_groups(self) -> None:
        artifacts = self._artifacts()
        report = json.loads(artifacts["boy-textured-export-report.json"])
        counts = report["counts"]
        self.assertEqual(counts["active_groups"], 65)
        self.assertEqual(counts["runtime_skipped_groups"], 17)
        self.assertEqual(counts["runtime_faces"], 502)
        self.assertEqual(counts["textured_verified_rgba16_groups"], 62)
        self.assertEqual(counts["textured_verified_rgba16_faces"], 478)
        self.assertEqual(counts["unknown_format_groups"], 3)
        self.assertEqual(counts["unknown_format_faces"], 24)
        self.assertEqual(counts["obj_v_records"], 660)
        self.assertEqual(counts["obj_vt_records"], 1434)
        self.assertTrue(report["validation"]["all_obj_v_indices_valid"])
        self.assertTrue(report["validation"]["all_obj_vt_indices_valid"])
        unknown = [group for group in report["groups"] if group["texture_status"] == "UNKNOWN FORMAT"]
        self.assertEqual([group["group_index"] for group in unknown], [79, 80, 81])
        self.assertEqual([group["texture_id_hex"] for group in unknown], ["0x9A00", "0x874E", "0x874C"])

    def test_materials_pngs_tile_states_and_unclamped_uvs(self) -> None:
        report = json.loads(self._artifacts()["boy-textured-export-report.json"])
        verified = [material for material in report["materials"] if material["texture_status"] == "VERIFIED RGBA16"]
        unknown = [material for material in report["materials"] if material["texture_status"] == "UNKNOWN FORMAT"]
        self.assertEqual(len(verified), 14)
        self.assertEqual(len(unknown), 3)
        for material in verified:
            tile = material["tile_state"]
            self.assertEqual(tile["cms"]["name"], "CLAMP")
            self.assertEqual(tile["cmt"]["name"], "CLAMP")
            self.assertEqual((tile["masks"], tile["maskt"], tile["shifts"], tile["shiftt"]), (0, 0, 0, 0))
            self.assertIsNotNone(material["png"])
            self.assertEqual(material["mtl_mapping"], "map_Kd -clamp on")
        self.assertTrue(all(material["png"] is None for material in unknown))
        uv = report["uv_range"]
        self.assertLess(uv["u_min"], 0)
        self.assertGreater(uv["u_max"], 1)
        self.assertLess(uv["v_min"], 0)
        mtl = self._artifacts()["boy-runtime-textured.mtl"].decode()
        self.assertEqual(mtl.count("map_Kd "), 14)

    def test_group16_matches_single_group_validation(self) -> None:
        report = json.loads(self._artifacts()["boy-textured-export-report.json"])
        self.assertTrue(report["validation"]["group16_uv_matches_verified_single_group_test"])
        group16 = [face for face in report["faces"] if face["group_index"] == 16]
        self.assertEqual(len(group16), 15)
        first = group16[0]
        for (raw_s, raw_t), (u, v) in zip(first["raw_corner_st"], first["obj_uv"]):
            self.assertEqual(u, raw_s / 512)
            self.assertEqual(v, 1 - raw_t / 512)

    def test_corner_uvs_and_output_are_deterministic(self) -> None:
        first = self._artifacts()
        second = self._artifacts()
        self.assertEqual(first, second)
        report = json.loads(first["boy-textured-export-report.json"])
        textured_faces = [face for face in report["faces"] if face["obj_uv"] is not None]
        vt_indices = [index for face in textured_faces for index in face["obj_vt_indices"]]
        self.assertEqual(vt_indices, list(range(1, len(vt_indices) + 1)))
        self.assertEqual(len(vt_indices), 478 * 3)

    def test_powerboy_is_rejected(self) -> None:
        with self.assertRaises(BoyExportError):
            build_textured_boy_artifacts(POWER_BOY.read_bytes(), self.rom, MANIFEST, Path("output"))


if __name__ == "__main__":
    unittest.main()
