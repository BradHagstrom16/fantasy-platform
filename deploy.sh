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
elif sudo cp deploy/fantasy-platform.service /etc/systemd/system/fantasy-platform.service; then
    echo "    unit changed — installed"
else
    echo "    !! WARNING: could not install the unit; continuing with the STALE one." >&2
    echo "    !! Fix with: sudo cp deploy/fantasy-platform.service /etc/systemd/system/" >&2
fi

# Unconditional, and deliberately NOT chained to the copy above. If cp were to
# succeed while the reload failed, /etc would already match the repo, so every
# later deploy would take the "unit unchanged" branch and skip the reload
# forever — systemd would keep serving its old in-memory definition with no
# signal that anything was wrong. Reloading on every deploy makes a transient
# failure self-heal on the next run. sudo is required for the restart below
# regardless, so this costs no extra credential prompt.
if sudo systemctl daemon-reload; then
    echo "    systemd reloaded"
else
    echo "    !! WARNING: daemon-reload failed — systemd is still running its" >&2
    echo "    !! previously loaded unit definition, even if the file on disk is current." >&2
    echo "    !! Fix with: sudo systemctl daemon-reload && sudo systemctl restart fantasy-platform" >&2
fi

echo "==> Restarting application..."
sudo systemctl restart fantasy-platform

echo "==> Done. App is live."
