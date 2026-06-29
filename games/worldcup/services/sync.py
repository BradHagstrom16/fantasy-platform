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
import random
import time

import requests
from flask import current_app

from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from games.worldcup.services.scoring import process_match_result
from utils.email import send_platform_email

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.football-data.org/v4'
COMPETITION_CODE = 'WC'

# Transient-failure resilience for the once-per-30-min timer (mirrors the Golf
# sync's _make_request, games/golf/services/sync.py). A single network blip on
# the droplet (DNS hiccup / ephemeral-port "address unavailable") or a 5xx
# should be absorbed by retry rather than skipping the run and emailing an
# alert — the failure self-heals within seconds. Only a *sustained* outage
# (all attempts exhausted) raises SyncError. 4 attempts with capped exponential
# backoff worst-cases well under the unit's TimeoutStartSec=5m.
API_MAX_RETRIES = 4
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

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
# differ. Most align (MEX==MEX). Verified against the live WC 2026 feed on
# 2026-06-02 (flask worldcup sync --mode link): only Uruguay diverges
# (football-data.org 'URY' vs our FIFA 'URU').
TEAM_TLA_OVERRIDES: dict[str, str] = {
    'URY': 'URU',  # Uruguay
}


class SyncError(Exception):
    """Raised when the football-data.org API is unreachable or misconfigured."""


