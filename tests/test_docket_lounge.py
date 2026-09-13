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
IN_WEEK1_CLOSED = '2026-09-06T18:00:00'      # past Sun 12:00 CT (17:00 UTC)
POST_SEASON = '2027-01-20T00:00:00'          # season ends Tue Jan 12 2027


def _hold(user, week, game, *, market='spread', side='home', slot=1,
          line=-3.5, is_best=False):
    db.session.add(DocketPick(
        user_id=user.id, week_id=week.id, game_id=game.id, market=market,
        side=side, slot=slot, is_best=is_best, line_value=line,
        book='draftkings'))


def _final(game, home_score, away_score):
    game.home_score, game.away_score, game.is_final = home_score, away_score, True


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


def test_join_window_open_flips_at_the_enrollment_deadline(app, monkeypatch):
    """Brad's enrollment ruling: self-serve joining closes at the shared
    enrollment deadline (Sat Sep 5 11:00 AM CT = 16:00 UTC), strictly (the
    deadline instant itself is closed). Decoupled from the weekly pick
    deadline, which moved to Sunday (2026-09-09)."""
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
    # roster_count is the floor-gated display count (ADR-051): 0 below
    # ROSTER_COUNT_FLOOR so the bill hides a tiny pre-launch roster.
    assert ctx == {'total_enrolled': 2, 'roster_count': 0}


def test_context_pre_first_deadline_line(app, monkeypatch):
    at(monkeypatch, PRE_ANCHOR)
    with app.app_context():
        user = make_user('early')
        make_enrollment(user)
        ctx = lounge.build_lounge_context(user, 'pre')
    assert ctx['is_enrolled'] is True
    assert ctx['viewer_mode'] == 'member'
    assert ctx['game_tile_label'] == 'OPENS · SEP 1'
    assert ctx['court_line'] == 'Sheets due Sundays · 12:00 PM CT'
    # Naive UTC (D6): Sun Sep 6 12:00 CT == 17:00 UTC. Templates ct-filter it.
    assert ctx['first_deadline_at'] == datetime(2026, 9, 6, 17, 0)
    assert ctx['archived_tiles'] == []


def test_context_pre_posted_branch_when_week_imported_with_games(app, monkeypatch):
    """Design review 2026-08-19: the room's pre-season preview means the
    docket can already be read — the panel says posted-for-reading, dated
    from the week math, instead of promising a post that already happened."""
    at(monkeypatch, PRE_ANCHOR)
    with app.app_context():
        user = make_user('reader')
        make_enrollment(user)
        week = make_week(1)
        make_game(week, kickoff=datetime(2026, 9, 3, 22, 0))
        db.session.commit()
        ctx = lounge.build_lounge_context(user, 'pre')
    assert ctx['posted_week_number'] == 1
    # Naive UTC (D6): Tue Sep 1 06:00 CT == 11:00 UTC. Templates ct-filter it.
    assert ctx['court_convenes_at'] == datetime(2026, 9, 1, 11, 0)


def test_context_pre_posted_branch_stays_off_without_games(app, monkeypatch):
    """An imported-but-empty week is not a posted docket (mirrors the room's
    own empty-state rule for the preview)."""
    at(monkeypatch, PRE_ANCHOR)
    with app.app_context():
        user = make_user('early2')
        make_enrollment(user)
        make_week(1)
        db.session.commit()
        ctx = lounge.build_lounge_context(user, 'pre')
    assert ctx['posted_week_number'] is None


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
    """Closed carries the board too (bolder pass 2026-09-12): the card keeps
    painting the viewer's slots and record while verdicts land, instead of
    collapsing to one sentence. No sheet: nine open tiles, no record."""
    at(monkeypatch, IN_WEEK1_CLOSED)
    with app.app_context():
        user = make_user('waiting-verdicts')
        make_enrollment(user)
        make_week(1)
        ctx = lounge.build_lounge_context(user, 'live')
    assert ctx['beat'] == 'closed'
    assert ctx['court_line'] == 'Week 1 · docket closed'
    assert 'result' not in ctx
    progress = ctx['progress']
    assert len(progress['marks']) == 9
    assert not any(m.held for m in progress['marks'])
    assert progress['tally'] is None and progress['record'] is None
    assert progress['board_label'] == '0 of 8 sides held'


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
    result = ctx['result']
    assert result['points_label'] == '6.5' and result['wins'] == 5
    # The final board rides the adjourned card (bolder pass 2026-09-12).
    assert len(result['marks']) == 9
    assert set(result) == {'points_label', 'wins', 'marks', 'tally',
                           'record', 'board_label'}


