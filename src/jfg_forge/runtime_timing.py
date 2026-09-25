"""Runtime-derived playback timing for verified Boy and Vela player states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from types import MappingProxyType
from typing import Mapping

from jfg_re.forge_types import AnimationClip, EvidenceStatus


NOMINAL_NTSC_VI_HZ = 60.0
TECHNICAL_SAMPLES_PER_SECOND = 1.0
MAX_RUNTIME_DELAY_DAT = 6


class PlaybackTimingMode(StrEnum):
    TECHNICAL = "Technical"
    GAME = "Game Timing"


class TimingDependency(StrEnum):
    FIXED = "fixed"
    MOVEMENT_MAX = "max(abs(racer+0x04), abs(racer+0x10))"
    MOVEMENT_LATERAL = "abs(racer+0x10)"
    OBJECT_ABS_CLAMPED = "max(1.0, abs(object+0x20))"
    COMBINED_MAX = "max(movement_max, abs(object+0x20))"
    STATE_FLAG_DOUBLE = "2x when the state timing flag has bit 0x10 set"
    UNKNOWN = "UNKNOWN"


class TimingCategory(StrEnum):
    FIXED = "FIXED"
    MOVEMENT_DEPENDENT = "MOVEMENT_DEPENDENT"
    STATE_DEPENDENT = "STATE_DEPENDENT"
    OTHER_RUNTIME_DEPENDENT = "OTHER_RUNTIME_DEPENDENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PlaybackTimingContext:
    """One shared preview/export interpretation of the visible speed control."""

    timing_mode: PlaybackTimingMode = PlaybackTimingMode.GAME
    movement_speed: float = 1.0
    state_timing_flag: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.movement_speed) or self.movement_speed <= 0.0:
            raise ValueError("Movement / Speed must be finite and positive.")
        if not isinstance(self.state_timing_flag, bool):
            raise ValueError("State timing flag must be boolean.")

    def effective_samples_per_second(self, clip: AnimationClip) -> float:
        """Return the exact rate consumed by both Forge playback and glTF export."""
        if self.timing_mode is PlaybackTimingMode.TECHNICAL:
            return TECHNICAL_SAMPLES_PER_SECOND * self.movement_speed
        timing = runtime_timing(clip)
        rate = timing.samples_per_second(
            clip,
            movement_metric=self.movement_speed if timing.requires_movement_metric else 1.0,
            state_timing_flag=self.state_timing_flag,
        )
        if rate is None:
            return TECHNICAL_SAMPLES_PER_SECOND * self.movement_speed
        # Movement-dependent formulas already consumed the slider exactly once.
        return rate if timing.requires_movement_metric else rate * self.movement_speed


@dataclass(frozen=True)
class RuntimeClipTiming:
    animation_index: int
    animation_id: int
    status: EvidenceStatus
    base_phase_per_vi_tick: float | None
    category: TimingCategory
    dependency: TimingDependency
    evidence: str

    @property
    def available(self) -> bool:
        return self.status is EvidenceStatus.VERIFIED and self.base_phase_per_vi_tick is not None

    @property
    def requires_movement_metric(self) -> bool:
        return self.dependency in (
            TimingDependency.MOVEMENT_MAX,
            TimingDependency.MOVEMENT_LATERAL,
            TimingDependency.OBJECT_ABS_CLAMPED,
            TimingDependency.COMBINED_MAX,
        )

    @property
    def requires_state_timing_flag(self) -> bool:
        return self.dependency is TimingDependency.STATE_FLAG_DOUBLE

    def _validate_clip(self, clip: AnimationClip) -> None:
        if (clip.animation_index, clip.animation_id) != (self.animation_index, self.animation_id):
            raise ValueError("Runtime timing metadata does not match the selected animation clip.")

    def clip_span(self, clip: AnimationClip) -> float:
        """Return the phase-to-sample multiplier used by modGenAnimMatrices."""
        self._validate_clip(clip)
        return float(clip.sample_count if clip.loop else clip.sample_count - 1)

    def phase_delta(
        self,
        *,
        delay_dat: int,
        movement_metric: float = 1.0,
        state_timing_flag: bool = False,
    ) -> float | None:
        """Return objAnimDframe's normalized phase change for one update."""
        if not self.available:
            return None
        if (
            not isinstance(delay_dat, int)
            or delay_dat < 1
            or delay_dat > MAX_RUNTIME_DELAY_DAT
        ):
            raise ValueError("delayDat must be the post-clamp integer VI count in 1..6.")
        if not math.isfinite(movement_metric) or movement_metric < 0.0:
            raise ValueError("Movement metric must be finite and non-negative.")
        if not isinstance(state_timing_flag, bool):
            raise ValueError("State timing flag must be boolean.")
        dependency_scale = movement_metric if self.requires_movement_metric else 1.0
        if self.requires_state_timing_flag and state_timing_flag:
            dependency_scale *= 2.0
        return float(delay_dat) * float(self.base_phase_per_vi_tick) * dependency_scale

    def sample_delta(
        self,
        clip: AnimationClip,
        *,
        delay_dat: int,
        movement_metric: float = 1.0,
        state_timing_flag: bool = False,
    ) -> float | None:
        phase_delta = self.phase_delta(
            delay_dat=delay_dat,
            movement_metric=movement_metric,
            state_timing_flag=state_timing_flag,
        )
        return None if phase_delta is None else self.clip_span(clip) * phase_delta

    def samples_per_second(
        self,
        clip: AnimationClip,
        *,
        movement_metric: float = 1.0,
        state_timing_flag: bool = False,
        vi_hz: float = NOMINAL_NTSC_VI_HZ,
    ) -> float | None:
        if not math.isfinite(vi_hz) or vi_hz <= 0.0:
            raise ValueError("VI rate must be finite and positive.")
        per_tick = self.sample_delta(
            clip,
            delay_dat=1,
            movement_metric=movement_metric,
            state_timing_flag=state_timing_flag,
        )
        return None if per_tick is None else per_tick * vi_hz


