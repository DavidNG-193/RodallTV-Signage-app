from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtNetwork import QLocalSocket

from rodall_signage.config import MPV_EXECUTABLE, build_ipc_endpoint


class MpvController(QObject):
    ready = Signal()
    error_occurred = Signal(str)
    playback_event = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._process = QProcess(self)
        null_device = QProcess.nullDevice()
        self._process.setStandardInputFile(null_device)
        self._process.setStandardOutputFile(null_device)
        self._process.setStandardErrorFile(null_device)
        self._socket = QLocalSocket(self)
        self._ipc_argument, self._ipc_socket_name = build_ipc_endpoint()
        self._is_ready = False
        self._is_stopping = False
        self._connect_attempts = 0
        self._max_connect_attempts = 30

        self._process.started.connect(self._schedule_ipc_connection)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)

        self._socket.connected.connect(self._on_ipc_connected)
        self._socket.readyRead.connect(self._read_ipc_messages)
        self._socket.errorOccurred.connect(self._on_socket_error)

        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(200)
        self._retry_timer.timeout.connect(self._connect_ipc)

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def start(self, window_id: int) -> None:
        if self._process.state() != QProcess.NotRunning:
            return

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
            f"--input-ipc-server={self._ipc_argument}",
        ]

        self._is_ready = False
        self._is_stopping = False
        self._connect_attempts = 0
        self._process.setProgram(MPV_EXECUTABLE)
        self._process.setArguments(arguments)
        self._process.start()

    def load(self, media_path: Path) -> None:
        resolved_path = media_path.resolve()

        if not resolved_path.is_file():
            self.error_occurred.emit(
                f"No existe el archivo multimedia: {resolved_path}"
            )
            return

        self.send_command(["loadfile", str(resolved_path), "replace"])

    def send_command(self, command: list[object]) -> None:
        if not self._is_ready:
            self.error_occurred.emit("mpv todavía no está listo para recibir comandos.")
            return

        payload = json.dumps({"command": command}, ensure_ascii=False) + "\n"
        written = self._socket.write(payload.encode("utf-8"))

        if written == -1:
            self.error_occurred.emit("No fue posible escribir en el canal IPC de mpv.")
            return

        self._socket.flush()

    def stop(self) -> None:
        self._is_stopping = True
        self._retry_timer.stop()
        self._is_ready = False

        if self._socket.state() == QLocalSocket.ConnectedState:
            payload = json.dumps({"command": ["quit"]}) + "\n"
            self._socket.write(payload.encode("utf-8"))
            self._socket.flush()
            self._socket.waitForBytesWritten(300)
            self._socket.disconnectFromServer()

        if self._process.state() != QProcess.NotRunning:
            if not self._process.waitForFinished(1500):
                self._process.terminate()

            if not self._process.waitForFinished(1000):
                self._process.kill()
                self._process.waitForFinished(1000)

        self._is_stopping = False

    def _schedule_ipc_connection(self) -> None:
        self._retry_timer.start()

    def _connect_ipc(self) -> None:
        if self._is_ready:
            self._retry_timer.stop()
            return

        if self._socket.state() != QLocalSocket.UnconnectedState:
            self._socket.abort()

        self._connect_attempts += 1
        self._socket.connectToServer(self._ipc_socket_name)

        if self._connect_attempts >= self._max_connect_attempts:
            self._retry_timer.stop()
            self.error_occurred.emit(
                "mpv inició, pero no fue posible conectar con su canal JSON IPC."
            )

    def _on_ipc_connected(self) -> None:
        self._retry_timer.stop()
        self._is_ready = True
        self.ready.emit()

        # Solicita eventos útiles para las pruebas posteriores.
        self.send_command(["observe_property", 1, "path"])
        self.send_command(["observe_property", 2, "pause"])
        self.send_command(["observe_property", 3, "eof-reached"])

    def _read_ipc_messages(self) -> None:
        while self._socket.canReadLine():
            raw_line = bytes(self._socket.readLine()).decode("utf-8").strip()

            if not raw_line:
                continue

            try:
                message = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            self.playback_event.emit(message)

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if self._is_stopping:
            return

        if error == QProcess.FailedToStart:
            self.error_occurred.emit(
                f"No fue posible iniciar mpv ({MPV_EXECUTABLE}): "
                f"{self._process.errorString()}"
            )
            return

        self.error_occurred.emit(f"Error de mpv: {self._process.errorString()}")

    def _on_process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._retry_timer.stop()
        self._is_ready = False

        if self._is_stopping:
            return

        self.error_occurred.emit(f"mpv terminó con código {exit_code}.")

    def _on_socket_error(self, _error: QLocalSocket.LocalSocketError) -> None:
        # Durante los primeros milisegundos es normal que el socket todavía no
        # exista. El temporizador realizará un nuevo intento.
        if self._connect_attempts >= self._max_connect_attempts:
            self.error_occurred.emit(self._socket.errorString())
