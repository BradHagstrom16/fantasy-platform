# CCC Brand Foundation + Chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Spec A (`docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`) — adopt CCC brand identity across platform chrome (nav, footer, auth, system email, admin), establish the new token architecture, and complete the naming sweep, without touching CFB/Golf interior pages or World Cup screens.

**Architecture:** Layered CSS tokens — new `static/css/tokens.css` (CCC house tokens) loads BEFORE existing `static/css/style.css`, which is rewired to consume the new tokens via aliases. Game-scoped sections in `style.css` are untouched. Naming sweep is a mechanical find-replace across 17 files. Visual restyle of platform chrome (`base.html`) and surface templates (auth, admin, system email) consumes the new tokens.

**Tech Stack:** Flask + Jinja2, Bootstrap 5.3 (kept), CSS custom properties, Teko + Newsreader (already loaded). No new Python dependencies. No DB migration.

**Spec reference:** `docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`

**Branch:** `redesign/ccc-brand` in worktree `../fantasy-platform-ccc`

**Working assumption:** ImageMagick is installed (`magick` or `convert` command). If not, Step 3 of Task 3 has alternatives.

---

## Task 1: Worktree setup and verification

**Files:** none (git operation)

- [ ] **Step 1: Confirm you're on `main` in `~/fantasy-platform`**

```bash
cd ~/fantasy-platform
git status --short
git branch --show-current
```
Expected: branch is `main`, working tree may have unrelated unstaged changes (deploy plan, design bundle untracked) — those are pre-existing and OK.

- [ ] **Step 2: Verify `b0fde0d` (the spec commit) is present on `main`**

```bash
git log --oneline -5
```
Expected: top entry is `b0fde0d docs(spec): add Spec A — CCC brand foundation + chrome design` (or near top if other commits intervened).

- [ ] **Step 3: Create the worktree**

```bash
git worktree add ../fantasy-platform-ccc -b redesign/ccc-brand main
```
Expected: `Preparing worktree (new branch 'redesign/ccc-brand')` and `HEAD is now at b0fde0d ...`

- [ ] **Step 4: Move to the worktree and verify state**

```bash
cd ../fantasy-platform-ccc
git status --short
git branch --show-current
ls docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md
```
Expected: clean working tree, branch `redesign/ccc-brand`, spec file present.

- [ ] **Step 5: Set up venv (worktree shares `.gitignore` but not `venv/`)**

```bash
ls venv/ 2>/dev/null && echo "venv present" || python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
Expected: either `venv present` (if it carried over) or fresh install completes. If install fails, fall back to `cd ~/fantasy-platform && cp -R venv ../fantasy-platform-ccc/`.

- [ ] **Step 6: Smoke-test the app boots in the worktree**

```bash
mkdir -p instance/
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```
Expected: `Smoke test OK`. If it fails, do not proceed — fix the venv or environment first.

- [ ] **Step 7: No commit at this task — worktree creation is not a code change**

Skip commit; proceed to Task 2.

---

## Task 2: Add `static/css/tokens.css` (CCC house tokens)

**Files:**
- Create: `static/css/tokens.css`

- [ ] **Step 1: Verify the source file exists in the design bundle**

```bash
ls -la fantasy-platform-and-world-cup-design/project/styles/tokens.css
```
Expected: file exists, ~890 bytes.

- [ ] **Step 2: Confirm tokens.css does NOT yet exist in static/css/**

```bash
ls static/css/tokens.css 2>&1
```
Expected: `ls: static/css/tokens.css: No such file or directory`. If it exists, halt and ask for direction.

- [ ] **Step 3: Create `static/css/tokens.css` with the design bundle's tokens (verbatim per spec 3a)**

Write file with content:

```css
/* ============================================================
   Corrupt Commish Club — Design Tokens (Layer 1)
   Source: fantasy-platform-and-world-cup-design/project/styles/tokens.css
   Loaded BEFORE style.css in templates/base.html.
   ============================================================ */
