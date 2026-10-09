# Mobile scenario tests

The mobile scenario tests that EFP assistants generate, as a plain Python project: behave features and their step definitions on top of the Appium Python client, run on BrowserStack real devices by the Jenkins pipeline in [Jenkinsfile](Jenkinsfile). Nothing in this repository depends on EFP; a laptop with Python and a BrowserStack account runs the same tests.

Working here as an agent, or with one: read [AGENTS.md](AGENTS.md) first; it says what to change, what to leave alone, and how to prove a change.

The flow around this repository:

1. A tester records a whole scenario of a Jira issue on a BrowserStack device from their own computer, through the Portal's Mobile testing panel and the local bridge.
2. The assistant compiles the recording into the scenario's script (`mobile-auto inspector script`): every recorded action in its order, swipes as they were made, coordinate taps named by the element under the finger, values as typed, passwords read from the test users file. The panel replays the script on the device; another scenario is another recording, or a copy of a script with its values changed.
3. The assistant exports the approved scenarios here (`mobile-auto test export --scripts`) on a branch `efp/<KEY>`: one folder per scenario with its feature (one plain Scenario in the words the business analyst approved), its step definitions (the script's steps as literal Python), and a config file with the app and device. Every generated line that comes from a recording carries a `# recorded:` comment with the recorded call, so what was recorded and what the assistant added are told apart in review.
4. The pipeline runs the scenarios in parallel, one session each, and publishes a Cucumber report, JUnit results, and one folder of evidence (a screenshot after every step, the screen at a failure, the video) per scenario.

After the export, the Python is the source: fixes go into the scenario's step definitions here, by the assistant or by a person. The export never overwrites a file that was edited by hand.

## Layout

| Path | What it is |
| --- | --- |
| `features/<platform>/<KEY>/<id>/<id>.feature` | One scenario of a Jira issue on one platform: a plain Scenario, its values in its steps |
| `features/<platform>/<KEY>/<id>/steps/<id>_steps.py` | Its step definitions: the recorded actions, in order, as literal `mobiletest` calls; passwords come from `secret("NAME")` |
| `features/<platform>/<KEY>/<id>/environment.py` | behave hooks (imports `mobiletest.hooks`): one BrowserStack session per scenario, evidence per scenario |
| `config/<KEY>.<platform>.yaml` | The app (a custom id or `bs://` URL), device, OS version, network (`public` for an app that needs no tunnel; left out, or anything else, the session goes through the BrowserStack Local tunnel), the Appium version BrowserStack runs (`appium_version`, 2.19.0 unless set; `BROWSERSTACK_APPIUM_VERSION` overrides it for a run), the secrets the tests need, and the scenario titles' ids |
| `mobiletest/` | The helpers: `find` with fallbacks and drift detection, actions, checks with timeouts, screenshots, the session, the runner, and the report |
| `runs/<label>/` | A run's results (not committed): `matrix.json`, `cucumber/cucumber.json`, `junit/`, `cases/<row>/evidence.json` with screenshots and video, `logs/` |

## Running

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
export BROWSERSTACK_USERNAME=... BROWSERSTACK_ACCESS_KEY=...
# The test accounts: a JSON map of profiles (see "Test users" below); MOBILE_TEST_USER picks one, default unless set
export MOBILE_TEST_USERS_FILE=$HOME/mobile-test-users.json
# The tunnel (every config uses it unless it says network: public): start it first and name it for the sessions
BrowserStackLocal --key "$BROWSERSTACK_ACCESS_KEY" --local-identifier local-1 --daemon start
export BROWSERSTACK_LOCAL_IDENTIFIER=local-1

# Every scenario of FX-12 on Android, four devices at a time
.venv/bin/python -m mobiletest.run --platform android --tags @FX-12 --parallel 4 --label local-1 --collect-video

# One scenario again
.venv/bin/python -m mobiletest.run --row buy-100-usd --label local-2

# What would run, and whether every step has a definition
.venv/bin/python -m mobiletest.run --platform android --tags @FX-12 --list
.venv/bin/python -m mobiletest.run --check

# Plain behave, one scenario folder, no matrix
.venv/bin/behave features/android/FX-12/buy-100-usd -D evidence_dir=runs/local/cases
```

The runner starts one `behave` process per scenario, prints the matrix as `EFP-MATRIX <json>` whenever it changes, and merges the scenarios' JSON into `runs/<label>/cucumber/cucumber.json`. Rows from several platforms share one run: their ids read `android/buy-100-usd` and `ios/buy-100-usd`. An issue exported before scenario scripts, as one feature with Scenario Outlines in `features/<platform>/<KEY>/`, still runs: each of its Examples rows is a row, `android/buy-foreign-currency#USD`.

The gestures (`swipe`, `tap_point`, `long_press`, `double_tap`) send the same W3C actions as mobile-auto's replay of the script on the device, so a scenario that passed its replay makes the same moves here; `tests/test_literal_gestures.py` pins them.

`MOBILETEST_FAKE_DRIVER=1` runs everything against a stand-in driver, without a device or an account: the smoke test in `tests/` uses it to check the project, the runner, and the report end to end.

### Test users

The accounts the tests sign in with live in one JSON file, a map of profiles: `default` and any others, each with the fields the app asks for.

```json
{
  "default": {"username": "uat-fx-01", "password": "...", "pin": "1234"},
  "vip": {"username": "uat-fx-vip", "password": "..."}
}
```

The team keeps it in Jenkins as a *Secret file* credential, `mobile-test-users` unless a build names another in `TEST_PROFILE_CREDENTIALS_ID` (a second file for another environment, say); the job hands it to the tests as `MOBILE_TEST_USERS_FILE`, and a build signs in with the `default` profile. In the tests, `secret("MOBILE_SECRET_PASSWORD")`, which recorded password fields turn into, reads the profile's `password` (the name without `MOBILE_SECRET_`, in lower case); `user_value("username")` reads any other field, `user_value("username", "vip")` another profile's; `profile()` the whole map. An environment variable named like the secret (`MOBILE_SECRET_PASSWORD`) still wins, so one value can be passed without a file, and `MOBILE_TEST_USER` picks another profile on a laptop. The values never pass through the assistant: it knows only the field names a script needs.

## The Jenkins job

1. Create a **Pipeline** job, for example `mobile/mobile-scenarios`, with *Pipeline script from SCM* pointing at this repository and `Jenkinsfile` as the script path. The job's SCM credentials are reused to check out the branch a build asks for.
2. Give it an agent, labelled `linux` unless `MOBILE_AGENT_LABEL` says otherwise, with Python 3.9+, `bash`, `curl`, and `tar`, that reaches:
   - `hub-cloud.browserstack.com` and `api-cloud.browserstack.com` on port 443;
   - a PyPI index for the requirements;
   - wherever app builds are downloaded from.

   Set `HTTPS_PROXY` on the agent if it needs a proxy. The job's own settings are set once, never as build parameters: as **Folder Properties** on the folder holding the job (the *Folder Properties* plugin; each team's folder keeps its own, a sub-folder's override its parent's, and a folder property wins over an environment variable of the same name), or as environment variables on the agent (its node properties) or under *Manage Jenkins > System > Global properties*:

   | Variable | Meaning | Default |
   | --- | --- | --- |
   | `MOBILE_AGENT_LABEL` | The agent label the job runs on | `linux` |
   | `MOBILE_PYTHON` | The Python 3.9+ interpreter on the agent | `python3` |
   | `MOBILE_PIP_INDEX_URL` | A PyPI index for the requirements, such as an internal Nexus proxy | pip's default |
   | `MOBILE_LOCAL_BINARY_URL` | Where the BrowserStackLocal binary is downloaded from; a copy in your artifact repository works. An absolute path uses that program on the agent; `installed` uses the `BrowserStackLocal` on the agent's `PATH` | browserstack.com |
   | `MOBILE_LOCAL_PROXY` | `http://host:port`, or `http://user:password@host:port` (percent-encoded) when the proxy asks for a login, that the tunnel goes out through | the agent's `HTTPS_PROXY` |
   | `MOBILE_BROWSERSTACK_CREDENTIALS_ID` | The *Username with password* credential with the BrowserStack account | `browserstack` |
   A setting or parameter left empty is absent from the environment of the processes the job starts (Jenkins drops empty variables when it launches one), so an empty value never means anything here: say `installed` where the table offers it.
