"""The test accounts come from one JSON file of profiles, never from chat."""
import json

import pytest

from mobiletest import hooks
from mobiletest.secrets import MissingSecret, profile, secret, secret_field, user_value


def _users(tmp_path, monkeypatch, users, chosen=None):
    path = tmp_path / "users.json"
    path.write_text(json.dumps(users), encoding="utf-8")
    monkeypatch.setenv("MOBILE_TEST_USERS_FILE", str(path))
    if chosen is None:
        monkeypatch.delenv("MOBILE_TEST_USER", raising=False)
    else:
        monkeypatch.setenv("MOBILE_TEST_USER", chosen)
    monkeypatch.delenv("MOBILE_SECRET_PASSWORD", raising=False)


def test_a_recorded_secret_name_reads_the_profile_field(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch, {"default": {"username": "uat-01", "password": "pw-default", "pin": "1234"}, "vip": {"username": "uat-vip", "password": "pw-vip"}})
    assert secret_field("MOBILE_SECRET_PASSWORD") == "password" and secret_field("MOBILE_SECRET_PIN") == "pin"
    assert secret("MOBILE_SECRET_PASSWORD") == "pw-default"
    assert user_value("username") == "uat-01"
    assert profile("vip") == {"username": "uat-vip", "password": "pw-vip"}
    monkeypatch.setenv("MOBILE_TEST_USER", "vip")
    assert secret("MOBILE_SECRET_PASSWORD") == "pw-vip" and user_value("username") == "uat-vip"
    # A value in the environment still wins: one secret without a file.
    monkeypatch.setenv("MOBILE_SECRET_PASSWORD", "from-env")
    assert secret("MOBILE_SECRET_PASSWORD") == "from-env"


def test_missing_file_profile_or_field_says_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("MOBILE_TEST_USERS_FILE", raising=False)
    monkeypatch.delenv("MOBILE_SECRET_PASSWORD", raising=False)
    with pytest.raises(MissingSecret, match="MOBILE_TEST_USERS_FILE"):
        secret("MOBILE_SECRET_PASSWORD")
    _users(tmp_path, monkeypatch, {"default": {"username": "uat-01"}}, chosen="vip")
    with pytest.raises(MissingSecret, match="no profile 'vip'; it has: default"):
        user_value("username")
    monkeypatch.setenv("MOBILE_TEST_USER", "default")
    with pytest.raises(MissingSecret, match="has no 'password'"):
        secret("MOBILE_SECRET_PASSWORD")


def test_the_job_can_name_the_build_to_test(monkeypatch):
    cfg = hooks.load_config("android", "EXAMPLE-1")
    configured = cfg["app"]
    monkeypatch.setenv("ANDROID_APP_ID", "bs://newer-build")
    assert hooks.load_config("android", "EXAMPLE-1")["app"] == "bs://newer-build"
    monkeypatch.delenv("ANDROID_APP_ID")
    assert hooks.load_config("android", "EXAMPLE-1")["app"] == configured
