# JFG Forge v0.1 plan

Status: M0 renderer-neutral data/scene APIs, M3 animation/skeleton tooling, the
technical Animation Browser, the first user-facing export milestone, and M4
BoyGun attachment browsing/rendering are implemented. The frozen Boy/Juno
Character Milestone 1 baseline is
[`../knowledge/verified/boy-juno-milestone-1.md`](../knowledge/verified/boy-juno-milestone-1.md).

Current desktop milestone:

- launch from `jfg-re/` with `python -B tools/run_jfg_forge.py` after installing
  the declared project dependencies;
- dependencies: PySide6, PyOpenGL, and NumPy;
- visible now: Boy / Prop 220 at animation 0, time 0 in an OpenGL 3.3 viewport,
  with 14 VERIFIED RGBA16 textures, neutral UNKNOWN-format batches, orbit/pan/
  zoom controls, and a model-information panel;
- the Animation Browser exposes all 52 clips by technical index/ID, sample
  count, stride, loop domain, root-field widths, and current decoder sample /
  interpolation state. Previous/next navigation wraps at the catalogue ends,
  switching preserves playback state and speed, and a selected clip can be
  retained as a metadata-only reference;
- gameplay context is a pinned read-only mapping of only the ten entries marked
  `VERIFIED GAMEPLAY CONTEXT` in
  `research/boy/boy-animation-identification.md`; all other entries display
  `UNKNOWN`, and no animation names are inferred;
- playback retains fractional scrubbing, catalogue loop semantics, pause/stop,
  and one `Movement / Speed` slider from 1.0 through 5.0 in 0.1 steps. Game
  Timing uses the complete runtime-derived VI/state catalogue for all 52 Boy
  states: 31 fixed, 20 movement-dependent, and one state-flag-dependent
  formula. For movement-dependent clips the slider is the simulated runtime
  movement input and is applied exactly once. For fixed clips and index 13 it
  is an additional preview/export multiplier; index 13's independent flag
  remains available. Technical mode uses it as a sample-rate multiplier;
- poses and rigid vertices remain CPU-evaluated through the verified Forge
  scene path, while the existing GPU buffers and textures are reused;
- an animated skeleton debug overlay now uses the same evaluated scene snapshot
  as the mesh, with Mesh, Skeleton, and Mesh + Skeleton modes. Technical joint
  IDs 0–20 can be selected; the inspector reports active render geometry and
  joint 6 is annotated only as the VERIFIED BoyGun attachment socket. No
  semantic joint names are assigned;
- the suspicious helmet-tip patch and possible eye surface remain unresolved
  visual TODOs and are unchanged;
- the BoyGun browser exposes None plus all nine verified slots (Props 301–309),
  caches loaded attachment models/textures, and renders the selection as a
  separate mesh following matrix 6 from the same evaluated scene snapshot;
- the complete normal BoyGun placement is now runtime-code VERIFIED as matrix
  6 with identity child-local transform. Unsupported attachment textures use
  the existing diagnostic material path and remain explicitly UNKNOWN;
- model and model-plus-current-animation glTF export automatically includes
  the currently selected BoyGun slot. Its unskinned Prop mesh is an identity-
  local child of exported `jfg_node_06`, so it follows the existing joint
  animation without separate attachment keys. Attachment RGBA16 images use
  collision-safe portable sidecar names; UNKNOWN formats stay diagnostic;
- deferred: timeline editing, GPU skinning, general asset browsers, and
  executable packaging;
- further Animation Browser work is deferred: user-authored labels/notes, pose
  difference rendering, runtime selector replay, and richer animation export
  management;
- the File > Export menu now supports model-only, current-animation-only, and
  model-plus-current-animation exports. Output is glTF 2.0 with a binary
  sidecar and copied VERIFIED PNG sidecars, so the result does not depend on
  JFG Forge at import time. At this export boundary only, renderer-neutral
  `v=1-t/H` UVs become glTF's upper-left-origin `v=t/H`; PNG data is not
  rewritten. UNKNOWN texture formats remain diagnostic materials;
- exported actions use technical names such as `anim_19_ID1022`. Their
  timestamp accessors use the same `PlaybackTimingContext` and effective
  samples-per-second calculation as the current Forge preview. Pose samples
  and STEP baking are unchanged. Export calls the same corrected
  `_local_matrix_from_stored` path as Forge playback and the runtime-validated
  Boy exporter;
