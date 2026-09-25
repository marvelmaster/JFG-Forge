# Vela Phase 1: identity and static structural map

Scope: pinned US Z64 ROM, SHA-1
`493ced9008dbe932d6e91179b68e8630cf23a023`. This phase identifies the base
Vela asset and maps its stored static structures. It does not decode Vela
animations, establish a runtime pose, place attachments, or integrate Vela
into Forge.

Machine-readable evidence:
[`phase1-structural-map.json`](phase1-structural-map.json). Reproduction helper:
[`analyze_vela_phase1.py`](analyze_vela_phase1.py).

## 1. Identity

### VERIFIED

`Vela == Girl / Prop 218` is verified by three independent ROM-derived links:

1. Prop-bank entry 218 and the decompressed model's internal ASCII name are
   both `Girl`.
2. Object definition 0 has the technical name `playerGirl`, is reached by
   object ID 0, and its primary model slot is Prop 218.
3. The same player definition has the immediately related `GirlGun` child;
   that child's final model slot is Prop 291 `VelaHand`.

The earlier name lead is therefore no longer merely a name-based association.

| Property | Value |
| --- | --- |
| Prop | 218 |
| Prop/internal name | `Girl` |
| Player object definition | 0, `playerGirl` |
| Relative prop-bank range | `0x6efa0..0x71380` |
| ROM compressed block | `0x140b5d0..0x140d9b0` |
| Compressed block size | 9,184 bytes (`0x23e0`) |
| Decompressed size | 19,016 bytes (`0x4a48`) |
| SHA-256 | `daaff6b50ffff82d9f586109f97f4332eda450280323faa542d8ff84fd2f5409` |
| Canonical local output | `data/generated/props-us-verified/bins/0218_Girl.bin` |

The canonical output is byte-identical to a direct re-decompression of the
ROM block. No duplicate extraction was created.

### Related candidates

Prop 219 `PowerGirl` immediately follows Prop 218. Object definition 3 is
named `playerGirlPower`, selects Props 219 and 795, and shares the `GirlGun`
child. This is strong direct evidence for the upgraded Vela analogue.

Other named model variants are Props 236 `MultiGirl`, 237 `GirlLod`, 242
`MultiPowerGirl`, and 243 `PowerGirlLod`. They were identified and confirmed
to use the compact model container, but they were not analyzed beyond the
identity and header checks required to distinguish the base candidate.

## 2. Header and section map

All ranges below are half-open. The exact counts, offsets, and strides are
**VERIFIED as stored structure**: every region closes exactly at the next
header pointer, the group boundary record ends both record sequences, and the
declared file size equals the decompressed size.

| Region | Range | Count / stride | Status |
| --- | --- | --- | --- |
| Header | `0x0000..0x0088` | 136 bytes | VERIFIED |
| Texture records | `0x0088..0x0108` | 16 × 8 | VERIFIED |
| Unknown/padding before groups | `0x0108..0x0110` | 8 bytes | UNKNOWN |
| Groups plus boundary record | `0x0110..0x0570` | 69 + 1 × 16 | VERIFIED |
| Triangle records | `0x0570..0x2320` | 475 × 16 | VERIFIED |
| Vertex records | `0x2320..0x3a18` | 588 × 10 | VERIFIED |
| Vertex-reference records | `0x3a18..0x3a20` | 2 × 4 | VERIFIED layout |
| Transform records | `0x3a20..0x3be0` | 28 × 16 | VERIFIED layout |
| Trailing region | `0x3be0..0x4a48` | 3,688 bytes | UNKNOWN |

### Header comparison

| Field | Girl value | Comparison with Boy |
| --- | ---: | --- |
| `+0x10` texture count | 16 | MATCHES field, count differs |
| `+0x12` vertex count | 588 | MATCHES field, count differs |
| `+0x14` triangle count | 475 | MATCHES field, count differs |
| `+0x16` group count | 69 | MATCHES field, count differs |
| `+0x18` texture start | `0x88` | MATCHES |
| `+0x1c` vertex start | `0x2320` | MATCHES field, offset differs |
| `+0x20` triangle start | `0x570` | MATCHES field, offset differs |
| `+0x24` group start | `0x110` | MATCHES field, offset differs |
| `+0x30` reference start | `0x3a18` | MATCHES field, offset differs |
| `+0x34` transform end | `0x3be0` | MATCHES field, offset differs |
| `+0x48` file size | `0x4a48` | MATCHES field, size differs |
| `+0x4f` transform count | 28 | MATCHES field, count differs |
| `+0x54` transform start | `0x3a20` | MATCHES field, offset differs |

The exact section arithmetic independently supports the same record strides as
Boy: texture 8, group 16 plus boundary record, triangle 16, vertex 10,
reference 4, and transform 16 bytes.

The old pre-migration `vela_skeleton.json` is not evidence for this map. Its
generator started at `0x3a18`, which is the two-record reference table, and
then treated the transform fields in the wrong order. That explains its
initial tiny floating-point values. The header's actual transform start is
`0x3a20`.

