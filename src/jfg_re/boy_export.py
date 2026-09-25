"""Experimental, asset-pinned static exporter for US Prop 220 ``Boy``.

This module is intentionally not a general JFG model exporter.  It preserves
the verified raw geometry relationships and emits diagnostic metadata without
inventing a bind pose, animation, vertex attribute semantics, or OBJ UVs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any
import zlib

from jfg_re.props import COMPRESSION_MARKER, validate_rom_identity


BOY_PROP_ID = 220
BOY_NAME = "Boy"
BOY_SIZE = 0x5170
BOY_SHA256 = "2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf"

TEXTURE_START = 0x88
TEXTURE_COUNT = 18
TEXTURE_RECORD_SIZE = 8
GROUP_START = 0x118
GROUP_COUNT = 82
GROUP_RECORD_SIZE = 16
TRIANGLE_START = 0x648
TRIANGLE_COUNT = 520
TRIANGLE_RECORD_SIZE = 16
VERTEX_START = 0x26C8
VERTEX_COUNT = 660
VERTEX_RECORD_SIZE = 10
RECORDS_END = 0x4090
BONE_START = 0x4098
BONE_COUNT = 21

ASSET_LUT_START = 0xB1750
ASSET_DATA_START = 0xB1880


class BoyExportError(ValueError):
    """Raised when a pinned input or a verified relationship differs."""


@dataclass(frozen=True)
class Vertex:
    x: int
    y: int
    z: int
    attributes: tuple[int, int, int, int]


@dataclass(frozen=True)
class Group:
    index: int
    texture_index: int
    matrix_ids: tuple[int, int, int]
    matrix_splits: tuple[int, int]
    vertex_start: int
    triangle_start: int
    byte_10: int
    frame_argument: int
    render_flags: int

    @property
    def runtime_skipped(self) -> bool:
        return bool(self.render_flags & 0x400)


@dataclass(frozen=True)
class Triangle:
    index: int
    flag: int
    local_indices: tuple[int, int, int]
    corner_pairs: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]


@dataclass(frozen=True)
class BoyModel:
    vertices: tuple[Vertex, ...]
    groups: tuple[Group, ...]
    sentinel: Group
    triangles: tuple[Triangle, ...]
    texture_records: tuple[bytes, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _be_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _be_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _parse_group(data: bytes, index: int, group_start: int = GROUP_START) -> Group:
    offset = group_start + index * GROUP_RECORD_SIZE
    return Group(
        index=index,
        texture_index=data[offset],
        matrix_ids=tuple(data[offset + 1 : offset + 4]),
        matrix_splits=tuple(data[offset + 4 : offset + 6]),
        vertex_start=_be_u16(data, offset + 6),
        triangle_start=_be_u16(data, offset + 8),
        byte_10=data[offset + 10],
        frame_argument=data[offset + 11],
        render_flags=_be_u32(data, offset + 12),
    )


def parse_model(data: bytes) -> BoyModel:
    """Parse the verified compact model records used by Boy and BoyGun Props.

    This is the record loop extracted from :func:`parse_boy`.  It reads counts
    and section starts from the same established header fields; it does not
    assign meanings to any unverified trailing sections.
    """
    if len(data) < 0x58:
        raise BoyExportError("Model data is shorter than the verified header fields.")
    texture_count = data[0x10]
    vertex_count = struct.unpack_from(">h", data, 0x12)[0]
    group_count = struct.unpack_from(">h", data, 0x16)[0]
    texture_start = _be_u32(data, 0x18)
    vertex_start = _be_u32(data, 0x1C)
    triangle_start = _be_u32(data, 0x20)
    group_start = _be_u32(data, 0x24)
    if vertex_count < 0 or group_count <= 0:
        raise BoyExportError("Model header has invalid vertex or group counts.")
    if any(offset < 0x58 or offset > len(data) for offset in (texture_start, vertex_start, triangle_start, group_start)):
        raise BoyExportError("Model section start lies outside the input.")
    if texture_start + texture_count * TEXTURE_RECORD_SIZE > len(data):
        raise BoyExportError("Model texture records exceed the input.")
    if group_start + (group_count + 1) * GROUP_RECORD_SIZE > len(data):
        raise BoyExportError("Model group table and sentinel exceed the input.")
    if vertex_start + vertex_count * VERTEX_RECORD_SIZE > len(data):
        raise BoyExportError("Model vertex records exceed the input.")

    groups_with_sentinel = tuple(_parse_group(data, index, group_start) for index in range(group_count + 1))
    groups, sentinel = groups_with_sentinel[:-1], groups_with_sentinel[-1]
    if (groups[0].vertex_start, groups[0].triangle_start) != (0, 0):
        raise BoyExportError("Model group table does not start at zero.")
    triangle_count = sentinel.triangle_start
    if sentinel.vertex_start != vertex_count:
        raise BoyExportError("Model group sentinel does not terminate the vertex array.")
    if triangle_start + triangle_count * TRIANGLE_RECORD_SIZE > len(data):
        raise BoyExportError("Model triangle records exceed the input.")
    for current, following in zip(groups_with_sentinel, groups_with_sentinel[1:]):
        if current.vertex_start >= following.vertex_start or current.triangle_start >= following.triangle_start:
            raise BoyExportError("Model group ranges are not strictly increasing.")

    vertices = tuple(
        Vertex(*struct.unpack_from(">hhh", data, vertex_start + index * VERTEX_RECORD_SIZE),
               tuple(data[vertex_start + index * VERTEX_RECORD_SIZE + 6 : vertex_start + index * VERTEX_RECORD_SIZE + 10]))
        for index in range(vertex_count)
    )
    triangles = tuple(
        Triangle(
            index=index,
            flag=data[triangle_start + index * TRIANGLE_RECORD_SIZE],
            local_indices=tuple(data[triangle_start + index * TRIANGLE_RECORD_SIZE + 1 : triangle_start + index * TRIANGLE_RECORD_SIZE + 4]),
            corner_pairs=tuple(
                struct.unpack_from(">hh", data, triangle_start + index * TRIANGLE_RECORD_SIZE + 4 + corner * 4)
                for corner in range(3)
            ),
        )
        for index in range(triangle_count)
    )
    for group, following in zip(groups, groups_with_sentinel[1:]):
        local_count = following.vertex_start - group.vertex_start
        for triangle in triangles[group.triangle_start : following.triangle_start]:
            if any(index >= local_count for index in triangle.local_indices):
                raise BoyExportError(f"Triangle {triangle.index} indexes outside group {group.index}.")
    texture_records = tuple(
        data[texture_start + index * TEXTURE_RECORD_SIZE : texture_start + (index + 1) * TEXTURE_RECORD_SIZE]
        for index in range(texture_count)
    )
    return BoyModel(vertices, groups, sentinel, triangles, texture_records)


def parse_boy(data: bytes) -> BoyModel:
    """Parse only the pinned US Prop 220 and validate its known boundaries."""
    if len(data) != BOY_SIZE or _sha256(data) != BOY_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 220 Boy binary.")
    if data[:4] != b"Boy\0":
        raise BoyExportError("Pinned Boy name bytes differ.")
    boundaries = [_be_u32(data, offset) for offset in (0x18, 0x1C, 0x20, 0x24, 0x30, 0x34, 0x48)]
    if boundaries != [TEXTURE_START, VERTEX_START, TRIANGLE_START, GROUP_START, RECORDS_END, 0x41E8, BOY_SIZE]:
        raise BoyExportError("Pinned Boy section boundaries differ.")
    if data[0x10] != TEXTURE_COUNT or struct.unpack_from(">h", data, 0x12)[0] != VERTEX_COUNT:
        raise BoyExportError("Pinned Boy texture or vertex count differs.")
    if struct.unpack_from(">h", data, 0x16)[0] != GROUP_COUNT or data[0x4F] != BONE_COUNT:
        raise BoyExportError("Pinned Boy group or transform count differs.")
    model = parse_model(data)
    if (model.sentinel.vertex_start, model.sentinel.triangle_start) != (VERTEX_COUNT, TRIANGLE_COUNT):
        raise BoyExportError("Boy group sentinel does not terminate both record arrays.")
    if VERTEX_START + VERTEX_COUNT * VERTEX_RECORD_SIZE != RECORDS_END:
        raise BoyExportError("Boy vertex section does not meet its verified end.")
    return model


def _matrix_id(group: Group, local_vertex: int) -> int | None:
    if group.runtime_skipped:
        return None
    first, second = group.matrix_splits
    if local_vertex < first:
        return group.matrix_ids[0]
    if local_vertex < second:
        return group.matrix_ids[1]
    return group.matrix_ids[2]


def _cross(points: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]) -> tuple[int, int, int]:
    a, b, c = points
    ab = tuple(b[axis] - a[axis] for axis in range(3))
    ac = tuple(c[axis] - a[axis] for axis in range(3))
    return (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )


def _asset_lut(rom: bytes) -> tuple[int, ...]:
    if len(rom) < ASSET_DATA_START:
        raise BoyExportError("ROM is too small to contain the verified asset LUT.")
    words = struct.unpack(
        f">{(ASSET_DATA_START - ASSET_LUT_START) // 4}I",
        rom[ASSET_LUT_START:ASSET_DATA_START],
    )
    if words[0] != 0x47:
        raise BoyExportError(f"Unexpected JFG asset section count 0x{words[0]:X}.")
    return words


def _asset_range(lut: tuple[int, ...], asset_index: int) -> tuple[int, int]:
    start = ASSET_DATA_START + lut[asset_index + 1]
    end = ASSET_DATA_START + lut[asset_index + 2]
    if start > end:
        raise BoyExportError(f"Asset section {asset_index} is descending.")
    return start, end


def _load_texture_manifest(path: Path) -> dict[int, dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BoyExportError(f"Cannot read verified RGBA16 manifest: {error}") from error
    records = document.get("textures")
    if document.get("schema_version") != 1 or not isinstance(records, list):
        raise BoyExportError("Unexpected verified RGBA16 manifest schema.")
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        offset = record.get("rom_offset")
        if isinstance(offset, int):
            result[offset] = record
    return result


def decompress_texture_container(rom: bytes, offset: int) -> bytes:
    if offset + 5 > len(rom):
        raise BoyExportError(f"Texture container 0x{offset:X} is outside the ROM.")
    expected = struct.unpack_from("<I", rom, offset)[0]
    if rom[offset + 4] != COMPRESSION_MARKER:
        raise BoyExportError(f"Texture container 0x{offset:X} lacks raw-deflate marker 0x09.")
    try:
        decoded = zlib.decompress(rom[offset + 5 :], wbits=-15)
    except zlib.error as error:
        raise BoyExportError(f"Texture container 0x{offset:X} failed to decompress: {error}") from error
    if len(decoded) != expected:
        raise BoyExportError(f"Texture container 0x{offset:X} decoded to {len(decoded)}, expected {expected} bytes.")
    return decoded


def resolve_boy_textures(
    model: BoyModel,
    rom: bytes,
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """Follow Boy TextureRecord IDs through texLoadTexture's verified table path."""
    lut = _asset_lut(rom)
    verified_by_offset = _load_texture_manifest(manifest_path)
    resolutions: list[dict[str, Any]] = []
    by_index: dict[int, dict[str, Any]] = {}
    for texture_index, raw in enumerate(model.texture_records):
        texture_id = _be_u16(raw, 6)
        high_table = bool(texture_id & 0x8000)
        lookup_index = texture_id & 0x7FFF
        table_asset_index = 1 if high_table else 3
        data_asset_index = 0 if high_table else 2
        table_start, table_end = _asset_range(lut, table_asset_index)
        table_words = struct.unpack(f">{(table_end - table_start) // 4}I", rom[table_start:table_end])
        if lookup_index + 1 >= len(table_words):
            raise BoyExportError(f"Texture ID 0x{texture_id:04X} is outside texture offset table {table_asset_index}.")
        local_start, local_end = table_words[lookup_index : lookup_index + 2]
        data_start, data_end = _asset_range(lut, data_asset_index)
        asset_start = data_start + local_start
        asset_end = data_start + local_end
        if asset_start < data_start or asset_end > data_end or asset_start + 32 > asset_end:
            raise BoyExportError(f"Texture ID 0x{texture_id:04X} resolves outside asset section {data_asset_index}.")
        header = rom[asset_start : asset_start + 32]
        compressed_stream_offset = asset_start + 32
        marker = header[2:4]
        manifest_record = verified_by_offset.get(compressed_stream_offset)
        verified_rgba16 = False
        reason: str | None = None
        png_path: str | None = None
        if marker == b"\x11\x00" and manifest_record is not None:
            decoded = decompress_texture_container(rom, compressed_stream_offset)
            required = {
                "status": "VERIFIED",
                "decoder_id": "rgba16-blockswap-v1",
                "rom_binary_match": True,
                "reference_pixel_match": True,
            }
            if any(manifest_record.get(key) != value for key, value in required.items()):
                raise BoyExportError(f"RGBA16 manifest entry for 0x{compressed_stream_offset:X} is not fully verified.")
            if _sha256(decoded) != manifest_record.get("binary_sha256"):
                raise BoyExportError(f"RGBA16 binary hash differs for texture ID 0x{texture_id:04X}.")
            if decoded[:2] != header[:2] or decoded[2:4] != marker:
                raise BoyExportError(f"Runtime header and RGBA16 container differ for texture ID 0x{texture_id:04X}.")
            verified_rgba16 = True
            png_path = manifest_record["output_png"]
        elif marker != b"\x11\x00":
            reason = f"format marker {marker.hex()} is outside the verified 11 00 RGBA16 pipeline"
        else:
            reason = "no matching entry in the verified RGBA16 manifest"
        record = {
            "texture_index": texture_index,
            "texture_record_hex": raw.hex(),
            "texture_id": texture_id,
            "texture_id_hex": f"0x{texture_id:04X}",
            "texLoadTexture_table_path": "high-bit: table asset 1 -> data asset 0" if high_table else "low-bit: table asset 3 -> data asset 2",
            "lookup_index": lookup_index,
            "runtime_asset_rom_start": asset_start,
            "runtime_asset_rom_start_hex": f"0x{asset_start:X}",
            "runtime_asset_rom_end": asset_end,
            "runtime_asset_size": asset_end - asset_start,
            "runtime_header_hex": header.hex(),
            "runtime_width": header[0],
            "runtime_height": header[1],
            "runtime_format_marker": marker.hex(),
            "runtime_compressed_flag": header[0x19],
            "compressed_stream_rom_offset": compressed_stream_offset,
            "compressed_stream_rom_offset_hex": f"0x{compressed_stream_offset:X}",
            "runtime_asset_resolution_status": "VERIFIED",
            "verified_rgba16_match": verified_rgba16,
            "verified_rgba16_png": png_path,
            "rgba16_unresolved_reason": reason,
        }
        resolutions.append(record)
        by_index[texture_index] = record
    return resolutions, by_index


