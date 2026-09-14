"""The Docket — per-side verdict pushes (PR 4).

Locks the verdict-games sync_scores now threads through _apply_event (flipped
∪ corrected, gated so an unchanged final game does no grading reads), the
before/after capture, the clerk's copy push_docket_verdicts sends, the
cosmetic-edit silence, and that all three score callers fire the helper.
send_push is patched; nothing here needs VAPID.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from extensions import db
from games.docket.models import DocketPick
from games.docket.services.notifications import push_docket_verdicts
from games.docket.services.scores import sync_scores
from tests._docket_fixtures import (
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

_PATH = 'games.docket.services.notifications.send_push'
# Home favored by 3.5, total 51.5 (make_game defaults). Naive UTC kickoff.
_KICKOFF = datetime(2026, 9, 6, 16, 0)


def _pick(user, week, game, market, side, slot, line):
    p = DocketPick(user_id=user.id, week_id=week.id, game_id=game.id,
                   market=market, side=side, slot=slot, line_value=line,
                   book='draftkings')
    db.session.add(p)
    db.session.flush()
    return p


def _event(game, home_score, away_score, completed=True):
    return {
        'id': game.api_event_id,
        'home_team': game.home_team,
        'away_team': game.away_team,
        'completed': completed,
        'scores': [{'name': game.home_team, 'score': home_score},
                   {'name': game.away_team, 'score': away_score}],
    }


def _sync(game, home_score, away_score, completed=True):
    events = {game.sport: [_event(game, home_score, away_score, completed)]}
    return sync_scores(game.week.week_number, events_by_sport=events)


# ---- sync_scores verdict-games threading ---------------------------------

def test_flip_to_final_yields_a_flipped_verdict(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    db.session.commit()
    summary = _sync(game, 24, 14)  # completed -> flips final
    assert summary['finalized'] == 1  # existing count intact
    verdicts = summary['verdict_games']
    assert len(verdicts) == 1
    assert verdicts[0] == {'game_id': game.id, 'kind': 'flipped', 'before': None}


def test_already_final_unchanged_yields_no_verdict(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    db.session.commit()
    _sync(game, 24, 14)                       # flip
    summary = _sync(game, 24, 14)             # same scores, still completed
    assert summary['already_final'] == 1
    assert summary['scores_written'] == 0     # nothing changed
    assert summary['verdict_games'] == []     # no capture, no push


def test_already_final_changed_yields_a_corrected_verdict(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    home = make_user('h')
    make_enrollment(home)
    _pick(home, week, game, 'spread', 'home', 1, -3.5)
    db.session.commit()
    _sync(game, 24, 14)                       # flip: home wins by 10
    summary = _sync(game, 24, 30)             # correction: away now wins
    assert summary['already_final'] == 1
    assert summary['scores_written'] == 1
    verdicts = summary['verdict_games']
    assert len(verdicts) == 1
    assert verdicts[0]['kind'] == 'corrected'
    # before-results captured from the OLD (home-winning) scores.
    assert verdicts[0]['before']  # non-empty {pick_id: result}


def test_correction_with_completed_cleared_still_yields_a_verdict(app):
    # is_final is one-way: a final game whose corrected scores arrive on an
    # in-progress payload still re-grades, so the flip must be buzzed.
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    home = make_user('h')
    make_enrollment(home)
    _pick(home, week, game, 'spread', 'home', 1, -3.5)
    db.session.commit()
    _sync(game, 24, 14)                                 # flip: home wins by 10
    summary = _sync(game, 24, 30, completed=False)      # away now wins, live
    assert game.is_final is True                        # one-way latch holds
    assert summary['scores_written'] == 1
    verdicts = summary['verdict_games']
    assert len(verdicts) == 1
    assert verdicts[0]['kind'] == 'corrected'
    assert verdicts[0]['before']


# ---- push_docket_verdicts copy + routing ----------------------------------

def test_flip_pushes_every_scoring_side_with_the_tally(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    # home 24, away 14 -> home covers -3.5 (WIN), total 38 < 51.5 (Under WIN)
    a = make_user('a')
    make_enrollment(a)
    b = make_user('b')
    make_enrollment(b)
    _pick(a, week, game, 'spread', 'home', 1, -3.5)   # WIN
    _pick(b, week, game, 'spread', 'home', 1, -3.5)   # WIN (2 sheets had them)
    _pick(a, week, game, 'total', 'under', 2, 51.5)   # WIN (1 sheet)
    game.home_score, game.away_score, game.is_final = 24, 14, True
    db.session.commit()
    with patch(_PATH) as sp:
        push_docket_verdicts([{'game_id': game.id, 'kind': 'flipped', 'before': None}])
    calls = [c.kwargs for c in sp.call_args_list]
    assert len(calls) == 3
    home_calls = [c for c in calls if c['title'].startswith('Home Team')]
    assert all(c['title'].endswith('WIN.') for c in home_calls)
    assert any('2 sheets had them' in c['body'] for c in home_calls)
    under = [c for c in calls if c['title'].startswith('Under')][0]
    assert under['title'] == 'Under 51.5: WIN.'
    assert under['body'] == '1 sheet had them.'
    # One distinct tag per market so both verdicts survive on a device that
    # holds this game's spread and its total.
    assert {c['tag'] for c in calls} == {
        f'docket-game-{game.id}-spread', f'docket-game-{game.id}-total'}
    assert all(c['urgency'] == 'high' and 'app_badge' not in c for c in calls)


def test_corrected_pushes_only_the_sides_that_flip(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    flipper = make_user('f')
    make_enrollment(flipper)
    steady = make_user('s')
    make_enrollment(steady)
    ph = _pick(flipper, week, game, 'spread', 'home', 1, -3.5)
    pu = _pick(steady, week, game, 'total', 'under', 1, 51.5)
    # After the correction: home wins by only 2 (spread LOSS), total 46 (Under WIN).
    game.home_score, game.away_score, game.is_final = 24, 22, True
    db.session.commit()
    # before: home spread was WIN (flips to LOSS -> push); under was WIN (stays -> silent)
    before = {ph.id: 'win', pu.id: 'win'}
    with patch(_PATH) as sp:
        push_docket_verdicts([{'game_id': game.id, 'kind': 'corrected', 'before': before}])
    assert sp.call_count == 1
    assert sp.call_args.args[0] == [flipper.id]  # only the flipped side's owner
    kw = sp.call_args.kwargs
    assert kw['title'].startswith('Home Team') and kw['title'].endswith('LOSS.')


def test_cosmetic_score_edit_pushes_nothing(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)
    u = make_user('u')
    make_enrollment(u)
    p = _pick(u, week, game, 'spread', 'home', 1, -3.5)
    game.home_score, game.away_score, game.is_final = 24, 14, True  # home WIN
    db.session.commit()
    before = {p.id: 'win'}  # unchanged after
    with patch(_PATH) as sp:
        push_docket_verdicts([{'game_id': game.id, 'kind': 'corrected', 'before': before}])
    sp.assert_not_called()


def test_nonfinal_game_pushes_nothing(app):
    week = make_week(1)
    game = make_game(week, kickoff=_KICKOFF)  # not final
    u = make_user('u')
    make_enrollment(u)
    _pick(u, week, game, 'spread', 'home', 1, -3.5)
    db.session.commit()
    with patch(_PATH) as sp:
        push_docket_verdicts([{'game_id': game.id, 'kind': 'flipped', 'before': None}])
    sp.assert_not_called()


def test_helper_never_raises_on_empty_or_bad_entry(app):
    with patch(_PATH) as sp:
        push_docket_verdicts([])
        push_docket_verdicts([{'game_id': 999999, 'kind': 'flipped'}])
    sp.assert_not_called()


# ---- all three callers fire the helper ------------------------------------

def test_three_score_callers_push():
    gd = Path('games/docket/services/gameday.py').read_text()
    cli = Path('games/docket/cli.py').read_text()
    assert 'push_docket_verdicts(' in gd
    # current-week _run_scores AND _catch_up_previous_week.
    assert cli.count('push_docket_verdicts(') >= 2
