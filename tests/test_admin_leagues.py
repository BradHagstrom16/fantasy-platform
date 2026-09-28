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


def test_dashboard_lists_the_live_games_before_the_world_cup(app, client):
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    world_cup = data.index('World Cup Fantasy')
    assert data.index('CFB Survivor Pool') < world_cup
    assert data.index('The Docket') < world_cup


# ---- Scheduled Jobs + the Odds API balance (open-items §H) ------------------

def _run(job, outcome, minutes_ago, *, summary=None, credits=None, via='systemd'):
    from datetime import UTC, datetime, timedelta

    from models.sync_run import SyncRun
    started = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    run = SyncRun(job=job, outcome=outcome, started_at=started,
                  finished_at=started + timedelta(seconds=42),
                  exit_code=1 if outcome == 'error' else 0, summary=summary,
                  odds_credits_remaining=credits, via=via)
    db.session.add(run)
    db.session.commit()
    return run


def test_dashboard_shows_each_jobs_latest_run(app, client):
    _run('cfb-scores', 'error', 120, summary='Odds API unreachable')
    _run('cfb-scores', 'ok', 60, summary='Week 4: processed', credits=412)
    _run('club-remind', 'idle', 5, summary='no tier is due', via='shell')
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    assert 'Scheduled Jobs' in data
    assert 'Survivor scores' in data and 'Reminder desk' in data
    assert 'Week 4: processed' in data
    # The earlier failure stays on the row after a later run went fine.
    assert 'Odds API unreachable' in data
    assert 'by hand' in data
    assert '42s' in data
    # A job that never ran is not listed.
    assert 'Docket deadline' not in data


def test_dashboard_shows_the_newest_credit_balance(app, client):
    _run('docket-scores', 'ok', 600, credits=500)
    _run('scores-gameday', 'ok', 30, credits=1234)
    _run('club-remind', 'ok', 5)
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    assert '1,234 Odds API credits left' in data


def test_dashboard_with_no_runs_says_so(app, client):
    _login_admin(client)
    data = client.get('/admin/').data.decode()
    assert 'No job has recorded a run yet' in data
    assert 'Odds API credits left' not in data
