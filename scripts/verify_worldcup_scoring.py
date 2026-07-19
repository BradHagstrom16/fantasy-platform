"""Read-only scoring audit for the World Cup Fantasy Pool.

Recomputes every stored scoring value from first principles and reports
mismatches. Safe to run against production (SELECTs only, no writes).

Invariants checked:
  1. Team base_points   == sum of compute_team_score_events (the SSoT)
  2. Team multiplied_points == base_points x multiplier
  3. Pick base/multiplied points mirror the picked team's
  4. Enrollment total_score == sum of its picks' multiplied points
  5. Group W/D/L columns match a recount of completed group matches
  6. Podium best_finish codes match the final / third-place match outcomes
  7. Completed knockout matches carry a winner (a winnerless completed KO
     match silently scores zero for everyone — the process-match gap)

Usage:
  ENVIRONMENT=testing venv/bin/python scripts/verify_worldcup_scoring.py   # local
  # prod (from repo root on the droplet):
  ENVIRONMENT=production FLASK_APP=app.py venv/bin/python scripts/verify_worldcup_scoring.py

Exit code 0 with per-check counts on success; 1 with a mismatch listing on
any failure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402


def run_audit() -> int:
    from games.worldcup.models import (
        WorldCupEnrollment,
        WorldCupMatch,
        WorldCupPick,
        WorldCupTeam,
    )
    from games.worldcup.services.scoring import compute_team_score_events

    failures: list[str] = []
    checks = 0

    def check(ok: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(message)

    teams = WorldCupTeam.query.order_by(WorldCupTeam.fifa_code).all()
    matches = WorldCupMatch.query.order_by(WorldCupMatch.match_number).all()
    picks = WorldCupPick.query.all()
    enrollments = WorldCupEnrollment.query.all()

    # 1 + 2: team parity against the ScoreEvent SSoT.
    for t in teams:
        derived = sum(e.base_points for e in compute_team_score_events(t))
        stored = float(t.base_points or 0.0)
        check(
            abs(derived - stored) < 1e-6,
            f'{t.fifa_code}: base_points stored={stored} derived={derived}',
        )
        check(
            abs(float(t.multiplied_points or 0.0) - stored * t.multiplier) < 1e-6,
            f'{t.fifa_code}: multiplied_points {t.multiplied_points} '
            f'!= base {stored} x {t.multiplier}',
        )

    # 3: picks mirror their team.
    for p in picks:
        check(
            abs(float(p.base_points or 0.0) - float(p.team.base_points or 0.0)) < 1e-6,
            f'pick {p.id} ({p.team.fifa_code}): base {p.base_points} '
            f'!= team base {p.team.base_points}',
        )
        check(
            abs(float(p.multiplied_points or 0.0)
                - float(p.team.multiplied_points or 0.0)) < 1e-6,
            f'pick {p.id} ({p.team.fifa_code}): multiplied {p.multiplied_points} '
            f'!= team multiplied {p.team.multiplied_points}',
        )

    # 4: enrollment totals.
    for e in enrollments:
        derived = sum(float(p.multiplied_points or 0.0) for p in e.picks)
        check(
            abs(float(e.total_score or 0.0) - derived) < 1e-6,
            f'enrollment {e.id}: total_score {e.total_score} != sum(picks) {derived}',
        )

    # 5: group W/D/L recount.
    for t in teams:
        wins = draws = losses = 0
        for m in matches:
            if m.stage != 'group' or not m.is_completed:
                continue
            if t.id not in (m.home_team_id, m.away_team_id):
                continue
            if m.is_draw:
                draws += 1
            elif m.winner_team_id == t.id:
                wins += 1
            else:
                losses += 1
        stored_wdl = (t.group_wins or 0, t.group_draws or 0, t.group_losses or 0)
        check(
            stored_wdl == (wins, draws, losses),
            f'{t.fifa_code}: stored W/D/L {stored_wdl} != recount {(wins, draws, losses)}',
        )

    # 6: podium codes vs the deciding matches.
    by_id = {t.id: t for t in teams}
    for m in matches:
        if m.stage not in ('final', 'third_place') or not m.is_completed:
            continue
        if not m.winner_team_id:
            continue  # caught by check 7
        winner = by_id[m.winner_team_id]
        loser_id = (
            m.away_team_id if m.winner_team_id == m.home_team_id
            else m.home_team_id
        )
        if m.stage == 'final':
            check(
                winner.best_finish == 'champion',
                f'final winner {winner.fifa_code} best_finish '
                f'{winner.best_finish!r} != champion',
            )
            loser = by_id.get(loser_id)
            check(
                loser is not None and loser.best_finish == 'runner_up',
                f'final loser best_finish '
                f'{loser.best_finish if loser else None!r} != runner_up',
            )
        else:
            check(
                winner.best_finish == '3rd',
                f'third-place winner {winner.fifa_code} best_finish '
                f'{winner.best_finish!r} != 3rd',
            )

    # 7: no winnerless completed knockout matches.
    for m in matches:
        if m.stage == 'group' or not m.is_completed:
            continue
        check(
            bool(m.winner_team_id),
            f'match {m.match_number} ({m.stage}): completed without a winner '
            '-- scores zero for everyone',
        )

    print(f'teams={len(teams)} matches={len(matches)} picks={len(picks)} '
          f'enrollments={len(enrollments)}')
    if failures:
        print(f'FAIL: {len(failures)} of {checks} checks failed')
        for f in failures:
            print(f'  - {f}')
        return 1
    print(f'OK: all {checks} checks passed')
    return 0


if __name__ == '__main__':
    application = create_app()
    with application.app_context():
        raise SystemExit(run_audit())
