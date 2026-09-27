import json
from types import SimpleNamespace

import pytest
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)

from garmin_watch_mcp.core import (
    APIError,
    AuthenticationError,
    GarminClient,
    MFARequiredError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    saved_tokens_exist,
)
from garmin_watch_mcp.core.client import translate


class FakeGarmin:
    """Stands in for garminconnect.Garmin; records constructor and login arguments."""

    instances: list["FakeGarmin"] = []
    login_error: Exception | None = None

    def __init__(self, email, password, *, is_cn, prompt_mfa):
        self.args = (email, password, is_cn, prompt_mfa)
        self.tokenstore = None
        self.raise_on_call: Exception | None = None
        self.client = SimpleNamespace(dumps=lambda: json.dumps({"di_token": "t"}))
        FakeGarmin.instances.append(self)

    def login(self, tokenstore):
        self.tokenstore = tokenstore
        if FakeGarmin.login_error is not None:
            raise FakeGarmin.login_error

    def get_user_summary(self, day):
        if self.raise_on_call:
            raise self.raise_on_call
        return {"calendarDate": day}

    def get_activities(self, start, limit):
        return [{"start": start, "limit": limit}]


@pytest.fixture(autouse=True)
def reset_fake():
    FakeGarmin.instances = []
    FakeGarmin.login_error = None


def make_client(**kwargs):
    return GarminClient("me@example.com", "pw", garmin_factory=FakeGarmin, **kwargs)


def with_status(exc, status):
    exc.response = SimpleNamespace(status_code=status)
    return exc


async def test_authenticate_builds_fresh_garmin_each_time():
    client = make_client(tokenstore="~/tokens", is_cn=True)
    await client.authenticate()
    await client.authenticate()
    assert len(FakeGarmin.instances) == 2
    first = FakeGarmin.instances[0]
    assert first.args[:3] == ("me@example.com", "pw", True)
    assert not first.tokenstore.startswith("~")


async def test_inline_tokens_passed_through_unchanged():
    inline = '{"di_token": "t"}'
    client = make_client(tokenstore=inline)
    await client.authenticate()
    assert FakeGarmin.instances[0].tokenstore == inline


async def test_calls_run_after_login_and_export_tokens():
    client = make_client()
    with pytest.raises(AuthenticationError):
        await client.user_summary("2026-09-26")
    await client.authenticate()
    assert await client.user_summary("2026-09-26") == {"calendarDate": "2026-09-26"}
    assert await client.activities(0, 5) == [{"start": 0, "limit": 5}]
    assert json.loads(client.export_tokens()) == {"di_token": "t"}


async def test_login_errors_translated():
    FakeGarmin.login_error = GarminConnectAuthenticationError(
        "MFA Required but no prompt_mfa mechanism supplied"
    )
    with pytest.raises(MFARequiredError):
        await make_client().authenticate()


async def test_call_errors_translated():
    client = make_client()
    await client.authenticate()
    FakeGarmin.instances[0].raise_on_call = GarminConnectTooManyRequestsError("429")
    with pytest.raises(RateLimitError):
        await client.user_summary("2026-09-26")


@pytest.mark.parametrize(
    "exc, expected",
    [
        (GarminConnectAuthenticationError("bad"), AuthenticationError),
        (GarminConnectTooManyRequestsError("slow"), RateLimitError),
        (GarminConnectNotFoundError("gone"), NotFoundError),
        (GarminConnectConnectionError("Connection error: reset"), NetworkError),
        (with_status(GarminConnectConnectionError("teapot"), 418), APIError),
    ],
)
def test_translate(exc, expected):
    assert isinstance(translate(exc, "call"), expected)


def test_translate_keeps_status_and_unknown_errors():
    err = translate(with_status(GarminConnectConnectionError("x"), 503), "get_devices")
    assert (err.status, err.call) == (503, "get_devices")
    unknown = KeyError("x")
    assert translate(unknown, "call") is unknown


def test_repr_hides_password():
    assert "pw" not in repr(make_client())


def test_saved_tokens_exist(tmp_path):
    assert not saved_tokens_exist(str(tmp_path))
    (tmp_path / "garmin_tokens.json").write_text("{}")
    assert saved_tokens_exist(str(tmp_path))
    assert saved_tokens_exist('{"di_token": "x"}')
