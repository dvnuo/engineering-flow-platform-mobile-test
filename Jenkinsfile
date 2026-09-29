// Mobile scenario runs for EFP assistants.
//
// The assistant commits compiled scripts (mobile/scripts/<KEY>/<platform>/*.yaml,
// one per scenario row) to a branch of this repository and starts this job;
// the job runs them on BrowserStack with mobile-auto and archives the
// evidence. The assistant's pod never talks to BrowserStack; this agent does.
// See README.md for the job setup.
//
// The job is a "Pipeline script from SCM" job pointing at this repository, so
// the scripts are checked out at the job root (mobile/ sits there) and the
// results go to mobile/runs/<RUN_LABEL>/: every relative path in the matrix
// and the evidence resolves the same way once the assistant unpacks them into
// its workspace.

pipeline {
  agent { label "${params.AGENT_LABEL ?: 'linux'}" }

  options {
    skipDefaultCheckout(true)
    timeout(time: 4, unit: 'HOURS')
    buildDiscarder(logRotator(numToKeepStr: '60', artifactNumToKeepStr: '30'))
  }

  parameters {
    string(name: 'SCRIPTS_REF', defaultValue: '', description: 'Branch, tag, or commit of this repository to run; empty runs the branch the job is configured with')
    string(name: 'SCRIPTS', defaultValue: '', description: 'Space-separated script directories or files, relative to the repository root, for example mobile/scripts/FX-12/android mobile/scripts/FX-12/ios')
    string(name: 'RUN_LABEL', defaultValue: '', description: 'Run id: the Portal task id, or chat-<time>. Results go to mobile/runs/<RUN_LABEL>/')
    string(name: 'PARALLEL', defaultValue: '4', description: 'Parallel BrowserStack sessions; the run waits for free ones')
    string(name: 'CASE', defaultValue: '', description: 'Optional: run only this scenario (case name)')
    string(name: 'MATRIX', defaultValue: '', description: 'Optional: run only this Examples row')
    booleanParam(name: 'COLLECT_VIDEO', defaultValue: true, description: 'Download each session video into the evidence')
    string(name: 'APP_FILE_URL', defaultValue: '', description: 'Optional: build to upload to BrowserStack first (.apk, .aab, .ipa), fetched by this agent')
    string(name: 'APP_CUSTOM_ID', defaultValue: '', description: 'Custom id for that build; scripts that name it get the newest upload')
    string(name: 'APP_CREDENTIALS_ID', defaultValue: '', description: 'Optional: username/password credentials for APP_FILE_URL (Nexus, Jenkins)')
    string(name: 'MOBILE_AUTO_URL', defaultValue: '', description: 'Where to download the linux mobile-auto binary; empty uses mobile-auto on PATH')
    string(name: 'BROWSERSTACK_CREDENTIALS_ID', defaultValue: 'browserstack', description: 'Username/password credentials: BrowserStack username and access key')
    string(name: 'TEST_SECRETS', defaultValue: '', description: 'Comma-separated NAME=credentialsId pairs: secret-text credentials exposed under the text_env names the scripts use, for example MOBILE_SECRET_PASSWORD=fx-uat-password')
    string(name: 'AGENT_LABEL', defaultValue: 'linux', description: 'Agent label; the agent needs egress to BrowserStack')
  }

  environment {
    MOBILE_AUTO_STATE_DIR = "${WORKSPACE}/.mobile-auto/state"
    MOBILE_AUTO_ARTIFACTS_DIR = "${WORKSPACE}/.mobile-auto/artifacts"
  }

  stages {
    stage('Check parameters') {
      steps {
        script {
          if (!params.SCRIPTS?.trim()) { error 'SCRIPTS is required' }
          if (!(params.RUN_LABEL ==~ /[A-Za-z0-9][A-Za-z0-9._-]{0,99}/)) { error 'RUN_LABEL must be letters, digits, dot, dash, or underscore' }
          if (!(params.PARALLEL ==~ /[1-9][0-9]?/)) { error 'PARALLEL must be a number from 1 to 99' }
          for (String path : params.SCRIPTS.trim().split(/\s+/)) {
            if (path.startsWith('/') || path.contains('..')) { error "SCRIPTS entries are paths inside the repository: ${path}" }
          }
          currentBuild.description = "${params.RUN_LABEL}: ${params.SCRIPTS_REF ?: 'job branch'} ${params.SCRIPTS}"
        }
      }
    }

    stage('Check out scripts') {
      steps {
        script {
          // The job's own SCM settings (this repository and its credentials)
          // are reused; SCRIPTS_REF picks the branch the assistant pushed.
          def ref = params.SCRIPTS_REF?.trim()
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

    stage('Install mobile-auto') {
      steps {
        sh '''#!/bin/bash
          set -euo pipefail
          mkdir -p .efp-bin
          if [ -n "${MOBILE_AUTO_URL}" ]; then
            curl -fsSL -o .efp-bin/mobile-auto "${MOBILE_AUTO_URL}"
            chmod +x .efp-bin/mobile-auto
          else
            ln -sf "$(command -v mobile-auto)" .efp-bin/mobile-auto
          fi
          .efp-bin/mobile-auto version --json
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
            args=(app upload --file "$name" --json)
            if [ -n "${APP_CUSTOM_ID}" ]; then args+=(--custom-id "${APP_CUSTOM_ID}"); fi
            .efp-bin/mobile-auto "${args[@]}"
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
            // The matrix is printed on one line whenever it changes, prefixed
            // EFP-MATRIX, so the assistant can follow the run from the
            // console log while it goes; the files are archived at the end.
            rc = sh(returnStatus: true, script: '''#!/bin/bash
              set -uo pipefail
              out="mobile/runs/${RUN_LABEL}"
              rm -rf "$out"
              mkdir -p "$out"
              args=(test run --parallel "${PARALLEL}" --wait-capacity --run-label "${RUN_LABEL}" --build "${RUN_LABEL}"
                    --matrix-out "$out/matrix.json" --evidence-dir "$out/cases"
                    --junit-out "$out/junit.xml" --report-out "$out/report.json" --json)
              for path in ${SCRIPTS}; do
                if [ -d "$path" ]; then args+=(--dir "$path"); else args+=(--file "$path"); fi
              done
              if [ -n "${CASE}" ]; then args+=(--case "${CASE}"); fi
              if [ -n "${MATRIX}" ]; then args+=(--matrix "${MATRIX}"); fi
              if [ "${COLLECT_VIDEO}" = "true" ]; then args+=(--collect-video); fi
              .efp-bin/mobile-auto "${args[@]}" > "$out/run.json" 2> "$out/run.log" &
              pid=$!
              last=""
              while kill -0 "$pid" 2>/dev/null; do
                if [ -f "$out/matrix.json" ]; then
                  cur="$(tr -d '\\n' < "$out/matrix.json")"
                  if [ "$cur" != "$last" ]; then echo "EFP-MATRIX $cur"; last="$cur"; fi
                fi
                sleep 30
              done
              wait "$pid"
              status=$?
              if [ -f "$out/matrix.json" ]; then echo "EFP-MATRIX $(tr -d '\\n' < "$out/matrix.json")"; fi
              exit $status
            ''')
          }
          if (rc != 0) {
            // Failed scenarios make the build unstable; the evidence still
            // gets archived for triage.
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
        out="mobile/runs/${RUN_LABEL}"
        if [ -d "$out" ]; then
          tar czf "$out/evidence.tar.gz" --exclude='*.mp4' --exclude='evidence.tar.gz' -C "$out" .
        fi
      '''
      archiveArtifacts allowEmptyArchive: true, artifacts: "mobile/runs/${params.RUN_LABEL}/matrix.json, mobile/runs/${params.RUN_LABEL}/evidence.tar.gz, mobile/runs/${params.RUN_LABEL}/run.json, mobile/runs/${params.RUN_LABEL}/cases/**/video.mp4"
      junit allowEmptyResults: true, testResults: "mobile/runs/${params.RUN_LABEL}/junit.xml"
    }
  }
}
