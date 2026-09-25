from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_overrides import report_bytes, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Boy's runtime animation override list and neutral-state limits.")
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = write_report(args.rom, args.output)
    digest = hashlib.sha256(report_bytes(report)).hexdigest()
    print(f"Wrote {args.output}")
    print(f"Conclusion: {report['conclusion']['code']}. {report['conclusion']['label']}")
    print(f"Pinned instructions checked: {report['code_evidence']['checked_instruction_count']}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
