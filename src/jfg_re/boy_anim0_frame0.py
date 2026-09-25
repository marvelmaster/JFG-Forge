"""Pinned Animation-0/Frame-0 decoder and pose exporter for US Prop 220 Boy.

This is deliberately not a general animation decoder.  Every lookup is
followed through the US ROM tables used by JFG and validated against the one
Boy animation blob required for this experiment.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_export import (
    ASSET_DATA_START,
    ASSET_LUT_START,
    BONE_COUNT,
    BONE_START,
    BOY_SHA256,
    BoyExportError,
    _asset_lut,
    _asset_range,
    _cross,
    _matrix_id,
    parse_boy,
    resolve_boy_textures,
)
from jfg_re.boy_group16_uv import _uv as group16_uv
from jfg_re.boy_textured_export import _build_materials, _material_name, _overview, _tile_state
from jfg_re.props import validate_rom_identity


PROP_ID = 220
ANIMATION_INDEX = 0
EXPECTED_ANIMATION_COUNT = 52
EXPECTED_ANIMATION_ID = 1026
EXPECTED_ANIMATION_ROM_START = 0x16E37C0
EXPECTED_ANIMATION_ROM_END = 0x16E39E0
EXPECTED_ANIMATION_SIZE = 544
EXPECTED_ANIMATION_SHA256 = "0693bf4740d35faa69637a37dede4a81fc84e2d9aabc812da03fdb6164de1d78"
EXPECTED_FRAME_DATA_OFFSET = 0x8E
EXPECTED_FRAME_STRIDE = 25
EXPECTED_FRAME_COUNT = 16
SINE_TABLE_ROM_OFFSET = 0xA8994
SINE_TABLE_VALUES = 1025


def _f32(value: float) -> float:
    return struct.unpack(">f", struct.pack(">f", value))[0]


def _mul(a: float, b: float) -> float:
    return _f32(_f32(a) * _f32(b))


def _add(a: float, b: float) -> float:
    return _f32(_f32(a) + _f32(b))


def _sub(a: float, b: float) -> float:
    return _f32(_f32(a) - _f32(b))


def _signed8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _signed16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


class _BitReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0

    def read(self, width: int) -> int:
        if width < 0 or self.position + width > len(self.data) * 8:
            raise BoyExportError("Animation frame bitstream ended unexpectedly.")
        result = 0
        for _ in range(width):
            result = (result << 1) | ((self.data[self.position // 8] >> (7 - self.position % 8)) & 1)
            self.position += 1
        return result


def _asset_bytes(rom: bytes, asset_index: int) -> tuple[int, int, bytes]:
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, asset_index)
    return start, end, rom[start:end]


def locate_boy_animation0(rom: bytes) -> dict[str, Any]:
    """Reproduce modLoadModel/func_8003CB04's table chain for Boy animation 0."""
    a40s, _, asset40 = _asset_bytes(rom, 40)
    model_group_offset = (PROP_ID & ~3) * 2
    pair_offset = model_group_offset + (PROP_ID & 3) * 2
    first_half, following_half = struct.unpack_from(">HH", asset40, pair_offset)
    first_animation = first_half >> 1
    following_animation = following_half >> 1
    animation_count = following_animation - first_animation
    if animation_count != EXPECTED_ANIMATION_COUNT:
        raise BoyExportError(f"Boy animation count differs: {animation_count}.")

    a41s, _, asset41 = _asset_bytes(rom, 41)
    animation_id = struct.unpack_from(">h", asset41, (first_animation + ANIMATION_INDEX) * 2)[0]
    if animation_id != EXPECTED_ANIMATION_ID:
        raise BoyExportError(f"Boy animation 0 ID differs: {animation_id}.")

    a44s, _, asset44 = _asset_bytes(rom, 44)
    map_group_offset = (PROP_ID & ~1) * 4
    map_pair_offset = map_group_offset + (PROP_ID & 1) * 4
    map_start, map_end = struct.unpack_from(">II", asset44, map_pair_offset)
    a45s, _, asset45 = _asset_bytes(rom, 45)
    map_blob = asset45[map_start:map_end]
    expected_map_size = animation_count * BONE_COUNT
    if len(map_blob) < expected_map_size:
        raise BoyExportError("Boy animation channel-map range is too short.")
    channel_map = list(map_blob[ANIMATION_INDEX * BONE_COUNT : (ANIMATION_INDEX + 1) * BONE_COUNT])
    if channel_map != list(range(BONE_COUNT)):
        raise BoyExportError(f"Boy animation 0 channel map differs: {channel_map}.")

    a42s, _, asset42 = _asset_bytes(rom, 42)
    animation_pair_offset = (animation_id & ~1) * 4 + (animation_id & 1) * 4
    animation_start, animation_end = struct.unpack_from(">II", asset42, animation_pair_offset)
    a43s, _, asset43 = _asset_bytes(rom, 43)
    blob = asset43[animation_start:animation_end]
    rom_start, rom_end = a43s + animation_start, a43s + animation_end
    digest = hashlib.sha256(blob).hexdigest()
    if (
        rom_start != EXPECTED_ANIMATION_ROM_START
        or rom_end != EXPECTED_ANIMATION_ROM_END
        or len(blob) != EXPECTED_ANIMATION_SIZE
        or digest != EXPECTED_ANIMATION_SHA256
    ):
        raise BoyExportError("Pinned Boy animation 0 blob identity differs.")

    return {
        "animation_count": animation_count,
        "animation_id": animation_id,
        "channel_map": channel_map,
        "blob": blob,
        "evidence": {
            "asset_lut_rom_offset_hex": f"0x{ASSET_LUT_START:X}",
            "asset_data_rom_offset_hex": f"0x{ASSET_DATA_START:X}",
            "asset40_model_range_table_rom_offset_hex": f"0x{a40s + pair_offset:X}",
            "asset40_halfword_pair_hex": [f"0x{first_half:04X}", f"0x{following_half:04X}"],
            "asset41_animation_id_rom_offset_hex": f"0x{a41s + first_animation * 2:X}",
            "asset44_channel_map_range_rom_offset_hex": f"0x{a44s + map_pair_offset:X}",
            "asset45_channel_map_rom_range_hex": [f"0x{a45s + map_start:X}", f"0x{a45s + map_end:X}"],
            "asset42_animation_range_rom_offset_hex": f"0x{a42s + animation_pair_offset:X}",
            "asset43_animation_blob_rom_range_hex": [f"0x{rom_start:X}", f"0x{rom_end:X}"],
            "animation_blob_size": len(blob),
            "animation_blob_sha256": digest,
            "storage": "direct asset slice loaded by assetLoad; no compression wrapper on this blob",
        },
    }


