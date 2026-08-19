"""The platform-admin leagues listing (/admin/): every game with shipped
admin routes appears with working Admin + Payments actions."""
from extensions import db
from tests._docket_fixtures import login, make_enrollment, make_user


def _login_admin(client):
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    login(client, admin)


def test_dashboard_lists_all_four_leagues(app, client):
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    for name in ('World Cup Fantasy', 'Golf Pick', 'CFB Survivor Pool',
                 'The Docket'):
        assert name in data, name


def test_dashboard_docket_card_carries_both_actions(app, client):
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    assert '/docket/admin/' in data
    assert '/docket/admin/payments' in data


def test_dashboard_counts_docket_enrollments(app, client):
    paid = make_user('paidmember')
    make_enrollment(paid, has_paid=True)
    unpaid = make_user('unpaidmember')
    make_enrollment(unpaid)
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    assert '2 enrolled · 1 paid' in data
