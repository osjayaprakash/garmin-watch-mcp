"""Hits the real Garmin Connect API. Run with: uv run pytest -m live"""

import pytest
from mcp import Client

from garmin_watch_mcp import server
from garmin_watch_mcp.config import ConfigError, load_settings
from garmin_watch_mcp.service import HealthService


def _settings_or_none():
    try:
        return load_settings()
    except ConfigError:
        return None


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        _settings_or_none() is None,
        reason="needs saved tokens (garmin-watch-mcp login) or GARMIN_EMAIL and GARMIN_PASSWORD",
    ),
]


async def test_live_devices_and_daily_summary():
    server.set_service(HealthService(server.build_client(load_settings())))
    try:
        async with Client(server.mcp) as mcp_client:
            devices = await mcp_client.call_tool("list_devices", {})
            assert not devices.is_error, devices.content
            summary = await mcp_client.call_tool("get_daily_summary", {"date": "yesterday"})
            assert not summary.is_error, summary.content
            assert summary.structured_content["date"]
            activities = await mcp_client.call_tool("list_activities", {"limit": 3})
            assert not activities.is_error, activities.content
    finally:
        server.set_service(None)
