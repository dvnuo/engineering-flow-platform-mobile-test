# Mobile scenario tests

The mobile scenario tests that EFP assistants generate, and the Jenkins pipeline that runs them on BrowserStack real devices.

The flow around this repository:

1. A tester records short app segments (log in, skip the introduction, choose a currency) on a BrowserStack device from their own computer, through the Portal Recording panel and the local bridge.
2. The assistant compiles the recordings into segments, turns the approved scenarios of a Jira issue into one fixed script per Examples row, and commits everything under `mobile/` on a branch of this repository.
3. The pipeline in [Jenkinsfile](Jenkinsfile) runs the scripts in parallel with `mobile-auto`, prints the scenario matrix to its console log, and archives one result, screenshots, and a video per scenario row.

Neither Portal nor the assistant's pod ever connects to BrowserStack; the tester's computer and the Jenkins agent do.

## Layout

| Path | What it is | Written by |
| --- | --- | --- |
| `mobile/scenarios/<KEY>/` | The scenario plan (`efp-scenario-plan/v1`) and the feature file of a Jira issue | the assistant (`design-mobile-scenarios`) |
| `mobile/segments/<platform>/<segment>.yaml` | Recorded, reusable flows | the assistant (`record-mobile-segment`) |
| `mobile/suites/<KEY>/<platform>.yaml` | One suite per issue and platform: one case per scenario, its Examples rows as the case's matrix | the assistant (`generate-mobile-scripts`) |
| `mobile/scripts/<KEY>/<platform>/<case>_<row>.yaml` | One compiled, self-contained script per scenario row (`efp-mobile-script/v1`); never edited by hand | `mobile-auto test compile` |
| `mobile/runs/<RUN_LABEL>/` | A run's matrix and evidence | the pipeline, on the agent; archived, not committed |

Recordings (`mobile/recordings/`) and runs stay in the assistant's workspace and on the agent; `.gitignore` keeps them out of commits. A scenario file format reference is in the tools repository's `docs/MOBILE_AUTO_SKILL_WORKFLOW.md`.

## How the assistant uses the pipeline

1. It pushes the issue's files to the branch `efp/<KEY>` and opens a pull request into the base branch once the dry run is approved.
2. It starts the job with `jenkins job build-with-params`:
   - `SCRIPTS_REF`: the branch it pushed;
   - `SCRIPTS`: the script directories or files to run;
   - `RUN_LABEL`: the Portal task id;
   - `TEST_SECRETS`: the credentials ids of the test accounts' passwords.
3. It follows the console log. Whenever the scenario matrix changes, the job prints it on one line prefixed `EFP-MATRIX`. The assistant copies it to `mobile/runs/<task id>/matrix.json` in its workspace, which the Portal task page shows live.
4. At the end it downloads these artifacts into `mobile/runs/<RUN_LABEL>/`:
   - `evidence.tar.gz`: the matrix, evidence, screenshots, failure details, JUnit, and the report;
   - the videos it needs, from `cases/**/video.mp4`.

   Because the job keeps the workspace layout, every relative path in the evidence resolves the same way there.

## Setting up the job

1. Create a **Pipeline** job, for example `mobile/mobile-scenarios`, with *Pipeline script from SCM* pointing at this repository and `Jenkinsfile` as the script path. The job's SCM credentials are reused to check out the branch a build asks for.
2. Give it an agent, labelled `linux` by default, that reaches:
   - `hub-cloud.browserstack.com` and `api-cloud.browserstack.com` on port 443;
   - wherever `mobile-auto` and app builds are downloaded from.

   Set `HTTPS_PROXY` on the agent if it needs a proxy; `mobile-auto` uses it. `bash`, `curl`, and `tar` must be installed.
3. Credentials:
   - `browserstack`: *Username with password*, holding the BrowserStack username and access key the runs use. Another id can be passed in `BROWSERSTACK_CREDENTIALS_ID`.
   - One *Secret text* per test account password the scripts type. Recorded password fields name them, for example `MOBILE_SECRET_PASSWORD`. Builds pass them as `TEST_SECRETS=MOBILE_SECRET_PASSWORD=fx-uat-password,MOBILE_SECRET_PIN=fx-uat-pin`, each name mapped to its credentials id.
   - `APP_CREDENTIALS_ID` when builds come from Nexus or Jenkins behind a login.
4. `mobile-auto`: set `MOBILE_AUTO_URL` to the linux-amd64 binary of an engineering-flow-platform-tools release (or its copy in your artifact repository), or install `mobile-auto` on the agent's PATH.
5. Run the job once by hand with the parameters filled in; Jenkins only picks up a pipeline's parameters after its first run.
6. Tell the assistant the job path and this repository once. The `generate-mobile-scripts` skill asks for them and keeps them in the scenario plan, together with the credentials ids of the test secrets.

## Parameters

| Parameter | Meaning |
| --- | --- |
| `SCRIPTS_REF` | Branch, tag, or commit of this repository to run; empty runs the job's configured branch |
| `SCRIPTS` | Space-separated directories (every script inside) or files; paths inside the repository |
| `RUN_LABEL` | Run id; results land in `mobile/runs/<RUN_LABEL>/` and the BrowserStack build takes the same name |
| `PARALLEL` | Sessions at a time; `--wait-capacity` queues the rest when others use the account |
| `CASE`, `MATRIX` | Optional filters for one scenario or one Examples row |
| `COLLECT_VIDEO` | Download each session's video (default on) |
| `APP_FILE_URL`, `APP_CUSTOM_ID`, `APP_CREDENTIALS_ID` | Optional build to upload first; give every build of an app the same custom id |
| `MOBILE_AUTO_URL` | mobile-auto binary to download; empty uses PATH |
| `BROWSERSTACK_CREDENTIALS_ID`, `TEST_SECRETS` | Credentials, as above |
| `AGENT_LABEL` | Agent label (default `linux`) |

Rows from more than one directory get the directory name in front of their id (`android/buy-currency#USD`), so both platforms share one matrix and one pool of parallel sessions. Failed scenarios make the build UNSTABLE; the evidence is archived either way.

## Running a script by hand

The scripts are plain `mobile-auto` files, so a tester with the tools and a BrowserStack account can run one from a checkout:

```bash
export BROWSERSTACK_USERNAME=... BROWSERSTACK_ACCESS_KEY=... MOBILE_SECRET_PASSWORD=...
mobile-auto test run --file mobile/scripts/FX-12/android/buy-foreign-currency_USD.yaml --evidence-dir /tmp/fx-12/cases --collect-video --json
```
