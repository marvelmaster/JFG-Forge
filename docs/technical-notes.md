# Technical notes

A short summary of how JFG Forge reads the game. All offsets refer to the US
ROM (SHA-1 `493ced9008dbe932d6e91179b68e8630cf23a023`). Labels follow the
evidence levels in [characters.md](characters.md). The code lives in
`jfg_forge/core/`.

## Props

The ROM holds 904 raw-deflate "Props" (models and other assets) in a table at
ROM `0x139B800`. `core/prop_bank.py` decompresses them on demand. Forge never
writes them to disk; it reads everything from the loaded ROM.

## Model layout

Each model Prop starts with a 16-byte name and a header, followed by these
sections. `core/model_parser.py` reads them.

| Section | Record size | Notes |
|---|---:|---|
| Texture records | 8 | Texture ID and tile setup |
| Groups | 16 | Vertex and triangle ranges, texture, matrix IDs, flags |
| Triangles | 16 | Local vertex indices |
| Vertices | 10 | Position, texture coordinates and attributes |
| Vertex references | 4 | Count at header `+0x2D`, pointer at `+0x30` |
| Transforms | 16 | Count at header `+0x4F`, pointer at `+0x54` |

A transform record is: parent joint (`0xFF` for the root), the joint's matrix
ID, two animation channel bytes, and three big-endian floats for the resting
offset. The joints form a tree in which each parent precedes its children.

Groups flagged `0x400` are skipped by the game's model-drawing code and are
skipped by Forge. Every remaining vertex follows a single joint (rigid
assignment), so the models have no blend weights.

## Textures

`core/texture_formats.py` and `core/texture_rgba16.py` decode the formats these
characters use: RGBA32, RGBA16 (RGBA5551), IA8 and one layout with several
RGBA16 images. Texture coordinates are signed S10.5 fixed point. A record whose
format marker is `0x3300` is not supported; it is only used by groups the game
skips. Unsupported textures show as UNKNOWN and are never guessed.

## Materials

`core/rdp_material.py` reproduces the render state the game sets for a
material (combine mode, other mode, decal and blend ordering) for the cases that
were traced. glTF cannot express all of it, so decal layers are separated by
small offsets in exports.

## Animations

Animation data comes from ROM assets 40 to 45:

| Asset | Content |
|---|---|
| 40 | Per Prop, the range of animation entries |
| 41 | Animation IDs |
| 42, 43 | Per-ID offsets and packed sample data |
| 44, 45 | Per-Prop channel maps (which stored channel drives which joint) |

Each clip has a sample count, a loop flag, packed per-joint rotation data and a
root translation stored in Q10 fixed point. `core/animation_decode.py`,
`core/animation_catalog.py` and `core/compact_animation.py` decode them;
`core/matrices.py` builds the joint matrices (child = local x parent). The stored
Euler components are used in the order A, C, B.

## Game Timing

The game advances each animation with:

```text
phase_next = phase + delayDat * state_scale
clip_span  = sample_count        (looping clips)
clip_span  = sample_count - 1    (non-looping clips)
sample_position = phase * clip_span
```

`delayDat` is the number of video ticks since the last update (limited to 6).
Forge assumes the nominal 60 ticks per second, so:

```text
samples_per_second = clip_span * state_scale * 60
```

`state_scale` comes from a per-animation table in each character's code, and
some entries are multiplied by a movement value (`max(abs(f32 +0x04), abs(f32
+0x10))` of the player, or only the lateral part). One Juno animation doubles
when a state flag bit `0x10` is set. `gui/runtime_timing.py` holds the tables.
The 60-tick conversion is nominal; PAL compensation was not investigated.

### Correction

Juno's table listed `0.009` for animations 29 and 35. The ROM holds `0.01`
(`0x3C23D70A`) at both entries, so they now use `0.01`. Only animation 1 keeps
`0.009`. This also applies to PowerBoy.

## Weapon attachments

A player's object definition names a child object (BoyGun, GirlGun or DogGun)
that has nine models. The game copies one joint's matrix, chosen by the first
vertex-reference record of the character's model, into the weapon's transform
with no extra rotation, scale or translation. `core/character_data.py` holds the
slot lists; the Green Ant reuses Juno's.

## Green Ant (LIKELY)

Prop 250 has Juno's 21-joint layout, its 51 animation IDs equal the first 51 of
Juno's, and its player definition lists the same BoyGun child. Forge therefore
uses Juno's timing table for animation indices 0 to 50 and BoyGun at joint 6.
The game code that drives the ant was not captured at run time, so both are
LIKELY. Overlays 15, 16 and 17 hold the Vela, Juno and Lupus controllers.
Overlays 50, 51 and 52 hold similar tables in a different, unanalysed function,
so it remains possible that the ant runs through that code instead.

## Known unknowns

- Several model header fields and vertex attributes.
- Gameplay names and meanings of most animations.
- The player state flags behind the timing rules.
- Whether the ant's controller matches Juno's.
