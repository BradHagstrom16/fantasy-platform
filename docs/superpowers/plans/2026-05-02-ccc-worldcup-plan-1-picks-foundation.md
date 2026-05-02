# Spec C — Plan 1: My Picks + Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the World Cup picks flow (3 states in `picks.html`) and land the foundation Plans 2/3/4 inherit — sub-nav rewrite with mobile compactions, cross-cutting `.wc-*` CSS utility classes, and a light chrome pass on `schedule.html` / `groups.html` / `rules.html`.

**Architecture:** Adds 6 new utility CSS classes consuming existing tokens from `static/css/tokens.css` (no new tokens). Rewrites the WC sub-nav block in `templates/base.html` and adds a mobile-only compaction media query in `static/css/style.css`. Restyles `picks.html` (edit form / sealed pre-deadline / post-deadline states), `_pick_row.html` (used here and by Plan 2), and applies a shallow visual refresh to `schedule.html` / `groups.html` / `rules.html`. No Python changes; no new tests; existing 150-test suite must continue to pass.

**Tech Stack:** Bootstrap 5.3, Jinja2 templates, vanilla CSS (no preprocessors), existing Teko + Newsreader fonts loaded by Spec A. WC palette tokens (`--wc-navy`, `--wc-red`, `--wc-white`) and `body.game-worldcup` activation already live from Spec A.

**Spec reference:** `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md` §6 (Plan 1).

---

## Pre-flight

### Task 0: Worktree setup + baseline verification

**Files:** none modified yet. This task creates the working environment.

- [ ] **Step 1: Create the worktree branch off main**

```bash
cd /Users/bhagstrom/fantasy-platform
git fetch origin main
git worktree add -b redesign/ccc-worldcup-plan1 ../fantasy-platform-ccc-wc-plan1 origin/main
cd ../fantasy-platform-ccc-wc-plan1
```

Expected: new directory `../fantasy-platform-ccc-wc-plan1` exists; git status reports a clean working tree on branch `redesign/ccc-worldcup-plan1`.

- [ ] **Step 2: Verify baseline tests pass before changing anything**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all 150 tests pass. If any fail, stop and investigate before proceeding — they are baseline regressions, not introduced by this plan.

- [ ] **Step 3: Verify pyright is clean on the WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors. (Pre-existing warnings outside `games/worldcup/` are out of scope for this plan.)

- [ ] **Step 4: Confirm the spec file is accessible**

```bash
test -f docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md && echo "spec present"
```

Expected output: `spec present`.

---

## Foundation: cross-cutting WC CSS utilities

### Task 1: Add the 6 cross-cutting `.wc-*` utility classes

**Files:**
- Modify: `static/css/style.css` — add a new section after the existing `/* === WORLD CUP FANTASY POOL === */` block (around line 2136 where `body.game-worldcup` is activated). Search for `body.game-worldcup` to locate.

Verify token availability by grepping before adding:

```bash
grep -n "^\s*--wc-navy\|^\s*--wc-red\|^\s*--wc-white\|^\s*--wc-tier1\|^\s*--gold-light\|^\s*--bone-mute" static/css/tokens.css static/css/style.css
```

Expected: confirms `--wc-navy`, `--wc-red`, `--wc-white`, `--gold-light`, `--bone-mute` in `tokens.css`; `--wc-tier1`–`--wc-tier5` in `style.css`. If any are missing, stop and reconcile against `static/css/tokens.css` before proceeding.

- [ ] **Step 1: Add the new section to `static/css/style.css`**

Insert this block immediately after the existing `body.game-worldcup` activation (search for `body.game-worldcup {` to locate the insertion point — add this block after the closing `}` of that rule):

```css
/* ============================================================
   Spec C — Cross-cutting WC utility classes
   Consume Spec A's tokens.css; no new tokens.
   ============================================================ */

/* Eyebrow label — small uppercase Teko text above section headers */
.wc-eyebrow {
  font-family: 'Teko', sans-serif;
  font-size: .7rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--bone-mute);
  display: inline-block;
}
.wc-eyebrow-red { color: var(--wc-red); }
.wc-eyebrow-gold { color: var(--gold-light); }

/* Display numeral utility — Teko, tabular figures */
.wc-numeral {
  font-family: 'Teko', sans-serif;
  font-weight: 700;
  font-feature-settings: 'tnum';
  letter-spacing: .03em;
}

/* Hero gradient — radial gold-tint over linear navy-to-near-black.
   Apply via class on .page-hero or a custom hero container. */
.wc-hero-grad {
  background:
    radial-gradient(500px 200px at 100% -20%, rgba(242, 211, 107, .15), transparent 65%),
    linear-gradient(180deg, #0A1A50 0%, #00102E 100%);
}

/* Tier dot — circular tier indicator. Sibling pattern to tier-badge-{n}. */
.wc-tier-dot {
  display: inline-block;
  width: .85rem;
  height: .85rem;
  border-radius: 50%;
  vertical-align: middle;
  margin-right: .35rem;
  flex-shrink: 0;
}
.wc-tier-dot-1 { background: var(--wc-tier1); }
.wc-tier-dot-2 { background: var(--wc-tier2); }
.wc-tier-dot-3 { background: var(--wc-tier3); }
.wc-tier-dot-4 { background: var(--wc-tier4); }
.wc-tier-dot-5 { background: var(--wc-tier5); }

/* Multiplier chip — flat numeral chip for ×N displays */
.wc-multiplier-chip {
  display: inline-block;
  font-family: 'Teko', sans-serif;
  font-weight: 600;
  font-size: .82rem;
  letter-spacing: .03em;
  padding: .15rem .45rem;
  background: rgba(245, 241, 232, .08);
  border: 1px solid rgba(245, 241, 232, .14);
  border-radius: 4px;
  color: var(--wc-white);
  white-space: nowrap;
}

/* WC card — refreshed card pattern with metalwork accent.
   Coexists with Bootstrap .card; use .wc-card for design-driven surfaces. */
.wc-card {
  background: rgba(0, 17, 46, .8);
  border: 1px solid rgba(245, 241, 232, .08);
  border-radius: 8px;
  padding: 1rem;
  transition: border-color var(--transition);
}
.wc-card:hover {
  border-color: rgba(242, 211, 107, .25);
}
.wc-card-flush {
  padding: 0;
}
```

- [ ] **Step 2: Visual smoke — verify the classes are reachable**

Run the dev server and load any WC page (e.g., `/worldcup/leaderboard`) in a browser:

