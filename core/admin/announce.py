"""
Fantasy Sports Platform - Admin Announce
==========================================
Platform-level admin: the Commish's recap desk. Compose an announcement in
light markup (utils/letter_markup.py) with live boards, watch the Club
Letter set beside it, save it as a draft, and mass-send it to the members
of one or more games (deduplicated). A sent announcement is kept as the
record of what went out (``models.content.Announcement``).
"""
import logging
from datetime import UTC, datetime
from typing import NamedTuple

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import delete, select, update
from sqlalchemy.orm import joinedload

from core.admin import admin_bp
from core.admin.routes import admin_required
from extensions import db
from games.cfb.models import CfbEnrollment
from games.cfb.services.announce_blocks import BOARDS as SURVIVOR_BOARDS
from games.docket.models import DocketEnrollment
from games.docket.services.announce_blocks import BOARDS as DOCKET_BOARDS
from games.docket.services.weeks import SEASON_YEAR as DOCKET_SEASON_YEAR
from games.golf.models import GolfEnrollment
from games.registry import GAMES
from games.worldcup.constants import SEASON_YEAR as WC_SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from models.content import ANNOUNCEMENT_CTAS, Announcement
from utils.email import send_platform_email
from utils.email_layout import Letter, render_letter, site_url
from utils.letter_markup import MarkupError, parse
from utils.time import format_deadline_short

logger = logging.getLogger(__name__)

MAX_SUBJECT = 200   # also the headline and inbox-preview cap (String(200))
MAX_BODY = 10_000

_VALID_FILTERS = ('all', 'active')

# The live boards a body may place on a line of its own ([[survivor-board]]),
# each read from the database at render time. The composer's Insert board
# menu lists them in this order.
BOARDS = {**SURVIVOR_BOARDS, **DOCKET_BOARDS}
BOARD_MENU = (
    ('survivor-board', 'Survivor: still standing'),
    ('survivor-cuts', 'Survivor: the week\'s damage'),
    ('survivor-picks', 'Survivor: pick split'),
    ('docket-week', 'Docket: the week'),
    ('docket-season', 'Docket: the season'),
)
# The letter's one button, in the composer's order (keys: ANNOUNCEMENT_CTAS).
CTA_MENU = (
    ('lounge', 'Open the lounge'),
    ('survivor', 'Survivor results'),
    ('docket', 'The Docket ledger'),
    ('none', 'No button'),
)


class Recipient(NamedTuple):
    """One resolved announcement recipient: email address + display name."""
    email: str
    name: str


def _wc_recipients(active_only):
    """World Cup recipients for the current season; active = picks submitted."""
    stmt = (
        select(WorldCupEnrollment)
        .filter_by(season_year=WC_SEASON_YEAR)
        .options(joinedload(WorldCupEnrollment.user))
    )
    if active_only:
        stmt = stmt.filter_by(picks_submitted=True)
    enrollments = db.session.execute(stmt).scalars().all()
    return [
        Recipient(e.user.email, e.get_display_name())
        for e in enrollments if e.user and e.user.email
    ]


def _cfb_recipients(active_only):
    """CFB Survivor recipients for the current season; active = not eliminated."""
    season = current_app.config.get('CFB_SEASON_YEAR', 2026)
    stmt = (
        select(CfbEnrollment)
        .filter_by(season_year=season)
        .options(joinedload(CfbEnrollment.user))
    )
    if active_only:
        stmt = stmt.filter_by(is_eliminated=False)
    enrollments = db.session.execute(stmt).scalars().all()
    return [
        Recipient(e.user.email, e.get_display_name())
        for e in enrollments if e.user and e.user.email
    ]


def _golf_recipients(active_only):
    """Golf recipients for the current season.

    Golf has no elimination/withdrawal concept, so active == enrolled and
    ``active_only`` is accepted but ignored.
    """
    season = current_app.config.get('SEASON_YEAR', 2026)
    stmt = (
        select(GolfEnrollment)
        .filter_by(season_year=season)
        .options(joinedload(GolfEnrollment.user))
    )
    enrollments = db.session.execute(stmt).scalars().all()
    return [
        Recipient(e.user.email, e.user.get_display_name())
        for e in enrollments if e.user and e.user.email
    ]


