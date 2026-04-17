# Human End-to-End Test Script
## Fantasy Platform — World Cup Launch Readiness

**Date:** April 11, 2026  
**Tester:** Brad  
**Focus:** Registration/auth flows + World Cup Fantasy Pool (primary); Golf + CFB regression (secondary)  
**Estimated time:** 45–60 minutes  


Open: `http://127.0.0.1:5000`

## Still Needs Work

- Should a games top toolbar (the pill-link subnav strip) be sticky/frozen so it always shows no matter how far the user has scrolled, both on mobile and web? I think there is room for improvement on this, it works but could be more aestetically pleasing and work a little better.

---

## Completed Enhancements (shipped)

- ✅ Flags on pick form, schedule, group standings, pick summary sidebar, and player detail — Group C1
- ✅ World Cup is now prominently featured on homepage (hero card) and login page — Group C1
- ✅ Removed redundant "Base" column from rules scoring matrix — Group C1
- ✅ Emoji avatar system: profile picker + displayed in all game standings — Group B
- ✅ Forgot/reset password flow with anti-enumeration pattern — Group B
- ✅ "See How It Works" CTA for non-enrolled users on the WC index — Group B
- ✅ "See full rules and scoring" link visible on the pick submission form — Group B
- ✅ Leaderboard: logged-in user's own row links to their picks — Group B
- ✅ My Roster widget on WC main page showing your 9 picks at a glance — Group B
- ✅ Other players' picks are hidden until tournament deadline (privacy enforced server-side) — commit 02599f3
- ✅ Mobile subnav reworked: scroll indicator, pill overflow, mobile-first layout overhaul — Group C2
- ✅ Edit Picks button now uses btn-game with full contrast — Group C1
- ✅ Confederation labels (CAF, UEFA, AFC, etc.) hidden from pick form — Group C1
- ✅ Group letter shown on pick summary sidebar and player detail view — Group C1
- ✅ Picks page shows read-only summary with an "Edit My Picks" button when picks already submitted — commit 02599f3


---

## How to Use This Script

- Work through sections in order — later sections depend on earlier ones
- Mark each item ✅ (pass), ❌ (fail), or ⚠️ (unexpected but not blocking)
- When something fails, note what you saw in the "Notes" space
- **Stop and fix blockers before continuing** — items marked 🔴 are go/no-go for launch

---

## Section 1: Pre-Flight (2 min)

Quick sanity check before you test anything user-facing.

```bash
# In a separate terminal — verify data is in the DB
FLASK_APP=app.py venv/bin/flask worldcup status
```

- [x] `flask worldcup status` prints: 48 teams, 104 matches, 0 completed, 0 enrolled
- [x] Homepage (`/`) loads without errors
- [x] Games dropdown in nav shows: Golf Pick 'Em, CFB Survivor, World Cup Fantasy
- [x] No 500 errors in the Flask console on any of those page loads

---

## Section 2: Registration Flow 🔴

> This is the most important flow to test. New users arriving from your invite link must be able to register without friction.

### 2A: New user registration — happy path

Open a fresh incognito window (so you start with no session).

