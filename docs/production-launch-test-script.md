# Production Launch Test Script
## Fantasy Platform — Post-Redesign Go-Live

**Date authored:** 2026-05-06
**Tester:** Brad
**Target URL:** `https://cccfantasy.com/`
**Estimated time:** ~3.5 hours including tournament simulation + DB reset
**Prerequisites:** Deployment plan Tasks 11–25 complete (Postgres provisioned, domain registered, server set up, app deployed, cron jobs loaded)

This script walks the production environment end-to-end against the live codebase. It registers two test users, simulates a full World Cup tournament with admin-entered match results, verifies every redesigned surface from Specs A/B/C, then resets the database to a clean launch baseline (admin user only, no test data, no entered results) before real players are invited in.

🔴 = go/no-go blocker for launch. Fix before announcing.
⚪ = regression check. Note and triage post-launch.
✅ / ❌ / ⚠️ — mark each item as you go.

---

## How to use this script

- Work through sections in order — later sections depend on earlier ones (especially §8–§14).
- Mark each item ✅ (pass), ❌ (fail), or ⚠️ (unexpected but not blocking).
- When something fails, capture what you saw in the section's `Notes:` block.
- **Stop and triage 🔴 blockers before continuing** — see the "If anything goes red" box at the bottom for rollback commands.
- **Do not skip §14 or §15.** The deadline edit and DB reset are mandatory before you announce launch.

---

## Section 0: Pre-flight (prod-side, no browser yet) 🔴

> Before touching the live URL in a browser, confirm the box itself is healthy. Cheap to run, expensive to skip — a stale systemd unit or a near-full disk will make every later section unreliable.

```bash
ssh deploy@<your-droplet-ip>

sudo systemctl status nginx fantasy-platform --no-pager | head -30
journalctl -u fantasy-platform -n 50 --no-pager
df -h /
free -h
cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup status
curl -I https://<your-live-domain>
```

- [x] `nginx` shows `active (running)`
- [x] `fantasy-platform` shows `active (running)`
- [x] `journalctl` shows no recent Python tracebacks
- [x] Disk usage on `/` is below 80% (matches DO alert threshold)
- [x] Memory is below 85% (matches DO alert threshold)
- [x] `flask worldcup status` prints: 48 teams, 104 matches, 0 completed, 0 enrolled (or your admin enrollment if you joined yourself during prior tasks)
- [x] `curl -I` returns `HTTP/2 200` and a `server: cloudflare` header

**Notes:**

---

## Section 1: Out state — logged-out chrome 🔴

> Verifies the CCC brand foundation (Spec A) and the `_home_out` partial (Spec B/C Plan 4) render correctly to a brand-new visitor, plus core HTTPS/redirect/static-asset hygiene.

Open a fresh **incognito** window. Navigate to `https://<your-live-domain>`.

- [x] Browser shows a green padlock (HTTPS, no certificate warnings)
- [x] Visiting `http://<your-live-domain>` (plain HTTP) 301-redirects to `https://`
- [x] Page renders the CCC brand mark in the navbar (gold accent, voice label)
- [x] Footer renders with voice strip + utility strip
- [x] No mixed-content warnings in the browser console
- [x] Open DevTools → Network → reload the page → `/static/css/style.css` returns `200` with `Cache-Control: public, immutable, max-age=...` (Nginx serving directly)
- [x] Open DevTools → Network → `/static/css/tokens.css` returns `200` (loaded **before** style.css per CLAUDE.md)
- [x] No `404`s on any static asset

**Notes:**

---

## Section 2: Registration + auth 🔴

> Verifies the auth-page pattern (Spec A: login, register, forgot, reset, change, profile), avatar picker integration, and — critically — that real password-reset emails arrive from the production Gmail SMTP.

> **Email aliasing tip:** Use Gmail's `+alias` form so password-reset emails land in *your* real inbox: `bhagstrom0+test1@gmail.com` and `bhagstrom0+test2@gmail.com`. Do **not** use throwaway domains — you must observe these emails in the next sub-step.

### 2A: Register two test users

In the incognito window:

- [x] `/register` renders the auth-page pattern (CCC palette, brand mark, gold accents)
- [x] Register `testplayer1` with email `bhagstrom0+test1@gmail.com`, strong password
- [x] Submit → redirects to home, logged in, username in navbar
- [x] Log out
- [x] Register `testplayer2` with email `bhagstrom0+test2@gmail.com`, strong password
- [x] Submit → redirects to home, logged in
- [x] Log out

### 2B: Validation

- [x] Try registering `testplayer1` again → inline error, not 500; form repopulates
- [x] Try registering with mismatched passwords → inline error
- [x] Try empty form → required-field errors, not 500

### 2C: Login flow + `?next=` redirect