:root{
  --ink:           #0A0612;
  --purple-950:    #140828;
  --purple-900:    #1C0A3A;
  --purple-850:    #230E48;
  --purple-800:    #2A1150;
  --purple-700:    #3A1D72;
  --purple-600:    #4E2A8F;
  --purple-500:    #6B3FAD;
  --purple-400:    #8E63C9;

  --gold-dark:     #8A6A1A;
  --gold:          #C9A227;
  --gold-light:    #F2D36B;
  --gold-hi:       #FFF1B8;

  --bone:          #F3EFE6;
  --bone-dim:      #D8D1BE;
  --bone-mute:     rgba(243,239,230,.55);

  /* WC scoped tokens — inert in Spec A; activated in Spec C */
  --wc-navy:       #001A4D;
  --wc-red:        #BF0A30;
  --wc-white:      #F5F1E8;

  --metal-gold: linear-gradient(180deg,
    #FFF1B8 0%, #F2D36B 18%, #C9A227 52%, #8A6A1A 78%, #E2B947 100%);
  --metal-gold-flat: linear-gradient(135deg, #F2D36B 0%, #C9A227 45%, #8A6A1A 100%);

  --live-red:      #E63946;
  --live-green:    #64DBA0;

  --font-teko: 'Teko', sans-serif;
  --font-news: 'Newsreader', Georgia, serif;
}
```

- [ ] **Step 4: Verify the file**

```bash
ls -la static/css/tokens.css
head -5 static/css/tokens.css
```
Expected: file exists ~1.1KB; first 5 lines match the comment header.

- [ ] **Step 5: Commit**

```bash
git add static/css/tokens.css
git commit -m "feat(ccc): add CCC design tokens (Layer 1)

Adopts the design bundle's tokens.css verbatim. WC scoped tokens
included but inert until Spec C wires them via body.game-worldcup."
```

---

## Task 3: Generate logo and favicon assets

**Files:**
- Create: `static/img/ccc-logo-mark.png` (240×240, ≤30KB)
- Create: `static/img/ccc-logo.png` (600×200, ≤60KB)
- Create: `static/img/favicon.ico` (16/32/48 multi-res, ≤8KB)
- Create: `static/img/favicon-180.png` (180×180, ≤12KB)

- [ ] **Step 1: Confirm `static/img/` directory and the source asset**

```bash
mkdir -p static/img
ls -la fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png
```
Expected: dir created/exists; source PNG ~1.7MB.

- [ ] **Step 2: Detect ImageMagick (preferred tool) or fall back**

```bash
which magick || which convert
```
Expected: a path to `magick` (IM7) or `convert` (IM6). If neither, see Step 3 alternative.

- [ ] **Step 3: Generate `ccc-logo-mark.png` (240×240, square crop of the mark)**

If ImageMagick is available:
```bash
magick fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  -resize 240x240 -strip -quality 92 \
  static/img/ccc-logo-mark.png
```
Or with IM6: replace `magick` with `convert`.

If no ImageMagick: use any web tool (squoosh.app, tinypng.com) or Mac's `sips`:
```bash
sips -z 240 240 fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  --out static/img/ccc-logo-mark.png
```

Verify size:
```bash
ls -la static/img/ccc-logo-mark.png
```
Expected: ≤30KB. If larger, re-run with lower `-quality` (try 85).

- [ ] **Step 4: Generate `ccc-logo.png` (600×200 wordmark for Spec B's hero)**

```bash
magick fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  -resize 600x200 -strip -quality 92 \
  static/img/ccc-logo.png
```
Or `sips -z 200 600 ...`.

Verify:
```bash
ls -la static/img/ccc-logo.png
```
Expected: ≤60KB.

- [ ] **Step 5: Generate `favicon.ico` (multi-resolution)**

```bash
magick fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  -resize 48x48 -strip \
  \( -clone 0 -resize 32x32 \) \
  \( -clone 0 -resize 16x16 \) \
  -delete 0 \
  static/img/favicon.ico
```
If this errors, simpler fallback (single 32×32):
```bash
magick fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  -resize 32x32 -strip static/img/favicon.ico
```
Or use a web tool (favicon.io). Verify:
```bash
ls -la static/img/favicon.ico
file static/img/favicon.ico
```
Expected: ≤8KB; `MS Windows icon resource` or similar.

- [ ] **Step 6: Generate `favicon-180.png` (180×180 apple-touch-icon)**

```bash
magick fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png \
  -resize 180x180 -strip -quality 92 \
  static/img/favicon-180.png
```
Verify ≤12KB.

- [ ] **Step 7: Commit**

```bash
git add static/img/
git commit -m "feat(ccc): add CCC logo and favicon assets

Outputs derived from the design bundle's ccc-logo-transparent.png:
- ccc-logo-mark.png (240×240) for nav/auth
- ccc-logo.png (600×200) reserved for Spec B hero
- favicon.ico (multi-res) + favicon-180.png (apple-touch-icon)"
```

---

## Task 4: Wire `<head>` in `base.html` — tokens.css link, favicons, theme-color

**Files:**
- Modify: `templates/base.html` (lines 13–22 area)

- [ ] **Step 1: Read current `<head>` of `base.html` to confirm structure**

```bash
sed -n '1,25p' templates/base.html
```
Expected: matches the structure documented in the spec (Google Fonts link at line 12, Bootstrap CSS at 15, platform CSS at 20).

- [ ] **Step 2: Insert tokens.css `<link>` BEFORE the Bootstrap CSS link**

Edit `templates/base.html`. Find:
```html
    <!-- Bootstrap 5.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
```
Replace with:
```html
    <!-- CCC tokens — must load before Bootstrap and style.css -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/tokens.css') }}">

    <!-- Bootstrap 5.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
```

- [ ] **Step 3: Add favicon and theme-color tags AFTER the Bootstrap Icons link**

Find:
```html
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">

    <!-- Platform CSS -->
```
Replace with:
```html
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">

    <!-- Favicons -->
    <link rel="icon" href="{{ url_for('static', filename='img/favicon.ico') }}" sizes="any">
    <link rel="apple-touch-icon" href="{{ url_for('static', filename='img/favicon-180.png') }}">
    <meta name="theme-color" content="#3A1D72">

    <!-- Platform CSS -->
```

- [ ] **Step 4: Boot the dev server and verify the new files load with no 404s**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050 &
SERVER_PID=$!
sleep 2
curl -sI http://localhost:5050/static/css/tokens.css | head -1
curl -sI http://localhost:5050/static/img/favicon.ico | head -1
curl -sI http://localhost:5050/static/img/favicon-180.png | head -1
kill $SERVER_PID
```
Expected: all three return `HTTP/1.1 200 OK`. If any 404s, halt and fix paths.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html
git commit -m "feat(ccc): wire tokens.css, favicons, theme-color in base.html

Loads CCC tokens BEFORE Bootstrap so style.css can consume them
in the next task. Adds favicon.ico, apple-touch-icon, and a
purple theme-color for mobile Safari address-bar tinting."
```

---

## Task 5: Rewire `style.css` `:root` block + add brand-mark classes

**Files:**
- Modify: `static/css/style.css` (lines 1–61, plus add brand-mark classes)

- [ ] **Step 1: Read current `:root` block to confirm what we're rewiring**

```bash
sed -n '1,65p' static/css/style.css
```
Expected: matches the spec's "before" — `--platform-primary: #3A1D72`, `--platform-accent: #D4A820`, etc.

- [ ] **Step 2: Replace lines 1–61 of `style.css`**

Replace the entire current header + `:root` block with:

```css
/* ============================================================
   Corrupt Commish Club — Platform Design System (Layer 2)
   Identity: Broadcast Authority — premium sports editorial
   Fonts: Teko (display/headings) + Newsreader (body/editorial)
   Token source: static/css/tokens.css (Layer 1)
   ============================================================ */

/* ── 1. CSS Custom Properties (:root) ────────────────────── */
:root {
  /* Platform identity — alias into Layer 1 CCC tokens */
  --platform-primary:        var(--purple-700);
  --platform-primary-dark:   var(--purple-900);
  --platform-primary-light:  var(--purple-500);
  --platform-accent:         var(--gold);
  --platform-accent-light:   var(--gold-light);

  /* Surfaces */
  --bg-page:                 var(--bone);
  --bg-card:                 #FFFFFF;
  --bg-muted:                #EDEBF4;

  /* Text */
  --text-primary:            #1C1730;
  --text-secondary:          #5A5470;
  --text-muted:              #8A849B;
  --text-on-dark:            var(--bone);

  /* Semantic */
  --success:                 #1A7A45;
  --success-bg:              #ecfdf5;
  --danger:                  #C0392B;
  --danger-bg:               #fef2f2;
  --warning:                 var(--gold);
  --warning-bg:              #FBF3DC;
  --warning-text:            #92400e;
  --info:                    #3B5998;
  --info-bg:                 #eff6ff;

  /* Borders */
  --border:                  #D8DDE8;
  --border-light:            #E8E5F0;

  /* Shadows */
  --shadow-sm:               0 2px 8px rgba(58,29,114,.07);
  --shadow-md:               0 4px 20px rgba(58,29,114,.12);
  --shadow-lg:               0 8px 40px rgba(58,29,114,.17);
  --shadow-gold:             0 4px 24px rgba(201,162,39,.25);

  /* Radius */
  --radius:                  .5rem;
  --radius-lg:               .875rem;

  /* Transitions */
  --transition:              .2s cubic-bezier(.4,0,.2,1);

  /* Game override slots — default to platform values */
  --game-primary:            var(--platform-primary);
  --game-primary-dark:       var(--platform-primary-dark);
  --game-primary-light:      var(--platform-primary-light);
  --game-accent:             var(--platform-accent);
  --game-accent-light:       var(--platform-accent-light);
}

/* Brand mark sizing — used in nav, auth heroes, email headers */
.brand-mark { width: 28px; height: 28px; vertical-align: -.35em; margin-right: .5rem; }
.brand-mark--lg { width: 56px; height: 56px; }
```

Leave everything from line 62 onward (`/* ── 2. Game-Specific Overrides ──────── */` and below) untouched.

- [ ] **Step 3: Verify Golf and CFB sections are still present**

```bash
grep -n "body.game-golf\|body.game-cfb\|body.game-worldcup" static/css/style.css
```
Expected: at least two matches each (one in `body.game-* { ... }` selector, possibly more in component selectors).

- [ ] **Step 4: Reload dev server and visually confirm a Bootstrap-styled page still renders**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050 &
SERVER_PID=$!
sleep 2
curl -s http://localhost:5050/login | grep -q "Bootstrap\|bootstrap" && echo "Bootstrap link present"
curl -s http://localhost:5050/login | grep -q "tokens.css" && echo "tokens.css link present"
kill $SERVER_PID
```
Expected: both echoes print. If `tokens.css link present` doesn't print, recheck Task 4 step 2.

- [ ] **Step 5: Commit**

```bash
git add static/css/style.css
git commit -m "feat(ccc): rewire style.css :root to consume CCC tokens

Platform identity tokens become aliases into tokens.css. Surfaces
(--bg-page) shift from #F5F3F0 to var(--bone) (#F3EFE6) — hair
difference. Game-scoped sections (Golf, CFB) untouched. Adds
.brand-mark and .brand-mark--lg classes."
```

---

## Task 6: Naming sweep — Layer 2 (code/config strings)

**Files:**
- Modify: `utils/email.py` (lines 9, 20)
- Modify: `core/auth/routes.py` (line 124)

- [ ] **Step 1: Read current state of `utils/email.py` lines 1–25**

```bash
sed -n '1,25p' utils/email.py
```

- [ ] **Step 2: Replace `PLATFORM_FROM_NAME` and its docstring**

Find:
```python
From-name: "The Commissioner's Club" for all outbound email.
```
Replace with:
```python
From-name: "Corrupt Commish Club" for all outbound email.
```

Find:
```python
PLATFORM_FROM_NAME = "The Commissioner's Club"
```
Replace with:
```python
PLATFORM_FROM_NAME = "Corrupt Commish Club"
```

- [ ] **Step 3: Update password-reset email subject in `core/auth/routes.py`**

```bash
sed -n '120,128p' core/auth/routes.py
```

Find:
```python
"Reset your password — The Commissioner's Club",
```
Replace with:
```python
"Reset your password — Corrupt Commish Club",
```

- [ ] **Step 4: Verify no `Commissioner` strings remain in these two files**

```bash
grep -n "Commissioner" utils/email.py core/auth/routes.py
```
Expected: zero results.

- [ ] **Step 5: Type check (no logic change, but confirm no syntax error)**

```bash
venv/bin/pyright utils/email.py core/auth/routes.py
```
Expected: 0 errors, 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add utils/email.py core/auth/routes.py
git commit -m "refactor(ccc): rename platform brand string in email + auth code

PLATFORM_FROM_NAME and password-reset subject line updated.
Behavior unchanged."
```

---

## Task 7: Naming sweep — Layer 1 (template title strings) + style.css comment

**Files:**
- Modify: `templates/base.html` (line 7)
- Modify: `templates/errors/404.html` (line 2)
- Modify: `templates/errors/500.html` (line 2)
- Modify: `templates/email/reset_password_html.j2` (lines 17, 54)
- Modify: `templates/email/reset_password_plain.txt` (lines 3, 12)
- Modify: `core/auth/templates/auth/login.html` (lines 3, 10, 12)
- Modify: `core/auth/templates/auth/register.html` (lines 3, 10)
- Modify: `core/auth/templates/auth/forgot_password.html` (lines 3, 10)
- Modify: `core/auth/templates/auth/reset_password.html` (lines 3, 10)
- Modify: `core/auth/templates/auth/change_password.html` (line 3)
- Modify: `core/auth/templates/auth/profile.html` (line 3)
- Modify: `core/admin/templates/admin/dashboard.html` (line 3)
- Modify: `core/admin/templates/admin/users.html` (line 3)
- Modify: `core/main/templates/main/index.html` (lines 3, 9)
- Modify: `static/css/style.css` (line 2 — top comment, since rewritten in Task 5 the line might already say "Corrupt Commish Club"; verify and fix if not)

> **Note:** Task 5 already updated `static/css/style.css`'s top comment to "Corrupt Commish Club". Verify in Step 1 and skip if already done.

- [ ] **Step 1: Confirm `style.css` line 2 already says "Corrupt Commish Club" (Task 5 leftover)**

```bash
sed -n '1,3p' static/css/style.css
```
Expected: comment already says `Corrupt Commish Club`. If not, fix it now (Edit line 2).

- [ ] **Step 2: Sweep title blocks and brand strings — apostrophe-aware (use plain `'` not curly `'`)**

Run an inventory grep first to lock in the exact occurrences to handle:
```bash
grep -rn "The Commissioner's Club\|The Commissioner&#8217;s Club\|TCC" \
  templates/ core/ \
  --include="*.html" --include="*.j2" --include="*.txt"
```
Save the output mentally; you'll edit each file accordingly.

- [ ] **Step 3: Replace `The Commissioner's Club` → `Corrupt Commish Club` (plain ASCII apostrophe)**

For each file/line above, do an Edit. Examples:

`templates/base.html` line 7:
```diff
- <title>{% block title %}The Commissioner's Club{% endblock %}</title>
+ <title>{% block title %}Corrupt Commish Club{% endblock %}</title>
```

`core/auth/templates/auth/login.html` line 3:
```diff
- {% block title %}Sign In — The Commissioner's Club{% endblock %}
+ {% block title %}Sign In — Corrupt Commish Club{% endblock %}
```

Repeat for every line in the inventory.

- [ ] **Step 4: Replace HTML-encoded variant `The Commissioner&#8217;s Club` → `Corrupt Commish Club`**

```bash
grep -rn "Commissioner&#8217;s Club" templates/
```
For each hit (notably `templates/email/reset_password_html.j2` line 17, 54), Edit to `Corrupt Commish Club`.

- [ ] **Step 5: Replace `TCC` → `CCC` in `base.html` line 31**

`templates/base.html` line 31 (mobile compact brand text):
```diff
- <span class="d-md-none">TCC</span>
+ <span class="d-md-none">CCC</span>
```

- [ ] **Step 6: Special handling for `core/auth/templates/auth/login.html` lines 10–12**

Read current state:
```bash
sed -n '8,16p' core/auth/templates/auth/login.html
```

The current hero is split across two lines:
```html
                The Commissioner's<br>
                Club
```
Replace with:
```html
                Corrupt Commish<br>
                Club
```

(The `<br>` stays — it's the visual line break.)

- [ ] **Step 7: Verify the sweep is complete (Gate 1 from spec)**

```bash
grep -rn "Commissioner\|TCC\b" templates/ core/ utils/ static/css/ \
  games/golf/services/reminders.py games/cfb/services/reminders.py \
  --include="*.py" --include="*.html" --include="*.j2" --include="*.txt" --include="*.css"
```
Expected: zero results EXCEPT in `games/*/services/reminders.py` (handled in Task 8). If any other file still has these strings, fix it now.

- [ ] **Step 8: Commit**

```bash
git add templates/ core/auth/templates/ core/admin/templates/ core/main/templates/
git commit -m "refactor(ccc): naming sweep — replace platform brand strings in templates

Sweeps title blocks, brand-logo display text, hero copy, email
templates, error pages. Plain ASCII apostrophe used uniformly.
TCC → CCC for mobile compact. Game reminder emails handled
separately in Task 8."
```

---

## Task 8: Naming sweep — Layer 3 (game reminder emails) + COMMISSIONER_NAME default

**Files:**
- Modify: `games/golf/services/reminders.py` (lines 120, 215, 509, 920)
- Modify: `games/cfb/services/reminders.py` (line 100)

- [ ] **Step 1: Read context around Golf reminders line 120**

```bash
sed -n '115,125p' games/golf/services/reminders.py
```

- [ ] **Step 2: Update Golf email footer brand link text (line 120)**

Find:
```python
Golf Pick &#8217;Em {season_year} &middot; <a href="{site_url}" style="color: {_GOLD_300}; text-decoration: none;">The Commissioner&#8217;s Club</a>
```
Replace `The Commissioner&#8217;s Club` with `Corrupt Commish Club`. (The Golf-specific surrounding markup stays.)

- [ ] **Step 3: Update `COMMISSIONER_NAME` default value at lines 215, 509, 920**

For each occurrence:
```bash
grep -n "COMMISSIONER_NAME" games/golf/services/reminders.py
```

Replace each:
```diff
- commissioner_name = config.get('COMMISSIONER_NAME', 'The Commissioner')
+ commissioner_name = config.get('COMMISSIONER_NAME', 'The Commish')
```

(All three occurrences identical — three Edits, one per line. Env var key unchanged per spec D8.)

- [ ] **Step 4: Update CFB reminders line 100**

```bash
sed -n '95,105p' games/cfb/services/reminders.py
```

Find:
```python
CFB Survivor Pool {season_year} &middot; <a href="{site_url}" style="color: {c['primary_light']}; text-decoration: none;">The Commissioner&#8217;s Club</a>
```
Replace `The Commissioner&#8217;s Club` with `Corrupt Commish Club`.

- [ ] **Step 5: Verify Gate 1 fully passes now**

```bash
grep -rn "Commissioner\|TCC\b" templates/ core/ utils/ static/css/ \
  games/golf/services/reminders.py games/cfb/services/reminders.py \
  --include="*.py" --include="*.html" --include="*.j2" --include="*.txt" --include="*.css"
```
Expected: zero results across all files.

- [ ] **Step 6: Type check the modified files**

```bash
venv/bin/pyright games/golf/services/reminders.py games/cfb/services/reminders.py
```
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add games/golf/services/reminders.py games/cfb/services/reminders.py
git commit -m "refactor(ccc): update game reminder email brand text + COMMISSIONER_NAME default

Brand string in Golf and CFB email footers updated to CCC. The
COMMISSIONER_NAME env var default flips from 'The Commissioner'
to 'The Commish' (key unchanged — env file untouched at deploy).
Game-themed visual styling of these emails left intact for those
games' future per-palette redesigns."
```

---

## Task 9: Brand chrome — `base.html` navbar restructure

**Files:**
- Modify: `templates/base.html` (lines 26–89, navbar block)

- [ ] **Step 1: Read current navbar block to confirm exact structure**

```bash
sed -n '25,90p' templates/base.html
```

- [ ] **Step 2: Replace the brand block — swap trophy icon for logo mark image**

Find:
```html
            <a class="navbar-brand" href="{{ url_for('main.index') }}">
                <i class="bi bi-trophy-fill me-1"></i>
                <span class="d-none d-md-inline">Corrupt Commish Club</span>
                <span class="d-md-none">CCC</span>
            </a>
```
Replace with:
```html
            <a class="navbar-brand" href="{{ url_for('main.index') }}">
                <img src="{{ url_for('static', filename='img/ccc-logo-mark.png') }}" class="brand-mark" alt="">
                <span class="d-none d-md-inline">Corrupt Commish Club</span>
                <span class="d-md-none">CCC</span>
            </a>
```

- [ ] **Step 3: Update Admin nav link label "Admin" → "the Commish"**

Find:
```html
                            <a class="nav-link {% if request.blueprint == 'admin' %}active{% endif %}"
                               href="{{ url_for('admin.dashboard') }}">
                                <i class="bi bi-gear-fill"></i> Admin
                            </a>
```
Replace with:
```html
                            <a class="nav-link {% if request.blueprint == 'admin' %}active{% endif %}"
                               href="{{ url_for('admin.dashboard') }}">
                                <i class="bi bi-gear-fill"></i> the Commish
                            </a>
```

- [ ] **Step 4: Update logged-in dropdown — "Logout" → "Step Out"**

Find:
```html
                                <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">
                                    <i class="bi bi-box-arrow-right me-2"></i>Logout
                                </a></li>
```
Replace with:
```html
                                <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">
                                    <i class="bi bi-box-arrow-right me-2"></i>Step Out
                                </a></li>
```

- [ ] **Step 5: Update logged-out buttons — "Login" → "Sign In", "Join Now" → "Join the Club"**

Find:
```html
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'auth.login' %}active{% endif %}"
                               href="{{ url_for('auth.login') }}">Login</a>
                        </li>
                        <li class="nav-item ms-1">
                            <a class="btn btn-warning btn-sm"
                               href="{{ url_for('auth.register') }}">Join Now</a>
                        </li>
```
Replace with:
```html
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'auth.login' %}active{% endif %}"
                               href="{{ url_for('auth.login') }}">Sign In</a>
                        </li>
                        <li class="nav-item ms-1">
                            <a class="btn btn-warning btn-sm"
                               href="{{ url_for('auth.register') }}">Join the Club</a>
                        </li>
```

- [ ] **Step 6: Add navbar token-driven CSS in `style.css` so the visual styling lands**

Append to `static/css/style.css` (anywhere after the `:root` block — pick after the last existing platform-level component, before the game-scoped sections):

```css
/* === CCC NAVBAR === */
.navbar.navbar-dark {
  background: var(--purple-700);
  border-bottom: 1px solid var(--purple-800);
}
.navbar.navbar-dark .navbar-brand {
  font-family: var(--font-teko);
  font-size: 1.25rem;
  letter-spacing: .04em;
  color: var(--bone);
  display: inline-flex;
  align-items: center;
}
.navbar.navbar-dark .nav-link {
  font-family: var(--font-teko);
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--bone-mute);
  position: relative;
  padding: .5rem .85rem;
}
.navbar.navbar-dark .nav-link:hover { color: var(--gold-light); }
.navbar.navbar-dark .nav-link.active {
  color: var(--gold);
}
.navbar.navbar-dark .nav-link.active::after {
  content: '';
  position: absolute;
  left: 12%; right: 12%; bottom: 4px;
  height: 2px;
  background: var(--gold);
  border-radius: 1px;
}
.navbar.navbar-dark .btn-warning {
  background: var(--metal-gold-flat);
  border: none;
  color: var(--purple-900);
  font-family: var(--font-teko);
  text-transform: uppercase;
  letter-spacing: .08em;
}
.navbar.navbar-dark .btn-warning:hover {
  filter: brightness(1.05);
  color: var(--purple-900);
}
```

- [ ] **Step 7: Boot dev server and visually verify navbar**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```
In a browser at `http://localhost:5050/`:
- Logo mark image visible at left of nav
- Brand text reads "Corrupt Commish Club" on desktop, "CCC" on mobile
- Game switcher items render in Teko all-caps
- Login button in CCC purple bg; "Sign In" / "Join the Club" labels visible when logged out
- If logged in as admin, nav shows "the Commish" with gear icon
- Logged-in user dropdown shows "Step Out" instead of Logout

