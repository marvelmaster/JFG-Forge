from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_anim0_temporal import decode_time
from jfg_re.boy_anim0_frame0 import locate_boy_animation0
from jfg_re.boy_export import BONE_COUNT, BoyExportError
from jfg_re.boy_runtime_capture import (
    CAPTURE_PC,
    _runtime_matrices,
    apply_selectors,
    capture_spec,
    capture_spec_bytes,
    import_capture,
    parse_selectors,
)
from jfg_re.props import EXPECTED_ROM_SIZE, EXPECTED_SHA1


ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"


class BoyRuntimeCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.boy = BOY.read_bytes()

    def _fixture(self, directory: Path, *, animation: int = 0, blend: int = 0, matrices: bool = True) -> Path:
        phase = 0.25
        matrix_base = 0x80410000
        instance = bytearray(0x80)
        instance[0x0B] = 1
        struct.pack_into(">II", instance, 0x10, 0x80400000, matrix_base)
        struct.pack_into(">HH", instance, 0x24, animation, 0)
        struct.pack_into(">f", instance, 0x28, phase * 16.0)
        struct.pack_into(">f", instance, 0x38, phase)
        struct.pack_into(">hh", instance, 0x5C, 0, blend)
        identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        object_matrix = struct.pack(">16f", *identity)
        selectors = struct.pack(">HhH", 0x0044, -3, 0x1000)
        dumps: dict[str, object] = {
            "instance": {"hex": instance.hex()},
            "object_world_matrix": {"hex": object_matrix.hex()},
            "selectors": {"hex": selectors.hex()},
        }
        if matrices:
            frame = decode_time(locate_boy_animation0(self.rom)["blob"], phase * 16.0)
            entries, _ = parse_selectors(selectors)
            apply_selectors(frame, entries)
            expected = _runtime_matrices(self.boy, frame, self.rom, list(range(BONE_COUNT)), [identity[i:i+4] for i in range(0, 16, 4)])
            raw = b"".join(
                struct.pack(">fffI", row[0], row[1], row[2], 0x7FC00000)
                for matrix in expected
                for row in matrix
            )
            dumps["runtime_matrices"] = {"hex": raw.hex(), "sha256": hashlib.sha256(raw).hexdigest()}
        capture = {
            "schema_version": 1,
            "synthetic": True,
            "provenance": {"rom_sha1": EXPECTED_SHA1, "rom_size_bytes": EXPECTED_ROM_SIZE, "capture_pc": f"0x{CAPTURE_PC:08X}", "target_model": "Boy / Prop 220", "object_type_s16": 1},
            "pointers": {
                "stack_pointer": "0x80300000",
                "instance": "0x80420000",
                "object": "0x80200000",
                "racer": "0x80380000",
                "matrix_base": f"0x{matrix_base:08X}",
            },
            "dumps": dumps,
        }
        path = directory / "synthetic-capture.json"
        path.write_text(json.dumps(capture), encoding="utf-8")
        return path

    def test_capture_spec_is_pinned_and_deterministic(self) -> None:
        first = capture_spec_bytes(self.rom)
        second = capture_spec_bytes(self.rom)
        self.assertEqual(first, second)
        spec = capture_spec(self.rom)
        self.assertEqual(spec["schema_version"], 2)
        self.assertEqual(spec["addresses"]["exact_breakpoint_ram"], "0x8003D908")
        self.assertEqual(spec["matrix_storage"]["size_bytes"], 0x540)
        self.assertTrue(spec["minimum_capture"]["sufficient"])

    def test_selector_parser_and_application(self) -> None:
        raw = struct.pack(">HhHhHhH", 0x0008, 7, 0x4024, 32, 0x5000, 0, 0x1000)
        entries, consumed = parse_selectors(raw)
        self.assertEqual(consumed, len(raw))
        frame = {"channels": [{"rotation_raw_s16_abc": [0, 0, 0], "scale_raw_u16_xyz": [0, 0, 0]} for _ in range(21)]}
        apply_selectors(frame, entries)
        self.assertEqual(frame["channels"][1]["rotation_raw_s16_abc"][1], 7)
        self.assertEqual(frame["channels"][6]["scale_raw_u16_xyz"][0], 32)

    def test_synthetic_capture_reconstructs_all_matrices_and_vertices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = import_capture(self._fixture(Path(temporary)), self.rom, self.boy)
        self.assertEqual(report["status"], "SYNTHETIC_TEST_FIXTURE")
        self.assertEqual(report["reconstruction"]["matrices"], 21)
        self.assertEqual(report["reconstruction"]["active_source_vertices_transformed"], 638)
        self.assertEqual(report["reconstruction"]["matrix_comparison"]["maximum_absolute_error"], 0.0)
        self.assertEqual(report["reconstruction"]["positional_comparison"]["maximum_absolute_error"], 0.0)

    def test_runtime_matrix_dump_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = import_capture(self._fixture(Path(temporary), matrices=False), self.rom, self.boy)
        self.assertFalse(report["reconstruction"]["runtime_matrices_present"])
        self.assertIsNone(report["reconstruction"]["matrix_comparison"])

    def test_blended_or_out_of_catalog_animation_capture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(BoyExportError, "blended"):
                import_capture(self._fixture(directory, blend=1), self.rom, self.boy)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(BoyExportError, "outside the Boy catalog"):
                import_capture(self._fixture(directory, animation=99), self.rom, self.boy)

    def test_missing_required_dump_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._fixture(Path(temporary))
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["dumps"]["selectors"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(BoyExportError, "Missing selectors"):
                import_capture(path, self.rom, self.boy)


if __name__ == "__main__":
    unittest.main()
