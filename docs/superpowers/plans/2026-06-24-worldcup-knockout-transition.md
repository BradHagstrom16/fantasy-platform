# World Cup Knockout-Transition Trio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three group→knockout-transition features for the World Cup pool: a bulk "Load from API" bracket populator (+ rehearsal + tests), an admin-triggered group-stage recap email, and an Ideal Lineup card on the Stats Hub.

**Architecture:** All three are additive to the existing WC blueprint. Bracket population reuses the football-data.org sync service (`services/sync.py`) and the admin-confirmed `set_knockout_teams()` write path behind a new review-then-confirm route. The recap email mirrors the existing daily-digest service (`services/notifications.py`). The Ideal Lineup is a pure function over the `country_stats` the Stats route already builds.

**Tech Stack:** Flask blueprints, SQLAlchemy 2.0, Jinja2, Click CLI (`AppGroup`), pytest with `unittest.mock.patch`, football-data.org REST (mocked in tests).

**Spec:** `docs/superpowers/specs/2026-06-24-worldcup-knockout-transition-design.md`

## Global Constraints

- **Timestamps:** `datetime.now(timezone.utc)` — never `utcnow()`. WC app code reads "now" via `games.worldcup.services.state.now_utc()`.
- **Tier multipliers (exact):** T1 ×1.0 (pick 2), T2 ×1.5 (pick 1), T3 ×2.5 (pick 2), T4 ×4.0 (pick 2), T5 ×7.0 (pick 2). Total 9. Source: `world_cup_countries.py::TIERS`.
- **Advancement base points (exact):** group winner +4, runner-up +3, best-third +1. Source: `constants.py` (`ADVANCE_GROUP_WINNER/RUNNER_UP/BEST_THIRD`).
- **Knockout base points (exact):** R32 +8, R16 +11, QF +15, SF +19, third/runner-up +8, champion +50. Source: `constants.py::KNOCKOUT_POINTS`.
- **Competition rank:** `rank = 1 + count of enrollments scoring strictly higher` (ties share a rank). Reuse `notifications._competition_rank`.
- **Admin auth:** every admin route is decorated `@worldcup_admin_required` (platform admin OR enrollment admin). In tests, authenticate by setting `sess['_user_id'] = user.auth_id` (NOT `str(user.id)`).
- **CSRF:** all POST forms include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. Testing config disables CSRF, so a placeholder is fine.
- **Advancement & bracket stay admin-confirmed:** never auto-write advancement or bracket assignments. New flows are review-then-confirm; the existing per-shell `set_knockout.html` form stays as the manual override.
- **Flags:** render via `{% from '_flag.html' import flag with context %}` then `{{ flag(iso_code) }}`. Email flags: emails can't use the macro's `url_for` reliably — use absolute `<img>` with `site_url` (mirror existing email templates).
- **Email:** route through `utils.email.send_platform_email`; HTML emails use table layout + inline styles; always provide a plain-text fallback.
- **UI surfaces:** WC body sits on the Casual-Light pattern (white `.card`/`.wc-stat-card` on bone). Any player-facing UI task (the Ideal Lineup card) loads the `impeccable` skill and reads both top-level `DESIGN.md` and `games/worldcup/DESIGN.md`.
- **Commits:** end every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Run tests with:** `ENVIRONMENT=testing venv/bin/python -m pytest <path> -q`.

---

## File Structure

**Phase 1 — Bracket readiness**
- Modify `games/worldcup/services/sync.py` — add `fetch_bracket_proposal`, `all_group_advancement_confirmed`, `populatable_bracket_stages`.
- Modify `games/worldcup/routes.py` — add `admin_bracket` route; add `populatable_stages` to `admin_dashboard` context.
- Create `games/worldcup/templates/worldcup/admin/bracket.html` — review-then-confirm screen.
- Modify `games/worldcup/templates/worldcup/admin/dashboard.html` — "Populate <Round> from API" CTA.
- Modify `tests/test_worldcup_sync.py` — service tests.
- Create `tests/test_worldcup_bracket.py` — route tests.

**Phase 2 — Group-stage recap email**
- Modify `games/worldcup/services/notifications.py` — `send_group_stage_recap`, `_plain_group_recap`, marker helpers.
- Create `games/worldcup/templates/worldcup/email/wc_group_recap.j2`.
- Modify `games/worldcup/routes.py` — `admin_send_group_recap` route.
- Modify `games/worldcup/templates/worldcup/admin/dashboard.html` — recap button.
- Modify `games/worldcup/cli.py` — `send-group-recap` command.
- Create `tests/test_worldcup_group_recap.py`.

**Phase 3 — Ideal Lineup card**
- Modify `games/worldcup/services/stats.py` — `get_ideal_lineup`.
- Modify `games/worldcup/routes.py::stats` — pass `ideal_lineup`.
- Modify `games/worldcup/templates/worldcup/stats.html` — card (via impeccable).
- Modify `tests/test_worldcup_stats.py`.

**Phase 4 — Docs**
- Run `claude-md-management:claude-md-improver`; update `CLAUDE.md`.

---

# PHASE 1 — Knockout Bracket Readiness *(time-critical: land before ~June 28)*

### Task 1: `fetch_bracket_proposal(target_stage)` service

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

**Interfaces:**
- Consumes: existing `_api_get`, `_fifa_for_tla`, `_to_naive_utc`, `_parse_api_kickoff`, `STAGE_MAP`, `COMPETITION_CODE`, `SyncError` (all in `sync.py`).
- Produces: `fetch_bracket_proposal(target_stage: str) -> dict` returning
  `{'target_stage': str, 'proposals': list[dict], 'unresolved': list[dict], 'error': str | None}`
  where each proposal is `{'match_number', 'shell_id', 'home_fifa', 'away_fifa', 'home_name', 'away_name', 'current_home', 'current_away', 'already_set', 'is_completed'}`.

- [x] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py` (reuse the file's existing `app` fixture and `_API_MATCHES_FIXTURE` style — define a small inline KO fixture):

```python
def _ko_matches_payload():
    """Two LAST_32 fixtures, one fully resolved, one half-resolved."""
    return {'matches': [
        {'id': 9001, 'stage': 'LAST_32', 'utcDate': '2026-06-28T19:00:00Z',
         'homeTeam': {'tla': 'BRA', 'name': 'Brazil'},
         'awayTeam': {'tla': 'KSA', 'name': 'Saudi Arabia'}},
        {'id': 9002, 'stage': 'LAST_32', 'utcDate': '2026-06-28T23:00:00Z',
         'homeTeam': {'tla': 'ARG', 'name': 'Argentina'},
         'awayTeam': {'tla': None, 'name': None}},
    ]}


def test_fetch_bracket_proposal_maps_resolved_and_flags_unresolved(app):
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    from games.worldcup.services import sync
    with app.app_context():
        db.create_all()
        for code, name, grp in [('BRA', 'Brazil', 'A'), ('KSA', 'Saudi Arabia', 'A'),
                                ('ARG', 'Argentina', 'B')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter=grp))
        # Two R32 shells linked by api_fixture_id.
        db.session.add(WorldCupMatch(match_number=73, stage='R32', api_fixture_id=9001))
        db.session.add(WorldCupMatch(match_number=74, stage='R32', api_fixture_id=9002))
        db.session.commit()

        with patch.object(sync, '_api_get', return_value=_ko_matches_payload()):
            out = sync.fetch_bracket_proposal('R32')

        assert out['error'] is None
        assert len(out['proposals']) == 1
        p = out['proposals'][0]
        assert (p['match_number'], p['home_fifa'], p['away_fifa']) == (73, 'BRA', 'KSA')
        assert p['already_set'] is False
        # Match 74 has an unresolved away team -> reported, not proposed.
        assert any(u['match_number'] == 74 for u in out['unresolved'])


