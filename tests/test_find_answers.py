"""What the driver answers a find with is a list of elements; when it is
not (bare element ids, or a string), the helpers neither die on a character
nor hide it: ids become elements and anything else is a warning in the
evidence."""
from types import SimpleNamespace

from mobiletest import checks, elements, evidence


class Element:
    def __init__(self, element_id):
        self.id = element_id
        self.rect = {"x": 0, "y": 0, "width": 10, "height": 10}

    def is_enabled(self):
        return True

    def is_displayed(self):
        return True

    def get_attribute(self, name):
        return None


class Driver:
    capabilities = {"platformName": "Android"}

    def __init__(self, answer):
        self.answer = answer

    def find_elements(self, by, value):
        return self.answer

    def create_web_element(self, element_id):
        return Element(element_id)


def test_bare_ids_become_elements():
    driver = Driver(["abc-1", {"element-6066-11e4-a52e-4f735466cecf": "abc-2"}, {"ELEMENT": "abc-3"}])
    found = elements.find(driver, ("id", "com.app:id/accept"), timeout=0)
    assert isinstance(found, Element) and found.id == "abc-1"
    assert checks.wait_enabled(driver, ("id", "com.app:id/accept"), timeout=0).id == "abc-1"


def test_an_answer_that_is_not_a_list_is_a_warning_not_a_crash(tmp_path):
    rec = evidence.start(SimpleNamespace(), str(tmp_path))
    try:
        driver = Driver("unexpected text")
        assert elements.find(driver, ("id", "com.app:id/accept"), optional=True, timeout=0) is None
        assert checks.visible(driver, ("id", "com.app:id/accept"), timeout=0) is False
        assert rec.warnings and "str instead of a list" in rec.warnings[0]["text"]
        path = evidence.write(rec, {"id": "android/x", "status": "failed"})
        assert '"warnings"' in open(path, encoding="utf-8").read()
    finally:
        evidence.stop()
