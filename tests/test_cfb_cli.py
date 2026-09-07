"""The `flask cfb` CLI: the operator's repairs.

`recalc-spreads` is the repair after the 2026-09-01 rule fix (a pick's
spread counts only once its week deadline passes; higher is better): it
recomputes every stored total under the current rule, prints old -> new
per member, and exits 0. Idempotent.

`repair-week-dates --week N` is the repair after the 2026-09-07 incident
(run_setup stored Week 2's aware 11:00 CT deadline as 16:00 through the
Postgres session-zone cast): it recomputes a regular-season week's
start_date/deadline from SEASON_SCHEDULE, prints old -> new, and refuses
the manually scheduled weeks (playoff / named rounds) and completed weeks.
"""
from datetime import datetime

import pytest

from extensions import db
from games.cfb.cli import cfb_cli
from games.cfb.models import CfbWeek
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def test_recalc_spreads_replaces_stale_totals_and_reports_each_member(app, runner):
    week = make_week(1)  # deadline already passed (fixture default)
    fav, dog = make_team('Fav'), make_team('Dog')
    make_game(week, fav, dog, spread=-7.0)
    alpha = make_user('alpha')
    e_alpha = make_enrollment(alpha)
    make_pick(alpha, week, fav)
    bravo = make_user('bravo')
    e_bravo = make_enrollment(bravo)
    make_pick(bravo, week, dog)
    e_alpha.cumulative_spread = 99.0  # stale
    e_bravo.cumulative_spread = 99.0
    db.session.commit()
    ids = (e_alpha.id, e_bravo.id)

    result = runner.invoke(cfb_cli, ['recalc-spreads'])

    assert result.exit_code == 0, result.output
    db.session.expire_all()
    from games.cfb.models import CfbEnrollment
    assert db.session.get(CfbEnrollment, ids[0]).cumulative_spread == -7.0
    assert db.session.get(CfbEnrollment, ids[1]).cumulative_spread == 7.0
    assert 'alpha: 99.0 -> -7.0' in result.output
    assert 'bravo: 99.0 -> 7.0' in result.output
    assert '2 enrollments' in result.output


# ── repair-week-dates: the 2026-09-07 GMT-cast repair ─────────────────────

def _shifted_week_2():
    """Week 2 as Postgres stored it: 11:00 CT bound as timestamptz and cast
    in a GMT session (start Thu 00:00 -> 05:00, deadline Sat 11:00 -> 16:00)."""
    week = make_week(2, deadline=datetime(2026, 9, 12, 16, 0))
    week.start_date = datetime(2026, 9, 10, 5, 0)
    db.session.commit()
    return week.id


def test_repair_week_dates_restores_the_schedule_wall_clock(app, runner):
    week_id = _shifted_week_2()

    result = runner.invoke(cfb_cli, ['repair-week-dates', '--week', '2'])

    assert result.exit_code == 0, result.output
    db.session.expire_all()
    fixed = db.session.get(CfbWeek, week_id)
    assert fixed.deadline == datetime(2026, 9, 12, 11, 0)
    assert fixed.start_date == datetime(2026, 9, 10, 0, 0)
    assert 'deadline: 2026-09-12 16:00 -> 2026-09-12 11:00' in result.output
    assert 'start_date: 2026-09-10 05:00 -> 2026-09-10 00:00' in result.output


def test_repair_week_dates_is_idempotent(app, runner):
    _shifted_week_2()
    runner.invoke(cfb_cli, ['repair-week-dates', '--week', '2'])

    result = runner.invoke(cfb_cli, ['repair-week-dates', '--week', '2'])

    assert result.exit_code == 0, result.output
    assert 'unchanged' in result.output


@pytest.mark.parametrize('field', ['is_playoff_week', 'round_name', 'is_complete'])
def test_repair_week_dates_refuses_manual_and_finished_weeks(app, runner, field):
    """CFP weeks are hand-scheduled (the rigid Saturday cadence in
    SEASON_SCHEDULE is wrong for them, tests/test_cfb_cfp_datemath.py) and a
    completed week's dates are history: neither is rewritten from the
    schedule, exit 1, no write."""
    week_id = _shifted_week_2()
    week = db.session.get(CfbWeek, week_id)
    setattr(week, field, 'CFP Semifinals' if field == 'round_name' else True)
    db.session.commit()

    result = runner.invoke(cfb_cli, ['repair-week-dates', '--week', '2'])

    assert result.exit_code == 1, result.output
    db.session.expire_all()
    assert db.session.get(CfbWeek, week_id).deadline == datetime(2026, 9, 12, 16, 0)


def test_repair_week_dates_unknown_week_exits_1(app, runner):
    result = runner.invoke(cfb_cli, ['repair-week-dates', '--week', '7'])

    assert result.exit_code == 1, result.output
    assert 'no Week 7' in result.output
