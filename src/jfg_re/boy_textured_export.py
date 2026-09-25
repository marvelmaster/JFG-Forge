"""Pinned textured static exporter for US Prop 220 ``Boy`` only.

The exporter applies the verified S10.5 corner-coordinate interpretation to
active Boy groups whose texture is already part of the verified RGBA16 set.
It deliberately leaves raw XYZ untransformed and does not decode unknown
texture formats.
"""

from __future__ import annotations

from collections import Counter
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
from jfg_re.boy_group16_uv import GROUP_INDEX as REFERENCE_GROUP_INDEX
from jfg_re.boy_group16_uv import _uv as reference_group16_uv
from jfg_re.props import validate_rom_identity
from jfg_re.textures_rgba16 import decode_png_rgba


EXPECTED_ACTIVE_GROUPS = 65
EXPECTED_RUNTIME_FACES = 502
EXPECTED_TEXTURED_GROUPS = 62
EXPECTED_TEXTURED_FACES = 478
EXPECTED_UNKNOWN_GROUPS = 3
EXPECTED_UNKNOWN_FACES = 24
EXPECTED_VERIFIED_TEXTURES = 14


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _following_group(model: Any, index: int) -> Any:
    return model.groups[index + 1] if index + 1 < len(model.groups) else model.sentinel


def _tile_axis(value: int) -> dict[str, Any]:
    return {
        "value": value,
        "clamp": bool(value & 2),
        "mirror": bool(value & 1),
        "wrap": not bool(value & 2),
        "name": {0: "WRAP", 1: "MIRROR|WRAP", 2: "CLAMP", 3: "MIRROR|CLAMP"}[value],
    }


def _tile_state(texture: dict[str, Any]) -> dict[str, Any]:
    header = bytes.fromhex(texture["runtime_header_hex"])
    if len(header) != 32:
        raise BoyExportError("Runtime texture header is not 32 bytes.")
    mip_levels = header[27]
    if mip_levels >= 2:
        raise BoyExportError(
            f"Texture {texture['texture_id_hex']} uses the separate mipmapped tile path, which this exporter does not claim."
        )
    cms, masks, cmt, maskt = header[28], header[29], header[30], header[31]
    if cms > 3 or cmt > 3 or masks > 15 or maskt > 15:
        raise BoyExportError(f"Texture {texture['texture_id_hex']} has invalid tile fields.")
    return {
        "cms": _tile_axis(cms),
        "cmt": _tile_axis(cmt),
        "masks": masks,
        "maskt": maskt,
        "shifts": 0,
        "shiftt": 0,
        "mip_level_count": mip_levels,
        "source": {
            "cms": "texture header +0x1C",
            "masks": "texture header +0x1D",
            "cmt": "texture header +0x1E",
            "maskt": "texture header +0x1F",
            "shifts": "zero in JFG non-mipmapped SetTile path at 0x800576C4..0x80057748",
            "shiftt": "zero in JFG non-mipmapped SetTile path at 0x800576C4..0x80057748",
        },
    }


def decode_tile_state(texture: dict[str, Any]) -> dict[str, Any]:
    """Public renderer-neutral access to the already verified tile decoder."""
    return _tile_state(texture)


def _material_name(texture_index: int, texture: dict[str, Any] | None) -> str:
    if texture_index == 0xFF:
        return "boy_untextured"
    assert texture is not None
    suffix = "rgba16_verified" if texture["verified_rgba16_match"] else "unknown_format"
    return f"boy_tex_{texture_index:02d}_id_{texture['texture_id']:04x}_{suffix}"


def _group_triangles(model: Any, group: Any) -> list[Any]:
    following = _following_group(model, group.index)
    return list(model.triangles[group.triangle_start : following.triangle_start])


def _is_degenerate(model: Any, group: Any, triangle: Any) -> bool:
    points = tuple(
        (
            model.vertices[group.vertex_start + index].x,
            model.vertices[group.vertex_start + index].y,
            model.vertices[group.vertex_start + index].z,
        )
        for index in triangle.local_indices
    )
    return _cross(points) == (0, 0, 0)