def _verified(
    animation_index: int,
    animation_id: int,
    base_scale: float,
    category: TimingCategory,
    dependency: TimingDependency,
    evidence: str,
) -> RuntimeClipTiming:
    return RuntimeClipTiming(
        animation_index=animation_index,
        animation_id=animation_id,
        status=EvidenceStatus.VERIFIED,
        base_phase_per_vi_tick=base_scale,
        category=category,
        dependency=dependency,
        evidence=evidence,
    )


_BOY_ANIMATION_IDS = (
    1026, 1027, 1028, 1025, 1033, 1039, 1040, 1041, 1038, 1042, 1043, 1031,
    1036, 1029, 1030, 1044, 1019, 1020, 1021, 1022, 1023, 1051, 1035, 1070,
    1048, 1050, 1054, 1053, 1055, 1056, 1057, 1058, 1059, 1060, 1063, 1062,
    1061, 1066, 1067, 1068, 1045, 1046, 1047, 1069, 1034, 1024, 1052, 1064,
    1065, 1032, 1037, 1071,
)

_BOY_BASE_PHASE_PER_VI_TICK = (
    0.015, 0.009, 0.0075, 0.014, 0.0175, 0.01, 0.02, 0.0175, 0.0334,
    0.0115, 0.0115, 0.0175, 0.028, 0.02, 0.005, 0.025, 0.005, 0.005,
    0.005, 0.005, 0.005, 0.017, 0.005, 0.01, 0.01, 0.0334, 0.014, 0.005,
    0.015, 0.009, 0.0075, 0.0115, 0.0115, 0.06, 0.0075, 0.009, 0.015,
    0.006, 0.004, 0.01, 0.014, 0.025, 0.02, 0.003, 0.0175, 0.005, 0.017,
    0.0115, 0.0115, 0.0175, 0.028, 0.01,
)

_BOY_MOVEMENT_MAX_INDICES = frozenset((0, 1, 2, 3, 4, 26, 28, 29, 30, 34, 35, 36, 37, 44))
_BOY_MOVEMENT_LATERAL_INDICES = frozenset((9, 10, 31, 32, 47, 48))
_BOY_STATE_FLAG_DOUBLE_INDICES = frozenset((13,))

