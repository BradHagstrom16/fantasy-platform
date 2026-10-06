"""
The Pay Sheet — season aggregates
===================================
Query-only reads over a season's usage, picks and results: who the room has
spent, what each golfer has won, and when a member spent whom. The pick page
reads them (games/golf/DESIGN.md §7.5, §7.7); the Record Room extends this
module. Every read takes a season.

Two money concepts, never to be confused:

- **Member points** = ``GolfPick.points_earned`` (the major ×1.5 already in it).
- **Golfer prize** = raw ``GolfTournamentResult.earnings``, the tour's own money.
  ``ytd_earnings`` is this one.
"""
from dataclasses import dataclass

from sqlalchemy import func, select

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentResult,
)


def _usage_counts(season_year):
    """(members with a line, {player_id: members who have spent him}).

    Read from ``GolfSeasonPlayerUsage``, the table that gates a pick, so the
    counts move only when a result is processed, never on a pick in flight.
    The room is the season's enrollees (the sheet's own roster), and only
    their usage is counted, so a share never passes 100.
    """
    members = db.session.scalar(
        select(func.count(GolfEnrollment.id)).filter_by(season_year=season_year)
    ) or 0
    counts = dict(db.session.execute(
        select(GolfSeasonPlayerUsage.player_id, func.count(GolfSeasonPlayerUsage.id))
        .join(GolfEnrollment, (GolfEnrollment.user_id == GolfSeasonPlayerUsage.user_id)
              & (GolfEnrollment.season_year == GolfSeasonPlayerUsage.season_year))
        .where(GolfSeasonPlayerUsage.season_year == season_year)
        .group_by(GolfSeasonPlayerUsage.player_id)
    ).all())
    return members, counts


def _pct(count, total):
    """Whole-number share of the room, safe while the room is empty."""
    return round(100 * count / total) if total else 0


def remaining_pct_map(season_year, player_ids):
    """{player_id: % of the room that still has him}; None before any burn.

    The complement of the rounded burn share (100 - burned), so the pick page
    and the Burn List always sum to exactly 100. None, rather than a map of
    100s, while the season has no usage: the pick page draws no hatch at all
    when there is no signal.
    """
    members, counts = _usage_counts(season_year)
    if not counts:
        return None
    return {pid: 100 - _pct(counts.get(pid, 0), members) for pid in player_ids}


def ytd_earnings(season_year):
    """{player_id: prize money won this season}, banked tournaments only.

    The golfer's own money (raw earnings, no member multiplier). A tournament
    counts once its results are final, so a live week never leaks in.
    """
    return dict(db.session.execute(
        select(GolfTournamentResult.player_id,
               func.coalesce(func.sum(GolfTournamentResult.earnings), 0))
        .join(GolfTournament, GolfTournamentResult.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season_year,
               GolfTournament.results_finalized.is_(True))
        .group_by(GolfTournamentResult.player_id)
    ).all())


@dataclass(frozen=True)
class SpentWeek:
    """The week a member spent a golfer: 'Wk 13 · Masters Tournament'."""
    week_number: int | None
    tournament: str


def spent_weeks(user_id, season_year):
    """{player_id: SpentWeek} for the golfers who counted in a member's weeks.

    Read from the member's resolved picks (``active_player_id``, the golfer
    who counted). A usage row with no such pick (one entered by hand) has no
    week to name and is simply absent here. A golfer an override left counting
    in two weeks is named by the first, the week he was spent.
    """
    rows = db.session.execute(
        select(GolfPick.active_player_id, GolfTournament.week_number, GolfTournament.name)
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .where(GolfPick.user_id == user_id,
               GolfTournament.season_year == season_year,
               GolfPick.active_player_id.is_not(None),
               GolfPick.points_earned.is_not(None))
        .order_by(GolfTournament.start_date)
    ).all()
    weeks = {}
    for player_id, week, name in rows:
        weeks.setdefault(player_id, SpentWeek(week, name))
    return weeks
