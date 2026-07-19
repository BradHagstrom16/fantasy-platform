"""
World Cup Fantasy Pool — Player Notification Service
=====================================================
Daily match-result digest emails. Sent at 5am CT via the wc-digest-player
systemd timer for every enrolled player whose picks scored the previous
CT calendar day.

One email per player, max. Skips players with no scoring picks that day.
Points are fully multiplied (per the display_points_for_pick_on_match
contract, which also attributes podium bonuses to their deciding match so
the championship-day digest carries the champion's +50 / runner-up's +8).

Also: the picks confirmation receipt (send_picks_confirmation), fired by
the /worldcup/picks POST success path on every save.
"""
import logging
import os
import subprocess
from datetime import UTC, timedelta
from pathlib import Path

from flask import current_app, render_template
from sqlalchemy import func

from extensions import db
from games.worldcup.constants import (
    ADVANCE_BEST_THIRD,
    ADVANCE_GROUP_WINNER,
    ADVANCE_RUNNER_UP,
    KNOCKOUT_POINTS,
    SEASON_YEAR,
    TOURNAMENT_DEADLINE_UTC,
    WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
)
from games.worldcup.services.ranking import compute_rank_delta
from games.worldcup.services.scoring import display_points_for_pick_on_match
from games.worldcup.services.stage import stage_label
from games.worldcup.services.state import now_utc
from games.worldcup.services.sync import all_group_advancement_confirmed
from games.worldcup.world_cup_countries import TIERS
from utils.email import send_platform_email

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


def _competition_rank(enrollment: WorldCupEnrollment) -> tuple[int, int]:
    """(rank, total_players) using competition rank for the active season.

    rank = 1 + count of enrollments scoring strictly higher, so tied scores
    share a rank and the next distinct score gaps by the size of the tie
    (1, 1, 3) — parity with compute_rank_neighbors() / routes.leaderboard().
    """
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
# Group-stage recap marker (idempotency / "last sent" display)
# ---------------------------------------------------------------------------

def _group_recap_marker_path() -> str:
    return os.path.join(current_app.instance_path, '.wc_group_recap_sent')


def group_recap_last_sent() -> str | None:
    """Return the ISO date string of the last recap send, or None."""
    try:
        with open(_group_recap_marker_path()) as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _mark_group_recap_sent() -> None:
    try:
        os.makedirs(current_app.instance_path, exist_ok=True)
        with open(_group_recap_marker_path(), 'w') as fh:
            fh.write(now_utc().astimezone(WORLDCUP_TZ).strftime('%Y-%m-%d'))
    except OSError:
        logger.warning('Could not write group-recap marker.')


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
        and m.updated_at.replace(tzinfo=UTC).astimezone(WORLDCUP_TZ).date() == yesterday
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
                # Display helper folds podium bonuses into their deciding
                # match. Without it the pts<=0 filter dropped the final's
                # champion/runner-up rows entirely — finalists' owners got
                # NO digest on championship day (2026-07-19 incident class).
                pts, podium_code = display_points_for_pick_on_match(pick, match)
                if pts <= 0:
                    continue
                podium_words = {
                    'champion': 'champions',
                    'runner_up': 'runners-up',
                    '3rd': 'third place',
                }
                result = (
                    podium_words[podium_code] if podium_code
                    else _result_for_pick(pick, match)
                )
                match_results.append({
                    'team': pick.team,
                    'match': match,
                    'multiplier_str': _fmt_multiplier(pick.team.multiplier),
                    'match_score': _match_score_str(match),
                    'stage_label': stage_label(match.stage),
                    'result': result,
                    'points_earned': pts,
                    'points_str': _fmt_pts(pts),
                })

        if not match_results:
            skipped_no_score += 1
            continue

        total_yesterday = sum(r['points_earned'] for r in match_results)
        total_yesterday_str = _fmt_pts(total_yesterday)
        rank, _ = _competition_rank(enrollment)
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


# ---------------------------------------------------------------------------
# Group-stage recap (admin-triggered at bracket lock)
# ---------------------------------------------------------------------------

_ADV_LABEL = {'group_winner': 'Group winner', 'runner_up': 'Runner-up', 'best_third': 'Best 3rd place'}
_ADV_BASE = {'group_winner': ADVANCE_GROUP_WINNER, 'runner_up': ADVANCE_RUNNER_UP, 'best_third': ADVANCE_BEST_THIRD}

