# CCC Home Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land all 11 CodeRabbit review items + 3 deferred Spec B follow-up items (route tests, snapshot CLI tests, draw branch in recent results) + 2 hand-flagged consider items (kickoff sort, countdown.js warnings) on top of PR #3 before it merges.

**Architecture:** No structural changes. Single-builder `now_utc()` plumbing (rename `_now_utc` → `now_utc`, import + use once per builder); deterministic secondary sort across all rank queries; per-pick scoring helper (`points_for_pick_on_match`) added to `games/worldcup/services/scoring.py` as the canonical math source for the new draw branch in `_recent_results.html`; two new test files (`tests/test_home_routes.py`, `tests/test_worldcup_snapshot_cli.py`) closing coverage gaps on Spec B partials and the snapshot cron CLI.

**Tech Stack:** Flask, Jinja2, SQLAlchemy 2.0, Flask-Migrate, pytest, Flask `CliRunner`, `WC_FAKE_NOW` env-var test seam already in `games/worldcup/services/state.py`.

**Worktree:** All work happens in `/Users/bhagstrom/fantasy-platform-ccc-home` on branch `redesign/ccc-home`. Commits stack on top of PR #3.

**Spec:** `docs/superpowers/specs/2026-05-01-ccc-home-followup-design.md` (committed as `b046a9e`).

---

## Task 1: Single `now_utc()` per builder + tie-break + kickoff sort

**Bundles spec items CR1, CR2, D1.** Largest source-fix task. Single commit.

**Files:**
- Modify: `games/worldcup/services/state.py:20-42` (rename `_now_utc()` → `now_utc()`)
- Modify: `games/worldcup/services/state.py:52` (update internal callsite)
- Modify: `core/main/home_context.py:7-23` (import); `:124-150` (use `now_utc()` once in `_context_pre`); `:167-172` (tie-break in `_context_live` leaderboard); `:259-265` (kickoff sort); `:279-289` (use `now_utc()` once in `_context_live`); `:342-346` (tie-break in `_context_post` leaderboard).
- Test (regression only): `tests/test_home_context.py` — existing tests must still pass.

- [ ] **Step 1: Verify no external `_now_utc` callers exist**

```bash
cd /Users/bhagstrom/fantasy-platform-ccc-home
grep -rn "_now_utc" --include="*.py" .
```

Expected: only two hits — `games/worldcup/services/state.py:20` (definition) and `games/worldcup/services/state.py:52` (internal use inside `worldcup_state()`). No other files reference it.

- [ ] **Step 2: Rename `_now_utc()` → `now_utc()` in state.py**

Edit `games/worldcup/services/state.py`:

```python
def now_utc() -> datetime:
    """Current UTC time, with a non-production test seam.

    In development or testing (ENVIRONMENT in {'development', 'testing'}),
    if WC_FAKE_NOW is set to an ISO 8601 string, return that instead of
    real time. A naive ISO string is treated as UTC. Malformed values
    are logged and ignored (falls through to real time). Production
    never reads WC_FAKE_NOW.
    """
    if os.environ.get('ENVIRONMENT') in ('development', 'testing'):
        fake = os.environ.get('WC_FAKE_NOW')
        if fake:
            try:
                dt = datetime.fromisoformat(fake.replace('Z', '+00:00'))
            except ValueError:
                import logging
                logging.getLogger(__name__).warning(
                    'WC_FAKE_NOW is not a valid ISO 8601 datetime: %r — falling back to real time',
                    fake,
                )
            else:
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)
```

(The body is identical; only the leading underscore in the function name is removed.)

Then update the internal caller — `worldcup_state()` line 52:

```python
def worldcup_state() -> WorldCupState:
    """..."""
    if now_utc() < TOURNAMENT_DEADLINE_UTC:
        return 'pre'
    final = WorldCupMatch.query.filter_by(
        match_number=FINAL_MATCH_NUMBER, is_completed=True
    ).first()
    return 'post' if final is not None else 'live'
```

- [ ] **Step 3: Update `home_context.py` imports**

In `core/main/home_context.py`, update the imports near the top (line ~19 currently imports `WorldCupState` from state.py — extend it to also import `now_utc`):

```python
from games.worldcup.services.state import WorldCupState, now_utc
```

- [ ] **Step 4: Rewrite `_context_pre` clock block (lines 124–150)**

Replace the existing block:

```python
    # court_line: "Thursday ◆ Tribute window open ◆ 2 days to kickoff"
    now_local = datetime.now(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - datetime.now(timezone.utc)
```

With the single-`now` form:

```python
    # court_line: "Thursday ◆ Tribute window open ◆ 2 days to kickoff"
    now = now_utc()
    now_local = now.astimezone(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - now
```

Then update the return-dict line 150 from:

```python
        'now_utc': datetime.now(timezone.utc),
```

To:

```python
        'now_utc': now,
```

- [ ] **Step 5: Rewrite `_context_live` clock + tie-break + kickoff sort**

In `_context_live` (starts ~line 162), the leaderboard query at lines 167–172 currently reads:

```python
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )
```

Change to:

```python
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
```

Recent results query at ~line 259–265 currently reads:

```python
    recent_results = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.match_number.desc())
        .limit(5)
        .all()
    )
```

Change to:

```python
    recent_results = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.kickoff_utc.desc())
        .limit(5)
        .all()
    )
```

The trend block at line 279 currently reads `weekday = datetime.now(WORLDCUP_TZ).strftime('%A')`. Hoist a single `now` to the top of `_context_live` (right after `is_enrolled = enrollment is not None`, before the leaderboard query):

```python
def _context_live(user, enrollment) -> dict:
    """Live-tournament state: dossier, leaderboard preview, recent results."""
    is_enrolled = enrollment is not None
    now = now_utc()

    # Leaderboard query — used for both rank and top-3
    all_enrollments = (...)
```

Then change line 279 from:

```python
    weekday = datetime.now(WORLDCUP_TZ).strftime('%A')
```

To:

```python
    weekday = now.astimezone(WORLDCUP_TZ).strftime('%A')
```

`_context_live` does not currently return `now_utc` in its dict — leave the return dict unchanged.

- [ ] **Step 6: Tie-break in `_context_post` leaderboard**

In `_context_post` (starts ~line 310), update the query at lines 342–346 from:

```python
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )
```

To:

```python
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
```

- [ ] **Step 7: Run the full test suite**

```bash
cd /Users/bhagstrom/fantasy-platform-ccc-home
venv/bin/python -m pytest tests/ -q
```

Expected: 124 passed. No new failures. (Tests that import `_now_utc` are not expected to exist; if any are surfaced, treat as an unexpected coupling — investigate.)

- [ ] **Step 8: Run pyright on touched files**

```bash
venv/bin/pyright games/worldcup/services/state.py core/main/home_context.py
```

Expected: 0 errors.

- [ ] **Step 9: Commit**

