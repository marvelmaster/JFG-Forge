"""Pinned runtime-transform analysis for US Prop 220 ``Boy``.

This module records only facts available without decoding an animation.  It
does not construct a pose matrix or emit transformed geometry: JFG obtains
rotation, optional scale, and root-translation inputs from animation data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_export import BONE_COUNT, BONE_START, BoyExportError, _matrix_id, parse_boy


REFERENCE_RECORD_START = 0x4090
REFERENCE_RECORD_COUNT = 2
REFERENCE_RECORD_SIZE = 4


def _bbox(model: Any) -> dict[str, list[int]]:
    return {
        "minimum": [min((v.x, v.y, v.z)[axis] for v in model.vertices) for axis in range(3)],
        "maximum": [max((v.x, v.y, v.z)[axis] for v in model.vertices) for axis in range(3)],
    }


def _path_to_root(records: list[dict[str, Any]], matrix_id: int) -> list[int]:
    by_id = {record["matrix_id"]: record for record in records}
    path: list[int] = []
    seen: set[int] = set()
    current = matrix_id
    while current != 0xFF:
        if current in seen or current not in by_id:
            raise BoyExportError("Boy transform hierarchy is cyclic or references a missing matrix.")
        seen.add(current)
        path.append(current)
        current = by_id[current]["parent_id"]
    return path


def build_transform_analysis(boy_data: bytes) -> dict[str, Any]:
    """Build deterministic evidence metadata without inventing a default pose."""
    model = parse_boy(boy_data)
    records: list[dict[str, Any]] = []
    for index in range(BONE_COUNT):
        offset = BONE_START + index * 16
        parent_id, matrix_id, channel_a, channel_b = boy_data[offset : offset + 4]
        translation = list(struct.unpack_from(">fff", boy_data, offset + 4))
        records.append(
            {
                "record_index": index,
                "file_offset_hex": f"0x{offset:04X}",
                "parent_id": parent_id,
                "matrix_id": matrix_id,
                "stored_channel_bytes": [channel_a, channel_b],
                "local_translation_xyz": translation,
                "local_matrix": None,
                "composed_matrix": None,
                "matrix_unavailable_reason": (
                    "Rotation, optional scale, and root translation are decoded from the selected animation; "
                    "the transform record alone is insufficient."
                ),
            }
        )

    if sorted(record["matrix_id"] for record in records) != list(range(BONE_COUNT)):
        raise BoyExportError("Pinned Boy matrix IDs are no longer exactly 0..20.")
    if records[0]["parent_id"] != 0xFF:
        raise BoyExportError("Pinned Boy root transform no longer uses parent 0xFF.")
    for record in records[1:]:
        if record["parent_id"] >= record["matrix_id"]:
            raise BoyExportError("Pinned Boy hierarchy is no longer parent-before-child ordered.")

    unique_vertices: dict[int, set[int]] = defaultdict(set)
    corner_references: Counter[int] = Counter()
    active_group_ids: dict[int, set[int]] = defaultdict(set)
    vertex_to_matrix: dict[int, int] = {}
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            for local_index in triangle.local_indices:
                matrix_id = _matrix_id(group, local_index)
                if matrix_id is None:
                    raise BoyExportError("Active Boy group unexpectedly has no matrix ID.")
                global_index = group.vertex_start + local_index
                previous = vertex_to_matrix.setdefault(global_index, matrix_id)
                if previous != matrix_id:
                    raise BoyExportError("One active Boy vertex is assigned to multiple matrices.")
                unique_vertices[matrix_id].add(global_index)
                corner_references[matrix_id] += 1
                active_group_ids[matrix_id].add(group.index)

    for record in records:
        matrix_id = record["matrix_id"]
        record["parent_chain_matrix_to_root"] = _path_to_root(records, matrix_id)
        record["active_unique_vertex_count"] = len(unique_vertices[matrix_id])
        record["active_triangle_corner_reference_count"] = corner_references[matrix_id]
        record["active_group_ids"] = sorted(active_group_ids[matrix_id])

    references = []
    for index in range(REFERENCE_RECORD_COUNT):
        offset = REFERENCE_RECORD_START + index * REFERENCE_RECORD_SIZE
        vertex_index, matrix_id = struct.unpack_from(">HH", boy_data, offset)
        references.append(
            {
                "record_index": index,
                "file_offset_hex": f"0x{offset:04X}",
                "vertex_index": vertex_index,
                "matrix_id": matrix_id,
                "source_xyz": list(struct.unpack_from(">hhh", boy_data, 0x26C8 + vertex_index * 10)),
                "runtime_result": "three f32 values stored in the model instance reference-point array",
            }
        )

    return {
        "schema_version": 1,
        "scope": "US Prop 220 Boy runtime transform analysis; no animation decoded",
        "input": {
            "prop_id": 220,
            "name": "Boy",
            "sha256": hashlib.sha256(boy_data).hexdigest(),
        },
        "status": {
            "record_translation_semantics": "VERIFIED",
            "hierarchy_and_matrix_order": "VERIFIED",
            "geometry_matrix_assignment": "VERIFIED",
            "static_default_pose_without_animation": "UNKNOWN / NOT REPRODUCIBLE FROM PROP ALONE",
            "transformed_obj_emitted": False,
        },
        "runtime_formula": {
            "matrix_layout": "row-vector affine; translation at byte offsets 0x30/0x34/0x38",
            "point": [
                "x' = x*m00 + y*m10 + z*m20 + m30",
                "y' = x*m01 + y*m11 + z*m21 + m31",
                "z' = x*m02 + y*m12 + z*m22 + m32",
            ],
            "hierarchy": "world_or_object_matrix[child] = local_matrix[child] * world_or_object_matrix[parent]",
            "root_parent": "animation root translation * caller-supplied object/root matrix",
            "output_conversion": "modMakeLimbModel converts each f32 result to s16 with truncation toward zero",
        },
        "raw_xyz_bbox": _bbox(model),
        "transformed_bbox": None,
        "transformed_bbox_unavailable_reason": (
            "The selected animation supplies rotations, optional scales, and root translation; decoding it was "
            "explicitly outside this step."
        ),
        "counts": {
            "transform_records": len(records),
            "active_geometry_unique_vertices_with_matrix": len(vertex_to_matrix),
            "stored_vertices": len(model.vertices),
            "active_triangle_corner_references": sum(corner_references.values()),
            "reference_point_records": len(references),
        },
        "transform_records": records,
        "header_0x30_reference_records": references,
    }


def build_artifacts(boy_data: bytes) -> dict[str, bytes]:
    report = build_transform_analysis(boy_data)
    payload = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    return {"boy-transform-runtime-analysis.json": payload}


def write_artifacts(boy_path: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    artifacts = build_artifacts(boy_path.read_bytes())
    output_dir.mkdir(parents=False)
    for name, payload in artifacts.items():
        (output_dir / name).write_bytes(payload)
    regenerated = build_artifacts(boy_path.read_bytes())
    if regenerated != artifacts:
        raise BoyExportError("Transform-analysis output is not deterministic.")
    result = json.loads(artifacts["boy-transform-runtime-analysis.json"])
    result["validation"] = {"deterministic_regeneration_match": True}
    return result
