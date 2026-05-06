# Spec C Plan 5 — WC Visual Polish CSS Sweep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define CSS for the orphan utility classes the Plan 4 home-shell partials emit and lift dark-surface contrast on the WC hub so Plan 4's structural state-shell ships with the polish it deferred.

**Architecture:** One additive Plan-5-headed block appended to `static/css/style.css` containing five clusters: hero typography, champion banner orphans, roster recap row, recent-results accent, and dark-surface utility lifts (`.text-muted` broadcast + table exclusion + narrow `.text-success`/`.text-danger`). One single-line markup wrap in `_home_post.html` enables the gold-gradient `.champion-name`. All selectors scope through their parent surface (`.card.wc-card`, `.card.wc-card.wc-hero-grad`, `.page-hero.wc-hero-grad`, `.table-worldcup`) so the rules win specificity over Bootstrap defaults and don't leak into Spec B's separate `.home-shell` platform home.

**Tech Stack:** CSS3 (custom properties + media queries), Bootstrap 5 (existing), Jinja2 (one template wrap). No Python, no JS, no migrations.

---

## Brainstorm Decision Log (frozen at plan-write time)

The brainstorm session that produced this plan locked four shaping choices:

1. **Scope includes** the `.text-success`/`.text-danger` sweep alongside the `.text-muted` lift — these were originally optional but the post-Plan-4 audit showed both are real contrast bugs in the home-shell hero stat blocks.
2. **Champion banner = Premium vibe** — match the energy of Spec B's `.home-shell .champion-banner` (legacy at `style.css:1388-1500`): `.champion-flag` at 5rem mobile / 7rem desktop with drop-shadow filters; `.champion-name` with Teko + gold-gradient text fill.
3. **`.is-roster-match` = Subtle** — gold left-border + faint gold-to-white gradient (NOT the prominent gold-tint version, which fails contrast for dark Teko team names; see `feedback_mockup_contrast.md` memory).
4. **Hero typography = Subordinate** — keep `<h1>World Cup Fantasy Pool>` as the visual lead; `.hero-headline` stays at Bootstrap h2 weight 600 (not Teko), `.hero-subhead` only lifts the muted color.
5. **Plan 6 backlog absorbed into Plan 5** — both deferred items (champion-name markup hook + `team_detail.fixture-pts` audit) brought in. Plan 5 ships with no known follow-ups.

---

## Pre-flight Setup (do BEFORE Task 1)

This plan was scoped to be executed in an isolated worktree per the user's standing setup pattern. Before starting any task:

- [ ] **Confirm Plan 4 merged.** Run `gh pr view 8 --json state -q .state` — must print `MERGED`. If not, stop and base this plan on `redesign/ccc-worldcup-plan4` with Plan 4 merged first.

- [ ] **Create the worktree.** From `/Users/bhagstrom/fantasy-platform`:
  ```bash
  git fetch origin main
  git worktree add /Users/bhagstrom/fantasy-platform-ccc-wc-plan5 -b redesign/ccc-worldcup-plan5 origin/main
  ```

- [ ] **Symlink instance + venv into the worktree.**
  ```bash
  cd /Users/bhagstrom/fantasy-platform-ccc-wc-plan5
  ln -s /Users/bhagstrom/fantasy-platform/instance instance
  ln -s /Users/bhagstrom/fantasy-platform/venv venv
  ```

- [ ] **Pre-approve subagent Edit/Write perms on the worktree path.** Open `/Users/bhagstrom/fantasy-platform/.claude/settings.local.json` and add the worktree path under `permissions.allow` per the pattern in `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/feedback_subagent_worktree_perms.md`. Without this, subagents that try to edit files in the worktree will hit deny prompts.

- [ ] **Verify dev DB state for visual smoke.** Open Task 9's smoke matrix — the `post` state requires the final match to be completed with a `winner_team_id`. If `flask worldcup status` from the worktree shows the final as not completed, run `flask worldcup process-match` to seed it before Task 9.

All subsequent tasks assume cwd = `/Users/bhagstrom/fantasy-platform-ccc-wc-plan5`.