```bash
git add games/worldcup/services/state.py core/main/home_context.py
git commit -m "$(cat <<'EOF'
fix(home): single now_utc per builder; tie-break + kickoff sort

- Rename _now_utc() → now_utc() in worldcup/services/state.py and
  import it into home_context.py so each builder calls it exactly once.
  Eliminates clock drift across one render and lets WC_FAKE_NOW take
  effect on rendered time copy (court_line weekday, deadline delta,
  returned now_utc).
- Add WorldCupEnrollment.id.asc() secondary sort to the leaderboard
  queries in _context_live and _context_post so tied scores produce
  deterministic row order. Without this, podium placement and
  snapshot-derived rank movement could shuffle between requests.
- Order live-state recent_results by kickoff_utc.desc() instead of
  match_number.desc(). Knockout match_number is bracket position, not
  chronological — kickoff is the right key once R32 starts. Verified
  every match in match_schedule.py has a non-null kickoff_utc.

Resolves CodeRabbit comments CR1, CR2, and Brad's flagged item D1.
EOF
)"
```

---

## Task 2: Draw branch in recent results with multiplied tier points

**Bundles spec item C1 (the only feature-flavored change in this PR).** Includes a new pure helper, context enrichment, template branch, and CSS rule. TDD'd because the helper is genuinely new code.

**Files:**
- Create: `games/worldcup/services/scoring.py:NEW` — `points_for_pick_on_match(pick, match)` function (append near existing pure-function helpers).
- Modify: `tests/test_worldcup_scoring.py:NEW` — append four tests for the helper.
- Modify: `core/main/home_context.py:_context_live` — enrich `your_pick_results` items with `points_earned` and `is_draw`.
- Modify: `core/main/templates/main/_recent_results.html` — three-way win / draw / loss branch.
- Modify: `static/css/style.css` — add `.match-foot-status--draw` rule alongside existing `--win` / `--loss` rules.

- [ ] **Step 1: Locate existing scoring helpers in `scoring.py`**

```bash
grep -n "^def " games/worldcup/services/scoring.py
```

Note the existing function names + line numbers. The new helper should sit alongside them (e.g., after `_apply_knockout_points` near line 188, or wherever logically groups with the other pure-function helpers — pick the natural slot when implementing).

- [ ] **Step 2: Write four failing tests for `points_for_pick_on_match`**

Append to `tests/test_worldcup_scoring.py` (use the existing fixture pattern in that file — `app`, `session`, `_make_team`, `_make_match`, `_make_user`, `_make_enrollment`, `_make_pick`):

```python
def test_points_for_pick_on_match_group_win_t1(app, session):
    """A T1 (mult 1.0) pick wins a group match → +3.0 points."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 1, 'group', bra, arg, group_letter='C')
        match.is_completed = True
        match.winner_team_id = bra.id
        user = _make_user(session, 'tester1')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, bra, tier=1)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 3.0


def test_points_for_pick_on_match_group_draw_t5(app, session):
    """A T5 (mult 7.0) pick draws → +7.0 points (1 base × 7.0 multiplier)."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        nor = _make_team(session, 'NOR', 'Norway', tier=5, multiplier=7.0)
        usa = _make_team(session, 'USA', 'United States', tier=1, multiplier=1.0)
        match = _make_match(session, 2, 'group', nor, usa, group_letter='I')
        match.is_completed = True
        match.is_draw = True
        match.winner_team_id = None
        user = _make_user(session, 'tester2')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, nor, tier=5)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 7.0


def test_points_for_pick_on_match_loss_returns_zero(app, session):
    """The losing side of a group match earns 0 from that match."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 3, 'group', bra, arg, group_letter='C')
        match.is_completed = True
        match.winner_team_id = bra.id  # bra wins
        user = _make_user(session, 'tester3')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, arg, tier=1)  # user picked the loser
        session.commit()
        assert points_for_pick_on_match(pick, match) == 0.0


def test_points_for_pick_on_match_uncompleted_returns_zero(app, session):
    """A match with is_completed=False yields 0, regardless of winner_team_id."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 4, 'group', bra, arg, group_letter='C')
        match.is_completed = False
        match.winner_team_id = bra.id  # set but match not completed
        user = _make_user(session, 'tester4')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, bra, tier=1)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 0.0
```

- [ ] **Step 3: Run the four new tests; expect failure**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::test_points_for_pick_on_match_group_win_t1 tests/test_worldcup_scoring.py::test_points_for_pick_on_match_group_draw_t5 tests/test_worldcup_scoring.py::test_points_for_pick_on_match_loss_returns_zero tests/test_worldcup_scoring.py::test_points_for_pick_on_match_uncompleted_returns_zero -v
```

Expected: 4 failures, all `ImportError: cannot import name 'points_for_pick_on_match'`.

- [ ] **Step 4: Implement `points_for_pick_on_match` in `scoring.py`**

Append to `games/worldcup/services/scoring.py` (after the existing `_apply_knockout_points` helper around line 188 — adjust to the natural location alongside other pure helpers):

```python
def points_for_pick_on_match(pick: WorldCupPick, match: WorldCupMatch) -> float:
    """Multiplied points the pick earns from this completed match. 0.0 if no scoring event.

    Per-pick, per-match analogue of compute_match_attribution. Pure function;
    no DB writes. Used by the live-state home page to surface per-result
    points in the recent-results strip (see _recent_results.html draw branch).
    """
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

Verify the imports at the top of `scoring.py` already include `WorldCupPick`, `WorldCupMatch`, `TIERS`, `GROUP_WIN`, `GROUP_DRAW`, `KNOCKOUT_POINTS`. If any are missing, add them (they should all exist — `compute_team_score_events` already uses these).

- [ ] **Step 5: Run the four tests; expect pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::test_points_for_pick_on_match_group_win_t1 tests/test_worldcup_scoring.py::test_points_for_pick_on_match_group_draw_t5 tests/test_worldcup_scoring.py::test_points_for_pick_on_match_loss_returns_zero tests/test_worldcup_scoring.py::test_points_for_pick_on_match_uncompleted_returns_zero -v
```

Expected: 4 passed.

- [ ] **Step 6: Enrich `your_pick_results` in `_context_live`**

In `core/main/home_context.py`, update the imports at the top of the file:

```python
from games.worldcup.services.scoring import points_for_pick_on_match
```

Then in `_context_live`, after `picks_by_enr` is built (~line 193) and before the `_alive_count` definition, add a team-id index of the user's picks:

```python
    user_picks_by_team_id: dict[int, WorldCupPick] = {}
    if is_enrolled:
        for p in picks_by_enr.get(enrollment.id, []):
            user_picks_by_team_id[p.team_id] = p
```

And in the `your_pick_results` build loop (~line 267–274), replace:

```python
    your_pick_results = []
    for match in recent_results:
        roster_match = None
        if match.home_team_id in user_team_ids:
            roster_match = {'team_id': match.home_team_id, 'side': 'home'}
        elif match.away_team_id in user_team_ids:
            roster_match = {'team_id': match.away_team_id, 'side': 'away'}
        your_pick_results.append({'match': match, 'roster_match': roster_match})
