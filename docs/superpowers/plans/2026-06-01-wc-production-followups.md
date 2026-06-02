# WC Production Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship five WC production-testing follow-ups in one PR on branch `worldcup/production-testing`: signup auto-join to World Cup, a shared CTA CSS recipe, derived knockout elimination, golf pytz→zoneinfo cleanup, and a CLAUDE.md/memory/repo cleanse.

**Architecture:** Backend/TDD work first (derived-elimination helper + read-site routing, signup auto-join, golf datetime migration), then the impeccable CSS refactor, then docs/memory/repo cleanse last so docs describe the final state. Each phase commits independently. Full pytest suite (~957) green before and after.

**Tech Stack:** Flask, SQLAlchemy 2.0, Jinja2, pytest, stdlib `zoneinfo`/`datetime`, CCC design system (impeccable skill).

**Spec:** `docs/superpowers/specs/2026-06-01-wc-production-followups-design.md`

**Conventions reminder (CLAUDE.md):**
- Tests that set `WC_FAKE_NOW` MUST also set `'ENVIRONMENT': 'testing'` in the same `patch.dict(os.environ, {...})`.
- Never mutate ORM attributes for display — pass sets / use transient attributes.
- Patch the time/deadline seam at the read-site (`games.worldcup.services.state`).
- Run tests: `ENVIRONMENT=testing venv/bin/python -m pytest tests/`.

---

## Phase 0: Baseline

### Task 0: Confirm green baseline

- [ ] **Step 1: Run the full suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
Expected: all pass (~957). Record the exact count — it is the regression baseline for the final phase.

- [ ] **Step 2: Confirm on the right branch**

Run: `git branch --show-current`
Expected: `worldcup/production-testing`

---

## Phase 1: Derived knockout elimination helper (Follow-up B core)

**Files:**
- Create: `games/worldcup/services/elimination.py`
- Test: `tests/test_worldcup_elimination.py`

