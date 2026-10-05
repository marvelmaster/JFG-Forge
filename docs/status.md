# Current status and open work

Documentation review: **2026-10-05**. Validation describes the local source
workspace; this documentation-only publication does not publish the outstanding
implementation changes. This page describes the current source in
`jfg-re/`, for the pinned US ROM normalized from Z64/V64/N64. It separates implemented features,
missing features and research that still needs evidence. It is an inventory,
not a commitment to an implementation order.

## Implemented features

| Area | Current support | Details |
|---|---|---|
| ROM | Read-only loading; storage-order normalization, size and full SHA-1 validation | [README](../README.md#required-rom) |
| Characters | 21 entries: 6 campaign, 11 multiplayer, 4 hover ships; rigs, animation playback and character glTF export | [Characters](characters.md), [Export](export-gltf.md) |
| Models | Catalogue of 904 Props; 604 static models and 284 animated Props; generic clip playback and glTF export (Technical timing) | [Models](models.md) |
| Levels | 412 named levels, 301 geometry blocks; placed models/sky/markers, filters/picking, cached Technical animation and snapshot/selected-object export | [Levels](levels.md) |
| Textures | 7,320 listed entries: Bank A 6,663, Bank B 657; manual decoding, frames, 215 reviewed flat split images (no model layouts) and PNG/layout export | [Textures](textures.md) |
| Audio | 80 nonempty songs and 547 playable sound effects; playback, seeking, WAV/MP3 export, instrument bank selection and ROM-derived reverb | [Audio](audio.md) |
| Workspace | Sessions, clip comparison, favorites/personal names, live search, bulk export, current-pose GLB/PNG, global view options and background loading | [DK64 comparison](dk64-feature-parity.md) |
| UI | DK64-style grouped tabs, compact sidebars, expandable diagnostics, searchable animation lists and Dark/Light/System appearance | [UI parity](ui-parity.md) |

The latest UI refinement hides advanced controls by default, starts animated
Props automatically with repeat, rotates their default camera by 180°, matches
the reference texture grid/layout, and removes placement/UV editing. Squaddie
scale comes from its associated squadron record. Old session edits are ignored.
The current regression suite passes 71 cases; native inspection covers seven
views. See [UI parity](ui-parity.md#navigation-and-layout).

The reproducible [coverage audit](../research-results/rom-coverage-audit.json)
checks all 7,320 texture entries and their 8,600 decoded frames: zero failures.
It loads 282 animated Props and evaluates 11,271 poses (start, fractional and
last sample per clip). Props 269 and 713 have no drawable faces. All 412 level
object lists parse, containing 20,866 placement records. These checks establish
decoder coverage, not visual equivalence, gameplay semantics or every animation
sample. Run `tools/audit_rom.py` with the supported ROM to reproduce them.

The [model-load audit](../research-results/model-load-audit.json) loads all 886
drawable models and finds no undecoded textures used by their drawn groups.
The same two geometry-free entries are reported separately.

Forty-six focused regression tests cover audio automation, finite loops, placement
records, bridge transforms, sessions, annotations, comparison, selection, cached
animation, texture slots, visibility and snapshot/GLB export. The historical 265-test suite passed 264 tests initially; its old PowerBoy-name
expectation was updated after verifying shared ROM clip IDs. The six affected
name tests and all 27 audio tests passed on rerun. The workspace expansion also
passed a native Windows OpenGL smoke check of character/level/comparison views
and GLB export. Neither GUI tests nor native smoke checks establish game fidelity.
The 2026-10-04 full regression run passed 263/266 tests; its three synchronous
GUI expectations were adapted to background loading and all 16 affected Props
tests passed on rerun. See [validation scope](dk64-feature-parity.md#validation).
The [scene/actor/renderer expansion](scene-actor-renderer-expansion.md) adds 13
focused cases and native checks for actor playback, selected placement clips,
ROM scrolling, GPU resource reuse and identical framebuffer pixels on rebind.
The ten existing material and five vertex-color tests also pass.

## Features still missing

| Area | Open work | Current behavior |
|---|---|---|
| General Props | Runtime clip semantics and original timing; empty animation-only helpers | Generic playback/export; technical clip identifiers |
| Levels | Remaining behavior rotations/spawning, water deformation, original sky effects, collision and runtime phase | Decoded bridge and squadron-based Squaddie transforms; ROM texture-scroll velocities; read-only placements and optional camera-follow sky preview |
| Character roster | Six multiplayer versions of Juno/Vela/Lupus, low-detail/shadow variants, NPCs and enemies in the Characters tab | Models may be inspected in the Models tab; generic Props playback available; no curated roster/timing mapping |
| Texture playback | Game-selected facial frames and original timing; full N64 mipmap/tile behavior | Independent character slots; frame selection/Technical playback in Models/Levels/Textures; trilinear preview |
| Audio synthesis | Exact chorus resampling and console fixed-point behavior | Sustain, mid-note pitch bends and volume/pan/effect-send changes implemented; finite sample-loop tails corrected; chorus/reverb resampling remain approximate |
| Platforms and ROMs | Validation beyond Windows 11 and the pinned US revision | Other systems/revisions untested; Z64/V64/N64 orders supported |

The [runtime workbench](runtime-validation.md) records emulator capture steps
and the exact limits of snapshot and audio comparisons.
The new Forest Day Landing state corroborates one Juno pose: 21 joint matrices,
maximum absolute error 0.0000152587890625. Twenty-two objects match ROM placement
records; bridge scale/yaw and the `dome3` sky identity are independently checked.
This does not close the remaining scene, animation or rendering research.

## Research and validation still open

- **Multiplayer controllers:** timing and weapon placement are LIKELY. Runtime
  captures must establish whether controllers use the campaign paths or the
  separate overlay 50/51/52 paths. See [technical notes](technical-notes.md#multiplayer-characters-and-hover-ships).
- **Hover ships:** animation timing and gameplay meaning are UNKNOWN; Forge
  falls back to Technical timing.
- **Animation semantics:** most gameplay names, the meaning of stance sets and
  some player state flags behind timing rules remain unresolved.
  The complete clip-ownership audit finds 1,863 clips across the 100 curated
  animated enemy/NPC entries; 371 now have direct or shared controller-context
  labels. Across all 3,761 model/clip entries, 2,824 remain UNKNOWN. Numeric
  controller roles and ownership are available in Models; see
  [animation attribution](animation-attribution.md) for evidence and exclusions.
- **Model structures:** some header fields, vertex attributes and auxiliary
  records still lack established semantics. Generic joint IDs remain technical
  identifiers rather than anatomical bone names.
- **Level structures:** other batch flags and header tables are UNKNOWN. UV
  scale, vertex tinting and the 0x400 helper-surface interpretation remain LIKELY
  at the evidence level documented in [levels.md](levels.md#how-it-is-read-evidence).
- **Texture fidelity:** lenient layouts and additional formats are LIKELY;
  RGBA32 odd-row swapping has mixed evidence. Successful decoding does not
  establish pixel accuracy. More reference and runtime comparisons are needed.
- **Materials and export:** untraced RDP states, hardware coverage and facial
  texture-frame selection are outside the frozen material milestone. glTF
  decal offsets approximate coplanar layering; they are not original geometry.
- **Audio validation:** the historical loop-state comparison matches 171 of 174
  looped waves. The three mismatches need explanation before claiming complete
  bit accuracy. Most sound effects remain unnamed; 109 playable entries have code-derived
  labels. Full console-renderer equivalence remains unproven.
- **Archived validation scope:** independent live Lupus matrix correlation is
  outside the six-character milestone. Historical visual validations apply to
  their recorded models and states, not automatically to every newer entry.

The connected-image milestone passed 81 tests and a native UI/export check.
See [the discovery handoff](connected-textures-handoff.md) and
[the expanded report](../research-results/connected-images-expanded-20261005.json).

## Documentation map and historical reports

Use the [README](../README.md) and this directory for current Forge behavior.
The [workspace documentation index](../../docs/README.md) links current usage
and historical research.

`../../docs/COMPLETE_GUIDE.md`, `EXTRACTION_SUMMARY.md`, `prop_formats.md`,
`prop_binary_format.md`, `animation_extraction.md`, and
`../../research/JFG_Reverse_Engineering_Doku.md` record earlier extraction
attempts. Some commands, output folders, counts and format interpretations do
not match the current checkout. They are preserved as historical evidence,
not supported installation instructions or the current open-work list.

`../../jfg-forge-archive/` preserves research and frozen milestones, including
[character/material milestone 2](../../jfg-forge-archive/knowledge/verified/character-and-material-milestone-2.md).
Its dated evidence should retain its original scope. Later Forge capabilities
are documented here rather than retroactively asserted in a frozen milestone.
