#!/bin/bash
# Local test harness for deploy.sh's re-exec guard (backlog 1.1) and
# concurrency lock (backlog 1.3). Runs the REAL deploy.sh, with two seds:
#   * `cd /home/deploy/fantasy-platform`  -> cd to the sandbox
#   * the lockfile path                   -> a sandbox path
# Both are outside the logic under test, and the harness prints the resulting
# diff so the substitution is auditable. Everything else — the hash compare,
# the exec, the fd-200 lock handling — is the shipped code, unmodified.
#
# The droplet-only commands (git, sudo, systemd, pip, flask) are PATH shims.
# The `git pull` shim rewrites the script the way git does: build a new file,
# then rename it over the path, so the running bash keeps executing the old
# inode — which is what makes the bug real in the first place.
#
# Usage:
#   bash tests/test-deploy-guards.sh                      # tests ../deploy.sh
#   bash tests/test-deploy-guards.sh /path/to/deploy.sh   # tests that one
#   USE_REAL_FLOCK=1 bash tests/test-deploy-guards.sh      # use the system
#       flock(1) instead of the shim; skips case L, which needs the shim to
#       force a return code. Worth running this way on the droplet, where
#       flock(1) is real — it is the only way to close the shim gap.
#
# Not a pytest file: it drives a shell script, so it lives here as .sh and is
# invisible to pytest collection (which matches test_*.py).
set -u

HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_SCRIPT="${1:-$(cd "$HARNESS_DIR/.." && pwd)/deploy.sh}"
[ -r "$REPO_SCRIPT" ] || { echo "no readable deploy.sh at $REPO_SCRIPT"; exit 1; }
# Normalized through `cd && pwd` on purpose. macOS sets TMPDIR with a trailing
# slash, so the raw mktemp path carries an embedded '//' — and deploy.sh's
# re-exec resolves its own path the same way, collapsing it. The sudo shim
# decides what it may execute by textual prefix match against $SANDBOX, so an
# un-normalized value made every re-exec'd run (B, C, E, K) look like it was
# writing outside the sandbox: the shim refused, install and mv became silent
# no-ops, and nothing failed because those cases assert on the lock, not on
# units. Case T is what surfaced it.
SANDBOX="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/deploy-guard-sandbox.XXXXXX")" && pwd)"
SHIMS="$SANDBOX/shims"

pass=0
fail=0

ok()   { pass=$((pass + 1)); echo "    PASS: $1"; }
bad()  { fail=$((fail + 1)); echo "    FAIL: $1"; }
check() { # check <description> <actual> <expected>
    if [ "$2" = "$3" ]; then ok "$1 (= $3)"; else bad "$1 — expected '$3', got '$2'"; fi
}

# ---------------------------------------------------------------- sandbox ---
mkdir -p "$SHIMS" "$SANDBOX/venv/bin" "$SANDBOX/deploy" "$SANDBOX/etc-systemd"

# SED 3/4 redirect the unit sync (backlog 1.2) at a sandbox directory owned by
# whoever is running the tests. Without them the loop would aim at the real
# /etc/systemd/system as root:root, so every local run would either refuse to
# work or — far worse — write there.
HARNESS_USER="$(id -un):$(id -gn)"

sed -e 's|^cd /home/deploy/fantasy-platform$|cd "$(dirname "$0")"|' \
    -e 's|^lockfile=/home/deploy/.*$|lockfile="$(dirname "$0")/deploy.lock"|' \
    -e 's|^unit_dir=/etc/systemd/system$|unit_dir="$(dirname "$0")/etc-systemd"|' \
    -e "s|^unit_owner=root:root\$|unit_owner=$HARNESS_USER|" \
    "$REPO_SCRIPT" > "$SANDBOX/deploy.sh"
chmod +x "$SANDBOX/deploy.sh"

echo "=== Harness seds applied to the copy under test ==="
diff "$REPO_SCRIPT" "$SANDBOX/deploy.sh" || true
echo

# Fail loudly if a sed silently matched nothing — a no-op sed would leave the
# test running against /home/deploy paths and quietly prove nothing.
grep -q 'cd "$(dirname "$0")"' "$SANDBOX/deploy.sh" || { echo "SED 1 MISSED"; exit 1; }
# SEDs 2–4 are relaxed only for the red-baseline run against a pre-fix script,
# which has no lockfile line and no unit_dir/unit_owner lines to rewrite.
if ! grep -q 'lockfile="$(dirname "$0")/deploy.lock"' "$SANDBOX/deploy.sh"; then
    [ -n "${ALLOW_MISSING_LOCK_SED:-}" ] || { echo "SED 2 MISSED"; exit 1; }
    echo "(no lockfile line — running the legacy-baseline comparison)"