def decode_frame0(blob: bytes) -> dict[str, Any]:
    """Decode exactly the integer frame 0 path used by func_80074B50."""
    frame_data_offset = struct.unpack_from(">H", blob, 2)[0]
    second_frame_data_offset = struct.unpack_from(">H", blob, 6)[0]
    control = blob[8:16]
    frame_count = control[3]
    frame_stride = control[5]
    channel_slots = control[1]
    if (
        frame_data_offset != EXPECTED_FRAME_DATA_OFFSET
        or second_frame_data_offset != EXPECTED_FRAME_DATA_OFFSET
        or frame_stride != EXPECTED_FRAME_STRIDE
        or frame_count != EXPECTED_FRAME_COUNT
        or channel_slots != BONE_COUNT
    ):
        raise BoyExportError("Pinned Boy animation 0 header differs.")
    frame = blob[frame_data_offset : frame_data_offset + frame_stride]
    if len(frame) != frame_stride:
        raise BoyExportError("Pinned Boy frame 0 is truncated.")
    reader = _BitReader(frame)

    root_widths = [control[6] >> 4, control[6] & 0xF, control[7] & 0xF]
    root_bases = [_signed8(control[0]) << 11, _signed8(control[2]) << 11, _signed8(control[4]) << 11]
    # func_80074B50 stores root samples in Q10 units: current_sample << 10,
    # plus the signed header base << 11.  The final matrix path divides by
    # 1024 at 0x80075270..0x80075280.
    root_raw = [base + (reader.read(width) << 10) for base, width in zip(root_bases, root_widths)]

    descriptor_offset = 16
    decoded_scalar_count = (channel_slots - 1) * 3
    angle_values: list[int] = []
    scale_values: list[int] = []
    descriptors: list[dict[str, Any]] = []
    for scalar_index in range(decoded_scalar_count):
        raw_descriptor = struct.unpack_from(">H", blob, descriptor_offset)[0]
        width = raw_descriptor & 0xF
        base = raw_descriptor & 0xFFF0
        packed_delta = reader.read(width)
        raw_u16 = (base + (packed_delta << 5)) & 0xFFFF
        raw_s16 = _signed16(raw_u16)
        scale_raw = 0
        consumed = 2
        if raw_u16 & 0x10:
            scale_base = blob[descriptor_offset + 2]
            scale_width = blob[descriptor_offset + 3] & 0xF
            scale_delta = reader.read(scale_width)
            scale_raw = ((scale_base + scale_delta) << 8) & 0xFFFF
            consumed = 4
        descriptors.append(
            {
                "scalar_index": scalar_index,
                "blob_offset_hex": f"0x{descriptor_offset:X}",
                "descriptor_hex": f"0x{raw_descriptor:04X}",
                "bit_width": width,
                "packed_frame0_value": packed_delta,
                "decoded_raw_u16": raw_u16,
                "decoded_raw_s16": raw_s16,
                "scale_raw_u16": scale_raw,
            }
        )
        angle_values.append(raw_s16)
        scale_values.append(scale_raw)
        descriptor_offset += consumed

    if descriptor_offset != frame_data_offset - 6 or blob[descriptor_offset:frame_data_offset] != b"\0" * 6:
        raise BoyExportError("Pinned Boy channel-20 zero descriptors differ.")
    if reader.position != 193 or any(reader.read(1) for _ in range(len(frame) * 8 - reader.position)):
        raise BoyExportError("Pinned Boy frame-0 padding or consumed bit count differs.")

    angle_values.extend((0, 0, 0))
    scale_values.extend((0, 0, 0))
    channels = []
    for channel in range(channel_slots):
        raw = angle_values[channel * 3 : channel * 3 + 3]
        scales = scale_values[channel * 3 : channel * 3 + 3]
        channels.append(
            {
                "channel_index": channel,
                "runtime_decode_status": (
                    "VERIFIED: written by frame-0 decoder"
                    if channel < channel_slots - 1
                    else "UNUSED: not written by this decoder; clean static scratch initialization is zero"
                ),
                "rotation_raw_s16_abc": raw,
                "rotation_raw_u16_abc": [value & 0xFFFF for value in raw],
                "rotation_index12_abc": [(value & 0xFFFF) >> 4 for value in raw],
                "rotation_degrees_signed_abc": [_f32(value * 360.0 / 65536.0) for value in raw],
                "scale_raw_u16_xyz": scales,
                "scale_factor_xyz": [1.0 if value == 0 else _f32(value / 32768.0) for value in scales],
            }
        )
    return {
        "frame_index": 0,
        "frame_count": frame_count,
        "frame_data_offset": frame_data_offset,
        "frame_stride": frame_stride,
        "frame_bytes_hex": frame.hex(),
        "frame_sha256": hashlib.sha256(frame).hexdigest(),
        "frame_indexing": "blob + u16@+2 + frame_stride * floor(frame); integer frame 0 uses interpolation offset 0",
        "root_bit_widths_xyz": root_widths,
        "root_base_signed8_xyz": [_signed8(control[0]), _signed8(control[2]), _signed8(control[4])],
        "root_translation_raw_xyz": root_raw,
        "root_translation_model_xyz": [_f32(value / 1024.0) for value in root_raw],
        "decoded_scalar_count": decoded_scalar_count,
        "consumed_frame_bits": 193,
        "padding_frame_bits": 7,
        "descriptors": descriptors,
        "channels": channels,
    }


