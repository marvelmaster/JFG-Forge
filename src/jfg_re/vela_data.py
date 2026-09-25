"""Renderer-neutral production API for Vela / Girl / Prop 218."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from jfg_re.boy_export import BoyExportError, parse_model
from jfg_re.forge_data import _matrix4, _normalize_model
from jfg_re.forge_types import (
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
from jfg_re.props import validate_rom_identity
from jfg_re.vela_animation import (
    _animation_blob,
    _tables,
    build_vela_matrices,
    catalog_vela_animations,
    decode_vela_animation_time,
)


VELA_PROP_ID = 218
VELA_PROP_SHA256 = "daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409"
VELA_TRANSFORM_COUNT = 28

GIRLGUN_ATTACHMENT = AttachmentDefinition(
    name="GirlGun",
    object_definition_id=397,
    attachment_joint_id=6,
    slots=(
        AttachmentSlot(0, 283, "Pistol", 67),
        AttachmentSlot(1, 284, "Automatic", 116),
        AttachmentSlot(2, 285, "Uzi", 126),
        AttachmentSlot(3, 286, "Uzi1", 106),
        AttachmentSlot(4, 287, "ShrinkBeam", 110),
        AttachmentSlot(5, 288, "Rocket", 142),
        AttachmentSlot(6, 289, "FlameThrower", 132),
        AttachmentSlot(7, 290, "Sniper", 245),
        AttachmentSlot(8, 291, "VelaHand", 32),
    ),
    status=EvidenceStatus.VERIFIED,
)


def _load_skeleton(data: bytes) -> Skeleton:
    start = struct.unpack_from(">I", data, 0x54)[0]
    count = data[0x4F]
    if count != VELA_TRANSFORM_COUNT:
        raise BoyExportError(f"Vela transform count is {count}, expected 28.")
    joints = []
    for record_index in range(count):
        offset = start + record_index * 16
        parent_id, joint_id = data[offset], data[offset + 1]
        joints.append(
            Joint(
                joint_id=joint_id,
                parent_id=None if parent_id == 0xFF else parent_id,
                name=f"jfg_node_{joint_id:02d}",
                static_local_translation=struct.unpack_from(">fff", data, offset + 4),
                record_index=record_index,
            )
        )
    result = tuple(joints)
    if tuple(joint.joint_id for joint in result) != tuple(range(VELA_TRANSFORM_COUNT)):
        raise BoyExportError("Vela skeleton matrix IDs are not exactly 0..27.")
    roots = tuple(joint.joint_id for joint in result if joint.parent_id is None)
    if len(roots) != 1:
        raise BoyExportError("Vela skeleton must have exactly one root joint.")
    return Skeleton(joints=result, root_joint_id=roots[0])


def _load_animations(rom: bytes) -> tuple[AnimationClip, ...]:
    catalog = catalog_vela_animations(rom)
    tables = _tables(rom)
    clips = []
    for record in catalog["animations"]:
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        metadata = dict(record)
        clips.append(
            AnimationClip(
                animation_index=record["vela_animation_index"],
                animation_id=record["animation_id"],
                sample_count=record["sample_count"],
                loop=record["loop_enabled"],
                channel_map=tuple(record["channel_map"]),
                blob=tables["asset43"][start:end],
                metadata=MappingProxyType(metadata),
            )
        )
    if tuple(clip.animation_index for clip in clips) != tuple(range(53)):
        raise BoyExportError("Vela animation catalog is not the expected contiguous 0..52 range.")
    return tuple(clips)


def load_vela(prop_path: Path, rom_path: Path, texture_manifest_path: Path) -> BoyAsset:
    """Load Prop 218, its verified textures, 28-joint skeleton and 53 clips."""
    identity = validate_rom_identity(Path(rom_path))
    prop_path = Path(prop_path).resolve(strict=True)
    texture_manifest_path = Path(texture_manifest_path).resolve(strict=True)
    data = prop_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != VELA_PROP_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 218 Girl binary.")
    rom = identity.path.read_bytes()
    model = _normalize_model(
        VELA_PROP_ID,
        data,
        parse_model(data),
        rom,
        texture_manifest_path,
        skeleton=_load_skeleton(data),
    )
    if model.active_face_count != 452:
        raise BoyExportError(f"Vela active face count is {model.active_face_count}, expected 452.")
    return BoyAsset(
        model=model,
        animations=_load_animations(rom),
        attachment=GIRLGUN_ATTACHMENT,
        rom_path=identity.path,
        prop_path=prop_path,
        texture_manifest_path=texture_manifest_path,
        raw_rom=rom,
        raw_prop=data,
    )


def sample_vela_animation(vela: BoyAsset, animation_index: int, time: float) -> Pose:
    clip = vela.animation(animation_index)
    lookahead = bytes.fromhex(str(clip.metadata.get("cross_blob_lookahead_hex", "")))
    frame = decode_vela_animation_time(clip.blob, time, lookahead)
    matrices = build_vela_matrices(
        vela.raw_prop,
        frame,
        vela.raw_rom,
        list(clip.channel_map),
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


def load_vela_attachment(
    vela: BoyAsset,
    *,
    slot: int,
    props_dir: Path | None = None,
) -> LoadedAttachment:
    try:
        slot_metadata = vela.attachment.slots[slot]
    except IndexError as error:
        raise KeyError(f"GirlGun slot {slot} is outside 0..8.") from error
    if slot_metadata.slot != slot:
        raise KeyError(f"GirlGun slot {slot} is unavailable.")
    source_dir = vela.prop_path.parent if props_dir is None else Path(props_dir).resolve(strict=True)
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
        vela.raw_rom,
        vela.texture_manifest_path,
    )
    if model.name != slot_metadata.name or model.active_face_count != slot_metadata.expected_active_faces:
        raise BoyExportError(f"GirlGun slot {slot} model identity or face count differs.")
    return LoadedAttachment(vela.attachment, slot_metadata, model)


__all__ = [
    "GIRLGUN_ATTACHMENT",
    "VELA_PROP_ID",
    "load_vela",
    "load_vela_attachment",
    "sample_vela_animation",
]