```

With:

```python
    your_pick_results = []
    for match in recent_results:
        roster_match = None
        points_earned: Optional[float] = None
        if match.home_team_id in user_team_ids:
            roster_match = {'team_id': match.home_team_id, 'side': 'home'}
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.home_team_id], match
            )
        elif match.away_team_id in user_team_ids:
            roster_match = {'team_id': match.away_team_id, 'side': 'away'}
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.away_team_id], match
            )
        your_pick_results.append({
            'match': match,
            'roster_match': roster_match,
            'points_earned': points_earned,
            'is_draw': match.is_draw,
        })
```

- [ ] **Step 7: Run pyright on `home_context.py`**

```bash
venv/bin/pyright core/main/home_context.py
```

Expected: 0 errors. (Note: `Optional[float]` requires `from typing import Optional` — already imported on line 8.)

- [ ] **Step 8: Replace the win/loss block in `_recent_results.html`**

Edit `core/main/templates/main/_recent_results.html`. The current `match-foot` block (lines 27–39) reads:

```jinja
  {% if item.roster_match and is_enrolled %}
  <div class="match-foot">
    <div class="match-foot-note">
      YOUR ROSTER &middot;
      {% set rm_team = match.home_team if item.roster_match.side == 'home' else match.away_team %}
      <strong>{{ rm_team.display_name }}</strong>
    </div>
    {% set won = (item.roster_match.side == 'home' and match.winner_team_id == match.home_team_id) or (item.roster_match.side == 'away' and match.winner_team_id == match.away_team_id) %}
    <div class="match-foot-status{% if won %} match-foot-status--win{% else %} match-foot-status--loss{% endif %}">
      {% if won %}+ POINTS EARNED{% else %}NO POINTS{% endif %}
    </div>
  </div>
  {% endif %}
```

Replace with the three-way branch (drops the local `won` recomputation):

```jinja
  {% if item.roster_match and is_enrolled %}
  <div class="match-foot">
    <div class="match-foot-note">
      YOUR ROSTER &middot;
      {% set rm_team = match.home_team if item.roster_match.side == 'home' else match.away_team %}
      <strong>{{ rm_team.display_name }}</strong>
    </div>
    {% if item.points_earned and item.points_earned > 0 %}
      {% if item.is_draw %}
        <div class="match-foot-status match-foot-status--draw">
          DRAW &middot; +{{ '%.0f'|format(item.points_earned) }} {% if item.points_earned == 1 %}PT{% else %}PTS{% endif %}
        </div>
      {% else %}
        <div class="match-foot-status match-foot-status--win">+ POINTS EARNED</div>
      {% endif %}
    {% else %}
      <div class="match-foot-status match-foot-status--loss">NO POINTS</div>
    {% endif %}
  </div>
  {% endif %}
```

- [ ] **Step 9: Add `.match-foot-status--draw` CSS rule**

Locate the existing `.match-foot-status--win` and `.match-foot-status--loss` rules in `static/css/style.css`:

```bash
grep -n "match-foot-status" static/css/style.css
```

Note the line numbers and the colors used by `--win` (likely `var(--live-green)` or similar) and `--loss` (likely a muted red/grey). Add a new rule using the existing CCC gold token `var(--gold-500)` (or whichever gold token is used elsewhere — check `static/css/tokens.css` for the canonical name; pick whichever rule already drives gold accents in the home-shell area, e.g. champion-row gold).

Insert after the `--loss` rule. Mirror its shape — the only difference should be color and any subtle border treatment. Approximate template (verify against existing siblings before pasting):

```css
.home-shell .match-foot-status--draw {
  color: var(--gold-500);
  border-color: rgba(184, 153, 62, 0.35); /* match the existing accent style */
}
```

(The selector prefix `.home-shell` matches Spec B's scoping convention — verify the existing `--win` / `--loss` rules use the same prefix.)

- [ ] **Step 10: Manual smoke — load `/` in dev with a draw seeded**

Run a quick dev server check to confirm visual output:

```bash
mkdir -p instance/
ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T00:00:00Z' FLASK_APP=app.py venv/bin/flask db upgrade
ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T00:00:00Z' FLASK_APP=app.py venv/bin/flask run
```

Then in another terminal, seed a completed group draw via the `worldcup process-match` CLI on a team a logged-in user picked. Confirm `/` renders `DRAW · +N PTS` (gold accent) instead of `NO POINTS` for that result. (Skip if no test fixture is feasible quickly — the route tests in Task 8 will catch this automatically.)

- [ ] **Step 11: Run full test suite + pyright**

```bash
venv/bin/python -m pytest tests/ -q
venv/bin/pyright
```

Expected: 128 passed (124 prior + 4 new from this task). 0 pyright errors.

- [ ] **Step 12: Commit**

```bash
git add games/worldcup/services/scoring.py tests/test_worldcup_scoring.py \
        core/main/home_context.py \
        core/main/templates/main/_recent_results.html static/css/style.css
git commit -m "$(cat <<'EOF'
feat(home): draw branch in recent results with multiplied tier points

Group-stage draws award GROUP_DRAW (1 base point) per side, multiplied
by the picker's tier multiplier (1.0–7.0). The recent-results strip on
the live home was hiding this behind a misleading "NO POINTS" label.

- Add points_for_pick_on_match(pick, match) to worldcup.services.scoring
  as the canonical per-pick-per-match scorer (per-match analogue of
  compute_match_attribution; pure function, no DB writes).
- Enrich your_pick_results items in _context_live with points_earned
  and is_draw so the template stays presentation-only.
- Three-way branch in _recent_results.html: win → "+ POINTS EARNED",
  draw → "DRAW · +N PT(S)" with the multiplied total, loss → "NO POINTS".
- New .match-foot-status--draw CSS rule with the CCC gold accent
  alongside existing --win / --loss.

Resolves Brad-flagged item C1. Adds 4 unit tests for the new helper.
EOF
)"
```

---

## Task 3: State-aware `_view_cta_card.html` eyebrow

**Spec item CR3.** Smallest source change in the PR.

**Files:**
- Modify: `core/main/templates/main/_view_cta_card.html:3`

- [ ] **Step 1: Edit the eyebrow line**

In `core/main/templates/main/_view_cta_card.html`, change line 3:

```jinja
  <div class="cta-card-eyebrow">◇ Tournament in session</div>
```

To:

```jinja
  <div class="cta-card-eyebrow">◇ {{ 'Tournament complete' if state == 'post' else 'Tournament in session' }}</div>
```

(The `state` variable is already passed in `core/main/routes.py:25` via `render_template('main/index.html', state=state, **ctx)` and inherited by all included partials.)

- [ ] **Step 2: Run full test suite (regression check)**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: still 128 passed.

- [ ] **Step 3: Commit**

```bash
git add core/main/templates/main/_view_cta_card.html
git commit -m "fix(home): state-aware view-CTA eyebrow

