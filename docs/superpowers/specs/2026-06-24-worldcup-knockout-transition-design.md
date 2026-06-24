# World Cup Knockout-Transition Trio — Design

**Date:** 2026-06-24
**Status:** Approved (brainstorm) — ready for implementation planning
**Author:** Brad Hagstrom + Claude

## Context

The 2026 World Cup group stage is in progress (June 11–27); the Round of 32
begins ~June 28. Three enhancements ride the group→knockout transition:

1. **Ideal Lineup card** — show players the highest-scoring possible roster and
   its total, on the public Stats Hub.
2. **Knockout bracket readiness** — close a real gap in how knockout shells get
   populated, then rehearse the whole advancement→bracket→scoring flow and lock
   it with tests. *(Time-critical: must land before ~June 28.)*
3. **Group-stage recap email** — an admin-triggered, per-player email at bracket
   lock explaining how group advancement points landed and where each player
   stands entering the Round of 32. *(Fires at the same ~June 28 moment.)*

Features 2 and 3 are urgency-ordered ahead of Feature 1.

### Grounding facts (verified against the codebase)

- **Pick structure** (`world_cup_countries.py::TIERS`): tier-partitioned slots —
  T1 Favorites ×1.0 (pick 2), T2 Contenders ×1.5 (pick 1), T3 Dark Horses ×2.5
  (pick 2), T4 Underdogs ×4.0 (pick 2), T5 Wildcards ×7.0 (pick 2). Total 9.
- **Scoring** (`services/scoring.py`): a team's `multiplied_points = base_points
  × tier multiplier`; multiplier is constant within a tier. Advancement
  milestones: group winner +4, runner-up +3, best-third +1 (base). Knockout:
  R32 +8, R16 +11, QF +15, SF +19, 3rd/runner-up +8, champion +50 (base).
- **Advancement is admin-confirmed** at `/worldcup/admin/advancement`; a "Load
  from API" button pre-fills winner/runner-up/best-third radios per group from
  `fetch_advancement_proposal()`.
- **Gap found:** knockout *shell* population is 100% manual. `set_knockout.html`
  is a plain dropdown form with no API pre-fill. `fetch_advancement_proposal()`
  already computes `ko_pairings` (R32 only) but **nothing consumes them**, and
  R16/QF/SF/final are not proposed at all. Today an admin hand-assigns all 32
  knockout shells one at a time.
- **Score auto-apply** (`services/sync.py::sync_scores`, 30-min timer): once a KO
  shell has both teams assigned and the API marks it FINISHED, the result flows
  through `process_match_result()`. Shells without teams are skipped
  (`skipped_unassigned`). So **populating shells correctly is the prerequisite**
  for automated knockout scoring.
- **Admin-due notifications** (`services/sync.py::run_advancement_check`, hourly):
  emails the admin once per "episode" when group stage is complete-unconfirmed
  (`group_stage_complete_and_unconfirmed()`) or when a KO round is done but the
  downstream shells are empty (`ko_round_pending()`).
- **Stats Hub** (`routes.py::stats`): already builds `country_stats` and gates
  visibility (platform admins anytime, everyone else at the pick deadline).
- **Daily digest** (`services/notifications.py::send_daily_digests`): the
  per-scoring-day email; the new recap is a distinct, once-per-tournament email.

---

## Feature 1 — Ideal Lineup card (Stats Hub)

### What it is
A "global ideal" card on `/worldcup/stats`: the highest-scoring roster anyone
*could* have drafted (best team per tier slot) and what that roster would score.
No personalization (decided in brainstorm).

### Service
Add to `games/worldcup/services/stats.py`:

```python
def get_ideal_lineup(country_stats: list[dict]) -> dict | None:
    """Highest-scoring possible roster: top-N multiplied_points teams per tier.

    Pure — consumes the country_stats the stats route already builds (no new
    DB calls), mirroring get_tier_stats()/get_overview_kpis(). Returns None
    when the ideal total is 0 (pre-results) so the card stays hidden until
    points exist. Ties for the final slot in a tier are broken deterministically
    by name; the returned total_score is exact regardless.
    """
