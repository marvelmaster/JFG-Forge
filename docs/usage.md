# Usage guide

This page walks through the JFG Forge window from top to bottom. For
installation see the [README](../README.md).

## 1. Load your ROM

Start JFG Forge with `start_forge.bat`. If you did not pass `--rom`, a small
welcome window opens.

1. Choose **File, then Load ROM...**
2. Select your US ROM (`.z64`). The file dialog shows `.z64` files by default;
   pick **All files** to see other names.
3. Forge checks the size, byte order and SHA-1 (see the README for the exact
   values). If the file is not the supported ROM you get an error and nothing
   is loaded.
4. On success the main window opens and the status bar shows
   `ROM: Jet Force Gemini (USA)`.

You can load another ROM at any time with the same menu entry. The path is not
saved, so you choose the ROM again on each start (or pass `--rom` on the
command line).

## 2. The left panel

### Asset / Model Info

The drop-down at the top selects the model. It is split into three groups
(Campaign, Multiplayer characters, Hover ships); the group names are headings,
not choices. A model is decoded from the ROM the first time you pick it, so the
status bar briefly shows "Loading ...". If a model cannot be loaded, Forge shows
the reason and keeps the previous one. Below the drop-down Forge lists what it
decoded from the ROM: model name, Prop number, vertex and face counts, groups,
joints, how many textures decoded (VERIFIED) and how many did not (UNKNOWN),
and the attachment status.

### Animation Browser

| Control | What it does |
|---|---|
| Animation list | Pick one animation of the selected character. |
| Previous / Next | Step through the list. Ctrl+Left and Ctrl+Right do the same and wrap around. |
| Play / Stop | Start or stop playback. Looping animations repeat; others stop at the last frame. |
| Time slider | Scrub to any point in the animation. |
| Movement / Speed | 1.0 to 5.0 in steps of 0.1. Explained under timing below. |
| Timing mode | *Game Timing* or *Technical*. |
| State timing flag | Only used by the one animation whose speed doubles when a game flag is set. |
| Timing status | Says which evidence level the current timing has, and the exact rate. |

The technical section under the browser shows the animation index and ID, its
sample count, whether it loops, and the root motion values for the current
frame. **Mark Current as Reference** stores the selected animation so you can
compare it with another one.

### Timing modes

- **Game Timing** plays every animation at the speed the game code uses. Some
  animations always run at one speed. Others scale with how fast the character
  moves; for those, the Movement / Speed slider is the movement input (1.0 is
  full input). For fixed-speed animations the slider simply multiplies the
  playback speed.
- **Technical** plays one animation sample per second (times the slider). Use
  it to study individual frames.

If an animation has no known game timing, Forge says so in the status text and
falls back to Technical timing.

### Attachment

The attachment list holds nine hand-and-weapon models for the character. Hover
ships carry no weapon, so for them the list is greyed out and the panel says so.
The nine models are:
pistol, automatic, uzi, second uzi, shrink beam, rocket, flamethrower, sniper,
and a ninth slot (a hand for Juno and Vela, a grenade model for Lupus).
**None** shows the character without an attachment. The weapon is placed on the
joint named under *Socket*, and the *Transform* line shows the evidence level of
that placement. Selected weapons are included in model exports.

### Viewport Debug

- **View**: Mesh, Skeleton, or Mesh + Skeleton.
- **Joint**: pick a joint by number to highlight it. The panel shows its ID,
  parent, position for the current frame, its resting offset, and how many
  vertices it moves.

## 3. The 3D view

| Input | Action |
|---|---|
| Left mouse button, drag | Orbit around the model |
| Middle mouse button, drag | Pan |
| Mouse wheel | Zoom |

The viewer needs OpenGL 3.3. If it cannot start, Forge shows a renderer error
(see [troubleshooting](troubleshooting.md)).

## 4. Export

Open **File, then Export** and choose one of three entries:

| Entry | Writes |
|---|---|
| Export Model... | The mesh, skeleton and textures, with the selected weapon if any |
| Export Current Animation... | Only the selected animation for the skeleton |
| Export Model + Current Animation... | Both in one file |

Choose a `.gltf` file name and folder. Forge writes the `.gltf`, a `.bin` file
and PNG textures next to it, so keep them together. Details are in
[export-gltf.md](export-gltf.md).
