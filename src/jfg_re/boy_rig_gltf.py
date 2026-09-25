"""Limited glTF rig validation artifact for Boy animations 0 and 43 only."""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_anim0_frame0 import _f32, _local_matrix_from_stored, _sine_table, _transform, build_matrices, locate_boy_animation0
from jfg_re.boy_anim0_temporal import decode_time as decode_anim0_time
import jfg_re.boy_animation_catalog as catalog_mod
from jfg_re.boy_export import BONE_COUNT, BONE_START, BOY_SHA256, BoyExportError, parse_boy, resolve_boy_textures
from jfg_re.boy_textured_export import _material_name, _tile_state
from jfg_re.props import validate_rom_identity
from jfg_re.render_mesh import expand_render_mesh, rigid_matrix_assignments


PROP_ID = 220
ANIMATION_SPECS = (
    {"index": 0, "id": 1026, "name": "boy_anim_00_id_1026", "loop": True},
    {"index": 43, "id": 1069, "name": "boy_anim_43_id_1069", "loop": False},
)
VALIDATION_TIMES = {0: (0.0, 1.0, 7.5, 8.0, 15.0), 43: (0.0, 1.0, 37.0, 37.5, 75.0)}
FLOAT_TOLERANCE = 1e-4
COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def _gltf_texcoord(render_uv: tuple[float, float]) -> tuple[float, float]:
    """Convert the renderer-neutral OBJ/OpenGL-style V axis to glTF's top origin."""
    return render_uv[0], 1.0 - render_uv[1]


def _image_uri(image_path: Path, output_dir: Path) -> str:
    """Return a portable image URI, including when source and output use different drives."""
    try:
        return os.path.relpath(image_path, output_dir).replace("\\", "/")
    except ValueError:
        return image_path.resolve().as_uri()


class _Buffer:
    def __init__(self) -> None:
        self.data = bytearray()
        self.views: list[dict[str, Any]] = []
        self.accessors: list[dict[str, Any]] = []

    def add(self, payload: bytes, component_type: int, count: int, type_name: str, *, target: int | None = None,
            minimum: list[float] | None = None, maximum: list[float] | None = None) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        offset = len(self.data)
        self.data.extend(payload)
        view: dict[str, Any] = {"buffer": 0, "byteOffset": offset, "byteLength": len(payload)}
        if target is not None:
            view["target"] = target
        view_index = len(self.views)
        self.views.append(view)
        accessor: dict[str, Any] = {"bufferView": view_index, "componentType": component_type, "count": count, "type": type_name}
        if minimum is not None:
            accessor["min"] = minimum
        if maximum is not None:
            accessor["max"] = maximum
        index = len(self.accessors)
        self.accessors.append(accessor)
        return index


