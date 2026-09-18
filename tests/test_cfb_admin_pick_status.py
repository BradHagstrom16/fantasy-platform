"""The Roster (/cfb/admin/users) shows active-week pick status.

The commish needs to see, at a glance, who has and hasn't a pick in for
the active week — to chase stragglers before the deadline and to audit
autopicks after it. The column always follows the raw is_active week (a
lingering "No pick" after the deadline surfaces an autopick miss).

Session identity is auth_id, never str(user.id) — see CLAUDE.md.
"""
from datetime import datetime

from extensions import db
from tests._cfb_fixtures import (
    make_enrollment,
    make_pick,
    make_team,
    make_user,
    make_week,
)

# A deadline comfortably ahead of any test run, so a pick created "now"
# reads as a real (pre-deadline) pick rather than an autopick.
FUTURE_DEADLINE = datetime(2035, 1, 3, 11, 0)


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def test_pick_status_column_flags_picked_missing_and_eliminated(app, client):
    """One picked, one active-no-pick, one eliminated — each rendered right."""
    admin = make_user('padmin', is_admin=True)
    georgia = make_team('Georgia')

    picked = make_user('haspick')
    make_enrollment(picked)
    missing = make_user('nopick')
    make_enrollment(missing)
    gone = make_user('eliminated')
    make_enrollment(gone, lives=0, eliminated=True)

    week = make_week(3, deadline=FUTURE_DEADLINE, is_active=True)
    make_pick(picked, week, georgia)
    db.session.commit()
    _login(client, admin)

    resp = client.get('/cfb/admin/users')
    body = resp.data.decode()

    assert resp.status_code == 200
    # Column header names the active week.
    assert 'Week 3 Pick' in body
    # The player who picked shows their team; no autopick tag pre-deadline.
    assert 'Georgia' in body
    assert 'cfb-auto-tag' not in body
    # The active player without a pick is flagged and their row shaded.
    assert 'No pick' in body
    assert 'is-attention' in body
    assert 'table-warning' in body
    # Eliminated players aren't expected to pick — em-dash placeholder.
    assert 'cfb-result-none' in body
    # Summary counts the live field only (eliminated excluded from denominator).
    assert '1</strong> of <strong>2</strong> picked, 1 still out' in body


def test_pick_status_marks_autopicks_after_deadline(app, client):
    """A pick created after the deadline reads as Auto (post-deadline audit)."""
    admin = make_user('padmin', is_admin=True)
    bama = make_team('Alabama')

    player = make_user('autopicked')
    make_enrollment(player)

    # Past deadline (the fixture default); make_pick's created_at defaults to
    # now, which is after it → is_autopick.
    week = make_week(1, is_active=True)
    make_pick(player, week, bama)
    db.session.commit()
    _login(client, admin)

    resp = client.get('/cfb/admin/users')
    body = resp.data.decode()

    assert resp.status_code == 200
    assert 'Alabama' in body
    assert 'cfb-auto-tag' in body


def test_no_active_week_hides_pick_column_and_summary(app, client):
    """Out of season / no open week: no column, no summary, page still renders."""
    admin = make_user('padmin', is_admin=True)
    player = make_user('player1')
    make_enrollment(player)
    # A week exists but is not active.
    make_week(1, is_active=False)
    db.session.commit()
    _login(client, admin)

    resp = client.get('/cfb/admin/users')
    body = resp.data.decode()

    assert resp.status_code == 200
    # No "Week N Pick" column header, no summary, no attention chips.
    assert 'Pick</th>' not in body
    assert 'still out' not in body
    assert 'No pick' not in body
    assert 'is-attention' not in body