- a single all-52-actions export is not exposed. The current writer preserves
  JFG interpolation by baking every 10-bit state transition as STEP keys; doing
  this for all clips would produce an unnecessarily large asset and needs a
  separate export-size/design milestone.

## 1. Vision

JFG Forge should become a standalone desktop workbench for inspecting Jet
Force Gemini assets and the evidence behind their interpretation. Its core
design principle is that verified binary decoding belongs in reusable library
modules. The desktop application consumes those modules through typed,
renderer-neutral model objects; it does not reproduce binary parsing in UI
callbacks or shaders.

Long term, the same shell should host model, texture, animation, audio, level,
scene, object, export, and research/debug tools. Each format can mature
independently while exposing `VERIFIED`, `LIKELY`, `HYPOTHESIS`, and `UNKNOWN`
metadata to the UI.

## 2. v0.1 scope

The first useful release is deliberately centered on Boy/Juno:

- launch as a normal desktop application without Blender;
- open the pinned US Z64 ROM, validate its identity, and optionally use the
  existing generated prop/texture manifests as a cache;
- parse Prop 220 directly into an in-memory model representation;
- render its 502 active faces with correct per-corner UV seams;
- use the 14 already VERIFIED RGBA16 textures and diagnostic materials for
  unsupported formats;
- display the 21-node hierarchy and optional skeleton lines;
- play and scrub Boy animation 0 / ID 1026 and animation 43 / ID 1069;
- orbit, pan, and zoom the camera;
- show identity and count information for the selected model;
- select BoyGun slots 0–8 and place the selected Prop 301–309 attachment under
  the transform of Boy matrix 6;
- show confidence/status labels alongside research-sensitive properties.

The initial displayed pose should be animation 0 at time 0. This is a concrete,
decoded animation state and must not be labelled as a verified bind pose.

## 3. Existing reusable code inventory

### ROM and prop bank

| File/module | Important API | Existing capability | Reuse decision |
| --- | --- | --- | --- |
| `src/jfg_re/props.py` | `validate_rom_identity` | Streams size and SHA-1 validation for the pinned US Z64 ROM and returns `RomIdentity`. | **Direct reuse.** Move only if a future generic ROM service is introduced. |
| `src/jfg_re/props.py` | `parse_offset_table` | Validates and parses the 905-entry BE prop offset table. | **Direct reuse.** Pure and already library-quality. |
| `src/jfg_re/props.py` | `decode_prop_block` | Validates the five-byte container and raw-Deflate payload. | **Direct reuse.** Pure and independently useful. |
| `src/jfg_re/props.py` | `extract_props` | Extracts all 904 Props and writes manifests/reports. | **CLI/export workflow only.** Forge should use a new read-only `load_prop(rom, id)` service built from the two pure functions rather than invoke this writer. |
| `tools/extract_props.py` | CLI `main` | Thin argument handling around `extract_props`. | **Do not import into GUI.** Keep as a CLI consumer of the same library. |

There is no general ROM object or asset-section reader. Several modules load
the complete ROM and repeat asset-LUT access. A small immutable `RomImage`
facade should own validated bytes, bounds-checked BE reads, prop access, and
asset-section slices while continuing to call the verified functions above.

### Model, groups, vertices, and triangles