# Multiplied knockout ladder for the "what's at stake" section.
_KO_LADDER = [('Round of 32', 'R32'), ('Round of 16', 'R16'), ('Quarterfinal', 'QF'),
              ('Semifinal', 'SF'), ('Final / 3rd place', 'runner_up'), ('Champion', 'champion')]


def _recap_rows(enrollment):
    """(advanced_rows, eliminated_rows, total_adv_pts) for one enrollment.

    advanced_rows: dicts with team, method_label, base, multiplier, points (multiplied).
    eliminated_rows: dicts with team.
    """
    advanced, eliminated, total = [], [], 0.0
    for pick in sorted(enrollment.picks, key=lambda p: (p.team.tier, p.team.display_name)):
        t = pick.team
        if t.advancement_method:
            base = _ADV_BASE.get(t.advancement_method, 0)
            pts = base * t.multiplier
            total += pts
            advanced.append({'team': t, 'method_label': _ADV_LABEL.get(t.advancement_method, t.advancement_method),
                             'base': base, 'multiplier': t.multiplier, 'points': pts})
        elif t.is_eliminated:
            eliminated.append({'team': t})
    return advanced, eliminated, total


def send_group_stage_recap() -> dict:
    """Email each player a personalized group-stage recap. Admin-triggered.

    Guarded: refuses unless every group's advancement is confirmed. Mirrors
    send_daily_digests structure; one email per enrolled, picks-submitted player
    with an address.
    """
    if not all_group_advancement_confirmed():
        return {'status': 'blocked', 'reason': 'group advancement not fully confirmed'}

    site_url = current_app.config.get('SITE_URL', 'https://cccfantasy.com').rstrip('/')
    logo_url = f'{site_url}/static/img/logo/ccc-logo-stacked.svg'
    av = _asset_version()
    ko_ladder = [(label, KNOCKOUT_POINTS[key]) for label, key in _KO_LADDER]

    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR, picks_submitted=True)
        .all()
    )
    total_enrolled = len(enrollments)
    sent = skipped_no_email = errors = 0

    for enrollment in enrollments:
        if not enrollment.user or not enrollment.user.email:
            skipped_no_email += 1
            continue
        advanced, eliminated, total_adv = _recap_rows(enrollment)
        rank, _ = _competition_rank(enrollment)
        try:
            html_body = render_template(
                'worldcup/email/wc_group_recap.j2',
                enrollment=enrollment, advanced=advanced, eliminated=eliminated,
                total_adv_str=_fmt_pts(total_adv), total_score_str=_fmt_pts(float(enrollment.total_score)),
                rank=rank, total_enrolled=total_enrolled, ko_ladder=ko_ladder,
                site_url=site_url, logo_url=logo_url, asset_version=av,
                fmt_mult=_fmt_multiplier, fmt_pts=_fmt_pts,
            )
            plain_body = _plain_group_recap(enrollment, advanced, eliminated,
                                            _fmt_pts(total_adv), rank, total_enrolled,
                                            ko_ladder, site_url)
            subject = 'World Cup: the group stage is a wrap'
            if send_platform_email(enrollment.user.email, subject, plain_body, html_body):
                sent += 1
            else:
                errors += 1
        except Exception:
            logger.exception('Group recap failed for enrollment %s', enrollment.id)
            errors += 1

    # Only stamp "last sent" when at least one email actually went out, so a
    # run where every delivery fails (or everyone is skipped) doesn't paint a
    # false "Last sent …" state on the dashboard.
    if sent:
        _mark_group_recap_sent()
    return {'status': 'sent' if sent else 'no_sends',
            'sent': sent, 'skipped_no_email': skipped_no_email, 'errors': errors}


