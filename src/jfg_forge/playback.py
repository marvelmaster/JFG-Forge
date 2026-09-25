"""Qt-free viewer playback state for catalogued JFG animation clips."""

from __future__ import annotations

import math
from collections.abc import Iterable

from jfg_re.forge_types import AnimationClip
from jfg_forge.runtime_timing import (
    PlaybackTimingContext,
    PlaybackTimingMode,
    RuntimeClipTiming,
    TECHNICAL_SAMPLES_PER_SECOND,
    runtime_timing,
)


SLIDER_STEPS_PER_SAMPLE = 1000
VIEWER_SAMPLES_PER_SECOND = TECHNICAL_SAMPLES_PER_SECOND
MIN_MOVEMENT_SPEED = 1.0
MAX_MOVEMENT_SPEED = 5.0
MOVEMENT_SPEED_TICKS_PER_UNIT = 10
MIN_MOVEMENT_SPEED_TICK = 10
MAX_MOVEMENT_SPEED_TICK = 50
SUPPORTED_SPEEDS = tuple(value / MOVEMENT_SPEED_TICKS_PER_UNIT for value in range(10, 51))


def animation_label(clip: AnimationClip) -> str:
    loop_text = "loop" if clip.loop else "non-loop"
    return (
        f"Index {clip.animation_index} — ID {clip.animation_id} — "
        f"{clip.sample_count} samples — {loop_text}"
    )


def movement_speed_label(speed: float) -> str:
    if speed not in SUPPORTED_SPEEDS:
        raise ValueError(f"Unsupported Movement / Speed value {speed!r}.")
    return f"{speed:.1f}"


def movement_speed_from_slider(value: int) -> float:
    if not MIN_MOVEMENT_SPEED_TICK <= value <= MAX_MOVEMENT_SPEED_TICK:
        raise ValueError(f"Movement / Speed slider tick {value!r} is outside 10..50.")
    return value / MOVEMENT_SPEED_TICKS_PER_UNIT


def slider_from_movement_speed(value: float) -> int:
    if value not in SUPPORTED_SPEEDS:
        raise ValueError(f"Unsupported Movement / Speed value {value!r}.")
    return round(value * MOVEMENT_SPEED_TICKS_PER_UNIT)


