# Production Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Phase 1 (Tasks 1–9)** is for Claude Code — run after `/clear`.
> **Phases 2–6 (Tasks 10–27)** are manual steps for Brad. Exact commands are provided for every step.

**Goal:** Deploy the fantasy-platform Flask app to a live production environment on DigitalOcean with Managed PostgreSQL, Nginx, Gunicorn, and Cloudflare SSL.

**Architecture:** DigitalOcean Droplet (Ubuntu 24.04, 2GB RAM) runs Nginx as reverse proxy in front of Gunicorn (3 workers) communicating over a Unix socket. Cloudflare handles DNS and SSL via an Origin Certificate. DO Managed PostgreSQL connects over a private VPC. Sync jobs run as Linux cron entries on the Droplet.

**Tech Stack:** Flask, Gunicorn, Nginx, systemd, PostgreSQL (psycopg2), Cloudflare, Ubuntu 24.04 LTS.

---

## Sequencing note (added 2026-04-28, post-pause)

Brad paused this plan after completing Phase 2 Task 10. Resume sequence:

1. Finish **Spec B — CCC home redesign** (`docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`) and merge to `main`.
2. Finish **Spec C — World Cup reskin** (next brainstorm) and merge to `main`.
3. Source / build a sports-data API integration for live World Cup scores (out of scope for B and C).
4. Resume this plan at **Task 11** and continue through Task 27.

Spec B adds one new cron entry (`flask worldcup snapshot-ranks`) which has been **already woven into Task 25's cron schedule below** — no separate task needed. If Spec C or the API work introduces additional infra requirements, append them to the appropriate task here at that time.

**Snapshot timing tradeoff to know about:** the snapshot infra collects rank-history daily once the production cron is live. If this plan resumes only shortly before WC kickoff (June 11), the live-state sparkline on the home page will start with an empty/flat line and accumulate real data from the first cron run forward. The dossier copy handles this honestly ("tracking starts {date}") so the launch-day experience is acceptable either way — but earlier production resume = richer sparkline at launch.

---

## Files Created / Modified

| File | Action | Purpose |
|---|---|---|
| `config.py` | Modify | Add SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY to ProductionConfig |
| `requirements.txt` | Modify | Add gunicorn, psycopg2-binary |
| `.env.example` | Modify | Add SITE_URL, correct DATABASE_URL placeholder |
| `app.py` | Modify | Add ProxyFix middleware so Flask sees HTTPS behind Cloudflare |
| `deploy.sh` | Create | One-command deploy script (git pull → pip install → db upgrade → restart) |
| `deploy/nginx.conf` | Create | Nginx site config template (copy to server during setup) |
| `deploy/fantasy-platform.service` | Create | systemd unit file template (copy to server during setup) |

---

## Phase 1: Code Changes (Claude Code)

### Task 1: Audit LIKE queries for Postgres compatibility

Postgres `LIKE` is case-sensitive; SQLite `LIKE` is not. Any query using `.like()` that was intended to be case-insensitive must use `.ilike()` in Postgres.

**Files:**
- Search: `games/`, `core/`, `models/`

- [ ] **Step 1: Search for `.like(` calls**

```bash
grep -rn "\.like(" games/ core/ models/ --include="*.py"
```

Expected output: list of files and line numbers. If none found, record "No .like() calls found" and skip to Task 2.

- [ ] **Step 2: For each result, check intent**

For each match, read the surrounding context. Ask: should this match regardless of case? If yes, replace `.like(` with `.ilike(`. If it is intentionally case-sensitive (e.g., matching exact slugs), leave it.

- [ ] **Step 3: Search for raw LIKE in any string queries**

```bash
grep -rn "LIKE\|like " games/ core/ models/ --include="*.py" | grep -v "\.like\|\.ilike\|# "
```

Review any hits for the same case-sensitivity issue.

- [ ] **Step 4: Commit if any changes were made**

```bash
git add -p
git commit -m "fix: replace .like() with .ilike() for Postgres case-insensitive queries"
```

If no changes were needed, skip the commit.

---

### Task 2: Harden ProductionConfig in config.py

**Files:**
- Modify: `config.py:56-58`

- [ ] **Step 1: Open config.py and locate ProductionConfig**

It is at line 56:
```python
class ProductionConfig(Config):
    DEBUG = False
```

- [ ] **Step 2: Add session cookie security flags**

