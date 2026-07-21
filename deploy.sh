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
# -c constraints.txt pins the transitive tree (ADR-042). Without it, pip reports an
# already-satisfied transitive as satisfied and never moves it — which is how prod sat
# on urllib3 2.6.3 across every deploy while 2.7.0 fixed two CVEs. Constraints make the
# installed set deterministic and identical to local; refreshing them is a deliberate
# act, documented in constraints.txt's own header.
venv/bin/pip install -r requirements.txt -c constraints.txt --quiet

echo "==> Applying database migrations..."
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade

# Unit files used to be installed by a manual `sudo cp` documented only in the
# unit's own header, so edits to deploy/*.service silently never reached the
# server: the --timeout 120 fix committed 2026-06-11 was still not live on
# 2026-07-21, leaving prod on gunicorn's 30s default. Sync them here (ADR-040).
#
# EVERY unit in deploy/ is synced, including ones with no counterpart in
# $unit_dir yet (ADR-041). Installing a unit file is not enabling it — systemd
# runs only what has been enabled or started — so a unit for a service this box
# has never run is inert, as the eight mothballed worldcup-* units sitting there
# disabled demonstrate. The alternative, skipping units absent from $unit_dir,
# would leave the CFB timer install at launch depending on someone remembering
# a manual step: the exact failure ADR-040 exists to prevent.
#
# Deliberately non-fatal: this script runs under `set -e`, and aborting here
# would leave migrations applied but the app never restarted — a worse state
# than deploying with a stale unit. Warn loudly and carry on instead.
#
# These two are rewritten by tests/test-deploy-guards.sh (SED 3 / SED 4) so the
# harness can drive this loop against a sandbox directory as an unprivileged
# user. Keep them literal, one per line, anchored at column 0.
unit_dir=/etc/systemd/system
unit_owner=root:root

echo "==> Syncing systemd units..."
# One trap covering every iteration's temp rather than one per unit. Without it,
# an interrupted run (dropped SSH -> SIGHUP) between an install and its rename
# strands a root-owned temp in $unit_dir that the deploy user cannot remove. A
# glob matching nothing expands to itself, and `rm -f` on a nonexistent literal
# is a silent no-op.
trap 'sudo rm -f "$unit_dir"/*.new.$$ 2>/dev/null || true' EXIT INT TERM HUP

# Syncs one unit by name. Prints its own failure explanation; the caller owns
# deploy_warnings so the accounting stays in one place. Return codes are
# distinct so the caller can report real counts rather than a vague "done":
#   0  already in sync    10  installed (was absent)
#   1  failed             11  updated (content or metadata had drifted)
#                         12  reinstalled, but mode/owner could not be verified
sync_unit() {
    local name="$1"
    local repo_file="deploy/$name"
    local live="$unit_dir/$name"
    local tmp="$live.new.$$"
    local meta="" existed=0 stat_failed=0

    # Content alone is not enough to call a unit correct. systemd runs these
    # files as root, so a world-writable or non-root-owned copy is a
    # privilege-escalation path — and a content-only check would report
    # "unchanged" forever while the metadata stayed wrong. Compare both. (GNU
    # stat; this script only ever runs on the Ubuntu droplet.) Absence and stat
    # *failure* are distinguished on purpose: both yield empty metadata, but
    # only the first is expected. Collapsing them would let a stat that breaks
    # for any other reason silently retire the ownership check while the deploy
    # still reported success.
    if [ -e "$live" ]; then
        existed=1
        if meta=$(stat -c '%a %U:%G' "$live" 2>/dev/null); then
            if [ "$meta" = "644 $unit_owner" ] && diff -q "$repo_file" "$live" >/dev/null 2>&1; then
                return 0
            fi
            if [ "$meta" != "644 $unit_owner" ]; then
                echo "    $name metadata is '$meta', expected '644 $unit_owner' — repairing"
            fi
        else
            # Fall through to the install rather than bailing: reinstalling is
            # the one action that makes mode and owner deterministic again, and
            # refusing to would leave the unit in the unverifiable state that
            # prompted the warning. Warn anyway, so a stat breaking for some
            # unexpected reason cannot silently retire the ownership check while
            # the deploy still reports success.
            stat_failed=1
            echo "    !! WARNING: $name exists but stat failed — cannot verify mode/owner." >&2
            echo "    !! Reinstalling it regardless; check by hand: stat -c '%a %U:%G' $live" >&2
        fi
    fi

    # Validate the *repo* file before it lands, not the installed one after.
    # `daemon-reload` exits 0 even for a unit it cannot load — it only logs — so
    # a typo'd ExecStart= or a bad directive would sail past the reload and only
    # surface as a failed restart, with migrations already applied and the
    # service down. Gating the install means the worst case is keeping whatever
    # is live now, which is exactly the pre-sync status quo.
    # Passing the path inside deploy/ matters: systemd-analyze adds the file's
    # own directory to the unit search path, so a .timer resolves its sibling
    # .service there even when neither is installed yet. Verified on the droplet
    # 2026-07-21 — all 29 units pass this with nothing but fantasy-platform and
    # worldcup-* present in $unit_dir.
    if ! sudo systemd-analyze verify "$repo_file"; then
        echo "    !! WARNING: $repo_file failed validation (above). NOT installing it;" >&2
        if [ "$existed" = 1 ]; then
            echo "    !! keeping the current live unit. Fix the repo file." >&2
        else
            echo "    !! $name stays absent from $unit_dir. Fix the repo file." >&2
        fi
        return 1
    fi

    # Installed via write-to-temp + atomic rename rather than a direct copy over
    # the live path. A copy truncates the destination first, so an interrupted
    # write leaves a unit that is still valid INI but missing ExecStart= —
    # systemd refuses to start it, and for fantasy-platform.service that is the
    # file deciding whether the app comes up at all, so the breakage stays
    # latent until the next reboot or deploy. rename(2) within the same
    # directory is atomic: the live path is either the old unit or the new one,
    # never a half-written one. The .new.$$ suffix is not a unit type systemd
    # recognises, so a leftover temp is ignored rather than loaded. Mode is
    # pinned at 644 $unit_owner rather than inherited from the ambient umask —
    # note this means a deliberate hand-tightening to e.g. 640 would be
    # reverted on the next deploy.
    if sudo install -m 644 -o "${unit_owner%%:*}" -g "${unit_owner##*:}" "$repo_file" "$tmp" \
       && sudo mv -f "$tmp" "$live"; then
        if [ "$stat_failed" = 1 ]; then return 12; fi
        if [ "$existed" = 1 ]; then return 11; else return 10; fi
    fi

    sudo rm -f "$tmp" 2>/dev/null || true
    if [ "$existed" = 1 ]; then
        echo "    !! WARNING: could not install $name; continuing with the STALE one." >&2
    else
        echo "    !! WARNING: could not install $name; it stays absent from $unit_dir." >&2
    fi
    echo "    !! Fix with: sudo install -m 644 -o ${unit_owner%%:*} -g ${unit_owner##*:} \\" >&2
    echo "    !!             $repo_file $live" >&2
    return 1
}

