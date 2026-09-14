"""CFB Survivor verdict + elimination pushes (PR 3).

Locks the push feed process_week_results now returns (graded + the this-run
elimination diff), the three survivor outcomes push_survivor_verdicts sends
(survive / lose-a-life / ceremony), the garnish-tally fallback, and that all
three grading callers fire the helper. send_push is patched everywhere; nothing
here needs VAPID or a real push service.
"""
from pathlib import Path
from unittest.mock import patch

from extensions import db
from games.cfb.services.game_logic import process_week_results
from games.cfb.services.reminders import push_survivor_verdicts
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

_PATH = 'games.cfb.services.reminders.send_push'


# ---- process_week_results return shape -----------------------------------

def test_existing_result_keys_intact(app):
    """Regression guard: the new keys are additive; every prior key survives."""
    week = make_week(1)
    home, away = make_team('Home U'), make_team('Away St')
    make_game(week, home, away, spread=-3.0, winner='home')
    u = make_user('picker')
    make_enrollment(u)
    make_pick(u, week, home)
    db.session.commit()
    result = process_week_results(week.id)
    for key in ('success', 'already_complete', 'processed', 'completed',
                'no_pick_penalties', 'revived', 'pool_empty',
                'graded', 'eliminated_user_ids'):
        assert key in result, key


def test_graded_list_carries_pick_tuples(app):
    week = make_week(1)
    home, away = make_team('Home U'), make_team('Away St')
    game = make_game(week, home, away, spread=-3.0, winner='home')
    winner = make_user('w')
    make_enrollment(winner)
    make_pick(winner, week, home)
    loser = make_user('l')
    make_enrollment(loser)
    make_pick(loser, week, away)
    db.session.commit()
    result = process_week_results(week.id)
    graded = {u: (g, t, ok) for (u, g, t, ok) in result['graded']}
    assert graded[winner.id] == (game.id, home.id, True)
    assert graded[loser.id] == (game.id, away.id, False)