def _material_name(group: Group, texture: dict[str, Any] | None) -> str:
    if group.texture_index == 0xFF:
        return "texture_none"
    assert texture is not None
    suffix = "rgba16_verified" if texture["verified_rgba16_match"] else "unsupported_format"
    return f"texture_{group.texture_index:02d}_id_{texture['texture_id']:04x}_{suffix}"


def _material_textures(model: BoyModel, textures: dict[int, dict[str, Any]]) -> list[tuple[str, dict[str, Any] | None]]:
    materials: dict[str, dict[str, Any] | None] = {"texture_none": None}
    for group in model.groups:
        texture = None if group.texture_index == 0xFF else textures[group.texture_index]
        materials[_material_name(group, texture)] = texture
    return sorted(materials.items())


def _make_mtl(
    model: BoyModel,
    textures: dict[int, dict[str, Any]],
    manifest_path: Path,
    output_dir: Path,
) -> str:
    lines = [
        "# Boy Prop 220 experimental materials",
        "# Texture identity is verified where marked; OBJ UV emission is intentionally omitted.",
    ]
    for ordinal, (name, texture) in enumerate(_material_textures(model, textures)):
        red = ((ordinal * 73) % 191 + 32) / 255
        green = ((ordinal * 109) % 191 + 32) / 255
        blue = ((ordinal * 151) % 191 + 32) / 255
        lines.extend(("", f"newmtl {name}", f"Kd {red:.6f} {green:.6f} {blue:.6f}", "Ka 0.000000 0.000000 0.000000", "d 1.0"))
        if texture and texture["verified_rgba16_match"]:
            png = manifest_path.parent / texture["verified_rgba16_png"]
            relative = os.path.relpath(png, output_dir).replace("\\", "/")
            lines.append(f"map_Kd {relative}")
    return "\n".join(lines) + "\n"


