"""The announcement's live boards: Survivor (games/cfb/services/announce_blocks.py)
and the Docket (games/docket/services/announce_blocks.py). Each renders the
current numbers, defaults to the latest finished week, and refuses a week
that has not finished (the reveal guard)."""
import pytest

from core.admin.announce import render_announcement
from extensions import db
from games.cfb.models import CfbWeekOutcome
from games.cfb.services import announce_blocks as survivor
from games.docket.services import announce_blocks as docket
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)
from tests.test_docket_record import ROSTER, _seed
from utils.letter_markup import MarkupError


def _outcome(week, user, *, lives, lost=False, out=False):
    db.session.add(CfbWeekOutcome(week_id=week.id, user_id=user.id,
                                  lives_remaining=lives, is_eliminated=out,
                                  lost_life=lost))


def _survivor_week_3():
    """Week 3 complete: Iowa (-6) lost with two riders, Utah (+3) won with
    one; Ava survives, Ben loses a life, Cy is cut. Week 4 is live."""
    ava, ben, cy = (make_user(n) for n in ('ava', 'ben', 'cy'))
    make_enrollment(ava, lives=2, display_name='Ava')
    make_enrollment(ben, lives=1, display_name='Ben')
    make_enrollment(cy, lives=0, eliminated=True, display_name='Cy')
    week = make_week(3, is_complete=True)
    iowa, duke, utah, byu = (make_team(n) for n in ('Iowa', 'Duke', 'Utah', 'BYU'))
    make_game(week, iowa, duke, spread=-6, winner='away')
    make_game(week, byu, utah, spread=-3, winner='away')
    make_pick(ava, week, utah, is_correct=True)
    make_pick(ben, week, iowa, is_correct=False)
    make_pick(cy, week, iowa, is_correct=False)
    _outcome(week, ava, lives=2)
    _outcome(week, ben, lives=1, lost=True)
    _outcome(week, cy, lives=0, lost=True, out=True)
    make_week(4, is_active=True)
    db.session.commit()
    return week


# ---------------------------------------------------------------------------
# Survivor
# ---------------------------------------------------------------------------

def test_survivor_board_ranks_the_living(app):
    with app.app_context():
        _survivor_week_3()
        block = survivor.survivor_board({})
    assert block.plain.splitlines()[0] == 'Still standing: 2'
    assert '1. Ava: 2 lives · spread +0.0' in block.plain
    assert '2. Ben: One life' in block.plain
    assert 'Cy' not in block.plain


def test_survivor_board_top_caps_and_counts_the_rest(app):
    with app.app_context():
        _survivor_week_3()
        block = survivor.survivor_board({'top': '1'})
    assert 'Ben' not in block.plain
    assert 'And 1 more still standing' in block.plain


def test_survivor_cuts_says_the_week_in_words(app):
    with app.app_context():
        _survivor_week_3()
        block = survivor.survivor_cuts({})
    assert 'Two players lost a life in Week 3. One was cut. 2 remain.' in block.plain
    assert 'Cut in Week 3: Cy.' in block.plain


def test_survivor_picks_is_the_results_page_split(app):
    with app.app_context():
        _survivor_week_3()
        block = survivor.survivor_picks({})
    assert block.plain.splitlines() == [
        'Week 3 pick split', 'Iowa (-6): 2 picks (Lost)', 'Utah (+3): 1 pick (Won)']


def test_survivor_boards_refuse_an_unfinished_week(app):
    """The reveal guard: Week 4's picks never reach an announcement early."""
    with app.app_context():
        _survivor_week_3()
        for board in (survivor.survivor_cuts, survivor.survivor_picks):
            with pytest.raises(ValueError, match='Week 4 is not complete'):
                board({'week': '4'})
            with pytest.raises(ValueError, match='no Week 9'):
                board({'week': '9'})


def test_survivor_boards_with_no_finished_week(app):
    with app.app_context():
        make_week(1, is_active=True)
        db.session.commit()
        with pytest.raises(ValueError, match='no finished week'):
            survivor.survivor_picks({})


@pytest.mark.parametrize('args, message', [
    ({'week': 'three'}, 'a number'),
    ({'week': '0'}, 'a number'),
    ({'round': '3'}, 'does not take round='),
])
def test_survivor_board_settings_are_checked(app, args, message):
    with app.app_context():
        _survivor_week_3()
        with pytest.raises(ValueError, match=message):
            survivor.survivor_picks(args)


# ---------------------------------------------------------------------------
# The Docket
# ---------------------------------------------------------------------------

def test_docket_week_names_the_top_sheet_and_the_field(app, monkeypatch):
    with app.app_context():
        _seed(monkeypatch, ROSTER)
        block = docket.docket_week({})
    assert 'Week 1 around the docket' in block.plain
    assert 'Top sheet: Dana Whitfield, 7-1' in block.plain
    assert 'Weekly purse: $20 to Dana Whitfield' in block.plain
    assert 'You' not in block.plain
    lines = block.plain.splitlines()
    top = lines[lines.index('Week 1: the top 3') + 1:]
    assert [line.split(':')[0] for line in top] == [
        '1. Dana Whitfield', '2. Clerk of Court', '3. Ghost Gary']


def test_docket_week_refuses_an_ungraded_week(app, monkeypatch):
    from tests._docket_fixtures import make_week as make_docket_week
    with app.app_context():
        _seed(monkeypatch, ROSTER)
        make_docket_week(2)
        db.session.commit()
        with pytest.raises(ValueError, match='Week 2 is not graded'):
            docket.docket_week({'week': '2'})


def test_docket_boards_before_any_grade(app):
    with app.app_context():
        for board in (docket.docket_week, docket.docket_season):
            with pytest.raises(ValueError, match='no graded week'):
                board({})


def test_docket_season_ledger_and_purse(app, monkeypatch):
    with app.app_context():
        _seed(monkeypatch, ROSTER)
        block = docket.docket_season({'top': '2'})
    assert 'The season after Week 1' in block.plain
    assert '1. Dana Whitfield' in block.plain and 'Ghost Gary' not in block.plain
    assert 'The season purse' in block.plain and 'First: $' in block.plain


# ---------------------------------------------------------------------------
# Through the announcement
# ---------------------------------------------------------------------------

def test_boards_render_inside_an_announcement(app):
    with app.app_context(), app.test_request_context():
        _survivor_week_3()
        plain, html = render_announcement(
            'Week 3', 'The damage:\n\n[[survivor-cuts]]\n\n[[survivor-picks week=3]]')
    assert 'Cut in Week 3: Cy.' in plain and 'Iowa (-6)' in html


def test_a_board_error_names_its_line(app):
    with app.app_context(), app.test_request_context():
        _survivor_week_3()
        with pytest.raises(MarkupError) as caught:
            render_announcement('s', 'Intro\n\n[[survivor-picks week=4]]')
    assert caught.value.errors == [
        'Line 3: [[survivor-picks]] shows finished weeks only; Week 4 is not '
        'complete yet.']
