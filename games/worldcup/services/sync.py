"""
World Cup Fantasy Pool — football-data.org Sync Service
=======================================================
Pulls final match results (auto-applied) and group-advancement / knockout-bracket
data (admin-confirmed) from football-data.org (free tier). Match data stays the
single source of truth; this service only feeds the existing scoring engine and
pre-fills the existing admin forms. It never recomputes scores.

Endpoints used (one request each):
    GET /v4/competitions/WC/matches    (all 104 fixtures + scores)
    GET /v4/competitions/WC/standings  (12 group tables)
Auth: header X-Auth-Token. Free tier: 10 req/min, no daily cap.
"""
import logging
import os

import requests
from flask import current_app

from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from games.worldcup.services.scoring import process_match_result
from utils.email import send_platform_email

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.football-data.org/v4'
COMPETITION_CODE = 'WC'

# football-data.org stage string -> our WorldCupMatch.stage code.
STAGE_MAP = {
    'GROUP_STAGE': 'group',
    'LAST_32': 'R32',
    'LAST_16': 'R16',
    'QUARTER_FINALS': 'QF',
    'SEMI_FINALS': 'SF',
    'THIRD_PLACE': 'third_place',
    'FINAL': 'final',
}

# A fixture is final (apply it) only in one of these statuses.
FINISHED_STATUSES = {'FINISHED'}

# football-data.org 3-letter team code (tla) -> our fifa_code, ONLY where they
# differ. Most align (MEX==MEX). Fill in during the `link` verification run.
TEAM_TLA_OVERRIDES: dict[str, str] = {}


class SyncError(Exception):
    """Raised when the football-data.org API is unreachable or misconfigured."""


def _api_get(path: str, params: dict | None = None) -> dict:
    """GET a football-data.org endpoint, returning parsed JSON. Raises SyncError."""
    api_key = current_app.config.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise SyncError('FOOTBALL_DATA_API_KEY is not configured')
    url = f'{API_BASE_URL}/{path}'
    try:
        resp = requests.get(
            url, headers={'X-Auth-Token': api_key}, params=params, timeout=30,
        )
    except Exception as exc:  # network error
        raise SyncError(f'request to {path} failed: {exc}') from exc
    if resp.status_code != 200:
        raise SyncError(f'{path} returned HTTP {resp.status_code}')
    # Defensive rate-limit logging (free tier = 10/min); back off if near zero.
    remaining = resp.headers.get('X-Requests-Available-Minute')
    if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
        logger.warning('football-data.org minute budget nearly exhausted (%s left)', remaining)
    return resp.json()


def _fifa_for_tla(tla: str | None) -> str | None:
    """Map a football-data.org tla to our fifa_code (override map, else identity)."""
    if not tla:
        return None
    return TEAM_TLA_OVERRIDES.get(tla, tla)


def _to_naive_utc(dt):
    """Normalize a datetime to naive-UTC (minute precision) for kickoff comparison."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        from datetime import timezone
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0, second=0)


def _parse_api_kickoff(utc_date: str):
    """'2026-06-11T19:00:00Z' -> naive-UTC datetime (minute precision)."""
    from datetime import datetime
    dt = datetime.fromisoformat(utc_date.replace('Z', '+00:00'))
    return _to_naive_utc(dt)


def link_fixtures() -> dict:
    """Idempotently link our 104 shells + 48 teams to football-data.org ids.

    Verify-then-trust: never guesses silently. Returns a report listing what was
    linked and every fixture/team that could NOT be matched, for manual review.
    Re-runnable (skips rows already linked).
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    api_matches = data.get('matches', [])

    teams_by_fifa = {t.fifa_code: t for t in WorldCupTeam.query.all()}
    our_matches = WorldCupMatch.query.all()

    # Index our group shells by the unordered team-id pair; KO shells by (stage, kickoff).
    group_by_pair: dict[frozenset, WorldCupMatch] = {}
    ko_by_stage_kick: dict[tuple, WorldCupMatch] = {}
    for m in our_matches:
        if m.stage == 'group' and m.home_team_id and m.away_team_id:
            group_by_pair[frozenset((m.home_team_id, m.away_team_id))] = m
        elif m.stage != 'group':
            ko_by_stage_kick[(m.stage, _to_naive_utc(m.kickoff_utc))] = m

    fixtures_linked = 0
    teams_linked = 0
    unmatched_fixtures = []
    unmapped_teams = []

    for f in api_matches:
        our_stage = STAGE_MAP.get(f.get('stage'))
        if our_stage is None:
            unmatched_fixtures.append({'id': f.get('id'), 'reason': f"unknown stage {f.get('stage')}"})
            continue

        # Map teams (group stage has them; KO may be null pre-resolution).
        for side in ('homeTeam', 'awayTeam'):
            api_team = f.get(side) or {}
            fifa = _fifa_for_tla(api_team.get('tla'))
            team = teams_by_fifa.get(fifa) if fifa else None
            if team and api_team.get('id') and team.api_team_id != api_team['id']:
                team.api_team_id = api_team['id']
                teams_linked += 1
            elif api_team.get('tla') and not team:
                unmapped_teams.append({'tla': api_team.get('tla'), 'name': api_team.get('name')})

        # Find our shell.
        shell = None
        if our_stage == 'group':
            home = teams_by_fifa.get(_fifa_for_tla((f.get('homeTeam') or {}).get('tla')))
            away = teams_by_fifa.get(_fifa_for_tla((f.get('awayTeam') or {}).get('tla')))
            if home and away:
                shell = group_by_pair.get(frozenset((home.id, away.id)))
        else:
            shell = ko_by_stage_kick.get((our_stage, _parse_api_kickoff(f['utcDate'])))

        if not shell:
            unmatched_fixtures.append({'id': f.get('id'), 'stage': f.get('stage'),
                                       'utcDate': f.get('utcDate')})
            continue

        if shell.api_fixture_id != f['id']:
            shell.api_fixture_id = f['id']
            fixtures_linked += 1

    db.session.commit()
    return {
        'fixtures_linked': fixtures_linked,
        'teams_linked': teams_linked,
        'unmatched_fixtures': unmatched_fixtures,
        'unmapped_teams': unmapped_teams,
        'api_fixture_count': len(api_matches),
    }


