from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "research" / "lupus" / "analyze_lupus.py"
ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
PROP = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0222_Dog.bin"
TEXTURES = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
INDEX = PROJECT_ROOT.parent / "extracted" / "index.json"
STRUCTURAL_REPORT = PROJECT_ROOT / "research" / "lupus" / "structural-map.json"
ANIMATION_REPORT = PROJECT_ROOT / "research" / "lupus" / "animation-map.json"


@unittest.skipUnless(
    all(path.is_file() for path in (ROM, PROP, TEXTURES, INDEX, STRUCTURAL_REPORT, ANIMATION_REPORT)),
    "Lupus discovery regression requires ignored local ROM and canonical extraction fixtures.",
)
class LupusDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("analyze_lupus", HELPER)
        if spec is None or spec.loader is None:
            raise AssertionError("Could not load Lupus analysis helper.")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.structural, cls.animation = cls.module.analyze(ROM, PROP, TEXTURES, INDEX)

    def test_canonical_identity_block_and_structure(self) -> None:
        identity = self.structural["identity"]
        self.assertEqual((identity["prop_id"], identity["prop_name"]), (222, "Dog"))
        self.assertEqual(identity["size_bytes"], 15_392)
        self.assertEqual(
            identity["sha256"],
            "e69c897a48697d6adef3c922111ae05d2ef04c07ff800d91f5ee0d78ab90b3eb",
        )
        self.assertEqual(identity["rom_container"]["rom_range_hex"], ["0x1415390", "0x1416F80"])
        self.assertTrue(identity["rom_container"]["canonical_matches_rom_decompression"])
        sections = self.structural["sections"]
        self.assertEqual(
            (
                sections["texture_records"]["count"],
                sections["groups_with_boundary"]["active_record_count"],
                sections["triangles"]["count"],
                sections["vertices"]["count"],
                sections["vertex_references"]["count"],
                sections["transforms"]["count"],
            ),
            (15, 65, 382, 490, 9, 27),
        )
        self.assertEqual(sections["pre_transform_unknown"]["hex"], "0000010c")

    def test_geometry_texture_and_hierarchy_consistency(self) -> None:
        geometry = self.structural["geometry"]
        self.assertEqual((geometry["active_group_count"], geometry["skipped_group_count"]), (44, 21))
        self.assertEqual((geometry["active_triangle_records"], geometry["active_nondegenerate_faces"]), (361, 361))
        self.assertEqual(geometry["active_referenced_source_vertices"], 459)
        self.assertEqual(geometry["active_vertex_matrix_assignment_conflicts"], [])
        textures = self.structural["textures"]
        self.assertEqual((textures["verified_rgba16_count"], textures["unsupported_count"]), (12, 3))
        unsupported = {item["texture_index"]: item for item in textures["records"] if not item["verified_rgba16"]}
        self.assertEqual(set(unsupported), {1, 4, 13})
        self.assertEqual(unsupported[1]["active_group_count"], 0)
        self.assertEqual((unsupported[4]["active_group_count"], unsupported[13]["active_group_count"]), (1, 1))
        topology = self.structural["transform_structure"]["topology"]
        self.assertEqual(topology["roots"], [0])
        self.assertEqual(topology["target_ids"], list(range(27)))
        self.assertTrue(topology["target_ids_unique"])
        self.assertTrue(topology["all_parents_valid"])
        self.assertTrue(topology["parent_before_child"])
        self.assertTrue(topology["cycle_free"])

    def test_object_chain_reference_points_and_attachment(self) -> None:
        objects = self.structural["objects_and_attachments"]
        self.assertEqual(objects["player"]["technical_name"], "playerDog")
        self.assertEqual(objects["player"]["model_prop_ids"], [222, 798])
        self.assertEqual(objects["player"]["child_object_definition_ids"], [401])
        self.assertEqual(objects["power_variant"]["technical_name"], "playerDogPower")
        self.assertEqual(objects["power_variant"]["model_prop_ids"], [223])
        doggun = objects["doggun"]
        self.assertEqual((doggun["technical_name"], doggun["attachment_matrix_id"]), ("DogGun", 16))
        self.assertEqual([item["prop_id"] for item in doggun["model_slots"]], list(range(320, 329)))
        references = self.structural["transform_structure"]["vertex_references"]
        self.assertEqual((references[0]["vertex_id"], references[0]["matrix_id"]), (467, 16))
        self.assertEqual(len(references), 9)
        attachments = self.structural["doggun_attachment_models"]
        self.assertTrue(all(item["transform_record_count"] == 0 for item in attachments))
        self.assertTrue(all(item["active_group_matrix_ids"] == [0] for item in attachments))

    def test_animation_catalog_and_reference_pose(self) -> None:
        catalog = self.animation["catalog"]
        self.assertEqual(catalog["counts"]["animations"], 24)
        self.assertEqual(catalog["counts"]["unique_animation_ids"], 24)
        self.assertEqual((catalog["counts"]["looping"], catalog["counts"]["non_looping"]), (15, 9))
        self.assertEqual(catalog["counts"]["with_runtime_scale_streams"], 24)
        self.assertEqual(catalog["counts"]["with_nonidentity_channel_map"], 24)
        self.assertEqual(catalog["animation_ids_in_index_order"], list(range(582, 606)))
        reference = self.animation["reference_animation"]
        self.assertEqual((reference["catalog_index"], reference["animation_id"], reference["time"]), (23, 605, 17.5))
        self.assertEqual(reference["interpolation"], {"current_sample": 17, "next_sample": 18, "fraction_10bit": 512})
        self.assertEqual(reference["root_translation_model_xyz"], [24.0, -29.0, 34.0])
        self.assertEqual(reference["matrix_count"], 27)
        self.assertEqual(reference["transformed_active_vertex_count"], 459)
        self.assertTrue(reference["all_matrices_finite"])
        self.assertEqual(
            reference["matrix_sha256_f32be_4x4"],
            "95dcf65672e1a1168716fefdec3dc4ab7094f888dfab5dc970c6f397840bbc6d",
        )

    def test_runtime_calls_and_checked_in_reports_are_reproducible(self) -> None:
        calls = {
            item["symbol"]: item["call_address"]
            for item in self.structural["runtime_evidence"]["relocated_calls"]
        }
        self.assertEqual(calls["modGenAnimMatrices"], "0x01101348")
        self.assertEqual(calls["objMakeGunMtx"], "0x01101380")
        self.assertEqual(calls["objAnimDframe"], "0x01105060")
        expected_structural = json.loads(STRUCTURAL_REPORT.read_text(encoding="utf-8"))
        expected_animation = json.loads(ANIMATION_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(self.structural, expected_structural)
        self.assertEqual(self.animation, expected_animation)


if __name__ == "__main__":
    unittest.main()
