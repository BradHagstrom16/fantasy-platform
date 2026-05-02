# Spec B Follow-up — CCC Home Redesign Hardening

**Date:** 2026-05-01
**Status:** Approved
**Initiative:** CCC Redesign (Specs A → B → C); follow-up PR for Spec B
**Predecessor:** Spec B — CCC Home Redesign (`docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`), PR [#3](https://github.com/BradHagstrom16/fantasy-platform/pull/3) (open at time of writing)
**Branch:** `redesign/ccc-home` (worktree at `../fantasy-platform-ccc-home`) — same branch, additional commits stacked on PR #3
**Successors:** Spec C — World Cup Reskin

---

## 1. Context

PR #3 ships Spec B's four-state home page. CodeRabbit's review surfaced 11 actionable items (4 Major, 7 Minor); a separate hand-eyed review surfaced three test-coverage and UX gaps that the implementation explicitly deferred to a follow-up. This spec covers all of them in a single tight PR so Spec B can merge clean.

Nothing in this spec changes Spec B's architecture: state detection, the `build_home_context()` seam, the `WorldCupRankSnapshot` model, the per-state partials, and the `home-shell--<state>` CSS scoping all stand. Every change here is either:

- **a fix** to an existing file (correctness, consistency, or doc accuracy), or
- **a test** that closes a coverage gap on Spec B code.

The single feature-flavored change is a draw branch in the live-state recent-results strip, which surfaces points that the scoring engine already awards but the UI was hiding behind a misleading "NO POINTS" label.

### Why now, not after merge

Three reasons:
1. The clock-consistency fix (CR1) and the deterministic-ordering fixes (CR2, CR8) plug small but real correctness holes — tied scores can shuffle row order between requests, and `WC_FAKE_NOW` doesn't fully take in dev/test renders. Both classes of issue are subtle and easier to fix while context is hot.
2. The "NO POINTS" misattribution actively shows wrong information to users on draws, and group-stage draws will start happening on day 1 of the live state.
3. The route-level rendering tests are missing entirely — `_home_live.html`, `_home_post.html`, `_dossier_card.html` (~122 lines), `_recent_results.html`, and `_champion_banner.html` are never rendered through `/` in any test. A follow-up that adds them lands as part of the PR's verification narrative rather than a separate post-merge debt.

---

## 2. Scope

15 deltas across 12 files, organized by category. Items keyed `CR<n>` reference CodeRabbit's numbered comments on PR #3.

### 2a. CodeRabbit fixes (10)

| # | File | Item | CR ref | Severity |
|---|---|---|---|---|
| 1 | `games/worldcup/services/state.py` + `core/main/home_context.py` | Single `now_utc()` per builder; rename `_now_utc()` → `now_utc()` (public) and import in builders. Drives `court_line` weekday, deadline-delta proximity copy, and the returned `now_utc` value. | CR1 | Major |
| 2 | `core/main/home_context.py` | Both leaderboard queries (`_context_live` and `_context_post`) add `WorldCupEnrollment.id.asc()` as secondary sort. | CR2 | Major |
| 3 | `core/main/templates/main/_view_cta_card.html` | Eyebrow becomes `{{ '◇ Tournament complete' if state == 'post' else '◇ Tournament in session' }}`. (`state` is already inherited from `index.html`'s `render_template` call.) | CR3 | Minor |
| 4 | `docs/superpowers/plans/2026-04-21-production-deployment.md` | Fix CST/CDT direction on the `05:05 UTC` snapshot cron line; bump "six entries" → "seven entries" in the matching expectations line. | CR4 | Minor |
| 5 | `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md` | Replace `captured_at`/`captured_at_utc` DateTime references with `captured_date` Date in the schema section and Gate 4. Note `unique_worldcup_snapshot_per_day` constraint. | CR5 | Minor |
| 6 | `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md` | Cron-note timezone direction: `05:05 UTC = 23:05 CST prior day (winter) / 00:05 CDT (summer)`. | CR6 | Minor |
| 7 | `games/worldcup/cli.py` | At top of `snapshot_ranks`: `if backfill < 0: raise click.BadParameter('--backfill must be >= 0')`. | CR7 | Minor |
| 8 | `games/worldcup/cli.py` | Snapshot-CLI enrollment query adds `WorldCupEnrollment.id.asc()` as secondary sort — prevents fake rank movement on tied scores. | CR8 | Major |
| 9 | `static/css/style.css` | `.home-shell .podium-name` swaps deprecated `word-break: break-word` for `word-break: normal; overflow-wrap: anywhere`. | CR9 | Minor |
| 10 | `tests/test_home_context.py` | Two existing builder tests (`test_context_pre_unenrolled`, `test_context_live_enrolled_basic`) gain a `ctx['now_utc']` assertion proving the `WC_FAKE_NOW` seam is honored. | CR10 | Minor |

CodeRabbit's 11th item ("restore rendered-template smoke tests" on `tests/test_homepage_sections.py:98-104`) is folded into category 2b — the new route-level tests cover that surface more thoroughly than the originals did.

### 2b. New tests

| # | File | What |
|---|---|---|
| B1 | `tests/test_home_routes.py` (new) | Seven route-level rendering tests, one per logical home state, hitting `client.get('/')` with `WC_FAKE_NOW` set and asserting state-specific HTML markers. |
| B2 | `tests/test_worldcup_snapshot_cli.py` (new) | Four CLI tests via `app.test_cli_runner()`: idempotency, `--backfill` writes N+1 rows in descending date order, negative-backfill rejected, tie ordering deterministic across runs. |

### 2c. UX fix

| # | File | What |
|---|---|---|
| C1 | `core/main/templates/main/_recent_results.html` + `core/main/home_context.py` + `games/worldcup/services/scoring.py` + `static/css/style.css` | Three-way win / draw / loss branch in the per-result strip. Scoring helper `points_for_pick_on_match()` added to `scoring.py`. `_context_live` enriches each `your_pick_results` item with `points_earned` and `is_draw`. New `.match-foot-status--draw` CSS rule (gold/amber accent). |

### 2d. Hand-flagged consider items

| # | File | What | Decision |
|---|---|---|---|
| D1 | `core/main/home_context.py` | Order `recent_results` by `kickoff_utc.desc()` instead of `match_number.desc()`. | INCLUDE — verified all matches in `match_schedule.py` have `kickoff_utc` set; knockout `match_number` is bracket position, not chronological. |
| D2 | `core/main/home_context.py` | Cache `now_utc()` per request on Flask `g`. | SKIP — premature; item #1 already collapses each builder to a single call, which addresses the actual semantic risk without adding `g`-scoped infrastructure. |
| D3 | `static/js/countdown.js` | Replace four silent early returns with `console.warn('[countdown] …')`. | INCLUDE — ~4-line change with real debugging value. |

---

## 3. Key implementation decisions

### 3a. `now_utc()` is exposed, not parameter-threaded

Rename `games/worldcup/services/state.py::_now_utc()` → `now_utc()`. Both `_context_pre()` and `_context_live()` import it and call it exactly once at the top of the builder. The function reads its own `WC_FAKE_NOW` env-var seam, so the test harness controls time without any signature changes to `build_home_context()`.

```python
# core/main/home_context.py
from games.worldcup.services.state import now_utc

def _context_pre(user, enrollment) -> dict:
    now = now_utc()
    now_local = now.astimezone(WORLDCUP_TZ)
    delta = TOURNAMENT_DEADLINE_UTC - now
    # ... court_line uses `now_local.strftime(...)` and `delta` ...
    return {..., 'now_utc': now, ...}

def _context_live(user, enrollment) -> dict:
    now = now_utc()
    weekday = now.astimezone(WORLDCUP_TZ).strftime('%A')
    # ...
```

`_context_post()` doesn't currently use a clock; no change needed.

The internal `worldcup_state()` callsite of `_now_utc()` stays — it just calls the now-public name.

### 3b. `points_for_pick_on_match()` lives in `scoring.py`

CLAUDE.md is explicit: *"`games/worldcup/services/scoring.compute_team_score_events` (per-team) and `compute_match_attribution` (per-match) are the single source of truth for scoring breakdowns."* This helper is the per-pick-per-match analogue and belongs in the same module.

```python
# games/worldcup/services/scoring.py
def points_for_pick_on_match(pick: WorldCupPick, match: WorldCupMatch) -> float:
    """Multiplied points the pick earns from this completed match. 0.0 if no scoring event."""
    if not match.is_completed:
        return 0.0
    multiplier = TIERS[pick.tier]['multiplier']
    if match.stage == 'group':
        if match.is_draw:
            return float(GROUP_DRAW) * multiplier
        if match.winner_team_id == pick.team_id:
            return float(GROUP_WIN) * multiplier
        return 0.0
    # Knockout — no draws (winner_team_id always resolved post-completion)
    if match.winner_team_id == pick.team_id:
        return float(KNOCKOUT_POINTS.get(match.stage, 0)) * multiplier
    return 0.0
```

`_context_live` consumes it. The existing `picks_by_enr[enrollment.id]` provides the user's picks; lookup-by-team-id via a small dict.

```python
# core/main/home_context.py — inside _context_live, after picks_by_enr is built
user_picks_by_team_id: dict[int, WorldCupPick] = {}
if is_enrolled:
    for p in picks_by_enr.get(enrollment.id, []):
        user_picks_by_team_id[p.team_id] = p

# ... then in the recent_results loop:
for match in recent_results:
    roster_match = None
    points_earned: Optional[float] = None
    if match.home_team_id in user_team_ids:
        roster_match = {'team_id': match.home_team_id, 'side': 'home'}
        pick = user_picks_by_team_id[match.home_team_id]
        points_earned = points_for_pick_on_match(pick, match)
    elif match.away_team_id in user_team_ids:
        roster_match = {'team_id': match.away_team_id, 'side': 'away'}
        pick = user_picks_by_team_id[match.away_team_id]
        points_earned = points_for_pick_on_match(pick, match)
    your_pick_results.append({
        'match': match,
        'roster_match': roster_match,
        'points_earned': points_earned,
        'is_draw': match.is_draw,
    })
```

### 3c. Draw branch in `_recent_results.html`

Three-way conditional. Branches off `points_earned` truthiness, then disambiguates win vs draw via `is_draw`.

```jinja
{% if item.points_earned and item.points_earned > 0 %}
  {% if item.is_draw %}
    <div class="match-foot-status match-foot-status--draw">
      DRAW · +{{ '%.0f'|format(item.points_earned) }} {% if item.points_earned == 1 %}PT{% else %}PTS{% endif %}
    </div>
  {% else %}
    <div class="match-foot-status match-foot-status--win">+ POINTS EARNED</div>
  {% endif %}
{% else %}
  <div class="match-foot-status match-foot-status--loss">NO POINTS</div>
{% endif %}
```

CSS: `.match-foot-status--draw` follows the same shape as `--win` and `--loss` but with a CCC-gold accent (token: `var(--gold-500)` or equivalent — exact token chosen during implementation against the existing palette in `tokens.css`). Visual slot is the same; only color and text differ.

The existing `won` boolean computation is removed — the template no longer needs to recompute scoring; `_context_live` is the source of truth.

### 3d. Test factories — per-file, no shared fixtures

`tests/test_home_routes.py` and `tests/test_worldcup_snapshot_cli.py` each declare their own `_make_user`, `_make_enrollment`, and (where needed) `_seed_match` helpers — same shape as the existing `tests/test_home_context.py`. ~25 lines duplicated per file. We extract to `conftest.py` if and when a third consumer appears.

### 3e. Recent-results ordering switch

`_context_live` line 262 changes from `order_by(WorldCupMatch.match_number.desc())` to `order_by(WorldCupMatch.kickoff_utc.desc())`. Verified: every match in `games/worldcup/match_schedule.py` ships with a non-null `kickoff_utc`, including all R32/R16/QF/SF/third_place/final shells. Knockout `match_number` is bracket position; for chronological order during the live state we want kickoff time.

---

## 4. Test plan

### 4a. `tests/test_home_routes.py` — 7 tests

Each test seeds the minimum required state, sets `WC_FAKE_NOW` where applicable, attaches a session cookie via `client.session_transaction()`, calls `client.get('/')`, and asserts `200` plus state-specific HTML markers in `resp.data`.

| Test | Seed | Markers asserted |
|---|---|---|
| `test_home_renders_logged_out` | (none) | `home-shell--out`; `Join the Club` (logged-out CTA token from `_home_out.html`) |
| `test_home_renders_pre_unenrolled` | user, no enrollment | `home-shell--pre`; `Join the World Cup pool` (token from `_join_cta_card.html`); `data-deadline-utc=` countdown markup |
| `test_home_renders_pre_enrolled_no_picks` | user + enrollment, `picks_submitted=False` | `home-shell--pre`; `Seal Your Roster` (token from `_submit_picks_cta.html`) |
| `test_home_renders_pre_enrolled_sealed` | user + enrollment + 1 pick + `picks_submitted=True` | `home-shell--pre`; `data-deadline-utc=`; the picked team's FIFA code |
| `test_home_renders_live_unenrolled` | user, no enrollment, `WC_FAKE_NOW='2026-06-15T00:00:00Z'` | `home-shell--live`; `cta-card--view`; eyebrow `Tournament in session` (proves CR3 live branch) |
| `test_home_renders_live_enrolled` | user + enrollment + 1 pick + 1 completed group match where the pick rosters one side | `home-shell--live`; `Your Dossier`; `Recent Results`; the picked team's FIFA code in the result strip |
| `test_home_renders_post_with_champion` | user + enrollment + 1 pick + match #104 completed with winner | `home-shell--post`; `The Final Standings`; champion team display name; `Tournament complete` (proves CR3 post branch) |

Marker-asserts favor structural CSS hooks (`home-shell--live`, `cta-card--view`) over copy strings, which are more likely to drift. Copy strings used only when they're the load-bearing thing the partial encodes (e.g., `Tournament in session` vs `Tournament complete` is the entire content of CR3).

### 4b. `tests/test_worldcup_snapshot_cli.py` — 4 tests

Use `app.test_cli_runner().invoke(snapshot_ranks, [...])` so we can assert exit codes + output, not just side effects.

| Test | Setup | Action | Assertion |
|---|---|---|---|
| `test_snapshot_idempotent_same_day` | 2 enrollments, 0 snapshots | invoke twice with no args | first run: 2 rows; second run: 0 new rows; total `WorldCupRankSnapshot.query.count() == 2` |
| `test_snapshot_backfill_writes_n_plus_one_descending` | 2 enrollments | invoke with `--backfill 3` | 8 rows total (2 enrollments × 4 days); for each enrollment, dates are 4 distinct values: max == today, min == today-3 |
| `test_snapshot_negative_backfill_rejected` | (none) | invoke with `--backfill -1` | exit code != 0; result output mentions `--backfill must be >= 0`; row count unchanged (0) |
| `test_snapshot_tie_ordering_deterministic` | 3 enrollments all with `total_score=10.0`, distinct ids | invoke; capture (eid, rank) pairs; delete all snapshot rows; invoke again | both runs produce identical `(eid, rank)` ordering |

### 4c. `tests/test_home_context.py` — 2 augmented tests (CR10)

The existing `test_context_pre_unenrolled` and `test_context_live_enrolled_basic` each gain one assertion:

```python
expected_now = datetime(2026, 5, 1, tzinfo=timezone.utc)  # or 6, 15 for live
assert ctx['now_utc'] == expected_now
```

Proves `WC_FAKE_NOW` flows from env-var → `now_utc()` → builder → context.

### 4d. Coverage delta

Spec B PR #3 ships with 124 tests (PR description math: 119 prior + 10 new − 5 obsolete). This follow-up adds 15 and modifies 2 on top of that baseline. New total: **139**. No tests are removed.

---

## 5. Out of scope (explicitly)

- **`_now_utc()` per-request `g`-caching** (D2) — premature; current per-builder single-call pattern is sufficient.
- **Render-test sparkline edge cases** (1 data point, exactly 7, more than 7) — `_dossier_card.html` sparkline rendering is already code-verified in PR #3's manual checklist; the route tests don't exercise these branches.
- **`_tagline_for` 9-branch coverage** — the function is unit-testable in isolation; if we want full branch coverage it's a separate, focused test addition that doesn't belong in a Spec-B-hardening PR. Punt to a future test-coverage sweep if any branch ever produces a bug.
- **Performance work** — no caching, no query consolidation beyond what the existing PR already does.
- **Visual changes beyond the new draw status row.** No new layouts, no token additions, no per-game palette adjustments.
- **`compute_match_attribution` integration with `points_for_pick_on_match`** — the new helper is a pure function; whether `compute_match_attribution` should call it internally is a refactor question for another day. Keep the helper standalone for now.

---

## 6. Commit shape

Nine commits, source fixes first and tests trailing their topics so each test can be run against its corresponding fix without bisecting.

1. `fix(home): single now_utc per builder; tie-break + kickoff sort` — bundles the `_now_utc` → `now_utc` rename + consume + leaderboard tie-break + recent-results ordering switch (CR1, CR2, D1).
2. `feat(home): draw branch in recent results with multiplied tier points` — C1 (`points_for_pick_on_match` helper, `_context_live` enrichment, template branch, CSS rule).
3. `fix(home): state-aware view-CTA eyebrow` — CR3.
4. `fix(worldcup-cli): reject negative --backfill, deterministic tie ordering` — CR7 + CR8.
5. `fix(ui): podium word-wrap, countdown warnings` — CR9 + D3.
6. `docs(spec-b): sync snapshot schema + cron timezone notes` — CR4 + CR5 + CR6.
7. `test(home): assert WC_FAKE_NOW honored in context builders` — CR10.
8. `test(home): route-level rendering tests for all 4 states` — B1 (covers CR11).
9. `test(worldcup-cli): snapshot CLI coverage` — B2 (asserts the guards added in commit 4).

---

## 7. Verification gates

Same shape as Spec B's verification gates (PR #3 sec "Verification gates passed"):

- **Gate 1 — Tests pass.** `venv/bin/python -m pytest tests/` reports all green. New count: 139.
- **Gate 2 — Type checks pass.** `venv/bin/pyright` reports 0 errors across the project, 0 errors on touched files.
- **Gate 3 — Migrations clean.** No new migrations expected; `flask db upgrade && flask db downgrade <prev> && flask db upgrade` round-trip remains clean.
- **Gate 4 — Snapshot CLI guards work.** `flask worldcup snapshot-ranks --backfill -1` exits non-zero with `BadParameter` message; `flask worldcup snapshot-ranks` re-run on the same day adds 0 rows.
- **Gate 5 — All four home states render manually.** Re-run Spec B's manual visual checklist (PR #3 table, rows 1-15) — all PASS. New verification: a completed group-stage match where the user's pick was on a draw renders `DRAW · +N PTS` (not `NO POINTS`).
- **Gate 6 — `WC_FAKE_NOW` consistency in dev.** Set `WC_FAKE_NOW=2026-05-01T12:00:00Z`, load `/`, observe `court_line` weekday is `Friday` (the local day for that UTC instant in `America/Chicago`). Set `WC_FAKE_NOW=2026-06-15T00:00:00Z`, verify court_line stage label corresponds to live state.
- **Gate 7 — CodeRabbit re-review.** After pushing, re-tag CodeRabbit. Confirm all 11 prior comments are resolved (or explicit non-fixes argued in reply).

---

## 8. Risks & rollback

- **Risk:** Renaming `_now_utc()` → `now_utc()` accidentally removes the symbol and breaks an unknown caller. **Mitigation:** grep for `_now_utc` across the repo before commit 1; only known callsite is `worldcup_state()` in the same file.
- **Risk:** `points_for_pick_on_match()` math diverges from the canonical scoring engine over time. **Mitigation:** the helper is a thin wrapper around the same constants (`GROUP_WIN`, `GROUP_DRAW`, `KNOCKOUT_POINTS`) and tier multipliers (`TIERS`) used by `compute_team_score_events`; if those constants change, both paths update together.
- **Risk:** Route tests are brittle if the partials' CSS hooks shift. **Mitigation:** assertions favor structural class names (`home-shell--<state>`, `cta-card--view`) which are load-bearing for the state shell architecture and unlikely to be renamed.
- **Risk:** CSS color choice for `--draw` clashes with `--win` and `--loss`. **Mitigation:** use the existing CCC gold token (already in `tokens.css`); reviewer-checked manually before commit 2 lands.
- **Rollback:** Each commit is independent and reversible. The most invasive is commit 1; if `now_utc()` integration causes unexpected issues, revert commit 1 and the home renders against real time again with no other consequence.
