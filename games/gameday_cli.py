"""
`flask scores game-day` — the shared game-day scores pass (ADR-063)
===================================================================
Runs games/gameday.run_game_day and turns its summary into an exit code:

- ``idle`` and ``floor`` exit 0 with or without ``--scheduled``. Idle is the
  normal state of an hourly timer (no tracked game could have ended), and
  standing down at the credit floor is a warning, not a failure.
- ``error`` exits 1 after every consumer has had its turn, so the unit fails
  and journals like the daily passes.

``--scheduled`` is accepted for unit-shape uniformity with the game timers
(tests/test_scores_timers.py) and changes nothing here: this pass has no
"week not imported yet" state — an empty table is simply idle.
"""
import click
from flask.cli import AppGroup

scores_cli = AppGroup('scores', help='Cross-game score passes.')


@scores_cli.command('game-day')
@click.option('--scheduled', is_flag=True,
              help='Timer mode (accepted for uniformity; idle and floor '
                   'exit 0 either way).')
def game_day_cmd(scheduled):
    """One game-day tick: fetch finals for any sport a game is waiting on."""
    from games.gameday import run_game_day

    summary = run_game_day()
    click.echo(f'\n[scores game-day] {summary["status"]}')
    click.echo(f'  wanted: {", ".join(summary["wanted"]) or "nothing"}')
    if summary['fetched']:
        click.echo(f'  fetched: {", ".join(summary["fetched"])}')
    if summary['remaining'] is not None:
        click.echo(f'  credits remaining: {summary["remaining"]}')
    for slug, outcome in summary['applied'].items():
        click.echo(f'  {slug}: {_one_line(outcome)}')
    for error in summary['errors']:
        click.secho(f'  ERROR: {error}', fg='red', err=True)
    if summary['status'] == 'error':
        raise SystemExit(1)


def _one_line(outcome):
    if isinstance(outcome, dict):
        return outcome.get('details') or ', '.join(
            f'{k}={v}' for k, v in outcome.items()
            if not isinstance(v, (dict, list)))
    return str(outcome)


def register_scores_cli(app):
    """Register the cross-game score commands with the Flask app."""
    app.cli.add_command(scores_cli)