Stop the server (Ctrl-C).

- [ ] **Step 8: Commit**

```bash
git add templates/base.html static/css/style.css
git commit -m "feat(ccc): restyle navbar — brand mark, voice labels, gold accents

Navbar adopts CCC purple bg with Teko all-caps nav items, gold
underline on active, gold-gradient join button. Voice labels:
Admin → the Commish, Logout → Step Out, Login → Sign In, Join
Now → Join the Club. URLs and is_admin API unchanged."
```

---

## Task 10: Brand chrome — `base.html` footer rewrite

**Files:**
- Modify: `templates/base.html` (lines 180–186, footer block)
- Modify: `static/css/style.css` (append footer CSS)

- [ ] **Step 1: Read current footer**

```bash
sed -n '178,190p' templates/base.html
```

- [ ] **Step 2: Replace footer block with two-strip structure**

Find:
```html
    <!-- Footer -->
    <footer class="text-center">
        <div class="container">
            <span>&copy; 2026 Corrupt Commish Club</span>
        </div>
    </footer>
```
Replace with:
```html
    <!-- Footer -->
    <footer class="ccc-footer">
        <div class="ccc-footer-voice">
            <div class="container">
                An exclusive members&rsquo; club. The Commish keeps the ledger. The Club keeps the code. The losers keep the tab.
            </div>
        </div>
        <div class="ccc-footer-utility">
            <div class="container">
                &copy; 2026 Corrupt Commish Club &middot; Built for the Club, by the Commish
            </div>
        </div>
    </footer>
```

