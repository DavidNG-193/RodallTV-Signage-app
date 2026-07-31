from __future__ import annotations

import argparse
from pathlib import Path

from rodall_signage.app import run


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prototipo PySide6 + mpv para RodallTV"
    )
    parser.add_argument(
        "--media",
        type=Path,
        default=None,
        help="Ruta de una imagen o video local para reproducir.",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Ejecuta el prototipo en una ventana redimensionable.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    return run(media_path=arguments.media, windowed=arguments.windowed)


if __name__ == "__main__":
    raise SystemExit(main())