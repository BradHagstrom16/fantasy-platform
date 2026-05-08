# Impeccable Design Improvement Project — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended)
> For In line execution use: `superpowers:executing-plans`  Steps use checkbox (`- [ ]`) syntax for tracking. **The user manually `/clear`s between sessions; each session is designed to be self-contained.** Meticulously decide for a given task whether inline or subagent is better.

**Goal:** Apply `impeccable` design discipline to every public-facing CCC surface — every World Cup state (live > pre > post), all global chrome (auth, errors, base layout). Eliminate the systemic anti-patterns surfaced in the WC leaderboard exemplar critique (Tier 1 baseline) and execute per-page `critque` / `shape` / `clarify` / `adapt` work across each cluster, then run a final `polish` pass.

**Architecture:** Single multi-session plan structured as **Phases (P0–P6)** containing **Sessions (S\*.\*)**. Each session is a single Claude Code chat — context-isolated, prerequisites noted at the top of the session, deliverables and verification at the bottom. The user `/clear`s between sessions and points the new session at this plan plus the session ID. Phases break at meaningful milestones (cross-cutting fixes complete, a cluster complete, etc.) and each phase ends with a PR to keep review batches manageable.

**Tech Stack:** Flask 3 + Jinja2 + Bootstrap 5.3 + custom CCC tokens/components (`static/css/tokens.css` + `static/css/style.css`). Verification is **hybrid**: pytest source-pattern locks + Flask test-client HTML assertions for cheap CI regression, and the **Playwright MCP plugin** (`mcp__plugin_playwright_playwright__*`) for in-session computed-style probes, tap-target measurements, axe a11y scans, and visual smoke. Design discipline via `impeccable` skill v2.1.8, anchored to `PRODUCT.md` (register: product) and `DESIGN.md` (Tribune North Star).

---

## 0. Project overview

### 0.1 Surface in scope (~38 templates)

**Excluded entirely:** Golf and CFB blueprints (out of use per user direction). Their templates are not touched by any session in this plan.

**Live state surfaces (highest priority):**
- `games/worldcup/templates/worldcup/leaderboard.html` (Tier 1 exemplar — already critiqued; closing in P1)
- `games/worldcup/templates/worldcup/home_shell.html` + `_home_live.html`
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/team_detail.html`
- `games/worldcup/templates/worldcup/stats.html`
- `games/worldcup/templates/worldcup/player_detail.html`
- Live-bearing core/main partials: `_dossier_card.html`, `_fixture_card.html`, `_recent_results.html`

**Pre-live state surfaces:**
- `games/worldcup/templates/worldcup/_home_pre.html` + `_home_out.html`
- `games/worldcup/templates/worldcup/picks.html` + `_pick_row.html` + `_pick_accordion_script.html`
- `games/worldcup/templates/worldcup/join.html`
- `games/worldcup/templates/worldcup/rules.html`
- `games/worldcup/templates/worldcup/groups.html`
- Pre-bearing core/main partials: `_countdown_card.html`, `_ballot_card.html`, `_join_cta_card.html`, `_submit_picks_cta.html`, `_view_cta_card.html`, `_game_tiles_compact.html`, `_game_card.html`

**Post-live state surfaces:**
- `games/worldcup/templates/worldcup/_home_post.html`
- core/main partials: `_champion_banner.html`, `_dispatches.html`, `_commish_note.html`

**Global chrome / auth / errors:**
- `templates/base.html`
- `templates/errors/404.html`, `500.html`
- `core/auth/templates/auth/login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `change_password.html`, `profile.html`
- `core/main/templates/main/index.html`

**Admin pages:** explicitly out of scope per your direction during scoping. Add to a future plan if/when the admin UX needs the same treatment.

### 0.2 Priority order (locked from user direction)

1. **Live state** — leaderboard movement, results, in-progress games. Highest emotional density and highest user time-on-page.
2. **Global chrome / auth / errors** — important for first impression, low-frequency once a user is logged in.
3. **Pre-live state** — pick/join/rules. The acquisition and roster-craft window.
4. **Post-live state** — recap, champion, archive. Lowest interaction frequency but defines the closing emotional moment.

### 0.3 Phase structure (~22-26 sessions)

Phase ordering follows §0.2 priority. Live state goes first because it's the highest emotional density; global chrome is second because every page inherits it; pre-live and post-live follow. Final polish closes the project.

| Phase | Sessions | Focus | Output |
|---|---|---|---|
| **P0** Cross-cutting harden | 3 | Bootstrap shadow leak, side-stripe ban migration, mobile tap-target floor, white-on-gold contrast, em-dash sweep, table semantics | PR at end of phase |
| **P1** Leaderboard close | 1 | Shape Your Standing, trend rank-delta, clarify copy, mobile card-as-link, empty state | PR at end of phase |
| **P2** Live state cluster | 6 | home_shell+_home_live, schedule, team_detail, stats, player_detail, cluster polish | PR at end of phase |
| **P3** Global chrome + auth + errors | 4 | base layout, auth pages, errors, platform home | PR at end of phase |
| **P4** Pre-live state cluster | 5 | _home_pre/_home_out, picks, join, rules, groups, cluster polish | PR at end of phase |
| **P5** Post-live state cluster | 3 | _home_post + post-state partials, cluster polish | PR at end of phase |
| **P6** Final polish + scorecard | 2 | `$impeccable polish` across the surface, re-critique Tier 1 exemplars, document score lift | Final PR + merge `design/wc-polish` to `main` |

### 0.4 Backlog (living section)

When a session surfaces a finding outside its scope, append it here with the session ID that found it. Future sessions in the same cluster pick up the relevant items.

- **[S0.2]** `groups.html:10` lead copy uses `&mdash;` HTML entity (`12 groups &mdash; 48 teams &mdash; 2026 FIFA World Cup`) — em-dash sweep target. Picked up by **S0.3**.
- **[S0.2]** `leaderboard.html:85` trend dash placeholder renders an em-dash glyph (`<span class="text-muted">—</span>`) — em-dash sweep target. Picked up by **S0.3**.
- **[S0.3]** `.navbar-brand` renders 68×38 at 375 viewport across every page (height-only fail, 6px short). Mobile-first 44×44 floor target. Self-contained CSS fix; defer to **P3 S3.1** (Global chrome) where the navbar is the focus.
- **[S0.3]** `/login` link rows ("Forgot your password?" 128×14, "Create an account" 116×37) fail the 44×44 floor. Self-contained auth-page CSS adjustment; defer to **P3 S3.2** (Auth surfaces).
- **[S0.3]** Navbar trophy CTA: chamber-purple text on `--metal-gold-flat` lands at 3.6:1 against the gradient's darkest stop (`--gold-dark` = `#8A6A1A`) at the bottom-right corner of the button. AA-passing across most of the surface (7.5:1 mid-stop, 12.4:1 lightest), but the worst-stop pixel-corner reads 3.6:1 — below the 4.5:1 normal-text floor. Fix requires retuning `--metal-gold-flat`'s dark stop in `tokens.css`, which is a DESIGN.md token spec change and out of scope for S0.3. Pick up in **P6 S6.1** (cross-surface polish) or as a one-off DESIGN.md spec session if a critique re-surfaces it earlier.

---

## 1. Cross-session conventions

These apply to every session unless overridden in-session. Read them once; sessions reference them by name.

### 1.1 Branch and commit strategy

- All sessions commit to `design/wc-polish` (the existing worktree branch).
- Commit per logical unit within a session (often 1-3 commits per session). Squashing to one commit per session is allowed if the session's work is genuinely atomic.
- **PR cadence**: open a PR at the **end of each Phase**, not per session. PR title format: `Impeccable PN — <phase name>`. PR body summarizes per-session deliverables, lists impeccable findings closed, and links to before/after screenshots. Final merge of `design/wc-polish` → `main` happens at the close of P6.
- Commit messages follow conventional commits (`fix:`, `feat:`, `style:`, `refactor:`, `test:`, `docs:`). For impeccable work, prefer `style:` for visual changes, `fix:` for a11y/contrast/correctness, `refactor:` for migrations (side-stripe, shadow), `feat:` only when a genuinely new component or capability lands.
- Tag @CodeRabbit AI Review so CR can review the code

### 1.2 Skill and command usage

- Every session begins with the user (or the agent on their behalf) invoking `Skill { skill: "impeccable" }`. The skill loads PRODUCT.md and DESIGN.md context. Failure to do any of the 3 is unacceptable. Every session and/or agent MUST invoke impeccable, fully read PRODUCT.md, and fully read DESIGN.md. 
- Sub-commands are invoked by writing `$impeccable <command> <target>` in chat. The skill routes to the relevant reference file.
- For cross-cutting hardens, use `$impeccable harden <surface>` with `<surface>` as a description of the systemic issue (e.g., `$impeccable harden bootstrap-shadow-leak across all .card.wc-card`).
- For per-page work, the typical session pattern is:
  1. `$impeccable critique <page>` — produces a Combined Critique Report with priority issues + recommended commands. The Tier 1 leaderboard run already exists; for new pages this is the first major step.
  2. Execute the recommended commands one by one (`$impeccable shape <component>`, `$impeccable clarify <copy target>`, `$impeccable adapt <responsive target>`, etc.).
  3. Re-run `$impeccable critique <page>` at the end to confirm score lift.
- "A step" in this plan can take 30-60 minutes of agent work when the step is "run $impeccable critique" (which spawns sub-agents and runs detectors). That's expected; the writing-plans bite-size rule is relaxed for design-work steps.

### 1.3 Verification strategy (hybrid: source locks + Playwright MCP + critique re-run)

Three layers per session. Each catches a different category of regression. Use them together; none is sufficient alone.

**Layer A: Source-pattern locks (pytest, fast, CI-friendly).**

- For things whose **source presence/absence is the violation**: em-dashes in user copy, `border-left: Npx` rules, missing `scope="col"` in rendered HTML, missing `role`/`aria-label` on regions. Source-grep style.
- Two flavors:
  - **CSS-source assertions**: open `static/css/style.css` as text and assert presence/absence of patterns. Example: `assert 'border-left: 3px solid var(--game-accent)' not in css_source` after side-stripe migration. Fast, deterministic, no browser.
  - **Rendered-HTML assertions**: Flask test client renders a representative page; substring/regex checks on response body. Example: `assert b'<th scope="col">' in resp.data` for table-semantics fixes.
- Tests live under `tests/test_design_<phase>_<topic>.py`. Each session adds its own file or appends to an existing one.
- `ENVIRONMENT=testing venv/bin/python -m pytest tests/` must pass at the end of every session.

