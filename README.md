# JFG Forge

JFG Forge is a Windows desktop viewer and glTF exporter for the character models
of *Jet Force Gemini* (Nintendo 64, US release). You load your own ROM, pick a
character, watch its animations with the game's own timing, put a weapon in its
hand, and export the model or animation to glTF for Blender and other tools.

**No game ROM and no game assets are included.** You need your own legally
obtained US ROM. See [Legal](#legal).

## Quick start (Windows)

1. Install [Python 3.12 or newer](https://www.python.org/downloads/). On the
   first installer page, tick **Add python.exe to PATH**.
2. Get JFG Forge: on this GitHub page choose **Code, then Download ZIP**, and
   unpack it. (With git: `git clone https://github.com/marvelmaster/JFG-Forge`.)
3. Double-click **`start_forge.bat`**. The first start creates a private Python
   environment and downloads the three libraries JFG Forge needs, which takes a
   minute or two. Later starts open the window right away.
4. In the window choose **File, then Load ROM...** and select your ROM.

If something goes wrong, see [docs/troubleshooting.md](docs/troubleshooting.md).

Manual start, if you prefer a terminal:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m jfg_forge --rom C:\path\to\your\rom.z64
```

`--rom` is optional. Without it the window opens and asks for the ROM.

## Required ROM

| Property | Required value |
|---|---|
| Region | US |
| Format | Z64 (big-endian) |
| Size | 33,554,432 bytes |
| SHA-1 | `493ced9008dbe932d6e91179b68e8630cf23a023` |

The file name does not matter. JFG Forge checks the size, the byte order and
the full SHA-1 before it loads anything, and it only reads the file: your ROM is
never copied, changed or uploaded. V64/N64 (byte-swapped) files and other
revisions are rejected. The ROM path is not remembered between starts.

## What you can do

- **Pick a character** from the list at the top of the left panel.
- **Browse animations** with Previous/Next (or Ctrl+Left / Ctrl+Right), play and
  stop them, and scrub through the frames.
- **Choose the timing**: *Game Timing* plays each animation at the speed the
  game uses, *Technical* plays one sample per second. The Movement / Speed
  slider (1.0 to 5.0) stands in for how fast the character is moving.
- **Equip a weapon**: pick one of nine hand-and-weapon models under the
  character's attachment list.
- **Inspect the rig**: show the mesh, the skeleton, or both, and select a joint
  to see its position and which geometry it moves.
- **Export** through **File, Export**: the model, the current animation, or
  both, as glTF 2.0 with PNG and binary side files.

In the 3D view, drag with the left mouse button to orbit, drag with the middle
button to pan, and use the mouse wheel to zoom. The
[usage guide](docs/usage.md) walks through every control.

## Supported characters

| Character | Prop | Joints | Animations | Game Timing | Weapon set |
|---|---:|---:|---:|---|---|
| Juno | 220 | 21 | 52 | VERIFIED | BoyGun, 9 models, VERIFIED |
| PowerBoy | 221 | 21 | 52 | VERIFIED (same as Juno) | BoyGun, VERIFIED |
| Vela | 218 | 28 | 53 entries, 52 unique | VERIFIED | GirlGun, 9 models, VERIFIED |
| PowerGirl | 219 | 28 | 53 entries, 52 unique | VERIFIED (same as Vela) | GirlGun, VERIFIED |
| Lupus | 222 | 27 | 24 | VERIFIED | DogGun, 9 models, VERIFIED |
| PowerDog | 223 | 18 | 29 entries, 28 unique | VERIFIED | DogGun, VERIFIED |
| Green Ant (multiplayer) | 250 | 21 | 51 | LIKELY (Juno's table) | BoyGun, LIKELY |

**VERIFIED** means the value comes straight from ROM data and game code that was
checked. **LIKELY** means the evidence is strong but no runtime capture confirms
it. [docs/characters.md](docs/characters.md) explains both labels and the Green
Ant in detail.

## Project layout

```
jfg_forge/
  __main__.py       starts the application (python -m jfg_forge)
  core/             ROM validation, prop bank, model and texture decoding,
                    animation and timing data, scenes, glTF export
  gui/              the Qt/OpenGL window, playback, export menu
docs/               usage guide, characters, glTF export, technical notes,
                    troubleshooting
licenses/           third-party software notices
start_forge.bat     one-click launcher for Windows
requirements.txt    Python libraries (NumPy, PyOpenGL, PySide6)
```

## Limitations

- Only the seven characters above load. Other props in the ROM are not browsable
  yet.
- The texture decoder handles the formats these characters use (RGBA32,
  RGBA16, IA8 and one multi-image RGBA16 layout). Others are shown as unknown.
- Animation numbers are technical IDs. They have no gameplay names unless that
  was verified.
- The Movement / Speed slider is a preview input, not a live game value.
- glTF exports approximate the game's decal layering, and skinned vertex
  weights are not written (each vertex follows one joint, as in the game).
- The viewer needs an OpenGL 3.3 capable graphics driver.
- Tested on Windows 11. Other systems are untested.

## Legal

JFG Forge is an unofficial, non-commercial fan project. It is not affiliated
with or endorsed by Nintendo or Rare. *Jet Force Gemini* and its content belong
to their rights holders. This repository contains no ROM and no extracted game
data, and you must not add any.

The JFG Forge source code and documentation are licensed under the
[MIT License](LICENSE). Third-party libraries are listed in
[licenses/THIRD_PARTY.md](licenses/THIRD_PARTY.md).
