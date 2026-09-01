"""The `flask cfb` CLI: the operator's cumulative-spread recalc.

`recalc-spreads` is the repair after the 2026-09-01 rule fix (a pick's
spread counts only once its week deadline passes; higher is better): it
recomputes every stored total under the current rule, prints old -> new
per member, and exits 0. Idempotent.
"""
import pytest

from extensions import db
from games.cfb.cli import cfb_cli
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
