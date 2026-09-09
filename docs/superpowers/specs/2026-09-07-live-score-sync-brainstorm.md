# Live score sync (CFB Survivor + The Docket) — design brief for the brainstorm

**Status: SUPERSEDED (2026-09-09) by ADR-063 and `docs/designs/same-evening-finals.md`.**
Brad's rulings at the brainstorm: members want their verdict and week record the same
evening, not a running score mid-game; the surfaces already exist (the Docket ledger's
"this week" record, CFB per-game grading), only the cadence was wrong. What shipped is one
shared game-day `/scores` pass (`flask scores game-day`, `deploy/scores-gameday.timer`).
§5 (a live surface) and §6 (`live_state` columns) were dropped: The Odds API gives no
period or clock, and a 1-credit `/scores` call returns only live and upcoming games, so it
can never land a final. Kept for the option analysis and the budget arithmetic.

**Original status: design only. No code until Brad has ruled on the questions at the end.**
Prepared 2026-09-07 from the live automation, the Odds API client and the two games' data
models. Numbers are re-verified facts, not the handoff's guesses.

## 1. What "live" would add, and what it must not do

Today both games learn a result once a day (CFB Sun–Thu 08:00 CT once PR #195 lands — the
timer on `main` before it fired Sun/Mon only — Docket Tue 05:15 + Wed–Mon 08:00 CT, both
`daysFrom=3`). A member on Saturday afternoon sees LOCKED picks and nothing
else until the next morning. "Live" means a LOCKED pick shows the game's running score and
state (1st quarter, halftime, final pending) during the window, and the room says so
honestly: **nothing grades live.** Grading stays on the daily pass (CFB per game since
ADR-061; the Docket at week grade), because a score that is "final" in a feed can still be
corrected, and both rooms' doctrine treats a verdict as final and evidenced.

## 2. What already exists

| | CFB Survivor | The Docket |
|---|---|---|
| In-progress state modeled | `fetch_scores_for_week` splits `matched_completed` / `matched_in_progress` but **persists only completed** scores; `CfbGame` has `home_score`/`away_score`/`home_team_won`, no status/clock column | `services/scores.py::_apply_event` writes `home_score`/`away_score` on **every** run, final or not; `is_final` is one-way; `DocketGame` has no clock/period column either |
| Pre-deadline fetch | refused (`deadline has not passed yet`), so a Saturday-morning poll would do nothing for the week that is playing | allowed (the Sat 08:00 run is by design pre-deadline) |
| Surface for a locked pick | standings pick column (after PR C: reveal week + LOCKED/VERDICT chips); My Picks; `/cfb/results` | All Sheets (`.docket-sheet-line`, result words; "Final 17-31" caption); the sheet rail |
| Feed matching | `api_event_id`, then team-name fallback | `api_event_id` only (D22) |

## 3. The budget, re-verified

- The Odds API free tier: **500 credits/month.** `/scores` with `daysFrom` = **2 credits** per
  sport per call; `/scores` **without** `daysFrom` (live + upcoming only) = **1 credit**;
  `/events` free.
- Current pace after PR A: CFB ≈ 5 runs/wk × 2 = 10/wk; Docket ≈ 7 runs/wk × 2 sports × 2 = 28/wk;
  lines/setup ≈ 6–10/wk. **≈ 45/wk ≈ 195/month**, December worse (daily windows on both).
- Journal on 2026-09-07: 34 used, 466 remaining, day 7 of the month — consistent with the
  estimate once the new CFB runs are counted.

Live polling costs, at **1 credit per sport per poll** (no `daysFrom`):

| Cadence | CFB (Sat 11:00–23:30 CT, 12.5 h) | Docket NFL (Sun 12:00–23:30 CT; Thu + Mon 19:00–23:00) | Monthly total added |
|---|---|---|---|
| every 30 min | 25/Sat → ≈ 108/mo | 23 + 8 + 8 = 39/wk → ≈ 169/mo | **≈ 277/mo** |
| every 20 min | 38/Sat → ≈ 163/mo | 59/wk → ≈ 255/mo | ≈ 418/mo |
| every 60 min | 13/Sat → ≈ 56/mo | 12 + 5 + 5 = 22/wk → ≈ 95/mo | ≈ 151/mo |

Baseline ≈ 195 + 30-minute live ≈ 277 = **≈ 470/month on the free tier, before December**,
and the Docket's CFB Saturday would ride the same CFB poll only if the two games share one
call (they can: one `/scores` call per sport serves both rooms).

