"""The Tribune (core/tribune): every sent Club Letter, on the record.

A sent ``Announcement`` is an issue. The send stores ``sent_page_html`` (the
same Letter rendered through the page shell) beside the mailed copy; the
Tribune lists issues newest first and prints one as the site's own page;
the lounge's From the Commish band names the latest issue; letters sent
before the column existed are backfilled once by ``flask tribune backfill``.
Members only: the Tribune is inside the club.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from core.admin.announce import claim_for_send, render_announcement
from core.tribune.services import (
    backfill_page_html,
    latest_issue,
    render_letter_page_for,
)
from extensions import db
from models.content import Announcement
from models.user import User
from utils.email_layout import Letter, render_letter_page

SEND = 'core.admin.announce.send_platform_email'


def _user(username, *, is_admin=False):
    user = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def _issue(admin_id, subject, body, *, sent_at, page=True, **fields):
    """A sent announcement as the desk stores one: body markup, the mailed
    copy, and (``page``) the page copy."""
    row = Announcement(created_by_id=admin_id, subject=subject, body=body,
                       audiences='cfb', recipient_filter='all', cta='lounge',
                       **fields)
    db.session.add(row)
    db.session.commit()
    plain, html = render_announcement(subject, body, headline=fields.get('headline'),
                                      preheader=fields.get('preheader'))
    row.sent_at = sent_at
    row.recipient_count = 3
    row.sent_count = 3
    row.sent_plain, row.sent_html = plain, html
    if page:
        row.sent_page_html = render_letter_page_for(row)
    db.session.commit()
    return row.id


@pytest.fixture
def member(app, client):
    """A logged-in ordinary member; returns the admin's id for authoring."""
    with app.app_context():
        admin = _user('commish', is_admin=True)
        reader = _user('reader')
        ids = (admin.id, reader.auth_id)
    _login(client, ids[1])
    return ids[0]


# ---------------------------------------------------------------------------
# The page renderer
# ---------------------------------------------------------------------------

def test_render_letter_page_prints_the_letter_as_page_content(app):
    with app.app_context():
        letter = Letter(subject='Week 3 recap', headline='The cut deepens',
                        lede=['Three lives went.'],
                        cta=('Open the lounge', 'https://x.test/'))
        html = render_letter_page(letter)
    assert '<!DOCTYPE html>' not in html and 'role="presentation"' not in html
    assert 'The cut deepens' in html and 'Three lives went.' in html
    assert 'eyebrow' not in html           # opens on the headline (ADR-066)
    # The CTA becomes an ordinary link at the foot, never a button.
    assert 'href="https://x.test/"' in html and 'Open the lounge' in html
    assert 'class="cta"' not in html


def test_render_letter_page_escapes_and_carries_blocks(app):
    with app.app_context():
        row = Announcement(created_by_id=1, subject='S <i>', cta='none',
                           body='## Standing <b>\n\nA line & more')
        page = render_letter_page_for(row)
    assert 'Standing &lt;b&gt;' in page and 'A line &amp; more' in page
    assert 'S &lt;i&gt;' in page
    assert '<b>' not in page and '<i>' not in page


# ---------------------------------------------------------------------------
# The send stores the page copy
# ---------------------------------------------------------------------------

def test_claim_for_send_stores_the_page_copy(app, member):
    with app.app_context():
        row = Announcement(created_by_id=member, subject='Week 1', body='Hello **club**.',
                           audiences='cfb', recipient_filter='all', cta='none')
        db.session.add(row)
        db.session.commit()
        plain, html = render_announcement('Week 1', 'Hello **club**.', cta='none')
        assert claim_for_send(row.id, 2, plain, html, '<article>Hello</article>')
        db.session.refresh(row)
        assert row.sent_page_html == '<article>Hello</article>'


def test_the_desk_send_stores_the_page_copy(app, client):
    from games.cfb.models import CfbEnrollment
    with app.app_context():
        admin = _user('admin', is_admin=True)
        reader = _user('reader')
        db.session.add(CfbEnrollment(user_id=reader.id, season_year=2026))
        db.session.commit()
        auth_id = admin.auth_id
    _login(client, auth_id)
    with patch(SEND, return_value=True):
        client.post('/admin/announce', data={
            'action': 'send', 'audiences': ['cfb'], 'recipient_filter': 'all',
            'subject': 'Week 2 recap', 'headline': '', 'preheader': '',
            'cta': 'lounge', 'body_text': 'A **bold** week.', 'csrf_token': 'x'})
    with app.app_context():
        row = db.session.scalars(db.select(Announcement)).one()
        assert row.sent_at is not None
        assert 'bold' in row.sent_page_html
        assert '<!DOCTYPE html>' not in row.sent_page_html


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def test_the_tribune_is_members_only(client):
    resp = client.get('/tribune')
    assert resp.status_code == 302 and '/login' in resp.headers['Location']
    assert client.get('/tribune/1').status_code == 302


