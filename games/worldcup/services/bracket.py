"""Auto-fill deterministic downstream knockout shells (R16 -> Final).

Hybrid: derive each pairing from a fixed bracket topology + our own completed
results (primary), cross-check against the football-data.org proposal, and write
via the existing set_knockout_teams only when they agree (or when the API is
unavailable, flagged). R32 / group advancement are out of scope (admin-confirmed).
"""
import logging

from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from games.worldcup.services.scoring import set_knockout_teams
from games.worldcup.services.sync import (
    fetch_bracket_proposal, populatable_bracket_stages,
    _send_admin_email, _notify_once, SyncError, _fifa_for_tla, _api_get,
    COMPETITION_CODE,
)

logger = logging.getLogger(__name__)

DOWNSTREAM_STAGES = ('R16', 'QF', 'SF', 'final', 'third_place')

# Downstream match_number -> (home_feeder, away_feeder); feeder = (kind, match_no).
# Official FIFA 2026 bracket (fixed, no redraws). R16/QF/SF transcribed from the
# Wikipedia knockout-stage bracket template + corroborated by news bracket sources;
# it is a genuine cross-bracket, NOT a sequential pairing. Confirm once the real
# rounds resolve with: `infer_topology_from_api()` (see docs plan Task 7 Step 2).
BRACKET_TOPOLOGY: dict[int, tuple[tuple[str, int], tuple[str, int]]] = {
    89: (('winner', 74), ('winner', 77)),
    90: (('winner', 73), ('winner', 75)),
    91: (('winner', 76), ('winner', 78)),
    92: (('winner', 79), ('winner', 80)),
    93: (('winner', 83), ('winner', 84)),
    94: (('winner', 81), ('winner', 82)),
    95: (('winner', 86), ('winner', 88)),
    96: (('winner', 85), ('winner', 87)),
    97: (('winner', 89), ('winner', 90)),
    98: (('winner', 93), ('winner', 94)),
    99: (('winner', 91), ('winner', 92)),
    100: (('winner', 95), ('winner', 96)),
    101: (('winner', 97), ('winner', 98)),
    102: (('winner', 99), ('winner', 100)),
    103: (('loser', 101), ('loser', 102)),
    104: (('winner', 101), ('winner', 102)),
}


def infer_topology_from_api() -> dict:
    """Generate the topology dict from a FULLY-RESOLVED API bracket (verify aid).

    For each downstream KO fixture with both teams resolved, find which earlier
    match's winner (or loser) each team is, and emit the feeder pair. Returns
    {match_number: ((kind, feeder_no), (kind, feeder_no))}. Read-only; used to
    confirm BRACKET_TOPOLOGY matches reality — never called at runtime.
    """
    data = _api_get(f'competitions/{COMPETITION_CODE}/matches')
    by_num = {}  # our match_number -> (winner_fifa, loser_fifa) for completed KO
    api_by_num = {}  # our match_number -> (home_fifa, away_fifa) resolved
    # Map API fixtures to our shells by api_fixture_id.
    shells = {m.api_fixture_id: m for m in WorldCupMatch.query.all() if m.api_fixture_id}
    for f in data.get('matches', []):
        shell = shells.get(f.get('id'))
        if not shell:
            continue
        home = _fifa_for_tla((f.get('homeTeam') or {}).get('tla'))
        away = _fifa_for_tla((f.get('awayTeam') or {}).get('tla'))
        if home and away:
            api_by_num[shell.match_number] = (home, away)
        winner_side = (f.get('score') or {}).get('winner')
        if winner_side in ('HOME_TEAM', 'AWAY_TEAM') and home and away:
            w, l = (home, away) if winner_side == 'HOME_TEAM' else (away, home)
            by_num[shell.match_number] = (w, l)

    winner_of = {fifa: n for n, (fifa, _) in by_num.items()}
    loser_of = {fifa: n for n, (_, fifa) in by_num.items()}
    topo = {}
    for num, (home, away) in api_by_num.items():
        if num < 89:
            continue

        def feeder(fifa):
            if fifa in winner_of:
                return ('winner', winner_of[fifa])
            if fifa in loser_of:
                return ('loser', loser_of[fifa])
            return None

        fh, fa = feeder(home), feeder(away)
        if fh and fa:
            topo[num] = (fh, fa)
    return dict(sorted(topo.items()))


def _winner_fifa(match_number: int) -> str | None:
    m = WorldCupMatch.query.filter_by(match_number=match_number).first()
    if not m or not m.is_completed or not m.winner_team_id:
        return None
    w = db.session.get(WorldCupTeam, m.winner_team_id)
    return w.fifa_code if w else None


def _loser_fifa(match_number: int) -> str | None:
    m = WorldCupMatch.query.filter_by(match_number=match_number).first()
    if not m or not m.is_completed or not m.winner_team_id:
        return None
    loser_id = m.home_team_id if m.winner_team_id == m.away_team_id else m.away_team_id
    l = db.session.get(WorldCupTeam, loser_id) if loser_id else None
    return l.fifa_code if l else None


