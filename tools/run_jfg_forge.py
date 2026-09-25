"""Repository-local launcher for JFG Forge."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from jfg_forge.app import main
except ModuleNotFoundError as error:
    if error.name in {"PySide6", "OpenGL", "numpy"}:
        raise SystemExit(
            f"Missing JFG Forge dependency {error.name!r}. "
            "Install the project dependencies with: python -m pip install -e ."
        ) from None
    raise


raise SystemExit(main())
