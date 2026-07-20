"""CFB lounge resolver + context builders (C2 slice 3, transition plan Phase 4).

Locks the C1 design spec's state table (spec section 2.1) and the out/pre
data contract (section 9) for the flip-minimum slice:

- ``cfb_lounge_state()`` resolves 'pre' | 'live' | 'post' from CFB data.
- ``build_lounge_context`` assembles the out + pre contexts; live and post
  raise NotImplementedError until their slices ship (Phase 4 PRs B/C) --
  failing visibly beats a half-rendered lounge if the changeover flip ever
  outran the remaining slices.
- The generalized ``_game_tiles_compact.html`` renders from lounge context
  (featured entry + per-state label + archived tiles) with no slug logic,
  and the WC lounge keeps rendering its exact pre-flip labels.

All CFB lounge code is dead on prod until the Phase 5 registry flip: CFB
stays coming_soon/unfeatured, so ``lounge_game()`` never selects it. Tests
simulate the changeover with the same monkeypatch helpers as
tests/test_registry_seam.py.
"""
import os
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models.user import User
from tests._registry_helpers import set_is_featured, set_status

# Tuesday 2026-08-18 noon CT (17:00 UTC): the handoff-window anchor.
# Kickoff (Thu Sep 3) is 16 days out; the week-1 deadline (Sat Sep 5,
# 11:00 AM CT) is 17 full days out.
PRE_ANCHOR = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-08-18T17:00:00'}

SEASON_YEAR = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_user(username='loungeuser'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def _enroll_cfb(user, lives=2, eliminated=False):
    from games.cfb.models import CfbEnrollment
    e = CfbEnrollment(
        user_id=user.id, season_year=SEASON_YEAR,
        lives_remaining=lives, is_eliminated=eliminated,
    )
    db.session.add(e)
    db.session.commit()
    return e


def _seed_cfb_field(spec):
    """Create one user + enrollment per (lives, eliminated) tuple."""
    enrollments = []
    for i, (lives, eliminated) in enumerate(spec):
        user = _make_user(username=f'fielduser{i}')
        enrollments.append(_enroll_cfb(user, lives=lives, eliminated=eliminated))
    return enrollments


def _make_week(number=1, active=False, complete=False, playoff=False,
               deadline=None):
    from games.cfb.models import CfbWeek
    w = CfbWeek(
        week_number=number,
        start_date=datetime(2026, 9, 3, 0, 0),
        deadline=deadline or datetime(2026, 9, 5, 11, 0),
        is_active=active, is_complete=complete, is_playoff_week=playoff,
    )
    db.session.add(w)
    db.session.commit()
    return w


def _seed_wc_archive(viewer_user=None):
    """Minimal frozen 2026 WC archive: final match, champion, standings.

    Standings fiction: The Commish 487.0, viewer 250.0 (if given), a
    third player 100.0 -- viewer finishes 2nd of 3.
    """
    from games.worldcup.models import (
        WorldCupEnrollment,
        WorldCupMatch,
        WorldCupTeam,
    )
    esp = WorldCupTeam(fifa_code='ESP', name='Spain', display_name='Spain',
                       tier=1, multiplier=1.0, confederation='UEFA',
                       group_letter='A')
    fra = WorldCupTeam(fifa_code='FRA', name='France', display_name='France',
                       tier=1, multiplier=1.0, confederation='UEFA',
                       group_letter='B')
    db.session.add_all([esp, fra])
    db.session.commit()
    db.session.add(WorldCupMatch(
        match_number=104, stage='final',
        home_team_id=esp.id, away_team_id=fra.id,
        home_score=2, away_score=1, winner_team_id=esp.id,
        is_completed=True,
    ))
    commish = _make_user(username='wc_commish')
    third = _make_user(username='wc_third')
    db.session.add(WorldCupEnrollment(
        user_id=commish.id, season_year=SEASON_YEAR,
        total_score=487.0, display_name='The Commish',
    ))
    if viewer_user is not None:
        db.session.add(WorldCupEnrollment(
            user_id=viewer_user.id, season_year=SEASON_YEAR,
            total_score=250.0,
        ))
    db.session.add(WorldCupEnrollment(
        user_id=third.id, season_year=SEASON_YEAR, total_score=100.0,
    ))
    db.session.commit()


def _flip_to_cfb(monkeypatch):
    """Simulate the Phase 5 atomic changeover against the real registry."""
    set_status(monkeypatch, 'worldcup', 'completed')
    set_is_featured(monkeypatch, 'worldcup', False)
    set_status(monkeypatch, 'cfb', 'open')
    set_is_featured(monkeypatch, 'cfb', True)


# == cfb_lounge_state() -- the C1 section 2.1 state table ==================

def test_state_pre_with_no_cfb_data(app):
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        assert cfb_lounge_state() == 'pre'


def test_state_pre_when_week_rows_exist_but_none_started(app):
    """Week 1 created by setup but not yet activated: picks are not open."""
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=1, active=False, complete=False)
        _seed_cfb_field([(2, False), (2, False)])
        assert cfb_lounge_state() == 'pre'


