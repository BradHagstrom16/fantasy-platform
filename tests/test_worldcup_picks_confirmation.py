"""Tests for the picks confirmation email.

Service: games/worldcup/services/notifications.send_picks_confirmation
Trigger: the /worldcup/picks POST success path (routes.picks).

Mock target is the service module's send_platform_email read-site, per the
established pattern in tests/test_worldcup_notifications.py.
"""
from collections import defaultdict
from datetime import datetime, timezone
from unittest import mock

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ


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


@pytest.fixture()
def pre_deadline(monkeypatch):
    """Pin the picks route pre-deadline regardless of the real date.

    routes.py imports TOURNAMENT_DEADLINE_UTC directly, so the route
    read-site is games.worldcup.routes (see CLAUDE.md mocking notes).
    """
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC',
        datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


# Valid 9-team roster matching TIER_PICK_COUNTS (2-1-2-2-2), with real
# tier multipliers and a FIFA→ISO mapped code (NED→nl) in the mix.
_ROSTER_SPEC = [
    ('BRA', 1, 1.0, 'A'), ('FRA', 1, 1.0, 'B'),
    ('NED', 2, 1.5, 'C'),
    ('SEN', 3, 2.5, 'D'), ('KOR', 3, 2.5, 'E'),
    ('PER', 4, 4.0, 'F'), ('CAN', 4, 4.0, 'G'),
    ('PAN', 5, 7.0, 'H'), ('IRN', 5, 7.0, 'I'),
]


def _seed_teams():
    from tests._worldcup_fixtures import make_team
    return [
        make_team(code, tier=tier, multiplier=mult, group_letter=group)
        for code, tier, mult, group in _ROSTER_SPEC
    ]


def _seed_enrollment(email='picker@example.com', picks_submitted=False,
                     usa_goals_guess=7, with_picks=False, teams=None):
    from tests._worldcup_fixtures import make_user, make_enrollment, make_pick
    user = make_user(email=email, display_name='Picker')
    enrollment = make_enrollment(
        user, picks_submitted=picks_submitted, usa_goals_guess=usa_goals_guess,
    )
    if with_picks:
        for team in (teams or []):
            make_pick(enrollment, team)
    return user, enrollment


def _picks_form(teams, usa_goals='7'):
    form = defaultdict(list)
    for team in teams:
        form[f'tier_{team.tier}'].append(str(team.id))
    form['usa_goals_guess'] = usa_goals
    form['csrf_token'] = 'placeholder'
    return dict(form)


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.get_id()  # auth_id, never str(user.id)
        sess['_fresh'] = True


# ---------------------------------------------------------------------------
# Service-level: content
# ---------------------------------------------------------------------------

