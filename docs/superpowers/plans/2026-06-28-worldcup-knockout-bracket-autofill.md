# World Cup Knockout Bracket Auto-Fill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-fill the deterministic downstream knockout shells (R16→Final) the moment their feeder round completes, so forgetting/being-away never stalls scoring, while never writing a wrong bracket.

**Architecture:** A new isolated module `games/worldcup/services/bracket.py` derives each downstream pairing from a fixed bracket topology + our own completed results (primary "B"), cross-checks against the existing football-data.org proposal (`fetch_bracket_proposal`, "A"), and auto-writes via the existing `set_knockout_teams` only when B and A agree (or when A is unavailable, flagged). It folds into the existing 30-minute `run_scores()` timer — no new systemd unit. Group advancement and the group→R32 transition stay admin-confirmed and out of scope.

**Tech Stack:** Flask, SQLAlchemy 2.0, pytest, football-data.org REST API (already wired in `services/sync.py`).

## Global Constraints

- Timestamps: `datetime.now(timezone.utc)` — never `utcnow()`. (Not expected in this feature; no new timestamps written.)
- ORM: `db.session.get(Model, id)`; existing `.query` style is fine (no mass migration).
- Reuse the existing write path `set_knockout_teams(match_id, home_fifa, away_fifa)` and read path `fetch_bracket_proposal(stage)` — **do not** add a new scoring or results-entry path.
- **R32 is out of scope.** Auto-fill must never touch the group→R32 transition (`stage == 'R32'`), which stays admin-confirmed.
- **Empty shells only.** Never overwrite a shell that already has both teams.
- An auto-write happens only on `APPLY` (B and A agree) or `APPLY_UNCONFIRMED` (A unavailable, B complete). A reachable API that **disagrees** always blocks the write (`CONFLICT`).
- Match-number layout (fixed, verified in `ccc_local`): group `1–72`, R32 `73–88`, R16 `89–96`, QF `97–100`, SF `101–102`, third-place `103`, final `104`.
- KO stage codes: `'R32','R16','QF','SF','final','third_place'`. Downstream (in-scope) stages: `'R16','QF','SF','final','third_place'`.
- Tests run with: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -v`.
- Avoid a circular import: `bracket.py` imports from `sync.py` at module top; `sync.run_scores()` imports `bracket.run_bracket_autofill` **locally** inside the function.

---

## File Structure

- **Create** `games/worldcup/services/bracket.py` — topology constant + `infer_topology_from_api`, `derive_pairings`, `reconcile`, `run_bracket_autofill`.
- **Create** `tests/test_worldcup_bracket_autofill.py` — all new unit + integration tests.
- **Modify** `games/worldcup/services/sync.py` — call `run_bracket_autofill()` from `run_scores()`.
- **Modify** `games/worldcup/cli.py` — add `'bracket'` to `SYNC_MODES` + a dispatch branch.
- **Modify** `CLAUDE.md` — narrow the "KO bracket never auto-written" invariant.

Existing signatures this plan consumes (do not change them):
- `games.worldcup.services.scoring.set_knockout_teams(match_id: int, home_fifa_code: str, away_fifa_code: str) -> dict` — returns `{'match_number','home','away'}` or `{'error': ...}`.
- `games.worldcup.services.sync.fetch_bracket_proposal(target_stage: str) -> dict` — `{'target_stage','proposals':[{'match_number','shell_id','home_fifa','away_fifa','already_set','is_completed',...}],'unresolved':[...],'error': None|str}`. Raises `sync.SyncError` if the API is unreachable.
- `games.worldcup.services.sync.populatable_bracket_stages() -> list[str]`.
- `games.worldcup.services.sync._send_admin_email(subject: str, body: str) -> bool`.
- `games.worldcup.services.sync._notify_once(signature: str) -> bool`.
- `WorldCupMatch` fields: `match_number, stage, home_team_id, away_team_id, winner_team_id, is_completed, home_team, away_team` (relationships). `WorldCupTeam.fifa_code`.

---

### Task 1: Bracket topology constant + structural consistency lock + API-inference helper

**Files:**
- Create: `games/worldcup/services/bracket.py`
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Produces: `BRACKET_TOPOLOGY: dict[int, tuple[tuple[str,int], tuple[str,int]]]` (downstream match_number → two feeders, each `('winner'|'loser', feeder_match_number)`); `DOWNSTREAM_STAGES: tuple[str,...]`; `infer_topology_from_api() -> dict` (read-only, generates the topology dict from a fully-resolved API bracket — used to VERIFY the constant, never at runtime).

> **Topology authoring (read before Step 1):** The feeder numbers below are the structurally-valid *sequential* default. FIFA's official 2026 bracket uses a specific cross-mapping; the sequential default may pair the wrong matches. This is acceptable for safety (production blocks any B/A disagreement → degrades to manual, never a wrong write) but the happy path only auto-fills if the topology is correct. **Before merge you MUST replace the feeder numbers with the official values**, verified via `infer_topology_from_api()` against the API once the real bracket resolves, and/or against the official FIFA 2026 bracket diagram. Match `103`/`104` (third-place = SF losers, final = SF winners) are fixed and correct as written.

- [ ] **Step 1: Write the failing test (structural consistency)**

```python
# tests/test_worldcup_bracket_autofill.py
"""Knockout bracket auto-fill — topology, derivation, reconciliation, run."""
from unittest.mock import patch