def _geometry_records(model: BoyModel) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, int]]:
    triangle_records: list[dict[str, Any]] = []
    vertex_records: list[dict[str, Any]] = []
    group_for_vertex: dict[int, int] = {}
    used_matrices: Counter[int] = Counter()
    for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
        for absolute in range(group.vertex_start, following.vertex_start):
            local = absolute - group.vertex_start
            matrix = _matrix_id(group, local)
            if matrix is not None:
                if matrix >= BONE_COUNT:
                    raise BoyExportError(f"Active group {group.index} selects invalid matrix ID {matrix}.")
                used_matrices[matrix] += 1
            vertex = model.vertices[absolute]
            group_for_vertex[absolute] = group.index
            vertex_records.append({
                "vertex_index": absolute,
                "group_index": group.index,
                "group_runtime_skipped": group.runtime_skipped,
                "local_vertex_index": local,
                "xyz_s16": [vertex.x, vertex.y, vertex.z],
                "f3ddkr_attributes_unknown": list(vertex.attributes),
                "f3ddkr_attributes_hex": bytes(vertex.attributes).hex(),
                "matrix_id": matrix,
                "matrix_assignment_status": "VERIFIED" if matrix is not None else "UNKNOWN for runtime-skipped 0x400 group",
            })
        group_vertex_count = following.vertex_start - group.vertex_start
        for triangle_index in range(group.triangle_start, following.triangle_start):
            triangle = model.triangles[triangle_index]
            if any(index >= group_vertex_count for index in triangle.local_indices):
                raise BoyExportError(f"Triangle {triangle_index} has an index outside group {group.index}.")
            absolute_indices = tuple(group.vertex_start + index for index in triangle.local_indices)
            points = tuple((model.vertices[index].x, model.vertices[index].y, model.vertices[index].z) for index in absolute_indices)
            cross = _cross(points)
            degenerate = cross == (0, 0, 0)
            triangle_records.append({
                "triangle_index": triangle_index,
                "group_index": group.index,
                "group_runtime_skipped": group.runtime_skipped,
                "flag": triangle.flag,
                "flag_hex": f"0x{triangle.flag:02X}",
                "bit_0x40_disables_backface_culling": bool(triangle.flag & 0x40),
                "local_vertex_indices": list(triangle.local_indices),
                "absolute_vertex_indices": list(absolute_indices),
                "corner_coordinate_pairs_raw_s16": [list(pair) for pair in triangle.corner_pairs],
                "corner_pair_semantics": "LIKELY UV; raw F3DDKR per-corner pairs are VERIFIED",
                "matrix_ids": [_matrix_id(group, index) for index in triangle.local_indices],
                "xyz_points": [list(point) for point in points],
                "cross_product": list(cross),
                "geometrically_degenerate": degenerate,
                "degenerate_reason": "repeated XYZ point" if degenerate and len(set(points)) < 3 else ("collinear XYZ points" if degenerate else None),
                "exported_in_all_groups_obj": not degenerate,
                "exported_in_runtime_visible_obj": not degenerate and not group.runtime_skipped,
            })
    if len(vertex_records) != VERTEX_COUNT or len(triangle_records) != TRIANGLE_COUNT:
        raise BoyExportError("Parsed group ranges do not cover all Boy records exactly once.")
    return vertex_records, triangle_records, dict(sorted(used_matrices.items()))