---

## Files to Create or Modify

| File | Change | Notes |
|---|---|---|
| `static/css/style.css` | Modify (append) | One new ~75-line Plan 5 block at end of file |
| `games/worldcup/templates/worldcup/_home_post.html` | Modify (1 line, line 22) | Wrap `{{ champion_team.display_name }}` in `<span class="champion-name">…</span>` |

That's it. No tokens.css change (audit confirmed `--gold-light`, `--metal-gold`, `--font-teko`, `--live-green`, `--live-red`, `--bs-secondary-color` all already exist; `--gold-deep` is replaced by the inline hex `#8a6a1a` from `--metal-gold-flat`'s end stop in Task 7's `.text-warning` override — no new token needed).

---

## TDD Note

CSS-only work doesn't fit the standard write-failing-test-first cycle. The discipline for this plan is:

- **Per-task visual smoke** — render the affected surface in a browser after each CSS task and eyeball that the rule applied as designed and didn't break anything.
- **Existing test suite stays green** as a regression backstop — the home-shell partial templates render the same DOM (only Task 4 changes markup, and only by adding a `<span>` wrapper that doesn't change visible text). Run the full suite at Task 10.
- **Pyright unchanged** — no Python files touched.
- **No new unit tests** for CSS rules. CodeRabbit + manual smoke + the existing 265 tests cover the regression surface.

---

## Task 1: Append Plan 5 block scaffold to style.css

**Files:**
- Modify: `static/css/style.css` (append at end of file)

- [ ] **Step 1: Find the end of the file.**

```bash
wc -l static/css/style.css
```
Note the line count — the new block goes after the current last line. Cluster comments inside the block will pad it by ~75 lines.

- [ ] **Step 2: Append the section header + empty cluster scaffolds.**

Append this exact block to `static/css/style.css`:

```css

/* ============================================================
   Plan 5: WC visual polish — orphan utilities + dark-surface legibility
   ----------------------------------------------------------------
   Closes the polish gap Plan 4 (WC Hub migration, PR #8) deferred:
   defines CSS for orphan utility classes emitted by the home-shell
   state partials, and lifts contrast on dark surfaces where Bootstrap
   defaults fail. All selectors scope through parent surfaces so the
   rules don't leak into Spec B's .home-shell platform home.

   Pattern reference: extends the dark-surface-legibility approach
   from the Plan 3 follow-up block at :3242-3286.
   ============================================================ */

/* --- Cluster 1: Hero typography (Task 2) --- */

/* --- Cluster 2: Champion banner orphans (Task 3) --- */

/* --- Cluster 3: Dark-surface .text-muted lift + table exclusion (Task 5) --- */

/* --- Cluster 4: Dark-surface .text-success/.text-danger lift (Task 6) --- */

/* --- Cluster 5: Roster recap row + Recent results accent (Tasks 7, 8) --- */
```

- [ ] **Step 3: Verify nothing else regressed.**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```
Expected: 265 passed. Style.css edits don't affect Python tests; this is a baseline gate.

- [ ] **Step 4: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): scaffold Plan 5 visual-polish block in style.css"
```

---

## Task 2: Hero typography (Cluster 1)

**Files:**
- Modify: `static/css/style.css` (Cluster 1 region from Task 1)

- [ ] **Step 1: Replace the Cluster 1 placeholder with these three rules.**

```css
/* --- Cluster 1: Hero typography (Task 2) --- */

/* .hero-headline + .hero-subhead are emitted by home_shell.html on every
   state. .page-hero h1 (the brand mark) at :4021 is the visual lead at
   2.8rem/700/uppercase; .hero-headline must sit clearly below to support
   without competing. Subordinate spec (per brainstorm decision 4): no Teko,
   no uppercase, weight 600. */
.page-hero.wc-hero-grad .hero-headline {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--bone, #f5f1e8);
  letter-spacing: 0.005em;
  margin-top: 0.25rem;
}

.page-hero.wc-hero-grad .hero-subhead {
  font-size: 1rem;
  margin-top: 0.5rem;
}

/* Lift Bootstrap's .text-muted on the navy gradient hero. .82 alpha matches
   the existing thead-on-navy treatment at :3250 (Plan 3 follow-up).
   !important needed because Bootstrap's .text-muted ships with !important. */
.page-hero.wc-hero-grad .hero-subhead.text-muted {
  color: rgba(245, 241, 232, .82) !important;
}
```

- [ ] **Step 2: Restart dev server (if running) and visually smoke the headline.**

In the worktree, start the dev server with a pre-deadline fake time so the `pre` state renders the hero copy:
```bash
ENVIRONMENT=development WC_FAKE_NOW='2026-06-10T12:00:00+00:00' \
  FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```
Open `http://localhost:5099/worldcup` in a browser. Expected: `<h2>` headline below the wc-eyebrow renders in bone color at ~1.5rem weight 600; the subhead `<p>` is light bone (~.82 alpha) instead of dim grey. The brand `<h1>` still dominates the hero.

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): define .hero-headline + .hero-subhead orphan utilities"
```

---

## Task 3: Champion banner CSS — `.champion-flag` + `.champion-name` (Cluster 2)

**Files:**
- Modify: `static/css/style.css` (Cluster 2 region from Task 1)

- [ ] **Step 1: Replace the Cluster 2 placeholder with these rules.**

```css
/* --- Cluster 2: Champion banner orphans (Task 3) --- */

