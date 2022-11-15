"""SONiC Salt Deployer settings."""
import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseSettings


def json_config_settings_source(settings: BaseSettings) -> dict[str, Any]:
    """Load configuration from json file."""
    encoding = settings.__config__.env_file_encoding
    try:
        return json.loads(Path("settings.json").read_text(encoding))
    except FileNotFoundError:
        return {}


class Settings(BaseSettings):
    """SONiC Salt Deployer configuration."""

    prometheus_listen_port: int = 9000
    force: bool = False
    dry_run: bool = False
    pretty_logs: bool = True
    log_level: str = "INFO"

    sonic_versions: list[str]

    minion_config: Optional[str]
    minion_config_file: str = "./minion.yml"
    dns_resolvers: list[str]
    resolve_dns_resolvers_hostname: bool = False

    minion_files_local_directory: Optional[str]
    minion_files_nexus_location: Optional[str]

    ##
    # SONiC devices list
    ##
    # via dynamic inventory
    inventory_url: Optional[str]
    # filter example: '.devices[] | select(.os|ascii_downcase == "sonic").host_name'
    inventory_filter: str = "."

    # or via static list of hostname
    devices: list[str] = []

    ##
    # Device SSH access
    ##
    # via static credentials
    username: Optional[str]
    password: Optional[str]

    # or credentials stored in Vault
    vault_url: Optional[str]
    vault_login: Optional[str]
    vault_password: Optional[str]
    vault_secret_path: Optional[str]
    vault_device_usernames: Optional[list[str]]

    def __init__(self, **kwargs: Any) -> None:
        """Override init to add post init."""
        super().__init__(**kwargs)
        self._post_init()

    def _post_init(self) -> None:
        """Set parameters after initialization."""
        if not self.minion_config:
            with open(self.minion_config_file, "r", encoding="utf-8") as config_file:
                self.minion_config = config_file.read()

    def is_vault_enabled(self) -> bool:
        """Return if the deployer is set to get creds from Hashicorp Vault."""
        enabled = all(
            [
                self.vault_url,
                self.vault_login,
                self.vault_password,
                self.vault_secret_path,
                self.vault_device_usernames,
            ]
        )

        return enabled

    class Config:  # pylint: disable=R0903
        """Pydantic settings."""

        env_file = "settings.env"
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            """Customise source of settings."""
            return (init_settings, json_config_settings_source, env_settings, file_secret_settings)


CONF = Settings()