- [x] Navigate to `/register`
- [x] Page renders correctly — form has: username, email, password, confirm password
- [x] Fill in valid details (use a test email like `testplayer1@test.com`, username `testplayer1`, strong password)
- [x] Submit — should redirect to the platform home page or a welcome page **without** requiring you to log in again
- [x] Your username appears in the nav (confirming you're logged in as `testplayer1`)
- [x] No error flash messages visible

**Notes:**

---

### 2B: Registration validation — error states

Still in incognito. Log out first if you're still logged in.

- [x] Try registering with a **duplicate username** (use `testplayer1` again) — should show an inline error, not a 500
- [x] Try registering with a **duplicate email** (use `testplayer1@test.com` again) — should show an inline error
- [x] Try submitting with **mismatched passwords** — should show an inline error
- [x] Try submitting with an **empty form** — should show required field errors, not a 500
- [x] In all error cases: the form **repopulates** whatever you typed (you shouldn't lose your username/email)

**Notes:**

---

### 2C: Login / logout

- [x] Log out from `testplayer1` — nav updates, you're no longer logged in
- [x] Navigate to a protected page (e.g., `/worldcup/picks`) — should redirect to `/login` with a flash message
- [x] After redirect: the login form shows (not a 500)
- [x] Log back in as `testplayer1` — should redirect back to `/worldcup/picks` (the `next` param should work)
- [x] Confirm you're logged in (username in nav)
- [x] Log out again

**Notes: Fixed in commit 02599f3 — login POST now reads `next` from a hidden form field so the redirect survives the GET→POST round-trip.**

---

### 2D: Login validation — error states

- [x] Try logging in with a **wrong password** — should show "Invalid credentials" or similar, not a 500
- [x] Try logging in with a **non-existent username** — same behavior as wrong password (no user enumeration)
- [x] Try submitting the **empty login form** — should show validation error, not a 500

**Notes:**

---

### 2E: Profile + change password

Log back in as `testplayer1`.

- [x] Navigate to `/profile` — page loads, shows your username and email
- [x] Navigate to `/change-password` — form renders with: current password, new password, confirm new password fields
- [x] Submit with **wrong current password** — should show an error, not a 500
- [x] Submit a valid password change — should succeed and confirm it worked
- [x] Log out, then log back in with the **new password** — should work
- [x] Change the password back to the original for cleanliness (optional)

**Notes:**

---

## Section 3: World Cup — Enrollment 🔴

> In a real launch scenario this is the second thing a player does after registering. It must be frictionless.

Log in as `testplayer1` (or your main admin account — whichever you prefer for this first pass).

### 3A: Join page

- [x] Navigate to `/worldcup/join` (or click the World Cup link in nav)
- [x] The game index page loads — does it describe the game clearly? Does it have a CTA to join?
- [x] Click through to the join/enrollment page
- [x] Page renders correctly — form shows entry fee, any rules summary, submit button
- [x] Submit enrollment — should redirect to the picks page
- [x] Confirm enrollment: nav should now show "My Picks" or similar World Cup nav items

**Notes:**

---

### 3B: Already enrolled

- [x] Try navigating to `/worldcup/join` again while already enrolled — should redirect away with a flash (not allow double enrollment)

**Notes:**

---

## Section 4: World Cup — Pick Submission 🔴

This is the most complex player flow. Take your time here.

### 4A: Pick form rendering

- [x] Navigate to `/worldcup/picks`
- [x] Page renders correctly — 5 tier sections are visible: Favorites, Contenders, Dark Horses, Underdogs, Wildcards
- [x] Each tier shows the correct teams (spot-check: Tier 1 should include Spain, France, England, Argentina, Brazil, Portugal, Germany — 7 teams for 2 picks)
- [x] Each tier shows the correct pick count requirement (Tier 1: pick 2, Tier 2: pick 1, Tier 3: pick 2, Tier 4: pick 2, Tier 5: pick 2)
- [x] USA goals tiebreaker field is visible
- [x] On **mobile** (open on your phone or use browser dev tools): cards are tappable, no horizontal scroll, the form is usable

**Notes:**

---

### 4B: Submission validation — wrong tier counts

Before submitting valid picks, test the guards.

- [x] Submit the form **with no picks selected** — should show a validation error listing tier requirements, not a 500
- [x] Submit with **only Tier 1 picks** (ignore others) — should error saying other tiers need picks
- [x] Submit with **3 Tier 1 picks** (too many) — should error specifically on Tier 1 count
- [x] Submit with a **negative tiebreaker** value — should error on tiebreaker validation
- [x] Submit with a **non-numeric tiebreaker** — should error on tiebreaker validation
- [x] In all error cases: the form **preserves your selections** (you don't lose everything you picked)

**Notes: These pass because you cannot hit submit picks button if you don't meet all necessary requirements. Guardrails are properly built in.**

---

### 4C: Valid pick submission — happy path

- [x] Select exactly: 2 Tier 1 teams, 1 Tier 2, 2 Tier 3, 2 Tier 4, 2 Tier 5 (9 total)
- [x] Enter a valid tiebreaker (e.g., `4`)
- [x] Submit — should succeed, redirect or show confirmation
- [x] Navigate to `/worldcup/picks` — your 9 picks should be displayed with team names and tiers
- [x] Scores should all show `0.0` (no matches played yet — this is correct)
- [x] Tiebreaker value should be visible

**Notes:**

---

### 4D: Pick editing — pre-deadline

- [x] While still on the picks page, click Edit (or navigate back to the submission form)
- [x] Your **previous picks should be pre-selected** — you're editing, not starting fresh
- [x] Change 2–3 of your selections
- [x] Submit the edited picks
- [x] Confirm the new picks are saved (navigate to `/worldcup/picks` to verify)
- [x] Edit again — change back to your original selections (or whatever you want)

**Notes:**

---

### 4E: Post-deadline behavior (simulate deadline passed)

> This requires a temporary code change. In `games/worldcup/constants.py`, change `TOURNAMENT_DEADLINE_UTC` to a date in the past (e.g., yesterday). Restart the server. Revert when done.

```python
# Temporary: set to a past date to simulate post-deadline state
TOURNAMENT_DEADLINE_UTC = datetime(2026, 4, 10, 19, 0, tzinfo=timezone.utc)  # yesterday
```

- [x] Navigate to `/worldcup/picks` — picks should be displayed as **read-only** (no edit form, no submit button)
- [x] A message should indicate that picks are locked / deadline has passed
- [x] Attempt to POST to `/worldcup/picks` directly (use browser dev tools or curl) — server should reject with a proper error, not silently save

```bash
# Quick POST test — replace SESSION_COOKIE with your actual session cookie value
# This is a spot-check; the key thing is the server returns a non-200 or a redirect with error
curl -X POST http://localhost:5000/worldcup/picks \
  -H "Cookie: session=<your_session_cookie>" \
  -d "csrf_token=fake" \
  --verbose 2>&1 | grep "< HTTP"
```

- [x] **Revert `TOURNAMENT_DEADLINE_UTC` to the real date and restart the server before continuing**

**Notes:**

---

## Section 5: World Cup — Leaderboard & Public Access 🔴

### 5A: Leaderboard — public access

- [x] **Log out completely**
- [x] Navigate to `/worldcup/leaderboard` directly (no login)
- [x] Page loads — **no redirect to login** (this is a public page per ADR-026)
- [x] Your `testplayer1` enrollment is visible in the leaderboard (score: 0.0 — correct)
- [x] Rank column is populated
- [x] Tiebreaker column is visible

**Notes:** ✅ Resolved — tiebreaker column/value is now hidden pre-deadline on both desktop and mobile (commit c5e4149, tightened in 49821a3).

---

### 5B: Leaderboard — player detail

- [x] Click on `testplayer1`'s name in the leaderboard
- [x] Player detail is correctl hidden since deadline has not passed
- [x] Page is accessible **without login** (still logged out)

**Notes:**

---

### 5C: Leaderboard with multiple players (if you have a second test account)

If you created a second user account earlier, enroll them too and submit different picks. Then:

- [x] Leaderboard shows both players
- [x] Ranking is correct (tied at 0.0 — order may be arbitrary, that's fine)

**Notes:**

---

## Section 6: World Cup — Info Pages

Quick renders-without-errors check. No deep interaction needed.

- [x] `/worldcup/schedule` — loads, shows match schedule with dates/times (in Central Time), organized by group or round
- [x] `/worldcup/groups` — loads, shows 12 group tables (A–L), all showing 0 points/0 matches played (correct pre-tournament state)
- [x] `/worldcup/rules` — loads, shows scoring rules including tier multipliers, group stage points, knockout points, tiebreaker explanation
- [x] All times on the schedule page are in **Central Time** (not UTC) — spot-check Match 1: Jun 11 at 2:00 PM CT

**Notes:** ✅ Resolved — schedule page now shows a "All kickoff times shown in Central Time" caption under the hero lead (commit 566128b).

---

## Section 7: World Cup — Admin Flows 🔴

Log back in as your **admin account** (the one with `User.is_admin = True`).

### 7A: Admin access

- [x] Navigate to `/worldcup/admin/` — admin dashboard loads
- [x] Dashboard shows: tournament status, matches needing scores, enrolled players
- [x] Player count shows `testplayer1` (and any other test enrollments)
- [x] "Matches needing scores" section shows upcoming matches (all 104 if no results entered yet)

**Notes:**

---

### 7B: Enter a group stage match result

Pick any group stage match (e.g., Match 1: Mexico vs South Africa, Jun 11).

- [x] Navigate to the match result entry page for Match 1 (via admin dashboard or `/worldcup/admin/match/1`)
- [x] Page shows: match details (teams, stage, kickoff time), score entry form
- [x] Enter a result: e.g., Mexico 2, South Africa 1
- [x] Submit — should redirect back to admin dashboard or show success
- [x] Confirm: admin dashboard now shows Match 1 as completed with the entered score
- [x] Confirm: **leaderboard updates** — navigate to `/worldcup/leaderboard`. If `testplayer1` picked Mexico, their score should be > 0. If they didn't, score stays 0 (also correct).

> **Scoring spot-check:** Mexico is a Tier 3 team (×2.5 multiplier). A win = 3 base points. Expected score if Mexico was picked: 3 × 2.5 = **7.5 points**. Verify this is what appears on the leaderboard.

- [ ] Score is mathematically correct based on the game design

**Notes:** ✅ Both resolved.
- Admin match entry auto-derives the winner (or draw) from the score, with an aria-live hint confirming the selection (commits bf3ea6d, 25cd5af).
- Schedule page shows per-team attribution chips under completed-match scores (e.g., `MEX +3 base`), derived from a `compute_match_attribution` helper (commits b5a7b07, 90833ca, 71147b1, 566128b). Own-picks and player-detail pages have a per-pick drill-down accordion that reveals the underlying ScoreEvent breakdown (commits f260c07, d336ded, 925b96e).

---

### 7C: Clear a result and re-enter

- [x] From the match detail page for Match 1, click "Clear Result"
- [x] Confirm the result is cleared — match shows as incomplete again
- [x] Leaderboard score drops back to 0.0 for affected players
- [x] Re-enter the same result
- [x] Leaderboard returns to the correct score

> This tests the idempotency of the recalc — scores should always reflect what's in the DB, not accumulate.

**Notes:** ✅ Resolved — admin dashboard now has a "Completed Matches" card with per-match Edit buttons, collapsing if >5 rows (commits 1513343, 63cea8e).

---

### 7D: Knockout team assignment (simulate)

The knockout round shells have no teams yet — they're filled in as the bracket resolves. Test that the admin UI for this works.

- [x] Navigate to `/worldcup/admin/knockout` (or the knockout team assignment section on the admin dashboard)
- [x] Find a Round of 32 match shell
- [x] Assign two teams to it (pick any two teams from the DB)
- [x] Confirm the assignment saves — the match now shows the assigned teams
- [x] Navigate to the match result entry for that match — teams should appear in the score form
- [x] Clear the team assignment (or assign different teams) to restore the clean state

**Notes:** ✅ Resolved.
- The set-knockout page (`/worldcup/admin/set-knockout/<match_id>`) now has a "Clear Team Assignment" button that nulls both teams. Blocked when the match has a recorded result (lock hint links to the result page to clear it first). Commit 359c278.
- Admin dashboard "Matches Needing Scores" card now shows an "Edit Teams" button on knockout-stage rows, so you no longer need to type the URL. Commit 06781e4.

---

### 7E: Admin advancement (group stage advancement milestones)

- [x] Navigate to `/worldcup/admin/advancement`
- [x] Page loads without error
- [x] Understand what this page does: it's where you'd manually record group advancement status (who won their group, who advanced as runner-up, best 3rd, etc.) for milestone points
- [x] You don't need to submit anything — just confirm the page renders correctly and the form makes sense

**Notes:**

---

### 7F: Admin player management

- [x] Find the player management section in the admin dashboard
- [x] `testplayer1`'s enrollment is visible
- [x] You can see their picks (or there's a link to them)
- [x] Payment status is visible (if that field exists for World Cup)

**Notes:**

---

### 7G: Non-admin access blocked

Log out of admin. Log in as `testplayer1` (a non-admin account without enrollment-scoped `is_admin`).

- [x] Navigate to `/worldcup/admin/` — should redirect away with a flash error (not show the admin dashboard)
- [x] Navigate to `/worldcup/admin/match/1` — same, should be blocked

**Notes:**

---

## Section 8: Golf + CFB Smoke Test (5 min)

Quick regression check — just confirm these haven't broken.

### 8A: Golf Pick 'Em

- [ ] `/golf/` loads — standings page or home page renders
- [ ] `/golf/schedule` loads (or equivalent schedule/tournament list page)
- [ ] No 500 errors in Flask console

**Notes:**

---

### 8B: CFB Survivor

- [ ] `/cfb/` loads — standings or home page renders
- [ ] No 500 errors in Flask console

**Notes:**

---

## Section 9: Mobile Check (5 min)

Open `http://<your-local-IP>:5000` on your phone, or use Chrome DevTools device emulation (F12 → toggle device toolbar → iPhone or Pixel).

- [ ] Platform homepage: nav collapses to hamburger, readable
- [ ] `/worldcup/join`: enrollment form is usable, button is tappable
- [ ] `/worldcup/picks`: tier cards are full-width, teams are selectable, no horizontal scroll
- [ ] `/worldcup/leaderboard`: table either scrolls horizontally with a scroll indicator, or uses the card/stacked layout — either is fine as long as it's not cutting off data
- [ ] `/worldcup/schedule`: same — table readable on mobile
- [ ] Login page: usable on mobile

**Notes:**

---

## What to Do with Failures

**Blockers (fix before deploying):**
- Any 500 error on a player-facing page
- Registration silently failing or not logging the user in
- Pick submission not saving, or saving picks post-deadline
- Leaderboard accessible only with login (ADR-026 violation)
- Score math wrong after entering a match result
- Admin pages accessible to non-admin users

**Non-blockers (fix post-launch or document as known):**
- Visual/layout issues that don't prevent interaction
- Minor wording that should be improved
- Admin advancement page behavior that's confusing but functional
- Golf/CFB cosmetic issues

---

## After Testing

If all blockers pass → proceed to the PA deploy handoff.  
If blockers are found → fix in a new Claude Code session, re-test the affected section only.

**Clean up test data before deploying:**
```bash
# Optional: wipe and re-seed for a clean production DB
# (only do this when you're ready to deploy — don't run this mid-testing)
FLASK_APP=app.py venv/bin/flask db downgrade base
FLASK_APP=app.py venv/bin/flask db upgrade
FLASK_APP=app.py venv/bin/flask worldcup init
FLASK_APP=app.py venv/bin/flask create-admin
```