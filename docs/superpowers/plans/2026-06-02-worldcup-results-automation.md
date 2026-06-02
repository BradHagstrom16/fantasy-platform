# World Cup Results & Advancement Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate World Cup final-match results (auto-applied) and assist group-advancement + knockout-bracket resolution (API-fed, admin-confirmed) by feeding football-data.org data into the existing idempotent scoring engine.

**Architecture:** A new `games/worldcup/services/sync.py` service pulls from football-data.org (free tier). Final scores call the existing `process_match_result()` automatically; advancement/bracket data pre-fills the existing admin forms for one-click confirmation. The scoring engine, ranking, and elimination logic are untouched — match data stays the single source of truth. A systemd timer on the droplet runs `flask worldcup sync --mode scores` every 30 min.

**Tech Stack:** Flask, SQLAlchemy 2.0, Alembic (Flask-Migrate), `requests`, pytest with mocked HTTP, systemd timers.

**Spec:** `docs/superpowers/specs/2026-06-02-worldcup-results-automation-design.md`

**Baseline:** `ENVIRONMENT=testing venv/bin/python -m pytest tests/` green before and after (~987 passing).

**Reference data shapes (football-data.org v4, verified 2026-06-02):**

```jsonc
// GET /v4/competitions/WC/matches  ->  {"matches": [ ... ]}
{
  "id": 537001,                         // -> WorldCupMatch.api_fixture_id
  "utcDate": "2026-06-11T19:00:00Z",
  "status": "TIMED",                    // FINISHED == final
  "stage": "GROUP_STAGE",               // see STAGE_MAP
  "group": "Group A",                   // null for knockout
  "homeTeam": {"id": 769, "name": "Mexico", "tla": "MEX"},
  "awayTeam": {"id": 805, "name": "South Africa", "tla": "RSA"},
  "score": {
    "winner": "HOME_TEAM",              // HOME_TEAM | AWAY_TEAM | DRAW | null
    "duration": "REGULAR",              // REGULAR | EXTRA_TIME | PENALTY_SHOOTOUT
    "fullTime": {"home": 2, "away": 0},
    "penalties": {"home": null, "away": null}
  }
}

// GET /v4/competitions/WC/standings  ->  {"standings": [ ... ]}
{
  "stage": "GROUP_STAGE",
  "type": "TOTAL",                      // also HOME / AWAY — use TOTAL only
  "group": "Group A",
  "table": [
    {"position": 1, "team": {"id": 769, "name": "Mexico", "tla": "MEX"},
     "playedGames": 3, "points": 9, "goalsFor": 6, "goalsAgainst": 1, "goalDifference": 5}
  ]
}
```

---

### Task 1: Schema — external-ID columns + migration

**Files:**
- Modify: `games/worldcup/models.py` (`WorldCupTeam`, `WorldCupMatch`)
- Create: `migrations/versions/<rev>_worldcup_api_ids.py` (generated)
- Test: `tests/test_worldcup_sync.py` (new)

- [x] **Step 1: Write the failing test**

Create `tests/test_worldcup_sync.py`:

```python
"""Tests for the World Cup football-data.org sync service."""
import pytest
from unittest.mock import patch

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _team(fifa, name, group, tier=1, mult=1.0):
    t = WorldCupTeam(fifa_code=fifa, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='UEFA', group_letter=group)
    db.session.add(t)
    return t


def test_match_and_team_have_api_id_columns(app):
    with app.app_context():
        t = _team('MEX', 'Mexico', 'A')
        db.session.flush()
        t.api_team_id = 769
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=t.id, api_fixture_id=537001)
        db.session.add(m)
        db.session.commit()
        assert db.session.get(WorldCupTeam, t.id).api_team_id == 769
        assert WorldCupMatch.query.filter_by(match_number=1).first().api_fixture_id == 537001
```

- [x] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py::test_match_and_team_have_api_id_columns -q`
Expected: FAIL — `TypeError: 'api_team_id' is an invalid keyword argument` (column doesn't exist).

- [x] **Step 3: Add the columns**

In `games/worldcup/models.py`, in `WorldCupTeam` after `multiplied_points` (line ~72):

```python
    # football-data.org team id, set by `flask worldcup sync --mode link`.
    api_team_id = db.Column(db.Integer, nullable=True)
```

In `WorldCupMatch` after `is_completed` (line ~131):

```python
    # football-data.org match id, set by `flask worldcup sync --mode link`.
    api_fixture_id = db.Column(db.Integer, nullable=True, index=True)
```

- [x] **Step 4: Generate + review the migration**

Run: `ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db migrate -m "worldcup api id columns"`
Then **open the generated file in `migrations/versions/`** and confirm it only `add_column`s `worldcup_team.api_team_id` and `worldcup_match.api_fixture_id` (plus the index) — no unrelated drops. Per CLAUDE.md, review before upgrade.

- [x] **Step 5: Apply + test**

Run: `ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade`
Then: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py::test_match_and_team_have_api_id_columns -q`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add games/worldcup/models.py migrations/versions/ tests/test_worldcup_sync.py
git commit -m "feat(worldcup): add football-data.org api id columns"
```

---

### Task 2: Config + API client helper

**Files:**
- Modify: `config.py` (base `Config`)
- Create: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

- [x] **Step 1: Add the config line**

In `config.py` base `Config`, next to `ODDS_API_KEY` (line ~49):

```python
    FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')
