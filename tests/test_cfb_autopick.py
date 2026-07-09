"""CFB autopick selection locks (pre-launch audit §8.12).

Regression locks for process_autopicks: the deadline gate, most-favored
selection within the 16-point cap, the smallest-underdog fallback, the
pick'em / no-eligible-team failure path (recorded, no pick — the life
penalty then applies at processing per DQ-2), and the guards that skip
eliminated/already-picked users, started games, and CFP-eliminated
teams in playoff weeks.

Autopick runs only after a deadline passes but considers only games that
have NOT kicked off (game_time > now). Those gates are independent, so a
week uses a past deadline (autopick eligible) with future game_times
(games still pickable) — the realistic post-deadline / pre-kickoff window.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.cfb.models import CfbPick
from games.cfb.services.game_logic import (
    check_and_process_autopicks,
    process_autopicks,
)
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

# Naive pool-tz wall clock. A future game_time keeps a game pickable; a past
# one marks it kicked off. FUTURE_DEADLINE keeps a week pre-deadline.
FUTURE_GAME = datetime(2099, 1, 1, 12, 0)
FUTURE_DEADLINE = datetime(2099, 1, 1, 11, 0)
STARTED = datetime(2020, 1, 1, 12, 0)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _future_game(week, home, away, *, spread):
    """A game in a past-deadline week whose kickoff is still ahead."""
    g = make_game(week, home, away, spread=spread)
    g.game_time = FUTURE_GAME
    db.session.flush()
    return g


def _pick_for(user, week):
    return CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first()


# ── deadline gate ─────────────────────────────────────────────────────────

def test_autopick_skips_before_deadline(app):
    """No autopicks run while the deadline is still in the future."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['processed'] is False
    assert 'Deadline' in result['reason']


# ── primary selection: most-favored team within the 16-point cap ──────────

def test_autopick_picks_most_favored_within_cap(app):
    """Among eligible favorites, the most-favored (≤16) wins; a >16 favorite
    is never chosen even though it is 'more favored'."""
    week = make_week(1)  # past deadline → autopick eligible
    a_home, a_away = make_team('Fav14'), make_team('Dog14')
    b_home, b_away = make_team('Fav7'), make_team('Dog7')
    c_home, c_away = make_team('Fav20'), make_team('Dog20')
    _future_game(week, a_home, a_away, spread=-14.0)  # favored by 14
    _future_game(week, b_home, b_away, spread=-7.0)   # favored by 7
    _future_game(week, c_home, c_away, spread=-20.0)  # favored by 20 (over cap)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['autopicks'] == 1
    assert _pick_for(user, week).team_id == a_home.id  # the 14-pt favorite


# ── fallback: smallest underdog when no favorite is within the cap ────────

def test_autopick_falls_back_to_smallest_underdog(app):
    """With every favorite over the cap, the smallest underdog is taken."""
    week = make_week(1)
    a_home, a_away = make_team('Fav18'), make_team('Dog18')
    b_home, b_away = make_team('Fav25'), make_team('Dog25')
    _future_game(week, a_home, a_away, spread=-18.0)  # away dog by 18
    _future_game(week, b_home, b_away, spread=-25.0)  # away dog by 25
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['autopicks'] == 1
    assert _pick_for(user, week).team_id == a_away.id  # smallest underdog (18)


# ── pick'em / no-eligible-team → recorded failure, no pick ────────────────

def test_autopick_cannot_select_pickem_game(app):
    """A pick'em (spread 0.0) is selectable by neither pass — failure, no pick."""
    week = make_week(1)
    home, away = make_team('EvenH'), make_team('EvenA')
    _future_game(week, home, away, spread=0.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['autopicks'] == 0
    assert result['failed'] == 1
    assert _pick_for(user, week) is None


def test_autopick_records_failure_when_no_eligible_team(app):
    """When the lone pickable game's two teams are both already used in the
    phase, no team is eligible → recorded failure, no pick."""
    w1 = make_week(1, is_playoff=False)
    w2 = make_week(2, is_playoff=False)
    w3 = make_week(3, is_playoff=False)
    home, away = make_team('UsedH'), make_team('UsedA')
    _future_game(w2, home, away, spread=-7.0)  # the only pickable game
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, w1, home)   # home already used
    make_pick(user, w3, away)   # away already used
    db.session.commit()

    result = process_autopicks(w2.id)

    assert result['autopicks'] == 0
    assert result['failed'] == 1
    assert _pick_for(user, w2) is None