## 3. Static geometry

### Stored facts and consistency checks

| Metric | Result |
| --- | ---: |
| Stored vertices | 588 |
| Stored triangle records | 475 |
| Groups | 69 |
| Groups admitted by the established `0x400` test | 51 |
| Groups excluded by that test | 18 |
| Triangle records in admitted groups | 452 |
| Geometrically degenerate triangles in admitted groups | 0 |
| Referenced source vertices in admitted groups | 551 |
| Triangle records in excluded groups | 23 |
| Degenerate records in excluded groups | 15 |
| Nondegenerate records in excluded groups | 8 |

All local triangle indices are in their group ranges. All 51 admitted groups
have ordered matrix splits inside the local vertex count. No active face
assigns one source vertex to contradictory matrices. Six excluded one-vertex
groups have nonsensical split bytes, consistent with Boy's warning that
excluded records must not be interpreted as ordinary mesh groups.

The active geometry references matrix IDs:

```text
2, 5, 8–24, 26
```

Raw stored XYZ has bounding box `(-23, -60, -32)` to `(33, 42, 26)`.

### Confidence boundary

The exact counts, range validity, and nondegeneracy are **VERIFIED data
properties**. The following Vela meanings are **LIKELY**, supported by the
generic model code path plus the complete structural consistency above, but
not by a Vela runtime capture in this phase:

- vertex `+0/+2/+4` as Big-Endian signed XYZ;
- triangle `+1/+2/+3` as group-local indices;
- group byte `+0` as texture record;
- group `+1..+3` and `+4/+5` as rigid matrix choices and splits;
- group `+6/+8` as vertex/triangle range starts;
- group flag `0x400` as the runtime exclusion condition for this Vela model.

No static transformed pose or model export was created.

## 4. Texture inventory

All 16 record IDs resolve through the established `texLoadTexture` tables to
ROM assets. All 16 records are referenced somewhere in the stored group table;
15 are referenced by admitted groups.

| Index | ID | Dimensions | Marker | Classification |
| ---: | ---: | ---: | ---: | --- |
| 0 | `0x8215` | 32×64 | `11 00` | VERIFIED RGBA16 |
| 1 | `0x8213` | 48×40 | `11 00` | VERIFIED RGBA16 |
| 2 | `0x80fa` | 20×32 | `11 00` | VERIFIED RGBA16 |
| 3 | `0x8217` | 32×16 | `11 00` | VERIFIED RGBA16 |
| 4 | `0x820f` | 64×32 | `11 00` | VERIFIED RGBA16 |
| 5 | `0x8211` | 64×32 | `11 00` | VERIFIED RGBA16 |
| 6 | `0x8219` | 16×16 | `11 00` | VERIFIED RGBA16 |
| 7 | `0x8212` | 16×16 | `11 00` | VERIFIED RGBA16 |
| 8 | `0x8436` | 8×16 | `11 00` | VERIFIED RGBA16 |
| 9 | `0x8422` | 8×16 | `11 00` | VERIFIED RGBA16 |
| 10 | `0x80fb` | 16×32 | `11 00` | VERIFIED RGBA16 |
| 11 | `0x8431` | 16×8 | `33 00` | UNKNOWN format; excluded groups only |
| 12 | `0x80f8` | 24×20 | `11 00` | VERIFIED RGBA16 |
| 13 | `0x874b` | 44×44 | `11 00` | VERIFIED RGBA16 |
| 14 | `0x874a` | 16×16 | `01 00` | UNKNOWN format; admitted group(s) |
| 15 | `0x821d` | 16×24 | `11 00` | VERIFIED RGBA16 |

The 14 `11 00` assets match the existing pixelvalidated manifest and decoder.
Markers `33 00` and `01 00` overlap Boy's already known unsupported marker
set. No new decoder or Vela-specific texture rule was introduced.

## 5. Transform hierarchy

The 28 records at `0x3a20` have unique target IDs `0..27`, one root, valid
parents, and parent-before-child ordering. Their topology is:

```text
root -> 0 -> 1 -> 2
2 -> 3
3 -> 4 -> 5 -> 6
3 -> 7 -> 8 -> 9
2 -> 10
10 -> 11
10 -> 12
2 -> 13
0 -> 14
14 -> 15 -> 16 -> 17 -> 18 -> 19
14 -> 20 -> 21 -> 22 -> 23 -> 24 -> 25
14 -> 26
14 -> 27
```

Every record has the same 16-byte shape as Boy: parent byte, target byte, two
channel bytes, and three finite Big-Endian `f32` values at `+4/+8/+12`. The
channel bytes are `[target_id, target_id]` for all 28 records.

This layout and topology are **VERIFIED as bytes**. Their runtime meanings as
parent, target matrix, current/second animation channel, and local translation
are **LIKELY for Vela** because they form a complete valid hierarchy matching
the established generic record shape. A Vela runtime pose/capture was not part
of Phase 1, so those semantic labels are not promoted beyond LIKELY here.

