# Nav Sub-Nav Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the crowded single-row navbar with a two-layer nav: a clean platform bar (logo + game switcher + user) on top, and a dark contextual pill sub-nav strip below — themed per game — that only appears when inside a game blueprint.

**Architecture:** Pure HTML/CSS change in `templates/base.html` and `static/css/style.css`. No Python, no routes, no migrations. The sub-nav block renders via Jinja2 `{% if request.blueprint %}` conditionals already used throughout the file. Per-game theming uses a CSS custom property (`--subnav-accent` + `--subnav-accent-rgb`) set on a game-specific class, consumed by shared pill rules.

**Tech Stack:** Jinja2, Bootstrap 5.3, vanilla CSS custom properties (no JS required)

---

## Files Changed

| File | Change |
|---|---|
| `static/css/style.css` | Add `/* === GAME SUB-NAV === */` section after the existing Navbar section (after line 904). Add mobile override inside existing `@media (max-width: 768px)` block. |
| `templates/base.html` | Strip the `<ul class="navbar-nav me-auto">` down to game switcher links only (remove Home link, remove all `{% if blueprint %}` nav-item blocks). Add `.game-subnav` block immediately after `</nav>`. |

---

## Task 1: Add game sub-nav CSS

**Files:**
- Modify: `static/css/style.css` (after line 904, before `/* ── 7. Flash Messages`)

- [ ] **Step 1: Insert the sub-nav CSS block**

In `static/css/style.css`, find the line:
```
/* ── 7. Flash Messages / Alerts ─────────────────────────── */
```
Insert the following block **immediately before** that line:

```css
/* === GAME SUB-NAV === */
/* Contextual strip that appears below the platform bar when inside a game blueprint.
   Per-game palette is set via --subnav-accent and --subnav-accent-rgb on the
   game class; shared pill rules consume those variables. */

.game-subnav {
  padding: .42rem 0;
  border-bottom: 1px solid rgba(255,255,255,.07);
}

.game-subnav .container {
  display: flex;
  align-items: center;
  gap: .5rem;
}

/* Per-game palettes */
.subnav-worldcup { background: #00122e; --subnav-accent: #BF0A30; --subnav-accent-rgb: 191,10,48; }
.subnav-golf     { background: #001a0d; --subnav-accent: #b8993e; --subnav-accent-rgb: 184,153,62; }
.subnav-cfb      { background: #0a080f; --subnav-accent: #C5050C; --subnav-accent-rgb: 197,5,12; }

/* Game label — links back to game index */
.subnav-game-label {
  font-family: 'Teko', sans-serif;
  font-weight: 700;
  font-size: .88rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: rgba(255,255,255,.9);
  text-decoration: none;
  white-space: nowrap;
  padding-right: .9rem;
  margin-right: .3rem;
  border-right: 1px solid rgba(255,255,255,.14);
  transition: opacity var(--transition);
  flex-shrink: 0;
}
.subnav-game-label:hover { opacity: .7; color: #fff; }

/* Pill container — scrolls horizontally on mobile */
.subnav-pills {
  display: flex;
  gap: .4rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  flex-wrap: nowrap;
}
.subnav-pills::-webkit-scrollbar { display: none; }

/* Individual pill */
.subnav-pill {
  font-family: 'Teko', sans-serif;
  font-weight: 500;
  font-size: .78rem;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: rgba(255,255,255,.48);
  text-decoration: none;
  padding: .26rem .72rem;
  border-radius: 20px;
  border: 1px solid transparent;
  white-space: nowrap;
  transition: color var(--transition), border-color var(--transition), background var(--transition);
}
.subnav-pill:hover {
  color: rgba(255,255,255,.85);
  border-color: rgba(255,255,255,.2);
  text-decoration: none;
}
.subnav-pill.active {
  color: #fff;
  background: rgba(var(--subnav-accent-rgb), .18);
  border-color: var(--subnav-accent);
}

```

- [ ] **Step 2: Add mobile override for label text**