### Task 1: `eliminated_team_ids()` helper + tests

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_elimination.py`:

```python
"""Tests for derived knockout elimination (services/elimination.py).

is_eliminated is GROUP-STAGE-ONLY (scoring sets it only for group non-advancers).
eliminated_team_ids() must additionally derive knockout losers from completed
matches, matching team_detail._path_status() elimination semantics.
"""
import pytest

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from games.worldcup.services.elimination import eliminated_team_ids
from games.worldcup.services.team_detail import _path_status


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _team(name, iso, *, is_eliminated=False, best_finish=None, advancement_method=None):
    t = WorldCupTeam(
        display_name=name, iso_code=iso, group_letter='A', tier=1,
        multiplier=1, is_eliminated=is_eliminated,
        best_finish=best_finish, advancement_method=advancement_method,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _match(number, stage, home, away, *, winner=None, completed=True):
    m = WorldCupMatch(
        match_number=number, stage=stage,
        home_team_id=home.id, away_team_id=away.id,
        winner_team_id=(winner.id if winner else None),
        is_completed=completed,
    )
    db.session.add(m)
    db.session.flush()
    return m


def test_group_stage_eliminated_team_is_out(app):
    with app.app_context():
        t = _team('Group Exit', 'aa', is_eliminated=True, best_finish='group')
        assert t.id in eliminated_team_ids()


def test_knockout_loser_is_out(app):
    """A team that lost a completed R32 match is out even though is_eliminated=False."""
    with app.app_context():
        winner = _team('Advancer', 'bb', advancement_method='winner', best_finish='R16')
        loser = _team('R32 Loser', 'cc', advancement_method='winner', best_finish='R32')
        _match(73, 'R32', winner, loser, winner=winner)
        ids = eliminated_team_ids()
        assert loser.id in ids
        assert loser.is_eliminated is False  # group flag never set for KO losers


def test_group_winner_that_lost_r32_is_out(app):
    """Distinct from group exit: advanced from group, then lost R32 → out."""
    with app.app_context():
        opp = _team('Opp', 'dd', advancement_method='winner', best_finish='R16')
        grp_winner = _team('Grp Winner', 'ee', advancement_method='winner', best_finish='R32')
        _match(74, 'R32', grp_winner, opp, winner=opp)
        assert grp_winner.id in eliminated_team_ids()


def test_still_advancing_team_is_not_out(app):
    """Won its last completed KO match, next match not yet played → alive."""
    with app.app_context():
        alive = _team('Alive', 'ff', advancement_method='winner', best_finish='QF')
        beaten = _team('Beaten', 'gg', advancement_method='winner', best_finish='R16')
        _match(89, 'QF', alive, beaten, winner=alive)  # alive WON the QF
        ids = eliminated_team_ids()
        assert alive.id not in ids
        assert beaten.id in ids


def test_null_winner_completed_ko_eliminates_both(app):
    """Completed KO match with no winner set → both teams out (knockouts never draw)."""
    with app.app_context():
        a = _team('A', 'hh', best_finish='R32', advancement_method='winner')
        b = _team('B', 'ii', best_finish='R32', advancement_method='winner')
        _match(75, 'R32', a, b, winner=None, completed=True)
        ids = eliminated_team_ids()
        assert a.id in ids and b.id in ids


def test_incomplete_ko_match_does_not_eliminate(app):
    """A scheduled-but-not-completed KO match must not mark anyone out."""
    with app.app_context():
        a = _team('A', 'jj', best_finish='R32', advancement_method='winner')
        b = _team('B', 'kk', best_finish='R32', advancement_method='winner')
        _match(76, 'R32', a, b, winner=None, completed=False)
        assert eliminated_team_ids() == set()


def test_parity_with_path_status(app):
    """eliminated_team_ids() agrees with _path_status: a team is in the set iff
    _path_status returns a non-None eliminated_at_index."""
    with app.app_context():
        champ = _team('Champ', 'll', best_finish='champion', advancement_method='winner')
        runner = _team('Runner', 'mm', best_finish='runner_up', advancement_method='winner')
        group = _team('Group', 'nn', is_eliminated=True, best_finish='group')
        sf_winner_alive = _team('SFW', 'oo', best_finish='SF', advancement_method='winner')
        # champ beat runner in the final
        _match(104, 'final', champ, runner, winner=champ)
        ids = eliminated_team_ids()
        for t in (champ, runner, group, sf_winner_alive):
            _, elim_at = _path_status(t)
            assert (t.id in ids) == (elim_at is not None), t.display_name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_elimination.py -q`
Expected: FAIL — `ModuleNotFoundError: games.worldcup.services.elimination`.

- [ ] **Step 3: Implement the helper**

Create `games/worldcup/services/elimination.py`:

```python
"""Derived team elimination — group-stage flag PLUS knockout losses.

WorldCupTeam.is_eliminated is GROUP-STAGE-ONLY by data contract: scoring sets
it True only for teams that fail to advance from their group. Knockout losers
(R32/R16/QF/SF/runner-up) keep is_eliminated=False. Any UI asking "is this team
out of the tournament?" must use eliminated_team_ids(), not the raw flag.

Mirrors games.worldcup.services.team_detail._path_status() KO semantics: a team
is out if it appears in a COMPLETED knockout match where it is not the winner.
A completed KO match with a NULL winner counts as elimination for BOTH teams
(knockouts never legitimately draw). The SF match alone eliminates both SF
losers, so 'third_place' is redundant and intentionally omitted; 'final'
captures the runner-up.
"""
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupMatch, WorldCupTeam

# Knockout stage codes as stored on WorldCupMatch.stage (see team_detail
# _NEXT_MATCH_STAGE: 'final' is lowercase; 'third_place' is the consolation).
_KO_STAGES = ('R32', 'R16', 'QF', 'SF', 'final')


def eliminated_team_ids(season_year: int = SEASON_YEAR) -> set[int]:
    """Team ids that are out of the tournament (group exit OR knockout loss).

    N+1-free: one query for group-eliminated team ids, one for completed KO
    matches. `season_year` is accepted for API symmetry / forward-compat; teams
    and matches are a single tournament edition today (no per-season column),
    so it is currently advisory — the completed-match set IS the edition.
    """
    out: set[int] = {
        tid for (tid,) in (
            WorldCupTeam.query
            .filter(WorldCupTeam.is_eliminated.is_(True))
            .with_entities(WorldCupTeam.id)
            .all()
        )
    }
    ko_matches = (
        WorldCupMatch.query
        .filter(
            WorldCupMatch.stage.in_(_KO_STAGES),
            WorldCupMatch.is_completed.is_(True),
        )
        .with_entities(
            WorldCupMatch.home_team_id,
            WorldCupMatch.away_team_id,
            WorldCupMatch.winner_team_id,
        )
        .all()
    )
    for home_id, away_id, winner_id in ko_matches:
        for tid in (home_id, away_id):
            if tid is not None and tid != winner_id:
                out.add(tid)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_elimination.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/elimination.py tests/test_worldcup_elimination.py
git commit -m "feat(worldcup): derive knockout elimination via eliminated_team_ids helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2: Route derived elimination through read-sites (Follow-up B)

### Task 2: Leaderboard route + template

**Files:**
- Modify: `games/worldcup/routes.py` (leaderboard route ~400-495)
- Modify: `games/worldcup/templates/worldcup/leaderboard.html` (desktop ~108-118, mobile ~176-184)
- Test: `tests/test_worldcup_leaderboard.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_worldcup_leaderboard.py` (reuse its existing `app`/`client` fixtures and `_seed_*` helpers; add team/match/pick seeding inline). Add:

```python
def test_leaderboard_rail_marks_knockout_loser_out(app, client, monkeypatch):
    """A picked team that lost a completed R32 match renders is-out on the rail,
    even though is_eliminated=False (group-only flag)."""
    import os
    from unittest import mock
    from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupPick

    with app.app_context():
        u = _seed_user('koviewer')
        db.session.flush()
        e = _seed_enrollment(u.id, score=10)
        winner = WorldCupTeam(display_name='Winner', iso_code='br', group_letter='A',
                              tier=1, multiplier=1, is_eliminated=False, best_finish='R16',
                              advancement_method='winner')
        loser = WorldCupTeam(display_name='KO Loser', iso_code='ar', group_letter='B',
                             tier=1, multiplier=1, is_eliminated=False, best_finish='R32',
                             advancement_method='winner')
        db.session.add_all([winner, loser])
        db.session.flush()
        db.session.add(WorldCupPick(enrollment_id=e.id, team_id=loser.id, tier=1))
        db.session.add(WorldCupMatch(match_number=73, stage='R32',
                                     home_team_id=winner.id, away_team_id=loser.id,
                                     winner_team_id=winner.id, is_completed=True))
        db.session.commit()
        loser_id = loser.id

    # Past the deadline so rosters render (D11 gate).
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # The loser's flag span must carry is-out + the "· out" tooltip text.
    assert 'is-out' in html
    assert '· out' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py::test_leaderboard_rail_marks_knockout_loser_out -q`
Expected: FAIL — `is_eliminated` is False for the KO loser, so `is-out` / `· out` are absent.

- [ ] **Step 3: Add the import + compute the set in the route**

In `games/worldcup/routes.py`, add to the worldcup-services imports near the top (next to other `from games.worldcup.services...` lines):

```python
from games.worldcup.services.elimination import eliminated_team_ids
```

In the `leaderboard()` route, just before the `return render_template('worldcup/leaderboard.html', ...)` (~line 492), add:

```python
    eliminated_ids = eliminated_team_ids()
```

Then add `eliminated_ids=eliminated_ids,` to that `render_template(...)` keyword arguments.

- [ ] **Step 4: Update the desktop rail in `leaderboard.html`**

Replace the desktop roster block (the `{% for pick in roster %}` loop around lines 110-118) so every `pick.team.is_eliminated` becomes `pick.team_id in eliminated_ids`:

```jinja
                  {% for pick in roster %}
                  {% set shared = (not is_me) and pick.team_id in your_team_ids %}
                  {% set is_out = pick.team_id in eliminated_ids %}
                  <span class="lb-flag{% if is_out %} is-out{% endif %}{% if shared %} is-shared{% endif %}"
                        tabindex="0"
                        title="{{ pick.team.display_name }} · &times;{{ pick.team.multiplier }}{% if is_out %} · out{% endif %}{% if shared %} · also yours{% endif %}"
                        aria-label="{{ pick.team.display_name }}, &times;{{ pick.team.multiplier }} multiplier{% if is_out %}, eliminated{% endif %}{% if shared %}, also in your roster{% endif %}">
                    {{ flag(pick.team.iso_code) }}
                  </span>
                  {% endfor %}
```

- [ ] **Step 5: Update the mobile rail in `leaderboard.html`**

Replace the mobile roster line (~181):

```jinja
              {% for pick in roster %}
              {% set shared = (not is_me) and pick.team_id in your_team_ids %}
              {% set is_out = pick.team_id in eliminated_ids %}
              <span class="lb-flag{% if is_out %} is-out{% endif %}{% if shared %} is-shared{% endif %}">{{ flag(pick.team.iso_code) }}</span>
              {% endfor %}
```

- [ ] **Step 6: Run the new test + leaderboard suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py -q`
Expected: PASS (new test + all existing).

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/leaderboard.html tests/test_worldcup_leaderboard.py
git commit -m "fix(worldcup): leaderboard rail uses derived KO elimination

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3: Live hub Leverage Board (home_context)

**Files:**
- Modify: `games/worldcup/services/home_context.py` (~396 alive_count, ~447 status)
- Test: `tests/test_worldcup_home_context.py` (add — confirm file exists; if not, create with the WC fixture pattern)

- [ ] **Step 1: Write the failing test**

Add a test asserting a KO-loser pick gets `status == 'out'` in the Leverage Board and is excluded from `alive_count`. Append to the existing home-context test module (locate it first: `grep -rl "_context_live\|build_home_context" tests/`). Test body:

```python
def test_leverage_board_marks_knockout_loser_out(app):
    import os
    from unittest import mock
    from models.user import User
    from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
    from games.worldcup.constants import SEASON_YEAR
    from games.worldcup.services.home_context import _context_live

    with app.app_context():
        u = User(username='lev', email='lev@test.com'); u.set_password('pw')
        db.session.add(u); db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=SEASON_YEAR, total_score=0)
        db.session.add(e); db.session.flush()
        w = WorldCupTeam(display_name='W', iso_code='br', group_letter='A', tier=1,
                         multiplier=1, is_eliminated=False, best_finish='R16',
                         advancement_method='winner')
        loser = WorldCupTeam(display_name='L', iso_code='ar', group_letter='B', tier=1,
                             multiplier=1, is_eliminated=False, best_finish='R32',
                             advancement_method='winner')
        db.session.add_all([w, loser]); db.session.flush()
        db.session.add(WorldCupPick(enrollment_id=e.id, team_id=loser.id, tier=1))
        db.session.add(WorldCupMatch(match_number=73, stage='R32', home_team_id=w.id,
                                     away_team_id=loser.id, winner_team_id=w.id,
                                     is_completed=True))
        db.session.commit()
        loser_id = loser.id

        with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                          'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
            ctx = _context_live(u)
        leverage = ctx['leverage']
        row = next(r for r in leverage if r['team_id'] == loser_id)
        assert row['status'] == 'out'
        assert ctx['dossier']['alive_count'] == 0
