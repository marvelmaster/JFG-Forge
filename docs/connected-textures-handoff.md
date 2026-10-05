# Connected-texture discovery handoff for DK64 Forge

Recorded on 2026-10-05 from the JFG Forge implementation. Adapt the procedure to
DK64 data; source IDs, decoder assumptions, UV conventions and thresholds are
not transferable unchanged. These instructions describe local source tools.

## Intended result

Only include pieces that form one continuous flat picture: doors, signs, logos,
maps, menu images or panoramas. Shared model usage, packed atlases, loose body UV
parts and consecutive animation frames do not qualify. Copy decoded source
pixels without gutters, projection, resampling or invented content.

JFG grew from 13 manually identified two-half images to 215 reviewed assemblies,
including 22 with Bank B pieces. Examples are a 48-piece race track, a 25-piece
landing pad and an 11-piece racing logo. This is a reviewed catalog, not proof
that every possible arrangement has been recovered.

## Procedure used

1. Decode all sources once into a local RGBA cache with bank/index, dimensions
   and frame identity. JFG decoded all 7,320 entries successfully.
2. Load models and identify shared triangle edges whose UV endpoints lie along
   opposite source-image borders. Recover integer source-pixel offsets. JFG
   inspected 886 loaded drawable models; two loads failed.
3. Compare borders across both banks, including distant IDs and sources with no
   model reference. Group equal border lengths. Premultiply RGB by alpha to
   avoid matching invisible colors; reject mostly transparent or uninformative
   edges. Shortlist twelve nearest neighbors and compare border error with
   adjacent interior rows/columns. JFG performed 29,151,760 eligible comparisons.
4. Assemble reciprocal neighbors and geometry-supported offsets into larger
   components. Reject overlaps and require complete rectangular coverage. Support
   multiple rows/columns and mixed rectangle sizes, rather than only pairs.
5. Review contact sheets with candidate IDs, source IDs and dimensions. Reject
   coincidental matches, independent motifs and model layouts. Inspect rejected
   large components for valid smaller subimages.
6. Deduplicate equal layouts and redundant contained fragments; retain genuine
   alternate images. Publish only reviewed layouts in a separate catalog.

The search uses heuristics. Edge matches generate proposals, not automatic
runtime additions. It does not establish rotated/scaled layouts or original
animation timing. Current catalog entries use frame zero.

## Coordinate and geometry pitfalls

JFG render UVs are bottom-up while decoded source rows are top-down. Discovery
therefore converts V with `source_v = 1 - render_v` before multiplying by source
width/height. Check DK64's decoder, UV construction and GPU upload independently
before adopting this conversion. Test known horizontal and vertical examples
first; an incorrect convention can reverse rows across the whole catalog.

Coplanar adjacency is useful for panels, but curved sky geometry needs a separate
path. A sky can still represent a rectangular panorama. Preserve separate tile
variants rather than combining alternate sun/background pieces. Do not force
mixed-resolution tiles to fit by scaling: JFG dome17 contains only its contiguous
main section because another tile has incompatible source dimensions.

## Runtime representation and verification

JFG `core/texture_assemblies.json` stores a name, users, evidence, canvas dimensions
and pieces with bank, index, frame, x/y and width/height.
`core/texture_assemblies.py` validates bounds, overlaps, positive sizes and exact
area coverage, then copies source rows directly into the canvas. Available
layouts require every source entry and the expected dimensions.

The UI in `gui/texture_atlas.py` supports search, related-source filtering,
nearest-neighbor zoom, source navigation and native PNG plus layout JSON export.
Its initial pixel zoom is 1. Legacy model-sheet/3D settings cannot restore
excluded previews.

Tests compare every output rectangle row against the original decoded source,
including missing/wrong-size sources, gaps, overlaps, multiple rows and both
banks. All 81 tests passed; native Qt/OpenGL checks additionally exercised large
images, source navigation and export. These checks establish composition
correctness, not proof of semantic continuity or console rendering fidelity.

## A more efficient repeat

- Establish source/UV orientation using known examples before the full scan.
- Use one resumable pipeline: decode, extract geometry evidence, scan edges,
  assemble candidates, review, validate and publish. JFG's exploratory run used
  several intermediate scripts; consolidate these stages for DK64.
- Use stable IDs hashed from source/frame/positions, not list indices. Persist
  accepted/rejected/uncertain decisions with reasons so reruns preserve review.
- Deduplicate before producing contact sheets, and show only new or changed
  candidates. Prioritize metadata/UV evidence, then reciprocal pixel matches.
- Cache decoded arrays and edge descriptors; use batched vectorized shortlist
  comparisons, followed by detailed scoring only for the shortlist.
- Keep uncertain proposals out of the shipped catalog and report source coverage,
  failures, reviewed candidates and unresolved cases explicitly.

## Reference tools

Paths below are relative to the JFG Forge repository:

- `tools/discover_texture_assemblies.py ROM --output DIRECTORY`: source cache,
  model-edge evidence and coverage report.
- `tools/scan_texture_edges.py DIRECTORY`: bank-wide candidate search and local
  review images. It does not automatically publish the catalog.
- `tools/audit_connected_preview.py ROM --output DIRECTORY`: export every catalog
  image, layout metadata and paginated contact sheets.
- `tools/smoke_ui_parity.py ROM --output DIRECTORY`: native UI/export checks.
- `tests/test_texture_assemblies.py`: source-pixel and layout regressions.

Run from the repository with its Python environment and module path configured.
Keep ROM files, decoded pixels and review images in ignored local directories.
The committed reports contain metadata; the catalog contains layout references.
