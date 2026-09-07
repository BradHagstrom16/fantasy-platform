"""The sheet behind each graded week, for the ledger's drawers.

A separate read from the season pass on purpose: `season_pass.py` reads
`docket_week` and `docket_week_result` and nothing else (D14-eng, DESIGN.md
9), so the ledger cannot quietly become a re-grade. This module reads picks
and games for GRADED weeks only — every side on them is revealed by
definition (the deadline has passed; All Sheets 7.13) — and prints each
line with All Sheets' own wording helpers, so the two surfaces never
disagree about a pick. Two queries whatever the roster or the season length.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.docket.models import DocketPick, DocketWeek
from games.docket.services.bridge_sheet import SPORT_LABELS
from games.docket.services.grading.snapshots import BACKUP_SLOT
from games.docket.services.picks import describe_pick
from games.docket.services.sheets import _caption, _result, _snapshot


@dataclass(frozen=True, slots=True)
class HistoryLine:
    """One pick on a graded week, as the sheet printed it."""
    slot: int
    is_reserve: bool
    is_best: bool
    is_auto_best: bool
    is_autopick: bool
    sport: str
    caption: str                 # 'Idaho Vandals at Utah Utes'
    kickoff: datetime            # naive UTC
    pick: str                    # 'Utah Utes -3.5' / 'Over 51.5'
    result: str | None           # 'win' | 'loss' | 'push' | 'no_contest' | None
    final_score: str | None      # 'away-home'


def pick_history(week_numbers, user_ids) -> dict[int, dict[int, tuple[HistoryLine, ...]]]:
    """{user_id: {week_number: lines}} for the given GRADED weeks.

    Lines are kickoff-ordered with the reserve last (All Sheets' order).
    Callers pass `SeasonLedger.week_numbers`, never an open week: a week
    that has not graded is not a ledger fact, and its sealed sides belong
    to the sheet's own reveal rule.
    """
    week_numbers = tuple(week_numbers)
    user_ids = tuple(user_ids)
    if not week_numbers or not user_ids:
        return {}
    weeks = db.session.scalars(
        select(DocketWeek).filter(DocketWeek.week_number.in_(week_numbers))).all()
    number_by_week_id = {week.id: week.week_number for week in weeks}
    picks = db.session.scalars(
        select(DocketPick)
        .filter(DocketPick.week_id.in_(list(number_by_week_id)),
                DocketPick.user_id.in_(user_ids))
        .options(joinedload(DocketPick.game))
    ).all()

    keyed: dict[int, dict[int, list]] = {}
    for pick in picks:
        game = pick.game
        snap = _snapshot(game)
        is_reserve = pick.slot == BACKUP_SLOT
        line = HistoryLine(
            slot=pick.slot,
            is_reserve=is_reserve,
            is_best=pick.is_best,
            is_auto_best=pick.is_auto_best,
            is_autopick=pick.is_autopick,
            sport=SPORT_LABELS.get(game.sport, game.sport),
            caption=_caption(game),
            kickoff=game.kickoff,
            pick=describe_pick(pick),
            result=_result(pick, game, snap),
            final_score=(f'{snap.away_score}-{snap.home_score}'
                         if snap is not None else None),
        )
        order = (is_reserve, game.kickoff, game.api_event_id, pick.slot)
        keyed.setdefault(pick.user_id, {}).setdefault(
            number_by_week_id[pick.week_id], []).append((order, line))

    return {
        user_id: {
            week_number: tuple(line for _, line in sorted(items, key=lambda item: item[0]))
            for week_number, items in by_week.items()
        }
        for user_id, by_week in keyed.items()
    }
