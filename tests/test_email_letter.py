"""The Club Letter: one shell for every member email (ADR-058).

Two kinds of lock live here.

1. **The shell itself** (`utils/email_layout.py` + `templates/email/letter.j2`):
   autoescape is a property of the one template, the Block helpers escape their
   inputs, the plain part is generated from the same fields as the HTML, and
   the seal is an absolute, versioned PNG.

2. **Every in-scope letter, as actually sent.** The catalogue below drives the
   real send paths (patched at each read site, per the platform mocking
   convention) and asserts the copy + material rules on the RENDERED output:
   no em dashes, no emoji, "CT" never "CDT", a deadline fact wherever one
   exists, exactly one CTA, no side-stripes, no SVG images, no off-palette
   hex, 560px, the greeting policy, the subject grammar.

Plus the "no other shell" lock: a second `role="presentation"` / `<!DOCTYPE
html>` anywhere in Python source or an email template directory fails, so a
sixth hand-rolled shell cannot regrow (Golf's is allowlisted until its PR).

4. **The desk letter** (DESIGN.md "The desk letter"): the second shape, one
   letter for more than one game. Its blocks (`game_section`, `rider_block`)
   and the locks `render_letter` enforces on them: one CTA per section and no
   club-gold button beside a game button, sections in deadline order, club
   chrome only with two or more sections; a rider is one link in `notes`.
"""
import os
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from markupsafe import Markup, escape

from extensions import db
from games.cfb.services.game_logic import process_week_results
from games.cfb.services.reminders import (
    run_reminder_check,
    send_picks_open_email,
    send_weekly_recap_email,
)
from games.docket.models import DocketLineCorrection, DocketPick
from games.docket.services.deadline_pass import run_deadline_pass
from games.docket.services.enrollment import roster_user_ids_as_of
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.notifications import (
    notify_line_correction,
    notify_picks_open,
    notify_redesignation,
)
from games.docket.services.record import run_record_pass
from games.docket.services.reminders import run_reminder_pass
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket
from utils import email_layout
from utils.email_layout import (
    Block,
    Letter,
    Section,
    SectionBlock,
    game_section,
    items_block,
    paragraphs_block,
    render_letter,
    result_block,
    rider_block,
    seal_url,
    section_block,
    tab_block,
)

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / 'templates' / 'email' / 'letter.j2'
SITE = 'https://cccfantasy.com'

# The only hex literals a letter may carry (tokens.css mirrored). Anything
# else is drift: no Tailwind grays, no traffic-light reds/greens, no #000/#fff
# text, and no #8A849B (3.0:1 on bone; labels use --text-secondary instead).
PALETTE = {
    '#F3EFE6', '#FFFFFF', '#2A1150', '#C9A227', '#3A1D72', '#1C1730',
    '#E8E5F0', '#5A5470', '#1C0A3A', '#C5050C', '#A63446', '#006747',
}
ACCENTS = {'cfb': '#C5050C', 'docket': '#A63446', 'golf': '#006747'}

# Copy points that depend on the recipient: broadcasts never greet, personal
# mail greets with the display name.
BROADCASTS = {
    'cfb-picks-open', 'cfb-reminder-warning', 'cfb-reminder-final',
    'docket-picks-open', 'docket-reminder-48h', 'docket-reminder-24h',
    'docket-reminder-2h', 'docket-tiebreaker-changed', 'platform-announce',
    'golf-picks-open', 'golf-reminder-24h', 'golf-reminder-12h',
    'golf-reminder-1h',
}
PERSONAL = {
    'cfb-recap-survived', 'cfb-recap-eliminated', 'cfb-recap-no-pick',
    'docket-line-corrected', 'docket-record', 'platform-reset', 'golf-recap',
    'golf-recap-no-pick',
}
WITH_DEADLINE = {
    'cfb-picks-open', 'cfb-reminder-warning', 'cfb-reminder-final',
    'docket-picks-open', 'docket-reminder-48h', 'docket-reminder-24h',
    'docket-reminder-2h', 'golf-picks-open', 'golf-reminder-24h',
    'golf-reminder-12h', 'golf-reminder-1h',
}
GAME_OF = {
    'cfb-picks-open': 'cfb', 'cfb-reminder-warning': 'cfb',
    'cfb-reminder-final': 'cfb', 'cfb-recap-survived': 'cfb',
    'cfb-recap-eliminated': 'cfb', 'cfb-recap-no-pick': 'cfb',
    'docket-picks-open': 'docket', 'docket-reminder-48h': 'docket',
    'docket-reminder-24h': 'docket', 'docket-reminder-2h': 'docket',
    'docket-line-corrected': 'docket', 'docket-tiebreaker-changed': 'docket',
    'docket-record': 'docket',
    'golf-picks-open': 'golf', 'golf-reminder-24h': 'golf',
    'golf-reminder-12h': 'golf', 'golf-reminder-1h': 'golf',
    'golf-recap': 'golf', 'golf-recap-no-pick': 'golf',
    'platform-reset': None, 'platform-announce': None,
}

# CFB: Sat Jan 3 2026 11:00 CST (naive pool wall clock); the reminder
# instants are the exact T-25h / T-1h targets in UTC.
CFB_DEADLINE = datetime(2026, 1, 3, 11, 0)
CFB_WARNING_AT = '2026-01-02T16:00:00+00:00'
CFB_FINAL_AT = '2026-01-03T16:00:00+00:00'
CFB_DEADLINE_TEXT = 'Saturday, Jan 3 · 11:00 AM CT'
# Docket Week 1: Sun Sep 6 2026 12:00 CDT = 17:00 UTC.
DOCKET_DEADLINE_UTC = datetime(2026, 9, 6, 17, 0, tzinfo=UTC)
DOCKET_DEADLINE_TEXT = 'Sunday, Sep 6 · 12:00 PM CT'
# Golf: Thu Jun 4 2026 07:00, stored naive as league wall clock (CDT).
GOLF_DEADLINE = datetime(2026, 6, 4, 7, 0)
GOLF_DEADLINE_TEXT = 'Thursday, Jun 4 · 7:00 AM CT'
DEADLINE_TEXT_OF = {'cfb': CFB_DEADLINE_TEXT, 'docket': DOCKET_DEADLINE_TEXT,
                    'golf': GOLF_DEADLINE_TEXT}


