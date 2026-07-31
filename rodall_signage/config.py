from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path


APP_NAME = "RodallTV Signage Prototype"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_MEDIA_DIR = PROJECT_ROOT / "test-media"

# Prioriza el binario distribuido con la aplicación y permite sobrescribirlo.
_bundled_mpv = PROJECT_ROOT / ("mpv.exe" if platform.system() == "Windows" else "mpv")
MPV_EXECUTABLE = os.getenv(
    "RODALL_MPV_PATH",
    str(_bundled_mpv) if _bundled_mpv.is_file() else "mpv",
)

def build_ipc_endpoint() -> tuple[str, str]:
    """
    Devuelve:
      1. El valor que recibirá --input-ipc-server.
      2. El nombre o ruta que usará QLocalSocket.

    En Windows, mpv crea una named pipe.
    En Linux, utiliza un Unix domain socket.
    """
    if platform.system() == "Windows":
        pipe_name = "rodalltv-mpv-prototype"
        return rf"\\.\pipe\{pipe_name}", pipe_name

    socket_path = str(Path(tempfile.gettempdir()) / "rodalltv-mpv-prototype.sock")
    return socket_path, socket_path