Find the existing `@media (max-width: 768px)` block (around line 1625). Add this rule inside it:

```css
  /* Sub-nav: hide label text on mobile — emoji stays visible */
  .subnav-label-text { display: none; }
```

- [ ] **Step 3: Run smoke test**

```bash
FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected output: `Smoke test OK`

- [ ] **Step 4: Commit**

```bash
git add static/css/style.css
git commit -m "feat: add game sub-nav CSS (per-game pill strip, mobile-friendly)"
```

---

## Task 2: Refactor the platform top bar in base.html

**Files:**
- Modify: `templates/base.html` (the `<ul class="navbar-nav me-auto">` block, lines 38–115)

This task cleans the top bar down to: logo · World Cup · Golf Pick 'Em · CFB Survivor · (user menu). The Home link is removed (the brand logo already links to `/`). The `nav-link-muted` class is dropped from Golf and CFB — they're active games now. All `{% if request.blueprint == '...' %}` blocks that injected game-specific links into the top bar are removed here (they move to the sub-nav in Task 3).

- [ ] **Step 1: Replace the `<ul class="navbar-nav me-auto">` block**

Find and replace the entire block from `<ul class="navbar-nav me-auto">` through its closing `</ul>` (currently lines 38–115 in `base.html`) with:

```html
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link {% if request.blueprint == 'worldcup' %}active{% endif %}"
                           href="{{ url_for('worldcup.index') }}">World Cup</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if request.blueprint == 'golf' %}active{% endif %}"
                           href="{{ url_for('golf.index') }}">Golf Pick 'Em</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if request.blueprint == 'cfb' %}active{% endif %}"
                           href="{{ url_for('cfb.index') }}">CFB Survivor</a>
                    </li>
                </ul>
```

- [ ] **Step 2: Run smoke test**

```bash
FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected output: `Smoke test OK`

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "refactor: strip game-specific links from platform top bar"
```

---

## Task 3: Add game sub-nav block to base.html

**Files:**
- Modify: `templates/base.html` (insert after `</nav>`, before flash messages `<div>`)

- [ ] **Step 1: Insert the sub-nav block**

In `templates/base.html`, find the line:
```html
    <!-- Flash Messages -->
