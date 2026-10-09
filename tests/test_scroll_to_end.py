"""scroll_to_end swipes until the screen stops changing, and scroll_to until
the element shows: both stop after the device's limit, 8 swipes unless the
step says otherwise, and the end not reached is a failure, as on the device."""
import pytest

from mobiletest import actions
from mobiletest.fake import FakeDriver


class Scrolling(FakeDriver):
    def __init__(self, screens):
        super().__init__("android", "scroll")
        self.screens = list(screens)
        self.swipes = 0

    @property
    def page_source(self):
        return self.screens[min(self.swipes, len(self.screens) - 1)]

    @page_source.setter
    def page_source(self, value):
        pass

    def execute(self, command, params=None):
        self.swipes += 1
        return {"value": None}


def test_it_stops_when_the_screen_stops_changing():
    driver = Scrolling(["top", "middle", "bottom", "bottom"])
    assert actions.scroll_to_end(driver, settle=0) == 3
    assert driver.swipes == 3


def test_a_screen_still_moving_after_the_limit_fails():
    driver = Scrolling([str(i) for i in range(100)])
    with pytest.raises(AssertionError, match="still changing after 4 swipes"):
        actions.scroll_to_end(driver, max_swipes=4, settle=0)
    assert driver.swipes == 4


def test_the_default_limit_is_the_devices():
    driver = Scrolling([str(i) for i in range(100)])
    with pytest.raises(AssertionError, match="after 8 swipes"):
        actions.scroll_to_end(driver, settle=0)
    assert driver.swipes == 8


class Searching(Scrolling):
    """The element shows after `found_after` swipes."""

    def __init__(self, found_after):
        super().__init__(["x"])
        self.found_after = found_after

    def find_elements(self, by, value):
        return super().find_elements(by, value) if self.swipes >= self.found_after else []


def test_scroll_to_swipes_at_most_max_scrolls_times(monkeypatch):
    monkeypatch.setattr(actions.time, "sleep", lambda s: None)
    driver = Searching(found_after=3)
    assert actions.scroll_to(driver, ("id", "fees"), max_scrolls=3, timeout=0) is not None
    assert driver.swipes == 3
    driver = Searching(found_after=99)
    with pytest.raises(AssertionError):
        actions.scroll_to(driver, ("id", "fees"), max_scrolls=3, timeout=0)
    assert driver.swipes == 3, "no swipe after the last look"


def test_scroll_to_looks_down_with_a_swipe_up(monkeypatch):
    monkeypatch.setattr(actions.time, "sleep", lambda s: None)
    driver = FakeDriver("android", "scroll")
    driver.find_elements = lambda by, value: []
    monkeypatch.setattr(actions, "DEFAULT_TIMEOUT", 0)
    with pytest.raises(AssertionError):
        actions.scroll_to(driver, ("id", "fees"), max_scrolls=1, timeout=0)
    start, end = driver.gestures[0][0], driver.gestures[0][2]
    assert start["y"] > end["y"], "the finger moves up to show what is further down"
