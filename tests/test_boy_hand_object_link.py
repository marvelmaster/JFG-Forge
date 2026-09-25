from __future__ import annotations
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jfg_re.boy_hand_object_link import build_report

WORKSPACE = ROOT.parent
ROM = WORKSPACE / "rom" / "jetforcegemini.z64"
CLUSTER = WORKSPACE / "extracted" / "props" / "0343_Cluster.bin"
JUNOHAND = WORKSPACE / "extracted" / "props" / "0309_JunoHand.bin"


@unittest.skipUnless(ROM.is_file() and CLUSTER.is_file() and JUNOHAND.is_file(), "local pinned inputs unavailable")
class BoyHandObjectLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report(ROM.read_bytes(), CLUSTER.read_bytes(), JUNOHAND.read_bytes())

    def test_object_f7_resolves_to_prop_343(self) -> None:
        chain = self.report["object_chain"]
        self.assertEqual(chain["translation_table"]["entry_value_object_definition_id"], 232)
        self.assertEqual(chain["object_definition"]["behaviour_id"], 0x59)
        self.assertEqual(chain["object_definition"]["model_ids"], [343])
        self.assertEqual(chain["resulting_prop_internal_name"], "Cluster")

    def test_junohand_is_disproved_for_this_path(self) -> None:
        self.assertIn("DISPROVED", self.report["object_chain"]["junohand_prop_309_result"])
        self.assertFalse(self.report["attachment_transform"]["junohand_transform_chain_exists"])
        self.assertFalse(self.report["diagnostic_obj_created"])

    def test_prop_309_has_other_object_definition_references(self) -> None:
        definitions = self.report["prop_309_occurs_elsewhere"]
        self.assertEqual([item["object_definition_id"] for item in definitions], [399, 564, 653])
        self.assertEqual([item["object_ids"] for item in definitions], [[199], [446], [517]])

    def test_actual_prop_343_structure(self) -> None:
        prop = self.report["actual_prop_343"]
        self.assertEqual((prop["vertex_count"], prop["triangle_record_count"], prop["group_count"]), (22, 32, 3))
        self.assertEqual((prop["geometrically_valid_triangle_count"], prop["geometrically_degenerate_triangle_count"]), (24, 8))
        self.assertEqual(prop["texture_ids_hex"], ["0x80FD"])
        self.assertEqual(prop["transform_record_count"], 0)


if __name__ == "__main__":
    unittest.main()
