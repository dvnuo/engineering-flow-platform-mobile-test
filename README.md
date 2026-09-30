# Mobile scenario tests

The mobile scenario tests that EFP assistants generate, as a plain Python project: behave features, step definitions, and segment modules on top of the Appium Python client, run on BrowserStack real devices by the Jenkins pipeline in [Jenkinsfile](Jenkinsfile). Nothing in this repository depends on EFP; a laptop with Python and a BrowserStack account runs the same tests.

The flow around this repository:

1. A tester records short app segments (log in, skip the introduction, choose a currency) on a BrowserStack device from their own computer, through the Portal Recording panel and the local bridge.
2. The assistant compiles the recordings, binds the checks of the approved scenarios of a Jira issue, and exports the result here (`mobile-auto test export`) on a branch `efp/<KEY>`: the feature file the business analyst approved, its step definitions, the segments as Python functions, and a config file with the app, device, and test data. Every generated line that comes from a recording carries a `# recorded:` comment with the recorded call, so what was recorded and what the assistant added are told apart in review.
3. The pipeline runs the scenario rows in parallel, one session per Examples row, and publishes a Cucumber report, JUnit results, and one folder of evidence (screenshots, the screen at a failure, the video) per row.

After the export, the Python is the source: fixes go into the step definitions and the segment modules here, by the assistant or by a person. The export never overwrites a file that was edited by hand.

## Layout

| Path | What it is |
| --- | --- |
| `features/<platform>/<KEY>/<KEY>.feature` | The Gherkin of one Jira issue on one platform: Background, Scenario Outlines, Examples |
| `features/<platform>/<KEY>/steps/<KEY>_steps.py` | Its step definitions: each Gherkin step calls segment functions and `mobiletest` helpers |
| `features/<platform>/<KEY>/environment.py` | behave hooks (imports `mobiletest.hooks`): one BrowserStack session per scenario row, evidence per row |
| `segments/<platform>/<segment>.py` | A recorded flow as a function of the driver and its parameters; passwords come from `secret("NAME")` |
| `config/<KEY>.<platform>.yaml` | The app (a custom id or `bs://` URL), device, OS version, network (`private-managed` when the app talks to servers on the private network), test data, the secrets the tests need, and the scenario titles' ids |
| `mobiletest/` | The helpers: `find` with fallbacks and drift detection, actions, checks with timeouts, screenshots, the session, the runner, and the report |
| `runs/<label>/` | A run's results (not committed): `matrix.json`, `cucumber/cucumber.json`, `junit/`, `cases/<row>/evidence.json` with screenshots and video, `logs/` |

## Running

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
export BROWSERSTACK_USERNAME=... BROWSERSTACK_ACCESS_KEY=... MOBILE_SECRET_PASSWORD=...
# An app on the private network: start a tunnel first and name it for the sessions
BrowserStackLocal --key "$BROWSERSTACK_ACCESS_KEY" --local-identifier local-1 --daemon start
export BROWSERSTACK_LOCAL_IDENTIFIER=local-1

# Every row of FX-12 on Android, four devices at a time
.venv/bin/python -m mobiletest.run --platform android --tags @FX-12 --parallel 4 --label local-1 --collect-video

# One row again
.venv/bin/python -m mobiletest.run --row buy-foreign-currency#USD --label local-2

# What would run
.venv/bin/python -m mobiletest.run --platform android --tags @FX-12 --list

# Plain behave, one row after the other, no matrix
.venv/bin/behave features/android/FX-12 --tags @FX-12 -D evidence_dir=runs/local/cases
```

The runner starts one `behave` process per scenario row, prints the matrix as `EFP-MATRIX <json>` whenever it changes, and merges the rows' JSON into `runs/<label>/cucumber/cucumber.json`. Rows from several platforms share one run: their ids read `android/buy-foreign-currency#USD` and `ios/buy-foreign-currency#USD`.

`MOBILETEST_FAKE_DRIVER=1` runs everything against a stand-in driver, without a device or an account: the smoke test in `tests/` uses it to check the project, the runner, and the report end to end.

## The Jenkins job

1. Create a **Pipeline** job, for example `mobile/mobile-scenarios`, with *Pipeline script from SCM* pointing at this repository and `Jenkinsfile` as the script path. The job's SCM credentials are reused to check out the branch a build asks for.
2. Give it an agent, labelled `linux` by default, with Python 3.9+ (`PYTHON` names the interpreter), `bash`, `curl`, and `tar`, that reaches:
   - `hub-cloud.browserstack.com` and `api-cloud.browserstack.com` on port 443;
   - a PyPI index for the requirements (`PIP_INDEX_URL` for an internal Nexus proxy);
   - wherever app builds are downloaded from.

   Set `HTTPS_PROXY` on the agent if it needs a proxy.
