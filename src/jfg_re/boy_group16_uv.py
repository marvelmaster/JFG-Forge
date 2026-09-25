"""Pinned UV and texture-tile validation for Boy Prop 220, group 16 only.

This module deliberately is not a general model exporter.  It records one
closed evidence chain and emits one small OBJ/MTL validation artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from jfg_re.boy_export import (
    BOY_SHA256,
    BoyExportError,
    _cross,
    parse_boy,
    resolve_boy_textures,
)
from jfg_re.props import validate_rom_identity
from jfg_re.textures_rgba16 import decode_png_rgba


GROUP_INDEX = 16
TEXTURE_INDEX = 5
TEXTURE_ID = 0x820D
TEXTURE_ROM_ASSET_START = 0x178650
TEXTURE_ROM_CONTAINER = 0x178670
TEXTURE_WIDTH = 16
TEXTURE_HEIGHT = 16
EXPECTED_GROUP_RAW = bytes.fromhex("05020bff081000670049000000000003")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _uv(raw_s: int, raw_t: int) -> tuple[float, float]:
    """Map JFG S10.5 texel coordinates to conventional OBJ coordinates."""
    return raw_s / (32 * TEXTURE_WIDTH), 1.0 - raw_t / (32 * TEXTURE_HEIGHT)


def _group_data(model: Any) -> tuple[Any, Any, list[Any]]:
    group = model.groups[GROUP_INDEX]
    following = model.groups[GROUP_INDEX + 1]
    triangles = list(model.triangles[group.triangle_start : following.triangle_start])
    return group, following, triangles


def _make_obj(model: Any, group: Any, following: Any, triangles: list[Any]) -> str:
    lines = [
        "# Prop 220 Boy, group 16 only: UV/tile validation artifact",
        "# Positions are stored raw XYZ; no bone or bind-pose transform is applied.",
        "# raw S/T are signed S10.5: texel_s=raw_s/32, texel_t=raw_t/32.",
        "# OBJ mapping: u=raw_s/(32*16), v=1-raw_t/(32*16).",
        "# The MTL requests clamp on both axes, matching this group's JFG tile.",
        "mtllib boy-group16-uv.mtl",
        "o Boy_Prop_0220_Group_016_UV_VALIDATION",
    ]
    for vertex in model.vertices[group.vertex_start : following.vertex_start]:
        lines.append(f"v {vertex.x} {vertex.y} {vertex.z}")
    vt_index = 1
    for triangle in triangles:
        for raw_s, raw_t in triangle.corner_pairs:
            u, v = _uv(raw_s, raw_t)
            lines.append(f"vt {u:.9f} {v:.9f}")
    lines.extend(("usemtl boy_group16_texture_05_id_820d", "s off"))
    for triangle in triangles:
        corners = []
        for local_index in triangle.local_indices:
            corners.append(f"{local_index + 1}/{vt_index}")
            vt_index += 1
        lines.append("f " + " ".join(corners))
    return "\n".join(lines) + "\n"


def _make_mtl(reference_png: Path, output_dir: Path) -> str:
    relative = os.path.relpath(reference_png, output_dir).replace("\\", "/")
    return "\n".join(
        (
            "# Prop 220 Boy group 16; JFG tile cms=cmt=CLAMP.",
            "newmtl boy_group16_texture_05_id_820d",
            "Ka 0.000000 0.000000 0.000000",
            "Kd 1.000000 1.000000 1.000000",
            "d 1.0",
            f"map_Kd -clamp on {relative}",
            "",
        )
    )


def build_group16_uv_artifacts(
    boy_data: bytes,
    rom: bytes,
    texture_manifest: Path,
    output_dir: Path,
) -> dict[str, bytes]:
    """Build deterministic artifacts after validating every pinned identity."""
    model = parse_boy(boy_data)
    group, following, triangles = _group_data(model)
    group_raw = boy_data[0x118 + GROUP_INDEX * 16 : 0x118 + (GROUP_INDEX + 1) * 16]
    if group_raw != EXPECTED_GROUP_RAW:
        raise BoyExportError("Pinned Boy group 16 record differs.")
    if group.runtime_skipped or group.texture_index != TEXTURE_INDEX:
        raise BoyExportError("Pinned Boy group 16 is no longer the expected active textured group.")
    if (group.vertex_start, following.vertex_start, group.triangle_start, following.triangle_start) != (103, 119, 73, 88):
        raise BoyExportError("Pinned Boy group 16 ranges differ.")

    resolutions, by_index = resolve_boy_textures(model, rom, texture_manifest)
    texture = by_index[TEXTURE_INDEX]
    required = {
        "texture_id": TEXTURE_ID,
        "runtime_asset_rom_start": TEXTURE_ROM_ASSET_START,
        "compressed_stream_rom_offset": TEXTURE_ROM_CONTAINER,
        "runtime_width": TEXTURE_WIDTH,
        "runtime_height": TEXTURE_HEIGHT,
        "verified_rgba16_match": True,
    }
    if any(texture.get(key) != value for key, value in required.items()):
        raise BoyExportError("Pinned group 16 texture resolution differs.")

    runtime_header = bytes.fromhex(texture["runtime_header_hex"])
    tile = {
        "cms": runtime_header[28],
        "cmt": runtime_header[30],
        "masks": runtime_header[29],
        "maskt": runtime_header[31],
        "shifts": 0,
        "shiftt": 0,
    }
    if tile != {"cms": 2, "cmt": 2, "masks": 0, "maskt": 0, "shifts": 0, "shiftt": 0}:
        raise BoyExportError("Pinned group 16 tile is no longer clamp/clamp with zero masks and shifts.")

    reference_png = texture_manifest.parent / texture["verified_rgba16_png"]
    png_data = reference_png.read_bytes()
    png_width, png_height, _ = decode_png_rgba(png_data)
    if (png_width, png_height) != (TEXTURE_WIDTH, TEXTURE_HEIGHT):
        raise BoyExportError("Pinned verified group 16 PNG dimensions differ.")

    triangle_records: list[dict[str, Any]] = []
    for triangle in triangles:
        absolute = [group.vertex_start + index for index in triangle.local_indices]
        points = [
            [model.vertices[index].x, model.vertices[index].y, model.vertices[index].z]
            for index in absolute
        ]
        if _cross(tuple(tuple(point) for point in points)) == (0, 0, 0):
            raise BoyExportError(f"Selected group triangle {triangle.index} is geometrically degenerate.")
        corners = []
        for raw_s, raw_t in triangle.corner_pairs:
            u, v = _uv(raw_s, raw_t)
            corners.append(
                {
                    "raw_s": raw_s,
                    "raw_t": raw_t,
                    "texel_s": raw_s / 32,
                    "texel_t": raw_t / 32,
                    "obj_u": u,
                    "obj_v": v,
                }
            )
        triangle_records.append(
            {
                "triangle_index": triangle.index,
                "flag_hex": f"0x{triangle.flag:02X}",
                "local_vertex_indices": list(triangle.local_indices),
                "absolute_vertex_indices": absolute,
                "xyz_points": points,
                "corners": corners,
            }
        )

    raw_s_values = [corner["raw_s"] for triangle in triangle_records for corner in triangle["corners"]]
    raw_t_values = [corner["raw_t"] for triangle in triangle_records for corner in triangle["corners"]]
    report: dict[str, Any] = {
        "schema_version": 1,
        "scope": "Prop 220 Boy, exactly group 16",
        "status": "EXPERIMENTAL artifact backed by the statuses recorded per finding",
        "input": {
            "boy_prop_id": 220,
            "boy_sha256": BOY_SHA256,
            "powerboy_processed": False,
            "rom_identity": "US Z64, 33,554,432 bytes, SHA-1 493ced9008dbe932d6e91179b68e8630cf23a023",
        },
        "selection": {
            "group_index": GROUP_INDEX,
            "reason": "active group with a VERIFIED RGBA16 chain, 15 nondegenerate triangles, and signed/boundary-crossing S/T ranges that expose both axes and clamp behavior",
            "group_record_hex": group_raw.hex(),
            "render_flags_hex": f"0x{group.render_flags:08X}",
            "vertex_range": [group.vertex_start, following.vertex_start],
            "triangle_range": [group.triangle_start, following.triangle_start],
            "vertex_count": following.vertex_start - group.vertex_start,
            "triangle_count": len(triangles),
            "nondegenerate_triangle_count": len(triangles),
            "raw_s_range": [min(raw_s_values), max(raw_s_values)],
            "raw_t_range": [min(raw_t_values), max(raw_t_values)],
        },
        "texture": {
            "texture_index": TEXTURE_INDEX,
            "texture_id_hex": "0x820D",
            "texture_record_hex": model.texture_records[TEXTURE_INDEX].hex(),
            "texLoadTexture_path": "ID high bit -> asset 1 offset table -> asset 0 data",
            "runtime_asset_rom_start_hex": "0x178650",
            "compressed_rgba16_container_rom_offset_hex": "0x178670",
            "dimensions": [TEXTURE_WIDTH, TEXTURE_HEIGHT],
            "runtime_header_hex": runtime_header.hex(),
            "verified_png": texture["verified_rgba16_png"],
            "verified_png_sha256": _sha256(png_data),
            "resolution_status": "VERIFIED",
        },
        "coordinate_dataflow": {
            "cpu": "makeModelGfx passes 16-byte triangle records unchanged through G_TRIN",
            "rsp_record_copy": [
                {"rsp_imem": "0x1740", "rom": "0x0A0710", "effect": "load triangle +4 (first S/T pair)"},
                {"rsp_imem": "0x1744", "rom": "0x0A0714", "effect": "store first pair to vertex slot +0x14"},
                {"rsp_imem": "0x1748..0x1754", "rom": "0x0A0718..0x0A0724", "effect": "repeat for triangle +8 and +12"},
            ],
            "rsp_texture_gradient": [
                {"rsp_imem": "0x1CC4", "rom": "0x0A0C94", "effect": "texture-enabled branch via triangle/RDP command bit 0x2"},
                {"rsp_imem": "0x1CE0..0x1CE8", "rom": "0x0A0CB0..0x0A0CB8", "effect": "LLV loads the three 4-byte S/T pairs from vertex slot +0x14"},
                {"rsp_imem": "0x1D10..0x1D64", "rom": "0x0A0CE0..0x0A0D34", "effect": "perspective products and initial texture coefficients"},
                {"rsp_imem": "0x1E08..0x1F6C", "rom": "0x0A0DD8..0x0A0F3C", "effect": "differences, gradients, and texture coefficient fields emitted into the RDP triangle command"},
            ],
            "fixed_point": {
                "status": "VERIFIED",
                "format": "signed S10.5",
                "evidence": "JFG PR/gt.h declares transformed gtVtxOut s/t as S10.5; actual JFG G_TRIN copies and loads the signed 16-bit pairs without a CPU-side normalization",
                "texel_formula": "texel_s = raw_s / 32; texel_t = raw_t / 32",
            },
        },
        "tile_configuration": {
            "builder_cpu_function": "0x8005719C (called through 0x800570D8)",
            "texDPTextureX": "0x80055C00",
            "header_field_loads": {
                "cmt": "lbu texture+0x1E at 0x800576FC",
                "maskt": "lbu texture+0x1F at 0x80057708",
                "cms": "lbu texture+0x1C at 0x80057724",
                "masks": "lbu texture+0x1D at 0x80057734",
            },
            "set_tile_size": "0x80057750..0x80057780 emits (width-1)<<2 and (height-1)<<2",
            "cms": {"value": 2, "meaning": "G_TX_CLAMP", "status": "VERIFIED"},
            "cmt": {"value": 2, "meaning": "G_TX_CLAMP", "status": "VERIFIED"},
            "masks": 0,
            "maskt": 0,
            "shifts": 0,
            "shiftt": 0,
            "mirror": False,
            "effective_behavior": "clamp on S and T; no mask repetition, mirror, or coordinate shift",
            "texDPTextureX_transform": "none; it selects/copies the prebuilt texture display list and render state",
        },
        "axis_and_export": {
            "s_axis": "horizontal texture axis",
            "t_axis": "row/vertical texture axis",
            "increasing_t": "later RDP texture rows; downward in the verified PNG's top-to-bottom row order",
            "obj_v_flip": True,
            "obj_v_flip_status": "VERIFIED for preserving this PNG orientation in conventional OBJ/Blender UV space",
            "raw_to_obj_formula": {
                "u": "raw_s / (32 * 16)",
                "v": "1 - raw_t / (32 * 16)",
            },
            "clamp_note": "coordinates outside [0,1] are intentional; the MTL requests clamp to reproduce the selected JFG tile",
        },
        "triangles": triangle_records,
        "confidence": {
            "VERIFIED": [
                "group 16 identity/ranges and texture index 5",
                "TextureRecord 5 -> ID 0x820D -> ROM 0x178650/0x178670 -> pixelvalidated 16x16 RGBA16 PNG",
                "S/T order, signed S10.5 unit, and direct participation in RSP texture gradients",
                "cms=cmt=CLAMP; masks=maskt=shifts=shiftt=0",
                "increasing T addresses later texture rows and therefore requires an OBJ V inversion for the existing top-down PNG",
            ],
            "LIKELY": [
                "visual sampling in a given OBJ importer matches RDP subtexel filtering exactly; OBJ/MTL cannot encode the complete N64 sampler",
            ],
            "UNKNOWN": [
                "whether every OBJ/MTL importer honors the -clamp on map option",
                "exact pixel-level equivalence of N64 filtering and Blender's selected image interpolation mode",
            ],
        },
        "applicability": "The S10.5 and OBJ V-axis formulas transfer to textured Boy G_TRIN groups. Tile modes must be read per texture header; group 16's clamp result must not be generalized to every Boy texture.",
        "validation": {
            "all_indices_in_group_vertex_range": True,
            "all_triangles_nondegenerate": True,
            "reference_png_dimensions_match": True,
            "artifact_generation_is_deterministic": True,
        },
    }

    readme = """# Boy group 16 UV validation artifact