| File/module | Important API | Existing capability | Reuse decision |
| --- | --- | --- | --- |
| `src/jfg_re/boy_export.py` | `Vertex`, `Group`, `Triangle`, `BoyModel` | Typed immutable records for the confirmed Boy geometry layout. | **Reuse after small refactor.** Rename/generalize the representation without weakening Boy identity checks. |
| `src/jfg_re/boy_export.py` | `parse_boy` | Parses and validates all 660 vertices, 82 groups plus sentinel, 520 triangles, and 18 texture records of pinned Prop 220. | **Directly usable for the first Boy view.** Before attachment support, extract a parameterized model parser and retain `parse_boy` as a pinned validation wrapper. |
| `src/jfg_re/boy_export.py` | private `_matrix_id` | Implements verified group split to one matrix ID per vertex. | **Promote to public library API.** It is renderer input, not exporter detail. |
| `src/jfg_re/boy_export.py` | private `_geometry_records`, `_cross` | Builds diagnostic geometry metadata and detects geometric degeneracy. | **Small refactor.** Keep pure geometry helpers; remove report formatting from the render-data path. |
| `src/jfg_re/boy_textured_export.py` | `_following_group`, `_group_triangles`, `_is_degenerate` | Resolves active group ranges and valid triangles. | **Promote/consolidate.** These currently exist only as private exporter helpers. |
| `src/jfg_re/boy_rig_gltf.py` | private `_geometry` | Correctly expands triangle corners, preserving UV seams, one joint per render vertex, materials, and triangle `0x40` double-sided state. | **Use as an algorithmic reference and refactor into a renderer-neutral mesh builder.** Do not make glTF an intermediate format. |
| `src/jfg_re/boy_transform_analysis.py` | `build_transform_analysis` | Validates matrix hierarchy, active vertex/corner assignment, reference records, and paths to root. | **Reuse validation logic after separating report assembly.** Currently analysis/report oriented. |
| `tools/inspect_boy_static.py`, `tools/export_boy_experimental.py`, `tools/export_boy_textured_static.py` | CLI entry points | Exercise the parser and produce OBJ/report artifacts. | **CLI only.** Useful integration examples; no UI should import them. |

`parse_boy` is deliberately pinned to a single hash and hardcoded section
counts. Forge needs Props 301–309 as well. The generalization must read the
same established header fields and record strides, validate all boundaries,
and return a common `ModelAsset`. Pinned wrappers for Boy and known BoyGun
models should remain as regression gates.

### Texture resolution, RGBA16, UV, and tile state

| File/module | Important API | Existing capability | Reuse decision |
| --- | --- | --- | --- |
| `src/jfg_re/boy_export.py` | `resolve_boy_textures` | Follows TextureRecord IDs through the verified high/low table paths to ROM assets and checks the RGBA16 manifest. | **Small refactor required.** Make a model-independent `TextureResolver`; accept a manifest/cache provider instead of embedding Boy naming. |
| `src/jfg_re/textures_rgba16.py` | `parse_texture_header`, `decode_rgba5551`, `apply_odd_row_block_swap`, `decode_texture` | Complete verified `11 00` RGBA16 decoding to RGBA8888. | **Direct reuse.** These pure functions can feed GPU texture uploads. |
| `src/jfg_re/textures_rgba16.py` | `encode_png_rgba`, `decode_png_rgba` | Deterministic PNG output and reference-pixel validation. | **Reuse for exports/tests only.** The viewport can upload decoded RGBA directly. |
| `src/jfg_re/textures_rgba16.py` | `export_rgba16_textures` | Batch exporter and validation-report writer. | **CLI/export workflow only.** Forge should call `decode_texture`, not run the exporter. |
| `src/jfg_re/boy_group16_uv.py` | private `_uv` | Implements the confirmed S10.5-to-OBJ formula for one pinned 16×16 texture. | **Refactor required.** Replace with public `decode_uv(raw_s, raw_t, width, height, target_origin)`; retain the group-16 test as a regression fixture. |
| `src/jfg_re/boy_textured_export.py` | private `_tile_axis`, `_tile_state` | Decodes clamp, mirror, wrap, mask, shift, and mip-count metadata from the runtime texture header. | **Promote to public texture-sampler API.** Current function is embedded in an exporter. |
| `src/jfg_re/boy_textured_export.py` | `_build_materials`, `_build_obj_and_report` | Maps verified PNGs and produces per-corner UV OBJ output. | **Exporter only.** Extract its material decisions and UV calculation into neutral render data. |
| `tools/export_rgba16_textures.py`, `tools/export_boy_group16_uv.py` | CLI entry points | Reproducible exporters/validators. | **CLI only.** Retain as independent regression workflows. |

The renderer should preserve out-of-range UVs and express wrap, mirror, and
clamp with OpenGL sampler state. Unsupported texture formats remain labelled
`UNKNOWN` and receive a deterministic diagnostic material.

### Skeleton, animation, matrices, and rigid transformation

