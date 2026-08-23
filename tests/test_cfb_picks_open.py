"""CFB Survivor — the "Picks Are Open" announcement email.

The season-open email that did not exist before launch: when spreads first
land on the active week (the Tuesday freeze), every enrolled player is told
picks are open — exactly once, latched on ``CfbWeek.picks_open_notified``.
Unlike the T-25h/T-1h deadline reminders, this goes to EVERYONE (eliminated
players and players who already picked included).

Mail is faked at the reminders read-site (``games.cfb.services.reminders``),
per the platform mocking convention; patching utils.email would be a no-op.
"""
from unittest.mock import Mock, patch

from extensions import db
from games.cfb.models import CfbWeek
from games.cfb.services.automation import run_spread_update
from games.cfb.services.reminders import send_picks_open_email
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)


def _api_response(payload):
    """A mock Odds-API /odds response carrying ``payload``."""
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = payload
    resp.headers = {}
    return resp


def _draftkings_event(point=-7.5, event_id='ev1',
                      home_api='Alabama Crimson Tide',
                      away_api='Georgia Bulldogs'):
    """One /odds event with a single DraftKings spreads market."""
    return {
        'id': event_id,
        'home_team': home_api,
        'away_team': away_api,
        'bookmakers': [{'key': 'draftkings', 'markets': [{
            'key': 'spreads',
            'outcomes': [
                {'name': home_api, 'point': point},
                {'name': away_api, 'point': -point},
            ],
        }]}],
    }


def _capture(result=True):
    """Patch the picks-open send-site; collect each message. ``result`` is
    what the fake send returns (False models a total mail outage)."""
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'html': html})
        return result

    return calls, patch(
        'games.cfb.services.reminders.send_platform_email', side_effect=fake)


# ── Sender: reaches everyone, once ───────────────────────────────────────

def test_picks_open_email_goes_to_every_enrollee(app):
    """Not a 'you haven't picked' reminder — an eliminated player and a
    player who already picked both still get the announcement."""
    week = make_week(1, is_active=True)
    make_enrollment(make_user('plain'))
    make_enrollment(make_user('gone'), eliminated=True)
    picked = make_user('picked')
    make_enrollment(picked)
    team = make_team('Alabama')
    make_game(week, team, make_team('Georgia'), spread=-3.0)
    make_pick(picked, week, team)
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        sent = send_picks_open_email(week.id)

    assert sent == 3
    assert {c['to'] for c in calls} == {
        'plain@test.com', 'gone@test.com', 'picked@test.com'}


def test_picks_open_email_subject_and_pick_link(app):
    """Subject names the game + week; the CTA links the week's pick page
    built from SITE_URL (never request.host)."""
    app.config['SITE_URL'] = 'https://cccfantasy.com'
    week = make_week(3, is_active=True)
    make_enrollment(make_user('p1'))
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        send_picks_open_email(week.id)

    assert calls[0]['subject'] == 'Picks Are Open: CFB Survivor — Week 3'
    assert 'https://cccfantasy.com/cfb/pick/3' in calls[0]['html']


# ── Trigger: fires when spreads land on the active week ──────────────────

@patch('games.cfb.services.odds_api.requests.get')
@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_spread_update_fires_picks_open_once(mock_admin, mock_get, app):
    """The Tuesday spreads run opens picks and announces it — and a later
    run over the now-locked week does not announce again."""
    app.config['ODDS_API_KEY'] = 'test-key'
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    week = make_week(1, is_active=True)
    game = make_game(week, make_team('Alabama'), make_team('Georgia'))
    game.api_event_id = 'ev1'
    make_enrollment(make_user('p1'))
    db.session.commit()
    mock_get.return_value = _api_response([_draftkings_event()])

    calls, patcher = _capture()
    with patcher:
        run_spread_update()
        assert len(calls) == 1
        assert db.session.get(CfbWeek, week.id).picks_open_notified is True
        run_spread_update()          # spread locked, week already notified
        assert len(calls) == 1       # no second announcement


@patch('games.cfb.services.odds_api.requests.get')
@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_no_picks_open_until_a_spread_lands(mock_admin, mock_get, app):
    """No spread landed (no matching event) → no announcement, flag stays
    False so the next run can still fire it."""
    app.config['ODDS_API_KEY'] = 'test-key'
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    week = make_week(1, is_active=True)
    game = make_game(week, make_team('Alabama'), make_team('Georgia'))
    game.api_event_id = 'ev1'
    make_enrollment(make_user('p1'))
    db.session.commit()
    mock_get.return_value = _api_response([])   # no events → no spread

    calls, patcher = _capture()
    with patcher:
        run_spread_update()

    assert calls == []
    assert db.session.get(CfbWeek, week.id).picks_open_notified is False


@patch('games.cfb.services.odds_api.requests.get')
@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_picks_open_not_latched_when_every_send_fails(mock_admin, mock_get,
                                                      app):
    """A mail outage must not consume the latch — the next run retries."""
    app.config['ODDS_API_KEY'] = 'test-key'
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    week = make_week(1, is_active=True)
    game = make_game(week, make_team('Alabama'), make_team('Georgia'))
    game.api_event_id = 'ev1'
    make_enrollment(make_user('p1'))
    db.session.commit()
    mock_get.return_value = _api_response([_draftkings_event()])

    calls, patcher = _capture(result=False)   # every send fails
    with patcher:
        run_spread_update()

    assert len(calls) == 1                     # it tried
    assert db.session.get(CfbWeek, week.id).picks_open_notified is False


def test_new_week_starts_unnotified(app):
    """The latch column defaults False for a freshly created week."""
    week = make_week(1)
    db.session.commit()
    assert week.picks_open_notified is False
