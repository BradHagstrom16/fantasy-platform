# Post-Deadline UI State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three UI surfaces that show stale pre-deadline messaging after `TOURNAMENT_DEADLINE_UTC` passes.

**Architecture:** Template-only fix across two templates and one route. `deadline_passed` (already computed in the WC route) is added to the homepage route; both templates add `{% if deadline_passed %}` branches. No model changes, no migrations. `frontend-design` skill invoked for new card HTML to ensure design system compliance.

**Tech Stack:** Flask/Jinja2, Bootstrap 5, Commissioner's Club CSS design system (`btn-game`, `--game-primary`, `border-start` conventions)

---

## File Map

| File | Change |
|------|--------|
| `games/worldcup/constants.py` | **Revert** temp deadline from 4E testing back to production value |
| `core/main/routes.py` | Import `TOURNAMENT_DEADLINE_UTC`, compute `deadline_passed`, pass to template |
| `core/main/templates/main/index.html` | Update featured card button text when `deadline_passed` |
| `games/worldcup/templates/worldcup/index.html` | Restructure `pre_tournament` CTA block around `deadline_passed` |
| `tests/test_post_deadline_ui.py` | New — route-level tests for all deadline UI states |

---

## Task 1: Revert temporary deadline constant from 4E testing

The deadline was set to a past date (Apr 10) for step 4E manual testing. Revert it before writing any new code.

**Files:**
- Modify: `games/worldcup/constants.py`

- [ ] **Step 1: Restore `TOURNAMENT_DEADLINE_UTC` to production value**

In `games/worldcup/constants.py`, change line 21 back to:

```python
TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
```

(Remove the `# TEMP: past deadline for 4E testing — revert to 2026-06-11` comment.)

- [ ] **Step 2: Verify the server renders pre-deadline state**

```bash
FLASK_APP=app.py venv/bin/flask run
```

Open `http://127.0.0.1:5000/worldcup/` — should show "Edit My Picks" / "Join Now" CTAs again (the pre-deadline state).

- [ ] **Step 3: Commit**

```bash
git add games/worldcup/constants.py
git commit -m "fix: revert TOURNAMENT_DEADLINE_UTC to production value after 4E testing"
```

---

## Task 2: Homepage route — pass `deadline_passed` to template

**Files:**
- Modify: `core/main/routes.py`
- Test: `tests/test_post_deadline_ui.py` (create file)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_post_deadline_ui.py`:

```python
"""
Tests for post-deadline UI state across homepage and WC index.
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick


PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=timezone.utc)


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


# ── Homepage tests ──────────────────────────────────────────────────────────

def test_homepage_shows_view_standings_post_deadline(client):
    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'View Standings' in resp.data


def test_homepage_shows_enter_pool_pre_deadline_authenticated(client, app):
    with app.app_context():
        user = User(username='homer', email='homer@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'Enter the Pool' in resp.data


def test_homepage_shows_join_pool_pre_deadline_anonymous(client):
    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'Join the World Cup Pool' in resp.data
```

- [ ] **Step 2: Run tests — expect failures**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py -v
```

Expected: `test_homepage_shows_view_standings_post_deadline` FAILS (`View Standings` not in response)

- [ ] **Step 3: Update `core/main/routes.py`**

```python
"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages.
"""
from datetime import datetime, timezone

from flask import render_template, url_for
from flask_login import current_user

from core.main import main_bp
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC


@main_bp.route('/')
def index():
    """Platform home page — shows available games."""
    featured_game = {
        'name': '2026 FIFA World Cup',
        'slug': 'worldcup',
        'description': 'Pick 9 national teams across 5 tiers. Points accumulate as your teams win and advance through the bracket.',
        'emoji': '⚽',
        'url': url_for('worldcup.index'),
    }

    other_games = [
        {
            'name': "Golf Pick 'Em",
            'slug': 'golf',
            'description': 'Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
            'emoji': '⛳',
            'url': None,
        },
        {
            'name': 'CFB Survivor Pool',
            'slug': 'cfb',
            'description': 'Weekly college football picks against the spread. Two lives. Last survivor wins.',
            'emoji': '🏈',
            'url': None,
        },
    ]

    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC

    return render_template(
        'main/index.html',
        featured_game=featured_game,
        other_games=other_games,
        deadline_passed=deadline_passed,
    )
