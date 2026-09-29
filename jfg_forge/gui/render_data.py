"""Qt/OpenGL-free preparation of one static JFG Forge scene for rendering."""

from __future__ import annotations

from dataclasses import dataclass, replace

from jfg_forge.core.scene import evaluate_attachment_positions, evaluate_rigid_mesh_positions
from jfg_forge.core.roster import ROSTER
from jfg_forge.core.asset_types import BoySceneSnapshot, EvidenceStatus, ModelAsset, SceneAttachment
from jfg_forge.core.rdp_material import primitive_material_state


NEUTRAL_FALLBACK_RGBA = (0.55, 0.55, 0.55, 1.0)


@dataclass(frozen=True)
class PreparedTexture:
    texture_index: int
    width: int
    height: int
    rgba: bytes
    wrap_s: str
    wrap_t: str


@dataclass(frozen=True)
class PreparedBatch:
    first_vertex: int
    vertex_count: int
    texture_index: int | None
    double_sided: bool
    uses_verified_texture: bool
    fallback_rgba: tuple[float, float, float, float]
    fallback_reason: str | None
    alpha_mode: str = "OPAQUE"
    depth_write: bool = True
    depth_compare: bool = True
    z_mode: int = 0

    @property
    def face_count(self) -> int:
        return self.vertex_count // 3


@dataclass(frozen=True)
class PreparedRenderData:
    positions: tuple[tuple[float, float, float], ...]
    uvs: tuple[tuple[float, float], ...]
    batches: tuple[PreparedBatch, ...]
    textures: tuple[PreparedTexture, ...]
    bounds_minimum: tuple[float, float, float]
    bounds_maximum: tuple[float, float, float]


@dataclass(frozen=True)
class ModelInformation:
    name: str | None
    prop_id: int
    source_vertices: int
    render_vertices: int
    faces: int
    groups: int
    joints: int
    verified_textures: int
    unknown_textures: int
    attachment_status: str


def _wrap_name(axis: object) -> str:
    if not isinstance(axis, dict):
        return "REPEAT"
    if axis.get("clamp"):
        return "CLAMP"
    if axis.get("mirror"):
        return "MIRROR"
    return "REPEAT"


def _prepare_model_render_data(
    model: ModelAsset,
    positions: tuple[tuple[float, float, float], ...],
) -> PreparedRenderData:
    texture_by_index = {texture.texture_index: texture for texture in model.textures}
    prepared_textures: list[PreparedTexture] = []
    for texture in model.textures:
        if not texture.supported:
            continue
        sampler = texture.sampler or {}
        prepared_textures.append(
            PreparedTexture(
                texture_index=texture.texture_index,
                width=texture.width,
                height=texture.height,
                rgba=texture.rgba,
                wrap_s=_wrap_name(sampler.get("cms")),
                wrap_t=_wrap_name(sampler.get("cmt")),
            )
        )

    uvs: list[tuple[float, float]] = []
    for vertex in model.render_mesh.vertices:
        uvs.append((0.0, 0.0) if vertex.uv is None else vertex.uv)

    batches: list[PreparedBatch] = []
    for primitive in model.render_mesh.primitives:
        texture = None if primitive.texture_index is None else texture_by_index[primitive.texture_index]
        verified = bool(texture and texture.supported)
        if primitive.texture_index is None:
            reason = "no texture assigned"
        elif not verified:
            reason = "UNKNOWN texture format"
        else:
            reason = None
        material_state = primitive_material_state(model, primitive)
        batches.append(
            PreparedBatch(
                first_vertex=primitive.first_index,
                vertex_count=primitive.index_count,
                texture_index=primitive.texture_index if verified else None,
                double_sided=primitive.double_sided,
                uses_verified_texture=verified,
                fallback_rgba=NEUTRAL_FALLBACK_RGBA,
                fallback_reason=reason,
                alpha_mode="OPAQUE" if material_state is None else material_state.preview_alpha_mode(
                    None if texture is None or not texture.supported else texture.rgba
                ),
                depth_write=True if material_state is None else material_state.depth_write,
                depth_compare=True if material_state is None else material_state.depth_compare,
                z_mode=0 if material_state is None else material_state.z_mode,
            )
        )

    minimum = tuple(min(point[axis] for point in positions) for axis in range(3))
    maximum = tuple(max(point[axis] for point in positions) for axis in range(3))
    return PreparedRenderData(
        positions=positions,
        uvs=tuple(uvs),
        batches=tuple(batches),
        textures=tuple(prepared_textures),
        bounds_minimum=minimum,
        bounds_maximum=maximum,
    )