def test_fetch_bracket_proposal_rejects_non_ko_stage(app):
    from games.worldcup.services import sync
    with app.app_context():
        db.create_all()
        out = sync.fetch_bracket_proposal('group')
        assert out['error'] is not None
        assert out['proposals'] == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py::test_fetch_bracket_proposal_maps_resolved_and_flags_unresolved tests/test_worldcup_sync.py::test_fetch_bracket_proposal_rejects_non_ko_stage -q`
Expected: FAIL (`AttributeError: module ... has no attribute 'fetch_bracket_proposal'`).

- [x] **Step 3: Implement `fetch_bracket_proposal`**

Add to `games/worldcup/services/sync.py` (after `fetch_advancement_proposal`):

```python
KO_STAGES = ('R32', 'R16', 'QF', 'SF', 'final', 'third_place')


def fetch_bracket_proposal(target_stage: str) -> dict:
    """Read-only proposed team assignments for every shell of target_stage.

    Reads the /matches feed, filters to target_stage, maps each API fixture to
    our shell (by api_fixture_id, else by (stage, kickoff)), and proposes
    home/away from the API's resolved teams. Never writes. Shells the API has
    not yet resolved (or that no fixture matched) are reported in 'unresolved'
    for admin review, never guessed.
    """
    if target_stage not in KO_STAGES:
        return {'target_stage': target_stage, 'proposals': [], 'unresolved': [],
                'error': f'Not a knockout stage: {target_stage}'}

    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    shells = WorldCupMatch.query.filter_by(stage=target_stage).all()
    by_fixture = {m.api_fixture_id: m for m in shells if m.api_fixture_id}
    by_kick = {_to_naive_utc(m.kickoff_utc): m for m in shells if m.kickoff_utc}

    proposals = []
    unresolved = []
    matched_ids = set()
    for f in data.get('matches', []):
        if STAGE_MAP.get(f.get('stage')) != target_stage:
            continue
        shell = by_fixture.get(f.get('id')) or by_kick.get(_parse_api_kickoff(f['utcDate']))
        if not shell:
            continue
        matched_ids.add(shell.id)
        home = _fifa_for_tla((f.get('homeTeam') or {}).get('tla'))
        away = _fifa_for_tla((f.get('awayTeam') or {}).get('tla'))
        if not home or not away:
            unresolved.append({'match_number': shell.match_number,
                               'reason': 'API has not resolved both teams yet'})
            continue
        teams = {t.fifa_code: t for t in WorldCupTeam.query.filter(
            WorldCupTeam.fifa_code.in_([home, away])).all()}
        proposals.append({
            'match_number': shell.match_number,
            'shell_id': shell.id,
            'home_fifa': home,
            'away_fifa': away,
            'home_name': teams[home].display_name if home in teams else home,
            'away_name': teams[away].display_name if away in teams else away,
            'current_home': shell.home_team.fifa_code if shell.home_team else None,
            'current_away': shell.away_team.fifa_code if shell.away_team else None,
            'already_set': bool(shell.home_team_id and shell.away_team_id),
            'is_completed': bool(shell.is_completed),
        })

    for shell in shells:
        if shell.id not in matched_ids:
            unresolved.append({'match_number': shell.match_number,
                               'reason': 'no API fixture matched this shell'})

    return {
        'target_stage': target_stage,
        'proposals': sorted(proposals, key=lambda p: p['match_number']),
        'unresolved': sorted(unresolved, key=lambda u: u['match_number']),
        'error': None,
    }
```

- [x] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k fetch_bracket_proposal -q`
Expected: PASS (2 tests).

- [x] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): fetch_bracket_proposal for bulk KO populate"
```

---

### Task 2: `all_group_advancement_confirmed` + `populatable_bracket_stages`

**Files:**
- Modify: `games/worldcup/services/sync.py`
- Test: `tests/test_worldcup_sync.py`

**Interfaces:**
- Consumes: existing `ko_round_pending()`, `WorldCupMatch`, `WorldCupTeam`, `db`.
- Produces:
  - `all_group_advancement_confirmed() -> bool` — group stage complete AND every non-eliminated team has an `advancement_method`.
  - `populatable_bracket_stages() -> list[str]` — KO stages whose shells are empty and whose feeder round is resolved (e.g. `['R32']`, or `['final', 'third_place']`).

- [x] **Step 1: Write the failing test**

Add to `tests/test_worldcup_sync.py`:

```python
def test_all_group_advancement_confirmed(app):
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    from games.worldcup.services import sync
    with app.app_context():
        db.create_all()
        # One group match, completed.
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        # Two teams: one advancing, one eliminated -> fully resolved.
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    advancement_method='group_winner'))
        db.session.add(WorldCupTeam(fifa_code='KSA', name='Saudi Arabia', display_name='Saudi Arabia',
                                    tier=5, multiplier=7.0, confederation='X', group_letter='A',
                                    is_eliminated=True))
        db.session.commit()
        assert sync.all_group_advancement_confirmed() is True

        # Add an unconfirmed team (no method, not eliminated) -> not confirmed.
        db.session.add(WorldCupTeam(fifa_code='ARG', name='Argentina', display_name='Argentina',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        db.session.commit()
        assert sync.all_group_advancement_confirmed() is False


def test_populatable_bracket_stages_offers_r32_after_advancement(app):
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    from games.worldcup.services import sync
    with app.app_context():
        db.create_all()
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    advancement_method='group_winner'))
        # An empty R32 shell.
        db.session.add(WorldCupMatch(match_number=73, stage='R32'))
        db.session.commit()
        assert 'R32' in sync.populatable_bracket_stages()
```

- [x] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "all_group_advancement_confirmed or populatable_bracket" -q`
Expected: FAIL (`AttributeError`).

- [x] **Step 3: Implement both helpers**

Add to `games/worldcup/services/sync.py` (near `group_stage_complete_and_unconfirmed`):

```python
def all_group_advancement_confirmed() -> bool:
    """True when group stage is complete AND every group's advancement is set."""
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
    return unconfirmed == 0


def populatable_bracket_stages() -> list[str]:
    """KO stages whose shells are empty and whose feeder round is resolved."""
    def has_empty(stage: str) -> bool:
        return (
            WorldCupMatch.query.filter_by(stage=stage)
            .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                           WorldCupMatch.away_team_id.is_(None)))
            .count() > 0
        )

    stages: list[str] = []
    if all_group_advancement_confirmed() and has_empty('R32'):
        stages.append('R32')

    src = ko_round_pending()  # source stage complete, downstream empty
    if src:
        downstream = ['final', 'third_place'] if src == 'SF' else [{'R32': 'R16', 'R16': 'QF', 'QF': 'SF'}[src]]
        for ds in downstream:
            if has_empty(ds) and ds not in stages:
                stages.append(ds)
    return stages
```

- [x] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py -k "all_group_advancement_confirmed or populatable_bracket" -q`
Expected: PASS (2 tests).

- [x] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py tests/test_worldcup_sync.py
git commit -m "feat(worldcup): advancement-confirmed + populatable-stages helpers"
```

---

### Task 3: Admin bracket review-then-confirm route

**Files:**
- Modify: `games/worldcup/routes.py`
- Test: `tests/test_worldcup_bracket.py` (create)

**Interfaces:**
- Consumes: `fetch_bracket_proposal`, `populatable_bracket_stages` (Tasks 1–2), `set_knockout_teams` (already imported in routes), `worldcup_admin_required`, `SyncError`.
- Produces: route `worldcup.admin_bracket` at `/admin/bracket/<target_stage>` (GET renders review; POST assigns).

- [x] **Step 1: Write the failing test**

