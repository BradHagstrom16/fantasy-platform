# Spec C — Plan 2: Per-rival surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin `player_detail.html` to consume Plan 1's `.wc-*` foundation, add a new public `/worldcup/team/<int:team_id>` route + `team_detail.html` template, and introduce two reusable service helpers (`compute_rank_neighbors` shared with Plan 3, `compute_team_ownership` for Plan 2 only).

**Architecture:** Pure visual reskin on `player_detail.html` — no scoring or model changes. New `team_detail` route is read-only and public (no `@login_required`, matches access policy of `leaderboard.html` and `stats.html`). Two new service modules: `games/worldcup/services/ranking.py` (rank-neighbor helper for player_detail hero + Plan 3's leaderboard "Your Standing" block) and `games/worldcup/services/team_detail.py` (ownership + path-to-crown helpers). All scoring data derived from `compute_team_score_events()` per CLAUDE.md SSoT — never recomputed in the route or template. Pre-deadline ownership data is strictly hidden (no count, no names) per spec D11.

**Tech Stack:** Bootstrap 5.3, Jinja2 templates, vanilla CSS (no preprocessors), SQLAlchemy 2.0. WC palette tokens, `body.game-worldcup` activation, and the 6 `.wc-*` foundation utilities (`wc-eyebrow`, `wc-numeral`, `wc-hero-grad`, `wc-tier-dot`, `wc-multiplier-chip`, `wc-card`) all live on `main` from Plan 1's commit `6434cae`. The sub-nav already forward-references `worldcup.team_detail` in the Board pill's active-state list — once Plan 2 lands the endpoint, the Board pill auto-activates on `/worldcup/team/<id>`.

**Spec reference:** `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md` §7 (Plan 2).

---

## Pre-flight

### Task 0: Worktree setup + baseline verification

**Files:** none modified yet. This task creates the working environment.

- [ ] **Step 1: Create the worktree branch off main**

```bash
cd /Users/bhagstrom/fantasy-platform
git fetch origin main
git worktree add -b redesign/ccc-worldcup-plan2 ../fantasy-platform-ccc-wc-plan2 origin/main
cd ../fantasy-platform-ccc-wc-plan2
```

Expected: new directory `../fantasy-platform-ccc-wc-plan2` exists; `git status` reports clean working tree on branch `redesign/ccc-worldcup-plan2`.

- [ ] **Step 2: Verify Plan 1's foundation is on main**

```bash
git log --oneline -5
grep -n "wc-eyebrow\|wc-card\|page-hero.wc-hero-grad" static/css/style.css | head -5
grep -n "worldcup.team_detail" templates/base.html
```

Expected: log shows `6434cae` (Plan 1 squash); style.css contains `.wc-eyebrow`, `.card.wc-card`, `.page-hero.wc-hero-grad`; base.html sub-nav references `worldcup.team_detail` in the Board pill's active-state list. If any are missing, you are not branched off the right `main` — stop and reconcile.

- [ ] **Step 3: Verify baseline tests pass before changing anything**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all 150 tests pass. If any fail, stop and investigate before proceeding — they are baseline regressions, not introduced by this plan.

- [ ] **Step 4: Verify pyright is clean on the WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 5: Confirm the spec file is accessible**

```bash
test -f docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md && echo "spec present"
```

Expected output: `spec present`.

---

## Foundation: shared rank-neighbor helper

### Task 1: Add `compute_rank_neighbors()` to a new ranking service module (TDD)

This helper is shared with Plan 3's leaderboard "Your Standing" block per spec §7. Living it in its own module keeps Plan 3's later import target stable.

**Files:**
- Create: `games/worldcup/services/ranking.py`
- Create: `tests/test_worldcup_ranking.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_ranking.py`:

```python
"""Tests for games/worldcup/services/ranking.compute_rank_neighbors."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.services.ranking import compute_rank_neighbors


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed_enrollments(scores: list[float]) -> list[int]:
    """Seed N enrollments with the given scores in input order. Returns ids."""
    ids = []
    for i, score in enumerate(scores):
        u = User(username=f'p{i}', email=f'p{i}@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(
            user_id=u.id, season_year=2026,
            picks_submitted=True, total_score=score,
            usa_goals_guess=5,
        )
        db.session.add(e)
        db.session.flush()
        ids.append(e.id)
    db.session.commit()
    return ids


def test_compute_rank_neighbors_for_leader(app):
    with app.app_context():
        # scores: [50, 40, 30] — first is leader
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[0])
        assert result['rank'] == 1
        assert result['points'] == 50.0
        assert result['lead_delta_up'] is None
        assert result['lead_delta_down'] == 10.0  # ahead of rank 2 by 10


def test_compute_rank_neighbors_for_middle(app):
    with app.app_context():
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[1])
        assert result['rank'] == 2
        assert result['points'] == 40.0
        assert result['lead_delta_up'] == 10.0   # 10 behind rank 1
        assert result['lead_delta_down'] == 10.0 # 10 ahead of rank 3


def test_compute_rank_neighbors_for_last(app):
    with app.app_context():
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[2])
        assert result['rank'] == 3
        assert result['points'] == 30.0
        assert result['lead_delta_up'] == 20.0
        assert result['lead_delta_down'] is None


def test_compute_rank_neighbors_handles_ties(app):
    with app.app_context():
        # Two enrollments tied at 40 — both rank 2. Tiebreaker: usa_goals_guess asc
        ids = _seed_enrollments([50.0, 40.0, 40.0])
        # ids[1] and ids[2] both at score=40; order tiebroken by usa_goals_guess asc
        # both seeded with guess=5 so the tiebreak is by id (stable sort)
        # Both should report rank=2 (dense-rank style: same score => same rank)
        r1 = compute_rank_neighbors(ids[1])
        r2 = compute_rank_neighbors(ids[2])
        assert r1['rank'] == 2
        assert r2['rank'] == 2


def test_compute_rank_neighbors_unknown_id_raises(app):
    with app.app_context():
        with pytest.raises(ValueError):
            compute_rank_neighbors(99999)
```

Run:

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'games.worldcup.services.ranking'`.

- [ ] **Step 2: Implement the helper**

Create `games/worldcup/services/ranking.py`:

```python
"""
World Cup Fantasy Pool — Ranking helpers
==========================================
Pure read-only ranking computations shared across surfaces:
- player_detail.html hero (Plan 2)
- leaderboard.html "Your Standing" block (Plan 3)
- worldcup home _live state dossier (Plan 4, optional reuse)

Ranks are dense — tied scores share a rank. The sort order matches
games/worldcup/routes.leaderboard():
    total_score DESC, usa_goals_guess ASC.
"""
from typing import Optional, TypedDict

from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


class RankNeighbors(TypedDict):
    rank: int
    points: float
    lead_delta_up: Optional[float]   # points behind rank 1; None if leader
    lead_delta_down: Optional[float] # points ahead of next-ranked; None if last


def compute_rank_neighbors(enrollment_id: int) -> RankNeighbors:
    """Return rank + points + lead deltas for one enrollment in the SEASON_YEAR pool.

    Sort matches the public leaderboard (total_score DESC, usa_goals_guess ASC).
    Ranks are dense: tied total_scores share the same rank.

    Raises ValueError if enrollment_id is not found in the SEASON_YEAR pool.
    """
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    target_idx = next((i for i, e in enumerate(enrollments) if e.id == enrollment_id), None)
    if target_idx is None:
        raise ValueError(f'enrollment {enrollment_id} not found in season {SEASON_YEAR}')

    target = enrollments[target_idx]

    # Dense rank: count distinct scores strictly greater than target.total_score, plus 1.
    rank = 1 + len({e.total_score for e in enrollments if e.total_score > target.total_score})

    # Leader points = first enrollment in the ordered list.
    leader_points = enrollments[0].total_score
    lead_delta_up: Optional[float] = (
        None if rank == 1 else round(leader_points - target.total_score, 2)
    )

    # "Next-ranked" delta is to the next enrollment with a strictly lower score.
    next_lower = next(
        (e for e in enrollments[target_idx + 1:] if e.total_score < target.total_score),
        None,
    )
    lead_delta_down: Optional[float] = (
        None if next_lower is None else round(target.total_score - next_lower.total_score, 2)
    )

    return RankNeighbors(
        rank=rank,
        points=float(target.total_score),
        lead_delta_up=lead_delta_up,
        lead_delta_down=lead_delta_down,
    )
```

- [ ] **Step 3: Run tests — they should pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 4: Run pyright + full test suite**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: pyright 0 errors; all tests green (155 = 150 baseline + 5 new).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/ranking.py tests/test_worldcup_ranking.py
git commit -m "feat(ccc-wc): add compute_rank_neighbors() shared ranking helper

Returns rank + points + lead_delta_up/down for one enrollment.
Dense-rank semantics; sort matches public leaderboard
(total_score DESC, usa_goals_guess ASC). Used by Plan 2's
player_detail hero and Plan 3's leaderboard 'Your Standing' block.

Refs Spec C Plan 2."
```

---

## player_detail.html reskin

### Task 2: Reskin `player_detail.html` and surface Lead delta in the hero

**Files:**
- Modify: `games/worldcup/routes.py` — `player_detail()` route (~lines 373–410): add rank-neighbor lookup
- Modify: `games/worldcup/templates/worldcup/player_detail.html` (113 lines)

- [ ] **Step 1: Re-read the existing route + template**

```bash
sed -n '373,415p' games/worldcup/routes.py
cat games/worldcup/templates/worldcup/player_detail.html
```

Expected: route fetches `enrollment`, computes `picks_visible`, renders `picks` + `events_by_pick`. Template has `.page-hero` + back link + desktop table + mobile cards + lock card.

- [ ] **Step 2: Wire `compute_rank_neighbors` into the route**

In `games/worldcup/routes.py`, add the import near the existing scoring imports (around line 26):

```python
from games.worldcup.services.ranking import compute_rank_neighbors
```

Then update the `player_detail()` route body. Replace the current `return render_template(...)` block (lines ~402–410) with:

```python
    # Rank + lead deltas for hero stat block. Always computed (cheap query).
    neighbors = compute_rank_neighbors(enrollment.id)

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
        events_by_pick=events_by_pick,
        tiers=TIERS,
        picks_visible=picks_visible,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        neighbors=neighbors,
    )
```

No other route logic changes.

- [ ] **Step 3: Replace the template**

Replace the entire contents of `games/worldcup/templates/worldcup/player_detail.html` with:

```jinja
{% extends "base.html" %}
{% block title %}{{ enrollment.get_display_name() }} — World Cup Fantasy Pool{% endblock %}

{% block content %}
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow {% if neighbors.rank == 1 %}wc-eyebrow-gold{% else %}wc-eyebrow-red{% endif %}">
      {% if neighbors.rank == 1 %}Current Leader{% else %}Rank {{ neighbors.rank }}{% endif %}
    </span>
    <h1>
      <span class="me-2">{{ enrollment.user.get_avatar() }}</span>{{ enrollment.get_display_name() }}
    </h1>
    <div class="player-hero-stats">
      <div class="hero-stat">
        <span class="wc-eyebrow">Total</span>
        <strong class="wc-numeral">{{ "%.1f"|format(enrollment.total_score) }}</strong>
      </div>
      <div class="hero-stat">
        <span class="wc-eyebrow">Lead</span>
        <strong class="wc-numeral">
          {% if neighbors.lead_delta_up is none %}
            &mdash;
          {% else %}
            -{{ "%.1f"|format(neighbors.lead_delta_up) }}
          {% endif %}
        </strong>
      </div>
      {% if enrollment.usa_goals_guess is not none %}
      <div class="hero-stat">
        <span class="wc-eyebrow">Tiebreak</span>
        <strong class="wc-numeral">{{ enrollment.usa_goals_guess }}</strong>
      </div>
      {% endif %}
    </div>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-8">

      <div class="mb-3">
        <a href="{{ url_for('worldcup.leaderboard') }}" class="back-link">
          <i class="bi bi-arrow-left me-1"></i>Back to Board
        </a>
      </div>

      {% if picks_visible %}
        {% if picks %}
        {# Desktop table with drill-down accordion #}
        <div class="card border-0 shadow-sm animate-in player-picks-desktop wc-card wc-card-flush">
          <div class="card-body p-0">
            <div class="table-responsive">
              <table class="table table-worldcup mb-0">
                <thead>
                  <tr>
                    <th>Team</th>
                    <th>Tier</th>
                    <th class="text-center">Multiplier</th>
                    <th class="text-end">Base</th>
                    <th class="text-end">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {% set ns = namespace(total_base=0.0, total_mult=0.0) %}
                  {% for pick in picks %}
                    {% with events = events_by_pick.get(pick.id, []) %}
                      {% include 'worldcup/_pick_row.html' %}
                    {% endwith %}
                    {% set ns.total_base = ns.total_base + pick.base_points %}
                    {% set ns.total_mult = ns.total_mult + pick.multiplied_points %}
                  {% endfor %}
                </tbody>
                <tfoot>
                  <tr style="border-top:2px solid var(--border);">
                    <td colspan="3" class="fw-bold">Total</td>
                    <td class="text-end fw-bold wc-numeral">{{ "%.1f"|format(ns.total_base) }}</td>
                    <td class="text-end fw-bold wc-numeral">{{ "%.1f"|format(ns.total_mult) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>

        {# Mobile cards. Team name is plain text in Task 2; Task 4 wraps it
           in a deep-link to /worldcup/team/<id> once the route exists.
           url_for() raises BuildError for missing endpoints (unlike Jinja's
           `in [...]` test in the sub-nav), so the link must wait for Task 4. #}
        <div class="player-picks-mobile">
          {% set ns2 = namespace(total=0.0) %}
          <div class="d-flex flex-column gap-2 mb-3">
            {% for pick in picks %}
            <div class="player-pick-card">
              <div>
                <span class="wc-tier-dot wc-tier-dot-{{ pick.tier }}"></span>
                <span class="wc-eyebrow">T{{ pick.tier }}</span>
                <span class="pick-team d-block mt-1">
                  {{ pick.team.flag_emoji }} {{ pick.team.display_name }}
                  <small class="text-muted">Grp {{ pick.team.group_letter }}</small>
                </span>
              </div>
              <div class="pick-points wc-numeral">
                {{ "%.1f"|format(pick.multiplied_points) }}
                <small>&times;{{ pick.team.multiplier }}</small>
              </div>
            </div>
            {% set ns2.total = ns2.total + pick.multiplied_points %}
            {% endfor %}
          </div>
          <div class="d-flex justify-content-between align-items-center px-1 fw-bold wc-numeral" style="font-size:1.15rem;">
            <span>Total</span>
            <span>{{ "%.1f"|format(ns2.total) }} pts</span>
          </div>
        </div>
        {% else %}
        <div class="text-center py-5 text-muted">
          <i class="bi bi-x-circle" style="font-size:2.5rem; opacity:.3;"></i>
          <p class="mt-2 mb-0">No picks submitted.</p>
        </div>
        {% endif %}
      {% else %}
        <div class="card border-0 shadow-sm animate-in wc-card wc-card-flush">
          <div class="card-body text-center py-5">
            <i class="bi bi-lock-fill" style="font-size:2.5rem; color:var(--wc-red); opacity:.7;"></i>
            <span class="wc-eyebrow d-block mt-3">Roster sealed</span>
            <h5 class="mt-1 mb-2">Picks are hidden</h5>
            <p class="text-muted mb-0">
              Picks will be revealed when the tournament begins.<br>
              <span class="small">Deadline: {{ deadline_ct.strftime('%b %-d, %Y at %-I:%M %p CT') }}</span>
            </p>
          </div>
        </div>
      {% endif %}

    </div>
  </div>

  {% include 'worldcup/_pick_accordion_script.html' %}
</div>
{% endblock %}
```

Notes for the editor:
- Hero gains a 2- or 3-stat grid (Total · Lead · Tiebreak) using `.hero-stat` containers — *not* the platform `.stat-block` class, which carries its own white-card chrome that collides with the dark hero. The `.hero-stat` class is introduced by this task's CSS.
- Lead delta displays with a leading minus sign (e.g., `-12.5`) framing the player as N points *behind* the leader. Leader's Lead block shows `—`.
- Mobile pick rows render the team name as plain text in this task. Wrapping it in a `<a href="{{ url_for('worldcup.team_detail', ...) }}">` is deferred to Task 4 because `url_for()` raises `BuildError` if the endpoint doesn't exist yet (unlike Jinja's `in [...]` endpoint check in the sub-nav, which silently returns false for missing endpoints). Task 4 adds the route AND wraps both the mobile pick card link here and the desktop `_pick_row.html` link.
- Back link copy is "Back to Board" to match Plan 1's sub-nav rename ("Leaderboard" → "Board").

