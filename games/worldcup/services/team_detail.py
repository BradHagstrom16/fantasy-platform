"""
World Cup Fantasy Pool — Team detail helpers
==============================================
Pure read-only helpers powering the public /worldcup/team/<id> route:
- compute_team_ownership: pick count / percent / picker_names (privacy-gated)
- current_user_owns_team: cheap auth-only check
- compute_path_to_crown: 6-segment knockout path + projected ceiling

Privacy invariant (Spec C D11): pre-deadline, picker_names is None and
count/percent are zero — no roster information leaks before the tournament
begins, mirroring the player_detail.html roster-hiding rule.

best_finish strings consumed here come verbatim from scoring._update_best_finish:
  None | 'group' | 'R32' | 'R16' | 'QF' | 'SF' | '3rd' | 'runner_up' | 'champion'
The 'advanced_*' shape used by an earlier draft of this plan does NOT exist
in the data model. KO elimination is derived from the WorldCupMatch table
because team.is_eliminated is only set during group-stage processing.
"""
from typing import Optional, TypedDict

from sqlalchemy import or_

from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch, WorldCupPick, WorldCupTeam,
)
from games.worldcup.constants import (
    SEASON_YEAR,
    ADVANCE_GROUP_WINNER, KNOCKOUT_POINTS,
)


_SEGMENT_LABELS = ['Group', 'R32', 'R16', 'QF', 'SF', 'Final']
_SEGMENT_DISPLAY = ['Group Stage', 'Round of 32', 'Round of 16',
                    'Quarterfinals', 'Semifinals', 'Final']
# WorldCupMatch.stage value the team plays at each segment-index ahead.
# Index 0 is multi-match group play and is handled via best_finish='group'.
_NEXT_MATCH_STAGE: list[Optional[str]] = [
    None, 'R32', 'R16', 'QF', 'SF', 'final',
]


class TeamOwnership(TypedDict):
    count: int
    percent: float
    picker_names: Optional[list[str]]


class PathSegment(TypedDict):
    stage: str    # 'Group', 'R32', 'R16', 'QF', 'SF', 'Final'
    status: str   # 'won', 'current', 'future', 'eliminated'


class PathToCrown(TypedDict):
    segments: list[PathSegment]
    eliminated: bool
    champion: bool              # cleared all 6 segments, not eliminated
    eliminated_at_label: Optional[str]
    projected_ceiling: float    # multiplied points if team wins out from here


def compute_team_ownership(team_id: int, deadline_passed: bool) -> TeamOwnership:
    """Return ownership stats for one team in the current SEASON_YEAR pool.

    Pre-deadline: count + percent are zero, picker_names is None — strict
    privacy parity with player_detail.html roster-hiding (spec D11).
    Post-deadline: count = picks on this team; percent = count / total
    enrollments in the pool * 100; picker_names is the sorted list of
    display names (falls back to User.username when display_name is null).
    """
    if not deadline_passed:
        return TeamOwnership(count=0, percent=0.0, picker_names=None)

    picks = (
        WorldCupPick.query
        .join(WorldCupEnrollment)
        .filter(
            WorldCupPick.team_id == team_id,
            WorldCupEnrollment.season_year == SEASON_YEAR,
        )
        .all()
    )
    total_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .count()
    )

    count = len(picks)
    percent = round((count / total_enrollments) * 100, 2) if total_enrollments else 0.0
    picker_names = sorted(p.enrollment.get_display_name() for p in picks)
    return TeamOwnership(count=count, percent=percent, picker_names=picker_names)


def current_user_owns_team(user_id: int, team_id: int) -> bool:
    """True iff the user has a pick on this team in the SEASON_YEAR pool."""
    return bool(db.session.query(
        WorldCupPick.query
        .join(WorldCupEnrollment)
        .filter(
            WorldCupEnrollment.user_id == user_id,
            WorldCupEnrollment.season_year == SEASON_YEAR,
            WorldCupPick.team_id == team_id,
        )
        .exists()
    ).scalar())