```

- For each `tier` in `TIERS`, sort that tier's countries by `total_score` desc,
  tiebreak by `name`, take the top `TIERS[tier]['picks']` (2/1/2/2/2).
- Return `{'teams': [...grouped by tier, each with name, iso_code, tier,
  multiplier, total_score...], 'total_score': <sum>}`, or `None` if the summed
  total is 0.
- Provably optimal: because slots are tier-partitioned and the multiplier is
  constant within a tier, greedy top-N per tier = global optimum.

### Route integration
In `routes.py::stats`, after `country_stats` is built, pass
`ideal_lineup=get_ideal_lineup(country_stats)` to the template. The page is
already admin-gated pre-deadline, so the card only ever appears post-deadline and
only when results exist.

### Template
Add a card to `templates/worldcup/stats.html`, rendered only when `ideal_lineup`
is truthy. Visual treatment is produced via the **impeccable** skill at build
time, conforming to WC body doctrine:
- White `.card` / `.wc-stat-card` on the bone substrate (Casual-Light).
- Teams grouped by tier; flags via `{% from '_flag.html' import flag with
  context %}`; Teko multiplier chips (`.wc-multiplier-chip` precedent).
- Total score is the focal figure.
- Working title "The Ideal Lineup." ("Perfect XI" is rejected — the roster is 9
  teams, not 11.) Final eyebrow/title/subhead copy is an impeccable decision.

### Tests (`tests/test_worldcup_stats.py`)
- Top-N-per-tier selection is correct (right slot counts, right teams).
- `total_score` equals the sum of the chosen teams' multiplied points.
- Returns `None` pre-results (all zero).
- Tiebreak determinism (two teams tied → stable choice; total unaffected).
- Route renders the card when results exist; omits it otherwise.

---

## Feature 2 — Knockout bracket readiness *(time-critical)*

### 2.1 — Bulk per-round "Load from API" (the fix)

**Service** — add to `games/worldcup/services/sync.py`:

```python
def fetch_bracket_proposal(target_stage: str) -> dict:
    """Read-only proposed team assignments for every shell of target_stage.

    Reads the football-data.org /matches feed, filters to target_stage, maps
    each API fixture to our shell via the existing api_fixture_id link (set by
    `sync --mode link`), and proposes home/away from the API's resolved teams.
    No DB writes. Returns matched proposals plus any shells it could not
    resolve, for admin review.
    """
