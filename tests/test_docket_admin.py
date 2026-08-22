"""The Docket admin desk (T9): the commissioner's three rulings.

Locks the binding rulings from the 2026-08-11 design SSoT — the Grading
Clarifications designation contract (enforced through the SAME
check_designation the deadline pass uses, never re-derived), D14's No
Contest auto-recalc, and D18's audited pre-deadline line correction with its
explicit pick re-snapshot — plus the gates that keep each ruling in its
window and the rule that a mail failure never unwinds a recorded ruling.
"""
from datetime import datetime

import pytest
from sqlalchemy import func, select

from extensions import db
from games.docket.models import (
    DocketGame,
    DocketLineCorrection,
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeekResult,
)
from games.docket.services import admin_ops
from games.docket.services.admin_ops import AdminOpError
from tests._docket_fixtures import (
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

BEFORE_DEADLINE = '2026-09-02T12:00:00'
AFTER_DEADLINE = '2026-09-05T16:30:00'
KICK_THU = datetime(2026, 9, 4, 0, 15)     # before the Saturday deadline
KICK_SAT = datetime(2026, 9, 5, 23, 30)    # after it


@pytest.fixture()
def week(app):
    return make_week(1)


@pytest.fixture()
def admin(app, client):
    user = make_user('clerk', is_admin=True)
    db.session.commit()
    login(client, user)
    return user


def _sat(week, **kw):
    kw.setdefault('kickoff', KICK_SAT)
    return make_game(week, **kw)


def _no_mail(monkeypatch):
    """Capture sends without touching SMTP. Patched at the read site."""
    sent = []

    def fake(to_addr, subject, plain, html=None):
        sent.append((to_addr, subject, plain, html))
        return True

    monkeypatch.setattr(
        'games.docket.services.notifications.send_platform_email', fake)
    return sent


# ── Tiebreaker designation ───────────────────────────────────────────────

def test_designation_sets_the_case(monkeypatch, week):
    game = _sat(week, home='Notre Dame', away='Wisconsin')
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    result = admin_ops.designate_tiebreaker(week, game.id)

    assert result['changed'] is True
    assert week.tiebreaker_game_id == game.id
    assert result['cleared'] == 0 and result['notified'] == 0


def test_designation_refuses_a_kickoff_before_the_deadline(monkeypatch, week):
    """A case already in progress at the deadline would let its pickers
    predict a score they can see."""
    early = make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.designate_tiebreaker(week, early.id)
    assert err.value.code == 'unsound'
    assert any('before the' in p for p in err.value.problems)
    db.session.rollback()
    assert week.tiebreaker_game_id is None


def test_designation_refuses_a_case_with_no_locked_total(monkeypatch, week):
    game = _sat(week, total=None)
    game.total_book = None
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.designate_tiebreaker(week, game.id)
    assert err.value.code == 'unsound'
    db.session.rollback()
    assert week.tiebreaker_game_id is None


def test_designation_refuses_a_case_from_another_docket(monkeypatch, week):
    other = make_week(2)
    stranger = make_game(other, kickoff=datetime(2026, 9, 12, 23, 30))
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.designate_tiebreaker(week, stranger.id)
    assert err.value.code == 'invalid'


def test_designation_is_refused_once_the_docket_closes(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.designate_tiebreaker(week, game.id)
    assert err.value.code == 'deadline_passed'


def test_redesignation_clears_predictions_and_notifies(monkeypatch, week):
    """Grading Clarifications: predictions clear to the NEW case's default
    and players are told they may resubmit."""
    first = _sat(week, home='Home A', away='Away A')
    second = _sat(week, home='Home B', away='Away B')
    player = make_user('predictor')
    make_enrollment(player)
    db.session.commit()
    db.session.add(DocketTiebreakerPrediction(
        user_id=player.id, week_id=week.id, prediction_tenths=515))
    week.tiebreaker_game_id = first.id
    db.session.commit()
    sent = _no_mail(monkeypatch)
    at(monkeypatch, BEFORE_DEADLINE)

    result = admin_ops.designate_tiebreaker(week, second.id)

    assert result['cleared'] == 1
    assert result['notified'] == 1
    assert db.session.scalar(
        select(func.count()).select_from(DocketTiebreakerPrediction)) == 0
    assert 'tiebreaker case changed' in sent[0][1]


def test_designation_refuses_a_thrown_out_case(monkeypatch, week):
    """The form hides these, but the form is not the guard: check_designation
    tests the total and the kickoff, never no_contest, so a stale form or a
    direct POST would land the tiebreaker on a void case."""
    game = _sat(week)
    game.no_contest = True
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.designate_tiebreaker(week, game.id)
    assert err.value.code == 'no_contest'
    assert week.tiebreaker_game_id is None


def test_redesignating_the_same_case_is_a_no_op(monkeypatch, week):
    game = _sat(week)
    week.tiebreaker_game_id = game.id
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    result = admin_ops.designate_tiebreaker(week, game.id)
    assert result['changed'] is False


def test_eligible_games_exclude_the_unqualified(monkeypatch, week):
    good = _sat(week)
    make_game(week, kickoff=KICK_THU)            # kicks off too early
    thrown_out = _sat(week)
    thrown_out.no_contest = True
    db.session.commit()

    assert [g.id for g in admin_ops.eligible_tiebreaker_games(week)] == [
        good.id]


# ── No Contest (D14) ─────────────────────────────────────────────────────

def test_no_contest_records_the_ruling_and_recalcs(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)

    result = admin_ops.rule_no_contest(week, game.id, 'Cancelled, lightning')

    assert game.no_contest is True
    assert game.nc_reason == 'Cancelled, lightning'
    # The week has had no deadline pass, so the recalc reports a wait rather
    # than raising — the readiness contract, untouched.
    assert result['grading']['status'] == 'not_ready'


def test_no_contest_requires_a_reason(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.rule_no_contest(week, game.id, '   ')
    assert err.value.code == 'reason_required'
    assert game.no_contest is False


def test_no_contest_refuses_a_second_ruling_and_clears_cleanly(
        monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)
    admin_ops.rule_no_contest(week, game.id, 'Postponed past the week')

    with pytest.raises(AdminOpError) as err:
        admin_ops.rule_no_contest(week, game.id, 'again')
    assert err.value.code == 'already_ruled'

    admin_ops.clear_no_contest(week, game.id)
    assert game.no_contest is False
    assert game.nc_reason is None

    with pytest.raises(AdminOpError) as err:
        admin_ops.clear_no_contest(week, game.id)
    assert err.value.code == 'not_ruled'


def test_no_contest_regrades_a_gradeable_week(monkeypatch, week):
    """The D14 contract end to end: the ruling itself writes new grades."""
    from games.docket.services.deadline_pass import run_deadline_pass

    games = [_sat(week, home=f'H{i}', away=f'A{i}',
                  home_spread=-(3.5 + i), total=40.5 + i)
             for i in range(9)]
    for game in games:
        game.home_score, game.away_score, game.is_final = 31, 17, True
    week.tiebreaker_game_id = games[0].id
    player = make_user('graded')
    make_enrollment(player)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)
    run_deadline_pass(1)
    assert db.session.scalar(
        select(func.count()).select_from(DocketWeekResult)) == 0

    result = admin_ops.rule_no_contest(week, games[5].id, 'Abandoned at half')

    assert result['grading']['status'] == 'ok'
    assert result['grading']['graded'] == 1
    assert db.session.scalar(
        select(func.count()).select_from(DocketWeekResult)
        .filter_by(user_id=player.id)) == 1


# ── D18 line correction ──────────────────────────────────────────────────

def test_line_correction_audits_resnapshots_and_notifies(monkeypatch, week):
    game = _sat(week, total=51.5)
    picker = make_user('picker')
    make_enrollment(picker)
    db.session.commit()
    db.session.add(DocketPick(
        user_id=picker.id, week_id=week.id, game_id=game.id,
        market='total', side='over', slot=1,
        line_value=51.5, book='draftkings'))
    db.session.commit()
    sent = _no_mail(monkeypatch)
    at(monkeypatch, BEFORE_DEADLINE)

    result = admin_ops.correct_line(week, game.id, 'total', '48.5',
                                    'draftkings', 'Imported total was wrong',
                                    picker.id)

    assert game.total_points == 48.5
    assert result['resnapshotted'] == 1
    assert result['notified'] == 1
    pick = db.session.scalars(select(DocketPick)).one()
    assert pick.line_value == 48.5, \
        'the pick grades on its own snapshot; the correction must reach it'
    audit = db.session.scalars(select(DocketLineCorrection)).one()
    assert (audit.old_value, audit.new_value) == (51.5, 48.5)
    assert audit.reason == 'Imported total was wrong'
    assert audit.picks_resnapshotted == 1
    assert 'A line was corrected' in sent[0][1]


def test_line_correction_leaves_the_other_market_alone(monkeypatch, week):
    game = _sat(week, home_spread=-3.5, total=51.5)
    picker = make_user('picker')
    db.session.commit()
    db.session.add(DocketPick(
        user_id=picker.id, week_id=week.id, game_id=game.id,
        market='spread', side='home', slot=1,
        line_value=-3.5, book='draftkings'))
    db.session.commit()
    _no_mail(monkeypatch)
    at(monkeypatch, BEFORE_DEADLINE)

    admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                           'total was wrong', picker.id)

    assert game.home_spread == -3.5
    assert db.session.scalars(select(DocketPick)).one().line_value == -3.5


def test_line_correction_requires_a_reason(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                               '', 1)
    assert err.value.code == 'reason_required'
    assert db.session.scalar(
        select(func.count()).select_from(DocketLineCorrection)) == 0


def test_line_correction_is_refused_after_the_deadline(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                               'too late', 1)
    assert err.value.code == 'deadline_passed'


def test_line_correction_is_refused_once_the_case_kicks_off(monkeypatch, week):
    """A Thursday case locks before the deadline; its picks are frozen, so
    the number under them may not move."""
    game = make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, '2026-09-04T01:00:00')

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                               'kicked off already', 1)
    assert err.value.code == 'game_locked'


