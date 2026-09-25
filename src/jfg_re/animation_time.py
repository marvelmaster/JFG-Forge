"""Canonical conversion from sample positions to JFG runtime interpolation state."""

from __future__ import annotations

from dataclasses import dataclass
import math

from jfg_re.boy_export import BoyExportError


@dataclass(frozen=True)
class RuntimeInterpolationState:
    current_sample: int
    next_sample: int
    fraction_10bit: int


def runtime_interpolation_state(
    time_value: float,
    *,
    sample_count: int,
    loop: bool,
) -> RuntimeInterpolationState:
    """Quantize one valid sample position to the runtime's discrete 10-bit state.

    Rounding a value immediately below an integer may produce 1024.  That value
    is represented canonically by carrying into the next sample and resetting
    the fraction to zero; 1024 is never passed to the animation decoder.
    """
    if sample_count <= 0:
        raise BoyExportError("Animation sample count must be positive.")
    maximum = float(sample_count if loop else sample_count - 1)
    valid = 0.0 <= time_value < maximum if loop else 0.0 <= time_value <= maximum
    if not math.isfinite(time_value) or not valid:
        domain = f"[0,{sample_count})" if loop else f"[0,{sample_count - 1}]"
        raise BoyExportError(f"Animation time {time_value} is outside {domain}.")

    current_sample = math.floor(time_value)
    fraction_10bit = int(round((time_value - current_sample) * 1024.0))
    if fraction_10bit == 1024:
        current_sample += 1
        fraction_10bit = 0
        if loop and current_sample == sample_count:
            current_sample = 0

    if not 0 <= fraction_10bit <= 1023:
        raise BoyExportError("Interpolation fraction is outside the runtime 10-bit domain.")
    if not 0 <= current_sample < sample_count:
        raise BoyExportError("Canonical interpolation sample is outside the animation.")

    if fraction_10bit == 0:
        next_sample = current_sample
    elif current_sample + 1 < sample_count:
        next_sample = current_sample + 1
    elif loop:
        next_sample = 0
    else:
        raise BoyExportError("Nonlooping endpoint cannot interpolate beyond its final sample.")

    return RuntimeInterpolationState(current_sample, next_sample, fraction_10bit)


__all__ = ["RuntimeInterpolationState", "runtime_interpolation_state"]
