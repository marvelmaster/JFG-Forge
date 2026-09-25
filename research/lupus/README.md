# Lupus discovery pass

This directory contains the first reproducible reverse-engineering pass for
Lupus in the US Jet Force Gemini ROM. It establishes the canonical player
model, static model map, transform hierarchy, animation catalog, shared
runtime path, and weapon child. It deliberately does not integrate Lupus into
JFG Forge and does not classify the complete gameplay timing catalog.

## Results

- **VERIFIED:** object definition 2 `playerDog` selects Prop 222 `Dog` and
  child object definition 401 `DogGun`.
- **VERIFIED:** object definition 5 `playerDogPower` selects Prop 223
  `PowerDog` and the same `DogGun` child.
- **VERIFIED:** Prop 222 contains 490 vertices, 382 triangle records, 65
  groups, nine vertex-reference records, and 27 transform records.
- **VERIFIED:** the generic `0x400` group exclusion admits 44 groups and 361
  nondegenerate faces.
- **VERIFIED:** all admitted source vertices have one consistent rigid matrix
  assignment.
- **VERIFIED:** 12 of 15 model textures match the existing RGBA16 pipeline.
  Two unsupported textures are used by admitted geometry; one is used only by
  excluded groups.
- **VERIFIED:** the Lupus animation table contains 24 entries and 24 unique
  IDs (`582..605`), with 15 looping and nine non-looping entries.
- **VERIFIED:** all 24 animation entries parse completely with the established
  packed format and contain six runtime scale scalar streams.
- **VERIFIED:** `dogControl` calls the shared `modGenAnimMatrices` path and then
  `objMakeGunMtx`. DogGun is attached through Prop 222 reference record 0 to
  Lupus matrix 16 with no additional child-local transform.
- **PENDING:** a complete Lupus Game Timing catalog and an independent live
  capture of all 27 runtime matrices.

## Files

- [`discovery-runtime.md`](discovery-runtime.md) explains the evidence and
  confidence boundaries.
- [`structural-map.json`](structural-map.json) contains the static model,
  texture, hierarchy, object, attachment, and runtime-call evidence.
- [`animation-map.json`](animation-map.json) contains all 24 animation records
  and the deterministic technical reference pose.
- [`analyze_lupus.py`](analyze_lupus.py) regenerates both JSON files from the
  pinned US ROM and existing canonical extraction artifacts.

## Reproduction

From the `jfg-re/` directory:

```powershell
python -B research/lupus/analyze_lupus.py `
  --rom ../rom/jetforcegemini.z64 `
  --prop data/generated/props-us-verified/bins/0222_Dog.bin `
  --textures data/generated/rgba16-us-verified/textures-manifest.json `
  --prop-index ../extracted/index.json `
  --structural-output research/lupus/structural-map.json `
  --animation-output research/lupus/animation-map.json
```

The helper reads legacy/reference inputs and writes only the two named Lupus
research outputs.
