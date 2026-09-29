"""Renderer-neutral production API for the multiplayer Green Ant / Prop 250."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from jfg_forge.core.model_parser import BoyExportError, parse_model
from jfg_forge.core.character_data import (
    BOYGUN_ATTACHMENT,
    _load_prop_input,
    _matrix4,
    _normalize_model,
    load_boy_attachment,
)
from jfg_forge.core.asset_types import (
    AnimationClip,
    AttachmentDefinition,
    BoyAsset,
    EvidenceStatus,
    Joint,
    JointPose,
    LoadedAttachment,
    Pose,
    Skeleton,
)
from jfg_forge.core.rom_source import RomSource
from jfg_forge.core.compact_animation import (
    build_compact_matrices,
    catalog_compact_animations,
    compact_animation_tables,
    decode_vela_animation_time,
)


GREENANT_PROP_ID = 250
GREENANT_PROP_SHA256 = "5b044d6c9a43bbdfa8505fc77bdfab5f81888d2323680cae7c5100ae4c25160f"
GREENANT_TRANSFORM_COUNT = 21
GREENANT_ANIMATION_COUNT = 51
GREENANT_ACTIVE_FACE_COUNT = 307

# Object definition 8 `playerGreenAnt` lists definition 399 `BoyGun` as its only
# child, so the Ant carries Juno's nine hand-and-weapon models. The socket is the
# matrix of the Prop 250 first reference record (vertex 336, matrix 6), read the
# way objMakeGunMtx reads Juno's. LIKELY, not VERIFIED: the ant-to-controller
# link rests on the shared child and clip table, not on a runtime capture.
GREENANT_ATTACHMENT = AttachmentDefinition(
    name="BoyGun",
    object_definition_id=399,
    attachment_joint_id=6,
    slots=BOYGUN_ATTACHMENT.slots,
    status=EvidenceStatus.LIKELY,
)


def _load_skeleton(data: bytes) -> Skeleton:
    start = struct.unpack_from(">I", data, 0x54)[0]
    count = data[0x4F]
    if count != GREENANT_TRANSFORM_COUNT:
        raise BoyExportError(f"Green Ant transform count is {count}, expected 21.")
    joints = tuple(
        Joint(
            joint_id=data[start + index * 16 + 1],
            parent_id=(
                None
                if data[start + index * 16] == 0xFF
                else data[start + index * 16]
            ),
            name=f"jfg_node_{data[start + index * 16 + 1]:02d}",
            static_local_translation=struct.unpack_from(">fff", data, start + index * 16 + 4),
            record_index=index,
        )
        for index in range(count)
    )
    if tuple(joint.joint_id for joint in joints) != tuple(range(count)):
        raise BoyExportError("Green Ant skeleton matrix IDs are not exactly 0..20.")
    roots = tuple(joint.joint_id for joint in joints if joint.parent_id is None)
    if len(roots) != 1:
        raise BoyExportError("Green Ant skeleton must have exactly one root joint.")
    return Skeleton(joints=joints, root_joint_id=roots[0])


def _load_animations(rom: bytes) -> tuple[AnimationClip, ...]:
    catalog = catalog_compact_animations(
        rom,
        prop_id=GREENANT_PROP_ID,
        transform_count=GREENANT_TRANSFORM_COUNT,
        expected_animation_count=GREENANT_ANIMATION_COUNT,
        label="MultiGreenAnt",
        index_key="ant_animation_index",
    )
    tables = compact_animation_tables(
        rom,
        prop_id=GREENANT_PROP_ID,
        transform_count=GREENANT_TRANSFORM_COUNT,
        expected_animation_count=GREENANT_ANIMATION_COUNT,
        label="Green Ant",
    )
    clips = []
    for record in catalog["animations"]:
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        clips.append(
            AnimationClip(
                animation_index=record["ant_animation_index"],
                animation_id=record["animation_id"],
                sample_count=record["sample_count"],
                loop=record["loop_enabled"],
                channel_map=tuple(record["channel_map"]),
                blob=tables["asset43"][start:end],
                metadata=MappingProxyType(dict(record)),
            )
        )
    if tuple(clip.animation_index for clip in clips) != tuple(range(GREENANT_ANIMATION_COUNT)):
        raise BoyExportError("Green Ant animation catalog is not the expected contiguous 0..50 range.")
    return tuple(clips)


def load_greenant(prop_path: Path | None, rom_path: RomSource | Path, texture_manifest_path: Path | None) -> BoyAsset:
    """Load multiplayer Green Ant Prop 250 with its model, rig and clips."""
    source, prop_path, data = _load_prop_input(prop_path, rom_path, GREENANT_PROP_ID)
    texture_manifest_path = None if texture_manifest_path is None else Path(texture_manifest_path).resolve(strict=True)
    if hashlib.sha256(data).hexdigest() != GREENANT_PROP_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 250 MultiGreenAnt binary.")
    rom = source.data
    model = _normalize_model(
        GREENANT_PROP_ID,
        data,
        parse_model(data),
        rom,
        texture_manifest_path,
        skeleton=_load_skeleton(data),
    )
    if model.active_face_count != GREENANT_ACTIVE_FACE_COUNT:
        raise BoyExportError(
            f"Green Ant active face count is {model.active_face_count}, expected {GREENANT_ACTIVE_FACE_COUNT}."
        )
    return BoyAsset(
        model=model,
        animations=_load_animations(rom),
        attachment=GREENANT_ATTACHMENT,
        rom_path=source.path,
        prop_path=prop_path,
        texture_manifest_path=texture_manifest_path,
        raw_rom=rom,
        raw_prop=data,
        rom_source=source,
    )


def sample_greenant_animation(greenant: BoyAsset, animation_index: int, time: float) -> Pose:
    clip = greenant.animation(animation_index)
    lookahead = bytes.fromhex(str(clip.metadata.get("cross_blob_lookahead_hex", "")))
    frame = decode_vela_animation_time(clip.blob, time, lookahead)
    matrices = build_compact_matrices(
        greenant.raw_prop,
        frame,
        greenant.raw_rom,
        list(clip.channel_map),
        transform_count=GREENANT_TRANSFORM_COUNT,
        label="Green Ant",
    )
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


def load_greenant_attachment(
    greenant: BoyAsset,
    *,
    slot: int,
    props_dir: Path | None = None,
) -> LoadedAttachment:
    """Load one BoyGun slot for the Green Ant through Juno's slot loader."""
    return load_boy_attachment(greenant, slot=slot, props_dir=props_dir)


__all__ = [
    "GREENANT_ATTACHMENT",
    "GREENANT_PROP_ID",
    "load_greenant",
    "load_greenant_attachment",
    "sample_greenant_animation",
]
