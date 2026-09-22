"""
`flask club desk` / `flask club paper` — the Club Desk's two passes (ADR-065)
===========================================================================
Runners for games/club_desk.py. Rollout state lives on the unit's
``ExecStart`` line, never in ``.env``: ``--anchor`` names the games the
desk may lead for, ``--ride`` the slots (F, S, D) that may carry a rider.

``--dry-run`` composes everything, prints what would go and what would
latch, and sends nothing and writes nothing. ``--now ISO`` is the one clock
the run reads (naive means America/Chicago), which is what makes a dry run
at a stated instant truthful in production, where the ``*_FAKE_NOW`` seams
are off. ``--scheduled`` is the TIMER-ONLY flag: out of season and
week-not-imported become a logged exit 0; nothing else is softened.
"""
from datetime import UTC, datetime

import click
from flask.cli import AppGroup

from utils.time import PLATFORM_TZ

club_cli = AppGroup('club', help='The Club Desk: cross-game member mail.')


def _parse_now(raw):
    if raw is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        click.secho(f'ERROR: --now must be ISO 8601, got {raw!r}', fg='red',
                    err=True)
        raise SystemExit(1) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PLATFORM_TZ)
    return parsed.astimezone(UTC)


def _csv(raw):
    return tuple(part.strip() for part in raw.split(',') if part.strip())


def _echo_now(now):
    click.echo(f'  now: {now.isoformat()} '
               f'({now.astimezone(PLATFORM_TZ):%a %b %-d %-I:%M %p} CT)')


def _echo_letters(composed):
    for item in composed:
        user = item.user
        rider = f' + rider {item.rider}' if item.rider else ''
        click.echo(f'  -> {user.get_display_name()} <{user.email}>: '
                   f'"{item.letter.subject}" [{item.anchor}{rider}]')


@club_cli.command('desk')
@click.option('--dry-run', is_flag=True,
              help='Compose and print; send nothing, write nothing.')
@click.option('--now', 'now_raw', default=None, metavar='ISO',
              help='The instant to run at (naive = America/Chicago). '
                   'Default: the real clock.')
@click.option('--anchor', 'anchors', default='cfb,docket', show_default=True,
              help='Games the desk may lead for (comma-separated slugs).')
@click.option('--ride', 'rides', default='', show_default=True,
              help='Slots that may carry a rider: F, S (comma-separated).')
@click.option('--scheduled', is_flag=True,
              help='Timer mode: exit 0 when nothing named has a week.')
def desk_cmd(dry_run, now_raw, anchors, rides, scheduled):
    """One firing of the reminder desk."""
    from games.club_desk import SLOTS, run_desk

    now = _parse_now(now_raw)
    anchor_slugs, ride_slots = _csv(anchors), _csv(rides)
    bad = [s for s in ride_slots if s not in SLOTS]
    if bad:
        click.secho(f'ERROR: unknown slot(s) {bad}; known: '
                    f'{", ".join(SLOTS)}', fg='red', err=True)
        raise SystemExit(1)

    click.echo(f'\n[club desk{" (dry run)" if dry_run else ""}]')
    _echo_now(now)
    click.echo(f'  anchor: {", ".join(anchor_slugs)}   '
               f'ride: {", ".join(ride_slots) or "(none)"}')
    run = run_desk(now, anchors=anchor_slugs, rides=ride_slots,
                   dry_run=dry_run, scheduled=scheduled)

    for slug, why in run.skipped.items():
        click.echo(f'  {slug}: {why}')
    if not run.anchors:
        if run.exit_code:
            click.secho('ERROR: nothing to do: no game named in --anchor '
                        'has a week (out of season or not imported)',
                        fg='red', err=True)
            raise SystemExit(1)
        click.echo('  no tier is due right now')
        return
    for anchor in run.anchors:
        rider = (f' + rider {anchor.rider.consumer.slug}/{anchor.rider.tier}'
                 if anchor.rider else '')
        click.echo(f'  anchor: {anchor.consumer.slug}/{anchor.tier} '
                   f'(slot {anchor.slot or "-"}, deadline '
                   f'{anchor.deadline.astimezone(PLATFORM_TZ):%a %-I:%M %p} CT)'
                   f'{rider}')
    _echo_letters(run.composed)
    for error in run.errors:
        click.secho(f'  ERROR: {error}', fg='red', err=True)
    if dry_run:
        latch = ', '.join(f'{k}={v}' for k, v in run.latched.items()) or 'nothing'
        click.echo(f'  would send {len(run.composed)} letter(s); would latch: '
                   f'{latch}')
        return
    click.echo(f'  delivered: {run.delivered or "nothing"}; latched: '
               f'{run.latched or "nothing"}')
    if run.exit_code:
        click.secho('ERROR: an active reminder tier reached nobody',
                    fg='red', err=True)
        raise SystemExit(run.exit_code)


@club_cli.command('paper')
@click.option('--dry-run', is_flag=True,
              help='Compose from whatever is open now and print; open '
                   'nothing, send nothing, write nothing.')
@click.option('--now', 'now_raw', default=None, metavar='ISO',
              help='The instant to run at (naive = America/Chicago).')
@click.option('--scheduled', is_flag=True,
              help='Timer mode: exit 0 when nothing is open.')
def paper_cmd(dry_run, now_raw, scheduled):
    """The Tuesday Paper: open both games, then one letter per member."""
    from games.club_desk import run_paper

    now = _parse_now(now_raw)
    click.echo(f'\n[club paper{" (dry run)" if dry_run else ""}]')
    _echo_now(now)
    run = run_paper(now, dry_run=dry_run, scheduled=scheduled)

    for error in run.errors:
        click.secho(f'  ERROR: {error}', fg='red', err=True)
    if not run.opened:
        if run.exit_code:
            click.secho('ERROR: nothing is open', fg='red', err=True)
            raise SystemExit(1)
        click.echo('  nothing is open right now')
        return
    for slug, week in run.opened.items():
        note = ' (already announced)' if run.announced.get(slug) else ''
        click.echo(f'  open: {slug} week {week.week_number}{note}')
    if run.record_week is not None:
        graded = run.record_week.default_error_tenths is not None
        click.echo(f'  record: docket week {run.record_week.week_number} '
                   f'({"graded" if graded else "not graded yet"}'
                   f'{", already sent" if run.record_week.record_notified else ""})')
    for item in run.composed:
        user = item.user
        click.echo(f'  -> {user.get_display_name()} <{user.email}>: '
                   f'"{item.letter.subject}" [{", ".join(item.games)}]')
    if dry_run:
        click.echo(f'  would send {len(run.composed)} letter(s)')
        return
    click.echo(f'  delivered sections: {run.delivered or "nothing"}; '
               f'latched: {run.latched or "nothing"}')
    if run.exit_code:
        raise SystemExit(run.exit_code)


def register_club_cli(app):
    """Register the Club Desk commands with the Flask app."""
    app.cli.add_command(club_cli)
