#!/usr/bin/env python3
"""Emit pinned Boy transform metadata without decoding or applying animation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_export import BoyExportError
from jfg_re.boy_transform_analysis import write_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boy", type=Path, required=True, help="Read-only canonical 0220_Boy.bin")
    parser.add_argument("--output", type=Path, required=True, help="New direct child of jfg-re/data/generated")
    args = parser.parse_args()
    generated_root = (PROJECT_ROOT / "data" / "generated").resolve()
    output = args.output.resolve()
    if output.parent != generated_root:
        parser.error("--output must be one new direct child of jfg-re/data/generated")
    try:
        report = write_artifacts(args.boy, output)
    except (OSError, FileExistsError, BoyExportError) as error:
        print(f"Boy transform analysis aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), **report["counts"], **report["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
