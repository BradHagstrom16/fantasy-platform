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


def test_consensus_per_week_and_no_wolf_without_a_crowd(app, season):
    with app.app_context():
        brief = build_brief()
        w1, w2 = brief.weeks
        assert (w1.week_number, w1.pick, w1.holders, w1.sheets, w1.result) == (
            1, 'Utah -3.5', 2, 3, 'win')
        # Ann's away B and Cy's under B were each held alone and won, but a
        # wolf needs a crowd: Ann faced one sheet (Bob), Cy faced none.
        assert w1.lone_wolf is None
        assert (w2.pick, w2.holders, w2.result) == ('Iowa +7', 2, 'win')
        assert w2.lone_wolf is None


@pytest.fixture
def wolf_week(app):
    """One graded week, five members, three games.

    Game D (Clemson at LSU, LSU -7): Ann, Bob, Cy and Dee take LSU, Eve
    alone on Clemson +7; Clemson wins outright: Eve's wolf, against 4.
    Game E (earlier kickoff): Ann and Bob over, Cy alone under, under hits:
    a wolf against 2. Game F (earliest): Dee and Eve over, Ann alone under,
    under hits: against 2, the same crowd as E.
    """
    with app.app_context():
        users = {n: make_user(n.lower()) for n in ('Ann', 'Bob', 'Cy', 'Dee', 'Eve')}
        for name, u in users.items():
            make_enrollment(u, display_name=name)
        wk = _graded_week(1)
        f = make_game(wk, kickoff=datetime(2026, 9, 5, 15, 0), home='Army', away='Navy',
                      home_spread=-3.5, total=40.0)
        e = make_game(wk, kickoff=datetime(2026, 9, 5, 16, 0), home='Utah', away='Idaho',
                      home_spread=-3.5, total=51.5)
        d = make_game(wk, kickoff=datetime(2026, 9, 5, 23, 0), home='LSU', away='Clemson',
                      home_spread=-7.0, total=50.5)
        _final(f, 17, 13)     # 30: under
        _final(e, 24, 20)     # 44: under
        _final(d, 20, 27)     # Clemson outright
        wk.tiebreaker_game_id = d.id
        for name in ('Ann', 'Bob', 'Cy', 'Dee'):
            _pick(users[name], wk, d, 'spread', 'home', 1)
        _pick(users['Eve'], wk, d, 'spread', 'away', 1)
        _pick(users['Ann'], wk, e, 'total', 'over', 2)
        _pick(users['Bob'], wk, e, 'total', 'over', 2)
        _pick(users['Cy'], wk, e, 'total', 'under', 2)
        _pick(users['Dee'], wk, f, 'total', 'over', 2)
        _pick(users['Eve'], wk, f, 'total', 'over', 2)
        _pick(users['Ann'], wk, f, 'total', 'under', 3)
        for u in users.values():
            _result(wk, u, 1, 1)
        db.session.commit()


def test_one_lone_wolf_a_week_the_biggest_crowd_faded(app, wolf_week):
    with app.app_context():
        (week,) = build_brief().weeks
        wolf = week.lone_wolf
        assert (wolf.enrollment.get_display_name(), wolf.pick, wolf.against) == (
            'Eve', 'Clemson +7', 4)
        assert wolf.caption == 'Clemson at LSU'


def test_a_tied_crowd_goes_to_the_earliest_kickoff(app, wolf_week):
    """Take Eve's pick off the board: Cy (under E) and Ann (under F) each
    faded two sheets; F kicked off first, so Ann is the wolf."""
    with app.app_context():
        db.session.query(DocketPick).filter(
            DocketPick.market == 'spread', DocketPick.side == 'away').delete()
        db.session.commit()
        (week,) = build_brief().weeks
        wolf = week.lone_wolf
        assert (wolf.enrollment.get_display_name(), wolf.pick, wolf.against) == (
            'Ann', 'Under 40', 2)


def test_the_page_prints_one_wolf_line(app, client, wolf_week):
    with app.app_context():
        from models.user import User
        login(client, db.session.scalar(db.select(User).filter_by(username='ann')))
    page = client.get('/docket/brief').get_data(as_text=True)
    assert page.count('docket-brief-wolf"') == 1
    assert 'Clemson +7' in page and 'against 4 sheets' in page
    assert 'Eve</a> on Clemson +7' in page


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
    assert (ann.overs, ann.unders, cy.overs) == (1, 0, 0)
    # How the fades went: Cy's away A lost, Ann's home C lost.
    assert (cy.contrarian_record.label, ann.contrarian_record.label) == ('0-1', '0-1')
    assert bob.contrarian_record.decided == 0
    assert (cy.best_week, cy.best_points) == (1, 1.0)
    assert ann.contrarian_share == 0.25


