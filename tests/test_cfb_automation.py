"""
CFB Survivor automation/ops regression locks (pre-launch audit 2026-06-10, PR 2).

Covers audit §5/§6 driven by §8 items 13-16: ADMIN_EMAIL alert routing
(Top-5 #5), run_setup orphan-week retry, the Thu→Wed import window,
silent-drop logging + team-name coverage validation, bookmaker
fallback/NULL-spread surfacing, the DQ-6 manual-spread lock, the
stuck-week alert in run_scores, ScoreFetcher matching, and the
week short-label map.

All Odds-API traffic is mocked at the requests boundary
(games.cfb.services.automation.requests / ...score_fetcher.requests).
"""
import pytest
from unittest.mock import Mock, patch

from app import create_app
from extensions import db
from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek, CfbGame, CfbPick
from tests._cfb_fixtures import (
    make_user, make_enrollment, make_team, make_week, make_game, make_pick,
)


@pytest.fixture()
def app():
    """App fixture: testing config + in-memory schema per test."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client bound to the app fixture."""
    return app.test_client()


def _api_response(payload, status_code=200, headers=None):
    """Build a mock requests.Response carrying a JSON payload."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.headers = headers or {}
    return resp


# ── Top-5 #5 — admin alerts route to a real inbox ────────────────────────

def test_admin_email_config_key_is_plumbed(app):
    """ADMIN_EMAIL must have an os.environ.get() line in config.py's base
    Config — the MAIL_FROM_ADDRESS gotcha: current_app.config.get() of an
    unplumbed key is silently None in prod."""
    assert 'ADMIN_EMAIL' in app.config


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_admin_alerts_prefer_admin_email(mock_send, app):
    """With ADMIN_EMAIL set, alerts go there — not to the SMTP login."""
    from games.cfb.services.automation import _send_admin_email
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    app.config['EMAIL_ADDRESS'] = 'ad34xxxxx@smtp-brevo.com'

    assert _send_admin_email('Test Alert', 'body') is True

    recipient = mock_send.call_args[0][0]
    assert recipient == 'commish@cccfantasy.com'


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_admin_alerts_fall_back_to_email_address(mock_send, app):
    """Without ADMIN_EMAIL (dev), alerts fall back to EMAIL_ADDRESS."""
    from games.cfb.services.automation import _send_admin_email
    app.config['ADMIN_EMAIL'] = ''
    app.config['EMAIL_ADDRESS'] = 'dev@example.com'

    assert _send_admin_email('Test Alert', 'body') is True

    recipient = mock_send.call_args[0][0]
    assert recipient == 'dev@example.com'


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
def test_admin_alert_skipped_when_no_recipient_configured(mock_send, app):
    """Neither ADMIN_EMAIL nor EMAIL_ADDRESS set → skip, don't crash."""
    from games.cfb.services.automation import _send_admin_email
    app.config['ADMIN_EMAIL'] = ''
    app.config['EMAIL_ADDRESS'] = ''

    assert _send_admin_email('Test Alert', 'body') is False
    mock_send.assert_not_called()


# ── §5/§8.13 — run_setup orphan-week retry + import hardening ────────────

def _setup_event(home_api='Alabama Crimson Tide', away_api='Georgia Bulldogs',
                 event_id='ev1', commence='2026-09-05T17:00:00Z'):
    """One Odds-API /events entry between two teams (API full names)."""
    return {
        'id': event_id,
        'home_team': home_api,
        'away_team': away_api,
        'commence_time': commence,
    }


