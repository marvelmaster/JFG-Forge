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
        # alpha in the low nibble.
        rgba_out = bytearray(width * height * 4)
        for index, pixel in enumerate(pixels):
            intensity = ((pixel >> 4) & 0x0F) * 17
            alpha = (pixel & 0x0F) * 17
            rgba_out[index * 4 : index * 4 + 4] = bytes(
                (intensity, intensity, intensity, alpha)
            )
        rgba = bytes(rgba_out)

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