Create `tests/test_worldcup_bracket.py`:

```python
"""Admin bulk bracket populate (review-then-confirm)."""
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
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
def client(app):
    return app.test_client()


def _make_admin(app):
    with app.app_context():
        u = User(username='boss', email='boss@test.com', is_admin=True)
        u.set_password('x')
        db.session.add(u)
        db.session.commit()
        return u.auth_id


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def test_admin_bracket_requires_admin(client):
    resp = client.get('/worldcup/admin/bracket/R32')
    assert resp.status_code in (302, 401, 403)


def test_admin_bracket_get_renders_proposal(client, app):
    auth_id = _make_admin(app)
    _login(client, auth_id)
    fake = {'target_stage': 'R32', 'error': None, 'unresolved': [],
            'proposals': [{'match_number': 73, 'shell_id': 1, 'home_fifa': 'BRA',
                           'away_fifa': 'KSA', 'home_name': 'Brazil', 'away_name': 'Saudi Arabia',
                           'current_home': None, 'current_away': None,
                           'already_set': False, 'is_completed': False}]}
    with patch('games.worldcup.routes.fetch_bracket_proposal', return_value=fake):
        resp = client.get('/worldcup/admin/bracket/R32')
    assert resp.status_code == 200
    assert b'BRA' in resp.data and b'KSA' in resp.data


def test_admin_bracket_post_assigns_shells(client, app):
    auth_id = _make_admin(app)
    with app.app_context():
        for code, name in [('BRA', 'Brazil'), ('KSA', 'Saudi Arabia')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        shell = WorldCupMatch(match_number=73, stage='R32')
        db.session.add(shell)
        db.session.commit()
        shell_id = shell.id
    _login(client, auth_id)
    resp = client.post('/worldcup/admin/bracket/R32', data={
        'csrf_token': 'x',
        'shell_id': str(shell_id), 'home_fifa': 'BRA', 'away_fifa': 'KSA',
    }, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        s = db.session.get(WorldCupMatch, shell_id)
        assert s.home_team.fifa_code == 'BRA'
        assert s.away_team.fifa_code == 'KSA'


def test_admin_bracket_post_skips_completed_shell(client, app):
    auth_id = _make_admin(app)
    with app.app_context():
        for code, name in [('BRA', 'Brazil'), ('KSA', 'Saudi Arabia')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        shell = WorldCupMatch(match_number=73, stage='R32', is_completed=True)
        db.session.add(shell)
        db.session.commit()
        shell_id = shell.id
    _login(client, auth_id)
    client.post('/worldcup/admin/bracket/R32', data={
        'csrf_token': 'x',
        'shell_id': str(shell_id), 'home_fifa': 'BRA', 'away_fifa': 'KSA',
    })
    with app.app_context():
        s = db.session.get(WorldCupMatch, shell_id)
        assert s.home_team_id is None  # completed shell left untouched
```

- [x] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket.py -q`
Expected: FAIL (404 on the route; route not defined).

- [x] **Step 3: Implement the route**

In `games/worldcup/routes.py`, add the import near the existing sync import (top of file has `from games.worldcup.services.sync import fetch_advancement_proposal`):

```python
from games.worldcup.services.sync import (
    fetch_advancement_proposal, fetch_bracket_proposal,
    populatable_bracket_stages, SyncError,
)
```

(Replace the existing single-name import line with this grouped one.)

Add the route after `admin_set_knockout`:

```python
@worldcup_bp.route('/admin/bracket/<target_stage>', methods=['GET', 'POST'])
@worldcup_admin_required
def admin_bracket(target_stage):
    """Bulk-populate one knockout round's shells from the API (review-then-confirm)."""
    KO_STAGES = ('R32', 'R16', 'QF', 'SF', 'final', 'third_place')
    if target_stage not in KO_STAGES:
        flash('Not a knockout stage.', 'error')
        return redirect(url_for('worldcup.admin_dashboard'))

    if request.method == 'POST':
        shell_ids = request.form.getlist('shell_id')
        home_fifas = request.form.getlist('home_fifa')
        away_fifas = request.form.getlist('away_fifa')
        assigned = skipped = failed = 0
        for sid, home, away in zip(shell_ids, home_fifas, away_fifas):
            shell = db.session.get(WorldCupMatch, int(sid)) if sid.isdigit() else None
            if not shell or shell.is_completed:
                skipped += 1
                continue
            res = set_knockout_teams(shell.id, home, away)
            if 'error' in res:
                failed += 1
            else:
                assigned += 1
        flash(
            f'{target_stage}: {assigned} assigned, {skipped} skipped, {failed} failed.',
            'warning' if failed else 'success',
        )
        return redirect(url_for('worldcup.admin_dashboard'))

    try:
        proposal = fetch_bracket_proposal(target_stage)
    except SyncError as exc:
        flash(f'Could not load bracket from API: {exc}', 'error')
        return redirect(url_for('worldcup.admin_dashboard'))
    return render_template('worldcup/admin/bracket.html',
        proposal=proposal, target_stage=target_stage)
```

- [x] **Step 4: Run test to verify it fails on template, then continue**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket.py -q`
Expected: the POST/skip/auth tests PASS; `test_admin_bracket_get_renders_proposal` FAILS with `TemplateNotFound: worldcup/admin/bracket.html`. Proceed to Task 4 (the GET test passes once the template exists).

- [x] **Step 5: Commit (route only)**

```bash
git add games/worldcup/routes.py tests/test_worldcup_bracket.py
git commit -m "feat(worldcup): admin bracket review-then-confirm route"
```

---

### Task 4: Bracket review template

**Files:**
- Create: `games/worldcup/templates/worldcup/admin/bracket.html`
- Test: `tests/test_worldcup_bracket.py::test_admin_bracket_get_renders_proposal` (from Task 3)

**Interfaces:**
- Consumes: `proposal` dict + `target_stage` (Task 3); `stage_label()` (global via context processor); `csrf_token()`.

- [x] **Step 1: Create the template**

Mirror the existing `admin/set_knockout.html` masthead/card structure. Create `games/worldcup/templates/worldcup/admin/bracket.html`:

```jinja
{% extends "base.html" %}
{% block title %}Populate {{ stage_label(target_stage) }} · World Cup Admin{% endblock %}

{% block content %}
<header class="admin-masthead">
    <div class="container">
        <a href="{{ url_for('worldcup.admin_dashboard') }}" class="adm-back">&larr; Tournament Control</a>
        <span class="admin-eyebrow">World Cup &middot; Bracket</span>
        <h1 class="admin-page-title">Populate {{ stage_label(target_stage) }}</h1>
        <p class="admin-masthead-sub">Proposed from football-data.org. Review, then confirm to assign every shell at once.</p>
    </div>
</header>

<div class="container pb-5">
    <div class="card" style="max-width:840px">
        <div class="card-body">
            {% if proposal.proposals %}
            <form method="POST" action="{{ url_for('worldcup.admin_bracket', target_stage=target_stage) }}"
                  onsubmit="return confirm('Assign all {{ proposal.proposals|length }} {{ stage_label(target_stage) }} shells?');">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <table class="table">
                    <thead><tr><th>Match</th><th>Proposed</th><th>Currently</th></tr></thead>
                    <tbody>
                    {% for p in proposal.proposals %}
                    <tr {% if p.is_completed %}class="adm-tag--muted"{% endif %}>
                        <td>#{{ p.match_number }}</td>
                        <td>
                            <input type="hidden" name="shell_id" value="{{ p.shell_id }}">
                            <input type="hidden" name="home_fifa" value="{{ p.home_fifa }}">
                            <input type="hidden" name="away_fifa" value="{{ p.away_fifa }}">
                            <strong>{{ p.home_fifa }}</strong> v <strong>{{ p.away_fifa }}</strong>
                            <span class="adm-sub d-block">{{ p.home_name }} v {{ p.away_name }}</span>
                        </td>
                        <td>
                            {% if p.current_home or p.current_away %}{{ p.current_home or 'TBD' }} v {{ p.current_away or 'TBD' }}
                            {% else %}<span class="adm-sub">empty</span>{% endif %}
                            {% if p.is_completed %} &middot; <span class="adm-tag adm-tag--muted">result locked</span>{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
                <button type="submit" class="btn btn-game">Confirm &amp; Assign</button>
                <a href="{{ url_for('worldcup.admin_dashboard') }}" class="btn btn-outline-secondary ms-2">Cancel</a>
            </form>
            {% else %}
            <p class="adm-sub">No resolvable pairings for {{ stage_label(target_stage) }} yet.</p>
            {% endif %}

            {% if proposal.unresolved %}
            <hr class="my-4">
            <p class="adm-masthead-sub mb-2">Not yet resolved by the API ({{ proposal.unresolved|length }}):</p>
            <ul class="adm-sub">
                {% for u in proposal.unresolved %}
                <li>#{{ u.match_number }} — {{ u.reason }}
                    (<a href="{{ url_for('worldcup.admin_set_knockout', match_id=u.match_number) }}">assign manually</a>)</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
```

