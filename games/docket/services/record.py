"""The Docket — the weekly record letter (Club Desk step 1).

"Here is your record for the week": the one letter the Docket never had
(docs/designs/unified-email.md). Personal mail, one per graded member,
built only from facts the game already persists and the room already
shows: W-L-P and points (the sheet's own tally, ``sheets.all_sheets``),
the week rank (``season_pass.week_standings``), the season rank and total
(``season_pass.season_ledger``), and the week's top sheet and purse (the
ledger's verdict + ``purse.season_purse``). Nothing here grades, re-grades,
or does pick math, so the letter cannot disagree with the ledger it links
to.

**Latch-driven, from the daily scores run only.** ``run_record_pass`` mails
every week that is graded (``default_error_tenths`` stamped) and not yet
``record_notified``, and latches the flag once at least one letter was
delivered (the reminders' reasoning: one bad address must not hold the
week open and re-mail everyone). Zero deliveries leave the latch open for
the next daily run. It never runs from ``try_grade_week``, the game-day
consumer (ADR-063: that pass sends no mail), the admin desk, or
``recalc`` — a regrade after the send issues no correction; the ledger
page is the truth.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import select

from extensions import db
from games.docket.models import DocketWeek
from games.docket.services.notifications import send_each
from games.docket.services.purse import season_purse
from games.docket.services.season_pass import season_ledger, week_standings
from games.docket.services.sheets import Tally, all_sheets
from games.docket.services.weeks import SEASON_YEAR, TOTAL_WEEKS
from games.docket.utils import now_utc, to_naive_utc
from utils.email_layout import Letter, render_letter, result_block, site_url

logger = logging.getLogger(__name__)

LEDGER_PATH = '/docket/ledger'
NO_TALLY = Tally(wins=0, losses=0, pushes=0, pending=0)


def ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st."""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def record_text(tally: Tally) -> str:
    """'6-2' / '6-1-1': the sheet's record without its pending suffix."""
    text = f'{tally.wins}-{tally.losses}'
    if tally.pushes:
        text += f'-{tally.pushes}'
    return text


def points_text(points: float) -> str:
    """'7 points' / '7.5 points' / '1 point'."""
    value = f'{points:g}'
    return f'{value} point' if value == '1' else f'{value} points'


@dataclass(frozen=True, slots=True)
class TopSheet:
    """The week's verdict as the letter states it: who topped the week, at
    what record, and whether the prize split."""
    names: tuple[str, ...]       # display names, ledger order
    record: str                  # the first winner's record ('7-1')
    split: bool


def record_letter(*, week_number, display_name, tally, points, week_rank,
                  roster_size, season_rank, season_points, top_sheet,
                  is_winner, weekly_prize, autopicked, ledger_url) -> Letter:
    """The record as a Club Letter (personal: greets by name).

    Digits in the headline (the room's register), words in the lede; three
    facts (this week, the week rank, the season) and the week around the
    docket as a result block. 0-8 and 8-0 get the same shape: no
    consolation copy, no celebration.
    """
    record = record_text(tally)
    lede = [f'The Week {week_number} docket is closed and every case is '
            f'decided.']
    if autopicked:
        lede.insert(0, 'Your sheet was filed from the locked lines.')

    if top_sheet.split:
        count = len(top_sheet.names)
        top_line = (f'{count} sheets at {top_sheet.record}; the purse is '
                    f'split')
        purse_line = f'${weekly_prize} split {count} ways'
    elif is_winner:
        top_line = f'You, {top_sheet.record}'
        purse_line = f'${weekly_prize} to you'
    else:
        top_line = f'{top_sheet.names[0]}, {top_sheet.record}'
        purse_line = f'${weekly_prize} to {top_sheet.names[0]}'

    supporting = []
    if week_number < TOTAL_WEEKS:
        supporting.append(f'The Week {week_number + 1} docket opens Tuesday '
                          f'morning.')

    return Letter(
        subject=f'Your record: The Docket, Week {week_number}',
        headline=f'Week {week_number}: {record}',
        eyebrow=f'The Docket · Week {week_number}',
        game_slug='docket',
        season=SEASON_YEAR,
        preheader=f'Week {week_number}: {record}, {ordinal(week_rank)} of '
                  f'{roster_size}.',
        greeting=display_name,
        lede=lede,
        facts=[
            (f'Week {week_number}', f'{record} · {points_text(points)}'),
            ('On the week', f'{ordinal(week_rank)} of {roster_size}'),
            ('Season', f'{ordinal(season_rank)} · {points_text(season_points)}'),
        ],
        extras=[result_block('Around the docket', [
            ('Top sheet', top_line),
            ('Weekly purse', purse_line),
        ])],
        cta=('See the ledger', ledger_url),
        supporting=supporting,
    )


