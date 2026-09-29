# Troubleshooting

## `start_forge.bat` says Python was not found

Install Python 3.12 or newer from <https://www.python.org/downloads/> and tick
**Add python.exe to PATH** on the first installer page. Then double-click
`start_forge.bat` again. If a `.venv` folder was left over from a failed start,
delete it first.

## "JFG Forge needs Python 3.12 or newer"

The `.venv` folder was made with an older Python. Delete the `.venv` folder,
install Python 3.12 or newer, and start again.

## Installing the requirements fails

The first start downloads NumPy, PyOpenGL and PySide6 from the internet. Check
your connection, a proxy or firewall, then delete the `.venv` folder and start
again. The download is a few hundred megabytes, mostly PySide6.

## "Unsupported ROM"

JFG Forge only accepts the US release in Z64 (big-endian) format, exactly
33,554,432 bytes, with SHA-1 `493ced9008dbe932d6e91179b68e8630cf23a023`.

- A ROM that starts with the bytes `37 80 40 12` is byte-swapped (V64/N64
  format). Convert it to Z64 with a ROM tool.
- A different region, a trimmed or patched ROM, or a hacked version has another
  hash and is rejected.

You can check the hash in PowerShell:

```powershell
Get-FileHash -Algorithm SHA1 C:\path\to\rom.z64
```

## "The supported ROM was recognized, but Forge could not load its character data"

Send the message text along with the ROM's SHA-1 when you report the problem
on GitHub.

## Renderer error / black 3D view

The viewer needs an OpenGL 3.3 core profile. Update your graphics driver. On
remote desktop sessions and in virtual machines OpenGL is often unavailable;
run JFG Forge on the PC itself.

## Audio tab: nothing plays

The player uses the default Windows audio output. Check that a device is selected
and not muted, and that the volume slider under the buttons is not at zero. If no
device is found, the status line says so; you can still export.

## Audio tab: "MP3 export unavailable"

MP3 export needs the `lameenc` package. Delete the `.venv` folder and start again
with `start_forge.bat` to install everything, or install it by hand from the
JFG Forge folder:

```powershell
.venv\Scripts\python.exe -m pip install lameenc
```

WAV export works without it.

## Exported glTF looks wrong in another program

- Keep the `.gltf`, `.bin` and `.png` files in the same folder.
- Check the Timing mode and Movement / Speed before exporting; they set the
  animation speed.
- Some viewers ignore per-material transparency settings. Try Blender.

## Where to ask

Open an issue at <https://github.com/marvelmaster/JFG-Forge/issues> with your
Windows version, the Python version (`python --version`) and the full error
message. Do not attach the ROM.