The _view_cta_card partial is included from both _home_live.html and
_home_post.html, but the eyebrow read 'Tournament in session' for both,
which is wrong copy for a post-tournament view. Branch on the inherited
\`state\` template variable.

Resolves CodeRabbit comment CR3."
```

---

## Task 4: CLI — reject negative `--backfill`, deterministic tie ordering

**Bundles spec items CR7, CR8.** Source-only commit; tests for both come in Task 9.

**Files:**
- Modify: `games/worldcup/cli.py:210-227`

- [ ] **Step 1: Add the negative-backfill guard + tie-break**

In `games/worldcup/cli.py`, the `snapshot_ranks` function currently begins at line 210. Add a click-error guard immediately after the `def`, and add a secondary sort to the enrollment query at line 226:

Replace lines 210–228 (current implementation):

```python
def snapshot_ranks(backfill: int):
    """Capture today's rank + score snapshot for every enrollment.

    Idempotent: re-running for the same day is a no-op.
    With --backfill N, also writes snapshots for the past N days using
    the current rank/score (best-effort backfill for first deploy).
    Net rows per enrollment: N+1 (today + N prior days).
    """
    today_local = datetime.now(WORLDCUP_TZ).date()

    for days_ago in range(backfill, -1, -1):
        target_date = today_local - timedelta(days=days_ago)

        enrollments = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(WorldCupEnrollment.total_score.desc())
            .all()
        )
```

With:

```python
def snapshot_ranks(backfill: int):
    """Capture today's rank + score snapshot for every enrollment.

    Idempotent: re-running for the same day is a no-op.
    With --backfill N, also writes snapshots for the past N days using
    the current rank/score (best-effort backfill for first deploy).
    Net rows per enrollment: N+1 (today + N prior days).
    """
    if backfill < 0:
        raise click.BadParameter('--backfill must be >= 0')

    today_local = datetime.now(WORLDCUP_TZ).date()

    for days_ago in range(backfill, -1, -1):
        target_date = today_local - timedelta(days=days_ago)

        enrollments = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(
                WorldCupEnrollment.total_score.desc(),
                WorldCupEnrollment.id.asc(),
            )
            .all()
        )
```

- [ ] **Step 2: Run full test suite (regression check)**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 128 passed (no new tests yet for these guards — they ship in Task 9).

- [ ] **Step 3: Manual smoke — negative backfill exits non-zero**

```bash
mkdir -p instance/
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill -1
echo "exit code: $?"
```

Expected: error output mentions `--backfill must be >= 0`; exit code != 0.

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/cli.py
git commit -m "$(cat <<'EOF'
fix(worldcup-cli): reject negative --backfill, deterministic tie ordering

- Raise click.BadParameter when --backfill < 0 instead of silently
  doing nothing (range(-1, -1, -1) is empty, so the previous code was
  a no-op for operator typos).
- Add WorldCupEnrollment.id.asc() as a secondary sort to the snapshot
  ranking query so tied total_score rows produce a stable rank order
  across runs. Without this, daily snapshots could record fake rank
  movement on tied scores.