```

- [ ] **Step 4: Run tests — expect all homepage tests to pass**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py::test_homepage_shows_view_standings_post_deadline tests/test_post_deadline_ui.py::test_homepage_shows_enter_pool_pre_deadline_authenticated tests/test_post_deadline_ui.py::test_homepage_shows_join_pool_pre_deadline_anonymous -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add core/main/routes.py tests/test_post_deadline_ui.py
git commit -m "feat: pass deadline_passed to homepage route + add UI state tests"
```

---

## Task 3: Homepage template — update featured card button text

**Invoke the `frontend-design` skill for this task.**

**Files:**
- Modify: `core/main/templates/main/index.html`

- [ ] **Step 1: Invoke `frontend-design` skill**

Before editing the template, invoke the `frontend-design` skill to ensure the new button state matches the Commissioner's Club design system and the existing featured card styling.

- [ ] **Step 2: Update the CTA button block**

In `core/main/templates/main/index.html`, replace lines 46–52:

```html
<span class="btn btn-warning btn-lg px-5 featured-cta">
    {% if current_user.is_authenticated %}
        <i class="bi bi-globe2 me-2"></i>Enter the Pool
    {% else %}
        <i class="bi bi-globe2 me-2"></i>Join the World Cup Pool
    {% endif %}
</span>
```

With:

```html
<span class="btn btn-warning btn-lg px-5 featured-cta">
    {% if deadline_passed %}
        <i class="bi bi-bar-chart me-2"></i>View Standings
    {% elif current_user.is_authenticated %}
        <i class="bi bi-globe2 me-2"></i>Enter the Pool
    {% else %}
        <i class="bi bi-globe2 me-2"></i>Join the World Cup Pool
    {% endif %}
</span>
```

- [ ] **Step 3: Run tests**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py -v
```

Expected: all 3 homepage tests PASS, no regressions

- [ ] **Step 4: Smoke check in browser**

With the server running, set `TOURNAMENT_DEADLINE_UTC` temporarily to `datetime(2000,1,1,tzinfo=ZoneInfo("UTC"))` in constants.py, reload, and verify the homepage card reads "View Standings". Revert the constant immediately after.

- [ ] **Step 5: Commit**

```bash
git add core/main/templates/main/index.html
git commit -m "feat: show 'View Standings' on homepage featured card post-deadline"
```

---

## Task 4: WC index template — restructure CTA block for post-deadline states

**Invoke the `frontend-design` skill for this task.**

**Files:**
- Modify: `games/worldcup/templates/worldcup/index.html`
- Modify: `tests/test_post_deadline_ui.py` (add WC index tests)

- [ ] **Step 1: Write failing WC index tests**

Add to `tests/test_post_deadline_ui.py`:

```python
# ── WC index helpers ─────────────────────────────────────────────────────────