Note: the manual-assign link uses `match_number` as a convenience; if `admin_set_knockout` needs the DB id, drop the link rather than mislink — match_number ≠ id. Verify against the route signature (`admin_set_knockout` takes `match_id`); if they differ in your data, render the unresolved rows without the manual link.

- [x] **Step 2: Run the GET test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket.py -q`
Expected: PASS (all 4 tests).

- [x] **Step 3: Commit**

```bash
git add games/worldcup/templates/worldcup/admin/bracket.html
git commit -m "feat(worldcup): bracket review template"
```

---

### Task 5: Dashboard "Populate <Round> from API" CTA

**Files:**
- Modify: `games/worldcup/routes.py::admin_dashboard`
- Modify: `games/worldcup/templates/worldcup/admin/dashboard.html`
- Test: `tests/test_worldcup_bracket.py`

**Interfaces:**
- Consumes: `populatable_bracket_stages` (Task 2).
- Produces: `populatable_stages` in the dashboard context; a CTA block in the template.

- [x] **Step 1: Write the failing test**

Add to `tests/test_worldcup_bracket.py`:

```python
def test_dashboard_shows_populate_cta_when_stage_ready(client, app):
    auth_id = _make_admin(app)
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    advancement_method='group_winner'))
        db.session.add(WorldCupMatch(match_number=73, stage='R32'))
        db.session.commit()
    _login(client, auth_id)
    resp = client.get('/worldcup/admin/')
    assert resp.status_code == 200
    assert b'/worldcup/admin/bracket/R32' in resp.data
```

- [x] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket.py::test_dashboard_shows_populate_cta_when_stage_ready -q`
Expected: FAIL (link not present).

- [x] **Step 3: Add context var to the route**

In `games/worldcup/routes.py::admin_dashboard`, before the `return render_template(...)`, add:

```python
    populatable_stages = populatable_bracket_stages()
```

and add to the `render_template('worldcup/admin/dashboard.html', ...)` kwargs:

```python
        populatable_stages=populatable_stages,
```

- [x] **Step 4: Add the CTA to the template**

In `games/worldcup/templates/worldcup/admin/dashboard.html`, immediately before the `{% if knockout_unassigned %}` block (around line 190), insert:

```jinja
    {% if populatable_stages %}
    <h2 class="section-heading">Populate the Bracket</h2>
    <p class="adm-sub mb-2">The feeder round is resolved — pull this round's pairings from the API and confirm.</p>
    <div class="adm-action-row mb-4">
        {% for stage in populatable_stages %}
        <a href="{{ url_for('worldcup.admin_bracket', target_stage=stage) }}" class="btn btn-game btn-sm">
            Populate {{ stage_label(stage) }} from API
        </a>
        {% endfor %}
    </div>
    {% endif %}
```

- [x] **Step 5: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket.py -q`
Expected: PASS (all 5 tests).

- [x] **Step 6: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/admin/dashboard.html tests/test_worldcup_bracket.py
git commit -m "feat(worldcup): dashboard populate-bracket CTA"
```

---

### Task 6: Rehearsal on local DB + restore to live

**Files:** none (verification task). Run against `ccc_local` (the dev Postgres, freely manipulable).

**Goal:** Prove the advancement → bulk-populate → KO-scoring loop end-to-end, then leave the DB in a LIVE state (mirrors prod).

- [x] **Step 1: Snapshot current state** so you can restore. Run: `ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup status` and note the phase.

- [x] **Step 2: Drive group stage to done.** If not already, `ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup simulate-group-stage` then confirm advancement for all 12 groups at `/worldcup/admin/advancement` (use "Load from API" against the live feed, or set manually). Verify `flask worldcup status` shows group stage complete.

- [x] **Step 3: Populate R32.** Visit `/worldcup/admin/` — confirm the "Populate Round of 32 from API" CTA appears, click it, review, confirm. Verify all R32 shells now have teams (no `knockout_unassigned` R32 rows).

- [x] **Step 4: Simulate R32 results + verify scoring.** Enter results for the R32 matches (`flask worldcup process-match ...` or the admin result page), then confirm scores recalc and KO points apply (R32 = 8 × multiplier). Spot-check a team's `team_detail` page.

- [x] **Step 5: Repeat for R16 → QF → SF → final/third_place** to confirm the CTA chains correctly round to round.

- [x] **Step 6: Restore to LIVE.** Walk the DB back to a live, mid-tournament state mirroring prod (group stage in progress / early knockouts) so local matches production. Per [[project_ccc_local_db_completed_state]]: clearing the final match → 'knockout'/live; clearing KO+final → 'group_stage'. Confirm `flask worldcup status` reflects a live phase. **Do not leave it completed.**

- [x] **Step 7: Full suite green.** Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_sync.py tests/test_worldcup_bracket.py -q`. Expected: all PASS.

**This is the end of Phase 1 — open the PR for Feature 2, carry it through CodeRabbit to merge before continuing.**

---

# PHASE 2 — Group-Stage Recap Email

### Task 7: `send_group_stage_recap` service + plain-text fallback

**Files:**
- Modify: `games/worldcup/services/notifications.py`
- Test: `tests/test_worldcup_group_recap.py` (create)

**Interfaces:**
- Consumes: `all_group_advancement_confirmed` (Task 2), `_competition_rank`, `_fmt_pts`, `_fmt_multiplier`, `_asset_version` (existing in notifications), `send_platform_email`, `ADVANCE_GROUP_WINNER/RUNNER_UP/BEST_THIRD` (constants), `KNOCKOUT_POINTS` (constants), `TIERS`.
- Produces: `send_group_stage_recap() -> dict` with keys `status` (`'sent' | 'blocked' | 'no_sends'`), `sent`, `skipped_no_email`, `errors`, plus `reason` when blocked.

- [ ] **Step 1: Write the failing test**

Create `tests/test_worldcup_group_recap.py`:

```python
"""Group-stage recap email."""
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
)
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _team(code, name, tier, mult, grp, **kw):
    t = WorldCupTeam(fifa_code=code, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='X', group_letter=grp, **kw)
    db.session.add(t)
    db.session.flush()
    return t


def test_recap_blocked_when_advancement_unconfirmed(app):
    from games.worldcup.services.notifications import send_group_stage_recap
    with app.app_context():
        # No completed group matches -> not confirmed.
        out = send_group_stage_recap()
        assert out['status'] == 'blocked'


