"""The game's reverb, rebuilt from its own effect settings.

Jet Force Gemini runs the standard N64 audio library with a *custom* effect: the
ROM stores its settings (a delay length and six delay sections) right after the
audio directory, in the layout that libultra's ``alFxNew`` reads. Every song has
its reverb flag on, and each channel's controller 91 sets how much of its sound
goes to the effect instead of straight to the output (an equal-power cross-fade:
dry = cos, wet = sin).

The effect (libultra ``alFxPull``) works on one long delay line, block by block:

1. the left and right effect sends are summed (each times 0.707) and written
   into the delay line;
2. for each section, the block delayed by ``input`` samples and the block
   delayed by ``output`` samples are read; the output block gains
   ``ffcoef`` times the input block, the input block gains ``fbcoef`` times the
   output block (feedback), an optional one-pole low pass filters the output
   block, both are written back, and the output block is added to the reverb
   result times ``gain``.
3. the result goes to both channels.

Delays are in samples of the console's 22,050 Hz output. Forge renders at a
higher rate, so delays and the block size are scaled by the rate ratio and the
low-pass coefficient keeps its time constant. Chorus (a section's rate/depth) is
not modelled; the one chorus section in the ROM has no output gain and no effect.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

CONSOLE_RATE = 22050
CONSOLE_BLOCK = 736  # samples per audio frame: 2 * rate / 60 rounded up to 16
SCALE = 32768.0


@dataclass(frozen=True)
class ReverbSection:
    input: int
    output: int
    feedback: int
    feedforward: int
    gain: int
    chorus_rate: int
    chorus_depth: int
    low_pass: int


@dataclass(frozen=True)
class ReverbSettings:
    length: int
    sections: tuple[ReverbSection, ...]


def parse_reverb(blob: bytes) -> ReverbSettings | None:
    """Read a libultra custom-effect parameter block; ``None`` if it does not fit."""
    if len(blob) < 8:
        return None
    count, length = struct.unpack_from(">ii", blob, 0)
    needed = 8 + count * 32
    if not 0 < count <= 16 or length <= 0 or len(blob) < needed:
        return None
    sections = []
    for index in range(count):
        values = struct.unpack_from(">8i", blob, 8 + index * 32)
        sections.append(ReverbSection(*values))
    return ReverbSettings(length, tuple(sections))


def eqpower(index: int) -> float:
    """The library's equal-power table: 32767 * cos(index / 127 * pi / 2), as 0..1."""
    return 0.0 if index >= 127 else float(np.cos(index / 127.0 * np.pi / 2.0))  # the table ends in an exact zero


def send_levels(fxmix: int) -> tuple[float, float]:
    """(dry, wet) amounts for a channel's effect send of 0 to 127."""
    fxmix = min(max(int(fxmix), 0), 127)
    return eqpower(fxmix), eqpower(127 - fxmix)


def apply_reverb(
    send_left: np.ndarray,
    send_right: np.ndarray,
    settings: ReverbSettings,
    rate: int,
) -> np.ndarray:
    """Run the effect over the summed sends; returns the mono result (same length)."""
    ratio = rate / CONSOLE_RATE
    block = max(int(round(CONSOLE_BLOCK * ratio)), 16)
    sections = settings.sections
    delays = [(int(round(s.input * ratio)), int(round(s.output * ratio))) for s in sections]
    pad = max(max(a, b) for a, b in delays) + block + 16
    total = len(send_left)
    line = np.zeros(pad + total + block, dtype=np.float32)
    result = np.zeros(total + block, dtype=np.float32)
    mono = (0.7071 * (send_left + send_right)).astype(np.float32)
    mono = np.concatenate([mono, np.zeros(block, dtype=np.float32)])
    taps = 96  # the one-pole filter's response is below 1e-9 long before this
    lp_kernel = []
    for s in sections:
        a = (min(max(s.low_pass, 0), 32767) / SCALE) ** (1.0 / ratio) if s.low_pass else 0.0
        lp_kernel.append(((1.0 - a) * a ** np.arange(taps)).astype(np.float64))
    lp_history = [np.zeros(taps - 1, dtype=np.float64) for _ in sections]
    for start in range(0, total, block):
        here = pad + start
        line[here : here + block] = mono[start : start + block]
        out = np.zeros(block, dtype=np.float32)
        for index, section in enumerate(sections):
            d_in, d_out = delays[index]
            in_at, out_at = here - d_in, here - d_out
            buff1 = line[in_at : in_at + block].copy()
            buff2 = line[out_at : out_at + block].copy()
            rs = section.chorus_rate != 0
            lp = section.low_pass != 0
            if section.feedforward:
                buff2 += buff1 * (section.feedforward / SCALE)
                if not rs and not lp:
                    line[out_at : out_at + block] = buff2
            if section.feedback:
                buff1 += buff2 * (section.feedback / SCALE)
                line[in_at : in_at + block] = buff1
            if lp:
                joined = np.concatenate([lp_history[index], buff2.astype(np.float64)])
                lp_history[index] = joined[-(taps - 1) :]
                buff2 = np.convolve(joined, lp_kernel[index], mode="valid")[:block].astype(np.float32)
            if not rs:
                line[out_at : out_at + block] = buff2
            if section.gain:
                out += buff2 * (section.gain / SCALE)
        result[start : start + block] = out
    return result[:total]


__all__ = [
    "ReverbSection",
    "ReverbSettings",
    "apply_reverb",
    "eqpower",
    "parse_reverb",
    "send_levels",
]
