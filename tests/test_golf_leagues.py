"""The Pay Sheet's two leagues (ADR-075): the spec lock for the whole change.

Golf is one game with two leagues inside it, Handicap (the house league) and
Pollyanna. Each league is a row in ``golf_league`` carrying its own entry fee
and penalty; every enrollment, pick and golfer usage belongs to exactly one.
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.enrollment import admin_enroll, enrollments_for, get_enrollment
from games.golf.services.leagues import (
    house_league,
    league_by_slug,
    leagues,
    seed_leagues,
)
from models.user import User


def _user(username):
    user = User(username=username, email=f'{username}@example.com')
    user.set_password('x')
    db.session.add(user)
    db.session.commit()
    return user


def test_seed_leagues_is_idempotent_and_ordered(app):
    seed_leagues()
    seed_leagues()

    assert [league.slug for league in leagues()] == ['handicap', 'pollyanna']
    assert [league.name for league in leagues()] == ['Handicap Pay Sheet', 'Pollyanna Pay Sheet']
    assert house_league().slug == 'handicap'
    assert league_by_slug('pollyanna').ordinal == 2
    assert league_by_slug('nope') is None
    for league in leagues():
        assert league.entry_fee == 25
        assert league.penalty_per_incident == 15


def test_the_same_member_holds_a_line_in_both_leagues(app, golf_leagues):
    brad = _user('two_sheets')
    db.session.add_all([
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id, season_year=2027),
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['pollyanna'].id, season_year=2027),
    ])
    db.session.commit()

    db.session.add(GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id,
                                  season_year=2027))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


SEASON = 2027


def _event(name, is_major=False):
    now = datetime.now(UTC)
    event = GolfTournament(
        api_tourn_id=f'T-{name}', name=name, season_year=SEASON,
        start_date=now - timedelta(days=4), end_date=now - timedelta(days=1),
        pick_deadline=now - timedelta(days=4), purse=10_000_000,
        is_major=is_major, status='complete',
    )
    db.session.add(event)
    db.session.commit()
    return event


def _golfer(api_id, last):
    player = GolfPlayer(api_player_id=api_id, first_name='Pat', last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _pick(user, league, event, primary, backup):
    pick = GolfPick(user_id=user.id, league_id=league.id, tournament_id=event.id,
                    primary_player_id=primary.id, backup_player_id=backup.id)
    db.session.add(pick)
    db.session.commit()
    return pick


def _result(event, player, status='complete', earnings=100):
    db.session.add(GolfTournamentResult(
        tournament_id=event.id, player_id=player.id, status=status,
        rounds_completed=4, earnings=earnings, final_position='1'))
    db.session.commit()


def test_spending_a_golfer_in_one_league_leaves_him_unspent_in_the_other(app, golf_leagues):
    brad = _user('spender')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    first, second = _event('First Open'), _event('Second Open')
    scheffler, backup = _golfer('S1', 'Scheffler'), _golfer('S2', 'Backup')
    for event in (first, second):
        for player in (scheffler, backup):
            db.session.add(GolfTournamentField(tournament_id=event.id, player_id=player.id))
        _result(event, scheffler)
        _result(event, backup)
    db.session.commit()

    spent = _pick(brad, handicap, first, scheffler, backup)
    assert spent.resolve_pick() is True
    db.session.commit()

    other = _pick(brad, pollyanna, second, scheffler, backup)
    assert other.validate_availability(SEASON) == []
    same_line = GolfPick(user_id=brad.id, league_id=handicap.id, tournament_id=second.id,
                         primary_player_id=scheffler.id, backup_player_id=backup.id)
    assert any('primary' in e for e in same_line.validate_availability(SEASON))

    assert other.resolve_pick() is True
    db.session.commit()
    rows = GolfSeasonPlayerUsage.query.filter_by(user_id=brad.id, player_id=scheffler.id).all()
    assert sorted(r.league_id for r in rows) == sorted([handicap.id, pollyanna.id])


def test_clear_resolution_deletes_only_this_leagues_usage(app, golf_leagues):
    brad = _user('clearer')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    event = _event('Clear Open')
    scheffler, backup = _golfer('C1', 'Scheffler'), _golfer('C2', 'Backup')
    _result(event, scheffler)
    _result(event, backup)
    h_pick = _pick(brad, handicap, event, scheffler, backup)
    p_pick = _pick(brad, pollyanna, event, scheffler, backup)
    assert h_pick.resolve_pick() and p_pick.resolve_pick()
    db.session.commit()

    h_pick.clear_resolution(SEASON)
    db.session.commit()

    rows = GolfSeasonPlayerUsage.query.filter_by(user_id=brad.id, player_id=scheffler.id).all()
    assert [r.league_id for r in rows] == [pollyanna.id]


def test_total_points_and_penalty_are_per_line(app, golf_leagues):
    brad = _user('liner')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    pollyanna.penalty_per_incident = 20
    db.session.commit()
    major = _event('The Major', is_major=True)
    a, b, c, d = (_golfer(f'L{i}', f'Last{i}') for i in range(4))
    _result(major, a, status='cut', earnings=0)
    _result(major, b, status='complete', earnings=200)
    _result(major, c, status='cut', earnings=0)
    _result(major, d, status='complete', earnings=50)
    h_pick = _pick(brad, handicap, major, a, b)
    p_pick = _pick(brad, pollyanna, major, c, d)
    assert h_pick.resolve_pick() and p_pick.resolve_pick()
    assert h_pick.penalty_triggered and p_pick.penalty_triggered
    minor = _event('The Minor')
    e, f = _golfer('L8', 'Last8'), _golfer('L9', 'Last9')
    _result(minor, e, earnings=500)
    _result(minor, f, earnings=40)
    h_minor = _pick(brad, handicap, minor, e, f)
    p_minor = _pick(brad, pollyanna, minor, f, e)
    assert h_minor.resolve_pick() and p_minor.resolve_pick()
    h_line = GolfEnrollment(user_id=brad.id, league_id=handicap.id, season_year=SEASON)
    p_line = GolfEnrollment(user_id=brad.id, league_id=pollyanna.id, season_year=SEASON)
    db.session.add_all([h_line, p_line])
    db.session.commit()

    h_line.calculate_total_points()
    p_line.calculate_total_points()
    assert (h_line.total_points, p_line.total_points) == (500, 40)
    assert h_line.penalty_owed() == 15
    assert p_line.penalty_owed() == 20
    assert len(h_line.get_used_player_ids()) == 2
    assert len(p_line.get_used_player_ids()) == 2


def test_get_enrollment_without_a_league_is_the_house_line_first(app, golf_leagues):
    brad = _user('registry')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    season = app.config['SEASON_YEAR']
    assert get_enrollment(brad.id) is None
    p_line = GolfEnrollment(user_id=brad.id, league_id=pollyanna.id, season_year=season)
    db.session.add(p_line)
    db.session.commit()
    assert get_enrollment(brad.id) == p_line
    h_line = GolfEnrollment(user_id=brad.id, league_id=handicap.id, season_year=season)
    db.session.add(h_line)
    db.session.commit()

    assert get_enrollment(brad.id) == h_line
    assert get_enrollment(brad.id, pollyanna) == p_line
    assert [e.league_id for e in enrollments_for(brad.id)] == [handicap.id, pollyanna.id]


def test_admin_enroll_seats_the_house_league(app, golf_leagues):
    brad = _user('seated')
    seated = admin_enroll(brad.id)
    assert seated.league_id == golf_leagues['handicap'].id
    assert admin_enroll(brad.id) == seated

    other = admin_enroll(brad.id, golf_leagues['pollyanna'])
    assert other.league_id == golf_leagues['pollyanna'].id
    assert admin_enroll(brad.id, golf_leagues['pollyanna']) == other
    assert GolfEnrollment.query.filter_by(user_id=brad.id).count() == 2
