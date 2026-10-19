"""iOS's App Tracking Transparency prompt is answered when the session
starts, outside the scenario, the way mobile-auto's run start answers it for
a recording: deny (the default) presses Ask App Not to Track, allow presses
Allow, leave only reports it; any other system prompt is left alone, and a
screen without a prompt costs nothing but the watch."""
import json
import time
import types

import pytest
from selenium.common.exceptions import NoAlertPresentException, WebDriverException

from mobiletest import alerts, evidence, hooks, session

ATT = ["Ask App Not to Track", "Allow"]
ATT_TEXT = "Allow “Bank” to track your activity across other companies’ apps and websites?"
NOTIFICATIONS = ["Don’t Allow", "Allow"]


class AlertDriver:
    """An iOS driver with one screen: the alert on it (None for none), what
    comes after the first press, and whether the alert is seen only once the
    driver respects system alerts. A screen without an alert answers the way
    selenium reports W3C's "no such alert", or, with by_message, the way an
    older hub does."""

    def __init__(self, buttons=None, text="", after=None, hidden=False, active="com.example.bank", by_message=False, fail_look=False, fail_press=False, gone=False):
        self.buttons, self.text, self.after = buttons, text, after
        self.hidden, self.respect, self.active, self.by_message = hidden, False, active, by_message
        self.fail_look, self.fail_press, self.gone = fail_look, fail_press, gone
        self.presses, self.settings, self.scripts = [], [], []
        self.look_count = 0
        self.capabilities = {"platformName": "iOS"}
        self.session_id = "sess-1"
        self.switch_to = self
        self.quit_calls = 0

    def _visible(self):
        return self.buttons is not None and (self.respect or not self.hidden)

    def _no_alert(self):
        if self.by_message:
            return WebDriverException("An attempt was made to operate on a modal dialog when one was not open")
        return NoAlertPresentException("no such alert")

    @property
    def alert(self):
        if not self._visible():
            raise self._no_alert()
        return types.SimpleNamespace(text=self.text)

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if script == "mobile: activeAppInfo":
            return {"bundleId": self.active, "name": "Bank"}
        if script != "mobile: alert":
            raise AssertionError(f"unexpected script {script}")
        action = args[0]["action"]
        if action == "getButtons":
            self.look_count += 1
            if self.fail_look:
                raise WebDriverException("socket hang up")
            if not self._visible():
                raise self._no_alert()
            return list(self.buttons)
        if self.fail_press:
            raise WebDriverException("Could not find an alert button named Allow")
        if self.gone or not self._visible():
            raise self._no_alert()
        self.presses.append(action + ":" + args[0].get("buttonLabel", ""))
        self.buttons, self.text, self.after = self.after, "", None
        return None

    def update_settings(self, settings):
        self.respect = bool(settings.get("respectSystemAlerts"))
        self.settings.append(self.respect)

    def looks(self):
        """How many times the screen was looked at (presses not counted)."""
        return self.look_count

    def quit(self):
        self.quit_calls += 1


class Clock:
    """A fake time: sleeping moves it on."""

    def __init__(self):
        self.now, self.slept = 1000.0, 0.0

    def sleep(self, seconds):
        self.now += seconds
        self.slept += seconds

    def settle(self, driver, policy, window=10.0):
        return alerts.settle_launch_alerts(driver, policy, window, sleep=self.sleep, clock=lambda: self.now)


@pytest.mark.parametrize("policy, press, action", [
    (alerts.DENY, "dismiss:Ask App Not to Track", "pressed"),
    (alerts.ALLOW, "accept:Allow", "pressed"),
    (alerts.LEAVE, "", "left"),
])
def test_the_prompt_is_answered_the_way_the_policy_says(policy, press, action):
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    clock = Clock()
    record = clock.settle(driver, policy)
    assert record["seen"] and record["kind"] == "tracking" and record["action"] == action and record["buttons"] == ATT and record["text"] == ATT_TEXT
    assert ",".join(driver.presses) == press
    if press:
        assert record["button"] == press.split(":", 1)[1] and "no other prompt followed" in record["note"]
        # After the answer the screen is watched two seconds more, a second at a time.
        assert clock.slept == 2.0 and driver.looks() == 3
    else:
        assert "left on the screen" in record["note"] and clock.slept == 0
    assert driver.settings == [] and "error" not in record


@pytest.mark.parametrize("by_message", [False, True])
def test_a_screen_without_a_prompt_is_quiet(by_message):
    driver = AlertDriver(by_message=by_message)
    clock = Clock()
    record = clock.settle(driver, alerts.DENY)
    assert not record["seen"] and record["action"] == "none" and record["note"] == "no system prompt within 10s" and record["took_ms"] == 10000
    assert driver.presses == [] and clock.slept == 10.0 and driver.looks() == 11 and "error" not in record
    # A short window keeps the poll inside it.
    driver, clock = AlertDriver(), Clock()
    assert not clock.settle(driver, alerts.DENY, window=0.3)["seen"] and clock.slept == pytest.approx(0.3) and driver.looks() == 2