/* .champion-flag — display:block lifts the flag onto its own line above
   the country name (markup wraps both inside one .display-4 div). Filter
   values match .home-shell .champion-flag at :1457 verbatim — Spec B has
   validated the visual; we want parity. Scoped to the WC-specific
   .card.wc-card.wc-hero-grad container so it doesn't reach Spec B's
   .home-shell platform home, which keeps its own copy at :1457. */
.card.wc-card.wc-hero-grad .champion-flag {
  display: block;
  font-size: 5rem;
  line-height: 1;
  margin-bottom: 0.75rem;
  filter: drop-shadow(0 4px 16px rgba(0, 0, 0, .4))
          drop-shadow(0 0 24px rgba(242, 211, 107, .25));
}
@media (min-width: 768px) {
  .card.wc-card.wc-hero-grad .champion-flag { font-size: 7rem; }
}

/* .champion-name — Teko gold-gradient country name. Mirrors
   .home-shell .champion-name at :1467-1482 with the same tokens
   (--font-teko, --metal-gold) so Spec B and the WC hub render identical
   typography on their respective champion banners. Requires the markup
   wrap in _home_post.html (Task 4). */
.card.wc-card.wc-hero-grad .champion-name {
  display: block;
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.8rem;
  line-height: 1;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--metal-gold);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 0.5rem 0 0.6rem;
}
@media (min-width: 768px) {
  .card.wc-card.wc-hero-grad .champion-name { font-size: 4rem; }
}
```

- [ ] **Step 2: Visual smoke is deferred to Task 4.**

The `.champion-name` rule needs the markup wrap to take effect. The `.champion-flag` rule will already apply, but to verify both at once, smoke after Task 4. (No commit-then-immediately-edit-the-same-file anti-pattern needed; this is one logical CSS unit.)

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): define .champion-flag + .champion-name (responsive, gold-gradient)"
```

---

## Task 4: Markup wrap for `.champion-name` in `_home_post.html`

**Files:**
- Modify: `games/worldcup/templates/worldcup/_home_post.html` (line 22)

- [ ] **Step 1: Apply the one-line wrap.**

In `games/worldcup/templates/worldcup/_home_post.html`, change:
```jinja
      <div class="display-4 mb-1">
        <span class="champion-flag">{{ champion_team.flag_emoji }}</span>
        {{ champion_team.display_name }}
      </div>
```
to:
```jinja
      <div class="display-4 mb-1">
        <span class="champion-flag">{{ champion_team.flag_emoji }}</span>
        <span class="champion-name">{{ champion_team.display_name }}</span>
      </div>
```

