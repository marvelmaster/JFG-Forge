"""Application entry point for JFG Forge."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication, QMessageBox

from jfg_re.forge_data import load_boy
from jfg_re.forge_scene import evaluate_boy_scene
from jfg_re.vela_data import load_vela
from jfg_forge.main_window import MainWindow
from jfg_forge.render_data import model_information, prepare_render_data


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROM = PROJECT_ROOT.parent / "rom" / "jetforcegemini.z64"
DEFAULT_BOY = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0220_Boy.bin"
DEFAULT_VELA = PROJECT_ROOT / "data" / "generated" / "props-us-verified" / "bins" / "0218_Girl.bin"
DEFAULT_TEXTURES = PROJECT_ROOT / "data" / "generated" / "rgba16-us-verified" / "textures-manifest.json"


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open the JFG Forge character model viewer.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--boy", type=Path, default=DEFAULT_BOY)
    parser.add_argument("--vela", type=Path, default=DEFAULT_VELA)
    parser.add_argument("--textures", type=Path, default=DEFAULT_TEXTURES)
    return parser.parse_args(argv)


def _request_opengl_33() -> None:
    surface = QSurfaceFormat()
    surface.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    surface.setVersion(3, 3)
    surface.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface.setDepthBufferSize(24)
    surface.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(surface)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    _request_opengl_33()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("JFG Forge")
    try:
        boy = load_boy(arguments.boy, arguments.rom, arguments.textures)
        vela = load_vela(arguments.vela, arguments.rom, arguments.textures)
        scene = evaluate_boy_scene(boy, animation_index=0, time=0.0)
        render_data = prepare_render_data(scene)
        information = model_information(scene)
    except Exception as error:
        message = f"JFG Forge could not load its character assets:\n\n{error}"
        print(message, file=sys.stderr)
        QMessageBox.critical(None, "JFG Forge load error", message)
        return 1
    window = MainWindow(boy, vela, scene, render_data, information)
    window.show()
    return application.exec()


__all__ = ["main"]
