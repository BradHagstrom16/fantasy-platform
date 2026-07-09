"""CFB phase-scoping locks (pre-launch audit §8.11 — DQ-3 + DQ-7).

Regression locks for two of Brad's binding rulings, both intended as
implemented (no code change):

  DQ-3 — weeks 1-15 share one "regular-season" used-team pool; the
         Conference Championship (week 15, is_playoff_week=False)
         consumes a regular-season team. The pool resets at week 16;
         weeks 16-19 (CFP) share a separate playoff pool.
  DQ-7 — the cumulative-spread tiebreaker is lifetime: it sums every
         pick across both phases with no CFP reset.

get_used_team_ids partitions strictly on CfbWeek.is_playoff_week and
honors exclude_current; calculate_cumulative_spread is phase-agnostic.
"""
import pytest

from app import create_app
from extensions import db
from games.cfb.services.game_logic import (
    calculate_cumulative_spread,
    get_used_team_ids,
)
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ── DQ-3 — regular-season pool spans weeks 1-15 ───────────────────────────

def test_regular_season_weeks_share_one_pool(app):
    """A team picked in week 1 is 'used' when evaluating week 2."""
    w1 = make_week(1, is_playoff=False)
    w2 = make_week(2, is_playoff=False)
    user = make_user('p1')
    team = make_team('Tigers')
    make_pick(user, w1, team)
    db.session.commit()

    used = get_used_team_ids(user.id, w2)

    assert team.id in used


def test_week_15_consumes_a_regular_season_team(app):
    """DQ-3: week 15 (Conf Championship, is_playoff_week=False) lives in the
    regular pool — a week-15 pick counts as used in week 3 and vice versa."""
    w3 = make_week(3, is_playoff=False)
    w15 = make_week(15, is_playoff=False)
    user = make_user('p1')
    cc_team = make_team('Champs')
    make_pick(user, w15, cc_team)
    db.session.commit()

    # week-15 pick is 'used' when looking at an earlier regular week
    assert cc_team.id in get_used_team_ids(user.id, w3)
    # and the reverse: an earlier pick is 'used' when evaluating week 15
    reg_team = make_team('Early')
    make_pick(user, w3, reg_team)
    db.session.commit()
    assert reg_team.id in get_used_team_ids(user.id, w15)


# ── DQ-3 — playoff pool is isolated and resets at week 16 ─────────────────

def test_playoff_weeks_share_their_own_pool(app):
    """A team picked in week 16 is 'used' when evaluating week 17."""
    w16 = make_week(16, is_playoff=True)
    w17 = make_week(17, is_playoff=True)
    user = make_user('p1')
    team = make_team('Seeds')
    make_pick(user, w16, team)
    db.session.commit()

    assert team.id in get_used_team_ids(user.id, w17)


def test_regular_pick_not_used_in_playoff_phase(app):
    """The pool resets at week 16: a regular-season pick frees up for CFP."""
    w1 = make_week(1, is_playoff=False)
    w16 = make_week(16, is_playoff=True)
    user = make_user('p1')
    team = make_team('Reset')
    make_pick(user, w1, team)
    db.session.commit()

    assert team.id not in get_used_team_ids(user.id, w16)


def test_playoff_pick_not_used_in_regular_phase(app):
    """Symmetric isolation: a playoff pick doesn't taint the regular pool."""
    w2 = make_week(2, is_playoff=False)
    w16 = make_week(16, is_playoff=True)
    user = make_user('p1')
    team = make_team('Bracket')
    make_pick(user, w16, team)
    db.session.commit()

    assert team.id not in get_used_team_ids(user.id, w2)


# ── exclude_current flag ──────────────────────────────────────────────────

def test_exclude_current_honored(app):
    """exclude_current drops (default) or keeps the evaluated week's own pick."""
    w2 = make_week(2, is_playoff=False)
    user = make_user('p1')
    team = make_team('ThisWeek')
    make_pick(user, w2, team)
    db.session.commit()

    assert team.id not in get_used_team_ids(user.id, w2, exclude_current=True)
    assert team.id in get_used_team_ids(user.id, w2, exclude_current=False)


# ── DQ-7 — cumulative spread is lifetime (no CFP reset) ───────────────────

def test_cumulative_spread_is_lifetime_across_phases(app):
    """A regular-season pick and a playoff pick both feed the tiebreaker."""
    w1 = make_week(1, is_playoff=False)
    w16 = make_week(16, is_playoff=True)
    user = make_user('p1')
    enrollment = make_enrollment(user)
    fav_reg, opp_reg = make_team('RegFav'), make_team('RegDog')
    fav_cfp, opp_cfp = make_team('CfpFav'), make_team('CfpDog')
    make_game(w1, fav_reg, opp_reg, spread=-7.0)   # picked team favored by 7
    make_game(w16, fav_cfp, opp_cfp, spread=-3.0)  # picked team favored by 3
    make_pick(user, w1, fav_reg)
    make_pick(user, w16, fav_cfp)
    db.session.commit()

    calculate_cumulative_spread(enrollment)

    # -7 (regular) + -3 (playoff) = -10, summed across phases with no reset.
    assert enrollment.cumulative_spread == pytest.approx(-10.0)