Resolves CodeRabbit comments CR7 and CR8.
EOF
)"
```

---

## Task 5: CSS + JS hygiene — podium word-wrap, countdown warnings

**Bundles spec items CR9, D3.** Two small unrelated UI hygiene fixes grouped.

**Files:**
- Modify: `static/css/style.css` (`.home-shell .podium-name` rule, around line 1558–1568)
- Modify: `static/js/countdown.js` (4 early-return sites)

- [ ] **Step 1: Replace `word-break: break-word` in `.podium-name`**

In `static/css/style.css`, find the `.home-shell .podium-name` rule (around line 1558–1568):

```bash
grep -n "podium-name" static/css/style.css
```

The rule currently ends with `word-break: break-word;`. Replace that single declaration with two modern declarations:

```css
.home-shell .podium-name {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
  position: relative;
  z-index: 1;
  word-break: normal;
  overflow-wrap: anywhere;
}
```

(Keep the rest of the rule — font, color, etc. — exactly as it is. Only the wrapping declarations change.)

- [ ] **Step 2: Add `console.warn` to the four early returns in `countdown.js`**

Replace the contents of `static/js/countdown.js` with:

```javascript
// Countdown ticker — drives the .decree countdown card on the pre-state home.
// Reads data-deadline-utc on the .decree element; ticks every second; reloads
// the page when the deadline is reached so the next request sees state='live'.
(function () {
  var el = document.querySelector('.decree[data-deadline-utc]');
  if (!el) {
    console.warn('[countdown] no .decree[data-deadline-utc] element on page');
    return;
  }

  var deadline = new Date(el.getAttribute('data-deadline-utc')).getTime();
  if (isNaN(deadline)) {
    console.warn('[countdown] data-deadline-utc is not parseable as a date:', el.getAttribute('data-deadline-utc'));
    return;
  }

  var dEl = el.querySelector('[data-cd-days]');
  var hEl = el.querySelector('[data-cd-hours]');
  var mEl = el.querySelector('[data-cd-mins]');
  var sEl = el.querySelector('[data-cd-secs]');
  if (!dEl || !hEl || !mEl || !sEl) {
    console.warn('[countdown] missing one or more [data-cd-*] children inside .decree');
    return;
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function tick() {
    var now = Date.now();
    var diff = deadline - now;
    if (diff <= 0) {
      dEl.textContent = '00';
      hEl.textContent = '00';
      mEl.textContent = '00';
      sEl.textContent = '00';
      // Wait one tick so the user sees zero, then reload for state transition
      setTimeout(function () { window.location.reload(); }, 1500);
      return;
    }
    var days = Math.floor(diff / (1000 * 60 * 60 * 24));
    var hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
    var mins = Math.floor((diff / (1000 * 60)) % 60);
    var secs = Math.floor((diff / 1000) % 60);
    dEl.textContent = pad(days);
    hEl.textContent = pad(hours);
    mEl.textContent = pad(mins);
    sEl.textContent = pad(secs);
  }

  tick();
  setInterval(tick, 1000);
})();
```

(The original file had three early returns; the rewrite makes them four because `if (!dEl || !hEl || !mEl || !sEl)` was previously combined. The rewrite splits the `if (!el)`, `if (isNaN(deadline))`, and `if (!dEl || ...)` paths into three explicitly-warned branches plus the deadline-reached reload path which intentionally has no warning.)

- [ ] **Step 3: Run full test suite (regression check)**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 128 passed.

- [ ] **Step 4: Manual smoke — pre-state still ticks, post-state console-warns when no decree on page**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run
```

Open `/` in dev (pre state) — countdown should tick normally. Open `/worldcup/` (a non-home page) and confirm browser console shows no `[countdown]` warnings (`countdown.js` is only loaded on pre-state home, so it shouldn't fire elsewhere). The warning paths trigger only if the JS is loaded but the `.decree` element is absent or malformed — verify by manually editing the rendered HTML in devtools to drop a `data-cd-*` attr and refreshing.

- [ ] **Step 5: Commit**

```bash
git add static/css/style.css static/js/countdown.js
git commit -m "$(cat <<'EOF'
fix(ui): podium word-wrap, countdown warnings

- .home-shell .podium-name swaps the deprecated word-break: break-word
  for the modern overflow-wrap: anywhere + word-break: normal pair.
  Long display names now wrap consistently across browsers.
- countdown.js logs console.warn on each silent early return (missing
  .decree element, unparseable data-deadline-utc, missing data-cd-*
  children) so future template restyles surface breakage in devtools
  instead of failing silently.

Resolves CodeRabbit comment CR9 and Brad-flagged item D3.
EOF
)"
```

---

## Task 6: Docs — sync snapshot schema + cron timezone notes

**Bundles spec items CR4, CR5, CR6.** Pure documentation fix; no code or tests change.

**Files:**
- Modify: `docs/superpowers/plans/2026-04-21-production-deployment.md:1166` (CST/CDT direction); `:1185` (job count).
- Modify: `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md:711-740` (`captured_at` → `captured_date`); `:799-803` (cron timezone direction); `:836-842` (Gate 4 expectations).

- [ ] **Step 1: Fix the CST/CDT direction in production-deployment.md**

In `docs/superpowers/plans/2026-04-21-production-deployment.md`, change line 1166 from:

```
# 05:05 UTC = 00:05 CST (winter) / 23:05 CDT prior day (summer); 5-min offset gives midnight match-result processing time to settle
```

To:

```
# 05:05 UTC = 23:05 CST (prior day, winter) / 00:05 CDT (summer); 5-min offset gives midnight match-result processing time to settle
```

- [ ] **Step 2: Fix the job-count expectation in production-deployment.md**

In the same file, change line 1185 from:

```
Expected: the six job entries are listed.
```

To:

```
Expected: the seven job entries are listed.
```

- [ ] **Step 3: Sync the snapshot model snippet in spec section 10a**

In `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`, the model snippet at lines 711–738 currently shows `captured_at = db.Column(db.DateTime, ...)`. Replace the entire model snippet (lines 711–738) with the shipped form:

```python
# games/worldcup/models.py
class WorldCupRankSnapshot(db.Model):
    """Daily snapshot of each enrollment's rank + total_score.

    Written by `flask worldcup snapshot-ranks`, run nightly via cron.
    Powers the live-state dossier sparkline and week-delta calculations.
    """
    __tablename__ = 'worldcup_rank_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey('worldcup_enrollment.id', ondelete='CASCADE'),
        nullable=False, index=True
    )
    captured_date = db.Column(db.Date, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Float, nullable=False)

    enrollment = db.relationship('WorldCupEnrollment', backref='rank_snapshots')

    __table_args__ = (
        db.UniqueConstraint(
            'enrollment_id', 'captured_date',
            name='unique_worldcup_snapshot_per_day'
        ),
    )
```

And update the explainer line 740 from:

```
`captured_at` stored as midnight CT for the day captured (date-equivalent precision; the unique constraint enforces one row per enrollment per day).
```

To:

```
`captured_date` stored as a `Date` (date-only, day-equivalent precision); the unique constraint `unique_worldcup_snapshot_per_day` enforces one row per enrollment per day.
```

- [ ] **Step 4: Fix the spec's cron timezone direction**

In the same spec file at lines 799–803, change:

```
# Worldcup: daily rank snapshot at midnight CT
# 05:05 UTC = 00:05 CST (winter) or 23:05 CDT prior day (summer); this offset
# gives any midnight match-result processing time to settle before snapshotting.
```

To:

```
# Worldcup: daily rank snapshot at midnight CT
# 05:05 UTC = 23:05 CST (prior day, winter) or 00:05 CDT (summer); this offset
# gives any midnight match-result processing time to settle before snapshotting.
```

- [ ] **Step 5: Sync Gate 4 in section 11a**

In the same spec file at lines 836–842, change the Gate 4 block from:

```
**Gate 4 — Snapshot CLI works:**
```bash
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
# verify row count, then re-run, verify no new rows added (idempotency)
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
# verify 7 distinct captured_at dates per enrollment
```
```

To:

```
**Gate 4 — Snapshot CLI works:**
```bash
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
# verify row count, then re-run, verify no new rows added (idempotency)
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
# verify 8 distinct captured_date values per enrollment (today + 7 backfilled)
```
```

- [ ] **Step 6: Verify the diff renders correctly**

```bash
git diff docs/
```

Expected: 5 hunks across 2 files; all changes match the steps above. No other doc changes.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/2026-04-21-production-deployment.md \
        docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md
git commit -m "$(cat <<'EOF'
docs(spec-b): sync snapshot schema + cron timezone notes

- Spec section 10a: model snippet now shows captured_date (Date, with
  the FK ondelete='CASCADE' that landed in 2df9e6a) instead of the
  pre-implementation captured_at (DateTime) draft. Mention the
  unique_worldcup_snapshot_per_day constraint name explicitly.
- Spec sec 4d cron note + production-deployment.md cron line: fix
  reversed CST/CDT mapping. 05:05 UTC = 23:05 CST prior day (winter)
  or 00:05 CDT (summer), not the inverse.
- production-deployment.md verification line: bump 'six entries' to
  'seven entries' since the snapshot job brought the cron count to 7.
- Spec Gate 4: --backfill 7 yields 8 captured_date values per
  enrollment (today + 7 backfilled), not 7.

Resolves CodeRabbit comments CR4, CR5, and CR6.
EOF
)"
```

---

## Task 7: Test — assert `WC_FAKE_NOW` honored in context builders

**Spec item CR10.** Augments two existing tests in `test_home_context.py` with a fake-clock assertion. Trails Task 1, which is the fix being asserted.

**Files:**
- Modify: `tests/test_home_context.py:103-110` (`test_context_pre_unenrolled`); `:158-170` (`test_context_live_enrolled_basic`)

- [ ] **Step 1: Update imports at the top of `test_home_context.py`**

Verify `from datetime import datetime, timezone` is present at the top of `tests/test_home_context.py`. If not, add it:

```python
from datetime import datetime, timezone
```

- [ ] **Step 2: Augment `test_context_pre_unenrolled`**

The current test (lines 100–110):

```python
def test_context_pre_unenrolled(app):
    """Logged-in but no WC enrollment → is_enrolled=False, no picks."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        user = _make_user()
        ctx = build_home_context(user, 'pre')
        assert ctx['is_enrolled'] is False
        assert ctx['picks'] == []
        assert ctx['display_name'] == 'alice'
        assert 'court_line' in ctx
        assert 'deadline_utc' in ctx
```

Add one assertion before the closing of the `with` block:

```python
def test_context_pre_unenrolled(app):
    """Logged-in but no WC enrollment → is_enrolled=False, no picks."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        user = _make_user()
        ctx = build_home_context(user, 'pre')
        assert ctx['is_enrolled'] is False
        assert ctx['picks'] == []
        assert ctx['display_name'] == 'alice'
        assert 'court_line' in ctx
        assert 'deadline_utc' in ctx
        assert ctx['now_utc'] == datetime(2026, 5, 1, tzinfo=timezone.utc)
```

- [ ] **Step 3: Augment `test_context_live_enrolled_basic`**

The current test (lines 158–169) does not assert `now_utc` because `_context_live` doesn't return it. The CR10 ask is to prove the seam is honored end-to-end — for `_context_live` we instead assert a value derived from the fake clock (the `court_line` weekday). With `WC_FAKE_NOW='2026-06-15T00:00:00Z'` and `WORLDCUP_TZ` (America/Chicago, CDT in June = UTC-5), the local time is 2026-06-14 19:00 CDT → weekday is `Sunday`.

Update the test:

```python
def test_context_live_enrolled_basic(app):
    """Live state, enrolled → dossier populated with rank/points/alive."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        user = _make_user()
        _make_enrollment(user, picks_submitted=True, total_score=100.0)
        ctx = build_home_context(user, 'live')
        assert ctx['is_enrolled'] is True
        assert ctx['dossier']['rank'] == 1  # only 1 enrollment
        assert ctx['dossier']['total_score'] == 100.0
        assert ctx['dossier']['alive_count'] == 0  # no picks seeded
        assert ctx['dossier']['week_delta_rank'] is None  # no snapshots
        # CR10: prove WC_FAKE_NOW flowed through to court_line weekday.
        # 2026-06-15T00:00:00Z = 2026-06-14 19:00 CDT (UTC-5) → Sunday.
        assert 'Sunday' in ctx['court_line']
```

- [ ] **Step 4: Run the two augmented tests**

```bash
venv/bin/python -m pytest tests/test_home_context.py::test_context_pre_unenrolled tests/test_home_context.py::test_context_live_enrolled_basic -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full test suite (sanity)**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 128 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_home_context.py
git commit -m "$(cat <<'EOF'
test(home): assert WC_FAKE_NOW honored in context builders

CR10 noted that two existing tests in test_home_context.py set
WC_FAKE_NOW but never asserted any value derived from it, leaving
the fake-clock seam uncovered.

- test_context_pre_unenrolled: assert ctx['now_utc'] equals the
  parsed WC_FAKE_NOW datetime (2026-05-01 UTC).
- test_context_live_enrolled_basic: assert 'Sunday' appears in
  ctx['court_line'] (2026-06-15T00:00:00Z = 2026-06-14 19:00 CDT
  → Sunday in America/Chicago). _context_live does not return
  now_utc directly, so we assert via the derived court_line.

Together these prove WC_FAKE_NOW flows env-var → now_utc() →
build_home_context → ctx end-to-end. Resolves CR10.
EOF
)"
```

---

## Task 8: Route-level rendering tests for all 4 home states

**Spec item B1 (also covers CR11).** Largest test addition: 7 new tests in a new file.

**Files:**
- Create: `tests/test_home_routes.py`

- [ ] **Step 1: Create the new test file with fixtures**

Create `tests/test_home_routes.py` with the fixture + helper scaffold:

```python
"""Route-level rendering tests for the four home states (Spec B follow-up B1)."""
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    """Testing app with in-memory SQLite + WC_FAKE_NOW disabled at start."""
    os.environ.pop('WC_FAKE_NOW', None)
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(username='alice', email='alice@example.com'):
    from models.user import User
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _make_enrollment(user, picks_submitted=False, total_score=0.0):
    from games.worldcup.models import WorldCupEnrollment
    from games.worldcup.constants import SEASON_YEAR
    enr = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def _make_team(fifa_code, name, tier=1, multiplier=1.0, group='A'):
    from games.worldcup.models import WorldCupTeam
    team = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier, confederation='TEST',
        group_letter=group,
    )
    db.session.add(team)
    db.session.commit()
    return team


def _make_pick(enrollment, team, tier=1):
    from games.worldcup.models import WorldCupPick
    pick = WorldCupPick(enrollment_id=enrollment.id, team_id=team.id, tier=tier)
    db.session.add(pick)
    db.session.commit()
    return pick


def _make_match(match_number, stage, home_team, away_team, completed=False,
                winner_team_id=None, group_letter=None, kickoff_utc=None):
    from games.worldcup.models import WorldCupMatch
    from datetime import datetime, timezone
    match = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        group_letter=group_letter,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        is_completed=completed,
        winner_team_id=winner_team_id,
        kickoff_utc=kickoff_utc or datetime(2026, 6, 14, 19, 0, tzinfo=timezone.utc),
    )
    db.session.add(match)
    db.session.commit()
    return match


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
```

- [ ] **Step 2: Add `test_home_renders_logged_out`**

Append to `tests/test_home_routes.py`:

```python
def test_home_renders_logged_out(client):
    """Anonymous GET / renders the logged-out shell."""
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'home-shell--out' in body
    assert 'Join the Club' in body  # logged-out CTA token from _home_out.html
```

- [ ] **Step 3: Add `test_home_renders_pre_unenrolled`**

```python
def test_home_renders_pre_unenrolled(app, client):
    """Logged-in pre-deadline + no WC enrollment renders the join CTA."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'Join the World Cup pool' in body  # _join_cta_card.html title
        assert 'data-deadline-utc=' in body  # countdown markup
```

- [ ] **Step 4: Add `test_home_renders_pre_enrolled_no_picks`**

```python
def test_home_renders_pre_enrolled_no_picks(app, client):
    """Pre-deadline + enrolled + picks_submitted=False renders the seal-roster CTA."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _make_enrollment(user, picks_submitted=False)
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'Seal Your Roster' in body  # _submit_picks_cta.html title
```

- [ ] **Step 5: Add `test_home_renders_pre_enrolled_sealed`**

```python
def test_home_renders_pre_enrolled_sealed(app, client):
    """Pre-deadline + enrolled + sealed → ballot card renders + countdown present."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            enr = _make_enrollment(user, picks_submitted=True)
            team = _make_team('USA', 'United States')
            _make_pick(enr, team, tier=1)
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'data-deadline-utc=' in body
        assert 'USA' in body  # ballot card lists the picked team's FIFA code
```

- [ ] **Step 6: Add `test_home_renders_live_unenrolled`**

```python
def test_home_renders_live_unenrolled(app, client):
    """Live state + unenrolled renders the view-CTA with 'in session' eyebrow (CR3 live branch)."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--live' in body
        assert 'cta-card--view' in body
        assert 'Tournament in session' in body
```

- [ ] **Step 7: Add `test_home_renders_live_enrolled`**

```python
def test_home_renders_live_enrolled(app, client):
    """Live + enrolled with one completed group match where pick rosters home side."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            enr = _make_enrollment(user, picks_submitted=True, total_score=10.0)
            usa = _make_team('USA', 'United States', tier=1, multiplier=1.0)
            mex = _make_team('MEX', 'Mexico', tier=1, multiplier=1.0, group='B')
            _make_pick(enr, usa, tier=1)
            _make_match(1, 'group', usa, mex, completed=True, winner_team_id=usa.id, group_letter='A')
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--live' in body
        assert 'Dossier' in body  # greet-title in _home_live.html
        assert 'Recent Results' in body
        assert 'USA' in body  # picked team's FIFA code surfaces in result strip
```

- [ ] **Step 8: Add `test_home_renders_post_with_champion`**

```python
def test_home_renders_post_with_champion(app, client):
    """Post state with match #104 completed renders champion banner + 'Tournament complete' CTA (CR3 post branch)."""
    with app.app_context():
        bra = _make_team('BRA', 'Brazil', tier=2, multiplier=1.5, group='C')
        arg = _make_team('ARG', 'Argentina', tier=2, multiplier=1.5, group='B')
        # Match #104 completed → triggers post state (no WC_FAKE_NOW needed once final is_completed)
        from games.worldcup.models import WorldCupMatch
        from datetime import datetime, timezone
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2, extra_time=True,
            winner_team_id=bra.id, is_completed=True,
            kickoff_utc=datetime(2026, 7, 19, 19, 0, tzinfo=timezone.utc),
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        # No enrollment → unenrolled post path, which renders the view-CTA
        _login(client, user.id)
        # WC_FAKE_NOW after the final-match kickoff so worldcup_state() returns 'post'
        with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-07-20T00:00:00Z'}):
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--post' in body
        assert 'Brazil' in body  # champion display name in banner
        assert 'Tournament complete' in body  # CR3 post branch
```

- [ ] **Step 9: Run the new test file**

```bash
venv/bin/python -m pytest tests/test_home_routes.py -v
```

Expected: 7 passed.

- [ ] **Step 10: Run full test suite**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 135 passed (128 prior + 7 new).

- [ ] **Step 11: Run pyright on the new file**

```bash
venv/bin/pyright tests/test_home_routes.py
```

Expected: 0 errors.

- [ ] **Step 12: Commit**

```bash
git add tests/test_home_routes.py
git commit -m "$(cat <<'EOF'
test(home): route-level rendering tests for all 4 states

Spec B's PR #3 left _home_live.html, _home_post.html, _dossier_card.html,
_recent_results.html, and _champion_banner.html unrendered through any
test — only the build_home_context() builders were unit-tested. Add a
new tests/test_home_routes.py file that hits client.get('/') for each
logical home state and asserts state-specific HTML markers.

Coverage: logged-out, pre-unenrolled, pre-enrolled-no-picks,
pre-enrolled-sealed, live-unenrolled (proves CR3 'Tournament in session'
eyebrow), live-enrolled (proves recent-results renders the picked team),
and post-with-champion (proves CR3 'Tournament complete' eyebrow +
champion banner). Marker assertions favor structural CSS hooks
(home-shell--<state>, cta-card--view) over copy strings where possible.

Resolves Brad-flagged item B1 and CodeRabbit comment CR11.
EOF
)"
```

---

## Task 9: CLI tests — snapshot idempotency, backfill, guards, tie ordering

**Spec item B2.** Trails Task 4 (the source fixes for negative-backfill + tie-break).

**Files:**
- Create: `tests/test_worldcup_snapshot_cli.py`

- [ ] **Step 1: Create the new test file with fixture + helpers**

Create `tests/test_worldcup_snapshot_cli.py`:

```python
"""Tests for the `flask worldcup snapshot-ranks` CLI (Spec B follow-up B2)."""
from datetime import date, timedelta