- [ ] **Step 4: Add minimal supporting CSS**

Append to the same `style.css` section as Plan 1's WC additions (search `Spec C — Cross-cutting WC utility classes` to locate, then append after the foundation block):

```css
/* Spec C Plan 2 — player_detail / team_detail hero stat grid.
   NOTE: uses .hero-stat (NOT .stat-block) — the platform .stat-block is a
   later, heavier rule with white-card chrome that collides with the dark
   hero background. Templates must use <div class="hero-stat"> here. */
.player-hero-stats,
.team-hero-stats {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-top: .75rem;
}
.player-hero-stats .hero-stat,
.team-hero-stats .hero-stat {
  display: flex;
  flex-direction: column;
  gap: .2rem;
  min-width: 70px;
}
.player-hero-stats .hero-stat strong,
.team-hero-stats .hero-stat strong {
  font-size: 1.6rem;
  line-height: 1;
  color: var(--wc-white);
  font-weight: 700;
}

/* Back-affordance link — small, bone-mute, hover-bright */
.back-link {
  display: inline-flex;
  align-items: center;
  font-family: 'Teko', sans-serif;
  font-size: .85rem;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--bone-mute);
  text-decoration: none;
}
.back-link:hover { color: var(--wc-white); }

/* Deep-link from a pick row's team name to /worldcup/team/<id> */
.team-link {
  color: inherit;
  text-decoration: none;
  border-bottom: 1px dotted rgba(245, 241, 232, .25);
  transition: border-color var(--transition);
}
.team-link:hover {
  color: var(--wc-white);
  border-bottom-color: var(--wc-red);
}
```

- [ ] **Step 5: Visual smoke**

```bash
FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Visit `/worldcup/leaderboard` → click any player. Verify on mobile (375px) + desktop:
- Hero gradient + new eyebrow ("Rank N" or "Current Leader" gold)
- Stat grid shows Total / Lead / Tiebreak with Teko numerals
- Back link reads "Back to Board"
- Desktop table renders with `_pick_row.html` (Plan 1's reskinned partial)
- Mobile cards include tier dot + tier eyebrow above team name; team name is a dotted-underline link
- Click a mobile team name → currently 404s (route lands in Task 4). For now, expected behavior is *the link exists* (the 404 is acceptable mid-plan)
- Pre-deadline + non-owner → roster-hidden card shows "Roster sealed" eyebrow + lock icon

If the lock card or stat blocks look unstyled, the Plan 1 foundation utility cascade is broken — re-run the verification step from Task 0 step 2.

- [ ] **Step 6: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: pyright 0 errors; all 155 tests pass.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/player_detail.html static/css/style.css
git commit -m "feat(ccc-wc): reskin player_detail.html with Lead-delta hero

Maps wc-player.jsx mock. Hero gains 2-3 stat grid (Total · Lead · Tiebreak)
sourced from new compute_rank_neighbors helper; eyebrow flips gold for
Rank 1 ('Current Leader'). Roster-hidden card gains 'Roster sealed'
eyebrow. Mobile pick cards now deep-link team name to
/worldcup/team/<id> (route lands in Task 4-5; link is forward-compat).
Desktop table inherits Plan 1's reskinned _pick_row.html unchanged.
Back link copy 'Back to Leaderboard' → 'Back to Board' to match
Plan 1 sub-nav rename.

Refs Spec C Plan 2."
```

---

## team_detail — service layer

### Task 3: Add ownership + path-to-crown helpers in a team_detail service module (TDD)

**Files:**
- Create: `games/worldcup/services/team_detail.py`
- Create: `tests/test_worldcup_team_detail_service.py`

