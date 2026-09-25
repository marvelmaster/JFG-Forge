"""Compatibility entry point for the first real Boy runtime capture.

The reusable implementation now lives in :mod:`jfg_re.boy_runtime_capture`.
This file preserves the original index-19 research command and regression
fixture without retaining an independent capture parser.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_capture import validate_capture_directory  # noqa: E402
from jfg_re.props import validate_rom_identity  # noqa: E402


CAPTURE_DIR = PROJECT_ROOT / "research" / "boy" / "runtime-captures" / "index19-id1022"
BOY_PATH = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
ROM_PATH = WORKSPACE_ROOT / "rom" / "jetforcegemini.z64"


def analyze(
    capture_dir: Path = CAPTURE_DIR,
    rom_path: Path = ROM_PATH,
    boy_path: Path = BOY_PATH,
) -> dict[str, Any]:
    identity = validate_rom_identity(rom_path)
    return validate_capture_directory(
        capture_dir,
        identity.path.read_bytes(),
        boy_path.resolve(strict=True).read_bytes(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, default=CAPTURE_DIR)
    parser.add_argument("--rom", type=Path, default=ROM_PATH)
    parser.add_argument("--boy", type=Path, default=BOY_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = (json.dumps(analyze(args.capture_dir, args.rom, args.boy), indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output is None:
        sys.stdout.buffer.write(encoded)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)


if __name__ == "__main__":
    main()
