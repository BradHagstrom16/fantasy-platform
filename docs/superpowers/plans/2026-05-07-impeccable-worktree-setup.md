# Impeccable Design Worktree Setup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

## Task 1: Create the Git Worktree

**Files:**
- No files created — git operation only

> **Note:** This task uses the `superpowers:using-git-worktrees` skill to handle all git complexity. Brad does not need to run git commands manually.

- [ ] **Step 1: Invoke the worktree skill**

In Claude Code (opened from `~/fantasy-platform/`), type:
```
/superpowers:using-git-worktrees
```
Follow the skill's prompts. When asked for branch name, use `design/wc-polish`. When asked for worktree path, use `../fantasy-design`.

- [ ] **Step 2: Verify the worktree was created**

```bash
git worktree list
```

Expected output (both rows present):
```
/Users/bhagstrom/fantasy-platform   <sha>  [main]
/Users/bhagstrom/fantasy-design     <sha>  [design/wc-polish]
```

- [ ] **Step 3: Verify the worktree folder has the full project**

```bash
ls ../fantasy-design/
```

Expected: same structure as `~/fantasy-platform/` — `app.py`, `games/`, `static/`, `templates/`, etc.

- [ ] **Step 4: Close this Claude Code session and reopen from the worktree**

Close Claude Code. Reopen it, setting the working directory to `~/fantasy-design/`. All remaining tasks in this plan run from that session.

---

## Task 2: Run Impeccable Teach (Interactive — Brad Must Be Present)

**Files:**
- Create: `PRODUCT.md` (at worktree root, written by the skill)

> **Important:** This step is a back-and-forth conversation. Claude will ask questions about cccfantasy.com one at a time; Brad answers each one. Do not skip or rush this — the output powers every impeccable command going forward.

- [ ] **Step 1: Invoke impeccable teach**

In Claude Code (opened from `~/fantasy-design/`), type:
```
/impeccable teach
```

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

- [ ] **Step 1: Invoke impeccable document**

```
/impeccable document
```

Claude will scan `static/css/tokens.css` and `static/css/style.css` automatically. No input required from Brad.

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
2. Tell Claude which category of issues to work on (e.g., "let's work through the Visual Polish items")
3. Claude picks the right impeccable command and runs it
4. Start the local dev server in a terminal: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`
5. Open `localhost:5099` alongside `cccfantasy.com` for side-by-side comparison
6. Approve, request tweaks, or reject — Claude commits each accepted change

**Starting a bug-fix session:**
1. Open Claude Code from `~/fantasy-design/`
2. Share the Bug category items
3. Claude uses the `systematic-debugging` skill — no impeccable involved

**Merging when done (deadline: June 1, 2026):**
1. Claude runs `ENVIRONMENT=testing venv/bin/python -m pytest tests/` — all 264 tests must pass
2. Claude runs `venv/bin/pyright` — 0 errors
3. Run `/commit-push-pr` to open the PR: `design/wc-polish → main`
4. Wait for CodeRabbit's full review comment (not just the "processing" stub)
5. Approve and merge on GitHub
6. Run `/clean_gone` to remove the worktree and branch locally
7. Deploy: `git push origin main` then `ssh deploy@<droplet-ip>` and run `./deploy.sh`
