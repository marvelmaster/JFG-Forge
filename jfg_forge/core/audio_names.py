"""Names for the game's songs and sound effects.

The ROM stores no audio names, so these come from three independent sources:

* **Song names** are the community song list of the kiosk demo (The Cutting Room
  Floor). The final ROM uses the same numbers: level records name their music at
  +0x72 and agree (Goldwood levels play 0x04, Mizar's levels 0x11, the swamp 0x2E,
  the military base 0x1F, the mines 0x26, and so on), and lengths match (the gem
  and medal jingles are short, "Landing" 0x07 and 0x3A and "Spawnship" 0x10 and
  0x3B are note-for-note identical). Status: VERIFIED for songs 0x01-0x43.
* **Levels that play a song** are read from the ROM (level record +0x72).
* **Sound-effect labels** come from the game code: every call that plays a sound
  with a fixed number, named after the calling function (for example
  ``healthPickupControl`` plays sounds 487, 552, 553 and 554). The label says who
  plays the sound, not what it sounds like. Status: LIKELY. Only 78 of the 640
  sounds are played with a fixed number; the rest are triggered through data.
"""

from __future__ import annotations

import struct

from jfg_forge.core.level_data import list_levels
from jfg_forge.core.model_parser import _asset_lut, _asset_range
from jfg_forge.core.rom_source import RomSource

MUSIC_FIELD_OFFSET = 0x72

# song number -> (name, source note)
SONG_NAMES: dict[int, str] = {
    0x01: "Sound-effect sequence 1",
    0x02: "Sound-effect sequence 2",
    0x03: "Sound-effect sequence 3",
    0x04: "Goldwood",
    0x05: "SS Anubis",
    0x07: "Landing",
    0x0B: "Main Theme",
    0x0C: "Caves of Goldwood",
    0x0D: "Gem pickup",
    0x0E: "Character Select",
    0x0F: "Goldbar",
    0x10: "Spawnship",
    0x11: "Mizar's Palace",
    0x12: "Rith Essa",
    0x13: "Ship ambience",
    0x14: "Sound-effect sequence 14",
    0x15: "Sound-effect sequence 15",
    0x16: "Sound-effect sequence 16",
    0x17: "Sound-effect sequence 17",
    0x18: "Sound-effect sequence 18",
    0x19: "Sound-effect sequence 19",
    0x1A: "Sound-effect sequence 1A",
    0x1B: "Sound-effect sequence 1B",
    0x1D: "Large Gem pickup",
    0x1E: "Eschebone",
    0x1F: "Ichor",
    0x20: "Goldwood Invasion",
    0x21: "Flume",
    0x23: "Sound-effect sequence 23",
    0x25: "Cerulean",
    0x26: "Mines",
    0x27: "Sound-effect sequence 27",
    0x29: "Asteroid",
    0x2A: "Clear Area",
    0x2B: "Medal",
    0x2C: "Unused song 3",
    0x2E: "Tawfret",
    0x2F: "Vela's Capture",
    0x30: "Meeting Mizar (Part 1)",
    0x31: "Landing on Gem Quarry",
    0x32: "Sekhmet",
    0x33: "Transformation of Tawfret",
    0x34: "Meeting Lupus",
    0x35: "Boss Battle",
    0x36: "Unused song 1",
    0x37: "Spacestation",
    0x38: "Death",
    0x39: "Opening Cinematic",
    0x3A: "Landing (second copy)",
    0x3B: "Spawnship (second copy)",
    0x3C: "Disco",
    0x3D: "More Disco",
    0x3E: "Even More Disco",
    0x3F: "Unused song 2",
    0x40: "Crickets",
    0x41: "More Disco (2)",
    0x42: "Rescuing Vela",
    0x43: "Mizar's Death",
}

