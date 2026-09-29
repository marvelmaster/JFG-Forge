# The Models tab

The **Models** tab is a catalogue of every model in the ROM. It is meant for
looking at the game's static objects (keys, doors, platforms, pickups, weapons,
scenery pieces) with their textures, next to the animated characters of the
Characters tab.

## What it lists

The ROM stores 904 model Props. Each Prop begins with a short name, so the list
shows the game's own names (`yellowkey`, `paneOfGlass`, `Cluster`, `BPistol` and
so on) and the Prop number in brackets. The names are internal labels, and some
are cryptic.

| Filter | Shows | Count |
|---|---|---:|
| Static models (default) | Props without animations that have geometry | 604 |
| Animated props (rest pose) | Props with animations | 284 |
| All props | Everything, including empty helper models | 904 |

Use **Sort by** to order the list by Prop number or by name. The search box
matches part of a name or an exact Prop number, and it works with every filter.

## Looking at a model

Select a row to load it. The 3D view uses the same camera as the Characters tab:
drag with the left mouse button to orbit, drag with the middle button to pan, and
use the wheel to zoom. The camera frames each new model automatically. The panel
under the list shows:

- **Name** and **Prop** number,
- **Type**: Static, Static with joints, or Animated,
- **Faces**, **Vertices** (as stored and as drawn) and **Groups**,
- **Joints** and **Animations**,
- **Textures**: how many of the model's textures Forge decoded.

The status bar repeats the name, number, face count and type.

## Rest pose

Most static models have no joints and are drawn exactly as stored. Some models,
mainly animated props such as doors, switches and pistons, are built from joints
that the game moves with animations. The Models tab draws those with every joint
at its stored offset from its parent and no rotation, and marks them "shown in
rest pose". That is an approximation: an animated prop can look assembled
differently here than in the game. Four props have joints but no animations
(`piston1`, `dino3`, `TeleBeam`, `TeleBeam1`) and are listed as static.

The animated characters also appear in the Animated list; use the Characters tab
to see them with their animations and weapons.

## Empty models

A number of Props hold no drawable geometry (hit boxes and other helper models).
They are hidden from the two main filters and appear under **All props** with the
tag `[no geometry]`. Selecting one shows a short message instead of a picture.
A couple more only turn out to be empty when opened; they disappear from the
lists afterwards.

## Textures

Forge decodes all seven texture formats the game uses (RGBA32, RGBA16, I8, I4, IA16,
IA8 and IA4), including textures with mipmaps or several frames. Every texture
that a drawable prop actually shows decodes. A texture that ever fails to decode
is drawn grey and the **Textures** line says how many were not decoded. Textures
with several frames show their first frame, and textures on the separate mipmapped
tile path are drawn with default wrapping. See [textures.md](textures.md).

## Limits

- The Models tab is a viewer. **File, Export** works for the Characters tab only.
- Models are shown one at a time and without lighting from the game or its level
  context, so colours and scale are as stored, not as seen in a level.
- Animated props have no playback here.
