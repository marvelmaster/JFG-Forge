"""Pinned runtime-use audit for US Prop 220 Boy animations 0 and 43."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from jfg_re.boy_animation_catalog import catalog_boy_animations
from jfg_re.boy_export import BoyExportError
from jfg_re.props import EXPECTED_ROM_SIZE, EXPECTED_SHA1


MAIN_VRAM = 0x80000400
MAIN_ROM = 0x1000
OVERLAY16_VRAM = 0x01000000
OVERLAY16_ROM = 0x1F1E018

# Instructions that anchor the conclusions below.  They are checked against the
# ROM so the report fails instead of silently describing a different build.
PINNED_WORDS = {
    0x80011398: 0x460E6102,  # mul.s caller_scale, caller_delta
    0x800113AC: 0x46040180,  # add.s normalized phase
    0x800113DC: 0x80480008,  # animation loop byte
    0x80045288: 0x8C843374,  # load delayDat
    0x8004528C: 0x0C0117C0,  # call frame/object update
    0x800460BC: 0x0C0023FC,  # call objObjectsTick
    0x800093B4: 0x02602825,  # pass objObjectsTick delta as controlPlayer a1
    0x800457B4: 0x0C0153EF,  # call viFrameSync
    0x800457CC: 0xAC223374,  # store delayDat (branch delay slot)
    0x80055034: 0x2411FFFF,  # VI queue loop starts with count=1
    0x80055040: 0x26100001,  # count another queued VI message
    0x8003B710: 0x2405002B,  # open-chest path selects index 43
    0x8003B714: 0x0C004527,  # objAnimSetMove
    0x8003B7C0: 0x8098003B,  # read current animation index
    0x8003B7C4: 0x2401002B,  # require index 43
    0x8003D44C: 0x241103FF,  # blend counter numerator 1023
    0x8003D560: 0x3059000F,  # animation header low nibble
    0x8003D570: 0xA691005E,  # initialize transition counter
    0x8003D5A0: 0xA688005C,  # store 1023/nibble decrement
    0x8003D714: 0x8682005E,  # transition counter read
    0x8003D774: 0x010A4823,  # subtract transition decrement
    0x80073F20: 0x84CB003E,  # gen_anim_data blend counter (base is instance+0x20)
    0x80073F94: 0x4615A703,  # counter / 1024.0
    0x80074030: 0x014E0018,  # angle delta * blend counter
    0x80074038: 0x000A5283,  # signed >> 10
    0x8003B4D8: 0x8C830068,  # player runtime data
    0x8003B4E0: 0x24620240,  # override list at racer +0x240
}

OVERLAY_WORDS = {
    0x0100513C: 0xC4A40004,  # racer movement component +4
    0x0100515C: 0xC5F00010,  # racer movement component +0x10
    0x0100517C: 0x460C703C,  # compare absolute components
    0x010051D8: 0xC7A40030,  # state-0 base scale
    0x010051E0: 0x46022182,  # state-0 scale *= max(abs components)
    0x01005B54: 0x8FA50030,  # objAnimDframe caller_scale
    0x01005B58: 0x8FA6004C,  # objAnimDframe caller_delta
    0x01002404: 0x240C0008,  # override selector: channel 1 axis 2
    0x01002424: 0x240D0014,  # override selector: channel 3 axis 2
    0x010024B8: 0x240D0006,  # override selector: channel 1 axis 0
    0x010024DC: 0x240E003C,  # override selector: channel 10 axis 0
    0x010048EC: 0x24190044,  # override selector: channel 11 axis 2
    0x0100112C: 0x240C4024,  # channel 6 scale X
    0x0100114C: 0x24094026,  # channel 6 scale Y
    0x01001160: 0x24194028,  # channel 6 scale Z
    0x0100167C: 0x0C000000,  # relocated modGenAnimMatrices call
    0x010016B4: 0x0C000000,  # relocated objMakeGunMtx call
}


def _word(rom: bytes, address: int, *, overlay: bool = False) -> int:
    if overlay:
        offset = OVERLAY16_ROM + address - OVERLAY16_VRAM
    else:
        offset = MAIN_ROM + address - MAIN_VRAM
    return struct.unpack_from(">I", rom, offset)[0]


def _verify_identity(rom: bytes) -> dict[str, Any]:
    digest = hashlib.sha1(rom).hexdigest()
    if len(rom) != EXPECTED_ROM_SIZE or digest != EXPECTED_SHA1:
        raise BoyExportError("Runtime audit requires the pinned US Z64 ROM.")
    return {"size_bytes": len(rom), "sha1": digest, "byte_order": "Z64 / Big Endian"}


def _verify_code(rom: bytes) -> list[dict[str, Any]]:
    checked: list[dict[str, Any]] = []
    for address, expected in PINNED_WORDS.items():
        actual = _word(rom, address)
        if actual != expected:
            raise BoyExportError(f"Pinned instruction differs at 0x{address:08X}.")
        checked.append({"address": f"0x{address:08X}", "word": f"0x{actual:08X}", "segment": "main"})
    for address, expected in OVERLAY_WORDS.items():
        actual = _word(rom, address, overlay=True)
        if actual != expected:
            raise BoyExportError(f"Pinned overlay instruction differs at 0x{address:08X}.")
        checked.append({"address": f"0x{address:08X}", "word": f"0x{actual:08X}", "segment": "overlay16"})
    return checked


def build_runtime_report(rom: bytes) -> dict[str, Any]:
    identity = _verify_identity(rom)
    instructions = _verify_code(rom)
    catalog = catalog_boy_animations(rom)
    selected = {item["boy_animation_index"]: item for item in catalog["animations"] if item["boy_animation_index"] in (0, 43)}
    if set(selected) != {0, 43} or selected[0]["animation_id"] != 1026 or selected[43]["animation_id"] != 1069:
        raise BoyExportError("Pinned Boy animation indices or IDs differ.")
    scale0 = struct.unpack_from(">f", rom, OVERLAY16_ROM + 0x7974)[0]
    scale43 = struct.unpack_from(">f", rom, OVERLAY16_ROM + 0x7974 + 43 * 4)[0]
    if not (abs(scale0 - 0.015) < 1e-8 and abs(scale43 - 0.003) < 1e-8):
        raise BoyExportError("Pinned Boy runtime animation scales differ.")

    concrete_speed = 1.0
    concrete_delta = 1
    phase_per_tick = scale0 * concrete_speed * concrete_delta
    cycle_ticks = 1.0 / phase_per_tick
    sample_rate_per_tick = 16.0 * phase_per_tick

    return {
        "schema_version": 1,
        "scope": "US Prop 220 Boy runtime use of animation index 0 / ID 1026; index 43 / ID 1069 only for caller context",
        "rom": identity,
        "animations": {
            "index_0_id_1026": {
                "identity": {key: selected[0][key] for key in ("boy_animation_index", "animation_id", "rom_range_hex", "blob_sha256", "sample_count", "sample_stride_bytes", "loop_enabled", "header_low_nibble")},
                "name": None,
                "name_status": "UNKNOWN; no semantic name inferred",
                "selection": {
                    "status": "VERIFIED",
                    "state_function": "overlay16 0x01005120",
                    "retained_when": "current index 0, max(abs(racer+4), abs(racer+0x10)) in [0.1,1.75], abs(+4) >= abs(+0x10), and no inspected interrupt condition selects another state",
                    "known_entries": [
                        "index 1 branch at 0x01005364 when its movement threshold falls below 0.25",
                        "indices 3/26 branch at 0x01005500 for the matching direction/control conditions",
                        "indices 9/10/31/32/47/48 branch at 0x0100569C for the matching direction and abs(racer+4) < 1.75",
                        "indices 21/46 may receive 0 from boyCanFire at 0x01005948",
                    ],
                    "known_exits": [
                        "racer+0x569 nonzero -> index 3",
                        "movement metric below 0.1 -> indices 16..19 according to inspected flags/random branch",
                        "dominant racer+0x10 component -> index 9 or 10 according to sign",
                        "movement metric above 1.75 -> index 1",
                    ],
                    "initialization_note": "controlPlayerInit selects index 16 or 9 for the normal inspected Boy subtype cases, so index 0 is not established as the universal spawn/default clip.",
                },
                "timing": {
                    "status": "VERIFIED",
                    "caller_delta": "boyControl integer delta inherited from controlPlayer <- objObjectsTick; delayDat is the viFrameSync return count, normally one elapsed VI and clamped to 6 (debug override 2)",
                    "caller_scale": "state 0 uses overlay base 0.015 multiplied by max(abs(racer f32 +4), abs(racer f32 +0x10))",
                    "base_scale": scale0,
                    "phase_formula": "delta_phase = delayDat * 0.015 * max(abs(racer+4), abs(racer+0x10))",
                    "sample_time_formula": "delta_sample_time = 16 * delta_phase",
                    "variable_speed": True,
                    "pal_ntsc": "The traced path uses elapsed VI count and contains no PAL/NTSC compensation. The pinned US ROM selects NTSC VI modes; seconds therefore depend on actual video cadence.",
                    "concrete_case": {
                        "conditions": {"delayDat_vi_ticks": concrete_delta, "movement_metric": concrete_speed},
                        "phase_per_update": phase_per_tick,
                        "sample_time_per_update": sample_rate_per_tick,
                        "vi_ticks_per_sample": 1.0 / sample_rate_per_tick,
                        "vi_ticks_per_16_sample_cycle": cycle_ticks,
                        "nominal_ntsc_60hz_seconds_per_cycle": cycle_ticks / 60.0,
                        "nominal_pal_50hz_seconds_per_cycle_if_same_path_were_used": cycle_ticks / 50.0,
                        "qualification": "Tick counts follow exactly from code. 60/50 Hz conversions are explicit nominal video-rate arithmetic, not a measured game FPS; PAL is not the normal path of the pinned US ROM.",
                    },
                },
            },
            "index_43_id_1069": {
                "identity": {key: selected[43][key] for key in ("boy_animation_index", "animation_id", "rom_range_hex", "blob_sha256", "sample_count", "sample_stride_bytes", "loop_enabled", "header_low_nibble")},
                "name": None,
                "name_status": "The gameplay caller is VERIFIED as controlPlayerOpenChest; no clip name is assigned.",
                "selection": {
                    "status": "VERIFIED",
                    "path": "controlPlayerOpenChest 0x8003B6C8 dispatches player subtype byte +1; values 1 and 5 reach 0x8003B710 and call objAnimSetMove(object,43,0).",
                    "phase_consumer": "controlPlayerOpeningChest 0x8003B740 requires index 43 for those subtypes and returns phase bands at normalized 0.15 and 0.53.",
                    "loop": False,
                    "base_scale": scale43,
                    "transition": "The Boy state-43 branch can return to a state chosen by boyCanFire when its special state byte clears; other exits depend on its inspected phase/control conditions.",
                },
                "root_translation": {
                    "status": "VERIFIED for the traced player/model path",
                    "endpoint_model_units": [-26.0, -2.0, 78.0],
                    "treatment": "gen_anim_data applies decoded Q10 root translation to the model root before hierarchy composition. No transfer from decoded root values to object world position and no compensation was found in objAnimDframe, controlPlayerOpeningChest, or the inspected Boy state-43 path.",
                    "scope_limit": "This establishes visual/model-local root motion in the traced path; unrelated object systems were not generalized.",
                },
            },
        },
        "transition_blend": {
            "status": "VERIFIED",
            "header_low_nibble": {"animation_0": selected[0]["header_low_nibble"], "animation_43": selected[43]["header_low_nibble"]},
            "activation": "modGenAnimMatrices reads the selected blob header low nibble. Nonzero initializes instance+0x5E to 1023, instance+0x5C to floor(1023/nibble), and decodes current plus previous animation states.",
            "weight": "w = instance+0x5E / 1024.0; it is decremented toward zero by instance+0x5C when the guarded player/object update permits.",
            "formula": "output = current + (previous - current) * w; transition therefore moves from previous toward current as w decreases.",
            "angles": "Each 16-bit angle component uses the runtime wrapped/signed delta path, multiplies by the integer counter, shifts right 10, and adds the current component.",
            "root": "Root X/Y/Z are decoded for both states and blended componentwise with the same weight before /1024 model-unit conversion.",
            "scales": "Optional decoded scales pass through the same two-state generation path.",
            "normal_use": "Both audited blobs have low nibble 4, so entering them requests transition blending against the prior clip when a prior state exists; they are decoded alone after the counter reaches zero.",
        },
        "player_overrides": {
            "status": "VERIFIED",
            "path": "controlPlayerTiltList 0x8003B4D8 supplies racer+0x240 to modGenAnimMatrices/gen_anim_data. Boy overlay16 builds the selector/value list before its call to modGenAnimMatrices at 0x0100167C.",
            "angle_selectors": [
                {"selector": "0x0008", "channel": 1, "axis": 2},
                {"selector": "0x0014", "channel": 3, "axis": 2},
                {"selector": "0x0006", "channel": 1, "axis": 0},
                {"selector": "0x003C", "channel": 10, "axis": 0},
                {"selector": "0x0044", "channel": 11, "axis": 2},
            ],
            "scale_selectors": "A condition at overlay 0x01001128 appends 0x4024/0x4026/0x4028 for channel 6 XYZ. A further runtime block may append scale selectors for channels 0,6,9,10,14,18.",
            "arm_chains": {
                "3_to_4_to_5_to_6": "channel/node 3 receives a direct local angle override; node 6 can receive scale overrides. Nodes 4 and 5 had no direct selector in the inspected Boy list.",
                "3_to_7_to_8_to_9": "inherits node 3's local angle override through hierarchy; node 9 can receive a conditional scale override. Nodes 7 and 8 had no direct selector in the inspected Boy list.",
            },
            "ordering": "Overrides are consumed inside gen_anim_data before final hierarchy/world matrices are emitted. After modGenAnimMatrices, the inspected Boy path calls objMakeGunMtx and render helpers but neither calls modGenAnimMatrices again nor writes the skeletal matrix slots.",
            "upper_body_layer": "No separate upper-body clip or second post-generation arm hierarchy pass was found in the inspected Boy player path. The concrete mechanisms are transition blending plus selector-based local angle/scale overrides.",
        },
        "blender_interpretation": {
            "status": "VERIFIED scope statement",
            "complete_runtime_pose": False,
            "reason": "The validated glTF reproduces the base animation matrix decoder. It omits live racer+0x240 aim/movement/weapon override values, transition state against a previous clip, and object/world context.",
            "corrections": [
                "The technical glTF time unit is sample time, not seconds.",
                "Animation 0 speed is runtime-variable and movement-dependent.",
                "Animation 0 is not established as the universal default and has no verified semantic name.",
                "Animation 43 has a verified chest-opening caller context, but no clip name is inferred.",
                "A single isolated base clip does not represent every complete runtime player pose.",
            ],
        },
        "code_evidence": {
            "checked_instruction_count": len(instructions),
            "instructions": instructions,
            "key_ranges": {
                "objAnimDframe": "0x8001138C..0x80011498",
                "viFrameSync_and_delayDat": "0x800457B0..0x800457F8, 0x80054FBC..0x80055064",
                "object_to_player_delta": "0x80045284..0x80045290, 0x800460BC, 0x800093AC..0x800093B4",
                "boy_state_machine": "overlay16 0x01005120..0x01005B74",
                "chest_selection": "0x8003B6C8..0x8003B81C",
                "transition_setup": "0x8003D4F0..0x8003D5A4",
                "transition_countdown": "0x8003D714..0x8003D790",
                "gen_anim_data_blend": "0x80073F10..0x80074044",
                "boy_override_builders": "overlay16 0x010023DC..0x0100250C, 0x010048E0..0x0100492C, 0x01001128..0x010011A8",
                "boy_model_generation_order": "overlay16 0x01001664..0x01001710",
            },
        },
        "remaining_unknowns": [
            "Exact gameplay meaning/name of animation 0 / ID 1026.",
            "Concrete live values of all Boy override selectors for any one captured gameplay frame.",
            "Whether a guarded modGenAnimMatrices update can defer a blend-counter decrement in every relevant player circumstance.",
            "Whether the unusual isolated animation-43 pose becomes visually expected only with its chest object, world transform, and live overrides.",
        ],
        "smallest_next_step": "Capture one deterministic normal-player frame while index 0 is active: movement components +4/+0x10, delayDat, phase, previous/current indices, blend counter +0x5E, and the complete racer+0x240 override list; then replay only those values through the existing decoder without altering it.",
    }


def report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_report(rom_path: Path, output_path: Path) -> dict[str, Any]:
    report = build_runtime_report(rom_path.read_bytes())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(report_bytes(report))
    return report
