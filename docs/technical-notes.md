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
slot lists; the multiplayer characters reuse Juno's or Vela's.

## Multiplayer characters and hover ships

The game's object table lists 31 "player" definitions. Besides the six campaign
characters, Forge opens 11 multiplayer characters and 8 ship models, all through
one generic loader (`core/compact_character.py`) driven by the table in
`core/roster.py`. Each entry pins the Prop's SHA-256, joint count, clip count and
IDs, and active-face count; a mismatch stops the load.

**Juno-layout models** (Green Ant 250, Red Ant 253, Tribal Man 251, Shield Bug
254, Stag Bug 255, Weevil 256, Cyborg 257, Zombie 258) have 21 joints and 51
clips whose IDs are Juno's first 51, and their player definitions list the same
BoyGun child. **Vela-layout models** (Blue Ant 248, Yellow Ant 252, Tribal Woman
249) have 28 joints and 52 clips equal to Vela's first 52, with the GirlGun
child. The first vertex-reference record of all of them is matrix 6. Forge
therefore uses the base character's timing factors and attachment definition.
Both are LIKELY because no run-time capture shows these controllers reaching the
base character's code.

Juno's timing function starts at Overlay 16 `0x01005120`, with 52 factors at
overlay offset `0x7974`. Overlays 50, 51 and 52 hold factor tables of the same
size and shape as Juno's, Lupus's and Vela's inside a smaller function with a
different dispatch. Which overlay the multiplayer controllers reach is not
proven, and overlay 50's function was not decoded, so it remains possible that
they run through that code instead.

**Hover ships** (Props 225, 228, 231 and 234; their low-detail copies 226, 229,
232 and 235 are only in the Models tab) have 8 joints and two animations: ID 779 (40 samples, looping) and ID
780 (5 samples, base pose only). No child object is listed, so there is no weapon,
and their controller was not analysed, so Game Timing is UNKNOWN and Forge uses
the technical rate.

Of the textures that are unknown to Forge, none is used by a drawn group on any
of the 21 characters: they are either the known `0x3300` record used only by groups
the game skips, or entries no group uses.

## Props and the Models tab

`core/prop_catalog.py` lists all 904 Props by reading each header: the 16-byte
name, the joint count (byte `+0x4F`) and the animation count from asset 40. A
Prop counts as animated if asset 40 gives it at least one clip. It is flagged
empty when none of its drawn groups holds triangle records; two more props turn
out empty only after degenerate triangles are removed.

`load_static_model` reuses the normal model decoding. Vertices of props without
joints all sit on joint 0 (identity) and are drawn as stored. For props with
joints each vertex is shifted by the summed stored offsets of its joint and that
joint's parents (rotation left at zero). A texture that Forge cannot decode
counts as "drawn" if any group that the game draws uses it; 67 props have one.

## Audio

All audio is in ROM asset 52, described by the small directory in asset 51. The
first seven words of the directory (`w0` to `w6`) are section offsets into asset 52:

| Section | Content |
|---|---|
| `[0, w0)` | music bank control data |
| `[w0, w1)` | music samples (2,746,560 bytes) |
| `[w1, w2)` | sound-effect bank control data |
| `[w2, w3)` | sound-effect samples (3,566,816 bytes) |
| `[w3, w4)` | sequence file: 90 compressed MIDI sequences |
| `[w4, w5)` | sequence index, 3 bytes per song (volume, tempo, reverb) |
| `[w5, w6)` | sound-effect index, 640 entries of 10 bytes |

Both banks are standard N64 `ALBankFile` structures (magic `B1`, offsets relative
to the start of the control data). The music bank has 159 instruments with 424
sounds at 22,050 Hz. The sound-effect bank has one instrument holding 640 sounds at
44,100 Hz. A wave table gives its sample offset and length, a VADPCM coefficient
book (order 2, one or four predictors) and an optional loop (start, end, count, and
the decoder state).

**Samples** are VADPCM: 9-byte frames of a header (scale, predictor) and 16 four-bit
residuals, decoded in blocks of eight with the coefficient book and the previous two
samples. The decoder is checked against the ROM: each looped wave stores the
decoder state at its loop start, and the decoded samples reproduce it bit for bit
for 171 of 174 looped waves.

**Sound effects.** An index entry is `soundBite` (the sample), volume (128 is full
scale), minimum volume, pitch (100 is original), hearing range, and priority. Forge
plays the sample at the entry's pitch times the sample's detune, scaled by volume.

**Songs** use the libultra compressed sequence format: 16 track offsets and a
division of 384 ticks per quarter note, then per track a delta time, a MIDI status
group and, for notes, a duration in place of a note-off. Byte `0xFE` starts a
back-reference that copies earlier bytes, and loops are meta events with a repeat
counter stored in the stream. All 90 sequences decode, with 95,653 notes in total.
To render one, Forge walks the events in time order and places each note using the
tempo map, the channel's program, volume and pan, the instrument's key map, and the
sample's pitch ratio `2^(((note - keyBase) * 100 + detune) / 1200)`. Pitch was
checked by rendering middle C through single-sound instruments: the strongest
partial lands on 261.6 Hz for the instruments that have it as their fundamental.

## Levels

Level names live in assets 30/31 and geometry in assets 36/37; the format and its
evidence are in [levels.md](levels.md).

## Textures

The two texture pools and the lenient decoder are described in
[textures.md](textures.md).

## Known unknowns

- Several model header fields and vertex attributes.
- Gameplay names and meanings of most animations (only clips with a known controller rule are named; see [characters.md](characters.md)).
- The player state flags behind the timing rules.
- Whether the multiplayer characters' controllers match Juno's and Vela's.
- The timing and meaning of the hover ships' animations.
- Batch flag bits, vertex colours and the remaining header tables of level blocks.
- Names of most sound effects (only 78 of 640 have a code-derived label), and how the console's synthesizer differs from Forge's renderer (reverb, chorus, sustain, bends).
