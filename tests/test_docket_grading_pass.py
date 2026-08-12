"""ORM→snapshot adapter + persisted grading pass (D9-eng thin adapter,
D14-eng docket_week_result upsert).

The pure engine never sees the ORM; this seam is where rows become
snapshots (zero datetime conversion — both sides are naive UTC) and where
WeekGrades become docket_week_result rows, idempotently.
"""
from datetime import datetime

import pytest
from sqlalchemy import select

DEADLINE = datetime(2026, 9, 5, 16, 0)
KICK = datetime(2026, 9, 5, 18, 0)


def _seed_week(db, *, stamp_frozen_kickoff=True):
    from games.docket.models import DocketGame, DocketWeek

    week = DocketWeek(week_number=1,
                      start_at=datetime(2026, 9, 1, 11, 0),
                      end_at=datetime(2026, 9, 8, 11, 0),
                      deadline_at=DEADLINE)
    db.session.add(week)
    db.session.flush()
    games = []
    for i in range(1, 10):
        game = DocketGame(
            week_id=week.id,
            sport='americanfootball_ncaaf',
            api_event_id=f'e-{i}',
            home_team=f'H{i}', away_team=f'A{i}',
            kickoff=KICK,
            kickoff_at_deadline=KICK if stamp_frozen_kickoff else None,
            home_spread=-7.0, spread_book='draftkings',
            spread_locked_at=datetime(2026, 9, 1, 11, 5),
            total_points=50.0, total_book='draftkings',
            total_locked_at=datetime(2026, 9, 1, 11, 5),
            home_score=30, away_score=20, is_final=True,
        )
        db.session.add(game)
        games.append(game)
    week.tiebreaker_game_id = None
    db.session.flush()
    week.tiebreaker_game_id = games[0].id
    db.session.commit()
    return week, games


def _seed_user(db, name='alice'):
    from models import User

    user = User(username=name, email=f'{name}@test.com')
    user.password_hash = 'x'
    db.session.add(user)
    db.session.commit()
    return user


def _seed_full_picks(db, user, week, games, *, best_slot=1):
    from games.docket.models import DocketPick

    for slot in range(1, 9):
        db.session.add(DocketPick(
            user_id=user.id, week_id=week.id, game_id=games[slot - 1].id,
            market='spread', side='home', slot=slot,
            is_best=(slot == best_slot), line_value=-7.0,
            book='draftkings'))
    db.session.commit()


def test_build_week_snapshot_maps_rows_verbatim(app):
    from extensions import db
    from games.docket.services.grading_pass import build_week_snapshot

    week, games = _seed_week(db)
    snapshot = build_week_snapshot(week)
    assert snapshot.week_number == 1
    assert snapshot.deadline_at == DEADLINE  # naive in, naive out — no tz math
    assert len(snapshot.games) == 9
    game = snapshot.game('e-1')
    assert game.kickoff_at_deadline == KICK
    assert game.home_spread == -7.0
    assert game.total == 50.0
    assert (game.home_score, game.away_score) == (30, 20)
    assert game.no_contest is False
    assert snapshot.tiebreaker_event_id == 'e-1'


def test_build_week_snapshot_requires_frozen_kickoffs(app):
    """Grading before the deadline pass stamped kickoff_at_deadline is a
    sequencing bug (F6) — refused loudly, never silently substituted with
    the live kickoff."""
    from extensions import db
    from games.docket.services.grading_pass import build_week_snapshot

    week, _ = _seed_week(db, stamp_frozen_kickoff=False)
    with pytest.raises(ValueError, match='kickoff_at_deadline'):
        build_week_snapshot(week)


def test_build_week_snapshot_requires_designation(app):
    from extensions import db
    from games.docket.models import DocketGame, DocketWeek

    week = DocketWeek(week_number=2,
                      start_at=datetime(2026, 9, 8, 11, 0),
                      end_at=datetime(2026, 9, 15, 11, 0),
                      deadline_at=datetime(2026, 9, 12, 16, 0))
    db.session.add(week)
    db.session.flush()
    db.session.add(DocketGame(
        week_id=week.id, sport='americanfootball_nfl', api_event_id='x-1',
        home_team='H', away_team='A', kickoff=KICK,
        kickoff_at_deadline=KICK))
    db.session.commit()

    from games.docket.services.grading_pass import build_week_snapshot
    with pytest.raises(ValueError, match='tiebreaker'):
        build_week_snapshot(week)


