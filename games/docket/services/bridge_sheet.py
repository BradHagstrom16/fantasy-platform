"""
The Docket — sport labels and the tiebreaker hand override
==========================================================
The module's name outlives the Google Sheet bridge it once generated (D22),
dropped when The Docket launched platform-native.
"""
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame

SPORT_LABELS = {
    'americanfootball_ncaaf': 'CFB',
    'americanfootball_nfl': 'NFL',
}


def set_tiebreaker(week, matchup):
    """Designate the week's tiebreaker game from an 'Away @ Home' string.

    Case-insensitive substring match on both team names; exactly one game
    must match (e.g. 'SMU @ Florida State'). Raises ValueError on no match,
    an ambiguous match, or a malformed matchup. This is the hand override of
    the rule-derived default (services/tiebreaker_rule.py).

    Only the matchup-string resolution lives here. The write itself
    delegates to ``admin_ops.designate_tiebreaker``, so this CLI fallback and
    T9's admin UI share one contract: the same designation validation, the
    same prediction-clearing on a re-designation, the same notification. An
    unsound designation now rolls back instead of committing and then being
    reported, which is why the refusal arrives as a ValueError carrying the
    contract's own problem strings.
    """
    if ' @ ' not in matchup:
        raise ValueError(f"Tiebreaker must be 'Away @ Home', got {matchup!r}")
    away_q, home_q = (part.strip().lower() for part in matchup.split(' @ ', 1))
    if not away_q or not home_q:
        # A blank side substring-matches every name — on a one-game week
        # that would silently designate the wrong game.
        raise ValueError(
            f"Tiebreaker must name both teams ('Away @ Home'), got {matchup!r}")
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)).all()
    matches = [g for g in games
               if away_q in g.away_team.lower() and home_q in g.home_team.lower()]
    if len(matches) != 1:
        raise ValueError(
            f'Tiebreaker {matchup!r} matched {len(matches)} games in week '
            f'{week.week_number}; need exactly 1')
    # Imported here, not at module scope: routes.py imports this module for
    # SPORT_LABELS while the blueprint is still assembling, and admin_ops
    # reaches the grading and deadline services.
    from games.docket.services.admin_ops import (
        AdminOpError,
        designate_tiebreaker,
    )
    try:
        return designate_tiebreaker(week, matches[0].id)['game']
    except AdminOpError as exc:
        raise ValueError('; '.join([exc.message, *exc.problems])) from exc
