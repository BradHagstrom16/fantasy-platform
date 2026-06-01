"""Derived team elimination — group-stage flag PLUS knockout losses.

WorldCupTeam.is_eliminated is GROUP-STAGE-ONLY by data contract: scoring sets
it True only for teams that fail to advance from their group. Knockout losers
(R32/R16/QF/SF/runner-up) keep is_eliminated=False. Any UI asking "is this team
out of the tournament?" must use eliminated_team_ids(), not the raw flag.

Mirrors games.worldcup.services.team_detail._path_status() KO semantics: a team
is out if it appears in a COMPLETED knockout match where it is not the winner.
A completed KO match with a NULL winner counts as elimination for BOTH teams
(knockouts never legitimately draw). The SF match alone eliminates both SF
losers, so 'third_place' is redundant and intentionally omitted; 'final'
captures the runner-up.
"""
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupMatch, WorldCupTeam

# Knockout stage codes as stored on WorldCupMatch.stage (see team_detail
# _NEXT_MATCH_STAGE: 'final' is lowercase; 'third_place' is the consolation).
_KO_STAGES = ('R32', 'R16', 'QF', 'SF', 'final')


def eliminated_team_ids(season_year: int = SEASON_YEAR) -> set[int]:
    """Team ids that are out of the tournament (group exit OR knockout loss).

    N+1-free: one query for group-eliminated team ids, one for completed KO
    matches. `season_year` is accepted for API symmetry / forward-compat; teams
    and matches are a single tournament edition today (no per-season column),
    so it is currently advisory — the completed-match set IS the edition.
    """
    out: set[int] = {
        tid for (tid,) in (
            WorldCupTeam.query
            .filter(WorldCupTeam.is_eliminated.is_(True))
            .with_entities(WorldCupTeam.id)
            .all()
        )
    }
    ko_matches = (
        WorldCupMatch.query
        .filter(
            WorldCupMatch.stage.in_(_KO_STAGES),
            WorldCupMatch.is_completed.is_(True),
        )
        .with_entities(
            WorldCupMatch.home_team_id,
            WorldCupMatch.away_team_id,
            WorldCupMatch.winner_team_id,
        )
        .all()
    )
    for home_id, away_id, winner_id in ko_matches:
        for tid in (home_id, away_id):
            if tid is not None and tid != winner_id:
                out.add(tid)
    return out
