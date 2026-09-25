from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_forge.playback import (
    MAX_MOVEMENT_SPEED,
    MAX_MOVEMENT_SPEED_TICK,
    MIN_MOVEMENT_SPEED,
    MIN_MOVEMENT_SPEED_TICK,
    PlaybackController,
    PlaybackTimingMode,
    SUPPORTED_SPEEDS,
    movement_speed_from_slider,
    movement_speed_label,
    slider_from_movement_speed,
)
from jfg_forge.runtime_timing import (
    NOMINAL_NTSC_VI_HZ,
    PlaybackTimingContext,
    TimingCategory,
    TimingDependency,
    VERIFIED_BOY_TIMINGS,
    runtime_timing,
    vi_ticks_to_seconds,
)
from jfg_re.forge_data import load_boy
from jfg_re.forge_types import EvidenceStatus


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class RuntimeTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def test_catalog_has_all_52_explicit_verified_entries(self) -> None:
        self.assertEqual(set(VERIFIED_BOY_TIMINGS), set(range(52)))
        self.assertEqual(len(VERIFIED_BOY_TIMINGS), 52)
        for index, timing in VERIFIED_BOY_TIMINGS.items():
            clip = self.boy.animation(index)
            self.assertIs(timing.status, EvidenceStatus.VERIFIED)
            self.assertTrue(timing.available)
            self.assertEqual(timing.animation_id, clip.animation_id)
        outside_catalog = replace(self.boy.animation(2), animation_index=99)
        self.assertIs(runtime_timing(outside_catalog).status, EvidenceStatus.UNKNOWN)

    def test_original_ten_timings_remain_unchanged(self) -> None:
        expected = {
            0: (0.015, TimingDependency.MOVEMENT_MAX),
            1: (0.009, TimingDependency.MOVEMENT_MAX),
            3: (0.014, TimingDependency.MOVEMENT_MAX),
            9: (0.0115, TimingDependency.MOVEMENT_LATERAL),
            10: (0.0115, TimingDependency.MOVEMENT_LATERAL),
            16: (0.005, TimingDependency.FIXED),
            17: (0.005, TimingDependency.FIXED),
            18: (0.005, TimingDependency.FIXED),
            19: (0.005, TimingDependency.FIXED),
            43: (0.003, TimingDependency.FIXED),
        }
        self.assertEqual(
            {
                index: (timing.base_phase_per_vi_tick, timing.dependency)
                for index, timing in VERIFIED_BOY_TIMINGS.items()
                if index in expected
            },
            expected,
        )

    def test_delay_dat_and_movement_dependent_index0_formula(self) -> None:
        clip = self.boy.animation(0)
        timing = runtime_timing(clip)
        self.assertIs(timing.dependency, TimingDependency.MOVEMENT_MAX)
        self.assertAlmostEqual(timing.phase_delta(delay_dat=1, movement_metric=1.0), 0.015)
        self.assertAlmostEqual(timing.sample_delta(clip, delay_dat=1, movement_metric=1.0), 0.24)
        self.assertAlmostEqual(timing.sample_delta(clip, delay_dat=3, movement_metric=1.0), 0.72)
        self.assertAlmostEqual(vi_ticks_to_seconds(1), 1.0 / 60.0)
        self.assertAlmostEqual(vi_ticks_to_seconds(6), 0.1)
        with self.assertRaises(ValueError):
            timing.phase_delta(delay_dat=7, movement_metric=1.0)
        self.assertAlmostEqual(
            timing.samples_per_second(clip, movement_metric=1.0),
            14.4,
        )
        self.assertAlmostEqual(
            timing.samples_per_second(clip, movement_metric=0.5),
            7.2,
        )

    def test_fixed_index43_runtime_rate_uses_nonloop_span(self) -> None:
        clip = self.boy.animation(43)
        timing = runtime_timing(clip)
        self.assertFalse(clip.loop)
        self.assertEqual(clip.sample_count, 76)
        self.assertEqual(timing.clip_span(clip), 75.0)
        self.assertAlmostEqual(timing.sample_delta(clip, delay_dat=1), 0.225)
        self.assertAlmostEqual(timing.samples_per_second(clip), 13.5)
        self.assertEqual(NOMINAL_NTSC_VI_HZ, 60.0)

    def test_new_shared_movement_and_fixed_formulas(self) -> None:
        maximum = runtime_timing(self.boy.animation(2))
        self.assertIs(maximum.category, TimingCategory.MOVEMENT_DEPENDENT)
        self.assertAlmostEqual(maximum.sample_delta(self.boy.animation(2), delay_dat=1, movement_metric=2.0), 0.24)

        lateral = runtime_timing(self.boy.animation(31))
        self.assertIs(lateral.dependency, TimingDependency.MOVEMENT_LATERAL)
        self.assertAlmostEqual(lateral.sample_delta(self.boy.animation(31), delay_dat=1, movement_metric=0.5), 0.092)

        fixed = runtime_timing(self.boy.animation(45))
        self.assertIs(fixed.category, TimingCategory.FIXED)
        self.assertAlmostEqual(fixed.samples_per_second(self.boy.animation(45)), 16.2)

    def test_index13_state_flag_doubles_verified_base_scale(self) -> None:
        clip = self.boy.animation(13)
        timing = runtime_timing(clip)
        self.assertIs(timing.category, TimingCategory.STATE_DEPENDENT)
        self.assertIs(timing.dependency, TimingDependency.STATE_FLAG_DOUBLE)
        self.assertAlmostEqual(timing.sample_delta(clip, delay_dat=1, state_timing_flag=False), 0.28)
        self.assertAlmostEqual(timing.sample_delta(clip, delay_dat=1, state_timing_flag=True), 0.56)

    def test_technical_mode_uses_single_slider_as_multiplier(self) -> None:
        playback = PlaybackController(self.boy.animations)
        playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        playback.set_time(2.0)
        playback.play()
        playback.advance(0.5)
        self.assertIs(playback.timing_mode, PlaybackTimingMode.TECHNICAL)
        self.assertEqual(playback.time, 2.5)

    def test_fixed_game_timing_uses_slider_as_multiplier(self) -> None:
        playback = PlaybackController(self.boy.animations, initial_index=43)
        playback.set_movement_speed(2.0)
        self.assertAlmostEqual(playback.base_samples_per_second, 13.5)
        self.assertAlmostEqual(playback.effective_samples_per_second, 27.0)
        playback.play()
        playback.advance(1.0)
        self.assertAlmostEqual(playback.time, 27.0)

    def test_movement_slider_is_applied_exactly_once_for_max_and_lateral(self) -> None:
        maximum = PlaybackTimingContext(movement_speed=4.0)
        self.assertAlmostEqual(
            maximum.effective_samples_per_second(self.boy.animation(0)),
            57.6,
        )
        lateral = PlaybackTimingContext(movement_speed=2.7)
        self.assertAlmostEqual(
            lateral.effective_samples_per_second(self.boy.animation(9)),
            29.808,
        )

    def test_state_dependent_flag_is_preserved_and_slider_multiplies_result(self) -> None:
        clip = self.boy.animation(13)
        clear = PlaybackTimingContext(movement_speed=2.7, state_timing_flag=False)
        set_flag = PlaybackTimingContext(movement_speed=2.7, state_timing_flag=True)
        self.assertAlmostEqual(clear.effective_samples_per_second(clip), 45.36)
        self.assertAlmostEqual(set_flag.effective_samples_per_second(clip), 90.72)

    def test_game_mode_uses_explicit_technical_fallback_for_unknown_state(self) -> None:
        unknown = replace(self.boy.animation(2), animation_index=99)
        playback = PlaybackController((unknown,), initial_index=99)
        playback.set_timing_mode(PlaybackTimingMode.GAME)
        playback.set_movement_speed(2.7)
        self.assertTrue(playback.uses_technical_fallback)
        self.assertEqual(playback.base_samples_per_second, 1.0)
        self.assertEqual(playback.effective_samples_per_second, 2.7)
        playback.play()
        playback.advance(0.5)
        self.assertEqual(playback.time, 1.35)

    def test_game_mode_preserves_loop_and_nonloop_end_behavior(self) -> None:
        loop = PlaybackController(self.boy.animations, initial_index=0)
        loop.set_time(15.5)
        loop.play()
        loop.advance(0.125)
        self.assertAlmostEqual(loop.time, 1.3)
        self.assertTrue(loop.playing)

        nonloop = PlaybackController(self.boy.animations, initial_index=43)
        nonloop.set_timing_mode(PlaybackTimingMode.GAME)
        nonloop.set_time(74.0)
        nonloop.play()
        nonloop.advance(1.0)
        self.assertEqual(nonloop.time, 75.0)
        self.assertFalse(nonloop.playing)

    def test_mode_switch_does_not_change_current_sample_position(self) -> None:
        playback = PlaybackController(self.boy.animations, initial_index=19)
        playback.set_time(30.41998291015625)
        playback.set_timing_mode(PlaybackTimingMode.GAME)
        self.assertAlmostEqual(playback.time, 30.41998291015625)
        self.assertAlmostEqual(playback.base_samples_per_second, 11.7)
        playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        self.assertAlmostEqual(playback.time, 30.41998291015625)
        self.assertEqual(playback.base_samples_per_second, 1.0)

    def test_movement_speed_slider_range_steps_and_labels(self) -> None:
        self.assertEqual((MIN_MOVEMENT_SPEED, MAX_MOVEMENT_SPEED), (1.0, 5.0))
        self.assertEqual((MIN_MOVEMENT_SPEED_TICK, MAX_MOVEMENT_SPEED_TICK), (10, 50))
        self.assertEqual(SUPPORTED_SPEEDS, tuple(value / 10 for value in range(10, 51)))
        self.assertEqual(movement_speed_label(1.0), "1.0")
        self.assertEqual(movement_speed_label(2.7), "2.7")
        self.assertEqual(movement_speed_label(5.0), "5.0")
        self.assertEqual(movement_speed_from_slider(27), 2.7)
        self.assertEqual(slider_from_movement_speed(2.7), 27)
        with self.assertRaises(ValueError):
            movement_speed_label(0.5)

    def test_slider_change_preserves_paused_time_and_survives_mode_and_clip_switches(self) -> None:
        playback = PlaybackController(self.boy.animations)
        playback.set_time(4.25)
        playback.set_movement_speed(2.7)
        self.assertEqual(playback.time, 4.25)
        playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        self.assertEqual((playback.time, playback.movement_speed), (4.25, 2.7))
        playback.select(43)
        self.assertEqual((playback.time, playback.movement_speed), (0.0, 2.7))

    def test_slider_change_takes_effect_during_playback(self) -> None:
        playback = PlaybackController(self.boy.animations, initial_index=43)
        playback.play()
        playback.advance(0.1)
        self.assertAlmostEqual(playback.time, 1.35)
        playback.set_movement_speed(2.0)
        playback.advance(0.1)
        self.assertAlmostEqual(playback.time, 4.05)


if __name__ == "__main__":
    unittest.main()