def _text(html):
    """The words a member reads: tags and comments stripped, entities decoded."""
    return Markup(html).striptags()


def _capture(target):
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'plain': plain,
                      'html': html})
        return True

    return calls, patch(target, side_effect=fake)


# ═══════════════════════════════════════════════════════════════════════════
# 1. The shell
# ═══════════════════════════════════════════════════════════════════════════

def test_template_is_the_only_shell_and_autoescapes_itself():
    """Flask does not autoescape .j2; the guarantee is the tag in the file."""
    lines = [ln.strip() for ln in TEMPLATE.read_text().splitlines()
             if ln.strip()]
    assert lines[0] == '{% autoescape true %}'
    assert lines[-1] == '{% endautoescape %}'
    source = TEMPLATE.read_text()
    assert '{% extends' not in source and '{% include' not in source
    assert sorted(p.name for p in TEMPLATE.parent.iterdir()) == ['letter.j2']


def test_render_escapes_every_string_field_and_keeps_plain_raw(app):
    app.config['SITE_URL'] = SITE
    plain, html = render_letter(Letter(
        subject='<s>ubj', headline='<b>x</b>', eyebrow='<e>',
        greeting='<g>', lede=['<i>lede'], facts=[('<l>', '<v>', '<t>')],
        cta=('<c>', 'https://x/?a=1&b=2'), supporting=['<p>sup'],
        footer_note='<f>',
    ))
    for raw in ('<s>ubj', '<b>x</b>', '<e>', '<g>', '<i>lede', '<l>', '<v>',
                '<c>', '<p>sup', '<f>'):
        assert raw not in html, raw
        if raw != '<s>ubj':               # the subject is a header, not body
            assert raw in plain, raw
    assert '&lt;b&gt;x&lt;/b&gt;' in html
    assert '<title>&lt;s&gt;ubj</title>' in html
    assert 'href="https://x/?a=1&amp;b=2"' in html
    assert '&lt;T&gt;' in html          # the tag renders uppercased
    assert '(<t>)' in plain


def test_markup_lede_passes_through_but_plain_strips_it(app):
    """Intentional emphasis (Markup.format) renders; plain text never sees tags."""
    app.config['SITE_URL'] = SITE
    lede = Markup('<strong>{}</strong> moved to {}.').format('<A>', 'B')
    plain, html = render_letter(Letter(
        subject='s', headline='h', eyebrow='e', lede=[lede]))
    assert '<strong>&lt;A&gt;</strong> moved to B.' in html
    assert '<A> moved to B.' in plain
    assert '<strong>' not in plain


def test_block_helpers_escape_and_pair_plain_with_html(app):
    app.config['SITE_URL'] = SITE
    items = items_block(['<x>', 'two'], title='Still <open>')
    assert '&lt;x&gt;' in items.html and '<x>' not in items.html
    assert '&lt;open&gt;' in items.html
    assert items.plain == 'Still <open>:\n- <x>\n- two'

    paras = paragraphs_block('para one\nstill one\n\n<b>para two')
    assert 'para one<br>still one' in paras.html
    assert paras.html.count('para one') == 1
    assert '&lt;b&gt;para two' in paras.html and '<b>' not in paras.html
    assert paras.plain == 'para one\nstill one\n\n<b>para two'

    rows = result_block('Your <standing>', [('Lives', '1 of 2'), ('<R>', '3')])
    assert '&lt;standing&gt;' in rows.html and '&lt;R&gt;' in rows.html
    assert rows.plain == 'Your <standing>\nLives: 1 of 2\n<R>: 3'


def test_tab_block_is_a_text_strip_naming_the_game_never_a_second_cta():
    assert tab_block(None, 'cfb') is None
    nudge = {'entry_fee': 60, 'venmo_url': 'https://venmo.com/x?amount=60&note=n',
             'zelle_phone': '(212) 555-0123'}
    block = tab_block(nudge, 'docket')
    assert block.html.count('<a ') == 1 and 'class="cta"' not in block.html
    assert 'Settle the tab.' in block.html
    assert 'The Docket: the $60 entry is due' in block.html
    assert 'href="https://venmo.com/x?amount=60&amp;note=n"' in block.html
    assert 'color:#A63446' in block.html    # the Venmo link wears the accent
    assert block.plain.startswith('Settle the tab. The Docket: the $60 entry')
    assert 'https://venmo.com/x?amount=60&note=n' in block.plain
    assert '(212) 555-0123' in block.plain
    assert '—' not in block.plain and '—' not in block.html


def test_seal_url_is_absolute_png_with_a_cache_bust(app, monkeypatch):
    app.config['SITE_URL'] = SITE + '/'
    monkeypatch.setenv('ASSET_VERSION', 'abc123')
    email_layout._asset_version.cache_clear()
    try:
        assert seal_url() == f'{SITE}/static/img/logo/seal-email.png?v=abc123'
    finally:
        email_layout._asset_version.cache_clear()


def test_plain_text_follows_the_letter_order(app):
    app.config['SITE_URL'] = SITE
    plain, _ = render_letter(Letter(
        subject='s', headline='Picks are open', eyebrow='CFB Survivor · Week 1',
        game_slug='cfb', season=2026, lede=['The lines are set.'],
        facts=[('Deadline', CFB_DEADLINE_TEXT)],
        extras=[items_block(['one'], title='List')],
        cta=('Make your pick', f'{SITE}/cfb/pick/1'),
        supporting=['Each team once.'],
        notes=[items_block(['note'], title='Footnote')],
    ))
    marks = ['CFB Survivor · Week 1', 'Picks are open', 'The lines are set.',
             f'Deadline: {CFB_DEADLINE_TEXT}', 'List:\n- one',
             f'Make your pick: {SITE}/cfb/pick/1', 'Each team once.',
             'Footnote:\n- note', 'Corrupt Commish Club · cccfantasy.com',
             'Sent to you as a member of CFB Survivor 2026.']
    positions = [plain.index(m) for m in marks]
    assert positions == sorted(positions), plain


