"""
The Pay Sheet — the sheet and the board
=========================================
One tournament's picks read against its results, and the season's lines read
against the week in progress. Pure builders over rows the route already
loaded: no query per row, and every sort and rank happens here rather than in
a template (games/golf/DESIGN.md §7.1, §9).
"""
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from games.golf.models import GolfPick, GolfPlayer, GolfTournament
from games.golf.utils import (
    GOLF_LEAGUE_TZ,
    calculate_projected_earnings,
    format_score_to_par,
    league_time,
)
from models.user import User

# A result status that takes the golfer out of the money. The API's casing
# drifts ('cut' and 'CUT' both sit in the 2026 archive).
DEDUCTIONS = {'cut': 'Cut', 'wd': 'WD', 'dq': 'DQ'}


def competition_ranks(values):
    """Competition rank for values already sorted high to low.

    ``rank = 1 + (count strictly higher)``: ties share and the next rank gaps
    (1, 1, 3, 4). Returns one ``(rank, label)`` per value; a shared rank is
    labelled "T4", a rank held alone "4".
    """
    ranks = []
    for i, value in enumerate(values):
        ranks.append(ranks[-1] if i and value == values[i - 1] else i + 1)
    shared = Counter(ranks)
    return [(rank, f'T{rank}' if shared[rank] > 1 else str(rank)) for rank in ranks]


def ordinal(n):
    """1 -> '1st', 2 -> '2nd', 11 -> '11th', 23 -> '23rd'."""
    if 10 <= n % 100 <= 13:
        return f'{n}th'
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


@dataclass(frozen=True)
class WeekLine:
    """One member's week on one tournament: the pencil line under a name."""
    pick: GolfPick
    golfer: GolfPlayer             # the golfer who counts
    position: str                  # '' when there is none, or a deduction says it
    to_par: str | None
    figure: int | None             # None before the first read of the week
    banked: bool                   # the tournament's results are final
    deduction: str | None          # Cut / WD / DQ
    replaces: GolfPlayer | None    # the primary, when the backup counts
    used: bool                     # the golfer who counted is now spent

    @property
    def place(self):
        """The position as a place when it is held alone: '2nd'; 'T9' stays."""
        return ordinal(int(self.position)) if self.position.isdigit() else self.position

    @property
    def idle(self):
        """The golfer of the pair who did not count."""
        if self.replaces is not None:
            return self.replaces
        return self.pick.backup_player

    @property
    def in_pencil(self):
        """A live projection: read, still in the money, not yet banked."""
        return not self.banked and self.figure is not None and self.deduction is None


def week_lines(tournament, picks, results):
    """Every pick on a tournament as a ``WeekLine``, keyed by member.

    Only for a tournament past its lock. A banked tournament reads
    ``points_earned`` and nothing else; until then the figure is a projection
    from position (the same ``calculate_projected_earnings`` the live sync
    uses), never the stored earnings, which may be official before the
    tournament is declared final.
    """
    by_player = {r.player_id: r for r in results}
    positions = [r.final_position for r in results if r.final_position]
    purse = tournament.effective_purse or 0
    banked = bool(tournament.results_finalized)

    lines = {}
    for pick in picks:
        pick.prime_results(by_player)
        backup_counts = pick.display_active_player_id == pick.backup_player_id
        golfer = pick.backup_player if backup_counts else pick.primary_player
        result = by_player.get(golfer.id)
        deduction = DEDUCTIONS.get(result.status.lower()) if result else None

        if banked:
            figure = pick.points_earned
        elif result is None:
            figure = None
        elif deduction:
            figure = 0
        else:
            figure = calculate_projected_earnings(
                result.final_position, purse, positions, tournament.is_major,
            )

        lines[pick.user_id] = WeekLine(
            pick=pick,
            golfer=golfer,
            position='' if deduction or result is None else result.final_position,
            to_par=format_score_to_par(result.score_to_par) if result else None,
            figure=figure,
            banked=banked,
            deduction=deduction,
            replaces=pick.primary_player if backup_counts else None,
            used=banked and bool(pick.primary_used or pick.backup_used),
        )
    return lines


def _by_name(user):
    return user.get_display_name().casefold()


@dataclass(frozen=True)
class SheetRow:
    rank: int
    rank_label: str
    user: User
    is_me: bool
    total: int
    projected: bool                # the total carries a live projection
    unpaid: bool
    week: WeekLine | None          # None: no live event, or no pick on it

    @property
    def place(self):
        """'4th', or 'Tied 4th' when the rank is shared."""
        place = ordinal(self.rank)
        return f'Tied {place}' if self.rank_label.startswith('T') else place