def week_records(week, now_naive):
    """``(user, record_letter fields)`` per graded member of ``week``: THE
    shared reader (the record letter and the Tuesday Paper's Docket line
    both read it, so the two can never disagree).

    One read of each source for the whole roster, so the recipient's own
    line and the top sheet's record come from the same tallies. The roster
    is the week's as of its deadline (``week_standings``, ADR-048), which
    is exactly the population the grade covered.
    """
    standing = week_standings(week.week_number)
    if standing is None:
        # Graded with nobody on the roster at its deadline (ADR-047: the
        # marker is stamped, zero result rows): nobody to write to.
        return []
    ledger = season_ledger()
    sheets = {m.user_id: m for m in all_sheets(week, now_naive).members}
    season_by_user = {row.enrollment.user_id: row.standing
                      for row in ledger.rows}
    verdict = next(v for v in ledger.verdicts
                   if v.week_number == week.week_number)
    winner_ids = {e.user_id for e in verdict.winners}
    first = sheets[verdict.winners[0].user_id]
    top_sheet = TopSheet(
        names=tuple(e.get_display_name() for e in verdict.winners),
        record=record_text(first.tally or NO_TALLY),
        split=verdict.split,
    )
    weekly_prize = season_purse(len(standing.rows)).weekly_prize

    recipients = []
    for row in standing.rows:
        user_id = row.enrollment.user_id
        sheet = sheets[user_id]
        season = season_by_user[user_id]
        recipients.append((row.enrollment.user, {
            'week_number': week.week_number,
            'display_name': row.enrollment.get_display_name(),
            'tally': sheet.tally or NO_TALLY,
            'points': row.points,
            'week_rank': row.rank,
            'roster_size': len(standing.rows),
            'season_rank': season.rank,
            'season_points': season.total_points,
            'top_sheet': top_sheet,
            'is_winner': user_id in winner_ids,
            'weekly_prize': weekly_prize,
            'autopicked': any(line.is_autopick for line in sheet.lines
                              if not line.is_reserve),
        }))
    return recipients


def _send(week, recipients) -> int:
    subject = f'Your record: The Docket, Week {week.week_number}'
    ledger_url = f'{site_url()}{LEDGER_PATH}'

    def build(_user, fields):
        return render_letter(record_letter(ledger_url=ledger_url, **fields))

    return send_each(recipients, subject, build)


def send_record_letters(week, *, now=None) -> int:
    """Mail every graded member of ``week`` their record; return how many
    were accepted. The latch is the caller's (``run_record_pass``)."""
    return _send(week, week_records(week, to_naive_utc(now or now_utc())))


def pending_weeks():
    """Graded weeks whose record has not gone out, ascending."""
    return db.session.scalars(
        select(DocketWeek)
        .filter(DocketWeek.default_error_tenths.is_not(None),
                DocketWeek.record_notified.is_(False))
        .order_by(DocketWeek.week_number)).all()


def run_record_pass() -> list[dict]:
    """Mail and latch every pending week's record. One entry per week."""
    now_naive = to_naive_utc(now_utc())
    results = []
    for week in pending_weeks():
        recipients = week_records(week, now_naive)
        sent = _send(week, recipients)
        # Latched on any delivery, and on a week with nobody to write to
        # (an empty roster owes no letter and must not alert every day).
        latched = sent > 0 or not recipients
        if latched:
            week.record_notified = True
            db.session.commit()
        else:
            # Nothing was delivered: leave the latch open so the next daily
            # run retries. Recording here would swallow a mail outage.
            logger.error('Week %s: record letter reached nobody (%s recipients)',
                         week.week_number, len(recipients))
        results.append({'week_number': week.week_number,
                        'recipients': len(recipients), 'sent': sent,
                        'latched': latched})
    return results
