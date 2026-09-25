from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_export import (
    BOY_SHA256,
    BoyExportError,
    _geometry_records,
    build_boy_export_artifacts,
    parse_boy,
    resolve_boy_textures,
)


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
POWER_BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0221_PowerBoy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class BoyExperimentalExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy_data = BOY.read_bytes()
        cls.rom = ROM.read_bytes()
        cls.model = parse_boy(cls.boy_data)

    def test_input_is_pinned_and_powerboy_is_rejected(self) -> None:
        self.assertEqual(BOY_SHA256, "2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf")
        with self.assertRaises(BoyExportError):
            parse_boy(POWER_BOY.read_bytes())

    def test_group_ranges_indices_and_geometric_degenerates(self) -> None:
        vertices, triangles, matrices = _geometry_records(self.model)
        self.assertEqual(len(vertices), 660)
        self.assertEqual(len(triangles), 520)
        degenerate = [record for record in triangles if record["geometrically_degenerate"]]
        self.assertEqual(len(degenerate), 15)
        self.assertTrue(all(record["degenerate_reason"] == "repeated XYZ point" for record in degenerate))
        self.assertEqual(sum(record["exported_in_all_groups_obj"] for record in triangles), 505)
        self.assertEqual(sum(record["exported_in_runtime_visible_obj"] for record in triangles), 502)
        self.assertEqual(sorted(matrices), [2, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])

    def test_texture_ids_resolve_and_only_verified_rgba16_is_linked(self) -> None:
        records, _ = resolve_boy_textures(self.model, self.rom, MANIFEST)
        self.assertEqual(len(records), 18)
        verified = [record for record in records if record["verified_rgba16_match"]]
        unsupported = [record for record in records if not record["verified_rgba16_match"]]
        self.assertEqual(len(verified), 14)
        self.assertEqual(
            [record["texture_id_hex"] for record in unsupported],
            ["0x8431", "0x9A00", "0x874E", "0x874C"],
        )
        self.assertTrue(all(record["runtime_asset_resolution_status"] == "VERIFIED" for record in records))

    def test_artifacts_are_deterministic_and_emit_no_obj_uvs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "boy"
            first = build_boy_export_artifacts(self.boy_data, self.rom, MANIFEST, output)
            second = build_boy_export_artifacts(self.boy_data, self.rom, MANIFEST, output)
        self.assertEqual(first, second)
        obj = first["boy-runtime-visible.obj"].decode("utf-8")
        self.assertNotIn("\nvt ", obj)
        report = json.loads(first["boy-export-report.json"])
        self.assertEqual(report["counts"]["active_groups"], 65)
        self.assertEqual(report["counts"]["runtime_skipped_groups"], 17)
        self.assertTrue(report["validation"]["deterministic_regeneration_match"])


if __name__ == "__main__":
    unittest.main()
