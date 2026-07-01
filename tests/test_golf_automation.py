"""PR 4 — Golf ops hardening & automation (TDD, audit §3/§6/§7).

Locks the ops fixes ported/added in PR 4:

- ``SLASHGOLF_API_KEY`` config-plumbing (the ``MAIL_FROM_ADDRESS`` gotcha —
  ``current_app.config.get()`` of an unplumbed key is silently ``None`` in prod);
- season-scoped automation queries (``get_active_tournaments`` /
  ``get_recently_completed_tournaments`` / ``get_tournaments_pending_finalization`` /
  ``get_upcoming_tournaments_window``) so a prior season can't contaminate a sync;
- ``GolfEnrollment.get_used_player_ids`` returns only current-season usage;
- reminder de-dup via ``GolfTournament.last_reminder_type`` (skip current-or-later
  tier; record only after a successful send) — ported from the standalone;
- CLI safety: ``sync-run --mode all`` is disabled in production, and
  ``--mode remind`` runs reminders without requiring the API key.

Golf tests run against in-memory SQLite via ``create_app('testing')``.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.golf.models import (
    GolfEnrollment,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
)
from games.golf.services.reminders import run_reminder_check
from games.golf.utils import GOLF_LEAGUE_TZ

SEASON = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    # Pin the season the code resolves from config so these tests don't couple to
    # the SEASON_YEAR default rolling forward — the season-scoping under test reads
    # current_app.config['SEASON_YEAR'], and SEASON below must match it.
    app.config['SEASON_YEAR'] = SEASON
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_user(username='golfer'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _make_enrollment(user, season_year=SEASON):
    e = GolfEnrollment(user_id=user.id, season_year=season_year, total_points=0)
    db.session.add(e)
    db.session.commit()
    return e


def _make_player(api_id, first='F', last='L'):
    p = GolfPlayer(api_player_id=api_id, first_name=first, last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


def _make_tournament(name='Test Open', status='upcoming', season_year=SEASON,
                     results_finalized=False, start_date=None, end_date=None,
                     pick_deadline=None):
    now = datetime.now(timezone.utc)
    t = GolfTournament(
        api_tourn_id=f'T-{name}-{season_year}',
        name=name,
        season_year=season_year,
        start_date=start_date if start_date is not None else now - timedelta(days=4),
        end_date=end_date if end_date is not None else now - timedelta(days=1),
        pick_deadline=pick_deadline,
        purse=10_000_000,
        status=status,
        results_finalized=results_finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _configure_email(app):
    """Give run_reminder_check the credentials it guards on."""
    app.config['EMAIL_ADDRESS'] = 'dev@example.com'
    app.config['EMAIL_PASSWORD'] = 'pw'
    app.config['SITE_URL'] = 'https://example.com'


def _make_reminder_tournament(hours_to_deadline=24, name='Reminder Open',
                              last_reminder_type=None):
    """A tournament whose pick deadline lands inside a reminder window."""
    now_ct = datetime.now(GOLF_LEAGUE_TZ)
    deadline = (now_ct + timedelta(hours=hours_to_deadline)).replace(tzinfo=None)
    t = GolfTournament(
        api_tourn_id=f'REM-{name}',
        name=name,
        season_year=SEASON,
        start_date=(now_ct + timedelta(hours=hours_to_deadline)).replace(tzinfo=None),
        end_date=(now_ct + timedelta(days=4)).replace(tzinfo=None),
        pick_deadline=deadline,
        purse=10_000_000,
        status='upcoming',
        last_reminder_type=last_reminder_type,
    )
    db.session.add(t)
    db.session.commit()
    return t


# ── Config-plumbing lock (audit §5, MAIL_FROM_ADDRESS gotcha) ────────────────

def test_slashgolf_api_key_config_key_is_plumbed(app):
    """SLASHGOLF_API_KEY must be defined on config.py's base Config (with an
    os.environ.get() line) — current_app.config.get() of an unplumbed key is
    silently None in prod (the MAIL_FROM_ADDRESS gotcha). Asserting on the base
    Config class (not just app.config) proves it's env-plumbed there rather than
    injected by the app factory or the testing config."""
    from config import Config
    assert 'SLASHGOLF_API_KEY' in vars(Config)   # defined on the base Config itself
    assert 'SLASHGOLF_API_KEY' in app.config      # and reaches the resolved app config


# ── Season-scoped automation queries (audit §3 MEDIUM) ───────────────────────

def test_get_active_tournaments_scoped_to_current_season(app):
    from games.golf.services.sync import get_active_tournaments
    _make_tournament(name='This Yr', status='active', season_year=SEASON)
    _make_tournament(name='Last Yr', status='active', season_year=SEASON - 1)

    names = [t.name for t in get_active_tournaments()]

    assert names == ['This Yr']


def test_get_recently_completed_tournaments_scoped_to_current_season(app):
    from games.golf.services.sync import get_recently_completed_tournaments
    now = datetime.now(timezone.utc)
    recent_end = now - timedelta(hours=1)  # inside the 2-day window for BOTH
    _make_tournament(name='This Yr', status='complete', season_year=SEASON,
                     end_date=recent_end)
    _make_tournament(name='Last Yr', status='complete', season_year=SEASON - 1,
                     end_date=recent_end)

    names = [t.name for t in get_recently_completed_tournaments()]

    assert 'This Yr' in names
    assert 'Last Yr' not in names  # excluded by season, not by the date window


def test_get_tournaments_pending_finalization_scoped_to_current_season(app):
    from games.golf.services.sync import get_tournaments_pending_finalization
    _make_tournament(name='This Yr', status='complete', results_finalized=False,
                     season_year=SEASON)
    _make_tournament(name='Last Yr', status='complete', results_finalized=False,
                     season_year=SEASON - 1)

    names = [t.name for t in get_tournaments_pending_finalization()]

    assert names == ['This Yr']


def test_get_upcoming_tournaments_window_scoped_to_current_season(app):
    from games.golf.services.sync import get_upcoming_tournaments_window
    now = datetime.now(timezone.utc)
    soon_start = now + timedelta(days=2)   # inside the 10-day window, stays upcoming
    soon_end = now + timedelta(days=5)
    _make_tournament(name='This Yr', status='upcoming', season_year=SEASON,
                     start_date=soon_start, end_date=soon_end,
                     pick_deadline=soon_start)
    _make_tournament(name='Last Yr', status='upcoming', season_year=SEASON - 1,
                     start_date=soon_start, end_date=soon_end,
                     pick_deadline=soon_start)

    names = [t.name for t in get_upcoming_tournaments_window()]

    assert 'This Yr' in names
    assert 'Last Yr' not in names


def test_get_used_player_ids_returns_current_season_only(app):
    """Enrollment usage is season-scoped — a prior season's locked golfer must
    not count against this season's pool."""
    user = _make_user()
    enrollment = _make_enrollment(user, SEASON)
    this_yr = _make_player('p-this')
    last_yr = _make_player('p-last')
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=this_yr.id, season_year=SEASON))
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=last_yr.id, season_year=SEASON - 1))
    db.session.commit()

    assert enrollment.get_used_player_ids() == [this_yr.id]


