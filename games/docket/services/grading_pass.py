"""ORM→snapshot adapter + persisted grading pass.

The thin seam D9-eng mandates: rows become frozen snapshots here (zero
datetime conversion — docket columns and snapshots are both naive UTC),
the pure engine grades, and the WeekGrade lands as docket_week_result
rows (D14-eng), upserted idempotently so `flask docket recalc` and the
admin NC auto-recalc can re-run at will.

Population contract: by default a week grades every user who submitted
ANY input (a pick or a prediction). Once enrollment exists, callers pass
`user_ids` with the full roster so enrolled no-input players get the
full D5 autopick treatment instead of being skipped.
"""
from sqlalchemy import select

from extensions import db
from games.docket.models import (
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeek,
    DocketWeekResult,
)
from games.docket.services.grading.engine import grade_week
from games.docket.services.grading.snapshots import (
    GameSnapshot,
    PickSnapshot,
    PlayerWeekInput,
    WeekSnapshot,
)
from games.docket.utils import now_utc, to_naive_utc


def build_week_snapshot(week: DocketWeek) -> WeekSnapshot:
    """Map a DocketWeek + its games to the engine's input, verbatim.

    Refuses to build when the deadline pass hasn't stamped
    kickoff_at_deadline (F6 — the substitution ordering input must be the
    frozen kickoff, never the live one) or when no tiebreaker game is
    designated. Scores flow through only when is_final — an in-progress
    score must never grade.
    """
    if week.tiebreaker_game_id is None:
        raise ValueError(
            f'week {week.week_number} has no designated tiebreaker game')
    tiebreaker_event_id = None
    games = []
    for game in sorted(week.games, key=lambda g: g.api_event_id):
        if game.kickoff_at_deadline is None:
            raise ValueError(
                f'{game.api_event_id}: kickoff_at_deadline is not stamped '
                f'— run the deadline pass before grading')
        final = game.is_final and not game.no_contest
        games.append(GameSnapshot(
            api_event_id=game.api_event_id,
            sport=game.sport,
            home_team=game.home_team,
            away_team=game.away_team,
            kickoff_at_deadline=game.kickoff_at_deadline,
            home_spread=game.home_spread,
            total=game.total_points,
            home_score=game.home_score if final else None,
            away_score=game.away_score if final else None,
            no_contest=game.no_contest,
        ))
        if game.id == week.tiebreaker_game_id:
            tiebreaker_event_id = game.api_event_id
    if tiebreaker_event_id is None:
        raise ValueError(
            f'week {week.week_number}: designated tiebreaker game is not '
            f'on this week\'s docket')
    return WeekSnapshot(
        week_number=week.week_number,
        deadline_at=week.deadline_at,
        games=tuple(games),
        tiebreaker_event_id=tiebreaker_event_id,
    )


def build_player_inputs(week: DocketWeek) -> tuple[PlayerWeekInput, ...]:
    """One PlayerWeekInput per user with any input this week, ordered by
    user id. player_id is str(user_id) — the engine treats it as opaque."""
    event_by_game_id = {g.id: g.api_event_id for g in week.games}
    picks_by_user: dict[int, list] = {}
    for pick in db.session.scalars(
            select(DocketPick).filter_by(week_id=week.id)
            .order_by(DocketPick.user_id, DocketPick.slot)):
        picks_by_user.setdefault(pick.user_id, []).append(PickSnapshot(
            slot=pick.slot,
            api_event_id=event_by_game_id[pick.game_id],
            market=pick.market,
            side=pick.side,
            is_best=pick.is_best,
            is_autopick=pick.is_autopick,
        ))
    predictions = {
        row.user_id: row.prediction_tenths
        for row in db.session.scalars(
            select(DocketTiebreakerPrediction).filter_by(week_id=week.id))
    }
    user_ids = sorted(set(picks_by_user) | set(predictions))
    return tuple(
        PlayerWeekInput(
            player_id=str(user_id),
            picks=tuple(picks_by_user.get(user_id, ())),
            tiebreaker_tenths=predictions.get(user_id),
        )
        for user_id in user_ids
    )


def run_grading_pass(week_id: int, user_ids=None) -> dict:
    """Grade a week and upsert docket_week_result rows (D14-eng).

    Raises EngineError (via grade_week) when a picked, non-NC game lacks
    a final score — the caller, not the engine, decides when a week is
    ready. Re-running updates rows in place; is_dropped is owned by the
    season pass and left untouched on update.
    """
    week = db.session.get(DocketWeek, week_id)
    if week is None:
        raise ValueError(f'no docket week with id {week_id}')
    snapshot = build_week_snapshot(week)
    players = build_player_inputs(week)
    if user_ids is not None:
        by_id = {p.player_id: p for p in players}
        players = tuple(
            by_id.get(str(uid), PlayerWeekInput(
                player_id=str(uid), picks=(), tiebreaker_tenths=None))
            for uid in user_ids)

    grade = grade_week(snapshot, players)
    graded_at = to_naive_utc(now_utc())
    for player_grade in grade.players:
        user_id = int(player_grade.player_id)
        row = db.session.scalar(
            select(DocketWeekResult).filter_by(user_id=user_id,
                                               week_id=week.id))
        if row is None:
            row = DocketWeekResult(
                user_id=user_id, week_id=week.id,
                points=player_grade.points, wins=player_grade.wins,
                error_tenths=player_grade.error_tenths,
                graded_at=graded_at)
            db.session.add(row)
        else:
            row.points = player_grade.points
            row.wins = player_grade.wins
            row.error_tenths = player_grade.error_tenths
            row.graded_at = graded_at
    db.session.commit()
    return {
        'status': 'ok',
        'week_number': week.week_number,
        'graded': len(grade.players),
    }
