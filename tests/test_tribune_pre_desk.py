"""The letters sent before the announce desk kept a copy (core/tribune/pre_desk.py).

Weeks 1 to 3 went out through the plain-text tool and left no row. The
backfill files them as sent rows built the way that tool rendered them, so
The Tribune carries every letter the club has received. It sends nothing,
and it runs once: a second run files nothing.
"""
from unittest.mock import patch

import pytest
from sqlalchemy import select

from core.tribune.pre_desk import (
    PRE_DESK_LETTERS,
    file_pre_desk_letters,
    pre_desk_letter,
)
from extensions import db
from models.content import Announcement
from models.user import User
from utils.email_layout import render_letter

# Week 1's text/plain part as members received it (copied from the delivered
# mail; the mail client trims the one trailing space the letter carried).
WEEK_1_AS_DELIVERED = (
    'From the Commish\n'
    'Yee-Haw Cowboy, We Have Pandemonium in Week 1\n'
    '\n'
    'Welcome to the CFB Survivor 2026 pool, and thank you for joining. There are 32 of us, and only one can be the final survivor. Week 1 delivered more than we could have ever asked for. Let’s dive into it. As always, I like to offer my kind-hearted condolences to all the lives lost each week.\n'
    '\n'
    '- 11 lives lost on Oklahoma State (-13.5). What in tarnation were the North Texas Mean Green Cowboys doing out there? Who gave this team a preseason AP vote? They turned the ball over on downs three times. I know Oklahoma is ranked in the bottom three states for education, but they should still be able to count to four. Add in four more turnovers, and you have a perfect recipe for a butt whoopin’. Tulsa defends their turf, 24-10, and rocks this survivor league in Week 1.\n'
    '\n'
    '- 2 lives lost on Georgia Tech (-6.5). What an ending. Colorado, who was wired, fired, and inspired, scored a miraculous TD late and then got one of the best jumps off the line to block the GT game-winning FG. Starting to think this Alberto Mendoza might only be a discount Fernando. Colorado wins 14-13 on the road.\n'
    '\n'
    'Congrats to those who picked Memphis, Ole Miss, New Mexico, JMU, LSU, Auburn, and UNLV.\n'
    'Week 2 selections are now available.\n'
    'As always, any feedback on the site is appreciated.\n'
    '\n'
    'Open the lounge: https://cccfantasy.com/\n'
    '\n'
    'Corrupt Commish Club · cccfantasy.com\n'
    'Sent to you as a member of the Corrupt Commish Club.'
)


def _rstrip_lines(text):
    return '\n'.join(line.rstrip() for line in text.strip().split('\n'))


@pytest.fixture
def commish(app):
    with app.app_context():
        user = User(username='commish', email='commish@test.com', is_admin=True)
        user.set_password('pw')
        db.session.add(user)
        db.session.commit()
        return user.auth_id


def test_week_1_rebuilds_exactly_as_delivered(app):
    app.config['SITE_URL'] = 'https://cccfantasy.com'
    with app.test_request_context():
        plain, _html = render_letter(pre_desk_letter(PRE_DESK_LETTERS[0]))
    assert _rstrip_lines(plain) == _rstrip_lines(WEEK_1_AS_DELIVERED)


def test_the_body_stays_plain_text_never_markup(app):
    """"- 11 lives lost" and "1) Open" were paragraphs in the mail; the
    announce markup would now read them as a bullet and a numbered step."""
    with app.test_request_context():
        _plain, html = render_letter(pre_desk_letter(PRE_DESK_LETTERS[1]))
    assert '<ul' not in html and '<ol' not in html
    assert '1) Open cccfantasy.com in Safari.' in html
    assert '- The Commish' in html


def test_filing_writes_four_sent_rows_and_sends_nothing(app, commish):
    with app.app_context(), patch('utils.email.send_platform_email') as send:
        assert file_pre_desk_letters() == 4
        send.assert_not_called()
        rows = db.session.scalars(select(Announcement).order_by(Announcement.sent_at)).all()
        assert [row.subject for row in rows] == [e.subject for e in PRE_DESK_LETTERS]
        assert [row.week_number for row in rows] == [1, 2, 2, 3]
        for row in rows:
            assert row.is_sent
            assert row.sent_html and row.sent_plain and row.sent_page_html
            assert row.recipient_count is None
            assert row.audiences == ''


def test_filing_twice_files_nothing_the_second_time(app, commish):
    with app.app_context():
        assert file_pre_desk_letters() == 4
        assert file_pre_desk_letters() == 0
        count = db.session.scalar(select(db.func.count()).select_from(Announcement))
        assert count == 4


def test_the_tribune_prints_them_as_issues(app, client, commish):
    with app.app_context():
        file_pre_desk_letters()
        first_id = db.session.scalar(select(Announcement.id).where(
            Announcement.subject == PRE_DESK_LETTERS[0].subject))
    with client.session_transaction() as sess:
        sess['_user_id'] = commish
        sess['_fresh'] = True
    index = client.get('/tribune').get_data(as_text=True)
    for entry in PRE_DESK_LETTERS:
        assert entry.subject in index
    issue = client.get(f'/tribune/{first_id}').get_data(as_text=True)
    assert 'Tulsa defends their turf' in issue
    assert 'To the club' in issue


def test_the_admin_archive_says_the_count_was_not_kept(app, client, commish):
    with app.app_context():
        file_pre_desk_letters()
        row_id = db.session.scalar(select(Announcement.id).where(
            Announcement.subject == PRE_DESK_LETTERS[3].subject))
    with client.session_transaction() as sess:
        sess['_user_id'] = commish
        sess['_fresh'] = True
    page = client.get(f'/admin/announce/{row_id}').get_data(as_text=True)
    assert 'Not recorded (sent before the desk kept copies)' in page
    assert 'Audience not recorded' in page
    # The backfilled filter is not the historical selection: no "all enrolled".
    assert 'all enrolled' not in page
    assert 'None member' not in page
