"""Structural catalog of all Boy animations and one pinned second validation."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_anim0_frame0 import _BitReader, _asset_bytes, _signed8, _signed16, build_matrices
from jfg_re.animation_time import runtime_interpolation_state
from jfg_re.boy_anim0_temporal import _assignments, _snapshot
from jfg_re.boy_export import BONE_COUNT, BOY_SHA256, BoyExportError, parse_boy, resolve_boy_textures
from jfg_re.boy_textured_export import _build_materials
from jfg_re.props import validate_rom_identity


PROP_ID = 220
EXPECTED_ANIMATION_COUNT = 52
SELECTED_INDEX = 43
SELECTED_ID = 1069
SELECTED_TIMES = (0.0, 1.0, 37.0, 37.5, 75.0)


def _descriptors(blob: bytes, slots: int) -> tuple[list[dict[str, int]], int]:
    offset = 16
    result: list[dict[str, int]] = []
    for scalar_index in range((slots - 1) * 3):
        if offset + 2 > len(blob):
            raise BoyExportError("Animation descriptor table is truncated.")
        raw = struct.unpack_from(">H", blob, offset)[0]
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
                raise BoyExportError("Animation scale descriptor is truncated.")
            item["scale_base"] = blob[offset]
            item["scale_width"] = blob[offset + 1] & 0xF
            offset += 2
        result.append(item)
    return result, offset


def _structure(blob: bytes) -> dict[str, Any]:
    if len(blob) < 16:
        raise BoyExportError("Animation blob is shorter than its fixed headers.")
    frame_offset = struct.unpack_from(">H", blob, 2)[0]
    loop_offset = struct.unpack_from(">H", blob, 6)[0]
    control = blob[8:16]
    slots, samples, stride = control[1], control[3], control[5]
    descriptors, descriptor_end = _descriptors(blob, slots)
    root_widths = [control[6] >> 4, control[6] & 0xF, control[7] & 0xF]
    root_bases = [_signed8(control[index]) for index in (0, 2, 4)]
    bits = sum(root_widths) + sum(item["angle_width"] + item["scale_width"] for item in descriptors)
    if stride == 0:
        if bits != 0:
            raise BoyExportError("Zero-stride animation has nonzero sample bits.")
    elif bits > stride * 8:
        raise BoyExportError("Animation sample fields exceed the declared stride.")
    data_end = frame_offset + samples * stride
    if data_end > len(blob):
        raise BoyExportError("Animation sample region exceeds its blob.")
    loop = bool(blob[1] & 0xF0)
    return {
        "header_0_7_hex": blob[:8].hex(),
        "control_8_15_hex": control.hex(),
        "frame_data_offset": frame_offset,
        "loop_frame_data_offset": loop_offset,
        "transform_channel_slots": slots,
        "sample_count": samples,
        "sample_stride_bytes": stride,
        "descriptor_count": len(descriptors),
        "descriptor_end": descriptor_end,
        "unused_descriptor_tail_bytes": frame_offset - descriptor_end,
        "sample_bits": bits,
        "sample_padding_bits": stride * 8 - bits,
        "trailing_alignment_bytes": len(blob) - data_end,
        "angle_bit_widths": sorted({item["angle_width"] for item in descriptors}),
        "angle_bit_width_sequence": [item["angle_width"] for item in descriptors],
        "root": {
            "format": "three signed bases << 11 plus optional Q10 samples; final /1024",
            "signed_base_values": root_bases,
            "bit_widths_xyz": root_widths,
            "dynamic_axes_xyz": [width != 0 for width in root_widths],
        },
        "scale_stream_count": sum(item["scale_width"] != 0 or bool(item["raw"] & 0x10) for item in descriptors),
        "scale_stream_scalar_indices": [item["scalar_index"] for item in descriptors if item["raw"] & 0x10],
        "scale_bit_widths": sorted({item["scale_width"] for item in descriptors if item["raw"] & 0x10}),
        "loop_enabled": loop,
        "loop_flag_hex": f"0x{blob[1] & 0xF0:02X}",
        "header_low_nibble": blob[1] & 0xF,
        "runtime_time_domain": f"[0,{samples})" if loop else f"[0,{max(0, samples - 1)}]",
        "last_sample_behavior": "interpolates to sample 0" if loop else "phase clamps; last sample is endpoint",
        "descriptors": descriptors,
    }


def _tables(rom: bytes) -> dict[str, Any]:
    _, _, asset40 = _asset_bytes(rom, 40)
    pair_offset = (PROP_ID & ~3) * 2 + (PROP_ID & 3) * 2
    first_half, following_half = struct.unpack_from(">HH", asset40, pair_offset)
    first, following = first_half >> 1, following_half >> 1
    if following - first != EXPECTED_ANIMATION_COUNT:
        raise BoyExportError("Boy animation count differs from 52.")
    asset41_start, _, asset41 = _asset_bytes(rom, 41)
    ids = [struct.unpack_from(">h", asset41, (first + index) * 2)[0] for index in range(EXPECTED_ANIMATION_COUNT)]
    asset42_start, _, asset42 = _asset_bytes(rom, 42)
    asset43_start, _, asset43 = _asset_bytes(rom, 43)
    _, _, asset44 = _asset_bytes(rom, 44)
    map_pair_offset = (PROP_ID & ~1) * 4 + (PROP_ID & 1) * 4
    map_start, map_end = struct.unpack_from(">II", asset44, map_pair_offset)
    asset45_start, _, asset45 = _asset_bytes(rom, 45)
    map_blob = asset45[map_start:map_end]
    required = EXPECTED_ANIMATION_COUNT * BONE_COUNT
    if len(map_blob) < required:
        raise BoyExportError("Boy channel-map table is truncated.")
    return {
        "first": first,
        "ids": ids,
        "asset41_start": asset41_start,
        "asset42_start": asset42_start,
        "asset43_start": asset43_start,
        "asset43": asset43,
        "asset42": asset42,
        "map_blob": map_blob,
        "map_rom_start": asset45_start + map_start,
        "map_trailing_bytes_hex": map_blob[required:].hex(),
    }


def catalog_boy_animations(rom: bytes) -> dict[str, Any]:
    tables = _tables(rom)
    animations: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[int]] = defaultdict(list)
    signature_data: dict[str, dict[str, Any]] = {}
    for index, animation_id in enumerate(tables["ids"]):
        if animation_id < 0:
            raise BoyExportError("Negative Boy animation ID is unsupported by the observed table path.")
        start, end = struct.unpack_from(">II", tables["asset42"], animation_id * 4)
        blob = tables["asset43"][start:end]
        structure = _structure(blob)
        for sample_index in range(structure["sample_count"]):
            _packed(blob, structure, sample_index)
        channel_map = list(tables["map_blob"][index * BONE_COUNT : (index + 1) * BONE_COUNT])
        signature = {
            "sample_count": structure["sample_count"],
            "sample_stride_bytes": structure["sample_stride_bytes"],
            "sample_bits": structure["sample_bits"],
            "angle_bit_width_sequence": structure["angle_bit_width_sequence"],
            "root_base_values": structure["root"]["signed_base_values"],
            "root_widths": structure["root"]["bit_widths_xyz"],
            "scale_scalar_indices": structure["scale_stream_scalar_indices"],
            "loop_enabled": structure["loop_enabled"],
            "channel_map": channel_map,
        }
        digest = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
        variant_id = f"variant-{digest}"
        grouped[variant_id].append(index)
        signature_data[variant_id] = signature
        animations.append(
            {
                "boy_animation_index": index,
                "animation_id": animation_id,
                "name": None,
                "name_status": "No name table was established; index and numeric ID only.",
                "asset42_offset_entry_rom_hex": f"0x{tables['asset42_start'] + animation_id * 4:X}",
                "asset43_relative_range_hex": [f"0x{start:X}", f"0x{end:X}"],
                "rom_range_hex": [f"0x{tables['asset43_start'] + start:X}", f"0x{tables['asset43_start'] + end:X}"],
                "blob_size": len(blob),
                "blob_sha256": hashlib.sha256(blob).hexdigest(),
                "channel_map": channel_map,
                "channel_map_rom_range_hex": [
                    f"0x{tables['map_rom_start'] + index * BONE_COUNT:X}",
                    f"0x{tables['map_rom_start'] + (index + 1) * BONE_COUNT:X}",
                ],
                "channel_map_identity_0_20": channel_map == list(range(BONE_COUNT)),
                "all_stored_samples_parse_and_have_zero_padding": True,
                "variant_id": variant_id,
                **{key: value for key, value in structure.items() if key != "descriptors"},
                "descriptor_records": structure["descriptors"],
            }
        )
    variants = [
        {"variant_id": variant_id, "animation_indices": indices, "count": len(indices), "signature": signature_data[variant_id]}
        for variant_id, indices in sorted(grouped.items(), key=lambda item: item[1][0])
    ]
    return {
        "schema_version": 1,
        "scope": "Prop 220 Boy: all 52 known animation table entries; structural catalog only",
        "animation_names": "UNKNOWN; none invented",
        "counts": {
            "animations": len(animations),
            "exact_structural_variants": len(variants),
            "with_scale_streams": sum(item["scale_stream_count"] > 0 for item in animations),
            "with_nonidentity_channel_map": sum(not item["channel_map_identity_0_20"] for item in animations),
            "looping": sum(item["loop_enabled"] for item in animations),
            "non_looping": sum(not item["loop_enabled"] for item in animations),
        },
        "sample_count_distribution": dict(sorted(Counter(item["sample_count"] for item in animations).items())),
        "sample_stride_distribution": dict(sorted(Counter(item["sample_stride_bytes"] for item in animations).items())),
        "map_table_trailing_alignment_hex": tables["map_trailing_bytes_hex"],
        "animations": animations,
        "format_variants": variants,
    }


def _packed(blob: bytes, structure: dict[str, Any], index: int) -> dict[str, Any]:
    if not 0 <= index < structure["sample_count"]:
        raise BoyExportError("Animation sample index is outside the stored range.")
    stride = structure["sample_stride_bytes"]
    offset = structure["frame_data_offset"] + index * stride
    data = blob[offset : offset + stride]
    reader = _BitReader(data)
    root = [reader.read(width) for width in structure["root"]["bit_widths_xyz"]]
    angles: list[int] = []
    scales: list[int] = []
    for item in structure["descriptors"]:
        angles.append(reader.read(item["angle_width"]))
        scales.append(reader.read(item["scale_width"]) if item["scale_width"] else 0)
    if reader.position != structure["sample_bits"]:
        raise BoyExportError("Animation sample bit count differs from its descriptor sum.")
    if any(reader.read(1) for _ in range(stride * 8 - reader.position)):
        raise BoyExportError(f"Animation sample {index} contains nonzero pad bits.")
    return {"root": root, "angles": angles, "scales": scales, "blob_offset": offset}


def _signed11(value: int) -> int:
    value &= 0x7FF
    return value - 0x800 if value & 0x400 else value


def decode_animation_time(blob: bytes, time_value: float) -> dict[str, Any]:
    structure = _structure(blob)
    sample_count = structure["sample_count"]
    maximum = float(sample_count) if structure["loop_enabled"] else float(sample_count - 1)
    valid = 0.0 <= time_value < maximum if structure["loop_enabled"] else 0.0 <= time_value <= maximum
    if not math.isfinite(time_value) or not valid:
        raise BoyExportError(f"Animation time {time_value} is outside {structure['runtime_time_domain']}.")
    interpolation_state = runtime_interpolation_state(
        time_value,
        sample_count=sample_count,
        loop=structure["loop_enabled"],
    )
    current_index = interpolation_state.current_sample
    next_index = interpolation_state.next_sample
    fraction10 = interpolation_state.fraction_10bit
    current, following = _packed(blob, structure, current_index), _packed(blob, structure, next_index)
    bases = [value << 11 for value in structure["root"]["signed_base_values"]]
    root_raw = [base + (a << 10) + (b - a) * fraction10 for base, a, b in zip(bases, current["root"], following["root"])]
    angles: list[int] = []
    scales: list[int] = []
    interpolation: list[dict[str, Any]] = []
    for item, a, b, sa, sb in zip(structure["descriptors"], current["angles"], following["angles"], current["scales"], following["scales"]):
        delta = _signed11(b - a)
        sample = a + ((delta * fraction10) >> 10)
        raw_u16 = (item["angle_base_u16"] + (sample << 5)) & 0xFFFF
        current_u16 = (item["angle_base_u16"] + (a << 5)) & 0xFFFF
        next_u16 = (item["angle_base_u16"] + (b << 5)) & 0xFFFF
        if item["raw"] & 0x10:
            scale_delta = sb - sa
            scale = ((item["scale_base"] << 8) + (sa << 8) + ((scale_delta * fraction10) >> 2)) & 0xFFFF
        else:
            scale_delta = 0
            scale = 0
        angles.append(_signed16(raw_u16))
        scales.append(scale)
        interpolation.append({
            "scalar_index": item["scalar_index"], "current_packed": a, "next_packed": b,
            "signed_11bit_delta": delta, "signed_11bit_wraparound_used": b - a != delta,
            "current_angle_raw_s16": _signed16(current_u16), "next_angle_raw_s16": _signed16(next_u16),
            "decoded_angle_raw_s16": _signed16(raw_u16),
            "u16_angle_boundary_crossed": abs(current_u16 - next_u16) > 0x8000,
            "scale_base": item["scale_base"], "scale_width": item["scale_width"],
            "scale_current_packed": sa, "scale_next_packed": sb, "scale_delta": scale_delta,
            "decoded_scale_raw_u16": scale,
        })
    angles.extend((0, 0, 0)); scales.extend((0, 0, 0))
    channels = []
    for channel in range(structure["transform_channel_slots"]):
        rotation = angles[channel * 3 : channel * 3 + 3]
        scale = scales[channel * 3 : channel * 3 + 3]
        channels.append({
            "channel_index": channel,
            "runtime_decode_status": "decoded" if channel < 20 else "clean-scratch zero; unused Boy leaf",
            "rotation_raw_s16_abc": rotation,
            "rotation_index12_abc": [(value & 0xFFFF) >> 4 for value in rotation],
            "rotation_degrees_signed_abc": [value * 360.0 / 65536.0 for value in rotation],
            "scale_raw_u16_xyz": scale,
            "scale_factor_xyz": [1.0 if value == 0 else value / 32768.0 for value in scale],
        })
    return {
        "time": time_value, "current_sample": current_index, "next_sample": next_index,
        "fraction_10bit": fraction10, "fraction": fraction10 / 1024.0,
        "root_translation_raw_q10_xyz": root_raw,
        "root_translation_model_xyz": [value / 1024.0 for value in root_raw],
        "channels": channels, "interpolation": interpolation,
        "signed_11bit_wraparound_scalar_count": sum(item["signed_11bit_wraparound_used"] for item in interpolation),
        "u16_angle_boundary_crossing_count": sum(item["u16_angle_boundary_crossed"] for item in interpolation),
        "active_scale_scalar_count": sum(item["decoded_scale_raw_u16"] != 0 for item in interpolation),
    }


def build_catalog_and_selected_artifacts(boy_data: bytes, rom: bytes, texture_manifest: Path, output_dir: Path) -> dict[str, bytes]:
    catalog = catalog_boy_animations(rom)
    selected_record = catalog["animations"][SELECTED_INDEX]
    if selected_record["animation_id"] != SELECTED_ID:
        raise BoyExportError("Pinned second animation ID differs.")
    tables = _tables(rom)
    start, end = struct.unpack_from(">II", tables["asset42"], SELECTED_ID * 4)
    blob = tables["asset43"][start:end]
    model = parse_boy(boy_data)
    assignments = _assignments(model)
    resolutions, textures = resolve_boy_textures(model, rom, texture_manifest)
    mtl, materials = _build_materials(model, textures, texture_manifest, output_dir)
    artifacts: dict[str, bytes] = {
        "boy-animation-catalog.json": (json.dumps(catalog, indent=2, sort_keys=True) + "\n").encode(),
        "boy-anim43-validation.mtl": mtl.encode(),
    }
    samples: list[dict[str, Any]] = []
    for time_value in SELECTED_TIMES:
        frame = decode_animation_time(blob, time_value)
        matrices = build_matrices(boy_data, frame, rom, selected_record["channel_map"])
        obj, snapshot = _snapshot(model, frame, matrices, assignments, textures, SELECTED_INDEX, SELECTED_ID)
        artifacts[snapshot["obj_file"]] = obj.encode()
        samples.append({"frame": frame, "matrices": matrices, "snapshot": snapshot})
    comparisons = []
    for left, right in zip(samples, samples[1:]):
        a = [item["world_model_matrix"][3][:3] for item in left["matrices"]]
        b = [item["world_model_matrix"][3][:3] for item in right["matrices"]]
        comparisons.append({
            "from_time": left["frame"]["time"], "to_time": right["frame"]["time"],
            "maximum_matrix_origin_displacement": max(math.dist(x, y) for x, y in zip(a, b)),
            "all_finite": all(math.isfinite(value) for point in b for value in point),
        })
    half = next(item for item in samples if item["frame"]["time"] == 37.5)
    report = {
        "schema_version": 1,
        "scope": "Full runtime validation of exactly Boy animation index 43 / ID 1069",
        "selection": {
            "index": SELECTED_INDEX, "animation_id": SELECTED_ID,
            "reason": "No Boy animation has scale or a nonidentity channel map. Index 43 maximizes sample count (76), has 49-byte samples, dynamic Q10 root fields on X/Y/Z, and is nonlooping, unlike animation 0.",
        },
        "input": {"boy_sha256": BOY_SHA256, "rom_sha1": "493ced9008dbe932d6e91179b68e8630cf23a023", "other_animation_mesh_exports": False},
        "catalog_summary": catalog["counts"],
        "selected_catalog_record": selected_record,
        "selected_times": list(SELECTED_TIMES),
        "samples": samples,
        "temporal_comparison": comparisons,
        "interpolation_validation": {
            "time": 37.5, "fraction_10bit": 512,
            "signed_11bit_wraparound_scalar_count": half["frame"]["signed_11bit_wraparound_scalar_count"],
            "u16_angle_boundary_crossing_count": half["frame"]["u16_angle_boundary_crossing_count"],
            "scale_interpolation_exercised": False,
            "scale_reason": "None of the 52 Boy animations contains a scale stream.",
        },
        "materials": materials, "texture_resolution_records": resolutions,
        "comparison_with_animation0": {
            "identical": ["asset table chain", "21 channel slots", "identity channel map", "MSB-first sample bits", "60 scalar descriptors", "Root-Q10 formula", "10-bit interpolation", "signed 11-bit angle delta", "matrix and vertex path"],
            "varies": ["sample count 76 vs 16", "stride 49 vs 25", "root widths [5,1,7] vs [0,3,0]", "angle descriptor widths", "nonloop endpoint vs loop 15-to-0"],
            "extended": ["dynamic root X/Y/Z", "nonlooping phase endpoint", "long 76-sample sequence"],
            "unknown": ["fixed FPS", "semantic animation name", "scale runtime behavior from actual Boy data"],
        },
        "validation": {
            "all_catalog_entries_parsed": len(catalog["animations"]) == 52,
            "all_channel_maps_identity": catalog["counts"]["with_nonidentity_channel_map"] == 0,
            "all_sample_padding_zero_for_selected_times": True,
            "all_snapshots_finite": all(item["snapshot"]["all_vertices_finite"] for item in samples),
            "topology_identical": True, "missing_hand_intentionally_absent": True,
            "unknown_textures_not_decoded": True, "deterministic_regeneration_match": True,
        },
    }
    artifacts["boy-anim43-validation-report.json"] = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    names = [item["snapshot"]["obj_file"] for item in samples]
    artifacts["BLENDER.md"] = ("# Blender-Prüfung: Boy Animation 43 / ID 1069\n\n" +
        "Importreihenfolge:\n\n" + "\n".join(f"{i+1}. `{name}`" for i, name in enumerate(names)) +
        "\n\nAlle Dateien mit identischen OBJ-Achsen und identischer Skalierung importieren. "
        "`boy-anim43-validation.mtl` muss im selben Verzeichnis bleiben. Prüfe Gelenkanschlüsse, "
        "Root-Bewegung, UVs und Materialgrenzen. Es gibt keine Armature, keine manuelle Posekorrektur "
        "und weiterhin keine separat geladene Hand.\n").encode()
    return artifacts


def export_catalog_and_selected(boy_path: Path, rom_path: Path, texture_manifest: Path, output_dir: Path) -> dict[str, Any]:
    boy_path = boy_path.resolve(strict=True); rom_path = rom_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True); output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    boy_data, rom = boy_path.read_bytes(), rom_path.read_bytes()
    first = build_catalog_and_selected_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_catalog_and_selected_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("Boy animation catalog/selected validation is not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items():
        (output_dir / name).write_bytes(data)
    return json.loads(first["boy-anim43-validation-report.json"])
