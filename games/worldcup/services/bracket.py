"""Auto-fill deterministic downstream knockout shells (R16 -> Final).

Hybrid: derive each pairing from a fixed bracket topology + our own completed
results (primary), cross-check against the football-data.org proposal, and write
via the existing set_knockout_teams only when they agree (or when the API is
unavailable, flagged). R32 / group advancement are out of scope (admin-confirmed).
"""
import logging

from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from games.worldcup.services.scoring import set_knockout_teams
from games.worldcup.services.sync import (
    fetch_bracket_proposal, populatable_bracket_stages,
    _send_admin_email, _notify_once, SyncError, _fifa_for_tla, _api_get,
    COMPETITION_CODE,
)

logger = logging.getLogger(__name__)

DOWNSTREAM_STAGES = ('R16', 'QF', 'SF', 'final', 'third_place')

# Downstream match_number -> (home_feeder, away_feeder); feeder = (kind, match_no).
# SEQUENTIAL DEFAULT — replace 89-100 feeders with the official FIFA 2026 values
# (verify via infer_topology_from_api). 101-104 are fixed/correct.
BRACKET_TOPOLOGY: dict[int, tuple[tuple[str, int], tuple[str, int]]] = {
    89: (('winner', 73), ('winner', 74)),
    90: (('winner', 75), ('winner', 76)),
    91: (('winner', 77), ('winner', 78)),
    92: (('winner', 79), ('winner', 80)),
    93: (('winner', 81), ('winner', 82)),
    94: (('winner', 83), ('winner', 84)),
    95: (('winner', 85), ('winner', 86)),
    96: (('winner', 87), ('winner', 88)),
    97: (('winner', 89), ('winner', 90)),
    98: (('winner', 91), ('winner', 92)),
    99: (('winner', 93), ('winner', 94)),
    100: (('winner', 95), ('winner', 96)),
    101: (('winner', 97), ('winner', 98)),
    102: (('winner', 99), ('winner', 100)),
    103: (('loser', 101), ('loser', 102)),
    104: (('winner', 101), ('winner', 102)),
}


def infer_topology_from_api() -> dict:
    """Generate the topology dict from a FULLY-RESOLVED API bracket (verify aid).

    For each downstream KO fixture with both teams resolved, find which earlier
    match's winner (or loser) each team is, and emit the feeder pair. Returns
    {match_number: ((kind, feeder_no), (kind, feeder_no))}. Read-only; used to
    confirm BRACKET_TOPOLOGY matches reality — never called at runtime.
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    by_num = {}  # our match_number -> (winner_fifa, loser_fifa) for completed KO
    api_by_num = {}  # our match_number -> (home_fifa, away_fifa) resolved
    # Map API fixtures to our shells by api_fixture_id.
    shells = {m.api_fixture_id: m for m in WorldCupMatch.query.all() if m.api_fixture_id}
    for f in data.get('matches', []):
        shell = shells.get(f.get('id'))
        if not shell:
            continue
        home = _fifa_for_tla((f.get('homeTeam') or {}).get('tla'))
        away = _fifa_for_tla((f.get('awayTeam') or {}).get('tla'))
        if home and away:
            api_by_num[shell.match_number] = (home, away)
        winner_side = (f.get('score') or {}).get('winner')
        if winner_side in ('HOME_TEAM', 'AWAY_TEAM') and home and away:
            w, l = (home, away) if winner_side == 'HOME_TEAM' else (away, home)
            by_num[shell.match_number] = (w, l)

    winner_of = {fifa: n for n, (fifa, _) in by_num.items()}
    loser_of = {fifa: n for n, (_, fifa) in by_num.items()}
    topo = {}
    for num, (home, away) in api_by_num.items():
        if num < 89:
            continue

        def feeder(fifa):
            if fifa in winner_of:
                return ('winner', winner_of[fifa])
            if fifa in loser_of:
                return ('loser', loser_of[fifa])
            return None

        fh, fa = feeder(home), feeder(away)
        if fh and fa:
            topo[num] = (fh, fa)
    return dict(sorted(topo.items()))