> **Plan revision (2026-05-02):** Initial draft of this task used fictional `best_finish` strings (`'advanced_R32'`, etc.) and assumed `team.is_eliminated` reflected KO losses. Both were wrong:
> - `scoring._update_best_finish` writes the bare-stage strings `'group'`, `'R32'`, `'R16'`, `'QF'`, `'SF'`, `'3rd'`, `'runner_up'`, `'champion'` (per `STAGE_ORDER` in `games/worldcup/services/scoring.py`). The `'advanced_*'` form does not exist.
> - `team.is_eliminated` is set ONLY by group-stage advancement (`scoring.py:256/259`); KO losses never update it. Detecting KO elimination requires querying `WorldCupMatch` for the next-stage match the team played and didn't win.
>
> The corrected design below uses the canonical strings, derives KO elimination from the matches table, and disambiguates the `best_finish='SF'` case (intermediate state for both SF winners awaiting Final and SF losers awaiting/exiting 3rd-place playoff).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_team_detail_service.py`:

```python
"""Tests for games/worldcup/services/team_detail helpers."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch, WorldCupPick, WorldCupTeam,
)
from games.worldcup.constants import ADVANCE_GROUP_WINNER, KNOCKOUT_POINTS
from games.worldcup.services.team_detail import (
    compute_team_ownership, current_user_owns_team, compute_path_to_crown,
)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed_team(fifa='USA', tier=1, multiplier=1.0, group='A',
               base=0.0, multiplied=0.0,
               adv=None, finish=None, eliminated=False):
    t = WorldCupTeam(
        fifa_code=fifa, name=fifa, display_name=fifa,
        tier=tier, multiplier=multiplier, confederation='CONCACAF',
        group_letter=group, base_points=base, multiplied_points=multiplied,
        advancement_method=adv, best_finish=finish, is_eliminated=eliminated,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _seed_completed_match(home_id, away_id, stage, winner_id,
                          match_number=49, home_score=0, away_score=1):
    m = WorldCupMatch(
        match_number=match_number, stage=stage,
        home_team_id=home_id, away_team_id=away_id,
        home_score=home_score, away_score=away_score,
        winner_team_id=winner_id, is_completed=True,
    )
    db.session.add(m)
    db.session.commit()
    return m


def _seed_enrollment_with_pick(team_id, tier, username='owner'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pass')
    db.session.add(u)
    db.session.flush()
    e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
    db.session.add(e)
    db.session.flush()
    p = WorldCupPick(enrollment_id=e.id, team_id=team_id, tier=tier)
    db.session.add(p)
    db.session.commit()
    return u.id, e.id


# ── compute_team_ownership ──────────────────────────────────────────────

def test_ownership_pre_deadline_returns_none_for_picker_names(app):
    with app.app_context():
        team = _seed_team()
        _seed_enrollment_with_pick(team.id, tier=1, username='alice')
        _seed_enrollment_with_pick(team.id, tier=1, username='bob')
        result = compute_team_ownership(team.id, deadline_passed=False)
        assert result['picker_names'] is None
        assert result['count'] == 0
        assert result['percent'] == 0.0


def test_ownership_post_deadline_returns_picker_names_and_count(app):
    with app.app_context():
        team = _seed_team()
        _seed_enrollment_with_pick(team.id, tier=1, username='alice')
        _seed_enrollment_with_pick(team.id, tier=1, username='bob')
        # Third enrollment in the pool with NO pick on this team
        u = User(username='carol', email='carol@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.commit()

        result = compute_team_ownership(team.id, deadline_passed=True)
        assert result['count'] == 2
        assert result['percent'] == pytest.approx(66.67, abs=0.01)  # 2 of 3 enrollments
        assert sorted(result['picker_names']) == ['alice', 'bob']


def test_ownership_post_deadline_zero_picks(app):
    with app.app_context():
        team = _seed_team()
        # No enrollments at all → percent must be 0.0, not divide-by-zero
        result = compute_team_ownership(team.id, deadline_passed=True)
        assert result['count'] == 0
        assert result['percent'] == 0.0
        assert result['picker_names'] == []


# ── current_user_owns_team ──────────────────────────────────────────────

def test_current_user_owns_team_true_when_pick_exists(app):
    with app.app_context():
        team = _seed_team()
        user_id, _ = _seed_enrollment_with_pick(team.id, tier=1)
        assert current_user_owns_team(user_id, team.id) is True


def test_current_user_owns_team_false_when_no_pick(app):
    with app.app_context():
        team = _seed_team()
        # User exists with enrollment but no pick on this team
        u = User(username='other', email='other@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.commit()
        assert current_user_owns_team(u.id, team.id) is False


# ── compute_path_to_crown ───────────────────────────────────────────────
# best_finish strings come verbatim from scoring._update_best_finish:
# None | 'group' | 'R32' | 'R16' | 'QF' | 'SF' | '3rd' | 'runner_up' | 'champion'.

def test_path_to_crown_group_in_progress(app):
    """No advancement, no elimination → Group is 'current', rest 'future'."""
    with app.app_context():
        team = _seed_team(multiplier=1.0)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert result['eliminated_at_label'] is None
        assert [s['stage'] for s in result['segments']] == [
            'Group', 'R32', 'R16', 'QF', 'SF', 'Final',
        ]
        assert [s['status'] for s in result['segments']] == [
            'current', 'future', 'future', 'future', 'future', 'future',
        ]
        # Win-out projection: 0 + 4 (group) + 8 + 11 + 15 + 19 + 50 = 107
        assert result['projected_ceiling'] == 107.0


def test_path_to_crown_group_eliminated(app):
    with app.app_context():
        team = _seed_team(multiplier=1.0, finish='group', eliminated=True,
                          base=3.0, multiplied=3.0)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Group Stage'
        assert [s['status'] for s in result['segments']] == [
            'eliminated', 'future', 'future', 'future', 'future', 'future',
        ]
        # Eliminated → ceiling reflects only earned multiplied points
        assert result['projected_ceiling'] == 3.0


def test_path_to_crown_advanced_from_group(app):
    """Cleared group, R32 not yet played: bf=None + advancement_method set."""
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner',
                          base=ADVANCE_GROUP_WINNER)  # 4 pts in base
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'current', 'future', 'future', 'future', 'future',
        ]
        # base=4 includes group-winner bonus; remaining = 8+11+15+19+50 = 103
        assert result['projected_ceiling'] == 107.0


def test_path_to_crown_won_R32(app):
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner', finish='R32',
                          base=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'])
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'current', 'future', 'future', 'future',
        ]


def test_path_to_crown_lost_R16_via_match(app):
    """Won R32, then lost R16 — KO elimination derived from completed match."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='R32',
                          base=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'],
                          multiplied=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'])
        opp = _seed_team(fifa='OPP', group='B')
        _seed_completed_match(team.id, opp.id, stage='R16',
                              winner_id=opp.id, match_number=49)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Round of 16'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'eliminated', 'future', 'future', 'future',
        ]
        # Eliminated → ceiling = multiplied_points (4 + 8 = 12.0)
        assert result['projected_ceiling'] == 12.0


def test_path_to_crown_runner_up(app):
    """Lost the Final → cleared SF, segment 5 'eliminated'."""
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner', finish='runner_up')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Final'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'eliminated',
        ]


def test_path_to_crown_third_place_winner(app):
    """Lost SF, won 3rd-place playoff → cleared QF, SF 'eliminated', Final 'future'.

    The 6-segment shape doesn't include the consolation match; the bonus
    surfaces in projected_ceiling/multiplied_points elsewhere.
    """
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='3rd')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Semifinals'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'eliminated', 'future',
        ]


def test_path_to_crown_champion(app):
    """Won everything — all segments 'won', not eliminated."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='champion')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert result['eliminated_at_label'] is None
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'won',
        ]


def test_path_to_crown_sf_state_with_no_terminal_match(app):
    """bf='SF' before any third_place/final completes → treated as alive at depth=5.

    This covers both the SF winner awaiting Final and the SF loser awaiting
    3rd-place. Display ambiguity is acceptable for this brief intermediate
    window; resolves naturally once a terminal match is recorded.
    """
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='SF')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'current',
        ]


def test_path_to_crown_fourth_place_finisher(app):
    """bf='SF' + completed third_place match → 4th-place finisher.

    A team with bf='3rd' would have won 3rd-place; bf='SF' + completed
    third_place means they LOST 3rd-place (they're the loser, otherwise
    scoring would have updated bf). So they finished 4th: cleared QF,
    eliminated at SF, Final 'future'.
    """
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='SF')
        opp = _seed_team(fifa='OPP', group='B')
        _seed_completed_match(team.id, opp.id, stage='third_place',
                              winner_id=opp.id, match_number=63)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Semifinals'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'eliminated', 'future',
        ]
```

Run:

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_team_detail_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'games.worldcup.services.team_detail'`.

- [ ] **Step 2: Implement the service module**

Create `games/worldcup/services/team_detail.py`:

```python
"""
World Cup Fantasy Pool — Team detail helpers
==============================================
Pure read-only helpers powering the public /worldcup/team/<id> route:
- compute_team_ownership: pick count / percent / picker_names (privacy-gated)
- current_user_owns_team: cheap auth-only check
- compute_path_to_crown: 6-segment knockout path + projected ceiling

Privacy invariant (Spec C D11): pre-deadline, picker_names is None and
count/percent are zero — no roster information leaks before the tournament
begins, mirroring the player_detail.html roster-hiding rule.

best_finish strings consumed here come verbatim from scoring._update_best_finish:
  None | 'group' | 'R32' | 'R16' | 'QF' | 'SF' | '3rd' | 'runner_up' | 'champion'