fi
if ! grep -q 'unit_dir="$(dirname "$0")/etc-systemd"' "$SANDBOX/deploy.sh"; then
    [ -n "${ALLOW_MISSING_LOCK_SED:-}" ] || { echo "SED 3 MISSED"; exit 1; }
    echo "(no unit_dir line — legacy baseline)"
fi
if ! grep -q "^unit_owner=$HARNESS_USER\$" "$SANDBOX/deploy.sh"; then
    [ -n "${ALLOW_MISSING_LOCK_SED:-}" ] || { echo "SED 4 MISSED"; exit 1; }
    echo "(no unit_owner line — legacy baseline)"
fi

cp "$SANDBOX/deploy.sh" "$SANDBOX/deploy.sh.pristine"

# Unit fixtures. deploy.sh loops over deploy/*.service and deploy/*.timer, so
# what lives here sets the counts every unit-sync case asserts on: five units —
# the real one by name (cases A–M restart it) plus two service/timer pairs
# standing in for a game's timers. The contents only need to be stable and
# distinguishable; systemd-analyze is shimmed, so unit *validity* is not what
# these prove. Change this set and cases N–S need their numbers rechecked.
: > "$SANDBOX/deploy/fantasy-platform.service"
for u in guard-alpha guard-beta; do
    printf '[Unit]\nDescription=%s fixture\n\n[Service]\nType=oneshot\nExecStart=/bin/true\n' \
        "$u" > "$SANDBOX/deploy/$u.service"
    printf '[Unit]\nDescription=%s fixture timer\n\n[Timer]\nOnCalendar=daily\n\n[Install]\nWantedBy=timers.target\n' \
        "$u" > "$SANDBOX/deploy/$u.timer"
done
UNIT_FIXTURE_COUNT=5

# Created empty so case T can count lines unconditionally. Left to accumulate
# for the whole run — reset_state must never clear it.
: > "$SANDBOX/sudo-refused"

# Fingerprint the live unit up front so test G can prove the harness never
# rewrote it. On the droplet this file exists (and must stay byte-identical);
# on a dev Mac it does not.
UNIT_LIVE=/etc/systemd/system/fantasy-platform.service
unit_fingerprint() { cksum < "$UNIT_LIVE" 2>/dev/null || echo "ABSENT"; }
UNIT_BEFORE="$(unit_fingerprint)"

# --- shims ------------------------------------------------------------------
# git: `pull` bumps a counter and, when MUTATE_PULLS says so, rewrites the
# script via cp+mv (git's own replace-by-rename), inserting a marker echo near
# the top so the new version announces itself when it runs.
cat > "$SHIMS/git" <<'GIT'
#!/bin/bash
if [ "${1:-}" = "pull" ]; then
    n=$(cat "$SANDBOX/pull-count" 2>/dev/null || echo 0)
    n=$((n + 1))
    echo "$n" > "$SANDBOX/pull-count"
    if [ "$n" -le "${MUTATE_PULLS:-0}" ]; then
        cp -p "$SANDBOX/deploy.sh" "$SANDBOX/deploy.sh.new"
        awk -v n="$n" 'NR==4 {print; print "echo \"[MARKER] running script version " n "\""; next} {print}' \
            "$SANDBOX/deploy.sh.pristine" > "$SANDBOX/deploy.sh.new"
        if [ -n "${STRIP_EXEC_BIT:-}" ]; then
            chmod -x "$SANDBOX/deploy.sh.new"
        else
            chmod +x "$SANDBOX/deploy.sh.new"
        fi
        mv -f "$SANDBOX/deploy.sh.new" "$SANDBOX/deploy.sh"
        echo "Updating fake..fake"
    else
        echo "Already up to date."
    fi
    exit 0
fi
exit 0
GIT

# sudo: records every command. Executes only file operations whose paths all
# resolve inside the sandbox; everything else is a logged no-op. Nothing in this
# harness may touch the real /etc — case T asserts that no path was ever even
# offered.
#
# The exec path exists because the unit sync (backlog 1.2) is only meaningfully
# testable against real files: deploy.sh's own diff and stat decide in-sync vs
# updated vs installed, and a shim that merely returned 0 would leave every one
# of those branches unreachable — which is exactly how the sync block shipped
# with 54 assertions around it and none on it.
cat > "$SHIMS/sudo" <<'SUDO'
#!/bin/bash
echo "sudo $*" >> "$SANDBOX/sudo-log"

# Lets a case force one privileged command to fail, the way a malformed unit
# fails systemd-analyze or a full disk fails install(1). Matched against the
# whole command line, so a case can target a single unit by name. Same idea as
# FLOCK_FORCE_RC in the flock shim.
if [ -n "${SUDO_FAIL_RE:-}" ] && [[ "$*" =~ $SUDO_FAIL_RE ]]; then
    echo "sudo: forced failure (SUDO_FAIL_RE) for: $*" >&2
    exit 1
fi

