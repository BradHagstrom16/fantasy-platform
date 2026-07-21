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

# Non-fatal steps below record a warning here instead of aborting. The final
# summary reads this: a deploy that printed a warning must not also print
# "App is live" and exit 0, or the warning is decoration.
deploy_warnings=0

# The unit file used to be installed by a manual `sudo cp` documented only in
# its own header, so edits to deploy/fantasy-platform.service silently never
# reached the server: the --timeout 120 fix committed 2026-06-11 was still not
# live on 2026-07-21, leaving prod on gunicorn's 30s default. Sync it here.
# Deliberately non-fatal: this script runs under `set -e`, and aborting here
# would leave migrations applied but the app never restarted — a worse state
# than deploying with a stale unit. Warn loudly and carry on instead.
echo "==> Syncing systemd unit..."
# Installed via write-to-temp + atomic rename rather than a direct copy over the
# live path. A copy truncates the destination first, so an interrupted write
# leaves a unit that is still valid INI but missing ExecStart= — systemd
# refuses to start it, and this is the file that decides whether the app comes
# up at all, so the breakage stays latent until the next reboot or deploy.
# rename(2) within the same directory is atomic: the live path is either the
# old unit or the new one, never a half-written one. The .new.$$ suffix is not
# a unit type systemd recognises, so a leftover temp is ignored rather than
# loaded. Mode is pinned at 644 root:root rather than inherited from the
# ambient umask — note this means a deliberate hand-tightening to e.g. 640
# would be reverted on the next deploy.
unit_live=/etc/systemd/system/fantasy-platform.service
unit_tmp="$unit_live.new.$$"
# Without this, an interrupted run (dropped SSH -> SIGHUP) between the install
# and the rename strands a root-owned temp in /etc/systemd/system/ that the
# deploy user cannot remove.
trap '[ -e "$unit_tmp" ] && sudo rm -f "$unit_tmp" 2>/dev/null || true' EXIT INT TERM HUP
# Content alone is not enough to call the unit correct. systemd runs this file
# as root, so a world-writable or non-root-owned copy is a privilege-escalation
# path — and a content-only check would report "unchanged" forever while the
# metadata stayed wrong. Compare both. (GNU stat; this script only ever runs on
# the Ubuntu droplet.) Absence and stat *failure* are distinguished on purpose:
# both yield empty metadata, but only the first is expected. Collapsing them
# would let a stat that breaks for any other reason silently retire the
# ownership check above while the deploy still reported success.
if [ -e "$unit_live" ]; then
    if ! unit_meta=$(stat -c '%a %U:%G' "$unit_live" 2>/dev/null); then
        unit_meta=""
        deploy_warnings=$((deploy_warnings + 1))
        echo "    !! WARNING: unit exists but stat failed — cannot verify mode/owner." >&2
        echo "    !! Check by hand: stat -c '%a %U:%G' $unit_live" >&2
    fi
else
    unit_meta=""
fi
diff -q deploy/fantasy-platform.service "$unit_live" >/dev/null 2>&1 && unit_same=1 || unit_same=0
if [ "$unit_same" = 1 ] && [ "$unit_meta" = "644 root:root" ]; then
    echo "    unit unchanged"
else
    if [ -n "$unit_meta" ] && [ "$unit_meta" != "644 root:root" ]; then
        echo "    unit metadata is '$unit_meta', expected '644 root:root' — repairing"
    fi
    # Validate the *repo* file before it lands, not the installed one after.
    # `daemon-reload` exits 0 even for a unit it cannot load — it only logs — so
    # a typo'd ExecStart= or a bad directive would sail past the reload and only
    # surface as a failed restart, with migrations already applied and the
    # service down. Gating the install means the worst case is keeping the
    # known-good live unit, which is exactly the pre-sync status quo.
    if sudo systemd-analyze verify deploy/fantasy-platform.service; then
        if sudo install -m 644 -o root -g root deploy/fantasy-platform.service "$unit_tmp" \
           && sudo mv -f "$unit_tmp" "$unit_live"; then
            echo "    unit installed (644 root:root)"
        else
            sudo rm -f "$unit_tmp" 2>/dev/null || true
            deploy_warnings=$((deploy_warnings + 1))
            echo "    !! WARNING: could not install the unit; continuing with the STALE one." >&2
            echo "    !! Fix with: sudo install -m 644 -o root -g root \\" >&2
            echo "    !!             deploy/fantasy-platform.service $unit_live" >&2
        fi
    else
        deploy_warnings=$((deploy_warnings + 1))
        echo "    !! WARNING: deploy/fantasy-platform.service failed validation (above)." >&2
        echo "    !! NOT installing it; keeping the current live unit. Fix the repo file." >&2
    fi
fi

# Unconditional, and deliberately NOT chained to the install above. If the
# install were to succeed while the reload failed, /etc would already match the
# repo, so every later deploy would take the "unit unchanged" branch and skip
# the reload forever — systemd would keep serving its old in-memory definition
# with no signal that anything was wrong. Reloading on every deploy makes a
# transient failure self-heal on the next run. sudo is required for the restart
# below regardless, so this costs no extra credential prompt.
if sudo systemctl daemon-reload; then
    echo "    systemd reloaded"
else
    deploy_warnings=$((deploy_warnings + 1))
    echo "    !! WARNING: daemon-reload failed — systemd is still running its" >&2
    echo "    !! previously loaded unit definition, even if the file on disk is current." >&2
    echo "    !! Fix with: sudo systemctl daemon-reload && sudo systemctl restart fantasy-platform" >&2
fi

echo "==> Restarting application..."
sudo systemctl restart fantasy-platform

# The unit declares no Type=, so it is Type=simple: systemd reports the restart
# as successful the moment the fork succeeds, whether or not gunicorn survives
# the next second. A bad flag, an import error or a malformed .env all exit
# non-zero *after* `restart` has already returned 0. Settle past RestartSec=5
# so a crash-loop is caught in `activating` rather than a momentary `active`.
echo "==> Verifying the service came up..."
sleep 6
if sudo systemctl is-active --quiet fantasy-platform; then
    echo "    service is active"
else
    echo "!! DEPLOY FAILED: fantasy-platform is not running after restart." >&2
    echo "!! Read the reason with: sudo journalctl -u fantasy-platform -n 50 --no-pager" >&2
    exit 1
fi

if [ "$deploy_warnings" -gt 0 ]; then
    echo "!! Done, but with $deploy_warnings warning(s) above — the app is running," >&2
    echo "!! on a configuration that is NOT fully in sync with the repo. Scroll up." >&2
    exit 1
fi

echo "==> Done. App is live."
