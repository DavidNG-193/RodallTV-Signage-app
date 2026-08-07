from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from rodall_signage.api.api_models import HeartbeatResult
from rodall_signage.services.heartbeat_service import HeartbeatService
from rodall_signage.services.power_manager import PowerManager


class _FakeApiClient:
    def __init__(self) -> None:
        self.acknowledged: list[str] = []

    def heartbeat(self) -> HeartbeatResult:
        return HeartbeatResult(
            server_time="2026-08-07T15:00:00Z",
            pending_power_command={
                "commandId": "command-1",
                "commandType": "Restart",
                "requestedAt": "2026-08-07T14:59:00Z",
            },
        )

    def acknowledge_power_command(self, command_id: str) -> None:
        self.acknowledged.append(command_id)


class PowerCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_heartbeat_acknowledges_and_emits_power_command(self) -> None:
        api = _FakeApiClient()
        service = HeartbeatService(api, interval_seconds=30)
        received: list[str] = []
        loop = QEventLoop()

        def on_ready(command_type: str) -> None:
            received.append(command_type)
            loop.quit()

        service.power_command_ready.connect(on_ready)
        QTimer.singleShot(3000, loop.quit)
        service.start()
        loop.exec()
        service.stop()

        self.assertEqual(api.acknowledged, ["command-1"])
        self.assertEqual(received, ["Restart"])

    @patch("rodall_signage.services.power_manager.platform.system")
    @patch("rodall_signage.services.power_manager.subprocess.run")
    def test_power_manager_uses_restricted_systemctl(
        self,
        run_mock,
        system_mock,
    ) -> None:
        system_mock.return_value = "Linux"

        PowerManager.execute("Shutdown")

        run_mock.assert_called_once_with(
            ["sudo", "/usr/bin/systemctl", "poweroff"],
            check=True,
        )

    def test_power_manager_rejects_unknown_command(self) -> None:
        with patch(
            "rodall_signage.services.power_manager.platform.system",
            return_value="Linux",
        ):
            with self.assertRaises(ValueError):
                PowerManager.execute("Arbitrary")


if __name__ == "__main__":
    unittest.main()