def _make_enrolled_user_with_picks(app):
    """Create a user enrolled in WC with 9 picks submitted. Returns user.id."""
    with app.app_context():
        user = User(username='player1', email='player1@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.flush()

        enrollment = WorldCupEnrollment(
            user_id=user.id,
            season_year=2026,
            picks_submitted=True,
            usa_goals_guess=4,
        )
        db.session.add(enrollment)
        db.session.flush()

        # Create 9 minimal teams across tiers and add picks
        tier_map = {1: 2, 2: 1, 3: 2, 4: 2, 5: 2}
        pick_num = 1
        for tier, count in tier_map.items():
            for _ in range(count):
                team = WorldCupTeam(
                    fifa_code=f'T{pick_num:02d}',
                    name=f'Team {pick_num}',
                    display_name=f'Team {pick_num}',
                    tier=tier,
                    multiplier=float(5 - tier) + 1.0,
                    confederation='TEST',
                    group_letter='A',
                )
                db.session.add(team)
                db.session.flush()
                pick = WorldCupPick(
                    enrollment_id=enrollment.id,
                    team_id=team.id,
                    tier=tier,
                )
                db.session.add(pick)
                pick_num += 1

        db.session.commit()
        return user.id


# ── WC index tests ───────────────────────────────────────────────────────────

def test_wc_index_shows_youre_in_post_deadline(client, app):
    user_id = _make_enrolled_user_with_picks(app)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert "You&#39;re In!".encode() in resp.data or b"You're In!" in resp.data
    assert b'View My Picks' in resp.data
    assert b'Edit My Picks' not in resp.data


def test_wc_index_shows_tournament_underway_unenrolled_post_deadline(client):
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert b'Tournament Underway' in resp.data
    assert b'View Leaderboard' in resp.data
    assert b'Join Now' not in resp.data


def test_wc_index_shows_join_cta_pre_deadline_unenrolled(client):
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert b'Join Now' in resp.data
```

- [ ] **Step 2: Run new tests — expect failures**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py::test_wc_index_shows_youre_in_post_deadline tests/test_post_deadline_ui.py::test_wc_index_shows_tournament_underway_unenrolled_post_deadline -v
```

Expected: both FAIL (`You're In!` and `Tournament Underway` not found)

- [ ] **Step 3: Invoke `frontend-design` skill, then update the WC index template**

Invoke `frontend-design` before editing. Then in `games/worldcup/templates/worldcup/index.html`, replace the `{# ── Pre-Tournament CTAs ── #}` block (lines 24–136) with:

```html
{# ── Pre-Tournament CTAs ── #}
{% if tournament_phase == 'pre_tournament' %}
<div class="row g-3 mb-4 animate-in">

  {% if deadline_passed %}

    {% if enrollment and enrollment.picks_submitted %}
    {# Deadline passed — enrolled with picks: You're In! #}
    <div class="col-12">
      <div class="card border-0 shadow-sm border-start border-success border-3">
        <div class="card-body p-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
          <div>
            <h4 class="mb-1 text-success" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">
              <i class="bi bi-check-circle-fill me-2"></i>You're In!
            </h4>
            <p class="mb-0 text-muted">
              The tournament has started &mdash; track your teams on the leaderboard.
            </p>
          </div>
          <a href="{{ url_for('worldcup.picks') }}" class="btn btn-game px-4">
            <i class="bi bi-clipboard-check me-1"></i>View My Picks
          </a>
        </div>
      </div>
    </div>

    {% else %}
    {# Deadline passed — unenrolled or enrolled with no picks: Tournament Underway #}
    <div class="col-12">
      <div class="card border-0 shadow-sm border-start border-3" style="border-color: var(--game-primary) !important;">
        <div class="card-body p-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
          <div>
            <h4 class="mb-1" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">
              <i class="bi bi-globe2 me-2"></i>Tournament Underway
            </h4>
            <p class="mb-0 text-muted">
              Registration is closed, but you can follow the action.
            </p>
          </div>
          <a href="{{ url_for('worldcup.leaderboard') }}" class="btn btn-outline-secondary px-4">
            <i class="bi bi-bar-chart me-1"></i>View Leaderboard
          </a>
        </div>
      </div>
    </div>
    {% endif %}

  {% else %}

    {% if not enrollment %}
    {# Not enrolled — join CTA #}
    <div class="col-12">
      <div class="card border-0 shadow-sm">
        <div class="card-body p-4 text-center">
          <h3 class="mb-2" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">
            Join the Pool
          </h3>
          <p class="text-muted mb-3">
            Pick 9 national teams across 5 tiers. Points accumulate as your teams win matches and advance through the bracket.
            Entry fee: <strong>${{ entry_fee }}</strong>.
          </p>
          <div class="d-flex justify-content-center gap-2 flex-wrap">
            <a href="{{ url_for('worldcup.join') }}" class="btn btn-game btn-lg px-5">
              <i class="bi bi-globe2 me-2"></i>Join Now
            </a>
            <a href="{{ url_for('worldcup.rules') }}" class="btn btn-outline-secondary btn-lg px-4">
              <i class="bi bi-info-circle me-2"></i>See How It Works
            </a>
          </div>
          {% if total_enrolled > 0 %}
          <div class="mt-3 text-muted small">{{ total_enrolled }} player{{ 's' if total_enrolled != 1 }} enrolled</div>
          {% endif %}
        </div>
      </div>
    </div>

    {% elif not enrollment.picks_submitted %}
    {# Enrolled but no picks — picks CTA #}
    <div class="col-12">
      <div class="card border-0 shadow-sm wc-pick-cta">
        <div class="card-body p-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
          <div>
            <h4 class="mb-1" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">
              <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Submit Your Picks
            </h4>
            <p class="mb-0 text-muted">
              Deadline: <strong>{{ deadline_ct.strftime('%b %-d, %Y at %-I:%M %p CT') }}</strong>
            </p>
          </div>
          <a href="{{ url_for('worldcup.picks') }}" class="btn btn-game btn-lg">
            <i class="bi bi-pencil-square me-2"></i>Make Picks
          </a>
        </div>
      </div>
    </div>

    {% else %}
    {# Enrolled with picks — edit CTA #}
    <div class="col-12">
      <div class="card border-0 shadow-sm border-start border-success border-3">
        <div class="card-body p-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
          <div>
            <h4 class="mb-1 text-success" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">
              <i class="bi bi-check-circle-fill me-2"></i>You're All Set!
            </h4>
            <p class="mb-0 text-muted">
              Picks submitted. You can edit until <strong>{{ deadline_ct.strftime('%b %-d at %-I:%M %p CT') }}</strong>.
            </p>
          </div>
          <a href="{{ url_for('worldcup.picks', edit=1) }}" class="btn btn-game px-4">
            <i class="bi bi-pencil-square me-1"></i>Edit My Picks
          </a>
        </div>
      </div>
    </div>
    {% endif %}

  {% endif %}{# end deadline_passed #}

  {# ── My Roster widget (enrolled with picks) ── #}
  {% if user_picks %}
  <div class="col-12">
    <div class="card border-0 shadow-sm roster-card">
      <div class="card-body p-0">
        <div class="roster-header">
          <i class="bi bi-people-fill"></i>My Roster
        </div>
        {% set picks_by_tier = {} %}
        {% for pick in user_picks %}
          {% if pick.team.tier not in picks_by_tier %}
            {% set _ = picks_by_tier.update({pick.team.tier: []}) %}
          {% endif %}
          {% set _ = picks_by_tier[pick.team.tier].append(pick) %}
        {% endfor %}
        <div class="roster-tiers">
          {% for tier_num in range(1, 6) %}
          {% if tier_num in picks_by_tier %}
          <div class="roster-tier-row" style="--tier-color: var(--wc-tier{{ tier_num }});">
            <div class="roster-tier-label tier-badge tier-badge-{{ tier_num }}">T{{ tier_num }}</div>
            <div class="roster-tier-teams">
              {% for pick in picks_by_tier[tier_num] %}
              <div class="roster-team-card">
                <span class="roster-team-flag">{{ pick.team.flag_emoji }}</span>
                <span class="roster-team-name">{{ pick.team.display_name }}</span>
                <span class="roster-team-abbr">{{ pick.team.fifa_code }}</span>
                <span class="roster-team-mult">×{{ pick.team.multiplier | int if pick.team.multiplier == (pick.team.multiplier | int) else pick.team.multiplier }}</span>
              </div>
              {% endfor %}
            </div>
          </div>
          {% endif %}
          {% endfor %}
        </div>
      </div>
    </div>
  </div>
  {% endif %}

</div>
{% endif %}
```

- [ ] **Step 4: Run all tests**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Run full test suite — no regressions**

```bash
venv/bin/python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/templates/worldcup/index.html tests/test_post_deadline_ui.py
git commit -m "feat: post-deadline CTA states on WC index (You're In + Tournament Underway)"
```

---

## Task 5: Manual verification against 4E checklist

- [ ] **Step 1: Temporarily set deadline to past for verification**

In `games/worldcup/constants.py`, set:

```python
TOURNAMENT_DEADLINE_UTC = datetime(2026, 4, 10, 19, 0, 0, tzinfo=ZoneInfo("UTC"))  # TEMP verification
```

Restart the server.

- [ ] **Step 2: Verify all three 4E checkboxes**

- [ ] `/worldcup/picks` — shows read-only (no edit form, no submit button) ✅ already passing
- [ ] WC index — enrolled user sees "You're In!" card with "View My Picks", no "Edit My Picks"
- [ ] WC index (logged out) — sees "Tournament Underway" + "View Leaderboard"
- [ ] Homepage — featured card button reads "View Standings"

- [ ] **Step 3: Revert deadline to production value**

```python
TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
```

Restart and confirm pre-deadline CTAs are back.

- [ ] **Step 4: Final commit**

```bash
git add games/worldcup/constants.py
git commit -m "fix: revert TOURNAMENT_DEADLINE_UTC after 4E verification — production value restored"
```

---

## Rebuild graphify after implementation

Per CLAUDE.md, after modifying code files run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```
