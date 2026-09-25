# RGBA16 texture container

Status: VERIFIED

The verified US-ROM extraction accepts only this observed texture container:

| Property | Verified value |
| --- | --- |
| Header size | 32 bytes |
| Width | Header byte 0 |
| Height | Header byte 1 |
| Format marker | Header bytes 2–3: `11 00` |
| Pixel-data length | Exactly `width * height * 2` bytes after the header |
| Pixel encoding | Big-Endian RGBA5551 / RGBA16 |
| Row correction | On odd rows, exchange the two-pixel halves of each complete four-pixel group |
| Verified reference set | 5,155 TextureBins and corresponding PNGs |

The decoder performs no Y flip. It does not establish support for RGBA32, CI,
IA, I, TLUT/palettes, mipmaps, or any other N64 texture format. Those formats
remain UNKNOWN.
