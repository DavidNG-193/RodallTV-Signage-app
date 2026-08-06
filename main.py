from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _ensure_project_python() -> None:
    required_modules = ("PySide6", "requests", "dotenv")
    missing_modules = [
        module
        for module in required_modules
        if importlib.util.find_spec(module) is None
    ]

    if not missing_modules:
        return

    project_root = Path(__file__).resolve().parent
    virtualenv_python = (
        project_root / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else project_root / ".venv" / "bin" / "python"
    )

    if virtualenv_python.is_file():
        if Path(sys.executable).resolve() == virtualenv_python.resolve():
            missing = ", ".join(missing_modules)
            raise RuntimeError(
                f"Faltan dependencias en signage-app/.venv: {missing}. "
                "Instala requirements-dev.txt en ese entorno."
            )

        os.execv(
            str(virtualenv_python),
            [str(virtualenv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )

    raise RuntimeError(
        "Faltan dependencias y no existe un entorno virtual compatible en "
        "signage-app/.venv. Crea el entorno e instala requirements-dev.txt."
    )


_ensure_project_python()

from rodall_signage.app import run  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run())
