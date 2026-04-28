# Spec A — CCC Brand Foundation + Chrome

**Date:** 2026-04-28
**Status:** Approved
**Initiative:** CCC Redesign (Specs A → B → C)
**Predecessors:** none — first slice
**Successors:** Spec B (home redesign), Spec C (World Cup reskin)
**Branch:** `redesign/ccc-brand` (worktree at `../fantasy-platform-ccc`)
**Source design bundle:** `fantasy-platform-and-world-cup-design/` (Claude Design handoff, untracked)

---

## 1. Context & decomposition

The Claude Design handoff bundle proposed a wholesale brand and UI redesign of the platform under a new identity, **Corrupt Commish Club (CCC)**, replacing the current "The Commissioner's Club" branding. The bundle covers brand identity, home page (4 states), and 12 World Cup mobile screens.

The bundle is too large for a single spec because it conflates four distinct projects:

1. **Brand rebrand** — name, logo, palette, typography (highest blast radius; touches every page and email)
2. **Home page redesign** — 4 states (pre-deadline, live, logged-out, desktop-live)
3. **World Cup UI overhaul** — reskin of existing routes (Pick / Tiebreak / Sealed / Roster / Team / Leaderboard / Player / Stats)
4. **Net-new World Cup features** — live match scoreboard with timeline + xG (`wc-match.jsx`), Tribune (news/dispatches) — these are not redesigns, they are features. Match needs a sports-data API; Tribune needs a content pipeline.

**Agreed decomposition:**

- **Spec A (this document)** — Brand foundation + brand chrome (tokens, logo, naming sweep, base.html chrome, auth pages restyle, system email restyle)
- **Spec B (next)** — Home page redesign on the new foundation (4 states)
- **Spec C** — World Cup reskin of existing routes only
- **Deferred to future brainstorms** — Match (live data API) + Tribune (content pipeline)

**Internal contradictions in the design bundle, resolved here:**

- `NEXT_STEPS.md` line 62 says *"A 'Crown' persona — the founder is 'the Commish.' 'Crown' was an earlier draft; do not reintroduce."* But `wc-pick.jsx` line 6 still says `kicker: "The Crown's chosen"` and line 133 says `"The Crown's Assignment · World Cup 2026"`. **Canonical:** Commish. Spec C will scrub Crown references when those screens get implemented.

**Pre-existing production state matters for scoping:**

- Typography (Teko + Newsreader) is already loaded in `base.html` line 12. **No font swap required.**
- The platform's current primary purple (`#3A1D72`) is the same hex as the design's `--purple-700`. **The visual delta is much smaller than the brand story implies.** Spec A is mostly *formalizing* the existing palette into a layered token system, plus adding the gold family, the bone surface family, the metal-gold gradient, and WC scoped tokens for Spec C.
- No game is live to real users yet (as of 2026-04-28). This gives broad freedom to make incompatible chrome changes — CFB and Golf interiors temporarily look one generation behind during the A → B → C window with no user impact.

---

