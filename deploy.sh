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
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade

# The unit file used to be installed by a manual `sudo cp` documented only in
# its own header, so edits to deploy/fantasy-platform.service silently never
# reached the server: the --timeout 120 fix committed 2026-06-12 was still not
# live on 2026-07-21, leaving prod on gunicorn's 30s default. Sync it here.
# Deliberately non-fatal: this script runs under `set -e`, and aborting here
# would leave migrations applied but the app never restarted — a worse state
# than deploying with a stale unit. Warn loudly and carry on instead.
echo "==> Syncing systemd unit..."
if diff -q deploy/fantasy-platform.service /etc/systemd/system/fantasy-platform.service >/dev/null 2>&1; then
    echo "    unit unchanged"
elif sudo cp deploy/fantasy-platform.service /etc/systemd/system/fantasy-platform.service \
     && sudo systemctl daemon-reload; then
    echo "    unit changed — installed and systemd reloaded"
else
    echo "    !! WARNING: could not install the unit; continuing with the STALE one." >&2
    echo "    !! Fix with: sudo cp deploy/fantasy-platform.service /etc/systemd/system/ \\" >&2
    echo "    !!           && sudo systemctl daemon-reload && sudo systemctl restart fantasy-platform" >&2
fi

echo "==> Restarting application..."
sudo systemctl restart fantasy-platform

echo "==> Done. App is live."