**Layer B: Playwright MCP — in-session computed/visual verification.**

- For things whose **rendered or computed value is the violation**: Bootstrap utility leaks (the gray `box-shadow` we'd never write in `style.css` but Bootstrap CDN does), tap-target rectangles at 375 viewport, contrast at the actual rendered color stack (not the source-declared color), focus-ring presence, focus-trap order, axe a11y violations.
- Use the Playwright MCP plugin (`mcp__plugin_playwright_playwright__*`) live during the session. The agent navigates the dev server, evaluates JS to read computed styles or bounding rects, runs axe (`npm exec axe-core` or via injected script), records findings.
- These checks are **session-time gates**, not pytest tests. They prove the fix worked at session end; they don't re-run in CI. The reasoning: visual regression infrastructure (pytest-playwright + browser install + live-server fixture) is a heavier investment than this project warrants — the next critique re-run (Layer C) catches anything Layer B would miss in CI.
- Required Playwright MCP probes per session type:
  - **Cross-cutting harden**: probe the specific computed value the harden targets (e.g., `box-shadow` of `.card.wc-card`, `min-height` of `.subnav-pill`, contrast of trophy CTA hover).
  - **Per-page** (P1, P2.x, P4.x, P5.x): take desktop + 375 mobile screenshots, run `axe-core` against the page, probe any computed styles flagged in the critique.
- When the Playwright MCP isn't available for some reason, the chrome-devtools-mcp plugin (`mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`) covers the same ground — pick whichever is available.

**Layer C: Holistic critique re-run (impeccable, end-of-session for per-page sessions).**

- After per-page execution, re-run `$impeccable critique <page>` and compare the new Design Health Score / Audit Health Score / Anti-Patterns count to the baseline. Record the delta in the session's commit message (e.g., `Critique: 23/40 → 31/40, audit 11/20 → 16/20, anti-patterns 5 → 1`).
- Cross-cutting harden sessions are scored against the leaderboard exemplar (re-run `$impeccable critique leaderboard` if the harden was meant to fix one of its findings).
- The critique re-run IS the visual-regression net for CI-skipped Layer B work. If Layer B passed at session-end and Layer C scored a lift, the work landed.

**Decision rule (which layer for which finding):**

| Finding type | Use |
|---|---|
| Source-pattern ban (em-dash, side-stripe rule, hard-coded hex) | **Layer A** (source grep) |
| Rendered-HTML structure (`scope="col"`, `<caption>`, `aria-label`) | **Layer A** (Flask test client) |
| Computed style of an element (`box-shadow`, `font-family`, `color`, contrast) | **Layer B** (Playwright MCP) |
| Tap-target rect / overflow / responsive-collapse | **Layer B** (Playwright MCP) |
| Axe a11y scan | **Layer B** (Playwright MCP, axe injected) |
| Holistic visual / brand fit / hierarchy | **Layer C** (`$impeccable critique` re-run) |

### 1.4 How to start a session

The user `/clear`s, then opens a fresh chat with prompt template:

```
Resuming the impeccable design improvement project. Plan:
docs/superpowers/plans/2026-05-08-impeccable-design-improvement-project.md.
Execute Session <ID> only. Do not run subsequent sessions in this chat.
```

The agent's first three actions in any session:

1. Invoke `Skill { skill: "impeccable" }` — loads context and design laws. Reads PRODUCT.md and DESIGN.md.
2. Read this plan, find the targeted session, read its full block.
3. Read every file listed under the session's "Files in scope (READ)" before any edit.

### 1.5 How to end a session

Every session ends with the same six steps:

1. **Run pytest**: `ENVIRONMENT=testing venv/bin/python -m pytest tests/` — must be green.
2. **Run pyright**: `venv/bin/pyright` — target 0 errors (existing baseline).
3. **Take after-screenshots** of any visually-changed pages at desktop (1470×900) and mobile (375×812). Save under `.impeccable-review/<session-id>/`. Add `.impeccable-review/` to `.gitignore` if not already (one-time, in P0 S0.1).
4. **Re-run impeccable critique** for any page touched (per-page sessions only). Record score delta in the commit message body.
5. **Commit** with conventional-commits prefix and a summary that names the session ID.
6. **Update the plan checklist** (Section 9 of this document) — mark the session complete, append any newly-found out-of-scope items to the Backlog (Section 0.4).
7. If any session findings would be beneficial for future sessions, update this document accordingly so future sessions and phases go smoothly. Usage of the remember skill is also encouraged.

### 1.6 Out-of-scope guardrails

- **Don't touch Golf or CFB.** They're explicitly excluded.
- **Don't touch admin templates.** They're explicitly excluded.
- **Don't introduce new design tokens** without a spec session. CCC tokens live in `tokens.css` and additions need explicit DESIGN.md updates.
- **Don't refactor business logic** as a side effect of design work. If a route handler needs to change shape to support a UI fix, scope it minimally and call it out in the commit message.

### 1.7 Failure mode: critique surfaces something we hadn't planned for

If a per-page critique surfaces a P0 or P1 issue that doesn't fit the session's scope:

1. **Don't push past it.** Mark the session as partially complete in the plan.
2. Append the new finding to the Backlog (Section 0.4).
3. Either: (a) handle it in the same session if the fix is self-contained, or (b) defer to a future session and note the dependency. Default to (a) unless (b) is clearly more beneficial and logical.
4. Add a note in the session's "Handoff" block.

### 1.8 Impeccable is the source of truth — the plan is scaffolding

This plan was written **before** most of the surfaces in scope had been critiqued. Its specifics for P2–P5 are educated guesses, not ground truth. The leaderboard's per-page priority issues were ground truth for P1; the cross-cutting findings are ground truth for P0. Everything beyond that is a starting point for the agent's actual critique work.

When the plan and impeccable findings disagree, **impeccable wins**. The agent's job in any per-page session is not to execute pre-specified edits — it's to:

1. Run the impeccable workflow (`$impeccable critique <target>` or the relevant sub-command).
2. Trust the resulting report.
3. Execute against the report's Priority Issues and Recommended Actions.
4. Update this plan if the truth surfaced is durable enough to benefit future sessions.

**Deviations from the plan are expected and welcome.** Specific examples of legitimate deviation:

- The plan predicts a per-page session will surface ~3 priority issues; the actual critique surfaces 7. → **Adapt scope.** Take the top 3-5 in this session per §1.7; backlog the rest. Do not push all 7 in one session.
- The plan suggests a specific impeccable command for a finding (e.g., `$impeccable clarify`); the critique recommends a different command (`$impeccable shape`). → **Trust the critique.** It saw the surface; the plan didn't.
- The plan's Priority Issues for a future session don't match what the actual critique surfaces. → **Trust the critique.** Update §0.4 (Backlog) and the affected session's notes.
- A regression test pattern in the plan turns out to be brittle for this codebase. → **Replace it.** Don't twist the codebase to fit the test pattern.
- A pattern locked in CLAUDE.md or an existing memory file conflicts with a critique finding. → **Surface the conflict to the user via `AskUserQuestion`.** Don't unilaterally override CLAUDE.md or invent a new rule.

**Plan-update mechanics during execution:**

- Append new findings to §0.4 Backlog with the discovering session ID.
- If a session discovers a fact that future sessions need (e.g., "the rank-delta helper actually lives at `services/snapshots.py`, not `services/ranking.py`"), edit the affected future-session block in the plan to reference the correct file.
- If a phase's session inventory is wrong (a session needed for a critical surface was missed; a planned session is no longer needed), insert/remove sessions and renumber. Update §9 checklist accordingly.
- Use the `remember` skill to capture durable lessons about the impeccable workflow itself or about this project's specific gotchas. Memory benefits future sessions across the project's life.

**What does NOT count as a deviation worth touching the plan over:**

- Style choices in copy rewrites (those happen per session and don't need plan amendments).
- One-off CSS edits that don't generalize (commit them; move on).
- Per-session test additions (each session writes its own; the plan describes the pattern, not the specific tests).

The plan's role is **scaffolding**: it gives every session a clean place to start, locks the strategic priorities, and tracks completion. Impeccable's role is **the design discipline**. Don't confuse the two.

---

## 2. Phase 0 — Cross-cutting harden (3 sessions)

These sessions execute the systemic findings from the leaderboard exemplar before any per-page work begins. Each fix touches the entire codebase, so doing them per-page would multiply the work and risk inconsistent migrations.

---

### Session S0.1 — Bootstrap shadow leak migration

**Goal:** Replace every Bootstrap `shadow-sm`/`shadow`/`shadow-lg` utility on CCC card classes with the brand-tinted `--shadow-sm/md/lg` scale, eliminating the neutral-gray `rgba(0,0,0,0.075)` shadow leak DESIGN.md flags as slop.

**Prerequisites:** None (this is the first session).

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- `static/css/tokens.css` — confirm `--shadow-sm/md/lg/gold` definitions
- `static/css/style.css` — find every `.card`, `.card.wc-card`, `.shadow-sm` rule
- All templates listed in §0.1 — grep for `class="...shadow..."` usage

**Files in scope (WRITE):**
- `static/css/style.css` — add scoped shadow rules
- All templates with literal `shadow-sm` / `shadow-lg` Bootstrap utility classes — strip the utility, rely on the scoped CSS rule
- `tests/test_design_p0_shadow.py` (new) — regression lock
- `.gitignore` — add `.impeccable-review/`

**Tasks:**

- [x] **Step 1: Confirm baseline**

```bash
grep -rn 'shadow-sm\|shadow-lg\|shadow ' games/worldcup/templates/ core/ templates/ 2>/dev/null | grep -v '.pyc'
grep -nE '\.card\.wc-card|\.card\b|\.shadow-sm|\.shadow-lg' static/css/style.css | head -40
```

Expected: a list of every Bootstrap shadow utility currently applied to CCC cards. Capture the count.

- [x] **Step 2: Add `.gitignore` entry**

Read `.gitignore`. If `.impeccable-review/` is not present, add it.

```
# Impeccable design-review screenshots and rendered HTML (regenerated per session)
.impeccable-review/
```

- [x] **Step 3: Write the failing test**

Create `tests/test_design_p0_shadow.py`:

```python
"""P0 S0.1 — lock: every CCC card class carries brand-tinted shadow, never neutral gray."""
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_no_neutral_gray_box_shadow_in_card_rules():
    """No CCC `.card`/`.card.wc-card` rule may declare a neutral `rgba(0,0,0,...)` shadow.
    All shadows must use the brand-tinted `--shadow-*` scale."""
    src = CSS_PATH.read_text()
    # Crude but adequate: walk every `.card` block and check its `box-shadow`/`shadow` declarations
    offenders = []
    for line_no, line in enumerate(src.splitlines(), start=1):
        if 'box-shadow' in line and 'rgba(0' in line and 'rgba(0, 17' not in line and 'rgba(0,17' not in line:
            # rgba(0, 17, ...) is the navy WC card surface, allowed; rgba(0, 0, 0, ...) is the gray slop
            if 'rgba(0, 0, 0' in line or 'rgba(0,0,0' in line:
                offenders.append((line_no, line.strip()))
    assert not offenders, f"Neutral-gray shadows found: {offenders}"


def test_card_wc_card_uses_brand_shadow_token():
    """`.card.wc-card` resting state must reference `var(--shadow-sm)` (brand-tinted)."""
    src = CSS_PATH.read_text()
    # Find the `.card.wc-card` block and confirm a shadow declaration referencing the token
    assert 'var(--shadow-sm)' in src or 'var(--shadow-md)' in src, "Brand shadow tokens must be referenced somewhere"
```

- [x] **Step 4: Run the test, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_shadow.py -v
```

Expected: failures (Bootstrap's `.shadow-sm` rule with `rgba(0, 0, 0, 0.075)` is in the cascade via the linked Bootstrap CSS — but NOT in our `style.css`. So this specific test may already pass since the offending shadow comes from Bootstrap CDN, not local source. **If both tests pass on the first run**, the issue is that Bootstrap's utility is being *applied via class*, not declared in our CSS. In that case skip Step 5's local-CSS edit and go to Step 6 (template scrub).

- [x] **Step 5: Add scoped shadow override in `style.css`**

Find the existing `.card.wc-card` block (around line 3242-3291 per the leaderboard audit). Above or alongside it, add:

```css
/* P0 S0.1 — neutralize Bootstrap's gray shadow utility on CCC cards.
   Every CCC card inherits the brand-tinted --shadow-sm at rest by default. */
.card,
.card.wc-card,
.game-card,
.leaderboard-card {
  box-shadow: var(--shadow-sm) !important;
}

.card:hover,
.card.wc-card:hover,
.game-card:hover,
.leaderboard-card:hover {
  box-shadow: var(--shadow-md) !important;
}
```

The `!important` is the only honest way to win against Bootstrap's `.shadow-sm` utility class once it's present in markup; a cleaner alternative is to **remove the utility class from templates** (Step 6) and drop `!important` here. Prefer that path.

- [x] **Step 6: Strip Bootstrap shadow utilities from templates**

For each occurrence found in Step 1, edit the template to remove `shadow-sm` / `shadow-lg` / `shadow` from the class list when the element already carries a `.card`, `.card.wc-card`, `.game-card`, or `.leaderboard-card` class. The CSS rule from Step 5 supplies the brand shadow.

Templates likely affected (from the leaderboard inventory):
- `games/worldcup/templates/worldcup/leaderboard.html` — `<div class="card wc-card border-0 shadow-sm ...">` (~6 instances)
- core/main partials: any `<div class="card ...shadow...">` — grep shows them
- Auth pages: `<div class="card shadow-lg auth-card">` etc.

After this, re-run grep:

```bash
grep -rn 'shadow-sm\|shadow-lg' games/worldcup/templates/ core/ templates/ 2>/dev/null | grep -v '.pyc'
```

Expected: zero results in templates that already carry a `.card` class.

- [x] **Step 7: Verify computed style via Playwright MCP (Layer B)**

Start dev server: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`. Use the Playwright MCP plugin (`mcp__plugin_playwright_playwright__*`) to:

1. `browser_navigate` to `http://127.0.0.1:5099/worldcup/leaderboard` (auth: the dev DB has a session cookie persisted from prior sessions; if not, log in via the form first).
2. `browser_evaluate` against `.card.wc-card`:
   ```javascript
   () => { const el = document.querySelector('.card.wc-card'); return el ? getComputedStyle(el).boxShadow : null; }
   ```
3. Assert in chat that the returned `boxShadow` contains `rgb(58, 29, 114)` or `rgba(58, 29, 114` (the brand-tinted purple), NOT `rgb(0, 0, 0)` or `rgba(0, 0, 0`.
4. Take a desktop + 375 mobile screenshot via `browser_take_screenshot` to `.impeccable-review/s0.1/`.

If the Playwright MCP is unavailable, fall back to `mcp__plugin_chrome-devtools-mcp_chrome-devtools__evaluate_script` with the same probe.

- [x] **Step 8: Run the test, see it pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_shadow.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright
```

All green.

- [x] **Step 9: Commit**

```bash
git add tests/test_design_p0_shadow.py static/css/style.css games/worldcup/templates/ core/ templates/ .gitignore
git commit -m "$(cat <<'EOF'
refactor(p0-s0.1): replace Bootstrap shadow leak with brand-tinted scale

Press-Room Shadow Rule (DESIGN.md): all shadows tint with brand purple,
never neutral gray. Bootstrap's .shadow-sm utility was rendering
rgba(0,0,0,0.075) on every .card.wc-card, leaking SaaS-stock chrome
into the Tribune surface. Strip the utility from templates and route
through .card/.card.wc-card scoped rules that reference --shadow-sm/md.

Locked by tests/test_design_p0_shadow.py.

Impeccable: P0 S0.1 — Bootstrap shadow leak.
Critique: leaderboard audit Theming 2 → 3.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- pyright 0 errors ✓
- DevTools confirms brand-tinted shadow on `.card.wc-card` ✓
- After-screenshot of leaderboard saved ✓

**Handoff to S0.2:** No outstanding work. Side-stripe migration is independent; can proceed.

---

### Session S0.2 — Side-stripe ban migration + table semantics sweep

**Goal:** Eliminate every `border-left: Npx` colored side-stripe accent across `style.css` and replace with full borders, leading icons/numerals, or background tints, per the impeccable absolute ban (DESIGN.md). Same session: add `<th scope="col">`, `<caption class="visually-hidden">`, and region roles to every leaderboard/standings table — they're WCAG 1.3.1 violations across the codebase.

**Prerequisites:** S0.1 complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- The full impeccable absolute-bans list (loaded by the skill)
- `static/css/style.css` — every `border-left:` declaration over 1px
- All public WC + global tables: leaderboard, schedule, stats, groups, picks (any `<table>` element)

**Files in scope (WRITE):**
- `static/css/style.css` — remove side-stripes, add replacement patterns
- Templates with `<table>` — add `scope="col"` to every `<th>`, add a visually-hidden `<caption>`
- Templates with `.your-standing` / `.row-current-user` — adjust class structure if the side-stripe migration changes the wrapper shape (but resist scope creep; the Your Standing reshape itself is P1 S1.1, not this session)
- `tests/test_design_p0_side_stripes.py` (new)
- `tests/test_design_p0_table_semantics.py` (new)

**Tasks:**

- [ ] **Step 1: Inventory side-stripes in `style.css`**

```bash
grep -nE 'border-(left|right):\s*[2-9]px|border-(left|right):\s*[1-9][0-9]+px' static/css/style.css
```

Expected: ~15-20 hits. Note line numbers and the rule each is attached to.

- [ ] **Step 2: Categorize each side-stripe**

For each hit, decide its replacement strategy:

| Selector type | Replacement |
|---|---|
| `.your-standing { border-left: 3px solid var(--game-accent) }` | Remove. Reshape (covered in P1 S1.1; for now, just remove the stripe and let P1 do the proper reshape). |
| `.row-current-user { border-left: ... }` | Remove. Replace with subtle background tint (already partially present) and a leading "you" indicator pill or numeral emphasis. |
| `.card.border-success/danger/warning/primary { border-left: 4px ... }` | Remove. Replace with **full-border** rules using the same token, plus a small leading icon (`<i class="bi bi-check-circle">` etc. injected via CSS pseudo-element if templates can't change). |
| `.tier-row { border-left: 3px solid var(--tier-color) }` (line 4729) | Remove. Replace with leading **tier number pill** (already-existing `.wc-tier-pill` pattern). |
| Game-specific stripes (CFB, Golf) | **Skip** — out of scope for this project. |
| `currentColor` stripes (`style.css:3563`) | Audit the rule. If it's an alert pattern, full-border + icon. |

- [ ] **Step 3: Write the failing test**

Create `tests/test_design_p0_side_stripes.py`:

```python
"""P0 S0.2 — lock: no `border-left: Npx` colored accent on CCC components.
Side-stripe accents are an impeccable absolute ban (DESIGN.md)."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'

# Selectors NOT in scope (game-specific, off-limits for this project)
GAME_SCOPED_PATTERNS = [
    r'\.lives-indicator',
    r'\.cfb-',
    r'\.game-cfb',
    r'\.game-golf',
]


def test_no_colored_side_stripes_on_platform_components():
    """Walk style.css. Any `border-left: Npx` (N >= 2) outside game-scoped blocks fails."""
    src = CSS_PATH.read_text()
    pattern = re.compile(r'(\.[\w\-\.]+)\s*\{[^}]*border-(left|right):\s*([2-9]|[1-9]\d+)px[^}]*\}', re.MULTILINE | re.DOTALL)
    offenders = []
    for match in pattern.finditer(src):
        selector = match.group(1)
        if any(re.search(p, selector) for p in GAME_SCOPED_PATTERNS):
            continue
        offenders.append((selector, match.group(2), match.group(3)))
    assert not offenders, f"Side-stripe ban violations on platform/WC components: {offenders}"


def test_card_border_state_classes_use_full_border_not_side_stripe():
    """`.card.border-success/danger/warning/primary` must use a full border, not border-left."""
    src = CSS_PATH.read_text()
    for class_name in ['border-success', 'border-danger', 'border-warning', 'border-primary']:
        # Find the rule and confirm it does NOT contain `border-left:` over 1px
        rule_match = re.search(rf'\.card\.{class_name}\s*\{{([^}}]+)\}}', src, re.MULTILINE)
        if rule_match is None:
            continue  # rule may have been removed entirely
        body = rule_match.group(1)
        assert 'border-left:' not in body or 'border-left: 1px' in body, \
            f".card.{class_name} still uses border-left side-stripe: {body[:200]}"
```

- [ ] **Step 4: Run the test, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_side_stripes.py -v
```

Expected: 1-2 failures with offender selectors listed.

- [ ] **Step 5: Migrate each side-stripe rule in `style.css`**

For each rule from Step 2, edit `style.css`:

For `.card.border-success/danger/warning/primary` (lines ~3602-3605):

```css
/* Replaced side-stripe with full border + tinted background for state communication.
   Per impeccable absolute ban: no border-left/right >1px as a colored accent. */
.card.border-success {
  border: 1px solid var(--success);
  background-color: rgba(26, 122, 69, 0.05);
}
.card.border-danger {
  border: 1px solid var(--danger);
  background-color: rgba(192, 57, 43, 0.05);
}
.card.border-warning {
  border: 1px solid var(--warning);
  background-color: rgba(201, 162, 39, 0.06);
}
.card.border-primary {
  border: 1px solid var(--platform-primary);
  background-color: rgba(58, 29, 114, 0.05);
}
```

For `.your-standing` (line ~3163): remove `border-left: 3px solid var(--game-accent);`. The block stays card-shaped; the proper Your Standing reshape happens in P1 S1.1. For now it's a plain bone-tinted card without the alert frequency.

For `.row-current-user` (find the active rule via grep): remove `border-left: ...`. Confirm an existing background-tint highlight remains (it does — the row already has a tinted bg).

For tier rows (line ~4729): remove `border-left: 3px solid var(--tier-color);`. Confirm leading tier pill (`.wc-tier-pill`) carries the color responsibility.

For any other rule from Step 2: full-border-or-pill replacement, never re-introduce a stripe.

- [ ] **Step 6: Add table semantics across in-scope tables**

For each public table in WC + global surfaces:
- `games/worldcup/templates/worldcup/leaderboard.html`
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/stats.html`
- `games/worldcup/templates/worldcup/groups.html`
- `games/worldcup/templates/worldcup/team_detail.html`
- `core/main/templates/main/...` (any partial with a `<table>`)

Apply this pattern:

```jinja
<table class="...existing classes...">
  <caption class="visually-hidden">{# Concise table description, e.g. "2026 World Cup Pool standings" #}</caption>
  <thead>
    <tr>
      <th scope="col">#</th>
      <th scope="col">Player</th>
      ...
    </tr>
  </thead>
  ...
</table>
```

Add `<th scope="row">` to any first-column `<th>` if a table uses row-headers.

- [ ] **Step 7: Add region role to `.your-standing`**

In `games/worldcup/templates/worldcup/leaderboard.html`, wrap the Your Standing block:

```jinja
<section role="region" aria-labelledby="your-standing-title">
  <span class="wc-eyebrow" id="your-standing-title">Your Standing</span>
  ...
</section>
```

Or use `aria-label="Your standing"` on the wrapper if a heading element isn't present.

- [ ] **Step 8: Write the table-semantics test**

Create `tests/test_design_p0_table_semantics.py`:

```python
"""P0 S0.2 — lock: every public WC/global table has scope=col + visually-hidden caption.
WCAG 1.3.1 (Info and Relationships)."""
import pytest
from app import create_app

PATHS_WITH_TABLES = [
    '/worldcup/leaderboard',
    '/worldcup/schedule',
    '/worldcup/stats',
    '/worldcup/groups',
    # Add as new tables surface in later phases
]


@pytest.fixture
def client():
    app = create_app('testing')
    with app.app_context():
        from extensions import db
        db.create_all()
        yield app.test_client()


@pytest.mark.parametrize('path', PATHS_WITH_TABLES)
def test_tables_carry_scope_col_and_caption(client, path):
    """Anonymous-or-authenticated GET must render <th scope="col"> on every <th> and
    a <caption class="visually-hidden"> on every standings table."""
    # Auth-gated routes: pre-login a test user (see tests/conftest.py if it exists; otherwise
    # this test parameter is skipped via pytest.skip when the path 302s to /login)
    resp = client.get(path, follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip(f'{path} requires auth; covered by per-page session integration tests')
    body = resp.data.decode('utf-8')
    if '<table' not in body:
        return  # page may not render a table in current state
    assert 'scope="col"' in body, f'{path}: <th> missing scope="col"'
    assert 'visually-hidden' in body and 'caption' in body, f'{path}: missing visually-hidden caption'
```

(Note: this test will skip auth-gated paths; per-page integration tests in later sessions cover them with a logged-in client. Adjust if `tests/conftest.py` already exposes an authenticated client fixture — check before writing.)

- [ ] **Step 9: Run all tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_side_stripes.py tests/test_design_p0_table_semantics.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright
```

All green.

- [ ] **Step 10: Playwright MCP verification (Layer B)**

Use the Playwright MCP plugin to confirm the rendered tables and the no-stripe state:

1. `browser_navigate` to `/worldcup/leaderboard`. `browser_evaluate`:
   ```javascript
   () => {
     const stripes = [];
     for (const sel of ['.your-standing', '.row-current-user', '.card.border-success', '.card.border-danger', '.card.border-warning', '.card.border-primary']) {
       const el = document.querySelector(sel);
       if (el) { const cs = getComputedStyle(el); stripes.push({ sel, borderLeft: cs.borderLeftWidth + ' ' + cs.borderLeftColor }); }
     }
     // Also check tables on this page:
     const tables = Array.from(document.querySelectorAll('table'));
     const tableSemantics = tables.map(t => ({
       hasCaption: !!t.querySelector('caption'),
       allThHaveScope: Array.from(t.querySelectorAll('thead th')).every(th => th.hasAttribute('scope')),
     }));
     return { stripes, tableSemantics };
   }
   ```
2. Assert: every `borderLeft` width is `0px` or `1px` (no >1px colored stripes). Every table reports `hasCaption: true` and `allThHaveScope: true`.
3. Take desktop (1470x900) + mobile (375x812) screenshots via `browser_take_screenshot` to `.impeccable-review/s0.2/`.
4. (Optional but recommended) Inject axe-core via `browser_evaluate` and run a scan; assert no `serious` or `critical` violations on tables. The skill or critique reference notes how to inject axe-core.

If Playwright MCP isn't available, fall back to chrome-devtools-mcp with the same probes.

- [ ] **Step 11: Commit**

```bash
git add tests/test_design_p0_side_stripes.py tests/test_design_p0_table_semantics.py static/css/style.css games/ core/ templates/
git commit -m "$(cat <<'EOF'
refactor(p0-s0.2): migrate side-stripe accents to full borders + table a11y sweep

Side-stripe ban (impeccable absolute) violated on .your-standing,
.row-current-user, .card.border-{success,danger,warning,primary},
tier-row, and others. Migrate to full borders + tinted backgrounds.
The Your Standing reshape lands in P1 S1.1; this session just neutralizes
the stripe so the surface stops shouting "alert".

Same pass: every public WC table gains <th scope="col"> + a
visually-hidden <caption> for WCAG 1.3.1 (Info and Relationships).
.your-standing wrapped as <section role="region" aria-labelledby=...>.

Locked by tests/test_design_p0_side_stripes.py and
tests/test_design_p0_table_semantics.py.

Impeccable: P0 S0.2 — side-stripe ban + table semantics.
Critique: leaderboard a11y 2 → 3, anti-patterns count -2.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- pyright 0 errors ✓
- All tables in scope have `scope="col"` + caption ✓
- No side-stripes >1px in `style.css` (outside CFB/Golf) ✓
- Visual smoke at desktop + mobile ✓

**Handoff to S0.3:** Mobile tap targets and white-on-gold contrast remain. They're independent of this session.

---

### Session S0.3 — Mobile tap-target floor + white-on-gold contrast + em-dash sweep

**Goal:** (a) Bring every interactive element across public WC + global pages to ≥44×44 px at 375 viewport, (b) repair white-on-gold contrast on the metal-gold trophy CTA hover (currently 1.5:1, must be ≥4.5:1), (c) eliminate em-dash glyphs (`—` and `--`) from UI copy per Copy Discipline.

**Prerequisites:** S0.1 + S0.2 complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- `static/css/style.css` — `.subnav-pill`, `.btn-warning`, `.metal-gold` rules; `.leaderboard-card` and any other `.card`-as-link patterns
- All in-scope templates — for em-dash sweep

**Files in scope (WRITE):**
- `static/css/style.css` — sub-nav pill min-height + padding; trophy CTA text contrast lock
- Mobile leaderboard cards: convert to whole-card-as-link (template + CSS)
- All in-scope templates — replace `—` glyphs with appropriate words/punctuation
- `tests/test_design_p0_tap_targets.py` (new)
- `tests/test_design_p0_contrast.py` (new)
- `tests/test_design_p0_copy_discipline.py` (new)

**Tasks:**

- [ ] **Step 1: Tap-target inventory via Playwright MCP (Layer B)**

Boot dev server. Use the Playwright MCP plugin: `browser_resize` to 375×812 (or `browser_emulate` mobile preset), `browser_navigate` to each in-scope page (`/worldcup/leaderboard`, `/worldcup/`, `/worldcup/schedule`, `/worldcup/picks`, `/worldcup/stats`, `/worldcup/rules`, `/login`, `/`). For each, run:

```javascript
() => {
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('a, button, [role="button"], .subnav-pill, .leaderboard-card, .btn-sm')) {
    if (seen.has(el)) continue; seen.add(el);
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44)) {
      out.push({ tag: el.tagName, classes: el.className.toString().slice(0, 80), text: (el.textContent || '').trim().slice(0, 40), w: r.width, h: r.height });
    }
  }
  return { failures: out, docW: document.documentElement.scrollWidth, winW: innerWidth };
}
```

Record every selector that fails 44×44. Known seeds from the leaderboard audit:
- `.leaderboard-card a.d-block` — 85×26
- `.subnav-pill` — 36–60×30 (six pills)

Likely failures elsewhere (verify with the probe above):
- Game-card name links on home (`.game-card a`)
- Auth page link rows
- Schedule fixture cards
- Empty-state CTAs (small `.btn-sm` buttons)

The Playwright MCP probe is the source of truth for which elements need fixing in this session — don't pre-commit to a list.

- [ ] **Step 2: Write the source-pattern test (tap-targets)**

Source-grep test confirms every fixed selector declares its min-height in `style.css`. The Playwright MCP probe in Step 1 confirms the rendered rect; the source test below locks the CSS so the rect can't regress in source.

Create `tests/test_design_p0_tap_targets.py`:

```python
"""P0 S0.3 — lock: mobile tap-target floor 44x44.
WCAG 2.5.5/2.5.8 + DESIGN.md mobile-first floor."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def _rule_min_height(css: str, selector: str) -> str | None:
    """Return the `min-height` value declared on a selector, or None if not declared."""
    pattern = rf'{re.escape(selector)}\s*\{{([^}}]+)\}}'
    match = re.search(pattern, css, re.MULTILINE)
    if not match:
        return None
    body = match.group(1)
    mh = re.search(r'min-height:\s*([^;]+);', body)
    return mh.group(1).strip() if mh else None


def test_subnav_pill_min_height_44px():
    """`.subnav-pill` must declare min-height ≥ 44px (or 2.75rem)."""
    css = CSS_PATH.read_text()
    mh = _rule_min_height(css, '.subnav-pill')
    assert mh is not None, '.subnav-pill must declare min-height'
    # Accept 44px, 2.75rem, or larger
    assert ('44px' in mh) or ('2.75rem' in mh) or ('48px' in mh), f'.subnav-pill min-height too small: {mh}'


def test_leaderboard_card_link_covers_card():
    """Mobile leaderboard cards must be whole-card-as-link, not name-string-as-link."""
    template = Path(__file__).parent.parent / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
    src = template.read_text()
    # Heuristic: the mobile section must wrap each card in <a> or use stretched-link pattern
    assert 'leaderboard-card-link' in src or 'stretched-link' in src or '<a href="/worldcup/leaderboard/' in src and 'leaderboard-card' in src, \
        'Mobile leaderboard cards must use whole-card-as-link pattern'
```

- [ ] **Step 3: Run, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py -v
```

Expected: both fail.

- [ ] **Step 4: Fix sub-nav pills in `style.css`**

Find the `.subnav-pill` block (search for `.subnav-pill {`). Edit:

```css
.subnav-pill {
  /* ...existing properties... */
  min-height: 44px;
  padding: 0.625rem 1rem;          /* was ~0.32rem 0.72rem; expand for the 44px floor */
  display: inline-flex;
  align-items: center;
  /* ...existing... */
}
```

If the surrounding container needs more vertical space, adjust `.subnav-pills` padding and `.game-subnav` height accordingly. Verify the navbar+sub-nav stack doesn't push hero content off-screen.

- [ ] **Step 5: Convert mobile leaderboard cards to whole-card links**

Edit `games/worldcup/templates/worldcup/leaderboard.html` mobile section. Replace the existing per-card structure:

```jinja
{# BEFORE — the inner <a> is the only tap target #}
<div class="card wc-card ...">
  <div class="card-body ...">
    <span class="...">{{ rank }}</span>
    <div>
      <span class="me-1">{{ avatar }}</span>
      <a href="..." class="text-decoration-none fw-medium d-block">{{ name }}</a>
      <small>...</small>
    </div>
    <span class="...">{{ score }}</span>
  </div>
</div>
```

```jinja
{# AFTER — whole card is the tap target #}
<a href="{{ '/worldcup/picks' if is_current_user else '/worldcup/leaderboard/' ~ enrollment.id }}"
   class="card wc-card leaderboard-card leaderboard-card-link {% if is_current_user %}leaderboard-card-current{% endif %} animate-in text-decoration-none">
  <div class="card-body p-3 d-flex align-items-center justify-content-between">
    <span class="...">{{ rank }}</span>
    <div>
      <span class="me-1">{{ avatar }}</span>
      <span class="fw-medium d-block leaderboard-card-name">{{ name }}</span>
      <small>...</small>
    </div>
    <span class="...">{{ score }}</span>
  </div>
</a>
```

Add `.leaderboard-card-link` to `style.css` to neutralize default link styling on the card and preserve the existing visual:

```css
.leaderboard-card-link {
  display: block;
  color: inherit;
  text-decoration: none;
}
.leaderboard-card-link:hover,
.leaderboard-card-link:focus {
  color: inherit;
  text-decoration: none;
}
.leaderboard-card-link:focus-visible {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}
```

- [ ] **Step 6: Run tap-target tests, see them pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py -v
```

- [ ] **Step 7: Write the failing test (white-on-gold contrast)**

Create `tests/test_design_p0_contrast.py`:

```python
"""P0 S0.3 — lock: trophy CTA text on metal-gold gradient meets WCAG AA contrast.
The previous hover state rendered white on #FFF1B8 (1.5:1). Lock to chamber-purple text."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_navbar_btn_warning_text_color_locked_to_purple():
    """Navbar `.btn-warning` (metal-gold trophy CTA) must declare a dark purple text color
    for both rest and hover, never bone/white. Per DESIGN.md trophy CTA contract."""
    css = CSS_PATH.read_text()
    rest = re.search(r'\.navbar\.navbar-dark\s+\.btn-warning\s*\{([^}]+)\}', css)
    hover = re.search(r'\.navbar\.navbar-dark\s+\.btn-warning:hover\s*\{([^}]+)\}', css)
    assert rest, 'navbar .btn-warning rest rule not found'
    assert hover, 'navbar .btn-warning:hover rule not found'
    for label, body in [('rest', rest.group(1)), ('hover', hover.group(1))]:
        # The text color must be the dark chamber purple, not bone/white
        assert 'var(--purple-900)' in body or '#1C0A3A' in body or 'var(--chamber)' in body, \
            f'navbar .btn-warning {label}: text color must be chamber-purple, found: {body[:200]}'
```

- [ ] **Step 7.5: Playwright MCP — measure actual rendered contrast (Layer B)**

Use the Playwright MCP to confirm the rendered contrast of the trophy CTA, before AND after the fix:

1. `browser_navigate` to any logged-in page (the navbar carries the trophy button).
2. `browser_evaluate` to get the rendered color stack of the navbar `.btn-warning` at rest and on hover. Sketch:
   ```javascript
   () => {
     const btn = document.querySelector('.navbar .btn-warning');
     if (!btn) return { found: false };
     const rest = getComputedStyle(btn);
     return { color: rest.color, backgroundColor: rest.backgroundColor, backgroundImage: rest.backgroundImage };
   }
   ```
3. For hover state, dispatch a `mouseenter`/`mouseover` synthetic event then re-measure.
4. Compute contrast ratio against the background's lightest stop (the gold gradient's near-white `#FFF1B8`). Use a ratio computer: any of axe-core, contrast-ratio NPM, or a quick inline ratio function. Assert ≥ 4.5:1 after the fix.

This catches the gradient-stop trap that source-grep can't see (a source `color: var(--bone)` declaration may pass source review but fail rendered contrast against the gold gradient).

- [ ] **Step 8: Repair the trophy CTA color in `style.css`**

Find `.navbar.navbar-dark .btn-warning` (around line 101) and `.navbar.navbar-dark .btn-warning:hover` (around line 109). Confirm both declare `color: var(--purple-900);` (or `#1C0A3A`). If hover declares a different color (e.g., `color: var(--bg-card)`), fix it.

```css
.navbar.navbar-dark .btn-warning {
  background: var(--metal-gold-flat);
  color: var(--purple-900);  /* DESIGN.md trophy CTA contract: dark purple on gold */
  /* ...other properties... */
}
.navbar.navbar-dark .btn-warning:hover {
  background: var(--metal-gold-flat);
  color: var(--purple-900);  /* lock; do not flip to bone/white on hover */
  filter: brightness(1.05);
  box-shadow: var(--shadow-gold);
  /* ...other properties... */
}
```

- [ ] **Step 9: Em-dash sweep across templates**

```bash
grep -rn '—\|–\|&mdash;\|&#8212;\|--' games/worldcup/templates/ core/ templates/ --include='*.html' | grep -v 'CCC tokens — must load' | grep -v 'inline comment' | head -100
```

Expected: dozens of hits. For each:

- **Title separators** (`<title>X — Y</title>`): replace `—` with `:` or `·`. E.g., `Leaderboard — World Cup Fantasy Pool` → `Leaderboard · World Cup Fantasy Pool` or `Leaderboard: 2026 World Cup`.
- **Empty-state placeholders** (`<span>—</span>`): replace with semantic words: `Pending`, `Even`, `Awaiting`, `–` (en-dash) only when truly absent. Choose per-context; never broadcast one replacement.
- **Body copy** (`Test1 — locked in`): rewrite with comma, colon, semicolon, or period.
- **Comments in CSS/HTML**: leave alone (comments aren't user copy).

Edit each in place. This is mechanical but careful work — the meaning of each `—` depends on context.

- [ ] **Step 10: Write the failing test (em-dash discipline)**

Create `tests/test_design_p0_copy_discipline.py`:

```python
"""P0 S0.3 — lock: no em-dashes (—) in user-facing template copy.
PRODUCT.md + DESIGN.md Copy Discipline."""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
TEMPLATE_DIRS = [
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup',
    ROOT / 'core' / 'main' / 'templates' / 'main',
    ROOT / 'core' / 'auth' / 'templates' / 'auth',
    ROOT / 'templates',
]

# Lines beginning with a Jinja comment ({# ... #}) or HTML comment (<!-- ... -->) are exempt.
COMMENT_LINE = re.compile(r'^\s*({#|<!--)')


def _user_copy_lines(path: Path):
    for line in path.read_text().splitlines():
        if COMMENT_LINE.match(line):
            continue
        yield line


def test_no_em_dash_in_user_facing_copy():
    offenders = []
    for tdir in TEMPLATE_DIRS:
        if not tdir.exists():
            continue
        for path in tdir.rglob('*.html'):
            # Skip admin/* (out of scope for this project)
            if 'admin' in path.parts:
                continue
            for i, line in enumerate(_user_copy_lines(path), start=1):
                if '—' in line or '&mdash;' in line or '&#8212;' in line:
                    offenders.append((path.relative_to(ROOT), i, line.strip()[:120]))
    assert not offenders, f'Em-dash discipline violations: {offenders[:20]}'
```

- [ ] **Step 11: Run all tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py tests/test_design_p0_contrast.py tests/test_design_p0_copy_discipline.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright
```

All green.

- [ ] **Step 12: Visual smoke**

Boot dev server, take desktop + 375 mobile screenshots of `/worldcup/leaderboard`, `/worldcup/`, `/worldcup/picks`, `/`, `/login`. Save under `.impeccable-review/s0.3/`. Confirm sub-nav pills are taller (~44px) and the metal-gold trophy CTA in the navbar reads dark-on-gold.

- [ ] **Step 13: Commit**

```bash
git add tests/test_design_p0_tap_targets.py tests/test_design_p0_contrast.py tests/test_design_p0_copy_discipline.py static/css/style.css games/ core/ templates/
git commit -m "$(cat <<'EOF'
fix(p0-s0.3): mobile tap-target floor, trophy CTA contrast, em-dash sweep

(a) Sub-nav pills + leaderboard mobile cards now meet 44x44 floor.
    Mobile cards converted to whole-card-as-link with focus-visible ring.
(b) Navbar .btn-warning trophy CTA text locked to var(--purple-900)
    on rest AND hover (was flipping to white on metal-gold gradient,
    rendering 1.5:1 contrast).
(c) Every user-facing — replaced with appropriate punctuation/copy
    across in-scope templates per Copy Discipline.

Locked by three new test files under tests/test_design_p0_*.py.

Impeccable: P0 S0.3 — tap-targets, contrast, copy discipline.
Critique: leaderboard a11y 2 → 3, anti-patterns count -1, microcopy improved.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- pyright 0 errors ✓
- 44px floor on tested elements ✓
- Trophy CTA dark-on-gold ✓
- Em-dash count 0 in user-facing copy ✓

**Handoff to P1:** Cross-cutting harden complete. **Open PR `Impeccable P0 — Cross-cutting harden`** combining commits from S0.1 + S0.2 + S0.3 to `main` (or stash for end-of-project merge per §1.1; user choice). Move to P1.

---

## 3. Phase 1 — Leaderboard close (1 session)

### Session S1.1 — Shape Your Standing + trend rank-delta + clarify leaderboard copy

**Goal:** Reshape the Your Standing block from a hero-metric SaaS card into a Tribune sidebar; replace the trend column's points-delta with a rank-delta (with points-delta on hover/secondary line); voice-rewrite the page's microcopy. Run a closing critique re-check to confirm score lift.

**Prerequisites:** P0 (S0.1, S0.2, S0.3) complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- The Tier 1 leaderboard critique in this conversation history (carried forward via the plan; the new session reads this section as the brief)
- `games/worldcup/routes.py` — `def leaderboard()`
- `games/worldcup/services/ranking.py` — `compute_rank_neighbors`
- `games/worldcup/services/snapshots.py` — `WorldCupRankSnapshot` query helpers
- `games/worldcup/templates/worldcup/leaderboard.html`
- `static/css/style.css` — `.your-standing*`, `.leaderboard-*`, `.wc-eyebrow*`

**Files in scope (WRITE):**
- `games/worldcup/services/ranking.py` — add a `compute_rank_delta(enrollment, window_days=1)` helper backed by `WorldCupRankSnapshot`
- `games/worldcup/routes.py` — wire `rank_delta` into the leaderboard context dict
- `games/worldcup/templates/worldcup/leaderboard.html` — Your Standing reshape, trend column rewrite, voice copy
- `static/css/style.css` — `.your-standing` rules updated, `.your-standing-caption` font-family corrected to Newsreader, new `.rank-delta-up/down/even` rules
- `tests/test_worldcup_ranking.py` (extend) — `compute_rank_delta` unit tests
- `tests/test_design_p1_leaderboard.py` (new) — surface-shape regression locks

**Tasks:**

- [ ] **Step 1: Read brief**

Re-read this plan's S1.1 block, the leaderboard's Critique Report (in chat history if available; otherwise carry the Priority Issues forward from the leaderboard's commit messages of P0 sessions), and DESIGN.md's Eyebrow + Newsroom + Lift-At-Rest rules.

- [ ] **Step 2: Compute-rank-delta helper — failing test**

Edit `tests/test_worldcup_ranking.py` (or create if absent). Add:

```python
def test_compute_rank_delta_returns_signed_int_or_none(app, db_session):
    """compute_rank_delta(enrollment, window_days) returns positive int (rank improved),
    negative (rank dropped), zero (held), or None (insufficient snapshot history)."""
    from games.worldcup.services.ranking import compute_rank_delta
    from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
    from games.worldcup.constants import SEASON_YEAR
    from datetime import date, timedelta
    # Setup: an enrollment with two snapshots (yesterday rank=5, today rank=3 → delta=+2)
    e = WorldCupEnrollment(user_id=..., season_year=SEASON_YEAR)  # fill via fixture
    db_session.add(e); db_session.flush()
    db_session.add_all([
        WorldCupRankSnapshot(enrollment_id=e.id, rank=5, total_score=10.0, captured_on=date.today() - timedelta(days=1)),
        WorldCupRankSnapshot(enrollment_id=e.id, rank=3, total_score=18.0, captured_on=date.today()),
    ])
    db_session.flush()
    assert compute_rank_delta(e, window_days=1) == 2

def test_compute_rank_delta_returns_none_when_no_prior_snapshot(app, db_session):
    from games.worldcup.services.ranking import compute_rank_delta
    e = WorldCupEnrollment(...)
    db_session.add(e); db_session.flush()
    # No snapshots
    assert compute_rank_delta(e, window_days=1) is None
```

(Adapt to existing test fixtures — check what `tests/conftest.py` provides.)

- [ ] **Step 3: Run, see fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v -k delta
```

- [ ] **Step 4: Implement `compute_rank_delta` in `services/ranking.py`**

```python
def compute_rank_delta(enrollment, window_days: int = 1) -> int | None:
    """Return positive int if rank improved (smaller rank number) over `window_days`,
    negative if rank dropped, zero if held, None if insufficient snapshot history.
    Snapshots must be season-scoped via the enrollment FK (CLAUDE.md invariant)."""
    from games.worldcup.models import WorldCupRankSnapshot
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=window_days)
    today = WorldCupRankSnapshot.query.filter_by(enrollment_id=enrollment.id).order_by(
        WorldCupRankSnapshot.captured_on.desc()).first()
    prior = WorldCupRankSnapshot.query.filter(
        WorldCupRankSnapshot.enrollment_id == enrollment.id,
        WorldCupRankSnapshot.captured_on <= cutoff,
    ).order_by(WorldCupRankSnapshot.captured_on.desc()).first()
    if today is None or prior is None:
        return None
    return prior.rank - today.rank  # smaller rank = better
```

- [ ] **Step 5: Run, see pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v -k delta
```

- [ ] **Step 6: Wire `rank_delta` into the leaderboard route**

Edit `games/worldcup/routes.py`'s `leaderboard()` view. For each enrollment in the standings, compute `rank_delta` (1-day window). Pass into the template context as part of each row's dict.

- [ ] **Step 7: Reshape Your Standing block in `leaderboard.html`**

Replace the existing `.your-standing` block with a Tribune-shaped version:

```jinja
{% if your_standing %}
<section class="your-standing-tribune animate-in mt-4" role="region" aria-labelledby="your-standing-h">
  <span class="wc-eyebrow" id="your-standing-h">Your Position</span>
  <div class="your-standing-tribune-grid">
    <div class="your-standing-tribune-rank">
      <span class="wc-numeral your-standing-tribune-numeral">{{ your_standing.rank }}</span>
      <span class="your-standing-tribune-of">of {{ total_players }}</span>
    </div>
    <p class="your-standing-tribune-caption mb-0">
      {{ standing_caption }}
    </p>
  </div>
</section>
{% else %}
<aside class="your-standing-tribune your-standing-tribune-empty animate-in mt-4">
  <p class="mb-0">
    <a href="{{ url_for('worldcup.join') }}" class="text-decoration-none">
      Join the pool
    </a> to claim your seat in the standings.
  </p>
</aside>
{% endif %}
```

The `standing_caption` is computed in the route as a voice-driven string (Step 8).

- [ ] **Step 8: Voice-drive the standing caption in the route**

In `routes.py`, after computing your_standing's position, build a voice-driven caption string:

```python
def _standing_caption(your_standing, total_players, ranked_enrollments, rank_delta):
    """Voice-driven 'where you stand' line. Sharp. Competitive. Pleasure."""
    rank = your_standing.rank
    if rank == 1:
        if rank_delta and rank_delta > 0:
            return f'You took the top. Don\'t look down.'
        return 'Top of the table. The chase is yours to lose.'
    if rank == total_players:
        return 'Cellar dweller. Plenty of road ahead.'
    leader_score = ranked_enrollments[0].total_score
    next_above = next((e for e in ranked_enrollments if e.rank < rank and e.rank == rank - 1), None)
    delta_to_lead = leader_score - your_standing.total_score
    delta_to_next = (next_above.total_score - your_standing.total_score) if next_above else 0.0
    if rank_delta and rank_delta > 0:
        return f'Up {rank_delta}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
    if rank_delta and rank_delta < 0:
        return f'Down {-rank_delta}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
    return f'Holding {rank}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
```

Pass `standing_caption` into the template.

- [ ] **Step 9: Replace trend column with rank-delta**

In the desktop table:

```jinja
<th scope="col" class="text-end">Move</th>  {# was "Trend" #}
...
<td class="text-end">
  {% if e.rank_delta is none %}
    <span class="text-muted" aria-label="Awaiting first matchday">Pending</span>
  {% elif e.rank_delta > 0 %}
    <span class="rank-delta-up wc-numeral" aria-label="Up {{ e.rank_delta }}">↑{{ e.rank_delta }}</span>
  {% elif e.rank_delta < 0 %}
    <span class="rank-delta-down wc-numeral" aria-label="Down {{ -e.rank_delta }}">↓{{ -e.rank_delta }}</span>
  {% else %}
    <span class="rank-delta-even text-muted" aria-label="Even">Even</span>
  {% endif %}
</td>
```

Same pattern in the mobile card. Replace `<small>Trend: ...</small>` with the rank-delta rendering. Carry the points-delta as a tooltip (`title=` attribute) for the analyst register:

```jinja
<span class="rank-delta-up" title="Points: +{{ e.points_delta }}">↑{{ e.rank_delta }}</span>
```

- [ ] **Step 10: Update CSS for new shape**

In `static/css/style.css`, replace `.your-standing` rules with `.your-standing-tribune` rules. Caption font-family **Newsreader** (Newsroom Rule). Eyebrow color stays gold (the override to red is gone). Rank numeral large in Teko. No side-stripe (already removed in S0.2; lock).

```css
.your-standing-tribune {
  background-color: var(--surface-card);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow-sm);
}
.your-standing-tribune-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1.5rem;
  align-items: center;
}
.your-standing-tribune-numeral {
  font-family: 'Teko', sans-serif;
  font-size: 3.5rem;
  font-weight: 600;
  line-height: 1;
  color: var(--platform-primary);  /* council purple */
  font-feature-settings: 'tnum';
}
.your-standing-tribune-of {
  font-family: 'Teko', sans-serif;
  font-size: 0.85rem;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  display: block;
  margin-top: 0.25rem;
}
.your-standing-tribune-caption {
  font-family: 'Newsreader', Georgia, serif;  /* NEWSROOM RULE */
  font-size: 1.05rem;
  line-height: 1.5;
  color: var(--text-ink);
}
.your-standing-tribune-empty p {
  font-family: 'Newsreader', Georgia, serif;
  color: var(--text-secondary);
}
.rank-delta-up { color: var(--success); font-weight: 600; }
.rank-delta-down { color: var(--danger); font-weight: 600; }
.rank-delta-even { font-weight: 500; }
```

- [ ] **Step 11: Voice rewrite of remaining microcopy**

Rewrite headers + supporting copy on `leaderboard.html`:

| Before | After |
|---|---|
| `<title>Leaderboard — World Cup Fantasy Pool</title>` | `<title>The Standings: 2026 World Cup Pool</title>` |
| `<h1>Leaderboard</h1>` | `<h1>The Standings</h1>` |
| `<span class="wc-eyebrow">Live Standings</span>` | `<span class="wc-eyebrow">{% if deadline_passed %}Tonight's Ledger{% else %}Tribute Window Open{% endif %}</span>` |
| `<th>Trend</th>` | `<th scope="col" class="text-end">Move</th>` |
| `No players enrolled yet. Be the first!` | `The ledger awaits its first name. Lock your roster.` |
| Empty trend `—` (mobile) | `Pending` |

Apply similarly throughout.

- [ ] **Step 12: Surface-shape regression test**

Create `tests/test_design_p1_leaderboard.py`:

```python
"""P1 S1.1 — lock the leaderboard's reshape."""
from pathlib import Path
import re

TEMPLATE = Path(__file__).parent.parent / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
CSS = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_your_standing_tribune_replaces_hero_metric_block():
    src = TEMPLATE.read_text()
    assert 'your-standing-tribune' in src, 'Your Standing must use the tribune-reshape class'
    assert 'your-standing-rank-numeral' not in src, 'Old hero-metric class must be removed'
    assert 'border-left' not in src, 'No inline side-stripe styles in the template'

def test_your_standing_caption_uses_newsreader():
    css = CSS.read_text()
    rule = re.search(r'\.your-standing-tribune-caption\s*\{([^}]+)\}', css)
    assert rule and 'Newsreader' in rule.group(1), 'Caption must be Newsreader (Newsroom Rule)'

def test_trend_column_renders_rank_delta_not_points_delta():
    src = TEMPLATE.read_text()
    # Header is Move, not Trend
    assert '<th scope="col" class="text-end">Move</th>' in src or 'rank-delta-up' in src, \
        'Trend column should render rank delta, header "Move"'
```

- [ ] **Step 13: Run pytest + Playwright MCP verification (Layer B)**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright
```

Then via Playwright MCP, against the running dev server:

1. `browser_navigate` to `/worldcup/leaderboard`. `browser_evaluate`:
   ```javascript
   () => {
     const cap = document.querySelector('.your-standing-tribune-caption');
     const eyebrow = document.querySelector('.your-standing-tribune .wc-eyebrow');
     const wrapper = document.querySelector('.your-standing-tribune');
     const trendUp = document.querySelector('.rank-delta-up');
     return {
       captionFontFamily: cap ? getComputedStyle(cap).fontFamily : null,
       eyebrowColor: eyebrow ? getComputedStyle(eyebrow).color : null,
       wrapperBorderLeft: wrapper ? getComputedStyle(wrapper).borderLeftWidth + ' ' + getComputedStyle(wrapper).borderLeftColor : null,
       trendUpRendered: !!trendUp,
       trendUpText: trendUp ? trendUp.textContent.trim() : null,
     };
   }
   ```
2. Assert: `captionFontFamily` contains `Newsreader`; `eyebrowColor` is the gold token (around `rgb(201, 162, 39)`), not red; `wrapperBorderLeft` width is `0px`; `trendUpRendered` is true and the text starts with `↑`.
3. Take desktop + mobile screenshots to `.impeccable-review/s1.1/after/`.

- [ ] **Step 14: Re-run impeccable critique on the leaderboard**

`$impeccable critique games/worldcup/templates/worldcup/leaderboard.html`. Compare to baseline (Design Health 23/40, Audit 11/20). Record new scores in commit message.

- [ ] **Step 15: Commit**

```bash
git add tests/test_design_p1_leaderboard.py tests/test_worldcup_ranking.py games/worldcup/services/ranking.py games/worldcup/routes.py games/worldcup/templates/worldcup/leaderboard.html static/css/style.css
git commit -m "$(cat <<'EOF'
feat(p1-s1.1): reshape Your Standing as Tribune sidebar; rank-delta trend; voice copy

Closes the leaderboard exemplar's per-page Priority Issues:
  P1: Your Standing reshaped from hero-metric SaaS card to Tribune sidebar.
      No side-stripe, gold eyebrow restored, Newsreader caption per Newsroom Rule.
  P1: Trend column now renders rank-delta (↑2/↓1/Even/Pending) instead of
      points-delta. Points-delta retained as tooltip for analyst register.
  P2: Voice rewrite of title, h1, eyebrow, empty state, column header.
  P2: Empty/anon viewer now sees a join callout, not silence.

New helper: services/ranking.compute_rank_delta(enrollment, window_days) backed by
WorldCupRankSnapshot. Season-scoped per CLAUDE.md invariant.

Locked by tests/test_design_p1_leaderboard.py and the rank-delta unit tests.

Impeccable: P1 S1.1 — leaderboard close.
Critique re-run: <RECORD NEW SCORE HERE>
EOF
)"
```

**Verification gate:**
- pytest green ✓
- pyright 0 errors ✓
- Re-run critique recorded ✓
- Visual smoke desktop + mobile ✓
- All Tier 1 Priority Issues marked closed ✓

**Handoff to P2:** Leaderboard exemplar complete. Open PR `Impeccable P1 — Leaderboard close`. Move to live-state cluster expansion.

---

## 4. Phase 2 — Live state cluster (6 sessions)

Each session takes one live-state surface from "no critique done" → "critique done + per-page execution complete + re-critique scored." The pattern is identical across S2.1–S2.5; S2.6 is a cross-cluster polish.

### Per-session pattern (applies to S2.1–S2.5)

**Files in scope (READ):** PRODUCT.md, DESIGN.md, CLAUDE.md, the target template, supporting routes/services, related CSS sections, the live-state context builder (`core/main/home_context.py` for state-bearing pages).

**Tasks:**

- [ ] **Step 1: Boot dev server, capture before-screenshots at desktop + mobile.** Save under `.impeccable-review/<session-id>/before/`.
- [ ] **Step 2: Run `$impeccable critique <target>`.** Two-assessment workflow per the impeccable critique reference. Sub-agent for design review; deterministic detector against rendered+inlined HTML; combined report.
- [ ] **Step 3: Read the report; decide which Priority Issues land in this session.** Stretch issues go to Backlog (§0.4). Don't push past 3-5 priority fixes per session.
- [ ] **Step 4: For each Priority Issue, execute its recommended impeccable command.** `$impeccable shape <component>`, `$impeccable clarify <copy>`, `$impeccable adapt <responsive>`, etc.
- [ ] **Step 5: Add session-specific regression tests** under `tests/test_design_p2_<session>.py`. Lock the most important shape decisions in source.
- [ ] **Step 6: Capture after-screenshots** under `.impeccable-review/<session-id>/after/`.
- [ ] **Step 7: Re-run `$impeccable critique <target>`.** Record score delta.
- [ ] **Step 8: Run `pytest` + `pyright`. Commit.**

### Session inventory

- [ ] **S2.1 — `home_shell.html` + `_home_live.html`** (the World Cup home in live state). Cross-cutting note: this surface uses `core/main/home_context.py` builders. Critique covers the page state but execution may need the partials in `core/main/templates/main/_home_live.html` plus `_dossier_card.html` / `_fixture_card.html`. Likely Priority Issues: dossier card hierarchy, live-state sparkline communication, week-delta gating UX.

- [ ] **S2.2 — `schedule.html`** (live mode shows in-progress + recently-finished matches). Likely Priority Issues: live-dot indicator clarity, live-vs-final visual differentiation, kickoff time formatting (PRODUCT.md: short-burst comprehension).

- [ ] **S2.3 — `team_detail.html`** (live ownership ribbon, score events stream, per-match column). Likely Priority Issues: ownership ribbon information density (D11 privacy invariant locks the count display, see CLAUDE.md), per-match column unit consistency, live score-event motion.

- [ ] **S2.4 — `stats.html`** (Stats Hub: country/tier KPIs, tier combos). Likely Priority Issues: stats-curious vs analyst register layering, table semantics (catch any tables S0.2 missed), filter/segment affordances.

- [ ] **S2.5 — `player_detail.html`** (other player's roster + score breakdown). Likely Priority Issues: rivalry framing, comparison shape (you vs them), pre/post-deadline differential.

- [ ] **S2.6 — Live cluster polish + re-critique.** Run `$impeccable polish <target>` against each S2.1–S2.5 surface. Re-run `$impeccable critique` on each + on the leaderboard (in case S2 work touched shared chrome or partials). Aggregate score lift across the cluster. Open PR `Impeccable P2 — Live state cluster`.

---

## 5. Phase 3 — Global chrome + auth + errors (4 sessions)

Same per-session pattern as P2. Global chrome runs before pre/post-state cluster work because every state-bearing surface inherits the chrome — fixing chrome first means later state-cluster sessions don't fight chrome regressions.

### Session inventory

- [ ] **S3.1 — `templates/base.html` (navbar, footer, sub-nav slot, body class flow).** This sets the chrome every other surface inherits. Likely Priority Issues: navbar dropdown a11y, footer voice/utility split (DESIGN.md defines the two-band structure), sub-nav scroll behavior on mobile, navbar-scrolled compaction smoothness.

- [ ] **S3.2 — Auth pages cluster.** `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `change_password.html`, `profile.html`. Run a single `$impeccable critique` per page (they're small, batch is feasible). Likely Priority Issues: auth-page Tribunal Black backdrop atmosphere, focus management, error message voice, password-reset-token UX.

- [ ] **S3.3 — Platform home (`core/main/templates/main/index.html`) + 12 component partials.** This is the biggest single template by partial-count. The home page dispatcher critiques separately from the four state partials (which are covered in P2/P4/P5). This session focuses on the dispatcher and any partials not already touched (e.g., `_game_card.html`, `_game_tiles_compact.html`).

- [ ] **S3.4 — Errors (`404.html`, `500.html`) + cluster polish + re-critique.** Errors are small — 30-min work. Wrap with cluster-wide polish. Open PR `Impeccable P3 — Global chrome + auth + errors`.

---

## 6. Phase 4 — Pre-live state cluster (5 sessions)

Same per-session pattern.

### Session inventory

- [ ] **S4.1 — `_home_pre.html` + `_home_out.html`** (the World Cup home in pre states). Likely Priority Issues: countdown card emotional fatigue if user visits often, ballot card readability, Tribute Window framing.

- [ ] **S4.2 — `picks.html` + `_pick_row.html`** (the pick UI cluster). This is the highest-stakes pre-live surface; users spend the most time here. Likely Priority Issues: pick accordion UX (the `transition: max-height` finding from the leaderboard detector applies here), tier visualization, multiplier explanation, save/lock affordance, mobile single-handed pick flow.

- [ ] **S4.3 — `join.html` + `rules.html`**. Lower-frequency but first-impression critical. Likely Priority Issues: rules typography (long-form Newsreader prose), join CTA voice, scoring system explanation depth.

- [ ] **S4.4 — `groups.html`**. Likely Priority Issues: group fixture grid density, country-flag legibility, mobile column collapse, table semantics.

- [ ] **S4.5 — Pre-live cluster polish + re-critique.** Per pattern. Open PR `Impeccable P4 — Pre-live state cluster`.

---

## 7. Phase 5 — Post-live state cluster (3 sessions)

Same per-session pattern.

### Session inventory

- [ ] **S5.1 — `_home_post.html`** (the World Cup home in post state). Likely Priority Issues: champion banner emotional payoff, retrospective tone, "the club will remember" voice from DESIGN.md's North Star.

- [ ] **S5.2 — Post-state component partials.** `_champion_banner.html`, `_dispatches.html`, `_commish_note.html`, `_recent_results.html` (post variant). The shared partials get their own session because they're used across multiple post-state contexts. Likely Priority Issues: champion typographic moment, dispatches narrative voice, commish note signature.

- [ ] **S5.3 — Post-live cluster polish + re-critique.** Open PR `Impeccable P5 — Post-live state cluster`.

---

## 8. Phase 6 — Final polish + scorecard (2 sessions)

### Session S6.1 — Cross-surface `$impeccable polish`

**Goal:** Run the polish command across every public WC + global surface as a final pass. Catch anything missed in cluster-level polish.

- [ ] **Step 1: Inventory.** List every template touched in P1–P5. ~38 templates.
- [ ] **Step 2: Run `$impeccable polish` per cluster.** Don't run per-template (too granular); run per-state-cluster (live, pre, post, global).
- [ ] **Step 3: Resolve any final findings.** Tighten copy, micro-spacing, motion polish.
- [ ] **Step 4: Re-run `$impeccable critique` on the four Tier 1 exemplars** (leaderboard, home_shell live, picks, base.html). Record final scores.
- [ ] **Step 5: Run full pytest + pyright.** Green.
- [ ] **Step 6: Commit polish.**

### Session S6.2 — Scorecard, handoff doc, merge

**Goal:** Document the project's outcomes. Merge `design/wc-polish` → `main`.

- [ ] **Step 1: Write a project scorecard.** Save under `docs/superpowers/specs/2026-XX-XX-impeccable-design-improvement-scorecard.md`. Include:
  - Baseline scores per Tier 1 exemplar (Tier 1: 23/40, 11/20).
  - Final scores per Tier 1 exemplar.
  - Anti-patterns count: before/after.
  - Cumulative findings closed.
  - Backlog items deferred (with rationale).
  - Lessons learned for future impeccable work.
- [ ] **Step 2: Update CLAUDE.md if any patterns warrant locking** (e.g., the new Tribune sidebar shape if it becomes a reusable component, the rank-delta helper, the regression-test patterns).
- [ ] **Step 3: Open final PR** `Impeccable P6 — Final polish + project close`.
- [ ] **Step 4: Merge `design/wc-polish` → `main`** after PR review.
- [ ] **Step 5: Tag the release** (e.g., `impeccable-v1`).

---

## 9. Session checklist (update as you go)

Mark each session as it completes. Append the session-completion commit SHA for traceability.

### Phase 0 — Cross-cutting harden
- [x] S0.1 — Bootstrap shadow leak migration (commit: 60aee97)
- [x] S0.2 — Side-stripe ban migration + table semantics sweep (commit: e4882ca)
- [x] S0.3 — Mobile tap-target floor + white-on-gold contrast + em-dash sweep (commit: 37a57cf)
- [ ] **PR P0** opened: ____

### Phase 1 — Leaderboard close
- [ ] S1.1 — Shape Your Standing + trend rank-delta + clarify copy (commit: ____)
- [ ] **PR P1** opened: ____

### Phase 2 — Live state cluster
- [ ] S2.1 — home_shell + _home_live (commit: ____)
- [ ] S2.2 — schedule (commit: ____)
- [ ] S2.3 — team_detail (commit: ____)
- [ ] S2.4 — stats (commit: ____)
- [ ] S2.5 — player_detail (commit: ____)
- [ ] S2.6 — live cluster polish + re-critique (commit: ____)
- [ ] **PR P2** opened: ____

### Phase 3 — Global chrome + auth + errors
- [ ] S3.1 — base.html (chrome) (commit: ____)
- [ ] S3.2 — auth cluster (commit: ____)
- [ ] S3.3 — platform home + partials (commit: ____)
- [ ] S3.4 — errors + cluster polish (commit: ____)
- [ ] **PR P3** opened: ____

### Phase 4 — Pre-live state cluster
- [ ] S4.1 — _home_pre + _home_out (commit: ____)
- [ ] S4.2 — picks + _pick_row (commit: ____)
- [ ] S4.3 — join + rules (commit: ____)
- [ ] S4.4 — groups (commit: ____)
- [ ] S4.5 — pre-live cluster polish + re-critique (commit: ____)
- [ ] **PR P4** opened: ____

### Phase 5 — Post-live state cluster
- [ ] S5.1 — _home_post (commit: ____)
- [ ] S5.2 — post-state component partials (commit: ____)
- [ ] S5.3 — post-live cluster polish + re-critique (commit: ____)
- [ ] **PR P5** opened: ____

### Phase 6 — Final polish
- [ ] S6.1 — cross-surface polish (commit: ____)
- [ ] S6.2 — scorecard + merge (commit: ____)
- [ ] **PR P6** opened: ____
- [ ] **Merge `design/wc-polish` → `main`**: ____
- [ ] **Tag**: `impeccable-v1`

---

## 10. Plan self-review (preserved for future maintenance)

This section was a checklist run at plan creation. Notes preserved so future amendments to the plan can verify they don't break invariants.

**Spec coverage** — every Tier 1 leaderboard finding has a session that closes it:
- P0 systemic: shadow leak (S0.1), side-stripe (S0.2), table semantics (S0.2), mobile tap-targets (S0.3), white-on-gold contrast (S0.3), em-dash sweep (S0.3).
- P1 page-specific: Your Standing reshape (S1.1), trend rank-delta (S1.1), voice copy (S1.1), empty state (S1.1).
- Future findings from new exemplars get folded into their session's scope; cross-cutting finds go into the Backlog (§0.4) and a future session picks them up.

**Placeholder scan** — none used; cross-cutting tasks have full code, per-page tasks use the explicit "run critique then execute" framework because their specific edits depend on what critique surfaces (and pre-specifying them would be the placeholder-prediction trap the writing-plans skill warns about).

**Type consistency** — `compute_rank_delta(enrollment, window_days)` is the single new helper; tested in S1.1, consumed by `routes.leaderboard()` in the same session. Existing types untouched.

**Adaptation rule** — when a per-page critique surfaces issues that should have been cross-cutting, those issues land in the Backlog and a "P0 follow-up" mini-session may be inserted between phases. The plan is adaptive on its tail; the head (P0 systemic + P1 leaderboard close) is fixed. See §1.8 for the full deviation-is-welcome policy.

**Verification strategy** — three layers (§1.3): source-pattern locks (cheap, CI-friendly, regression net for things that are violations in source), Playwright MCP (in-session, computed/visual ground truth, no CI cost), critique re-run (holistic). All three together; no single layer is sufficient.

**Phase order** — sequenced by §0.2 priority: live > global chrome > pre-live > post-live. Global chrome (P3) runs before the state clusters (P4, P5) so chrome regressions don't fight subsequent state-cluster work.

---

## 11. Notes on impeccable command nuances

These are subtleties the `impeccable` skill and command references encode but that are easy to miss across sessions. Read this section once at the project start; refer back when uncertain.

- **`$impeccable critique` requires sub-agent isolation.** Assessment A (LLM design review) MUST run as an isolated sub-agent that does not see the deterministic detector output. Don't shortcut this; the combined-report integrity depends on it.
- **`$impeccable detect` (the CLI) does not handle Jinja templates well.** Run it against rendered HTML with linked CSS inlined (the "inlined.html" pattern from S0/S1). Alternatively, run it against a URL via Puppeteer if the dev server is up and the page is accessible without auth.
- **The deterministic detector flags "bounce-easing" and "dark-glow" as AI-slop**, but DESIGN.md explicitly defends both for narrow uses (card-hover overshoot; trophy CTA glow). When verifying detector findings, cross-reference DESIGN.md before fixing — sometimes the right action is "add a CSS comment explaining why the rule is intentional," not "remove the rule."
- **`fullPage: true` screenshots via chrome-devtools-mcp can drop content below the viewport.** When a screenshot looks suspicious, scroll to the suspect region and take a viewport-only screenshot to confirm. Don't trust fullPage as a sole visual oracle.
- **The `register: product` setting in PRODUCT.md is load-bearing.** Brand-shaped surfaces (landing, marketing, /join) tilt toward the brand register; product-shaped surfaces (leaderboard, picks) tilt product. If a session feels like it's straddling registers, re-read PRODUCT.md's "Register" field and §0.2 of `reference/brand.md` vs `reference/product.md`.
- **Voice copy is subjective.** When a copy rewrite is uncertain, write 2-3 alternatives in the session and surface them to the user as `AskUserQuestion`. Don't push a tonal call past confirmation; the user knows the group voice better than any agent.
- **Playwright MCP availability check first.** At session start, confirm `mcp__plugin_playwright_playwright__*` tools are loadable via ToolSearch. If not, fall through to `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*` — both expose `browser_navigate`, `browser_evaluate`, `browser_take_screenshot` equivalents. Don't fail the session over which MCP is reachable; pick the one that loads.
- **Auth-gated routes during Playwright probes.** The dev DB at `instance/fantasy_platform.db` carries a session cookie persisted across runs (the Tier 1 baseline session created a `review_user`). If the browser navigates and lands on `/login`, fill the form once; subsequent probes within the same session reuse the cookie. If a fresh review user is needed, follow the pattern from the Tier 1 baseline (Python script that adds a user with `username` + email + password set, season-scoped enrollment).
- **Inlining linked CSS for `$impeccable detect`.** The CLI detector won't resolve `/static/css/style.css` from a saved HTML file. Inline `tokens.css` + `style.css` into the HTML before scanning, OR point the detector at the live URL via Puppeteer (which loads CSS fully). The Tier 1 baseline used the inline approach; either is fine.

---

**End of plan.**
