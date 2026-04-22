# World Cup Stats Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6-tab Stats Hub analytics page to the World Cup game, accessible publicly, showing selection statistics, country scoring, tier performance, portfolio impact, and pick combo data.

**Architecture:** New `services/stats.py` module provides 4 query/computation functions; the `/stats` route renders all data server-side into Jinja2 → JS variables; Chart.js initializes lazily per tab to avoid zero-size canvas issues.

**Tech Stack:** Flask, SQLAlchemy 2.0, Jinja2, Chart.js 4.4.3, vanilla JS, existing `WorldCupTeam` / `WorldCupPick` / `WorldCupEnrollment` models.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `games/worldcup/services/stats.py` | **Create** | 4 data functions: `get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos` |
| `tests/test_worldcup_stats.py` | **Create** | Unit + route tests for all stats functions |
| `games/worldcup/routes.py` | **Modify** | Add `from games.worldcup.services.stats import ...` + `/stats` route |
| `games/worldcup/templates/worldcup/stats.html` | **Create** | Full 6-tab page: dark mode detection, Jinja2→JS bridge, tab switching, Chart.js lazy init |
| `static/css/style.css` | **Modify** | Tab bar, panel, pick-bar, and stats component CSS under `/* === WORLD CUP FANTASY POOL === */` |
| `templates/base.html` | **Modify** | Stats Hub subnav pill in the `{% if request.blueprint == 'worldcup' %}` block |

---

## Task 1: Service — `get_country_stats`

**Files:**
- Create: `games/worldcup/services/stats.py`
- Create: `tests/test_worldcup_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worldcup_stats.py
import pytest
from app import create_app
from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield db.session


def _make_user(session, username):
    u = User(username=username, email=f'{username}@test.com', password_hash='x')
    session.add(u)
    session.flush()
    return u


def _make_team(session, fifa_code, name, tier, multiplier, group='A'):
    t = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier, confederation='TEST', group_letter=group,
    )
    session.add(t)
    session.flush()
    return t


def _make_enrollment(session, user_id, season_year=2026):
    e = WorldCupEnrollment(user_id=user_id, season_year=season_year, picks_submitted=True)
    session.add(e)
    session.flush()
    return e


def _make_pick(session, enrollment_id, team_id, tier):
    p = WorldCupPick(enrollment_id=enrollment_id, team_id=team_id, tier=tier)
    session.add(p)
    session.flush()
    return p


def test_get_country_stats_basic(session):
    from games.worldcup.services.stats import get_country_stats

    u1 = _make_user(session, 'alice')
    u2 = _make_user(session, 'bob')
    team_a = _make_team(session, 'USA', 'USA', tier=3, multiplier=2.5)
    team_b = _make_team(session, 'MEX', 'Mexico', tier=3, multiplier=2.5)
    e1 = _make_enrollment(session, u1.id)
    e2 = _make_enrollment(session, u2.id)
    _make_pick(session, e1.id, team_a.id, tier=3)
    _make_pick(session, e2.id, team_a.id, tier=3)
    _make_pick(session, e1.id, team_b.id, tier=3)
    session.commit()

    stats, total_players = get_country_stats(2026)

    assert total_players == 2
    by_name = {c['name']: c for c in stats}
    assert by_name['USA']['pick_count'] == 2
    assert abs(by_name['USA']['pick_pct'] - 100.0) < 0.01
    assert by_name['Mexico']['pick_count'] == 1
    assert abs(by_name['Mexico']['pick_pct'] - 50.0) < 0.01


def test_get_country_stats_zero_picks(session):
    from games.worldcup.services.stats import get_country_stats

    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    stats, total_players = get_country_stats(2026)

    assert total_players == 0
    assert stats[0]['pick_count'] == 0
    assert stats[0]['pick_pct'] == 0.0


def test_get_country_stats_dict_shape(session):
    from games.worldcup.services.stats import get_country_stats

    _make_team(session, 'ENG', 'England', tier=1, multiplier=1.0)
    session.commit()

    stats, _ = get_country_stats(2026)
    c = stats[0]

    assert 'name' in c
    assert 'flag_emoji' in c
    assert 'tier' in c
    assert 'multiplier' in c
    assert 'pick_count' in c
    assert 'pick_pct' in c
    assert 'group_score' in c
    assert 'ko_score' in c
    assert 'total_score' in c
    assert 'is_active' in c
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/bhagstrom/fantasy-platform
venv/bin/python -m pytest tests/test_worldcup_stats.py -v 2>&1 | head -30
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `games.worldcup.services.stats`.

- [ ] **Step 3: Create `games/worldcup/services/stats.py` with `get_country_stats`**

```python
# games/worldcup/services/stats.py
from sqlalchemy import func

from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick
from games.worldcup.services.scoring import compute_team_score_events

_GROUP_SOURCES = {'group_win', 'group_draw', 'advancement'}
_KO_SOURCES = {'knockout', 'podium'}


def get_country_stats(season_year: int) -> tuple[list[dict], int]:
    """Return (country_list, total_players) for the given season.

    Every WorldCupTeam row is included, even if pick_count is 0.
    """
    total_players: int = WorldCupEnrollment.query.filter_by(
        season_year=season_year
    ).count()

    pick_counts: dict[int, int] = dict(
        db.session.query(WorldCupPick.team_id, func.count(WorldCupPick.id))
        .join(WorldCupEnrollment, WorldCupPick.enrollment_id == WorldCupEnrollment.id)
        .filter(WorldCupEnrollment.season_year == season_year)
        .group_by(WorldCupPick.team_id)
        .all()
    )

    result = []
    for team in WorldCupTeam.query.all():
        events = compute_team_score_events(team)
        group_base = sum(e.base_points for e in events if e.source in _GROUP_SOURCES)
        ko_base = sum(e.base_points for e in events if e.source in _KO_SOURCES)

        pick_count = pick_counts.get(team.id, 0)
        pick_pct = (pick_count / total_players * 100) if total_players > 0 else 0.0

        result.append({
            'name': team.display_name,
            'flag_emoji': team.flag_emoji,
            'tier': team.tier,
            'multiplier': team.multiplier,
            'pick_count': pick_count,
            'pick_pct': pick_pct,
            'group_score': group_base * team.multiplier,
            'ko_score': ko_base * team.multiplier,
            'total_score': team.multiplied_points,
            'is_active': not team.is_eliminated,
        })

    return result, total_players
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_get_country_stats_basic tests/test_worldcup_stats.py::test_get_country_stats_zero_picks tests/test_worldcup_stats.py::test_get_country_stats_dict_shape -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/stats.py tests/test_worldcup_stats.py
git commit -m "feat(worldcup): add stats service get_country_stats"
```

---

## Task 2: Service — `get_tier_stats` and `get_overview_kpis`

**Files:**
- Modify: `tests/test_worldcup_stats.py` (add tests)
- Modify: `games/worldcup/services/stats.py` (add functions)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_worldcup_stats.py`:

