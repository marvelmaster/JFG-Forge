# Boy runtime capture: animation index 19 / ID 1022

This report validates the first real RMG capture taken at guest PC
`0x8003D908`, immediately after `gen_anim_data` returned. It covers Prop 220
Boy only. The original investigation did not change production code. A later
focused integration applied the resulting A/C/B mapping through the shared
`_local_matrix_from_stored` helper used by Forge, runtime validation, and the
limited Boy glTF baker; packed animation decoding remained unchanged.

## Result

The captured pose is reproducible for **21/21 matrices** when the comparison
uses the 12 values that JFG actually writes in each 64-byte runtime slot and
the stored Euler components are supplied to the already documented
`Rx(A) * Ry(C) * Rz(B)` path in that order.

```text
maximum absolute element error: 7.62939453125e-06
mean absolute element error:    1.6745697293016644e-07
matrices within 1e-5:           21 / 21
```

The residuals are at float32 accumulation scale. Matrix 15 has the largest
element error. Its translation Euclidean error is
`9.548656651735681e-06`.

## Capture identity and byte order

| Item | Value |
| --- | --- |
| Guest PC | `0x8003D908` |
| Instance (`S4`) | `0x802FBFF0` |
| Object matrix | `0x800F8D70` |
| Selector list | `0x801BD44C` |
| Active matrix buffer | `1` |
| Matrix base | `0x802FC5C8` |
| Current animation | index `19`, ID `1022` |
| Previous animation | index `36`, ID `1061` |
| Blend step / counter | `102 / 0` |

Reversing every four-byte word in `selectors_n64.bin` and
`matrices_n64.bin` reproduces the corresponding host-raw file byte for byte.
All decoding below uses the logical N64-order files.

## Runtime matrix representation

Each runtime slot has a stride of `0x40`, but it is not valid to interpret all
16 words as a complete 4x4 float matrix. `gen_anim_data` writes three
Big-Endian `f32` values in each 16-byte row:

```text
row 0: +0x00, +0x04, +0x08    +0x0C unused
row 1: +0x10, +0x14, +0x18    +0x1C unused
row 2: +0x20, +0x24, +0x28    +0x2C unused
row 3: +0x30, +0x34, +0x38    +0x3C unused
```

The meaningful representation is therefore a row-major 4x3 affine matrix.
The unused fourth words retain unrelated/stale bit patterns. Reading all 336
words as floats produces 41 non-finite values in this capture. The previous
capture documentation that required 16 finite `f32` values per slot is
contradicted by the real dump.

The separate object matrix is a complete, finite 4x4 matrix:

```text
[ 0.2355460227, -0.0000000000,  0.1097199321, 0.0 ]
[ 0.0000000000,  0.2599993646,  0.0000000000, 0.0 ]
[-0.1097199321,  0.0000000000,  0.2355460227, 0.0 ]
[19.5716342926, -101.9899597168, -3.0037481785, 1.0 ]
```

## Instance animation state

The relevant decoded fields are:

| Instance offset | Type | Captured value | Interpretation |
| ---: | --- | ---: | --- |
| `+0x24` | `u16` | `19` | current animation index |
| `+0x26` | `u16` | `36` | previous animation index; inactive because blend counter is zero |
| `+0x28` | `f32` | `30.41998291015625` | effective current decode time |
| `+0x2C` | `f32` | `9.201152801513672` | previous effective time; inactive here |
| `+0x38` | `f32` | `39.0` | current clip span in sample units |
| `+0x3C` | `f32` | `16.0` | previous clip span; inactive here |
| `+0x5C` | `s16` | `102` | blend step |
| `+0x5E` | `s16` | `0` | no previous-pose contribution |

At `0x8003D3F8..0x8003D428`, `modGenAnimMatrices` loads `f32
instance+0x38`, multiplies it by `f32 object+0x28`, and stores the product at
`instance+0x28`. `gen_anim_data` receives the state beginning at
`instance+0x20`, so its current time field is that product at relative `+0x08`.