def test_the_issue_list_is_newest_first_and_numbered_by_send_order(app, client, member):
    with app.app_context():
        t0 = datetime(2026, 9, 8, 14, 0, tzinfo=UTC)
        first = _issue(member, 'Week 1 recap', 'One.', sent_at=t0)
        second = _issue(member, 'Week 2 recap', 'Two.', sent_at=t0 + timedelta(days=7),
                        headline='The field thins', preheader='Two lives went.')
        # A draft is never an issue.
        db.session.add(Announcement(created_by_id=member, subject='Draft only', body='x',
                                    audiences='cfb', recipient_filter='all', cta='lounge'))
        db.session.commit()
    page = client.get('/tribune').get_data(as_text=True)
    assert page.index('The field thins') < page.index('Week 1 recap')
    assert 'Draft only' not in page
    assert f'/tribune/{second}' in page and f'/tribune/{first}' in page
    assert 'Two lives went.' in page                 # the preheader as the deck
    assert 'No. 2' in page and 'No. 1' in page       # issue numbers by send order
    assert 'Sep 15' in page                           # the sent date, CT
    assert 'Week 2' in page and 'Week 1' in page      # filed under their weeks


def test_the_issue_page_prints_the_letter_and_walks_the_issues(app, client, member):
    with app.app_context():
        t0 = datetime(2026, 9, 8, 14, 0, tzinfo=UTC)
        first = _issue(member, 'Week 1 recap', 'The **opening** week.', sent_at=t0)
        second = _issue(member, 'Week 2 recap', 'Two.', sent_at=t0 + timedelta(days=7))
    page = client.get(f'/tribune/{first}').get_data(as_text=True)
    assert '<strong' in page and 'opening' in page
    assert 'Week 1 recap' in page and 'No. 1' in page
    assert f'/tribune/{second}' in page              # next issue
    assert 'CFB Survivor' in page                    # the audience line
    page2 = client.get(f'/tribune/{second}').get_data(as_text=True)
    assert f'/tribune/{first}' in page2              # previous issue
    assert client.get('/tribune/999').status_code == 404


def test_a_draft_is_not_an_issue_and_a_stale_issue_still_reads(app, client, member):
    with app.app_context():
        draft = Announcement(created_by_id=member, subject='Draft', body='x',
                             audiences='cfb', recipient_filter='all', cta='lounge')
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id
        stale = _issue(member, 'Old', 'Old words.', page=False,
                       sent_at=datetime(2026, 9, 1, tzinfo=UTC))
    assert client.get(f'/tribune/{draft_id}').status_code == 404
    # Sent before the column existed and not yet backfilled: the page prints
    # the mailed plain copy rather than 404ing a member out of the archive.
    page = client.get(f'/tribune/{stale}').get_data(as_text=True)
    assert 'Old words.' in page


def test_a_stale_issue_reads_as_mailed_and_never_re_renders(app, client, member):
    with app.app_context():
        stale = _issue(member, 'Old', 'First line\nsecond <line>.', page=False,
                       sent_at=datetime(2026, 9, 1, tzinfo=UTC))
        # A body that no longer parses (a board that is gone) must not 500
        # the issue, and nothing but the mailed copy reaches the page.
        row = db.session.get(Announcement, stale)
        row.body = '[[no-such-board]]'
        db.session.commit()
    resp = client.get(f'/tribune/{stale}')
    assert resp.status_code == 200
    page = resp.get_data(as_text=True)
    assert 'First line<br>second &lt;line&gt;.' in page
    assert 'no-such-board' not in page


def test_the_empty_tribune_speaks_in_the_commish_register(client, member):
    page = client.get('/tribune').get_data(as_text=True)
    assert 'Nothing on the record yet' in page


# ---------------------------------------------------------------------------
# The calendar: which week a letter files under
# ---------------------------------------------------------------------------

def test_filed_week_reads_the_title_then_the_club_calendar():
    from core.tribune.services import filed_week
    tue_wk4 = datetime(2026, 9, 23, 11, 15, tzinfo=UTC)   # Tue Sep 23, 06:15 CT
    assert filed_week('Week 3 recap', None, tue_wk4) == 3       # the subject's word
    assert filed_week('Recap', 'The Week 2 cut', tue_wk4) == 2  # the headline first
    assert filed_week('week 12 preview', None, tue_wk4) == 12   # case-free
    assert filed_week('Week 99 of what', None, tue_wk4) == 4    # not a season week
    assert filed_week('The Wire is live', None, tue_wk4) == 4   # the club week
    assert filed_week('Offseason note', None,
                      datetime(2026, 8, 1, tzinfo=UTC)) is None  # out of season
    assert filed_week('Draft', None, None) is None


def test_week_head_names_the_saturday():
    from core.tribune.services import week_head
    head = week_head(3)
    assert head['label'] == 'Week 3' and head['date'] == 'Saturday, Sep 19'
    assert week_head(None)['label'] == 'Between seasons'


