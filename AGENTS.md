# Working in this repository as an agent

For the EFP assistant working in its clone (`repos/<name>` in its workspace) and for any coding agent a person runs here. The README says what the project is and how the Jenkins job runs it; this file says what to change, what to leave alone, and how to prove a change.

## What this is

A plain Python test project: behave features, step definitions, and segment modules on the Appium Python client, run on BrowserStack real devices by the Jenkins job in `Jenkinsfile`. `mobile-auto test export` writes it from an assistant's workspace (the scenario plan, the recorded segments, the suites); after the export, the Python here is the source.

## Who edits what

| Path | Edit it here? |
| --- | --- |
| `features/<platform>/<KEY>/<KEY>.feature` | No. It is the Gherkin the requirement owner approved; a change goes through the scenario plan, its review card, and a new export. |
| `features/<platform>/<KEY>/steps/<KEY>_steps.py` | Yes: a scenario's own actions and checks. |
| `segments/<platform>/<segment>.py` | Yes: a recorded flow shared by every scenario that calls it. Fix a shared step once, here. |
| `config/<KEY>.<platform>.yaml` | Rarely: `device`, `os_version`, `appium_version`, `data`, `network` (`public` only for an app that needs no tunnel; every other config goes through BrowserStack Local). `app`, `secrets`, and `scenarios` come from the export. |
| `mobiletest/` | Yes, with a test in `tests/`; every suite shares it. |
| `Jenkinsfile`, `README.md`, this file | Yes. |
| `runs/` | Never committed: results. |

## Rules

- Preserve scenario intent: adapt how the app is driven, never what the scenario checks. A product defect stays a failing test with its evidence; do not bend the test to pass.
- Keep the `# recorded:` comment above a line you change: it says what the recording did.
- Keep the first line of a generated file (`# mobile-auto export: ... content_sha256=...`). Its hashes tell the exporter the file was edited by hand, so the next export keeps your change instead of overwriting it.
- Locators, in this order: accessibility id, resource id (Android) or name (iOS), then text; give `find` a `fallbacks=` route when the first one is fragile. Coordinates (`tap_point`) only when nothing identifies the element. Never `sleep`: use `wait_visible`, `wait_text`, `wait_gone`, `visible(..., timeout=)`, or `wait_stable`. A screen that only sometimes appears is guarded with `if visible(driver, ..., timeout=3):`.
- Scrolling: `scroll_to_end(driver)` is what the export writes for a segment's `scroll-to` step with `edge: bottom` (the compiler folds three or more recorded swipes into it, and the replay runs it on the device); `scroll_to(driver, locator)` for a `scroll-to` with a target. A fixed count of swipes is never right: another device or build needs a different number. Fix it in the segment and export again while the recording flow is available, so the segment, its replay, and this file agree; fix it here only when it is not.
- Take a new target from the page source at the failure (`cases/<row>/source.xml` in the run's evidence), not from memory.
- Accounts: the test users file is a JSON map of profiles (`default` and any others, each with `username`, `password`, and whatever else the app asks for) kept in Jenkins as a Secret file credential. A build names that credential in its `TEST_PROFILE_CREDENTIALS_ID` parameter (`mobile-test-users` unless the team keeps several files, one per environment), the job hands the file to the tests as `MOBILE_TEST_USERS_FILE`, and the tests sign in with the `default` profile. On a laptop, export `MOBILE_TEST_USERS_FILE` yourself, and `MOBILE_TEST_USER` to use another profile. `secret("MOBILE_SECRET_PASSWORD")` (what a recorded password field turns into) reads the profile's `password`, the name without `MOBILE_SECRET_` in lower case; `user_value("username")` any other field, `user_value("username", "vip")` another profile's; `profile()` the whole map. Never write a value into a file, a log, a commit message, or a test name; never ask a person for one in chat.
- Ids: `config/<KEY>.<platform>.yaml` maps scenario titles to ids; a row is `<id>#<example>`. Do not rename them; the matrix, the evidence folders, and the Jenkins `SCENARIOS` parameter depend on them.
- Branches: work on `efp/<KEY>` (or `efp/<KEY>-<n>`) and open a pull request into the base branch; never push to the base branch.

## The helpers (`mobiletest`)

- Finding: `find(driver, locator, fallbacks=, index=, nearby_text=, within_text=, optional=, retry=, timeout=)`, `by_text`, `by_name`, `by_role`, `optional()` (a block whose missing element is not a failure).
- Actions: `tap`, `type_text`, `clear`, `long_press`, `double_tap`, `tap_point`, `swipe`, `scroll_to`, `scroll_to_end`, `back`, `hide_keyboard`, `press_enter`, `press_keycode`, `launch_app`, `close_app`, `reset_app`, `activate_app`, `terminate_app`, `open_deep_link`, `accept_permission`, `deny_permission`.
- Checks, each with `timeout=`: `visible`, `wait_visible`, `wait_gone`, `wait_enabled`, `wait_text`, `wait_stable`, `assert_visible`, `assert_not_visible`, `assert_enabled`, `assert_selected`, `assert_text`, `assert_count`.
- Evidence: `screenshot(driver, label)` attaches a PNG to the step; a failed step records `screenshot.png` and `source.xml` by itself; a `find` answered only by a fallback is recorded as drift.
- Accounts: `secret`, `user_value`, `profile`.

## Prove a change before pushing

1. `python -m pytest -q tests`: the helpers, the runner, and the report, against the stand-in driver; no device.
2. `python -m behave features/<platform>/<KEY> --dry-run --no-summary`: every step of the feature has a definition.
3. `python -m mobiletest.run --platform <platform> --tags @<KEY> --list`: the rows you expect, with their ids.
4. A real run: the Jenkins job with `BRANCH_NAME=<your branch>` and `SCENARIOS=<the rows you touched>`; read `runs/build-<n>/cases/<row>/evidence.json` and the Cucumber report. A changed segment changes every scenario that calls it: rerun at least one row of each.

## Reading a failure

`cases/<row>/evidence.json` holds the failed step and its message (`error.code`: `assertion_failed`, `element_not_found`, `step_error` with the `traceback`, or `session_start_failed`); `screenshot.png` and `source.xml` beside it are the screen at the failure, and `video.mp4` the session (`video_error` says why there is none). `warnings` lists what looked odd on the way, such as the driver answering a find with something other than a list of elements. Drift (a passed row whose `fallback_hits` is not empty) means the primary locator is stale: fix it now, before it fails.
