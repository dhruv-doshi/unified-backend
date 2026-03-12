#!/usr/bin/env bash
# provision_droplet.sh — Run this from your LOCAL machine.
# Usage: bash scripts/provision_droplet.sh <server-ip> [deploy-user]
#
# What it does:
#   1. Copies your local SSH public key to root@<ip> so root login works (one-time)
#   2. Creates a non-root 'deploy' user with sudo + SSH access
#   3. Runs setup_server.sh on the remote (installs Docker, UFW, systemd service)
#   4. Adds a swap file (2 GB) — critical for the $12 / 2 GB RAM plan
#   5. Sets up a GitHub deploy SSH key on the server
#   6. Prints next-step instructions

set -euo pipefail

# ── Arguments ────────────────────────────────────────────────────────────────
SERVER_IP="${1:?Usage: bash scripts/provision_droplet.sh <server-ip> [deploy-user]}"
DEPLOY_USER="${2:-deploy}"
REPO="git@github.com:dhruv-doshi/unified-backend.git"
APP_DIR="/srv/app/unified-backend"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

# ── Step 0: Verify local SSH key exists ──────────────────────────────────────
LOCAL_PUBKEY="$HOME/.ssh/id_ed25519.pub"
if [[ ! -f "$LOCAL_PUBKEY" ]]; then
  warn "No SSH key found at $LOCAL_PUBKEY. Generating one now..."
  ssh-keygen -t ed25519 -C "deploy@$(hostname)" -f "$HOME/.ssh/id_ed25519" -N ""
fi

info "Using public key: $LOCAL_PUBKEY"
info "Target server:    $SERVER_IP"
info "Deploy user:      $DEPLOY_USER"
echo ""

# ── Step 1: Copy key to root (initial access) ─────────────────────────────
info "Step 1/5 — Copying SSH key to root@$SERVER_IP ..."
warn "You will be prompted for the root password DigitalOcean emailed you."
ssh-copy-id -i "$LOCAL_PUBKEY" "root@$SERVER_IP"

# ── Step 2: Create deploy user + copy SSH key ─────────────────────────────
info "Step 2/5 — Creating '$DEPLOY_USER' user on the server..."
ssh -o StrictHostKeyChecking=accept-new "root@$SERVER_IP" bash -s << ENDSSH
set -e
if id "$DEPLOY_USER" &>/dev/null; then
  echo "  User '$DEPLOY_USER' already exists — skipping creation."
else
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
  chmod 440 /etc/sudoers.d/$DEPLOY_USER
fi
# Copy root's authorized_keys to deploy user
mkdir -p /home/$DEPLOY_USER/.ssh
cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/authorized_keys
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys
echo "  Done."
ENDSSH

# ── Step 3: Run setup_server.sh via deploy user ───────────────────────────
info "Step 3/5 — Running server setup (Docker, UFW, systemd service)..."
warn "If apt prompts appear during upgrade, see recommendations below."
ssh "$DEPLOY_USER@$SERVER_IP" bash -s << 'ENDSSH'
set -e
# Non-interactive apt — keep existing config files automatically
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Wait for any automatic apt lock to clear (cloud-init / unattended-upgrades runs on fresh droplets)
echo "  Waiting for apt lock to clear..."
while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
  echo "  apt lock held — waiting 5 s..."
  sleep 5
done

sudo apt-get update -y
sudo apt-get upgrade -y \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold"

# Install Docker
sudo apt-get install -y ca-certificates curl gnupg lsb-release git fail2ban unattended-upgrades
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add deploy user to docker group
sudo usermod -aG docker "$USER"

# UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# systemd service
sudo mkdir -p /srv/app
sudo chown deploy:deploy /srv/app 2>/dev/null || true
sudo tee /etc/systemd/system/unified-backend.service > /dev/null << 'EOF'
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
sudo systemctl daemon-reload
sudo systemctl enable unified-backend
echo "Setup complete."
ENDSSH

# ── Step 4: Add swap (critical for 2 GB RAM plan) ────────────────────────
info "Step 4/5 — Adding 2 GB swap file (required for 2 GB RAM Droplet)..."
ssh "$DEPLOY_USER@$SERVER_IP" bash -s << 'ENDSSH'
if swapon --show | grep -q /swapfile; then
  echo "  Swap already exists — skipping."
else
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  # Reduce swappiness for server use
  echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
  sudo sysctl -p
  echo "  2 GB swap file created and activated."
fi
free -h
ENDSSH

# ── Step 5: Generate deploy SSH key and clone repo ────────────────────────
info "Step 5/5 — Setting up GitHub deploy key and cloning repository..."
REMOTE_PUBKEY=$(ssh "$DEPLOY_USER@$SERVER_IP" bash -s << 'ENDSSH'
if [[ ! -f ~/.ssh/github_deploy_key ]]; then
  ssh-keygen -t ed25519 -C "deploy@server" -f ~/.ssh/github_deploy_key -N ""
  cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy_key
EOF
  chmod 600 ~/.ssh/config
fi
cat ~/.ssh/github_deploy_key.pub
ENDSSH
)

echo ""
echo "════════════════════════════════════════════════════════════"
warn "ACTION REQUIRED — Add this deploy key to GitHub:"
echo ""
echo "$REMOTE_PUBKEY"
echo ""
echo "  1. Go to: https://github.com/dhruv-doshi/unified-backend/settings/keys"
echo "  2. Click 'Add deploy key'"
echo "  3. Paste the key above — name it 'DO Droplet $SERVER_IP'"
echo "  4. Leave 'Allow write access' UNCHECKED"
echo "  5. Click 'Add key'"
echo "════════════════════════════════════════════════════════════"
echo ""
read -rp "Press Enter once you have added the deploy key to GitHub..."

ssh "$DEPLOY_USER@$SERVER_IP" bash -s << ENDSSH
set -e
# Trust GitHub's host key
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
# Refresh docker group without logout
newgrp docker << 'INNERSH'
cd /srv/app
if [[ -d unified-backend/.git ]]; then
  echo "Repo already cloned — pulling latest..."
  cd unified-backend && git pull origin prod
else
  git clone $REPO
  cd unified-backend
  git checkout prod
fi
INNERSH
echo "Repository ready at /srv/app/unified-backend"
ENDSSH

echo ""
echo "════════════════════════════════════════════════════════════"
info "Provisioning complete!"
echo ""
echo "Next steps:"
echo ""
echo "  1. SSH into the server:"
echo "     ssh $DEPLOY_USER@$SERVER_IP"
echo ""
echo "  2. Configure environment:"
echo "     cd /srv/app/unified-backend"
echo "     cp .env.prod.example .env.prod"
echo "     nano .env.prod"
echo ""
echo "  3. Deploy:"
echo "     bash scripts/deploy.sh"
echo ""
echo "  4. Point DNS: A record @ → $SERVER_IP"
echo "  5. Then set up SSL: see docs/DEPLOY.md Section 9"
echo "════════════════════════════════════════════════════════════"
