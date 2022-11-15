"""Deployer for Salt grains."""
from typing import Dict

from futurelog import FutureLogger

from app import resources
from app.deployers.deployer import Deployer
from app.settings import CONF
from app.utils import extract_checksum, get_sha256, upload_file

FUTURE_LOGGER = FutureLogger(__name__, CONF.log_level)


class GrainsDeployer(Deployer):
    """Deploys grains update script.

    The systemd configuration is done in a dedicated deployer.
    """

    sha256: Dict = {}

    @classmethod
    def calculate_checksum(cls) -> None:
        """Calculate checksum for local file."""
        filepath = f"{resources.__path__[0]}/scripts/update_grains.py"
        cls.sha256["update_grains"] = get_sha256(filepath)

    async def check(self) -> bool:
        """Check the Salt grains script is present."""
        FUTURE_LOGGER.debug(self.hostname, "check if update_grains.py is present on remote")

        response = await self.ssh.run("sha256sum /opt/salt/update_grains.py")

        if response.exit_status:
            FUTURE_LOGGER.debug(self.hostname, "check failed")
            return False

        return self.sha256["update_grains"] == extract_checksum(response.stdout)

    async def deploy(self) -> bool:
        """Upload the Salt grains script."""
        FUTURE_LOGGER.debug(self.hostname, "pushing update_grains.py")
        await upload_file(
            self.hostname,
            self.ssh,
            f"{resources.__path__[0]}/scripts/update_grains.py",
            "/opt/salt/",
        )
        return await self.check()
