#!/usr/bin/env bash
set -euo pipefail

# setup_server.sh — One-time Ubuntu 22.04+ server setup
# Run as root or with sudo: bash scripts/setup_server.sh

echo "==> Updating system packages..."
apt-get update -y && apt-get upgrade -y

echo "==> Installing Docker..."
apt-get install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Enabling Docker service..."
systemctl enable docker
systemctl start docker

echo "==> Configuring firewall (ufw)..."
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw --force enable

echo "==> Creating deploy directory /srv/app..."
mkdir -p /srv/app

echo "==> Creating systemd service for unified-backend..."
cat > /etc/systemd/system/unified-backend.service << 'EOF'
[Unit]
Description=Unified Backend (Docker Compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/srv/app/unified-backend
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable unified-backend

echo ""
echo "==> Server setup complete."
echo "    Next steps:"
echo "    1. cd /srv/app && git clone <repo-url> unified-backend"
echo "    2. cd unified-backend && git checkout prod"
echo "    3. cp .env.prod.example .env.prod && nano .env.prod"
echo "    4. bash scripts/deploy.sh"
