from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_capture import import_capture, report_bytes
from jfg_re.props import validate_rom_identity


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one Boy runtime capture against the pinned offline decoder.")
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--boy", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    identity = validate_rom_identity(args.rom)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    report = import_capture(args.capture, identity.path.read_bytes(), args.boy.resolve(strict=True).read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(report_bytes(report))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
