"""Tests for /worldcup/rosters — The Open Ballots (all rosters, names written out).

The page exists so a member can find-on-page a full country name ("who picked
Bosnia") across every roster at once. Locks:

- D11 privacy gate mirrors /worldcup/stats: sealed for EVERYONE pre-deadline
  (including enrolled members), admin preview allowed.
- Full ``display_name`` strings render in the DOM post-deadline (the Ctrl-F
  contract — no FIFA-code-only grids, no collapsed accordions).
- Dense rank parity with the leaderboard idiom.
- Eliminated picks carry a text "Out" label (never color alone).
- Avatar precedes the display name (platform standings integration point).
"""
import os
import re
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def session(app):
    yield db.session


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_user(session, username, is_admin=False):
    u = User(username=username, email=f'{username}@test.com',
             password_hash='x', is_admin=is_admin)
    session.add(u)
    session.flush()
    return u


def _make_team(session, fifa_code, name, tier=1, multiplier=1.0, group='A'):
    t = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier, confederation='TEST', group_letter=group,
    )
    session.add(t)
    session.flush()
    return t


def _make_enrollment(session, user_id, season_year=2026, total_score=0.0):
    e = WorldCupEnrollment(
        user_id=user_id, season_year=season_year,
        picks_submitted=True, total_score=total_score,
    )
    session.add(e)
    session.flush()
    return e


def _make_pick(session, enrollment_id, team_id, tier, multiplied_points=0.0):
    p = WorldCupPick(
        enrollment_id=enrollment_id, team_id=team_id, tier=tier,
        multiplied_points=multiplied_points,
    )
    session.add(p)
    session.flush()
    return p


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.get_id()  # auth_id, never str(user.id)
        sess['_fresh'] = True


# Picks locked at 2026-06-11 19:00 UTC (now in the past), so BOTH sides of
# the gate must fake the clock: pre-deadline tests pin a date before kickoff,
# post-deadline tests pin one after. ENVIRONMENT=testing activates the seam.
_BEFORE_KICKOFF = {'WC_FAKE_NOW': '2026-06-01T12:00:00+00:00', 'ENVIRONMENT': 'testing'}
_AFTER_KICKOFF = {'WC_FAKE_NOW': '2026-06-15T12:00:00+00:00', 'ENVIRONMENT': 'testing'}


def _field_with_bosnia(session):
    """Two players; alice holds Bosnia and Herzegovina. Returns (alice, bob, team)."""
    bosnia = _make_team(session, 'BIH', 'Bosnia and Herzegovina', tier=5, multiplier=7.0)
    brazil = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    alice = _make_user(session, 'alice')
    bob = _make_user(session, 'bob')
    e1 = _make_enrollment(session, alice.id, total_score=12.5)
    e2 = _make_enrollment(session, bob.id, total_score=3.0)
    _make_pick(session, e1.id, bosnia.id, tier=5, multiplied_points=12.5)
    _make_pick(session, e2.id, brazil.id, tier=1, multiplied_points=3.0)
    session.commit()
    return alice, bob, bosnia


# ── Privacy gate (D11 corollary: sealed for everyone pre-deadline) ──────────

