"""scroll_to_end swipes until the screen stops changing: the end of a list or
a long text, wherever it is on this device."""
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


def test_it_gives_up_after_max_swipes_on_a_screen_that_keeps_moving():
    driver = Scrolling([str(i) for i in range(100)])
    assert actions.scroll_to_end(driver, max_swipes=4, settle=0) == 4