def _docket_recipients(active_only):
    """Docket recipients for the current season.

    The Docket has no elimination concept (missed weeks score 0 and the
    season continues), so active == enrolled and ``active_only`` is
    accepted but ignored.
    """
    stmt = (
        select(DocketEnrollment)
        .filter_by(season_year=DOCKET_SEASON_YEAR)
        .options(joinedload(DocketEnrollment.user))
    )
    enrollments = db.session.execute(stmt).scalars().all()
    return [
        Recipient(e.user.email, e.get_display_name())
        for e in enrollments if e.user and e.user.email
    ]


_RESOLVERS = {
    'worldcup': _wc_recipients,
    'cfb': _cfb_recipients,
    'docket': _docket_recipients,
    'golf': _golf_recipients,
}


def resolve_recipients(audiences, active_only):
    """Resolve (email, name) recipients for the chosen games.

    ``audiences`` is a list of registry slugs; the union is deduplicated by
    lowercased email, first occurrence wins, in registry order.
    """
    chosen = set(audiences)
    seen = set()
    recipients = []
    for entry in GAMES:
        if entry.slug not in chosen:
            continue
        for r in _RESOLVERS[entry.slug](active_only):
            key = r.email.strip().lower()
            if key and key not in seen:
                seen.add(key)
                recipients.append(r)
    return recipients


def _cta(key):
    """The letter's button for a CTA key, or None for no button."""
    base = site_url()
    return {
        'lounge': ('Open the lounge', f'{base}/'),
        'survivor': ('See the Survivor results', f'{base}/cfb/results'),
        'docket': ('See the ledger', f'{base}/docket/ledger'),
        'none': None,
    }[key]


def render_announcement(subject, body_text, *, headline=None, preheader=None,
                        cta='lounge'):
    """Render the announcement as a Club Letter. Returns (plain_body, html_body).

    The admin's markup becomes the letter's blocks through
    ``utils.letter_markup.parse`` (plain text still renders as it always
    did: a blank line starts a paragraph, a newline is a ``<br>``,
    everything escaped once), live boards included. The headline defaults
    to the subject. Club business, so the button is the trophy gold and the
    eyebrow carries no game accent. Raises ``MarkupError`` listing every
    mistake in the body.
    """
    letter = Letter(
        subject=subject,
        headline=headline or subject,
        eyebrow='From the Commish',
        preheader=preheader or '',
        extras=parse(body_text, BOARDS),
        cta=_cta(cta),
    )
    return render_letter(letter)


def _form_values():
    """The composer's submitted values, stripped (body newline-normalized),
    echoed back to the template on any error."""
    def text(name):
        return (request.form.get(name) or '').strip()
    return {
        'audiences': [slug for slug in request.form.getlist('audiences') if slug],
        'recipient_filter': text('recipient_filter'),
        'subject': text('subject'),
        'headline': text('headline'),
        'preheader': text('preheader'),
        'cta': text('cta') or 'lounge',
        'body_text': (request.form.get('body_text') or '').replace('\r\n', '\n').strip(),
    }


def _new_values():
    """A fresh composer: addressed to every open game, the lounge button."""
    return {
        'audiences': [entry.slug for entry in GAMES if entry.status == 'open'],
        'recipient_filter': 'all', 'subject': '', 'headline': '',
        'preheader': '', 'cta': 'lounge', 'body_text': '',
    }


def _values_of(announcement):
    return {
        'audiences': announcement.audience_list,
        'recipient_filter': announcement.recipient_filter,
        'subject': announcement.subject,
        'headline': announcement.headline or '',
        'preheader': announcement.preheader or '',
        'cta': announcement.cta,
        'body_text': announcement.body,
    }


def _errors(values, *, complete):
    """What stops these values being stored (always checked) or sent
    (``complete``: preview, test and send need a subject, a body, and at
    least one game)."""
    errors = []
    valid_games = {entry.slug for entry in GAMES}
    if any(slug not in valid_games for slug in values['audiences']):
        errors.append('Pick a valid audience.')
    elif complete and not values['audiences']:
        errors.append('Pick at least one game to send to.')
    if values['recipient_filter'] not in _VALID_FILTERS:
        errors.append('Pick a valid recipient filter.')
    if values['cta'] not in ANNOUNCEMENT_CTAS:
        errors.append('Pick a valid button.')
    for key, label in (('subject', 'Subject'), ('headline', 'Headline'),
                       ('preheader', 'Inbox preview')):
        if len(values[key]) > MAX_SUBJECT:
            errors.append(f'{label} must be {MAX_SUBJECT} characters or fewer.')
    if len(values['body_text']) > MAX_BODY:
        errors.append(f'Body must be {MAX_BODY} characters or fewer.')
    if complete and not values['subject']:
        errors.append('Subject is required.')
    if complete and not values['body_text']:
        errors.append('Body is required.')
    return errors