_CASE_ADDRESS = {
    0: "0x010051D8", 1: "0x010052FC", 2: "0x01005388", 3: "0x010053F4",
    4: "0x01005504", 5: "0x01005530", 6: "0x01005B50", 7: "0x01005B50",
    8: "0x0100556C", 9: "0x0100559C", 10: "0x0100559C", 11: "0x010056D4",
    12: "0x0100571C", 13: "0x010057AC", 14: "0x010057F8", 15: "0x01005820",
    16: "0x0100584C", 17: "0x0100584C", 18: "0x0100584C", 19: "0x0100584C",
    20: "0x0100584C", 21: "0x01005948", 22: "0x010059A0", 23: "0x01005B50",
    24: "0x01005B50", 25: "0x01005B50", 26: "0x010053F4", 27: "0x0100584C",
    28: "0x010051D8", 29: "0x010052FC", 30: "0x01005388", 31: "0x0100559C",
    32: "0x0100559C", 33: "0x010057F8", 34: "0x01005388", 35: "0x010052FC",
    36: "0x010051D8", 37: "0x01005A04", 38: "0x010059C8", 39: "0x01005B18",
    40: "0x01005B50", 41: "0x01005AB0", 42: "0x01005AE4", 43: "0x01005A44",
    44: "0x01005504", 45: "0x0100584C", 46: "0x01005948", 47: "0x0100559C",
    48: "0x0100559C", 49: "0x010056F8", 50: "0x01005764", 51: "default -> 0x01005B50",
}


def _boy_timing_kind(index: int) -> tuple[TimingCategory, TimingDependency]:
    if index in _BOY_MOVEMENT_MAX_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.MOVEMENT_MAX
    if index in _BOY_MOVEMENT_LATERAL_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.MOVEMENT_LATERAL
    if index in _BOY_STATE_FLAG_DOUBLE_INDICES:
        return TimingCategory.STATE_DEPENDENT, TimingDependency.STATE_FLAG_DOUBLE
    return TimingCategory.FIXED, TimingDependency.FIXED


VERIFIED_BOY_TIMINGS: Mapping[int, RuntimeClipTiming] = MappingProxyType(
    {
        index: _verified(
            index,
            animation_id,
            base_scale,
            *_boy_timing_kind(index),
            evidence=(
                f"Overlay16 jump-table case {_CASE_ADDRESS[index]}; "
                "common objAnimDframe call 0x01005B54..0x01005B60"
            ),
        )
        for index, (animation_id, base_scale) in enumerate(
            zip(_BOY_ANIMATION_IDS, _BOY_BASE_PHASE_PER_VI_TICK, strict=True)
        )
    }
)


_VELA_ANIMATION_IDS = (
    1097, 1098, 1099, 1096, 1104, 1110, 1111, 1112, 1109, 1113, 1114,
    1102, 1107, 1100, 1101, 1115, 1090, 1091, 1092, 1093, 1094, 1095,
    1121, 1106, 1141, 1119, 1120, 1124, 1123, 1125, 1126, 1127, 1128,
    1129, 1130, 1116, 1117, 1118, 1131, 1132, 1133, 1124, 1134, 1135,
    1137, 1136, 1138, 1139, 1140, 1122, 1103, 1108, 1142,
)

_VELA_BASE_PHASE_PER_VI_TICK = (
    0.014, 0.011, 0.008, 0.014, 0.014, 0.012, 0.02, 0.015, 0.0334,
    0.0115, 0.0115, 0.02, 0.028, 0.02, 0.005, 0.025, 0.005, 0.0075,
    0.005, 0.005, 0.005, 0.005, 0.0175, 0.005, 0.01, 0.01, 0.0334,
    0.014, 0.005, 0.014, 0.011, 0.0085, 0.0115, 0.0115, 0.005, 0.014,
    0.035, 0.02, 0.014, 0.011, 0.0085, 0.014, 0.0115, 0.0115, 0.006,
    0.006, 0.01, 0.01, 0.003, 0.02, 0.02, 0.028, 0.006,
)

_VELA_MOVEMENT_MAX_INDICES = frozenset((0, 1, 2, 3, 4, 27, 29, 30, 31, 38, 39, 40, 41))
_VELA_MOVEMENT_LATERAL_INDICES = frozenset((9, 10, 32, 33, 42, 43))
_VELA_OBJECT_ABS_CLAMPED_INDICES = frozenset((44, 52))
_VELA_COMBINED_MAX_INDICES = frozenset((45,))
_VELA_STATE_FLAG_DOUBLE_INDICES = frozenset((13,))

