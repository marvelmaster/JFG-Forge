#!/usr/bin/env python3
"""Diagnose the missing +X-side hand in pinned Boy anim0/frame0."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from jfg_re.boy_export import BoyExportError
from jfg_re.boy_missing_hand_analysis import analyze
from jfg_re.props import RomIdentityError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boy", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--junohand", type=Path, required=True, help="Read-only pinned Prop 309 evidence")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != (PROJECT_ROOT / "data" / "generated").resolve():
        parser.error("--output must be one new direct child of jfg-re/data/generated")
    try:
        report = analyze(args.boy, args.rom, args.junohand, output)
    except (OSError, FileExistsError, BoyExportError, RomIdentityError) as error:
        print(f"Boy missing-hand analysis aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), "missing_side": report["arm_comparison"]["missing_geometry_side"],
                      "triangle_accounting": report["triangle_accounting"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
