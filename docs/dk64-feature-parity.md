# DK64 Forge comparison and JFG workspace expansion

Compared on **2026-10-05** against `F:/SelfmadeTools/DK64-Forge`, its README,
animation-workspace, viewer-expansion and level-exploration documentation, and
application source. DK64 game tables/scripts are not transferred to JFG.

| DK64 capability | JFG implementation |
|---|---|
| Tab structure and compact layout | Models → Characters / Other models; Levels, Audio, Textures; searchable catalogs and expandable diagnostics; Dark/Light/System appearance |
| Connected textures | 215 reviewed flat split images from both banks; exact-pixel mosaics, zoom, source navigation and PNG + JSON export; model UV sheets excluded |
| Manual texture decoding | Optional width/height/format overrides on the decompressed in-memory preview; source ROM unchanged |
| Z64/N64/V64 loading | In-memory storage-order normalization; full normalized US SHA-1 validation; file unchanged |
| Searchable clip lists | Live results, named/favorite/personal filters; searching preserves selection/playback |
| Clip ownership/labels | JFG model clip tables establish availability; existing evidence-graded campaign names also appear in Models; unknown names stay technical |
| Favorites/personal names | Per-ROM, per-model JSON library; personal names visibly separate from recovered names |
| Clip comparison | Independent selections/cameras, synchronized normalized progress, shared scrubber/playback |
| Optional interpolation | Characters/Models show integer samples or existing JFG interpolation |
| Slow/fast playback | Character preview clock multiplier 0.1–5×, separate from the JFG gameplay movement/timing input; authored export timing remains unchanged |
| Low-detail/multiplayer variants | Campaign variant selector navigates to ROM-named Multi/Lod/Shad Props with generic Models playback/export |
| Viewer sessions | Manual save/open, optional remember-on-close; poses, cameras, attachments, filters, object selections and texture/view settings; restored paused |
| Current view/pose export | GLB, glTF or framebuffer PNG; posed attachment and glTF camera included |
| Bulk export | Listed character clips as animated glTF; shown models/levels as static GLB; shown songs/sounds as WAV; shown textures as PNG |
| Progress/cancellation | Cancel between entries; per-entry failure/cancellation report |
| Animated prop GLB | Existing rig/clip exporter plus embedded buffers and textures |
| FPS/grid/trilinear | Global 3D options, red X/blue Z ground axes; smooth texture preview; PNG texture exports keep original pixels |
| Preview lighting/fog | Optional geometry lighting and distance fog; explicitly preview controls |
| Renderer visibility/cache | Uniform-location cache, conservative static batch frustum rejection; moving geometry retained |
| Background loading | Serialized CPU character/prop/level jobs, activity indicator, stale-result rejection; Qt/GL remain on GUI thread |
| Asset caches | Character library, 12 decoded Props, four level blocks, placed-model assets and bounded texture/thumbnail caches |
| Texture browser | Thumbnail grid/list, pixel zoom, double-click model/level usage links |
| Texture sequences | Actual container frames, sequence strip/scrubbing/technical playback; no guessed consecutive IDs |
| Character texture selectors | Independent frame controls per animated bank/ID/slot; no guessed eye/clothing names |
| Placement filters | Name/definition and model/sky/marker categories; terrain retained; texture bindings preserved |
| Selection/focus/export | Ctrl/Shift multi-selection, bounds-based ray picking, double-click focus, selected current-pose GLB/glTF |
| Missing-model markers | Optional orange octahedra at stored XYZ, omitted-geometry reasons retained |
| Placed-model playback | Opt-in cached first-clip preview, technical 30 samples/s, repeated at stored XYZ/scale/yaw |

The later [scene/actor/renderer expansion](scene-actor-renderer-expansion.md)
originally added placement clip/rate/transform overrides, ROM texture scrolling,
actor clip ownership details, shared GPU textures, retained buffers and draw
state consolidation. The first-clip default below remains an inspection policy.
The [latest UI refinement](ui-parity.md) removes placement/UV override editing,
keeps placements read-only, and corrects associated-squadron enemy scale.

Level playback has pause/resume, a seconds scrubber and optional interpolation
between cached vertex poses. That interpolation is a viewer approximation and
may shorten rotating limbs; it is not inferred game interpolation.

## Controls and persistence

Use **Session** to save/open state. **Remember session on close** defaults on.
Sessions and personal libraries live in `%USERPROFILE%/.jfg_forge`; no ROM bytes
are included. Versions/fingerprints/nonfinite values are checked. Restored
sessions end paused. Personal labels never change recovered evidence grades.

**File → Export** exports the current view or shown list. Filters determine
the list. Bulk exports write `jfg-export-report.json`; cancellation retains
completed files. PNG captures the OpenGL framebuffer, excluding normal UI
controls. GLB/glTF contain portable preview geometry/materials and available
JFG RDP metadata. PNG preserves preview shader lighting/fog.

In Levels enable **Show placed objects**, optionally missing-model markers,
then search/select object rows. Double-click focuses. View picking uses the
nearest intersected object bounding box; this is conservative selection, not
collision or exact triangle visibility. Selected-object export freezes current
preview positions and texture frames.

**Animate placed models** explicitly means the first stored clip at technical
30 samples/s. Model definitions establish the model, but do not prove the
behavior's selected animation. Bounded cached cycles use discrete poses; AI,
navigation, script waits, transition rules and spawning are not simulated.

## Game-specific differences and remaining research

DK64 instruments, Tiny's procedural hair/jaw diagnostic, Kong blink/eye rules,
Fungi night replacements and DK64 effect IDs have no direct JFG implementation
to transplant. JFG already has weapons/power forms. Independent texture-slot
controls supply frame selection without inventing JFG facial semantics.

Full JFG combiner/material tables, game lighting/fog, water/UV handlers,
remaining object transforms/spawn scripts, clip names and runtime timing remain
research tasks. The reference also documents runtime/rendering gaps. Generic
viewer controls do not resolve them; [status.md](status.md) retains their scope.

## Validation

The [2026-10-05 UI parity update](ui-parity.md) documents the per-tab cleanup,
new texture tools, compatibility and latest 68-test/native validation.

Focused tests cover file validation, model-scoped annotations, self-contained
GLB images/camera, ray/frustum math, stale loads, independent comparison panes,
paused session restoration, selected geometry, cached placement cycles,
texture-slot pose preservation and live-search selection preservation.

`tools/smoke_workspace.py` exercised native Windows OpenGL with Juno, Forest Day
Landing and both comparison panes, grid/trilinear/lighting and GLB export.
Native captures were inspected. The level had 25 model/marker rows and exported
a roughly 550 KB GLB. These are viewer checks, not emulator equivalence. Images,
GLB and test settings remain under ignored `local/`.

The 266-test existing suite initially passed 263 cases. Three GUI checks still
assumed immediate loading; they were adapted to await background completion.
The complete affected 16-test Props suite then passed, including all three.
The final focused workspace/core suite passed all 33 tests. The full expensive
suite was not repeated after that targeted correction.
