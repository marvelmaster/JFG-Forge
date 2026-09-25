#!/usr/bin/env python3
"""Trace US JFG object 0xF7 / behaviour 0x59 to its actual model."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from jfg_re.boy_export import BoyExportError
from jfg_re.boy_hand_object_link import analyze
from jfg_re.props import RomIdentityError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--cluster", type=Path, required=True, help="Read-only pinned Prop 343")
    parser.add_argument("--junohand", type=Path, required=True, help="Read-only pinned Prop 309")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != (PROJECT_ROOT / "data" / "generated").resolve():
        parser.error("--output must be one new direct child of jfg-re/data/generated")
    try:
        report = analyze(args.rom, args.cluster, args.junohand, output)
    except (OSError, FileExistsError, BoyExportError, RomIdentityError) as error:
        print(f"Boy object-link analysis aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), "object_chain": report["object_chain"],
                      "diagnostic_obj_created": report["diagnostic_obj_created"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
