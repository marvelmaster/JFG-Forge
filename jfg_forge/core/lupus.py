"""Renderer-neutral production API for normal Lupus / Dog / Prop 222."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from jfg_forge.core.model_parser import BoyExportError, parse_model
from jfg_forge.core.character_data import _load_prop_input, _matrix4, _normalize_model
from jfg_forge.core.asset_types import (
    AnimationClip,
    AttachmentDefinition,
    AttachmentSlot,
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


LUPUS_PROP_ID = 222
LUPUS_PROP_SHA256 = "e69c897a48697d6adef3c922111ae05d2ef04c07ff800d91f5ee0d78ab90b3eb"
LUPUS_TRANSFORM_COUNT = 27
LUPUS_ANIMATION_COUNT = 24

DOGGUN_ATTACHMENT = AttachmentDefinition(
    name="DogGun",
    object_definition_id=401,
    attachment_joint_id=16,
    slots=(
        AttachmentSlot(0, 320, "DogPistol", 77),
        AttachmentSlot(1, 321, "DogAutomatic", 78),
        AttachmentSlot(2, 322, "DogUzi", 95),
        AttachmentSlot(3, 323, "DogUzi1", 80),
        AttachmentSlot(4, 324, "DogShrinkBeam", 86),
        AttachmentSlot(5, 325, "DogRocket", 80),
        AttachmentSlot(6, 326, "DogFlameThrower", 98),
        AttachmentSlot(7, 327, "DogSniper", 210),
        AttachmentSlot(8, 328, "DogGrenade", 132),
    ),
    status=EvidenceStatus.VERIFIED,
)


def _load_skeleton(data: bytes) -> Skeleton:
    start = struct.unpack_from(">I", data, 0x54)[0]
    count = data[0x4F]
    if count != LUPUS_TRANSFORM_COUNT:
        raise BoyExportError(f"Lupus transform count is {count}, expected 27.")
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
        raise BoyExportError("Lupus skeleton matrix IDs are not exactly 0..26.")
    roots = tuple(joint.joint_id for joint in joints if joint.parent_id is None)
    if len(roots) != 1:
        raise BoyExportError("Lupus skeleton must have exactly one root joint.")
    return Skeleton(joints=joints, root_joint_id=roots[0])


def _load_animations(rom: bytes) -> tuple[AnimationClip, ...]:
    catalog = catalog_compact_animations(
        rom,
        prop_id=LUPUS_PROP_ID,
        transform_count=LUPUS_TRANSFORM_COUNT,
        expected_animation_count=LUPUS_ANIMATION_COUNT,
        label="Dog",
        index_key="lupus_animation_index",
    )
    tables = compact_animation_tables(
        rom,
        prop_id=LUPUS_PROP_ID,
        transform_count=LUPUS_TRANSFORM_COUNT,
        expected_animation_count=LUPUS_ANIMATION_COUNT,
        label="Lupus",
    )
    clips = []
    for record in catalog["animations"]:
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        clips.append(
            AnimationClip(
                animation_index=record["lupus_animation_index"],
                animation_id=record["animation_id"],
                sample_count=record["sample_count"],
                loop=record["loop_enabled"],
                channel_map=tuple(record["channel_map"]),
                blob=tables["asset43"][start:end],
                metadata=MappingProxyType(dict(record)),
            )
        )
    if tuple(clip.animation_index for clip in clips) != tuple(range(LUPUS_ANIMATION_COUNT)):
        raise BoyExportError("Lupus animation catalog is not the expected contiguous 0..23 range.")
    return tuple(clips)


def load_lupus(prop_path: Path | None, rom_path: RomSource | Path, texture_manifest_path: Path | None) -> BoyAsset:
    """Load normal Lupus Prop 222 with its verified model, rig and clips."""
    source, prop_path, data = _load_prop_input(prop_path, rom_path, LUPUS_PROP_ID)
    texture_manifest_path = None if texture_manifest_path is None else Path(texture_manifest_path).resolve(strict=True)
    if hashlib.sha256(data).hexdigest() != LUPUS_PROP_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 222 Dog binary.")
    rom = source.data
    model = _normalize_model(
        LUPUS_PROP_ID,
        data,
        parse_model(data),
        rom,
        texture_manifest_path,
        skeleton=_load_skeleton(data),
    )
    if model.active_face_count != 361:
        raise BoyExportError(f"Lupus active face count is {model.active_face_count}, expected 361.")
    return BoyAsset(
        model=model,
        animations=_load_animations(rom),
        attachment=DOGGUN_ATTACHMENT,
        rom_path=source.path,
        prop_path=prop_path,
        texture_manifest_path=texture_manifest_path,
        raw_rom=rom,
        raw_prop=data,
        rom_source=source,
    )


def sample_lupus_animation(lupus: BoyAsset, animation_index: int, time: float) -> Pose:
    clip = lupus.animation(animation_index)
    lookahead = bytes.fromhex(str(clip.metadata.get("cross_blob_lookahead_hex", "")))
    frame = decode_vela_animation_time(clip.blob, time, lookahead)
    matrices = build_compact_matrices(
        lupus.raw_prop,
        frame,
        lupus.raw_rom,
        list(clip.channel_map),
        transform_count=LUPUS_TRANSFORM_COUNT,
        label="Lupus",
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


def load_lupus_attachment(
    lupus: BoyAsset,
    *,
    slot: int,
    props_dir: Path | None = None,
) -> LoadedAttachment:
    try:
        slot_metadata = lupus.attachment.slots[slot]
    except IndexError as error:
        raise KeyError(f"DogGun slot {slot} is outside 0..8.") from error
    if slot_metadata.slot != slot:
        raise KeyError(f"DogGun slot {slot} is unavailable.")
    if props_dir is None and lupus.prop_path is None:
        _source, _path, data = _load_prop_input(None, lupus.rom_source, slot_metadata.prop_id)
    else:
        source_dir = lupus.prop_path.parent if props_dir is None else Path(props_dir).resolve(strict=True)
        candidates = sorted(source_dir.glob(f"{slot_metadata.prop_id:04d}_*.bin"))
        if len(candidates) != 1:
            raise FileNotFoundError(
                f"Expected one Prop {slot_metadata.prop_id} binary in {source_dir}; found {len(candidates)}."
            )
        data = candidates[0].read_bytes()
    model = _normalize_model(
        slot_metadata.prop_id,
        data,
        parse_model(data),
        lupus.raw_rom,
        lupus.texture_manifest_path,
    )
    if model.name != slot_metadata.name or model.active_face_count != slot_metadata.expected_active_faces:
        raise BoyExportError(f"DogGun slot {slot} model identity or face count differs.")
    return LoadedAttachment(lupus.attachment, slot_metadata, model)


__all__ = [
    "DOGGUN_ATTACHMENT",
    "LUPUS_PROP_ID",
    "load_lupus",
    "load_lupus_attachment",
    "sample_lupus_animation",
]
