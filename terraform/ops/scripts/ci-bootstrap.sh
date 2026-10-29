#!/bin/bash
# Runs once, as root, when the CI server starts for the first time (EC2 "user data").
# Installs Docker, then starts Jenkins and SonarQube from the jenkins/ folder of your repository.
# Watch it with:   sudo tail -f /var/log/ci-bootstrap.log
set -euo pipefail
exec > >(tee /var/log/ci-bootstrap.log) 2>&1

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git unzip snapd
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker ubuntu

# SonarQube (Elasticsearch inside it) refuses to start without these settings.
cat > /etc/sysctl.d/99-sonarqube.conf <<'SYSCTL'
vm.max_map_count=262144
fs.file-max=65536
SYSCTL
sysctl --system

# Jenkins keeps its files in /var/jenkins_home. The SAME path is used inside and outside the container,
# so the docker commands that Jenkins starts can find the project files. User 1000 is the "jenkins" user in the image.
mkdir -p /var/jenkins_home
chown 1000:1000 /var/jenkins_home

git clone --depth 1 --branch "${git_branch}" "${repo_url}" /opt/ci
cd /opt/ci/jenkins

# The container must be allowed to use the docker socket: give it the group number of the "docker" group.
cat > .env <<ENVFILE
DOCKER_GID=$(getent group docker | cut -d: -f3)
AWS_REGION=${region}
ENVFILE

docker compose up -d --build
echo "CI server is ready"