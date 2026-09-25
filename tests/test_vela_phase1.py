from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "research" / "vela" / "analyze_vela_phase1.py"
ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
PROP = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0218_Girl.bin"
TEXTURES = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
INDEX = PROJECT_ROOT.parent / "extracted" / "index.json"
REPORT = PROJECT_ROOT / "research" / "vela" / "phase1-structural-map.json"


@unittest.skipUnless(
    all(path.is_file() for path in (ROM, PROP, TEXTURES, INDEX)),
    "Vela Phase-1 regression requires ignored local ROM and canonical extraction fixtures.",
)
class VelaPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("analyze_vela_phase1", HELPER)
        if spec is None or spec.loader is None:
            raise AssertionError("Could not load Vela Phase-1 helper.")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.actual = cls.module.analyze(ROM, PROP, TEXTURES, INDEX)

    def test_identity_and_structure(self) -> None:
        identity = self.actual["identity"]
        self.assertEqual((identity["prop_id"], identity["name"]), (218, "Girl"))
        self.assertEqual(identity["size_bytes"], 19_016)
        self.assertEqual(
            identity["sha256"],
            "daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409",
        )
        self.assertTrue(identity["rom_container"]["canonical_matches_rom_decompression"])
        self.assertEqual(self.actual["sections"]["transforms"]["count"], 28)
        self.assertEqual(self.actual["sections"]["vertex_references"]["count"], 2)

    def test_geometry_textures_and_child(self) -> None:
        geometry = self.actual["geometry"]
        self.assertEqual(
            (geometry["stored_vertices"], geometry["stored_triangle_records"], geometry["group_count"]),
            (588, 475, 69),
        )
        self.assertEqual((geometry["active_group_count"], geometry["active_nondegenerate_faces"]), (51, 452))
        self.assertEqual(geometry["active_referenced_source_vertices"], 551)
        self.assertEqual(geometry["active_vertex_matrix_assignment_conflicts"], [])
        self.assertEqual((self.actual["textures"]["verified_rgba16_count"], self.actual["textures"]["unsupported_count"]), (14, 2))
        objects = self.actual["objects_and_attachments"]
        self.assertEqual(objects["player"]["technical_name"], "playerGirl")
        self.assertEqual(objects["player"]["child_object_definition_ids"], [397])
        self.assertEqual(objects["girlgun"]["technical_name"], "GirlGun")
        self.assertEqual([slot["prop_id"] for slot in objects["girlgun"]["model_slots"]], list(range(283, 292)))
        self.assertEqual(objects["power_variant"]["technical_name"], "playerGirlPower")
        self.assertEqual(objects["power_variant"]["model_prop_ids"], [219, 795])
        self.assertEqual(objects["power_variant"]["child_object_definition_ids"], [397])

    def test_checked_in_report_is_reproducible(self) -> None:
        expected = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(self.actual, expected)


if __name__ == "__main__":
    unittest.main()