def validate_gltf_binary_layout(
    gltf: dict[str, Any],
    binary: bytes,
    *,
    require_skin: bool = True,
    joint_count: int = 21,
) -> dict[str, Any]:
    """Validate every accessor's readable byte span, not just its BufferView."""
    if len(gltf.get("buffers", [])) != 1 or gltf["buffers"][0]["byteLength"] != len(binary):
        raise BoyExportError("glTF buffer byteLength differs from the binary file.")
    checked: list[dict[str, Any]] = []
    for accessor_index, accessor in enumerate(gltf.get("accessors", [])):
        if "bufferView" not in accessor or not 0 <= accessor["bufferView"] < len(gltf.get("bufferViews", [])):
            raise BoyExportError(f"Accessor {accessor_index} has an invalid BufferView.")
        component_type = accessor.get("componentType")
        type_name = accessor.get("type")
        count = accessor.get("count")
        if component_type not in COMPONENT_BYTES or type_name not in TYPE_COMPONENTS:
            raise BoyExportError(f"Accessor {accessor_index} has an invalid componentType or type.")
        if not isinstance(count, int) or count < 0:
            raise BoyExportError(f"Accessor {accessor_index} has an invalid count.")
        view = gltf["bufferViews"][accessor["bufferView"]]
        if view.get("buffer", 0) != 0:
            raise BoyExportError(f"Accessor {accessor_index} references an unsupported buffer.")
        component_size = COMPONENT_BYTES[component_type]
        element_size = component_size * TYPE_COMPONENTS[type_name]
        accessor_offset = accessor.get("byteOffset", 0)
        view_offset = view.get("byteOffset", 0)
        view_length = view.get("byteLength")
        stride = view.get("byteStride", element_size)
        if not all(isinstance(value, int) and value >= 0 for value in (accessor_offset, view_offset, view_length)):
            raise BoyExportError(f"Accessor {accessor_index} has invalid offsets or lengths.")
        if stride < element_size or stride % component_size or stride > 252:
            raise BoyExportError(f"Accessor {accessor_index} has an invalid byteStride.")
        if view_offset % 4 or accessor_offset % component_size or (view_offset + accessor_offset) % component_size:
            raise BoyExportError(f"Accessor {accessor_index} is misaligned.")
        required = 0 if count == 0 else (count - 1) * stride + element_size
        absolute_start = view_offset + accessor_offset
        absolute_end = absolute_start + required
        view_end = view_offset + view_length
        if accessor_offset + required > view_length:
            raise BoyExportError(
                f"Accessor {accessor_index} ({type_name}, component {component_type}, count {count}) "
                f"requires {required} bytes at relative offset {accessor_offset}, "
                f"but BufferView {accessor['bufferView']} has only {view_length} bytes."
            )
        if view_end > len(binary) or absolute_end > len(binary):
            raise BoyExportError(f"Accessor {accessor_index} reads beyond the binary buffer.")
        checked.append({
            "accessor": accessor_index, "buffer_view": accessor["bufferView"], "component_type": component_type,
            "type": type_name, "count": count, "component_size": component_size, "element_size": element_size,
            "byte_stride": stride, "accessor_byte_offset": accessor_offset, "buffer_view_byte_offset": view_offset,
            "buffer_view_byte_length": view_length, "absolute_start": absolute_start,
            "required_bytes": required, "absolute_end": absolute_end, "buffer_view_end": view_end,
        })
    skin = None
    if require_skin:
        if len(gltf.get("skins", [])) != 1:
            raise BoyExportError("glTF model export must contain exactly one skin.")
        skin_accessor = gltf["skins"][0]["inverseBindMatrices"]
        skin = checked[skin_accessor]
        if not (skin["component_type"] == 5126 and skin["type"] == "MAT4" and skin["count"] == joint_count
                and skin["required_bytes"] == joint_count * 16 * 4):
            raise BoyExportError(
                f"Inverse-bind accessor is not {joint_count} tightly readable FLOAT/MAT4 values."
            )
    return {"accessor_count": len(checked), "all_accessors_valid": True,
            "inverse_bind_accessor": skin, "checked_accessors": checked}


def _f32_next(value: float) -> float:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return struct.unpack("<f", struct.pack("<I", bits + 1))[0]


def _bake_states(sample_count: int, loop: bool) -> list[tuple[float, int, int, int]]:
    """STEP keys at exact MIPS round-to-nearest-even 10-bit transition times."""
    intervals = sample_count if loop else sample_count - 1
    states = [(0.0, 0, 0, 0)]
    for current in range(intervals):
        following = (current + 1) % sample_count
        for fraction10 in range(1, 1025):
            boundary = _f32(current + (fraction10 - 0.5) / 1024.0)
            # cvt.w.s ties to even: an odd result starts immediately after its
            # half-unit boundary; an even result starts at the boundary.
            if fraction10 & 1:
                boundary = _f32_next(boundary)
            states.append((boundary, current, following, fraction10))
    duration = float(sample_count if loop else sample_count - 1)
    endpoint = 0 if loop else sample_count - 1
    states.append((_f32(duration), endpoint, endpoint, 0))
    if any(a[0] >= b[0] for a, b in zip(states, states[1:])):
        raise BoyExportError("Baked 10-bit animation times are not strictly increasing.")
    return states


