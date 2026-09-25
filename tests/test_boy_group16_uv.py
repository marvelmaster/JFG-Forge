from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_group16_uv import _uv, build_group16_uv_artifacts


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


class BoyGroup16UvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = BOY.read_bytes()
        cls.rom = ROM.read_bytes()

    def test_s10_5_to_obj_formula_and_v_flip(self) -> None:
        self.assertEqual(_uv(0, 0), (0.0, 1.0))
        self.assertEqual(_uv(512, 512), (1.0, 0.0))
        self.assertEqual(_uv(-256, 256), (-0.5, 0.5))

    def test_pinned_group_texture_tile_and_faces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            artifacts = build_group16_uv_artifacts(self.boy, self.rom, MANIFEST, output)
        report = json.loads(artifacts["boy-group16-uv-report.json"])
        self.assertEqual(report["selection"]["group_index"], 16)
        self.assertEqual(report["selection"]["triangle_count"], 15)
        self.assertEqual(report["texture"]["texture_id_hex"], "0x820D")
        self.assertEqual(report["texture"]["compressed_rgba16_container_rom_offset_hex"], "0x178670")
        self.assertEqual(report["tile_configuration"]["cms"]["meaning"], "G_TX_CLAMP")
        self.assertEqual(report["tile_configuration"]["cmt"]["meaning"], "G_TX_CLAMP")
        self.assertEqual(report["tile_configuration"]["masks"], 0)
        self.assertEqual(report["tile_configuration"]["maskt"], 0)
        obj = artifacts["boy-group16-uv.obj"].decode()
        self.assertEqual(sum(line.startswith("v ") for line in obj.splitlines()), 16)
        self.assertEqual(sum(line.startswith("vt ") for line in obj.splitlines()), 45)
        self.assertEqual(sum(line.startswith("f ") for line in obj.splitlines()), 15)
        self.assertIn("map_Kd -clamp on", artifacts["boy-group16-uv.mtl"].decode())

    def test_generation_is_deterministic(self) -> None:
        first = build_group16_uv_artifacts(self.boy, self.rom, MANIFEST, Path("A"))
        second = build_group16_uv_artifacts(self.boy, self.rom, MANIFEST, Path("A"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
