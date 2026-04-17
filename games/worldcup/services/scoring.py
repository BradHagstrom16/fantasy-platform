"""
World Cup Fantasy Pool — Scoring Engine
==========================================
Idempotent scoring pipeline: matches -> teams -> picks -> enrollments.

Full recalc every time — with ≤50 enrollments x 9 picks = 450 pick rows
and 48 team rows, a full recalc takes milliseconds.

Match data is the source of truth. Team scores, pick scores, and
enrollment totals are all derived from completed matches + advancement data.
"""
from dataclasses import dataclass
from datetime import date
from typing import Literal

from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
)
from games.worldcup.constants import (
    SEASON_YEAR, GROUP_WIN, GROUP_DRAW,
    ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD,
    KNOCKOUT_POINTS,
)

# Stage ordering for best_finish comparisons — higher = deeper run
STAGE_ORDER = {
    'group': 0,
    'R32': 1,
    'R16': 2,
    'QF': 3,
    'SF': 4,
    '3rd': 5,
    'runner_up': 6,
    'champion': 7,
}


ScoreSource = Literal['group_win', 'group_draw', 'advancement', 'knockout', 'podium']


@dataclass(frozen=True)
class ScoreEvent:
    """A single scoring event contributing to a team's base_points total.

    Returned by compute_team_score_events() for UI drill-down. Not persisted —
    derived fresh each render from current match/team state (ADR-024).
    """
    source: ScoreSource
    label: str
    base_points: float
    match_id: int | None
    occurred_on: date | None


def recalculate_all_scores() -> dict:
    """Master orchestrator. Performs a full idempotent recalculation.

    8-phase pipeline:
    1. Reset team cumulative scores
    2. Process group stage matches (W/D/L + match points)
    3. Apply advancement milestones
    4. Process knockout matches
    5. Apply podium bonuses
    6. Compute multiplied points
    7. Update pick scores
    8. Update enrollment totals
    """
    teams = WorldCupTeam.query.all()
    teams_by_id = {t.id: t for t in teams}

    # PHASE 1: Reset team cumulative scores
    for team in teams:
        team.base_points = 0.0
        team.multiplied_points = 0.0
        team.group_wins = 0
        team.group_draws = 0
        team.group_losses = 0
        # DO NOT reset: advancement_method, best_finish, is_eliminated

    # PHASE 2: Process group stage matches
    group_matches = WorldCupMatch.query.filter_by(
        stage='group', is_completed=True,
    ).all()
    for match in group_matches:
        _apply_match_to_teams(match)

    # PHASE 3: Apply advancement milestones
    for team in teams:
        if team.advancement_method:
            team.base_points += _apply_advancement_points(team)

    # PHASE 4: Process knockout matches
    knockout_matches = WorldCupMatch.query.filter(
        WorldCupMatch.stage != 'group',
        WorldCupMatch.is_completed == True,  # noqa: E712
    ).all()
    for match in knockout_matches:
        if match.winner_team_id:
            winner = teams_by_id.get(match.winner_team_id)
            if winner:
                winner.base_points += _apply_knockout_points(match)

    # PHASE 5: Apply podium bonuses
    for team in teams:
        team.base_points += _apply_podium_bonus(team)

    # PHASE 6: Compute multiplied points
    for team in teams:
        team.multiplied_points = team.base_points * team.multiplier

    # PHASE 7: Update pick scores
    picks = WorldCupPick.query.all()
    picks_by_enrollment: dict[int, list[WorldCupPick]] = {}
    for pick in picks:
        team = teams_by_id.get(pick.team_id)
        if team:
            pick.base_points = team.base_points
            pick.multiplied_points = team.multiplied_points
        picks_by_enrollment.setdefault(pick.enrollment_id, []).append(pick)

    # PHASE 8: Update enrollment totals
    enrollments = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).all()
    for enrollment in enrollments:
        enrollment.total_score = sum(
            p.multiplied_points for p in picks_by_enrollment.get(enrollment.id, [])
        )

    db.session.commit()

    return {
        'teams_updated': len(teams),
        'picks_updated': len(picks),
        'enrollments_updated': len(enrollments),
    }


def _apply_match_to_teams(match: WorldCupMatch) -> None:
    """Process a single completed group match's impact on team W/D/L records.

    Only handles group stage. Knockout matches are handled separately.
    """
    if match.stage != 'group':
        return

    home = db.session.get(WorldCupTeam, match.home_team_id)
    away = db.session.get(WorldCupTeam, match.away_team_id)
    if not home or not away:
        return

    if match.is_draw:
        home.group_draws += 1
        away.group_draws += 1
        home.base_points += GROUP_DRAW
        away.base_points += GROUP_DRAW
    elif match.winner_team_id == home.id:
        home.group_wins += 1
        away.group_losses += 1
        home.base_points += GROUP_WIN
    elif match.winner_team_id == away.id:
        away.group_wins += 1
        home.group_losses += 1
        away.base_points += GROUP_WIN


