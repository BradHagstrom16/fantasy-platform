"""The Docket lounge module (multi-featured seam).

State resolution is pure week-boundary math (never the DB) so empty docket
tables — every foreign test that renders `/`, and prod before the Week-1
import — can never break a lounge render. The context builder is read-only
and summary-cheap by contract: no game loads, no season_ledger, no writers.
"""
from datetime import datetime

from extensions import db
from games.docket.models import DocketPick, DocketTiebreakerPrediction, DocketWeekResult
from games.docket.services import lounge
from tests._docket_fixtures import (
    at,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

PRE_ANCHOR = '2026-08-18T17:00:00'
IN_SEASON = '2026-09-24T17:00:00'
WEEK1_BOUNDARY_UTC = '2026-09-01T11:00:00'   # Tue Sep 1 06:00 CT
IN_WEEK1_OPEN = '2026-09-02T12:00:00'
IN_WEEK1_CLOSED = '2026-09-05T17:00:00'      # past Sat 11:00 CT (16:00 UTC)
POST_SEASON = '2027-01-20T00:00:00'          # season ends Tue Jan 12 2027


# --- State resolver: pure time math ---------------------------------------

def test_state_pre_before_week1_boundary(app, monkeypatch):
    at(monkeypatch, PRE_ANCHOR)
    assert lounge.docket_lounge_state() == 'pre'


def test_state_live_in_season(app, monkeypatch):
    at(monkeypatch, IN_SEASON)
    assert lounge.docket_lounge_state() == 'live'


def test_state_live_at_week1_boundary_instant(app, monkeypatch):
    """Half-open weeks: the boundary instant belongs to the week it opens."""
    at(monkeypatch, WEEK1_BOUNDARY_UTC)
    assert lounge.docket_lounge_state() == 'live'


def test_state_post_after_season(app, monkeypatch):
    at(monkeypatch, POST_SEASON)
    assert lounge.docket_lounge_state() == 'post'


def test_state_never_touches_db(monkeypatch):
    """No app, no tables: the resolver is week-math plus the clock seam.

    This is the property that makes the docket panel safe on every lounge
    render against empty tables (and in every non-docket test)."""
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('DOCKET_FAKE_NOW', IN_SEASON)
    assert lounge.docket_lounge_state() == 'live'


def test_join_window_open_flips_at_week1_deadline(app, monkeypatch):
    """Brad's enrollment ruling: self-serve joining closes at the Week 1
    deadline, strictly (the deadline instant itself is closed)."""
    at(monkeypatch, '2026-09-05T15:59:00')
    assert lounge.join_window_open() is True
    at(monkeypatch, '2026-09-05T16:00:00')
    assert lounge.join_window_open() is False


# --- Context builder -------------------------------------------------------

def test_context_out_counts_enrollments(app, monkeypatch):
    with app.app_context():
        make_enrollment(make_user('clerk1'))
        make_enrollment(make_user('clerk2'))
        ctx = lounge.build_lounge_context(None, None)
    assert ctx == {'total_enrolled': 2}


def test_context_pre_first_deadline_line(app, monkeypatch):
    at(monkeypatch, PRE_ANCHOR)
    with app.app_context():
        user = make_user('early')
        make_enrollment(user)
        ctx = lounge.build_lounge_context(user, 'pre')
    assert ctx['is_enrolled'] is True
    assert ctx['viewer_mode'] == 'member'
    assert ctx['game_tile_label'] == 'OPENS · SEP 1'
    assert ctx['court_line'] == 'Sheets due Saturdays · 11:00 AM CT'
    # Naive UTC (D6): Sat Sep 5 11:00 CT == 16:00 UTC. Templates ct-filter it.
    assert ctx['first_deadline_at'] == datetime(2026, 9, 5, 16, 0)
    assert ctx['archived_tiles'] == []


def test_context_live_awaiting_beat_when_week_not_imported(app, monkeypatch):
    """Week 1 is CFB-only and imports by hand: a missing week row in season
    is the 'awaiting' beat, never an error. week_number still resolves from
    the pure math."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('waiting')
        make_enrollment(user)
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['beat'] == 'awaiting'
    assert ctx['week_number'] == 1
    assert ctx['week_deadline_at'] is None
    assert ctx['court_line'] == 'Week 1 · awaiting the docket'
    assert ctx['game_tile_label'] == 'WEEK 1 · AWAITING'
    assert 'progress' not in ctx


def test_context_live_open_beat_progress_counts(app, monkeypatch):
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('picker')
        make_enrollment(user)
        week = make_week(1)
        kickoff = datetime(2026, 9, 3, 23, 30)
        g1 = make_game(week, kickoff=kickoff)
        g2 = make_game(week, kickoff=kickoff)
        rows = [
            DocketPick(user_id=user.id, week_id=week.id, game_id=g1.id,
                       market='spread', side='home', slot=1, is_best=True,
                       line_value=-3.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=g1.id,
                       market='total', side='over', slot=2,
                       line_value=51.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=g2.id,
                       market='spread', side='away', slot=3,
                       line_value=3.5, book='draftkings'),
            # Held in reserve: slot 9 never counts toward the eight.
            DocketPick(user_id=user.id, week_id=week.id, game_id=g2.id,
                       market='total', side='under', slot=9,
                       line_value=51.5, book='draftkings'),
        ]
        db.session.add_all(rows)
        db.session.flush()
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['beat'] == 'open'
    progress = ctx['progress']
    assert progress['scoring_count'] == 3
    assert progress['best_named'] is True
    assert progress['backup_held'] is True
    assert progress['prediction_recorded'] is False
    assert 'Sides committed: 3 of 8.' in progress['outstanding']
    assert 'No combined-score number recorded.' in progress['outstanding']
    assert 'No headliner named.' not in progress['outstanding']
    assert ctx['week_deadline_at'] == week.deadline_at


def test_context_live_outstanding_empty_when_sheet_complete(app, monkeypatch):
    """Prose parity with the reminder emails: a complete sheet owes nothing."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('complete')
        make_enrollment(user)
        week = make_week(1)
        kickoff = datetime(2026, 9, 3, 23, 30)
        games = [make_game(week, kickoff=kickoff) for _ in range(4)]
        slot = 1
        for game in games:
            for market, side, line in (('spread', 'home', -3.5),
                                       ('total', 'over', 51.5)):
                db.session.add(DocketPick(
                    user_id=user.id, week_id=week.id, game_id=game.id,
                    market=market, side=side, slot=slot, is_best=(slot == 1),
                    line_value=line, book='draftkings'))
                slot += 1
        db.session.add(DocketTiebreakerPrediction(
            user_id=user.id, week_id=week.id, prediction_tenths=515))
        db.session.flush()
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['progress']['scoring_count'] == 8
    assert ctx['progress']['outstanding'] == []


def test_context_live_closed_beat_post_deadline_ungraded(app, monkeypatch):
    at(monkeypatch, IN_WEEK1_CLOSED)
    with app.app_context():
        user = make_user('waiting-verdicts')
        make_enrollment(user)
        make_week(1)
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['beat'] == 'closed'
    assert ctx['court_line'] == 'Week 1 · docket closed'
    assert 'progress' not in ctx
    assert 'result' not in ctx


def test_context_live_adjourned_beat_when_graded(app, monkeypatch):
    at(monkeypatch, IN_WEEK1_CLOSED)
    with app.app_context():
        user = make_user('graded')
        make_enrollment(user)
        week = make_week(1)
        week.default_error_tenths = 20
        db.session.add(DocketWeekResult(
            user_id=user.id, week_id=week.id, points=6.5, wins=5,
            error_tenths=30, graded_at=datetime(2026, 9, 8, 12, 0)))
        db.session.flush()
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['beat'] == 'adjourned'
    assert ctx['result'] == {'points_label': '6.5', 'wins': 5}


def test_context_live_view_mode_unenrolled(app, monkeypatch):
    """A member of the club but not of this game: the beat is public, the
    personal sheet facts are not."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('spectator')
        make_week(1)
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['viewer_mode'] == 'view'
    assert ctx['is_enrolled'] is False
    assert ctx['beat'] == 'open'
    assert 'progress' not in ctx


def test_context_post_minimal(app, monkeypatch):
    at(monkeypatch, POST_SEASON)
    with app.app_context():
        user = make_user('after')
        make_enrollment(user)
        ctx = lounge.build_lounge_context(user, 'post')
    assert ctx['season_complete'] is True
    assert ctx['game_tile_label'] == 'SEASON CLOSED'


def test_lounge_module_never_imports_writers():
    """Read-only contract: the lounge runs on every home render and is
    imported by the registry at boot. The write passes stay out."""
    from pathlib import Path
    src = Path('games/docket/services/lounge.py').read_text()
    import_lines = [
        line for line in src.splitlines()
        if line.strip().startswith(('import ', 'from '))
    ]
    for forbidden in ('deadline_pass', 'grading_pass', 'importer', 'scores'):
        offenders = [line for line in import_lines if forbidden in line]
        assert offenders == [], (
            f'lounge module imports a writer service: {offenders}'
        )
