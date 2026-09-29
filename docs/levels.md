# The Levels tab

The **Levels** tab lists the 412 named levels in the ROM and shows the textured
geometry of each one.

## Using it

Type a name or a level number into the search box, or sort by level number, name
or geometry block. Click a level to see it. Drag to orbit, middle-drag to pan and
scroll to zoom. The panel shows the level's name, number, geometry block, other
levels that use the same geometry, face and vertex counts, segments and how many
of its textures Forge decoded.

Several levels share one geometry block: cut-scene versions, night versions and
multiplayer variants of a level point at the same block, so they look identical
here. The **Same geometry** line lists them.

## What is shown

Only the level's static world geometry with its textures. Not shown yet: objects
and enemies, lighting and vertex colours, sky, water, collision, and any
per-level texture animation. Some materials use plain grey or a flat colour
where the game blends or scrolls them. Level geometry uses the same 3D view as
the Models tab.

## How it is read (evidence)

| Fact | Status |
|---|---|
| Name records are 0x118 bytes each in asset 31, indexed by asset 30; the u16 at +0x54 is the geometry block number. All 301 blocks are used exactly once or more. | VERIFIED (every block covered, names match block sizes and shared variants) |
| Blocks are the 301 compressed entries of asset 37, indexed by asset 36. | VERIFIED (all decode) |
| Block layout: header offsets, 8-byte texture records, 0x48-byte segments, 16-byte batches, 16-byte triangles, 10-byte vertices. Triangle indices are relative to their batch. | VERIFIED (all 2,016 segments contiguous, 1.3 million indices in range) |
| Texture number at record bytes 2-3, looked up in asset 1 and read from asset 0; width and height match the record in 99% of cases. | VERIFIED |
| UV scale of 32 units per texel. | LIKELY (same as models; looks right) |
| Meaning of batch flag bits, the remaining header tables, vertex colours. | UNKNOWN |

Of 11,422 texture references across all blocks, 10,811 decode; the rest use
formats the decoder does not know and are drawn grey.
