"""The Tribune's reads and the one write (the backfill).

An issue is a sent ``Announcement``. Its page copy (``sent_page_html``) and
the week it files under (``week_number``) are stored by the desk at send;
a row sent before those columns existed reads as its mailed plain copy
through ``page_html`` and files by ``filed_week`` until
``backfill_page_html`` stores both. Nothing re-renders the markup on read.
"""
import logging
import re
from datetime import UTC, timedelta

from markupsafe import Markup, escape
from sqlalchemy import select

from core.admin.announce import announcement_letter
from extensions import db
from games.docket.services.weeks import (
    TOTAL_WEEKS,
    deadline_utc,
    week_number_for,
)
from models.content import Announcement, latest_issue, sent_issues
from utils.email_layout import render_letter_page
from utils.letter_markup import MarkupError
from utils.time import format_ct

__all__ = ['backfill_page_html', 'filed_week', 'issue_date', 'latest_issue',
           'page_html', 'render_letter_page_for', 'sent_issues', 'week_head']

logger = logging.getLogger(__name__)

# "Week 3" in a subject or headline: the week the letter speaks to.
_WEEK_IN_TITLE = re.compile(r'\bweek\s+(\d{1,2})\b', re.IGNORECASE)


def render_letter_page_for(announcement: Announcement) -> str:
    """The announcement's markup as page content: the same Letter the
    desk mails, through the page shell. Live boards re-read the database,
    so this is the copy to STORE at send, not to render on every read."""
    letter = announcement_letter(
        announcement.subject, announcement.body,
        headline=announcement.headline, preheader=announcement.preheader,
        cta=announcement.cta)
    return render_letter_page(letter)


def page_html(announcement: Announcement) -> str:
    """The stored page copy, or, for a row without one (sent before the
    column existed and not yet backfilled, or skipped by the backfill), the
    mailed plain copy as page paragraphs. Never a re-render: a live board
    would show today's field, and a body that no longer parses would 500."""
    if announcement.sent_page_html is not None:
        return announcement.sent_page_html
    paragraphs = [p for p in re.split(r'\n\s*\n', announcement.sent_plain)
                  if p.strip()]
    body = Markup('').join(
        Markup('<p class="letter-page-para">{}</p>').format(
            Markup('<br>').join(escape(line) for line in p.split('\n')))
        for p in paragraphs)
    return Markup('<article class="letter-page"><div class="letter-page-body">'
                  '{}</div></article>').format(body)


def filed_week(subject: str, headline: str | None, sent_at) -> int | None:
    """The season week a letter files under: the "Week N" its headline or
    subject names (the Commish's own word), else the club week the send
    instant falls in (the Docket's pure week math, Tuesday to Tuesday),
    else None out of season."""
    for text in (headline or '', subject or ''):
        match = _WEEK_IN_TITLE.search(text)
        if match and 1 <= int(match.group(1)) <= TOTAL_WEEKS:
            return int(match.group(1))
    if sent_at is None:
        return None
    instant = sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=UTC)
    return week_number_for(instant.astimezone(UTC))


def week_head(number: int | None) -> dict:
    """The calendar head for a week: its label and the Saturday it was
    played on (the Docket deadline is the Sunday noon after it)."""
    if number is None:
        return {'number': None, 'label': 'Between seasons', 'date': ''}
    saturday = deadline_utc(number) - timedelta(days=1)
    return {'number': number, 'label': f'Week {number}',
            'date': format_ct(saturday, '%A, %b %-d')}


def issue_date(announcement: Announcement) -> str:
    """'Sep 23': the sent date in Central Time, the issue's dateline."""
    return format_ct(announcement.sent_at, '%b %-d')


def backfill_page_html() -> tuple[int, list[int]]:
    """Store the page copy and the filing week on every sent row that
    lacks the page copy; returns (count filled, ids skipped). Idempotent.
    A live board ([[survivor-board]]) rendered now shows today's field, not
    the field on the send date: the caller prints that caveat. A body that
    no longer parses (a board that now refuses its settings) is skipped and
    keeps reading as its mailed plain copy; the rest still commit."""
    rows = db.session.scalars(
        select(Announcement)
        .where(Announcement.sent_at.is_not(None),
               Announcement.sent_page_html.is_(None))
        .order_by(Announcement.sent_at.asc())
    ).all()
    filled, skipped = 0, []
    for row in rows:
        try:
            row.sent_page_html = render_letter_page_for(row)
        except MarkupError:
            logger.exception('Tribune backfill skipped announcement #%d', row.id)
            skipped.append(row.id)
            continue
        filled += 1
        if row.week_number is None:
            row.week_number = filed_week(row.subject, row.headline, row.sent_at)
    db.session.commit()
    return filled, skipped
