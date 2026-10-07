"""Evidence of one scenario row: screenshots at its checks, the screen at a
failure, and the drift hits of its finds. The hooks open a recorder per
scenario; screenshot() and find() report to it."""
import json
import os
import re
import time

_current = None
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(text, default="item"):
    cleaned = _SAFE.sub("-", str(text or "")).strip("-.")
    return cleaned[:80] or default


class Recorder:
    def __init__(self, context, case_dir):
        self.context = context
        self.dir = case_dir
        self.screenshots = []
        self.drift = []
        self.step_index = 0
        self.error = None
        self.failure_screenshot = ""
        self.warnings = []
        os.makedirs(case_dir, exist_ok=True)

    def attach(self, mime_type, data):
        """Into the Cucumber JSON, next to the step that is running."""
        attach = getattr(self.context, "attach", None)
        if attach is None:
            return
        try:
            attach(mime_type, data)
        except Exception:  # noqa: BLE001 - the report is a courtesy
            pass


def start(context, case_dir):
    global _current
    _current = Recorder(context, case_dir)
    return _current


def current():
    return _current


def stop():
    global _current
    _current = None


def screenshot(driver, label="screen"):
    """A PNG under the scenario's evidence folder, attached to the step."""
    rec = _current
    try:
        png = driver.get_screenshot_as_png()
    except Exception as exc:  # noqa: BLE001
        if rec is not None:
            rec.screenshots.append({"label": str(label), "step": rec.step_index + 1, "error": str(exc)[:200]})
        return ""
    if rec is None:
        return ""
    name = f"{len(rec.screenshots) + 1:02d}-{safe_name(label, 'screen')}.png"
    path = os.path.join(rec.dir, name)
    with open(path, "wb") as f:
        f.write(png)
    rec.screenshots.append({"label": str(label), "file": name, "step": rec.step_index + 1})
    rec.attach("image/png", png)
    return path


def drift(primary, matched, by, value):
    """A find that only a fallback answered: the primary locator is stale."""
    rec = _current
    if rec is None:
        return
    from mobiletest.elements import describe

    rec.drift.append({"step": rec.step_index + 1, "target": describe(primary), "matched": describe(matched), "by": str(by), "value": str(value)})


def warn(text):
    """Something odd on the way that is not a failure by itself (the driver
    answering a find with something other than a list of elements): into the
    row's log, and evidence.json's warnings."""
    print(f"warning: {text}", flush=True)
    rec = _current
    if rec is not None:
        rec.warnings.append({"step": rec.step_index + 1, "text": str(text)[:500]})


def failure(driver):
    """The screen at the failure: screenshot.png and source.xml."""
    rec = _current
    if rec is None or driver is None:
        return
    try:
        png = driver.get_screenshot_as_png()
        with open(os.path.join(rec.dir, "screenshot.png"), "wb") as f:
            f.write(png)
        rec.failure_screenshot = "screenshot.png"
        rec.attach("image/png", png)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(os.path.join(rec.dir, "source.xml"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:  # noqa: BLE001
        pass


def write(rec, doc):
    """evidence.json (efp-evidence/v1) in the scenario's folder."""
    doc = dict(doc)
    doc.setdefault("format", "efp-evidence/v1")
    doc["screenshots"] = rec.screenshots
    if rec.drift:
        doc["fallback_hits"] = rec.drift
    if rec.error:
        doc["error"] = rec.error
    if rec.failure_screenshot:
        doc["failure_screenshot"] = rec.failure_screenshot
    if rec.warnings:
        doc["warnings"] = rec.warnings
    doc["written_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path = os.path.join(rec.dir, "evidence.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path