def _sine_table(rom: bytes) -> tuple[float, ...]:
    end = SINE_TABLE_ROM_OFFSET + SINE_TABLE_VALUES * 4
    table = struct.unpack(f">{SINE_TABLE_VALUES}f", rom[SINE_TABLE_ROM_OFFSET:end])
    if table[0] != 0.0 or table[-1] != 1.0:
        raise BoyExportError("JFG quarter-sine table identity differs.")
    return table


def _sin_cos(raw_s16: int, table: tuple[float, ...]) -> tuple[float, float]:
    index = (raw_s16 & 0xFFFF) >> 4
    quadrant, within = index >> 10, index & 0x3FF
    low, complement = table[within], table[1024 - within]
    if quadrant == 0:
        return low, complement
    if quadrant == 1:
        return complement, _f32(-low)
    if quadrant == 2:
        return _f32(-low), _f32(-complement)
    return _f32(-complement), low


def _local_matrix(rotation: list[int], scales: list[int], translation: list[float], table: tuple[float, ...]) -> list[list[float]]:
    sin_a, cos_a = _sin_cos(rotation[0], table)
    sin_b, cos_b = _sin_cos(rotation[1], table)
    sin_c, cos_c = _sin_cos(rotation[2], table)
    f6, f7 = _mul(sin_a, sin_b), _mul(cos_a, sin_b)
    f8, f9 = _mul(sin_a, cos_b), _mul(cos_a, cos_b)
    rows = [
        [_mul(cos_c, cos_b), _mul(cos_c, sin_b), _f32(-sin_c), 0.0],
        [_sub(_mul(f8, sin_c), f7), _add(_mul(f6, sin_c), f9), _mul(sin_a, cos_c), 0.0],
        [_add(_mul(f9, sin_c), f6), _sub(_mul(f7, sin_c), f8), _mul(cos_a, cos_c), 0.0],
        [_f32(translation[0]), _f32(translation[1]), _f32(translation[2]), 1.0],
    ]
    factors = [1.0 if value == 0 else _f32(value / 32768.0) for value in scales]
    for axis in range(3):
        for column in range(3):
            rows[axis][column] = _mul(rows[axis][column], factors[axis])
    return rows