def depth_comparison_for_batch(batch: PreparedBatch) -> str:
    """Coincident ZMODE_DEC overlays must pass their underlying surface depth."""
    return "LEQUAL" if batch.z_mode == 3 else "LESS"


def ordered_draw_batches(
    scenes: tuple[PreparedRenderData, ...],
    view_matrix: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[int, PreparedBatch], ...]:
    """Opaque, then depth-neutral decals, then blended back to front."""
    sortable: list[tuple[int, float, int, int, PreparedBatch]] = []
    view_z = view_matrix[2]
    for scene_index, scene in enumerate(scenes):
        for batch in scene.batches:
            if batch.alpha_mode == "BLEND":
                phase = 2
                positions = scene.positions[batch.first_vertex : batch.first_vertex + batch.vertex_count]
                camera_z = sum(
                    view_z[0] * p[0] + view_z[1] * p[1] + view_z[2] * p[2] + view_z[3]
                    for p in positions
                ) / len(positions)
            else:
                phase = 0 if batch.depth_write else 1
                camera_z = 0.0
            sortable.append((phase, camera_z, scene_index, batch.first_vertex, batch))
    sortable.sort(key=lambda item: item[:4])
    return tuple((scene_index, batch) for _, _, scene_index, _, batch in sortable)


def with_render_positions(
    data: PreparedRenderData,
    positions: tuple[tuple[float, float, float], ...],
) -> PreparedRenderData:
    """Keep CPU draw ordering on the same animated positions uploaded to the VBO."""
    if len(positions) != len(data.positions):
        raise ValueError("Animated position count differs from the loaded render mesh.")
    return replace(data, positions=positions)


def prepare_render_data(scene: BoySceneSnapshot) -> PreparedRenderData:
    """Prepare static CPU-evaluated character geometry and material batches."""
    positions = evaluate_rigid_mesh_positions(scene.model.render_mesh, scene.pose)
    return _prepare_model_render_data(scene.model, positions)


def prepare_attachment_render_data(attachment: SceneAttachment) -> PreparedRenderData:
    """Prepare one selected attachment using its composed scene transform."""
    positions = evaluate_attachment_positions(attachment)
    return _prepare_model_render_data(attachment.attachment.model, positions)


_CAMPAIGN_ATTACHMENT_STATUS = {
    218: "GirlGun matrix 6 placement VERIFIED",
    219: "GirlGun matrix 6 placement VERIFIED",
    220: "matrix 6 placement VERIFIED",
    221: "matrix 6 placement VERIFIED",
    222: "DogGun matrix 16 placement VERIFIED",
    223: "DogGun matrix 7 placement VERIFIED",
}


def _attachment_status(prop_id: int) -> str:
    if prop_id in _CAMPAIGN_ATTACHMENT_STATUS:
        return _CAMPAIGN_ATTACHMENT_STATUS[prop_id]
    for spec in ROSTER:
        if spec.compact and spec.prop_id == prop_id:
            attachment = spec.attachment
            if not attachment.slots:
                return "no attachment"
            return f"{attachment.name} matrix {attachment.attachment_joint_id} placement {attachment.status}"
    return "attachment placement UNKNOWN"


def model_information(scene: BoySceneSnapshot) -> ModelInformation:
    model = scene.model
    skeleton = model.skeleton
    attachment_status = _attachment_status(model.prop_id)
    return ModelInformation(
        name=model.name,
        prop_id=model.prop_id,
        source_vertices=len(model.source_vertices),
        render_vertices=len(model.render_mesh.vertices),
        faces=model.active_face_count,
        groups=len(model.groups),
        joints=0 if skeleton is None else len(skeleton.joints),
        verified_textures=sum(texture.status is EvidenceStatus.VERIFIED for texture in model.textures),
        unknown_textures=sum(texture.status is EvidenceStatus.UNKNOWN for texture in model.textures),
        attachment_status=attachment_status,
    )


__all__ = [
    "ModelInformation",
    "NEUTRAL_FALLBACK_RGBA",
    "PreparedBatch",
    "PreparedRenderData",
    "PreparedTexture",
    "model_information",
    "prepare_attachment_render_data",
    "prepare_render_data",
]
