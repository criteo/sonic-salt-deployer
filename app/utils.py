"""Define some helpers."""
import hashlib
import json
import os
from typing import Any, Dict

import asyncssh  # type: ignore
import hvac  # type: ignore
import requests
from asyncssh.connection import SSHClientConnection  # type: ignore
from futurelog import FutureLogger

from app.exceptions import (
    APIException,
    ChecksumException,
    VaultPasswordNotFound,
    VaultUnreachable,
)
from app.settings import CONF

FUTURE_LOGGER = FutureLogger(__name__)

in_progress = False  # pylint: disable=C0103
stop_requested = False  # pylint: disable=C0103


async def upload_file(
    hostname: str,
    ssh: SSHClientConnection,
    local_resource: str,
    remote_dir: str,
    remote_name: str = "",
) -> bool:
    """Upload files to a remote device using SCP.

    :param hostname: hostname of the remote device
    :param ssh: asyncssh SSHClientConnection object which must be already connected to the device
    :param local_resource: filepath to push
    :param remote_dir: target path on the remote device
    :param remote_name: filename on remote device
    """
    # get local path and filename
    absolute_filepath = os.path.abspath(local_resource)
    filename = os.path.basename(local_resource)

    # Push grain script
    FUTURE_LOGGER.debug(hostname, "pushing %s to remote", local_resource)
    await asyncssh.scp(absolute_filepath, (ssh, "/tmp"))

    # Put it in the right place and change the owner to root:root.
    remote_filepath = os.path.join(remote_dir, remote_name)
    FUTURE_LOGGER.info(hostname, "move %s to %s", filename, remote_filepath)
    commands = {
        f"ensure {remote_dir} exists": f"sudo mkdir -p {remote_dir}",
        f"move file to {remote_dir}": f"sudo mv /tmp/{filename} {remote_filepath}",
        "change owner to root": f"sudo chown -R root:root {remote_filepath}",
    }

    for action, cmd in commands.items():
        FUTURE_LOGGER.debug(hostname, action)
        stdout = await ssh.run(cmd)
        if stdout.exit_status:
            return False

    return True


def get_sha256(filepath: str) -> str:
    """Get sha256 from a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as res:
        buffer = res.read()
        sha256.update(buffer)

    return sha256.hexdigest()


def extract_checksum(stdout: Any) -> str:
    """Extract checksum from stdout (SSH)."""
    try:
        checksum = stdout.split(" ")[0]
    except AttributeError as err:
        raise ChecksumException("unable to calculate checksum") from err

    return checksum


def request_api(request: str) -> Dict:
    """Request an API and return data in json format.

    :param request: URL request
    :param session: requests.session object
    """
    try:
        response = requests.get(request, timeout=60)
        response.raise_for_status()
    except (requests.HTTPError, requests.RequestException) as error:
        raise APIException(f"Error while contacting API: {request}") from error

    # load data as JSON
    try:
        json_data = response.json()
    except (json.JSONDecodeError, TypeError) as error:
        raise APIException(f"Error while decoding response from API: {request}") from error

    return json_data


def get_passwords(
    users: list, path: str, kv_v2: bool = False, mount_point: str = None
) -> dict[str, str]:
    """Get passwords from Vault."""
    passwords = {}

    vault_client = hvac.Client(url=CONF.vault_url)
    vault_client.auth.ldap.login(username=CONF.vault_login, password=CONF.vault_password)
    if not vault_client.is_authenticated():
        raise VaultUnreachable("Unable to connect to Vault")

    if kv_v2:
        result = vault_client.secrets.kv.read_secret_version(path=path, mount_point=mount_point)
    else:
        result = vault_client.read(path)

    vault_client.logout(revoke_token=True)

    for user in users:
        data = result["data"]["data"] if kv_v2 else result["data"]
        if user not in data:
            raise VaultPasswordNotFound(f"Unable to find {user}")

        passwords[user] = data[user]

    return passwords
