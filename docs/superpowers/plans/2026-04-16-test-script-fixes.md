# Test Script Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six issues surfaced in the April 2026 World Cup human test pass (sections 5A, 6, 7B, 7C, 7D) — pre-deadline tiebreaker leak, missing Central Time indicator, admin winner-entry friction, absent scoring attribution, inaccessible edit path for completed matches, and no way to clear a knockout team assignment.

**Architecture:** Grounded in ADR-024 (denormalized scoring, "every number rebuildable"): scoring attribution is **derived on display** via two new pure helpers in `services/scoring.py`, not persisted in a new table. No migrations. No new routes — only new POST `action=` branches on existing admin endpoints. All new UI reuses the existing "Commissioner's Club" World Cup palette (Old Glory blue / red / Teko font).

**Tech Stack:** Flask, Jinja2, SQLAlchemy 2.0, Bootstrap 5.3, vanilla JS, CSS custom properties, pytest.

**Related spec:** `docs/superpowers/specs/2026-04-16-test-script-fixes-design.md`

---

## File Map

| File | Change |
|------|--------|
| `games/worldcup/services/scoring.py` | Add `ScoreEvent` dataclass + `compute_team_score_events()` + `compute_match_attribution()` |
| `games/worldcup/routes.py` | Modify `leaderboard()`, `schedule()`, `player_detail()`, `admin_dashboard()`, `admin_set_knockout()` |
| `games/worldcup/templates/worldcup/leaderboard.html` | Conditional tiebreaker column/line |
| `games/worldcup/templates/worldcup/schedule.html` | CT caption in hero + per-match attribution chip |
| `games/worldcup/templates/worldcup/_pick_row.html` | **New** — shared partial for pick rows with drill-down |
| `games/worldcup/templates/worldcup/player_detail.html` | Use partial; accordion drill-down |
| `games/worldcup/templates/worldcup/picks.html` | Use partial; accordion drill-down for read-only view |
| `games/worldcup/templates/worldcup/admin/dashboard.html` | "Completed Matches" collapsible card |
| `games/worldcup/templates/worldcup/admin/match_result.html` | Inline JS: auto-winner from score inputs |
| `games/worldcup/templates/worldcup/admin/set_knockout.html` | "Clear Team Assignment" button + lock hint |
| `static/css/style.css` | `.match-points-chip`, `.pick-accordion`, `.score-events-list`, `@keyframes wc-auto-pulse` |
| `tests/test_worldcup_scoring.py` | Extend — 7 new tests around derive helpers |
| `tests/test_worldcup_admin.py` | **New** — 5 admin-route tests |
| `games/worldcup/constants.py` | **Final step:** revert `TOURNAMENT_DEADLINE_UTC` to production value |

---

## Task 1: `ScoreEvent` dataclass + `compute_team_score_events()` — group-stage events

Follow TDD. Write tests first using the existing helper functions in `tests/test_worldcup_scoring.py`.

**Files:**
- Modify: `games/worldcup/services/scoring.py`
- Test: `tests/test_worldcup_scoring.py`

- [ ] **Step 1: Write the failing tests for group-stage events**

Append to `tests/test_worldcup_scoring.py`:

```python
# ============================================================
# Score Event Attribution (display-time derivation, ADR-024)
# ============================================================

class TestComputeTeamScoreEventsGroup:
    """compute_team_score_events derives per-team scoring sources from match state."""

    def test_group_win_emits_single_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_team_score_events,
            )
            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='MEX',
            )
            db.session.refresh(mex)

            events = compute_team_score_events(mex)
            assert len(events) == 1
            assert events[0].source == 'group_win'
            assert events[0].base_points == 3.0
            assert events[0].match_id == match.id
            assert 'RSA' in events[0].label or 'South Africa' in events[0].label

    def test_group_draw_emits_event_for_both_teams(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_team_score_events,
            )
            bra = _make_team(db.session, 'BRA', 'Brazil', 1, 1.0, 'B')
            mar = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5, 'B')
            match = _make_match(db.session, 6, 'group', bra, mar, 'B')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=0, away_score=0,
                winner_fifa_code=None, is_draw=True,
            )
            db.session.refresh(bra)
            db.session.refresh(mar)

            bra_events = compute_team_score_events(bra)
            mar_events = compute_team_score_events(mar)
            assert len(bra_events) == 1
            assert bra_events[0].source == 'group_draw'
            assert bra_events[0].base_points == 1.0
            assert len(mar_events) == 1
            assert mar_events[0].source == 'group_draw'

    def test_group_loss_emits_no_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_team_score_events,
            )
            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'C')
            ksa = _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'C')
            match = _make_match(db.session, 10, 'group', arg, ksa, 'C')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=1, away_score=2,
                winner_fifa_code='KSA',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            assert events == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestComputeTeamScoreEventsGroup -v
```

Expected: `ImportError: cannot import name 'compute_team_score_events' from 'games.worldcup.services.scoring'`

- [ ] **Step 3: Implement `ScoreEvent` + `compute_team_score_events()` for group stage**

At the top of `games/worldcup/services/scoring.py`, update imports:

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal
```

Add near the top of the file (after `STAGE_ORDER`):

```python
ScoreSource = Literal['group_win', 'group_draw', 'advancement', 'knockout', 'podium']


@dataclass(frozen=True)
class ScoreEvent:
    """A single scoring event contributing to a team's base_points total.

    Returned by compute_team_score_events() for UI drill-down. Not persisted —
    derived fresh each render from current match/team state (ADR-024).
    """
    source: ScoreSource
    label: str
    base_points: float
    match_id: int | None
    occurred_on: date | None
```

At the end of the file, add:

```python
def compute_team_score_events(team: WorldCupTeam) -> list[ScoreEvent]:
    """Replay this team's scoring sources against current match/team state.

    Returns a chronologically-ordered list of ScoreEvents. The sum of
    `base_points` across events equals `team.base_points` (enforced via
    unit test). Pure function — performs no DB writes.
    """
    events: list[ScoreEvent] = []

    # Group-stage match events
    group_matches = (
        WorldCupMatch.query
        .filter_by(stage='group', is_completed=True)
        .filter(
            (WorldCupMatch.home_team_id == team.id)
            | (WorldCupMatch.away_team_id == team.id)
        )
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )
    for match in group_matches:
        opponent = (
            match.away_team if match.home_team_id == team.id else match.home_team
        )
        opp_code = opponent.fifa_code if opponent else '???'
        kickoff_date = match.kickoff_utc.date() if match.kickoff_utc else None
        if match.is_draw:
            events.append(ScoreEvent(
                source='group_draw',
                label=f'Draw vs {opp_code}',
                base_points=float(GROUP_DRAW),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))
        elif match.winner_team_id == team.id:
            events.append(ScoreEvent(
                source='group_win',
                label=f'Win vs {opp_code}',
                base_points=float(GROUP_WIN),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestComputeTeamScoreEventsGroup -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/scoring.py tests/test_worldcup_scoring.py
git commit -m "feat(worldcup): add ScoreEvent + compute_team_score_events group stage"
```

---

## Task 2: Extend `compute_team_score_events()` — advancement + knockout + podium

**Files:**
- Modify: `games/worldcup/services/scoring.py`
- Test: `tests/test_worldcup_scoring.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_worldcup_scoring.py`:

```python
class TestComputeTeamScoreEventsAdvancement:
    """Advancement methods emit events worth the matching constant."""

    def test_group_winner_advancement_emits_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                apply_group_advancement, compute_team_score_events,
            )
            from games.worldcup.constants import ADVANCE_GROUP_WINNER

            esp = _make_team(db.session, 'ESP', 'Spain', 1, 1.0, 'A')
            uru = _make_team(db.session, 'URU', 'Uruguay', 2, 1.5, 'A')
            ksa = _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'A')
            jpn = _make_team(db.session, 'JPN', 'Japan', 4, 4.0, 'A')
            db.session.commit()

            apply_group_advancement('A', {
                'ESP': 'group_winner',
                'URU': 'runner_up',
                'KSA': 'best_third',
            })
            db.session.refresh(esp)

            events = compute_team_score_events(esp)
            adv_events = [e for e in events if e.source == 'advancement']
            assert len(adv_events) == 1
            assert adv_events[0].base_points == float(ADVANCE_GROUP_WINNER)
            assert 'winner' in adv_events[0].label.lower()


