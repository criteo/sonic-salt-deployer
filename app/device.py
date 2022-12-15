"""Device class."""
import sys

import asyncssh  # type: ignore
from futurelog import FutureLogger

from app import utils
from app.deployers import (
    ConfigDeployer,
    GrainsDeployer,
    MinionDeployer,
    SystemdDeployer,
)
from app.exceptions import DeviceConnectionException, UnknownSonicVersionException
from app.logger import get_logger
from app.metrics import DEPLOYMENT_STATUS
from app.settings import CONF

LOGGER = get_logger(__name__)
FUTURE_LOGGER = FutureLogger(__name__, CONF.log_level)


class Device:
    """Define a SONiC device and define how to deploy Salt."""

    connected: bool
    hostname: str
    components: dict
    salt_master: str
    ssh: asyncssh
    sonic_version: str

    def __init__(self, hostname: str) -> None:
        """Initialize Device, including SSH connection."""
        self.hostname = hostname
        self.connected = False
        self.sonic_version = ""
        self.components = {}

    async def connect(self, user: str, password: str) -> None:
        """Connect to the device via SSH."""
        # set SSH connection for all deployers
        try:
            self.ssh = await asyncssh.connect(
                self.hostname, username=user, password=password, known_hosts=None, login_timeout=10
            )
            self.connected = True
        except (asyncssh.Error, Exception) as error:
            FUTURE_LOGGER.error(self.hostname, error)
            raise DeviceConnectionException(f"Connection failure: {self.hostname}") from error

        self.sonic_version = await self.get_running_sonic_version()
        if not self.sonic_version:
            raise UnknownSonicVersionException("failed to parse")

        FUTURE_LOGGER.info(self.hostname, f"SONiC version: {self.sonic_version}")
        self.components = {
            "minion": MinionDeployer(self.ssh, self.hostname, self.sonic_version),
            "grains": GrainsDeployer(self.ssh, self.hostname, self.sonic_version),
            "config": ConfigDeployer(self.ssh, self.hostname, self.sonic_version),
            "systemd": SystemdDeployer(self.ssh, self.hostname, self.sonic_version),
        }

    async def disconnect(self) -> None:
        """Disconnect SSH."""
        self.ssh.abort()
        await self.ssh.wait_closed()

    async def get_running_sonic_version(self) -> str:
        """Get SONiC version running on the device."""
        cmd1 = "cat /etc/sonic/sonic_release 2> /dev/null"
        cmd2 = (
            "show version 2> /dev/null | "
            r"sed -En 's/SONiC Software Version: SONiC\.([0-9]{6}).*/\1/p'"
        )

        response = await self.ssh.run(f"{cmd1} || {cmd2}")

        if response.exit_status != 0:
            FUTURE_LOGGER.info(self.hostname, "Command to determine SONiC version failed")
            return ""

        if not response.stdout.splitlines():
            FUTURE_LOGGER.info(self.hostname, "Failed to parse SONiC version")
            return ""

        return response.stdout.splitlines()[0]

    async def is_salt_ready(self) -> bool:
        """Check if Salt is properly installed."""
        status = True
        if self.components:
            for component in self.components.values():
                status = status and await component.check()
        else:
            status = False

        DEPLOYMENT_STATUS.labels(self.hostname, self.sonic_version).set(int(status))

        return status

    async def _stop_if_signal(self) -> None:
        if utils.stop_requested:
            LOGGER.warning("Exiting...")
            await self.disconnect()
            LOGGER.warning("SSH connection closed. Bye.")
            sys.exit(0)

    @staticmethod
    def _start_progress() -> None:
        LOGGER.debug("Starting: prevent SIGTERM")
        utils.in_progress = True

    async def _stop_progress(self) -> None:
        LOGGER.debug("Finished: allow SIGTERM and check if signal has been received")
        utils.in_progress = False
        await self._stop_if_signal()

    async def deploy_salt(self, force: bool = False) -> bool:
        """Deploy Salt on the device.

        It will stop if one step fails.
        """
        changed = False

        if not self.components:
            FUTURE_LOGGER.error(self.hostname, "missing deployer requirements")
            return False

        for name, component in self.components.items():
            # we deploy only if not already deployed
            if not force and await component.check():
                continue

            FUTURE_LOGGER.warning(self.hostname, "%s deployers started", name)
            self._start_progress()
            if not await component.deploy():
                DEPLOYMENT_STATUS.labels(self.hostname, self.sonic_version).set(-1)
                FUTURE_LOGGER.error(self.hostname, "%s deployer failed", name)
                await self._stop_progress()
                return False

            changed = True
            DEPLOYMENT_STATUS.labels(self.hostname, self.sonic_version).set(1)
            FUTURE_LOGGER.warning(self.hostname, "%s deployer succeeded", name)

            await self._stop_progress()

        if changed:
            restarted = await self.components["systemd"].restart()
            if restarted:
                FUTURE_LOGGER.warning(self.hostname, "salt-minion restarted")
            else:
                FUTURE_LOGGER.error(self.hostname, "salt-minion failed to restart")

        FUTURE_LOGGER.warning(self.hostname, "SUCCESS: %s", self.hostname)
        return True