def test_line_correction_refuses_an_unlocked_market(monkeypatch, week):
    game = _sat(week, total=None)
    game.total_book = None
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                               'nothing to correct', 1)
    assert err.value.code == 'not_locked'


def test_line_correction_refuses_junk_numbers(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    for value in ('', 'fifty', '0', '9999'):
        with pytest.raises(AdminOpError) as err:
            admin_ops.correct_line(week, game.id, 'total', value,
                                   'draftkings', 'typo', 1)
        assert err.value.code == 'invalid_number'


def test_line_correction_refuses_non_finite_numbers(monkeypatch, week):
    """float() accepts 'nan' and 'inf' happily; only the explicit check stops
    a non-finite number reaching the column."""
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    for value in ('nan', 'inf', '-inf'):
        with pytest.raises(AdminOpError) as err:
            admin_ops.correct_line(week, game.id, 'total', value,
                                   'draftkings', 'typo', 1)
        assert err.value.code == 'invalid_number', value
    assert db.session.get(DocketGame, game.id).total_points == 51.5


def test_line_correction_requires_a_usable_bookmaker(monkeypatch, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    for book in ('', '   ', 'x' * 41):
        with pytest.raises(AdminOpError) as err:
            admin_ops.correct_line(week, game.id, 'total', '48.5', book,
                                   'bad import', 1)
        assert err.value.code == 'book_required', repr(book)


def test_line_correction_refuses_the_number_already_on_file(monkeypatch, week):
    """No audit row for a correction that corrects nothing."""
    game = _sat(week, total=51.5)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '51.5',
                               game.total_book, 'no change', 1)
    assert err.value.code == 'no_change'
    assert db.session.scalar(
        select(func.count()).select_from(DocketLineCorrection)) == 0


def test_correcting_the_designated_total_must_keep_the_contract(
        monkeypatch, week):
    """The number range check is looser than the designation contract, so a
    total like 48.55 on the tiebreaker case would leave key 3 with no
    computable default. Refused, and the game keeps its old number."""
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)
    admin_ops.designate_tiebreaker(week, game.id)

    with pytest.raises(AdminOpError) as err:
        admin_ops.correct_line(week, game.id, 'total', '48.55', 'draftkings',
                               'fat fingered it', 1)

    assert err.value.code == 'unsound_designation'
    assert err.value.problems
    assert db.session.get(DocketGame, game.id).total_points == 51.5
    assert db.session.scalar(
        select(func.count()).select_from(DocketLineCorrection)) == 0