That is one line modified (line 22 currently `        {{ champion_team.display_name }}` → `        <span class="champion-name">{{ champion_team.display_name }}</span>`).

- [ ] **Step 2: Visual smoke the post-state champion banner.**

Restart dev server with a post-tournament fake time:
```bash
# Stop the previous dev server (Ctrl+C) first, then:
ENVIRONMENT=development WC_FAKE_NOW='2026-07-25T12:00:00+00:00' \
  FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```
**Pre-req:** the dev DB's final match must be `is_completed=True` with a `winner_team_id`. If `flask worldcup status` shows the final as not completed, run `flask worldcup process-match` first to seed a champion.

Open `http://localhost:5099/worldcup` (logged in as an enrolled user). Expected:
- Flag is on its own line above the country name, ~5rem on mobile / ~7rem on ≥768px desktop, with visible gold drop-shadow.
- Country name renders as Teko display font with gold-gradient text fill, uppercase, ~2.8rem mobile / ~4rem desktop.
- Champion summary line below in lifted-muted bone color.

Resize the window across the 768px breakpoint to verify both responsive sizes.

- [ ] **Step 3: Confirm rendered text content unchanged.**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -q
```
Expected: all `home_context` tests still pass (the wrap doesn't change context shape; templates still receive `champion_team.display_name` and render its text). If any test breaks, the wrap interfered — investigate before continuing.

- [ ] **Step 4: Commit.**

```bash
git add games/worldcup/templates/worldcup/_home_post.html
git commit -m "html(wc): wrap champion country name in .champion-name span for gold-gradient style"
```

---

## Task 5: Dark-surface `.text-muted` lift + table exclusion (Cluster 3)

**Files:**
- Modify: `static/css/style.css` (Cluster 3 region from Task 1)

- [ ] **Step 1: Replace the Cluster 3 placeholder.**

```css
/* --- Cluster 3: Dark-surface .text-muted lift + table exclusion (Task 5) --- */

/* Lift .text-muted to readable on the navy .card.wc-card surface. The
   broadcast catches every direct-on-navy use across the hub: champion
   summary, hero stat block "of N" copy, deadline-date captions in
   pre/out states, fixture-row text-muted in team_detail. .82 alpha
   matches the existing thead-on-navy treatment at :3250 (Plan 3
   follow-up). Bootstrap's .text-muted ships !important so override
   matches. Plan 3's deeper-specificity rules (:3259, :3273) at .55
   alpha for tertiary leaderboard content win on (0,0,4-5,0+) — leave
   intact. */
.card.wc-card .text-muted {
  color: rgba(245, 241, 232, .82) !important;
}

/* Surgical exclusion: restore Bootstrap default for any .text-muted
   that lives inside a Bootstrap table cell. Bootstrap's white td bg
   masks the navy parent, and the lifted bone color would render
   invisible there. Concrete affected case: _pick_row.html:16 "Grp X"
   caption inside the picks accordion <td>. Mirrors the don't-broadcast
   logic from the Plan 3 follow-up block. */
.card.wc-card .table > tbody > tr > td .text-muted,
.card.wc-card .table > tbody > tr > td.text-muted {
  color: var(--bs-secondary-color) !important;
}
```

- [ ] **Step 2: Visual smoke across all 4 home-states + picks page.**

Use the dev server (restart with the appropriate WC_FAKE_NOW per row):

| Surface | URL / state | What to check |
|---|---|---|
| Pre-deadline `<p>` "Deadline: ..." | `/worldcup` with WC_FAKE_NOW=`2026-06-10T12:00:00+00:00` | bone-light text on navy, readable |
| Live "of N" copy in Your Standing | `/worldcup` with WC_FAKE_NOW=`2026-07-01T12:00:00+00:00` | bone-light text on navy, readable |
| Post champion summary text | `/worldcup` with WC_FAKE_NOW=`2026-07-25T12:00:00+00:00` | bone-light text on navy gradient, readable |
| Out-state "Deadline / N players enrolled" | `/worldcup` logged out | bone-light text on navy, readable |
| Picks page "Grp X" caption | `/worldcup/picks` (logged in, enrolled) | grey text on white td (UNCHANGED — exclusion working) |
| Leaderboard | `/worldcup/leaderboard` | Plan 3's .55 alpha rules still win for tertiary content |

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): lift .text-muted on .card.wc-card with Bootstrap-table exclusion"
```