def test_more_than_three_facts_is_refused(app):
    """The fact block is a deadline card, not the hero-metric trio's cousin."""
    app.config['SITE_URL'] = SITE
    with pytest.raises(ValueError):
        render_letter(Letter(subject='s', headline='h', eyebrow='e',
                             facts=[('a', '1'), ('b', '2'), ('c', '3'),
                                    ('d', '4')]))


def test_platform_and_game_letters_wear_different_cta_fills(app):
    app.config['SITE_URL'] = SITE
    _, club = render_letter(Letter(subject='s', headline='h', eyebrow='e',
                                   cta=('Go', SITE)))
    assert 'background:#C9A227' in club and 'color:#1C0A3A' in club
    assert 'color:#5A5470' in club          # platform eyebrow is ink, not gold
    _, game = render_letter(Letter(subject='s', headline='h', eyebrow='e',
                                   game_slug='cfb', cta=('Go', SITE)))
    assert 'background:#C5050C' in game and 'background:#C9A227' not in game


# ═══════════════════════════════════════════════════════════════════════════
# 2. The catalogue: every in-scope letter, as sent
# ═══════════════════════════════════════════════════════════════════════════

def _platform_letters(app):
    out = {}
    user = cfb.make_user('reseeker')
    user.display_name = 'Re Seeker'
    db.session.commit()
    captured = {}

    def keep(to, subject, plain, html=None):
        captured.update(to=to, subject=subject, plain=plain, html=html)
        return True

    with patch('core.auth.routes.send_platform_email', side_effect=keep):
        app.test_client().post('/forgot-password',
                               data={'email': 'reseeker@test.com',
                                     'csrf_token': 'x'})
    assert captured, 'password-reset did not send an email'
    out['platform-reset'] = dict(captured)

    from core.admin.announce import render_announcement
    with app.test_request_context():
        plain, html = render_announcement(
            'Big news', 'Hello everyone.\n\nSee you Saturday.')
    out['platform-announce'] = {'subject': 'Big news', 'plain': plain,
                                'html': html}
    return out


def _cfb_letters(app):
    out = {}
    # Week 1: decided (away won). Three fates: survived, eliminated, no pick.
    week1 = cfb.make_week(1, deadline=CFB_DEADLINE)
    home, away = cfb.make_team('Home U'), cfb.make_team('Away St')
    cfb.make_game(week1, home, away, spread=-7.0, winner='away')
    survivor = cfb.make_user('survivor')
    cfb.make_enrollment(survivor, lives=2, display_name='Steady Eddie')
    doomed = cfb.make_user('doomed')
    cfb.make_enrollment(doomed, lives=1, display_name='Ghost Gary')
    ghost = cfb.make_user('ghost')
    ghost_enrollment = cfb.make_enrollment(ghost, lives=2)
    ghost_enrollment.has_paid = False
    # Picked at 06:00 CST on deadline day (naive UTC), i.e. before the
    # deadline: a manual pick, so the recap carries no AUTOPICK tag.
    picked_at = datetime(2026, 1, 3, 12, 0)
    cfb.make_pick(survivor, week1, away, created_at=picked_at)
    cfb.make_pick(doomed, week1, home, created_at=picked_at)
    db.session.commit()
    assert process_week_results(week1.id)['success'] is True

    target = 'games.cfb.services.reminders.send_platform_email'
    sent, patcher = _capture(target)
    with patcher:
        send_weekly_recap_email(week1.id)
    by_to = {m['to']: m for m in sent}
    out['cfb-recap-survived'] = by_to['survivor@test.com']
    out['cfb-recap-eliminated'] = by_to['doomed@test.com']
    out['cfb-recap-no-pick'] = by_to['ghost@test.com']

    # Week 2: open. Picks-open to everyone, then both reminder tiers.
    week2 = cfb.make_week(2, deadline=CFB_DEADLINE, is_active=True)
    db.session.commit()
    sent, patcher = _capture(target)
    with patcher:
        send_picks_open_email(week2.id)
    out['cfb-picks-open'] = {m['to']: m for m in sent}['ghost@test.com']

    for key, instant in (('cfb-reminder-warning', CFB_WARNING_AT),
                         ('cfb-reminder-final', CFB_FINAL_AT)):
        sent, patcher = _capture(target)
        with patcher, patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                              'CFB_FAKE_NOW': instant}):
            run_reminder_check()
        assert sent, key
        out[key] = sent[0]
    return out


def _docket_letters(app):
    out = {}
    week = docket.make_week(1)
    thu = docket.make_game(week, kickoff=datetime(2026, 9, 4, 0, 30),
                           home='Notre Dame', away='Wisconsin')
    sat = docket.make_game(week, kickoff=datetime(2026, 9, 5, 18, 0),
                           home='Florida State', away='SMU', total=51.5)
    user = docket.make_user('clerk')
    enrollment = docket.make_enrollment(user, display_name='Clerk of Court')
    enrollment.has_paid = False
    db.session.commit()

    target = 'games.docket.services.notifications.send_platform_email'
    sent, patcher = _capture(target)
    with patcher:
        notify_picks_open(week, [(user, enrollment)])
    out['docket-picks-open'] = sent[0]

    for tier, hours in (('48h', 48), ('24h', 24), ('2h', 2)):
        sent, patcher = _capture(target)
        with patcher:
            result = run_reminder_pass(
                week, now=DOCKET_DEADLINE_UTC - timedelta(hours=hours),
                user_ids=[user.id])
        assert result['status'] == 'sent', result
        out[f'docket-reminder-{tier}'] = sent[0]

    pick = DocketPick(user_id=user.id, week_id=week.id, game_id=sat.id,
                      market='total', side='over', slot=1,
                      line_value=48.5, book='fanduel')
    db.session.add(pick)
    db.session.commit()
    correction = DocketLineCorrection(
        game_id=sat.id, market='total', old_value=51.5, old_book='draftkings',
        new_value=48.5, new_book='fanduel', reason='Imported total was wrong',
        admin_user_id=user.id, picks_resnapshotted=1)
    sent, patcher = _capture(target)
    with patcher:
        notify_line_correction(correction, sat, [pick], week)
    out['docket-line-corrected'] = sent[0]

    sent, patcher = _capture(target)
    with patcher:
        notify_redesignation(week, sat, thu, [user])
    out['docket-tiebreaker-changed'] = sent[0]

    # The record: the week closes, every case finals, the deadline pass files
    # and freezes, the grade lands, and the daily scores run's record pass
    # mails the one member their 1-0 (the Over came home).
    for game in (thu, sat):
        game.home_score, game.away_score, game.is_final = 31, 27, True
    week.tiebreaker_game_id = sat.id
    db.session.commit()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'DOCKET_FAKE_NOW': '2026-09-06T17:30:00'}):
        run_deadline_pass(1)
        assert try_grade_week(
            week.id, user_ids=roster_user_ids_as_of(week.deadline_at)
        )['status'] == 'ok'
        sent, patcher = _capture(target)
        with patcher:
            run_record_pass()
    out['docket-record'] = sent[0]
    return out


