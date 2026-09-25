# BoyGun transform validation

Scope: the normal Boy/Juno attachment path in US-ROM
`493ced9008dbe932d6e91179b68e8630cf23a023`, limited to `objMakeGunMtx`
(`0x8000BC28`) after the established matrix-6 selection.

## Result

For the normal Boy path the complete attachment transform is:

```text
BoyGun_world = Boy_matrix_6
BoyGun_local = identity
```

This is **VERIFIED** from the instruction and data flow below. No inferred
visual alignment is used.

## Matrix selection and copy

| RAM address | instruction word | relevant effect |
| --- | --- | --- |
| `0x8000BCE0` | `8CD90030` | load model reference-table pointer |
| `0x8000BCE4` | `818D000B` | load active matrix-buffer selector |
| `0x8000BCE8` | `972A0002` | load matrix ID from the first reference record |
| `0x8000BCEC..0x8000BCF4` | `000D7880`, `018FC021`, `8F0E0010` | select one pointer from the matrix-buffer pointer sequence at object `+0x10` |
| `0x8000BCF8` | `000A5980` | matrix ID `<< 6`, giving the `0x40` slot stride |
| `0x8000BD00` | `016E2021` | form selected runtime-matrix address |
| `0x8000BD04..0x8000BD1C` | copy loop | copy 15 consecutive `f32` words to the output matrix |
| `0x8000BD20..0x8000BD38` | `mtc1`/`swc1` | write output fourth column as `0,0,0,1` |

The first Boy reference record contains matrix ID 6. The copied runtime slot
therefore supplies the complete affine transform used for the selected BoyGun
model.

## Following code does not add a child-local transform

The object-type-`0x33` branch beginning at `0x8000BD3C` may replace matrix
translation from a model reference point. The normal Boy object does not take
that special branch.

At `0x8000BE3C`, `objMakeGunMtx` calls `mathMtxXFMF` (`0x80048B60`) with a
separate reference point and three output pointers. The local declaration is:

```c
void mathMtxXFMF(Matrix mf, float x, float y, float z,
                 float *ox, float *oy, float *oz);
```

The call computes transformed point outputs. It does not mutate the copied
BoyGun matrix. No additional model-specific rotation, translation, or scale is
present in this normal path.

## Forge consequence

All nine Props 301–309 can be rendered as separate mesh instances using the
evaluated Boy matrix 6 directly. The same sampled `BoySceneSnapshot` must feed
the Boy mesh, skeleton, and attachment. Unsupported texture formats remain
explicit diagnostic materials. Attachment export remains outside this
milestone.

The normalized loader reports:

| Slot | Prop/name | active faces | VERIFIED textures | UNKNOWN textures |
| ---: | --- | ---: | ---: | ---: |
| 0 | 301 `BPistol` | 67 | 2 | 1 |
| 1 | 302 `BAutomatic` | 116 | 2 | 1 |
| 2 | 303 `BUzi` | 126 | 2 | 1 |
| 3 | 304 `BUzi1` | 106 | 2 | 0 |
| 4 | 305 `BShrinkBeam` | 110 | 2 | 1 |
| 5 | 306 `BRocket` | 142 | 2 | 1 |
| 6 | 307 `BFlameThrower` | 132 | 3 | 0 |
| 7 | 308 `BSniper` | 245 | 2 | 1 |
| 8 | 309 `JunoHand` | 32 | 1 | 0 |

Every slot renders its complete active geometry. Batches whose texture format
is still UNKNOWN use the existing neutral diagnostic material rather than a
guessed decoder.

## Remaining boundaries

- Slot 8 as the precise normal unarmed state remains **LIKELY**; it is the
  verified hand/fallback model slot, but every selector condition is not named.
- The two additional generated hand copies in `boy-test-002` remain unrelated
  to this transform proof and their ownership remains **UNKNOWN**.
- Unknown BoyGun texture formats remain **UNKNOWN**.