def _save(announcement, values):
    """Store the composer's values on a draft (a new one when ``None``).

    An existing draft is re-read under a row lock first, so a save racing a
    send in another tab either lands before the claim or sees the row sent
    and writes nothing (returns None): a sent record never changes.
    """
    if announcement is None:
        announcement = Announcement(created_by_id=current_user.id)
        db.session.add(announcement)
    else:
        db.session.refresh(announcement, with_for_update=True)
        if announcement.is_sent:
            db.session.rollback()
            return None
    chosen = set(values['audiences'])
    announcement.audiences = ','.join(
        entry.slug for entry in GAMES if entry.slug in chosen)
    announcement.recipient_filter = values['recipient_filter']
    announcement.subject = values['subject']
    announcement.headline = values['headline'] or None
    announcement.preheader = values['preheader'] or None
    announcement.cta = values['cta']
    announcement.body = values['body_text']
    db.session.commit()
    return announcement


def _render(values):
    return render_announcement(
        values['subject'], values['body_text'], headline=values['headline'],
        preheader=values['preheader'], cta=values['cta'])


def _safe_send(to_addr, subject, plain, html):
    """One recipient's failure must never abort the send loop."""
    try:
        return send_platform_email(to_addr, subject, plain, html)
    except Exception:
        logger.exception('Announce send failed for %s', to_addr)
        return False


def _page(announcement, values, preview=None):
    drafts = db.session.scalars(
        select(Announcement).where(Announcement.sent_at.is_(None))
        .order_by(Announcement.updated_at.desc())).all()
    sent = db.session.scalars(
        select(Announcement).where(Announcement.sent_at.is_not(None))
        .order_by(Announcement.sent_at.desc()).limit(25)).all()
    names = {entry.slug: entry.display_name for entry in GAMES}

    def audience_label(item):
        return (' + '.join(names[slug] for slug in item.audience_list)
                or 'No games picked')

    return render_template(
        'admin/announce.html',
        announcement=announcement, form_data=values, preview=preview,
        audiences=list(names.items()), audience_label=audience_label,
        when=format_deadline_short, cta_menu=CTA_MENU, board_menu=BOARD_MENU,
        drafts=drafts, sent=sent,
    )


def _here(announcement):
    return redirect(url_for('admin.announce', announcement_id=announcement.id))


def _duplicate(source):
    copy = Announcement(
        created_by_id=current_user.id, subject=source.subject,
        headline=source.headline, preheader=source.preheader, cta=source.cta,
        audiences=source.audiences, recipient_filter=source.recipient_filter,
        body=source.body,
    )
    db.session.add(copy)
    db.session.commit()
    flash('Copied into a new draft.', 'success')
    return _here(copy)


def claim_for_send(announcement_id, recipient_count, plain, html):
    """Mark a draft sent, storing the copy that goes out, if and only if
    nobody has yet: a conditional UPDATE on ``sent_at IS NULL``, committed.
    A second tab or a double click finds the row claimed (on Postgres it
    waits on the first claim's row lock, then re-reads) and gets False.
    """
    claimed = db.session.execute(
        update(Announcement)
        .where(Announcement.id == announcement_id,
               Announcement.sent_at.is_(None))
        .values(sent_at=datetime.now(UTC), recipient_count=recipient_count,
                sent_html=html, sent_plain=plain)
    ).rowcount
    db.session.commit()
    return claimed == 1


def _send(announcement, recipients, plain, html):
    """Claim the draft, then mail every recipient; the archive keeps
    exactly the copy that was mailed."""
    if not claim_for_send(announcement.id, len(recipients), plain, html):
        flash('This announcement already went out; nothing was sent twice.',
              'warning')
        return _here(announcement)

    subject = announcement.subject
    sent = sum(1 for r in recipients if _safe_send(r.email, subject, plain, html))
    db.session.execute(update(Announcement)
                       .where(Announcement.id == announcement.id)
                       .values(sent_count=sent))
    db.session.commit()
    failed = len(recipients) - sent
    logger.info('Announce #%d: %s sent %r to %d/%d (audiences=%s, filter=%s)',
                announcement.id, current_user.username, subject, sent,
                len(recipients), announcement.audiences,
                announcement.recipient_filter)
    if failed:
        flash(f'Sent {sent} of {len(recipients)}: {failed} failed, check the '
              f'logs.', 'warning')
    else:
        flash(f'Sent {sent} of {len(recipients)} announcement '
              f'email{"s" if sent != 1 else ""}.', 'success')
    return _here(announcement)


