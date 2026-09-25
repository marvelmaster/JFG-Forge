# Lupus discovery, model, rig, and runtime pass

Scope: pinned US ROM SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`, canonical Prop 222, the directly
connected object tables, animation assets 40–45, overlay 17, and shared model
runtime functions already verified for Juno and Vela.

`VERIFIED` below means directly supported by the pinned ROM/model data or by a
concrete Lupus call into an already verified shared runtime routine. A shared
runtime result is identified as such when Lupus lacks an independent live
numeric capture.

## 1. Identity

The canonical Lupus player chain is **VERIFIED**:

| Item | Value | Evidence |
| --- | --- | --- |
| player object | definition 2, `playerDog` | object header at ROM `0x1715A58` |
| object entry | `0x06` | object translation table |
| primary model | Prop 222 `Dog` | player model list |
| secondary player model | Prop 798 `DogShad` | same model list; exact rendering role not investigated |
| child object | definition 401, `DogGun` | sole player child |
| powered player | definition 5, `playerDogPower` | object header at ROM `0x1715F28` |
| powered model | Prop 223 `PowerDog` | powered player model list |
| powered child | definition 401, `DogGun` | shared child list |

The filename resemblance was not used alone: object definitions, model lists,
internal names, and the canonical ROM block agree.

Additional table identities are Prop 240 `MultiDog`, Prop 241 `DogLod`, Prop
246 `MultiPowerDog`, and Prop 247 `PowerDogLod`. The `Multi*` table links are
directly visible; the exact LOD runtime policy was outside this pass.

## 2. Canonical Prop block

| Property | Value |
| --- | --- |
| Prop ID/name | 222 / `Dog` |
| ROM range | `0x1415390..0x1416F80` |
| ROM block size | 7,152 bytes, including the four-byte decompression-size prefix |
| decompressed size | 15,392 bytes |
| SHA-256 | `e69c897a48697d6adef3c922111ae05d2ef04c07ff800d91f5ee0d78ab90b3eb` |
| canonical bin | `data/generated/props-us-verified/bins/0222_Dog.bin` |

A fresh raw-deflate decode of that ROM block is byte-identical to the
canonical bin.

## 3. Static section map

All ranges are offsets within the decompressed Prop 222 block.

| Section | Range | Count/size | Stride |
| --- | ---: | ---: | ---: |
| header | `0x0000..0x0088` | 136 bytes | — |
| texture records | `0x0088..0x0100` | 15 | 8 |
| pre-group unknown | `0x0100..0x0108` | 8 bytes | — |
| groups plus boundary | `0x0108..0x0528` | 65 + boundary | 16 |
| triangles | `0x0528..0x1D08` | 382 | 16 |
| vertices | `0x1D08..0x3030` | 490 | 10 |
| vertex references | `0x3030..0x3054` | 9 | 4 |
| pre-transform unknown | `0x3054..0x3058` | 4 bytes: `0000010c` | — |
| transforms | `0x3058..0x3208` | 27 | 16 |
| trailing unknown | `0x3208..0x3C20` | 2,584 bytes | — |

The reference count is model header byte `+0x2D`, which is 9. This matters:
treating the complete gap through the transform pointer as four-byte reference
records would incorrectly turn the word `0000010c` into a tenth record.

## 4. Geometry

Prop 222 uses the same compact group/triangle/vertex layout as Juno and Vela.

| Measure | Result |
| --- | ---: |
| stored vertices | 490 |
| stored triangle records | 382 |
| stored groups | 65 |
| admitted groups | 44 |
| groups excluded by `0x400` | 21 |
| admitted triangle records | 361 |
| admitted nondegenerate faces | 361 |
| excluded triangle records | 21 |
| excluded degenerate records | 16 |
| active referenced source vertices | 459 |
| rigid assignment conflicts | 0 |

Active matrix IDs are:

```text
1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 14, 15, 17, 19, 20, 22, 23, 25, 26
```

The raw XYZ bounds are `(-34,-39,-56)` through `(34,45,39)`.

The exclusion rule applies to Lupus through the same `makeModelGfx` path:
`0x8003DF34` masks group flag `0x400`, and `0x8003DF44` skips that group.
Overlay 17 supplies the Prop 222 model to the generic player model path. This
is shared-code-path verification, not an inferred visual rule.

## 5. Textures

| Index | Texture ID | Size | Marker | Status | Group use |
| ---: | ---: | ---: | ---: | --- | --- |
| 0 | `0x83D2` | 36×32 | `1100` | VERIFIED RGBA16 | 3 admitted |
| 1 | `0x8431` | 16×8 | `3300` | unsupported | 5 excluded only |
| 2 | `0x8149` | 16×16 | `1100` | VERIFIED RGBA16 | 4 admitted |
| 3 | `0x8138` | 48×40 | `1100` | VERIFIED RGBA16 | 8 admitted |
| 4 | `0x9A01` | 32×32 | `0100` | unsupported | 1 admitted |
| 5 | `0x813B` | 16×16 | `1100` | VERIFIED RGBA16 | 1 admitted |
| 6 | `0x8CD5` | 32×32 | `1100` | VERIFIED RGBA16 | 11 admitted |
| 7 | `0x83D3` | 36×32 | `1100` | VERIFIED RGBA16 | 3 admitted |
| 8 | `0x83D4` | 36×32 | `1100` | VERIFIED RGBA16 | 1 admitted |
| 9 | `0x83D5` | 36×32 | `1100` | VERIFIED RGBA16 | 1 admitted |
| 10 | `0x83D6` | 36×32 | `1100` | VERIFIED RGBA16 | 3 admitted |
| 11 | `0x816C` | 16×32 | `1100` | VERIFIED RGBA16 | 2 admitted |
| 12 | `0x83D7` | 36×32 | `1100` | VERIFIED RGBA16 | 2 admitted |
| 13 | `0x814A` | 16×16 | `0000` | unsupported | 1 admitted |
| 14 | `0x83D1` | 8×64 | `1100` | VERIFIED RGBA16 | 3 admitted |

The existing verified RGBA16 decoder and signed S10.5 UV convention apply to
the 12 matching records. Marker `3300` was not decoded because it occurs only
in excluded groups. Markers `0100` and `0000` remain relevant UNKNOWN formats
because each is used by one admitted group.

## 6. Transform structure

All 27 target IDs `0..26` occur exactly once. There is one root, matrix 0;
every parent exists, parents precede children, and the graph is cycle-free.

```text
0
├─1
│ ├─2
│ │ ├─3
│ │ ├─4
│ │ ├─5
│ │ ├─6
│ │ └─7─8
│ ├─9─10─11
│ ├─12─13─14
│ └─15─16
└─17
  ├─18─19─20
  ├─21─22─23
  └─24─25─26
