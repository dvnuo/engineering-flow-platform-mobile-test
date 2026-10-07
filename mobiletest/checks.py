"""Checks: each waits up to its timeout for the screen to show what the
scenario expects, then fails with what the screen showed instead."""
import time

from selenium.common.exceptions import StaleElementReferenceException, WebDriverException

from mobiletest.elements import DEFAULT_TIMEOUT, POLL_SECONDS, ElementNotFound, describe, find


def _text_of(element):
    try:
        text = element.text
    except (StaleElementReferenceException, WebDriverException):
        return ""
    if not text:
        for attr in ("value", "label", "content-desc", "name"):
            try:
                text = element.get_attribute(attr)
            except WebDriverException:
                text = None
            if text:
                break
    return str(text or "")


def _displayed(element):
    try:
        return bool(element.is_displayed())
    except (StaleElementReferenceException, WebDriverException):
        return False


def visible(driver, locator, timeout=3, **kwargs):
    """Whether the element is on screen within timeout seconds."""
    element = find(driver, locator, optional=True, timeout=timeout, **kwargs)
    return element is not None and _displayed(element)


def wait_visible(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    deadline = time.monotonic() + float(timeout)
    while True:
        element = find(driver, locator, optional=True, timeout=1, **kwargs)
        if element is not None and _displayed(element):
            return element
        if time.monotonic() >= deadline:
            raise ElementNotFound(f"{describe(locator)} is not visible after {timeout}s")
        time.sleep(POLL_SECONDS)


def wait_gone(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    deadline = time.monotonic() + float(timeout)
    while True:
        element = find(driver, locator, optional=True, timeout=0, **kwargs)
        if element is None or not _displayed(element):
            return
        if time.monotonic() >= deadline:
            raise AssertionError(f"{describe(locator)} is still visible after {timeout}s")
        time.sleep(POLL_SECONDS)


def wait_enabled(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    deadline = time.monotonic() + float(timeout)
    while True:
        element = find(driver, locator, optional=True, timeout=1, **kwargs)
        if element is not None:
            try:
                if element.is_enabled():
                    return element
            except WebDriverException:
                pass
        if time.monotonic() >= deadline:
            raise AssertionError(f"{describe(locator)} is not enabled after {timeout}s")
        time.sleep(POLL_SECONDS)


def _matches(actual, equals=None, contains=None):
    if equals is not None:
        return actual.strip() == str(equals).strip()
    if contains is not None:
        return str(contains) in actual
    return True


def wait_text(driver, locator, equals=None, contains=None, timeout=DEFAULT_TIMEOUT, **kwargs):
    deadline = time.monotonic() + float(timeout)
    last = None
    while True:
        element = find(driver, locator, optional=True, timeout=1, **kwargs)
        if element is not None:
            last = _text_of(element)
            if _matches(last, equals=equals, contains=contains):
                return element
        if time.monotonic() >= deadline:
            break
        time.sleep(POLL_SECONDS)
    expected = f"equal to {equals!r}" if equals is not None else f"containing {contains!r}"
    if last is None:
        raise ElementNotFound(f"{describe(locator)} did not appear within {timeout}s (expected text {expected})")
    raise AssertionError(f"text of {describe(locator)} is {last!r}, expected {expected}")


def wait_stable(driver, timeout=5, settle=1.0):
    """Wait until the page source stops changing for settle seconds."""
    deadline = time.monotonic() + float(timeout)
    last = None
    since = time.monotonic()
    while time.monotonic() < deadline:
        try:
            current = driver.page_source
        except WebDriverException:
            current = None
        if current != last:
            last = current
            since = time.monotonic()
        elif time.monotonic() - since >= settle:
            return
        time.sleep(POLL_SECONDS)


def assert_visible(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    return wait_visible(driver, locator, timeout=timeout, **kwargs)


def assert_not_visible(driver, locator, timeout=3, **kwargs):
    """Fails when the element shows up within timeout seconds."""
    deadline = time.monotonic() + float(timeout)
    while True:
        element = find(driver, locator, optional=True, timeout=0, **kwargs)
        if element is not None and _displayed(element):
            raise AssertionError(f"{describe(locator)} is visible, expected not to be")
        if time.monotonic() >= deadline:
            return
        time.sleep(POLL_SECONDS)


def assert_enabled(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    return wait_enabled(driver, locator, timeout=timeout, **kwargs)


def assert_selected(driver, locator, timeout=DEFAULT_TIMEOUT, **kwargs):
    element = wait_visible(driver, locator, timeout=timeout, **kwargs)
    selected = False
    try:
        selected = element.is_selected() or str(element.get_attribute("checked")).lower() == "true"
    except WebDriverException:
        pass
    if not selected:
        raise AssertionError(f"{describe(locator)} is not selected")
    return element


def assert_text(driver, locator, equals=None, contains=None, timeout=DEFAULT_TIMEOUT, **kwargs):
    return wait_text(driver, locator, equals=equals, contains=contains, timeout=timeout, **kwargs)


def assert_count(driver, locator, expected, timeout=DEFAULT_TIMEOUT, **kwargs):
    from mobiletest.elements import _candidates, _find_all, platform_of

    deadline = time.monotonic() + float(timeout)
    count = 0
    while True:
        for by, value in _candidates(locator, platform_of(driver)):
            count = len(_find_all(driver, by, value))
            if count:
                break
        if count == int(expected):
            return count
        if time.monotonic() >= deadline:
            raise AssertionError(f"{describe(locator)}: {count} elements, expected {expected}")
        time.sleep(POLL_SECONDS)
