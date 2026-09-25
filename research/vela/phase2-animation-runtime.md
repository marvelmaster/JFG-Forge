# Vela Phase 2: animation source and runtime path

Scope: Prop 218 `Girl` in the pinned US Z64 ROM, SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`. This phase maps Vela's
animation source, decodes one isolated technical reference clip, traces the
actual Girl model-generation calls, and resolves the GirlGun socket. It does
not add Vela to Forge and does not assign semantic animation names.

Machine-readable evidence:
[`phase2-runtime-map.json`](phase2-runtime-map.json). Reproduction helper:
[`analyze_vela_phase2.py`](analyze_vela_phase2.py).

## 1. Animation catalog

### VERIFIED

Prop 218 indexes the same generic animation asset chain that Boy uses, with
character-specific table ranges:

| Item | Vela value |
| --- | --- |
| Asset 40 Prop pair | ROM `0x160ab34` |
| Global animation-index range | `170..223` |
| Entry count | 53 |
| Asset 41 ID range | ROM `0x160b1f4..0x160b25e` |
| Asset 44 map pair | ROM `0x16ff368` |
| Asset 45 relative map range | `0xfe0..0x15b0` |
| Asset 45 ROM map range | `0x1700e10..0x17013e0` |
| Map size | 1,488 bytes: 53 × 28 plus four zero alignment bytes |

The 53 index-ordered IDs are:

```text
1097, 1098, 1099, 1096, 1104, 1110, 1111, 1112, 1109, 1113,
1114, 1102, 1107, 1100, 1101, 1115, 1090, 1091, 1092, 1093,
1094, 1095, 1121, 1106, 1141, 1119, 1120, 1124, 1123, 1125,
1126, 1127, 1128, 1129, 1130, 1116, 1117, 1118, 1131, 1132,
1133, 1124, 1134, 1135, 1137, 1136, 1138, 1139, 1140, 1122,
1103, 1108, 1142
```

There are 52 unique IDs because ID 1124 appears at indices 27 and 41. The
catalog contains 28 looping and 25 nonlooping entries. Sample counts range
from 3 to 70 and declared strides from 0 to 55 bytes. Thirty-five entries
contain three runtime-consumed scale streams. Exact per-entry ROM ranges,
sample counts, strides, flags, root widths, descriptor counts, channel maps,
and hashes are recorded in the JSON report.

### Runtime descriptor-count detail

Vela exposed an ambiguity hidden by Boy's zero-filled final slot. The blob
serializes `slots × 3` scalar descriptor records, but the internal decoder in
`gen_anim_data` reads `control[1]`, subtracts one, and multiplies by three at
`0x800743e8..0x800743fc`. The runtime therefore decodes exactly:

```text
(transform_channel_slots - 1) × 3 scalar descriptors
```

The last serialized triplet belongs to the runtime's zero scratch channel and
is ignored even when its stored fields and per-sample bits are nonzero. This is
not ordinary padding. The research decoder validates those serialized bits,
but deliberately supplies a zero channel to the runtime pose.

Two nonlooping blobs, indices 17/22 (IDs 1091/1121), end one declared stride
byte before their final sample boundary. The immediately following byte in
contiguous asset 43 is `00` and supplies that lookahead. The runtime-consumed
fields and serialized fields both parse completely with that byte. This is
recorded explicitly rather than silently extending each blob.

## 2. Channel mapping to 28 transforms

### VERIFIED

`modGenAnimMatrices` at `0x8003d5cc..0x8003d618` reads the model transform
count at model `+0x4f` and copies one byte per transform from the selected
animation's map into transform-record byte `+2`. Prop 218 has 28 transform
records, and each of Vela's 53 map rows contains 28 bytes.

- Indices 1–52 use the identity map `0..27`. Their clips expose 28 channel
  slots: 27 decoded channels plus zero scratch channel 27. Transform 27 thus
  receives the scratch channel.
- Index 0 uses 29 slots and map
  `0..25, 27, 28`. It has 28 decoded channels plus scratch channel 28;
  animation channel 26 is not selected, transform 26 uses decoded channel 27,
  and transform 27 uses scratch channel 28.

No 21-channel Boy assumption is used.

## 3. Technical reference animation

Index 0 / ID 1097 was selected as the Phase-2 reference. This selection does
not assign a semantic name or claim it is the universal gameplay default.
Index 0 is the generic new-instance initial value and is the structurally most
useful Vela entry: it is the sole 29-slot/nonidentity-map clip, has Root-Q10 Y,
one runtime-consumed scale triplet, and a looping 16-sample domain.

| Property | Value |
| --- | --- |
| Index / ID | 0 / 1097 |
| ROM range | `0x16ee210..0x16ee530` |
| Blob size | 800 bytes |
| SHA-256 | `ba1f34a283390a3b7328a5939ecd4eb364c2e9145b69fe20c163abc91984d42d` |
| Samples / stride | 16 / 37 bytes |
| Loop domain | `[0,16)`; sample 15 interpolates to 0 |
| Frame-data offset | `0xca` |
| Runtime channels | 28 decoded plus scratch channel 28 |
| Runtime descriptors | 84 |
| Serialized descriptors | 87 |
| Runtime sample bits | 269 |
| Root widths X/Y/Z | `[0,3,0]` |
| Runtime scale scalars | 81, 82, 83 (channel 27 XYZ) |

The ignored final descriptor triplet is `0016 0010 0010`, including three
stored scale fields. Fourteen of 16 samples contain nonzero ignored-final-slot
values. The runtime does not consume these values because of its explicit
`slots - 1` loop bound.

## 4. Decoder and isolated pose

The research decoder reuses the established MSB-first bit reader, canonical
10-bit interpolation state, signed 11-bit angle delta, Root-Q10 formula,
quarter-sine table, row-vector matrix multiplication, and local matrix helper.
No production decoder or Forge behavior changed.

### Runtime-format confidence

- **VERIFIED:** Root translation uses the same signed base plus packed Q10
  fields and final `/1024` conversion. Vela calls the same generic
  `modGenAnimMatrices` and `gen_anim_data` functions.
- **VERIFIED generic runtime path:** stored angle components are A/C/B relative
  to the matrix helper, so the shared helper receives
  `[stored[0], stored[2], stored[1]]` and constructs
  `Rx(A) * Ry(C) * Rz(B)`.
- **VERIFIED generic runtime path:** matrices use row vectors and
  `child_world = child_local * parent_world`.
- **UNKNOWN numerically for a real Vela frame:** no live Vela matrix capture
  exists yet. The isolated results below omit live selector values, transition
  state, and an external object/world matrix.

The reference clip was evaluated at five deterministic technical sample
positions. All 28 matrices and all 551 active referenced vertices are finite.

| Time | Runtime state `(current,next,fraction10)` | Root XYZ | Transformed XYZ bounds |
| ---: | --- | --- | --- |
| 0 | `(0,0,0)` | `(0,-5,0)` | `(-30.407,-2.845,-59.719)..(27.493,206.822,59.066)` |
| 1 | `(1,1,0)` | `(0,-2,0)` | `(-32.314,-3.369,-46.132)..(29.389,209.516,61.012)` |
| 7.5 | `(7,8,512)` | `(0,-5.5,0)` | `(-30.446,-1.699,-62.409)..(25.720,206.248,60.702)` |
| 8 | `(8,8,0)` | `(0,-5,0)` | `(-30.949,-2.996,-60.139)..(25.820,206.794,60.138)` |
| 15 | `(15,15,0)` | `(0,-6,0)` | `(-28.417,-3.223,-64.783)..(25.850,205.682,60.632)` |

The changing matrix hashes, joint origins, and vertex bounds establish that
the hierarchy affects the geometry subsets. Plausibility is not used as a
substitute for a runtime capture.

## 5. Actual Vela runtime path

Girl uses overlay 15; `girlControl` begins at `0x00f00000`. Its model build
block is the direct Girl counterpart of the previously audited Boy block:

| Girl call site | Function |
| --- | --- |
| `0x00f01740` | `modGenAnimMatrices` (`0x8003d21c`) |
| `0x00f01778` | `objMakeGunMtx` (`0x8000bc28`) |
| `0x00f017b0` | `lightObject` (`0x800221f0`) |

Overlay-15 relocation entries 84–86 resolve these three calls directly; the
names are not inferred merely from their similarity to Boy. The surrounding
data flow passes the loaded Prop 218 model pointer to the matrix and attachment
calls. Character-specific inputs enter through the model's 28-record count and
translations, its selected 28-byte animation map, the Girl animation
index/time/transition state, and Girl's selector list.

This establishes `modLoadModel`, `modGenAnimMatrices`, `gen_anim_data`, and
`makeModelGfx` as generic character mechanisms. Exact animation IDs, maps,
timing tables, transform hierarchies, and selector construction remain
character-specific.

## 6. GirlGun placement

### VERIFIED

`girlControl` calls `objMakeGunMtx` at `0x00f01778` with the Prop 218 model
pointer. The generic function then:

1. loads model `+0x30`, the reference-record table, at `0x8000bce0`;
2. loads reference record 0 matrix ID `+2` at `0x8000bce8`;
3. multiplies that ID by the `0x40` runtime-matrix stride at `0x8000bcf8`;
4. forms the selected matrix address at `0x8000bd00` and copies the affine
   matrix to the attachment output.

Prop 218 reference record 0 is `(vertex 567, matrix 6)`. `playerGirl` has
behavior 1, so it does not take the object-type-`0x33` translation replacement
branch. The already audited remainder of `objMakeGunMtx` adds no normal
child-local rotation, translation, or scale. Therefore:

```text
GirlGun_world = Vela_matrix_6
GirlGun_local = identity
```

All GirlGun selectable Props 283–291 have zero internal transform records and
all active groups use local matrix 0. They are rigid model-local geometry
submitted under the external GirlGun transform; they are not separately
skinned attachments.

Prop 291 `VelaHand` is **VERIFIED** as GirlGun slot 8 and as a rigid hand
model. Its narrower meaning as the ordinary unarmed fallback remains
**LIKELY** because this phase did not trace every state-selector condition.

## 7. `0x400` and the 452-face result

Phase 1 marked the Vela face count LIKELY. This is upgraded to **VERIFIED for
the statically traced runtime submission**:

- object definition 0 `playerGirl` selects Prop 218 and the established
  `objSetupObject` path loads it through generic `modLoadModel` at
  `0x8003b9e8`;
- every inspected successful `modLoadModel` branch reaches at least one of its
  `makeModelGfx` calls at `0x8003bf10`, `0x8003bf58`, `0x8003bf7c`, or
  `0x8003bfac`;
- `makeModelGfx` masks group flags with `0x400` at `0x8003df34` and branches
  to the next group at `0x8003df44` when set;
- applying that exact branch to Prop 218 admits 51 groups and all 452 of their
  nondegenerate triangle records, while excluding 18 groups.

A SceneRipper face count would still be useful independent capture evidence,
but it is no longer required to establish which records the traced CPU path
submits.

## 8. Boy/Vela generalization boundary

### GENERIC VERIFIED

- compact model header and texture/group/triangle/vertex record shapes;
- rigid group matrix split and four-byte vertex references;
- 16-byte transform records and row-vector hierarchy evaluation;
- animation asset chain and MSB-first packed stream;
- Root-Q10, signed packed angle interpolation, and optional scale streams;
- stored A/C/B mapping through shared `gen_anim_data`;
- child weapon object plus reference-record-0 socket extraction;
- `makeModelGfx` group flag `0x400` exclusion.

### GENERIC LIKELY

- slot 8 as the ordinary unarmed hand/fallback state;
- higher-level player selector meanings beyond the inspected call sequence.

### CHARACTER-SPECIFIC

- animation count, ID order, sample metadata, channel maps, and timing tables;
- transform count, hierarchy, translations, active matrix subsets, and
  reference vertices;
- Girl overlay selector construction and GirlGun Props 283–291.

### STILL UNKNOWN

- semantic names and gameplay contexts for the 53 Vela clips;
- live selector/transition/object state for the isolated reference pose;
- the unsupported Vela texture format for ID `0x874a`.

## 9. Required independent runtime capture

No Vela capture was found. The existing SceneRipper directories are the three
Boy captures only. Exact numerical reproduction of a real Vela pose therefore
still requires one capture.

Break at emulated PC `0x8003d908`, immediately after `gen_anim_data` returns
inside `modGenAnimMatrices`, and save:

| File | Minimum content |
| --- | --- |
| `capture.txt` | PC, model/character identity, current/previous animation indices, blend state/counter, and source pointers |
| `instance_n64.bin` | model instance through at least `+0x60`, including effective time `+0x28` and unscaled time `+0x38` |
| `object_matrix_n64.bin` | the 0x40-byte object/world matrix passed to `gen_anim_data` |
| `selectors_n64.bin` | player selector list through the `0x1000` terminator |
| `matrices_n64.bin` | 28 consecutive 0x40-byte runtime matrix slots |

An optional attachment check can capture the output matrix from
`objMakeGunMtx` and compare it directly with runtime matrix slot 6. Use the
already established `DebugMemGetPointer` RDRAM access while stopped. Do not
call `executeCodeEx` on the suspended emulator thread.

Until that comparison exists, the research decoder is suitable for continued
validation but is not yet a runtime-correlated Vela production/Forge loader.
