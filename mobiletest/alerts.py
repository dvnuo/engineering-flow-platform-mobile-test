"""iOS's App Tracking Transparency prompt, answered when a session starts.

Every BrowserStack session installs the app afresh, so on iOS its first start
shows the prompt ("Allow 'X' to track your activity across other companies'
apps and websites?", with "Ask App Not to Track" and "Allow"), which
SpringBoard draws over the app; the app waits behind it, and so would the
first step. The session start answers it here, outside the scenario, the
same way mobile-auto's run start answers it for a recording in the Portal's
Mobile testing panel: a recording and its exported scenario see the same
first screen, and no script holds a tap on the prompt.

The policy is the config's `tracking:` (deny, allow, or leave), else
MOBILETEST_TRACKING, else deny; the screen is watched for
MOBILETEST_LAUNCH_ALERT_WAIT seconds (10). Any other system prompt is
reported with its buttons and left alone, since what it asks is the test's
business; the session-wide autoAcceptAlerts/autoDismissAlerts capabilities
are not used, because they would answer the app's own dialogs too.
"""
import os
import time

from selenium.common.exceptions import NoAlertPresentException, WebDriverException

DENY, ALLOW, LEAVE = "deny", "allow", "leave"
POLICIES = (DENY, ALLOW, LEAVE)
DENY_BUTTON = "Ask App Not to Track"
ALLOW_BUTTON = "Allow"
# In the prompt's text whatever the app's name; the second way to tell the
# prompt, on a device whose buttons are not the English ones.
TEXT_MARK = "track your activity"
DEFAULT_WINDOW = 10.0
# How often the screen is looked at, how long it is watched after the answer
# for a prompt that follows, and how many prompts one watch answers.
POLL = 1.0
GRACE = 2.0
PRESSES = 3
SPRINGBOARD = "com.apple.springboard"
_NO_ALERT = ("no such alert", "no alert is present", "no alert open", "modal dialog when one was not open")


def tracking_policy(config, env=None):
    """deny, allow, or leave: the config's tracking:, else MOBILETEST_TRACKING,
    else deny. Anything else is a ValueError, before a device is taken."""
    env = os.environ if env is None else env
    raw = config.get("tracking")
    source = "the config's tracking:"
    if raw is None or str(raw).strip() == "":
        raw = env.get("MOBILETEST_TRACKING", "")
        source = "MOBILETEST_TRACKING"
    policy = str(raw).strip().lower() or DENY
    if policy not in POLICIES:
        raise ValueError(f"{source} must be deny, allow, or leave, not {str(raw).strip()!r}")
    return policy


def launch_alert_wait(env=None):
    """How long the screen is watched for the prompt, in seconds:
    MOBILETEST_LAUNCH_ALERT_WAIT, 10 by default; 0 switches the watch off."""
    env = os.environ if env is None else env
    raw = str(env.get("MOBILETEST_LAUNCH_ALERT_WAIT", "")).strip()
    if not raw:
        return DEFAULT_WINDOW
    try:
        wait = float(raw)
    except ValueError:
        raise ValueError(f"MOBILETEST_LAUNCH_ALERT_WAIT must be a number of seconds, not {raw!r}") from None
    if wait < 0:
        raise ValueError("MOBILETEST_LAUNCH_ALERT_WAIT cannot be negative")
    return wait


def _no_alert(exc):
    """Whether exc is the driver's answer to an alert command when no alert
    is open: W3C's "no such alert", or the older protocol's status 27."""
    if isinstance(exc, NoAlertPresentException):
        return True
    text = str(exc).lower()
    return any(phrase in text for phrase in _NO_ALERT)


def alert_buttons(driver):
    """The labels of the open alert's buttons, in the driver's order (the
    XCUITest driver's mobile: alert getButtons, which sees SpringBoard's
    prompts); None when no alert is open."""
    try:
        value = driver.execute_script("mobile: alert", {"action": "getButtons"})
    except WebDriverException as exc:
        if _no_alert(exc):
            return None
        raise
    return [str(b).strip() for b in (value or []) if str(b).strip()]


def alert_text(driver):
    """The open alert's text; "" when none is open, or when the driver does
    not say (the text is a courtesy for the record)."""
    try:
        return str(driver.switch_to.alert.text or "").strip()
    except Exception:  # noqa: BLE001 - the buttons already told the prompt
        return ""


def press_alert_button(driver, action, label):
    """Press the open alert's button labelled label (action is accept or
    dismiss); False when no alert was open: the prompt had gone."""
    if action not in ("accept", "dismiss"):
        raise ValueError("alert action must be accept or dismiss")
    args = {"action": action}
    if label:
        args["buttonLabel"] = label
    try:
        driver.execute_script("mobile: alert", args)
    except WebDriverException as exc:
        if _no_alert(exc):
            return False
        raise
    return True


def _active_bundle_id(driver):
    try:
        info = driver.execute_script("mobile: activeAppInfo") or {}
        return str(info.get("bundleId") or "").strip().lower()
    except Exception:  # noqa: BLE001 - "" means the driver did not say
        return ""