def test_other_prompts_are_reported_and_left_alone():
    driver = AlertDriver(buttons=NOTIFICATIONS, text="“Bank” Would Like to Send You Notifications")
    record = Clock().settle(driver, alerts.ALLOW)
    assert record["seen"] and record["kind"] == "other" and record["action"] == "left" and driver.presses == []
    assert "not App Tracking Transparency" in record["note"] and "Don’t Allow / Allow" in record["note"]
    # A prompt that follows the answered one is reported, not pressed.
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT, after=NOTIFICATIONS)
    record = Clock().settle(driver, alerts.DENY)
    assert record["action"] == "pressed" and record["button"] == "Ask App Not to Track" and record["followed_by"] == NOTIFICATIONS
    assert driver.presses == ["dismiss:Ask App Not to Track"] and "another system prompt followed" in record["note"]


@pytest.mark.parametrize("policy, press", [(alerts.DENY, "dismiss:Nicht erlauben"), (alerts.ALLOW, "accept:Erlauben")])
def test_the_prompt_is_told_by_its_text_in_another_language(policy, press):
    # The buttons are not the English ones; the text still names tracking the
    # activity. Deny is the first button, allow the last.
    driver = AlertDriver(buttons=["Nicht erlauben", "Erlauben"], text=ATT_TEXT)
    record = Clock().settle(driver, policy)
    assert record["kind"] == "tracking" and driver.presses == [press]


def test_the_driver_is_asked_to_respect_system_alerts_when_springboard_is_up():
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT, hidden=True, active=alerts.SPRINGBOARD)
    record = Clock().settle(driver, alerts.DENY)
    assert record["action"] == "pressed" and record["button"] == "Ask App Not to Track"
    # Switched on for the look and off again.
    assert driver.settings[:2] == [True, False] and not driver.respect
    # With the app in front the setting is left alone.
    driver = AlertDriver(hidden=True)
    Clock().settle(driver, alerts.DENY, window=1.0)
    assert driver.settings == []


def test_appium_failures_are_reported_never_raised():
    record = Clock().settle(AlertDriver(fail_look=True), alerts.DENY)
    assert not record["seen"] and record["action"] == "none" and "could not be checked" in record["note"] and "socket hang up" in record["error"]
    record = Clock().settle(AlertDriver(buttons=ATT, text=ATT_TEXT, fail_press=True), alerts.ALLOW)
    assert record["seen"] and record["action"] == "failed" and "could not be answered with Allow" in record["note"] and "error" in record
    record = Clock().settle(AlertDriver(buttons=ATT, text=ATT_TEXT, gone=True), alerts.DENY)
    assert record["action"] == "pressed" and "had gone before" in record["note"] and "error" not in record
    with pytest.raises(ValueError, match="deny, allow, or leave"):
        Clock().settle(AlertDriver(), "maybe")


def test_the_policy_comes_from_the_config_then_the_environment():
    assert alerts.tracking_policy({}, env={}) == "deny"
    assert alerts.tracking_policy({"tracking": " Allow "}, env={"MOBILETEST_TRACKING": "leave"}) == "allow"
    assert alerts.tracking_policy({"tracking": None}, env={"MOBILETEST_TRACKING": "leave"}) == "leave"
    assert alerts.tracking_policy({}, env={"MOBILETEST_TRACKING": ""}) == "deny"
    with pytest.raises(ValueError, match="the config's tracking: must be deny, allow, or leave, not 'maybe'"):
        alerts.tracking_policy({"tracking": "maybe"}, env={})
    with pytest.raises(ValueError, match="MOBILETEST_TRACKING must be"):
        alerts.tracking_policy({}, env={"MOBILETEST_TRACKING": "yes"})
    assert alerts.launch_alert_wait(env={}) == 10.0 and alerts.launch_alert_wait(env={"MOBILETEST_LAUNCH_ALERT_WAIT": "0"}) == 0
    assert alerts.launch_alert_wait(env={"MOBILETEST_LAUNCH_ALERT_WAIT": " 2.5 "}) == 2.5
    with pytest.raises(ValueError, match="MOBILETEST_LAUNCH_ALERT_WAIT"):
        alerts.launch_alert_wait(env={"MOBILETEST_LAUNCH_ALERT_WAIT": "soon"})