import pytest

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


def test_topology_is_structurally_consistent():
    from games.worldcup.services.bracket import BRACKET_TOPOLOGY

    # Exactly the 16 downstream shells: R16 89-96, QF 97-100, SF 101-102,
    # third place 103, final 104.
    assert set(BRACKET_TOPOLOGY) == set(range(89, 105))

    feeder_uses = []  # (kind, feeder_no) usages across all shells
    for shell_no, feeders in BRACKET_TOPOLOGY.items():
        assert len(feeders) == 2, f"shell {shell_no} needs exactly 2 feeders"
        for kind, feeder_no in feeders:
            assert kind in ('winner', 'loser')
            assert feeder_no < shell_no, f"shell {shell_no} feeder {feeder_no} not earlier"
            feeder_uses.append((kind, feeder_no))

    # Third place = both SF losers; final = both SF winners.
    assert set(BRACKET_TOPOLOGY[103]) == {('loser', 101), ('loser', 102)}
    assert set(BRACKET_TOPOLOGY[104]) == {('winner', 101), ('winner', 102)}

    # Each R32 winner (73-88) feeds exactly one R16 slot.
    r32_winner_uses = [f for f in feeder_uses if f[0] == 'winner' and 73 <= f[1] <= 88]
    assert sorted(n for _, n in r32_winner_uses) == list(range(73, 89))

    # No (kind, feeder) pair is used twice except the deliberate SF reuse
    # (101 & 102 each feed both final-as-winner and third-as-loser).
    winner_feeders = [n for k, n in feeder_uses if k == 'winner']
    assert len(winner_feeders) == len(set(winner_feeders))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py::test_topology_is_structurally_consistent -v`
Expected: FAIL — `ModuleNotFoundError: games.worldcup.services.bracket`.

- [ ] **Step 3: Write the module with the topology constant + inference helper**

```python
# games/worldcup/services/bracket.py
"""Auto-fill deterministic downstream knockout shells (R16 -> Final).

Hybrid: derive each pairing from a fixed bracket topology + our own completed
results (primary), cross-check against the football-data.org proposal, and write
via the existing set_knockout_teams only when they agree (or when the API is
unavailable, flagged). R32 / group advancement are out of scope (admin-confirmed).
"""
import logging

from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from games.worldcup.services.scoring import set_knockout_teams
from games.worldcup.services.sync import (
    fetch_bracket_proposal, populatable_bracket_stages,
    _send_admin_email, _notify_once, SyncError, STAGE_MAP, _fifa_for_tla, _api_get,
    COMPETITION_CODE,
)

logger = logging.getLogger(__name__)

DOWNSTREAM_STAGES = ('R16', 'QF', 'SF', 'final', 'third_place')

# Downstream match_number -> (home_feeder, away_feeder); feeder = (kind, match_no).
# SEQUENTIAL DEFAULT — replace 89-100 feeders with the official FIFA 2026 values
# (verify via infer_topology_from_api). 101-104 are fixed/correct.
BRACKET_TOPOLOGY: dict[int, tuple[tuple[str, int], tuple[str, int]]] = {
    89: (('winner', 73), ('winner', 74)),
    90: (('winner', 75), ('winner', 76)),
    91: (('winner', 77), ('winner', 78)),
    92: (('winner', 79), ('winner', 80)),
    93: (('winner', 81), ('winner', 82)),
    94: (('winner', 83), ('winner', 84)),
    95: (('winner', 85), ('winner', 86)),
    96: (('winner', 87), ('winner', 88)),
    97: (('winner', 89), ('winner', 90)),
    98: (('winner', 91), ('winner', 92)),
    99: (('winner', 93), ('winner', 94)),
    100: (('winner', 95), ('winner', 96)),
    101: (('winner', 97), ('winner', 98)),
    102: (('winner', 99), ('winner', 100)),
    103: (('loser', 101), ('loser', 102)),
    104: (('winner', 101), ('winner', 102)),
}