def _golf_letters(app):
    from games.golf.services.reminders import (
        _reminder_letter as golf_reminder_letter,
    )
    from games.golf.services.reminders import (
        send_picks_open_email as golf_picks_open,
    )
    from games.golf.services.reminders import (
        send_results_recap_email as golf_recap,
    )
    from tests.test_golf_conformance import (
        _add_to_field,
        _make_enrollment,
        _make_pick,
        _make_player,
        _make_result,
        _make_tournament,
        _make_user,
    )

    out = {}
    app.config['SEASON_YEAR'] = 2026
    app.config['EMAIL_ADDRESS'] = 'commish@test.com'
    app.config['EMAIL_PASSWORD'] = 'x'
    member = _make_user('golfmember', display_name='Fairway Fred')
    _make_enrollment(member)
    ghost = _make_user('golfghost', display_name='Cart Path Carl')
    _make_enrollment(ghost)

    open_t = _make_tournament(name='The Memorial', status='upcoming')
    open_t.pick_deadline = GOLF_DEADLINE
    db.session.commit()
    target = 'games.golf.services.reminders.send_platform_email'
    sent, patcher = _capture(target)
    with patcher:
        golf_picks_open(open_t.id)
    out['golf-picks-open'] = sent[0]

    # Golf's reminder pass is gated on the real clock (no fake-now seam) and
    # a 50-player field, so the tiers render through the pure builder that
    # run_reminder_check itself calls.
    for window in ({'hours': 24, 'type': 'warning', 'countdown': '23 hours, 40 minutes'},
                   {'hours': 12, 'type': 'reminder', 'countdown': '11 hours, 40 minutes'},
                   {'hours': 1, 'type': 'final', 'countdown': '55 minutes'}):
        letter = golf_reminder_letter(
            tournament_name='The Memorial',
            deadline_short=GOLF_DEADLINE_TEXT,
            time_remaining=window['countdown'],
            purse=20_000_000,
            golfers_used=4,
            pick_url=f'{SITE}/golf/pick/{open_t.id}',
            window=window,
            season_year=2026)
        plain, html = render_letter(letter)
        out[f"golf-reminder-{window['hours']}h"] = {
            'subject': letter.subject, 'plain': plain, 'html': html}

    done_t = _make_tournament(name='The Memorial Finale', status='complete',
                              results_finalized=True)
    p1 = _make_player('GP1', 'Rory', 'McIlroy')
    p2 = _make_player('GP2', 'Jon', 'Rahm')
    _add_to_field(done_t, p1)
    _add_to_field(done_t, p2)
    _make_result(done_t, p1, earnings=1_500_000, final_position='1')
    pick = _make_pick(member, done_t, p1, p2)
    pick.active_player_id = p1.id
    pick.points_earned = 1_500_000
    db.session.commit()
    sent, patcher = _capture(target)
    with patcher:
        golf_recap(done_t.id)
    by_to = {m['to']: m for m in sent}
    out['golf-recap'] = by_to['golfmember@test.com']
    out['golf-recap-no-pick'] = by_to['golfghost@test.com']
    return out


@pytest.fixture()
def letters(app):
    """name -> {'subject', 'plain', 'html'} for every in-scope letter."""
    app.config['SITE_URL'] = SITE
    out = {}
    out.update(_platform_letters(app))
    out.update(_cfb_letters(app))
    out.update(_docket_letters(app))
    out.update(_golf_letters(app))
    assert set(out) == set(GAME_OF), sorted(set(GAME_OF) ^ set(out))
    return out


_URL = re.compile(r'https?://\S+')


def test_no_em_dashes_double_hyphens_or_emoji_anywhere(letters):
    """Copy rules, so URLs are exempt from the double-hyphen check: the
    reset letter carries a URLSafeTimedSerializer token, base64url with a
    signature that changes every second, and roughly one run in a hundred
    lands a '--' inside it (seen once in the 2026-09-07 full runs, never
    twice in a row)."""
    emoji = re.compile('[\U0001F000-\U0001FAFF☀-➿]')
    for name, m in letters.items():
        for part in (m['subject'], m['plain'], _text(m['html'])):
            assert '—' not in part, (name, part)
            assert '--' not in _URL.sub('', part), (name, part)
            assert not emoji.search(part), (name, part)
        assert '&mdash;' not in m['html'] and '&#8212;' not in m['html'], name


def test_deadlines_say_ct_and_lead_the_fact_block(letters):
    for name, m in letters.items():
        text = _text(m['html'])
        assert 'CDT' not in text and 'CST' not in text, name
        assert 'CDT' not in m['plain'] and 'CST' not in m['plain'], name
        if name in WITH_DEADLINE:
            expected = DEADLINE_TEXT_OF[GAME_OF[name]]
            assert f'Deadline: {expected}' in m['plain'], (name, m['plain'])
            assert '>Deadline<' in m['html'], name
            assert expected in text, name


def test_exactly_one_cta_and_the_plain_part_carries_its_url(letters):
    for name, m in letters.items():
        assert m['html'].count('class="cta"') == 1, name
        href = unescape(re.search(r'class="cta" href="([^"]+)"', m['html'])
                        .group(1))
        assert href.startswith(SITE), (name, href)
        assert href in m['plain'], (name, href)


