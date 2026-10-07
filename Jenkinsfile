// Mobile scenario runs for EFP assistants.
//
// The tests are a plain Python project: behave features under
// features/<platform>/<KEY>/, step definitions and segment modules the
// assistant generated, and the mobiletest helpers. This job installs the
// requirements, runs the selected scenario rows in parallel on BrowserStack
// (one session per Examples row), and publishes the Cucumber report, the JUnit
// results, and the evidence. Nothing here needs EFP; the same command runs on
// a laptop.
//
// The job is a "Pipeline script from SCM" job pointing at this repository. A
// build names the branch to run (the assistant pushes efp/<KEY> branches) and
// what to run. Results go to runs/build-<build number>/. While the run goes,
// the matrix is printed on one line prefixed EFP-MATRIX whenever it changes,
// so the assistant can follow it from the console log.
//
// What a team sets once, never as build parameters: as Folder Properties on
// the folder holding the job (the Folder Properties plugin; a sub-folder's
// override its parent's, and a folder property wins over an environment
// variable of the same name), or as environment variables on the agent or
// under Manage Jenkins > System > Global properties:
//   MOBILE_AGENT_LABEL                 the agent label (default linux); the agent needs egress to BrowserStack
//   MOBILE_PYTHON                      the Python 3.9+ interpreter on the agent (default python3)
//   MOBILE_PIP_INDEX_URL               a PyPI index for the requirements, such as an internal Nexus proxy
//   MOBILE_LOCAL_BINARY_URL            where the BrowserStackLocal binary is downloaded from (default
//                                      browserstack.com; a copy in your artifact repository works); an
//                                      absolute path uses that program on the agent, and the word
//                                      installed the BrowserStackLocal on the agent's PATH
//   MOBILE_LOCAL_PROXY                 http://host:port (or http://user:password@host:port, percent-encoded)
//                                      the tunnel goes out through (default: the agent's HTTPS_PROXY)
//   MOBILE_BROWSERSTACK_CREDENTIALS_ID the Username with password credential holding the BrowserStack
//                                      username and access key (default browserstack)
//
// A parameter or setting left empty is absent from the environment of a
// process the job starts (Jenkins drops empty variables when it launches
// one), so every optional value is read with a default below, and an empty
// value is never a signal.
//
// The test accounts come from a Secret file credential named by the build
// (TEST_PROFILE_CREDENTIALS_ID, default mobile-test-users): a JSON map of
// profiles, "default" and any others, each with username, password, and
// whatever else the app asks for. A build signs in with the "default" profile.
// Every build starts a BrowserStack Local tunnel: the apps live on the
// private network.