def _build_materials(
    model: Any,
    textures: dict[int, dict[str, Any]],
    manifest_path: Path,
    output_dir: Path,
) -> tuple[str, list[dict[str, Any]]]:
    used_indices = sorted({group.texture_index for group in model.groups if not group.runtime_skipped})
    lines = [
        "# Prop 220 Boy textured static validation materials",
        "# Only VERIFIED RGBA16 textures are mapped. Unknown formats use diagnostic colors.",
    ]
    records: list[dict[str, Any]] = []
    for ordinal, texture_index in enumerate(used_indices):
        texture = None if texture_index == 0xFF else textures[texture_index]
        name = _material_name(texture_index, texture)
        verified = bool(texture and texture["verified_rgba16_match"])
        color = (
            ((ordinal * 73) % 191 + 32) / 255,
            ((ordinal * 109) % 191 + 32) / 255,
            ((ordinal * 151) % 191 + 32) / 255,
        )
        lines.extend(
            (
                "",
                f"newmtl {name}",
                f"Ka 0.000000 0.000000 0.000000",
                f"Kd {color[0]:.6f} {color[1]:.6f} {color[2]:.6f}",
                "d 1.0",
            )
        )
        record: dict[str, Any] = {
            "material": name,
            "texture_index": texture_index,
            "texture_status": "UNREFERENCED" if texture is None else ("VERIFIED RGBA16" if verified else "UNKNOWN FORMAT"),
            "texture_id_hex": None if texture is None else texture["texture_id_hex"],
            "png": None,
            "png_sha256": None,
            "tile_state": None,
            "mtl_mapping": "none",
        }
        if verified:
            png = manifest_path.parent / texture["verified_rgba16_png"]
            if not png.is_file():
                raise BoyExportError(f"Verified texture PNG is missing: {png}")
            png_data = png.read_bytes()
            width, height, _ = decode_png_rgba(png_data)
            if (width, height) != (texture["runtime_width"], texture["runtime_height"]):
                raise BoyExportError(f"Verified PNG dimensions differ for {texture['texture_id_hex']}.")
            tile = _tile_state(texture)
            relative = os.path.relpath(png, output_dir).replace("\\", "/")
            cms, cmt = tile["cms"], tile["cmt"]
            if cms["clamp"] and cmt["clamp"] and not cms["mirror"] and not cmt["mirror"]:
                lines.append(f"map_Kd -clamp on {relative}")
                mapping = "map_Kd -clamp on"
            elif cms["wrap"] and cmt["wrap"] and not cms["mirror"] and not cmt["mirror"]:
                lines.append(f"map_Kd {relative}")
                mapping = "map_Kd default repeat"
            else:
                lines.append(f"map_Kd {relative}")
                mapping = "PNG linked; exact asymmetric/mirrored RDP addressing is metadata-only"
            record.update(
                {
                    "png": texture["verified_rgba16_png"],
                    "png_sha256": _sha256(png_data),
                    "dimensions": [width, height],
                    "runtime_asset_rom_start_hex": texture["runtime_asset_rom_start_hex"],
                    "compressed_stream_rom_offset_hex": texture["compressed_stream_rom_offset_hex"],
                    "tile_state": tile,
                    "mtl_mapping": mapping,
                }
            )
        records.append(record)
    return "\n".join(lines) + "\n", records


