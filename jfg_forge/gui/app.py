"""Application entry point and user-selected ROM lifecycle for JFG Forge."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from jfg_forge.core.green_ant import load_greenant
from jfg_forge.core.character_data import load_boy, load_powerboy
from jfg_forge.core.scene import evaluate_boy_scene
from jfg_forge.core.lupus import load_lupus
from jfg_forge.core.powerdog import load_powerdog
from jfg_forge.core.rom_source import RomLoadError, RomSession, RomSource
from jfg_forge.core.vela import load_powergirl, load_vela
from jfg_forge.gui.main_window import MainWindow, RomWelcomeWindow
from jfg_forge.gui.render_data import model_information, prepare_render_data


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open the JFG Forge character model viewer.")
    parser.add_argument("--rom", type=Path, default=None, help="Explicit supported US Z64 ROM path.")
    parser.add_argument("--textures", type=Path, default=None, help="Optional verified texture manifest.")
    return parser.parse_args(argv)


def _request_opengl_33() -> None:
    surface = QSurfaceFormat()
    surface.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    surface.setVersion(3, 3)
    surface.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface.setDepthBufferSize(24)
    surface.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(surface)


def _load_characters(arguments: argparse.Namespace, source: RomSource):
    boy = load_boy(None, source, arguments.textures)
    powerboy = load_powerboy(None, source, arguments.textures)
    vela = load_vela(None, source, arguments.textures)
    powergirl = load_powergirl(None, source, arguments.textures)
    lupus = load_lupus(None, source, arguments.textures)
    powerdog = load_powerdog(None, source, arguments.textures)
    greenant = load_greenant(None, source, arguments.textures)
    scene = evaluate_boy_scene(boy, animation_index=0, time=0.0)
    return (
        boy,
        powerboy,
        vela,
        powergirl,
        lupus,
        powerdog,
        greenant,
        scene,
        prepare_render_data(scene),
        model_information(scene),
    )


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    _request_opengl_33()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("JFG Forge")
    active_window: dict[str, QWidget] = {}
    session: RomSession[MainWindow] = RomSession()

    def build_main_window(source: RomSource) -> MainWindow:
        assets = _load_characters(arguments, source)
        return MainWindow(
            *assets,
            rom_source=source,
            on_rom_selected=show_loaded_rom,
        )

    def show_loaded_rom(path: Path) -> None:
        parent = active_window.get("window")
        try:
            new_window = session.load(path, build_main_window)
        except RomLoadError as error:
            QMessageBox.critical(parent, "Unsupported ROM", str(error))
            return
        except Exception as error:
            QMessageBox.critical(
                parent,
                "JFG Forge load error",
                f"The supported ROM was recognized, but Forge could not load its character data:\n\n{error}",
            )
            return

        old_window = active_window.get("window")
        active_window["window"] = new_window
        new_window.show()
        if old_window is not None:
            old_window.close()

    if arguments.rom is None:
        window: QWidget = RomWelcomeWindow(show_loaded_rom)
        active_window["window"] = window
        window.show()
    else:
        try:
            window = session.load(arguments.rom, build_main_window)
        except RomLoadError as error:
            print(f"Unsupported ROM: {error}", file=sys.stderr)
            QMessageBox.critical(None, "Unsupported ROM", str(error))
            return 1
        except Exception as error:
            message = f"JFG Forge could not load its character assets:\n\n{error}"
            print(message, file=sys.stderr)
            QMessageBox.critical(None, "JFG Forge load error", message)
            return 1
        active_window["window"] = window
        window.show()
    return application.exec()


__all__ = ["main"]
