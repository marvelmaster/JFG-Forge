"""Renderer-neutral state and metadata for the Forge skeleton debug view."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jfg_re.forge_types import BoySceneSnapshot, SkeletonDebugData


JOINT_6_CONTEXT = "BoyGun attachment socket [VERIFIED]"


class ViewMode(StrEnum):
    MESH = "Mesh"
    SKELETON = "Skeleton"
    MESH_SKELETON = "Mesh + Skeleton"

    @property
    def shows_mesh(self) -> bool:
        return self in (ViewMode.MESH, ViewMode.MESH_SKELETON)

    @property
    def shows_skeleton(self) -> bool:
        return self in (ViewMode.SKELETON, ViewMode.MESH_SKELETON)


DEFAULT_VIEW_MODE = ViewMode.MESH_SKELETON


@dataclass(frozen=True)
class PreparedSkeletonDebug:
    joint_ids: tuple[int, ...]
    joint_positions: tuple[tuple[float, float, float], ...]
    edge_positions: tuple[tuple[float, float, float], ...]

    @property
    def joint_count(self) -> int:
        return len(self.joint_ids)

    @property
    def edge_count(self) -> int:
        return len(self.edge_positions) // 2

    def offset_for_joint(self, joint_id: int) -> int:
        try:
            return self.joint_ids.index(joint_id)
        except ValueError as error:
            raise KeyError(f"Skeleton debug data has no joint {joint_id}.") from error


@dataclass(frozen=True)
class SelectedJointInformation:
    joint_id: int
    parent_id: int | None
    evaluated_position: tuple[float, float, float]
    static_local_translation: tuple[float, float, float]
    rendered_corner_count: int
    rendered_source_vertex_count: int
    context: str | None

    @property
    def has_active_rendered_geometry(self) -> bool:
        return self.rendered_corner_count > 0


def prepare_skeleton_debug(data: SkeletonDebugData) -> PreparedSkeletonDebug:
    """Flatten already evaluated public debug data without rebuilding it."""
    return PreparedSkeletonDebug(
        joint_ids=tuple(joint.joint_id for joint in data.joints),
        joint_positions=tuple(joint.position for joint in data.joints),
        edge_positions=tuple(point for edge in data.edges for point in (edge.start, edge.end)),
    )


def selected_joint_information(scene: BoySceneSnapshot, joint_id: int) -> SelectedJointInformation:
    skeleton = scene.model.skeleton
    if skeleton is None:
        raise ValueError("The scene model has no skeleton metadata.")
    try:
        evaluated = next(joint for joint in scene.skeleton_debug.joints if joint.joint_id == joint_id)
        static = next(joint for joint in skeleton.joints if joint.joint_id == joint_id)
    except StopIteration as error:
        raise KeyError(f"Boy scene has no joint {joint_id}.") from error
    rendered_corner_count = 0
    rendered_source_vertices: set[int] = set()
    for vertex in scene.model.render_mesh.vertices:
        if vertex.joint_id == joint_id:
            rendered_corner_count += 1
            rendered_source_vertices.add(vertex.source_vertex_index)
    return SelectedJointInformation(
        joint_id=joint_id,
        parent_id=evaluated.parent_id,
        evaluated_position=evaluated.position,
        static_local_translation=static.static_local_translation,
        rendered_corner_count=rendered_corner_count,
        rendered_source_vertex_count=len(rendered_source_vertices),
        context=JOINT_6_CONTEXT if joint_id == 6 else None,
    )


__all__ = [
    "DEFAULT_VIEW_MODE",
    "JOINT_6_CONTEXT",
    "PreparedSkeletonDebug",
    "SelectedJointInformation",
    "ViewMode",
    "prepare_skeleton_debug",
    "selected_joint_information",
]
