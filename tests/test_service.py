import asyncio
from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from garmin_watch_mcp.core import (
    APIError,
    AuthenticationError,
    MFARequiredError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from garmin_watch_mcp.service import HealthService, parse_day, parse_range
from tests.fakes import FakeGarminClient

TODAY = date(2026, 9, 26)


@pytest.fixture
def client():
    return FakeGarminClient()


@pytest.fixture
def service(client):
    return HealthService(client, today=lambda: TODAY)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, TODAY),
        ("", TODAY),
        (" Today ", TODAY),
        ("yesterday", date(2026, 9, 25)),
        ("2026-01-02", date(2026, 1, 2)),
    ],
)
def test_parse_day(raw, expected):
    assert parse_day(raw, TODAY) == expected


@pytest.mark.parametrize("raw", ["26/09/2026", "tomorrow", "2026-13-01"])
def test_parse_day_rejects_bad_input(raw):
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        parse_day(raw, TODAY)


def test_parse_range_defaults_and_limits():
    assert parse_range(None, None, TODAY) == (TODAY, TODAY)
    assert parse_range("2026-09-20", None, TODAY) == (date(2026, 9, 20), TODAY)
    with pytest.raises(ToolError, match="after"):
        parse_range("2026-09-27", "2026-09-26", TODAY)
    with pytest.raises(ToolError, match="31 days"):
        parse_range("2026-08-01", "2026-09-26", TODAY)
    assert parse_range("2026-08-27", "2026-09-26", TODAY)[0] == date(2026, 8, 27)


async def test_logs_in_lazily_once(service, client):
    assert client.calls == []
    await service.daily_summary(None)
    await service.sleep("yesterday")
    assert client.count("authenticate") == 1
    assert ("user_summary", "2026-09-26") in client.calls
    assert ("sleep", "2026-09-25") in client.calls


async def test_concurrent_calls_share_one_login():
    client = FakeGarminClient(auth_delay=0.01)
    service = HealthService(client, today=lambda: TODAY)
    await asyncio.gather(service.heart_rate(None), service.stress(None), service.hrv(None))
    assert client.count("authenticate") == 1


async def test_relogin_once_on_expired_token(service, client):
    client.fail_next["devices"] = [AuthenticationError("devices")]
    assert await service.devices()
    assert client.count("authenticate") == 2
    assert client.count("devices") == 2


async def test_second_auth_failure_becomes_tool_error(service, client):
    client.fail_next["devices"] = [AuthenticationError("x"), AuthenticationError("x")]
    with pytest.raises(ToolError, match="GARMIN_EMAIL"):
        await service.devices()


@pytest.mark.parametrize(
    "exc, message",
    [
        (MFARequiredError("login"), "garmin-watch-mcp login"),
        (RateLimitError("x"), "Rate limited"),
        (NotFoundError("x"), "no such record"),
        (APIError(503, "get_devices"), "API error 503 for get_devices"),
        (NetworkError("x"), "Could not reach"),
    ],
)
async def test_errors_are_translated(service, client, exc, message):
    client.fail_next["authenticate"] = [exc]
    with pytest.raises(ToolError, match=message):
        await service.devices()


async def test_unknown_errors_propagate(service, client):
    client.fail_next["devices"] = [KeyError("boom")]
    with pytest.raises(KeyError):
        await service.devices()


async def test_body_battery_range(service, client):
    await service.body_battery("2026-09-20", None)
    assert ("body_battery", "2026-09-20", "2026-09-26") in client.calls


async def test_recent_activities_without_dates(service, client):
    result = await service.activities(None, None, 1)
    assert len(result) == 1
    assert ("activities", 0, 1) in client.calls


async def test_activities_by_date_sorted_and_limited(service, client):
    result = await service.activities("2026-09-20", "2026-09-26", 1)
    assert [a["activityId"] for a in result] == [111]
    assert ("activities_by_date", "2026-09-20", "2026-09-26") in client.calls


@pytest.mark.parametrize("limit", [0, 101])
async def test_activities_limit_checked(service, limit):
    with pytest.raises(ToolError, match="limit"):
        await service.activities(None, None, limit)


async def test_activity_id_must_be_numeric(service, client):
    with pytest.raises(ToolError, match="numeric"):
        await service.activity("abc")
    await service.activity(" 111 ")
    assert ("activity", "111") in client.calls


async def test_mfa_failure_is_not_retried(service, client):
    client.fail_next["authenticate"] = [MFARequiredError("login")]
    for _ in range(3):
        with pytest.raises(ToolError, match="garmin-watch-mcp login"):
            await service.devices()
    assert client.count("authenticate") == 1
    assert client.count("devices") == 0


async def test_mfa_after_expired_token_is_not_retried(service, client):
    await service.devices()
    client.fail_next["devices"] = [AuthenticationError("devices")]
    client.fail_next["authenticate"] = [MFARequiredError("login")]
    with pytest.raises(ToolError, match="uses MFA"):
        await service.devices()
    with pytest.raises(ToolError, match="uses MFA"):
        await service.sleep(None)
    assert client.count("authenticate") == 2
