"""
Fantasy Sports Platform - Admin Announce
==========================================
Platform-level admin: compose and mass-send an announcement email to a
game's enrolled members (or every game, deduplicated) via the browser.
"""
import logging
from typing import NamedTuple

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.admin import admin_bp
from core.admin.routes import admin_required
from extensions import db
from games.cfb.models import CfbEnrollment
from games.docket.models import DocketEnrollment
from games.docket.services.weeks import SEASON_YEAR as DOCKET_SEASON_YEAR
from games.golf.models import GolfEnrollment
from games.registry import GAMES
from games.worldcup.constants import SEASON_YEAR as WC_SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from utils.email import send_platform_email
from utils.email_layout import Letter, paragraphs_block, render_letter, site_url

logger = logging.getLogger(__name__)

MAX_SUBJECT = 200
MAX_BODY = 10_000

_VALID_FILTERS = ('all', 'active')


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


def resolve_recipients(audience, active_only):
    """Resolve (email, name) recipients for an audience.

    ``audience`` is a registry slug or ``'all'`` (union of every game,
    deduplicated by lowercased email — first occurrence wins, registry order).
    """
    slugs = [entry.slug for entry in GAMES] if audience == 'all' else [audience]
    seen = set()
    recipients = []
    for slug in slugs:
        for r in _RESOLVERS[slug](active_only):
            key = r.email.strip().lower()
            if key and key not in seen:
                seen.add(key)
                recipients.append(r)
    return recipients


def _clean_form():
    """Validate the compose form. Returns (form_data, errors).

    ``form_data`` always echoes the submitted values back (stripped subject,
    newline-normalized body) so the template can repopulate on error.
    """
    form_data = {
        'audience': (request.form.get('audience') or '').strip(),
        'recipient_filter': (request.form.get('recipient_filter') or '').strip(),
        'subject': (request.form.get('subject') or '').strip(),
        'body_text': (request.form.get('body_text') or '').replace('\r\n', '\n').strip(),
    }
    errors = []
    valid_audiences = {entry.slug for entry in GAMES} | {'all'}
    if form_data['audience'] not in valid_audiences:
        errors.append('Pick a valid audience.')
    if form_data['recipient_filter'] not in _VALID_FILTERS:
        errors.append('Pick a valid recipient filter.')
    if not form_data['subject']:
        errors.append('Subject is required.')
    elif len(form_data['subject']) > MAX_SUBJECT:
        errors.append(f'Subject must be {MAX_SUBJECT} characters or fewer.')
    if not form_data['body_text']:
        errors.append('Body is required.')
    elif len(form_data['body_text']) > MAX_BODY:
        errors.append(f'Body must be {MAX_BODY} characters or fewer.')
    return form_data, errors


def render_announcement(subject, body_text):
    """Render the announcement as a Club Letter. Returns (plain_body, html_body).

    The admin's free text becomes a ``paragraphs_block`` (a blank line starts
    a paragraph, a single newline is a ``<br>``, everything escaped once);
    the subject is the headline. Club business, so the CTA is the trophy
    gold and the eyebrow carries no game accent.
    """
    letter = Letter(
        subject=subject,
        headline=subject,
        eyebrow='From the Commish',
        extras=[paragraphs_block(body_text)],
        cta=('Open the lounge', site_url() + '/'),
    )
    return render_letter(letter)


def _safe_send(to_addr, subject, plain, html):
    """One recipient's failure must never abort the send loop."""
    try:
        return send_platform_email(to_addr, subject, plain, html)
    except Exception:
        logger.exception('Announce send failed for %s', to_addr)
        return False


@admin_bp.route('/announce', methods=['GET', 'POST'])
@admin_required
def announce():
    """Compose, preview, test-send, and mass-send an announcement email.

    POST branches on ``action``: ``preview`` re-renders with the resolved
    recipient count + rendered email; ``test`` sends only to the composing
    admin; ``send`` mass-sends and redirects (PRG). Validation failures
    re-render the form with the submitted values intact.
    """
    audiences = [(entry.slug, entry.display_name) for entry in GAMES]
    audiences.append(('all', 'All Games'))
    form_data = {
        'audience': 'worldcup', 'recipient_filter': 'all',
        'subject': '', 'body_text': '',
    }
    preview = None

    if request.method == 'POST':
        action = request.form.get('action', 'preview')
        form_data, errors = _clean_form()
        if errors:
            for message in errors:
                flash(message, 'error')
        else:
            active_only = form_data['recipient_filter'] == 'active'
            recipients = resolve_recipients(form_data['audience'], active_only)
            plain, html = render_announcement(
                form_data['subject'], form_data['body_text'],
            )

            if action == 'send':
                if not recipients:
                    flash('No recipients matched that audience.', 'warning')
                else:
                    sent = sum(
                        1 for r in recipients
                        if _safe_send(r.email, form_data['subject'], plain, html)
                    )
                    failed = len(recipients) - sent
                    logger.info(
                        'Announce: %s sent %r to %d/%d (audience=%s, filter=%s)',
                        current_user.username, form_data['subject'],
                        sent, len(recipients),
                        form_data['audience'], form_data['recipient_filter'],
                    )
                    if failed:
                        flash(
                            f'Sent {sent} of {len(recipients)}: '
                            f'{failed} failed, check the logs.',
                            'warning',
                        )
                    else:
                        flash(
                            f'Sent {sent} of {len(recipients)} announcement '
                            f'email{"s" if sent != 1 else ""}.',
                            'success',
                        )
                    return redirect(url_for('admin.announce'))

            if action == 'test':
                ok = _safe_send(
                    current_user.email, f'[TEST] {form_data["subject"]}',
                    plain, html,
                )
                if ok:
                    flash(f'Test email sent to {current_user.email}.', 'success')
                else:
                    flash('Test email failed. Check the logs.', 'error')

            preview = {
                'count': len(recipients),
                'sample_names': [r.name for r in recipients[:10]],
                'preview_html': html,
                'plain_body': plain,
            }

    return render_template(
        'admin/announce.html',
        audiences=audiences, form_data=form_data, preview=preview,
    )
