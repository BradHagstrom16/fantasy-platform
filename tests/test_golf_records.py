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


def _line(user, season, total, *, league_id):
    e = GolfEnrollment(user_id=user.id, league_id=league_id, season_year=season, total_points=total)
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


def _banked_season(season, *, league_id):
    _event(season, 'Sony Open in Hawaii', 1)
    _event(season, 'The American Express', 2)
    casey = _user('casey', display_name='Casey Champion')
    brock = _user('brock', display_name='Brock Second')
    dana = _user('dana', display_name='Dana Second')
    morgan = _user('morgan')
    _line(casey, season, 4_200_000, league_id=league_id)
    _line(dana, season, 750_000, league_id=league_id)
    _line(brock, season, 750_000, league_id=league_id)
    _line(morgan, season, 0, league_id=league_id)
    return casey, brock, dana, morgan


def test_a_banked_season_ranks_the_lines_with_shared_places(app, golf_leagues):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    casey, brock, dana, morgan = _banked_season(season, league_id=golf_leagues['handicap'].id)

    drafts = season_finishes(season)

    assert [(d.place, d.name, d.user_id, d.detail) for d in drafts] == [
        (1, 'Casey Champion', casey.id, '$4,200,000'),
        (2, 'Brock Second', brock.id, '$750,000'),
        (2, 'Dana Second', dana.id, '$750,000'),
        (4, 'morgan', morgan.id, '$0'),
    ]
    assert [d.outcome for d in drafts] == ['champion', None, None, None]


def test_tied_leaders_are_both_champions(app, golf_leagues):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    _event(season, 'Sony Open in Hawaii', 1)
    a, b = _user('a', display_name='Alex'), _user('b', display_name='Blake')
    _line(a, season, 1_000_000, league_id=golf_leagues['handicap'].id)
    _line(b, season, 1_000_000, league_id=golf_leagues['handicap'].id)
    drafts = season_finishes(season)
    assert [(d.place, d.outcome) for d in drafts] == [(1, 'champion'), (1, 'champion')]


def test_refuses_a_season_with_no_schedule(app):
    from games.golf.services.records import season_finishes
    with pytest.raises(SeasonNotClosed, match='no schedule'):
        season_finishes(2031)


def test_refuses_while_an_event_is_not_banked(app, golf_leagues):
    from games.golf.services.records import season_finishes
    season = app.config['SEASON_YEAR']
    _event(season, 'Sony Open in Hawaii', 1)
    _event(season, 'Masters Tournament', 15, finalized=False)
    _line(_user('casey'), season, 100, league_id=golf_leagues['handicap'].id)
    with pytest.raises(SeasonNotClosed, match='Masters Tournament'):
        season_finishes(season)


def test_a_past_season_closes_from_its_own_rows(app, golf_leagues):
    """Like the Docket's seam and unlike Survivor's, the builder takes any
    year: 2026 closes from a box whose configured season is 2027."""
    from games.golf.services.records import season_finishes
    past = app.config['SEASON_YEAR'] - 1
    casey, *_ = _banked_season(past, league_id=golf_leagues['handicap'].id)
    _event(app.config['SEASON_YEAR'], 'Sony Open in Hawaii', 1, finalized=False)
    drafts = season_finishes(past)
    assert drafts[0].user_id == casey.id and drafts[0].place == 1


def test_the_registry_wires_the_seam():
    from games.golf.services.records import season_finishes
    from games.registry import get_entry
    assert get_entry('golf').season_finishes is season_finishes


def test_records_close_golf_puts_the_season_on_record(app, golf_leagues):
    from core.records.cli import records_cli
    season = app.config['SEASON_YEAR']
    casey, *_ = _banked_season(season, league_id=golf_leagues['handicap'].id)

    result = app.test_cli_runner().invoke(records_cli, ['close', 'golf', str(season)])

    assert result.exit_code == 0, result.output
    rows = finishes_for('golf', season)
    assert [(r.place, r.name) for r in rows][:2] == [(1, 'Casey Champion'), (2, 'Brock Second')]
    assert rows[0].user_id == casey.id
    assert db.session.get(User, casey.id).is_reigning_champion is True


# --- one board per league (ADR-075, Task C1) ---------------------------------

def _pollyanna_room(season, *, league_id):
    """Two Pollyanna lines; Casey (the Handicap champion) is on neither."""
    polly = _user('polly', display_name='Polly Leader')
    quinn = _user('quinn', display_name='Quinn Second')
    _line(polly, season, 900_000, league_id=league_id)
    _line(quinn, season, 100_000, league_id=league_id)
    return polly, quinn