def test_context_live_open_beat_paints_verdicts_as_they_land(app, monkeypatch):
    """The board (bolder pass 2026-09-12): each of the viewer's own slots
    carries its state — a final case its engine result, a kicked-off case
    the live flag — and the record is the tally of the finals, in the same
    words All Sheets prints. The reserve never counts."""
    at(monkeypatch, IN_WEEK1_OPEN)                      # Wed Sep 2 12:00 UTC
    with app.app_context():
        user = make_user('scorer')
        make_enrollment(user)
        week = make_week(1)
        done = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        done.home_score, done.away_score, done.is_final = 31, 17, True
        live = make_game(week, kickoff=datetime(2026, 9, 2, 0, 0))    # kicked off
        later = make_game(week, kickoff=datetime(2026, 9, 3, 23, 30))
        db.session.add_all([
            # home -3.5, final 31-17: a win. Over 51.5 on 48: a loss.
            DocketPick(user_id=user.id, week_id=week.id, game_id=done.id,
                       market='spread', side='home', slot=1,
                       line_value=-3.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=done.id,
                       market='total', side='over', slot=2,
                       line_value=51.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=live.id,
                       market='spread', side='away', slot=3, is_best=True,
                       line_value=3.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=later.id,
                       market='spread', side='home', slot=4,
                       line_value=-3.5, book='draftkings'),
            # The reserve rides the kicked-off case's other market: on the
            # board with the live flag, never counted.
            DocketPick(user_id=user.id, week_id=week.id, game_id=live.id,
                       market='total', side='under', slot=9,
                       line_value=51.5, book='draftkings'),
        ])
        db.session.flush()
        ctx = lounge.build_lounge_context(user, 'live')
    progress = ctx['progress']
    by_slot = {m.slot: m for m in progress['marks']}
    assert [m.slot for m in progress['marks']] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert by_slot[1].result == 'win' and by_slot[2].result == 'loss'
    assert by_slot[3].result is None and by_slot[3].in_play is True
    assert by_slot[3].is_best is True
    assert by_slot[4].in_play is False and by_slot[4].held is True
    assert by_slot[5].held is False
    assert by_slot[9].is_reserve and by_slot[9].held and by_slot[9].in_play
    tally = progress['tally']
    assert (tally.wins, tally.losses, tally.pushes, tally.pending) == (1, 1, 0, 2)
    assert progress['record'] == '1-1 · 2 to play'
    assert progress['board_label'] == (
        '1 win, 1 loss; 2 to play; 1 in play; x2 on slot 3; reserve held')
    assert progress['scoring_count'] == 4 and progress['backup_held'] is True


def test_context_live_record_is_none_until_a_scoring_side_is_final(app, monkeypatch):
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('early-bird')
        make_enrollment(user)
        week = make_week(1)
        game = make_game(week, kickoff=datetime(2026, 9, 3, 23, 30))
        db.session.add(DocketPick(
            user_id=user.id, week_id=week.id, game_id=game.id,
            market='spread', side='home', slot=1, is_best=True,
            line_value=-3.5, book='draftkings'))
        db.session.flush()
        ctx = lounge.build_lounge_context(user, 'live')
    progress = ctx['progress']
    assert progress['tally'] is None and progress['record'] is None
    assert progress['board_label'] == '1 of 8 sides held; x2 on slot 1'