```

(Adjust the import of `db` / fixtures to match the test module's existing pattern.)

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest <that test file>::test_leverage_board_marks_knockout_loser_out -q`
Expected: FAIL — `status` is `'dormant'`/`'scoring'`, `alive_count` is 1.

- [ ] **Step 3: Wire the helper into `_context_live`**

In `games/worldcup/services/home_context.py`, add the import at the top with the other service imports:

```python
from games.worldcup.services.elimination import eliminated_team_ids
```

In `_context_live`, before the `alive_count` line (~396), add:

```python
    eliminated_ids = eliminated_team_ids()
```

Change line ~396 from:

```python
    alive_count = sum(1 for p in user_picks if not p.team.is_eliminated)
```

to:

```python
    alive_count = sum(1 for p in user_picks if p.team_id not in eliminated_ids)
```

Change the leverage-row `status` (~447) from:

```python
            'status': (
                'out' if p.team.is_eliminated
                else ('scoring' if pts > 0 else 'dormant')
            ),
```

to:

```python
            'status': (
                'out' if p.team_id in eliminated_ids
                else ('scoring' if pts > 0 else 'dormant')
            ),
```

- [ ] **Step 4: Run the test + home-context suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest <that test file> -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/home_context.py tests/<that test file>
git commit -m "fix(worldcup): Leverage Board + alive_count use derived KO elimination

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 4: Picks route alive_count + picks/_pick_row/player_detail templates

