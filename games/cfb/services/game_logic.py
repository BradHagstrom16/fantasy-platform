"""
CFB Survivor Pool — Game Logic Service
========================================
Core business logic: result processing, auto-picks, team eligibility,
cumulative spread calculation.
"""

import logging

from flask import current_app

from extensions import db
from models import User
from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek, CfbGame, CfbPick
from games.cfb.utils import (
    get_current_time, get_utc_time, make_aware, deadline_has_passed,
    is_week_playoff, get_cfp_eliminated_teams,
)

logger = logging.getLogger(__name__)


def _get_season_year():
    """Get the configured CFB season year."""
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


# ---------------------------------------------------------------------------
# Team eligibility
# ---------------------------------------------------------------------------

def get_game_for_team(week_id, team_id):
    """Return the CfbGame in this week that involves the given team."""
    return CfbGame.query.filter_by(week_id=week_id).filter(
        db.or_(CfbGame.home_team_id == team_id, CfbGame.away_team_id == team_id)
    ).first()


def get_used_team_ids(user_id, week, *, exclude_current=True):
    """Return set of team IDs the user has already picked in the current phase."""
    q = db.session.query(CfbPick.team_id).join(CfbWeek)

    if is_week_playoff(week):
        q = q.filter(CfbWeek.is_playoff_week == True)  # noqa: E712
    else:
        q = q.filter(CfbWeek.is_playoff_week == False)  # noqa: E712

    q = q.filter(CfbPick.user_id == user_id)
    if exclude_current:
        q = q.filter(CfbPick.week_id != week.id)

    return {t[0] for t in q.all()}


# ---------------------------------------------------------------------------
# Cumulative spread
# ---------------------------------------------------------------------------

def calculate_cumulative_spread(enrollment):
    """Recalculate cumulative spread for an enrollment.

    Cumulative spread = sum of the spread (from the picked team's perspective)
    across all of this user's picks where the game has a spread.
    Used as a tiebreaker — tracks how safely users pick.
    """
    picks = CfbPick.query.filter_by(user_id=enrollment.user_id).all()
    total = 0.0

    for pick in picks:
        game = get_game_for_team(pick.week_id, pick.team_id)
        # No Contest games are a push — their spread is excluded (DQ-4).
        if game and not game.is_no_contest and game.home_team_spread is not None:
            spread = game.get_spread_for_team(pick.team_id)
            if spread is not None:
                total += spread

    enrollment.cumulative_spread = total


# ---------------------------------------------------------------------------
# Result processing
# ---------------------------------------------------------------------------

