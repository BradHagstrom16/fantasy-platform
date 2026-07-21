#!/bin/bash
# Run this on the server to deploy a new version of the app.
# Usage: ./deploy.sh
set -e

# Resolved before the cd below, because $0 is relative when this is invoked the
# documented way (./deploy.sh) and the cd would strand it. Used twice later: to
# notice that `git pull` rewrote this file, and to re-exec the new copy.
script_path="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

# sha256sum is coreutils (the droplet); shasum is the fallback the local test
# harness runs under on macOS. Both print "<hash>  <path>", and the path is
# identical between the two calls, so whole-line comparison is fine. A file that
# cannot be hashed at all reports a constant, which reads as "unchanged".
hash_self() {
    sha256sum "$script_path" 2>/dev/null \
        || shasum -a 256 "$script_path" 2>/dev/null \
        || echo "unhashable"
}

cd /home/deploy/fantasy-platform

# Non-fatal steps below record a warning here instead of aborting. The final
# summary reads this: a deploy that printed a warning must not also print
# "App is live" and exit 0, or the warning is decoration.
deploy_warnings=0

# Two overlapping deploys would run concurrent `flask db upgrade` against the
# same Postgres instance and concurrent `git pull` into the same checkout, so
# the lock has to wrap everything below including the pull. It lives beside the
# checkout rather than in /tmp (world-writable: any local user could pre-create
# the path and sit on it) and rather than inside the repo (would need a
# .gitignore entry). Nothing removes it — the lock is released when the process
# exits and its fds close; unlinking a lockfile others may already have open is
# how you get two holders at once.
# The usual flock caveat — a long-lived child inheriting fd 200 would hold the
# lock past our exit — does not bite here: every child this script spawns (git,
# pip, flask, sudo) is short-lived, and gunicorn is started by systemd via
# `systemctl restart`, so it is a child of PID 1 and never sees our fds.
lockfile=/home/deploy/.fantasy-platform-deploy.lock

# flock locks an open file *description* — not a path, not a process — and
# exec(2) preserves file descriptors. So the re-exec'd instance below inherits
# fd 200 with the lock still on it, and must NOT lock again: flock(2) is
# explicit that a request through a second open() of the same file "may be
# denied by a lock that the calling process has already placed via another file
# descriptor". Re-acquiring would deadlock the deploy against itself and blame
# its own PID. Verify the fd rather than assuming it: if it is somehow gone the
# lock went with it, and acquiring fresh is then the correct move.
if [ "${DEPLOY_REEXECED:-}" = 1 ] && { true >&200; } 2>/dev/null; then
    echo "==> Holding the deploy lock inherited across the restart (PID $$)."
elif ! command -v flock >/dev/null 2>&1; then
    deploy_warnings=$((deploy_warnings + 1))
    echo "!! WARNING: flock not found — running WITHOUT a concurrency lock." >&2
    echo "!! A second ./deploy.sh could run migrations at the same time as this one." >&2
    echo "!! Fix with: sudo apt-get install -y util-linux" >&2
elif ! { : >>"$lockfile"; } 2>/dev/null; then
    # Caught here rather than at the `exec` redirect below, which is fatal on
    # error and would abort with nothing but a bash "Permission denied".
    deploy_warnings=$((deploy_warnings + 1))
    echo "!! WARNING: cannot open $lockfile for writing —" >&2
    echo "!! running WITHOUT a concurrency lock. An earlier 'sudo ./deploy.sh'" >&2
    echo "!! leaves this file owned by root, which does exactly this." >&2
    echo "!! Fix with: sudo rm -f $lockfile" >&2
