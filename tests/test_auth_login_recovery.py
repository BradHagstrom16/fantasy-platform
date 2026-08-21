"""Login-recovery affordances for a user who forgot their username.

Covers three changes made together:
  1. login() accepts the account EMAIL as well as the username (username-first,
     email-fallback — deterministic on the rare username==other-email collision).
  2. The password-reset email surfaces the username explicitly.
  3. The reset link is built from SITE_URL (the canonical apex), not from the
     proxied request.host, so it no longer inherits a www-vs-apex mismatch.

Credentials are uuid-derived (not string literals) so GitGuardian's secret
detector doesn't flag throwaway in-memory-DB fixtures — same rationale as
tests/test_auth_worldcup_autojoin.py::_reg_data.
"""
import uuid
from unittest import mock

from extensions import db
from models.user import User


def _make_user(app, username, email, password):
    """Create a committed user directly (bypasses register-form validation so
    the collision edge below can use an '@'-bearing username)."""
    with app.app_context():
        u = User(username=username, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()


def _login(client, identifier, password):
    """POST the login form and follow redirects to the resulting page."""
    return client.post(
        '/login',
        data={'username': identifier, 'password': password, 'csrf_token': 'x'},
        follow_redirects=True,
    )


# --- login by username OR email -------------------------------------------

def test_login_by_username_still_succeeds(app, client):
    """The pre-existing username login path is unchanged."""
    pw = uuid.uuid4().hex
    _make_user(app, 'carol', 'carol@test.com', pw)
    body = _login(client, 'carol', pw).get_data(as_text=True)
    assert 'Logged in successfully' in body


def test_login_by_email_succeeds(app, client):
    """A user can sign in with their account email instead of their username."""
    pw = uuid.uuid4().hex
    _make_user(app, 'alice', 'alice@test.com', pw)
    body = _login(client, 'alice@test.com', pw).get_data(as_text=True)
    assert 'Logged in successfully' in body


def test_login_by_email_is_case_insensitive(app, client):
    """Email login matches regardless of the case the user types."""
    pw = uuid.uuid4().hex
    _make_user(app, 'dave', 'dave@test.com', pw)
    body = _login(client, 'DAVE@TEST.COM', pw).get_data(as_text=True)
    assert 'Logged in successfully' in body


def test_login_wrong_password_shows_generic_error(app, client):
    """A wrong password yields the generic error and no login."""
    pw = uuid.uuid4().hex
    _make_user(app, 'bob', 'bob@test.com', pw)
    body = _login(client, 'bob', 'not-the-password').get_data(as_text=True)
    assert 'Invalid login or password' in body
    assert 'Logged in successfully' not in body


def test_login_unknown_identifier_shows_generic_error(app, client):
    """An unknown identifier is indistinguishable from a wrong password."""
    # No such account: response is identical to the wrong-password case (no
    # enumeration signal from login).
    body = _login(client, 'ghost@nowhere.test', uuid.uuid4().hex).get_data(as_text=True)
    assert 'Invalid login or password' in body


def test_username_takes_precedence_over_email_collision(app, client):
    """If one account's username equals another's email, the username match wins.

    User A's username IS user B's email. Logging in with that string resolves to
    A (username-first short-circuits before the email query), so A's password
    works and B's password does NOT fall through to B.
    """
    pw_a, pw_b = uuid.uuid4().hex, uuid.uuid4().hex
    _make_user(app, 'collide@test.com', 'a-real@test.com', pw_a)  # username looks like an email
    _make_user(app, 'realbob', 'collide@test.com', pw_b)          # email == A's username

    # Order matters: a SUCCESSFUL login caches current_user on the app-context
    # `g` shared by the conftest fixture, which would make a subsequent request
    # short-circuit on is_authenticated. So exercise the denied (no login_user
    # side effect) attempt first, then the successful one — each on its own
    # client for a clean cookie jar.
    denied = _login(app.test_client(), 'collide@test.com', pw_b).get_data(as_text=True)
    assert 'Invalid login or password' in denied  # username match (A) wins; never falls through to B

    ok = _login(app.test_client(), 'collide@test.com', pw_a).get_data(as_text=True)
    assert 'Logged in successfully' in ok  # the colliding string resolves to A


def test_login_page_labels_field_username_or_email(client):
    """The login form advertises that the field accepts a username or email."""
    body = client.get('/login').get_data(as_text=True)
    assert 'Username or email' in body


# --- reset email: username shown + link built from SITE_URL ----------------

def test_reset_email_shows_username_and_uses_site_url(app, client):
    """The reset email surfaces the username and builds links from SITE_URL."""
    site_url = 'https://canonical.example'
    app.config['SITE_URL'] = site_url
    _make_user(app, 'reseeker', 'reseeker@test.com', uuid.uuid4().hex)

    captured = {}

    def _capture(to, subject, plain, html):
        captured.update(to=to, subject=subject, plain=plain, html=html)

    with mock.patch('core.auth.routes.send_platform_email', _capture):
        resp = client.post(
            '/forgot-password',
            data={'email': 'reseeker@test.com', 'csrf_token': 'x'},
        )

    assert resp.status_code == 302  # anti-enumeration redirect to login
    # Username surfaced in both parts so the user can recover their identity.
    assert 'reseeker' in captured['plain']
    assert 'reseeker' in captured['html']
    # Reset link built from SITE_URL (apex), not the proxied host.
    assert (site_url + '/reset-password/') in captured['plain']
    assert (site_url + '/reset-password/') in captured['html']
    # And the emailed seal image is SITE_URL-rooted too.
    assert (site_url + '/static/') in captured['html']


def test_reset_email_escapes_username_in_html(app, client):
    """The HTML email is a .j2 template (NOT autoescaped by Flask), and the
    username is user-controlled, so it must be explicitly escaped or it is a
    stored-injection vector."""
    _make_user(app, '<b>evil</b>', 'xss@test.com', uuid.uuid4().hex)

    captured = {}
    with mock.patch('core.auth.routes.send_platform_email',
                    lambda to, subject, plain, html: captured.update(plain=plain, html=html)):
        client.post('/forgot-password', data={'email': 'xss@test.com', 'csrf_token': 'x'})

    assert '<b>evil</b>' not in captured['html']       # raw markup must not survive
    assert '&lt;b&gt;evil&lt;/b&gt;' in captured['html']  # escaped form present


def test_forgot_password_does_not_reveal_account_existence(app):
    """A registered and an unregistered email get the identical redirect + flash,
    so the forgot-password form never signals which addresses have an account."""
    _make_user(app, 'known', 'known@test.com', uuid.uuid4().hex)

    def _forgot(email, **kw):
        c = app.test_client()  # fresh session per call — no flash bleed across posts
        with mock.patch('core.auth.routes.send_platform_email', lambda *a, **k: None):
            return c.post('/forgot-password',
                          data={'email': email, 'csrf_token': 'x'}, **kw)

    # Immediate redirect is identical whether or not the account exists.
    known, unknown = _forgot('known@test.com'), _forgot('nobody@test.com')
    assert known.status_code == unknown.status_code == 302
    assert known.headers['Location'] == unknown.headers['Location']

    # ...and both render the same anti-enumeration flash on the login page.
    msg = 'If that email is registered'
    assert msg in _forgot('known@test.com', follow_redirects=True).get_data(as_text=True)
    assert msg in _forgot('nobody@test.com', follow_redirects=True).get_data(as_text=True)
