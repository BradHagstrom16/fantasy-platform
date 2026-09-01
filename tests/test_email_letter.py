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
"""
import os
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from unittest.mock import patch

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
from games.docket.services.notifications import (
    notify_line_correction,
    notify_picks_open,
    notify_redesignation,
)
from games.docket.services.reminders import run_reminder_pass
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket
from utils import email_layout
from utils.email_layout import (
    Letter,
    items_block,
    paragraphs_block,
    render_letter,
    result_block,
    seal_url,
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
}
PERSONAL = {
    'cfb-recap-survived', 'cfb-recap-eliminated', 'cfb-recap-no-pick',
    'docket-line-corrected', 'platform-reset',
}
WITH_DEADLINE = {
    'cfb-picks-open', 'cfb-reminder-warning', 'cfb-reminder-final',
    'docket-picks-open', 'docket-reminder-48h', 'docket-reminder-24h',
    'docket-reminder-2h',
}
GAME_OF = {
    'cfb-picks-open': 'cfb', 'cfb-reminder-warning': 'cfb',
    'cfb-reminder-final': 'cfb', 'cfb-recap-survived': 'cfb',
    'cfb-recap-eliminated': 'cfb', 'cfb-recap-no-pick': 'cfb',
    'docket-picks-open': 'docket', 'docket-reminder-48h': 'docket',
    'docket-reminder-24h': 'docket', 'docket-reminder-2h': 'docket',
    'docket-line-corrected': 'docket', 'docket-tiebreaker-changed': 'docket',
    'platform-reset': None, 'platform-announce': None,
}

# CFB: Sat Jan 3 2026 11:00 CST (naive pool wall clock); the reminder
# instants are the exact T-25h / T-1h targets in UTC.
CFB_DEADLINE = datetime(2026, 1, 3, 11, 0)
CFB_WARNING_AT = '2026-01-02T16:00:00+00:00'
CFB_FINAL_AT = '2026-01-03T16:00:00+00:00'
CFB_DEADLINE_TEXT = 'Saturday, Jan 3 · 11:00 AM CT'
# Docket Week 1: Sat Sep 5 2026 11:00 CDT = 16:00 UTC.
DOCKET_DEADLINE_UTC = datetime(2026, 9, 5, 16, 0, tzinfo=UTC)
DOCKET_DEADLINE_TEXT = 'Saturday, Sep 5 · 11:00 AM CT'


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

    def keep(to, subject, plain, html):
        captured.update(to=to, subject=subject, plain=plain, html=html)
        return True

    with patch('core.auth.routes.send_platform_email', side_effect=keep):
        app.test_client().post('/forgot-password',
                               data={'email': 'reseeker@test.com',
                                     'csrf_token': 'x'})
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
    return out


@pytest.fixture()
def letters(app):
    """name -> {'subject', 'plain', 'html'} for every in-scope letter."""
    app.config['SITE_URL'] = SITE
    out = {}
    out.update(_platform_letters(app))
    out.update(_cfb_letters(app))
    out.update(_docket_letters(app))
    assert set(out) == set(GAME_OF), sorted(set(GAME_OF) ^ set(out))
    return out


def test_no_em_dashes_double_hyphens_or_emoji_anywhere(letters):
    emoji = re.compile('[\U0001F000-\U0001FAFF☀-➿]')
    for name, m in letters.items():
        for part in (m['subject'], m['plain'], _text(m['html'])):
            assert '—' not in part, (name, part)
            assert '--' not in part, (name, part)
            assert not emoji.search(part), (name, part)
        assert '&mdash;' not in m['html'] and '&#8212;' not in m['html'], name


def test_deadlines_say_ct_and_lead_the_fact_block(letters):
    for name, m in letters.items():
        text = _text(m['html'])
        assert 'CDT' not in text and 'CST' not in text, name
        assert 'CDT' not in m['plain'] and 'CST' not in m['plain'], name
        if name in WITH_DEADLINE:
            expected = (CFB_DEADLINE_TEXT if GAME_OF[name] == 'cfb'
                        else DOCKET_DEADLINE_TEXT)
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
    game_names = {'cfb': 'CFB Survivor', 'docket': 'The Docket'}
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
    assert 'FINAL' in letters['cfb-reminder-final']['subject']
    assert "You've been eliminated" in letters['cfb-recap-eliminated']['subject']
    assert 'You survived' in letters['cfb-recap-survived']['subject']
    tiers = {letters[f'docket-reminder-{t}']['subject'] for t in ('48h', '24h', '2h')}
    assert len(tiers) == 3, tiers      # distinct, so Gmail never threads them


def test_greeting_policy(letters):
    for name in BROADCASTS:
        plain = letters[name]['plain']
        assert not re.search(r'(^|\n)Hi ', plain), (name, plain)
    assert 'Hi Steady Eddie,' in letters['cfb-recap-survived']['plain']
    assert 'Hi Ghost Gary,' in letters['cfb-recap-eliminated']['plain']
    assert 'Hi Clerk of Court,' in letters['docket-line-corrected']['plain']
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
# Hand-rolled shells still standing. Each entry leaves in the PR that
# migrates it (Golf: its own PR, timers held until ~Jan 2027).
LEGACY_SHELLS = {'games/golf/services/reminders.py'}
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
