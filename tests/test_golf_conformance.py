"""PR 5 — Golf routes, standings & email conformance (TDD).

Mirrors the CFB §7 conformance work. Locks the platform-integration fixes:

- Golf-scoped standings (ADR-036): index() shows only current-season
  GolfEnrollment rows, never every platform user.
- Enrollment-scoped mail: picks-open / reminder / recap mail reaches only
  current-season golf enrollees, never World-Cup/CFB-only accounts.
- Avatars: tournament_detail standings render user.get_avatar() before the
  display name (crown-for-admins enforced by get_avatar()).
- Admin override hardening: the POST is server-validated against field
  membership + season usage (excluding the pick's own players); the GET
  used-list excludes the existing pick's players; a validation failure never
  mutates the pick.
- Complete-vs-finalized gating: tournament_detail switches to the final
  earnings mode on results_finalized, not status == 'complete'.
- Email HTML safety: dynamic user/tournament/golfer names are escaped.

Golf tests run against in-memory SQLite via create_app('testing').
The confirm-before-reresolve gate the standalone carries is intentionally
NOT ported here — see test_admin_override_complete_tournament_reresolves_
immediately for the reconciliation of the roadmap's named
test_admin_override_requires_confirm_for_complete.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app import create_app
from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services import reminders as reminders_mod
from games.golf.services.reminders import (
    get_users_without_picks,
    send_picks_open_email,
    send_results_recap_email,
)
from models.user import User
from tests._registry_helpers import set_status as _set_status

SEASON = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    # Pin the season so seed helpers and route/query season-scoping agree even
    # if the testing-config default ever drifts.
    app.config['SEASON_YEAR'] = SEASON
    # The mail functions early-return without credentials; give them dummies so
    # the enrollment-scoping / escaping paths actually run (send is monkeypatched).
    app.config['EMAIL_ADDRESS'] = 'commish@test.com'
    app.config['EMAIL_PASSWORD'] = 'x'
    app.config['SITE_URL'] = 'http://localhost'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_user(username='golfer', is_admin=False, display_name=None, avatar=None):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin,
             display_name=display_name, avatar_emoji=avatar)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _make_enrollment(user, season_year=SEASON):
    e = GolfEnrollment(user_id=user.id, season_year=season_year, total_points=0)
    db.session.add(e)
    db.session.commit()
    return e


def _make_tournament(name='Test Open', is_major=False, is_team_event=False,
                     status='complete', results_finalized=False, season_year=SEASON):
    now = datetime.now(UTC)
    t = GolfTournament(
        api_tourn_id=f'T-{name}',
        name=name,
        season_year=season_year,
        start_date=now - timedelta(days=4),
        end_date=now - timedelta(days=1),
        pick_deadline=now - timedelta(days=4),
        purse=10_000_000,
        is_major=is_major,
        is_team_event=is_team_event,
        status=status,
        results_finalized=results_finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_player(api_id, first, last):
    p = GolfPlayer(api_player_id=api_id, first_name=first, last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


def _add_to_field(tournament, player):
    fe = GolfTournamentField(tournament_id=tournament.id, player_id=player.id)
    db.session.add(fe)
    db.session.commit()
    return fe


def _mark_used(user, player, season_year=SEASON):
    usage = GolfSeasonPlayerUsage(
        user_id=user.id, player_id=player.id, season_year=season_year
    )
    db.session.add(usage)
    db.session.commit()
    return usage


def _make_result(tournament, player, status='complete', rounds_completed=4,
                 earnings=0, final_position='1'):
    r = GolfTournamentResult(
        tournament_id=tournament.id,
        player_id=player.id,
        status=status,
        rounds_completed=rounds_completed,
        earnings=earnings,
        final_position=final_position,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _make_pick(user, tournament, primary, backup, **kwargs):
    pick = GolfPick(
        user_id=user.id,
        tournament_id=tournament.id,
        primary_player_id=primary.id,
        backup_player_id=backup.id,
        **kwargs,
    )
    db.session.add(pick)
    db.session.commit()
    return pick


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _patch_mail(monkeypatch):
    """Capture send_platform_email calls made from the reminders module."""
    captured = []

    def _fake_send(to, subject, plain, html=None, *args, **kwargs):
        captured.append({'to': to, 'subject': subject, 'plain': plain, 'html': html})
        return True

    monkeypatch.setattr(reminders_mod, 'send_platform_email', _fake_send)
    return captured


# ============================================================================
# Golf-scoped standings (ADR-036)
# ============================================================================

def test_index_standings_scoped_to_golf_enrollments(app, client):
    """index() lists only current-season golf enrollees, not every platform user."""
    enrolled = _make_user('enrolled_golfer', display_name='EnrolledGolfer')
    _make_enrollment(enrolled)
    # A user in another game only — never enrolled in golf.
    _make_user('worldcup_only', display_name='WorldCupOnly')

    resp = client.get('/golf/')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'EnrolledGolfer' in body
    assert 'WorldCupOnly' not in body


def test_index_standings_prior_season_enrollment_excluded(app, client):
    """A prior-season enrollment must not appear on the current-season board."""
    current = _make_user('current', display_name='CurrentSeason')
    _make_enrollment(current)
    old = _make_user('old', display_name='OldSeason')
    _make_enrollment(old, season_year=SEASON - 1)

    body = client.get('/golf/').get_data(as_text=True)
    assert 'CurrentSeason' in body
    assert 'OldSeason' not in body


# ============================================================================
# Enrollment-scoped mail
# ============================================================================

def test_picks_open_mail_only_golf_enrollees(app, monkeypatch):
    captured = _patch_mail(monkeypatch)
    enrolled = _make_user('enrolled')
    _make_enrollment(enrolled)
    _make_user('non_golf')  # no golf enrollment
    tournament = _make_tournament(status='upcoming')

    sent = send_picks_open_email(tournament.id)

    recipients = {c['to'] for c in captured}
    assert enrolled.email in recipients
    assert 'non_golf@test.com' not in recipients
    assert sent == 1


def test_reminder_mail_only_golf_enrollees(app):
    """get_users_without_picks returns only current-season enrollees with no pick."""
    enrolled = _make_user('enrolled')
    _make_enrollment(enrolled)
    _make_user('non_golf')  # not enrolled
    old = _make_user('old_season')
    _make_enrollment(old, season_year=SEASON - 1)
    tournament = _make_tournament(status='active')

    recipients = get_users_without_picks(tournament.id, SEASON)
    ids = {u.id for u in recipients}
    assert enrolled.id in ids
    assert 'non_golf' not in {u.username for u in recipients}
    assert old.id not in ids


def test_reminder_mail_excludes_users_who_picked(app):
    picked = _make_user('picked')
    _make_enrollment(picked)
    waiting = _make_user('waiting')
    _make_enrollment(waiting)
    tournament = _make_tournament(status='active')
    p1, p2 = _make_player('P1', 'A', 'One'), _make_player('P2', 'B', 'Two')
    _make_pick(picked, tournament, p1, p2)

    recipients = get_users_without_picks(tournament.id, SEASON)
    ids = {u.id for u in recipients}
    assert waiting.id in ids
    assert picked.id not in ids


def test_recap_mail_only_golf_enrollees(app, monkeypatch):
    captured = _patch_mail(monkeypatch)
    enrolled = _make_user('enrolled')
    _make_enrollment(enrolled)
    _make_user('non_golf')  # not enrolled
    tournament = _make_tournament(status='complete', results_finalized=True)

    sent = send_results_recap_email(tournament.id)

    recipients = {c['to'] for c in captured}
    assert enrolled.email in recipients
    assert 'non_golf@test.com' not in recipients
    assert sent == 1


def test_recap_null_total_points_renders_zero(app, monkeypatch):
    """An enrollment with NULL total_points must not crash the recap formatter.

    The column has ``default=0`` but not ``nullable=False``, so ``None`` is
    technically possible.  The standings builder normalises it to 0 so the
    currency format (``$0``) never receives ``None``.
    """
    captured = _patch_mail(monkeypatch)
    member = _make_user('null_pts')
    enrollment = _make_enrollment(member)
    enrollment.total_points = None
    db.session.commit()

    tournament = _make_tournament(status='complete', results_finalized=True)
    sent = send_results_recap_email(tournament.id)

    assert sent == 1
    assert captured
    assert '$0' in captured[0]['plain']


# ============================================================================
# Email HTML escaping
# ============================================================================

def test_email_html_escapes_dynamic_values(app, monkeypatch):
    """Tournament names are HTML-escaped in the picks-open letter.

    (Display names left broadcasts with the Club Letter's greeting policy —
    the recap's greeting covers them in the test below.)
    """
    captured = _patch_mail(monkeypatch)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(name='The <Open> & Masters', status='upcoming')

    send_picks_open_email(tournament.id)

    assert captured, 'no email captured'
    html = captured[0]['html']
    # Raw markup from the tournament name must not survive into the HTML body.
    assert 'The <Open>' not in html
    # …and the escaped form must be present.
    assert 'The &lt;Open&gt; &amp; Masters' in html


def test_recap_email_escapes_display_name(app, monkeypatch):
    """The recap greets by display name; a hostile name is escaped."""
    captured = _patch_mail(monkeypatch)
    hostile = _make_user('hostile', display_name='Evil<script>&amp')
    _make_enrollment(hostile)
    tournament = _make_tournament(status='complete', results_finalized=True)

    send_results_recap_email(tournament.id)

    assert captured, 'no email captured'
    html = captured[0]['html']
    assert 'Evil<script>' not in html
    assert 'Evil&lt;script&gt;' in html


def test_recap_email_escapes_golfer_name(app, monkeypatch):
    """Golfer names interpolated into the recap HTML are escaped."""
    captured = _patch_mail(monkeypatch)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='complete', results_finalized=True)
    primary = _make_player('P1', 'Rory', '<b>McIlroy</b>')
    backup = _make_player('P2', 'Jon', 'Rahm')
    _add_to_field(tournament, primary)
    _add_to_field(tournament, backup)
    _make_result(tournament, primary, earnings=100000, final_position='1')
    pick = _make_pick(member, tournament, primary, backup)
    pick.active_player_id = primary.id
    pick.points_earned = 100000
    db.session.commit()

    send_results_recap_email(tournament.id)

    html = captured[0]['html']
    assert '<b>McIlroy</b>' not in html
    assert '&lt;b&gt;McIlroy&lt;/b&gt;' in html


# ============================================================================
# Avatars on tournament_detail standings
# ============================================================================

def test_tournament_detail_renders_avatar(app, client):
    """The player column renders get_avatar() immediately before the display name."""
    member = _make_user('member', display_name='ZorpTheGolfer', avatar='🎯')
    _make_enrollment(member)
    tournament = _make_tournament(status='complete', results_finalized=True)
    p1, p2 = _make_player('P1', 'A', 'One'), _make_player('P2', 'B', 'Two')
    _make_pick(member, tournament, p1, p2)

    body = client.get(f'/golf/tournament/{tournament.id}').get_data(as_text=True)
    assert '🎯' in body
    assert 'ZorpTheGolfer' in body
    # Avatar renders before the name.
    assert body.index('🎯') < body.index('ZorpTheGolfer')


# ============================================================================
# Complete-vs-finalized gating
# ============================================================================

def test_final_mode_gated_on_results_finalized(app, client):
    """Complete-but-unfinalized shows Projected; a finalized one shows Earnings.

    Two tournaments so the assertion doesn't depend on a mid-test mutation being
    visible across the shared fixture session.
    """
    member = _make_user('member')
    _make_enrollment(member)
    p1, p2 = _make_player('P1', 'A', 'One'), _make_player('P2', 'B', 'Two')

    # Complete but NOT finalized → projected mode.
    pending = _make_tournament(name='Pending Open', status='complete',
                               results_finalized=False)
    _add_to_field(pending, p1)
    _add_to_field(pending, p2)
    _make_result(pending, p1, earnings=100000, final_position='1')
    _make_pick(member, pending, p1, p2)

    body = client.get(f'/golf/tournament/{pending.id}').get_data(as_text=True)
    assert 'Projected' in body
    assert 'Earnings' not in body

    # Finalized → earnings mode.
    p3, p4 = _make_player('P3', 'C', 'Three'), _make_player('P4', 'D', 'Four')
    final = _make_tournament(name='Final Open', status='complete',
                             results_finalized=True)
    _add_to_field(final, p3)
    _add_to_field(final, p4)
    _make_result(final, p3, earnings=100000, final_position='1')
    _make_pick(member, final, p3, p4, active_player_id=p3.id, points_earned=100000)

    body2 = client.get(f'/golf/tournament/{final.id}').get_data(as_text=True)
    assert 'Earnings' in body2


# ============================================================================
# Admin override hardening
# ============================================================================

def _override_post(client, tournament, user, primary, backup, note='t'):
    return client.post('/golf/admin/override-pick', data={
        'csrf_token': 'x',
        'tournament_id': tournament.id,
        'user_id': user.id,
        'primary_player_id': primary.id,
        'backup_player_id': backup.id,
        'override_note': note,
    }, follow_redirects=True)


def test_admin_override_rejects_used_or_non_field_player(app, client, monkeypatch):
    """POST validation blocks non-field and already-used golfers; nothing mutates."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='upcoming')
    in_field_a = _make_player('A', 'In', 'FieldA')
    in_field_b = _make_player('B', 'In', 'FieldB')
    used = _make_player('U', 'Already', 'Used')
    off_field = _make_player('O', 'Off', 'Field')
    _add_to_field(tournament, in_field_a)
    _add_to_field(tournament, in_field_b)
    _add_to_field(tournament, used)
    _mark_used(member, used)  # used in a prior tournament this season
    _login(client, admin)

    # Non-field primary → rejected, no pick created.
    resp = _override_post(client, tournament, member, off_field, in_field_b)
    assert resp.status_code == 200
    assert 'not in the tournament field' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first() is None

    # Already-used primary (in field) → rejected, no pick created.
    resp = _override_post(client, tournament, member, used, in_field_b)
    assert 'already been used' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first() is None

    # The BACKUP is validated the same way — non-field backup → rejected.
    resp = _override_post(client, tournament, member, in_field_a, off_field)
    assert 'not in the tournament field' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first() is None

    # Already-used backup → rejected.
    resp = _override_post(client, tournament, member, in_field_a, used)
    assert 'already been used' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first() is None


def test_admin_override_rejection_does_not_mutate_existing_pick(app, client, monkeypatch):
    """A rejected override leaves an existing valid pick untouched (validate-before-mutate)."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='upcoming')
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    off_field = _make_player('O', 'Off', 'Field')
    _add_to_field(tournament, a)
    _add_to_field(tournament, b)
    _make_pick(member, tournament, a, b)
    _login(client, admin)

    # Attempt to override to an off-field primary → rejected.
    _override_post(client, tournament, member, off_field, b)

    with app.app_context():
        pick = GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first()
        assert pick.primary_player_id == a.id  # unchanged
        assert pick.backup_player_id == b.id


def test_admin_override_valid_submission_saves(app, client, monkeypatch):
    """A valid override for an upcoming tournament creates the pick."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='upcoming')
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    _add_to_field(tournament, a)
    _add_to_field(tournament, b)
    _login(client, admin)

    resp = _override_post(client, tournament, member, a, b)
    assert resp.status_code == 200
    with app.app_context():
        pick = GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first()
        assert pick is not None
        assert pick.admin_override is True


def test_admin_override_rejects_unenrolled_user(app, client, monkeypatch):
    """Override refuses a non-enrolled user (never creates enrollment rows)."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    stranger = _make_user('stranger')  # no golf enrollment
    tournament = _make_tournament(status='upcoming')
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    _add_to_field(tournament, a)
    _add_to_field(tournament, b)
    _login(client, admin)

    _override_post(client, tournament, stranger, a, b)
    with app.app_context():
        assert GolfEnrollment.query.filter_by(user_id=stranger.id).first() is None
        assert GolfPick.query.filter_by(user_id=stranger.id).first() is None


def test_admin_override_rejects_cross_season_tournament(app, client, monkeypatch):
    """A tournament from another season can't be overridden via a crafted POST."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)  # current season only
    old = _make_tournament(name='Last Year Open', status='complete',
                           season_year=SEASON - 1)
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    _add_to_field(old, a)
    _add_to_field(old, b)
    _login(client, admin)

    resp = _override_post(client, old, member, a, b)
    assert 'not eligible for admin overrides' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=old.id).first() is None