def _quat_from_row_matrix(matrix: list[list[float]]) -> tuple[float, float, float, float]:
    # glTF uses column vectors, so transpose JFG's row-vector rotation.
    m00, m01, m02 = matrix[0][0], matrix[1][0], matrix[2][0]
    m10, m11, m12 = matrix[0][1], matrix[1][1], matrix[2][1]
    m20, m21, m22 = matrix[0][2], matrix[1][2], matrix[2][2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w, x, y, z = 0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w, x, y, z = (m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w, x, y, z = (m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w, x, y, z = (m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s
    length = math.sqrt(x * x + y * y + z * z + w * w)
    values = [x / length, y / length, z / length, w / length]
    if values[3] < 0.0:
        values = [-value for value in values]
    return tuple(_f32(value) for value in values)


def _signed11(value: int) -> int:
    value &= 0x7FF
    return value - 0x800 if value & 0x400 else value


def _state_values(blob: bytes, structure: dict[str, Any], packed: list[dict[str, Any]], current: int, following: int,
                  fraction10: int) -> tuple[list[int], list[int], list[float]]:
    a, b = packed[current], packed[following]
    angles: list[int] = []
    scales: list[int] = []
    for item, av, bv, sa, sb in zip(structure["descriptors"], a["angles"], b["angles"], a["scales"], b["scales"]):
        sample = av + ((_signed11(bv - av) * fraction10) >> 10)
        angles.append(catalog_mod._signed16((item["angle_base_u16"] + (sample << 5)) & 0xFFFF))
        if item["raw"] & 0x10:
            scale = ((item["scale_base"] << 8) + (sa << 8) + (((sb - sa) * fraction10) >> 2)) & 0xFFFF
        else:
            scale = 0
        scales.append(scale)
    angles.extend((0, 0, 0)); scales.extend((0, 0, 0))
    root = [
        ((base << 11) + (av << 10) + (bv - av) * fraction10) / 1024.0
        for base, av, bv in zip(structure["root"]["signed_base_values"], a["root"], b["root"])
    ]
    return angles, scales, root


def _bone_records(boy_data: bytes, assignments: dict[int, int], model: Any) -> list[dict[str, Any]]:
    vertex_counts = Counter(assignments.values())
    corner_counts: Counter[int] = Counter()
    face_sets: defaultdict[int, set[int]] = defaultdict(set)
    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = model.groups[group.index + 1] if group.index + 1 < len(model.groups) else model.sentinel
        for triangle in model.triangles[group.triangle_start : following.triangle_start]:
            for local in triangle.local_indices:
                source = group.vertex_start + local
                matrix_id = assignments[source]
                corner_counts[matrix_id] += 1
                face_sets[matrix_id].add(triangle.index)
    records = []
    for index in range(BONE_COUNT):
        offset = BONE_START + index * 16
        parent, matrix_id = boy_data[offset], boy_data[offset + 1]
        records.append({
            "record_index": index, "name": f"jfg_node_{matrix_id:02d}", "matrix_id": matrix_id,
            "parent_id": None if parent == 0xFF else parent,
            "local_translation_xyz": list(struct.unpack_from(">fff", boy_data, offset + 4)),
            "active_vertex_count": vertex_counts[matrix_id],
            "active_corner_reference_count": corner_counts[matrix_id],
            "active_faces_touching_node": len(face_sets[matrix_id]),
            "has_active_geometry": vertex_counts[matrix_id] > 0,
        })
    return records


def _pack_floats(values: list[float] | tuple[float, ...]) -> bytes:
    return struct.pack("<" + "f" * len(values), *values)


def _geometry(model: Any, textures: dict[int, dict[str, Any]], assignments: dict[int, int], manifest_path: Path,
              output_dir: Path, buffer: _Buffer) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    dimensions = {
        index: (texture["runtime_width"], texture["runtime_height"])
        if texture["verified_rgba16_match"] else None
        for index, texture in textures.items()
    }
    render_mesh = expand_render_mesh(model, assignments, dimensions)
    keys = [
        (0xFF if primitive.texture_index is None else primitive.texture_index, primitive.double_sided)
        for primitive in render_mesh.primitives
    ]

    images: list[dict[str, Any]] = []
    samplers: list[dict[str, Any]] = []
    gltf_textures: list[dict[str, Any]] = []
    texture_ref: dict[int, int] = {}
    for texture_index in sorted({key[0] for key in keys if key[0] != 0xFF}):
        texture = textures[texture_index]
        if not texture["verified_rgba16_match"]:
            continue
        png = manifest_path.parent / texture["verified_rgba16_png"]
        relative = _image_uri(png, output_dir)
        tile = _tile_state(texture)
        def wrap(axis: dict[str, Any]) -> int:
            if axis["clamp"]: return 33071
            if axis["mirror"]: return 33648
            return 10497
        sampler_index = len(samplers)
        samplers.append({"wrapS": wrap(tile["cms"]), "wrapT": wrap(tile["cmt"]), "magFilter": 9729, "minFilter": 9729})
        image_index = len(images); images.append({"uri": relative, "name": f"boy_texture_{texture_index:02d}"})
        texture_ref[texture_index] = len(gltf_textures)
        gltf_textures.append({"sampler": sampler_index, "source": image_index})

    materials: list[dict[str, Any]] = []
    material_ref: dict[tuple[int, bool], int] = {}
    for ordinal, key in enumerate(keys):
        texture_index, double_sided = key
        texture = None if texture_index == 0xFF else textures[texture_index]
        verified = bool(texture and texture["verified_rgba16_match"])
        color = [((ordinal * factor) % 191 + 32) / 255 for factor in (73, 109, 151)] + [1.0]
        pbr: dict[str, Any] = {"baseColorFactor": color, "metallicFactor": 0.0, "roughnessFactor": 1.0}
        if verified:
            pbr["baseColorTexture"] = {"index": texture_ref[texture_index], "texCoord": 0}
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
        material_ref[key] = len(materials)
        materials.append({
            "name": f"{_material_name(texture_index, texture)}_{'double_sided' if double_sided else 'culled'}",
            "pbrMetallicRoughness": pbr, "doubleSided": double_sided,
            "alphaMode": "MASK" if verified else "OPAQUE", "alphaCutoff": 0.5,
            "extras": {"triangle_bit_0x40": double_sided, "texture_status": "VERIFIED RGBA16" if verified else ("NO TEXTURE" if texture is None else "UNKNOWN FORMAT")},
        })

    primitives: list[dict[str, Any]] = []
    corner_total = 0
    render_source_indices: list[int] = []
    for primitive in render_mesh.primitives:
        key = (0xFF if primitive.texture_index is None else primitive.texture_index, primitive.double_sided)
        texture_index, double_sided = key
        texture = None if texture_index == 0xFF else textures[texture_index]
        verified = bool(texture and texture["verified_rgba16_match"])
        positions: list[float] = []; uvs: list[float] = []; joints: list[int] = []; weights: list[float] = []; sources: list[int] = []
        first = primitive.first_index
        for vertex in render_mesh.vertices[first : first + primitive.index_count]:
            positions.extend(vertex.position)
            sources.append(vertex.source_vertex_index); render_source_indices.append(vertex.source_vertex_index)
            joints.extend((vertex.joint_id, 0, 0, 0)); weights.extend((1.0, 0.0, 0.0, 0.0))
            if verified:
                assert vertex.uv is not None
                uvs.extend(_gltf_texcoord(vertex.uv))
        count = len(positions) // 3; corner_total += count
        attrs = {
            "POSITION": buffer.add(_pack_floats(positions), 5126, count, "VEC3", target=34962,
                                   minimum=[min(positions[i::3]) for i in range(3)], maximum=[max(positions[i::3]) for i in range(3)]),
            "JOINTS_0": buffer.add(struct.pack("<" + "H" * len(joints), *joints), 5123, count, "VEC4", target=34962),
            "WEIGHTS_0": buffer.add(_pack_floats(weights), 5126, count, "VEC4", target=34962),
            "_JFG_SOURCE_INDEX": buffer.add(struct.pack("<" + "H" * len(sources), *sources), 5123, count, "SCALAR", target=34962),
        }
        if verified:
            attrs["TEXCOORD_0"] = buffer.add(_pack_floats(uvs), 5126, count, "VEC2", target=34962)
        primitives.append({"attributes": attrs, "material": material_ref[key], "mode": 4,
                           "extras": {"group_indices": list(primitive.group_indices), "face_count": count // 3, "triangle_bit_0x40": double_sided}})
    return primitives, materials, images, samplers, gltf_textures, {
        "render_corner_vertices": corner_total, "primitives": len(primitives),
        "render_vertex_to_source_vertex": render_source_indices,
    }


def _quat_matrix(q: tuple[float, float, float, float]) -> list[list[float]]:
    x, y, z, w = q
    xx, yy, zz, xy, xz, yz, wx, wy, wz = x*x, y*y, z*z, x*y, x*z, y*z, w*x, w*y, w*z
    return [[1-2*(yy+zz), 2*(xy-wz), 2*(xz+wy), 0.0],
            [2*(xy+wz), 1-2*(xx+zz), 2*(yz-wx), 0.0],
            [2*(xz-wy), 2*(yz+wx), 1-2*(xx+yy), 0.0], [0.0, 0.0, 0.0, 1.0]]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _artifact_positions(records: list[dict[str, Any]], assignments: dict[int, int], model: Any,
                        clip: dict[str, Any], time_value: float) -> dict[int, tuple[float, float, float]]:
    index = bisect_right(clip["times"], time_value) - 1
    worlds: dict[int, list[list[float]]] = {}
    for record in records:
        matrix_id = record["matrix_id"]
        local = _quat_matrix(clip["rotations"][matrix_id][index])
        translation = list(record["local_translation_xyz"])
        if matrix_id == 0:
            translation = list(clip["root_translations"][index])
        local[0][3], local[1][3], local[2][3] = translation
        world = local if record["parent_id"] is None else _matmul(worlds[record["parent_id"]], local)
        worlds[matrix_id] = world
    result = {}
    for source, matrix_id in assignments.items():
        vertex = model.vertices[source]; p = (vertex.x, vertex.y, vertex.z, 1.0); world = worlds[matrix_id]
        result[source] = tuple(sum(world[row][column] * p[column] for column in range(4)) for row in range(3))
    return result


def build_rig_artifacts(
    boy_data: bytes,
    rom: bytes,
    texture_manifest: Path,
    output_dir: Path,
    *,
    animation_specs: tuple[dict[str, Any], ...] | None = None,
    include_mesh: bool = True,
    validation_times: dict[int, tuple[float, ...]] | None = None,
) -> dict[str, bytes]:
    """Build the established Boy glTF representation for selected clips.

    Omitting ``animation_specs`` preserves the historical two-clip validation
    artifact exactly.  Passing an empty tuple emits the model and rig without
    actions.  ``include_mesh=False`` emits only the technical joint hierarchy
    and requested actions for animation-only interchange.
    """
    model = parse_boy(boy_data); assignments = rigid_matrix_assignments(model); records = _bone_records(boy_data, assignments, model)
    catalog = catalog_mod.catalog_boy_animations(rom); tables = catalog_mod._tables(rom)
    selected_specs = ANIMATION_SPECS if animation_specs is None else tuple(animation_specs)
    selected_indices = {spec["index"] for spec in selected_specs}
    if len(selected_indices) != len(selected_specs):
        raise BoyExportError("Requested Boy animation indices are not unique.")
    for spec in selected_specs:
        if not 0 <= spec["index"] < len(catalog["animations"]):
            raise BoyExportError(f"Boy animation index {spec['index']} is unavailable.")
        record = catalog["animations"][spec["index"]]
        if record["animation_id"] != spec["id"] or record["loop_enabled"] != spec["loop"]:
            raise BoyExportError(f"Requested Boy animation {spec['index']} metadata differs from the ROM catalog.")
    runtime_specs = list(selected_specs)
    if 0 not in selected_indices:
        record = catalog["animations"][0]
        runtime_specs.insert(0, {
            "index": 0,
            "id": record["animation_id"],
            "name": f"anim_00_ID{record['animation_id']}",
            "loop": record["loop_enabled"],
        })
    animation_sources: dict[int, tuple[bytes, dict[str, Any], list[dict[str, Any]], list[int]]] = {}
    for spec in runtime_specs:
        record = catalog["animations"][spec["index"]]
        if record["animation_id"] != spec["id"]:
            raise BoyExportError("Pinned rig animation ID differs.")
        start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
        blob = tables["asset43"][start:end]; structure = catalog_mod._structure(blob)
        packed = [catalog_mod._packed(blob, structure, index) for index in range(structure["sample_count"])]
        animation_sources[spec["index"]] = (blob, structure, packed, record["channel_map"])

    buffer = _Buffer(); resolutions, textures = resolve_boy_textures(model, rom, texture_manifest)
    if include_mesh:
        primitives, materials, images, samplers, gltf_textures, geometry_counts = _geometry(
            model, textures, assignments, texture_manifest, output_dir, buffer
        )
    else:
        primitives, materials, images, samplers, gltf_textures = [], [], [], [], []
        geometry_counts = {"render_corner_vertices": 0, "primitives": 0, "render_vertex_to_source_vertex": []}
    identity_matrices = []
    for _ in range(BONE_COUNT):
        identity_matrices.extend((
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ))
    inverse_bind_accessor = (
        buffer.add(_pack_floats(identity_matrices), 5126, BONE_COUNT, "MAT4")
        if include_mesh else None
    )
    sine_table = _sine_table(rom)
    clip_runtime: dict[int, dict[str, Any]] = {}
    gltf_animations: list[dict[str, Any]] = []
    for spec in runtime_specs:
        blob, structure, packed, channel_map = animation_sources[spec["index"]]
        emit_animation = spec["index"] in selected_indices
        states = _bake_states(structure["sample_count"], spec["loop"]) if emit_animation else [(0.0, 0, 0, 0)]
        times = [state[0] for state in states]
        rotations: list[list[tuple[float,float,float,float]]] = [[] for _ in range(BONE_COUNT)]
        roots: list[tuple[float,float,float]] = []
        for _, current, following, fraction10 in states:
            angles, scales, root = _state_values(blob, structure, packed, current, following, fraction10)
            for record in records:
                channel = channel_map[record["record_index"]]
                matrix = _local_matrix_from_stored(
                    angles[channel*3:channel*3+3],
                    scales[channel*3:channel*3+3],
                    record["local_translation_xyz"],
                    sine_table,
                )
                rotations[record["matrix_id"]].append(_quat_from_row_matrix(matrix))
            base = records[0]["local_translation_xyz"]
            roots.append(tuple(_f32(base[axis] + root[axis]) for axis in range(3)))
        if emit_animation:
            time_accessor = buffer.add(_pack_floats(times), 5126, len(times), "SCALAR", minimum=[times[0]], maximum=[times[-1]])
            samplers_out: list[dict[str, Any]] = []; channels_out: list[dict[str, Any]] = []
            for matrix_id in range(BONE_COUNT):
                flat = [value for quaternion in rotations[matrix_id] for value in quaternion]
                output = buffer.add(_pack_floats(flat), 5126, len(times), "VEC4")
                sampler = len(samplers_out); samplers_out.append({"input": time_accessor, "output": output, "interpolation": "STEP"})
                channels_out.append({"sampler": sampler, "target": {"node": 1 + matrix_id, "path": "rotation"}})
            root_flat = [value for translation in roots for value in translation]
            output = buffer.add(_pack_floats(root_flat), 5126, len(times), "VEC3")
            sampler = len(samplers_out); samplers_out.append({"input": time_accessor, "output": output, "interpolation": "STEP"})
            channels_out.append({"sampler": sampler, "target": {"node": 1, "path": "translation"}})
            gltf_animations.append({"name": spec["name"], "samplers": samplers_out, "channels": channels_out,
                                    "extras": {"boy_animation_index": spec["index"], "animation_id": spec["id"], "loop": spec["loop"],
                                               "time_unit": "one glTF second equals one JFG sample-time unit (technical mapping)",
                                               "bake": "STEP at every MIPS 10-bit round-to-nearest-even state transition"}})
        clip_runtime[spec["index"]] = {"times": times, "rotations": rotations, "root_translations": roots, "state_count": len(times)}

    model_node: dict[str, Any] = {
        "name": "Boy_Prop_0220_RIG_VALIDATION",
        "extras": {"status": "VALIDATION ARTIFACT", "missing_separate_hand": True},
    }
    if include_mesh:
        model_node.update({"mesh": 0, "skin": 0})
    nodes: list[dict[str, Any]] = [model_node]
    default_clip = clip_runtime[0]
    for record in records:
        matrix_id = record["matrix_id"]
        translation = default_clip["root_translations"][0] if matrix_id == 0 else tuple(record["local_translation_xyz"])
        children = [1 + child["matrix_id"] for child in records if child["parent_id"] == matrix_id]
        node = {"name": record["name"], "translation": list(translation), "rotation": list(default_clip["rotations"][matrix_id][0]),
                "extras": {key: value for key, value in record.items() if key != "name"}}
        if children: node["children"] = children
        nodes.append(node)
    root_joint = next(record["matrix_id"] for record in records if record["parent_id"] is None)
    gltf: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "jfg-re limited Boy rig validator"},
        "scene": 0, "scenes": [{"name": "Boy validation", "nodes": [0, 1 + root_joint]}],
        "nodes": nodes, "animations": gltf_animations,
        "buffers": [{"uri": "boy-rig-validation.bin", "byteLength": len(buffer.data)}],
        "bufferViews": buffer.views, "accessors": buffer.accessors,
        "extras": {"prop_id": PROP_ID, "status": "LIMITED VALIDATION ARTIFACT", "technical_time_mapping": "1 second = 1 JFG sample unit; no FPS claim"},
    }
    if include_mesh:
        gltf.update({
            "meshes": [{"name": "Boy verified runtime mesh", "primitives": primitives}],
            "skins": [{"name": "TECHNICAL_REPRESENTATION_identity_inverse_bind", "inverseBindMatrices": inverse_bind_accessor,
                       "skeleton": 1 + root_joint, "joints": [1 + index for index in range(BONE_COUNT)],
                       "extras": {"status": "TECHNICAL REPRESENTATION; not a claimed JFG bind/rest pose", "weights": "one joint per vertex, weight 1.0"}}],
            "materials": materials, "images": images, "samplers": samplers, "textures": gltf_textures,
        })

    effective_validation_times = VALIDATION_TIMES if validation_times is None and animation_specs is None else (validation_times or {})
    validation_results = []
    for spec in selected_specs:
        blob, _, _, channel_map = animation_sources[spec["index"]]
        for time_value in effective_validation_times.get(spec["index"], ()):
            frame = decode_anim0_time(blob, time_value) if spec["index"] == 0 else catalog_mod.decode_animation_time(blob, time_value)
            matrices = build_matrices(boy_data, frame, rom, channel_map)
            world_by_id = {item["matrix_id"]: item["world_model_matrix"] for item in matrices}
            artifact = _artifact_positions(records, assignments, model, clip_runtime[spec["index"]], time_value)
            errors: list[float] = []; by_matrix: defaultdict[int, list[float]] = defaultdict(list); exact = within = 0
            for source, matrix_id in assignments.items():
                reference = _transform(model.vertices[source], world_by_id[matrix_id])[0]
                delta = math.dist(reference, artifact[source]); errors.append(delta); by_matrix[matrix_id].append(delta)
                exact += delta == 0.0; within += delta <= FLOAT_TOLERANCE
            validation_results.append({
                "animation_index": spec["index"], "animation_id": spec["id"], "time": time_value,
                "maximum_position_error": max(errors), "mean_position_error": sum(errors)/len(errors),
                "exact_vertex_count": exact, "within_tolerance_vertex_count": within, "vertex_count": len(errors),
                "tolerance": FLOAT_TOLERANCE,
                "per_matrix_id": {str(mid): {"vertex_count": len(vals), "maximum_error": max(vals), "mean_error": sum(vals)/len(vals),
                                               "within_tolerance": sum(value <= FLOAT_TOLERANCE for value in vals)}
                                  for mid, vals in sorted(by_matrix.items())},
            })
    all_errors = [item["maximum_position_error"] for item in validation_results]
    compared_vertices = sum(item["vertex_count"] for item in validation_results)
    weighted_mean = (
        sum(item["mean_position_error"] * item["vertex_count"] for item in validation_results) / compared_vertices
        if compared_vertices else 0.0
    )
    binary_layout = validate_gltf_binary_layout(gltf, bytes(buffer.data), require_skin=include_mesh)
    render_map = {
        "schema_version": 1,
        "render_vertex_count": geometry_counts["render_corner_vertices"],
        "active_source_vertex_count": len(assignments),
        "render_vertex_to_source_vertex": geometry_counts.pop("render_vertex_to_source_vertex"),
        "coordinate_note": "glTF source coordinates; Blender importer converts Y-up to Z-up",
    }
    report = {
        "schema_version": 1,
        "scope": "Prop 220 Boy; selected technical animations",
        "representation": {
            "format": "glTF 2.0 plus external binary and existing VERIFIED PNG references",
            "joints": 21, "joint_names": [record["name"] for record in records],
            "skin": "one joint per render vertex; WEIGHTS_0 exactly [1,0,0,0]",
            "inverse_bind_matrices": "21 identity matrices",
            "reference_status": "TECHNICAL REPRESENTATION; not a JFG bind pose, rest pose, or T-pose",
            "equivalence": "identity inverse-bind makes each skin matrix equal the animated JFG joint world matrix",
            "render_vertex_note": "Corner-expanded glTF vertices preserve per-corner UVs; they map back to 638 active source vertices.",
        },
        "nodes": records, "geometry": {**geometry_counts, "active_source_vertices": len(assignments), "faces": 502},
        "animations": [{**spec, "baked_state_count": clip_runtime[spec["index"]]["state_count"],
                         "duration_in_technical_sample_units": clip_runtime[spec["index"]]["times"][-1],
                         "interpolation": "STEP on complete 10-bit state-transition grid"} for spec in selected_specs],
        "validation_times": validation_results,
        "validation_summary": {
            "maximum_position_error": max(all_errors, default=0.0), "mean_position_error": weighted_mean,
            "vertices_compared": compared_vertices,
            "within_tolerance": sum(item["within_tolerance_vertex_count"] for item in validation_results),
            "exact": sum(item["exact_vertex_count"] for item in validation_results), "tolerance": FLOAT_TOLERANCE,
        },
        "texture_resolution_records": resolutions,
        "binary_layout_validation": binary_layout,
        "limitations": ["No FPS is claimed; glTF seconds are technical JFG sample units.",
                        "The identity inverse-bind reference is technical and not a discovered game bind pose.",
                        "Only explicitly selected technical animations are included.", "The separate hand remains absent.",
                        "UNKNOWN texture formats retain diagnostic materials."],
        "validation": {"all_requested_reference_times_compared": len(validation_results) == sum(len(times) for times in effective_validation_times.values()),
                       "all_ten_reference_times_compared": animation_specs is None and len(validation_results) == 10,
                       "all_vertices_within_tolerance": all(item["within_tolerance_vertex_count"] == item["vertex_count"] for item in validation_results),
                       "deterministic_regeneration_match": True, "rom_identity_verified": True},
    }
    guide = """# Blender-Prüfung: begrenztes Boy-Rig

1. Importiere `boy-rig-validation.gltf` über **File > Import > glTF 2.0**.
2. Wähle die importierte Armature beziehungsweise den technischen Skin-Rig.
3. Wähle im Dope Sheet / Action Editor `boy_anim_00_id_1026` oder
   `boy_anim_43_id_1069`.
4. Die Timeline-Zeit ist technisch: eine Sekunde entspricht einer JFG-
   Samplezeiteinheit. Es wird keine Spiel-FPS behauptet.
5. Animation 0 läuft von 0 bis 16 und ist als Loop markiert. Animation 43
   läuft von 0 bis 75 und endet dort.
6. Verwende Material Preview. Die referenzierten VERIFIED PNGs müssen an
   ihren relativen Pfaden unter `data/generated/rgba16-us-verified/` bleiben.
7. Zeige Armature/Bones beziehungsweise Joint-Nodes an. Die technischen
   Identitäts-Inverse-Bindmatrizen sind keine behauptete JFG-Rest- oder T-Pose.

Die Animationen benutzen STEP-Keys an sämtlichen 10-Bit-Zustandsübergängen.
Blenders Quaternion- oder Euler-Interpolation wird deshalb nicht als Ersatz
für JFGs Winkelinterpolation verwendet.

## Reproduzierbare Importprüfung

`blender_validate_boy_rig.py` im selben Verzeichnis ist die gepinnte Kopie
des Prüfskripts. Es importiert das glTF mit Blender, kontrolliert Mesh,
Armature, Actions, Materialien und Bilder und vergleicht die ausgewerteten
Positionen an zehn Zeiten mit dem JFG-Referenzdecoder. Der ausgeführte Lauf
liegt in `blender-validation-report.json`; die importierte Szene in
`boy-rig-validation.blend`.
"""
    gltf_bytes = (json.dumps(gltf, indent=2, sort_keys=True) + "\n").encode()
    tool_script = Path(__file__).resolve().parents[2] / "tools" / "blender_validate_boy_rig.py"
    return {"boy-rig-validation.gltf": gltf_bytes, "boy-rig-validation.bin": bytes(buffer.data),
            "boy-rig-validation-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
            "boy-rig-render-map.json": (json.dumps(render_map, indent=2, sort_keys=True) + "\n").encode(),
            "blender_validate_boy_rig.py": tool_script.read_bytes(), "BLENDER.md": guide.encode()}


def export_boy_rig(boy_path: Path, rom_path: Path, texture_manifest: Path, output_dir: Path) -> dict[str, Any]:
    boy_path = boy_path.resolve(strict=True); rom_path = rom_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True); output_dir = output_dir.resolve()
    if output_dir.exists(): raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    first = build_rig_artifacts(boy_path.read_bytes(), rom_path.read_bytes(), texture_manifest, output_dir)
    second = build_rig_artifacts(boy_path.read_bytes(), rom_path.read_bytes(), texture_manifest, output_dir)
    if first != second: raise BoyExportError("Boy rig artifacts are not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items(): (output_dir / name).write_bytes(data)
    return json.loads(first["boy-rig-validation-report.json"])
