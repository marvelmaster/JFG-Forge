# Vela runtime animation timing

Scope: Vela/Girl, Prop 218, pinned US Z64 ROM. This report derives Vela's
timing independently from Girl overlay 15; Boy/Juno is used only as a
methodological comparison.

## VERIFIED advancement chain

Girl overlay function `0x00F05328` reads the signed animation index from
object `+0x3B`, normalized phase from object `+0x28`, and the per-index
big-endian `f32` base factor from `0x00F0823C`. Its 53-entry jump table
is at `0x00F08848`. Every case reaches the common call at
`0x00F05E74..0x00F05E80`; overlay relocation entry 280 resolves the call
at `0x00F05E7C` to `objAnimDframe` (`0x8001138C`). Therefore:

```text
phase_next = phase + delayDat * state_scale
clip_span = sample_count       for loop clips
clip_span = sample_count - 1   for non-loop clips
effective_sample_time = phase * clip_span
```

The common caller passes the case-produced factor from stack `+0x38` as
the scale argument and the incoming integer `delayDat` from stack `+0x5C`
as the delta argument. Nominal rates below use 60 VI/s.

## VERIFIED inputs and formulas

The Vela path independently loads and takes absolute values of:

```text
movement_max     = max(abs(racer+0x04), abs(racer+0x10))
movement_lateral = abs(racer+0x10)
object_abs       = abs(object+0x20)
```

Four movement-dependent scale forms occur: `movement_max`,
`movement_lateral`, `max(1.0, object_abs)`, and
`max(movement_max, object_abs)`. Index 13 doubles its base factor when
`controlKeys` (`0x800F6DA0`) has bit `0x10` set. The semantic gameplay
names of these fields and the flag remain UNKNOWN.

The catalogue contains 30 FIXED, 22 MOVEMENT_DEPENDENT, and one
STATE_DEPENDENT entry. All 53 timing formulas are resolved. State-change
branches may reset phase or suppress one advancement while selecting a
new animation; the rows describe ordinary advancement while the indexed
clip remains current, matching the established Boy catalogue boundary.

## Complete 53-entry catalogue

For movement rows, the shown rate is a reference at the complete listed
dependency value `1.0`; it is not a claim about typical gameplay input.
Index 13's rate column uses the clear-bit base value.