def test_state_live_when_a_week_is_active(app):
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=1, active=True)
        _seed_cfb_field([(2, False), (2, False)])
        assert cfb_lounge_state() == 'live'


def test_state_live_in_aftermath_window(app):
    """No active week but a completed one: the verdict window is live."""
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=1, active=False, complete=True)
        _seed_cfb_field([(2, False), (1, False)])
        assert cfb_lounge_state() == 'live'


def test_state_live_with_eliminations_but_multiple_active(app):
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=8, active=True)
        _seed_cfb_field([(2, False), (1, False), (0, True), (0, True)])
        assert cfb_lounge_state() == 'live'


def test_state_post_on_sole_survivor(app):
    """A sole survivor ends the season immediately, even mid-week."""
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=9, active=True)
        _seed_cfb_field([(1, False), (0, True), (0, True)])
        assert cfb_lounge_state() == 'post'


def test_state_post_on_final_week_tiebreak_conclusion(app):
    """Final playoff week complete with more than one active player:
    the season concluded by cumulative-spread tiebreak."""
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=19, complete=True, playoff=True)
        _seed_cfb_field([(1, False), (1, False), (0, True)])
        assert cfb_lounge_state() == 'post'


def test_state_live_when_final_week_not_yet_complete(app):
    from games.cfb.services.lounge import cfb_lounge_state
    with app.app_context():
        _make_week(number=19, active=True, playoff=True)
        _seed_cfb_field([(1, False), (1, False), (0, True)])
        assert cfb_lounge_state() == 'live'


# == build_lounge_context -- out ===========================================