def test_correction_email_escapes_the_admin_reason(monkeypatch, week):
    """The reason is admin free text going straight into an HTML body."""
    game = _sat(week)
    picker = make_user('picker')
    db.session.commit()
    db.session.add(DocketPick(
        user_id=picker.id, week_id=week.id, game_id=game.id,
        market='total', side='over', slot=1,
        line_value=51.5, book='draftkings'))
    db.session.commit()
    sent = _no_mail(monkeypatch)
    at(monkeypatch, BEFORE_DEADLINE)

    admin_ops.correct_line(week, game.id, 'total', '48.5', 'draftkings',
                           '<script>alert(1)</script> & co', picker.id)

    _to, _subject, plain, html = sent[0]
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '&amp; co' in html
    # The plain-text part is not HTML and stays literal.
    assert '<script>alert(1)</script> & co' in plain
    # Intentional markup still renders as markup.
    assert '<strong>' in html


def test_a_failed_send_never_unwinds_the_ruling(monkeypatch, week):
    """send_platform_email returns False rather than raising; a mail outage
    must not roll back a correction already recorded."""
    game = _sat(week)
    picker = make_user('picker')
    db.session.commit()
    db.session.add(DocketPick(
        user_id=picker.id, week_id=week.id, game_id=game.id,
        market='total', side='over', slot=1,
        line_value=51.5, book='draftkings'))
    db.session.commit()
    monkeypatch.setattr(
        'games.docket.services.notifications.send_platform_email',
        lambda *a, **k: False)
    at(monkeypatch, BEFORE_DEADLINE)

    result = admin_ops.correct_line(week, game.id, 'total', '48.5',
                                    'draftkings', 'book had it wrong',
                                    picker.id)

    assert result['notified'] == 0
    assert db.session.scalar(
        select(func.count()).select_from(DocketLineCorrection)) == 1
    assert db.session.scalars(select(DocketPick)).one().line_value == 48.5


