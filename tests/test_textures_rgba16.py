from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.textures_rgba16 import (
    FORMAT_MARKER,
    HEADER_SIZE,
    TextureValidationError,
    apply_odd_row_block_swap,
    decode_png_rgba,
    decode_rgba5551,
    encode_png_rgba,
    parse_texture_header,
)


class Rgba16TextureTests(unittest.TestCase):
    def test_header_accepts_verified_shape(self) -> None:
        data = bytes([2, 3]) + FORMAT_MARKER + bytes(HEADER_SIZE - 4) + bytes(2 * 3 * 2)
        header = parse_texture_header(data)
        self.assertEqual((header.width, header.height), (2, 3))

    def test_header_rejects_bad_marker_and_length(self) -> None:
        with self.assertRaises(TextureValidationError):
            parse_texture_header(bytes([2, 2, 0, 0]) + bytes(HEADER_SIZE))
        with self.assertRaises(TextureValidationError):
            parse_texture_header(bytes([2, 2]) + FORMAT_MARKER + bytes(HEADER_SIZE - 4))

    def test_rgba5551_is_big_endian_and_honors_alpha(self) -> None:
        pixels = decode_rgba5551(bytes.fromhex("f80107c1003f0000"))
        self.assertEqual(pixels[0:4], bytes((255, 0, 0, 255)))
        self.assertEqual(pixels[4:8], bytes((0, 255, 0, 255)))
        self.assertEqual(pixels[8:12], bytes((0, 0, 255, 255)))
        self.assertEqual(pixels[12:16], bytes((0, 0, 0, 0)))

    def test_block_swap_changes_only_full_groups_on_odd_rows(self) -> None:
        rgba = bytes(component for pixel in range(8) for component in (pixel, 0, 0, 255))
        swapped = apply_odd_row_block_swap(rgba, width=4, height=2)
        self.assertEqual([swapped[index] for index in range(0, 16, 4)], [0, 1, 2, 3])
        self.assertEqual([swapped[index] for index in range(16, 32, 4)], [6, 7, 4, 5])

    def test_png_round_trip_preserves_rgba_pixels(self) -> None:
        rgba = bytes((1, 2, 3, 4, 5, 6, 7, 8))
        width, height, decoded = decode_png_rgba(encode_png_rgba(2, 1, rgba))
        self.assertEqual((width, height, decoded), (2, 1, rgba))


if __name__ == "__main__":
    unittest.main()
