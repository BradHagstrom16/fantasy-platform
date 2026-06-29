"""Auto-fill deterministic downstream knockout shells (R16 -> Final).

Hybrid: derive each pairing from a fixed bracket topology + our own completed
results (primary), cross-check against the football-data.org proposal, and write
via the existing set_knockout_teams only when they agree (or when the API is
unavailable, flagged). R32 / group advancement are out of scope (admin-confirmed).
"""
import logging

from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from games.worldcup.services.scoring import set_knockout_team_side
from games.worldcup.services.sync import (
    fetch_bracket_proposal,
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

    def feeder(fifa: str, prior: dict) -> tuple[str, int] | None:
        # A team's feeder is its MOST RECENT prior appearance — win OR loss.
        # Checking wins first would mis-map a semifinal loser (who also won
        # earlier rounds) to a QF win instead of the SF loss that feeds the
        # third-place shell. Most-recent (max match number < num) is correct
        # for both winner feeders and the loser feeders of third place.
        appearances: list[tuple[str, int]] = []
        for match_no, (winner_fifa, loser_fifa) in prior.items():
            if winner_fifa == fifa:
                appearances.append(('winner', match_no))
            elif loser_fifa == fifa:
                appearances.append(('loser', match_no))
        return max(appearances, key=lambda item: item[1], default=None)

    topo = {}
    for num, (home, away) in api_by_num.items():
        if num < 89:
            continue
        prior = {n: pair for n, pair in by_num.items() if n < num}
        fh, fa = feeder(home, prior), feeder(away, prior)
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


def derive_sides(stage: str) -> dict:
    """{shell_id: {'home': fifa, 'away': fifa}} for the EMPTY sides of `stage`
    whose feeder match is complete — fill each side the moment its feeder resolves.

    A side already set (manual override or a prior pass) is omitted (never
    overwritten); a feeder not yet completed is omitted (the side stays TBD). No
    whole-stage gating: a shell with one resolved feeder yields just that side.
    Returns {} when nothing is fillable.
    """
    out: dict = {}
    for shell in WorldCupMatch.query.filter_by(stage=stage).all():
        feeders = BRACKET_TOPOLOGY.get(shell.match_number)
        if not feeders:
            logger.warning('No topology entry for shell #%s', shell.match_number)
            continue
        (hk, hn), (ak, an) = feeders
        sides: dict = {}
        if shell.home_team_id is None:
            home = _resolve_feeder(hk, hn)
            if home:
                sides['home'] = home
        if shell.away_team_id is None:
            away = _resolve_feeder(ak, an)
            if away:
                sides['away'] = away
        if not sides:
            continue
        # Topology-bug guard: never place a team that already sits on the other
        # side, and never derive the same team for both sides of one shell.
        occupied = {
            t.fifa_code for t in (
                db.session.get(WorldCupTeam, shell.home_team_id) if shell.home_team_id else None,
                db.session.get(WorldCupTeam, shell.away_team_id) if shell.away_team_id else None,
            ) if t
        }
        if sides.get('home') and sides.get('home') == sides.get('away'):
            logger.warning('topology bug: same team both sides of shell #%s', shell.match_number)
            continue
        for side in ('home', 'away'):
            if sides.get(side) in occupied:
                logger.warning('topology bug: %s already on shell #%s; skipping %s',
                               sides[side], shell.match_number, side)
                sides.pop(side)
        if sides:
            out[shell.id] = sides
    return out


def reconcile(stage: str) -> dict:
    """Cross-check each self-derived side (B) against the API's resolved side (A).

    Returns {'stage', 'applies': [(shell_id, side, fifa, confirmed)], 'conflicts':
    [(shell_id, side, ours, api_pair)]}. The cross-check is by MEMBERSHIP, not
    orientation: a derived team is confirmed if the API has it on either side of
    that fixture; it conflicts only when the API has FULLY resolved the fixture to
    a pairing that excludes our team; otherwise it's an unconfirmed apply (write
    from our results, flagged).
    """
    derived = derive_sides(stage)
    if not derived:
        return {'stage': stage, 'applies': [], 'conflicts': []}

    try:
        proposal = fetch_bracket_proposal(stage)
        api_sides = None if proposal.get('error') else (proposal.get('sides') or {})
    except SyncError:
        api_sides = None  # API unreachable -> everything unconfirmed (never wrong)

    applies = []
    conflicts = []
    for shell_id, sides in derived.items():
        if api_sides is None:
            api_for_shell = None
        else:
            api_for_shell = api_sides.get(shell_id, {})
        known = {v for v in (api_for_shell or {}).values() if v}
        api_complete = bool(api_for_shell) and len(known) == 2
        for side, fifa in sides.items():
            if fifa in known:
                applies.append((shell_id, side, fifa, True))      # API confirms membership
            elif api_complete:
                conflicts.append((shell_id, side, fifa, sorted(known)))  # API pairing excludes us
            else:
                applies.append((shell_id, side, fifa, False))     # API can't confirm yet
    return {'stage': stage, 'applies': applies, 'conflicts': conflicts}


def _side_label(shell_id: int, side: str, fifa: str) -> str:
    m = db.session.get(WorldCupMatch, shell_id)
    num = m.match_number if m else '?'
    return f'#{num} {side}: {fifa}'


def run_bracket_autofill() -> dict:
    """Fill empty downstream KO shell SIDES whose feeder match has completed.

    Folded into run_scores() (30-min timer). Writes each confirmed/unconfirmed
    side via set_knockout_team_side (empty-side-only); a side the API resolves
    differently is BLOCKED and emailed once (de-duped). Confirmed fills are silent
    (logged + surfaced by the daily digest); only action-needed events email.

    Self-gated per-side via derive_sides — a stage is processed the moment any one
    of its shells has a resolved feeder, NOT only once the whole feeder round is
    complete (the gate populatable_bracket_stages still applies to the admin
    bulk-populate UI). R32 is excluded — the group->R32 transition stays
    admin-confirmed.
    """
    stages = [s for s in DOWNSTREAM_STAGES if derive_sides(s)]
    if not stages:
        return {'status': 'idle', 'stages': []}

    acted = []
    # Accumulate notifications across ALL stages, then send one batched email per
    # category. _notify_once' marker holds a single signature, so a per-stage call
    # would let one stage's signature overwrite another's (final + third_place both
    # conflicting -> re-sent every run). One signature per category, on its own
    # marker file, is the de-dup that actually holds.
    all_conflicts = []    # (stage, shell_id, side, fifa, api_pair)
    all_failed = []       # (stage, shell_id, side, error)
    all_unconfirmed = []  # (stage, label)
    for stage in stages:
        d = reconcile(stage)
        applies, conflicts = d['applies'], d['conflicts']
        if not applies and not conflicts:
            continue

        filled, failed, unconfirmed = [], [], []
        for shell_id, side, fifa, confirmed in applies:
            res = set_knockout_team_side(shell_id, side, fifa)
            if 'error' in res:
                logger.warning('autofill write failed shell=%s %s: %s',
                               shell_id, side, res['error'])
                failed.append({'shell_id': shell_id, 'side': side, 'error': res['error']})
            elif res.get('skipped'):
                continue  # already set (idempotent no-op)
            else:
                label = _side_label(shell_id, side, fifa)
                filled.append(label)
                if not confirmed:
                    unconfirmed.append(label)

        all_conflicts += [(stage, s, side, fifa, api) for s, side, fifa, api in conflicts]
        all_failed += [(stage, f['shell_id'], f['side'], f['error']) for f in failed]
        all_unconfirmed += [(stage, lbl) for lbl in unconfirmed]
        acted.append({'stage': stage, 'filled': filled, 'unconfirmed': len(unconfirmed),
                      'conflicts': [_side_label(s, side, fifa) for s, side, fifa, _ in conflicts],
                      'failed': failed})

    if all_conflicts:
        # Signature carries fifa + api so a CHANGED conflict re-arms the notice.
        sig = 'bracket-conflict:' + '|'.join(sorted(
            f'{st}:{s}:{side}:{fifa}:{",".join(api)}'
            for st, s, side, fifa, api in all_conflicts))
        if _notify_once(sig, '.wc_bracket_conflict_notify'):
            lines = [f"  {st} #{db.session.get(WorldCupMatch, s).match_number} {side}: "
                     f"{fifa} (ours) — API pairing {api}"
                     for st, s, side, fifa, api in all_conflicts]
            urls = ', '.join(f'/worldcup/admin/bracket/{st}'
                             for st in sorted({st for st, *_ in all_conflicts}))
            _send_admin_email(
                'Bracket auto-fill BLOCKED: API disagrees',
                'Our results and the API disagree on these sides — nothing written '
                f'for them. Confirm manually at: {urls}\n'
                + '\n'.join(lines))

    if all_failed:
        # A persistent write failure would leave the side empty with no alert —
        # the silent-stall mode this feature exists to remove (always loud).
        urls = ', '.join(f'/worldcup/admin/bracket/{st}'
                         for st in sorted({st for st, *_ in all_failed}))
        _send_admin_email(
            'Bracket auto-fill write FAILED',
            'These sides could not be written — confirm manually at '
            f'{urls}:\n'
            + '\n'.join(f"  {st} shell {s} {side}: {err}"
                        for st, s, side, err in all_failed))

    if all_unconfirmed:
        sig = 'bracket-unconfirmed:' + '|'.join(sorted(
            f'{st}:{lbl}' for st, lbl in all_unconfirmed))
        if _notify_once(sig, '.wc_bracket_unconfirmed_notify'):
            _send_admin_email(
                'Bracket auto-filled — NO API confirmation, please spot-check',
                'These sides were written from our own results without an API '
                'second-opinion (the API had not resolved them yet):\n'
                + '\n'.join(f"  {st} {lbl}" for st, lbl in all_unconfirmed))

    return {'status': 'acted' if acted else 'idle', 'stages': acted}