# ── started games are excluded from candidates ────────────────────────────

def test_autopick_excludes_started_games(app):
    """A more-favored team whose game has kicked off is skipped."""
    week = make_week(1)
    open_h, open_a = make_team('OpenFav7'), make_team('OpenDog7')
    started_h, started_a = make_team('StartedFav14'), make_team('StartedDog14')
    _future_game(week, open_h, open_a, spread=-7.0)     # eligible, favored 7
    started = make_game(week, started_h, started_a, spread=-14.0)  # favored 14
    started.game_time = STARTED  # already kicked off → excluded
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['autopicks'] == 1
    # The 14-pt favorite started, so the 7-pt open favorite is taken instead.
    assert _pick_for(user, week).team_id == open_h.id


# ── eliminated and already-picked users are skipped ───────────────────────

def test_autopick_skips_eliminated_and_already_picked_users(app):
    """Only an active, pickless enrollment receives an autopick."""
    week = make_week(1)
    home, away = make_team('Fav7'), make_team('Dog7')
    _future_game(week, home, away, spread=-7.0)
    active = make_user('active')
    make_enrollment(active)
    picked = make_user('picked')
    make_enrollment(picked)
    make_pick(picked, week, away)  # already has a pick
    gone = make_user('gone')
    make_enrollment(gone, lives=0, eliminated=True)
    db.session.commit()

    result = process_autopicks(week.id)

    assert result['autopicks'] == 1
    assert _pick_for(active, week) is not None and _pick_for(active, week).team_id == home.id
    assert _pick_for(picked, week).team_id == away.id  # untouched
    assert _pick_for(gone, week) is None               # eliminated, skipped


# ── CFP-eliminated teams excluded in playoff weeks ────────────────────────

def test_autopick_excludes_cfp_eliminated_in_playoff_weeks(app):
    """In a playoff week the autopick never lands on a CFP-eliminated team:
    the eliminated favorite is passed over for an eligible one elsewhere.

    (Realistically an eliminated team has no future game — this guard is the
    backstop, so the two teams sit in separate games.)"""
    week = make_week(16, is_playoff=True)
    elim_h, elim_a = make_team('Eliminated'), make_team('ElimOpp')
    alive_h, alive_a = make_team('Alive'), make_team('AliveOpp')
    _future_game(week, elim_h, elim_a, spread=-14.0)  # eliminated, favored 14
    _future_game(week, alive_h, alive_a, spread=-7.0)  # eligible, favored 7
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    with patch(
        'games.cfb.services.game_logic.get_cfp_eliminated_teams',
        return_value={'Eliminated'},
    ):
        result = process_autopicks(week.id)

    assert result['autopicks'] == 1
    pick = _pick_for(user, week)
    assert pick.team_id == alive_h.id          # eligible favorite taken
    assert pick.team_id != elim_h.id           # eliminated team never picked


# ── CLI sweep emails the admin about pickless players (audit §4) ──────────

def test_check_and_process_autopicks_emails_admin_on_failure(app):
    """A player left pickless (no eligible team) gets surfaced to the admin —
    that silent no-pick becomes a DQ-2 life loss at processing."""
    week = make_week(1)
    home, away = make_team('EvenH'), make_team('EvenA')
    _future_game(week, home, away, spread=0.0)  # pick'em → no eligible team
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    with patch('games.cfb.services.automation._send_admin_email') as mock_email:
        check_and_process_autopicks()

    assert mock_email.called
    body = mock_email.call_args[0][1]
    assert 'p1' in body


def test_check_and_process_autopicks_no_email_when_all_succeed(app):
    """No failures → no admin email (don't cry wolf on clean sweeps)."""
    week = make_week(1)
    home, away = make_team('Fav7'), make_team('Dog7')
    _future_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()

    with patch('games.cfb.services.automation._send_admin_email') as mock_email:
        check_and_process_autopicks()

    assert not mock_email.called
