"""The deadline pass: the D7 kickoff freeze + the D5 autopick package.

Locks the ordering contract (stamp before autopick), the freeze semantics
(only-if-null, so a kickoff that moves after the deadline can never shift
already-graded substitution order), the line-snapshot parity that makes an
autopick row indistinguishable from a hand-made one, the "block autopick but
still freeze" behavior when no tiebreaker is designated, and the invariant
that persisting autopicks changes no grade — the engine completes the same
inputs itself.
"""
from datetime import datetime

import pytest
from sqlalchemy import select

from extensions import db
from games.docket.models import (
    DocketPick,
    DocketTiebreakerPrediction,
)
from tests._docket_fixtures import (
    WEEK1_DEADLINE_UTC,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

AFTER_DEADLINE = '2026-09-05T16:30:00'
BEFORE_DEADLINE = '2026-09-05T15:59:00'
# Every seeded kickoff sits after the deadline, so the whole docket is in
# the autopick pool unless a test says otherwise.
KICK = datetime(2026, 9, 5, 18, 0)


def _seed(week_games=9, *, final=True):
    """A designated week whose games differ in spread and total, so every
    autopick ordering (descending total, descending |spread|) is unambiguous.
    """
    week = make_week(1)
    games = [
        make_game(week, kickoff=KICK,
                  home=f'Home {i}', away=f'Away {i}',
                  home_spread=-(3.5 + i), total=40.5 + i)
        for i in range(week_games)
    ]
    if final:
        for game in games:
            game.home_score = 31
            game.away_score = 17
            game.is_final = True
    week.tiebreaker_game_id = games[0].id
    db.session.flush()
    return week, games


def _hold(user, week, game, market, side, slot, *, is_best=False):
    """A pick the player made themselves, snapshotting the locked line the
    way games/docket/services/picks.set_pick does."""
    value, book = ((game.home_spread, game.spread_book) if market == 'spread'
                   else (game.total_points, game.total_book))
    pick = DocketPick(user_id=user.id, week_id=week.id, game_id=game.id,
                      market=market, side=side, slot=slot, is_best=is_best,
                      is_autopick=False, line_value=value, book=book)
    db.session.add(pick)
    db.session.flush()
    return pick


def _picks(user, week):
    return db.session.scalars(
        select(DocketPick).filter_by(user_id=user.id, week_id=week.id)
        .order_by(DocketPick.slot)).all()


def test_stamp_freezes_the_live_kickoff_and_never_re_freezes(app, monkeypatch):
    """Only-if-null IS the freeze: a kickoff that moves after the deadline
    must not shift the D6 substitution ordering under a graded week."""
    from games.docket.services.deadline_pass import stamp_kickoffs

    week, games = _seed(week_games=2)
    db.session.commit()

    assert stamp_kickoffs(week)['stamped'] == 2
    assert all(g.kickoff_at_deadline == KICK for g in games)

    moved = datetime(2026, 9, 6, 23, 0)
    games[0].kickoff = moved
    db.session.commit()
    assert stamp_kickoffs(week)['stamped'] == 0, 'a re-run must stamp nothing'
    assert games[0].kickoff_at_deadline == KICK
    assert games[0].kickoff == moved


def test_a_game_imported_after_the_deadline_is_stamped_and_flagged(app):
    """It was never on the docket the players saw, but the engine requires
    every game stamped — so stamp it and say so."""
    from games.docket.services.deadline_pass import stamp_kickoffs

    week, _games = _seed(week_games=1)
    latecomer = make_game(week, kickoff=KICK, home='Late', away='Arrival')
    latecomer.created_at = datetime(2026, 9, 5, 20, 0)  # after the deadline
    db.session.commit()

    result = stamp_kickoffs(week)
    assert result['stamped'] == 2
    assert result['stamped_late_arrivals'] == 1
    assert latecomer.kickoff_at_deadline == KICK


def test_pass_refuses_while_the_sheet_is_still_open(app, monkeypatch):
    from games.docket.services.deadline_pass import (
        DeadlinePassError,
        run_deadline_pass,
    )

    week, games = _seed()
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', BEFORE_DEADLINE)

    with pytest.raises(DeadlinePassError, match='still open'):
        run_deadline_pass(1)
    assert all(g.kickoff_at_deadline is None for g in games), \
        'a refused pass must not freeze anything'

    # --force is the development escape, not a different code path.
    run_deadline_pass(1, force=True)
    assert all(g.kickoff_at_deadline == KICK for g in games)


def test_autopick_fills_to_eight_slots_with_line_snapshot_parity(app,
                                                                 monkeypatch):
    """An autopick row is indistinguishable from a hand-made one except for
    is_autopick: same slots, same one-side-per-market rule, and line_value /
    book copied from the game's locked market (D7-eng), never invented."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, games = _seed()
    user = make_user('nopicks')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    summary = run_deadline_pass(1)
    assert summary['picks_added'] == 8
    assert summary['line_gaps'] == 0

    picks = _picks(user, week)
    assert [p.slot for p in picks] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert all(p.is_autopick for p in picks)
    assert len({(p.game_id, p.market) for p in picks}) == 8
    for pick in picks:
        game = pick.game
        expected = ((game.home_spread, game.spread_book)
                    if pick.market == 'spread'
                    else (game.total_points, game.total_book))
        assert (pick.line_value, pick.book) == expected


def test_autopick_tops_up_around_held_picks_and_fills_slot_gaps(app,
                                                                monkeypatch):
    """Top-up never overwrites (D5): held picks keep their slots and their
    is_autopick=False, and the gap a withdrawal left is filled ascending."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, games = _seed()
    user = make_user('partial')
    make_enrollment(user)
    kept = _hold(user, week, games[0], 'spread', 'home', 1)
    _hold(user, week, games[1], 'total', 'under', 3)  # slot 2 is a gap
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    run_deadline_pass(1)

    picks = _picks(user, week)
    assert [p.slot for p in picks] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert not picks[0].is_autopick and not picks[2].is_autopick
    assert picks[1].is_autopick, 'the slot-2 gap is filled, not renumbered'
    assert kept.side == 'home' and kept.is_autopick is False
    # The player's own markets are never re-picked from the other side.
    assert sum(1 for p in picks
               if p.game_id == games[1].id and p.market == 'total') == 1


def test_autopick_designates_the_headliner_and_respects_an_existing_one(
        app, monkeypatch):
    """Auto-designation evaluates the FINAL 8-slot set (largest favorite
    first) and never moves a headliner the player already set."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, games = _seed()
    auto_user = make_user('auto')
    own_user = make_user('own')
    make_enrollment(auto_user)
    make_enrollment(own_user)
    own_best = _hold(own_user, week, games[0], 'total', 'over', 1,
                     is_best=True)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    run_deadline_pass(1)

    auto_best = [p for p in _picks(auto_user, week) if p.is_best]
    assert len(auto_best) == 1
    # The chain evaluates the FINAL set, and bucket exclusivity shapes it:
    # games[-1] has both the biggest total and the biggest spread, but the
    # interleave opens with the Over bucket, which claims that game — so the
    # largest favorite actually held is games[-2].
    assert auto_best[0].market == 'spread'
    assert auto_best[0].game_id == games[-2].id
    assert auto_best[0].side == 'home'

    own = [p for p in _picks(own_user, week) if p.is_best]
    assert [p.id for p in own] == [own_best.id], \
        'a player-set headliner is never moved'


def test_the_default_tiebreaker_prediction_is_never_materialized(
        app, monkeypatch):
    """D5/D20: the default is COMPUTED at grading so used_default_prediction
    survives into the grade — writing a row would erase that fact."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, _games = _seed()
    user = make_user('silent')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    run_deadline_pass(1)

    assert db.session.scalars(
        select(DocketTiebreakerPrediction).filter_by(week_id=week.id)
    ).all() == []


def test_a_second_pass_is_a_no_op(app, monkeypatch):
    from games.docket.services.deadline_pass import run_deadline_pass

    week, _games = _seed()
    user = make_user('twice')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    run_deadline_pass(1)
    first = [(p.slot, p.game_id, p.market, p.side, p.is_best)
             for p in _picks(user, week)]

    second = run_deadline_pass(1)
    assert second['picks_added'] == 0
    assert second['designations'] == 0
    assert [(p.slot, p.game_id, p.market, p.side, p.is_best)
            for p in _picks(user, week)] == first


def test_missing_designation_freezes_kickoffs_but_deals_no_picks(
        app, monkeypatch):
    """The ruled behavior: stamping is time-critical and designation-
    independent; autopick is a replayable pure function and can wait."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, games = _seed()
    week.tiebreaker_game_id = None
    user = make_user('waiting')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    summary = run_deadline_pass(1)

    assert summary['stamped'] == len(games)
    assert all(g.kickoff_at_deadline == KICK for g in games)
    assert summary['problems'], 'the refusal must be reported, not silent'
    assert 'no designated tiebreaker game' in summary['problems'][0]
    assert _picks(user, week) == []


def test_check_designation_flags_an_unsound_designation(app):
    """The full Grading Clarifications contract: locked whole-tenth total,
    kickoff at or after the deadline."""
    from games.docket.services.deadline_pass import check_designation

    week, games = _seed()
    assert check_designation(week) == []

    games[0].total_points = None
    assert any('no locked total' in p for p in check_designation(week))

    games[0].total_points = 51.25
    assert any('whole tenth' in p for p in check_designation(week))

    games[0].total_points = 51.5
    games[0].kickoff = WEEK1_DEADLINE_UTC.replace(hour=15)
    assert any('before the' in p for p in check_designation(week))


def test_check_designation_reads_the_frozen_kickoff_once_stamped(app):
    """Post-stamp — which is when the deadline pass calls it — the frozen
    column is the honest one. A designation whose LIVE kickoff moved late is
    still judged on the docket the players saw."""
    from games.docket.services.deadline_pass import check_designation

    week, games = _seed()
    games[0].kickoff_at_deadline = WEEK1_DEADLINE_UTC.replace(hour=15)
    games[0].kickoff = KICK  # the live column says "after the deadline"
    db.session.flush()

    assert any('before the' in p for p in check_designation(week))


def test_check_designation_flags_a_game_from_another_week(app):
    from games.docket.services.deadline_pass import check_designation

    week, _games = _seed()
    other = make_week(2)
    stray = make_game(other, kickoff=datetime(2026, 9, 12, 18, 0))
    week.tiebreaker_game_id = stray.id
    db.session.flush()

    assert any('belongs to another week' in p for p in check_designation(week))


def test_a_market_with_no_bookmaker_is_skipped_not_invented(app, monkeypatch):
    """D17 provenance is auditable or absent: a value locked without a book
    is unpostable (locked_line refuses it, exactly as the sheet does), so the
    slot stays empty rather than carrying a fabricated book."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, games = _seed(week_games=4)
    for game in games:
        game.spread_book = None  # every spread market loses provenance
    user = make_user('gappy')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    summary = run_deadline_pass(1)

    assert summary['line_gaps'] > 0
    written = _picks(user, week)
    assert all(p.market == 'total' for p in written)
    assert all(p.book == 'draftkings' for p in written)


def test_persisting_autopicks_changes_no_grade(app, monkeypatch):
    """THE invariant behind writing these rows at all: grade_week completes
    inputs itself, so the persisted sheet is transparency, not scoring. If
    these ever disagree, the deadline pass is writing something the engine
    would not have chosen."""
    from games.docket.services.deadline_pass import run_autopick, stamp_kickoffs
    from games.docket.services.enrollment import roster_user_ids
    from games.docket.services.grading.engine import grade_week
    from games.docket.services.grading_pass import (
        build_week_snapshot,
        player_inputs_for,
    )

    week, games = _seed()
    partial = make_user('partial')
    empty = make_user('empty')
    make_enrollment(partial)
    make_enrollment(empty)
    _hold(partial, week, games[2], 'spread', 'away', 1)
    _hold(partial, week, games[3], 'total', 'under', 2)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    stamp_kickoffs(week)
    roster = roster_user_ids()

    def _grade():
        return {
            p.player_id: (p.points, p.wins, p.error_tenths,
                          p.used_default_prediction)
            for p in grade_week(build_week_snapshot(week),
                                player_inputs_for(week, roster)).players
        }

    before = _grade()
    run_autopick(week, roster)
    assert _grade() == before


def test_the_roster_is_the_population_not_just_submitters(app, monkeypatch):
    """An enrolled player who touched nothing still gets dealt a sheet;
    a non-enrolled user never does."""
    from games.docket.services.deadline_pass import run_deadline_pass

    week, _games = _seed()
    enrolled = make_user('enrolled')
    bystander = make_user('bystander')
    make_enrollment(enrolled)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    summary = run_deadline_pass(1)

    assert summary['players'] == 1
    assert len(_picks(enrolled, week)) == 8
    assert _picks(bystander, week) == []