```

Insert the following block **immediately before** that line (after `</nav>`):

```html
    <!-- Game Sub-Nav: contextual strip, only inside game blueprints -->
    {% if request.blueprint == 'worldcup' %}
    <div class="game-subnav subnav-worldcup">
        <div class="container">
            <a class="subnav-game-label" href="{{ url_for('worldcup.index') }}">
                ⚽ <span class="subnav-label-text">WC 2026</span>
            </a>
            <div class="subnav-pills">
                <a class="subnav-pill {% if request.endpoint == 'worldcup.index' %}active{% endif %}"
                   href="{{ url_for('worldcup.index') }}">Dashboard</a>
                <a class="subnav-pill {% if request.endpoint in ['worldcup.leaderboard', 'worldcup.player_detail'] %}active{% endif %}"
                   href="{{ url_for('worldcup.leaderboard') }}">Leaderboard</a>
                <a class="subnav-pill {% if request.endpoint == 'worldcup.schedule' %}active{% endif %}"
                   href="{{ url_for('worldcup.schedule') }}">Schedule</a>
                <a class="subnav-pill {% if request.endpoint == 'worldcup.groups' %}active{% endif %}"
                   href="{{ url_for('worldcup.groups') }}">Groups</a>
                {% if current_user.is_authenticated %}
                <a class="subnav-pill {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
                   href="{{ url_for('worldcup.picks') }}">My Picks</a>
                {% endif %}
                <a class="subnav-pill {% if request.endpoint == 'worldcup.rules' %}active{% endif %}"
                   href="{{ url_for('worldcup.rules') }}">Rules</a>
            </div>
        </div>
    </div>
    {% elif request.blueprint == 'golf' %}
    <div class="game-subnav subnav-golf">
        <div class="container">
            <a class="subnav-game-label" href="{{ url_for('golf.index') }}">
                ⛳ <span class="subnav-label-text">Golf 2026</span>
            </a>
            <div class="subnav-pills">
                <a class="subnav-pill {% if request.endpoint == 'golf.index' %}active{% endif %}"
                   href="{{ url_for('golf.index') }}">Standings</a>
                <a class="subnav-pill {% if request.endpoint == 'golf.schedule' %}active{% endif %}"
                   href="{{ url_for('golf.schedule') }}">Schedule</a>
                {% if current_user.is_authenticated %}
                <a class="subnav-pill {% if request.endpoint == 'golf.my_picks' %}active{% endif %}"
                   href="{{ url_for('golf.my_picks') }}">My Picks</a>
                {% endif %}
            </div>
        </div>
    </div>
    {% elif request.blueprint == 'cfb' %}
    <div class="game-subnav subnav-cfb">
        <div class="container">
            <a class="subnav-game-label" href="{{ url_for('cfb.index') }}">
                🏈 <span class="subnav-label-text">CFB 2025</span>
            </a>
            <div class="subnav-pills">
                <a class="subnav-pill {% if request.endpoint == 'cfb.index' %}active{% endif %}"
                   href="{{ url_for('cfb.index') }}">Standings</a>
                <a class="subnav-pill {% if request.endpoint == 'cfb.weekly_results' %}active{% endif %}"
                   href="{{ url_for('cfb.weekly_results') }}">Results</a>
                {% if current_user.is_authenticated %}
                <a class="subnav-pill {% if request.endpoint == 'cfb.my_picks' %}active{% endif %}"
                   href="{{ url_for('cfb.my_picks') }}">My Picks</a>
                {% endif %}
            </div>
        </div>
    </div>
    {% endif %}

```

- [ ] **Step 2: Run smoke test**

```bash
FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected output: `Smoke test OK`

- [ ] **Step 3: Visual verification checklist**

Start the dev server:
```bash
FLASK_APP=app.py venv/bin/flask run
```

Check each of the following at `http://localhost:5000`:

| URL | Expected sub-nav |
|---|---|
| `/` (homepage) | No sub-nav strip |
| `/worldcup/` | Navy strip, ⚽ WC 2026 label, red active pill on Dashboard |
| `/worldcup/leaderboard` | Navy strip, Leaderboard pill active |
| `/worldcup/schedule` | Navy strip, Schedule pill active |
| `/worldcup/groups` | Navy strip, Groups pill active |
| `/worldcup/rules` | Navy strip, Rules pill active |
| `/golf/` | Forest strip, ⛳ Golf 2026 label, gold active pill on Standings |
| `/golf/schedule` | Forest strip, Schedule pill active |
| `/cfb/` | Midnight strip, 🏈 CFB 2025 label, crimson active pill on Standings |
| `/login` | No sub-nav strip |

Also verify at browser width ~375px (iPhone): label text hidden, emoji visible, pills scroll horizontally without wrapping.

- [ ] **Step 4: Commit**

```bash
git add templates/base.html
git commit -m "feat: add game sub-nav strip (pill links, per-game theming, mobile-friendly)"
```

---

## Acceptance Checklist

- [ ] World Cup sub-nav: navy bg, red active pills, ⚽ label links to `/worldcup/`
- [ ] Golf sub-nav: forest bg, gold active pills, ⛳ label links to `/golf/`
- [ ] CFB sub-nav: midnight bg, crimson active pills, 🏈 label links to `/cfb/`
- [ ] Home / auth pages: no sub-nav rendered
- [ ] Mobile ≤ 768px: label text hidden, emoji visible, pills scroll without wrapping
- [ ] Active pill matches `request.endpoint` on every page
- [ ] My Picks pill only visible when authenticated
- [ ] Smoke test passes after each task
- [ ] No regressions in platform nav (logo, game switcher, user dropdown, admin link)