---

## Task 6: Dark-surface `.text-success` / `.text-danger` lift (Cluster 4)

**Files:**
- Modify: `static/css/style.css` (Cluster 4 region from Task 1)

- [ ] **Step 1: Replace the Cluster 4 placeholder.**

```css
/* --- Cluster 4: Dark-surface .text-success/.text-danger lift (Task 6) --- */

/* Lift Bootstrap's .text-success/.text-danger to live tokens on audited
   navy surfaces. Two surface families:
     1. Home-shell hero stat blocks (Your Standing, Your Finish) — direct
        children of .card-body > .row, no white-td masking.
     2. team_detail.html .fixture-pts — sits in <li class="fixture-row">
        (CSS grid li, not a Bootstrap table cell), so navy bleeds through.
   Explicitly NOT broadcasting on .card.wc-card — _pick_row.html:41 lives
   inside <td colspan="5"> (white-td masking, Bootstrap green readable),
   and _home_live.html:99 lives inside .match-result-card (white card,
   Bootstrap green readable, --live-green at #64DBA0 would actually have
   WORSE contrast on white than Bootstrap's #198754). */
.card.wc-card > .card-body > .row .text-success,
.card.wc-card .fixture-pts.text-success {
  color: var(--live-green) !important;
}
.card.wc-card > .card-body > .row .text-danger,
.card.wc-card .fixture-pts.text-danger {
  color: var(--live-red) !important;
}
```

- [ ] **Step 2: Visual smoke each affected surface.**

| Surface | URL / state | What to check |
|---|---|---|
| Live trend delta in Your Standing | `/worldcup` with WC_FAKE_NOW=`2026-07-01T12:00:00+00:00` | "+X.X since last snapshot" reads in bright `--live-green` (#64DBA0), not Bootstrap dark green |
| Post climbed/slipped delta | `/worldcup` with WC_FAKE_NOW=`2026-07-25T12:00:00+00:00` | "Climbed N spots" reads in bright `--live-green` |
| team_detail fixture-pts column | `/worldcup/team/<any-team-id>` | per-match "+X.X" reads in bright green on the navy .fixture-row |
| Recent Results "+X pts" chip | `/worldcup` live state | UNCHANGED — Bootstrap green on the white .match-result-card child still readable |
| Picks page accordion drill-down | `/worldcup/picks` → expand a row | UNCHANGED — Bootstrap green inside <td colspan="5"> still readable |

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): lift .text-success/.text-danger on home-shell hero blocks + fixture-pts"
```

---

## Task 7: Roster recap row + `.text-warning` override (Cluster 5, part 1)

**Files:**
- Modify: `static/css/style.css` (Cluster 5 region from Task 1)

- [ ] **Step 1: Append these three rules to Cluster 5 (don't replace the placeholder yet — Task 8 adds more).**

Edit the Cluster 5 comment line so it reads:
```css
/* --- Cluster 5: Roster recap row + Recent results accent (Tasks 7, 8) --- */

/* .row-champion-pick — Premium gold treatment for the user's champion
   pick in the Final Roster recap (post-state). Mirrors the
   .table-worldcup .row-current-user pattern at :2476 — same three
   properties (bg tint + left-border + first-td-only) — but at .16 alpha
   (vs .06) and gold instead of red, plus a weight bump for "this row
   matters most" emphasis. White td bg + gold tint at .16 = pale cream,
   keeps Bootstrap dark text high-contrast. */
.table-worldcup .row-champion-pick > td {
  background: rgba(242, 211, 107, .16) !important;
  border-left: 3px solid var(--gold-light);
  font-weight: 600;
}
.table-worldcup .row-champion-pick > td:not(:first-child) {
  border-left: none;
}