case "${1:-}" in
    install|mv|rm) cmd="$1"; shift ;;
    *) exit 0 ;;                     # systemctl, systemd-analyze, ... : no-op
esac

args=()
while [ $# -gt 0 ]; do
    case "$1" in
        # The harness is not root, so ownership cannot be set. This is the one
        # fidelity gap in the shim, and it is why deploy.sh reads $unit_owner
        # instead of hardcoding root:root — the mode/owner comparison it does
        # afterwards is still exercised for real, against this user.
        -o|-g) shift 2 ;;
        -m)    args+=("$1" "$2"); shift 2 ;;
        -*)    args+=("$1"); shift ;;
        *)
            # A path argument. If even one escapes the sandbox, refuse the whole
            # command rather than let a harness bug write to the real box, and
            # leave a durable record for case T.
            case "$1" in
                "$SANDBOX"/*) args+=("$1"); shift ;;
                /*)    echo "REFUSED absolute path outside sandbox: $1" >> "$SANDBOX/sudo-refused"; exit 0 ;;
                *..*)  echo "REFUSED relative path containing ..: $1" >> "$SANDBOX/sudo-refused"; exit 0 ;;
                # Relative to the cwd, which SED 1 pins inside the sandbox.
                *)     args+=("$1"); shift ;;
            esac
            ;;
    esac
done
exec "$cmd" "${args[@]}"
SUDO

# deploy.sh reads mode and owner with GNU `stat -c`. Always shimmed, for two
# reasons:
#   * macOS BSD stat has no -c, and once the unit directory is inside the
#     sandbox that file exists locally too — so deploy.sh's "stat failed"
#     warning branch would fire as a false positive on every local run.
#   * STAT_FORCE_FAIL_RE gives case U a way to exercise that branch deliberately,
#     the same seam FLOCK_FORCE_RC provides for the lock.
# Where GNU stat exists (the droplet) the shim delegates straight to it, so the
# forced-failure hook is the only behavioural difference.
if stat -c '%a' . >/dev/null 2>&1; then STAT_MODE=gnu; else STAT_MODE=bsd; fi
echo "(system stat is $STAT_MODE-style; shimming it with a forced-failure seam)"
# Two heredocs on purpose: the first interpolates the values resolved here (note
# this runs before $SHIMS is on PATH, so it finds the system binary), the second
# is quoted so the shim body is taken literally.
cat > "$SHIMS/stat" <<STAT
#!/bin/bash
STAT_MODE=$STAT_MODE
REAL_STAT=$(command -v stat)
STAT
cat >> "$SHIMS/stat" <<'STAT'
if [ -n "${STAT_FORCE_FAIL_RE:-}" ] && [[ "$*" =~ $STAT_FORCE_FAIL_RE ]]; then
    echo "stat: forced failure (STAT_FORCE_FAIL_RE): $*" >&2
    exit 1
fi
[ "$STAT_MODE" = gnu ] && exec "$REAL_STAT" "$@"
# Only the formats deploy.sh and this harness use are translated. Anything else
# is an error rather than a silently wrong answer.
case "${2:-}" in
    '%a %U:%G') exec "$REAL_STAT" -f '%Lp %Su:%Sg' "$3" ;;
    '%a')       exec "$REAL_STAT" -f '%Lp' "$3" ;;
esac
echo "stat shim: unsupported invocation: $*" >&2
exit 64
STAT

# flock(1) does not exist on macOS. This calls flock(2) on the same inherited
# fd the real utility would — same syscall, same kernel semantics — so what is
# under test is the script's fd handling, not this shim's cleverness.
if [ -n "${USE_REAL_FLOCK:-}" ]; then
    echo "(USE_REAL_FLOCK: using the system flock(1) at $(command -v flock); test L skipped)"
else
cat > "$SHIMS/flock" <<'FLOCK'
#!/usr/bin/env python3
import fcntl, os, sys
# Lets a test force a non-contention failure, the way flock(1) reports one on a
# filesystem with limited flock(2) support (sysexits.h codes, never 1).
forced = os.environ.get("FLOCK_FORCE_RC")
if forced:
    sys.exit(int(forced))
args = sys.argv[1:]
nonblock = "-n" in args or "--nonblock" in args
fds = [int(a) for a in args if a.isdigit()]
if not fds:
    sys.exit(2)
try:
    fcntl.flock(fds[0], fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblock else 0))
except OSError:
    sys.exit(1)
sys.exit(0)
FLOCK
fi

# The 6s post-restart settle is not what these tests exercise; overlap for the
# concurrency tests is created deliberately by the flask shim instead.
cat > "$SHIMS/sleep" <<'SLEEP'
#!/bin/bash
exit 0
SLEEP

cat > "$SANDBOX/venv/bin/pip" <<'PIP'
#!/bin/bash
exit 0
PIP

# `db upgrade` is the step two concurrent deploys must never overlap on, so it
# is also the natural place to hold the lock open for the concurrency tests.
cat > "$SANDBOX/venv/bin/flask" <<'FLASK'
#!/bin/bash
if [ -n "${SLOW_MIGRATION:-}" ]; then /bin/sleep "$SLOW_MIGRATION"; fi
exit 0
FLASK

chmod +x "$SHIMS"/* "$SANDBOX/venv/bin/pip" "$SANDBOX/venv/bin/flask"
export SANDBOX
export PATH="$SHIMS:$PATH"

reset_state() {
    rm -f "$SANDBOX/pull-count" "$SANDBOX/sudo-log" "$SANDBOX/deploy.lock"
    cp -p "$SANDBOX/deploy.sh.pristine" "$SANDBOX/deploy.sh"
    # Units land for real (see the sudo shim), so a case that distinguishes
    # installed from in-sync has to start from a known-empty unit directory.
    # sudo-refused is deliberately NOT cleared: it accumulates across the whole
    # run so case T can assert on every case at once.
    rm -rf "$SANDBOX/etc-systemd"
    mkdir -p "$SANDBOX/etc-systemd"
}

# ------------------------------------------------------------------ tests ---
echo "=== A: script unchanged by the pull ⇒ no re-exec ==="
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/a.out" 2>&1
check "exit code" "$?" "0"
check "re-exec announcements" "$(grep -c 'updated mid-run' "$SANDBOX/a.out")" "0"
check "git pull invocations" "$(cat "$SANDBOX/pull-count")" "1"
check "reached the end" "$(grep -c 'Done. App is live' "$SANDBOX/a.out")" "1"
echo

echo "=== B: pull replaces the script ⇒ exactly one re-exec, new version runs ==="
reset_state
MUTATE_PULLS=1 "$SANDBOX/deploy.sh" > "$SANDBOX/b.out" 2>&1
check "exit code" "$?" "0"
check "re-exec announcements" "$(grep -c 'updated mid-run' "$SANDBOX/b.out")" "1"
check "git pull invocations" "$(cat "$SANDBOX/pull-count")" "2"
check "new version announced itself" "$(grep -c '\[MARKER\] running script version 1' "$SANDBOX/b.out")" "1"
check "reached the end" "$(grep -c 'Done. App is live' "$SANDBOX/b.out")" "1"
# The marker must appear AFTER the restart line, i.e. the new code really is
# what ran on — not merely that both strings landed in the output somewhere.
marker_line=$(grep -n '\[MARKER\]' "$SANDBOX/b.out" | head -1 | cut -d: -f1)
restart_line=$(grep -n 'updated mid-run' "$SANDBOX/b.out" | head -1 | cut -d: -f1)
if [ "$marker_line" -gt "$restart_line" ]; then
    ok "marker (line $marker_line) follows the restart notice (line $restart_line)"
else
    bad "marker at $marker_line did not follow the restart notice at $restart_line"
fi
echo

echo "=== C: every pull rewrites the script ⇒ still exactly one re-exec, no loop ==="
reset_state
MUTATE_PULLS=99 "$SANDBOX/deploy.sh" > "$SANDBOX/c.out" 2>&1
check "exit code" "$?" "0"
check "re-exec announcements" "$(grep -c 'updated mid-run' "$SANDBOX/c.out")" "1"
check "git pull invocations (would grow unbounded if it looped)" "$(cat "$SANDBOX/pull-count")" "2"
# Version 1 is what runs on after the single permitted restart. Version 2 lands
# on disk during v1's pull and is deliberately NOT executed — that is the
# "at most once" contract, and the reason the guard cannot livelock. A v3 never
# even gets written, because there is no third pull.
check "version 1 ran (the one restart)" "$(grep -c '\[MARKER\] running script version 1' "$SANDBOX/c.out")" "1"
check "version 2 written but never executed" "$(grep -c '\[MARKER\] running script version 2' "$SANDBOX/c.out")" "0"
check "v2 is nonetheless on disk for the next deploy" \
      "$(grep -c 'running script version 2' "$SANDBOX/deploy.sh")" "1"
echo

echo "=== D: a second deploy is refused while the first holds the lock ==="
reset_state
MUTATE_PULLS=0 SLOW_MIGRATION=6 "$SANDBOX/deploy.sh" > "$SANDBOX/d1.out" 2>&1 &
first_pid=$!
/bin/sleep 2
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/d2.out" 2>&1
second_rc=$?
check "second run exit code (non-zero)" "$second_rc" "1"
check "named the conflict" "$(grep -c 'another deploy already holds' "$SANDBOX/d2.out")" "1"
check "named the holding PID" "$(grep -c "PID $first_pid" "$SANDBOX/d2.out")" "1"
check "second run did NOT reach migrations" "$(grep -c 'Applying database migrations' "$SANDBOX/d2.out")" "0"
wait $first_pid
check "first run still succeeded" "$?" "0"
echo

echo "=== E: the lock survives the re-exec (fd 200 inherited) ==="
reset_state
MUTATE_PULLS=1 SLOW_MIGRATION=6 "$SANDBOX/deploy.sh" > "$SANDBOX/e1.out" 2>&1 &
first_pid=$!
/bin/sleep 3   # past the re-exec, inside the slow migration of the NEW process
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/e2.out" 2>&1
second_rc=$?
check "competing run refused during the re-exec'd phase" "$second_rc" "1"
check "PID is unchanged across exec" "$(grep -c "PID $first_pid" "$SANDBOX/e2.out")" "1"
wait $first_pid
check "re-exec'd run reported the inherited lock" "$(grep -c 'inherited across the restart' "$SANDBOX/e1.out")" "1"
check "re-exec'd run did not re-acquire (would self-deny)" "$(grep -c 'another deploy already holds' "$SANDBOX/e1.out")" "0"
check "re-exec'd run finished" "$(grep -c 'Done. App is live' "$SANDBOX/e1.out")" "1"
echo

echo "=== F: the lock is released when a run finishes ==="
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/f.out" 2>&1
check "next deploy acquires cleanly" "$?" "0"
check "no spurious conflict" "$(grep -c 'another deploy already holds' "$SANDBOX/f.out")" "0"
echo

echo "=== G: no test ever touched the real /etc ==="
# The sudo-log spans tests E and F (reset_state is not called before F), so the
# meaningful assertion is the state of the box, not a call count.
check "live systemd unit is byte-identical to before the run" "$(unit_fingerprint)" "$UNIT_BEFORE"
check "privileged calls all went to the shim log" \
      "$(grep -c 'systemctl restart fantasy-platform' "$SANDBOX/sudo-log")" "2"
echo

echo "=== H: premise check — flock(2) denies a second lock from the SAME process ==="
# The whole design rests on this: the re-exec'd instance must reuse the
# inherited fd, because re-acquiring through a fresh open() of the same file
# would be denied by its own lock. If this ever passed, the comment in
# deploy.sh explaining why we do not re-acquire would be wrong.
premise=$(python3 - "$SANDBOX/premise.lock" <<'PY'
import fcntl, sys
path = sys.argv[1]
a = open(path, "a")
fcntl.flock(a, fcntl.LOCK_EX | fcntl.LOCK_NB)
b = open(path, "a")          # same file, same process, different description
try:
    fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("GRANTED")
except OSError:
    print("DENIED")
PY
)
check "second lock through a fresh open()" "$premise" "DENIED"
echo

echo "=== I: flock unavailable ⇒ warn, deploy anyway, exit non-zero ==="
# Deploying must not become impossible because a utility is missing, but per
# #120's doctrine a warned deploy may not report success.
reset_state
# The PATH here must genuinely lack flock. Appending /usr/bin would defeat that
# on any box that actually ships it (the droplet does; macOS does not — which is
# why an earlier version of this test passed locally and failed there). So build
# an explicit bin dir: symlink exactly what deploy.sh calls, and nothing else.
mkdir -p "$SANDBOX/shims-noflock"
for s in git sudo sleep; do cp "$SHIMS/$s" "$SANDBOX/shims-noflock/"; done
for b in dirname basename sha256sum shasum stat diff head cat cksum rm mv install kill; do
    src="$(command -v "$b" 2>/dev/null)" && ln -sf "$src" "$SANDBOX/shims-noflock/$b"
done
# The GNU-stat translation shim, where one was needed, has to win over the
# symlink to the system stat the loop above just made — otherwise this case
# alone hits BSD stat and reports a warning the other cases don't.
if [ -e "$SHIMS/stat" ]; then cp -f "$SHIMS/stat" "$SANDBOX/shims-noflock/stat"; fi
if PATH="$SANDBOX/shims-noflock" command -v flock >/dev/null 2>&1; then
    bad "test I setup is broken — flock is still reachable on the stripped PATH"
fi
PATH="$SANDBOX/shims-noflock" MUTATE_PULLS=0 \
    "$SANDBOX/deploy.sh" > "$SANDBOX/i.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "warned about the missing lock" "$(grep -c 'WITHOUT a concurrency lock' "$SANDBOX/i.out")" "1"
check "deploy still completed the real work" "$(grep -c 'Restarting application' "$SANDBOX/i.out")" "1"
check "did not claim success" "$(grep -c 'Done. App is live' "$SANDBOX/i.out")" "0"
check "counted exactly one warning" "$(grep -c 'with 1 warning' "$SANDBOX/i.out")" "1"
echo

echo "=== J: unwritable lockfile (the root-owned-by-sudo case) ⇒ warn, not a crash ==="
if [ "$(id -u)" = 0 ]; then
    # root has CAP_DAC_OVERRIDE, so the 444 below would still be writable and
    # the branch under test could never fire. Skipped rather than reported as a
    # failure — and announced rather than dropped silently, since a quiet skip
    # reads as "covered". deploy.sh runs as the unprivileged 'deploy' user in
    # production, which is the case this models.
    echo "    SKIPPED: running as root, which bypasses the 444 mode this case needs"
    echo
else
reset_state
: > "$SANDBOX/deploy.lock"
chmod 444 "$SANDBOX/deploy.lock"
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/j.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "explained the cause" "$(grep -c 'cannot open' "$SANDBOX/j.out")" "1"
check "gave the fix" "$(grep -c 'sudo rm -f' "$SANDBOX/j.out")" "1"
check "no raw bash redirection error" "$(grep -ci 'permission denied' "$SANDBOX/j.out")" "0"
check "deploy still ran" "$(grep -c 'Restarting application' "$SANDBOX/j.out")" "1"
chmod 644 "$SANDBOX/deploy.lock"
echo
fi

echo "=== K: the pulled script lost its execute bit ⇒ re-exec still works ==="
reset_state
STRIP_EXEC_BIT=1 MUTATE_PULLS=1 "$SANDBOX/deploy.sh" > "$SANDBOX/k.out" 2>&1
check "exit code" "$?" "0"
check "still restarted exactly once" "$(grep -c 'updated mid-run' "$SANDBOX/k.out")" "1"
check "new version ran via the bash fallback" \
      "$(grep -c '\[MARKER\] running script version 1' "$SANDBOX/k.out")" "1"
check "reached the end" "$(grep -c 'Done. App is live' "$SANDBOX/k.out")" "1"
chmod +x "$SANDBOX/deploy.sh"
echo

if [ -n "${USE_REAL_FLOCK:-}" ]; then
    echo "=== L: SKIPPED (needs the shim to force a sysexits return code) ==="
    echo
else
echo "=== L: flock fails for a NON-contention reason ⇒ error, not a false conflict ==="
# CR #121: on NFS/CIFS flock(2) can always fail. flock(1) reports contention as
# exit 1 and everything else with sysexits.h codes, so EX_OSERR must not be
# mistaken for another deploy.
reset_state
FLOCK_FORCE_RC=71 MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/l.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "did NOT falsely claim contention" "$(grep -c 'another deploy already holds' "$SANDBOX/l.out")" "0"
check "reported the real exit code" "$(grep -c 'flock exited 71' "$SANDBOX/l.out")" "1"
check "named the likely cause" "$(grep -c 'NFS/CIFS' "$SANDBOX/l.out")" "1"
check "deploy still ran" "$(grep -c 'Restarting application' "$SANDBOX/l.out")" "1"
echo
fi

echo "=== M: contention with a stale PID in the file ⇒ don't send them chasing it ==="
reset_state
( exec 200>>"$SANDBOX/deploy.lock"
  flock -n 200 && echo "999999" > "$SANDBOX/deploy.lock" && /bin/sleep 8 ) &
holder_pid=$!
/bin/sleep 2
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/m.out" 2>&1
check "still aborts on real contention" "$?" "1"
check "reported the conflict" "$(grep -c 'another deploy already holds' "$SANDBOX/m.out")" "1"
check "flagged the PID as not visible" "$(grep -c 'no such process is' "$SANDBOX/m.out")" "1"
check "did not offer a bogus ps command" "$(grep -c 'ps -fp 999999' "$SANDBOX/m.out")" "0"
wait $holder_pid 2>/dev/null || true
echo

# --- unit sync (backlog 1.2 / ADR-041) --------------------------------------
# These start at N rather than slotting in earlier on purpose: case G counts
# `systemctl restart` calls accumulated across E and F (F deliberately skips
# reset_state), so inserting a deploy-invoking case above it would silently
# change that number.
#
# Before 1.2, deploy.sh synced exactly one unit and the other 28 in deploy/ were
# in the silent-drift state ADR-040 condemns: editing the repo file changed
# nothing on the box, and nothing said so. The sync block also ran in every case
# A–M with not one assertion on it, so all of its warning branches were dead
# code. N–S cover the loop; T is the safety net for the whole run.

echo "=== N: nothing changed since the last deploy ⇒ everything reports in sync ==="
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/n1.out" 2>&1
check "first run installed the fixtures" \
      "$(grep -c "0 in sync, 0 updated, $UNIT_FIXTURE_COUNT installed, 0 failed" "$SANDBOX/n1.out")" "1"
# Cleared by hand rather than via reset_state, which would also wipe the unit
# directory this case exists to find already-populated.
rm -f "$SANDBOX/sudo-log"
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/n2.out" 2>&1
check "exit code" "$?" "0"
check "second run found every unit in sync" \
      "$(grep -c "$UNIT_FIXTURE_COUNT in sync, 0 updated, 0 installed, 0 failed" "$SANDBOX/n2.out")" "1"
check "rewrote nothing" "$(grep -c 'installed (644' "$SANDBOX/n2.out")" "0"
check "no NOT-enabled note when nothing was installed" \
      "$(grep -c 'NOT enabled' "$SANDBOX/n2.out")" "0"
# Validation is gated behind the change check, so a steady-state deploy must not
# pay for 29 systemd-analyze invocations.
check "validated nothing it wasn't about to install" \
      "$(grep -c 'systemd-analyze verify' "$SANDBOX/sudo-log")" "0"
echo

echo "=== O: units absent from the unit dir ⇒ installed, and said to be inert ==="
# ADR-041: absent units are installed rather than skipped, so the CFB timer
# install at launch is not left depending on someone remembering a manual step.
# The note matters as much as the install — installing is not enabling, and an
# operator who thinks otherwise could double-run Golf against PythonAnywhere.
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/o.out" 2>&1
check "exit code" "$?" "0"
check "installed every absent unit" \
      "$(grep -c "0 in sync, 0 updated, $UNIT_FIXTURE_COUNT installed, 0 failed" "$SANDBOX/o.out")" "1"
check "said installed is not enabled" "$(grep -c 'NOT enabled' "$SANDBOX/o.out")" "1"
check "the files really landed" \
      "$(find "$SANDBOX/etc-systemd" -type f | wc -l | tr -d ' ')" "$UNIT_FIXTURE_COUNT"
check "landed at mode 644" "$(stat -c '%a' "$SANDBOX/etc-systemd/guard-alpha.timer")" "644"
check "landed byte-identical to the repo copy" \
      "$(cmp -s "$SANDBOX/deploy/guard-alpha.timer" "$SANDBOX/etc-systemd/guard-alpha.timer" && echo same || echo differs)" "same"
check "no temp file survived the run" \
      "$(find "$SANDBOX/etc-systemd" -name '*.new.*' | wc -l | tr -d ' ')" "0"
check "reached the end" "$(grep -c 'Done. App is live' "$SANDBOX/o.out")" "1"
echo

echo "=== P: one unit fails validation ⇒ it is skipped, the rest still install ==="
# The whole point of a per-unit verdict. A loop that aborted on the first bad
# unit would leave the deploy half-synced with no signal which half.
reset_state
SUDO_FAIL_RE='systemd-analyze verify deploy/guard-beta\.timer' MUTATE_PULLS=0 \
    "$SANDBOX/deploy.sh" > "$SANDBOX/p.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "named the failing unit" \
      "$(grep -c 'deploy/guard-beta.timer failed validation' "$SANDBOX/p.out")" "1"
check "said it stays absent, not that a stale copy was kept" \
      "$(grep -c 'guard-beta.timer stays absent' "$SANDBOX/p.out")" "1"
check "the other four installed anyway" \
      "$(grep -c '0 in sync, 0 updated, 4 installed, 1 failed' "$SANDBOX/p.out")" "1"
check "the rejected unit did not land" \
      "$([ -e "$SANDBOX/etc-systemd/guard-beta.timer" ] && echo present || echo absent)" "absent"
check "counted exactly one warning" "$(grep -c 'with 1 warning' "$SANDBOX/p.out")" "1"
check "deploy still completed the real work" \
      "$(grep -c 'Restarting application' "$SANDBOX/p.out")" "1"
check "did not claim success" "$(grep -c 'Done. App is live' "$SANDBOX/p.out")" "0"
echo

echo "=== Q: one unit's install fails ⇒ warned per-unit, the rest still install ==="
# Distinct from P: validation passed and the write itself failed, which is the
# branch that has to clean up its temp file.
reset_state
SUDO_FAIL_RE='^install .*guard-alpha\.service' MUTATE_PULLS=0 \
    "$SANDBOX/deploy.sh" > "$SANDBOX/q.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "named the unit it could not install" \
      "$(grep -c 'could not install guard-alpha.service' "$SANDBOX/q.out")" "1"
check "offered the by-hand fix" \
      "$(grep -c 'Fix with: sudo install -m 644' "$SANDBOX/q.out")" "1"
check "the other four installed anyway" \
      "$(grep -c '0 in sync, 0 updated, 4 installed, 1 failed' "$SANDBOX/q.out")" "1"
check "counted exactly one warning" "$(grep -c 'with 1 warning' "$SANDBOX/q.out")" "1"
check "left no temp file behind" \
      "$(find "$SANDBOX/etc-systemd" -name '*.new.*' | wc -l | tr -d ' ')" "0"
check "did not claim success" "$(grep -c 'Done. App is live' "$SANDBOX/q.out")" "0"
echo

echo "=== R: an installed unit's mode drifted ⇒ repaired, not reported in sync ==="
# A content-only comparison would call this unit correct forever. systemd runs
# these files as root, so a loosened mode is a privilege-escalation path, not a
# cosmetic difference.
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/r1.out" 2>&1
chmod 600 "$SANDBOX/etc-systemd/guard-alpha.service"
rm -f "$SANDBOX/sudo-log"
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/r2.out" 2>&1
check "exit code (a repair is not a warning)" "$?" "0"
check "reported the drifted metadata" \
      "$(grep -c "guard-alpha.service metadata is '600" "$SANDBOX/r2.out")" "1"
check "counted it as updated, not in sync" \
      "$(grep -c '4 in sync, 1 updated, 0 installed, 0 failed' "$SANDBOX/r2.out")" "1"
check "mode is back to 644" \
      "$(stat -c '%a' "$SANDBOX/etc-systemd/guard-alpha.service")" "644"
check "still claimed success" "$(grep -c 'Done. App is live' "$SANDBOX/r2.out")" "1"
echo

echo "=== S: an installed unit was hand-edited ⇒ overwritten; one reload for the batch ==="
# The drift ADR-040 exists to kill, in the direction nobody expects: the box
# edited, not the repo. The repo wins.
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/s1.out" 2>&1
echo "# hand-edited on the box" >> "$SANDBOX/etc-systemd/guard-beta.service"
rm -f "$SANDBOX/sudo-log"
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/s2.out" 2>&1
check "exit code" "$?" "0"
check "counted exactly one unit as updated" \
      "$(grep -c '4 in sync, 1 updated, 0 installed, 0 failed' "$SANDBOX/s2.out")" "1"
check "the hand edit is gone" \
      "$(grep -c 'hand-edited' "$SANDBOX/etc-systemd/guard-beta.service")" "0"
check "left the units it did not touch alone" \
      "$(grep -c 'updated (644' "$SANDBOX/s2.out")" "1"
# Per unit would mean 29 reloads on the real box. Once, unconditionally, after
# the loop — see the comment in deploy.sh for why it is not chained to a
# successful install.
check "reloaded systemd exactly once for the whole loop" \
      "$(grep -c 'systemctl daemon-reload' "$SANDBOX/sudo-log")" "1"
echo

echo "=== U: mode/owner unreadable ⇒ reinstall anyway, and still warn ==="
# Bailing out here would be the tempting read of "can't verify, don't touch" —
# and it would be wrong twice over: it leaves the unit in exactly the
# unverifiable state that raised the alarm, and reinstalling is the one action
# that makes mode and owner deterministic again. The warning has to survive the
# repair, or a stat breaking for an unexpected reason silently retires the
# ownership check while the deploy reports success.
reset_state
MUTATE_PULLS=0 "$SANDBOX/deploy.sh" > "$SANDBOX/u1.out" 2>&1
chmod 600 "$SANDBOX/etc-systemd/guard-beta.timer"
rm -f "$SANDBOX/sudo-log"
STAT_FORCE_FAIL_RE='guard-beta\.timer' MUTATE_PULLS=0 \
    "$SANDBOX/deploy.sh" > "$SANDBOX/u.out" 2>&1
check "exit code (warned ⇒ non-zero)" "$?" "1"
check "said it could not verify mode/owner" \
      "$(grep -c 'guard-beta.timer exists but stat failed' "$SANDBOX/u.out")" "1"
check "said it was reinstalling regardless" \
      "$(grep -c 'Reinstalling it regardless' "$SANDBOX/u.out")" "1"
check "counted it as updated, not failed" \
      "$(grep -c '4 in sync, 1 updated, 0 installed, 0 failed' "$SANDBOX/u.out")" "1"
check "repaired the mode it could not read" \
      "$(stat -c '%a' "$SANDBOX/etc-systemd/guard-beta.timer")" "644"
check "counted exactly one warning" "$(grep -c 'with 1 warning' "$SANDBOX/u.out")" "1"
check "did not claim success" "$(grep -c 'Done. App is live' "$SANDBOX/u.out")" "0"
echo

echo "=== T: across every case above, no privileged call was aimed outside the sandbox ==="
# The standing safety net for the mirror policy. A bug in the loop, a sed that
# stopped matching, or a fixture with an absolute path would show up here as a
# refusal — and case G's fingerprint proves the real unit is untouched even if
# the shim's guard were itself wrong.
check "the sudo shim never had to refuse a path" \
      "$(wc -l < "$SANDBOX/sudo-refused" | tr -d ' ')" "0"
check "the real live unit is still byte-identical" "$(unit_fingerprint)" "$UNIT_BEFORE"
echo

echo "==================================================="
echo "  PASSED: $pass    FAILED: $fail"
echo "==================================================="
if [ "$fail" -eq 0 ]; then
    rm -rf "$SANDBOX"
else
    echo "sandbox kept for inspection: $SANDBOX"
fi
[ "$fail" -eq 0 ]