class PlaybackController:
    """Own viewer-only time progression without changing decoder semantics."""

    def __init__(self, clips: Iterable[AnimationClip], *, initial_index: int = 0) -> None:
        self.clips = tuple(clips)
        self._by_index = {clip.animation_index: clip for clip in self.clips}
        if not self.clips or len(self._by_index) != len(self.clips):
            raise ValueError("Playback requires one or more uniquely indexed clips.")
        self.animation_index = initial_index
        if initial_index not in self._by_index:
            raise KeyError(f"Animation index {initial_index} is unavailable.")
        self.time = 0.0
        self.movement_speed = 1.0
        self.timing_mode = PlaybackTimingMode.GAME
        self.state_timing_flag = False
        self.playing = False
        self.reference_index: int | None = None

    @property
    def clip(self) -> AnimationClip:
        return self._by_index[self.animation_index]

    @property
    def end_time(self) -> float:
        """Technical domain end; exclusive for loop clips, inclusive otherwise."""
        return float(self.clip.sample_count if self.clip.loop else self.clip.sample_count - 1)

    @property
    def slider_maximum(self) -> int:
        if self.clip.loop:
            return self.clip.sample_count * SLIDER_STEPS_PER_SAMPLE - 1
        return (self.clip.sample_count - 1) * SLIDER_STEPS_PER_SAMPLE

    def select(self, animation_index: int) -> None:
        if animation_index not in self._by_index:
            raise KeyError(f"Animation index {animation_index} is unavailable.")
        self.animation_index = animation_index
        self.time = 0.0

    def adjacent_index(self, offset: int) -> int:
        """Return an adjacent catalogue index, wrapping at both boundaries."""
        ordered = tuple(clip.animation_index for clip in self.clips)
        position = ordered.index(self.animation_index)
        return ordered[(position + int(offset)) % len(ordered)]

    def select_previous(self) -> None:
        self.select(self.adjacent_index(-1))

    def select_next(self) -> None:
        self.select(self.adjacent_index(1))

    def mark_reference(self) -> None:
        self.reference_index = self.animation_index

    @property
    def reference_clip(self) -> AnimationClip | None:
        if self.reference_index is None:
            return None
        return self._by_index[self.reference_index]

    def set_movement_speed(self, value: float) -> None:
        if value not in SUPPORTED_SPEEDS:
            raise ValueError(f"Unsupported Movement / Speed value {value!r}.")
        self.movement_speed = float(value)

    def set_timing_mode(self, mode: PlaybackTimingMode) -> None:
        self.timing_mode = PlaybackTimingMode(mode)

    def set_state_timing_flag(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("State timing flag must be boolean.")
        self.state_timing_flag = enabled

    @property
    def game_timing(self) -> RuntimeClipTiming:
        return runtime_timing(self.clip)

    @property
    def uses_technical_fallback(self) -> bool:
        return self.timing_mode is PlaybackTimingMode.GAME and not self.game_timing.available

    @property
    def base_samples_per_second(self) -> float:
        if self.timing_mode is PlaybackTimingMode.TECHNICAL:
            return TECHNICAL_SAMPLES_PER_SECOND
        rate = self.game_timing.samples_per_second(
            self.clip,
            movement_metric=1.0,
            state_timing_flag=self.state_timing_flag,
        )
        return TECHNICAL_SAMPLES_PER_SECOND if rate is None else rate

    @property
    def timing_context(self) -> PlaybackTimingContext:
        return PlaybackTimingContext(
            timing_mode=self.timing_mode,
            movement_speed=self.movement_speed,
            state_timing_flag=self.state_timing_flag,
        )

    @property
    def effective_samples_per_second(self) -> float:
        return self.timing_context.effective_samples_per_second(self.clip)

    def set_time(self, time_value: float) -> None:
        if not math.isfinite(time_value):
            raise ValueError("Playback time must be finite.")
        selectable_end = self.slider_maximum / SLIDER_STEPS_PER_SAMPLE
        self.time = min(max(float(time_value), 0.0), selectable_end)

    def time_from_slider(self, value: int) -> float:
        value = min(max(int(value), 0), self.slider_maximum)
        return value / SLIDER_STEPS_PER_SAMPLE

    def slider_from_time(self) -> int:
        value = round(self.time * SLIDER_STEPS_PER_SAMPLE)
        return min(max(value, 0), self.slider_maximum)

    def play(self) -> None:
        if not self.clip.loop and self.time >= self.end_time:
            self.time = 0.0
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def stop(self) -> None:
        self.playing = False
        self.time = 0.0

    def advance(self, elapsed_seconds: float) -> None:
        if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0.0:
            raise ValueError("Elapsed playback time must be finite and non-negative.")
        if not self.playing or elapsed_seconds == 0.0:
            return
        next_time = self.time + elapsed_seconds * self.effective_samples_per_second
        if self.clip.loop:
            self.time = next_time % self.clip.sample_count
            return
        if next_time >= self.end_time:
            self.time = self.end_time
            self.playing = False
        else:
            self.time = next_time


__all__ = [
    "PlaybackController",
    "PlaybackTimingMode",
    "MAX_MOVEMENT_SPEED",
    "MIN_MOVEMENT_SPEED",
    "MAX_MOVEMENT_SPEED_TICK",
    "MIN_MOVEMENT_SPEED_TICK",
    "MOVEMENT_SPEED_TICKS_PER_UNIT",
    "SLIDER_STEPS_PER_SAMPLE",
    "SUPPORTED_SPEEDS",
    "VIEWER_SAMPLES_PER_SECOND",
    "animation_label",
    "movement_speed_from_slider",
    "movement_speed_label",
    "slider_from_movement_speed",
]
