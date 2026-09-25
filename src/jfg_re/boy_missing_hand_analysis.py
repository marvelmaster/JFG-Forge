"""Pinned diagnosis of the absent +X-side hand in Boy anim0/frame0."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_anim0_frame0 import _bbox, _transform, build_matrices, decode_frame0, locate_boy_animation0
from jfg_re.boy_export import BOY_SHA256, BoyExportError, _cross, parse_boy
from jfg_re.props import validate_rom_identity


JUNOHAND_SHA256 = "954a408709bb6ff6e2bfc8f3eed1adc5d55826f63adba8d9f65ee3fc7e9583f4"
JUNOHAND_SIZE = 1424


def _following(model: Any, index: int) -> Any:
    return model.groups[index + 1] if index + 1 < len(model.groups) else model.sentinel


def _candidate_matrix_ids(group: Any, count: int) -> list[int] | None:
    """Apply the normal split rule only when all fields are internally valid."""
    first, second = group.matrix_splits
    if not (0 <= first <= second <= count):
        return None
    result = [group.matrix_ids[0] if i < first else group.matrix_ids[1] if i < second else group.matrix_ids[2]
              for i in range(count)]
    return None if any(matrix_id >= 21 for matrix_id in result) else result


def _group_record(model: Any, group: Any, matrices: dict[int, list[list[float]]]) -> dict[str, Any]:
    following = _following(model, group.index)
    vertices = list(model.vertices[group.vertex_start:following.vertex_start])
    triangles = list(model.triangles[group.triangle_start:following.triangle_start])
    nondegenerate = 0
    for triangle in triangles:
        points = tuple((vertices[index].x, vertices[index].y, vertices[index].z) for index in triangle.local_indices)
        nondegenerate += _cross(points) != (0, 0, 0)
    candidate = _candidate_matrix_ids(group, len(vertices))
    transformed = None
    if candidate is not None:
        transformed = [_transform(vertex, matrices[matrix_id])[1] for vertex, matrix_id in zip(vertices, candidate)]
    texture_id = None
    if group.texture_index != 0xFF:
        texture_id = struct.unpack_from(">H", model.texture_records[group.texture_index], 6)[0]
    points = [[vertex.x, vertex.y, vertex.z] for vertex in vertices]
    return {
        "group_index": group.index,
        "render_flags_hex": f"0x{group.render_flags:08X}",
        "vertex_range": [group.vertex_start, following.vertex_start],
        "triangle_range": [group.triangle_start, following.triangle_start],
        "vertex_count": len(vertices),
        "triangle_record_count": len(triangles),
        "nondegenerate_face_count": nondegenerate,
        "matrix_ids_raw": list(group.matrix_ids),
        "matrix_splits_raw": list(group.matrix_splits),
        "normal_split_rule_internally_valid": candidate is not None,
        "candidate_matrix_assignment": candidate,
        "texture_record_index": None if group.texture_index == 0xFF else group.texture_index,
        "texture_id": texture_id,
        "texture_id_hex": None if texture_id is None else f"0x{texture_id:04X}",
        "local_bbox": _bbox(points),
        "anim0_frame0_bbox": None if transformed is None else _bbox(transformed),
    }


def _active_matrix_inventory(model: Any) -> dict[int, dict[str, Any]]:
    inventory: dict[int, dict[str, Any]] = defaultdict(lambda: {"vertices": set(), "triangle_corners": 0, "groups": set()})
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = _following(model, group.index)
        first, second = group.matrix_splits
        select = lambda local: group.matrix_ids[0] if local < first else group.matrix_ids[1] if local < second else group.matrix_ids[2]
        for absolute in range(group.vertex_start, following.vertex_start):
            matrix_id = select(absolute - group.vertex_start)
            inventory[matrix_id]["vertices"].add(absolute)
            inventory[matrix_id]["groups"].add(group.index)
        for triangle in model.triangles[group.triangle_start:following.triangle_start]:
            for local in triangle.local_indices:
                inventory[select(local)]["triangle_corners"] += 1
    return {matrix_id: {"unique_vertices": len(record["vertices"]), "triangle_corners": record["triangle_corners"],
                        "groups": sorted(record["groups"])} for matrix_id, record in sorted(inventory.items())}


def _parse_junohand(data: bytes) -> dict[str, Any]:
    if len(data) != JUNOHAND_SIZE or hashlib.sha256(data).hexdigest() != JUNOHAND_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 309 JunoHand binary.")
    if not data.startswith(b"JunoHand\0"):
        raise BoyExportError("Pinned Prop 309 name differs.")
    vertex_count, triangle_count, group_count = struct.unpack_from(">hhh", data, 0x12)
    vertex_start = struct.unpack_from(">I", data, 0x1C)[0]
    group_start = struct.unpack_from(">I", data, 0x24)[0]
    vertices = [struct.unpack_from(">hhh", data, vertex_start + index * 10) for index in range(vertex_count)]
    groups = []
    for index in range(group_count + 1):
        offset = group_start + index * 16
        groups.append((struct.unpack_from(">H", data, offset + 6)[0], struct.unpack_from(">H", data, offset + 8)[0]))
    active_vertices, active_faces = groups[3]
    return {
        "prop_id": 309, "internal_name": "JunoHand", "size_bytes": len(data), "sha256": JUNOHAND_SHA256,
        "texture_count": data[0x10], "vertex_count": vertex_count, "triangle_count": triangle_count,
        "group_count": group_count, "active_prefix_vertex_count": active_vertices,
        "active_prefix_face_count": active_faces,
        "active_prefix_local_bbox": _bbox([list(point) for point in vertices[:active_vertices]]),
        "comparison_status": "HISTORICAL STRUCTURAL CANDIDATE; subsequent object-table tracing disproved Prop 309 for the 0xF7/0x59 path",
    }


def build_report(boy_data: bytes, rom: bytes, junohand_data: bytes) -> dict[str, Any]:
    model = parse_boy(boy_data)
    located = locate_boy_animation0(rom)
    frame = decode_frame0(located["blob"])
    matrix_records = build_matrices(boy_data, frame, rom, located["channel_map"])
    matrices = {record["matrix_id"]: record["world_model_matrix"] for record in matrix_records}
    skipped = [_group_record(model, group, matrices) for group in model.groups if group.runtime_skipped]
    active_inventory = _active_matrix_inventory(model)
    reference_points = []
    for vertex_index, matrix_id in ((619, 6), (624, 10)):
        vertex = model.vertices[vertex_index]
        transformed_f32, transformed_s16 = _transform(vertex, matrices[matrix_id])
        reference_points.append({"vertex_index": vertex_index, "matrix_id": matrix_id,
                                 "stored_xyz": [vertex.x, vertex.y, vertex.z],
                                 "anim0_frame0_xyz_f32": transformed_f32,
                                 "anim0_frame0_xyz_s16": transformed_s16})
    valid = degenerate = runtime = 0
    skipped_valid = []
    for group in model.groups:
        following = _following(model, group.index)
        vertices = model.vertices[group.vertex_start:following.vertex_start]
        for triangle in model.triangles[group.triangle_start:following.triangle_start]:
            points = tuple((vertices[i].x, vertices[i].y, vertices[i].z) for i in triangle.local_indices)
            is_valid = _cross(points) != (0, 0, 0)
            valid += is_valid
            degenerate += not is_valid
            runtime += is_valid and not group.runtime_skipped
            if is_valid and group.runtime_skipped:
                skipped_valid.append(triangle.index)
    return {
        "schema_version": 1,
        "scope": "US Prop 220 Boy; Animation 0 integer Frame 0; missing-hand diagnosis only",
        "input": {"boy_sha256": BOY_SHA256, "powerboy_processed": False,
                  "junohand_used_only_as_separate_asset_structural_evidence": True},
        "arm_comparison": {
            "missing_geometry_side": "model-space +X arm", "missing_side_matrix_chain": [3, 4, 5, 6],
            "visible_hand_side": "model-space -X arm", "visible_side_matrix_chain": [3, 7, 8, 9],
            "visible_hand_matrix_9": active_inventory[9],
            "opposite_endpoint_matrix_6": active_inventory.get(6, {"unique_vertices": 0, "triangle_corners": 0, "groups": []}),
            "matrix_5_active_geometry": active_inventory[5], "matrix_6_reference_point": reference_points[0],
            "conclusion": "No structurally corresponding hand mesh is present in Boy's runtime-visible groups on matrix 6.",
        },
        "runtime_skipped_groups": skipped,
        "triangle_accounting": {
            "prop_triangle_records": len(model.triangles), "geometrically_valid": valid,
            "geometrically_degenerate": degenerate, "valid_in_makeModelGfx_path": runtime,
            "exported_by_anim0_frame0_exporter": 502, "valid_but_skipped_triangle_indices": skipped_valid,
            "explanation": "Three valid triangles belong to skipped groups 0 and 1; all 15 degenerate records belong to skipped groups 64-78.",
        },
        "reference_points": reference_points,
        "separate_asset_evidence": _parse_junohand(junohand_data),
        "jfg_code_evidence": {
            "makeModelGfx": {"address": "0x8003DDD8", "flag_test": "0x8003DF34 andi t9,v0,0x400; 0x8003DF44 bne -> next group"},
            "modMakeLimbModel": {"address": "0x8003E638", "flag_test": "0x8003E72C andi t9,t8,0x400; 0x8003E738 bne -> next group",
                                  "effect": "The known severed-limb reconstruction path also excludes these groups."},
            "controlGetGunBarrelPos": {"address": "0x8003B418",
                "dataflow": "0x8003B454..0x8003B4A4 follows object+0x6c -> model instance -> +0x68 and returns the first transformed XYZ triple.",
                "boy_binding": "modGenAnimMatrices fills that first triple from Boy reference record (vertex 619, matrix 6).",
                "status": "VERIFIED gun-barrel/reference-point role"},
            "controlEmptyPlayersHand": {"address": "0x8003B820",
                "dataflow": "Reads player-control +0x5cc as a separate object pointer, checks object halfword +0x48 == 0x59, then clears its model state and the pointer.",
                "status": "VERIFIED separate player-equipment object slot; hand meaning is LIKELY from the symbol and weapon-selection callers; exact Prop 309 lookup not yet proven"},
        },
        "classification": {
            "VERIFIED": ["Boy's runtime-visible -X arm has 42 hand vertices and 32 faces on matrix 9.",
                         "Boy's runtime-visible +X arm endpoint matrix 6 has no mesh vertices or faces.",
                         "Skipped groups contain only three nondegenerate triangles, not a 42-vertex/32-face counterpart.",
                         "Reference point 0 at vertex 619/matrix 6 feeds controlGetGunBarrelPos.",
                         "The prior exporter emits all 502 valid triangles admitted by the examined makeModelGfx path."],
            "DISPROVED_FOR_0xF7_0x59": ["Subsequent independent table tracing shows object 0xF7 / behaviour 0x59 loads Prop 343 Cluster, not Prop 309 JunoHand."],
            "UNKNOWN": ["Whether Prop 309 supplies a hand through a different object path.",
                        "A complete semantic name for group flag 0x400 beyond exclusion from both examined model-building paths."],
        },
        "diagnostic_obj_created": False,
        "diagnostic_obj_reason": "No excluded group contains the missing hand; automatically exporting a separate attachment was explicitly out of scope.",
        "smallest_next_test": "Trace the actual Prop-309 object IDs 0xC7, 0x1BE and 0x205 to determine whether one belongs to Juno's missing-hand path.",
    }


def analyze(boy_path: Path, rom_path: Path, junohand_path: Path, output_dir: Path) -> dict[str, Any]:
    boy_path, rom_path, junohand_path = boy_path.resolve(strict=True), rom_path.resolve(strict=True), junohand_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    args = (boy_path.read_bytes(), rom_path.read_bytes(), junohand_path.read_bytes())
    first = json.dumps(build_report(*args), indent=2, sort_keys=True) + "\n"
    second = json.dumps(build_report(*args), indent=2, sort_keys=True) + "\n"
    if first != second:
        raise BoyExportError("Missing-hand diagnosis is not deterministic.")
    output_dir.mkdir(parents=False)
    (output_dir / "boy-missing-hand-analysis.json").write_text(first, encoding="utf-8", newline="\n")
    return json.loads(first)