```

> Per CLAUDE.md config-plumbing rule: a `current_app.config.get('FOOTBALL_DATA_API_KEY')` read is silently `None` without this line.

- [x] **Step 2: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def test_api_get_raises_without_key(app):
    from games.worldcup.services.sync import _api_get, SyncError
    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = ''
        with pytest.raises(SyncError):
            _api_get('competitions/WC/matches')


def test_api_get_returns_json_on_200(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'

        class _Resp:
            status_code = 200
            headers = {'X-Requests-Available-Minute': '9'}
            def json(self): return {'matches': []}

        with patch.object(sync.requests, 'get', return_value=_Resp()) as g:
            out = sync._api_get('competitions/WC/matches')
        assert out == {'matches': []}
        # Auth header is sent
        assert g.call_args.kwargs['headers']['X-Auth-Token'] == 'k'
```

- [x] **Step 3: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k api_get -q`
Expected: FAIL — `ModuleNotFoundError: games.worldcup.services.sync`.

- [x] **Step 4: Create the service skeleton + client**

Create `games/worldcup/services/sync.py`:

```python
"""
World Cup Fantasy Pool — football-data.org Sync Service
=======================================================
Pulls final match results (auto-applied) and group-advancement / knockout-bracket
data (admin-confirmed) from football-data.org (free tier). Match data stays the
single source of truth; this service only feeds the existing scoring engine and
pre-fills the existing admin forms. It never recomputes scores.

Endpoints used (one request each):
    GET /v4/competitions/WC/matches    (all 104 fixtures + scores)
    GET /v4/competitions/WC/standings  (12 group tables)
Auth: header X-Auth-Token. Free tier: 10 req/min, no daily cap.
"""
import logging

import requests
from flask import current_app

from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from games.worldcup.services.scoring import (
    process_match_result, set_knockout_teams,
)

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.football-data.org/v4'
COMPETITION_CODE = 'WC'

# football-data.org stage string -> our WorldCupMatch.stage code.
STAGE_MAP = {
    'GROUP_STAGE': 'group',
    'LAST_32': 'R32',
    'LAST_16': 'R16',
    'QUARTER_FINALS': 'QF',
    'SEMI_FINALS': 'SF',
    'THIRD_PLACE': 'third_place',
    'FINAL': 'final',
}

# A fixture is final (apply it) only in one of these statuses.
FINISHED_STATUSES = {'FINISHED'}

# football-data.org 3-letter team code (tla) -> our fifa_code, ONLY where they
# differ. Most align (MEX==MEX). Fill in during the `link` verification run.
TEAM_TLA_OVERRIDES: dict[str, str] = {}


class SyncError(Exception):
    """Raised when the football-data.org API is unreachable or misconfigured."""


def _api_get(path: str, params: dict | None = None) -> dict:
    """GET a football-data.org endpoint, returning parsed JSON. Raises SyncError."""
    api_key = current_app.config.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise SyncError('FOOTBALL_DATA_API_KEY is not configured')
    url = f'{API_BASE_URL}/{path}'
    try:
        resp = requests.get(
            url, headers={'X-Auth-Token': api_key}, params=params, timeout=30,
        )
    except Exception as exc:  # network error
        raise SyncError(f'request to {path} failed: {exc}') from exc
    if resp.status_code != 200:
        raise SyncError(f'{path} returned HTTP {resp.status_code}')
    # Defensive rate-limit logging (free tier = 10/min); back off if near zero.
    remaining = resp.headers.get('X-Requests-Available-Minute')
    if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
        logger.warning('football-data.org minute budget nearly exhausted (%s left)', remaining)
    return resp.json()


def _fifa_for_tla(tla: str | None) -> str | None:
    """Map a football-data.org tla to our fifa_code (override map, else identity)."""
    if not tla:
        return None
    return TEAM_TLA_OVERRIDES.get(tla, tla)
```

- [x] **Step 5: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k api_get -q`
Expected: PASS (both).

- [x] **Step 6: Commit**

```bash
git add config.py games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): football-data.org config + api client"
```

---

### Task 3: `link_fixtures()` — map our shells/teams to API ids

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

- [x] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
from datetime import datetime


def _seed_group_pair(app):
    """Two teams + their group match shell, kickoff matching the API sample."""
    with app.app_context():
        mex = _team('MEX', 'Mexico', 'A')
        rsa = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=mex.id, away_team_id=rsa.id,
                          kickoff_utc=datetime(2026, 6, 11, 19, 0, 0))
        db.session.add(m)
        db.session.commit()
        return m.id


_API_MATCHES_FIXTURE = {'matches': [{
    'id': 537001, 'utcDate': '2026-06-11T19:00:00Z', 'status': 'TIMED',
    'stage': 'GROUP_STAGE', 'group': 'Group A',
    'homeTeam': {'id': 769, 'name': 'Mexico', 'tla': 'MEX'},
    'awayTeam': {'id': 805, 'name': 'South Africa', 'tla': 'RSA'},
    'score': {'winner': None, 'duration': 'REGULAR',
              'fullTime': {'home': None, 'away': None}},
}]}


def test_link_fixtures_maps_ids(app):
    from games.worldcup.services import sync
    mid = _seed_group_pair(app)
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=_API_MATCHES_FIXTURE):
            report = sync.link_fixtures()
        m = db.session.get(WorldCupMatch, mid)
        assert m.api_fixture_id == 537001
        assert db.session.get(WorldCupTeam, m.home_team_id).api_team_id == 769
        assert db.session.get(WorldCupTeam, m.away_team_id).api_team_id == 805
        assert report['fixtures_linked'] == 1
        assert report['unmatched_fixtures'] == []