Replace the existing `ProductionConfig` block with:

```python
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
```

- [ ] **Step 3: Verify the change looks correct**

```bash
grep -A 5 "class ProductionConfig" config.py
```

Expected output:
```
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
```

- [ ] **Step 4: Run the test suite to verify nothing is broken**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass (119 tests).

---

### Task 3: Add gunicorn and psycopg2-binary to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the two production dependencies**

Append to `requirements.txt`:

```
gunicorn==23.0.0
psycopg2-binary==2.9.10
```

- [ ] **Step 2: Install locally to verify the versions resolve**

```bash
venv/bin/pip install gunicorn==23.0.0 psycopg2-binary==2.9.10
```

Expected: both install without error.

- [ ] **Step 3: Verify the file**

```bash
cat requirements.txt
```

Expected: file ends with the two new lines.

---

### Task 4: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Replace the entire file contents**

```
# Flask
SECRET_KEY=change-this-to-a-random-64-char-string
ENVIRONMENT=development

# Database
# Development (default): SQLite
# DATABASE_URL=sqlite:///instance/fantasy_platform.db
# Production: set this to your DO Managed Postgres connection string
# DATABASE_URL=postgresql://doadmin:<password>@<host>.db.ondigitalocean.com:25060/defaultdb?sslmode=require

# Timezone
PLATFORM_TIMEZONE=America/Chicago

# Site URL (used in password-reset emails and other outbound links)
# Development:
SITE_URL=http://localhost:5000
# Production: set to your actual domain
# SITE_URL=https://yourdomain.com

# Email (Gmail SMTP for reminders and password resets)
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Golf Pick 'Em
SEASON_YEAR=2026
ENTRY_FEE=25
SYNC_MODE=standard
FIXED_DEADLINE_HOUR_CT=7
SLASHGOLF_API_KEY=your-rapidapi-key-here

# CFB Survivor Pool
ODDS_API_KEY=
CFB_ENTRY_FEE=25
CFB_SEASON_YEAR=2026
```

- [ ] **Step 2: Verify the file**

```bash
cat .env.example
```

Expected: file matches the above.

---

### Task 5: Add ProxyFix to app.py

ProxyFix tells Flask to trust the `X-Forwarded-Proto: https` header that Cloudflare sends, so `SESSION_COOKIE_SECURE` and `url_for(_external=True)` work correctly.

**Files:**
- Modify: `app.py:7` (import block) and `app.py:111` (before `return app`)

- [ ] **Step 1: Add the import**

In `app.py`, add `ProxyFix` to the import block (after the existing imports, before `from config import config`):

```python
from werkzeug.middleware.proxy_fix import ProxyFix
```

The import block should look like:

```python
import logging
import os

import click
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from extensions import db, migrate, login_manager, csrf, limiter
```

- [ ] **Step 2: Apply ProxyFix before the return statement**

In `create_app()`, add two lines directly before `return app` (currently at line 112):

```python
    # Trust one level of proxy headers (Cloudflare → Nginx → Gunicorn)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app
```

- [ ] **Step 3: Run the test suite to verify nothing is broken**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass.

---

### Task 6: Write deploy.sh

**Files:**
- Create: `deploy.sh` (project root)

- [ ] **Step 1: Create the file**

```bash
#!/bin/bash
# Run this on the server to deploy a new version of the app.
# Usage: ./deploy.sh
set -e

cd /home/deploy/fantasy-platform

echo "==> Pulling latest code..."
git pull

echo "==> Installing/updating Python dependencies..."
venv/bin/pip install -r requirements.txt --quiet

echo "==> Applying database migrations..."
FLASK_APP=app.py venv/bin/flask db upgrade

echo "==> Restarting application..."
sudo systemctl restart fantasy-platform

echo "==> Done. App is live."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x deploy.sh
```

- [ ] **Step 3: Verify**

```bash
head -5 deploy.sh && ls -l deploy.sh
```

Expected: file starts with `#!/bin/bash` and has `-rwxr-xr-x` permissions.

---

### Task 7: Write deploy/nginx.conf

**Files:**
- Create: `deploy/nginx.conf`

- [ ] **Step 1: Create the deploy directory and nginx config**

```bash
mkdir -p deploy
```

File contents for `deploy/nginx.conf`:

