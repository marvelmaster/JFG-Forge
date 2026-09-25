from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_forge.attachment_browser import AttachmentBrowserController, inspect_attachment
from jfg_forge.render_data import prepare_attachment_render_data
from jfg_re.forge_data import load_boy, load_boy_attachment
from jfg_re.forge_scene import evaluate_boy_scene
from jfg_re.forge_types import EvidenceStatus


BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
PROPS = BOY.parent
ROM = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"
MANIFEST = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"

EXPECTED = (
    (0, 301, "BPistol", 67),
    (1, 302, "BAutomatic", 116),
    (2, 303, "BUzi", 126),
    (3, 304, "BUzi1", 106),
    (4, 305, "BShrinkBeam", 110),
    (5, 306, "BRocket", 142),
    (6, 307, "BFlameThrower", 132),
    (7, 308, "BSniper", 245),
    (8, 309, "JunoHand", 32),
)
EXPECTED_TEXTURES = (
    (2, 1),
    (2, 1),
    (2, 1),
    (2, 0),
    (2, 1),
    (2, 1),
    (3, 0),
    (2, 1),
    (1, 0),
)


class ForgeAttachmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boy = load_boy(BOY, ROM, MANIFEST)
        cls.loaded = {
            slot: load_boy_attachment(cls.boy, slot=slot, props_dir=PROPS)
            for slot, _prop, _name, _faces in EXPECTED
        }

    def test_browser_has_none_and_exact_verified_slot_metadata(self) -> None:
        browser = AttachmentBrowserController(self.boy.attachment)
        self.assertIsNone(browser.selected_slot)
        self.assertEqual(browser.entries[0].label, "None")
        self.assertEqual(
            [entry.label for entry in browser.entries[1:]],
            [f"Slot {slot} — Prop{prop} — {name}" for slot, prop, name, _faces in EXPECTED],
        )
        browser.select(4)
        self.assertEqual(browser.selected_slot, 4)
        browser.select(None)
        self.assertIsNone(browser.selected_slot)
        with self.assertRaises(KeyError):
            browser.select(9)

    def test_all_nine_slots_load_generic_prop_models(self) -> None:
        actual = tuple(
            (
                slot,
                loaded.model.prop_id,
                loaded.model.name,
                loaded.model.active_face_count,
            )
            for slot, loaded in self.loaded.items()
        )
        self.assertEqual(actual, EXPECTED)

    def test_scene_uses_matrix_6_and_reports_attachment_metadata(self) -> None:
        loaded = self.loaded[0]
        scene = evaluate_boy_scene(
            self.boy,
            animation_index=0,
            time=7.5,
            loaded_attachment=loaded,
        )
        self.assertEqual(scene.model.active_face_count, 502)
        self.assertEqual(len(scene.model.render_mesh.vertices), 1506)
        self.assertEqual(scene.attachment.parent_joint_id, 6)
        self.assertIs(scene.attachment.socket_world_matrix, scene.pose.joints[6].world_matrix)
        self.assertEqual(scene.attachment.final_world_transform, scene.pose.joints[6].world_matrix)
        self.assertIs(scene.attachment.transform_status, EvidenceStatus.VERIFIED)
        information = inspect_attachment(loaded, scene.attachment)
        self.assertEqual((information.slot, information.prop_id, information.active_faces), (0, 301, 67))
        self.assertEqual(
            information.verified_textures + information.unknown_textures,
            len(loaded.model.textures),
        )

    def test_texture_status_is_explicit_for_every_slot(self) -> None:
        actual = tuple(
            (
                sum(texture.supported for texture in self.loaded[slot].model.textures),
                sum(not texture.supported for texture in self.loaded[slot].model.textures),
            )
            for slot in range(9)
        )
        self.assertEqual(actual, EXPECTED_TEXTURES)

    def test_attachment_render_data_uses_only_prop_geometry(self) -> None:
        for slot in (0, 8):
            loaded = self.loaded[slot]
            scene = evaluate_boy_scene(
                self.boy,
                animation_index=43,
                time=37.5,
                loaded_attachment=loaded,
            )
            data = prepare_attachment_render_data(scene.attachment)
            self.assertEqual(len(data.positions), loaded.model.active_face_count * 3)
            self.assertEqual(sum(batch.face_count for batch in data.batches), loaded.model.active_face_count)
        self.assertEqual(len(self.boy.model.render_mesh.vertices), 1506)
        self.assertEqual(self.loaded[0].model.active_face_count, 67)
        self.assertEqual(self.loaded[8].model.active_face_count, 32)


if __name__ == "__main__":
    unittest.main()