For index 19, the catalogued non-looping time domain is `[0,39]`. The captured
`+0x38 == 39.0` is therefore in clip sample units and is **not a normalized
phase**. The effective value `+0x28 == 30.41998291015625` decodes as:

```text
current sample: 30
next sample:    31
fraction Q10:   430 / 1024
```

The implied game-object phase is `0.7799995617988782`. Its numerical value is
inferred from the two captured instance fields because game object `+0x28`
itself was not dumped. Subsequent static timing validation identifies that
field as the normalized phase advanced by `objAnimDframe`; model instance
`+0x38` is the clip span (`39` here), not a second advancing cursor.

## Selector list

The terminator is at selector-dump offset `+0x04`; six bytes are consumed in
total.

| Dump offset | Selector | Operation | Channel | Stored component | Signed value | Direct Boy joint |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `+0x00` | `0x0044` | additive angle | `11` | `1` | `-15` | `11` |
| `+0x04` | `0x1000` | terminator | — | — | — | — |

`racer+0x580` is `-15`, exactly matching the emitted selector value.
`u32 racer+0x540` is zero, so its `0x40` bit is clear and no node-6 scale
triplet is present.

The selector directly changes joint/channel 11 and propagates through its
descendants 12–20. It changes 10 final matrices. In identity-object space the
maximum A-to-B matrix element delta is `0.1258983612060547`. With the captured
object matrix but without the selector, the maximum error against the capture
is `0.03200340270996094`, and only 11/21 matrices remain within `1e-5`.
The selector is therefore numerically material and required for this frame.

## Three reconstruction variants

| Variant | Current clip | Selectors | Object matrix | Purpose |
| --- | --- | --- | --- | --- |
| A | index 19 at time `30.41998291015625` | no | identity | isolated clip |
| B | same | captured list | identity | runtime-modified model space |
| C | same | captured list | captured matrix | exact runtime comparison |

A→B changes 10 matrices. B→C changes all 21 matrices; its maximum element
delta is `237.39801025390625`, reflecting the captured scale, orientation,
and world translation. Only C is directly comparable with the runtime dump.

## Per-matrix comparison for variant C

All errors use the 12 written 4x3 elements. Translation max is the maximum
absolute error among row-3 XYZ; translation L2 is the Euclidean XYZ error.

| Matrix | Max element error | Mean element error | Translation max | Translation L2 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 2.98023224e-08 | 2.48352687e-09 | 0 | 0 |
| 4 | 3.81469727e-06 | 3.22858493e-07 | 3.81469727e-06 | 3.81469727e-06 |
| 5 | 3.81469727e-06 | 3.23479374e-07 | 3.81469727e-06 | 3.81469727e-06 |
| 6 | 9.53674316e-07 | 8.44399134e-08 | 9.53674316e-07 | 9.53674316e-07 |
| 7 | 4.47034836e-08 | 4.65661287e-09 | 0 | 0 |
| 8 | 3.81469727e-06 | 3.24410697e-07 | 3.81469727e-06 | 3.81469727e-06 |
| 9 | 9.53674316e-07 | 8.63025586e-08 | 9.53674316e-07 | 9.53674316e-07 |
| 10 | 3.72529030e-09 | 3.10440858e-10 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 |
| 12 | 1.90734863e-06 | 1.58945719e-07 | 1.90734863e-06 | 1.90734863e-06 |
| 13 | 3.81469727e-06 | 3.20530186e-07 | 3.81469727e-06 | 3.81469727e-06 |
| 14 | 3.81469727e-06 | 3.20530186e-07 | 3.81469727e-06 | 3.81469727e-06 |
| 15 | 7.62939453e-06 | 1.15491760e-06 | 7.62939453e-06 | 9.54865665e-06 |
| 16 | 0 | 0 | 0 | 0 |
| 17 | 4.76837158e-07 | 3.97364299e-08 | 4.76837158e-07 | 4.76837158e-07 |
| 18 | 9.53674316e-07 | 1.19364510e-07 | 9.53674316e-07 | 1.06624030e-06 |
| 19 | 9.53674316e-07 | 1.19364510e-07 | 9.53674316e-07 | 1.06624030e-06 |
| 20 | 9.53674316e-07 | 1.34265671e-07 | 9.53674316e-07 | 1.15731286e-06 |

