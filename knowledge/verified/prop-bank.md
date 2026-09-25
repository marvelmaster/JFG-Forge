# Prop-bank outer container

Status: VERIFIED

Evidence: the verified US Z64 ROM, the reproducible extractor, and the
canonical 904 reference prop binaries agree byte-for-byte after decompression.

| Field | Value |
| --- | --- |
| Offset table | `0x139B800` |
| Table entries | 905 Big-Endian 32-bit relative offsets |
| Data base | `0x139C630` |
| Extracted props | 904 |
| Final table entry | End offset only; never decoded as a prop |
| Container | 4-byte Little-Endian output size, `0x09`, Raw Deflate stream |

This finding only covers the outer bank container and verified extraction. It
does not assign meaning to fields inside decompressed prop data.