**Files:**
- Modify: `games/worldcup/routes.py` (picks route ~226 alive_count; pass `eliminated_ids` to both `picks.html` renders ~284/318 and to `player_detail.html` render ~544)
- Modify: `games/worldcup/templates/worldcup/picks.html` (~109,114)
- Modify: `games/worldcup/templates/worldcup/_pick_row.html` (~10)
- Test: `tests/test_worldcup_picks.py` (locate or create) — assert a KO-loser pick row reads "Out"

- [ ] **Step 1: Write the failing test**

Locate the picks route test module (`grep -rln "worldcup/picks\|def test.*pick" tests/`). Add a test that seeds an enrolled user with a pick on a KO-loser team and a completed R32 match, sets `WC_FAKE_NOW` past deadline (so `show_scoring` is on), GETs `/worldcup/picks`, and asserts the response contains the out marker (`pick-team-out` or `wc-pick-status-out` / "Out"). Model seeding on Task 2's test.

```python
def test_picks_page_marks_knockout_loser_out(app, client, monkeypatch):
    import os
    from unittest import mock
    # ... seed enrolled user 'pk', team 'L' (best_finish='R32', is_eliminated=False),
    #     team 'W', a WorldCupPick for 'L', and a completed R32 match W beats L ...
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        # log the user in via session_transaction, then:
        resp = client.get('/worldcup/picks')
    assert resp.status_code == 200
    assert 'pick-team-out' in resp.get_data(as_text=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest <picks test file>::test_picks_page_marks_knockout_loser_out -q`
Expected: FAIL — KO loser's `is_eliminated` is False, so `pick-team-out` is absent.

- [ ] **Step 3: Compute + pass `eliminated_ids` in the picks route**

In `games/worldcup/routes.py` picks route, change line ~226 from:

```python
    alive_count = sum(1 for p in existing_picks if not p.team.is_eliminated)
```

to:

```python
    eliminated_ids = eliminated_team_ids()
    alive_count = sum(1 for p in existing_picks if p.team_id not in eliminated_ids)
```

Add `eliminated_ids=eliminated_ids,` to BOTH `render_template('worldcup/picks.html', ...)` calls (~284 and ~318).

- [ ] **Step 4: Pass `eliminated_ids` to player_detail**

In the `player_detail` route (renders `worldcup/player_detail.html` ~544), add before the return:

```python
    eliminated_ids = eliminated_team_ids()
```

and add `eliminated_ids=eliminated_ids,` to that `render_template(...)`.

- [ ] **Step 5: Update `picks.html`**

Replace the two `pick.team.is_eliminated` references (~109, ~114). Line ~109:

```jinja
              <div class="pick-team{% if show_scoring and pick.team_id in eliminated_ids %} pick-team-out{% endif %}">{{ flag(pick.team.iso_code) }} {{ pick.team.display_name }} <small>Grp {{ pick.team.group_letter }}</small></div>
```

Line ~114 block:

```jinja
                {% if pick.team_id in eliminated_ids %}
                <small class="wc-pick-status-out">Out</small>
                {% else %}
                <small>&times;{{ "%g"|format(pick.team.multiplier) }}</small>
                {% endif %}
```

- [ ] **Step 6: Update `_pick_row.html`**

Line ~10:

```jinja
{% set is_out = show_scoring and pick.team_id in eliminated_ids %}
```

