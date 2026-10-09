"""Actions on the device. Every one takes the driver and a locator the way
the generated code writes them; keyword arguments go to find().

Gestures send the same W3C actions as mobile-auto's replay of the scenario
script on the device (internal/mobileauto/commands/observe_actions.go in
engineering-flow-platform-tools): a swipe is move (0 ms) to start, down,
pause for hold_ms, move over duration_ms to end, pause for end_hold_ms, up;
a tap is move, down, pause for hold_ms, up. A point given in percent is
floor(window.x + window.width * percent / 100 + 0.5), as the device rounds
it. tests/test_literal_gestures.py pins the sequences both sides send.
"""
import math
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.command import Command

from mobiletest.elements import DEFAULT_TIMEOUT, find, platform_of

ANDROID_KEYCODE_ENTER = 66

# mobile-auto's swipe by direction: the finger's start and end, in percent of
# the window, and its default duration.
DIRECTION_PERCENTS = {
    "up": ((50, 80), (50, 20)),
    "down": ((50, 20), (50, 80)),
    "left": ((80, 50), (20, 50)),
    "right": ((20, 50), (80, 50)),
}
DEFAULT_SWIPE_MS = 500
# mobile-auto scroll-to's limit: how many swipes before it gives up.
DEFAULT_MAX_SCROLLS = 8


def _found(driver, locator, kwargs):
    """find() with the keyword arguments an action was given; None only when
    the step is optional."""
    return find(driver, locator, **kwargs)


