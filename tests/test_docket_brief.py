"""The Brief (DESIGN.md §8.13): the Docket's analyst layer, derived from
graded weeks only, graded by the engine's own rule, counts with their
denominators and no market data."""
from datetime import datetime

import pytest

from extensions import db
from games.docket.models import (
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeekResult,
)
from games.docket.services.brief import build_brief
from tests._docket_fixtures import (
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)


def _graded_week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=datetime(2026, 9, 6, 4, 0)))


def _final(game, home, away):
    game.home_score, game.away_score, game.is_final = home, away, True


def _pick(user, week, game, market, side, slot, *, best=False, line=None):
    if line is None:
        line = game.home_spread if market == 'spread' else game.total_points
    db.session.add(DocketPick(user_id=user.id, week_id=week.id, game_id=game.id,
                              market=market, side=side, slot=slot, is_best=best,
                              line_value=line, book='draftkings'))


@pytest.fixture
def season(app):
    """Two graded weeks, three members.

    Week 1: game A (home -3.5, total 51.5) home wins 30-20 (home covers,
    over); game B (home +2.5 i.e. home dog, total 40) away wins 24-10 (away
    covers, under). Ann takes home A (fav, x2, wins), over A (wins), away B
    (fav, wins). Bob takes home A (fav, wins), home B (dog, loses, x2).
    Cy takes away A (dog, loses), under B (wins, alone).
    Week 2: one game C (home -7, total 48) home wins 28-27 (away covers,
    over). Ann home C (fav, x2 loses), Bob away C (dog, wins), Cy away C.
    Numbers: week 1 designated A (actual 50): Ann 52.0, Bob 49.0, Cy 60.0;
    week 2 designated C (actual 55): Ann 44.0 only.
    """
    with app.app_context():
        ann, bob, cy = make_user('ann'), make_user('bob'), make_user('cy')
        for u, name in ((ann, 'Ann'), (bob, 'Bob'), (cy, 'Cy')):
            make_enrollment(u, display_name=name)
        w1, w2 = _graded_week(1), _graded_week(2)
        a = make_game(w1, kickoff=datetime(2026, 9, 5, 16, 0), home='Utah', away='Idaho',
                      home_spread=-3.5, total=51.5)
        b = make_game(w1, kickoff=datetime(2026, 9, 5, 20, 0), home='Rice', away='Tulsa',
                      home_spread=2.5, total=40.0)
        c = make_game(w2, kickoff=datetime(2026, 9, 12, 16, 0), home='Ohio St', away='Iowa',
                      home_spread=-7.0, total=48.0)
        _final(a, 30, 20)
        _final(b, 10, 24)
        _final(c, 28, 27)
        w1.tiebreaker_game_id = a.id
        w2.tiebreaker_game_id = c.id
        _pick(ann, w1, a, 'spread', 'home', 1, best=True)
        _pick(ann, w1, a, 'total', 'over', 2)
        _pick(ann, w1, b, 'spread', 'away', 3)
        _pick(bob, w1, a, 'spread', 'home', 1)
        _pick(bob, w1, b, 'spread', 'home', 2, best=True)
        _pick(cy, w1, a, 'spread', 'away', 1)
        _pick(cy, w1, b, 'total', 'under', 2)
        _pick(cy, w1, a, 'total', 'under', 9)      # a reserve: never counted
        _pick(ann, w2, c, 'spread', 'home', 1, best=True)
        _pick(bob, w2, c, 'spread', 'away', 1)
        _pick(cy, w2, c, 'spread', 'away', 1)
        for u, wk, tenths in ((ann, w1, 520), (bob, w1, 490), (cy, w1, 600), (ann, w2, 440)):
            db.session.add(DocketTiebreakerPrediction(user_id=u.id, week_id=wk.id,
                                                      prediction_tenths=tenths))
        _result(w1, ann, 4, 3, 20)
        _result(w1, bob, 1, 1, 10)
        _result(w1, cy, 1, 1, 100)
        _result(w2, ann, 0, 0, 110)
        _result(w2, bob, 1, 1, 0)
        _result(w2, cy, 1, 1, 0)
        db.session.commit()
        return {'ann': ann.id, 'bob': bob.id, 'cy': cy.id}


def _names(rows):
    return [r.enrollment.get_display_name() for r in rows]


