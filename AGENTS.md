# Working in this repository as an agent

For the EFP assistant working in its clone (`repos/<name>` in its workspace) and for any coding agent a person runs here. The README says what the project is and how the Jenkins job runs it; this file says what to change, what to leave alone, and how to prove a change.

## What this is

A plain Python test project: behave features and their step definitions on the Appium Python client, run on BrowserStack real devices by the Jenkins job in `Jenkinsfile`. `mobile-auto test export --scripts` writes it from an assistant's workspace (the scenario plan and one scenario script per scenario, each compiled from a recording of that scenario); after the export, the Python here is the source.

Each scenario is a folder of its own, `features/<platform>/<KEY>/<id>/`: one plain Scenario, its values written into its steps (no Scenario Outline, no Examples, no parameters), and step definitions that replay the recording literally, every recorded action in its order. An issue exported before scenario scripts (`features/<platform>/<KEY>/<KEY>.feature` with Examples, and `segments/`) still runs as it is.

## Who edits what

| Path | Edit it here? |
| --- | --- |
| `features/<platform>/<KEY>/<id>/<id>.feature` | No. It is the Gherkin the requirement owner approved; a change goes through the scenario plan, its review card, and a new export. |
| `features/<platform>/<KEY>/<id>/steps/<id>_steps.py` | Yes: this scenario's actions and checks, and nobody else's. A fix in one scenario does not reach its copies: make it in each one that needs it. |
| `config/<KEY>.<platform>.yaml` | Rarely: `device`, `os_version`, `appium_version`, `network` (`public` only for an app that needs no tunnel; every other config goes through BrowserStack Local). `app`, `secrets`, and `scenarios` come from the export. |
| `mobiletest/` | Yes, with a test in `tests/`; every suite shares it. |
| `Jenkinsfile`, `README.md`, this file | Yes. |
| `runs/` | Never committed: results. |

## Rules

- Preserve scenario intent: adapt how the app is driven, never what the scenario checks. A product defect stays a failing test with its evidence; do not bend the test to pass.
- Keep the `# recorded:` comment above a line you change: it says what the recording did.
- Keep the first line of a generated file (`# mobile-auto export: ... content_sha256=...`). Its hashes tell the exporter the file was edited by hand, so the next export keeps your change instead of overwriting it.
- Locators, in this order: accessibility id, resource id (Android) or name (iOS), then text; give `find` a `fallbacks=` route when the first one is fragile. Coordinates (`tap_point`) only when nothing identifies the element. Never `sleep`: use `wait_visible`, `wait_text`, `wait_gone`, `visible(..., timeout=)`, or `wait_stable`. A screen that only sometimes appears is guarded with `if visible(driver, ..., timeout=3):`.
- Gestures are the recording's: each recorded swipe is one `swipe(context.driver, start=(x, y), end=(x, y), duration_ms=...)` in percent of the window, and a tap nothing could name is `tap_point(..., hold_ms=...)`. They send the same W3C actions as the replay on the device. Never fold swipes into `scroll_to_end` or change their count to make a run pass: a scenario that no longer reaches its screen fails at that step's arrival check (`assert_visible` on the next screen), and the fix is to record the scenario again, or to change its script and replay it, then export again, so the script, its replay, and this file agree. Fix it here only when the recording flow is not available, and say so in the pull request.
- Values are literal: the account name, the amounts, and the expected results are written into the steps. Only passwords and other secrets come from the test users file (`secret(...)`). Never turn a value into a parameter, a `context.data` lookup, or an Examples column.
- Take a new target from the page source at the failure (`cases/<row>/source.xml` in the run's evidence), not from memory.
- Accounts: the test users file is a JSON map of profiles (`default` and any others, each with `username`, `password`, and whatever else the app asks for) kept in Jenkins as a Secret file credential. A build names that credential in its `TEST_PROFILE_CREDENTIALS_ID` parameter (`mobile-test-users` unless the team keeps several files, one per environment), the job hands the file to the tests as `MOBILE_TEST_USERS_FILE`, and the tests sign in with the `default` profile. On a laptop, export `MOBILE_TEST_USERS_FILE` yourself, and `MOBILE_TEST_USER` to use another profile. `secret("MOBILE_SECRET_PASSWORD")` (what a recorded password field turns into) reads the profile's `password`, the name without `MOBILE_SECRET_` in lower case; `user_value("username")` any other field, `user_value("username", "vip")` another profile's; `profile()` the whole map. Never write a value into a file, a log, a commit message, or a test name; never ask a person for one in chat.
- Ids: `config/<KEY>.<platform>.yaml` maps scenario titles to ids; a row is `<platform>/<id>` (`<id>#<example>` in an issue exported with Examples). Do not rename them; the matrix, the evidence folders, and the Jenkins `SCENARIOS` parameter depend on them.
- Branches: work on `efp/<KEY>` (or `efp/<KEY>-<n>`) and open a pull request into the base branch; never push to the base branch.

## The helpers (`mobiletest`)

- Finding: `find(driver, locator, fallbacks=, index=, nearby_text=, within_text=, optional=, retry=, timeout=)`, `by_text`, `by_name`, `by_role`, `optional()` (a block whose missing element is not a failure).
- Actions: `tap`, `type_text`, `clear`, `long_press`, `double_tap`, `tap_point` (`x_percent=`, `y_percent=`, `hold_ms=`), `swipe` (`start=`, `end=`, `duration_ms=`, `hold_ms=`, `end_hold_ms=`, or a direction), `scroll_to` and `scroll_to_end` (at most 8 swipes unless told otherwise, like the device), `back`, `hide_keyboard`, `press_enter`, `press_keycode`, `launch_app`, `close_app`, `reset_app`, `activate_app`, `terminate_app`, `open_deep_link`, `accept_permission`, `deny_permission`.
- Checks, each with `timeout=`: `visible`, `wait_visible`, `wait_gone`, `wait_enabled`, `wait_text`, `wait_stable`, `assert_visible`, `assert_not_visible`, `assert_enabled`, `assert_selected`, `assert_text`, `assert_count`.
- Evidence: `screenshot(driver, label)` attaches a PNG to the step; a failed step records `screenshot.png` and `source.xml` by itself; a `find` answered only by a fallback is recorded as drift.
- Accounts: `secret`, `user_value`, `profile`.

## Prove a change before pushing

1. `python -m pytest -q tests`: the helpers, the runner, and the report, against the stand-in driver; no device.
2. `python -m mobiletest.run --check`: every step of every feature has a definition (behave `--dry-run` in each scenario folder).
3. `python -m mobiletest.run --platform <platform> --tags @<KEY> --list`: the rows you expect, with their ids.
4. A real run: the Jenkins job with `BRANCH_NAME=<your branch>` and `SCENARIOS=<the scenarios you touched>`; read `runs/build-<n>/cases/<row>/evidence.json` and the Cucumber report.

## Reading a failure

`cases/<row>/evidence.json` holds the failed step and its message (`error.code`: `assertion_failed`, `element_not_found`, `step_error` with the `traceback`, or `session_start_failed`); `screenshot.png` and `source.xml` beside it are the screen at the failure, and `video.mp4` the session (`video_error` says why there is none). `warnings` lists what looked odd on the way, such as the driver answering a find with something other than a list of elements. Drift (a passed row whose `fallback_hits` is not empty) means the primary locator is stale: fix it now, before it fails.