def test_link_fixtures_reports_unmatched(app):
    from games.worldcup.services import sync
    _seed_group_pair(app)
    bad = {'matches': [{
        'id': 999, 'utcDate': '2026-06-11T19:00:00Z', 'status': 'TIMED',
        'stage': 'GROUP_STAGE', 'group': 'Group Z',
        'homeTeam': {'id': 1, 'name': 'Narnia', 'tla': 'NAR'},
        'awayTeam': {'id': 2, 'name': 'Oz', 'tla': 'OZX'},
        'score': {'winner': None, 'duration': 'REGULAR',
                  'fullTime': {'home': None, 'away': None}},
    }]}
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=bad):
            report = sync.link_fixtures()
        assert report['fixtures_linked'] == 0
        assert len(report['unmatched_fixtures']) == 1
```

- [x] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k link_fixtures -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'link_fixtures'`.

- [x] **Step 3: Implement `link_fixtures`**

Append to `games/worldcup/services/sync.py`:

```python
def _to_naive_utc(dt):
    """Normalize a datetime to naive-UTC for kickoff comparison."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        from datetime import timezone
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0, second=0)


def _parse_api_kickoff(utc_date: str):
    """'2026-06-11T19:00:00Z' -> naive-UTC datetime (minute precision)."""
    from datetime import datetime
    dt = datetime.fromisoformat(utc_date.replace('Z', '+00:00'))
    return _to_naive_utc(dt)


def link_fixtures() -> dict:
    """Idempotently link our 104 shells + 48 teams to football-data.org ids.

    Verify-then-trust: never guesses silently. Returns a report listing what was
    linked and every fixture/team that could NOT be matched, for manual review.
    Re-runnable (skips rows already linked).
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    api_matches = data.get('matches', [])

    teams_by_fifa = {t.fifa_code: t for t in WorldCupTeam.query.all()}
    our_matches = WorldCupMatch.query.all()

    # Index our group shells by the unordered team-id pair; KO shells by (stage, kickoff).
    group_by_pair: dict[frozenset, WorldCupMatch] = {}
    ko_by_stage_kick: dict[tuple, WorldCupMatch] = {}
    for m in our_matches:
        if m.stage == 'group' and m.home_team_id and m.away_team_id:
            group_by_pair[frozenset((m.home_team_id, m.away_team_id))] = m
        elif m.stage != 'group':
            ko_by_stage_kick[(m.stage, _to_naive_utc(m.kickoff_utc))] = m

    fixtures_linked = 0
    teams_linked = 0
    unmatched_fixtures = []
    unmapped_teams = []

    for f in api_matches:
        our_stage = STAGE_MAP.get(f.get('stage'))
        if our_stage is None:
            unmatched_fixtures.append({'id': f.get('id'), 'reason': f"unknown stage {f.get('stage')}"})
            continue

        # Map teams (group stage has them; KO may be null pre-resolution).
        for side in ('homeTeam', 'awayTeam'):
            api_team = f.get(side) or {}
            fifa = _fifa_for_tla(api_team.get('tla'))
            team = teams_by_fifa.get(fifa) if fifa else None
            if team and api_team.get('id') and team.api_team_id != api_team['id']:
                team.api_team_id = api_team['id']
                teams_linked += 1
            elif api_team.get('tla') and not team:
                unmapped_teams.append({'tla': api_team.get('tla'), 'name': api_team.get('name')})

        # Find our shell.
        shell = None
        if our_stage == 'group':
            home = teams_by_fifa.get(_fifa_for_tla((f.get('homeTeam') or {}).get('tla')))
            away = teams_by_fifa.get(_fifa_for_tla((f.get('awayTeam') or {}).get('tla')))
            if home and away:
                shell = group_by_pair.get(frozenset((home.id, away.id)))
        else:
            shell = ko_by_stage_kick.get((our_stage, _parse_api_kickoff(f['utcDate'])))

        if not shell:
            unmatched_fixtures.append({'id': f.get('id'), 'stage': f.get('stage'),
                                       'utcDate': f.get('utcDate')})
            continue

        if shell.api_fixture_id != f['id']:
            shell.api_fixture_id = f['id']
            fixtures_linked += 1

    db.session.commit()
    return {
        'fixtures_linked': fixtures_linked,
        'teams_linked': teams_linked,
        'unmatched_fixtures': unmatched_fixtures,
        'unmapped_teams': unmapped_teams,
        'api_fixture_count': len(api_matches),
    }
```

- [x] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k link_fixtures -q`
Expected: PASS (both).

- [x] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): link_fixtures maps shells/teams to api ids"
```

---

### Task 4: `sync_scores()` — auto-apply finals

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def _seed_linked_group_match(app, status_winner, home, away, draw=False):
    """Seed a linked group match and return (match_id, api payload)."""
    with app.app_context():
        a = _team('MEX', 'Mexico', 'A'); b = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=537001,
                          kickoff_utc=datetime(2026, 6, 11, 19, 0, 0))
        db.session.add(m); db.session.commit()
        payload = {'matches': [{
            'id': 537001, 'status': 'FINISHED', 'stage': 'GROUP_STAGE',
            'homeTeam': {'tla': 'MEX'}, 'awayTeam': {'tla': 'RSA'},
            'score': {'winner': status_winner, 'duration': 'REGULAR',
                      'fullTime': {'home': home, 'away': away}},
        }]}
        return m.id, payload


def test_sync_scores_applies_group_win(app):
    from games.worldcup.services import sync
    mid, payload = _seed_linked_group_match(app, 'HOME_TEAM', 2, 0)
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert m.is_completed and m.home_score == 2 and m.away_score == 0
        assert m.winner_team_id == m.home_team_id
        assert report['applied_count'] == 1


def test_sync_scores_skips_unfinished_and_completed(app):
    from games.worldcup.services import sync
    mid, payload = _seed_linked_group_match(app, 'HOME_TEAM', 2, 0)
    with app.app_context():
        payload['matches'][0]['status'] = 'IN_PLAY'
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert report['applied_count'] == 0
        assert db.session.get(WorldCupMatch, mid).is_completed is False