The 'advanced_*' shape used by an earlier draft of this plan does NOT exist
in the data model. KO elimination is derived from the WorldCupMatch table
because team.is_eliminated is only set during group-stage processing.
"""
from typing import Optional, TypedDict

from sqlalchemy import or_

from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch, WorldCupPick, WorldCupTeam,
)
from games.worldcup.constants import (
    SEASON_YEAR,
    ADVANCE_GROUP_WINNER, KNOCKOUT_POINTS,
)


_SEGMENT_LABELS = ['Group', 'R32', 'R16', 'QF', 'SF', 'Final']
_SEGMENT_DISPLAY = ['Group Stage', 'Round of 32', 'Round of 16',
                    'Quarterfinals', 'Semifinals', 'Final']
# WorldCupMatch.stage value the team plays at each segment-index ahead.
# Index 0 is multi-match group play and is handled via best_finish='group'.
_NEXT_MATCH_STAGE: list[Optional[str]] = [
    None, 'R32', 'R16', 'QF', 'SF', 'final',
]


class TeamOwnership(TypedDict):
    count: int
    percent: float
    picker_names: Optional[list[str]]


class PathSegment(TypedDict):
    stage: str    # 'Group', 'R32', 'R16', 'QF', 'SF', 'Final'
    status: str   # 'won', 'current', 'future', 'eliminated'


class PathToCrown(TypedDict):
    segments: list[PathSegment]
    eliminated: bool
    eliminated_at_label: Optional[str]
    projected_ceiling: float    # multiplied points if team wins out from here


def compute_team_ownership(team_id: int, deadline_passed: bool) -> TeamOwnership:
    """Return ownership stats for one team in the current SEASON_YEAR pool.

    Pre-deadline: count + percent are zero, picker_names is None — strict
    privacy parity with player_detail.html roster-hiding (spec D11).
    Post-deadline: count = picks on this team; percent = count / total
    enrollments in the pool * 100; picker_names is the sorted list of
    display names (falls back to User.username when display_name is null).
    """
    if not deadline_passed:
        return TeamOwnership(count=0, percent=0.0, picker_names=None)

    picks = (
        WorldCupPick.query
        .join(WorldCupEnrollment)
        .filter(
            WorldCupPick.team_id == team_id,
            WorldCupEnrollment.season_year == SEASON_YEAR,
        )
        .all()
    )
    total_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .count()
    )

    count = len(picks)
    percent = round((count / total_enrollments) * 100, 2) if total_enrollments else 0.0
    picker_names = sorted(p.enrollment.get_display_name() for p in picks)
    return TeamOwnership(count=count, percent=percent, picker_names=picker_names)


def current_user_owns_team(user_id: int, team_id: int) -> bool:
    """True iff the user has a pick on this team in the SEASON_YEAR pool."""
    return bool(db.session.query(
        WorldCupPick.query
        .join(WorldCupEnrollment)
        .filter(
            WorldCupEnrollment.user_id == user_id,
            WorldCupEnrollment.season_year == SEASON_YEAR,
            WorldCupPick.team_id == team_id,
        )
        .exists()
    ).scalar())


def compute_path_to_crown(team: WorldCupTeam) -> PathToCrown:
    """Build the 6-segment knockout-path payload.

    Segments are: Group · R32 · R16 · QF · SF · Final.
    Status per segment:
      - 'won':         team has cleared this stage
      - 'current':     team's next stage (only when not eliminated)
      - 'eliminated':  the segment where the team was knocked out
      - 'future':      stage hasn't been reached yet

    projected_ceiling: if the team wins every remaining segment, what total
    multiplied score does their team contribute? team.base_points already
    holds everything earned to date (group match points, advancement bonus,
    KO wins), so we add only the unearned remainder before multiplying.
    Eliminated teams' ceiling = team.multiplied_points (no further upside).
    """
    cleared, eliminated_at = _path_status(team)
    eliminated = eliminated_at is not None

    segments: list[PathSegment] = []
    for i, label in enumerate(_SEGMENT_LABELS):
        if i < cleared:
            status = 'won'
        elif eliminated and i == eliminated_at:
            status = 'eliminated'
        elif i == cleared and not eliminated:
            status = 'current'
        else:
            status = 'future'
        segments.append(PathSegment(stage=label, status=status))

    eliminated_at_label = (
        _SEGMENT_DISPLAY[eliminated_at]
        if eliminated and eliminated_at is not None
        else None
    )

    if eliminated:
        projected_ceiling = float(team.multiplied_points)
    else:
        # Sum unearned base contributions assuming team wins out.
        remaining_base = 0.0
        if cleared == 0:
            # Group still in progress — assume group winner advancement bonus.
            remaining_base += ADVANCE_GROUP_WINNER
        # Knockout match wins yet to earn:
        #   cleared=1 (cleared group)         → R32, R16, QF, SF
        #   cleared=2 (won R32)               → R16, QF, SF
        #   cleared=k                         → keys at index >= k-1
        knockout_keys = ['R32', 'R16', 'QF', 'SF']
        for i, key in enumerate(knockout_keys):
            if (i + 1) >= cleared:
                remaining_base += KNOCKOUT_POINTS[key]
        # Champion bonus only if not already champion.
        if cleared < 6:
            remaining_base += KNOCKOUT_POINTS['champion']
        projected_ceiling = round(
            (float(team.base_points) + remaining_base) * team.multiplier, 1,
        )

    return PathToCrown(
        segments=segments,
        eliminated=eliminated,
        eliminated_at_label=eliminated_at_label,
        projected_ceiling=projected_ceiling,
    )


def _path_status(team: WorldCupTeam) -> tuple[int, Optional[int]]:
    """Return (cleared_depth, eliminated_at_index).

    cleared_depth: how many of the 6 segments the team has won (0..6).
    eliminated_at_index: the segment index where the team was knocked out,
    or None if still alive / champion.

    Sources of truth:
    - Terminal best_finish values ('champion', 'runner_up', '3rd', 'group')
      resolve directly without a query.
    - For intermediate KO states (best_finish in {'R32','R16','QF','SF'} or
      bf=None+advancement_method), elimination is derived from a completed
      WorldCupMatch at the team's next stage where they are not the winner.
      team.is_eliminated cannot be used because scoring only sets it during
      group-stage processing (scoring.py:256/259) — never for KO losses.
    """
    bf = team.best_finish

    # Terminal states resolved directly.
    if bf == 'champion':
        return (6, None)
    if bf == 'runner_up':
        return (5, 5)            # cleared SF, lost Final
    if bf == '3rd':
        return (4, 4)            # cleared QF, lost SF (won 3rd-place playoff)
    if bf == 'group':
        return (0, 0)            # group eliminated

    # bf='SF' is intermediate: SF winner awaiting Final, OR SF loser
    # awaiting/exiting 3rd-place playoff. Disambiguate via matches:
    # any completed third_place match for this team means they lost it
    # (otherwise bf would be '3rd') → 4th-place finisher.
    if bf == 'SF':
        completed_third = WorldCupMatch.query.filter(
            WorldCupMatch.stage == 'third_place',
            WorldCupMatch.is_completed.is_(True),
            or_(
                WorldCupMatch.home_team_id == team.id,
                WorldCupMatch.away_team_id == team.id,
            ),
        ).first()
        if completed_third is not None:
            return (4, 4)
        return (5, None)

    # Cleared depth from bf + advancement_method.
    if bf == 'QF':
        cleared = 4
    elif bf == 'R16':
        cleared = 3
    elif bf == 'R32':
        cleared = 2
    elif bf is None and team.advancement_method:
        cleared = 1
    else:
        # bf is None and no advancement_method → group stage in progress
        return (0, None)

    # KO elimination check: completed match at the next stage where the team
    # didn't win (winner_team_id is the opponent, or NULL for unresolved draws).
    next_stage = _NEXT_MATCH_STAGE[cleared]
    if next_stage is None:
        return (cleared, None)
    elim = WorldCupMatch.query.filter(
        WorldCupMatch.stage == next_stage,
        WorldCupMatch.is_completed.is_(True),
        or_(
            WorldCupMatch.home_team_id == team.id,
            WorldCupMatch.away_team_id == team.id,
        ),
        or_(
            WorldCupMatch.winner_team_id != team.id,
            WorldCupMatch.winner_team_id.is_(None),
        ),
    ).first()
    if elim is not None:
        return (cleared, cleared)
    return (cleared, None)
```

- [ ] **Step 3: Run tests — they should pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_team_detail_service.py -v
```

Expected: all 15 tests PASS (5 ownership + owns + 10 path-to-crown).

If `test_path_to_crown_group_in_progress` fails on `projected_ceiling == 107.0`, double-check: ADVANCE_GROUP_WINNER (4) + R32 (8) + R16 (11) + QF (15) + SF (19) + champion (50) = 107.

- [ ] **Step 4: Run pyright + full test suite**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 errors; **170 tests pass** (155 + 15 new).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/team_detail.py tests/test_worldcup_team_detail_service.py
git commit -m "feat(ccc-wc): add team_detail service helpers (ownership + path-to-crown)

- compute_team_ownership(team_id, deadline_passed): privacy-gated; pre-deadline
  returns count=0/percent=0/picker_names=None per spec D11.
- current_user_owns_team(user_id, team_id): cheap exists() check.
- compute_path_to_crown(team): 6-segment Group/R32/R16/QF/SF/Final payload
  driven by canonical best_finish strings ('group'/'R32'/.../'champion'
  per scoring._update_best_finish). KO elimination derived from completed
  WorldCupMatch entries at the team's next stage, since scoring only sets
  team.is_eliminated during group-stage processing. bf='SF' disambiguates
  4th-place finishers from SF winners by checking for a completed
  third_place match. projected_ceiling is base_points + unearned win-out
  contributions, multiplied by tier multiplier (or multiplied_points if
  already eliminated).

Refs Spec C Plan 2."
```

---

## team_detail — route + template

### Task 4: Add the `team_detail` route + initial template scaffold (TDD)

**Files:**
- Modify: `games/worldcup/routes.py`
- Create: `games/worldcup/templates/worldcup/team_detail.html`
- Create: `tests/test_worldcup_team_detail.py`

- [ ] **Step 1: Write the failing route tests**

Create `tests/test_worldcup_team_detail.py`:

```python
"""Tests for the public /worldcup/team/<int:team_id> route."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupPick,
)


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


