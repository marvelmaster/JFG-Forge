"""Shared compact-character glTF 2.0 builders used by Vela, PowerGirl, Lupus, and PowerDog."""

from __future__ import annotations

from typing import TYPE_CHECKING

import json
import math
from pathlib import Path
import struct
from typing import Any, Callable

from jfg_forge.core.model_parser import parse_model, resolve_boy_textures
from jfg_forge.core.gltf_rig import (
    _Buffer,
    _bake_states,
    _geometry,
    _pack_floats,
    _quat_from_row_matrix,
    validate_gltf_binary_layout,
)
from jfg_forge.core.asset_types import AnimationClip, BoyAsset, Pose
from jfg_forge.core.render_mesh import rigid_matrix_assignments
from jfg_forge.core.vela import sample_vela_animation


if TYPE_CHECKING:
    from jfg_forge.core.roster import CharacterSpec


def _decompose_local(
    matrix: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float]]:
    scales = tuple(math.sqrt(sum(matrix[row][column] ** 2 for column in range(3))) for row in range(3))
    normalized = [list(row) for row in matrix]
    for row, scale in enumerate(scales):
        if scale <= 0.0:
            raise ValueError("Character animation produced a zero local scale.")
        for column in range(3):
            normalized[row][column] /= scale
    return _quat_from_row_matrix(normalized), scales


