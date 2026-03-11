# Deployment Guide

Step-by-step guide for deploying to a Linux VPS (Ubuntu 22.04+).

---

## 1. Server Provisioning

**Minimum specs:**
- 2 vCPUs, 4 GB RAM, 40 GB SSD
- Ubuntu 22.04 LTS
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)

Recommended providers: DigitalOcean, Hetzner, Linode, AWS EC2.

---

## 2. One-Time Server Setup

SSH into the server and run:

```bash
curl -fsSL https://raw.githubusercontent.com/dhruv-doshi/unified-backend/prod/scripts/setup_server.sh | sudo bash
```

Or clone the repo first and run locally:

```bash
sudo bash scripts/setup_server.sh
```

This installs Docker, configures ufw, creates `/srv/app`, and registers a systemd service that auto-starts on boot.

---

## 3. Clone the Repository

```bash
cd /srv/app
git clone git@github.com:dhruv-doshi/unified-backend.git
cd unified-backend
git checkout prod
```

---

## 4. Configure Environment

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Fill in **all** values. Required secrets:
- `SECRET_KEY` — 64+ random chars: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `DB_PASSWORD` — strong random password
- `CLOUDFLARE_R2_*` — from your R2 bucket settings
- `OPENROUTER_API_KEY` — from openrouter.ai
- `SENDGRID_API_KEY` — from sendgrid.com
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from Google Cloud Console
- `FRONTEND_URL` — your production frontend domain (e.g. `https://shootright.app`)

---

## 5. Deploy

```bash
bash scripts/deploy.sh
```

This pulls the latest `prod` branch, rebuilds containers, runs migrations, seeds accounts, and starts all services.

---

## 6. Point DNS to Server

In your domain registrar / DNS provider:

```
A    @        <your-server-ip>
A    www      <your-server-ip>
A    api      <your-server-ip>   # if using a subdomain for the API
```

Wait for DNS propagation (up to 24 hours, usually minutes).

---

## 7. SSL Certificate (Let's Encrypt)

Install Certbot and obtain a certificate:

```bash
apt-get install -y certbot python3-certbot-nginx

# Stop nginx to free port 80 temporarily
docker compose -f docker-compose.prod.yml stop nginx

certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certs are at /etc/letsencrypt/live/yourdomain.com/
# Copy to nginx/ssl/ so Docker can mount them:
mkdir -p /srv/app/unified-backend/nginx/ssl
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem   nginx/ssl/

# Update nginx/conf.d/default.conf to enable HTTPS (see below)
docker compose -f docker-compose.prod.yml up -d nginx
```

**Nginx HTTPS snippet** (`nginx/conf.d/default.conf`):
```nginx
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

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Auto-renew certs** (add to crontab):
```bash
0 3 * * 0 certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/*.pem /srv/app/unified-backend/nginx/ssl/ && docker compose -f /srv/app/unified-backend/docker-compose.prod.yml restart nginx
```

---

## 8. Verify Deployment

```bash
curl https://yourdomain.com/health
# Expected: {"status": "ok"}
```

---

## 9. Updating the Server

After pushing changes to the `prod` branch:

```bash
cd /srv/app/unified-backend
bash scripts/deploy.sh
```

---

## 10. Rolling Back

```bash
# Roll back to a specific tag or commit
git checkout v1.2.3   # or git checkout <commit-sha>
bash scripts/deploy.sh
```

---

## Frontend Deployment Note

The frontend (Next.js) is deployed **separately** — typically on Vercel or Netlify. Set these environment variables in the frontend:

```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

The backend CORS config reads `FRONTEND_URL` from `.env.prod` and whitelists that origin. Make sure `FRONTEND_URL` matches the exact origin of your deployed frontend.

---

## Logs & Monitoring

```bash
# View API logs
docker compose -f docker-compose.prod.yml logs -f api

# View worker logs
docker compose -f docker-compose.prod.yml logs -f worker

# Check all service statuses
docker compose -f docker-compose.prod.yml ps
```
