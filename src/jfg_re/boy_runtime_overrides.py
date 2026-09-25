"""Static audit of Boy's runtime animation override list.

This module deliberately does not alter the verified animation decoder.  It
pins the relevant US-ROM instructions and records the smallest state that a
runtime capture must supply for a complete ordinary index-0 pose.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_export import BoyExportError
from jfg_re.props import EXPECTED_ROM_SIZE, EXPECTED_SHA1


MAIN_VRAM = 0x80000400
MAIN_ROM = 0x1000
OVERLAY16_VRAM = 0x01000000
OVERLAY16_ROM = 0x1F1E018
SINE_TABLE_VRAM = 0x800A7590

# Concrete instructions used by this audit. Relocated overlay calls remain
# zero in ROM; their targets are established independently by overlay 16's
# relocation table in the research note.
MAIN_WORDS = {
    0x8003215C: 0x8C970068,  # racer = object+0x68
    0x80032160: 0x240E1000,  # terminator selector
    0x80032164: 0xA6EE0240,  # initialize racer+0x240
    0x8003B4D8: 0x8C830068,  # controlPlayerTiltList: racer pointer
    0x8003B4E0: 0x24620240,  # return racer+0x240
    0x800745E0: 0x96700000,  # selector u16
    0x800745E8: 0x96750002,  # value u16
    0x800745EC: 0x3218F000,  # operation mask
    0x800745F0: 0x26730004,  # normal entry stride
    0x800745F4: 0x17010003,  # 0x1000 terminates
    0x80074610: 0x86180000,  # read decoded angle
    0x80074614: 0x02B8A820,  # additive value + decoded angle
    0x8007461C: 0xA6150000,  # store wrapped s16 angle
    0x80074630: 0x0801D178,  # replacement path
    0x80074634: 0xA6150000,  # replace decoded angle
    0x8007464C: 0x86700000,  # 0x3000 extra s16 operand
    0x80074660: 0x0000A812,  # product result
    0x80074664: 0x0015AA83,  # signed >> 10
    0x80074684: 0x2529720C,  # scale scratch at 0x800A720C
    0x80074690: 0xA6150000,  # replace scale scratch value
    0x8007478C: 0x3C013800,  # 1/32768.0 scale conversion constant
    0x8004966C: 0x00041440,  # mathSin starts with sll v0,a0,17
}

OVERLAY_WORDS = {
    0x01000020: 0x8C900068,  # racer pointer
    0x01000030: 0x260E0240,  # list start
    0x01000034: 0xAE2E0000,  # moving write pointer
    0x0100110C: 0x0C000888,  # local call to 0x01002220
    0x01001114: 0x8E0A0540,  # word containing node-6 gate
    0x0100111C: 0x000A5E40,  # test original bit 6
    0x01001120: 0x05610022,  # skip scale triplet when clear
    0x0100112C: 0x240C4024,  # node 6 scale X selector
    0x01001138: 0x24020020,  # raw scale 32
    0x010011B4: 0x3C0F0000,  # relocated deformedchars high half
    0x010011B8: 0x91EF0000,  # deformedchars byte
    0x010011C8: 0x82180189,  # racer subtype/state guard
    0x01001280: 0x35394000,  # dynamic scale operation selector
    0x010014C8: 0x240F1000,  # final list terminator
    0x010023CC: 0x82270342,  # signed pulse racer+0x342
    0x010023DC: 0x00047EC0,  # pulse << 11
    0x010023E4: 0x0C000000,  # relocated mathSin call
    0x010023FC: 0x92390343,  # unsigned shift racer+0x343
    0x01002404: 0x240C0008,  # node 1 axis 2
    0x01002410: 0x03224007,  # arithmetic shift of mathSin result
    0x01002424: 0x240D0014,  # node 3 axis 2
    0x01002498: 0x0C000000,  # second relocated mathSin call
    0x010024B8: 0x240D0006,  # node 1 axis 0
    0x010024DC: 0x240E003C,  # node 10 axis 0
    0x0100485C: 0xC4AE0004,  # movement component +4
    0x01004860: 0xC4AC0010,  # movement component +0x10
    0x0100488C: 0x460E003C,  # compare abs(+0x10), abs(+4)
    0x0100489C: 0x0C000000,  # relocated Arctanf call
    0x010048AC: 0x00029023,  # target = -Arctanf(...)
    0x010048B8: 0x8E240580,  # history accumulator
    0x010048BC: 0x0C000000,  # relocated mathDiffAngle call
    0x010048C8: 0x00027903,  # signed diff >> 4
    0x010048D4: 0xAE380580,  # update history accumulator
    0x010048EC: 0x24190044,  # node 11 axis 2 selector
    0x01004904: 0x8E2B0580,  # emitted value
}


def _main_offset(address: int) -> int:
    return MAIN_ROM + address - MAIN_VRAM


def _overlay_offset(address: int) -> int:
    return OVERLAY16_ROM + address - OVERLAY16_VRAM


def _word(rom: bytes, address: int, *, overlay: bool = False) -> int:
    offset = _overlay_offset(address) if overlay else _main_offset(address)
    return struct.unpack_from(">I", rom, offset)[0]


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def wrap_s16(value: int) -> int:
    """Match an N64 `sh` followed by a signed `lh`."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def selector_parts(selector: int) -> tuple[int, int, int, int]:
    """Return operation, byte offset, channel, and zero-based component."""
    operation = selector & 0xF000
    byte_offset = selector & 0x0FFF
    return operation, byte_offset, byte_offset // 6, byte_offset % 6 // 2