```nginx
# Fantasy Sports Platform — Nginx site config
# Replace every instance of "yourdomain.com" with your actual domain before use.
# Install: sudo cp /home/deploy/fantasy-platform/deploy/nginx.conf /etc/nginx/sites-available/fantasy-platform
# Enable: sudo ln -s /etc/nginx/sites-available/fantasy-platform /etc/nginx/sites-enabled/

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/ssl/cloudflare/cert.pem;
    ssl_certificate_key /etc/ssl/cloudflare/key.pem;

    # Serve static files directly — Gunicorn never sees these requests
    location /static/ {
        alias /home/deploy/fantasy-platform/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy all other requests to Gunicorn via Unix socket
    location / {
        proxy_pass         http://unix:/run/fantasy-platform/gunicorn.sock;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}
```

- [ ] **Step 2: Verify the file exists**

```bash
cat deploy/nginx.conf
```

---

### Task 8: Write deploy/fantasy-platform.service

**Files:**
- Create: `deploy/fantasy-platform.service`

- [ ] **Step 1: Create the systemd unit file**

File contents for `deploy/fantasy-platform.service`:

```ini
# Fantasy Sports Platform — systemd service for Gunicorn
# Install: sudo cp /home/deploy/fantasy-platform/deploy/fantasy-platform.service /etc/systemd/system/
# Enable:  sudo systemctl daemon-reload && sudo systemctl enable fantasy-platform
# Control: sudo systemctl start|stop|restart|status fantasy-platform

[Unit]
Description=Fantasy Sports Platform (Gunicorn)
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/fantasy-platform
EnvironmentFile=/home/deploy/fantasy-platform/.env
RuntimeDirectory=fantasy-platform
ExecStart=/home/deploy/fantasy-platform/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/fantasy-platform/gunicorn.sock \
    --umask 007 \
    wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Verify the file exists**

```bash
cat deploy/fantasy-platform.service
```

---

### Task 9: Commit all Phase 1 changes

- [ ] **Step 1: Stage all changes**

```bash
git add config.py requirements.txt .env.example app.py deploy.sh deploy/nginx.conf deploy/fantasy-platform.service
```

- [ ] **Step 2: Verify what's staged**

```bash
git diff --cached --stat
```

Expected: 7 files changed.

- [ ] **Step 3: Run the full test suite one final time**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(deploy): add production deployment config and hardening

- Add gunicorn + psycopg2-binary to requirements.txt
- Harden ProductionConfig with SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE
- Add ProxyFix middleware for Cloudflare X-Forwarded-Proto handling
- Add deploy.sh, deploy/nginx.conf, deploy/fantasy-platform.service
- Update .env.example with production DATABASE_URL and SITE_URL"
```

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```

---

## Phase 2: Infrastructure Provisioning (Brad)

### Task 10: Create a DigitalOcean account and Droplet

- [x] **Step 1: Create a DigitalOcean account**

Go to https://digitalocean.com and sign up. You'll need a credit card. You get $200 free credit if you use a referral link.

- [x] **Step 2: Prepare an SSH key on your Mac**

SSH keys let you log in without typing a password, and Task 13 relies on having one. In a terminal on your Mac, check whether you already have a key:

```bash
ls ~/.ssh/id_ed25519.pub 2>/dev/null || ls ~/.ssh/id_rsa.pub 2>/dev/null
```

If you see a file path, you already have a key — skip ahead. If the command prints nothing, generate one:

```bash
ssh-keygen -t ed25519 -C "bhagstrom0@gmail.com"
```

Press Enter at each prompt to accept the defaults (an empty passphrase is fine for a solo setup; set one if you want extra security — you'll be asked for it each time you SSH).

Print the public key so you can copy it:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire output (one line starting with `ssh-ed25519`).

- [x] **Step 3: Create a Droplet**

In the DigitalOcean dashboard:
1. Click **Create → Droplets**
2. **Region:** Choose the one closest to you (e.g., New York or San Francisco)
3. **Image:** Ubuntu 24.04 LTS x64
4. **Size:** Basic → Regular (SSD) → **$12/mo** (2 GB RAM / 1 vCPU / 50 GB SSD)
5. **Authentication:** Choose **SSH Key** → **New SSH Key**. Paste the public key you copied in Step 2. Name it `my-mac`. Click **Add SSH Key**. Make sure the new key is checked under "Choose authentication method."
6. **Hostname:** `fantasy-platform`
7. Click **Create Droplet**

- [x] **Step 4: Copy the Droplet's IP address**

After creation, you'll see your Droplet's public IP address (e.g., `143.110.152.42`). Save it — you'll need it throughout the setup.

---

### Task 11: Create a DO Managed PostgreSQL cluster

- [ ] **Step 1: Create the database**

In the DigitalOcean dashboard:
1. Click **Create → Databases**
2. **Database engine:** PostgreSQL (latest version — 16 or 17)
3. **Region:** Choose the **same region as your Droplet** (important for private VPC)
4. **Machine type:** Basic → $15/mo (1 GB RAM / 1 vCPU / 10 GB SSD)
5. **Cluster name:** `fantasy-platform-db`
6. Click **Create Database Cluster**

Creation takes 2–3 minutes.

- [ ] **Step 2: Restrict access to your Droplet only**

Once the cluster is created:
1. Go to the database's **Settings** tab
2. Under **Trusted Sources**, click **Add trusted source**
3. Select your `fantasy-platform` Droplet from the dropdown
4. Click **Save**

This ensures the DB port is only reachable from your Droplet, not the public internet.

- [ ] **Step 3: Copy the connection string**

1. Go to the database's **Overview** tab
2. Under **Connection Details**, select **Connection string** from the dropdown
3. Copy the full string — it looks like:
   ```
   postgresql://doadmin:<password>@<host>.db.ondigitalocean.com:25060/defaultdb?sslmode=require
   ```
4. Save it securely — you'll paste it into `.env` on the server.

---

### Task 12: Register a domain

- [ ] **Step 1: Choose and register a domain**

Go to https://www.namecheap.com (or https://www.cloudflare.com/products/registrar/ — Cloudflare charges at-cost with no markup).

Search for your desired name. Suggested TLDs for a sports platform: `.com`, `.app`, `.io`, `.gg`.

Purchase the domain (~$9–15/yr).

- [ ] **Step 2: Note your domain name**

Save your domain name (e.g., `commissionersclub.com`) — you'll use it in every step below that says `yourdomain.com`.

---

## Phase 3: Server Setup (Brad via SSH)

> **How to open a terminal:**
> - **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter.
> - Every command below is typed at the `$` prompt and followed by Enter.
> - When a command asks for a password, type it and press Enter (the characters won't appear — that's normal).

### Task 13: First login and create a deploy user

- [ ] **Step 1: SSH into the server as root**

In your terminal, run (replace with your actual IP):

```bash
ssh root@143.110.152.42
```

Type `yes` when asked about the fingerprint. If you set a passphrase on your SSH key (Task 10 Step 2), you'll be asked for it once per terminal session.

You are now on the server. Your prompt will look like `root@fantasy-platform:~#`.

