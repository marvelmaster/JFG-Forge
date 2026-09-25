"""One-asset Boy structure experiment. This is not a model format decoder.

The input is pinned to the verified US prop 220 SHA-256. The OBJ uses only
proposed XYZ and local triangle indices; it does not establish bone or
material semantics. No UV, skinning, or animation is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path


BOY_SHA256 = "2cd9e008852355d8191cf11e383de833b7ab1ea2814b3dd71583c8aa104f0baf"
BOY_SIZE = 0x5170
GROUP_START, TRIANGLE_START, VERTEX_START, RECORDS_END = 0x118, 0x648, 0x26C8, 0x4090
OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "generated"


def be16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def be32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def inspect(data: bytes) -> tuple[dict, list[str]]:
    if len(data) != BOY_SIZE or hashlib.sha256(data).hexdigest() != BOY_SHA256:
        raise ValueError("Input is not the pinned US Boy prop 220")
    if data[:4] != b"Boy\0":
        raise ValueError("Boy name bytes differ")
    if [be32(data, n) for n in (0x18, 0x1C, 0x20, 0x24, 0x30, 0x34, 0x48)] != [
        0x88, 0x26C8, 0x648, 0x118, 0x4090, 0x41E8, BOY_SIZE
    ]:
        raise ValueError("Expected Boy section boundary words differ")

    groups = []
    for i in range(83):
        at = GROUP_START + i * 16
        groups.append({
            "first_byte": data[at],
            "vertex_start": be16(data, at + 6),
            "triangle_start": be16(data, at + 8),
        })
    if groups[0]["vertex_start"] != 0 or groups[0]["triangle_start"] != 0:
        raise ValueError("Group table does not start at zero")
    if (groups[-1]["vertex_start"], groups[-1]["triangle_start"]) != (660, 520):
        raise ValueError("Group sentinel does not terminate at 660/520")
    if any(groups[i][k] >= groups[i + 1][k] for i in range(82) for k in ("vertex_start", "triangle_start")):
        raise ValueError("Group starts are not strictly increasing")

    vertices = [struct.unpack_from(">hhhBBBB", data, VERTEX_START + i * 10) for i in range(660)]
    triangle_count = (VERTEX_START - TRIANGLE_START) // 16
    if triangle_count != 520 or VERTEX_START + 660 * 10 != RECORDS_END:
        raise ValueError("Record sections do not meet their boundaries")

    out_of_range = 0
    degenerate = 0
    uv_by_vertex: dict[int, set[tuple[int, int]]] = defaultdict(set)
    triangle_flags = Counter()
    lines = [
        "# Boy prop 220, experimental static geometry reconstruction",
        "# HYPOTHESIS: proposed s16 XYZ and group-local triangle indices",
        "# Units, orientation, materials, UV scale, bones and skinning UNKNOWN",
    ]
    for x, y, z, *_ in vertices:
        lines.append(f"v {x} {y} {z}")
    used_vertices: set[int] = set()
    for group_number in range(82):
        group, following = groups[group_number:group_number + 2]
        first, last = group["triangle_start"], following["triangle_start"]
        base = group["vertex_start"]
        group_size = following["vertex_start"] - base
        lines.append(f"g group_{group_number:02d}")
        for triangle_number in range(first, last):
            at = TRIANGLE_START + triangle_number * 16
            flag, *local = data[at:at + 4]
            triangle_flags[flag] += 1
            if any(index >= group_size for index in local):
                out_of_range += 1
                continue
            absolute = [base + index for index in local]
            used_vertices.update(absolute)
            for corner, vertex_index in enumerate(absolute):
                uv_by_vertex[vertex_index].add(struct.unpack_from(">hh", data, at + 4 + corner * 4))
            a, b, c = (vertices[index][:3] for index in absolute)
            ab = [b[i] - a[i] for i in range(3)]
            ac = [c[i] - a[i] for i in range(3)]
            cross = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            if cross == (0, 0, 0):
                degenerate += 1
                continue
            lines.append("f " + " ".join(str(index + 1) for index in absolute))

    if out_of_range or len(used_vertices) != 660:
        raise ValueError("Triangle/group links are inconsistent")
    if sum(triangle_flags.values()) != 520:
        raise ValueError("Triangle count differs")
    axis_ranges = [
        [min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices)]
        for axis in range(3)
    ]
    skeleton_candidate = []
    for i in range(21):
        at = 0x4090 + i * 16
        skeleton_candidate.append({
            "record": i,
            "byte_8_parent_candidate": data[at + 8],
            "byte_10_id_candidate": data[at + 10],
        })
    report = {
        "asset": "Boy", "prop_id": 220, "sha256": BOY_SHA256, "size": BOY_SIZE,
        "status": "HYPOTHESIS: static geometry layout; VERIFIED: raw bytes and arithmetic",
        "group_records_including_sentinel": 83,
        "group_count": 82,
        "triangle_records": triangle_count,
        "vertex_records": len(vertices),
        "candidate_xyz_axis_ranges": axis_ranges,
        "triangle_flags": {f"0x{k:02x}": v for k, v in sorted(triangle_flags.items())},
        "triangle_indices_out_of_group_range": out_of_range,
        "vertices_referenced": len(used_vertices),
        "degenerate_candidate_triangles": degenerate,
        "obj_faces_emitted": triangle_count - degenerate,
        "vertices_with_multiple_corner_uv_pairs": sum(len(values) > 1 for values in uv_by_vertex.values()),
        "candidate_bone_records": skeleton_candidate,
    }
    return report, lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boy", type=Path, required=True, help="Read-only path to canonical 0220_Boy.bin")
    parser.add_argument("--output-name", default="boy-study", help="New subdirectory under data/generated")
    args = parser.parse_args()
    if args.output_name in ("", ".", "..") or Path(args.output_name).name != args.output_name:
        parser.error("output-name must be one new directory name")
    try:
        report, lines = inspect(args.boy.read_bytes())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = OUTPUT_ROOT / args.output_name
    output.mkdir(exist_ok=False, parents=False)
    (output / "boy-structure-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "boy-static-hypothesis.obj").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(json.dumps({"output": str(output), **{k: report[k] for k in (
        "group_count", "triangle_records", "vertex_records", "obj_faces_emitted",
        "triangle_indices_out_of_group_range", "degenerate_candidate_triangles"
    )}}, indent=2))


if __name__ == "__main__":
    main()