def test_material_rules_on_rendered_html(letters):
    hexes = re.compile(r'(?<!&)#[0-9A-Fa-f]{3,8}\b')
    for name, m in letters.items():
        html = m['html']
        assert re.search(r'border-(left|right)\s*:\s*([2-9]|\d{2,})px',
                         html) is None, name
        assert '.svg' not in html, name
        assert re.search(r'(?<!&)#(000|fff)\b', html, re.I) is None, name
        found = set()
        for style in re.findall(r'style="([^"]*)"', html):
            found.update(h.upper() for h in hexes.findall(style))
        assert found <= PALETTE, (name, sorted(found - PALETTE))
        assert 'width="560"' in html and 'max-width:560px' in html, name
        assert 'width="600"' not in html, name
        assert html.count('<img ') == 1, name
        seal = re.search(
            rf'<img src="{re.escape(SITE)}/static/img/logo/seal-email\.png'
            r'\?v=[^"]+" width="56" height="56" alt="Corrupt Commish Club"',
            html)
        assert seal, name
        for needle in ('<!DOCTYPE html>', 'lang="en"', 'charset="UTF-8"',
                       'name="viewport"', 'name="color-scheme" content="light"',
                       f'<title>{escape(m["subject"])}</title>'):
            assert needle in html, (name, needle)
        assert html.count('fonts.googleapis.com') == 1, name
        assert '{% ' not in html and '{{' not in html, name


def test_letters_carry_their_own_accent_and_no_other(letters):
    for name, m in letters.items():
        slug = GAME_OF[name]
        html = m['html']
        if slug is None:
            assert not any(a in html for a in ACCENTS.values()), name
            assert 'background:#C9A227' in html, name
            continue
        assert ACCENTS[slug] in html, name
        for other, hexval in ACCENTS.items():
            if other != slug:
                assert hexval not in html, (name, other)
        assert 'background:#C9A227' not in html, name   # gold never fills a game CTA


def test_subject_grammar(letters):
    game_names = {'cfb': 'CFB Survivor', 'docket': 'The Docket',
                  'golf': 'Golf'}
    for name, m in letters.items():
        slug = GAME_OF[name]
        subject = m['subject']
        if slug is None:
            continue
        assert re.fullmatch(rf'[^:]+: {game_names[slug]}, .+', subject), \
            (name, subject)
        assert len(subject) <= 45, (name, subject, len(subject))
    assert letters['cfb-picks-open']['subject'] == \
        'Picks are open: CFB Survivor, Week 2'
    assert letters['docket-picks-open']['subject'] == \
        'Picks are open: The Docket, Week 1'
    assert letters['golf-picks-open']['subject'] == \
        'Picks are open: Golf, The Memorial'
    assert 'FINAL' in letters['cfb-reminder-final']['subject']
    assert "You've been eliminated" in letters['cfb-recap-eliminated']['subject']
    assert 'You survived' in letters['cfb-recap-survived']['subject']
    tiers = {letters[f'docket-reminder-{t}']['subject'] for t in ('48h', '24h', '2h')}
    assert len(tiers) == 3, tiers      # distinct, so Gmail never threads them
    assert letters['docket-record']['subject'] == \
        'Your record: The Docket, Week 1'


def test_greeting_policy(letters):
    for name in BROADCASTS:
        plain = letters[name]['plain']
        assert not re.search(r'(^|\n)Hi ', plain), (name, plain)
    assert 'Hi Steady Eddie,' in letters['cfb-recap-survived']['plain']
    assert 'Hi Ghost Gary,' in letters['cfb-recap-eliminated']['plain']
    assert 'Hi Clerk of Court,' in letters['docket-line-corrected']['plain']
    assert 'Hi Clerk of Court,' in letters['docket-record']['plain']
    assert 'Hi Fairway Fred,' in letters['golf-recap']['plain']
    assert 'Hi Re Seeker,' in letters['platform-reset']['plain']


def test_footer_names_the_membership(letters):
    for name, m in letters.items():
        assert 'Corrupt Commish Club · cccfantasy.com' in m['plain'], name
        assert m['html'].index('class="cta"') < m['html'].index('#1C0A3A; padding'), name
        slug = GAME_OF[name]
        if slug == 'cfb':
            line = 'Sent to you as a member of CFB Survivor 2026.'
        elif slug == 'docket':
            line = 'Sent to you as a member of The Docket 2026.'
        elif slug == 'golf':
            line = "Sent to you as a member of Golf Pick 'Em 2026."
        else:
            line = 'Sent to you as a member of the Corrupt Commish Club.'
        assert line in m['plain'] and line in _text(m['html']), name


def test_each_game_states_its_consequence_and_the_tab_names_its_game(letters):
    cfb_open = letters['cfb-picks-open']['plain']
    assert 'the Commish picks for you' in cfb_open
    assert 'Settle the tab. CFB Survivor: the $25 entry is due' in cfb_open
    docket_open = letters['docket-picks-open']['plain']
    assert 'filled for you from the locked lines' in docket_open
    assert 'A case locks at its own kickoff' in docket_open
    assert 'Settle the tab. The Docket: the $60 entry is due' in docket_open
    reminder = letters['docket-reminder-48h']['plain']
    assert 'Still open on your sheet:\n- Sides committed: 0 of 8.' in reminder
    assert '- No headliner named.\n- No combined-score number recorded.' in reminder
    golf_open = letters['golf-picks-open']['plain']
    assert 'Each golfer can be used once this season' in golf_open
    assert 'Your season\nSeason total: $0\nGolfers used: 0' in golf_open


def test_record_says_the_week_in_digits_and_the_docket_around_it(letters):
    record = letters['docket-record']['plain']
    assert 'The Docket · Week 1\nWeek 1: 1-0' in record
    # The one filed side became the auto-designated x2, so 1-0 scores 2.
    assert 'Week 1: 1-0 · 2 points\nOn the week: 1st of 1\nSeason: 1st · 2 points' in record
    assert 'Around the docket\nTop sheet: You, 1-0\nWeekly purse: $20 to you' in record
    assert 'The Week 2 docket opens Tuesday morning.' in record
    assert 'Hardest case' not in record


def test_recap_says_the_result_in_words(letters):
    survived = letters['cfb-recap-survived']
    assert 'Result: Survived' in survived['plain']
    assert 'Eliminated this week:\n- Ghost Gary' in survived['plain']
    eliminated = letters['cfb-recap-eliminated']
    assert 'Result: Lost a life' in eliminated['plain']
    assert 'You have been eliminated.' in eliminated['plain']
    no_pick = letters['cfb-recap-no-pick']
    assert 'Your pick: No pick: life lost' in no_pick['plain']
    for m in (survived, eliminated, no_pick):
        assert 'AUTOPICK' not in m['html']


