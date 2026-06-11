"""
Fantasy Sports Platform - Admin Announce
==========================================
Platform-level admin: compose and mass-send an announcement email to a
game's enrolled members (or every game, deduplicated) via the browser.
"""
import logging
import re
from typing import NamedTuple

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user
from markupsafe import escape
from sqlalchemy.orm import joinedload

from core.admin import admin_bp
from core.admin.routes import admin_required
from games.registry import GAMES
from games.worldcup.constants import SEASON_YEAR as WC_SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from games.cfb.models import CfbEnrollment
from games.golf.models import GolfEnrollment
from utils.email import send_platform_email

logger = logging.getLogger(__name__)

MAX_SUBJECT = 200
MAX_BODY = 10_000

_VALID_FILTERS = ('all', 'active')


class Recipient(NamedTuple):
    email: str
    name: str


def _wc_recipients(active_only):
    query = (
        WorldCupEnrollment.query
        .filter_by(season_year=WC_SEASON_YEAR)
        .options(joinedload(WorldCupEnrollment.user))
    )
    if active_only:
        query = query.filter_by(picks_submitted=True)
    return [
        Recipient(e.user.email, e.get_display_name())
        for e in query.all() if e.user and e.user.email
    ]


def _cfb_recipients(active_only):
    season = current_app.config.get('CFB_SEASON_YEAR', 2026)
    query = (
        CfbEnrollment.query
        .filter_by(season_year=season)
        .options(joinedload(CfbEnrollment.user))
    )
    if active_only:
        query = query.filter_by(is_eliminated=False)
    return [
        Recipient(e.user.email, e.get_display_name())
        for e in query.all() if e.user and e.user.email
    ]


def _golf_recipients(active_only):
    # Golf has no elimination/withdrawal concept — active == enrolled.
    season = current_app.config.get('SEASON_YEAR', 2026)
    query = (
        GolfEnrollment.query
        .filter_by(season_year=season)
        .options(joinedload(GolfEnrollment.user))
    )
    return [
        Recipient(e.user.email, e.user.get_display_name())
        for e in query.all() if e.user and e.user.email
    ]


_RESOLVERS = {
    'worldcup': _wc_recipients,
    'cfb': _cfb_recipients,
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


def _body_paragraphs(body_text):
    """Split body text into pre-escaped HTML paragraph fragments.

    Flask does NOT autoescape ``.j2`` templates, so each blank-line-separated
    block is escaped here before single newlines become ``<br>``.
    """
    return [
        str(escape(block)).replace('\n', '<br>')
        for block in re.split(r'\n\s*\n', body_text) if block.strip()
    ]


def render_announcement(subject, body_text):
    """Render the announcement email. Returns (plain_body, html_body).

    Requires a request context (external seal URL + asset_version context
    processor).
    """
    seal_url = url_for('static', filename='img/logo/seal-email.png', _external=True)
    plain = render_template('email/announcement_plain.txt', body_text=body_text)
    html = render_template(
        'email/announcement_html.j2',
        subject=subject,
        body_paragraphs=_body_paragraphs(body_text),
        seal_url=seal_url,
    )
    return plain, html


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
