# The Textures tab

## Connected images

**Connected textures** contains only verified pieces of one flat picture.
The current catalog has **215 reviewed split images**, including 22 with Bank B
pieces. It includes doors, badges, sky panoramas, menu artwork, a 48-piece race
track overview, a 25-piece landing pad, and an 11-piece racing logo. Layouts can
contain multiple rows and columns with differently sized rectangles. Original
source pixels are copied without padding, resampling, lighting or projection.
MizarDoor3 still joins A923 and A924; BearPad joins A6054 and A6055.
Shared layouts and redundant contained fragments are deduplicated.

Model co-usage does not establish a connected picture. Boy, IntroGirl,
Fatbob_Intro2 and other model texture layouts are excluded. There is no model
preview or texture-sheet mode in this tab. Unverified arrangements are omitted;
the catalog does not claim exhaustive discovery of every possible split image.
Individual textures remain available in **Individual texture**.

Search or browse all connected images; disable Browse all to show only images
containing the selected texture. Pixel zoom defaults to 1 and uses nearest-neighbor scaling.
Double-click a piece to inspect its individual source. **Export PNG + layout**
saves the native-resolution joined pixels and JSON with source IDs, rectangles,
ROM identity and verification evidence. Old sheet/model session settings cannot
restore excluded content. Neither previews nor exports change the ROM.

Layouts are maintained in `core/texture_assemblies.json`; composition and validation
are implemented in `core/texture_assemblies.py`. New entries require a
verified continuous motif and correct outer borders, not just common model
usage or similar edge colors. Tests compare every output row against its source.
`tools/audit_connected_preview.py` exports every catalog image and paginated contact sheets
for review. The earlier 172 projected images/714 model previews audit describes
a superseded implementation and is not evidence of flat-image assembly.

The [DK64 handoff](connected-textures-handoff.md) explains the algorithm, pitfalls
and a more efficient repeatable review process.

### Discovery coverage

The October 2026 scan decoded all 7,320 entries in both banks and inspected 886
successfully loaded drawable models (two model loads failed). A bank-wide search
compared 29,151,760 eligible borders, including distant and cross-bank IDs.
Candidate matching uses source UV adjacency and reciprocal pixel-edge matches;
visual review rejects loose UV parts, animation alternatives and coincidental
edges. Renderer V coordinates are inverted back to source row coordinates before
joining tiles. Matching alone never adds an image to the runtime catalog.

Run `tools/discover_texture_assemblies.py ROM --output DIRECTORY`, then
`tools/scan_texture_edges.py DIRECTORY` to produce review candidates. The latter
compares borders at least eight pixels long, shortlists twelve nearest neighbors,
and writes source images/contact sheets locally. No ROM pixels are shipped in
the catalog. The search is broad, but is not proof that every rotated, scaled,
animated or otherwise ambiguous arrangement has been recovered. The dome17
entry is the contiguous main section; a differently sized source tile prevents
an exact-pixel assembly of its entire sky. Source orientation is retained.

Validation: 81 tests pass, including every output pixel, unavailable sources,
wrong dimensions, overlapping/gapped layouts, multirow mosaics and both banks.

The **Textures** tab is a browsable texture bank: all 7,320 textures in the ROM,
with a preview, size and format, the models and levels that use each one, and
PNG export.

## Using it

The default layout follows DK64 Forge: thumbnail grid and compact metadata on
the left, individual/connected preview tabs on the right, source links beneath
the individual image. Scroll over the image to zoom. **View → Show advanced
controls** reveals manual decoding and additional diagnostics.

Search by name, by number (for example `A2715`) or by the model or level that
uses a texture. Filter by bank, by decoded or not decoded, or by used and unused,
and sort by number, name or size. Click a texture to see it, step through
animated textures with the **Frame** box, and use **Export PNG...** for one
texture or **Export shown list as PNG files...** for everything currently shown
(after filtering). Files are named like `A2715_Forest_Sequence_Start.png`.

The list appears at once. The names are filled in a moment later, once Forge has
read every model and level to find where each texture is used.

## Names

**The ROM stores no texture names.** Forge derives a name from usage: the first
model that uses the texture, otherwise the first level, followed by `+N` for the
other users and the size, for example `Forest First +7 · 32×64`. Textures nothing
uses are called `Unused`. Treat the names as labels, not the game's own names.
The full list of users is shown for each texture.

## Banks

| Bank | Table / data assets | Used by |
|---|---|---|
| A | 1 / 0 (6,663 listed textures) | levels, and models whose texture id has the high bit set |
| B | 3 / 2 (657 listed textures) | models without the high bit |

These are the entries returned by `core/texture_bank.py:list_textures`, which
excludes empty or invalid header slots; table slots are not the same as listed
textures. The two banks total 7,320. On 2026-10-03 every listed entry's default
frame was decoded successfully from the validated US ROM. This checks decoder
coverage, not visual fidelity or every frame of a multi-frame texture.

## Decoding and limits

All 7,320 textures decode. The header's format number is one of the standard
N64 image formats: 0 RGBA32, 1 RGBA16, 2 I8, 3 I4, 4 IA16, 5 IA8, 6 IA4 (the
texel sizes match, for example format 3 stores half a byte per texel). The strict
decoder that handles most textures is VERIFIED against reference images for
RGBA16. Textures that carry mipmap bytes after the pixels, or have no stride in
their header (about 760), and the formats I8, I4, IA16 and IA4 decode through a
lenient path that shows the base image of each frame; that path is LIKELY, not
VERIFIED. In every one of these formats except RGBA32 the odd rows are stored
with their 4-byte words swapped (the way texture memory holds them), which Forge
undoes; this was found by checking that images become smooth, and it also
corrects the IA8 textures (ship glows and similar), which were slightly scrambled
before. RGBA32 is left as stored because its evidence is mixed. Nine textures
(Bank B, numbers 180 to 188) are not compressed at all (their header flag at +0x19
is 0), so Forge reads their pixels directly.
