"""
The Docket — CLI Commands
=========================
Flask CLI commands namespaced under the ``docket`` AppGroup. These are the
runners for logic that already exists: the two-sport importer (T2), the pure
grading engine + adapter (T4), and the D5 autopick package. Systemd timers
land with T11; until then every command below is run by hand.

Season runbook
--------------
**Tue Sep 1, ~06:00 CT — the Week 1 line freeze.** This is the deliberate
first write to the (until now empty) production docket tables::

    flask docket sync --mode setup                              # week 1 + both slates + first-posted lines
    flask docket set-tiebreaker 1 "Wisconsin @ Notre Dame"      # hand-set until T9's admin UI
    flask docket sync --mode status                             # verify: games in, lines locked, designation set

**Tue-Fri — gap fill.** Fills markets that weren't posted Tuesday and
refreshes live kickoffs off the free /events endpoint (D19). Also reports a
missing or unsound tiebreaker designation, days before it would matter::

    flask docket sync --mode lines

**Sat 11:00 AM CT — the deadline pass.** Freezes each game's kickoff (the D7
substitution-ordering input) and deals the D5 autopick package to every
enrolled player::

    flask docket sync --mode deadline

**Tue ~05:15 / Wed / Thu / Sun / Mon — scores** (daily through the December
window; /scores looks back at most 3 days, which is why midweek runs exist).
Writes scores and grades the week as soon as it is complete::

    flask docket sync --mode scores

**Any time — re-grade.** Idempotent; the fix after an admin No Contest
ruling or a corrected score::

    flask docket recalc          # every past-deadline week
    flask docket recalc 1        # one week

Credit budget: /events is free, /odds costs 2 per sport per run (skipped
once a sport's markets are all locked), /scores costs 2 per sport per run.
Every call logs the account's remaining credits via utils/odds_api.py.
"""
import click
from flask.cli import AppGroup
from sqlalchemy import func, select

from extensions import db
from games.docket.models import (
    DocketGame,
    DocketPick,
    DocketWeek,
    DocketWeekResult,
)
from games.docket.services.bridge_sheet import set_tiebreaker
from games.docket.services.deadline_pass import (
    DeadlinePassError,
    check_designation,
    run_deadline_pass,
)
from games.docket.services.enrollment import roster_user_ids
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.importer import import_week
from games.docket.services.scores import sync_scores
from games.docket.services.weeks import SEASON_YEAR, TOTAL_WEEKS, week_number_for
from games.docket.utils import now_utc, to_naive_utc

docket_cli = AppGroup('docket', help="The Docket (NFL+CFB pick'em) commands.")

SYNC_MODES = ('setup', 'lines', 'scores', 'deadline', 'status')


def _fail(message):
    """Report an operator-facing refusal and exit non-zero.

    Non-zero matters: T11's timers alert on it, and `deploy.sh`-style
    "it printed something" is not a success signal.
    """
    click.secho(f'ERROR: {message}', fg='red', err=True)
    raise SystemExit(1)


def _resolve_week_number(week):
    """The explicit --week, else the week containing now (pure math, so it
    resolves before the row exists — which is exactly the setup case)."""
    if week is not None:
        if not 1 <= week <= TOTAL_WEEKS:
            _fail(f'week must be 1-{TOTAL_WEEKS}, got {week}')
        return week
    resolved = week_number_for(now_utc())
    if resolved is None:
        _fail('the current time is outside the docket season — pass --week')
    return resolved


def _get_week(week_number):
    return db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))


def _echo_summary(title, summary):
    click.echo(f'\n[{title}]')
    for key, value in summary.items():
        if isinstance(value, list):
            value = ', '.join(str(v) for v in value) or '(none)'
        click.echo(f'  {key}: {value}')


def _report_designation(week):
    """Print designation problems; True when the week is sound."""
    problems = check_designation(week)
    for problem in problems:
        click.secho(f'  WARNING: {problem}', fg='yellow')
    if problems:
        click.secho(
            '  Fix with: flask docket set-tiebreaker '
            f'{week.week_number} "Away @ Home"', fg='yellow')
    return not problems


