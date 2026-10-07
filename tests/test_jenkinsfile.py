"""The Jenkinsfile keeps the shape the README and the assistant's skills
describe: the job's settings come from Folder Properties (or environment
variables) and never from build parameters, the agent is chosen once the
folder's properties are in the environment, and the parameters are the
documented ones.

    python tests/test_jenkinsfile.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JENKINSFILE = (ROOT / "Jenkinsfile").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

PARAMETERS = ["BRANCH_NAME", "PLATFORMS", "TAGS", "SCENARIOS", "ANDROID_APP_ID", "IOS_APP_ID", "TEST_PROFILE_CREDENTIALS_ID", "PARALLEL", "COLLECT_VIDEO"]
SETTINGS = ["MOBILE_AGENT_LABEL", "MOBILE_PYTHON", "MOBILE_PIP_INDEX_URL", "MOBILE_LOCAL_BINARY_URL", "MOBILE_LOCAL_PROXY", "MOBILE_BROWSERSTACK_CREDENTIALS_ID"]
# What a build or a team may leave empty.
OPTIONAL = ["TAGS", "SCENARIOS", "ANDROID_APP_ID", "IOS_APP_ID", "MOBILE_PYTHON", "MOBILE_PIP_INDEX_URL", "MOBILE_LOCAL_BINARY_URL", "MOBILE_LOCAL_PROXY"]


def block(text, opener):
    """The text of the first `opener {` block, braces balanced."""
    start = text.index(opener)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unbalanced block {opener!r}")


def test_settings_come_from_folder_properties_not_parameters():
    options = block(JENKINSFILE, "options {")
    assert "withFolderProperties()" in options
    for name in SETTINGS:
        assert f"env.{name}" in JENKINSFILE or f"${{{name}" in JENKINSFILE, name
        assert f"name: '{name}'" not in JENKINSFILE, f"{name} must not be a build parameter"
    # The README's settings table names the same six.
    table = README[README.index("| Variable | Meaning | Default |") :]
    for name in SETTINGS:
        assert f"| `{name}` |" in table, name
    assert "Folder Properties" in README


def test_the_agent_is_chosen_inside_the_folder_properties():
    # No pipeline-level agent: the label would be read before the folder's
    # properties are in the environment. The stage holding every other stage
    # chooses it, and its post publishes the results on the same agent.
    assert re.search(r"^  agent none$", JENKINSFILE, re.M)
    outer = block(JENKINSFILE, "    stage('Mobile scenarios') {")
    assert "agent { label \"${env.MOBILE_AGENT_LABEL ?: 'linux'}\" }" in outer
    assert "      stages {" in outer and "      post {" in outer
    assert "\n  post {" not in JENKINSFILE
    for stage in ("Check parameters", "Check out", "Python environment", "BrowserStack Local", "Run scenarios"):
        assert f"stage('{stage}')" in outer, stage


def test_parameters_are_the_documented_ones():
    params = block(JENKINSFILE, "parameters {")
    assert re.findall(r"name: '([A-Z_]+)'", params) == PARAMETERS
    for name in PARAMETERS:
        assert f"`{name}`" in README, name


def test_optional_values_are_read_with_defaults():
    # Jenkins drops an empty variable from the environment of a process it
    # starts, and the scripts run with set -u: a parameter or setting that may
    # be left empty is read with a default, never bare (the first real build
    # died on "SCENARIOS: unbound variable" with SCENARIOS left blank), and an
    # empty value is never a signal: BrowserStackLocal already on the agent is
    # asked for with the word installed.
    for name in OPTIONAL:
        assert "${" + name + "}" not in JENKINSFILE, name
        assert "${" + name + "-" not in JENKINSFILE, name
        assert "$" + name + " " not in JENKINSFILE and "$" + name + '"' not in JENKINSFILE, name
    assert "${TAGS:-}" in JENKINSFILE and "${SCENARIOS:-}" in JENKINSFILE
    assert "installed)" in JENKINSFILE and "`installed`" in README


if __name__ == "__main__":
    test_settings_come_from_folder_properties_not_parameters()
    test_the_agent_is_chosen_inside_the_folder_properties()
    test_parameters_are_the_documented_ones()
    test_optional_values_are_read_with_defaults()
    print("ok")
