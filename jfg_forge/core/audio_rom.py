"""Audio data in the ROM: banks, samples, sound-effect index and music sequences.

All audio lives in one ROM asset (52) described by a small directory (asset 51).
Both the music and the sound-effect banks use the standard N64 libultra
``ALBankFile`` layout with VADPCM-compressed samples:

===============  ==============================================================
section          content
===============  ==============================================================
``[0, w0)``      music bank control data (instruments and their key maps)
``[w0, w1)``     music samples
``[w1, w2)``     sound-effect bank control data
``[w2, w3)``     sound-effect samples
``[w3, w4)``     sequence file: 90 compressed MIDI sequences
``[w4, w5)``     sequence index, 3 bytes per song (volume, tempo, reverb)
``[w5, w6)``     sound-effect index, 10 bytes per sound
===============  ==============================================================

``w0..w6`` are the first seven words of the directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np

from jfg_forge.core.model_parser import BoyExportError, _asset_lut, _asset_range
from jfg_forge.core.rom_source import RomSource, as_rom_source

DIRECTORY_ASSET = 51
AUDIO_ASSET = 52
DEFAULT_OUTPUT_RATE = 32000


@dataclass(frozen=True)
class Envelope:
    attack_us: int
    decay_us: int
    release_us: int
    attack_volume: int
    decay_volume: int


@dataclass(frozen=True)
class KeyMap:
    velocity_min: int
    velocity_max: int
    key_min: int
    key_max: int
    key_base: int
    detune_cents: int


@dataclass(frozen=True)
class AdpcmLoop:
    start: int
    end: int
    count: int
    state: tuple[int, ...]


@dataclass(frozen=True)
class WaveTable:
    base: int
    length: int
    type: int
    flags: int
    order: int
    predictors: int
    book: tuple[int, ...]
    loop: AdpcmLoop | None


@dataclass(frozen=True)
class Sound:
    envelope: Envelope
    key_map: KeyMap
    wave: WaveTable
    pan: int
    volume: int


@dataclass(frozen=True)
class Instrument:
    volume: int
    pan: int
    priority: int
    bend_range: int
    sounds: tuple[Sound, ...]


@dataclass(frozen=True)
class SoundBank:
    sample_rate: int
    instruments: tuple[Instrument, ...]
    samples: bytes = b""

    @property
    def sound_count(self) -> int:
        return sum(len(instrument.sounds) for instrument in self.instruments)


@dataclass(frozen=True)
class SoundEffect:
    """One entry of the sound-effect index (game sound ID)."""

    sound_id: int
    bite: int  # index of the sample-bank sound this effect plays
    volume: int  # 0..255, 128 is full scale in the game's tables
    min_volume: int
    pitch: int  # 100 = original pitch
    range: int
    priority: int


@dataclass(frozen=True)
class Song:
    song_id: int
    volume: int
    tempo: int
    reverb: int
    data: bytes


@dataclass(frozen=True)
class AudioRom:
    music_bank: SoundBank
    sfx_bank: SoundBank
    effects: tuple[SoundEffect, ...]
    songs: tuple[Song, ...]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _s32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">i", data, offset)[0]


def _s16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]


def _parse_wave(ctl: bytes, offset: int) -> WaveTable:
    base, length = _s32(ctl, offset), _s32(ctl, offset + 4)
    wave_type, flags = ctl[offset + 8], ctl[offset + 9]
    if wave_type != 0:
        raise BoyExportError(f"Unsupported wave table type {wave_type}; only ADPCM is used.")
    loop_offset, book_offset = _u32(ctl, offset + 12), _u32(ctl, offset + 16)
    order, predictors = _s32(ctl, book_offset), _s32(ctl, book_offset + 4)
    book_count = order * predictors * 8
    book = struct.unpack_from(f">{book_count}h", ctl, book_offset + 8)
    loop = None
    if loop_offset:
        start, end, count = struct.unpack_from(">III", ctl, loop_offset)
        state = struct.unpack_from(">16h", ctl, loop_offset + 12)
        loop = AdpcmLoop(start, end, count, tuple(state))
    return WaveTable(base, length, wave_type, flags, order, predictors, tuple(book), loop)


def _parse_bank(ctl: bytes, samples: bytes) -> SoundBank:
    revision, bank_count = struct.unpack_from(">HH", ctl, 0)
    if revision != 0x4231 or bank_count != 1:
        raise BoyExportError("Audio bank does not start with a single-bank 'B1' header.")
    bank = _u32(ctl, 4)
    instrument_count = _s16(ctl, bank)
    sample_rate = _s32(ctl, bank + 4)
    instruments = []
    for index in range(instrument_count):
        instrument_offset = _u32(ctl, bank + 12 + 4 * index)
        if instrument_offset == 0:
            instruments.append(Instrument(0, 0, 0, 0, ()))
            continue
        sound_count = _s16(ctl, instrument_offset + 14)
        sounds = []
        for slot in range(sound_count):
            sound_offset = _u32(ctl, instrument_offset + 16 + 4 * slot)
            envelope_offset, key_offset, wave_offset = struct.unpack_from(">III", ctl, sound_offset)
            attack, decay, release = struct.unpack_from(">iii", ctl, envelope_offset)
            envelope = Envelope(attack, decay, release, ctl[envelope_offset + 12], ctl[envelope_offset + 13])
            key = struct.unpack_from(">BBBBBb", ctl, key_offset)
            sounds.append(
                Sound(
                    envelope,
                    KeyMap(*key),
                    _parse_wave(ctl, wave_offset),
                    ctl[sound_offset + 12],
                    ctl[sound_offset + 13],
                )
            )
        instruments.append(
            Instrument(
                ctl[instrument_offset],
                ctl[instrument_offset + 1],
                ctl[instrument_offset + 2],
                _s16(ctl, instrument_offset + 12),
                tuple(sounds),
            )
        )
    return SoundBank(sample_rate, tuple(instruments), samples)


def load_audio(rom_path: RomSource | Path) -> AudioRom:
    """Read the banks, sound-effect index and songs from the ROM."""
    source = as_rom_source(rom_path)
    rom = source.data
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, DIRECTORY_ASSET)
    words = struct.unpack_from(">7I", rom[start:end], 0)
    w0, w1, w2, w3, w4, w5, w6 = words
    start, end = _asset_range(lut, AUDIO_ASSET)
    audio = rom[start:end]
    if not (0 < w0 < w1 < w2 < w3 < w4 < w5 < w6 <= len(audio)):
        raise BoyExportError("Audio directory offsets are not increasing or exceed the audio asset.")
    music = _parse_bank(audio[:w0], audio[w0:w1])
    sfx = _parse_bank(audio[w1:w2], audio[w2:w3])

    index = audio[w5:w6]
    effects = tuple(
        SoundEffect(i, *struct.unpack_from(">HBBBxHBx", index, i * 10))
        for i in range(len(index) // 10)
    )

    seq_file = audio[w3:w4]
    revision, seq_count = struct.unpack_from(">HH", seq_file, 0)
    if revision != 0x5331:
        raise BoyExportError("Sequence file does not start with an 'S1' header.")
    seq_index = audio[w4:w5]
    songs = []
    for song_id in range(seq_count):
        offset, length = struct.unpack_from(">Ii", seq_file, 4 + song_id * 8)
        volume, tempo, reverb = (
            struct.unpack_from(">BBB", seq_index, song_id * 3)
            if song_id * 3 + 3 <= len(seq_index)
            else (127, 0, 0)
        )
        songs.append(Song(song_id, volume, tempo, reverb, bytes(seq_file[offset : offset + length])))
    return AudioRom(music, sfx, effects, tuple(songs))


# --------------------------------------------------------------------------
# VADPCM decoding
# --------------------------------------------------------------------------


def decode_adpcm(samples: bytes, wave: WaveTable) -> np.ndarray:
    """Decode one VADPCM wave table to signed 16-bit samples.

    Each 9-byte frame holds a header (scale in the high nibble, predictor in the
    low nibble) and 16 four-bit residuals.  Every block of eight output samples
    is predicted from the previous two output samples and the residuals before
    it, using the wave table's coefficient book.  The result reproduces the loop
    states stored in the ROM exactly.
    """
    frame_count = wave.length // 9
    data = np.frombuffer(samples, dtype=np.uint8, count=frame_count * 9, offset=wave.base)
    frames = data.reshape(frame_count, 9)
    order = wave.order
    book = np.asarray(wave.book, dtype=np.int64).reshape(wave.predictors, order, 8)
    # For each predictor: rows for the two previous samples, and the 8x8 lower-triangular
    # matrix that spreads earlier residuals of the same block onto later samples.
    previous = []
    spread = []
    for predictor in range(wave.predictors):
        rows = book[predictor]
        if order >= 2:
            previous.append((rows[0], rows[1]))
        else:
            previous.append((np.zeros(8, dtype=np.int64), rows[0]))
        matrix = np.zeros((8, 8), dtype=np.int64)
        for i in range(8):
            for j in range(i):
                matrix[i, j] = rows[order - 1][i - 1 - j]
        spread.append(matrix)
    headers = frames[:, 0].astype(np.int64)
    scales = headers >> 4
    predictors = np.where((headers & 0x0F) < wave.predictors, headers & 0x0F, 0)
    nibbles = np.empty((frame_count, 16), dtype=np.int64)
    nibbles[:, 0::2] = frames[:, 1:] >> 4
    nibbles[:, 1::2] = frames[:, 1:] & 0x0F
    nibbles = np.where(nibbles >= 8, nibbles - 16, nibbles) << scales[:, None]
    out = np.empty(frame_count * 16, dtype=np.int64)
    last1 = last2 = 0
    position = 0
    for frame in range(frame_count):
        predictor = predictors[frame]
        row2, row1 = previous[predictor]
        matrix = spread[predictor]
        for half in range(2):
            residual = nibbles[frame, half * 8 : half * 8 + 8]
            accumulator = (residual << 11) + row2 * last2 + row1 * last1 + matrix @ residual
            block = np.clip(accumulator >> 11, -32768, 32767)
            out[position : position + 8] = block
            position += 8
            last2, last1 = int(block[6]), int(block[7])
    return out.astype(np.int16)


__all__ = [
    "AUDIO_ASSET",
    "AdpcmLoop",
    "AudioRom",
    "DEFAULT_OUTPUT_RATE",
    "DIRECTORY_ASSET",
    "Envelope",
    "Instrument",
    "KeyMap",
    "Song",
    "Sound",
    "SoundBank",
    "SoundEffect",
    "WaveTable",
    "decode_adpcm",
    "load_audio",
]
