"""Derived team elimination — group-stage flag PLUS knockout losses.

WorldCupTeam.is_eliminated is GROUP-STAGE-ONLY by data contract: scoring sets
it True only for teams that fail to advance from their group. Knockout losers
(R32/R16/QF/SF/runner-up) keep is_eliminated=False. Any UI asking "is this team
out of the tournament?" must use eliminated_team_ids(), not the raw flag.

Mirrors games.worldcup.services.team_detail._path_status() KO semantics:

- The LOSER of a completed R32/R16/QF/final match is out (NULL winner ⇒ BOTH,
  knockouts never legitimately draw). 'final' is here so the runner-up is out
  only once the final completes.
- 'SF' is deliberately NOT a loss stage: a semifinal loser still plays the
  third-place match, so they stay alive until it completes (scoring.py keeps
  SF losers `best_finish='SF'`, NOT eliminated; _path_status returns (5, None)).
- A completed 'third_place' match marks BOTH participants out — the 3rd-place
  finisher and the 4th — since finishing the consolation is the trigger that
  ends both teams' tournament. This is also what finally eliminates the SF
  losers.
"""
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupMatch, WorldCupTeam

# Knockout rounds whose completed-match LOSER is out (see _NEXT_MATCH_STAGE in
# team_detail: 'final' is lowercase). 'SF' and 'third_place' are handled
# separately (see module docstring) — do not add them here.
_KO_LOSS_STAGES = ('R32', 'R16', 'QF', 'final')


def eliminated_team_ids(season_year: int = SEASON_YEAR) -> set[int]:
    """Team ids that are out of the tournament (group exit OR knockout loss).

    N+1-free: one query for group-eliminated team ids, one for completed
    loss-stage matches, one for completed third-place matches. `season_year` is
    accepted for API symmetry / forward-compat; teams and matches are a single
    tournament edition today (no per-season column), so it is currently
    advisory — the completed-match set IS the edition.
    """
    out: set[int] = {
        tid for (tid,) in (
            WorldCupTeam.query
            .filter(WorldCupTeam.is_eliminated.is_(True))
            .with_entities(WorldCupTeam.id)
            .all()
        )
    }
    # Losers of completed R32/R16/QF/final matches (NULL winner ⇒ both out).
    loss_matches = (
        WorldCupMatch.query
        .filter(
            WorldCupMatch.stage.in_(_KO_LOSS_STAGES),
            WorldCupMatch.is_completed.is_(True),
        )
        .with_entities(
            WorldCupMatch.home_team_id,
            WorldCupMatch.away_team_id,
            WorldCupMatch.winner_team_id,
        )
        .all()
    )
    for home_id, away_id, winner_id in loss_matches:
        for tid in (home_id, away_id):
            if tid is not None and tid != winner_id:
                out.add(tid)
    # A completed third-place match ends BOTH participants' run (3rd + 4th).
    third_place_matches = (
        WorldCupMatch.query
        .filter(
            WorldCupMatch.stage == 'third_place',
            WorldCupMatch.is_completed.is_(True),
        )
        .with_entities(
            WorldCupMatch.home_team_id,
            WorldCupMatch.away_team_id,
        )
        .all()
    )
    for home_id, away_id in third_place_matches:
        for tid in (home_id, away_id):
            if tid is not None:
                out.add(tid)
    return out
