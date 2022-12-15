"""Deploy Salt minion executable."""
import re
import tempfile
import xml.etree.ElementTree as ET

import requests
from futurelog import FutureLogger

from app.deployers.deployer import Deployer
from app.exceptions import InvalidMinion, MinionDeployerException
from app.exceptions.config_exception import InvalidConfiguration
from app.logger import get_logger
from app.settings import CONF
from app.utils import extract_checksum, upload_file

LOGGER = get_logger(__name__)
FUTURE_LOGGER = FutureLogger(__name__, CONF.log_level)

PYTHON_SHEBANG = "#!/usr/bin/env python"


class MinionDeployer(Deployer):
    """Ensure the device has the salt-minion executable from Nexus."""

    filepath: tempfile.TemporaryDirectory
    checksum_sha256: dict[str, str] = {}

    @classmethod
    def download_minions(cls) -> None:
        """Get minion executables from local filesystem or Nexus and get the checksum."""
        if CONF.minion_files_local_directory:
            cls.filepath = CONF.minion_files_local_directory

            for sonic_version in CONF.sonic_versions:
                minion_file = f"{CONF.minion_files_local_directory}/salt-minion-{sonic_version}.pex"
                with open(minion_file, "r", encoding="utf-8") as minion_fd:
                    if PYTHON_SHEBANG not in minion_fd.readline():
                        raise InvalidMinion()

                with open(f"{minion_file}.sha256", "r", encoding="utf-8") as checksum_file:
                    cls.checksum_sha256[sonic_version] = checksum_file.read()

        elif CONF.minion_files_nexus_location:
            cls.filepath = tempfile.TemporaryDirectory()  # pylint: disable=R1732

            for sonic_version in CONF.sonic_versions:
                nexus_release = cls._get_latest_nexus_build()
                cls._download_minion_from_nexus(nexus_release, sonic_version)
                cls._get_checksum_from_nexus(nexus_release, sonic_version)

        else:
            raise InvalidConfiguration("minion files location was not specified")

    ##
    # Get minion executables from Nexus
    ##

    @classmethod
    def _get_latest_nexus_build(cls) -> str:
        try:
            response = requests.get(
                f"{CONF.minion_files_nexus_location}/maven-metadata.xml", timeout=60
            )
            root = ET.fromstring(response.text)
        except (requests.HTTPError, requests.RequestException) as error:
            raise MinionDeployerException("error while fetching metadata in Nexus") from error

        return root.find("versioning").find("latest").text  # type: ignore

    @classmethod
    def _get_checksum_from_nexus(cls, nexus_release, sonic_version) -> None:
        basename = f"salt-minion-{nexus_release}-{sonic_version}.pex"
        # get checksum
        try:
            checksum = requests.get(
                f"{CONF.minion_files_nexus_location}/{nexus_release}/{basename}.sha256",
                timeout=60,
            )
            checksum.raise_for_status()
        except (requests.HTTPError, requests.RequestException) as error:
            raise MinionDeployerException("error while fetching minion from nexus") from error

        if not re.match(r"^[A-Fa-f0-9]{64}$", checksum.text):
            raise MinionDeployerException("invalid checksum value")  # InconsistentChecksum

        cls.checksum_sha256[sonic_version] = checksum.text

    @classmethod
    def _download_minion_from_nexus(cls, nexus_release, sonic_version) -> None:
        basename = f"salt-minion-{nexus_release}-{sonic_version}.pex"
        minion_pex = requests.get(
            f"{CONF.minion_files_nexus_location}/{nexus_release}/{basename}",
            timeout=60,
        )
        minion_pex.raise_for_status()

        # check shebang matches with a python PEX
        shebang = next(minion_pex.iter_lines()).decode()
        if PYTHON_SHEBANG not in shebang:
            raise InvalidMinion()

        with open(f"{cls.filepath.name}/salt-minion-{sonic_version}", "wb") as pex_file:
            for chunk in minion_pex.iter_content(102400):
                pex_file.write(chunk)

    ##
    # Deploy and checks
    ##

    async def check(self) -> bool:
        """Check the minion has been well deployed."""
        checksum = ""
        commands = {
            "if minion is present": "ls /opt/salt/salt-minion",
            "if salt is executable": "if [ ! -x /opt/salt/salt-minion ]; then exit 1 ; fi",
            "file checksum": "sha256sum /opt/salt/salt-minion",
        }

        for action, cmd in commands.items():
            FUTURE_LOGGER.debug(self.hostname, "check %s", action)
            response = await self.ssh.run(cmd)

            if response.exit_status != 0:
                FUTURE_LOGGER.info(self.hostname, "check %s: failed", action)
                return False

            if action == "file checksum":
                checksum = extract_checksum(response.stdout)

        return checksum == self.checksum_sha256[self.sonic_version]

    async def deploy(self) -> bool:
        """Deploy the minion PEX in the right place."""
        # Push the minion
        uploaded = await upload_file(
            self.hostname,
            self.ssh,
            f"{self.filepath.name}/salt-minion-{self.sonic_version}",
            "/opt/salt",
            "salt-minion",
        )
        if not uploaded:
            return False

        # make the minion executable
        FUTURE_LOGGER.debug(self.hostname, "make the minion executable")
        response = await self.ssh.run("sudo chmod +x /opt/salt/salt-minion")
        if response.exit_status != 0:
            return False

        return await self.check()