def test_recap_sends_with_advancement_breakdown(app):
    from games.worldcup.services.notifications import send_group_stage_recap
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        winner = _team('BRA', 'Brazil', 1, 1.0, 'A', advancement_method='group_winner')
        wild = _team('KSA', 'Saudi Arabia', 5, 7.0, 'A', advancement_method='best_third')
        out_team = _team('SRB', 'Serbia', 4, 4.0, 'A', is_eliminated=True)
        u = User(username='al', email='al@test.com'); u.set_password('x')
        db.session.add(u); db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e); db.session.flush()
        for t in (winner, wild, out_team):
            db.session.add(WorldCupPick(enrollment_id=e.id, team_id=t.id, tier=t.tier))
        db.session.commit()

        with patch('games.worldcup.services.notifications.send_platform_email',
                   return_value=True) as send:
            out = send_group_stage_recap()
        assert out['status'] == 'sent'
        assert out['sent'] == 1
        # Email body mentions advancement points: winner +4, best-third 1*7=7.
        html = send.call_args[0][3]
        assert 'Brazil' in html and 'Saudi Arabia' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -q`
Expected: FAIL (`ImportError: cannot import name 'send_group_stage_recap'`).

- [ ] **Step 3: Implement the service**

Add to `games/worldcup/services/notifications.py`. First extend the imports at the top:

```python
from games.worldcup.constants import (
    SEASON_YEAR, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
    ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD, KNOCKOUT_POINTS,
)
from games.worldcup.services.sync import all_group_advancement_confirmed
```

(Add the new names to the existing `constants` import; add the `sync` import line.)

Then add the service:

```python
_ADV_LABEL = {'group_winner': 'Group winner', 'runner_up': 'Runner-up', 'best_third': 'Best 3rd place'}
_ADV_BASE = {'group_winner': ADVANCE_GROUP_WINNER, 'runner_up': ADVANCE_RUNNER_UP, 'best_third': ADVANCE_BEST_THIRD}

# Multiplied knockout ladder for the "what's at stake" section.
_KO_LADDER = [('Round of 32', 'R32'), ('Round of 16', 'R16'), ('Quarterfinal', 'QF'),
              ('Semifinal', 'SF'), ('Final / 3rd place', 'runner_up'), ('Champion', 'champion')]


def _recap_rows(enrollment):
    """(advanced_rows, eliminated_rows, total_adv_pts) for one enrollment.

    advanced_rows: dicts with team, method_label, base, multiplier, points (multiplied).
    eliminated_rows: dicts with team.
    """
    advanced, eliminated, total = [], [], 0.0
    for pick in sorted(enrollment.picks, key=lambda p: (p.team.tier, p.team.display_name)):
        t = pick.team
        if t.advancement_method:
            base = _ADV_BASE.get(t.advancement_method, 0)
            pts = base * t.multiplier
            total += pts
            advanced.append({'team': t, 'method_label': _ADV_LABEL.get(t.advancement_method, t.advancement_method),
                             'base': base, 'multiplier': t.multiplier, 'points': pts})
        elif t.is_eliminated:
            eliminated.append({'team': t})
    return advanced, eliminated, total


def send_group_stage_recap() -> dict:
    """Email each player a personalized group-stage recap. Admin-triggered.

    Guarded: refuses unless every group's advancement is confirmed. Mirrors
    send_daily_digests structure; one email per enrolled, picks-submitted player
    with an address.
    """
    if not all_group_advancement_confirmed():
        return {'status': 'blocked', 'reason': 'group advancement not fully confirmed'}

    site_url = current_app.config.get('SITE_URL', 'https://cccfantasy.com').rstrip('/')
    logo_url = f'{site_url}/static/img/logo/ccc-logo-stacked.svg'
    av = _asset_version()
    ko_ladder = [(label, KNOCKOUT_POINTS[key]) for label, key in _KO_LADDER]

    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR, picks_submitted=True)
        .all()
    )
    total_enrolled = len(enrollments)
    sent = skipped_no_email = errors = 0

    for enrollment in enrollments:
        if not enrollment.user or not enrollment.user.email:
            skipped_no_email += 1
            continue
        advanced, eliminated, total_adv = _recap_rows(enrollment)
        rank, _ = _competition_rank(enrollment)
        try:
            html_body = render_template(
                'worldcup/email/wc_group_recap.j2',
                enrollment=enrollment, advanced=advanced, eliminated=eliminated,
                total_adv_str=_fmt_pts(total_adv), total_score_str=_fmt_pts(float(enrollment.total_score)),
                rank=rank, total_enrolled=total_enrolled, ko_ladder=ko_ladder,
                site_url=site_url, logo_url=logo_url, asset_version=av,
                fmt_mult=_fmt_multiplier, fmt_pts=_fmt_pts,
            )
            plain_body = _plain_group_recap(enrollment, advanced, eliminated,
                                            _fmt_pts(total_adv), rank, total_enrolled, site_url)
            subject = 'World Cup: the group stage is a wrap'
            if send_platform_email(enrollment.user.email, subject, plain_body, html_body):
                sent += 1
            else:
                errors += 1
        except Exception:
            logger.exception('Group recap failed for enrollment %s', enrollment.id)
            errors += 1

    _mark_group_recap_sent()
    return {'status': 'sent' if sent else 'no_sends',
            'sent': sent, 'skipped_no_email': skipped_no_email, 'errors': errors}


def _plain_group_recap(enrollment, advanced, eliminated, total_adv_str, rank, total_enrolled, site_url):
    name = enrollment.get_display_name()
    lines = ['The group stage is a wrap', '=' * 40, '', f'Hi {name},', '',
             f'Group advancement points earned: +{total_adv_str}', '',
             'Your teams that advanced:', '-' * 36]
    for r in advanced:
        lines.append(f"  {r['team'].display_name} ({_fmt_multiplier(r['multiplier'])})"
                     f"  {r['method_label']}  +{_fmt_pts(r['points'])} pts")
    if eliminated:
        lines += ['', 'Out after the group stage:']
        for r in eliminated:
            lines.append(f"  {r['team'].display_name}")
    lines += ['', 'How group points worked: Group winner +4, Runner-up +3, Best 3rd +1 '
              '(x your tier multiplier).', '',
              f'Standing entering the Round of 32: #{rank} of {total_enrolled}', '',
              f'Full standings: {site_url}/worldcup/leaderboard', '',
              'Corrupt Commish Club -- cccfantasy.com']
    return '\n'.join(lines)
```

Also add the marker helpers near `_asset_version`:

```python
def _group_recap_marker_path() -> str:
    return os.path.join(current_app.instance_path, '.wc_group_recap_sent')


def group_recap_last_sent() -> str | None:
    """Return the ISO date string of the last recap send, or None."""
    try:
        with open(_group_recap_marker_path()) as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _mark_group_recap_sent() -> None:
    try:
        os.makedirs(current_app.instance_path, exist_ok=True)
        with open(_group_recap_marker_path(), 'w') as fh:
            fh.write(now_utc().astimezone(WORLDCUP_TZ).strftime('%Y-%m-%d'))
    except OSError:
        logger.warning('Could not write group-recap marker.')
```

- [ ] **Step 4: Run test (expect template error next)**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -q`
Expected: `test_recap_blocked_when_advancement_unconfirmed` PASSES; `test_recap_sends_with_advancement_breakdown` FAILS with `TemplateNotFound: worldcup/email/wc_group_recap.j2`. Proceed to Task 8.

- [ ] **Step 5: Commit (service only)**

```bash
git add games/worldcup/services/notifications.py tests/test_worldcup_group_recap.py
git commit -m "feat(worldcup): group-stage recap service + guard + marker"
```

---