| File/module | Important API | Existing capability | Reuse decision |
| --- | --- | --- | --- |
| `src/jfg_re/boy_anim0_frame0.py` | `locate_boy_animation0`, `decode_frame0` | Pinned table traversal and exact frame-0 decoding for animation 0. | **Keep as regression oracle.** Forge should use the later generic catalog decoder. |
| `src/jfg_re/boy_anim0_temporal.py` | `animation_metadata`, `decode_time` | Pinned animation-0 sample interpolation, loop handling, angles, scales, and Q10 root translation. | **Keep as regression oracle.** Logic is superseded for application use by `decode_animation_time`. |
| `src/jfg_re/boy_animation_catalog.py` | `catalog_boy_animations` | Locates and structurally validates all 52 Boy animation entries and channel maps. | **Reuse after API cleanup.** It already supports IDs 1026 and 1069. |
| `src/jfg_re/boy_animation_catalog.py` | private `_tables`, `_structure`, `_packed` | Loads animation assets, parses the variable descriptor layout, and decodes packed samples. | **Promote behind public `AnimationLibrary`/`AnimationClip` APIs.** The GUI must not call underscored functions. |
| `src/jfg_re/boy_animation_catalog.py` | `decode_animation_time` | Generic 10-bit interpolation, looping/nonlooping endpoint handling, root translation, rotations, and optional scales. | **Direct algorithm reuse with a typed return value.** Presently returns nested dictionaries. |
| `src/jfg_re/boy_anim0_frame0.py` | `build_matrices` | Parses the 21 transform records and reproduces local/world row-vector matrices using the ROM sine table. | **Core reuse after split.** Separate skeleton parsing, sine-table service, and pose evaluation; accept an `AnimationSample`. |
| `src/jfg_re/boy_anim0_frame0.py` | private `_local_matrix`, `_matrix_multiply`, `_transform` | Runtime-equivalent rotation/scale/translation, hierarchy composition, and rigid point transform. | **Promote as tested pose/skinning primitives.** These are currently hidden in an artifact module. |
| `src/jfg_re/boy_anim0_temporal.py` | private `_assignments` | Produces the unique source-vertex to matrix assignment. | **Promote and deduplicate.** `boy_rig_gltf` also consumes it. |
| `src/jfg_re/boy_rig_gltf.py` | `_bone_records`, `build_rig_artifacts` | Creates the 21-node hierarchy, rigid joint data, two animations, and validates transformed vertices. | **Reference/exporter reuse.** Extract hierarchy and clip-building logic; keep glTF serialization isolated. |
| `src/jfg_re/boy_runtime_overrides.py` | `selector_parts`, `apply_additive_angle`, `movement_step`, report builder | Documents and emulates live player-specific override operations. | **Deferred from playback core.** Useful later for a runtime-state/debug layer; ordinary decoded clip playback does not have enough live racer state to apply every override. |
| `src/jfg_re/boy_runtime_capture.py` | `parse_selectors`, `apply_selectors`, `_runtime_matrices` | Imports captured runtime selectors and compares generated matrices. | **Research/debug extension only.** Do not make captures a v0.1 requirement. |
| `tools/export_boy_anim0_frame0.py`, `tools/export_boy_anim0_temporal.py`, `tools/validate_boy_animation_catalog.py`, `tools/export_boy_rig_validation.py` | CLI entry points | Existing end-to-end validation and exports. | **CLI only.** Preserve as regressions while the shared library is extracted. |

The existing code uses JFG row-vector matrices. OpenGL shader conventions
must be handled once in the renderer adapter, with explicit transpose/layout
tests; the decoding library should retain its proven JFG convention.

### glTF and attachments

| File/module | Important API | Existing capability | Reuse decision |
| --- | --- | --- | --- |
| `src/jfg_re/boy_rig_gltf.py` | `build_rig_artifacts`, `validate_gltf_binary_layout` | Validated glTF rig export for animations 0 and 43, with corner-expanded geometry and rigid weights. | **Keep as exporter and test oracle.** Forge must not generate/read glTF to display JFG assets. |
| `knowledge/verified/boy-gun-attachment.md` | verified data table | Records BoyGun object definition 399, slots 0–8/Props 301–309, matrix-6 socket, and confidence boundaries. | **Implemented.** Typed attachment metadata, loading, viewport placement, and model-bearing glTF export consume these constants. |

