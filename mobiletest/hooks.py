"""behave hooks: one BrowserStack session per scenario row, evidence per row.

features/<platform>/<KEY>/environment.py imports everything from here.
"""
import os
import sys
import time
from pathlib import Path

import yaml

from mobiletest import evidence, session

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # The generated steps import segments.<platform>.<segment>.
    sys.path.insert(0, str(REPO_ROOT))

__all__ = ["before_all", "before_feature", "before_scenario", "after_step", "after_scenario"]


def _flag(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _status_name(status):
    return getattr(status, "name", str(status)).replace("Status.", "")


def feature_location(filename):
    """(platform, KEY) from features/<platform>/<KEY>/<KEY>.feature."""
    parts = Path(filename).resolve().parts
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in ("android", "ios") and i + 1 < len(parts):
            return parts[i], parts[i + 1]
    return "android", Path(filename).stem


def load_config(platform, key):
    path = REPO_ROOT / "config" / f"{key}.{platform}.yaml"
    if not path.is_file():
        raise RuntimeError(f"missing {path.relative_to(REPO_ROOT)}: export the suite again (mobile-auto test export)")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("platform", platform)
    cfg.setdefault("issue", key)
    cfg.setdefault("data", {})
    cfg.setdefault("scenarios", {})
    # A build already on BrowserStack named by the job (ANDROID_APP_ID,
    # IOS_APP_ID: a bs:// id or a custom id) replaces the config's app.
    override = os.environ.get(f"{platform.upper()}_APP_ID", "").strip()
    if override:
        cfg["app"] = override
    return cfg


def before_all(context):
    userdata = context.config.userdata
    context.evidence_dir = userdata.get("evidence_dir") or os.environ.get("MOBILETEST_EVIDENCE_DIR") or "runs/local/cases"
    context.run_label = userdata.get("run_label") or os.environ.get("RUN_LABEL") or ""
    context.collect_video = _flag(userdata.get("collect_video") or os.environ.get("MOBILETEST_COLLECT_VIDEO") or "0")


def before_feature(context, feature):
    context.platform, context.issue = feature_location(feature.filename)
    context.cfg = load_config(context.platform, context.issue)
    context.feature_file = str(Path(feature.filename).as_posix())


def before_scenario(context, scenario):
    row = getattr(context, "active_outline", None)
    context.row = dict(zip(row.headings, row.cells)) if row is not None else {}
    context.data = dict(context.cfg.get("data") or {})
    title = scenario.name.split(" -- @")[0].strip()
    case_id = context.cfg["scenarios"].get(title) or evidence.safe_name(title.lower(), "scenario")
    example = context.row.get("example") or (row.cells[0] if row is not None and row.cells else "") or ""
    context.case_id, context.example = case_id, example
    context.row_id = f"{context.platform}/{case_id}#{example}" if example else f"{context.platform}/{case_id}"
    folder = evidence.safe_name(f"{context.platform}_{case_id}_{example}" if example else f"{context.platform}_{case_id}")
    context.case_dir = os.path.join(context.evidence_dir, folder)
    context.recorder = evidence.start(context, context.case_dir)
    context.started_at = time.time()
    context.driver = None
    context.session_id = ""
    session_name = f"{case_id}#{example}" if example else case_id
    try:
        context.driver = session.start(context.cfg, session_name, build_name=context.run_label or None, project_name=context.cfg.get("issue"))
        context.session_id = getattr(context.driver, "session_id", "") or ""
    except Exception as exc:  # noqa: BLE001 - the row fails with the reason
        context.recorder.error = {"code": "session_start_failed", "message": str(exc)[:1000]}
        _write_evidence(context, "failed")
        raise


def after_step(context, step):
    rec = getattr(context, "recorder", None)
    if rec is None:
        return
    rec.step_index += 1
    if _status_name(step.status) == "failed" and rec.error is None:
        message = getattr(step, "error_message", None) or str(getattr(step, "exception", "") or "step failed")
        rec.error = {
            "code": "assertion_failed" if "AssertionError" in str(type(getattr(step, "exception", None))) or "expected" in str(message) else "step_failed",
            "message": str(message)[:2000],
            "step": f"{step.keyword} {step.name}",
        }
        evidence.failure(context.driver)


def after_scenario(context, scenario):
    rec = getattr(context, "recorder", None)
    if rec is None:
        return
    status = _status_name(scenario.status)
    passed = status == "passed"
    if not passed and rec.error is None:
        rec.error = {"code": "scenario_" + status, "message": f"scenario ended {status}"}
    driver = context.driver
    if driver is not None:
        session.set_status(driver, passed, rec.error["message"] if rec.error else "passed")
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            pass
    _write_evidence(context, "passed" if passed else "failed")
    evidence.stop()


def _write_evidence(context, status):
    rec = context.recorder
    info = {}
    if context.session_id:
        try:
            info = session.details(context.session_id, wait_for_video=60 if context.collect_video else 15)
        except Exception:  # noqa: BLE001
            info = {}
    doc = {
        "id": context.row_id,
        "scenario": context.case_id,
        "example": context.example,
        "status": status,
        "duration_ms": int((time.time() - context.started_at) * 1000),
        "platform": context.platform,
        "device": info.get("device") or context.cfg.get("device", ""),
        "os_version": info.get("os_version") or context.cfg.get("os_version", ""),
        "run_id": context.run_label,
        "session_id": context.session_id,
        "session_url": info.get("public_url", ""),
        "video_url": info.get("video_url", ""),
        "script": f"features/{context.platform}/{context.issue}.feature",
    }
    if context.collect_video and info.get("video_url"):
        if session.download(info["video_url"], os.path.join(rec.dir, "video.mp4")):
            doc["video"] = "video.mp4"
    evidence.write(rec, doc)
