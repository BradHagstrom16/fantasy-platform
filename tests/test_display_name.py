"""One display name per member (ADR-057).

``User.display_name`` is the only member name on the platform: every
enrollment helper delegates to it, it is validated in exactly one place
(``utils/display_name.normalize_display_name``), and it is editable by the
member on /profile and by the Commish on /admin/users. The per-game name
that CFB/Docket joins used to collect is gone; the join pages state the name
the member will stand under and point at the profile instead.
"""
from extensions import db
from games.cfb.models import CfbEnrollment
from games.docket.models import DocketEnrollment
from games.worldcup.models import WorldCupEnrollment
from models.user import User
from tests._cfb_fixtures import make_enrollment as make_cfb_enrollment
from tests._docket_fixtures import login, make_user
from tests._docket_fixtures import make_enrollment as make_docket_enrollment

LONGEST = 'x' * 100


def _norm(raw, **kwargs):
    from utils.display_name import normalize_display_name
    return normalize_display_name(raw, **kwargs)


def _profile_post(client, email, display_name):
    return client.post('/profile', data={
        'email': email, 'display_name': display_name,
        'avatar_emoji': '', 'phone': '',
    })


# --- normalize_display_name: the one validator ----------------------------

def test_blank_display_name_normalizes_to_none(app):
    assert _norm('') == (None, None)
    assert _norm('   ') == (None, None)
    assert _norm(None) == (None, None)


def test_display_name_is_stripped_and_inner_whitespace_collapsed(app):
    assert _norm('  Fourth   &  Pine ') == ('Fourth & Pine', None)


def test_display_name_at_column_length_is_accepted(app):
    assert _norm(LONGEST) == (LONGEST, None)


def test_display_name_over_column_length_is_rejected(app):
    value, error = _norm(LONGEST + 'y')
    assert value is None
    assert error


def test_display_name_taken_by_another_members_display_name(app):
    other = make_user('other')
    other.display_name = 'The Gavel'
    db.session.commit()
    value, error = _norm('the gavel')
    assert value is None
    assert 'taken' in error


def test_display_name_taken_by_another_members_username(app):
    make_user('cubbies22')
    db.session.commit()
    value, error = _norm('Cubbies22')
    assert value is None
    assert 'taken' in error


def test_display_name_collision_check_excludes_the_member_themself(app):
    me = make_user('me')
    me.display_name = 'The Gavel'
    db.session.commit()
    assert _norm('The Gavel', exclude_user_id=me.id) == ('The Gavel', None)
    # A member may stand under their own username, spelled however they like.
    assert _norm('ME', exclude_user_id=me.id) == ('ME', None)


# --- enrollment helpers delegate to the platform name ---------------------

def test_cfb_enrollment_name_follows_the_platform_display_name(app):
    user = make_user('cfbuser')
    enrollment = make_cfb_enrollment(user)
    db.session.commit()
    assert enrollment.get_display_name() == 'cfbuser'
    user.display_name = 'Fourth & Pine'
    assert enrollment.get_display_name() == 'Fourth & Pine'


def test_docket_enrollment_name_follows_the_platform_display_name(app):
    user = make_user('docketuser')
    enrollment = make_docket_enrollment(user)
    db.session.commit()
    assert enrollment.get_display_name() == 'docketuser'
    user.display_name = 'The Gavel'
    assert enrollment.get_display_name() == 'The Gavel'


def test_worldcup_enrollment_falls_back_to_the_platform_display_name(app):
    """The archived WC leaderboard reads the platform name too (the frozen
    per-game column still wins where it was ever set)."""
    user = make_user('wcuser')
    user.display_name = 'Platform Name'
    enrollment = WorldCupEnrollment(user_id=user.id, season_year=2026)
    db.session.add(enrollment)
    db.session.commit()
    assert enrollment.get_display_name() == 'Platform Name'
    enrollment.display_name = 'WC Name'
    assert enrollment.get_display_name() == 'WC Name'


def test_cfb_and_docket_enrollments_carry_no_display_name_column(app):
    assert 'display_name' not in CfbEnrollment.__table__.columns
    assert 'display_name' not in DocketEnrollment.__table__.columns


def test_rename_reaches_the_docket_payment_memo(app):
    from games.docket.services.payment import payment_nudge_for
    user = make_user('payer')
    enrollment = make_docket_enrollment(user)
    user.display_name = 'The Gavel'
    db.session.commit()
    nudge = payment_nudge_for(enrollment, False)
    assert 'The+Gavel' in nudge['venmo_url']


# --- /profile: the member's edit point ------------------------------------

def test_profile_rename_propagates_to_the_cfb_standings(app, client):
    user = make_user('renamer')
    make_cfb_enrollment(user)
    db.session.commit()
    login(client, user)
    _profile_post(client, 'renamer@test.com', 'Fourth & Pine')
    text = client.get('/cfb/').get_data(as_text=True)
    assert 'Fourth &amp; Pine' in text
    assert 'renamer' not in text


def test_profile_rejects_a_taken_display_name(app, client):
    other = make_user('other')
    other.display_name = 'The Gavel'
    me = make_user('me')
    db.session.commit()
    login(client, me)
    resp = _profile_post(client, 'me@test.com', 'the gavel')
    assert 'taken' in resp.get_data(as_text=True)
    assert db.session.get(User, me.id).display_name is None


