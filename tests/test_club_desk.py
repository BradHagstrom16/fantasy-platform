"""The Club Desk beyond the matrix (docs/designs/unified-email.md, step 4).

The reminder desk's send rules under failure and retry, the one-clock rule,
push, exit codes, the Paper's open order and isolation, the graded Docket
record line, the two dry runs, and the regressions that keep every legacy
announce path standalone. The 12-state matrix (tests/test_club_desk_matrix.py)
is the spec of who gets what; this file is everything around it.
"""
import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from markupsafe import Markup

from extensions import db
from games.cfb.models import CfbPick, CfbWeek
from games.cfb.services import desk as cfb_desk
from games.club_desk import ANCHOR_SLUGS, SLOTS, run_desk, run_paper
from games.docket.models import DocketPick, DocketWeek
from games.docket.services import desk as docket_desk
from games.docket.services.deadline_pass import run_deadline_pass
from games.docket.services.enrollment import roster_user_ids_as_of
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.opener import OpenResult, open_week
from games.docket.services.record import send_record_letters
from tests import _docket_fixtures as docket
from tests._club_desk_fixtures import (
    D_AT,
    F_AT,
    PAPER_AT,
    S_AT,
    add_member,
    capture,
    docket_open_fn,
    paper_openers,
    push_capture,
    seed,
)
from tests.test_email_letter import PALETTE

SITE = 'https://cccfantasy.com'
BOTH = ('cfb', 'docket')
RIDES = ('F', 'S')
NO_PUSH = (patch('games.cfb.services.reminders.send_push'),
           patch('games.docket.services.reminders.send_push'))


def _desk(now, **kwargs):
    kwargs.setdefault('anchors', BOTH)
    kwargs.setdefault('rides', RIDES)
    sent, patcher = capture(accept=kwargs.pop('accept', None))
    with patcher, NO_PUSH[0], NO_PUSH[1]:
        run = run_desk(now, **kwargs)
    return sent, run


def _flags(seeded):
    cfb_week = db.session.get(CfbWeek, seeded.cfb.week4.id)
    docket_week = db.session.get(DocketWeek, seeded.docket.week4.id)
    return cfb_week.last_reminder_type, docket_week.last_reminder_tier


# ── send rules under failure and retry ────────────────────────────────────

def test_second_firing_in_a_window_sends_nothing(app):
    """Sequential idempotence: the flag gate. Survivor's windows hold two
    hourly firings; after a delivered first, the second finds no anchor
    (the tier is sent), so a rider never joins it either and the Docket's
    48h waits for its own hour."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, run = _desk(F_AT)
    assert len(sent) == 1 and run.latched == {'cfb': 'warning', 'docket': '48h'}
    sent, run = _desk(F_AT + timedelta(hours=1))
    assert sent == [] and run.anchors == []
    assert _flags(seeded) == ('warning', '48h')


def test_a_ridden_tier_never_sends_standalone_later(app):
    """The pre-mark. The Docket rode Saturday's final (24h covered); its own
    24h window, two hours later, finds the tier already sent — even with
    the Docket anchoring alone, as the desk would if Survivor's week were
    gone."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, run = _desk(S_AT)
    assert len(sent) == 1 and run.latched == {'cfb': 'final', 'docket': '24h'}
    sent, run = _desk(S_AT + timedelta(hours=2), anchors=('docket',), rides=())
    assert sent == [] and run.anchors == []
    assert _flags(seeded) == ('final', '24h')


