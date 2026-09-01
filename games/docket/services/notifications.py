"""The Docket — admin-ruling notifications + the game's shared email plumbing.

Two rulings oblige the commissioner to tell players something changed under
them, and both come from the 2026-08-11 design SSoT:

- **D18** — a corrected line: the pickers of that market are told to
  re-decide, because their pick now grades against a different number.
- **Grading Clarifications, designation constraints** — a re-designated
  tiebreaker: every prediction for the week is cleared to the new game's
  default, so the whole roster is told they may resubmit.

Sending never gates the ruling. ``send_platform_email`` returns False rather
than raising (utils/email.py), and these functions mirror that: they report
how many messages went out and let the caller flash it. A mail outage must
not roll back an admin decision that has already been recorded.

Content assembly lives here per the platform convention
(games/<game>/services/reminders.py); transport is the shared helper, and
every message is a Club Letter (utils/email_layout.py, ADR-058): this module
supplies words, facts, and the sheet link, never markup. The copy is the
clerk's (DESIGN.md 6.7): the deadline line always states the literal time,
the ninth pick is "Reserve", the mark is "x2".

``sheet_url``, ``send_each``, ``letter``, and ``deadline_line`` are public
because the D24 deadline reminders (games/docket/services/reminders.py) send
through the same shape.
"""
import logging

from flask import current_app
from markupsafe import Markup

from games.docket.services.payment import payment_nudge_for
from games.docket.services.weeks import SEASON_YEAR
from utils.email import send_platform_email
from utils.email_layout import (
    Letter,
    format_deadline_short,
    render_letter,
    tab_block,
)

logger = logging.getLogger(__name__)

# Literal, not url_for: these run from the CLI and from timers as well as
# from a request, and url_for needs a request context or SERVER_NAME. Every
# other game's email builder composes SITE_URL + a path for the same reason.
SHEET_PATH = '/docket/'


def sheet_url():
    """Absolute pick-sheet link for an email body."""
    base = current_app.config.get(
        'SITE_URL', 'http://localhost:5000').rstrip('/')
    return f'{base}{SHEET_PATH}'


def letter(week, **fields) -> Letter:
    """A Docket letter: the eyebrow names the week, the accent is the stamp
    garnet, the footer names the season. ``fields`` are the Letter's own."""
    return Letter(eyebrow=f'The Docket · Week {week.week_number}',
                  game_slug='docket', season=SEASON_YEAR, **fields)


def deadline_line(week) -> str:
    """'Saturday, Sep 5 · 11:00 AM CT' for the week's deadline.

    A render boundary, so this is one of the sanctioned places a D6 naive-UTC
    column becomes America/Chicago (bridge_sheet._format_ct is the other);
    the platform formatter reads naive input as UTC.
    """
    return format_deadline_short(week.deadline_at)


def _side_phrase(pick, game):
    """'Over 51.5' / 'Nebraska -3.5' — the player's own side, their number."""
    if pick.market == 'total':
        label = 'Over' if pick.side == 'over' else 'Under'
        return f'{label} {pick.line_value:g}'
    team = game.home_team if pick.side == 'home' else game.away_team
    number = pick.line_value if pick.side == 'home' else -pick.line_value
    return f'{team} {"PK" if pick.line_value == 0 else f"{number:+g}"}'


def send_each(recipients, subject, build_body):
    """Send one message per recipient; return how many were accepted.

    The failure log carries the user id, never the address: these lines land
    in the journal on the droplet and a bounced send is not a reason to put
    a member's email in it.
    """
    sent = 0
    for user, context in recipients:
        if not user.email:
            continue
        plain, html = build_body(user, context)
        if send_platform_email(user.email, subject, plain, html):
            sent += 1
        else:
            logger.warning('Docket notification to user %s was not accepted',
                           user.id)
    return sent


