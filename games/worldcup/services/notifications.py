"""
World Cup Fantasy Pool — Player Notification Service
=====================================================
Daily match-result digest emails. Sent at 5am CT via the wc-digest-player
systemd timer for every enrolled player whose picks scored the previous
CT calendar day.

One email per player, max. Skips players with no scoring picks that day.
Points are fully multiplied (per points_for_pick_on_match contract).
"""
import logging
import os
import subprocess
from datetime import timedelta, timezone
from pathlib import Path

from flask import current_app, render_template
from sqlalchemy import func

from extensions import db
from utils.email import send_platform_email
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import WorldCupEnrollment, WorldCupMatch, WorldCupPick
from games.worldcup.services.ranking import compute_rank_delta
from games.worldcup.services.scoring import points_for_pick_on_match
from games.worldcup.services.stage import stage_label
from games.worldcup.services.state import now_utc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_pts(pts: float) -> str:
    """'18' for whole numbers, '4.5' for fractions."""
    return str(int(pts)) if pts == int(pts) else f'{pts:.1f}'


def _fmt_multiplier(m: float) -> str:
    """'×1' for whole numbers, '×1.5' for fractions."""
    return f'×{int(m)}' if m == int(m) else f'×{m}'


def _match_score_str(match: WorldCupMatch) -> str:
    """'BRA 2–0 MEX' (home–away order, en dash)."""
    home = match.home_team.fifa_code if match.home_team else '?'
    away = match.away_team.fifa_code if match.away_team else '?'
    h = match.home_score if match.home_score is not None else '?'
    a = match.away_score if match.away_score is not None else '?'
    return f'{home} {h}–{a} {away}'


def _result_for_pick(pick: WorldCupPick, match: WorldCupMatch) -> str:
    """'won', 'draw', or 'lost' from the pick's team perspective."""
    if match.is_draw:
        return 'draw'
    if match.winner_team_id == pick.team_id:
        return 'won'
    return 'lost'


def _dense_rank(enrollment: WorldCupEnrollment) -> tuple[int, int]:
    """(rank, total_players) using dense rank for the active season."""
    higher = (
        db.session.query(func.count(WorldCupEnrollment.id))
        .filter(
            WorldCupEnrollment.season_year == SEASON_YEAR,
            WorldCupEnrollment.total_score > enrollment.total_score,
            WorldCupEnrollment.picks_submitted == True,  # noqa: E712
        )
        .scalar() or 0
    )
    total = (
        db.session.query(func.count(WorldCupEnrollment.id))
        .filter(
            WorldCupEnrollment.season_year == SEASON_YEAR,
            WorldCupEnrollment.picks_submitted == True,  # noqa: E712
        )
        .scalar() or 0
    )
    return higher + 1, total


def _asset_version() -> str:
    """Resolve cache-bust token: ASSET_VERSION env var, then git short SHA, then 'dev'."""
    env = os.environ.get('ASSET_VERSION', '').strip()
    if env:
        return env
    root = Path(__file__).resolve().parents[3]
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=root, stderr=subprocess.DEVNULL, timeout=2,
        ).strip().decode('ascii')
        return sha or 'dev'
    except Exception:
        return 'dev'


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------