def test_lounge_renders_the_board_and_the_record(app, client, monkeypatch):
    """Rendered: a final case lights its tile with its letter (structure
    before color), the record takes the verdict register with its text
    equivalent, and the pre-results copy steps aside."""
    monkeypatch.setenv('CFB_FAKE_NOW', IN_WEEK1_OPEN)   # both clocks in season
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        user = make_user('viewer')
        make_enrollment(user)
        week = make_week(1)
        done = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        done.home_score, done.away_score, done.is_final = 31, 17, True
        later = make_game(week, kickoff=datetime(2026, 9, 3, 23, 30))
        db.session.add_all([
            DocketPick(user_id=user.id, week_id=week.id, game_id=done.id,
                       market='spread', side='home', slot=1,
                       line_value=-3.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=done.id,
                       market='total', side='over', slot=2,
                       line_value=51.5, book='draftkings'),
            DocketPick(user_id=user.id, week_id=week.id, game_id=later.id,
                       market='spread', side='home', slot=3, is_best=True,
                       line_value=-3.5, book='draftkings'),
        ])
        db.session.commit()
        auth_id = user.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    html = client.get('/').get_data(as_text=True)
    docket = html[html.index('hl-panel--docket'):]
    assert 'class="hl-tile is-win" aria-hidden="true">W</span>' in docket
    assert 'class="hl-tile is-loss" aria-hidden="true">L</span>' in docket
    assert 'hl-tile is-held is-x2" aria-hidden="true">3<span class="hl-tile-x2">x2</span>' in docket
    assert 'class="hl-tile" aria-hidden="true">4</span>' in docket
    assert 'hl-tile hl-tile--reserve" aria-hidden="true">R</span>' in docket
    assert 'class="hl-record" role="img" aria-label="1-1 · 1 to play"' in docket
    assert 'Your sheet is complete.' not in docket
    assert 'Your sheet is not finished.' not in docket
    assert '>1</span> to play' in docket
    assert 'class="hl-cta" href="/docket/">Open Your Sheet</a>' in docket
    # No room class or variable leaks into the lounge (the accent firewall).
    assert 'docket-sheet' not in docket and '--game-accent' not in docket


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


# --- The standings board (Brad, 2026-09-12) --------------------------------

def test_leaderboard_weekly_once_three_have_a_final(app, monkeypatch):
    """The board goes weekly once >=3 members have a final this week, ranked by
    live record (marks only, never a point before the week grades)."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)                       # home -3.5 covers → win
        lost = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(lost, 17, 31)                      # home -3.5 fails → loss
        viewer = make_user('you')
        make_enrollment(viewer)
        _hold(viewer, week, won)                  # 1-0
        for name, game in (('amy', won), ('bob', won), ('cyd', lost)):
            u = make_user(name)
            make_enrollment(u)
            _hold(u, week, game)
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'live')
    lb = ctx['leaderboard']
    assert lb['mode'] == 'weekly' and lb['title'] == 'This week'
    top = lb['rows'][0]
    assert top['rank'] == 1 and 'record' in top and 'points' not in top


def test_leaderboard_top_three_plus_you_row(app, monkeypatch):
    """Below the cut, the viewer's own line rides a separator (survivor shape)."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)
        lost = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(lost, 17, 31)
        for name in ('amy', 'bob', 'cyd'):        # three winners: rank 1
            u = make_user(name)
            make_enrollment(u)
            _hold(u, week, won)
        viewer = make_user('zed')
        make_enrollment(viewer)
        _hold(viewer, week, lost)                 # 0-1: below the top three
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'live')
    rows = ctx['leaderboard']['rows']
    assert len(rows) == 4
    assert [r['is_you'] for r in rows] == [False, False, False, True]
    assert rows[-1]['separator_above'] is True and rows[-1]['rank'] == 4


