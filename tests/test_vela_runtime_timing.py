from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from jfg_forge.export_service import ExportOperation, export_vela
from jfg_forge.playback import PlaybackController, PlaybackTimingMode
from jfg_forge.runtime_timing import (
    PlaybackTimingContext,
    TimingCategory,
    TimingDependency,
    VERIFIED_BOY_TIMINGS,
    VERIFIED_VELA_TIMINGS,
    runtime_timing,
)
from jfg_re.forge_data import load_boy
from jfg_re.forge_types import EvidenceStatus
from jfg_re.vela_data import load_vela
from research.vela.analyze_vela_runtime_timing import analyze


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
VELA_PROP = PROJECT_ROOT / "data/generated/props-us-verified/bins/0218_Girl.bin"
BOY_PROP = PROJECT_ROOT / "data/generated/props-us-verified/bins/0220_Boy.bin"
MANIFEST = PROJECT_ROOT / "data/generated/rgba16-us-verified/textures-manifest.json"
PHASE2 = PROJECT_ROOT / "research/vela/phase2-runtime-map.json"


@unittest.skipUnless(
    all(path.is_file() for path in (ROM, VELA_PROP, BOY_PROP, MANIFEST, PHASE2)),
    "Vela timing regression requires ignored local ROM and extraction fixtures.",
)
class VelaRuntimeTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vela = load_vela(VELA_PROP, ROM, MANIFEST)
        cls.boy = load_boy(BOY_PROP, ROM, MANIFEST)

    def test_rom_analysis_and_all_53_production_rows_agree(self) -> None:
        traced = analyze(
            ROM.read_bytes(),
            json.loads(PHASE2.read_text(encoding="utf-8")),
        )
        self.assertEqual(traced["counts"], {
            "FIXED": 30,
            "MOVEMENT_DEPENDENT": 22,
            "STATE_DEPENDENT": 1,
        })
        self.assertEqual(set(VERIFIED_VELA_TIMINGS), set(range(53)))
        self.assertEqual(len(traced["entries"]), 53)
        for entry in traced["entries"]:
            index = entry["index"]
            clip = self.vela.animation(index)
            timing = runtime_timing(clip)
            self.assertIs(timing, VERIFIED_VELA_TIMINGS[index])
            self.assertIs(timing.status, EvidenceStatus.VERIFIED)
            self.assertEqual(timing.animation_id, entry["animation_id"])
            self.assertAlmostEqual(timing.base_phase_per_vi_tick, entry["base_factor"])
            self.assertEqual(timing.category.value, entry["category"])

    def test_dependency_sets_and_exact_runtime_forms(self) -> None:
        dependencies = Counter(timing.dependency for timing in VERIFIED_VELA_TIMINGS.values())
        self.assertEqual(dependencies, {
            TimingDependency.FIXED: 30,
            TimingDependency.MOVEMENT_MAX: 13,
            TimingDependency.MOVEMENT_LATERAL: 6,
            TimingDependency.OBJECT_ABS_CLAMPED: 2,
            TimingDependency.COMBINED_MAX: 1,
            TimingDependency.STATE_FLAG_DOUBLE: 1,
        })
        self.assertEqual(VERIFIED_VELA_TIMINGS[44].evidence.split(";")[0], "Girl overlay 15 jump-table case 0x00F05B68")
        self.assertEqual(VERIFIED_VELA_TIMINGS[45].evidence.split(";")[0], "Girl overlay 15 jump-table case 0x00F05CB8")
        self.assertEqual(VERIFIED_VELA_TIMINGS[52].evidence.split(";")[0], "Girl overlay 15 jump-table case 0x00F05C10")

    def test_fixed_loop_nonloop_and_movement_reference_rates(self) -> None:
        fixed = runtime_timing(self.vela.animation(48))
        self.assertIs(fixed.category, TimingCategory.FIXED)
        self.assertEqual(fixed.clip_span(self.vela.animation(48)), 69.0)
        self.assertAlmostEqual(fixed.samples_per_second(self.vela.animation(48)), 12.42)

        loop = runtime_timing(self.vela.animation(0))
        self.assertEqual(loop.clip_span(self.vela.animation(0)), 16.0)
        self.assertAlmostEqual(loop.samples_per_second(self.vela.animation(0), movement_metric=1.0), 13.44)
        self.assertAlmostEqual(loop.samples_per_second(self.vela.animation(0), movement_metric=2.7), 36.288)

        lateral = runtime_timing(self.vela.animation(9))
        self.assertAlmostEqual(lateral.samples_per_second(self.vela.animation(9), movement_metric=1.0), 11.04)
        object_abs = runtime_timing(self.vela.animation(44))
        combined = runtime_timing(self.vela.animation(45))
        self.assertAlmostEqual(object_abs.samples_per_second(self.vela.animation(44), movement_metric=1.0), 5.76)
        self.assertAlmostEqual(combined.samples_per_second(self.vela.animation(45), movement_metric=1.0), 5.76)

    def test_state_flag_and_slider_application(self) -> None:
        clip = self.vela.animation(13)
        timing = runtime_timing(clip)
        self.assertIs(timing.dependency, TimingDependency.STATE_FLAG_DOUBLE)
        self.assertAlmostEqual(timing.samples_per_second(clip, state_timing_flag=False), 13.2)
        self.assertAlmostEqual(timing.samples_per_second(clip, state_timing_flag=True), 26.4)

        movement = PlaybackTimingContext(movement_speed=2.7)
        self.assertAlmostEqual(movement.effective_samples_per_second(self.vela.animation(0)), 36.288)
        self.assertAlmostEqual(movement.effective_samples_per_second(self.vela.animation(44)), 15.552)
        self.assertAlmostEqual(movement.effective_samples_per_second(self.vela.animation(45)), 15.552)
        flagged = PlaybackTimingContext(movement_speed=2.7, state_timing_flag=True)
        self.assertAlmostEqual(flagged.effective_samples_per_second(clip), 71.28)

    def test_technical_game_switch_preserves_position(self) -> None:
        playback = PlaybackController(self.vela.animations, initial_index=48)
        playback.set_time(17.25)
        self.assertIs(playback.timing_mode, PlaybackTimingMode.GAME)
        self.assertAlmostEqual(playback.effective_samples_per_second, 12.42)
        playback.set_timing_mode(PlaybackTimingMode.TECHNICAL)
        self.assertEqual(playback.time, 17.25)
        self.assertEqual(playback.effective_samples_per_second, 1.0)
        playback.set_timing_mode(PlaybackTimingMode.GAME)
        self.assertEqual(playback.time, 17.25)

    def test_preview_and_export_share_one_vela_timing_context(self) -> None:
        playback = PlaybackController(self.vela.animations, initial_index=0)
        playback.set_movement_speed(2.7)
        preview_rate = playback.effective_samples_per_second
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "vela-index0.gltf"
            result = export_vela(
                self.vela,
                target,
                ExportOperation.CURRENT_ANIMATION,
                animation_index=0,
                timing_context=playback.timing_context,
            )
            gltf = json.loads(target.read_text(encoding="utf-8"))
        extras = gltf["animations"][0]["extras"]
        self.assertAlmostEqual(result.effective_samples_per_second, preview_rate)
        self.assertAlmostEqual(extras["effective_samples_per_second"], preview_rate)
        self.assertEqual(extras["timing_mode"], "Game Timing")
        self.assertEqual(extras["movement_speed"], 2.7)

    def test_boy_timing_profile_is_unchanged(self) -> None:
        self.assertEqual(len(VERIFIED_BOY_TIMINGS), 52)
        boy0 = runtime_timing(self.boy.animation(0))
        boy13 = runtime_timing(self.boy.animation(13))
        boy43 = runtime_timing(self.boy.animation(43))
        self.assertAlmostEqual(boy0.samples_per_second(self.boy.animation(0), movement_metric=1.0), 14.4)
        self.assertAlmostEqual(boy13.samples_per_second(self.boy.animation(13), state_timing_flag=True), 33.6)
        self.assertAlmostEqual(boy43.samples_per_second(self.boy.animation(43)), 13.5)


if __name__ == "__main__":
    unittest.main()
