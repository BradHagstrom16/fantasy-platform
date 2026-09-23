"""weekly_results lives-display locks (pre-launch audit §2 + §8.19).

The page must derive per-week lives from CfbWeekOutcome snapshots (or
current enrollment state when no snapshot exists yet) — never recompute
from pick history, which cannot see DQ-2 no-pick penalties or DQ-1
revivals and silently diverged from enrollment.lives_remaining.
"""

from extensions import db
from games.cfb.services.game_logic import (
    get_elimination_weeks,
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
            'lost_life': True,     # the wipe charged the life, then revived
            'no_pick': False,
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
        'lost_life': False,
        'no_pick': False,
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


def test_snapshot_status_flags_a_no_pick_penalty(app):
    """The DQ-2 penalty reaches the page through the snapshot: lost_life
    AND no_pick, so the Field can chip it and the summary can count it."""
    picker = make_user('picker')
    e_picker = make_enrollment(picker)
    ghost = make_user('ghost')
    e_ghost = make_enrollment(ghost)
    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='away')
    make_pick(picker, week, away)
    db.session.commit()
    process_week_results(week.id)

    statuses = get_week_user_statuses(week, [e_picker, e_ghost], [])

    assert statuses[ghost.id]['lost_life'] is True
    assert statuses[ghost.id]['no_pick'] is True
    assert statuses[picker.id]['lost_life'] is False


def test_elimination_weeks_take_the_latest_earlier_week(app):
    """Out week = the latest earlier week whose snapshot eliminated the
    player; the page's own week and later are never read."""
    out = make_user('out')
    make_enrollment(out, lives=1)
    safe = make_user('safe')
    make_enrollment(safe)
    week1 = make_week(1)
    h1, a1 = make_team('Home1'), make_team('Away1')
    make_game(week1, h1, a1, spread=-7.0, winner='away')
    make_pick(out, week1, h1)
    make_pick(safe, week1, a1)
    db.session.commit()
    process_week_results(week1.id)

    assert get_elimination_weeks([out.id, safe.id], 2) == {out.id: week1}
    assert get_elimination_weeks([out.id], 1) == {}
    assert get_elimination_weeks([], 2) == {}


# -- Route: The Field vs Already Out (critique P0, 2026-09-23) ---------------

def _field_html(html):
    """The Field table only (Already Out and the Cut live outside it)."""
    return html[html.index('<table'):html.index('</table>')]


def _out_html(html):
    return html[html.index('id="cfb-out-title"'):]


def _two_week_season(extra_out=0):
    """Week 1 knocks out 'Ollie Out' (+ extra_out more); week 2 is settled.

    'Sam Safe' wins both weeks, so no whole-pool wipe revives anyone.
    """
    safe = make_user('safe')
    make_enrollment(safe, display_name='Sam Safe')
    outs = []
    for i in range(1 + extra_out):
        u = make_user(f'out{i}')
        make_enrollment(u, lives=1,
                        display_name='Ollie Out' if i == 0 else f'Gone {i:02d}')
        outs.append(u)
    week1 = make_week(1)
    h1, a1 = make_team('Home1'), make_team('Away1')
    make_game(week1, h1, a1, spread=-7.0, winner='away')
    make_pick(safe, week1, a1)
    for u in outs:
        make_pick(u, week1, h1)
    week2 = make_week(2)
    h2, a2 = make_team('Home2'), make_team('Away2')
    make_game(week2, h2, a2, spread=-3.5, winner='home')
    make_pick(safe, week2, h2)
    db.session.commit()
    process_week_results(week1.id)
    process_week_results(week2.id)
    return safe, outs


def test_player_out_before_this_week_leaves_the_field(client):
    _two_week_season()

    html = client.get('/cfb/results/2').get_data(as_text=True)

    assert 'Ollie Out' not in _field_html(html)
    out = _out_html(html)
    assert 'Already Out' in html and 'Ollie Out' in out
    assert 'Week 1' in out, 'the list names the week the player went out'
    assert 'Out before Week 2' in out
    assert '<details' not in out, 'a short list is never collapsed'


def test_long_already_out_list_collapses(client):
    _two_week_season(extra_out=8)   # nine players out before week 2

    out = _out_html(client.get('/cfb/results/2').get_data(as_text=True))

    assert '<details' in out and 'Show all 9' in out


def test_no_pick_penalty_this_week_stays_in_the_field(client):
    """A missed pick is this week's story: the player stays in the Field
    with a NO PICK chip and counts in "Lost a life"."""
    picker = make_user('picker')
    make_enrollment(picker, display_name='Safe Sam')
    ghost = make_user('ghost')
    make_enrollment(ghost, display_name='Ghost Gary')
    week = make_week(1)
    home, away = make_team('Home1'), make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='away')
    make_pick(picker, week, away)
    db.session.commit()
    process_week_results(week.id)

    html = client.get('/cfb/results/1').get_data(as_text=True)

    field = _field_html(html)
    assert 'Ghost Gary' in field and '>NO PICK<' in field
    assert 'id="cfb-out-title"' not in html
    assert 'cfb-summary-num is-lost">1<' in html


def test_already_out_viewer_gets_the_observer_card(client):
    _, outs = _two_week_season()
    with client.session_transaction() as sess:
        sess['_user_id'] = outs[0].auth_id
        sess['_fresh'] = True

    html = client.get('/cfb/results/2').get_data(as_text=True)

    assert 'Your season ended in Week 1.' in html
    assert 'cfb-verdict is-out' in html
    assert '>NO PICK<' not in html, 'an old elimination is never replayed as a penalty'


def test_distribution_carries_spread_result_and_labeled_count(client):
    week = make_week(1)
    home, away = make_team('Liberty'), make_team('Toledo')
    make_game(week, home, away, spread=-7.0, winner='home')
    for name in ('a', 'b'):
        u = make_user(name)
        make_enrollment(u)
        make_pick(u, week, home)
    c = make_user('c')
    make_enrollment(c)
    make_pick(c, week, away)
    db.session.commit()
    process_week_results(week.id)

    html = client.get('/cfb/results/1').get_data(as_text=True)
    dist = html[html.index('cfb-dist-list'):html.index('cfb-dist-caption')]

    assert dist.index('Liberty') < dist.index('Toledo'), 'ordered by count'
    assert '-7.0' in dist and '+7.0' in dist
    assert '2 picks' in dist and '1 pick<' in dist
    assert 'Spread is the tiebreaker.' in html


def test_pending_week_says_games_are_still_being_played(client):
    u = make_user('p1')
    make_enrollment(u)
    week = make_week(1)
    home, away = make_team('Home1'), make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner=None)
    make_pick(u, week, home)
    db.session.commit()

    html = client.get('/cfb/results/1').get_data(as_text=True)

    assert 'Games are still being played.' in html
    assert 'The slate is settled' not in html


def test_no_contest_pick_is_not_pending(client):
    """A No Contest pick is never graded (is_correct stays None); it reads
    NC and survived, never TBD, and never holds the week "in progress"."""
    u = make_user('p1')
    make_enrollment(u, display_name='Nora')
    week = make_week(1)
    home, away = make_team('Home1'), make_team('Away1')
    make_game(week, home, away, spread=-7.0, no_contest=True)
    make_pick(u, week, home)
    db.session.commit()

    html = client.get('/cfb/results/1').get_data(as_text=True)

    assert '>NC<' in _field_html(html)
    assert 'Games are still being played.' not in html
    assert 'cfb-summary-num is-survived">1<' in html
