"""Headless Boy/Juno scene and pose composition for JFG Forge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jfg_re.boy_anim0_frame0 import _transform
from jfg_re.boy_export import BoyExportError
from jfg_re.forge_data import load_boy_attachment, sample_animation
from jfg_re.vela_data import load_vela_attachment, sample_vela_animation
from jfg_re.forge_types import (
    BoyAsset,
    BoySceneSnapshot,
    EvidenceStatus,
    LoadedAttachment,
    Pose,
    RenderMesh,
    SceneAttachment,
    SkeletonDebugData,
    SkeletonDebugEdge,
    SkeletonDebugJoint,
)


@dataclass(frozen=True)
class _Point:
    x: float
    y: float
    z: float


def evaluate_rigid_mesh_positions(
    render_mesh: RenderMesh,
    pose: Pose,
) -> tuple[tuple[float, float, float], ...]:
    """Evaluate corner-expanded vertices with the verified JFG row-vector path.

    This is a CPU reference for later shader validation. It intentionally calls
    the existing verified point transform rather than introducing new matrix
    arithmetic.
    """
    matrices = {joint.joint_id: joint.world_matrix for joint in pose.joints}
    result: list[tuple[float, float, float]] = []
    for vertex in render_mesh.vertices:
        try:
            matrix = matrices[vertex.joint_id]
        except KeyError as error:
            raise BoyExportError(
                f"Render vertex references matrix {vertex.joint_id}, absent from the pose."
            ) from error
        transformed, _ = _transform(_Point(*vertex.position), matrix)
        result.append(tuple(transformed))
    return tuple(result)


def build_skeleton_debug_data(pose: Pose) -> SkeletonDebugData:
    """Build evaluated joint points and parent-child line segments."""
    joints = tuple(
        SkeletonDebugJoint(
            joint_id=joint.joint_id,
            parent_id=joint.parent_id,
            position=tuple(joint.world_matrix[3][:3]),
        )
        for joint in pose.joints
    )
    by_id = {joint.joint_id: joint for joint in joints}
    edges: list[SkeletonDebugEdge] = []
    for joint in joints:
        if joint.parent_id is None:
            continue
        try:
            parent = by_id[joint.parent_id]
        except KeyError as error:
            raise BoyExportError(
                f"Skeleton debug joint {joint.joint_id} has absent parent {joint.parent_id}."
            ) from error
        edges.append(
            SkeletonDebugEdge(
                parent_joint_id=parent.joint_id,
                child_joint_id=joint.joint_id,
                start=parent.position,
                end=joint.position,
            )
        )
    return SkeletonDebugData(joints=joints, edges=tuple(edges))


def _compose_attachment(
    character: BoyAsset,
    pose: Pose,
    attachment: LoadedAttachment,
) -> SceneAttachment:
    parent_joint_id = character.attachment.attachment_joint_id
    if attachment.definition != character.attachment:
        raise BoyExportError("Loaded attachment does not belong to the character's attachment definition.")
    try:
        socket = next(joint.world_matrix for joint in pose.joints if joint.joint_id == parent_joint_id)
    except StopIteration as error:
        raise BoyExportError(f"Boy pose does not contain attachment matrix {parent_joint_id}.") from error

    # VERIFIED: objMakeGunMtx copies the selected 4x3 Boy matrix (matrix 6 for
    # Boy's first reference record) into a complete affine 4x4. Its subsequent
    # mathMtxXFMF call transforms a separate reference point into caller-owned
    # outputs; it does not mutate this matrix. The normal Boy path does not take
    # the object-type-0x33 translation override.
    identity: tuple[tuple[float, float, float, float], ...] = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return SceneAttachment(
        attachment=attachment,
        parent_joint_id=parent_joint_id,
        socket_world_matrix=socket,
        local_transform=identity,
        final_world_transform=socket,
        transform_status=EvidenceStatus.VERIFIED,
        unresolved_reason=None,
    )


def evaluate_attachment_positions(
    attachment: SceneAttachment,
) -> tuple[tuple[float, float, float], ...]:
    """Transform one loaded attachment through its verified scene transform."""
    if attachment.final_world_transform is None:
        raise BoyExportError("Attachment placement is not available.")
    result: list[tuple[float, float, float]] = []
    for vertex in attachment.attachment.model.render_mesh.vertices:
        transformed, _ = _transform(_Point(*vertex.position), attachment.final_world_transform)
        result.append(tuple(transformed))
    return tuple(result)


def compose_boy_scene(
    boy: BoyAsset,
    pose: Pose,
    *,
    attachment: LoadedAttachment | None = None,
) -> BoySceneSnapshot:
    """Compose an immutable scene snapshot from already loaded/evaluated data."""
    expected_joints = 0 if boy.model.skeleton is None else len(boy.model.skeleton.joints)
    if pose.animation_index < 0 or len(pose.joints) != expected_joints:
        raise BoyExportError(
            f"Character scene composition requires a complete {expected_joints}-joint pose."
        )
    world_matrices = tuple(joint.world_matrix for joint in pose.joints)
    scene_attachment = None if attachment is None else _compose_attachment(boy, pose, attachment)
    return BoySceneSnapshot(
        model=boy.model,
        pose=pose,
        joint_world_matrices=world_matrices,
        skeleton_debug=build_skeleton_debug_data(pose),
        attachment=scene_attachment,
    )


def evaluate_boy_scene(
    boy: BoyAsset,
    *,
    animation_index: int,
    time: float,
    attachment_slot: int | None = None,
    props_dir: Path | None = None,
    loaded_attachment: LoadedAttachment | None = None,
) -> BoySceneSnapshot:
    """Sample Boy and compose one renderer-neutral scene snapshot.

    ``loaded_attachment`` lets a future session cache asset loading between
    frames. When omitted, ``attachment_slot`` is loaded through the existing
    public BoyGun loader.
    """
    if loaded_attachment is not None and attachment_slot is not None:
        if loaded_attachment.slot.slot != attachment_slot:
            raise ValueError("loaded_attachment and attachment_slot select different slots.")
    attachment = loaded_attachment
    if attachment is None and attachment_slot is not None:
        attachment = load_boy_attachment(boy, slot=attachment_slot, props_dir=props_dir)
    pose = sample_animation(boy, animation_index, time)
    return compose_boy_scene(boy, pose, attachment=attachment)


def evaluate_vela_scene(
    vela: BoyAsset,
    *,
    animation_index: int,
    time: float,
    attachment_slot: int | None = None,
    props_dir: Path | None = None,
    loaded_attachment: LoadedAttachment | None = None,
) -> BoySceneSnapshot:
    """Sample Vela and compose one renderer-neutral scene snapshot."""
    if loaded_attachment is not None and attachment_slot is not None:
        if loaded_attachment.slot.slot != attachment_slot:
            raise ValueError("loaded_attachment and attachment_slot select different slots.")
    attachment = loaded_attachment
    if attachment is None and attachment_slot is not None:
        attachment = load_vela_attachment(vela, slot=attachment_slot, props_dir=props_dir)
    pose = sample_vela_animation(vela, animation_index, time)
    return compose_boy_scene(vela, pose, attachment=attachment)


__all__ = [
    "build_skeleton_debug_data",
    "compose_boy_scene",
    "evaluate_attachment_positions",
    "evaluate_boy_scene",
    "evaluate_vela_scene",
    "evaluate_rigid_mesh_positions",
]