def _api_get(path: str, params: dict | None = None,
             retries: int = API_MAX_RETRIES) -> dict:
    """GET a football-data.org endpoint, returning parsed JSON.

    Retries transient failures (network errors, 429, 5xx) with capped
    exponential backoff + jitter so a momentary blip on the droplet doesn't
    skip the run and alarm the admin. A permanent client error (4xx other than
    429, e.g. a bad key → 403) fails fast. Raises SyncError only when retries
    are exhausted or the error is non-retryable.
    """
    api_key = current_app.config.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise SyncError('FOOTBALL_DATA_API_KEY is not configured')
    url = f'{API_BASE_URL}/{path}'
    backoff = 1.5
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, headers={'X-Auth-Token': api_key}, params=params, timeout=30,
            )
        except requests.RequestException as exc:  # transient network error: retry
            last_error = f'request to {path} failed: {exc}'
            logger.warning('football-data.org %s network error (attempt %s/%s): %s',
                           path, attempt, retries, exc)
        else:
            if resp.status_code == 200:
                # Defensive rate-limit logging (free tier = 10/min); back off if near zero.
                remaining = resp.headers.get('X-Requests-Available-Minute')
                if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                    logger.warning('football-data.org minute budget nearly exhausted (%s left)', remaining)
                return resp.json()
            if resp.status_code not in _RETRYABLE_STATUS:
                # Permanent client error — retrying won't help; surface immediately.
                raise SyncError(f'{path} returned HTTP {resp.status_code}')
            last_error = f'{path} returned HTTP {resp.status_code}'
            logger.warning('football-data.org %s returned HTTP %s (attempt %s/%s)',
                           path, resp.status_code, attempt, retries)
        if attempt < retries:
            sleep_for = min(60, backoff * (2 ** (attempt - 1)))
            sleep_for *= (1 + random.uniform(-0.25, 0.25))
            time.sleep(max(0.5, sleep_for))
    raise SyncError(last_error or f'request to {path} failed after {retries} attempts')


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
    team_conflicts = []
    fixture_conflicts = []

    for f in api_matches:
        our_stage = STAGE_MAP.get(f.get('stage'))
        if our_stage is None:
            unmatched_fixtures.append({'id': f.get('id'), 'reason': f"unknown stage {f.get('stage')}"})
            continue

        # Map teams (group stage has them; KO may be null pre-resolution).
        # Fill only an empty column; a non-null id that differs is a conflict to
        # review, never a silent overwrite.
        for side in ('homeTeam', 'awayTeam'):
            api_team = f.get(side) or {}
            fifa = _fifa_for_tla(api_team.get('tla'))
            team = teams_by_fifa.get(fifa) if fifa else None
            if team and api_team.get('id'):
                if team.api_team_id is None:
                    team.api_team_id = api_team['id']
                    teams_linked += 1
                elif team.api_team_id != api_team['id']:
                    team_conflicts.append({'fifa': team.fifa_code,
                                           'stored': team.api_team_id,
                                           'incoming': api_team['id']})
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

        if shell.api_fixture_id is None:
            shell.api_fixture_id = f['id']
            fixtures_linked += 1
        elif shell.api_fixture_id != f['id']:
            fixture_conflicts.append({'match_number': shell.match_number,
                                      'stored': shell.api_fixture_id,
                                      'incoming': f['id']})

    db.session.commit()
    return {
        'fixtures_linked': fixtures_linked,
        'teams_linked': teams_linked,
        'unmatched_fixtures': unmatched_fixtures,
        'unmapped_teams': unmapped_teams,
        'team_conflicts': team_conflicts,
        'fixture_conflicts': fixture_conflicts,
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
    failed = []
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
        if 'error' in res:
            failed.append({'match_number': shell.match_number, 'match_id': shell.id,
                           'error': res['error']})
        else:
            applied.append({'match_number': shell.match_number, 'result': res.get('result')})

    return {
        'applied_count': len(applied),
        'applied': applied,
        'skipped_unassigned': skipped_unassigned,
        'failed': failed,
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


KO_STAGES = ('R32', 'R16', 'QF', 'SF', 'final', 'third_place')


def fetch_bracket_proposal(target_stage: str) -> dict:
    """Read-only proposed team assignments for every shell of target_stage.

    Reads the /matches feed, filters to target_stage, maps each API fixture to
    our shell (by api_fixture_id, else by (stage, kickoff)), and proposes
    home/away from the API's resolved teams. Never writes. Shells the API has
    not yet resolved (or that no fixture matched) are reported in 'unresolved'
    for admin review, never guessed.
    """
    if target_stage not in KO_STAGES:
        return {'target_stage': target_stage, 'proposals': [], 'unresolved': [],
                'error': f'Not a knockout stage: {target_stage}'}

    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    shells = WorldCupMatch.query.filter_by(stage=target_stage).all()
    by_fixture = {m.api_fixture_id: m for m in shells if m.api_fixture_id}
    by_kick = {_to_naive_utc(m.kickoff_utc): m for m in shells if m.kickoff_utc}

    proposals = []
    unresolved = []
    sides_by_shell = {}  # shell_id -> {'home': fifa|None, 'away': fifa|None}
    matched_ids = set()
    for f in data.get('matches', []):
        if STAGE_MAP.get(f.get('stage')) != target_stage:
            continue
        shell = by_fixture.get(f.get('id'))
        if shell is None and f.get('utcDate'):
            shell = by_kick.get(_parse_api_kickoff(f['utcDate']))
        if not shell:
            continue
        matched_ids.add(shell.id)
        home = _fifa_for_tla((f.get('homeTeam') or {}).get('tla'))
        away = _fifa_for_tla((f.get('awayTeam') or {}).get('tla'))
        # Record each side independently — a side the API hasn't resolved is None.
        # The per-side bracket auto-fill cross-checks against this map.
        sides_by_shell[shell.id] = {'home': home or None, 'away': away or None}
        if not home or not away:
            unresolved.append({'match_number': shell.match_number,
                               'reason': 'API has not resolved both teams yet'})
            continue
        teams = {t.fifa_code: t for t in WorldCupTeam.query.filter(
            WorldCupTeam.fifa_code.in_([home, away])).all()}
        proposals.append({
            'match_number': shell.match_number,
            'shell_id': shell.id,
            'home_fifa': home,
            'away_fifa': away,
            'home_name': teams[home].display_name if home in teams else home,
            'away_name': teams[away].display_name if away in teams else away,
            'current_home': shell.home_team.fifa_code if shell.home_team else None,
            'current_away': shell.away_team.fifa_code if shell.away_team else None,
            'already_set': bool(shell.home_team_id and shell.away_team_id),
            'is_completed': bool(shell.is_completed),
        })

    for shell in shells:
        if shell.id not in matched_ids:
            unresolved.append({'match_number': shell.match_number,
                               'reason': 'no API fixture matched this shell'})

    return {
        'target_stage': target_stage,
        'proposals': sorted(proposals, key=lambda p: p['match_number']),
        'unresolved': sorted(unresolved, key=lambda u: u['match_number']),
        'sides': sides_by_shell,
        'error': None,
    }


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


def all_group_advancement_confirmed() -> bool:
    """True when group stage is complete AND every group's advancement is set."""
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
    return unconfirmed == 0


def populatable_bracket_stages() -> list[str]:
    """KO stages whose shells are empty and whose feeder round is resolved."""
    def has_empty(stage: str) -> bool:
        return (
            WorldCupMatch.query.filter_by(stage=stage)
            .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                           WorldCupMatch.away_team_id.is_(None)))
            .count() > 0
        )

    stages: list[str] = []
    if all_group_advancement_confirmed() and has_empty('R32'):
        stages.append('R32')

    src = ko_round_pending()  # source stage complete, downstream empty
    if src:
        downstream = (['final', 'third_place'] if src == 'SF'
                      else [{'R32': 'R16', 'R16': 'QF', 'QF': 'SF'}[src]])
        for ds in downstream:
            if has_empty(ds) and ds not in stages:
                stages.append(ds)
    return stages


