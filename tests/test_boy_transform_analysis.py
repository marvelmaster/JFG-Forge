from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_transform_analysis import build_artifacts, build_transform_analysis


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"


class BoyTransformAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = BOY.read_bytes()
        cls.report = build_transform_analysis(cls.data)

    def test_hierarchy_translation_and_reference_records(self) -> None:
        records = self.report["transform_records"]
        self.assertEqual(len(records), 21)
        self.assertEqual(records[0]["parent_id"], 0xFF)
        self.assertEqual([record["matrix_id"] for record in records], list(range(21)))
        self.assertEqual(records[0]["local_translation_xyz"], [0.0, 137.72930908203125, 0.0])
        self.assertEqual(
            [(item["vertex_index"], item["matrix_id"]) for item in self.report["header_0x30_reference_records"]],
            [(619, 6), (624, 10)],
        )

    def test_active_geometry_assignments_are_unambiguous(self) -> None:
        self.assertEqual(self.report["counts"]["stored_vertices"], 660)
        self.assertEqual(self.report["counts"]["active_geometry_unique_vertices_with_matrix"], 638)
        self.assertEqual(self.report["counts"]["active_triangle_corner_references"], 1506)
        used = [r["matrix_id"] for r in self.report["transform_records"] if r["active_unique_vertex_count"]]
        self.assertEqual(used, [2, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])

    def test_no_pose_matrix_or_transformed_bbox_is_invented(self) -> None:
        self.assertFalse(self.report["status"]["transformed_obj_emitted"])
        self.assertIsNone(self.report["transformed_bbox"])
        self.assertTrue(all(record["local_matrix"] is None for record in self.report["transform_records"]))

    def test_artifacts_are_byte_deterministic(self) -> None:
        first = build_artifacts(self.data)
        second = build_artifacts(self.data)
        self.assertEqual(first, second)
        parsed = json.loads(first["boy-transform-runtime-analysis.json"])
        self.assertEqual(parsed["input"]["prop_id"], 220)


if __name__ == "__main__":
    unittest.main()
