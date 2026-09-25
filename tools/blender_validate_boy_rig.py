#!/usr/bin/env python3
"""Headless Blender validation for the limited Prop-220 rig glTF artifact.

Run with Blender's Python, after a ``--`` separator.  The script imports the
artifact through Blender's real glTF importer and compares evaluated mesh
positions with the pinned JFG runtime decoder.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

import bpy


ANIMATION_NAMES = {0: "boy_anim_00_id_1026", 43: "boy_anim_43_id_1069"}
SAMPLE_TIMES = {0: (0.0, 1.0, 7.5, 8.0, 15.0), 43: (0.0, 1.0, 37.0, 37.5, 75.0)}


def _arguments() -> argparse.Namespace:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--gltf", required=True, type=Path)
    parser.add_argument("--render-map", required=True, type=Path)
    parser.add_argument("--boy", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--output-blend", type=Path)
    return parser.parse_args(args)


def _action(name: str):
    exact = bpy.data.actions.get(name)
    if exact is not None:
        return exact
    matches = [item for item in bpy.data.actions if item.name == name or item.name.startswith(name + ".")]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Blender action for {name!r}; found {[item.name for item in matches]}")
    return matches[0]


def _source_attribute(mesh):
    for name in ("_JFG_SOURCE_INDEX", "JFG_SOURCE_INDEX"):
        attribute = mesh.attributes.get(name)
        if attribute is not None:
            return attribute
    return None


def _attribute_values(attribute) -> list[int]:
    result = []
    for item in attribute.data:
        if hasattr(item, "value"):
            result.append(int(round(item.value)))
        elif hasattr(item, "vector"):
            result.append(int(round(item.vector[0])))
        else:
            raise RuntimeError("Unsupported Blender custom-attribute storage for source indices.")
    return result


def _to_jfg(world_position) -> tuple[float, float, float]:
    # Blender's glTF importer maps glTF +Y-up coordinates to Blender +Z-up as
    # (x, y, z)_gltf -> (x, -z, y)_blender.  This is the exact inverse.
    return float(world_position.x), float(world_position.z), float(-world_position.y)


def _evaluated_positions(mesh_objects, render_map: list[int]) -> tuple[dict[int, tuple[float, float, float]], dict[str, object]]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    by_source: defaultdict[int, list[tuple[float, float, float]]] = defaultdict(list)
    object_records = []
    render_count = 0
    for mesh_object in mesh_objects:
        evaluated = mesh_object.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            attribute = _source_attribute(mesh)
            if attribute is None:
                if len(mesh_objects) == 1 and len(mesh.vertices) == len(render_map):
                    source_indices = render_map
                    mapping = "deterministic primitive-order render map fallback"
                else:
                    raise RuntimeError(
                        f"Mesh {mesh_object.name!r} has no JFG source attribute; its {len(mesh.vertices)} vertices "
                        "cannot safely be mapped within a multi-object import."
                    )
            else:
                source_indices = _attribute_values(attribute)
                mapping = f"Blender mesh attribute {attribute.name}"
            if len(source_indices) != len(mesh.vertices):
                raise RuntimeError("Source-index attribute length differs from evaluated vertex count.")
            render_count += len(mesh.vertices)
            object_records.append({"object": mesh_object.name, "vertices": len(mesh.vertices), "mapping": mapping,
                                   "attributes": list(mesh.attributes.keys())})
            for vertex, source in zip(mesh.vertices, source_indices):
                by_source[source].append(_to_jfg(evaluated.matrix_world @ vertex.co))
        finally:
            evaluated.to_mesh_clear()
    duplicate_errors = []
    positions = {}
    for source, values in by_source.items():
        positions[source] = values[0]
        duplicate_errors.extend(math.dist(values[0], value) for value in values[1:])
    return positions, {
        "objects": object_records,
        "evaluated_render_vertex_count": render_count,
        "mapped_source_vertex_count": len(positions),
        "maximum_duplicate_position_error": max(duplicate_errors, default=0.0),
    }


def _reference_positions(boy_data: bytes, rom: bytes, model, assignments: dict[int, int], index: int, time_value: float,
                         catalog_mod, decode_anim0_time, locate_boy_animation0, build_matrices, transform):
    if index == 0:
        located = locate_boy_animation0(rom)
        decoded = decode_anim0_time(located["blob"], time_value)
        channel_map = located["channel_map"]
    else:
        catalogue = catalog_mod.catalog_boy_animations(rom)
        record = catalogue["animations"][index]
        tables = catalog_mod._tables(rom)
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        decoded = catalog_mod.decode_animation_time(tables["asset43"][start:end], time_value)
        channel_map = record["channel_map"]
    matrices = build_matrices(boy_data, decoded, rom, channel_map)
    worlds = {item["matrix_id"]: item["world_model_matrix"] for item in matrices}
    return {source: transform(model.vertices[source], worlds[matrix_id])[0] for source, matrix_id in assignments.items()}


def _comparison(actual: dict[int, tuple[float, float, float]], expected: dict[int, tuple[float, float, float]]) -> dict[str, object]:
    if set(actual) != set(expected):
        raise RuntimeError(f"Source-vertex sets differ: Blender={len(actual)}, JFG={len(expected)}")
    errors = [math.dist(actual[index], expected[index]) for index in sorted(expected)]
    return {
        "source_vertex_count": len(errors),
        "maximum_position_error": max(errors),
        "mean_position_error": sum(errors) / len(errors),
        "within_1e-4": sum(value <= 1e-4 for value in errors),
        "within_1e-3": sum(value <= 1e-3 for value in errors),
    }


def _action_range(action) -> tuple[float, float]:
    return float(action.frame_range[0]), float(action.frame_range[1])


def _action_cycle_modifiers(action) -> tuple[int, bool]:
    """Return CYCLES modifier count across legacy or Blender-5 layered actions."""
    curves = []
    if hasattr(action, "fcurves"):
        curves.extend(action.fcurves)
    else:
        try:
            for layer in action.layers:
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                        for bag in strip.channelbags:
                            curves.extend(bag.fcurves)
                    else:
                        for slot in action.slots:
                            bag = strip.channelbag(slot, ensure=False)
                            if bag is not None:
                                curves.extend(bag.fcurves)
        except (AttributeError, TypeError):
            return 0, False
    return sum(modifier.type == "CYCLES" for curve in curves for modifier in curve.modifiers), True


def _set_action(armature, action) -> None:
    animation_data = armature.animation_data_create()
    for track in animation_data.nla_tracks:
        track.mute = True
    animation_data.action = action


def _set_time(scene, frame_value: float) -> None:
    integer = math.floor(frame_value)
    scene.frame_set(integer, subframe=frame_value - integer)


def main() -> int:
    args = _arguments()
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "schema_version": 1,
        "status": "FAILED",
        "blender_version": bpy.app.version_string,
        "inputs": {key: str(getattr(args, key).resolve()) for key in ("gltf", "render_map", "boy", "rom")},
    }
    try:
        project_root = args.project_root.resolve(strict=True)
        sys.path.insert(0, str(project_root / "src"))
        from jfg_re.boy_anim0_frame0 import _transform, build_matrices, locate_boy_animation0
        from jfg_re.boy_anim0_temporal import _assignments, decode_time as decode_anim0_time
        import jfg_re.boy_animation_catalog as catalog_mod
        from jfg_re.boy_export import BONE_COUNT, BONE_START, BOY_SHA256, parse_boy
        from jfg_re.props import validate_rom_identity

        validate_rom_identity(args.rom.resolve(strict=True))
        boy_data = args.boy.resolve(strict=True).read_bytes()
        if hashlib.sha256(boy_data).hexdigest() != BOY_SHA256:
            raise RuntimeError("Boy Prop-220 input identity differs.")
        rom = args.rom.read_bytes()
        model = parse_boy(boy_data)
        assignments = _assignments(model)
        render_map_payload = json.loads(args.render_map.read_text(encoding="utf-8"))
        render_map = render_map_payload["render_vertex_to_source_vertex"]

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        result = bpy.ops.import_scene.gltf(filepath=str(args.gltf.resolve(strict=True)))
        if "FINISHED" not in result:
            raise RuntimeError(f"Blender glTF importer returned {result!r}.")

        mesh_objects = [item for item in bpy.context.scene.objects if item.type == "MESH"]
        armatures = [item for item in bpy.context.scene.objects if item.type == "ARMATURE"]
        if not mesh_objects or len(armatures) != 1:
            raise RuntimeError(f"Expected one or more meshes and one armature; found {len(mesh_objects)} and {len(armatures)}.")
        armature = armatures[0]
        mesh_inventory = [{"name": item.name, "vertices": len(item.data.vertices),
                           "parent": item.parent.name if item.parent else None,
                           "modifiers": [modifier.type for modifier in item.modifiers]}
                          for item in mesh_objects]
        render_meshes = [item for item in mesh_objects if len(item.data.vertices) == len(render_map)]
        if len(render_meshes) == 1:
            # Blender may create an additional zero-vertex helper mesh for the
            # glTF node that owns the skin.  It is not part of evaluated geometry.
            mesh_objects = render_meshes
        bone_names = [bone.name for bone in armature.data.bones]
        hierarchy = {bone.name: (bone.parent.name if bone.parent else None) for bone in armature.data.bones}
        expected_names = [f"jfg_node_{index:02d}" for index in range(21)]
        if sorted(bone_names) != expected_names:
            raise RuntimeError(f"Imported joint names differ: {bone_names}")
        expected_hierarchy = {}
        for record_index in range(BONE_COUNT):
            offset = BONE_START + record_index * 16
            parent, matrix_id = boy_data[offset], boy_data[offset + 1]
            expected_hierarchy[f"jfg_node_{matrix_id:02d}"] = None if parent == 0xFF else f"jfg_node_{parent:02d}"
        if hierarchy != expected_hierarchy:
            raise RuntimeError("Imported joint parent hierarchy differs from Prop 220.")

        source_gltf = json.loads(args.gltf.read_text(encoding="utf-8"))
        expected_materials = {item["name"] for item in source_gltf.get("materials", [])}
        boy_materials = {slot.material.name for item in mesh_objects for slot in item.material_slots if slot.material}
        if boy_materials != expected_materials:
            raise RuntimeError(f"Imported Boy materials differ: missing={expected_materials-boy_materials}, extra={boy_materials-expected_materials}")

        actions = {index: _action(name) for index, name in ANIMATION_NAMES.items()}
        action_ranges = {index: _action_range(action) for index, action in actions.items()}
        time_scales = {
            0: (action_ranges[0][1] - action_ranges[0][0]) / 16.0,
            43: (action_ranges[43][1] - action_ranges[43][0]) / 75.0,
        }
        if not math.isclose(time_scales[0], time_scales[43], rel_tol=0.0, abs_tol=1e-6):
            raise RuntimeError(f"Imported action time scales differ: {time_scales}")

        image_records = []
        for image in bpy.data.images:
            if not image.filepath:
                continue
            resolved = Path(bpy.path.abspath(image.filepath)).resolve()
            image_records.append({"name": image.name, "path": str(resolved), "exists": resolved.is_file(), "size": list(image.size)})
        if any(not item["exists"] for item in image_records):
            raise RuntimeError("At least one imported material image is missing.")

        samples = []
        cached_actual: dict[tuple[int, float], dict[int, tuple[float, float, float]]] = {}
        mapping_info = None
        scene = bpy.context.scene
        for index in (0, 43):
            _set_action(armature, actions[index])
            start = action_ranges[index][0]
            for time_value in SAMPLE_TIMES[index]:
                blender_frame = start + time_value * time_scales[index]
                _set_time(scene, blender_frame)
                actual, current_mapping = _evaluated_positions(mesh_objects, render_map)
                mapping_info = current_mapping
                expected = _reference_positions(
                    boy_data, rom, model, assignments, index, time_value, catalog_mod,
                    decode_anim0_time, locate_boy_animation0, build_matrices, _transform,
                )
                comparison = _comparison(actual, expected)
                cached_actual[index, time_value] = actual
                samples.append({
                    "animation_index": index,
                    "jfg_sample_time": time_value,
                    "blender_frame": blender_frame,
                    **comparison,
                })

        _set_action(armature, actions[0])
        _set_time(scene, action_ranges[0][0] + 16.0 * time_scales[0])
        anim0_closure, _ = _evaluated_positions(mesh_objects, render_map)
        closure = _comparison(anim0_closure, cached_actual[0, 0.0])
        _set_action(armature, actions[43])
        endpoint = cached_actual[43, 75.0]
        endpoint_vs_start = _comparison(endpoint, cached_actual[43, 0.0])
        cycle_modifiers, cycle_modifiers_inspected = _action_cycle_modifiers(actions[43])

        report.update({
            "status": "PASS",
            "import": {
                "mesh_objects": [item.name for item in mesh_objects],
                "scene_mesh_inventory": mesh_inventory,
                "armature_object": armature.name,
                "joint_count": len(bone_names),
                "joint_names": sorted(bone_names),
                "joint_hierarchy": hierarchy,
                "joint_hierarchy_matches_prop_220": hierarchy == expected_hierarchy,
                "actions": [action.name for action in bpy.data.actions],
                "action_ranges_blender_frames": {str(index): list(action_ranges[index]) for index in action_ranges},
                "blender_frames_per_jfg_sample_unit": time_scales[0],
                "boy_materials": sorted(boy_materials),
                "boy_material_count": len(boy_materials),
                "all_blender_material_datablocks": [material.name for material in bpy.data.materials],
                "images": image_records,
                "image_count": len(image_records),
            },
            "render_mapping": mapping_info,
            "evaluated_samples": samples,
            "summary": {
                "sample_count": len(samples),
                "comparisons": sum(item["source_vertex_count"] for item in samples),
                "maximum_position_error": max(item["maximum_position_error"] for item in samples),
                "mean_position_error": sum(item["mean_position_error"] * item["source_vertex_count"] for item in samples)
                    / sum(item["source_vertex_count"] for item in samples),
                "within_1e-4": sum(item["within_1e-4"] for item in samples),
                "within_1e-3": sum(item["within_1e-3"] for item in samples),
            },
            "edge_cases": {
                "animation_0_time_0_vs_baked_closure_16": closure,
                "animation_43_endpoint_75_vs_time_0": endpoint_vs_start,
                "animation_43_cycle_modifier_count": cycle_modifiers,
                "animation_43_cycle_modifiers_inspected": cycle_modifiers_inspected,
                "animation_43_endpoint_is_not_loop": endpoint_vs_start["maximum_position_error"] > 1e-3 and cycle_modifiers == 0,
            },
            "identity": {"rom_verified": True, "boy_sha256": BOY_SHA256, "powerboy_processed": False},
        })
        if report["summary"]["within_1e-4"] != report["summary"]["comparisons"]:
            raise RuntimeError("Blender evaluated positions exceed 1e-4 tolerance.")
        if closure["maximum_position_error"] > 1e-4:
            raise RuntimeError("Animation 0 baked closure differs from time 0.")
        if not report["edge_cases"]["animation_43_endpoint_is_not_loop"]:
            raise RuntimeError("Animation 43 endpoint did not validate as non-looping.")
        if args.output_blend:
            args.output_blend.parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
            report["blend_file"] = str(args.output_blend.resolve())
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        args.output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    args.output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