def _make_obj(
    model: BoyModel,
    triangle_records: list[dict[str, Any]],
    textures: dict[int, dict[str, Any]],
    runtime_visible_only: bool,
) -> str:
    scope = "runtime-visible groups only" if runtime_visible_only else "all groups including runtime-skipped groups"
    lines = [
        "# Boy Prop 220 experimental static raw XYZ mesh",
        f"# Scope: {scope}",
        "# No bone transforms, bind pose, animation, normals, or interpreted UVs.",
        "mtllib boy-materials.mtl",
        "o Boy_Prop_0220_EXPERIMENTAL",
    ]
    lines.extend(f"v {vertex.x} {vertex.y} {vertex.z}" for vertex in model.vertices)
    by_triangle = {record["triangle_index"]: record for record in triangle_records}
    for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
        if runtime_visible_only and group.runtime_skipped:
            continue
        texture = None if group.texture_index == 0xFF else textures[group.texture_index]
        lines.extend((
            "",
            f"g group_{group.index:02d}_{'skipped_0x400' if group.runtime_skipped else 'active'}",
            f"usemtl {_material_name(group, texture)}",
            "s off",
        ))
        for triangle_index in range(group.triangle_start, following.triangle_start):
            record = by_triangle[triangle_index]
            pairs = ";".join(f"{u},{v}" for u, v in record["corner_coordinate_pairs_raw_s16"])
            lines.append(
                f"# tri={triangle_index} flag={record['flag_hex']} raw_corner_pairs={pairs}"
                f" matrix_ids={record['matrix_ids']}"
            )
            if record["geometrically_degenerate"]:
                lines.append("# omitted: geometrically degenerate in stored XYZ")
                continue
            lines.append("f " + " ".join(str(index + 1) for index in record["absolute_vertex_indices"]))
    return "\n".join(lines) + "\n"


