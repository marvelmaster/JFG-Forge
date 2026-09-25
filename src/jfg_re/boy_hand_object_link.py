"""Pinned runtime lookup for Boy's player-control +0x5CC object.

This module answers one narrow question for the US ROM: whether object entry
0xF7 / runtime behaviour 0x59 loads Prop 309 ``JunoHand``.  It deliberately
does not infer a general object-header or attachment format.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_export import ASSET_DATA_START, ASSET_LUT_START, BoyExportError, _asset_lut, _asset_range
from jfg_re.boy_missing_hand_analysis import JUNOHAND_SHA256, JUNOHAND_SIZE
from jfg_re.props import validate_rom_identity


OBJECT_ID = 0xF7
OBJECT_TRANSLATION_ASSET = 48
OBJECT_HEADER_TABLE_ASSET = 46
OBJECT_HEADER_DATA_ASSET = 47
EXPECTED_HEADER_ID = 232
EXPECTED_BEHAVIOUR_ID = 0x59
EXPECTED_MODEL_ID = 343
CLUSTER_SHA256 = "2b8a04547723c27def6d3145ae81a113dee745bd355bb7d22d96f3147bbd8cff"
CLUSTER_SIZE = 1104


def _asset(rom: bytes, index: int) -> tuple[int, int, bytes]:
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, index)
    return start, end, rom[start:end]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _instruction(rom: bytes, vram: int) -> int:
    rom_offset = vram - 0x80000400 + 0x1000
    return _u32(rom, rom_offset)


def _header_offsets(table: bytes) -> list[int]:
    result: list[int] = []
    for offset in range(0, len(table), 4):
        value = _u32(table, offset)
        if value == 0xFFFFFFFF:
            break
        result.append(value)
    return result


def _model_ids(header: bytes) -> tuple[int, int, list[int]]:
    model_type = header[0x1E]
    count = header[0x1F]
    relative_offset = _u32(header, 0x30)
    if relative_offset + count * 4 > len(header):
        raise BoyExportError("Object-header model list is outside its pinned header.")
    return model_type, relative_offset, list(struct.unpack_from(f">{count}I", header, relative_offset))


def _object_definitions_using_model(rom: bytes, model_id: int) -> list[dict[str, Any]]:
    table_start, _, table = _asset(rom, OBJECT_HEADER_TABLE_ASSET)
    data_start, _, data = _asset(rom, OBJECT_HEADER_DATA_ASSET)
    translation_start, _, translation = _asset(rom, OBJECT_TRANSLATION_ASSET)
    offsets = _header_offsets(table)
    translation_values = struct.unpack(f">{len(translation) // 2}h", translation)
    result = []
    for header_id in range(len(offsets) - 1):
        header = data[offsets[header_id] : offsets[header_id + 1]]
        if len(header) < 0x34:
            continue
        try:
            model_type, model_list_offset, model_ids = _model_ids(header)
        except BoyExportError:
            continue
        if model_id not in model_ids:
            continue
        object_ids = [index for index, value in enumerate(translation_values) if value == header_id]
        result.append(
            {
                "object_definition_id": header_id,
                "object_ids": object_ids,
                "object_ids_hex": [f"0x{value:X}" for value in object_ids],
                "behaviour_id": struct.unpack_from(">H", header, 0x1C)[0],
                "behaviour_id_hex": f"0x{struct.unpack_from('>H', header, 0x1C)[0]:X}",
                "model_type": model_type,
                "model_list_relative_offset_hex": f"0x{model_list_offset:X}",
                "model_ids": model_ids,
                "header_rom_range": [data_start + offsets[header_id], data_start + offsets[header_id + 1]],
                "header_table_entry_rom_offset": table_start + header_id * 4,
                "translation_entry_rom_offsets": [translation_start + value * 2 for value in object_ids],
            }
        )
    return result


def _cross(points: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    a = tuple(points[1][axis] - points[0][axis] for axis in range(3))
    b = tuple(points[2][axis] - points[0][axis] for axis in range(3))
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _parse_cluster(data: bytes) -> dict[str, Any]:
    if len(data) != CLUSTER_SIZE or hashlib.sha256(data).hexdigest() != CLUSTER_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 343 Cluster binary.")
    if not data.startswith(b"Cluster\0"):
        raise BoyExportError("Pinned Prop 343 internal name differs.")
    texture_count = data[0x10]
    vertex_count, triangle_count, group_count = struct.unpack_from(">hhh", data, 0x12)
    texture_start, vertex_start, triangle_start, group_start = (_u32(data, offset) for offset in (0x18, 0x1C, 0x20, 0x24))
    vertices = [struct.unpack_from(">hhh", data, vertex_start + index * 10) for index in range(vertex_count)]
    groups = []
    boundaries = []
    for index in range(group_count + 1):
        offset = group_start + index * 16
        boundaries.append((struct.unpack_from(">H", data, offset + 6)[0], struct.unpack_from(">H", data, offset + 8)[0]))
        if index < group_count:
            groups.append(
                {
                    "group_index": index,
                    "texture_record_index": data[offset],
                    "matrix_ids": list(data[offset + 1 : offset + 4]),
                    "matrix_splits": list(data[offset + 4 : offset + 6]),
                    "vertex_start": boundaries[-1][0],
                    "triangle_start": boundaries[-1][1],
                    "render_flags_hex": f"0x{_u32(data, offset + 12):08X}",
                }
            )
    valid = degenerate = 0
    for group_index in range(group_count):
        vertex_base, triangle_base = boundaries[group_index]
        vertex_end, triangle_end = boundaries[group_index + 1]
        local = vertices[vertex_base:vertex_end]
        for triangle_index in range(triangle_base, triangle_end):
            offset = triangle_start + triangle_index * 16
            indices = data[offset + 1 : offset + 4]
            if any(index >= len(local) for index in indices):
                raise BoyExportError("Prop 343 contains an out-of-range local triangle index.")
            points = [local[index] for index in indices]
            if _cross(points) == (0, 0, 0):
                degenerate += 1
            else:
                valid += 1
    texture_ids = [struct.unpack_from(">H", data, texture_start + index * 8 + 6)[0] for index in range(texture_count)]
    return {
        "prop_id": EXPECTED_MODEL_ID,
        "internal_name": "Cluster",
        "size_bytes": len(data),
        "sha256": CLUSTER_SHA256,
        "texture_record_count": texture_count,
        "texture_ids": texture_ids,
        "texture_ids_hex": [f"0x{value:04X}" for value in texture_ids],
        "vertex_count": vertex_count,
        "triangle_record_count": triangle_count,
        "geometrically_valid_triangle_count": valid,
        "geometrically_degenerate_triangle_count": degenerate,
        "group_count": group_count,
        "groups": groups,
        "all_groups_admitted_by_0x400_test": all(int(group["render_flags_hex"], 16) & 0x400 == 0 for group in groups),
        "transform_record_count": data[0x4F],
        "matrix_ids_used_by_groups": sorted({matrix_id for group in groups for matrix_id in group["matrix_ids"] if matrix_id != 0xFF}),
        "local_bbox": {
            "minimum": [min(vertex[axis] for vertex in vertices) for axis in range(3)],
            "maximum": [max(vertex[axis] for vertex in vertices) for axis in range(3)],
        },
    }


def build_report(rom: bytes, cluster_data: bytes, junohand_data: bytes) -> dict[str, Any]:
    if len(junohand_data) != JUNOHAND_SIZE or hashlib.sha256(junohand_data).hexdigest() != JUNOHAND_SHA256:
        raise BoyExportError("Input is not the pinned US Prop 309 JunoHand binary.")
    translation_start, translation_end, translation = _asset(rom, OBJECT_TRANSLATION_ASSET)
    header_table_start, header_table_end, header_table = _asset(rom, OBJECT_HEADER_TABLE_ASSET)
    header_data_start, header_data_end, header_data = _asset(rom, OBJECT_HEADER_DATA_ASSET)
    header_id = struct.unpack_from(">h", translation, OBJECT_ID * 2)[0]
    offsets = _header_offsets(header_table)
    header = header_data[offsets[header_id] : offsets[header_id + 1]]
    behaviour_id = struct.unpack_from(">H", header, 0x1C)[0]
    model_type, model_list_offset, model_ids = _model_ids(header)
    if (header_id, behaviour_id, model_ids) != (EXPECTED_HEADER_ID, EXPECTED_BEHAVIOUR_ID, [EXPECTED_MODEL_ID]):
        raise BoyExportError("Pinned 0xF7 object-definition chain differs.")

    expected_instructions = {
        "0x80005F30": 0x84820000,
        "0x80005FBC": 0x8D4A2CF8,
        "0x80006068": 0x0C00131D,
        "0x800061BC": 0x806F001F,
        "0x800062BC": 0x8C6E0030,
        "0x800062CC": 0x0C00EE7A,
        "0x8000F03C": 0x85CF001C,
        "0x8000F044": 0xA48F0048,
        "0x80038870": 0x0C00ED06,
        "0x80038930": 0x0C00E742,
        "0x80039D7C": 0x241900F7,
        "0x80039DA4": 0xA7B9002C,
        "0x80039E48": 0x0C0017C5,
        "0x80039E70": 0xAE0205CC,
        "0x800330E0": 0x8E0205CC,
        "0x80033108": 0x0C00ED06,
    }
    for address, expected in expected_instructions.items():
        if _instruction(rom, int(address, 16)) != expected:
            raise BoyExportError(f"Pinned instruction differs at {address}.")

    object_chain = {
        "object_entry_id": OBJECT_ID,
        "object_entry_id_hex": "0xF7",
        "translation_table": {
            "asset_index": OBJECT_TRANSLATION_ASSET,
            "rom_range": [translation_start, translation_end],
            "rom_range_hex": [f"0x{translation_start:X}", f"0x{translation_end:X}"],
            "entry_rom_offset": translation_start + OBJECT_ID * 2,
            "entry_rom_offset_hex": f"0x{translation_start + OBJECT_ID * 2:X}",
            "entry_value_object_definition_id": header_id,
        },
        "object_definition": {
            "id": header_id,
            "offset_table_asset_index": OBJECT_HEADER_TABLE_ASSET,
            "offset_table_rom_range": [header_table_start, header_table_end],
            "offset_table_entry_rom_offset": header_table_start + header_id * 4,
            "relative_range": [offsets[header_id], offsets[header_id + 1]],
            "data_asset_index": OBJECT_HEADER_DATA_ASSET,
            "data_asset_rom_range": [header_data_start, header_data_end],
            "header_rom_range": [header_data_start + offsets[header_id], header_data_start + offsets[header_id + 1]],
            "header_sha256": hashlib.sha256(header).hexdigest(),
            "behaviour_id": behaviour_id,
            "behaviour_id_hex": f"0x{behaviour_id:02X}",
            "model_type": model_type,
            "model_count": header[0x1F],
            "model_list_relative_offset": model_list_offset,
            "model_list_rom_offset": header_data_start + offsets[header_id] + model_list_offset,
            "model_ids": model_ids,
        },
        "resulting_prop_id": model_ids[0],
        "resulting_prop_internal_name": "Cluster",
        "junohand_prop_309_result": "DISPROVED for object 0xF7 / behaviour 0x59",
    }
    return {
        "schema_version": 1,
        "scope": "US ROM object 0xF7 / behaviour 0x59 link and Boy matrix-6 position feed only",
        "asset_system": {"lut_rom_offset_hex": f"0x{ASSET_LUT_START:X}", "data_rom_offset_hex": f"0x{ASSET_DATA_START:X}"},
        "object_chain": object_chain,
        "actual_prop_343": _parse_cluster(cluster_data),
        "prop_309_occurs_elsewhere": _object_definitions_using_model(rom, 309),
        "code_evidence": {
            "objSetupObject": {
                "address": "0x80005F14",
                "dataflow": [
                    "0x80005F30 reads the entry ID; 0x80005FBC..0x80005FD8 indexes objindex (asset 48).",
                    "0x80006068 calls objGetObjdef with object-definition ID 232.",
                    "0x800061BC reads model count at header +0x1F; 0x800062BC reads the model-list pointer at +0x30.",
                    "0x800062CC calls modLoadModel with the first list value, 343.",
                    "0x800060B8..0x800060FC copies entry s16 XYZ at +4/+6/+8 to object float position +0x0C/+0x10/+0x14.",
                ],
            },
            "objSetup": {
                "address": "0x8000F028",
                "dataflow": "0x8000F03C reads object-header u16 +0x1C (0x0059); 0x8000F044 writes it to object s16 +0x48.",
            },
            "spawn_path": {
                "function": "func_80039AE0 (labelled shoot_Flares in the external decomp)",
                "address": "0x80039D08",
                "dataflow": [
                    "0x80039D7C/0x80039DA4 places 0xF7 in the spawn entry.",
                    "0x80039E48 calls objSetupObject; 0x80039E70 retains the result in player-control +0x5CC for character modes other than 2 and 6.",
                    "The caller at 0x80038870 first obtains XYZ through controlGetGunBarrelPos, then calls this function at 0x80038930.",
                ],
            },
            "continuous_position_update": {
                "addresses": ["0x800330E0", "0x800330F0", "0x80033100", "0x80033104", "0x80033108"],
                "dataflow": "When player-control +0x5CC is non-null, controlGetGunBarrelPos writes directly to attached object position +0x0C/+0x10/+0x14.",
            },
            "controlGetGunBarrelPos": {
                "address": "0x8003B418",
                "normal_model_path": "0x8003B454..0x8003B4A4 reads reference point 0: Boy vertex 619 / matrix 6.",
                "alternate_paths": "Depending on control flags/model availability, it uses cached player-control XYZ +0x544/+0x548/+0x54C or the player object's own XYZ.",
            },
        },
        "attachment_transform": {
            "verified_translation_chain": "Boy anim0/frame0 matrix 6 -> transformed reference vertex 619 -> model-instance reference point 0 -> controlGetGunBarrelPos -> object 0xF7 position",
            "anim0_frame0_reference_xyz_f32": [79.79156494140625, 131.83807373046875, 45.23564910888672],
            "spawn_entry_xyz_conversion": "Each float is converted to integer for entry s16 +4/+6/+8; objSetupObject converts those s16 values back to object-position f32.",
            "continuous_update_conversion": "Subsequent updates write reference-point f32 values directly to object position.",
            "orientation_inputs": "The spawn call passes player-control s16 +0x1CA and +0x1CC into entry +0x0A/+0x0C, plus weapon-specific fields.",
            "orientation_status": "UNKNOWN: the behaviour-specific consumer is overlay code; no matrix-6 orientation copy or parent matrix pointer is present in the proven base-code path.",
            "parenting_status": "No persistent matrix-6 parent relation was found; the verified link is repeated world/model-space position copying.",
            "junohand_transform_chain_exists": False,
        },
        "classification": {
            "VERIFIED": [
                "Object 0xF7 maps to object definition 232, behaviour 0x59, and sole model/Prop 343 Cluster.",
                "Prop 309 JunoHand is not loaded by the 0xF7/0x59 path.",
                "The retained +0x5CC object is repeatedly positioned through controlGetGunBarrelPos.",
                "Prop 309 appears in other object definitions, so it remains a real independently used asset.",
            ],
            "LIKELY": ["The external shoot_Flares label describes the 0x80039D08 spawn function; the label alone is not used to prove the asset chain."],
            "UNKNOWN": [
                "The complete behaviour-overlay interpretation of entry angles and weapon-specific fields for object 0xF7.",
                "Whether Prop 309 supplies a hand in a different gameplay path; the tested 0xF7/0x59 path does not.",
            ],
        },
        "diagnostic_obj_created": False,
        "diagnostic_obj_reason": "Required condition A failed: the actual object model is Prop 343, not Prop 309.",
        "juno_geometrically_complete_from_this_result": False,
        "smallest_next_test": "Trace the object-definition paths that really reference Prop 309 (object IDs 0xC7, 0x1BE and 0x205) and identify which, if any, is instantiated for Juno's missing +X hand.",
    }


def analyze(rom_path: Path, cluster_path: Path, junohand_path: Path, output_dir: Path) -> dict[str, Any]:
    rom_path = rom_path.resolve(strict=True)
    cluster_path = cluster_path.resolve(strict=True)
    junohand_path = junohand_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    validate_rom_identity(rom_path)
    args = (rom_path.read_bytes(), cluster_path.read_bytes(), junohand_path.read_bytes())
    first = json.dumps(build_report(*args), indent=2, sort_keys=True) + "\n"
    second = json.dumps(build_report(*args), indent=2, sort_keys=True) + "\n"
    if first != second:
        raise BoyExportError("Object-link analysis is not deterministic.")
    output_dir.mkdir(parents=False)
    (output_dir / "boy-hand-object-link.json").write_text(first, encoding="utf-8", newline="\n")
    return json.loads(first)
