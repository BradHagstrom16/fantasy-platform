"""
CFB Survivor lives-pipeline regression locks (pre-launch audit 2026-06-10).

Covers audit §8 items 1-7: outright-win grading, life decrement and
elimination, processing idempotency (Top-5 #1/#2), the DQ-1 revival rule
(whole-pool wipe only), the DQ-2 no-pick penalty, DQ-4 No Contest push
semantics, and cumulative-spread recalculation — plus the admin-route
processing guards (mark-results / apply-scores) and the
auto_process_week is_complete ordering.
"""
import pytest
from unittest.mock import Mock, patch

from app import create_app
from extensions import db
from models.user import User
from games.cfb.models import (
    CfbEnrollment, CfbTeam, CfbWeek, CfbGame, CfbPick, CfbWeekOutcome,
)
from games.cfb.services.game_logic import (
    process_week_results, calculate_cumulative_spread, get_used_team_ids,
)
from games.cfb.services.score_fetcher import ScoreFetcher
from tests._cfb_fixtures import (
    make_user, make_enrollment, make_team, make_week, make_game, make_pick,
)


@pytest.fixture()
def app():
    """App fixture: testing config + in-memory schema per test."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client bound to the app fixture."""
    return app.test_client()


def _seed_basic_week(week_number=1):
    """One week, one decided game (away team won). Returns (week, home, away)."""
    week = make_week(week_number)
    home = make_team(f'Home U {week_number}')
    away = make_team(f'Away St {week_number}')
    game = make_game(week, home, away, spread=-7.0, winner='away')
    return week, home, away, game


def _login_admin(app, client):
    """Create a platform admin and seed the session (auth_id, never str(id))."""
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    auth_id = admin.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    return admin


# ── §8.1 — outright-win grading ──────────────────────────────────────────

