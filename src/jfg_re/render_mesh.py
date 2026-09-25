"""Shared renderer-neutral rigid assignment and corner expansion."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from jfg_re.boy_export import BoyExportError, BoyModel, _cross, _matrix_id
from jfg_re.forge_types import RenderMesh, RenderPrimitive, RenderVertex


def rigid_matrix_assignments(model: BoyModel) -> dict[int, int]:
    """Return the verified one-matrix assignment for active source vertices."""
    result: dict[int, int] = {}
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        for vertex_index in range(group.vertex_start, following.vertex_start):
            matrix_id = _matrix_id(group, vertex_index - group.vertex_start)
            if matrix_id is None:
                raise BoyExportError("Active model vertex has no matrix assignment.")
            if vertex_index in result and result[vertex_index] != matrix_id:
                raise BoyExportError("Active model vertex has conflicting matrix assignments.")
            result[vertex_index] = matrix_id
    return result


def expand_render_mesh(
    model: BoyModel,
    assignments: Mapping[int, int],
    texture_dimensions: Mapping[int, tuple[int, int] | None],
    *,
    exclude_degenerate: bool = False,
) -> RenderMesh:
    """Expand JFG per-corner data without introducing a file-format layer.

    Ordering matches the existing Boy glTF exporter: material keys are sorted
    by texture index and triangle bit 0x40, while triangles retain source order
    inside each key.
    """
    buckets: defaultdict[tuple[int, bool], list[tuple[object, object]]] = defaultdict(list)
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            if exclude_degenerate:
                points = tuple(
                    (
                        model.vertices[group.vertex_start + local].x,
                        model.vertices[group.vertex_start + local].y,
                        model.vertices[group.vertex_start + local].z,
                    )
                    for local in triangle.local_indices
                )
                if _cross(points) == (0, 0, 0):
                    continue
            buckets[(group.texture_index, bool(triangle.flag & 0x40))].append((group, triangle))

    vertices: list[RenderVertex] = []
    primitives: list[RenderPrimitive] = []
    for material_index, key in enumerate(sorted(buckets)):
        texture_index_raw, double_sided = key
        texture_index = None if texture_index_raw == 0xFF else texture_index_raw
        dimensions = None if texture_index is None else texture_dimensions.get(texture_index)
        first = len(vertices)
        group_ids: set[int] = set()
        for group, triangle in buckets[key]:
            group_ids.add(group.index)
            for local, raw_st in zip(triangle.local_indices, triangle.corner_pairs):
                source = group.vertex_start + local
                if source not in assignments:
                    raise BoyExportError(f"Active source vertex {source} has no rigid matrix assignment.")
                vertex = model.vertices[source]
                uv = None
                if dimensions is not None:
                    width, height = dimensions
                    if width <= 0 or height <= 0:
                        raise BoyExportError("Verified texture dimensions must be positive.")
                    raw_s, raw_t = raw_st
                    uv = (raw_s / (32 * width), 1.0 - raw_t / (32 * height))
                vertices.append(
                    RenderVertex(
                        position=(float(vertex.x), float(vertex.y), float(vertex.z)),
                        uv=uv,
                        raw_st=raw_st,
                        source_vertex_index=source,
                        joint_id=assignments[source],
                        group_index=group.index,
                        triangle_index=triangle.index,
                    )
                )
        count = len(vertices) - first
        primitives.append(
            RenderPrimitive(
                material_index=material_index,
                texture_index=texture_index,
                double_sided=double_sided,
                first_index=first,
                index_count=count,
                group_indices=tuple(sorted(group_ids)),
            )
        )
    return RenderMesh(tuple(vertices), tuple(range(len(vertices))), tuple(primitives))