def compute_path_to_crown(team: WorldCupTeam) -> PathToCrown:
    """Build the 6-segment knockout-path payload.

    Segments are: Group · R32 · R16 · QF · SF · Final.
    Status per segment:
      - 'won':         team has cleared this stage
      - 'current':     team's next stage (only when not eliminated)
      - 'eliminated':  the segment where the team was knocked out
      - 'future':      stage hasn't been reached yet

    projected_ceiling: if the team wins every remaining segment, what total
    multiplied score does their team contribute? team.base_points already
    holds everything earned to date (group match points, advancement bonus,
    KO wins), so we add only the unearned remainder before multiplying.
    Eliminated teams' ceiling = team.multiplied_points (no further upside).
    """
    cleared, eliminated_at = _path_status(team)
    eliminated = eliminated_at is not None
    champion = not eliminated and cleared == len(_SEGMENT_LABELS)

    segments: list[PathSegment] = []
    for i, label in enumerate(_SEGMENT_LABELS):
        if i < cleared:
            status = 'won'
        elif eliminated and i == eliminated_at:
            status = 'eliminated'
        elif i == cleared and not eliminated:
            status = 'current'
        else:
            status = 'future'
        segments.append(PathSegment(stage=label, status=status))

    eliminated_at_label = (
        _SEGMENT_DISPLAY[eliminated_at]
        if eliminated and eliminated_at is not None
        else None
    )

    if eliminated:
        projected_ceiling = float(team.multiplied_points)
    else:
        # Sum unearned base contributions assuming team wins out.
        remaining_base = 0.0
        if cleared == 0:
            # Group still in progress — assume group winner advancement bonus.
            remaining_base += ADVANCE_GROUP_WINNER
        # Knockout match wins yet to earn:
        #   cleared=1 (cleared group)         → R32, R16, QF, SF
        #   cleared=2 (won R32)               → R16, QF, SF
        #   cleared=k                         → keys at index >= k-1
        knockout_keys = ['R32', 'R16', 'QF', 'SF']
        for i, key in enumerate(knockout_keys):
            if (i + 1) >= cleared:
                remaining_base += KNOCKOUT_POINTS[key]
        # Champion bonus only if not already champion.
        if cleared < 6:
            remaining_base += KNOCKOUT_POINTS['champion']
        projected_ceiling = round(
            (float(team.base_points) + remaining_base) * team.multiplier, 1,
        )

    return PathToCrown(
        segments=segments,
        eliminated=eliminated,
        champion=champion,
        eliminated_at_label=eliminated_at_label,
        projected_ceiling=projected_ceiling,
    )


def _path_status(team: WorldCupTeam) -> tuple[int, Optional[int]]:
    """Return (cleared_depth, eliminated_at_index).

    cleared_depth: how many of the 6 segments the team has won (0..6).
    eliminated_at_index: the segment index where the team was knocked out,
    or None if still alive / champion.

    Sources of truth:
    - Terminal best_finish values ('champion', 'runner_up', '3rd', 'group')
      resolve directly without a query.
    - For intermediate KO states (best_finish in {'R32','R16','QF','SF'} or
      bf=None+advancement_method), elimination is derived from a completed
      WorldCupMatch at the team's next stage where they are not the winner.
      team.is_eliminated cannot be used because scoring only sets it during
      group-stage processing (scoring.py:256/259) — never for KO losses.
    """
    bf = team.best_finish

    # Terminal states resolved directly.
    if bf == 'champion':
        return (6, None)
    if bf == 'runner_up':
        return (5, 5)            # cleared SF, lost Final
    if bf == '3rd':
        return (4, 4)            # cleared QF, lost SF (won 3rd-place playoff)
    if bf == 'group':
        return (0, 0)            # group eliminated

    # bf='SF' is intermediate: SF winner awaiting Final, OR SF loser
    # awaiting/exiting 3rd-place playoff. Disambiguate via matches:
    # any completed third_place match for this team means they lost it
    # (otherwise bf would be '3rd') → 4th-place finisher.
    if bf == 'SF':
        completed_third = WorldCupMatch.query.filter(
            WorldCupMatch.stage == 'third_place',
            WorldCupMatch.is_completed.is_(True),
            or_(
                WorldCupMatch.home_team_id == team.id,
                WorldCupMatch.away_team_id == team.id,
            ),
        ).first()
        if completed_third is not None:
            return (4, 4)
        return (5, None)

    # Cleared depth from bf + advancement_method.
    if bf == 'QF':
        cleared = 4
    elif bf == 'R16':
        cleared = 3
    elif bf == 'R32':
        cleared = 2
    elif bf is None and team.advancement_method:
        cleared = 1
    else:
        # bf is None and no advancement_method → group stage in progress
        return (0, None)

    # KO elimination check: completed match at the next stage where the team
    # didn't win (winner_team_id is the opponent, or NULL if the row was
    # entered without a winner — knockouts never legitimately end as draws).
    next_stage = _NEXT_MATCH_STAGE[cleared]
    if next_stage is None:
        return (cleared, None)
    elim = WorldCupMatch.query.filter(
        WorldCupMatch.stage == next_stage,
        WorldCupMatch.is_completed.is_(True),
        or_(
            WorldCupMatch.home_team_id == team.id,
            WorldCupMatch.away_team_id == team.id,
        ),
        or_(
            WorldCupMatch.winner_team_id != team.id,
            WorldCupMatch.winner_team_id.is_(None),
        ),
    ).first()
    if elim is not None:
        return (cleared, cleared)
    return (cleared, None)