/* The inline "Champion" badge inside the row uses .text-warning
   (Bootstrap #ffc107 with !important) which collides with the gold tint
   and reads poorly. Override to a darker gold (the dark end stop of
   --metal-gold-flat at tokens.css:33) for legibility on the cream bg. */
.table-worldcup .row-champion-pick .text-warning {
  color: #8a6a1a !important;
}
```

- [ ] **Step 2: Visual smoke the post-state Final Roster.**

Same dev server setup as Task 4 (post-state with WC_FAKE_NOW=`2026-07-25T12:00:00+00:00`). Open `/worldcup` logged in as an enrolled user whose roster includes the actual champion (verify by checking that one row in the Final Roster table is `is_champion=True`). Expected:
- Champion row has a pale cream bg tint across the row.
- 3px gold left-border on the leftmost cell (no border on subsequent cells — matches `.row-current-user` behavior).
- Row text is weight 600 (subtle visual heaviness vs the other rows).
- "Champion" inline badge text is dark gold, clearly readable against the cream.

If no enrolled user has the actual champion, you can still verify the styling visually by manually adding `class="row-champion-pick"` in browser DevTools to any roster row.

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): style .row-champion-pick + override .text-warning for legibility"
```

---

## Task 8: `.match-result-card.is-roster-match` accent (Cluster 5, part 2)

**Files:**
- Modify: `static/css/style.css` (Cluster 5 region)

- [ ] **Step 1: Append this rule to Cluster 5.**

Add after the `.row-champion-pick .text-warning` rule from Task 7:

```css

/* .match-result-card.is-roster-match — Subtle "your team played" accent
   on the live-state Recent Results card. Applies on top of
   .match-result-card (defined at :2651, white card with var(--bg-card)
   bg). Compound selector (0,0,2,0) wins over the bare card rule
   (0,0,1,0).
   
   Soft gold-to-white gradient lets the row read as flagged at a glance
   but stays scannable when 3-5 of 7 matches involve the user's picks
   during group-stage worst case (per brainstorm decision 3 — Subtle was
   chosen over Prominent specifically to handle this density). */
.match-result-card.is-roster-match {
  border-left: 3px solid var(--gold-light);
  background: linear-gradient(90deg, rgba(242, 211, 107, .10) 0%, var(--bg-card) 35%);
}
```

- [ ] **Step 2: Visual smoke the live-state Recent Results.**

Restart dev server with live-state fake time:
```bash
ENVIRONMENT=development WC_FAKE_NOW='2026-07-01T12:00:00+00:00' \
  FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```
Open `/worldcup` logged in as an enrolled user with at least one match completed where they own one of the teams. Expected:
- Match cards involving one of the user's picks have a 3px gold left-border and a faint gold-to-white left-edge gradient.
- Other match cards (no user pick involved) render as the standard plain `.match-result-card`.
- Team names and scores remain high-contrast — the gradient fades to white well before the team-name column.

- [ ] **Step 3: Commit.**

```bash
git add static/css/style.css
git commit -m "css(wc): subtle .is-roster-match accent on Recent Results match cards"
```

---

## Task 9: Full visual smoke matrix

**Files:** none (browser verification only)

This task runs the comprehensive visual smoke matrix to catch interactions between clusters and validate against all 4 hub states + the team_detail page at desktop and mobile breakpoints.

- [ ] **Step 1: Run the matrix below.** For each row, restart the dev server with the listed `WC_FAKE_NOW` (or log out for guest), open the URL, and verify the listed expectations at both window widths (resize across 768px). Take a screenshot of each cell and stash them in `.superpowers/brainstorm/<session>/smoke/` for the PR description.