# ═══════════════════════════════════════════════════════════════════════════
# 3. No other shell
# ═══════════════════════════════════════════════════════════════════════════

SHELL_MARKERS = ('role="presentation"', '<!DOCTYPE html>')
THE_SHELL = {'utils/email_layout.py', 'templates/email/letter.j2'}
# Hand-rolled shells still standing. Empty since the Golf migration; a new
# entry needs the same one-PR lifespan Golf's had (added with its reason,
# removed in the PR that migrates it).
LEGACY_SHELLS = set()
SKIP_DIRS = {'venv', '.git', '.claude', '.worktrees', 'migrations', 'docs',
             'node_modules', 'tests', 'static'}


def _candidate_files():
    """Every Python source file, plus every file in an email template dir."""
    for path in REPO.rglob('*'):
        rel = path.relative_to(REPO)
        if not path.is_file() or set(rel.parts) & SKIP_DIRS:
            continue
        if rel.parts[0] == 'games' and rel.parts[1] == 'worldcup':
            continue                                    # frozen archive
        in_email_dir = 'email' in rel.parts[:-1] and 'templates' in rel.parts
        if path.suffix == '.py' or in_email_dir:
            yield rel.as_posix(), path


def _files_with_shell_markers():
    return {
        rel for rel, path in _candidate_files()
        if any(marker in path.read_text(errors='ignore')
               for marker in SHELL_MARKERS)
    }


def test_no_other_shell_exists():
    others = _files_with_shell_markers() - THE_SHELL - LEGACY_SHELLS
    assert not others, (
        f'{sorted(others)} carry email-shell markup. Build a Letter and call '
        f'utils.email_layout.render_letter instead.')


def test_legacy_shell_allowlist_has_no_dead_entries():
    dead = LEGACY_SHELLS - _files_with_shell_markers()
    assert not dead, f'Migrated shells still allowlisted: {sorted(dead)}'


# ═══════════════════════════════════════════════════════════════════════════
# 4. The desk letter
# ═══════════════════════════════════════════════════════════════════════════

CT = ZoneInfo('America/Chicago')
SAT = datetime(2026, 9, 26, 11, 0, tzinfo=CT)
SUN = datetime(2026, 9, 27, 12, 0, tzinfo=CT)
SAT_TEXT = 'Saturday, Sep 26 · 11:00 AM CT'
SUN_TEXT = 'Sunday, Sep 27 · 12:00 PM CT'
DOCKET_NUDGE = {'entry_fee': 60, 'venmo_url': f'{SITE}/venmo?amount=60&note=n',
                'zelle_phone': '(312) 555-0142'}
RIDER_SENTENCE = ('three sides still to file. The docket closes Sun, Sep 27, '
                  '12:00 PM CT.')


def _survivor_section(**overrides):
    fields = {
        'lines': [Markup('Last week: <strong>Survived</strong> with Oregon. '
                         'Two lives in hand. 27 of 31 still alive.')],
        'deadline': SAT, 'deadline_label': 'Survivor locks',
        'button': 'Make your pick', 'url': f'{SITE}/cfb/', **overrides}
    return game_section('cfb', 'CFB Survivor · Week 4', fields.pop('lines'),
                        **fields)


def _docket_section(**overrides):
    fields = {
        'lines': ['Last week: 6-2, 7 points. 4th of 31 sheets. Dana Whitfield '
                  'went 7-1 and takes the $20 weekly purse.'],
        'deadline': SUN, 'deadline_label': 'The docket closes',
        'button': 'Open your sheet', 'url': f'{SITE}/docket/', **overrides}
    return game_section('docket', 'The Docket · Week 4', fields.pop('lines'),
                        **fields)


def _paper(**overrides):
    """The approved Variant-B Paper: club chrome, Survivor then Docket, one
    tab strip for the owed game, no club CTA."""
    return Letter(**{
        'subject': 'The Morning Line, Week 4: Both boards are open',
        'headline': 'Both boards are open',
        'eyebrow': 'The Morning Line · Week 4',
        'preheader': 'You went 6-2 and survived with Oregon',
        'lede': ['Last week is in the books and this week\u2019s lines are '
                 'posted.'],
        'extras': [_survivor_section(), _docket_section()],
        'notes': [tab_block(DOCKET_NUDGE, 'docket')],
        **overrides})


def _merged_reminder():
    """The merged Saturday nag: the anchor letter as sent today, plus the
    Docket rider as a footnote before the tab strip."""
    return Letter(
        subject='FINAL, two hours left: CFB Survivor, Week 4',
        headline='Final call: two hours left',
        eyebrow='CFB Survivor · Week 4', game_slug='cfb', season=2026,
        preheader='Deadline Sat, Sep 26, 11:00 AM CT.',
        lede=['Your Week 4 pick is not in and the deadline is about two '
              'hours away.'],
        facts=[('Deadline', 'Sat, Sep 26, 11:00 AM CT'), ('Lives', '2 of 2'),
               ('Cumulative spread', '18.5')],
        cta=('Make your pick', f'{SITE}/cfb/'),
        supporting=['Miss the deadline and the pool picks for you: the '
                    'biggest favorite you have not used.'],
        notes=[rider_block('docket', RIDER_SENTENCE, 'Open your sheet',
                           f'{SITE}/docket/'),
               tab_block({'entry_fee': 25, 'venmo_url': f'{SITE}/venmo',
                          'zelle_phone': '(312) 555-0142'}, 'cfb')],
    )


def _assert_material_rules(name, html, subject):
    """The same material rules the catalogue test applies, on a letter that
    has no send path yet (the desk composer lands in a later step)."""
    hexes = re.compile(r'(?<!&)#[0-9A-Fa-f]{3,8}\b')
    assert re.search(r'border-(left|right)\s*:\s*([2-9]|\d{2,})px',
                     html) is None, name
    assert '.svg' not in html, name
    assert re.search(r'(?<!&)#(000|fff)\b', html, re.I) is None, name
    found = set()
    for style in re.findall(r'style="([^"]*)"', html):
        found.update(h.upper() for h in hexes.findall(style))
    assert found <= PALETTE, (name, sorted(found - PALETTE))
    assert 'width="560"' in html and 'max-width:560px' in html, name
    assert html.count('<img ') == 1, name
    assert f'<title>{escape(subject)}</title>' in html, name
    assert '{% ' not in html and '{{' not in html, name
    text = _text(html)
    assert '—' not in text and 'CDT' not in text and 'CST' not in text, name


