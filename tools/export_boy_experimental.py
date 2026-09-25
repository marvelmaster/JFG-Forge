#!/usr/bin/env python3
"""Export the pinned US Prop 220 Boy as an experimental static raw mesh."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_export import BoyExportError, export_boy
from jfg_re.props import RomIdentityError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boy", type=Path, required=True, help="Read-only path to canonical 0220_Boy.bin")
    parser.add_argument("--rom", type=Path, required=True, help="Read-only path to the verified US Z64 ROM")
    parser.add_argument("--texture-manifest", type=Path, required=True, help="Existing verified RGBA16 textures-manifest.json")
    parser.add_argument("--output", type=Path, required=True, help="New output directory under jfg-re/data/generated")
    args = parser.parse_args()
    generated_root = (PROJECT_ROOT / "data" / "generated").resolve()
    output = args.output.resolve()
    if output.parent != generated_root:
        parser.error("--output must be one new direct child of jfg-re/data/generated")
    try:
        report = export_boy(args.boy, args.rom, args.texture_manifest, output)
    except (OSError, FileExistsError, BoyExportError, RomIdentityError) as error:
        print(f"Boy export aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), **report["counts"], **{
        "runtime_texture_ids_resolved": report["texture_resolution"]["runtime_texture_ids_resolved"],
        "verified_rgba16_matches": report["texture_resolution"]["verified_rgba16_matches"],
    }}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
