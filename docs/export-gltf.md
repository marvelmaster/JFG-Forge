# Exporting to glTF

JFG Forge writes glTF 2.0, which Blender, Godot, Unity and many viewers can open.
Use **File, Export** in the viewer.

## The three exports

| Menu entry | Contents | Default file name |
|---|---|---|
| Export Model... | Mesh, skeleton, textures, and the selected weapon | `Juno_Prop220.gltf` |
| Export Current Animation... | The skeleton animation only, no mesh | `Juno_anim_05_ID1039.gltf` |
| Export Model + Current Animation... | Everything in one file | `Juno_Prop220_anim_05_ID1039.gltf` |

The file name starts with the character name. `anim_05_ID1039` means animation
index 5 with the game's animation ID 1039. Your exported file must end in
`.gltf`.

An animation-only export cannot contain a weapon, because it has no mesh.

## Files that are written

Next to the `.gltf` file Forge writes:

- a `.bin` file with the geometry and animation data, and
- one `.png` file per texture (model exports only).

Keep these files together. The `.gltf` refers to them by name. The output folder
must already exist; Forge does not create it.

## What is in the file

- **Skeleton:** one node per game joint, named `jfg_node_NN` where NN is the
  joint number. Every vertex follows exactly one joint, the way the game draws
  it, so there are no blend weights.
- **Weapon:** the selected weapon model is a child of the character's socket
  joint, with an identity local transform. Its evidence level (VERIFIED or
  LIKELY) is written into the file's `extras`.
- **Materials:** the game's texture state is carried over where it is known,
  including transparency and clamped or repeated texture edges. Decal layers
  are separated by small offsets, which is an approximation of the game's
  drawing order.
- **Animation timing:** keys are stored in seconds. The time is the sample
  position divided by the playback rate that the viewer shows for the current
  Timing mode and Movement / Speed setting, so an export looks like the
  preview. Set these before you export.

## Opening in Blender

1. **File, Import, glTF 2.0 (.glb/.gltf)** and choose the exported file.
2. The skeleton appears as an armature. Blender converts glTF's Y-up axes to
   Z-up on import.
3. For an animation-only export, import it into a scene that already has the
   model, or use the combined export.

Blender's interpolation can differ slightly from the game's between samples;
the exported keys are the game's own samples.