```python
def test_get_tier_stats(session):
    from games.worldcup.services.stats import get_tier_stats

    country_stats = [
        {'tier': 1, 'total_score': 10.0, 'group_score': 5.0, 'ko_score': 5.0,
         'name': 'Spain', 'pick_count': 2, 'pick_pct': 50.0, 'multiplier': 1.0,
         'flag_emoji': '🇪🇸', 'is_active': True},
        {'tier': 1, 'total_score': 20.0, 'group_score': 10.0, 'ko_score': 10.0,
         'name': 'France', 'pick_count': 1, 'pick_pct': 25.0, 'multiplier': 1.0,
         'flag_emoji': '🇫🇷', 'is_active': False},
        {'tier': 3, 'total_score': 30.0, 'group_score': 15.0, 'ko_score': 15.0,
         'name': 'USA', 'pick_count': 3, 'pick_pct': 75.0, 'multiplier': 2.5,
         'flag_emoji': '🇺🇸', 'is_active': True},
    ]

    tier_stats = get_tier_stats(country_stats)

    assert tier_stats[1]['avg_score'] == 15.0
    assert tier_stats[1]['total_score'] == 30.0
    assert tier_stats[1]['best_country'] == 'France'
    assert tier_stats[1]['best_score'] == 20.0
    assert tier_stats[3]['avg_score'] == 30.0
    assert tier_stats[3]['best_country'] == 'USA'


def test_get_overview_kpis(session):
    from games.worldcup.services.stats import get_overview_kpis

    country_stats = [
        {'tier': 1, 'total_score': 10.0, 'group_score': 5.0, 'ko_score': 5.0,
         'name': 'Spain', 'pick_count': 2, 'pick_pct': 50.0, 'multiplier': 1.0,
         'flag_emoji': '🇪🇸', 'is_active': False},
        {'tier': 3, 'total_score': 50.0, 'group_score': 20.0, 'ko_score': 30.0,
         'name': 'USA', 'pick_count': 3, 'pick_pct': 75.0, 'multiplier': 2.5,
         'flag_emoji': '🇺🇸', 'is_active': True},
    ]

    kpis = get_overview_kpis(country_stats, total_players=4)

    assert kpis['total_players'] == 4
    assert kpis['active_countries'] == 1
    assert kpis['top_country_score'] == 50.0
    assert kpis['top_country_name'] == 'USA'
    assert kpis['total_pts_awarded'] == 60.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_get_tier_stats tests/test_worldcup_stats.py::test_get_overview_kpis -v 2>&1 | head -20
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add `get_tier_stats` and `get_overview_kpis` to `games/worldcup/services/stats.py`**

Append to `stats.py` (after `get_country_stats`):

```python
def get_tier_stats(country_stats: list[dict]) -> dict[int, dict]:
    """Pure Python — no DB calls. Groups country_stats by tier."""
    tiers: dict[int, list[dict]] = {}
    for c in country_stats:
        tiers.setdefault(c['tier'], []).append(c)

    result: dict[int, dict] = {}
    for tier, countries in tiers.items():
        scores = [c['total_score'] for c in countries]
        best = max(countries, key=lambda c: c['total_score'])
        result[tier] = {
            'avg_score': sum(scores) / len(scores),
            'total_score': sum(scores),
            'best_country': best['name'],
            'best_score': best['total_score'],
        }
    return result