## 2. Approved design decisions

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Rename scope | **D — Full platform rename** including domain/positioning. Pre-launch, so flexibility exists. CCC replaces "Commissioner's Club" everywhere user-facing, email from-name, eventual domain. Repo name stays `fantasy-platform`. | The design bundle assumes total rebrand; Brad has runway to commit fully before launch. |
| D2 | Per-event palette policy | **A — Keep per-event palettes.** CFB (crimson/midnight) and Golf (Augusta green/gold) untouched in this initiative; each gets its own per-palette redesign before its launch. WC's distinct navy/red/cream is the *pattern*, not an exception. | Respects existing `body.game-<game>` scoping and the design bundle's own "WC has its own palette" principle. |
| D3 | Spec A scope | **B — Foundation + brand chrome.** Spec A includes new tokens, logo, favicon, naming sweep, `base.html` chrome (nav/footer), auth pages restyled, email templates restyled. CFB/Golf interior pages stay visually as-is. | (A) leaves dead/unintegrated code; (C) violates decomposition. (B) is the right shape — visible rebrand of platform chrome, game interiors deferred. |
| D4 | Voice doctrine | **B — Moderate.** Voice for ritual & celebration, plain for utility. Auth, errors, validation, system email body copy, settings — all plain English. Voice vocabulary explicitly enumerated in Section 5h. | Matches design bundle's own `NEXT_STEPS.md` recommendation: *"Auth and errors should step out of the ceremonial voice."* |
| D5 | Implementation approach | **A3 — Worktree + single PR.** `git worktree add ../fantasy-platform-ccc -b redesign/ccc-brand main`. One PR for the full Spec A scope. | Pre-launch but production deploy plumbing is real; worktree isolates redesign work from any potential `main` hotfix. Spec A is bounded enough for one PR. |
| D6 | Logo flexibility | Use design bundle's existing PNG, resized for web. SVG conversion deferred until logo finalizes — chrome references file path, so swap is one file with zero template edits. | Logo asset isn't final; the chrome only references a path. |
| D7 | Domain strategy | No placeholder domain in copy. Footer reads `© 2026 Corrupt Commish Club` (no URL). Email signatures use `{{ config.SITE_URL }}` (already env-driven). Domain commit is one-line env change in production when finalized. | Maximum flexibility; zero code rework when domain lands. |
| D8 | `COMMISSIONER_NAME` env var | **A — Default-only change.** Env var key stays `COMMISSIONER_NAME`. Default value flips from `"The Commissioner"` to `"The Commish"`. No env touches required at deploy. | Cosmetic gain isn't worth env rename friction. |
| D9 | CLAUDE.md update timing | After Spec A merges → run `/claude-md-management:revise-claude-md` (lighter, captures session learnings). After Spec C merges → run `/claude-md-management:claude-md-improver` (heavier audit, restructures sections). | Two tools at two cadences match the drift profile. |

---

## 3. Architecture & file layout

### 3a. Files added

```
static/
├── img/
│   ├── ccc-logo.png              (new, 600×200 wordmark+mark, ≤60 KB)
│   ├── ccc-logo-mark.png         (new, 240×240 mark, ≤30 KB; used in nav, auth, email)
│   ├── favicon.ico               (new, multi-res 16/32/48, ≤8 KB)
│   └── favicon-180.png           (new, 180×180 apple-touch-icon, ≤12 KB)
└── css/
    └── tokens.css                (new — CCC house tokens; loaded BEFORE style.css in base.html)
```

The design bundle's `tokens.css` (purple-950 → purple-400, gold family, bone, metal-gold gradient, font tokens, WC scoped tokens) is adopted **verbatim** as `static/css/tokens.css`. WC scoped tokens (`--wc-navy`, `--wc-red`, `--wc-white`) are inert in Spec A — they only activate when Spec C adds a `body.game-worldcup { ... }` block consuming them.

### 3b. Files modified

| File | Change scope |
|---|---|
| `static/css/style.css` | Rewire `:root` block (lines 7–61) to consume new CCC tokens via aliases. Add `.brand-mark` and `.brand-mark--lg` classes. Top-of-file comment updated. Game-scoped sections (Golf, CFB) **not touched**. |
| `templates/base.html` | Title block, navbar brand mark + brand text + game switcher styling, footer (full rewrite into voice + utility strips), `<head>` favicon + theme-color additions, tokens.css `<link>`. |
| `templates/email/reset_password_html.j2` | Restyle: CCC purple header band, bone body card, gold-gradient CTA, brand text update. |
| `templates/email/reset_password_plain.txt` | Brand text update only. |
| `templates/errors/404.html`, `templates/errors/500.html` | Title block update. |
| 6 auth templates under `core/auth/templates/auth/` | Brand-mark swap, hero typography Teko, form input restyle, primary button gold gradient, page bg purple-950 with vignette. Plain copy throughout (Doctrine B). |
| 3 admin templates under `core/admin/templates/admin/` | Page header eyebrow + title treatment, voice vocabulary applied per Section 5h. Internal table/row actions stay plain. |
| `core/main/templates/main/index.html` | Title + hero eyebrow string update only (Spec B replaces this template wholesale). |
| `utils/email.py` | `PLATFORM_FROM_NAME` constant + docstring updated. |
| `core/auth/routes.py` | Password-reset email subject string updated. |
| `games/golf/services/reminders.py` | Brand text in email footer + `COMMISSIONER_NAME` default value. Email body content untouched. |
| `games/cfb/services/reminders.py` | Brand text in email footer. Email body content untouched. |
| `CLAUDE.md` | One targeted edit only: design-system bullet brand string. Bulk left for post-Spec A revise pass. |