def _remote(monkeypatch, driver):
    """session.start's webdriver.Remote, answering the given driver."""
    calls = []

    def remote(hub, options=None):
        calls.append((hub, options))
        return driver

    monkeypatch.setattr(session.webdriver, "Remote", remote)
    monkeypatch.setenv("BROWSERSTACK_USERNAME", "user")
    monkeypatch.setenv("BROWSERSTACK_ACCESS_KEY", "not-a-real-key")
    monkeypatch.setenv("MOBILETEST_LAUNCH_ALERT_WAIT", "0.2")
    monkeypatch.delenv("MOBILETEST_TRACKING", raising=False)
    monkeypatch.delenv("MOBILETEST_FAKE_DRIVER", raising=False)
    return calls


def test_the_session_start_answers_the_prompt_on_ios(monkeypatch, capsys):
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    calls = _remote(monkeypatch, driver)
    got = session.start({"platform": "ios", "app": "bs://x"}, "buy-100-usd")
    assert got is driver and len(calls) == 1
    record = session.launch_alerts(driver)
    assert record["action"] == "pressed" and record["button"] == "Ask App Not to Track" and driver.presses == ["dismiss:Ask App Not to Track"]
    assert "launch alerts (buy-100-usd): the App Tracking Transparency prompt was answered with Ask App Not to Track" in capsys.readouterr().out
    # The config's policy, else the environment's.
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    _remote(monkeypatch, driver)
    session.start({"platform": "ios", "app": "bs://x", "tracking": "allow"}, "row")
    assert driver.presses == ["accept:Allow"]
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    _remote(monkeypatch, driver)
    monkeypatch.setenv("MOBILETEST_TRACKING", "leave")
    session.start({"platform": "ios", "app": "bs://x"}, "row")
    assert driver.presses == [] and session.launch_alerts(driver)["action"] == "left"
    # A failure of the watch is a warning line, never the session's failure.
    driver = AlertDriver(fail_look=True)
    _remote(monkeypatch, driver)
    assert session.start({"platform": "ios", "app": "bs://x"}, "row") is driver
    assert "warning: launch alerts (row): the screen could not be checked for a system prompt: Message: socket hang up" in capsys.readouterr().out


def test_the_session_start_leaves_android_alone_and_refuses_a_bad_policy(monkeypatch, capsys):
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    calls = _remote(monkeypatch, driver)
    assert session.start({"platform": "android", "app": "bs://x"}, "row") is driver
    assert driver.scripts == [] and session.launch_alerts(driver) is None and "launch alerts" not in capsys.readouterr().out
    # MOBILETEST_LAUNCH_ALERT_WAIT=0 switches the watch off on iOS too.
    monkeypatch.setenv("MOBILETEST_LAUNCH_ALERT_WAIT", "0")
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    _remote(monkeypatch, driver)
    monkeypatch.setenv("MOBILETEST_LAUNCH_ALERT_WAIT", "0")
    session.start({"platform": "ios", "app": "bs://x"}, "row")
    assert driver.scripts == [] and session.launch_alerts(driver) is None
    # A policy that is none of the three fails before a device is taken.
    calls = _remote(monkeypatch, AlertDriver())
    with pytest.raises(ValueError, match="deny, allow, or leave"):
        session.start({"platform": "ios", "app": "bs://x", "tracking": "maybe"}, "row")
    assert calls == []


def test_the_stand_in_driver_is_not_watched(monkeypatch):
    monkeypatch.setenv("MOBILETEST_FAKE_DRIVER", "1")
    driver = session.start({"platform": "ios", "app": "bs://x"}, "row")
    assert type(driver).__name__ == "FakeDriver" and session.launch_alerts(driver) is None


def test_the_evidence_keeps_the_record(tmp_path, monkeypatch):
    driver = AlertDriver(buttons=ATT, text=ATT_TEXT)
    driver.efp_launch_alerts = Clock().settle(driver, alerts.DENY)
    context = types.SimpleNamespace(
        row_id="ios/buy-100-usd", case_id="buy-100-usd", example="", platform="ios", cfg={"device": "iPhone 17"},
        run_label="", session_id="", collect_video=False, started_at=time.time(), script_path="features/ios/FX-12/buy-100-usd.feature", driver=driver,
    )
    context.recorder = evidence.start(context, str(tmp_path / "case"))
    hooks._write_evidence(context, "passed")
    evidence.stop()
    doc = json.loads((tmp_path / "case" / "evidence.json").read_text(encoding="utf-8"))
    assert doc["launch_alerts"]["action"] == "pressed" and doc["launch_alerts"]["button"] == "Ask App Not to Track" and doc["launch_alerts"]["policy"] == "deny"
    # A session that was not watched has no such key.
    context.driver = None
    context.recorder = evidence.start(context, str(tmp_path / "case2"))
    hooks._write_evidence(context, "passed")
    evidence.stop()
    assert "launch_alerts" not in json.loads((tmp_path / "case2" / "evidence.json").read_text(encoding="utf-8"))
