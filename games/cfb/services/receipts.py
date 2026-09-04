"""CFB Survivor — the pick receipt (Brad's ruling 2026-09-04).

One Club Letter every time a member makes or changes their pick: the team
and its number, when it kicks off, when picks lock, and the way back to the
pick page. A member who wonders whether the pick went through has it in
their inbox; a change says it is a change, so the old receipt cannot be
mistaken for the standing pick.

Sending never gates the pick: the route commits first, then asks for the
mail, and ``send_platform_email`` returns False rather than raising. There
is no de-dup and no flag: a change is a new receipt on purpose. Autopicks
are not receipts; the weekly recap covers them.
"""
import logging

from flask import current_app

from games.cfb.services.payment import payment_nudge_for
from games.cfb.utils import format_deadline_short, get_week_display_name
from utils.email import send_platform_email
from utils.email_layout import Letter, render_letter, tab_block

logger = logging.getLogger(__name__)


def pick_label(team, game) -> str:
    """'Navy -7.0' as the pick page prints it; the bare name without a line."""
    spread = game.get_spread_for_team(team.id) if game else None
    return team.name if spread is None else f'{team.name} {spread:+.1f}'


def pick_receipt_letter(*, week_name, week_number, label, kickoff_short,
                        deadline_short, changed, nudge, season_year,
                        site_url) -> Letter:
    """The receipt as a Club Letter (personal, so it still keeps the
    broadcast shape: the pick leads the fact block, the lock closes it)."""
    if changed:
        subject = f'Pick changed: CFB Survivor, {week_name}'
        lede = [f'Your {week_name} pick changed. This is the one on file now.']
    else:
        subject = f'Your pick is in: CFB Survivor, {week_name}'
        lede = [f'Your {week_name} pick is on file.']
    lede.append('Change it any time before picks lock; once its game kicks '
                'off, the call is final for the week.')
    return Letter(
        subject=subject,
        headline=f'Your {week_name} pick: {label}',
        eyebrow=f'CFB Survivor · {week_name}',
        game_slug='cfb',
        season=season_year,
        preheader=f'{label}. Picks lock {deadline_short}.',
        lede=lede,
        facts=[('Pick', label),
               ('Kickoff', kickoff_short),
               ('Picks lock', deadline_short)],
        cta=('See your pick', f'{site_url}/cfb/pick/{week_number}'),
        supporting=['Each team can be used once all season.'],
        notes=[tab_block(nudge, 'cfb')],
    )


def send_pick_receipt(user, enrollment, week, team, game, *,
                      changed: bool) -> bool:
    """Mail the member their pick. Returns whether the send was accepted."""
    if not user.email:
        return False
    config = current_app.config
    receipt = pick_receipt_letter(
        week_name=get_week_display_name(week),
        week_number=week.week_number,
        label=pick_label(team, game),
        kickoff_short=format_deadline_short(game.game_time if game else None),
        deadline_short=format_deadline_short(week.deadline),
        changed=changed,
        nudge=payment_nudge_for(enrollment, bool(user.is_admin)),
        season_year=config.get('CFB_SEASON_YEAR', 2026),
        site_url=config.get('SITE_URL', 'http://localhost:5000').rstrip('/'),
    )
    plain, html = render_letter(receipt)
    sent = send_platform_email(user.email, receipt.subject, plain, html)
    if sent:
        logger.info('CFB pick receipt sent to user %s for week %s',
                    user.id, week.week_number)
    else:
        logger.warning('CFB pick receipt to user %s was not accepted',
                       user.id)
    return sent
