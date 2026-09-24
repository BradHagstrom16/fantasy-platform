"""The Docket's live boards for the Commish's announcements.

``[[docket-week]]`` and ``[[docket-season]]`` in an announcement body
(core/admin/announce.py, utils/letter_markup.py) render through these
builders, read at render time from the stored results (they never grade).

The reveal guard: a board shows a GRADED week only (the default is the
latest graded week; ``week=N`` is refused until week N grades), so an
announcement can never show a sheet before its week is decided. A
``ValueError`` is the admin's error line, worded to follow the board's name.
"""
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketWeek
from games.docket.services.purse import season_purse
from games.docket.services.record import (
    around_the_docket,
    points_text,
    record_text,
    week_records,
)
from games.docket.services.season_pass import season_ledger
from games.docket.utils import now_utc, to_naive_utc
from utils.email_layout import result_block, stack_blocks
from utils.letter_markup import board_number

DEFAULT_TOP = 5


def _graded_week(args, *, allowed):
    number = board_number(args, 'week', allowed=allowed)
    if number is None:
        graded = season_ledger().week_numbers
        if not graded:
            raise ValueError('has no graded week to show yet.')
        number = graded[-1]
    week = db.session.scalar(select(DocketWeek).filter_by(week_number=number))
    if week is None:
        raise ValueError(f'has no Week {number}.')
    if week.default_error_tenths is None:
        raise ValueError(f'shows graded weeks only; Week {number} is not '
                         f'graded yet.')
    return week


def _wins(count):
    return '1 win' if count == 1 else f'{count} wins'


def docket_week(args):
    """One graded week: the top sheet and where the weekly purse went (the
    record letter's own rows), then the week's top ``top`` (default 5)."""
    week = _graded_week(args, allowed=('week', 'top'))
    top = board_number(args, 'top', allowed=('week', 'top'),
                       default=DEFAULT_TOP)
    records = week_records(week, to_naive_utc(now_utc()))
    if not records:
        raise ValueError(f'has no sheets in Week {week.week_number}.')
    first = records[0][1]
    ranked = sorted((fields for _user, fields in records),
                    key=lambda f: (f['week_rank'], f['display_name'].casefold()))
    return stack_blocks([
        result_block(f'Week {week.week_number} around the docket',
                     around_the_docket(first['top_sheet'],
                                       first['weekly_prize'])),
        result_block(f'Week {week.week_number}: the top {min(top, len(ranked))}', [
            (f'{f["week_rank"]}. {f["display_name"]}',
             f'{record_text(f["tally"])} · {points_text(f["points"])}')
            for f in ranked[:top]]),
    ])


def docket_season(args):
    """The season so far: the ledger's top ``top`` (default 5) on points,
    then the podium purse the season is playing for."""
    top = board_number(args, 'top', allowed=('top',), default=DEFAULT_TOP)
    ledger = season_ledger()
    if not ledger.is_graded:
        raise ValueError('has no graded week to show yet.')
    purse = season_purse(len(ledger.rows))
    return stack_blocks([
        result_block(f'The season after Week {ledger.week_numbers[-1]}', [
            (f'{row.standing.rank}. {row.enrollment.get_display_name()}',
             f'{points_text(row.standing.total_points)} · '
             f'{_wins(row.standing.wins)}')
            for row in ledger.rows[:top]]),
        result_block('The season purse', [
            (line.label, f'${line.dollars}') for line in purse.podium]),
    ])


BOARDS = {
    'docket-week': docket_week,
    'docket-season': docket_season,
}
