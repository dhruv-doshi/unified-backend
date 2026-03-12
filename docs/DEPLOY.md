# Deployment Guide — DigitalOcean Droplet

Step-by-step guide for deploying to a DigitalOcean Droplet (Ubuntu 22.04 LTS).

> **Setup:** No custom domain or SSL. The API is accessed directly over HTTP via the Droplet's public IP address (`http://<your-server-ip>/api/`).

---

## Table of Contents

1. [Create a Droplet](#1-create-a-droplet)
2. [Provision with One Script (from your Mac)](#2-provision-with-one-script-from-your-mac)
3. [Manual Provisioning (alternative)](#3-manual-provisioning-alternative)
   - 3a. [Initial SSH Access](#3a-initial-ssh-access)
   - 3b. [Secure the Server](#3b-secure-the-server)
   - 3c. [One-Time Server Setup](#3c-one-time-server-setup)
   - 3d. [Add Swap (required on 2 GB plan)](#3d-add-swap-required-on-2-gb-plan)
   - 3e. [Clone the Repository](#3e-clone-the-repository)
4. [Configure Environment](#4-configure-environment)
5. [Deploy](#5-deploy)
6. [Verify Deployment](#6-verify-deployment)
7. [Updating the Server](#7-updating-the-server)
8. [Rolling Back](#8-rolling-back)
9. [Frontend Note](#9-frontend-note)
10. [Logs & Monitoring](#10-logs--monitoring)
11. [Resource Budget — 2 GB RAM Plan](#11-resource-budget--2-gb-ram-plan)

---

## 1. Create a Droplet

### 1.1 Log in to DigitalOcean

Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) and sign in.

### 1.2 Create a new Droplet

1. Click **Create → Droplets** from the top navigation.

2. **Choose a region** — pick the region closest to your users.
   > **Recommendation:** `NYC3` (US East), `SFO3` (US West), `AMS3` (Europe), `SGP1` (Asia).

3. **Choose an image**
   > **Recommendation:** Select **Ubuntu 22.04 (LTS) x64**.

4. **Choose a plan** — select **Basic Shared / 1 vCPU / 2 GB RAM / 50 GB SSD (~$12/mo)**.
   The `docker-compose.prod.yml` is tuned for this plan. A 2 GB swap file is added automatically.

5. **Additional storage** — skip.

6. **Authentication — SSH Keys (strongly recommended)**
   - Click **New SSH Key**.
   - On your local Mac, generate a key if you don't have one:
     ```bash
     ssh-keygen -t ed25519 -C "your-email@example.com"
     ```
   - Copy the public key:
     ```bash
     cat ~/.ssh/id_ed25519.pub
     ```
   - Paste it into the DigitalOcean dialog and give it a name (e.g., `MacBook`).

7. **Hostname** — give it a meaningful name, e.g., `unified-backend-prod`.

8. Click **Create Droplet** and wait ~60 seconds. Copy the **IPv4 address** — you will use it as `<your-server-ip>` throughout this guide.

---

## 2. Provision with One Script (from your Mac)

Run this **from your local machine** inside the `unified-backend` directory:

```bash
bash scripts/provision_droplet.sh <your-server-ip>
```

The script will:

1. Copy your local SSH public key to `root@<ip>` — you'll be prompted for the root password once
2. Create a non-root `deploy` user with passwordless sudo
3. Install Docker, UFW firewall, Fail2Ban, and register the systemd service
4. Add a **2 GB swap file** (required for the 2 GB RAM plan)
5. Generate a GitHub deploy SSH key on the server and pause for you to add it to GitHub
6. Clone the repository to `/srv/app/unified-backend`

After it finishes, jump to [Section 4 — Configure Environment](#4-configure-environment).

---

## 3. Manual Provisioning (alternative)

Skip this section if you used the script in Section 2.

### 3a. Initial SSH Access

```bash
ssh root@<your-server-ip>
```

Create a non-root deploy user:

```bash
adduser --disabled-password --gecos "" deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Verify in a new terminal:

```bash
ssh deploy@<your-server-ip>
sudo whoami   # should print "root"
```

### 3b. Secure the Server

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

Configure UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw --force enable
```

Harden SSH — edit `/etc/ssh/sshd_config` and set:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
```

Install Fail2Ban:

```bash
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
```

### 3c. One-Time Server Setup

```bash
# Install Docker
sudo apt-get install -y ca-certificates curl gnupg lsb-release
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
sudo usermod -aG docker deploy

# Create app directory
sudo mkdir -p /srv/app
sudo chown deploy:deploy /srv/app

# Register systemd service
sudo tee /etc/systemd/system/unified-backend.service > /dev/null << 'EOF'
[Unit]
Description=Unified Backend (Docker Compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/srv/app/unified-backend
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml --env-file .env.prod down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable unified-backend
```

**Log out and back in** so the `docker` group change takes effect:

```bash
exit
ssh deploy@<your-server-ip>
docker ps   # should work without sudo
```

### 3d. Add Swap (required on 2 GB plan)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
free -h   # should show: Swap: 2.0Gi
```

### 3e. Clone the Repository

```bash
ssh-keygen -t ed25519 -C "deploy@server" -f ~/.ssh/github_deploy_key -N ""

cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy_key
EOF

chmod 600 ~/.ssh/config
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
```

Add the public key to GitHub:

```bash
cat ~/.ssh/github_deploy_key.pub
```

1. Go to [github.com/dhruv-doshi/unified-backend/settings/keys](https://github.com/dhruv-doshi/unified-backend/settings/keys)
2. Click **Add deploy key** → paste the key → name it `DO Droplet` → leave **Allow write access** unchecked → **Add key**

```bash
cd /srv/app
git clone git@github.com:dhruv-doshi/unified-backend.git
cd unified-backend
git checkout prod
```

---

## 4. Configure Environment

```bash
cd /srv/app/unified-backend
cp .env.prod.example .env.prod
nano .env.prod
```

Fill in **all** values:

| Variable | How to generate / where to find |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_PASSWORD` | `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `R2_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` — Account ID in Cloudflare dashboard → R2 |
| `R2_ACCESS_KEY_ID` | Cloudflare dashboard → R2 → Manage R2 API Tokens |
| `R2_SECRET_ACCESS_KEY` | Same as above |
| `R2_BUCKET_NAME` | Name of your R2 bucket |
| `R2_PUBLIC_BASE_URL` | Public domain attached to the bucket (e.g. `https://cdn.example.com`) |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) → Keys |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Your SMTP provider credentials |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials |
| `FRONTEND_URL` | Set to `http://<your-server-ip>` until you have a real frontend URL |

Set secure permissions:

```bash
chmod 600 .env.prod
```

---

## 5. Deploy

```bash
cd /srv/app/unified-backend
bash scripts/deploy.sh
```

The script: pulls latest `prod` branch → rebuilds containers → starts all services → runs DB migrations → seeds accounts.

Check all containers are running:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

All services should show `Up` or `running`. If any show `Exit`, check logs:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs <service-name>
```

---

## 6. Verify Deployment

```bash
# Health check (from the server or your local machine)
curl http://157.245.101.121/health
# Expected: {"status": "ok"}

# API docs (browse from your machine)
open http://<your-server-ip>/docs

# All containers running
docker compose -f docker-compose.prod.yml --env-file .env.prod ps

# Memory usage
free -h
```

---

## 7. Updating the Server

After pushing changes to the `prod` branch on your Mac:

```bash
ssh deploy@<your-server-ip>
cd /srv/app/unified-backend
bash scripts/deploy.sh
```

---

## 8. Rolling Back

```bash
ssh deploy@<your-server-ip>
cd /srv/app/unified-backend

git checkout <commit-sha>
bash scripts/deploy.sh
```

To roll back only the database (without changing code):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm api alembic downgrade -1
```

---

## 9. Frontend Note

The frontend (Next.js) is deployed separately on Vercel or Netlify. Set:

```
NEXT_PUBLIC_API_URL=http://<your-server-ip>
```

Once deployed, update `FRONTEND_URL` in `.env.prod` to the exact frontend origin (scheme + hostname, no trailing slash) and restart the API:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart api
```

---

## 10. Logs & Monitoring

```bash
# All services
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f

# Single service
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f api
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f worker
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f nginx

# Per-container CPU/RAM
docker stats

# Disk usage
df -h
```

Prune unused Docker data (run monthly):

```bash
docker system prune -f
```

### DigitalOcean built-in monitoring

1. Droplet dashboard → **Monitoring** tab → enable the **Monitoring Agent**
2. **Monitoring → Alert Policies** → set:
   - CPU > 80% for 5 min → email alert
   - RAM > 85% for 5 min → email alert
   - Disk > 80% → email alert

---

## 11. Resource Budget — 2 GB RAM Plan

| Service | Memory limit | Notes |
|---|---|---|
| PostgreSQL | 256 MB | Sufficient for low-to-medium query load |
| Redis | 128 MB | Rate limiting + Celery queue |
| API (Uvicorn) | 512 MB | 2 workers |
| Celery worker | 384 MB | concurrency=1 |
| Nginx | ~20 MB | Proxy only |
| **Total** | **~1.3 GB** | ~700 MB headroom + 2 GB swap |

Steady-state RAM sits around 900 MB–1.1 GB. The swap absorbs spikes during Docker builds.

**Upgrading to the $24 / 2 vCPU / 4 GB plan:** edit `docker-compose.prod.yml` and change:
- `--workers 2` → `--workers 4`
- `--concurrency=1` → `--concurrency=2`
- `memory: 512m` (api) → `memory: 1g`
- `memory: 384m` (worker) → `memory: 1g`