def math_sin(rom: bytes, angle: int) -> int:
    """Bit-exact integer `mathSin` lookup used by the Boy pulse producer."""
    angle &= 0xFFFFFFFF
    if _s32(angle << 17) < 0:
        angle ^= 0x7FFF
    table_index = (angle >> 3) & 0x7FE
    value = struct.unpack_from(">H", rom, _main_offset(SINE_TABLE_VRAM) + table_index)[0] << 1
    if _s32(angle << 16) < 0:
        value = -value
    return _s32(value)


def pulse_value(rom: bytes, counter_s8: int, shift_u8: int) -> int:
    """Compute `mathSin(sign_extend_s8(counter)<<11) >> shift`."""
    if not -128 <= counter_s8 <= 127 or not 0 <= shift_u8 <= 31:
        raise ValueError("pulse fields do not fit their runtime widths")
    return math_sin(rom, counter_s8 << 11) >> shift_u8


def apply_additive_angle(base_s16: int, delta_s16: int) -> int:
    return wrap_s16(base_s16 + delta_s16)


def movement_step(current: int, target: int) -> int:
    """One delta=1 update of racer+0x580, including wrapped angle diff."""
    difference = target - current
    if difference >= 0x8000:
        difference -= 0x10000
    elif difference < -0x7FFF:
        difference += 0x10000
    return _s32(current + (difference >> 4))


def _verify_rom(rom: bytes) -> tuple[dict[str, Any], list[dict[str, str]]]:
    digest = hashlib.sha1(rom).hexdigest()
    if len(rom) != EXPECTED_ROM_SIZE or digest != EXPECTED_SHA1:
        raise BoyExportError("Runtime override audit requires the pinned US Z64 ROM.")
    checked: list[dict[str, str]] = []
    for address, expected in MAIN_WORDS.items():
        actual = _word(rom, address)
        if actual != expected:
            raise BoyExportError(f"Pinned instruction differs at 0x{address:08X}.")
        checked.append({"address": f"0x{address:08X}", "word": f"0x{actual:08X}", "segment": "main"})
    for address, expected in OVERLAY_WORDS.items():
        actual = _word(rom, address, overlay=True)
        if actual != expected:
            raise BoyExportError(f"Pinned overlay instruction differs at 0x{address:08X}.")
        checked.append({"address": f"0x{address:08X}", "word": f"0x{actual:08X}", "segment": "overlay16"})
    return ({"size_bytes": len(rom), "sha1": digest, "byte_order": "Z64 / Big Endian"}, checked)