def test_context_out_counts_cfb_enrollments(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        _seed_cfb_field([(2, False), (2, False)])
        ctx = build_lounge_context(None, None)
    assert ctx['total_enrolled'] == 2


# == build_lounge_context -- pre ===========================================

def test_context_pre_core_keys_unenrolled(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        _seed_cfb_field([(2, False), (2, False)])
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['is_enrolled'] is False
    assert ctx['enrollment'] is None
    assert ctx['display_name'] == 'loungeuser'
    assert ctx['total_enrolled'] == 2
    assert ctx['game_tile_label'] == 'PRESEASON · SEP 3'
    assert ctx['archived_tiles'] == []
    assert ctx['farewell'] is None


def test_context_pre_enrolled_viewer(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        enrollment = _enroll_cfb(user)
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
        assert ctx['is_enrolled'] is True
        assert ctx['enrollment'].id == enrollment.id


def test_context_pre_court_line(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        _seed_cfb_field([(2, False), (2, False)])
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['court_line'] == 'Tuesday · 2 enrolled · first kickoff in 16 days'


def test_context_pre_decree_uses_week1_db_deadline(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        _make_week(number=1, active=False, complete=False,
                   deadline=datetime(2026, 9, 5, 11, 0))
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['decree_days'] == 17
    assert ctx['decree_deadline_line'] == (
        'Week 1 locks Saturday, Sep 5, 11:00 AM CT.'
    )


def test_context_pre_decree_falls_back_to_week_1_start(app):
    """No week rows yet: the decree counts to the WEEK_1_START constant
    with first-kickoff copy (C1 section 3.6)."""
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['decree_days'] == 16
    assert ctx['decree_deadline_line'] == 'First kickoff Thursday, Sep 3.'


def test_context_pre_farewell_from_frozen_wc_data(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        _seed_wc_archive(viewer_user=user)
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['farewell']['line'] == (
        'Spain took the Cup. The Commish took the pool.'
    )
    assert ctx['farewell']['finish'] == 'You finished 2nd of 3 · 250.0 pts'
    assert len(ctx['archived_tiles']) == 1
    assert ctx['archived_tiles'][0]['label'] == '2026 · ESP Won · You 2nd'
    assert ctx['archived_tiles'][0]['endpoint'] == 'worldcup.index'


def test_context_pre_farewell_viewer_not_in_wc_pool(app):
    """Enrollment-aware fragments drop for a viewer who never played WC."""
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        _seed_wc_archive(viewer_user=None)
        with patch.dict(os.environ, PRE_ANCHOR):
            ctx = build_lounge_context(user, 'pre')
    assert ctx['farewell']['line'] == (
        'Spain took the Cup. The Commish took the pool.'
    )
    assert ctx['farewell']['finish'] is None
    assert ctx['archived_tiles'][0]['label'] == '2026 · ESP Won'


def test_archive_summary_viewer_rank_is_competition_rank(app):
    """Tied scores share a rank (platform convention: competition rank,
    1 + count scoring strictly higher — never positional). The viewer is
    the id-later member of a 250.0 tie behind the 487.0 winner: 2nd of 4,
    not the positional 3rd."""
    from games.worldcup.models import WorldCupEnrollment
    from games.worldcup.services.lounge import archive_summary
    with app.app_context():
        _seed_wc_archive(viewer_user=None)  # commish 487.0, third 100.0
        tied = _make_user(username='wc_tie_partner')
        db.session.add(WorldCupEnrollment(
            user_id=tied.id, season_year=SEASON_YEAR, total_score=250.0,
        ))
        db.session.commit()
        user = _make_user()
        db.session.add(WorldCupEnrollment(
            user_id=user.id, season_year=SEASON_YEAR, total_score=250.0,
        ))
        db.session.commit()
        summary = archive_summary(user)
    assert summary['viewer_rank'] == 2
    assert summary['viewer_finish_label'] == '2nd of 4'


# == build_lounge_context -- live/post are later slices ====================

def test_context_post_raises_until_slice_ships(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        with pytest.raises(NotImplementedError):
            build_lounge_context(user, 'post')


# == WC tile-label parity (tiles generalization) ===========================

def test_wc_game_tile_label_matches_pre_flip_template_logic():
    """The labels the old hardcoded WC tile computed in-template, now
    supplied by the WC lounge builder: exact string parity."""
    from games.worldcup.services.lounge import game_tile_label

    class _Sealed:
        picks_submitted = True

    class _Unsealed:
        picks_submitted = False

    assert game_tile_label('pre', {'is_enrolled': True, 'enrollment': _Sealed()}) == 'SEALED'
    assert game_tile_label('pre', {'is_enrolled': True, 'enrollment': _Unsealed()}) == 'ROSTER OPEN'
    assert game_tile_label('pre', {'is_enrolled': False}) == 'ROSTER OPEN'
    assert game_tile_label('live', {'dossier': {'rank': 4}}) == 'LIVE · #4'
    assert game_tile_label('live', {'dossier': None}) == 'LIVE'
    assert game_tile_label('post', {}) == 'COMPLETED'


def test_wc_lounge_context_supplies_tile_keys(app):
    """Every authenticated WC lounge context carries the generalized tile
    keys (label + empty archived list)."""
    from games.worldcup.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        ctx = build_lounge_context(user, 'pre')
    assert ctx['game_tile_label'] == 'ROSTER OPEN'
    assert ctx['archived_tiles'] == []


# == live state (C2 slice 4): beats, variants, Who's Left, standings =======

# Thursday 2026-09-24 noon CT: week 4 active, deadline Sat Sep 26 11:00 CT
# (1d 23h out). LIVE_POST is Saturday 7:00 PM CT, past the deadline.
LIVE_PRE = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-24T17:00:00'}
LIVE_POST = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-27T00:00:00'}

W4_DEADLINE = datetime(2026, 9, 26, 11, 0)


def _make_team(name):
    from games.cfb.models import CfbTeam
    t = CfbTeam(name=name)
    db.session.add(t)
    db.session.commit()
    return t


def _make_game(week, home, away, spread=-7.5, game_time=None,
               home_score=None, away_score=None, home_won=None,
               no_contest=False):
    from games.cfb.models import CfbGame
    g = CfbGame(
        week_id=week.id, home_team_id=home.id, away_team_id=away.id,
        home_team_spread=spread, game_time=game_time,
        home_score=home_score, away_score=away_score,
        home_team_won=home_won, is_no_contest=no_contest,
    )
    db.session.add(g)
    db.session.commit()
    return g


def _make_pick(user, week, team, created_at=None, is_correct=None):
    from games.cfb.models import CfbPick
    p = CfbPick(user_id=user.id, week_id=week.id, team_id=team.id,
                is_correct=is_correct)
    if created_at is not None:
        p.created_at = created_at
    db.session.add(p)
    db.session.commit()
    return p


def _make_outcome(week, user, lives=2, eliminated=False, lost_life=False,
                  no_pick=False, revived=False):
    from games.cfb.models import CfbWeekOutcome
    o = CfbWeekOutcome(
        week_id=week.id, user_id=user.id, lives_remaining=lives,
        is_eliminated=eliminated, lost_life=lost_life, no_pick=no_pick,
        revived=revived,
    )
    db.session.add(o)
    db.session.commit()
    return o


def _matchup(week):
    """Auburn (home) vs Alabama (away): the viewer always picks Alabama."""
    auburn = _make_team('Auburn')
    alabama = _make_team('Alabama')
    game = _make_game(week, home=auburn, away=alabama)
    return alabama, auburn, game


def _live_ctx(user, env=LIVE_PRE):
    from games.cfb.services.lounge import build_lounge_context
    with patch.dict(os.environ, env):
        return build_lounge_context(user, 'live')


def test_live_open_beat(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        ctx = _live_ctx(user)
    assert ctx['viewer_mode'] == 'summons'
    s = ctx['summons']
    assert s['beat'] == 'open'
    assert s['week_label'] == 'Week 4'
    assert s['lives'] == 2
    assert s['deadline_relative'] == '1d 23h'
    assert s['deadline_absolute'] == 'Saturday, 11:00 AM CT'
    assert ctx['court_line'] == 'Thursday · Week 4 · 1 remains'


def test_live_held_beat(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=True, deadline=W4_DEADLINE)
        alabama, _, _ = _matchup(week)
        _make_pick(user, week, alabama)
        ctx = _live_ctx(user)
    s = ctx['summons']
    assert s['beat'] == 'held'
    assert s['sentence'] == 'Alabama is held.'
    assert s['support'] == (
        'You may change your pick until Saturday, 11:00 AM CT.'
    )


def test_live_locked_upcoming(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=True, deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.game_time = datetime(2026, 9, 26, 20, 30)
        db.session.commit()
        _make_pick(user, week, alabama)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['beat'] == 'locked'
    assert s['locked_variant'] == 'upcoming'
    assert s['sentence'] == 'Alabama at Auburn. Your pick is final.'
    assert s['meta'] == 'Kickoff Saturday, 8:30 PM CT.'


def test_live_locked_in_progress(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=True, deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.game_time = datetime(2026, 9, 26, 14, 30)
        game.home_score = 17
        game.away_score = 21
        db.session.commit()
        _make_pick(user, week, alabama)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['locked_variant'] == 'in_progress'
    assert s['meta'] == 'In progress · Alabama leads, 21–17.'


def test_live_locked_final_unprocessed(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=True, deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_score = 20
        game.away_score = 31
        game.home_team_won = False
        db.session.commit()
        _make_pick(user, week, alabama)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['locked_variant'] == 'final'
    assert s['meta'] == 'Final: Alabama 31, Auburn 20. The official verdict follows.'


def test_live_locked_autopick_pending(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['beat'] == 'locked'
    assert s['locked_variant'] == 'autopick_pending'
    assert s['sentence'] == (
        'Deadline passed. The Commish is assigning your pick under the '
        'missed-pick rule.'
    )


def test_live_locked_autopick_assigned(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=True, deadline=W4_DEADLINE)
        alabama, _, _ = _matchup(week)
        # created_at is a naive-UTC column; Sat 16:30 UTC is past the
        # 11:00 CT deadline -- the room's autopick detection idiom.
        _make_pick(user, week, alabama,
                   created_at=datetime(2026, 9, 26, 16, 30))
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['beat'] == 'locked'
    assert s['autopick_note'] == (
        'Alabama was assigned under the missed-pick rule.'
    )


def test_live_verdict_survived_with_field_impact(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_score = 20
        game.away_score = 31
        game.home_team_won = False
        db.session.commit()
        _make_pick(user, week, alabama, is_correct=True)
        _make_outcome(week, user, lives=2)
        # Field: one player drops to one life, one is cut.
        others = _seed_cfb_field([(1, False), (0, True)])
        _make_outcome(week, db.session.get(User, others[0].user_id),
                      lives=1, lost_life=True)
        _make_outcome(week, db.session.get(User, others[1].user_id),
                      lives=0, eliminated=True, lost_life=True)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['beat'] == 'verdict'
    assert s['verdict_word'] == 'SURVIVED'
    assert s['verdict_class'] == 'is-win'
    assert s['sentence'] == (
        'Alabama defeated Auburn, 31–20. You advance with two lives.'
    )
    assert s['field_impact'] == (
        'Two players lost a life in Week 4. One was cut. 2 remain.'
    )


def test_live_verdict_lost(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=1)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_score = 24
        game.away_score = 17
        game.home_team_won = True
        db.session.commit()
        _make_pick(user, week, alabama, is_correct=False)
        _make_outcome(week, user, lives=1, lost_life=True)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['verdict_word'] == 'LOST A LIFE'
    assert s['verdict_class'] == 'is-loss'
    assert s['sentence'] == (
        'Alabama lost to Auburn, 17–24. You have one life remaining. '
        'Your next loss eliminates you.'
    )


def test_live_verdict_eliminated(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=0, eliminated=True)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_team_won = True
        db.session.commit()
        _make_pick(user, week, alabama, is_correct=False)
        _make_outcome(week, user, lives=0, eliminated=True, lost_life=True)
        _seed_cfb_field([(2, False), (2, False)])
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert ctx['viewer_mode'] == 'summons'  # elimination week renders VERDICT
    assert s['verdict_word'] == 'ELIMINATED'
    assert s['verdict_class'] == 'is-out'
    assert s['sentence'] == (
        'Alabama lost to Auburn. No lives remain. Your season ends in '
        'Week 4; the pool plays on.'
    )
    assert [r['label'] for r in s['routes']] == [
        "Follow who's left", 'Review my season',
    ]


def test_live_verdict_no_pick_penalty(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=1)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        _make_outcome(week, user, lives=1, lost_life=True, no_pick=True)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['verdict_word'] == 'LOST A LIFE'
    assert s['sentence'] == (
        'No valid pick was submitted. One life has been lost. You have '
        'one life remaining. Your next loss eliminates you.'
    )


def test_live_verdict_revived(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=1)
        week = _make_week(number=9, active=False, complete=True,
                          deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_team_won = True
        db.session.commit()
        _make_pick(user, week, alabama, is_correct=False)
        _make_outcome(week, user, lives=1, lost_life=True, revived=True)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['verdict_word'] == 'REVIVED'
    assert s['verdict_class'] == 'is-win'
    assert s['sentence'] == (
        'Every remaining player lost in Week 9. The pool revives all who '
        'picked and lost. You continue with one life.'
    )


def test_live_verdict_no_contest(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        auburn = _make_team('Auburn')
        alabama = _make_team('Alabama')
        _make_game(week, home=auburn, away=alabama, no_contest=True)
        _make_pick(user, week, alabama)
        _make_outcome(week, user, lives=2)
        ctx = _live_ctx(user, LIVE_POST)
    s = ctx['summons']
    assert s['verdict_word'] == 'NO CONTEST'
    assert s['verdict_class'] == 'is-push'
    assert s['sentence'] == (
        "Alabama's game was canceled. No life lost; the week counts as "
        'survived. Alabama stays used; the spread is excluded from your '
        'tiebreaker.'
    )


def test_live_standing_eliminated_module(app):
    """Eliminated in an earlier week: the standing module takes the
    Summons slot once the next week opens (C1 section 2.3)."""
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=0, eliminated=True)
        week3 = _make_week(number=3, active=False, complete=True,
                           deadline=datetime(2026, 9, 19, 11, 0))
        _make_outcome(week3, user, lives=0, eliminated=True, lost_life=True)
        week1 = _make_week(number=1, active=False, complete=True,
                           deadline=datetime(2026, 9, 5, 11, 0))
        week2 = _make_week(number=2, active=False, complete=True,
                           deadline=datetime(2026, 9, 12, 11, 0))
        georgia = _make_team('Georgia')
        texas = _make_team('Texas')
        _make_pick(user, week1, georgia, is_correct=True)
        _make_pick(user, week2, texas, is_correct=True)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(2, False), (2, False)])
        ctx = _live_ctx(user)
    assert ctx['viewer_mode'] == 'eliminated'
    em = ctx['eliminated_module']
    assert em['line'] == 'Out in Week 3. The pool plays on.'
    assert em['path'] == 'You survived two weeks on Georgia and Texas.'


def test_live_view_variant_unenrolled(app):
    with app.app_context():
        user = _make_user()
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(2, False), (1, False), (0, True)])
        ctx = _live_ctx(user)
    assert ctx['viewer_mode'] == 'view'
    assert ctx['view_module']['field_line'] == (
        'The pool is underway. 2 of 3 remain.'
    )
    assert ctx['game_tile_label'] == 'WEEK 4 · LIVE'


# == Who's Left phases =====================================================

def test_whos_left_phase_a_full_field(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=1, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(2, False), (2, False)])
        ctx = _live_ctx(user)
    wl = ctx['whos_left']
    assert wl['phase'] == 'A'
    assert wl['total'] == 3
    assert wl['two_lives_each'] is True


def test_whos_left_phase_b_band_and_cuts(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        week3 = _make_week(number=3, active=False, complete=True,
                           deadline=datetime(2026, 9, 19, 11, 0))
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        # 24 total: viewer + 8 more two-lives, 5 one-life, 10 out
        others = _seed_cfb_field(
            [(2, False)] * 8 + [(1, False)] * 5 + [(0, True)] * 10
        )
        cut_a = others[13]  # first eliminated seed (fielduser13)
        cut_b = others[14]
        _make_outcome(week3, db.session.get(User, cut_a.user_id),
                      lives=0, eliminated=True, lost_life=True)
        _make_outcome(week3, db.session.get(User, cut_b.user_id),
                      lives=0, eliminated=True, lost_life=True)
        ctx = _live_ctx(user)
    wl = ctx['whos_left']
    assert wl['phase'] == 'B'
    assert (wl['two_lives'], wl['one_life'], wl['out']) == (9, 5, 10)
    assert wl['active'] == 14
    assert wl['cuts_line'] == 'Cut in Week 3: fielduser13, fielduser14.'


def test_whos_left_phase_c_names(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=10, active=True, deadline=W4_DEADLINE)
        # 24 total, 8 active (viewer + 7): names phase
        _seed_cfb_field([(2, False)] * 4 + [(1, False)] * 3 + [(0, True)] * 16)
        ctx = _live_ctx(user)
    wl = ctx['whos_left']
    assert wl['phase'] == 'C'
    assert wl['active'] == 8
    assert len(wl['rows']) == 8
    assert any(r['is_you'] for r in wl['rows'])


def test_whos_left_phase_d_endgame(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=13, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(1, False), (1, False)] + [(0, True)] * 10)
        ctx = _live_ctx(user)
    wl = ctx['whos_left']
    assert wl['phase'] == 'D'
    assert wl['remain_line'] == '3 remain. One survives.'
    assert wl['reveal_note'] == (
        'Week 13 picks lock Saturday, 11:00 AM CT. Revealed at the deadline.'
    )
    assert len(wl['rows']) == 3


# == compact standings =====================================================

def test_get_official_standings_order_and_tie_ranks(app):
    """Central helper (room + lounge): official order is lives DESC,
    cumulative spread ASC; competition ranks share on exact ties."""
    from games.cfb.services.game_logic import get_official_standings
    with app.app_context():
        spec = [(2, 41.5), (2, 48.0), (1, 30.0), (2, 41.5)]
        for i, (lives, spread) in enumerate(spec):
            u = _make_user(username=f'rankuser{i}')
            e = _enroll_cfb(u, lives=lives)
            e.cumulative_spread = spread
        db.session.commit()
        ordered, ranks = get_official_standings(SEASON_YEAR)
        names = [e.get_display_name() for e in ordered]
        rank_list = [ranks[e.id] for e in ordered]
    assert names == ['rankuser0', 'rankuser3', 'rankuser1', 'rankuser2']
    assert rank_list == [1, 1, 3, 4]


def test_live_standings_rows_top3_plus_you(app):
    with app.app_context():
        user = _make_user()
        viewer = _enroll_cfb(user, lives=1)
        viewer.cumulative_spread = 99.0
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        for i, spread in enumerate([41.5, 48.0, 52.5, 61.0]):
            u = _make_user(username=f'standuser{i}')
            e = _enroll_cfb(u)
            e.cumulative_spread = spread
        db.session.commit()
        ctx = _live_ctx(user)
    rows = ctx['standings_rows']
    assert len(rows) == 4
    assert [r['rank'] for r in rows] == [1, 2, 3, 5]
    assert rows[0]['tagline'] == 'Two lives · spread 41.5'
    assert rows[3]['is_you'] is True
    assert rows[3]['separator_above'] is True
    assert rows[3]['tagline'] == 'One life · spread 99.0'


def test_live_standings_no_you_row_duplicate_when_in_top3(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(1, False), (1, False)])
        ctx = _live_ctx(user)
    rows = ctx['standings_rows']
    assert len(rows) == 3
    assert sum(1 for r in rows if r['is_you']) == 1


def test_live_tile_label_lives_variants(app):
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=1)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        ctx = _live_ctx(user)
        assert ctx['game_tile_label'] == 'WEEK 4 · 1 LIFE'
        user2 = _make_user(username='cutviewer')
        _enroll_cfb(user2, lives=0, eliminated=True)
        ctx2 = _live_ctx(user2)
        assert ctx2['game_tile_label'] == 'ELIMINATED'


# == rendered shells through the flipped registry ==========================

def test_cfb_pre_shell_renders_for_unenrolled_viewer(app, client, monkeypatch):
    _flip_to_cfb(monkeypatch)
    with app.app_context():
        user = _make_user()
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, PRE_ANCHOR):
        resp = client.get('/')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'home-shell--pre' in text
    assert 'The Season' in text and 'Opens' in text
    assert 'No 002' in text
    assert 'First Pick Locks In' in text
    assert 'Take Your Two Lives' in text
    assert 'Everyone starts with two lives.' in text


def test_cfb_pre_shell_enrolled_viewer_gets_room_cta(app, client, monkeypatch):
    _flip_to_cfb(monkeypatch)
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _seed_wc_archive(viewer_user=user)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, PRE_ANCHOR):
        resp = client.get('/')
    text = resp.get_data(as_text=True)
    assert 'Enter the Room' in text
    assert 'Take Your Two Lives' not in text
    # Farewell strip (pre-state only, C1 ruling 4) + archived WC tile
    assert 'Spain took the Cup. The Commish took the pool.' in text
    assert 'Visit the archive' in text
    assert 'cg--archived' in text
    assert '2026 · ESP Won · You 2nd' in text


def test_cfb_out_shell_copy_pass(app, client, monkeypatch):
    """Anonymous, post-flip: survivor-voice marketing copy, Golf-only
    coming-soon rail, WC nowhere (C1 section 4.1)."""
    _flip_to_cfb(monkeypatch)
    resp = client.get('/')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'home-shell--out' in text
    assert 'CFB Survivor' in text
    assert 'Open Court' in text
    assert 'Survive the season' in text
    assert 'Outlast the field' in text
    # One combined join-card paragraph (registry description + kickoff
    # date), not a description followed by a repetitive deadline line.
    assert 'Last survivor wins. Season kicks off Thursday, Sep 3.' in text
    # Golf still on the docket; the finished WC pool is a members' surface
    assert 'Golf' in text
    assert 'World Cup' not in text


def test_cfb_live_open_shell_renders(app, client, monkeypatch):
    _flip_to_cfb(monkeypatch)
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user)
        _make_week(number=4, active=True, deadline=W4_DEADLINE)
        _seed_cfb_field([(2, False), (2, False)])
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, LIVE_PRE):
        resp = client.get('/')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'home-shell--live' in text
    assert 'Still' in text and 'Standing' in text
    assert 'The Summons' in text
    assert 'You have not made a pick.' in text
    assert 'Choose Team' in text
    assert 'Full standings' in text
    assert 'The field' in text  # Who's Left route
    # No WC archive seeded here, so the strip omits the archived tile
    assert 'cg--archived' not in text


def test_cfb_live_verdict_shell_renders(app, client, monkeypatch):
    _flip_to_cfb(monkeypatch)
    with app.app_context():
        user = _make_user()
        _enroll_cfb(user, lives=1)
        week = _make_week(number=4, active=False, complete=True,
                          deadline=W4_DEADLINE)
        alabama, auburn, game = _matchup(week)
        game.home_score = 24
        game.away_score = 17
        game.home_team_won = True
        db.session.commit()
        _make_pick(user, week, alabama, is_correct=False)
        _make_outcome(week, user, lives=1, lost_life=True)
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, LIVE_POST):
        resp = client.get('/')
    text = resp.get_data(as_text=True)
    assert 'Lost a Life' in text or 'LOST A LIFE' in text
    assert 'Your next loss eliminates you.' in text
    assert 'View week results' in text
    assert 'Choose Team' not in text


def test_wc_pre_shell_tiles_unchanged_before_flip(app, client):
    """Pre-flip regression: the generalized tile strip still renders the
    WC active tile + registry coming-soon tiles exactly as before."""
    with app.app_context():
        user = _make_user()
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'WC_FAKE_NOW': '2026-06-01T00:00:00'}):
        resp = client.get('/')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'home-shell--pre' in text
    assert 'cg--active' in text
    assert 'ROSTER OPEN' in text
    assert '/worldcup' in text
    # Coming-soon tiles stay registry-driven
    assert 'Sep 3' in text and '2027' in text
    assert 'cg--archived' not in text