**SUPERSEDED planning note:** the typed, explicit and pinned BoyGun descriptor
now supplies the GUI and exporter. A future generic object-definition parser
may replace its storage without changing the renderer API.

## 4. Proposed package and module structure

Keep the established `jfg_re` package as the decoding authority and add the
application as a consumer:

```text
src/jfg_re/
  rom.py                  validated read-only RomImage and asset slices
  props.py                existing prop-bank primitives and extraction CLI API
  model.py                ModelAsset, Group, Triangle, Vertex, parser
  textures.py             TextureResolver, TextureAsset, sampler/tile metadata
  textures_rgba16.py      existing verified RGBA16 codec
  skeleton.py             Joint, Skeleton, reference points, rigid assignments
  animation.py            AnimationLibrary, AnimationClip, AnimationSample
  pose.py                 JFG matrix generation and rigid transforms
  attachments.py          AttachmentDefinition/Slot and pinned BoyGun data
  confidence.py           VERIFIED/LIKELY/HYPOTHESIS/UNKNOWN enum + provenance
  exporters/
    gltf.py               existing glTF-specific serialization after refactor

src/jfg_forge/
  __main__.py             desktop entry point
  application.py          QApplication lifetime, settings, error boundary
  session.py              loaded ROM/assets and current selection/playback state
  main_window.py          menus, docks, viewport, timeline wiring
  models/                 Qt item models for props, groups, joints, animations
  widgets/
    viewport.py           QOpenGLWidget and input routing
    timeline.py           transport, scrubber, loop, speed
    inspector.py          counts, status, group/triangle/material details
  render/
    renderer.py           passes and GPU resource lifetime
    camera.py             orbit/pan/zoom camera
    mesh.py               corner-expanded GPU mesh and material batches
    texture.py            RGBA upload and sampler state
    skeleton.py           joint/debug line pass
    shaders.py            minimal mesh and line shader sources
```

`jfg_re` must not import Qt, OpenGL, or `jfg_forge`. `jfg_forge` may import
public `jfg_re` APIs. Exporters consume the same neutral assets as Forge.

Core typed objects should be immutable where practical:

- `ModelAsset`: identity, source vertices, triangles, groups, textures,
  skeleton, reference points, and evidence metadata;
- `RenderMesh`: corner-expanded positions/UVs/joint IDs plus material batches;
- `AnimationClip`: numeric ID, sample count, loop flag, channel map, encoded
  data/descriptor representation;
- `AnimationSample`: root translation and per-channel angle/scale values;
- `Pose`: 21 JFG local/world matrices keyed by matrix ID;
- `AttachmentInstance`: slot metadata, model asset, socket matrix ID, optional
  verified child-local transform.

## 5. GUI framework

Use **PySide6**.

Reasons:

- mature Windows desktop widgets, docking panels, menus, file dialogs, timers,
  settings, and high-DPI support;
- `QOpenGLWidget` embeds a custom renderer without a game engine;
- Qt model/view classes suit future prop, texture, animation, audio, object,
  and scene browsers;
- the animation timer can schedule redraws while decoding remains ordinary
  Python library code;
- PySide6 has a clear path to a packaged standalone Windows application.

Avoid Tkinter because its native 3D integration is poor. Avoid a full game
engine because Forge needs inspection widgets, provenance, tables, and debug
views more than scene/gameplay systems. Avoid making Blender or glTF a runtime
dependency.

## 6. 3D rendering approach

Use `QOpenGLWidget` with a small modern OpenGL 3.3 renderer implemented through
**PyOpenGL**, with **NumPy** for contiguous buffers and matrix transfer.

The renderer needs two simple passes:

1. textured mesh pass;
2. colored line pass for skeleton and debug overlays.

For Boy, build corner-expanded render vertices exactly as the glTF exporter
already does. Each render vertex stores:

- raw model-space XYZ;
- one normalized UV pair where a VERIFIED RGBA16 texture exists;
- source vertex index for inspection;
- rigid matrix ID;
- group and source triangle identity, either as CPU metadata or integer vertex
  attributes;
- material batch including culling and sampler state.

Upload the 21 world matrices each frame as a uniform array. The vertex shader
selects one matrix by integer joint ID. This directly represents JFG's
one-joint-per-vertex assignment and avoids rebuilding vertex buffers while
scrubbing. Convert the established JFG row-vector layout to the shader's
column-vector convention at the upload boundary and test the result against
the existing CPU/glTF position oracle.

