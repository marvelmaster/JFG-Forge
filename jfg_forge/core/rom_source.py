"""Validated, immutable source for the supported JFG US Z64 ROM."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Callable, Generic, TypeVar

from jfg_forge.core.prop_bank import (
    EXPECTED_ROM_SIZE,
    EXPECTED_SHA1,
    PROP_COUNT,
    PROP_DATA_BASE,
    PROP_TABLE_ENTRIES,
    PROP_TABLE_OFFSET,
    RomIdentity,
    RomIdentityError,
    decode_prop_block,
    parse_offset_table,
    validate_rom_identity,
)


Z64_BIG_ENDIAN_MAGIC = b"\x80\x37\x12\x40"


class RomLoadError(ValueError):
    """A selected file is not the supported, verified ROM."""


@dataclass(frozen=True, slots=True)
class RomSource:
    """Validated ROM identity and the exact bytes shared by Forge consumers."""

    identity: RomIdentity
    data: bytes

    @property
    def path(self) -> Path:
        return self.identity.path

    @property
    def display_name(self) -> str:
        return "Jet Force Gemini (USA)"

    def prop_bytes(self, prop_id: int) -> bytes:
        """Decompress one Prop from the verified ROM offset table."""
        if not 0 <= prop_id < PROP_COUNT:
            raise RomLoadError(f"Prop ID {prop_id} is outside the ROM Prop bank.")
        table_end = PROP_TABLE_OFFSET + PROP_TABLE_ENTRIES * 4
        offsets = parse_offset_table(self.data[PROP_TABLE_OFFSET:table_end])
        start = PROP_DATA_BASE + offsets[prop_id]
        end = PROP_DATA_BASE + offsets[prop_id + 1]
        _declared, decompressed = decode_prop_block(self.data[start:end])
        return decompressed


def open_rom_source(path: Path | str) -> RomSource:
    """Validate size, canonical Z64 byte order, and the verified full-ROM SHA-1."""
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
        size = resolved.stat().st_size
        if size != EXPECTED_ROM_SIZE:
            raise RomLoadError(
                f"Unsupported ROM size ({size:,} bytes); the supported US ROM is "
                f"{EXPECTED_ROM_SIZE:,} bytes."
            )
        with resolved.open("rb") as source:
            magic = source.read(4)
        if magic != Z64_BIG_ENDIAN_MAGIC:
            raise RomLoadError(
                "Unsupported ROM byte order or header. Select the canonical "
                "Z64 big-endian ROM. V64/N64 byte-swapped files are not supported."
            )
        identity = validate_rom_identity(resolved)
        data = resolved.read_bytes()
    except RomLoadError:
        raise
    except (OSError, RomIdentityError) as error:
        raise RomLoadError(f"Could not load the supported JFG ROM: {error}") from error

    # Check the bytes actually retained in memory too, avoiding a path-change
    # race between streaming identity validation and the subsequent read.
    if len(data) != EXPECTED_ROM_SIZE or sha1(data).hexdigest() != EXPECTED_SHA1:
        raise RomLoadError("The ROM changed while it was being loaded; please select it again.")
    return RomSource(identity=identity, data=data)


def as_rom_source(value: RomSource | Path | str) -> RomSource:
    """Keep explicit-path research APIs working while sharing GUI sources."""
    return value if isinstance(value, RomSource) else open_rom_source(value)


T = TypeVar("T")


class RomSession(Generic[T]):
    """Atomically replace active ROM-derived UI state after preparation succeeds."""

    def __init__(self) -> None:
        self.source: RomSource | None = None
        self.value: T | None = None

    def load(self, path: Path | str, prepare: Callable[[RomSource], T]) -> T:
        candidate = open_rom_source(path)
        prepared = prepare(candidate)
        self.source = candidate
        self.value = prepared
        return prepared
