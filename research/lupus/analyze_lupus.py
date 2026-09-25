"""Reproducible US-ROM Lupus discovery and runtime-path analysis.

This helper deliberately reuses the verified Vela/Juno compact-model and
packed-animation research implementations.  It does not add Lupus to Forge.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
VELA_RESEARCH = PROJECT_ROOT / "research" / "vela"
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(VELA_RESEARCH))

import analyze_vela_phase1 as model_helpers  # noqa: E402
import analyze_vela_phase2 as animation_helpers  # noqa: E402
from jfg_re.boy_anim0_frame0 import _asset_bytes, _transform  # noqa: E402
from jfg_re.boy_export import BoyExportError, _matrix_id, parse_model  # noqa: E402
from jfg_re.boy_hand_object_link import (  # noqa: E402
    OBJECT_HEADER_DATA_ASSET,
    OBJECT_HEADER_TABLE_ASSET,
    _asset,
    _header_offsets,
    _model_ids,
    _object_definitions_using_model,
)
from jfg_re.props import (  # noqa: E402
    PROP_DATA_BASE,
    PROP_TABLE_ENTRIES,
    PROP_TABLE_OFFSET,
    decode_prop_block,
    parse_offset_table,
    validate_rom_identity,
)


PROP_ID = 222
PROP_NAME = "Dog"
POWER_PROP_ID = 223
TRANSFORM_COUNT = 27
ANIMATION_COUNT = 24
EXPECTED_SIZE = 15_392
EXPECTED_SHA256 = "e69c897a48697d6adef3c922111ae05d2ef04c07ff800d91f5ee0d78ab90b3eb"
PLAYER_OBJECT_DEFINITION_ID = 2
POWER_OBJECT_DEFINITION_ID = 5
DOGGUN_OBJECT_DEFINITION_ID = 401
REFERENCE_ANIMATION_INDEX = 23
REFERENCE_ANIMATION_ID = 605
REFERENCE_TIME = 17.5

OVERLAY_NUMBER = 17
OVERLAY_VRAM = 0x01100000
OVERLAY_ROM = 0x1F27B48
OVERLAY_TABLE = 0x1ED2780
OVERLAY_DATA_BASE = 0x1ED3B20
OVERLAY_ROM_TABLE = 0x1ED0270
MAIN_VRAM_BASE = 0x80000450


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _name(data: bytes, start: int = 0) -> str:
    return data[start : data.index(0, start)].decode("ascii")


def _object_header(rom: bytes, header_id: int) -> tuple[int, bytes]:
    _, _, table = _asset(rom, OBJECT_HEADER_TABLE_ASSET)
    data_start, _, data = _asset(rom, OBJECT_HEADER_DATA_ASSET)
    offsets = _header_offsets(table)
    return data_start + offsets[header_id], data[offsets[header_id] : offsets[header_id + 1]]


def _child_ids(header: bytes) -> list[int]:
    count = header[0x20]
    relative_offset = _u32(header, 0x34)
    if relative_offset + count * 4 > len(header):
        raise BoyExportError("Lupus object-header child list exceeds its header.")
    return list(struct.unpack_from(f">{count}I", header, relative_offset)) if count else []


def _sections(data: bytes) -> dict[str, Any]:
    result = model_helpers._sections(data)
    reference_start = result["vertex_references"]["start"]
    transform_start = result["transforms"]["start"]
    reference_count = data[0x2D]
    reference_end = reference_start + reference_count * 4
    if reference_end > transform_start:
        raise BoyExportError("Lupus reference records overlap the transform table.")
    result["vertex_references"].update(end=reference_end, count=reference_count)
    result["pre_transform_unknown"] = {
        "start": reference_end,
        "end": transform_start,
        "size": transform_start - reference_end,
        "hex": data[reference_end:transform_start].hex(),
    }
    return result


def _transforms_and_references(data: bytes, sections: dict[str, Any]) -> dict[str, Any]:
    vertex_start = sections["vertices"]["start"]
    references = []
    for index in range(sections["vertex_references"]["count"]):
        offset = sections["vertex_references"]["start"] + index * 4
        vertex_id, matrix_id = struct.unpack_from(">HH", data, offset)
        references.append(
            {
                "record_index": index,
                "file_offset": offset,
                "vertex_id": vertex_id,
                "matrix_id": matrix_id,
                "source_xyz_s16": list(
                    struct.unpack_from(">hhh", data, vertex_start + vertex_id * 10)
                ),
                "runtime_role": (
                    "DogGun attachment-matrix selector and runtime reference point 0"
                    if index == 0
                    else "runtime-transformed reference point; higher-level purpose UNKNOWN"
                ),
            }
        )

    records = []
    for index in range(sections["transforms"]["count"]):
        offset = sections["transforms"]["start"] + index * 16
        parent_id, target_id, channel_a, channel_b = data[offset : offset + 4]
        records.append(
            {
                "record_index": index,
                "file_offset": offset,
                "parent_id": parent_id,
                "target_matrix_id": target_id,
                "channel_bytes": [channel_a, channel_b],
                "local_translation_xyz_f32": list(struct.unpack_from(">fff", data, offset + 4)),
            }
        )

    targets = {record["target_matrix_id"] for record in records}
    edges = [
        [record["parent_id"], record["target_matrix_id"]]
        for record in records
        if record["parent_id"] != 0xFF
    ]
    return {
        "vertex_references": references,
        "transform_records": records,
        "topology": {
            "roots": [record["target_matrix_id"] for record in records if record["parent_id"] == 0xFF],
            "target_ids": sorted(targets),
            "target_ids_unique": len(targets) == len(records),
            "all_parents_valid": all(
                record["parent_id"] == 0xFF or record["parent_id"] in targets
                for record in records
            ),
            "parent_before_child": all(
                record["parent_id"] == 0xFF
                or record["parent_id"] in {item["target_matrix_id"] for item in records[: record["record_index"]]}
                for record in records
            ),
            "cycle_free": _cycle_free(records),
            "edges": edges,
        },
    }


def _cycle_free(records: list[dict[str, Any]]) -> bool:
    parents = {record["target_matrix_id"]: record["parent_id"] for record in records}
    for start in parents:
        seen: set[int] = set()
        current = start
        while current != 0xFF:
            if current in seen or current not in parents:
                return False
            seen.add(current)
            current = parents[current]
    return True


def _objects(rom: bytes, prop_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    matches = _object_definitions_using_model(rom, PROP_ID)
    player = [row for row in matches if row["object_definition_id"] == PLAYER_OBJECT_DEFINITION_ID]
    if len(player) != 1:
        raise BoyExportError("Prop 222 does not resolve uniquely to playerDog definition 2.")

    player_start, player_header = _object_header(rom, PLAYER_OBJECT_DEFINITION_ID)
    _, _, player_models = _model_ids(player_header)
    player_children = _child_ids(player_header)
    power_start, power_header = _object_header(rom, POWER_OBJECT_DEFINITION_ID)
    _, _, power_models = _model_ids(power_header)
    power_children = _child_ids(power_header)
    gun_start, gun_header = _object_header(rom, DOGGUN_OBJECT_DEFINITION_ID)
    _, _, gun_models = _model_ids(gun_header)
    if player_models != [222, 798] or player_children != [401]:
        raise BoyExportError("playerDog's pinned model/child chain differs.")
    if power_models != [223] or power_children != [401]:
        raise BoyExportError("playerDogPower's pinned model/child chain differs.")
    if gun_models != list(range(320, 329)):
        raise BoyExportError("DogGun's pinned nine-slot model list differs.")

    return {
        "player": {
            "object_definition_id": PLAYER_OBJECT_DEFINITION_ID,
            "technical_name": _name(player_header, 4),
            "header_rom_start": player_start,
            "object_ids": player[0]["object_ids"],
            "model_prop_ids": player_models,
            "model_names": [prop_index[prop_id]["name"] for prop_id in player_models],
            "child_object_definition_ids": player_children,
        },
        "power_variant": {
            "object_definition_id": POWER_OBJECT_DEFINITION_ID,
            "technical_name": _name(power_header, 4),
            "header_rom_start": power_start,
            "model_prop_ids": power_models,
            "model_names": [prop_index[prop_id]["name"] for prop_id in power_models],
            "child_object_definition_ids": power_children,
        },
        "doggun": {
            "object_definition_id": DOGGUN_OBJECT_DEFINITION_ID,
            "technical_name": _name(gun_header, 4),
            "header_rom_start": gun_start,
            "behaviour_id": _u16(gun_header, 0x1C),
            "attachment_matrix_id": 16,
            "attachment_local_transform": "identity",
            "model_slots": [
                {"slot": slot, "prop_id": prop_id, "name": prop_index[prop_id]["name"]}
                for slot, prop_id in enumerate(gun_models)
            ],
            "hand_or_unarmed_fallback": "No hand/fallback-named slot is present; slot 8 is DogGrenade. Precise unarmed selection remains UNKNOWN.",
        },
    }


def _attachment_models(prop_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    bins = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins"
    for slot, prop_id in enumerate(range(320, 329)):
        matches = list(bins.glob(f"{prop_id:04d}_*.bin"))
        if len(matches) != 1:
            raise BoyExportError(f"Expected one canonical DogGun Prop {prop_id}.")
        data = matches[0].read_bytes()
        model = parse_model(data)
        faces = 0
        degenerate = 0
        matrix_ids: set[int] = set()
        for group, following in zip(model.groups, (*model.groups[1:], model.sentinel)):
            if group.runtime_skipped:
                continue
            faces += following.triangle_start - group.triangle_start
            matrix_ids.update(item for item in group.matrix_ids if item != 0xFF)
            for triangle in model.triangles[group.triangle_start : following.triangle_start]:
                points = tuple(
                    (
                        model.vertices[group.vertex_start + local].x,
                        model.vertices[group.vertex_start + local].y,
                        model.vertices[group.vertex_start + local].z,
                    )
                    for local in triangle.local_indices
                )
                degenerate += int(model_helpers._cross(points) == (0, 0, 0))
        result.append(
            {
                "slot": slot,
                "prop_id": prop_id,
                "name": prop_index[prop_id]["name"],
                "sha256": hashlib.sha256(data).hexdigest(),
                "active_triangle_records": faces,
                "active_nondegenerate_faces": faces - degenerate,
                "transform_record_count": data[0x4F],
                "active_group_matrix_ids": sorted(matrix_ids),
                "placement": "rigid model-local geometry under the external DogGun matrix",
            }
        )
    return result


def _texture_usage(data: bytes, textures: dict[str, Any]) -> dict[str, Any]:
    model = parse_model(data)
    active = Counter(group.texture_index for group in model.groups if not group.runtime_skipped)
    skipped = Counter(group.texture_index for group in model.groups if group.runtime_skipped)
    records = []
    for record in textures["records"]:
        index = record["texture_index"]
        records.append(
            {
                **record,
                "active_group_count": active[index],
                "excluded_group_count": skipped[index],
                "usage": (
                    "admitted geometry"
                    if active[index]
                    else "excluded-by-0x400 geometry only"
                    if skipped[index]
                    else "not selected by a stored group"
                ),
            }
        )
    return {**textures, "records": records}


@contextmanager
def _lupus_animation_constants() -> Iterator[None]:
    old = (
        animation_helpers.PROP_ID,
        animation_helpers.TRANSFORM_COUNT,
        animation_helpers.EXPECTED_ANIMATION_COUNT,
    )
    animation_helpers.PROP_ID = PROP_ID
    animation_helpers.TRANSFORM_COUNT = TRANSFORM_COUNT
    animation_helpers.EXPECTED_ANIMATION_COUNT = ANIMATION_COUNT
    try:
        yield
    finally:
        (
            animation_helpers.PROP_ID,
            animation_helpers.TRANSFORM_COUNT,
            animation_helpers.EXPECTED_ANIMATION_COUNT,
        ) = old


def catalog_lupus_animations(rom: bytes) -> dict[str, Any]:
    with _lupus_animation_constants():
        catalog = animation_helpers.catalog_vela_animations(rom)
    catalog["scope"] = "Prop 222 Dog: all 24 animation table entries"
    for item in catalog["animations"]:
        item["lupus_animation_index"] = item.pop("vela_animation_index")
        item["name_status"] = "No Lupus animation-name table was established; numeric index and ID only."
        item["channel_map_identity"] = item.pop("channel_map_identity_0_27")
    catalog["counts"]["with_nonidentity_channel_map"] = sum(
        not item["channel_map_identity"] for item in catalog["animations"]
    )
    return catalog


def _reference_pose(rom: bytes, data: bytes, catalog: dict[str, Any]) -> dict[str, Any]:
    record = catalog["animations"][REFERENCE_ANIMATION_INDEX]
    if record["animation_id"] != REFERENCE_ANIMATION_ID:
        raise BoyExportError("Pinned Lupus reference animation differs.")
    with _lupus_animation_constants():
        blob, lookahead = animation_helpers._animation_blob(rom, REFERENCE_ANIMATION_ID)
        frame = animation_helpers.decode_vela_animation_time(blob, REFERENCE_TIME, lookahead)
        matrices = animation_helpers.build_vela_matrices(
            data, frame, rom, record["channel_map"]
        )
        model, assignments, face_count = animation_helpers._active_assignments(data)
    matrix_by_id = {item["matrix_id"]: item["world_model_matrix"] for item in matrices}
    points = [
        _transform(model.vertices[index], matrix_by_id[matrix_id])[0]
        for index, matrix_id in sorted(assignments.items())
    ]
    origins = [item["world_model_matrix"][3][:3] for item in matrices]
    payload = b"".join(
        struct.pack(">f", value)
        for item in matrices
        for row in item["world_model_matrix"]
        for value in row
    )
    return {
        "selection_reason": (
            "Catalog index 23 uniquely uses 28 serialized channel slots with a zero scratch slot, "
            "a distinct 27-entry map, dynamic Root-Q10 Y/Z, six runtime scale streams, and non-looping interpolation."
        ),
        "catalog_index": REFERENCE_ANIMATION_INDEX,
        "animation_id": REFERENCE_ANIMATION_ID,
        "semantic_name": None,
        "time": REFERENCE_TIME,
        "interpolation": {
            "current_sample": frame["current_sample"],
            "next_sample": frame["next_sample"],
            "fraction_10bit": frame["fraction_10bit"],
        },
        "root_translation_raw_q10_xyz": frame["root_translation_raw_q10_xyz"],
        "root_translation_model_xyz": frame["root_translation_model_xyz"],
        "matrix_count": len(matrices),
        "matrix_sha256_f32be_4x4": hashlib.sha256(payload).hexdigest(),
        "all_matrices_finite": all(
            math.isfinite(value)
            for item in matrices
            for row in item["world_model_matrix"]
            for value in row
        ),
        "transformed_active_vertex_count": len(points),
        "active_triangle_record_count": face_count,
        "transformed_vertex_bbox": animation_helpers._bbox(points),
        "joint_origin_bbox": animation_helpers._bbox(origins),
        "world_matrices": matrices,
        "numeric_runtime_capture_status": "UNKNOWN; this is an isolated shared-decoder evaluation, not a live Lupus matrix capture.",
    }


def _overlay_relocation_targets(rom: bytes, offsets: list[int]) -> dict[int, int]:
    header_offset = OVERLAY_TABLE + (OVERLAY_NUMBER - 1) * 0x20
    _, relative_rom, text_size, data_size, _, reloc_size = struct.unpack_from(">iiiiiH", rom, header_offset)
    reloc_start = OVERLAY_DATA_BASE + relative_rom + text_size + data_size
    wanted = set(offsets)
    result: dict[int, int] = {}
    for index in range(reloc_size // 8):
        symbol_index, info = struct.unpack_from(">II", rom, reloc_start + index * 8)
        target_offset = (info >> 8) & 0xFFFFFF
        patch_type = (info >> 4) & 0xF
        reloc_type = info & 0xF
        if target_offset not in wanted:
            continue
        if patch_type != 4 or reloc_type != 0:
            raise BoyExportError("Expected an external JAL relocation in dog overlay.")
        entry = _u32(rom, OVERLAY_ROM_TABLE + symbol_index * 4)
        target_overlay, target_relative = entry >> 20, entry & 0xFFFFF
        if target_overlay != 0:
            raise BoyExportError("Expected dog runtime helper in the main segment.")
        result[target_offset] = MAIN_VRAM_BASE + target_relative
    if set(result) != wanted:
        raise BoyExportError("Required dog-overlay relocations were not found.")
    return result


def _overlay_word(rom: bytes, address: int) -> int:
    return _u32(rom, OVERLAY_ROM + address - OVERLAY_VRAM)


def _main_word(rom: bytes, address: int) -> int:
    return _u32(rom, 0x1000 + address - 0x80000400)


def _runtime_evidence(rom: bytes) -> dict[str, Any]:
    relocation_offsets = [0x1348, 0x1380, 0x13B8, 0x13DC, 0x5060, 0x5074]
    targets = _overlay_relocation_targets(rom, relocation_offsets)
    expected_targets = {
        0x1348: 0x8003D21C,
        0x1380: 0x8000BC28,
        0x13B8: 0x800221F0,
        0x13DC: 0x80009734,
        0x5060: 0x8001138C,
        0x5074: 0x8002B1D4,
    }
    if targets != expected_targets:
        raise BoyExportError("Dog overlay helper relocations differ from the pinned US-ROM chain.")
    overlay_pins = {
        0x01101310: 0x8D640000,
        0x01101320: 0x808D000A,
        0x01101348: 0x0C000000,
        0x01101350: 0x8FAE005C,
        0x01101380: 0x0C000000,
        0x01101384: 0x02202025,
        0x011013B8: 0x0C000000,
        0x011013DC: 0x0C000000,
        0x01105054: 0x8FA40040,
        0x01105058: 0x8FA50030,
        0x0110505C: 0x8FA6004C,
        0x01105060: 0x0C000000,
    }
    main_pins = {
        0x8003D5CC: 0x8263004F,
        0x8003D604: 0xA1EB0002,
        0x8003D908: 0x9268002D,
        0x8003D918: 0x8E6A0030,
        0x8003D924: 0x94690000,
        0x8003D958: 0x94780002,
        0x8003D994: 0x0C0122D8,
        0x8003D99C: 0x926F002D,
        0x8000BCE0: 0x8CD90030,
        0x8000BCE8: 0x972A0002,
        0x8000BCF8: 0x000A5980,
        0x8000BD00: 0x016E2021,
    }
    for address, expected in overlay_pins.items():
        if _overlay_word(rom, address) != expected:
            raise BoyExportError(f"Pinned dog-overlay instruction differs at 0x{address:08X}.")
    for address, expected in main_pins.items():
        if _main_word(rom, address) != expected:
            raise BoyExportError(f"Pinned main instruction differs at 0x{address:08X}.")
    return {
        "overlay": {
            "number": 17,
            "name": "dogControl overlay",
            "vram": "0x01100000",
            "rom_start": "0x1F27B48",
            "text_size": "0x6240",
            "data_size": "0x770",
        },
        "relocated_calls": [
            {
                "call_address": f"0x{OVERLAY_VRAM + offset:08X}",
                "target_address": f"0x{target:08X}",
                "symbol": {
                    0x1348: "modGenAnimMatrices",
                    0x1380: "objMakeGunMtx",
                    0x13B8: "lightObject",
                    0x13DC: "objAnimTextures",
                    0x5060: "objAnimDframe",
                    0x5074: "charAnimSoundTick",
                }[offset],
            }
            for offset, target in sorted(targets.items())
        ],
        "animation_path": {
            "selection_owner": "dogControl and directly connected overlay-17 helpers",
            "known_objAnimSetMove_calls": ["0x01100E08", "0x011014F8", "0x01101538"],
            "matrix_generation_call": "0x01101348 -> modGenAnimMatrices 0x8003D21C",
            "channel_map_copy": "0x8003D5CC..0x8003D618 reads model +0x4F and writes each current map byte to transform +2",
            "packed_decoder": "gen_anim_data 0x80073E80",
            "post_matrix_sequence": "objMakeGunMtx, lightObject, and objAnimTextures; no intervening write to the 27 skeletal matrix slots was found in this submission block",
        },
        "reference_points": {
            "count_loads": "0x8003D908 and 0x8003D99C read model byte +0x2D (9 for Prop 222)",
            "loop": "0x8003D918..0x8003D9AC reads each (vertex,matrix) record and transforms its XYZ into the model-instance reference-point array",
            "doggun_selector": "objMakeGunMtx 0x8000BCE0..0x8000BD00 reads reference record 0 matrix ID and copies that 0x40-byte runtime slot",
        },
        "doggun_attachment": {
            "reference_record_0": {"vertex_id": 467, "matrix_id": 16, "source_xyz_s16": [0, 0, -1]},
            "result": "DogGun_world = Lupus_matrix_16; DogGun_local = identity",
            "status": "VERIFIED through the Lupus overlay call, Prop 222 record 0, and generic objMakeGunMtx data flow",
        },
        "timing_lead": {
            "function": "func_overlay_17_01104C50_1F2C798",
            "objAnimDframe_call": "0x01105060 -> 0x8001138C",
            "arguments": "0x01105054/58/5C load a0/a1/a2 from stack +0x40/+0x30/+0x4C",
            "candidate_local_state_table": "overlay data near 0x011067C0 is referenced by the surrounding state machinery; its timing semantics are PENDING",
            "scope_boundary": "No complete 24-entry Game Timing classification was performed.",
        },
        "shared_mechanisms": {
            "Root_Q10": "APPLIES THROUGH VERIFIED SHARED RUNTIME PATH and structurally valid Lupus blobs",
            "MSB_first_packed_samples": "VERIFIED FOR LUPUS by complete structural parse",
            "signed_angle_deltas": "APPLIES THROUGH VERIFIED SHARED gen_anim_data path",
            "interpolation_10bit": "APPLIES THROUGH VERIFIED SHARED gen_anim_data path",
            "stored_A_C_B_mapping": "APPLIES THROUGH VERIFIED SHARED gen_anim_data/matrix path; no live Lupus matrix capture",
            "optional_scale_streams": "VERIFIED FOR LUPUS; all 24 entries contain six runtime scalar scale streams",
            "row_vector_hierarchy": "APPLIES THROUGH VERIFIED SHARED matrix path; no live Lupus matrix capture",
            "rigid_matrix_deformation": "VERIFIED FOR LUPUS model data and shared render path",
            "current_previous_blending": "APPLIES THROUGH VERIFIED SHARED modGenAnimMatrices path; no Lupus transition capture",
        },
    }


def _comparison() -> list[dict[str, str]]:
    return [
        {"mechanism": "compact model record format", "Juno": "VERIFIED", "Vela": "VERIFIED", "Lupus": "VERIFIED", "classification": "GENERIC VERIFIED ACROSS ALL THREE"},
        {"mechanism": "group flag 0x400 exclusion", "Juno": "VERIFIED", "Vela": "VERIFIED", "Lupus": "VERIFIED shared makeModelGfx path", "classification": "GENERIC VERIFIED ACROSS ALL THREE"},
        {"mechanism": "rigid matrix splits", "Juno": "VERIFIED", "Vela": "VERIFIED", "Lupus": "VERIFIED", "classification": "GENERIC VERIFIED ACROSS ALL THREE"},
        {"mechanism": "16-byte transforms", "Juno": "VERIFIED", "Vela": "VERIFIED", "Lupus": "VERIFIED", "classification": "GENERIC VERIFIED ACROSS ALL THREE"},
        {"mechanism": "packed animation / Root-Q10 / 10-bit interpolation", "Juno": "VERIFIED", "Vela": "VERIFIED shared path", "Lupus": "VERIFIED structure + shared path", "classification": "GENERIC VERIFIED ACROSS ALL THREE"},
        {"mechanism": "stored A/C/B rotation mapping", "Juno": "VERIFIED live capture", "Vela": "VERIFIED shared path", "Lupus": "VERIFIED shared path", "classification": "GENERIC VERIFIED ACROSS ALL THREE; only Juno has independent live numeric capture"},
        {"mechanism": "scale streams", "Juno": "present in subset", "Vela": "present in subset", "Lupus": "present in 24/24", "classification": "GENERIC FORMAT, CHARACTER-SPECIFIC USAGE"},
        {"mechanism": "child weapon object", "Juno": "BoyGun", "Vela": "GirlGun", "Lupus": "DogGun", "classification": "GENERIC ARCHITECTURE, CHARACTER-SPECIFIC MODELS"},
        {"mechanism": "reference-record-0 attachment socket", "Juno": "matrix 6", "Vela": "matrix 6", "Lupus": "matrix 16", "classification": "GENERIC MECHANISM, CHARACTER-SPECIFIC MATRIX"},
        {"mechanism": "objAnimDframe timing family", "Juno": "catalogued", "Vela": "catalogued", "Lupus": "call verified; catalog PENDING", "classification": "SHARED FUNCTION, LUPUS-SPECIFIC TIMING UNKNOWN"},
    ]


def analyze(
    rom_path: Path,
    prop_path: Path,
    texture_manifest_path: Path,
    prop_index_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    identity = validate_rom_identity(rom_path)
    rom = identity.path.read_bytes()
    data = prop_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_SIZE or digest != EXPECTED_SHA256 or not data.startswith(b"Dog\0"):
        raise BoyExportError("Input is not the pinned US Prop 222 Dog binary.")

    offsets = parse_offset_table(rom[PROP_TABLE_OFFSET : PROP_TABLE_OFFSET + PROP_TABLE_ENTRIES * 4])
    relative_start, relative_end = offsets[PROP_ID : PROP_ID + 2]
    rom_start = PROP_DATA_BASE + relative_start
    rom_end = PROP_DATA_BASE + relative_end
    declared_size, decoded = decode_prop_block(rom[rom_start:rom_end])
    if declared_size != EXPECTED_SIZE or decoded != data:
        raise BoyExportError("Canonical Dog binary differs from direct ROM decompression.")

    prop_rows = json.loads(prop_index_path.read_text(encoding="utf-8"))
    prop_index = {row["id"]: row for row in prop_rows}
    if prop_index[PROP_ID]["name"] != PROP_NAME:
        raise BoyExportError("Prop index no longer identifies Prop 222 as Dog.")

    sections = _sections(data)
    geometry = model_helpers._geometry(data)
    transforms = _transforms_and_references(data, sections)
    textures = _texture_usage(
        data, model_helpers._textures(data, rom, texture_manifest_path)
    )
    objects = _objects(rom, prop_index)
    attachments = _attachment_models(prop_index)
    runtime = _runtime_evidence(rom)
    structural = {
        "schema_version": 1,
        "scope": "Lupus discovery: canonical US Prop 222 static model, object chain, attachments, and shared runtime evidence",
        "identity": {
            "character": "Lupus",
            "internal_player_name": "playerDog",
            "prop_id": PROP_ID,
            "prop_name": PROP_NAME,
            "size_bytes": len(data),
            "sha256": digest,
            "canonical_generated_path": "data/generated/props-us-verified/bins/0222_Dog.bin",
            "rom_sha1": identity.sha1,
            "rom_container": {
                "relative_start": relative_start,
                "relative_end": relative_end,
                "relative_range_hex": [f"0x{relative_start:X}", f"0x{relative_end:X}"],
                "rom_start": rom_start,
                "rom_end": rom_end,
                "rom_range_hex": [f"0x{rom_start:X}", f"0x{rom_end:X}"],
                "compressed_size": rom_end - rom_start,
                "declared_decompressed_size": declared_size,
                "canonical_matches_rom_decompression": True,
            },
            "confidence": "VERIFIED from playerDog object definition 2, model Prop 222, internal Dog name, and canonical ROM decompression",
        },
        "variants": [
            {"prop_id": 223, "name": prop_index[223]["name"], "relationship": "playerDogPower object definition 5 primary model", "status": "VERIFIED powered player variant"},
            {"prop_id": 240, "name": prop_index[240]["name"], "relationship": "playerMultiDog model", "status": "VERIFIED table identity; runtime purpose outside this pass"},
            {"prop_id": 241, "name": prop_index[241]["name"], "relationship": "DogLod", "status": "LIKELY LOD variant from internal name"},
            {"prop_id": 246, "name": prop_index[246]["name"], "relationship": "playerMultiDogP model", "status": "VERIFIED table identity; runtime purpose outside this pass"},
            {"prop_id": 247, "name": prop_index[247]["name"], "relationship": "PowerDogLod", "status": "LIKELY LOD variant from internal name"},
        ],
        "sections": sections,
        "geometry": geometry,
        "textures": textures,
        "transform_structure": transforms,
        "objects_and_attachments": objects,
        "doggun_attachment_models": attachments,
        "runtime_evidence": runtime,
        "three_character_comparison": _comparison(),
        "confidence": {
            "canonical_Lupus_identity": "VERIFIED",
            "static_model_layout": "VERIFIED",
            "27_node_hierarchy": "VERIFIED from Prop 222",
            "generic_runtime_matrix_rules": "APPLIES THROUGH VERIFIED SHARED RUNTIME PATH; no live Lupus numeric matrix capture",
            "DogGun_matrix_16_socket": "VERIFIED",
            "reference_points_1_through_8_semantics": "UNKNOWN",
            "full_Lupus_timing_catalog": "PENDING",
        },
    }

    catalog = catalog_lupus_animations(rom)
    animation = {
        "schema_version": 1,
        "scope": "Lupus Prop 222 animation assets, complete 24-entry structural catalog, and isolated reference evaluation",
        "prop_id": PROP_ID,
        "prop_sha256": digest,
        "catalog": catalog,
        "reference_animation": _reference_pose(rom, data, catalog),
        "evidence_classification": runtime["shared_mechanisms"],
    }
    return structural, animation


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--prop", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--prop-index", type=Path, required=True)
    parser.add_argument("--structural-output", type=Path, required=True)
    parser.add_argument("--animation-output", type=Path, required=True)
    args = parser.parse_args()
    structural, animation = analyze(args.rom, args.prop, args.textures, args.prop_index)
    args.structural_output.write_bytes(json_bytes(structural))
    args.animation_output.write_bytes(json_bytes(animation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
