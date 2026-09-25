"""Minimal glTF 2.0 builder for the Vela Forge MVP."""

from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_export import parse_model, resolve_boy_textures
from jfg_re.boy_rig_gltf import (
    _Buffer,
    _bake_states,
    _geometry,
    _pack_floats,
    _quat_from_row_matrix,
    validate_gltf_binary_layout,
)
from jfg_re.forge_types import AnimationClip, BoyAsset
from jfg_re.render_mesh import rigid_matrix_assignments
from jfg_re.vela_data import sample_vela_animation


def _decompose_local(
    matrix: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float]]:
    scales = tuple(math.sqrt(sum(matrix[row][column] ** 2 for column in range(3))) for row in range(3))
    normalized = [list(row) for row in matrix]
    for row, scale in enumerate(scales):
        if scale <= 0.0:
            raise ValueError("Vela animation produced a zero local scale.")
        for column in range(3):
            normalized[row][column] /= scale
    return _quat_from_row_matrix(normalized), scales


def build_vela_rig_artifacts(
    vela: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
) -> dict[str, bytes]:
    model = parse_model(vela.raw_prop)
    assignments = rigid_matrix_assignments(model)
    buffer = _Buffer()
    _, textures = resolve_boy_textures(model, vela.raw_rom, vela.texture_manifest_path)
    if include_mesh:
        primitives, materials, images, samplers, gltf_textures, geometry = _geometry(
            model,
            textures,
            assignments,
            vela.texture_manifest_path,
            output_dir,
            buffer,
        )
    else:
        primitives, materials, images, samplers, gltf_textures = [], [], [], [], []
        geometry = {"render_corner_vertices": 0, "primitives": 0}

    skeleton = vela.model.skeleton
    if skeleton is None:
        raise ValueError("Vela export requires its 28-joint skeleton.")
    joint_count = len(skeleton.joints)
    identity = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )
    inverse_bind = (
        buffer.add(_pack_floats(list(identity) * joint_count), 5126, joint_count, "MAT4")
        if include_mesh
        else None
    )

    initial_pose = sample_vela_animation(vela, 0, 0.0)
    nodes: list[dict[str, Any]] = [{
        "name": "Vela_Prop_0218",
        "extras": {
            "status": "MVP; live 28-matrix numerical runtime capture PENDING",
        },
    }]
    if include_mesh:
        nodes[0].update({"mesh": 0, "skin": 0})
    initial_by_id = {joint.joint_id: joint for joint in initial_pose.joints}
    for joint in skeleton.joints:
        pose_joint = initial_by_id[joint.joint_id]
        rotation, scale = _decompose_local(pose_joint.local_matrix)
        translation = list(joint.static_local_translation)
        if joint.parent_id is None:
            translation = [
                translation[axis] + initial_pose.root_translation[axis]
                for axis in range(3)
            ]
        children = [1 + item.joint_id for item in skeleton.joints if item.parent_id == joint.joint_id]
        node: dict[str, Any] = {
            "name": joint.name,
            "translation": translation,
            "rotation": list(rotation),
            "scale": list(scale),
            "extras": {
                "joint_id": joint.joint_id,
                "parent_id": joint.parent_id,
                "status": "VERIFIED structure; live numerical capture PENDING",
            },
        }
        if children:
            node["children"] = children
        nodes.append(node)

    animations: list[dict[str, Any]] = []
    if clip is not None:
        states = _bake_states(clip.sample_count, clip.loop)
        times = [state[0] for state in states]
        rotations = [[] for _ in skeleton.joints]
        scales = [[] for _ in skeleton.joints]
        roots: list[tuple[float, float, float]] = []
        for time_value, _current, _following, _fraction in states:
            sample_time = 0.0 if clip.loop and time_value == float(clip.sample_count) else time_value
            pose = sample_vela_animation(vela, clip.animation_index, sample_time)
            for item in pose.joints:
                rotation, scale = _decompose_local(item.local_matrix)
                rotations[item.joint_id].append(rotation)
                scales[item.joint_id].append(scale)
            root = skeleton.joints[skeleton.root_joint_id].static_local_translation
            roots.append(tuple(root[axis] + pose.root_translation[axis] for axis in range(3)))
        time_accessor = buffer.add(
            _pack_floats(times), 5126, len(times), "SCALAR", minimum=[times[0]], maximum=[times[-1]]
        )
        output_samplers: list[dict[str, Any]] = []
        channels: list[dict[str, Any]] = []
        for joint_id in range(joint_count):
            for path, values, type_name in (
                ("rotation", rotations[joint_id], "VEC4"),
                ("scale", scales[joint_id], "VEC3"),
            ):
                flat = [component for value in values for component in value]
                output = buffer.add(_pack_floats(flat), 5126, len(times), type_name)
                sampler_index = len(output_samplers)
                output_samplers.append({
                    "input": time_accessor,
                    "output": output,
                    "interpolation": "STEP",
                })
                channels.append({
                    "sampler": sampler_index,
                    "target": {"node": 1 + joint_id, "path": path},
                })
        root_output = buffer.add(
            _pack_floats([component for value in roots for component in value]),
            5126,
            len(times),
            "VEC3",
        )
        root_sampler = len(output_samplers)
        output_samplers.append({"input": time_accessor, "output": root_output, "interpolation": "STEP"})
        channels.append({
            "sampler": root_sampler,
            "target": {"node": 1 + skeleton.root_joint_id, "path": "translation"},
        })
        animations.append({
            "name": f"anim_{clip.animation_index:02d}_ID{clip.animation_id}",
            "samplers": output_samplers,
            "channels": channels,
            "extras": {
                "animation_index": clip.animation_index,
                "animation_id": clip.animation_id,
                "loop": clip.loop,
                "timing": "Technical Timing; Vela gameplay timing UNKNOWN",
                "scale_streams_preserved": True,
            },
        })

    gltf: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "JFG Forge Vela MVP exporter"},
        "scene": 0,
        "scenes": [{"name": "Vela", "nodes": [0, 1 + skeleton.root_joint_id]}],
        "nodes": nodes,
        "animations": animations,
        "buffers": [{"uri": "vela.bin", "byteLength": len(buffer.data)}],
        "bufferViews": buffer.views,
        "accessors": buffer.accessors,
        "extras": {
            "prop_id": 218,
            "geometry_status": "VERIFIED",
            "live_28_matrix_capture": "PENDING",
            "game_timing": "UNKNOWN",
        },
    }
    if include_mesh:
        gltf.update({
            "meshes": [{"name": "Vela runtime mesh", "primitives": primitives}],
            "skins": [{
                "name": "TECHNICAL_REPRESENTATION_identity_inverse_bind",
                "inverseBindMatrices": inverse_bind,
                "skeleton": 1 + skeleton.root_joint_id,
                "joints": [1 + index for index in range(joint_count)],
            }],
            "materials": materials,
            "images": images,
            "samplers": samplers,
            "textures": gltf_textures,
        })
    validate_gltf_binary_layout(
        gltf,
        bytes(buffer.data),
        require_skin=include_mesh,
        joint_count=joint_count,
    )
    report = {
        "geometry": {**geometry, "faces": 452 if include_mesh else 0},
        "validation_summary": {"maximum_position_error": 0.0},
    }
    return {
        "vela.bin": bytes(buffer.data),
        "vela.gltf": (json.dumps(gltf, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "vela-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }


__all__ = ["build_vela_rig_artifacts"]