(`_pick_row.html` is `{% include %}`d by both `picks.html` and `player_detail.html`, which inherit context, so `eliminated_ids` is in scope. Verify the include is NOT `without context` — it is a plain `{% include %}`, so context passes.)

- [ ] **Step 7: Run the test + picks/player_detail suites**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_picks.py tests/test_worldcup_team_detail.py -q`
(Adjust to the actual picks/player_detail test filenames.)
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/picks.html games/worldcup/templates/worldcup/_pick_row.html tests/<picks test file>
git commit -m "fix(worldcup): picks + player detail rows use derived KO elimination

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 5: Document the groups.html verdict

**Files:**
- Modify: `games/worldcup/templates/worldcup/groups.html` (comment only, ~72)

- [ ] **Step 1: Add a clarifying comment, no behavior change**

`groups.html` shows GROUP-STAGE standings with advancement badges; its `team.is_eliminated` is legitimately group-scoped (a team eliminated *in the group stage*) and must NOT be migrated to derived KO elimination. Add a Jinja comment above the `{% elif team.is_eliminated %}` branch (~72):

```jinja
                {# Group-scoped on purpose: this table is group standings, so
                   is_eliminated (group-stage exit) is the correct semantic here.
                   Do NOT swap for eliminated_team_ids() — that's tournament-wide
                   "out" and would mislabel KO-stage teams in a group context. #}
                {% elif team.is_eliminated %}
                  <span class="advancement-badge eliminated">Out</span>
                {% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add games/worldcup/templates/worldcup/groups.html
git commit -m "docs(worldcup): note groups.html is_eliminated is group-scoped by design

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3: Signup auto-join to World Cup (Follow-up: behavior change)

**Files:**
- Modify: `core/auth/routes.py` (`register()` ~85-95)
- Test: `tests/test_auth_worldcup_autojoin.py` (create)

### Task 6: Auto-join tests + implementation

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_worldcup_autojoin.py`:

```python
"""Signup auto-joins the World Cup while picks are open (pre-deadline only).

This is a SANCTIONED signup-time auto-enroll — distinct from the banned
pick/admin auto-enroll path (tests/test_golf_auto_enroll_removed.py).
"""
import os
from unittest import mock

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, username='newbie'):
    return client.post('/register', data={
        'username': username,
        'email': f'{username}@test.com',
        'password': 'secret1',
        'confirm_password': 'secret1',
        'csrf_token': 'x',
    }, follow_redirects=True)


def test_signup_auto_joins_worldcup_pre_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        resp = _register(client, 'preuser')
    assert resp.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username='preuser').first()
        assert u is not None
        enr = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).first()
        assert enr is not None  # auto-joined


def test_signup_shows_worldcup_flash_pre_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        resp = _register(client, 'flashuser')
    # The auto-join flash mentions the World Cup pool (exact copy finalized by
    # impeccable; assert on the stable substring "World Cup").
    assert 'World Cup' in resp.get_data(as_text=True)


def test_signup_does_not_auto_join_after_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = _register(client, 'lateuser')
    assert resp.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username='lateuser').first()
        assert u is not None  # account still created
        enr = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).first()
        assert enr is None  # NOT auto-joined post-deadline


def test_signup_auto_join_is_idempotent(app, client):
    """Defensive: a second enroll for the same user never duplicates."""
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        _register(client, 'dupuser')
    with app.app_context():
        u = User.query.filter_by(username='dupuser').first()
        from games.worldcup.services.enrollment import admin_enroll
        admin_enroll(u.id)  # second call
        count = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).count()
        assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_auth_worldcup_autojoin.py -q`
Expected: FAIL — `test_signup_auto_joins_worldcup_pre_deadline` and the flash test fail (no enrollment created, no flash); the post-deadline + idempotency tests may pass vacuously.

- [ ] **Step 3: Add imports to `core/auth/routes.py`**

Add near the existing imports:

```python
from games.worldcup.services.state import worldcup_state
from games.worldcup.services import enrollment as worldcup_enrollment
```

- [ ] **Step 4: Implement auto-join in `register()`**

In `register()`, locate (after the new-user commit):

```python
        login_user(user, remember=True)
        flash('Account created! Welcome to the platform.', 'success')
        return redirect(url_for('main.index'))
```

Replace with:

```python
        login_user(user, remember=True)
        flash('Account created! Welcome to the platform.', 'success')

        # Sanctioned signup-time auto-join: while the World Cup pick window is
        # open (pre-deadline), every new account wants in. This is distinct
        # from the banned pick/admin auto-enroll path — it is an intentional
        # signup behavior, and it self-disables once the tournament starts.
        # PLACEHOLDER COPY — impeccable finalizes the flash wording.
        if worldcup_state() == 'pre':
            worldcup_enrollment.admin_enroll(user.id)
            flash("You're in the World Cup pool — make your picks!", 'success')

        return redirect(url_for('main.index'))
