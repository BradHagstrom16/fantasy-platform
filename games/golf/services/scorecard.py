"""
The Pay Sheet — the scorecard
===============================
One member's season, the newest week first (games/golf/DESIGN.md §8). A pure
builder over rows the route already loaded, like the sheet and the field: no
query per week, and the member's rank and total are the sheet's own row, so
the two pages never disagree.

Nothing shows before the lock: for anyone but the member, a pick on a week
not yet revealed is dropped here, before a row is built from it.
"""
from dataclasses import dataclass

from games.golf.models import PENALTY_PER_INCIDENT, GolfPick, GolfTournament
from games.golf.services.field import spent_golfers
from games.golf.services.sheet import SheetRow, WeekLine, week_lines
from games.golf.services.stats import SpentWeek
from models.user import User


def revealed(tournament):
    """A week whose picks are public: past its lock, or already banked.

    The lock reads a missing ``pick_deadline`` as open, and an imported or
    unsynced week can be banked without one, so a banked week is revealed
    whatever its deadline says.
    """
    return bool(tournament.is_deadline_passed() or tournament.results_finalized)


@dataclass(frozen=True)
class WeekRow:
    """One week on a member's scorecard."""
    tournament: GolfTournament
    state: str                     # 'banked', 'live', 'pending' (locked, no figure yet) or 'open'
    pick: GolfPick | None          # None: no pick, or one that is not the viewer's to see
    line: WeekLine | None          # the pick read against its results (banked and live weeks)
    hidden: bool                   # another member's week before its lock


@dataclass(frozen=True)
class Scorecard:
    member: User
    is_me: bool
    line: SheetRow                 # the member's row on the sheet: rank, total, this week
    members: int
    weeks: list                    # newest first, from the next pick back to week 1
    to_play: int                   # weeks after the next pick
    played: int                    # banked weeks with a resolved pick
    cashes: int                    # of those, the weeks in the money
    used: int                      # golfers spent this season
    overrides: int                 # picks the Commish set, on revealed weeks
    best: WeekLine | None          # the member's biggest banked week
    major_cuts: int                # missed cuts and DQs at majors
    pot_owed: int
    pot_outstanding: int
    spent: list                    # the golfers spent, newest first (field.SpentGolfer)
    ledger: list                   # the room's override tally (stats.OverrideCount)

    @property
    def pot_paid(self):
        return self.pot_owed - self.pot_outstanding


def build_scorecard(member, viewer_id, sheet, tournaments, picks, results, usage,
                    ledger, penalty_paid, live=None, live_lines=None, next_tournament=None):
    """A member's season as their scorecard shows it.

    ``sheet`` is ``sheet.build_sheet`` for the season (with the live event's
    lines when one is on the course); ``tournaments`` the season's, in start
    order; ``picks`` every pick the member has on them, golfers and
    tournament loaded; ``results`` the results of those picks' golfers;
    ``usage`` the member's spent golfers by id; ``ledger``
    ``stats.override_tally`` over the revealed weeks. ``live`` and
    ``live_lines`` are the sheet's event and its ``week_lines``;
    ``next_tournament`` is the week still open for a pick.
    """
    is_me = member.id == viewer_id
    open_ids = {t.id for t in tournaments if not revealed(t)}
    visible = {
        pick.tournament_id: pick for pick in picks
        if is_me or pick.tournament_id not in open_ids
    }
    results_by_week = {}
    for result in results:
        results_by_week.setdefault(result.tournament_id, []).append(result)

    weeks = []
    for tournament in reversed(tournaments):
        pick = visible.get(tournament.id)
        line = None
        if tournament.id in open_ids:
            if next_tournament is None or tournament.id != next_tournament.id:
                continue
            state = 'open'
        elif tournament.results_finalized:
            state = 'banked'
            if pick:
                line = week_lines(
                    tournament, [pick], results_by_week.get(tournament.id, []),
                )[member.id]
        elif live is not None and tournament.id == live.id:
            state = 'live'
            line = (live_lines or {}).get(member.id)
        else:
            state = 'pending'
        weeks.append(WeekRow(
            tournament=tournament, state=state, pick=pick, line=line,
            hidden=state == 'open' and not is_me,
        ))

    banked = [week.line for week in weeks
              if week.state == 'banked' and week.line and week.pick.points_earned is not None]
    paying = [line for line in banked if line.pick.points_earned]
    best = max(paying, key=lambda line: (line.pick.points_earned, -line.pick.id), default=None)

    # The week a golfer went: the first resolved pick he counted on.
    spent_in = {}
    for pick in sorted(picks, key=lambda pick: pick.tournament.start_date):
        if pick.active_player_id and pick.points_earned is not None:
            spent_in.setdefault(pick.active_player_id, SpentWeek(
                pick.tournament.week_number, pick.tournament.name,
            ))

    # The pot counts the flag the scoring wrote, never a status re-read, so
    # the tile always equals GolfEnrollment.penalty_owed().
    # The card reads newest first, so its spent golfers do too; one no pick
    # accounts for has no week and stays last.
    by_week = spent_golfers(usage, spent_in)
    spent = ([golfer for golfer in reversed(by_week) if golfer.week]
             + [golfer for golfer in by_week if not golfer.week])

    major_cuts = sum(1 for pick in picks if pick.penalty_triggered)
    pot_owed = major_cuts * PENALTY_PER_INCIDENT

    return Scorecard(
        member=member,
        is_me=is_me,
        line=next(row for row in sheet.rows if row.user.id == member.id),
        members=len(sheet.rows),
        weeks=weeks,
        to_play=len(open_ids) - sum(1 for week in weeks if week.state == 'open'),
        played=len(banked),
        cashes=len(paying),
        used=len(usage),
        overrides=next((row.count for row in ledger if row.user_id == member.id), 0),
        best=best,
        major_cuts=major_cuts,
        pot_owed=pot_owed,
        pot_outstanding=max(0, pot_owed - (penalty_paid or 0)),
        spent=spent,
        ledger=ledger,
    )
