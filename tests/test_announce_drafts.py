"""The announce desk's drafts and sent archive (models.content.Announcement,
core/admin/announce.py): every storable POST saves the draft, a sent
announcement is immutable and keeps the copy that went out, and a draft can
be sent exactly once."""
import re
from threading import Thread
from unittest.mock import patch

import pytest

from core.admin.announce import claim_for_send
from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from models.content import Announcement
from models.user import User

SEND = 'core.admin.announce.send_platform_email'


def _user(username, *, is_admin=False, enroll=False):
    user = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    if enroll:
        db.session.add(WorldCupEnrollment(user_id=user.id, season_year=SEASON_YEAR,
                                          picks_submitted=True))
        db.session.commit()
    return user


@pytest.fixture
def admin(app, client):
    """A logged-in platform admin plus two World Cup members; returns the
    admin's id."""
    with app.app_context():
        admin = _user('admin', is_admin=True)
        _user('m1', enroll=True)
        _user('m2', enroll=True)
        admin_id, auth_id = admin.id, admin.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    return admin_id


def _form(action, **overrides):
    data = {'action': action, 'audiences': ['worldcup'], 'recipient_filter': 'all',
            'subject': 'Week 3 recap', 'headline': '', 'preheader': '',
            'cta': 'lounge', 'body_text': '**Carnage** in Ames.', 'csrf_token': 'x'}
    data.update(overrides)
    return data


def _only(app):
    with app.app_context():
        rows = db.session.scalars(db.select(Announcement)).all()
        assert len(rows) == 1, rows
        db.session.expunge(rows[0])
        return rows[0]


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

def test_save_creates_a_draft_and_redirects_to_it(app, client, admin):
    resp = client.post('/admin/announce', data=_form(
        'save', audiences=['golf', 'cfb'], headline='Carnage', preheader='Two gone',
        cta='docket'))
    draft = _only(app)
    assert resp.status_code == 302
    assert resp.location.endswith(f'/admin/announce/{draft.id}')
    assert draft.audiences == 'cfb,golf'      # registry order, whatever the form's
    assert (draft.subject, draft.headline, draft.preheader, draft.cta) == (
        'Week 3 recap', 'Carnage', 'Two gone', 'docket')
    assert draft.body == '**Carnage** in Ames.' and draft.created_by_id == admin
    assert not draft.is_sent


def test_a_half_written_draft_saves(app, client, admin):
    """Save never demands a subject, a body or a game."""
    resp = client.post('/admin/announce', data=_form(
        'save', subject='', body_text='', audiences=[]))
    assert resp.status_code == 302
    draft = _only(app)
    assert draft.subject == '' and draft.audience_list == []
    page = client.get(resp.location).data.decode()
    assert 'Untitled draft' in page


def test_an_unstorable_draft_is_refused(app, client, admin):
    resp = client.post('/admin/announce', data=_form('save', subject='x' * 201))
    assert resp.status_code == 200
    assert 'Subject must be 200 characters or fewer.' in resp.data.decode()
    with app.app_context():
        assert db.session.scalars(db.select(Announcement)).all() == []


def test_a_draft_reopens_with_its_values(app, client, admin):
    location = client.post('/admin/announce', data=_form(
        'save', headline='The headline')).location
    page = client.get(location).data.decode()
    assert 'value="The headline"' in page
    assert '**Carnage** in Ames.</textarea>' in page
    assert 'name="audiences" value="worldcup" id="audience-worldcup"\n' in page
    assert 'Delete Draft' in page


def test_preview_saves_the_draft_once(app, client, admin):
    """The first preview creates the draft; the form then posts to it."""
    page = client.post('/admin/announce', data=_form('preview')).data.decode()
    draft = _only(app)
    assert f'action="/admin/announce/{draft.id}"' in page
    client.post(f'/admin/announce/{draft.id}', data=_form('preview', subject='Again'))
    assert _only(app).subject == 'Again'


def test_a_markup_mistake_still_saves_the_words(app, client, admin):
    page = client.post('/admin/announce', data=_form(
        'preview', body_text='Keep this.\n\n[[nope]]')).data.decode()
    assert 'no board called [[nope]]' in page
    assert _only(app).body == 'Keep this.\n\n[[nope]]'


def test_delete_removes_a_draft(app, client, admin):
    location = client.post('/admin/announce', data=_form('save')).location
    resp = client.post(location, data={'action': 'delete', 'csrf_token': 'x'})
    assert resp.status_code == 302 and resp.location.endswith('/admin/announce')
    with app.app_context():
        assert db.session.scalars(db.select(Announcement)).all() == []


def test_a_stale_delete_never_removes_a_sent_record(app, client, admin):
    """The draft was sent from another tab before this tab's delete."""
    location = client.post('/admin/announce', data=_form('save')).location
    draft_id = int(location.rsplit('/', 1)[1])
    # The route's early is_sent check read the row before the claim: patch it
    # to the stale answer so the request reaches the delete itself.
    with app.app_context(), patch('core.admin.announce.Announcement.is_sent', False):
        assert claim_for_send(draft_id, 2, 'plain', 'html') is True
        resp = client.post(location, data={'action': 'delete', 'csrf_token': 'x'})
    assert resp.status_code == 302 and resp.location.endswith(location)
    assert _only(app).is_sent


def test_an_unknown_announcement_is_a_404(client, admin):
    assert client.get('/admin/announce/999').status_code == 404


def test_the_page_lists_drafts_and_sent(app, client, admin):
    client.post('/admin/announce', data=_form('save', subject='Draft one'))
    with patch(SEND, return_value=True):
        client.post('/admin/announce', data=_form('send', subject='Went out'))
    page = client.get('/admin/announce').data.decode()
    drafts, sent = page.split('id="announce-sent-title"')
    assert 'Draft one' in drafts and 'Went out' not in drafts.split('announce-drafts-title')[1]
    assert 'Went out' in sent and '2 members' in sent