# ── The screens ──────────────────────────────────────────────────────────

def test_desk_lists_every_week(monkeypatch, client, admin, week):
    _sat(week)
    db.session.commit()
    html = client.get('/docket/admin/').data.decode()
    assert "The Clerk's Office" in html
    assert 'Week 1' in html
    assert 'None designated' in html


def test_designation_screen_posts_and_redirects(monkeypatch, client, admin,
                                                week):
    game = _sat(week, home='Notre Dame', away='Wisconsin')
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    resp = client.post('/docket/admin/week/1/tiebreaker',
                       data={'game_id': game.id, 'csrf_token': 'x'})

    assert resp.status_code == 302
    assert week.tiebreaker_game_id == game.id


def test_designation_screen_names_the_rule_default(monkeypatch, client, admin,
                                                   week):
    """The desk shows what the rule names today next to what is on file, so
    a commissioner reading the screen sees the same disagreement the lines
    run prints (week 1: the latest game on the slate)."""
    _sat(week, home='Notre Dame', away='Wisconsin')
    labor_day = make_game(week, kickoff=KICK_SAT.replace(day=7),
                          home='Florida State', away='SMU')
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    html = client.get('/docket/admin/week/1/tiebreaker').data.decode()

    assert 'By rule: SMU at Florida State' in html
    assert labor_day.total_points is not None  # eligible, so no caveat
    assert 'No case designated yet' in html


def test_designation_screen_reports_the_contract_problems(
        monkeypatch, client, admin, week):
    early = make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    resp = client.post('/docket/admin/week/1/tiebreaker',
                       data={'game_id': early.id, 'csrf_token': 'x'},
                       follow_redirects=True)

    assert 'does not satisfy the designation contract' in resp.data.decode()
    assert week.tiebreaker_game_id is None


def test_rulings_screen_throws_a_case_out(monkeypatch, client, admin, week):
    game = _sat(week)
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)

    resp = client.post('/docket/admin/week/1/rulings',
                       data={'game_id': game.id, 'reason': 'Cancelled',
                             'csrf_token': 'x'},
                       follow_redirects=True)

    assert db.session.get(DocketGame, game.id).no_contest is True
    assert 'thrown out' in resp.data.decode()


def test_lines_screen_corrects_and_reports(monkeypatch, client, admin, week):
    game = _sat(week)
    db.session.commit()
    _no_mail(monkeypatch)
    at(monkeypatch, BEFORE_DEADLINE)

    resp = client.post('/docket/admin/week/1/lines',
                       data={'game_id': game.id, 'market': 'total',
                             'value': '48.5', 'book': 'draftkings',
                             'reason': 'Bad import', 'csrf_token': 'x'},
                       follow_redirects=True)

    assert db.session.get(DocketGame, game.id).total_points == 48.5
    assert 'Line corrected' in resp.data.decode()


def test_admin_screens_refuse_an_unknown_week(client, admin):
    for path in ('/docket/admin/week/7/tiebreaker',
                 '/docket/admin/week/7/rulings',
                 '/docket/admin/week/7/lines'):
        resp = client.get(path)
        assert resp.status_code == 302
        assert '/docket/admin/' in resp.headers['Location']