Render BoyGun as a separate mesh instance whose model transform is derived
from Boy matrix 6. The attachment mesh should not be merged into Boy. Changing
slots then changes only the attached GPU asset. Any still-unverified
model-local adjustment remains explicit metadata and must not be guessed.

RGBA8888 bytes returned by `decode_texture` can be uploaded directly. Forge and
exported glTF samplers explicitly use linear minification and magnification
filtering for smooth display. Map verified clamp/wrap/mirror fields to sampler
parameters. Keep unsupported tile behavior visible in the inspector.

Camera behavior:

- left drag: orbit around a model pivot;
- middle drag, or Shift+left drag: pan;
- wheel: exponential zoom/dolly;
- `F`: frame selected model or group;
- optional axis/grid overlays, disabled independently of skeleton lines.

## 7. Data flow

```text
US Z64 ROM or existing verified extracted cache
  -> RomImage identity and bounds validation
  -> PropBank / asset table access
  -> ModelParser + TextureResolver + AnimationLibrary
  -> ModelAsset / TextureAsset / Skeleton / AnimationClip
  -> AnimationSampler(time)
  -> PoseEvaluator (21 local/world matrices)
  -> AttachmentResolver (BoyGun slot, socket matrix 6)
  -> RenderMesh builder + GPU resource cache
  -> OpenGL mesh/skeleton passes
  -> PySide6 viewport and inspectors
```

UI selections modify a `ForgeSession`. The session publishes immutable
snapshots or narrow signals: selected animation, time, playback state,
attachment slot, visibility flags, and selected group/triangle/joint. Binary
parsing occurs when an asset is loaded, not during paint events. Per-frame work
is limited to animation sampling, matrix evaluation, uniform upload, and draw
submission.

## 8. Boy/Juno reference implementation plan

1. Validate the selected ROM with `validate_rom_identity`.
2. Read and decompress Prop 220 through a read-only PropBank API.
3. Call the pinned Boy wrapper and the generalized model parser; assert equal
   normalized output during migration.
4. Resolve the 18 Boy texture records. Decode the 14 verified RGBA16 assets;
   represent the other four with `UNKNOWN` diagnostic materials.
5. Build a corner-expanded `RenderMesh` for the 65 active groups and 502
   faces. Preserve per-corner S10.5 coordinates, culling bit `0x40`, group
   boundaries, source indices, and unclamped UV values.
6. Parse the 21 transform records and rigid source-vertex assignments.
7. Build an `AnimationLibrary` for Boy and expose only indices 0 and 43 in the
   first UI, labelled with IDs 1026 and 1069 and no invented names.
8. Sample the selected clip at the timeline time and evaluate the 21 matrices
   with the existing runtime-equivalent formula.
9. Load Props 301–309 with the same normalized model parser. Expose BoyGun
   slots using the verified table and parent the selected model to matrix 6.
10. Compare representative CPU-transformed vertices at the existing ten
    validation times against the current glTF/CPU oracle before accepting the
    shader path.

Raw clip playback in v0.1 does not claim to reproduce every live player
override. The UI should state `decoded animation` and separately show whether
runtime overrides are applied. Initially that field is `no / unavailable`.

## 9. Proposed UI layout

```text
+----------------------+--------------------------------+----------------------+
| Assets / model tree  |                                | Inspector            |
|                      |          3D viewport           | Model / Group        |
| Prop 220 Boy         |                                | Material / Joint     |
| BoyGun slots 0..8    |                                | Evidence / Status    |
+----------------------+--------------------------------+----------------------+
| Animation: [0 / 1026 v] [|<] [Play/Pause] [>|]  time slider  Loop  1.0x |
+-----------------------------------------------------------------------------+
| Status: ROM identity, loaded asset, warnings, unsupported formats            |
+-----------------------------------------------------------------------------+
```

Minimum inspector fields:

- Prop ID/name and source identity;
- 660 source vertices, 502 active faces, 82 groups, 18 texture records, and
  21 joints for Boy;
- selected group's ranges, texture status, tile state, and culling state;
- selected joint's parent, local translation, current matrix, and confidence;
- current attachment definition, slot, Prop, socket matrix 6, and provenance.

