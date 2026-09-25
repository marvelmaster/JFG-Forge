"""Boy-only runtime capture specification and offline pose validator.

This module consumes one capture made immediately after ``gen_anim_data`` in
``modGenAnimMatrices``.  It deliberately leaves the verified animation
decoder unchanged and rejects missing runtime state instead of supplying
neutral defaults.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

import jfg_re.boy_animation_catalog as animation_catalog
from jfg_re.boy_anim0_frame0 import (
    _f32,
    _local_matrix_from_stored,
    _matrix_multiply,
    _sine_table,
    _transform,
)
from jfg_re.boy_anim0_temporal import _assignments, decode_time as decode_animation0_time
from jfg_re.boy_export import BONE_COUNT, BONE_START, BOY_SHA256, BoyExportError, parse_boy
from jfg_re.boy_runtime_overrides import selector_parts, wrap_s16
from jfg_re.props import EXPECTED_ROM_SIZE, EXPECTED_SHA1


CAPTURE_PC = 0x8003D908
PLAYER_LIST_POINTER = 0x800F2D0C
PLAYER_COUNT = 0x800F2D10
DELAY_DAT = 0x800A3374
INSTANCE_DUMP_SIZE = 0x80
OBJECT_MATRIX_SIZE = 0x40
SELECTOR_DUMP_SIZE = 0x80
RACER_EXTENDED_START = 0x540
RACER_EXTENDED_SIZE = 0x44
MATRIX_SIZE = 0x40
MATRIX_DUMP_SIZE = BONE_COUNT * MATRIX_SIZE
RUNTIME_MATRIX_COLUMNS = 3
RUNTIME_MATRIX_ELEMENT_COUNT = BONE_COUNT * 4 * RUNTIME_MATRIX_COLUMNS
OVERLAY16_ROM = 0x1F1E018
OVERLAY16_VRAM = 0x01000000


PINNED_WORDS = {
    0x8000E464: 0x3C0E800F,
    0x8000E468: 0x8DCE2D10,
    0x8000E470: 0xAC8E0000,
    0x8000E474: 0x8C422D0C,
    0x8003D21C: 0x27BDFF10,
    0x8003D238: 0xAFA600F8,
    0x8003D240: 0x8CC70068,
    0x8003D248: 0xAFA70074,
    0x8003D3C8: 0x8289000B,
    0x8003D3D0: 0x392A0001,
    0x8003D3D4: 0xA28A000B,
    0x8003D3D8: 0x828E000B,
    0x8003D3E8: 0x8D8D0010,
    0x8003D3F0: 0xAFAD00D0,
    0x8003D3F8: 0xC6840038,
    0x8003D404: 0x8DE80018,
    0x8003D408: 0x868A005E,
    0x8003D8F4: 0x27A400D0,
    0x8003D8F8: 0x27A50090,
    0x8003D8FC: 0x26860020,
    0x8003D900: 0x0C01CFA0,
    0x8003D908: 0x9268002D,
    0x800457CC: 0xAC223374,
}

OVERLAY_WORDS = {
    0x01001634: 0x824B003A,  # model_index = s8[object+0x3A]
    0x01001638: 0x8E4A006C,  # model_array = u32[object+0x6C]
    0x0100163C: 0x000B6080,  # index * 4
    0x01001640: 0x014C7021,
    0x01001644: 0x8DC40000,  # a0 = selected model instance
    0x01001658: 0x02403025,  # a2 = object
    0x01001664: 0x8C910000,  # a1 source = static model definition
    0x01001678: 0x02202825,
    0x0100167C: 0x0C000000,  # relocation resolves to modGenAnimMatrices
}


def _main_rom_offset(address: int) -> int:
    return 0x1000 + address - 0x80000400


def _verify_rom(rom: bytes) -> list[dict[str, str]]:
    if len(rom) != EXPECTED_ROM_SIZE or hashlib.sha1(rom).hexdigest() != EXPECTED_SHA1:
        raise BoyExportError("Runtime capture validation requires the pinned US Z64 ROM.")
    evidence = []
    for address, expected in PINNED_WORDS.items():
        word = struct.unpack_from(">I", rom, _main_rom_offset(address))[0]
        if word != expected:
            raise BoyExportError(f"Pinned instruction differs at 0x{address:08X}.")
        evidence.append({"ram_address": f"0x{address:08X}", "word": f"0x{word:08X}", "segment": "main"})
    for address, expected in OVERLAY_WORDS.items():
        word = struct.unpack_from(">I", rom, OVERLAY16_ROM + address - OVERLAY16_VRAM)[0]
        if word != expected:
            raise BoyExportError(f"Pinned overlay instruction differs at 0x{address:08X}.")
        evidence.append({"overlay_link_address": f"0x{address:08X}", "word": f"0x{word:08X}", "segment": "overlay16 ROM image; not a fixed runtime breakpoint address"})
    return evidence


def capture_spec(rom: bytes) -> dict[str, Any]:
    """Return the deterministic emulator-agnostic capture contract."""
    instructions = _verify_rom(rom)
    fields = [
        ("instance", "S4", "+0x00", "0x80", "raw bytes", "animation indices, phase, blend state, buffer index/pointers"),
        ("object_world_matrix", "SP", "+0x90", "0x40", "16 big-endian f32, row-major", "exact root parent used by gen_anim_data"),
        ("object_pointer", "SP", "+0xF8", "4", "big-endian u32 pointer", "provenance and racer-chain check"),
        ("racer_pointer", "SP", "+0x74", "4", "big-endian u32 pointer", "base for selector and extended racer state"),
        ("selectors", "racer", "+0x240", "through 0x1000 terminator; dump 0x80", "big-endian u16 selector/s16 value", "all overrides consumed by gen_anim_data"),
        ("delayDat", "absolute", "0x800A3374", "4", "big-endian s32", "extended timing provenance; phase already captures pose time"),
        ("racer_extended", "racer", "+0x540", "0x44", "raw big-endian bytes", "u32 +0x540 and s32 +0x580 diagnostics"),
        ("runtime_matrices", "matrix_base", "+0x00", "0x540", "21 row-major 4x3 big-endian f32 in 0x40-byte slots", "direct numeric validation target; fourth word of each row is unused"),
    ]
    decoded_fields = [
        ("matrix_buffer_index", "instance", "+0x0B", "1", "s8", "0 or 1", "select current double buffer"),
        ("matrix_buffer_0", "instance", "+0x10", "4", "u32 pointer", "KSEG0 RAM", "first matrix-buffer pointer"),
        ("matrix_buffer_1", "instance", "+0x14", "4", "u32 pointer", "KSEG0 RAM", "second matrix-buffer pointer"),
        ("current_animation_index", "instance", "+0x24", "2", "u16", "exactly 0", "select pinned Animation 0 / ID 1026"),
        ("previous_animation_index", "instance", "+0x26", "2", "u16", "0..51 when live; may be stale with no blend", "extended transition provenance"),
        ("effective_animation_time", "instance", "+0x28", "4", "IEEE-754 f32", "inside the current clip time domain", "exact current time consumed by gen_anim_data"),
        ("unscaled_animation_time", "instance", "+0x38", "4", "IEEE-754 f32", "finite", "pre-multiplier animation time; not a normalized phase"),
        ("blend_step", "instance", "+0x5C", "2", "s16", "nonnegative in observed initialization", "extended blend provenance"),
        ("blend_counter", "instance", "+0x5E", "2", "s16", "exactly 0", "prove no-blend path"),
        ("object", "SP", "+0xF8", "4", "u32 pointer", "KSEG0 RAM", "identify exact rendered object"),
        ("racer", "SP", "+0x74", "4", "u32 pointer", "KSEG0 RAM", "locate selector and racer state"),
        ("object_type", "object", "+0x48", "2", "s16", "exactly 1", "prove player-type modGenAnimMatrices path"),
        ("selector", "racer", "+0x240 + variable", "2", "u16", "known operations; 0x1000 terminates", "select override operation/channel/component"),
        ("selector_value", "racer", "+0x242 + variable", "2", "s16", "operation-dependent", "captured runtime override value"),
        ("object_world_matrix", "SP", "+0x90", "64", "16 IEEE-754 f32", "all finite", "exact parent matrix for the hierarchy root"),
        ("racer_gate_word", "racer", "+0x540", "4", "u32", "bit 0x40 retained", "extended node-6 gate provenance"),
        ("movement_accumulator", "racer", "+0x580", "4", "s32", "full signed range", "extended source provenance for selector 0x0044"),
        ("delayDat", "absolute RAM", "0x800A3374", "4", "s32", "normally positive VI ticks", "extended timing provenance"),
        ("runtime_matrix_element", "matrix_base", "+matrix_id*0x40 + row*0x10 + column*4", "4", "IEEE-754 f32", "finite for columns 0..2; 21*12 values", "numeric decoder comparison; row fourth words are unused"),
    ]
    return {
        "schema_version": 2,
        "scope": "Prop 220 Boy, any catalogued no-blend runtime animation",
        "status": "workflow and numeric replay VERIFIED by the real index-19 / ID-1022 capture",
        "rom": {"sha1": EXPECTED_SHA1, "size_bytes": EXPECTED_ROM_SIZE, "byte_order": "Z64 / Big Endian"},
        "addresses": {
            "kinds": "0x800..... values are N64 KSEG0 virtual RAM addresses; they are not ROM file offsets",
            "exact_breakpoint_ram": "0x8003D908",
            "function": "modGenAnimMatrices 0x8003D21C; breakpoint is first instruction after gen_anim_data returns",
            "player_list_pointer_global_ram": "0x800F2D0C",
            "player_count_global_ram": "0x800F2D10",
            "delayDat_ram": "0x800A3374",
        },
        "runtime_addressing": {
            "player_list": "u32_be[0x800F2D0C] points to an array of Object*; u32_be[0x800F2D10] is its count",
            "racer": "u32_be[object+0x68]; dynamically allocated and therefore not assigned a fixed address",
            "selected_model_instance": "model_index=s8[object+0x3A]; array=u32_be[object+0x6C]; instance=u32_be[array+4*model_index]",
            "breakpoint_shortcut": "at 0x8003D908 S4 is the exact selected model instance; u32_be[SP+0xF8] is object and u32_be[SP+0x74] is racer",
        },
        "matrix_storage": {
            "buffer_index": "s8[instance+0x0B], toggled with XOR 1 before generation",
            "matrix_base": "u32_be[instance+0x10 + 4*buffer_index]",
            "layout": "21 consecutive 64-byte slots; each row stores three meaningful big-endian f32 at +0/+4/+8 and an unused fourth word; slot address = matrix_base + matrix_id*0x40",
            "size_bytes": MATRIX_DUMP_SIZE,
            "lifetime": "heap-backed double buffers persist in the model instance; at the breakpoint the selected buffer has just been fully written",
        },
        "minimum_capture": {
            "sufficient": True,
            "time_and_selectors_alone": "sufficient for animation-local matrices only after the current catalog index and no-blend state are established; insufficient for final runtime/world matrices",
            "required": [
                "instance dump: supplies animation index, exact effective time at +0x28, unscaled time at +0x38, no-blend counter, buffer index and matrix pointer",
                "selector dump through 0x1000 terminator",
                "exact object/world matrix at SP+0x90",
                "final 21 runtime 4x3 matrices in their 0x540-byte slot buffer",
                "capture PC and object/racer/instance pointers",
            ],
            "optional_but_recommended": ["host-raw word-swapped copies", "delayDat", "racer+0x540..+0x583"],
        },
        "fields": [
            {"name": name, "base": base, "offset": offset, "width": width, "interpretation": interpretation, "reason": reason}
            for name, base, offset, width, interpretation, reason in fields
        ],
        "decoded_fields": [
            {"name": name, "base": base, "offset": offset, "width_bytes": width, "big_endian_type": interpretation, "expected_or_range": expected, "reason": reason}
            for name, base, offset, width, interpretation, expected, reason in decoded_fields
        ],
        "human_actions": [
            "Run the pinned US Z64 ROM and reach the desired Boy/Juno animation in a stable no-blend frame.",
            "Set an execute breakpoint at N64 RAM 0x8003D908 and continue until it hits during Boy rendering/update.",
            "Record PC, S4 and SP. Read object=u32_be[SP+0xF8] and racer=u32_be[SP+0x74]; require s16_be[object+0x48] == 1 and visibly confirm the controlled character is Boy/Juno.",
            "Dump 0x80 bytes from S4, 0x40 bytes from SP+0x90, and 0x80 bytes from racer+0x240.",
            "Read buffer_index=s8[S4+0x0B], then matrix_base=u32_be[S4+0x10+4*buffer_index]; dump 0x540 bytes there.",
            "For extended provenance dump 0x44 bytes from racer+0x540 and 4 bytes from absolute RAM 0x800A3374.",
            "Write capture.txt plus the four required N64-order binary dumps and run validate_boy_runtime_capture.py.",
        ],
        "code_evidence": instructions,
    }


def capture_spec_bytes(rom: bytes) -> bytes:
    return (json.dumps(capture_spec(rom), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_address(value: Any, name: str) -> int:
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise BoyExportError(f"Invalid {name} address.") from exc
    else:
        raise BoyExportError(f"Missing {name} address.")
    if not 0x80000000 <= result < 0x80800000:
        raise BoyExportError(f"{name} is not an N64 KSEG0 RAM address.")
    return result


def _blob(spec: Any, base: Path, name: str, minimum: int, exact: bool = False) -> bytes:
    if not isinstance(spec, dict):
        raise BoyExportError(f"Missing {name} dump descriptor.")
    if "hex" in spec:
        try:
            data = bytes.fromhex(spec["hex"])
        except (TypeError, ValueError) as exc:
            raise BoyExportError(f"Invalid hexadecimal {name} dump.") from exc
    elif "file" in spec:
        path = (base / spec["file"]).resolve(strict=True)
        data = path.read_bytes()
        if "sha256" not in spec:
            raise BoyExportError(f"File-backed {name} dump needs a SHA-256 value.")
    else:
        raise BoyExportError(f"{name} needs either 'hex' or 'file'.")
    if exact and len(data) != minimum:
        raise BoyExportError(f"{name} must contain exactly 0x{minimum:X} bytes.")
    if not exact and len(data) < minimum:
        raise BoyExportError(f"{name} must contain at least 0x{minimum:X} bytes.")
    expected = spec.get("sha256")
    actual = hashlib.sha256(data).hexdigest()
    if expected is not None and expected.lower() != actual:
        raise BoyExportError(f"{name} SHA-256 differs from its capture descriptor.")
    return data


def _s16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def parse_selectors(data: bytes) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    offset = 0
    while offset + 2 <= len(data):
        selector = _u16(data, offset)
        operation, byte_offset, channel, component = selector_parts(selector)
        if operation == 0x1000:
            entries.append({"offset": offset, "selector": selector, "operation": operation, "terminator": True})
            return entries, offset + 2
        if offset + 4 > len(data):
            raise BoyExportError("Selector dump ends in a partial entry.")
        value = _s16(data, offset + 2)
        item: dict[str, Any] = {
            "offset": offset,
            "selector": selector,
            "operation": operation,
            "channel": channel,
            "component": component,
            "value_s16": value,
        }
        offset += 4
        if operation == 0x3000:
            if offset + 2 > len(data):
                raise BoyExportError("0x3000 selector lacks its second target offset.")
            item["target_byte_offset"] = _s16(data, offset)
            offset += 2
        if operation not in (0x0000, 0x2000, 0x3000, 0x4000, 0x5000):
            raise BoyExportError(f"Unknown selector operation 0x{operation:04X}.")
        entries.append(item)
    raise BoyExportError("Selector dump has no 0x1000 terminator.")


def apply_selectors(frame: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    angles = [channel["rotation_raw_s16_abc"][:] for channel in frame["channels"]]
    scales = [channel["scale_raw_u16_xyz"][:] for channel in frame["channels"]]

    def position(byte_offset: int) -> tuple[int, int]:
        channel, remainder = divmod(byte_offset, 6)
        if channel >= len(angles) or remainder not in (0, 2, 4):
            raise BoyExportError(f"Selector byte offset 0x{byte_offset:X} is outside Boy channel scratch.")
        return channel, remainder // 2

    for item in entries:
        if item.get("terminator"):
            break
        operation = item["operation"]
        channel, component = position(item["selector"] & 0x0FFF)
        value = item["value_s16"]
        if operation == 0x0000:
            angles[channel][component] = wrap_s16(angles[channel][component] + value)
        elif operation == 0x2000:
            angles[channel][component] = value
        elif operation == 0x3000:
            target_channel, target_component = position(item["target_byte_offset"])
            product = angles[channel][component] * value
            angles[target_channel][target_component] = wrap_s16(angles[target_channel][target_component] + (product >> 10))
        elif operation == 0x4000:
            scales[channel][component] = value & 0xFFFF
        elif operation == 0x5000:
            pass  # Runtime copies the decoded angle into the list value slot; it does not change scratch.
    for index, channel in enumerate(frame["channels"]):
        channel["rotation_raw_s16_abc"] = angles[index]
        channel["rotation_index12_abc"] = [(value & 0xFFFF) >> 4 for value in angles[index]]
        channel["rotation_degrees_signed_abc"] = [_f32(value * 360.0 / 65536.0) for value in angles[index]]
        channel["scale_raw_u16_xyz"] = scales[index]
        channel["scale_factor_xyz"] = [1.0 if value == 0 else _f32(value / 32768.0) for value in scales[index]]


def _unpack_matrix(data: bytes) -> list[list[float]]:
    """Decode the complete 4x4 object/world matrix."""
    values = struct.unpack(">16f", data)
    if not all(math.isfinite(value) for value in values):
        raise BoyExportError("Captured matrix contains NaN or infinity.")
    return [list(values[row * 4 : row * 4 + 4]) for row in range(4)]


def unpack_runtime_matrices(data: bytes) -> tuple[list[list[list[float]]], list[list[str]], int]:
    """Decode 21 JFG 4x3 affine matrices from their 0x40-byte slots.

    The fourth word in each 16-byte row is not part of the runtime affine
    matrix.  It is retained as hexadecimal diagnostics and never compared as
    a float.
    """
    if len(data) != MATRIX_DUMP_SIZE:
        raise BoyExportError(f"Runtime matrices must contain exactly 0x{MATRIX_DUMP_SIZE:X} bytes.")
    matrices: list[list[list[float]]] = []
    unused_words: list[list[str]] = []
    naive_nonfinite = 0
    for matrix_id in range(BONE_COUNT):
        slot = data[matrix_id * MATRIX_SIZE : (matrix_id + 1) * MATRIX_SIZE]
        naive_nonfinite += sum(not math.isfinite(value) for value in struct.unpack(">16f", slot))
        rows: list[list[float]] = []
        padding: list[str] = []
        for row in range(4):
            values = list(struct.unpack_from(">fff", slot, row * 0x10))
            if not all(math.isfinite(value) for value in values):
                raise BoyExportError(f"Captured runtime matrix {matrix_id} contains a non-finite 4x3 element.")
            values.append(1.0 if row == 3 else 0.0)
            rows.append(values)
            padding.append(slot[row * 0x10 + 0x0C : row * 0x10 + 0x10].hex())
        matrices.append(rows)
        unused_words.append(padding)
    return matrices, unused_words, naive_nonfinite


def _runtime_matrices(boy: bytes, frame: dict[str, Any], rom: bytes, channel_map: list[int], object_matrix: list[list[float]]) -> list[list[list[float]]]:
    table = _sine_table(rom)
    root_translation = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [*frame["root_translation_model_xyz"], 1.0]]
    root_parent = _matrix_multiply(root_translation, object_matrix)
    by_id: dict[int, list[list[float]]] = {}
    for record_index in range(BONE_COUNT):
        offset = BONE_START + record_index * 16
        parent_id, matrix_id = boy[offset], boy[offset + 1]
        channel = frame["channels"][channel_map[record_index]]
        translation = list(struct.unpack_from(">fff", boy, offset + 4))
        local = _local_matrix_from_stored(
            channel["rotation_raw_s16_abc"],
            channel["scale_raw_u16_xyz"],
            translation,
            table,
        )
        by_id[matrix_id] = _matrix_multiply(local, root_parent if parent_id == 0xFF else by_id[parent_id])
    if sorted(by_id) != list(range(BONE_COUNT)):
        raise BoyExportError("Boy matrix IDs no longer cover 0..20 exactly.")
    return [by_id[index] for index in range(BONE_COUNT)]


def _error_stats(a: list[float], b: list[float]) -> dict[str, float]:
    errors = [abs(x - y) for x, y in zip(a, b)]
    return {"maximum_absolute_error": max(errors, default=0.0), "mean_absolute_error": sum(errors) / len(errors) if errors else 0.0}


def _matrix_comparison(
    actual: list[list[list[float]]],
    expected: list[list[list[float]]],
) -> dict[str, Any]:
    per_matrix: list[dict[str, Any]] = []
    all_errors: list[float] = []
    for matrix_id, (left, right) in enumerate(zip(actual, expected, strict=True)):
        errors = [abs(left[row][column] - right[row][column]) for row in range(4) for column in range(3)]
        translation = [left[3][axis] - right[3][axis] for axis in range(3)]
        all_errors.extend(errors)
        per_matrix.append({
            "matrix_id": matrix_id,
            "max_absolute_element_error": max(errors),
            "mean_absolute_element_error": sum(errors) / len(errors),
            "translation_max_absolute_error": max(abs(value) for value in translation),
            "translation_euclidean_error": math.sqrt(sum(value * value for value in translation)),
        })
    return {
        "meaningful_elements_compared": len(all_errors),
        "maximum_absolute_error": max(all_errors),
        "mean_absolute_error": sum(all_errors) / len(all_errors),
        "matrices_with_max_error_at_most_1e-5": sum(
            item["max_absolute_element_error"] <= 1.0e-5 for item in per_matrix
        ),
        "per_matrix": per_matrix,
    }


def _variant_delta(
    left: list[list[list[float]]],
    right: list[list[list[float]]],
) -> dict[str, Any]:
    errors = [
        abs(left[matrix][row][column] - right[matrix][row][column])
        for matrix in range(BONE_COUNT)
        for row in range(4)
        for column in range(3)
    ]
    return {
        "maximum_absolute_element_delta": max(errors),
        "mean_absolute_element_delta": sum(errors) / len(errors),
        "changed_matrix_count": sum(
            any(left[matrix][row][column] != right[matrix][row][column] for row in range(4) for column in range(3))
            for matrix in range(BONE_COUNT)
        ),
    }


def _capture_text(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BoyExportError("capture.txt could not be read.") from exc
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    if not values:
        raise BoyExportError("capture.txt contains no key=value metadata.")
    return values


def _metadata_int(metadata: dict[str, str], key: str, *, required: bool = False) -> int | None:
    value = metadata.get(key)
    if value is None:
        if required:
            raise BoyExportError(f"capture.txt is missing {key}.")
        return None
    try:
        return int(value, 0)
    except ValueError as exc:
        raise BoyExportError(f"capture.txt field {key} is not an integer.") from exc


def _decode_catalog_frame(
    rom: bytes,
    animation_index: int,
    effective_time: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = animation_catalog.catalog_boy_animations(rom)
    if not 0 <= animation_index < len(catalog["animations"]):
        raise BoyExportError(f"Animation index {animation_index} is outside the Boy catalog.")
    record = catalog["animations"][animation_index]
    tables = animation_catalog._tables(rom)
    start, end = (int(value, 16) for value in record["asset43_relative_range_hex"])
    blob = tables["asset43"][start:end]
    frame = decode_animation0_time(blob, effective_time) if animation_index == 0 else animation_catalog.decode_animation_time(blob, effective_time)
    return record, frame


def validate_capture_directory(capture_dir: Path, rom: bytes, boy: bytes) -> dict[str, Any]:
    """Replay one no-blend Boy capture directory against the verified decoder.

    The required files are capture.txt, instance_n64.bin,
    object_matrix_n64.bin, selectors_n64.bin, and matrices_n64.bin. Host-raw
    and racer diagnostic files are checked when present.
    """
    _verify_rom(rom)
    parse_boy(boy)
    capture_dir = Path(capture_dir).resolve(strict=True)
    metadata = _capture_text(capture_dir / "capture.txt")
    if _metadata_int(metadata, "guest_pc", required=True) != CAPTURE_PC:
        raise BoyExportError("Capture was not taken at 0x8003D908.")

    required = {
        "instance": ("instance_n64.bin", INSTANCE_DUMP_SIZE, True),
        "object": ("object_matrix_n64.bin", OBJECT_MATRIX_SIZE, True),
        "selectors": ("selectors_n64.bin", 2, False),
        "matrices": ("matrices_n64.bin", MATRIX_DUMP_SIZE, True),
    }
    loaded: dict[str, bytes] = {}
    for key, (name, size, exact) in required.items():
        path = capture_dir / name
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise BoyExportError(f"Required capture file is unavailable: {name}") from exc
        if exact and len(data) != size:
            raise BoyExportError(f"{name} must contain exactly 0x{size:X} bytes.")
        if not exact and len(data) < size:
            raise BoyExportError(f"{name} must contain at least 0x{size:X} bytes.")
        loaded[key] = data

    instance = loaded["instance"]
    current_index, previous_index = struct.unpack_from(">HH", instance, 0x24)
    effective_time = struct.unpack_from(">f", instance, 0x28)[0]
    previous_time = struct.unpack_from(">f", instance, 0x2C)[0]
    unscaled_time = struct.unpack_from(">f", instance, 0x38)[0]
    previous_unscaled_time = struct.unpack_from(">f", instance, 0x3C)[0]
    blend_step, blend_counter = struct.unpack_from(">hh", instance, 0x5C)
    buffer_index = struct.unpack_from(">b", instance, 0x0B)[0]
    if buffer_index not in (0, 1):
        raise BoyExportError("Captured matrix buffer index is not 0 or 1.")
    matrix_pointers = struct.unpack_from(">II", instance, 0x10)
    matrix_base = matrix_pointers[buffer_index]
    metadata_base = _metadata_int(metadata, "matrix_base")
    if metadata_base is not None and metadata_base != matrix_base:
        raise BoyExportError("capture.txt matrix_base differs from the active instance buffer pointer.")
    metadata_buffer = _metadata_int(metadata, "buffer_index")
    if metadata_buffer is not None and metadata_buffer != buffer_index:
        raise BoyExportError("capture.txt buffer_index differs from the instance.")
    if blend_counter != 0:
        raise BoyExportError(
            f"Capture has blend counter {blend_counter}; the current-clip A/B/C validator requires a stable no-blend frame."
        )
    if not all(math.isfinite(value) for value in (effective_time, previous_time, unscaled_time, previous_unscaled_time)):
        raise BoyExportError("Captured animation time contains NaN or infinity.")

    catalog = animation_catalog.catalog_boy_animations(rom)
    record, base_frame = _decode_catalog_frame(rom, current_index, effective_time)
    previous_id = catalog["animations"][previous_index]["animation_id"] if 0 <= previous_index < len(catalog["animations"]) else None
    entries, consumed = parse_selectors(loaded["selectors"])
    selected_frame = copy.deepcopy(base_frame)
    apply_selectors(selected_frame, entries)

    identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    object_matrix = _unpack_matrix(loaded["object"])
    captured, unused_words, naive_nonfinite = unpack_runtime_matrices(loaded["matrices"])
    variant_a = _runtime_matrices(boy, base_frame, rom, record["channel_map"], identity)
    variant_b = _runtime_matrices(boy, selected_frame, rom, record["channel_map"], identity)
    variant_c = _runtime_matrices(boy, selected_frame, rom, record["channel_map"], object_matrix)
    no_selector_world = _runtime_matrices(boy, base_frame, rom, record["channel_map"], object_matrix)

    selector_report: list[dict[str, Any]] = []
    for item in entries:
        output = dict(item)
        if not item.get("terminator"):
            output["direct_boy_joint_ids"] = [
                joint for joint, channel in enumerate(record["channel_map"]) if channel == item["channel"]
            ]
        selector_report.append(output)

    optional: dict[str, Any] = {}
    for logical_name, host_name in (("selectors_n64.bin", "selectors_host_raw.bin"), ("matrices_n64.bin", "matrices_host_raw.bin")):
        host_path = capture_dir / host_name
        if host_path.exists():
            logical = (capture_dir / logical_name).read_bytes()
            optional[f"{host_name}_word_swap_matches"] = b"".join(
                logical[offset : offset + 4][::-1] for offset in range(0, len(logical), 4)
            ) == host_path.read_bytes()
    racer_path = capture_dir / "racer_540_n64.bin"
    if racer_path.exists():
        racer = racer_path.read_bytes()
        if len(racer) != RACER_EXTENDED_SIZE:
            raise BoyExportError("racer_540_n64.bin must contain exactly 0x44 bytes.")
        optional.update({
            "racer_plus_0x540_u32": _u32(racer, 0),
            "racer_plus_0x540_bit_0x40": bool(_u32(racer, 0) & 0x40),
            "racer_plus_0x580_s32": struct.unpack_from(">i", racer, 0x40)[0],
        })

    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(capture_dir.iterdir()) if path.is_file()}
    multiplier = effective_time / unscaled_time if unscaled_time != 0.0 else None
    return {
        "schema_version": 2,
        "status": "REAL_RUNTIME_CAPTURE",
        "scope": f"Boy / Prop 220 runtime capture, animation index {current_index} / ID {record['animation_id']}",
        "capture": {
            "directory": capture_dir.name,
            "metadata": metadata,
            "file_sha256": files,
            "matrix_base": f"0x{matrix_base:08X}",
            "optional_checks": optional,
        },
        "instance_state": {
            "buffer_index": buffer_index,
            "matrix_pointers": [f"0x{value:08X}" for value in matrix_pointers],
            "current_animation_index": current_index,
            "current_animation_id": record["animation_id"],
            "previous_animation_index": previous_index,
            "previous_animation_id": previous_id,
            "effective_current_sample_time_instance_plus_0x28": effective_time,
            "effective_previous_sample_time_instance_plus_0x2c": previous_time,
            "unscaled_current_time_instance_plus_0x38": unscaled_time,
            "unscaled_previous_time_instance_plus_0x3c": previous_unscaled_time,
            "inferred_object_plus_0x28_multiplier": multiplier,
            "blend_step_s16": blend_step,
            "blend_counter_s16": blend_counter,
            "decoded_current_sample": base_frame["current_sample"],
            "decoded_next_sample": base_frame["next_sample"],
            "fraction_10bit": base_frame["fraction_10bit"],
        },
        "object_matrix_row_major": object_matrix,
        "runtime_matrix_storage": {
            "slot_count": BONE_COUNT,
            "slot_stride_bytes": MATRIX_SIZE,
            "meaningful_element_count": RUNTIME_MATRIX_ELEMENT_COUNT,
            "meaningful_layout": "four rows; three big-endian f32 at row offsets +0/+4/+8",
            "unused_fourth_word_hex_by_matrix": unused_words,
            "nonfinite_values_if_all_16_words_are_misread_as_f32": naive_nonfinite,
        },
        "selectors": {
            "bytes_consumed_through_terminator": consumed,
            "entries": selector_report,
            "a_to_b": _variant_delta(variant_a, variant_b),
            "world_without_selectors_vs_capture": _matrix_comparison(no_selector_world, captured),
        },
        "variants": {
            "a": "current clip; no selectors; identity object matrix",
            "b": "current clip plus selectors; identity object matrix",
            "c": "current clip plus selectors plus captured object matrix",
            "a_to_b": _variant_delta(variant_a, variant_b),
            "b_to_c": _variant_delta(variant_b, variant_c),
        },
        "runtime_comparison_c": _matrix_comparison(variant_c, captured),
        "verified_runtime_rules": {
            "euler_order": "Rx(A) * Ry(C) * Rz(B)",
            "stored_to_local_matrix_arguments": "[stored[0], stored[2], stored[1]]",
            "runtime_matrix_layout": "4x3 meaningful big-endian f32 in 0x40-byte slots",
        },
    }


def import_capture(capture_path: Path, rom: bytes, boy: bytes) -> dict[str, Any]:
    _verify_rom(rom)
    parse_boy(boy)
    capture_path = capture_path.resolve(strict=True)
    try:
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BoyExportError("Capture JSON could not be read.") from exc
    if capture.get("schema_version") != 1:
        raise BoyExportError("Unsupported runtime capture schema.")
    provenance = capture.get("provenance", {})
    if provenance.get("rom_sha1", "").lower() != EXPECTED_SHA1 or provenance.get("rom_size_bytes") != EXPECTED_ROM_SIZE:
        raise BoyExportError("Capture ROM provenance does not match the pinned US ROM.")
    if int(str(provenance.get("capture_pc", "-1")), 0) != CAPTURE_PC:
        raise BoyExportError("Capture was not taken at 0x8003D908.")
    if provenance.get("target_model") != "Boy / Prop 220" or provenance.get("object_type_s16") != 1:
        raise BoyExportError("Capture provenance does not identify a player-type Boy / Prop 220 target.")
    pointers = capture.get("pointers", {})
    instance_address = _parse_address(pointers.get("instance"), "instance")
    _parse_address(pointers.get("stack_pointer"), "stack pointer")
    _parse_address(pointers.get("object"), "object")
    _parse_address(pointers.get("racer"), "racer")
    matrix_address = _parse_address(pointers.get("matrix_base"), "matrix base")
    dumps = capture.get("dumps", {})
    instance = _blob(dumps.get("instance"), capture_path.parent, "instance", INSTANCE_DUMP_SIZE, exact=True)
    object_raw = _blob(dumps.get("object_world_matrix"), capture_path.parent, "object/world matrix", OBJECT_MATRIX_SIZE, exact=True)
    selector_raw = _blob(dumps.get("selectors"), capture_path.parent, "selectors", 2)
    entries, consumed = parse_selectors(selector_raw)

    current_animation = _u16(instance, 0x24)
    previous_animation = _u16(instance, 0x26)
    effective_time = struct.unpack_from(">f", instance, 0x28)[0]
    unscaled_time = struct.unpack_from(">f", instance, 0x38)[0]
    blend_step = _s16(instance, 0x5C)
    blend_counter = _s16(instance, 0x5E)
    buffer_index = struct.unpack_from(">b", instance, 0x0B)[0]
    if blend_counter != 0:
        raise BoyExportError(f"Capture is blended: instance+0x5E is {blend_counter}, not zero.")
    if not math.isfinite(effective_time) or not math.isfinite(unscaled_time):
        raise BoyExportError("Captured animation time contains NaN or infinity.")
    if buffer_index not in (0, 1):
        raise BoyExportError("Captured matrix buffer index is not 0 or 1.")
    stored_matrix_address = _u32(instance, 0x10 + 4 * buffer_index)
    if stored_matrix_address != matrix_address:
        raise BoyExportError("matrix_base does not match the current instance double-buffer pointer.")

    record, frame = _decode_catalog_frame(rom, current_animation, effective_time)
    apply_selectors(frame, entries)
    object_matrix = _unpack_matrix(object_raw)
    offline = _runtime_matrices(boy, frame, rom, record["channel_map"], object_matrix)

    model = parse_boy(boy)
    assignments = _assignments(model)
    if len(assignments) != 638:
        raise BoyExportError(f"Expected 638 active Boy vertices, got {len(assignments)}.")
    offline_positions = {
        index: _transform(model.vertices[index], offline[matrix_id])[0]
        for index, matrix_id in assignments.items()
    }

    matrix_comparison = None
    positional_comparison = None
    if dumps.get("runtime_matrices") is not None:
        runtime_raw = _blob(dumps["runtime_matrices"], capture_path.parent, "runtime matrices", MATRIX_DUMP_SIZE, exact=True)
        captured, _, _ = unpack_runtime_matrices(runtime_raw)
        matrix_comparison = _error_stats(
            [matrix[row][column] for matrix in offline for row in range(4) for column in range(3)],
            [matrix[row][column] for matrix in captured for row in range(4) for column in range(3)],
        )
        runtime_positions = {
            index: _transform(model.vertices[index], captured[matrix_id])[0]
            for index, matrix_id in assignments.items()
        }
        positional_comparison = _error_stats(
            [value for index in sorted(assignments) for value in offline_positions[index]],
            [value for index in sorted(assignments) for value in runtime_positions[index]],
        )

    extended: dict[str, Any] = {}
    if dumps.get("racer_extended") is not None:
        racer_ext = _blob(dumps["racer_extended"], capture_path.parent, "racer extended", RACER_EXTENDED_SIZE, exact=True)
        extended["racer_plus_0x540_u32"] = _u32(racer_ext, 0)
        extended["racer_plus_0x540_bit_0x40"] = bool(_u32(racer_ext, 0) & 0x40)
        extended["racer_plus_0x580_s32"] = struct.unpack_from(">i", racer_ext, 0x40)[0]
    if dumps.get("delay_dat") is not None:
        delay = _blob(dumps["delay_dat"], capture_path.parent, "delayDat", 4, exact=True)
        extended["delayDat_s32"] = struct.unpack(">i", delay)[0]

    xs = [point[0] for point in offline_positions.values()]
    ys = [point[1] for point in offline_positions.values()]
    zs = [point[2] for point in offline_positions.values()]
    return {
        "schema_version": 1,
        "status": "REAL_RUNTIME_CAPTURE" if not capture.get("synthetic", False) else "SYNTHETIC_TEST_FIXTURE",
        "scope": f"Boy / Prop 220 animation-index-{current_animation} no-blend capture replay",
        "input": {
            "capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
            "rom_sha1": EXPECTED_SHA1,
            "boy_sha256": BOY_SHA256,
            "capture_pc": f"0x{CAPTURE_PC:08X}",
            "pointers": {key: f"0x{_parse_address(value, key):08X}" for key, value in pointers.items()},
        },
        "captured_state": {
            "current_animation_index": current_animation,
            "current_animation_id": record["animation_id"],
            "previous_animation_index": previous_animation,
            "effective_animation_time_f32": effective_time,
            "unscaled_animation_time_f32": unscaled_time,
            "blend_step_s16": blend_step,
            "blend_counter_s16": blend_counter,
            "matrix_buffer_index": buffer_index,
            "matrix_base": f"0x{matrix_address:08X}",
            "selector_bytes_consumed": consumed,
            "selector_entry_count_excluding_terminator": len(entries) - 1,
            "extended": extended,
        },
        "reconstruction": {
            "matrices": BONE_COUNT,
            "active_source_vertices_transformed": len(assignments),
            "position_bounds_f32": {"minimum": [min(xs), min(ys), min(zs)], "maximum": [max(xs), max(ys), max(zs)]},
            "matrix_comparison": matrix_comparison,
            "positional_comparison": positional_comparison,
            "runtime_matrices_present": matrix_comparison is not None,
        },
        "selectors": entries,
        "proof": {
            "when_real_capture_is_supplied": "The report tests whether the catalog-selected decoder plus the exact captured selector list and object/world matrix reproduces all 21 runtime 4x3 matrices and all 638 active vertex positions.",
            "no_defaults_invented": True,
            "packed_animation_decoder_modified": False,
            "runtime_matrix_component_mapping": "verified A/C/B storage supplied to A/B/C helper as [0,2,1]",
        },
    }


def report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
