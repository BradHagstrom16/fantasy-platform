# World Cup Results & Advancement Automation — Design Spec

**Date:** 2026-06-02
**Branch:** TBD (e.g. `worldcup/results-automation`)
**Ships as:** one PR (backend service + CLI + schema + admin pre-fill + deploy artifacts)

The World Cup is live and users are joining; the tournament kicks off
**2026-06-11** (9 days out). Today, every match result, group advancement, and
knockout-bracket assignment is entered by hand (`flask worldcup process-match`,
`/admin/advancement`, `/admin/set_knockout`). This spec automates the
low-risk, high-frequency parts (match results) and assists the high-risk parts
(advancement + bracket) with API-fed, admin-confirmed proposals — without ever
reimplementing the scoring engine, which already derives everything idempotently
from match data.

Full suite baseline: `ENVIRONMENT=testing venv/bin/python -m pytest tests/` must
be green before and after the PR.

---

## Locked decisions (from brainstorming)

1. **Trust model — tiered.** Final match scores apply **automatically**;
   group advancement + knockout-bracket resolution are fetched, **staged as a
   pre-filled admin proposal, and confirmed with one click** (you are the safety
   net on the calls that can silently corrupt everyone's score).
2. **Data source — football-data.org, free tier ($0).** Verified live on
   2026-06-02: competition `WC`, currentSeason `2026-06-11 → 2026-07-19`,
   **104 matches**, full 48-team stage structure (incl. `LAST_32`), **12 group
   standings on the free tier**, clean team names. One request returns all 104
   matches, so the 10 req/min free limit is a non-issue. (API-Football's free
   tier is gated to seasons 2022–2024 and cannot serve 2026 — rejected.
   TheSportsDB free key lacks clean WC league + standings — rejected.)
3. **Advancement logic — trust API, admin confirms.** Read group standings +
   resolved knockout matchups from the API; present them pre-filled in the
   existing admin forms with a "loaded from API — review before confirming"
   banner. We do **not** reimplement FIFA's best-third → R32-slot lookup table;
   once FIFA assigns the bracket, the API's match list shows the actual pairings
   and we read them.
4. **Score scope — finals only.** A match is applied only once the API reports it
   `FINISHED`. No live/in-progress ticker (matches the current scoring engine +
   UI). A live ticker is a possible future feature, explicitly out of scope.
5. **Notifications — admin-only, three kinds:** advancement-ready-to-confirm,
   errors/API-failures, and a daily results digest. **Player-facing recap emails
   are a desired future enhancement, deferred from this scope.**
6. **Scheduler — systemd timer on the droplet.** Consistent with the existing
   systemd-managed Gunicorn unit; gives `systemctl status` + `journalctl` run
   logs and no overlapping runs. The triggered work is a plain
   `flask worldcup sync` command, so the trigger mechanism is decoupled and
   trivially swappable.

---

## Architecture overview

Mirrors the proven CFB sync shape (`games/cfb/services/automation.py` +
`score_fetcher.py`) adapted to the World Cup data model. **Match data remains the
single source of truth.** The automation has exactly two jobs:

- **Feed final match results in** → call the existing `process_match_result()`,
  which runs the existing idempotent `recalculate_all_scores()`. (Low-risk tier,
  fully automatic.)
- **Pre-fill the existing advancement/bracket admin forms** from API data → you
  confirm → the existing `apply_group_advancement()` / `set_knockout_teams()`
  run. (High-risk tier, human-in-the-loop.)

Nothing in the scoring engine, ranking, elimination, or home-context builders
changes. The new code is additive and isolated to a sync service, a CLI command,
two nullable columns, an admin pre-fill, and deploy artifacts.

---

## 1. Schema — external-ID mapping (Alembic migration)

### Intent
Link our 104 match shells and 48 team rows to their football-data.org
counterparts so syncs match by stable ID, not fragile name comparison.

### Decision
Two nullable columns, same idea as CFB's `api_event_id`:

- `WorldCupMatch.api_fixture_id` — `Integer`, nullable, indexed. football-data.org
  match `id`.
- `WorldCupTeam.api_team_id` — `Integer`, nullable. football-data.org team `id`.

Nullable because KO shells and TBD teams exist pre-resolution, and because the
link step runs once after deploy. Flask-Migrate only; review the generated file
before `db upgrade`; commit migration with the model change.

---

## 2. Sync service — `games/worldcup/services/sync.py` (new)

### Constants / config
- Base URL `https://api.football-data.org/v4/`, header `X-Auth-Token`.
- New env var `FOOTBALL_DATA_API_KEY`, read via `current_app.config.get(...)`
  **with a matching `os.environ.get('FOOTBALL_DATA_API_KEY')` line in `config.py`'s
  base `Config`** (per the config-plumbing gotcha — without it the value is
  silently `None`).
- `COMPETITION_CODE = 'WC'`, `SEASON = 2026`.
- `STAGE_MAP` (football-data.org → ours): `GROUP_STAGE→group`, `LAST_32→R32`,
  `LAST_16→R16`, `QUARTER_FINALS→QF`, `SEMI_FINALS→SF`, `THIRD_PLACE→third_place`,
  `FINAL→final`.
- `FINISHED_STATUS = 'FINISHED'`.
- `TEAM_TLA_OVERRIDES` — small dict for any `tla`→`fifa_code` mismatch (built
  during link verification; most teams map `tla == fifa_code` directly).

### Functions

**`link_fixtures()` — idempotent, run once after deploy.**
Fetch `GET /competitions/WC/matches`. For each API match, find our shell by
`(stage, kickoff_utc)` (and team identity for group matches); store
`api_fixture_id`. Map teams by `tla` → `fifa_code` (override dict for
mismatches); store `api_team_id`. **Verify-then-trust:** print every unmatched
fixture and every unmapped team; write nothing silently. Re-runnable (skips
already-linked rows).

**`sync_scores()` — low-risk tier, automatic.**
Fetch `GET /competitions/WC/matches`. For each API match with `status ==
'FINISHED'` whose linked shell is **not yet `is_completed`**:
- `home_score`/`away_score` ← `score.fullTime.{home,away}`.
- Group stage: `is_draw` ← `score.winner == 'DRAW'`; winner auto-derived by
  `process_match_result` from scores.
- Knockout: `winner_fifa_code` ← team behind `score.winner` (`HOME_TEAM`/
  `AWAY_TEAM`); `extra_time` ← `score.duration in (EXTRA_TIME, PENALTY_SHOOTOUT)`;
  `penalties` ← `score.duration == PENALTY_SHOOTOUT` (or `score.penalties`
  present).
- Call `process_match_result(...)` (which recalcs). Already-completed shells are
  skipped (the helper refuses them) → idempotent.
- Collect applied results for the daily digest. Return a summary dict.

**`fetch_advancement_proposal()` — high-risk tier, read-only (no DB writes).**
Fetch `GET /competitions/WC/standings` (12 group tables) + the resolved KO
matchups from `/competitions/WC/matches`. Return a structured proposal:
- Per group: positions 1 & 2 → `group_winner` / `runner_up`; supporting
  pts/GD/GF/played so the admin can sanity-check.
- Best-thirds + R32 slotting: inferred from which teams appear in the resolved
  `LAST_32` matchups (we read FIFA's assignment, not recompute it).
- KO shell fills: `(api_fixture_id → home_fifa_code, away_fifa_code)` for each
  resolved knockout match.

**Detection helpers** (read-only, drive notifications):
- `group_stage_complete_and_unconfirmed()` — all 72 group matches `is_completed`
  AND ≥1 group still has `advancement_method` unset on a non-eliminated team.
- `ko_round_complete_and_next_empty()` — a KO round's matches all `is_completed`
  AND the next round's shells have null `home_team_id`/`away_team_id`.

### Notifications
A small `_send_admin_email(subject, body)` mirroring CFB's helper (to
`EMAIL_ADDRESS`, `[World Cup]` subject prefix, routed through
`utils/email.send_platform_email`). Three triggers:
- **Advancement ready** — when a detection helper flips true. Links to
  `/worldcup/admin/advancement` (or set-knockout). The key prompt of the tiered
  model.
- **Errors / API failures** — API non-200/timeout, or unmatched fixtures during a
  scores run.
- **Daily digest** — once per day, the matches finalized + scores applied that
  day. (Idempotent: a per-day "digest sent" guard, e.g. keyed on local date.)

---

## 3. CLI — `flask worldcup sync --mode {link|scores|advancement|status}`

In `games/worldcup/cli.py`, mirroring `flask cfb sync --mode ...`:
- `link` → `link_fixtures()` (one-time, prints mapping report).
- `scores` → `sync_scores()` (the timer's main job).
- `advancement` → run detection helpers + send the advancement-ready email if
  triggered (never writes).
- `status` → print link coverage (matches/teams linked), last-sync info,
  completed-match count, API reachability.

All command lines in deploy artifacts/cron carry `ENVIRONMENT=production` per the
three-layer defense-in-depth rule.

---

## 4. Admin UI — pre-fill existing forms (no new routes)

### Intent
Turn the existing manual advancement + set-knockout screens into one-click
confirmations of an API-sourced proposal.

### Decision
Enhance the existing `/worldcup/admin/advancement` and
`/worldcup/admin/set_knockout` templates/routes:
- A **"Load from API"** action calls `fetch_advancement_proposal()` and pre-fills
  the form fields (group winner / runner-up / best-third selects; KO home/away
  team selects).
- A visible **source banner**: "Loaded from football-data.org — review before
  confirming," showing the supporting standings data (pts/GD/GF) so the admin
  verifies against reality before submitting.
- Submitting calls the **unchanged** `apply_group_advancement()` /
  `set_knockout_teams()`. No new write path; the audited manual logic is the only
  thing that mutates state.

No new persistence (no proposal table) — the proposal is computed on demand at
render time. Keeps the high-risk surface running through already-hardened code.

---

## 5. Scheduler — systemd timer (deploy artifacts)

**Six new files in `deploy/`** — three `service`+`timer` pairs, each mirroring the
existing `deploy/fantasy-platform.service` pattern (`User=deploy`, `EnvironmentFile`,
`Environment=ENVIRONMENT=production`, hardening), so operators enable three units:
- `deploy/worldcup-sync.{service,timer}` — `--mode scores`, `OnCalendar=*:0/30`
  (every 30 min). The oneshot loads `.env` via `EnvironmentFile` and runs as the
  `deploy` user; `TimeoutStartSec=5m` bounds a stuck run under the timer interval.
- `deploy/worldcup-advancement.{service,timer}` — `--mode advancement`, hourly
  (`OnCalendar=*:05`), detection/notify only (never writes).
- `deploy/worldcup-digest.{service,timer}` — `--mode digest`, daily at 22:30 with
  `TimeZone=America/Chicago` so the firing matches `run_digest`'s CT "today" window.

Setup is documented as exact copy/enable commands (`systemctl enable --now`) in
the runbook (Brad is new to VPS ops — no assumed knowledge). Logs via
`journalctl -u worldcup-sync` (and the `-advancement` / `-digest` units).

### API budget (stays well under the free tier)
football-data.org free tier (registered): **10 requests/minute, no daily cap**
(the "100 per 24h" applies only to unauthenticated callers). Our usage:
- **Scores timer:** 1 request per 30-min tick → ~48/day, never >1 in any minute.
  One poll = one request regardless of match count (`/competitions/WC/matches`
  returns all 104), so usage is flat — it never spikes on a heavy match day.
- **Advancement-detection timer:** reads our **own DB** (match-completion counts),
  **0 API calls** normally; 1–2 only on the rare day a stage finishes.
- **One-time `link`:** 1 request. **Admin "Load from API":** 2 requests per manual
  click (matches + standings), infrequent.

Worst realistic minute ≈ 3 requests (a scores tick coinciding with an admin
"Load from API") against the 10/min ceiling — ~3× headroom, and timers are
30 min / 60 min apart so they never burst together. Defensive guard: the sync
reads football-data.org's rate-limit response headers (`X-Requests-Available-Minute`
+ reset) and backs off if the minute budget runs low. No match-window gating
needed for quota. (Optional later optimization: early-return when no match is
scheduled "today," to keep logs quiet — not required.)

---

## 6. Edge cases & known limitations (accepted)

- **Score corrected after we applied it:** `process_match_result` refuses
  already-completed matches, so a post-finalization API correction is handled
  manually (admin edits the match, runs `flask worldcup recalc`). Same posture as
  CFB. Rare; documented in the runbook.
- **Fixture mapping is the riskiest step** — `link_fixtures()` is verify-then-trust
  (prints unmatched, never guesses). Run + eyeball once before 2026-06-11. Match
  on `(stage, kickoff_utc)`; if kickoff times drift slightly between our seed and
  the API, fall back to team-identity match for group stage and flag the rest.
- **Team-name / `tla` drift** — handled by `api_team_id` (stored after first link,
  so later syncs use IDs) plus the small `TEAM_TLA_OVERRIDES` dict.
- **KO winner with no draw:** knockout `score.winner` is always HOME/AWAY post-
  completion (ET/penalties resolved); we never pass `is_draw=True` for non-group
  stages.
- **API outage:** a failed run logs + emails the error and changes nothing;
  the next timer tick retries. Scores are catch-up safe (we re-scan all matches
  each run and apply any newly-`FINISHED` ones).

---

## 7. Testing (TDD, API mocked)

New `tests/test_worldcup_sync.py` (+ additions to existing files where natural),
all with mocked HTTP (no live API dependency):
- `link_fixtures`: happy-path mapping; unmatched-fixture path; `tla` override path;
  re-run idempotency.
- `sync_scores`: group win / draw apply; knockout ET + penalties flag mapping;
  `FINISHED`-only gating (ignores `IN_PLAY`/`TIMED`); skip already-completed;
  idempotent re-run; score totals reconcile via existing scoring parity locks.
- `fetch_advancement_proposal`: standings → winner/runner-up parsing; best-third
  inference from resolved LAST_32; KO shell-fill mapping; read-only (no writes).
- Detection helpers: group-complete-and-unconfirmed true/false; KO-round triggers.
- Notifications: each trigger fires the correct email once (digest per-day guard).
- Stage map + status constants: exhaustive map coverage (lock against silent
  fallthrough on a new stage string).

---

## 8. Out of scope (explicit)

- Player-facing recap/standings emails (desired future enhancement — deferred).
- Live/in-progress score ticker + any new live UI.
- Automating the high-risk advancement writes (stays human-confirmed by design).
- CFB/Golf sync changes (untouched).

---

## 9. Pre-tournament checklist (runbook, before 2026-06-11)

1. Add `FOOTBALL_DATA_API_KEY` to server `.env` + `config.py` base `Config`.
2. Deploy; run `flask db upgrade` (new columns).
3. Run `flask worldcup sync --mode link`; **eyeball the mapping report** — expect
   104 fixtures linked, 48 teams mapped, zero unmatched. Fix any `tla` override.
4. Install + enable the systemd timer(s); confirm `systemctl status` +
   `journalctl -u worldcup-sync` show a clean dry tick.
5. Run `flask worldcup sync --mode status` — confirm link coverage + API reach.
6. Confirm admin email delivery (trigger a test error path).