- [x] Visit `/worldcup/picks` while logged out → redirected to `/login?next=/worldcup/picks`
- [x] Log in as `testplayer1` → redirects back to `/worldcup/picks` (the `next` param survives the GET → POST round-trip — locked in commit `02599f3` per archived script)

### 2D: Login validation

- [x] Wrong password → "Invalid credentials" (or equivalent), not 500
- [x] Non-existent username → identical message (no user enumeration)

### 2E: Profile + avatar picker

Logged in as `testplayer1`:

- [x] `/profile` renders auth-page pattern; shows username + email
- [x] Avatar picker visible; pick an emoji other than ⚽ (default); save → confirmation
- [x] Pick a different one to confirm it's persistent

### 2F: Change password

- [x] `/change-password` renders auth-page pattern
- [x] Wrong current password → inline error, not 500
- [x] Successful change → confirmation; log out, log back in with new password
- [x] Change back to original (optional, for cleanliness)

### 2G: Forgot/reset password — real email send

> **Prerequisite — SMTP unblock:** DigitalOcean blocks outbound port 587 by default. A support ticket has been submitted. Before running this section, confirm the block is lifted:
> ```bash
> nc -w 5 smtp.gmail.com 587 && echo "SMTP reachable" || echo "still blocked"
> ```
> If still blocked, skip §2G and §12C for now and return to them once DO approves. They are pre-launch 🔴 blockers — do not check §15E's announcement gate until both pass.

- [x] SMTP reachable confirmed (nc test above returns "SMTP reachable")
- [x] Log out
- [x] `/forgot-password` → enter `bhagstrom0+test1@gmail.com` → submit
- [x] Flash message is intentionally ambiguous (anti-enumeration: "If that email is in our system, a reset link has been sent")
- [x] **Real email arrives** in your Gmail within 2 minutes, from-name **"Corrupt Commish Club"**, with a reset link
- [x] Click the link → reset form renders the auth-page pattern → set new password → submit → success
- [x] Log in with new password → works

### 2H: Anti-enumeration on a non-existent email