def get_overview_kpis(country_stats: list[dict], total_players: int) -> dict:
    """No DB calls — derived from country_stats and total_players."""
    if not country_stats:
        return {
            'total_players': total_players,
            'active_countries': 0,
            'top_country_score': 0.0,
            'top_country_name': '',
            'total_pts_awarded': 0.0,
        }
    top = max(country_stats, key=lambda c: c['total_score'])
    return {
        'total_players': total_players,
        'active_countries': sum(1 for c in country_stats if c['is_active']),
        'top_country_score': top['total_score'],
        'top_country_name': top['name'],
        'total_pts_awarded': sum(c['total_score'] for c in country_stats),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_get_tier_stats tests/test_worldcup_stats.py::test_get_overview_kpis -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/stats.py tests/test_worldcup_stats.py
git commit -m "feat(worldcup): add get_tier_stats and get_overview_kpis"
```

---

## Task 3: Service — `get_tier_combos`

**Files:**
- Modify: `tests/test_worldcup_stats.py` (add tests)
- Modify: `games/worldcup/services/stats.py` (add function)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_worldcup_stats.py`:

```python
def test_get_tier_combos_returns_pairs(session):
    from games.worldcup.services.stats import get_tier_combos

    u1 = _make_user(session, 'carol')
    u2 = _make_user(session, 'dave')
    u3 = _make_user(session, 'eve')
    t1 = _make_team(session, 'SPA', 'Spain', tier=1, multiplier=1.0)
    t2 = _make_team(session, 'FRA', 'France', tier=1, multiplier=1.0)
    t3 = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
    e1 = _make_enrollment(session, u1.id)
    e2 = _make_enrollment(session, u2.id)
    e3 = _make_enrollment(session, u3.id)
    # Spain+France: all 3 players
    _make_pick(session, e1.id, t1.id, tier=1)
    _make_pick(session, e1.id, t2.id, tier=1)
    _make_pick(session, e2.id, t1.id, tier=1)
    _make_pick(session, e2.id, t2.id, tier=1)
    _make_pick(session, e3.id, t1.id, tier=1)
    _make_pick(session, e3.id, t3.id, tier=1)
    session.commit()

    combos = get_tier_combos(2026)

    assert 1 in combos
    assert 3 not in combos  # no tier 3 picks
    top_pair = combos[1][0]
    # Spain+France appear together 2x; Spain+Argentina 1x
    assert top_pair['count'] == 2
    assert {top_pair['team_a'], top_pair['team_b']} == {'Spain', 'France'}
    assert abs(top_pair['pct'] - (2 / 3 * 100)) < 0.1


def test_get_tier_combos_excludes_tier2(session):
    from games.worldcup.services.stats import get_tier_combos

    session.commit()
    combos = get_tier_combos(2026)

    assert 2 not in combos


def test_get_tier_combos_empty_season(session):
    from games.worldcup.services.stats import get_tier_combos

    session.commit()
    combos = get_tier_combos(2026)

    # No picks at all — all tiers either absent or empty
    for tier_data in combos.values():
        assert tier_data == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_get_tier_combos_returns_pairs tests/test_worldcup_stats.py::test_get_tier_combos_excludes_tier2 tests/test_worldcup_stats.py::test_get_tier_combos_empty_season -v 2>&1 | head -20
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add `get_tier_combos` to `games/worldcup/services/stats.py`**

Add these imports at the top of `stats.py` (after existing imports):

```python
from sqlalchemy.orm import aliased
```

Append to `stats.py`:

```python
def get_tier_combos(season_year: int) -> dict[int, list[dict]]:
    """Return top-5 team pairs per tier for tiers 1, 3, 4, 5.

    Tier 2 is excluded — players pick only 1 Tier 2 team, so no pairs exist.
    """
    total_players: int = WorldCupEnrollment.query.filter_by(
        season_year=season_year
    ).count()

    P1 = aliased(WorldCupPick)
    P2 = aliased(WorldCupPick)
    T1 = aliased(WorldCupTeam)
    T2 = aliased(WorldCupTeam)

    result: dict[int, list[dict]] = {}
    for tier in [1, 3, 4, 5]:
        rows = (
            db.session.query(
                T1.display_name.label('team_a'),
                T2.display_name.label('team_b'),
                func.count().label('count'),
            )
            .select_from(P1)
            .join(WorldCupEnrollment, P1.enrollment_id == WorldCupEnrollment.id)
            .join(P2, (P2.enrollment_id == P1.enrollment_id) & (P1.team_id < P2.team_id))
            .join(T1, T1.id == P1.team_id)
            .join(T2, T2.id == P2.team_id)
            .filter(WorldCupEnrollment.season_year == season_year)
            .filter(P1.tier == tier)
            .filter(P2.tier == tier)
            .group_by(T1.display_name, T2.display_name)
            .order_by(func.count().desc())
            .limit(5)
            .all()
        )
        result[tier] = [
            {
                'team_a': row.team_a,
                'team_b': row.team_b,
                'count': row.count,
                'pct': round(row.count / total_players * 100, 1) if total_players > 0 else 0.0,
            }
            for row in rows
        ]
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_get_tier_combos_returns_pairs tests/test_worldcup_stats.py::test_get_tier_combos_excludes_tier2 tests/test_worldcup_stats.py::test_get_tier_combos_empty_season -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Run the full stats test suite**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py -v
```

Expected: All PASSED (no failures).

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/stats.py tests/test_worldcup_stats.py
git commit -m "feat(worldcup): add get_tier_combos with self-join query"
```

---

## Task 4: Route `/stats`

**Files:**
- Modify: `games/worldcup/routes.py` (add import + route)
- Modify: `tests/test_worldcup_stats.py` (add route test)

- [ ] **Step 1: Write the failing route test**

Append to `tests/test_worldcup_stats.py`:

```python
@pytest.fixture()
def client(app):
    return app.test_client()


def test_stats_route_public(client, session):
    """Stats page is public — no login required."""
    # Need at least one team for country_stats to work
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert b'Stats Hub' in resp.data
    assert b'wc-stats-tab-bar' in resp.data


def test_stats_route_my_picks_unauthenticated(client, session):
    """Unauthenticated users get MY_PICKS = [] — no error."""
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert b'MY_PICKS = []' in resp.data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_stats_route_public tests/test_worldcup_stats.py::test_stats_route_my_picks_unauthenticated -v 2>&1 | head -30
```

Expected: FAIL with 404 (route doesn't exist yet).

- [ ] **Step 3: Add import + route to `games/worldcup/routes.py`**

Add to the imports block in `routes.py` (after the existing `from games.worldcup.services.scoring import ...` block):

```python
from games.worldcup.services.stats import (
    get_country_stats,
    get_tier_stats,
    get_overview_kpis,
    get_tier_combos,
)
```

Add the route at the end of the public routes section (before admin routes), after the `rules` route:

```python
@worldcup_bp.route('/stats')
def stats():
    country_stats, total_players = get_country_stats(SEASON_YEAR)
    tier_stats = get_tier_stats(country_stats)
    kpis = get_overview_kpis(country_stats, total_players)
    combos = get_tier_combos(SEASON_YEAR)

    my_picks: list[str] = []
    if current_user.is_authenticated:
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()
        if enrollment:
            my_picks = [p.team.display_name for p in enrollment.picks]

    return render_template(
        'worldcup/stats.html',
        country_stats=country_stats,
        tier_stats=tier_stats,
        kpis=kpis,
        combos=combos,
        my_picks=my_picks,
        current_phase=_derive_tournament_phase(),
    )
```

- [ ] **Step 4: Create a minimal stub template to make the route test pass**

Create `games/worldcup/templates/worldcup/stats.html` with only this content temporarily:

```html
{% extends "base.html" %}
{% block title %}Stats Hub — World Cup Fantasy Pool{% endblock %}
{% block content %}
<div class="wc-stats-tab-bar"></div>
<p>Stats Hub</p>
<script>const MY_PICKS = {{ my_picks | tojson }};</script>
{% endblock %}
```

- [ ] **Step 5: Run route tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_stats.py::test_stats_route_public tests/test_worldcup_stats.py::test_stats_route_my_picks_unauthenticated -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/stats.html tests/test_worldcup_stats.py
git commit -m "feat(worldcup): add /stats route (stub template)"
```

---

## Task 5: CSS Classes

**Files:**
- Modify: `static/css/style.css`

- [ ] **Step 1: Append stats CSS to the World Cup section**

Find the `/* === WORLD CUP FANTASY POOL === */` section in `static/css/style.css` and append the following block at the end of that section (before the next `/* === */` section header):

```css
/* — Stats Hub — */
.wc-stats-tab-bar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 93px;
  z-index: 900;
  overflow-x: auto;
  scrollbar-width: none;
  transition: background .3s;
}
.wc-stats-tab-bar::-webkit-scrollbar { display: none; }
.wc-stats-tab-bar-inner { display: flex; min-width: max-content; }

.wc-stats-tab-btn {
  font-family: 'Teko', sans-serif;
  font-weight: 500;
  font-size: .82rem;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: .7rem 1.15rem;
  white-space: nowrap;
  cursor: pointer;
  transition: color .15s, border-color .15s;
}
.wc-stats-tab-btn:hover { color: var(--game-primary); border-color: var(--game-primary-light); }
.wc-stats-tab-btn.active { color: var(--game-primary); border-color: var(--game-accent); font-weight: 700; }

.wc-stats-panel { display: none; animation: wc-fadeInUp .22s ease both; }
.wc-stats-panel.active { display: block; }
@keyframes wc-fadeInUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }

.wc-pick-bar { margin-bottom: .55rem; }
.wc-pick-bar.my-pick .wc-pick-bar-label { color: var(--platform-accent); font-weight: 700; }
.wc-pick-bar-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'Teko', sans-serif;
  font-size: .92rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: .18rem;
  gap: .5rem;
}
.wc-pick-bar-track { height: 7px; background: var(--bg-muted); border-radius: 4px; overflow: hidden; }
.wc-pick-bar-fill { height: 100%; border-radius: 4px; transition: width .55s cubic-bezier(.4,0,.2,1); }

/* Stats page component classes */
.wc-kpi-block {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: 3px solid var(--game-accent);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1rem;
  text-align: center;
  box-shadow: var(--shadow-sm);
  transition: background .3s, border-color .3s;
}
.wc-kpi-value {
  font-family: 'Teko', sans-serif;
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}
.wc-kpi-label {
  font-family: 'Teko', sans-serif;
  font-size: .78rem;
  font-weight: 500;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: .3rem;
}
.wc-kpi-sub { font-size: .76rem; color: var(--text-muted); margin-top: .15rem; }

.wc-stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 1.5rem;
  height: 100%;
  transition: background .3s, border-color .3s;
}
.wc-card-head {
  font-family: 'Teko', sans-serif;
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Tier badges */
.wc-tb {
  display: inline-block;
  font-family: 'Teko', sans-serif;
  font-weight: 700;
  font-size: .68rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  padding: .18em .55em;
  border-radius: 1rem;
  color: #fff;
  line-height: 1.4;
  vertical-align: middle;
}
.wc-tb-1 { background: var(--wc-tier1); }
.wc-tb-2 { background: var(--wc-tier2); }
.wc-tb-3 { background: var(--wc-tier3); }
.wc-tb-4 { background: var(--wc-tier4); }
.wc-tb-5 { background: var(--wc-tier5); }

/* Scoring list */
.wc-lb-row {
  display: grid;
  grid-template-columns: 1.8rem 1fr 4rem;
  align-items: center;
  gap: .6rem;
  padding: .55rem .6rem;
  border-radius: var(--radius);
  transition: background .15s;
}
.wc-lb-row:hover { background: var(--bg-muted); }
.wc-lb-rank { font-family: 'Teko', sans-serif; font-weight: 700; font-size: 1.05rem; color: var(--text-muted); text-align: center; }
.wc-lb-score { font-family: 'Teko', sans-serif; font-weight: 700; font-size: 1.1rem; color: var(--game-primary); text-align: right; }
.wc-still-in {
  display: inline-block;
  font-family: 'Teko', sans-serif;
  font-size: .65rem;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  padding: .12em .45em;
  border-radius: .25rem;
  background: rgba(26,122,69,.15);
  color: #1A7A45;
  margin-left: .3rem;
}
.wc-sbar { display: flex; height: 5px; background: var(--bg-muted); border-radius: 3px; overflow: hidden; margin-top: .25rem; }
.wc-sbar-g { background: var(--game-primary); }
.wc-sbar-k { background: var(--game-accent); }

/* Combo rows */
.wc-combo-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .45rem .6rem;
  border-radius: var(--radius);
  transition: background .15s;
}
.wc-combo-row:hover { background: var(--bg-muted); }
.wc-combo-count { font-family: 'Teko', sans-serif; font-weight: 700; font-size: .95rem; color: var(--game-primary); text-align: right; white-space: nowrap; }