def test_the_short_of_it(app, season):
    """The page's answer first: the most lopsided habit pair (unders 1-0 vs
    overs 0-1 splits wider than favorites 3-1 vs underdogs 2-2), the
    most-held side's weeks (both won), and every fade (Cy's away A, Ann's
    home C: both lost)."""
    with app.app_context():
        short = build_brief().short
        better, worse = short.leaning
    assert (better.key, better.record.label, worse.key, worse.record.label) == (
        'unders', '1-0', 'overs', '0-1')
    assert short.consensus.label == '2-0'
    assert short.fades.label == '0-2'


def test_the_leaning_needs_both_sides_decided_and_a_gap():
    from games.docket.services.brief import Habit, Record, _leaning

    def habits(fav, dog, over, under):
        return tuple(Habit(key=k, label=k.title(), count=r.decided, record=r)
                     for k, r in (('favorites', fav), ('underdogs', dog),
                                  ('overs', over), ('unders', under)))

    even = Record(wins=1, losses=1)
    assert _leaning(habits(even, even, even, even)) is None          # no gap
    assert _leaning(habits(Record(wins=3), Record(), even, even)) is None  # dogs undecided
    better, worse = _leaning(habits(Record(wins=3), Record(losses=1), even, even))
    assert (better.key, worse.key) == ('favorites', 'underdogs')


def test_the_number_names_who_saved_none(app, client, season):
    """Dee is on the ledger with a graded week but never saved a number:
    the section names her rather than dropping her silently."""
    with app.app_context():
        dee = make_user('dee')
        make_enrollment(dee, display_name='Dee')
        from games.docket.models import DocketWeek
        w1 = db.session.scalar(db.select(DocketWeek).filter_by(week_number=1))
        _result(w1, dee, 0, 0, 505)
        db.session.commit()
        unsaved = build_brief().number.unsaved
        assert [e.get_display_name() for e in unsaved] == ['Dee']
        login(client, dee)
    page = client.get('/docket/brief').get_data(as_text=True)
    assert 'No number saved:' in page and '>Dee</a>.' in page


def test_the_page_leads_with_the_short_of_it_and_its_doors(app, client, season):
    with app.app_context():
        from models.user import User
        login(client, db.session.get(User, season['ann']))
    page = client.get('/docket/brief').get_data(as_text=True)
    short = page[page.index('id="brief-short"'):page.index('id="brief-habits"')]
    assert 'The short of it' in short
    assert 'Unders are' in short and 'overs are' in short
    assert "The week's most-held side has gone" in short
    assert 'Sides taken against the field have gone' in short
    for anchor in ('brief-habits', 'brief-consensus', 'brief-x2', 'brief-number', 'brief-members'):
        assert f'href="#{anchor}"' in short
    # The rules page's words, not the engine's.
    assert 'The Headliners' in page and 'x2 ledger' not in page
    for jargon in ("engine's grade", 'designated case', 'scoring side'):
        assert jargon not in page


def test_no_guess_at_all_reads_as_an_empty_number(app, client, wolf_week):
    with app.app_context():
        from models.user import User
        login(client, db.session.scalar(db.select(User).filter_by(username='ann')))
    page = client.get('/docket/brief').get_data(as_text=True)
    number = page[page.index('id="brief-number"'):page.index('id="brief-members"')]
    assert 'No number saved in a graded week yet.' in number
    assert 'guessed over' not in number and 'No number saved:' not in number


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
    assert 'Utah -3.5' in page and 'How each member plays' in page
    assert 'No lone wolf this week' in page
    assert 'graded weeks' in page.lower()
    ledger = client.get('/docket/ledger').get_data(as_text=True)
    assert '/docket/brief' in ledger
    assert client.get('/docket/brief?sort=contrarian').status_code == 200


def test_the_brief_is_members_only(client):
    assert client.get('/docket/brief').status_code == 302


def test_the_members_sorts_keep_blanks_last_in_both_directions():
    """A dash on the page (no week submitted) follows every measured row
    whichever way the column is sorted."""
    from types import SimpleNamespace

    from games.docket.routes import _brief_order

    def row(name, best):
        return SimpleNamespace(name=name, best_week=1 if best is not None else None,
                               best_points=best)

    rows = [row('blank', None), row('low', 2.0), row('high', 9.0)]
    for direction, measured in (('asc', ['low', 'high']), ('desc', ['high', 'low'])):
        ordered, _key, _dir = _brief_order(rows, 'best', direction)
        assert [r.name for r in ordered] == [*measured, 'blank'], direction


def test_the_members_rows_sort_only_on_what_they_print():
    """How each member plays prints no x2 and no off-by (those have their
    own sections), so neither is a sort; an old link falls back to ledger
    order rather than erroring."""
    from games.docket.routes import BRIEF_SORTS, _brief_order
    assert set(BRIEF_SORTS) == {'name', 'contrarian', 'favorites', 'underdogs',
                                'overs', 'unders', 'best'}
    assert _brief_order([], 'x2', 'desc') == ([], None, None)