def _seed_team(app, fifa='USA'):
    with app.app_context():
        t = WorldCupTeam(
            fifa_code=fifa, name=fifa, display_name=fifa,
            tier=1, multiplier=1.0, confederation='CONCACAF',
            group_letter='A',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def _seed_owner_with_pick(app, team_id, username='owner'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.flush()
        p = WorldCupPick(enrollment_id=e.id, team_id=team_id, tier=1)
        db.session.add(p)
        db.session.commit()
        return u.id


def test_team_detail_returns_200_for_valid_team(client, app):
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200


def test_team_detail_returns_404_for_invalid_team(client, app):
    resp = client.get('/worldcup/team/99999')
    assert resp.status_code == 404


def test_team_detail_public_no_auth_required(client, app):
    """Anonymous users see the page (matches leaderboard/stats access policy)."""
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Response should contain the team's display name
    assert b'USA' in resp.data


def test_team_detail_renders_team_name_and_fifa_code(client, app):
    team_id = _seed_team(app, fifa='ENG')
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'ENG' in resp.data
```

Run:

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_team_detail.py -v
```

Expected: FAIL — `404` on every request (route doesn't exist yet) or `TemplateNotFound`.

- [ ] **Step 2: Add the route**

In `games/worldcup/routes.py`, add imports near the existing top-block (around line 26 after the scoring imports):

```python
from sqlalchemy import or_
from games.worldcup.services.team_detail import (
    compute_team_ownership, current_user_owns_team, compute_path_to_crown,
)
```

`or_` may already be present via `from sqlalchemy import func` — just extend that line to `from sqlalchemy import func, or_` if so.

Then append the new route immediately after the existing `player_detail()` block (after line ~410):

```python
@worldcup_bp.route('/team/<int:team_id>')
def team_detail(team_id):
    """Public per-team surface: fixtures, score events, ownership, path to crown.

    No @login_required — matches access policy of leaderboard/stats. Pre-deadline,
    ownership data is strictly hidden (no count, no names) per spec D11.
    """
    team = db.get_or_404(WorldCupTeam, team_id)

    matches = (
        WorldCupMatch.query
        .filter(or_(
            WorldCupMatch.home_team_id == team_id,
            WorldCupMatch.away_team_id == team_id,
        ))
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    score_events = compute_team_score_events(team)

    # Per-match points map (match_id → sum of base_points for events on that match).
    # 'team.multiplier' applied at display time only; SSoT keeps base in events.
    points_by_match: dict[int, float] = {}
    for ev in score_events:
        if ev.match_id is not None:
            points_by_match[ev.match_id] = points_by_match.get(ev.match_id, 0.0) + ev.base_points

    # Pre-format kickoff dates in CT for the template — kickoff_utc is naive UTC
    # in the DB, so build a (match.id → CT-aware datetime) map here rather than
    # smuggling tzinfo logic into Jinja.
    from zoneinfo import ZoneInfo
    match_dates_ct: dict[int, str] = {}
    for m in matches:
        if m.kickoff_utc:
            aware = m.kickoff_utc.replace(tzinfo=ZoneInfo('UTC')).astimezone(WORLDCUP_TZ)
            match_dates_ct[m.id] = aware.strftime('%b %-d')

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    ownership = compute_team_ownership(team_id, deadline_passed)

    user_owns = (
        current_user.is_authenticated
        and current_user_owns_team(current_user.id, team_id)
    )

    path = compute_path_to_crown(team)

    # Picker links: post-deadline only, list of (display_name, enrollment_id) for "Who Picked This".
    picker_links: list[tuple[str, int]] = []
    if deadline_passed:
        picks = (
            WorldCupPick.query
            .join(WorldCupEnrollment)
            .filter(
                WorldCupPick.team_id == team_id,
                WorldCupEnrollment.season_year == SEASON_YEAR,
            )
            .all()
        )
        picker_links = sorted(
            (p.enrollment.get_display_name(), p.enrollment.id) for p in picks
        )

    # Inline _stage_label so we don't depend on core/main internals from a game blueprint.
    # If Plan 4 lifts _stage_label() into games/worldcup/services/stage.py, swap to that import.
    from core.main.home_context import _stage_label

    return render_template('worldcup/team_detail.html',
        team=team,
        matches=matches,
        points_by_match=points_by_match,
        match_dates_ct=match_dates_ct,
        ownership=ownership,
        user_owns=user_owns,
        deadline_passed=deadline_passed,
        path=path,
        picker_links=picker_links,
        stage_label=_stage_label,
    )
```

Notes:
- `WORLDCUP_TZ` is already imported at the top of routes.py. `WorldCupMatch`, `compute_team_score_events`, `current_user`, `db`, `render_template` are all already imported.
- `_stage_label` import is intentionally inline so anyone reading this route sees the Plan 4 swap-target comment. Per CLAUDE.md, `_stage_label` is the SSoT for `WorldCupMatch.stage` display labels — never use `match.stage|title` in the template.

- [ ] **Step 3: Add the placeholder template**

Create `games/worldcup/templates/worldcup/team_detail.html` with a minimal scaffold so the tests pass. The full sections are built out in Tasks 5–6.

```jinja
{% extends "base.html" %}
{% block title %}{{ team.display_name }} ({{ team.fifa_code }}) — World Cup Fantasy Pool{% endblock %}

{% block content %}
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow wc-eyebrow-red">{{ team.fifa_code }} · Group {{ team.group_letter }}</span>
    <h1>
      <span class="me-2 fs-1">{{ team.flag_emoji }}</span>{{ team.display_name }}
    </h1>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-8">
      <div class="mb-3">
        <a href="{{ url_for('worldcup.leaderboard') }}" class="back-link">
          <i class="bi bi-arrow-left me-1"></i>Back to Board
        </a>
      </div>
      <p class="text-muted small">Team detail under construction (Plan 2 Tasks 5–6).</p>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the route tests — they should pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_team_detail.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Wire the deferred mobile pick-card team-link in `player_detail.html`**

Task 2 left the mobile pick-card team name as plain text because `url_for('worldcup.team_detail', ...)` raises `BuildError` when the endpoint doesn't exist. Now that the route is in place, wrap the team name in the link.

In `games/worldcup/templates/worldcup/player_detail.html`, find:

```jinja
                <span class="pick-team d-block mt-1">
                  {{ pick.team.flag_emoji }} {{ pick.team.display_name }}
                  <small class="text-muted">Grp {{ pick.team.group_letter }}</small>
                </span>
```

Replace with:

```jinja
                <span class="pick-team d-block mt-1">
                  <a href="{{ url_for('worldcup.team_detail', team_id=pick.team_id) }}"
                     class="team-link">
                    {{ pick.team.flag_emoji }} {{ pick.team.display_name }}
                  </a>
                  <small class="text-muted">Grp {{ pick.team.group_letter }}</small>
                </span>
```

(The desktop equivalent in `_pick_row.html` is wired in Task 7.)

- [ ] **Step 6: Verify the sub-nav Board pill auto-activates + mobile pick-card link works**

Start the dev server and visit `/worldcup/team/1` (or pick any valid team id from `flask worldcup status`):

```bash
FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

In the browser, confirm:
- Page renders with hero (flag, name, eyebrow)
- The `Board` pill in the WC sub-nav is highlighted (Plan 1's forward-reference now resolves)
- Visit `/worldcup/leaderboard/<id>` for an enrollment with submitted picks (use `WC_FAKE_NOW` post-deadline if needed) — mobile pick-card team names are now dotted-underline links to `/worldcup/team/<team_id>`; clicking navigates correctly with no `BuildError`

- [ ] **Step 7: Run pyright + full test suite**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 errors; 174 tests pass (170 + 4 new).

- [ ] **Step 8: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/team_detail.html games/worldcup/templates/worldcup/player_detail.html tests/test_worldcup_team_detail.py
git commit -m "feat(ccc-wc): add public worldcup.team_detail route + scaffold template

GET /worldcup/team/<int:team_id> — public, no @login_required (matches
leaderboard/stats access policy). Computes match log via or_() filter,
score_events via compute_team_score_events SSoT, points_by_match map for
template rendering, ownership via privacy-gated helper, user_owns flag,
path-to-crown segments + projected ceiling, and picker_links list
(empty pre-deadline).

Wires the deferred mobile pick-card team-link in player_detail.html
(Task 2 left it plain text because url_for() raises BuildError on
missing endpoints; route now exists).

Sub-nav Board pill now auto-activates on /worldcup/team/<id> (Plan 1's
forward-compat reference resolves with this commit).

Refs Spec C Plan 2."
```

---

### Task 5: Build out `team_detail.html` — Hero, Ownership ribbon, Tournament Fixtures

> **REQUIRED PLUGIN: `frontend-design`.** This task builds net-new UI surfaces (`team_detail.html` is a brand-new page, not an existing template being reskinned) where the design bundle (`wc-team.jsx`) is mobile-only and the implementer has real latitude on desktop. Invoke the `frontend-design` skill at the start of this task and use its judgment for the hero proportions, ownership-ribbon visual hierarchy, fixture-row grid rhythm, and any class-naming choices that risk colliding with existing platform components (cf. Plan 2 Task 2 lesson — `.stat-block` was reused with confusing results; use unique names like `.hero-stat`). The class names and CSS in the steps below are baseline starting points, not final answers — `frontend-design` may iterate on padding, type scale, color tinting, hover affordances, etc.

**Files:**
- Modify: `games/worldcup/templates/worldcup/team_detail.html`
- Modify: `static/css/style.css` (append)

- [ ] **Step 1: Replace the placeholder template body**

Replace the entire contents of `games/worldcup/templates/worldcup/team_detail.html` with:

```jinja
{% extends "base.html" %}
{% block title %}{{ team.display_name }} ({{ team.fifa_code }}) — World Cup Fantasy Pool{% endblock %}

{% block content %}
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow wc-eyebrow-red">
      {{ team.fifa_code }} · Group {{ team.group_letter }} · Tier {{ team.tier }}
    </span>
    <h1 class="d-flex align-items-center gap-3">
      <span class="team-hero-flag">{{ team.flag_emoji }}</span>
      {{ team.display_name }}
    </h1>
    <div class="team-hero-stats">
      <div class="hero-stat">
        <span class="wc-eyebrow">Tier</span>
        <strong>
          <span class="wc-tier-dot wc-tier-dot-{{ team.tier }}"></span>
          <span class="wc-numeral">{{ team.tier }}</span>
        </strong>
      </div>
      <div class="hero-stat">
        <span class="wc-eyebrow">Multiplier</span>
        <strong><span class="wc-multiplier-chip">×{{ team.multiplier }}</span></strong>
      </div>
      <div class="hero-stat">
        <span class="wc-eyebrow">Base</span>
        <strong class="wc-numeral">{{ "%.1f"|format(team.base_points) }}</strong>
      </div>
      <div class="hero-stat">
        <span class="wc-eyebrow">Scored</span>
        <strong class="wc-numeral">{{ "%.1f"|format(team.multiplied_points) }}</strong>
      </div>
    </div>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-8">

      <div class="mb-3">
        <a href="{{ url_for('worldcup.leaderboard') }}" class="back-link">
          <i class="bi bi-arrow-left me-1"></i>Back to Board
        </a>
      </div>

      {# ── Ownership ribbon ────────────────────────────────────────────── #}
      {# Three branches per spec D11:
           1. user_owns           → red ribbon with "You Own This Nation" + count/percent
           2. deadline_passed     → ribbon with count/percent only (no names here)
           3. pre-deadline + non-owner → ribbon entirely hidden #}
      {% if user_owns or (deadline_passed and ownership.count > 0) %}
      <div class="ownership-ribbon {% if user_owns %}ownership-ribbon-owned{% endif %} animate-in mb-4">
        {% if user_owns %}
        <div>
          <span class="wc-eyebrow wc-eyebrow-red">You Own This Nation</span>
          <div class="small text-muted mt-1">Count this scoreline toward your roster.</div>
        </div>
        {% else %}
        <div>
          <span class="wc-eyebrow">Roster ownership</span>
          <div class="small text-muted mt-1">Across the Club this tournament.</div>
        </div>
        {% endif %}
        {% if deadline_passed %}
        <div class="text-end">
          <div class="wc-numeral" style="font-size:1.4rem;">{{ ownership.count }}</div>
          <div class="wc-eyebrow">{{ "%.1f"|format(ownership.percent) }}% of Club</div>
        </div>
        {% endif %}
      </div>
      {% endif %}

      {# ── Tournament Fixtures ─────────────────────────────────────────── #}
      <section class="mb-4">
        <span class="wc-eyebrow">Tournament fixtures</span>
        <h3 class="mb-3">Match log</h3>

        {% if matches %}
        <div class="card border-0 shadow-sm wc-card wc-card-flush">
          <div class="card-body p-0">
            <ul class="list-unstyled m-0 fixture-list">
              {% set ns = namespace(next_set=false) %}
              {% for match in matches %}
                {% set is_team_home = match.home_team_id == team.id %}
                {% set opponent = match.away_team if is_team_home else match.home_team %}
                {% set match_pts = points_by_match.get(match.id, 0.0) %}
                {# Mark first not-completed match as "Next" #}
                {% set is_next = (not match.is_completed) and (not ns.next_set) %}
                {% if is_next %}{% set ns.next_set = true %}{% endif %}
                <li class="fixture-row {% if is_next %}fixture-row-next{% endif %}">
                  <div class="fixture-stage">
                    <span class="wc-eyebrow">{{ stage_label(match.stage) }}</span>
                    {% if match_dates_ct.get(match.id) %}
                    <small class="text-muted d-block">{{ match_dates_ct[match.id] }}</small>
                    {% endif %}
                  </div>
                  <div class="fixture-opponent">
                    <span class="text-muted small me-1">{% if is_team_home %}vs{% else %}@{% endif %}</span>
                    {% if opponent %}
                      <span class="me-1">{{ opponent.flag_emoji }}</span>{{ opponent.fifa_code }}
                    {% else %}
                      <span class="text-muted">TBD</span>
                    {% endif %}
                  </div>
                  <div class="fixture-result wc-numeral">
                    {% if match.is_completed %}
                      {% if is_team_home %}{{ match.home_score }}–{{ match.away_score }}{% else %}{{ match.away_score }}–{{ match.home_score }}{% endif %}
                    {% else %}
                      <span class="text-muted">—</span>
                    {% endif %}
                  </div>
                  <div class="fixture-pts wc-numeral {% if match_pts > 0 %}text-success{% elif match_pts < 0 %}text-danger{% endif %}">
                    {% if match.is_completed %}
                      {{ "+%.1f"|format(match_pts) if match_pts >= 0 else "%.1f"|format(match_pts) }}
                    {% else %}
                      <span class="text-muted">—</span>
                    {% endif %}
                  </div>
                  {% if is_next %}
                  <div class="fixture-next-pip wc-eyebrow wc-eyebrow-red">Next</div>
                  {% endif %}
                </li>
              {% endfor %}
            </ul>
          </div>
        </div>
        {% else %}
        <p class="text-muted">No fixtures available.</p>
        {% endif %}
      </section>

      {# ── Path to the Crown (Task 6) ──────────────────────────────────── #}
      {# Path-to-crown section is added in Task 6. #}

      {# ── Who Picked This (Task 6, post-deadline only) ─────────────────── #}
      {# Picker list section is added in Task 6. #}

    </div>
  </div>
</div>
{% endblock %}
```

A note on the kickoff timezone: `WorldCupMatch.kickoff_utc` is a naive `datetime` stored as UTC (see `models.py`). Task 4's route pre-formats CT date strings into `match_dates_ct` and passes that map to the template, so the template stays free of `ZoneInfo` and `astimezone()` plumbing.

- [ ] **Step 2: Append supporting CSS**

Append to `static/css/style.css` immediately below the Plan 2 Task 2 additions (after `.team-link:hover { ... }`):

```css
/* Spec C Plan 2 — team_detail hero + ownership ribbon + fixture list */
.team-hero-flag {
  font-size: 2.4rem;
  line-height: 1;
}

/* Ownership ribbon */
.ownership-ribbon {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: .85rem 1rem;
  border: 1px solid rgba(245, 241, 232, .1);
  border-radius: 6px;
  background: rgba(0, 17, 46, .6);
}
.ownership-ribbon-owned {
  border-color: var(--wc-red);
  background: linear-gradient(90deg,
              rgba(191, 10, 48, .15) 0%,
              rgba(0, 17, 46, .6) 100%);
}

/* Fixture row grid */
.fixture-list { padding: 0; }
.fixture-row {
  display: grid;
  grid-template-columns: 110px 1fr 60px 60px;
  gap: .75rem;
  align-items: center;
  padding: .65rem 1rem;
  border-bottom: 1px solid rgba(245, 241, 232, .05);
  position: relative;
}
.fixture-row:last-child { border-bottom: none; }
.fixture-row-next { background: rgba(191, 10, 48, .08); }
.fixture-stage { line-height: 1.2; }
.fixture-result { text-align: right; }
.fixture-pts { text-align: right; font-weight: 700; }
.fixture-next-pip {
  position: absolute;
  top: 4px;
  right: 6px;
  font-size: .6rem;
}

@media (max-width: 575.98px) {
  .fixture-row {
    grid-template-columns: 80px 1fr 50px 50px;
    padding: .55rem .75rem;
    gap: .5rem;
  }
}
```

- [ ] **Step 3: Visual smoke**

Visit `/worldcup/team/<id>` for a few teams. Verify:
- Hero shows flag, name, eyebrow with FIFA · Group · Tier; stat grid Tier/Mult/Base/Scored
- Ownership ribbon: hidden pre-deadline for non-owners; visible post-deadline; red-tinted for the logged-in owner
- Fixture list shows match log in match-number order; "Next" pip appears on the very first not-completed fixture; completed matches show score and points awarded; future matches show `—`

If `worldcup_tz` raises a Jinja error: it's the cleverness in the original kickoff line. Switch to the cleaner form noted above.

- [ ] **Step 4: Run pyright + full test suite**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 errors; 167 tests pass.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/templates/worldcup/team_detail.html static/css/style.css
git commit -m "feat(ccc-wc): build team_detail hero + ownership ribbon + fixture log

Hero shows flag, FIFA·Group·Tier eyebrow, 4-stat grid (Tier·Mult·Base·Scored).
Ownership ribbon: hidden pre-deadline for non-owners; visible post-deadline;
red-tinted 'You Own This Nation' for the logged-in owner. Fixture list shows
chronological match log (via stage_label SSoT), opponent flag/code, score,
points awarded per match (sourced from points_by_match map), 'Next' pip on
the first not-completed match.

Refs Spec C Plan 2."
```

---

### Task 6: Add Path to the Crown + Who Picked This sections + privacy tests

> **REQUIRED PLUGIN: `frontend-design`.** Continue using `frontend-design` from Task 5 — Path-to-Crown is the most distinctive component in Plan 2 (6 stage segments × 4 statuses = lots of room for design choices). The default segment treatment in the steps below (flex row of bordered tiles) is a starting point. `frontend-design` should evaluate alternatives like a connected-arrow timeline, gradient-tinted progression, micro-icons per stage, etc., and pick whichever best reads at both 375px and 1280px. Same applies to the Who Picked This list — a grid of pill-links is the baseline; the skill may push for richer treatments (avatars inline, alphabetical group headings, etc.) if they hold up. Tests in this task lock in **behavior** (privacy gates, render conditions, parity) — they should remain green regardless of which visual treatment `frontend-design` lands on.

**Files:**
- Modify: `games/worldcup/templates/worldcup/team_detail.html`
- Modify: `tests/test_worldcup_team_detail.py` (add ownership privacy + parity tests)

- [ ] **Step 1: Add Path to the Crown section to the template**

In `team_detail.html`, replace the comment line `{# ── Path to the Crown (Task 6) ──── #}` with:

```jinja
      {# ── Path to the Crown ──────────────────────────────────────────── #}
      <section class="mb-4">
        <span class="wc-eyebrow {% if path.eliminated %}wc-eyebrow-red{% endif %}">
          {% if path.eliminated %}Out of the running{% else %}Path to the Crown{% endif %}
        </span>
        <h3 class="mb-3">
          {% if path.eliminated %}
            Eliminated · {{ path.eliminated_at_label }}
          {% else %}
            Projected ceiling: <span class="wc-numeral">{{ "%.1f"|format(path.projected_ceiling) }}</span>
          {% endif %}
        </h3>
        <div class="path-segments">
          {% for seg in path.segments %}
          <div class="path-segment path-segment-{{ seg.status }}">
            <span class="wc-eyebrow">{{ seg.stage }}</span>
            {% if seg.status == 'won' %}
              <i class="bi bi-check-lg" aria-label="won"></i>
            {% elif seg.status == 'eliminated' %}
              <i class="bi bi-x-lg" aria-label="eliminated"></i>
            {% endif %}
          </div>
          {% endfor %}
        </div>
        {% if not path.eliminated %}
        <p class="text-muted small mt-2 mb-0">
          If <strong>{{ team.fifa_code }}</strong> wins out from here, this is the team's
          maximum possible contribution to a roster.
        </p>
        {% endif %}
      </section>
```

- [ ] **Step 2: Add Who Picked This section to the template**

Replace `{# ── Who Picked This (Task 6, post-deadline only) ── #}` with:

```jinja
      {# ── Who Picked This (post-deadline only — privacy gate per spec D11) ── #}
      {% if deadline_passed and picker_links %}
      <section class="mb-4">
        <span class="wc-eyebrow">Roster overlap</span>
        <h3 class="mb-3">Who Picked This</h3>
        <ul class="picker-list list-unstyled m-0">
          {% for name, enrollment_id in picker_links %}
          <li class="picker-list-item">
            <a href="{{ url_for('worldcup.player_detail', enrollment_id=enrollment_id) }}"
               class="picker-link">{{ name }}</a>
          </li>
          {% endfor %}
        </ul>
      </section>
      {% endif %}
```

- [ ] **Step 3: Append supporting CSS**

Append to `static/css/style.css` (immediately after the Task 5 fixture-row block):

```css
/* Spec C Plan 2 — path-to-crown segments + picker list */
.path-segments {
  display: flex;
  gap: .4rem;
  flex-wrap: wrap;
}
.path-segment {
  flex: 1 1 0;
  min-width: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .15rem;
  padding: .5rem .25rem;
  border: 1px solid rgba(245, 241, 232, .08);
  border-radius: 4px;
  background: rgba(0, 17, 46, .5);
  color: var(--bone-mute);
}
.path-segment-won {
  color: var(--wc-white);
  border-color: rgba(242, 211, 107, .35);
  background: rgba(242, 211, 107, .08);
}
.path-segment-current {
  color: var(--wc-white);
  border-color: var(--wc-red);
  background: rgba(191, 10, 48, .12);
}
.path-segment-eliminated {
  color: var(--bone-mute);
  border-color: var(--wc-red);
  background: rgba(191, 10, 48, .06);
}

.picker-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: .35rem .5rem;
}
.picker-list-item .picker-link {
  display: inline-block;
  padding: .25rem .5rem;
  color: var(--wc-white);
  text-decoration: none;
  border: 1px solid rgba(245, 241, 232, .08);
  border-radius: 4px;
  font-size: .9rem;
}
.picker-list-item .picker-link:hover {
  border-color: var(--wc-red);
}
```

- [ ] **Step 4: Add privacy + parity tests**

Append to `tests/test_worldcup_team_detail.py`:

```python
def test_team_detail_ownership_hidden_pre_deadline(client, app):
    """Pre-deadline + non-owner: no ownership ribbon, no count, no picker names."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # No ownership ribbon block content
    assert b'You Own This Nation' not in resp.data
    assert b'Roster ownership' not in resp.data
    assert b'Who Picked This' not in resp.data
    # Specifically: 'alice' must not appear in the response
    assert b'alice' not in resp.data
    # Path-to-crown section still renders (it's not gated by deadline)
    assert b'Path to the Crown' in resp.data or b'Out of the running' in resp.data


def test_team_detail_ownership_visible_post_deadline(client, app):
    """Post-deadline + non-owner: ribbon shows count/percent; picker list renders."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    _seed_owner_with_pick(app, team_id, username='bob')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'Roster ownership' in resp.data
    assert b'Who Picked This' in resp.data
    assert b'alice' in resp.data
    assert b'bob' in resp.data


def test_team_detail_user_owns_ribbon(client, app):
    """Authenticated user with a pick on this team sees red 'You Own This Nation' ribbon."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data


def test_team_detail_user_owns_ribbon_pre_deadline(client, app):
    """Even pre-deadline, the owner sees their own 'You Own This Nation' ribbon
    (no privacy concern — it's their own pick)."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data
    # But ownership counts/names of OTHERS still hidden pre-deadline
    assert b'Who Picked This' not in resp.data


def test_team_detail_match_log_includes_all_team_fixtures(client, app):
    """Both home and away fixtures appear in the match log."""
    team_id = _seed_team(app, fifa='USA')
    other_id = _seed_team(app, fifa='ENG')
    with app.app_context():
        # Match where USA is home, vs ENG
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=team_id, away_team_id=other_id,
            home_score=2, away_score=1, is_completed=True,
        )
        # Match where USA is away, vs ENG
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='A',
            home_team_id=other_id, away_team_id=team_id,
            home_score=0, away_score=3, is_completed=True,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Both fixture lines should be visible (each has the opponent's FIFA code)
    # Two ENG fixture rows means 'ENG' appears at least twice in the response.
    assert resp.data.count(b'ENG') >= 2


def test_team_detail_score_events_match_canonical_helper(client, app):
    """Sum of displayed per-match points equals compute_team_score_events total — SSoT parity."""
    from games.worldcup.services.scoring import compute_team_score_events

    team_id = _seed_team(app, fifa='USA')
    with app.app_context():
        from games.worldcup.models import WorldCupTeam
        team = db.session.get(WorldCupTeam, team_id)
        # Simulate a completed group win for USA
        opponent = WorldCupTeam(
            fifa_code='ENG', name='ENG', display_name='ENG',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='A',
        )
        db.session.add(opponent)
        db.session.flush()
        m = WorldCupMatch(
            match_number=10, stage='group', group_letter='A',
            home_team_id=team.id, away_team_id=opponent.id,
            home_score=2, away_score=0, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        # Update USA group_wins to reflect the result for compute_team_score_events
        team.group_wins = 1
        team.base_points = 3.0  # GROUP_WIN
        db.session.commit()

        canonical_total = sum(ev.base_points for ev in compute_team_score_events(team))

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # The hero's "Base" stat block should display the canonical total
    base_str = "%.1f" % canonical_total
    assert base_str.encode() in resp.data
```

Run the tests:

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_team_detail.py -v
```

Expected: all 10 tests PASS (4 from Task 4 + 6 new).

If `test_team_detail_ownership_hidden_pre_deadline` fails because the team has no path data and `Path to the Crown` doesn't render, double-check that the Path section is unconditionally included (only the *content* branches on `path.eliminated`, the section header always renders).

- [ ] **Step 5: Run pyright + full test suite**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 errors; 173 tests pass (167 + 6 new).

- [ ] **Step 6: Visual smoke**

Visit a few `/worldcup/team/<id>` pages. Verify:
- **Pre-deadline, anonymous or non-owner**: Path-to-crown section visible; Who-Picked-This absent; ownership ribbon absent
- **Pre-deadline, logged-in owner**: red "You Own This Nation" ribbon; Who-Picked-This still absent
- **Post-deadline, anonymous**: ribbon shows count/percent; Who-Picked-This shows alphabetized picker links to `/worldcup/player/<id>`
- **Post-deadline, logged-in owner**: red ribbon + Who-Picked-This both visible
- **Team eliminated** (manually set `is_eliminated=True` on a team in dev DB if needed): Path section heading reads "Eliminated · {{ stage }}" with the segment marked accordingly
- **Path segments**: 6 segments (Group, R32, R16, QF, SF, Final); won segments show ✓; current segment red-tinted; future segments dim

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/templates/worldcup/team_detail.html static/css/style.css tests/test_worldcup_team_detail.py
git commit -m "feat(ccc-wc): add path-to-crown + who-picked-this sections to team_detail

Path to the Crown: 6 stage segments (Group · R32 · R16 · QF · SF · Final)
with per-segment status (won/current/future/eliminated). Headline shows
either projected ceiling (alive teams) or 'Eliminated · stage' (out teams),
sourced from compute_path_to_crown helper.

Who Picked This: post-deadline only (privacy invariant per spec D11),
alphabetized picker links to /worldcup/player/<enrollment_id>.

Adds 6 new tests covering ownership privacy gating (pre/post deadline),
owner ribbon visibility (auth + ownership flag), match log home+away
coverage, and score-event parity against compute_team_score_events SSoT.

Refs Spec C Plan 2."
```

---

## Wire deep-link from desktop pick rows

### Task 7: Add "View team →" deep-link to `_pick_row.html`

The desktop table rendered by `picks.html` (post-deadline) and `player_detail.html` uses the shared `_pick_row.html` partial. Mobile cards in `player_detail.html` already linked the team name to `team_detail` in Task 2. This task adds the equivalent affordance to the desktop partial.

**Files:**
- Modify: `games/worldcup/templates/worldcup/_pick_row.html`

- [ ] **Step 1: Re-read the partial**

```bash
cat games/worldcup/templates/worldcup/_pick_row.html
```

Expected: shows the structure shipped by Plan 1 (5-cell `<tr>` + accordion `<tr>` with the events list).

- [ ] **Step 2: Wrap the team display name in a deep-link**

Find the line:

```jinja
    <span class="fw-medium">{{ pick.team.display_name }}</span>
```

Replace with:

```jinja
    <a href="{{ url_for('worldcup.team_detail', team_id=pick.team_id) }}"
       class="fw-medium team-link">{{ pick.team.display_name }}</a>
```

The accordion's click handler in `_pick_accordion_script.html` is bound to `.pick-accordion-toggle` (the chevron button), not to the row or the team-name span. So no `stopPropagation` is needed — the link click navigates without triggering the toggle.

- [ ] **Step 3: Visual smoke**

Visit `/worldcup/picks` (post-deadline) and `/worldcup/player/<id>` (post-deadline) on desktop. For each pick row:
- The team display name is now a dotted-underline link (uses the `.team-link` style added in Task 2)
- Clicking the team name navigates to `/worldcup/team/<team_id>`
- Clicking the chevron still expands the row (the toggle button has its own click handler; the team-name link is a sibling element, not a parent of the toggle)

- [ ] **Step 4: Run pyright + tests**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 errors; 173 tests still pass.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/templates/worldcup/_pick_row.html
git commit -m "feat(ccc-wc): deep-link team name in _pick_row.html to team_detail

Wraps pick.team.display_name in <a href=url_for('worldcup.team_detail')>.
The accordion toggle handler is bound to the chevron button, not the row,
so the link does not interfere with expand/collapse behavior. Mirrors
the mobile-card link in player_detail.html.

Refs Spec C Plan 2."
```

---

## Final verification + PR

### Task 8: End-to-end verification + open PR

- [ ] **Step 1: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -v
```

Expected: 173 tests pass (150 baseline + 5 ranking + 8 team_detail_service + 10 team_detail route).

- [ ] **Step 2: Run pyright on the entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 3: Manual visual checklist**

Walk through each touched surface in a browser at both 375px (mobile) and 1280px (desktop). Use `WC_FAKE_NOW` in dev to flip pre/post deadline as needed:

```bash
# Pre-deadline
WC_FAKE_NOW=2026-06-10T00:00:00+00:00 FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# Post-deadline (in another shell)
WC_FAKE_NOW=2026-06-15T00:00:00+00:00 FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

| Route + state | Verify |
|---|---|
| `/worldcup/player/<id>` (any rank) | New hero with eyebrow ("Rank N" or "Current Leader"), 2-3 stat grid, "Back to Board" link |
| `/worldcup/player/<id>` (rank 1) | Eyebrow turns gold, lead delta shows `—` |
| `/worldcup/player/<id>` mobile | Pick-card team names dotted-underline → team_detail; tier-dot + eyebrow above team name |
| `/worldcup/team/<id>` (any team) | Hero with flag/name/eyebrow + 4-stat grid; Path-to-Crown 6 segments; sub-nav `Board` pill highlighted |
| `/worldcup/team/<id>` pre-deadline + anonymous | Ownership ribbon hidden; Who-Picked-This absent |
| `/worldcup/team/<id>` pre-deadline + logged-in owner | Red ribbon "You Own This Nation"; Who-Picked-This still absent |
| `/worldcup/team/<id>` post-deadline + anonymous | Ribbon shows count + percent; Who-Picked-This list visible (alphabetized) |
| `/worldcup/team/<id>` post-deadline + logged-in owner | Red ribbon + Who-Picked-This both visible |
| `/worldcup/team/<id>` (team eliminated) | Path heading "Eliminated · stage"; segment for elimination round red-bordered |
| `/worldcup/team/99999` | 404 |
| `/worldcup/picks` post-deadline desktop | Pick row team name dotted-underline → `/worldcup/team/<id>`; chevron accordion still expands/collapses |
| `/worldcup/player/<id>` post-deadline desktop | Same desktop pick-row deep-link |

Mobile-specific:
- 375px viewport: hero stat grids wrap cleanly; ribbon stays single-row; fixture rows compact gracefully
- Sub-nav: 6 pills still fit on one row (Plan 1 invariant — should not regress)

- [ ] **Step 4: Push the branch**

```bash
git push -u origin redesign/ccc-worldcup-plan2
```

- [ ] **Step 5: Open the PR**

```bash
gh pr create --title "Spec C Plan 2 — Per-rival surfaces (player_detail reskin + team_detail route)" --body "$(cat <<'EOF'
## Summary

Lands Plan 2 of Spec C (CCC World Cup reskin):

- **`player_detail.html` reskin**: hero rebuilt with eyebrow ("Rank N" or gold "Current Leader"), 2-3 stat grid (Total · Lead · Tiebreak). Mobile pick cards now deep-link team name to `team_detail`. Inherits Plan 1's reskinned `_pick_row.html` for the desktop table.
- **NEW public route `/worldcup/team/<int:team_id>`** + `team_detail.html`: hero (flag · name · 4-stat grid), ownership ribbon (privacy-gated per spec D11), tournament fixtures match log, Path to the Crown (6 stage segments + projected ceiling), Who Picked This (post-deadline only, alphabetized links to `player_detail`).
- **NEW shared helper `compute_rank_neighbors()`** in `games/worldcup/services/ranking.py` — Plan 3 will reuse for the leaderboard "Your Standing" block.
- **NEW helpers `compute_team_ownership` / `current_user_owns_team` / `compute_path_to_crown`** in `games/worldcup/services/team_detail.py`.
- **`_pick_row.html` deep-link**: desktop pick row team name now links to `team_detail` (mobile equivalent shipped in player_detail mobile cards).

Sub-nav `Board` pill auto-activates on `/worldcup/team/<id>` (Plan 1's forward-reference resolves with this PR). No CSS scoping issues — utilities used here (`.wc-eyebrow`, `.wc-numeral`, `.wc-tier-dot`, `.wc-multiplier-chip`, `.page-hero.wc-hero-grad`, `.card.wc-card`) all live foundation utilities from Plan 1; new Plan 2 utilities (`.player-hero-stats`, `.team-hero-stats`, `.ownership-ribbon`, `.fixture-list`, `.path-segments`, `.picker-list`) are scoped multi-class selectors with no overlap with later base rules.

Spec: `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md`
Plan: `docs/superpowers/plans/2026-05-02-ccc-worldcup-plan-2-per-rival-surfaces.md`

## Test plan

- [x] All 173 tests pass (150 baseline + 23 new across ranking/team_detail_service/team_detail)
- [x] `pyright` clean on `games/worldcup/`
- [x] Manual visual checklist passed for every touched surface at 375px and 1280px
- [x] Pre-deadline ownership privacy verified — count, percent, and picker names all hidden for non-owners (test + manual)
- [x] Post-deadline ownership visible with picker links to `/worldcup/player/<id>`
- [x] Owner-of-team sees red 'You Own This Nation' ribbon even pre-deadline (own data, no privacy concern)
- [x] Path-to-Crown segments render with correct status across alive/eliminated/group-stage cases
- [x] Score-event parity test confirms `team_detail` displays match the `compute_team_score_events` SSoT
- [x] Sub-nav `Board` pill auto-activates on `/worldcup/team/<id>`
- [x] `_pick_row.html` chevron accordion still expands/collapses (DOM hooks preserved; team-name link uses event.stopPropagation)

@coderabbitai please review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. CodeRabbit will review automatically per the `@coderabbitai` mention.

- [ ] **Step 6: Wait for CodeRabbit's review and address any findings**

Wait until CodeRabbit's actual review comment lands (not the "processing" stub). Address any findings via additional commits on the same branch. Re-push.

- [ ] **Step 7: Once approved, merge**

After CodeRabbit's review is addressed and the PR is approved, merge via the GitHub UI (squash recommended — matches Spec B + Plan 1's pattern). After merge, Plans 3 and 4 can branch from the freshly-merged main; both plans' helpers (Plan 3 reuses `compute_rank_neighbors`; Plan 4 may lift `_stage_label` into `games/worldcup/services/stage.py` and update Plan 2's inline import to point at the new location) build on top of Plan 2's foundation.

---

## Notes for the executing agent

- **Use `frontend-design` for Tasks 5 and 6**: those tasks build the brand-new `team_detail.html` template, where the design bundle is mobile-only and you have real latitude on desktop, segment treatments, and component polish. Tasks 0–4 and 7–8 do NOT need `frontend-design` (they're either non-UI, paint-by-numbers reskin against an already-prescribed design, or trivial wiring). See the in-task notes at the top of Task 5 + Task 6 for scope.
- **Class-naming caution (lesson from Task 2)**: when adding component classes inside the dark WC hero or other surfaces with their own background, do NOT reuse generic platform-component class names like `.stat-block`, `.card`, etc. — they carry pre-existing chrome (white card backgrounds, padding, shadows) that will collide. Use unique names (e.g., `.hero-stat`, `.fixture-row`, `.path-segment`). Plan 2 Task 2's `.hero-stat` was renamed mid-execution after `.stat-block` rendered as invisible white-on-white.
- **`url_for` vs Jinja `in [...]` for forward-references**: Plan 1 forward-referenced `worldcup.team_detail` in the sub-nav via `request.endpoint in ['worldcup.leaderboard', ..., 'worldcup.team_detail']` — that's silent for missing endpoints. But `url_for('worldcup.team_detail', ...)` raises `BuildError` at template-render time if the endpoint doesn't exist. Don't add `url_for` calls to the team_detail endpoint until Task 4 lands the route. Plan 2 Task 2 originally tried this and 500'd the post-deadline player_detail page; the link was deferred to Task 4 (Step 5).
- **Privacy invariant is a hard constraint**: `compute_team_ownership(team_id, deadline_passed=False)` MUST return `count=0, percent=0.0, picker_names=None`. The test `test_team_detail_ownership_hidden_pre_deadline` is non-negotiable. Per spec D11, even a count leaks information about which teams gained traction.
- **Score-event SSoT**: `team_detail` derives all per-match points from `compute_team_score_events()` via the `points_by_match` map. Never recompute scoring math in the route or template; the parity test (`test_team_detail_score_events_match_canonical_helper`) guards against drift.
- **Inline `_stage_label` import**: Plan 2 imports `_stage_label` from `core/main/home_context` per CLAUDE.md (cross-game module currently). When Plan 4 lifts it to `games/worldcup/services/stage.py`, that PR updates Plan 2's import line to point at the new location. Pyright will catch the missing import if Plan 4 deletes the function from `core/main/home_context` without updating callers.
- **Forward references**: Plan 1 already wired `worldcup.team_detail` into the sub-nav active-state list and added `.team-link` styling expectations are now met by Plan 2 Task 2's CSS additions. Plan 1's wiring required NO change to the sub-nav for this PR — it just *resolves* once the route exists.
- **`compute_rank_neighbors` is shared with Plan 3**: design choices (dense rank, sort matches public leaderboard, rounded to 2 decimals) are deliberate so Plan 3's leaderboard "Your Standing" block can consume it unchanged. Don't change the signature without coordinating with Plan 3.
- **Worktree scoping for new `.wc-*` utilities**: Plan 2 introduces no new utility classes that overlap with later base rules. The new selectors (`.player-hero-stats`, `.team-hero-stats`, `.ownership-ribbon`, `.fixture-list`, `.path-segments`, `.picker-list`, `.team-link`, `.back-link`) are all multi-token (or unique enough) that they win cascade naturally. If you find yourself adding another single-class `.wc-*` utility, re-read `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_wc_reskin_gotchas.md` §2 and scope it as `.base.wc-x` if it overlaps with a later platform rule.
- **Visual fidelity** per spec D8 (B): strict-where-clear, interpretive-where-ambiguous. The bundle is mobile-only; desktop interpretations on `team_detail.html` are your call as long as mobile-first reading order is preserved. Default to single-column up through `lg`; the existing `col-lg-8 / col-lg-4` split on `player_detail.html` is *not* introduced here (the page stays centered single-column on all viewports per spec §5).