def ko_round_pending() -> str | None:
    """Return the completed knockout round whose downstream shells are still empty.

    Returns the source-stage code (e.g. 'R32', 'SF') of a round that is fully
    played but whose next round isn't populated yet, else None. SF is special:
    its losers play the third-place match, so BOTH 'final' and 'third_place'
    must be filled before SF counts as resolved.
    """
    order = ['R32', 'R16', 'QF', 'SF']
    nxt = {'R32': 'R16', 'R16': 'QF', 'QF': 'SF'}
    for stage in order:
        total = WorldCupMatch.query.filter_by(stage=stage).count()
        if total == 0:
            continue
        done = WorldCupMatch.query.filter_by(stage=stage, is_completed=True).count()
        if done < total:
            continue
        downstream = ['final', 'third_place'] if stage == 'SF' else [nxt[stage]]
        for ds in downstream:
            empty = (
                WorldCupMatch.query
                .filter_by(stage=ds)
                .filter((WorldCupMatch.home_team_id.is_(None)) | (WorldCupMatch.away_team_id.is_(None)))
                .count()
            )
            if empty > 0:
                return stage
    return None


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
    """Timer entry point (every 30 min): apply finals + auto-fill downstream
    KO shells; email only on error / on bracket events."""
    try:
        result = sync_scores()
    except SyncError as exc:
        _send_admin_email('Score sync failed', f'football-data.org sync error:\n{exc}')
        return {'status': 'error', 'details': str(exc)}

    # Auto-fill any downstream KO round whose feeder round just completed.
    # Local import avoids a circular import (bracket imports from sync).
    from games.worldcup.services.bracket import run_bracket_autofill
    try:
        bracket_summary = run_bracket_autofill()
    except SyncError as exc:
        # API outage during the bracket pass is non-fatal to score sync.
        logger.warning('bracket auto-fill skipped (API error): %s', exc)
        bracket_summary = {'status': 'error', 'details': str(exc)}

    if result['applied_count']:
        logger.info('worldcup sync applied %s result(s)', result['applied_count'])
    if result['failed']:
        body = '\n'.join(f"#{f['match_number']}: {f['error']}" for f in result['failed'])
        _send_admin_email('Score sync: some results failed to apply', body)
        return {'status': 'error', 'bracket': bracket_summary, **result}
    return {'status': 'ok', 'bracket': bracket_summary, **result}


def run_advancement_check() -> dict:
    """Timer entry point (hourly): notify (once per episode) when admin action is due."""
    group_due = group_stage_complete_and_unconfirmed()
    ko_stage = ko_round_pending()
    if not (group_due or ko_stage):
        return {'status': 'idle'}
    # Signature uniquely identifies this pending episode so each distinct round
    # (group, R32, R16, …) gets its own one-time notification rather than being
    # collapsed into a single 'knockout pending' state.
    parts = []
    if group_due:
        parts.append('group')
    if ko_stage:
        parts.append(f'ko:{ko_stage}')
    signature = ';'.join(parts)
    if not _notify_once(signature):
        return {'status': 'already_notified'}
    lines = []
    if group_due:
        lines.append('Group stage is complete — confirm advancement at '
                     '/worldcup/admin/advancement (use "Load from API").')
    if ko_stage:
        lines.append(f'The {ko_stage} round is complete — set the next round\'s teams at '
                     'the admin bracket pages (use "Load from API").')
    _send_admin_email('Advancement ready to confirm', '\n'.join(lines))
    return {'status': 'notified', 'group_due': group_due, 'ko_stage': ko_stage}


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
