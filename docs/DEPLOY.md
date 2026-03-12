# Deployment Guide — DigitalOcean Droplet

Step-by-step guide for deploying to a DigitalOcean Droplet (Ubuntu 22.04 LTS).

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
6. [Point DNS to Droplet](#6-point-dns-to-droplet)
7. [SSL Certificate (Let's Encrypt)](#7-ssl-certificate-lets-encrypt)
8. [Verify Deployment](#8-verify-deployment)
9. [Updating the Server](#9-updating-the-server)
10. [Rolling Back](#10-rolling-back)
11. [Frontend Deployment Note](#frontend-deployment-note)
12. [Logs & Monitoring](#logs--monitoring)
13. [Resource Budget — 2 GB RAM Plan](#resource-budget--2-gb-ram-plan)

---

## 1. Create a Droplet

### 1.1 Log in to DigitalOcean

Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) and sign in.

### 1.2 Create a new Droplet

1. Click **Create → Droplets** from the top navigation.

2. **Choose a region** — pick the region closest to your users.
   > **Recommendation:** `NYC3` (US East), `SFO3` (US West), `AMS3` (Europe), `SGP1` (Asia). Pick based on where most of your users are. If unsure, `NYC3` is a good default.

3. **Choose an image**
   > **Recommendation:** Select **Ubuntu 22.04 (LTS) x64**. Do not choose the newer 24.04 — Docker's Ubuntu packages have wider 22.04 testing.

4. **Choose a plan**

   | Plan | vCPU | RAM | SSD | Price | Notes |
   |---|---|---|---|---|---|
   | Basic Shared | 1 | 2 GB | 50 GB | ~$12/mo | Fine for low-to-medium traffic. Use swap. |
   | Basic Shared | 2 | 4 GB | 80 GB | ~$24/mo | Recommended for production. No swap needed. |
   | General Purpose | 2 | 8 GB | 25 GB NVMe | ~$63/mo | High-traffic / multiple Celery workers |

   > **Recommendation for $12 plan:** This guide is optimised for the 1 vCPU / 2 GB RAM plan. The `docker-compose.prod.yml` has been tuned with reduced worker counts and memory limits that fit within this budget. A 2 GB swap file is added automatically (see Section 3d).

5. **Additional storage** — skip unless you expect very large file uploads (>10 GB total stored on disk). R2 handles object storage externally.

6. **Authentication — SSH Keys (strongly recommended)**
   > **Recommendation:** Always use SSH keys, not password. Passwords are vulnerable to brute-force attacks and DigitalOcean will email the root password in plaintext.

   - Click **New SSH Key**.
   - On your local Mac, generate a key if you don't have one:
     ```bash
     ssh-keygen -t ed25519 -C "your-email@example.com"
     # Press Enter for all prompts to accept defaults
     ```
   - Copy the public key:
     ```bash
     cat ~/.ssh/id_ed25519.pub
     ```
   - Paste it into the DigitalOcean dialog and give it a name (e.g., `MacBook`).

7. **Backups** (optional)
   > **Recommendation:** Enable if this is a production app. It adds ~20% to the Droplet cost but gives you weekly snapshots you can restore from.

8. **Hostname** — give it a meaningful name, e.g., `unified-backend-prod`.

9. Click **Create Droplet** and wait ~60 seconds. Copy the **IPv4 address** — you will use it as `<your-server-ip>` throughout this guide.

---

## 2. Provision with One Script (from your Mac)

This is the fastest path. Run this **from your local machine** — it handles everything: creating the deploy user, installing Docker, adding swap, and cloning the repo.

```bash
# From your local machine, inside the unified-backend directory
bash scripts/provision_droplet.sh <your-server-ip>
```

The script will:

1. Copy your local SSH public key to `root@<ip>` — you'll be prompted for the root password once
2. Create a non-root `deploy` user with passwordless sudo
3. Install Docker, UFW firewall, Fail2Ban, and register the systemd service
4. Add a **2 GB swap file** (required to keep the stack within the 2 GB RAM limit)
5. Generate a GitHub deploy SSH key on the server and pause for you to add it to GitHub
6. Clone the repository to `/srv/app/unified-backend`
7. Print exact next steps

After it finishes, jump to [Section 4 — Configure Environment](#4-configure-environment).

---

## 3. Manual Provisioning (alternative)

Skip this section if you used the script in Section 2.

### 3a. Initial SSH Access

Connect as root using the password DigitalOcean emailed you:

```bash
ssh root@<your-server-ip>
```

Create a non-root deploy user:

```bash
adduser deploy
# Prompts:
#   New password: <enter a strong password>
#   Full Name []: <leave blank, press Enter>
#   Room Number []: <press Enter>
#   Work Phone []: <press Enter>
#   Home Phone []: <press Enter>
#   Other []: <press Enter>
#   Is the information correct? [Y/n]: Y

usermod -aG sudo deploy

# Copy your SSH key to the deploy user
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Open a new terminal and verify:

```bash
ssh deploy@<your-server-ip>
sudo whoami   # should print "root"
```

### 3b. Secure the Server

Run as the `deploy` user:

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

> **Interactive prompts during upgrade:**
> - **"A new version of configuration file /etc/ssh/sshd_config is available"** → Select **"keep the local version currently installed"** (option N or press Enter on "keep"). Do NOT overwrite — it would reset any SSH hardening.
> - **"Which services should be restarted?"** → Press Enter to accept the defaults listed. This is safe and just restarts affected services.
> - **"A new kernel is available"** or **"Restart required"** → After the upgrade finishes, run `sudo reboot` and reconnect after ~30 seconds.

Configure UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
# Prompt: "Command may disrupt existing ssh connections. Proceed with operation (y|n)?" → y
sudo ufw status verbose
```

Harden SSH (disable root and password login):

```bash
sudo nano /etc/ssh/sshd_config
```

Set or confirm:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
```

> Verify you can still SSH as `deploy` in a separate terminal before closing the root session.

Install Fail2Ban:

```bash
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
```

### 3c. One-Time Server Setup

Install Docker, set up the app directory, and register the systemd service:

```bash
# Install Docker
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
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
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
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

The full stack (PostgreSQL + Redis + API + Celery + Nginx) peaks at ~1.3 GB RAM. Adding swap prevents OOM kills during Docker builds, which can use an additional 500 MB+ temporarily.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Reduce swap aggressiveness (10 = only use swap when RAM is 90%+ full)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Verify
free -h
# Should show: Swap: 2.0Gi
```

### 3e. Clone the Repository

#### Generate a deploy SSH key (for private repos)

```bash
ssh-keygen -t ed25519 -C "deploy@server" -f ~/.ssh/github_deploy_key -N ""

cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy_key
EOF

chmod 600 ~/.ssh/config
```

Add the public key to GitHub:

```bash
cat ~/.ssh/github_deploy_key.pub
```

1. Go to [github.com/dhruv-doshi/unified-backend/settings/keys](https://github.com/dhruv-doshi/unified-backend/settings/keys)
2. Click **Add deploy key**
3. Paste the output above
4. Name: `DO Droplet`
5. Leave **Allow write access** unchecked
6. Click **Add key**

Test and clone:

```bash
ssh -T git@github.com
# Expected: "Hi dhruv-doshi/unified-backend! You've successfully authenticated..."

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

Fill in **all** values. Required secrets:

| Variable | How to generate / where to find |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_PASSWORD` | `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `CLOUDFLARE_R2_ACCOUNT_ID` | Cloudflare dashboard → R2 → your bucket |
| `CLOUDFLARE_R2_ACCESS_KEY_ID` | Cloudflare dashboard → R2 → Manage R2 API Tokens |
| `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | Same as above |
| `CLOUDFLARE_R2_BUCKET_NAME` | Name of your R2 bucket |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) → Keys |
| `SENDGRID_API_KEY` | [sendgrid.com](https://sendgrid.com) → Settings → API Keys |
| `GOOGLE_CLIENT_ID` | Google Cloud Console → APIs & Services → Credentials |
| `GOOGLE_CLIENT_SECRET` | Same as above |
| `FRONTEND_URL` | Your production frontend domain, e.g. `https://shootright.app` |

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

The script: pulls latest `prod` branch → rebuilds containers → runs DB migrations → seeds accounts → starts all services.

Check all containers are running:

```bash
docker compose -f docker-compose.prod.yml ps
```

All services should show `Up` or `running`. If any show `Exit`, check logs:

```bash
docker compose -f docker-compose.prod.yml logs <service-name>
```

---

## 6. Point DNS to Droplet

In your domain registrar or DNS provider:

```
Type    Name    Value
A       @       <your-server-ip>
A       www     <your-server-ip>
A       api     <your-server-ip>    # only if using api.yourdomain.com
```

### Using DigitalOcean DNS (optional)

1. In the dashboard, go to **Networking → Domains**.
2. Add your domain and create the A records above pointing to your Droplet.
3. At your registrar, set nameservers to:
   ```
   ns1.digitalocean.com
   ns2.digitalocean.com
   ns3.digitalocean.com
   ```

Check propagation (usually minutes, up to 24 hours):

```bash
dig +short yourdomain.com
# Should return <your-server-ip>
```

---

## 7. SSL Certificate (Let's Encrypt)

> Complete this only after `dig +short yourdomain.com` returns your Droplet IP.

### 7.1 Install Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### 7.2 Obtain the certificate

Stop Nginx to free port 80 for the ACME challenge:

```bash
docker compose -f docker-compose.prod.yml stop nginx
```

```bash
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive
```

> **Certbot prompts:**
> - **"Enter email address"** → enter your real email (used for expiry warnings)
> - **"Please read the Terms of Service"** → `A` to agree
> - **"Would you be willing to share your email?"** → `N` (optional, up to you)

### 7.3 Copy certs into the Nginx mount directory

```bash
mkdir -p /srv/app/unified-backend/nginx/ssl

sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem \
        /srv/app/unified-backend/nginx/ssl/fullchain.pem

sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem \
        /srv/app/unified-backend/nginx/ssl/privkey.pem

sudo chown deploy:deploy /srv/app/unified-backend/nginx/ssl/*.pem
```

### 7.4 Update Nginx config for HTTPS

Edit `nginx/conf.d/default.conf`:

```nginx
# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    location /api/ {
        proxy_pass         http://api:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 20M;
    }

    location /health {
        proxy_pass http://api:8000/health;
    }
}
```

### 7.5 Restart Nginx

```bash
docker compose -f docker-compose.prod.yml up -d nginx
```

### 7.6 Auto-renew certificates

Check if the systemd timer is active:

```bash
sudo systemctl status certbot.timer
```

If not active, add a cron job:

```bash
sudo crontab -e
# Prompt: "Select an editor" → enter 1 for nano (easiest)
```

Add:

```
0 3 * * 0 certbot renew --quiet \
  && cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /srv/app/unified-backend/nginx/ssl/ \
  && cp /etc/letsencrypt/live/yourdomain.com/privkey.pem   /srv/app/unified-backend/nginx/ssl/ \
  && docker compose -f /srv/app/unified-backend/docker-compose.prod.yml restart nginx
```

---

## 8. Verify Deployment

```bash
# Health check
curl https://yourdomain.com/health
# Expected: {"status": "ok"}

# All containers running
docker compose -f docker-compose.prod.yml ps

# Memory usage (confirm we're within 2 GB budget)
free -h

# SSL grade
curl -vI https://yourdomain.com 2>&1 | grep -E "SSL|subject|issuer"
```

---

## 9. Updating the Server

After pushing changes to the `prod` branch:

```bash
ssh deploy@<your-server-ip>
cd /srv/app/unified-backend
bash scripts/deploy.sh
```

---

## 10. Rolling Back

```bash
ssh deploy@<your-server-ip>
cd /srv/app/unified-backend

git checkout v1.2.3        # or git checkout <commit-sha>
bash scripts/deploy.sh
```

To roll back only the database (without changing code):

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic downgrade -1
```

---

## Frontend Deployment Note

The frontend (Next.js) is deployed **separately** on Vercel or Netlify. Set:

```
NEXT_PUBLIC_API_URL=https://yourdomain.com
```

Ensure `FRONTEND_URL` in `.env.prod` exactly matches the deployed frontend origin (scheme + hostname, no trailing slash).

---

## Logs & Monitoring

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# API only
docker compose -f docker-compose.prod.yml logs -f api

# Celery worker only
docker compose -f docker-compose.prod.yml logs -f worker

# Nginx
docker compose -f docker-compose.prod.yml logs -f nginx

# Service status
docker compose -f docker-compose.prod.yml ps

# Per-container CPU/RAM usage
docker stats

# Disk usage
df -h
```

Prune unused Docker data (run monthly to reclaim disk):

```bash
docker system prune -f
```

### DigitalOcean built-in monitoring

1. Droplet dashboard → **Monitoring** tab
2. Enable the **Monitoring Agent** for CPU, RAM, and disk metrics
3. Go to **Monitoring → Alert Policies** and set:
   - CPU > 80% for 5 min → email alert
   - RAM > 85% for 5 min → email alert
   - Disk > 80% → email alert

---

## Resource Budget — 2 GB RAM Plan

The `docker-compose.prod.yml` is tuned for the $12 / 1 vCPU / 2 GB RAM DigitalOcean plan:

| Service | Memory limit | Notes |
|---|---|---|
| PostgreSQL | 256 MB | Sufficient for low-to-medium query load |
| Redis | 128 MB | Rate limiting + Celery queue |
| API (Uvicorn) | 512 MB | 2 workers (reduced from 4) |
| Celery worker | 384 MB | concurrency=1 (reduced from 4) |
| Nginx | ~20 MB | Proxy only, no caching |
| **Total** | **~1.3 GB** | ~700 MB headroom + 2 GB swap |

The 2 GB swap file absorbs spikes during Docker image builds and JIT compilation on first start. Steady-state RAM usage sits around 900 MB–1.1 GB.

**Upgrading to the $24 / 2 vCPU / 4 GB plan:** Edit `docker-compose.prod.yml` and change:
- `--workers 2` → `--workers 4`
- `--concurrency=1` → `--concurrency=2`
- `memory: 512m` (api) → `memory: 1g`
- `memory: 384m` (worker) → `memory: 1g`
