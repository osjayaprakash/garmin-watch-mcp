import json
from datetime import date

import pytest
from mcp import Client

from garmin_watch_mcp import server
from garmin_watch_mcp.service import HealthService
from tests.fakes import FakeGarminClient

TOOLS = {
    "get_daily_summary",
    "get_sleep",
    "get_heart_rate",
    "get_stress",
    "get_body_battery",
    "get_hrv",
    "get_training_readiness",
    "list_activities",
    "get_activity",
    "list_devices",
}
DATE_TOOLS = {
    "get_daily_summary",
    "get_sleep",
    "get_heart_rate",
    "get_stress",
    "get_hrv",
    "get_training_readiness",
}


@pytest.fixture
def fake_client():
    client = FakeGarminClient()
    server.set_service(HealthService(client, today=lambda: date(2026, 9, 26)))
    yield client
    server.set_service(None)


async def call(name, arguments=None):
    async with Client(server.mcp) as client:
        return await client.call_tool(name, arguments or {})


async def test_lists_read_only_tools(fake_client):
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == TOOLS
    assert all(t.annotations.read_only_hint for t in tools.values())
    for name in DATE_TOOLS:
        schema = tools[name].input_schema
        assert list(schema["properties"]) == ["date"]
        assert schema.get("required", []) == []
    assert tools["get_activity"].input_schema["required"] == ["activity_id"]
    assert tools["list_devices"].input_schema.get("properties", {}) == {}


async def test_get_daily_summary_defaults_to_today(fake_client):
    result = await call("get_daily_summary")
    assert not result.is_error
    body = result.structured_content
    assert body["date"] == "2026-09-26"
    assert body["totalSteps"] == 8421
    assert json.loads(result.content[0].text) == body


async def test_get_sleep(fake_client):
    body = (await call("get_sleep", {"date": "yesterday"})).structured_content
    assert body["date"] == "2026-09-25"
    assert body["sleep_score"] == 82


async def test_get_heart_rate_and_stress(fake_client):
    assert (await call("get_heart_rate")).structured_content["hourly"]
    assert (await call("get_stress")).structured_content["maxStressLevel"] == 88


async def test_get_body_battery(fake_client):
    body = (await call("get_body_battery", {"start_date": "2026-09-25"})).structured_content
    assert [d["date"] for d in body["days"]] == ["2026-09-25", "2026-09-26"]


async def test_get_hrv_and_readiness(fake_client):
    assert (await call("get_hrv")).structured_content["status"] == "BALANCED"
    assert (await call("get_training_readiness")).structured_content["score"] == 64


async def test_list_and_get_activity(fake_client):
    listed = (await call("list_activities", {"limit": 5})).structured_content
    assert listed["count"] == 2
    first = listed["activities"][0]["activityId"]
    detail = (await call("get_activity", {"activity_id": str(first)})).structured_content
    assert detail["maxHR"] == 172.0


async def test_list_devices(fake_client):
    body = (await call("list_devices")).structured_content
    assert body["devices"][0]["productDisplayName"] == "Forerunner 965"


async def test_tool_error_is_reported_not_raised(fake_client):
    result = await call("get_sleep", {"date": "last tuesday"})
    assert result.is_error
    assert "YYYY-MM-DD" in result.content[0].text


async def test_main_exits_on_missing_credentials(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "none"))
    with pytest.raises(SystemExit) as info:
        server.main([])
    assert info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "GARMIN_EMAIL" in captured.err


def test_main_rejects_unknown_argument(capsys):
    with pytest.raises(SystemExit) as info:
        server.main(["serve"])
    assert info.value.code == 2
    assert "login" in capsys.readouterr().err


def test_build_client_uses_settings(tmp_path):
    from garmin_watch_mcp.config import load_settings
    from garmin_watch_mcp.core.client import GarminClient

    settings = load_settings(
        {
            "GARMIN_EMAIL": "me@example.com",
            "GARMIN_PASSWORD": " pass word ",
            "GARMINTOKENS": str(tmp_path),
            "GARMIN_IS_CN": "true",
        }
    )
    client = server.build_client(settings)
    assert isinstance(client, GarminClient)
    assert client.is_cn is True
    assert client.tokenstore == str(tmp_path)
    assert "pass word" not in repr(client)
