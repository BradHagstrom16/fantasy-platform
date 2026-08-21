"""weekly_results lives-display locks (pre-launch audit §2 + §8.19).

The page must derive per-week lives from CfbWeekOutcome snapshots (or
current enrollment state when no snapshot exists yet) — never recompute
from pick history, which cannot see DQ-2 no-pick penalties or DQ-1
revivals and silently diverged from enrollment.lives_remaining.
"""

from extensions import db
from games.cfb.services.game_logic import (
    get_week_user_statuses,
    process_week_results,
)
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)


def _lose_week(number, users):
    """Seed week <number> where every listed user picks the losing side."""
    week = make_week(number)
    home = make_team(f'Home{number}')
    away = make_team(f'Away{number}')
    make_game(week, home, away, spread=-7.0, winner='away')
    for u in users:
        make_pick(u, week, home)
    return week


# ── Route: revival must not display as elimination ───────────────────────

def test_revived_players_show_in_not_out_on_wipe_week(client):
    """After a week-2 whole-pool wipe + revival, the week-2 results page
    shows both players IN at 1 life — the old pick-history recompute
    showed them OUT with an elimination banner."""
    u1 = make_user('p1')
    make_enrollment(u1, display_name='Alpha')
    u2 = make_user('p2')
    make_enrollment(u2, display_name='Bravo')
    week1 = _lose_week(1, [u1, u2])
    week2 = _lose_week(2, [u1, u2])
    db.session.commit()

    assert process_week_results(week1.id)['completed'] is True
    result = process_week_results(week2.id)
    assert result['revived'] == 2

    resp = client.get('/cfb/results/2')

    assert resp.status_code == 200
    assert b'>OUT<' not in resp.data
    assert b'Eliminated This Week' not in resp.data


# ── Route: no-pick penalties must show on the results page ───────────────

def test_no_pick_elimination_appears_on_results_page(client):
    """A no-pick elimination (DQ-2) shows OUT and lands in the
    Eliminated This Week banner — the old recompute saw no incorrect
    picks and displayed 2 lives, IN."""
    picker = make_user('picker')
    make_enrollment(picker, display_name='Safe Sam')
    ghost = make_user('ghost')
    make_enrollment(ghost, lives=1, display_name='Ghost Gary')

    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='away')
    make_pick(picker, week, away)
    db.session.commit()

    result = process_week_results(week.id)
    assert result['no_pick_penalties'] == 1

    resp = client.get('/cfb/results/1')

    assert resp.status_code == 200
    assert b'Eliminated This Week' in resp.data
    assert b'Ghost Gary' in resp.data
    assert b'>OUT<' in resp.data


# ── Service: snapshot-backed statuses with enrollment fallback ───────────

def test_statuses_from_outcomes_for_completed_week(app):
    """Completed weeks read the snapshot, not pick history."""
    u1 = make_user('p1')
    e1 = make_enrollment(u1)
    u2 = make_user('p2')
    e2 = make_enrollment(u2)
    week1 = _lose_week(1, [u1, u2])
    week2 = _lose_week(2, [u1, u2])
    db.session.commit()
    process_week_results(week1.id)
    process_week_results(week2.id)  # wipe + revival

    from games.cfb.models import CfbPick
    picks2 = CfbPick.query.filter_by(week_id=week2.id).all()
    statuses = get_week_user_statuses(week2, [e1, e2], picks2)

    for uid in (u1.id, u2.id):
        assert statuses[uid] == {
            'lives': 1,
            'is_eliminated': False,
            'eliminated_this_week': False,
        }


def test_statuses_fall_back_to_enrollment_state_without_snapshot(app):
    """An in-progress week (no snapshot rows) reads live enrollment state."""
    u1 = make_user('p1')
    e1 = make_enrollment(u1, lives=1)

    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner=None)  # undecided
    pick = make_pick(u1, week, home)
    db.session.commit()

    statuses = get_week_user_statuses(week, [e1], [pick])

    assert statuses[u1.id] == {
        'lives': 1,
        'is_eliminated': False,
        'eliminated_this_week': False,
    }


def test_fallback_flags_midweek_elimination_from_graded_pick(app):
    """Partial grading can eliminate before the week completes — the
    fallback attributes that elimination to the week of the losing pick."""
    u1 = make_user('p1')
    e1 = make_enrollment(u1, lives=0, eliminated=True)

    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='away')
    pick = make_pick(u1, week, home, is_correct=False)
    db.session.commit()

    statuses = get_week_user_statuses(week, [e1], [pick])

    assert statuses[u1.id]['is_eliminated'] is True
    assert statuses[u1.id]['eliminated_this_week'] is True