def test_eliminated_this_run_pick_dropped_from_graded_feed(app):
    """A pick that eliminates its owner this run is filtered out of `graded`
    (the owner gets the ceremony, not a game verdict) and appears in the
    elimination diff instead."""
    week, home, away, game = _seed_one_game('home')  # home wins, away loses
    survivor = make_user('s')
    make_enrollment(survivor, lives=2)
    make_pick(survivor, week, home)
    doomed = make_user('d')
    make_enrollment(doomed, lives=1)  # one life, picks the loser -> eliminated
    make_pick(doomed, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    graded_users = {u for (u, _, _, _) in result['graded']}
    assert survivor.id in graded_users        # winner keeps the game verdict
    assert doomed.id not in graded_users       # eliminated -> ceremony only
    assert doomed.id in result['eliminated_user_ids']


def test_revived_pickers_stay_in_graded_feed(app):
    """A whole-pool wipe + DQ-1 revival flips wiped pickers back to alive;
    their losing picks are retained in `graded` (they get a game verdict, not
    the ceremony) and never appear in the elimination diff."""
    week, home, away, game = _seed_one_game('home')  # away is the loser
    u1 = make_user('r1')
    make_enrollment(u1, lives=1)
    u2 = make_user('r2')
    make_enrollment(u2, lives=1)
    make_pick(u1, week, away)
    make_pick(u2, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 2
    graded_users = {u for (u, _, _, _) in result['graded']}
    assert {u1.id, u2.id} <= graded_users            # retained despite the loss
    assert result['eliminated_user_ids'] == []        # revived -> not eliminated


def test_eliminated_diff_is_this_run_only(app):
    """A member already eliminated coming in never appears in the diff."""
    week = make_week(1)
    home, away = make_team('Home U'), make_team('Away St')
    make_game(week, home, away, spread=-3.0, winner='home')
    # Dead already, picks the loser again — must NOT re-buzz the ceremony.
    dead = make_user('dead')
    make_enrollment(dead, lives=0, eliminated=True)
    make_pick(dead, week, away)
    # Alive, picks the loser with one life left → eliminated THIS run.
    fresh = make_user('fresh')
    make_enrollment(fresh, lives=1)
    make_pick(fresh, week, away)
    # A survivor keeps the pool alive so no whole-pool wipe / DQ-1 revival fires.
    alive = make_user('alive')
    make_enrollment(alive, lives=2)
    make_pick(alive, week, home)
    db.session.commit()
    result = process_week_results(week.id)
    assert fresh.id in result['eliminated_user_ids']
    assert dead.id not in result['eliminated_user_ids']
    assert alive.id not in result['eliminated_user_ids']


# ---- push_survivor_verdicts copy + routing --------------------------------

def _seed_one_game(winner='home'):
    week = make_week(1)
    home, away = make_team('Ohio State'), make_team('Michigan')
    game = make_game(week, home, away, spread=-7.0, winner=winner)
    return week, home, away, game


def test_survive_pushes_with_tally(app):
    week, home, away, game = _seed_one_game('home')
    u = make_user('a')
    make_enrollment(u, lives=2)
    other = make_user('b')
    make_enrollment(other, lives=2)
    db.session.commit()
    result = {
        'graded': [(u.id, game.id, home.id, True),
                   (other.id, game.id, home.id, True)],
        'eliminated_user_ids': [],
    }
    with patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    calls = {c.args[0][0]: c.kwargs for c in sp.call_args_list}
    kw = calls[u.id]
    assert kw['title'] == 'Ohio State won.'
    assert kw['body'].startswith('You survive. So do 1 others.')
    assert 'remain' in kw['body']
    assert kw['tag'] == f'cfb-game-{game.id}'
    assert kw['ttl'] == 6 * 3600 and kw['urgency'] == 'high'
    assert 'app_badge' not in kw  # verdicts never badge


def test_loss_with_a_life_left(app):
    week, home, away, game = _seed_one_game('home')  # away (Michigan) lost
    # One life left after the loss, not eliminated (not in the diff).
    u = make_user('a')
    make_enrollment(u, lives=1)
    db.session.commit()
    result = {'graded': [(u.id, game.id, away.id, False)],
              'eliminated_user_ids': []}
    with patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    kw = sp.call_args.kwargs
    assert kw['title'] == 'Michigan lost.'
    assert kw['body'] == 'You lose a life. 1 left.'
    assert kw['tag'] == f'cfb-game-{game.id}'


def test_loss_that_eliminates_gets_the_ceremony_not_a_game_push(app):
    week, home, away, game = _seed_one_game('home')
    u = make_user('a')
    make_enrollment(u, lives=0, eliminated=True)
    db.session.commit()
    result = {'graded': [(u.id, game.id, away.id, False)],
              'eliminated_user_ids': [u.id]}
    with patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    assert sp.call_count == 1
    kw = sp.call_args.kwargs
    assert kw['tag'] == f'cfb-elim-{week.week_number}'
    assert kw['title'] == f'Your run ends at Week {week.week_number}.'
    assert 'remain' in kw['body']


def test_dq2_no_pick_elimination_ceremony_but_survivor_gets_nothing(app):
    """A no-pick member eliminated at completion gets the ceremony; a no-pick
    member who only loses a life (still alive) buzzes nothing."""
    week, home, away, game = _seed_one_game('home')
    doomed = make_user('doomed')
    make_enrollment(doomed, lives=1)   # -> 0, eliminated
    spared = make_user('spared')
    make_enrollment(spared, lives=2)   # -> 1, still alive
    db.session.commit()
    result = process_week_results(week.id)  # completes: one game, settled
    assert result['completed'] is True
    assert doomed.id in result['eliminated_user_ids']
    assert spared.id not in result['eliminated_user_ids']
    with patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    pushed = {c.args[0][0] for c in sp.call_args_list}
    assert doomed.id in pushed      # ceremony
    assert spared.id not in pushed  # no game, still alive → silent


def test_tally_read_failure_falls_back_to_short_body(app):
    week, home, away, game = _seed_one_game('home')
    u = make_user('a')
    make_enrollment(u, lives=2)
    db.session.commit()
    result = {'graded': [(u.id, game.id, home.id, True)],
              'eliminated_user_ids': []}
    # The tally count is the only db.session.scalar call in the helper.
    with patch('games.cfb.services.reminders.db.session.scalar',
               side_effect=RuntimeError('db hiccup')), patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    kw = sp.call_args.kwargs
    assert kw['title'] == 'Ohio State won.'
    assert kw['body'] == 'You survive.'  # tally-free fallback, still sent


def test_tally_failure_rolls_back_before_fallback_pushes(app):
    """A failed tally count poisons the session (Postgres aborts the txn);
    the handler must roll back so the fallback verdict pushes' own DB reads
    succeed rather than the first one silently returning 0."""
    week, home, away, game = _seed_one_game('home')
    u = make_user('a')
    make_enrollment(u, lives=2)
    db.session.commit()
    result = {'graded': [(u.id, game.id, home.id, True)],
              'eliminated_user_ids': []}
    with patch('games.cfb.services.reminders.db.session.scalar',
               side_effect=RuntimeError('db hiccup')), \
         patch('games.cfb.services.reminders.db.session.rollback') as rb, \
         patch(_PATH) as sp:
        push_survivor_verdicts(week, result)
    rb.assert_called_once()          # session rolled back before fallback
    assert sp.call_args.kwargs['body'] == 'You survive.'  # push still sent


def test_helper_never_raises_and_noop_on_empty(app):
    week = make_week(1)
    db.session.commit()
    with patch(_PATH) as sp:
        push_survivor_verdicts(week, {'graded': [], 'eliminated_user_ids': []})
        push_survivor_verdicts(week, {})  # missing keys → still a no-op
    sp.assert_not_called()


# ---- all three callers fire the helper ------------------------------------

def test_all_three_grading_callers_push():
    sf = Path('games/cfb/services/score_fetcher.py').read_text()
    rt = Path('games/cfb/routes.py').read_text()
    assert 'push_survivor_verdicts(week, result)' in sf
    # Both admin correction routes (admin_mark_results, admin_apply_scores).
    assert rt.count('push_survivor_verdicts(week, result)') >= 2