- [x] `/forgot-password` → enter `nope-not-real@example.com` → submit
- [x] Identical flash message as 2G (no leak that the address doesn't exist)
- [x] No email arrives at any inbox

**Notes:**

---

## Section 3: WC enrollment + picks + pre-deadline surfaces 🔴

> Verifies the per-game enrollment flow (Plan: 2026-04-17), the new picks foundation (Spec C Plan 1), the leaderboard reskin (Plan 3), the new `team_detail` route with D11 ownership privacy (Plan 2), and the schedule/groups/rules content pages.

Logged in as `testplayer1`:

### 3A: Join

- [x] `/worldcup/join` loads (`game_must_be_open` decorator allows it)
- [x] Page renders with page-hero, how-it-works card, btn-game submit (Spec C Plan 1 pattern)
- [x] Submit enrollment → redirects to `/worldcup/picks`
- [x] Sub-nav now shows the WC pill set with red accent (`subnav-worldcup` per CLAUDE.md)

### 3B: Submit picks (testplayer1)

- [x] `/worldcup/picks` renders the new picks foundation: 5 tier sections (Favorites, Contenders, Dark Horses, Underdogs, Wildcards)
- [x] Each tier shows correct pick-count requirement (T1: 2, T2: 1, T3: 2, T4: 2, T5: 2 = 9 total)
- [x] USA goals tiebreaker field visible
- [x] Validation guards work (cannot submit without 9 picks; submit button disabled or rejects)
- [x] Select 2 T1, 1 T2, 2 T3, 2 T4, 2 T5; tiebreaker `4`; submit → success
- [x] After submit, page shows read-only summary with "Edit My Picks" button (per archived script `02599f3` lock-in)

### 3C: Edit picks (still pre-deadline)

- [x] Click Edit; existing picks are pre-selected (not blank)
- [x] Change 2–3 picks; submit → confirms saved
- [x] Reload `/worldcup/picks` → new picks visible

### 3D: Enroll testplayer2 + submit different picks

- [x] Log out, log in as `testplayer2`
- [x] Enroll via `/worldcup/join`
- [x] Submit a **different** set of 9 picks (overlap with testplayer1 in some tiers, divergent in others) — this matters for §10 ownership-reveal verification
- [x] Tiebreaker `2` (different from testplayer1)

### 3E: Leaderboard pre-deadline (logged-out, public per ADR-026)

- [x] Log out completely
- [x] `/worldcup/leaderboard` loads — **no redirect to login**
- [x] Both `testplayer1` and `testplayer2` rows appear
- [x] Both rows show score 0.0 (no matches played); rank shows dense rank
- [x] **Rivals' picks are NOT shown anywhere on the leaderboard pre-deadline** (privacy enforced server-side)
- [x] Each row has the player's avatar emoji rendered before the display name
- [x] Tiebreaker column is **hidden** pre-deadline (per archived-script `c5e4149` / `49821a3`)
- [x] **Trend column is NOT visible** (gated at ≥7 snapshots; we have 0 right now)
- [x] Click a player row → `/worldcup/leaderboard/<id>` (player_detail) loads

### 3F: Player detail pre-deadline

- [x] `/worldcup/leaderboard/<testplayer2_id>` (logged out)
- [x] Page renders the Plan 2 player_detail reskin (page-hero, player chip with avatar)
- [x] **testplayer2's individual picks are NOT shown** (only aggregate score, no roster reveal)
- [x] Per-pick accordion drill-down is empty / hidden pre-deadline

### 3G: Team detail pre-deadline — **D11 ownership privacy invariant** 🔴

This is the most important privacy invariant in the codebase right now. Per CLAUDE.md and the spec memory `project_ccc_team_detail_privacy`: ownership count, percent, and picker_names must be hidden from **ALL viewers including the team's own picker** pre-deadline.

Pick any team that testplayer1 picked (e.g., a Tier 1 team). Note the team_id from the picks page or from the schedule.

- [x] `/worldcup/team/<team_id>` loads (logged out)
- [x] Page renders Plan 2 team_detail (hero, fixtures, ownership ribbon section)
- [x] **Ownership count is hidden** — no "X players picked this team" display
- [x] **Picker names are NOT shown**
- [x] **Percent is NOT shown**

Now log in as `testplayer1` (the team's own picker):

- [x] `/worldcup/team/<team_id>` while logged in as picker
- [x] **Ownership count is STILL hidden** even from the team's own picker (this is the D11 invariant — do NOT "fix" the absent-count branch)
- [x] No leak of "you and N others picked this team"

### 3H: Content pages

Logged in as `testplayer1`:

- [x] `/worldcup/schedule` — renders matches in CT timestamps, has "All kickoff times shown in Central Time" caption (per archived-script `566128b`)
- [x] `/worldcup/groups` — 12 group tables (A–L), all 0 points / 0 played
- [x] `/worldcup/rules` — scoring matrix renders without redundant "Base" column

**Notes:**

---

## Section 4: Stats Hub (pre-tournament) ⚪

> Verifies Spec C Plan 3's public stats hub. Pre-tournament data is sparse but the page must render cleanly.

- [x] `/worldcup/stats` loads (publicly accessible, logged out is fine)
- [x] Phase chip reads "Pre-Tournament" (per CLAUDE.md `current_phase` derivation, **not** mangled by `|title`)
- [x] Country / tier KPIs render with empty / zero-baseline data
- [x] Tier combos table renders (may be sparse with only 2 enrolled players)

**Notes:**

---

## Section 5: Home state machine — `out` + `pre` 🔴

> Verifies Spec B's `build_home_context` dispatcher and the `_home_out` / `_home_pre` partials. `live` and `post` are exercised in §9 and §11.

### 5A: Logged-out home → `_home_out` partial

Incognito window:

- [x] `/` renders the `_home_out` partial: the King Viking Badger mascot bust (`.out-mark`) leads the hero, with the `◈ Fantasy for crooked kings & queens ◈` eyebrow, the two-line `.out-title` ("The Fix / Is In."), and the `.out-sub` tagline — no enrolled-player content
- [x] "Join the Club" CTA + "Sign in" link render; the headline (`.out-title`) clearly dominates the subordinate tagline (`.out-sub`)
- [x] Below the hero, the "Pools in Session" registry section lists World Cup as the featured pool

### 5B: Logged-in pre-deadline, **not enrolled in WC** — join CTA

- [x] Register a third throwaway user **without** enrolling in WC (or use testplayer1 after un-enrolling — just need a logged-in non-enrolled state)
- [x] `/` shows the join-the-cup treatment (not the enrolled `_home_pre` content)

### 5C: Logged-in pre-deadline, **enrolled** — `_home_pre` partial

Logged in as `testplayer1` (already enrolled):

- [x] `/` renders `_home_pre` partial (greet "The Council Awaits" + countdown card)
- [x] Sealed ballot card (`.ballot-card`, "Sealed & delivered" / ◈ Locked) renders all 9 picks as a flag ribbon, plus the tier-grouped Roster Spine (T1–T5 with country names + multipliers)
- [x] Countdown card counts down to the June 11 deadline — the honest pre-tournament state (no live sparkline/dossier yet; that's live-state only)
- [x] "Opening Matches" fixture ladder lists upcoming matches, marking any "YOUR PICK" rows; no "Recent Results" section (that surface is live-state only)

**Notes:**

---

## Section 6: Game switcher + Golf/CFB regression ⚪

> Quick smoke check that Spec A's brand foundation didn't break Golf or CFB blueprints, and the game switcher in the navbar wires up correctly.

- [x] Navbar game switcher dropdown shows: Golf Pick 'Em, CFB Survivor, World Cup Fantasy
- [x] `/golf/` loads — no 500; sub-nav swaps to Golf theme (Augusta green / gold accents)
- [x] `/cfb/` loads — no 500; sub-nav swaps to CFB theme (crimson / midnight)
- [x] `body.game-golf` / `body.game-cfb` CSS class injected (inspect via DevTools)
- [x] Switching back to `/worldcup/` restores the WC theme

**Notes:**

---

## Section 7: Admin two-tier scoping 🔴

> Verifies the two-tier admin invariant from CLAUDE.md: platform admin (`User.is_admin`) is universal override; enrollment-scoped admin works for delegated game admin; non-admins are blocked.

### 7A: Platform admin universal override

Log in as your platform admin account (the user created via `flask create-admin`):

- [x] `/worldcup/admin/` — admin dashboard loads
- [x] `/golf/admin` — golf admin loads (even without golf enrollment, because platform admin overrides)
- [x] `/cfb/admin` — same

### 7B: Non-admin blocked

Log in as `testplayer1`:

- [x] `/worldcup/admin/` → flash error + redirect (NOT a 500, NOT a silent allow)
- [x] `/worldcup/admin/match/1` → blocked
- [x] `/golf/admin` → blocked
- [x] `/cfb/admin` → blocked

**Notes:**

---

## Section 8: Tournament prep — flip the deadline

> The next sections (§9–§11) require `worldcup_state()` to no longer return `'pre'` — they need `'live'` and eventually `'post'`. On production, `WC_FAKE_NOW` is silently ignored (`ENVIRONMENT=production`), so the only path is to set the deadline to a past datetime in the canonical definition site, restart the service, and **revert before §14's DB reset.**
>
> ⚠️ **REVERT REMINDER:** Section 14 starts by reverting this edit. If you stop testing partway through and forget to revert, you will ship a yesterday-deadline to real players. Set a phone reminder.

### 8A: SSH and edit the deadline

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
```

- [x] Find the line: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))`
- [x] Change it to: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 5, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))` (or any clearly-past date)
- [x] Save (`Ctrl+X`, `Y`, Enter)

```bash
sudo systemctl restart fantasy-platform
sudo systemctl status fantasy-platform --no-pager | head -10
```

- [x] Service is `active (running)` after restart

### 8B: Verify the deadline took effect

In a browser logged in as `testplayer1`:

- [x] `/worldcup/picks` is now **read-only** (no edit form, no submit button)
- [x] A flash / banner indicates picks are locked / deadline has passed

Try to bypass via direct POST:

```bash
# From your Mac terminal — replace SESSION_COOKIE with the value from your browser DevTools
curl -X POST https://<your-live-domain>/worldcup/picks \
  -H "Cookie: session=<SESSION_COOKIE>" \
  -d "csrf_token=fake" \
  --verbose 2>&1 | grep "< HTTP"
```

- [ ] Server returns a 3xx redirect or 4xx error — **NOT** a 200 / silent save

### 8C: Verify rivals' picks are now visible (post-deadline reveal)

Log in as `testplayer1`:

- [x] `/worldcup/leaderboard/<testplayer2_id>` (player_detail) — testplayer2's picks ARE now visible (deadline_passed gate flipped)
- [x] Per-pick accordion drill-down works on player_detail

**Notes:**

---

## Section 9: Live state — group stage simulation 🔴

> Drives `worldcup_state()` to `'live'` by entering 4 group-stage match results that exercise every multiplier path. Verifies the `_home_live` partial renders the dossier sparkline (after a manual snapshot backfill) and that recent results promote testplayer1's picked teams to full `.match-card--roster` cards.

> **Score-math expected values** (verified from `games/worldcup/world_cup_countries.py` TIERS dict and `games/worldcup/constants.py`):
> - Group win = **3** base × tier multiplier
> - Group draw = **1** base × tier multiplier
> - Tier multipliers: T1 Favorites=**1.0**, T2 Contenders=**1.5**, T3 Dark Horses=**2.5**, T4 Underdogs=**4.0**, T5 Wildcards=**7.0**

### 9A: Backfill the snapshot table for the trend column

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
```

- [x] Command prints "Backfilled 7 days" (or equivalent); no errors
- [x] (Note: all 7 backfilled days will share the current rank/score since we have no historical data — real differentiation accumulates only after live cron runs)

### 9B: Enter 4 group-stage results via admin

Log in as platform admin. Pick 4 specific matches that exercise each multiplier path. Tier 4 examples (Underdogs) include Scotland (SCO, Group C), Czechia (CZE, Group A), Ivory Coast (CIV, Group E), Egypt (EGY, Group G), Ghana (GHA, Group L), Algeria (ALG, Group J), South Korea (KOR, Group A), Bosnia (BIH, Group B), Austria (AUT, Group J), Canada (CAN, Group B), Paraguay (PAR, Group D).

| # | Match shape | Result | Expected per-pick impact (if testplayer1 picked the team) |
|---|---|---|---|
| 1 | A match where one of testplayer1's **Tier 1 picks** plays | T1 wins, e.g., 2–0 | `3 × 1.0` = **3.0** points added to testplayer1's total |
| 2 | A match where two **Tier 3** teams play, one of testplayer1's T3 picks involved | Draw, e.g., 1–1 | `1 × 2.5` = **2.5** points added |
| 3 | A match where one of testplayer1's **Tier 4** picks plays (e.g., Scotland upsets Brazil) | T4 wins, e.g., 1–0 | `3 × 4.0` = **12.0** points added |
| 4 | A match where one of testplayer1's **Tier 5** picks plays | T5 wins, e.g., 2–1 | `3 × 7.0` = **21.0** points added |

If testplayer1 picked the winning/drawn team in all four matches, their total after Recalc = **38.5**.

For each match:

- [x] Navigate to `/worldcup/admin/match/<match_id>`
- [x] Enter the score
- [x] Page auto-derives winner from score with aria-live confirmation (per archived-script `bf3ea6d`/`25cd5af`)
- [x] Submit → success

After all 4:

- [x] Click admin Recalc button (POST to `/worldcup/admin/recalc`) — instant; verifies the route works
- [x] testplayer1's leaderboard total = sum of expected impacts for whichever subset they picked
- [x] testplayer2's leaderboard total reflects whichever subset of those 4 matches involved their picks
- [x] Schedule page shows per-team attribution chips on completed matches (e.g., `MEX +3 base` per archived-script `b5a7b07`/`90833ca`)

### 9C: Group advancement form

Pick one group where you've entered enough results to call advancement:

- [x] `/worldcup/admin/advancement` loads
- [x] Submit advancement for that group (winner, runner-up, possibly best-3rd)
- [x] Confirm submission persists (re-load page, values pre-filled)

> **Tip — test advancement across all 12 groups without clicking through every match:**
> SSH to the droplet and run `flask worldcup simulate-group-stage` (add `--dry-run` first
> to preview). It fills all 72 group results with deterministic, tie-free standings
> (clean 9/4/3/1 per group, one draw each) so every group shows `all_complete` on the
> advancement page. Only touches `stage='group'` matches; re-runs skip completed matches.
> It stops *before* advancement confirmation, so the `/admin/advancement` flow above stays
> the manual step under test. Note: completing all 72 group matches moves the live-state
> home page past the "partial results" view checked in 9A/9B/9D — run those UI checks
> first, or reset the DB to baseline afterward.

### 9D: `_home_live` partial renders correctly
Log in as `testplayer1`, navigate to `/`:

- [x] Home page now renders `_home_live` partial (NOT `_home_pre`) — greet reads "Your Dossier"
- [x] Dossier card (`.dossier`) visible with the rank line + sparkline. The sparkline renders as a centered **dashed** line (the `is_flat` branch — backfill produced identical days so min == max; real movement only accrues after future cron runs)
- [x] Rank-movement / week-delta line is shown ("Holding rank over 7 days" — gated at ≥7 snapshots; `--backfill 7` writes 8 rows, so the gate passes)
- [x] Recent Results section lists the entered matches
- [x] Matches involving testplayer1's picks render as full `.match-card--roster` cards with a "YOUR ROSTER · <team>" footer + a `+X.X PTS` chip; non-roster results collapse into the "Around the Tournament" strip

### 9E: Stats Hub during live state

- [x] `/worldcup/stats` — phase chip reads "Group Stage" or similar (NOT "Pre-Tournament")
- [x] Country / tier KPIs reflect the 4 entered matches

### 9F: WC room hub live state ⚪

> The WC room hub at `/worldcup/` carries its own **differentiated** live surface — the Leverage Board — that the lounge (`/`) intentionally does not mirror. Not exercised anywhere else in this script.

- [x] `/worldcup/` (logged in as testplayer1) leads with the Leverage Board inside `.wc-standing-card.is-lead`: one row per pick with a multiplier chip + a red realized-points bar, carriers (scoring picks) sorted on top
- [x] A survival/upside summary line renders (e.g., "N of 9 still alive" + the highest-multiplier dormant "upside") below the board

**Notes:**

---

## Section 10: Knockout simulation 🔴

> Drives the bracket from R32 to final. Verifies `/worldcup/admin/set-knockout` team assignment, the clear-team-assignment guard (locked when result entered), knockout scoring math, and the post-deadline ownership reveal on team_detail.

### 10A: Assign teams to one R32 match

- [x] `/worldcup/admin/set-knockout/<R32_match_id>` loads
- [x] "Edit Teams" button on knockout-stage rows of "Matches Needing Scores" (per archived-script `06781e4`)
- [x] Assign two teams to the R32 match → save → page shows the assignment
- [x] "Clear Team Assignment" button is now visible (per archived-script `359c278`)

### 10B: Enter R32 result + verify guard

- [x] `/worldcup/admin/match/<R32_match_id>` — enter a result (e.g., 2–1)
- [x] Submit → success
- [x] Return to `/worldcup/admin/set-knockout/<R32_match_id>` — "Clear Team Assignment" is now **locked** with a hint to clear the result first
- [x] Click admin Recalc → leaderboard updates with knockout points (uses `points_for_pick_on_match` per CLAUDE.md — already-multiplied)

### 10C: Drive the bracket to a champion (~5 more matches)

Enter results for one path through the bracket:

- [x] One R16 match (assign teams via set-knockout, enter result, recalc)
- [x] One QF match (same)
- [x] One SF match (same)
- [x] The Final (same)
- [x] The Third-Place Match (same)

Verify after each:

- [x] Leaderboard math is internally consistent (totals only ever increase with each new match)
- [x] Stage labels render correctly via `stage_label()` (e.g., "Semifinals", "Third-Place Match", **NOT** "Sf" / "Third_Place" — `|title` filter must NOT be in use per CLAUDE.md)

### 10D: Post-deadline ownership reveal on team_detail 🔴

Pick any team that testplayer1 picked. Log out (or stay logged in — D11 says hidden pre-deadline for everyone, but reveal post-deadline is for everyone too):

- [x] `/worldcup/team/<team_id>` (logged out)
- [x] Ownership count is now **visible** (e.g., "1 player picked this team" or "2 players picked this team")
- [x] Percent is shown
- [x] Picker names list shows `testplayer1` (and testplayer2 if they also picked it)

**Notes:**

---

## Section 11: Post state — champion crowned 🔴

> After the final + third-place results are entered in §10, the tournament `current_phase` flips to `'completed'` and `worldcup_state()` returns `'post'`. Verifies `_home_post` renders the champion banner, final roster recap, and `team.best_finish` labels render literally.

Log in as `testplayer1`, navigate to `/`:

- [x] Home page renders `_home_post` partial (NOT `_home_live`) — greet `.greet-title` reads "The 2026 World Cup"
- [x] Full-bleed champion banner (`_champion_banner.html`) renders with the `◈ Final Decree ◈` eyebrow, the `.champion-flag` emoji, and the `.champion-name`. ⚠️ If it instead reads "◇ Awaiting Decree / 🏆 / Champion Pending", the final match has no winner set — re-enter the Final result so `winner_team_id` is populated (the admin score form auto-derives the winner from the score)
- [x] Final podium (top 3) renders above the recap with dense-rank positions
- [x] Roster recap (`.roster-recap`) lists all 9 of testplayer1's picks
- [x] If testplayer1 picked the champion, that row has the `.roster-recap-row--champion` highlight
- [x] `team.best_finish` labels render literally — "Champion", "Round of 16", "Group Stage" — **NOT** raw codes like `'champion'` or `'r16'` (per CLAUDE.md `_BEST_FINISH_LABELS`)

Public surfaces:

- [x] `/worldcup/leaderboard` — final ranks render with dense rank
- [x] `/worldcup/stats` — phase chip flips to "Completed"
- [x] `/worldcup/` (WC room post-state) renders its own ceremonial `.wc-champion-banner` surface ⚪

**Notes:**

---

## Section 12: Cron + email + monitoring smoke 🔴

> Verifies cron jobs are actually running on the live server, the SMTP path produces real email, and monitoring is configured before the announcement.

### 12A: Cron logs (current state)

```bash
ssh deploy@<your-droplet-ip>
ls -la /var/log/fantasy/
tail -n 20 /var/log/fantasy/worldcup-recalc.log
tail -n 20 /var/log/fantasy/worldcup-snapshot.log
```

- [ ] Both active WC logs exist — `worldcup-recalc.log` + `worldcup-snapshot.log`. **Golf/CFB cron jobs are intentionally disabled** (Golf runs on a separate PythonAnywhere box; CFB is out of season until Sept 2026 — see deployment plan Task 25), so `golf-*.log` / `cfb-*.log` legitimately won't exist. If either WC log is missing or empty, that cron may have never fired.
- [ ] Recent timestamps in `worldcup-recalc.log` (cron runs every 10 min)
- [ ] No Python tracebacks in the active WC logs (`worldcup-recalc.log` / `worldcup-snapshot.log`)

### 12B: Verify the cron actually fires (~12-min passive wait)

- [ ] Note the latest timestamp in `worldcup-recalc.log`
- [ ] Leave the SSH session open, work on §13 mobile pass for ~12 min
- [ ] Re-tail `worldcup-recalc.log` — a new entry appeared (cron windows that fire every 10 min must have triggered at least one new run)

### 12C: Email — second password reset

- [ ] Log out, `/forgot-password` for `bhagstrom0+test1@gmail.com`
- [ ] Email arrives within 2 minutes from "Corrupt Commish Club"
- [ ] Reset link works (don't actually need to reset again — just verify the click loads the page)

### 12D: Monitoring

- [ ] UptimeRobot dashboard shows the Fantasy Platform monitor as **Up** (green) with a recent successful check
- [ ] DigitalOcean Monitoring → Alerts shows the three resource alerts configured (CPU > 80%, Memory > 85%, Disk > 80%)
- [ ] (Optional) Trigger a synthetic outage check: `sudo systemctl stop nginx`, wait 5 min, see UptimeRobot fire, then `sudo systemctl start nginx`. Skip if you don't want the noise.

**Notes:**

---

## Section 13: Mobile pass — real device ⚪

> Re-walks the visually-redesigned surfaces on a real phone (not Chrome DevTools emulation). DevTools won't catch real touch-target issues or actual font rendering at the device DPI.

On your iPhone or Android (connect to the live URL via Cloudflare):

- [ ] `/` (home, currently in `_home_post` after §11) — champion banner readable, hero typography distinct, no horizontal scroll
- [ ] `/worldcup/picks` (read-only post-deadline) — tier cards stack, no truncation
- [ ] `/worldcup/leaderboard` — table either scrolls horizontally with indicator OR uses card layout; nothing truncated
- [ ] `/worldcup/team/<team_id>` — Plan 2 team_detail page renders cleanly, ownership ribbon legible
- [ ] `/worldcup/leaderboard/<testplayer2_id>` (player_detail) — accordion drill-down tappable
- [ ] `/worldcup/stats` — KPI cards stack, charts/tables not cut off
- [ ] `/worldcup/schedule` — match list readable, CT timestamps visible
- [ ] Sub-nav scrolls horizontally with the scroll indicator (per archived-script Group C2)
- [ ] Hero typography legibility on the remaining dark surfaces — the navy `.page-hero.wc-hero-grad` tab heroes and the post-state champion banner (`.text-muted` + status-color overrides apply per CLAUDE.md; the old `.card.wc-card` body substrate was retired in WC Tab Unification, so every tab *body* is now light-on-bone)

**Notes:**

---

## Section 14: Cleanup — restore deadline + reset DB 🔴

> ⚠️ **Two destructive operations.** Both must complete before launch announcement.
>
> Step 1 reverts the deadline edit from §8. Step 2 wipes ALL test data (test users, all entered match results, all snapshot rows) and re-seeds the WC tournament shells. Both use `sudo systemctl restart fantasy-platform` to pick up changes.

### 14A: Restore the deadline

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
```

- [x] Find the modified `TOURNAMENT_DEADLINE_UTC` line (set in §8 to yesterday)
- [x] Restore it to: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))`
- [x] Save (`Ctrl+X`, `Y`, Enter)

```bash
sudo systemctl restart fantasy-platform
```

- [x] Service restarts cleanly

### 14B: Verify-on-prod guard before any destructive command

Inside the SSH session:

```bash
cat .env | grep DATABASE_URL
```

- [x] **Connection string contains `db.ondigitalocean.com`** — this confirms you're about to wipe the production Postgres, not a local SQLite
- [x] If the URL does NOT match, **STOP** — investigate before running any `db downgrade`

### 14C: Wipe + reseed

> 🔒 **Rotate `SECRET_KEY` as part of every destructive wipe.** `db downgrade base` → `db upgrade`
> restarts the `users` id sequence, so post-wipe signups reuse old integer PKs. Any session/remember
> cookie issued before the wipe is still validly signed under the old `SECRET_KEY`; rotating the key
> invalidates every such cookie so a returning pre-wipe visitor can't be auto-logged into whoever now
> holds the recycled id. (`User.auth_id` already makes this structurally safe, but rotating the key is
> belt-and-suspenders and instantly logs out every stale session.)

```bash
# Rotate the signing key FIRST (invalidates all existing session + remember cookies):
python3 -c "import secrets; print(secrets.token_hex(32))"   # copy the output
nano .env                                                    # replace SECRET_KEY=<new value>

# Then wipe + reseed:
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db downgrade base
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup init
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask create-admin
sudo systemctl restart fantasy-platform                      # load the new SECRET_KEY
```

- [x] `db downgrade base` — drops all tables; outputs Alembic "Running downgrade" lines
- [x] `db upgrade` — re-applies all migrations; outputs Alembic "Running upgrade" lines
- [x] `worldcup init` — seeds 48 teams + 104 match shells
- [x] `create-admin` — prompts for username, email, password — use **your real admin credentials** (this is the production launch admin user)
- [x] `flask worldcup status` — prints **48 teams, 104 matches, 0 completed, 0 enrolled**

**Notes:**

---

## Section 15: Post-reset sanity — the launch baseline 🔴

> Final pre-announcement sanity. Confirm the world is clean and the freshly-recreated admin can do what every real player will do first.

### 15A: Re-verify the deadline value

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
```

In the shell:

```python
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
print(TOURNAMENT_DEADLINE_UTC)
exit()
```

- [x] Printed value: `2026-06-11 19:00:00+00:00` — **NOT** any other date

### 15B: Admin user state

In a browser, log in as the freshly-created admin:

- [x] `/worldcup/admin/users` shows **only the admin** — no `testplayer1`, no `testplayer2`, no third throwaway user
- [x] `/worldcup/admin/` dashboard: 0 enrolled players, 0 completed matches

### 15C: First-touch flow (mirror what every real player does)

Still as admin (or register a fresh real user):

- [x] `/worldcup/picks` loads with the **empty pick form** (no pre-selected picks)
- [x] All 5 tier sections render with their full team rosters
- [x] Submit button is disabled until 9 valid picks chosen
- [x] (Don't actually submit picks unless you want them locked-in for the real cup)

### 15D: Public surfaces are production-ready

Logged out:

- [x] `/` renders `_home_out` partial with brand mark + login/register CTAs
- [x] `/worldcup/leaderboard` is empty (or shows only the admin if they enrolled)
- [x] `/worldcup/stats` phase chip back to "Pre-Tournament"
- [x] `/worldcup/schedule` shows all 104 matches with CT timestamps, none completed

### 15E: Announcement gate

- [x] All 🔴 sections (0, 1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 14, 15) are 100% ✅
- [x] All ⚪ sections noted, blockers triaged or post-launch tickets filed
- [x] **Only now** announce launch to real players

**Notes:**

---

## If anything goes red

Use these to recover from a failed section without abandoning the launch.

**Restore the deadline (if §14 was skipped or failed):**

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
# Set TOURNAMENT_DEADLINE_UTC back to: datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
sudo systemctl restart fantasy-platform
```

**Roll back code to a known-good `main` SHA:**

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
git fetch origin
git reset --hard origin/main
./deploy.sh
```

(Resets the local checkout to the latest `main` from GitHub, including reverting any §8 hand-edit since the SSH edit was never committed.)

**Roll back DB to a prior migration:**

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db downgrade <prior-revision-sha>
```

(Use `flask db history` to find the target revision.)

**Stop the world (full outage, intentional):**

```bash
sudo systemctl stop fantasy-platform nginx
```

UptimeRobot will fire within 5 minutes. Re-start with `sudo systemctl start nginx fantasy-platform` after the issue is resolved.

---

---

## When DigitalOcean approves the SMTP unblock

**Background:** Outbound SMTP (port 587) was blocked by DO's default network policy, causing the forgot-password workflow to spin then 500. A support ticket was opened 2026-05-30. Once approved, complete these steps before resuming the test script.

**1. Confirm the port is open (SSH into the server):**
```bash
nc -w 5 smtp.gmail.com 587 && echo "SMTP reachable" || echo "still blocked"
```

**2. Deploy the timeout fix** (merged to `main` in PR #52, merge commit `30141db`; the fix itself is commit `f617d55`). After `./deploy.sh` runs on the server, verify the change is live:
```bash
# Robust check — confirm a socket timeout is set on the SMTP call without
# depending on the exact numeric value or whitespace:
grep -nE "smtplib\.SMTP\(.*timeout *= *[0-9]+" /home/deploy/fantasy-platform/utils/email.py
# Belt-and-suspenders — confirm the fix commit is actually in the deployed tree:
git -C /home/deploy/fantasy-platform log --oneline | grep f617d55
```

**3. Run §2G (forgot/reset password) live:**
```bash
# Watch logs in one terminal while triggering forgot-password in the browser:
sudo journalctl -u fantasy-platform -f
# Should see: "Email sent to bhagstrom0+test1@gmail.com: Reset your password..."
# NOT: "Error handling request POST /forgot-password"
```
- [ ] §2G checklist items all pass (email arrives, reset link works, login with new password works)

**4. Run §12C (second email smoke) the same way:**
- [ ] §12C checklist items all pass

**5. Return to §15E announcement gate** — both §2G and §12C must be ✅ before flipping to launched.

*End of script.*
