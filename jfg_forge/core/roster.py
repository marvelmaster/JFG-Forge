"""Every playable model JFG Forge can open, as one table.

The six campaign characters keep their hand-written, fully verified loaders.
All other entries (multiplayer characters and hover ships) use the generic
compact loader and are described only by the pins below.

Evidence levels follow the project convention.  A multiplayer character takes
its weapon set, socket joint and Game Timing from the campaign character whose
animation IDs it reproduces (Juno for 21-joint models, Vela for 28-joint
models).  That inference is LIKELY: the ROM data agree, but no runtime capture
shows the character's controller.  Hover ships have no weapon and no known
timing.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from jfg_forge.core.asset_types import AttachmentDefinition, BoyAsset, EvidenceStatus
from jfg_forge.core.character_data import BOYGUN_ATTACHMENT
from jfg_forge.core.rom_source import RomSource
from jfg_forge.core.vela import GIRLGUN_ATTACHMENT


GROUP_CAMPAIGN = "Campaign"
GROUP_MULTIPLAYER = "Multiplayer characters"
GROUP_SHIPS = "Hover ships"

TIMING_JUNO_LIKE = "juno_like"
TIMING_VELA_LIKE = "vela_like"
TIMING_NONE = "none"

# Juno's 52 animation IDs (Prop 220) and Vela's 53 entries (Prop 218), in
# catalogue order.  Multiplayer characters reproduce the start of these lists.
JUNO_CLIP_IDS = (
    1026, 1027, 1028, 1025, 1033, 1039, 1040, 1041, 1038, 1042, 1043, 1031,
    1036, 1029, 1030, 1044, 1019, 1020, 1021, 1022, 1023, 1051, 1035, 1070,
    1048, 1050, 1054, 1053, 1055, 1056, 1057, 1058, 1059, 1060, 1063, 1062,
    1061, 1066, 1067, 1068, 1045, 1046, 1047, 1069, 1034, 1024, 1052, 1064,
    1065, 1032, 1037, 1071,
)
VELA_CLIP_IDS = (
    1097, 1098, 1099, 1096, 1104, 1110, 1111, 1112, 1109, 1113, 1114,
    1102, 1107, 1100, 1101, 1115, 1090, 1091, 1092, 1093, 1094, 1095,
    1121, 1106, 1141, 1119, 1120, 1124, 1123, 1125, 1126, 1127, 1128,
    1129, 1130, 1116, 1117, 1118, 1131, 1132, 1133, 1124, 1134, 1135,
    1137, 1136, 1138, 1139, 1140, 1122, 1103, 1108, 1142,
)
SHIP_CLIP_IDS = (779, 780)

JUNO_LIKE_ATTACHMENT = dataclasses.replace(BOYGUN_ATTACHMENT, status=EvidenceStatus.LIKELY)
VELA_LIKE_ATTACHMENT = dataclasses.replace(GIRLGUN_ATTACHMENT, status=EvidenceStatus.LIKELY)
NO_ATTACHMENT = AttachmentDefinition(
    name="None",
    object_definition_id=0,
    attachment_joint_id=0,
    slots=(),
    status=EvidenceStatus.UNKNOWN,
)


@dataclass(frozen=True)
class CharacterSpec:
    key: str
    group: str
    prop_id: int
    file_name: str
    kind: str
    model_name: str = ""
    prop_sha256: str = ""
    transform_count: int = 0
    clip_count: int = 0
    active_faces: int = 0
    timing_family: str = TIMING_NONE
    clip_ids: tuple[int, ...] = ()
    attachment: AttachmentDefinition = NO_ATTACHMENT

    @property
    def compact(self) -> bool:
        return self.kind == "compact"

    @property
    def has_attachment(self) -> bool:
        return self.kind != "compact" or bool(self.attachment.slots)

    @property
    def file_stem(self) -> str:
        return self.file_name.lower()


def _campaign(key: str, prop_id: int, kind: str) -> CharacterSpec:
    return CharacterSpec(key, GROUP_CAMPAIGN, prop_id, key, kind)


def _juno_like(key: str, file_name: str, prop_id: int, model_name: str, sha: str, joints: int, faces: int) -> CharacterSpec:
    return CharacterSpec(
        key, GROUP_MULTIPLAYER, prop_id, file_name, "compact", model_name, sha, joints, 51, faces,
        TIMING_JUNO_LIKE, JUNO_CLIP_IDS[:51], JUNO_LIKE_ATTACHMENT,
    )


def _vela_like(key: str, file_name: str, prop_id: int, model_name: str, sha: str, joints: int, faces: int) -> CharacterSpec:
    return CharacterSpec(
        key, GROUP_MULTIPLAYER, prop_id, file_name, "compact", model_name, sha, joints, 52, faces,
        TIMING_VELA_LIKE, VELA_CLIP_IDS[:52], VELA_LIKE_ATTACHMENT,
    )


def _ship(key: str, file_name: str, prop_id: int, model_name: str, sha: str, faces: int) -> CharacterSpec:
    return CharacterSpec(
        key, GROUP_SHIPS, prop_id, file_name, "compact", model_name, sha, 8, 2, faces,
        TIMING_NONE, SHIP_CLIP_IDS, NO_ATTACHMENT,
    )


ROSTER: tuple[CharacterSpec, ...] = (
    _campaign("Juno", 220, "boy"),
    _campaign("PowerBoy", 221, "powerboy"),
    _campaign("Vela", 218, "vela"),
    _campaign("PowerGirl", 219, "powergirl"),
    _campaign("Lupus", 222, "lupus"),
    _campaign("PowerDog", 223, "powerdog"),
    _juno_like("Green Ant", "GreenAnt", 250, "MultiGreenAnt",
               "5b044d6c9a43bbdfa8505fc77bdfab5f81888d2323680cae7c5100ae4c25160f", 21, 307),
    _juno_like("Red Ant", "RedAnt", 253, "MultiRedAnt",
               "6f2656c352593469439e37566982ea0d0c8beb80b085203cc447c7c1c003f7c3", 21, 307),
    _vela_like("Blue Ant", "BlueAnt", 248, "MultiBlueAnt",
               "03e184f23ccdc239c53b2a63308d89e950f4fe3d9ce6e5560e3ed91a42bcc66b", 28, 337),
    _vela_like("Yellow Ant", "YellowAnt", 252, "MultiYellowAnt",
               "00f794c58445c2797ae22f8c473cadb97b8a3b67553c705cb8c7956f3739abb6", 28, 337),
    _juno_like("Tribal Man", "TribalMan", 251, "MultiTribalMan",
               "1d2054ecb8f70b558041b8aa9f46184964dc9ceb4a235dcde05dec901dc0afe3", 21, 115),
    _vela_like("Tribal Woman", "TribalWoman", 249, "MultiTribalWoma",
               "9c9fc5899e113bc6731c1aff5abaf3442d6645020d7ca92dc003b59d0edf1044", 28, 135),
    _juno_like("Shield Bug", "ShieldBug", 254, "MultiShieldBug",
               "8f4fa9fed383d11818ecaf72cce6c46909fe28786bddbfae295971a0e391dbca", 21, 231),
    _juno_like("Stag Bug", "StagBug", 255, "MultiStagBug",
               "eb40f5d8580c063bbd17f378b5cfef5e710f367c105d7edbefbb6f6485986384", 21, 268),
    _juno_like("Weevil", "Weevil", 256, "MultiWeevil",
               "aee8bb5041bf1df65e042aa76139042fdc4ce783955343316013accebd67243c", 21, 232),
    _juno_like("Cyborg", "Cyborg", 257, "MultiCyborg",
               "5bbf05d5f1dfdb410b975ecf238d68bb21ad01c6444ad5c6a295cc1492590866", 21, 254),
    _juno_like("Zombie", "Zombie", 258, "MultiZombie",
               "41be805bd6670299c245a34d9e86fc650ce2729334bc24144c28b793919033ac", 21, 257),
    _ship("Yellow Ant Ship", "YellowAntShip", 225, "HoverShip1",
          "0d7866386637c2f9e05321bde021047ebd34cc2d9679da6a91740d3845a74ef4", 192),
    _ship("Yellow Ant Ship (low detail)", "YellowAntShipLod", 226, "HoverShip1Lod",
          "314fdb33f517cd3d7f7b5696beed4d582c61b502c201af56b32dc85a6475d29d", 62),
    _ship("Red Ant Ship", "RedAntShip", 228, "HoverShip2",
          "f2e7472ef6a8bc94ac0340b8aea1cc35d7af6d41784d49ae4ce45fcf322f1550", 208),
    _ship("Red Ant Ship (low detail)", "RedAntShipLod", 229, "HoverShip2Lod",
          "05bcf781c58139bfb388945b4a44e0652b2ff0d5db408fc10aa8c1da736fcb54", 62),
    _ship("Blue Ant Ship", "BlueAntShip", 231, "HoverShip3",
          "6497a8e728f67d8c9aa1471c2a0633a7078b47880c4442467001586764ccaeb4", 192),
    _ship("Blue Ant Ship (low detail)", "BlueAntShipLod", 232, "HoverShip3Lod",
          "5bfc0b5e10a3b33716af40718906a38f3054d1ee0aa883c0099bb025a8b42a21", 62),
    _ship("Green Ant Ship", "GreenAntShip", 234, "HoverShip4",
          "19365f5a93c069fe8e7c8ac19509acd3431e11bde77d0051e479b862bbabac81", 210),
    _ship("Green Ant Ship (low detail)", "GreenAntShipLod", 235, "HoverShip4Lod",
          "ec74b4e8755fbfe7a57c36d48bd76eabb1d4e26d4513466355806c2a2ea5f6f1", 62),
)

_BY_KEY = {spec.key: spec for spec in ROSTER}
if len(_BY_KEY) != len(ROSTER):
    raise RuntimeError("Roster keys must be unique.")

GROUPS = (GROUP_CAMPAIGN, GROUP_MULTIPLAYER, GROUP_SHIPS)


def spec_for(key: str) -> CharacterSpec:
    try:
        return _BY_KEY[key]
    except KeyError as error:
        raise KeyError(f"Unknown character {key!r}.") from error


def specs_in_group(group: str) -> tuple[CharacterSpec, ...]:
    return tuple(spec for spec in ROSTER if spec.group == group)


def load_character(
    spec: CharacterSpec,
    source: RomSource | Path,
    texture_manifest_path: Path | None = None,
) -> BoyAsset:
    """Load one roster entry through its verified or generic loader."""
    from jfg_forge.core import character_data, lupus, powerdog, vela
    from jfg_forge.core.compact_character import load_compact_character

    if spec.compact:
        return load_compact_character(spec, source, texture_manifest_path)
    loaders: dict[str, Callable[..., BoyAsset]] = {
        "boy": character_data.load_boy,
        "powerboy": character_data.load_powerboy,
        "vela": vela.load_vela,
        "powergirl": vela.load_powergirl,
        "lupus": lupus.load_lupus,
        "powerdog": powerdog.load_powerdog,
    }
    return loaders[spec.kind](None, source, texture_manifest_path)


def scene_evaluator(spec: CharacterSpec) -> Callable[..., object]:
    """Return ``evaluate(asset, animation_index=, time=, ...)`` for the entry."""
    from jfg_forge.core import scene

    if spec.compact:
        return scene.evaluate_compact_scene
    return {
        "boy": scene.evaluate_boy_scene,
        "powerboy": scene.evaluate_boy_scene,
        "vela": scene.evaluate_vela_scene,
        "powergirl": scene.evaluate_vela_scene,
        "lupus": scene.evaluate_lupus_scene,
        "powerdog": scene.evaluate_powerdog_scene,
    }[spec.kind]


def attachment_loader(spec: CharacterSpec) -> Callable[..., object]:
    """Return ``load(asset, slot=, props_dir=)``; entries without weapons raise KeyError."""
    from jfg_forge.core import character_data, lupus, powerdog, vela

    if spec.compact:
        if spec.timing_family == TIMING_JUNO_LIKE:
            return character_data.load_boy_attachment
        if spec.timing_family == TIMING_VELA_LIKE:
            return vela.load_vela_attachment

        def no_attachment(asset: BoyAsset, *, slot: int, props_dir: Path | None = None):
            raise KeyError(f"{spec.key} has no attachment slots; slot {slot} is unavailable.")

        return no_attachment
    return {
        "boy": character_data.load_boy_attachment,
        "powerboy": character_data.load_boy_attachment,
        "vela": vela.load_vela_attachment,
        "powergirl": vela.load_vela_attachment,
        "lupus": lupus.load_lupus_attachment,
        "powerdog": powerdog.load_powerdog_attachment,
    }[spec.kind]


class CharacterLibrary:
    """Loads roster entries from one ROM the first time each is requested."""

    def __init__(self, source: RomSource | Path, texture_manifest_path: Path | None = None) -> None:
        self.source = source
        self.texture_manifest_path = texture_manifest_path
        self._loaded: dict[str, BoyAsset] = {}

    def is_loaded(self, key: str) -> bool:
        return key in self._loaded

    def get(self, key: str) -> BoyAsset:
        asset = self._loaded.get(key)
        if asset is None:
            asset = load_character(spec_for(key), self.source, self.texture_manifest_path)
            self._loaded[key] = asset
        return asset


__all__ = [
    "CharacterLibrary",
    "CharacterSpec",
    "GROUPS",
    "GROUP_CAMPAIGN",
    "GROUP_MULTIPLAYER",
    "GROUP_SHIPS",
    "JUNO_CLIP_IDS",
    "ROSTER",
    "SHIP_CLIP_IDS",
    "TIMING_JUNO_LIKE",
    "TIMING_NONE",
    "TIMING_VELA_LIKE",
    "VELA_CLIP_IDS",
    "attachment_loader",
    "load_character",
    "scene_evaluator",
    "spec_for",
    "specs_in_group",
]
