"""Public renderer-neutral Boy/Juno data API for JFG Forge.

This module wraps the established parsers and decoders.  It deliberately does
not contain UI, rendering, glTF, Blender, or export types.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import jfg_re.boy_animation_catalog as animation_catalog
from jfg_re.boy_anim0_frame0 import build_matrices
from jfg_re.boy_anim0_temporal import decode_time as decode_animation0_time
from jfg_re.boy_export import (
    BOY_PROP_ID,
    BoyExportError,
    BoyModel,
    decompress_texture_container,
    parse_boy,
    parse_model,
    resolve_boy_textures,
)
from jfg_re.boy_textured_export import decode_tile_state
from jfg_re.boy_transform_analysis import build_transform_analysis
from jfg_re.forge_types import (
    AnimationClip,
    AttachmentDefinition,
    AttachmentSlot,
    BoyAsset,
    EvidenceStatus,
    Joint,
    JointPose,
    LoadedAttachment,
    MaterialAsset,
    Matrix4,
    ModelAsset,
    ModelGroup,
    Pose,
    Skeleton,
    SourceVertex,
    TextureAsset,
)
from jfg_re.props import validate_rom_identity
from jfg_re.render_mesh import expand_render_mesh, rigid_matrix_assignments
from jfg_re.textures_rgba16 import DECODER_ID, decode_texture


BOYGUN_ATTACHMENT = AttachmentDefinition(
    name="BoyGun",
    object_definition_id=399,
    attachment_joint_id=6,
    slots=(
        AttachmentSlot(0, 301, "BPistol", 67),
        AttachmentSlot(1, 302, "BAutomatic", 116),
        AttachmentSlot(2, 303, "BUzi", 126),
        AttachmentSlot(3, 304, "BUzi1", 106),
        AttachmentSlot(4, 305, "BShrinkBeam", 110),
        AttachmentSlot(5, 306, "BRocket", 142),
        AttachmentSlot(6, 307, "BFlameThrower", 132),
        AttachmentSlot(7, 308, "BSniper", 245),
        AttachmentSlot(8, 309, "JunoHand", 32),
    ),
    status=EvidenceStatus.VERIFIED,
)


def _model_name(data: bytes) -> str | None:
    raw = data[:16].split(b"\0", 1)[0]
    if not raw:
        return None
    return raw.decode("ascii", errors="replace")


def _matrix4(value: list[list[float]]) -> Matrix4:
    if len(value) != 4 or any(len(row) != 4 for row in value):
        raise BoyExportError("Expected a 4x4 JFG matrix.")
    return tuple(tuple(float(item) for item in row) for row in value)  # type: ignore[return-value]


def _decode_textures(
    parsed: BoyModel,
    rom: bytes,
    texture_manifest_path: Path,
) -> tuple[tuple[TextureAsset, ...], dict[int, dict[str, Any]]]:
    _, by_index = resolve_boy_textures(parsed, rom, texture_manifest_path)
    textures: list[TextureAsset] = []
    for texture_index in range(len(parsed.texture_records)):
        record = by_index[texture_index]
        header = bytes.fromhex(record["runtime_header_hex"])
        rgba: bytes | None = None
        width: int | None = None
        height: int | None = None
        decoder_id: str | None = None
        sampler: dict[str, Any] | None = None
        status = EvidenceStatus.UNKNOWN
        if record["verified_rgba16_match"]:
            binary = decompress_texture_container(rom, record["compressed_stream_rom_offset"])
            decoded_header, rgba = decode_texture(binary)
            width, height = decoded_header.width, decoded_header.height
            decoder_id = DECODER_ID
            sampler = decode_tile_state(record)
            status = EvidenceStatus.VERIFIED
        textures.append(
            TextureAsset(
                texture_index=texture_index,
                texture_id=record["texture_id"],
                status=status,
                width=width,
                height=height,
                rgba=rgba,
                decoder_id=decoder_id,
                rom_offset=record["compressed_stream_rom_offset"],
                header=header,
                sampler=MappingProxyType(sampler) if sampler is not None else None,
                metadata=MappingProxyType(dict(record)),
            )
        )
    return tuple(textures), by_index


def _normalize_model(
    prop_id: int,
    data: bytes,
    parsed: BoyModel,
    rom: bytes,
    texture_manifest_path: Path,
    *,
    skeleton: Skeleton | None = None,
) -> ModelAsset:
    textures, _ = _decode_textures(parsed, rom, texture_manifest_path)
    texture_by_index = {texture.texture_index: texture for texture in textures}
    dimensions = {
        index: (texture.width, texture.height) if texture.supported else None
        for index, texture in texture_by_index.items()
    }
    assignments = rigid_matrix_assignments(parsed)
    render_mesh = expand_render_mesh(parsed, assignments, dimensions, exclude_degenerate=True)

    source_vertices = tuple(
        SourceVertex(index, (vertex.x, vertex.y, vertex.z), vertex.attributes)
        for index, vertex in enumerate(parsed.vertices)
    )
    groups: list[ModelGroup] = []
    for group in parsed.groups:
        following = parsed.groups[group.index + 1] if group.index + 1 < len(parsed.groups) else parsed.sentinel
        groups.append(
            ModelGroup(
                index=group.index,
                texture_index=group.texture_index,
                matrix_ids=group.matrix_ids,
                matrix_splits=group.matrix_splits,
                vertex_range=(group.vertex_start, following.vertex_start),
                triangle_range=(group.triangle_start, following.triangle_start),
                render_flags=group.render_flags,
                runtime_skipped=group.runtime_skipped,
            )
        )

    materials: list[MaterialAsset] = []
    for primitive in render_mesh.primitives:
        texture = None if primitive.texture_index is None else texture_by_index[primitive.texture_index]
        materials.append(
            MaterialAsset(
                index=primitive.material_index,
                texture_index=primitive.texture_index,
                texture_id=None if texture is None else texture.texture_id,
                texture_status=None if texture is None else texture.status,
                double_sided=primitive.double_sided,
            )
        )
    return ModelAsset(
        prop_id=prop_id,
        name=_model_name(data),
        source_vertices=source_vertices,
        groups=tuple(groups),
        render_mesh=render_mesh,
        materials=tuple(materials),
        textures=textures,
        rigid_joint_assignments=MappingProxyType(dict(assignments)),
        skeleton=skeleton,
    )


def _load_skeleton(boy_data: bytes) -> Skeleton:
    analysis = build_transform_analysis(boy_data)
    joints = tuple(
        Joint(
            joint_id=record["matrix_id"],
            parent_id=None if record["parent_id"] == 0xFF else record["parent_id"],
            name=f"jfg_node_{record['matrix_id']:02d}",
            static_local_translation=tuple(record["local_translation_xyz"]),
            record_index=record["record_index"],
        )
        for record in analysis["transform_records"]
    )
    if tuple(joint.joint_id for joint in joints) != tuple(range(21)):
        raise BoyExportError("Boy skeleton matrix IDs are not exactly 0..20.")
    root = next((joint.joint_id for joint in joints if joint.parent_id is None), None)
    if root is None:
        raise BoyExportError("Boy skeleton has no root joint.")
    return Skeleton(joints=joints, root_joint_id=root)


def _load_animations(rom: bytes) -> tuple[AnimationClip, ...]:
    catalog = animation_catalog.catalog_boy_animations(rom)
    tables = animation_catalog._tables(rom)
    clips: list[AnimationClip] = []
    for record in catalog["animations"]:
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        clip = AnimationClip(
            animation_index=record["boy_animation_index"],
            animation_id=record["animation_id"],
            sample_count=record["sample_count"],
            loop=record["loop_enabled"],
            channel_map=tuple(record["channel_map"]),
            blob=tables["asset43"][start:end],
            metadata=MappingProxyType(dict(record)),
        )
        clips.append(clip)
    if tuple(clip.animation_index for clip in clips) != tuple(range(52)):
        raise BoyExportError("Boy animation catalog is not the expected contiguous 0..51 range.")
    return tuple(clips)


def load_boy(
    prop_path: Path,
    rom_path: Path,
    texture_manifest_path: Path,
) -> BoyAsset:
    """Load normalized Prop 220 model, textures, skeleton, and 52 clips."""
    identity = validate_rom_identity(Path(rom_path))
    prop_path = Path(prop_path).resolve(strict=True)
    texture_manifest_path = Path(texture_manifest_path).resolve(strict=True)
    boy_data = prop_path.read_bytes()
    rom = identity.path.read_bytes()
    parsed = parse_boy(boy_data)
    skeleton = _load_skeleton(boy_data)
    model = _normalize_model(
        BOY_PROP_ID,
        boy_data,
        parsed,
        rom,
        texture_manifest_path,
        skeleton=skeleton,
    )
    return BoyAsset(
        model=model,
        animations=_load_animations(rom),
        attachment=BOYGUN_ATTACHMENT,
        rom_path=identity.path,
        prop_path=prop_path,
        texture_manifest_path=texture_manifest_path,
        raw_rom=rom,
        raw_prop=boy_data,
    )


def sample_animation(boy: BoyAsset, animation_index: int, time: float) -> Pose:
    """Sample one Boy clip with the verified JFG packed-angle interpolation."""
    clip = boy.animation(animation_index)
    if animation_index == 0:
        frame = decode_animation0_time(clip.blob, time)
    else:
        frame = animation_catalog.decode_animation_time(clip.blob, time)
    matrices = build_matrices(boy.raw_prop, frame, boy.raw_rom, list(clip.channel_map))
    joints = tuple(
        JointPose(
            joint_id=record["matrix_id"],
            parent_id=None if record["parent_id"] == 0xFF else record["parent_id"],
            local_matrix=_matrix4(record["local_matrix"]),
            world_matrix=_matrix4(record["world_model_matrix"]),
        )
        for record in matrices
    )
    return Pose(
        animation_index=animation_index,
        animation_id=clip.animation_id,
        time=float(time),
        current_sample=frame["current_sample"],
        next_sample=frame["next_sample"],
        fraction_10bit=frame["fraction_10bit"],
        root_translation=tuple(frame["root_translation_model_xyz"]),
        root_translation_raw_q10=tuple(frame["root_translation_raw_q10_xyz"]),
        joints=joints,
    )


def load_boy_attachment(
    boy: BoyAsset,
    *,
    slot: int,
    props_dir: Path | None = None,
) -> LoadedAttachment:
    """Load one verified BoyGun slot as renderer-neutral model data."""
    try:
        slot_metadata = boy.attachment.slots[slot]
    except IndexError as error:
        raise KeyError(f"BoyGun slot {slot} is outside 0..8.") from error
    if slot_metadata.slot != slot:
        raise KeyError(f"BoyGun slot {slot} is unavailable.")
    source_dir = boy.prop_path.parent if props_dir is None else Path(props_dir).resolve(strict=True)
    candidates = sorted(source_dir.glob(f"{slot_metadata.prop_id:04d}_*.bin"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected one Prop {slot_metadata.prop_id} binary in {source_dir}; found {len(candidates)}."
        )
    data = candidates[0].read_bytes()
    parsed = parse_model(data)
    model = _normalize_model(
        slot_metadata.prop_id,
        data,
        parsed,
        boy.raw_rom,
        boy.texture_manifest_path,
    )
    if model.name != slot_metadata.name:
        raise BoyExportError(
            f"BoyGun slot {slot} expected {slot_metadata.name}, found {model.name}."
        )
    if model.active_face_count != slot_metadata.expected_active_faces:
        raise BoyExportError(
            f"BoyGun slot {slot} active face count {model.active_face_count} differs from "
            f"verified count {slot_metadata.expected_active_faces}."
        )
    return LoadedAttachment(boy.attachment, slot_metadata, model)


__all__ = [
    "BOYGUN_ATTACHMENT",
    "load_boy",
    "load_boy_attachment",
    "sample_animation",
]
