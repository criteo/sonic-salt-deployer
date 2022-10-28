"""Deployer main class definition.

Must be extended to be used.
"""
from asyncssh.connection import SSHClientConnection  # type: ignore


class Deployer:
    """Define the structure of a Deployer."""

    def __init__(self, ssh: SSHClientConnection, hostname: str, sonic_version: str) -> None:
        """Initialize the Deployer.

        It includes the SSH connection object to maintain and
        reuse the connection during the deployment.
        """
        self.ssh = ssh
        self.hostname = hostname
        self.sonic_version = sonic_version

    async def check(self) -> bool:
        """Check if Salt is deployed properly on the remote device."""
        raise NotImplementedError()

    async def deploy(self) -> bool:
        """Deploy Salt on the remote device.."""
        raise NotImplementedError()