def process_week_results(week_id, season_year=None):
    """Grade picks and settle lives for a week. Safe to re-run.

    Idempotency contract (audit Top-5 #1/#2):
      - per-pick effects fire only when ``is_correct`` transitions from None;
      - week-level effects (no-pick penalties, revival, ``is_complete``)
        fire only in the run that completes the week, and this function is
        the sole owner of ``CfbWeek.is_complete`` on the processing path;
      - an already-complete week short-circuits to a no-op.

    Week-level rules (DQ-1/DQ-2/DQ-4): once every game is settled
    (decided or No Contest), active players with no pick lose a life;
    No Contest picks push (no grade, no life loss, player survived);
    revival fires only on a whole-pool wipe (zero active players left
    AND >1 eliminated this week) and revives only those who picked —
    a wipe with nobody eligible to revive is surfaced via pool_empty.

    Returns dict: success, already_complete, processed (picks graded this
    run), completed, no_pick_penalties, revived, pool_empty.
    """
    week = db.session.get(CfbWeek, week_id)
    if not week:
        logger.error("process_week_results: Week %s not found", week_id)
        return {"success": False, "error": f"Week {week_id} not found"}

    result = {
        "success": True, "already_complete": False, "processed": 0,
        "completed": False, "no_pick_penalties": 0, "revived": 0,
        "pool_empty": False,
    }
    if week.is_complete:
        return {**result, "already_complete": True}

    if season_year is None:
        season_year = _get_season_year()

    try:
        picks = CfbPick.query.filter_by(week_id=week_id).all()
        pick_by_user = {p.user_id: p for p in picks}

        season_enrollments = CfbEnrollment.query.filter_by(
            season_year=season_year
        ).all()
        enrollment_by_user = {e.user_id: e for e in season_enrollments}

        # Team-keyed lookup of gradeable games (decided, not No Contest)
        games = CfbGame.query.filter_by(week_id=week_id).all()
        games_by_team = {}
        for game in games:
            if game.home_team_won is not None and not game.is_no_contest:
                if game.home_team_id:
                    games_by_team[game.home_team_id] = game
                if game.away_team_id:
                    games_by_team[game.away_team_id] = game

        graded = 0
        for pick in picks:
            if pick.is_correct is not None:
                continue  # graded on a previous run — never re-grade
            game = games_by_team.get(pick.team_id)
            if not game:
                continue  # undecided (pending) or No Contest (permanent push)

            pick.is_correct = (
                game.home_team_won if pick.team_id == game.home_team_id
                else not game.home_team_won
            )
            graded += 1

            if not pick.is_correct:
                enrollment = enrollment_by_user.get(pick.user_id)
                if enrollment and not enrollment.is_eliminated:
                    enrollment.lives_remaining -= 1
                    if enrollment.lives_remaining <= 0:
                        enrollment.lives_remaining = 0
                        enrollment.is_eliminated = True
        result["processed"] = graded

        for user_id in pick_by_user:
            enrollment = enrollment_by_user.get(user_id)
            if enrollment:
                calculate_cumulative_spread(enrollment)

        # Week-level effects only in the run that completes the week.
        # A 0-game week (orphaned import) must never complete — it would
        # no-pick-penalize the entire pool.
        all_settled = bool(games) and all(g.is_settled for g in games)
        if all_settled:
            # DQ-2: active players with no pick lose a life
            no_pick_eliminated = 0
            for enrollment in season_enrollments:
                if enrollment.is_eliminated or enrollment.user_id in pick_by_user:
                    continue
                enrollment.lives_remaining -= 1
                result["no_pick_penalties"] += 1
                if enrollment.lives_remaining <= 0:
                    enrollment.lives_remaining = 0
                    enrollment.is_eliminated = True
                    no_pick_eliminated += 1

            week.is_complete = True
            result["completed"] = True

            # DQ-1 revival: whole-pool wipe only. Eliminated-this-week
            # pickers are derived from this week's pick rows so the set
            # survives partial runs (an enrollment eliminated in an earlier
            # week cannot have a pick in this one).
            active_remaining = [
                e for e in season_enrollments if not e.is_eliminated
            ]
            if not active_remaining:
                wiped_pickers = []
                for enrollment in season_enrollments:
                    pick = pick_by_user.get(enrollment.user_id)
                    if (enrollment.is_eliminated and pick is not None
                            and pick.is_correct is False):
                        wiped_pickers.append(enrollment)

                eliminated_this_week = len(wiped_pickers) + no_pick_eliminated
                if eliminated_this_week > 1 and wiped_pickers:
                    for enrollment in wiped_pickers:
                        enrollment.lives_remaining = 1
                        enrollment.is_eliminated = False
                    result["revived"] = len(wiped_pickers)
                    logger.info(
                        "REVIVAL RULE ACTIVATED: Week %s — whole-pool wipe, "
                        "%d players revived",
                        week.week_number, result["revived"],
                    )
                else:
                    result["pool_empty"] = True
                    logger.warning(
                        "Week %s completed with zero active players and no "
                        "revival-eligible picks — pool is empty; admin "
                        "review required",
                        week.week_number,
                    )

        db.session.commit()
        return result

    except Exception:
        db.session.rollback()
        logger.exception("process_week_results failed for week %s", week_id)
        return {"success": False, "error": "Database error during result processing"}


# ---------------------------------------------------------------------------
# Auto-picks
# ---------------------------------------------------------------------------

