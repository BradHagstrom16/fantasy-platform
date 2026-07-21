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
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/deploy-guard-sandbox.XXXXXX")"
SHIMS="$SANDBOX/shims"

pass=0
fail=0

ok()   { pass=$((pass + 1)); echo "    PASS: $1"; }
bad()  { fail=$((fail + 1)); echo "    FAIL: $1"; }
check() { # check <description> <actual> <expected>
    if [ "$2" = "$3" ]; then ok "$1 (= $3)"; else bad "$1 — expected '$3', got '$2'"; fi
}

# ---------------------------------------------------------------- sandbox ---
mkdir -p "$SHIMS" "$SANDBOX/venv/bin" "$SANDBOX/deploy"

sed -e 's|^cd /home/deploy/fantasy-platform$|cd "$(dirname "$0")"|' \
    -e 's|^lockfile=/home/deploy/.*$|lockfile="$(dirname "$0")/deploy.lock"|' \
    "$REPO_SCRIPT" > "$SANDBOX/deploy.sh"
chmod +x "$SANDBOX/deploy.sh"

echo "=== Harness seds applied to the copy under test ==="
diff "$REPO_SCRIPT" "$SANDBOX/deploy.sh" || true
echo

# Fail loudly if a sed silently matched nothing — a no-op sed would leave the
# test running against /home/deploy paths and quietly prove nothing.
grep -q 'cd "$(dirname "$0")"' "$SANDBOX/deploy.sh" || { echo "SED 1 MISSED"; exit 1; }
# Relaxed only for the red-baseline run against the pre-fix script, which has
# no lockfile line to rewrite.
if ! grep -q 'lockfile="$(dirname "$0")/deploy.lock"' "$SANDBOX/deploy.sh"; then
    [ -n "${ALLOW_MISSING_LOCK_SED:-}" ] || { echo "SED 2 MISSED"; exit 1; }
    echo "(no lockfile line — running the legacy-baseline comparison)"
fi

cp "$SANDBOX/deploy.sh" "$SANDBOX/deploy.sh.pristine"
: > "$SANDBOX/deploy/fantasy-platform.service"

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

# sudo: records the command, never executes it. Nothing in this harness may
# touch the real /etc.
cat > "$SHIMS/sudo" <<'SUDO'
#!/bin/bash
echo "sudo $*" >> "$SANDBOX/sudo-log"
exit 0
SUDO

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

echo "==================================================="
echo "  PASSED: $pass    FAILED: $fail"
echo "==================================================="
if [ "$fail" -eq 0 ]; then
    rm -rf "$SANDBOX"
else
    echo "sandbox kept for inspection: $SANDBOX"
fi
[ "$fail" -eq 0 ]