def infer_topology_from_api() -> dict:
    """Generate the topology dict from a FULLY-RESOLVED API bracket (verify aid).

    For each downstream KO fixture with both teams resolved, find which earlier
    match's winner (or loser) each team is, and emit the feeder pair. Returns
    {match_number: ((kind, feeder_no), (kind, feeder_no))}. Read-only; used to
    confirm BRACKET_TOPOLOGY matches reality — never called at runtime.
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    by_num = {}  # our match_number -> (winner_fifa, loser_fifa) for completed KO
    api_by_num = {}  # our match_number -> (home_fifa, away_fifa) resolved
    # Map API fixtures to our shells by api_fixture_id.
    shells = {m.api_fixture_id: m for m in WorldCupMatch.query.all() if m.api_fixture_id}
    for f in data.get('matches', []):
        shell = shells.get(f.get('id'))
        if not shell:
            continue
        home = _fifa_for_tla((f.get('homeTeam') or {}).get('tla'))
        away = _fifa_for_tla((f.get('awayTeam') or {}).get('tla'))
        if home and away:
            api_by_num[shell.match_number] = (home, away)
        winner_side = (f.get('score') or {}).get('winner')
        if winner_side in ('HOME_TEAM', 'AWAY_TEAM') and home and away:
            w, l = (home, away) if winner_side == 'HOME_TEAM' else (away, home)
            by_num[shell.match_number] = (w, l)

    winner_of = {fifa: n for n, (fifa, _) in by_num.items()}
    loser_of = {fifa: n for n, (_, fifa) in by_num.items()}
    topo = {}
    for num, (home, away) in api_by_num.items():
        if num < 89:
            continue
        def feeder(fifa):
            if fifa in winner_of:
                return ('winner', winner_of[fifa])
            if fifa in loser_of:
                return ('loser', loser_of[fifa])
            return None
        fh, fa = feeder(home), feeder(away)
        if fh and fa:
            topo[num] = (fh, fa)
    return dict(sorted(topo.items()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py::test_topology_is_structurally_consistent -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/bracket.py tests/test_worldcup_bracket_autofill.py
git commit -m "feat(worldcup): bracket topology constant + consistency lock + API inference helper"
```

---

### Task 2: `derive_pairings(stage)` — self-derived pairings from our own results

**Files:**
- Modify: `games/worldcup/services/bracket.py`
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Consumes: `BRACKET_TOPOLOGY`, `WorldCupMatch`, `WorldCupTeam`.
- Produces: `derive_pairings(stage: str) -> dict[int, tuple[str, str]] | None` — `{shell_id: (home_fifa, away_fifa)}` for every EMPTY shell of `stage`, or `None` if the stage is not fully ready (any feeder not completed / no winner / team unresolvable). Also `_winner_fifa(match_number) -> str | None` and `_loser_fifa(match_number) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_worldcup_bracket_autofill.py

def _team(fifa, name, group='A', tier=1, mult=1.0):
    t = WorldCupTeam(fifa_code=fifa, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='UEFA', group_letter=group)
    db.session.add(t)
    return t


def _completed_ko(match_number, stage, home, away, winner):
    """Create a completed KO match with a winner; return the shell."""
    m = WorldCupMatch(match_number=match_number, stage=stage,
                      home_team_id=home.id, away_team_id=away.id,
                      winner_team_id=winner.id, is_completed=True,
                      home_score=1, away_score=0)
    db.session.add(m)
    return m


def test_derive_pairings_r16_happy_path(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)   # winner BRA
        _completed_ko(74, 'R32', ned, mex, mex)   # winner MEX
        shell = WorldCupMatch(match_number=89, stage='R16')  # empty
        db.session.add(shell)
        db.session.commit()
        out = derive_pairings('R16')
        assert out == {shell.id: ('BRA', 'MEX')}


def test_derive_pairings_not_ready_when_feeder_incomplete(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)
        # match 74 NOT completed (no winner)
        m74 = WorldCupMatch(match_number=74, stage='R32',
                            home_team_id=ned.id, away_team_id=mex.id, is_completed=False)
        db.session.add(m74)
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))
        db.session.commit()
        assert derive_pairings('R16') is None


def test_derive_pairings_third_place_uses_sf_losers(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        a, b = _team('ARG', 'Argentina'), _team('FRA', 'France')
        c, d = _team('ESP', 'Spain'), _team('GER', 'Germany')
        db.session.flush()
        _completed_ko(101, 'SF', a, b, a)   # loser FRA
        _completed_ko(102, 'SF', c, d, d)   # loser ESP
        shell = WorldCupMatch(match_number=103, stage='third_place')
        db.session.add(shell)
        db.session.commit()
        out = derive_pairings('third_place')
        assert out == {shell.id: ('FRA', 'ESP')}


def test_derive_pairings_skips_already_filled_shell(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)
        _completed_ko(74, 'R32', ned, mex, mex)
        # shell 89 already filled -> not in output
        WorldCupMatch.query  # no-op for readability
        filled = WorldCupMatch(match_number=89, stage='R16',
                               home_team_id=bra.id, away_team_id=mex.id)
        db.session.add(filled)
        db.session.commit()
        assert derive_pairings('R16') == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k derive_pairings -v`
Expected: FAIL — `ImportError: cannot import name 'derive_pairings'`.

- [ ] **Step 3: Implement `derive_pairings` + feeder helpers**

```python
# append to games/worldcup/services/bracket.py

def _winner_fifa(match_number: int) -> str | None:
    m = WorldCupMatch.query.filter_by(match_number=match_number).first()
    if not m or not m.is_completed or not m.winner_team_id:
        return None
    w = db.session.get(WorldCupTeam, m.winner_team_id)
    return w.fifa_code if w else None


def _loser_fifa(match_number: int) -> str | None:
    m = WorldCupMatch.query.filter_by(match_number=match_number).first()
    if not m or not m.is_completed or not m.winner_team_id:
        return None
    loser_id = m.home_team_id if m.winner_team_id == m.away_team_id else m.away_team_id
    l = db.session.get(WorldCupTeam, loser_id) if loser_id else None
    return l.fifa_code if l else None


def _resolve_feeder(kind: str, feeder_no: int) -> str | None:
    return _winner_fifa(feeder_no) if kind == 'winner' else _loser_fifa(feeder_no)


def derive_pairings(stage: str) -> dict | None:
    """{shell_id: (home_fifa, away_fifa)} for every EMPTY shell of `stage`.

    Returns None if the stage is not fully ready: any feeder match is not yet
    completed / has no winner, or a derived team cannot be resolved. Empty dict
    means the stage has no empty shells (already filled).
    """
    empty_shells = (
        WorldCupMatch.query.filter_by(stage=stage)
        .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                       WorldCupMatch.away_team_id.is_(None)))
        .all()
    )
    out: dict = {}
    for shell in empty_shells:
        feeders = BRACKET_TOPOLOGY.get(shell.match_number)
        if not feeders:
            logger.warning('No topology entry for shell #%s', shell.match_number)
            return None
        (hk, hn), (ak, an) = feeders
        home = _resolve_feeder(hk, hn)
        away = _resolve_feeder(ak, an)
        if not home or not away or home == away:
            return None  # stage not ready (feeder unplayed or unresolved)
        out[shell.id] = (home, away)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k derive_pairings -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/bracket.py tests/test_worldcup_bracket_autofill.py
git commit -m "feat(worldcup): derive_pairings — self-derived KO pairings from our results"
```

---

### Task 3: `reconcile(stage)` — the hybrid decision

**Files:**
- Modify: `games/worldcup/services/bracket.py`
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Consumes: `derive_pairings`, `fetch_bracket_proposal`, `SyncError`.
- Produces: `reconcile(stage: str) -> dict` with keys `stage`, `decision` (`'APPLY'|'CONFLICT'|'APPLY_UNCONFIRMED'|'NOT_READY'`), `pairings` (`{shell_id: (home,away)}`, present for APPLY/APPLY_UNCONFIRMED), `conflicts` (`list[dict]`, present for CONFLICT).

> "Agrees" = for every shell B proposes, A has a matching proposal with the same unordered pair `frozenset({home_fifa, away_fifa})`. Orientation differences are NOT a conflict; on write we use B's order. If A is missing any shell B has, or `error` is set, or `fetch_bracket_proposal` raises `SyncError` → A is treated as unavailable → `APPLY_UNCONFIRMED`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_worldcup_bracket_autofill.py

def _api_proposal(shell_id, home, away):
    return {'target_stage': 'R16', 'error': None, 'unresolved': [],
            'proposals': [{'match_number': 89, 'shell_id': shell_id,
                           'home_fifa': home, 'away_fifa': away,
                           'already_set': False, 'is_completed': False}]}


def _seed_r16_ready():
    """Two completed R32 feeders + one empty R16 shell; returns shell_id."""
    bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
    ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
    db.session.flush()
    _completed_ko(73, 'R32', bra, kor, bra)
    _completed_ko(74, 'R32', ned, mex, mex)
    shell = WorldCupMatch(match_number=89, stage='R16')
    db.session.add(shell)
    db.session.commit()
    return shell.id


def test_reconcile_apply_when_api_agrees(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'MEX', 'BRA')):  # reversed order ok
            d = bracket.reconcile('R16')
        assert d['decision'] == 'APPLY'
        assert d['pairings'] == {sid: ('BRA', 'MEX')}


def test_reconcile_conflict_when_api_disagrees(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'KOR')):  # wrong team
            d = bracket.reconcile('R16')
        assert d['decision'] == 'CONFLICT'
        assert d['conflicts'] and d['conflicts'][0]['shell_id'] == sid


def test_reconcile_apply_unconfirmed_when_api_unavailable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=bracket.SyncError('down')):
            d = bracket.reconcile('R16')
        assert d['decision'] == 'APPLY_UNCONFIRMED'
        assert d['pairings'] == {sid: ('BRA', 'MEX')}


def test_reconcile_not_ready_when_feeders_incomplete(app):
    from games.worldcup.services import bracket
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))  # no feeders
        db.session.commit()
        d = bracket.reconcile('R16')
        assert d['decision'] == 'NOT_READY'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k reconcile -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'reconcile'`.

- [ ] **Step 3: Implement `reconcile`**

```python
# append to games/worldcup/services/bracket.py

def reconcile(stage: str) -> dict:
    """Combine self-derived pairings (B) with the API proposal (A)."""
    pairings = derive_pairings(stage)
    if not pairings:  # None (not ready) or {} (nothing empty)
        return {'stage': stage, 'decision': 'NOT_READY'}

    try:
        proposal = fetch_bracket_proposal(stage)
    except SyncError:
        return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}

    if proposal.get('error'):
        return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}

    api_by_shell = {
        p['shell_id']: frozenset({p.get('home_fifa'), p.get('away_fifa')})
        for p in proposal.get('proposals', [])
        if p.get('home_fifa') and p.get('away_fifa')
    }

    conflicts = []
    for shell_id, (home, away) in pairings.items():
        api_pair = api_by_shell.get(shell_id)
        if api_pair is None:
            # API hasn't resolved this shell we can derive -> unavailable, not wrong.
            return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}
        if api_pair != frozenset({home, away}):
            conflicts.append({'shell_id': shell_id, 'ours': [home, away],
                              'api': sorted(api_pair)})

    if conflicts:
        return {'stage': stage, 'decision': 'CONFLICT', 'conflicts': conflicts}
    return {'stage': stage, 'decision': 'APPLY', 'pairings': pairings}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k reconcile -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/bracket.py tests/test_worldcup_bracket_autofill.py
git commit -m "feat(worldcup): reconcile — hybrid B/A decision for bracket auto-fill"
```

---

### Task 4: `run_bracket_autofill()` — write, notify, guard

**Files:**
- Modify: `games/worldcup/services/bracket.py`
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Consumes: `reconcile`, `populatable_bracket_stages`, `set_knockout_teams`, `_send_admin_email`, `_notify_once`.
- Produces: `run_bracket_autofill() -> dict` — `{'status': 'idle'|'acted', 'stages': [{'stage','decision','filled':[match_numbers]}]}`. Writes only empty shells; excludes `'R32'`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_worldcup_bracket_autofill.py

def test_autofill_apply_writes_shells_and_emails(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'populatable_bracket_stages', return_value=['R16']), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'MEX')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email:
            out = bracket.run_bracket_autofill()
        assert out['status'] == 'acted'
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'BRA' and s.away_team.fifa_code == 'MEX'
        assert email.called  # receipt sent


def test_autofill_conflict_writes_nothing_and_dedupes_email(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'populatable_bracket_stages', return_value=['R16']), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'KOR')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email, \
             patch.object(bracket, '_notify_once', side_effect=[True, False]):
            bracket.run_bracket_autofill()  # first: notifies
            bracket.run_bracket_autofill()  # second: deduped
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team_id is None and s.away_team_id is None  # never written
        assert email.call_count == 1  # _notify_once gated the 2nd send


def test_autofill_never_touches_r32(app):
    from games.worldcup.services import bracket
    with app.app_context():
        with patch.object(bracket, 'populatable_bracket_stages',
                          return_value=['R32', 'R16']) as pop, \
             patch.object(bracket, 'reconcile',
                          return_value={'stage': 'x', 'decision': 'NOT_READY'}) as rec:
            bracket.run_bracket_autofill()
        # reconcile is called for R16 only, never R32
        called_stages = [c.args[0] for c in rec.call_args_list]
        assert 'R32' not in called_stages and 'R16' in called_stages


def test_autofill_idle_when_nothing_populatable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        with patch.object(bracket, 'populatable_bracket_stages', return_value=[]):
            out = bracket.run_bracket_autofill()
        assert out['status'] == 'idle'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k autofill -v`
Expected: FAIL — `AttributeError: ... 'run_bracket_autofill'`.

- [ ] **Step 3: Implement `run_bracket_autofill`**

```python
# append to games/worldcup/services/bracket.py

def _shell_label(shell_id: int, home: str, away: str) -> str:
    m = db.session.get(WorldCupMatch, shell_id)
    num = m.match_number if m else '?'
    return f'#{num}: {home} vs {away}'


def run_bracket_autofill() -> dict:
    """Fill empty downstream KO shells whose feeder round is resolved.

    Folded into run_scores() (30-min timer). Writes only on APPLY /
    APPLY_UNCONFIRMED; CONFLICT writes nothing and emails once (de-duped).
    R32 is excluded — the group->R32 transition stays admin-confirmed.
    """
    stages = [s for s in populatable_bracket_stages() if s in DOWNSTREAM_STAGES]
    if not stages:
        return {'status': 'idle', 'stages': []}

    acted = []
    for stage in stages:
        d = reconcile(stage)
        decision = d['decision']
        if decision == 'NOT_READY':
            continue

        if decision == 'CONFLICT':
            if _notify_once(f'bracket-conflict:{stage}'):
                lines = [f"  {c['ours']} (ours) vs {sorted(c['api'])} (API)"
                         for c in d['conflicts']]
                _send_admin_email(
                    f'Bracket auto-fill BLOCKED ({stage}): API disagrees',
                    'Our results and the API disagree on these shells — '
                    'no teams written. Confirm manually at '
                    f'/worldcup/admin/bracket/{stage}.\n' + '\n'.join(lines))
            acted.append({'stage': stage, 'decision': decision, 'filled': []})
            continue

        # APPLY or APPLY_UNCONFIRMED -> write empty shells.
        filled = []
        for shell_id, (home, away) in d['pairings'].items():
            res = set_knockout_teams(shell_id, home, away)
            if 'error' in res:
                logger.warning('autofill write failed shell=%s: %s', shell_id, res['error'])
            else:
                filled.append(_shell_label(shell_id, home, away))
        if filled:
            unconfirmed = decision == 'APPLY_UNCONFIRMED'
            subject = (f'Bracket auto-filled ({stage})'
                       + (' — NO API confirmation, please spot-check' if unconfirmed else ''))
            note = ('\n\nThe API was unavailable, so this was written from our own '
                    'results without a second-opinion cross-check.' if unconfirmed else '')
            _send_admin_email(subject,
                              f'Auto-filled {stage} shells:\n  ' + '\n  '.join(filled) + note)
        acted.append({'stage': stage, 'decision': decision,
                      'filled': filled})

    return {'status': 'acted' if acted else 'idle', 'stages': acted}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k autofill -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/bracket.py tests/test_worldcup_bracket_autofill.py
git commit -m "feat(worldcup): run_bracket_autofill — write/notify/guard the downstream rounds"
```

---

### Task 5: Wire into the 30-min timer (`run_scores`) + CLI `--mode bracket`

**Files:**
- Modify: `games/worldcup/services/sync.py` (function `run_scores`, ~lines 523-536)
- Modify: `games/worldcup/cli.py` (`SYNC_MODES` line 31; `sync_cmd` ~line 459)
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Consumes: `bracket.run_bracket_autofill`.
- Produces: `run_scores()` return dict gains a `'bracket'` key with the autofill summary. CLI gains `--mode bracket`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_worldcup_bracket_autofill.py

def test_run_scores_invokes_bracket_autofill(app):
    from games.worldcup.services import sync
    with app.app_context():
        with patch.object(sync, 'sync_scores',
                          return_value={'applied_count': 0, 'failed': [],
                                        'skipped_unassigned': 0, 'applied': []}), \
             patch('games.worldcup.services.bracket.run_bracket_autofill',
                   return_value={'status': 'idle', 'stages': []}) as af:
            out = sync.run_scores()
        assert af.called
        assert out['bracket'] == {'status': 'idle', 'stages': []}


def test_cli_bracket_mode_dispatches(app):
    from games.worldcup.cli import SYNC_MODES
    assert 'bracket' in SYNC_MODES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k "run_scores or cli_bracket" -v`
Expected: FAIL — `out['bracket']` KeyError and `'bracket' not in SYNC_MODES`.

- [ ] **Step 3a: Wire `run_bracket_autofill` into `run_scores`**

In `games/worldcup/services/sync.py`, edit `run_scores()` so its three return paths all carry a `bracket` summary. Replace the body after `result = sync_scores()` succeeds:

```python
def run_scores() -> dict:
    """Timer entry point (every 30 min): apply finals + auto-fill downstream
    KO shells; email only on error / on bracket events."""
    try:
        result = sync_scores()
    except SyncError as exc:
        _send_admin_email('Score sync failed', f'football-data.org sync error:\n{exc}')
        return {'status': 'error', 'details': str(exc)}

    # Auto-fill any downstream KO round whose feeder round just completed.
    # Local import avoids a circular import (bracket imports from sync).
    from games.worldcup.services.bracket import run_bracket_autofill
    try:
        bracket_summary = run_bracket_autofill()
    except SyncError as exc:
        # API outage during the bracket pass is non-fatal to score sync.
        logger.warning('bracket auto-fill skipped (API error): %s', exc)
        bracket_summary = {'status': 'error', 'details': str(exc)}

    if result['applied_count']:
        logger.info('worldcup sync applied %s result(s)', result['applied_count'])
    if result['failed']:
        body = '\n'.join(f"#{f['match_number']}: {f['error']}" for f in result['failed'])
        _send_admin_email('Score sync: some results failed to apply', body)
        return {'status': 'error', 'bracket': bracket_summary, **result}
    return {'status': 'ok', 'bracket': bracket_summary, **result}
```

- [ ] **Step 3b: Add the CLI mode**

In `games/worldcup/cli.py` line 31, add `'bracket'`:

```python
SYNC_MODES = ('link', 'scores', 'advancement', 'digest', 'status', 'bracket')
```

In `sync_cmd`, add a branch before the `elif mode == 'status':` branch:

```python
    elif mode == 'bracket':
        from games.worldcup.services import bracket as wc_bracket
        result = wc_bracket.run_bracket_autofill()
        click.echo(f"[bracket] {result.get('status')}")
        for s in result.get('stages', []):
            click.echo(f"   {s['stage']}: {s['decision']} "
                       f"(filled {len(s.get('filled', []))})")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -k "run_scores or cli_bracket" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/sync.py games/worldcup/cli.py tests/test_worldcup_bracket_autofill.py
git commit -m "feat(worldcup): run bracket auto-fill in the 30-min scores timer + CLI --mode bracket"
```

---

### Task 6: Full R32→Final auto-advance simulation (integration test)

**Files:**
- Test: `tests/test_worldcup_bracket_autofill.py`

**Interfaces:**
- Consumes: `run_bracket_autofill`, `set_knockout_teams`, `WorldCupMatch`.

> This test proves a whole bracket auto-advances round-by-round using the **default sequential topology** (so it is independent of the official-values transcription). It seeds R32 with 32 teams and 16 completed results, then alternately: run autofill (fills next round's empty shells) → mark that round's matches completed with winners → repeat, through the final + third place. The API cross-check is patched to agree (return the same pairings the derivation produces).

- [ ] **Step 1: Write the integration test**

```python
# append to tests/test_worldcup_bracket_autofill.py

def _agreeing_proposal(stage):
    """Build an API proposal that mirrors derive_pairings (always agrees)."""
    from games.worldcup.services.bracket import derive_pairings
    pairings = derive_pairings(stage) or {}
    return {'target_stage': stage, 'error': None, 'unresolved': [],
            'proposals': [{'match_number': db.session.get(WorldCupMatch, sid).match_number,
                           'shell_id': sid, 'home_fifa': h, 'away_fifa': a,
                           'already_set': False, 'is_completed': False}
                          for sid, (h, a) in pairings.items()]}


def test_full_bracket_auto_advances_r32_to_final(app):
    from games.worldcup.services import bracket
    with app.app_context():
        # 32 teams T01..T32.
        teams = []
        for i in range(1, 33):
            teams.append(_team(f'T{i:02d}', f'Team{i}', group='A'))
        db.session.flush()

        # R32 #73-88: pair teams (0,1),(2,3),... home wins each (lower index).
        for idx, num in enumerate(range(73, 89)):
            h, a = teams[idx * 2], teams[idx * 2 + 1]
            _completed_ko(num, 'R32', h, a, h)

        # Empty shells for R16/QF/SF/third/final.
        for num in range(89, 97):
            db.session.add(WorldCupMatch(match_number=num, stage='R16'))
        for num in range(97, 101):
            db.session.add(WorldCupMatch(match_number=num, stage='QF'))
        for num in (101, 102):
            db.session.add(WorldCupMatch(match_number=num, stage='SF'))
        db.session.add(WorldCupMatch(match_number=103, stage='third_place'))
        db.session.add(WorldCupMatch(match_number=104, stage='final'))
        db.session.commit()

        def complete_round(stage):
            """Mark every filled shell of `stage` completed; home team wins."""
            for m in WorldCupMatch.query.filter_by(stage=stage).all():
                if m.home_team_id and m.away_team_id and not m.is_completed:
                    m.winner_team_id = m.home_team_id
                    m.home_score, m.away_score, m.is_completed = 1, 0, True
            db.session.commit()

        # Patch populatable_bracket_stages + API to track our own DB state.
        def fake_populatable():
            stages = []
            for st in bracket.DOWNSTREAM_STAGES:
                empty = (WorldCupMatch.query.filter_by(stage=st)
                         .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                                        WorldCupMatch.away_team_id.is_(None))).count())
                if empty:
                    stages.append(st)
            return stages

        with patch.object(bracket, '_send_admin_email', return_value=True), \
             patch.object(bracket, 'populatable_bracket_stages', side_effect=fake_populatable), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=lambda st: _agreeing_proposal(st)):
            # R16 fills from R32 results.
            bracket.run_bracket_autofill()
            assert WorldCupMatch.query.filter_by(match_number=89).first().home_team_id is not None
            complete_round('R16')
            # QF fills, then SF, then final+third.
            bracket.run_bracket_autofill(); complete_round('QF')
            bracket.run_bracket_autofill(); complete_round('SF')
            bracket.run_bracket_autofill()  # fills final (104) + third place (103)

        final = WorldCupMatch.query.filter_by(match_number=104).first()
        third = WorldCupMatch.query.filter_by(match_number=103).first()
        assert final.home_team_id is not None and final.away_team_id is not None
        assert third.home_team_id is not None and third.away_team_id is not None
        # Final = SF winners (home sides); third = SF losers (away sides).
        sf1 = WorldCupMatch.query.filter_by(match_number=101).first()
        sf2 = WorldCupMatch.query.filter_by(match_number=102).first()
        assert {final.home_team_id, final.away_team_id} == {sf1.winner_team_id, sf2.winner_team_id}
        assert {third.home_team_id, third.away_team_id} == {sf1.away_team_id, sf2.away_team_id}
```

- [ ] **Step 2: Run the test**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py::test_full_bracket_auto_advances_r32_to_final -v`
Expected: PASS.

- [ ] **Step 3: Run the whole new file + the existing bracket/sync suites**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py tests/test_worldcup_bracket.py tests/test_worldcup_sync.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_worldcup_bracket_autofill.py
git commit -m "test(worldcup): full R32->Final auto-advance simulation"
```

---

### Task 7: Transcribe official topology + verify against the API, then narrow the CLAUDE.md invariant

**Files:**
- Modify: `games/worldcup/services/bracket.py` (`BRACKET_TOPOLOGY` values 89-100)
- Modify: `CLAUDE.md`

**Interfaces:** none (data + docs).

- [ ] **Step 1: Replace feeders 89-100 with the official FIFA 2026 values**

Open the official FIFA 2026 bracket (the same source used to verify the R32 pairings last session — the published match schedule labels each KO match "Winners Match N vs Winners Match M"). For each R16 shell (89-96) and QF shell (97-100), set the two feeder match numbers to the official ones. Leave 101-104 unchanged. The structural consistency test (Task 1) must still pass after editing.

- [ ] **Step 2: Verify the constant against the API (when the bracket has resolved)**

When the real tournament has the relevant rounds resolved (or on a fully-simulated `ccc_local`), run this one-shot and confirm it matches `BRACKET_TOPOLOGY` for every resolved shell:

```bash
ENVIRONMENT=development venv/bin/python -c "
from app import create_app
app = create_app('development')
with app.app_context():
    from games.worldcup.services.bracket import infer_topology_from_api, BRACKET_TOPOLOGY
    api = infer_topology_from_api()
    for num, feeders in sorted(api.items()):
        ours = BRACKET_TOPOLOGY.get(num)
        flag = 'OK ' if set(ours) == set(feeders) else 'MISMATCH'
        print(f'{flag} #{num}: api={feeders} ours={ours}')
"
```

Expected: every resolved shell prints `OK`. Any `MISMATCH` is a transcription error — fix the constant. (Until the rounds resolve, this verifies nothing yet; the production cross-check still blocks any wrong write in the meantime.)

- [ ] **Step 3: Re-run the consistency + simulation tests**

Run: `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_bracket_autofill.py -v`
Expected: all PASS (the simulation uses sequential `complete_round` logic that is topology-agnostic, so official values do not break it).

- [ ] **Step 4: Narrow the CLAUDE.md invariant**

In `CLAUDE.md`, under **World Cup scoring & ranking → Results automation**, the line currently reads (paraphrased): "Group advancement + KO bracket are admin-confirmed via the 'Load from API' pre-fill ... never auto-written." Replace with:

```
- **Results + downstream-bracket automation:** `games/worldcup/services/sync.py` auto-applies completed-match results; `games/worldcup/services/bracket.py` (`run_bracket_autofill`, folded into the 30-min `run_scores` timer + `flask worldcup sync --mode bracket`) auto-fills the **deterministic downstream KO rounds (R16→Final)** once a feeder round completes — hybrid: pairings derived from our own results (`derive_pairings` + `BRACKET_TOPOLOGY`) and cross-checked against the API proposal (`reconcile`); auto-writes only when they agree (APPLY) or the API is down (APPLY_UNCONFIRMED, flagged), and a reachable API that disagrees BLOCKS the write (CONFLICT → admin email). **Group advancement + the group→R32 transition remain admin-confirmed** (`/worldcup/admin/advancement`, "Load from API") — tiebreaker risk; never auto-written. The manual `/worldcup/admin/bracket/<stage>` pages stay as the override for every KO round. Don't add a parallel results-entry or scoring path.
```

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/services/bracket.py CLAUDE.md
git commit -m "feat(worldcup): official bracket topology + narrow auto-fill invariant in CLAUDE.md"
```

---

## Self-Review

**Spec coverage:**
- Trigger folded into 30-min `run_scores` (no new timer) → Task 5. ✓
- `BRACKET_TOPOLOGY` + authoring/verification (consistency test, API inference, eyeball) → Tasks 1, 7. ✓
- `derive_pairings` (B, incl. third-place loser derivation) → Task 2. ✓
- `reconcile` 4-row decision table → Task 3. ✓
- `run_bracket_autofill` guardrails (empty-only, distinct real teams, R32 excluded, dedup notifications, receipts) → Task 4. ✓
- Full R32→Final simulation → Task 6. ✓
- CLAUDE.md invariant narrowed → Task 7. ✓
- API-unavailable policy (APPLY_UNCONFIRMED, flagged) → Tasks 3, 4. ✓

**Placeholder scan:** Topology values 89-100 are a structurally-valid default explicitly flagged for official-source replacement in Task 7 (with a concrete verification command), not a silent TODO. All test/impl steps contain full code. No "TBD"/"handle edge cases". ✓

**Type consistency:** `derive_pairings -> dict|None` ({shell_id: (home_fifa, away_fifa)}) consumed identically in `reconcile` and `run_bracket_autofill`; `reconcile -> dict` with `decision`/`pairings`/`conflicts` consumed in `run_bracket_autofill`; `set_knockout_teams(match_id, home_fifa, away_fifa)` called with shell_id + fifa codes per its real signature; `fetch_bracket_proposal` patched at `games.worldcup.services.bracket` (module-level import) in every test. ✓