def test_rosters_sealed_pre_deadline_anonymous(client, session):
    _field_with_bosnia(session)

    with patch.dict(os.environ, _BEFORE_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert resp.status_code == 200
    # Hero still renders...
    assert b'The Open Ballots' in resp.data
    # ...but no roster data leaks: no grid, no country, no player.
    assert b'ballotsGrid' not in resp.data
    assert b'Bosnia and Herzegovina' not in resp.data
    assert b'alice' not in resp.data
    assert b'Ballots sealed' in resp.data


def test_rosters_sealed_pre_deadline_enrolled_member(client, session):
    """Pre-lock the page is sealed even for an enrolled member — their own
    roster on an aggregate surface would still leak the field's shape."""
    alice, _, _ = _field_with_bosnia(session)
    _login(client, alice)

    with patch.dict(os.environ, _BEFORE_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert resp.status_code == 200
    assert b'Ballots sealed' in resp.data
    assert b'Bosnia and Herzegovina' not in resp.data


def test_rosters_visible_admin_pre_deadline(client, session):
    _field_with_bosnia(session)
    admin = _make_user(session, 'wcadmin', is_admin=True)
    session.commit()
    _login(client, admin)

    with patch.dict(os.environ, _BEFORE_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert resp.status_code == 200
    assert b'ballotsGrid' in resp.data
    assert b'Bosnia and Herzegovina' in resp.data


# ── The Ctrl-F contract ─────────────────────────────────────────────────────

def test_rosters_full_country_names_post_deadline(client, session):
    """Every roster renders with full country names in the DOM — the page's
    reason to exist ("ctrl-f to find who picked Bosnia")."""
    _field_with_bosnia(session)

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert resp.status_code == 200
    assert b'Bosnia and Herzegovina' in resp.data
    assert b'Brazil' in resp.data
    # Both players appear with their multiplier chips.
    assert b'alice' in resp.data
    assert b'bob' in resp.data
    assert b'&times;7' in resp.data


def test_rosters_avatar_precedes_name(client, session):
    """Platform integration point: standings show user.get_avatar() inline
    before the player display name."""
    _field_with_bosnia(session)

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    html = resp.data.decode()
    card = re.search(r'<h2 class="wc-ballots-name[^>]*>(.*?)</h2>', html, re.DOTALL)
    assert card, 'ballot card name heading missing'
    assert 'leaderboard-avatar' in card.group(1)
    assert card.group(1).index('leaderboard-avatar') < card.group(1).index('alice')


def test_rosters_dense_rank(client, session):
    """Tied scores share a rank; the next distinct score is rank+1 (no gap)."""
    team = _make_team(session, 'ARG', 'Argentina')
    users = [_make_user(session, f'p{i}') for i in range(3)]
    scores = [10.0, 10.0, 5.0]
    for u, s in zip(users, scores, strict=True):
        e = _make_enrollment(session, u.id, total_score=s)
        _make_pick(session, e.id, team.id, tier=1)
    session.commit()

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    html = resp.data.decode()
    assert html.count('title="Rank 1 of 3"') == 2
    assert 'title="Rank 2 of 3"' in html
    assert 'title="Rank 3 of 3"' not in html


def test_rosters_eliminated_pick_carries_out_label(client, session):
    """A tournament-out pick gets the struck row + a text 'Out' label."""
    out_team = _make_team(session, 'GER', 'Germany')
    out_team.is_eliminated = True  # group exit; eliminated_team_ids() includes it
    u = _make_user(session, 'carol')
    e = _make_enrollment(session, u.id)
    _make_pick(session, e.id, out_team.id, tier=1)
    session.commit()

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    html = resp.data.decode()
    assert 'wc-ballots-row is-out' in html
    assert re.search(r'<span class="wc-ballots-out">Out</span>', html)


def test_rosters_no_ballot_filed(client, session):
    """An enrollment with zero picks renders an explicit empty line."""
    u = _make_user(session, 'dave')
    _make_enrollment(session, u.id)
    session.commit()

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert b'No ballot filed.' in resp.data


def test_rosters_empty_pool(client, session):
    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    assert resp.status_code == 200
    assert b'The ballot box is empty.' in resp.data


def test_rosters_own_card_links_to_picks_page(client, session):
    """The viewer's own card routes to /worldcup/picks (leaderboard parity);
    everyone else's routes to their player detail."""
    alice, _, _ = _field_with_bosnia(session)
    _login(client, alice)

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    html = resp.data.decode()
    alice_card = re.search(
        r'<article[^>]*data-player="alice".*?</article>', html, re.DOTALL)
    assert alice_card and '/worldcup/picks' in alice_card.group(0)
    bob_card = re.search(
        r'<article[^>]*data-player="bob".*?</article>', html, re.DOTALL)
    assert bob_card and '/worldcup/leaderboard/' in bob_card.group(0)
    # Viewer's card carries the current-user tint class.
    assert 'is-me' in alice_card.group(0)
    assert 'is-me' not in bob_card.group(0)


# ── Navigation ──────────────────────────────────────────────────────────────

def test_subnav_all_picks_pill_active_on_rosters(client, session):
    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/rosters')
    html = resp.data.decode()
    assert re.search(
        r'subnav-pill active"\s+href="/worldcup/rosters">All Picks</a>', html)


def test_subnav_all_picks_pill_inactive_elsewhere(client, session):
    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/leaderboard')
    html = resp.data.decode()
    assert re.search(
        r'subnav-pill\s*"\s+href="/worldcup/rosters">All Picks</a>', html)


def test_leaderboard_crosslink_gated_on_deadline(client, session):
    """The Board links to the rosters page post-deadline only — pre-lock the
    target is sealed and the invitation would dead-end."""
    _field_with_bosnia(session)

    with patch.dict(os.environ, _AFTER_KICKOFF):
        post = client.get('/worldcup/leaderboard')
    assert b'Every roster, written out, on one page' in post.data

    with patch.dict(os.environ, _BEFORE_KICKOFF):
        pre = client.get('/worldcup/leaderboard')
    assert b'Every roster, written out, on one page' not in pre.data
