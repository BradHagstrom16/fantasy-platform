"""The Docket pick-service rules ledger (T7).

Every binding sheet rule from the 2026-08-11 design SSoT gets a lock here:
the line-snapshot parity contract (models.py's deferred write-path lock),
one-side-per-market, slot mechanics (gaps are real), the headliner rules
including the move-the-double exploit, strict deadline and kickoff
boundaries (driven through the DOCKET_FAKE_NOW seam against week rows built
by the real CT->UTC math), and integer-tenths tiebreaker parsing (D20).
"""
from datetime import datetime

import pytest

from extensions import db
from games.docket.models import DocketPick
from games.docket.services import picks as picks_service
from games.docket.services.picks import PickError
from tests._docket_fixtures import (
    IN_WEEK1,
    WEEK1_DEADLINE_UTC,
    at,
    make_game,
    make_user,
    make_week,
)

# Kickoffs (naive UTC): Thursday night CT, Saturday evening CT (after the
# deadline), and the Big Noon instant (kickoff == deadline).
KICK_THU = datetime(2026, 9, 4, 0, 15)
KICK_SAT = datetime(2026, 9, 5, 23, 30)


@pytest.fixture()
def week(app):
    return make_week(1)


@pytest.fixture()
def user(app):
    u = make_user('picker')
    db.session.commit()
    return u


def _pick(user, week, game, market='spread', side='home', backup=False):
    return picks_service.set_pick(
        user.id, week, game.id, market, side, backup=backup)


# ── Line-snapshot parity (the models.py write-path lock) ─────────────────

def test_spread_pick_snapshots_canonical_home_line_and_book(
        monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT, home_spread=-6.5,
                     spread_book='draftkings')
    pick = _pick(user, week, game, 'spread', 'away')
    # Canonical market value: home perspective regardless of picked side.
    assert pick.line_value == -6.5
    assert pick.book == 'draftkings'
    assert pick.line_value == game.home_spread
    assert pick.book == game.spread_book


def test_total_pick_snapshots_total_and_book(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT, total=47.5, total_book='fanduel')
    pick = _pick(user, week, game, 'total', 'under')
    assert pick.line_value == 47.5
    assert pick.book == 'fanduel'


def test_side_flip_does_not_resnapshot(monkeypatch, week, user):
    """The pick's frozen number survives a side flip even if the game row
    were to change (T9's audited line correction re-snapshots explicitly)."""
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT, home_spread=-3.5)
    pick = _pick(user, week, game, 'spread', 'home')
    original_slot = pick.slot
    game.home_spread = -9.5  # simulate drift the flip must NOT absorb
    db.session.flush()
    flipped = picks_service.set_pick(
        user.id, week, game.id, 'spread', 'away')
    assert flipped.id == pick.id
    assert flipped.line_value == -3.5
    assert flipped.slot == original_slot
    assert DocketPick.query.count() == 1


# ── One side per market ──────────────────────────────────────────────────