- [ ] **Step 2: Update the system**

```bash
apt update && apt upgrade -y
```

This takes 1–2 minutes. Wait for it to finish.

- [ ] **Step 3: Create a deploy user**

```bash
adduser deploy
```

You'll be prompted to set a password. Choose a strong one and save it. Press Enter to skip the other fields (Full Name, Room Number, etc.).

- [ ] **Step 4: Give deploy user sudo access**

```bash
usermod -aG sudo deploy
```

- [ ] **Step 5: Copy your SSH key to the deploy user**

Your Mac's public key was added to root's `~/.ssh/authorized_keys` automatically during Droplet creation (Task 10 Step 3). Copy it to the deploy user so you can SSH in as deploy too:

```bash
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

- [ ] **Step 6: Verify you can SSH as deploy**

Open a **new** terminal window on your Mac and run:

```bash
ssh deploy@143.110.152.42
```

You should log in without entering a password (or with just your key's passphrase, if you set one). Your prompt will look like `deploy@fantasy-platform:~$`.

**From this point forward, all server commands are run as the `deploy` user, not root.**

---

### Task 14: Set up the firewall

Run these commands in your deploy SSH session:

- [ ] **Step 1: Allow SSH, HTTP, and HTTPS**

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
```

- [ ] **Step 2: Enable the firewall**

```bash
sudo ufw enable
```

Type `y` when prompted.

- [ ] **Step 3: Verify the rules**

```bash
sudo ufw status
```

Expected output:
```
Status: active

To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
Nginx Full                 ALLOW       Anywhere
OpenSSH (v6)               ALLOW       Anywhere (v6)
Nginx Full (v6)            ALLOW       Anywhere (v6)
```

