"""Strict decoders for N64 image formats observed in JFG texture headers.

The verified reference-image RGBA16 pipeline remains in ``textures_rgba16``.
This module decodes a model texture frame only after validating its native
header format, frame table, stride, and exact decompressed block length.
"""

from __future__ import annotations

from dataclasses import dataclass

from jfg_forge.core.texture_rgba16 import (
    HEADER_SIZE,
    TextureHeader,
    TextureValidationError,
    apply_odd_row_block_swap,
    decode_rgba5551,
)


@dataclass(frozen=True)
class DecodedModelTexture:
    header: TextureHeader
    rgba: bytes
    format_id: int
    format_name: str
    format_flags: int
    frame_count: int
    frame_stride: int
    selected_frame: int
    trailing_frame_bytes: int


_FORMAT_NAMES = {0: "RGBA32", 1: "RGBA16", 2: "I8", 3: "I4", 4: "IA16", 5: "IA8", 6: "IA4"}
# bits per texel of each header format nibble (the standard N64 image formats)
_BITS_PER_TEXEL = {0: 32, 1: 16, 2: 8, 3: 4, 4: 16, 5: 8, 6: 4}


def _swap_odd_rows(raw: bytes, width: int, bits: int, height: int) -> bytes:
    """Undo the texture memory's odd-row word swap on packed source rows.

    In every odd row the two 4-byte words of each 8-byte group are exchanged. Found
    by row smoothness: it makes IA8, I8, I4, IA16 and IA4 images continuous (the
    RGBA16 case is the verified one).
    """
    row_bytes = width * bits // 8
    out = bytearray(raw)
    for y in range(1, height, 2):
        base = y * row_bytes
        for x in range(0, row_bytes - 7, 8):
            first = base + x
            out[first : first + 4], out[first + 4 : first + 8] = raw[first + 4 : first + 8], raw[first : first + 4]
    return bytes(out)


def _small_format_rgba(format_id: int, pixels: bytes, width: int, height: int) -> bytes:
    """RGBA for the intensity formats I8, I4, IA16, IA8 and IA4 (after the odd-row swap)."""
    pixels = _swap_odd_rows(pixels, width, _BITS_PER_TEXEL[format_id], height)
    count = width * height
    rgba = bytearray(count * 4)
    if format_id == 4:  # intensity byte, then alpha byte
        for i in range(count):
            intensity, alpha = pixels[i * 2], pixels[i * 2 + 1]
            rgba[i * 4 : i * 4 + 4] = bytes((intensity, intensity, intensity, alpha))
        return bytes(rgba)
    for i in range(count):
        if format_id == 2:  # I8 (opaque: the intensity is not used as alpha here)
            intensity, alpha = pixels[i], 255
        elif format_id == 5:  # IA8: 4-bit intensity high, 4-bit alpha low
            intensity, alpha = (pixels[i] >> 4) * 17, (pixels[i] & 0x0F) * 17
        else:
            byte = pixels[i // 2]
            nibble = byte >> 4 if i % 2 == 0 else byte & 0x0F
            if format_id == 3:  # I4
                intensity, alpha = nibble * 17, 255
            else:  # IA4: 3-bit intensity, 1-bit alpha
                intensity, alpha = (nibble >> 1) * 255 // 7, (nibble & 1) * 255
        rgba[i * 4 : i * 4 + 4] = bytes((intensity, intensity, intensity, alpha))
    return bytes(rgba)


def _u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def decode_model_texture_frame(
    data: bytes,
    *,
    requested_frame: int = 0,
) -> DecodedModelTexture:
    """Decode one model texture frame for observed N64 formats 0, 1, and 5.

    `requested_frame` is the resolved frame index passed by the model group.
    JFG's runtime falls back to frame zero when the requested index is outside
    a multi-frame texture, which is reproduced here.
    """
    if len(data) < HEADER_SIZE:
        raise TextureValidationError("Model texture is shorter than its 32-byte header.")
    width, height = data[0], data[1]
    if width == 0 or height == 0:
        raise TextureValidationError("Texture width and height must be non-zero.")

    format_byte = data[2]
    format_id = format_byte & 0x0F
    format_flags = format_byte >> 4
    format_names = {0: "RGBA32", 1: "RGBA16", 5: "IA8"}
    if format_id not in format_names:
        raise TextureValidationError(f"Unsupported JFG texture format nibble {format_id}.")

    # texDPTextureX reads the BE u16 at +0x12 and shifts it right by 8.
    # This is the runtime count field, not a little-endian u16 count.
    count_word = _u16_be(data, 0x12)
    if count_word & 0x00FF:
        raise TextureValidationError("Texture frame-count low byte is non-zero.")
    frame_count = count_word >> 8
    frame_stride = _u16_be(data, 0x16)
    if frame_count < 1 or frame_stride < 1:
        raise TextureValidationError("Texture frame count and stride must be positive.")
    expected_length = HEADER_SIZE + frame_count * frame_stride
    if len(data) != expected_length:
        raise TextureValidationError(
            f"Texture block length {len(data)} differs from header plus "
            f"{frame_count} frames of {frame_stride} bytes ({expected_length})."
        )

    frame_index = requested_frame if 0 <= requested_frame < frame_count else 0
    if requested_frame < 0:
        raise TextureValidationError("Requested frame cannot be negative.")
    pixel_bytes = width * height * {0: 4, 1: 2, 5: 1}[format_id]
    tail_bytes = frame_stride - pixel_bytes
    if format_id == 1:
        # The two observed RGBA16 frame sets with tails have exactly eight
        # bytes per frame; keep those bytes accounted for but uninterpreted.
        if tail_bytes not in (0, 8):
            raise TextureValidationError("RGBA16 frame has an unrecognized trailing-byte count.")
    elif tail_bytes != 0:
        raise TextureValidationError("RGBA32/IA8 frame stride does not equal its pixel payload.")

    start = HEADER_SIZE + frame_index * frame_stride
    pixels = data[start : start + pixel_bytes]
    if format_id == 1:
        rgba = apply_odd_row_block_swap(decode_rgba5551(pixels), width, height)
    elif format_id == 0:
        rgba = pixels
    else:
        # N64 IA8 stores the 4-bit intensity in the high nibble and 4-bit
        # alpha in the low nibble, in rows whose odd ones are word-swapped.
        rgba = _small_format_rgba(5, pixels, width, height)

    return DecodedModelTexture(
        header=TextureHeader(width=width, height=height, raw=data[:HEADER_SIZE]),
        rgba=rgba,
        format_id=format_id,
        format_name=format_names[format_id],
        format_flags=format_flags,
        frame_count=frame_count,
        frame_stride=frame_stride,
        selected_frame=frame_index,
        trailing_frame_bytes=tail_bytes,
    )


def decode_model_texture_lenient(binary: bytes, frame: int = 0) -> DecodedModelTexture:
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
    if width == 0 or height == 0 or format_id not in _BITS_PER_TEXEL:
        raise TextureValidationError("Unsupported texture layout.")
    pixel_bytes = width * height * _BITS_PER_TEXEL[format_id] // 8
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
        rgba = _small_format_rgba(format_id, pixels, width, height)
    return DecodedModelTexture(
        header=TextureHeader(width=width, height=height, raw=binary[:HEADER_SIZE]),
        rgba=rgba,
        format_id=format_id,
        format_name=_FORMAT_NAMES[format_id],
        format_flags=binary[2] >> 4,
        frame_count=frame_count,
        frame_stride=stride,
        selected_frame=chosen,
        trailing_frame_bytes=stride - pixel_bytes,
    )
