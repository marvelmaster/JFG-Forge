"""Generic loader for characters that use the compact 16-byte transform layout.

Every playable model beyond the six campaign characters (multiplayer ants,
tribals, bugs, cyborg, zombie and the hover ships) shares the rig, animation and
attachment machinery already verified for Juno, Vela, Lupus and PowerDog.  A
``CharacterSpec`` (see ``roster``) supplies the pins that make each model
explicit: Prop ID and SHA-256, joint count, clip count and IDs, active faces.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from types import MappingProxyType
from typing import TYPE_CHECKING

from jfg_forge.core.asset_types import (
    AnimationClip,
    BoyAsset,
    Joint,
    JointPose,
    Pose,
    Skeleton,
)
from jfg_forge.core.character_data import _load_prop_input, _matrix4, _normalize_model
from jfg_forge.core.compact_animation import (
    build_compact_matrices,
    catalog_compact_animations,
    compact_animation_tables,
    decode_vela_animation_time,
)
from jfg_forge.core.model_parser import BoyExportError, parse_model
from jfg_forge.core.rom_source import RomSource

if TYPE_CHECKING:
    from jfg_forge.core.roster import CharacterSpec


CLIP_INDEX_KEY = "compact_animation_index"
TIMING_FAMILY_KEY = "compact_timing_family"


def _load_skeleton(data: bytes, spec: "CharacterSpec") -> Skeleton:
    start = struct.unpack_from(">I", data, 0x54)[0]
    count = data[0x4F]
    if count != spec.transform_count:
        raise BoyExportError(
            f"{spec.file_name} transform count is {count}, expected {spec.transform_count}."
        )
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
        raise BoyExportError(f"{spec.file_name} skeleton matrix IDs are not exactly 0..{count - 1}.")
    roots = tuple(joint.joint_id for joint in joints if joint.parent_id is None)
    if len(roots) != 1:
        raise BoyExportError(f"{spec.file_name} skeleton must have exactly one root joint.")
    return Skeleton(joints=joints, root_joint_id=roots[0])


def _load_animations(rom: bytes, spec: "CharacterSpec") -> tuple[AnimationClip, ...]:
    catalog = catalog_compact_animations(
        rom,
        prop_id=spec.prop_id,
        transform_count=spec.transform_count,
        expected_animation_count=spec.clip_count,
        label=spec.file_name,
        index_key=CLIP_INDEX_KEY,
    )
    tables = compact_animation_tables(
        rom,
        prop_id=spec.prop_id,
        transform_count=spec.transform_count,
        expected_animation_count=spec.clip_count,
        label=spec.file_name,
    )
    clips = []
    for record in catalog["animations"]:
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        metadata = dict(record)
        metadata[TIMING_FAMILY_KEY] = spec.timing_family
        clips.append(
            AnimationClip(
                animation_index=record[CLIP_INDEX_KEY],
                animation_id=record["animation_id"],
                sample_count=record["sample_count"],
                loop=record["loop_enabled"],
                channel_map=tuple(record["channel_map"]),
                blob=tables["asset43"][start:end],
                metadata=MappingProxyType(metadata),
            )
        )
    if tuple(clip.animation_index for clip in clips) != tuple(range(spec.clip_count)):
        raise BoyExportError(
            f"{spec.file_name} animation catalog is not the expected contiguous 0..{spec.clip_count - 1} range."
        )
    # The timing and weapon conclusions for a family rest on these IDs being
    # the base character's IDs, so a mismatch must stop the load.
    if tuple(clip.animation_id for clip in clips) != tuple(spec.clip_ids):
        raise BoyExportError(f"{spec.file_name} animation IDs differ from the pinned list.")
    return tuple(clips)


def load_compact_character(
    spec: "CharacterSpec",
    rom_path: RomSource | Path,
    texture_manifest_path: Path | None = None,
    prop_path: Path | None = None,
) -> BoyAsset:
    """Load one roster entry with its model, rig, clips and attachment definition."""
    source, prop_path, data = _load_prop_input(prop_path, rom_path, spec.prop_id)
    texture_manifest_path = (
        None if texture_manifest_path is None else Path(texture_manifest_path).resolve(strict=True)
    )
    if hashlib.sha256(data).hexdigest() != spec.prop_sha256:
        raise BoyExportError(
            f"Input is not the pinned US Prop {spec.prop_id} {spec.model_name} binary."
        )
    rom = source.data
    model = _normalize_model(
        spec.prop_id,
        data,
        parse_model(data),
        rom,
        texture_manifest_path,
        skeleton=_load_skeleton(data, spec),
    )
    if model.active_face_count != spec.active_faces:
        raise BoyExportError(
            f"{spec.file_name} active face count is {model.active_face_count}, expected {spec.active_faces}."
        )
    return BoyAsset(
        model=model,
        animations=_load_animations(rom, spec),
        attachment=spec.attachment,
        rom_path=source.path,
        prop_path=prop_path,
        texture_manifest_path=texture_manifest_path,
        raw_rom=rom,
        raw_prop=data,
        rom_source=source,
    )


def sample_compact_animation(character: BoyAsset, animation_index: int, time: float) -> Pose:
    clip = character.animation(animation_index)
    lookahead = bytes.fromhex(str(clip.metadata.get("cross_blob_lookahead_hex", "")))
    frame = decode_vela_animation_time(clip.blob, time, lookahead)
    matrices = build_compact_matrices(
        character.raw_prop,
        frame,
        character.raw_rom,
        list(clip.channel_map),
        transform_count=len(character.model.skeleton.joints),
        label=character.model.name,
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


__all__ = [
    "CLIP_INDEX_KEY",
    "TIMING_FAMILY_KEY",
    "load_compact_character",
    "sample_compact_animation",
]
