from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
CACHE_DIR = RUNTIME_DIR / "cache"
LOG_DIR = RUNTIME_DIR / "logs"
TEST_MEDIA_DIR = PROJECT_ROOT / "test-media"
_BUNDLED_MPV = PROJECT_ROOT / (
    "mpv.exe" if platform.system() == "Windows" else "mpv"
)


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_ipc_endpoint() -> tuple[str, str]:
    name = os.getenv("RODALL_IPC_NAME", "rodalltv-mpv").strip()

    if platform.system() == "Windows":
        return rf"\\.\pipe\{name}", name

    socket_path = str(Path(tempfile.gettempdir()) / f"{name}.sock")
    return socket_path, socket_path


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_name: str
    environment: str
    mpv_executable: str
    log_level: str
    windowed: bool
    test_media_path: Path | None
    ipc_argument: str
    ipc_socket_name: str
    runtime_dir: Path
    cache_dir: Path
    log_dir: Path

    @classmethod
    def from_environment(cls) -> "AppSettings":
        ipc_argument, ipc_socket_name = _build_ipc_endpoint()

        raw_media = os.getenv("RODALL_TEST_MEDIA", "").strip()
        media_path = Path(raw_media).expanduser() if raw_media else None
        configured_mpv = os.getenv("RODALL_MPV_PATH", "").strip()

        if _BUNDLED_MPV.is_file() and configured_mpv in {"", "mpv", "mpv.exe"}:
            mpv_executable = str(_BUNDLED_MPV)
        else:
            mpv_executable = configured_mpv or "mpv"

        return cls(
            app_name="RodallTV Signage",
            environment=os.getenv("RODALL_APP_ENV", "development").strip(),
            mpv_executable=mpv_executable,
            log_level=os.getenv("RODALL_LOG_LEVEL", "INFO").strip().upper(),
            windowed=_read_bool("RODALL_WINDOWED", True),
            test_media_path=media_path,
            ipc_argument=ipc_argument,
            ipc_socket_name=ipc_socket_name,
            runtime_dir=RUNTIME_DIR,
            cache_dir=CACHE_DIR,
            log_dir=LOG_DIR,
        )

    def ensure_directories(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