class TestComputeTeamScoreEventsKnockout:
    """Knockout wins emit events worth KNOCKOUT_POINTS[stage]."""

    def test_r16_win_emits_knockout_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_team_score_events,
            )
            from games.worldcup.constants import KNOCKOUT_POINTS

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            cro = _make_team(db.session, 'CRO', 'Croatia', 3, 2.5, 'B')
            match = _make_match(db.session, 105, 'R16', arg, cro)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='ARG',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            ko_events = [e for e in events if e.source == 'knockout']
            assert len(ko_events) == 1
            assert ko_events[0].base_points == float(KNOCKOUT_POINTS['R16'])
            assert ko_events[0].match_id == match.id


class TestComputeTeamScoreEventsPodium:
    """Champion / runner_up / third_place each add a podium event."""

    def test_champion_emits_podium_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_team_score_events,
            )
            from games.worldcup.constants import KNOCKOUT_POINTS

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            fra = _make_team(db.session, 'FRA', 'France', 1, 1.0, 'B')
            match = _make_match(db.session, 104, 'final', arg, fra)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=3, away_score=2,
                winner_fifa_code='ARG',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            podium = [e for e in events if e.source == 'podium']
            assert len(podium) == 1
            assert podium[0].base_points == float(KNOCKOUT_POINTS['champion'])


class TestComputeTeamScoreEventsInvariant:
    """Invariant: sum of event base_points == team.base_points."""

    def test_sum_matches_base_points_after_full_recalc(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, apply_group_advancement,
                compute_team_score_events,
            )

            # Build a tiny simulated tournament: one group + one R32
            esp = _make_team(db.session, 'ESP', 'Spain', 1, 1.0, 'A')
            uru = _make_team(db.session, 'URU', 'Uruguay', 2, 1.5, 'A')
            ksa = _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'A')
            jpn = _make_team(db.session, 'JPN', 'Japan', 4, 4.0, 'A')
            m1 = _make_match(db.session, 1, 'group', esp, uru, 'A')
            m2 = _make_match(db.session, 2, 'group', ksa, jpn, 'A')
            m3 = _make_match(db.session, 3, 'group', esp, ksa, 'A')
            db.session.commit()

            process_match_result(
                match_id=m1.id, home_score=2, away_score=1,
                winner_fifa_code='ESP',
            )
            process_match_result(
                match_id=m2.id, home_score=0, away_score=0,
                winner_fifa_code=None, is_draw=True,
            )
            process_match_result(
                match_id=m3.id, home_score=3, away_score=0,
                winner_fifa_code='ESP',
            )
            apply_group_advancement('A', {
                'ESP': 'group_winner',
                'URU': 'runner_up',
            })

            for team in WorldCupTeam.query.all():
                db.session.refresh(team)
                events = compute_team_score_events(team)
                derived = sum(e.base_points for e in events)
                assert derived == team.base_points, (
                    f'{team.fifa_code}: derived {derived} != stored {team.base_points}'
                )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py -k "TestComputeTeamScoreEvents" -v
```

Expected: group-stage tests PASS (from Task 1); the 4 new test classes FAIL with assertion errors.

- [ ] **Step 3: Extend `compute_team_score_events()` to cover advancement, knockout, podium**

Replace the `compute_team_score_events()` function in `games/worldcup/services/scoring.py` with:

```python
def compute_team_score_events(team: WorldCupTeam) -> list[ScoreEvent]:
    """Replay this team's scoring sources against current match/team state.

    Returns a chronologically-ordered list of ScoreEvents. The sum of
    `base_points` across events equals `team.base_points` (enforced via
    unit test). Pure function — performs no DB writes.
    """
    events: list[ScoreEvent] = []

    # Group-stage match events
    group_matches = (
        WorldCupMatch.query
        .filter_by(stage='group', is_completed=True)
        .filter(
            (WorldCupMatch.home_team_id == team.id)
            | (WorldCupMatch.away_team_id == team.id)
        )
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )
    for match in group_matches:
        opponent = (
            match.away_team if match.home_team_id == team.id else match.home_team
        )
        opp_code = opponent.fifa_code if opponent else '???'
        kickoff_date = match.kickoff_utc.date() if match.kickoff_utc else None
        if match.is_draw:
            events.append(ScoreEvent(
                source='group_draw',
                label=f'Draw vs {opp_code}',
                base_points=float(GROUP_DRAW),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))
        elif match.winner_team_id == team.id:
            events.append(ScoreEvent(
                source='group_win',
                label=f'Win vs {opp_code}',
                base_points=float(GROUP_WIN),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))

    # Advancement milestone
    if team.advancement_method:
        adv_points = _apply_advancement_points(team)
        if adv_points > 0:
            adv_labels = {
                'group_winner': 'Group winner',
                'runner_up': 'Group runner-up',
                'best_third': 'Best 3rd place',
            }
            events.append(ScoreEvent(
                source='advancement',
                label=adv_labels.get(team.advancement_method, team.advancement_method),
                base_points=float(adv_points),
                match_id=None,
                occurred_on=None,
            ))

    # Knockout-match wins (R32, R16, QF, SF)
    knockout_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.stage != 'group')
        .filter(WorldCupMatch.is_completed == True)  # noqa: E712
        .filter(WorldCupMatch.winner_team_id == team.id)
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )
    for match in knockout_matches:
        stage_points = _apply_knockout_points(match)
        if stage_points <= 0:
            continue
        opponent = (
            match.away_team if match.home_team_id == team.id else match.home_team
        )
        opp_code = opponent.fifa_code if opponent else '???'
        kickoff_date = match.kickoff_utc.date() if match.kickoff_utc else None
        events.append(ScoreEvent(
            source='knockout',
            label=f'{match.stage}: beat {opp_code}',
            base_points=float(stage_points),
            match_id=match.id,
            occurred_on=kickoff_date,
        ))

    # Podium bonus
    podium_points = _apply_podium_bonus(team)
    if podium_points > 0:
        podium_labels = {
            'champion': 'Champion',
            'runner_up': 'Runner-up (final)',
            '3rd': 'Third place',
        }
        events.append(ScoreEvent(
            source='podium',
            label=podium_labels.get(team.best_finish or '', team.best_finish or ''),
            base_points=float(podium_points),
            match_id=None,
            occurred_on=None,
        ))

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py -k "TestComputeTeamScoreEvents" -v
```

Expected: all tests in the 4 `TestComputeTeamScoreEvents*` classes PASS.

- [ ] **Step 5: Run the full scoring test suite to confirm no regressions**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py -v
```

