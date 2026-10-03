"""Level list and level geometry from the ROM's level assets.

Everything here is read straight from the verified US ROM:

* asset 30 / 31: offset table and 412 name records of 0x118 bytes each; the
  record starts with the level's name and holds the geometry block number as a
  big-endian u16 at +0x54 (several records share one block, for example the
  cut-scene variants of a level);
* asset 36 / 37: offset table and the compressed geometry blocks;
* asset 1 / 0: the texture table and texture data pool that block texture
  records point into (record bytes 2-3 are the texture number, bytes 4-5 the
  width and height).

Block layout (all big-endian): a header of offsets, 8-byte texture records,
0x48-byte segments, and per segment 16-byte batch entries, 16-byte triangles
and 10-byte vertices. Triangle vertex indices are relative to the vertex range
of the batch they belong to. Vertex colours are read but not drawn.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache

from jfg_forge.core.model_parser import _asset_lut, _asset_range, decompress_texture_container
from jfg_forge.core.prop_bank import decode_prop_block
from jfg_forge.core.rom_source import RomSource
from jfg_forge.core.texture_formats import decode_model_texture_frame, decode_model_texture_lenient

NAME_TABLE_ASSET = 30
NAME_RECORD_ASSET = 31
GEOMETRY_TABLE_ASSET = 36
GEOMETRY_DATA_ASSET = 37
TEXTURE_TABLE_ASSET = 1
TEXTURE_DATA_ASSET = 0

NAME_RECORD_SIZE = 0x118
BLOCK_FIELD_OFFSET = 0x54
SEGMENT_STRIDE = 0x48
NO_TEXTURE = 0xFF
HIDDEN_BATCH_FLAG = 0x400


@dataclass(frozen=True)
class LevelEntry:
    index: int
    name: str
    block_id: int
    shared_with: tuple[int, ...] = ()


@dataclass(frozen=True)
class LevelTexture:
    index: int
    texture_id: int
    width: int
    height: int
    rgba: bytes | None
    format_name: str | None


@dataclass(frozen=True)
class LevelBatch:
    first_vertex: int
    vertex_count: int
    texture_index: int | None
    flags: int

    @property
    def hidden(self) -> bool:
        """Batches with flag 0x400 are helper surfaces the game does not draw.

        Same bit as a model group's "runtime skipped" flag. Every batch that uses the
        game's purple placeholder texture has it (and only 1% of the others do).
        """
        return bool(self.flags & HIDDEN_BATCH_FLAG)


@dataclass(frozen=True)
class LevelGeometry:
    block_id: int
    positions: tuple[tuple[float, float, float], ...]
    uvs: tuple[tuple[float, float], ...]
    colors: tuple[tuple[float, float, float], ...]
    batches: tuple[LevelBatch, ...]
    textures: tuple[LevelTexture, ...]
    segments: int
    source_vertices: int

    @property
    def faces(self) -> int:
        return len(self.positions) // 3

    @property
    def hidden_faces(self) -> int:
        return sum(batch.vertex_count for batch in self.batches if batch.hidden) // 3

    @property
    def decoded_textures(self) -> int:
        return sum(texture.rgba is not None for texture in self.textures)


class LevelDataError(ValueError):
    pass


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _s16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]


def _asset(rom: bytes, lut: tuple[int, ...], index: int) -> bytes:
    start, end = _asset_range(lut, index)
    return rom[start:end]


def _words(data: bytes) -> tuple[int, ...]:
    return struct.unpack(f">{len(data) // 4}I", data[: len(data) // 4 * 4])


def list_levels(source: RomSource) -> tuple[LevelEntry, ...]:
    """All 412 named levels with the geometry block each one uses."""
    rom = source.data
    lut = _asset_lut(rom)
    offsets = _words(_asset(rom, lut, NAME_TABLE_ASSET))
    records = _asset(rom, lut, NAME_RECORD_ASSET)
    raw: list[tuple[str, int]] = []
    for offset in offsets:
        if offset == 0xFFFFFFFF:  # end marker; the words after it are padding
            break
        if offset + NAME_RECORD_SIZE > len(records):
            continue
        record = records[offset : offset + NAME_RECORD_SIZE]
        end = record.index(0) if 0 in record else 0x14
        raw.append((record[:end].decode("latin-1").strip(), _u16(record, BLOCK_FIELD_OFFSET)))
    users: dict[int, list[int]] = {}
    for index, (_, block_id) in enumerate(raw):
        users.setdefault(block_id, []).append(index)
    return tuple(
        LevelEntry(
            index=index,
            name=name or f"Level {index}",
            block_id=block_id,
            shared_with=tuple(other for other in users[block_id] if other != index),
        )
        for index, (name, block_id) in enumerate(raw)
    )


@lru_cache(maxsize=2)
def _block_offsets(rom_id: int, table: bytes, data_length: int) -> tuple[int, ...]:
    offsets = sorted({word for word in _words(table) if word < data_length})
    offsets.append(data_length)
    return tuple(offsets)


def block_count(source: RomSource) -> int:
    rom = source.data
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, GEOMETRY_DATA_ASSET)
    table = _asset(rom, lut, GEOMETRY_TABLE_ASSET)
    return len(_block_offsets(id(rom), table, end - start)) - 1


def decode_block(source: RomSource, block_id: int) -> bytes:
    rom = source.data
    lut = _asset_lut(rom)
    start, end = _asset_range(lut, GEOMETRY_DATA_ASSET)
    table = _asset(rom, lut, GEOMETRY_TABLE_ASSET)
    offsets = _block_offsets(id(rom), table, end - start)
    if not 0 <= block_id < len(offsets) - 1:
        raise LevelDataError(f"Level geometry block {block_id} does not exist.")
    raw = rom[start + offsets[block_id] : start + offsets[block_id + 1]]
    return decode_prop_block(raw)[1]


def _load_texture(
    rom: bytes,
    pool_range: tuple[int, int],
    table: tuple[int, ...],
    index: int,
    record: bytes,
) -> LevelTexture:
    texture_id = _u16(record, 2)
    width, height = record[4], record[5]
    rgba: bytes | None = None
    format_name: str | None = None
    try:
        data_start, data_end = pool_range
        start, end = data_start + table[texture_id], data_start + table[texture_id + 1]
        if end > data_end or end - start < 32:
            raise LevelDataError("texture outside the pool")
        binary = decompress_texture_container(rom, start + 32)
        try:
            decoded = decode_model_texture_frame(binary)
        except ValueError:  # mipmap tails, missing strides: decode the base image instead
            decoded = decode_model_texture_lenient(binary)
        width, height = decoded.header.width, decoded.header.height
        rgba, format_name = decoded.rgba, decoded.format_name
    except Exception:  # unsupported format or damaged container: leave it undecoded
        pass
    return LevelTexture(index, texture_id, width, height, rgba, format_name)


def load_level_geometry(source: RomSource, block_id: int) -> LevelGeometry:
    """Decode one geometry block into flat triangle lists grouped by batch."""
    rom = source.data
    lut = _asset_lut(rom)
    block = decode_block(source, block_id)
    if len(block) < 0x30:
        raise LevelDataError("Level geometry block is too short.")
    texture_offset, segment_offset = _u32(block, 0), _u32(block, 4)
    texture_count, segment_count = _s16(block, 0x18), _s16(block, 0x1A)

    pool_range = _asset_range(lut, TEXTURE_DATA_ASSET)
    table = _words(_asset(rom, lut, TEXTURE_TABLE_ASSET))
    textures = tuple(
        _load_texture(rom, pool_range, table, index, block[texture_offset + index * 8 : texture_offset + index * 8 + 8])
        for index in range(max(texture_count, 0))
    )
    pool = {texture.index: texture for texture in textures}

    positions: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    colors: list[tuple[float, float, float]] = []
    batches: list[LevelBatch] = []
    source_vertices = 0
    for segment in range(max(segment_count, 0)):
        base = segment_offset + segment * SEGMENT_STRIDE
        vertex_offset, triangle_offset, _, batch_offset = struct.unpack_from(">4I", block, base)
        vertex_total = _s16(block, base + 0x24)
        batch_total = _s16(block, base + 0x28)
        source_vertices += vertex_total
        entries = [
            struct.unpack_from(">BBHHHHHI", block, batch_offset + index * 16)
            for index in range(batch_total + 1)
        ]
        for index in range(batch_total):
            entry, following = entries[index], entries[index + 1]
            texture = entry[0]
            first_vertex = len(positions)
            first_face, last_face = entry[5], following[5]
            vertex_base = entry[4]
            for face in range(first_face, last_face):
                triangle = triangle_offset + face * 16
                corner_indices = block[triangle + 1 : triangle + 4]
                raw_uv = struct.unpack_from(">6h", block, triangle + 4)
                texture_asset = pool.get(texture)
                width = texture_asset.width if texture_asset else 32
                height = texture_asset.height if texture_asset else 32
                for corner in range(3):
                    at = vertex_offset + (vertex_base + corner_indices[corner]) * 10
                    x, y, z = struct.unpack_from(">3h", block, at)
                    positions.append((float(x), float(y), float(z)))
                    red, green, blue = block[at + 6 : at + 9]
                    colors.append((red / 255.0, green / 255.0, blue / 255.0))
                    uvs.append((
                        raw_uv[corner * 2] / (32 * width),
                        1.0 - raw_uv[corner * 2 + 1] / (32 * height),
                    ))
            count = len(positions) - first_vertex
            if count:
                batches.append(
                    LevelBatch(
                        first_vertex=first_vertex,
                        vertex_count=count,
                        texture_index=None if texture == NO_TEXTURE or texture not in pool else texture,
                        flags=entry[7],
                    )
                )
    if not positions:
        raise LevelDataError("This level block has no drawable triangles.")
    return LevelGeometry(
        block_id=block_id,
        positions=tuple(positions),
        uvs=tuple(uvs),
        colors=tuple(colors),
        batches=tuple(batches),
        textures=textures,
        segments=max(segment_count, 0),
        source_vertices=source_vertices,
    )
