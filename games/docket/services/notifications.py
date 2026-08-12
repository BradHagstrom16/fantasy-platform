"""The Docket — admin-ruling notifications.

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
(games/<game>/services/reminders.py); transport is the shared helper.
"""
import logging

from flask import current_app
from markupsafe import Markup

from utils.email import send_platform_email

logger = logging.getLogger(__name__)

# Literal, not url_for: these run from the CLI and from timers as well as
# from a request, and url_for needs a request context or SERVER_NAME. Every
# other game's email builder composes SITE_URL + a path for the same reason.
SHEET_PATH = '/docket/'


def _sheet_url():
    """Absolute pick-sheet link for an email body."""
    base = current_app.config.get(
        'SITE_URL', 'http://localhost:5000').rstrip('/')
    return f'{base}{SHEET_PATH}'


def _side_phrase(pick, game):
    """'Over 51.5' / 'Nebraska -3.5' — the player's own side, their number."""
    if pick.market == 'total':
        label = 'Over' if pick.side == 'over' else 'Under'
        return f'{label} {pick.line_value:g}'
    team = game.home_team if pick.side == 'home' else game.away_team
    number = pick.line_value if pick.side == 'home' else -pick.line_value
    return f'{team} {"PK" if pick.line_value == 0 else f"{number:+g}"}'


def _send(recipients, subject, build_body):
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


def _wrap(plain_lines, html_lines):
    """Paragraph pairs -> (plain body, HTML body).

    Plain and HTML are built from SEPARATE line lists rather than deriving
    one from the other, so every dynamic value (an admin's free-text reason,
    a team name, a bookmaker key) is escaped exactly once on the HTML side
    via Markup.format while the plain side stays literal. Table layout with
    inline styles is the platform's Gmail-safe shape; this message is a
    short paragraph set, so paragraphs in one cell are enough.
    """
    plain = '\n\n'.join(plain_lines)
    body = ''.join(
        f'<p style="margin:0 0 14px;font-family:Georgia,serif;'
        f'font-size:15px;line-height:1.5;color:#1C1730;">{line}</p>'
        for line in html_lines)
    html = (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="background:#F3EFE6;padding:24px 0;">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" '
        'cellspacing="0" style="max-width:560px;background:#FFFFFF;'
        'border-radius:12px;padding:28px;">'
        f'<tr><td>{body}</td></tr>'
        '</table></td></tr></table>'
    )
    return plain, html


def notify_line_correction(correction, game, picks):
    """Tell the pickers of a corrected market that their number moved (D18).

    ``picks`` are that market's rows, already re-snapshotted. Each player is
    told their own side and the new number, and that they may change it
    until the deadline.
    """
    case = f'{game.away_team} at {game.home_team}'
    market = 'spread' if correction.market == 'spread' else 'total'
    subject = f'A line was corrected: {case}'
    link = _sheet_url()

    def build(user, pick):
        side = _side_phrase(pick, game)
        moved = (f'{case}: the {market} was {correction.old_value:g} '
                 f'({correction.old_book}) and is now '
                 f'{correction.new_value:g} ({correction.new_book}).')
        held = (f'Your side is now recorded as {side}. It will grade against '
                f'the corrected number. You may change or withdraw it until '
                f'the docket closes.')
        return _wrap([
            'The commissioner corrected a line on your sheet.',
            moved,
            f'Reason given: {correction.reason}',
            held,
            f'Your sheet: {link}',
        ], [
            Markup('The commissioner corrected a line on your sheet.'),
            Markup('<strong>{}</strong>: the {} was {} ({}) and is now '
                   '{} ({}).').format(
                       case, market, f'{correction.old_value:g}',
                       correction.old_book, f'{correction.new_value:g}',
                       correction.new_book),
            Markup('Reason given: {}').format(correction.reason),
            Markup('Your side is now recorded as <strong>{}</strong>. It '
                   'will grade against the corrected number. You may change '
                   'or withdraw it until the docket closes.').format(side),
            Markup('Your sheet: {}').format(link),
        ])

    return _send([(p.user, p) for p in picks], subject, build)


def notify_redesignation(week, new_game, old_game, users):
    """Tell the roster the tiebreaker case moved and their number was cleared.

    Clearing to the new game's default is the designation contract; players
    may resubmit until the deadline.
    """
    new_case = f'{new_game.away_team} at {new_game.home_team}'
    old_case = (f'{old_game.away_team} at {old_game.home_team}'
                if old_game is not None else 'the previous case')
    subject = f'The Week {week.week_number} tiebreaker case changed'
    link = _sheet_url()
    total = ('' if new_game.total_points is None
             else f' The line says {new_game.total_points:g}.')

    cleared = (f'Any combined-score prediction you had recorded has been '
               f'cleared. Until you enter a new one, the designated case\'s '
               f'locked total stands in for you.{total}')

    def build(user, _context):
        return _wrap([
            f'The tiebreaker case for Week {week.week_number} moved from '
            f'{old_case} to {new_case}.',
            cleared,
            'You may enter a number until the docket closes.',
            f'Your sheet: {link}',
        ], [
            Markup('The tiebreaker case for Week {} moved from '
                   '<strong>{}</strong> to <strong>{}</strong>.').format(
                       week.week_number, old_case, new_case),
            Markup('{}').format(cleared),
            Markup('You may enter a number until the docket closes.'),
            Markup('Your sheet: {}').format(link),
        ])

    return _send([(u, None) for u in users], subject, build)
