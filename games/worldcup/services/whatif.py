"""World Cup Fantasy Pool — What-If Simulator.

Pure, read-only projections over the remaining KNOCKOUT bracket (group stage
is out of scope — round-robin tiebreakers are a different, harder problem).
Mirrors fetch_bracket_proposal()'s contract: never writes to the database.
Reuses the real KNOCKOUT_POINTS constants and each team's stored multiplier
so simulated numbers can never drift from the actual scoring engine
(games/worldcup/services/scoring.py) — see CLAUDE.md's scoring-attribution
SSoT rule.
"""
from collections import Counter

from extensions import db
from games.worldcup.constants import KNOCKOUT_POINTS, SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
)
from games.worldcup.services.bracket import BRACKET_TOPOLOGY
from games.worldcup.services.stage import stage_label

# Stages whose match winner earns a flat per-round point value (excludes
# 'final'/'third_place', which route through champion/runner_up/third_place
# below instead — same split as scoring._apply_knockout_points).
_ROUND_STAGES = ('R32', 'R16', 'QF', 'SF')


def incomplete_knockout_matches() -> list[WorldCupMatch]:
    """All non-group matches not yet completed, ordered by match_number.

    No assumption about how many remain — works whether the tournament is
    down to the final 4 matches or still mid-knockout-bracket.
    """
    return (
        WorldCupMatch.query
        .filter(WorldCupMatch.stage != 'group', WorldCupMatch.is_completed.is_(False))
        .order_by(WorldCupMatch.match_number)
        .all()
    )


def _resolve(match_number, hypothetical, matches_by_number, cache):
    """(home_id, away_id) for match_number, resolved transitively.

    Real data wins if the shell already has both sides set. Otherwise walks
    BRACKET_TOPOLOGY's feeder pair: a feeder's real result wins if it's
    completed; otherwise the caller's hypothetical pick for that feeder is
    used, but only once validated against the feeder's OWN resolved sides
    (recursively) — an unresolved/undecided feeder yields None (still TBD).
    """
    if match_number in cache:
        return cache[match_number]

    match = matches_by_number.get(match_number)
    if match and match.home_team_id and match.away_team_id:
        result = (match.home_team_id, match.away_team_id)
        cache[match_number] = result
        return result

    feeders = BRACKET_TOPOLOGY.get(match_number)
    if not feeders:
        result = (
            match.home_team_id if match else None,
            match.away_team_id if match else None,
        )
        cache[match_number] = result
        return result

    sides = []
    for kind, feeder_no in feeders:
        feeder_match = matches_by_number.get(feeder_no)
        winner_id = loser_id = None
        if feeder_match and feeder_match.is_completed and feeder_match.winner_team_id:
            winner_id = feeder_match.winner_team_id
            loser_id = (
                feeder_match.away_team_id
                if winner_id == feeder_match.home_team_id
                else feeder_match.home_team_id
            )
        elif feeder_no in hypothetical:
            fh, fa = _resolve(feeder_no, hypothetical, matches_by_number, cache)
            candidate = hypothetical[feeder_no]
            if candidate in (fh, fa):
                winner_id = candidate
                loser_id = fa if candidate == fh else fh
        sides.append(winner_id if kind == 'winner' else loser_id)

    result = tuple(sides)
    cache[match_number] = result
    return result


def resolve_match_teams(match_number, hypothetical, matches_by_number):
    """Public entry point for _resolve — see its docstring."""
    return _resolve(match_number, hypothetical, matches_by_number, {})


