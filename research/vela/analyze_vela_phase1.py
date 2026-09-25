"""Reproducible Phase-1 structural analysis for US Prop 218 ``Girl``.

This research helper deliberately consumes the existing verified prop/model
and texture primitives. It does not add Vela behavior to the production Forge
loaders and does not decode animation data.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"

import sys

sys.path.insert(0, str(SOURCE_ROOT))

from jfg_re.boy_export import (  # noqa: E402
    _cross,
    _matrix_id,
    parse_model,
    resolve_boy_textures,
)
from jfg_re.boy_hand_object_link import (  # noqa: E402
    OBJECT_HEADER_DATA_ASSET,
    OBJECT_HEADER_TABLE_ASSET,
    _asset,
    _header_offsets,
    _model_ids,
    _object_definitions_using_model,
)
from jfg_re.props import (  # noqa: E402
    PROP_DATA_BASE,
    PROP_TABLE_ENTRIES,
    PROP_TABLE_OFFSET,
    decode_prop_block,
    parse_offset_table,
    validate_rom_identity,
)


PROP_ID = 218
PROP_NAME = "Girl"
EXPECTED_SIZE = 19_016
EXPECTED_SHA256 = "daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409"
PLAYER_OBJECT_DEFINITION_ID = 0
GIRLGUN_OBJECT_DEFINITION_ID = 397


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _name(data: bytes, start: int = 0) -> str:
    return data[start : data.index(0, start)].decode("ascii")


def _object_header(rom: bytes, header_id: int) -> tuple[int, bytes]:
    _, _, table = _asset(rom, OBJECT_HEADER_TABLE_ASSET)
    data_start, _, data = _asset(rom, OBJECT_HEADER_DATA_ASSET)
    offsets = _header_offsets(table)
    return data_start + offsets[header_id], data[offsets[header_id] : offsets[header_id + 1]]


def _child_ids(header: bytes) -> list[int]:
    count = header[0x20]
    relative_offset = _u32(header, 0x34)
    if relative_offset + count * 4 > len(header):
        raise ValueError("Object-header child list exceeds its header.")
    return list(struct.unpack_from(f">{count}I", header, relative_offset)) if count else []


def _sections(data: bytes) -> dict[str, Any]:
    texture_count = data[0x10]
    vertex_count, triangle_count, group_count = struct.unpack_from(">HHH", data, 0x12)
    texture_start = _u32(data, 0x18)
    vertex_start = _u32(data, 0x1C)
    triangle_start = _u32(data, 0x20)
    group_start = _u32(data, 0x24)
    reference_start = _u32(data, 0x30)
    transform_end = _u32(data, 0x34)
    trailing_start = _u32(data, 0x38)
    declared_file_size = _u32(data, 0x48)
    transform_count = data[0x4F]
    transform_start = _u32(data, 0x54)
    return {
        "header": {"start": 0, "end": texture_start, "size": texture_start},
        "texture_records": {
            "start": texture_start,
            "end": texture_start + texture_count * 8,
            "count": texture_count,
            "stride": 8,
        },
        "pre_group_unknown": {
            "start": texture_start + texture_count * 8,
            "end": group_start,
            "size": group_start - (texture_start + texture_count * 8),
        },
        "groups_with_boundary": {
            "start": group_start,
            "end": triangle_start,
            "active_record_count": group_count,
            "stored_record_count": group_count + 1,
            "stride": 16,
        },
        "triangles": {
            "start": triangle_start,
            "end": vertex_start,
            "count": triangle_count,
            "stride": 16,
        },
        "vertices": {
            "start": vertex_start,
            "end": reference_start,
            "count": vertex_count,
            "stride": 10,
        },
        "vertex_references": {
            "start": reference_start,
            "end": transform_start,
            "count": (transform_start - reference_start) // 4,
            "stride": 4,
        },
        "transforms": {
            "start": transform_start,
            "end": transform_end,
            "count": transform_count,
            "stride": 16,
        },
        "trailing_unknown": {
            "start": trailing_start,
            "end": declared_file_size,
            "size": declared_file_size - trailing_start,
        },
        "declared_file_size": declared_file_size,
    }


def _geometry(data: bytes) -> dict[str, Any]:
    model = parse_model(data)
    active_group_ids: list[int] = []
    skipped_group_ids: list[int] = []
    active_referenced_vertices: set[int] = set()
    active_assignments: dict[int, int] = {}
    assignment_conflicts: list[dict[str, int]] = []
    active_matrix_ids: set[int] = set()
    active_faces = 0
    active_degenerate = 0
    skipped_faces = 0
    skipped_degenerate = 0
    active_split_violations: list[int] = []
    skipped_split_violations: list[int] = []

    for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
        local_count = following.vertex_start - group.vertex_start
        split_valid = 0 <= group.matrix_splits[0] <= group.matrix_splits[1] <= local_count
        if group.runtime_skipped:
            skipped_group_ids.append(group.index)
            if not split_valid:
                skipped_split_violations.append(group.index)
        else:
            active_group_ids.append(group.index)
            if not split_valid:
                active_split_violations.append(group.index)

        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            global_indices = [group.vertex_start + local for local in triangle.local_indices]
            points = tuple(
                (model.vertices[index].x, model.vertices[index].y, model.vertices[index].z)
                for index in global_indices
            )
            degenerate = _cross(points) == (0, 0, 0)
            if group.runtime_skipped:
                skipped_faces += 1
                skipped_degenerate += int(degenerate)
                continue
            active_faces += 1
            active_degenerate += int(degenerate)
            for local, absolute in zip(triangle.local_indices, global_indices):
                matrix_id = _matrix_id(group, local)
                if matrix_id is None:
                    raise ValueError("Active Girl group has no matrix assignment.")
                active_matrix_ids.add(matrix_id)
                active_referenced_vertices.add(absolute)
                previous = active_assignments.setdefault(absolute, matrix_id)
                if previous != matrix_id:
                    assignment_conflicts.append(
                        {"vertex": absolute, "first_matrix": previous, "second_matrix": matrix_id}
                    )

    return {
        "stored_vertices": len(model.vertices),
        "stored_triangle_records": len(model.triangles),
        "group_count": len(model.groups),
        "active_group_count": len(active_group_ids),
        "active_group_ids": active_group_ids,
        "skipped_group_count": len(skipped_group_ids),
        "skipped_group_ids": skipped_group_ids,
        "active_triangle_records": active_faces,
        "active_geometrically_degenerate": active_degenerate,
        "active_nondegenerate_faces": active_faces - active_degenerate,
        "skipped_triangle_records": skipped_faces,
        "skipped_geometrically_degenerate": skipped_degenerate,
        "skipped_nondegenerate_faces": skipped_faces - skipped_degenerate,
        "active_referenced_source_vertices": len(active_referenced_vertices),
        "active_matrix_ids": sorted(active_matrix_ids),
        "active_vertex_matrix_assignment_conflicts": assignment_conflicts,
        "active_group_split_violations": active_split_violations,
        "skipped_group_split_violations": skipped_split_violations,
        "raw_xyz_bbox": {
            "minimum": [min((v.x, v.y, v.z)[axis] for v in model.vertices) for axis in range(3)],
            "maximum": [max((v.x, v.y, v.z)[axis] for v in model.vertices) for axis in range(3)],
        },
        "texture_indices_used_by_active_groups": sorted(
            {group.texture_index for group in model.groups if not group.runtime_skipped and group.texture_index != 0xFF}
        ),
        "texture_indices_used_by_all_groups": sorted(
            {group.texture_index for group in model.groups if group.texture_index != 0xFF}
        ),
        "structural_checks": {
            "group_ranges_strictly_increasing": True,
            "sentinel_matches_header_counts": True,
            "all_triangle_local_indices_in_range": True,
            "all_active_group_splits_valid": not active_split_violations,
            "no_active_vertex_matrix_conflicts": not assignment_conflicts,
        },
    }


def _transforms_and_references(data: bytes, sections: dict[str, Any]) -> dict[str, Any]:
    vertex_start = sections["vertices"]["start"]
    references = []
    for index in range(sections["vertex_references"]["count"]):
        offset = sections["vertex_references"]["start"] + index * 4
        vertex_id, matrix_id = struct.unpack_from(">HH", data, offset)
        references.append(
            {
                "record_index": index,
                "file_offset": offset,
                "vertex_id": vertex_id,
                "matrix_id": matrix_id,
                "source_xyz_s16": list(struct.unpack_from(">hhh", data, vertex_start + vertex_id * 10)),
            }
        )

    records = []
    for index in range(sections["transforms"]["count"]):
        offset = sections["transforms"]["start"] + index * 16
        parent_id, target_id, channel_a, channel_b = data[offset : offset + 4]
        records.append(
            {
                "record_index": index,
                "file_offset": offset,
                "parent_id": parent_id,
                "target_matrix_id": target_id,
                "channel_bytes": [channel_a, channel_b],
                "local_translation_xyz_f32": list(struct.unpack_from(">fff", data, offset + 4)),
            }
        )

    targets = {record["target_matrix_id"] for record in records}
    roots = [record["target_matrix_id"] for record in records if record["parent_id"] == 0xFF]
    return {
        "vertex_references": references,
        "transform_records": records,
        "topology": {
            "roots": roots,
            "target_ids": sorted(targets),
            "target_ids_unique": len(targets) == len(records),
            "all_parents_valid": all(
                record["parent_id"] == 0xFF or record["parent_id"] in targets for record in records
            ),
            "parent_before_child": all(
                record["parent_id"] == 0xFF or record["parent_id"] < record["target_matrix_id"]
                for record in records
            ),
            "edges": [
                [record["parent_id"], record["target_matrix_id"]]
                for record in records
                if record["parent_id"] != 0xFF
            ],
        },
    }


def _textures(data: bytes, rom: bytes, manifest_path: Path) -> dict[str, Any]:
    model = parse_model(data)
    resolutions, _ = resolve_boy_textures(model, rom, manifest_path)
    records = [
        {
            "texture_index": record["texture_index"],
            "texture_id": record["texture_id"],
            "texture_id_hex": record["texture_id_hex"],
            "width": record["runtime_width"],
            "height": record["runtime_height"],
            "format_marker": record["runtime_format_marker"],
            "asset_rom_start": record["runtime_asset_rom_start"],
            "compressed_stream_rom_offset": record["compressed_stream_rom_offset"],
            "verified_rgba16": record["verified_rgba16_match"],
        }
        for record in resolutions
    ]
    markers = Counter(record["format_marker"] for record in records)
    return {
        "record_count": len(records),
        "verified_rgba16_count": sum(record["verified_rgba16"] for record in records),
        "unsupported_count": sum(not record["verified_rgba16"] for record in records),
        "format_markers": dict(sorted(markers.items())),
        "records": records,
    }


def _objects(rom: bytes, prop_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    definitions = _object_definitions_using_model(rom, PROP_ID)
    player_matches = [row for row in definitions if row["object_definition_id"] == PLAYER_OBJECT_DEFINITION_ID]
    if len(player_matches) != 1:
        raise ValueError("Prop 218 does not resolve uniquely to player object definition 0.")

    player_rom_start, player_header = _object_header(rom, PLAYER_OBJECT_DEFINITION_ID)
    _, _, player_models = _model_ids(player_header)
    player_children = _child_ids(player_header)
    if player_children != [GIRLGUN_OBJECT_DEFINITION_ID]:
        raise ValueError("playerGirl no longer has exactly the expected GirlGun child.")

    gun_rom_start, gun_header = _object_header(rom, GIRLGUN_OBJECT_DEFINITION_ID)
    _, _, gun_models = _model_ids(gun_header)
    power_rom_start, power_header = _object_header(rom, 3)
    _, _, power_models = _model_ids(power_header)
    power_children = _child_ids(power_header)
    if power_models != [219, 795] or power_children != [GIRLGUN_OBJECT_DEFINITION_ID]:
        raise ValueError("playerGirlPower no longer selects PowerGirl and the shared GirlGun child.")
    slots = [
        {
            "slot": slot,
            "prop_id": prop_id,
            "name": prop_index[prop_id]["name"],
        }
        for slot, prop_id in enumerate(gun_models)
    ]
    return {
        "player": {
            "object_definition_id": PLAYER_OBJECT_DEFINITION_ID,
            "technical_name": _name(player_header, 4),
            "header_rom_start": player_rom_start,
            "object_ids": player_matches[0]["object_ids"],
            "model_prop_ids": player_models,
            "child_object_definition_ids": player_children,
        },
        "girlgun": {
            "object_definition_id": GIRLGUN_OBJECT_DEFINITION_ID,
            "technical_name": _name(gun_header, 4),
            "header_rom_start": gun_rom_start,
            "behaviour_id": _u16(gun_header, 0x1C),
            "model_slots": slots,
            "attachment_matrix_id": None,
            "attachment_matrix_status": "UNKNOWN in Phase 1; matrix 6 is only a structural lead from reference record 0",
        },
        "power_variant": {
            "object_definition_id": 3,
            "technical_name": _name(power_header, 4),
            "header_rom_start": power_rom_start,
            "model_prop_ids": power_models,
            "child_object_definition_ids": power_children,
        },
    }


def analyze(
    rom_path: Path,
    prop_path: Path,
    texture_manifest_path: Path,
    prop_index_path: Path,
) -> dict[str, Any]:
    """Return deterministic, path-neutral Vela Phase-1 evidence."""
    identity = validate_rom_identity(rom_path)
    rom = identity.path.read_bytes()
    data = prop_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_SIZE or digest != EXPECTED_SHA256 or not data.startswith(b"Girl\0"):
        raise ValueError("Candidate input is not the pinned US Prop 218 Girl binary.")

    offsets = parse_offset_table(
        rom[PROP_TABLE_OFFSET : PROP_TABLE_OFFSET + PROP_TABLE_ENTRIES * 4]
    )
    relative_start, relative_end = offsets[PROP_ID : PROP_ID + 2]
    rom_start = PROP_DATA_BASE + relative_start
    rom_end = PROP_DATA_BASE + relative_end
    declared_size, rom_decoded = decode_prop_block(rom[rom_start:rom_end])
    if rom_decoded != data:
        raise ValueError("Canonical Girl binary differs from direct ROM decompression.")

    index_rows = json.loads(prop_index_path.read_text(encoding="utf-8"))
    prop_index = {row["id"]: row for row in index_rows}
    if prop_index[PROP_ID]["name"] != PROP_NAME:
        raise ValueError("Reference index no longer names Prop 218 Girl.")

    sections = _sections(data)
    geometry = _geometry(data)
    transforms = _transforms_and_references(data, sections)
    textures = _textures(data, rom, texture_manifest_path)
    objects = _objects(rom, prop_index)
    variants = [
        {
            "prop_id": prop_id,
            "name": prop_index[prop_id]["name"],
            "relationship": relationship,
        }
        for prop_id, relationship in (
            (219, "immediately adjacent PowerGirl upgraded variant"),
            (236, "MultiGirl variant"),
            (237, "GirlLod variant"),
            (242, "MultiPowerGirl variant"),
            (243, "PowerGirlLod variant"),
        )
    ]

    return {
        "schema_version": 1,
        "scope": "Vela Phase 1: US Prop 218 static identity and structural map only",
        "identity": {
            "classification": "VERIFIED",
            "prop_id": PROP_ID,
            "name": PROP_NAME,
            "internal_name": _name(data),
            "player_object_technical_name": objects["player"]["technical_name"],
            "size_bytes": len(data),
            "sha256": digest,
            "canonical_output": "data/generated/props-us-verified/bins/0218_Girl.bin",
            "rom_identity": {"size_bytes": identity.size_bytes, "sha1": identity.sha1},
            "rom_container": {
                "relative_start": relative_start,
                "relative_end": relative_end,
                "rom_start": rom_start,
                "rom_end": rom_end,
                "compressed_size": rom_end - rom_start,
                "declared_decompressed_size": declared_size,
                "canonical_matches_rom_decompression": True,
            },
        },
        "variants": variants,
        "sections": sections,
        "geometry": geometry,
        "textures": textures,
        "transforms_and_references": transforms,
        "objects_and_attachments": objects,
        "confidence": {
            "exact_header_counts_offsets_and_record_strides": "VERIFIED from bytes and exact section arithmetic",
            "Boy_style_field_semantics_for_Girl": "LIKELY; structurally consistent and consumed by the same compact-model parser, but no Vela runtime capture was used",
            "group_0x400_runtime_skip": "LIKELY for Vela; generic JFG model code is established, but this phase has no Vela render capture",
            "transform_record_layout": "LIKELY for Vela; 28 records form a complete valid hierarchy matching the established runtime record shape",
            "GirlGun_attachment_socket": "UNKNOWN; reference record 0 selects matrix 6, but Phase 1 did not trace the GirlGun runtime placement",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--prop", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.rom, args.prop, args.textures, args.index)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
