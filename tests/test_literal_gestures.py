"""The exported Python makes the same gestures as the device replay.

The table is the one in engineering-flow-platform-tools'
internal/mobileauto/commands/inspector_script_test.go (canonicalGestures):
the Python line mobile-auto test export writes for a script step, and the
W3C actions mobile-auto sends for the same step on a 1080x2400 window. Here
the very line runs against the stand-in driver and must send those actions.
Change both tables together.
"""
import json

import pytest

from mobiletest import actions
from mobiletest.fake import FakeDriver

CANONICAL = [
    (
        "recorded swipe",
        'swipe(context.driver, start=(50, 62.5), end=(50, 37.5), duration_ms=750)',
        '[{"type":"pointerMove","duration":0,"x":540,"y":1500},{"type":"pointerDown","button":0},{"type":"pointerMove","duration":750,"x":540,"y":900},{"type":"pointerUp","button":0}]',
    ),
    (
        "swipe from the screen edge, with holds",
        'swipe(context.driver, start=(0.4, 50), end=(80, 50.02), duration_ms=300, hold_ms=200, end_hold_ms=50)',
        '[{"type":"pointerMove","duration":0,"x":4,"y":1200},{"type":"pointerDown","button":0},{"type":"pause","duration":200},{"type":"pointerMove","duration":300,"x":864,"y":1200},{"type":"pause","duration":50},{"type":"pointerUp","button":0}]',
    ),
    (
        "swipe by direction",
        'swipe(context.driver, "up", duration_ms=500)',
        '[{"type":"pointerMove","duration":0,"x":540,"y":1920},{"type":"pointerDown","button":0},{"type":"pointerMove","duration":500,"x":540,"y":480},{"type":"pointerUp","button":0}]',
    ),
    (
        "scroll by its default direction",
        'swipe(context.driver, "down", duration_ms=500)',
        '[{"type":"pointerMove","duration":0,"x":540,"y":480},{"type":"pointerDown","button":0},{"type":"pointerMove","duration":500,"x":540,"y":1920},{"type":"pointerUp","button":0}]',
    ),
    (
        "coordinate tap",
        'tap_point(context.driver, x_percent=50, y_percent=62.5, hold_ms=100)',
        '[{"type":"pointerMove","duration":0,"x":540,"y":1500},{"type":"pointerDown","button":0},{"type":"pause","duration":100},{"type":"pointerUp","button":0}]',
    ),
    (
        "coordinate tap on a half pixel",
        'tap_point(context.driver, x_percent=51.25, y_percent=50)',
        '[{"type":"pointerMove","duration":0,"x":554,"y":1200},{"type":"pointerDown","button":0},{"type":"pointerUp","button":0}]',
    ),
    (
        "swipe from a half pixel",
        'swipe(context.driver, start=(51.25, 62.5), end=(51.25, 37.5), duration_ms=750)',
        '[{"type":"pointerMove","duration":0,"x":554,"y":1500},{"type":"pointerDown","button":0},{"type":"pointerMove","duration":750,"x":554,"y":900},{"type":"pointerUp","button":0}]',
    ),
]


class _Context:
    def __init__(self):
        self.driver = FakeDriver("android", "gestures")


@pytest.mark.parametrize("name,line,w3c", CANONICAL, ids=[c[0] for c in CANONICAL])
def test_the_exported_line_sends_what_the_device_sends(name, line, w3c):
    context = _Context()
    eval(line, {"swipe": actions.swipe, "tap_point": actions.tap_point, "context": context})  # noqa: S307 - the export's own line
    assert context.driver.gestures == [json.loads(w3c)], name


def test_one_finger_named_like_the_device_one():
    driver = FakeDriver("android", "gestures")
    sent = []
    driver.execute = lambda command, params=None: sent.append((command, params)) or {"value": None}
    actions.swipe(driver, start=(50, 75), end=(50, 45), duration_ms=750)
    command, params = sent[0]
    source = params["actions"][0]
    assert command == "actions" and source["type"] == "pointer" and source["id"] == "finger1" and source["parameters"] == {"pointerType": "touch"}


def test_element_centres_round_half_away_from_zero_like_the_device():
    class Element:
        rect = {"x": 0, "y": 0, "width": 101, "height": 41}

    # Go's math.Round gives (51, 21); Python's round() would give (50, 20).
    assert actions._center(Element()) == (51, 21)
    Element.rect = {"x": -101, "y": 0, "width": 101, "height": 2}
    assert actions._center(Element()) == (-51, 1)


def test_points_round_half_away_from_zero_like_the_device():
    driver = FakeDriver("android", "gestures")
    driver.get_window_rect = lambda: {"x": 0, "y": 0, "width": 1000, "height": 2000}
    # 1000 * 0.05 / 100 = 0.5 rounds to 1, as Go's math.Round does (Python's round() would give 0).
    actions.tap_point(driver, x_percent=0.05, y_percent=50)
    assert driver.gestures[-1][0] == {"type": "pointerMove", "duration": 0, "x": 1, "y": 1000}
