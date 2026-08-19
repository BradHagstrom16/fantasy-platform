"""The clerk's Court Costs screen (/docket/admin/payments): the $60 entry
fee from config, the season-scoped roster, and the payment toggle."""
from extensions import db
from games.docket.models import DocketEnrollment
from tests._docket_fixtures import login, make_enrollment, make_user


def _login_admin(client):
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    login(client, admin)
    return admin


def test_entry_fee_default_is_sixty(app):
    assert app.config['DOCKET_ENTRY_FEE'] == 60


def test_payments_page_lists_only_the_current_season(app, client):
    member = make_user('member')
    make_enrollment(member, display_name='The Gavel')
    oldtimer = make_user('oldtimer')
    db.session.add(DocketEnrollment(user_id=oldtimer.id, season_year=2025))
    _login_admin(client)
    data = client.get('/docket/admin/payments').data.decode()
    assert 'The Gavel' in data
    assert 'oldtimer' not in data


def test_payments_page_states_the_fee_and_the_count(app, client):
    paid = make_user('paidup')
    make_enrollment(paid, has_paid=True)
    unpaid = make_user('owes')
    make_enrollment(unpaid)
    _login_admin(client)
    data = client.get('/docket/admin/payments').data.decode()
    assert '$60' in data
    assert '1 of 2 paid' in data


def test_payments_page_renders_with_an_empty_roster(app, client):
    _login_admin(client)
    assert client.get('/docket/admin/payments').status_code == 200


def test_toggle_marks_paid_and_back(app, client):
    member = make_user('member')
    enrollment = make_enrollment(member)
    _login_admin(client)

    resp = client.post(f'/docket/admin/update-payment/{member.id}',
                       json={'has_paid': True})
    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'has_paid': True}
    assert db.session.get(DocketEnrollment, enrollment.id).has_paid is True

    resp = client.post(f'/docket/admin/update-payment/{member.id}',
                       json={'has_paid': False})
    assert resp.get_json() == {'success': True, 'has_paid': False}
    assert db.session.get(DocketEnrollment, enrollment.id).has_paid is False


def test_toggle_404s_for_a_user_with_no_enrollment(app, client):
    stranger = make_user('stranger')
    _login_admin(client)
    resp = client.post(f'/docket/admin/update-payment/{stranger.id}',
                       json={'has_paid': True})
    assert resp.status_code == 404


def test_toggle_400s_without_a_json_body(app, client):
    member = make_user('member')
    make_enrollment(member)
    _login_admin(client)
    resp = client.post(f'/docket/admin/update-payment/{member.id}')
    assert resp.status_code == 400


def test_toggle_400s_unless_has_paid_is_a_real_boolean(app, client):
    """A JSON string "false" is truthy and a list body has no .get() —
    anything but {"has_paid": <bool>} is refused before mutating."""
    member = make_user('member')
    enrollment = make_enrollment(member)
    _login_admin(client)
    for body in ({}, {'has_paid': 'false'}, {'has_paid': 0},
                 ['has_paid'], {'has_paid': None}):
        resp = client.post(f'/docket/admin/update-payment/{member.id}',
                           json=body)
        assert resp.status_code == 400, body
    assert db.session.get(DocketEnrollment, enrollment.id).has_paid is False


def test_toggle_is_post_only(app, client):
    _login_admin(client)
    assert client.get('/docket/admin/update-payment/1').status_code == 405
