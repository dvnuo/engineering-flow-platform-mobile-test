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
# confirmation after a refused purchase. The EUR row fails on purpose.
SCREEN = {"com.bank:id/total": "Total: 100.00 USD", "Purchase confirmed": None}


def run():
    shutil.rmtree(OUT, ignore_errors=True)
    env = dict(os.environ, MOBILETEST_FAKE_DRIVER="1", MOBILETEST_FAKE_SCREEN=json.dumps(SCREEN), MOBILE_SECRET_PASSWORD="not-a-real-password")
    cmd = [sys.executable, "-m", "mobiletest.run", "--platform", "android", "--tags", "@EXAMPLE-1", "--parallel", "2", "--label", LABEL, "--out", str(OUT)]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert proc.returncode == 1, f"one row fails on purpose, so the runner exits 1; got {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
    assert proc.stdout.count("EFP-MATRIX ") >= 4, "the matrix is printed whenever it changes"

    matrix = json.loads((OUT / "matrix.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in matrix["rows"]}
    assert matrix["format"] == "efp-matrix/v1" and matrix["summary"] == {"passed": 2, "failed": 1, "running": 0, "queued": 0, "total": 3}, matrix["summary"]
    assert rows["android/buy-foreign-currency#USD"]["status"] == "passed"
    assert rows["android/over-daily-limit#USD-limit"]["status"] == "passed"
    failed = rows["android/buy-foreign-currency#EUR"]
    assert failed["status"] == "failed" and "250.00 EUR" in failed["error"], failed
    assert failed["evidence"] == "cases/android_buy-foreign-currency_EUR/evidence.json"
    assert rows["android/buy-foreign-currency#USD"]["screenshots"] == 1

    evidence = json.loads((OUT / "cases" / "android_buy-foreign-currency_EUR" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["format"] == "efp-evidence/v1" and evidence["error"]["step"].startswith("Then the confirmation shows")
    assert evidence["failure_screenshot"] == "screenshot.png" and (OUT / "cases" / "android_buy-foreign-currency_EUR" / "screenshot.png").is_file()
    assert (OUT / "cases" / "android_buy-foreign-currency_EUR" / "source.xml").is_file()
    passed = json.loads((OUT / "cases" / "android_buy-foreign-currency_USD" / "evidence.json").read_text(encoding="utf-8"))
    assert passed["screenshots"][0]["label"] == "USD confirmation" and (OUT / "cases" / "android_buy-foreign-currency_USD" / passed["screenshots"][0]["file"]).is_file()

    cucumber = json.loads((OUT / "cucumber" / "cucumber.json").read_text(encoding="utf-8"))
    assert len(cucumber) == 1 and cucumber[0]["uri"] == "features/android/EXAMPLE-1.feature" and cucumber[0]["name"].endswith("(android)")
    elements = cucumber[0]["elements"]
    assert [e["name"].split(" -- ")[1].strip() for e in elements] == ["@1.1", "@1.2", "@1.1"], [e["name"] for e in elements]
    statuses = {e["name"]: [s["result"]["status"] for s in e["steps"]] for e in elements}
    assert all(s == "passed" for s in statuses[elements[0]["name"]]), statuses
    assert statuses[elements[1]["name"]][-1] == "failed", statuses
    failed_step = elements[1]["steps"][-1]
    assert failed_step["result"]["error_message"] and failed_step["embeddings"][0]["mime_type"] == "image/png", "the failure screen is in the report"
    assert isinstance(failed_step["result"]["duration"], int) and failed_step["keyword"] == "Then "
    assert cucumber[0]["tags"][0]["name"] == "@EXAMPLE-1"
    junit = list((OUT / "junit").rglob("*.xml"))
    assert len(junit) == 3, junit
    print("smoke ok:", matrix["summary"])


if __name__ == "__main__":
    run()