def test_profile_rejects_an_overlong_display_name(app, client):
    me = make_user('me')
    db.session.commit()
    login(client, me)
    _profile_post(client, 'me@test.com', LONGEST + 'y')
    assert db.session.get(User, me.id).display_name is None


def test_profile_resave_keeps_the_members_own_name(app, client):
    me = make_user('me')
    me.display_name = 'My Name'
    db.session.commit()
    login(client, me)
    _profile_post(client, 'me@test.com', 'My Name')
    assert db.session.get(User, me.id).display_name == 'My Name'


# --- /register: same validator -------------------------------------------

def test_register_rejects_a_display_name_matching_another_username(app, client):
    make_user('taken')
    db.session.commit()
    client.post('/register', data={
        'username': 'newbie', 'email': 'newbie@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'display_name': 'TAKEN',
    })
    assert User.query.filter_by(username='newbie').first() is None


def test_register_stores_a_collapsed_display_name(app, client):
    client.post('/register', data={
        'username': 'newbie', 'email': 'newbie@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'display_name': '  Brad   H. ',
    })
    assert User.query.filter_by(username='newbie').first().display_name == 'Brad H.'


# --- /admin/users: the Commish's edit point ------------------------------

def _rename_url(user):
    return f'/admin/users/{user.id}/display-name'


def test_admin_can_rename_a_member(app, client):
    admin = make_user('commish', is_admin=True)
    member = make_user('member')
    db.session.commit()
    login(client, admin)
    resp = client.post(_rename_url(member),
                       data={'display_name': 'Fourth & Pine', 'csrf_token': 'x'})
    assert resp.status_code == 302
    assert db.session.get(User, member.id).display_name == 'Fourth & Pine'


def test_admin_rename_with_blank_clears_the_name(app, client):
    admin = make_user('commish', is_admin=True)
    member = make_user('member')
    member.display_name = 'Old Name'
    db.session.commit()
    login(client, admin)
    client.post(_rename_url(member), data={'display_name': '  ', 'csrf_token': 'x'})
    assert db.session.get(User, member.id).display_name is None


def test_admin_rename_rejects_a_taken_name(app, client):
    admin = make_user('commish', is_admin=True)
    member = make_user('member')
    other = make_user('other')
    other.display_name = 'The Gavel'
    db.session.commit()
    login(client, admin)
    resp = client.post(_rename_url(member),
                       data={'display_name': 'The Gavel', 'csrf_token': 'x'},
                       follow_redirects=True)
    assert 'taken' in resp.get_data(as_text=True)
    assert db.session.get(User, member.id).display_name is None


def test_non_admin_cannot_rename_anyone(app, client):
    member = make_user('member')
    victim = make_user('victim')
    db.session.commit()
    login(client, member)
    resp = client.post(_rename_url(victim),
                       data={'display_name': 'Pwned', 'csrf_token': 'x'})
    assert resp.status_code == 302
    assert db.session.get(User, victim.id).display_name is None


def test_admin_rename_is_post_only(app, client):
    admin = make_user('commish', is_admin=True)
    member = make_user('member')
    db.session.commit()
    login(client, admin)
    assert client.get(_rename_url(member)).status_code == 405


def test_admin_users_page_carries_a_rename_form_per_member(app, client):
    admin = make_user('commish', is_admin=True)
    member = make_user('member')
    member.display_name = 'Old Name'
    db.session.commit()
    login(client, admin)
    text = client.get('/admin/users').get_data(as_text=True)
    assert _rename_url(member) in text
    assert 'value="Old Name"' in text


# --- join pages: state the name, collect nothing --------------------------

def test_cfb_join_states_the_name_and_collects_none(app, client):
    user = make_user('joiner')
    user.display_name = 'Fourth & Pine'
    db.session.commit()
    login(client, user)
    text = client.get('/cfb/join').get_data(as_text=True)
    assert 'name="display_name"' not in text
    assert 'id="join-current-name"' in text
    assert 'Fourth &amp; Pine' in text


def test_docket_join_states_the_name_and_collects_none(app, client):
    user = make_user('joiner')
    user.display_name = 'The Gavel'
    db.session.commit()
    login(client, user)
    text = client.get('/docket/join').get_data(as_text=True)
    assert 'name="display_name"' not in text
    assert 'id="join-current-name"' in text
    assert 'The Gavel' in text


def test_cfb_join_ignores_a_posted_display_name(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    client.post('/cfb/join', data={'display_name': 'Sneaky', 'csrf_token': 'x'})
    enrollment = CfbEnrollment.query.filter_by(user_id=user.id).first()
    assert enrollment.get_display_name() == 'joiner'
    assert db.session.get(User, user.id).display_name is None


def test_docket_join_ignores_a_posted_display_name(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    client.post('/docket/join', data={'display_name': 'Sneaky', 'csrf_token': 'x'})
    enrollment = DocketEnrollment.query.filter_by(user_id=user.id).first()
    assert enrollment.get_display_name() == 'joiner'
    assert db.session.get(User, user.id).display_name is None
