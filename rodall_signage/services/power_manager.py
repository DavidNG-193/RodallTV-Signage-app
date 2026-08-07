from __future__ import annotations

import logging
import platform
import subprocess


logger = logging.getLogger(__name__)


class PowerManager:
    @staticmethod
    def execute(command_type: str) -> None:
        if platform.system() != "Linux":
            raise RuntimeError(
                "Los comandos de energía solo pueden ejecutarse en Linux."
            )

        actions = {
            "Restart": "reboot",
            "Shutdown": "poweroff",
        }
        action = actions.get(command_type)
        if action is None:
            raise ValueError(
                f"Comando de energía no permitido: {command_type}"
            )

        logger.warning("Ejecutando comando de energía: %s", command_type)
        subprocess.run(
            ["sudo", "/usr/bin/systemctl", action],
            check=True,
        )
