#!/bin/bash
set -e

echo "=== Installing Docker ==="
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin > /dev/null 2>&1

systemctl enable docker
systemctl start docker

echo "Docker installed:"
docker --version
docker compose version

echo ""
echo "=== Cloning repo ==="
mkdir -p /opt
cd /opt
if [ -d "taxja" ]; then
  echo "taxja directory exists, pulling latest..."
  cd taxja
  git pull
else
  git clone https://github.com/yk1e25/taxja.git
  cd taxja
fi

echo "Repo ready at /opt/taxja"
echo ""
echo "=== Server init complete ==="