| Index | ID | Samples | Mode | Span | Category | State scale/VI | Dependency | Samples/s at dependency=1 | Case | Confidence |
| ---: | ---: | ---: | --- | ---: | --- | --- | --- | ---: | --- | --- |
| 0 | 1097 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F05400` | VERIFIED |
| 1 | 1098 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.011 * movement_max` | `movement_max` | 10.56 | `0x00F054FC` | VERIFIED |
| 2 | 1099 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.008 * movement_max` | `movement_max` | 7.68 | `0x00F05580` | VERIFIED |
| 3 | 1096 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F055E4` | VERIFIED |
| 4 | 1104 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F056D0` | VERIFIED |
| 5 | 1110 | 31 | loop | 31 | FIXED | 0.012 | `fixed` | 22.32 | `0x00F05700` | VERIFIED |
| 6 | 1111 | 19 | non-loop | 18 | FIXED | 0.02 | `fixed` | 21.6 | `0x00F05E70` | VERIFIED |
| 7 | 1112 | 19 | loop | 19 | FIXED | 0.015 | `fixed` | 17.1 | `0x00F05E70` | VERIFIED |
| 8 | 1109 | 15 | non-loop | 14 | FIXED | 0.0334 | `fixed` | 28.056 | `0x00F0573C` | VERIFIED |
| 9 | 1113 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 10 | 1114 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 11 | 1102 | 30 | non-loop | 29 | FIXED | 0.02 | `fixed` | 34.8 | `0x00F05878` | VERIFIED |
| 12 | 1107 | 17 | non-loop | 16 | FIXED | 0.028 | `fixed` | 26.88 | `0x00F058C8` | VERIFIED |
| 13 | 1100 | 12 | non-loop | 11 | STATE_DEPENDENT | `0.02` or `0.04` when bit `0x10` is set | `controlKeys_bit_0x10_double` | 13.2 | `0x00F05948` | VERIFIED |
| 14 | 1101 | 12 | loop | 12 | FIXED | 0.005 | `fixed` | 3.6 | `0x00F05994` | VERIFIED |
| 15 | 1115 | 3 | non-loop | 2 | FIXED | 0.025 | `fixed` | 3 | `0x00F059C0` | VERIFIED |
| 16 | 1090 | 20 | non-loop | 19 | FIXED | 0.005 | `fixed` | 5.7 | `0x00F059E8` | VERIFIED |
| 17 | 1091 | 25 | non-loop | 24 | FIXED | 0.0075 | `fixed` | 10.8 | `0x00F059E8` | VERIFIED |
| 18 | 1092 | 55 | non-loop | 54 | FIXED | 0.005 | `fixed` | 16.2 | `0x00F059E8` | VERIFIED |
| 19 | 1093 | 20 | non-loop | 19 | FIXED | 0.005 | `fixed` | 5.7 | `0x00F059E8` | VERIFIED |
| 20 | 1094 | 20 | non-loop | 19 | FIXED | 0.005 | `fixed` | 5.7 | `0x00F059E8` | VERIFIED |
| 21 | 1095 | 20 | non-loop | 19 | FIXED | 0.005 | `fixed` | 5.7 | `0x00F059E8` | VERIFIED |
| 22 | 1121 | 25 | non-loop | 24 | FIXED | 0.0175 | `fixed` | 25.2 | `0x00F05ADC` | VERIFIED |
| 23 | 1106 | 10 | loop | 10 | FIXED | 0.005 | `fixed` | 3 | `0x00F05B3C` | VERIFIED |
| 24 | 1141 | 20 | non-loop | 19 | FIXED | 0.01 | `fixed` | 11.4 | `0x00F05E70` | VERIFIED |
| 25 | 1119 | 4 | non-loop | 3 | FIXED | 0.01 | `fixed` | 1.8 | `0x00F05E70` | VERIFIED |
| 26 | 1120 | 8 | non-loop | 7 | FIXED | 0.0334 | `fixed` | 14.028 | `0x00F05E70` | VERIFIED |
| 27 | 1124 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F055E4` | VERIFIED |
| 28 | 1123 | 3 | loop | 3 | FIXED | 0.005 | `fixed` | 0.9 | `0x00F059E8` | VERIFIED |
| 29 | 1125 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F05400` | VERIFIED |
| 30 | 1126 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.011 * movement_max` | `movement_max` | 10.56 | `0x00F054FC` | VERIFIED |
| 31 | 1127 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0085 * movement_max` | `movement_max` | 8.16 | `0x00F05580` | VERIFIED |
| 32 | 1128 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 33 | 1129 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 34 | 1130 | 3 | non-loop | 2 | FIXED | 0.005 | `fixed` | 0.6 | `0x00F05994` | VERIFIED |
| 35 | 1116 | 12 | loop | 12 | FIXED | 0.014 | `fixed` | 10.08 | `0x00F05E70` | VERIFIED |
| 36 | 1117 | 6 | non-loop | 5 | FIXED | 0.035 | `fixed` | 10.5 | `0x00F05D54` | VERIFIED |
| 37 | 1118 | 13 | non-loop | 12 | FIXED | 0.02 | `fixed` | 14.4 | `0x00F05D8C` | VERIFIED |
| 38 | 1131 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F05400` | VERIFIED |
| 39 | 1132 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.011 * movement_max` | `movement_max` | 10.56 | `0x00F054FC` | VERIFIED |
| 40 | 1133 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0085 * movement_max` | `movement_max` | 8.16 | `0x00F05580` | VERIFIED |
| 41 | 1124 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.014 * movement_max` | `movement_max` | 13.44 | `0x00F055E4` | VERIFIED |
| 42 | 1134 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 43 | 1135 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.0115 * movement_lateral` | `movement_lateral` | 11.04 | `0x00F05770` | VERIFIED |
| 44 | 1137 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.006 * max(1.0, abs(object+0x20))` | `object_abs_clamped` | 5.76 | `0x00F05B68` | VERIFIED |
| 45 | 1136 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.006 * max(movement_max, abs(object+0x20))` | `combined_max` | 5.76 | `0x00F05CB8` | VERIFIED |
| 46 | 1138 | 3 | non-loop | 2 | FIXED | 0.01 | `fixed` | 1.2 | `0x00F05E70` | VERIFIED |
| 47 | 1139 | 10 | non-loop | 9 | FIXED | 0.01 | `fixed` | 5.4 | `0x00F05DC4` | VERIFIED |
| 48 | 1140 | 70 | non-loop | 69 | FIXED | 0.003 | `fixed` | 12.42 | `0x00F05E04` | VERIFIED |
| 49 | 1122 | 25 | non-loop | 24 | FIXED | 0.02 | `fixed` | 28.8 | `0x00F05ADC` | VERIFIED |
| 50 | 1103 | 30 | non-loop | 29 | FIXED | 0.02 | `fixed` | 34.8 | `0x00F058A0` | VERIFIED |
| 51 | 1108 | 17 | non-loop | 16 | FIXED | 0.028 | `fixed` | 26.88 | `0x00F05908` | VERIFIED |
| 52 | 1142 | 16 | loop | 16 | MOVEMENT_DEPENDENT | `0.006 * max(1.0, abs(object+0x20))` | `object_abs_clamped` | 5.76 | `0x00F05C10` | VERIFIED |

## Comparison with Boy/Juno

**GENERIC VERIFIED:** both character overlays load an indexed `f32` factor,
dispatch through a character-specific jump table, and call the same
`objAnimDframe` with `delayDat` and the resulting factor. Both use
`movement_max`, `movement_lateral`, and a bit-`0x10` factor doubling case.

**SHARED NUMERICAL DATA:** several individual factor values match, but the
53-value Vela table is independently stored and differs in count, ordering,
and multiple values from Boy's 52-value table.

**CHARACTER-SPECIFIC:** Vela's jump table and factor table are in overlay 15.
Vela additionally uses `abs(object+0x20)` in indices 44, 45, and 52; this
dependency does not occur in the verified Boy timing catalogue.

**UNKNOWN:** semantic gameplay labels for the three numeric motion fields
and `controlKeys` bit `0x10`; live values without a runtime capture; PAL
caller-level compensation outside this pinned US-ROM path.

## Forge interpretation

Game Timing uses `clip_span * state_scale * 60` samples/s. For all Vela
movement-dependent forms, the existing Movement / Speed slider supplies
the complete evaluated dependency scalar once. For fixed clips it remains
the established preview/export multiplier. The existing state timing flag
checkbox supplies the verified bit-`0x10` clear/set choice for index 13.
Preview and glTF export consume the same immutable timing context.

## Reproduction

```powershell
python research/vela/analyze_vela_runtime_timing.py --rom ../rom/jetforcegemini.z64
```
