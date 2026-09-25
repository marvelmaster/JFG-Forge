#!/usr/bin/env python3
"""Analyze one immutable SceneRipper capture against US Prop 220 Boy."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jfg_re.scene_ripper_glr import build_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--boy", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--textured-report", type=Path, required=True)
    parser.add_argument("--verified-texture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifacts = build_artifacts(args.capture_dir, args.boy, args.rom, args.textured_report, args.verified_texture_root)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        path = args.output / name
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing output: {path}")
        path.write_bytes(data)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