def test_same_side_reset_is_idempotent(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    p1 = _pick(user, week, game, 'spread', 'home')
    p2 = _pick(user, week, game, 'spread', 'home')
    assert p1.id == p2.id
    assert DocketPick.query.count() == 1


def test_spread_and_total_on_same_game_are_two_picks(
        monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    p1 = _pick(user, week, game, 'spread', 'home')
    p2 = _pick(user, week, game, 'total', 'over')
    assert p1.id != p2.id
    assert {p1.slot, p2.slot} == {1, 2}


def test_opposite_side_moves_pick_in_place(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, game, 'total', 'over')
    flipped = _pick(user, week, game, 'total', 'under')
    assert flipped.side == 'under'
    assert DocketPick.query.count() == 1


# ── Slot mechanics ───────────────────────────────────────────────────────

def test_sequential_adds_fill_slots_ascending(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(3)]
    slots = [_pick(user, week, g).slot for g in games]
    assert slots == [1, 2, 3]


def test_remove_leaves_gap_and_next_add_fills_it(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(4)]
    for g in games[:3]:
        _pick(user, week, g)
    picks_service.remove_pick(user.id, week, games[1].id, 'spread')
    remaining = {p.slot for p in DocketPick.query.all()}
    assert remaining == {1, 3}  # no renumbering: the gap is real
    refill = _pick(user, week, games[3])
    assert refill.slot == 2


def test_ninth_pick_without_backup_flag_is_sheet_full(
        monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(9)]
    for g in games[:8]:
        _pick(user, week, g)
    with pytest.raises(PickError) as err:
        _pick(user, week, games[8])
    assert err.value.code == 'sheet_full'


def test_backup_flag_files_slot_nine(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(9)]
    for g in games[:8]:
        _pick(user, week, g)
    backup = _pick(user, week, games[8], backup=True)
    assert backup.slot == 9


def test_backup_taken_is_refused(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    g1 = make_game(week, kickoff=KICK_SAT)
    g2 = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, g1, backup=True)
    with pytest.raises(PickError) as err:
        _pick(user, week, g2, backup=True)
    assert err.value.code == 'backup_taken'


def test_backup_allowed_before_eight_primaries(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    backup = _pick(user, week, game, backup=True)
    assert backup.slot == 9
    assert DocketPick.query.count() == 1


def test_backup_on_held_market_flips_side_in_place(monkeypatch, week, user):
    """One side per market binds the backup too: a backup request on a
    market already held flips the held pick (its slot is settled); it never
    creates a second row on the market."""
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    held = _pick(user, week, game, 'spread', 'home')
    result = _pick(user, week, game, 'spread', 'away', backup=True)
    assert result.id == held.id
    assert result.slot == held.slot
    assert result.side == 'away'
    assert DocketPick.query.count() == 1


# ── Deadline boundary (strictly before Sat 11:00:00 CT) ─────────────────

def test_mutations_allowed_at_deadline_minus_one_second(
        monkeypatch, week, user):
    at(monkeypatch, '2026-09-05T15:59:59')  # 10:59:59 CT
    game = make_game(week, kickoff=KICK_SAT)
    assert _pick(user, week, game).slot == 1


def test_mutations_refused_at_exactly_the_deadline(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, game)
    at(monkeypatch, WEEK1_DEADLINE_UTC.isoformat())  # 11:00:00.000 is late
    for call in (
        lambda: _pick(user, week, game, 'total', 'over'),
        lambda: picks_service.remove_pick(user.id, week, game.id, 'spread'),
        lambda: picks_service.set_best(user.id, week, game.id, 'spread'),
        lambda: picks_service.set_tiebreaker(user.id, week, '51.5'),
    ):
        with pytest.raises(PickError) as err:
            call()
        assert err.value.code == 'deadline_passed'


def test_no_active_week_is_refused(monkeypatch, app, user):
    at(monkeypatch, IN_WEEK1)
    with pytest.raises(PickError) as err:
        picks_service.set_pick(user.id, None, 1, 'spread', 'home')
    assert err.value.code == 'no_active_week'


# ── Kickoff locks (t >= kickoff, live column) ────────────────────────────

def test_pick_refused_at_exact_kickoff(monkeypatch, week, user):
    game = make_game(week, kickoff=KICK_THU)
    at(monkeypatch, KICK_THU.isoformat())
    with pytest.raises(PickError) as err:
        _pick(user, week, game)
    assert err.value.code == 'game_locked'


def test_pick_allowed_one_second_before_kickoff(monkeypatch, week, user):
    game = make_game(week, kickoff=KICK_THU)
    at(monkeypatch, '2026-09-04T00:14:59')
    assert _pick(user, week, game).slot == 1


def test_held_pick_frozen_after_kickoff(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_THU)
    _pick(user, week, game, 'spread', 'home')
    at(monkeypatch, '2026-09-04T01:00:00')
    with pytest.raises(PickError) as err:
        picks_service.remove_pick(user.id, week, game.id, 'spread')
    assert err.value.code == 'game_locked'
    with pytest.raises(PickError) as err:
        _pick(user, week, game, 'spread', 'away')  # side flip is a change
    assert err.value.code == 'game_locked'


def test_other_games_unaffected_by_one_kickoff(monkeypatch, week, user):
    thu = make_game(week, kickoff=KICK_THU)
    sat = make_game(week, kickoff=KICK_SAT)
    at(monkeypatch, IN_WEEK1)
    _pick(user, week, thu)
    at(monkeypatch, '2026-09-04T01:00:00')  # Thursday game underway
    assert _pick(user, week, sat).slot == 2


def test_big_noon_agrees_with_the_deadline(monkeypatch, week, user):
    """kickoff == deadline: pickable at 10:59:59, refused at 11:00:00 with
    no special-case code (the deadline and the lock coincide)."""
    game = make_game(week, kickoff=WEEK1_DEADLINE_UTC)
    at(monkeypatch, '2026-09-05T15:59:59')
    pick = _pick(user, week, game)
    assert pick.slot == 1
    at(monkeypatch, WEEK1_DEADLINE_UTC.isoformat())
    with pytest.raises(PickError):
        _pick(user, week, game, 'total', 'over')


# ── Markets require a frozen line ────────────────────────────────────────

def test_market_without_line_is_no_line(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT, home_spread=None)
    with pytest.raises(PickError) as err:
        _pick(user, week, game, 'spread', 'home')
    assert err.value.code == 'no_line'
    assert _pick(user, week, game, 'total', 'over').slot == 1


def test_line_without_book_is_no_line(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    game.total_book = None
    db.session.flush()
    with pytest.raises(PickError) as err:
        _pick(user, week, game, 'total', 'over')
    assert err.value.code == 'no_line'


def test_unknown_market_and_side_are_invalid(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    with pytest.raises(PickError) as err:
        _pick(user, week, game, 'moneyline', 'home')
    assert err.value.status == 400
    with pytest.raises(PickError) as err:
        _pick(user, week, game, 'spread', 'over')  # side/market mismatch
    assert err.value.status == 400


def test_game_from_another_week_is_invalid(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    week2 = make_week(2)
    foreign = make_game(week2, kickoff=datetime(2026, 9, 12, 23, 30))
    with pytest.raises(PickError) as err:
        _pick(user, week, foreign)
    assert err.value.status == 400


# ── The headliner (best pick) ────────────────────────────────────────────

def test_set_and_move_headliner_pre_kickoff(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    g1 = make_game(week, kickoff=KICK_SAT)
    g2 = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, g1)
    _pick(user, week, g2)
    best = picks_service.set_best(user.id, week, g1.id, 'spread')
    assert best.is_best is True
    moved = picks_service.set_best(user.id, week, g2.id, 'spread')
    assert moved.is_best is True
    assert DocketPick.query.filter(
        DocketPick.is_best.is_(True)).count() == 1


def test_headliner_refused_on_backup_slot(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, game, backup=True)
    with pytest.raises(PickError) as err:
        picks_service.set_best(user.id, week, game.id, 'spread')
    assert err.value.code == 'best_on_backup'


def test_headliner_cannot_move_onto_kicked_off_market(
        monkeypatch, week, user):
    """The exploit lock: no moving the double onto Thursday's winner."""
    thu = make_game(week, kickoff=KICK_THU)
    sat = make_game(week, kickoff=KICK_SAT)
    at(monkeypatch, IN_WEEK1)
    _pick(user, week, thu)
    _pick(user, week, sat)
    picks_service.set_best(user.id, week, sat.id, 'spread')
    at(monkeypatch, '2026-09-04T01:00:00')  # Thursday underway
    with pytest.raises(PickError) as err:
        picks_service.set_best(user.id, week, thu.id, 'spread')
    assert err.value.code == 'game_locked'


def test_headliner_frozen_once_its_own_game_kicks_off(
        monkeypatch, week, user):
    """The designation locks with its pick at that game's kickoff."""
    thu = make_game(week, kickoff=KICK_THU)
    sat = make_game(week, kickoff=KICK_SAT)
    at(monkeypatch, IN_WEEK1)
    _pick(user, week, thu)
    _pick(user, week, sat)
    picks_service.set_best(user.id, week, thu.id, 'spread')
    at(monkeypatch, '2026-09-04T01:00:00')
    with pytest.raises(PickError) as err:
        picks_service.set_best(user.id, week, sat.id, 'spread')
    assert err.value.code == 'best_locked'
    with pytest.raises(PickError) as err:
        picks_service.clear_best(user.id, week)
    assert err.value.code == 'best_locked'


def test_clear_headliner_pre_kickoff_and_idempotent(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    _pick(user, week, game)
    picks_service.set_best(user.id, week, game.id, 'spread')
    picks_service.clear_best(user.id, week)
    assert DocketPick.query.filter(
        DocketPick.is_best.is_(True)).count() == 0
    picks_service.clear_best(user.id, week)  # no designation: no-op


def test_headliner_requires_a_held_pick(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    with pytest.raises(PickError) as err:
        picks_service.set_best(user.id, week, game.id, 'spread')
    assert err.value.status == 400


# ── The number (tiebreaker, integer tenths — D20) ────────────────────────

@pytest.mark.parametrize('raw,tenths', [
    ('51.5', 515),
    ('51', 510),
    ('0.5', 5),
    (' 44.0 ', 440),
])
def test_prediction_parses_to_integer_tenths(raw, tenths):
    assert picks_service.parse_prediction_tenths(raw) == tenths


@pytest.mark.parametrize('raw', [
    '51.55', '.5', '51.', '-3', 'abc', '5 1', '1e3', '9999.1',
])
def test_prediction_rejects_non_tenths(raw):
    with pytest.raises(PickError) as err:
        picks_service.parse_prediction_tenths(raw)
    assert err.value.status == 400


def _designate(week, game):
    week.tiebreaker_game_id = game.id
    db.session.flush()


def test_prediction_upserts_and_empty_clears(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    _designate(week, game)
    row = picks_service.set_tiebreaker(user.id, week, '51.5')
    assert row.prediction_tenths == 515
    row = picks_service.set_tiebreaker(user.id, week, '48')
    assert row.prediction_tenths == 480
    assert picks_service.set_tiebreaker(user.id, week, '  ') is None
    from games.docket.models import DocketTiebreakerPrediction
    assert DocketTiebreakerPrediction.query.count() == 0


def test_prediction_locks_at_designated_kickoff_before_deadline(
        monkeypatch, week, user):
    thu = make_game(week, kickoff=KICK_THU)
    _designate(week, thu)
    at(monkeypatch, '2026-09-04T01:00:00')  # designated game underway
    with pytest.raises(PickError) as err:
        picks_service.set_tiebreaker(user.id, week, '51.5')
    assert err.value.code == 'prediction_locked'


def test_prediction_requires_a_designated_game(monkeypatch, week, user):
    at(monkeypatch, IN_WEEK1)
    with pytest.raises(PickError) as err:
        picks_service.set_tiebreaker(user.id, week, '51.5')
    assert err.value.code == 'invalid'


# ── Race handling ────────────────────────────────────────────────────────

def test_duplicate_submit_race_returns_existing_row(monkeypatch, week, user):
    """A double submit that loses the unique-constraint race is reported as
    success when the surviving row matches the request (CFB pattern)."""
    at(monkeypatch, IN_WEEK1)
    game = make_game(week, kickoff=KICK_SAT)
    winner = _pick(user, week, game, 'spread', 'home')
    real_lookup = picks_service._market_row
    calls = {'n': 0}

    def racing_lookup(*args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            return None  # the losing request saw no row pre-insert
        return real_lookup(*args, **kwargs)

    monkeypatch.setattr(picks_service, '_market_row', racing_lookup)
    result = picks_service.set_pick(
        user.id, week, game.id, 'spread', 'home')
    assert result.id == winner.id
    assert DocketPick.query.count() == 1


# ── Sheet state assembly ─────────────────────────────────────────────────

def test_sheet_state_reports_progress_and_locks(monkeypatch, week, user):
    thu = make_game(week, kickoff=KICK_THU)
    sat = make_game(week, kickoff=KICK_SAT)
    at(monkeypatch, IN_WEEK1)
    _pick(user, week, thu)
    _pick(user, week, sat, 'total', 'over')
    picks_service.set_best(user.id, week, sat.id, 'total')
    _designate(week, sat)
    picks_service.set_tiebreaker(user.id, week, '51.5')
    at(monkeypatch, '2026-09-04T01:00:00')  # Thursday kicked off
    state = picks_service.sheet_state(user.id, week)
    assert state['scoring_count'] == 2
    assert state['backup'] is None
    assert state['best']['game_id'] == sat.id
    assert state['prediction'] == '51.5'
    assert state['locked_game_ids'] == [thu.id]
    assert state['deadline_passed'] is False
    locked_flags = {p['game_id']: p['locked'] for p in state['picks']}
    assert locked_flags == {thu.id: True, sat.id: False}
