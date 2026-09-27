"""A small async Garmin Connect client built on the `garminconnect` library."""

from garmin_watch_mcp.core.client import DEFAULT_TOKENSTORE, GarminClient, saved_tokens_exist
from garmin_watch_mcp.core.exceptions import (
    APIError,
    AuthenticationError,
    GarminError,
    MFARequiredError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

__all__ = [
    "DEFAULT_TOKENSTORE",
    "APIError",
    "AuthenticationError",
    "GarminClient",
    "GarminError",
    "MFARequiredError",
    "NetworkError",
    "NotFoundError",
    "RateLimitError",
    "saved_tokens_exist",
]