3. Credentials:
   - `browserstack`: *Username with password*, holding the BrowserStack username and access key the runs use. Another id can be passed in `BROWSERSTACK_CREDENTIALS_ID`.
   - One *Secret text* per test account password the tests read with `secret("NAME")`. Recorded password fields name them, for example `MOBILE_SECRET_PASSWORD`; each `config/<KEY>.<platform>.yaml` lists the names its tests need. Builds pass them as `TEST_SECRETS=MOBILE_SECRET_PASSWORD=fx-uat-password,MOBILE_SECRET_PIN=fx-uat-pin`, each name mapped to its credentials id.
   - `APP_CREDENTIALS_ID` when builds come from Nexus or Jenkins behind a login.
4. Install the **Cucumber Reports** plugin to see each run's report on the build page; without it the build still archives `cucumber.json` and publishes the JUnit results.
5. Apps on a private network: leave `LOCAL` on. The job downloads the BrowserStackLocal binary (`LOCAL_BINARY_URL`, a copy in your artifact repository works) and starts one tunnel per build, named after the run, through `LOCAL_PROXY` or the agent's `HTTPS_PROXY`; the sessions of the configs whose `network` is private attach to it. The agent must reach the app's servers. For apps on the public internet set `LOCAL` to false.
6. Run the job once by hand with the parameters filled in; Jenkins only picks up a pipeline's parameters after its first run.
7. Tell the assistant the job path and this repository once. The `generate-mobile-scripts` skill asks for them and keeps them in the scenario plan, together with the credentials ids of the test secrets.

### Parameters

| Parameter | Meaning |
| --- | --- |
| `SCRIPTS_REF` | Branch, tag, or commit of this repository to run; empty runs the job's configured branch |
| `PLATFORMS` | `android`, `ios`, or both |
| `TAGS` | behave tag expressions a scenario must match, for example `@FX-12`; empty runs everything |
| `ROWS`, `CASE`, `EXAMPLE` | Narrow a build to rows (`<scenario id>#<example>`), one scenario, or one Examples row: a dry run or a rerun |
| `RUN_LABEL` | Run id; results land in `runs/<RUN_LABEL>/` and the BrowserStack build takes the same name |
| `PARALLEL` | Sessions at a time; the runner waits for free parallel sessions when others use the account |
| `COLLECT_VIDEO` | Download each session's video into the evidence (default on) |
| `APP_FILE_URL`, `APP_CUSTOM_ID`, `APP_CREDENTIALS_ID` | Optional build to upload first; give every build of an app the same custom id |
| `BROWSERSTACK_CREDENTIALS_ID`, `TEST_SECRETS` | Credentials, as above |
| `LOCAL`, `LOCAL_BINARY_URL`, `LOCAL_PROXY` | A BrowserStack Local tunnel for the run (default on), where its binary comes from, and the proxy it goes out through |
| `PIP_INDEX_URL`, `PYTHON`, `AGENT_LABEL` | The agent's Python and package index |

### What a build publishes

- The Cucumber report (the plugin) and the JUnit results.
- Artifacts under `runs/<RUN_LABEL>/`: `matrix.json`, `report.json`, `cucumber/cucumber.json`, `evidence.tar.gz` (the matrix, every row's `evidence.json`, screenshots, the failure screen and page source, the JUnit files, and the feature files that ran), and `cases/**/video.mp4`.
- `EFP-MATRIX` lines in the console log while the run goes.

Failed scenarios make the build UNSTABLE; a build that could not run anything (no row matched, no Python, no credentials) FAILS.

## How the assistant uses the pipeline

1. It pushes the issue's files to the branch `efp/<KEY>` and opens a pull request into the base branch once the dry run is approved.
2. It starts the job with `jenkins job build-with-params`: `SCRIPTS_REF`, `PLATFORMS`, `TAGS` (the issue key), `RUN_LABEL` (the Portal task id), `TEST_SECRETS`, and `ROWS` for a rerun.
3. It follows the console log's `EFP-MATRIX` lines into `mobile/runs/<task id>/matrix.json` in its workspace, which the Portal task page shows live.
4. At the end it downloads `evidence.tar.gz` and the videos it needs into `mobile/runs/<RUN_LABEL>/`. The layout is the same as on the agent, so every relative path in the evidence resolves.