- [ ] **Step 3: Append footer CSS to `static/css/style.css`**

Append after the navbar CSS from Task 9:

```css
/* === CCC FOOTER === */
.ccc-footer {
  margin-top: 4rem;
}
.ccc-footer-voice {
  background: var(--purple-800);
  color: var(--gold-light);
  padding: 1.25rem 0;
  font-family: var(--font-news);
  font-style: italic;
  font-size: .95rem;
  text-align: center;
  border-top: 2px solid var(--gold);
}
.ccc-footer-utility {
  background: var(--purple-900);
  color: var(--bone-mute);
  padding: .75rem 0;
  font-family: var(--font-teko);
  font-size: .8rem;
  letter-spacing: .12em;
  text-align: center;
  text-transform: uppercase;
}
```

- [ ] **Step 4: Boot dev server and verify**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```
In browser at `http://localhost:5050/`:
- Voice strip: italic Newsreader, gold text on deeper purple, the four-sentence line wraps cleanly
- Utility strip: small Teko all-caps, muted bone, deeper purple bg
- Both strips full-width

Stop server.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html static/css/style.css
git commit -m "feat(ccc): rewrite footer with voice + utility strips

Voice strip carries the brand line in Newsreader italic gold on
purple. Utility strip is Teko all-caps copyright + tagline. No
domain string. No social links."
```

---

## Task 11: Auth pages restyle — `login.html` (pattern template)

**Files:**
- Modify: `core/auth/templates/auth/login.html`
- Modify: `static/css/style.css` (append auth CSS — single block consumed by all 6 auth pages)

- [ ] **Step 1: Read current `login.html` to understand the existing structure**

```bash
cat core/auth/templates/auth/login.html
```
Expected: extends `base.html`, has a `.brand-logo` div with trophy icon, hero copy, form, and links.

- [ ] **Step 2: Add `body_class` block override in `login.html` so CSS can target `body.auth-page`**

At the top of `login.html`, ensure the template sets the body class. Find the first `{% block %}` directive after `extends`. Add (or update) the body_class block:

```jinja
{% extends "base.html" %}
{% block body_class %}auth-page{% endblock %}
```

(The `base.html` has `<body class="{{ body_class|default('') }}">` so this block sets the class.)

- [ ] **Step 3: Replace the brand-logo block — swap `<i>` icon for logo mark image, scale up**

Find:
```html
            <div class="brand-logo"><i class="bi bi-trophy-fill me-1"></i> Corrupt Commish Club</div>