```

- Shape (suggested):
  `{'target_stage': 'R16', 'proposals': [{'match_number', 'shell_id',
  'home_fifa', 'away_fifa', 'home_name', 'away_name', 'current_home',
  'current_away', 'already_set': bool}], 'unresolved': [...], 'api_error': None}`.
- Mapping primarily by `api_fixture_id` (KO shells get linked by `(stage,
  kickoff)` in `link_fixtures()`); fall back to `(stage, kickoff)` if a shell's
  `api_fixture_id` is null. Skip API fixtures whose home/away aren't both
  resolved yet (report as `unresolved`).
- Generalizes the dormant `ko_pairings` logic past R32. (The R32-only block in
  `fetch_advancement_proposal()` can stay for the advancement page, or R32 can
  route through this new function — implementation detail for the plan.)

**Admin route** — `/worldcup/admin/bracket/<target_stage>`:
- **GET** → review screen listing every shell in `target_stage` with proposed
  vs current assignment, plus any unresolved/conflict rows. No writes.
- **POST** → loop `set_knockout_teams(shell_id, home_fifa, away_fifa)` for each
  proposed pairing. **Skip shells already completed** (a result is recorded);
  idempotent (re-running with the same proposals is a no-op). Flash a summary
  (`N assigned, M skipped`).
- Decorated `@worldcup_admin_required`. Guard `target_stage` to the KO stages
  (`R32/R16/QF/SF/final/third_place`); reject `group`.

**Dashboard CTA** — `routes.py::admin_dashboard` surfaces a **"Populate <Round>
from API"** button for the round whose shells are empty once its feeder resolves:
- R32 unlocks after group advancement is confirmed for all 12 groups.
- R16/QF/SF unlock after the prior round completes (reuse `ko_round_pending()`).
- final + third_place unlock after SF completes.

**Fallback** — the existing per-shell `set_knockout.html` manual form is
**unchanged**; it remains the override for edge cases (bad API data, manual
correction). No per-shell "Load from API" button is added.

### 2.2 — Rehearsal

A documented dry-run proving the end-to-end flow on a local DB (the live API has
no KO pairings yet — group stage is still running — so this and the tests mock /
fixture the API feed):

1. `flask worldcup simulate-group-stage` → 72 group results.
2. Confirm advancement for all 12 groups (winner/runner-up/best-third).
3. Populate R32 via the new bulk flow (mocked API proposal).
4. Simulate R32 results → verify `sync_scores()` applies them and scores recalc.
5. Repeat populate→simulate for R16 → QF → SF → final + third_place.
6. Verify scoring parity at each step (stored totals = sum of ScoreEvents).

Capture the recipe in the spec/plan and (where useful) `.remember` for the live
run. The local DB (`ccc_local`) is freely manipulable; set it to a group-stage-
done / KO-empty state for the rehearsal, then **restore it to a LIVE state
afterward** so it mirrors the current production DB (Brad's standing preference —
prod is mid-tournament with knockouts imminent).

### 2.3 — Tests
- `fetch_bracket_proposal`: correct API→shell mapping; unresolved fixtures
  reported, not guessed; missing `api_fixture_id` falls back to (stage,kickoff);
  `api_error` surfaced (mock a `SyncError`).
- Bracket review→confirm route: auth-gated (platform + enrollment admin matrix);
  GET writes nothing; POST assigns all proposed shells; skips completed shells;
  idempotent re-run.
- Advancement→scoring regression (extend existing locks if needed).

---

## Feature 3 — Group-stage recap email *(fires at bracket lock)*

### Trigger & guard
Admin-triggered, two entry points:
- **Button** on the admin dashboard: `POST /worldcup/admin/send-group-recap`.
- **CLI**: `flask worldcup send-group-recap`.

**Guard** — only sends when group advancement is fully confirmed. Add a helper
(e.g. `services/sync.py` or `services/elimination.py`):
`group_advancement_fully_confirmed(season_year) -> bool` — true when group stage
is complete and every non-eliminated team has an `advancement_method` set (no
group left unconfirmed). If not satisfied, the route/CLI refuses with a clear
message.

**Idempotency** — a marker file (mirrors `services/sync.py::_notify_once`,
e.g. `.wc_group_recap_sent`) records the send. A second press flips the button
copy to "Resend (last sent <date>)" and shows a confirm dialog, so an accidental
double-blast takes a deliberate action.

### Per-player content (personalized; their teams flagged)
1. **Framing** — "The group stage is a wrap."
2. **Your teams that advanced** — for each pick whose team advanced: flag, name,
   tier ×multiplier, advancement method (Group winner / Runner-up / Best 3rd),
   and **advancement points earned** = base milestone (+4/+3/+1) × tier
   multiplier. Derive from `team.advancement_method` +
   `scoring._apply_advancement_points` (or the `source == 'advancement'`
   `ScoreEvent` from `compute_team_score_events`). These are the highlighted
   teams.
3. **Your teams that are out** — flag + name, greyed.
4. **How group points worked** — the +4 / +3 / +1 explainer (the core ask).
5. **Where you stand entering the Round of 32** — total score + competition rank
   (reuse `notifications._competition_rank`).
6. **What's at stake next** *(the "anything else relevant")* — the knockout
   points ladder (R32 +8 → champion +50, × multiplier) and a one-line nudge that
   surviving high-multiplier picks carry the biggest upside.

### Implementation
- `send_group_stage_recap() -> dict` in `services/notifications.py`, structured
  like `send_daily_digests` (iterate `picks_submitted` enrollments with email;
  build per-player advancement breakdown; render HTML + plain text; return a
  summary dict).
- New `templates/worldcup/email/wc_group_recap.j2` (table layout + inline styles,
  consistent with existing WC emails) + a `_plain_*` fallback in
  `notifications.py`.
- Admin route `POST /worldcup/admin/send-group-recap` (`@worldcup_admin_required`,
  CSRF, guard + marker), button on `admin/dashboard.html`.
- CLI `send-group-recap` in `games/worldcup/cli.py`.

### Tests
- Guard blocks the send when ≥1 group is unconfirmed; allows it when all are.
- Per-player advancement breakdown: correct method + points for each advanced
  pick; correct tier multiplier applied.
- Eliminated picks listed; standing/rank correct.
- Idempotency marker (second send flagged as resend).
- Plain-text fallback parity with HTML.
- Route auth-gated; no email config in test → graceful.

---

## Sequencing

Three PRs, urgency-ordered (each carried through its CodeRabbit cycle to merge in
its own session, per project practice; UI work loads impeccable):

1. **Feature 2 — bracket readiness** (must precede ~June 28 R32 kickoff).
2. **Feature 3 — group-stage recap email** (fires at the same bracket-lock
   moment).
3. **Feature 1 — ideal lineup card** (independent, low-risk).
4. **CLAUDE.md pass** — once all three land, run the
   `claude-md-management:claude-md-improver` skill to fold the new conventions
   into `CLAUDE.md` (the bulk-bracket "Load from API" admin route + admin-confirmed
   review-then-write extension, the `send-group-recap` admin/CLI trigger + guard +
   marker, and the `get_ideal_lineup` Stats-Hub service/card). Keep pattern locks
   accurate; don't duplicate what tests already enforce.

`writing-plans` will phase these into the implementation plan.

## Out of scope
- Personalized "points left on the table" / per-player gap on the ideal lineup
  (chose global-only).
- Auto-firing the recap email from a timer (chose admin-triggered).
- Per-shell "Load from API" button (bulk + existing manual form covers it).
- A season-end / champion-crowned wrap-up email (chose bracket-lock only).
- Any new auto-written advancement/bracket path — advancement and bracket
  population stay admin-confirmed (review-then-write).
