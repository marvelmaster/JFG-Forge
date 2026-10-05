# The Levels tab

The **Levels** tab lists the 412 named levels in the ROM and shows the textured
geometry of each one.

## Using it

Type a name or a level number into the search box, or sort by level number, name
or geometry block. Click a level to see it. Drag to orbit, middle-drag to pan and
scroll to zoom. The panel shows the level's name, number, geometry block, other
levels that use the same geometry, face and vertex counts, segments and how many
of its textures Forge decoded.

Several levels share one geometry block: cut-scene versions, night versions and
multiplayer variants can share world geometry while object lists and sky differ. The **Same geometry** line lists them.

## What is shown

The default view shows static world geometry. **Show placed objects (base
pose)** adds the first ordinary Prop model referenced by each supported object
definition, at the placement XYZ and definition scale. Bridge behavior 55 also
uses initializer-derived scale and yaw. **Show sky model (base
pose)** adds the referenced sky Prop at the origin. The panel reports skipped
objects: behavior helpers, non-model objects and missing geometry.

This is a structural scene preview. Other behavior-specific rotations, spawning,
model switching, gameplay-selected animation poses, original sky/water effects
and collision data still require runtime interpretation. The
hidden surface toggle below is not a complete collision viewer.

Level placements are read-only. Selection, focus, source-model navigation and
export remain available; transform, clip/rate and manual UV override editors
have been removed, and legacy session edits are ignored. The
[scene expansion](scene-actor-renderer-expansion.md) records the earlier
implementation and instruction evidence. Water deformation, conditional
spawning and original runtime phase remain open.

Texture-frame controls select or cycle decoded frames at Technical 10 frames
per second. This does not establish the game's per-level frame timing. Vertex
colours provide stored shading; complete RDP blending and lighting are not
reproduced.

The [workspace expansion](dk64-feature-parity.md) adds placement filters,
multi-selection, bounds-based picking/focus, selected-object export and missing
model markers. Optional placed-model animation uses a cached first-clip cycle
at Technical 30 samples/s; pause/resume, seconds scrubbing and cached vertex
interpolation are preview controls. Original script-selected poses remain open.

## Hidden helper surfaces

Some surfaces of a level are flat purple-and-white (the game's placeholder texture).
They are collision and trigger helpers that the game does not draw: the batch flag
0x400, the same bit that marks a model group as skipped at run time, is set on every
batch that uses the placeholder (and on only 1% of the other batches). Forge leaves
them out and lists their count (for example "2,018 (+324 hidden helper faces)").
Tick **Show hidden helper surfaces** to see them. 74 of the 301 geometry blocks
contain some.

## How it is read (evidence)

| Fact | Status |
|---|---|
| Name records are 0x118 bytes each in asset 31, indexed by asset 30; the u16 at +0x54 is the geometry block number. All 301 blocks are used exactly once or more. | VERIFIED (every block covered, names match block sizes and shared variants) |
| Blocks are the 301 compressed entries of asset 37, indexed by asset 36. | VERIFIED (all decode) |
| Block layout: header offsets, 8-byte texture records, 0x48-byte segments, 16-byte batches, 16-byte triangles, 10-byte vertices. Triangle indices are relative to their batch. | VERIFIED (all 2,016 segments contiguous, 1.3 million indices in range) |
| Texture number at record bytes 2-3, looked up in asset 1 and read from asset 0; width and height match the record in 99% of cases. | VERIFIED |
| UV scale of 32 units per texel. | LIKELY (same as models; looks right) |
| Vertex colour bytes tint the texture (texture times shade). | LIKELY (matches the material state the model code uses; looks right) |
| Batch flag 0x400 marks undrawn helper surfaces. | LIKELY (statistical match with the placeholder texture and the model flag of the same value) |
| Meaning of the other batch flag bits and the remaining header tables. | UNKNOWN |

All 11,422 texture references across all blocks decode (see [textures.md](textures.md)
for the formats).

## Export and follow-up work

**Export level glTF...** or **File, Export, Model** with Levels selected exports
the displayed geometry, selected objects/sky and current texture frames.
The glTF extras record the preview scope and omitted-object reasons. This is
an unskinned scene snapshot; animation export is unavailable for a level.
Research gaps are tracked in [status.md](status.md).

## Placement evidence

`objLoadObjList` at `0x800053F8` reads assets 28/29: a 16-byte header,
payload length at +0, then variable records with byte length at +2.
`objSetupObject` at `0x80005F14` translates the signed ID at +0 via asset 48
and reads signed XYZ at +4/+6/+8. `objGetObjdef` at `0x80004C74` resolves
assets 46/47. Definition scale is float +0; model type/count are +0x1E/+0x1F
and the model list is referenced by +0x30. The placement preview selects model
zero for ordinary model objects. Level header +0x56 supplies the object-list
index; +0x58 supplies the sky-definition index, corroborated against the live
`dome3` sky in level 92. Other levels and sky effects still need comparison.
All addresses refer to the pinned US ROM. The remaining record bytes are
preserved, not assigned guessed meanings.

`hitBridgeInit`, module 105 at ROM `0x1FBA830`, reads placement byte +0x0C
as a scale multiplier divided by 64, then applies definition scale. Byte +0x0D
sets signed yaw by shifting left eight bits; pitch and roll are zero. The
Forest Day Landing bridge matches these values in the saved runtime state:
XYZ (-2, 1, 583), scale 0.515625, yaw -16384. This rule applies only to behavior
55. See the [runtime comparison](runtime-validation.md) and its recorded scope.