| # | State | URL | WC_FAKE_NOW | Login | Expectations |
|---|---|---|---|---|---|
| 1 | out / guest | `/worldcup` | none | logged out | Hero copy: bone headline + lifted-muted subhead. Stats row stat-blocks unchanged. |
| 2 | out / unenrolled-pre | `/worldcup` | `2026-06-10T12:00:00+00:00` | logged-in user with no WC enrollment | Same hero treatment; deadline caption in lifted-muted bone. |
| 3 | pre / unsubmitted | `/worldcup` | `2026-06-10T12:00:00+00:00` | enrolled user, no picks submitted | "Deadline: ..." caption readable in lifted-muted bone. Hero typography correct. |
| 4 | pre / submitted | `/worldcup` | `2026-06-10T12:00:00+00:00` | enrolled user with picks submitted | Roster preview card unchanged; hero typography correct. |
| 5 | live / Your Standing | `/worldcup` | `2026-07-01T12:00:00+00:00` | enrolled user, mid-tournament | "of N" caption + lead-delta sentence in lifted-muted bone. Trend delta in `--live-green`/`--live-red`. |
| 6 | live / Recent Results with .is-roster-match | `/worldcup` | `2026-07-01T12:00:00+00:00` | enrolled user with completed matches involving picks | Subtle gold left-border + gradient on roster-match cards. Other cards plain. |
| 7 | post / champion banner | `/worldcup` | `2026-07-25T12:00:00+00:00` | enrolled user, final completed | Premium champion banner: 5–7rem flag with drop-shadow, gold-gradient Teko country name, lifted-muted summary. |
| 8 | post / Final Roster + .row-champion-pick | `/worldcup` | `2026-07-25T12:00:00+00:00` | enrolled user whose pick won | Champion row: cream tint, 3px gold left-border, weight-600 text, dark-gold "Champion" badge readable. |
| 9 | team_detail fixture-pts | `/worldcup/team/<id>` | `2026-07-01T12:00:00+00:00` | any logged-in user | Fixture column "+X.X" in `--live-green` on navy. text-muted "—" placeholders in lifted bone. |
| 10 | leaderboard regression | `/worldcup/leaderboard` | none | enrolled user | Plan 3 .55-alpha rules still apply on `.leaderboard-card` mobile + `.row-current-user` overlay. Trend column unchanged. |
| 11 | picks page regression | `/worldcup/picks` | `2026-06-10T12:00:00+00:00` | enrolled user | "Grp X" caption inside accordion `<td>` is grey-on-white (NOT lifted) — exclusion working. Drill-down accordion green/red points still readable. |

- [ ] **Step 2: If any cell fails, return to the relevant cluster's task and fix.** Don't proceed to Task 10 with known failures.

- [ ] **Step 3: Commit screenshots to the brainstorm session directory (not the repo) and note in the PR description which states were validated.**

No git commit on this task — visual evidence stays out of repo.

---

## Task 10: Test suite + Pyright + tooling check

**Files:** none (commands only)

- [ ] **Step 1: Run the full test suite.**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```
Expected: 265 passed (or +0 from baseline; Plan 5 adds no tests). If any test fails, investigate — most likely culprit is the Task 4 markup wrap if a test was asserting against literal HTML output.

- [ ] **Step 2: Run pyright on the full project.**

```bash
venv/bin/pyright
```
Expected: 0 errors, 0 warnings, 0 information. Plan 5 touches no Python; this is a baseline gate to confirm nothing drifted.

- [ ] **Step 3: Stat the diff for sanity.**

```bash
git diff main --stat
```
Expected: 2 files changed (`static/css/style.css`, `games/worldcup/templates/worldcup/_home_post.html`), additions in the ~75-100 line range, deletions ≈ 0.

- [ ] **Step 4: No commit.** This task is verification only.

---

## Task 11: Push branch + open PR

**Files:** none (git/gh commands only)

- [ ] **Step 1: Push the branch.**

```bash
git push -u origin redesign/ccc-worldcup-plan5
```

- [ ] **Step 2: Open the PR.**

```bash
gh pr create --title "Spec C Plan 5 — WC visual polish (orphan utilities + dark-surface legibility)" --body "$(cat <<'EOF'
## Summary

