"""The Club Desk's 12-state matrix (eng review 8A): the written spec of
who gets what.

Four Survivor states (not enrolled, eliminated, picked, owes) x three
Docket states (not enrolled, complete, incomplete), each run through the
three reminder slots (F, S, D) and the Tuesday Paper, with both games
anchoring and both slots F and S open to a rider. Every assertion is on
CAPTURED RENDERED letters (the desk's one send site patched), never a
mocked builder: the recipient, which game owns the subject, which sections
or rider the letter carries, and which flags latch afterwards.
"""
from unittest.mock import patch

import pytest

from extensions import db
from games.cfb.models import CfbWeek
from games.club_desk import run_desk, run_paper
from games.docket.models import DocketWeek
from tests._club_desk_fixtures import (
    D_AT,
    DOCKET_STATES,
    F_AT,
    PAPER_AT,
    S_AT,
    SURVIVOR_STATES,
    capture,
    paper_openers,
    seed,
)

SITE = 'https://cccfantasy.com'
STATES = [(s, d) for s in SURVIVOR_STATES for d in DOCKET_STATES]
CFB_SUBJECT = {'F': 'Pick due tomorrow: CFB Survivor, Week 4',
               'S': 'FINAL, 1 hour left: CFB Survivor, Week 4'}
DOCKET_SUBJECT = {'F': 'Sheet not finished: The Docket, Week 4',
                  'S': 'Closes tomorrow: The Docket, Week 4',
                  'D': 'Two hours left: The Docket, Week 4'}
CFB_TIER = {'F': 'warning', 'S': 'final'}
DOCKET_TIER = {'F': '48h', 'S': '24h', 'D': '2h'}
AT = {'F': F_AT, 'S': S_AT, 'D': D_AT}
RIDER_MARK = 'Also on your desk. The Docket:'


def _expect_slot(slot, survivor, docket_state):
    """(subject owner, rider present, latches) per the design's send rules."""
    owes_cfb = survivor == 'owes' and slot in ('F', 'S')
    owes_docket = docket_state == 'incomplete'
    latches = {}
    if owes_cfb:
        latches['cfb'] = CFB_TIER[slot]
    if owes_docket:
        latches['docket'] = DOCKET_TIER[slot]
    if owes_cfb:
        return 'cfb', owes_docket, latches
    if owes_docket:
        return 'docket', False, latches
    return None, False, latches


@pytest.mark.parametrize('slot', ['F', 'S', 'D'])
@pytest.mark.parametrize(('survivor', 'docket_state'), STATES)
def test_reminder_slot(app, slot, survivor, docket_state):
    app.config['SITE_URL'] = SITE
    seeded = seed(survivor, docket_state)
    owner, rider, latches = _expect_slot(slot, survivor, docket_state)

    sent, patcher = capture()
    with patcher, patch('games.cfb.services.reminders.send_push'), \
            patch('games.docket.services.reminders.send_push'):
        run = run_desk(AT[slot], anchors=('cfb', 'docket'), rides=('F', 'S'))

    assert run.exit_code == 0
    if owner is None:
        assert sent == []
    else:
        assert len(sent) == 1
        letter = sent[0]
        assert letter['to'] == 'member@test.com'
        expected = (CFB_SUBJECT if owner == 'cfb' else DOCKET_SUBJECT)[slot]
        assert letter['subject'] == expected
        assert letter['html'].count('class="cta"') == 1
        assert (RIDER_MARK in letter['plain']) is rider
        if rider:
            assert 'Open your sheet: https://cccfantasy.com/docket/' in letter['plain']
            assert letter['plain'].index('Miss the deadline') < \
                letter['plain'].index(RIDER_MARK)
        if owner == 'docket':
            assert 'Still open on your sheet' in letter['plain']

    cfb_week = db.session.get(CfbWeek, seeded.cfb.week4.id)
    docket_week = db.session.get(DocketWeek, seeded.docket.week4.id)
    assert cfb_week.last_reminder_type == latches.get('cfb')
    assert docket_week.last_reminder_tier == latches.get('docket')
    assert run.latched == latches


def _expect_paper(survivor, docket_state):
    """(subject, sections, latches) for the Paper in a week both games open
    and the Docket's previous week is not yet graded."""
    in_cfb = survivor != 'none'
    in_docket = docket_state != 'none'
    active = survivor in ('picked', 'owes')
    if not in_cfb and not in_docket:
        return None, (), {}
    if in_cfb and in_docket:
        latches = {'docket': 'picks_open_notified'}
        if active:
            latches['cfb'] = 'picks_open_notified'
        return ('The Morning Line, Week 4: Both boards are open',
                ('cfb', 'docket'), latches)
    if in_cfb:
        if not active:
            return None, (), {}         # a spectator alone gets no Paper
        return ('Picks are open: CFB Survivor, Week 4', ('cfb',),
                {'cfb': 'picks_open_notified'})
    return ('Picks are open: The Docket, Week 4', ('docket',),
            {'docket': 'picks_open_notified'})


@pytest.mark.parametrize(('survivor', 'docket_state'), STATES)
def test_paper(app, survivor, docket_state):
    app.config['SITE_URL'] = SITE
    seeded = seed(survivor, docket_state)
    subject, sections, latches = _expect_paper(survivor, docket_state)

    sent, patcher = capture()
    cfb_open, docket_open = paper_openers(seeded)
    with patcher, cfb_open, docket_open:
        run = run_paper(PAPER_AT)

    assert run.exit_code == 0
    assert set(run.opened) == {'cfb', 'docket'}
    if subject is None:
        assert sent == []
    else:
        assert len(sent) == 1
        letter = sent[0]
        assert letter['to'] == 'member@test.com'
        assert letter['subject'] == subject
        plain, html = letter['plain'], letter['html']
        assert ('CFB SURVIVOR' in plain.upper()) is ('cfb' in sections)
        assert ('THE DOCKET' in plain.upper()) is ('docket' in sections)
        if len(sections) == 2:
            assert html.count('class="cta"') == 0
            assert html.count('class="section-cta"') == \
                (2 if survivor != 'eliminated' else 1)
            assert 'background:#C9A227' not in html
            assert 'Last week is still being graded.' in plain
            if survivor == 'eliminated':
                # A spectator line has no deadline, so it renders last.
                assert plain.index('The Docket · Week 4') < \
                    plain.index('CFB Survivor · Week 4')
                assert 'Out after Week 3. 0 of 1 still alive.' in plain
                assert 'Survivor locks' not in plain
            else:
                assert plain.index('CFB Survivor · Week 4') < \
                    plain.index('The Docket · Week 4')
                assert 'Last week: Survived with Oregon. Two lives in hand. ' \
                       '1 of 1 still alive.' in plain
                assert 'Survivor locks: Saturday, Sep 26 · 11:00 AM CT' in plain
            assert 'The docket closes: Sunday, Sep 27 · 12:00 PM CT' in plain
        else:
            assert html.count('class="cta"') == 1
            assert 'class="section-cta"' not in html

    cfb_week = db.session.get(CfbWeek, seeded.cfb.week4.id)
    docket_week = db.session.get(DocketWeek, seeded.docket.week4.id)
    docket_prev = db.session.get(DocketWeek, seeded.docket.week3.id)
    assert cfb_week.picks_open_notified is ('cfb' in latches)
    assert docket_week.picks_open_notified is ('docket' in latches)
    assert docket_prev.record_notified is False      # never on an ungraded week
    assert run.latched == latches
