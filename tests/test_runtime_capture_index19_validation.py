from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import struct
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "research" / "boy" / "validate_runtime_capture_index19.py"


class RuntimeCaptureIndex19ValidationTests(unittest.TestCase):
    def test_real_capture_reproduces_all_runtime_matrices(self) -> None:
        spec = importlib.util.spec_from_file_location("validate_runtime_capture_index19", HELPER)
        if spec is None or spec.loader is None:
            self.fail("Could not load the index-19 capture validator.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.analyze()

        self.assertEqual(report["capture"]["directory"], "index19-id1022")
        state = report["instance_state"]
        self.assertEqual((state["current_animation_index"], state["current_animation_id"]), (19, 1022))
        self.assertEqual(state["blend_counter_s16"], 0)
        self.assertEqual(state["unscaled_current_time_instance_plus_0x38"], 39.0)
        self.assertEqual(state["effective_current_sample_time_instance_plus_0x28"], 30.41998291015625)
        self.assertEqual(state["fraction_10bit"], 430)

        selectors = report["selectors"]
        self.assertEqual(selectors["bytes_consumed_through_terminator"], 6)
        self.assertEqual(selectors["entries"][0]["selector"], 0x0044)
        self.assertEqual(selectors["entries"][0]["value_s16"], -15)
        self.assertEqual(selectors["entries"][0]["direct_boy_joint_ids"], [11])
        self.assertEqual(selectors["a_to_b"]["changed_matrix_count"], 10)

        comparison = report["runtime_comparison_c"]
        self.assertEqual(comparison["matrices_with_max_error_at_most_1e-5"], 21)
        self.assertLessEqual(comparison["maximum_absolute_error"], 1.0e-5)
        self.assertLessEqual(comparison["mean_absolute_error"], 2.0e-7)

    def test_only_five_required_capture_files_are_needed(self) -> None:
        spec = importlib.util.spec_from_file_location("validate_runtime_capture_index19_minimum", HELPER)
        if spec is None or spec.loader is None:
            self.fail("Could not load the generalized capture validator.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in (
                "capture.txt",
                "instance_n64.bin",
                "object_matrix_n64.bin",
                "selectors_n64.bin",
                "matrices_n64.bin",
            ):
                shutil.copyfile(module.CAPTURE_DIR / name, directory / name)
            selectors = (directory / "selectors_n64.bin").read_bytes()
            (directory / "selectors_n64.bin").write_bytes(selectors[:6])
            report = module.analyze(directory)
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["runtime_comparison_c"]["matrices_with_max_error_at_most_1e-5"], 21)
        self.assertEqual(report["capture"]["optional_checks"], {})

    def test_blended_capture_is_rejected_at_the_reusable_boundary(self) -> None:
        spec = importlib.util.spec_from_file_location("validate_runtime_capture_index19_blend", HELPER)
        if spec is None or spec.loader is None:
            self.fail("Could not load the generalized capture validator.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in (
                "capture.txt",
                "instance_n64.bin",
                "object_matrix_n64.bin",
                "selectors_n64.bin",
                "matrices_n64.bin",
            ):
                shutil.copyfile(module.CAPTURE_DIR / name, directory / name)
            instance = bytearray((directory / "instance_n64.bin").read_bytes())
            struct.pack_into(">h", instance, 0x5E, 1)
            (directory / "instance_n64.bin").write_bytes(instance)
            with self.assertRaisesRegex(Exception, "requires a stable no-blend frame"):
                module.analyze(directory)


if __name__ == "__main__":
    unittest.main()