## 10. Incremental implementation milestones

### M0 — public data model and adapters

- introduce typed neutral model/skeleton/animation/texture objects;
- extract public APIs from private exporter helpers;
- retain old pinned functions as compatibility wrappers;
- add equivalence tests against existing Boy reports and glTF position checks.

### M1 — headless Boy scene builder

- read-only `RomImage` and `PropBank.get(220)`;
- construct Boy `ModelAsset`, verified textures, skeleton, animations 0/43,
  and render batches without Qt or OpenGL;
- expose deterministic counts and CPU pose evaluation.

### M2 — Forge shell and static viewport

- PySide6 application, main window, session, OpenGL widget, camera controls;
- render static animation-0/time-0 Boy mesh and textures;
- show model counts and diagnostic materials.

### M3 — skeleton and animation transport

- **Implemented:** skeleton line pass and technical joint inspector, including
  per-joint active-geometry indication;
- **Implemented:** all-52 technical animation browser, previous/next shortcuts,
  play/pause, scrubber, loop-domain display, speed, verified research context,
  and metadata-only reference clip;
- GPU rigid transform path checked against CPU reference positions.

### M3.5 — user-facing Boy export

- **Implemented:** model-only glTF with active mesh, verified textures,
  diagnostic UNKNOWN materials, 21-joint technical skin, and standalone
  binary/image sidecars;
- **Implemented:** selected technical animation as a 21-node hierarchy plus one
  action, and combined model/rig/current-action export for direct Blender use;
- **Implemented:** deterministic technical filenames, standard Qt save dialog,
  concise status/error feedback, and structural buffer/image validation;
- **Deferred:** one-file GLB packaging, all-52-actions export, attachment
  user-authored action names, and animation export options.

### M4 — BoyGun attachments

- **Implemented:** load slots 0–8 through the generic normalized Prop model
  path and switch cached models without reloading Boy or the ROM;
- **Implemented:** follow matrix 6 every sampled frame using the same scene
  pose as Boy and the skeleton;
- **Implemented:** show slot, Prop identity, face count, texture status,
  transform confidence, and the VERIFIED matrix-6 socket;
- **Implemented:** include the selected slot in model-bearing glTF exports as
  a rigid identity-local child of joint 6, preserving verified textures,
  per-corner UVs, diagnostic materials, and animation following by hierarchy;
- **Deferred:** any unsupported texture decoder.

### M5 — standalone v0.1 packaging and acceptance

- persistent settings and friendly ROM-selection/error flow;
- package Windows application and licenses;
- smoke-test clean launch, camera, both clips, all nine attachment slots, and
  shutdown/resource cleanup.

## 11. Dependencies

Current state:

- Python requirement: `>=3.12`;
- `pyproject.toml` declares `PySide6`, `PyOpenGL`, and `numpy`;
- current decoding modules use the standard library;
- tests use `unittest` and are discoverable through the existing pytest
  configuration, but pytest itself is not declared.

Current v0.1 runtime dependencies:

- `PySide6`: desktop UI, timers, settings, and `QOpenGLWidget`;
- `PyOpenGL`: explicit modern OpenGL calls inside the Qt-owned context;
- `numpy`: contiguous vertex/index/matrix buffers and predictable numeric
  transfer to OpenGL.

Proposed development/package dependency:

- `PyInstaller`, added only when M5 begins and kept in an optional packaging
  dependency group.

No image library is required for v0.1 because the verified decoder already
returns RGBA8888 and includes deterministic PNG support. Do not add a scene
engine, glTF runtime, Blender dependency, audio framework, or scientific stack
for this release.

## 12. Technical risks and unknowns