def test_grading_is_outright_win_not_against_spread(app):
    """Grading uses the outright result only — the spread plays no role."""
    week = make_week(1)
    home = make_team('Home U')
    away = make_team('Away St')
    # Home is a 20-point underdog but wins outright — the spread must not
    # factor into grading, only the outright result.
    make_game(week, home, away, spread=20.0, winner='home')
    home_picker = make_user('homepicker')
    e_home = make_enrollment(home_picker)
    away_picker = make_user('awaypicker')
    e_away = make_enrollment(away_picker)
    p_home = make_pick(home_picker, week, home)
    p_away = make_pick(away_picker, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['success'] is True
    assert p_home.is_correct is True
    assert e_home.lives_remaining == 2
    assert p_away.is_correct is False
    assert e_away.lives_remaining == 1


def test_away_picker_correct_when_home_loses(app):
    """An away-team picker grades correct when home_team_won is False."""
    week, home, away, _ = _seed_basic_week()
    user = make_user('p1')
    enrollment = make_enrollment(user)
    pick = make_pick(user, week, away)
    db.session.commit()

    process_week_results(week.id)

    assert pick.is_correct is True
    assert enrollment.lives_remaining == 2
    assert enrollment.is_eliminated is False


# ── §8.2 — lives decrement and elimination ───────────────────────────────

def test_two_lives_wrong_pick_loses_one_life_not_eliminated(app):
    """A wrong pick at 2 lives costs one life without elimination."""
    week, home, away, _ = _seed_basic_week()
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    make_pick(user, week, home)
    db.session.commit()

    process_week_results(week.id)

    assert enrollment.lives_remaining == 1
    assert enrollment.is_eliminated is False


def test_one_life_wrong_pick_eliminated_and_not_revived(app):
    """1 life + wrong pick = eliminated at 0. The surviving 2-life winner
    means revival must NOT fire (locks the all()-over-one-element bug)."""
    week, home, away, _ = _seed_basic_week()
    loser = make_user('loser')
    e_loser = make_enrollment(loser, lives=1)
    winner = make_user('winner')
    e_winner = make_enrollment(winner, lives=2)
    make_pick(loser, week, home)
    make_pick(winner, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert e_loser.lives_remaining == 0
    assert e_loser.is_eliminated is True
    assert result['revived'] == 0
    assert e_winner.is_eliminated is False


# ── §8.3 — idempotency (Top-5 #1/#2) ─────────────────────────────────────

def test_process_week_results_is_idempotent_across_reruns(app):
    """Re-running a completed week is a no-op (Top-5 #1 lock)."""
    week, home, away, _ = _seed_basic_week()
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    pick = make_pick(user, week, home)
    db.session.commit()

    first = process_week_results(week.id)
    second = process_week_results(week.id)

    assert first['completed'] is True
    assert week.is_complete is True
    assert second['already_complete'] is True
    assert pick.is_correct is False
    assert enrollment.lives_remaining == 1


def test_partial_processing_grades_each_pick_exactly_once(app):
    """Picks graded in a partial run are never re-graded when the week completes."""
    week = make_week(1)
    t1, t2 = make_team('T1'), make_team('T2')
    t3, t4 = make_team('T3'), make_team('T4')
    make_game(week, t1, t2, winner='away')
    game2 = make_game(week, t3, t4)  # undecided
    u1 = make_user('p1')
    e1 = make_enrollment(u1, lives=2)
    u2 = make_user('p2')
    e2 = make_enrollment(u2, lives=2)
    make_pick(u1, week, t1)
    p2 = make_pick(u2, week, t3)
    db.session.commit()

    first = process_week_results(week.id)
    assert e1.lives_remaining == 1
    assert p2.is_correct is None
    assert first['completed'] is False
    assert week.is_complete is False

    game2.home_team_won = True
    db.session.commit()
    process_week_results(week.id)

    assert e1.lives_remaining == 1  # not decremented again
    assert p2.is_correct is True
    assert week.is_complete is True


def test_pick_on_undecided_game_is_untouched(app):
    """An undecided game leaves the pick ungraded and lives unchanged."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    make_game(week, home, away)  # undecided
    user = make_user('p1')
    enrollment = make_enrollment(user)
    pick = make_pick(user, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert pick.is_correct is None
    assert enrollment.lives_remaining == 2
    assert result['completed'] is False
    assert week.is_complete is False


def test_week_with_no_games_is_never_completed(app):
    """A 0-game week (orphan-week shape, audit §5.2) must not complete —
    completing it would no-pick-penalize every active player."""
    week = make_week(1)
    user = make_user('p1')
    enrollment = make_enrollment(user)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['completed'] is False
    assert result['no_pick_penalties'] == 0
    assert enrollment.lives_remaining == 2
    assert week.is_complete is False


# ── §8.4 — revival per DQ-1 ──────────────────────────────────────────────

def test_revival_fires_on_whole_pool_wipe(app):
    """A whole-pool wipe of pickers revives every wiped picker (DQ-1)."""
    week, home, away, _ = _seed_basic_week()
    u1 = make_user('p1')
    e1 = make_enrollment(u1, lives=1)
    u2 = make_user('p2')
    e2 = make_enrollment(u2, lives=1)
    make_pick(u1, week, home)
    make_pick(u2, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 2
    for e in (e1, e2):
        assert e.lives_remaining == 1
        assert e.is_eliminated is False
    assert week.is_complete is True


def test_no_revival_when_two_life_loser_remains_active(app):
    """Dana (2 lives) and Eve (1 life) both lose: Dana survives at 1 life,
    Eve stays eliminated — no revival (audit §2 concrete failure case)."""
    week, home, away, _ = _seed_basic_week()
    dana = make_user('dana')
    e_dana = make_enrollment(dana, lives=2)
    eve = make_user('eve')
    e_eve = make_enrollment(eve, lives=1)
    make_pick(dana, week, home)
    make_pick(eve, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 0
    assert e_dana.lives_remaining == 1
    assert e_dana.is_eliminated is False
    assert e_eve.lives_remaining == 0
    assert e_eve.is_eliminated is True


def test_no_revival_when_a_player_wins(app):
    """Alice (2 lives) wins; Bob and Carol (1 life) lose — both stay
    eliminated (audit §2 concrete failure case)."""
    week, home, away, _ = _seed_basic_week()
    alice = make_user('alice')
    e_alice = make_enrollment(alice, lives=2)
    e_by_user = {}
    for name in ('bob', 'carol'):
        u = make_user(name)
        e_by_user[name] = make_enrollment(u, lives=1)
        make_pick(u, week, home)
    make_pick(alice, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 0
    assert e_alice.lives_remaining == 2
    for name in ('bob', 'carol'):
        assert e_by_user[name].is_eliminated is True


def test_lone_last_player_losing_is_not_revived(app):
    """A lone remaining player who loses is not revived (DQ-1: no revival
    keeps a lone player alive) — the empty pool is surfaced to the admin."""
    week, home, away, _ = _seed_basic_week()
    user = make_user('lone')
    enrollment = make_enrollment(user, lives=1)
    make_pick(user, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 0
    assert result['pool_empty'] is True
    assert enrollment.is_eliminated is True


def test_revival_excludes_no_pick_eliminations(app):
    """On a wipe, only players who picked are revived — no-pick
    eliminations stay dead (DQ-1 + DQ-2)."""
    week, home, away, _ = _seed_basic_week()
    picker = make_user('picker')
    e_picker = make_enrollment(picker, lives=1)
    sleeper = make_user('sleeper')
    e_sleeper = make_enrollment(sleeper, lives=1)
    make_pick(picker, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 1
    assert e_picker.lives_remaining == 1
    assert e_picker.is_eliminated is False
    assert e_sleeper.lives_remaining == 0
    assert e_sleeper.is_eliminated is True


def test_wipe_of_only_no_pick_players_reports_empty_pool(app):
    """DQ-1 edge: a wipe made entirely of no-pick eliminations leaves
    nobody eligible to revive — surfaced via pool_empty, not silent."""
    week, home, away, _ = _seed_basic_week()
    for name in ('s1', 's2'):
        make_enrollment(make_user(name), lives=1)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 0
    assert result['pool_empty'] is True
    enrollments = CfbEnrollment.query.all()
    assert all(e.is_eliminated for e in enrollments)


def test_revival_deferred_until_all_games_settled(app):
    """Revival is evaluated only when every game has a result (DQ-1) —
    and the eliminated-this-week set survives across partial runs."""
    week = make_week(1)
    t1, t2 = make_team('T1'), make_team('T2')
    t3, t4 = make_team('T3'), make_team('T4')
    make_game(week, t1, t2, winner='away')
    game2 = make_game(week, t3, t4)  # undecided
    e_by_name = {}
    for name in ('p1', 'p2'):
        u = make_user(name)
        e_by_name[name] = make_enrollment(u, lives=1)
        make_pick(u, week, t1)
    db.session.commit()

    first = process_week_results(week.id)
    assert first['revived'] == 0
    assert first['completed'] is False
    assert all(e.is_eliminated for e in e_by_name.values())

    game2.home_team_won = True
    db.session.commit()
    second = process_week_results(week.id)

    assert second['revived'] == 2
    for e in e_by_name.values():
        assert e.lives_remaining == 1
        assert e.is_eliminated is False


# ── §8.5 — no-pick penalty per DQ-2 ──────────────────────────────────────

def test_active_no_pick_player_loses_life_when_week_completes(app):
    """An active player with no pick loses a life at completion (DQ-2)."""
    week, home, away, _ = _seed_basic_week()
    sleeper = make_user('sleeper')
    e_sleeper = make_enrollment(sleeper, lives=2)
    picker = make_user('picker')
    make_enrollment(picker, lives=2)
    make_pick(picker, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['no_pick_penalties'] == 1
    assert e_sleeper.lives_remaining == 1
    assert e_sleeper.is_eliminated is False


def test_no_pick_at_one_life_is_eliminated_not_revived(app):
    """A no-pick at 1 life eliminates; a surviving picker blocks revival."""
    week, home, away, _ = _seed_basic_week()
    sleeper = make_user('sleeper')
    e_sleeper = make_enrollment(sleeper, lives=1)
    picker = make_user('picker')
    e_picker = make_enrollment(picker, lives=2)
    make_pick(picker, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert e_sleeper.lives_remaining == 0
    assert e_sleeper.is_eliminated is True
    assert result['revived'] == 0
    assert e_picker.is_eliminated is False


def test_already_eliminated_players_are_not_penalized(app):
    """Players eliminated in earlier weeks take no further no-pick penalty."""
    week, home, away, _ = _seed_basic_week()
    ghost = make_user('ghost')
    e_ghost = make_enrollment(ghost, lives=0, eliminated=True)
    picker = make_user('picker')
    make_enrollment(picker, lives=2)
    make_pick(picker, week, away)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['no_pick_penalties'] == 0
    assert e_ghost.lives_remaining == 0
    assert e_ghost.is_eliminated is True


def test_no_pick_penalty_deferred_until_completion_and_applied_once(app):
    """The no-pick penalty waits for completion and never reapplies."""
    week = make_week(1)
    t1, t2 = make_team('T1'), make_team('T2')
    game = make_game(week, t1, t2)  # undecided
    sleeper = make_user('sleeper')
    e_sleeper = make_enrollment(sleeper, lives=2)
    picker = make_user('picker')
    make_enrollment(picker, lives=2)
    make_pick(picker, week, t2)
    db.session.commit()

    process_week_results(week.id)
    assert e_sleeper.lives_remaining == 2  # deferred while games pending

    game.home_team_won = False
    db.session.commit()
    process_week_results(week.id)
    assert e_sleeper.lives_remaining == 1

    process_week_results(week.id)
    assert e_sleeper.lives_remaining == 1  # already_complete short-circuit


# ── §8.6 — No Contest per DQ-4 ───────────────────────────────────────────

def test_no_contest_pick_is_push_with_no_life_loss(app):
    """A No Contest pick pushes: ungraded, no life loss, week still completes."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    make_game(week, home, away, no_contest=True)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=1)
    pick = make_pick(user, week, home)
    db.session.commit()

    result = process_week_results(week.id)

    assert pick.is_correct is None
    assert enrollment.lives_remaining == 1
    assert enrollment.is_eliminated is False
    assert result['completed'] is True  # no-contest counts as settled
    assert week.is_complete is True


def test_no_contest_player_counts_as_survivor_for_revival(app):
    """A no-contest push counts as survived — it suppresses revival for
    others who lost (DQ-4)."""
    week = make_week(1)
    t1, t2 = make_team('T1'), make_team('T2')
    t3, t4 = make_team('T3'), make_team('T4')
    make_game(week, t1, t2, no_contest=True)
    make_game(week, t3, t4, winner='away')
    pusher = make_user('pusher')
    e_pusher = make_enrollment(pusher, lives=1)
    loser = make_user('loser')
    e_loser = make_enrollment(loser, lives=1)
    make_pick(pusher, week, t1)
    make_pick(loser, week, t3)
    db.session.commit()

    result = process_week_results(week.id)

    assert result['revived'] == 0
    assert e_pusher.is_eliminated is False
    assert e_loser.is_eliminated is True


def test_no_contest_team_remains_used(app):
    """The push consumes the team (DQ-4) — it stays in the used pool."""
    week1 = make_week(1)
    week2 = make_week(2)
    home, away = make_team('T1'), make_team('T2')
    make_game(week1, home, away, no_contest=True)
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, week1, home)
    db.session.commit()

    used = get_used_team_ids(user.id, week2)

    assert home.id in used


def test_no_contest_game_excluded_from_cumulative_spread(app):
    """No Contest games contribute nothing to the cumulative-spread tiebreaker."""
    week1 = make_week(1)
    week2 = make_week(2)
    t1, t2 = make_team('T1'), make_team('T2')
    t3, t4 = make_team('T3'), make_team('T4')
    make_game(week1, t1, t2, spread=-7.0, winner='home')
    make_game(week2, t3, t4, spread=-3.0, no_contest=True)
    user = make_user('p1')
    enrollment = make_enrollment(user)
    make_pick(user, week1, t1)
    make_pick(user, week2, t3)
    db.session.commit()

    calculate_cumulative_spread(enrollment)

    assert enrollment.cumulative_spread == -7.0


# ── §8.7 — cumulative spread recalculation ───────────────────────────────

def test_cumulative_spread_recalculated_not_accumulated(app):
    """Processing replaces the stored cumulative spread, never adds to it."""
    week, home, away, _ = _seed_basic_week()
    user = make_user('p1')
    enrollment = make_enrollment(user)
    enrollment.cumulative_spread = 99.0  # stale value must be replaced
    make_pick(user, week, away)
    db.session.commit()

    process_week_results(week.id)

    assert enrollment.cumulative_spread == 7.0  # away side of -7.0 home spread


# ── Admin route guards (Top-5 #2 + DQ-4 surfaces) ────────────────────────

def test_mark_results_completes_week_and_blocks_reruns(app, client):
    """mark-results completes the week via the engine and rejects resubmits."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    make_pick(user, week, home)
    _login_admin(app, client)

    resp = client.post(
        f'/cfb/admin/week/{week.id}/mark-results',
        data={f'game_{game.id}': 'away', 'csrf_token': 'x'},
    )
    assert resp.status_code == 302
    assert week.is_complete is True
    assert enrollment.lives_remaining == 1

    # Re-submitting must not decrement again (Top-5 #2 / scores-cron path)
    client.post(
        f'/cfb/admin/week/{week.id}/mark-results',
        data={f'game_{game.id}': 'away', 'csrf_token': 'x'},
    )
    assert enrollment.lives_remaining == 1


def test_apply_scores_double_post_decrements_once(app, client):
    """A double-POST of apply-scores decrements lives exactly once."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    make_pick(user, week, home)
    _login_admin(app, client)

    data = {
        f'winner_{game.id}': 'away',
        f'home_score_{game.id}': '10',
        f'away_score_{game.id}': '20',
        'csrf_token': 'x',
    }
    client.post(f'/cfb/admin/week/{week.id}/apply-scores', data=data)
    assert week.is_complete is True
    assert enrollment.lives_remaining == 1

    client.post(f'/cfb/admin/week/{week.id}/apply-scores', data=data)
    assert enrollment.lives_remaining == 1


def test_mark_results_accepts_no_contest(app, client):
    """mark-results persists a No Contest ruling with push semantics."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    pick = make_pick(user, week, home)
    _login_admin(app, client)

    client.post(
        f'/cfb/admin/week/{week.id}/mark-results',
        data={f'game_{game.id}': 'no_contest', 'csrf_token': 'x'},
    )

    assert game.is_no_contest is True
    assert game.home_team_won is None
    assert pick.is_correct is None
    assert enrollment.lives_remaining == 2
    assert week.is_complete is True


def test_apply_scores_accepts_no_contest(app, client):
    """apply-scores persists a No Contest ruling with push semantics."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    make_pick(user, week, home)
    _login_admin(app, client)

    client.post(
        f'/cfb/admin/week/{week.id}/apply-scores',
        data={f'winner_{game.id}': 'no_contest', 'csrf_token': 'x'},
    )

    assert game.is_no_contest is True
    assert game.home_team_won is None
    assert enrollment.lives_remaining == 2
    assert week.is_complete is True


def test_admin_surfaces_offer_no_contest_option(app, client):
    """Mark-results offers a No Contest radio for every game."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    make_game(week, home, away)
    db.session.commit()
    _login_admin(app, client)

    resp = client.get(f'/cfb/admin/week/{week.id}/mark-results')
    assert b'no_contest' in resp.data


def test_review_scores_preselects_persisted_no_contest(app, client):
    """A stored No Contest ruling stays selected on review-scores — a blind
    resubmit must not overturn it with a score-derived winner default."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    make_game(week, home, away, no_contest=True)
    db.session.commit()
    _login_admin(app, client)

    api_event = {
        'id': 'evt9', 'home_team': 'T1', 'away_team': 'T2',
        'completed': True,
        'scores': [{'name': 'T1', 'score': '10'},
                   {'name': 'T2', 'score': '20'}],
    }
    fake_resp = Mock(status_code=200, headers={})
    fake_resp.json.return_value = [api_event]

    with patch('games.cfb.services.score_fetcher.requests.get',
               return_value=fake_resp):
        resp = client.get(f'/cfb/admin/week/{week.id}/fetch-scores')

    html = resp.data.decode()
    assert 'value="no_contest" selected' in html
    # The score-derived default (away won 20-10) must be suppressed
    assert 'value="away" selected' not in html


# ── auto_process_week is_complete ordering (engine owns the flag) ────────

def _fake_fetch(game):
    """Canned fetch_scores_for_week payload: one completed 10-20 game."""
    return {
        'matched_completed': [{
            'game_id': game.id,
            'home_team': 'T1', 'away_team': 'T2',
            'home_score': 10, 'away_score': 20,
            'match_method': 'event_id', 'api_event_id': 'evt1',
        }],
        'matched_in_progress': [],
        'unmatched': [],
        'api_credits_remaining': None,
        'error': None,
    }


def test_auto_process_week_completes_via_engine(app):
    """auto_process_week completes a settled week through the engine."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    user = make_user('p1')
    enrollment = make_enrollment(user, lives=2)
    make_pick(user, week, home)
    db.session.commit()

    with patch.object(ScoreFetcher, 'fetch_scores_for_week',
                      return_value=_fake_fetch(game)):
        result = ScoreFetcher().auto_process_week(week.id)

    assert result['status'] == 'completed'
    assert week.is_complete is True
    assert enrollment.lives_remaining == 1


def test_auto_process_week_partial_when_engine_declines_completion(app):
    """Engine success without completion (raced worker / 0-game edge) must
    report 'partial', never 'completed'."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    db.session.commit()

    with patch.object(ScoreFetcher, 'fetch_scores_for_week',
                      return_value=_fake_fetch(game)), \
         patch('games.cfb.services.score_fetcher.process_week_results',
               return_value={'success': True, 'completed': False}):
        result = ScoreFetcher().auto_process_week(week.id)

    assert result['status'] == 'partial'
    assert week.is_complete is False


def test_auto_process_week_failure_does_not_strand_week_complete(app):
    """§8.16 ordering lock: a failed processing run must leave
    is_complete False so the week can be retried."""
    week = make_week(1)
    home, away = make_team('T1'), make_team('T2')
    game = make_game(week, home, away)
    db.session.commit()

    with patch.object(ScoreFetcher, 'fetch_scores_for_week',
                      return_value=_fake_fetch(game)), \
         patch('games.cfb.services.score_fetcher.process_week_results',
               return_value={'success': False, 'error': 'boom'}):
        result = ScoreFetcher().auto_process_week(week.id)

    assert result['status'] == 'error'
    assert week.is_complete is False


# ── CfbWeekOutcome snapshot (§8.19 SSoT for per-week lives display) ───────

def test_completing_run_writes_outcome_rows_for_every_enrollment(app):
    """The run that completes a week snapshots every season enrollment —
    winner, life-loser, and prior-week eliminations alike."""
    week, home, away, _ = _seed_basic_week()  # away team won
    winner = make_user('winner')
    make_enrollment(winner)
    loser = make_user('loser')
    make_enrollment(loser)
    prior_out = make_user('priorout')
    make_enrollment(prior_out, lives=0, eliminated=True)
    make_pick(winner, week, away)
    make_pick(loser, week, home)
    db.session.commit()

    process_week_results(week.id)

    outcomes = {
        o.user_id: o
        for o in CfbWeekOutcome.query.filter_by(week_id=week.id).all()
    }
    assert len(outcomes) == 3
    w = outcomes[winner.id]
    assert (w.lives_remaining, w.lost_life, w.is_eliminated) == (2, False, False)
    l = outcomes[loser.id]
    assert (l.lives_remaining, l.lost_life, l.is_eliminated) == (1, True, False)
    p = outcomes[prior_out.id]
    assert (p.lives_remaining, p.is_eliminated, p.lost_life, p.no_pick) == (
        0, True, False, False)
    assert p.eliminated_this_week is False


def test_no_pick_penalty_recorded_in_outcome(app):
    """A DQ-2 no-pick life loss is flagged no_pick + lost_life."""
    week, home, away, _ = _seed_basic_week()
    picker = make_user('picker')
    make_enrollment(picker)
    nopick = make_user('nopick')
    make_enrollment(nopick)
    make_pick(picker, week, away)
    db.session.commit()

    process_week_results(week.id)

    o = CfbWeekOutcome.query.filter_by(
        week_id=week.id, user_id=nopick.id).first()
    assert o is not None
    assert o.no_pick is True
    assert o.lost_life is True
    assert o.lives_remaining == 1
    assert o.eliminated_this_week is False


def test_no_pick_elimination_flagged_eliminated_this_week(app):
    """A no-pick loss at 1 life is an elimination attributable to this
    week — the recap and weekly_results depend on this derivation."""
    week, home, away, _ = _seed_basic_week()
    picker = make_user('picker')
    make_enrollment(picker)
    nopick = make_user('nopick')
    make_enrollment(nopick, lives=1)
    make_pick(picker, week, away)
    db.session.commit()

    process_week_results(week.id)

    o = CfbWeekOutcome.query.filter_by(
        week_id=week.id, user_id=nopick.id).first()
    assert o.eliminated_this_week is True
    assert o.no_pick is True
    assert o.lives_remaining == 0


def test_revival_recorded_in_outcome_snapshot(app):
    """Outcome rows capture post-revival state: revived players show
    revived=True, 1 life, not eliminated."""
    week, home, away, _ = _seed_basic_week()  # away won; both pick home
    for name in ('p1', 'p2'):
        u = make_user(name)
        make_enrollment(u, lives=1)
        make_pick(u, week, home)
    db.session.commit()

    process_week_results(week.id)

    outcomes = CfbWeekOutcome.query.filter_by(week_id=week.id).all()
    assert len(outcomes) == 2
    for o in outcomes:
        assert o.revived is True
        assert o.lives_remaining == 1
        assert o.is_eliminated is False
        assert o.lost_life is True
        assert o.eliminated_this_week is False


def test_outcomes_not_written_until_week_completes(app):
    """Partial runs (undecided games) write no snapshot rows."""
    week = make_week(1)
    home, away = make_team('H'), make_team('A')
    make_game(week, home, away, spread=-3.0, winner=None)
    u = make_user('p1')
    make_enrollment(u)
    make_pick(u, week, home)
    db.session.commit()

    process_week_results(week.id)

    assert CfbWeekOutcome.query.filter_by(week_id=week.id).count() == 0


def test_outcomes_not_duplicated_on_rerun(app):
    """Re-running a completed week leaves exactly one row per enrollment."""
    week, home, away, _ = _seed_basic_week()
    u = make_user('p1')
    make_enrollment(u)
    make_pick(u, week, away)
    db.session.commit()

    process_week_results(week.id)
    process_week_results(week.id)

    assert CfbWeekOutcome.query.filter_by(week_id=week.id).count() == 1
