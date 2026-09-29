# The Textures tab

The **Textures** tab is a browsable texture bank: all 7,320 textures in the ROM,
with a preview, size and format, the models and levels that use each one, and
PNG export.

## Using it

Search by name, by number (for example `A2715`) or by the model or level that
uses a texture. Filter by bank, by decoded or not decoded, or by used and unused,
and sort by number, name or size. Click a texture to see it, step through
animated textures with the **Frame** box, and use **Export PNG...** for one
texture or **Export shown list as PNG files...** for everything currently shown
(after filtering). Files are named like `A2715_Forest_Sequence_Start.png`.

The list appears at once. The names are filled in a moment later, once Forge has
read every model and level to find where each texture is used.

## Names

**The ROM stores no texture names.** Forge derives a name from usage: the first
model that uses the texture, otherwise the first level, followed by `+N` for the
other users and the size, for example `Forest First +7 · 32×64`. Textures nothing
uses are called `Unused`. Treat the names as labels, not the game's own names.
The full list of users is shown for each texture.

## Banks

| Bank | Table / data assets | Used by |
|---|---|---|
| A | 1 / 0 (6,667 textures) | levels, and models whose texture id has the high bit set |
| B | 3 / 2 (659 textures) | models without the high bit |

## Decoding and limits

7,193 of 7,320 textures decode (RGBA32, RGBA16 and IA8). The strict decoder that
handles most is VERIFIED against reference images for RGBA16. Textures that carry
mipmap bytes after the pixels, or have no stride in their header (about 760),
decode through a lenient path that shows the base image of each frame; that path
is LIKELY, not VERIFIED. About 117 textures use other N64 formats (numbers 2, 3,
4 and 6) that are not decoded yet and are marked `[not decoded]`, and four
containers are damaged or use another compression marker.