def test_game_section_escapes_and_pairs_plain_with_html(app):
    app.config['SITE_URL'] = SITE
    block = game_section('cfb', 'Title <t>', ['<i>line', Markup('<b>ok</b>')],
                         deadline=SAT, deadline_label='Locks <l>',
                         button='Go <b>', url='https://x/?a=1&b=2')
    assert isinstance(block, Block) and isinstance(block, SectionBlock)
    assert block.slug == 'cfb' and block.deadline == SAT and block.has_button
    for raw in ('<t>', '<i>line', '<l>', 'Go <b>'):
        assert raw not in block.html, raw
    assert '&lt;t&gt;' in block.html and '<b>ok</b>' in block.html
    assert 'href="https://x/?a=1&amp;b=2"' in block.html
    assert block.plain == (f'Title <t>\n<i>line\nok\nLocks <l>: {SAT_TEXT}\n'
                           f'Go <b>: https://x/?a=1&b=2')


def test_section_block_renders_a_section_dataclass(app):
    app.config['SITE_URL'] = SITE
    section = Section(slug='docket', title='The Docket · Week 4',
                      lines=['One line.'], deadline=SUN,
                      deadline_label='The docket closes',
                      button='Open your sheet', url=f'{SITE}/docket/',
                      nudge=DOCKET_NUDGE)
    block = section_block(section)
    assert block == _docket_section(lines=['One line.'])
    assert block.deadline == SUN and block.slug == 'docket'
    assert 'Settle the tab' not in block.html    # the nudge is the composer's


def test_game_section_wears_its_accent_and_the_mockup_markup(app):
    app.config['SITE_URL'] = SITE
    html = _survivor_section().html
    # The hairline-topped eyebrow, the one-row inset, the solid button.
    assert ('margin:26px 0 6px; padding-top:18px; border-top:1px solid '
            '#E8E5F0;') in html
    assert 'color:#C5050C;">CFB Survivor · Week 4</p>' in html
    assert '>Survivor locks</div>' in html and SAT_TEXT in html
    assert 'background:#C5050C; color:#F3EFE6;' in html
    assert html.count('class="section-cta"') == 1
    assert 'class="cta"' not in html
    assert 'margin:4px auto 6px;' in html
    assert '#A63446' not in html


def test_spectator_section_has_no_inset_and_no_button(app):
    app.config['SITE_URL'] = SITE
    block = game_section('cfb', 'CFB Survivor · Week 4',
                         ['Out after Week 3. 27 of 31 still alive.'])
    assert block.deadline is None and not block.has_button
    assert 'role="presentation"' not in block.html   # no inset table
    assert 'section-cta' not in block.html and '<a ' not in block.html
    assert block.plain == ('CFB Survivor · Week 4\nOut after Week 3. 27 of 31 '
                           'still alive.')


def test_rider_block_is_one_link_in_the_tab_strip_register(app):
    app.config['SITE_URL'] = SITE
    block = rider_block('docket', 'three <sides> to file.', 'Open <s>',
                        'https://x/?a=1&b=2')
    assert block.html.count('<a ') == 1
    assert 'class="cta"' not in block.html and 'section-cta' not in block.html
    assert ('margin:24px 0 0; padding-top:16px; border-top:1px solid '
            '#E8E5F0;') in block.html
    assert ('>Also on your desk.</strong> The Docket: three &lt;sides&gt; to '
            'file. <a href="https://x/?a=1&amp;b=2" style="color:#A63446; '
            'font-weight:600;">Open &lt;s&gt;</a>') in block.html
    assert block.plain == ('Also on your desk. The Docket: three <sides> to '
                           'file. Open <s>: https://x/?a=1&b=2')


def test_the_paper_renders_two_sections_under_club_chrome(app):
    app.config['SITE_URL'] = SITE
    letter = _paper()
    plain, html = render_letter(letter)
    _assert_material_rules('paper', html, letter.subject)
    assert html.count('class="section-cta"') == 2
    assert 'class="cta"' not in html
    assert ACCENTS['cfb'] in html and ACCENTS['docket'] in html
    assert 'background:#C9A227' not in html          # no club-gold button
    assert 'color:#5A5470;">The Morning Line · Week 4</p>' in html
    assert 'Sent to you as a member of the Corrupt Commish Club.' in plain
    # Plain text follows the letter: sections in order, each with its own
    # deadline line and button line, the tab strip after both.
    marks = ['The Morning Line · Week 4', 'Both boards are open',
             'Last week is in the books', 'CFB Survivor · Week 4',
             'Last week: Survived with Oregon.', f'Survivor locks: {SAT_TEXT}',
             f'Make your pick: {SITE}/cfb/', 'The Docket · Week 4',
             f'The docket closes: {SUN_TEXT}', f'Open your sheet: {SITE}/docket/',
             'Settle the tab. The Docket: the $60 entry is due',
             'Corrupt Commish Club · cccfantasy.com']
    positions = [plain.index(m) for m in marks]
    assert positions == sorted(positions), plain
    assert '<strong>' not in plain
    assert len(letter.subject) <= 50


def test_the_paper_renders_a_long_name_and_an_eight_item_list(app):
    """A 47-character display name and an 8-item outstanding list (the widest
    content a section carries) render inside the 560px card without breaking
    the material rules."""
    app.config['SITE_URL'] = SITE
    name = 'Bartholomew Montgomery-Fitzgerald the Third Esq'
    assert len(name) == 47
    owed = [f'Slot {n}: no side filed.' for n in range(1, 9)]
    letter = _paper(
        greeting=name,
        extras=[_survivor_section(),
                _docket_section(lines=['Your sheet is short.']),
                items_block(owed, title='Still open on your sheet')])
    plain, html = render_letter(letter)
    _assert_material_rules('paper-long', html, letter.subject)
    assert f'Hi {name},' in plain and escape(name) in html
    assert plain.count('Slot ') == 8 and html.count('<li ') == 8
    assert plain.index('Open your sheet:') < plain.index('Slot 1:')


