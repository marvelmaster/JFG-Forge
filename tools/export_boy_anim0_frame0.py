#!/usr/bin/env python3
"""Export pinned Prop 220 Boy at JFG Animation 0, integer Frame 0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_anim0_frame0 import export_boy_anim0_frame0
from jfg_re.boy_export import BoyExportError
from jfg_re.props import RomIdentityError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boy", type=Path, required=True, help="Read-only canonical 0220_Boy.bin")
    parser.add_argument("--rom", type=Path, required=True, help="Read-only verified US Z64 ROM")
    parser.add_argument("--texture-manifest", type=Path, required=True, help="Existing VERIFIED RGBA16 manifest")
    parser.add_argument("--output", type=Path, required=True, help="New direct child of jfg-re/data/generated")
    args = parser.parse_args()
    generated_root = (PROJECT_ROOT / "data" / "generated").resolve()
    output = args.output.resolve()
    if output.parent != generated_root:
        parser.error("--output must be one new direct child of jfg-re/data/generated")
    try:
        report = export_boy_anim0_frame0(args.boy, args.rom, args.texture_manifest, output)
    except (OSError, FileExistsError, BoyExportError, RomIdentityError) as error:
        print(f"Boy Animation-0/Frame-0 export aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), **report["counts"], "bounding_boxes": report["bounding_boxes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
