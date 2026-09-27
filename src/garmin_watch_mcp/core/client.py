"""Async wrapper over the `garminconnect` library.

`garminconnect` is synchronous, so every call runs in a worker thread. Its
exceptions are translated into `core.exceptions` so the rest of the server
never depends on the library's error types.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)
from garminconnect.client import token_file_path

from garmin_watch_mcp.core.exceptions import (
    APIError,
    AuthenticationError,
    MFARequiredError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

DEFAULT_TOKENSTORE = "~/.garminconnect"


def is_inline_tokens(tokenstore: str) -> bool:
    """GARMINTOKENS may hold the token JSON itself instead of a directory path."""
    return tokenstore.lstrip().startswith("{")


def saved_tokens_exist(tokenstore: str) -> bool:
    if is_inline_tokens(tokenstore):
        return True
    try:
        return token_file_path(tokenstore).is_file()
    except (OSError, ValueError):
        return False


def _caused_by(exc: BaseException, kind: type[BaseException]) -> bool:
    while exc is not None:
        if isinstance(exc, kind):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def translate(exc: Exception, call: str) -> Exception:
    """Map a garminconnect exception to a core exception (or return it unchanged)."""
    # With no prompt_mfa, garminconnect raises an auth error saying "MFA Required".
    if _caused_by(exc, MFARequiredError) or "MFA Required" in str(exc):
        return MFARequiredError(call)
    if isinstance(exc, GarminConnectAuthenticationError):
        return AuthenticationError(call)
    if isinstance(exc, GarminConnectTooManyRequestsError):
        return RateLimitError(call)
    if isinstance(exc, GarminConnectNotFoundError):
        return NotFoundError(call)
    if isinstance(exc, GarminConnectConnectionError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return NetworkError(call) if status is None else APIError(status, call)
    return exc


class GarminClient:
    """Logs in with saved tokens (preferred) or email/password, then reads data."""

    def __init__(
        self,
        email: str | None,
        password: str | None,
        *,
        tokenstore: str = DEFAULT_TOKENSTORE,
        is_cn: bool = False,
        prompt_mfa: Callable[[], str] | None = None,
        garmin_factory: Callable[..., Any] = Garmin,
    ) -> None:
        self._email = email
        self._password = password
        self.tokenstore = tokenstore
        self.is_cn = is_cn
        self._prompt_mfa = prompt_mfa
        self._factory = garmin_factory
        self._api: Any | None = None

    def __repr__(self) -> str:
        return f"GarminClient(email={self._email!r}, is_cn={self.is_cn})"

    async def authenticate(self) -> None:
        """Log in from scratch. A fresh `Garmin` object is needed: it drops the password."""
        await asyncio.to_thread(self._login)

    def _login(self) -> None:
        api = self._factory(
            self._email, self._password, is_cn=self.is_cn, prompt_mfa=self._prompt_mfa
        )
        tokenstore = self.tokenstore
        if not is_inline_tokens(tokenstore):
            tokenstore = str(Path(tokenstore).expanduser())
        try:
            api.login(tokenstore)
        except Exception as exc:
            raise translate(exc, "login") from exc
        self._api = api

    def export_tokens(self) -> str:
        """Token JSON for GARMINTOKENS (e.g. to pass into a Docker container)."""
        return self._require_api().client.dumps()

    def _require_api(self) -> Any:
        if self._api is None:
            raise AuthenticationError("not logged in")
        return self._api

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        fn = getattr(self._require_api(), method)
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as exc:
            raise translate(exc, method) from exc

    async def user_summary(self, day: str) -> dict[str, Any]:
        return await self._call("get_user_summary", day)

    async def sleep(self, day: str) -> dict[str, Any]:
        return await self._call("get_sleep_data", day)

    async def heart_rates(self, day: str) -> dict[str, Any]:
        return await self._call("get_heart_rates", day)

    async def stress(self, day: str) -> dict[str, Any]:
        return await self._call("get_stress_data", day)

    async def body_battery(self, start: str, end: str) -> list[dict[str, Any]]:
        return await self._call("get_body_battery", start, end)

    async def hrv(self, day: str) -> dict[str, Any] | None:
        return await self._call("get_hrv_data", day)

    async def training_readiness(self, day: str) -> list[dict[str, Any]]:
        return await self._call("get_training_readiness", day)

    async def activities(self, start: int, limit: int) -> list[dict[str, Any]]:
        return await self._call("get_activities", start, limit)

    async def activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]:
        return await self._call("get_activities_by_date", start, end)

    async def activity(self, activity_id: str) -> dict[str, Any]:
        return await self._call("get_activity", activity_id)

    async def devices(self) -> list[dict[str, Any]]:
        return await self._call("get_devices")