def process_autopicks(week_id, season_year=None):
    """Process auto-picks for users who missed the deadline."""
    week = db.session.get(CfbWeek, week_id)
    if not week:
        return {"processed": False, "reason": f"Week {week_id} not found"}

    deadline = make_aware(week.deadline)
    if not deadline_has_passed(deadline):
        return {"processed": False, "reason": "Deadline not yet passed"}

    if season_year is None:
        season_year = _get_season_year()

    active_enrollments = CfbEnrollment.query.filter_by(
        is_eliminated=False, season_year=season_year
    ).all()
    enrollment_by_user = {e.user_id: e for e in active_enrollments}

    # Pre-load user objects for logging
    user_objects = {
        u.id: u for u in User.query.filter(
            User.id.in_(enrollment_by_user.keys())
        ).all()
    } if enrollment_by_user else {}

    existing_picks = CfbPick.query.filter_by(week_id=week_id).all()
    users_with_picks = {pick.user_id for pick in existing_picks}

    enrollments_needing_autopick = [
        e for e in active_enrollments if e.user_id not in users_with_picks
    ]

    if not enrollments_needing_autopick:
        return {"processed": True, "autopicks": 0, "reason": "All active users have picks"}

    autopicks_made = []
    autopicks_failed = []

    current_time = get_current_time()
    games = [
        g for g in CfbGame.query.filter_by(week_id=week_id).all()
        if not g.game_time or make_aware(g.game_time) > current_time
    ]

    cfp_eliminated_names = set()
    if is_week_playoff(week):
        cfp_eliminated_names = get_cfp_eliminated_teams()

    for enrollment in enrollments_needing_autopick:
        user = user_objects.get(enrollment.user_id)
        username = user.username if user else f"user_{enrollment.user_id}"
        used_team_ids = get_used_team_ids(enrollment.user_id, week)

        best_team = None
        best_spread = None
        best_favoritism = -999

        for game in games:
            # Check home team
            if (game.home_team and game.home_team_id not in used_team_ids
                    and game.home_team_spread is not None):
                if is_week_playoff(week) and game.home_team.name in cfp_eliminated_names:
                    continue
                home_favoritism = -game.home_team_spread
                if 0 < home_favoritism <= 16:
                    if home_favoritism > best_favoritism:
                        best_favoritism = home_favoritism
                        best_spread = game.home_team_spread
                        best_team = game.home_team

            # Check away team
            if (game.away_team and game.away_team_id not in used_team_ids
                    and game.home_team_spread is not None):
                if is_week_playoff(week) and game.away_team.name in cfp_eliminated_names:
                    continue
                away_favoritism = game.home_team_spread
                if 0 < away_favoritism <= 16:
                    if away_favoritism > best_favoritism:
                        best_favoritism = away_favoritism
                        best_spread = -game.home_team_spread
                        best_team = game.away_team

        # Fallback: pick the smallest underdog
        if not best_team:
            smallest_underdog = None
            smallest_underdog_points = 999

            for game in games:
                if (game.home_team and game.home_team_id not in used_team_ids
                        and game.home_team_spread is not None):
                    if is_week_playoff(week) and game.home_team.name in cfp_eliminated_names:
                        continue
                    if game.home_team_spread > 0 and game.home_team_spread < smallest_underdog_points:
                        smallest_underdog_points = game.home_team_spread
                        smallest_underdog = game.home_team
                        best_spread = game.home_team_spread

                if (game.away_team and game.away_team_id not in used_team_ids
                        and game.home_team_spread is not None):
                    if is_week_playoff(week) and game.away_team.name in cfp_eliminated_names:
                        continue
                    away_spread = -game.home_team_spread
                    if away_spread > 0 and away_spread < smallest_underdog_points:
                        smallest_underdog_points = away_spread
                        smallest_underdog = game.away_team
                        best_spread = away_spread

            best_team = smallest_underdog

        if best_team:
            auto_pick = CfbPick(
                user_id=enrollment.user_id,
                week_id=week_id,
                team_id=best_team.id,
                created_at=get_utc_time(),
            )
            db.session.add(auto_pick)
            calculate_cumulative_spread(enrollment)

            if best_spread and best_spread < 0:
                favoritism_text = f"favored by {-best_spread} points"
            elif best_spread and best_spread > 0:
                favoritism_text = f"underdog by {best_spread} points"
            else:
                favoritism_text = "pick'em"

            autopicks_made.append({
                "user": username,
                "team": best_team.name,
                "spread": best_spread,
                "description": favoritism_text,
            })
            logger.info("Auto-pick: %s -> %s (%s)", username, best_team.name, favoritism_text)
        else:
            autopicks_failed.append({
                "user": username,
                "reason": "No eligible teams available",
            })
            logger.warning("Auto-pick failed: %s - No eligible teams", username)

    if autopicks_made:
        db.session.commit()

    return {
        "processed": True,
        "autopicks": len(autopicks_made),
        "failed": len(autopicks_failed),
        "details": autopicks_made,
        "failures": autopicks_failed,
    }


def check_and_process_autopicks():
    """Check all active weeks and process autopicks if past deadline."""
    weeks = CfbWeek.query.filter_by(is_complete=False).all()
    results = []
    for week in weeks:
        deadline = make_aware(week.deadline)
        if deadline_has_passed(deadline):
            result = process_autopicks(week.id)
            if result["processed"] and result["autopicks"] > 0:
                results.append(
                    f"Week {week.week_number}: {result['autopicks']} auto-picks made"
                )
    return results