def test_confirmation_html_contains_full_roster(app):
    """HTML carries all 9 teams, tier names, multipliers, groups, and flags."""
    from games.worldcup.services.notifications import send_picks_confirmation
    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(with_picks=True, teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            ok = send_picks_confirmation(enrollment)

    assert ok is True
    mock_send.assert_called_once()
    to, subject, plain, html = mock_send.call_args[0]
    assert to == 'picker@example.com'
    for code, _, _, _ in _ROSTER_SPEC:
        assert code in html
    for tier_name in ('Favorites', 'Contenders', 'Dark Horses',
                      'Underdogs', 'Wildcards'):
        assert tier_name in html
    for mult_str in ('×1', '×1.5', '×2.5', '×4', '×7'):
        assert mult_str in html
    assert 'Group H' in html
    # Flags are hosted SVGs, never emoji; NED maps to nl via _FIFA_TO_ISO.
    assert '/static/flags/br.svg' in html
    assert '/static/flags/nl.svg' in html


def test_confirmation_contains_tiebreaker_and_deadline(app):
    """Tiebreaker guess + edit-window deadline (in CT) appear in both bodies."""
    from games.worldcup.services.notifications import send_picks_confirmation
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)
    deadline_day = deadline_ct.strftime('%B %-d')  # e.g. "June 11"

    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(usa_goals_guess=7, with_picks=True,
                                         teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            send_picks_confirmation(enrollment)

    _, _, plain, html = mock_send.call_args[0]
    for body in (plain, html):
        assert 'USA goals' in body
        assert deadline_day in body
        assert 'CT' in body


def test_confirmation_subject_first_vs_update(app):
    """is_update flips the subject so inbox history reads correctly."""
    from games.worldcup.services.notifications import send_picks_confirmation
    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(with_picks=True, teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            send_picks_confirmation(enrollment, is_update=False)
            send_picks_confirmation(enrollment, is_update=True)

    first_subject = mock_send.call_args_list[0][0][1]
    update_subject = mock_send.call_args_list[1][0][1]
    assert first_subject == 'Your World Cup picks are in'
    assert update_subject == 'Your updated World Cup picks'


def test_confirmation_plain_body_contains_roster(app):
    """Plain-text fallback mirrors the roster, tiers, and picks link."""
    from games.worldcup.services.notifications import send_picks_confirmation
    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(with_picks=True, teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            send_picks_confirmation(enrollment)

    _, _, plain, _ = mock_send.call_args[0]
    for code, _, _, _ in _ROSTER_SPEC:
        assert code in plain
    assert 'Favorites' in plain
    assert 'Wildcards' in plain
    assert '/worldcup/picks' in plain


def test_confirmation_cta_links_to_picks(app):
    """HTML CTA points back at the picks page, not the leaderboard."""
    from games.worldcup.services.notifications import send_picks_confirmation
    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(with_picks=True, teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            send_picks_confirmation(enrollment)

    _, _, _, html = mock_send.call_args[0]
    assert '/worldcup/picks' in html


def test_confirmation_never_raises(app):
    """A render failure is caught and logged; the caller sees False."""
    from games.worldcup.services.notifications import send_picks_confirmation
    with app.app_context():
        teams = _seed_teams()
        _, enrollment = _seed_enrollment(with_picks=True, teams=teams)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.render_template',
            side_effect=Exception('template boom'),
        ), mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
        ) as mock_send:
            ok = send_picks_confirmation(enrollment)

    assert ok is False
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Route-level: trigger wiring
# ---------------------------------------------------------------------------

def test_first_submission_sends_confirmation(app, client, pre_deadline):
    """A valid first POST fires exactly one email with the first-save subject."""
    with app.app_context():
        teams = _seed_teams()
        user, _ = _seed_enrollment(picks_submitted=False)
        db.session.commit()
        form = _picks_form(teams)
        _login(client, user)

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            resp = client.post('/worldcup/picks', data=form)

    assert resp.status_code == 302
    mock_send.assert_called_once()
    to, subject, plain, html = mock_send.call_args[0]
    assert to == 'picker@example.com'
    assert subject == 'Your World Cup picks are in'
    for code, _, _, _ in _ROSTER_SPEC:
        assert code in html


def test_resubmission_sends_update_subject(app, client, pre_deadline):
    """Editing picks pre-deadline re-fires the email with the update subject."""
    with app.app_context():
        teams = _seed_teams()
        user, _ = _seed_enrollment(picks_submitted=True, with_picks=True,
                                   teams=teams)
        db.session.commit()
        form = _picks_form(teams)
        _login(client, user)

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            resp = client.post('/worldcup/picks', data=form)

    assert resp.status_code == 302
    mock_send.assert_called_once()
    assert mock_send.call_args[0][1] == 'Your updated World Cup picks'


def test_validation_failure_sends_no_email(app, client, pre_deadline):
    """An invalid POST (missing tiebreaker) never reaches the send."""
    with app.app_context():
        teams = _seed_teams()
        user, _ = _seed_enrollment(picks_submitted=False)
        db.session.commit()
        form = _picks_form(teams, usa_goals='')  # tiebreaker missing
        _login(client, user)

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
        ) as mock_send:
            resp = client.post('/worldcup/picks', data=form)

    assert resp.status_code == 200  # re-rendered with errors
    mock_send.assert_not_called()


def test_send_failure_does_not_break_submission(app, client, pre_deadline):
    """SMTP failure: picks still persist and the redirect still happens."""
    from games.worldcup.models import WorldCupPick
    with app.app_context():
        teams = _seed_teams()
        user, enrollment = _seed_enrollment(picks_submitted=False)
        enrollment_id = enrollment.id
        db.session.commit()
        form = _picks_form(teams)
        _login(client, user)

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=False,
        ):
            resp = client.post('/worldcup/picks', data=form)

        saved = WorldCupPick.query.filter_by(enrollment_id=enrollment_id).count()

    assert resp.status_code == 302
    assert saved == 9
