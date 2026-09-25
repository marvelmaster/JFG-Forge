"""Production Vela animation catalog and pose decoder.

This is a direct extraction of the Phase-2 research implementation.  The
bitstream, scratch-channel, Root-Q10, scale, Euler, and hierarchy algorithms
are intentionally unchanged.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import math
import struct
from typing import Any

from jfg_re.animation_time import runtime_interpolation_state
from jfg_re.boy_anim0_frame0 import (
    _BitReader,
    _asset_bytes,
    _float_hex,
    _local_matrix_from_stored,
    _matrix_multiply,
    _signed8,
    _signed16,
    _sine_table,
)
from jfg_re.boy_animation_catalog import _signed11
from jfg_re.boy_export import BoyExportError

PROP_ID = 218
TRANSFORM_COUNT = 28
EXPECTED_ANIMATION_COUNT = 53

def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]

def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]

def _descriptors(blob: bytes, count: int) -> tuple[list[dict[str, int]], int]:
    offset = 16
    result: list[dict[str, int]] = []
    for scalar_index in range(count):
        if offset + 2 > len(blob):
            raise BoyExportError("Vela animation descriptor table is truncated.")
        raw = _u16(blob, offset)
        item = {
            "scalar_index": scalar_index,
            "blob_offset": offset,
            "raw": raw,
            "angle_base_u16": raw & 0xFFF0,
            "angle_width": raw & 0xF,
            "scale_base": 0,
            "scale_width": 0,
        }
        offset += 2
        if raw & 0x10:
            if offset + 2 > len(blob):
                raise BoyExportError("Vela animation scale descriptor is truncated.")
            item["scale_base"] = blob[offset]
            item["scale_width"] = blob[offset + 1] & 0xF
            offset += 2
        result.append(item)
    return result, offset

def _structure(blob: bytes) -> dict[str, Any]:
    if len(blob) < 16:
        raise BoyExportError("Vela animation blob is shorter than its fixed headers.")
    frame_offset = _u16(blob, 2)
    loop_offset = _u16(blob, 6)
    control = blob[8:16]
    slots, samples, stride = control[1], control[3], control[5]
    if slots < 2 or samples == 0:
        raise BoyExportError("Vela animation control counts are invalid.")

    # gen_anim_data's internal decoder reads control+1, subtracts one, then
    # multiplies by three at the pinned US-ROM instructions below.
    # The files still serialize three descriptors for the final scratch slot;
    # those records and their per-sample bits are deliberately not consumed by
    # the runtime decoder.
    serialized, serialized_end = _descriptors(blob, slots * 3)
    runtime_count = (slots - 1) * 3
    runtime = serialized[:runtime_count]
    ignored = serialized[runtime_count:]
    if serialized_end != frame_offset:
        raise BoyExportError("Serialized Vela descriptors do not end at frame data.")

    root_widths = [control[6] >> 4, control[6] & 0xF, control[7] & 0xF]
    runtime_bits = sum(root_widths) + sum(
        item["angle_width"] + item["scale_width"] for item in runtime
    )
    serialized_bits = sum(root_widths) + sum(
        item["angle_width"] + item["scale_width"] for item in serialized
    )
    if stride == 0:
        if serialized_bits != 0:
            raise BoyExportError("Zero-stride Vela animation has nonzero sample fields.")
    elif serialized_bits > stride * 8:
        raise BoyExportError("Serialized Vela sample fields exceed the declared stride.")

    full_end = frame_offset + samples * stride
    cross_blob_lookahead = max(0, full_end - len(blob))
    if cross_blob_lookahead > 1:
        raise BoyExportError("Vela animation requires unexpected cross-blob lookahead.")

    loop = bool(blob[1] & 0xF0)
    return {
        "header_0_7_hex": blob[:8].hex(),
        "control_8_15_hex": control.hex(),
        "frame_data_offset": frame_offset,
        "loop_frame_data_offset": loop_offset,
        "transform_channel_slots": slots,
        "runtime_decoded_channel_count": slots - 1,
        "scratch_channel_index": slots - 1,
        "sample_count": samples,
        "sample_stride_bytes": stride,
        "runtime_descriptor_count": len(runtime),
        "serialized_descriptor_count": len(serialized),
        "runtime_sample_bits": runtime_bits,
        "serialized_sample_bits": serialized_bits,
        "runtime_ignored_bits_per_declared_sample": stride * 8 - runtime_bits,
        "zero_padding_bits_after_serialized_fields": stride * 8 - serialized_bits,
        "cross_blob_lookahead_bytes": cross_blob_lookahead,
        "root": {
            "format": "three signed bases << 11 plus optional Q10 samples; final /1024",
            "signed_base_values": [_signed8(control[index]) for index in (0, 2, 4)],
            "bit_widths_xyz": root_widths,
            "dynamic_axes_xyz": [width != 0 for width in root_widths],
        },
        "runtime_scale_stream_count": sum(bool(item["raw"] & 0x10) for item in runtime),
        "runtime_scale_stream_scalar_indices": [
            item["scalar_index"] for item in runtime if item["raw"] & 0x10
        ],
        "ignored_final_slot_scale_stream_count": sum(
            bool(item["raw"] & 0x10) for item in ignored
        ),
        "loop_enabled": loop,
        "loop_flag_hex": f"0x{blob[1] & 0xF0:02X}",
        "header_low_nibble": blob[1] & 0xF,
        "runtime_time_domain": f"[0,{samples})" if loop else f"[0,{samples - 1}]",
        "runtime_descriptors": runtime,
        "ignored_final_slot_descriptors": ignored,
    }

def _sample_data(
    blob: bytes,
    structure: dict[str, Any],
    index: int,
    lookahead: bytes = b"",
) -> bytes:
    if not 0 <= index < structure["sample_count"]:
        raise BoyExportError("Vela animation sample index is outside the stored range.")
    stride = structure["sample_stride_bytes"]
    offset = structure["frame_data_offset"] + index * stride
    data = (blob + lookahead)[offset : offset + stride]
    if len(data) != stride:
        raise BoyExportError("Vela animation sample lacks its declared runtime bytes.")
    return data

def _packed(
    blob: bytes,
    structure: dict[str, Any],
    index: int,
    lookahead: bytes = b"",
) -> dict[str, Any]:
    data = _sample_data(blob, structure, index, lookahead)
    reader = _BitReader(data)
    root = [reader.read(width) for width in structure["root"]["bit_widths_xyz"]]
    angles: list[int] = []
    scales: list[int] = []
    for item in structure["runtime_descriptors"]:
        angles.append(reader.read(item["angle_width"]))
        scales.append(reader.read(item["scale_width"]) if item["scale_width"] else 0)
    if reader.position != structure["runtime_sample_bits"]:
        raise BoyExportError("Vela runtime sample bit count differs from its descriptor sum.")

    ignored_angles: list[int] = []
    ignored_scales: list[int] = []
    for item in structure["ignored_final_slot_descriptors"]:
        ignored_angles.append(reader.read(item["angle_width"]))
        ignored_scales.append(reader.read(item["scale_width"]) if item["scale_width"] else 0)
    if reader.position != structure["serialized_sample_bits"]:
        raise BoyExportError("Vela serialized sample bit count differs from its descriptor sum.")
    if any(reader.read(1) for _ in range(len(data) * 8 - reader.position)):
        raise BoyExportError(f"Vela animation sample {index} has nonzero true padding bits.")
    return {
        "root": root,
        "angles": angles,
        "scales": scales,
        "ignored_final_slot_angles": ignored_angles,
        "ignored_final_slot_scales": ignored_scales,
    }

def _tables(rom: bytes) -> dict[str, Any]:
    asset40_start, _, asset40 = _asset_bytes(rom, 40)
    pair_offset = (PROP_ID & ~3) * 2 + (PROP_ID & 3) * 2
    first_half, following_half = struct.unpack_from(">HH", asset40, pair_offset)
    first, following = first_half >> 1, following_half >> 1
    if following - first != EXPECTED_ANIMATION_COUNT:
        raise BoyExportError("Vela animation count differs from 53.")

    asset41_start, _, asset41 = _asset_bytes(rom, 41)
    ids = [
        struct.unpack_from(">h", asset41, (first + index) * 2)[0]
        for index in range(EXPECTED_ANIMATION_COUNT)
    ]
    asset42_start, _, asset42 = _asset_bytes(rom, 42)
    asset43_start, _, asset43 = _asset_bytes(rom, 43)
    asset44_start, _, asset44 = _asset_bytes(rom, 44)
    map_pair_offset = (PROP_ID & ~1) * 4 + (PROP_ID & 1) * 4
    map_start, map_end = struct.unpack_from(">II", asset44, map_pair_offset)
    asset45_start, _, asset45 = _asset_bytes(rom, 45)
    map_blob = asset45[map_start:map_end]
    required = EXPECTED_ANIMATION_COUNT * TRANSFORM_COUNT
    if len(map_blob) < required:
        raise BoyExportError("Vela channel-map table is truncated.")
    return {
        "first": first,
        "following": following,
        "ids": ids,
        "asset40_pair_rom": asset40_start + pair_offset,
        "asset41_range": [asset41_start + first * 2, asset41_start + following * 2],
        "asset42_start": asset42_start,
        "asset42": asset42,
        "asset43_start": asset43_start,
        "asset43": asset43,
        "asset44_pair_rom": asset44_start + map_pair_offset,
        "map_relative_range": [map_start, map_end],
        "map_rom_range": [asset45_start + map_start, asset45_start + map_end],
        "map_blob": map_blob,
        "map_trailing_hex": map_blob[required:].hex(),
    }

def catalog_vela_animations(rom: bytes) -> dict[str, Any]:
    tables = _tables(rom)
    animations: list[dict[str, Any]] = []
    for index, animation_id in enumerate(tables["ids"]):
        start, end = struct.unpack_from(">II", tables["asset42"], animation_id * 4)
        blob = tables["asset43"][start:end]
        structure = _structure(blob)
        lookahead_count = structure["cross_blob_lookahead_bytes"]
        lookahead = tables["asset43"][end : end + lookahead_count]
        if len(lookahead) != lookahead_count:
            raise BoyExportError("Vela animation lookahead exceeds asset 43.")
        ignored_nonzero_samples = 0
        for sample_index in range(structure["sample_count"]):
            packed = _packed(blob, structure, sample_index, lookahead)
            ignored_nonzero_samples += int(
                any(packed["ignored_final_slot_angles"])
                or any(packed["ignored_final_slot_scales"])
            )
        channel_map = list(
            tables["map_blob"][
                index * TRANSFORM_COUNT : (index + 1) * TRANSFORM_COUNT
            ]
        )
        if any(channel >= structure["transform_channel_slots"] for channel in channel_map):
            raise BoyExportError("Vela channel map references a channel outside the clip.")
        animations.append(
            {
                "vela_animation_index": index,
                "animation_id": animation_id,
                "name": None,
                "name_status": "No name table was established; index and numeric ID only.",
                "asset42_offset_entry_rom_hex": f"0x{tables['asset42_start'] + animation_id * 4:X}",
                "asset43_relative_range_hex": [f"0x{start:X}", f"0x{end:X}"],
                "rom_range_hex": [
                    f"0x{tables['asset43_start'] + start:X}",
                    f"0x{tables['asset43_start'] + end:X}",
                ],
                "blob_size": len(blob),
                "blob_sha256": hashlib.sha256(blob).hexdigest(),
                "cross_blob_lookahead_hex": lookahead.hex(),
                "channel_map": channel_map,
                "channel_map_identity_0_27": channel_map == list(range(TRANSFORM_COUNT)),
                "ignored_final_slot_nonzero_sample_count": ignored_nonzero_samples,
                **{
                    key: value
                    for key, value in structure.items()
                    if key not in ("runtime_descriptors", "ignored_final_slot_descriptors")
                },
                "runtime_scale_stream_scalar_indices": structure[
                    "runtime_scale_stream_scalar_indices"
                ],
                "ignored_final_slot_descriptor_hex": [
                    f"0x{item['raw']:04X}"
                    for item in structure["ignored_final_slot_descriptors"]
                ],
            }
        )

    return {
        "schema_version": 1,
        "scope": "Prop 218 Girl: all 53 animation table entries",
        "table_chain": {
            "asset40_prop_pair_rom_hex": f"0x{tables['asset40_pair_rom']:X}",
            "global_index_range": [tables["first"], tables["following"]],
            "asset41_id_range_rom_hex": [f"0x{x:X}" for x in tables["asset41_range"]],
            "asset44_map_pair_rom_hex": f"0x{tables['asset44_pair_rom']:X}",
            "asset45_map_relative_range_hex": [
                f"0x{x:X}" for x in tables["map_relative_range"]
            ],
            "asset45_map_rom_range_hex": [f"0x{x:X}" for x in tables["map_rom_range"]],
            "map_trailing_alignment_hex": tables["map_trailing_hex"],
        },
        "animation_ids_in_index_order": tables["ids"],
        "counts": {
            "animations": len(animations),
            "unique_animation_ids": len(set(tables["ids"])),
            "looping": sum(item["loop_enabled"] for item in animations),
            "non_looping": sum(not item["loop_enabled"] for item in animations),
            "with_runtime_scale_streams": sum(
                item["runtime_scale_stream_count"] > 0 for item in animations
            ),
            "with_nonidentity_channel_map": sum(
                not item["channel_map_identity_0_27"] for item in animations
            ),
            "requiring_one_byte_contiguous_asset_lookahead": sum(
                item["cross_blob_lookahead_bytes"] == 1 for item in animations
            ),
        },
        "sample_count_distribution": {
            str(key): value
            for key, value in sorted(
                Counter(item["sample_count"] for item in animations).items()
            )
        },
        "sample_stride_distribution": {
            str(key): value
            for key, value in sorted(
                Counter(item["sample_stride_bytes"] for item in animations).items()
            )
        },
        "animations": animations,
    }

def _animation_blob(
    rom: bytes,
    animation_id: int,
) -> tuple[bytes, bytes]:
    tables = _tables(rom)
    start, end = struct.unpack_from(">II", tables["asset42"], animation_id * 4)
    blob = tables["asset43"][start:end]
    structure = _structure(blob)
    count = structure["cross_blob_lookahead_bytes"]
    return blob, tables["asset43"][end : end + count]

def decode_vela_animation_time(
    blob: bytes,
    time_value: float,
    lookahead: bytes = b"",
) -> dict[str, Any]:
    structure = _structure(blob)
    interpolation = runtime_interpolation_state(
        time_value,
        sample_count=structure["sample_count"],
        loop=structure["loop_enabled"],
    )
    current = _packed(blob, structure, interpolation.current_sample, lookahead)
    following = _packed(blob, structure, interpolation.next_sample, lookahead)
    fraction10 = interpolation.fraction_10bit

    bases = [value << 11 for value in structure["root"]["signed_base_values"]]
    root_raw = [
        base + (a << 10) + (b - a) * fraction10
        for base, a, b in zip(bases, current["root"], following["root"])
    ]
    angles: list[int] = []
    scales: list[int] = []
    for item, a, b, sa, sb in zip(
        structure["runtime_descriptors"],
        current["angles"],
        following["angles"],
        current["scales"],
        following["scales"],
    ):
        delta = _signed11(b - a)
        sample = a + ((delta * fraction10) >> 10)
        angles.append(_signed16((item["angle_base_u16"] + (sample << 5)) & 0xFFFF))
        if item["raw"] & 0x10:
            scale = (
                (item["scale_base"] << 8)
                + (sa << 8)
                + (((sb - sa) * fraction10) >> 2)
            ) & 0xFFFF
        else:
            scale = 0
        scales.append(scale)

    # gen_anim_data deliberately decodes slots-1 channels.  The final slot is
    # the zero scratch channel even when serialized ignored fields are nonzero.
    angles.extend((0, 0, 0))
    scales.extend((0, 0, 0))
    channels = []
    for channel_index in range(structure["transform_channel_slots"]):
        rotation = angles[channel_index * 3 : channel_index * 3 + 3]
        scale = scales[channel_index * 3 : channel_index * 3 + 3]
        channels.append(
            {
                "channel_index": channel_index,
                "runtime_decode_status": (
                    "decoded"
                    if channel_index < structure["runtime_decoded_channel_count"]
                    else "runtime zero scratch; serialized final-slot fields ignored"
                ),
                "rotation_raw_s16_abc": rotation,
                "rotation_index12_abc": [(value & 0xFFFF) >> 4 for value in rotation],
                "rotation_degrees_signed_abc": [
                    value * 360.0 / 65536.0 for value in rotation
                ],
                "scale_raw_u16_xyz": scale,
                "scale_factor_xyz": [
                    1.0 if value == 0 else value / 32768.0 for value in scale
                ],
            }
        )
    return {
        "time": time_value,
        "current_sample": interpolation.current_sample,
        "next_sample": interpolation.next_sample,
        "fraction_10bit": fraction10,
        "root_translation_raw_q10_xyz": root_raw,
        "root_translation_model_xyz": [value / 1024.0 for value in root_raw],
        "channels": channels,
        "ignored_final_slot_current_packed": {
            "angles": current["ignored_final_slot_angles"],
            "scales": current["ignored_final_slot_scales"],
        },
    }

def build_vela_matrices(
    vela_data: bytes,
    frame: dict[str, Any],
    rom: bytes,
    channel_map: list[int],
) -> list[dict[str, Any]]:
    transform_start = _u32(vela_data, 0x54)
    transform_count = vela_data[0x4F]
    if transform_count != TRANSFORM_COUNT or len(channel_map) != transform_count:
        raise BoyExportError("Vela transform count or channel-map length differs.")
    table = _sine_table(rom)
    identity = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    root_parent = [row[:] for row in identity]
    root_parent[3][:3] = frame["root_translation_model_xyz"]
    world_by_id: dict[int, list[list[float]]] = {}
    records: list[dict[str, Any]] = []
    for record_index in range(transform_count):
        offset = transform_start + record_index * 16
        parent_id, matrix_id = vela_data[offset], vela_data[offset + 1]
        channel_index = channel_map[record_index]
        channel = frame["channels"][channel_index]
        translation = list(struct.unpack_from(">fff", vela_data, offset + 4))
        local = _local_matrix_from_stored(
            channel["rotation_raw_s16_abc"],
            channel["scale_raw_u16_xyz"],
            translation,
            table,
        )
        if parent_id != 0xFF and parent_id not in world_by_id:
            raise BoyExportError("Vela transform hierarchy is not parent-before-child.")
        parent = root_parent if parent_id == 0xFF else world_by_id[parent_id]
        world = _matrix_multiply(local, parent)
        if not all(math.isfinite(value) for row in world for value in row):
            raise BoyExportError("Vela pose produced NaN or infinity.")
        world_by_id[matrix_id] = world
        records.append(
            {
                "record_index": record_index,
                "parent_id": parent_id,
                "matrix_id": matrix_id,
                "animation_channel": channel_index,
                "animation_channel_status": channel["runtime_decode_status"],
                "local_translation_xyz": translation,
                "rotation_raw_s16_abc": channel["rotation_raw_s16_abc"],
                "scale_raw_u16_xyz": channel["scale_raw_u16_xyz"],
                "local_matrix": local,
                "local_matrix_f32_hex": _float_hex(local),
                "world_model_matrix": world,
                "world_model_matrix_f32_hex": _float_hex(world),
            }
        )
    return records

__all__ = [
    "build_vela_matrices",
    "catalog_vela_animations",
    "decode_vela_animation_time",
]