- [ ] **Step 4: Install fail2ban to block SSH brute-force attempts**

fail2ban watches auth logs and temporarily IP-bans addresses that fail too many SSH logins in a row. It's a standard hardening step for any public-facing VPS.

```bash
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
```

Verify it's running:

```bash
sudo systemctl status fail2ban --no-pager | head -5
```

Expected: `Active: active (running)`.

---

### Task 15: Install system dependencies

- [ ] **Step 1: Install Nginx and Git**

```bash
sudo apt install -y nginx git
```

- [ ] **Step 2: Add the deadsnakes PPA for Python 3.13**

Ubuntu 24.04 ships Python 3.12 by default. Your app requires 3.13.

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
```

Press Enter when prompted.

```bash
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
```

- [ ] **Step 3: Verify Python version**

```bash
python3.13 --version
```

Expected output: `Python 3.13.x`

- [ ] **Step 4: Allow Nginx to access the Gunicorn socket**

Nginx runs as `www-data`. Gunicorn runs as `deploy`. The socket file needs to be readable by both.

```bash
sudo usermod -aG deploy www-data
```

- [ ] **Step 5: Enable automatic security updates**

Ubuntu's `unattended-upgrades` package applies security patches without manual intervention — critical for a server that runs unattended for months.

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

When prompted "Automatically download and install stable updates?", select **Yes**. This writes `/etc/apt/apt.conf.d/20auto-upgrades` so the system applies security-only updates daily.

---

### Task 16: Clone the repo and set up the Python environment

- [ ] **Step 1: Clone the repository**

```bash
cd /home/deploy
git clone https://github.com/BradHagstrom16/fantasy-platform.git
cd fantasy-platform
```

- [ ] **Step 2: Create a Python 3.13 virtual environment**

```bash
python3.13 -m venv venv
```

- [ ] **Step 3: Install Python dependencies**

```bash
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

This takes 1–2 minutes. Expected: no errors.

- [ ] **Step 4: Verify Gunicorn installed**

```bash
venv/bin/gunicorn --version
```

Expected output: `gunicorn (version 23.0.0)`

---

### Task 17: Create the production .env file

- [ ] **Step 1: Generate a SECRET_KEY**

```bash
python3.13 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output — it's your `SECRET_KEY`.

- [ ] **Step 2: Create the .env file**

```bash
nano /home/deploy/fantasy-platform/.env
```

Paste the following, filling in every value marked with `<...>`:

```bash
FLASK_APP=app.py
ENVIRONMENT=production
SECRET_KEY=<paste the token_hex output from Step 1>
DATABASE_URL=<paste the DO Postgres connection string from Task 11 Step 3>
SLASHGOLF_API_KEY=<your RapidAPI key>
ODDS_API_KEY=<your Odds API key>
EMAIL_ADDRESS=bhagstrom0@gmail.com
EMAIL_PASSWORD=<your Gmail app password>
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SITE_URL=https://<your-actual-domain>
PLATFORM_TIMEZONE=America/Chicago
```

> **How to save in nano:** Press `Ctrl+X`, then `Y`, then `Enter`.

> **Note:** Replace `<your-actual-domain>` (Task 12) in `SITE_URL` before saving — password-reset emails and any other outbound links will embed this value, so it must be your live domain (e.g., `https://commissionersclub.com`).

- [ ] **Step 3: Lock down the file permissions**

```bash
chmod 600 /home/deploy/fantasy-platform/.env
```

This ensures only the `deploy` user can read it.

- [ ] **Step 4: Verify the file is locked**

```bash
ls -la /home/deploy/fantasy-platform/.env
```

Expected: `-rw-------` (only owner can read/write).

---

### Task 18: Install and enable the Nginx config

- [ ] **Step 1: Open the Nginx config from the repo**

```bash
cat /home/deploy/fantasy-platform/deploy/nginx.conf
```

You'll see `yourdomain.com` as a placeholder. You need to replace it with your actual domain.

- [ ] **Step 2: Copy it to the Nginx sites directory with your domain substituted**

Replace `commissionersclub.com` in the sed command below with **your actual domain** from Task 12:

```bash
sudo sed 's/yourdomain.com/commissionersclub.com/g' \
    /home/deploy/fantasy-platform/deploy/nginx.conf \
    > /tmp/fantasy-platform.conf
sudo cp /tmp/fantasy-platform.conf /etc/nginx/sites-available/fantasy-platform
```