```bash
FLASK_APP=app.py venv/bin/flask run
```

Then in the browser DevTools console:

```js
const probe = document.createElement('span');
probe.className = 'wc-eyebrow';
document.body.appendChild(probe);
console.log(getComputedStyle(probe).fontFamily);  // should include "Teko"
console.log(getComputedStyle(probe).textTransform); // should be "uppercase"
probe.remove();
```

Expected: console logs include "Teko" and "uppercase". If style is not applied, check that `body.game-worldcup` is on the body element and the new block is in the file.

- [ ] **Step 3: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: pyright 0 errors; pytest all green (150 tests).

- [ ] **Step 4: Commit**

```bash
git add static/css/style.css
git commit -m "feat(ccc-wc): add cross-cutting .wc-* utility CSS classes

Adds 6 utility classes (wc-eyebrow, wc-numeral, wc-hero-grad,
wc-tier-dot, wc-multiplier-chip, wc-card) consuming Spec A tokens.
No new tokens. Foundation for Plans 2/3/4 to inherit.

Refs Spec C Plan 1."
```

---

## Foundation: sub-nav rewrite

### Task 2: Replace the WC sub-nav block in `base.html`

**Files:**
- Modify: `templates/base.html` lines ~99–130 (the `{% if request.blueprint == 'worldcup' %}` branch)

- [ ] **Step 1: Locate the existing block**

```bash
grep -n "request.blueprint == 'worldcup'\|subnav-worldcup" templates/base.html
```

Expected: shows the start of the WC sub-nav block at line ~100.

- [ ] **Step 2: Replace the block with the new pill set**

Replace the entire `{% if request.blueprint == 'worldcup' %}` … `{% elif request.blueprint == 'golf' %}` block (the WC branch only — leave Golf and CFB untouched) with:

```jinja
{% if request.blueprint == 'worldcup' %}
<div class="game-subnav subnav-worldcup">
    <div class="container">
        <a class="subnav-game-label d-none d-sm-inline-flex" href="{{ url_for('worldcup.index') }}">
            ⚽ <span class="subnav-label-text">WC 2026</span>
        </a>
        <div class="subnav-pills">
            <a class="subnav-pill {% if request.endpoint == 'worldcup.index' %}active{% endif %}"
               href="{{ url_for('worldcup.index') }}">Hub</a>
            {% if current_user.is_authenticated %}
            <a class="subnav-pill {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
               href="{{ url_for('worldcup.picks') }}">Roster</a>
            {% endif %}
            <a class="subnav-pill {% if request.endpoint in ['worldcup.leaderboard', 'worldcup.player_detail', 'worldcup.team_detail'] %}active{% endif %}"
               href="{{ url_for('worldcup.leaderboard') }}">Board</a>
            <a class="subnav-pill {% if request.endpoint == 'worldcup.schedule' %}active{% endif %}"
               href="{{ url_for('worldcup.schedule') }}">Schedule</a>
            <a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
               href="{{ url_for('worldcup.stats') }}">Stats</a>
            <a class="subnav-pill {% if request.endpoint == 'worldcup.rules' %}active{% endif %}"
               href="{{ url_for('worldcup.rules') }}">Rules</a>
            {% if worldcup_enrollment and worldcup_enrollment.is_admin %}
            <a class="subnav-pill {% if request.endpoint and 'admin' in request.endpoint %}active{% endif %}"
               href="{{ url_for('worldcup.admin_dashboard') }}">
                <i class="bi bi-gear-fill"></i> Admin</a>
            {% endif %}
        </div>
    </div>
</div>
```