def test_leaderboard_falls_back_to_season_below_three(app, monkeypatch):
    """Under three finals, a graded season carries the board instead."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)
        viewer = make_user('you')
        make_enrollment(viewer)
        _hold(viewer, week, won)                  # only one final: under three
        # A prior graded week gives the season ledger something to rank.
        graded = make_week(2)
        graded.default_error_tenths = 20
        db.session.add(DocketWeekResult(
            user_id=viewer.id, week_id=graded.id, points=9.0, wins=6,
            error_tenths=15, graded_at=datetime(2026, 9, 8, 12, 0)))
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'live')
    lb = ctx['leaderboard']
    assert lb['mode'] == 'season' and lb['title'] == 'The season, so far'
    assert 'points' in lb['rows'][0]


def test_leaderboard_none_when_nothing_to_rank(app, monkeypatch):
    """Early Week 1: under three finals and no graded week, no board at all."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)
        viewer = make_user('you')
        make_enrollment(viewer)
        _hold(viewer, week, won)
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'live')
    assert ctx['leaderboard'] is None


def test_leaderboard_adjourned_shows_season(app, monkeypatch):
    """Between weeks (adjourned), the board is the season ledger (Brad Q1)."""
    at(monkeypatch, IN_WEEK1_CLOSED)
    with app.app_context():
        week = make_week(1)
        week.default_error_tenths = 20
        viewer = make_user('graded')
        make_enrollment(viewer)
        db.session.add(DocketWeekResult(
            user_id=viewer.id, week_id=week.id, points=6.5, wins=5,
            error_tenths=30, graded_at=datetime(2026, 9, 8, 12, 0)))
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'live')
    assert ctx['beat'] == 'adjourned'
    assert ctx['leaderboard']['mode'] == 'season'


def test_leaderboard_unenrolled_gets_none(app, monkeypatch):
    """A non-member sees the sell, never a you-less board."""
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)
        for name in ('amy', 'bob', 'cyd'):
            u = make_user(name)
            make_enrollment(u)
            _hold(u, week, won)
        spectator = make_user('nosy')             # enrolled in nothing
        db.session.flush()
        ctx = lounge.build_lounge_context(spectator, 'live')
    assert ctx['viewer_mode'] == 'view'
    assert 'leaderboard' not in ctx


def test_context_post_shows_season_board_for_member(app, monkeypatch):
    at(monkeypatch, POST_SEASON)
    with app.app_context():
        week = make_week(1)
        week.default_error_tenths = 20
        viewer = make_user('after')
        make_enrollment(viewer)
        db.session.add(DocketWeekResult(
            user_id=viewer.id, week_id=week.id, points=6.5, wins=5,
            error_tenths=30, graded_at=datetime(2026, 9, 8, 12, 0)))
        db.session.flush()
        ctx = lounge.build_lounge_context(viewer, 'post')
    assert ctx['season_complete'] is True
    assert ctx['leaderboard']['mode'] == 'season'


def test_lounge_renders_the_standings_board(app, client, monkeypatch):
    """Rendered: the weekly board prints the survivor .rolls shape, the viewer's
    row wears the You chip, and no room class or var leaks (accent firewall)."""
    monkeypatch.setenv('CFB_FAKE_NOW', IN_WEEK1_OPEN)
    at(monkeypatch, IN_WEEK1_OPEN)
    with app.app_context():
        week = make_week(1)
        won = make_game(week, kickoff=datetime(2026, 9, 1, 23, 30))
        _final(won, 31, 17)
        viewer = make_user('viewer')
        make_enrollment(viewer)
        _hold(viewer, week, won)
        for name in ('amy', 'bob'):
            u = make_user(name)
            make_enrollment(u)
            _hold(u, week, won)
        db.session.commit()
        auth_id = viewer.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    html = client.get('/').get_data(as_text=True)
    docket = html[html.index('hl-panel--docket'):]
    assert 'class="hl-standings"' in docket
    assert 'class="roll-row roll-row--you"' in docket
    assert 'class="roll-you-chip">You<' in docket
    assert 'Full standings' in docket
    assert 'class="roll-record"' in docket
    assert 'docket-sheet' not in docket and '--game-accent' not in docket


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