def test_dual_send_fails_docket_only_succeeds_survivor_does_not_latch(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    add_member(seeded, 'clerk', survivor='none', docket_state='incomplete')
    sent, run = _desk(F_AT, accept=lambda to: to != 'member@test.com')
    assert {m['to'] for m in sent} == {'member@test.com', 'clerk@test.com'}
    assert run.delivered == {'docket': 1}
    assert _flags(seeded) == (None, '48h')
    assert run.exit_code == 1            # an active anchor reached nobody


def test_anchor_retry_never_resends_the_rider(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('picked', 'incomplete')
    sent, run = _desk(F_AT)
    assert [m['subject'] for m in sent] == ['Sheet not finished: The Docket, Week 4']
    assert _flags(seeded) == (None, '48h')      # anchor had nobody: stays open
    # The member withdraws the pick; the anchor fires again in its window.
    db.session.delete(db.session.scalar(
        db.select(CfbPick).filter_by(week_id=seeded.cfb.week4.id)))
    db.session.commit()
    sent, run = _desk(F_AT)
    assert [m['subject'] for m in sent] == ['Pick due tomorrow: CFB Survivor, Week 4']
    assert 'Also on your desk' not in sent[0]['plain']
    assert _flags(seeded) == ('warning', '48h')


def test_rider_failure_degrades_to_anchor_only_and_latches_only_the_anchor(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    add_member(seeded, 'other', survivor='owes', docket_state='none')
    with patch('games.docket.services.reminders.sheet_state',
               side_effect=RuntimeError('sheet exploded')):
        sent, run = _desk(F_AT)
    assert {m['to'] for m in sent} == {'member@test.com', 'other@test.com'}
    assert all('Also on your desk' not in m['plain'] for m in sent)
    assert run.errors and 'sheet exploded' in run.errors[0]
    assert _flags(seeded) == ('warning', None)
    assert run.exit_code == 0


def test_mark_sent_never_regresses(app):
    seeded = seed('owes', 'incomplete')
    cfb_week, docket_week = seeded.cfb.week4, seeded.docket.week4
    cfb_desk.REMINDER.mark_sent(cfb_week, 'final')
    cfb_desk.REMINDER.mark_sent(cfb_week, 'warning')
    assert cfb_week.last_reminder_type == 'final'
    docket_desk.REMINDER.mark_sent(docket_week, '2h')
    docket_desk.REMINDER.mark_sent(docket_week, '48h')
    assert docket_week.last_reminder_tier == '2h'


def test_docket_only_week_sends_every_tier_standalone(app):
    """1A: with no Survivor week the Docket's 48h, 24h and 2h anchor their
    own letters, in order, each latching."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.cfb.week4.is_active = False
    db.session.commit()
    expected = [('2026-09-25T17:00:00+00:00', '48h', 'Sheet not finished'),
                ('2026-09-26T17:00:00+00:00', '24h', 'Closes tomorrow'),
                ('2026-09-27T15:00:00+00:00', '2h', 'Two hours left')]
    for iso, tier, subject in expected:
        sent, run = _desk(datetime.fromisoformat(iso))
        assert len(sent) == 1 and subject in sent[0]['subject'], tier
        assert run.skipped == {'cfb': 'no week to answer for'}
        assert _flags(seeded)[1] == tier


def test_two_anchors_at_once_nearest_deadline_owns_the_subject(app):
    """Survivor's warning and the Docket's 48h in the same firing: the
    nearer deadline (Survivor's Saturday) leads and the Docket rides F."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.cfb.week4.deadline = datetime(2026, 9, 26, 13, 0)   # T-25h = Fri noon CT
    db.session.commit()
    both_active = datetime(2026, 9, 25, 17, 0, tzinfo=UTC)
    sent, run = _desk(both_active)
    assert [m['subject'] for m in sent] == ['Pick due tomorrow: CFB Survivor, Week 4']
    assert 'Also on your desk. The Docket:' in sent[0]['plain']
    assert _flags(seeded) == ('warning', '48h')

    # Without the ride, both anchor standalone in the same firing.
    for week, attr in ((seeded.cfb.week4, 'last_reminder_type'),
                       (seeded.docket.week4, 'last_reminder_tier')):
        setattr(week, attr, None)
    db.session.commit()
    sent, run = _desk(both_active, rides=())
    assert sorted(m['subject'] for m in sent) == [
        'Pick due tomorrow: CFB Survivor, Week 4',
        'Sheet not finished: The Docket, Week 4']
    assert _flags(seeded) == ('warning', '48h')


def test_anchor_cfb_never_leads_a_docket_tier(app):
    """5A."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, run = _desk(D_AT, anchors=('cfb',))
    assert sent == [] and _flags(seeded) == (None, None)
    assert run.skipped == {} and run.anchors == []


def test_ride_f_only_drops_the_rider_on_the_final_tier(app):
    """3A."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, run = _desk(S_AT, rides=('F',))
    assert [m['subject'] for m in sent] == ['FINAL, 1 hour left: CFB Survivor, Week 4']
    assert 'Also on your desk' not in sent[0]['plain']
    assert _flags(seeded) == ('final', None)


HIDDEN_CLOCKS = (
    'games.cfb.utils.get_current_time',
    'games.cfb.services.reminders.get_current_time',
    'games.docket.utils.now_utc',
    'games.docket.services.picks.now_utc',
    'games.docket.services.record.now_utc',
)


def _no_clock():
    return [patch(target, side_effect=AssertionError(f'{target} read a clock'))
            for target in HIDDEN_CLOCKS]


def test_no_hidden_clock_read_during_a_desk_run(app):
    """7A: with an explicit ``now`` nothing reached from the desk reads a
    clock, which is what makes a production dry run truthful."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    patches = _no_clock()
    for p in patches:
        p.start()
    try:
        sent, run = _desk(F_AT)
        assert len(sent) == 1 and 'Also on your desk' in sent[0]['plain']
        sent, run = _desk(D_AT)
        assert len(sent) == 1
        cfb_open, docket_open = paper_openers(seeded)
        with cfb_open, docket_open:
            paper = run_paper(PAPER_AT, dry_run=True)
        assert len(paper.composed) == 1
    finally:
        for p in patches:
            p.stop()


def test_push_fires_both_tags_with_mail_up_and_down(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    pushes, (cfb_push, docket_push) = push_capture()
    sent, patcher = capture()
    with patcher, cfb_push, docket_push:
        run = run_desk(F_AT, anchors=BOTH, rides=RIDES)
    assert sorted(pushes) == [('cfb-w4-nag', [seeded.user.id]),
                              ('docket-w4-nag', [seeded.user.id])]
    assert run.exit_code == 0

    for week, attr in ((seeded.cfb.week4, 'last_reminder_type'),
                       (seeded.docket.week4, 'last_reminder_tier')):
        setattr(week, attr, None)
    db.session.commit()
    pushes.clear()
    sent, patcher = capture(accept=lambda to: False)
    with patcher, cfb_push, docket_push:
        run = run_desk(F_AT, anchors=BOTH, rides=RIDES)
    assert sorted(pushes) == [('cfb-w4-nag', [seeded.user.id]),
                              ('docket-w4-nag', [seeded.user.id])]
    assert run.exit_code == 1 and _flags(seeded) == (None, None)


def test_exit_codes_out_of_season_and_not_imported(app):
    app.config['SITE_URL'] = SITE
    july = datetime(2026, 7, 4, 15, 0, tzinfo=UTC)
    sent, run = _desk(july)
    assert run.exit_code == 1 and run.skipped == {
        'cfb': 'no week to answer for', 'docket': 'no week to answer for'}
    sent, run = _desk(july, scheduled=True)
    assert run.exit_code == 0
    # In season, the Docket week not imported and no Survivor week open.
    sent, run = _desk(F_AT, scheduled=True)
    assert run.exit_code == 0 and sent == []


def test_member_who_picks_between_firings_gets_no_second_nag(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'complete')
    sent, run = _desk(S_AT)
    assert len(sent) == 1
    db.session.add(CfbPick(user_id=seeded.user.id, week_id=seeded.cfb.week4.id,
                           team_id=seeded.cfb.utah.id))
    db.session.commit()
    sent, run = _desk(S_AT + timedelta(minutes=30))
    assert sent == [] and run.anchors == []


def test_covers_only_within_six_hours_of_the_docket_tier(app):
    seeded = seed('owes', 'incomplete')
    week = seeded.docket.week4
    covers = docket_desk.REMINDER.covers
    assert covers('F', week, F_AT) == '48h'
    assert covers('S', week, S_AT) == '24h'
    assert covers('F', week, F_AT - timedelta(hours=7)) is None
    assert covers('S', week, S_AT - timedelta(hours=7)) is None
    assert covers('D', week, D_AT) is None
    assert covers('F', week, D_AT + timedelta(hours=3)) is None   # closed
    assert cfb_desk.REMINDER.covers('D', seeded.cfb.week4, D_AT) is None


def test_dry_run_sends_nothing_and_writes_nothing(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.docket_enrollment.has_paid = False
    db.session.commit()
    boom = patch('games.club_desk.send_platform_email',
                 side_effect=AssertionError('a dry run sent mail'))
    pushes, (cfb_push, docket_push) = push_capture()
    with boom, cfb_push, docket_push:
        run = run_desk(F_AT, anchors=BOTH, rides=RIDES, dry_run=True)
        assert len(run.composed) == 1 and run.composed[0].rider == 'docket'
        assert run.latched == {'cfb': 'warning', 'docket': '48h'}
        assert not db.session.dirty and not db.session.new
        assert _flags(seeded) == (None, None) and pushes == []

        cfb_open, docket_open = paper_openers(seeded)
        with cfb_open as cfb_mock, docket_open as docket_mock:
            paper = run_paper(PAPER_AT, dry_run=True)
        assert cfb_mock.call_count == 0 and docket_mock.call_count == 0
        assert len(paper.composed) == 1
        assert paper.announced == {'docket': False, 'cfb': False}
        assert not db.session.dirty and not db.session.new
    assert db.session.get(CfbWeek, seeded.cfb.week4.id).picks_open_notified is False
    assert db.session.get(DocketWeek, seeded.docket.week4.id).picks_open_notified is False


def test_dry_run_still_composes_an_announced_week(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.cfb.week4.picks_open_notified = True
    seeded.docket.week4.picks_open_notified = True
    db.session.commit()
    cfb_open, docket_open = paper_openers(seeded)
    with cfb_open, docket_open:
        paper = run_paper(PAPER_AT, dry_run=True)
    assert paper.announced == {'docket': True, 'cfb': True}
    assert len(paper.composed) == 1


# ── the Paper ─────────────────────────────────────────────────────────────

def _paper(seeded, *, cfb_open=None, docket_open=None):
    default_cfb, default_docket = paper_openers(seeded)
    sent, patcher = capture()
    with patcher, (cfb_open or default_cfb), (docket_open or default_docket):
        run = run_paper(PAPER_AT)
    return sent, run


def test_paper_one_open_is_that_games_own_letter(app):
    """The Docket's opener returns nothing (odds down at 06:15): a dual
    member gets Survivor's own letter, and the Docket's 07:00 path is left
    to announce standalone."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, run = _paper(seeded, docket_open=patch(
        'games.docket.services.desk._open_by_number',
        return_value=OpenResult(summary={'status': 'error', 'errors': ['x']},
                                week=seeded.docket.week4, rule_outcome=None,
                                problems=(), announced=0)))
    assert set(run.opened) == {'cfb'}
    assert [m['subject'] for m in sent] == ['Picks are open: CFB Survivor, Week 4']
    assert 'Last week: Survived with Oregon.' in sent[0]['plain']
    assert 'The Docket' not in sent[0]['plain']
    assert db.session.get(DocketWeek, seeded.docket.week4.id).picks_open_notified is False


def test_paper_partial_docket_import_is_not_announced(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('none', 'incomplete')
    sent, run = _paper(seeded, docket_open=patch(
        'games.docket.services.desk._open_by_number',
        return_value=OpenResult(summary={'status': 'partial', 'errors': ['nfl']},
                                week=seeded.docket.week4, rule_outcome=None,
                                problems=(), announced=0)))
    assert 'docket' not in run.opened and sent == []
    assert db.session.get(DocketWeek, seeded.docket.week4.id).picks_open_notified is False


def test_paper_latch_already_set_by_a_retry_path_means_no_second_opener(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.cfb.week4.picks_open_notified = True      # the 08:00 retry got there
    db.session.commit()
    sent, run = _paper(seeded)
    assert set(run.opened) == {'docket'}
    assert [m['subject'] for m in sent] == ['Picks are open: The Docket, Week 4']
    assert 'CFB Survivor' not in sent[0]['plain']


def test_paper_docket_opens_first_and_a_cfb_failure_cannot_block_it(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    order = []
    real_docket_open = docket_open_fn(seeded)

    def docket_side(number, **kwargs):
        order.append('docket')
        return real_docket_open(number, **kwargs)

    def cfb_side(**kwargs):
        order.append('cfb')
        raise RuntimeError('odds hung')

    sent, run = _paper(
        seeded,
        cfb_open=patch('games.cfb.services.automation.run_spread_update',
                       side_effect=cfb_side),
        docket_open=patch('games.docket.services.desk._open_by_number',
                          side_effect=docket_side))
    assert order == ['docket', 'cfb']
    assert set(run.opened) == {'docket'}
    assert run.exit_code == 1 and 'odds hung' in run.errors[0]
    assert [m['subject'] for m in sent] == ['Picks are open: The Docket, Week 4']
    assert db.session.get(DocketWeek, seeded.docket.week4.id).picks_open_notified is True


def test_paper_carries_one_tab_strip_per_owed_game_in_section_order(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.cfb_enrollment.has_paid = False
    seeded.docket_enrollment.has_paid = False
    db.session.commit()
    sent, run = _paper(seeded)
    plain = sent[0]['plain']
    assert plain.count('Settle the tab.') == 2
    assert plain.index('CFB Survivor: the $25 entry is due') < \
        plain.index('The Docket: the $60 entry is due')
    assert plain.index('Open your sheet:') < plain.index('Settle the tab.')

    seeded.cfb_enrollment.has_paid = True
    db.session.commit()
    seeded.cfb.week4.picks_open_notified = False
    seeded.docket.week4.picks_open_notified = False
    db.session.commit()
    sent, run = _paper(seeded)
    assert sent[0]['plain'].count('Settle the tab.') == 1
    assert 'The Docket: the $60 entry is due' in sent[0]['plain']


def _grade_docket_week3(seeded, monkeypatch, *, wins_by_user):
    """A graded Docket Week 3: eight final cases the home side covers; each
    user's first ``wins`` slots on the home side. Real deadline pass and
    grading, driven through the docket clock seam."""
    week3 = seeded.docket.week3
    kick = datetime(2026, 9, 20, 18, 0)
    games = [docket.make_game(week3, kickoff=kick, home=f'Prev Home {i}',
                              away=f'Prev Away {i}', total=40.5 + i)
             for i in range(8)]
    for game in games:
        game.home_score, game.away_score, game.is_final = 31, 17, True
    week3.tiebreaker_game_id = games[0].id
    for user, wins in wins_by_user.items():
        for slot in range(1, 9):
            db.session.add(DocketPick(
                user_id=user.id, week_id=week3.id, game_id=games[slot - 1].id,
                market='spread', side='home' if slot <= wins else 'away',
                slot=slot, is_best=(slot == 1), line_value=-3.5,
                book='draftkings'))
    db.session.commit()
    docket.at(monkeypatch, '2026-09-20T17:30:00')
    run_deadline_pass(3)
    graded = try_grade_week(week3.id,
                            user_ids=roster_user_ids_as_of(week3.deadline_at))
    assert graded['status'] == 'ok', graded
    return week3


def test_paper_docket_line_reads_the_record_and_latches_it(app, monkeypatch):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    dana = add_member(seeded, 'dana', survivor='none', docket_state='complete',
                      display_name='Dana Whitfield')
    week3 = _grade_docket_week3(seeded, monkeypatch,
                                wins_by_user={seeded.user: 6, dana: 7})
    sent, run = _paper(seeded)
    by_to = {m['to']: m for m in sent}
    member = by_to['member@test.com']['plain']
    assert ('Last week: 6 wins, 2 losses, 7 points. 2nd of 2 sheets. '
            'Dana Whitfield went 7-1 and takes the $20 weekly purse.') in member
    # The preheader hook follows section order: nearest deadline first.
    assert 'You survived with Oregon and went 6-2.' in by_to['member@test.com']['html']
    assert ('Last week: 7 wins, 1 loss, 8 points. 1st of 2 sheets. '
            'You went 7-1 and take the $20 weekly purse.') in by_to['dana@test.com']['plain']
    assert db.session.get(DocketWeek, week3.id).record_notified is True
    assert run.latched == {'docket': 'picks_open_notified', 'docket-record': 3,
                           'cfb': 'picks_open_notified'}

    # The record letter reads the same facts: the two can never disagree.
    records, patcher = capture('games.docket.services.notifications.send_platform_email')
    week3.record_notified = False
    db.session.commit()
    with patcher:
        send_record_letters(week3, now=PAPER_AT)
    record = {m['to']: m for m in records}['member@test.com']['plain']
    assert 'Week 3: 6-2 · 7 points' in record
    assert 'On the week: 2nd of 2' in record
    assert 'Top sheet: Dana Whitfield, 7-1' in record
    assert 'Weekly purse: $20 to Dana Whitfield' in record


def test_paper_first_week_says_nothing_about_last_week(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('none', 'incomplete')
    seeded.docket.week4.week_number = 1      # the Docket's opening week
    seeded.cfb.week4.is_active = False
    db.session.delete(seeded.docket.week3)
    db.session.commit()
    default_cfb, _ = paper_openers(seeded)
    week = seeded.docket.week4

    def fake_open(number, *, announce=True, **_):
        return OpenResult(summary={'status': 'ok'}, week=week,
                          rule_outcome=None, problems=(), announced=0)

    sent, run = _paper(seeded, docket_open=patch(
        'games.docket.services.desk._open_by_number', side_effect=fake_open))
    assert 'Last week' not in sent[0]['plain']
    assert 'File eight sides' in sent[0]['plain']


def test_paper_letters_obey_the_letter_rules(app):
    """The copy and material rules of tests/test_email_letter.py, on the
    two-section Paper and the merged nag."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    seeded.docket_enrollment.has_paid = False
    db.session.commit()
    sent, run = _paper(seeded)
    nag, _ = _desk(S_AT)
    hexes = re.compile(r'(?<!&)#[0-9A-Fa-f]{3,8}\b')
    for m in (sent[0], nag[0]):
        text = Markup(m['html']).striptags()
        for part in (m['subject'], m['plain'], text):
            assert '—' not in part and 'CDT' not in part and 'CST' not in part
        found = set()
        for style in re.findall(r'style="([^"]*)"', m['html']):
            found.update(h.upper() for h in hexes.findall(style))
        assert found <= PALETTE, sorted(found - PALETTE)
        assert 'width="560"' in m['html'] and m['html'].count('<img ') == 1
    assert len(sent[0]['subject']) <= 50
    assert sent[0]['subject'] == 'The Morning Line, Week 4: Both boards are open'
    assert 'You went' not in sent[0]['html']      # Docket Week 3 ungraded here
    assert 'You survived with Oregon.' in sent[0]['html']   # the preheader hook
    assert len(nag[0]['subject']) <= 45


# ── the legacy announce paths stay standalone ─────────────────────────────

def test_friday_spreads_and_the_retry_still_announce_standalone(app):
    """When the Paper did not announce Survivor (the Docket-only Paper
    above), ``run_spread_update()`` with its default still does."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'none')
    seeded.cfb.week4.picks_open_notified = True   # pretend: Paper never ran
    seeded.cfb.week4.picks_open_notified = False
    db.session.commit()
    from games.cfb.services.automation import run_spread_update
    legacy, patcher = capture('games.cfb.services.reminders.send_platform_email')
    with patcher, patch('games.cfb.services.automation._fetch_and_lock_lines',
                        return_value=(0, 'n/a')), \
            patch('games.cfb.services.automation.send_platform_email',
                  return_value=True):
        result = run_spread_update()
    assert result['status'] == 'updated'
    assert [m['subject'] for m in legacy] == ['Picks are open: CFB Survivor, Week 4']
    assert db.session.get(CfbWeek, seeded.cfb.week4.id).picks_open_notified is True


def test_docket_lines_still_announces_standalone_after_a_partial_paper(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('none', 'incomplete')
    legacy, patcher = capture('games.docket.services.notifications.send_platform_email')
    with patcher:
        result = open_week(4, announce=True,
                           importer=lambda n, **_: {'status': 'ok'})
    assert result.announced == 1
    assert [m['subject'] for m in legacy] == ['Picks are open: The Docket, Week 4']
    assert db.session.get(DocketWeek, seeded.docket.week4.id).picks_open_notified is True


# ── the CLI ───────────────────────────────────────────────────────────────

def test_cli_desk_dry_run_prints_the_plan(app):
    app.config['SITE_URL'] = SITE
    seed('owes', 'incomplete')
    runner = app.test_cli_runner()
    with patch('games.club_desk.send_platform_email',
               side_effect=AssertionError('sent')):
        result = runner.invoke(args=['club', 'desk', '--dry-run',
                                     '--now', '2026-09-25T10:00',
                                     '--anchor', 'cfb,docket', '--ride', 'F,S'])
    assert result.exit_code == 0, result.output
    assert 'anchor: cfb/warning (slot F' in result.output
    assert '+ rider docket/48h' in result.output
    assert 'Member One <member@test.com>' in result.output
    assert 'would latch: cfb=warning, docket=48h' in result.output

    result = runner.invoke(args=['club', 'desk', '--dry-run', '--ride', 'X'])
    assert result.exit_code == 1 and 'unknown slot' in result.output
    assert set(SLOTS) == {'F', 'S', 'D'}


def test_cli_desk_refuses_an_unknown_anchor(app):
    """A typo on the unit's ExecStart line (``--anchor cfb,dockett``) would
    otherwise drop the Docket from every firing with exit 0."""
    seed('owes', 'incomplete')
    runner = app.test_cli_runner()
    with patch('games.club_desk.send_platform_email',
               side_effect=AssertionError('sent')):
        result = runner.invoke(args=['club', 'desk', '--dry-run',
                                     '--now', '2026-09-25T10:00',
                                     '--anchor', 'cfb,dockett'])
    assert result.exit_code == 1
    assert "unknown game(s) ['dockett']; known: cfb, docket" in result.output
    assert '->' not in result.output
    assert set(ANCHOR_SLUGS) == {'cfb', 'docket'}


def test_cli_live_output_names_members_by_id(app):
    """The address is for the dry run's reader; a live run writes to the
    journal and names the member by id, as the desk's warnings do."""
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    sent, patcher = capture()
    with patcher:
        result = app.test_cli_runner().invoke(
            args=['club', 'desk', '--now', '2026-09-25T10:00',
                  '--anchor', 'cfb', '--ride', 'F'])
    assert result.exit_code == 0, result.output
    assert [m['to'] for m in sent] == ['member@test.com']
    assert f'-> Member One #{seeded.user.id}:' in result.output
    assert 'member@test.com' not in result.output


def test_cli_paper_dry_run_prints_the_plan(app):
    app.config['SITE_URL'] = SITE
    seeded = seed('owes', 'incomplete')
    runner = app.test_cli_runner()
    cfb_open, docket_open = paper_openers(seeded)
    with cfb_open, docket_open, patch('games.club_desk.send_platform_email',
                                      side_effect=AssertionError('sent')):
        result = runner.invoke(args=['club', 'paper', '--dry-run',
                                     '--now', '2026-09-22T06:15'])
    assert result.exit_code == 0, result.output
    assert 'open: docket week 4' in result.output
    assert 'open: cfb week 4' in result.output
    assert 'record: docket week 3 (not graded yet)' in result.output
    assert 'The Morning Line, Week 4: Both boards are open' in result.output
    assert 'would send 1 letter(s)' in result.output


def test_cli_scheduled_out_of_season_exits_zero(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['club', 'desk', '--scheduled',
                                 '--now', '2026-07-04T10:00'])
    assert result.exit_code == 0, result.output
    result = runner.invoke(args=['club', 'desk', '--now', '2026-07-04T10:00'])
    assert result.exit_code == 1
    result = runner.invoke(args=['club', 'paper', '--scheduled', '--dry-run',
                                 '--now', '2026-07-07T06:15'])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('raw', ['not-a-date', '2026-13-01'])
def test_cli_rejects_a_bad_now(app, raw):
    result = app.test_cli_runner().invoke(args=['club', 'desk', '--dry-run',
                                                '--now', raw])
    assert result.exit_code == 1 and 'ISO 8601' in result.output
