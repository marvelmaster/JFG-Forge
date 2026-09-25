"""Renderer-neutral typed assets for JFG Forge and other consumers.

The types in this module deliberately contain no Qt, OpenGL, glTF, Blender,
or exporter-specific values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping


Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


class EvidenceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    LIKELY = "LIKELY"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceVertex:
    index: int
    position: tuple[int, int, int]
    f3ddkr_attributes: tuple[int, int, int, int]


@dataclass(frozen=True)
class ModelGroup:
    index: int
    texture_index: int
    matrix_ids: tuple[int, int, int]
    matrix_splits: tuple[int, int]
    vertex_range: tuple[int, int]
    triangle_range: tuple[int, int]
    render_flags: int
    runtime_skipped: bool


@dataclass(frozen=True)
class TextureAsset:
    texture_index: int
    texture_id: int
    status: EvidenceStatus
    width: int | None
    height: int | None
    rgba: bytes | None
    decoder_id: str | None
    rom_offset: int
    header: bytes
    sampler: Mapping[str, Any] | None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def supported(self) -> bool:
        return self.status is EvidenceStatus.VERIFIED and self.rgba is not None


@dataclass(frozen=True)
class MaterialAsset:
    index: int
    texture_index: int | None
    texture_id: int | None
    texture_status: EvidenceStatus | None
    double_sided: bool
    confidence: EvidenceStatus = EvidenceStatus.VERIFIED


@dataclass(frozen=True)
class RenderVertex:
    position: tuple[float, float, float]
    uv: tuple[float, float] | None
    raw_st: tuple[int, int]
    source_vertex_index: int
    joint_id: int
    group_index: int
    triangle_index: int


@dataclass(frozen=True)
class RenderPrimitive:
    material_index: int
    texture_index: int | None
    double_sided: bool
    first_index: int
    index_count: int
    group_indices: tuple[int, ...]

    @property
    def face_count(self) -> int:
        return self.index_count // 3


@dataclass(frozen=True)
class RenderMesh:
    vertices: tuple[RenderVertex, ...]
    indices: tuple[int, ...]
    primitives: tuple[RenderPrimitive, ...]

    @property
    def face_count(self) -> int:
        return len(self.indices) // 3


@dataclass(frozen=True)
class Joint:
    joint_id: int
    parent_id: int | None
    name: str
    static_local_translation: tuple[float, float, float]
    record_index: int


@dataclass(frozen=True)
class Skeleton:
    joints: tuple[Joint, ...]
    root_joint_id: int
    matrix_convention: str = "JFG row-vector; child_world = child_local * parent_world"


@dataclass(frozen=True)
class AnimationClip:
    animation_index: int
    animation_id: int
    sample_count: int
    loop: bool
    channel_map: tuple[int, ...]
    blob: bytes = field(repr=False)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    name: None = None


@dataclass(frozen=True)
class JointPose:
    joint_id: int
    parent_id: int | None
    local_matrix: Matrix4
    world_matrix: Matrix4


@dataclass(frozen=True)
class Pose:
    animation_index: int
    animation_id: int
    time: float
    current_sample: int
    next_sample: int
    fraction_10bit: int
    root_translation: tuple[float, float, float]
    root_translation_raw_q10: tuple[int, int, int]
    joints: tuple[JointPose, ...]
    matrix_convention: str = "JFG row-vector; child_world = child_local * parent_world"


@dataclass(frozen=True)
class ModelAsset:
    prop_id: int
    name: str | None
    source_vertices: tuple[SourceVertex, ...]
    groups: tuple[ModelGroup, ...]
    render_mesh: RenderMesh
    materials: tuple[MaterialAsset, ...]
    textures: tuple[TextureAsset, ...]
    rigid_joint_assignments: Mapping[int, int]
    skeleton: Skeleton | None = None
    confidence: EvidenceStatus = EvidenceStatus.VERIFIED

    @property
    def active_face_count(self) -> int:
        return self.render_mesh.face_count


@dataclass(frozen=True)
class AttachmentSlot:
    slot: int
    prop_id: int
    name: str
    expected_active_faces: int


@dataclass(frozen=True)
class AttachmentDefinition:
    name: str
    object_definition_id: int
    attachment_joint_id: int
    slots: tuple[AttachmentSlot, ...]
    status: EvidenceStatus


@dataclass(frozen=True)
class LoadedAttachment:
    definition: AttachmentDefinition
    slot: AttachmentSlot
    model: ModelAsset


@dataclass(frozen=True)
class BoyAsset:
    model: ModelAsset
    animations: tuple[AnimationClip, ...]
    attachment: AttachmentDefinition
    rom_path: Path
    prop_path: Path
    texture_manifest_path: Path
    raw_rom: bytes = field(repr=False)
    raw_prop: bytes = field(repr=False)

    def animation(self, animation_index: int) -> AnimationClip:
        try:
            clip = self.animations[animation_index]
        except IndexError as error:
            raise KeyError(f"Boy animation index {animation_index} is unavailable.") from error
        if clip.animation_index != animation_index:
            raise KeyError(f"Boy animation index {animation_index} is unavailable.")
        return clip


@dataclass(frozen=True)
class SkeletonDebugJoint:
    joint_id: int
    parent_id: int | None
    position: tuple[float, float, float]


@dataclass(frozen=True)
class SkeletonDebugEdge:
    parent_joint_id: int
    child_joint_id: int
    start: tuple[float, float, float]
    end: tuple[float, float, float]


@dataclass(frozen=True)
class SkeletonDebugData:
    joints: tuple[SkeletonDebugJoint, ...]
    edges: tuple[SkeletonDebugEdge, ...]


@dataclass(frozen=True)
class SceneAttachment:
    attachment: LoadedAttachment
    parent_joint_id: int
    socket_world_matrix: Matrix4
    local_transform: Matrix4 | None
    final_world_transform: Matrix4 | None
    transform_status: EvidenceStatus
    unresolved_reason: str | None

    @property
    def exact_transform_available(self) -> bool:
        return self.final_world_transform is not None


@dataclass(frozen=True)
class BoySceneSnapshot:
    model: ModelAsset
    pose: Pose
    joint_world_matrices: tuple[Matrix4, ...]
    skeleton_debug: SkeletonDebugData
    attachment: SceneAttachment | None
