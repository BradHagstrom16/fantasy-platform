# Group B — Feature Enhancements Design Spec

**Date:** 2026-04-11
**Scope:** 6 pre-launch feature enhancements for the fantasy platform

---

## Context

After Group A bug fixes, this batch delivers six player-facing enhancements identified during Brad's end-to-end testing. The work spans platform infrastructure (email consolidation, auth flows) and game-level UX (avatar, World Cup polish). All changes target the main branch for imminent World Cup launch.

---

## Feature 1: Shared Email Utility

**Problem:** Three independent SMTP helpers with duplicated logic, inconsistent From headers (Golf uses "The Commissioner", CFB uses raw email address).

**Solution:** Create `utils/email.py` with a single `send_platform_email(to_addr, subject, plain_body, html_body=None) -> bool` function. All outbound email uses From name "The Commissioner's Club".

**Migration plan (one file at a time):**

| File | Old function | Call sites | Notes |
|------|-------------|------------|-------|
| `games/golf/services/reminders.py` | `send_email()` (line 189) | Lines 337, 530, 679, 1036 | 4 call sites (handoff listed 3; line 530 is admin email to `ADMIN_EMAIL`) |
| `games/cfb/services/reminders.py` | `_send_email()` (line 143) | Lines 400, 542 | 2 call sites |
| `games/cfb/services/automation.py` | `send_admin_email()` (line 34) | Line 437 | Plain-text only; sends to self (`EMAIL_ADDRESS`) |

After migration: delete each old function, remove unused `smtplib`/`MIMEMultipart`/`MIMEText` imports.

**`send_reminders.py`:** Does not exist in the repo. Already superseded by CLI commands. No action needed.

**Files to create:**
- `utils/__init__.py` (empty)
- `utils/email.py`

**Files to modify:**
- `games/golf/services/reminders.py`
- `games/cfb/services/reminders.py`
- `games/cfb/services/automation.py`

---

## Feature 2: Avatar Emoji on User Model

**Schema change:** Add `avatar_emoji = db.Column(db.String(4), nullable=True)` to `models/user.py`.

**Method:** `get_avatar() -> str` returns `self.avatar_emoji or '⚽'`.

**Migration:** `flask db migrate -m "add avatar_emoji to users"` + `flask db upgrade`.

**Files to modify:**
- `models/user.py`

---

## Feature 3: Forgot/Reset Password Flow

**Architecture:** Platform-level auth (no game involvement). Confirmed: all existing auth routes (`/login`, `/register`, `/logout`, `/change-password`, `/profile`) are platform-level with no game model references.

**Token module:** `core/auth/tokens.py`
- `generate_reset_token(email) -> str` — `URLSafeTimedSerializer` with SECRET_KEY, salt `'password-reset'`
- `verify_reset_token(token) -> str | None` — 1-hour expiry, returns email or None

**Routes (no URL prefix — lives at `/forgot-password` and `/reset-password/<token>`):**
- `/forgot-password` (GET/POST) — rate limited 10/min. Anti-enumeration: identical flash message regardless of email existence. On valid email: generate token, send reset email via `send_platform_email`.
- `/reset-password/<token>` (GET/POST) — verify token on both GET and POST. Validate: min 6 chars, passwords match. On success: update password, redirect to login.

**Email templates:**
- `templates/email/reset_password_plain.txt` — plain-text fallback
- `templates/email/reset_password_html.j2` — HTML with platform purple branding, gold CTA button

**Auth page templates** (note: auth templates live at `core/auth/templates/auth/`, not `templates/auth/`):
- `core/auth/templates/auth/forgot_password.html` — extends `base.html`, centered card, email input
- `core/auth/templates/auth/reset_password.html` — extends `base.html`, centered card, new password + confirm

**Files to create:**
- `core/auth/tokens.py`
- `templates/email/reset_password_plain.txt`
- `templates/email/reset_password_html.j2`
- `core/auth/templates/auth/forgot_password.html`
- `core/auth/templates/auth/reset_password.html`

**Files to modify:**
- `core/auth/routes.py` — add 2 routes, new imports

---

## Feature 4: Wire Forgot Password into Login

**Current state:** Login template already has "Forgot your password?" link (lines 61-65) that opens a modal (lines 81-100) saying "contact the commissioner."

**Change:** Replace the modal-trigger `<a>` with a plain link to `url_for('auth.forgot_password')`. Delete the entire `#forgotModal` div.

**Files to modify:**
- `core/auth/templates/auth/login.html`