import pytest

from app import create_app
from extensions import db
from games.worldcup.cli import worldcup_cli


@pytest.fixture
def app():
    """Testing app with in-memory SQLite."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_enrollment(total_score=0.0, username='u'):
    """Create a User + WorldCupEnrollment for the current SEASON_YEAR."""
    from models.user import User
    from games.worldcup.models import WorldCupEnrollment
    from games.worldcup.constants import SEASON_YEAR
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    enr = WorldCupEnrollment(
        user_id=user.id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def _today_local():
    """Today's date in WORLDCUP_TZ — matches what the CLI uses."""
    from datetime import datetime
    from games.worldcup.constants import WORLDCUP_TZ
    return datetime.now(WORLDCUP_TZ).date()
```

- [ ] **Step 2: Add `test_snapshot_idempotent_same_day`**

Append to `tests/test_worldcup_snapshot_cli.py`:

```python
def test_snapshot_idempotent_same_day(app):
    """Re-running snapshot-ranks for the same day adds 0 new rows."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')
        _make_enrollment(total_score=20.0, username='bob')

        runner = app.test_cli_runner()
        result1 = runner.invoke(worldcup_cli, ['snapshot-ranks'])
        assert result1.exit_code == 0, result1.output
        assert WorldCupRankSnapshot.query.count() == 2

        result2 = runner.invoke(worldcup_cli, ['snapshot-ranks'])
        assert result2.exit_code == 0, result2.output
        # Still 2 rows; second run was a no-op.
        assert WorldCupRankSnapshot.query.count() == 2
```

- [ ] **Step 3: Add `test_snapshot_backfill_writes_n_plus_one_descending`**

```python
def test_snapshot_backfill_writes_n_plus_one_descending(app):
    """`--backfill 3` writes today + 3 prior days (4 distinct dates per enrollment)."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')
        _make_enrollment(total_score=20.0, username='bob')

        runner = app.test_cli_runner()
        result = runner.invoke(worldcup_cli, ['snapshot-ranks', '--backfill', '3'])
        assert result.exit_code == 0, result.output

        # 2 enrollments × 4 days = 8 rows total
        assert WorldCupRankSnapshot.query.count() == 8

        # For each enrollment, dates span today back to today-3
        today = _today_local()
        for enr in db.session.query(WorldCupRankSnapshot.enrollment_id).distinct().all():
            eid = enr[0]
            dates = sorted(
                row.captured_date for row in
                WorldCupRankSnapshot.query.filter_by(enrollment_id=eid).all()
            )
            assert len(dates) == 4
            assert dates[-1] == today
            assert dates[0] == today - timedelta(days=3)
