# DK64 Forge layout and feature parity

Connected textures now lists 215 reviewed flat split pictures. Original
pixels are joined edge to edge; model previews and texture sheets are excluded.
See [connected images](textures.md#connected-images).

Compared on **2026-10-05** against the local reference at
`F:/SelfmadeTools/DK64-Forge`: application source, model browser, dropdown search,
texture tab, connected-texture documentation and published screenshot.

## Latest connected-image validation

The expanded catalog contains 215 reviewed flat images, including 22 with
Bank B pieces. All 81 regression tests passed. Native Qt/OpenGL checks confirmed
all 215 catalog entries were available and exercised MizarDoor3, BearPad,
the 48-piece race track and the 11-piece racing logo, with PNG/layout exports.
The initial pixel zoom is 1 so large images are visible without the former
fourfold crop. Original source pixels and orientations are retained.

See [the expanded report](../research-results/connected-images-expanded-20261005.json),
[the native UI report](../research-results/connected-images-ui-20261005.json) and
[the DK64 implementation handoff](connected-textures-handoff.md).
Earlier validation sections below describe superseded milestones.

## Navigation and layout

The subsequent user-requested refinement hides advanced controls by default
under **View → Show advanced controls**, instead of leaving many disclosure
headers on screen. Animation selectors show compact names; search reveals
matching results. The weapon selector stays visible without its technical
attachment rows. Other models defaults to all Props, automatically plays a
selected animated model and repeats its clip, including nonlooping game clips
for inspection. Its starting camera yaw is 215°, exactly 180° from the previous
35° view; model geometry stays upright.

Textures now starts with the reference's 64-pixel thumbnail grid in 92 × 96
cells, compact metadata on the left, and source links beneath the individual
preview. Mouse-wheel zoom and individual/connected sub-tabs follow the reference
arrangement. Manual decoding diagnostics are advanced
controls. Connected previews show the assembled image with source-piece
navigation, pixel zoom and export below it.

Level placements are read-only. Transform, clip/rate and UV override editors
have been removed; old session offsets and scroll edits are ignored. Selection,
focus, source-model navigation and export remain available.

Squaddie placements now use their associated squadron's ROM size byte, rather
than the object's definition scale. `SquadronInit` copies raw +0x15 to runtime
+0x02 (PC 0x0880192C); the squad initializer writes byte × f32(0.01), or 1 for
zero (PCs 0x0030D710–0x0030D768, constant ROM 0x1EEF254). Explicit identifiers
match squadron +0x2D to squaddie +0x11; identifier zero chooses the closest
squadron. CargoShip Sewer1's BlackAnt uses 0.4199999869, correcting its oversized
preview. Static and cached animated placements share this transform. Missing
squadron associations and other controllers retain their documented fallback;
runtime spawning and actor behavior are not simulated.

The refinement passed **71 tests**, including automatic repeat, camera direction,
source scale, texture layout and rejection of old object edits. Native captures
of seven views additionally confirmed autoplay, camera yaw, read-only placement
controls, the 0.42 BlackAnt scale and atlas export. Artifacts are under ignored
`local/ui-refinement-20261005/`.

The top-level tabs now match the reference: **Models, Levels, Audio, Textures**.
Models contains **Characters** and **Other models**. Sidebars use consistent
widths, spacing and searchable catalogs beside the main preview. The initial
window size is 1180 × 760 logical pixels. Dark appearance is the default;
**View → Appearance** also offers Light and System.

Characters show a compact model summary, searchable animation selection, playback,
seconds, timing mode and preview speed. Technical model/clip information,
game timing inputs, texture frames, attachments and joint debugging are in
expandable sections available in advanced mode. Other models show animation controls only for animated
assets. Level scene controls, placement tools, audio diagnostics and texture
source details use the same expandable pattern. Existing inspection controls
remain available.

**File → Export** contains workspace exports. Characters, Other models, Levels
and Audio also have local bulk-export buttons; Textures retains its PNG bulk
export. Catalog highlights follow programmatic source navigation when the
target is visible; filters are preserved and hidden targets clear the old
highlight.

## Added texture tools

Textures has **Individual texture** and **Connected textures** sub-tabs.
The latter shows only verified split-image assemblies, with search, filtering
by the selected source texture, pixel zoom and source-piece navigation.
**Export PNG + layout** preserves every decoded source pixel without gaps and
records bank-qualified IDs and rectangles. Shared model usage never adds a
texture set to this list. Model rendering and packed-sheet modes were removed.

Individual texture previews offer optional **manual decoding settings** for
width, height and the seven supported JFG formats. Overrides affect the
in-memory preview and its PNG export; source ROM bytes stay unchanged. The
connected image uses normal source decoding. Arbitrary palettes and unknown
container encodings are not inferred.

## Sessions and compatibility

Existing saved page IDs remain valid despite the new nested navigation.
Sessions also retain appearance, expanded sections, manual decoding settings,
the selected texture sub-tab and atlas controls. Restoration ends paused.
Animation list selection supports keyboard navigation without search changing
the current clip.

## Transfer limits

The generic reference tools missing from the compared JFG workspace are now
implemented. DK64-specific flat-image assemblies, instrument semantics, Kong
eyes/blinks, mouth adjustments, Tiny hair and level-specific replacements do
not establish JFG rules. Those require JFG evidence; independent texture-frame
controls and verified JFG split images are available. Original JFG
water, sky, actor behavior and remaining animation semantics remain documented
in [status](status.md). The UI is a close structural match, rather than a claim
of identical game-specific rendering.

## Earlier validation (before the split-image correction)

The earlier discovery suite passed **68 tests**. After appearance/menu changes,
the 16 workspace and seven new UI/atlas cases passed again. The new tests cover
bank-qualified atlas rectangles and unchanged source pixels, PNG/JSON export,
source navigation, frame inclusion, manual decoding without ROM mutation,
legacy page IDs, keyboard clip selection and paused section-state restoration.

The earlier version of `tools/smoke_ui_parity.py` loaded the supported ROM in native Windows Qt/OpenGL,
captured Characters, Other models, Levels, Audio and both texture views, and
exported a 20-part Boy atlas. All six captures and three 3D contexts succeeded;
the 889 atlas groups were available. Captures were visually inspected. Results
are summarized in [the validation record](../research-results/ui-parity-validation-20261005.json).
Screenshots and exported game assets stay under ignored `local/`.
