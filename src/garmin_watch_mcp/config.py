"""Settings loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from garmin_watch_mcp.core import DEFAULT_TOKENSTORE, saved_tokens_exist

_TRUTHY = {"true", "1", "yes"}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    email: str | None
    password: str | None = field(repr=False)
    # A directory path, or the token JSON itself; either way a secret.
    tokenstore: str = field(repr=False)
    is_cn: bool
    langfuse_enabled: bool
    langfuse_capture_data: bool


def load_settings(env: Mapping[str, str] | None = None, *, require_auth: bool = True) -> Settings:
    """Build Settings from `env` (defaults to os.environ). Raises ConfigError.

    With `require_auth`, either saved tokens or GARMIN_EMAIL + GARMIN_PASSWORD must exist.
    """
    env = os.environ if env is None else env

    email = env.get("GARMIN_EMAIL", "").strip() or None
    password = env.get("GARMIN_PASSWORD", "") or None
    tokenstore = env.get("GARMINTOKENS", "").strip() or DEFAULT_TOKENSTORE

    if require_auth and not saved_tokens_exist(tokenstore):
        missing = [
            name
            for name, value in (("GARMIN_EMAIL", email), ("GARMIN_PASSWORD", password))
            if not value
        ]
        if missing:
            raise ConfigError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                f"No saved Garmin tokens were found at {tokenstore}; set the variables "
                "or run `garmin-watch-mcp login` first."
            )

    langfuse_enabled = bool(
        env.get("LANGFUSE_PUBLIC_KEY", "").strip() and env.get("LANGFUSE_SECRET_KEY", "").strip()
    )

    return Settings(
        email=email,
        password=password,
        tokenstore=tokenstore,
        is_cn=_flag(env, "GARMIN_IS_CN"),
        langfuse_enabled=langfuse_enabled,
        langfuse_capture_data=_flag(env, "LANGFUSE_CAPTURE_DATA"),
    )


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in _TRUTHY