/* Impact rows */
.wc-imp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .4rem .6rem;
  border-radius: var(--radius);
  transition: background .15s;
  margin-bottom: .15rem;
}
.wc-imp-row:hover { background: var(--bg-muted); }

@media (max-width: 767px) {
  .wc-stats-tab-bar { top: 86px; }
  .wc-kpi-value { font-size: 2rem; }
}
```

- [ ] **Step 2: Verify CSS is syntactically valid by loading the dev server briefly**

```bash
FLASK_APP=app.py venv/bin/flask run --port 5001 &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/worldcup/stats
kill %1
```

Expected: `200`.

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "style(worldcup): add Stats Hub CSS classes"
```

---

## Task 6: Subnav Pill

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1: Add the Stats Hub pill to the worldcup subnav**

In `templates/base.html`, locate the `{% if request.blueprint == 'worldcup' %}` subnav block. The subnav-pills div currently contains: Dashboard, Leaderboard, Schedule, Groups, My Picks, Rules, and (conditional) Admin.

Add the Stats Hub pill **between Groups and My Picks**:

```html
<a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
   href="{{ url_for('worldcup.stats') }}">Stats Hub</a>
```

The pills block should look like this after the edit:

```html
<div class="subnav-pills">
    <a class="subnav-pill {% if request.endpoint == 'worldcup.index' %}active{% endif %}"
       href="{{ url_for('worldcup.index') }}">Dashboard</a>
    <a class="subnav-pill {% if request.endpoint in ['worldcup.leaderboard', 'worldcup.player_detail'] %}active{% endif %}"
       href="{{ url_for('worldcup.leaderboard') }}">Leaderboard</a>
    <a class="subnav-pill {% if request.endpoint == 'worldcup.schedule' %}active{% endif %}"
       href="{{ url_for('worldcup.schedule') }}">Schedule</a>
    <a class="subnav-pill {% if request.endpoint == 'worldcup.groups' %}active{% endif %}"
       href="{{ url_for('worldcup.groups') }}">Groups</a>
    <a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
       href="{{ url_for('worldcup.stats') }}">Stats Hub</a>
    <a class="subnav-pill {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
       href="{{ url_for('worldcup.picks') }}">My Picks</a>
    <a class="subnav-pill {% if request.endpoint == 'worldcup.rules' %}active{% endif %}"
       href="{{ url_for('worldcup.rules') }}">Rules</a>
    {% if worldcup_enrollment and worldcup_enrollment.is_admin %}
    ...
    {% endif %}
</div>
```

- [ ] **Step 2: Run the full test suite to verify nothing broke**

```bash
venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat(worldcup): add Stats Hub subnav pill"
```

---

## Task 7: Full Template

**Files:**
- Modify: `games/worldcup/templates/worldcup/stats.html` (replace stub with full implementation)

This task replaces the stub template from Task 4 with the full 6-tab page matching the prototype in `docs/World Cup Stats Hub.html`. The JS field names are adapted to the service layer's dict keys.

- [ ] **Step 1: Write the full template**

Replace `games/worldcup/templates/worldcup/stats.html` entirely with:

```html
{% extends "base.html" %}
{% block title %}Stats Hub — World Cup Fantasy Pool{% endblock %}

{% block head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
{% endblock %}

{% block content %}
<script>
if (window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.body.classList.add('theme-dark');
</script>

<!-- ── Hero ── -->
<div class="page-hero">
  <div class="container">
    <div class="d-flex align-items-center gap-3 mb-2 flex-wrap">
      <span class="phase-chip">
        <span class="phase-dot"></span>
        {% if current_phase == 'completed' %}Tournament Complete
        {% elif current_phase == 'knockout' %}Knockout Stage
        {% elif current_phase == 'group_stage' %}Group Stage
        {% else %}Pre-Tournament{% endif %}
      </span>
    </div>
    <h1 class="mb-1" style="font-size:2.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Stats Hub</h1>
    <p class="mb-0" style="color:rgba(255,255,255,.6);font-size:1rem;">
      {{ kpis.total_players }} player{{ 's' if kpis.total_players != 1 }} &middot; Full tournament analytics
    </p>
  </div>
</div>

<!-- ── Tab Bar ── -->
<div class="wc-stats-tab-bar">
  <div class="container p-0">
    <div class="wc-stats-tab-bar-inner">
      <button class="wc-stats-tab-btn active" onclick="switchTab('overview')">Overview</button>
      <button class="wc-stats-tab-btn" onclick="switchTab('selection')">Selection</button>
      <button class="wc-stats-tab-btn" onclick="switchTab('scoring')">Scoring</button>
      <button class="wc-stats-tab-btn" onclick="switchTab('tiers')">Tier Performance</button>
      <button class="wc-stats-tab-btn" onclick="switchTab('impact')">Portfolio Impact</button>
      <button class="wc-stats-tab-btn" onclick="switchTab('combos')">Pick Combos</button>
    </div>
  </div>
</div>

<main>
<div class="container pb-5">

  <!-- ════ OVERVIEW ════ -->
  <div id="tab-overview" class="wc-stats-panel active pt-4 pb-5">
    <div class="row g-3">
      <div class="col-6 col-md-3">
        <div class="wc-kpi-block" style="border-top-color:var(--game-primary);">
          <div class="wc-kpi-value">{{ kpis.total_players }}</div>
          <div class="wc-kpi-label">Players Enrolled</div>
          <div class="wc-kpi-sub">Picks locked Jun 11</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="wc-kpi-block" style="border-top-color:var(--game-accent);">
          <div class="wc-kpi-value">{{ kpis.active_countries }}</div>
          <div class="wc-kpi-label">Teams Still Active</div>
          <div class="wc-kpi-sub">{{ kpis.top_country_name }} &amp; others</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="wc-kpi-block" style="border-top-color:var(--wc-tier3);">
          <div class="wc-kpi-value">{{ kpis.top_country_score | round(1) }}</div>
          <div class="wc-kpi-label">Top Country Score</div>
          <div class="wc-kpi-sub">{{ kpis.top_country_name }}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="wc-kpi-block" style="border-top-color:var(--wc-tier5);">
          <div class="wc-kpi-value">{{ kpis.total_pts_awarded | round(0) | int }}</div>
          <div class="wc-kpi-label">Total Pts Awarded</div>
          <div class="wc-kpi-sub">Group + Knockout combined</div>
        </div>
      </div>
    </div>

    <!-- Tournament Progress Bar -->
    <div class="wc-stat-card mt-4">
      <div class="wc-card-head">
        <span>Tournament Progress</span>
        <span style="font-family:'Teko',sans-serif;font-size:.75rem;color:var(--text-muted);">Jun 11 – Jul 19 · 104 matches</span>
      </div>
      <div id="progress-bar-wrap" class="d-flex gap-0 align-items-stretch"
           style="border-radius:var(--radius);overflow:hidden;height:36px;font-family:'Teko',sans-serif;font-size:.78rem;letter-spacing:.05em;text-transform:uppercase;">
      </div>
    </div>
  </div>

  <!-- ════ SELECTION STATS ════ -->
  <div id="tab-selection" class="wc-stats-panel pt-4 pb-5">
    <h2 style="font-family:'Teko',sans-serif;font-size:1.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-primary);margin-bottom:.2rem;">Selection Stats</h2>
    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:1.5rem;">How players distributed their picks — who the field trusts, who they ignored</p>

    <div class="row g-4 mb-4">
      <div class="col-lg-6">
        <div class="wc-stat-card">
          <div class="wc-card-head">
            <span>Most Popular Picks</span>
            <span style="font-family:'Teko',sans-serif;font-size:.72rem;color:var(--text-muted);">% of players</span>
          </div>
          <div id="bars-popular"></div>
        </div>
      </div>
      <div class="col-lg-6">
        <div class="wc-stat-card">
          <div class="wc-card-head">
            <span>Least Popular Picks</span>
            <span style="font-family:'Teko',sans-serif;font-size:.72rem;color:var(--text-muted);">Hidden gems?</span>
          </div>
          <div id="bars-unpopular"></div>
        </div>
      </div>
    </div>

    <div class="wc-stat-card">
      <div class="wc-card-head"><span>Pick Distribution by Tier</span></div>
      <div class="row g-4">
        <div class="col-md-6"><div id="bars-t1"></div></div>
        <div class="col-md-6"><div id="bars-t2"></div></div>
        <div class="col-12"><div id="bars-t3"></div></div>
        <div class="col-md-6"><div id="bars-t4"></div></div>
        <div class="col-md-6"><div id="bars-t5"></div></div>
      </div>
    </div>
  </div>

  <!-- ════ SCORING ════ -->
  <div id="tab-scoring" class="wc-stats-panel pt-4 pb-5">
    <h2 style="font-family:'Teko',sans-serif;font-size:1.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-primary);margin-bottom:.2rem;">Country Scoring</h2>
    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:1.5rem;">Multiplied points earned — group stage (navy) stacked with knockout rounds (red)</p>
    <div class="row g-4">
      <div class="col-xl-8">
        <div class="wc-stat-card">
          <div class="wc-card-head">
            <span>Top Scorers</span>
            <span style="display:flex;gap:.6rem;align-items:center;font-family:'Teko',sans-serif;font-size:.72rem;">
              <span style="display:flex;align-items:center;gap:.3rem;"><span style="width:10px;height:10px;border-radius:2px;background:var(--game-primary);display:inline-block;"></span>Group</span>
              <span style="display:flex;align-items:center;gap:.3rem;"><span style="width:10px;height:10px;border-radius:2px;background:var(--game-accent);display:inline-block;"></span>Knockout</span>
            </span>
          </div>
          <div id="scoring-list"></div>
        </div>
      </div>
      <div class="col-xl-4">
        <div class="wc-stat-card">
          <div class="wc-card-head"><span>Pts Breakdown</span></div>
          <div style="position:relative;height:260px;"><canvas id="ch-accum"></canvas></div>
          <div class="mt-3" id="accum-summary" style="font-family:'Teko',sans-serif;font-size:.8rem;color:var(--text-muted);letter-spacing:.04em;text-transform:uppercase;"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ════ TIER PERFORMANCE ════ -->
  <div id="tab-tiers" class="wc-stats-panel pt-4 pb-5">
    <h2 style="font-family:'Teko',sans-serif;font-size:1.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-primary);margin-bottom:.2rem;">Tier Performance</h2>
    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:1.5rem;">Which multiplier tiers are delivering — average multiplied score per country within each tier</p>
    <div class="row g-3 mb-4" id="tier-kpis"></div>
    <div class="row g-4">
      <div class="col-lg-7">
        <div class="wc-stat-card">
          <div class="wc-card-head"><span>Avg Multiplied Score by Tier</span></div>
          <div style="position:relative;height:260px;"><canvas id="ch-tier-bar"></canvas></div>
        </div>
      </div>
      <div class="col-lg-5">
        <div class="wc-stat-card">
          <div class="wc-card-head"><span>Total Points by Tier</span></div>
          <div style="position:relative;height:260px;"><canvas id="ch-tier-donut"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ════ PORTFOLIO IMPACT ════ -->
  <div id="tab-impact" class="wc-stats-panel pt-4 pb-5">
    <h2 style="font-family:'Teko',sans-serif;font-size:1.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-primary);margin-bottom:.2rem;">Portfolio Impact</h2>
    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:1.5rem;">Countries mapped by selection popularity vs. score — find the carries, gems, and dead weight</p>
    <div class="row g-4">
      <div class="col-xl-8">
        <div class="wc-stat-card">
          <div class="wc-card-head">
            <span>Popularity vs. Score (bubble = # of players)</span>
            <span style="display:flex;gap:.75rem;font-family:'Teko',sans-serif;font-size:.7rem;letter-spacing:.04em;text-transform:uppercase;color:var(--text-muted);">
              <span>High pick % + high score = <strong style="color:#1A7A45;">carrying</strong></span>
              <span>Low pick % + high score = <strong style="color:var(--platform-accent);">gem</strong></span>
            </span>
          </div>
          <div style="position:relative;height:380px;"><canvas id="ch-scatter"></canvas></div>
        </div>
      </div>
      <div class="col-xl-4 d-flex flex-column gap-4">
        <div class="wc-stat-card">
          <div class="wc-card-head"><span>🟢 Helping Most Players</span></div>
          <div id="help-list"></div>
        </div>
        <div class="wc-stat-card">
          <div class="wc-card-head"><span>🔴 Disappointing Most</span></div>
          <div id="hurt-list"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ════ PICK COMBOS ════ -->
  <div id="tab-combos" class="wc-stats-panel pt-4 pb-5">
    <h2 style="font-family:'Teko',sans-serif;font-size:1.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-primary);margin-bottom:.2rem;">Pick Combos &amp; Overlap</h2>
    <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:1.5rem;">Most common team pairings within tiers — how many players share the same picks</p>
    <div class="row g-4">
      <div class="col-lg-6"><div class="wc-stat-card"><div class="wc-card-head"><span>Tier 1 Pairs</span><span class="wc-tb wc-tb-1">Favorites</span></div><div id="combos-t1"></div></div></div>
      <div class="col-lg-6"><div class="wc-stat-card"><div class="wc-card-head"><span>Tier 3 Pairs</span><span class="wc-tb wc-tb-3">Dark Horses</span></div><div id="combos-t3"></div></div></div>
      <div class="col-lg-6"><div class="wc-stat-card"><div class="wc-card-head"><span>Tier 4 Pairs</span><span class="wc-tb wc-tb-4">Underdogs</span></div><div id="combos-t4"></div></div></div>
      <div class="col-lg-6"><div class="wc-stat-card"><div class="wc-card-head"><span>Tier 5 Pairs</span><span class="wc-tb wc-tb-5">Wildcards</span></div><div id="combos-t5"></div></div></div>
    </div>
  </div>

</div><!-- /container -->
</main>
{% endblock %}

{% block scripts %}
<script>
// ── DATA BRIDGE ───────────────────────────────────────────────
const MY_PICKS = {{ my_picks | tojson }};
const COUNTRY_STATS = {{ country_stats | tojson }};
const TIER_STATS = {{ tier_stats | tojson }};
const COMBOS = {{ combos | tojson }};
const KPIS = {{ kpis | tojson }};

// ── CONSTANTS ─────────────────────────────────────────────────
const TC = {1:'#D97706',2:'#4B7399',3:'#B45309',4:'#0D7377',5:'#9333EA'};
const TN = {1:'Favorites',2:'Contenders',3:'Dark Horses',4:'Underdogs',5:'Wildcards'};
const TM = {1:1,2:1.5,3:2.5,4:4,5:7};
const TAB_IDS = ['overview','selection','scoring','tiers','impact','combos'];

// ── HELPERS ───────────────────────────────────────────────────
function tb(t){ return `<span class="wc-tb wc-tb-${t}">T${t}</span>`; }
function tbl(t){ return `<span class="wc-tb wc-tb-${t}">T${t} · ${TN[t]}</span>`; }

function pbarHtml(c, maxPct) {
  const hl = MY_PICKS.includes(c.name);
  const pct = Math.round(c.pick_pct);
  const fill = Math.max(2, (pct / maxPct) * 100);
  return `<div class="wc-pick-bar${hl ? ' my-pick' : ''}">
    <div class="wc-pick-bar-label">
      <span>${c.flag_emoji} ${c.name} ${hl ? '<span style="color:var(--platform-accent)">★</span>' : ''} ${tb(c.tier)}</span>
      <span style="font-family:'Teko',sans-serif;font-weight:700;color:${TC[c.tier]};">${pct}%</span>
    </div>
    <div class="wc-pick-bar-track"><div class="wc-pick-bar-fill" style="width:${fill}%;background:${TC[c.tier]};"></div></div>
  </div>`;
}

function tierHeader(t) {
  return `<div style="font-family:'Teko',sans-serif;font-weight:700;font-size:.9rem;letter-spacing:.06em;text-transform:uppercase;color:${TC[t]};margin-bottom:.65rem;">${tbl(t)} <span style="color:var(--text-muted);font-weight:500;">×${TM[t]} multiplier</span></div>`;
}

// ── OVERVIEW PROGRESS BAR ─────────────────────────────────────
function renderProgressBar() {
  const phase = '{{ current_phase }}';
  const phases = [
    {id:'group',   label:'Group Stage', flex:3, doneStyle:`background:var(--game-primary);color:#fff;`},
    {id:'R32',     label:'R32',         flex:1, doneStyle:`background:var(--game-primary-light);color:#fff;`},
    {id:'R16',     label:'R16',         flex:1, doneStyle:`background:var(--game-accent);color:#fff;`},
    {id:'QF',      label:'QF',          flex:1, doneStyle:`background:#B45309;color:#fff;`},
    {id:'SF',      label:'SF',          flex:1, doneStyle:`background:rgba(212,168,32,.9);color:#fff;`},
    {id:'final',   label:'Final',       flex:1, doneStyle:`background:var(--platform-accent);color:var(--platform-primary-dark);font-weight:800;`},
  ];
  const phaseOrder = ['pre_tournament','group_stage','knockout','completed'];
  const currentIdx = phaseOrder.indexOf(phase);

  // Determine which visual segments are done, current, or upcoming
  // Map server phases to visual segment completion
  const segDone = {
    group:  currentIdx >= 1,
    R32:    currentIdx >= 2,
    R16:    currentIdx >= 2,
    QF:     currentIdx >= 2,
    SF:     currentIdx >= 3,
    final:  currentIdx >= 3,
  };
  const segCurrent = {
    group:  currentIdx === 1,
    R32:    currentIdx === 2,
    R16:    false,
    QF:     false,
    SF:     currentIdx === 2,
    final:  currentIdx === 2,
  };

  const wrap = document.getElementById('progress-bar-wrap');
  wrap.innerHTML = phases.map(p => {
    const done = segDone[p.id];
    const cur = segCurrent[p.id];
    const label = done ? p.label + ' ✓' : cur ? p.label + ' ←' : p.label;
    let style = `flex:${p.flex};display:flex;align-items:center;justify-content:center;padding:0 .75rem;`;
    if (done) style += p.doneStyle;
    else if (cur) style += `background:rgba(212,168,32,.2);color:var(--platform-accent);border:2px solid var(--platform-accent);font-weight:700;`;
    else style += `background:var(--bg-muted);color:var(--text-muted);`;
    return `<div style="${style}">${label}</div>`;
  }).join('');
}