def _apply_advancement_points(team: WorldCupTeam) -> float:
    """Return advancement milestone base points for a team."""
    if team.advancement_method == 'group_winner':
        return ADVANCE_GROUP_WINNER
    elif team.advancement_method == 'runner_up':
        return ADVANCE_RUNNER_UP
    elif team.advancement_method == 'best_third':
        return ADVANCE_BEST_THIRD
    return 0.0


def _apply_knockout_points(match: WorldCupMatch) -> float:
    """Return knockout round base points for the winning team.

    Note: 'champion', 'runner_up', and 'third_place' in KNOCKOUT_POINTS
    are podium bonuses handled separately via best_finish.
    """
    stage = match.stage
    if stage in KNOCKOUT_POINTS and stage not in ('champion', 'runner_up', 'third_place'):
        return KNOCKOUT_POINTS[stage]
    return 0.0


def _apply_podium_bonus(team: WorldCupTeam) -> float:
    """Return podium bonus base points based on best_finish."""
    if team.best_finish == 'champion':
        return KNOCKOUT_POINTS['champion']
    elif team.best_finish == 'runner_up':
        return KNOCKOUT_POINTS['runner_up']
    elif team.best_finish == '3rd':
        return KNOCKOUT_POINTS['third_place']
    return 0.0


def _update_best_finish(team: WorldCupTeam, new_finish: str) -> None:
    """Update best_finish only if new_finish is deeper than current."""
    current_order = STAGE_ORDER.get(team.best_finish, -1)
    new_order = STAGE_ORDER.get(new_finish, -1)
    if new_order > current_order:
        team.best_finish = new_finish


def apply_group_advancement(group_letter: str, advancements: dict) -> dict:
    """Set advancement methods for a group after group stage concludes.

    advancements maps FIFA codes to methods:
        {'ESP': 'group_winner', 'URU': 'runner_up', 'KSA': 'best_third'}

    Teams in the group NOT in advancements are eliminated.
    """
    group_teams = WorldCupTeam.query.filter_by(
        group_letter=group_letter,
    ).all()

    advanced = []
    eliminated = []

    for team in group_teams:
        if team.fifa_code in advancements:
            team.advancement_method = advancements[team.fifa_code]
            team.is_eliminated = False
            advanced.append(team.fifa_code)
        else:
            team.is_eliminated = True
            team.best_finish = 'group'
            eliminated.append(team.fifa_code)

    recalculate_all_scores()

    return {
        'group': group_letter,
        'advanced': advanced,
        'eliminated': eliminated,
    }


def process_match_result(
    match_id: int,
    home_score: int,
    away_score: int,
    winner_fifa_code: str | None,
    is_draw: bool = False,
    extra_time: bool = False,
    penalties: bool = False,
) -> dict:
    """Enter a match result. Primary entry point for scoring during the tournament.

    Returns a summary dict. If the match is already completed, returns an
    error dict suggesting the admin use recalc after manually editing.
    """
    match = db.session.get(WorldCupMatch, match_id)
    if not match:
        return {'error': f'Match {match_id} not found'}

    if match.is_completed:
        return {
            'error': f'Match #{match.match_number} already completed. '
                     'Edit manually and run recalc.',
        }

    # Set match result fields
    match.home_score = home_score
    match.away_score = away_score
    match.is_draw = is_draw
    match.extra_time = extra_time
    match.penalties = penalties
    match.is_completed = True

    # Determine winner
    if winner_fifa_code:
        winner_team = WorldCupTeam.query.filter_by(
            fifa_code=winner_fifa_code,
        ).first()
        if winner_team:
            match.winner_team_id = winner_team.id
    elif not is_draw and match.stage == 'group':
        # Auto-determine winner from scores for group matches
        if home_score > away_score:
            match.winner_team_id = match.home_team_id
        elif away_score > home_score:
            match.winner_team_id = match.away_team_id

    # Update best_finish for knockout matches
    if match.stage != 'group' and match.winner_team_id:
        winner = db.session.get(WorldCupTeam, match.winner_team_id)
        loser_id = (
            match.away_team_id
            if match.winner_team_id == match.home_team_id
            else match.home_team_id
        )
        loser = db.session.get(WorldCupTeam, loser_id) if loser_id else None

        if match.stage == 'final':
            if winner:
                _update_best_finish(winner, 'champion')
            if loser:
                _update_best_finish(loser, 'runner_up')
        elif match.stage == 'third_place':
            if winner:
                _update_best_finish(winner, '3rd')
            # Loser stays at 'SF' — already set from losing the semifinal
        elif match.stage == 'SF':
            if winner:
                _update_best_finish(winner, 'SF')
            if loser:
                # SF losers get best_finish = 'SF', NOT eliminated (play 3rd place)
                _update_best_finish(loser, 'SF')
        else:
            # R32, R16, QF — winner's best_finish is the stage they won
            if winner:
                _update_best_finish(winner, match.stage)

    recalculate_all_scores()

    home_name = match.home_team.display_name if match.home_team else '?'
    away_name = match.away_team.display_name if match.away_team else '?'
    result_str = f'{home_name} {home_score}-{away_score} {away_name}'
    if is_draw:
        result_str += ' (draw)'

    return {
        'match_number': match.match_number,
        'result': result_str,
        'scores_updated': True,
    }


