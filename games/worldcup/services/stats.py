from sqlalchemy import func

from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick
from games.worldcup.services.scoring import compute_team_score_events

_GROUP_SOURCES = {'group_win', 'group_draw', 'advancement'}
_KO_SOURCES = {'knockout', 'podium'}


def get_country_stats(season_year: int) -> tuple[list[dict], int]:
    """Return (country_list, total_players) for the given season.

    Every WorldCupTeam row is included, even if pick_count is 0.
    """
    total_players: int = WorldCupEnrollment.query.filter_by(
        season_year=season_year
    ).count()

    pick_counts: dict[int, int] = dict(
        db.session.query(WorldCupPick.team_id, func.count(WorldCupPick.id))
        .join(WorldCupEnrollment, WorldCupPick.enrollment_id == WorldCupEnrollment.id)
        .filter(WorldCupEnrollment.season_year == season_year)
        .group_by(WorldCupPick.team_id)
        .all()
    )

    result = []
    for team in WorldCupTeam.query.all():  # teams are global (no season_year column)
        events = compute_team_score_events(team)
        group_base = sum(e.base_points for e in events if e.source in _GROUP_SOURCES)
        ko_base = sum(e.base_points for e in events if e.source in _KO_SOURCES)

        pick_count = pick_counts.get(team.id, 0)
        pick_pct = (pick_count / total_players * 100) if total_players > 0 else 0.0

        result.append({
            'name': team.display_name,
            'flag_emoji': team.flag_emoji,
            'tier': team.tier,
            'multiplier': team.multiplier,
            'pick_count': pick_count,
            'pick_pct': pick_pct,
            'group_score': group_base * team.multiplier,
            'ko_score': ko_base * team.multiplier,
            'total_score': team.multiplied_points,
            'is_active': not team.is_eliminated,
        })

    return result, total_players


def get_tier_stats(country_stats: list[dict]) -> dict[int, dict]:
    """Pure Python — no DB calls. Groups country_stats by tier."""
    tiers: dict[int, list[dict]] = {}
    for c in country_stats:
        tiers.setdefault(c['tier'], []).append(c)

    result: dict[int, dict] = {}
    for tier, countries in tiers.items():
        scores = [c['total_score'] for c in countries]
        best = max(countries, key=lambda c: c['total_score'])
        result[tier] = {
            'avg_score': sum(scores) / len(scores),
            'total_score': sum(scores),
            'best_country': best['name'],
            'best_score': best['total_score'],
        }
    return result


def get_overview_kpis(country_stats: list[dict], total_players: int) -> dict:
    """No DB calls — derived from country_stats and total_players."""
    if not country_stats:
        return {
            'total_players': total_players,
            'active_countries': 0,
            'top_country_score': 0.0,
            'top_country_name': '',
            'total_pts_awarded': 0.0,
        }
    top = max(country_stats, key=lambda c: c['total_score'])
    return {
        'total_players': total_players,
        'active_countries': sum(1 for c in country_stats if c['is_active']),
        'top_country_score': top['total_score'],
        'top_country_name': top['name'],
        'total_pts_awarded': sum(c['total_score'] for c in country_stats),
    }
