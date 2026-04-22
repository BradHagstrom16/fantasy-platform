# Production Deployment Design
**Date:** 2026-04-21
**Status:** Approved

---

## Overview

Deploy the fantasy-platform Flask app to a live production environment using DigitalOcean (Droplet + Managed PostgreSQL), Nginx, Gunicorn, systemd, and Cloudflare. Target: private platform for friends and family, up to ~100 users.

---

## Infrastructure Topology

```
Internet
  │
  ▼
Cloudflare (DNS + SSL termination, free tier)
  │ HTTPS
  ▼
DigitalOcean Droplet — $12/mo
  ├── Nginx (reverse proxy, ports 80/443)
  │     └── /static/* served directly from disk
  └── Gunicorn (WSGI, Unix socket, 3 workers)
        └── Flask app (fantasy-platform)
              ├── Cron jobs via Linux crontab
              └── Gmail SMTP (email, unchanged)
  │
  │ Private VPC (no public internet exposure)
  ▼
DO Managed PostgreSQL — $15/mo
  └── Daily automated backups, 7-day point-in-time recovery (included)

Domain registrar: Namecheap or Cloudflare (~$12/yr)
  └── Nameservers → Cloudflare
```

**Droplet spec:** Basic, 2GB RAM / 1 vCPU / 50GB SSD, Ubuntu 24.04 LTS.

**Total cost:** ~$27/mo + ~$12/yr for domain.

---

## Application Layer

### Gunicorn
- Entry point: existing `wsgi.py` (`application = create_app()`) — no changes needed
- Workers: 3 (`2 × vCPU + 1`)
- Binding: Unix socket (`/run/fantasy-platform.sock`) — not a TCP port
- Managed by systemd (auto-start on boot, auto-restart on crash)

### Nginx
- Reverse proxy from ports 80/443 to the Gunicorn Unix socket
- Serves `static/` directory directly from disk — Gunicorn never processes static assets
- SSL termination handled by Cloudflare (full SSL mode); Nginx serves HTTP internally

### systemd
- Unit file: `/etc/systemd/system/fantasy-platform.service`
- Loads `.env` via `EnvironmentFile=`
- Control: `sudo systemctl start|stop|restart|status fantasy-platform`

### Deploy script (`deploy.sh`)
```bash
#!/bin/bash
set -e
cd /home/deploy/fantasy-platform
git pull
venv/bin/pip install -r requirements.txt
FLASK_APP=app.py venv/bin/flask db upgrade
sudo systemctl restart fantasy-platform
echo "Deploy complete."
```

---

## Database

### Engine
- DigitalOcean Managed PostgreSQL (Basic, 1GB RAM, 10GB SSD)
- Connected to Droplet via private VPC — DB port never exposed to public internet
- Connection string format:
  ```
  postgresql://doadmin:<password>@<host>.db.ondigitalocean.com:25060/defaultdb?sslmode=require
  ```

### Migration
- Schema: `FLASK_APP=app.py venv/bin/flask db upgrade` against Postgres — Alembic history is complete, no manual SQL
- Data: start fresh in production (dev SQLite data is not migrated); real users populate naturally
- First user: `flask create-admin` after `db upgrade`

### Backups
- Daily automated backups with 7-day point-in-time recovery — included in DO Managed Postgres price, no configuration required

### Postgres vs SQLite compatibility audit
- Audit all `LIKE` queries before launch — Postgres `LIKE` is case-sensitive, SQLite is not
- Audit any raw `TEXT` column comparisons used in filters

---

## Secrets & Configuration

### Storage
- Single `.env` file at `/home/deploy/fantasy-platform/.env`
- Permissions: `600` (readable only by the deploy user)
- Loaded by systemd `EnvironmentFile=` directive — never committed to git

