"""Exception for API requests."""


class APIException(RuntimeError):
    """Exception found while trying to request an API."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Failed request: {msg}")


class ChecksumException(RuntimeError):
    """Exception found while trying to get checkum."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Checksum issue: {msg}")


class UploadException(RuntimeError):
    """Exception while upload a file."""

    def __init__(self, msg: str) -> None:
        """Initialize."""
        super().__init__(f"Upload issue: {msg}")