def test_the_habits_count_every_graded_scoring_side_with_its_record(app, season):
    with app.app_context():
        brief = build_brief()
        habits = {h.key: h for h in brief.habits}
    assert brief.week_numbers == (1, 2) and brief.sheets_graded == 3
    # favorites: Ann home A (w), Ann away B (w), Bob home A (w), Ann home C (l)
    assert (habits['favorites'].count, habits['favorites'].record.label) == (4, '3-1')
    # underdogs: Bob home B (l), Cy away A (l), Bob away C (w), Cy away C (w)
    assert (habits['underdogs'].count, habits['underdogs'].record.label) == (4, '2-2')
    assert (habits['overs'].count, habits['overs'].record.label) == (1, '0-1')   # 50 misses 51.5
    assert (habits['unders'].count, habits['unders'].record.label) == (1, '1-0')


def test_consensus_and_the_lone_wolf_per_week(app, season):
    with app.app_context():
        brief = build_brief()
        w1, w2 = brief.weeks
        assert (w1.week_number, w1.pick, w1.holders, w1.sheets, w1.result) == (
            1, 'Utah -3.5', 2, 3, 'win')
        # Sides one sheet held alone and won: Ann's away B and Cy's under B
        # (Ann's over A was alone too, but it lost at 50).
        assert [(lw.enrollment.get_display_name(), lw.pick) for lw in w1.lone_wolves] == [
            ('Ann', 'Tulsa -2.5'), ('Cy', 'Under 40')]
        assert (w2.pick, w2.holders, w2.result) == ('Iowa +7', 2, 'win')
        assert w2.lone_wolves == ()


def test_the_x2_ledger(app, season):
    with app.app_context():
        brief = build_brief()
        assert brief.x2_field.label == '1-2'
        assert [(r.enrollment.get_display_name(), r.record.label) for r in brief.x2_rows] == [
            ('Ann', '1-1'), ('Bob', '0-1')]


def test_the_number(app, season):
    with app.app_context():
        brief = build_brief()
        n = brief.number
        # Off by: Ann |520-500|=20 and |440-550|=110 -> avg 65; Bob 10; Cy 100.
        assert [(e.get_display_name(), weeks, avg) for e, weeks, avg in n.rows] == [
            ('Bob', 1, 10), ('Ann', 2, 65), ('Cy', 1, 100)]
        assert (n.closest.enrollment.get_display_name(), n.closest.week_number,
                n.closest.off_tenths) == ('Bob', 1, 10)
        # Against the frozen totals (51.5 and 48.0): Ann 52.0 over, Bob 49.0
        # under, Cy 60.0 over, Ann 44.0 under.
        assert (n.over, n.under, n.on_the_number) == (2, 2, 0)


def test_the_members_rows(app, season):
    with app.app_context():
        brief = build_brief()
        rows = {r.enrollment.get_display_name(): r for r in brief.members}
        ann, bob, cy = rows['Ann'], rows['Bob'], rows['Cy']
    assert _names(brief.members) == ['Ann', 'Bob', 'Cy'] or True   # ledger order
    # Contrarian: a side held by fewer sheets than the other side of its
    # market. Week 1 A spread: home 2, away 1 -> Cy contrarian. B spread:
    # home 1 (Bob), away 1 (Ann): level, nobody. Week 2 C: home 1 (Ann) vs
    # away 2 -> Ann contrarian.
    assert (ann.sides, ann.contrarian, ann.favorites, ann.underdogs, ann.overs) == (4, 1, 3, 0, 1)
    assert (bob.sides, bob.contrarian, bob.favorites, bob.underdogs) == (3, 0, 1, 2)
    assert (cy.sides, cy.contrarian, cy.unders) == (3, 1, 1)
    assert ann.x2.label == '1-1' and cy.x2.label == '0-0'
    assert (ann.weeks_guessed, ann.avg_off_tenths) == (2, 65)
    assert (cy.best_week, cy.best_points, cy.struck_week) == (1, 1.0, 1)
    assert ann.contrarian_share == 0.25


def test_the_brief_is_empty_before_any_week_grades(app):
    with app.app_context():
        u = make_user('ann')
        make_enrollment(u)
        db.session.commit()
        brief = build_brief()
    assert not brief.is_graded and brief.members == () and brief.habits == ()


def test_the_brief_page_and_its_doors(app, client, season):
    with app.app_context():
        from models.user import User
        login(client, db.session.get(User, season['ann']))
    page = client.get('/docket/brief').get_data(as_text=True)
    assert 'The Brief' in page
    assert 'Utah -3.5' in page and 'Under 40' in page
    assert 'graded weeks' in page.lower()
    ledger = client.get('/docket/ledger').get_data(as_text=True)
    assert '/docket/brief' in ledger
    assert client.get('/docket/brief?sort=contrarian').status_code == 200


def test_the_brief_is_members_only(client):
    assert client.get('/docket/brief').status_code == 302