After the copy, confirm there are no residual `yourdomain.com` strings:

```bash
grep -n "yourdomain\.com" /etc/nginx/sites-available/fantasy-platform || echo "OK — no placeholders remain"
```

- [ ] **Step 3: Enable the site**

```bash
sudo ln -s /etc/nginx/sites-available/fantasy-platform /etc/nginx/sites-enabled/
```

- [ ] **Step 4: Remove the default Nginx site**

```bash
sudo rm /etc/nginx/sites-enabled/default
```

- [ ] **Step 5: Test the Nginx config**

```bash
sudo nginx -t
```

Expected output:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**Do not restart Nginx yet** — you need the Cloudflare Origin Certificate installed first (Task 22). Starting Nginx with no cert at `/etc/ssl/cloudflare/cert.pem` will fail the `listen 443 ssl` block.

---

### Task 19: Install and enable the systemd service

- [ ] **Step 1: Copy the service file to systemd**

```bash
sudo cp /home/deploy/fantasy-platform/deploy/fantasy-platform.service \
    /etc/systemd/system/fantasy-platform.service
```

- [ ] **Step 2: Reload systemd so it sees the new file**

```bash
sudo systemctl daemon-reload
```

- [ ] **Step 3: Enable the service to start on boot**

```bash
sudo systemctl enable fantasy-platform
```

Expected output: `Created symlink /etc/systemd/system/multi-user.target.wants/fantasy-platform.service → /etc/systemd/system/fantasy-platform.service`

---

### Task 20: Run database migration and create admin user

- [ ] **Step 1: Create the log directory for cron jobs**

```bash
sudo mkdir -p /var/log/fantasy
sudo chown deploy:deploy /var/log/fantasy
```

- [ ] **Step 2: Run the database migration**

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: Alembic applies all migrations. No errors.

> **Why the `ENVIRONMENT=production` prefix?** `migrations/env.py` reads the database URL from whichever config class `create_app()` loads. Explicitly setting `ENVIRONMENT=production` guarantees migrations run against the Postgres `DATABASE_URL` from `.env` and never against a stray dev SQLite. The deploy.sh script and systemd unit use the same belt-and-suspenders approach.

- [ ] **Step 3: Create your admin user**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask create-admin
```

You'll be prompted for username, email, and password. This is your platform admin account.

---

### Task 20.5: Initialize the production database schema

- [ ] **Step 1: Run migrations against the production database**

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: Alembic applies all migrations in order. You will see output like `Running upgrade -> abc123, ...` for each migration. No errors.

- [ ] **Step 2: Verify the tables exist**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
```

Then in the shell:

```python
from extensions import db
from sqlalchemy import inspect
print(inspect(db.engine).get_table_names())
exit()
```

Expected: a list of table names including `user`, `golf_enrollment`, `cfb_enrollment`, `world_cup_enrollment`, and others. If you see an empty list, something is wrong with `DATABASE_URL` in your `.env`.

---

## Phase 4: DNS and SSL (Brad)

### Task 21: Set up Cloudflare DNS

- [ ] **Step 1: Create a Cloudflare account**

Go to https://cloudflare.com and sign up (free).

- [ ] **Step 2: Add your domain to Cloudflare**

1. In the Cloudflare dashboard, click **Add a Site**
2. Enter your domain name (e.g., `commissionersclub.com`)
3. Choose the **Free** plan
4. Cloudflare will scan your existing DNS records — click **Continue**

- [ ] **Step 3: Add an A record pointing to your Droplet**

In the Cloudflare DNS editor:
1. Click **Add record**
2. Type: **A**
3. Name: `@` (this means the root domain, `commissionersclub.com`)
4. IPv4 address: your Droplet's IP (e.g., `143.110.152.42`)
5. Proxy status: **Proxied** (orange cloud — leave it ON)
6. Click **Save**

Repeat for a `www` record:
1. Add record → Type: **A** → Name: `www` → IPv4: same Droplet IP → Proxied ON → Save

- [ ] **Step 4: Update your domain's nameservers**

Cloudflare will show you two nameservers like:
```
amy.ns.cloudflare.com
bob.ns.cloudflare.com
```

Log into your domain registrar (Namecheap or wherever you bought the domain) and replace the nameservers with these two Cloudflare ones. The exact steps vary by registrar — look for "Nameservers" in your domain settings.

DNS propagation takes 5–30 minutes.