// ── RENDER: SELECTION ─────────────────────────────────────────
function renderSelection() {
  const withPicks = COUNTRY_STATS.filter(c => c.pick_count > 0);
  const sorted = [...withPicks].sort((a,b) => b.pick_count - a.pick_count);
  const top = sorted.slice(0, 10);
  const bot = [...withPicks].filter(c => c.pick_count <= 4).sort((a,b) => a.pick_count - b.pick_count).slice(0, 8);

  const topMax = top[0]?.pick_pct || 10;
  document.getElementById('bars-popular').innerHTML = top.map(c => pbarHtml(c, topMax)).join('');

  const botMax = (Math.max(...bot.map(c => c.pick_pct)) || 10) + 4;
  document.getElementById('bars-unpopular').innerHTML = bot.map(c => pbarHtml(c, botMax)).join('');

  [1,2,3,4,5].forEach(t => {
    const tc = COUNTRY_STATS.filter(c => c.tier === t).sort((a,b) => b.pick_count - a.pick_count);
    const mx = tc[0]?.pick_pct || 10;
    document.getElementById(`bars-t${t}`).innerHTML = tierHeader(t) + tc.map(c => pbarHtml(c, mx)).join('');
  });
}

// ── RENDER: SCORING LIST ──────────────────────────────────────
function renderScoring() {
  const sorted = [...COUNTRY_STATS].sort((a,b) => b.total_score - a.total_score).slice(0, 16);
  const mx = sorted[0]?.total_score || 1;
  document.getElementById('scoring-list').innerHTML = sorted.map((c,i) => {
    const hl = MY_PICKS.includes(c.name);
    const gf = Math.max(1, c.group_score / mx * 100);
    const kf = Math.max(0, c.ko_score / mx * 100);
    return `<div class="wc-lb-row${hl ? ' my-pick' : ''}">
      <div class="wc-lb-rank">${i+1}</div>
      <div>
        <div style="font-family:'Teko',sans-serif;font-weight:600;font-size:.95rem;color:var(--text-primary);">
          ${c.flag_emoji} ${c.name}${hl ? ' <span style="color:var(--platform-accent)">★</span>' : ''} ${tb(c.tier)}${c.is_active ? '<span class="wc-still-in ms-1">Active</span>' : ''}
        </div>
        <div class="wc-sbar" style="margin-top:.2rem;">
          <div class="wc-sbar-g" style="width:${gf}%;"></div>
          <div class="wc-sbar-k" style="width:${kf}%;"></div>
        </div>
        <div style="font-family:'Teko',sans-serif;font-size:.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin-top:.1rem;">
          Grp: ${c.group_score.toFixed(1)} · KO: ${c.ko_score.toFixed(1)}
        </div>
      </div>
      <div class="wc-lb-score">${c.total_score.toFixed(1)}</div>
    </div>`;
  }).join('');
}