def sync_scores() -> dict:
    """Apply every newly-FINISHED fixture to its linked shell. Idempotent.

    Low-risk tier: runs automatically. Group draws/wins and knockout
    ET/penalties flow through the existing process_match_result(), which
    recalculates all scores. Already-completed shells are skipped.
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    by_fixture = {
        m.api_fixture_id: m
        for m in WorldCupMatch.query.filter(WorldCupMatch.api_fixture_id.isnot(None)).all()
    }

    applied = []
    skipped_unassigned = 0
    for f in data.get('matches', []):
        if f.get('status') not in FINISHED_STATUSES:
            continue
        shell = by_fixture.get(f.get('id'))
        if not shell or shell.is_completed:
            continue

        ft = (f.get('score') or {}).get('fullTime') or {}
        home, away = ft.get('home'), ft.get('away')
        if home is None or away is None:
            continue

        if shell.stage == 'group':
            is_draw = (f['score'].get('winner') == 'DRAW')
            res = process_match_result(shell.id, home, away, None, is_draw=is_draw)
        else:
            # Knockout requires assigned teams (bracket confirmed by admin first).
            if not shell.home_team_id or not shell.away_team_id:
                skipped_unassigned += 1
                continue
            duration = f['score'].get('duration', 'REGULAR')
            winner_side = f['score'].get('winner')
            api_winner = f.get('homeTeam') if winner_side == 'HOME_TEAM' else f.get('awayTeam')
            winner_fifa = _fifa_for_tla((api_winner or {}).get('tla'))
            res = process_match_result(
                shell.id, home, away, winner_fifa,
                extra_time=duration in ('EXTRA_TIME', 'PENALTY_SHOOTOUT'),
                penalties=duration == 'PENALTY_SHOOTOUT',
            )
        if 'error' not in res:
            applied.append({'match_number': shell.match_number, 'result': res.get('result')})

    return {
        'applied_count': len(applied),
        'applied': applied,
        'skipped_unassigned': skipped_unassigned,
    }


def fetch_advancement_proposal() -> dict:
    """Read-only proposal for the admin advancement/bracket forms (no DB writes).

    Reads group standings (positions 1/2 -> winner/runner-up) and the resolved
    LAST_32 matchups (to flag which 3rd-place teams actually advanced as best
    thirds, and to pre-fill knockout shell team assignments). The admin reviews
    and confirms; we do not write any scoring state here.
    """
    standings = _api_get(f'competitions/{COMPETITION_CODE}/standings').get('standings', [])
    matches = _api_get(f'competitions/{COMPETITION_CODE}/matches').get('matches', [])

    # tlas appearing in resolved LAST_32 = teams that advanced (incl. best thirds).
    advancing_tlas = set()
    ko_pairings = []
    for m in matches:
        if STAGE_MAP.get(m.get('stage')) != 'R32':
            continue
        home, away = (m.get('homeTeam') or {}), (m.get('awayTeam') or {})
        if home.get('tla'):
            advancing_tlas.add(home['tla'])
        if away.get('tla'):
            advancing_tlas.add(away['tla'])
        if home.get('tla') and away.get('tla'):
            ko_pairings.append({
                'api_fixture_id': m['id'],
                'home_fifa': _fifa_for_tla(home['tla']),
                'away_fifa': _fifa_for_tla(away['tla']),
            })

    groups = []
    for g in standings:
        if g.get('type') != 'TOTAL':
            continue
        letter = g.get('group', '').replace('Group', '').strip()
        rows = sorted(g.get('table', []), key=lambda r: r['position'])

        def fifa(i):
            return _fifa_for_tla(rows[i]['team']['tla']) if len(rows) > i else None

        third_tla = rows[2]['team']['tla'] if len(rows) > 2 else None
        third_advances = bool(third_tla and third_tla in advancing_tlas)
        groups.append({
            'letter': letter,
            'group_winner': fifa(0),
            'runner_up': fifa(1),
            'best_third': fifa(2) if third_advances else None,
            'third_advances': third_advances,
            'table': [
                {'position': r['position'], 'fifa': _fifa_for_tla(r['team']['tla']),
                 'name': r['team'].get('name'), 'points': r.get('points'),
                 'gd': r.get('goalDifference'), 'gf': r.get('goalsFor')}
                for r in rows
            ],
        })

    return {'groups': sorted(groups, key=lambda x: x['letter']), 'ko_pairings': ko_pairings}


def group_stage_complete_and_unconfirmed() -> bool:
    """True when all group matches are done but ≥1 group's advancement is unset."""
    total = WorldCupMatch.query.filter_by(stage='group').count()
    done = WorldCupMatch.query.filter_by(stage='group', is_completed=True).count()
    if total == 0 or done < total:
        return False
    unconfirmed = (
        WorldCupTeam.query
        .filter(WorldCupTeam.advancement_method.is_(None))
        .filter(WorldCupTeam.is_eliminated.isnot(True))
        .count()
    )
    return unconfirmed > 0


