"""Finding elements: a locator with fallbacks, polled until one matches.

A locator is either an Appium (by, value) tuple, or one of by_text, by_name,
by_role, which resolve per platform when they are used. The primary locator
is the one the recording named; when only a fallback matches, the run passes
and the match is recorded as drift, so the primary can be fixed before it
breaks a test.
"""
import contextlib
import math
import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    InvalidSelectorException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

from mobiletest import evidence

DEFAULT_TIMEOUT = 10
POLL_SECONDS = 0.5

# Roles the suites use, per platform. Unknown roles fall back to any element.
ANDROID_ROLES = {
    "button": "android.widget.Button",
    "text": "android.widget.TextView",
    "input": "android.widget.EditText",
    "image": "android.widget.ImageView",
    "checkbox": "android.widget.CheckBox",
    "switch": "android.widget.Switch",
    "radio": "android.widget.RadioButton",
    "link": "android.widget.TextView",
    "tab": "android.widget.TextView",
    "list": "androidx.recyclerview.widget.RecyclerView",
}
IOS_ROLES = {
    "button": "XCUIElementTypeButton",
    "text": "XCUIElementTypeStaticText",
    "input": "XCUIElementTypeTextField",
    "secure_input": "XCUIElementTypeSecureTextField",
    "image": "XCUIElementTypeImage",
    "checkbox": "XCUIElementTypeSwitch",
    "switch": "XCUIElementTypeSwitch",
    "radio": "XCUIElementTypeButton",
    "link": "XCUIElementTypeLink",
    "tab": "XCUIElementTypeButton",
    "list": "XCUIElementTypeTable",
    "cell": "XCUIElementTypeCell",
}


class ElementNotFound(AssertionError):
    pass


def _quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def platform_of(driver):
    caps = getattr(driver, "capabilities", None) or {}
    return str(caps.get("platformName") or caps.get("appium:platformName") or "").lower()


class Locator:
    """A platform-independent locator: candidates() gives the Appium locators
    to try, most exact first."""

    def candidates(self, platform):
        raise NotImplementedError

    def __repr__(self):
        return self.describe()

    def describe(self):
        raise NotImplementedError


class ByText(Locator):
    def __init__(self, text, role=None):
        self.text = str(text)
        self.role = role

    def candidates(self, platform):
        text = _quote(self.text)
        if platform == "ios":
            kind = IOS_ROLES.get(self.role or "", "")
            where = f'(label == {text} OR name == {text} OR value == {text})'
            contains = f'(label CONTAINS {text} OR name CONTAINS {text} OR value CONTAINS {text})'
            if kind:
                where = f'type == "{kind}" AND {where}'
                contains = f'type == "{kind}" AND {contains}'
            return [(AppiumBy.IOS_PREDICATE, where), (AppiumBy.IOS_PREDICATE, contains)]
        kind = ANDROID_ROLES.get(self.role or "", "")
        prefix = f'new UiSelector().className({_quote(kind)})' if kind else "new UiSelector()"
        return [
            (AppiumBy.ANDROID_UIAUTOMATOR, f"{prefix}.text({text})"),
            (AppiumBy.ANDROID_UIAUTOMATOR, f"{prefix}.description({text})"),
            (AppiumBy.ANDROID_UIAUTOMATOR, f"{prefix}.textContains({text})"),
        ]

    def describe(self):
        return f"text {self.text!r}" + (f" ({self.role})" if self.role else "")


class ByName(Locator):
    def __init__(self, name):
        self.name = str(name)

    def candidates(self, platform):
        if platform == "ios":
            return [(AppiumBy.IOS_PREDICATE, f"name == {_quote(self.name)}"), (AppiumBy.ACCESSIBILITY_ID, self.name)]
        return [(AppiumBy.ACCESSIBILITY_ID, self.name)]

    def describe(self):
        return f"name {self.name!r}"