## Mismatch localization

Using the existing production call `_local_matrix(stored_components, ...)`
directly gives a maximum runtime-matrix error of `18.070096015930176` for this
same frame. The hierarchy, root Q10 translation, selector application, and
object composition do not explain that pattern: extracting captured child
local matrices shows that the stored second component drives the formula's
`C` term and the stored third component drives its `B` term.

The existing low-level helper names its inputs A/B/C. To reproduce the runtime
from the stored triplet, the capture-specific replay therefore calls:

```python
_local_matrix([stored[0], stored[2], stored[1]], scales, translation, sine_table)
```

This is consistent with the previously documented runtime order
`Rx(A) * Ry(C) * Rz(B)`. The production caller originally supplied the stored
triplet without that exchange. It now uses the same shared conversion as this
runtime regression.

## Evidence status

### VERIFIED

- Logical N64 and host-raw files have the documented per-word byte-order
  relationship.
- Runtime slots are `0x40` bytes but contain 12 meaningful `f32` values in a
  4x3 layout; the fourth word of each row is not a matrix float.
- `instance+0x38` is the unscaled clip span in sample units in this frame,
  not a normalized `[0,1)` phase or an independently advancing cursor.
- `instance+0x28` is the effective current time consumed by the current-state
  decoder after multiplication by `object+0x28`.
- Blend counter zero selects the no-previous-contribution path for this
  capture.
- Selector `0x0044`, value `-15`, modifies stored component 1 of channel 11;
  it is required to reproduce joints 11–20.
- Swapping the stored second/third components at the existing matrix-helper
  boundary reproduces 21/21 captured matrices with maximum error
  `7.62939453125e-06`.

### LIKELY

- The undumped `f32 object+0x28` was approximately
  `0.7799995617988782`; the value is inferred from the verified multiply and
  captured span/output, while its normalized-phase role is VERIFIED by the
  `objAnimDframe` data flow.

### UNKNOWN

- A semantic name for animation index 19 / ID 1022.
- Whether another runtime path ever assigns a meaning to the unused fourth
  word in a matrix row. It is not part of the affine matrix consumed here.

## Boundary before captures 3, 32, and 35

The capture method itself is now sufficient. Before those captures are fed to
the old importer, its assumptions must be aligned with this evidence:

1. read effective current time from `instance+0x28` and retain `+0x38` only as
   the pre-multiplier input;
2. compare 12 written elements per runtime slot, not 16 finite floats;
3. supply stored angle components to the established A/B/C helper in
   A/third/second order;
4. permit arbitrary catalogued animation indices rather than index 0 only.

Reaching gameplay states for indices 32 and 35 remains a separate practical
blocker because their selection paths are still unknown. No further analysis
of those clips was performed here.

## Reproduction

The index-19 script is retained as a compatibility wrapper around the reusable
`jfg_re.boy_runtime_capture.validate_capture_directory` API. For this fixture,
from `jfg-re/`:

```powershell
python -B research/boy/validate_runtime_capture_index19.py `
  --output research/boy/runtime-capture-index19-validation.json

python -B -m unittest tests.test_runtime_capture_index19_validation
```

For any future no-blend capture directory:

```powershell
python -B tools/validate_boy_runtime_capture.py `
  --rom ../rom/jetforcegemini.z64 `
  --boy data/generated/props-us-verified/bins/0220_Boy.bin `
  --capture-dir research/boy/runtime-captures/CAPTURE-NAME `
  --output research/boy/runtime-captures/CAPTURE-NAME/validation.json
```

The JSON contains capture hashes, decoded state, selector entries, all
per-matrix metrics, and the unused row words for independent checking.