def test_sync_scores_knockout_extra_time_penalties(app):
    from games.worldcup.services import sync
    with app.app_context():
        a = _team('ESP', 'Spain', 'B'); b = _team('BRA', 'Brazil', 'C')
        db.session.flush()
        m = WorldCupMatch(match_number=90, stage='R16',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=537090,
                          kickoff_utc=datetime(2026, 7, 4, 19, 0, 0))
        db.session.add(m); db.session.commit()
        mid = m.id
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'PENALTY_SHOOTOUT',
                      'fullTime': {'home': 1, 'away': 1},
                      'penalties': {'home': 3, 'away': 4}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert m.is_completed and m.winner_team_id == b.id
        assert m.extra_time is True and m.penalties is True


def test_sync_scores_skips_knockout_with_unset_teams(app):
    from games.worldcup.services import sync
    with app.app_context():
        m = WorldCupMatch(match_number=90, stage='R16', api_fixture_id=537090,
                          kickoff_utc=datetime(2026, 7, 4, 19, 0, 0))
        db.session.add(m); db.session.commit()
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'REGULAR',
                      'fullTime': {'home': 0, 'away': 1}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert report['applied_count'] == 0
        assert report['skipped_unassigned'] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k sync_scores -q`
Expected: FAIL — `AttributeError: 'sync_scores'`.

- [ ] **Step 3: Implement `sync_scores`**

Append to `games/worldcup/services/sync.py`:

```python
def sync_scores() -> dict:
    """Apply every newly-FINISHED fixture to its linked shell. Idempotent.

    Low-risk tier: runs automatically. Group draws/wins and knockout
    ET/penalties flow through the existing process_match_result(), which
    recalculates all scores. Already-completed shells are skipped.
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    by_fixture = {
        m.api_fixture_id: m
        for m in WorldCupMatch.query.filter(WorldCupMatch.api_fixture_id.isnot(None)).all()
    }

    applied = []
    skipped_unassigned = 0
    for f in data.get('matches', []):
        if f.get('status') not in FINISHED_STATUSES:
            continue
        shell = by_fixture.get(f.get('id'))
        if not shell or shell.is_completed:
            continue

        ft = (f.get('score') or {}).get('fullTime') or {}
        home, away = ft.get('home'), ft.get('away')
        if home is None or away is None:
            continue

        if shell.stage == 'group':
            is_draw = (f['score'].get('winner') == 'DRAW')
            res = process_match_result(shell.id, home, away, None, is_draw=is_draw)
        else:
            # Knockout requires assigned teams (bracket confirmed by admin first).
            if not shell.home_team_id or not shell.away_team_id:
                skipped_unassigned += 1
                continue
            duration = f['score'].get('duration', 'REGULAR')
            winner_side = f['score'].get('winner')
            api_winner = f.get('homeTeam') if winner_side == 'HOME_TEAM' else f.get('awayTeam')
            winner_fifa = _fifa_for_tla((api_winner or {}).get('tla'))
            res = process_match_result(
                shell.id, home, away, winner_fifa,
                extra_time=duration in ('EXTRA_TIME', 'PENALTY_SHOOTOUT'),
                penalties=duration == 'PENALTY_SHOOTOUT',
            )
        if 'error' not in res:
            applied.append({'match_number': shell.match_number, 'result': res.get('result')})

    return {
        'applied_count': len(applied),
        'applied': applied,
        'skipped_unassigned': skipped_unassigned,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k sync_scores -q`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): sync_scores auto-applies finals"
```

---

### Task 5: `fetch_advancement_proposal()` — read-only proposal

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
_STANDINGS_FIXTURE = {'standings': [{
    'stage': 'GROUP_STAGE', 'type': 'TOTAL', 'group': 'Group A',
    'table': [
        {'position': 1, 'team': {'tla': 'MEX', 'name': 'Mexico'}, 'points': 9,
         'goalDifference': 5, 'goalsFor': 6, 'playedGames': 3},
        {'position': 2, 'team': {'tla': 'RSA', 'name': 'South Africa'}, 'points': 4,
         'goalDifference': 0, 'goalsFor': 3, 'playedGames': 3},
        {'position': 3, 'team': {'tla': 'KOR', 'name': 'South Korea'}, 'points': 3,
         'goalDifference': -1, 'goalsFor': 2, 'playedGames': 3},
        {'position': 4, 'team': {'tla': 'CZE', 'name': 'Czechia'}, 'points': 1,
         'goalDifference': -4, 'goalsFor': 1, 'playedGames': 3},
    ],
}]}

_KO_MATCHES_FIXTURE = {'matches': [{
    'id': 537073, 'utcDate': '2026-06-28T19:00:00Z', 'status': 'TIMED',
    'stage': 'LAST_32', 'group': None,
    'homeTeam': {'tla': 'MEX', 'name': 'Mexico'},
    'awayTeam': {'tla': 'KOR', 'name': 'South Korea'},
    'score': {'winner': None, 'duration': 'REGULAR', 'fullTime': {'home': None, 'away': None}},
}]}


def test_fetch_advancement_proposal(app):
    from games.worldcup.services import sync
    with app.app_context():
        def fake_get(path, params=None):
            return _STANDINGS_FIXTURE if 'standings' in path else _KO_MATCHES_FIXTURE
        with patch.object(sync, '_api_get', side_effect=fake_get):
            proposal = sync.fetch_advancement_proposal()
        groups = {g['letter']: g for g in proposal['groups']}
        assert groups['A']['group_winner'] == 'MEX'
        assert groups['A']['runner_up'] == 'RSA'
        # KOR appears in resolved LAST_32 -> flagged as the advancing best third.
        assert groups['A']['best_third'] == 'KOR'
        # CZE did not advance.
        assert groups['A']['third_advances'] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k advancement_proposal -q`
Expected: FAIL — `AttributeError: 'fetch_advancement_proposal'`.

- [ ] **Step 3: Implement `fetch_advancement_proposal`**

Append to `games/worldcup/services/sync.py`:

```python
def fetch_advancement_proposal() -> dict:
    """Read-only proposal for the admin advancement/bracket forms (no DB writes).

    Reads group standings (positions 1/2 -> winner/runner-up) and the resolved
    LAST_32 matchups (to flag which 3rd-place teams actually advanced as best
    thirds, and to pre-fill knockout shell team assignments). The admin reviews
    and confirms; we do not write any scoring state here.
    """
    standings = _api_get(f'competitions/{COMPETITION_CODE}/standings').get('standings', [])
    matches = _api_get(f'competitions/{COMPETITION_CODE}/matches').get('matches', [])

    # tlas appearing in resolved LAST_32 = teams that advanced (incl. best thirds).
    advancing_tlas = set()
    ko_pairings = []
    for m in matches:
        if STAGE_MAP.get(m.get('stage')) != 'R32':
            continue
        home, away = (m.get('homeTeam') or {}), (m.get('awayTeam') or {})
        if home.get('tla'):
            advancing_tlas.add(home['tla'])
        if away.get('tla'):
            advancing_tlas.add(away['tla'])
        if home.get('tla') and away.get('tla'):
            ko_pairings.append({
                'api_fixture_id': m['id'],
                'home_fifa': _fifa_for_tla(home['tla']),
                'away_fifa': _fifa_for_tla(away['tla']),
            })

    groups = []
    for g in standings:
        if g.get('type') != 'TOTAL':
            continue
        letter = g.get('group', '').replace('Group', '').strip()
        rows = sorted(g.get('table', []), key=lambda r: r['position'])
        def fifa(i):
            return _fifa_for_tla(rows[i]['team']['tla']) if len(rows) > i else None
        third_tla = rows[2]['team']['tla'] if len(rows) > 2 else None
        third_advances = bool(third_tla and third_tla in advancing_tlas)
        groups.append({
            'letter': letter,
            'group_winner': fifa(0),
            'runner_up': fifa(1),
            'best_third': fifa(2) if third_advances else None,
            'third_advances': third_advances,
            'table': [
                {'position': r['position'], 'fifa': _fifa_for_tla(r['team']['tla']),
                 'name': r['team'].get('name'), 'points': r.get('points'),
                 'gd': r.get('goalDifference'), 'gf': r.get('goalsFor')}
                for r in rows
            ],
        })

    return {'groups': sorted(groups, key=lambda x: x['letter']), 'ko_pairings': ko_pairings}
```

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k advancement_proposal -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): fetch_advancement_proposal (read-only)"
```

---

### Task 6: Detection helpers + admin notifications

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def test_group_stage_detection(app):
    from games.worldcup.services import sync
    with app.app_context():
        a = _team('MEX', 'Mexico', 'A'); b = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        # One completed group match, no advancement set yet.
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     home_team_id=a.id, away_team_id=b.id,
                                     is_completed=True))
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is True
        # Confirm advancement -> no longer flagged.
        a.advancement_method = 'group_winner'
        b.advancement_method = 'runner_up'
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is False


def test_group_stage_detection_false_when_incomplete(app):
    from games.worldcup.services import sync
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=False))
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is False


def test_send_admin_email_uses_platform_helper(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        with patch.object(sync, 'send_platform_email', return_value=True) as send:
            sync._send_admin_email('Subject', 'Body')
        assert send.call_args.args[0] == 'commish@test.com'
        assert '[World Cup]' in send.call_args.args[1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "detection or admin_email" -q`
Expected: FAIL — attributes missing.

- [ ] **Step 3: Implement detection + email**

Add the import at the top of `games/worldcup/services/sync.py` (with the other imports):

```python
from utils.email import send_platform_email
```

Append to `games/worldcup/services/sync.py`:

```python
def group_stage_complete_and_unconfirmed() -> bool:
    """True when all group matches are done but ≥1 group's advancement is unset."""
    total = WorldCupMatch.query.filter_by(stage='group').count()
    done = WorldCupMatch.query.filter_by(stage='group', is_completed=True).count()
    if total == 0 or done < total:
        return False
    unconfirmed = (
        WorldCupTeam.query
        .filter(WorldCupTeam.advancement_method.is_(None))
        .filter(WorldCupTeam.is_eliminated.isnot(True))
        .count()
    )
    return unconfirmed > 0


