"""The Field (games/cfb/services/field.py, /cfb/field): CFB Survivor's field
intelligence under the room's one visibility rule (9.9): a pick is read only
once its week's deadline has passed; the cut, week by week, comes from the
outcomes on record; the spent board names the survivors who burned a team;
most backed orders by count, never by spread; no rank movement anywhere."""
from datetime import datetime, timedelta

import pytest

from extensions import db
from games.cfb.models import CfbWeekOutcome
from games.cfb.services.field import (
    attrition_rows,
    build_field,
    field_delta_line,
    most_backed,
    spent_board,
)
from tests._cfb_fixtures import (
    PAST_DEADLINE,
    SEASON,
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

FUTURE_DEADLINE = datetime(2099, 9, 5, 11, 0)


def _outcome(week, user, *, lives, eliminated=False, lost=False):
    db.session.add(CfbWeekOutcome(week_id=week.id, user_id=user.id,
                                  lives_remaining=lives, is_eliminated=eliminated,
                                  lost_life=lost))


@pytest.fixture
def season(app):
    """Four members, two revealed weeks and one open week.

    Week 1 (complete): Ann and Bob take Georgia (win), Cy takes Iowa (loss,
    one life), Dee takes Georgia (win). Week 2 (complete): Ann takes Ohio
    State (win), Bob takes Iowa (loss, one life), Cy takes Utah (loss, out),
    Dee takes Ohio State (win). Week 3 (open): Ann has picked Utah, hidden.
    """
    with app.app_context():
        ann, bob, cy, dee = (make_user(n) for n in ('ann', 'bob', 'cy', 'dee'))
        e = {
            'ann': make_enrollment(ann, display_name='Ann'),
            'bob': make_enrollment(bob, lives=1, display_name='Bob'),
            'cy': make_enrollment(cy, lives=0, eliminated=True, display_name='Cy'),
            'dee': make_enrollment(dee, display_name='Dee'),
        }
        georgia, iowa, ohio, utah = (make_team(n) for n in ('Georgia', 'Iowa', 'Ohio State', 'Utah'))
        w1 = make_week(1, deadline=PAST_DEADLINE, is_complete=True)
        w2 = make_week(2, deadline=PAST_DEADLINE + timedelta(days=7), is_complete=True)
        w3 = make_week(3, deadline=FUTURE_DEADLINE, is_active=True)
        make_game(w1, georgia, iowa, spread=-10.5, winner='home')
        make_game(w2, ohio, utah, spread=-7.0, winner='home')
        make_game(w2, iowa, georgia, spread=3.0, winner='away')
        make_pick(ann, w1, georgia, is_correct=True)
        make_pick(bob, w1, georgia, is_correct=True)
        make_pick(cy, w1, iowa, is_correct=False)
        make_pick(dee, w1, georgia, is_correct=True)
        make_pick(ann, w2, ohio, is_correct=True)
        make_pick(bob, w2, iowa, is_correct=False)
        make_pick(cy, w2, utah, is_correct=False)
        make_pick(dee, w2, ohio, is_correct=True)
        make_pick(ann, w3, utah)                       # open: hidden everywhere
        _outcome(w1, ann, lives=2)
        _outcome(w1, bob, lives=2)
        _outcome(w1, cy, lives=1, lost=True)
        _outcome(w1, dee, lives=2)
        _outcome(w2, ann, lives=2)
        _outcome(w2, bob, lives=1, lost=True)
        _outcome(w2, cy, lives=0, eliminated=True, lost=True)
        _outcome(w2, dee, lives=2)
        db.session.commit()
        return {k: v.id for k, v in e.items()} | {'ann_user': ann.id, 'utah': utah.id}


def test_the_cut_week_by_week(app, season):
    with app.app_context():
        field = build_field(SEASON)
    w1, w2 = field.weeks
    assert (w1.alive_entering, w1.lost_life, w1.cut, w1.alive_after) == (4, 1, 0, 4)
    assert (w1.two_lives, w1.one_life, w1.out) == (3, 1, 0)
    assert (w2.alive_entering, w2.lost_life, w2.cut, w2.alive_after) == (4, 1, 1, 3)
    assert (w2.two_lives, w2.one_life, w2.out) == (2, 1, 1)
    assert w1.complete and w2.complete
    assert (field.survivors, field.total, field.revealed_weeks, field.phase) == (3, 4, 2, 'early')


def test_the_spent_board_names_survivors_and_counts_holders(app, season):
    with app.app_context():
        field = build_field(SEASON)
        lines = {line.team.name: line for board in field.board for line in board.lines}
        georgia, ohio, iowa, utah = (lines[n] for n in ('Georgia', 'Ohio State', 'Iowa', 'Utah'))
        assert [(s.enrollment.get_display_name(), s.week_number) for s in georgia.spent_by] == [
            ('Ann', 1), ('Bob', 1), ('Dee', 1)]
        assert georgia.holders == 0 and georgia.spent_by_out == 0
        assert [s.enrollment.get_display_name() for s in ohio.spent_by] == ['Ann', 'Dee']
        assert ohio.holders == 1
        # Cy (out) burned Iowa and Utah: counted apart, never named as a survivor.
        assert [s.enrollment.get_display_name() for s in iowa.spent_by] == ['Bob']
        assert iowa.spent_by_out == 1
        # Ann's open Week 3 Utah pick is hidden: Utah still shows every survivor holding it.
        assert utah.spent_by == () and utah.spent_by_out == 1 and utah.holders == 3


def test_most_backed_orders_by_count_never_by_spread(app, season):
    with app.app_context():
        field = build_field(SEASON)
        rows = [(r.team.name, r.count, r.wins, r.losses) for r in field.backed]
    assert rows == [('Georgia', 3, 3, 0), ('Iowa', 2, 0, 2), ('Ohio State', 2, 2, 0), ('Utah', 1, 0, 1)]


def test_an_open_week_never_reaches_a_count(app, season):
    from games.cfb.models import CfbEnrollment, CfbWeek
    with app.app_context():
        enrollments = CfbEnrollment.query.all()
        weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
        # Passing the open week explicitly is the only way to reach it; the
        # builders themselves take the revealed weeks. Even then a pick of a
        # week with no outcome is not a cut and not a spent team here:
        assert len(attrition_rows(enrollments, weeks[:2])) == 2
        assert all(r.week_number < 3 for r in attrition_rows(enrollments, weeks))
        open_only = most_backed(weeks[2:])
        assert open_only and open_only[0].pending == 1     # only when asked for
        assert not any(s.week_number == 3 for b in spent_board(enrollments, weeks[:2])
                       for line in b.lines for s in line.spent_by)


def test_a_week_in_play_reads_its_settled_games_live(app, client, season):
    """Week 3's deadline passes and one of its games settles: Bob's Iowa
    loses (one life, so he is cut) while Ann's Utah is still being played.
    Outcomes are written only when the week completes, so the row is built
    from the live enrollments, marked in play, and the page says so."""
    from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek
    with app.app_context():
        w3 = CfbWeek.query.filter_by(week_number=3).one()
        w3.deadline = PAST_DEADLINE + timedelta(days=14)
        bob = db.session.get(CfbEnrollment, season['bob'])
        bob.lives_remaining, bob.is_eliminated = 0, True
        iowa = CfbTeam.query.filter_by(name='Iowa').one()
        georgia = CfbTeam.query.filter_by(name='Georgia').one()
        make_pick(bob.user, w3, iowa, is_correct=False)
        dee = db.session.get(CfbEnrollment, season['dee'])
        make_pick(dee.user, w3, georgia, is_correct=True)
        db.session.commit()
        field = build_field(SEASON)
        w3_row = field.weeks[-1]
        assert (w3_row.week_number, w3_row.complete) == (3, False)
        assert (w3_row.alive_entering, w3_row.lost_life, w3_row.cut, w3_row.alive_after) == (3, 0, 1, 2)
        assert (w3_row.two_lives, w3_row.one_life, w3_row.out) == (2, 0, 2)
        # The lounge's delta counts Week 3's cut against the field after
        # Week 2, never two weeks of cuts against Week 1.
        enrollments = CfbEnrollment.query.all()
        weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
        assert field_delta_line(enrollments, weeks) == 'One fewer than last week.'
    page = client.get('/cfb/field').get_data(as_text=True)
    assert 'still in play' in page and '>in play</span>' in page


def test_a_player_already_out_is_never_cut_twice(app, season):
    """Cy went out in Week 2, but his Week 3 pick was made while Week 2 was
    still in play and it loses too. The grader still grades it, so Week 3
    carries a lost life on an eliminated player, in play and on record; the
    cut is Week 2's alone."""
    from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek
    with app.app_context():
        w3 = CfbWeek.query.filter_by(week_number=3).one()
        w3.deadline = PAST_DEADLINE + timedelta(days=14)
        cy = db.session.get(CfbEnrollment, season['cy'])
        make_pick(cy.user, w3, CfbTeam.query.filter_by(name='Iowa').one(), is_correct=False)
        db.session.commit()
        enrollments = CfbEnrollment.query.all()
        weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
        in_play = attrition_rows(enrollments, weeks)[-1]
        assert (in_play.alive_entering, in_play.lost_life, in_play.cut, in_play.alive_after) == (3, 0, 0, 3)
        assert field_delta_line(enrollments, weeks) is None
        w3.is_complete = True
        for e in enrollments:
            _outcome(w3, e.user, lives=e.lives_remaining, eliminated=e.is_eliminated,
                     lost=e.user_id == cy.user_id)
        db.session.commit()
        on_record = attrition_rows(enrollments, weeks)[-1]
        assert (on_record.alive_entering, on_record.lost_life, on_record.cut, on_record.alive_after) == (3, 0, 0, 3)
        assert on_record.out == 1


def test_the_delta_line_for_the_lounge(app, season):
    from games.cfb.models import CfbEnrollment, CfbWeek
    with app.app_context():
        enrollments = CfbEnrollment.query.all()
        weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()[:2]
        assert field_delta_line(enrollments, weeks) == 'One fewer than last week.'
        assert field_delta_line(enrollments, weeks[:1]) is None


def test_the_delta_line_counts_a_second_week_in_play(app, season):
    """Week 1 complete, Week 2 past its deadline and still in play: Cy's
    settled loss already cut him, so the line reads against Week 1."""
    from games.cfb.models import CfbEnrollment, CfbWeek
    with app.app_context():
        w2 = CfbWeek.query.filter_by(week_number=2).one()
        w2.is_complete = False
        CfbWeekOutcome.query.filter_by(week_id=w2.id).delete()
        db.session.commit()
        enrollments = CfbEnrollment.query.all()
        weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()[:2]
        assert field_delta_line(enrollments, weeks) == 'One fewer than last week.'


def test_the_field_page(app, client, season):
    page = client.get('/cfb/field').get_data(as_text=True)
    assert 'The Field' in page
    assert 'Georgia' in page and 'Ohio State' in page
    assert 'Ann' in page                                 # a survivor named on the board
    assert 'rank' not in page.lower().replace('rankings', '')  # no rank movement surface
    assert '/cfb/player/' in page                        # names are doors


def test_the_field_before_any_week(app, client):
    with app.app_context():
        u = make_user('ann')
        make_enrollment(u)
        make_team('Georgia')
        db.session.commit()
    page = client.get('/cfb/field').get_data(as_text=True)
    assert 'The full field remains alive' in page


def test_the_lounge_who_is_left_door_opens_the_field():
    """The lounge's "The field" link under Who's Left leads to /cfb/field, not standings."""
    from pathlib import Path
    panel = Path(__file__).resolve().parent.parent / 'games/cfb/templates/cfb/lounge/_panel_live.html'
    assert "url_for('cfb.field') }}\">The field" in panel.read_text()