@dataclass(frozen=True)
class Sheet:
    rows: list
    mine: SheetRow | None
    didnt_pick: list               # members with no pick on the live event
    projected: bool                # any line on the sheet is in pencil


def build_sheet(enrollments, viewer_id=None, lines=None):
    """The season's lines in true rank order.

    ``lines`` is ``week_lines`` for the event on the course (or settling), or
    None between events. A member's total is what they have banked plus this
    week's projection; a line is in pencil only while that projection is live.
    """
    drafts = []
    for enrollment in enrollments:
        week = lines.get(enrollment.user_id) if lines else None
        # A pick already resolved (a Commish override on a settling event) is
        # in total_points; adding its projection would count the week twice.
        live = bool(week and week.in_pencil and week.pick.points_earned is None)
        total = (enrollment.total_points or 0) + (week.figure if live else 0)
        drafts.append((enrollment, week, total, live))
    drafts.sort(key=lambda d: (-d[2], _by_name(d[0].user)))

    ranks = competition_ranks([d[2] for d in drafts])
    rows = [
        SheetRow(
            rank=rank,
            rank_label=label,
            user=enrollment.user,
            is_me=enrollment.user_id == viewer_id,
            total=total,
            projected=live,
            unpaid=not enrollment.has_paid,
            week=week,
        )
        for (enrollment, week, total, live), (rank, label) in zip(drafts, ranks, strict=True)
    ]
    didnt_pick = sorted(
        (row.user for row in rows if row.week is None), key=_by_name,
    ) if lines is not None else []
    return Sheet(
        rows=rows,
        mine=next((row for row in rows if row.is_me), None),
        didnt_pick=didnt_pick,
        projected=any(row.projected for row in rows),
    )


@dataclass(frozen=True)
class BoardRow:
    rank: int
    rank_label: str
    user: User
    is_me: bool
    week: WeekLine


@dataclass(frozen=True)
class Board:
    rows: list
    mine: BoardRow | None
    didnt_pick: list               # the season's members with no pick here
    penalties: int                 # $15 incidents showing on this board


def build_board(lines, enrollments, viewer_id=None):
    """One tournament's picks ranked by what each is worth this week."""
    ordered = sorted(
        lines.values(),
        key=lambda week: (-(week.figure or 0), _by_name(week.pick.user)),
    )
    ranks = competition_ranks([week.figure or 0 for week in ordered])
    rows = [
        BoardRow(
            rank=rank,
            rank_label=label,
            user=week.pick.user,
            is_me=week.pick.user_id == viewer_id,
            week=week,
        )
        for week, (rank, label) in zip(ordered, ranks, strict=True)
    ]
    return Board(
        rows=rows,
        mine=next((row for row in rows if row.is_me), None),
        didnt_pick=sorted(
            (e.user for e in enrollments if e.user_id not in lines), key=_by_name,
        ),
        penalties=sum(1 for week in ordered if week.pick.show_penalty_badge),
    )


def last_read(results):
    """When the leaderboard was last read: the newest result stamp, in league time."""
    stamps = [r.updated_at for r in results if r.updated_at]
    if not stamps:
        return None
    newest = max(stamps)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    return newest.astimezone(GOLF_LEAGUE_TZ)


@dataclass(frozen=True)
class EventClock:
    """Where an unbanked tournament stands, for the context line."""
    tournament: GolfTournament
    on_course: bool                # still being played: the Live chip
    round_label: str
    last_read: datetime | None


def event_clock(tournament, results, now):
    """The clock for a tournament past its lock whose results are not final."""
    played_out = (
        tournament.status == 'complete'
        or now.date() > league_time(tournament.end_date).date()
    )
    if played_out:
        round_label = 'Final round played'
    else:
        day = (now.date() - league_time(tournament.start_date).date()).days + 1
        round_label = f'Round {min(max(day, 1), 4)}'
    return EventClock(
        tournament=tournament,
        on_course=not played_out,
        round_label=round_label,
        last_read=last_read(results),
    )


def live_event(locked):
    """The tournament the sheet is pencilling: on the course, else settling.

    ``locked`` is the season's tournaments already past their lock, in start
    order; the latest whose results are not final is the one. No status is
    read: a sync writes 'active' early and the request hook moves 'upcoming'
    late, so only the lock says when a week turns over.
    """
    return next((t for t in reversed(locked) if not t.results_finalized), None)