def _prep_setup(app, *teams):
    """Common run_setup test prep: API key, alert inbox, tracked teams."""
    app.config['ODDS_API_KEY'] = 'test-key'
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    made = [make_team(n) for n in (teams or ('Alabama', 'Georgia'))]
    db.session.commit()
    return made


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_retries_lowest_orphan_week_before_advancing(
        mock_get, mock_send, app):
    """A 0-game week from a failed import is retried, not orphaned forever
    behind week N+1 (audit §5.2: the documented retry was unreachable)."""
    from games.cfb.services.automation import run_setup
    _prep_setup(app)
    orphan = make_week(1)
    db.session.commit()
    mock_get.return_value = _api_response([_setup_event()])

    result = run_setup()

    assert result['week_number'] == 1
    assert result['game_count'] == 1
    assert CfbGame.query.filter_by(week_id=orphan.id).count() == 1
    assert db.session.get(CfbWeek, orphan.id).is_active is True
    assert CfbWeek.query.filter_by(week_number=2).first() is None


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_failed_orphan_retry_does_not_advance(
        mock_get, mock_send, app):
    """When the retry import also fails, the orphan stays the next target —
    week N+1 must not be created over it."""
    from games.cfb.services.automation import run_setup
    _prep_setup(app)
    orphan = make_week(1)
    db.session.commit()
    mock_get.return_value = _api_response([])

    result = run_setup()

    assert result['status'] == 'error'
    assert db.session.get(CfbWeek, orphan.id).is_active is False
    assert CfbWeek.query.filter_by(week_number=2).first() is None


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_zero_game_week_alerts_admin_and_never_activates(
        mock_get, mock_send, app):
    """§8.14: a 0-game week is never activated; the failure now also emails
    the admin (journal-only errors were invisible — Top-5 #5 theme)."""
    from games.cfb.services.automation import run_setup
    _prep_setup(app)
    mock_get.return_value = _api_response([])

    result = run_setup()

    assert result['status'] == 'error'
    week = CfbWeek.query.filter_by(week_number=1).first()
    assert week is not None
    assert week.is_active is False
    assert mock_send.called
    subject = mock_send.call_args[0][1]
    assert 'setup' in subject.lower()


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_import_window_covers_thursday_through_wednesday(
        mock_get, mock_send, app):
    """§5.3: the import window must span the full Thu→Wed week (7 days),
    not cut off Monday 00:00 — Labor-Day Monday and Tue/Wed MACtion games
    were silently missed at +4 days."""
    from datetime import datetime, timedelta
    from games.cfb.services.automation import run_setup
    _prep_setup(app)
    mock_get.return_value = _api_response([_setup_event()])

    run_setup()

    params = mock_get.call_args.kwargs['params']
    t_from = datetime.strptime(params['commenceTimeFrom'], '%Y-%m-%dT%H:%M:%SZ')
    t_to = datetime.strptime(params['commenceTimeTo'], '%Y-%m-%dT%H:%M:%SZ')
    # 7 days minus 1s so the boundary instant can't import into two weeks
    # (event dedupe is week-scoped).
    assert t_to - t_from == timedelta(days=7) - timedelta(seconds=1)


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_import_logs_skipped_untracked_events(mock_get, mock_send, app, caplog):
    """§5.4: events where neither team resolves are skipped WITH a log line
    (they were silently dropped)."""
    import logging
    from games.cfb.services.automation import run_setup
    _prep_setup(app)
    mock_get.return_value = _api_response([
        _setup_event(),
        _setup_event(home_api='Podunk State Hornets',
                     away_api='Nowhere A&M Aggies', event_id='ev2'),
    ])

    with caplog.at_level(logging.INFO, logger='games.cfb.services.automation'):
        result = run_setup()

    assert result['game_count'] == 1
    assert 'Podunk State Hornets' in caplog.text


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_alerts_on_unresolvable_team_names(mock_get, mock_send, app):
    """§5.4: a CfbTeam whose name no API event can resolve to (master-list
    drift / rename) is reported to the admin at sync time instead of going
    silently unpickable all season."""
    from games.cfb.services.automation import run_setup
    _prep_setup(app, 'Alabama', 'Georgia', 'Fake Tech U')
    mock_get.return_value = _api_response([_setup_event()])

    result = run_setup()

    assert result['unresolvable_teams'] == ['Fake Tech U']
    bodies = ' '.join(str(c.args) for c in mock_send.call_args_list)
    assert 'Fake Tech U' in bodies


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_run_setup_applies_special_week_names_and_flags(
        mock_get, mock_send, app):
    """§8.14: special weeks get SEASON_SCHEDULE round names + playoff flags
    (week 15 CCW stays regular-season per DQ-3)."""
    from games.cfb.services.automation import run_setup
    alabama, georgia = _prep_setup(app)
    for n in range(1, 15):
        w = make_week(n)
        make_game(w, alabama, georgia)
    db.session.commit()
    mock_get.return_value = _api_response([_setup_event()])

    result = run_setup()

    assert result['week_number'] == 15
    week15 = CfbWeek.query.filter_by(week_number=15).first()
    assert week15.round_name == 'Conference Championship Week'
    assert week15.is_playoff_week is False


