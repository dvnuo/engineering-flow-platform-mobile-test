"""The BrowserStack session of one scenario: start, status, video."""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions

DEFAULT_HUB = "https://hub-cloud.browserstack.com/wd/hub"
DEFAULT_API = "https://api-cloud.browserstack.com"


def credentials():
    user = os.environ.get("BROWSERSTACK_USERNAME", "")
    key = os.environ.get("BROWSERSTACK_ACCESS_KEY", "")
    if not user or not key:
        raise RuntimeError("BROWSERSTACK_USERNAME and BROWSERSTACK_ACCESS_KEY must be set (the job's BrowserStack credential)")
    return user, key


def hub_url():
    return os.environ.get("BROWSERSTACK_HUB_URL", DEFAULT_HUB)


def api_url():
    return os.environ.get("BROWSERSTACK_API_URL", DEFAULT_API).rstrip("/")


def _options(platform):
    if platform == "ios":
        options = XCUITestOptions()
        options.platform_name = "iOS"
    else:
        options = UiAutomator2Options()
        options.platform_name = "Android"
    return options


def start(config, session_name, build_name=None, project_name=None):
    """A BrowserStack device with the build the config names.

    config is config/<KEY>.<platform>.yaml: platform, app (a custom id or a
    bs:// URL), device, os_version, network.
    """
    if os.environ.get("MOBILETEST_FAKE_DRIVER"):
        from mobiletest.fake import FakeDriver

        return FakeDriver(config.get("platform", "android"), session_name)
    user, key = credentials()
    platform = str(config.get("platform", "android")).lower()
    options = _options(platform)
    options.set_capability("appium:app", str(config["app"]))
    bstack = {
        "userName": user,
        "accessKey": key,
        "projectName": project_name or config.get("issue") or "mobile scenarios",
        "buildName": build_name or config.get("build") or config.get("issue") or "mobile scenarios",
        "sessionName": session_name,
        "debug": True,
        "networkLogs": False,
        "idleTimeout": int(os.environ.get("BROWSERSTACK_IDLE_TIMEOUT", "300")),
    }
    if config.get("device"):
        bstack["deviceName"] = str(config["device"])
    if config.get("os_version"):
        bstack["osVersion"] = str(config["os_version"])
    if str(config.get("network", "")).startswith("private"):
        # The app is on a private network: the session goes through the
        # BrowserStack Local tunnel the pipeline (or the tester) started,
        # named by BROWSERSTACK_LOCAL_IDENTIFIER.
        bstack["local"] = True
        identifier = os.environ.get("BROWSERSTACK_LOCAL_IDENTIFIER", "")
        if identifier:
            bstack["localIdentifier"] = identifier
        else:
            print(f"warning: {config.get('issue')} needs a private network but BROWSERSTACK_LOCAL_IDENTIFIER is not set; the session uses any tunnel of the account", flush=True)
    options.set_capability("bstack:options", bstack)
    return webdriver.Remote(hub_url(), options=options)


def set_status(driver, passed, reason=""):
    """Mark the session passed or failed on the BrowserStack dashboard."""
    try:
        payload = {"action": "setSessionStatus", "arguments": {"status": "passed" if passed else "failed", "reason": str(reason)[:250]}}
        driver.execute_script("browserstack_executor: " + json.dumps(payload))
    except Exception:  # noqa: BLE001 - the status is a courtesy
        pass


def _get_json(url):
    user, key = credentials()
    token = base64.b64encode(f"{user}:{key}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": "Basic " + token, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def details(session_id, wait_for_video=60):
    """The session's dashboard URL, device, and video URL (the video appears
    a little after the session ends, so this waits for it)."""
    if os.environ.get("MOBILETEST_FAKE_DRIVER"):
        return {"public_url": f"https://app-automate.browserstack.com/sessions/{session_id}", "video_url": "", "device": "Fake device", "os_version": "1.0"}
    url = f"{api_url()}/app-automate/sessions/{urllib.parse.quote(session_id)}.json"
    deadline = time.monotonic() + float(wait_for_video)
    info = {}
    while True:
        try:
            info = _get_json(url).get("automation_session", {}) or {}
        except (urllib.error.URLError, ValueError, RuntimeError):
            info = info or {}
        if info.get("video_url") or time.monotonic() >= deadline:
            break
        time.sleep(5)
    return {
        "public_url": info.get("public_url") or info.get("browser_url") or "",
        "video_url": info.get("video_url") or "",
        "device": info.get("device") or "",
        "os_version": info.get("os_version") or "",
        "status": info.get("status") or "",
    }


def download(url, path):
    """Save a signed BrowserStack URL (a video) to path; returns the path or ''."""
    if not url:
        return ""
    try:
        with urllib.request.urlopen(url, timeout=300) as response, open(path, "wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        return path
    except (urllib.error.URLError, OSError):
        return ""


def plan():
    """The account's parallel sessions in use and allowed."""
    if os.environ.get("MOBILETEST_FAKE_DRIVER"):
        return {"parallel_sessions_running": 0, "parallel_sessions_max_allowed": 99}
    info = _get_json(f"{api_url()}/app-automate/plan.json")
    return {
        "parallel_sessions_running": int(info.get("parallel_sessions_running") or 0),
        "parallel_sessions_max_allowed": int(info.get("team_parallel_sessions_max_allowed") or info.get("parallel_sessions_max_allowed") or 0),
        "queued_sessions": int(info.get("queued_sessions") or 0),
    }