class ByRole(Locator):
    def __init__(self, role):
        self.role = role

    def candidates(self, platform):
        if platform == "ios":
            kind = IOS_ROLES.get(self.role, "XCUIElementTypeAny")
            return [(AppiumBy.IOS_PREDICATE, f'type == "{kind}"')]
        kind = ANDROID_ROLES.get(self.role, "")
        return [(AppiumBy.ANDROID_UIAUTOMATOR, f"new UiSelector().className({_quote(kind)})" if kind else "new UiSelector()")]

    def describe(self):
        return f"role {self.role!r}"


def by_text(text, role=None):
    return ByText(text, role)


def by_name(name):
    return ByName(name)


def by_role(role):
    return ByRole(role)


def describe(locator):
    if isinstance(locator, Locator):
        return locator.describe()
    by, value = locator
    return f"{by} {value!r}"


def _candidates(locator, platform):
    if isinstance(locator, Locator):
        return locator.candidates(platform)
    return [tuple(locator)]


def _rect(element):
    try:
        r = element.rect
        return float(r["x"]), float(r["y"]), float(r["width"]), float(r["height"])
    except (WebDriverException, KeyError, TypeError):
        return None


def _center(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def _pick(driver, elements, index=None, nearby_text=None, within_text=None):
    """Narrow a list of matches by index, by the closest anchor text, or by
    the row an anchor text sits on."""
    anchor_text = within_text or nearby_text
    if anchor_text:
        anchors = []
        for by, value in ByText(anchor_text).candidates(platform_of(driver)):
            anchors = _find_all(driver, by, value)
            if anchors:
                break
        if not anchors:
            return []
        anchor = _rect(anchors[0])
        if anchor is None:
            return elements[:1]
        scored = []
        for el in elements:
            r = _rect(el)
            if r is None:
                continue
            if within_text:
                # The same row: vertical spans overlap.
                if r[1] + r[3] < anchor[1] or r[1] > anchor[1] + anchor[3]:
                    continue
            ax, ay = _center(anchor)
            cx, cy = _center(r)
            scored.append((math.hypot(cx - ax, cy - ay), el))
        scored.sort(key=lambda item: item[0])
        elements = [el for _, el in scored]
    if index:
        return elements[index - 1:index] if len(elements) >= index else []
    return elements


def _find_all(driver, by, value):
    try:
        return list(driver.find_elements(by, value))
    except (NoSuchElementException, InvalidSelectorException):
        return []
    except WebDriverException as exc:
        if "invalid selector" in str(exc).lower():
            return []
        raise


def find(driver, locator, fallbacks=(), index=None, nearby_text=None, within_text=None, optional=False, retry=0, timeout=DEFAULT_TIMEOUT):
    """The element the locator names, waiting up to timeout seconds.

    The primary locator's candidates are tried first, then each fallback's.
    A match through anything but the primary's first candidate is recorded
    as a drift hit. optional=True returns None instead of raising.
    """
    platform = platform_of(driver)
    attempts = []
    for i, loc in enumerate([locator, *fallbacks]):
        for j, (by, value) in enumerate(_candidates(loc, platform)):
            attempts.append((i == 0 and j == 0, loc, by, value))
    deadline = time.monotonic() + max(float(timeout), 0)
    while True:
        for primary, loc, by, value in attempts:
            elements = _find_all(driver, by, value)
            if not elements:
                continue
            chosen = _pick(driver, elements, index=index, nearby_text=nearby_text, within_text=within_text)
            if not chosen:
                continue
            if not primary:
                evidence.drift(locator, loc, by, value)
            return chosen[0]
        if time.monotonic() >= deadline:
            break
        time.sleep(POLL_SECONDS)
    if optional:
        return None
    tried = "; ".join(f"{by} {value!r}" for _, _, by, value in attempts)
    raise ElementNotFound(f"no element for {describe(locator)} within {timeout}s (tried {tried})")


@contextlib.contextmanager
def optional():
    """A block whose missing element is not a failure."""
    try:
        yield
    except (ElementNotFound, NoSuchElementException, StaleElementReferenceException):
        pass