// ── RENDER: TIER KPIS ─────────────────────────────────────────
function renderTierKPIs() {
  document.getElementById('tier-kpis').innerHTML = [1,2,3,4,5].map(t => {
    const ts = TIER_STATS[t];
    if (!ts) return '';
    return `<div class="col-6 col-md">
      <div class="wc-kpi-block" style="border-top-color:${TC[t]};">
        <div class="wc-kpi-value" style="font-size:1.9rem;">${ts.avg_score.toFixed(1)}</div>
        <div class="wc-kpi-label">${tbl(t)}</div>
        <div class="wc-kpi-sub">Best: ${ts.best_country} (${ts.best_score.toFixed(1)})</div>
      </div>
    </div>`;
  }).join('');
}

// ── RENDER: IMPACT ────────────────────────────────────────────
function renderImpact() {
  const withScore = COUNTRY_STATS.filter(c => c.total_score > 0 && c.pick_count > 0);
  const byImpact = withScore
    .map(c => ({...c, impact: c.pick_count * c.total_score}))
    .sort((a,b) => b.impact - a.impact);

  document.getElementById('help-list').innerHTML = byImpact.slice(0, 5).map(c => `
    <div class="wc-imp-row">
      <div><span style="font-family:'Teko',sans-serif;font-weight:600;">${c.flag_emoji} ${c.name}</span> ${tb(c.tier)}</div>
      <div style="text-align:right;">
        <div class="wc-combo-count">${Math.round(c.pick_pct)}% · ${c.total_score.toFixed(1)}pts</div>
        <div style="font-family:'Teko',sans-serif;font-size:.7rem;color:var(--text-muted);">Impact: ${c.impact.toFixed(0)}</div>
      </div>
    </div>`).join('');

  const byDisappoint = COUNTRY_STATS
    .filter(c => c.pick_count >= 4)
    .map(c => ({...c, ratio: c.total_score / c.pick_count}))
    .sort((a,b) => a.ratio - b.ratio);

  document.getElementById('hurt-list').innerHTML = byDisappoint.slice(0, 5).map(c => `
    <div class="wc-imp-row">
      <div><span style="font-family:'Teko',sans-serif;font-weight:600;">${c.flag_emoji} ${c.name}</span> ${tb(c.tier)}</div>
      <div style="text-align:right;">
        <div class="wc-combo-count" style="color:var(--game-accent);">${Math.round(c.pick_pct)}% · ${c.total_score.toFixed(1)}pts</div>
      </div>
    </div>`).join('');
}

// ── RENDER: COMBOS ────────────────────────────────────────────
function renderCombos() {
  function renderComboList(combos, containerId, tierNum) {
    if (!combos || combos.length === 0) {
      document.getElementById(containerId).innerHTML =
        '<p style="font-family:\'Teko\',sans-serif;color:var(--text-muted);font-size:.9rem;">No pairs yet — picks still open or no data.</p>';
      return;
    }
    const mx = combos[0].count;
    document.getElementById(containerId).innerHTML = combos.map(combo => {
      const hl = [combo.team_a, combo.team_b].every(t => MY_PICKS.includes(t));
      return `<div class="wc-combo-row${hl ? ' my-pick' : ''}">
        <div style="display:flex;flex-wrap:wrap;gap:.3rem;align-items:center;">
          <strong style="font-family:'Teko',sans-serif;">${combo.team_a}</strong>
          <span style="color:var(--text-muted);margin:0 .1rem;">+</span>
          <strong style="font-family:'Teko',sans-serif;">${combo.team_b}</strong>
          ${hl ? '<span style="color:var(--platform-accent);font-family:\'Teko\',sans-serif;font-size:.8rem;">★ Your picks</span>' : ''}
        </div>
        <div style="text-align:right;">
          <div class="wc-combo-count">${combo.count} players</div>
          <div style="font-family:'Teko',sans-serif;font-size:.68rem;color:var(--text-muted);">${combo.pct.toFixed(0)}% of field</div>
        </div>
      </div>
      <div style="height:3px;background:var(--bg-muted);border-radius:2px;overflow:hidden;margin:0 .6rem .4rem;">
        <div style="height:100%;width:${(combo.count/mx)*100}%;background:${TC[tierNum]};border-radius:2px;"></div>
      </div>`;
    }).join('');
  }
  renderComboList(COMBOS[1], 'combos-t1', 1);
  renderComboList(COMBOS[3], 'combos-t3', 3);
  renderComboList(COMBOS[4], 'combos-t4', 4);
  renderComboList(COMBOS[5], 'combos-t5', 5);
}

// ── CHARTS (lazy per tab) ─────────────────────────────────────
const chartsInitialized = new Set();
let charts = {};