Closes the polish gap Plan 4 (PR #8) deferred — defines CSS for orphan utility classes the home-shell state partials emit and lifts contrast on dark `.card.wc-card` surfaces where Bootstrap defaults fail.

- **One additive Plan-5-headed block** appended to `static/css/style.css` (~75 lines, 5 clusters).
- **One single-line markup wrap** in `_home_post.html` enabling the `.champion-name` gold-gradient style.
- **Zero Python, zero migrations, zero new tests.**

### Five clusters

1. **Hero typography** — `.hero-headline` (bone, weight 600, ~1.5rem) + `.hero-subhead.text-muted` lift on `.page-hero.wc-hero-grad`.
2. **Champion banner orphans** — `.champion-flag` (5–7rem responsive, drop-shadow) + `.champion-name` (Teko, gold-gradient text fill, 2.8–4rem responsive). Both scoped to `.card.wc-card.wc-hero-grad` so Spec B's `.home-shell` champion banner is untouched.
3. **`.text-muted` lift + table exclusion** — broadcast `.card.wc-card .text-muted` to .82-alpha bone; surgical exclusion restores Bootstrap default inside `<td>` (white-td masking surface — `_pick_row.html:16` "Grp X" caption).
4. **`.text-success` / `.text-danger` lift** — narrow scope to `.card.wc-card > .card-body > .row` (home-shell hero stat blocks) and `.card.wc-card .fixture-pts.text-*` (`team_detail`). Explicitly NOT broadcasting (would degrade `.match-result-card` and `_pick_row` accordion green/red).
5. **`.row-champion-pick`** (Premium gold tint + 3px gold left-border + weight-600 + `.text-warning` override) and **`.match-result-card.is-roster-match`** (Subtle gold left-border + soft gradient).

### Brainstorm decisions locked

See `docs/superpowers/plans/2026-05-06-ccc-worldcup-plan-5-visual-polish.md` "Brainstorm Decision Log" for the four design decisions made during the brainstorm session that produced this plan.

## Test plan

- [ ] All 265 tests pass (no new tests; existing suite is regression backstop)
- [ ] `pyright` clean (no Python touched)
- [ ] Visual smoke matrix complete — 11 cells across 4 home states + team_detail + 2 regression checks (leaderboard, picks page) at desktop + mobile breakpoints (see plan Task 9)
- [ ] Spec B's `.home-shell .champion-flag` (`style.css:1457`) and `.home-shell .champion-name` (`:1467`) untouched and still rendering on `/` (platform home)
- [ ] CodeRabbit review

## No follow-ups for Plan 6

The Plan 6 backlog Plan 4 seeded was absorbed into Plan 5 scope (champion-name markup hook + `team_detail.fixture-pts` audit). Plan 5 ships with no known polish follow-ups — any Plan 6 would need new scope.

@coderabbitai please review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CodeRabbit's actual review comment to land** before considering merge — per `feedback_coderabbit_timing.md`, the "processing" stub is not enough.

- [ ] **Step 4: Address any CodeRabbit findings as additional commits on the branch.** Don't squash; the squash-merge happens at GitHub merge time.

---

## Out-of-Scope Guards (do NOT do in this plan)

- **No new tests.** CSS-only work doesn't fit TDD; existing 265 tests are the regression backstop.
- **No tokens.css edits.** All required tokens already exist.
- **No Python, no routes, no models, no migrations.** Pure presentation layer.
- **No edits to existing CSS rules.** Plan 5 is additive — the new block goes at the end of `style.css`. The Plan 3 follow-up block at `:3242-3286`, the legacy `.home-shell .*` block, the `.match-result-card` base rules, all stay byte-for-byte identical.
- **No additional markup wraps beyond the one in Task 4.** The brainstorm decision was that ONE `<span class="champion-name">` wrap is the only markup change Plan 5 needs.
- **No animation.** Plan 5 is polish-only; CSS animations would read as new behavior. Defer to a future plan if desired.

## Plan 6+ candidates

**None.** The brainstorm absorbed all known Plan 6 candidates into Plan 5. Future polish plans would need fresh scope (e.g., motion / micro-interactions, mobile-specific hero layout adjustments, dark-mode token overrides — all out of scope for the current "fix what Plan 4 left orphaned" charter).