def _build_compact_character_rig_artifacts(
    character: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
    sample_pose: Callable[[BoyAsset, int, float], Pose],
    character_name: str,
    artifact_stem: str,
    root_status: str,
    joint_status: str,
    animation_timing: str,
    asset_generator: str,
    character_extras: dict[str, Any],
    exclude_degenerate: bool = False,
) -> dict[str, bytes]:
    model = parse_model(character.raw_prop)
    assignments = rigid_matrix_assignments(model)
    buffer = _Buffer()
    _, textures = resolve_boy_textures(
        model, character.raw_rom, character.texture_manifest_path
    )
    decoded_textures = {
        texture.texture_index: (texture.width, texture.height, texture.rgba)
        for texture in character.model.textures
        if (
            texture.supported
            and texture.width is not None
            and texture.height is not None
            and texture.rgba is not None
        )
    }
    if include_mesh:
        primitives, materials, images, samplers, gltf_textures, geometry = _geometry(
            model,
            textures,
            assignments,
            character.texture_manifest_path,
            output_dir,
            buffer,
            exclude_degenerate=exclude_degenerate,
            decoded_textures=decoded_textures,
        )
    else:
        primitives, materials, images, samplers, gltf_textures = [], [], [], [], []
        geometry = {"render_corner_vertices": 0, "primitives": 0}

    skeleton = character.model.skeleton
    if skeleton is None:
        raise ValueError(f"{character_name} export requires its skeleton.")
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

    initial_pose = sample_pose(character, 0, 0.0)
    nodes: list[dict[str, Any]] = [{
        "name": f"{character_name}_Prop_{character.model.prop_id:04d}",
        "extras": {
            "status": root_status,
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
                "status": joint_status,
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
            pose = sample_pose(character, clip.animation_index, sample_time)
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
                "timing": animation_timing,
                "scale_streams_preserved": True,
            },
        })

    gltf: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": asset_generator},
        "scene": 0,
        "scenes": [{"name": character_name, "nodes": [0, 1 + skeleton.root_joint_id]}],
        "nodes": nodes,
        "animations": animations,
        "buffers": [{"uri": f"{artifact_stem}.bin", "byteLength": len(buffer.data)}],
        "bufferViews": buffer.views,
        "accessors": buffer.accessors,
        "extras": {
            "prop_id": character.model.prop_id,
            "geometry_status": "VERIFIED",
            **character_extras,
        },
    }
    if include_mesh:
        gltf.update({
            "meshes": [{"name": f"{character_name} runtime mesh", "primitives": primitives}],
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
        "geometry": {
            **geometry,
            "faces": character.model.active_face_count if include_mesh else 0,
        },
        "validation_summary": {"maximum_position_error": 0.0},
    }
    return {
        f"{artifact_stem}.bin": bytes(buffer.data),
        f"{artifact_stem}.gltf": (json.dumps(gltf, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        f"{artifact_stem}-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }


def build_vela_rig_artifacts(
    vela: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
) -> dict[str, bytes]:
    return _build_compact_character_rig_artifacts(
        vela,
        output_dir,
        clip=clip,
        include_mesh=include_mesh,
        sample_pose=sample_vela_animation,
        character_name="Vela",
        artifact_stem="vela",
        root_status="MVP; live 28-matrix numerical runtime capture PENDING",
        joint_status="VERIFIED structure; live numerical capture PENDING",
        animation_timing="Technical Timing; Vela gameplay timing UNKNOWN",
        asset_generator="JFG Forge Vela MVP exporter",
        character_extras={
            "live_28_matrix_capture": "PENDING",
            "game_timing": "UNKNOWN",
        },
    )


def build_powergirl_rig_artifacts(
    powergirl: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
) -> dict[str, bytes]:
    return _build_compact_character_rig_artifacts(
        powergirl,
        output_dir,
        clip=clip,
        include_mesh=include_mesh,
        sample_pose=sample_vela_animation,
        character_name="PowerGirl",
        artifact_stem="powergirl",
        root_status="VERIFIED shared 28-joint Vela structure; live numerical capture PENDING",
        joint_status="VERIFIED structure; live numerical capture PENDING",
        animation_timing="Shared Vela Game Timing; retimed by JFG Forge export service",
        asset_generator="JFG Forge PowerGirl exporter",
        character_extras={
            "joint_count": 28,
            "game_timing": "VERIFIED shared with Girl / Vela",
            "live_28_matrix_capture": "PENDING",
        },
    )


def build_lupus_rig_artifacts(
    lupus: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
) -> dict[str, bytes]:
    from jfg_forge.core.lupus import sample_lupus_animation

    return _build_compact_character_rig_artifacts(
        lupus,
        output_dir,
        clip=clip,
        include_mesh=include_mesh,
        sample_pose=sample_lupus_animation,
        character_name="Lupus",
        artifact_stem="lupus",
        root_status="VERIFIED normal Lupus model and 27-joint structure",
        joint_status="VERIFIED structure; live numerical capture PENDING",
        animation_timing="Technical Timing; retimed by JFG Forge export service",
        asset_generator="JFG Forge Lupus exporter",
        character_extras={
            "joint_count": 27,
            "game_timing": "VERIFIED in JFG Forge export service",
        },
    )


def build_compact_rig_artifacts(
    character: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
    spec: "CharacterSpec",
) -> dict[str, bytes]:
    """glTF builder for roster entries that use the generic compact loader."""
    from jfg_forge.core.compact_character import sample_compact_animation
    from jfg_forge.core.roster import TIMING_JUNO_LIKE, TIMING_VELA_LIKE

    joint_count = len(character.model.skeleton.joints)
    if spec.timing_family == TIMING_JUNO_LIKE:
        base, first, last = "Juno", 0, spec.clip_count - 1
    elif spec.timing_family == TIMING_VELA_LIKE:
        base, first, last = "Vela", 0, spec.clip_count - 1
    else:
        base = first = last = None
    if base is None:
        animation_timing = "Technical Timing (Game Timing UNKNOWN); retimed by JFG Forge export service"
        game_timing = "UNKNOWN; Technical fallback"
    else:
        animation_timing = f"LIKELY {base}-derived Game Timing; retimed by JFG Forge export service"
        game_timing = f"LIKELY: {base} factors, indices {first}..{last}"
    return _build_compact_character_rig_artifacts(
        character,
        output_dir,
        clip=clip,
        include_mesh=include_mesh,
        sample_pose=sample_compact_animation,
        character_name=spec.file_name,
        artifact_stem=spec.file_stem,
        root_status=f"Prop {spec.prop_id} {spec.model_name} model and {joint_count}-joint structure",
        joint_status="Structure decoded; live numerical capture PENDING",
        animation_timing=animation_timing,
        asset_generator=f"JFG Forge {spec.key} exporter",
        character_extras={
            "joint_count": joint_count,
            "game_timing": game_timing,
        },
    )


def build_powerdog_rig_artifacts(
    powerdog: BoyAsset,
    output_dir: Path,
    *,
    clip: AnimationClip | None,
    include_mesh: bool,
) -> dict[str, bytes]:
    from jfg_forge.core.powerdog import sample_powerdog_animation

    return _build_compact_character_rig_artifacts(
        powerdog,
        output_dir,
        clip=clip,
        include_mesh=include_mesh,
        sample_pose=sample_powerdog_animation,
        character_name="PowerDog",
        artifact_stem="powerdog",
        root_status="VERIFIED PowerDog model and independent 18-joint structure",
        joint_status="VERIFIED structure; live numerical capture PENDING",
        animation_timing="Verified PowerDog Game Timing; retimed by JFG Forge export service",
        asset_generator="JFG Forge PowerDog exporter",
        character_extras={
            "joint_count": 18,
            "game_timing": "VERIFIED PowerDog-specific timing table",
            "live_18_matrix_capture": "PENDING",
        },
        exclude_degenerate=True,
    )


__all__ = [
    "build_compact_rig_artifacts",
    "build_lupus_rig_artifacts",
    "build_powerdog_rig_artifacts",
    "build_powergirl_rig_artifacts",
    "build_vela_rig_artifacts",
]
