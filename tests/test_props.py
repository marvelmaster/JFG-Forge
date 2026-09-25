from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.props import (
    COMPRESSION_MARKER,
    PROP_COUNT,
    PROP_TABLE_ENTRIES,
    PropExtractionError,
    RomIdentityError,
    decode_prop_block,
    parse_offset_table,
    validate_rom_identity,
)


class PropFormatTests(unittest.TestCase):
    def test_verified_table_dimensions(self) -> None:
        self.assertEqual(PROP_TABLE_ENTRIES, 905)
        self.assertEqual(PROP_COUNT, 904)

    def test_offset_table_parses_big_endian_aligned_offsets(self) -> None:
        values = tuple(index * 16 for index in range(PROP_TABLE_ENTRIES))
        parsed = parse_offset_table(struct.pack(f">{PROP_TABLE_ENTRIES}I", *values))
        self.assertEqual(parsed, values)

    def test_offset_table_rejects_unaligned_or_descending_offsets(self) -> None:
        values = [index * 16 for index in range(PROP_TABLE_ENTRIES)]
        values[10] = 7
        with self.assertRaises(PropExtractionError):
            parse_offset_table(struct.pack(f">{PROP_TABLE_ENTRIES}I", *values))

    def test_raw_deflate_container_round_trips_and_validates_size(self) -> None:
        data = b"verified prop payload" * 32
        compressor = zlib.compressobj(wbits=-15)
        compressed = compressor.compress(data) + compressor.flush()
        declared_size, decoded = decode_prop_block(
            struct.pack("<I", len(data)) + bytes([COMPRESSION_MARKER]) + compressed
        )
        self.assertEqual(declared_size, len(data))
        self.assertEqual(decoded, data)

    def test_raw_deflate_container_rejects_marker_or_wrong_size(self) -> None:
        data = b"prop"
        compressor = zlib.compressobj(wbits=-15)
        compressed = compressor.compress(data) + compressor.flush()
        with self.assertRaises(PropExtractionError):
            decode_prop_block(struct.pack("<I", len(data)) + b"\x00" + compressed)
        with self.assertRaises(PropExtractionError):
            decode_prop_block(struct.pack("<I", len(data) + 1) + bytes([COMPRESSION_MARKER]) + compressed)

    def test_wrong_rom_is_rejected_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_rom = Path(temporary_directory) / "invalid.z64"
            invalid_rom.write_bytes(b"not a verified ROM")
            with self.assertRaises(RomIdentityError):
                validate_rom_identity(invalid_rom)


if __name__ == "__main__":
    unittest.main()