| Risk/unknown | Impact | Mitigation |
| --- | --- | --- |
| Existing model parser is pinned to Boy. | Props 301–309 cannot be loaded through the public parser as-is. | Generalize only confirmed header/record fields; keep per-asset identity wrappers and fixture equivalence tests. |
| Animation code exposes key operations as private dictionary-producing helpers. | UI code could become coupled to validation report schemas. | Introduce typed clips/samples and public services while retaining existing report functions as adapters. |
| JFG row-vector matrices differ from normal OpenGL presentation. | Transpose/order mistakes would corrupt animation and attachment placement. | One tested conversion boundary; compare GPU-equivalent positions with existing CPU reference results. |
| UVs require corner expansion. | Sharing source vertices would destroy seams. | Reuse the exact corner-expansion strategy already proven by the glTF exporter. |
| Four Boy texture formats remain UNKNOWN. | Some groups cannot be faithfully textured. | Diagnostic material plus visible status; do not infer decoders. |
| Runtime player override state is not available from a raw clip. | Playback may differ from a live gameplay pose. | Label playback as decoded clip; keep override/capture support out of the initial pose path. |
| Qt/OpenGL context lifetime and Windows driver differences. | Blank viewport or leaked resources on context recreation. | Create/delete GPU resources in `initializeGL`/context teardown; log GL vendor/version; require OpenGL 3.3 with a clear failure dialog. |
| Packaging PySide6 increases distribution size. | Larger standalone build. | Accept for v0.1 reliability; exclude unused Qt modules during the packaging milestone. |

## 13. Explicitly deferred features

- general browser for all 904 Props;
- unsupported CI, IA, I, RGBA32, TLUT, and other texture formats;
- runtime player override reconstruction and live emulator capture;
- animation blending and editing;
- bind-pose claims, weight painting, or non-rigid skinning;
- SceneRipper integration;
- general object-definition and child-graph browser;
- model/texture replacement or ROM writing;
- FBX, GLB and an all-52-actions export;
- audio browser/player;
- level, scene, AI, cutscene, collision, and object inspection;
- general research hex/disassembly views;
- plugin system, scripting console, and project/workspace management;
- macOS/Linux packaging for the first Windows-focused milestone.

## 14. Historical pre-GUI refactor plan — SUPERSEDED

The following list is retained as planning provenance. M0 through M4 have
implemented the Boy data layer, GUI, animation browser, export and attachments;
it is not a current prerequisite list.

In priority order:

1. **Model representation:** move `Vertex`, `Group`, `Triangle`, model parsing,
   group ranges, active-face iteration, rigid assignments, and corner-expanded
   render mesh construction out of `boy_export.py`, `boy_textured_export.py`,
   and `boy_rig_gltf.py` into public renderer-neutral APIs.
2. **Animation library:** expose animation table access, blob retrieval,
   structure parsing, and `decode_animation_time` through typed public APIs;
   eliminate GUI dependence on `_tables`, `_structure`, and `_packed`.
3. **Skeleton/pose:** separate 21-record hierarchy parsing from
   `build_matrices`; publish matrix generation and rigid transformation while
   preserving bit/float behavior.
4. **Textures/materials:** generalize `resolve_boy_textures`, `_tile_state`, and
   the dimension-aware UV formula. Keep `decode_texture` unchanged.
5. **ROM access:** add one validated read-only byte owner and bounds-checked
   asset/prop views to stop repeated full-ROM reads and LUT implementations.
6. **Attachments:** encode the verified BoyGun definition 399/slots 0–8/socket
   matrix 6 as typed data with provenance and confidence.
7. **Exporter adapters:** update existing OBJ/glTF/report builders to consume
   the public objects, proving that the refactor preserves previous outputs.

Refactoring should be incremental. Each old public workflow remains callable
until its output-equivalence test passes; only then should duplicate private
logic be removed.

## 15. Historical first implementation task — SUPERSEDED

Implement **M0's renderer-neutral Boy scene data layer**, without Qt or
OpenGL:

1. add typed `ModelAsset`, `Skeleton`, `AnimationClip`, `AnimationSample`,
   `Pose`, `RenderMesh`, and evidence-status records;
2. adapt `parse_boy`, `resolve_boy_textures`, `catalog_boy_animations`,
   `decode_animation_time`, `build_matrices`, rigid assignment, and the glTF
   corner-expansion algorithm behind public functions;
3. build one headless `BoyScene` at animation 0/time 0 and another at animation
   43/time 37.5;
4. verify exact counts, texture/status mapping, hierarchy, matrix IDs, UVs,
   culling batches, and representative transformed positions against the
   existing tests/artifacts;
5. keep every existing CLI/export API operational through adapters.

This is the smallest task that removes the current coupling to export scripts
and gives the future GUI one stable input. Starting with a window or renderer
before this layer would force binary/report logic into application code and
create a second implementation of already verified algorithms.