```
Replace with:
```html
            <div class="brand-logo">
                <img src="{{ url_for('static', filename='img/ccc-logo-mark.png') }}" class="brand-mark brand-mark--lg" alt="">
                <span>Corrupt Commish Club</span>
            </div>
```

- [ ] **Step 4: Append auth-page CSS to `static/css/style.css`**

Append after the footer CSS from Task 10:

```css
/* === CCC AUTH PAGES === */
body.auth-page {
  background: var(--purple-950);
  background-image: radial-gradient(ellipse at center, var(--purple-900) 0%, var(--purple-950) 70%);
  color: var(--bone);
  min-height: 100vh;
}
body.auth-page main {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 220px); /* offset for navbar + footer */
  padding: 2rem 1rem;
}
body.auth-page .brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .75rem;
  font-family: var(--font-teko);
  text-transform: uppercase;
  letter-spacing: .04em;
  font-size: 1.5rem;
  color: var(--gold);
  margin-bottom: 1.5rem;
}
body.auth-page .auth-card,
body.auth-page .card {
  background: var(--bone);
  color: var(--text-primary);
  border: 1px solid var(--bone-dim);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 2.5rem 2rem;
  max-width: 440px;
  width: 100%;
}
body.auth-page h1, body.auth-page .auth-title {
  font-family: var(--font-teko);
  font-size: 2rem;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--purple-700);
  margin-bottom: .5rem;
  text-align: center;
}
body.auth-page .auth-subhead, body.auth-page .text-muted {
  font-family: var(--font-news);
  font-style: italic;
  color: var(--text-secondary);
}
body.auth-page .form-control {
  background: #fff;
  border: 1px solid rgba(58, 29, 114, .18);
  color: var(--text-primary);
}
body.auth-page .form-control:focus {
  border-color: var(--gold);
  box-shadow: 0 0 0 .2rem rgba(201, 162, 39, .25);
  outline: none;
}
body.auth-page .form-label {
  font-family: var(--font-teko);
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: .85rem;
  color: var(--purple-700);
}
body.auth-page .btn-primary {
  background: var(--metal-gold-flat);
  border: none;
  color: var(--purple-900);
  font-family: var(--font-teko);
  text-transform: uppercase;
  letter-spacing: .08em;
  font-weight: 600;
  padding: .65rem 1.5rem;
  transition: transform .15s, box-shadow .15s;
}
body.auth-page .btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(201, 162, 39, .35);
  background: var(--metal-gold-flat);
  color: var(--purple-900);
}
body.auth-page a {
  color: var(--purple-700);
}
body.auth-page a:hover { color: var(--gold-dark); }
body.auth-page .alert-danger {
  background: var(--danger-bg);
  border: 1px solid var(--danger);
  color: var(--danger);
}
body.auth-page .alert-success {
  background: var(--success-bg);
  border: 1px solid var(--success);
  color: var(--success);
}
```

- [ ] **Step 5: Boot dev server and verify**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```
Visit `http://localhost:5050/login`. Verify:
- Page bg is dark purple with vignette
- Card is bone-cream, centered, with shadow
- Brand-logo shows large logo mark + "Corrupt Commish Club" in Teko gold
- Form labels uppercase Teko purple
- Sign In button is gold gradient with dark purple text
- "Forgot Password" link is purple
- Form submit on hover lifts slightly with gold shadow