def notify_line_correction(correction, game, picks, week):
    """Tell the pickers of a corrected market that their number moved (D18).

    ``picks`` are that market's rows, already re-snapshotted. Each player is
    told their own side and the new number, and that they may change it
    until the deadline. Personal mail, so it greets by name; the admin's
    free-text reason is escaped by the shell like every other string.
    """
    case = f'{game.away_team} at {game.home_team}'
    market = 'spread' if correction.market == 'spread' else 'total'
    old, new = f'{correction.old_value:g}', f'{correction.new_value:g}'
    subject = f'Line corrected: The Docket, Week {week.week_number}'
    link = sheet_url()

    def build(user, pick):
        side = _side_phrase(pick, game)
        return render_letter(letter(
            week,
            subject=subject,
            headline='A line on your sheet was corrected',
            preheader=f'{case}: the {market} is now {new}.',
            greeting=user.get_display_name(),
            lede=[
                Markup('<strong>{}</strong>: the {} was {} ({}) and is now '
                       '{} ({}).').format(case, market, old,
                                          correction.old_book, new,
                                          correction.new_book),
                f'Reason given: {correction.reason}',
            ],
            facts=[('Your side', side),
                   ('Grades against', f'{new} ({correction.new_book})')],
            cta=('Open your sheet', link),
            supporting=['You may change or withdraw it until the docket '
                        'closes.'],
        ))

    return send_each([(p.user, p) for p in picks], subject, build)


def notify_redesignation(week, new_game, old_game, users):
    """Tell the roster the tiebreaker case moved and their number was cleared.

    Clearing to the new game's default is the designation contract; players
    may resubmit until the deadline.
    """
    new_case = f'{new_game.away_team} at {new_game.home_team}'
    old_case = (f'{old_game.away_team} at {old_game.home_team}'
                if old_game is not None else 'the previous case')
    subject = f'Tiebreaker case changed: The Docket, Week {week.week_number}'
    link = sheet_url()
    facts = [('New case', new_case)]
    if new_game.total_points is not None:
        facts.append(('Line total', f'{new_game.total_points:g}'))
    cleared = ('Any combined-score prediction you had recorded has been '
               'cleared. Until you enter a new one, the designated case\'s '
               'locked total stands in for you.')

    def build(user, _context):
        return render_letter(letter(
            week,
            subject=subject,
            headline='The tiebreaker case moved',
            preheader=f'Now {new_case}. Enter a new number before the docket '
                      f'closes.',
            lede=[
                Markup('The tiebreaker case for Week {} moved from '
                       '<strong>{}</strong> to <strong>{}</strong>.').format(
                           week.week_number, old_case, new_case),
                cleared,
            ],
            facts=facts,
            cta=('Open your sheet', link),
            supporting=['You may enter a number until the docket closes.'],
        ))

    return send_each([(u, None) for u in users], subject, build)


def notify_picks_open(week, recipients):
    """Tell the roster that picks are open for a freshly imported week.

    The season-open announcement (not a deadline reminder): sent once per week,
    latched by the import run on ``DocketWeek.picks_open_notified``, to every
    roster member with the sheet link. ``recipients`` are ``(user,
    enrollment)`` pairs: a member who still owes the buy-in also gets the
    "Settle the tab" strip (gate: services/payment.py — unpaid only, never
    the Commish; ``None`` for the enrollment means no tab). Returns how many
    messages were accepted.
    """
    number = week.week_number
    subject = f'Picks are open: The Docket, Week {number}'
    link = sheet_url()
    deadline = deadline_line(week)

    def build(user, enrollment):
        nudge = payment_nudge_for(enrollment, bool(user.is_admin))
        return render_letter(letter(
            week,
            subject=subject,
            headline=f'The Week {number} docket is open',
            preheader=f'The docket closes {deadline}.',
            lede=[f'The Week {number} slate is posted and the lines are '
                  f'frozen. File eight sides, name your x2 (it scores '
                  f'double), and enter your number before the docket '
                  f'closes.'],
            facts=[('Deadline', deadline)],
            cta=('Open your sheet', link),
            supporting=['Anything still open when the docket closes is '
                        'filled for you from the locked lines. A case locks '
                        'at its own kickoff, so the early games close early.'],
            notes=[tab_block(nudge, 'docket')],
        ))

    return send_each(recipients, subject, build)
