from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jfg_re.boy_runtime_capture import validate_capture_directory
from jfg_re.props import validate_rom_identity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate one no-blend Boy runtime-capture directory against the reusable decoder."
    )
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--boy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    identity = validate_rom_identity(args.rom)
    boy = args.boy.resolve(strict=True).read_bytes()
    report = validate_capture_directory(args.capture_dir, identity.path.read_bytes(), boy)
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output = args.output.resolve()
    if output.exists() and output.read_bytes() != encoded:
        raise FileExistsError(f"Refusing to overwrite different existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    comparison = report["runtime_comparison_c"]
    print(
        f"Validated {comparison['matrices_with_max_error_at_most_1e-5']}/21 matrices; "
        f"max error {comparison['maximum_absolute_error']:.12g}"
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
