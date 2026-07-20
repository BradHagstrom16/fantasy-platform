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


# == build_lounge_context -- live/post are later slices ====================

def test_context_live_raises_until_slice_ships(app):
    from games.cfb.services.lounge import build_lounge_context
    with app.app_context():
        user = _make_user()
        with pytest.raises(NotImplementedError):
            build_lounge_context(user, 'live')


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
    assert 'Two lives. One pick a week.' in text
    # Golf still on the docket; the finished WC pool is a members' surface
    assert 'Golf' in text
    assert 'World Cup' not in text


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
