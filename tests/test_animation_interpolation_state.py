from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_forge.playback import PlaybackController
from jfg_re.animation_time import runtime_interpolation_state
from jfg_re.forge_data import load_boy, sample_animation


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"
SLIDER_VALUES = (1.0, 1.1, 1.2, 2.7, 3.3, 4.0, 4.9, 5.0)


class AnimationInterpolationStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)

    def test_exact_and_adjacent_integer_positions_are_canonical(self) -> None:
        exact = runtime_interpolation_state(7.0, sample_count=16, loop=True)
        below = runtime_interpolation_state(math.nextafter(7.0, -math.inf), sample_count=16, loop=True)
        above = runtime_interpolation_state(math.nextafter(7.0, math.inf), sample_count=16, loop=True)
        self.assertEqual((exact.current_sample, exact.next_sample, exact.fraction_10bit), (7, 7, 0))
        self.assertEqual(below, exact)
        self.assertEqual(above, exact)

        last_fraction = runtime_interpolation_state(6.0 + 1023.0 / 1024.0, sample_count=16, loop=True)
        self.assertEqual(
            (last_fraction.current_sample, last_fraction.next_sample, last_fraction.fraction_10bit),
            (6, 7, 1023),
        )

    def test_loop_wrap_and_nonloop_endpoint_carry_canonically(self) -> None:
        loop = runtime_interpolation_state(math.nextafter(16.0, -math.inf), sample_count=16, loop=True)
        nonloop = runtime_interpolation_state(math.nextafter(75.0, -math.inf), sample_count=76, loop=False)
        endpoint = runtime_interpolation_state(75.0, sample_count=76, loop=False)
        self.assertEqual((loop.current_sample, loop.next_sample, loop.fraction_10bit), (0, 0, 0))
        self.assertEqual((nonloop.current_sample, nonloop.next_sample, nonloop.fraction_10bit), (75, 75, 0))
        self.assertEqual(endpoint, nonloop)

    def test_reproduced_slider_failure_carries_1024_instead_of_decoding_it(self) -> None:
        playback = PlaybackController(self.boy.animations, initial_index=0)
        playback.play()
        deltas = (1.0 / 60.0, 0.016, 0.033, 0.001)
        for tick in range(2097):
            playback.set_movement_speed(SLIDER_VALUES[tick % len(SLIDER_VALUES)])
            playback.advance(deltas[tick % len(deltas)])
        self.assertAlmostEqual(playback.time, 6.999680000000052)
        self.assertEqual(round((playback.time - math.floor(playback.time)) * 1024.0), 1024)
        pose = sample_animation(self.boy, 0, playback.time)
        self.assertEqual((pose.current_sample, pose.next_sample, pose.fraction_10bit), (7, 7, 0))

    def test_playback_stress_keeps_fixed_and_movement_fractions_in_runtime_domain(self) -> None:
        deltas = (1.0 / 60.0, 0.016, 0.033, 0.001, 0.125)
        for animation_index in (0, 43):
            playback = PlaybackController(self.boy.animations, initial_index=animation_index)
            playback.play()
            for tick in range(5000):
                playback.set_movement_speed(SLIDER_VALUES[tick % len(SLIDER_VALUES)])
                playback.advance(deltas[tick % len(deltas)])
                pose = sample_animation(self.boy, animation_index, playback.time)
                self.assertLessEqual(pose.fraction_10bit, 1023)
                self.assertGreaterEqual(pose.fraction_10bit, 0)
                if not playback.playing:
                    self.assertEqual(playback.time, playback.end_time)
                    self.assertEqual(pose.fraction_10bit, 0)
                    playback.play()

    def test_paused_slider_changes_preserve_sample_position_for_all_values(self) -> None:
        playback = PlaybackController(self.boy.animations, initial_index=0)
        playback.set_time(7.25)
        for value in SLIDER_VALUES:
            playback.set_movement_speed(value)
            self.assertEqual(playback.time, 7.25)


if __name__ == "__main__":
    unittest.main()