This directory contains exactly one active group from Prop 220.  Open
`boy-group16-uv.obj`; its MTL references the already VERIFIED RGBA16 PNG.

The coordinates are exported as:

```text
texel_s = raw_s / 32
texel_t = raw_t / 32
u = raw_s / (32 * 16)
v = 1 - raw_t / (32 * 16)
```

The selected JFG tile clamps S and T and uses zero masks and shifts.  Values
outside the normalized range are retained; the MTL requests `-clamp on`.
This OBJ still uses stored raw XYZ and applies no bone or bind-pose transform.
"""
    artifacts = {
        "boy-group16-uv.obj": _make_obj(model, group, following, triangles).encode(),
        "boy-group16-uv.mtl": _make_mtl(reference_png, output_dir).encode(),
        "boy-group16-uv-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
        "README.md": readme.encode(),
    }
    return artifacts


def export_group16_uv(
    boy_path: Path,
    rom_path: Path,
    texture_manifest: Path,
    output_dir: Path,
) -> dict[str, Any]:
    boy_path = boy_path.resolve(strict=True)
    rom_path = rom_path.resolve(strict=True)
    texture_manifest = texture_manifest.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    rom = rom_path.read_bytes()
    boy_data = boy_path.read_bytes()
    first = build_group16_uv_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_group16_uv_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("Group 16 artifact generation is not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items():
        (output_dir / name).write_bytes(data)
    return json.loads(first["boy-group16-uv-report.json"])
