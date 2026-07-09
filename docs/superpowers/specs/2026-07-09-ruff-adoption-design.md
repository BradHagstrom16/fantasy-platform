# Ruff Adoption — Design

**Date:** 2026-07-09
**Status:** Approved
**Motivation:** Adopt Ruff as the repo's linter and clean the whole repo to zero findings, replacing CodeRabbit's mechanical-lint layer ahead of an eventual CR cancellation. CR's semantic-review layer is covered separately by `/code-review`. This supersedes the 2026-07-08 "changed-lines-only" scoping note — the sized cleanup (~440 findings, majority auto-fixable) is small enough that a full pass plus whole-repo enforcement is simpler than changed-line filtering.

## Baseline (Ruff 0.15.21, repo-wide, 198 source files)

| Rule group | Findings | Disposition |
|---|---|---|
| Defaults (F + E4/E7/E9) | 124 | Adopt |
| `I` import sorting | 208 (100% auto-fixable) | Adopt |
| `B` bugbear | 10 | Adopt |
| `UP` pyupgrade | 73 | Adopt |
| `SIM` + `C4` | 17 | Adopt |
| `RUF012`/`RUF013` | 8 | Adopt (cherry-picked) |
| `E501` line-too-long | 1147 @ 88 chars / 240 @ 120 | **Excluded** — cosmetic, high-churn |
| Other `RUF` (unicode etc.) | ~183 | **Excluded** — false positives on CCC glyphs/prose |

Guiding principle: every enabled rule is a standing contract on all future diffs — enable only rules whose findings are trustworthy (real bug risk, genuine modernization, or free auto-fix). Ratcheting up later is one config line + a small cleanup PR.

## 1. Configuration

**File:** `ruff.toml` at repo root (no `pyproject.toml` exists; single-purpose file avoids packaging ambiguity; CodeRabbit's Ruff integration reads the same config during the overlap period).

```toml
target-version = "py313"
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
known-first-party = ["app", "config", "extensions", "models", "utils", "core", "games"]
```

- `migrations/` excluded: Alembic-generated, reviewed once at generation, template noise otherwise. `venv/`, `_migration_source/`, `instance/` are covered because Ruff respects `.gitignore` by default.
- `known-first-party` is required for correct import-sort classification of the repo's top-level packages across all 208 `I001` fixes.
- **Install:** `ruff==0.15.21` pinned in a new `requirements-dev.txt` (first line `-r requirements.txt`), installed into the venv. `deploy.sh` continues installing `requirements.txt` only — no lint tooling on the droplet.

## 2. Repo-wide cleanup (rollout: one PR, staged commits)

Single PR, three logical commits, one CodeRabbit cycle carried to merge in-session.

- **Commit 1 — infrastructure:** `ruff.toml`, `requirements-dev.txt`, CI workflow, Claude Code hook, CLAUDE.md updates.
- **Commit 2 — auto-fixes (~350):** `venv/bin/ruff check --fix .` — safe fixes only (`--unsafe-fixes` is never used). Covers all `I001`, `F541`, most `UP`/`SIM`/`C4`, and whatever subset of `F401` Ruff deems safe to auto-delete. The exact auto/manual split is whatever `--fix` takes; the remainder rolls into commit 3.
- **Commit 3 — manual fixes (~90):**
  - `F401` remainder outside `__init__.py` (mostly tests): verify unused, delete.
  - `E712`/`E711` (5 sites, golf + cfb): SQLAlchemy boolean filters → `.is_(True)` / `.is_(False)` ORM idiom. **Never** the Python-idiom rewrite (`is True` / truthiness), which silently breaks the query — this is why Ruff marks the fix unsafe. Paths covered by golf/cfb suites.
  - `E702` semicolons (24): split lines.
  - `F841` unused variables (11): case-by-case — delete dead code or rename to `_`.
  - `E402` late imports (8): deliberate (circular-import avoidance) → inline `# noqa: E402` with reason; accidental → move to top.
  - `RUF012` (6) / `RUF013` (2): `ClassVar` / explicit `Optional` annotations; confirm no behavior change around Flask config classes.

**Verification gate:** `ruff check .` exits 0, and the full suite (`ENVIRONMENT=testing venv/bin/python -m pytest tests/`, 1603 tests) is green after commit 2 and again after commit 3, so a bad fix is bisectable to its commit.

## 3. Enforcement

- **GitHub Actions** — `.github/workflows/lint.yml`, the repo's first CI workflow. Triggers: every `pull_request` + `push` to `main`. One job: checkout, then `astral-sh/ruff-action` pinned to the same Ruff version as `requirements-dev.txt` (CI can never disagree with local). Lint-only — pytest-in-CI is a separate future decision.
- **Claude Code hook** — `PostToolUse` hook in `.claude/settings.json` (alongside the existing .env-protection and smoke-test hooks). After Edit/Write to a `*.py` file, run `venv/bin/ruff check` on that file; findings are returned as blocking feedback so Claude fixes them in-session. **Check-only, never auto-fix** — a hook that rewrites files behind the editor causes state mismatches on subsequent edits.
- **CodeRabbit overlap:** CR runs Ruff as a built-in linter reading repo config, so it enforces the identical ruleset until canceled. Nothing in this design depends on the cancellation date.

## 4. Documentation & success criteria

**CLAUDE.md:** replace the "No linter configured" line — document `venv/bin/ruff check .` / `--fix`, `requirements-dev.txt`, config location, and two conventions: SQLAlchemy boolean filters use `.is_(True/False)`; `__init__.py` re-exports rely on the per-file-ignore, not `noqa` comments.

**Success criteria:**
1. `venv/bin/ruff check .` exits 0 repo-wide.
2. Full suite green (1603 tests) after the auto-fix commit and after the manual commit.
3. The lint workflow runs green on the PR itself before merge.
4. The Claude hook demonstrably fires on a `.py` edit in-session.

## Non-goals

- `ruff format` (whole-repo reformatter) — separate future decision.
- `E501` and broad `RUF` (unicode) rules — excluded by design; revisit by adding a config line + small cleanup PR.
- pytest in CI, pre-commit framework, `deploy.sh`/prod changes — untouched.
- Canceling CodeRabbit — user's call, on their timeline.