unit_ok=0
unit_updated=0
unit_installed=0
unit_failed=0
for unit_path in deploy/*.service deploy/*.timer; do
    # A glob matching nothing expands to itself; don't try to install a file
    # literally named '*.timer'. -f rather than -e so a directory that happens
    # to end in .service is skipped too.
    [ -f "$unit_path" ] || continue
    # Parameter expansion, not basename(1). Case I of the harness runs this
    # script on a PATH stripped to an explicit list of binaries, so every
    # external command added here has to be added there too.
    unit_name="${unit_path##*/}"
    unit_rc=0
    sync_unit "$unit_name" || unit_rc=$?
    case "$unit_rc" in
        0)  unit_ok=$((unit_ok + 1)) ;;
        10) unit_installed=$((unit_installed + 1))
            echo "    $unit_name installed (644 $unit_owner)" ;;
        11) unit_updated=$((unit_updated + 1))
            echo "    $unit_name updated (644 $unit_owner)" ;;
        # Repaired, but the pre-existing state could not be read. Counted as
        # updated *and* warned: the file is now correct, yet something about
        # this box stopped stat working and that should not pass silently.
        12) unit_updated=$((unit_updated + 1))
            deploy_warnings=$((deploy_warnings + 1))
            echo "    $unit_name reinstalled (prior mode/owner unverifiable)" ;;
        # One unit's failure must not abort the others, and must not be hidden
        # by them either: it warns on its own account, and the summary below
        # reports the count.
        *)  unit_failed=$((unit_failed + 1))
            deploy_warnings=$((deploy_warnings + 1)) ;;
    esac
done
echo "    $unit_ok in sync, $unit_updated updated, $unit_installed installed, $unit_failed failed"
if [ "$unit_installed" -gt 0 ]; then
    echo "    NOTE: newly installed units are NOT enabled — writing a unit file"
    echo "    starts nothing. Enable deliberately, one game at a time, naming"
    echo "    each unit in full (systemctl enable does not accept globs):"
    echo "        sudo systemctl enable --now <name>.timer [<name>.timer ...]"
fi

# Once for the whole loop, not per unit. Unconditional, and deliberately NOT
# chained to the installs above. If an install were to succeed while the reload
# failed, $unit_dir would already match the repo, so every later deploy would
# score that unit "in sync" and skip the reload forever — systemd would keep
# serving its old in-memory definition with no signal that anything was wrong.
# Reloading on every deploy makes a transient failure self-heal on the next run.
# sudo is required for the restart below regardless, so this costs no extra
# credential prompt.
# A reload is also all a changed timer needs: it reschedules enabled timers from
# the new OnCalendar, and a changed Type=oneshot service is picked up at its
# next firing. Only fantasy-platform.service is restarted, below.
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
