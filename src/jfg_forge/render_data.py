"""Qt/OpenGL-free preparation of one static JFG Forge scene for rendering."""

from __future__ import annotations

from dataclasses import dataclass

from jfg_re.forge_scene import evaluate_attachment_positions, evaluate_rigid_mesh_positions
from jfg_re.forge_types import BoySceneSnapshot, EvidenceStatus, ModelAsset, SceneAttachment


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
        batches.append(
            PreparedBatch(
                first_vertex=primitive.first_index,
                vertex_count=primitive.index_count,
                texture_index=primitive.texture_index if verified else None,
                double_sided=primitive.double_sided,
                uses_verified_texture=verified,
                fallback_rgba=NEUTRAL_FALLBACK_RGBA,
                fallback_reason=reason,
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


def prepare_render_data(scene: BoySceneSnapshot) -> PreparedRenderData:
    """Prepare static CPU-evaluated Boy geometry and material batches."""
    positions = evaluate_rigid_mesh_positions(scene.model.render_mesh, scene.pose)
    return _prepare_model_render_data(scene.model, positions)


def prepare_attachment_render_data(attachment: SceneAttachment) -> PreparedRenderData:
    """Prepare one selected BoyGun model using its composed scene transform."""
    positions = evaluate_attachment_positions(attachment)
    return _prepare_model_render_data(attachment.attachment.model, positions)


def model_information(scene: BoySceneSnapshot) -> ModelInformation:
    model = scene.model
    skeleton = model.skeleton
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
        attachment_status="matrix 6 placement VERIFIED",
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
