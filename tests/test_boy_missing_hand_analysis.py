from __future__ import annotations
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jfg_re.boy_missing_hand_analysis import build_report

WORKSPACE = ROOT.parent
BOY = WORKSPACE / "extracted" / "characters" / "0220_Boy.bin"
ROM = WORKSPACE / "rom" / "jetforcegemini.z64"
JUNOHAND = WORKSPACE / "extracted" / "props" / "0309_JunoHand.bin"


@unittest.skipUnless(BOY.is_file() and ROM.is_file() and JUNOHAND.is_file(), "local pinned inputs unavailable")
class MissingHandAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report(BOY.read_bytes(), ROM.read_bytes(), JUNOHAND.read_bytes())

    def test_triangle_accounting(self) -> None:
        counts = self.report["triangle_accounting"]
        self.assertEqual((counts["prop_triangle_records"], counts["geometrically_valid"], counts["geometrically_degenerate"]), (520, 505, 15))
        self.assertEqual((counts["valid_in_makeModelGfx_path"], counts["exported_by_anim0_frame0_exporter"]), (502, 502))
        self.assertEqual(counts["valid_but_skipped_triangle_indices"], [0, 1, 2])

    def test_arm_asymmetry_and_reference(self) -> None:
        arms = self.report["arm_comparison"]
        self.assertEqual(arms["visible_hand_matrix_9"]["unique_vertices"], 42)
        self.assertEqual(arms["visible_hand_matrix_9"]["triangle_corners"], 96)
        self.assertEqual(arms["opposite_endpoint_matrix_6"]["unique_vertices"], 0)
        self.assertEqual(arms["matrix_6_reference_point"]["anim0_frame0_xyz_s16"], [79, 131, 45])

    def test_skipped_groups_are_not_a_hand_counterpart(self) -> None:
        groups = self.report["runtime_skipped_groups"]
        self.assertEqual(len(groups), 17)
        self.assertEqual(sum(group["nondegenerate_face_count"] for group in groups), 3)
        self.assertEqual(sum(group["vertex_count"] for group in groups), 22)
        self.assertEqual([group["group_index"] for group in groups if group["nondegenerate_face_count"]], [0, 1])

    def test_junohand_historical_candidate_is_marked_superseded(self) -> None:
        hand = self.report["separate_asset_evidence"]
        self.assertEqual((hand["active_prefix_vertex_count"], hand["active_prefix_face_count"]), (42, 32))
        self.assertIn("disproved", hand["comparison_status"])
        self.assertFalse(self.report["diagnostic_obj_created"])


if __name__ == "__main__":
    unittest.main()
