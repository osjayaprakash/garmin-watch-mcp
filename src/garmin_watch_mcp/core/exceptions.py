"""Errors raised by GarminClient, independent of the garminconnect library's own."""

from __future__ import annotations


class GarminError(Exception):
    """Base class for Garmin Connect client errors."""


class AuthenticationError(GarminError):
    """Credentials were rejected, or saved tokens expired and cannot be refreshed."""


class MFARequiredError(GarminError):
    """The account uses MFA and has no saved tokens; run `garmin-watch-mcp login`."""


class RateLimitError(GarminError):
    """Garmin Connect answered 429 Too Many Requests."""


class NotFoundError(GarminError):
    """The requested resource (e.g. an activity) does not exist."""


class APIError(GarminError):
    """Garmin Connect answered with an unexpected HTTP status."""

    def __init__(self, status: int | None, call: str) -> None:
        self.status = status
        self.call = call
        super().__init__(f"{call}: HTTP {status}")


class NetworkError(GarminError):
    """Garmin Connect could not be reached."""

    def __init__(self, call: str) -> None:
        self.call = call
        super().__init__(f"{call}: network error")