def ko_round_complete_and_next_empty() -> bool:
    """True when a knockout round is fully played but the next round's shells are empty."""
    order = ['R32', 'R16', 'QF', 'SF']
    nxt = {'R32': 'R16', 'R16': 'QF', 'QF': 'SF', 'SF': 'final'}
    for stage in order:
        total = WorldCupMatch.query.filter_by(stage=stage).count()
        if total == 0:
            continue
        done = WorldCupMatch.query.filter_by(stage=stage, is_completed=True).count()
        if done < total:
            continue
        next_stage = nxt[stage]
        empty = (
            WorldCupMatch.query
            .filter_by(stage=next_stage)
            .filter((WorldCupMatch.home_team_id.is_(None)) | (WorldCupMatch.away_team_id.is_(None)))
            .count()
        )
        if empty > 0:
            return True
    return False


def _send_admin_email(subject: str, body: str) -> bool:
    """Send a plain-text admin notification to the platform email address."""
    to_addr = current_app.config.get('EMAIL_ADDRESS', '')
    if not to_addr:
        logger.warning('EMAIL_ADDRESS not configured; skipping admin email.')
        return False
    return send_platform_email(to_addr, f'[World Cup] {subject}', body)


def _notify_once(signature: str) -> bool:
    """Return True the first time we see `signature`; suppress repeats.

    Schema-free de-dup via a marker file in the instance dir. A new pending-state
    signature (e.g. group stage done, then a KO round done) re-arms the notice.
    """
    marker = os.path.join(current_app.instance_path, '.wc_sync_notify')
    try:
        with open(marker) as fh:
            last = fh.read().strip()
    except OSError:
        last = ''
    if last == signature:
        return False
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(marker, 'w') as fh:
        fh.write(signature)
    return True


def run_scores() -> dict:
    """Timer entry point (every 30 min): apply finals; email only on error."""
    try:
        result = sync_scores()
    except SyncError as exc:
        _send_admin_email('Score sync failed', f'football-data.org sync error:\n{exc}')
        return {'status': 'error', 'details': str(exc)}
    if result['applied_count']:
        logger.info('worldcup sync applied %s result(s)', result['applied_count'])
    return {'status': 'ok', **result}


def run_advancement_check() -> dict:
    """Timer entry point (hourly): notify (once per episode) when admin action is due."""
    group_due = group_stage_complete_and_unconfirmed()
    ko_due = ko_round_complete_and_next_empty()
    if not (group_due or ko_due):
        return {'status': 'idle'}
    signature = f'group={group_due};ko={ko_due}'
    if not _notify_once(signature):
        return {'status': 'already_notified'}
    lines = []
    if group_due:
        lines.append('Group stage is complete — confirm advancement at '
                     '/worldcup/admin/advancement (use "Load from API").')
    if ko_due:
        lines.append('A knockout round is complete — set the next round\'s teams at '
                     'the admin bracket pages (use "Load from API").')
    _send_admin_email('Advancement ready to confirm', '\n'.join(lines))
    return {'status': 'notified', 'group_due': group_due, 'ko_due': ko_due}


def run_digest() -> dict:
    """Daily entry point: email a summary of matches finalized today (CT)."""
    from datetime import timezone
    from games.worldcup.services.state import now_utc
    from games.worldcup.constants import WORLDCUP_TZ
    today = now_utc().astimezone(WORLDCUP_TZ).date()

    completed = WorldCupMatch.query.filter_by(is_completed=True).all()
    todays = [
        m for m in completed
        if m.updated_at and m.updated_at.replace(tzinfo=timezone.utc).astimezone(WORLDCUP_TZ).date() == today
    ]
    if not todays:
        return {'status': 'no_results'}
    lines = [f"Results finalized {today:%b %d}:"]
    for m in sorted(todays, key=lambda x: x.match_number):
        hn = m.home_team.display_name if m.home_team else '?'
        an = m.away_team.display_name if m.away_team else '?'
        lines.append(f'  #{m.match_number} [{m.stage}] {hn} {m.home_score}-{m.away_score} {an}')
    _send_admin_email('Daily results digest', '\n'.join(lines))
    return {'status': 'sent', 'count': len(todays)}
