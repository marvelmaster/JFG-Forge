"""Reproducible Vela Phase-2 animation and runtime-path analysis.

This research helper deliberately leaves the production Boy/JFG Forge path
unchanged.  It reuses the established JFG bit reader, interpolation, matrix,
and compact-model helpers, while deriving Vela's catalog and 28-node mapping
directly from the pinned US ROM.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from jfg_re.animation_time import runtime_interpolation_state  # noqa: E402
from jfg_re.boy_anim0_frame0 import (  # noqa: E402
    _BitReader,
    _asset_bytes,
    _float_hex,
    _local_matrix_from_stored,
    _matrix_multiply,
    _signed8,
    _signed16,
    _sine_table,
    _transform,
)
from jfg_re.boy_animation_catalog import _signed11  # noqa: E402
from jfg_re.boy_export import BoyExportError, _matrix_id, parse_model  # noqa: E402
from jfg_re.props import validate_rom_identity  # noqa: E402


PROP_ID = 218
TRANSFORM_COUNT = 28
EXPECTED_ANIMATION_COUNT = 53
EXPECTED_PROP_SHA256 = "daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409"
REFERENCE_INDEX = 0
REFERENCE_ID = 1097
REFERENCE_TIMES = (0.0, 1.0, 7.5, 8.0, 15.0)

GIRL_OVERLAY_VRAM = 0x00F00000
GIRL_OVERLAY_ROM = 0x1F13980
MAIN_VRAM = 0x80000400
MAIN_ROM = 0x1000


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _word(rom: bytes, address: int, *, overlay: bool = False) -> int:
    offset = (
        GIRL_OVERLAY_ROM + address - GIRL_OVERLAY_VRAM
        if overlay
        else MAIN_ROM + address - MAIN_VRAM
    )
    return _u32(rom, offset)


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


def _active_assignments(vela_data: bytes) -> tuple[Any, dict[int, int], int]:
    model = parse_model(vela_data)
    assignments: dict[int, int] = {}
    faces = 0
    for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
        if group.runtime_skipped:
            continue
        faces += following.triangle_start - group.triangle_start
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            for local_index in triangle.local_indices:
                vertex_index = group.vertex_start + local_index
                matrix_id = _matrix_id(group, local_index)
                if matrix_id is None:
                    raise BoyExportError("Active Vela vertex lacks a matrix assignment.")
                previous = assignments.setdefault(vertex_index, matrix_id)
                if previous != matrix_id:
                    raise BoyExportError("Active Vela vertex has conflicting matrix assignments.")
    return model, assignments, faces


def _bbox(points: list[list[float]]) -> dict[str, list[float]]:
    return {
        "minimum": [min(point[axis] for point in points) for axis in range(3)],
        "maximum": [max(point[axis] for point in points) for axis in range(3)],
    }


def _pose_summary(
    vela_data: bytes,
    rom: bytes,
    blob: bytes,
    lookahead: bytes,
    channel_map: list[int],
    time_value: float,
) -> dict[str, Any]:
    frame = decode_vela_animation_time(blob, time_value, lookahead)
    matrices = build_vela_matrices(vela_data, frame, rom, channel_map)
    model, assignments, faces = _active_assignments(vela_data)
    by_id = {record["matrix_id"]: record["world_model_matrix"] for record in matrices}
    points = [
        _transform(model.vertices[index], by_id[matrix_id])[0]
        for index, matrix_id in sorted(assignments.items())
    ]
    origins = [record["world_model_matrix"][3][:3] for record in matrices]
    payload = b"".join(
        struct.pack(">f", value)
        for record in matrices
        for row in record["world_model_matrix"]
        for value in row
    )
    return {
        "time": time_value,
        "interpolation": {
            key: frame[key] for key in ("current_sample", "next_sample", "fraction_10bit")
        },
        "root_translation_model_xyz": frame["root_translation_model_xyz"],
        "matrix_count": len(matrices),
        "matrix_sha256_f32be_4x4": hashlib.sha256(payload).hexdigest(),
        "joint_origin_bbox": _bbox(origins),
        "transformed_referenced_vertex_count": len(points),
        "transformed_vertex_bbox": _bbox(points),
        "maximum_absolute_coordinate": max(abs(value) for point in points for value in point),
        "all_finite": all(math.isfinite(value) for point in points for value in point),
        "active_face_count": faces,
        "matrix_origins": origins,
    }


def _runtime_evidence(rom: bytes, vela_data: bytes) -> dict[str, Any]:
    pins = {
        # Girl overlay: the same model-generation call sequence already
        # identified in Boy at 0x0100167C/0x010016B4/0x010016EC.
        (0x00F01728, True): 0x8C910000,
        (0x00F01740, True): 0x0C000000,
        (0x00F01778, True): 0x0C000000,
        (0x00F0177C, True): 0x02203025,
        (0x00F017AC, True): 0x8D670010,
        (0x00F017B0, True): 0x0C000000,
        # Generic animation-channel and render-group loops.
        (0x8003D5CC, False): 0x8263004F,
        (0x8003D5D0, False): 0x94C90024,
        (0x8003D604, False): 0xA1EB0002,
        (0x8003BF10, False): 0x0C00F776,
        (0x8003BF58, False): 0x0C00F776,
        (0x8003BF7C, False): 0x0C00F776,
        (0x8003BFAC, False): 0x0C00F776,
        (0x8003DF34, False): 0x30590400,
        (0x8003DF44, False): 0x172000C4,
        # Runtime descriptor count = (control[1] - 1) * 3.
        (0x800743E8, False): 0x90EE0001,
        (0x800743F4, False): 0x25CEFFFF,
        (0x800743F8, False): 0x000E7840,
        (0x800743FC, False): 0x01CF7021,
        # objMakeGunMtx dynamically selects reference-record-0's matrix.
        (0x8000BCE0, False): 0x8CD90030,
        (0x8000BCE8, False): 0x972A0002,
        (0x8000BCF8, False): 0x000A5980,
        (0x8000BD00, False): 0x016E2021,
    }
    checked = []
    for (address, overlay), expected in pins.items():
        actual = _word(rom, address, overlay=overlay)
        if actual != expected:
            raise BoyExportError(f"Pinned Vela runtime instruction differs at 0x{address:08X}.")
        checked.append(
            {
                "address": f"0x{address:08X}",
                "word": f"0x{actual:08X}",
                "segment": "overlay15 Girl" if overlay else "main",
            }
        )

    reference_start = _u32(vela_data, 0x30)
    reference_vertex, reference_matrix = struct.unpack_from(">HH", vela_data, reference_start)
    return {
        "checked_instruction_count": len(checked),
        "instructions": checked,
        "girl_overlay": {
            "girlControl": "0x00F00000",
            "modGenAnimMatrices_call": "0x00F01740",
            "objMakeGunMtx_call": "0x00F01778",
            "lightObject_call": "0x00F017B0",
            "relocation_resolution": (
                "overlay 15 relocation entries 84/85/86 resolve these calls to "
                "0x8003D21C, 0x8000BC28, and 0x800221F0 respectively"
            ),
            "character_specific_input": "Prop 218 model pointer, 28 transform count, per-animation 28-byte channel map, and Girl overlay selectors/state",
        },
        "runtime_animation": {
            "modGenAnimMatrices": "0x8003D21C",
            "gen_anim_data": "0x80073E80",
            "channel_map_copy": "0x8003D5CC..0x8003D618 reads model +0x4F and copies one map byte to transform +2",
            "descriptor_count": "0x800743E8..0x800743FC computes (control[1]-1)*3",
            "matrix_semantics": "same generic row-vector hierarchy and Rx(A)*Ry(C)*Rz(B) implementation used by Boy",
            "stored_component_mapping": "stored [A,C,B] is passed to the established helper as [stored0,stored2,stored1]",
        },
        "geometry": {
            "generic_group_flag_test": "makeModelGfx 0x8003DF34 masks 0x400 and 0x8003DF44 skips the group",
            "Vela_load_path": "playerGirl object definition 0 selects Prop 218; objSetupObject reaches generic modLoadModel 0x8003B9E8",
            "makeModelGfx_calls": ["0x8003BF10", "0x8003BF58", "0x8003BF7C", "0x8003BFAC"],
            "branch_coverage": "the inspected successful modLoadModel branches all reach at least one of these makeModelGfx calls",
        },
        "girlgun": {
            "player_object_definition": 0,
            "player_behaviour_id": 1,
            "child_object_definition": 397,
            "first_reference_record": {
                "vertex_id": reference_vertex,
                "matrix_id": reference_matrix,
            },
            "objMakeGunMtx_dataflow": [
                "0x8000BCE0 loads model +0x30 reference-table pointer",
                "0x8000BCE8 loads reference record 0 matrix ID +2",
                "0x8000BCF8 multiplies that ID by the 0x40 runtime-matrix stride",
                "0x8000BD00 forms the selected matrix address and the following loop copies it",
            ],
            "result": "GirlGun_world = Vela_matrix_6; GirlGun_local = identity",
            "attachment_matrix_id": reference_matrix,
        },
    }


def _attachment_models(phase1: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for slot in phase1["objects_and_attachments"]["girlgun"]["model_slots"]:
        matches = list(
            (PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins").glob(
                f"{slot['prop_id']:04d}_*.bin"
            )
        )
        if len(matches) != 1:
            raise BoyExportError(f"Expected one canonical Prop {slot['prop_id']} attachment.")
        data = matches[0].read_bytes()
        model = parse_model(data)
        active_matrix_ids = sorted(
            {
                matrix_id
                for group in model.groups
                if not group.runtime_skipped
                for matrix_id in group.matrix_ids
                if matrix_id != 0xFF
            }
        )
        result.append(
            {
                **slot,
                "transform_record_count": data[0x4F],
                "active_group_matrix_ids": active_matrix_ids,
                "placement": "rigid model-local geometry under the external GirlGun transform",
            }
        )
    return result


def analyze(rom_path: Path, prop_path: Path, phase1_path: Path) -> dict[str, Any]:
    identity = validate_rom_identity(rom_path)
    rom = identity.path.read_bytes()
    vela_data = prop_path.read_bytes()
    if hashlib.sha256(vela_data).hexdigest() != EXPECTED_PROP_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 218 Girl binary.")
    phase1 = json.loads(phase1_path.read_text(encoding="utf-8"))
    if phase1["identity"]["prop_id"] != PROP_ID:
        raise BoyExportError("Phase-1 evidence is not for Prop 218.")

    catalog = catalog_vela_animations(rom)
    reference = catalog["animations"][REFERENCE_INDEX]
    if reference["animation_id"] != REFERENCE_ID:
        raise BoyExportError("Pinned Vela reference animation differs.")
    blob, lookahead = _animation_blob(rom, REFERENCE_ID)
    samples = [
        _pose_summary(
            vela_data,
            rom,
            blob,
            lookahead,
            reference["channel_map"],
            time_value,
        )
        for time_value in REFERENCE_TIMES
    ]
    geometry = phase1["geometry"]
    runtime = _runtime_evidence(rom, vela_data)
    attachments = _attachment_models(phase1)
    return {
        "schema_version": 1,
        "scope": "Vela Phase 2: animation source, isolated reference pose, generic runtime path, geometry flag, and GirlGun socket",
        "inputs": {
            "rom_sha1": identity.sha1,
            "prop_id": PROP_ID,
            "prop_sha256": EXPECTED_PROP_SHA256,
            "existing_vela_runtime_capture_found": False,
            "existing_scene_ripper_captures_checked": [
                "boy-test-001",
                "boy-test-002",
                "boy-test-003",
            ],
        },
        "catalog": catalog,
        "reference_animation": {
            "index": REFERENCE_INDEX,
            "animation_id": REFERENCE_ID,
            "semantic_name": None,
            "gameplay_context": "UNKNOWN",
            "selection_reason": (
                "First catalog entry and generic instance initialization value; it exercises the only "
                "29-slot/nonidentity map, Root-Q10 Y, one active scale triplet, and looping interpolation. "
                "It is a technical reference, not a claimed gameplay name or universal default."
            ),
            "catalog_record": reference,
            "times": list(REFERENCE_TIMES),
            "pose_samples": samples,
            "reference_time_7_5_world_matrices": build_vela_matrices(
                vela_data,
                decode_vela_animation_time(blob, 7.5, lookahead),
                rom,
                reference["channel_map"],
            ),
        },
        "geometry_validation": {
            "stored_vertices": geometry["stored_vertices"],
            "admitted_groups": geometry["active_group_count"],
            "skipped_groups": geometry["skipped_group_count"],
            "runtime_visible_faces": geometry["active_nondegenerate_faces"],
            "referenced_vertices": geometry["active_referenced_source_vertices"],
            "matrix_assignment_conflicts": geometry[
                "active_vertex_matrix_assignment_conflicts"
            ],
            "active_matrix_ids": geometry["active_matrix_ids"],
            "all_reference_samples_finite": all(sample["all_finite"] for sample in samples),
            "confidence": "VERIFIED for the generic makeModelGfx path and this Prop 218 submission; capture-visible count remains available as an independent future check",
        },
        "runtime_evidence": runtime,
        "girlgun_attachment_models": attachments,
        "confidence": {
            "Vela_animation_table_and_blob_structure": "VERIFIED from ROM tables and complete parse of all 53 entries",
            "Root_Q10": "VERIFIED generic runtime format used by Vela's modGenAnimMatrices/gen_anim_data path",
            "Euler_A_C_B_mapping": "VERIFIED generic runtime code path; Vela numerical matrices still lack an independent live capture",
            "row_vector_hierarchy": "VERIFIED generic runtime code path; isolated research pose is structurally validated",
            "reference_pose_numeric_runtime_match": "UNKNOWN until a real Vela matrix capture is compared",
            "selector_values_for_reference_pose": "UNKNOWN; isolated clip uses no captured selectors",
            "GirlGun_matrix_6_socket": "VERIFIED from Vela call site, Prop 218 reference record 0, and objMakeGunMtx data flow",
            "Prop291_precise_unarmed_state": "LIKELY; it is verified as GirlGun slot 8 and rigid VelaHand geometry, but the complete state selector was not traced",
            "Vela_452_face_runtime_path": "VERIFIED statically from playerGirl -> Prop 218 -> modLoadModel -> makeModelGfx and the generic 0x400 branch",
        },
        "generic_comparison": {
            "GENERIC_VERIFIED": [
                "compact model header and texture/group/triangle/vertex record shapes",
                "rigid group matrix split and 4-byte vertex-reference records",
                "16-byte transform records and row-vector hierarchy evaluation",
                "animation table chain and MSB-first packed bitstream",
                "Root-Q10 and optional scale streams",
                "stored A/C/B component mapping through the shared gen_anim_data path",
                "child weapon object system and reference-record-0 socket extraction",
                "makeModelGfx group flag 0x400 exclusion",
            ],
            "GENERIC_LIKELY": [
                "slot 8 as the ordinary unarmed hand/fallback state",
                "higher-level player selector meanings beyond the inspected call sequence",
            ],
            "CHARACTER_SPECIFIC": [
                "animation count, index-to-ID list, strides, channel maps, and timing metadata",
                "transform count, hierarchy, translations, active matrix subsets, and reference vertices",
                "Girl overlay selector construction and GirlGun Props 283..291",
            ],
            "STILL_UNKNOWN": [
                "semantic names and gameplay contexts for the 53 animation entries",
                "live selector/transition/object state for the isolated reference frame",
                "pixel format of Vela texture ID 0x874A",
            ],
        },
        "runtime_capture": {
            "required_for_exact_numeric_matrix_validation": True,
            "breakpoint": "first instruction after gen_anim_data returns inside modGenAnimMatrices (same main-code site used for Boy, 0x8003D908)",
            "minimum_files": {
                "capture.txt": "PC, current/previous animation indices, blend counter/state, model/character identity, and source pointer addresses",
                "instance_n64.bin": "model instance through at least +0x60, including effective time +0x28 and unscaled time +0x38",
                "object_matrix_n64.bin": "the 0x40-byte object/world matrix passed to gen_anim_data",
                "selectors_n64.bin": "racer/player selector list through 0x1000 terminator",
                "matrices_n64.bin": "28 consecutive 0x40-byte runtime matrix slots",
            },
            "optional_attachment_check": "capture the GirlGun output matrix from objMakeGunMtx and compare it with runtime matrix slot 6",
            "capture_safety": "Use DebugMemGetPointer-backed RDRAM dumps while execution is stopped; do not call executeCodeEx on the suspended emulator thread.",
        },
    }


def report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--prop", type=Path, required=True)
    parser.add_argument("--phase1", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.rom, args.prop, args.phase1)
    payload = report_bytes(report)
    if args.output is None:
        sys.stdout.buffer.write(payload)
    else:
        args.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
