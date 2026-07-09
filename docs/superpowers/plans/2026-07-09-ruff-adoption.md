# Ruff Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt Ruff (curated ruleset) as the repo's linter, clean all 499 findings repo-wide, and enforce zero-findings via GitHub Actions + a Claude Code hook — one PR.

**Architecture:** Config in `ruff.toml`, tool pinned in a new `requirements-dev.txt` (dev-only; prod deploy untouched). Cleanup lands as staged commits: infra → auto-fixes → manual-mechanical → semantic-care, each gated on the full pytest suite so a bad fix is bisectable. Enforcement is `.github/workflows/lint.yml` (repo's first CI workflow) plus a check-only PostToolUse hook.

**Tech Stack:** Ruff 0.15.21 (pinned), GitHub Actions `astral-sh/ruff-action@v3`, Claude Code hooks (`$CLAUDE_TOOL_INPUT` + `jq` pattern already used in `.claude/settings.json`).

**Spec:** `docs/superpowers/specs/2026-07-09-ruff-adoption-design.md`. The spec's "3 logical commits" is refined here into 6 commits (housekeeping / config / CI+hook+docs / auto-fix / manual-mechanical / semantic-care) — finer bisection, same single-PR rollout.

## Global Constraints

- Ruff version everywhere (requirements-dev.txt, CI): exactly `0.15.21`.
- Never run `ruff check --fix --unsafe-fixes` — unsafe fixes are applied by hand or not at all.
- SQLAlchemy boolean filters: `.is_(True)` / `.is_(False)` / `.is_not(None)` — NEVER the Python-idiom rewrite (`is True`, truthiness, `is not None`), which breaks query SQL generation.
- Full suite gate after every fix commit: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q` → **1614 passed** (count as of plan date; must not drop).
- `deploy.sh`, `requirements.txt`, prod droplet: untouched.
- Branch: `platform/ruff-adoption` off `main`. Commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Baseline numbers (verify against these): 499 total findings, 411 safe-auto-fixable, ~88 manual.

---

### Task 1: Branch + .gitignore housekeeping

**Files:**
- Modify: `.gitignore` (append `.ruff_cache/`; also commits the pre-existing uncommitted Codex block from 2026-07-08 — finished work approved for inclusion during planning)

**Interfaces:**
- Produces: branch `platform/ruff-adoption`; `.ruff_cache/` ignored so later `ruff check .` runs don't pollute `git status`.

- [x] **Step 1: Create branch**

```bash
cd /Users/bhagstrom/fantasy-platform && git checkout -b platform/ruff-adoption
```

- [x] **Step 2: Append `.ruff_cache/` to `.gitignore`**

Append to the end of `.gitignore` (after the existing uncommitted Codex block, which stays as-is):

```
# Ruff linter cache
.ruff_cache/
```

- [x] **Step 3: Commit (includes the pre-existing Codex block)**

```bash
git add .gitignore
git commit -m "chore(gitignore): ignore .ruff_cache; commit Codex CLI artifact block

The Codex block (.agents/, .codex/, AGENTS.md) is finished 2026-07-08 work
that was never committed; folding it in here so the Ruff PR diff stays clean.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: `git status` shows a clean tree.

---

### Task 2: Ruff config + dev requirements

**Files:**
- Create: `ruff.toml`
- Create: `requirements-dev.txt`

**Interfaces:**
- Produces: `venv/bin/ruff` (0.15.21) runnable; `ruff.toml` consumed by every later task, the CI workflow, and the hook.

- [x] **Step 1: Create `ruff.toml`** (exact content):

```toml
target-version = "py313"
# Hook and CI pass explicit file paths; force-exclude keeps `extend-exclude`
# effective even for directly-named files (e.g. a migrations/ file).
force-exclude = true
extend-exclude = ["migrations"]

[lint]
select = [
    "E4", "E7", "E9", "F",   # ruff defaults: pyflakes + core pycodestyle errors
    "I",                     # import sorting
    "B",                     # bugbear — bug-catchers
    "UP",                    # pyupgrade — modern 3.13 idioms
    "SIM",                   # flake8-simplify
    "C4",                    # comprehension cleanups
    "RUF012", "RUF013",      # mutable class defaults, implicit Optional
]

[lint.per-file-ignores]
"**/__init__.py" = ["F401"]  # re-export pattern (models/, games/*/services/)

[lint.isort]
known-first-party = ["app", "config", "extensions", "models", "utils", "core", "games", "tests"]
```

- [x] **Step 2: Create `requirements-dev.txt`** (exact content):

```
-r requirements.txt
ruff==0.15.21
```

- [x] **Step 3: Install into the venv**

```bash
venv/bin/pip install -r requirements-dev.txt && venv/bin/ruff --version
```

Expected: `ruff 0.15.21`.

- [x] **Step 4: Verify baseline finding counts (the "failing test" for this PR)**

```bash
venv/bin/ruff check . --statistics | tail -3
```

Expected: `Found 499 errors.` and `411 fixable with the --fix option`. (Small drift is fine only if `main` moved since 2026-07-09; investigate any large delta before proceeding.)

- [x] **Step 5: Commit**

```bash
git add ruff.toml requirements-dev.txt
git commit -m "chore(lint): add Ruff 0.15.21 — curated ruleset config + dev requirements

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: CI workflow + Claude Code hook + CLAUDE.md

**Files:**
- Create: `.github/workflows/lint.yml`
- Modify: `.claude/settings.json` (append one entry to the existing `PostToolUse` array)
- Modify: `CLAUDE.md:82` ("No linter configured…" line) and the Timestamps convention bullet

**Interfaces:**
- Consumes: `ruff.toml` + pinned version from Task 2.
- Produces: CI gate on PRs/main; in-session lint feedback on `*.py` edits.

- [x] **Step 1: Create `.github/workflows/lint.yml`** (exact content):

```yaml
name: Lint

on:
  pull_request:
  push:
    branches: [main]

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/ruff-action@v3
        with:
          version: "0.15.21"
          args: "check"
```

- [x] **Step 2: Add the hook to `.claude/settings.json`**

Append this object to the existing `PostToolUse` array (after the smoke-test entry — do not modify the existing entries):

```json
{
  "matcher": "Edit|Write",
  "hooks": [
    {
      "type": "command",
      "command": "fp=$(echo \"$CLAUDE_TOOL_INPUT\" | jq -r '.file_path // empty'); root=$(git rev-parse --show-toplevel 2>/dev/null); if [ -n \"$root\" ] && [ -n \"$fp\" ]; then case \"$fp\" in \"$root\"/*.py) out=$(\"$root/venv/bin/ruff\" check --no-cache \"$fp\" 2>&1) || { echo \"$out\" 1>&2; exit 2; } ;; esac; fi"
    }
  ]
}
```

Design notes baked in: check-only (never `--fix` — a hook rewriting files causes editor state mismatches); `--no-cache` so hook runs never create `.ruff_cache/`; exit 2 returns findings to Claude as blocking feedback; `force-exclude` in ruff.toml keeps `migrations/` files silent even when passed explicitly.

- [x] **Step 3: Verify settings.json is still valid JSON**

```bash
jq . .claude/settings.json > /dev/null && echo JSON-OK
```

Expected: `JSON-OK`.

- [x] **Step 4: Test the hook by manual simulation**

(Hook config is snapshotted at session start, so live firing begins next session — simulate now:)

```bash
printf 'import os\n' > /tmp/ruff_hook_test.py
CLAUDE_TOOL_INPUT='{"file_path": "'"$(git rev-parse --show-toplevel)"'/app.py"}' sh -c "$(jq -r '.hooks.PostToolUse[1].hooks[0].command' .claude/settings.json)"; echo "exit=$?"
```

Expected while findings still exist in `app.py`-adjacent code: findings printed + `exit=2` (or `exit=0` if `app.py` is already clean — then re-test against any file listed in `venv/bin/ruff check . --statistics`). Also verify a non-`.py` path exits 0:

```bash
CLAUDE_TOOL_INPUT='{"file_path": "/Users/bhagstrom/fantasy-platform/CLAUDE.md"}' sh -c "$(jq -r '.hooks.PostToolUse[1].hooks[0].command' .claude/settings.json)"; echo "exit=$?"
```

Expected: no output, `exit=0`. Clean up: `rm /tmp/ruff_hook_test.py`.

- [x] **Step 5: Update CLAUDE.md**

(a) Replace line 82 — `No linter configured. No pyright either — verify code with pytest.` — with:

```markdown
**Linting: Ruff** (pinned in `requirements-dev.txt`, config in `ruff.toml` — curated ruleset; no E501, no formatter). `venv/bin/ruff check .` must exit clean; `venv/bin/ruff check --fix .` applies safe autofixes. Enforced by `.github/workflows/lint.yml` (PRs + main) and a check-only PostToolUse hook on `*.py` edits. Two conventions: SQLAlchemy boolean filters use `.is_(True)`/`.is_(False)`/`.is_not(None)` — never `== True` (E712) and never the Python-idiom rewrite, which silently breaks the query; `__init__.py` re-exports are covered by a per-file-ignore (F401), not `noqa` comments. No pyright — verify behavior with pytest.
```

(b) Update the Timestamps convention bullet (UP017 autofix rewrites `timezone.utc` → `datetime.UTC` repo-wide in Task 4): change `**Timestamps:** \`datetime.now(timezone.utc)\` — never \`utcnow()\`` to:

```markdown
- **Timestamps:** `datetime.now(UTC)` (`from datetime import UTC`; Ruff UP017 enforces over `timezone.utc`) — never `utcnow()`
```

- [x] **Step 6: Commit**

```bash
git add .github/workflows/lint.yml .claude/settings.json CLAUDE.md
git commit -m "ci(lint): Ruff workflow on PRs/main + check-only Claude hook; document conventions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Auto-fix pass (411 findings)

**Files:**
- Modify: ~100 files repo-wide (mechanical; no hand edits in this task)

**Interfaces:**
- Consumes: `ruff.toml` from Task 2.
- Produces: repo with only the ~88 manual findings remaining, listed for Tasks 5–6.

- [x] **Step 1: Run the safe auto-fix twice** (second run catches fixes unlocked by the first, e.g. an import made unused by a `UP` rewrite):

```bash
venv/bin/ruff check . --fix > /dev/null; venv/bin/ruff check . --fix --statistics
```

Expected: ~88 findings remain, none marked `[*]`.

- [x] **Step 2: Spot-check the diff by category** (not line-by-line — one representative example per fixed rule):

```bash
git diff --stat | tail -3
git diff -- games/worldcup/services/state.py   # UP017: timezone.utc → UTC
git diff -- models/user.py                      # I001 import sort respects first-party grouping
```

Verify: `datetime.now(UTC)` rewrites carry the `UTC` import; import blocks group stdlib / third-party / first-party correctly (`games`, `core`, etc. in the first-party block — if not, `known-first-party` is wrong; stop and fix `ruff.toml`).

- [x] **Step 3: Full suite gate**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: `1614 passed`. Any failure: `git checkout -- <file>` the offending fix, re-run, and move that finding to Task 6's judgment list.

- [x] **Step 4: Commit**

```bash
git add -A
git commit -m "style(lint): apply Ruff safe autofixes repo-wide (411 findings)

ruff check . --fix, run twice for cascades. No --unsafe-fixes, no hand edits.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Manual-mechanical fixes (~60 findings)

**Files:**
- Modify: files listed by `venv/bin/ruff check . --output-format concise` for the rules below
- Test: existing suite (no new tests — lint-only changes)

**Interfaces:**
- Consumes: post-autofix repo from Task 4.
- Produces: repo where only the Task 6 judgment rules remain.

Rules in scope — mechanical even though Ruff won't auto-fix them:
- **E702 (24):** split `a; b` statements onto separate lines.
- **F841 (11):** unused variable — delete the assignment if the value is unused, or rename to `_` when unpacking requires a slot.
- **F401 remainder (unsafe subset):** verify each import is truly unused (`grep` the name in-file), then delete.
- **B007 (6):** unused loop variable — rename to `_` (or `_name` if the name aids readability).
- **B905 (2):** add `strict=False` to `zip(...)` — explicit and behavior-preserving; do NOT use `strict=True` (behavior change).
- **E741 (3):** rename ambiguous `l`/`I`/`O` variables to a descriptive name; scope-local rename only.
- **C416 (3), SIM102 (4), SIM105 (1), SIM108 (2), SIM117 (5), UP031 (2), UP035 remainder:** apply the rule's suggested rewrite; each is a local, semantics-preserving transform. For SIM117, merge nested `with` statements into one parenthesized `with` (common in test `patch` stacks).

- [x] **Step 1: Enumerate the worklist**

```bash
venv/bin/ruff check . --select E702,F841,F401,B007,B905,E741,C416,SIM102,SIM105,SIM108,SIM117,UP031,UP035 --output-format concise
```

- [x] **Step 2: Fix every listed finding per the rules above**

- [x] **Step 3: Verify only judgment rules remain**

```bash
venv/bin/ruff check . --statistics
```

Expected remaining: only `E402` (8), `E711` (1), `E712` (4), `B023` (2), `RUF012` (6), `RUF013` (2) — ~23 findings.

- [x] **Step 4: Full suite gate**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: `1614 passed`.

- [x] **Step 5: Commit**

```bash
git add -A
git commit -m "style(lint): manual mechanical fixes — semicolons, unused vars/imports, sim/comprehension rewrites

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Semantic-care fixes (~23 findings) → zero

**Files:**
- Modify: `games/cfb/utils.py:219`, `games/golf/cli.py:184,298`, `games/golf/services/sync.py:140,389,1135`, `games/worldcup/services/sync.py:412`, `games/registry.py:36-38`, `games/worldcup/models.py:80`, `config.py:83`, `tests/test_logo_assets.py`, `tests/test_cfb_odds_api.py:18`, `tests/test_worldcup_sync.py:57,75,129`

**Interfaces:**
- Consumes: post-Task-5 repo.
- Produces: `venv/bin/ruff check .` exits 0.

Each fix, with the exact transform:

- [x] **Step 1: E712/E711 → SQLAlchemy `.is_()` idiom (5 sites)**

`games/cfb/utils.py:219`:
```python
# before
.filter(CfbWeek.is_playoff_week == True, CfbGame.home_team_won != None)
# after
.filter(CfbWeek.is_playoff_week.is_(True), CfbGame.home_team_won.is_not(None))
```

`games/golf/cli.py:184,298` and `games/golf/services/sync.py:1135` (same pattern ×3):
```python
# before
GolfTournament.results_finalized == False
# after
GolfTournament.results_finalized.is_(False)
```

- [x] **Step 2: B023 — loop-closure in `games/worldcup/services/sync.py:412`**

```python
# before (closes over loop-scoped `rows`)
def fifa(i):
    return _fifa_for_tla(rows[i]['team']['tla']) if len(rows) > i else None
# after (bind at definition time — behavior-identical because fifa is only
# called within the same loop iteration, but now provably so)
def fifa(i, rows=rows):
    return _fifa_for_tla(rows[i]['team']['tla']) if len(rows) > i else None
```

First CONFIRM `fifa` is only called inside the same iteration (read the enclosing loop body); if it escapes the iteration, this is a live bug — fix the capture and add a regression test before proceeding.

- [x] **Step 3: E402 (8 sites)**

`games/registry.py:36-38`: imports below module-level code. If moving them to the top creates a circular import (likely — registry imports game services), keep in place with a reason:
```python
from games.worldcup.services.enrollment import get_enrollment as wc_get_enrollment  # noqa: E402 — must follow GameRegistryEntry definition (circular import)
```
`tests/test_logo_assets.py` (5 sites): section-style test file with interleaved imports. Move imports to the top if the file still reads clearly; otherwise same `# noqa: E402 — <reason>` treatment. Never a bare `noqa`.

- [x] **Step 4: RUF012 (6) — `ClassVar` annotations**

`config.py:83`:
```python
from typing import ClassVar
...
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
```
Same pattern for `games/worldcup/models.py:80` and the three test stub classes (`tests/test_cfb_odds_api.py:18`, `tests/test_worldcup_sync.py:57,75,129`). CAUTION at `games/worldcup/models.py:80`: if the attribute is a SQLAlchemy model-class attribute, verify the annotation doesn't interact with declarative mapping — if it's a mapped construct, `RUF012` is a false positive there; use a targeted `# noqa: RUF012 — declarative mapping attribute` instead.

- [x] **Step 5: RUF013 (2) — explicit Optional in `games/golf/services/sync.py:140,389`**

```python
# before
def f(arg: str = None):
# after
def f(arg: str | None = None):
```

- [x] **Step 6: Zero-findings check**

```bash
venv/bin/ruff check .
```

Expected: `All checks passed!`

- [x] **Step 7: Full suite gate** (golf/cfb suites cover the `.is_()` query sites)

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: `1614 passed`.

- [x] **Step 8: Commit**

```bash
git add -A
git commit -m "fix(lint): semantic-care fixes — SQLAlchemy .is_() filters, loop-closure binding, ClassVar/Optional annotations, justified noqas

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: PR, CI verification, CodeRabbit cycle, merge

**Files:** none (process task)

**Interfaces:**
- Consumes: 6 commits from Tasks 1–6 on `platform/ruff-adoption`.
- Produces: merged PR; live CI + hook enforcement on `main`.

- [x] **Step 1: Push and open the PR**

```bash
git push -u origin platform/ruff-adoption
gh pr create --title "Adopt Ruff: curated ruleset, repo-wide cleanup, CI + hook enforcement" --body "$(cat <<'EOF'
## Summary
- Ruff 0.15.21 (pinned) with a curated ruleset (`ruff.toml`): defaults + I/B/UP/SIM/C4 + RUF012/RUF013 — no E501, no formatter (see spec: docs/superpowers/specs/2026-07-09-ruff-adoption-design.md)
- Repo-wide cleanup: 499 findings → 0 (411 safe autofixes + manual passes), staged commits, suite green after each
- Enforcement: first CI workflow (.github/workflows/lint.yml, PRs + main) + check-only Claude Code PostToolUse hook
- Replaces CodeRabbit's mechanical-lint layer ahead of eventual CR cancellation

## Test plan
- [x] `venv/bin/ruff check .` → All checks passed!
- [x] `ENVIRONMENT=testing pytest tests/` → 1614 passed after each fix commit
- [x] Lint workflow green on this PR
- [x] Hook verified by manual simulation (live firing starts next session — hook config snapshots at session start)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 2: Verify the Actions lint job runs green on this PR** (this proves the CI wiring before merge)

```bash
gh pr checks --watch
```

Expected: `Lint / ruff` → pass.

- [x] **Step 3: CodeRabbit cycle** — load `superpowers:receiving-code-review`; address comments with technical rigor (CR may flag the `noqa`s — the justifications are in the comments; CR's Ruff runs the same `ruff.toml`, so no tool disagreement). Re-request review after every fix push; merge only when CR's LATEST review is APPROVED with 0 actionable comments.

- [x] **Step 4: Merge (house style)**

```bash
gh pr merge --merge --delete-branch
```

- [x] **Step 5: Post-merge verification on main**

```bash
git checkout main && git pull
venv/bin/ruff check . && ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: `All checks passed!` + `1614 passed`. Confirm the push-to-main lint run is green: `gh run list --workflow=lint.yml --limit 1`.
