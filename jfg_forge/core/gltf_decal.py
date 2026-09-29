"""Export-only depth separation for evidenced, coplanar model decals.

glTF has no equivalent of JFG's decal Z mode.  This module changes only the
corner-expanded POSITION values emitted by glTF exporters; model and Forge
geometry remain untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Sequence

from jfg_forge.core.rdp_material import ModelMaterialState


_OFFSET_FRACTION_OF_DIAGONAL = 1.0 / 2048.0
_ZERO = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class GltfDecalPlan:
    vertex_offsets: tuple[tuple[float, float, float], ...]
    displaced_faces: tuple[int, ...]
    distance: float


def _face_key(corners: Sequence[Any]) -> tuple[tuple[tuple[float, float, float], int], ...]:
    return tuple(sorted((tuple(corner.position), corner.joint_id) for corner in corners))


def plan_gltf_decal_offsets(
    render_mesh: Any,
    states: Sequence[ModelMaterialState | None],
    rgba_by_primitive: Sequence[bytes | None],
) -> GltfDecalPlan:
    """Offset only binary-alpha decal faces exactly duplicated by opaque bases.

    The corner order determines the visible-side local normal. The same tiny
    displacement is applied to all three corners, including faces spanning
    multiple rigid joints; their original joint IDs remain unchanged.
    """
    primitives = render_mesh.primitives
    vertices = render_mesh.vertices
    if len(states) != len(primitives) or len(rgba_by_primitive) != len(primitives):
        raise ValueError("Decal state/texture list does not match render primitives.")
    if not vertices:
        return GltfDecalPlan((), (0,) * len(primitives), 0.0)

    axes = [tuple(vertex.position[axis] for vertex in vertices) for axis in range(3)]
    diagonal = sqrt(sum((max(axis) - min(axis)) ** 2 for axis in axes))
    distance = diagonal * _OFFSET_FRACTION_OF_DIAGONAL
    base_faces: set[tuple[tuple[tuple[float, float, float], int], ...]] = set()
    for primitive, state in zip(primitives, states):
        if state is None or state.z_mode != 0 or not state.depth_write:
            continue
        for start in range(primitive.first_index, primitive.first_index + primitive.index_count, 3):
            base_faces.add(_face_key(vertices[start:start + 3]))

    offsets = [_ZERO] * len(vertices)
    displaced = [0] * len(primitives)
    for primitive_index, (primitive, state, rgba) in enumerate(
        zip(primitives, states, rgba_by_primitive)
    ):
        if state is None or state.z_mode != 3 or state.preview_alpha_mode(rgba) != "MASK":
            continue
        for start in range(primitive.first_index, primitive.first_index + primitive.index_count, 3):
            corners = vertices[start:start + 3]
            if _face_key(corners) not in base_faces:
                continue
            a, b, c = (v.position for v in corners)
            ab = tuple(b[i] - a[i] for i in range(3))
            ac = tuple(c[i] - a[i] for i in range(3))
            normal = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            length = sqrt(sum(component * component for component in normal))
            if length == 0:
                continue
            delta = tuple(component * distance / length for component in normal)
            offsets[start:start + 3] = [delta, delta, delta]
            displaced[primitive_index] += 1
    return GltfDecalPlan(tuple(offsets), tuple(displaced), distance)