_VELA_CASE_ADDRESS = {
    0: "0x00F05400", 1: "0x00F054FC", 2: "0x00F05580", 3: "0x00F055E4",
    4: "0x00F056D0", 5: "0x00F05700", 6: "0x00F05E70", 7: "0x00F05E70",
    8: "0x00F0573C", 9: "0x00F05770", 10: "0x00F05770", 11: "0x00F05878",
    12: "0x00F058C8", 13: "0x00F05948", 14: "0x00F05994", 15: "0x00F059C0",
    16: "0x00F059E8", 17: "0x00F059E8", 18: "0x00F059E8", 19: "0x00F059E8",
    20: "0x00F059E8", 21: "0x00F059E8", 22: "0x00F05ADC", 23: "0x00F05B3C",
    24: "0x00F05E70", 25: "0x00F05E70", 26: "0x00F05E70", 27: "0x00F055E4",
    28: "0x00F059E8", 29: "0x00F05400", 30: "0x00F054FC", 31: "0x00F05580",
    32: "0x00F05770", 33: "0x00F05770", 34: "0x00F05994", 35: "0x00F05E70",
    36: "0x00F05D54", 37: "0x00F05D8C", 38: "0x00F05400", 39: "0x00F054FC",
    40: "0x00F05580", 41: "0x00F055E4", 42: "0x00F05770", 43: "0x00F05770",
    44: "0x00F05B68", 45: "0x00F05CB8", 46: "0x00F05E70", 47: "0x00F05DC4",
    48: "0x00F05E04", 49: "0x00F05ADC", 50: "0x00F058A0", 51: "0x00F05908",
    52: "0x00F05C10",
}


def _vela_timing_kind(index: int) -> tuple[TimingCategory, TimingDependency]:
    if index in _VELA_MOVEMENT_MAX_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.MOVEMENT_MAX
    if index in _VELA_MOVEMENT_LATERAL_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.MOVEMENT_LATERAL
    if index in _VELA_OBJECT_ABS_CLAMPED_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.OBJECT_ABS_CLAMPED
    if index in _VELA_COMBINED_MAX_INDICES:
        return TimingCategory.MOVEMENT_DEPENDENT, TimingDependency.COMBINED_MAX
    if index in _VELA_STATE_FLAG_DOUBLE_INDICES:
        return TimingCategory.STATE_DEPENDENT, TimingDependency.STATE_FLAG_DOUBLE
    return TimingCategory.FIXED, TimingDependency.FIXED


VERIFIED_VELA_TIMINGS: Mapping[int, RuntimeClipTiming] = MappingProxyType(
    {
        index: _verified(
            index,
            animation_id,
            base_scale,
            *_vela_timing_kind(index),
            evidence=(
                f"Girl overlay 15 jump-table case {_VELA_CASE_ADDRESS[index]}; "
                "common objAnimDframe call 0x00F05E74..0x00F05E80"
            ),
        )
        for index, (animation_id, base_scale) in enumerate(
            zip(_VELA_ANIMATION_IDS, _VELA_BASE_PHASE_PER_VI_TICK, strict=True)
        )
    }
)


def runtime_timing(clip: AnimationClip) -> RuntimeClipTiming:
    if "vela_animation_index" in clip.metadata:
        known = VERIFIED_VELA_TIMINGS.get(clip.animation_index)
    elif "boy_animation_index" in clip.metadata:
        known = VERIFIED_BOY_TIMINGS.get(clip.animation_index)
    else:
        known = None
    if known is not None:
        known._validate_clip(clip)
        return known
    return RuntimeClipTiming(
        animation_index=clip.animation_index,
        animation_id=clip.animation_id,
        status=EvidenceStatus.UNKNOWN,
        base_phase_per_vi_tick=None,
        category=TimingCategory.UNKNOWN,
        dependency=TimingDependency.UNKNOWN,
        evidence="The selected character state case has not been timing-audited.",
    )


def vi_ticks_to_seconds(
    delay_dat: int,
    *,
    vi_hz: float = NOMINAL_NTSC_VI_HZ,
) -> float:
    if (
        not isinstance(delay_dat, int)
        or delay_dat < 1
        or delay_dat > MAX_RUNTIME_DELAY_DAT
    ):
        raise ValueError("delayDat must be the post-clamp integer VI count in 1..6.")
    if not math.isfinite(vi_hz) or vi_hz <= 0.0:
        raise ValueError("VI rate must be finite and positive.")
    return delay_dat / vi_hz


__all__ = [
    "NOMINAL_NTSC_VI_HZ",
    "MAX_RUNTIME_DELAY_DAT",
    "PlaybackTimingMode",
    "PlaybackTimingContext",
    "RuntimeClipTiming",
    "TECHNICAL_SAMPLES_PER_SECOND",
    "TimingDependency",
    "TimingCategory",
    "VERIFIED_BOY_TIMINGS",
    "VERIFIED_VELA_TIMINGS",
    "runtime_timing",
    "vi_ticks_to_seconds",
]
