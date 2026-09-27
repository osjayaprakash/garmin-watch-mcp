"""MCP server exposing Garmin Connect health and activity data as read-only tools."""

from __future__ import annotations

import atexit
import logging
import sys
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from garmin_watch_mcp import formatting, tracing
from garmin_watch_mcp.config import ConfigError, Settings, load_settings
from garmin_watch_mcp.core.client import GarminClient
from garmin_watch_mcp.service import MAX_ACTIVITIES, MAX_RANGE_DAYS, HealthService

mcp = MCPServer(
    "garmin",
    instructions=(
        "Read-only access to Garmin watch data synced to Garmin Connect: daily summaries, "
        "sleep, heart rate, stress, Body Battery, HRV, training readiness, activities and "
        "devices. Dates are YYYY-MM-DD (or 'today'/'yesterday') and default to today in the "
        "server's local time zone. Durations are seconds, distances metres, speeds m/s. "
        "Data appears only after the watch syncs."
    ),
)

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

DateArg = Annotated[
    str | None,
    Field(description="Day as YYYY-MM-DD, 'today' or 'yesterday'. Defaults to today."),
]
StartDateArg = Annotated[
    str | None,
    Field(description=f"First day (YYYY-MM-DD). Defaults to end_date. Max {MAX_RANGE_DAYS} days."),
]
EndDateArg = Annotated[
    str | None, Field(description="Last day (YYYY-MM-DD, 'today', 'yesterday'). Defaults to today.")
]

_service: HealthService | None = None


def set_service(service: HealthService | None) -> None:
    global _service
    _service = service


def _get_service() -> HealthService:
    if _service is None:
        raise RuntimeError("HealthService is not configured; call main() or set_service().")
    return _service


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_daily_summary")
async def get_daily_summary(date: DateArg = None) -> dict[str, Any]:
    """Daily totals: steps, distance, calories, floors, heart rate, stress, Body Battery,
    intensity minutes, SpO2 and respiration."""
    day, raw = await _get_service().daily_summary(date)
    return formatting.daily_summary(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_sleep")
async def get_sleep(date: DateArg = None) -> dict[str, Any]:
    """Sleep for the night ending on `date`: stages (seconds), sleep score, start/end (UTC),
    overnight HRV, resting heart rate and Body Battery change."""
    day, raw = await _get_service().sleep(date)
    return formatting.sleep(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_heart_rate")
async def get_heart_rate(date: DateArg = None) -> dict[str, Any]:
    """Resting, min and max heart rate for a day, plus hourly (UTC) min/avg/max bpm."""
    day, raw = await _get_service().heart_rate(date)
    return formatting.heart_rate(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_stress")
async def get_stress(date: DateArg = None) -> dict[str, Any]:
    """Average and max stress (0-100) for a day, plus hourly (UTC) min/avg/max."""
    day, raw = await _get_service().stress(date)
    return formatting.stress(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_body_battery")
async def get_body_battery(
    start_date: StartDateArg = None, end_date: EndDateArg = None
) -> dict[str, Any]:
    """Body Battery per day: charged, drained, highest, lowest and latest level (0-100)."""
    return formatting.body_battery(await _get_service().body_battery(start_date, end_date))


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_hrv")
async def get_hrv(date: DateArg = None) -> dict[str, Any]:
    """Heart rate variability: last-night average, weekly average, baseline and status."""
    day, raw = await _get_service().hrv(date)
    return formatting.hrv(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_training_readiness")
async def get_training_readiness(date: DateArg = None) -> dict[str, Any]:
    """Latest training readiness score (0-100) for a day, with its contributing factors."""
    day, raw = await _get_service().training_readiness(date)
    return formatting.training_readiness(day, raw)


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("list_activities")
async def list_activities(
    start_date: StartDateArg = None,
    end_date: EndDateArg = None,
    limit: Annotated[int, Field(description=f"Max activities, 1-{MAX_ACTIVITIES}.")] = 20,
) -> dict[str, Any]:
    """Recorded activities (runs, rides, workouts...), newest first. With no dates, the most
    recent `limit` activities."""
    return formatting.activities(await _get_service().activities(start_date, end_date, limit))


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("get_activity")
async def get_activity(
    activity_id: Annotated[str, Field(description="activityId from list_activities.")],
) -> dict[str, Any]:
    """Summary of one activity: duration, distance, pace, heart rate, elevation, training
    effect."""
    return formatting.activity(await _get_service().activity(activity_id))


@mcp.tool(annotations=_READ_ONLY)
@tracing.traced("list_devices")
async def list_devices() -> dict[str, Any]:
    """Garmin devices registered to the account."""
    return formatting.devices(await _get_service().devices())


def build_client(settings: Settings) -> GarminClient:
    return GarminClient(
        settings.email, settings.password, tokenstore=settings.tokenstore, is_cn=settings.is_cn
    )


def main(argv: list[str] | None = None) -> None:
    # stdout carries the MCP protocol; every log line must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "login":
        from garmin_watch_mcp.login import run

        sys.exit(run(argv[1:]))
    if argv:
        print(
            f"garmin-watch-mcp: unknown argument {argv[0]!r}. Usage: garmin-watch-mcp [login]",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"garmin-watch-mcp: {exc}", file=sys.stderr)
        sys.exit(1)

    tracing.configure(settings)
    atexit.register(tracing.shutdown)
    set_service(HealthService(build_client(settings)))
    mcp.run("stdio")