Stop server.

- [ ] **Step 6: Commit**

```bash
git add core/auth/templates/auth/login.html static/css/style.css
git commit -m "feat(ccc): restyle login page (pattern for all auth pages)

Sets body.auth-page class. Adds CCC auth-page CSS block (consumed
by all 6 auth pages in next task). Bone card on purple-vignette
bg, Teko form labels, metal-gold primary button. Copy stays plain
per voice doctrine B."
```

---

## Task 12: Auth pages restyle — apply pattern to remaining 5 templates

**Files:**
- Modify: `core/auth/templates/auth/register.html`
- Modify: `core/auth/templates/auth/forgot_password.html`
- Modify: `core/auth/templates/auth/reset_password.html`
- Modify: `core/auth/templates/auth/change_password.html`
- Modify: `core/auth/templates/auth/profile.html`

- [ ] **Step 1: Apply pattern to `register.html`**

Add at top after `{% extends "base.html" %}`:
```jinja
{% block body_class %}auth-page{% endblock %}
```
And replace the brand-logo block:
```html
            <div class="brand-logo"><i class="bi bi-trophy-fill me-1"></i> Corrupt Commish Club</div>
```
With:
```html
            <div class="brand-logo">
                <img src="{{ url_for('static', filename='img/ccc-logo-mark.png') }}" class="brand-mark brand-mark--lg" alt="">
                <span>Corrupt Commish Club</span>
            </div>
```

- [ ] **Step 2: Apply pattern to `forgot_password.html`** — same two edits.

- [ ] **Step 3: Apply pattern to `reset_password.html`** — same two edits.

- [ ] **Step 4: Apply pattern to `change_password.html`**

`change_password.html` has only the title block change (Task 7). It does NOT have a `.brand-logo` div per the spec inventory. Just add `body_class`:
```jinja
{% extends "base.html" %}
{% block body_class %}auth-page{% endblock %}
```

(If reading the file shows it DOES have a `.brand-logo`, also apply the brand-mark replacement.)

- [ ] **Step 5: Apply pattern to `profile.html`** — same as Step 4 (no `.brand-logo` per spec; just add `body_class`). If file actually has `.brand-logo`, apply the replacement.

- [ ] **Step 6: Boot dev server and walk through all 6 auth pages**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```
Visit each in browser:
- `/login` — already verified Task 11
- `/register`
- `/auth/forgot-password`
- `/auth/reset-password/<any-string>` (will 404 the token but should still render the chrome)
- `/auth/change-password` — requires login; create a user via `/register` first if needed
- `/auth/profile` — requires login

Each should have CCC purple bg, bone card, gold accents, plain copy.

Stop server.

- [ ] **Step 7: Commit**

```bash
git add core/auth/templates/auth/
git commit -m "feat(ccc): apply auth-page pattern to register, forgot, reset, change, profile

Each template sets body.auth-page and (where present) replaces the
brand-logo trophy icon with the CCC logo mark. Visual styling
inherited from the auth-page CSS block."
```

---

## Task 13: Admin pages restyle — eyebrow + voice labels

**Files:**
- Modify: `core/admin/templates/admin/dashboard.html`
- Modify: `core/admin/templates/admin/users.html`
- Modify: `core/admin/templates/admin/enrollments.html`
- Modify: `static/css/style.css` (append admin eyebrow CSS)

- [ ] **Step 1: Append admin-eyebrow CSS to `static/css/style.css`**

```css
/* === CCC ADMIN EYEBROW === */
.admin-eyebrow {
  font-family: var(--font-teko);
  font-size: .85rem;
  letter-spacing: .14em;
  color: var(--gold);
  text-transform: uppercase;
  margin-bottom: .25rem;
  display: block;
}
.admin-page-title {
  font-family: var(--font-teko);
  font-size: 2.25rem;
  letter-spacing: .04em;
  color: var(--purple-700);
  text-transform: uppercase;
  margin-bottom: 1.5rem;
}
```

- [ ] **Step 2: Read current `dashboard.html` page header**

```bash
head -30 core/admin/templates/admin/dashboard.html
```
Identify the existing `<h1>Dashboard</h1>` (or similar) opening header.

- [ ] **Step 3: Replace the page header in `dashboard.html`**

Find the current page header (likely `<h1>Dashboard</h1>` or similar — the exact markup may vary; read the file). Replace with:
```html
<span class="admin-eyebrow">The Commish&rsquo;s Desk</span>
<h1 class="admin-page-title">Dashboard</h1>
```

- [ ] **Step 4: Replace the page header in `users.html`**

Find the existing user-management page header. Replace with:
```html
<span class="admin-eyebrow">The Commish&rsquo;s Desk</span>
<h1 class="admin-page-title">the Club</h1>
```

(Title display becomes "the Club" per voice vocab; route stays `/admin/users`, model unchanged.)

- [ ] **Step 5: Replace the page header in `enrollments.html`**

Find the existing enrollments page header. Replace with:
```html
<span class="admin-eyebrow">The Commish&rsquo;s Desk</span>
<h1 class="admin-page-title">Enrollments</h1>
```

(Plain "Enrollments" — no voice term per voice vocab.)

- [ ] **Step 6: Boot and verify**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```
Log in as admin. Visit `/admin/`, `/admin/users`, `/admin/enrollments`. Verify:
- Each page has gold Teko eyebrow "THE COMMISH'S DESK" above the title
- Title is large purple Teko all-caps
- Tables and forms below render with Bootstrap defaults (untouched in Spec A)