# ── Reminder de-dup (audit §6 HIGH) ──────────────────────────────────────────

@patch('games.golf.services.reminders.get_field_count', return_value=50)
@patch('games.golf.services.reminders.is_field_ready', return_value=True)
@patch('games.golf.services.reminders.send_platform_email', return_value=True)
def test_reminder_dedup_skips_already_sent_tier(mock_send, _ready, _count, app):
    """A second hourly run inside the same reminder window must not re-send the
    tier — the dedup records last_reminder_type after a successful send."""
    _configure_email(app)
    tournament = _make_reminder_tournament(hours_to_deadline=24)
    _make_enrollment(_make_user())

    run_reminder_check()

    assert mock_send.call_count == 1
    assert tournament.last_reminder_type == '24h'

    run_reminder_check()  # same window, tier already recorded

    assert mock_send.call_count == 1  # no second send


@patch('games.golf.services.reminders.get_field_count', return_value=50)
@patch('games.golf.services.reminders.is_field_ready', return_value=True)
@patch('games.golf.services.reminders.send_platform_email', return_value=False)
def test_reminder_not_recorded_when_send_fails(mock_send, _ready, _count, app):
    """If every send fails, the tier must NOT be recorded — the next run retries."""
    _configure_email(app)
    tournament = _make_reminder_tournament(hours_to_deadline=24)
    _make_enrollment(_make_user())

    run_reminder_check()

    assert mock_send.called
    assert tournament.last_reminder_type is None


@patch('games.golf.services.reminders.get_field_count', return_value=50)
@patch('games.golf.services.reminders.is_field_ready', return_value=True)
@patch('games.golf.services.reminders.send_platform_email', return_value=True)
def test_reminder_skips_earlier_tier_after_later_sent(mock_send, _ready, _count, app):
    """Once the 12h tier is recorded, a later run that lands in the 24h window
    (an earlier tier) is skipped — skip current-OR-later."""
    _configure_email(app)
    _make_reminder_tournament(hours_to_deadline=24, last_reminder_type='12h')
    _make_enrollment(_make_user())

    run_reminder_check()

    assert mock_send.call_count == 0


# ── CLI safety (audit §7 MEDIUM) ─────────────────────────────────────────────

def test_sync_run_all_mode_disabled_in_production(app, monkeypatch):
    """'--mode all' chains every sync with only partial gates — it is a
    dev/manual convenience and must refuse to run in production."""
    monkeypatch.setenv('ENVIRONMENT', 'production')
    runner = app.test_cli_runner()

    result = runner.invoke(args=['golf', 'sync-run', '--mode', 'all'])

    assert result.exit_code != 0
    assert 'production' in result.output.lower()


@patch('games.golf.services.reminders.run_reminder_check')
def test_sync_run_remind_mode_runs_without_api_key(mock_run, app, monkeypatch):
    """'--mode remind' must short-circuit before the API client is built so it
    works with no SLASHGOLF_API_KEY set (reminders never call the API)."""
    monkeypatch.delenv('SLASHGOLF_API_KEY', raising=False)
    runner = app.test_cli_runner()

    result = runner.invoke(args=['golf', 'sync-run', '--mode', 'remind'])

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()


# ── Lazy, fault-tolerant API-call logging (audit §3 LOW) ─────────────────────

def test_api_call_logging_tolerates_unwritable_log_dir(tmp_path, monkeypatch):
    """The API-call file logger is set up lazily and must NOT crash when its
    directory can't be created (a read-only deploy) — the fix for the
    import-time os.makedirs that could break app startup."""
    import games.golf.services.sync as sync_mod
    # Point the log dir *under a regular file* so os.makedirs raises OSError.
    blocker = tmp_path / 'blocker'
    blocker.write_text('x')
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(blocker / 'logs'))
    monkeypatch.setattr(sync_mod, '_api_call_logging_configured', False)

    sync_mod._ensure_api_call_logging()  # must not raise

    assert sync_mod._api_call_logging_configured is True