else
    # Append, not truncate: `>` empties the file at open — i.e. before we know
    # whether we won the race — wiping the current holder's PID out of it.
    exec 200>>"$lockfile"
    flock_rc=0
    flock -n 200 || flock_rc=$?
    # Exit 1 means contention and *only* contention: flock(1) reports a failed
    # -n acquisition with the -E code (1 by default) and uses sysexits.h values
    # for every other failure. Worth discriminating, because "flock failed" is
    # not the same claim as "someone else is deploying" — on a filesystem with
    # a limited flock(2) (NFS, CIFS) the call can always fail, and treating that
    # as contention would abort every deploy while blaming a process that does
    # not exist. /home/deploy is local disk on the droplet, so this is a
    # guard against a future move, not a live problem.
    if [ "$flock_rc" = 0 ]; then
        # A separate open, so this replaces the file's *contents* without
        # disturbing the lock held on fd 200. It gives whoever gets blocked
        # next a real PID to name.
        printf '%s\n' "$$" >"$lockfile"
    elif [ "$flock_rc" = 1 ]; then
        holder="$(head -n 1 "$lockfile" 2>/dev/null || true)"
        echo "!! DEPLOY ABORTED: another deploy already holds $lockfile" >&2
        if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
            echo "!! (PID $holder). Inspect it with: ps -fp $holder" >&2
        elif [ -n "$holder" ]; then
            # Don't send the operator chasing a PID that isn't there: the file
            # records whoever wrote it last, which is not necessarily the
            # process the kernel is holding the lock for.
            echo "!! (the file names PID $holder, but no such process is" >&2
            echo "!!  visible — find the real holder with: fuser -v $lockfile)" >&2
        else
            echo "!! (holder PID unknown). Inspect with: fuser -v $lockfile" >&2
        fi
        echo "!! Wait for it to finish, then run ./deploy.sh again." >&2
        exit 1
    else
        deploy_warnings=$((deploy_warnings + 1))
        echo "!! WARNING: flock exited $flock_rc — an error, not contention." >&2
        echo "!! A filesystem with limited flock(2) support (NFS/CIFS) does this." >&2
        echo "!! Running WITHOUT a concurrency lock; check that $lockfile" >&2
        echo "!! is on local disk: df -PT $lockfile" >&2
    fi
fi

echo "==> Pulling latest code..."
script_hash_before="$(hash_self)"
git pull
script_hash_after="$(hash_self)"

# `git pull` can replace this very file, but bash is executing the copy it
# already opened — so every change to deploy.sh would otherwise take effect one
# deploy LATE. Observed live 2026-07-21: the first deploy after PR #120 pulled
# the systemd-unit sync, did not run it, printed "Done. App is live" and exited
# 0 with a stale unit still installed. It also defeats the warning-gating added
# in that PR, since the *old* script has no gating.
# DEPLOY_REEXECED bounds this to a single restart: a script that somehow hashed
# differently on every read still cannot ping-pong forever.
if [ "$script_hash_before" != "$script_hash_after" ] && [ "${DEPLOY_REEXECED:-}" != 1 ]; then
    if [ -r "$script_path" ]; then
        echo "==> deploy.sh updated mid-run; restarting with new version"
        echo "    (everything above this line came from the previous version)"
        export DEPLOY_REEXECED=1
        if [ -x "$script_path" ]; then
            exec "$script_path" "$@"
        else
            # The execute bit can go missing across a pull (a checkout made with
            # core.filemode off, say). Failing here would abort the deploy after
            # the pull but before migrations, so fall back to the interpreter the
            # shebang names anyway rather than dying on a mode bit.
            exec bash "$script_path" "$@"
        fi
    else
        deploy_warnings=$((deploy_warnings + 1))
        echo "!! WARNING: deploy.sh changed but is no longer readable at" >&2
        echo "!! $script_path — continuing with the version already loaded," >&2
        echo "!! which is NOT the one just pulled. Re-run ./deploy.sh." >&2
    fi
fi

echo "==> Installing/updating Python dependencies..."
venv/bin/pip install -r requirements.txt --quiet

echo "==> Applying database migrations..."
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade

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
echo "==> REEXEC PROOF: this line is from the pulled version"