### Production `.env` contents
```bash
FLASK_APP=app.py
ENVIRONMENT=production
SECRET_KEY=<64-char random string>
DATABASE_URL=postgresql://doadmin:...@...db.ondigitalocean.com:25060/defaultdb?sslmode=require
SLASHGOLF_API_KEY=...
ODDS_API_KEY=...
EMAIL_ADDRESS=bhagstrom0@gmail.com
EMAIL_PASSWORD=...
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SITE_URL=https://<yourdomain.com>
PLATFORM_TIMEZONE=America/Chicago
```

### Code change required before deployment
Add to `ProductionConfig` in `config.py`:
```python
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
```

---

## Cron Jobs

All jobs run as the `deploy` user via `crontab -e`. All times are UTC (server clock). CT = UTC−5 (CDT) or UTC−6 (CST).

Log directory: `/var/log/fantasy/` (created at setup, writable by deploy user).

```cron
# Golf — live leaderboard (every 5 min, 11:00–23:59 UTC = 6am–6:59pm CDT)
*/5 11-23 * * * cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask golf sync-run --mode live >> /var/log/fantasy/golf-live.log 2>&1
# Golf — live leaderboard continued (every 5 min, 00:00–03:00 UTC = 7pm–10pm CDT)
*/5 0-3 * * * cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask golf sync-run --mode live >> /var/log/fantasy/golf-live.log 2>&1

# Golf — finalize results (daily at 05:00 UTC = midnight CDT)
0 5 * * * cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask golf sync-run --mode results >> /var/log/fantasy/golf-results.log 2>&1

# CFB — fetch scores + auto-process (every 15 min)
*/15 * * * * cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask cfb sync --mode scores >> /var/log/fantasy/cfb-scores.log 2>&1

# CFB — email reminders (Fri + Sat at 15:00 UTC = 10am CDT)
0 15 * * 5,6 cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask cfb sync --mode remind >> /var/log/fantasy/cfb-remind.log 2>&1

# World Cup — recalculate scores (every 10 min during tournament)
*/10 * * * * cd /home/deploy/fantasy-platform && FLASK_APP=app.py venv/bin/flask worldcup recalc >> /var/log/fantasy/worldcup-recalc.log 2>&1
```

**Planned evolution — World Cup score ingestion:**
The `worldcup recalc` cron is a temporary polling pattern. When an external score feed is available, this will be replaced by an inbound webhook route (`POST /worldcup/admin/webhook/match-result` or similar). No infrastructure changes required — Nginx already accepts inbound POST requests. The cron entry is simply removed and the webhook route added to the blueprint.

---

## DNS, Domain, and SSL

### Steps (one-time)
1. Register domain at Namecheap or Cloudflare (~$9–15/yr depending on TLD)
2. Set domain nameservers to Cloudflare's nameservers
3. In Cloudflare dashboard: add `A` record → Droplet public IP, proxy enabled (orange cloud)
4. Cloudflare provisions SSL automatically — site is HTTPS from day one

### Cloudflare free tier benefits
- SSL/TLS (full mode)
- DDoS protection
- Bot filtering
- Traffic analytics

---

## Monitoring

| Tool | Purpose | Cost |
|---|---|---|
| UptimeRobot | Pings site every 5 min, emails on downtime | Free |
| DO Monitoring | CPU/memory/disk alerts on Droplet | Free (built-in) |
| `/var/log/fantasy/*.log` | Per-job cron output, tail for debugging | Free |

---

## Cost Summary

| Component | Cost |
|---|---|
| DO Droplet (2GB, Ubuntu 24.04) | $12/mo |
| DO Managed PostgreSQL | $15/mo |
| Cloudflare DNS + SSL | Free |
| UptimeRobot | Free |
| Domain | ~$12/yr |
| **Total** | **~$27/mo + $12/yr** |

---

## Out of Scope

- CI/CD pipeline (GitHub Actions auto-deploy) — manual `deploy.sh` is sufficient for this scale
- Celery / Redis background workers — Flask CLI cron is sufficient; revisit only if jobs need sub-minute frequency or concurrency
- Container orchestration (Docker, Kubernetes) — overkill for a private platform at this scale
- Read replicas or connection pooling (PgBouncer) — not needed at <100 users
