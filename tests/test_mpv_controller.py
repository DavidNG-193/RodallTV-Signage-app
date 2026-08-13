from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

from rodall_signage.player.mpv_controller import MpvController


class MpvControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def test_arguments_enable_safe_hardware_decoding(self) -> None:
        settings = SimpleNamespace(
            mpv_executable="mpv",
            mpv_hwdec="auto-safe",
            mpv_profile="fast",
            mpv_gpu_dumb_mode=True,
            ipc_argument="/tmp/rodalltv-test.sock",
            ipc_socket_name="/tmp/rodalltv-test.sock",
        )
        controller = MpvController(settings)

        arguments = controller._build_arguments(1234)

        self.assertIn("--wid=1234", arguments)
        self.assertIn("--hwdec=auto-safe", arguments)
        self.assertIn("--vo=gpu", arguments)
        self.assertIn("--profile=fast", arguments)
        self.assertIn("--gpu-dumb-mode=yes", arguments)


if __name__ == "__main__":
    unittest.main()