def set_knockout_teams(
    match_id: int,
    home_fifa_code: str,
    away_fifa_code: str,
) -> dict:
    """Assign teams to a knockout match shell as the bracket resolves."""
    match = db.session.get(WorldCupMatch, match_id)
    if not match:
        return {'error': f'Match {match_id} not found'}

    home = WorldCupTeam.query.filter_by(fifa_code=home_fifa_code).first()
    away = WorldCupTeam.query.filter_by(fifa_code=away_fifa_code).first()

    if not home or not away:
        missing = []
        if not home:
            missing.append(home_fifa_code)
        if not away:
            missing.append(away_fifa_code)
        return {'error': f'Team(s) not found: {", ".join(missing)}'}

    match.home_team_id = home.id
    match.away_team_id = away.id
    db.session.commit()

    return {
        'match_number': match.match_number,
        'home': home.display_name,
        'away': away.display_name,
    }


def compute_team_score_events(team: WorldCupTeam) -> list[ScoreEvent]:
    """Replay this team's scoring sources against current match/team state.

    Returns a chronologically-ordered list of ScoreEvents. The sum of
    `base_points` across events equals `team.base_points` (enforced via
    unit test). Pure function — performs no DB writes.
    """
    events: list[ScoreEvent] = []

    # Group-stage match events
    group_matches = (
        WorldCupMatch.query
        .filter_by(stage='group', is_completed=True)
        .filter(
            (WorldCupMatch.home_team_id == team.id)
            | (WorldCupMatch.away_team_id == team.id)
        )
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )
    for match in group_matches:
        opponent = (
            match.away_team if match.home_team_id == team.id else match.home_team
        )
        opp_code = opponent.fifa_code if opponent else '???'
        kickoff_date = match.kickoff_utc.date() if match.kickoff_utc else None
        if match.is_draw:
            events.append(ScoreEvent(
                source='group_draw',
                label=f'Draw vs {opp_code}',
                base_points=float(GROUP_DRAW),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))
        elif match.winner_team_id == team.id:
            events.append(ScoreEvent(
                source='group_win',
                label=f'Win vs {opp_code}',
                base_points=float(GROUP_WIN),
                match_id=match.id,
                occurred_on=kickoff_date,
            ))

    # Advancement milestone
    if team.advancement_method:
        adv_points = _apply_advancement_points(team)
        if adv_points > 0:
            adv_labels = {
                'group_winner': 'Group winner',
                'runner_up': 'Group runner-up',
                'best_third': 'Best 3rd place',
            }
            events.append(ScoreEvent(
                source='advancement',
                label=adv_labels.get(team.advancement_method, team.advancement_method),
                base_points=float(adv_points),
                match_id=None,
                occurred_on=None,
            ))

    # Knockout-match wins (R32, R16, QF, SF)
    knockout_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.stage != 'group')
        .filter(WorldCupMatch.is_completed == True)  # noqa: E712
        .filter(WorldCupMatch.winner_team_id == team.id)
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )
    for match in knockout_matches:
        stage_points = _apply_knockout_points(match)
        if stage_points <= 0:
            continue
        opponent = (
            match.away_team if match.home_team_id == team.id else match.home_team
        )
        opp_code = opponent.fifa_code if opponent else '???'
        kickoff_date = match.kickoff_utc.date() if match.kickoff_utc else None
        events.append(ScoreEvent(
            source='knockout',
            label=f'{match.stage}: beat {opp_code}',
            base_points=float(stage_points),
            match_id=match.id,
            occurred_on=kickoff_date,
        ))

    # Podium bonus
    podium_points = _apply_podium_bonus(team)
    if podium_points > 0:
        podium_labels = {
            'champion': 'Champion',
            'runner_up': 'Runner-up (final)',
            '3rd': 'Third place',
        }
        events.append(ScoreEvent(
            source='podium',
            label=podium_labels.get(team.best_finish or '', team.best_finish or ''),
            base_points=float(podium_points),
            match_id=None,
            occurred_on=None,
        ))

    return events
