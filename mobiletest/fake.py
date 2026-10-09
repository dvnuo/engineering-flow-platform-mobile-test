"""A stand-in driver for smoke tests of the project without a device:
MOBILETEST_FAKE_DRIVER=1 makes the hooks use it instead of BrowserStack.

Every text locator finds an element whose text is the text looked for; every
other locator finds an element with no text. MOBILETEST_FAKE_SCREEN, a JSON
object, overrides that per locator: each key is a substring of a locator
value, its value the element's text, null for an element that is not on the
screen, or "!error" for a driver that raises on it (what a step that dies on
something other than an assertion looks like). That runs the steps end to
end and produces the same evidence, JSON, and matrix a real run would.
"""
import base64
import json
import os

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class FakeElement:
    def __init__(self, text=""):
        self.text = text
        self.rect = {"x": 10, "y": 10, "width": 100, "height": 40}

    def click(self):
        pass

    def clear(self):
        pass

    def send_keys(self, value):
        pass

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def is_selected(self):
        return False

    def get_attribute(self, name):
        return self.text if name in ("label", "name", "value", "content-desc") else None


class _SwitchTo:
    active_element = FakeElement()


def _screen():
    try:
        return json.loads(os.environ.get("MOBILETEST_FAKE_SCREEN") or "{}")
    except ValueError:
        return {}


class FakeDriver:
    def __init__(self, platform, session_name):
        self.capabilities = {"platformName": "iOS" if platform == "ios" else "Android"}
        self.session_id = "fake-" + session_name.replace("#", "-")
        self.page_source = "<hierarchy/>"
        self.switch_to = _SwitchTo()
        # The W3C actions each gesture sent, for tests that compare them.
        self.gestures = []

    def find_elements(self, by, value):
        for key, text in _screen().items():
            if key in str(value):
                if text == "!error":
                    raise RuntimeError(f"fake driver error for {key!r}")
                return [] if text is None else [FakeElement(str(text))]
        text = ""
        for marker in ('.text("', '.description("', '.textContains("', 'label == "', 'label CONTAINS "'):
            if marker in str(value):
                text = str(value).split(marker, 1)[1].split('"', 1)[0]
                break
        return [FakeElement(text)]

    def find_element(self, by, value):
        return self.find_elements(by, value)[0]

    def get_screenshot_as_png(self):
        return _PNG

    def get_window_size(self):
        return {"width": 1080, "height": 2400}

    def get_window_rect(self):
        return {"x": 0, "y": 0, "width": 1080, "height": 2400}

    def execute_script(self, script, *args):
        return None

    def execute(self, command, params=None):
        # W3C actions (swipes, taps by coordinates, long presses) go through here.
        if command == "actions" and params:
            for source in params.get("actions") or []:
                self.gestures.append(source.get("actions"))
        return {"value": None}

    def create_web_element(self, element_id):
        return FakeElement(str(element_id))

    def back(self):
        pass

    def hide_keyboard(self):
        pass

    def press_keycode(self, code):
        pass

    def activate_app(self, app):
        pass

    def terminate_app(self, app):
        pass

    def quit(self):
        pass