def _local_matrix_from_stored(
    stored_rotation: list[int],
    scales: list[int],
    translation: list[float],
    table: tuple[float, ...],
) -> list[list[float]]:
    """Build a local matrix from JFG's runtime-verified A/C/B storage order."""
    return _local_matrix(
        [stored_rotation[0], stored_rotation[2], stored_rotation[1]],
        scales,
        translation,
        table,
    )


def _matrix_multiply(local: list[list[float]], parent: list[list[float]]) -> list[list[float]]:
    result = [[0.0] * 4 for _ in range(4)]
    for row in range(3):
        for column in range(3):
            value = _add(_mul(local[row][0], parent[0][column]), _mul(local[row][1], parent[1][column]))
            result[row][column] = _add(value, _mul(local[row][2], parent[2][column]))
    for column in range(3):
        value = _add(_mul(local[3][0], parent[0][column]), _mul(local[3][1], parent[1][column]))
        value = _add(value, _mul(local[3][2], parent[2][column]))
        result[3][column] = _add(value, parent[3][column])
    result[3][3] = 1.0
    return result


def _float_hex(matrix: list[list[float]]) -> list[list[str]]:
    return [[struct.pack(">f", value).hex() for value in row] for row in matrix]


def build_matrices(boy_data: bytes, frame: dict[str, Any], rom: bytes, channel_map: list[int]) -> list[dict[str, Any]]:
    table = _sine_table(rom)
    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    root_parent = [row[:] for row in identity]
    root_parent[3][:3] = frame["root_translation_model_xyz"]
    world_by_id: dict[int, list[list[float]]] = {}
    records: list[dict[str, Any]] = []
    for record_index in range(BONE_COUNT):
        offset = BONE_START + record_index * 16
        parent_id, matrix_id = boy_data[offset], boy_data[offset + 1]
        channel_index = channel_map[record_index]
        translation = list(struct.unpack_from(">fff", boy_data, offset + 4))
        channel = frame["channels"][channel_index]
        local = _local_matrix_from_stored(
            channel["rotation_raw_s16_abc"],
            channel["scale_raw_u16_xyz"],
            translation,
            table,
        )
        parent = root_parent if parent_id == 0xFF else world_by_id[parent_id]
        world = _matrix_multiply(local, parent)
        world_by_id[matrix_id] = world
        records.append(
            {
                "record_index": record_index,
                "record_file_offset_hex": f"0x{offset:04X}",
                "parent_id": parent_id,
                "matrix_id": matrix_id,
                "animation_channel": channel_index,
                "animation_channel_status": channel["runtime_decode_status"],
                "local_translation_xyz": translation,
                "rotation_raw_s16_abc": channel["rotation_raw_s16_abc"],
                "rotation_index12_abc": channel["rotation_index12_abc"],
                "rotation_degrees_signed_abc": channel["rotation_degrees_signed_abc"],
                "scale_raw_u16_xyz": channel["scale_raw_u16_xyz"],
                "scale_factor_xyz": channel["scale_factor_xyz"],
                "local_matrix": local,
                "local_matrix_f32_hex": _float_hex(local),
                "world_model_matrix": world,
                "world_model_matrix_f32_hex": _float_hex(world),
            }
        )
    return records