```

- [ ] **Step 4: Add `test_snapshot_negative_backfill_rejected`**

```python
def test_snapshot_negative_backfill_rejected(app):
    """`--backfill -1` exits non-zero with a BadParameter message; no rows written."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')

        runner = app.test_cli_runner()
        result = runner.invoke(worldcup_cli, ['snapshot-ranks', '--backfill', '-1'])
        assert result.exit_code != 0
        assert '--backfill must be >= 0' in result.output
        assert WorldCupRankSnapshot.query.count() == 0
```

- [ ] **Step 5: Add `test_snapshot_tie_ordering_deterministic`**

```python
def test_snapshot_tie_ordering_deterministic(app):
    """3 tied-score enrollments produce identical (eid, rank) ordering across runs."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        e1 = _make_enrollment(total_score=10.0, username='alice')
        e2 = _make_enrollment(total_score=10.0, username='bob')
        e3 = _make_enrollment(total_score=10.0, username='carol')

        runner = app.test_cli_runner()
        runner.invoke(worldcup_cli, ['snapshot-ranks'])
        first = sorted(
            (row.enrollment_id, row.rank)
            for row in WorldCupRankSnapshot.query.all()
        )

        # Wipe and re-run; captured_date is "today" for both runs so we'd hit
        # idempotency without the wipe.
        WorldCupRankSnapshot.query.delete()
        db.session.commit()

        runner.invoke(worldcup_cli, ['snapshot-ranks'])
        second = sorted(
            (row.enrollment_id, row.rank)
            for row in WorldCupRankSnapshot.query.all()
        )

        assert first == second
        # And the ordering is by id ascending (since all scores tied)
        assert first == sorted([(e1.id, 1), (e2.id, 2), (e3.id, 3)])