Expected: 100% pass.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/scoring.py tests/test_worldcup_scoring.py
git commit -m "feat(worldcup): extend score events — advancement, knockout, podium"
```

---

## Task 3: `compute_match_attribution()` — schedule chip data

**Files:**
- Modify: `games/worldcup/services/scoring.py`
- Test: `tests/test_worldcup_scoring.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_worldcup_scoring.py`:

```python
class TestComputeMatchAttribution:
    """compute_match_attribution emits chip data for completed matches."""

    def test_incomplete_match_returns_none(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import compute_match_attribution

            a = _make_team(db.session, 'AAA', 'Team A', 3, 2.5, 'A')
            b = _make_team(db.session, 'BBB', 'Team B', 3, 2.5, 'A')
            match = _make_match(db.session, 1, 'group', a, b, 'A')
            db.session.commit()

            assert compute_match_attribution(match) is None

    def test_group_win_returns_winner_plus_three(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_match_attribution,
            )
            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='MEX',
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'group_win'
            assert attr['events'] == [('Mexico', 'MEX', 3.0)]

    def test_group_draw_returns_both_teams_plus_one(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_match_attribution,
            )
            bra = _make_team(db.session, 'BRA', 'Brazil', 1, 1.0, 'B')
            mar = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5, 'B')
            match = _make_match(db.session, 6, 'group', bra, mar, 'B')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=1, away_score=1,
                winner_fifa_code=None, is_draw=True,
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'group_draw'
            assert ('Brazil', 'BRA', 1.0) in attr['events']
            assert ('Morocco', 'MAR', 1.0) in attr['events']
            assert len(attr['events']) == 2

    def test_knockout_win_includes_stage_points(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, compute_match_attribution,
            )
            from games.worldcup.constants import KNOCKOUT_POINTS

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            cro = _make_team(db.session, 'CRO', 'Croatia', 3, 2.5, 'B')
            match = _make_match(db.session, 105, 'R16', arg, cro)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='ARG',
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'knockout'
            assert attr['stage'] == 'R16'
            assert attr['events'] == [('Argentina', 'ARG', float(KNOCKOUT_POINTS['R16']))]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestComputeMatchAttribution -v
