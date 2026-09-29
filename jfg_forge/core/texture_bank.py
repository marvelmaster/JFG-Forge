"""The ROM's texture bank: every texture, its format, and where it is used.

Textures live in two pools. Bank A is table asset 1 into data asset 0 (level
textures and model textures whose id has the high bit set); bank B is table
asset 3 into data asset 2 (model textures without the high bit). Each entry is
a 32-byte runtime header followed by one compressed container. Header byte 0/1
are width/height and the low nibble of byte 2 is the N64 format.

The ROM stores no texture names. Forge derives a *label* from usage: the first
model (or level) that references the texture, the way the game's own files name
things. Labels are marked as derived everywhere they are shown.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from jfg_forge.core.level_data import decode_block
from jfg_forge.core.model_parser import _asset_lut, _asset_range, decompress_texture_container, parse_model
from jfg_forge.core.rom_source import RomSource
from jfg_forge.core.texture_formats import DecodedModelTexture, decode_model_texture_frame
from jfg_forge.core.texture_rgba16 import (
    HEADER_SIZE,
    TextureHeader,
    TextureValidationError,
    apply_odd_row_block_swap,
    decode_rgba5551,
)

BANK_A = "A"
BANK_B = "B"
_BANK_ASSETS = {BANK_A: (1, 0), BANK_B: (3, 2)}
FORMAT_NAMES = {0: "RGBA32", 1: "RGBA16", 5: "IA8"}
PROP_COUNT = 904


@dataclass(frozen=True)
class TextureEntry:
    bank: str
    index: int
    width: int
    height: int
    format_byte: int
    rom_offset: int
    label: str = ""
    used_by: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, int]:
        return (self.bank, self.index)

    @property
    def format_nibble(self) -> int:
        return self.format_byte & 0x0F

    @property
    def format_name(self) -> str:
        return FORMAT_NAMES.get(self.format_nibble, f"format {self.format_nibble}")

    @property
    def decodable(self) -> bool:
        return self.format_nibble in FORMAT_NAMES

    @property
    def title(self) -> str:
        return self.label or f"Texture {self.bank}{self.index}"


def _words(rom: bytes, lut: tuple[int, ...], asset: int) -> tuple[int, ...]:
    start, end = _asset_range(lut, asset)
    return struct.unpack(f">{(end - start) // 4}I", rom[start:end])


def list_textures(source: RomSource) -> tuple[TextureEntry, ...]:
    """Header-only listing of both pools (fast: no decompression)."""
    rom = source.data
    lut = _asset_lut(rom)
    entries: list[TextureEntry] = []
    for bank in (BANK_A, BANK_B):
        table_asset, data_asset = _BANK_ASSETS[bank]
        table = _words(rom, lut, table_asset)
        data_start, data_end = _asset_range(lut, data_asset)
        for index in range(len(table) - 1):
            start, end = data_start + table[index], data_start + table[index + 1]
            if end - start < 32 or end > data_end:
                continue
            header = rom[start : start + 32]
            if header[0] == 0 or header[1] == 0:
                continue
            entries.append(TextureEntry(bank, index, header[0], header[1], header[2], start + 32))
    return tuple(entries)


def _lenient_decode(binary: bytes, frame: int) -> DecodedModelTexture:
    """Decode textures the strict model decoder refuses.

    Two layouts are covered: frames whose stride is larger than the pixels
    (the extra bytes are the smaller mipmap levels, which are skipped) and
    headers with a zero stride (frames are stored back to back). Only the base
    image of the requested frame is decoded. LIKELY, not VERIFIED.
    """
    if len(binary) < HEADER_SIZE:
        raise TextureValidationError("Texture is shorter than its 32-byte header.")
    width, height = binary[0], binary[1]
    format_id = binary[2] & 0x0F
    if width == 0 or height == 0 or format_id not in (0, 1, 5):
        raise TextureValidationError("Unsupported texture layout.")
    pixel_bytes = width * height * {0: 4, 1: 2, 5: 1}[format_id]
    frame_count = max(int.from_bytes(binary[0x12:0x14], "big") >> 8, 1)
    stride = int.from_bytes(binary[0x16:0x18], "big") or pixel_bytes
    if stride < pixel_bytes:
        raise TextureValidationError("Texture frame stride is smaller than its pixels.")
    chosen = frame if 0 <= frame < frame_count else 0
    start = HEADER_SIZE + chosen * stride
    pixels = binary[start : start + pixel_bytes]
    if len(pixels) != pixel_bytes:
        raise TextureValidationError("Texture data is shorter than its header says.")
    if format_id == 1:
        rgba = apply_odd_row_block_swap(decode_rgba5551(pixels), width, height)
    elif format_id == 0:
        rgba = pixels
    else:
        out = bytearray(width * height * 4)
        for i, pixel in enumerate(pixels):
            intensity, alpha = ((pixel >> 4) & 0x0F) * 17, (pixel & 0x0F) * 17
            out[i * 4 : i * 4 + 4] = bytes((intensity, intensity, intensity, alpha))
        rgba = bytes(out)
    return DecodedModelTexture(
        header=TextureHeader(width=width, height=height, raw=binary[:HEADER_SIZE]),
        rgba=rgba,
        format_id=format_id,
        format_name=FORMAT_NAMES[format_id],
        format_flags=binary[2] >> 4,
        frame_count=frame_count,
        frame_stride=stride,
        selected_frame=chosen,
        trailing_frame_bytes=stride - pixel_bytes,
    )


def decode_texture_entry(source: RomSource, entry: TextureEntry, frame: int = 0) -> DecodedModelTexture:
    """Decode one frame of a texture; raises for formats outside the decoder."""
    binary = decompress_texture_container(source.data, entry.rom_offset)
    try:
        return decode_model_texture_frame(binary, requested_frame=frame)
    except TextureValidationError:
        return _lenient_decode(binary, frame)


def find_usage(source: RomSource) -> dict[tuple[str, int], list[str]]:
    """Which models and levels reference each texture (slow: reads every Prop and level block)."""
    from jfg_forge.core.level_data import block_count, list_levels

    usage: dict[tuple[str, int], list[str]] = {}

    def note(key: tuple[str, int], who: str) -> None:
        users = usage.setdefault(key, [])
        if who not in users:
            users.append(who)

    for prop_id in range(PROP_COUNT):
        try:
            data = source.prop_bytes(prop_id)
            name = data[:16].split(b"\0", 1)[0].decode("ascii", errors="replace") or f"prop_{prop_id:04d}"
            model = parse_model(data)
        except Exception:  # helper props without a model
            continue
        for record in model.texture_records:
            texture_id = struct.unpack_from(">H", record, 6)[0]
            key = (BANK_A, texture_id & 0x7FFF) if texture_id & 0x8000 else (BANK_B, texture_id)
            note(key, f"model {name}")

    first_level_for_block: dict[int, str] = {}
    for level in list_levels(source):
        first_level_for_block.setdefault(level.block_id, level.name)
    for block_id in range(block_count(source)):
        block = decode_block(source, block_id)
        offset = struct.unpack_from(">I", block, 0)[0]
        count = struct.unpack_from(">h", block, 0x18)[0]
        level = first_level_for_block.get(block_id, f"block {block_id}")
        for index in range(max(count, 0)):
            texture_id = struct.unpack_from(">H", block, offset + index * 8 + 2)[0]
            note((BANK_A, texture_id), f"level {level}")
    return usage


def apply_usage(entries: tuple[TextureEntry, ...], usage: dict[tuple[str, int], list[str]]) -> tuple[TextureEntry, ...]:
    """Attach derived labels: '<first user> - WxH' (models before levels)."""
    result = []
    for entry in entries:
        users = usage.get(entry.key, [])
        ordered = sorted(users, key=lambda user: (not user.startswith("model "), users.index(user)))
        if ordered:
            first = ordered[0].split(" ", 1)[1]
            extra = f" +{len(ordered) - 1}" if len(ordered) > 1 else ""
            label = f"{first}{extra} · {entry.width}×{entry.height}"
        else:
            label = f"Unused · {entry.width}×{entry.height}"
        result.append(
            TextureEntry(entry.bank, entry.index, entry.width, entry.height, entry.format_byte,
                         entry.rom_offset, label, tuple(ordered))
        )
    return tuple(result)


__all__ = [
    "BANK_A",
    "BANK_B",
    "TextureEntry",
    "apply_usage",
    "decode_texture_entry",
    "find_usage",
    "list_textures",
]
