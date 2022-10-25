"""Exception for Deployer class."""


class InvalidMinion(RuntimeError):
    """Exception found while fetching minion pex."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__("Minion pex is invalid (sheebang does not match)")


class MinionDeployerException(RuntimeError):
    """Exception found while deploying the minion."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Minion deployer failed: {msg}")


class ConfigDeployerException(RuntimeError):
    """Exception found while deploying the minion."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Minion deployer failed: {msg}")
