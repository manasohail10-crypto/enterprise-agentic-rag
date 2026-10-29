// Jenkins pipeline for Enterprise RAG (Step 16).
//
//   GitHub push -> webhook -> Jenkins
//     1. lint + tests          (in a clean python container)
//     2. SonarQube             (code quality gate: the build FAILS if the gate fails)
//     3. Trivy                 (files + images: the build FAILS on CRITICAL problems that have a fix)
//     4. build images, push to ECR with the tag  j<BUILD>-<commit>
//     5. GitOps: write the new tag in deploy/eks/kustomization.yaml and push it to GitHub.
//        ArgoCD sees the change and starts the canary rollout (Step 17 and 18).
//
// Jenkins itself never touches the cluster. Git is the only door into the cluster.
//
// Needs in Jenkins (Manage Jenkins > Credentials):
//   sonar-token   "Secret text"           a SonarQube token
//   github-push   "Username with password" your GitHub user name + a fine-grained token (Contents: read and write)

pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    triggers {
        githubPush() // the GitHub webhook starts the build
    }

    environment {
        AWS_REGION     = 'ap-south-1'
        TRIVY_IMAGE    = 'aquasec/trivy:0.69.3' // never 0.69.4 to 0.69.6 (the compromised releases)
        SONAR_IMAGE    = 'sonarsource/sonar-scanner-cli'
        GITOPS_FILE    = 'deploy/eks/kustomization.yaml'
        GIT_REPO_PATH  = 'github.com/manasohail10-crypto/enterprise-agentic-rag.git'
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    def subject = sh(script: 'git log -1 --pretty=%s', returnStdout: true).trim()
                    // Our own "bump the tag" commit must NOT start another build (that would loop forever).
                    env.SKIP_BUILD = subject.contains('[ci-bump]') ? 'true' : 'false'
                    env.SHORT_SHA  = sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()
                    env.TAG        = "j${env.BUILD_NUMBER}-${env.SHORT_SHA}"
                    env.IS_MAIN    = (env.GIT_BRANCH == 'origin/main' || env.GIT_BRANCH == 'main') ? 'true' : 'false'
                    if (env.SKIP_BUILD == 'true') {
                        currentBuild.result = 'NOT_BUILT'
                        currentBuild.description = 'ci-bump commit, skipped'
                    } else {
                        currentBuild.description = env.TAG
                    }
                }
            }
        }

        stage('Lint and tests') {
            when { expression { env.SKIP_BUILD == 'false' } }
            steps {
                // Everything runs in a fresh container, so Jenkins itself needs no Python.
                sh '''
                    docker run --rm -v "$WORKSPACE:/w" -w /w python:3.12-slim sh -c "
                      pip install --quiet ruff==0.17.2 &&
                      ruff check . &&
                      pip install --quiet -r requirements-ci.txt -c requirements.lock.txt &&
                      python -m pytest tests -v
                    "
                '''
            }
        }

        stage('SonarQube') {
            when { expression { env.SKIP_BUILD == 'false' } }
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    // The scanner runs on the same docker network as SonarQube (called "ci_default").
                    // -Dsonar.qualitygate.wait=true makes the build wait for the answer and FAIL if the gate fails.
                    sh '''
                        docker run --rm --network ci_default \
                          -e SONAR_HOST_URL=http://sonarqube:9000 \
                          -e SONAR_TOKEN \
                          -v "$WORKSPACE:/usr/src" \
                          $SONAR_IMAGE \
                          -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=300
                    '''
                }
            }
        }

        stage('Trivy (files)') {
            when { expression { env.SKIP_BUILD == 'false' } }
            steps {
                sh '''
                    docker run --rm -v "$WORKSPACE:/w" -v trivy-cache:/root/.cache/ $TRIVY_IMAGE \
                      fs --scanners secret,misconfig --severity HIGH,CRITICAL --exit-code 1 \
                      --skip-dirs /w/terraform/eks --ignorefile /w/.trivyignore.yaml /w
                '''
            }
        }

        stage('Build images') {
            when { expression { env.SKIP_BUILD == 'false' } }
            steps {
                script {
                    env.ACCOUNT  = sh(script: 'aws sts get-caller-identity --query Account --output text', returnStdout: true).trim()
                    env.REGISTRY = "${env.ACCOUNT}.dkr.ecr.${env.AWS_REGION}.amazonaws.com"
                }
                sh '''
                    docker build -t $REGISTRY/enterprise-rag-api:$TAG -f Dockerfile .
                    docker build -t $REGISTRY/enterprise-rag-ui:$TAG  -f Dockerfile.ui .
                '''
            }
        }

        stage('Trivy (images)') {
            when { expression { env.SKIP_BUILD == 'false' } }
            steps {
                sh '''
                    for NAME in api ui; do
                      docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/ $TRIVY_IMAGE \
                        image --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 \
                        $REGISTRY/enterprise-rag-$NAME:$TAG
                    done
                '''
            }
        }

        stage('Push to ECR') {
            when { expression { env.SKIP_BUILD == 'false' && env.IS_MAIN == 'true' } }
            steps {
                // No password is stored: Jenkins uses the role of the server (it can only push to our two repositories).
                sh '''
                    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REGISTRY
                    docker push $REGISTRY/enterprise-rag-api:$TAG
                    docker push $REGISTRY/enterprise-rag-ui:$TAG
                '''
            }
        }

        stage('GitOps: write the new tag') {
            when { expression { env.SKIP_BUILD == 'false' && env.IS_MAIN == 'true' } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'github-push', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                    // Single quotes: Groovy does not touch the secrets, the shell reads them from the environment.
                    sh '''
                        git config user.name  "jenkins-ci"
                        git config user.email "jenkins-ci@users.noreply.github.com"
                        git fetch origin main
                        git checkout -B main origin/main
                        sed -i -E "s/^( *newTag: ).*/\\1$TAG/" $GITOPS_FILE
                        git add $GITOPS_FILE
                        git diff --cached --quiet && { echo "nothing to change"; exit 0; }
                        git commit -m "[ci-bump] images -> $TAG"
                        git -c credential.helper='!f() { echo "username=$GIT_USER"; echo "password=$GIT_PASS"; }; f' \
                          push https://$GIT_REPO_PATH main
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
    }
}