def _plain_group_recap(enrollment, advanced, eliminated, total_adv_str, rank,
                       total_enrolled, ko_ladder, site_url):
    name = enrollment.get_display_name()
    lines = ['The group stage is a wrap', '=' * 40, '', f'Hi {name},', '',
             f'Group advancement points earned: +{total_adv_str}', '',
             'Your teams that advanced:', '-' * 36]
    for r in advanced:
        lines.append(f"  {r['team'].display_name} ({_fmt_multiplier(r['multiplier'])})"
                     f"  {r['method_label']}  +{_fmt_pts(r['points'])} pts")
    if eliminated:
        lines += ['', 'Out after the group stage:']
        for r in eliminated:
            lines.append(f"  {r['team'].display_name}")
    lines += ['', 'How group points worked: Group winner +4, Runner-up +3, Best 3rd +1 '
              '(x your tier multiplier).', '',
              f'Standing entering the Round of 32: #{rank} of {total_enrolled}', '',
              "What's at stake next (x your multiplier):"]
    for label, base in ko_ladder:
        lines.append(f'  {label}: +{base} base')
    lines += ['', 'Your surviving high-multiplier picks carry the biggest upside from here.', '',
              f'Full standings: {site_url}/worldcup/leaderboard', '',
              'Corrupt Commish Club -- cccfantasy.com']
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Picks confirmation receipt
# ---------------------------------------------------------------------------

def _plain_confirmation(
    enrollment: WorldCupEnrollment,
    tier_groups: list[dict],
    deadline_str: str,
    site_url: str,
    is_update: bool,
) -> str:
    """Plain-text fallback for the picks confirmation (mirrors the HTML body)."""
    lines = [
        'Your updated World Cup picks' if is_update else 'Your World Cup picks are in',
        '=' * 40,
        '',
        f'Hi {enrollment.get_display_name()},',
        '',
        'Your roster:',
        '-' * 36,
    ]
    for group in tier_groups:
        lines.append(f'{group["name"]} ({group["multiplier_str"]})')
        for team in group['teams']:
            lines.append(f'  {team.display_name}  (Group {team.group_letter})')
    lines += [
        '',
        f'USA goals tiebreaker: {enrollment.usa_goals_guess}',
        '',
        f'You can edit your picks until {deadline_str}.',
        f'View your picks: {site_url}/worldcup/picks',
        '',
        'Corrupt Commish Club -- cccfantasy.com',
    ]
    return '\n'.join(lines)


def send_picks_confirmation(
    enrollment: WorldCupEnrollment, is_update: bool = False,
) -> bool:
    """Send a roster receipt after a successful picks submission.

    Fires on every save (picks stay editable pre-deadline); ``is_update``
    flips the subject so inbox history reads correctly and no stale email
    masquerades as the entry of record.

    Never raises — a render or SMTP failure must not break the submission
    that triggered it. Returns True only when the send succeeded.
    """
    try:
        if not enrollment.user or not enrollment.user.email:
            logger.warning(
                'Picks confirmation skipped — enrollment %s has no email',
                enrollment.id,
            )
            return False

        # Same ordering as the picks-page roster: tier, then display name.
        picks = (
            WorldCupPick.query
            .join(WorldCupTeam, WorldCupPick.team_id == WorldCupTeam.id)
            .filter(WorldCupPick.enrollment_id == enrollment.id)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        if not picks:
            logger.warning(
                'Picks confirmation skipped — enrollment %s has no picks',
                enrollment.id,
            )
            return False

        tier_groups = []
        for tier_num in sorted(TIERS):
            tier_teams = [p.team for p in picks if p.team.tier == tier_num]
            if not tier_teams:
                continue
            tier_groups.append({
                'tier': tier_num,
                'name': TIERS[tier_num]['name'],
                'multiplier_str': _fmt_multiplier(TIERS[tier_num]['multiplier']),
                'teams': tier_teams,
            })

        deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)
        deadline_str = deadline_ct.strftime('%A, %B %-d at %-I:%M %p CT')

        site_url = current_app.config.get('SITE_URL', 'https://cccfantasy.com').rstrip('/')
        logo_url = f'{site_url}/static/img/logo/ccc-logo-stacked.svg'

        html_body = render_template(
            'worldcup/email/wc_picks_confirmation.j2',
            enrollment=enrollment,
            tier_groups=tier_groups,
            is_update=is_update,
            deadline_str=deadline_str,
            site_url=site_url,
            logo_url=logo_url,
            asset_version=_asset_version(),
        )
        plain_body = _plain_confirmation(
            enrollment, tier_groups, deadline_str, site_url, is_update,
        )
        subject = (
            'Your updated World Cup picks' if is_update
            else 'Your World Cup picks are in'
        )
        return send_platform_email(
            enrollment.user.email, subject, plain_body, html_body,
        )
    except Exception:
        logger.exception(
            'Picks confirmation failed for enrollment %s', enrollment.id,
        )
        return False