```

- [ ] **Step 5: Run the auto-join tests**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_auth_worldcup_autojoin.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add core/auth/routes.py tests/test_auth_worldcup_autojoin.py
git commit -m "feat(auth): auto-join World Cup on signup while picks are open

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 4: golf pytz → zoneinfo cleanup

**Files (all under `games/golf/`):** `utils.py`, `constants.py`, `models.py`, `services/sync.py`, `services/reminders.py`, `cli.py`

### Task 7: Migrate golf datetime usage

- [ ] **Step 1: Run golf tests to capture the pre-migration baseline**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -k golf -q`
Expected: record pass count (the post-migration run must match).

- [ ] **Step 2: `games/golf/utils.py`**

Replace `import pytz` with `from zoneinfo import ZoneInfo` and line 14:

```python
GOLF_LEAGUE_TZ = ZoneInfo('America/Chicago')
```

- [ ] **Step 3: `games/golf/constants.py`**

Replace `import pytz` with `from datetime import datetime, timezone` (merge with the existing datetime import) and line 23:

```python
SEASON_CUTOFF_DATE = datetime(2026, 8, 24, tzinfo=timezone.utc)
```

- [ ] **Step 4: `games/golf/models.py`**

Remove `import pytz`. The four `GOLF_LEAGUE_TZ.localize(x)` calls (~178, 202, 203, 221) become `x.replace(tzinfo=GOLF_LEAGUE_TZ)`:

- ~178: `deadline = deadline.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~202: `deadline_localized = deadline if deadline.tzinfo else deadline.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~203: `end_localized = self.end_date if self.end_date.tzinfo else self.end_date.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~221: `deadline = deadline.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~223 `.astimezone(GOLF_LEAGUE_TZ)` is unchanged (works with ZoneInfo).

(`GOLF_LEAGUE_TZ` is imported from `games.golf.utils`; ensure that import remains.)

- [ ] **Step 5: `games/golf/services/sync.py`**

Remove `import pytz`; add `from zoneinfo import ZoneInfo` and ensure `from datetime import ..., timezone` includes `timezone`.

- ~186 type hint `def _get_event_timezone(...) -> pytz.timezone:` → `-> ZoneInfo:`
- ~190 `return pytz.timezone(tz_name)` → `return ZoneInfo(tz_name)`
- ~224 `datetime.fromtimestamp(ts_sec, tz=pytz.UTC)` → `datetime.fromtimestamp(ts_sec, tz=timezone.utc)`
- ~230 param hint `event_tz: pytz.timezone` → `event_tz: ZoneInfo`
- ~244 `dt = event_tz.localize(dt)` → `dt = dt.replace(tzinfo=event_tz)`
- ~249 `return event_tz.localize(tee_datetime)` → `return tee_datetime.replace(tzinfo=event_tz)`
- ~277 `... else GOLF_LEAGUE_TZ.localize(tournament.start_date)` → `... else tournament.start_date.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~278 `... else GOLF_LEAGUE_TZ.localize(tournament.end_date)` → `... else tournament.end_date.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~299 `start_localized = GOLF_LEAGUE_TZ.localize(start_localized)` → `start_localized = start_localized.replace(tzinfo=GOLF_LEAGUE_TZ)`
- ~369 `datetime.fromtimestamp(start_ts, tz=pytz.UTC)` → `datetime.fromtimestamp(start_ts, tz=timezone.utc)`
- ~469 `.astimezone(GOLF_LEAGUE_TZ)` unchanged.

- [ ] **Step 6: `games/golf/services/reminders.py`**

Lines ~228, 450, 823 `deadline = GOLF_LEAGUE_TZ.localize(deadline)` → `deadline = deadline.replace(tzinfo=GOLF_LEAGUE_TZ)`. Remove any now-unused `pytz` import if present (grep confirmed `reminders.py` had no `import pytz` line — it uses the imported `GOLF_LEAGUE_TZ`; leave imports otherwise intact).

- [ ] **Step 7: `games/golf/cli.py`**

Line ~61 `datetime.now().year` → `datetime.now(timezone.utc).year`. Ensure `timezone` is imported from `datetime`.

- [ ] **Step 8: Verify no pytz / naive datetime.now remain**

Run: `grep -rn "pytz\|datetime.now()" games/golf/ --include="*.py"`
Expected: no output.

- [ ] **Step 9: Run golf tests + a sanity import**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -k golf -q`
Expected: PASS, same count as Step 1.
Run: `ENVIRONMENT=testing venv/bin/python -c "import games.golf.models, games.golf.constants, games.golf.utils, games.golf.services.sync, games.golf.services.reminders, games.golf.cli; print('golf import OK')"`
Expected: `golf import OK`.

- [ ] **Step 10: Commit**

```bash
git add games/golf/
git commit -m "refactor(golf): migrate pytz -> stdlib zoneinfo; tz-aware datetime.now

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 5: Shared CTA recipe (Follow-up A — /impeccable)

**Files:**
- Modify: `static/css/style.css` (`.decree-cta` block ~1534-1602; `.dossier-cta` block ~2592-2655)
- Modify: `core/main/templates/main/_countdown_card.html` (~68-70)
- Modify: `core/main/templates/main/_dossier_card.html` (~208-210)
- Test: design-test lock (locate: `grep -rln "decree-cta\|dossier-cta\|cta-seal" tests/`)

### Task 8: Invoke /impeccable and extract the recipe