Stop server.

- [ ] **Step 7: Commit**

```bash
git add core/admin/templates/admin/ static/css/style.css
git commit -m "feat(ccc): restyle admin page headers with Commish eyebrow

Each admin page gets a gold Teko 'The Commish's Desk' eyebrow
above a large purple Teko title. Display titles use voice vocab
(Dashboard, the Club, Enrollments). URLs and is_admin API
unchanged. Row actions stay plain."
```

---

## Task 14: System email restyle — `reset_password_html.j2`

**Files:**
- Modify: `templates/email/reset_password_html.j2`

- [ ] **Step 1: Read current email template**

```bash
cat templates/email/reset_password_html.j2
```

- [ ] **Step 2: Replace the entire template with the CCC-restyled version**

Replace the file contents with:

```jinja
{% raw %}<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Reset your password — Corrupt Commish Club</title>
</head>
<body style="margin:0; padding:0; background:#F3EFE6; font-family: 'Newsreader', Georgia, serif; color:#1C1730;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3EFE6;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px; background:#FFFFFF; border-radius:8px; overflow:hidden; box-shadow:0 4px 20px rgba(58,29,114,.12);">

        <!-- Header band -->
        <tr>
          <td style="background:#2A1150; padding:24px 28px; text-align:center;">
            <span style="font-family:'Teko', sans-serif; font-size:24px; font-weight:600; letter-spacing:.04em; color:#C9A227; text-transform:uppercase;">Corrupt Commish Club</span>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 28px;">
            <h1 style="font-family:'Teko', sans-serif; font-size:28px; font-weight:600; letter-spacing:.04em; color:#3A1D72; text-transform:uppercase; margin:0 0 16px 0;">Reset your password</h1>
            <p style="margin:0 0 16px 0; line-height:1.55;">{% endraw %}You requested a password reset for your Corrupt Commish Club account.{% raw %}</p>
            <p style="margin:0 0 24px 0; line-height:1.55;">{% endraw %}Click the button below to set a new password. This link expires in 1 hour.{% raw %}</p>

            <!-- CTA -->
            <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
              <tr>
                <td align="center" style="background:linear-gradient(135deg,#F2D36B 0%,#C9A227 45%,#8A6A1A 100%); border-radius:6px;">
                  <a href="{% endraw %}{{ reset_url }}{% raw %}" style="display:inline-block; padding:14px 32px; font-family:'Teko', sans-serif; font-size:16px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:#1C0A3A; text-decoration:none;">Reset Password</a>
                </td>
              </tr>
            </table>

            <p style="margin:24px 0 0 0; line-height:1.55; font-size:14px; color:#5A5470;">{% endraw %}If you didn&rsquo;t request this, you can safely ignore this email — your password will remain unchanged.{% raw %}</p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#1C0A3A; padding:16px 28px; text-align:center;">
            <span style="font-family:'Teko', sans-serif; font-size:12px; letter-spacing:.12em; color:rgba(243,239,230,.55); text-transform:uppercase;">Corrupt Commish Club</span>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>{% endraw %}
```

> Note on the `{% raw %}` ... `{% endraw %}` wrapping: Jinja escaping ensures the literal text in the template renders correctly. `{{ reset_url }}` is the only Jinja interpolation. If the existing template already has different variable names (e.g., `{{ url }}` or `{{ link }}`), use the existing variable name — verify in Step 1 by reading the original file.

- [ ] **Step 3: If the variable name differs from `reset_url`, fix it**

```bash
grep -E "{{ ?(reset_url|url|link|reset_link) ?}}" templates/email/reset_password_html.j2
```
Use the same variable name that `core/auth/routes.py` passes when rendering this template.

```bash
grep -A2 "render_template.*reset_password_html" core/auth/routes.py
```
Expected: shows the variable name passed. Match it in the template.

- [ ] **Step 4: Render the template locally to verify it's not broken**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    from flask import render_template
    html = render_template('email/reset_password_html.j2', reset_url='http://localhost:5050/auth/reset-password/test-token')
    with open('/tmp/reset_email_preview.html', 'w') as f:
        f.write(html)
    print('Rendered to /tmp/reset_email_preview.html')
"
```
Expected: prints success message. Open `/tmp/reset_email_preview.html` in a browser to visually verify:
- Header band purple with gold Teko wordmark
- Body bone bg, dark text, Newsreader serif
- Gold gradient CTA button
- Footer dark purple with muted bone tagline

If template rendering errors, fix the variable name in Step 3.

- [ ] **Step 5: Commit**

```bash
git add templates/email/reset_password_html.j2
git commit -m "feat(ccc): restyle password-reset HTML email

CCC purple header band with Teko gold wordmark, bone body card,
gold-gradient CTA, dark purple footer tagline. All inline styles
for Gmail compat. Plain-text fallback unchanged in copy (already
swept in Task 7)."
```

---

## Task 15: CLAUDE.md targeted edit

**Files:**
- Modify: `CLAUDE.md` (Design system bullet around line 75)

- [ ] **Step 1: Find the design-system bullet in CLAUDE.md**

```bash
grep -n "Commissioner" CLAUDE.md
```
Expected: shows the line in the conventions section (around `Design system: "The Commissioner's Club"`).

- [ ] **Step 2: Replace just that one bullet**

Find:
```markdown
- **Design system:** "The Commissioner's Club" — platform purple/gold + per-game palettes via `body.game-<game>` CSS class
```
Replace with:
```markdown
- **Design system:** "Corrupt Commish Club" (CCC) — CCC purple/gold tokens in `static/css/tokens.css` + per-game palettes via `body.game-<game>` CSS class. See `docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`.
```

- [ ] **Step 3: Verify only that one line changed**

```bash
git diff CLAUDE.md
```
Expected: a one-line diff. Bulk content of CLAUDE.md untouched.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(ccc): update CLAUDE.md design-system bullet to CCC

Targeted edit only. Full audit/restructure of CLAUDE.md happens
in the post-Spec A revise-claude-md pass."
```

---

## Task 16: Run automated verification gates (Spec section 7a)

**Files:** none (verification only)

- [ ] **Step 1: Gate 1 — Naming sweep complete (must return zero)**

