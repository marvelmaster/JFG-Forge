# The Audio tab

The **Audio** tab plays the game's music and sound effects and exports them as
WAV or MP3. It has two segments, **Music** and **Sounds**, that share one player,
so only one clip plays at a time. Opening either segment stops the other.

## Music

The ROM holds 90 songs. Ten are empty placeholders without a single note; they
are hidden, which leaves **80 songs**. Each row shows the song number, its length
and its number of notes. Select a song to see its tempo, how many instruments it
uses and its rendered length.

- **Play** renders the song (one to two seconds for a full song) and plays it.
  The window stays usable while it renders.
- Songs play **once through**. Most game songs end in an endless loop; Forge plays
  the intro and one pass of the loop, then stops.
- The position bar and time show the progress. Playing another song, pressing
  **Stop** or leaving the tab ends playback.

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

## Volume and position

The volume slider sets the loudness of this program's output only; it does not
change exported files. The Music position bar is display only.

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
tempo, instruments, key ranges, pitch, loops, envelopes, channel volume and
panning, using the game's own instrument samples. It leaves out reverb, chorus,
the sustain pedal and pitch bends that change during a note, and it mixes with its
own simple rules. Expect the right notes, rhythm and instruments, with a drier and
less polished sound than on the console.

There are no known names for songs or sounds, so entries are numbered.

## Playback problems

If nothing plays, check that Windows has a default audio output device selected.
The status line under the buttons says when no device is found. Exporting works
without a device. See [troubleshooting](troubleshooting.md).