def _check_sync_status(summary, what):
    """Turn a sync summary into an exit code.

    'partial' means one sport failed while the other succeeded — the work
    that landed is kept, but the run did NOT do its job and must exit
    non-zero, or a sport can stay dark for a week with every timer green.
    Called after the useful work, so a failing sport never costs the
    healthy one its result.
    """
    status = summary.get('status')
    if status in ('error', 'partial'):
        _fail(f'{what} {"failed" if status == "error" else "partially failed"}'
              f': {"; ".join(summary.get("errors", []))}')


def _run_import(week_number, force_odds, title):
    summary = import_week(week_number, force_odds=force_odds)
    _echo_summary(title, summary)
    week = _get_week(week_number)
    if week is not None:
        _report_designation(week)
    _check_sync_status(summary, 'import')


def _run_scores(week_number, days_from):
    summary = sync_scores(week_number, days_from=days_from)
    _echo_summary(f'docket sync --mode scores (week {week_number})', summary)
    if summary.get('status') == 'error':
        _fail(f'score sync failed: {"; ".join(summary.get("errors", []))}')

    week = _get_week(week_number)
    graded = try_grade_week(week.id, user_ids=roster_user_ids())
    if graded['status'] == 'not_ready':
        click.echo(f'  grading: not ready — {graded["reason"]}')
    else:
        click.secho(f'  grading: {graded["graded"]} players graded',
                    fg='green')
    _check_sync_status(summary, 'score sync')


def _run_deadline(week_number, force):
    try:
        summary = run_deadline_pass(week_number, force=force)
    except DeadlinePassError as exc:
        _fail(str(exc))
    problems = summary.pop('problems', [])
    _echo_summary(f'docket sync --mode deadline (week {week_number})',
                  summary)
    if problems:
        click.secho('\n  Kickoffs are frozen, but AUTOPICK WAS SKIPPED:',
                    fg='red')
        for problem in problems:
            click.secho(f'    - {problem}', fg='red')
        _fail(
            f'designate the tiebreaker (flask docket set-tiebreaker '
            f'{week_number} "Away @ Home"), then re-run this pass — it is '
            f'idempotent, and picks are already frozen by the deadline')


def _run_status():
    click.echo(f'\n[docket status — season {SEASON_YEAR}]')
    now = to_naive_utc(now_utc())
    current = week_number_for(now_utc())
    click.echo(f'  now (UTC): {now}')
    click.echo(f'  current week: {current if current else "out of season"}')
    click.echo(f'  enrolled players: {len(roster_user_ids())}')

    weeks = db.session.scalars(
        select(DocketWeek).order_by(DocketWeek.week_number)).all()
    if not weeks:
        click.echo('  no weeks imported yet')
        return
    for week in weeks:
        games = db.session.scalar(select(func.count(DocketGame.id))
                                  .filter_by(week_id=week.id))
        spreads = db.session.scalar(
            select(func.count(DocketGame.id)).filter_by(week_id=week.id)
            .filter(DocketGame.spread_locked_at.is_not(None)))
        totals = db.session.scalar(
            select(func.count(DocketGame.id)).filter_by(week_id=week.id)
            .filter(DocketGame.total_locked_at.is_not(None)))
        finals = db.session.scalar(
            select(func.count(DocketGame.id)).filter_by(week_id=week.id)
            .filter(DocketGame.is_final.is_(True)))
        stamped = db.session.scalar(
            select(func.count(DocketGame.id)).filter_by(week_id=week.id)
            .filter(DocketGame.kickoff_at_deadline.is_not(None)))
        picks = db.session.scalar(select(func.count(DocketPick.id))
                                  .filter_by(week_id=week.id))
        results = db.session.scalar(select(func.count(DocketWeekResult.id))
                                    .filter_by(week_id=week.id))
        designated = (week.tiebreaker_game.away_team + ' @ '
                      + week.tiebreaker_game.home_team
                      if week.tiebreaker_game else 'NONE')
        click.echo(
            f'  week {week.week_number:>2}: {games:>3} games '
            f'({spreads} spreads, {totals} totals locked, {stamped} frozen, '
            f'{finals} final) | {picks} picks | {results} graded | '
            f'deadline {week.deadline_at} UTC | tiebreaker: {designated}')
        _report_designation(week)