# sound number -> (label, calling functions in the game code)
SFX_LABELS: dict[int, tuple[str, str]] = {
    1: ("Flamethrower fire", "flamethrowerFire"),
    3: ("Enemy or boss shot", "controlFireDummyShot, mizarControl"),
    6: ("Mr. Hints", "mrhintsControl"),
    22: ("Mizar wing bit", "mizarWingBitControl"),
    28: ("Player action (Juno, Vela, Lupus)", "boyControl, girlControl, dogControl"),
    29: ("Aim hit check", "hitPlayerAimCheck"),
    33: ("Pause and character menus", "multiPlayerPauseInit, pauseInit, menuCamControl"),
    34: ("Boss and race objects", "mizarControl, rockstormControl, raceobstacleControl, robottargetControl"),
    35: ("Multiplayer character menu", "menuCamControl, multiCharArmControl"),
    47: ("Squad enemy fires weapon", "squadsFireWeapon"),
    71: ("Multiplayer stats screen", "frontCleanupMultiStats"),
    138: ("Weapon and invisibility pickup", "invisibilityControl, weaponPickupControl, robotcollectableControl"),
    139: ("Deathmatch scores", "frontDeathMatchScores"),
    154: ("Shuriken", "ShirukenControl"),
    156: ("Player action 2 (Juno, Vela, Lupus)", "boyControl, girlControl, dogControl"),
    197: ("Mantis", "mantisControl"),
    205: ("Mine", "mineControl"),
    206: ("Character badge", "frontCharBadge"),
    207: ("Character badge / menu TV", "frontCharBadge, menuCamFacingTVControl"),
    208: ("Character select", "frontCharSelect"),
    218: ("Sprint race", "sprintUpdate"),
    219: ("Teleport", "teleportEffectControl"),
    221: ("Player animation-event sound", "animBoyEventHandler, animGirlEventHandler, animDogEventHandler"),
    241: ("Vela magic", "girlUpdateMagic"),
    244: ("Chest", "chestControl"),
    245: ("Sidekick", "sidekickControl"),
    246: ("Sidekick 2", "sidekickControl"),
    249: ("Invincibility shield", "invincibilityShieldControl"),
    312: ("Sidekick 3", "sidekickControl"),
    351: ("Sidekick 4", "sidekickControl"),
    352: ("Sprint race 2", "sprintUpdate"),
    354: ("Sprint race 3", "sprintUpdate"),
    356: ("Sprint race 4", "sprintUpdate"),
    363: ("Menu screens", "healthScreen, inventoryScreen, shipScreen, tribalScreen, weaponScreen"),
    364: ("Menu select", "frontOptionsPage, frontKeyboard, frontMultiModeSelect, healthScreen"),
    365: ("Menu confirm", "menuScreen, weaponScreen, frontOptionsPage, frontStartScreen"),
    366: ("Menu move", "frontOptionsPage, frontKeyboard, frontMap, hoovertankControl"),
    369: ("Menu frame", "frontMenuFrameTick, arcadeControl"),
    370: ("Menu frame closes", "frontClearMenuFrame"),
    399: ("Hover ship", "hovershipControl"),
    400: ("Instruments menu", "frontCleanupInstruments"),
    403: ("Race pickup", "racepickupControl"),
    404: ("Target switch", "targetswitchControl"),
    443: ("Mantis 2", "mantisControl"),
    444: ("Mantis 3", "mantisControl"),
    446: ("Terminal", "terminalControl"),
    447: ("Terminal 2", "terminalControl"),
    451: ("Multiplayer stats 2", "frontCleanupMultiStats"),
    452: ("Multiplayer stats and credits", "frontMultiStats, frontCredits"),
    454: ("Boss rockstorm", "rockstormControl"),
    455: ("Mizar attack", "mizarControl"),
    456: ("Weapon update", "controlUpdateWeapon"),
    460: ("Mizar and Fat Bob", "FatBobPhaseChange, mizarControl"),
    461: ("Mizar attack 2", "mizarControl"),
    464: ("Mizar attack 3", "mizarControl"),
    481: ("Weapon update 2", "controlUpdateWeapon"),
    487: ("Health pickup", "healthPickupControl"),
    489: ("Ammo pickup", "ammoPickupControl, severedLimbControl"),
    490: ("Ammo pickup 2", "ammoPickupControl"),
    491: ("Robot token", "robotTokenControl"),
    495: ("Night-vision pad", "nightvisionpadControl"),
    500: ("Key", "keyControl"),
    504: ("Lupus action", "dogControl"),
    505: ("Lupus action 2", "dogControl"),
    527: ("Fat Bob shockwave / squad weapon", "FatBobShockWaveControl, squadsFireWeapon"),
    532: ("Fireball", "mizarFireBallControl, girlControl, dogControl"),
    533: ("Sprint fire", "sprintPlayerFire"),
    534: ("Sprint fire 2", "sprintPlayerFire"),
    540: ("Sprint hit", "sprintHitBomb, sprintHitOilSlick"),
    545: ("Menu screen 2", "menuScreen"),
    552: ("Health pickup 2", "healthPickupControl"),
    553: ("Health pickup 3", "healthPickupControl"),
    554: ("Health pickup 4", "healthPickupControl"),
}


def song_levels(source: RomSource) -> dict[int, tuple[str, ...]]:
    """Which levels play each song (level record byte +0x72; 0 means none)."""
    rom = source.data
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, 31)
    records = rom[start:end]
    table_start, table_end = _asset_range(lut, 30)
    offsets = struct.unpack(f">{(table_end - table_start) // 4}I", rom[table_start:table_end])
    usage: dict[int, list[str]] = {}
    for entry in list_levels(source):
        offset = offsets[entry.index]
        song = records[offset + MUSIC_FIELD_OFFSET]
        if song:
            usage.setdefault(song, []).append(entry.name)
    return {song: tuple(names) for song, names in usage.items()}


def song_name(song_id: int, levels: dict[int, tuple[str, ...]] | None = None) -> str:
    """The best available name: the listed name, else the first level that plays it."""
    if song_id in SONG_NAMES:
        return SONG_NAMES[song_id]
    users = (levels or {}).get(song_id)
    if users:
        return f"Music of {users[0]}" + (f" (+{len(users) - 1})" if len(users) > 1 else "")
    return ""


def song_note(song_id: int) -> str:
    if song_id in SONG_NAMES:
        return "name from the community song list; confirmed against the ROM (VERIFIED)"
    return "no listed name; derived from the levels that play it (LIKELY)"


def sfx_label(sound_id: int) -> str:
    entry = SFX_LABELS.get(sound_id)
    return entry[0] if entry else ""


__all__ = ["SFX_LABELS", "SONG_NAMES", "sfx_label", "song_levels", "song_name", "song_note"]
