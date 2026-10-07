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
// What a team sets once, as environment variables on the agent or under
// Manage Jenkins > System > Global properties (none of these is a build
// parameter):
//   MOBILE_AGENT_LABEL                 the agent label (default linux); the agent needs egress to BrowserStack
//   MOBILE_PYTHON                      the Python 3.9+ interpreter on the agent (default python3)
//   MOBILE_PIP_INDEX_URL               a PyPI index for the requirements, such as an internal Nexus proxy
//   MOBILE_LOCAL_BINARY_URL            where the BrowserStackLocal binary is downloaded from (default
//                                      browserstack.com; a copy in your artifact repository works; set it
//                                      empty to use a BrowserStackLocal already on the agent's PATH)
//   MOBILE_LOCAL_PROXY                 http://host:port the tunnel goes out through (default: the agent's HTTPS_PROXY)
//   MOBILE_BROWSERSTACK_CREDENTIALS_ID the Username with password credential holding the BrowserStack
//                                      username and access key (default browserstack)
//
// The test accounts come from a Secret file credential named by the build
// (TEST_PROFILE_CREDENTIALS_ID, default mobile-test-users): a JSON map of
// profiles, "default" and any others, each with username, password, and
// whatever else the app asks for. A build signs in with the "default" profile.
// Every build starts a BrowserStack Local tunnel: the apps live on the
// private network.

pipeline {
  agent { label "${env.MOBILE_AGENT_LABEL ?: 'linux'}" }

  options {
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
          if [ -n "${MOBILE_PIP_INDEX_URL:-}" ]; then index=(--index-url "${MOBILE_PIP_INDEX_URL}"); fi
          .venv/bin/python -m pip install --quiet "${index[@]}" -r requirements.txt
          .venv/bin/python -m behave --version
        '''
      }
    }

    stage('BrowserStack Local') {
      steps {
        script {
          // One tunnel per build, named after the run; the sessions of the
          // configs on a private network attach to it by that identifier.
          // The apps live on the private network, so every build has one.
          withCredentials([usernamePassword(credentialsId: env.MOBILE_BROWSERSTACK_CREDENTIALS_ID ?: 'browserstack', usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY')]) {
            sh '''#!/bin/bash
              set -euo pipefail
              mkdir -p .efp-bin runs
              url="${MOBILE_LOCAL_BINARY_URL-https://www.browserstack.com/browserstack-local/BrowserStackLocal-linux-x64.zip}"
              if [ -n "$url" ]; then
                curl -fsSL -o .efp-bin/BrowserStackLocal.zip "$url"
                (cd .efp-bin && unzip -o -q BrowserStackLocal.zip && chmod +x BrowserStackLocal)
                bin=.efp-bin/BrowserStackLocal
              else
                bin="$(command -v BrowserStackLocal)"
              fi
              args=(--key "${BROWSERSTACK_ACCESS_KEY}" --local-identifier "${RUN_LABEL}" --force-local --daemon start)
              proxy="${MOBILE_LOCAL_PROXY:-${HTTPS_PROXY:-${https_proxy:-}}}"
              if [ -n "$proxy" ]; then
                hostport="${proxy#*://}"; hostport="${hostport%%/*}"; hostport="${hostport##*@}"
                args+=(--proxy-host "${hostport%%:*}" --proxy-port "${hostport##*:}" --force-proxy)
              fi
              "$bin" "${args[@]}" > "runs/${RUN_LABEL}.local.log" 2>&1 || { sed "s/${BROWSERSTACK_ACCESS_KEY}/***/g" "runs/${RUN_LABEL}.local.log"; exit 1; }
              sed "s/${BROWSERSTACK_ACCESS_KEY}/***/g" "runs/${RUN_LABEL}.local.log"
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
              export BROWSERSTACK_LOCAL_IDENTIFIER="${RUN_LABEL}"
              args=(-m mobiletest.run --label "${RUN_LABEL}" --out "runs/${RUN_LABEL}" --parallel "${PARALLEL}" --wait-capacity)
              for platform in ${PLATFORM_LIST}; do args+=(--platform "${platform}"); done
              for tag in ${TAGS}; do args+=(--tags "${tag}"); done
              for row in ${SCENARIOS}; do args+=(--row "${row}"); done
              if [ "${COLLECT_VIDEO}" = "true" ]; then args+=(--collect-video); fi
              .venv/bin/python "${args[@]}"
            ''')
          }
          if (rc == 2) {
            error 'No scenario row matched PLATFORMS, TAGS, and SCENARIOS'
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
        out="runs/${RUN_LABEL}"
        if [ -d "$out" ]; then
          tar czf "$out/evidence.tar.gz" --exclude='*.mp4' --exclude='evidence.tar.gz' --exclude='behave' -C "$out" .
        fi
        bin=.efp-bin/BrowserStackLocal; [ -x "$bin" ] || bin="$(command -v BrowserStackLocal || true)"
        [ -n "$bin" ] && "$bin" --local-identifier "${RUN_LABEL}" --daemon stop > /dev/null 2>&1 || true
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