# ── §5/§8.15 — spread updates: bookmaker selection + NULL surfacing ──────

def _bm(key, point=-7.5, home_api='Alabama Crimson Tide',
        away_api='Georgia Bulldogs', with_spreads=True):
    """One bookmaker entry; with_spreads=False carries only an h2h market."""
    if not with_spreads:
        return {'key': key, 'markets': [{'key': 'h2h', 'outcomes': []}]}
    return {'key': key, 'markets': [{
        'key': 'spreads',
        'outcomes': [
            {'name': home_api, 'point': point},
            {'name': away_api, 'point': -point if point is not None else None},
        ],
    }]}


def _odds_event(bookmakers, event_id='ev1', home_api='Alabama Crimson Tide',
                away_api='Georgia Bulldogs'):
    """One Odds-API /odds entry."""
    return {
        'id': event_id,
        'home_team': home_api,
        'away_team': away_api,
        'bookmakers': bookmakers,
    }


def _seed_active_week_game(app, *, locked_at=None, spread=None):
    """Active week + one Alabama/Georgia game wired to API event ev1."""
    app.config['ODDS_API_KEY'] = 'test-key'
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    week = make_week(1, is_active=True)
    home = make_team('Alabama')
    away = make_team('Georgia')
    game = make_game(week, home, away, spread=spread)
    game.api_event_id = 'ev1'
    game.spread_locked_at = locked_at
    db.session.commit()
    return week, game


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_spread_update_prefers_draftkings(mock_get, mock_send, app):
    """DraftKings wins over an earlier-listed bookmaker."""
    from games.cfb.services.automation import run_spread_update
    week, game = _seed_active_week_game(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('bovada', point=-3.0), _bm('draftkings', point=-7.5)]),
    ])

    result = run_spread_update()

    assert result['updated'] == 1
    assert game.home_team_spread == -7.5
    assert game.spread_locked_at is not None


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_spread_update_falls_back_to_bookmaker_with_spreads_market(
        mock_get, mock_send, app, caplog):
    """§5.5: when the first bookmaker has no spreads market, one that does
    carry spreads must be used (selection used to happen before market
    inspection) — and the fallback is logged."""
    import logging
    from games.cfb.services.automation import run_spread_update
    week, game = _seed_active_week_game(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('bovada', with_spreads=False),
                     _bm('fanduel', point=-4.5)]),
    ])

    with caplog.at_level(logging.INFO, logger='games.cfb.services.automation'):
        result = run_spread_update()

    assert result['updated'] == 1
    assert game.home_team_spread == -4.5
    assert 'fanduel' in caplog.text


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_spread_update_skips_locked_games(mock_get, mock_send, app):
    """A locked spread is never overwritten by the cron (DQ-6 inverse)."""
    from datetime import datetime, timezone
    from games.cfb.services.automation import run_spread_update
    week, game = _seed_active_week_game(
        app, locked_at=datetime(2026, 8, 30, 12, 0), spread=-2.5)
    mock_get.return_value = _api_response([
        _odds_event([_bm('draftkings', point=-10.0)]),
    ])

    result = run_spread_update()

    assert result['locked'] == 1
    assert game.home_team_spread == -2.5


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_spread_update_reports_and_alerts_null_spread_games(
        mock_get, mock_send, app):
    """§5.5: a game left with no spread (no bookmaker carries one) is
    reported in the result and emailed to the admin — NULL-spread teams are
    unpickable, which was previously silent."""
    from games.cfb.services.automation import run_spread_update
    week, game = _seed_active_week_game(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('bovada', with_spreads=False)]),
    ])

    result = run_spread_update()

    assert result['games_without_spread'] == ['Georgia @ Alabama']
    assert game.spread_locked_at is None
    assert mock_send.called
    body = mock_send.call_args[0][2]
    assert 'Georgia @ Alabama' in body


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.requests.get')
def test_spread_update_missing_point_is_not_locked_as_zero(
        mock_get, mock_send, app):
    """§5: an outcome without a 'point' must not become a locked 0.0
    spread — treat it as no spread."""
    from games.cfb.services.automation import run_spread_update
    week, game = _seed_active_week_game(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('draftkings', point=None)]),
    ])

    result = run_spread_update()

    assert game.home_team_spread is None
    assert game.spread_locked_at is None
    assert result['games_without_spread'] == ['Georgia @ Alabama']