def ko_round_complete_and_next_empty() -> bool:
    """True when a knockout round is fully played but the next round's shells are empty."""
    order = ['R32', 'R16', 'QF', 'SF']
    nxt = {'R32': 'R16', 'R16': 'QF', 'QF': 'SF', 'SF': 'final'}
    for stage in order:
        total = WorldCupMatch.query.filter_by(stage=stage).count()
        if total == 0:
            continue
        done = WorldCupMatch.query.filter_by(stage=stage, is_completed=True).count()
        if done < total:
            continue
        next_stage = nxt[stage]
        empty = (
            WorldCupMatch.query
            .filter_by(stage=next_stage)
            .filter((WorldCupMatch.home_team_id.is_(None)) | (WorldCupMatch.away_team_id.is_(None)))
            .count()
        )
        if empty > 0:
            return True
    return False


def _send_admin_email(subject: str, body: str) -> bool:
    """Send a plain-text admin notification to the platform email address."""
    to_addr = current_app.config.get('EMAIL_ADDRESS', '')
    if not to_addr:
        logger.warning('EMAIL_ADDRESS not configured; skipping admin email.')
        return False
    return send_platform_email(to_addr, f'[World Cup] {subject}', body)
```

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "detection or admin_email" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): advancement detection + admin email helper"
```