---

### Task 22: Generate and install a Cloudflare Origin Certificate

This is a free SSL certificate that Cloudflare generates for you. It's valid for 15 years and tells Nginx to encrypt traffic between Cloudflare and your server.

- [ ] **Step 1: Generate the certificate**

In Cloudflare dashboard:
1. Go to **SSL/TLS → Origin Server**
2. Click **Create Certificate**
3. Leave all defaults (RSA 2048, hostnames auto-filled, 15-year validity)
4. Click **Create**

Two text boxes appear: **Origin Certificate** and **Private Key**. **Do not close this page** until you've saved both.

- [ ] **Step 2: Copy the certificate to the server**

On the server, create the directory and file:

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo nano /etc/ssl/cloudflare/cert.pem
```

In nano: paste the entire **Origin Certificate** text (starts with `-----BEGIN CERTIFICATE-----`, ends with `-----END CERTIFICATE-----`).

Save: `Ctrl+X` → `Y` → `Enter`

- [ ] **Step 3: Copy the private key to the server**

```bash
sudo nano /etc/ssl/cloudflare/key.pem
```

Paste the entire **Private Key** text (starts with `-----BEGIN PRIVATE KEY-----`).

Save: `Ctrl+X` → `Y` → `Enter`

- [ ] **Step 4: Lock down the private key**

```bash
sudo chmod 600 /etc/ssl/cloudflare/key.pem
sudo chmod 644 /etc/ssl/cloudflare/cert.pem
```

- [ ] **Step 5: Set Cloudflare SSL mode to Full (strict)**

In Cloudflare dashboard → **SSL/TLS → Overview** → set encryption mode to **Full (strict)**.

> Cloudflare Origin Certificates are signed by Cloudflare's internal CA, which Cloudflare trusts in "Full (strict)" mode. This gives end-to-end TLS validation all the way to the origin — strictly better than plain "Full", which accepts any origin certificate (including expired or self-signed ones). Do **not** pick "Flexible" — it leaves the Cloudflare → origin hop unencrypted.

---

## Phase 5: Start the App and First Smoke Test (Brad)

### Task 23: Start the app

- [ ] **Step 1: Start the Gunicorn service**

```bash
sudo systemctl start fantasy-platform
```

- [ ] **Step 2: Check the service is running**

```bash
sudo systemctl status fantasy-platform
```

Expected: the output includes `Active: active (running)`. If you see `failed`, run `journalctl -u fantasy-platform -n 50` to see the error log.

- [ ] **Step 3: Verify the socket file was created**

```bash
ls -la /run/fantasy-platform/gunicorn.sock
```

Expected: the socket file exists with permissions `srw-rw----` (or similar — just needs to exist).

- [ ] **Step 4: Start (or restart) Nginx**

```bash
sudo systemctl restart nginx
sudo systemctl status nginx
```

Expected: `Active: active (running)`.

---

### Task 24: Smoke test the live site

Wait 10 minutes for DNS to propagate after Task 21 before running these tests.

- [ ] **Step 1: Test via browser**

Open a browser and go to `https://yourdomain.com`. You should see the Commissioner's Club homepage with a padlock icon in the browser bar (HTTPS).

- [ ] **Step 2: Test login**

Log in with the admin account you created in Task 20. You should reach the dashboard.

- [ ] **Step 3: Test the admin panel**

Navigate to `/admin`. Verify you can see the platform admin interface.

- [ ] **Step 4: Test a static asset loads**

Open DevTools (F12) → Network tab. Reload the page. Confirm that `/static/css/style.css` returns a 200 status. Nginx is serving it directly — if it works, the static file path is correct.

- [ ] **Step 5: Test HTTP → HTTPS redirect**

In your browser, go to `http://yourdomain.com` (plain HTTP). It should redirect to `https://yourdomain.com`.

---

### Task 25: Set up cron jobs

- [ ] **Step 1: Open the cron editor**

```bash
crontab -e
```

The first time you run this it may ask which editor to use — type `1` and press Enter to select `nano`.

- [ ] **Step 2: Paste the cron schedule at the bottom of the file**