@docket_cli.command('sync')
@click.option('--mode', required=True, type=click.Choice(SYNC_MODES),
              help='Sync mode to run.')
@click.option('--week', type=int, default=None,
              help='Docket week number (default: the week containing now).')
@click.option('--force', is_flag=True,
              help='deadline: run before the deadline (development only).')
@click.option('--force-odds', is_flag=True,
              help='setup/lines: fetch /odds even when every market is locked.')
@click.option('--days-from', type=int, default=3, show_default=True,
              help='scores: lookback window in days (API caps at 3).')
def sync_cmd(mode, week, force, force_odds, days_from):
    """Unified Docket automation CLI — run weekly tasks by mode."""
    if mode == 'status':
        _run_status()
        return

    week_number = _resolve_week_number(week)
    if mode == 'setup':
        _run_import(week_number, force_odds,
                    f'docket sync --mode setup (week {week_number})')
    elif mode == 'lines':
        if _get_week(week_number) is None:
            _fail(f'no docket week {week_number} yet — run '
                  f'`flask docket sync --mode setup --week {week_number}`')
        _run_import(week_number, force_odds,
                    f'docket sync --mode lines (week {week_number})')
    elif mode == 'scores':
        if _get_week(week_number) is None:
            _fail(f'no docket week {week_number} yet — run '
                  f'`flask docket sync --mode setup --week {week_number}`')
        _run_scores(week_number, days_from)
    elif mode == 'deadline':
        _run_deadline(week_number, force)


@docket_cli.command('recalc')
@click.argument('week', type=int, required=False)
def recalc_cmd(week):
    """Re-grade WEEK (or every past-deadline week) idempotently.

    The population is the full enrolled roster, per the grading pass's
    contract: a player who submitted nothing still gets a week result (0
    points, 0 wins, the week's default tiebreaker error) rather than being
    skipped. ``is_dropped`` belongs to the season rollup and is left alone.
    """
    roster = roster_user_ids()
    if week is not None:
        target = _get_week(week)
        if target is None:
            _fail(f'no docket week {week}')
        weeks = [target]
    else:
        now = to_naive_utc(now_utc())
        weeks = db.session.scalars(
            select(DocketWeek).filter(DocketWeek.deadline_at <= now)
            .order_by(DocketWeek.week_number)).all()
        if not weeks:
            click.echo('No week has reached its deadline yet.')
            return

    click.echo(f'\n[docket recalc] roster: {len(roster)} enrolled')
    for target in weeks:
        result = try_grade_week(target.id, user_ids=roster)
        if result['status'] == 'not_ready':
            click.echo(f'  week {target.week_number}: not ready — '
                       f'{result["reason"]}')
        else:
            click.secho(f'  week {target.week_number}: '
                        f'{result["graded"]} players graded', fg='green')


@docket_cli.command('set-tiebreaker')
@click.argument('week', type=int)
@click.argument('matchup')
def set_tiebreaker_cmd(week, matchup):
    """Designate WEEK's tiebreaker game from an 'Away @ Home' MATCHUP.

    The Week 1 hand-set (`"Wisconsin @ Notre Dame"`) until T9 ships the admin
    designation UI. Designation must satisfy the Grading Clarifications
    contract — a locked whole-tenth O/U total and a kickoff at or after the
    deadline — which this command verifies and reports.
    """
    target = _get_week(week)
    if target is None:
        _fail(f'no docket week {week}')
    try:
        game = set_tiebreaker(target, matchup)
    except ValueError as exc:
        _fail(str(exc))
    click.secho(f'Week {week} tiebreaker: {game.away_team} @ {game.home_team} '
                f'(total {game.total_points})', fg='green')
    if not _report_designation(target):
        _fail('the designated game does not satisfy the designation contract')


def register_docket_cli(app):
    """Register The Docket's CLI commands with the Flask app."""
    app.cli.add_command(docket_cli)
