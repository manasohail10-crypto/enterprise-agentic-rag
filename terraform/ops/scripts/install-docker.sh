#!/bin/bash
# Runs once, as root, when the app server starts for the first time (EC2 "user data").
# Installs Docker Engine from Docker's official apt repository (the same steps as Step 13).
set -euo pipefail
exec > >(tee /var/log/install-docker.log) 2>&1

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git unzip snapd
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker ubuntu
snap install aws-cli --classic || true
mkdir -p /home/ubuntu/rag && chown ubuntu:ubuntu /home/ubuntu/rag
echo "docker is ready"