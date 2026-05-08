# Impeccable Design Worktree Setup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> ⚠️ **SKILL PRESCRIPTION ENFORCEMENT — READ BEFORE STARTING:**
> This plan specifies skills at each task. Skipping a skill invocation — for any reason, including "I know the commands" — is a **plan failure**. This applies to every skill in this plan, and is most critical for `impeccable`: it carries design laws, anti-pattern rules, a preflight checklist, and context-loading logic that cannot be replicated by running commands manually. Every task that calls a skill must invoke it via the `Skill` tool and follow its output exactly. If a skill's preflight gate fails (e.g., PRODUCT.md missing, context not loaded), resolve the gate before touching any files.

**Goal:** Stand up the `design/wc-polish` git worktree and fully initialize the impeccable design studio so Brad can immediately begin logging and fixing design issues discovered during the Phase 5.5 production test script at cccfantasy.com.

**Architecture:** Git worktree at `../fantasy-design` (sibling to `~/fantasy-platform/`) linked to branch `design/wc-polish`. Impeccable context files (`PRODUCT.md`, `DESIGN.md`) created inside the worktree. Issue tracking template pre-populated and committed. All future design sessions open Claude Code from `~/fantasy-design/`.

**Tech Stack:** git worktree, impeccable skill, Flask/Jinja2, CSS custom properties (`static/css/tokens.css`, `static/css/style.css`).

---

## Files Created

| File | Location | Purpose |
|---|---|---|
| `PRODUCT.md` | worktree root | Brand/audience/strategy brief for impeccable (created by `teach`) |
| `DESIGN.md` | worktree root | Color/typography/component spec for impeccable (created by `document`) |
| `docs/superpowers/notes/wc-test-feedback.md` | worktree | Issue tracking template for Phase 5.5 test script |

All three files live on the `design/wc-polish` branch and merge into `main` when the design sprint is complete.

---

## Task 1: Create the Git Worktree ✅ COMPLETE

**Files:**
- No files created — git operation only

> **SKILL REQUIRED:** Invoke `superpowers:using-git-worktrees` first. Do not run `git worktree add` directly — `EnterWorktree` is the native harness tool (Step 1a of the skill) and must be used. Running raw git commands when a native tool exists is the #1 mistake called out in the skill. The skill also drives project setup (venv) and baseline test verification that raw git commands skip entirely.

- [x] **Step 1: Invoke the worktree skill**

In Claude Code (opened from `~/fantasy-platform/`), invoke:
```
/superpowers:using-git-worktrees
```
The skill detects you are in the main repo, checks for native tools, and uses `EnterWorktree` (not `git worktree add`) to create and enter `design/wc-polish` at `../fantasy-design`. Follow its output exactly.

- [x] **Step 2: Verify the worktree was created**

```bash
git worktree list
```

Expected output (both rows present):
```
/Users/bhagstrom/fantasy-platform   <sha>  [main]
/Users/bhagstrom/fantasy-design     <sha>  [design/wc-polish]
```

- [x] **Step 3: Verify the worktree folder has the full project**

```bash
ls ../fantasy-design/
```

Expected: same structure as `~/fantasy-platform/` — `app.py`, `games/`, `static/`, `templates/`, etc.

- [x] **Step 4: Project setup and baseline (driven by the skill)**

The `superpowers:using-git-worktrees` skill runs these. Verify they passed:

```bash
ls venv/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: venv present, full test suite passes. If tests fail, stop and investigate before proceeding.

- [x] **Step 5: Session is now inside the worktree**

`EnterWorktree` switches the session automatically. All remaining tasks run in this same session from `~/fantasy-design/`.

---

## Task 2: Run Impeccable Teach (Interactive — Brad Must Be Present)

**Files:**
- Create: `PRODUCT.md` (at worktree root, written by the skill)

> **SKILL REQUIRED — NO EXCEPTIONS:** Invoke `/impeccable teach` via the `Skill` tool. Do not synthesize PRODUCT.md manually, do not summarize assumptions, do not write it from the user's original prompt. The impeccable skill's preflight explicitly fails if PRODUCT.md is missing, empty, or placeholder. PRODUCT.md is the foundation every subsequent impeccable command (`polish`, `audit`, `layout`, etc.) reads — a bad or skipped teach poisons every design session that follows.
>
> This step is a back-and-forth conversation. Claude asks questions one at a time; Brad answers. Do not skip or rush — the output powers every impeccable command going forward.

- [ ] **Step 1: Invoke impeccable teach via the Skill tool**

In Claude Code (opened from `~/fantasy-design/`), invoke:
```
/impeccable teach
```
The skill must be loaded — do not type impeccable commands freehand. Confirm the skill output is visible before answering any questions.

- [ ] **Step 2: Answer Claude's discovery questions**

Claude will ask about these topics (answer each honestly based on cccfantasy.com):

- **Who uses this?** — A private friend group (roughly 10–30 people) running a World Cup fantasy pool. They know each other personally. They're casual sports fans, not hardcore analysts.
- **Brand register** — Product (the design serves the game, not the other way around).
- **Brand voice** — Sharp, competitive, fun. "Corrupt Commish Club" — the name has edge. Not corporate, not sanitized.
- **Visual anti-references** — Generic SaaS dashboards, gray-on-white enterprise apps, anything that looks like it came from a Bootstrap starter template.
- **Color strategy** — Committed: CCC purple/gold is the identity. World Cup adds navy/red as a game palette layered on top.
- **Strategic principles** — The site should feel like a place your friend group runs, not a product a startup built.

Answer in your own words — Claude synthesizes your answers, you don't need to match these exactly.

- [ ] **Step 3: Confirm PRODUCT.md was created**

```bash
wc -c PRODUCT.md
```

Expected: a number greater than 200 (the impeccable minimum). If the file is missing or empty, re-run `/impeccable teach`.

---

## Task 3: Run Impeccable Document (Automated)

**Files:**
- Create: `DESIGN.md` (at worktree root, written by the skill)

> **SKILL REQUIRED — NO EXCEPTIONS:** Invoke `/impeccable document` via the `Skill` tool. Do not write DESIGN.md by hand or by reading tokens.css yourself. The skill loads the full impeccable context (including PRODUCT.md from Task 2) before scanning — running the command without the skill skips that context load and produces a generic design doc that ignores the CCC brand. PRODUCT.md must exist and pass the preflight check before this step starts.

- [ ] **Step 1: Invoke impeccable document via the Skill tool**

```
/impeccable document
```

The skill scans `static/css/tokens.css` and `static/css/style.css` automatically. No input required from Brad. Confirm the skill is loaded (visible in output) before the scan begins.

- [ ] **Step 2: Review the generated DESIGN.md briefly**

Open `DESIGN.md` and do a quick sanity check:
- CCC purple and gold tokens are present
- World Cup navy (`#001A4D`) and red (`#BF0A30`) are present
- Font families are listed (check `tokens.css` for the source of truth)

If anything looks obviously wrong (e.g., no colors listed), let Claude know and it will re-scan.

- [ ] **Step 3: Confirm DESIGN.md was created**

```bash
wc -c DESIGN.md
```

Expected: a number greater than 500. If missing or near-empty, re-run `/impeccable document`.

---

## Task 4: Create the Issue Tracking Template

**Files:**
- Create: `docs/superpowers/notes/wc-test-feedback.md`

- [ ] **Step 1: Create the file with the full template**

Create `docs/superpowers/notes/wc-test-feedback.md` with this exact content:

```markdown
# WC Production Test Script — Issue & Feedback Tracker

Capture everything found during the Phase 5.5 test at cccfantasy.com. One line per issue — page/component, what you see, what you expect. Do not attempt fixes during the test. Just log.

**Scope:** Global platform pages + World Cup pages only. Golf and CFB are out of scope.

**Format:**
> `Page / Component — Observed behavior. Expected behavior.`

---

## Bug
*Scoring errors, broken logic, wrong data displayed.*
*Fix path: Bring to a Claude debug session. Use `systematic-debugging` skill.*

- [x] B0 — Tier 5 team detail — Points shown as 0 after match completion. Should reflect earned base points × multiplier. *(example — delete when adding real entries)*
- [ ] B1 — 
- [ ] B2 — 

---

## Critical
*Broken layout, unreadable text, mobile collapse.*
*Fix path: `impeccable audit` or `impeccable adapt`.*

- [x] C0 — Leaderboard (mobile) — Rank column is cut off on narrow screens. Should be fully visible at 375px viewport. *(example — delete when adding real entries)*
- [ ] C1 — 
- [ ] C2 — 

---

## Functional
*Wrong state shown, missing UI feedback, confusing flow.*
*Fix path: `impeccable clarify` or `impeccable harden`.*

- [x] F0 — Join page — No confirmation shown after enrolling. User should see a success message before being redirected. *(example — delete when adding real entries)*
- [ ] F1 — 
- [ ] F2 — 

---

## Visual Polish
*Spacing off, color inconsistency, typography rough, alignment issues.*
*Fix path: `impeccable layout`, `impeccable typeset`, or `impeccable polish`.*

- [x] P0 — Home page hero — Heading font size feels small on desktop. Should command more visual weight relative to the sub-copy. *(example — delete when adding real entries)*
- [ ] P1 — 
- [ ] P2 — 

---

## Delight
*Nice-to-have: animations, empty states, personality touches.*
*Fix path: `impeccable animate` or `impeccable delight`.*

- [x] D0 — Leaderboard — Row transitions feel instant when scores update. A subtle fade would make changes feel alive. *(example — delete when adding real entries)*
- [ ] D1 — 
- [ ] D2 — 
```

- [ ] **Step 2: Verify the file exists**

```bash
ls docs/superpowers/notes/wc-test-feedback.md
```

Expected: the path prints without error.

---

## Task 5: Commit the Setup to the Branch

**Files:**
- Commit: `PRODUCT.md`, `DESIGN.md`, `docs/superpowers/notes/wc-test-feedback.md`

- [ ] **Step 1: Confirm you are on the correct branch**

```bash
git branch
```

Expected: `* design/wc-polish` is starred. If you see `* main`, stop — you are in the wrong folder. Make sure Claude Code is opened from `~/fantasy-design/`.

- [ ] **Step 2: Stage the three new files**

```bash
git add PRODUCT.md DESIGN.md docs/superpowers/notes/wc-test-feedback.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: impeccable context + issue tracker — design studio ready"
```

Expected output: `[design/wc-polish <sha>] feat: impeccable context + issue tracker — design studio ready` with 3 files changed.

- [ ] **Step 4: Verify the branch is ahead of main**

```bash
git log --oneline main..design/wc-polish
```

Expected: the commit from Step 3 appears. If the output is empty, the commit didn't land on the right branch.

---

## Setup Complete — How to Use the Worktree

The design studio is ready. From here, the workflow is:

**During the production test (cccfantasy.com):**
- Open `~/fantasy-design/docs/superpowers/notes/wc-test-feedback.md` in any text editor
- Log issues as you find them using the format: `Page / Component — Observed. Expected.`
- Check off the placeholder row (`B1`, `C1`, etc.) and add more rows as needed

**Starting a design session:**
1. Open Claude Code from `~/fantasy-design/` (not `~/fantasy-platform/`)
2. Claude must invoke `/impeccable` via the `Skill` tool and run the context loader (`load-context.mjs`) before touching any files — this is the impeccable preflight. Skipping it means design laws, anti-patterns, and brand context are not loaded. This is a session failure, not a shortcut.
3. Tell Claude which category of issues to work on (e.g., "let's work through the Visual Polish items")
4. Claude picks the matching impeccable sub-command and invokes it (e.g., `/impeccable polish`, `/impeccable layout`) — again via the `Skill` tool, not freehand
5. Start the local dev server in a terminal: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`
6. Open `localhost:5099` alongside `cccfantasy.com` for side-by-side comparison
7. Approve, request tweaks, or reject — Claude commits each accepted change

**Starting a bug-fix session:**
1. Open Claude Code from `~/fantasy-design/`
2. Share the Bug category items
3. Claude invokes `systematic-debugging` via the `Skill` tool — no impeccable involved, but the skill must still be loaded

**Merging when done (deadline: June 1, 2026):**
1. Claude runs `ENVIRONMENT=testing venv/bin/python -m pytest tests/`, full test suite must pass
2. Run `/commit-push-pr` to open the PR: `design/wc-polish → main`
3. Wait for CodeRabbit's full review comment (not just the "processing" stub)
4. Approve and merge on GitHub
5. Run `/clean_gone` to remove the worktree and branch locally
6. Deploy: `git push origin main` then `ssh deploy@<droplet-ip>` and run `./deploy.sh`
