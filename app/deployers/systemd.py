"""Systemd service/timer deployer."""
from typing import Dict

from futurelog import FutureLogger

from app import resources
from app.deployers.deployer import Deployer
from app.logger import get_logger
from app.utils import extract_checksum, get_sha256, upload_file

LOGGER = get_logger(__name__)
FUTURE_LOGGER = FutureLogger(__name__)


class SystemdDeployer(Deployer):
    """Deploys systemd services and timers to execute minion and scripts."""

    sha256: Dict = {}

    @classmethod
    def calculate_checksum(cls) -> None:
        """Calculate checksum for local files."""
        path = f"{resources.__path__[0]}/systemd"
        cls.sha256["minion.service"] = get_sha256(f"{path}/salt-minion.service")
        cls.sha256["grains.service"] = get_sha256(f"{path}/salt-update-grains.service")
        cls.sha256["grains.timer"] = get_sha256(f"{path}/salt-update-grains.timer")

    async def _check_systemd(self) -> bool:
        commands = {
            "minion service is enabled": "sudo systemctl is-enabled salt-minion.service",
            "minion service is started": "sudo systemctl is-active salt-minion.service",
            "grains timer is enabled": "sudo systemctl is-enabled salt-update-grains.timer",
            "grains timer is started": "sudo systemctl is-active salt-update-grains.timer",
            "grains service is enabled": "sudo systemctl is-enabled salt-update-grains.service",
        }

        for action, cmd in commands.items():
            FUTURE_LOGGER.info(self.hostname, "check if %s", action)
            response = await self.ssh.run(cmd)

            if response.exit_status != 0:
                FUTURE_LOGGER.debug(self.hostname, "check %s failed", action)
                return False

        return True

    async def _check_checksum(self) -> bool:
        commands = {
            "minion.service": "sha256sum /etc/systemd/system/salt-minion.service",
            "grains.service": "sha256sum /etc/systemd/system/salt-update-grains.service",
            "grains.timer": "sha256sum /etc/systemd/system/salt-update-grains.timer",
        }

        for action, cmd in commands.items():
            FUTURE_LOGGER.info(self.hostname, "check sha256 of %s", action)
            response = await self.ssh.run(cmd)

            if response.exit_status != 0:
                FUTURE_LOGGER.debug(self.hostname, "check %s failed", action)
                return False
            if self.sha256[action] != extract_checksum(response.stdout):
                return False

        return True

    async def restart(self) -> bool:
        """Restart salt-minion systemd service."""
        response = await self.ssh.run("sudo systemctl restart salt-minion.service")

        return not bool(response.exit_status)

    async def check(self) -> bool:
        """Check if all services are started and enabled."""
        checks = [await self._check_systemd(), await self._check_checksum()]
        return all(checks)

    async def deploy(self) -> bool:
        """Deploys salt-minion service and timer/service for some scripts."""
        systemd_files = [
            "salt-minion.service",
            "salt-update-grains.service",
            "salt-update-grains.timer",
        ]
        commands = {
            "reload systemd": "sudo systemctl daemon-reload",
        }

        # upload systemd files
        for elt in systemd_files:
            uploaded = await upload_file(
                self.hostname,
                self.ssh,
                f"{resources.__path__[0]}/systemd/{elt}",
                "/etc/systemd/system/",
            )

            if not uploaded:
                return False

            commands[f"enable {elt}"] = f"sudo systemctl enable {elt}"
            commands[f"starting {elt}"] = f"sudo systemctl start {elt}"

        # enable and start systemd services
        for action, cmd in commands.items():
            FUTURE_LOGGER.info(self.hostname, action)
            response = await self.ssh.run(cmd)
            if response.exit_status != 0:
                return False

        return await self.check()
