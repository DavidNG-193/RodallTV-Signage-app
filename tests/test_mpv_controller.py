from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

from rodall_signage.config import _build_ipc_endpoint
from rodall_signage.player.mpv_controller import MpvController
from rodall_signage.player.mpv_models import MpvState


class MpvControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    @staticmethod
    def _settings() -> SimpleNamespace:
        return SimpleNamespace(
            mpv_executable="mpv",
            mpv_hwdec="auto-safe",
            mpv_profile="fast",
            mpv_gpu_dumb_mode=True,
            ipc_argument="/tmp/rodalltv-test.sock",
            ipc_socket_name="/tmp/rodalltv-test.sock",
        )

    def test_arguments_enable_safe_hardware_decoding(self) -> None:
        controller = MpvController(self._settings())

        arguments = controller._build_arguments(1234)

        self.assertIn("--wid=1234", arguments)
        self.assertIn("--hwdec=auto-safe", arguments)
        self.assertIn("--vo=gpu", arguments)
        self.assertIn("--profile=fast", arguments)
        self.assertIn("--gpu-dumb-mode=yes", arguments)
        self.assertIn("--msg-level=all=warn", arguments)
        self.assertNotIn("--no-terminal", arguments)

    def test_ipc_endpoint_is_unique_for_the_application_process(self) -> None:
        argument, socket_name = _build_ipc_endpoint()

        self.assertIn(str(os.getpid()), argument)
        self.assertIn(str(os.getpid()), socket_name)
        if os.name != "nt":
            self.assertEqual(Path(argument).parent.name, "runtime")

    def test_ipc_failure_schedules_bounded_restart(self) -> None:
        controller = MpvController(self._settings())
        controller._window_id = 1234

        controller._schedule_restart("IPC no disponible")

        self.assertEqual(controller.state, MpvState.STARTING)
        self.assertTrue(controller._restart_scheduled)
        self.assertEqual(controller._restart_attempts, 1)
        self.assertEqual(controller._restart_timer.interval(), 2_000)
        controller.stop()

    def test_restart_exhaustion_reports_terminal_error(self) -> None:
        controller = MpvController(self._settings())
        controller._window_id = 1234
        controller._restart_attempts = len(controller._RESTART_DELAYS_MS)
        errors: list[str] = []
        controller.error_occurred.connect(errors.append)

        controller._schedule_restart("IPC no disponible")

        self.assertEqual(controller.state, MpvState.ERROR)
        self.assertTrue(controller._restart_scheduled)
        self.assertEqual(len(errors), 1)
        self.assertIn("Se agotaron", errors[0])
        controller.stop()

    def test_handshake_marks_player_ready_and_resets_restarts(self) -> None:
        controller = MpvController(self._settings())
        controller._restart_attempts = 3
        commands: list[tuple[list[object], int | None]] = []
        ready_events: list[bool] = []
        controller.ready.connect(lambda: ready_events.append(True))

        def record_command(
            command: list[object],
            request_id: int | None = None,
        ) -> bool:
            commands.append((command, request_id))
            return True

        controller._write_ipc_command = record_command
        controller._handle_ipc_handshake(
            {
                "error": "success",
                "data": "0.39.0",
                "request_id": controller._IPC_HANDSHAKE_REQUEST_ID,
            }
        )

        self.assertEqual(controller.state, MpvState.READY)
        self.assertEqual(controller._restart_attempts, 0)
        self.assertEqual(len(commands), 5)
        self.assertEqual(len(ready_events), 1)

        controller._change_state(MpvState.STARTING)
        controller.send_command(["set_property", "pause", False])
        controller._handle_ipc_handshake(
            {"error": "success", "data": "0.39.0"}
        )
        self.assertEqual(len(ready_events), 1)
        self.assertEqual(
            commands[-1][0],
            ["set_property", "pause", False],
        )
        self.assertEqual(controller._pending_commands, [])
        controller.stop()

    def test_ipc_disconnect_attempts_reconnection_before_restart(self) -> None:
        controller = MpvController(self._settings())
        controller._window_id = 1234
        controller._ipc_was_ready = True
        controller._change_state(MpvState.READY)

        controller._on_ipc_disconnected()

        self.assertEqual(controller.state, MpvState.STARTING)
        self.assertTrue(controller._retry_timer.isActive())
        self.assertTrue(controller._reconnect_timer.isActive())
        self.assertFalse(controller._restart_scheduled)

        controller.send_command(["set_property", "pause", False])
        self.assertEqual(len(controller._pending_commands), 1)

        controller._on_ipc_reconnect_timeout()
        self.assertTrue(controller._restart_scheduled)
        self.assertEqual(controller._restart_attempts, 1)
        controller.stop()


if __name__ == "__main__":
    unittest.main()
