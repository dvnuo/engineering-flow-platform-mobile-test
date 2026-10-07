"""behave's statuses become Cucumber's: behave 1.3 says "error" for a step
that raised anything but an AssertionError, which the Jenkins plugin does
not know and the matrix must count as a failure with its message."""
from mobiletest import report


def feature(status, error_message=None):
    result = {"status": status, "duration": 1.5}
    if error_message is not None:
        result["error_message"] = error_message
    return {
        "name": "Checkout", "location": "f.feature:1", "keyword": "Feature",
        "elements": [{"type": "scenario", "keyword": "Scenario", "name": "Pay -- @1.1", "location": "f.feature:5", "steps": [
            {"keyword": "Given", "name": "the app is open", "location": "f.feature:6", "result": {"status": "passed", "duration": 0.5}},
            {"keyword": "When", "name": "the user accepts the terms", "location": "f.feature:7", "result": result},
            {"keyword": "Then", "name": "home shows", "location": "f.feature:8", "result": {"status": "skipped", "duration": 0}},
        ]}],
    }


def test_an_error_step_is_a_failure_with_its_message():
    message = ["Traceback (most recent call last):", '  File "checks.py", line 67', "AttributeError: 'str' object has no attribute 'is_enabled'"]
    element = report.to_cucumber(feature("error", message), "android", "features/android/F.feature")["elements"][0]
    assert [s["result"]["status"] for s in element["steps"]] == ["passed", "failed", "skipped"]
    assert report.scenario_status(element) == "failed"
    assert report.scenario_error(element) == "When the user accepts the terms: AttributeError: 'str' object has no attribute 'is_enabled'"


def test_every_behave_status_maps_to_one_the_plugin_knows():
    known = {"passed", "failed", "skipped", "pending", "undefined"}
    for status in ["unknown", "untested", "executing", "skipped", "passed", "xfailed", "xpassed", "failed", "error", "hook_error", "cleanup_error", "undefined", "pending", "pending_warn", "untested_pending", "untested_undefined", "something_new"]:
        assert report._status({"status": status}) in known, status
    assert report._status({"status": "hook_error"}) == "failed" and report._status({}) == "skipped"
    # A step that errored without a message still names its step.
    element = report.to_cucumber(feature("error"), "ios", "f")["elements"][0]
    assert report.scenario_error(element).startswith("When the user accepts the terms: failed step")


def test_a_step_without_a_message_takes_the_evidence_s():
    # behave 1.3 writes no error_message for a step that raised; the hooks
    # kept it in the evidence, and the report and the matrix show it.
    element = report.to_cucumber(feature("error"), "ios", "f")["elements"][0]
    report.fill_error(element, {"code": "step_error", "message": "RuntimeError: boom", "traceback": "Traceback (most recent call last):\n  ...\nRuntimeError: boom", "step": "When x"})
    assert element["steps"][1]["result"]["error_message"].startswith("RuntimeError: boom\nTraceback")
    assert report.scenario_error(element) == "When the user accepts the terms: RuntimeError: boom"
    # A passed step, or one that already has a message, is left alone.
    report.fill_error(element, {"message": "other"})
    assert element["steps"][1]["result"]["error_message"].startswith("RuntimeError: boom")