## 4. Options

1. **Hourly live on the free tier, shared calls.** One `americanfootball_ncaaf` poll per hour
   on Saturday and one `americanfootball_nfl` poll per hour on Sun/Thu/Mon, written to both
   games' rows from a single fetch (a small `utils/live_scores.py` that both services read).
   ≈ +151/mo (systemd ranges are inclusive: `Sun 12..23` is 12 polls, `Thu,Mon 19..23` five
   each). Honest cost: an hour-old score on a live page, which the page must say ("as of
   3:12 PM CT"). Fits the tier with ~150 credits of headroom, tighter in December.
2. **20–30-minute live on the paid tier.** The Odds API's first paid plan is 20,000
   credits/month for $30/month; every question above disappears, and the daily passes can run
   with `daysFrom=3` twice a day as cheap insurance. Cost is real money for a friends' club
   that currently runs on $0.
3. **A free scoreboard source for live-only reads** (ESPN's unofficial scoreboard JSON, no
   key, no published quota). Zero credits, but unofficial: no SLA, team names differ from The
   Odds API's (a second name map to maintain), and a breaking change lands on a Saturday.
   Grading would still use The Odds API, so a disagreement between the two is a new failure
   shape to design for.
4. **No live scores; make the daily pass richer instead.** Score at 17:00 CT on Saturday too
   (+2 credits/wk), so early-window verdicts land the same evening. Cheapest; not "live".

**Recommendation to bring to Brad:** option 1 now (it is the same code shape as option 2, and
the tier can be upgraded later by flipping the cadence), with option 4's Saturday-evening pass
included regardless because it improves the room even if live is rejected.

## 5. Surface sketch (both rooms), under the existing doctrine

- **CFB standings / My Picks:** a LOCKED pick keeps the hollow `.badge-pending` chip and gains a
  quiet score line under the team ("Georgia 14, Clemson 10 · in progress", `--text-secondary`,
  Teko digits). The Odds API gives no period or clock (§6), so "· 3rd" exists only under
  option 3's second source; option 1 shows "in progress" and the freshness line. No colour on
  the score: crimson is identity, outcome colours are for verdicts (§6.5–6.7). Page states its
  freshness once: "Scores as of 3:12 PM CT."
- **All Sheets:** the line's caption already carries "Final 17-31"; in progress it would carry
  "17-31 · in progress" (the period only with option 3) and never the result word (the
  engine's rule stays the only grader). The
  `Tally` gains nothing — no live win/loss counts, by the "no points before the week grades"
  rule (§7.13).
- **Lounge:** unchanged. Live is participation-depth content; the lounge owns orientation
  (DESIGN.md §3).

## 6. Data shape (if approved)

- One new nullable column per game table: `live_state` (String(24): e.g. `1Q 12:34`, `HALF`,
  `4Q 0:52`, `FINAL`) and `live_updated_at` (naive UTC). Alembic migration, called out in
  that PR. The Odds API `/scores` gives `completed` and the running `scores`; it does **not**
  give period/clock, so `live_state` would be "in progress" unless a second source is used.
  That fact alone may decide between options 1 and 3.
- The live pass never writes `home_team_won` (CFB) or `is_final` (Docket). Finalization stays
  with the daily pass, so a feed correction between the last live poll and the morning pass
  cannot grade the wrong way. The write contract, stated once: the live pass may update
  `home_score`/`away_score` and the two `live_*` columns and nothing else; a feed
  `completed=true` it sees is display-only (`live_state = FINAL`, the caption says "final
  pending"); `home_team_won` and `is_final` are written by the daily pass alone; and no
  grader reads `live_state` — it is a caption, never a status.
- A `live-scores.timer` per sport day (`Sat *-*-* 11..23:00` for CFB, `Sun 12..23`, `Thu,Mon
  19..23` for NFL), `Persistent=false` (a missed live poll is worthless later), preset
  `ignore` like the rest.

## 7. Questions for Brad (the brainstorm)

1. Is an hour-old score worth showing at all, or is live only worth doing at 20–30 minutes?
2. $30/month for the paid tier: yes, no, or "not this season"?
3. Is an unofficial scoreboard source acceptable for display-only reads if the Odds API still
   grades?
4. Which surface matters most: CFB standings, CFB My Picks, or All Sheets?
5. Should the Saturday-evening CFB scores pass (option 4) ship regardless?
