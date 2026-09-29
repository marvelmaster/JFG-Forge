# The Audio tab

The **Audio** tab plays the game's music and sound effects and exports them as
WAV or MP3. It has two segments, **Music** and **Sounds**, that share one player,
so only one clip plays at a time. Opening either segment stops the other.

## Music

The ROM holds 90 songs. Ten are empty placeholders without a single note; they
are hidden, which leaves **80 songs**. Each row shows the song number, its length
and its number of notes. Select a song to see its tempo, how many instruments it
uses and its rendered length.

- **Play** renders the song (a few seconds for a full song) and plays it.
  The window stays usable while it renders.
- Songs play **once through**. Most game songs end in an endless loop; Forge plays
  the intro and one pass of the loop, then stops.
- The position bar and time show the progress. Playing another song, pressing
  **Stop** or leaving the tab ends playback.

- **Instruments.** The music bank holds 159 instruments in two banks of programs. A
  song picks the second bank (instruments 128 to 158) with controller 32 (bank
  select) before a program change; 54 of the 90 songs use it for some of their
  parts, for a third of all notes. Forge applies bank select, so those parts play
  the intended instruments instead of the first bank's instruments with the same
  program number (which sounded like a generic MIDI arrangement).

## Sounds

The game's sound table has 640 entries. Three point past the end of the sample
bank and cannot play, which leaves **637 sound effects**. Search for a number in
the search box, or tick **Only looping sounds** to see the 65 effects that loop
(engines, alarms, hums).

- **Play when selected** (on by default here) plays each effect as soon as you
  select it, so you can step through the list with the arrow keys. Double-click or
  press **Play** to hear it again.
- Effects play with the pitch and volume that the game's table gives them.
- A looping effect repeats for three seconds.

## Names

The ROM stores no names for its audio, so Forge takes them from other sources and
marks how sure it is. You can search the lists by name, and exported files carry
the name (for example `Song_04_Goldwood.wav`).

**Songs.** Songs 1 to 67 use the community song list from the kiosk demo (The
Cutting Room Floor), for example Goldwood, Mizar's Palace, Tawfret and Sekhmet.
This list was checked against the final ROM (VERIFIED): each level records the
song it plays, and every level agrees with the list (the Forest levels play
Goldwood, the swamp plays Tawfret, the military base plays Ichor, the mines play
Mines). The short jingles are short, and Landing and Spawnship each appear twice
with identical notes. Songs with no listed name are called `Music of <level>`
after the first level that plays them (LIKELY); a few have no known name or user.
Names such as `Sound-effect sequence 14` are the list's "SFX" entries, which are
ambience and effect sequences rather than tunes. Details shows the levels that
play the selected song.

**Sounds.** No source names sound effects, so Forge labels them by who plays
them. Every place in the game code that plays a sound with a fixed number was
found, and the sound is labelled after the calling code (`Health pickup`,
`Flamethrower fire`, `Terminal`, `Menu select`). This covers 78 of the 640 sounds
and says who plays the sound, not what it sounds like (LIKELY). The other sounds
are triggered through game data and keep their number only.

## Volume and position

The volume slider sets the loudness of this program's output only; it does not
change exported files. The position bar is a scrubber: click it or drag it to jump to any point while a clip plays, or
while it is stopped to start playing from that point.

## Export

**Export WAV...** and **Export MP3...** save the selected entry.

| | Music | Sounds |
|---|---|---|
| Channels | stereo | mono |
| Sample rate | 32000 Hz | 44100 Hz |
| WAV | 16-bit PCM | 16-bit PCM |
| MP3 | 192 kbit/s | 192 kbit/s |

Songs are scaled so their loudest point is comfortable and never clips. Sound
effects keep the game's own levels.

File names start with the entry, for example `Song_05.wav` or `Sound_101.mp3`. MP3
export uses the `lameenc` package, which `start_forge.bat` installs. If it is
missing, Forge tells you and WAV export still works.

The audio comes from the game and belongs to its rights holders. Keep exports for
your own use.

## How close to the game is it?

**Sound effects** use the game's own samples, decoded exactly (Forge checks this
against the loop information stored in the ROM), so they should sound like the
game.

**Songs** are rendered by Forge, not by the console. It follows each song's notes,
tempo, instruments (including the second bank, see above), key ranges, pitch,
loops, envelopes, channel volume and panning, using the game's own instrument
samples, and it applies the game's own reverb: the effect settings are stored in
the ROM (six delay sections over a 6,400-sample delay line) and each channel's
effect send (controller 91) splits its sound between the direct output and the
reverb, as the console's audio library does. It leaves out chorus, the sustain
pedal and pitch bends that change during a note, and the console's fixed-point
rounding, so expect the right notes, rhythm, instruments and room sound, but not a
bit-exact copy of the console.

The reverb is modelled at the console's 22,050 Hz rate and scaled to Forge's
32,000 Hz output. The effect settings, the equal-power send curve and the delay
section algorithm are the ones used by the audio library shared with the
*Diddy Kong Racing* decompilation; the ROM's audio bank ranges also match those in
the N64 sound bank tool's configuration for this game.

Song names come from a community list and sound labels from the game code; see Names above.

## Playback problems

If nothing plays, check that Windows has a default audio output device selected.
The status line under the buttons says when no device is found. Exporting works
without a device. See [troubleshooting](troubleshooting.md).