def _resolve_feeder(kind: str, feeder_no: int) -> str | None:
    return _winner_fifa(feeder_no) if kind == 'winner' else _loser_fifa(feeder_no)


def derive_pairings(stage: str) -> dict | None:
    """{shell_id: (home_fifa, away_fifa)} for every EMPTY shell of `stage`.

    Returns None if the stage is not fully ready: any feeder match is not yet
    completed / has no winner, or a derived team cannot be resolved. Empty dict
    means the stage has no empty shells (already filled).
    """
    empty_shells = (
        WorldCupMatch.query.filter_by(stage=stage)
        .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                       WorldCupMatch.away_team_id.is_(None)))
        .all()
    )
    out: dict = {}
    for shell in empty_shells:
        feeders = BRACKET_TOPOLOGY.get(shell.match_number)
        if not feeders:
            logger.warning('No topology entry for shell #%s', shell.match_number)
            return None
        (hk, hn), (ak, an) = feeders
        home = _resolve_feeder(hk, hn)
        away = _resolve_feeder(ak, an)
        if not home or not away or home == away:
            return None  # stage not ready (feeder unplayed or unresolved)
        out[shell.id] = (home, away)
    return out


def reconcile(stage: str) -> dict:
    """Combine self-derived pairings (B) with the API proposal (A)."""
    pairings = derive_pairings(stage)
    if not pairings:  # None (not ready) or {} (nothing empty)
        return {'stage': stage, 'decision': 'NOT_READY'}

    try:
        proposal = fetch_bracket_proposal(stage)
    except SyncError:
        return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}

    if proposal.get('error'):
        return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}

    api_by_shell = {
        p['shell_id']: frozenset({p.get('home_fifa'), p.get('away_fifa')})
        for p in proposal.get('proposals', [])
        if p.get('home_fifa') and p.get('away_fifa')
    }

    conflicts = []
    for shell_id, (home, away) in pairings.items():
        api_pair = api_by_shell.get(shell_id)
        if api_pair is None:
            # API hasn't resolved this shell we can derive -> unavailable, not wrong.
            return {'stage': stage, 'decision': 'APPLY_UNCONFIRMED', 'pairings': pairings}
        if api_pair != frozenset({home, away}):
            conflicts.append({'shell_id': shell_id, 'ours': [home, away],
                              'api': sorted(api_pair)})

    if conflicts:
        return {'stage': stage, 'decision': 'CONFLICT', 'conflicts': conflicts}
    return {'stage': stage, 'decision': 'APPLY', 'pairings': pairings}


def _shell_label(shell_id: int, home: str, away: str) -> str:
    m = db.session.get(WorldCupMatch, shell_id)
    num = m.match_number if m else '?'
    return f'#{num}: {home} vs {away}'


def run_bracket_autofill() -> dict:
    """Fill empty downstream KO shells whose feeder round is resolved.

    Folded into run_scores() (30-min timer). Writes only on APPLY /
    APPLY_UNCONFIRMED; CONFLICT writes nothing and emails once (de-duped).
    R32 is excluded — the group->R32 transition stays admin-confirmed.
    """
    stages = [s for s in populatable_bracket_stages() if s in DOWNSTREAM_STAGES]
    if not stages:
        return {'status': 'idle', 'stages': []}

    acted = []
    for stage in stages:
        d = reconcile(stage)
        decision = d['decision']
        if decision == 'NOT_READY':
            continue

        if decision == 'CONFLICT':
            if _notify_once(f'bracket-conflict:{stage}'):
                lines = [f"  {c['ours']} (ours) vs {sorted(c['api'])} (API)"
                         for c in d['conflicts']]
                _send_admin_email(
                    f'Bracket auto-fill BLOCKED ({stage}): API disagrees',
                    'Our results and the API disagree on these shells — '
                    'no teams written. Confirm manually at '
                    f'/worldcup/admin/bracket/{stage}.\n' + '\n'.join(lines))
            acted.append({'stage': stage, 'decision': decision, 'filled': []})
            continue

        # APPLY or APPLY_UNCONFIRMED -> write empty shells.
        filled = []
        for shell_id, (home, away) in d['pairings'].items():
            res = set_knockout_teams(shell_id, home, away)
            if 'error' in res:
                logger.warning('autofill write failed shell=%s: %s', shell_id, res['error'])
            else:
                filled.append(_shell_label(shell_id, home, away))
        if filled:
            unconfirmed = decision == 'APPLY_UNCONFIRMED'
            subject = (f'Bracket auto-filled ({stage})'
                       + (' — NO API confirmation, please spot-check' if unconfirmed else ''))
            note = ('\n\nThe API was unavailable, so this was written from our own '
                    'results without a second-opinion cross-check.' if unconfirmed else '')
            _send_admin_email(subject,
                              f'Auto-filled {stage} shells:\n  ' + '\n  '.join(filled) + note)
        acted.append({'stage': stage, 'decision': decision, 'filled': filled})

    return {'status': 'acted' if acted else 'idle', 'stages': acted}