---

### Task 7: Orchestrators — `run_scores`, `run_advancement_check`, `run_digest`

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

These wrap the primitives with notifications + a schema-free per-episode notify guard (a marker file in the instance dir, so repeated 30-min runs don't spam).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def test_run_scores_emails_on_error(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        with patch.object(sync, 'sync_scores', side_effect=sync.SyncError('down')), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            out = sync.run_scores()
        assert out['status'] == 'error'
        assert send.called


def test_run_advancement_check_notifies_once_per_episode(app, tmp_path):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        app.instance_path = str(tmp_path)
        with patch.object(sync, 'group_stage_complete_and_unconfirmed', return_value=True), \
             patch.object(sync, 'ko_round_complete_and_next_empty', return_value=False), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            sync.run_advancement_check()   # fires
            sync.run_advancement_check()   # same episode -> suppressed
        assert send.call_count == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "run_scores or advancement_check" -q`
Expected: FAIL — attributes missing.

- [ ] **Step 3: Implement orchestrators**

Append to `games/worldcup/services/sync.py`:

```python
import os


def _notify_once(signature: str) -> bool:
    """Return True the first time we see `signature`; suppress repeats.

    Schema-free de-dup via a marker file in the instance dir. A new pending-state
    signature (e.g. group stage done, then a KO round done) re-arms the notice.
    """
    marker = os.path.join(current_app.instance_path, '.wc_sync_notify')
    try:
        with open(marker) as fh:
            last = fh.read().strip()
    except OSError:
        last = ''
    if last == signature:
        return False
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(marker, 'w') as fh:
        fh.write(signature)
    return True


def run_scores() -> dict:
    """Timer entry point (every 30 min): apply finals; email only on error."""
    try:
        result = sync_scores()
    except SyncError as exc:
        _send_admin_email('Score sync failed', f'football-data.org sync error:\n{exc}')
        return {'status': 'error', 'details': str(exc)}
    if result['applied_count']:
        logger.info('worldcup sync applied %s result(s)', result['applied_count'])
    return {'status': 'ok', **result}


def run_advancement_check() -> dict:
    """Timer entry point (hourly): notify (once per episode) when admin action is due."""
    group_due = group_stage_complete_and_unconfirmed()
    ko_due = ko_round_complete_and_next_empty()
    if not (group_due or ko_due):
        return {'status': 'idle'}
    signature = f'group={group_due};ko={ko_due}'
    if not _notify_once(signature):
        return {'status': 'already_notified'}
    lines = []
    if group_due:
        lines.append('Group stage is complete — confirm advancement at '
                     '/worldcup/admin/advancement (use "Load from API").')
    if ko_due:
        lines.append('A knockout round is complete — set the next round\'s teams at '
                     'the admin bracket pages (use "Load from API").')
    _send_admin_email('Advancement ready to confirm', '\n'.join(lines))
    return {'status': 'notified', 'group_due': group_due, 'ko_due': ko_due}


def run_digest() -> dict:
    """Daily entry point: email a summary of matches finalized today (CT)."""
    from datetime import timezone
    from games.worldcup.services.state import now_utc
    from games.worldcup.constants import WORLDCUP_TZ
    today = now_utc().astimezone(WORLDCUP_TZ).date()

    completed = WorldCupMatch.query.filter_by(is_completed=True).all()
    todays = [
        m for m in completed
        if m.updated_at and m.updated_at.replace(tzinfo=timezone.utc).astimezone(WORLDCUP_TZ).date() == today
    ]
    if not todays:
        return {'status': 'no_results'}
    lines = [f"Results finalized {today:%b %d}:"]
    for m in sorted(todays, key=lambda x: x.match_number):
        hn = m.home_team.display_name if m.home_team else '?'
        an = m.away_team.display_name if m.away_team else '?'
        lines.append(f'  #{m.match_number} [{m.stage}] {hn} {m.home_score}-{m.away_score} {an}')
    _send_admin_email('Daily results digest', '\n'.join(lines))
    return {'status': 'sent', 'count': len(todays)}
```

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "run_scores or advancement_check" -q`
Expected: PASS.

- [ ] **Step 5: Run the whole sync suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -q`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): sync orchestrators with notifications"
```

---

### Task 8: CLI — `flask worldcup sync --mode ...`

**Files:**
- Modify: `games/worldcup/cli.py`
- Test: `tests/test_worldcup_sync.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def test_cli_sync_link_invokes_service(app):
    from games.worldcup.services import sync
    runner = app.test_cli_runner()
    with patch.object(sync, 'link_fixtures',
                      return_value={'fixtures_linked': 104, 'teams_linked': 48,
                                    'unmatched_fixtures': [], 'unmapped_teams': [],
                                    'api_fixture_count': 104}) as link:
        result = runner.invoke(args=['worldcup', 'sync', '--mode', 'link'])
    assert link.called
    assert '104' in result.output


def test_cli_sync_rejects_bad_mode(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['worldcup', 'sync', '--mode', 'bogus'])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k cli_sync -q`
Expected: FAIL — no `sync` command.

- [ ] **Step 3: Add the CLI command**

In `games/worldcup/cli.py`, add after the imports:

```python
SYNC_MODES = ('link', 'scores', 'advancement', 'digest', 'status')
```

And add this command (before `register_worldcup_cli`):

```python
@worldcup_cli.command('sync')
@click.option('--mode', required=True, type=click.Choice(SYNC_MODES),
              help='Sync mode to run.')
def sync_cmd(mode):
    """football-data.org automation — run by mode (see deploy/ timers)."""
    from games.worldcup.services import sync as wc_sync

    if mode == 'link':
        report = wc_sync.link_fixtures()
        click.echo(f"Fixtures linked: {report['fixtures_linked']} "
                   f"(API has {report['api_fixture_count']})")
        click.echo(f"Teams linked:    {report['teams_linked']}")
        if report['unmatched_fixtures']:
            click.echo(f"\n! UNMATCHED FIXTURES ({len(report['unmatched_fixtures'])}) — review:")
            for u in report['unmatched_fixtures']:
                click.echo(f"   {u}")
        if report['unmapped_teams']:
            click.echo(f"\n! UNMAPPED TEAMS ({len(report['unmapped_teams'])}) — add to TEAM_TLA_OVERRIDES:")
            for u in report['unmapped_teams']:
                click.echo(f"   {u}")
    elif mode == 'scores':
        result = wc_sync.run_scores()
        click.echo(f"[scores] {result.get('status')}: applied "
                   f"{result.get('applied_count', 0)}, "
                   f"skipped-unassigned {result.get('skipped_unassigned', 0)}")
    elif mode == 'advancement':
        result = wc_sync.run_advancement_check()
        click.echo(f"[advancement] {result.get('status')}")
    elif mode == 'digest':
        result = wc_sync.run_digest()
        click.echo(f"[digest] {result.get('status')} ({result.get('count', 0)} results)")
    elif mode == 'status':
        linked = WorldCupMatch.query.filter(WorldCupMatch.api_fixture_id.isnot(None)).count()
        total = WorldCupMatch.query.count()
        completed = WorldCupMatch.query.filter_by(is_completed=True).count()
        click.echo(f"Linked fixtures: {linked}/{total}")
        click.echo(f"Completed:       {completed}/{total}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k cli_sync -q`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/cli.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): flask worldcup sync CLI"
