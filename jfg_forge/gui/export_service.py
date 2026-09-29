"""Forge-facing Boy glTF export coordination.

All geometry, texture, skeleton, and animation construction remains in
``jfg_forge.core.gltf_rig``.  This module only selects an operation, assigns safe
technical names, writes sidecars, and validates the resulting interchange
files.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
import json
from pathlib import Path
import struct
from typing import Any, Callable
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from jfg_forge.core.gltf_rig import (
    _gltf_texcoord,
    _image_uri,
    _pixel_alpha_properties,
    build_rig_artifacts,
    validate_gltf_binary_layout,
)
from jfg_forge.core.asset_types import AnimationClip, BoyAsset, LoadedAttachment, TextureAsset
from jfg_forge.core.gltf_decal import plan_gltf_decal_offsets
from jfg_forge.core.rdp_material import primitive_material_state
from jfg_forge.core.roster import CharacterSpec
from jfg_forge.core.texture_rgba16 import encode_png_rgba
from jfg_forge.core.gltf_compact_rig import (
    build_compact_rig_artifacts,
    build_lupus_rig_artifacts,
    build_powerdog_rig_artifacts,
    build_powergirl_rig_artifacts,
    build_vela_rig_artifacts,
)
from jfg_forge.gui.runtime_timing import PlaybackTimingContext


class ExportOperation(StrEnum):
    MODEL = "model"
    CURRENT_ANIMATION = "current_animation"
    MODEL_AND_CURRENT_ANIMATION = "model_and_current_animation"


@dataclass(frozen=True)
class ExportResult:
    operation: ExportOperation
    destination: Path
    written_files: tuple[Path, ...]
    animation_index: int | None
    animation_id: int | None
    mesh_included: bool
    animation_count: int
    maximum_position_error: float
    attachment_slot: int | None
    attachment_prop_id: int | None
    effective_samples_per_second: float | None
    animation_duration_seconds: float | None


def suggested_filename(
    operation: ExportOperation,
    clip: AnimationClip | None = None,
    *,
    character_name: str = "Boy",
    prop_id: int = 220,
) -> str:
    if operation is ExportOperation.MODEL:
        if clip is not None:
            raise ValueError("Model-only export does not accept an animation clip.")
        return f"{character_name}_Prop{prop_id}.gltf"
    if clip is None:
        raise ValueError("Animation export requires a selected clip.")
    identity = f"anim_{clip.animation_index:02d}_ID{clip.animation_id}"
    if operation is ExportOperation.CURRENT_ANIMATION:
        return f"{character_name}_{identity}.gltf"
    if operation is ExportOperation.MODEL_AND_CURRENT_ANIMATION:
        return f"{character_name}_Prop{prop_id}_{identity}.gltf"
    raise ValueError(f"Unsupported export operation {operation!r}.")


def _animation_spec(clip: AnimationClip) -> dict[str, object]:
    return {
        "index": clip.animation_index,
        "id": clip.animation_id,
        "name": f"anim_{clip.animation_index:02d}_ID{clip.animation_id}",
        "loop": clip.loop,
    }


def _validation_times(clip: AnimationClip) -> tuple[float, ...]:
    end = float(clip.sample_count if clip.loop else clip.sample_count - 1)
    final_decodable = float(clip.sample_count - 1)
    return tuple(dict.fromkeys((0.0, end / 2.0, final_decodable)))


def _resolve_image_source(base_directory: Path, uri: str) -> Path:
    """Resolve the intermediate builder URI without assuming a shared drive."""
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path_text = url2pathname(parsed.path)
        if parsed.netloc:
            path_text = f"//{parsed.netloc}{path_text}"
        return Path(path_text).resolve(strict=True)
    if parsed.scheme:
        raise ValueError(f"Unsupported local glTF image URI scheme: {parsed.scheme}")
    return (base_directory / unquote(uri)).resolve(strict=True)


def _export_image_payload(base_directory: Path, image: dict[str, Any]) -> tuple[bytes, str]:
    uri = image["uri"]
    if uri.startswith("data:image/png;base64,"):
        payload = base64.b64decode(uri.partition(",")[2], validate=True)
        fallback_name = "texture.png"
    else:
        source = _resolve_image_source(base_directory, uri)
        payload = source.read_bytes()
        fallback_name = source.name
    portable_name = image.get("extras", {}).get("portable_filename", fallback_name)
    return payload, portable_name


def _pack_floats(values: list[float]) -> bytes:
    return struct.pack("<" + "f" * len(values), *values)


def _append_accessor(
    gltf: dict[str, Any],
    binary: bytearray,
    payload: bytes,
    *,
    count: int,
    type_name: str,
    minimum: list[float] | None = None,
    maximum: list[float] | None = None,
) -> int:
    while len(binary) % 4:
        binary.append(0)
    offset = len(binary)
    binary.extend(payload)
    view_index = len(gltf["bufferViews"])
    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "target": 34962,
    })
    accessor: dict[str, Any] = {
        "bufferView": view_index,
        "componentType": 5126,
        "count": count,
        "type": type_name,
    }
    if minimum is not None:
        accessor["min"] = minimum
    if maximum is not None:
        accessor["max"] = maximum
    accessor_index = len(gltf["accessors"])
    gltf["accessors"].append(accessor)
    return accessor_index


def _retime_animation(
    gltf: dict[str, Any],
    binary: bytes,
    clip: AnimationClip,
    timing_context: PlaybackTimingContext,
) -> tuple[bytes, float, float]:
    """Convert technical sample-position keys to the exact preview seconds."""
    rate = timing_context.effective_samples_per_second(clip)
    if not rate > 0.0:
        raise ValueError("Effective animation rate must be positive.")
    data = bytearray(binary)
    animations = gltf.get("animations", [])
    if len(animations) != 1:
        raise ValueError("Current-animation export must contain exactly one animation.")
    animation = animations[0]
    input_accessors = {sampler["input"] for sampler in animation["samplers"]}
    for accessor_index in input_accessors:
        accessor = gltf["accessors"][accessor_index]
        if accessor["componentType"] != 5126 or accessor["type"] != "SCALAR":
            raise ValueError("Animation time accessor must be FLOAT SCALAR.")
        view = gltf["bufferViews"][accessor["bufferView"]]
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        values = struct.unpack_from("<" + "f" * accessor["count"], data, offset)
        seconds = tuple(value / rate for value in values)
        struct.pack_into("<" + "f" * len(seconds), data, offset, *seconds)
        stored_seconds = struct.unpack_from("<" + "f" * accessor["count"], data, offset)
        accessor["min"] = [min(stored_seconds)]
        accessor["max"] = [max(stored_seconds)]
    span = float(clip.sample_count if clip.loop else clip.sample_count - 1)
    duration = span / rate
    animation["extras"].update({
        "effective_samples_per_second": rate,
        "movement_speed": timing_context.movement_speed,
        "state_timing_flag": timing_context.state_timing_flag,
        "timing_mode": timing_context.timing_mode.value,
        "time_unit": "seconds using the exported Forge preview timing context",
    })
    return bytes(data), rate, duration


def _sampler_wrap(axis: object) -> int:
    if not isinstance(axis, dict):
        return 10497
    if axis.get("clamp"):
        return 33071
    if axis.get("mirror"):
        return 33648
    return 10497


def _attachment_name(attachment: LoadedAttachment) -> str:
    return (
        f"{attachment.definition.name}_slot{attachment.slot.slot}_Prop{attachment.slot.prop_id}_"
        f"{attachment.slot.name}"
    )


def _append_attachment(
    gltf: dict[str, Any],
    binary: bytes,
    attachment: LoadedAttachment,
    texture_manifest_path: Path | None,
    output_directory: Path,
) -> bytes:
    """Append one rigid character attachment below its verified joint node."""
    if attachment.model.active_face_count != attachment.slot.expected_active_faces:
        raise ValueError("Attachment geometry differs from its verified active-face count.")

    name = _attachment_name(attachment)
    data = bytearray(binary)
    texture_by_index = {
        texture.texture_index: texture for texture in attachment.model.textures
    }
    used_texture_indices = sorted({
        primitive.texture_index
        for primitive in attachment.model.render_mesh.primitives
        if primitive.texture_index is not None
        and texture_by_index[primitive.texture_index].supported
    })
    texture_refs: dict[int, int] = {}
    gltf.setdefault("images", [])
    gltf.setdefault("samplers", [])
    gltf.setdefault("textures", [])
    gltf.setdefault("materials", [])
    for texture_index in used_texture_indices:
        texture: TextureAsset = texture_by_index[texture_index]
        relative_png = texture.metadata.get("verified_rgba16_png")
        if texture.supported and texture.rgba is not None and texture.width and texture.height:
            png_bytes = encode_png_rgba(texture.width, texture.height, texture.rgba)
            image_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            portable_filename = f"{name}_tex{texture_index:02d}.png"
            pixel_source = f"ROM decoded by {texture.decoder_id}"
        elif isinstance(relative_png, str):
            source = texture_manifest_path.parent / relative_png
            image_uri = _image_uri(source, output_directory)
            portable_filename = f"{name}_tex{texture_index:02d}_{source.name}"
            pixel_source = "verified RGBA16 reference PNG"
        else:
            raise ValueError(f"Supported attachment texture {texture_index} has no pixel data.")
        sampler = texture.sampler or {}
        sampler_index = len(gltf["samplers"])
        gltf["samplers"].append({
            "wrapS": _sampler_wrap(sampler.get("cms")),
            "wrapT": _sampler_wrap(sampler.get("cmt")),
            "magFilter": 9729,
            "minFilter": 9729,
        })
        image_index = len(gltf["images"])
        gltf["images"].append({
            "uri": image_uri,
            "name": f"{name}_texture_{texture_index:02d}",
            "extras": {"portable_filename": portable_filename, "pixel_source": pixel_source},
        })
        texture_refs[texture_index] = len(gltf["textures"])
        gltf["textures"].append({"sampler": sampler_index, "source": image_index})

    model_primitives = attachment.model.render_mesh.primitives
    material_states = [primitive_material_state(attachment.model, primitive)
                       for primitive in model_primitives]
    primitive_rgba = [
        None if primitive.texture_index is None else texture_by_index[primitive.texture_index].rgba
        for primitive in model_primitives
    ]
    decal_plan = plan_gltf_decal_offsets(
        attachment.model.render_mesh, material_states, primitive_rgba
    )
    primitives: list[dict[str, Any]] = []
    for ordinal, primitive in enumerate(attachment.model.render_mesh.primitives):
        first = primitive.first_index
        vertices = attachment.model.render_mesh.vertices[first : first + primitive.index_count]
        positions = [
            vertex.position[axis] + decal_plan.vertex_offsets[first + local_index][axis]
            for local_index, vertex in enumerate(vertices) for axis in range(3)
        ]
        count = len(vertices)
        attributes: dict[str, int] = {
            "POSITION": _append_accessor(
                gltf,
                data,
                _pack_floats(positions),
                count=count,
                type_name="VEC3",
                minimum=[min(positions[axis::3]) for axis in range(3)],
                maximum=[max(positions[axis::3]) for axis in range(3)],
            )
        }
        texture = (
            None
            if primitive.texture_index is None
            else texture_by_index[primitive.texture_index]
        )
        verified = bool(texture and texture.supported)
        if verified:
            if any(vertex.uv is None for vertex in vertices):
                raise ValueError("Verified attachment texture is missing corner UV data.")
            uv_values = [
                component
                for vertex in vertices
                for component in _gltf_texcoord(vertex.uv)  # type: ignore[arg-type]
            ]
            attributes["TEXCOORD_0"] = _append_accessor(
                gltf,
                data,
                _pack_floats(uv_values),
                count=count,
                type_name="VEC2",
            )

        color = [((ordinal * factor) % 191 + 32) / 255 for factor in (73, 109, 151)] + [1.0]
        pbr: dict[str, Any] = {
            "baseColorFactor": color,
            "metallicFactor": 0.0,
            "roughnessFactor": 1.0,
        }
        if verified:
            assert primitive.texture_index is not None
            pbr["baseColorTexture"] = {
                "index": texture_refs[primitive.texture_index],
                "texCoord": 0,
            }
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
        texture_status = (
            "NO TEXTURE"
            if texture is None
            else f"DECODED {texture.decoder_id}" if verified else "UNKNOWN FORMAT"
        )
        material_state = material_states[ordinal]
        alpha_properties = (
            material_state.gltf_properties(None if texture is None else texture.rgba)
            if material_state is not None
            else _pixel_alpha_properties(None if texture is None else texture.rgba)
        )
        material_index = len(gltf["materials"])
        gltf["materials"].append({
            "name": f"{name}_material_{ordinal:02d}_{texture_status.lower().replace(' ', '_')}",
            "pbrMetallicRoughness": pbr,
            "doubleSided": primitive.double_sided,
            **alpha_properties,
            "extras": {
                "triangle_bit_0x40": primitive.double_sided,
                "texture_status": texture_status,
                "texture_index": primitive.texture_index,
                **alpha_properties.get("extras", {}),
                "jfg_rdp_alpha_state": "VERIFIED ordinary model state" if material_state is not None else "UNKNOWN",
            },
        })
        primitives.append({
            "attributes": attributes,
            "material": material_index,
            "mode": 4,
            "extras": {
                "group_indices": list(primitive.group_indices),
                "face_count": primitive.face_count,
                "triangle_bit_0x40": primitive.double_sided,
                "gltf_decal_offset_faces": decal_plan.displaced_faces[ordinal],
                "gltf_decal_offset_distance": (
                    decal_plan.distance if decal_plan.displaced_faces[ordinal] else 0.0
                ),
            },
        })

    mesh_index = len(gltf["meshes"])
    gltf["meshes"].append({
        "name": name,
        "primitives": primitives,
        "extras": {
            "active_face_count": attachment.model.active_face_count,
            "rigid_attachment": True,
        },
    })
    socket_name = f"jfg_node_{attachment.definition.attachment_joint_id:02d}"
    socket_indices = [
        index for index, node in enumerate(gltf["nodes"]) if node.get("name") == socket_name
    ]
    if len(socket_indices) != 1:
        raise ValueError(f"Exported Boy hierarchy does not contain exactly one {socket_name}.")
    attachment_node = len(gltf["nodes"])
    identity = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    gltf["nodes"].append({
        "name": name,
        "mesh": mesh_index,
        "matrix": identity,
        "extras": {
            "attachment_joint_id": attachment.definition.attachment_joint_id,
            "local_transform": "identity",
            "prop_id": attachment.slot.prop_id,
            "slot": attachment.slot.slot,
            "status": str(attachment.definition.status),
        },
    })
    gltf["nodes"][socket_indices[0]].setdefault("children", []).append(attachment_node)
    gltf["buffers"][0]["byteLength"] = len(data)
    gltf["extras"][f"{attachment.definition.name.lower()}_attachment"] = {
        "node": attachment_node,
        "parent_joint_id": attachment.definition.attachment_joint_id,
        "prop_id": attachment.slot.prop_id,
        "slot": attachment.slot.slot,
        "local_transform": "identity",
        "status": str(attachment.definition.status),
    }
    return bytes(data)


def export_boy(
    boy: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    """Write one standalone glTF export plus binary and texture sidecars."""
    destination = Path(destination).resolve()
    if destination.suffix.lower() != ".gltf":
        raise ValueError("JFG Forge Boy exports require a .gltf destination.")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Export directory does not exist: {destination.parent}")

    include_mesh = operation is not ExportOperation.CURRENT_ANIMATION
    clip: AnimationClip | None = None
    specs: tuple[dict[str, object], ...] = ()
    validation: dict[int, tuple[float, ...]] = {}
    if operation is not ExportOperation.MODEL:
        if animation_index is None:
            raise ValueError("Current-animation export requires an animation index.")
        clip = boy.animation(animation_index)
        specs = (_animation_spec(clip),)
        validation = {clip.animation_index: _validation_times(clip)}
    elif animation_index is not None:
        raise ValueError("Model-only export does not accept an animation index.")
    if attachment is not None and not include_mesh:
        raise ValueError("Animation-only export does not include attachment geometry.")
    if attachment is not None and attachment.definition != boy.attachment:
        raise ValueError("Selected attachment does not belong to Boy's attachment definition.")

    artifacts = build_rig_artifacts(
        boy.raw_prop,
        boy.raw_rom,
        boy.texture_manifest_path,
        destination.parent,
        animation_specs=specs,
        include_mesh=include_mesh,
        validation_times=validation,
        prop_id=boy.model.prop_id,
        character_name=boy.model.name or "Boy",
        decoded_textures={
            texture.texture_index: (texture.width, texture.height, texture.rgba)
            for texture in boy.model.textures
            if texture.supported
            and texture.width is not None
            and texture.height is not None
            and texture.rgba is not None
        },
    )
    binary = artifacts["boy-rig-validation.bin"]
    gltf = json.loads(artifacts["boy-rig-validation.gltf"])
    report = json.loads(artifacts["boy-rig-validation-report.json"])
    effective_rate: float | None = None
    animation_duration: float | None = None
    if clip is not None:
        binary, effective_rate, animation_duration = _retime_animation(
            gltf,
            binary,
            clip,
            timing_context or PlaybackTimingContext(),
        )
    if attachment is not None:
        binary = _append_attachment(
            gltf,
            binary,
            attachment,
            boy.texture_manifest_path,
            destination.parent,
        )
    binary_path = destination.with_suffix(".bin")
    gltf["buffers"][0]["uri"] = binary_path.name
    gltf["asset"]["generator"] = f"JFG Forge {boy.model.name or 'Boy'} exporter"
    gltf["extras"].update({
        "forge_export_operation": operation.value,
        "technical_animation_identity": None if clip is None else {
            "index": clip.animation_index,
            "id": clip.animation_id,
        },
    })

    written: list[Path] = []
    if include_mesh:
        texture_directory = destination.parent / f"{destination.stem}_textures"
        texture_directory.mkdir(parents=False, exist_ok=True)
        for image in gltf.get("images", []):
            payload, target_name = _export_image_payload(destination.parent, image)
            target = texture_directory / target_name
            target.write_bytes(payload)
            image["uri"] = f"{texture_directory.name}/{target.name}"
            written.append(target)

    validate_gltf_binary_layout(gltf, binary, require_skin=include_mesh)
    binary_path.write_bytes(binary)
    destination.write_text(json.dumps(gltf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.extend((binary_path, destination))

    for image in gltf.get("images", []):
        if not (destination.parent / image["uri"]).is_file():
            raise RuntimeError(f"Exported glTF image is missing: {image['uri']}")
    if binary_path.stat().st_size != gltf["buffers"][0]["byteLength"]:
        raise RuntimeError("Exported glTF binary length differs from its declaration.")

    return ExportResult(
        operation=operation,
        destination=destination,
        written_files=tuple(written),
        animation_index=None if clip is None else clip.animation_index,
        animation_id=None if clip is None else clip.animation_id,
        mesh_included=include_mesh,
        animation_count=len(gltf.get("animations", [])),
        maximum_position_error=float(report["validation_summary"]["maximum_position_error"]),
        attachment_slot=None if attachment is None else attachment.slot.slot,
        attachment_prop_id=None if attachment is None else attachment.slot.prop_id,
        effective_samples_per_second=effective_rate,
        animation_duration_seconds=animation_duration,
    )


def _export_compact_character(
    character: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
    character_name: str,
    artifact_stem: str,
    builder: Callable[..., dict[str, bytes]],
) -> ExportResult:
    """Write one compact-model character glTF with shared preview timing."""
    destination = Path(destination).resolve()
    if destination.suffix.lower() != ".gltf":
        raise ValueError(f"JFG Forge {character_name} exports require a .gltf destination.")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Export directory does not exist: {destination.parent}")
    include_mesh = operation is not ExportOperation.CURRENT_ANIMATION
    clip = None
    if operation is not ExportOperation.MODEL:
        if animation_index is None:
            raise ValueError("Current-animation export requires an animation index.")
        clip = character.animation(animation_index)
    elif animation_index is not None:
        raise ValueError("Model-only export does not accept an animation index.")
    if attachment is not None and not include_mesh:
        raise ValueError("Animation-only export does not include attachment geometry.")
    if attachment is not None and attachment.definition != character.attachment:
        raise ValueError(
            f"Selected attachment does not belong to {character_name}'s attachment definition."
        )

    artifacts = builder(
        character,
        destination.parent,
        clip=clip,
        include_mesh=include_mesh,
    )
    binary = artifacts[f"{artifact_stem}.bin"]
    gltf = json.loads(artifacts[f"{artifact_stem}.gltf"])
    report = json.loads(artifacts[f"{artifact_stem}-report.json"])
    effective_rate = None
    animation_duration = None
    if clip is not None:
        binary, effective_rate, animation_duration = _retime_animation(
            gltf,
            binary,
            clip,
            timing_context or PlaybackTimingContext(),
        )
    if attachment is not None:
        binary = _append_attachment(
            gltf,
            binary,
            attachment,
            character.texture_manifest_path,
            destination.parent,
        )
    binary_path = destination.with_suffix(".bin")
    gltf["buffers"][0]["uri"] = binary_path.name
    gltf["buffers"][0]["byteLength"] = len(binary)
    gltf["extras"].update({
        "forge_export_operation": operation.value,
        "technical_animation_identity": None if clip is None else {
            "index": clip.animation_index,
            "id": clip.animation_id,
        },
        "timing": "Shared JFG Forge preview/export timing context",
    })

    written: list[Path] = []
    if include_mesh:
        texture_directory = destination.parent / f"{destination.stem}_textures"
        texture_directory.mkdir(parents=False, exist_ok=True)
        for image in gltf.get("images", []):
            payload, target_name = _export_image_payload(destination.parent, image)
            target = texture_directory / target_name
            target.write_bytes(payload)
            image["uri"] = f"{texture_directory.name}/{target.name}"
            written.append(target)

    joint_count = len(character.model.skeleton.joints) if character.model.skeleton else None
    validate_gltf_binary_layout(
        gltf, binary, require_skin=include_mesh, joint_count=joint_count
    )
    binary_path.write_bytes(binary)
    destination.write_text(json.dumps(gltf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.extend((binary_path, destination))
    return ExportResult(
        operation=operation,
        destination=destination,
        written_files=tuple(written),
        animation_index=None if clip is None else clip.animation_index,
        animation_id=None if clip is None else clip.animation_id,
        mesh_included=include_mesh,
        animation_count=len(gltf.get("animations", [])),
        maximum_position_error=float(report["validation_summary"]["maximum_position_error"]),
        attachment_slot=None if attachment is None else attachment.slot.slot,
        attachment_prop_id=None if attachment is None else attachment.slot.prop_id,
        effective_samples_per_second=effective_rate,
        animation_duration_seconds=animation_duration,
    )


def export_vela(
    vela: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    return _export_compact_character(
        vela,
        destination,
        operation,
        animation_index=animation_index,
        attachment=attachment,
        timing_context=timing_context,
        character_name="Vela",
        artifact_stem="vela",
        builder=build_vela_rig_artifacts,
    )


def export_lupus(
    lupus: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    return _export_compact_character(
        lupus,
        destination,
        operation,
        animation_index=animation_index,
        attachment=attachment,
        timing_context=timing_context,
        character_name="Lupus",
        artifact_stem="lupus",
        builder=build_lupus_rig_artifacts,
    )


def export_compact_character(
    spec: CharacterSpec,
    character: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    """Export any roster entry that uses the generic compact loader."""

    def builder(asset: BoyAsset, output_dir: Path, *, clip: AnimationClip | None, include_mesh: bool):
        return build_compact_rig_artifacts(
            asset, output_dir, clip=clip, include_mesh=include_mesh, spec=spec
        )

    return _export_compact_character(
        character,
        destination,
        operation,
        animation_index=animation_index,
        attachment=attachment,
        timing_context=timing_context,
        character_name=spec.file_name,
        artifact_stem=spec.file_stem,
        builder=builder,
    )


def export_powerdog(
    powerdog: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    return _export_compact_character(
        powerdog,
        destination,
        operation,
        animation_index=animation_index,
        attachment=attachment,
        timing_context=timing_context,
        character_name="PowerDog",
        artifact_stem="powerdog",
        builder=build_powerdog_rig_artifacts,
    )


def export_powergirl(
    powergirl: BoyAsset,
    destination: Path,
    operation: ExportOperation,
    *,
    animation_index: int | None = None,
    attachment: LoadedAttachment | None = None,
    timing_context: PlaybackTimingContext | None = None,
) -> ExportResult:
    return _export_compact_character(
        powergirl,
        destination,
        operation,
        animation_index=animation_index,
        attachment=attachment,
        timing_context=timing_context,
        character_name="PowerGirl",
        artifact_stem="powergirl",
        builder=build_powergirl_rig_artifacts,
    )


def exporter_for(spec: CharacterSpec) -> Callable[..., ExportResult]:
    """Return ``export(asset, destination, operation, ...)`` for a roster entry."""
    if spec.compact:
        return partial(export_compact_character, spec)
    return {
        "boy": export_boy,
        "powerboy": export_boy,
        "vela": export_vela,
        "powergirl": export_powergirl,
        "lupus": export_lupus,
        "powerdog": export_powerdog,
    }[spec.kind]


__all__ = [
    "ExportOperation",
    "ExportResult",
    "export_boy",
    "export_compact_character",
    "exporter_for",
    "export_lupus",
    "export_powerdog",
    "export_powergirl",
    "export_vela",
    "suggested_filename",
]
