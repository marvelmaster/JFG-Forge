"""Reproduce the pinned-US-ROM Vela runtime timing catalogue.

This helper is deliberately limited to Girl overlay 15's animation timing
function.  It validates the factor table, jump table, dependency-producing
instructions, and the relocation of the common call to objAnimDframe, then
combines those facts with the already established Phase-2 animation catalogue.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
PHASE2_MAP = PROJECT_ROOT / "research" / "vela" / "phase2-runtime-map.json"
OUTPUT_JSON = PROJECT_ROOT / "research" / "vela" / "runtime-timing-map.json"
OUTPUT_MARKDOWN = PROJECT_ROOT / "research" / "vela" / "runtime-timing.md"

OVERLAY_NUMBER = 15
OVERLAY_VRAM = 0x00F00000
OVERLAY_ROM = 0x1F13980
TIMING_FUNCTION = 0x00F05328
FACTOR_TABLE = 0x00F0823C
JUMP_TABLE = 0x00F08848
COMMON_CALL = 0x00F05E7C
OBJ_ANIM_DFRAME = 0x8001138C

OVERLAY_TABLE_ROM = 0x1ED2780
OVERLAY_DATA_BASE_ROM = 0x1ED3B20
OVERLAY_ROM_TABLE_ROM = 0x1ED0270
SYMBOL_NAME_OFFSETS_ROM = 0x1FEB040
SYMBOL_NAMES_ROM = 0x1FED550
MAIN_VRAM_BASE = 0x80000450

ANIMATION_IDS = (
    1097, 1098, 1099, 1096, 1104, 1110, 1111, 1112, 1109, 1113, 1114,
    1102, 1107, 1100, 1101, 1115, 1090, 1091, 1092, 1093, 1094, 1095,
    1121, 1106, 1141, 1119, 1120, 1124, 1123, 1125, 1126, 1127, 1128,
    1129, 1130, 1116, 1117, 1118, 1131, 1132, 1133, 1124, 1134, 1135,
    1137, 1136, 1138, 1139, 1140, 1122, 1103, 1108, 1142,
)

# Canonical decimal spellings of the 53 big-endian f32 values at 0x00F0823C.
BASE_FACTORS = (
    0.014, 0.011, 0.008, 0.014, 0.014, 0.012, 0.02, 0.015, 0.0334,
    0.0115, 0.0115, 0.02, 0.028, 0.02, 0.005, 0.025, 0.005, 0.0075,
    0.005, 0.005, 0.005, 0.005, 0.0175, 0.005, 0.01, 0.01, 0.0334,
    0.014, 0.005, 0.014, 0.011, 0.0085, 0.0115, 0.0115, 0.005, 0.014,
    0.035, 0.02, 0.014, 0.011, 0.0085, 0.014, 0.0115, 0.0115, 0.006,
    0.006, 0.01, 0.01, 0.003, 0.02, 0.02, 0.028, 0.006,
)

CASE_TARGETS = (
    0x00F05400, 0x00F054FC, 0x00F05580, 0x00F055E4, 0x00F056D0,
    0x00F05700, 0x00F05E70, 0x00F05E70, 0x00F0573C, 0x00F05770,
    0x00F05770, 0x00F05878, 0x00F058C8, 0x00F05948, 0x00F05994,
    0x00F059C0, 0x00F059E8, 0x00F059E8, 0x00F059E8, 0x00F059E8,
    0x00F059E8, 0x00F059E8, 0x00F05ADC, 0x00F05B3C, 0x00F05E70,
    0x00F05E70, 0x00F05E70, 0x00F055E4, 0x00F059E8, 0x00F05400,
    0x00F054FC, 0x00F05580, 0x00F05770, 0x00F05770, 0x00F05994,
    0x00F05E70, 0x00F05D54, 0x00F05D8C, 0x00F05400, 0x00F054FC,
    0x00F05580, 0x00F055E4, 0x00F05770, 0x00F05770, 0x00F05B68,
    0x00F05CB8, 0x00F05E70, 0x00F05DC4, 0x00F05E04, 0x00F05ADC,
    0x00F058A0, 0x00F05908, 0x00F05C10,
)

MOVEMENT_MAX_CASES = frozenset((0x00F05400, 0x00F054FC, 0x00F05580, 0x00F055E4, 0x00F056D0))
MOVEMENT_LATERAL_CASES = frozenset((0x00F05770,))
OBJECT_ABS_CLAMPED_CASES = frozenset((0x00F05B68, 0x00F05C10))
COMBINED_MAX_CASES = frozenset((0x00F05CB8,))
STATE_FLAG_CASES = frozenset((0x00F05948,))

# Direct data-flow pins.  These are the instructions that alter the factor at
# stack +0x38, rather than merely using it for a state-transition threshold.
INSTRUCTION_PINS = {
    0x00F05344: 0xC4A40004,  # racer +0x04
    0x00F05364: 0xC5E80010,  # racer +0x10
    0x00F05384: 0xC7120020,  # object +0x20
    0x00F05408: 0x46024282,  # factor * movement_max
    0x00F05504: 0x46024282,
    0x00F05588: 0x46023202,
    0x00F055F0: 0x46025102,
    0x00F056DC: 0x46022182,
    0x00F0577C: 0x460E5102,  # factor * abs(racer+0x10)
    0x00F05954: 0x31CF0010,  # controlKeys & 0x10
    0x00F05968: 0x46042180,  # factor + factor
    0x00F05C04: 0x460C2182,  # factor * abs(object+0x20)
    0x00F05CAC: 0x460C3202,
    0x00F05D3C: 0x460C2182,  # factor * max(movement_max, object_abs)
    0x00F05D48: 0x46024282,
    0x00F05E74: 0x8FA50038,  # factor argument
    0x00F05E78: 0x8FA6005C,  # delayDat argument
    0x00F05E7C: 0x0C000000,  # relocated objAnimDframe call
}


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _overlay_offset(address: int) -> int:
    return OVERLAY_ROM + address - OVERLAY_VRAM


def _word(rom: bytes, address: int) -> int:
    return _u32(rom, _overlay_offset(address))


def _read_c_string(data: bytes, offset: int) -> str:
    end = data.index(0, offset)
    return data[offset:end].decode("ascii")


def _resolve_common_call(rom: bytes) -> dict[str, Any]:
    header = OVERLAY_TABLE_ROM + (OVERLAY_NUMBER - 1) * 0x20
    relative_rom, text_size, data_size = struct.unpack_from(">III", rom, header + 4)
    reloc_size = struct.unpack_from(">H", rom, header + 0x14)[0]
    reloc_rom = OVERLAY_DATA_BASE_ROM + relative_rom + text_size + data_size
    found = None
    for index in range(reloc_size // 8):
        symbol_index, info = struct.unpack_from(">II", rom, reloc_rom + index * 8)
        target_offset = (info >> 8) & 0xFFFFFF
        patch_type = (info >> 4) & 0xF
        reloc_type = info & 0xF
        if target_offset == COMMON_CALL - OVERLAY_VRAM:
            found = (index, symbol_index, patch_type, reloc_type)
            break
    if found is None:
        raise ValueError("The objAnimDframe relocation was not found.")
    index, symbol_index, patch_type, reloc_type = found
    ort = _u32(rom, OVERLAY_ROM_TABLE_ROM + symbol_index * 4)
    target_overlay, target_offset = (ort >> 20) & 0xFFF, ort & 0xFFFFF
    target = MAIN_VRAM_BASE + target_offset if target_overlay == 0 else None
    name_offset = _u32(rom, SYMBOL_NAME_OFFSETS_ROM + symbol_index * 4)
    name = _read_c_string(rom, SYMBOL_NAMES_ROM + name_offset)
    if (patch_type, target_overlay, target, name) != (4, 0, OBJ_ANIM_DFRAME, "objAnimDframe"):
        raise ValueError("The common timing call no longer relocates to objAnimDframe.")
    return {
        "relocation_index": index,
        "symbol_index": symbol_index,
        "patch_type": patch_type,
        "relocation_type": reloc_type,
        "symbol": name,
        "target": f"0x{target:08X}",
    }


def _classification(case: int) -> tuple[str, str, str]:
    if case in MOVEMENT_MAX_CASES:
        return "MOVEMENT_DEPENDENT", "movement_max", "base_factor * movement_max"
    if case in MOVEMENT_LATERAL_CASES:
        return "MOVEMENT_DEPENDENT", "movement_lateral", "base_factor * movement_lateral"
    if case in OBJECT_ABS_CLAMPED_CASES:
        return (
            "MOVEMENT_DEPENDENT",
            "object_abs_clamped",
            "base_factor * max(1.0, abs(object+0x20))",
        )
    if case in COMBINED_MAX_CASES:
        return (
            "MOVEMENT_DEPENDENT",
            "combined_max",
            "base_factor * max(movement_max, abs(object+0x20))",
        )
    if case in STATE_FLAG_CASES:
        return (
            "STATE_DEPENDENT",
            "controlKeys_bit_0x10_double",
            "base_factor * (2.0 if controlKeys bit 0x10 is set else 1.0)",
        )
    return "FIXED", "fixed", "base_factor"


def analyze(rom: bytes, phase2: dict[str, Any]) -> dict[str, Any]:
    for address, expected in INSTRUCTION_PINS.items():
        actual = _word(rom, address)
        if actual != expected:
            raise ValueError(f"Pinned timing instruction differs at 0x{address:08X}.")

    raw_factors = rom[_overlay_offset(FACTOR_TABLE):_overlay_offset(FACTOR_TABLE) + 53 * 4]
    factors = struct.unpack(">53f", raw_factors)
    for index, (actual, expected) in enumerate(zip(factors, BASE_FACTORS, strict=True)):
        if abs(actual - expected) > 1e-8:
            raise ValueError(f"Vela timing factor {index} differs from its pinned value.")

    raw_targets = struct.unpack_from(">53I", rom, _overlay_offset(JUMP_TABLE))
    targets = tuple(OVERLAY_VRAM + target for target in raw_targets)
    if targets != CASE_TARGETS:
        raise ValueError("Vela timing jump table differs from the pinned catalogue.")

    animations = phase2["catalog"]["animations"]
    if len(animations) != 53:
        raise ValueError("Phase-2 Vela catalogue does not contain 53 entries.")
    entries = []
    for index, (animation, factor, case) in enumerate(zip(animations, factors, targets, strict=True)):
        if (animation["vela_animation_index"], animation["animation_id"]) != (index, ANIMATION_IDS[index]):
            raise ValueError(f"Phase-2 Vela identity differs at index {index}.")
        category, dependency, formula = _classification(case)
        sample_count = int(animation["sample_count"])
        loop = bool(animation["loop_enabled"])
        span = sample_count if loop else sample_count - 1
        reference_rate = span * 60.0 * factor
        entries.append({
            "index": index,
            "animation_id": animation["animation_id"],
            "sample_count": sample_count,
            "loop": loop,
            "clip_span": span,
            "category": category,
            "base_factor": factor,
            "base_factor_f32_hex": raw_factors[index * 4:index * 4 + 4].hex().upper(),
            "dependency": dependency,
            "phase_delta_per_update": f"delayDat * ({formula})",
            "nominal_samples_per_second_at_dependency_1": reference_rate,
            "case_address": f"0x{case:08X}",
            "confidence": "VERIFIED",
        })

    return {
        "scope": "Vela/Girl Prop 218 runtime animation timing in pinned US ROM",
        "timing_function": f"0x{TIMING_FUNCTION:08X}",
        "factor_table": f"0x{FACTOR_TABLE:08X}",
        "jump_table": f"0x{JUMP_TABLE:08X}",
        "common_call": f"0x{COMMON_CALL:08X}",
        "common_call_relocation": _resolve_common_call(rom),
        "movement_inputs": {
            "movement_max": "max(abs(racer+0x04), abs(racer+0x10))",
            "movement_lateral": "abs(racer+0x10)",
            "object_abs": "abs(object+0x20)",
        },
        "state_input": "controlKeys at 0x800F6DA0, bit 0x10",
        "instruction_pins": {f"0x{address:08X}": f"0x{word:08X}" for address, word in INSTRUCTION_PINS.items()},
        "counts": dict(sorted(Counter(entry["category"] for entry in entries).items())),
        "entries": entries,
    }


def _factor_text(entry: dict[str, Any]) -> str:
    factor = format(entry["base_factor"], ".7g")
    dep = entry["dependency"]
    if dep == "fixed":
        return factor
    if dep == "controlKeys_bit_0x10_double":
        return f"`{factor}` or `{format(entry['base_factor'] * 2.0, '.7g')}` when bit `0x10` is set"
    formula = {
        "movement_max": "movement_max",
        "movement_lateral": "movement_lateral",
        "object_abs_clamped": "max(1.0, abs(object+0x20))",
        "combined_max": "max(movement_max, abs(object+0x20))",
    }[dep]
    return f"`{factor} * {formula}`"


def markdown(result: dict[str, Any]) -> str:
    rows = []
    for entry in result["entries"]:
        loop = "loop" if entry["loop"] else "non-loop"
        rate = format(entry["nominal_samples_per_second_at_dependency_1"], ".7g")
        rows.append(
            f"| {entry['index']} | {entry['animation_id']} | {entry['sample_count']} | {loop} | "
            f"{entry['clip_span']} | {entry['category']} | {_factor_text(entry)} | "
            f"`{entry['dependency']}` | {rate} | `{entry['case_address']}` | VERIFIED |"
        )
    return "\n".join((
        "# Vela runtime animation timing",
        "",
        "Scope: Vela/Girl, Prop 218, pinned US Z64 ROM. This report derives Vela's",
        "timing independently from Girl overlay 15; Boy/Juno is used only as a",
        "methodological comparison.",
        "",
        "## VERIFIED advancement chain",
        "",
        "Girl overlay function `0x00F05328` reads the signed animation index from",
        "object `+0x3B`, normalized phase from object `+0x28`, and the per-index",
        "big-endian `f32` base factor from `0x00F0823C`. Its 53-entry jump table",
        "is at `0x00F08848`. Every case reaches the common call at",
        "`0x00F05E74..0x00F05E80`; overlay relocation entry 280 resolves the call",
        "at `0x00F05E7C` to `objAnimDframe` (`0x8001138C`). Therefore:",
        "",
        "```text",
        "phase_next = phase + delayDat * state_scale",
        "clip_span = sample_count       for loop clips",
        "clip_span = sample_count - 1   for non-loop clips",
        "effective_sample_time = phase * clip_span",
        "```",
        "",
        "The common caller passes the case-produced factor from stack `+0x38` as",
        "the scale argument and the incoming integer `delayDat` from stack `+0x5C`",
        "as the delta argument. Nominal rates below use 60 VI/s.",
        "",
        "## VERIFIED inputs and formulas",
        "",
        "The Vela path independently loads and takes absolute values of:",
        "",
        "```text",
        "movement_max     = max(abs(racer+0x04), abs(racer+0x10))",
        "movement_lateral = abs(racer+0x10)",
        "object_abs       = abs(object+0x20)",
        "```",
        "",
        "Four movement-dependent scale forms occur: `movement_max`,",
        "`movement_lateral`, `max(1.0, object_abs)`, and",
        "`max(movement_max, object_abs)`. Index 13 doubles its base factor when",
        "`controlKeys` (`0x800F6DA0`) has bit `0x10` set. The semantic gameplay",
        "names of these fields and the flag remain UNKNOWN.",
        "",
        "The catalogue contains 30 FIXED, 22 MOVEMENT_DEPENDENT, and one",
        "STATE_DEPENDENT entry. All 53 timing formulas are resolved. State-change",
        "branches may reset phase or suppress one advancement while selecting a",
        "new animation; the rows describe ordinary advancement while the indexed",
        "clip remains current, matching the established Boy catalogue boundary.",
        "",
        "## Complete 53-entry catalogue",
        "",
        "For movement rows, the shown rate is a reference at the complete listed",
        "dependency value `1.0`; it is not a claim about typical gameplay input.",
        "Index 13's rate column uses the clear-bit base value.",
        "",
        "| Index | ID | Samples | Mode | Span | Category | State scale/VI | Dependency | Samples/s at dependency=1 | Case | Confidence |",
        "| ---: | ---: | ---: | --- | ---: | --- | --- | --- | ---: | --- | --- |",
        *rows,
        "",
        "## Comparison with Boy/Juno",
        "",
        "**GENERIC VERIFIED:** both character overlays load an indexed `f32` factor,",
        "dispatch through a character-specific jump table, and call the same",
        "`objAnimDframe` with `delayDat` and the resulting factor. Both use",
        "`movement_max`, `movement_lateral`, and a bit-`0x10` factor doubling case.",
        "",
        "**SHARED NUMERICAL DATA:** several individual factor values match, but the",
        "53-value Vela table is independently stored and differs in count, ordering,",
        "and multiple values from Boy's 52-value table.",
        "",
        "**CHARACTER-SPECIFIC:** Vela's jump table and factor table are in overlay 15.",
        "Vela additionally uses `abs(object+0x20)` in indices 44, 45, and 52; this",
        "dependency does not occur in the verified Boy timing catalogue.",
        "",
        "**UNKNOWN:** semantic gameplay labels for the three numeric motion fields",
        "and `controlKeys` bit `0x10`; live values without a runtime capture; PAL",
        "caller-level compensation outside this pinned US-ROM path.",
        "",
        "## Forge interpretation",
        "",
        "Game Timing uses `clip_span * state_scale * 60` samples/s. For all Vela",
        "movement-dependent forms, the existing Movement / Speed slider supplies",
        "the complete evaluated dependency scalar once. For fixed clips it remains",
        "the established preview/export multiplier. The existing state timing flag",
        "checkbox supplies the verified bit-`0x10` clear/set choice for index 13.",
        "Preview and glTF export consume the same immutable timing context.",
        "",
        "## Reproduction",
        "",
        "```powershell",
        "python research/vela/analyze_vela_runtime_timing.py --rom ../rom/jetforcegemini.z64",
        "```",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--markdown", type=Path, default=OUTPUT_MARKDOWN)
    args = parser.parse_args()
    rom = args.rom.resolve(strict=True).read_bytes()
    phase2 = json.loads(PHASE2_MAP.read_text(encoding="utf-8"))
    result = analyze(rom, phase2)
    args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "entries": len(result["entries"])}, sort_keys=True))


if __name__ == "__main__":
    main()