```

- [ ] **Step 6: Run the new test file**

```bash
venv/bin/python -m pytest tests/test_worldcup_snapshot_cli.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Run full test suite**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 139 passed (135 + 4 new). NOTE: this is **higher than the spec's 135** because Task 2 added 4 new helper-unit tests in `test_worldcup_scoring.py` that the spec's coverage delta did not budget for. Adjust the PR description coverage line accordingly.

- [ ] **Step 8: Run pyright on the new file**

```bash
venv/bin/pyright tests/test_worldcup_snapshot_cli.py
```

Expected: 0 errors.

- [ ] **Step 9: Commit**

```bash
git add tests/test_worldcup_snapshot_cli.py
git commit -m "$(cat <<'EOF'
test(worldcup-cli): snapshot CLI coverage

The flask worldcup snapshot-ranks command had zero tests despite being
a nightly cron job. Add four CLI tests via app.test_cli_runner():

- idempotent_same_day: re-running on the same day is a no-op (0 new rows).
- backfill_writes_n_plus_one_descending: --backfill 3 writes 4 distinct
  captured_date values per enrollment, max == today, min == today-3.
- negative_backfill_rejected: --backfill -1 exits non-zero with the
  click.BadParameter guard message; no rows written.
- tie_ordering_deterministic: three tied-score enrollments produce
  identical (eid, rank) pairs across runs, ordered by id ascending.

Resolves Brad-flagged item B2; provides positive coverage for the
guards added in commit 4 (CR7 + CR8).
EOF
)"
```

---

## Task 10: Final verification + push

**Verification gates per spec section 7.** Single push at the end.

- [ ] **Step 1: Confirm clean worktree**

```bash
cd /Users/bhagstrom/fantasy-platform-ccc-home
git status
```

Expected: working tree clean (only untracked `venv` directory which is `.gitignore`d).

- [ ] **Step 2: Run the full test suite one more time**

```bash
venv/bin/python -m pytest tests/ -q
```

Expected: 139 passed (or 128 if you count differently — see Task 9 Step 7 note). 0 failures.

- [ ] **Step 3: Run pyright across the project**

```bash
venv/bin/pyright
```

Expected: 0 errors.

- [ ] **Step 4: Migration round-trip**

```bash
mkdir -p instance/
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```

Then check the current head and downgrade by one revision:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db current
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db downgrade
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: clean round-trip; no migration changes were introduced by this PR, so this should behave exactly as it did before.

- [ ] **Step 5: Manual smoke — Gate 6 (`WC_FAKE_NOW` consistency)**

```bash
ENVIRONMENT=development WC_FAKE_NOW='2026-05-01T12:00:00Z' FLASK_APP=app.py venv/bin/flask run
```

In a browser, load `/` (logged out is fine; we're checking server-rendered weekday). View page source, search for `court_line`. The proximity copy should reflect 2026-05-01 12:00 UTC = 2026-05-01 07:00 CDT (`Friday`). Stop the server.

Then:

```bash
ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T00:00:00Z' FLASK_APP=app.py venv/bin/flask run
```

Load `/` while logged in (or check the live-state route directly). The court_line stage label should be `Group Stage` (since the live shell renders during the group phase).

- [ ] **Step 6: Push the branch**

```bash
git push origin redesign/ccc-home
```

Expected: push succeeds; PR #3 picks up the new commits automatically.

- [ ] **Step 7: Re-tag CodeRabbit on PR #3**

```bash
gh pr comment 3 --body "@coderabbitai review"
```

Expected: CodeRabbit re-reviews and confirms the 11 prior comments are resolved (or surfaces new ones for response).

- [ ] **Step 8: Update the PR body's Deferred-to-follow-up section**

The original PR description has a "Deferred to follow-up" block. Replace it (via `gh pr edit 3`) with a short note that the deferred items shipped in commits b046a9e through the final commit of this plan, with the new test count (139).

```bash
gh pr view 3 --json body --jq .body > /tmp/pr3-body.md
# Edit /tmp/pr3-body.md — replace the "Deferred to follow-up" block with:
#   "Deferred items shipped in this PR — see commits b046a9e..HEAD."
gh pr edit 3 --body-file /tmp/pr3-body.md
```

---

## Self-review notes (writer's checklist, applied)

**Spec coverage:** All 15 deltas in spec section 2 mapped to tasks:
- CR1 → Task 1 (steps 2, 4, 5)
- CR2 → Task 1 (steps 5, 6)
- CR3 → Task 3
- CR4 → Task 6 (steps 1, 2)
- CR5 → Task 6 (step 3)
- CR6 → Task 6 (step 4)
- CR7 → Task 4 (step 1) + Task 9 (step 4)
- CR8 → Task 4 (step 1) + Task 9 (step 5)
- CR9 → Task 5 (step 1)
- CR10 → Task 7
- CR11 → Task 8 (covered via route tests, replaces the homepage-section smoke approach)
- B1 → Task 8
- B2 → Task 9
- C1 → Task 2
- D1 → Task 1 (step 5)
- D3 → Task 5 (step 2)

D2 explicitly out of scope per spec section 5.

**Coverage delta:** Spec budgeted 135 tests. Actual is 139 because Task 2 TDD'd the new `points_for_pick_on_match` helper with 4 unit tests that the spec didn't separately budget. This is a strict improvement and makes the helper safer to maintain. Note in PR body update (Task 10 Step 8).

**Type consistency:** `points_for_pick_on_match(pick: WorldCupPick, match: WorldCupMatch) -> float` is referenced consistently in Task 2 (definition) and the home_context.py edit (consumer). `now_utc()` is referenced consistently in Tasks 1 and 7.
