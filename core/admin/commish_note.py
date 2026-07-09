"""
Fantasy Sports Platform - Admin Commish Note
==============================================
Platform-level admin: edit the home-page "From the Commish" note per
home-page state (pre / live / post). Replaces hand-editing
`_commish_note.html` + redeploying. Body is plain text; blank lines start
new paragraphs (rendered by models.content.commish_note_paragraphs).
"""
import logging

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import select

from core.admin import admin_bp
from core.admin.routes import admin_required
from extensions import db
from models.content import (
    COMMISH_NOTE_STATES,
    CommishNote,
    commish_note_body,
)

logger = logging.getLogger(__name__)

MAX_BODY = 4_000

_STATE_LABELS = {
    'pre': 'Pre-Tournament',
    'live': 'Live Tournament',
    'post': 'Post-Tournament',
}


def _current_bodies():
    """Per-state body text for the form: stored value, else the default."""
    return {state: commish_note_body(state) for state in COMMISH_NOTE_STATES}


@admin_bp.route('/commish-note', methods=['GET', 'POST'])
@admin_required
def commish_note():
    """Edit the per-state "From the Commish" note.

    GET pre-fills each state's textarea with its stored body (or the default
    when unset). POST upserts one row per state and redirects (PRG). A blank
    body is allowed and intentionally suppresses that state's note on the home
    page. The post body may include a literal ``{champion}`` token, swapped for
    the champion's name when the home page renders the post state.
    """
    if request.method == 'POST':
        bodies = {}
        too_long = False
        for state in COMMISH_NOTE_STATES:
            body = (request.form.get(f'body_{state}') or '').replace('\r\n', '\n').strip()
            if len(body) > MAX_BODY:
                too_long = True
            bodies[state] = body

        if too_long:
            flash(f'Each note must be {MAX_BODY} characters or fewer.', 'error')
            return render_template(
                'admin/commish_note.html',
                states=COMMISH_NOTE_STATES, state_labels=_STATE_LABELS,
                bodies=bodies,
            )

        for state in COMMISH_NOTE_STATES:
            row = db.session.execute(
                select(CommishNote).filter_by(state=state)
            ).scalars().first()
            if row is None:
                row = CommishNote(state=state)
                db.session.add(row)
            row.body = bodies[state]
        db.session.commit()
        flash('Commish note saved.', 'success')
        return redirect(url_for('admin.commish_note'))

    return render_template(
        'admin/commish_note.html',
        states=COMMISH_NOTE_STATES, state_labels=_STATE_LABELS,
        bodies=_current_bodies(),
    )
