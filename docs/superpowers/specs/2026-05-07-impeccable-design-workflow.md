# Impeccable Design and Production Test Script Feedback Workflow — Spec

**Date:** 2026-05-07
**Scope:** Global platform pages + World Cup pages only (Golf and CFB excluded)
**Goal:** Collect, categorize, and fix design issues discovered during the Phase 5.5 production test script along with Impeccable utilization and processes then merge to main before World Cup user signups open.

---

## Git Structure

**Branch:** `design/wc-polish`
**Worktree:** `../fantasy-design` (sibling folder to `~/fantasy-platform/`)

```
~/fantasy-platform/    ← main branch, always clean, reflects production
~/fantasy-design/      ← design/wc-polish branch, the design studio
```

All design work happens in `~/fantasy-design/`. The `~/fantasy-platform/` folder is never touched during this phase. The `using-git-worktrees` superpowers skill handles worktree creation — no manual git commands required.

On completion, one PR merges `design/wc-polish` → `main`. The worktree and branch are cleaned up via `/clean_gone`.

---

## Impeccable Setup (One-Time, First Session)

Before any design changes, two impeccable setup commands run in the worktree:

### `/impeccable teach`
Claude interviews the user about cccfantasy.com: audience (friend group playing the pool), brand voice (CCC — sharp, competitive, fun), visual references, and strategic principles. Output: `PRODUCT.md` at the project root.

### `/impeccable document`
Claude scans `static/css/tokens.css` and `static/css/style.css` and auto-generates `DESIGN.md` documenting the color system, typography, component patterns, and CCC brand tokens.

Both files live in the `design/wc-polish` branch and merge into `main` with the rest of the design work. Every future Claude design session loads them automatically via the impeccable context loader — no re-running required after the first session.

---

## Issue Capture Document

Claude Code creates the issue tracking document at:

```
docs/superpowers/notes/wc-test-feedback.md
```

This is the single source of truth for **everything** found during the Phase 5.5 test script — design issues and code bugs alike. Five categories cover the full range:

| Category | What goes here | How it gets fixed |
|---|---|---|
| **Bug** | Scoring errors, broken logic, wrong data displayed | `systematic-debugging` skill + normal code session |
| **Critical** | Broken layout, unreadable text, mobile collapse | `impeccable audit`, `impeccable adapt` |
| **Functional** | Wrong state shown, missing feedback, confusing flow | `impeccable clarify`, `impeccable harden` |
| **Visual Polish** | Spacing off, color inconsistency, typography rough | `impeccable layout`, `impeccable typeset`, `impeccable polish` |
| **Delight** | Nice-to-have: animations, empty states, personality | `impeccable animate`, `impeccable delight` |

Each entry: one line with page/component, observed behavior, and expected behavior. No fix required — that is determined in the session with Claude.

Bug category items skip impeccable entirely and are handled in a separate debugging session. Design categories (Critical through Delight) go through the impeccable design iteration loop.

Claude creates the template (pre-populated with headers, instructions, and example entries per category) as the first task of the implementation plan.

---

## Design Iteration Loop

Each design session after the test script follows this repeating cycle:

```
1. Open Claude Code in ~/fantasy-design/
2. Share the issue list (or a category subset)
3. Claude selects the matching impeccable command and executes it
4. Local dev server runs at localhost:5099 for visual review
5. User approves, requests tweaks, or rejects
6. Repeat until the category is resolved
7. Claude commits changes to design/wc-polish branch
```

Two browser tabs for side-by-side comparison during review:
- `cccfantasy.com` — production (what users see now)
- `localhost:5099` — design branch (what is being built)

Claude handles all git commits inside the worktree. No manual git commands required from the user.

---

## Merge Strategy

When all design issues are resolved:

1. Claude runs the full test suite, all tests must pass
2. `/commit-push-pr` opens a PR: `design/wc-polish → main`
3. Wait for CodeRabbit's full review (not just the processing stub) before merging
4. User approves and merges
5. `/clean_gone` removes the worktree and branch
6. User deploys: `git push origin main` locally, then `ssh deploy@<droplet-ip> ./deploy.sh`

**Merge deadline:** Before World Cup user signups open (June 1st 2026 at the latest).

---

## Session-to-Session Continuity

- Impeccable context (`PRODUCT.md` / `DESIGN.md`) loads automatically each session via the impeccable skill's context loader — no re-running `teach` or `document`
- Issue doc at `docs/superpowers/notes/wc-test-feedback.md` is the persistent backlog — add to it any time during testing, work through it in design or debugging sessions
- Claude Code must be opened from `~/fantasy-design/` (not `~/fantasy-platform/`) for all design sessions
