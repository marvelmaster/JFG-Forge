"""Catalogue and static loader for every model Prop in the ROM.

The ROM stores 904 Props.  Each starts with a header holding its name, so the
whole catalogue can be listed instantly.  A Prop can then be loaded as a static
model: props without joints are drawn as stored, and props with joints are drawn
in a *rest pose* (every joint at its stored offset from its parent, no
rotation).  A rest pose is an approximation for animated props, whose real
pose comes from their animation clips.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from jfg_forge.core.asset_types import ModelAsset
from jfg_forge.core.character_data import _normalize_model
from jfg_forge.core.compact_animation import _asset_bytes
from jfg_forge.core.model_parser import BoyExportError, parse_model
from jfg_forge.core.rom_source import RomSource, as_rom_source

PROP_COUNT = 904


@dataclass(frozen=True)
class PropEntry:
    prop_id: int
    name: str
    joints: int
    clips: int
    drawable: bool = True

    @property
    def animated(self) -> bool:
        return self.clips > 0

    @property
    def kind(self) -> str:
        if self.clips > 0:
            return "Animated (shown in rest pose)"
        if self.joints > 0:
            return "Static, with joints (shown in rest pose)"
        return "Static"


@dataclass(frozen=True)
class StaticModel:
    entry: PropEntry
    model: ModelAsset
    positions: tuple[tuple[float, float, float], ...]
    rest_pose: bool
    drawn_unknown_textures: int

    @property
    def faces(self) -> int:
        return self.model.active_face_count


def _clip_counter(rom: bytes):
    _start, _end, asset40 = _asset_bytes(rom, 40)

    def clips(prop_id: int) -> int:
        offset = (prop_id & ~3) * 2 + (prop_id & 3) * 2
        try:
            first, following = struct.unpack_from(">HH", asset40, offset)
        except struct.error:
            return 0
        return max((following >> 1) - (first >> 1), 0)

    return clips


def _has_triangles(data: bytes) -> bool:
    """True if any group the game draws holds triangle records (header data only)."""
    model = parse_model(data)
    following = (*model.groups[1:], model.sentinel)
    return any(
        next_group.triangle_start > group.triangle_start
        for group, next_group in zip(model.groups, following)
        if not group.runtime_skipped
    )


def list_props(rom_path: RomSource | Path) -> tuple[PropEntry, ...]:
    """Name, joint count and clip count of every Prop (fast: headers only)."""
    source = as_rom_source(rom_path)
    clips = _clip_counter(source.data)
    entries = []
    for prop_id in range(PROP_COUNT):
        data = source.prop_bytes(prop_id)
        name = data[:16].split(b"\0", 1)[0].decode("ascii", errors="replace")
        entries.append(
            PropEntry(
                prop_id,
                name or f"prop_{prop_id:04d}",
                data[0x4F],
                clips(prop_id),
                _has_triangles(data),
            )
        )
    return tuple(entries)


def _rest_translations(data: bytes) -> dict[int, tuple[float, float, float]]:
    """World offset of each joint with every rotation at zero."""
    count = data[0x4F]
    if count == 0:
        return {}
    start = struct.unpack_from(">I", data, 0x54)[0]
    world: dict[int, tuple[float, float, float]] = {}
    for index in range(count):
        offset = start + index * 16
        parent, joint = data[offset], data[offset + 1]
        local = struct.unpack_from(">fff", data, offset + 4)
        if parent == 0xFF:
            world[joint] = local
        elif parent in world:
            base = world[parent]
            world[joint] = (base[0] + local[0], base[1] + local[1], base[2] + local[2])
        else:
            raise BoyExportError(f"Joint {joint} lists parent {parent} before it exists.")
    return world


def load_static_model(rom_path: RomSource | Path, prop_id: int) -> StaticModel:
    """Load one Prop with its textures as a static (or rest-pose) model."""
    if not 0 <= prop_id < PROP_COUNT:
        raise KeyError(f"Prop {prop_id} is outside 0..{PROP_COUNT - 1}.")
    source = as_rom_source(rom_path)
    data = source.prop_bytes(prop_id)
    entry = _entry(source, prop_id)
    parsed = parse_model(data)
    model = _normalize_model(prop_id, data, parsed, source.data, None)
    if model.active_face_count == 0:
        raise BoyExportError(f"Prop {prop_id} {entry.name} has no drawable faces.")
    translations = _rest_translations(data)
    positions = []
    for vertex in model.render_mesh.vertices:
        x, y, z = vertex.position
        dx, dy, dz = translations.get(vertex.joint_id, (0.0, 0.0, 0.0))
        positions.append((x + dx, y + dy, z + dz))
    drawn_unknown = sum(
        1
        for texture in model.textures
        if not texture.supported
        and any(
            group.texture_index == texture.texture_index and not group.runtime_skipped
            for group in parsed.groups
        )
    )
    return StaticModel(entry, model, tuple(positions), bool(translations), drawn_unknown)


def _entry(source: RomSource, prop_id: int) -> PropEntry:
    data = source.prop_bytes(prop_id)
    name = data[:16].split(b"\0", 1)[0].decode("ascii", errors="replace")
    return PropEntry(
        prop_id,
        name or f"prop_{prop_id:04d}",
        data[0x4F],
        _clip_counter(source.data)(prop_id),
        _has_triangles(data),
    )


__all__ = [
    "PROP_COUNT",
    "PropEntry",
    "StaticModel",
    "list_props",
    "load_static_model",
]
