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
        self._process.setStandardErrorFile(null_device)
        self._socket = QLocalSocket(self)
        self._state = MpvState.STOPPED
        self._is_stopping = False
        self._connect_attempts = 0
        self._max_connect_attempts = 40
        self._read_buffer = b""

        self._process.started.connect(self._schedule_ipc_connection)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)

        self._socket.connected.connect(self._on_ipc_connected)
        self._socket.readyRead.connect(self._read_ipc_messages)
        self._socket.errorOccurred.connect(self._on_socket_error)

        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(250)
        self._retry_timer.timeout.connect(self._connect_ipc)

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

        self._cleanup_stale_socket()

        arguments = [
            f"--wid={window_id}",
            "--idle=yes",
            "--force-window=yes",
            "--keep-open=yes",
            "--no-terminal",
            "--no-border",
            "--no-osc",
            "--no-input-default-bindings",
            "--cursor-autohide=always",
            "--image-display-duration=10",
            "--background=color",
            "--background-color=#101827",
            "--keepaspect=yes",
            "--video-unscaled=no",
            f"--input-ipc-server={self._settings.ipc_argument}",
        ]

        self._connect_attempts = 0
        self._is_stopping = False
        self._change_state(MpvState.STARTING)

        logger.info(
            "Iniciando mpv. executable=%s window_id=%s ipc=%s",
            self._settings.mpv_executable,
            window_id,
            self._settings.ipc_argument,
        )

        self._process.setProgram(self._settings.mpv_executable)
        self._process.setArguments(arguments)
        self._process.start()

    def load(self, media_path: Path) -> None:
        resolved_path = media_path.expanduser().resolve()

        if not resolved_path.is_file():
            self._report_error(
                f"No existe el archivo multimedia: {resolved_path}"
            )
            return

        logger.info("Solicitando reproducción: %s", resolved_path)
        self.send_command(["loadfile", str(resolved_path), "replace"])

    def send_command(self, command: list[object]) -> None:
        if not self.is_ready:
            self._report_error(
                "mpv todavía no está listo para recibir comandos."
            )
            return

        payload = json.dumps(
            {"command": command},
            ensure_ascii=False,
        ) + "\n"

        written = self._socket.write(payload.encode("utf-8"))

        if written == -1:
            self._report_error(
                "No fue posible escribir en el canal IPC de mpv."
            )
            return

        self._socket.flush()
        logger.debug("Comando enviado a mpv: %s", command)

    def stop(self) -> None:
        logger.info("Deteniendo mpv.")
        self._is_stopping = True
        self._retry_timer.stop()

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
        self._change_state(MpvState.STOPPED)
        self._is_stopping = False

    def _schedule_ipc_connection(self) -> None:
        logger.debug("Proceso mpv iniciado; esperando IPC.")
        self._retry_timer.start()

    def _connect_ipc(self) -> None:
        if self.is_ready:
            self._retry_timer.stop()
            return

        if self._socket.state() != QLocalSocket.UnconnectedState:
            self._socket.abort()

        self._connect_attempts += 1
        self._socket.connectToServer(self._settings.ipc_socket_name)

        if self._connect_attempts >= self._max_connect_attempts:
            self._retry_timer.stop()
            self._report_error(
                "mpv inició, pero no fue posible conectar con JSON IPC."
            )

    def _on_ipc_connected(self) -> None:
        self._retry_timer.stop()
        self._change_state(MpvState.READY)

        logger.info("Conexión JSON IPC establecida.")

        self.ready.emit()
        self.send_command(["observe_property", 1, "path"])
        self.send_command(["observe_property", 2, "pause"])
        self.send_command(["observe_property", 3, "eof-reached"])

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

            self.playback_event.emit(
                MpvEvent(
                    name=str(message.get("event", "response")),
                    data=message.get("data"),
                    raw=message,
                )
            )

            if (
                message.get("event") == "property-change"
                and message.get("name") == "path"
                and message.get("data")
            ):
                self._change_state(MpvState.PLAYING)

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if self._is_stopping:
            return

        if error == QProcess.FailedToStart:
            self._report_error(
                f"No fue posible iniciar mpv ({self._settings.mpv_executable}): "
                f"{self._process.errorString()}"
            )
            return

        self._report_error(f"Error de mpv: {self._process.errorString()}")

    def _on_process_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        self._retry_timer.stop()

        if not self._is_stopping and self._state != MpvState.STOPPED:
            logger.warning("mpv terminó con código %s.", exit_code)

        self._change_state(MpvState.STOPPED)

    def _on_socket_error(
        self,
        _error: QLocalSocket.LocalSocketError,
    ) -> None:
        if self._connect_attempts >= self._max_connect_attempts:
            logger.error("Error IPC: %s", self._socket.errorString())

    def _cleanup_stale_socket(self) -> None:
        if platform.system() == "Windows":
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
