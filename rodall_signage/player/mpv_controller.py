from __future__ import annotations

import json
import logging
import platform
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalSocket

from rodall_signage.config import AppSettings
from rodall_signage.player.mpv_models import MpvEvent, MpvState


logger = logging.getLogger(__name__)


class MpvController(QObject):
    _IPC_HANDSHAKE_REQUEST_ID = 10_001
    _IPC_CONNECT_INTERVAL_MS = 250
    _IPC_STARTUP_TIMEOUT_MS = 30_000
    _IPC_RECONNECT_TIMEOUT_MS = 5_000
    _RESTART_DELAYS_MS = (2_000, 5_000, 15_000, 30_000)

    ready = Signal()
    state_changed = Signal(MpvState)
    error_occurred = Signal(str)
    playback_event = Signal(MpvEvent)

    def __init__(
        self,
        settings: AppSettings,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings = settings
        self._process = QProcess(self)
        null_device = QProcess.nullDevice()
        self._process.setStandardInputFile(null_device)
        self._process.setStandardOutputFile(null_device)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._socket = QLocalSocket(self)
        self._state = MpvState.STOPPED
        self._is_stopping = False
        self._restart_scheduled = False
        self._restart_attempts = 0
        self._connect_attempts = 0
        self._ipc_was_ready = False
        self._window_id: int | None = None
        self._read_buffer = b""
        self._stderr_buffer = ""
        self._pending_commands: list[list[object]] = []

        self._process.started.connect(self._schedule_ipc_connection)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)
        self._process.readyReadStandardError.connect(self._read_process_stderr)

        self._socket.connected.connect(self._on_ipc_connected)
        self._socket.disconnected.connect(self._on_ipc_disconnected)
        self._socket.readyRead.connect(self._read_ipc_messages)
        self._socket.errorOccurred.connect(self._on_socket_error)

        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(self._IPC_CONNECT_INTERVAL_MS)
        self._retry_timer.timeout.connect(self._connect_ipc)

        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.setInterval(self._IPC_STARTUP_TIMEOUT_MS)
        self._startup_timer.timeout.connect(self._on_ipc_startup_timeout)

        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._restart_process)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.setInterval(self._IPC_RECONNECT_TIMEOUT_MS)
        self._reconnect_timer.timeout.connect(self._on_ipc_reconnect_timeout)

    @property
    def state(self) -> MpvState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state in {MpvState.READY, MpvState.PLAYING}

    def start(self, window_id: int) -> None:
        if self._process.state() != QProcess.NotRunning:
            logger.warning("Se ignoró start(): mpv ya está ejecutándose.")
            return

        self._window_id = window_id
        self._restart_attempts = 0
        self._restart_scheduled = False
        self._is_stopping = False
        self._launch_process()

    def _launch_process(self) -> None:
        if self._window_id is None or self._is_stopping:
            return

        self._cleanup_stale_socket()
        arguments = self._build_arguments(self._window_id)

        self._connect_attempts = 0
        self._read_buffer = b""
        self._stderr_buffer = ""
        self._pending_commands.clear()
        self._ipc_was_ready = False
        self._restart_scheduled = False
        self._change_state(MpvState.STARTING)

        logger.info(
            "Iniciando mpv. executable=%s window_id=%s ipc=%s "
            "hwdec=%s profile=%s gpu_dumb_mode=%s",
            self._settings.mpv_executable,
            self._window_id,
            self._settings.ipc_argument,
            self._settings.mpv_hwdec,
            self._settings.mpv_profile,
            self._settings.mpv_gpu_dumb_mode,
        )

        self._process.setProgram(self._settings.mpv_executable)
        self._process.setArguments(arguments)
        self._process.start()

    def _build_arguments(self, window_id: int) -> list[str]:
        return [
            f"--wid={window_id}",
            "--idle=yes",
            "--force-window=yes",
            # mpv desactiva la decodificación por hardware de forma
            # predeterminada. En Raspberry eso puede ocupar el CPU completo y
            # quitarle tiempo a los repintados de Qt.
            f"--hwdec={self._settings.mpv_hwdec}",
            "--vo=gpu",
            f"--profile={self._settings.mpv_profile}",
            "--gpu-dumb-mode="
            + ("yes" if self._settings.mpv_gpu_dumb_mode else "no"),
            # El coordinador administra el bucle. Mantener un video abierto al
            # llegar al EOF deja ``pause=yes`` en algunas versiones de mpv
            # para Raspberry Pi y el segundo ciclo puede quedar negro.
            "--keep-open=no",
            # Mantener stderr habilitado permite diagnosticar por qué mpv no
            # llegó a crear o atender el socket IPC sin mostrar una terminal.
            "--msg-level=all=warn",
            "--no-border",
            "--no-osc",
            "--no-input-default-bindings",
            "--cursor-autohide=always",
            # Las imágenes avanzan mediante PlaybackCoordinator; mpv debe
            # conservarlas hasta recibir el siguiente loadfile.
            "--image-display-duration=inf",
            "--background=color",
            "--background-color=#101827",
            "--keepaspect=yes",
            "--video-unscaled=no",
            f"--input-ipc-server={self._settings.ipc_argument}",
        ]

    def load(self, media_path: Path) -> None:
        resolved_path = media_path.expanduser().resolve()

        if not resolved_path.is_file():
            self._report_error(
                f"No existe el archivo multimedia: {resolved_path}"
            )
            return

        logger.info("Solicitando reproducción: %s", resolved_path)
        self.send_command(["loadfile", str(resolved_path), "replace"])
        # ``pause`` es una propiedad global y versiones antiguas de mpv pueden
        # conservarla después de un EOF. Restablecerla hace repetible cada
        # vuelta de la playlist, especialmente con decodificación en Raspberry.
        self.send_command(["set_property", "pause", False])

    def send_command(self, command: list[object]) -> None:
        if not self.is_ready:
            if self._state == MpvState.STARTING:
                if self._ipc_was_ready and not self._restart_scheduled:
                    self._pending_commands.append(command)
                    logger.info(
                        "Comando retenido mientras se reconecta JSON IPC: %s",
                        command,
                    )
                else:
                    logger.debug(
                        "Comando omitido mientras mpv se recupera: %s",
                        command,
                    )
                return

            self._report_error(
                "mpv todavía no está listo para recibir comandos."
            )
            return

        if not self._write_ipc_command(command):
            self._schedule_restart(
                "No fue posible escribir en el canal IPC de mpv."
            )

    def _write_ipc_command(
        self,
        command: list[object],
        request_id: int | None = None,
    ) -> bool:
        message: dict[str, object] = {"command": command}
        if request_id is not None:
            message["request_id"] = request_id

        payload = json.dumps(
            message,
            ensure_ascii=False,
        ) + "\n"

        written = self._socket.write(payload.encode("utf-8"))

        if written == -1:
            logger.error("No fue posible escribir en el canal IPC de mpv.")
            return False

        self._socket.flush()
        logger.debug("Comando enviado a mpv: %s", command)
        return True

    def stop(self) -> None:
        logger.info("Deteniendo mpv.")
        self._is_stopping = True
        self._restart_scheduled = False
        self._retry_timer.stop()
        self._startup_timer.stop()
        self._restart_timer.stop()
        self._reconnect_timer.stop()

        if self._socket.state() == QLocalSocket.ConnectedState:
            payload = json.dumps({"command": ["quit"]}) + "\n"
            self._socket.write(payload.encode("utf-8"))
            self._socket.flush()
            self._socket.waitForBytesWritten(500)
            self._socket.disconnectFromServer()

        if self._process.state() != QProcess.NotRunning:
            if not self._process.waitForFinished(2000):
                logger.warning("mpv no cerró con quit; enviando terminate.")
                self._process.terminate()

            if not self._process.waitForFinished(1500):
                logger.error("mpv no cerró con terminate; enviando kill.")
                self._process.kill()
                self._process.waitForFinished(1000)

        self._cleanup_stale_socket()
        self._window_id = None
        self._restart_attempts = 0
        self._pending_commands.clear()
        self._change_state(MpvState.STOPPED)
        self._is_stopping = False

    def _schedule_ipc_connection(self) -> None:
        logger.debug("Proceso mpv iniciado; esperando IPC.")
        self._startup_timer.start()
        self._retry_timer.start()
        self._connect_ipc()

    def _connect_ipc(self) -> None:
        if self.is_ready or self._restart_scheduled or self._is_stopping:
            self._retry_timer.stop()
            return

        if self._socket.state() != QLocalSocket.UnconnectedState:
            self._socket.abort()

        self._connect_attempts += 1
        self._socket.connectToServer(self._settings.ipc_socket_name)

    def _on_ipc_connected(self) -> None:
        self._retry_timer.stop()
        logger.debug("Socket IPC conectado; verificando protocolo JSON.")
        if not self._write_ipc_command(
            ["get_property", "mpv-version"],
            self._IPC_HANDSHAKE_REQUEST_ID,
        ):
            self._schedule_restart(
                "El socket de mpv conectó, pero no aceptó el handshake JSON."
            )

    def _read_ipc_messages(self) -> None:
        self._read_buffer += bytes(self._socket.readAll())

        while b"\n" in self._read_buffer:
            raw_line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            raw_line = raw_line.strip()

            if not raw_line:
                continue

            try:
                message = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("Se ignoró un mensaje IPC inválido.")
                continue

            if message.get("request_id") == self._IPC_HANDSHAKE_REQUEST_ID:
                self._handle_ipc_handshake(message)
                continue

            self.playback_event.emit(
                MpvEvent(
                    name=str(message.get("event", "response")),
                    data=message.get("data"),
                    raw=message,
                )
            )

            if (
                message.get("event") == "property-change"
                and message.get("name") == "hwdec-current"
                and message.get("data") is not None
            ):
                hwdec = str(message["data"])
                if hwdec == "no":
                    logger.warning(
                        "mpv está decodificando video por CPU; no se "
                        "encontró un backend de hardware compatible."
                    )
                else:
                    logger.info(
                        "Decodificación de video por hardware activa: %s",
                        hwdec,
                    )

            if (
                message.get("event") == "property-change"
                and message.get("name") == "path"
                and message.get("data")
            ):
                self._change_state(MpvState.PLAYING)

    def _handle_ipc_handshake(self, message: dict[str, object]) -> None:
        if message.get("error") not in (None, "success"):
            self._schedule_restart(
                "mpv rechazó el handshake JSON IPC: "
                f"{message.get('error')}"
            )
            return

        self._startup_timer.stop()
        self._reconnect_timer.stop()
        was_ready = self._ipc_was_ready
        self._ipc_was_ready = True
        self._restart_attempts = 0
        self._restart_scheduled = False
        self._change_state(MpvState.READY)

        logger.info(
            "Conexión JSON IPC verificada. mpv_version=%s attempts=%s",
            message.get("data", "desconocida"),
            self._connect_attempts,
        )

        if not was_ready:
            self.ready.emit()
        self._write_ipc_command(["observe_property", 1, "path"])
        self._write_ipc_command(["observe_property", 2, "pause"])
        self._write_ipc_command(["observe_property", 3, "eof-reached"])
        self._write_ipc_command(["observe_property", 4, "media-title"])
        self._write_ipc_command(["observe_property", 5, "hwdec-current"])

        if was_ready and self._pending_commands:
            pending_commands = self._pending_commands.copy()
            self._pending_commands.clear()
            for command in pending_commands:
                if not self._write_ipc_command(command):
                    self._schedule_restart(
                        "Falló el envío de comandos retenidos tras reconectar "
                        "JSON IPC."
                    )
                    break

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if self._is_stopping or self._restart_scheduled:
            return

        if error == QProcess.FailedToStart:
            self._schedule_restart(
                f"No fue posible iniciar mpv ({self._settings.mpv_executable}): "
                f"{self._process.errorString()}"
            )
            return

        self._schedule_restart(
            f"Error de mpv: {self._process.errorString()}"
        )

    def _on_process_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        self._read_process_stderr()
        self._flush_stderr_buffer()
        self._retry_timer.stop()
        self._startup_timer.stop()

        if self._is_stopping:
            return

        if self._restart_scheduled:
            logger.debug(
                "mpv terminó como parte de la recuperación. code=%s",
                exit_code,
            )
            return

        self._schedule_restart(
            f"mpv terminó inesperadamente con código {exit_code}."
        )

    def _on_socket_error(
        self,
        _error: QLocalSocket.LocalSocketError,
    ) -> None:
        if self._is_stopping or self._restart_scheduled:
            return

        logger.debug(
            "Conexión IPC todavía no disponible. attempt=%s error=%s",
            self._connect_attempts,
            self._socket.errorString(),
        )

    def _on_ipc_disconnected(self) -> None:
        if self._is_stopping or self._restart_scheduled:
            return

        if self._ipc_was_ready:
            self._change_state(MpvState.STARTING)
            if not self._reconnect_timer.isActive():
                logger.warning(
                    "Se perdió JSON IPC; se intentará reconectar durante "
                    "%.1f segundos.",
                    self._IPC_RECONNECT_TIMEOUT_MS / 1000,
                )
                self._reconnect_timer.start()

        if self._state == MpvState.STARTING:
            self._retry_timer.start()

    def _on_ipc_reconnect_timeout(self) -> None:
        if self.is_ready or self._is_stopping or self._restart_scheduled:
            return

        self._schedule_restart(
            "No fue posible restablecer la conexión JSON IPC con mpv."
        )

    def _on_ipc_startup_timeout(self) -> None:
        if self.is_ready or self._is_stopping or self._restart_scheduled:
            return

        self._schedule_restart(
            "mpv inició, pero no respondió al handshake JSON IPC "
            f"después de {self._IPC_STARTUP_TIMEOUT_MS // 1000} segundos."
        )

    def _schedule_restart(self, reason: str) -> None:
        if self._is_stopping or self._restart_scheduled:
            return

        self._retry_timer.stop()
        self._startup_timer.stop()
        self._reconnect_timer.stop()

        if self._restart_attempts >= len(self._RESTART_DELAYS_MS):
            self._restart_scheduled = True
            self._stop_process_for_restart()
            self._cleanup_stale_socket()
            self._report_error(
                f"{reason} Se agotaron los intentos automáticos de recuperación."
            )
            return

        delay_ms = self._RESTART_DELAYS_MS[self._restart_attempts]
        self._restart_attempts += 1
        self._restart_scheduled = True
        self._change_state(MpvState.STARTING)

        logger.warning(
            "%s Se reiniciará mpv en %.1f segundos (intento %s/%s).",
            reason,
            delay_ms / 1000,
            self._restart_attempts,
            len(self._RESTART_DELAYS_MS),
        )

        self._socket.abort()
        self._stop_process_for_restart()
        self._cleanup_stale_socket()
        self._restart_timer.start(delay_ms)

    def _restart_process(self) -> None:
        if self._is_stopping or not self._restart_scheduled:
            return

        logger.info("Ejecutando reinicio automático de mpv.")
        self._launch_process()

    def _stop_process_for_restart(self) -> None:
        if self._process.state() == QProcess.NotRunning:
            return

        self._process.terminate()
        if not self._process.waitForFinished(1500):
            logger.warning(
                "mpv no terminó durante la recuperación; enviando kill."
            )
            self._process.kill()
            self._process.waitForFinished(1000)

    def _read_process_stderr(self) -> None:
        raw = bytes(self._process.readAllStandardError())
        if not raw:
            return

        self._stderr_buffer += raw.decode("utf-8", errors="replace")
        lines = self._stderr_buffer.splitlines(keepends=True)
        self._stderr_buffer = ""

        if lines and not lines[-1].endswith(("\n", "\r")):
            self._stderr_buffer = lines.pop()

        for line in lines:
            text = line.strip()
            if text:
                logger.warning("mpv stderr: %s", text)

    def _flush_stderr_buffer(self) -> None:
        text = self._stderr_buffer.strip()
        self._stderr_buffer = ""
        if text:
            logger.warning("mpv stderr: %s", text)

    def _cleanup_stale_socket(self) -> None:
        if platform.system() == "Windows":
            return

        if self._process.state() != QProcess.NotRunning:
            logger.warning(
                "No se eliminará el socket IPC porque mpv sigue activo."
            )
            return

        socket_path = Path(self._settings.ipc_argument)

        if socket_path.exists():
            try:
                socket_path.unlink()
                logger.debug(
                    "Socket IPC anterior eliminado: %s",
                    socket_path,
                )
            except OSError:
                logger.warning(
                    "No se pudo eliminar el socket anterior: %s",
                    socket_path,
                )

    def _change_state(self, state: MpvState) -> None:
        if self._state == state:
            return

        self._state = state
        logger.debug("Estado de mpv: %s", state)
        self.state_changed.emit(state)

    def _report_error(self, message: str) -> None:
        self._change_state(MpvState.ERROR)
        logger.error(message)
        self.error_occurred.emit(message)
