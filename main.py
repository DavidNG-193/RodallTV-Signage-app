from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _ensure_project_python() -> None:
    if importlib.util.find_spec("PySide6") is not None:
        return

    project_root = Path(__file__).resolve().parent
    virtualenv_python = project_root / ".venv" / "Scripts" / "python.exe"

    if virtualenv_python.is_file():
        os.execv(
            str(virtualenv_python),
            [str(virtualenv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )

    raise RuntimeError(
        "PySide6 no está instalado y no existe signage-app/.venv. "
        "Crea el entorno virtual e instala requirements-dev.txt."
    )


_ensure_project_python()

from rodall_signage.app import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run())