### 3c. What is NOT touched in Spec A

- Anything under `games/golf/` or `games/cfb/` outside the email-chrome string updates above.
- `games/worldcup/templates/worldcup/` — Spec C territory (sub-nav block in `base.html` left structurally intact for now).
- `ARCHITECTURE_DECISION_LOG.md` and historical specs/plans in `docs/superpowers/` — period-correct, not retroactively edited.
- Bootstrap version (5.3 stays).
- Any `.py` outside the four files listed above.
- Any tests (no new tests added; no existing tests modified).

### 3d. Worktree setup

```bash
git worktree add ../fantasy-platform-ccc -b redesign/ccc-brand main
cd ../fantasy-platform-ccc
```

All Spec A code work happens in the worktree. The `main` checkout in `~/fantasy-platform` stays available for any production hotfix.

---

## 4. Brand chrome (nav, footer, the universals)

### 4a. Where we follow the design

CCC monogram + crown brand mark, deep purple primary, gold accent, bone surface family, Teko display + Newsreader voice copy.

### 4b. Where we **diverge** from the design (with reasoning)

| Diverge from | Why |
|---|---|
| Bottom tab bar (`shared.jsx`'s `TabBar` with Desk/Picks/Board/Court) | Single-event mobile-app nav. We are multi-game responsive web. Top navbar with game switcher + per-game sub-nav is the right shape. |
| Search icon + notification bell in `AppBar` | No backend support for either. They'd be dead buttons. Cut. |
| Fixed mobile app shell | Responsive web; Bootstrap navbar collapses to hamburger on mobile, like today. |

### 4c. Top nav — exact changes to `templates/base.html`

| Before | After |
|---|---|
| `<i class="bi bi-trophy-fill">` | `<img src="{{ url_for('static', filename='img/ccc-logo-mark.png') }}" class="brand-mark" alt="">` |
| "The Commissioner's Club" / "TCC" | "Corrupt Commish Club" / "CCC" |
| Bootstrap navbar-dark default | CCC purple-700 bg, gold-on-hover, gold underline on active |
| Game switcher (Golf | CFB | WC) | Unchanged structure, restyled (Teko all-caps, .08em letter-spacing) |
| "Admin" link with gear icon | "the Commish" with gear icon (display only; route stays `/admin`) |
| "Login" / "Join Now" buttons | "Sign In" / "Join the Club" |
| User dropdown: "Profile / Change Password / Logout" | "Profile" / "Change Password" stay plain; **"Logout" → "Step Out"** |
| Compact-on-scroll JS (lines 191–211) | Preserved as-is |

### 4d. Sub-nav — minimal changes

`.game-subnav` block stays. Only the platform-level pill/active states are restyled to consume CCC tokens. Spec C will rewrite `subnav-worldcup` content; Spec A leaves it structurally intact.

### 4e. Footer — full rewrite

Two stripes:

1. **Voice strip** (full-width band, `var(--purple-800)` bg, Newsreader italic, gold dot accents, single line):
   > *"An exclusive members' club. The Commish keeps the ledger. The Club keeps the code. The losers keep the tab."*
2. **Utility strip** (smaller, muted bone): `© 2026 Corrupt Commish Club · Built for the Club, by the Commish` — no domain, no nav links, no social.

### 4f. Auth pages chrome wrapper

Auth pages extend `base.html` and inherit the new nav/footer. Page-internal restyle covered in Section 5.

### 4g. Admin pages chrome wrapper

Same — admin pages live under standard nav. Admin nav link displays as "the Commish"; admin page headers can use Commish voice ("the Commish's Desk", "the Club") without affecting URL or `is_admin` API.

### 4h. Mobile behavior

- Navbar collapses to hamburger; brand mark stays visible
- Sub-nav scrolls horizontally as today (existing JS in base.html lines 213–224)
- Footer stays full-width, voice strip wraps if needed

---

## 5. Naming sweep + visual restyle

### 5a. Naming sweep — Layer 1: User-facing brand strings (14 files)

Mechanical find-and-replace:

| File | Lines | Replace |
|---|---|---|
| `templates/base.html` | 7, 30, 31, 183 | title, brand-text x2, footer copyright |
| `templates/errors/404.html` | 2 | title |
| `templates/errors/500.html` | 2 | title |
| `templates/email/reset_password_html.j2` | 17, 54 | brand header + footer attribution |
| `templates/email/reset_password_plain.txt` | 3, 12 | body reference + sign-off |
| `core/auth/templates/auth/login.html` | 3, 10, 12 | title + brand-logo + hero copy |
| `core/auth/templates/auth/register.html` | 3, 10 | title + brand-logo |
| `core/auth/templates/auth/forgot_password.html` | 3, 10 | title + brand-logo |
| `core/auth/templates/auth/reset_password.html` | 3, 10 | title + brand-logo |
| `core/auth/templates/auth/change_password.html` | 3 | title |
| `core/auth/templates/auth/profile.html` | 3 | title |
| `core/admin/templates/admin/dashboard.html` | 3 | title |
| `core/admin/templates/admin/users.html` | 3 | title |
| `core/main/templates/main/index.html` | 3, 9 | title + hero eyebrow |

Replacement rules:

- `The Commissioner's Club` → `Corrupt Commish Club`
- `The Commissioner&#8217;s Club` (HTML-encoded) → `Corrupt Commish Club`
- `TCC` (mobile compact) → `CCC`
- `<i class="bi bi-trophy-fill">` paired with brand text → `<img src="{{ url_for('static', filename='img/ccc-logo-mark.png') }}" class="brand-mark" alt="">`

### 5b. Naming sweep — Layer 2: Code/config strings (3 files)

| File | Line | Change |
|---|---|---|
| `utils/email.py` | 9, 20 | `PLATFORM_FROM_NAME = "Corrupt Commish Club"` + matching docstring |
| `core/auth/routes.py` | 124 | password-reset subject: `"Reset your password — Corrupt Commish Club"` |
| `static/css/style.css` | 2 | top-of-file comment header |

### 5c. Naming sweep — Layer 3: Game reminder emails (chrome only, not content)

| File | Line | Change |
|---|---|---|
| `games/golf/services/reminders.py` | 120 | brand link text in email footer |
| `games/golf/services/reminders.py` | 215, 509, 920 | `COMMISSIONER_NAME` default value: `"The Commissioner"` → `"The Commish"` (per D8) |
| `games/cfb/services/reminders.py` | 100 | brand link text in email footer |

The Golf/CFB reminder *body content* is untouched. Visual restyle of these emails waits for those games' own per-palette redesigns.

### 5d. Auth page restyle (visual; copy stays plain per D4)

- Brand mark in `.brand-logo` — Bootstrap trophy swapped for `<img class="brand-mark brand-mark--lg">`
- Hero typography — Teko display, all-caps, `.04em` letter-spacing; Newsreader subhead
- Form inputs — bg `var(--bone)`, border `var(--purple-700)` 18% alpha, focus ring `var(--gold)` 60% alpha
- Primary button — `var(--metal-gold-flat)` gradient, dark purple text, hover `transform: translateY(-1px)` + shadow
- Page background — `var(--purple-950)` with subtle radial-gradient vignette toward center (purple-900 → purple-950)
- Alert overrides — `.alert-danger` / `.alert-success` use `var(--danger-bg)` / `var(--success-bg)` against bone surface

What stays: form structure, CSRF token, all Flask-WTF validation messages, brand-name text in hero (just restyled, not removed).

### 5e. System email restyle (`reset_password_html.j2`)

- Header band: `var(--purple-800)` bg, brand-mark + "Corrupt Commish Club" wordmark in Teko gold (text + inline color, no image)
- Body card: bone bg, dark text, Newsreader serif body
- CTA button: gold gradient, dark purple text, ~14px padding, rounded
- Footer: muted bone text, no domain, brand only
- All inline styles (no `<style>` block) for Gmail compat
- Plain-text fallback: brand string update only

Voice doctrine for system emails: **plain.**

### 5f. Game reminder email visual — TEXT ONLY in Spec A

`games/golf/services/reminders.py` and `games/cfb/services/reminders.py` get **only** the brand-text update from Section 5c. Visual restyle of these emails is deferred to those games' own per-palette redesigns. CCC purple header on green body would be visually broken.

### 5g. Admin page restyle (3 templates)

- Page header treatment: Teko/Newsreader stack
  - Eyebrow (small, gold, all-caps Teko)
  - Title (large, bone-cream, Teko)
- Display labels per voice vocabulary table (Section 5h):
  - Admin → "the Commish" (nav + page eyebrow `THE COMMISH'S DESK`)
  - User Management → "the Club" (page title)
  - Enrollments → "Enrollments" (kept plain)
- Tables, forms, buttons consume new tokens via `style.css` overrides (no structural HTML change)
- Row actions ("Edit", "Delete", "Save") **stay plain**

### 5h. Voice vocabulary table — canonical for Spec A

| Voice term | Where it appears in Spec A | Replaces | Lives plain |
|---|---|---|---|
| **Corrupt Commish Club** / **CCC** | Brand name everywhere | The Commissioner's Club / TCC | — |
| **the Commish** | Admin nav link; admin page eyebrow ("THE COMMISH'S DESK"); footer voice strip | "Admin" (display only) | `is_admin` API, route `/admin`, code identifiers |
| **the Club** | Admin users page title; footer voice strip; "Join the Club" auth nav button | "Users" / "Members" / "Join Now" (display only) | `User` model, code identifiers, form labels |
| **the Ledger** | Footer voice strip; reserved for activity/history surfaces in Spec C | — (Spec A: no replacements yet) | — |
| **Step Out** | User dropdown logout link | "Logout" | `auth.logout` route, code identifier |
| **Sign In** | Auth nav button | "Login" | route `/login` |

Spec C will extend with WC-specific voice (Oath, Seal, Roster, etc.). Spec A locks only platform-level terms.

What is **explicitly plain** in Spec A:

- All form field labels (Email, Password, Display Name, etc.)
- All form validation/error/success messages
- All flash messages from `auth.routes`
- All system email subject lines and body copy
- All error page copy (404/500)
- All admin row action buttons (Edit, Delete, Save)
- All settings/profile page copy
- The word "Profile" in the user dropdown

---

## 6. Logo, assets, and the token integration layer

### 6a. Logo asset prep

| File | Dimensions | Approx size | Usage |
|---|---|---|---|
| `static/img/ccc-logo-mark.png` | 240×240 (displayed at 120×120 max) | ≤ 30 KB | Top nav, auth `.brand-logo`, email header (inline) |
| `static/img/ccc-logo.png` | 600×200 wordmark + mark | ≤ 60 KB | Reserved for Spec B home hero (shipped early) |
| `static/img/favicon.ico` | multi-res 16/32/48 | ≤ 8 KB | Legacy + most desktop browsers |
| `static/img/favicon-180.png` | 180×180 | ≤ 12 KB | iOS / Android shortcut |

Generated from `fantasy-platform-and-world-cup-design/project/assets/ccc-logo-transparent.png`. Tool of choice (ImageMagick or equivalent).

CSS additions to `style.css`:

```css
.brand-mark { width: 28px; height: 28px; vertical-align: -.35em; margin-right: .5rem; }
.brand-mark--lg { width: 56px; height: 56px; }   /* auth page heroes */
```

### 6b. Favicon `<head>` block in `base.html`

```html
<link rel="icon" href="{{ url_for('static', filename='img/favicon.ico') }}" sizes="any">
<link rel="apple-touch-icon" href="{{ url_for('static', filename='img/favicon-180.png') }}">
<meta name="theme-color" content="#3A1D72">
```

### 6c. Token integration — four-layer stack

```
Layer 1: tokens.css                                  ← NEW FILE
   ├── CCC house tokens (purple-950..400, gold-dark..hi, bone family)
   ├── --metal-gold and --metal-gold-flat gradients
   ├── --live-red, --live-green semantic
   ├── WC scoped tokens (--wc-navy, --wc-red, --wc-white) — inert until Spec C
   └── --font-teko, --font-news family vars

Layer 2: style.css :root (REWRITTEN)
   ├── --platform-primary: var(--purple-700)         (alias, same color)
   ├── --platform-accent: var(--gold)                (refined from old #D4A820)
   ├── --bg-page: var(--bone)                        (#F5F3F0 → #F3EFE6, hair difference)
   ├── --bg-card: white (unchanged)
   ├── --text-primary, --text-secondary (unchanged)
   ├── --success, --danger, etc. (unchanged)
   └── --game-* slot vars (unchanged)

Layer 3: style.css body.game-* (UNCHANGED)
   └── Golf and CFB overrides — same hex values, same scoping

Layer 4: Components (UNCHANGED behavior)
   └── Consume Layer 2 vars; pick up new colors transparently
```

### 6d. Load order in `base.html` `<head>`

```html
<!-- CCC tokens — must load before style.css so style.css can consume them -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/tokens.css') }}">
<!-- Bootstrap 5.3 CSS -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<!-- Bootstrap Icons -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<!-- Platform CSS -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
```

### 6e. WC scoped tokens defined here, activated in Spec C

`tokens.css` includes `--wc-navy: #001A4D; --wc-red: #BF0A30; --wc-white: #F5F1E8;` — inert in Spec A. Spec C wires them via `body.game-worldcup { --game-primary: var(--wc-navy); ... }` in `style.css`.

Note: production currently has WC palette in CLAUDE.md as `Old Glory blue #002868 + red #BF0A30`. We adopt the design's deeper navy (`#001A4D`) and update CLAUDE.md in the post-Spec A revise pass.

### 6f. Bootstrap 5.3 stays — no upgrade, no replacement

CCC theming sits as token-driven overrides in `style.css`. Replacing Bootstrap is out of scope and out of need.

---

## 7. Verification & exit criteria

### 7a. Automated gates (must pass before merge)

**Gate 1 — Naming sweep complete:**
```bash
grep -rn "Commissioner\|TCC\b" templates/ core/ utils/ static/css/ \
  games/golf/services/reminders.py games/cfb/services/reminders.py
```
Expected: zero results. Excludes `docs/` and `ARCHITECTURE_DECISION_LOG.md` per D2 reasoning (period-correct historical records).

**Gate 2 — Existing test suite passes unchanged:**
```bash
venv/bin/python -m pytest tests/
```
Expected: all 119 tests pass. Spec A doesn't add, remove, or modify tests.

**Gate 3 — Type checking clean:**
```bash
venv/bin/pyright
```
Expected: 0 errors.

**Gate 4 — App boots clean in dev:**
```bash
cd ../fantasy-platform-ccc
mkdir -p instance/
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run
```
Expected: every page returns 200, brand mark visible in nav, footer voice strip visible, no console errors.

### 7b. Manual visual checklist (12 surfaces)

Implementer marks pass/fail on each in the PR description.

| # | Surface | What to verify |
|---|---|---|
| 1 | `/` (home, pre-Spec B) | Title says CCC; nav shows logo mark + brand text; footer voice + utility strips render |
| 2 | `/login` | CCC brand-mark, Teko hero, gold-gradient primary button, "Join the Club" link in nav |
| 3 | `/register` | Same chrome; form styling consistent |
| 4 | `/auth/forgot-password` | Same chrome; plain copy |
| 5 | `/auth/reset-password/<token>` | Same chrome; plain copy |
| 6 | `/auth/change-password` (logged in) | Same chrome; plain copy |
| 7 | `/auth/profile` | Same chrome; plain copy; user dropdown shows "Step Out" |
| 8 | `/admin/` | Eyebrow "THE COMMISH'S DESK"; admin nav link "the Commish" |
| 9 | `/admin/users` | Page title "the Club"; row actions plain |
| 10 | `/admin/enrollments` | Page title "Enrollments" (kept plain); table tokens consumed |
| 11 | `/nonexistent-route` | CCC chrome wraps 404; copy plain |
| 12 | Trigger 500 in dev | Same |

### 7c. Email verification (manual)

1. Trigger `/auth/forgot-password` against a real Gmail account; receive and inspect in Gmail web, Gmail mobile, Apple Mail (iOS).
2. Verify: header band CCC purple, brand wordmark Teko gold, body bone surface, gold CTA button, plain-text fallback renders.
3. Trigger a Golf reminder via the appropriate `flask golf sync-run` mode; verify the brand text in the footer changed and nothing else.

Alternative: render `reset_password_html.j2` to a local file via Flask shell and open in browser.

### 7d. Cross-browser sanity check

- Chrome desktop (primary)
- Safari iOS (mobile collapse, sub-nav horizontal scroll, theme-color tint)
- Firefox desktop (Teko + Newsreader rendering)

### 7e. Post-Spec A actions

After Spec A's PR merges to `main`:

1. Run `/claude-md-management:revise-claude-md`. Expected captured updates:
   - Brand string in CLAUDE.md design-system bullet → "Corrupt Commish Club"
   - Add "CCC token architecture" line: `tokens.css → style.css :root → body.game-* → components`
   - Add voice vocabulary table or pointer to this spec doc
   - WC palette correction: `Old Glory blue #002868` → `--wc-navy #001A4D`
   - Note the worktree pattern as the redesign workflow
2. Worktree cleanup:
   ```bash
   cd ~/fantasy-platform
   git worktree remove ../fantasy-platform-ccc
   ```
3. If proceeding straight to Spec B, branch `redesign/ccc-home` off `main` (Spec A is now merged).

### 7f. Out-of-scope verification

- No Lighthouse score targets (perf audit deferred).
- No formal a11y audit (color contrast spot-checks in 7b are a soft check, not a hard gate).
- No load test (pre-launch).
- No production smoke test as part of Spec A merge — production deploy is a separate operation per CLAUDE.md.

---

## 8. Risks & open items at spec close

| Risk | Mitigation |
|---|---|
| Spec B / Spec C reveal a token gap not covered by `tokens.css` | Add tokens to `tokens.css` in those specs as needed; Layer 1 is extensible. |
| Color contrast (gold-on-purple) fails WCAG AA in some surface | Spot-check during 7b. If a specific pairing fails, swap to `--gold-light` for that surface. |
| Gmail clients render the restyled email differently than expected | Verify in Gmail web + mobile during 7c; iterate on inline styles if needed. |
| `--bone` (#F3EFE6) vs current `--bg-page` (#F5F3F0) shift causes visual regression in some component | Hair-difference shift; expected to be invisible. If a component looks wrong, swap that component's bg to `var(--bg-card)` or hardcoded value. |
| The `<title>` block change in `core/main/templates/main/index.html` conflicts with Spec B's wholesale template replacement | Spec B's plan will note that Spec A's title block is the canonical brand string and will be preserved during template replacement. |

No open items requiring resolution before implementation begins.

---

## 9. Appendix: Brainstorming process record

Decisions made during brainstorming on 2026-04-27 (carried to 2026-04-28 for spec write):

- D1 (rename scope) — option D, full platform rename including domain
- D2 (palettes) — option A, per-event palettes preserved
- D3 (Spec A scope) — option B, foundation + chrome
- D4 (voice doctrine) — option B, ritual yes / utility no
- D5 (implementation approach) — option A3, worktree + single PR
- D6 (logo) — flexible, deferred SVG
- D7 (domain) — flexible, no placeholder in copy
- D8 (`COMMISSIONER_NAME`) — option A, default-only change
- D9 (CLAUDE.md) — revise-claude-md after A, claude-md-improver after C
- Footer voice line approved verbatim with one typo fix ("memebers'" → "members'")
- "Step Out" approved for logout
