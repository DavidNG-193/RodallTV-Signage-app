from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
CACHE_DIR = RUNTIME_DIR / "cache"
LOG_DIR = RUNTIME_DIR / "logs"
TEST_MEDIA_DIR = PROJECT_ROOT / "test-media"
_BUNDLED_MPV = PROJECT_ROOT / (
    "mpv.exe" if platform.system() == "Windows" else "mpv"
)


def _load_environment_files() -> None:
    # La ubicación oficial es signage-app/.env. Se conserva compatibilidad
    # con rodall_signage/.env porque algunas instalaciones iniciales en
    # Raspberry recibieron el archivo dentro del paquete.
    candidates = (
        PROJECT_ROOT / ".env",
        Path(__file__).resolve().parent / ".env",
        # Fallback de migración: reutiliza las credenciales ya provisionadas
        # por el agente anterior sin copiarlas al código ni versionarlas.
        PROJECT_ROOT.parent / "raspberry-agent" / ".env",
    )

    for path in candidates:
        if path.is_file():
            load_dotenv(dotenv_path=path, override=False)


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un número entero.") from error

    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")

    return value


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
    mpv_hwdec: str
    mpv_profile: str
    mpv_gpu_dumb_mode: bool
    log_level: str
    windowed: bool
    test_media_path: Path | None
    ipc_argument: str
    ipc_socket_name: str
    runtime_dir: Path
    cache_dir: Path
    log_dir: Path
    api_base_url: str
    device_id: str
    device_token: str
    heartbeat_seconds: int
    sync_seconds: int
    content_dir: Path
    manifest_path: Path
    exchange_rate_refresh_seconds: int
    weather_refresh_seconds: int
    reference_refresh_seconds: int

    @classmethod
    def from_environment(cls) -> "AppSettings":
        _load_environment_files()
        ipc_argument, ipc_socket_name = _build_ipc_endpoint()

        raw_media = os.getenv("RODALL_TEST_MEDIA", "").strip()
        media_path = Path(raw_media).expanduser() if raw_media else None
        configured_mpv = os.getenv("RODALL_MPV_PATH", "").strip()
        api_base_url = os.getenv(
            "RODALL_API_BASE_URL",
            "http://localhost:5026",
        ).rstrip("/")
        device_id = os.getenv(
            "RODALL_DEVICE_ID",
            os.getenv("RODALL_DEVICE_UUID", ""),
        ).strip()
        device_token = os.getenv("RODALL_DEVICE_TOKEN", "").strip()

        if _BUNDLED_MPV.is_file() and configured_mpv in {"", "mpv", "mpv.exe"}:
            mpv_executable = str(_BUNDLED_MPV)
        else:
            mpv_executable = configured_mpv or "mpv"

        return cls(
            app_name="RodallTV Signage",
            environment=os.getenv("RODALL_APP_ENV", "development").strip(),
            mpv_executable=mpv_executable,
            mpv_hwdec=(
                os.getenv("RODALL_MPV_HWDEC", "auto-safe").strip()
                or "auto-safe"
            ),
            mpv_profile=(
                os.getenv("RODALL_MPV_PROFILE", "fast").strip() or "fast"
            ),
            mpv_gpu_dumb_mode=_read_bool(
                "RODALL_MPV_GPU_DUMB_MODE",
                True,
            ),
            log_level=os.getenv("RODALL_LOG_LEVEL", "INFO").strip().upper(),
            windowed=_read_bool("RODALL_WINDOWED", True),
            test_media_path=media_path,
            ipc_argument=ipc_argument,
            ipc_socket_name=ipc_socket_name,
            runtime_dir=RUNTIME_DIR,
            cache_dir=CACHE_DIR,
            log_dir=LOG_DIR,
            api_base_url=api_base_url,
            device_id=device_id,
            device_token=device_token,
            heartbeat_seconds=_read_positive_int(
                "RODALL_HEARTBEAT_SECONDS",
                30,
            ),
            sync_seconds=_read_positive_int("RODALL_SYNC_SECONDS", 60),
            content_dir=RUNTIME_DIR / "content",
            manifest_path=CACHE_DIR / "active_manifest.json",
            exchange_rate_refresh_seconds=max(
                _read_positive_int("RODALL_EXCHANGE_RATE_SECONDS", 3600),
                300,
            ),
            weather_refresh_seconds=max(
                _read_positive_int("RODALL_WEATHER_SECONDS", 900),
                300,
            ),
            reference_refresh_seconds=max(
                _read_positive_int("RODALL_REFERENCE_SECONDS", 60),
                30,
            ),
        )

    def ensure_directories(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
