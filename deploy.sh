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