### Task 8: Recap email template

**Files:**
- Create: `games/worldcup/templates/worldcup/email/wc_group_recap.j2`
- Test: `tests/test_worldcup_group_recap.py::test_recap_sends_with_advancement_breakdown`

**Interfaces:**
- Consumes: `enrollment, advanced, eliminated, total_adv_str, total_score_str, rank, total_enrolled, ko_ladder, site_url, logo_url, asset_version, fmt_mult, fmt_pts` (Task 7).

- [ ] **Step 1: Read the existing digest template** `games/worldcup/templates/worldcup/email/wc_daily_digest.j2` to copy its outer table shell, header (logo via `logo_url`), and footer (table layout + inline styles). Reuse that chrome verbatim; only the body section differs.

- [ ] **Step 2: Create the template** with the digest's header/footer chrome and this body:

```jinja
{# Group-stage recap. Reuses the wc_daily_digest.j2 table shell + header/footer. #}
<tr><td style="padding:24px 32px;">
  <h1 style="margin:0 0 8px;font-size:22px;color:#001A4D;">The group stage is a wrap</h1>
  <p style="margin:0 0 20px;font-size:15px;color:#5A5470;">
    Hi {{ enrollment.get_display_name() }} — here's how your roster came through the groups,
    and where you stand heading into the Round of 32.
  </p>

  <p style="margin:0 0 6px;font-size:13px;color:#5A5470;text-transform:uppercase;letter-spacing:.04em;">
    Group advancement points earned
  </p>
  <p style="margin:0 0 20px;font-size:28px;font-weight:700;color:#BF0A30;">+{{ total_adv_str }}</p>

  <p style="margin:0 0 8px;font-size:13px;color:#5A5470;text-transform:uppercase;letter-spacing:.04em;">
    Your teams that advanced
  </p>
  <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:20px;">
    {% for r in advanced %}
    <tr>
      <td style="padding:8px 0;border-bottom:1px solid #eee;font-size:15px;color:#001A4D;">
        <strong>{{ r.team.display_name }}</strong>
        <span style="color:#5A5470;">{{ fmt_mult(r.multiplier) }}</span><br>
        <span style="font-size:13px;color:#5A5470;">{{ r.method_label }} (+{{ r.base }} base)</span>
      </td>
      <td style="padding:8px 0;border-bottom:1px solid #eee;text-align:right;font-size:15px;font-weight:700;color:#BF0A30;">
        +{{ fmt_pts(r.points) }}
      </td>
    </tr>
    {% endfor %}
  </table>

  {% if eliminated %}
  <p style="margin:0 0 8px;font-size:13px;color:#5A5470;text-transform:uppercase;letter-spacing:.04em;">
    Out after the groups
  </p>
  <p style="margin:0 0 20px;font-size:15px;color:#8A849B;">
    {% for r in eliminated %}{{ r.team.display_name }}{% if not loop.last %} · {% endif %}{% endfor %}
  </p>
  {% endif %}

  <div style="background:#f6f5f8;border-radius:8px;padding:16px;margin-bottom:20px;">
    <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#001A4D;">How group points worked</p>
    <p style="margin:0;font-size:14px;color:#5A5470;">
      Group winner +4 · Runner-up +3 · Best 3rd +1 — each multiplied by your tier multiplier.
    </p>
  </div>

  <p style="margin:0 0 4px;font-size:13px;color:#5A5470;text-transform:uppercase;letter-spacing:.04em;">
    Entering the Round of 32
  </p>
  <p style="margin:0 0 20px;font-size:18px;color:#001A4D;">
    <strong>{{ total_score_str }} pts</strong> · #{{ rank }} of {{ total_enrolled }}
  </p>

  <p style="margin:0 0 8px;font-size:13px;color:#5A5470;text-transform:uppercase;letter-spacing:.04em;">
    What's at stake next (× your multiplier)
  </p>
  <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:20px;">
    {% for label, base in ko_ladder %}
    <tr>
      <td style="padding:4px 0;font-size:14px;color:#001A4D;">{{ label }}</td>
      <td style="padding:4px 0;text-align:right;font-size:14px;color:#5A5470;">+{{ base }} base</td>
    </tr>
    {% endfor %}
  </table>
  <p style="margin:0 0 24px;font-size:14px;color:#5A5470;">
    Your surviving high-multiplier picks carry the biggest upside from here.
  </p>

  <a href="{{ site_url }}/worldcup/leaderboard"
     style="display:inline-block;background:#BF0A30;color:#fff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:700;">
    View the standings
  </a>
</td></tr>
```

- [ ] **Step 3: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -q`
Expected: PASS (both tests).

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/templates/worldcup/email/wc_group_recap.j2
git commit -m "feat(worldcup): group-recap email template"
```

---

### Task 9: Admin "Send group recap" route + dashboard button

**Files:**
- Modify: `games/worldcup/routes.py`
- Modify: `games/worldcup/templates/worldcup/admin/dashboard.html`
- Test: `tests/test_worldcup_group_recap.py`

**Interfaces:**
- Consumes: `send_group_stage_recap`, `group_recap_last_sent`, `all_group_advancement_confirmed`.
- Produces: route `worldcup.admin_send_group_recap` (POST) at `/admin/send-group-recap`; `recap_last_sent` + `recap_ready` in dashboard context.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_group_recap.py` (reuse `client`/`_make_admin`/`_login` pattern from `tests/test_worldcup_bracket.py` — copy those fixtures in):

```python
def test_send_group_recap_route_admin_only(app):
    client = app.test_client()
    resp = client.post('/worldcup/admin/send-group-recap', data={'csrf_token': 'x'})
    assert resp.status_code in (302, 401, 403)


def test_send_group_recap_route_invokes_service(app):
    client = app.test_client()
    with app.app_context():
        u = User(username='boss', email='boss@test.com', is_admin=True); u.set_password('x')
        db.session.add(u); db.session.commit()
        auth_id = u.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.send_group_stage_recap',
               return_value={'status': 'sent', 'sent': 3, 'skipped_no_email': 0, 'errors': 0}) as svc:
        resp = client.post('/worldcup/admin/send-group-recap', data={'csrf_token': 'x'})
    assert resp.status_code == 302
    svc.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -k send_group_recap_route -q`
Expected: FAIL (404).

- [ ] **Step 3: Implement the route**

In `games/worldcup/routes.py`, add to the notifications import (find the existing `from games.worldcup.services.notifications import ...`, or add one):

```python
from games.worldcup.services.notifications import (
    send_group_stage_recap, group_recap_last_sent,
)
```

Add the route after `admin_recalc`:

```python
@worldcup_bp.route('/admin/send-group-recap', methods=['POST'])
@worldcup_admin_required
def admin_send_group_recap():
    """Send the personalized group-stage recap email to all players (guarded)."""
    result = send_group_stage_recap()
    if result['status'] == 'blocked':
        flash('Group advancement is not fully confirmed yet — confirm all 12 groups first.', 'error')
    elif result['status'] == 'sent':
        flash(f"Group recap sent to {result['sent']} player(s) "
              f"({result.get('errors', 0)} error(s)).", 'success')
    else:
        flash('No recap emails were sent (no eligible players).', 'warning')
    return redirect(url_for('worldcup.admin_dashboard'))
```

- [ ] **Step 4: Add the button to the dashboard**

In `games/worldcup/routes.py::admin_dashboard`, add context:

```python
    recap_ready = all_group_advancement_confirmed()
    recap_last_sent = group_recap_last_sent()
