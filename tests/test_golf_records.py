"""The Pay Sheet on the club's permanent record (ADR-068, Golf Phase U7).

``games/golf/services/records.py::season_finishes(season_year)`` is the
registry seam ``flask records close golf YEAR`` calls: the season's enrollees
ranked by the money on their line, in competition rank (ties share and gap),
the champion(s) at place 1. A season is closed once it has a schedule and
every event on it is banked (``results_finalized``); until then the seam
raises ``SeasonNotClosed`` and names what is still open. The import created a
real User for every 2026 member, so every row is linked and there is no link
map.
"""
from datetime import UTC, datetime, timedelta

import pytest

from extensions import db
from games.golf.models import GolfEnrollment, GolfTournament
from models.records import SeasonNotClosed, finishes_for
from models.user import User


def _user(username, display_name=None):
    u = User(username=username, email=f'{username}@test.com', display_name=display_name)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _line(user, season, total):
    e = GolfEnrollment(user_id=user.id, season_year=season, total_points=total)
    db.session.add(e)
    db.session.commit()
    return e


def _event(season, name, week, finalized=True):
    start = datetime(season, 1, 8, tzinfo=UTC) + timedelta(weeks=week - 1)
    t = GolfTournament(
        api_tourn_id=f'T{season}-{week}', name=name, season_year=season, week_number=week,
        start_date=start, end_date=start + timedelta(days=3),
        pick_deadline=start, purse=9_000_000,
        status='complete', results_finalized=finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _banked_season(season):
    _event(season, 'Sony Open in Hawaii', 1)
    _event(season, 'The American Express', 2)
    casey = _user('casey', display_name='Casey Champion')
    brock = _user('brock', display_name='Brock Second')
    dana = _user('dana', display_name='Dana Second')
    morgan = _user('morgan')
    _line(casey, season, 4_200_000)
    _line(dana, season, 750_000)
    _line(brock, season, 750_000)
    _line(morgan, season, 0)
    return casey, brock, dana, morgan


def test_a_banked_season_ranks_the_lines_with_shared_places(app):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    casey, brock, dana, morgan = _banked_season(season)

    drafts = season_finishes(season)

    assert [(d.place, d.name, d.user_id, d.detail) for d in drafts] == [
        (1, 'Casey Champion', casey.id, '$4,200,000'),
        (2, 'Brock Second', brock.id, '$750,000'),
        (2, 'Dana Second', dana.id, '$750,000'),
        (4, 'morgan', morgan.id, '$0'),
    ]
    assert [d.outcome for d in drafts] == ['champion', None, None, None]


def test_tied_leaders_are_both_champions(app):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    _event(season, 'Sony Open in Hawaii', 1)
    a, b = _user('a', display_name='Alex'), _user('b', display_name='Blake')
    _line(a, season, 1_000_000)
    _line(b, season, 1_000_000)
    drafts = season_finishes(season)
    assert [(d.place, d.outcome) for d in drafts] == [(1, 'champion'), (1, 'champion')]


def test_refuses_a_season_with_no_schedule(app):
    from games.golf.services.records import season_finishes
    with pytest.raises(SeasonNotClosed, match='no schedule'):
        season_finishes(2031)


def test_refuses_while_an_event_is_not_banked(app):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    _event(season, 'Sony Open in Hawaii', 1)
    _event(season, 'Masters Tournament', 15, finalized=False)
    _line(_user('casey'), season, 100)
    with pytest.raises(SeasonNotClosed, match='Masters Tournament'):
        season_finishes(season)


def test_a_past_season_closes_from_its_own_rows(app):
    """Like the Docket's seam and unlike Survivor's, the builder takes any
    year: 2026 closes from a box whose configured season is 2027."""
    from games.golf.services.records import season_finishes
    past = app.config['SEASON_YEAR'] - 1
    casey, *_ = _banked_season(past)
    _event(app.config['SEASON_YEAR'], 'Sony Open in Hawaii', 1, finalized=False)
    drafts = season_finishes(past)
    assert drafts[0].user_id == casey.id and drafts[0].place == 1


def test_the_registry_wires_the_seam():
    from games.golf.services.records import season_finishes
    from games.registry import get_entry
    assert get_entry('golf').season_finishes is season_finishes


def test_records_close_golf_puts_the_season_on_record(app):
    from core.records.cli import records_cli
    season = app.config['SEASON_YEAR']
    casey, *_ = _banked_season(season)

    result = app.test_cli_runner().invoke(records_cli, ['close', 'golf', str(season)])

    assert result.exit_code == 0, result.output
    rows = finishes_for('golf', season)
    assert [(r.place, r.name) for r in rows][:2] == [(1, 'Casey Champion'), (2, 'Brock Second')]
    assert rows[0].user_id == casey.id
    assert db.session.get(User, casey.id).is_reigning_champion is True