- [ ] **Step 1: Invoke the impeccable skill**

Invoke `Skill { skill: "impeccable", args: "extract" }` (CSS dedup / extraction). Per the CLAUDE.md hard rule, READ both `DESIGN.md` (top-level) AND `games/worldcup/DESIGN.md` before producing output, and prove the skill invocation with content-fingerprint quotes. Have impeccable also finalize the auto-join flash copy from Phase 3 (replace the placeholder string; keep the stable substring "World Cup" so the Phase 3 flash test still passes — if impeccable chooses copy without that substring, update `test_signup_shows_worldcup_flash_pre_deadline` to match the chosen copy).

- [ ] **Step 2: Add the shared `.cta-seal` recipe to `style.css`**

Introduce `.home-shell .cta-seal` (+ `.cta-seal-label`, `.cta-seal-sub`, `.cta-seal-label i`, `:hover`, `:hover .cta-seal-label i`, `:active`, `:focus-visible`, and the `prefers-reduced-motion` block) carrying the full shared stack (the byte-identical declarations confirmed in the spec). Reduce the two purpose-named selectors to only their deltas:

```css
.home-shell .decree-cta { margin: 1.5rem auto 0.25rem; max-width: 22rem; }
.home-shell .dossier-cta { margin-top: 1.25rem; max-width: 24rem; }
```

Keep `--metal-gold-flat` on `.cta-seal` (Trophy Rule). Preserve the decree's "wax seal" explanatory comment by relocating it onto `.cta-seal:active`. Delete the now-redundant duplicated declarations from both old blocks.

- [ ] **Step 3: Update both templates to use the shared classes**

`_countdown_card.html` (~68-70):

```jinja
    <a class="cta-seal decree-cta" href="{{ _cta_href }}">
      <span class="cta-seal-label">{{ _cta_label }}<i class="bi bi-arrow-right" aria-hidden="true"></i></span>
      <span class="cta-seal-sub">{{ _cta_sub }}</span>
```

`_dossier_card.html` (~208-210):

```jinja
  <a class="cta-seal dossier-cta" href="{{ url_for('worldcup.index') }}">
    <span class="cta-seal-label">Enter the World Cup<i class="bi bi-arrow-right" aria-hidden="true"></i></span>
    <span class="cta-seal-sub">Your roster and the live ledger.</span>
```

- [ ] **Step 4: Update / extend the design test lock**

