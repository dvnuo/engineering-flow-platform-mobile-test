"""Actions on the device. Every one takes the driver and a locator the way
the generated code writes them; keyword arguments go to find()."""
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.common.exceptions import WebDriverException

from mobiletest.elements import DEFAULT_TIMEOUT, find, platform_of

ANDROID_KEYCODE_ENTER = 66


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


def _touch(driver):
    actions = ActionChains(driver)
    actions.w3c_actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
    return actions


def _press_at(driver, x, y, hold_ms):
    actions = _touch(driver)
    pointer = actions.w3c_actions.pointer_action
    pointer.move_to_location(int(x), int(y))
    pointer.pointer_down()
    pointer.pause(hold_ms / 1000.0)
    pointer.release()
    actions.perform()


def long_press(driver, locator, duration_ms=800, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is None:
        return None
    r = element.rect
    _press_at(driver, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, duration_ms)
    return element


def double_tap(driver, locator, **kwargs):
    element = _found(driver, locator, kwargs)
    if element is None:
        return None
    r = element.rect
    x, y = r["x"] + r["width"] / 2, r["y"] + r["height"] / 2
    actions = _touch(driver)
    pointer = actions.w3c_actions.pointer_action
    for _ in range(2):
        pointer.move_to_location(int(x), int(y))
        pointer.pointer_down()
        pointer.pause(0.05)
        pointer.release()
        pointer.pause(0.1)
    actions.perform()
    return element


def tap_point(driver, x=None, y=None, x_percent=None, y_percent=None):
    """A tap at absolute pixels, or at a percentage of the screen."""
    if x_percent is not None or y_percent is not None:
        size = driver.get_window_size()
        x = size["width"] * float(x_percent or 0) / 100.0
        y = size["height"] * float(y_percent or 0) / 100.0
    _press_at(driver, x or 0, y or 0, 100)


def swipe(driver, direction="up", distance=0.6, duration_ms=600):
    """A swipe across the screen's middle in the given direction."""
    size = driver.get_window_size()
    w, h = size["width"], size["height"]
    cx, cy = w / 2, h / 2
    span = distance / 2
    moves = {
        "up": ((cx, h * (0.5 + span)), (cx, h * (0.5 - span))),
        "down": ((cx, h * (0.5 - span)), (cx, h * (0.5 + span))),
        "left": ((w * (0.5 + span), cy), (w * (0.5 - span), cy)),
        "right": ((w * (0.5 - span), cy), (w * (0.5 + span), cy)),
    }
    (x1, y1), (x2, y2) = moves.get(direction, moves["up"])
    actions = _touch(driver)
    pointer = actions.w3c_actions.pointer_action
    pointer.move_to_location(int(x1), int(y1))
    pointer.pointer_down()
    pointer.pause(0.1)
    pointer.move_to_location(int(x2), int(y2))
    pointer.pause(duration_ms / 1000.0)
    pointer.release()
    actions.perform()


def scroll_to(driver, locator, direction="down", max_scrolls=5, **kwargs):
    """Swipe until the element is on screen, then return it."""
    kwargs.setdefault("timeout", 1)
    kwargs["optional"] = True
    for _ in range(max(int(max_scrolls), 0) + 1):
        element = find(driver, locator, **kwargs)
        if element is not None:
            return element
        swipe(driver, "up" if direction == "down" else "down" if direction == "up" else direction)
        time.sleep(0.3)
    kwargs["optional"] = False
    kwargs["timeout"] = DEFAULT_TIMEOUT
    return find(driver, locator, **kwargs)


def scroll_to_end(driver, direction="down", max_swipes=30, settle=0.3):
    """Swipe through a list or a long text until the screen stops changing,
    and return the number of swipes it took. For what a member scrolled to
    the bottom of when recording (terms to accept, a long form): the
    recording's fixed number of swipes lands elsewhere on another device."""
    before = _source(driver)
    swipes = 0
    for _ in range(max(int(max_swipes), 0)):
        swipe(driver, "up" if direction == "down" else "down" if direction == "up" else direction)
        swipes += 1
        time.sleep(settle)
        after = _source(driver)
        if after == before:
            return swipes
        before = after
    return swipes


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
