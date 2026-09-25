#!/usr/bin/env python3
"""Export and validate only the verified JFG US RGBA16 texture format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.props import RomIdentityError
from jfg_re.textures_rgba16 import TextureValidationError, export_rgba16_textures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Explicit path to the verified US Z64 ROM.")
    parser.add_argument("--input-bins", type=Path, required=True, help="Read-only directory of verified TextureBins.")
    parser.add_argument("--reference-pngs", type=Path, required=True, help="Read-only directory of reference PNGs.")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; it must not exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = export_rgba16_textures(args.rom, args.input_bins, args.reference_pngs, args.output)
    except (FileNotFoundError, FileExistsError, NotADirectoryError, RomIdentityError, TextureValidationError) as error:
        print(f"Texture export aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report["validation"], indent=2))
    return 0 if not report["validation"]["deviation_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
