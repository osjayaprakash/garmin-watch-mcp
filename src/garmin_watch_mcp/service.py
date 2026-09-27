"""HealthService: date handling, lazy login and error mapping over the Garmin client."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import Any, Protocol, TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from garmin_watch_mcp import tracing
from garmin_watch_mcp.core import (
    APIError,
    AuthenticationError,
    MFARequiredError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)

T = TypeVar("T")

MAX_RANGE_DAYS = 31
MAX_ACTIVITIES = 100


class GarminAPI(Protocol):
    """The subset of core.client.GarminClient that HealthService uses."""

    async def authenticate(self) -> None: ...
    async def user_summary(self, day: str) -> dict[str, Any]: ...
    async def sleep(self, day: str) -> dict[str, Any]: ...
    async def heart_rates(self, day: str) -> dict[str, Any]: ...
    async def stress(self, day: str) -> dict[str, Any]: ...
    async def body_battery(self, start: str, end: str) -> list[dict[str, Any]]: ...
    async def hrv(self, day: str) -> dict[str, Any] | None: ...
    async def training_readiness(self, day: str) -> list[dict[str, Any]]: ...
    async def activities(self, start: int, limit: int) -> list[dict[str, Any]]: ...
    async def activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]: ...
    async def activity(self, activity_id: str) -> dict[str, Any]: ...
    async def devices(self) -> list[dict[str, Any]]: ...


def parse_day(value: str | None, today: date) -> date:
    """Accept None/'today', 'yesterday', or YYYY-MM-DD."""
    text = (value or "").strip().lower()
    if text in ("", "today"):
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ToolError(
            f"Invalid date {value!r}; use YYYY-MM-DD, 'today' or 'yesterday'."
        ) from None


def parse_range(start: str | None, end: str | None, today: date) -> tuple[date, date]:
    """Resolve a date range. A missing start means the same day as end."""
    last = parse_day(end, today)
    first = parse_day(start, today) if start else last
    if first > last:
        raise ToolError(f"start_date {first} is after end_date {last}.")
    if (last - first).days >= MAX_RANGE_DAYS:
        raise ToolError(f"Date ranges are limited to {MAX_RANGE_DAYS} days.")
    return first, last


def _to_tool_error(exc: Exception) -> ToolError | None:
    """Translate a Garmin client error into a user-facing ToolError."""
    if isinstance(exc, MFARequiredError):
        return ToolError(
            "This Garmin account uses MFA. Run `garmin-watch-mcp login` in a terminal once to "
            "save tokens, then restart the MCP client."
        )
    if isinstance(exc, AuthenticationError):
        return ToolError(
            "Garmin Connect login failed. Check GARMIN_EMAIL and GARMIN_PASSWORD, or run "
            "`garmin-watch-mcp login` to refresh the saved tokens."
        )
    if isinstance(exc, RateLimitError):
        return ToolError("Rate limited by Garmin Connect. Wait a few minutes and try again.")
    if isinstance(exc, NotFoundError):
        return ToolError("Garmin Connect has no such record.")
    if isinstance(exc, APIError):
        return ToolError(f"Garmin Connect API error {exc.status} for {exc.call}.")
    if isinstance(exc, NetworkError):
        return ToolError("Could not reach Garmin Connect.")
    return None


class HealthService:
    """Lazy login, re-login on expiry, and argument checking over a Garmin client."""

    def __init__(self, client: GarminAPI, *, today: Callable[[], date] = date.today) -> None:
        self._client = client
        self._today = today
        self._auth_lock = asyncio.Lock()
        self._authenticated = False
        # Set once login needs an MFA code. Retrying would only re-trigger Garmin's MFA
        # (a new code each time) and its login rate limit, so fail fast until restart.
        self._mfa_required = False

    def day(self, value: str | None) -> str:
        return parse_day(value, self._today()).isoformat()

    async def daily_summary(self, day: str | None) -> tuple[str, dict[str, Any]]:
        d = self.day(day)
        return d, await self._request("user_summary", self._client.user_summary, d)

    async def sleep(self, day: str | None) -> tuple[str, dict[str, Any]]:
        d = self.day(day)
        return d, await self._request("sleep", self._client.sleep, d)

    async def heart_rate(self, day: str | None) -> tuple[str, dict[str, Any]]:
        d = self.day(day)
        return d, await self._request("heart_rates", self._client.heart_rates, d)

    async def stress(self, day: str | None) -> tuple[str, dict[str, Any]]:
        d = self.day(day)
        return d, await self._request("stress", self._client.stress, d)

    async def hrv(self, day: str | None) -> tuple[str, dict[str, Any] | None]:
        d = self.day(day)
        return d, await self._request("hrv", self._client.hrv, d)

    async def training_readiness(self, day: str | None) -> tuple[str, list[dict[str, Any]]]:
        d = self.day(day)
        return d, await self._request("training_readiness", self._client.training_readiness, d)

    async def body_battery(self, start: str | None, end: str | None) -> list[dict[str, Any]]:
        first, last = parse_range(start, end, self._today())
        return await self._request(
            "body_battery", self._client.body_battery, first.isoformat(), last.isoformat()
        )

    async def activities(
        self, start: str | None, end: str | None, limit: int
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= MAX_ACTIVITIES:
            raise ToolError(f"limit must be between 1 and {MAX_ACTIVITIES}.")
        if start is None and end is None:
            return await self._request("activities", self._client.activities, 0, limit)
        first, last = parse_range(start, end, self._today())
        found = await self._request(
            "activities_by_date",
            self._client.activities_by_date,
            first.isoformat(),
            last.isoformat(),
        )
        found = sorted(found, key=lambda a: a.get("startTimeGMT") or "", reverse=True)
        return found[:limit]

    async def activity(self, activity_id: str) -> dict[str, Any]:
        text = activity_id.strip()
        if not text.isdigit():
            raise ToolError(f"activity_id must be numeric (from list_activities), got {text!r}.")
        return await self._request("activity", self._client.activity, text)

    async def devices(self) -> list[dict[str, Any]]:
        return await self._request("devices", self._client.devices)

    async def _authenticate(self, *, force: bool) -> None:
        async with self._auth_lock:
            if self._authenticated and not force:
                return
            if self._mfa_required:
                raise MFARequiredError("login")
            self._authenticated = False
            try:
                await self._client.authenticate()
            except MFARequiredError:
                self._mfa_required = True
                raise
            self._authenticated = True

    async def _request(self, method: str, fn: Callable[..., Awaitable[T]], *args: Any) -> T:
        async with tracing.span(f"garmin.{method}"):
            try:
                return await self._call_with_reauth(fn, *args)
            except Exception as exc:
                tool_error = _to_tool_error(exc)
                if tool_error is None:
                    raise
                raise tool_error from exc

    async def _call_with_reauth(self, fn: Callable[..., Awaitable[T]], *args: Any) -> T:
        await self._authenticate(force=False)
        try:
            return await fn(*args)
        except AuthenticationError:
            pass  # token expired: log in again and retry once
        await self._authenticate(force=True)
        return await fn(*args)