3. Credentials, in the folder's own credentials store or a global one (an id is looked up from the job's folder upwards):
   - `browserstack`: *Username with password*, holding the BrowserStack username and access key the runs use (another id: `MOBILE_BROWSERSTACK_CREDENTIALS_ID`).
   - `mobile-test-users`: *Secret file*, the test users JSON file described under "Test users" (a build can name another file in `TEST_PROFILE_CREDENTIALS_ID`). Whoever manages the test accounts uploads a new version of the file when they change; `config/<KEY>.<platform>.yaml` lists under `secrets` the fields its tests need.
4. Install the **Folder Properties** plugin: the Jenkinsfile's `withFolderProperties()` option needs it, even for a job that keeps its settings as environment variables (the folder's *Expose these properties at build start* box can stay unticked). Install the **Cucumber Reports** plugin to see each run's report on the build page; without it the build still archives `cucumber.json` and publishes the JUnit results.
5. The apps live on the private network, so every build starts a BrowserStack Local tunnel: the job downloads the BrowserStackLocal binary (`MOBILE_LOCAL_BINARY_URL`) and starts one tunnel per build, named after the run, through `MOBILE_LOCAL_PROXY` or the agent's `HTTPS_PROXY`; the sessions attach to it, unless a config says `network: public`. The agent must reach the app's servers. The stage fails with the binary's own message when the tunnel does not connect (its exit code is not trusted), and *Run scenarios* checks the tunnel is still running before it starts; a session that BrowserStack still refuses with *Please set up Local Testing to test* means the tunnel went away in between.
6. Run the job once by hand with the parameters filled in; Jenkins only picks up a pipeline's parameters after its first run.
7. Tell the assistant the job path and this repository once. The `generate-mobile-scripts` skill asks for them and keeps them in the scenario plan, together with the credentials ids of the test secrets.