def tap(driver, locator, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is not None:
        element.click()
    return element


def clear(driver, locator, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is not None:
        element.clear()
    return element


def type_text(driver, locator, text, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is not None:
        element.send_keys(str(text))
    return element


def _window(driver):
    """The window's x, y, width, and height, the frame the device's percent
    points are taken in."""
    try:
        rect = driver.get_window_rect()
        return float(rect.get("x") or 0), float(rect.get("y") or 0), float(rect["width"]), float(rect["height"])
    except (AttributeError, KeyError, TypeError, WebDriverException):
        size = driver.get_window_size()
        return 0.0, 0.0, float(size["width"]), float(size["height"])


def _px(origin, size, percent):
    """A coordinate in percent of the window, rounded the way the device
    rounds it (half away from zero)."""
    return int(math.floor(origin + size * float(percent) / 100 + 0.5))


def _point(window, x_percent, y_percent):
    wx, wy, ww, wh = window
    return _px(wx, ww, x_percent), _px(wy, wh, y_percent)


def _gesture(driver, steps):
    """Send one finger's W3C actions, built as the device's replay builds
    them: ("move", ms, x, y), ("down",), ("pause", ms), ("up",)."""
    actions = []
    for step in steps:
        kind = step[0]
        if kind == "move":
            actions.append({"type": "pointerMove", "duration": int(step[1]), "x": int(step[2]), "y": int(step[3])})
        elif kind == "down":
            actions.append({"type": "pointerDown", "button": 0})
        elif kind == "pause":
            if int(step[1]) > 0:
                actions.append({"type": "pause", "duration": int(step[1])})
        elif kind == "up":
            actions.append({"type": "pointerUp", "button": 0})
    source = {"type": "pointer", "id": "finger1", "parameters": {"pointerType": "touch"}, "actions": actions}
    driver.execute(Command.W3C_ACTIONS, {"actions": [source]})


def _center(element):
    r = element.rect
    return int(round(r["x"] + r["width"] / 2)), int(round(r["y"] + r["height"] / 2))


def long_press(driver, locator, duration_ms=800, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is None:
        return None
    x, y = _center(element)
    _gesture(driver, [("move", 0, x, y), ("down",), ("pause", duration_ms), ("up",)])
    return element


def double_tap(driver, locator, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is None:
        return None
    x, y = _center(element)
    _gesture(driver, [("move", 0, x, y), ("down",), ("up",), ("pause", 100), ("down",), ("up",)])
    return element


def tap_point(driver, x=None, y=None, x_percent=None, y_percent=None, hold_ms=0):
    """A tap at absolute pixels, or at a percentage of the window, resting
    hold_ms before lifting: what a coordinate tap of a recording replays as
    when no element could be named."""
    if x_percent is not None or y_percent is not None:
        x, y = _point(_window(driver), x_percent or 0, y_percent or 0)
    _gesture(driver, [("move", 0, x or 0, y or 0), ("down",), ("pause", hold_ms), ("up",)])


def swipe(driver, direction="up", distance=0.6, duration_ms=DEFAULT_SWIPE_MS, start=None, end=None, hold_ms=0, end_hold_ms=0):
    """A swipe. With start and end ((x, y) in percent of the window, as a
    scenario script records them) it is that swipe; otherwise it is
    mobile-auto's swipe in the direction the finger moves, across distance
    of the window through its middle."""
    if start is None or end is None:
        if direction not in DIRECTION_PERCENTS:
            direction = "up"
        if distance == 0.6:
            start, end = DIRECTION_PERCENTS[direction]
        else:
            half = float(distance) * 50
            start, end = {
                "up": ((50, 50 + half), (50, 50 - half)),
                "down": ((50, 50 - half), (50, 50 + half)),
                "left": ((50 + half, 50), (50 - half, 50)),
                "right": ((50 - half, 50), (50 + half, 50)),
            }[direction]
    window = _window(driver)
    x1, y1 = _point(window, *start)
    x2, y2 = _point(window, *end)
    _gesture(driver, [("move", 0, x1, y1), ("down",), ("pause", hold_ms), ("move", duration_ms or DEFAULT_SWIPE_MS, x2, y2), ("pause", end_hold_ms), ("up",)])


def _finger(direction):
    """The swipe that looks in a direction: down (further down the page) is a
    swipe up; left and right swipe that way."""
    return {"down": "up", "up": "down"}.get(direction, direction)


def scroll_to(driver, locator, direction="down", max_scrolls=DEFAULT_MAX_SCROLLS, **kwargs):
    """Swipe until the element is on screen, then return it: at most
    max_scrolls swipes, like mobile-auto scroll-to."""
    kwargs.setdefault("timeout", 1)
    kwargs["optional"] = True
    limit = max(int(max_scrolls), 0)
    for i in range(limit + 1):
        element = find(driver, locator, **kwargs)
        if element is not None:
            return element
        if i == limit:
            break
        swipe(driver, _finger(direction))
        time.sleep(0.3)
    kwargs["optional"] = False
    kwargs["timeout"] = DEFAULT_TIMEOUT
    return find(driver, locator, **kwargs)


def scroll_to_end(driver, direction="down", max_swipes=DEFAULT_MAX_SCROLLS, settle=0.3):
    """Swipe through a list or a long text until the screen stops changing,
    and return the number of swipes it took. Still changing after max_swipes
    is a failure, as on the device: the end was not reached."""
    before = _source(driver)
    swipes = 0
    for _ in range(max(int(max_swipes), 0)):
        swipe(driver, _finger(direction))
        swipes += 1
        time.sleep(settle)
        after = _source(driver)
        if after == before:
            return swipes
        before = after
    raise AssertionError(f"the screen was still changing after {swipes} swipes; the end was not reached")


def _source(driver):
    try:
        return str(driver.page_source)
    except WebDriverException:
        return ""


def back(driver):
    driver.back()


def hide_keyboard(driver):
    try:
        driver.hide_keyboard()
    except Exception:  # noqa: BLE001 - no keyboard is not a failure
        pass


def press_enter(driver):
    if platform_of(driver) == "ios":
        driver.switch_to.active_element.send_keys("\n")
    else:
        driver.press_keycode(ANDROID_KEYCODE_ENTER)


def press_keycode(driver, code):
    driver.press_keycode(int(code))


def _app_id(driver):
    caps = driver.capabilities or {}
    return caps.get("appPackage") or caps.get("appium:appPackage") or caps.get("bundleId") or caps.get("appium:bundleId")


def launch_app(driver):
    driver.activate_app(_app_id(driver))


def close_app(driver):
    driver.terminate_app(_app_id(driver))


def reset_app(driver):
    app = _app_id(driver)
    driver.terminate_app(app)
    driver.activate_app(app)


def activate_app(driver, app_id):
    driver.activate_app(app_id)


def terminate_app(driver, app_id):
    driver.terminate_app(app_id)


def open_deep_link(driver, url, package=None):
    args = {"url": url}
    if package:
        args["package"] = package
    driver.execute_script("mobile: deepLink", args)


def _permission_button(driver, accept):
    from mobiletest.elements import by_text

    if platform_of(driver) == "ios":
        labels = ["Allow", "Allow While Using App", "OK"] if accept else ["Don't Allow", "Deny"]
        buttons = [by_text(label, role="button") for label in labels]
    else:
        labels = ["Allow", "While using the app", "Only this time", "ALLOW"] if accept else ["Deny", "Don't allow", "DENY"]
        buttons = [by_text(label, role="button") for label in labels]
    for locator in buttons:
        element = find(driver, locator, optional=True, timeout=2)
        if element is not None:
            element.click()
            return True
    return False


def accept_permission(driver):
    _permission_button(driver, True)


def deny_permission(driver):
    _permission_button(driver, False)