```

(`all_group_advancement_confirmed` is already importable via the grouped sync import from Task 3; add `all_group_advancement_confirmed` to that import.) Pass both into `render_template`.

In `dashboard.html`, after the "Populate the Bracket" block, add:

```jinja
    {% if recap_ready %}
    <h2 class="section-heading">Group-Stage Recap Email</h2>
    <form method="POST" action="{{ url_for('worldcup.admin_send_group_recap') }}"
          onsubmit="return confirm('Send the group-stage recap to every player now?');">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn btn-game btn-sm">
            {% if recap_last_sent %}Resend group recap{% else %}Send group recap{% endif %}
        </button>
        {% if recap_last_sent %}<span class="adm-sub ms-2">Last sent {{ recap_last_sent }}</span>{% endif %}
    </form>
    {% endif %}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -q`
Expected: PASS (all recap tests).

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/admin/dashboard.html tests/test_worldcup_group_recap.py
git commit -m "feat(worldcup): admin send-group-recap route + dashboard button"
```

---

### Task 10: `send-group-recap` CLI command

**Files:**
- Modify: `games/worldcup/cli.py`
- Test: `tests/test_worldcup_group_recap.py`

**Interfaces:**
- Consumes: `send_group_stage_recap`.
- Produces: `flask worldcup send-group-recap`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_group_recap.py`:

```python
def test_cli_send_group_recap(app):
    runner = app.test_cli_runner()
    with patch('games.worldcup.services.notifications.send_group_stage_recap',
               return_value={'status': 'sent', 'sent': 2, 'skipped_no_email': 0, 'errors': 0}):
        res = runner.invoke(args=['worldcup', 'send-group-recap'])
    assert res.exit_code == 0
    assert 'sent' in res.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py::test_cli_send_group_recap -q`
Expected: FAIL (no such command).

- [ ] **Step 3: Implement the command**

Add to `games/worldcup/cli.py` (before `register_worldcup_cli`):

```python
@worldcup_cli.command('send-group-recap')
def send_group_recap_cmd():
    """Send the personalized group-stage recap email to all players.

    Admin-triggered analogue of the dashboard button. Refuses unless every
    group's advancement is confirmed.
    """
    from games.worldcup.services.notifications import send_group_stage_recap

    result = send_group_stage_recap()
    click.echo(
        f"[send-group-recap] {result['status']}  "
        f"sent={result.get('sent', 0)}  "
        f"skipped-no-email={result.get('skipped_no_email', 0)}  "
        f"errors={result.get('errors', 0)}"
        + (f"  reason={result['reason']}" if result.get('reason') else '')
    )
    if result.get('errors'):
        raise click.ClickException('One or more recap sends failed — check logs.')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_group_recap.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/cli.py tests/test_worldcup_group_recap.py
git commit -m "feat(worldcup): send-group-recap CLI command"
```

**This is the end of Phase 2 — open the PR for Feature 3, carry it through CodeRabbit to merge before continuing.**

---

# PHASE 3 — Ideal Lineup Card

### Task 11: `get_ideal_lineup` service

**Files:**
- Modify: `games/worldcup/services/stats.py`
- Test: `tests/test_worldcup_stats.py`

**Interfaces:**
- Consumes: the `country_stats` list shape from `get_country_stats` (each dict has `name, iso_code, tier, multiplier, total_score, ...`), `TIERS`.
- Produces: `get_ideal_lineup(country_stats: list[dict]) -> dict | None` returning
  `{'teams': [{'name','iso_code','tier','tier_name','multiplier','total_score'}], 'total_score': float}`
  or `None` when the ideal total is 0.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_stats.py`:

```python
def test_get_ideal_lineup_picks_top_n_per_tier():
    from games.worldcup.services.stats import get_ideal_lineup
    cs = [
        {'name': 'A1', 'iso_code': 'a1', 'tier': 1, 'multiplier': 1.0, 'total_score': 10.0},
        {'name': 'A2', 'iso_code': 'a2', 'tier': 1, 'multiplier': 1.0, 'total_score': 8.0},
        {'name': 'A3', 'iso_code': 'a3', 'tier': 1, 'multiplier': 1.0, 'total_score': 3.0},
        {'name': 'B1', 'iso_code': 'b1', 'tier': 2, 'multiplier': 1.5, 'total_score': 12.0},
        {'name': 'B2', 'iso_code': 'b2', 'tier': 2, 'multiplier': 1.5, 'total_score': 6.0},
    ]
    out = get_ideal_lineup(cs)
    # Tier 1 picks 2 (A1+A2), Tier 2 picks 1 (B1). Total = 10+8+12 = 30.
    names = [t['name'] for t in out['teams']]
    assert names == ['A1', 'A2', 'B1']
    assert out['total_score'] == 30.0


def test_get_ideal_lineup_none_when_no_points():
    from games.worldcup.services.stats import get_ideal_lineup
    cs = [{'name': 'A1', 'iso_code': 'a1', 'tier': 1, 'multiplier': 1.0, 'total_score': 0.0}]
    assert get_ideal_lineup(cs) is None


def test_get_ideal_lineup_tiebreak_is_deterministic():
    from games.worldcup.services.stats import get_ideal_lineup
    cs = [
        {'name': 'Zeta', 'iso_code': 'z', 'tier': 1, 'multiplier': 1.0, 'total_score': 5.0},
        {'name': 'Alpha', 'iso_code': 'a', 'tier': 1, 'multiplier': 1.0, 'total_score': 5.0},
        {'name': 'Mid', 'iso_code': 'm', 'tier': 1, 'multiplier': 1.0, 'total_score': 5.0},
    ]
    out = get_ideal_lineup(cs)
    # Tier 1 picks 2; ties broken by name -> Alpha, Mid.
    assert [t['name'] for t in out['teams']] == ['Alpha', 'Mid']
    assert out['total_score'] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py -k ideal_lineup -q`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement the function**

Add to `games/worldcup/services/stats.py`:

```python
def get_ideal_lineup(country_stats: list[dict]) -> dict | None:
    """Highest-scoring possible roster: top-N multiplied_points teams per tier.

    Pure — consumes the country_stats the stats route already builds. Returns
    None when the ideal total is 0 (pre-results) so the card stays hidden until
    points exist. Provably optimal: slots are tier-partitioned and the
    multiplier is constant within a tier, so greedy top-N per tier = global
    optimum. Ties for the final slot are broken by name; the total is exact.
    """
    from games.worldcup.world_cup_countries import TIERS

    by_tier: dict[int, list[dict]] = {}
    for c in country_stats:
        by_tier.setdefault(c['tier'], []).append(c)

    teams: list[dict] = []
    total = 0.0
    for tier in sorted(TIERS):
        ranked = sorted(by_tier.get(tier, []), key=lambda c: (-c['total_score'], c['name']))
        for c in ranked[:TIERS[tier]['picks']]:
            teams.append({
                'name': c['name'], 'iso_code': c['iso_code'], 'tier': tier,
                'tier_name': TIERS[tier]['name'], 'multiplier': c['multiplier'],
                'total_score': c['total_score'],
            })
            total += c['total_score']

    if total <= 0:
        return None
    return {'teams': teams, 'total_score': total}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py -k ideal_lineup -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/stats.py tests/test_worldcup_stats.py
git commit -m "feat(worldcup): get_ideal_lineup service"
```

---

### Task 12: Wire `ideal_lineup` into the Stats route

**Files:**
- Modify: `games/worldcup/routes.py::stats`
- Test: `tests/test_worldcup_stats.py`

