from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_animation import write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Boy animation runtime selection, timing, blend, and overrides.")
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = write_report(args.rom, args.output)
    print(f"Wrote {args.output}")
    print(f"Pinned instructions checked: {report['code_evidence']['checked_instruction_count']}")
    print(f"ROM SHA-1: {report['rom']['sha1']}")


if __name__ == "__main__":
    main()