@admin_bp.route('/announce', methods=['GET', 'POST'])
@admin_bp.route('/announce/<int:announcement_id>', methods=['GET', 'POST'])
@admin_required
def announce(announcement_id=None):
    """The recap desk: compose, save, preview, test-send, and mass-send.

    Every POST that can be stored saves the draft first, so no work is lost
    to a markup mistake. POST branches on ``action``: ``save`` stores and
    redirects (PRG); ``preview`` also resolves the recipients and reveals
    the send buttons; ``test`` sends only to the composing admin; ``send``
    claims the draft and mass-sends (PRG to the sent record);
    ``duplicate`` copies any announcement into a new draft; ``delete``
    removes a draft (the guarded destructive branch). A sent announcement
    is read-only: only ``duplicate`` acts on it.
    """
    announcement = (db.get_or_404(Announcement, announcement_id)
                    if announcement_id is not None else None)
    if request.method == 'GET':
        values = _values_of(announcement) if announcement else _new_values()
        return _page(announcement, values)

    action = request.form.get('action', 'preview')
    if action == 'duplicate' and announcement is not None:
        return _duplicate(announcement)
    if announcement is not None and announcement.is_sent:
        flash('This announcement already went out. Copy it into a new draft '
              'to reuse it.', 'warning')
        return _here(announcement)
    if action == 'delete':
        if announcement is not None:
            # Conditional, like the claim: a draft another tab just sent is
            # a sent record now, and a stale tab never deletes it.
            deleted = db.session.execute(
                delete(Announcement)
                .where(Announcement.id == announcement.id,
                       Announcement.sent_at.is_(None))
            ).rowcount
            db.session.commit()
            if not deleted:
                flash('This announcement already went out, so it is kept.',
                      'warning')
                return _here(announcement)
            flash('Draft deleted.', 'success')
        return redirect(url_for('admin.announce'))

    values = _form_values()
    errors = _errors(values, complete=False)
    if errors:
        for message in errors:
            flash(message, 'error')
        return _page(announcement, values)
    saved = _save(announcement, values)
    if saved is None:
        flash('This announcement already went out. Copy it into a new draft '
              'to reuse it.', 'warning')
        return _here(announcement)
    announcement = saved
    if action == 'save':
        flash('Draft saved.', 'success')
        return _here(announcement)

    errors = _errors(values, complete=True)
    if not errors:
        try:
            plain, html = _render(values)
        except MarkupError as exc:
            errors = exc.errors
    if errors:
        for message in errors:
            flash(message, 'error')
        return _page(announcement, values)

    recipients = resolve_recipients(values['audiences'],
                                    values['recipient_filter'] == 'active')
    if action == 'send':
        if recipients:
            return _send(announcement, recipients, plain, html)
        flash('No recipients matched that audience.', 'warning')
    elif action == 'test':
        if _safe_send(current_user.email, f'[TEST] {values["subject"]}',
                      plain, html):
            flash(f'Test email sent to {current_user.email}.', 'success')
        else:
            flash('Test email failed. Check the logs.', 'error')

    return _page(announcement, values, preview={
        'count': len(recipients),
        'sample_names': [r.name for r in recipients[:10]],
        'preview_html': html,
        'plain_body': plain,
    })


@admin_bp.route('/announce/render', methods=['POST'])
@admin_required
def announce_render():
    """The composer's live preview: the letter as it stands, as JSON
    ``{html, plain, errors}``. Stores nothing and sends nothing; a blank
    subject previews under a stand-in headline."""
    values = _form_values()
    values['subject'] = values['subject'][:MAX_SUBJECT] or 'Your headline here'
    values['headline'] = values['headline'][:MAX_SUBJECT]
    values['preheader'] = values['preheader'][:MAX_SUBJECT]
    values['body_text'] = values['body_text'][:MAX_BODY]
    if values['cta'] not in ANNOUNCEMENT_CTAS:
        values['cta'] = 'lounge'
    try:
        plain, html = _render(values)
    except MarkupError as exc:
        return jsonify(html=None, plain=None, errors=exc.errors)
    return jsonify(html=html, plain=plain, errors=[])