def _look(driver):
    """(buttons, text) of the open alert; (None, "") when none is open. The
    driver answers the alert commands from the active application and does
    not list SpringBoard's prompts unless its respectSystemAlerts setting
    says so: when no alert is reported while SpringBoard is in front, the
    setting is switched on for one more look and off again."""
    buttons = alert_buttons(driver)
    if buttons is None and _active_bundle_id(driver) == SPRINGBOARD:
        try:
            driver.update_settings({"respectSystemAlerts": True})
        except Exception:  # noqa: BLE001 - a driver without the setting
            pass
        else:
            try:
                buttons = alert_buttons(driver)
            finally:
                try:
                    driver.update_settings({"respectSystemAlerts": False})
                except Exception:  # noqa: BLE001
                    pass
    if buttons is None:
        return None, ""
    return buttons, alert_text(driver)


def is_tracking_prompt(buttons, text):
    """The App Tracking Transparency prompt, by its deny button or, on a
    device in another language, by its text."""
    if any(DENY_BUTTON.lower() in str(b).lower() for b in buttons):
        return True
    return TEXT_MARK in str(text or "").lower()


def _pick(buttons, want, position):
    """The button to press: the one labelled want (whatever its case), else,
    when the prompt was told by its text alone, the one at position: deny is
    the prompt's first button, allow its last."""
    for b in buttons:
        if b.strip().lower() == want.lower():
            return b.strip()
    for b in buttons:
        if want.lower() in b.lower():
            return b.strip()
    if 0 <= position < len(buttons):
        return buttons[position].strip()
    return want


def settle_launch_alerts(driver, policy=DENY, window=DEFAULT_WINDOW, poll=None, grace=None, sleep=time.sleep, clock=time.monotonic):
    """Watch the screen for the App Tracking Transparency prompt for window
    seconds and answer it the way policy says (deny presses Ask App Not to
    Track, allow presses Allow, leave leaves it); then watch a little longer
    for a prompt that follows. Returns the record: policy, seen, kind
    (tracking or other), buttons, text, action (pressed, left, none, or
    failed), button, followed_by, took_ms, note, and error when an Appium
    failure stopped the watch (which never raises: a prompt that could not
    be checked must not fail a session whose device is up)."""
    if policy not in POLICIES:
        raise ValueError("tracking must be deny, allow, or leave")
    window = float(window) if window and float(window) > 0 else DEFAULT_WINDOW
    poll = min(float(poll) if poll and float(poll) > 0 else POLL, window)
    grace = min(float(grace) if grace and float(grace) > 0 else GRACE, window)
    started = clock()
    record = {"policy": policy, "seen": False, "action": "none"}

    def finish(note, error=None):
        record["took_ms"] = int((clock() - started) * 1000)
        record["note"] = note
        if error is not None:
            record["error"] = str(error)[:500]
        return record

    deadline = started + window
    presses = 0
    while True:
        try:
            buttons, text = _look(driver)
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            if record["action"] == "pressed":
                return finish(f"the screen could not be checked for a prompt after the answer: {str(exc)[:300]}", exc)
            return finish(f"the screen could not be checked for a system prompt: {str(exc)[:300]}", exc)
        if buttons is None:
            pass
        elif record["action"] == "pressed" and not is_tracking_prompt(buttons, text):
            record["followed_by"] = buttons
            return finish(f"the App Tracking Transparency prompt was answered with {record['button']}; another system prompt followed ({' / '.join(buttons)}) and was left on the screen")
        elif not is_tracking_prompt(buttons, text):
            record.update(seen=True, kind="other", buttons=buttons, text=text, action="left")
            return finish(f"a system prompt that is not App Tracking Transparency is on the screen ({' / '.join(buttons)}) and was left as it is")
        elif policy == LEAVE:
            record.update(seen=True, kind="tracking", buttons=buttons, text=text, action="left")
            return finish("the App Tracking Transparency prompt was left on the screen (tracking: leave)")
        else:
            if presses >= PRESSES:
                return finish(f"the App Tracking Transparency prompt is still on the screen after {presses} answers")
            presses += 1
            record.update(seen=True, kind="tracking", buttons=buttons, text=text)
            if policy == ALLOW:
                action, label = "accept", _pick(buttons, ALLOW_BUTTON, len(buttons) - 1)
            else:
                action, label = "dismiss", _pick(buttons, DENY_BUTTON, 0)
            try:
                pressed = press_alert_button(driver, action, label)
            except Exception as exc:  # noqa: BLE001 - reported, never raised
                record["action"] = "failed"
                return finish(f"the App Tracking Transparency prompt could not be answered with {label}: {str(exc)[:300]}", exc)
            record.update(action="pressed", button=label)
            if not pressed:
                return finish(f"the App Tracking Transparency prompt had gone before {label} was pressed")
            # Watch a little longer for a prompt that follows this one.
            deadline = clock() + grace
        remaining = deadline - clock()
        if remaining <= 0:
            if record["action"] == "pressed":
                return finish(f"the App Tracking Transparency prompt was answered with {record['button']}; no other prompt followed")
            return finish(f"no system prompt within {window:g}s")
        sleep(min(poll, remaining))
