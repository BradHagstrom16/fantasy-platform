"""Group-stage recap email."""
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
)
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _team(code, name, tier, mult, grp, **kw):
    t = WorldCupTeam(fifa_code=code, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='X', group_letter=grp, **kw)
    db.session.add(t)
    db.session.flush()
    return t


def test_recap_blocked_when_advancement_unconfirmed(app):
    from games.worldcup.services.notifications import send_group_stage_recap
    with app.app_context():
        # No completed group matches -> not confirmed.
        out = send_group_stage_recap()
        assert out['status'] == 'blocked'


def test_recap_sends_with_advancement_breakdown(app):
    from games.worldcup.services.notifications import send_group_stage_recap
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        winner = _team('BRA', 'Brazil', 1, 1.0, 'A', advancement_method='group_winner')
        wild = _team('KSA', 'Saudi Arabia', 5, 7.0, 'A', advancement_method='best_third')
        out_team = _team('SRB', 'Serbia', 4, 4.0, 'A', is_eliminated=True)
        u = User(username='al', email='al@test.com'); u.set_password('x')
        db.session.add(u); db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e); db.session.flush()
        for t in (winner, wild, out_team):
            db.session.add(WorldCupPick(enrollment_id=e.id, team_id=t.id, tier=t.tier))
        db.session.commit()

        with patch('games.worldcup.services.notifications.send_platform_email',
                   return_value=True) as send:
            out = send_group_stage_recap()
        assert out['status'] == 'sent'
        assert out['sent'] == 1
        # Email body mentions advancement points: winner +4, best-third 1*7=7.
        html = send.call_args[0][3]
        assert 'Brazil' in html and 'Saudi Arabia' in html


def test_send_group_recap_route_admin_only(app):
    client = app.test_client()
    resp = client.post('/worldcup/admin/send-group-recap', data={'csrf_token': 'x'})
    assert resp.status_code in (302, 401, 403)


def test_send_group_recap_route_invokes_service(app):
    client = app.test_client()
    with app.app_context():
        u = User(username='boss', email='boss@test.com', is_admin=True); u.set_password('x')
        db.session.add(u); db.session.commit()
        auth_id = u.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.send_group_stage_recap',
               return_value={'status': 'sent', 'sent': 3, 'skipped_no_email': 0, 'errors': 0}) as svc:
        resp = client.post('/worldcup/admin/send-group-recap', data={'csrf_token': 'x'})
    assert resp.status_code == 302
    svc.assert_called_once()