def build_override_report(rom: bytes) -> dict[str, Any]:
    identity, instructions = _verify_rom(rom)
    factors = [struct.unpack_from(">f", rom, OVERLAY16_ROM + 0x7D64 + 4 * i)[0] for i in range(6)]
    channels = [struct.unpack_from(">I", rom, OVERLAY16_ROM + 0x7D4C + 4 * i)[0] for i in range(6)]
    raw_scales = [int(value * 32768.0) for value in factors]
    initial_deformedchars = rom[_main_offset(0x800A5084)]

    node3_initial_q = pulse_value(rom, 15, 5)
    negative_residuals = [value for value in range(-15, 0) if movement_step(value, 0) == value]

    return {
        "schema_version": 1,
        "scope": "Boy / Prop 220 animation index 0 runtime override analysis",
        "rom": identity,
        "conclusion": {
            "code": "B",
            "label": "RUNTIME CAPTURE REQUIRED",
            "reason": "The always-emitted selector 0x0044 contains racer+0x580, a history-dependent smoothed angle. Static ordinary-state predicates do not select one unique value. The conditional node-6 scale triplet additionally depends on live bit 0x40 of the u32 at racer+0x540.",
            "synthetic_pose_generated": False,
        },
        "list_layout": {
            "status": "VERIFIED",
            "address": "racer+0x240",
            "initialization": "controlPlayerInit 0x80032130 writes u16 0x1000 at 0x80032164",
            "producer": "Boy overlay16 starts a moving write pointer at 0x01000030..0x01000034 and terminates it at 0x010014C4..0x010014DC",
            "consumer": "controlPlayerTiltList 0x8003B4D8 returns racer+0x240; gen_anim_data consumes it at 0x800745CC..0x800746B0",
            "normal_entry": {"offset_0": "u16 selector, big endian", "offset_2": "s16 value, big endian", "stride_bytes": 4},
            "selector": "high nibble is operation; low 12 bits are a byte offset channel*6 + zero_based_component*2",
            "operations": {
                "0x0000": "add value to decoded angle and store modulo 16 bits",
                "0x1000": "terminator; value halfword is not consumed semantically",
                "0x2000": "replace decoded angle",
                "0x3000": "weighted/additive operation consuming one extra s16 halfword",
                "0x4000": "replace scale scratch value",
                "0x5000": "copy decoded angle back into the list value slot",
            },
        },
        "angle_units": {
            "status": "VERIFIED",
            "full_turn_units": 65536,
            "degrees_per_unit": 360.0 / 65536.0,
            "storage": "s16 with modulo-65536 wrap on store",
        },
        "node3_override": {
            "status": "VERIFIED",
            "producer": "unnamed overlay16 function 0x01002220, called at 0x0100110C",
            "consumer": "gen_anim_data additive selector path 0x80074604..0x8007461C",
            "source_fields": [
                {"offset": "racer+0x342", "type": "s8", "meaning": "transient pulse counter"},
                {"offset": "racer+0x343", "type": "u8", "meaning": "arithmetic right-shift count"},
            ],
            "formula": "q = mathSin(sign_extend_s8(racer[0x342]) << 11) >> racer[0x343]; node1.component_at_+2 = wrap_s16(base + q); node3.component_at_+2 = wrap_s16(base - q)",
            "node3_operation": "ADDITIVE on the second stored Euler component (byte offset +2, zero-based index 1, angle B / Rz term in the verified matrix formula); not replacement and not blend",
            "pulse_start_example": {"counter": 15, "shift": 5, "mathSin": math_sin(rom, 15 << 11), "q": node3_initial_q, "node3_delta": -node3_initial_q},
            "decay": "0x01002458..0x0100247C subtracts caller delta and clamps at zero. With no new trigger, valid producer-created pulses reach zero in at most 15 delta=1 updates.",
        },
        "other_angles": {
            "selectors": [
                {"selector": "0x0008", "channel": 1, "component_offset": 2, "component_index0": 1, "value": "+q from racer+0x342/+0x343"},
                {"selector": "0x0014", "channel": 3, "component_offset": 2, "component_index0": 1, "value": "-q from racer+0x342/+0x343"},
                {"selector": "0x0006", "channel": 1, "component_offset": 0, "component_index0": 0, "value": "(mathSin(s8(racer+0x340)<<11) >> u8(racer+0x341)) >> 1"},
                {"selector": "0x003C", "channel": 10, "component_offset": 0, "component_index0": 0, "value": "same value as 0x0006"},
                {"selector": "0x0044", "channel": 11, "component_offset": 2, "component_index0": 1, "value": "updated racer+0x580; always emitted"},
            ],
            "movement_update": "For each caller-delta tick: racer+0x580 += mathDiffAngle(racer+0x580,target) >> 4. When abs(+0x10) < abs(+4), target=-Arctanf(racer+0x10,abs(racer+4)); otherwise target=0.",
            "history_dependence_proof": {"target": 0, "fixed_negative_residuals": negative_residuals, "note": "Arithmetic >>4 makes every value -15..-1 a fixed point at target zero, so ordinary movement inputs alone do not recover a unique accumulator."},
        },
        "scales": {
            "node6_flag_path": {
                "status": "VERIFIED",
                "activation": "(u32_be(racer+0x540) & 0x40) != 0; equivalently byte racer+0x543 bit 6",
                "selectors": ["0x4024", "0x4026", "0x4028"],
                "raw_value": 32,
                "factor_xyz": 32 / 32768.0,
                "ordinary_neutral": "UNKNOWN from static state predicates; the live bit is not established by no-firing/no-aim alone",
            },
            "deformation_path": {
                "status": "VERIFIED",
                "activation": "deformedchars != 0 and signed racer+0x189 != 2",
                "channels": channels,
                "rom_float_factors": factors,
                "raw_scale_values": raw_scales,
                "effective_factors": [value / 32768.0 for value in raw_scales],
                "node6_and_node9": "both receive XYZ raw 50790, factor 1.54998779296875, when active",
                "ordinary_neutral": "deformedchars data initializer is zero; excluding character-deformation special state makes this path inactive and leaves scale scratch zero, which gen_anim_data treats as factor 1",
                "rom_initializer": initial_deformedchars,
            },
            "ordering": "The 1/1024 node-6 triplet is appended first. If the deformation path is also active, its later node-6 50790 triplet is consumed later and replaces the same three scale-scratch values.",
        },
        "transform_layers": {
            "animation_local": "Animation 0 decodes per-node local rotations, optional scales, and model-local root translation.",
            "boy_overrides": "The selector list changes decoded local angle/scale scratch before matrix construction and therefore propagates through descendants.",
            "object_world": "modGenAnimMatrices composes the root against the supplied object matrix; this rotates/translates the complete model but does not change the relative local arm pose.",
            "camera": "view/projection is applied by the render path after model/world construction and does not rewrite Boy's 21 skeletal matrices.",
        },
        "ordinary_index0": {
            "settled_no_trigger": "The +0x340/+0x342 pulse paths can be proven zero after their bounded decay when no new trigger occurs.",
            "no_blend": "Can be selected by requiring instance+0x5E == 0.",
            "no_deformation": "Can be selected by deformedchars == 0, its ROM-initialized value.",
            "unresolved": [
                "exact s32 racer+0x580 (only its emitted low s16 affects selector 0x0044)",
                "u32 racer+0x540 bit 0x40, which controls the node-6 scale triplet",
            ],
            "why_no_static_artifact": "Choosing zero for either unresolved value would add a runtime assumption. Index 0 is not the initialization clip, so the copied/initialized value alone would not establish the value at an ordinary later index-0 frame.",
        },
        "minimal_runtime_capture": {
            "preferred": "Capture racer+0x240 from its first halfword through the 0x1000 terminator at one settled, non-blended index-0 frame, plus the normalized phase. This directly contains every override consumed by gen_anim_data.",
            "smallest_raw_unknowns_for_the_constrained_case": [
                {"field": "racer+0x580", "width": "s32", "needed_for": "selector 0x0044; low s16 is consumed"},
                {"field": "racer+0x540", "width": "u32", "needed_for": "bit 0x40 presence of node-6 scale selectors"},
            ],
            "capture_guards": ["animation index 0 / ID 1026", "instance+0x5E == 0", "deformedchars == 0", "racer+0x340 == 0", "racer+0x342 == 0"],
            "optional_context_for_world_comparison": ["object/world matrix", "the emitted 21 runtime matrices or transformed vertices as a comparison target"],
        },
        "code_evidence": {
            "checked_instruction_count": len(instructions),
            "instructions": instructions,
            "relocations": {
                "0x010023E4_and_0x01002498": "mathSin 0x8004966C",
                "0x0100489C": "Arctanf 0x80049C84",
                "0x010048BC": "mathDiffAngle 0x80049D80",
                "0x010011B4_0x010011B8": "deformedchars 0x800A5084",
            },
            "ranges": {
                "list_initialization": "0x80032130..0x80032164",
                "list_pointer": "0x8003B4D8..0x8003B4E0",
                "list_consumer": "0x800745CC..0x800746B0",
                "pulse_producer": "overlay16 0x01002220..0x0100250C",
                "movement_accumulator": "overlay16 0x01004840..0x01004930",
                "node6_scale": "overlay16 0x01001114..0x010011A8",
                "deformation_scales": "overlay16 0x010011B4..0x010014C0",
            },
        },
        "status_summary": {
            "VERIFIED": [
                "list encoding, operations, selectors, and termination",
                "node-3 additive axis-2 formula and 16-bit wrap",
                "node-11 history-dependent smoothing formula",
                "node-6 and deformation scale activation/formulas",
                "separation of animation-local, override, object/world, and camera layers",
            ],
            "LIKELY": [],
            "HYPOTHESIS": [],
            "UNKNOWN": [
                "semantic gameplay name of animation 0 / ID 1026",
                "one unique racer+0x580 value for an arbitrary ordinary index-0 frame",
                "node-6 gate bit for that same uncaptured frame",
            ],
        },
    }


def report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_report(rom_path: Path, output_path: Path) -> dict[str, Any]:
    report = build_override_report(rom_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(report_bytes(report))
    return report