If a design test references `.decree-cta` / `.dossier-cta` (from Step 1's grep), update it to assert: (a) the shared `.cta-seal` recipe exists with `--metal-gold-flat`, the reduced-motion reset, and `:focus-visible`; (b) `.decree-cta` / `.dossier-cta` carry ONLY margin/max-width (no duplicated interaction declarations). If no such test exists, add a small assertion to the nearest design-invariant test file (e.g. `tests/test_design_*.py`) checking the shared selector is present and the metal-gold Trophy Rule still holds (no new metal-gold consumers beyond the known set).

- [ ] **Step 5: Visual verification (both states, both widths)**

Start the dev server and flip states with the WC_FAKE_NOW seam (CLAUDE.md recipe):

```bash
# pre-state (countdown / decree-cta)
ENVIRONMENT=development WC_FAKE_NOW='2026-06-01T12:00:00+00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# live-state (dossier / dossier-cta) — enrolled user, post-deadline
ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T12:00:00+00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Confirm `/` renders the gold seal CTA identically to pre-refactor at desktop and mobile (375px) widths in both states (hover lift, active press, focus ring, reduced-motion). Capture before/after screenshots if iterating in-browser (pass `animations: 'disabled'` to avoid the `.animate-in` race — memory note).

- [ ] **Step 6: Run the design suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -k "design or cta" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add static/css/style.css core/main/templates/main/_countdown_card.html core/main/templates/main/_dossier_card.html core/auth/routes.py tests/
git commit -m "refactor(css): extract shared .cta-seal recipe from decree/dossier CTAs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 6: CLAUDE.md / memory / repo cleanse

### Task 9: CLAUDE.md improver (conciseness) + data-contract update

**Files:** `CLAUDE.md`, `memory/project_wc_data_contracts.md`, `memory/MEMORY.md`

- [ ] **Step 1: Invoke the improver**

Invoke `Skill { skill: "claude-md-management:claude-md-improver" }` focused on conciseness. Remove outdated / duplicated / low-value content. Known fix: the "games/golf/ — Golf Pick 'Em (live)" / "Active games ... live" framing is stale — only worldcup is `status='open'`; cfb + golf are `coming_soon`. Apply its targeted edits.

- [ ] **Step 2: Update the `is_eliminated` guidance to name the helper**

In CLAUDE.md (World Cup data-contracts area) and `memory/project_wc_data_contracts.md`, change the "derive KO elimination from completed matches" guidance to point at the concrete helper: `games/worldcup/services/elimination.eliminated_team_ids(season_year) -> set[int]` is the SSoT for "is a team out of the tournament" (group flag OR KO loss); `is_eliminated` remains group-stage-only and is correct only in group-scoped surfaces (e.g. `groups.html`).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md memory/project_wc_data_contracts.md memory/MEMORY.md
git commit -m "docs: tighten CLAUDE.md; document eliminated_team_ids data contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 10: Memory cleanse

**Files:** `memory/*.md`, `memory/MEMORY.md`

- [ ] **Step 1: Audit memory files**

List `memory/*.md` and evaluate each against: low-value, outdated, duplicated by CLAUDE.md, or only-mattered-to-a-past-conversation. Candidates to scrutinize (verify before acting — do not blind-delete):
- Dormant/situational notes (e.g. `project_worktree_plan_edit_discipline.md` self-describes as "currently dormant").
- Notes whose substance now lives verbatim in CLAUDE.md (`feedback_no_pyright.md` self-notes it's "now also reflected in CLAUDE.md").
- Any note fully superseded by a later one.

- [ ] **Step 2: Present the cleanse proposal to the user**

Show the user a short table: file → keep / merge / delete, with one-line rationale each. Get explicit approval before deleting or merging any memory file. (Memory is durable user state — no silent deletion.)

- [ ] **Step 3: Apply approved changes + update the index**

Delete/merge approved files; update `memory/MEMORY.md` so every remaining file has exactly one index line and no deleted file is referenced.

- [ ] **Step 4: Commit**

```bash
git add memory/
git commit -m "chore(memory): prune low-value/duplicated notes; refresh index

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 11: Repo file cleanup

- [ ] **Step 1: Build a delete-candidate list**

Identify files safe to remove before production ship: stale scratch docs, superseded specs/plans, one-off artifacts. Do NOT touch the gitignored `_migration_source/` (kept for golf/cfb go-live per `project_migration_source_kept.md`). Cross-check git status / recent commits for anything obviously transient.

- [ ] **Step 2: Present the delete-list to the user for approval**

Show the candidate list with a one-line reason each. Get explicit approval before deleting.

- [ ] **Step 3: Apply approved deletions + commit**

```bash
git rm <approved paths>
git commit -m "chore: remove stale artifacts before production ship

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 7: Full verification + PR

### Task 12: Final suite + PR

- [ ] **Step 1: Run the full suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
Expected: all pass — count = baseline (Task 0) + the newly added tests (elimination 7, leaderboard 1, home_context 1, picks 1, auto-join 4 ≈ +14), with no regressions.

- [ ] **Step 2: Final grep guards**

Run: `grep -rn "pytz" games/ --include="*.py"`
Expected: no output.
Run: `grep -rn "\.team\.is_eliminated" games/worldcup/templates/worldcup/leaderboard.html games/worldcup/templates/worldcup/picks.html games/worldcup/templates/worldcup/_pick_row.html`
Expected: no output (all migrated; groups.html intentionally retains it).

- [ ] **Step 3: Push + open PR**

```bash
git push -u origin worldcup/production-testing
gh pr create --title "WC production follow-ups: auto-join, CTA dedup, derived KO elimination, pytz cleanup" --body "$(cat <<'EOF'
Five WC production-testing follow-ups in one PR (spec: docs/superpowers/specs/2026-06-01-wc-production-followups-design.md).

1. **Signup auto-join to World Cup** (behavior): new accounts auto-join the WC pool while picks are open (pre-deadline); self-disables once the tournament starts. Sanctioned signup path, distinct from the banned pick/admin auto-enroll.
2. **Shared CTA recipe** (CSS, no behavior change): extracted `.cta-seal` from the near-identical `.decree-cta` / `.dossier-cta` blocks; both reduced to margin/max-width deltas. Trophy Rule + reduced-motion + focus parity preserved.
3. **Derived knockout elimination** (fix): new `eliminated_team_ids()` SSoT; leaderboard rail, Leverage Board, alive_count, picks/player-detail rows now report KO losers as out. `groups.html` stays group-scoped by design.
4. **golf pytz → zoneinfo** cleanup; tz-aware `datetime.now()`. Zero `pytz` left in the repo.
5. **CLAUDE.md / memory / repo cleanse** for conciseness and a clean production ship.

Full suite green (~957 baseline + ~14 new). TDD on the behavior changes; /impeccable on the CSS.
EOF
)"
```

- [ ] **Step 4: Report the PR URL to the user.**

---

## Self-Review Notes (author)

- **Spec coverage:** §1 auto-join → Task 6; §2 CTA → Task 8; §3 derived elimination → Tasks 1-5 (+ doc Task 9 Step 2); §4 golf pytz → Task 7; §5 cleanse → Tasks 9-11. All covered.
- **Flash-copy coupling:** Phase 3 ships placeholder copy containing "World Cup"; the flash test asserts that substring; Task 8 Step 1 finalizes copy and updates the test if the substring changes. Consistent.
- **Helper name consistency:** `eliminated_team_ids` used identically in Tasks 1-5, 9, 12.
- **N+1 safety:** helper does 2 bulk queries; routes call it once per request and pass a set; templates do membership tests only (no ORM mutation).
- **Time-seam gotcha:** every `WC_FAKE_NOW` test sets `ENVIRONMENT=testing` in the same `patch.dict`.