```bash
grep -rn "Commissioner\|TCC\b" templates/ core/ utils/ static/css/ \
  games/golf/services/reminders.py games/cfb/services/reminders.py \
  --include="*.py" --include="*.html" --include="*.j2" --include="*.txt" --include="*.css"
```
Expected: zero results. If any line returns, halt and fix before proceeding.

- [ ] **Step 2: Gate 2 — Existing test suite passes unchanged**

```bash
venv/bin/python -m pytest tests/ -v
```
Expected: all 119 tests pass. If any fail, the failure is a regression. Investigate before merging.

- [ ] **Step 3: Gate 3 — Type checking clean**

```bash
venv/bin/pyright
```
Expected: 0 errors.

- [ ] **Step 4: Gate 4 — App boots clean in dev (full smoke)**

```bash
mkdir -p instance/
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050 &
SERVER_PID=$!
sleep 3
for path in / /login /register /auth/forgot-password /auth/profile /admin/ /nonexistent; do
  echo -n "$path → "
  curl -so /dev/null -w "%{http_code}\n" "http://localhost:5050$path"
done
kill $SERVER_PID
```
Expected: `/`, `/login`, `/register`, `/auth/forgot-password` return `200`. `/auth/profile` and `/admin/` return `302` (redirect to login when not authenticated). `/nonexistent` returns `404`.

- [ ] **Step 5: No commit** — verification only.

---

## Task 17: Manual visual checklist + email verification (Spec sections 7b, 7c)

**Files:** none (manual verification)

- [ ] **Step 1: Boot dev server and walk the 12 surfaces**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5050
```

For each surface, verify the items from Spec section 7b. Record pass/fail in the PR description.

| # | Surface | Key checks |
|---|---|---|
| 1 | `/` | CCC chrome, footer voice + utility strips |
| 2 | `/login` | Brand-mark, Teko hero, gold button, "Join the Club" in nav |
| 3 | `/register` | Same chrome |
| 4 | `/auth/forgot-password` | Same chrome; plain copy |
| 5 | `/auth/reset-password/test-token` | Same chrome (will show "invalid token" but chrome correct) |
| 6 | `/auth/change-password` (logged in) | Same chrome |
| 7 | `/auth/profile` (logged in) | Same chrome; "Step Out" in dropdown |
| 8 | `/admin/` (admin user) | "THE COMMISH'S DESK" eyebrow; "the Commish" in nav |
| 9 | `/admin/users` | Title "the Club"; row actions plain |
| 10 | `/admin/enrollments` | Title "Enrollments"; tokens consumed |
| 11 | `/nonexistent-route` | CCC chrome wraps 404; copy plain |
| 12 | Trigger 500 (e.g., visit a route that errors) | Same |

- [ ] **Step 2: Email verification — render password reset locally**

The pre-rendered preview from Task 14 step 4 is at `/tmp/reset_email_preview.html`. If still present, open in browser. Otherwise re-render:

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    from flask import render_template
    html = render_template('email/reset_password_html.j2', reset_url='http://localhost:5050/auth/reset-password/test-token')
    with open('/tmp/reset_email_preview.html', 'w') as f:
        f.write(html)
    print('Rendered to /tmp/reset_email_preview.html')
"
open /tmp/reset_email_preview.html
```
Verify visual aesthetics match the spec (purple band, bone body, gold CTA). For full Gmail/iOS verification, optionally trigger an actual reset email via `/auth/forgot-password` against a configured Gmail address — only do this if you want full client-render fidelity.

- [ ] **Step 3: Cross-browser sanity check**

Open the dev server in:
- Chrome desktop — primary
- Safari iOS (or Chrome dev-tools mobile emulation) — verify mobile collapse, sub-nav scroll, theme-color tint
- Firefox desktop (optional) — verify Teko + Newsreader render

- [ ] **Step 4: No commit** — verification only.

---

## Task 18: Open the PR

**Files:** none (git operation)

- [ ] **Step 1: Push the branch to the remote**

```bash
git push -u origin redesign/ccc-brand
```

- [ ] **Step 2: Open the PR via `gh`**

```bash
gh pr create --title "Spec A — CCC brand foundation + chrome" --body "$(cat <<'EOF'
## Summary

Implements [Spec A](../docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md) — the brand foundation slice of the CCC redesign initiative. Establishes the new token architecture (`tokens.css` + rewired `style.css :root`), restyles platform chrome (navbar, footer, auth pages, system email), runs the naming sweep across 17 files, and updates the CLAUDE.md design-system bullet.

CFB and Golf interior pages and World Cup screens are intentionally untouched (deferred to those games' own redesigns and Spec C respectively).

## Verification

### Automated gates (Spec 7a)
- [ ] Gate 1 — naming sweep returns zero `Commissioner`/`TCC` results
- [ ] Gate 2 — `pytest tests/` 119 tests pass
- [ ] Gate 3 — `pyright` 0 errors
- [ ] Gate 4 — dev server boots, 12 surfaces return expected status

### Manual visual checklist (Spec 7b — 12 surfaces)
- [ ] Surface 1 — `/` (home, pre-Spec B)
- [ ] Surface 2 — `/login`
- [ ] Surface 3 — `/register`
- [ ] Surface 4 — `/auth/forgot-password`
- [ ] Surface 5 — `/auth/reset-password/<token>`
- [ ] Surface 6 — `/auth/change-password`
- [ ] Surface 7 — `/auth/profile`
- [ ] Surface 8 — `/admin/`
- [ ] Surface 9 — `/admin/users`
- [ ] Surface 10 — `/admin/enrollments`
- [ ] Surface 11 — `/nonexistent-route` (404)
- [ ] Surface 12 — triggered 500

### Email verification (Spec 7c)
- [ ] Password-reset HTML email renders correctly (local preview minimum)
- [ ] Plain-text fallback brand string updated

## Post-merge actions
- Run `/claude-md-management:revise-claude-md` to capture session learnings
- `git worktree remove ../fantasy-platform-ccc`
- Branch `redesign/ccc-home` off `main` for Spec B (when ready)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Capture the PR URL** for handoff to Brad / next-step tracking.

```bash
gh pr view --json url --jq .url
```

- [ ] **Step 4: No commit** — PR is the deliverable.

---

## Post-merge follow-ups (NOT in this plan, but next steps after PR merges)

1. Run `/claude-md-management:revise-claude-md` against the merged `main` to capture:
   - CCC brand string in the design-system bullet (already done in Task 15, but the slash-command may add additional captures around the token architecture, voice vocabulary, worktree pattern)
   - The WC navy correction (`#002868` → `#001A4D` per Spec 6e)
2. Worktree cleanup:
   ```bash
   cd ~/fantasy-platform
   git worktree remove ../fantasy-platform-ccc
   ```
3. If proceeding straight into Spec B, in a fresh conversation, brainstorm Spec B per the agreed sequence. Memory file `project_ccc_specs_b_c_notes.md` carries forward the cross-spec design guidance.