### Parameters

| Parameter | Meaning |
| --- | --- |
| `BRANCH_NAME` | Branch, tag, or commit of this repository to run (the assistant pushes `efp/<KEY>`); empty runs the job's configured branch |
| `PLATFORMS` | `all`, `android`, or `ios` |
| `TAGS` | behave tag expressions a scenario must match, for example `@FX-12` (the issue's tag); empty runs everything |
| `SCENARIOS` | Optional: only these scenarios, by id (`buy-100-usd`), each optionally prefixed `<platform>/`; in an issue exported with Examples, `<scenario id>` runs every row and `<scenario id>#<example>` one; a dry run or a rerun |
| `ANDROID_APP_ID`, `IOS_APP_ID` | Optional: a build already on BrowserStack (`bs://...` or its custom id) to test instead of the one `config/<KEY>.<platform>.yaml` names |
| `TEST_PROFILE_CREDENTIALS_ID` | The *Secret file* credential holding the test users file (`mobile-test-users`) |
| `PARALLEL` | Sessions at a time; the runner waits for free parallel sessions when others use the account |
| `COLLECT_VIDEO` | Download each session's video into the evidence (default on) |

Results land in `runs/build-<build number>/`, and the BrowserStack build and the Local tunnel take that name too.

### What a build publishes

- The Cucumber report (the plugin) and the JUnit results.
- Artifacts under `runs/<RUN_LABEL>/`: `matrix.json`, `report.json`, `cucumber/cucumber.json`, `evidence.tar.gz` (the matrix, every row's `evidence.json`, screenshots, the failure screen and page source, the JUnit files, and the feature files that ran), and `cases/**/video.mp4`.
- `EFP-MATRIX` lines in the console log while the run goes.

Failed scenarios make the build UNSTABLE; a build that could not run anything (no row matched, no Python, no credentials) FAILS.

## How the assistant uses the pipeline

1. It pushes the issue's files to the branch `efp/<KEY>` and opens a pull request into the base branch once the dry run is approved.
2. It starts the job with `jenkins job build-with-params`: `BRANCH_NAME`, `PLATFORMS`, `TAGS` (the issue key), `TEST_PROFILE_CREDENTIALS_ID` from the plan, and `SCENARIOS` for a dry run or a rerun.
3. It follows the console log's `EFP-MATRIX` lines into `mobile/runs/<task id>/matrix.json` in its workspace, which the Portal task page shows live.
4. At the end it downloads `evidence.tar.gz` and the videos it needs from `runs/build-<build number>/` into `mobile/runs/<task id>/`. The layout is the same as on the agent, so every relative path in the evidence resolves.
