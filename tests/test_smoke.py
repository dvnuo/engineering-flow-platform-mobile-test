"""The project end to end without a device: the example issue runs through
the runner against the fake driver, and the matrix, the Cucumber JSON, and
the evidence come out the way the assistant and the Jenkins plugin read them.

    python tests/test_smoke.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = "smoke"
OUT = ROOT / "runs" / LABEL

# The example app's screen: the total shows the USD purchase, and there is no
# confirmation after a refused purchase. The EUR scenario fails on purpose.
SCREEN = {"com.bank:id/total": "Total: 100.00 USD", "Purchase confirmed": None}


def run():
    shutil.rmtree(OUT, ignore_errors=True)
    env = dict(os.environ, MOBILETEST_FAKE_DRIVER="1", MOBILETEST_FAKE_SCREEN=json.dumps(SCREEN), MOBILE_SECRET_PASSWORD="not-a-real-password")
    cmd = [sys.executable, "-m", "mobiletest.run", "--platform", "android", "--tags", "@EXAMPLE-1", "--parallel", "2", "--label", LABEL, "--out", str(OUT)]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert proc.returncode == 1, f"one row fails on purpose, so the runner exits 1; got {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    assert proc.stdout.count("EFP-MATRIX ") >= 4, "the matrix is printed whenever it changes"

    # Each scenario folder is a row of its own, named by its scenario id.
    matrix = json.loads((OUT / "matrix.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in matrix["rows"]}
    assert matrix["format"] == "efp-matrix/v1" and matrix["summary"] == {"passed": 2, "failed": 1, "running": 0, "queued": 0, "total": 3}, matrix["summary"]
    assert rows["android/buy-100-usd"]["status"] == "passed"
    assert rows["android/over-daily-limit-usd"]["status"] == "passed"
    failed = rows["android/buy-250-eur"]
    assert failed["status"] == "failed" and "250.00 EUR" in failed["error"], failed
    assert failed["evidence"] == "cases/android_buy-250-eur/evidence.json"
    assert rows["android/buy-100-usd"]["screenshots"] == 4, "a screenshot after every step of the scenario"
    assert rows["android/buy-100-usd"]["script"] == "features/android/EXAMPLE-1/buy-100-usd.feature"
    assert (OUT / "features" / "android" / "EXAMPLE-1" / "buy-100-usd.feature").is_file()

    evidence = json.loads((OUT / "cases" / "android_buy-250-eur" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["format"] == "efp-evidence/v1" and evidence["error"]["step"].startswith("Then the confirmation shows")
    assert evidence["failure_screenshot"] == "screenshot.png" and (OUT / "cases" / "android_buy-250-eur" / "screenshot.png").is_file()
    assert (OUT / "cases" / "android_buy-250-eur" / "source.xml").is_file()
    passed = json.loads((OUT / "cases" / "android_buy-100-usd" / "evidence.json").read_text(encoding="utf-8"))
    assert [s["label"] for s in passed["screenshots"]] == ["signed in", "foreign exchange screen", "confirmation screen", "100 USD confirmation"], passed["screenshots"]
    assert (OUT / "cases" / "android_buy-100-usd" / passed["screenshots"][0]["file"]).is_file()

    cucumber = json.loads((OUT / "cucumber" / "cucumber.json").read_text(encoding="utf-8"))
    features = {f["uri"]: f for f in cucumber}
    assert sorted(features) == [
        "features/android/EXAMPLE-1/buy-100-usd.feature",
        "features/android/EXAMPLE-1/buy-250-eur.feature",
        "features/android/EXAMPLE-1/over-daily-limit-usd.feature",
    ], sorted(features)
    assert len({f["id"] for f in cucumber}) == 3, "every feature has an id of its own"
    usd = features["features/android/EXAMPLE-1/buy-100-usd.feature"]
    assert usd["name"].endswith("(android)") and usd["tags"][0]["name"] == "@EXAMPLE-1"
    assert [e["name"] for e in usd["elements"]] == ["Buy 100 USD within the daily limit"]
    assert all(s["result"]["status"] == "passed" for s in usd["elements"][0]["steps"])
    eur = features["features/android/EXAMPLE-1/buy-250-eur.feature"]["elements"][0]
    assert eur["steps"][-1]["result"]["status"] == "failed", eur["steps"]
    failed_step = eur["steps"][-1]
    assert failed_step["result"]["error_message"] and failed_step["embeddings"][0]["mime_type"] == "image/png", "the failure screen is in the report"
    assert isinstance(failed_step["result"]["duration"], int) and failed_step["keyword"] == "Then "
    junit = list((OUT / "junit").rglob("*.xml"))
    assert len(junit) == 3, junit
    print("smoke ok:", matrix["summary"])


def test_smoke():
    run()


def test_an_error_in_a_step_is_a_failure_with_the_screen():
    """behave 1.3 marks a step that raised anything but an AssertionError as
    "error": the matrix, the evidence, and the Cucumber JSON treat it as the
    failure it is, with the screen at the failure."""
    out = ROOT / "runs" / "smoke-error"
    shutil.rmtree(out, ignore_errors=True)
    screen = dict(SCREEN, **{"Amount exceeds": "!error"})
    env = dict(os.environ, MOBILETEST_FAKE_DRIVER="1", MOBILETEST_FAKE_SCREEN=json.dumps(screen), MOBILE_SECRET_PASSWORD="not-a-real-password")
    cmd = [sys.executable, "-m", "mobiletest.run", "--platform", "android", "--row", "over-daily-limit-usd", "--label", "smoke-error", "--out", str(out)]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    matrix = json.loads((out / "matrix.json").read_text(encoding="utf-8"))
    row = matrix["rows"][0]
    assert row["status"] == "failed" and "RuntimeError: fake driver error" in row["error"], row
    folder = out / "cases" / "android_over-daily-limit-usd"
    evidence = json.loads((folder / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["error"]["code"] == "step_error" and "fake driver error" in evidence["error"]["message"], evidence["error"]
    assert "Traceback" in evidence["error"]["traceback"] and evidence["error"]["step"].startswith("Then the message")
    assert evidence["failure_screenshot"] == "screenshot.png" and (folder / "screenshot.png").is_file() and (folder / "source.xml").is_file()
    cucumber = json.loads((out / "cucumber" / "cucumber.json").read_text(encoding="utf-8"))
    statuses = [s["result"]["status"] for s in cucumber[0]["elements"][0]["steps"]]
    assert "error" not in statuses and "failed" in statuses, statuses


if __name__ == "__main__":
    run()
    test_an_error_in_a_step_is_a_failure_with_the_screen()