def _json_lines(records: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records)


def build_boy_export_artifacts(
    boy_data: bytes,
    rom: bytes,
    texture_manifest: Path,
    output_dir: Path,
) -> dict[str, bytes]:
    """Build deterministic export bytes without touching the filesystem."""
    model = parse_boy(boy_data)
    texture_resolutions, textures_by_index = resolve_boy_textures(model, rom, texture_manifest)
    vertex_records, triangle_records, used_matrices = _geometry_records(model)
    degenerate = [record for record in triangle_records if record["geometrically_degenerate"]]
    active_groups = [group for group in model.groups if not group.runtime_skipped]
    skipped_groups = [group for group in model.groups if group.runtime_skipped]
    all_faces = sum(record["exported_in_all_groups_obj"] for record in triangle_records)
    runtime_faces = sum(record["exported_in_runtime_visible_obj"] for record in triangle_records)
    used_texture_indices = sorted({group.texture_index for group in model.groups})
    verified_textures = [record for record in texture_resolutions if record["verified_rgba16_match"]]
    unsupported_textures = [record for record in texture_resolutions if not record["verified_rgba16_match"]]
    groups_report = []
    for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
        texture = None if group.texture_index == 0xFF else textures_by_index[group.texture_index]
        groups_report.append({
            "group_index": group.index,
            "runtime_status": "SKIPPED_FLAG_0x400" if group.runtime_skipped else "ACTIVE",
            "texture_index": group.texture_index,
            "texture_id_hex": texture["texture_id_hex"] if texture else None,
            "verified_rgba16_texture": texture["verified_rgba16_png"] if texture and texture["verified_rgba16_match"] else None,
            "matrix_ids_raw": list(group.matrix_ids),
            "matrix_splits": list(group.matrix_splits),
            "vertex_range": [group.vertex_start, following.vertex_start],
            "triangle_range": [group.triangle_start, following.triangle_start],
            "render_flags_hex": f"0x{group.render_flags:08X}",
        })
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "EXPERIMENTAL Boy-only static exporter",
        "scope": "Prop 220 Boy only; stored XYZ; no bind pose, animation, skinning, or interpreted OBJ UVs",
        "input": {"prop_id": BOY_PROP_ID, "name": BOY_NAME, "size_bytes": BOY_SIZE, "sha256": BOY_SHA256},
        "counts": {
            "vertex_records": VERTEX_COUNT,
            "triangle_records": TRIANGLE_COUNT,
            "all_groups_exported_faces": all_faces,
            "runtime_visible_exported_faces": runtime_faces,
            "geometrically_degenerate_faces": len(degenerate),
            "groups": GROUP_COUNT,
            "active_groups": len(active_groups),
            "runtime_skipped_groups": len(skipped_groups),
            "group_records_including_sentinel": GROUP_COUNT + 1,
        },
        "used_matrix_ids": sorted(used_matrices),
        "vertices_per_matrix_id": {str(key): value for key, value in used_matrices.items()},
        "used_texture_indices": [f"0x{value:02X}" for value in used_texture_indices],
        "texture_resolution": {
            "runtime_texture_ids_resolved": len(texture_resolutions),
            "resolved_texture_ids": [record["texture_id_hex"] for record in texture_resolutions],
            "verified_rgba16_matches": len(verified_textures),
            "verified_rgba16_texture_ids": [record["texture_id_hex"] for record in verified_textures],
            "not_in_verified_rgba16_pipeline": len(unsupported_textures),
            "unresolved_rgba16_texture_ids": [record["texture_id_hex"] for record in unsupported_textures],
            "records": texture_resolutions,
        },
        "degenerate_triangles": degenerate,
        "groups_detail": groups_report,
        "interpretations": {
            "VERIFIED": [
                "Prop identity and section boundaries",
                "stored Big-Endian s16 XYZ and 10-byte vertex stride",
                "group ranges and local triangle indices",
                "per-corner raw s16 coordinate pairs are passed through the F3DDKR triangle ABI",
                "active-group rigid matrix ID selection metadata",
                "triangle bit 0x40 disables winding-based backface rejection",
                "all 18 texture IDs resolve through texLoadTexture's high-bit table path to ROM assets",
                "14 resolved ROM assets match the existing pixel-verified 11 00 RGBA16 manifest",
            ],
            "LIKELY": ["the three per-corner coordinate pairs are texture coordinates"],
            "HYPOTHESIS": [],
            "UNKNOWN": [
                "bind/rest-pose meaning of the transform-record float triplets",
                "semantics of vertex bytes +6..+9 for every group",
                "OBJ V-axis conversion and final wrap/clamp behavior for each rendered group",
                "formats represented by texture IDs outside the verified 11 00 RGBA16 set",
                "semantics of runtime-skipped 0x400 groups beyond their observed skip behavior",
            ],
        },
        "uv_investigation": {
            "raw_pairs_preserved": True,
            "rsp_copy_to_vertex_cache": "VERIFIED: triangle +4..+15 copied unchanged to three vertex slots +0x14",
            "fixed_point_evidence": "JFG PR/gt.h labels transformed s/t as S10.5; this supports 1/32-texel units but does not settle OBJ V orientation",
            "obj_vt_emitted": False,
            "reason": "No V flip, origin, and complete per-group sampler interpretation was established without an extra convention.",
        },
        "validation": {
            "all_triangle_indices_within_group_vertex_ranges": True,
            "group_ranges_cover_all_records_once": True,
            "all_15_previous_degenerate_candidates_confirmed_by_zero_xyz_cross_product": len(degenerate) == 15,
            "all_degenerate_records_have_repeated_xyz_points": all(record["degenerate_reason"] == "repeated XYZ point" for record in degenerate),
            "powerboy_processed": False,
            "deterministic_regeneration_match": True,
        },
    }
    files = {
        "boy-materials.mtl": _make_mtl(model, textures_by_index, texture_manifest, output_dir),
        "boy-raw-all-groups.obj": _make_obj(model, triangle_records, textures_by_index, False),
        "boy-runtime-visible.obj": _make_obj(model, triangle_records, textures_by_index, True),
        "boy-vertices.jsonl": _json_lines(vertex_records),
        "boy-triangles.jsonl": _json_lines(triangle_records),
        "boy-export-report.json": json.dumps(report, indent=2, sort_keys=True) + "\n",
    }
    return {name: content.encode("utf-8") for name, content in sorted(files.items())}


def export_boy(
    boy_path: Path,
    rom_path: Path,
    texture_manifest: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate inputs, build twice for determinism, then write a new directory."""
    identity = validate_rom_identity(rom_path)
    boy_path = boy_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to write into existing output directory: {output_dir}")
    boy_data = boy_path.read_bytes()
    rom = identity.path.read_bytes()
    first = build_boy_export_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_boy_export_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("In-memory deterministic regeneration check failed.")
    output_dir.mkdir(parents=True)
    for name, content in first.items():
        (output_dir / name).write_bytes(content)
    return json.loads(first["boy-export-report.json"])