def test_the_calendar_groups_issues_under_their_week(app, client, member):
    with app.app_context():
        a = _issue(member, 'Week 1 recap', 'One.', sent_at=datetime(2026, 9, 8, 14, tzinfo=UTC))
        b = _issue(member, 'Week 2 recap', 'Two.', sent_at=datetime(2026, 9, 15, 14, tzinfo=UTC))
        c = _issue(member, 'The Wire is live', 'Install it.',
                   sent_at=datetime(2026, 9, 16, 14, tzinfo=UTC))   # club week 3
        for row_id, week in ((a, 1), (b, 2), (c, 3)):
            db.session.get(Announcement, row_id).week_number = week
        db.session.commit()
    page = client.get('/tribune').get_data(as_text=True)
    assert page.index('Week 3') < page.index('Week 2') < page.index('Week 1')
    assert page.index('Saturday, Sep 19') < page.index('The Wire is live') < page.index('Week 2 recap')
    issue_page = client.get(f'/tribune/{b}').get_data(as_text=True)
    assert 'Week 2, Saturday, Sep 12' in issue_page
    # A stale row with no stored week still files by its title.
    with app.app_context():
        db.session.get(Announcement, a).week_number = None
        db.session.commit()
    page = client.get('/tribune').get_data(as_text=True)
    assert page.index('Week 1 recap') > page.index('Week 2 recap')


def test_the_desk_files_the_letter_under_its_week(app, client):
    from games.cfb.models import CfbEnrollment
    with app.app_context():
        admin = _user('admin', is_admin=True)
        reader = _user('reader')
        db.session.add(CfbEnrollment(user_id=reader.id, season_year=2026))
        db.session.commit()
        auth_id = admin.auth_id
    _login(client, auth_id)
    with patch(SEND, return_value=True):
        preview = client.post('/admin/announce', data={
            'action': 'preview', 'audiences': ['cfb'], 'recipient_filter': 'all',
            'subject': 'Week 2 recap', 'headline': '', 'preheader': '',
            'cta': 'lounge', 'body_text': 'A week.', 'csrf_token': 'x'}).get_data(as_text=True)
        assert 'Files in The Tribune under Week 2' in preview
        with app.app_context():
            draft_id = db.session.scalars(db.select(Announcement)).one().id
        client.post(f'/admin/announce/{draft_id}', data={
            'action': 'send', 'audiences': ['cfb'], 'recipient_filter': 'all',
            'subject': 'Week 2 recap', 'headline': '', 'preheader': '',
            'cta': 'lounge', 'body_text': 'A week.', 'csrf_token': 'x'})
    with app.app_context():
        row = db.session.get(Announcement, draft_id)
        assert row.sent_at is not None and row.week_number == 2


# ---------------------------------------------------------------------------
# The lounge line
# ---------------------------------------------------------------------------

def test_the_lounge_names_the_latest_issue_only_when_one_exists(app, client, member):
    home = client.get('/').get_data(as_text=True)
    assert 'Latest letter' not in home
    with app.app_context():
        _issue(member, 'Week 3 recap', 'Words.', headline='The cut deepens',
               sent_at=datetime(2026, 9, 23, 14, 0, tzinfo=UTC))
        assert latest_issue().headline == 'The cut deepens'
    home = client.get('/').get_data(as_text=True)
    assert 'The cut deepens' in home and '/tribune' in home
    assert 'Sep 23' in home


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def test_backfill_fills_only_sent_rows_without_a_page_copy(app, member):
    with app.app_context():
        old = _issue(member, 'Old', 'Old **words**.', page=False,
                     sent_at=datetime(2026, 9, 2, 14, tzinfo=UTC))
        done = _issue(member, 'Done', 'Done.', sent_at=datetime(2026, 9, 3, tzinfo=UTC))
        before = db.session.get(Announcement, done).sent_page_html
        assert backfill_page_html() == (1, [])
        assert 'words' in db.session.get(Announcement, old).sent_page_html
        assert db.session.get(Announcement, old).week_number == 1   # Sep 2 = club week 1
        assert db.session.get(Announcement, done).sent_page_html == before
        assert backfill_page_html() == (0, [])                 # idempotent


def test_backfill_skips_a_body_that_no_longer_parses_and_commits_the_rest(app, member):
    with app.app_context():
        broken = _issue(member, 'Broken', 'Fine then.', page=False,
                        sent_at=datetime(2026, 9, 1, tzinfo=UTC))
        good = _issue(member, 'Good', 'Good words.', page=False,
                      sent_at=datetime(2026, 9, 2, tzinfo=UTC))
        db.session.get(Announcement, broken).body = '[[no-such-board]]'
        db.session.commit()
        assert backfill_page_html() == (1, [broken])
        assert db.session.get(Announcement, broken).sent_page_html is None
        assert 'Good words.' in db.session.get(Announcement, good).sent_page_html
        assert backfill_page_html() == (0, [broken])           # still skipped, still safe


def test_backfill_cli_reports_the_count(app, member):
    with app.app_context():
        _issue(member, 'Old', 'Old.', page=False, sent_at=datetime(2026, 9, 1, tzinfo=UTC))
    result = app.test_cli_runner().invoke(args=['tribune', 'backfill'])
    assert result.exit_code == 0, result.output
    assert '1 issue' in result.output
    assert 'Skipped' not in result.output
