"""Deployer for the configuration."""
from typing import List

import dns.resolver
from futurelog import FutureLogger

from app.deployers.deployer import Deployer
from app.exceptions import ConfigDeployerException
from app.logger import get_logger
from app.settings import CONF
from app.utils import upload_file

LOGGER = get_logger(__name__)
FUTURE_LOGGER = FutureLogger(__name__, CONF.log_level)


class ConfigDeployer(Deployer):
    """Deploys configuration for DNS and minion."""

    resolv_conf: str

    async def _check_dns_configuration(self) -> bool:
        """Check /etc/resolv.conf configuration."""
        FUTURE_LOGGER.debug(self.hostname, "check DNS servers configuration")

        response = await self.ssh.run("cat /etc/resolv.conf")
        result = response.stdout.rstrip()

        if result != self.resolv_conf:
            FUTURE_LOGGER.info(self.hostname, "check DNS servers configuration: failed")
            return False

        return True

    async def _check_no_automatic_changes_allowed(self) -> bool:
        """Check if automatic modification on /etc/resolv.conf are disabled."""
        FUTURE_LOGGER.debug(self.hostname, "check automatic changes on resolv.conf disabled")

        response = await self.ssh.run("grep 'resolvconf=NO' /etc/resolvconf.conf")

        if response.exit_status != 0:
            FUTURE_LOGGER.info(
                self.hostname, "check automatic changes on resolv.conf disabled: failed"
            )
            return False

        return True

    async def _check_minion_configuration(self) -> bool:
        """Check minion configuration."""
        FUTURE_LOGGER.debug(self.hostname, "check minion configuration")

        response = await self.ssh.run("sudo cat /etc/salt/minion")
        result = response.stdout.rstrip()
        if result != CONF.minion_config.rstrip():
            FUTURE_LOGGER.info(self.hostname, "check minion configuration: failed")
            return False

        return True

    async def check(self) -> bool:
        """Check the configuration is up to date."""
        checks = [
            await self._check_dns_configuration(),
            await self._check_no_automatic_changes_allowed(),
            await self._check_minion_configuration(),
        ]
        return all(checks)

    @classmethod
    def prepare(cls) -> None:
        """Get all necessary information to run the deployer."""
        # prepare /etc/resolv.conf
        dns_servers = cls._get_dns_resolvers()
        cls.resolv_conf = cls._construct_dns(dns_servers)

    @staticmethod
    def _get_dns_resolvers() -> List:
        """Return valid DNS resolvers only."""
        if not CONF.resolve_dns_resolvers_hostname:
            return CONF.dns_resolvers

        dns_resolvers = set()
        for hostname in CONF.dns_resolvers:
            try:
                answers = dns.resolver.query(hostname, "A")
            except dns.resolver.NXDOMAIN:
                LOGGER.debug("%s does not exist", hostname)
                continue

            dns_resolvers.update([answer.address for answer in answers])

        if not dns_resolvers:
            raise ConfigDeployerException("No DNS servers found.")

        return sorted(dns_resolvers)

    @staticmethod
    def _construct_dns(dns_servers: List) -> str:
        dns_conf = [f"nameserver {dns}" for dns in dns_servers]
        return "\n".join(dns_conf)

    async def _dns_configuration(self) -> bool:
        """Push DNS configuration and disable automatic update by the DHCP.

        details here: https://wiki.debian.org/resolv.conf
        """
        commands = {
            "configure DNS servers": f"echo '{self.resolv_conf}' | sudo tee /etc/resolv.conf",
            "disable automatic changes": "echo 'resolvconf=NO' | sudo tee /etc/resolvconf.conf",
        }

        for action, cmd in commands.items():
            FUTURE_LOGGER.debug(self.hostname, action)
            response = await self.ssh.run(cmd)
            if response.exit_status != 0:
                FUTURE_LOGGER.info(self.hostname, "%s: failed", action)
                return False

        return True

    async def _minion_configuration(self) -> bool:
        """Push DNS configuration and disable automatic update by the DHCP.

        details here: https://wiki.debian.org/resolv.conf
        """
        await upload_file(self.hostname, self.ssh, CONF.minion_config_file, "/etc/salt/", "minion")

        commands = {
            "change permission": "sudo chmod 600 /etc/salt/minion",
            "get back pki after an upgrade": (
                "if [ ! -d /etc/sonic/salt ] && [ -d /etc/sonic/old_config/salt ] ; "
                "then sudo cp -r /etc/sonic/old_config/salt /etc/sonic/ ; fi"
            ),
        }

        for action, cmd in commands.items():
            FUTURE_LOGGER.debug(self.hostname, action)
            response = await self.ssh.run(cmd)
            if response.exit_status != 0:
                FUTURE_LOGGER.info(self.hostname, "%s: failed", action)
                return False

        # request the restart of the minion if necessary
        response = await self.ssh.run("sudo systemctl is-active salt-minion.service")
        if response.exit_status == 0:
            response = await self.ssh.run("sudo systemctl restart salt-minion")
            if response.exit_status != 0:
                return False

        return True

    async def deploy(self) -> bool:
        """Push the configuration."""
        if not await self._dns_configuration() or not await self._minion_configuration():
            return False

        return await self.check()