```

---

### Task 9: Admin pre-fill — JSON proposal endpoint + form wiring

**Files:**
- Modify: `games/worldcup/routes.py`
- Modify: `games/worldcup/templates/worldcup/admin/advancement.html`
- Test: `tests/test_worldcup_admin_sync.py` (new)

The testable substance is a JSON endpoint returning the proposal; the template gets a "Load from API" button + a small fetch script that fills the existing form fields. No new write path — submitting still calls the existing `apply_group_advancement()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_worldcup_admin_sync.py`:

```python
"""Admin 'Load from API' proposal endpoint."""
import pytest
from unittest.mock import patch

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupTeam


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_admin(app):
    with app.app_context():
        u = User(username='boss', email='boss@test.com', is_admin=True)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.auth_id


def test_advancement_proposal_endpoint_requires_admin(client):
    resp = client.get('/worldcup/admin/advancement/proposal')
    assert resp.status_code in (302, 401, 403)


def test_advancement_proposal_endpoint_returns_json(client, app):
    auth_id = _make_admin(app)
    fake = {'groups': [{'letter': 'A', 'group_winner': 'MEX',
                        'runner_up': 'RSA', 'best_third': 'KOR',
                        'third_advances': True, 'table': []}],
            'ko_pairings': []}
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.fetch_advancement_proposal', return_value=fake):
        resp = client.get('/worldcup/admin/advancement/proposal')
    assert resp.status_code == 200
    assert resp.get_json()['groups'][0]['group_winner'] == 'MEX'
```

- [ ] **Step 2: Run to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_admin_sync.py -q`
Expected: FAIL — endpoint 404.

- [ ] **Step 3: Add the import + route**

In `games/worldcup/routes.py`, extend the scoring-service import block (the one importing `process_match_result, apply_group_advancement, set_knockout_teams` near line 28) is in `services.scoring`; add a separate import for the sync helper near the other service imports:

```python
from games.worldcup.services.sync import fetch_advancement_proposal
```

Add the route next to `admin_advancement` (after line ~1095):

```python
@worldcup_bp.route('/admin/advancement/proposal')
@worldcup_admin_required
def admin_advancement_proposal():
    """Return the football-data.org advancement/bracket proposal as JSON.

    Read-only. Powers the 'Load from API' pre-fill on the advancement +
    set-knockout admin pages. Confirming still goes through the existing
    apply_group_advancement() / set_knockout_teams() write paths.
    """
    from games.worldcup.services.sync import SyncError
    try:
        return jsonify(fetch_advancement_proposal())
    except SyncError as exc:
        return jsonify({'error': str(exc)}), 502
```

> Confirm `jsonify` is imported in `routes.py` (it is used elsewhere; if not, add it to the `from flask import ...` line).

- [ ] **Step 4: Run to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_admin_sync.py -q`
Expected: PASS.

- [ ] **Step 5: Wire the button into the template**

In `games/worldcup/templates/worldcup/admin/advancement.html`, add a "Load from API" control and a script that fetches the endpoint and fills each group's `group_winner` / `runner_up` / `best_third` selects by FIFA code. Insert near the top of the groups section:

```html
<button type="button" class="btn btn-game" id="wc-load-api"
        data-proposal-url="{{ url_for('worldcup.admin_advancement_proposal') }}">
  Load from API
</button>
<p class="wc-eyebrow">Loaded from football-data.org — review the standings before confirming.</p>