**Interfaces:**
- Consumes: `get_ideal_lineup`, `country_stats`.
- Produces: `ideal_lineup` in the `stats.html` context (only on the `stats_visible=True` branch).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_worldcup_stats.py` (this file's existing tests show the route-test idiom; if a route-rendering test helper exists, reuse it — otherwise assert via the service is already covered, so test the context by rendering):

```python
def test_stats_route_passes_ideal_lineup_when_results_exist(app):
    """Admin sees stats anytime; ideal_lineup present once a team has points."""
    from games.worldcup.services import stats as stats_mod
    client = app.test_client()
    with app.app_context():
        admin = User(username='boss', email='b@test.com', is_admin=True); admin.set_password('x')
        db.session.add(admin)
        t = WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                         tier=1, multiplier=1.0, confederation='X', group_letter='A',
                         base_points=3.0, multiplied_points=3.0)
        db.session.add(t)
        db.session.commit()
        auth_id = admin.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    captured = {}
    real = stats_mod.get_ideal_lineup
    def spy(cs):
        captured['out'] = real(cs)
        return captured['out']
    with patch('games.worldcup.routes.get_ideal_lineup', side_effect=spy):
        resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert captured['out'] is not None  # Brazil has 3 pts -> ideal exists
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py::test_stats_route_passes_ideal_lineup_when_results_exist -q`
Expected: FAIL (`get_ideal_lineup` not imported in routes / not called).

- [ ] **Step 3: Implement**

In `games/worldcup/routes.py`, add `get_ideal_lineup` to the stats-service import (find the existing `from games.worldcup.services.stats import ...`):

```python
from games.worldcup.services.stats import (
    get_country_stats, get_tier_stats, get_overview_kpis, get_tier_combos,
    get_ideal_lineup,
)
```

In `stats()`, in the `stats_visible=True` branch, after `combos = get_tier_combos(SEASON_YEAR)`:

```python
    ideal_lineup = get_ideal_lineup(country_stats)
```

Add `ideal_lineup=ideal_lineup,` to the final `render_template('worldcup/stats.html', ...)` kwargs.

- [ ] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py -k ideal -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/routes.py tests/test_worldcup_stats.py
git commit -m "feat(worldcup): wire ideal_lineup into stats route"
```

---

### Task 13: Ideal Lineup card on the Stats Hub (impeccable)

**Files:**
- Modify: `games/worldcup/templates/worldcup/stats.html`

**Interfaces:**
- Consumes: `ideal_lineup` (`{'teams': [...{name, iso_code, tier, tier_name, multiplier, total_score}], 'total_score': float}`), `_flag.html` macro.

- [ ] **Step 1: Invoke impeccable**

Load the `impeccable` skill (subcommand for adding/designing a component). Per the project hard rule, read BOTH the top-level `DESIGN.md` and `games/worldcup/DESIGN.md` before producing design output. Prove skill use with content fingerprints (per [[feedback_subagent_skill_proof]] if delegating).

- [ ] **Step 2: Design + add the card** to `stats.html`, rendered only `{% if ideal_lineup %}`. Requirements:
- WC Casual-Light: white `.card` / `.wc-stat-card` on bone; navy/red/gold per WC palette; no raw `color: var(--text-muted)` on the light substrate.
- Flags via `{% from '_flag.html' import flag with context %}` then `{{ flag(t.iso_code) }}`.
- Group the 9 teams by `tier_name`; show each team's `multiplier` as a Teko chip (`.wc-multiplier-chip` precedent) and its `total_score`.
- `total_score` is the focal figure.
- Working title "The Ideal Lineup" (NOT "Perfect XI" — 9 teams). Final eyebrow/title/subhead copy is impeccable's call; WC body eyebrows carry no `◈`/`◇` glyph.
- Placement within the page is impeccable's call (a strong default: directly under the overview KPIs).

- [ ] **Step 3: Smoke it in the browser**

With the dev server on a live-state DB, load `/worldcup/stats` (as admin, or post-deadline) and confirm the card renders with flags, tier grouping, multiplier chips, and the total. Mobile-width check per [[project_chrome_devtools_mobile_emulation]] (`emulate "375x812x2,mobile,touch"`).

- [ ] **Step 4: Add a render lock test** to `tests/test_worldcup_stats.py`:

```python
def test_stats_page_renders_ideal_lineup_card(app):
    client = app.test_client()
    with app.app_context():
        admin = User(username='boss2', email='b2@test.com', is_admin=True); admin.set_password('x')
        db.session.add(admin)
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    base_points=3.0, multiplied_points=3.0))
        db.session.commit()
        auth_id = admin.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert b'Ideal Lineup' in resp.data  # adjust to the final card title impeccable ships
```

(Adjust the asserted string to match the final card title.)

- [ ] **Step 5: Run tests + commit**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py -q`
Expected: PASS.

```bash
git add games/worldcup/templates/worldcup/stats.html tests/test_worldcup_stats.py
git commit -m "feat(worldcup): Ideal Lineup card on the Stats Hub"
```

**This is the end of Phase 3 — open the PR for Feature 1, carry it through CodeRabbit to merge.**

---

# PHASE 4 — CLAUDE.md Pass

### Task 14: Fold new conventions into CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (and run the skill's audit).

- [ ] **Step 1: Run the improver.** Invoke the `claude-md-management:claude-md-improver` skill. Direct it at the conventions introduced by this work:
  - The bulk bracket "Load from API" admin route (`/worldcup/admin/bracket/<stage>`), the review-then-confirm pattern, `fetch_bracket_proposal` / `populatable_bracket_stages` / `all_group_advancement_confirmed` in `services/sync.py`, and that the per-shell `set_knockout.html` form remains the manual override.
  - The admin-triggered group recap (`send_group_stage_recap`, `/worldcup/admin/send-group-recap`, `flask worldcup send-group-recap`), its all-groups-confirmed guard, and the marker-file idempotency.
  - The `get_ideal_lineup` Stats-Hub service + "The Ideal Lineup" card (and the "not Perfect XI / 9 not 11" naming note).
  - Add `flask worldcup send-group-recap` to the World Cup CLI command list in the Commands block.

- [ ] **Step 2: Keep it lean.** Don't duplicate what tests already enforce — record only the load-bearing conventions and SSoT pointers. Verify any file:line citations against current code before writing them.

- [ ] **Step 3: Commit.**

```bash
git add CLAUDE.md
git commit -m "docs: fold knockout-transition conventions into CLAUDE.md"
```

---

## Self-Review

**Spec coverage:**
- Feature 1 (ideal lineup, Stats card, global, `None` pre-results, impeccable, tests) → Tasks 11–13. ✓
- Feature 2 (bulk bracket pre-fill, proposal extended past R32, review-then-write route, dashboard CTA, manual fallback kept, rehearsal, tests) → Tasks 1–6. ✓
- Feature 3 (bracket-lock recap, admin button + CLI, all-groups-confirmed guard, marker idempotency, personalized advanced/eliminated/explainer/standing/ladder content, HTML + plain text, tests) → Tasks 7–10. ✓
- CLAUDE.md final pass → Task 14. ✓
- Sequencing 2→3→1→docs preserved; each phase ends at a PR boundary. ✓

**Placeholder scan:** No "TBD/TODO/handle edge cases" — every code step shows real code; the two "adjust to final title/route" notes are deliberate, scoped follow-ups with a concrete default, not blanks. ✓

**Type consistency:**
- `fetch_bracket_proposal` returns `{target_stage, proposals, unresolved, error}`; consumed identically in Task 3 route + Task 4 template. ✓
- `all_group_advancement_confirmed()` (Task 2) consumed by `populatable_bracket_stages` (Task 2), the recap guard (Task 7), and the dashboard (Task 9). ✓
- `send_group_stage_recap()` return keys (`status/sent/skipped_no_email/errors/reason`) consumed consistently in the route (Task 9) and CLI (Task 10). ✓
- `get_ideal_lineup()` shape (`teams[].{name,iso_code,tier,tier_name,multiplier,total_score}`, `total_score`) defined in Task 11, consumed in Task 13 template. ✓

No issues found.
