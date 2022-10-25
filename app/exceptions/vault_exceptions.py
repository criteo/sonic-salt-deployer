"""Exception for Device class."""


class VaultUnreachable(RuntimeError):
    """Exception found while trying to get passwords from Vault."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Unable to reach Vault: {msg}")


class VaultPasswordNotFound(RuntimeError):
    """Exception found while trying to get passwords from Vault."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Unable to reach Vault: {msg}")