```

Each 16-byte record has the shared interpretation: parent ID, target matrix
ID, current/previous animation channel bytes, then three big-endian local
translation floats. The complete translations are retained in
`structural-map.json`.

Lupus reaches the shared `modGenAnimMatrices`/`gen_anim_data` path. Therefore
the following apply through verified shared runtime code:

```text
M_child_world = M_child_local * M_parent_world
stored Euler components = A/C/B
matrix helper input      = [stored0, stored2, stored1]
```

This does not constitute an independent live Lupus 27-matrix capture. Exact
numeric agreement with the live game remains **UNKNOWN** until such a capture
is made.

## 7. Vertex-reference records and sockets

At `0x8003D908` and `0x8003D99C`, `modGenAnimMatrices` reads model byte
`+0x2D`; for Prop 222 this is 9. The loop at `0x8003D918..0x8003D9AC`
transforms every record's source vertex through its named matrix and stores a
runtime reference point.

| Record | Vertex | Matrix | Source XYZ | Established purpose |
| ---: | ---: | ---: | ---: | --- |
| 0 | 467 | 16 | `(0,0,-1)` | DogGun matrix selector and runtime reference point 0 |
| 1 | 471 | 23 | `(-2,-4,4)` | UNKNOWN beyond runtime-transformed point |
| 2 | 468 | 20 | `(2,-4,4)` | UNKNOWN beyond runtime-transformed point |
| 3 | 463 | 14 | `(-4,-5,7)` | UNKNOWN beyond runtime-transformed point |
| 4 | 460 | 11 | `(2,-5,6)` | UNKNOWN beyond runtime-transformed point |
| 5 | 461 | 11 | `(2,-38,6)` | UNKNOWN beyond runtime-transformed point |
| 6 | 464 | 14 | `(-4,-39,7)` | UNKNOWN beyond runtime-transformed point |
| 7 | 469 | 20 | `(2,-37,4)` | UNKNOWN beyond runtime-transformed point |
| 8 | 472 | 23 | `(-2,-37,4)` | UNKNOWN beyond runtime-transformed point |

The source vertices occur in the marker-like excluded group region. Their
spatial arrangement is suggestive of character reference/effect points, but
no semantic labels were assigned without consumers.

## 8. Animation catalog

The same asset chain used by Juno and Vela independently resolves for Prop
222:

| Table | Lupus result |
| --- | --- |
| asset 40 Prop pair | ROM `0x160AB3C`, global entries `380..404` |
| asset 41 IDs | ROM `0x160B398..0x160B3C8` |
| asset 42/43 | per-ID offsets and packed blobs |
| asset 44 map pair | ROM `0x16FF378` |
| asset 45 maps | relative `0x2410..0x2698`, ROM `0x1702240..0x17024C8` |

Catalog results:

- 24 entries and 24 unique IDs: consecutive `582..605`;
- 15 looping, 9 non-looping;
- sample counts range from 8 to 40;
- packed sample strides range from 7 to 38 bytes;
- 23 entries serialize 27 channel slots; index 23 serializes 28;
- every map is intentionally nonidentity relative to transform-record order;
- every entry contains six runtime scale scalar streams;
- no entry needs cross-blob lookahead;
- descriptors, sample bounds, true padding, maps, and scratch channels pass
  the established structural checks.

The common map for indices 0–22 is:

```text
0,1,8,9,10,11,12,13,14,2,3,4,5,6,7,15,16,17,24,25,26,21,22,23,18,19,20
```

Index 23 uses:

```text
0,1,8,9,10,11,12,13,14,2,3,4,5,6,7,16,17,18,25,26,27,22,23,24,19,20,21
```

The final serialized channel remains the runtime zero scratch channel, as in
the already verified generic decoder.

## 9. Technical reference animation

Index 23 / ID 605 was selected because it uniquely exercises 28 serialized
slots, the distinct map, dynamic Root-Q10 Y and Z, six scale streams, and a
non-looping time domain. No gameplay name is assigned.

At technical time `17.5`:

| Result | Value |
| --- | --- |
| sample pair | 17 → 18 |
| fraction10 | 512 |
| root Q10 | `(24576,-29696,34816)` |
| root model units | `(24,-29,34)` |
| finite matrices | 27/27 |
| transformed active vertices | 459 |
| active faces | 361 |
| transformed bounds | `(-30.126499,-7.806570,-38.824142)` through `(99.640350,97.546150,142.560486)` |
| matrix SHA-256 | `95dcf65672e1a1168716fefdec3dc4ab7094f888dfab5dc970c6f397840bbc6d` |

The hash covers all 27 shared-decoder world matrices serialized as
big-endian `f32` 4×4 values in transform-record order. It is a deterministic
research regression, not a claim of live captured matrix equality.

## 10. Overlay 17 runtime path

The US Dog overlay occupies ROM `0x1F27B48`, is linked at `0x01100000`, and
contains `dogControl` plus directly connected helpers.

| Call site | Relocated target |
| --- | --- |
| `0x01101348` | `modGenAnimMatrices` `0x8003D21C` |
| `0x01101380` | `objMakeGunMtx` `0x8000BC28` |
| `0x011013B8` | `lightObject` `0x800221F0` |
| `0x011013DC` | `objAnimTextures` `0x80009734` |
| `0x01105060` | `objAnimDframe` `0x8001138C` |
| `0x01105074` | `charAnimSoundTick` `0x8002B1D4` |

The model submission block reads the selected model, calls
`modGenAnimMatrices`, then builds the child weapon matrix. No write to the 27
skeletal slots appears between that matrix generation and the following
DogGun/light/texture calls.

Animation selection belongs to `dogControl` and its local helpers. Confirmed
`objAnimSetMove` calls exist at `0x01100E08`, `0x011014F8`, and `0x01101538`.
The complete state-to-animation semantics were not named.

### Timing lead for the next task

Function `func_overlay_17_01104C50_1F2C798` calls `objAnimDframe` at
`0x01105060`. Instructions `0x01105054/58/5C` load its three arguments from
stack `+0x40/+0x30/+0x4C`. Overlay-local state/table data around
`0x011067C0` is referenced by the surrounding state machinery. Its exact
timing semantics are **PENDING**; no 24-entry Game Timing classification was
performed here.

## 11. DogGun

Object definition 401 `DogGun` has behaviour 4 and nine rigid model slots:

| Slot | Prop | Name | Active faces |
| ---: | ---: | --- | ---: |
| 0 | 320 | `DogPistol` | 77 |
| 1 | 321 | `DogAutomatic` | 78 |
| 2 | 322 | `DogUzi` | 95 |
| 3 | 323 | `DogUzi1` | 80 |
| 4 | 324 | `DogShrinkBeam` | 86 |
| 5 | 325 | `DogRocket` | 80 |
| 6 | 326 | `DogFlameThrower` | 98 |
| 7 | 327 | `DogSniper` | 210 |
| 8 | 328 | `DogGrenade` | 132 |

Every slot has zero internal transform records, and active groups use local
matrix 0. `objMakeGunMtx` reads the first Prop 222 reference record's matrix
ID and copies that runtime slot. For normal player type 1, the later special
object-type `0x33` translation branch does not run, and the generic function
adds no child-local transform:

```text
DogGun_world = Lupus_matrix_16
DogGun_local = identity
```

This attachment is **VERIFIED**. Unlike BoyGun and GirlGun, the ninth slot is
named `DogGrenade`; there is no hand/fallback-named model. The exact unarmed
selector behavior remains **UNKNOWN**.

## 12. Mechanisms across Juno, Vela, and Lupus

| Mechanism | Juno | Vela | Lupus | Classification |
| --- | --- | --- | --- | --- |
| compact model records | verified | verified | verified | generic across all three |
| `0x400` exclusion | verified | verified | shared verified path | generic across all three |
| rigid matrix splits | verified | verified | verified | generic across all three |
| 16-byte transforms | 21 | 28 | 27 | generic format, character-specific topology |
| packed animation / Root-Q10 / fraction10 | verified | shared path | structural parse + shared path | generic across all three |
| A/C/B stored mapping | live capture | shared path | shared path | generic; only Juno has live numeric proof |
| scale streams | subset | subset | 24/24 | generic format, character-specific usage |
| child weapon object | BoyGun | GirlGun | DogGun | generic architecture, character-specific models |
| attachment socket | matrix 6 | matrix 6 | matrix 16 | generic reference mechanism, character-specific ID |
| `objAnimDframe` timing | catalogued | catalogued | call verified, catalog pending | shared function, character-specific policy |

Numerical constants, hierarchies, maps, IDs, and socket numbers are not
generalized across characters.

## 13. Remaining UNKNOWNs

- Live 27-matrix correlation for a real Lupus runtime frame.
- Runtime selectors, blends, and object/world matrix for the isolated ID 605
  reference pose.
- Higher-level consumers and semantic names for reference records 1–8.
- The four-byte word `0000010c` before the transform table.
- The admitted texture formats marked `0100` and `0000`.
- The exact role of Prop 798 `DogShad` in the player model list.
- Exact unarmed DogGun selection and whether slot 8 participates.
- Full Lupus Game Timing classification and overlay state meanings.
- Any Lupus-specific matrix post-processing outside the inspected normal
  submission block; none was found in that block.

Forge integration, animation naming, unsupported texture decoding, and full
timing derivation remain outside this discovery pass.