def test_close_golf_writes_one_board_per_league(app, golf_leagues):
    from core.records.cli import records_cli
    from models.records import reigning_champion_user_ids
    season = app.config['SEASON_YEAR']
    casey, *_ = _banked_season(season, league_id=golf_leagues['handicap'].id)
    polly, quinn = _pollyanna_room(season, league_id=golf_leagues['pollyanna'].id)

    result = app.test_cli_runner().invoke(records_cli, ['close', 'golf', str(season)])

    assert result.exit_code == 0, result.output
    assert 'Handicap Pay Sheet: 4 finishers on record' in result.output
    assert 'Pollyanna Pay Sheet: 2 finishers on record' in result.output
    handicap = finishes_for('golf', season, division='handicap')
    pollyanna = finishes_for('golf', season, division='pollyanna')
    assert [(r.place, r.name, r.field_size) for r in pollyanna] == [
        (1, 'Polly Leader', 2), (2, 'Quinn Second', 2)]
    assert {r.division_name for r in handicap} == {'Handicap Pay Sheet'}
    assert {r.division_name for r in pollyanna} == {'Pollyanna Pay Sheet'}
    assert [r.user_id for r in handicap + pollyanna if r.place == 1] == [casey.id, polly.id]
    assert reigning_champion_user_ids() == frozenset({casey.id, polly.id})
    assert db.session.get(User, polly.id).is_reigning_champion is True
    assert db.session.get(User, quinn.id).is_reigning_champion is False


def test_records_show_prints_both_divisions(app, golf_leagues):
    from core.records.cli import records_cli
    season = app.config['SEASON_YEAR']
    _banked_season(season, league_id=golf_leagues['handicap'].id)
    _pollyanna_room(season, league_id=golf_leagues['pollyanna'].id)
    runner = app.test_cli_runner()
    assert runner.invoke(records_cli, ['close', 'golf', str(season)]).exit_code == 0

    index = runner.invoke(records_cli, ['show'])
    assert index.exit_code == 0, index.output
    assert f'golf {season} handicap: 4 finishers' in index.output
    assert f'golf {season} pollyanna: 2 finishers' in index.output

    board = runner.invoke(records_cli, ['show', 'golf', str(season)])
    assert board.exit_code == 0, board.output
    out = board.output
    assert 'Handicap Pay Sheet: 4 finishers' in out and 'Pollyanna Pay Sheet: 2 finishers' in out
    # Each league's board under its own name, the house league first.
    assert out.index('Handicap Pay Sheet') < out.index('Casey Champion') \
        < out.index('Pollyanna Pay Sheet') < out.index('Polly Leader')


def test_a_league_with_no_enrollee_is_skipped_and_named(app, golf_leagues):
    """Review Focus 5: the empty league is named and skipped, the other closes."""
    from core.records.cli import records_cli
    season = app.config['SEASON_YEAR']
    casey, *_ = _banked_season(season, league_id=golf_leagues['handicap'].id)

    result = app.test_cli_runner().invoke(records_cli, ['close', 'golf', str(season)])

    assert result.exit_code == 0, result.output
    assert f'Pollyanna Pay Sheet: nobody on the sheet in {season}, skipped' in result.stderr
    assert 'Handicap Pay Sheet: 4 finishers on record' in result.output
    rows = finishes_for('golf', season)
    assert {r.division for r in rows} == {'handicap'}
    assert rows[0].user_id == casey.id


def test_every_league_empty_is_an_empty_board(app, golf_leagues):
    from core.records.cli import records_cli
    season = app.config['SEASON_YEAR']
    _event(season, 'Sony Open in Hawaii', 1)
    result = app.test_cli_runner().invoke(records_cli, ['close', 'golf', str(season)])
    assert result.exit_code == 1
    assert 'the board is empty' in result.output
    assert 'Handicap Pay Sheet: nobody on the sheet' in result.stderr
    assert finishes_for('golf', season) == []


def test_a_closed_handicap_board_never_crowns_the_pollyanna_pages(app, client, golf_leagues):
    """The record is read per league: Handicap's closed board crowns the
    Handicap Sheet and Record Room only. Pollyanna's own banked season stays
    off the record until it is closed, and never borrows Casey's crown."""
    from models.records import FinishDraft, record_season
    season = app.config['SEASON_YEAR']
    casey, *_ = _banked_season(season, league_id=golf_leagues['handicap'].id)
    _pollyanna_room(season, league_id=golf_leagues['pollyanna'].id)
    record_season('golf', season, [
        FinishDraft(casey.id, 'Casey Champion', 1, 'champion', '$4,200,000',
                    division='handicap', division_name='Handicap Pay Sheet'),
    ])

    for url in ('/golf/handicap/', '/golf/handicap/stats'):
        body = client.get(url).get_data(as_text=True)
        fold = body[body.index('id="golf-champion"'):]
        fold = fold[:fold.index('</section>')]
        assert 'Casey Champion' in fold, url
        assert 'On the club’s record.' in fold, url
        assert f'href="/records#board-golf-{season}-handicap"' in fold, url

    for url in ('/golf/pollyanna/', '/golf/pollyanna/stats'):
        body = client.get(url).get_data(as_text=True)
        assert 'Casey Champion' not in body, url
        assert 'On the club’s record.' not in body, url
        assert '#board-golf-' not in body, url
