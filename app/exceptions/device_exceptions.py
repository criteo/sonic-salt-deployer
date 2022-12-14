"""Exception for Device class."""


class DeviceConnectionException(RuntimeError):
    """Exception found while trying to communicate with a device."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Connection issues with device: {msg}")


class UnknownSonicVersionException(RuntimeError):
    """Exception found when trying to get SONiC version."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"SONiC version unknown for device: {msg}")
