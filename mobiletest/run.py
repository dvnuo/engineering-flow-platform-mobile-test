"""Run scenario rows in parallel, one behave process and one BrowserStack
session per row, and collect the results:

    python -m mobiletest.run --platform android --tags @FX-12 --parallel 4 --label task-123

Each scenario is a row: a scenario folder, features/<platform>/<KEY>/<id>/,
holds one (what mobile-auto test export writes from a scenario script), and
in an issue exported as one feature, features/<platform>/<KEY>/, each Examples
row of each Scenario Outline is one. A row's evidence lands in
runs/<label>/cases/<platform>_<scenario>[_<row>]/; the run's Cucumber JSON in
runs/<label>/cucumber/cucumber.json, its JUnit files under runs/<label>/junit/,
and its matrix in runs/<label>/matrix.json. Whenever the matrix changes it is
also printed on one line prefixed EFP-MATRIX, for a reader following the log.

behave on its own runs one scenario folder's scenario:
    behave features/android/FX-12/buy-100-usd -D evidence_dir=runs/local/cases
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from mobiletest import report, session

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Row:
    directory: Path
    platform: str
    issue: str
    case_id: str
    example: str
    name: str
    feature_file: Path
    tags: list = field(default_factory=list)

    @property
    def id(self):
        return f"{self.platform}/{self.case_id}#{self.example}" if self.example else f"{self.platform}/{self.case_id}"

    @property
    def folder(self):
        from mobiletest.evidence import safe_name

        return safe_name(f"{self.platform}_{self.case_id}_{self.example}" if self.example else f"{self.platform}_{self.case_id}")

    @property
    def script(self):
        """The feature's path in the run's output and the Cucumber report:
        features/<platform>/<KEY>/<id>.feature for a scenario folder,
        features/<platform>/<KEY>.feature for an issue exported as one."""
        if self.directory.parent.name == self.issue:
            return f"features/{self.platform}/{self.issue}/{self.feature_file.name}"
        return f"features/{self.platform}/{self.issue}.feature"


def feature_dirs(platforms=None, features=None):
    """Every folder behave runs, or the ones asked for: each scenario folder
    features/<platform>/<KEY>/<id>/, and an issue exported as one feature,
    features/<platform>/<KEY>/."""
    dirs = []
    if features:
        for f in features:
            path = Path(f)
            dirs.append(path if path.is_absolute() else REPO_ROOT / path)
        return dirs
    root = REPO_ROOT / "features"
    for platform_dir in sorted(root.glob("*")):
        if not platform_dir.is_dir() or (platforms and platform_dir.name not in platforms):
            continue
        for issue_dir in sorted(platform_dir.glob("*")):
            if not issue_dir.is_dir():
                continue
            if list(issue_dir.glob("*.feature")):
                dirs.append(issue_dir)
                continue
            for scenario_dir in sorted(issue_dir.glob("*")):
                if scenario_dir.is_dir() and list(scenario_dir.glob("*.feature")):
                    dirs.append(scenario_dir)
    return dirs


def location(directory):
    """(platform, KEY) of a folder behave runs."""
    if directory.parent.name in ("android", "ios"):
        return directory.parent.name, directory.name
    return directory.parent.parent.name, directory.parent.name


def load_config(platform, issue):
    from mobiletest.hooks import load_config as _load

    return _load(platform, issue)


def tag_args(tags):
    args = []
    for tag in tags or []:
        args += ["--tags", tag]
    return args


def enumerate_rows(directory, tags):
    """The rows behave would run in the directory, with their ids."""
    from behave.model import ScenarioOutline
    from behave.parser import parse_file

    platform, issue = location(directory)
    cfg = load_config(platform, issue)
    # A scenario folder is named after its scenario: that is the row's id,
    # whatever the scenario's title.
    folder_id = directory.name if directory.parent.name == issue else ""
    selected = _selected_names(directory, tags)
    rows = []
    for feature_file in sorted(directory.glob("*.feature")):
        feature = parse_file(str(feature_file))
        for scenario in feature.scenarios:
            generated = scenario.scenarios if isinstance(scenario, ScenarioOutline) else [scenario]
            for s in generated:
                if selected is not None and s.name not in selected:
                    continue
                row = getattr(s, "_row", None)
                headings = list(getattr(row, "headings", []) or [])
                cells = list(getattr(row, "cells", []) or [])
                values = dict(zip(headings, cells))
                example = values.get("example") or (cells[0] if cells else "")
                title = scenario.name.strip()
                case_id = folder_id or cfg["scenarios"].get(title) or report.slug(title)
                rows.append(Row(directory, platform, issue, case_id, example, s.name, feature_file, [str(t) for t in s.effective_tags]))
    return rows


def _selected_names(directory, tags):
    """The scenario names behave selects for the tags, from a dry run; None
    when everything is selected."""
    if not tags:
        return None
    cmd = [sys.executable, "-m", "behave", str(directory), "--dry-run", "-f", "json", "-o", "-", "--no-summary", "--no-color"] + tag_args(tags)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=300, check=False).stdout
        data = json.loads(out[out.index("["):])
    except (ValueError, subprocess.SubprocessError):
        return None
    names = set()
    for feature in data:
        for el in feature.get("elements") or []:
            if el.get("type") == "background":
                continue
            if str(el.get("status") or "").lower() != "skipped":
                names.add(el.get("name"))
    return names


def run_row(row, out, label, tags, collect_video, index, wait_capacity):
    """One behave process for one row; returns (row, cucumber feature or None, log path)."""
    if wait_capacity:
        _wait_for_capacity()
    json_path = out / "behave" / f"{index:03d}.json"
    junit_dir = out / "junit" / f"{index:03d}"
    log_path = out / "logs" / f"{index:03d}-{row.folder}.log"
    for p in (json_path.parent, junit_dir, log_path.parent):
        p.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "behave", str(row.directory),
        "--name", "^" + re.escape(row.name) + "$",
        "-f", "json", "-o", str(json_path),
        "--junit", "--junit-directory", str(junit_dir),
        "-D", f"evidence_dir={out / 'cases'}",
        "-D", f"run_label={label}",
        "-D", f"collect_video={'1' if collect_video else '0'}",
        "--no-summary", "--no-color",
    ] + tag_args(tags)
    with open(log_path, "w", encoding="utf-8") as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=REPO_ROOT, check=False)
    feature = None
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            converted = report.to_cucumber(item, row.platform, row.script, keep_names={row.name})
            if converted["elements"]:
                feature = converted
                break
    except (OSError, ValueError):
        feature = None
    return row, feature, log_path


def _wait_for_capacity():
    for _ in range(360):
        try:
            info = session.plan()
        except Exception:  # noqa: BLE001 - the account may not answer; go ahead
            return
        limit = info.get("parallel_sessions_max_allowed") or 0
        if not limit or info.get("parallel_sessions_running", 0) < limit:
            return
        time.sleep(10)


def _evidence(out, row):
    path = out / "cases" / row.folder / "evidence.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), path
    except (OSError, ValueError):
        return {}, path


def row_wanted(row, wanted):
    """Whether a --row entry names this row: the row id with or without its
    platform, or the scenario id alone (every row of that scenario)."""
    without_platform = row.id.split("/", 1)[1]
    return any(key in wanted for key in (row.id, without_platform, f"{row.platform}/{row.case_id}", row.case_id))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m mobiletest.run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--features", nargs="*", help="folders behave runs; default: every features/<platform>/<KEY>/<id> (and features/<platform>/<KEY> of an issue exported as one feature)")
    parser.add_argument("--platform", action="append", dest="platforms", help="android or ios; repeatable")
    parser.add_argument("--tags", action="append", default=[], help="behave tag expression, for example @FX-12; repeatable")
    parser.add_argument("--case", help="only this scenario id")
    parser.add_argument("--example", help="only this Examples row")
    parser.add_argument("--name", help="only rows whose name matches this regex")
    parser.add_argument("--row", action="append", default=[], help="only this row: <scenario id>, or <scenario id>#<example> in an issue exported with Examples, each optionally prefixed <platform>/; repeatable")
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--label", help="run id; default local-<time>")
    parser.add_argument("--out", help="output directory; default runs/<label>")
    parser.add_argument("--collect-video", action="store_true")
    parser.add_argument("--wait-capacity", action="store_true", help="start a row only when the account has a free parallel session")
    parser.add_argument("--list", action="store_true", help="list the rows and exit")
    parser.add_argument("--check", action="store_true", help="check that every step of every selected feature has a definition (behave --dry-run in each folder), without a device, and exit")
    args = parser.parse_args(argv)

    if args.check:
        return check(feature_dirs(args.platforms, args.features), args.tags)
    label = args.label or time.strftime("local-%Y%m%d%H%M%S")
    out = Path(args.out) if args.out else REPO_ROOT / "runs" / label
    rows = []
    for directory in feature_dirs(args.platforms, args.features):
        rows.extend(enumerate_rows(directory, args.tags))
    if args.case:
        rows = [r for r in rows if r.case_id == args.case]
    if args.example:
        rows = [r for r in rows if r.example == args.example]
    if args.name:
        pattern = re.compile(args.name)
        rows = [r for r in rows if pattern.search(r.name)]
    if args.row:
        wanted = {w.strip() for w in args.row if w.strip()}
        rows = [r for r in rows if row_wanted(r, wanted)]
    if args.list:
        print(json.dumps([{"id": r.id, "name": r.name, "feature": r.feature_file.relative_to(REPO_ROOT).as_posix(), "tags": r.tags} for r in rows], indent=2))
        return 0
    if not rows:
        print("no scenario rows match", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    (out / "cases").mkdir(exist_ok=True)
    for row in {r.feature_file: r for r in rows}.values():
        target = out / row.script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row.feature_file, target)
    suite = ", ".join(sorted({r.issue for r in rows}))
    matrix = report.Matrix(out / "matrix.json", suite, label, rows)
    _emit(matrix.update("", status=None))

    features = []
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures = {}
        for i, row in enumerate(rows, start=1):
            futures[pool.submit(run_row, row, out, label, args.tags, args.collect_video, i, args.wait_capacity)] = row
            _emit(matrix.update(row.id, status="running", started_at=report.now()))
        for future in concurrent.futures.as_completed(futures):
            row, feature, log_path = future.result()
            evidence, evidence_path = _evidence(out, row)
            if feature is not None:
                element = feature["elements"][0]
                report.fill_error(element, evidence.get("error"))
                status = report.scenario_status(element)
                error = report.scenario_error(element)
                duration = report.scenario_duration_ms(element)
                features.append(feature)
            else:
                status, duration = "failed", 0
                error = evidence.get("error", {}).get("message") if isinstance(evidence.get("error"), dict) else ""
                error = error or f"behave produced no result; see {log_path.relative_to(out)}"
            if status == "skipped":
                status = "failed"
                error = error or "the row was not run: no step ran; see the row's log"
            if status == "failed":
                failed += 1
            fields = {
                "status": status,
                "duration_ms": duration or evidence.get("duration_ms"),
                "device": evidence.get("device"),
                "session_url": evidence.get("session_url"),
                "evidence": f"cases/{row.folder}/evidence.json" if evidence_path.exists() else "",
                "video": f"cases/{row.folder}/video.mp4" if evidence.get("video") else "",
                "video_error": evidence.get("video_error"),
                "screenshots": len(evidence.get("screenshots") or []),
                "fallback_hits": len(evidence.get("fallback_hits") or []),
                "error": error if status == "failed" else "",
                "finished_at": report.now(),
            }
            _emit(matrix.update(row.id, **fields))

    cucumber_dir = out / "cucumber"
    cucumber_dir.mkdir(exist_ok=True)
    merged = report.merge(features)
    with open(cucumber_dir / "cucumber.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    summary = matrix.doc["summary"]
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump({"run": label, "summary": summary, "rows": matrix.doc["rows"], "cucumber": "cucumber/cucumber.json", "matrix": "matrix.json"}, f, indent=2)
    print(f"{summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed of {summary.get('total', 0)} rows; results in {out}")
    return 1 if failed else 0


def check(dirs, tags):
    """behave --dry-run in each folder: every step has a definition. Each
    scenario folder has steps of its own, so behave runs one folder at a
    time."""
    if not dirs:
        print("no feature folders", file=sys.stderr)
        return 2
    failed = []
    for directory in dirs:
        cmd = [sys.executable, "-m", "behave", str(directory), "--dry-run", "--no-summary", "--no-color", "--format", "progress"] + tag_args(tags)
        if subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode != 0:
            failed.append(directory)
    for directory in failed:
        print(f"steps without a definition in {directory.relative_to(REPO_ROOT).as_posix() if directory.is_relative_to(REPO_ROOT) else directory}", file=sys.stderr)
    print(f"{len(dirs) - len(failed)} of {len(dirs)} feature folders have every step defined")
    return 1 if failed else 0


def _emit(text):
    if text:
        print("EFP-MATRIX " + text, flush=True)


if __name__ == "__main__":
    sys.exit(main())