pipeline {
  // The agent is chosen in the stage below, once the folder's properties are
  // in the environment: a pipeline-level agent would read the label first.
  agent none

  options {
    withFolderProperties()
    skipDefaultCheckout(true)
    timeout(time: 4, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '60', artifactNumToKeepStr: '30'))
  }

  parameters {
    string(name: 'BRANCH_NAME', defaultValue: '', description: 'Branch, tag, or commit of this repository to run (the assistant pushes efp/<KEY>); empty runs the branch the job is configured with')
    choice(name: 'PLATFORMS', choices: ['all', 'android', 'ios'], description: 'The platforms to run')
    string(name: 'TAGS', defaultValue: '', description: 'Space-separated behave tag expressions, all of which a scenario must match, for example @FX-12 or @FX-12 @positive; empty runs every scenario')
    string(name: 'SCENARIOS', defaultValue: '', description: 'Optional: only these scenarios, space-separated: <scenario id> runs every Examples row of the scenario, <scenario id>#<example> one row, each optionally prefixed <platform>/ (a dry run or a rerun); empty runs everything the tags select')
    string(name: 'ANDROID_APP_ID', defaultValue: '', description: 'Optional: the Android build on BrowserStack to test, already uploaded (bs://... or its custom id); empty uses the app named in config/<KEY>.android.yaml')
    string(name: 'IOS_APP_ID', defaultValue: '', description: 'Optional: the iOS build on BrowserStack to test, already uploaded (bs://... or its custom id); empty uses the app named in config/<KEY>.ios.yaml')
    string(name: 'TEST_PROFILE_CREDENTIALS_ID', defaultValue: 'mobile-test-users', description: 'The Secret file credential holding the test users file: a JSON map of profiles ("default" and any others), each with username, password, and whatever else the app asks for')
    string(name: 'PARALLEL', defaultValue: '4', description: 'Parallel BrowserStack sessions; the run waits for free ones')
    booleanParam(name: 'COLLECT_VIDEO', defaultValue: true, description: 'Download each session video into the evidence')
  }

  stages {
    stage('Mobile scenarios') {
      // Everything runs on one agent, chosen here: the folder's properties
      // (MOBILE_AGENT_LABEL among them) are in the environment by now.
      agent { label "${env.MOBILE_AGENT_LABEL ?: 'linux'}" }
      stages {
        stage('Check parameters') {
          steps {
            script {
              env.RUN_LABEL = "build-${env.BUILD_NUMBER}"
              if (!(params.PARALLEL ==~ /[1-9][0-9]?/)) { error 'PARALLEL must be a number from 1 to 99' }
              if (!params.TEST_PROFILE_CREDENTIALS_ID?.trim()) { error 'TEST_PROFILE_CREDENTIALS_ID must name the Secret file credential holding the test users file' }
              env.PLATFORM_LIST = params.PLATFORMS == 'all' ? 'android ios' : params.PLATFORMS
              currentBuild.description = "${params.BRANCH_NAME ?: 'job branch'} ${params.PLATFORMS} ${params.TAGS} ${params.SCENARIOS}".trim()
            }
          }
        }

        stage('Check out') {
          steps {
            script {
              // The job's own SCM settings (this repository and its credentials)
              // are reused; BRANCH_NAME picks the branch the assistant pushed.
              def ref = params.BRANCH_NAME?.trim()
              if (ref) {
                checkout([$class: 'GitSCM',
                  branches: [[name: ref]],
                  userRemoteConfigs: scm.userRemoteConfigs,
                  extensions: [[$class: 'CleanBeforeCheckout']]])
              } else {
                checkout scm
              }
            }
          }
        }

        stage('Python environment') {
          steps {
            sh '''#!/bin/bash
              set -euo pipefail
              python="${MOBILE_PYTHON:-python3}"
              "$python" -m venv .venv
              index=()
              if [ -n "${MOBILE_PIP_INDEX_URL:-}" ]; then index=(--index-url "${MOBILE_PIP_INDEX_URL:-}"); fi
              .venv/bin/python -m pip install --quiet "${index[@]}" -r requirements.txt
              .venv/bin/python -m behave --version
            '''
          }
        }

        stage('BrowserStack Local') {
          steps {
            script {
              // One tunnel per build, named after the run; the sessions attach
              // to it by that identifier (every config, unless it says
              // network: public). The apps live on the private network.
              withCredentials([usernamePassword(credentialsId: env.MOBILE_BROWSERSTACK_CREDENTIALS_ID ?: 'browserstack', usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY')]) {
                sh '''#!/bin/bash
                  set -euo pipefail
                  mkdir -p .efp-bin runs
                  rm -f .efp-bin/BrowserStackLocal
                  # A URL is downloaded; an absolute path is a program on the agent;
                  # "installed" is the BrowserStackLocal on the agent's PATH. (An
                  # empty value is not an option: Jenkins drops empty variables.)
                  from="${MOBILE_LOCAL_BINARY_URL:-https://www.browserstack.com/browserstack-local/BrowserStackLocal-linux-x64.zip}"
                  case "$from" in
                    http://*|https://*)
                      curl -fsSL -o .efp-bin/BrowserStackLocal.zip "$from"
                      (cd .efp-bin && unzip -o -q BrowserStackLocal.zip && chmod +x BrowserStackLocal)
                      ;;
                    installed)
                      command -v BrowserStackLocal > /dev/null || { echo "MOBILE_LOCAL_BINARY_URL says installed, but BrowserStackLocal is not on the agent's PATH" >&2; exit 1; }
                      ln -s "$(command -v BrowserStackLocal)" .efp-bin/BrowserStackLocal
                      ;;
                    /*)
                      [ -x "$from" ] || { echo "MOBILE_LOCAL_BINARY_URL names $from, which is not an executable on this agent" >&2; exit 1; }
                      ln -s "$from" .efp-bin/BrowserStackLocal
                      ;;
                    *)
                      echo "MOBILE_LOCAL_BINARY_URL must be a URL to download, an absolute path on the agent, or installed: $from" >&2
                      exit 1
                      ;;
                  esac
                  bin=.efp-bin/BrowserStackLocal
                  args=(--key "${BROWSERSTACK_ACCESS_KEY}" --local-identifier "${RUN_LABEL}" --force-local --daemon start)
                  # The proxy may carry a login (http://user:password@host:port,
                  # percent-encoded); BrowserStack Local takes it as its own flags.
                  proxy="${MOBILE_LOCAL_PROXY:-${HTTPS_PROXY:-${https_proxy:-}}}"
                  if [ -n "$proxy" ]; then
                    rest="${proxy#*://}"; rest="${rest%%/*}"; hostport="${rest##*@}"
                    args+=(--proxy-host "${hostport%%:*}" --proxy-port "${hostport##*:}" --force-proxy)
                    if [ "$rest" != "$hostport" ]; then
                      login="${rest%@*}"
                      unquote='import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))'
                      args+=(--proxy-user "$(.venv/bin/python -c "$unquote" "${login%%:*}")" --proxy-pass "$(.venv/bin/python -c "$unquote" "${login#*:}")")
                    fi
                  fi
                  log="runs/${RUN_LABEL}.local.log"
                  "$bin" "${args[@]}" > "$log" 2>&1 || true
                  sed "s/${BROWSERSTACK_ACCESS_KEY}/***/g" "$log"
                  # The binary's exit code says little; its JSON answer says whether
                  # the tunnel is up, and a session finds a connected tunnel only.
                  parse='import json, sys; d = json.loads(next(l for l in open(sys.argv[1]) if l.lstrip().startswith("{"))); m = d.get("message"); m = m.get("message", "") if isinstance(m, dict) else (m or ""); print(d.get("state", "unknown"), d.get("pid", 0), m)'
                  answer="$(.venv/bin/python -c "$parse" "$log" 2>/dev/null || echo "unparsable 0 no JSON answer from the binary")"
                  state="${answer%% *}"; rest="${answer#* }"; pid="${rest%% *}"
                  if [ "$state" != "connected" ]; then
                    echo "BrowserStack Local did not connect: ${answer}. Check MOBILE_LOCAL_PROXY (or the agent's HTTPS_PROXY, with its login when the proxy asks for one) and that this agent reaches *.browserstack.com." >&2
                    exit 1
                  fi
                  echo "$pid" > .efp-bin/local.pid
                  # BrowserStack needs a few seconds before sessions find a new tunnel.
                  sleep 5
                  echo "BrowserStack Local is connected as ${RUN_LABEL} (pid ${pid}); the sessions attach to it by that identifier."
                '''
              }
            }
          }
        }

        stage('Run scenarios') {
          steps {
            script {
              // The BrowserStack account and the test users file come from
              // Jenkins credentials; the file is handed to the tests as a path
              // and removed with the build.
              def bindings = [
                usernamePassword(credentialsId: env.MOBILE_BROWSERSTACK_CREDENTIALS_ID ?: 'browserstack', usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY'),
                file(credentialsId: params.TEST_PROFILE_CREDENTIALS_ID.trim(), variable: 'MOBILE_TEST_USERS_FILE'),
              ]
              def rc = 0
              withCredentials(bindings) {
                rc = sh(returnStatus: true, script: '''#!/bin/bash
                  set -uo pipefail
                  rm -rf "runs/${RUN_LABEL}"
                  pid="$(cat .efp-bin/local.pid 2>/dev/null || echo 0)"
                  if [ "$pid" -gt 0 ] 2>/dev/null && ! kill -0 "$pid" 2>/dev/null; then
                    echo "BrowserStack Local (pid ${pid}) is no longer running; the sessions could not reach the private network" >&2
                    exit 3
                  fi
                  export BROWSERSTACK_LOCAL_IDENTIFIER="${RUN_LABEL}"
                  args=(-m mobiletest.run --label "${RUN_LABEL}" --out "runs/${RUN_LABEL}" --parallel "${PARALLEL}" --wait-capacity)
                  for platform in ${PLATFORM_LIST}; do args+=(--platform "${platform}"); done
                  for tag in ${TAGS:-}; do args+=(--tags "${tag}"); done
                  for row in ${SCENARIOS:-}; do args+=(--row "${row}"); done
                  if [ "${COLLECT_VIDEO}" = "true" ]; then args+=(--collect-video); fi
                  .venv/bin/python "${args[@]}"
                ''')
              }
              if (rc == 2) {
                error 'No scenario row matched PLATFORMS, TAGS, and SCENARIOS'
              }
              if (rc == 3) {
                error 'BrowserStack Local stopped before the scenarios ran (see the log above); nothing was run'
              }
              if (rc != 0) {
                // Failed scenarios make the build unstable; the evidence and the
                // report are published either way.
                currentBuild.result = 'UNSTABLE'
              }
            }
          }
        }
      }

      post {
        always {
          sh '''#!/bin/bash
            set -uo pipefail
            label="${RUN_LABEL:-build-${BUILD_NUMBER}}"
            out="runs/${label}"
            if [ -d "$out" ]; then
              tar czf "$out/evidence.tar.gz" --exclude='*.mp4' --exclude='evidence.tar.gz' --exclude='behave' -C "$out" .
            fi
            bin=.efp-bin/BrowserStackLocal; [ -x "$bin" ] || bin="$(command -v BrowserStackLocal || true)"
            [ -n "$bin" ] && "$bin" --local-identifier "${label}" --daemon stop > /dev/null 2>&1 || true
          '''
          script {
            try {
              cucumber buildStatus: 'UNSTABLE',
                fileIncludePattern: 'cucumber.json',
                jsonReportDirectory: "runs/${env.RUN_LABEL}/cucumber",
                reportTitle: 'Mobile scenarios',
                trendsLimit: 20
            } catch (Exception e) {
              echo "Cucumber report not published (is the Cucumber Reports plugin installed?): ${e}"
            }
          }
          junit allowEmptyResults: true, testResults: "runs/${env.RUN_LABEL}/junit/**/*.xml"
          archiveArtifacts allowEmptyArchive: true, artifacts: "runs/${env.RUN_LABEL}/matrix.json, runs/${env.RUN_LABEL}/report.json, runs/${env.RUN_LABEL}/evidence.tar.gz, runs/${env.RUN_LABEL}/cucumber/cucumber.json, runs/${env.RUN_LABEL}/cases/**/video.mp4"
        }
      }
    }
  }
}