def test_no_gold_cta_beside_a_game_button(app):
    app.config['SITE_URL'] = SITE
    with pytest.raises(ValueError, match='club-gold'):
        render_letter(_paper(cta=('Open the lounge', SITE)))
    # A section without a button leaves a club CTA legal (nothing competes).
    spectator = game_section('cfb', 'CFB Survivor · Week 4', ['Out.'])
    quiet = game_section('docket', 'The Docket · Week 4', ['Filed.'])
    _, html = render_letter(_paper(extras=[quiet, spectator],
                                   cta=('Open the lounge', SITE)))
    assert html.count('class="cta"') == 1 and 'section-cta' not in html


def test_sections_render_in_deadline_order(app):
    app.config['SITE_URL'] = SITE
    with pytest.raises(ValueError, match='deadline order'):
        render_letter(_paper(extras=[_docket_section(), _survivor_section()]))
    spectator = game_section('cfb', 'CFB Survivor · Week 4', ['Out.'])
    with pytest.raises(ValueError, match='undated'):
        render_letter(_paper(extras=[spectator, _docket_section()]))
    _, html = render_letter(_paper(extras=[_docket_section(), spectator]))
    assert html.index('The Docket · Week 4') < html.index('CFB Survivor · Week 4')
    # Equal deadlines are in order; a non-section extra between sections is
    # not a section and does not enter the ordering.
    render_letter(_paper(extras=[_survivor_section(),
                                 items_block(['x'], title='Between'),
                                 _docket_section(deadline=SAT)]))


def test_a_single_section_is_that_games_own_letter(app):
    app.config['SITE_URL'] = SITE
    with pytest.raises(ValueError, match="own letter"):
        render_letter(_paper(extras=[_survivor_section()]))
    # A single CFB section under a non-null but wrong game_slug would render
    # Docket chrome over CFB content — reject it, not just the null case.
    with pytest.raises(ValueError, match="own letter"):
        render_letter(_paper(extras=[_survivor_section()], game_slug='docket',
                             eyebrow='CFB Survivor · Week 4'))
    letter = _paper(extras=[_survivor_section()], game_slug='cfb', season=2026,
                    eyebrow='CFB Survivor · Week 4', headline='Picks are open',
                    notes=[])
    plain, html = render_letter(letter)
    _assert_material_rules('single', html, letter.subject)
    assert html.count('class="section-cta"') == 1 and 'class="cta"' not in html
    assert '#A63446' not in html and 'background:#C9A227' not in html
    assert 'Sent to you as a member of CFB Survivor 2026.' in plain


def test_game_section_refuses_a_half_given_deadline_or_cta_pair():
    # A button without a url would render href="None"; a deadline without a
    # label would render "None" as the fact label. Reject the half-pairs.
    with pytest.raises(ValueError, match='deadline and deadline_label'):
        game_section('cfb', 'CFB Survivor · Week 4', ['Out.'], deadline=SAT)
    with pytest.raises(ValueError, match='deadline and deadline_label'):
        game_section('cfb', 'CFB Survivor · Week 4', ['Out.'],
                     deadline_label='Survivor locks')
    with pytest.raises(ValueError, match='button and url'):
        game_section('cfb', 'CFB Survivor · Week 4', ['Out.'], button='Pick')
    with pytest.raises(ValueError, match='button and url'):
        game_section('cfb', 'CFB Survivor · Week 4', ['Out.'],
                     url=f'{SITE}/cfb/')


def test_a_desk_letter_carries_one_section_per_game(app):
    app.config['SITE_URL'] = SITE
    with pytest.raises(ValueError, match='one section per game'):
        render_letter(_paper(extras=[_survivor_section(),
                                     _survivor_section(deadline=SUN)]))


def test_a_naive_section_deadline_is_refused(app):
    # Docket columns are naive-UTC and CFB deadlines are aware; a Paper that
    # mixed them would raise TypeError deep in sorted(). Fail with a clear
    # message at the section instead.
    app.config['SITE_URL'] = SITE
    naive = SUN.replace(tzinfo=None)
    with pytest.raises(ValueError, match='naive deadline'):
        render_letter(_paper(extras=[_survivor_section(),
                                     _docket_section(deadline=naive)]))


def test_letters_without_sections_are_untouched_by_the_desk_locks(app):
    """A single-game letter with a club CTA and ordinary extras never trips
    the desk rules: they apply only when a SectionBlock is present."""
    app.config['SITE_URL'] = SITE
    _, html = render_letter(Letter(
        subject='s', headline='h', eyebrow='e', cta=('Go', SITE),
        extras=[items_block(['one']), result_block('R', [('a', '1')])]))
    assert html.count('class="cta"') == 1


def test_merged_reminder_keeps_one_cta_and_the_rider_before_the_tab(app):
    app.config['SITE_URL'] = SITE
    letter = _merged_reminder()
    plain, html = render_letter(letter)
    _assert_material_rules('merged-reminder', html, letter.subject)
    assert html.count('class="cta"') == 1 and 'section-cta' not in html
    assert len(letter.subject) <= 45
    rider = html[html.index('Also on your desk.'):]
    rider = rider[:rider.index('Settle the tab.')]
    assert rider.count('<a ') == 1 and 'href="https://cccfantasy.com/docket/"' in rider
    assert ACCENTS['docket'] in rider and 'background:#A63446' not in html
    # After the supporting line, before the tab strip, never between the
    # inset and the button.
    order = [html.index('class="cta"'), html.index('Miss the deadline'),
             html.index('Also on your desk.'), html.index('Settle the tab.'),
             html.index('#1C0A3A; padding')]
    assert order == sorted(order)
    assert (f'Also on your desk. The Docket: {RIDER_SENTENCE} Open your sheet: '
            f'{SITE}/docket/') in plain
    assert plain.index('Miss the deadline') < plain.index('Also on your desk.') \
        < plain.index('Settle the tab.')
    # The anchor's own words are the ones a single-game reminder carries.
    assert f'Make your pick: {SITE}/cfb/' in plain
    assert 'Sent to you as a member of CFB Survivor 2026.' in plain
