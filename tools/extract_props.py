#!/usr/bin/env python3
"""Command-line entry point for the verified JFG US prop-bank extractor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.props import PropExtractionError, RomIdentityError, extract_props


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Explicit path to the verified US Z64 ROM.")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; it must not exist.")
    parser.add_argument(
        "--reference-index", type=Path, required=True, help="Existing canonical extracted/index.json, read only."
    )
    parser.add_argument(
        "--reference-bins", type=Path, required=True, help="Existing canonical extracted directory, read only."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = extract_props(
            args.rom,
            args.output,
            reference_index=args.reference_index,
            reference_root=args.reference_bins,
        )
    except (FileNotFoundError, FileExistsError, ValueError, RomIdentityError, PropExtractionError) as error:
        print(f"Extraction aborted: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report["validation"], indent=2))
    return 0 if not report["validation"]["deviations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