---

## Feature 5: Emoji Avatar Picker + Standings Integration

**Picker (profile page):**
- Define `AVATAR_CHOICES` list (~20 emoji) in `core/auth/routes.py`
- Pass to profile template; validate selection in POST handler
- Template: responsive grid of clickable emoji buttons with visual selection state (CSS highlight on active)
- Replace the existing first-letter avatar circle with `get_avatar()` display

**Standings integration — add `{{ user.get_avatar() }}` before display name in:**
- Golf: `games/golf/templates/golf/index.html` (line 114) — `{{ u.user.get_avatar() }}`
- CFB: `games/cfb/templates/cfb/index.html` (line 221) — `{{ enrollment.user.get_avatar() }}`
- WC Leaderboard: `games/worldcup/templates/worldcup/leaderboard.html` (lines 36, 59) — `{{ e.user.get_avatar() }}`
- WC Player Detail: `games/worldcup/templates/worldcup/player_detail.html` — `{{ enrollment.user.get_avatar() }}`

**Files to modify:**
- `core/auth/routes.py` — `AVATAR_CHOICES` list, profile POST handler update
- `core/auth/templates/auth/profile.html` — emoji picker UI, avatar display
- `games/golf/templates/golf/index.html`
- `games/cfb/templates/cfb/index.html`
- `games/worldcup/templates/worldcup/leaderboard.html`
- `games/worldcup/templates/worldcup/player_detail.html`

---

## Feature 6: World Cup UX Improvements

### 6a: My Roster Widget on Index

**Model:** Add `@property flag_emoji` to `WorldCupTeam` in `games/worldcup/models.py`. Uses FIFA-to-ISO alpha-2 lookup for ~15 exceptions (GER→DE, SUI→CH, etc.), derives Unicode regional indicator symbols.

**Route:** In WC index route, when `enrollment.picks_submitted`, query picks with joined teams. Pass `user_picks` to template.

**Template:** Compact "My Roster" card after the "You're All Set" section, grouped by tier: flag emoji + FIFA code per pick.

### 6b: Non-Enrolled Dual CTA

Add "See How It Works" secondary button alongside "Join the Pool" on WC index for non-enrolled users. Links to `url_for('worldcup.rules')`.

### 6c: Scoring Rules Link on Picks Page

Small "View Scoring Rules" link in the picks page hero area, visible in both read-only and edit states.

### 6d: Leaderboard Self-Link

Current user's row links to `/worldcup/picks` instead of `player_detail`. Other users' rows stay linked to `player_detail`. Applies to both desktop table and mobile cards.

**Files to modify:**
- `games/worldcup/models.py` — `flag_emoji` property
- `games/worldcup/routes.py` — picks query in index route
- `games/worldcup/templates/worldcup/index.html` — roster widget + dual CTA
- `games/worldcup/templates/worldcup/picks.html` — scoring rules link
- `games/worldcup/templates/worldcup/leaderboard.html` — self-link logic

---

## Build Order

Sequential, following dependency chain:

1. Create `utils/email.py` (Feature 1)
2. Migrate golf email call sites
3. Migrate CFB email call sites
4. Add `avatar_emoji` column + migration (Feature 2)
5. Create `core/auth/tokens.py` (Feature 3)
6. Create email templates for password reset
7. Create auth page templates (forgot + reset)
8. Add forgot/reset routes to `core/auth/routes.py`
9. Wire forgot password link into login (Feature 4)
10. Add emoji picker to profile + route handler (Feature 5)
11. Wire avatar into all game standings
12. Add `flag_emoji` property to WorldCupTeam (Feature 6a)
13. Add roster widget to WC index
14. Add non-enrolled dual CTA (Feature 6b)
15. Add scoring rules link on picks page (Feature 6c)
16. Add leaderboard self-link (Feature 6d)

---

## CLAUDE.md Updates Required

After implementation:
- Document `utils/email.py` as canonical email helper
- Add avatar convention: "All game standings must display `user.get_avatar()` inline before the player display name"
- Add `utils/` to project structure

## ADR Updates Required

- ADR-029: Emoji avatar — nullable String(4) on User, default ⚽, all games must display
- ADR-016 fulfilled: Email consolidation via `utils/email.py`

---

## Verification

1. Smoke test script (all routes return expected status codes)
2. `pyright` — 0 errors on all modified `.py` files
3. `pytest tests/` — full suite passes
4. `flask db upgrade` and `flask db downgrade` both succeed
5. Playwright verification of all UI changes