def _transform(vertex: Any, matrix: list[list[float]]) -> tuple[list[float], list[int]]:
    xyz = [float(vertex.x), float(vertex.y), float(vertex.z)]
    result: list[float] = []
    for column in range(3):
        value = _add(_mul(xyz[0], matrix[0][column]), _mul(xyz[1], matrix[1][column]))
        value = _add(value, _mul(xyz[2], matrix[2][column]))
        result.append(_add(value, matrix[3][column]))
    if not all(math.isfinite(value) for value in result):
        raise BoyExportError("Animation-0/frame-0 transform produced NaN or infinity.")
    converted = [math.trunc(value) for value in result]
    if any(value < -32768 or value > 32767 for value in converted):
        raise BoyExportError("Animation-0/frame-0 transform exceeds s16 output range.")
    return result, converted


def _bbox(points: list[list[int]]) -> dict[str, list[int]]:
    return {
        "minimum": [min(point[axis] for point in points) for axis in range(3)],
        "maximum": [max(point[axis] for point in points) for axis in range(3)],
    }


def _blender_guide() -> str:
    return """# Blender-Prüfung: Boy Animation 0, Frame 0

1. Importiere `boy-anim0-frame0-experimental.obj` als Wavefront OBJ. Die MTL
   muss im selben Verzeichnis bleiben.
2. Die 14 bestätigten RGBA16-PNGs werden relativ referenziert. Für die hier
   verwendeten Clamp-Texturen sollte Blender **Extension = Extend** verwenden.
3. Belasse OBJ-Achsen, Skalierung und Ursprung zunächst unverändert. Dieser
   Export enthält bereits die model-space Matrizen von Animation 0, Frame 0.
4. Prüfe Körperzusammenhang, Gelenkanschlüsse, Links/Rechts-Symmetrie,
   Texturorientierung, UV-Seams und Materialgrenzen.
5. Gruppen 79–81 bleiben wegen UNKNOWN-Texturformaten untexturiert. Das ist
   kein Posefehler. OBJ transportiert außerdem das per Triangle gesetzte
   Backface-Culling-Bit nicht.

Der Export ist ein gepinnter experimenteller Reality-Check für Prop 220 und
kein allgemeiner Modell- oder Animationsexporter.
"""


