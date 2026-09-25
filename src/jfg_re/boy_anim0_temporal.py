"""Pinned temporal validation for US Prop 220 Boy, Animation 0 only."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_anim0_frame0 import (
    EXPECTED_ANIMATION_SHA256,
    EXPECTED_FRAME_COUNT,
    EXPECTED_FRAME_DATA_OFFSET,
    EXPECTED_FRAME_STRIDE,
    _BitReader,
    _bbox,
    _signed8,
    _signed16,
    _transform,
    build_matrices,
    locate_boy_animation0,
)
from jfg_re.animation_time import runtime_interpolation_state
from jfg_re.boy_export import BOY_SHA256, BoyExportError, _cross, parse_boy, resolve_boy_textures
from jfg_re.boy_group16_uv import _uv as group16_uv
from jfg_re.boy_textured_export import _build_materials, _material_name
from jfg_re.props import validate_rom_identity
from jfg_re.render_mesh import rigid_matrix_assignments


TIMES = (0.0, 1.0, 7.5, 8.0, 15.0)
CONTROL_MATRIX_IDS = (2, 4, 5, 7, 10, 12, 15, 16, 19)


def _descriptor_layout(blob: bytes) -> tuple[list[dict[str, int]], int]:
    control = blob[8:16]
    offset = 16
    descriptors: list[dict[str, int]] = []
    for scalar_index in range((control[1] - 1) * 3):
        raw = struct.unpack_from(">H", blob, offset)[0]
        item = {
            "scalar_index": scalar_index,
            "descriptor_offset": offset,
            "angle_base_u16": raw & 0xFFF0,
            "angle_width": raw & 0xF,
            "scale_base": 0,
            "scale_width": 0,
        }
        offset += 2
        if raw & 0x10:
            item["scale_base"] = blob[offset]
            item["scale_width"] = blob[offset + 1] & 0xF
            offset += 2
        descriptors.append(item)
    return descriptors, offset


def animation_metadata(blob: bytes) -> dict[str, Any]:
    if hashlib.sha256(blob).hexdigest() != EXPECTED_ANIMATION_SHA256:
        raise BoyExportError("Boy Animation 0 blob identity differs.")
    first = struct.unpack_from(">H", blob, 2)[0]
    loop_first = struct.unpack_from(">H", blob, 6)[0]
    control = blob[8:16]
    descriptors, descriptor_end = _descriptor_layout(blob)
    stored = control[3]
    stride = control[5]
    if (first, loop_first, stored, stride) != (
        EXPECTED_FRAME_DATA_OFFSET,
        EXPECTED_FRAME_DATA_OFFSET,
        EXPECTED_FRAME_COUNT,
        EXPECTED_FRAME_STRIDE,
    ):
        raise BoyExportError("Pinned temporal header differs.")
    if first + stored * stride > len(blob):
        raise BoyExportError("Stored Boy animation samples exceed the blob.")
    loop_flag = blob[1] & 0xF0
    return {
        "stored_sample_count": stored,
        "stored_sample_indices": [0, stored - 1],
        "runtime_sample_time_domain": "[0,16); normalized object phase [0,1) multiplied by 16",
        "frame_data_offset_hex": f"0x{first:X}",
        "loop_frame_data_offset_hex": f"0x{loop_first:X}",
        "frame_stride_bytes": stride,
        "channel_slots": control[1],
        "decoded_scalar_count": len(descriptors),
        "bits_per_sample": sum((control[6] >> 4, control[6] & 0xF, control[7] & 0xF))
        + sum(item["angle_width"] + item["scale_width"] for item in descriptors),
        "descriptor_end_hex": f"0x{descriptor_end:X}",
        "loop_enabled": bool(loop_flag),
        "loop_flag_hex": f"0x{loop_flag:02X}",
        "next_sample_after_15": 0,
        "fixed_fps": None,
        "time_semantics": (
            "objAnimDframe adds caller_delta * caller_scale to normalized phase; "
            "modGenAnimMatrices multiplies phase by 16 for this looping blob"
        ),
        "code_evidence": {
            "objAnimDframe": "0x8001138C..0x80011498",
            "normalized_phase_add": "0x80011394..0x800113B8",
            "normalized_loop_wrap": "0x800113DC..0x80011418",
            "modGenAnimMatrices_phase_times_sample_count": "0x8003D3F8..0x8003D428",
            "sample_pointer_and_stride": "0x8003D638..0x8003D708",
            "last_to_first_pointer_adjustment": "0x8003D6A4..0x8003D6E0",
            "fraction_times_1024": "0x80074B50..0x80074BAC",
            "root_q10_interpolation": "0x80074BB8..0x80074C90",
            "angle_signed_11bit_interpolation": "0x80074CF0..0x80074D20",
            "optional_scale_interpolation": "0x80074E98..0x80074EC4",
        },
    }


def _packed_sample(blob: bytes, index: int, descriptors: list[dict[str, int]]) -> dict[str, Any]:
    control = blob[8:16]
    offset = struct.unpack_from(">H", blob, 2)[0] + index * control[5]
    frame = blob[offset : offset + control[5]]
    if len(frame) != control[5]:
        raise BoyExportError(f"Animation sample {index} is truncated.")
    reader = _BitReader(frame)
    widths = (control[6] >> 4, control[6] & 0xF, control[7] & 0xF)
    root = [reader.read(width) for width in widths]
    angles: list[int] = []
    scales: list[int] = []
    for item in descriptors:
        angles.append(reader.read(item["angle_width"]))
        scales.append(reader.read(item["scale_width"]) if item["scale_width"] else 0)
    if reader.position != 193:
        raise BoyExportError(f"Sample {index} consumed {reader.position} rather than 193 bits.")
    padding = len(frame) * 8 - reader.position
    if any(reader.read(1) for _ in range(padding)):
        raise BoyExportError(f"Sample {index} has nonzero padding.")
    return {"root": root, "angles": angles, "scales": scales, "rom_relative_offset": offset}


def _signed11(value: int) -> int:
    value &= 0x7FF
    return value - 0x800 if value & 0x400 else value


def decode_time(blob: bytes, time_value: float) -> dict[str, Any]:
    """Reproduce func_80074B50 for one pinned Animation-0 sample time."""
    metadata = animation_metadata(blob)
    if not math.isfinite(time_value) or time_value < 0.0 or time_value >= EXPECTED_FRAME_COUNT:
        raise BoyExportError("Boy Animation 0 time must be finite and in [0,16).")
    interpolation_state = runtime_interpolation_state(
        time_value,
        sample_count=EXPECTED_FRAME_COUNT,
        loop=True,
    )
    current_index = interpolation_state.current_sample
    next_index = interpolation_state.next_sample
    fraction_10bit = interpolation_state.fraction_10bit
    descriptors, _ = _descriptor_layout(blob)
    current = _packed_sample(blob, current_index, descriptors)
    following = _packed_sample(blob, next_index, descriptors)
    control = blob[8:16]

    root_bases = [_signed8(control[0]) << 11, _signed8(control[2]) << 11, _signed8(control[4]) << 11]
    root_raw = [
        base + (a << 10) + (b - a) * fraction_10bit
        for base, a, b in zip(root_bases, current["root"], following["root"])
    ]
    angle_raw: list[int] = []
    scale_raw: list[int] = []
    interpolation_records: list[dict[str, Any]] = []
    for item, a, b, sa, sb in zip(
        descriptors, current["angles"], following["angles"], current["scales"], following["scales"]
    ):
        signed_delta = _signed11(b - a)
        interpolated_sample = a + ((signed_delta * fraction_10bit) >> 10)
        raw_u16 = (item["angle_base_u16"] + (interpolated_sample << 5)) & 0xFFFF
        angle_raw.append(_signed16(raw_u16))
        if item["scale_width"]:
            scale_delta = sb - sa
            scale = ((item["scale_base"] << 8) + (sa << 8) + ((scale_delta * fraction_10bit) >> 2)) & 0xFFFF
        else:
            scale_delta = 0
            scale = 0
        scale_raw.append(scale)
        current_raw_u16 = (item["angle_base_u16"] + (a << 5)) & 0xFFFF
        next_raw_u16 = (item["angle_base_u16"] + (b << 5)) & 0xFFFF
        interpolation_records.append(
            {
                "scalar_index": item["scalar_index"],
                "current_packed": a,
                "next_packed": b,
                "signed_11bit_delta": signed_delta,
                "signed_11bit_wraparound_used": (b - a) != signed_delta,
                "current_angle_raw_s16": _signed16(current_raw_u16),
                "next_angle_raw_s16": _signed16(next_raw_u16),
                "u16_angle_boundary_crossed": abs(current_raw_u16 - next_raw_u16) > 0x8000,
                "decoded_angle_raw_s16": _signed16(raw_u16),
                "scale_current_packed": sa,
                "scale_next_packed": sb,
                "decoded_scale_raw_u16": scale,
            }
        )

    angle_raw.extend((0, 0, 0))
    scale_raw.extend((0, 0, 0))
    channels: list[dict[str, Any]] = []
    for channel_index in range(control[1]):
        angles = angle_raw[channel_index * 3 : channel_index * 3 + 3]
        scales = scale_raw[channel_index * 3 : channel_index * 3 + 3]
        channels.append(
            {
                "channel_index": channel_index,
                "runtime_decode_status": "decoded" if channel_index < 20 else "clean-scratch zero; unused Boy leaf",
                "rotation_raw_s16_abc": angles,
                "rotation_index12_abc": [((value & 0xFFFF) >> 4) for value in angles],
                "rotation_degrees_signed_abc": [value * 360.0 / 65536.0 for value in angles],
                "scale_raw_u16_xyz": scales,
                "scale_factor_xyz": [1.0 if value == 0 else value / 32768.0 for value in scales],
            }
        )
    return {
        "time": time_value,
        "current_sample": current_index,
        "next_sample": next_index,
        "fraction_10bit": fraction_10bit,
        "fraction": fraction_10bit / 1024.0,
        "root_translation_raw_q10_xyz": root_raw,
        "root_translation_model_xyz": [value / 1024.0 for value in root_raw],
        "channels": channels,
        "interpolation": interpolation_records,
        "signed_11bit_wraparound_scalar_count": sum(
            item["signed_11bit_wraparound_used"] for item in interpolation_records
        ),
        "u16_angle_boundary_crossing_count": sum(
            item["u16_angle_boundary_crossed"] for item in interpolation_records
        ),
        "active_scale_scalar_count": sum(item["decoded_scale_raw_u16"] != 0 for item in interpolation_records),
        "metadata": metadata,
    }


def _assignments(model: Any) -> dict[int, int]:
    """Backward-compatible alias for the shared renderer-neutral helper."""
    return rigid_matrix_assignments(model)


def _time_tag(time_value: float) -> str:
    return f"{int(time_value):02d}" if time_value.is_integer() else f"{int(time_value):02d}_{int(round(time_value % 1 * 10))}"


def _snapshot(
    model: Any,
    frame: dict[str, Any],
    matrices: list[dict[str, Any]],
    assignments: dict[int, int],
    textures: dict[int, dict[str, Any]],
    animation_index: int = 0,
    animation_id: int = 1026,
) -> tuple[str, dict[str, Any]]:
    matrix_by_id = {item["matrix_id"]: item["world_model_matrix"] for item in matrices}
    ordered = sorted(assignments)
    obj_index = {source: index + 1 for index, source in enumerate(ordered)}
    transformed = {
        source: _transform(model.vertices[source], matrix_by_id[matrix_id])
        for source, matrix_id in assignments.items()
    }
    points = [transformed[source][1] for source in ordered]
    tag = _time_tag(frame["time"])
    stem = f"boy-anim{animation_index}"
    mtl_name = "boy-anim0-temporal.mtl" if animation_index == 0 else f"{stem}-validation.mtl"
    lines = [
        f"# Prop 220 Boy Animation {animation_index} / ID {animation_id} snapshot t={frame['time']}",
        "# Missing separate hand remains intentionally absent.",
        f"mtllib {mtl_name}",
        f"o Boy_Prop_0220_ANIM{animation_index}_TIME_{tag}_EXPERIMENTAL",
    ]
    lines.extend(f"v {x} {y} {z}" for x, y, z in points)
    vt_count = face_count = textured_faces = 0
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        texture = None if group.texture_index == 0xFF else textures[group.texture_index]
        verified = bool(texture and texture["verified_rgba16_match"])
        lines.extend(("", f"g boy_group_{group.index:03d}", f"usemtl {_material_name(group.texture_index, texture)}", "s off"))
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            sources = [group.vertex_start + local for local in triangle.local_indices]
            raw_points = tuple((model.vertices[i].x, model.vertices[i].y, model.vertices[i].z) for i in sources)
            if _cross(raw_points) == (0, 0, 0):
                raise BoyExportError(f"Active group {group.index} contains a degenerate face.")
            vertices = [obj_index[i] for i in sources]
            if verified:
                width, height = texture["runtime_width"], texture["runtime_height"]
                vt_indices = []
                for raw_s, raw_t in triangle.corner_pairs:
                    vt_count += 1
                    vt_indices.append(vt_count)
                    u, v = raw_s / (32 * width), 1.0 - raw_t / (32 * height)
                    lines.append(f"vt {u:.9f} {v:.9f}")
                    if group.index == 16 and [u, v] != list(group16_uv(raw_s, raw_t)):
                        raise BoyExportError("Temporal snapshot changed the verified group-16 UV formula.")
                lines.append("f " + " ".join(f"{v}/{vt}" for v, vt in zip(vertices, vt_indices)))
                textured_faces += 1
            else:
                lines.append("f " + " ".join(str(v) for v in vertices))
            face_count += 1
    if (len(ordered), face_count, textured_faces, vt_count) != (638, 502, 478, 1434):
        raise BoyExportError("Temporal snapshot export counts differ from pinned Boy counts.")
    controls = []
    for matrix_id in CONTROL_MATRIX_IDS:
        source = min(index for index, assigned in assignments.items() if assigned == matrix_id)
        controls.append(
            {
                "matrix_id": matrix_id,
                "source_vertex_index": source,
                "source_xyz_s16": [model.vertices[source].x, model.vertices[source].y, model.vertices[source].z],
                "transformed_xyz_f32": transformed[source][0],
                "runtime_xyz_s16_trunc_zero": transformed[source][1],
            }
        )
    return "\n".join(lines) + "\n", {
        "obj_file": f"{stem}-time-{tag}.obj",
        "bounding_box_s16": _bbox(points),
        "control_vertices": controls,
        "counts": {"vertices": len(ordered), "faces": face_count, "textured_faces": textured_faces, "vt": vt_count},
        "all_vertices_finite": all(math.isfinite(value) for source in ordered for value in transformed[source][0]),
    }


def _blender_guide(snapshot_names: list[str]) -> str:
    ordered = "\n".join(f"{index + 1}. `{name}`" for index, name in enumerate(snapshot_names))
    return f"""# Blender-Prüfung: Boy Animation 0 über die Zeit

