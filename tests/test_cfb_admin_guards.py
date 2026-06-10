"""CFB admin destructive-action guards (pre-launch audit §9 MEDIUM).

Two guards on the admin team/game admin surfaces:

  admin_delete_game — must refuse to delete a game whose teams have
    already been picked this week; deleting strands those picks
    ungradeable and silently shrinks cumulative spreads on recalc.
  admin_manage_teams — must refuse to remove a team still referenced by
    a CfbGame; a bare delete raises a FK IntegrityError on Postgres.

Admin routes use the two-tier @cfb_admin_required (platform admin passes
directly), so these tests log in a platform admin via auth_id.
"""
import pytest

from app import create_app
from extensions import db
from games.cfb.models import CfbTeam, CfbGame
from tests._cfb_fixtures import (
    make_user, make_enrollment, make_team, make_week, make_game, make_pick,
)


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


def _login_admin(client):
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['_user_id'] = admin.auth_id
        sess['_fresh'] = True
    return admin


# ── admin_delete_game pick guard ──────────────────────────────────────────

def test_delete_game_refused_when_a_team_was_picked(app, client):
    """A game whose team a player already picked can't be deleted."""
    _login_admin(client)
    week = make_week(1)
    home, away = make_team('Home'), make_team('Away')
    game = make_game(week, home, away, spread=-7.0)
    picker = make_user('picker')
    make_enrollment(picker)
    make_pick(picker, week, home)
    db.session.commit()
    game_id, week_id = game.id, week.id

    resp = client.post(
        f'/cfb/admin/week/{week_id}/games/{game_id}/delete',
        data={'csrf_token': 'x'}, follow_redirects=False,
    )

    assert resp.status_code == 302
    assert f'/cfb/admin/week/{week_id}/games' in resp.headers['Location']
    assert db.session.get(CfbGame, game_id) is not None  # not deleted


def test_delete_game_allowed_when_no_picks(app, client):
    """The happy path still works: an unpicked game deletes cleanly."""
    _login_admin(client)
    week = make_week(1)
    home, away = make_team('Home'), make_team('Away')
    game = make_game(week, home, away, spread=-7.0)
    db.session.commit()
    game_id, week_id = game.id, week.id

    resp = client.post(
        f'/cfb/admin/week/{week_id}/games/{game_id}/delete',
        data={'csrf_token': 'x'}, follow_redirects=False,
    )

    assert resp.status_code == 302
    assert f'/cfb/admin/week/{week_id}/games' in resp.headers['Location']
    assert db.session.get(CfbGame, game_id) is None  # deleted


# ── admin_manage_teams game-reference guard ───────────────────────────────

def test_manage_teams_keeps_team_referenced_by_a_game(app, client):
    """Deselecting a team that still has a scheduled game must not remove it
    (a bare delete would FK-500 on Postgres)."""
    _login_admin(client)
    week = make_week(1)
    # Use real FBS names so they round-trip through the master-list form.
    home, away = make_team('Alabama'), make_team('Auburn')
    make_game(week, home, away, spread=-7.0)
    db.session.commit()

    # POST with an empty selection — without the guard both teams get deleted.
    resp = client.post(
        '/cfb/admin/manage-teams',
        data={'csrf_token': 'x'}, follow_redirects=False,
    )

    assert resp.status_code == 302
    assert '/cfb/admin/manage-teams' in resp.headers['Location']
    assert CfbTeam.query.filter_by(name='Alabama').first() is not None
    assert CfbTeam.query.filter_by(name='Auburn').first() is not None


def test_manage_teams_still_removes_unreferenced_team(app, client):
    """A team with neither picks nor games is freely removable."""
    _login_admin(client)
    make_team('Akron')  # no game, no pick
    db.session.commit()

    resp = client.post(
        '/cfb/admin/manage-teams',
        data={'csrf_token': 'x'}, follow_redirects=False,
    )

    assert resp.status_code == 302
    assert '/cfb/admin/manage-teams' in resp.headers['Location']
    assert CfbTeam.query.filter_by(name='Akron').first() is None  # removed