<script>
document.getElementById('wc-load-api')?.addEventListener('click', async (e) => {
  const url = e.target.dataset.proposalUrl;
  const resp = await fetch(url, {headers: {'X-Requested-With': 'fetch'}});
  if (!resp.ok) { alert('Could not load proposal from API.'); return; }
  const data = await resp.json();
  for (const g of data.groups) {
    const form = document.querySelector(`form[data-group="${g.letter}"]`);
    if (!form) continue;
    const set = (name, val) => {
      const el = form.querySelector(`[name="${name}"]`);
      if (el && val) el.value = val;
    };
    set('group_winner', g.group_winner);
    set('runner_up', g.runner_up);
    set('best_third', g.best_third);
  }
});
</script>
```

> The executor must verify each group's `<form>` carries `data-group="{{ letter }}"` and that the selects' `value`s are FIFA codes; add `data-group` to the form tag and `value="{{ team.fifa_code }}"` to the option tags if missing (these are the JS-critical hooks — add classes/attributes, never remove existing ones, per CLAUDE.md).

- [ ] **Step 6: Manual smoke + commit**

Smoke (local Postgres, group stage simulated): `flask worldcup simulate-group-stage -y` then load `/worldcup/admin/advancement`, click "Load from API" (mock or live), confirm selects populate.

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/admin/advancement.html tests/test_worldcup_admin_sync.py
git commit -m "feat(worldcup): admin Load-from-API advancement pre-fill"
```

---

### Task 10: systemd timer deploy artifacts + runbook

**Files:**
- Create: `deploy/worldcup-sync.service`, `deploy/worldcup-sync.timer`
- Create: `deploy/worldcup-advancement.service`, `deploy/worldcup-advancement.timer`
- Create: `deploy/worldcup-digest.service`, `deploy/worldcup-digest.timer`
- Modify: `docs/production-launch-test-script.md` (append a sync runbook section)

No automated test (deploy artifacts). The verification is the pre-tournament checklist.

- [ ] **Step 1: Create the scores unit + timer**

`deploy/worldcup-sync.service`:

```ini
[Unit]
Description=World Cup results sync (apply finals)
After=network-online.target

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/home/deploy/fantasy-platform
Environment=ENVIRONMENT=production
Environment=FLASK_APP=app.py
ExecStart=/home/deploy/fantasy-platform/venv/bin/flask worldcup sync --mode scores
```

`deploy/worldcup-sync.timer`:

```ini
[Unit]
Description=Run World Cup score sync every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Create the advancement-check unit + timer**

`deploy/worldcup-advancement.service` (same as above but `--mode advancement` and `Description=World Cup advancement check`).

`deploy/worldcup-advancement.timer`:

```ini
[Unit]
Description=Run World Cup advancement check hourly

[Timer]
OnCalendar=*:05
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Create the daily digest unit + timer**

`deploy/worldcup-digest.service` (same shape, `--mode digest`, `Description=World Cup daily digest`).

`deploy/worldcup-digest.timer`:

```ini
[Unit]
Description=Send World Cup daily results digest

[Timer]
OnCalendar=*-*-* 22:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Append the runbook**

Add a "World Cup Sync Automation" section to `docs/production-launch-test-script.md` with the exact, no-assumed-knowledge install commands:

```bash
# On the droplet, as a sudo user:
sudo cp /home/deploy/fantasy-platform/deploy/worldcup-*.service /etc/systemd/system/
sudo cp /home/deploy/fantasy-platform/deploy/worldcup-*.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now worldcup-sync.timer worldcup-advancement.timer worldcup-digest.timer

# Verify:
systemctl list-timers 'worldcup-*'
journalctl -u worldcup-sync --since today
```

Document the **pre-tournament checklist** (from the spec §9): add `FOOTBALL_DATA_API_KEY` to server `.env`; `flask db upgrade`; `flask worldcup sync --mode link` and eyeball the report (expect 104 fixtures, 48 teams, zero unmatched — add any `tla` mismatch to `TEAM_TLA_OVERRIDES` and re-run); enable timers; `flask worldcup sync --mode status`. And the **score-correction** note: to fix a result already applied, edit the match in admin and run `flask worldcup recalc`.

- [ ] **Step 5: Commit**

```bash
git add deploy/worldcup-*.service deploy/worldcup-*.timer docs/production-launch-test-script.md
git commit -m "feat(worldcup): systemd sync timers + runbook"
```

---

### Task 11: Full-suite verification

- [ ] **Step 1: Run the entire suite**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
Expected: all green (~987 prior + new sync/admin-sync tests).

- [ ] **Step 2: Confirm no scoring regressions**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py tests/test_worldcup_elimination.py -q`
Expected: PASS — the scoring engine is untouched; this confirms the new feed path didn't disturb it.

- [ ] **Step 3: Final commit (if any cleanup)**

```bash
git add -A
git commit -m "test(worldcup): full-suite green with sync automation"
```

---

## Out of scope (do not build)

- Player-facing recap/standings emails (deferred future enhancement).
- Live/in-progress score ticker or any new live UI.
- Automating the high-risk advancement writes (stays human-confirmed by design).
- CFB/Golf sync changes.

## Notes for the implementer

- **Mock at `_api_get`**, not `requests`, for service tests — cleaner and avoids HTTP wiring.
- **Orientation assumption (knockout):** `sync_scores` resolves the winner by `tla` (orientation-independent) but assigns `home_score`/`away_score` as the API reports them. Because the admin confirms the bracket *from the API proposal* (same orientation), our shell's home/away matches the API — keep that invariant when wiring the set-knockout pre-fill.
- **`kickoff_utc` matching:** KO shells are matched by `(stage, kickoff minute-precision UTC)`. If `link --mode` reports KO fixtures unmatched, compare our `match_schedule.py` kickoff times to the API `utcDate`s and reconcile before the tournament — this is the one mapping that can't fall back to team identity (KO teams are TBD).
- **TDD discipline:** every task is test-first. Do not batch-write implementation ahead of its test.
```
