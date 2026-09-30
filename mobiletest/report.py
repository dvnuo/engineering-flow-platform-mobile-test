"""behave's JSON to Cucumber JSON (what the Jenkins Cucumber Reports plugin
reads), and the scenario matrix (efp-matrix/v1)."""
import json
import re
import time

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text):
    return _SLUG.sub("-", str(text).lower()).strip("-") or "item"


def _line(node):
    location = str(node.get("location") or "")
    if ":" in location:
        try:
            return int(location.rsplit(":", 1)[1])
        except ValueError:
            pass
    return 1


def _tags(node):
    out = []
    for tag in node.get("tags") or []:
        name = tag.get("name") if isinstance(tag, dict) else str(tag)
        if not name:
            continue
        if not name.startswith("@"):
            name = "@" + name
        out.append({"name": name, "line": _line(node)})
    return out


def _status(result):
    status = str((result or {}).get("status") or "skipped")
    return {"untested": "skipped", "undefined": "undefined", "untitled": "skipped"}.get(status, status)


def to_cucumber(feature, platform, uri, keep_names=None):
    """One behave feature as a Cucumber JSON feature. keep_names limits the
    scenarios to those names (a row's own JSON also lists the rows that were
    skipped)."""
    fid = slug(f"{feature.get('name', 'feature')}-{platform}")
    elements = []
    for el in feature.get("elements") or []:
        if el.get("type") == "background":
            # behave lists the Background's steps inside every scenario already.
            continue
        if keep_names is not None and el.get("name") not in keep_names:
            continue
        steps = []
        for st in el.get("steps") or []:
            result = st.get("result") or {}
            entry = {"status": _status(result), "duration": int(float(result.get("duration") or 0) * 1e9)}
            message = result.get("error_message")
            if message:
                entry["error_message"] = "\n".join(message) if isinstance(message, list) else str(message)
            step = {"keyword": str(st.get("keyword", "")).strip() + " ", "name": st.get("name", ""), "line": _line(st), "result": entry}
            if st.get("match"):
                step["match"] = {"location": str(st["match"].get("location") or "")}
            embeddings = [{"mime_type": e.get("mime_type"), "data": e.get("data")} for e in st.get("embeddings") or [] if e.get("data")]
            if embeddings:
                step["embeddings"] = embeddings
            steps.append(step)
        elements.append({
            "id": f"{fid};{slug(el.get('name') or el.get('keyword') or 'scenario')}",
            "keyword": el.get("keyword") or "Scenario",
            "name": el.get("name") or "",
            "line": _line(el),
            "description": "",
            "type": "scenario",
            "tags": _tags(el),
            "steps": steps,
        })
    description = feature.get("description") or []
    return {
        "id": fid,
        "uri": uri,
        "keyword": "Feature",
        "name": f"{feature.get('name', '')} ({platform})",
        "line": _line(feature),
        "description": "\n".join(description) if isinstance(description, list) else str(description),
        "tags": _tags(feature),
        "elements": elements,
    }


def merge(features):
    """Features with the same uri become one, their scenarios in order."""
    merged = {}
    order = []
    for feature in features:
        key = feature["uri"]
        if key not in merged:
            merged[key] = dict(feature, elements=[])
            order.append(key)
        merged[key]["elements"].extend(feature["elements"])
    for feature in merged.values():
        feature["elements"].sort(key=lambda el: (el.get("line", 0), el.get("name", "")))
    return [merged[k] for k in order]


def scenario_status(element):
    """passed, failed, or skipped from a Cucumber scenario's steps."""
    statuses = [s["result"]["status"] for s in element.get("steps") or []]
    if any(s in ("failed", "undefined", "pending") for s in statuses):
        return "failed"
    if statuses and all(s == "passed" for s in statuses):
        return "passed"
    if any(s == "passed" for s in statuses):
        return "failed"
    return "skipped"


def scenario_error(element):
    for step in element.get("steps") or []:
        result = step.get("result") or {}
        if result.get("status") in ("failed", "undefined", "pending"):
            message = result.get("error_message") or f"{result.get('status')} step"
            first = str(message).strip().splitlines()
            return f"{step['keyword']}{step['name']}: {first[-1] if first else message}"[:500]
    return ""


def scenario_duration_ms(element):
    return int(sum(int((s.get("result") or {}).get("duration") or 0) for s in element.get("steps") or []) / 1e6)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Matrix:
    """The run's scenario matrix, rewritten as rows start and finish."""

    def __init__(self, path, suite, run, rows):
        self.path = path
        self.doc = {"format": "efp-matrix/v1", "suite": suite, "run": run, "started_at": now(), "updated_at": now(), "summary": {}, "rows": []}
        for row in rows:
            self.doc["rows"].append({"id": row.id, "case": row.case_id, "example": row.example, "status": "queued", "platform": row.platform, "script": row.script})
        self._last = ""

    def update(self, row_id, **fields):
        for row in self.doc["rows"]:
            if row["id"] == row_id:
                row.update({k: v for k, v in fields.items() if v not in (None, "", 0, [])} | {k: v for k, v in fields.items() if k == "status"})
                break
        summary = {"passed": 0, "failed": 0, "running": 0, "queued": 0}
        for row in self.doc["rows"]:
            summary[row["status"]] = summary.get(row["status"], 0) + 1
        summary["total"] = len(self.doc["rows"])
        self.doc["summary"] = summary
        self.doc["updated_at"] = now()
        text = json.dumps(self.doc, separators=(",", ":"))
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.doc, f, indent=2)
        if text != self._last:
            self._last = text
            return text
        return ""