def bracket_state_for_ui() -> list[dict]:
    """The zero-picks view of every incomplete knockout match — the initial
    page-load payload the client needs to render bracket-ordered, feeder-gated
    picker options without an initial AJAX round trip."""
    matches = incomplete_knockout_matches()
    matches_by_number = {m.match_number: m for m in matches}
    team_ids = set()
    sides_by_match = {}
    for match in matches:
        home_id, away_id = resolve_match_teams(match.match_number, {}, matches_by_number)
        sides_by_match[match.match_number] = (home_id, away_id)
        team_ids.update(tid for tid in (home_id, away_id) if tid)

    teams_by_id = {t.id: t for t in WorldCupTeam.query.filter(WorldCupTeam.id.in_(team_ids)).all()} if team_ids else {}

    def _brief(team_id):
        if not team_id:
            return None
        team = teams_by_id.get(team_id)
        if not team:
            return None
        return {
            'team_id': team.id, 'name': team.display_name,
            'fifa_code': team.fifa_code, 'iso_code': team.iso_code,
        }

    def _feeder(match_number, side_index):
        """Where a still-TBD side comes from, so the client can resolve it as
        the visitor picks upstream matches (a concretely-known side needs no
        pointer — the client already has the real team)."""
        feeders = BRACKET_TOPOLOGY.get(match_number)
        if not feeders:
            return None
        kind, feeder_no = feeders[side_index]
        return {'kind': kind, 'match_number': feeder_no}

    result = []
    for match in matches:
        home_id, away_id = sides_by_match[match.match_number]
        home_brief, away_brief = _brief(home_id), _brief(away_id)
        result.append({
            'match_number': match.match_number,
            'stage': match.stage,
            'stage_label': stage_label(match.stage),
            'home': home_brief,
            'away': away_brief,
            'home_feeder': None if home_brief else _feeder(match.match_number, 0),
            'away_feeder': None if away_brief else _feeder(match.match_number, 1),
        })
    return result


def compute_hypothetical_deltas(hypothetical: dict[int, int]) -> dict[int, float]:
    """{team_id: hypothetical point delta} for the given {match_number: winner_team_id} picks.

    Only teams affected by a resolved, valid pick appear. Values come only
    from KNOCKOUT_POINTS and each team's stored multiplier — never
    redeclared here.
    """
    matches = incomplete_knockout_matches()
    matches_by_number = {m.match_number: m for m in matches}
    deltas: dict[int, float] = {}

    for match in matches:
        winner_id = hypothetical.get(match.match_number)
        if winner_id is None:
            continue
        home_id, away_id = resolve_match_teams(match.match_number, hypothetical, matches_by_number)
        if winner_id not in (home_id, away_id):
            continue  # stale/invalid pick — silently ignored
        loser_id = away_id if winner_id == home_id else home_id

        winner_team = db.session.get(WorldCupTeam, winner_id)
        if match.stage in _ROUND_STAGES:
            if winner_team:
                deltas[winner_id] = deltas.get(winner_id, 0.0) + KNOCKOUT_POINTS[match.stage] * winner_team.multiplier
        elif match.stage == 'final':
            loser_team = db.session.get(WorldCupTeam, loser_id) if loser_id else None
            if winner_team:
                deltas[winner_id] = deltas.get(winner_id, 0.0) + KNOCKOUT_POINTS['champion'] * winner_team.multiplier
            if loser_team:
                deltas[loser_id] = deltas.get(loser_id, 0.0) + KNOCKOUT_POINTS['runner_up'] * loser_team.multiplier
        elif match.stage == 'third_place' and winner_team:
            deltas[winner_id] = deltas.get(winner_id, 0.0) + KNOCKOUT_POINTS['third_place'] * winner_team.multiplier

    return deltas


def simulate_leaderboard(hypothetical: dict[int, int]) -> dict:
    """Full hypothetical leaderboard: current total_score + deltas, re-ranked
    with the same competition-rank convention as routes.leaderboard() (tied
    scores share a rank; the next distinct score jumps by the tie size)."""
    deltas = compute_hypothetical_deltas(hypothetical)

    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .all()
    )
    enrollment_ids = [e.id for e in enrollments]
    picks_by_enrollment: dict[int, list[int]] = {}
    if enrollment_ids:
        for pick in WorldCupPick.query.filter(WorldCupPick.enrollment_id.in_(enrollment_ids)).all():
            picks_by_enrollment.setdefault(pick.enrollment_id, []).append(pick.team_id)

    rows = []
    for e in enrollments:
        delta = sum(deltas.get(tid, 0.0) for tid in picks_by_enrollment.get(e.id, []))
        rows.append({
            'enrollment_id': e.id,
            'display_name': e.get_display_name(),
            'score': e.total_score + delta,
            'delta': delta,
        })
    rows.sort(key=lambda r: -r['score'])

    ranked = []
    current_rank = 0
    prev_score = None
    for i, row in enumerate(rows):
        if row['score'] != prev_score:
            current_rank = i + 1
        ranked.append({**row, 'rank': current_rank})
        prev_score = row['score']

    rank_counts = Counter(r['rank'] for r in ranked)
    for r in ranked:
        r['tied'] = rank_counts[r['rank']] > 1

    return {'ranked': ranked, 'total_players': len(ranked)}