def build_artifacts(boy_data: bytes, rom: bytes, texture_manifest: Path, output_dir: Path) -> dict[str, bytes]:
    model = parse_boy(boy_data)
    located = locate_boy_animation0(rom)
    frame = decode_frame0(located["blob"])
    matrices = build_matrices(boy_data, frame, rom, located["channel_map"])
    matrix_by_id = {record["matrix_id"]: record["world_model_matrix"] for record in matrices}
    resolutions, textures = resolve_boy_textures(model, rom, texture_manifest)
    mtl, materials = _build_materials(model, textures, texture_manifest, output_dir)

    assignments: dict[int, int] = {}
    groups: list[dict[str, Any]] = []
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        for global_index in range(group.vertex_start, following.vertex_start):
            matrix_id = _matrix_id(group, global_index - group.vertex_start)
            assert matrix_id is not None
            old = assignments.setdefault(global_index, matrix_id)
            if old != matrix_id:
                raise BoyExportError("One active Boy vertex has conflicting matrix assignments.")

    ordered_vertices = sorted(assignments)
    obj_index = {global_index: index + 1 for index, global_index in enumerate(ordered_vertices)}
    transformed: dict[int, tuple[list[float], list[int]]] = {
        global_index: _transform(model.vertices[global_index], matrix_by_id[matrix_id])
        for global_index, matrix_id in assignments.items()
    }
    raw_points = [[model.vertices[index].x, model.vertices[index].y, model.vertices[index].z] for index in ordered_vertices]
    transformed_points = [transformed[index][1] for index in ordered_vertices]

    obj_lines = [
        "# Prop 220 Boy, Animation 0 Frame 0, JFG runtime matrix reproduction",
        "# Model-space export; no manual pose correction.",
        "mtllib boy-anim0-frame0-experimental.mtl",
        "o Boy_Prop_0220_ANIM0_FRAME0_EXPERIMENTAL",
    ]
    obj_lines.extend(f"v {x} {y} {z}" for x, y, z in transformed_points)
    vt_count = face_count = textured_faces = 0
    face_records: list[dict[str, Any]] = []
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        texture = None if group.texture_index == 0xFF else textures[group.texture_index]
        verified = bool(texture and texture["verified_rgba16_match"])
        material = _material_name(group.texture_index, texture)
        obj_lines.extend(("", f"g boy_group_{group.index:03d}", f"usemtl {material}", "s off"))
        flag_counts: Counter[str] = Counter()
        group_faces = 0
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            global_indices = [group.vertex_start + local for local in triangle.local_indices]
            raw_triangle = tuple(tuple(raw_points[ordered_vertices.index(index)]) for index in global_indices)
            if _cross(raw_triangle) == (0, 0, 0):
                raise BoyExportError(f"Active group {group.index} unexpectedly contains a degenerate face.")
            vertices = [obj_index[index] for index in global_indices]
            uv_values: list[list[float]] | None = None
            vt_indices: list[int] | None = None
            if verified:
                width, height = texture["runtime_width"], texture["runtime_height"]
                uv_values, vt_indices = [], []
                for raw_s, raw_t in triangle.corner_pairs:
                    u, v = raw_s / (32 * width), 1.0 - raw_t / (32 * height)
                    vt_count += 1
                    vt_indices.append(vt_count)
                    uv_values.append([u, v])
                    obj_lines.append(f"vt {u:.9f} {v:.9f}")
                tokens = [f"{vertex}/{vt}" for vertex, vt in zip(vertices, vt_indices)]
                textured_faces += 1
            else:
                tokens = [str(vertex) for vertex in vertices]
            obj_lines.append("f " + " ".join(tokens))
            flag_counts[f"0x{triangle.flag:02X}"] += 1
            face_records.append(
                {
                    "triangle_index": triangle.index,
                    "group_index": group.index,
                    "obj_vertex_indices": vertices,
                    "global_source_vertex_indices": global_indices,
                    "matrix_ids": [assignments[index] for index in global_indices],
                    "raw_corner_st": [list(pair) for pair in triangle.corner_pairs],
                    "obj_vt_indices": vt_indices,
                    "obj_uv": uv_values,
                    "triangle_flag_hex": f"0x{triangle.flag:02X}",
                }
            )
            face_count += 1
            group_faces += 1
        groups.append(
            {
                "group_index": group.index,
                "exported_faces": group_faces,
                "texture_id_hex": None if texture is None else texture["texture_id_hex"],
                "texture_status": "NO TEXTURE" if texture is None else ("VERIFIED RGBA16" if verified else "UNKNOWN FORMAT"),
                "material": material,
                "matrix_ids": list(group.matrix_ids),
                "matrix_splits": list(group.matrix_splits),
                "triangle_flag_counts": dict(sorted(flag_counts.items())),
                "tile_state": _tile_state(texture) if verified else None,
            }
        )

    if (len(ordered_vertices), face_count, textured_faces, vt_count) != (638, 502, 478, 1434):
        raise BoyExportError("Pinned transformed Boy export counts differ.")
    group16_faces = [face for face in face_records if face["group_index"] == 16]
    for face in group16_faces:
        assert face["obj_uv"] is not None
        for raw, uv in zip(face["raw_corner_st"], face["obj_uv"]):
            if uv != list(group16_uv(*raw)):
                raise BoyExportError("Transformed export changed the verified group-16 UV formula.")

    counts_by_matrix = Counter(assignments.values())
    examples = []
    for matrix_id in sorted(counts_by_matrix):
        source_index = min(index for index, assigned in assignments.items() if assigned == matrix_id)
        vertex = model.vertices[source_index]
        float_result, s16_result = transformed[source_index]
        examples.append(
            {
                "matrix_id": matrix_id,
                "source_vertex_index": source_index,
                "source_xyz_s16": [vertex.x, vertex.y, vertex.z],
                "transformed_xyz_f32": float_result,
                "runtime_output_xyz_s16_trunc_zero": s16_result,
            }
        )
    for record in matrices:
        record["transformed_active_vertex_count"] = counts_by_matrix[record["matrix_id"]]

    report = {
        "schema_version": 1,
        "scope": "US Prop 220 Boy only; Animation 0, integer Frame 0 only",
        "status": "EXPERIMENTAL pose export from VERIFIED runtime data path",
        "input": {
            "boy_prop_id": PROP_ID,
            "boy_sha256": BOY_SHA256,
            "rom_identity": "US Z64, 33,554,432 bytes, SHA-1 493ced9008dbe932d6e91179b68e8630cf23a023",
            "powerboy_processed": False,
        },
        "animation_lookup": {key: value for key, value in located.items() if key != "blob"},
        "frame0": frame,
        "matrix_convention": {
            "local_rotation": "Rx(A) * Ry(C) * Rz(B), row-vector convention",
            "hierarchy": "M_child_world = M_child_local * M_parent_world",
            "root_parent": "T(animation_root_translation / 1024) * identity model-space object matrix",
            "point": "p_out = p_local * M_world; then truncate toward zero to s16",
            "sine_table_rom_offset_hex": f"0x{SINE_TABLE_ROM_OFFSET:X}",
        },
        "matrices": matrices,
        "vertex_examples": examples,
        "bounding_boxes": {
            "active_raw_xyz": _bbox(raw_points),
            "active_transformed_s16": _bbox(transformed_points),
        },
        "counts": {
            "stored_vertices": len(model.vertices),
            "transformed_active_vertices": len(ordered_vertices),
            "untransformed_runtime_skipped_vertices": len(model.vertices) - len(ordered_vertices),
            "exported_faces": face_count,
            "verified_rgba16_textured_faces": textured_faces,
            "obj_vt_records": vt_count,
            "active_groups": len(groups),
            "runtime_skipped_groups": sum(group.runtime_skipped for group in model.groups),
        },
        "materials": materials,
        "groups": groups,
        "faces": face_records,
        "texture_resolution_records": resolutions,
        "validation": {
            "animation_blob_identity_verified": True,
            "frame0_bitstream_consumed_without_nonzero_padding": True,
            "channel_map_is_exact_identity_0_through_20": True,
            "all_scale_values_zero_default_one": True,
            "all_output_values_finite": True,
            "all_output_values_fit_s16": True,
            "all_obj_vertex_indices_valid": all(1 <= index <= len(ordered_vertices) for face in face_records for index in face["obj_vertex_indices"]),
            "all_obj_vt_indices_valid": all(
                face["obj_vt_indices"] is None or all(1 <= index <= vt_count for index in face["obj_vt_indices"])
                for face in face_records
            ),
            "group16_uv_matches_verified_test": True,
            "unknown_textures_not_decoded": True,
            "deterministic_regeneration_match": True,
        },
        "limitations": [
            "Only Boy animation 0 at integer frame 0 is decoded.",
            "The caller-supplied world/object transform is intentionally identity for a model-space OBJ.",
            "OBJ/MTL does not encode JFG per-triangle culling or exact RDP sampling.",
            "Three UNKNOWN-format group textures remain untextured.",
        ],
    }
    obj = "\n".join(obj_lines) + "\n"
    return {
        "boy-anim0-frame0-experimental.obj": obj.encode(),
        "boy-anim0-frame0-experimental.mtl": mtl.encode(),
        "boy-anim0-frame0-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
        "materials-and-groups.md": _overview(groups, materials).encode(),
        "BLENDER.md": _blender_guide().encode(),
    }


def export_boy_anim0_frame0(boy_path: Path, rom_path: Path, texture_manifest: Path, output_dir: Path) -> dict[str, Any]:
    boy_path = boy_path.resolve(strict=True)
    rom_path = rom_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    boy_data, rom = boy_path.read_bytes(), rom_path.read_bytes()
    first = build_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("Boy animation-0/frame-0 artifacts are not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items():
        (output_dir / name).write_bytes(data)
    return json.loads(first["boy-anim0-frame0-report.json"])
