"""Exception for configuration."""


class InvalidConfiguration(RuntimeError):
    """Bad configuration."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Configuration error: {msg}")
