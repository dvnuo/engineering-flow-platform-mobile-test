"""The runner finds each scenario folder (features/<platform>/<KEY>/<id>/,
what mobile-auto test export writes from scenario scripts) and still finds
an issue exported as one feature (features/<platform>/<KEY>/)."""
from pathlib import Path

from mobiletest import hooks, run

FEATURE = """@{key}
Feature: Sign in

  @positive
  Scenario: {title}
    Given the customer signs in
"""

OUTLINE = """@{key}
Feature: Sign in

  Scenario Outline: Sign in as <user>
    Given the customer signs in

    Examples:
      | example | user |
      | a       | x    |
      | b       | y    |
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scenario_folders_and_old_issue_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    for scenario, title in (("sign-in", "Sign in as a customer"), ("sign-in-vip", "Sign in as the VIP")):
        _write(tmp_path / "features" / "android" / "FX-12" / scenario / f"{scenario}.feature", FEATURE.format(key="FX-12", title=title))
        _write(tmp_path / "features" / "android" / "FX-12" / scenario / "steps" / "s.py", "")
    _write(tmp_path / "config" / "FX-12.android.yaml", "scenarios:\n  Sign in as a customer: sign-in\n  Sign in as the VIP: sign-in-vip\n")
    _write(tmp_path / "features" / "android" / "OLD-1" / "OLD-1.feature", OUTLINE.format(key="OLD-1"))
    _write(tmp_path / "config" / "OLD-1.android.yaml", "scenarios:\n  Sign in as <user>: sign-in\n")

    dirs = run.feature_dirs()
    assert [d.relative_to(tmp_path).as_posix() for d in dirs] == [
        "features/android/FX-12/sign-in",
        "features/android/FX-12/sign-in-vip",
        "features/android/OLD-1",
    ]
    assert run.location(dirs[0]) == ("android", "FX-12") and run.location(dirs[2]) == ("android", "OLD-1")

    rows = [r for d in dirs for r in run.enumerate_rows(d, [])]
    assert [r.id for r in rows] == ["android/sign-in", "android/sign-in-vip", "android/sign-in#a", "android/sign-in#b"]
    assert rows[0].issue == "FX-12" and rows[0].directory == dirs[0]
    assert rows[0].script == "features/android/FX-12/sign-in.feature"
    assert rows[2].script == "features/android/OLD-1.feature"
    assert run.feature_dirs(platforms=["ios"]) == []


def test_the_hooks_find_the_issue_of_a_scenario_folder():
    assert hooks.feature_location(str(Path("features") / "android" / "FX-12" / "sign-in" / "sign-in.feature")) == ("android", "FX-12")
    assert hooks.feature_location(str(Path("features") / "ios" / "FX-12" / "FX-12.feature")) == ("ios", "FX-12")
    assert hooks.feature_scenario_folder(str(Path("features") / "android" / "FX-12" / "sign-in" / "sign-in.feature")) == "sign-in"
    assert hooks.feature_scenario_folder(str(Path("features") / "ios" / "FX-12" / "FX-12.feature")) == ""


def test_two_scenarios_with_one_title_keep_their_own_rows(tmp_path, monkeypatch):
    # The config maps titles to ids, so a title two scenarios share keeps only
    # one id there; a scenario folder's name is the row's id instead.
    monkeypatch.setattr(run, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    for scenario in ("buy-100-usd", "buy-250-eur"):
        _write(tmp_path / "features" / "android" / "FX-12" / scenario / f"{scenario}.feature", FEATURE.format(key="FX-12", title="Buy currency within the daily limit"))
        _write(tmp_path / "features" / "android" / "FX-12" / scenario / "steps" / "s.py", "")
    _write(tmp_path / "config" / "FX-12.android.yaml", "scenarios:\n  Buy currency within the daily limit: buy-250-eur\n")
    rows = [r for d in run.feature_dirs() for r in run.enumerate_rows(d, [])]
    assert [r.id for r in rows] == ["android/buy-100-usd", "android/buy-250-eur"]


def test_check_fails_on_a_step_without_a_definition(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "REPO_ROOT", tmp_path)
    folder = tmp_path / "features" / "android" / "FX-12" / "sign-in"
    _write(folder / "sign-in.feature", FEATURE.format(key="FX-12", title="Sign in as a customer"))
    _write(folder / "steps" / "sign_in_steps.py", "")
    assert run.check([folder], []) == 1
    _write(folder / "steps" / "sign_in_steps.py", "from behave import given\n\n\n@given('the customer signs in')\ndef step(context):\n    pass\n")
    assert run.check([folder], []) == 0