```

Expected: `ImportError: cannot import name 'compute_match_attribution'`

- [ ] **Step 3: Implement `compute_match_attribution()`**

Append to `games/worldcup/services/scoring.py`:

```python
def compute_match_attribution(match: WorldCupMatch) -> dict | None:
    """Return scoring-chip data for a completed match. None for incomplete.

    Shape:
        group_win:   {'type': 'group_win',   'events': [(name, code, +base)]}
        group_draw:  {'type': 'group_draw',  'events': [(name, code, +1), (name, code, +1)]}
        knockout:    {'type': 'knockout', 'stage': 'R16', 'events': [(name, code, +stage_pts)]}

    Podium bonuses are NOT included here — they attach to the final/3rd-place
    match's winner but are owned by `best_finish`, and are surfaced in the
    per-pick drill-down instead. Schedule chips show match-contribution only.
    """
    if not match.is_completed:
        return None

    if match.stage == 'group':
        if match.is_draw:
            if not match.home_team or not match.away_team:
                return None
            return {
                'type': 'group_draw',
                'events': [
                    (match.home_team.display_name, match.home_team.fifa_code, float(GROUP_DRAW)),
                    (match.away_team.display_name, match.away_team.fifa_code, float(GROUP_DRAW)),
                ],
            }
        winner = match.winner_team
        if not winner:
            return None
        return {
            'type': 'group_win',
            'events': [(winner.display_name, winner.fifa_code, float(GROUP_WIN))],
        }

    # Knockout (R32 / R16 / QF / SF / third_place / final)
    winner = match.winner_team
    if not winner:
        return None
    stage_points = _apply_knockout_points(match)
    if stage_points <= 0:
        return None
    return {
        'type': 'knockout',
        'stage': match.stage,
        'events': [(winner.display_name, winner.fifa_code, float(stage_points))],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestComputeMatchAttribution -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Run pyright on scoring.py**

```bash
venv/bin/pyright games/worldcup/services/scoring.py
```

Expected: 0 errors, 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/scoring.py tests/test_worldcup_scoring.py
git commit -m "feat(worldcup): add compute_match_attribution for schedule chips"
```

---

## Task 4: Schedule CT caption + attribution chip — route + template + CSS

**Files:**
- Modify: `games/worldcup/routes.py` (`schedule()`)
- Modify: `games/worldcup/templates/worldcup/schedule.html`
- Modify: `static/css/style.css`

- [ ] **Step 1: Update `schedule()` to pass attribution data**

In `games/worldcup/routes.py`, find the `schedule()` function (currently around lines 394-419) and update the imports block at the top to include `compute_match_attribution`:

```python
from games.worldcup.services.scoring import (
    process_match_result,
    apply_group_advancement,
    set_knockout_teams,
    recalculate_all_scores,
    compute_match_attribution,
)
```

Replace the body of `schedule()`:

```python
@worldcup_bp.route('/schedule')
def schedule():
    """Match schedule with results."""
    matches = (
        WorldCupMatch.query
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    attribution_by_match = {
        m.id: compute_match_attribution(m) for m in matches if m.is_completed
    }

    group_matches = [m for m in matches if m.stage == 'group']
    r32_matches = [m for m in matches if m.stage == 'R32']
    r16_matches = [m for m in matches if m.stage == 'R16']
    qf_matches = [m for m in matches if m.stage == 'QF']
    sf_matches = [m for m in matches if m.stage == 'SF']
    third_place = [m for m in matches if m.stage == 'third_place']
    final = [m for m in matches if m.stage == 'final']

    return render_template('worldcup/schedule.html',
        group_matches=group_matches,
        r32_matches=r32_matches,
        r16_matches=r16_matches,
        qf_matches=qf_matches,
        sf_matches=sf_matches,
        third_place=third_place,
        final=final,
        attribution_by_match=attribution_by_match,
    )
```

- [ ] **Step 2: Add CSS for the chip**

In `static/css/style.css`, inside the `/* === WORLD CUP FANTASY POOL === */` section (after the `.match-result-card` block around line 628), add:

```css
/* Match attribution chip — "ARG +3 base" etc. */
.match-points-chip {
  display: inline-flex;
  align-items: center;
  gap: .35em;
  padding: .15rem .55rem;
  background: rgba(0, 40, 104, .08);
  border-left: 2px solid var(--game-accent, #BF0A30);
  color: var(--game-primary, #002868);
  font-family: 'Teko', sans-serif;
  font-size: .85rem;
  font-weight: 500;
  letter-spacing: .04em;
  text-transform: uppercase;
  border-radius: 2px;
  margin-top: .4rem;
  white-space: nowrap;
}
.match-points-chip .chip-pts {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.match-points-chip .chip-sep {
  opacity: .5;
  margin: 0 .2em;
}
```

- [ ] **Step 3: Add the CT caption + render the chip in schedule.html**

In `games/worldcup/templates/worldcup/schedule.html`, replace the hero block (lines 5-11) with:

```html
<div class="page-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <h1>Match Schedule</h1>
    <p class="lead mb-0">All 104 matches &mdash; 2026 FIFA World Cup</p>
    <small class="d-block mt-1 opacity-75"
           style="letter-spacing:.08em; text-transform:uppercase; font-size:.72rem;">
      All kickoff times shown in Central Time
    </small>
  </div>
</div>
```

Next, define a macro for the attribution chip and use it in both the group-stage loop and the `render_stage` macro. Replace the entire template body (`{% block content %}` through `{% endblock %}`) with:

```html
{% block content %}
<div class="page-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <h1>Match Schedule</h1>
    <p class="lead mb-0">All 104 matches &mdash; 2026 FIFA World Cup</p>
    <small class="d-block mt-1 opacity-75"
           style="letter-spacing:.08em; text-transform:uppercase; font-size:.72rem;">
      All kickoff times shown in Central Time
    </small>
  </div>
</div>

<div class="container pb-5">

  {% macro render_chip(match) %}
    {% set attr = attribution_by_match.get(match.id) %}
    {% if attr %}
      <div class="match-points-chip">
        {% if attr.type == 'group_draw' %}
          <span>{{ attr.events[0][1] }} <span class="chip-pts">+{{ "%g"|format(attr.events[0][2]) }}</span></span>
          <span class="chip-sep">·</span>
          <span>{{ attr.events[1][1] }} <span class="chip-pts">+{{ "%g"|format(attr.events[1][2]) }}</span> base</span>
        {% elif attr.type == 'knockout' %}
          <span>{{ attr.events[0][1] }} <span class="chip-pts">+{{ "%g"|format(attr.events[0][2]) }}</span> base ({{ attr.stage }})</span>
        {% else %}
          <span>{{ attr.events[0][1] }} <span class="chip-pts">+{{ "%g"|format(attr.events[0][2]) }}</span> base</span>
        {% endif %}
      </div>
    {% endif %}
  {% endmacro %}

  {# ── Group Stage ── #}
  {% if group_matches %}
  <h2 class="section-heading mb-3 animate-in">
    <i class="bi bi-grid-3x3 me-2"></i>Group Stage
    <small class="text-muted ms-2" style="font-size:.6em; font-weight:400;">{{ group_matches|length }} matches</small>
  </h2>

  {% set ns = namespace(current_group='') %}
  {% for m in group_matches %}
    {% if m.group_letter != ns.current_group %}
      {% if ns.current_group != '' %}</div>{% endif %}
      {% set ns.current_group = m.group_letter %}
      <h4 class="mt-4 mb-2" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.06em; font-size:1.1rem; color:var(--text-muted);">
        Group {{ m.group_letter }}
      </h4>
      <div class="d-flex flex-column gap-2 mb-3">
    {% endif %}

    <div>
      <div class="match-result-card">
        <span class="match-team home">{% if m.home_team %}{{ m.home_team.flag_emoji }} {{ m.home_team.display_name }}{% else %}TBD{% endif %}</span>
        {% if m.is_completed %}
          <span class="match-score">{{ m.home_score }}&ndash;{{ m.away_score }}</span>
        {% elif m.kickoff_utc %}
          <span class="match-score pending">{{ format_ct(m.kickoff_utc).strftime('%-m/%-d %-I:%M%p') }}</span>
        {% else %}
          <span class="match-score pending">TBD</span>
        {% endif %}
        <span class="match-team away">{% if m.away_team %}{{ m.away_team.flag_emoji }} {{ m.away_team.display_name }}{% else %}TBD{% endif %}</span>
      </div>
      {{ render_chip(m) }}
    </div>
  {% endfor %}
  {% if group_matches %}</div>{% endif %}
  {% endif %}

  {# ── Knockout Rounds ── #}
  {% macro render_stage(matches, title, icon) %}
  {% if matches %}
  <h2 class="section-heading mt-5 mb-3 animate-in">
    <i class="bi bi-{{ icon }} me-2"></i>{{ title }}
    <small class="text-muted ms-2" style="font-size:.6em; font-weight:400;">{{ matches|length }} match{{ 'es' if matches|length != 1 }}</small>
  </h2>
  <div class="d-flex flex-column gap-2">
    {% for m in matches %}
    <div>
      <div class="match-result-card">
        <span class="match-team home">{% if m.home_team %}{{ m.home_team.flag_emoji }} {{ m.home_team.display_name }}{% else %}TBD{% endif %}</span>
        {% if m.is_completed %}
          <span class="match-score">{{ m.home_score }}&ndash;{{ m.away_score }}</span>
        {% elif m.kickoff_utc %}
          <span class="match-score pending">{{ format_ct(m.kickoff_utc).strftime('%-m/%-d %-I:%M%p') }}</span>
        {% else %}
          <span class="match-score pending">TBD</span>
        {% endif %}
        <span class="match-team away">{% if m.away_team %}{{ m.away_team.flag_emoji }} {{ m.away_team.display_name }}{% else %}TBD{% endif %}</span>
      </div>
      {{ render_chip(m) }}
    </div>
    {% endfor %}
  </div>
  {% endif %}
  {% endmacro %}

  {{ render_stage(r32_matches, 'Round of 32', 'trophy') }}
  {{ render_stage(r16_matches, 'Round of 16', 'trophy') }}
  {{ render_stage(qf_matches, 'Quarterfinals', 'trophy-fill') }}
  {{ render_stage(sf_matches, 'Semifinals', 'trophy-fill') }}
  {{ render_stage(third_place, 'Third Place Match', 'award') }}
  {{ render_stage(final, 'Final', 'star-fill') }}

</div>
{% endblock %}
```

- [ ] **Step 4: Manual verification**

```bash
FLASK_APP=app.py venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Then start the dev server and visit `/worldcup/schedule`:

```bash
FLASK_APP=app.py venv/bin/flask run
```

Expected: page renders; CT caption visible under the lead; no chips yet (no matches completed in dev DB). Stop the server (Ctrl-C).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/schedule.html static/css/style.css
git commit -m "feat(worldcup): schedule CT caption + match attribution chips"
```

---

## Task 5: Leaderboard — hide tiebreaker pre-deadline

**Files:**
- Modify: `games/worldcup/routes.py` (`leaderboard()`)
- Modify: `games/worldcup/templates/worldcup/leaderboard.html`
- Test: `tests/test_worldcup_admin.py` (new file — shared location for admin + public deadline-sensitive tests)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_admin.py`:

```python
"""
Tests for World Cup public + admin routes that depend on deadline or
state guards. Complements tests/test_worldcup_scoring.py (engine tests).
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
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


def _make_enrolled_user_with_tiebreaker(app, guess=7):
    """Create an enrollment with a known USA goals tiebreaker."""
    with app.app_context():
        user = User(username='tbplayer', email='tbplayer@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.flush()

        enrollment = WorldCupEnrollment(
            user_id=user.id,
            season_year=2026,
            picks_submitted=True,
            usa_goals_guess=guess,
            total_score=5.0,
        )
        db.session.add(enrollment)
        db.session.commit()
        return user.id, enrollment.id


# ── Leaderboard tiebreaker visibility ────────────────────────────────────

def test_leaderboard_hides_tiebreaker_pre_deadline(client, app):
    _make_enrolled_user_with_tiebreaker(app, guess=7)
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # The tiebreaker column header should not be in the desktop table
    assert b'Tiebreaker' not in resp.data
    # The mobile "TB: N" label should not be in the response
    assert b'TB:' not in resp.data
    # And the actual value should not leak
    assert b'>7<' not in resp.data


def test_leaderboard_shows_tiebreaker_post_deadline(client, app):
    _make_enrolled_user_with_tiebreaker(app, guess=7)
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Tiebreaker' in resp.data
    assert b'7' in resp.data
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py::test_leaderboard_hides_tiebreaker_pre_deadline tests/test_worldcup_admin.py::test_leaderboard_shows_tiebreaker_post_deadline -v
```

Expected: `test_leaderboard_hides_tiebreaker_pre_deadline` FAILS (Tiebreaker header still present).

- [ ] **Step 3: Update `leaderboard()` route to pass `deadline_passed`**

In `games/worldcup/routes.py`, replace the `leaderboard()` function body:

```python
@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Public leaderboard — no login required."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    ranked = []
    current_rank = 0
    prev_score = None
    for i, e in enumerate(enrollments):
        if e.total_score != prev_score:
            current_rank = i + 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
        deadline_passed=deadline_passed,
    )
```

- [ ] **Step 4: Update `leaderboard.html` to conditionally render tiebreaker**

In `games/worldcup/templates/worldcup/leaderboard.html`:

Wrap the desktop `<th class="text-end">Tiebreaker</th>` and matching `<td class="text-end text-muted">...</td>` in `{% if deadline_passed %}`.

Specifically, replace lines 22-27 with:

```html
<tr>
  <th style="width:60px">#</th>
  <th>Player</th>
  <th class="text-end">Points</th>
  {% if deadline_passed %}
  <th class="text-end">Tiebreaker</th>
  {% endif %}
</tr>
```

And replace the tiebreaker `<td>` (currently line 47) to be conditional. Replace lines 45-48 with:

```html
<td class="text-end fw-bold">{{ "%.1f"|format(e.total_score) }}</td>
{% if deadline_passed %}
<td class="text-end text-muted">{{ e.usa_goals_guess if e.usa_goals_guess is not none else '—' }}</td>
{% endif %}
```

Then in the mobile card, wrap the `{% if e.usa_goals_guess is not none %}...{% endif %}` block (currently lines 76-78) in an outer `{% if deadline_passed %}`:

```html
{% if deadline_passed and e.usa_goals_guess is not none %}
<small class="text-muted">TB: {{ e.usa_goals_guess }}</small>
{% endif %}
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py -v
```

Expected: both tiebreaker tests PASS.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/leaderboard.html tests/test_worldcup_admin.py
git commit -m "fix(worldcup): hide tiebreaker on leaderboard pre-deadline"
```

---

## Task 6: Player detail accordion — shared partial + drill-down

**Files:**
- Create: `games/worldcup/templates/worldcup/_pick_row.html`
- Modify: `games/worldcup/routes.py` (`player_detail()`)
- Modify: `games/worldcup/templates/worldcup/player_detail.html`
- Modify: `static/css/style.css`

- [ ] **Step 1: Add CSS for the accordion**

In `static/css/style.css`, inside the `/* === WORLD CUP FANTASY POOL === */` section (after `.match-points-chip`), add:

```css
/* Pick drill-down accordion */
.pick-accordion {
  border-top: 1px dashed var(--border, #dee2e6);
  background: rgba(0, 40, 104, .03);
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 140ms ease-out, opacity 140ms ease-out;
}
.pick-accordion.open {
  max-height: 600px; /* generous upper bound */
  opacity: 1;
}
.pick-accordion-toggle {
  background: transparent;
  border: 0;
  color: var(--text-muted, #6c757d);
  cursor: pointer;
  padding: 0 .35rem;
  font-size: .9rem;
  transition: transform 140ms ease-out;
}
.pick-accordion-toggle.open {
  transform: rotate(90deg);
  color: var(--game-primary, #002868);
}
.score-events-list {
  list-style: none;
  margin: 0;
  padding: .75rem 1rem;
  font-size: .85rem;
}
.score-events-list li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: .75rem;
  padding: .2rem 0;
  animation: wc-event-fade-in 200ms ease-out both;
  animation-delay: calc(var(--event-i, 0) * 40ms);
}
.score-events-list .event-meta {
  color: var(--text-muted, #6c757d);
  font-size: .8rem;
  letter-spacing: .02em;
  text-transform: uppercase;
}
.score-events-list .event-pts {
  font-family: 'Teko', sans-serif;
  font-weight: 600;
  letter-spacing: .03em;
  color: var(--game-primary, #002868);
}
.score-events-list .event-source-dot {
  display: inline-block;
  width: .45em;
  height: .45em;
  border-radius: 50%;
  background: var(--game-accent, #BF0A30);
  margin-right: .5em;
  vertical-align: middle;
  opacity: .7;
}
.score-events-total {
  padding: .5rem 1rem .75rem;
  border-top: 1px dotted var(--border, #dee2e6);
  color: var(--text-muted, #6c757d);
  font-size: .8rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.score-events-empty {
  padding: .75rem 1rem;
  font-size: .85rem;
  color: var(--text-muted, #6c757d);
  font-style: italic;
}
@keyframes wc-event-fade-in {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 2: Create the shared partial**

Create `games/worldcup/templates/worldcup/_pick_row.html`:

```html
{# Shared pick-row partial. Expects: pick, events (list[ScoreEvent]), pick_index (int for id namespacing). #}
{% set row_id = 'pick-row-' ~ pick.id %}
<tr>
  <td class="fw-medium">
    <button type="button" class="pick-accordion-toggle"
            aria-controls="{{ row_id }}-body" aria-expanded="false"
            data-accordion-target="{{ row_id }}">
      <i class="bi bi-chevron-right"></i>
    </button>
    {{ pick.team.flag_emoji }} {{ pick.team.display_name }}
    <small class="text-muted">Group {{ pick.team.group_letter }}</small>
  </td>
  <td><span class="tier-badge tier-badge-{{ pick.tier }}">{{ tiers[pick.tier]['name'] }}</span></td>
  <td class="text-center"><span class="multiplier-badge">&times;{{ pick.team.multiplier }}</span></td>
  <td class="text-end">{{ "%.1f"|format(pick.base_points) }}</td>
  <td class="text-end fw-bold">{{ "%.1f"|format(pick.multiplied_points) }}</td>
</tr>
<tr class="pick-accordion-row">
  <td colspan="5" class="p-0">
    <div class="pick-accordion" id="{{ row_id }}-body">
      {% if events and events|length > 0 %}
      <ul class="score-events-list">
        {% for event in events %}
        <li style="--event-i: {{ loop.index0 }};">
          <span>
            <span class="event-source-dot"></span>
            {% if event.occurred_on %}
            <span class="event-meta">{{ event.occurred_on.strftime('%b %-d') }}</span> ·
            {% endif %}
            {{ event.label }}
          </span>
          <span class="event-pts">+{{ "%g"|format(event.base_points) }} base</span>
        </li>
        {% endfor %}
      </ul>
      <div class="score-events-total">
        Total base <strong>{{ "%.1f"|format(pick.base_points) }}</strong> &times; {{ pick.team.multiplier }} =
        <strong>{{ "%.1f"|format(pick.multiplied_points) }}</strong> multiplied
      </div>
      {% else %}
      <div class="score-events-empty">No scoring events yet.</div>
      {% endif %}
    </div>
  </td>
</tr>
```

Note: the mobile view continues to use the existing `.player-pick-card` layout (no drill-down on mobile to keep the list scannable). A follow-up can add mobile drill-down if you want parity later.

- [ ] **Step 3: Update `player_detail()` route to compute events**

In `games/worldcup/routes.py`, update the imports to include `compute_team_score_events`:

```python
from games.worldcup.services.scoring import (
    process_match_result,
    apply_group_advancement,
    set_knockout_teams,
    recalculate_all_scores,
    compute_match_attribution,
    compute_team_score_events,
)
```

Replace the `player_detail()` function body with:

```python
@worldcup_bp.route('/leaderboard/<int:enrollment_id>')
def player_detail(enrollment_id):
    """One player's 9 picks with per-team scores and drill-down events."""
    enrollment = db.get_or_404(WorldCupEnrollment, enrollment_id)
    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC

    is_owner = (
        current_user.is_authenticated
        and current_user.id == enrollment.user_id
    )
    is_admin = current_user.is_authenticated and current_user.is_admin
    picks_visible = deadline_passed or is_owner or is_admin

    picks = []
    events_by_pick: dict[int, list] = {}
    if picks_visible:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        events_by_pick = {p.id: compute_team_score_events(p.team) for p in picks}

    from games.worldcup.world_cup_countries import TIERS

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
        events_by_pick=events_by_pick,
        tiers=TIERS,
        picks_visible=picks_visible,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
    )
```

- [ ] **Step 4: Update `player_detail.html` to use the partial**

In `games/worldcup/templates/worldcup/player_detail.html`, replace the desktop-table block (currently lines 30-68 — the `<div class="card border-0 shadow-sm animate-in player-picks-desktop">` through its closing `</div>`) with:

```html
{# Desktop table with drill-down accordion #}
<div class="card border-0 shadow-sm animate-in player-picks-desktop">
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
            <td class="text-end fw-bold">{{ "%.1f"|format(ns.total_base) }}</td>
            <td class="text-end fw-bold">{{ "%.1f"|format(ns.total_mult) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</div>
```

Add an inline script block at the end of the `{% block content %}` (before the final `</div>`), to toggle the accordion:

```html
<script>
(function() {
  document.querySelectorAll('.pick-accordion-toggle').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var targetId = btn.dataset.accordionTarget + '-body';
      var body = document.getElementById(targetId);
      if (!body) return;
      var open = body.classList.toggle('open');
      btn.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
})();
</script>
```

- [ ] **Step 5: Start the dev server and manually verify**

```bash
FLASK_APP=app.py venv/bin/flask run
```

Open `/worldcup/leaderboard` post-deadline (temporarily set `TOURNAMENT_DEADLINE_UTC` to a past date in `games/worldcup/constants.py` for the test, revert after), click your own name, click the chevron next to a pick — accordion should expand. Stop the server.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py \
  games/worldcup/templates/worldcup/_pick_row.html \
  games/worldcup/templates/worldcup/player_detail.html \
  static/css/style.css
git commit -m "feat(worldcup): per-pick drill-down accordion on player detail"
```

---

## Task 7: Picks page parity — use shared partial

**Files:**
- Modify: `games/worldcup/routes.py` (`picks()`)
- Modify: `games/worldcup/templates/worldcup/picks.html`

- [ ] **Step 1: Pass `events_by_pick` from `picks()` route**

In `games/worldcup/routes.py`, in the `picks()` function, after `existing_picks = ...` assignment (around line 224), add:

```python
events_by_pick = {p.id: compute_team_score_events(p.team) for p in existing_picks}
```

Then update both `render_template('worldcup/picks.html', ...)` calls (the error-case render around line 283 and the final render around line 315) to include `events_by_pick=events_by_pick`.

- [ ] **Step 2: Update the read-only desktop block in `picks.html` to use the partial**

In `games/worldcup/templates/worldcup/picks.html`, replace the read-only desktop table block (currently lines 33-66 — `<div class="card border-0 shadow-sm mb-4 animate-in player-picks-desktop">` through its closing `</div>`) with:

```html
{# Desktop table with drill-down accordion #}
<div class="card border-0 shadow-sm mb-4 animate-in player-picks-desktop">
  <div class="card-header d-flex align-items-center justify-content-between">
    <h4 class="mb-0"><i class="bi bi-check2-square me-2"></i>Your 9 Picks</h4>
    <span class="fw-bold" style="font-family:'Teko',sans-serif; font-size:1.3rem; letter-spacing:.03em;">
      Total: {{ "%.1f"|format(enrollment.total_score) }} pts
    </span>
  </div>
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
          {% for pick in existing_picks %}
            {% with events = events_by_pick.get(pick.id, []) %}
              {% include 'worldcup/_pick_row.html' %}
            {% endwith %}
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add the same toggle script**

At the end of `picks.html`, inside the existing `{% block scripts %}` (after the `{% endif %}` for `show_edit_form`), add a second `<script>` guarded by the read-only path. Append:

```html
{% if deadline_passed or (not show_edit_form and has_picks) %}
<script>
(function() {
  document.querySelectorAll('.pick-accordion-toggle').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var targetId = btn.dataset.accordionTarget + '-body';
      var body = document.getElementById(targetId);
      if (!body) return;
      var open = body.classList.toggle('open');
      btn.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
})();
</script>
{% endif %}
```

- [ ] **Step 4: Run the existing post-deadline UI tests to confirm no regression**

```bash
venv/bin/python -m pytest tests/test_post_deadline_ui.py -v
```

Expected: all tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/picks.html
git commit -m "feat(worldcup): drill-down accordion on own picks page"
```

---

## Task 8: Admin dashboard — completed matches section

**Files:**
- Modify: `games/worldcup/routes.py` (`admin_dashboard()`)
- Modify: `games/worldcup/templates/worldcup/admin/dashboard.html`
- Test: `tests/test_worldcup_admin.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_worldcup_admin.py`:

```python
# ── Admin dashboard completed-matches list ──────────────────────────────

def _make_admin_user(app):
    """Create a platform admin user and return their id."""
    with app.app_context():
        user = User(username='wcadmin', email='wcadmin@test.com', is_admin=True)
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_two_completed_group_matches(app):
    """Seed two completed group matches with different update times."""
    with app.app_context():
        a = WorldCupTeam(
            fifa_code='AAA', name='Alpha', display_name='Alpha',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        b = WorldCupTeam(
            fifa_code='BBB', name='Beta', display_name='Beta',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        c = WorldCupTeam(
            fifa_code='CCC', name='Gamma', display_name='Gamma',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        d = WorldCupTeam(
            fifa_code='DDD', name='Delta', display_name='Delta',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        db.session.add_all([a, b, c, d])
        db.session.flush()

        from games.worldcup.services.scoring import process_match_result
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=a.id, away_team_id=b.id,
        )
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='A',
            home_team_id=c.id, away_team_id=d.id,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

        process_match_result(
            match_id=m1.id, home_score=1, away_score=0,
            winner_fifa_code='AAA',
        )
        process_match_result(
            match_id=m2.id, home_score=2, away_score=1,
            winner_fifa_code='CCC',
        )
        return m1.id, m2.id


def test_admin_dashboard_lists_completed_matches(client, app):
    admin_id = _make_admin_user(app)
    _seed_two_completed_group_matches(app)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    resp = client.get('/worldcup/admin/')
    assert resp.status_code == 200
    # Card header must be rendered
    assert b'Completed Matches' in resp.data
    # Both match numbers surface
    assert b'>1<' in resp.data or b'#1' in resp.data
    assert b'>2<' in resp.data or b'#2' in resp.data
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py::test_admin_dashboard_lists_completed_matches -v
```

Expected: FAIL (`b'Completed Matches' not in resp.data`).

- [ ] **Step 3: Update `admin_dashboard()` to query completed matches**

In `games/worldcup/routes.py`, in `admin_dashboard()`, after the `pending_matches = ...` query (around line 467-473), add:

```python
    completed_matches = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(
            WorldCupMatch.updated_at.desc(),
            WorldCupMatch.match_number.desc(),
        )
        .all()
    )
```

Update the `render_template(...)` call at the end of `admin_dashboard()` to include the new variable. Replace the call with:

```python
    return render_template('worldcup/admin/dashboard.html',
        total_matches=total_matches,
        completed_matches=completed_matches,
        pending_matches=pending_matches,
        groups_needing_advancement=groups_needing_advancement,
        knockout_unassigned=knockout_unassigned,
        total_enrolled=total_enrolled,
        total_paid=total_paid,
        picks_submitted=picks_submitted,
    )
```

- [ ] **Step 4: Render the completed-matches card in `dashboard.html`**

In `games/worldcup/templates/worldcup/admin/dashboard.html`, after the closing `</div>` of the "Matches Needing Scores" card (which ends around line 63), and before the "Groups Needing Advancement" card, insert:

```html
{# Completed Matches (reachable for edit) #}
{% if completed_matches %}
<div class="card mb-3">
    <div class="card-header d-flex align-items-center justify-content-between">
        <h4 class="mb-0">Completed Matches</h4>
        {% if completed_matches|length > 5 %}
        <button class="btn btn-sm btn-outline-secondary" type="button"
                data-bs-toggle="collapse" data-bs-target="#completedMatchesBody">
            Show all {{ completed_matches|length }}
        </button>
        {% endif %}
    </div>
    <div id="completedMatchesBody" class="card-body {% if completed_matches|length > 5 %}collapse{% endif %}">
        <div class="table-responsive">
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Stage</th>
                    <th>Result</th>
                    <th>Updated</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for match in completed_matches %}
                <tr>
                    <td>{{ match.match_number }}</td>
                    <td>
                        <span class="badge bg-secondary">{{ match.stage }}</span>
                        {% if match.group_letter %}({{ match.group_letter }}){% endif %}
                    </td>
                    <td>
                        {{ match.home_team.display_name if match.home_team else '?' }}
                        {{ match.home_score }}&ndash;{{ match.away_score }}
                        {{ match.away_team.display_name if match.away_team else '?' }}
                        {% if match.is_draw %}<small class="text-muted">(draw)</small>{% endif %}
                    </td>
                    <td>
                        <small class="text-muted">
                            {% if match.updated_at %}{{ match.updated_at.strftime('%b %-d, %-I:%M %p') }}{% else %}—{% endif %}
                        </small>
                    </td>
                    <td>
                        <a href="{{ url_for('worldcup.admin_match_result', match_id=match.id) }}"
                           class="btn btn-sm btn-outline-primary">Edit</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
    </div>
</div>
{% endif %}
```

- [ ] **Step 5: Run the test**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py::test_admin_dashboard_lists_completed_matches -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py \
  games/worldcup/templates/worldcup/admin/dashboard.html \
  tests/test_worldcup_admin.py
git commit -m "feat(worldcup): admin dashboard — Completed Matches card with edit link"
```

---

## Task 9: Admin match-result auto-winner JS + pulse animation

**Files:**
- Modify: `games/worldcup/templates/worldcup/admin/match_result.html`
- Modify: `static/css/style.css`

No Python change — `process_match_result()` already accepts the form's winner.

- [ ] **Step 1: Add the pulse keyframe to CSS**

In `static/css/style.css`, inside the `/* === WORLD CUP FANTASY POOL === */` section, append:

```css
/* Admin: auto-winner pulse on match_result form */
@keyframes wc-auto-pulse {
  0%   { background-color: transparent; }
  40%  { background-color: rgba(191, 10, 48, .18); }
  100% { background-color: transparent; }
}
.wc-auto-picked {
  animation: wc-auto-pulse 160ms ease-out;
}
```

- [ ] **Step 2: Add the auto-winner JS to `match_result.html`**

In `games/worldcup/templates/worldcup/admin/match_result.html`, inside the score-entry form block (before the submit `<button>` line — currently line 137), insert a hint element and an inline script at the very end of the template, before `{% endblock %}`.

First, inside the winner `<div class="form-check">` group, add a sibling hint element. Replace the whole winner block (currently lines 103-121) with:

```html
<div class="mt-3" id="winnerBlock" data-stage="{{ match.stage }}">
    <label class="form-label fw-bold">Winner</label>
    <div class="d-flex gap-3 flex-wrap">
        <div class="form-check">
            <input class="form-check-input" type="radio" name="winner" id="winner_home" value="home">
            <label class="form-check-label" for="winner_home">{{ match.home_team.display_name }}</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="radio" name="winner" id="winner_away" value="away">
            <label class="form-check-label" for="winner_away">{{ match.away_team.display_name }}</label>
        </div>
        {% if match.stage == 'group' %}
        <div class="form-check">
            <input class="form-check-input" type="radio" name="winner" id="winner_draw" value="draw">
            <label class="form-check-label" for="winner_draw">Draw</label>
        </div>
        {% endif %}
    </div>
    <small id="winnerHint" class="text-muted d-none mt-1 d-block">
        <i class="bi bi-exclamation-circle me-1"></i>
        Equal score — pick the winner and mark ET or penalties below.
    </small>
</div>
```

Then just before `{% endblock %}` at the end of the template, add:

```html
<script>
(function() {
  var home = document.querySelector('input[name="home_score"]');
  var away = document.querySelector('input[name="away_score"]');
  var block = document.getElementById('winnerBlock');
  var hint = document.getElementById('winnerHint');
  if (!home || !away || !block) return; // form not rendered (completed match)

  var stage = block.dataset.stage || 'group';
  var userOverride = false;

  var radios = block.querySelectorAll('input[name="winner"]');
  radios.forEach(function(r) {
    r.addEventListener('change', function(ev) {
      if (ev.isTrusted) userOverride = true;
    });
  });

  function clearRadios() {
    radios.forEach(function(r) { r.checked = false; });
  }

  function setRadio(value) {
    var r = block.querySelector('input[name="winner"][value="' + value + '"]');
    if (!r || r.checked) return;
    clearRadios();
    r.checked = true;
    var label = block.querySelector('label[for="' + r.id + '"]');
    if (label) {
      label.classList.remove('wc-auto-picked');
      // Force reflow so the animation re-runs if the same choice is re-picked.
      void label.offsetWidth;
      label.classList.add('wc-auto-picked');
    }
  }

  function deriveAndApply() {
    if (userOverride) return;
    var h = parseInt(home.value, 10);
    var a = parseInt(away.value, 10);
    if (isNaN(h) || isNaN(a)) {
      hint.classList.add('d-none');
      return;
    }
    if (h > a) {
      hint.classList.add('d-none');
      setRadio('home');
    } else if (a > h) {
      hint.classList.add('d-none');
      setRadio('away');
    } else {
      // Equal scores
      if (stage === 'group') {
        hint.classList.add('d-none');
        setRadio('draw');
      } else {
        // Knockout tie — admin must pick
        clearRadios();
        hint.classList.remove('d-none');
      }
    }
  }

  home.addEventListener('input', deriveAndApply);
  away.addEventListener('input', deriveAndApply);
})();
</script>
```

- [ ] **Step 3: Smoke-test the template renders**

```bash
venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected: `Smoke test OK`.

- [ ] **Step 4: Start the dev server, manually verify auto-pick**

```bash
FLASK_APP=app.py venv/bin/flask run
```

Log in as platform admin, navigate to `/worldcup/admin/match/1` (Match 1: Mexico vs South Africa). Enter home=2, away=1 — the "Mexico" radio should auto-check with a subtle red pulse. Enter home=1, away=1 — the "Draw" radio should auto-check (group match). Click the "Argentina" radio manually — further score changes should NOT flip it back. Stop the server.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/templates/worldcup/admin/match_result.html static/css/style.css
git commit -m "feat(worldcup): admin match entry — auto-derive winner from score"
```

---

## Task 10: Admin set-knockout — clear team assignment

**Files:**
- Modify: `games/worldcup/routes.py` (`admin_set_knockout()`)
- Modify: `games/worldcup/templates/worldcup/admin/set_knockout.html`
- Test: `tests/test_worldcup_admin.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_worldcup_admin.py`:

```python
# ── Clear knockout team assignment ──────────────────────────────────────

def _seed_knockout_match_with_teams(app, completed=False):
    """Seed an R16 knockout match with teams assigned; optionally completed."""
    with app.app_context():
        a = WorldCupTeam(
            fifa_code='AAA', name='Alpha', display_name='Alpha',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        b = WorldCupTeam(
            fifa_code='BBB', name='Beta', display_name='Beta',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='B',
        )
        db.session.add_all([a, b])
        db.session.flush()
        match = WorldCupMatch(
            match_number=105, stage='R16',
            home_team_id=a.id, away_team_id=b.id,
        )
        db.session.add(match)
        db.session.commit()

        if completed:
            from games.worldcup.services.scoring import process_match_result
            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='AAA',
            )
        return match.id


def test_clear_knockout_nulls_both_teams(client, app):
    admin_id = _make_admin_user(app)
    match_id = _seed_knockout_match_with_teams(app, completed=False)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    resp = client.post(
        f'/worldcup/admin/set-knockout/{match_id}',
        data={'action': 'clear', 'csrf_token': 'test'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        match = db.session.get(WorldCupMatch, match_id)
        assert match.home_team_id is None
        assert match.away_team_id is None


def test_clear_knockout_blocked_when_match_completed(client, app):
    admin_id = _make_admin_user(app)
    match_id = _seed_knockout_match_with_teams(app, completed=True)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    resp = client.post(
        f'/worldcup/admin/set-knockout/{match_id}',
        data={'action': 'clear', 'csrf_token': 'test'},
        follow_redirects=False,
    )
    # Redirect back to same page with flash; teams unchanged
    assert resp.status_code in (302, 303)

    with app.app_context():
        match = db.session.get(WorldCupMatch, match_id)
        assert match.home_team_id is not None
        assert match.away_team_id is not None
        assert match.is_completed is True
```

Note: the testing config has `WTF_CSRF_ENABLED=False` (verify in `config.py` if unsure); `csrf_token=test` is a placeholder that Flask-WTF ignores in test mode.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py -k "clear_knockout" -v
```

Expected: both FAIL — route doesn't handle `action=clear` yet.

- [ ] **Step 3: Extend `admin_set_knockout()` to handle `action=clear`**

In `games/worldcup/routes.py`, find `admin_set_knockout()` (around line 711). Replace the body of the `if request.method == 'POST':` block (currently lines 721-738) with:

```python
    if request.method == 'POST':
        action = request.form.get('action')

        # Handle clear action
        if action == 'clear':
            if match.is_completed:
                flash(
                    'Clear the match result first before clearing the team assignment.',
                    'error',
                )
                return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))
            match.home_team_id = None
            match.away_team_id = None
            db.session.commit()
            flash(
                f'Match #{match.match_number}: team assignment cleared.',
                'warning',
            )
            return redirect(url_for('worldcup.admin_dashboard'))

        # Handle assign action (default)
        home_code = request.form.get('home_team', '').strip()
        away_code = request.form.get('away_team', '').strip()

        if not home_code or not away_code:
            flash('Both teams are required.', 'error')
            return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))

        if home_code == away_code:
            flash('Home and away teams must be different.', 'error')
            return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))

        result = set_knockout_teams(match.id, home_code, away_code)
        if 'error' in result:
            flash(result['error'], 'error')
        else:
            flash(f'Match #{match.match_number}: teams set to {home_code} vs {away_code}.', 'success')
            return redirect(url_for('worldcup.admin_dashboard'))
```

- [ ] **Step 4: Add the clear button + lock hint to `set_knockout.html`**

In `games/worldcup/templates/worldcup/admin/set_knockout.html`, find the closing `</div>` of the `<div class="card">` wrapper (around line 78) that contains the assign form. Before it, after the assign form's closing `</form>`, add:

```html
{# Clear-assignment action (incomplete matches only). #}
{% if (match.home_team or match.away_team) and not match.is_completed %}
<hr class="my-4">
<form method="POST" action="{{ url_for('worldcup.admin_set_knockout', match_id=match.id) }}"
      onsubmit="return confirm('Clear both team assignments for Match #{{ match.match_number }}?');">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="hidden" name="action" value="clear">
    <button type="submit" class="btn btn-outline-danger">
        <i class="bi bi-x-octagon me-1"></i>Clear Team Assignment
    </button>
    <small class="text-muted ms-2">
        Nulls both home and away. Restores the match to an empty shell.
    </small>
</form>
{% elif match.is_completed %}
<hr class="my-4">
<p class="text-muted small mb-0">
    <i class="bi bi-lock me-1"></i>
    Match result is recorded. Clear the result on
    <a href="{{ url_for('worldcup.admin_match_result', match_id=match.id) }}">the result page</a>
    before reassigning teams.
</p>
{% endif %}
```

- [ ] **Step 5: Run the tests**

```bash
venv/bin/python -m pytest tests/test_worldcup_admin.py -v
```

Expected: all tests in the file PASS.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py \
  games/worldcup/templates/worldcup/admin/set_knockout.html \
  tests/test_worldcup_admin.py
git commit -m "feat(worldcup): admin — clear knockout team assignment (blocked when completed)"
```

---

## Task 11: Full test + pyright sweep

**Files:** none modified — safety check before reverting the deadline constant.

- [ ] **Step 1: Run the full test suite**

```bash
venv/bin/python -m pytest tests/ -v
```

Expected: 100% pass.

- [ ] **Step 2: Run pyright**

```bash
venv/bin/pyright
```

Expected: 0 errors, 0 warnings.

- [ ] **Step 3: Smoke test the app boots**

```bash
venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected: `Smoke test OK`.

No commit — this is a verification gate.

---

## Task 12: Revert `TOURNAMENT_DEADLINE_UTC` to production value

**Files:**
- Modify: `games/worldcup/constants.py`

- [ ] **Step 1: Restore the real kickoff time**

In `games/worldcup/constants.py`, replace line 21:

```python
TOURNAMENT_DEADLINE_UTC = datetime(2026, 4, 10, 19, 0, 0, tzinfo=ZoneInfo("UTC"))  # TEMP: past deadline for testing sections 7A-7G
```

with:

```python
TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
```

- [ ] **Step 2: Update the comment block above it**

Ensure the comment directly above the `TOURNAMENT_DEADLINE_UTC` line reads:

```python
# Picks lock at first match kickoff:
# Mexico vs South Africa, June 11, 2026, 3:00 PM ET = 2:00 PM CT = 7:00 PM UTC
```

- [ ] **Step 3: Smoke test the app still boots**

```bash
venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
"
```

Expected: `Smoke test OK`.

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/constants.py
git commit -m "chore: restore TOURNAMENT_DEADLINE_UTC to production value post-testing"
```

---

## Task 13: Manual re-verification of test-script sections 5A, 6, 7B, 7C, 7D

Work through the affected portions of `Human End-to-End Test Script.md`. Use a temporary past-deadline override only to verify the post-deadline leaderboard column — the production value restored in Task 12 stays intact between tests.

- [ ] **Step 1: Start dev server**

```bash
FLASK_APP=app.py venv/bin/flask run
```

- [ ] **Step 2: Verify Section 5A (tiebreaker hidden pre-deadline)**

Open `/worldcup/leaderboard` as an anonymous user. Confirm:
- No "Tiebreaker" column header
- No "TB: N" on mobile
- No value in `e.usa_goals_guess` visible

- [ ] **Step 3: Verify Section 6 (CT caption on schedule)**

Open `/worldcup/schedule`. Confirm the small "All kickoff times shown in Central Time" caption appears under the lead paragraph inside the hero.

- [ ] **Step 4: Verify Section 7B (auto-winner + attribution chips + drill-down)**

Log in as admin. Enter Match 1 result: Mexico 2 – South Africa 1. Confirm:
- Winner radio auto-checks "Mexico" with a red pulse
- Submitting succeeds
- `/worldcup/schedule` shows a "MEX +3 base" chip under Match 1's score
- Click any player's name on `/worldcup/leaderboard` (post-deadline required — skip if you don't want to temporarily flip the constant); click a chevron next to a pick — accordion reveals `Win vs ...  +3 base` etc.

- [ ] **Step 5: Verify Section 7C (edit completed match from dashboard)**

On `/worldcup/admin/`, scroll below "Matches Needing Scores" — confirm a "Completed Matches" card lists Match 1 with an Edit button. Click Edit, clear the result, confirm the dashboard drops the row.

- [ ] **Step 6: Verify Section 7D (clear knockout)**

Navigate to `/worldcup/admin/set-knockout/105` (an R16 match shell, match_number 105). Assign two teams. Refresh the page — the Clear Team Assignment button should now be visible. Click it, confirm both teams are nulled.

- [ ] **Step 7: Stop dev server and mark test script sections as ✅**

Update `Human End-to-End Test Script.md` notes for 5A, 6, 7B, 7C, 7D to reflect the fixes landed.

- [ ] **Step 8: Commit test-script note updates**

```bash
git add "Human End-to-End Test Script.md"
git commit -m "docs: mark test script sections 5A/6/7B/7C/7D as resolved"
```

---

## Done.

All six issues from the April 2026 test pass are now addressed, with unit tests guaranteeing the scoring-attribution derive logic stays in sync with the stored totals. The tournament deadline is back on its production value, ready for launch.