function initScoringCharts() {
  Chart.defaults.font.family = 'Teko';
  const totalGroup = COUNTRY_STATS.reduce((s,c) => s + c.group_score, 0);
  const totalKO = COUNTRY_STATS.reduce((s,c) => s + c.ko_score, 0);
  const totalAwarded = totalGroup + totalKO;

  charts.accum = new Chart(document.getElementById('ch-accum'), {
    type: 'doughnut',
    data: {
      labels: ['Group Stage', 'Knockout Rounds'],
      datasets: [{
        data: [totalGroup, totalKO],
        backgroundColor: ['#002868', '#BF0A30'],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: {position:'bottom',labels:{font:{size:12},color:'#8A849B',padding:14,boxWidth:12}},
        tooltip: {callbacks:{label:ctx=>` ${ctx.label}: ${ctx.parsed.toFixed(1)} pts`}},
      },
    },
  });

  document.getElementById('accum-summary').innerHTML = `
    <div class="d-flex justify-content-between mb-1"><span>Group Stage</span><strong style="color:var(--game-primary);">${totalGroup.toFixed(1)} pts</strong></div>
    <div class="d-flex justify-content-between mb-1"><span>Knockout Rounds</span><strong style="color:var(--game-accent);">${totalKO.toFixed(1)} pts</strong></div>
    <div class="d-flex justify-content-between pt-2" style="border-top:1px solid var(--border);">
      <span>Total Awarded</span><strong style="color:var(--text-primary);">${totalAwarded.toFixed(1)} pts</strong>
    </div>`;
}

function initTierCharts() {
  Chart.defaults.font.family = 'Teko';

  const tierAvgs = [1,2,3,4,5].map(t => {
    const ts = TIER_STATS[t];
    return ts ? ts.avg_score : 0;
  });
  charts.tierBar = new Chart(document.getElementById('ch-tier-bar'), {
    type: 'bar',
    data: {
      labels: ['T1 ×1','T2 ×1.5','T3 ×2.5','T4 ×4','T5 ×7'],
      datasets: [{
        label: 'Avg Score',
        data: tierAvgs,
        backgroundColor: [TC[1],TC[2],TC[3],TC[4],TC[5]],
        borderRadius: 5,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {display:false},
        tooltip: {callbacks:{label:ctx=>` ${ctx.parsed.y.toFixed(1)} avg pts`}},
      },
      scales: {
        x: {grid:{display:false},ticks:{font:{size:12}}},
        y: {grid:{color:'rgba(0,0,0,.05)'},ticks:{font:{size:11}}},
      },
    },
  });

  const tierTotals = [1,2,3,4,5].map(t => TIER_STATS[t]?.total_score || 0);
  charts.tierDonut = new Chart(document.getElementById('ch-tier-donut'), {
    type: 'doughnut',
    data: {
      labels: ['T1 Favorites','T2 Contenders','T3 Dark Horses','T4 Underdogs','T5 Wildcards'],
      datasets: [{
        data: tierTotals,
        backgroundColor: [TC[1],TC[2],TC[3],TC[4],TC[5]],
        borderWidth: 0,
        hoverOffset: 5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: {position:'bottom',labels:{font:{size:11},padding:10,boxWidth:11,color:'#8A849B'}},
        tooltip: {callbacks:{label:ctx=>` ${ctx.label}: ${ctx.parsed.toFixed(1)} pts`}},
      },
    },
  });
}

function initImpactCharts() {
  Chart.defaults.font.family = 'Teko';

  const datasets = [1,2,3,4,5].map(t => ({
    label: `Tier ${t}`,
    data: COUNTRY_STATS.filter(c => c.tier === t && c.pick_count > 0).map(c => ({
      x: c.pick_pct,
      y: c.total_score,
      r: Math.max(5, Math.sqrt(c.pick_count) * 3.2),
      name: c.name,
    })),
    backgroundColor: TC[t] + 'BB',
    borderColor: TC[t],
    borderWidth: 1.5,
  }));

  charts.scatter = new Chart(document.getElementById('ch-scatter'), {
    type: 'bubble',
    data: {datasets},
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {position:'right',labels:{font:{size:12},padding:12,boxWidth:11}},
        tooltip: {callbacks:{label:ctx=>` ${ctx.raw.name}: ${ctx.raw.x.toFixed(0)}% picked · ${ctx.raw.y.toFixed(1)} pts`}},
      },
      scales: {
        x: {
          title:{display:true,text:'% of Players Who Picked',font:{size:12},color:'#8A849B'},
          grid:{color:'rgba(0,0,0,.05)'},
          ticks:{font:{size:11},callback:v=>v+'%'},
          min:0,max:100,
        },
        y: {
          title:{display:true,text:'Multiplied Points',font:{size:12},color:'#8A849B'},
          grid:{color:'rgba(0,0,0,.05)'},
          ticks:{font:{size:11}},
          min:0,
        },
      },
    },
  });
}

// ── TABS ──────────────────────────────────────────────────────
function switchTab(id) {
  TAB_IDS.forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('active', t === id);
  });
  document.querySelectorAll('.wc-stats-tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', TAB_IDS[i] === id);
  });
  setTimeout(() => {
    if (id === 'scoring' && !chartsInitialized.has('scoring')) {
      chartsInitialized.add('scoring'); initScoringCharts();
    }
    if (id === 'tiers' && !chartsInitialized.has('tiers')) {
      chartsInitialized.add('tiers'); initTierCharts();
    }
    if (id === 'impact' && !chartsInitialized.has('impact')) {
      chartsInitialized.add('impact'); initImpactCharts();
    }
  }, 40);
  window.scrollTo({top: 0, behavior: 'instant'});
  try { localStorage.setItem('wc_stats_tab', id); } catch(e) {}
}

// ── INIT ──────────────────────────────────────────────────────
renderProgressBar();
renderSelection();
renderScoring();
renderTierKPIs();
renderImpact();
renderCombos();

try {
  const saved = localStorage.getItem('wc_stats_tab');
  if (saved && TAB_IDS.includes(saved)) switchTab(saved);
} catch(e) {}
</script>
{% endblock %}
```

- [ ] **Step 2: Run the full test suite**

```bash
venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -25
```

Expected: All tests PASS.

- [ ] **Step 3: Start the dev server and verify visually**

```bash
FLASK_APP=app.py venv/bin/flask run
```

Navigate to `http://localhost:5000/worldcup/stats` and verify:
- Page loads without errors
- Tab bar is sticky below subnav
- All 6 tabs switch correctly
- Pick bars render in Selection tab
- Scoring list renders with stacked bars
- Tier KPIs render in Tier Performance tab
- Impact lists render
- Combos render (or show "No pairs yet" message if no picks)
- Charts initialize on first tab switch (no zero-size canvas errors in console)
- Tab selection persists across reload (localStorage)
- Dark mode detection works if OS is set to dark

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/templates/worldcup/stats.html
git commit -m "feat(worldcup): implement Stats Hub full 6-tab template"
```

---

## Task 8: Run All Tests + Final Commit

- [ ] **Step 1: Run the complete test suite**

```bash
venv/bin/python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASS with 0 failures.

- [ ] **Step 2: Run pyright type check**

```bash
venv/bin/pyright games/worldcup/services/stats.py
```

Expected: 0 errors.

- [ ] **Step 3: Final commit**

```bash
git add -p  # review any unstaged changes
git commit -m "feat(worldcup): Stats Hub — 6-tab analytics dashboard

Adds public /worldcup/stats page with selection stats, country scoring,
tier performance, portfolio impact, and pick combo panels. Chart.js
charts initialize lazily per tab. MY_PICKS highlights user's own teams."
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `get_country_stats` with all fields | Task 1 |
| `get_tier_stats` pure Python | Task 2 |
| `get_overview_kpis` pure Python | Task 2 |
| `get_tier_combos` tiers 1,3,4,5 self-join | Task 3 |
| Public `/stats` route, `my_picks` for authenticated/enrolled users | Task 4 |
| CSS: tab bar, panel, pick bar, stats components | Task 5 |
| Subnav: Stats Hub pill between Groups and My Picks | Task 6 |
| Template: dark mode, data bridge, 6 tabs, lazy charts, pick highlighting, tab persistence | Task 7 |
| Edge case: zero picks → pick_pct=0 | Task 1 test |
| Edge case: unauthenticated → MY_PICKS=[] | Task 4 test |
| Edge case: no combos → graceful message | Task 7 (renderComboList) |

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks are complete.

**Type consistency:**
- `get_country_stats` → `list[dict]` with keys: `name`, `flag_emoji`, `tier`, `multiplier`, `pick_count`, `pick_pct`, `group_score`, `ko_score`, `total_score`, `is_active`
- `get_tier_stats` takes `country_stats: list[dict]` (same shape), accesses `c['tier']`, `c['total_score']`, `c['name']`
- `get_overview_kpis` takes same `country_stats`, accesses `c['is_active']`, `c['total_score']`, `c['name']`
- `get_tier_combos` returns `dict[int, list[dict]]` with keys `team_a`, `team_b`, `count`, `pct`
- JS uses `c.name`, `c.flag_emoji`, `c.tier`, `c.pick_pct`, `c.pick_count`, `c.group_score`, `c.ko_score`, `c.total_score`, `c.is_active` — all match service output
- Combo JS uses `combo.team_a`, `combo.team_b`, `combo.count`, `combo.pct` — matches service output
- Tier stats JS uses `TIER_STATS[t].avg_score`, `TIER_STATS[t].total_score`, `TIER_STATS[t].best_country`, `TIER_STATS[t].best_score` — matches service output
