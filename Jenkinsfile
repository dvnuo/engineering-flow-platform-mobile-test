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
// the rows to run. Results go to runs/<RUN_LABEL>/. While the run goes, the
// matrix is printed on one line prefixed EFP-MATRIX whenever it changes, so
// the assistant can follow it from the console log.
//
// What a team sets once, as environment variables on the agent or under
// Manage Jenkins > System > Global properties (none of these is a build
// parameter):
//   MOBILE_AGENT_LABEL       the agent label (default linux); the agent needs egress to BrowserStack
//   MOBILE_PYTHON            the Python 3.9+ interpreter on the agent (default python3)
//   MOBILE_PIP_INDEX_URL     a PyPI index for the requirements, such as an internal Nexus proxy
//   MOBILE_LOCAL_BINARY_URL  where the BrowserStackLocal binary is downloaded from (default
//                            browserstack.com; a copy in your artifact repository works; set it
//                            empty to use a BrowserStackLocal already on the agent's PATH)
//   MOBILE_LOCAL_PROXY       http://host:port the tunnel goes out through (default: the agent's HTTPS_PROXY)

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
    string(name: 'ROWS', defaultValue: '', description: 'Optional: only these scenarios or rows, space-separated: <scenario id> runs all its Examples rows, <scenario id>#<example> one row, each optionally prefixed <platform>/ (a dry run or a rerun)')
    string(name: 'RUN_LABEL', defaultValue: '', description: 'Run id: results go to runs/<RUN_LABEL>/ and the BrowserStack build takes the name; the assistant passes its Portal task id; empty uses build-<build number>')
    string(name: 'PARALLEL', defaultValue: '4', description: 'Parallel BrowserStack sessions; the run waits for free ones')
    booleanParam(name: 'COLLECT_VIDEO', defaultValue: true, description: 'Download each session video into the evidence')
    string(name: 'APP_FILE_URL', defaultValue: '', description: 'Optional: a build to upload to BrowserStack first (.apk, .aab, .ipa), fetched by this agent; the config files then run the newest upload of its custom id')
    string(name: 'APP_CUSTOM_ID', defaultValue: '', description: 'The custom id that upload is stored under (every build of an app shares one, for example fxapp-uat-android, which is what config/<KEY>.<platform>.yaml names)')
    string(name: 'APP_CREDENTIALS_ID', defaultValue: '', description: 'Optional: username/password credentials for fetching APP_FILE_URL (Nexus, Jenkins behind a login)')
    string(name: 'BROWSERSTACK_CREDENTIALS_ID', defaultValue: 'browserstack', description: 'Username/password credentials: BrowserStack username and access key')
    string(name: 'TEST_SECRETS', defaultValue: '', description: 'Comma-separated NAME=credentialsId pairs: secret-text credentials exposed under the names the tests read with secret(), for example MOBILE_SECRET_PASSWORD=fx-uat-password')
    booleanParam(name: 'LOCAL', defaultValue: true, description: 'Start a BrowserStack Local tunnel on this agent for the run, for apps that talk to servers on the private network (the configs whose network is private use it)')
  }

  stages {
    stage('Check parameters') {
      steps {
        script {
          env.RUN_LABEL = params.RUN_LABEL?.trim() ?: "build-${env.BUILD_NUMBER}"
          if (!(env.RUN_LABEL ==~ /[A-Za-z0-9][A-Za-z0-9._-]{0,99}/)) { error 'RUN_LABEL must be letters, digits, dot, dash, or underscore' }
          if (!(params.PARALLEL ==~ /[1-9][0-9]?/)) { error 'PARALLEL must be a number from 1 to 99' }
          env.PLATFORM_LIST = params.PLATFORMS == 'all' ? 'android ios' : params.PLATFORMS
          currentBuild.description = "${env.RUN_LABEL}: ${params.BRANCH_NAME ?: 'job branch'} ${params.PLATFORMS} ${params.TAGS} ${params.ROWS}".trim()
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

    stage('Upload build') {
      when { expression { return params.APP_FILE_URL?.trim() } }
      steps {
        script {
          def upload = '''#!/bin/bash
            set -euo pipefail
            name="$(basename "${APP_FILE_URL%%\\?*}")"
            case "$name" in *.apk|*.aab|*.ipa) ;; *) echo "APP_FILE_URL must end in .apk, .aab, or .ipa"; exit 2 ;; esac
            if [ -n "${APP_USER:-}" ]; then
              curl -fsSL -u "${APP_USER}:${APP_PASS}" -o "$name" "${APP_FILE_URL}"
            else
              curl -fsSL -o "$name" "${APP_FILE_URL}"
            fi
            form=(-F "file=@${name}")
            if [ -n "${APP_CUSTOM_ID}" ]; then form+=(-F "custom_id=${APP_CUSTOM_ID}"); fi
            curl -fsS -u "${BROWSERSTACK_USERNAME}:${BROWSERSTACK_ACCESS_KEY}" -X POST "${BROWSERSTACK_API_URL:-https://api-cloud.browserstack.com}/app-automate/upload" "${form[@]}"
            echo
            rm -f "$name"
          '''
          def account = [usernamePassword(credentialsId: params.BROWSERSTACK_CREDENTIALS_ID, usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY')]
          if (params.APP_CREDENTIALS_ID?.trim()) {
            account << usernamePassword(credentialsId: params.APP_CREDENTIALS_ID, usernameVariable: 'APP_USER', passwordVariable: 'APP_PASS')
          }
          withCredentials(account) { sh upload }
        }
      }
    }

    stage('BrowserStack Local') {
      when { expression { return params.LOCAL } }
      steps {
        script {
          // One tunnel per build, named after the run; the sessions of the
          // configs on a private network attach to it by that identifier.
          withCredentials([usernamePassword(credentialsId: params.BROWSERSTACK_CREDENTIALS_ID, usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY')]) {
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
          def bindings = [usernamePassword(credentialsId: params.BROWSERSTACK_CREDENTIALS_ID, usernameVariable: 'BROWSERSTACK_USERNAME', passwordVariable: 'BROWSERSTACK_ACCESS_KEY')]
          for (String pair : (params.TEST_SECRETS ?: '').split(',')) {
            def entry = pair.trim()
            if (entry) {
              def parts = entry.split('=', 2)
              if (parts.size() != 2 || !(parts[0].trim() ==~ /[A-Z][A-Z0-9_]*/) || !parts[1].trim()) {
                error "TEST_SECRETS entries look like MOBILE_SECRET_PASSWORD=credentials-id: ${entry}"
              }
              bindings << string(credentialsId: parts[1].trim(), variable: parts[0].trim())
            }
          }
          def rc = 0
          withCredentials(bindings) {
            rc = sh(returnStatus: true, script: '''#!/bin/bash
              set -uo pipefail
              rm -rf "runs/${RUN_LABEL}"
              if [ "${LOCAL}" = "true" ]; then export BROWSERSTACK_LOCAL_IDENTIFIER="${RUN_LABEL}"; fi
              args=(-m mobiletest.run --label "${RUN_LABEL}" --out "runs/${RUN_LABEL}" --parallel "${PARALLEL}" --wait-capacity)
              for platform in ${PLATFORM_LIST}; do args+=(--platform "${platform}"); done
              for tag in ${TAGS}; do args+=(--tags "${tag}"); done
              for row in ${ROWS}; do args+=(--row "${row}"); done
              if [ "${COLLECT_VIDEO}" = "true" ]; then args+=(--collect-video); fi
              .venv/bin/python "${args[@]}"
            ''')
          }
          if (rc == 2) {
            error 'No scenario row matched PLATFORMS, TAGS, and ROWS'
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
        if [ "${LOCAL}" = "true" ]; then
          bin=.efp-bin/BrowserStackLocal; [ -x "$bin" ] || bin="$(command -v BrowserStackLocal || true)"
          [ -n "$bin" ] && "$bin" --local-identifier "${RUN_LABEL}" --daemon stop > /dev/null 2>&1 || true
        fi
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
