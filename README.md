# JFG RE and JFG Forge

JFG RE is a reproducible reverse engineering workspace for the US release of
*Jet Force Gemini*. JFG Forge is its current desktop viewer and exporter. The
first character milestone focuses on Boy/Juno (Prop 220), its rigid 21-joint
skeleton, 52 catalogued animations, verified RGBA16 textures, and the nine
BoyGun hand or weapon attachments.

This is an unofficial fan research project. It is not affiliated with or
endorsed by Nintendo or Rare. No game ROM or extracted game assets are intended
to be distributed in this repository.

## Current capabilities

- Validate and extract the US ROM prop bank: 904 raw-deflate Props from the
  verified table at ROM `0x139b800`.
- Parse Boy/Prop 220 into renderer-neutral geometry while preserving UV seams,
  material groups, triangle culling metadata, and rigid matrix assignments.
- Decode the 14 currently verified Boy RGBA16 textures. Four resolved Boy
  textures with other formats remain explicitly unsupported.
- Expose the verified 21-joint hierarchy and sample all 52 catalogued Boy
  animations with JFG's packed angles, Q10 root translation, interpolation,
  selector, matrix, and timing conventions.
- Display the animated mesh, skeleton overlay, technical animation browser,
  timing controls, and BoyGun slots 0 through 8 in JFG Forge.
- Export a model, the selected animation, or both as glTF 2.0. Model-bearing
  exports can include the selected BoyGun attachment and write their own PNG
  and binary sidecars.

The frozen first-character evidence baseline is
[`knowledge/verified/boy-juno-milestone-1.md`](knowledge/verified/boy-juno-milestone-1.md).
The next planned character milestone is Vela; Boy-specific rules will not be
generalized without new evidence.

## Required ROM

You must supply your own legally obtained US Z64 ROM. Tools open it read-only
and validate it before using it.

| Property | Required value |
| --- | --- |
| SHA-1 | `493ced9008dbe932d6e91179b68e8630cf23a023` |
| Size | `33,554,432 bytes` |
| Byte order | `Z64 / Big Endian` |

Pass the ROM with `--rom`. JFG Forge's convenience default is
`../rom/jetforcegemini.z64`, outside this project directory. ROM extensions and
local ROM directories are ignored by Git.

## Install

Python 3.12 or newer is required. From this directory on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The declared runtime dependencies are NumPy, PyOpenGL, and PySide6. The viewer
requests an OpenGL 3.3 core context.

## Prepare local inputs

Generated assets stay under `data/generated/` and are ignored by Git. The
verified prop extractor currently validates its result against the earlier
canonical index and Prop bins:

```powershell
python -B tools/extract_props.py `
  --rom C:\path\to\jetforcegemini.z64 `
  --output data\generated\props-us-verified `
  --reference-index C:\path\to\canonical\extracted\index.json `
  --reference-bins C:\path\to\canonical\extracted
```

The RGBA16 validation exporter likewise consumes the known TextureBins and
reference PNGs:

```powershell
python -B tools/export_rgba16_textures.py `
  --rom C:\path\to\jetforcegemini.z64 `
  --input-bins C:\path\to\canonical\TextureBins `
  --reference-pngs C:\path\to\canonical\TexturePNGs `
  --output data\generated\rgba16-us-verified
```

Both output directories must be absent before a run. These validation inputs
are local research artifacts and are intentionally not committed. A clean
ROM-only bootstrap for the texture offset corpus is a known missing workflow.

## Run JFG Forge

After preparing the Boy Prop and texture manifest:

```powershell
python -B tools/run_jfg_forge.py `
  --rom C:\path\to\jetforcegemini.z64 `
  --boy data\generated\props-us-verified\bins\0220_Boy.bin `
  --textures data\generated\rgba16-us-verified\textures-manifest.json
```

An editable install also provides the `jfg-forge` command with the same
arguments. Use Forge's Export menu for glTF output; choose an output directory
outside `data/generated/` if you want to retain it independently. Exported
assets remain ignored by default so they cannot be committed accidentally.

## Tests

The test suite uses Python's built-in `unittest` runner:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
```

Some integration and regression tests require the ignored local ROM, generated
assets, or runtime-capture fixtures. Focused pure tests can run without those
files; the relevant research documents identify fixture-dependent validations.

## Repository layout

- `src/jfg_re/`: verified decoders, typed assets, animation and scene logic.
- `src/jfg_forge/`: PySide6/OpenGL desktop application and glTF coordination.
- `tools/`: explicit command-line entry points.
- `tests/`: focused unit and regression tests.
- `knowledge/`: findings separated by evidence level.
- `research/`: analysis reports and reproducible research helpers.
- `data/manifests/`: small, distributable provenance manifests when available.
- `data/source/`: local raw inputs; only its policy README is committed.
- `data/generated/`: reproducible local outputs; only its policy README is
  committed.
- `references/`: attribution and notes about external projects.

## Known limits

- The model and attachment APIs remain pinned to Boy/Juno and its BoyGun table;
  this is not yet a general JFG character loader.
- Four Boy texture formats remain unknown and use diagnostic materials.
- Animation IDs stay technical unless a gameplay context was independently
  verified. Viewer movement values are controlled research inputs, not claimed
  live gameplay values.
- Several model header fields, vertex attributes, and other ROM asset types are
  still unknown.
- The texture pipeline currently needs the local canonical TextureBins and PNG
  references described above.

## License

The repository's original source code and documentation are licensed under the
[MIT License](LICENSE).

*Jet Force Gemini* and its original game content are not relicensed by this
repository. The game ROM is not included.