# ---------------------------------------------------------------------------
# Sending and the archive
# ---------------------------------------------------------------------------

def test_send_marks_it_sent_and_keeps_the_mailed_copy(app, client, admin):
    with patch(SEND, return_value=True) as send:
        resp = client.post('/admin/announce', data=_form('send'))
    sent = _only(app)
    assert resp.status_code == 302
    assert resp.location.endswith(f'/admin/announce/{sent.id}')
    assert sent.is_sent and (sent.recipient_count, sent.sent_count) == (2, 2)
    mailed_plain, mailed_html = send.call_args.args[2], send.call_args.args[3]
    assert (sent.sent_plain, sent.sent_html) == (mailed_plain, mailed_html)


def test_a_sent_announcement_is_read_only(app, client, admin):
    with patch(SEND, return_value=True):
        location = client.post('/admin/announce', data=_form('send')).location
    page = client.get(location).data.decode()
    assert 'As Sent' in page and 'value="duplicate"' in page
    assert 'name="body_text"' not in page and 'value="send"' not in page
    assert '2 of 2 members' in page

    with patch(SEND, return_value=True) as send:
        for action in ('save', 'send', 'test', 'delete'):
            resp = client.post(location, data=_form(action, subject='Changed'))
            assert resp.status_code == 302
    send.assert_not_called()
    assert _only(app).subject == 'Week 3 recap'


def test_duplicate_copies_a_sent_announcement_into_a_draft(app, client, admin):
    with patch(SEND, return_value=True):
        location = client.post('/admin/announce', data=_form(
            'send', headline='Carnage', cta='none')).location
    resp = client.post(location, data={'action': 'duplicate', 'csrf_token': 'x'})
    with app.app_context():
        rows = db.session.scalars(db.select(Announcement).order_by(Announcement.id)).all()
        original, copy = rows
        assert resp.location.endswith(f'/admin/announce/{copy.id}')
        assert not copy.is_sent and copy.sent_html is None
        assert (copy.subject, copy.headline, copy.cta, copy.body, copy.audiences) == (
            original.subject, original.headline, original.cta, original.body,
            original.audiences)


def test_a_claimed_draft_is_never_sent_again(app, client, admin):
    """The claim is conditional: once sent_at is set, a second claim loses."""
    location = client.post('/admin/announce', data=_form('save')).location
    draft_id = int(location.rsplit('/', 1)[1])
    with app.app_context():
        assert claim_for_send(draft_id, 2, 'plain', 'html') is True
        assert claim_for_send(draft_id, 2, 'other', 'other') is False
        assert db.session.get(Announcement, draft_id).sent_plain == 'plain'


def test_a_save_racing_a_send_writes_nothing(app, client, admin):
    """A tab that loaded the draft before another tab sent it cannot
    rewrite the sent record."""
    from core.admin.announce import _save
    location = client.post('/admin/announce', data=_form('save')).location
    draft_id = int(location.rsplit('/', 1)[1])
    with app.test_request_context():
        stale = db.session.get(Announcement, draft_id)
        assert claim_for_send(draft_id, 2, 'plain', 'html') is True
        values = {'audiences': ['worldcup'], 'recipient_filter': 'all',
                  'subject': 'Rewritten', 'headline': '', 'preheader': '',
                  'cta': 'lounge', 'body_text': 'Rewritten'}
        assert _save(stale, values) is None
    assert _only(app).subject == 'Week 3 recap'


@pytest.mark.postgres
def test_two_racing_claims_send_once(app, client, admin):
    """A second tab's claim waits on the first claim's row lock and, once it
    commits, re-reads sent_at and loses."""
    location = client.post('/admin/announce', data=_form('save')).location
    draft_id = int(location.rsplit('/', 1)[1])
    db.session.remove()

    outcome = {}

    def second_tab():
        with app.app_context():
            try:
                outcome['claimed'] = claim_for_send(draft_id, 2, 'p', 'h')
            finally:
                db.session.remove()

    holder = db.engine.connect()
    held = holder.begin()
    racer = Thread(target=second_tab)
    try:
        first = holder.execute(db.text(
            'UPDATE announcements SET sent_at = now() '
            'WHERE id = :id AND sent_at IS NULL'), {'id': draft_id})
        assert first.rowcount == 1
        racer.start()
        racer.join(timeout=1)
        assert racer.is_alive(), 'the second claim did not wait on the row lock'
        held.commit()
    finally:
        if held.is_active:
            held.rollback()
        holder.close()
        if racer.ident is not None:          # started
            racer.join(timeout=10)
    assert outcome == {'claimed': False}


# ---------------------------------------------------------------------------
# The letter's controls
# ---------------------------------------------------------------------------

def test_headline_preheader_and_button_reach_the_letter(app):
    from core.admin.announce import render_announcement
    with app.test_request_context():
        _, html = render_announcement('Subject line', 'Body.', headline='Carnage',
                                      preheader='Two gone', cta='docket')
        _, bare = render_announcement('Subject line', 'Body.', cta='none')
    assert 'Carnage</h1>' in html and 'Two gone' in html
    assert re.search(r'class="cta" href="[^"]*/docket/ledger"', html)
    assert 'class="cta"' not in bare
    assert 'Subject line</h1>' in bare


def test_the_live_preview_follows_the_controls(client, admin):
    data = client.post('/admin/announce/render', data=_form(
        'preview', headline='Carnage', cta='survivor')).get_json()
    assert 'Carnage</h1>' in data['html'] and '/cfb/results"' in data['html']
