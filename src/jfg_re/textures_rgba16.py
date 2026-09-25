"""Verified JFG US RGBA5551 texture extraction with RDP block-swap correction.

This module deliberately supports only the observed 32-byte ``11 00`` RGBA16
container. It makes no inference about RGBA32, CI, IA, I, TLUT, mipmaps, or
any other texture format.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import binascii
import json
from pathlib import Path
import struct
from typing import Any
import zlib

from jfg_re.props import COMPRESSION_MARKER, validate_rom_identity


HEADER_SIZE = 32
FORMAT_MARKER = b"\x11\x00"
DECODER_ID = "rgba16-blockswap-v1"
STATUS = "VERIFIED"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TextureValidationError(ValueError):
    """Raised when a file does not match the verified RGBA16 texture container."""


@dataclass(frozen=True)
class TextureHeader:
    width: int
    height: int
    raw: bytes


def sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_texture_header(data: bytes) -> TextureHeader:
    """Validate the observed 32-byte RGBA16 header and return its dimensions."""
    if len(data) < HEADER_SIZE:
        raise TextureValidationError(f"Texture is {len(data)} bytes; header requires {HEADER_SIZE} bytes.")
    width, height = data[0], data[1]
    if width == 0 or height == 0:
        raise TextureValidationError("Width and height must both be non-zero.")
    if data[2:4] != FORMAT_MARKER:
        raise TextureValidationError(
            f"Unexpected format marker {data[2:4].hex()}; expected {FORMAT_MARKER.hex()}."
        )
    expected_length = HEADER_SIZE + width * height * 2
    if len(data) != expected_length:
        raise TextureValidationError(
            f"Texture length {len(data)} does not match {width}x{height} RGBA16 length {expected_length}."
        )
    return TextureHeader(width=width, height=height, raw=data[:HEADER_SIZE])


def decode_rgba5551(pixel_bytes: bytes) -> bytes:
    """Decode Big-Endian N64 RGBA5551 pixels to RGBA8888 bytes."""
    if len(pixel_bytes) % 2:
        raise TextureValidationError("RGBA5551 pixel data must have an even byte length.")
    rgba = bytearray(len(pixel_bytes) * 2)
    output = 0
    for index in range(0, len(pixel_bytes), 2):
        value = (pixel_bytes[index] << 8) | pixel_bytes[index + 1]
        rgba[output] = ((value >> 11) & 0x1F) * 255 // 31
        rgba[output + 1] = ((value >> 6) & 0x1F) * 255 // 31
        rgba[output + 2] = ((value >> 1) & 0x1F) * 255 // 31
        rgba[output + 3] = 255 if value & 1 else 0
        output += 4
    return bytes(rgba)


def apply_odd_row_block_swap(rgba: bytes, width: int, height: int) -> bytes:
    """Swap two-pixel halves in full four-pixel groups on odd image rows."""
    if len(rgba) != width * height * 4:
        raise TextureValidationError("RGBA buffer length does not match the supplied dimensions.")
    result = bytearray(rgba)
    row_stride = width * 4
    for y in range(1, height, 2):
        row_start = y * row_stride
        for x in range(0, width - 3, 4):
            first = row_start + x * 4
            second = first + 8
            result[first : first + 8] = rgba[second : second + 8]
            result[second : second + 8] = rgba[first : first + 8]
    return bytes(result)


def decode_texture(data: bytes) -> tuple[TextureHeader, bytes]:
    """Validate, decode, and apply the verified block-swap correction."""
    header = parse_texture_header(data)
    rgba = decode_rgba5551(data[HEADER_SIZE:])
    return header, apply_odd_row_block_swap(rgba, header.width, header.height)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    """Encode a deterministic non-interlaced 8-bit RGBA PNG using filter type 0."""
    if len(rgba) != width * height * 4:
        raise TextureValidationError("RGBA buffer length does not match PNG dimensions.")
    row_stride = width * 4
    raw_rows = b"".join(b"\x00" + rgba[offset : offset + row_stride] for offset in range(0, len(rgba), row_stride))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw_rows)) + _png_chunk(b"IEND", b"")


def _paeth(left: int, above: int, upper_left: int) -> int:
    predictor = left + above - upper_left
    left_distance = abs(predictor - left)
    above_distance = abs(predictor - above)
    upper_left_distance = abs(predictor - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def decode_png_rgba(png: bytes) -> tuple[int, int, bytes]:
    """Decode non-interlaced, 8-bit RGBA PNGs for pixel-level reference checks."""
    if not png.startswith(PNG_SIGNATURE):
        raise TextureValidationError("Reference image does not have a PNG signature.")
    position = len(PNG_SIGNATURE)
    width = height = None
    idat: list[bytes] = []
    while position < len(png):
        if position + 12 > len(png):
            raise TextureValidationError("Truncated PNG chunk.")
        length = struct.unpack_from(">I", png, position)[0]
        kind = png[position + 4 : position + 8]
        payload_start = position + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(png):
            raise TextureValidationError("Truncated PNG chunk payload.")
        payload = png[payload_start:payload_end]
        if kind == b"IHDR":
            if length != 13:
                raise TextureValidationError("Invalid PNG IHDR length.")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", payload)
            if (bit_depth, color_type, compression, filter_method, interlace) != (8, 6, 0, 0, 0):
                raise TextureValidationError("Only non-interlaced 8-bit RGBA PNG references are supported.")
        elif kind == b"IDAT":
            idat.append(payload)
        elif kind == b"IEND":
            break
        position = payload_end + 4
    if width is None or height is None or not idat:
        raise TextureValidationError("PNG is missing IHDR or IDAT data.")
    try:
        filtered = zlib.decompress(b"".join(idat))
    except zlib.error as error:
        raise TextureValidationError(f"PNG IDAT decompression failed: {error}") from error
    stride = width * 4
    if len(filtered) != height * (stride + 1):
        raise TextureValidationError("PNG scanline data has an unexpected length.")
    result = bytearray(height * stride)
    previous = bytearray(stride)
    cursor = 0
    for row_index in range(height):
        filter_type = filtered[cursor]
        cursor += 1
        source = filtered[cursor : cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(source):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                row[index] = value
            elif filter_type == 1:
                row[index] = (value + left) & 0xFF
            elif filter_type == 2:
                row[index] = (value + above) & 0xFF
            elif filter_type == 3:
                row[index] = (value + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (value + _paeth(left, above, upper_left)) & 0xFF
            else:
                raise TextureValidationError(f"Unsupported PNG filter type {filter_type}.")
        offset = row_index * stride
        result[offset : offset + stride] = row
        previous = row
    return width, height, bytes(result)


def _parse_rom_offset(path: Path) -> int:
    try:
        return int(path.stem, 16)
    except ValueError as error:
        raise TextureValidationError(f"Texture bin name must be a hexadecimal ROM offset: {path.name}") from error


def _decompress_rom_block(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 5 > len(rom):
        raise TextureValidationError(f"ROM offset 0x{offset:X} cannot contain a compression container.")
    declared_size = struct.unpack_from("<I", rom, offset)[0]
    marker = rom[offset + 4]
    if marker != COMPRESSION_MARKER:
        raise TextureValidationError(
            f"ROM offset 0x{offset:X} has compression marker 0x{marker:02X}, expected 0x{COMPRESSION_MARKER:02X}."
        )
    try:
        data = zlib.decompress(rom[offset + 5 :], wbits=-15)
    except zlib.error as error:
        raise TextureValidationError(f"ROM block at 0x{offset:X} cannot be decompressed: {error}") from error
    if len(data) != declared_size:
        raise TextureValidationError(
            f"ROM block at 0x{offset:X} has decoded size {len(data)}, expected {declared_size}."
        )
    return data


def export_rgba16_textures(
    rom_path: Path,
    input_bins: Path,
    reference_pngs: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Export and fully validate verified RGBA16 texture bins into a new directory."""
    identity = validate_rom_identity(rom_path)
    input_bins = input_bins.resolve(strict=True)
    reference_pngs = reference_pngs.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to write into existing output directory: {output_dir}")
    if not input_bins.is_dir() or not reference_pngs.is_dir():
        raise NotADirectoryError("input_bins and reference_pngs must both be directories.")

    bin_paths = sorted(input_bins.glob("*.bin"))
    rom = identity.path.read_bytes()
    output_dir.mkdir(parents=True)
    png_dir = output_dir / "png"
    png_dir.mkdir()
    records: list[dict[str, Any]] = []
    deviations: list[dict[str, Any]] = []

    for bin_path in bin_paths:
        offset = _parse_rom_offset(bin_path)
        binary_data = bin_path.read_bytes()
        record: dict[str, Any] = {
            "status": STATUS,
            "decoder_id": DECODER_ID,
            "source_bin": bin_path.name,
            "rom_offset": offset,
            "rom_offset_hex": f"0x{offset:X}",
            "binary_sha256": sha256_bytes(binary_data),
        }
        try:
            header, rgba = decode_texture(binary_data)
            rom_data = _decompress_rom_block(rom, offset)
            rom_binary_match = rom_data == binary_data
            if not rom_binary_match:
                raise TextureValidationError("TextureBin bytes do not match the decompressed ROM block.")
            output_name = f"{bin_path.stem}_{header.width}x{header.height}.png"
            output_path = png_dir / output_name
            png_data = encode_png_rgba(header.width, header.height, rgba)
            output_path.write_bytes(png_data)
            reference_path = reference_pngs / output_name
            if not reference_path.is_file():
                raise TextureValidationError(f"Reference PNG is missing: {reference_path.name}")
            reference_data = reference_path.read_bytes()
            reference_width, reference_height, reference_rgba = decode_png_rgba(reference_data)
            dimensions_match = (reference_width, reference_height) == (header.width, header.height)
            pixels_match = dimensions_match and reference_rgba == rgba
            record.update(
                {
                    "width": header.width,
                    "height": header.height,
                    "header_hex": header.raw.hex(),
                    "rom_binary_match": rom_binary_match,
                    "output_png": f"png/{output_name}",
                    "png_sha256": sha256_bytes(png_data),
                    "reference_png": reference_path.name,
                    "reference_png_sha256": sha256_bytes(reference_data),
                    "png_file_hash_match": sha256_bytes(png_data) == sha256_bytes(reference_data),
                    "reference_dimensions_match": dimensions_match,
                    "reference_pixel_match": pixels_match,
                }
            )
            if not pixels_match:
                raise TextureValidationError("Decoded RGBA pixels differ from the reference PNG.")
        except (OSError, TextureValidationError) as error:
            record["error"] = str(error)
            deviations.append({"source_bin": bin_path.name, "rom_offset_hex": f"0x{offset:X}", "cause": str(error)})
        records.append(record)

    report = {
        "schema_version": 1,
        "status": STATUS,
        "scope": "Only 32-byte 11 00 RGBA5551 containers with odd-row two-pixel block swapping.",
        "rom": {"path": str(identity.path), "size_bytes": identity.size_bytes, "sha1": identity.sha1},
        "validation": {
            "input_bins": len(bin_paths),
            "recognized_rgba16_textures": sum("error" not in record for record in records),
            "rom_binary_matches": sum(record.get("rom_binary_match") is True for record in records),
            "reference_pixel_matches": sum(record.get("reference_pixel_match") is True for record in records),
            "identical_png_file_hashes": sum(record.get("png_file_hash_match") is True for record in records),
            "deviation_count": len(deviations),
            "deviations": deviations,
        },
    }
    (output_dir / "textures-manifest.json").write_text(
        json.dumps({"schema_version": 1, "textures": records}, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "validation-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report