def _build_obj_and_report(
    model: Any,
    textures: dict[int, dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    lines = [
        "# Prop 220 Boy textured static raw-XYZ export",
        "# No bind pose, bone transform, animation, normals, or unknown texture decoding.",
        "# VERIFIED RGBA16 corner UV: u=raw_s/(32*W), v=1-raw_t/(32*H).",
        "mtllib boy-runtime-textured.mtl",
        "o Boy_Prop_0220_TEXTURED_STATIC_EXPERIMENTAL",
    ]
    lines.extend(f"v {vertex.x} {vertex.y} {vertex.z}" for vertex in model.vertices)

    group_records: list[dict[str, Any]] = []
    face_records: list[dict[str, Any]] = []
    vt_count = 0
    all_u: list[float] = []
    all_v: list[float] = []
    runtime_faces = textured_faces = unknown_faces = 0
    textured_groups = unknown_groups = untextured_groups = 0
    cull_flags: Counter[str] = Counter()

    for group in model.groups:
        if group.runtime_skipped:
            continue
        following = _following_group(model, group.index)
        texture = None if group.texture_index == 0xFF else textures[group.texture_index]
        verified = bool(texture and texture["verified_rgba16_match"])
        material = _material_name(group.texture_index, texture)
        triangles = _group_triangles(model, group)
        nondegenerate = [triangle for triangle in triangles if not _is_degenerate(model, group, triangle)]
        if len(nondegenerate) != len(triangles):
            raise BoyExportError(f"Active group {group.index} unexpectedly contains a degenerate face.")
        if verified:
            textured_groups += 1
            textured_faces += len(nondegenerate)
            tile = _tile_state(texture)
            width, height = texture["runtime_width"], texture["runtime_height"]
            texture_status = "VERIFIED RGBA16"
        elif texture is None:
            untextured_groups += 1
            tile = None
            width = height = None
            texture_status = "NO TEXTURE"
        else:
            unknown_groups += 1
            unknown_faces += len(nondegenerate)
            tile = None
            width = height = None
            texture_status = "UNKNOWN FORMAT"
        runtime_faces += len(nondegenerate)

        lines.extend(("", f"g boy_group_{group.index:03d}", f"usemtl {material}", "s off"))
        group_face_start = len(face_records)
        for triangle in nondegenerate:
            absolute_indices = [group.vertex_start + index for index in triangle.local_indices]
            if any(index < 0 or index >= len(model.vertices) for index in absolute_indices):
                raise BoyExportError(f"Group {group.index} has an invalid OBJ vertex index.")
            flag_key = f"0x{triangle.flag:02X}"
            cull_flags[flag_key] += 1
            face: dict[str, Any] = {
                "triangle_index": triangle.index,
                "group_index": group.index,
                "material": material,
                "texture_status": texture_status,
                "triangle_flag_hex": flag_key,
                "bit_0x40_disables_backface_culling": bool(triangle.flag & 0x40),
                "local_vertex_indices": list(triangle.local_indices),
                "obj_vertex_indices": [index + 1 for index in absolute_indices],
                "raw_corner_st": [list(pair) for pair in triangle.corner_pairs],
                "obj_vt_indices": None,
                "obj_uv": None,
            }
            if verified:
                assert width is not None and height is not None
                vt_indices: list[int] = []
                uv: list[list[float]] = []
                for raw_s, raw_t in triangle.corner_pairs:
                    u = raw_s / (32 * width)
                    v = 1.0 - raw_t / (32 * height)
                    vt_count += 1
                    vt_indices.append(vt_count)
                    uv.append([u, v])
                    all_u.append(u)
                    all_v.append(v)
                    lines.append(f"vt {u:.9f} {v:.9f}")
                face["obj_vt_indices"] = vt_indices
                face["obj_uv"] = uv
                tokens = [f"{vertex}/{vt}" for vertex, vt in zip(face["obj_vertex_indices"], vt_indices)]
            else:
                tokens = [str(vertex) for vertex in face["obj_vertex_indices"]]
            lines.append("f " + " ".join(tokens))
            face_records.append(face)

        group_records.append(
            {
                "group_index": group.index,
                "group_record_texture_index": group.texture_index,
                "material": material,
                "texture_status": texture_status,
                "texture_id_hex": None if texture is None else texture["texture_id_hex"],
                "verified_png": None if not verified else texture["verified_rgba16_png"],
                "dimensions": None if not verified else [width, height],
                "tile_state": tile,
                "vertex_range": [group.vertex_start, following.vertex_start],
                "triangle_range": [group.triangle_start, following.triangle_start],
                "exported_faces": len(nondegenerate),
                "face_record_range": [group_face_start, len(face_records)],
                "triangle_flag_counts": dict(sorted(Counter(f"0x{triangle.flag:02X}" for triangle in nondegenerate).items())),
            }
        )

    counts = {
        "stored_vertices": len(model.vertices),
        "active_groups": len(group_records),
        "runtime_skipped_groups": sum(group.runtime_skipped for group in model.groups),
        "runtime_faces": runtime_faces,
        "textured_verified_rgba16_groups": textured_groups,
        "textured_verified_rgba16_faces": textured_faces,
        "unknown_format_groups": unknown_groups,
        "unknown_format_faces": unknown_faces,
        "untextured_groups": untextured_groups,
        "obj_v_records": len(model.vertices),
        "obj_vt_records": vt_count,
        "triangle_flag_counts": dict(sorted(cull_flags.items())),
    }
    expected = {
        "active_groups": EXPECTED_ACTIVE_GROUPS,
        "runtime_skipped_groups": 17,
        "runtime_faces": EXPECTED_RUNTIME_FACES,
        "textured_verified_rgba16_groups": EXPECTED_TEXTURED_GROUPS,
        "textured_verified_rgba16_faces": EXPECTED_TEXTURED_FACES,
        "unknown_format_groups": EXPECTED_UNKNOWN_GROUPS,
        "unknown_format_faces": EXPECTED_UNKNOWN_FACES,
        "untextured_groups": 0,
        "obj_v_records": 660,
        "obj_vt_records": EXPECTED_TEXTURED_FACES * 3,
    }
    if any(counts[key] != value for key, value in expected.items()):
        raise BoyExportError(f"Pinned Boy textured-export counts differ: {counts}")
    uv_range = {
        "u_min": min(all_u),
        "u_max": max(all_u),
        "v_min": min(all_v),
        "v_max": max(all_v),
    }
    if not (uv_range["u_min"] < 0 or uv_range["u_max"] > 1 or uv_range["v_min"] < 0 or uv_range["v_max"] > 1):
        raise BoyExportError("Pinned Boy no longer demonstrates unclamped UV output.")
    return "\n".join(lines) + "\n", group_records, face_records, {"counts": counts, "uv_range": uv_range}


def _validate_obj(obj: str, faces: list[dict[str, Any]], vertex_count: int) -> dict[str, Any]:
    lines = obj.splitlines()
    actual_v = sum(line.startswith("v ") for line in lines)
    actual_vt = sum(line.startswith("vt ") for line in lines)
    actual_faces = [line for line in lines if line.startswith("f ")]
    if actual_v != vertex_count or len(actual_faces) != len(faces):
        raise BoyExportError("OBJ record counts differ from the report.")
    for line, face in zip(actual_faces, faces):
        tokens = line.split()[1:]
        if len(tokens) != 3:
            raise BoyExportError("OBJ face is not triangular.")
        for corner, token in enumerate(tokens):
            parts = token.split("/")
            vertex = int(parts[0])
            if vertex < 1 or vertex > actual_v or vertex != face["obj_vertex_indices"][corner]:
                raise BoyExportError("OBJ vertex index validation failed.")
            if face["obj_vt_indices"] is None:
                if len(parts) != 1:
                    raise BoyExportError("Unknown-format face unexpectedly has UV indices.")
            else:
                if len(parts) != 2:
                    raise BoyExportError("Textured face is missing a UV index.")
                vt = int(parts[1])
                if vt < 1 or vt > actual_vt or vt != face["obj_vt_indices"][corner]:
                    raise BoyExportError("OBJ UV index validation failed.")
    return {
        "all_obj_v_indices_valid": True,
        "all_obj_vt_indices_valid": True,
        "corner_uv_indices_preserved": True,
    }


def _validate_group16_reference(groups: list[dict[str, Any]], faces: list[dict[str, Any]]) -> None:
    group = next(record for record in groups if record["group_index"] == REFERENCE_GROUP_INDEX)
    if group["texture_id_hex"] != "0x820D" or group["dimensions"] != [16, 16]:
        raise BoyExportError("Verified group 16 reference identity differs.")
    group_faces = [face for face in faces if face["group_index"] == REFERENCE_GROUP_INDEX]
    for face in group_faces:
        assert face["obj_uv"] is not None
        for raw, actual in zip(face["raw_corner_st"], face["obj_uv"]):
            expected = reference_group16_uv(*raw)
            if actual != [expected[0], expected[1]]:
                raise BoyExportError("Full export UV differs from the verified group 16 formula.")


def _overview(groups: list[dict[str, Any]], materials: list[dict[str, Any]]) -> str:
    lines = [
        "# Boy textured static export: material and group overview",
        "",
        "Only VERIFIED RGBA16 materials have PNG mappings. UNKNOWN formats are diagnostic untextured materials.",
        "",
        "## Materials",
        "",
        "| Material | Texture | Status | Size | S | T | Mask/Shift | PNG |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for material in materials:
        tile = material["tile_state"]
        size = "—" if "dimensions" not in material else f"{material['dimensions'][0]}×{material['dimensions'][1]}"
        s_mode = "—" if tile is None else tile["cms"]["name"]
        t_mode = "—" if tile is None else tile["cmt"]["name"]
        detail = "—" if tile is None else f"mask {tile['masks']}/{tile['maskt']}, shift {tile['shifts']}/{tile['shiftt']}"
        lines.append(
            f"| `{material['material']}` | {material['texture_id_hex'] or '—'} | {material['texture_status']} | {size} | {s_mode} | {t_mode} | {detail} | {material['png'] or '—'} |"
        )
    lines.extend(
        (
            "",
            "## Active groups",
            "",
            "| Group | Faces | Texture | Status | Triangle flags | Material |",
            "| ---: | ---: | --- | --- | --- | --- |",
        )
    )
    for group in groups:
        flags = ", ".join(f"{key}: {value}" for key, value in group["triangle_flag_counts"].items())
        lines.append(
            f"| {group['group_index']} | {group['exported_faces']} | {group['texture_id_hex'] or '—'} | {group['texture_status']} | {flags} | `{group['material']}` |"
        )
    return "\n".join(lines) + "\n"


def _blender_guide() -> str:
    return """# Blender-Prüfanleitung: Prop 220 Boy

1. Importiere `boy-runtime-textured.obj` über **File → Import → Wavefront
   (.obj)**. Die zugehörige MTL muss im selben Verzeichnis bleiben.
2. Prüfe, ob Blender die 14 referenzierten PNGs automatisch findet. Sie
   liegen relativ unter `../rgba16-us-verified/png/`.
3. Alle verwendeten RGBA16-Materialien haben in JFG Clamp auf S und T. Falls
   der OBJ-Importer die MTL-Option `-clamp on` ignoriert, stelle bei den
   Image-Texture-Nodes **Extension = Extend** ein. Verwende nicht Repeat.
4. Belasse die UVs außerhalb `0..1`. Diese Werte sind absichtlich erhalten
   und werden durch den JFG-Tilezustand geklemmt.
5. Aktiviere Material Preview oder Rendered View. Das OBJ enthält keine
   Normalen; für eine reine UV-Prüfung kann ein unbeleuchteter beziehungsweise
   Emission-basierter Materialaufbau die Texturen deutlicher zeigen.

Visuell zu prüfen sind:

- Orientierung: Schrift- oder Gesichtsdetails dürfen weder vertikal gespiegelt
  noch um 90 Grad vertauscht sein;
- UV-Seams: Übergänge an gemeinsam genutzten XYZ-Vertices dürfen die pro
  Triangle-Corner gespeicherten UVs nicht zusammenziehen;
- Materialgrenzen: Gruppen mit verschiedenen Texture-IDs müssen an ihren
  tatsächlichen Grenzen wechseln;
- Projektion: stark gestreckte, versetzte oder an falsche Ränder geklemmte
  Bereiche separat notieren;
- UNKNOWN-Gruppen 79, 80 und 81 müssen als untexturierte Diagnosematerialien
  erscheinen. Ihnen darf kein RGBA16-PNG zugeordnet sein.

Noch nicht visuell verbindlich sind Silhouette und Lage einzelner Teile. Die
XYZ-Werte werden ohne Bone-, Rest- oder Bind-Pose-Transformation exportiert.
OBJ/MTL bildet außerdem RDP-Filterung und das per Triangle gesetzte
Backface-Culling-Bit nicht vollständig ab. Die exakten Flags stehen im JSON-
Report; die Geometrie wurde dafür nicht verändert oder dupliziert.
"""


def build_textured_boy_artifacts(
    boy_data: bytes,
    rom: bytes,
    texture_manifest: Path,
    output_dir: Path,
) -> dict[str, bytes]:
    model = parse_boy(boy_data)
    resolutions, textures = resolve_boy_textures(model, rom, texture_manifest)
    obj, groups, faces, summary = _build_obj_and_report(model, textures)
    mtl, materials = _build_materials(model, textures, texture_manifest, output_dir)
    obj_validation = _validate_obj(obj, faces, len(model.vertices))
    _validate_group16_reference(groups, faces)

    verified_materials = [material for material in materials if material["texture_status"] == "VERIFIED RGBA16"]
    if len(verified_materials) != EXPECTED_VERIFIED_TEXTURES:
        raise BoyExportError("Unexpected number of used verified RGBA16 materials.")
    unknown_materials = [material for material in materials if material["texture_status"] == "UNKNOWN FORMAT"]
    if [material["texture_id_hex"] for material in unknown_materials] != ["0x9A00", "0x874E", "0x874C"]:
        raise BoyExportError("Unexpected unknown-format material set.")
    tile_variants = {
        json.dumps(material["tile_state"], sort_keys=True)
        for material in verified_materials
    }
    if len(tile_variants) != 1:
        raise BoyExportError("Pinned verified Boy textures no longer share one tile-state variant.")

    report = {
        "schema_version": 1,
        "scope": "Prop 220 Boy: active runtime groups, static raw XYZ, verified RGBA16 textures only",
        "status": "EXPERIMENTAL textured static exporter",
        "input": {
            "boy_prop_id": 220,
            "boy_sha256": BOY_SHA256,
            "powerboy_processed": False,
            "rom_identity": "US Z64, 33,554,432 bytes, SHA-1 493ced9008dbe932d6e91179b68e8630cf23a023",
        },
        **summary,
        "uv_formula": {
            "texel_s": "raw_s / 32",
            "texel_t": "raw_t / 32",
            "obj_u": "raw_s / (32 * texture_width)",
            "obj_v": "1 - raw_t / (32 * texture_height)",
            "artificial_clamping_applied": False,
            "corner_semantics": "one OBJ vt record per textured triangle corner",
        },
        "materials": materials,
        "groups": groups,
        "faces": faces,
        "texture_resolution_records": resolutions,
        "validation": {
            **obj_validation,
            "group16_uv_matches_verified_single_group_test": True,
            "all_referenced_pngs_exist_and_decode": True,
            "material_png_assignments_match_verified_texture_records": True,
            "unknown_formats_not_exported_as_rgba16": True,
            "active_and_skipped_group_counts_match": True,
            "uv_values_not_artificially_clamped": True,
            "powerboy_processed": False,
            "deterministic_regeneration_match": True,
        },
        "limitations": [
            "raw stored XYZ only; no bone, rest-pose, bind-pose, or animation transform",
            "OBJ/MTL cannot transport per-triangle bit 0x40 culling state; it remains report metadata",
            "OBJ/MTL cannot guarantee pixel-identical N64 RDP filtering in Blender",
            "Texture IDs 0x9A00, 0x874E, and 0x874C remain UNKNOWN and receive no PNG mapping",
            "unknown four-byte vertex attributes remain uninterpreted",
        ],
    }
    artifacts = {
        "boy-runtime-textured.obj": obj.encode(),
        "boy-runtime-textured.mtl": mtl.encode(),
        "boy-textured-export-report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
        "materials-and-groups.md": _overview(groups, materials).encode(),
        "BLENDER.md": _blender_guide().encode(),
    }
    return artifacts


def export_textured_boy(
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
    boy_data = boy_path.read_bytes()
    rom = rom_path.read_bytes()
    first = build_textured_boy_artifacts(boy_data, rom, texture_manifest, output_dir)
    second = build_textured_boy_artifacts(boy_data, rom, texture_manifest, output_dir)
    if first != second:
        raise BoyExportError("Textured Boy artifact generation is not deterministic.")
    output_dir.mkdir(parents=False)
    for name, data in first.items():
        (output_dir / name).write_bytes(data)
    return json.loads(first["boy-textured-export-report.json"])