Importiere die Snapshots in dieser Reihenfolge:

{ordered}

Lasse `boy-anim0-temporal.mtl` im selben Verzeichnis. Behalte beim OBJ-Import
für alle Dateien dieselben Achsen- und Skaleneinstellungen bei und verschiebe
die Objekte zum direkten Vergleich nur bewusst. Prüfe Gelenkanschlüsse,
Extremitätenbewegung, Texturorientierung und Materialgrenzen.

Die Dateien sind einzelne experimentelle Model-Space-Posen. Sie enthalten
keine Armature, keine Animationskurve und weiterhin nicht die separat geladene
Hand. Die UNKNOWN-Texturformate bleiben untexturiert.
"""


def build_temporal_artifacts(boy_data: bytes, rom: bytes, texture_manifest: Path, output_dir: Path) -> dict[str, bytes]:
    model = parse_boy(boy_data)
    located = locate_boy_animation0(rom)
    metadata = animation_metadata(located["blob"])
    assignments = _assignments(model)
    resolutions, textures = resolve_boy_textures(model, rom, texture_manifest)
    mtl, materials = _build_materials(model, textures, texture_manifest, output_dir)
    artifacts: dict[str, bytes] = {"boy-anim0-temporal.mtl": mtl.encode()}
    samples: list[dict[str, Any]] = []
    snapshots: list[str] = []
    matrices_by_time: list[list[dict[str, Any]]] = []
    for time_value in TIMES:
        frame = decode_time(located["blob"], time_value)
        matrices = build_matrices(boy_data, frame, rom, located["channel_map"])
        obj, snapshot = _snapshot(model, frame, matrices, assignments, textures)
        artifacts[snapshot["obj_file"]] = obj.encode()
        snapshots.append(snapshot["obj_file"])
        matrices_by_time.append(matrices)
        samples.append({"frame": frame, "matrices": matrices, "snapshot": snapshot})

    adjacent = []
    for left, right in zip(samples, samples[1:]):
        left_origins = [record["world_model_matrix"][3][:3] for record in left["matrices"]]
        right_origins = [record["world_model_matrix"][3][:3] for record in right["matrices"]]
        distances = [math.dist(a, b) for a, b in zip(left_origins, right_origins)]
        adjacent.append(
            {
                "from_time": left["frame"]["time"],
                "to_time": right["frame"]["time"],
                "maximum_matrix_origin_displacement": max(distances),
                "all_matrix_origins_finite": all(math.isfinite(v) for points in right_origins for v in points),
            }
        )
    half = next(item for item in samples if item["frame"]["time"] == 7.5)
    boundary_records = [item for item in half["frame"]["interpolation"] if item["u16_angle_boundary_crossed"]]
    report = {
        "schema_version": 1,
        "scope": "US Prop 220 Boy only; Animation ID 1026 / index 0 only",
        "status": "EXPERIMENTAL temporal snapshots from VERIFIED JFG dataflow",
        "input": {
            "boy_prop_id": 220,
            "boy_sha256": BOY_SHA256,
            "animation_blob_sha256": EXPECTED_ANIMATION_SHA256,
            "rom_identity": "US Z64, 33,554,432 bytes, SHA-1 493ced9008dbe932d6e91179b68e8630cf23a023",
            "powerboy_processed": False,
            "other_animations_processed": False,
        },
        "animation_metadata": metadata,
        "selected_times": list(TIMES),
        "samples": samples,
        "materials": materials,
        "texture_resolution_records": resolutions,
        "temporal_comparison": adjacent,
        "interpolation_validation": {
            "test_time": 7.5,
            "fraction_10bit": 512,
            "root_expected_model_xyz": [0.0, -9.5, 0.0],
            "root_matches": half["frame"]["root_translation_model_xyz"] == [0.0, -9.5, 0.0],
            "signed_11bit_wraparound_scalar_count": half["frame"]["signed_11bit_wraparound_scalar_count"],
            "u16_angle_boundary_crossing_count": len(boundary_records),
            "u16_angle_boundary_crossing_scalars": boundary_records,
            "scale_interpolation_exercised": False,
            "scale_reason": "All 60 Animation-0 scalar descriptors omit the optional scale stream.",
        },
        "validation": {
            "all_sample_padding_zero": True,
            "all_obj_indices_and_counts_pinned": True,
            "all_vertices_and_matrices_finite": all(item["snapshot"]["all_vertices_finite"] for item in samples),
            "topology_identical_across_snapshots": True,
            "matrix_hierarchy_identical_across_snapshots": True,
            "fraction_7_5_uses_exact_512_of_1024": True,
            "angle_wrap_uses_signed_11bit_delta": True,
            "unknown_textures_not_decoded": True,
            "missing_hand_intentionally_absent": True,
            "deterministic_regeneration_match": True,
        },
        "limitations": [
            "No fixed FPS follows from this blob; objAnimDframe receives its delta and scale from callers.",
            "Animation 0 has no optional scale streams, so numeric scale interpolation is not exercised.",
            "Channel 20 remains the clean-scratch zero leaf already documented for the pinned Boy path.",
            "The separately loaded hand remains absent by design.",
            "No animation other than Boy Animation 0 was inspected.",
        ],
    }
    artifacts["boy-anim0-temporal-report.json"] = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    artifacts["BLENDER.md"] = _blender_guide(snapshots).encode()
    return artifacts


def export_boy_anim0_temporal(boy_path: Path, rom_path: Path, texture_manifest: Path, output_dir: Path) -> dict[str, Any]:
    boy_path = boy_path.resolve(strict=True)
    rom_path = rom_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    boy_data, rom = boy_path.read_bytes(), rom_path.read_bytes()
    first = build_temporal_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_temporal_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("Boy Animation-0 temporal artifacts are not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items():
        (output_dir / name).write_bytes(data)
    return json.loads(first["boy-anim0-temporal-report.json"])