def _plain_body(
    enrollment: WorldCupEnrollment,
    match_results: list[dict],
    total_yesterday_str: str,
    rank: int,
    total_enrolled: int,
    rank_delta: int | None,
    date_str: str,
    site_url: str,
) -> str:
    name = enrollment.get_display_name()
    score = _fmt_pts(float(enrollment.total_score))
    if rank_delta is None:
        rank_str = f'#{rank} of {total_enrolled}'
    elif rank_delta > 0:
        rank_str = f'#{rank} of {total_enrolled}  (up {rank_delta} spot{"s" if rank_delta != 1 else ""})'
    elif rank_delta < 0:
        rank_str = f'#{rank} of {total_enrolled}  (down {abs(rank_delta)} spot{"s" if abs(rank_delta) != 1 else ""})'
    else:
        rank_str = f'#{rank} of {total_enrolled}  (steady)'
    lines = [
        f'Your World Cup results for {date_str}',
        '=' * 40,
        '',
        f'Good morning, {name}',
        '',
        f'Total score : {score} pts',
        f'Yesterday   : +{total_yesterday_str} pts',
        f'Rank        : {rank_str}',
        '',
        'Picks that scored:',
        '-' * 36,
    ]
    for r in match_results:
        lines.append(
            f'  {r["team"].display_name} ({r["multiplier_str"]})'
            f'  {r["match_score"]}  {r["result"].title()}'
            f'  +{r["points_str"]} pts'
        )
    lines += [
        '',
        f'Full standings: {site_url}/worldcup/leaderboard',
        '',
        'Corrupt Commish Club -- cccfantasy.com',
    ]
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def send_daily_digests() -> dict:
    """Send WC daily digest to players whose picks scored yesterday (CT).

    Called by `flask worldcup send-digest` and the wc-digest-player.timer at
    5am CT. Covers matches completed on the previous CT calendar day.
    Returns a summary dict suitable for CLI output or admin logging.
    """
    yesterday = (now_utc().astimezone(WORLDCUP_TZ) - timedelta(days=1)).date()

    # Matches completed on yesterday (CT) — match updated_at to CT calendar day.
    all_completed = WorldCupMatch.query.filter_by(is_completed=True).all()
    yesterdays_matches = [
        m for m in all_completed
        if m.updated_at
        and m.updated_at.replace(tzinfo=timezone.utc).astimezone(WORLDCUP_TZ).date() == yesterday
        and m.home_team_id
        and m.away_team_id
    ]

    if not yesterdays_matches:
        return {'status': 'no_results', 'date': str(yesterday)}

    # Set of team IDs active yesterday.
    team_ids_played: set[int] = set()
    for m in yesterdays_matches:
        team_ids_played.add(m.home_team_id)
        team_ids_played.add(m.away_team_id)

    site_url = current_app.config.get('SITE_URL', 'https://cccfantasy.com').rstrip('/')
    logo_url = f'{site_url}/static/img/logo/ccc-logo-stacked.svg'
    av = _asset_version()
    date_str = yesterday.strftime('%B %-d')  # e.g. "June 1"

    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR, picks_submitted=True)
        .all()
    )
    total_enrolled = len(enrollments)

    sent = skipped_no_match = skipped_no_score = skipped_no_email = errors = 0

    for enrollment in enrollments:
        if not enrollment.user or not enrollment.user.email:
            skipped_no_email += 1
            continue

        # Picks whose team played yesterday.
        picks_in_play = [
            p for p in enrollment.picks if p.team_id in team_ids_played
        ]
        if not picks_in_play:
            skipped_no_match += 1
            continue

        # Build per-match scoring rows (scoring events only, pts > 0).
        match_results = []
        for match in sorted(yesterdays_matches, key=lambda m: m.match_number):
            for pick in picks_in_play:
                if pick.team_id not in {match.home_team_id, match.away_team_id}:
                    continue
                pts = points_for_pick_on_match(pick, match)
                if pts <= 0:
                    continue
                match_results.append({
                    'team': pick.team,
                    'match': match,
                    'multiplier_str': _fmt_multiplier(pick.team.multiplier),
                    'match_score': _match_score_str(match),
                    'stage_label': stage_label(match.stage),
                    'result': _result_for_pick(pick, match),
                    'points_earned': pts,
                    'points_str': _fmt_pts(pts),
                })

        if not match_results:
            skipped_no_score += 1
            continue

        total_yesterday = sum(r['points_earned'] for r in match_results)
        total_yesterday_str = _fmt_pts(total_yesterday)
        rank, _ = _dense_rank(enrollment)
        rank_delta = compute_rank_delta(enrollment, window_days=1)

        try:
            html_body = render_template(
                'worldcup/email/wc_daily_digest.j2',
                enrollment=enrollment,
                match_results=match_results,
                total_yesterday_str=total_yesterday_str,
                rank=rank,
                total_enrolled=total_enrolled,
                rank_delta=rank_delta,
                date_str=date_str,
                site_url=site_url,
                logo_url=logo_url,
                asset_version=av,
            )
            plain_body = _plain_body(
                enrollment, match_results, total_yesterday_str,
                rank, total_enrolled, rank_delta, date_str, site_url,
            )
            subject = f'Your World Cup picks on {date_str}'
            ok = send_platform_email(enrollment.user.email, subject, plain_body, html_body)
            if ok:
                sent += 1
            else:
                errors += 1
        except Exception:
            logger.exception('Digest send failed for enrollment %s', enrollment.id)
            errors += 1

    return {
        'status': 'sent' if sent else 'no_sends',
        'sent': sent,
        'skipped_no_match': skipped_no_match,
        'skipped_no_score': skipped_no_score,
        'skipped_no_email': skipped_no_email,
        'errors': errors,
        'date': str(yesterday),
    }
