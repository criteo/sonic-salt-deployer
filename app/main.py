"""Start deployment on all devices."""
import asyncio
import getpass
import os
import signal
import sys
from typing import Any, Dict, List

import coloredlogs  # type: ignore
import jq  # type: ignore
from futurelog import FutureLogger
from prometheus_client import start_http_server  # type: ignore

from app import utils
from app.deployers import (
    ConfigDeployer,
    GrainsDeployer,
    MinionDeployer,
    SystemdDeployer,
)
from app.device import Device
from app.exceptions import APIException, DeviceConnectionException
from app.exceptions.config_exception import InvalidConfiguration
from app.logger import get_logger
from app.settings import CONF

LOGGER = get_logger(__name__)
FUTURE_LOGGER = FutureLogger(__name__, CONF.log_level)


DEFAULT_PASSWORD_SUFFIX = "_default"


def get_all_devices() -> list[str]:
    """Get SONiC device hostname list from a JSON API."""
    try:
        data = utils.request_api(CONF.inventory_url)
    except APIException as error:
        LOGGER.error("unable to get devices list: %s", error)
        return []

    try:
        devices = jq.compile(CONF.inventory_filter).input(data).all()  # pylint: disable=I1101
    except SyntaxError as error:
        raise InvalidConfiguration("JQ filter syntax error") from error

    LOGGER.debug("SONiC device list: %s", devices)

    if not devices:
        LOGGER.error("no devices found")
        return []

    if not all(devices):
        LOGGER.error("at least one device hostname is null or empty")
        return []

    return devices


def prepare_deployers() -> None:
    """Prepare all deployers."""
    # Download minion pex
    LOGGER.info("Downloading salt-minion pex files")
    MinionDeployer.download_minions()

    # Calculate checksum
    LOGGER.info("Calculating checksum of all files")
    GrainsDeployer.calculate_checksum()
    SystemdDeployer.calculate_checksum()

    # Prepare configuration
    LOGGER.info("Resolving DNS forwarders hostnames are valid")
    ConfigDeployer.prepare()


async def deploy_on_device(hostname: str, credentials: Dict) -> bool:
    """Deploy salt minion on one device."""
    FUTURE_LOGGER.warning(hostname, "********* %s *********", hostname)
    device = Device(hostname)

    # Try to connect with one user in the list
    for user, password in credentials.items():
        if user.endswith(DEFAULT_PASSWORD_SUFFIX):
            user = user[: -len(DEFAULT_PASSWORD_SUFFIX)]

        try:
            await device.connect(user, password)
            FUTURE_LOGGER.warning(
                hostname, "Successfully connected to %s with user '%s'", device.hostname, user
            )
            break
        except DeviceConnectionException as error:
            FUTURE_LOGGER.error(
                hostname, "Unable to connect to %s with user '%s': %s", device.hostname, user, error
            )

    if not device.connected:
        return False

    FUTURE_LOGGER.warning(hostname, "checking if minion needs to be installed")
    ready = await device.is_salt_ready()

    if CONF.dry_run:
        status = ready
    elif CONF.force or not ready:
        FUTURE_LOGGER.warning(hostname, "starting deployment")
        status = await device.deploy_salt(CONF.force)
    else:
        FUTURE_LOGGER.warning(hostname, "minion is already installed")
        status = True

    await device.disconnect()

    return status


def print_result(succeeded: List, failed: List) -> None:
    """Print deployment results."""
    if CONF.dry_run:
        ok_msg = "already_deployed"
        nok_msg = "to_deploy"
    else:
        ok_msg = "succeeded"
        nok_msg = "failed"

    LOGGER.info("%s: %s", ok_msg, succeeded)
    LOGGER.info("%s: %s", nok_msg, failed)

    LOGGER.warning(
        "********* FINISHED (%s: %s, %s: %s) *********",
        ok_msg,
        len(succeeded),
        nok_msg,
        len(failed),
    )


async def start_deployment(credentials: Dict, devices: List) -> None:
    """Start the deployment."""
    # deploy
    LOGGER.warning("Starting deployment")
    tasks = {}
    wait_tasks = []
    for hostname in devices:
        task = asyncio.ensure_future(deploy_on_device(hostname, credentials))
        wait_tasks.append(task)
        tasks[hostname] = task

    done, _ = await asyncio.wait(wait_tasks, return_when=asyncio.ALL_COMPLETED)

    # get result
    failed = []
    succeeded = []
    for hostname, task in tasks.items():
        if task not in done:
            raise RuntimeError("A task was incomplete, it should not have happen.")

        try:
            status = await task
        except RuntimeError as error:
            FUTURE_LOGGER.error(hostname, error)
            status = False

        if status:
            succeeded.append(hostname)
        else:
            failed.append(hostname)

        # consume all logs for current device
        FutureLogger.consume_all_logger_for(hostname)

    # consume logs
    FutureLogger.consume_all_logger()

    print_result(succeeded, failed)


def stop_request(_: int, __: Any) -> None:
    """Stop handler for SIGTERM.

    :param signum: signal number
    :param frame: None or a frame object. Represents execution frames
    """
    if not utils.in_progress:
        # we restart directly if there is no job in progress
        LOGGER.warning("Process %i exiting...", os.getpid())
        sys.exit(0)
    else:
        utils.stop_requested = True


def interruption_request(_: int, __: Any) -> None:
    """Stop handler for SIGTERM.

    :param signum: signal number
    :param frame: None or a frame object. Represents execution frames
    """
    LOGGER.warning("Process %i exiting...", os.getpid())
    sys.exit(0)


def _get_credentials() -> dict[str, str]:
    if CONF.is_vault_enabled():
        path = CONF.vault_secret_path
        credentials = utils.get_passwords(
            CONF.vault_device_usernames, path, kv_v2=True, mount_point="devices"
        )
    elif CONF.username and CONF.password:
        credentials = {CONF.username: CONF.password}
    else:
        user = input("Username: ")
        credentials = {
            user: getpass.getpass(prompt="Password: ", stream=None),
        }

    return credentials


async def start_app() -> None:
    """Prepare environment and start deployment."""
    signal.signal(signal.SIGTERM, stop_request)
    signal.signal(signal.SIGINT, stop_request)

    # pretty logging
    if CONF.pretty_logs:
        coloredlogs.install(fmt="%(name)s\t\t%(levelname)s\t\t%(message)s")

    credentials = _get_credentials()
    devices = CONF.devices or get_all_devices()

    if not devices:
        LOGGER.critical("No devices found")
        sys.exit(-1)

    start_http_server(CONF.prometheus_listen_port)

    # start the deployment
    if CONF.dry_run:
        LOGGER.warning("Dry-run mode enabled")

    prepare_deployers()

    await start_deployment(credentials, devices)


def main():
    """Entrypoint."""
    asyncio.run(start_app())


if __name__ == "__main__":
    main()