def test_admin_override_complete_resolution_failure_rolls_back(app, client, monkeypatch):
    """A complete-tournament override that can't resolve persists nothing."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='complete', results_finalized=True)
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    _add_to_field(tournament, a)
    _add_to_field(tournament, b)
    # No GolfTournamentResult rows → resolve_pick() returns False.
    _login(client, admin)

    resp = _override_post(client, tournament, member, a, b)
    assert 'could not be resolved' in resp.get_data(as_text=True)
    with app.app_context():
        assert GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first() is None


def test_admin_override_excludes_own_pick_players_from_used_ids(app, client, monkeypatch):
    """The GET form excludes the pick's own players from the used list.

    A player used only because it IS the existing pick keeps being selectable;
    a player used elsewhere still renders disabled.
    """
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    tournament = _make_tournament(status='complete', results_finalized=True)
    own = _make_player('OWN', 'Own', 'Pick')
    backup = _make_player('BKP', 'Own', 'Backup')
    elsewhere = _make_player('ELS', 'Used', 'Elsewhere')
    for p in (own, backup, elsewhere):
        _add_to_field(tournament, p)
    _make_pick(member, tournament, own, backup)
    _mark_used(member, own)        # the pick's own player is "used"
    _mark_used(member, elsewhere)  # a genuinely locked player
    _login(client, admin)

    body = client.get(
        f'/golf/admin/override-pick?tournament_id={tournament.id}&user_id={member.id}'
    ).get_data(as_text=True)

    # own pick's player is NOT marked used; the elsewhere-locked player IS.
    assert f'{own.full_name()} (used)' not in body
    assert f'{elsewhere.full_name()} (used)' in body


def test_admin_override_complete_tournament_reresolves_immediately(app, client, monkeypatch):
    """Reconciles the roadmap's test_admin_override_requires_confirm_for_complete.

    The standalone gates a completed-tournament override behind a two-step
    confirm preview. That confirm gate is a new interaction surface (a preview
    screen), out of scope for this conformance PR and deferred to a later
    hardening/UI slice. This test documents+locks the CURRENT behavior: a valid
    override on a complete tournament re-resolves and commits in one step.
    """
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    enrollment = _make_enrollment(member)
    tournament = _make_tournament(status='complete', results_finalized=True)
    a = _make_player('A', 'Alpha', 'One')
    b = _make_player('B', 'Bravo', 'Two')
    _add_to_field(tournament, a)
    _add_to_field(tournament, b)
    _make_result(tournament, a, earnings=250000, final_position='1')
    _make_result(tournament, b, earnings=0, final_position='CUT', status='cut')
    _login(client, admin)

    resp = _override_post(client, tournament, member, a, b)
    assert resp.status_code == 200
    with app.app_context():
        pick = GolfPick.query.filter_by(
            user_id=member.id, tournament_id=tournament.id).first()
        assert pick is not None
        assert pick.points_earned == 250000  # re-resolved immediately, no confirm
        e = db.session.get(GolfEnrollment, enrollment.id)
        assert e.total_points == 250000
