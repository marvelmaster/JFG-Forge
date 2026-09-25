"""Verified extractor for the Jet Force Gemini US prop bank.

The bank layout is verified for the US Z64 ROM identified by ``EXPECTED_SHA1``.
This module only interprets the outer compression container. It does not assign
meaning to fields inside a decompressed prop.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import struct
from typing import Any
import zlib


EXPECTED_ROM_SIZE = 33_554_432
EXPECTED_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
PROP_TABLE_OFFSET = 0x139B800
PROP_TABLE_ENTRIES = 905
PROP_COUNT = 904
PROP_DATA_BASE = 0x139C630
COMPRESSION_MARKER = 0x09


class RomIdentityError(ValueError):
    """Raised when a ROM is not the verified US source ROM."""


class PropExtractionError(ValueError):
    """Raised when verified prop-bank container assumptions do not hold."""


@dataclass(frozen=True)
class RomIdentity:
    path: Path
    size_bytes: int
    sha1: str


def sha256_file(path: Path) -> str:
    """Return a lower-case SHA-256 digest without loading the file at once."""
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_rom_identity(rom_path: Path) -> RomIdentity:
    """Validate the required ROM size and SHA-1 before any extraction output exists."""
    rom_path = rom_path.resolve(strict=True)
    size_bytes = rom_path.stat().st_size
    if size_bytes != EXPECTED_ROM_SIZE:
        raise RomIdentityError(
            f"Unexpected ROM size: {size_bytes:,}; expected {EXPECTED_ROM_SIZE:,} bytes."
        )

    digest = sha1()
    with rom_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha1 = digest.hexdigest()
    if actual_sha1 != EXPECTED_SHA1:
        raise RomIdentityError(
            f"Unexpected ROM SHA-1: {actual_sha1}; expected {EXPECTED_SHA1}."
        )
    return RomIdentity(rom_path, size_bytes, actual_sha1)


def parse_offset_table(table_bytes: bytes) -> tuple[int, ...]:
    """Parse and validate the 905-entry Big-Endian prop offset table."""
    expected_size = PROP_TABLE_ENTRIES * 4
    if len(table_bytes) != expected_size:
        raise PropExtractionError(
            f"Offset table is {len(table_bytes)} bytes; expected {expected_size}."
        )
    offsets = struct.unpack(f">{PROP_TABLE_ENTRIES}I", table_bytes)
    if any(next_offset < offset for offset, next_offset in zip(offsets, offsets[1:])):
        raise PropExtractionError("Prop offsets are not monotonically non-decreasing.")
    if any(offset % 16 for offset in offsets):
        raise PropExtractionError("Prop offsets are expected to be 16-byte aligned.")
    return offsets


def decode_prop_block(block: bytes) -> tuple[int, bytes]:
    """Decode one 5-byte-container raw-Deflate prop block."""
    if len(block) < 5:
        raise PropExtractionError("Prop block is shorter than its 5-byte container header.")
    expected_size = struct.unpack_from("<I", block)[0]
    marker = block[4]
    if marker != COMPRESSION_MARKER:
        raise PropExtractionError(
            f"Unexpected compression marker 0x{marker:02X}; expected 0x{COMPRESSION_MARKER:02X}."
        )
    try:
        decompressed = zlib.decompress(block[5:], wbits=-15)
    except zlib.error as error:
        raise PropExtractionError(f"Raw-Deflate decompression failed: {error}") from error
    if len(decompressed) != expected_size:
        raise PropExtractionError(
            f"Decompressed size {len(decompressed)} does not match header size {expected_size}."
        )
    return expected_size, decompressed


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("._")
    return safe or "unnamed"


def load_reference_names(reference_index: Path | None) -> dict[int, str]:
    """Load known prop names only from the prior canonical reference index."""
    if reference_index is None:
        return {}
    records = json.loads(reference_index.read_text(encoding="utf-8"))
    names: dict[int, str] = {}
    for record in records:
        prop_id = record.get("id")
        name = record.get("name")
        if isinstance(prop_id, int) and isinstance(name, str) and name:
            names[prop_id] = name
    return names


def _reference_candidates(reference_root: Path, prop_id: int) -> list[Path]:
    """Find prior canonical candidates by their stable four-digit prop ID."""
    pattern = f"{prop_id:04d}_*.bin"
    return sorted(reference_root.rglob(pattern))


def _compare_reference(
    reference_root: Path | None, prop_id: int, output_sha256: str
) -> dict[str, Any]:
    if reference_root is None:
        return {"checked": False, "match": None, "candidate_count": 0, "matches": []}
    candidates = _reference_candidates(reference_root, prop_id)
    matches = [
        candidate.relative_to(reference_root).as_posix()
        for candidate in candidates
        if sha256_file(candidate) == output_sha256
    ]
    return {
        "checked": True,
        "match": bool(matches),
        "candidate_count": len(candidates),
        "matches": matches,
    }


def extract_props(
    rom_path: Path,
    output_dir: Path,
    *,
    reference_index: Path | None = None,
    reference_root: Path | None = None,
) -> dict[str, Any]:
    """Extract all 904 verified props into a new, non-existing output directory.

    The output directory is intentionally required not to exist, preventing an
    accidental overwrite of prior runs. Reference data is read-only and is used
    only for names and SHA-256 comparison.
    """
    identity = validate_rom_identity(rom_path)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to write into existing output directory: {output_dir}")
    if (reference_index is None) != (reference_root is None):
        raise ValueError("reference_index and reference_root must be provided together.")
    if reference_index is not None:
        reference_index = reference_index.resolve(strict=True)
        reference_root = reference_root.resolve(strict=True)

    names = load_reference_names(reference_index)
    with identity.path.open("rb") as source:
        source.seek(PROP_TABLE_OFFSET)
        offsets = parse_offset_table(source.read(PROP_TABLE_ENTRIES * 4))
        source.seek(0)
        rom = source.read()

    output_dir.mkdir(parents=True)
    bins_dir = output_dir / "bins"
    bins_dir.mkdir()
    records: list[dict[str, Any]] = []
    deviations: list[dict[str, Any]] = []

    for prop_id in range(PROP_COUNT):
        relative_offset = offsets[prop_id]
        next_relative_offset = offsets[prop_id + 1]
        absolute_offset = PROP_DATA_BASE + relative_offset
        compressed_size = next_relative_offset - relative_offset
        if compressed_size < 5 or absolute_offset + compressed_size > len(rom):
            raise PropExtractionError(f"Invalid range for prop {prop_id} at 0x{absolute_offset:X}.")
        expected_size, data = decode_prop_block(rom[absolute_offset : absolute_offset + compressed_size])
        name = names.get(prop_id)
        filename = f"{prop_id:04d}_{_safe_name(name) if name else 'unnamed'}.bin"
        output_path = bins_dir / filename
        output_path.write_bytes(data)
        output_sha256 = sha256(data).hexdigest()
        comparison = _compare_reference(reference_root, prop_id, output_sha256)
        if comparison["checked"] and not comparison["match"]:
            deviations.append(
                {
                    "prop_id": prop_id,
                    "kind": "reference_sha256_mismatch_or_missing",
                    "reference_candidate_count": comparison["candidate_count"],
                    "output_sha256": output_sha256,
                }
            )
        records.append(
            {
                "prop_id": prop_id,
                "table_index": prop_id,
                "name": name,
                "relative_offset": relative_offset,
                "absolute_rom_offset": absolute_offset,
                "compressed_size": compressed_size,
                "declared_decompressed_size": expected_size,
                "decompressed_size": len(data),
                "sha256": output_sha256,
                "output_path": f"bins/{filename}",
                "reference": comparison,
            }
        )

    report = {
        "schema_version": 1,
        "status": "VERIFIED",
        "scope": "Prop-bank outer container only; decompressed prop semantics are not asserted.",
        "rom": {"path": str(identity.path), "size_bytes": identity.size_bytes, "sha1": identity.sha1},
        "prop_table": {
            "offset": PROP_TABLE_OFFSET,
            "entry_count": PROP_TABLE_ENTRIES,
            "prop_count": PROP_COUNT,
            "data_base": PROP_DATA_BASE,
            "end_offset": offsets[-1],
            "end_absolute_rom_offset": PROP_DATA_BASE + offsets[-1],
            "end_offset_treated_as_prop": False,
        },
        "validation": {
            "successful_decompressions": len(records),
            "declared_size_matches": sum(
                record["declared_decompressed_size"] == record["decompressed_size"] for record in records
            ),
            "reference_hash_matches": sum(record["reference"]["match"] is True for record in records),
            "reference_checked": reference_root is not None,
            "deviations": deviations,
        },
    }
    (output_dir / "props-manifest.json").write_text(
        json.dumps({"schema_version": 1, "props": records}, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "extraction-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report
