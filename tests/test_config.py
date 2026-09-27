import json

import pytest

from garmin_watch_mcp.config import ConfigError, load_settings
from garmin_watch_mcp.core import DEFAULT_TOKENSTORE


@pytest.fixture
def empty_store(tmp_path):
    return str(tmp_path / "tokens")


@pytest.fixture
def saved_store(tmp_path):
    store = tmp_path / "tokens"
    store.mkdir()
    (store / "garmin_tokens.json").write_text("{}")
    return str(store)


def creds(store):
    return {"GARMIN_EMAIL": "me@example.com", "GARMIN_PASSWORD": "s3cret", "GARMINTOKENS": store}


def test_minimal_env_uses_defaults(empty_store):
    settings = load_settings(creds(empty_store))
    assert settings.email == "me@example.com"
    assert settings.password == "s3cret"
    assert settings.tokenstore == empty_store
    assert settings.is_cn is False
    assert settings.langfuse_enabled is False
    assert settings.langfuse_capture_data is False


def test_default_tokenstore():
    env = {"GARMIN_EMAIL": "me@example.com", "GARMIN_PASSWORD": "pw"}
    assert load_settings(env).tokenstore == DEFAULT_TOKENSTORE


def test_secrets_not_in_repr():
    inline = json.dumps({"di_token": "tok-123"})
    text = repr(load_settings({"GARMIN_PASSWORD": "s3cret", "GARMINTOKENS": inline}))
    assert "s3cret" not in text and "tok-123" not in text


@pytest.mark.parametrize("missing", ["GARMIN_EMAIL", "GARMIN_PASSWORD"])
def test_missing_credential_without_tokens_raises(missing, empty_store):
    env = {k: v for k, v in creds(empty_store).items() if k != missing}
    with pytest.raises(ConfigError, match=missing) as info:
        load_settings(env)
    assert "garmin-watch-mcp login" in str(info.value)


def test_saved_tokens_make_credentials_optional(saved_store):
    settings = load_settings({"GARMINTOKENS": saved_store})
    assert settings.email is None and settings.password is None


def test_inline_token_json_counts_as_saved_tokens():
    assert load_settings({"GARMINTOKENS": ' {"di_token": "x"}'}).email is None


def test_require_auth_false_skips_check(empty_store):
    assert load_settings({"GARMINTOKENS": empty_store}, require_auth=False).email is None


def test_password_is_used_verbatim(empty_store):
    env = {**creds(empty_store), "GARMIN_PASSWORD": " pass word "}
    assert load_settings(env).password == " pass word "


def test_blank_email_counts_as_missing(empty_store):
    with pytest.raises(ConfigError, match="GARMIN_EMAIL"):
        load_settings({**creds(empty_store), "GARMIN_EMAIL": "   "})


@pytest.mark.parametrize("raw, expected", [("true", True), ("1", True), ("no", False), ("", False)])
def test_is_cn_flag(raw, expected, empty_store):
    assert load_settings({**creds(empty_store), "GARMIN_IS_CN": raw}).is_cn is expected


@pytest.mark.parametrize(
    "public, secret, enabled",
    [("pk", "sk", True), ("pk", "", False), ("", "sk", False), ("", "", False)],
)
def test_langfuse_enabled_only_with_both_keys(public, secret, enabled, empty_store):
    env = {**creds(empty_store), "LANGFUSE_PUBLIC_KEY": public, "LANGFUSE_SECRET_KEY": secret}
    assert load_settings(env).langfuse_enabled is enabled


@pytest.mark.parametrize(
    "raw, expected",
    [("true", True), ("1", True), ("YES", True), ("false", False), ("0", False), ("", False)],
)
def test_capture_flag_parsing(raw, expected, empty_store):
    env = {**creds(empty_store), "LANGFUSE_CAPTURE_DATA": raw}
    assert load_settings(env).langfuse_capture_data is expected
