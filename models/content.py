"""
Fantasy Sports Platform - Editorial Content
=============================================
Admin-editable editorial copy for platform surfaces. Currently the
home-page "From the Commish" note, which previously lived as hardcoded
prose in `core/main/templates/main/_commish_note.html`.

The note is keyed by home-page state (`pre` / `live` / `post`) so the
Commish can speak to the tournament moment. A missing or blank row falls
back to ``COMMISH_NOTE_DEFAULTS`` (the original hardcoded prose), so the
home page renders identical copy until an admin edits it.
"""
from datetime import datetime, timezone

from extensions import db

# Valid home-page states that carry a Commish note (the logged-out 'out'
# state has no narrative band). The post body may contain a ``{champion}``
# placeholder, substituted at render time with the champion's display name.
COMMISH_NOTE_STATES = ('pre', 'live', 'post')

COMMISH_NOTE_DEFAULTS = {
    'pre': (
        "Welcome to the Club, I hope you enjoy the site. Pass along any "
        "feedback that you have. World Cup tribute window is open until June "
        "11th. Pick your nine nations wisely, take your seat, and watch the "
        "action unfold. Fortune favors the bold."
    ),
    'live': (
        "The tournament runs and the ledger updates daily. Picks are sealed. "
        "Goals fall where they fall. The Commish will not entertain appeals, "
        "sympathies, or revisions to the roster. Watch your nations, watch the "
        "Club, and keep the trash talk inside the room."
    ),
    'post': (
        "The 2026 ledger is closed. {champion} lifted the trophy and the Club "
        "records it as such. Whatever your finish, the rivalry held, the picks "
        "paid out where they paid out, and the receipts are now part of the "
        "Club's history.\n\n"
        "Rest the legs. The Commish will be in touch when the next ledger opens."
    ),
}


class CommishNote(db.Model):
    """One editable "From the Commish" note body, keyed by home-page state."""
    __tablename__ = 'commish_notes'

    id = db.Column(db.Integer, primary_key=True)
    # 'pre' | 'live' | 'post' — one row per home-page state.
    state = db.Column(db.String(16), unique=True, nullable=False, index=True)
    # Plain text; blank lines separate paragraphs at render time.
    body = db.Column(db.Text, nullable=False, default='')
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f'<CommishNote state={self.state!r}>'


def commish_note_body(state: str) -> str:
    """Return the raw note body for ``state`` (DB row, else the default).

    Empty/whitespace bodies fall back to the default so a stored-but-blank
    row doesn't silently suppress the note (admins suppress intentionally by
    saving a blank body — see ``commish_note_paragraphs``).
    """
    row = CommishNote.query.filter_by(state=state).first()
    if row is not None:
        # A row that exists is authoritative, even when blank — that's how an
        # admin suppresses the note for a state.
        return row.body or ''
    return COMMISH_NOTE_DEFAULTS.get(state, '')


def commish_note_paragraphs(state: str, champion_team=None) -> list[str]:
    """Render the note for ``state`` into a list of paragraph strings.

    Splits on blank lines; collapses internal whitespace so each paragraph is
    a clean single string the template can autoescape into a ``<p>``. Returns
    ``[]`` when the body is empty (the template then suppresses the whole
    note). For the post state, substitutes the ``{champion}`` placeholder with
    the champion's display name (or a neutral phrase when none is set).
    """
    import re

    body = commish_note_body(state)
    if state == 'post':
        champion = champion_team.display_name if champion_team else 'The champion'
        body = body.replace('{champion}', champion)
    return [
        re.sub(r'\s+', ' ', block).strip()
        for block in re.split(r'\n\s*\n', body)
        if block.strip()
    ]