def test_admin_added_game_spread_is_locked_per_dq6(app, client):
    """DQ-6: a manually entered spread sets spread_locked_at so the spread
    cron can't overwrite the admin's entry."""
    from tests.test_cfb_results import _login_admin
    week = make_week(1, is_active=True)
    home = make_team('Alabama')
    away = make_team('Georgia')
    db.session.commit()
    _login_admin(app, client)

    resp = client.post(f'/cfb/admin/week/{week.id}/games', data={
        'home_team_id': str(home.id),
        'away_team_id': str(away.id),
        'home_spread': '-6.5',
        'game_time': '2026-01-02T18:00',
        'csrf_token': 'x',
    })

    assert resp.status_code == 302
    game = CfbGame.query.filter_by(week_id=week.id).first()
    assert game is not None
    assert game.home_team_spread == -6.5
    assert game.spread_locked_at is not None


# ── §5.1 — run_scores stuck-week alert ───────────────────────────────────

@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.ScoreFetcher')
def test_run_scores_alerts_when_week_stuck_partial(
        mock_fetcher_cls, mock_send, app):
    """§5.1: a week still incomplete >2 days past deadline (score window
    missed — e.g. the Monday-night CFP final vs daysFrom=3) escalates in the
    admin summary instead of silently re-reporting 'partial' forever."""
    from games.cfb.services.automation import run_scores
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    make_week(1)  # PAST_DEADLINE — months past, well over the threshold
    db.session.commit()
    mock_fetcher_cls.return_value.auto_process_week.return_value = {
        'status': 'partial', 'details': '0 games updated, 1 still pending'}

    run_scores()

    assert mock_send.called
    subject = mock_send.call_args[0][1]
    body = mock_send.call_args[0][2]
    assert 'STUCK' in subject
    assert 'STUCK' in body