Notes for the editor:
- The `worldcup.team_detail` endpoint **does not exist yet** (Plan 2 introduces it). Including it in the active-state list is forward-compatible — Jinja's `in [...]` test silently returns false for an unmatched endpoint name string. Verify by loading any WC page in Plan 1 and confirming no template render error.
- The `d-none d-sm-inline-flex` Bootstrap utilities hide the `⚽ WC 2026` label on viewports under 576px (Bootstrap's `sm` breakpoint).
- Pill order: Hub (always) · Roster (auth only) · Board · Schedule · Stats · Rules · Admin (admin only). Groups is intentionally absent — see Plan 1 Task 4 step 3 for the inline group-letter affordances added elsewhere.

- [ ] **Step 3: Verify rendering on every WC route**

Start the dev server and visit each route in turn, confirming the sub-nav renders with the active pill highlighted:

```bash
FLASK_APP=app.py venv/bin/flask run
```

Visit (in any logged-in browser session as a regular user — no admin needed yet):
- `/worldcup/` → Hub active
- `/worldcup/picks` → Roster active (if auth)
- `/worldcup/leaderboard` → Board active
- `/worldcup/schedule` → Schedule active
- `/worldcup/stats` → Stats active
- `/worldcup/rules` → Rules active

Expected: every page renders; the correct pill is highlighted; no Jinja `BuildError` from the forward-compatible `worldcup.team_detail` reference.

- [ ] **Step 4: Commit**

```bash
git add templates/base.html
git commit -m "feat(ccc-wc): rewrite WC sub-nav (Hub · Roster · Board · Schedule · Stats · Rules)

Demotes Groups from primary nav (will surface from Hub tiles + inline
group-letter badge links in subsequent tasks). Renames Dashboard→Hub,
My Picks→Roster, Leaderboard→Board, Stats Hub→Stats. Forward-references
worldcup.team_detail endpoint introduced by Plan 2 — silently inert
until then.

Refs Spec C Plan 1 D5."
```

### Task 3: Mobile compaction media query

**Files:**
- Modify: `static/css/style.css` — append a media query after the `.subnav-pill` definitions (search for `.subnav-pill {` to locate)

- [ ] **Step 1: Locate insertion point**

```bash
grep -n "^\.subnav-pill" static/css/style.css
```

Expected: shows `.subnav-pill {`, `.subnav-pill:hover {`, `.subnav-pill.active {` rules around the same line range. Insertion point is **after** the last of these (`.subnav-pill.active`).

- [ ] **Step 2: Append the media query**

Add immediately after the last `.subnav-pill` rule:

```css
/* Spec C Plan 1 — mobile compactions: fit 6 pills on 375px without scroll */
@media (max-width: 575.98px) {
  .subnav-pills { gap: .25rem; }
  .subnav-pill {
    font-size: .72rem;
    padding: .28rem .55rem;
    letter-spacing: .04em;
  }
}
```

- [ ] **Step 3: Verify on a 375px viewport**

In Chrome DevTools, toggle device toolbar → set viewport to 375×667 (iPhone SE). Visit `/worldcup/` (or any WC page).

Expected: all 6 pills (Hub · Roster · Board · Schedule · Stats · Rules) fit on a single row without horizontal scroll. The `⚽ WC 2026` label is hidden. Pill text remains readable.

If the row scrolls or pills wrap to a second line: check that the `d-none d-sm-inline-flex` is on the `subnav-game-label` from Task 2; check that the media query is below 576px and uses `max-width: 575.98px` (not `<= 575px`).

- [ ] **Step 4: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add static/css/style.css
git commit -m "feat(ccc-wc): mobile sub-nav compactions for narrow viewports

Tightens pill padding/font/gap below 576px so 6 pills fit on a 375px
screen without horizontal scroll.

Refs Spec C Plan 1 D5."
```

---

## picks.html — three states

`picks.html` (325 lines today) handles three render paths via existing Jinja conditionals:

1. `show_edit_form == true` → edit form (wc-pick + wc-tiebreak mocks)
2. Picks submitted, pre-deadline, not editing → sealed view (wc-confirmed + wc-roster Pre-Lock mocks)
3. Post-deadline → read-only view with drill-down accordion (wc-roster Live mock)

Each task below restyles one render path. Counter logic, tier-cap enforcement JS, and accordion drill-down behavior are **not changed** — only markup + classes + copy.

### Task 4: picks.html — edit form state (`show_edit_form`)

**Files:**
- Modify: `games/worldcup/templates/worldcup/picks.html` — the `{% else %}` branch starting at "PRE-DEADLINE -- Pick Form" (around line 121)

- [ ] **Step 1: Re-read picks.html to ground the changes**

```bash
sed -n '120,220p' games/worldcup/templates/worldcup/picks.html
```

Expected: shows the form branch with `<form method="POST" id="pickForm">`, the 5-tier loop, the sticky sidebar with pick summary and tiebreak input, and the mobile sticky bar.

- [ ] **Step 2: Update the H1 in the page hero**

Find at line ~5–20 the `<div class="page-hero">` block. Update the H1 to use the new copy and apply `.wc-hero-grad`:

```jinja
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow wc-eyebrow-red">Roster · 9 nations</span>
    <h1>{% if deadline_passed %}The Oath is sealed{% elif show_edit_form %}Submit Your Picks{% else %}Sealed. Still amendable.{% endif %}</h1>
    <p class="lead mb-0">
      {% if deadline_passed %}
        Picks are locked. The tournament is underway.
      {% else %}
        Deadline: <strong>{{ deadline_ct.strftime('%b %-d, %Y at %-I:%M %p CT') }}</strong>
      {% endif %}
    </p>
    <a href="{{ url_for('worldcup.rules') }}" class="text-white-50 small text-decoration-none mt-2 d-inline-block">
      <i class="bi bi-info-circle me-1"></i>View Scoring Rules
    </a>
  </div>
</div>
```

- [ ] **Step 3: Restyle tier-card headers**

Find the `{% for tier_num in range(1, 6) %}` loop (around line ~130). Replace the existing `<div class="tier-card-header">` block with:

```jinja
<div class="tier-card-header">
  <div>
    <span class="wc-eyebrow wc-eyebrow-red">Tier {{ tier_num }} · {{ tier['name'] }}</span>
    <h3 class="d-flex align-items-center gap-2 mb-0">
      <span class="wc-tier-dot wc-tier-dot-{{ tier_num }}"></span>
      {{ tier['name'] }}
      <span class="wc-multiplier-chip">×{{ tier['multiplier'] }}</span>
    </h3>
  </div>
  <span class="tier-counter wc-numeral" id="counter-{{ tier_num }}">
    0/{{ tier['picks'] }} selected
  </span>
</div>
```

Notes:
- Existing `tier-counter` ID and class preserved (JS hooks at line ~262-267 in `_pick_accordion_script.html` and the inline script at lines ~232-318 of picks.html depend on `#counter-{n}`).
- `wc-numeral` is additive — does not remove `tier-counter`.

- [ ] **Step 4: Restyle the country/team cards**

Find `<div class="wc-team-card …">` (around line ~146). The existing class name is preserved (JS hooks `.wc-team-card[data-tier="..."]` at line ~232 depend on it). Update the content layout flag-forward:

```jinja
<div class="wc-team-card {% if team.id in selected_team_ids %}selected{% endif %}"
     data-team-id="{{ team.id }}"
     data-tier="{{ tier_num }}"
     data-flag="{{ team.flag_emoji }}"
     data-group="{{ team.group_letter }}"
     onclick="toggleTeam(this)">
  <input type="checkbox" name="tier_{{ tier_num }}" value="{{ team.id }}"
         class="d-none team-checkbox"
         {% if team.id in selected_team_ids %}checked{% endif %}>
  <span class="team-flag fs-4">{{ team.flag_emoji }}</span>
  <span class="team-name">{{ team.display_name }}</span>
  <span class="team-meta">
    <a href="{{ url_for('worldcup.groups') }}#group-{{ team.group_letter }}"
       class="team-group-pill"
       onclick="event.stopPropagation();">Group {{ team.group_letter }}</a>
  </span>
</div>
```

Notes:
- `event.stopPropagation()` prevents the group-pill click from triggering the parent `toggleTeam(this)` checkbox toggle.
- The `#group-{{ team.group_letter }}` anchor is added in Task 9 — Plan 1 ships the link forward-compatibly (it'll deep-link to the page top until Task 9 lands the anchors, then deep-link to the section).
- `.team-flag`, `.team-group-pill` are new descendant classes; add them to the existing `.wc-team-card` rules in `style.css` if they're not already styled (search `.wc-team-card` in style.css). If unstyled, add minimal supporting CSS in the same `style.css` section as Task 1's additions:

```css
/* picks.html team card descendants */
.wc-team-card .team-flag { margin-right: .4rem; }
.wc-team-card .team-group-pill {
  display: inline-block;
  font-family: 'Teko', sans-serif;
  font-size: .68rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  padding: .1rem .35rem;
  background: rgba(245, 241, 232, .06);
  border-radius: 3px;
  color: var(--bone-mute);
  text-decoration: none;
}
.wc-team-card .team-group-pill:hover {
  color: var(--wc-white);
  background: rgba(245, 241, 232, .12);
}
```

- [ ] **Step 5: Restyle the pick summary sidebar**

Find `<div class="pick-summary …" id="pickSummary">` (around line ~171). Update:

```jinja
<div class="pick-summary animate-in stagger-2" id="pickSummary">
  <span class="wc-eyebrow">Your selections</span>
  <h4 class="mb-3"><i class="bi bi-list-check me-2"></i>Pick Summary</h4>
  <ul class="pick-summary-list" id="summaryList">
    <li class="text-muted" id="summaryEmpty">Select your 9 teams...</li>
  </ul>
  <div class="mt-3 text-end fw-bold wc-numeral" style="font-size:1.1rem;" id="summaryCount">
    0/9 picks
  </div>
</div>
```

ID `pickSummary`, list ID `summaryList`, count ID `summaryCount` preserved (JS hooks at line ~270-291 depend on them).

- [ ] **Step 6: Restyle the tiebreak input card**

Find the card containing `<label for="usa_goals_guess">` (around line ~181). Replace its body with:

```jinja
<div class="card border-0 shadow-sm mt-3 wc-card wc-card-flush">
  <div class="card-body p-3">
    <span class="wc-eyebrow wc-eyebrow-red">The Tiebreak</span>
    <label for="usa_goals_guess" class="form-label fw-medium mt-1">
      <i class="bi bi-bullseye me-2"></i>USA Goals — Tournament Total
    </label>
    <p class="text-muted small mb-2">
      How many total goals will the USA score in the tournament?
    </p>
    <input type="number" class="form-control wc-numeral" id="usa_goals_guess" name="usa_goals_guess"
           min="0" step="1" placeholder="e.g. 7"
           value="{{ usa_goals_guess if usa_goals_guess is not none and usa_goals_guess != '' else '' }}"
           oninput="updateSubmitState()">
  </div>
</div>
```

ID `usa_goals_guess` preserved (form-name dependency + JS hook at line ~304).

- [ ] **Step 7: Update the submit CTA copy + styling**

Find `<button type="submit" class="btn btn-game btn-lg w-100 mt-3 …" id="submitBtn"` (around line ~196). Update copy to "Seal the Oath":

```jinja
<button type="submit" class="btn btn-game btn-lg w-100 mt-3 pick-form-sidebar-desktop" id="submitBtn" disabled>
  <i class="bi bi-check-lg me-2"></i>Seal the Oath
</button>
<p class="text-muted small text-center mt-2 pick-form-sidebar-desktop">
  You can amend until the deadline.
</p>
```

ID `submitBtn` preserved (JS hook at line ~295).

- [ ] **Step 8: Update the mobile sticky bar copy**

Find `<div class="wc-mobile-sticky-bar" id="mobileStickyBar">` (around line ~208). Update the inner button copy:

```jinja
<div class="wc-mobile-sticky-bar" id="mobileStickyBar">
  <div class="pick-count">
    <span class="count-num wc-numeral" id="mobilePickCount">0</span>/9 picks
  </div>
  <button type="submit" class="btn btn-game" id="mobileSubmitBtn" disabled>
    <i class="bi bi-check-lg me-1"></i>Seal
  </button>
</div>
```

IDs `mobilePickCount`, `mobileSubmitBtn` preserved (JS hooks at line ~296-298, 313).

- [ ] **Step 9: Visual smoke**

Start the dev server. Log in as a user who has not submitted picks (or use admin to clear picks via `/worldcup/admin/...` if needed). Visit `/worldcup/picks` in edit mode (auto-redirects to edit form if no picks). Verify on both mobile (375px) and desktop:
- Hero displays "Submit Your Picks" + new eyebrow + new gradient
- Each tier card shows tier dot, name, multiplier chip, and counter
- Country cards display flag prominently and a Group X pill in the meta
- Click a country card → it toggles selected state (JS still works)
- Click the Group X pill → navigates to `/worldcup/groups#group-X` (no error; anchor lands on page until Task 9)
- Sidebar pick summary updates as you select countries
- Tiebreak input accepts a number; "Seal the Oath" enables when 9 picks + valid tiebreak
- On mobile, sticky bottom bar shows pick count and "Seal" button

- [ ] **Step 10: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 11: Commit**

```bash
git add games/worldcup/templates/worldcup/picks.html static/css/style.css
git commit -m "feat(ccc-wc): reskin picks.html edit form state

Maps wc-pick + wc-tiebreak design mocks: hero with red eyebrow + new
gradient, tier cards with wc-tier-dot + wc-multiplier-chip + tier name
eyebrow, flag-forward country cards with inline group-pill links,
pick summary with eyebrow, tiebreak as 'The Tiebreak' card, CTA
'Seal the Oath' / mobile 'Seal'.

All JS DOM hooks preserved (counter-N, pickSummary, summaryList,
summaryCount, usa_goals_guess, submitBtn, mobileSubmitBtn,
mobilePickCount). No behavioral changes.

Refs Spec C Plan 1."
```

### Task 5: picks.html — sealed pre-deadline state

The sealed-but-amendable view renders when picks are submitted but the deadline has not passed and `show_edit_form` is false. In production today the same `{% if existing_picks %}` block (lines ~31–115) handles both sealed-pre-deadline and post-deadline reads. We split visual treatment by branching on `deadline_passed`.

**Files:**
- Modify: `games/worldcup/templates/worldcup/picks.html` lines ~24–118 (the read-only `{% if deadline_passed or (not show_edit_form and has_picks) %}` block — this same block also covers Task 6's post-deadline state)

- [ ] **Step 1: Restyle the desktop card header**

Find at line ~33 `<div class="card border-0 shadow-sm mb-4 animate-in player-picks-desktop">`. Update its header:

```jinja
<div class="card border-0 shadow-sm mb-4 animate-in player-picks-desktop wc-card wc-card-flush">
  <div class="card-header d-flex align-items-center justify-content-between">
    <div>
      <span class="wc-eyebrow {% if deadline_passed %}wc-eyebrow-red{% endif %}">
        {% if deadline_passed %}The Oath is sealed{% else %}Sealed · still amendable{% endif %}
      </span>
      <h4 class="mb-0 mt-1"><i class="bi bi-check2-square me-2"></i>Your 9 Picks</h4>
    </div>
    <span class="fw-bold wc-numeral" style="font-size:1.3rem;">
      Total: {{ "%.1f"|format(enrollment.total_score) }} pts
    </span>
  </div>
  <div class="card-body p-0">
    <!-- table block stays as-is for now; restyling lives in Task 7 (_pick_row.html) -->
    <div class="table-responsive">
      <table class="table table-worldcup mb-0">
        <thead>
          <tr>
            <th>Team</th>
            <th>Tier</th>
            <th class="text-center">Multiplier</th>
            <th class="text-end">Base</th>
            <th class="text-end">Points</th>
          </tr>
        </thead>
        <tbody>
          {% for pick in existing_picks %}
            {% with events = events_by_pick.get(pick.id, []) %}
              {% include 'worldcup/_pick_row.html' %}
            {% endwith %}
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Restyle the mobile card header**

Find at line ~65 `<div class="player-picks-mobile mb-4 animate-in">`. Update its header:

```jinja
<div class="player-picks-mobile mb-4 animate-in">
  <div class="card-header d-flex align-items-center justify-content-between border-0 px-1 mb-2">
    <div>
      <span class="wc-eyebrow {% if deadline_passed %}wc-eyebrow-red{% endif %}">
        {% if deadline_passed %}The Oath is sealed{% else %}Sealed · still amendable{% endif %}
      </span>
      <h4 class="mb-0 mt-1" style="font-family:'Teko',sans-serif; font-weight:600; text-transform:uppercase; letter-spacing:.04em; font-size:1.1rem;">
        <i class="bi bi-check2-square me-2"></i>Your 9 Picks
      </h4>
    </div>
    <span class="fw-bold wc-numeral" style="font-size:1.2rem;">
      {{ "%.1f"|format(enrollment.total_score) }} pts
    </span>
  </div>
  <!-- mobile pick cards: keep existing markup; styling refresh comes in Task 7 -->
  <div class="d-flex flex-column gap-2">
    {% for pick in existing_picks %}
    <div class="player-pick-card">
      <div>
        <span class="tier-badge tier-badge-{{ pick.tier }} me-1" style="font-size:.65rem; vertical-align:middle;">T{{ pick.tier }}</span>
        <span class="pick-team">{{ pick.team.flag_emoji }} {{ pick.team.display_name }} <small>Grp {{ pick.team.group_letter }}</small></span>
      </div>
      <div class="pick-points wc-numeral">
        {{ "%.1f"|format(pick.multiplied_points) }}
        <small>&times;{{ pick.team.multiplier }}</small>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
```

- [ ] **Step 3: Update the tiebreak summary card**

Find at line ~90 `{% if enrollment.usa_goals_guess is not none %}`. Update:

```jinja
{% if enrollment.usa_goals_guess is not none %}
<div class="card border-0 shadow-sm animate-in stagger-1 wc-card wc-card-flush">
  <div class="card-body p-3 d-flex align-items-center justify-content-between">
    <div>
      <span class="wc-eyebrow">The Tiebreak</span>
      <div class="text-muted mt-1"><i class="bi bi-bullseye me-2"></i>USA — Tournament total goals</div>
    </div>
    <span class="fw-bold wc-numeral" style="font-size:1.4rem;">{{ enrollment.usa_goals_guess }}</span>
  </div>
</div>
{% endif %}
```

- [ ] **Step 4: Update the "Edit My Picks" CTA copy**

Find at line ~99 `{% if not deadline_passed %}` block. Update the link:

```jinja
{% if not deadline_passed %}
<div class="text-center mt-4 animate-in stagger-2">
  <a href="{{ url_for('worldcup.picks', edit=1) }}" class="btn btn-game btn-lg px-5">
    <i class="bi bi-pencil-square me-2"></i>Amend the Oath
  </a>
  <p class="text-muted small mt-2 mb-0">
    You can amend your picks until {{ deadline_ct.strftime('%b %-d at %-I:%M %p CT') }}.
  </p>
</div>
{% endif %}
```

- [ ] **Step 5: Visual smoke (sealed pre-deadline)**

Log in as a user who has submitted picks but the deadline has not passed. Visit `/worldcup/picks`. Verify on mobile + desktop:
- Hero shows "Sealed. Still amendable." with countdown
- Card header shows "Sealed · still amendable" eyebrow + "Your 9 Picks"
- Total points shown in numeral typography
- Tiebreak card shows "The Tiebreak" eyebrow
- "Amend the Oath" CTA links back to `/worldcup/picks?edit=1`

(If you cannot reproduce sealed pre-deadline locally because the deadline has already passed in your dev DB, set `WC_FAKE_NOW` to a pre-deadline ISO time and `ENVIRONMENT=development`:

```bash
WC_FAKE_NOW=2026-06-10T00:00:00+00:00 FLASK_APP=app.py venv/bin/flask run
```

Per CLAUDE.md, the `now_utc()` seam honors `WC_FAKE_NOW` in dev/testing.)

- [ ] **Step 6: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/templates/worldcup/picks.html
git commit -m "feat(ccc-wc): reskin picks.html sealed pre-deadline state

Maps wc-confirmed + wc-roster Pre-Lock mocks. Card header gets
red 'Sealed · still amendable' eyebrow; total score uses wc-numeral;
tiebreak summary card surfaces 'The Tiebreak' eyebrow; CTA copy
'Edit My Picks' → 'Amend the Oath'. Existing _pick_row.html pickup
unchanged (restyled in Task 7).

Refs Spec C Plan 1."
```

### Task 6: picks.html — post-deadline read-only state

Most of the post-deadline visual treatment is shared with Task 5 (the same `{% if existing_picks %}` block). This task focuses on copy that's specific to post-deadline (already handled inline via `{% if deadline_passed %}` branches in Task 5's edits) plus an explicit smoke pass on the drill-down accordion.

**Files:**
- Verify: `games/worldcup/templates/worldcup/picks.html` post-deadline branches (already updated in Task 5)
- Verify: `games/worldcup/templates/worldcup/_pick_accordion_script.html` (no changes)

- [ ] **Step 1: Visual smoke (post-deadline)**

Set the fake-now to post-deadline (or use a real post-deadline DB):

```bash
WC_FAKE_NOW=2026-06-15T00:00:00+00:00 FLASK_APP=app.py venv/bin/flask run
```

Visit `/worldcup/picks` as a user who submitted picks. Verify:
- Hero shows "The Oath is sealed" (per Task 4 step 2's H1 logic)
- Card header eyebrow shows red "The Oath is sealed"
- Each pick row shows tier, multiplier, points (still using legacy styling — Task 7 refreshes the partial)
- Click any pick row → drill-down accordion expands and shows score events
- Click again → accordion collapses
- Tiebreak summary card displays USA goals number
- No "Amend the Oath" CTA (correct — post-deadline)

If accordion drill-down does **not** expand: stop. The likely cause is a broken DOM hook from Task 4 or Task 5. Run:

```bash
grep -n "data-pick-id\|toggleAccordion\|wc-team-card.*selected" games/worldcup/templates/worldcup/_pick_accordion_script.html games/worldcup/templates/worldcup/_pick_row.html games/worldcup/templates/worldcup/picks.html
```

…and reconcile against the JS hooks in `_pick_accordion_script.html`. The fix is to restore any class/ID name that was inadvertently changed.

- [ ] **Step 2: No code commit needed for this task** (verification-only). Proceed to Task 7.

### Task 7: `_pick_row.html` partial reskin

**Files:**
- Modify: `games/worldcup/templates/worldcup/_pick_row.html` (46 lines)

- [ ] **Step 1: Read the current partial**

```bash
cat games/worldcup/templates/worldcup/_pick_row.html
```

- [ ] **Step 2: Replace the entire file**

This partial is rendered inside a `<table>` (post-deadline desktop view in `picks.html` and `player_detail.html`). It's used for both your-own-roster and a rival's roster. The variables `pick`, `events`, and any others required come from the calling template's `{% with events = events_by_pick.get(pick.id, []) %}` context.

Replace the file contents with:

```jinja
{# Pick row — desktop table row + drill-down accordion details.
   Used by picks.html (post-deadline) and player_detail.html.
   Rendering context: caller wraps with {% with events = events_by_pick.get(pick.id, []) %} #}

<tr class="pick-row" data-pick-id="{{ pick.id }}" {% if events %}role="button" tabindex="0" aria-expanded="false" aria-controls="pick-events-{{ pick.id }}"{% endif %}>
  <td class="pick-team-cell">
    <span class="me-2 fs-5">{{ pick.team.flag_emoji }}</span>
    <span class="fw-medium">{{ pick.team.display_name }}</span>
    <small class="text-muted ms-1">Grp {{ pick.team.group_letter }}</small>
  </td>
  <td>
    <span class="wc-tier-dot wc-tier-dot-{{ pick.tier }}"></span>
    <span class="wc-eyebrow">T{{ pick.tier }}</span>
  </td>
  <td class="text-center">
    <span class="wc-multiplier-chip">×{{ pick.team.multiplier }}</span>
  </td>
  <td class="text-end wc-numeral">{{ "%.1f"|format(pick.base_points) }}</td>
  <td class="text-end wc-numeral fw-bold">
    {{ "%.1f"|format(pick.multiplied_points) }}
    {% if events %}<i class="bi bi-chevron-down ms-1 text-muted small pick-row-chevron"></i>{% endif %}
  </td>
</tr>
{% if events %}
<tr class="pick-events-row" id="pick-events-{{ pick.id }}" hidden>
  <td colspan="5" class="pick-events-cell p-0">
    <div class="pick-events-inner">
      <span class="wc-eyebrow d-block mb-2">Score events</span>
      <ul class="pick-events-list list-unstyled m-0">
        {% for event in events %}
        <li class="pick-event-item">
          <span class="pick-event-stage wc-eyebrow">{{ event.stage_label or event.stage }}</span>
          <span class="pick-event-desc">{{ event.description }}</span>
          <span class="pick-event-pts wc-numeral {% if event.points >= 0 %}text-success{% else %}text-danger{% endif %}">
            {{ "+%.1f"|format(event.points) if event.points >= 0 else "%.1f"|format(event.points) }}
          </span>
        </li>
        {% endfor %}
      </ul>
    </div>
  </td>
</tr>
{% endif %}
```

Notes for the editor:
- `data-pick-id`, `aria-controls="pick-events-{{ pick.id }}"`, and the row IDs are preserved exactly so `_pick_accordion_script.html` continues to work.
- `event.stage_label` is referenced as a fallback to `event.stage` — this works whether `ScoreEvent` exposes a `stage_label` property (added later) or only the raw `stage` string. Verify by reading the dataclass:

```bash
grep -nA 12 "^class ScoreEvent" games/worldcup/services/scoring.py
```

If `ScoreEvent` does not have `stage_label`, leave the partial's fallback expression as-is — Jinja's `or` short-circuits to `event.stage`.

- The chevron icon (`pick-row-chevron`) is purely visual; if `_pick_accordion_script.html` rotates a chevron on expand, find that hook and update its selector to `.pick-row-chevron` — otherwise omit the chevron CSS rotation.

- [ ] **Step 3: Add minimal supporting CSS for the partial**

Add to the same `style.css` section as Task 1:

```css
/* picks.html / player_detail.html — pick row + drill-down accordion */
.pick-row {
  cursor: pointer;
}
.pick-row:hover {
  background: rgba(245, 241, 232, .03);
}
.pick-row.expanded .pick-row-chevron {
  transform: rotate(180deg);
}
.pick-row-chevron {
  transition: transform var(--transition);
}
.pick-events-cell {
  background: rgba(0, 17, 46, .6);
  border-bottom: 1px solid rgba(245, 241, 232, .05);
}
.pick-events-inner {
  padding: .75rem 1rem;
}
.pick-event-item {
  display: grid;
  grid-template-columns: 90px 1fr auto;
  gap: .75rem;
  align-items: baseline;
  padding: .25rem 0;
  border-bottom: 1px dashed rgba(245, 241, 232, .04);
}
.pick-event-item:last-child { border-bottom: none; }
.pick-event-stage { color: var(--bone-mute); }
.pick-event-desc { color: var(--wc-white); font-size: .9rem; }
.pick-event-pts { font-size: 1rem; }
```

- [ ] **Step 4: Verify accordion behavior preserved**

Visit `/worldcup/picks` post-deadline (use `WC_FAKE_NOW` if needed). Click a pick row. Verify:
- The accordion `<tr id="pick-events-{n}">` toggles between `hidden` and visible
- Chevron rotates (if `_pick_accordion_script.html` rotates it via the `.expanded` class on the parent row)
- Score events render with stage eyebrow, description, points (color-coded green/red)

- [ ] **Step 5: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/templates/worldcup/_pick_row.html static/css/style.css
git commit -m "feat(ccc-wc): reskin _pick_row.html partial + drill-down accordion

Tier cell uses wc-tier-dot + tier eyebrow; multiplier cell uses
wc-multiplier-chip; points cells use wc-numeral. Drill-down accordion
gets eyebrow labels, three-column event-item grid, and bone-mute
descriptions over a navy backdrop. All DOM hooks (data-pick-id,
aria-controls, pick-events-{id}) preserved.

Refs Spec C Plan 1."
```

---

## Light chrome pass

These three pages have no design-bundle mocks — the goal is visual *coherence* with the rest of the WC reskin (page-hero gradient, eyebrow labels, numeral typography, .wc-card pattern), not bespoke design. Keep changes shallow. No copy changes.

### Task 8: `schedule.html` light chrome pass

**Files:**
- Modify: `games/worldcup/templates/worldcup/schedule.html` (108 lines)

- [ ] **Step 1: Read current schedule.html**

```bash
cat games/worldcup/templates/worldcup/schedule.html
```

- [ ] **Step 2: Apply chrome refresh**

Update the page hero block (top of file) to use `.wc-hero-grad` and add an eyebrow:

```jinja
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow">Tournament fixtures</span>
    <h1>Schedule</h1>
    <p class="lead mb-0">2026 FIFA World Cup &mdash; All 104 matches</p>
  </div>
</div>
```

For each `<div class="card …">` containing match-day groupings, add `.wc-card`:

```bash
# Locate card occurrences in schedule.html
grep -n "card border-0\|class=\"card" games/worldcup/templates/worldcup/schedule.html
```

For each card, add `wc-card` to its class list (preserving Bootstrap classes already present — additive only):

```jinja
<div class="card border-0 shadow-sm wc-card wc-card-flush">
  <!-- existing body unchanged -->
</div>
```

For score / match-result numerals (any `<span>` or `<strong>` that displays a score like "2–1"), add `wc-numeral`:

```jinja
<span class="match-score wc-numeral">{{ m.home_score }}–{{ m.away_score }}</span>
```

(Search for `match-score` in the file; add `wc-numeral` to those elements.)

- [ ] **Step 3: Visual smoke**

Visit `/worldcup/schedule`. Verify the hero gradient renders, cards have the new border on hover, and numerals use Teko.

- [ ] **Step 4: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/templates/worldcup/schedule.html
git commit -m "feat(ccc-wc): light chrome pass on schedule.html

Hero gets wc-hero-grad + eyebrow; cards adopt .wc-card pattern; match
scores use .wc-numeral. No structural or copy changes. No design
bundle mock for this page; coherence-only pass.

Refs Spec C Plan 1."
```

### Task 9: `groups.html` light chrome pass + anchor IDs

**Files:**
- Modify: `games/worldcup/templates/worldcup/groups.html` (57 lines)

- [ ] **Step 1: Read current groups.html**

```bash
cat games/worldcup/templates/worldcup/groups.html
```

- [ ] **Step 2: Apply chrome refresh + add anchors**

Update the page hero (top of file):

```jinja
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow">Group standings</span>
    <h1>Groups</h1>
    <p class="lead mb-0">2026 FIFA World Cup &mdash; 12 groups, 4 nations each</p>
  </div>
</div>
```

For each group section, add an anchor ID using the group letter. Find the loop that renders groups (likely `{% for group in groups %}` or similar):

```bash
grep -n "group_letter\|for group\|<section\|<div.*group" games/worldcup/templates/worldcup/groups.html
```

Wrap each group's container with an anchor section:

```jinja
{% for group in groups %}
<section id="group-{{ group.letter }}" class="mb-4 wc-card wc-card-flush">
  <div class="p-3 border-bottom">
    <span class="wc-eyebrow">Group</span>
    <h3 class="mb-0"><span class="wc-numeral">{{ group.letter }}</span></h3>
  </div>
  <!-- existing inner table / standings markup unchanged -->
  <div class="table-responsive">
    <table class="table table-worldcup mb-0">
      <!-- existing thead + tbody -->
    </table>
  </div>
</section>
{% endfor %}
```

If the production template doesn't iterate via `groups` (the variable might be named differently), match its existing variable shape. The key change is wrapping each group section in `<section id="group-{LETTER}">` so deep-links from elsewhere (`#group-A` etc.) scroll the correct group into view.

For score/numeric cells inside the standings table (Pts, GF, GA, GD), add `wc-numeral`.

- [ ] **Step 3: Verify deep-link works**

Visit `/worldcup/groups#group-A` directly. Browser should scroll Group A into view (or at least anchor-jump to it). Try `#group-D`, `#group-L` etc.

- [ ] **Step 4: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/templates/worldcup/groups.html
git commit -m "feat(ccc-wc): light chrome pass on groups.html + anchor IDs

Hero gets wc-hero-grad + eyebrow; each group section wrapped in
<section id='group-{LETTER}'> for deep-link targeting from inline
group-letter pills (added in picks.html Task 4). Cards adopt .wc-card;
standings cells use .wc-numeral. No structural or copy changes.

Refs Spec C Plan 1."
```

### Task 10: `rules.html` light chrome pass

**Files:**
- Modify: `games/worldcup/templates/worldcup/rules.html` (266 lines)

- [ ] **Step 1: Apply chrome refresh**

Update the page hero:

```jinja
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow">Scoring reference</span>
    <h1>Rules</h1>
    <p class="lead mb-0">How the World Cup pool scores</p>
  </div>
</div>
```

Find each section header (likely `<h2>` or `<h3>`) and add a `.wc-eyebrow` line above it. Pattern:

```jinja
<section class="mb-4">
  <span class="wc-eyebrow wc-eyebrow-red">Tiers</span>
  <h2>Pick 9 nations across 5 tiers</h2>
  <!-- existing body content -->
</section>
```

For tier example pills (search `tier-badge-` in the file), add the new `.wc-tier-dot` pattern alongside (additive — keep existing tier-badge-{n} for backward compatibility):

```jinja
<li>
  <span class="wc-tier-dot wc-tier-dot-1"></span>
  <strong>Tier 1 — Favorites</strong> (×1.0): countries with the strongest qualifying form...
</li>
```

For multiplier examples (`×1.0`, `×7.0`), wrap in `.wc-multiplier-chip`:

```jinja
<span class="wc-multiplier-chip">×7.0</span>
```

For card containers (existing `<div class="card">` blocks), add `.wc-card`:

```jinja
<div class="card border-0 shadow-sm wc-card wc-card-flush">
  <!-- existing body unchanged -->
</div>
```

**Do not change copy.** Rules page text must stay verbatim — only add CSS classes around it.

- [ ] **Step 2: Visual smoke**

Visit `/worldcup/rules`. Verify hero gradient, section eyebrows, tier-dot examples render, multiplier chips display, no copy changes.

- [ ] **Step 3: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/templates/worldcup/rules.html
git commit -m "feat(ccc-wc): light chrome pass on rules.html

Hero gets wc-hero-grad + eyebrow; section headers gain wc-eyebrow lines;
tier examples surface .wc-tier-dot alongside existing .tier-badge-{n};
multiplier values wrap in .wc-multiplier-chip; cards adopt .wc-card.
No copy changes. Coherence-only pass.

Refs Spec C Plan 1."
```

---

## Final verification + PR

### Task 11: End-to-end verification + open PR

- [ ] **Step 1: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -v
```

Expected: all 150 tests pass (unchanged from baseline). Plan 1 introduced no test changes.

- [ ] **Step 2: Run pyright on the entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 3: Manual visual checklist**

Walk through each WC route in a browser at both 375px (mobile) and 1280px (desktop):

| Route | Verify |
|---|---|
| `/worldcup/` | Hub pill active in sub-nav; page renders (still on legacy index template — Plan 4 reskins this) |
| `/worldcup/picks` (no picks state) | Roster pill active; edit form renders with Task 4 changes |
| `/worldcup/picks` (sealed pre-deadline) | Roster pill active; sealed view renders with Task 5 changes; "Amend the Oath" CTA |
| `/worldcup/picks` (post-deadline) | Roster pill active; "The Oath is sealed" hero; accordion drill-down works (Task 6 verification) |
| `/worldcup/leaderboard` | Board pill active; page renders (Plan 3 reskins) |
| `/worldcup/player/<id>` | Board pill active (multi-endpoint match); page renders (Plan 2 reskins) |
| `/worldcup/schedule` | Schedule pill active; Task 8 hero gradient + cards |
| `/worldcup/groups` | Hub pill active (Groups absent from sub-nav by design); Task 9 hero + anchors |
| `/worldcup/groups#group-A` | Page scrolls Group A into view |
| `/worldcup/stats` | Stats pill active; page renders (Plan 3 reskins) |
| `/worldcup/rules` | Rules pill active; Task 10 hero + section eyebrows |
| Admin user only: `/worldcup/admin/...` | Admin pill active and visible |
| Anonymous user: any WC page | Roster + Admin pills hidden; other pills render |

Mobile-specific verification:
- 375px viewport: 6 pills (Hub · Roster · Board · Schedule · Stats · Rules) fit on one row without horizontal scroll. `⚽ WC 2026` label hidden.
- Each touched page renders cleanly with the new gradient hero.

- [ ] **Step 4: Push the branch**

```bash
git push -u origin redesign/ccc-worldcup-plan1
```

- [ ] **Step 5: Open the PR**

```bash
gh pr create --title "Spec C Plan 1 — WC picks flow + foundation" --body "$(cat <<'EOF'
## Summary

Lands the foundation for Spec C (CCC World Cup reskin):

- **Cross-cutting CSS**: 6 new `.wc-*` utility classes (`wc-eyebrow`, `wc-numeral`, `wc-hero-grad`, `wc-tier-dot`, `wc-multiplier-chip`, `wc-card`) consuming Spec A tokens. No new tokens.
- **Sub-nav rewrite** (Hub · Roster · Board · Schedule · Stats · Rules + Admin): mobile compactions hide the `⚽ WC 2026` label and tighten pills so all 6 fit on a 375px screen without scroll. Groups demoted from primary nav.
- **`picks.html` reskin** across all three states (edit form, sealed pre-deadline, post-deadline). All JS DOM hooks preserved.
- **`_pick_row.html` partial reskin** (used here and by Plan 2's `player_detail.html`).
- **Light chrome pass** on `schedule.html`, `groups.html` (with anchor IDs `#group-A`…), `rules.html`. Coherence-only — no design mocks for these pages, no copy changes.

Spec: `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md`

## Test plan

- [x] All 150 existing tests pass (no logic changes; pure visual reskin)
- [x] `pyright` clean on `games/worldcup/`
- [x] Manual visual checklist passed for every WC route at 375px and 1280px
- [x] Sub-nav active states correct on every WC endpoint (including multi-endpoint match for Board → leaderboard / player / team)
- [x] Mobile sub-nav fits on 375px without horizontal scroll
- [x] `picks.html` accordion drill-down still expands/collapses correctly (DOM hooks preserved)
- [x] `/worldcup/groups#group-A` deep-links work

@coderabbitai please review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. CodeRabbit will review automatically per the `@coderabbitai` mention.

- [ ] **Step 6: Wait for CodeRabbit's review and address any findings**

Wait until CodeRabbit's actual review comment lands (not the "processing" stub). Address any findings via additional commits on the same branch. Re-push.

- [ ] **Step 7: Once approved, merge**

After CodeRabbit's review is addressed and the PR is approved, merge via the GitHub UI (squash recommended — matches Spec B's pattern). After merge, Plan 2 / 3 / 4 plans can be written using writing-plans skill against the spec, branching from the freshly-merged main.

---

## Notes for the executing agent

- **Token preservation**: Plan 1 adds zero new tokens. If you find yourself wanting to add one to `tokens.css`, stop and re-read Spec C §5 — the constraint is hard.
- **DOM hook preservation**: Every `id="..."` and `class="..."` that JavaScript references must survive the reskin. The pattern is **additive** — add `.wc-numeral` / `.wc-card` etc. *alongside* existing classes, never replacing them.
- **Forward references**: Task 2's sub-nav references `worldcup.team_detail` (Plan 2) and Task 4's group-pill links reference `#group-{LETTER}` anchors (Task 9 in this plan). Both are forward-compatible — Jinja's `in [...]` test is silent for unmatched endpoint strings; HTML anchors silently fall through to the page top if missing.
- **Visual fidelity**: Per spec D8 (B), be strict-where-clear, interpretive-where-ambiguous. The bundle is mobile-only; desktop interpretations are your call as long as they preserve mobile-first reading order.
- **Schedule.html and groups.html structures**: I've assumed common patterns (loop over groups, etc.) — verify against the actual file before applying changes. The chrome-pass tasks (8, 9, 10) are deliberately less scripted than the `picks.html` tasks because the production templates have less constrained structure and the goal is coherence rather than mock fidelity.