The topology differs materially from Boy's 21-node tree. Exact counts,
hierarchies, channel maps, and animation tables must remain character-specific.

## 6. Vertex-reference records

The two four-byte records immediately before the transform table are:

| Record | Vertex | Matrix | Stored XYZ |
| ---: | ---: | ---: | ---: |
| 0 | 567 | 6 | `(33, -18, -23)` |
| 1 | 572 | 10 | `(0, 3, -17)` |

Both vertex and matrix IDs are in range. The four-byte layout is VERIFIED.
Use as runtime-transformed reference points is LIKELY by correspondence with
the established generic model mechanism. In particular, record 0 makes matrix
6 an attachment lead, not a verified Vela socket.

## 7. Player child and weapon leads

### VERIFIED

Object definition 0 `playerGirl` has two models, Props 218 `Girl` and 794
`GirlShad`, and exactly one child: object definition 397 `GirlGun`.

`GirlGun` has behavior ID 4 and nine model slots:

| Slot | Prop | Name |
| ---: | ---: | --- |
| 0 | 283 | `Pistol` |
| 1 | 284 | `Automatic` |
| 2 | 285 | `Uzi` |
| 3 | 286 | `Uzi1` |
| 4 | 287 | `ShrinkBeam` |
| 5 | 288 | `Rocket` |
| 6 | 289 | `FlameThrower` |
| 7 | 290 | `Sniper` |
| 8 | 291 | `VelaHand` |

This is the direct Vela-side structural analogue of BoyGun. The mapping only
establishes the child and selectable models. It does not establish which state
selects slot 8, whether every weapon asset includes hand geometry, or how the
child is placed.

### UNKNOWN

The GirlGun attachment matrix remains UNKNOWN. Girl reference record 0 selects
matrix 6 and is a concrete lead for Phase 2, but Boy's matrix-6 result is not
being transferred without tracing Girl's actual runtime placement.

## 8. Boy/Juno comparison matrix

| Property | Boy/Juno | Vela candidate |
| --- | --- | --- |
| Prop | 220, VERIFIED | 218, VERIFIED |
| Model name | `Boy` | `Girl`, VERIFIED |
| Decompressed size | 20,848 | 19,016, VERIFIED |
| Texture records | 18 | 16, VERIFIED |
| Groups | 82 | 69, VERIFIED |
| Stored triangles | 520 | 475, VERIFIED |
| Stored vertices | 660 | 588, VERIFIED |
| Vertex references | 2 | 2, VERIFIED layout |
| Transforms/joints | 21 | 28, VERIFIED count; semantic role LIKELY |
| Transform topology | Boy 21-node tree | distinct 28-node tree, VERIFIED topology |
| Active matrix IDs | `2,4,5,7..19` | `2,5,8..24,26`, LIKELY runtime use |
| Admitted/skipped groups | 65 / 17 | 51 / 18, LIKELY runtime split |
| Runtime-visible faces | 502 | 452, LIKELY |
| RGBA16 textures | 14 | 14, VERIFIED against manifest |
| Unsupported textures | 4 | 2 (`33 00`, `01 00`), VERIFIED markers |
| Child object | definition 399 `BoyGun` | definition 397 `GirlGun`, VERIFIED |
| Weapon/hand models | Props 301–309 | Props 283–291, VERIFIED slots |
| Known attachment socket | matrix 6, VERIFIED | UNKNOWN; matrix 6 is a lead only |

## 9. Generalization boundary

### LIKELY GENERIC IF A VELA RUNTIME VALIDATION CONFIRMS IT

- verified prop-bank extraction and ROM identity;
- compact model header counts and section pointers;
- 8/16/16/10-byte texture/group/triangle/vertex record layout;
- group boundary-record convention;
- triangle-local indexing and group range arithmetic;
- rigid matrix split selection;
- 4-byte vertex references;
- 16-byte transform record storage;
- texture ID resolution and existing RGBA16 decoding;
- object-definition model/child lists and attachment slot metadata.

### CHARACTER-SPECIFIC UNTIL PROVEN OTHERWISE

- exact counts, offsets, hierarchy, translations, and channel mapping;
- animation table, IDs, timing, selectors, and pose behavior;
- GirlGun slot state semantics and model contents;
- attachment/reference-point semantics and socket matrix;
- unsupported texture formats;
- semantic node names and gameplay contexts.

No `boy_*` module was renamed, moved, generalized, or behaviorally changed.

## 10. Phase-2 blockers

1. Capture or statically trace one ordinary Vela render to validate the
   proposed group, triangle, XYZ, rigid-matrix, and `0x400` semantics.
2. Trace `GirlGun` through the player render/`objMakeGunMtx` path to establish
   its actual reference record and attachment matrix.
3. Identify the correct Vela animation catalog source and validate its channel
   count against all 28 transforms; the old pre-migration animation JSON is not
   considered reliable evidence.
4. Validate a real Vela pose before producing a transformed mesh or Forge
   integration.

Phase 2 was not started.