def test_build_player_inputs_maps_picks_and_predictions(app):
    from extensions import db
    from games.docket.models import DocketPick, DocketTiebreakerPrediction
    from games.docket.services.grading_pass import build_player_inputs

    week, games = _seed_week(db)
    user = _seed_user(db)
    _seed_full_picks(db, user, week, games, best_slot=3)
    db.session.add(DocketPick(
        user_id=user.id, week_id=week.id, game_id=games[8].id,
        market='total', side='over', slot=9, is_autopick=False,
        line_value=50.0, book='fanduel'))
    db.session.add(DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=515))
    db.session.commit()

    players = build_player_inputs(week)
    assert len(players) == 1
    player = players[0]
    assert player.player_id == str(user.id)
    assert player.tiebreaker_tenths == 515
    assert len(player.picks) == 9
    best = [p for p in player.picks if p.is_best]
    assert [p.slot for p in best] == [3]
    backup = next(p for p in player.picks if p.slot == 9)
    assert str(backup.market) == 'total'
    assert str(backup.side) == 'over'


def test_build_player_inputs_includes_prediction_only_players(app):
    """A player who submitted only a tiebreaker prediction still grades
    (full autopick per D5-session) — input presence, not pick presence,
    defines the week's graded population."""
    from extensions import db
    from games.docket.models import DocketTiebreakerPrediction
    from games.docket.services.grading_pass import build_player_inputs

    week, _ = _seed_week(db)
    user = _seed_user(db, 'bob')
    db.session.add(DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=470))
    db.session.commit()

    players = build_player_inputs(week)
    assert [p.player_id for p in players] == [str(user.id)]
    assert players[0].picks == ()
    assert players[0].tiebreaker_tenths == 470


def test_run_grading_pass_upserts_week_results_idempotently(app):
    from extensions import db
    from games.docket.models import DocketWeekResult
    from games.docket.services.grading_pass import run_grading_pass

    week, games = _seed_week(db)
    alice = _seed_user(db, 'alice')
    bob = _seed_user(db, 'bob')
    _seed_full_picks(db, alice, week, games)
    _seed_full_picks(db, bob, week, games)

    summary = run_grading_pass(week.id)
    assert summary['graded'] == 2

    rows = db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id)).all()
    assert len(rows) == 2
    by_user = {r.user_id: r for r in rows}
    # all 8 home picks win at -7 with 30-20; best doubles: 9.0 / 8 wins
    assert by_user[alice.id].points == 9.0
    assert by_user[alice.id].wins == 8
    # no prediction submitted -> default = designated locked total 50.0;
    # actual combined 50 -> zero error
    assert by_user[alice.id].error_tenths == 0
    assert by_user[alice.id].graded_at is not None
    first_graded_at = by_user[alice.id].graded_at

    # re-run: same two rows, updated in place (D14-eng idempotent recalc)
    summary = run_grading_pass(week.id)
    assert summary['graded'] == 2
    rows = db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id)).all()
    assert len(rows) == 2
    assert all(r.points == 9.0 for r in rows)
    assert first_graded_at is not None


def test_run_grading_pass_accepts_explicit_population(app):
    """The roster is a parameter: once enrollment exists, the caller passes
    every enrolled user id and no-input players get the full-autopick
    treatment instead of being skipped."""
    from extensions import db
    from games.docket.models import DocketWeekResult
    from games.docket.services.grading_pass import run_grading_pass

    week, games = _seed_week(db)
    alice = _seed_user(db, 'alice')
    _seed_full_picks(db, alice, week, games)
    ghost = _seed_user(db, 'ghost')  # enrolled-no-input stand-in

    run_grading_pass(week.id, user_ids=[alice.id, ghost.id])
    rows = {r.user_id: r for r in db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id)).all()}
    assert set(rows) == {alice.id, ghost.id}
    # ghost got the full D5 autopick week: deterministic, non-zero points
    assert rows[ghost.id].points > 0
    assert rows[ghost.id].error_tenths == 0  # default prediction, actual 50
