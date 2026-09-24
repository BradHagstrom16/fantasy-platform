"""
Fantasy Sports Platform - Editorial Content
=============================================
Admin-editable editorial copy for platform surfaces. Currently the
home-page "From the Commish" note, which previously lived as hardcoded
prose in `core/main/templates/main/_commish_note.html`.

The note is keyed by home-page state (`pre` / `live` / `post`) so the
Commish can speak to the tournament moment. A *missing* row falls back to
``COMMISH_NOTE_DEFAULTS`` (the original hardcoded prose), so the home page
renders identical copy until an admin edits it. A *stored* row is
authoritative — including a blank one, which an admin saves to intentionally
suppress that state's note.
"""
from datetime import UTC, datetime

from sqlalchemy import select

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
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self):
        return f'<CommishNote state={self.state!r}>'


def commish_note_body(state: str) -> str:
    """Return the raw note body for ``state``.

    A stored row is authoritative, even when blank — that's how an admin
    intentionally suppresses the note for a state (a blank body yields no
    paragraphs in ``commish_note_paragraphs``). Only a *missing* row falls
    back to ``COMMISH_NOTE_DEFAULTS``.
    """
    row = db.session.execute(
        select(CommishNote).filter_by(state=state)
    ).scalars().first()
    if row is not None:
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


# Where an announcement's one button points (core/admin/announce.py builds
# the URL). Club business, so every choice wears the club gold.
ANNOUNCEMENT_CTAS = ('lounge', 'survivor', 'docket', 'none')


class Announcement(db.Model):
    """One Commish announcement: a draft until it is sent, then the record
    of what went out (the sent archive). Status is derived from
    ``sent_at``, never stored: a row with ``sent_at`` set is immutable, and
    the send claims it with a conditional UPDATE so it can go out once.
    """
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False, default='')
    # The letter's H1; None means the subject is the headline.
    headline = db.Column(db.String(200), nullable=True)
    # The inbox preview line (Letter.preheader); None means none.
    preheader = db.Column(db.String(200), nullable=True)
    cta = db.Column(db.String(16), nullable=False, default='lounge')
    # Registry slugs, comma-joined ('cfb,docket'), deduplicated at send.
    audiences = db.Column(db.String(64), nullable=False, default='')
    recipient_filter = db.Column(db.String(8), nullable=False, default='all')
    # The announcement markup (utils/letter_markup.py).
    body = db.Column(db.Text, nullable=False, default='')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                              nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(UTC),
                           onupdate=lambda: datetime.now(UTC))
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    recipient_count = db.Column(db.Integer, nullable=True)
    sent_count = db.Column(db.Integer, nullable=True)
    # The letter exactly as it went out: live boards re-read the database
    # on every render, so the archive keeps the sent copy, not a re-render.
    sent_html = db.Column(db.Text, nullable=True)
    sent_plain = db.Column(db.Text, nullable=True)

    created_by = db.relationship('User')

    @property
    def is_sent(self) -> bool:
        return self.sent_at is not None

    @property
    def audience_list(self) -> list[str]:
        return [slug for slug in self.audiences.split(',') if slug]

    def __repr__(self):
        state = 'sent' if self.is_sent else 'draft'
        return f'<Announcement {self.id} {state} {self.subject!r}>'