```cron
# Fantasy Platform sync jobs — all times are UTC

# Golf — live leaderboard (every 5 min, 11:00–23:59 UTC = 6am–6:59pm CDT)
*/5 11-23 * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask golf sync-run --mode live >> /var/log/fantasy/golf-live.log 2>&1

# Golf — live leaderboard continued (every 5 min, 00:00–03:00 UTC = 7pm–10pm CDT)
*/5 0-3 * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask golf sync-run --mode live >> /var/log/fantasy/golf-live.log 2>&1

# Golf — finalize results (daily at 05:00 UTC = midnight CDT)
0 5 * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask golf sync-run --mode results >> /var/log/fantasy/golf-results.log 2>&1

# CFB — fetch scores + auto-process (every 15 min)
*/15 * * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask cfb sync --mode scores >> /var/log/fantasy/cfb-scores.log 2>&1

# CFB — email reminders (Fri + Sat at 15:00 UTC = 10am CDT)
0 15 * * 5,6 cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask cfb sync --mode remind >> /var/log/fantasy/cfb-remind.log 2>&1

# World Cup — recalculate scores (every 10 min during tournament)
*/10 * * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup recalc >> /var/log/fantasy/worldcup-recalc.log 2>&1

# World Cup — daily rank snapshot at midnight CT (added by Spec B — CCC home redesign)
# 05:05 UTC = 23:05 CST (prior day, winter) / 00:05 CDT (summer); 5-min offset gives midnight match-result processing time to settle
# Powers the live-state dossier sparkline + week-delta on the home page
5 5 * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks >> /var/log/fantasy/worldcup-snapshot.log 2>&1
```

> **Snapshot backfill note (Spec B):** After the cron is verified loaded (Step 3 below), run the backfill helper once to seed the snapshot table so the sparkline isn't empty on Day 1:
> ```bash
> ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
> ```
> Best-effort backfill (all 7 backfilled days will share the current rank/score since we don't have historical data); real differentiation accumulates after the first nightly cron run.

Save: `Ctrl+X` → `Y` → `Enter`

- [ ] **Step 3: Verify cron is loaded**

```bash
crontab -l
```

Expected: the seven job entries are listed.

> **Tip:** When a game's season is over (e.g., World Cup ends), open `crontab -e` and add a `#` at the start of that job's line to disable it. Remove the `#` when the season begins again.

---

## Phase 6: Monitoring (Brad)

### Task 26: Set up UptimeRobot

- [ ] **Step 1: Create a free UptimeRobot account**

Go to https://uptimerobot.com and sign up (free tier: 50 monitors, 5-minute checks).

- [ ] **Step 2: Add a monitor**

1. Click **Add New Monitor**
2. Monitor type: **HTTP(s)**
3. Friendly name: `Fantasy Platform`
4. URL: `https://yourdomain.com`
5. Monitoring interval: **5 minutes**
6. Click **Create Monitor**

- [ ] **Step 3: Configure alert contacts**

In UptimeRobot → **My Settings → Alert Contacts**:
1. Add your email address (`bhagstrom0@gmail.com`)
2. Confirm the verification email UptimeRobot sends

You'll now receive an email any time the site goes down and when it comes back up.

- [ ] **Step 4: Set up DigitalOcean resource alerts**

In the DigitalOcean dashboard → **Monitoring → Alerts**:
1. Click **Create Alert Policy**
2. Add three alerts (repeat for each):

| Alert | Threshold | Why |
|---|---|---|
| CPU | > 80% for 5 min | App under sustained load |
| Memory | > 85% for 5 min | Possible memory leak |
| Disk | > 80% | DB or logs filling the drive |

For each: set the notification to your email and click **Save Alert Policy**.

---

## Ongoing: Deploying New Code

Every time you want to ship an update from your Mac:

**On your Mac:**
```bash
git push origin main
```

**Then SSH to the server:**
```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
./deploy.sh
```

That's it. The script pulls the new code, installs any new dependencies, applies any new migrations, and restarts the app.

---

## Troubleshooting Reference

| Symptom | Command to run | What to look for |
|---|---|---|
| App not responding | `sudo systemctl status fantasy-platform` | `Active: failed` → check next row |
| App crash details | `journalctl -u fantasy-platform -n 100` | Python traceback |
| Nginx error | `sudo nginx -t` | Config syntax error |
| Nginx logs | `sudo tail -f /var/log/nginx/error.log` | 502 Bad Gateway = socket issue |
| Cron job output | `tail -f /var/log/fantasy/golf-live.log` | Python errors from sync jobs |
| DB connection issue | Check `.env` `DATABASE_URL` value | Missing `?sslmode=require` |
