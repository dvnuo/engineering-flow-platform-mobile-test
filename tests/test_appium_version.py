"""The Appium version each session asks BrowserStack for."""
from mobiletest.session import DEFAULT_APPIUM_VERSION, appium_version


def test_the_config_names_the_appium_version_else_the_environment_else_the_default(monkeypatch):
    monkeypatch.delenv("BROWSERSTACK_APPIUM_VERSION", raising=False)
    assert appium_version({}) == DEFAULT_APPIUM_VERSION == "2.19.0"
    monkeypatch.setenv("BROWSERSTACK_APPIUM_VERSION", "2.12.1")
    assert appium_version({}) == "2.12.1"
    assert appium_version({"appium_version": "3.5.2"}) == "3.5.2"