@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.ScoreFetcher')
def test_run_scores_fresh_partial_is_not_flagged_stuck(
        mock_fetcher_cls, mock_send, app):
    """A week partial within the threshold (normal Sunday-after-Saturday
    state) gets the plain summary, no STUCK escalation."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from games.cfb.services.automation import run_scores
    app.config['ADMIN_EMAIL'] = 'commish@cccfantasy.com'
    recent = (datetime.now(ZoneInfo('America/Chicago')).replace(tzinfo=None)
              - timedelta(hours=12))
    make_week(1, deadline=recent)
    db.session.commit()
    mock_fetcher_cls.return_value.auto_process_week.return_value = {
        'status': 'partial', 'details': '3 games updated, 1 still pending'}

    run_scores()

    assert mock_send.called
    subject = mock_send.call_args[0][1]
    body = mock_send.call_args[0][2]
    assert 'STUCK' not in subject
    assert 'STUCK' not in body


# ── §8.16 — ScoreFetcher matching locks ──────────────────────────────────

def _score_event(event_id='ev1', home_api='Alabama Crimson Tide',
                 away_api='Georgia Bulldogs', home_score=28, away_score=10,
                 completed=True):
    """One Odds-API /scores entry."""
    return {
        'id': event_id,
        'home_team': home_api,
        'away_team': away_api,
        'completed': completed,
        'scores': [
            {'name': home_api, 'score': str(home_score)},
            {'name': away_api, 'score': str(away_score)},
        ],
    }


def _seed_score_week(app, *, event_id='ev1'):
    """Past-deadline week + one undecided Alabama/Georgia game."""
    app.config['ODDS_API_KEY'] = 'test-key'
    week = make_week(1)
    home = make_team('Alabama')
    away = make_team('Georgia')
    game = make_game(week, home, away, spread=-7.0)
    game.api_event_id = event_id
    db.session.commit()
    return week, game


@patch('games.cfb.services.score_fetcher.requests.get')
def test_fetch_scores_matches_by_event_id(mock_get, app):
    """Primary match path: api_event_id, week-scoped."""
    from games.cfb.services.score_fetcher import ScoreFetcher
    week, game = _seed_score_week(app)
    mock_get.return_value = _api_response([_score_event()])

    fetched = ScoreFetcher().fetch_scores_for_week(week.id)

    assert fetched['error'] is None
    assert len(fetched['matched_completed']) == 1
    match = fetched['matched_completed'][0]
    assert match['game_id'] == game.id
    assert match['match_method'] == 'event_id'
    assert match['home_score'] == 28


@patch('games.cfb.services.score_fetcher.requests.get')
def test_fetch_scores_team_name_fallback_backfills_event_id(mock_get, app):
    """Fallback match path: API full names → short names; applying the
    result saves the event id for future runs."""
    from games.cfb.services.score_fetcher import ScoreFetcher
    week, game = _seed_score_week(app, event_id=None)
    mock_get.return_value = _api_response([_score_event(event_id='ev9')])

    fetcher = ScoreFetcher()
    fetched = fetcher.fetch_scores_for_week(week.id)

    assert len(fetched['matched_completed']) == 1
    assert fetched['matched_completed'][0]['match_method'] == 'team_name'

    fetcher.apply_scores_to_games(week.id, fetched['matched_completed'])
    assert game.api_event_id == 'ev9'
    assert game.home_team_won is True


def test_apply_scores_tie_flags_manual_review(app):
    """A tie sets no winner and is surfaced for manual review."""
    from games.cfb.services.score_fetcher import ScoreFetcher
    week, game = _seed_score_week(app)

    result = ScoreFetcher().apply_scores_to_games(week.id, [
        {'game_id': game.id, 'home_score': 21, 'away_score': 21},
    ])

    assert game.home_team_won is None
    assert result['updated_count'] == 0
    assert len(result['tie_games']) == 1
    assert result['tie_games'][0]['game_id'] == game.id


def test_apply_scores_skips_decided_and_no_contest_games(app):
    """Already-decided games and admin No Contest rulings are never
    overturned by a late API score (DQ-4)."""
    from games.cfb.services.score_fetcher import ScoreFetcher
    app.config['ODDS_API_KEY'] = 'test-key'
    week = make_week(1)
    t1, t2, t3, t4 = (make_team(n) for n in ('Alabama', 'Georgia',
                                             'Ohio State', 'Michigan'))
    decided = make_game(week, t1, t2, winner='home')
    no_contest = make_game(week, t3, t4, no_contest=True)
    db.session.commit()

    result = ScoreFetcher().apply_scores_to_games(week.id, [
        {'game_id': decided.id, 'home_score': 3, 'away_score': 45},
        {'game_id': no_contest.id, 'home_score': 30, 'away_score': 7},
    ])

    assert result['skipped_count'] == 2
    assert decided.home_team_won is True
    assert no_contest.home_team_won is None
    assert no_contest.home_score is None


# ── §8.14 — short-label map matches SEASON_SCHEDULE round names ──────────

def test_week_short_labels_match_season_schedule_round_names(app):
    """§3: get_week_short_label's map must key on the round names automation
    actually writes (SEASON_SCHEDULE) — weeks 16/19 rendered 'W16'/'W19'
    because the map expected 'CFP Round 1'/'CFP Championship'."""
    from games.cfb.constants import SEASON_SCHEDULE
    from games.cfb.utils import get_week_short_label
    expected = {15: 'CCW', 16: 'R1', 17: 'QF', 18: 'SF', 19: 'F'}

    for number, info in SEASON_SCHEDULE['special_weeks'].items():
        week = make_week(number)
        week.round_name = info['name']
        assert get_week_short_label(week) == expected[number], info['name']
