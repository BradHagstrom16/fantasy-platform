"""The rule-derived default tiebreaker (games/docket/services/tiebreaker_rule.py).

League vote, 2026-08-22: the tiebreaker case is the LAST game on the docket —
the latest-kickoff NFL game of the week (Monday Night Football; the later of a
doubleheader; Sunday night when no Monday game exists) from FIRST_NFL_WEEK on,
and the latest game on the whole slate in Week 1, which carries no NFL game
(SMU @ Florida State, Mon Sep 7). The rule fills an EMPTY designation only,
never moves one, waits for the target's total rather than sliding to the next
game, and hands every write to admin_ops.designate_tiebreaker so the contract
(check_designation) stays the single authority.
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy import select, update

from extensions import db
from games.docket.models import (
    DocketGame,
    DocketTiebreakerPrediction,
    DocketWeek,
)
from games.docket.services import admin_ops, notifications
from games.docket.services.deadline_pass import check_designation
from games.docket.services.importer import SPORTS
from games.docket.services.tiebreaker_rule import (
    NFL,
    apply_default_tiebreaker,
    default_tiebreaker_game,
)
from games.docket.services.weeks import FIRST_NFL_WEEK, week_number_for
from tests._docket_fixtures import IN_WEEK1, at, make_game, make_week

# Week 2 = Docket week of NFL Week 1: [Tue Sep 8 06:00 CT, Tue Sep 15 06:00 CT),
# deadline Sat Sep 12 11:00 CT = 16:00 UTC. Kickoffs are naive UTC.
IN_WEEK2 = '2026-09-09T12:00:00'
AFTER_W2_DEADLINE = '2026-09-12T16:30:00'
THU = datetime(2026, 9, 11, 0, 15)        # Thu night, before the deadline
SAT = datetime(2026, 9, 12, 18, 0)
SUN_EARLY = datetime(2026, 9, 13, 17, 0)
SUN_LATE = datetime(2026, 9, 13, 20, 25)
SNF = datetime(2026, 9, 14, 0, 20)
MNF = datetime(2026, 9, 15, 0, 15)
MNF_LATE = datetime(2026, 9, 15, 2, 30)
CFB_LATE = datetime(2026, 9, 15, 3, 0)    # contract-only: CFB later than MNF


def _nfl(week, kickoff, **kw):
    return make_game(week, sport=NFL, kickoff=kickoff, **kw)


def _id_of(week):
    db.session.expire_all()
    return week.tiebreaker_game_id


# ── the selection ────────────────────────────────────────────────────────

def test_nfl_week_picks_the_latest_nfl_kickoff_over_snf_and_cfb(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, SNF, home='Sunday Home', away='Sunday Away')
    mnf = _nfl(week, MNF, home='Monday Home', away='Monday Away')
    make_game(week, kickoff=CFB_LATE, home='Late CFB', away='Later CFB')
    db.session.commit()

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'designated'
    assert outcome['game'].id == mnf.id
    assert _id_of(week) == mnf.id


def test_no_monday_game_falls_to_the_latest_sunday_kickoff(app, monkeypatch):
    """NFL Week 18's shape: no Monday game, so Sunday night holds it."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, SUN_EARLY)
    _nfl(week, SUN_LATE)
    snf = _nfl(week, SNF)
    db.session.commit()

    game, reason = default_tiebreaker_game(week)

    assert game.id == snf.id
    assert reason == ''


def test_two_monday_games_pick_the_later_kickoff(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, MNF)
    late = _nfl(week, MNF_LATE)
    _nfl(week, SNF)
    db.session.commit()

    game, _ = default_tiebreaker_game(week)

    assert game.id == late.id


def test_same_instant_tie_breaks_on_api_event_id(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    first = _nfl(week, MNF)
    second = _nfl(week, MNF)
    # Explicit ids: the fixture counter crosses digit lengths, so a string
    # comparison on generated ids would not be the order under test.
    first.api_event_id = 'zz-a'
    second.api_event_id = 'zz-b'
    db.session.commit()

    game, _ = default_tiebreaker_game(week)

    assert game.api_event_id == 'zz-b'


def test_week_one_picks_the_latest_game_on_the_slate(app, monkeypatch):
    """Week 1 carries no NFL game, so the whole slate is the pool — which
    resolves the real 2026 slate to SMU @ Florida State on Labor Day."""
    at(monkeypatch, IN_WEEK1)
    week = make_week(1)
    make_game(week, kickoff=datetime(2026, 9, 5, 23, 30), home='Sat Home',
              away='Sat Away')
    make_game(week, kickoff=datetime(2026, 9, 6, 23, 30),
              home='Notre Dame Fighting Irish', away='Wisconsin Badgers')
    labor_day = make_game(week, kickoff=datetime(2026, 9, 7, 23, 30),
                          home='Florida State Seminoles', away='SMU Mustangs',
                          total=53.5)
    db.session.commit()

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'designated'
    assert _id_of(week) == labor_day.id


def test_nfl_week_with_no_nfl_games_designates_nothing(app, monkeypatch):
    """A partial import that lost the NFL half must never land the tiebreaker
    on a college game after Week 1."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    make_game(week, kickoff=SAT)
    make_game(week, kickoff=CFB_LATE)
    db.session.commit()

    assert default_tiebreaker_game(week) == (None, 'no NFL game on the docket yet')
    outcome = apply_default_tiebreaker(week)
    assert outcome['status'] == 'none'
    assert 'no NFL game' in outcome['reason']
    assert _id_of(week) is None


def test_a_thrown_out_latest_game_yields_to_the_next(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    snf = _nfl(week, SNF)
    mnf = _nfl(week, MNF)
    mnf.no_contest = True
    mnf.nc_reason = 'postponed'
    db.session.commit()

    game, _ = default_tiebreaker_game(week)

    assert game.id == snf.id


def test_a_kickoff_before_the_deadline_is_never_a_candidate(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, THU)
    db.session.commit()

    game, reason = default_tiebreaker_game(week)

    assert game is None
    assert reason == 'no NFL game on the docket yet'
    assert apply_default_tiebreaker(week)['status'] == 'none'


# ── the applier ──────────────────────────────────────────────────────────

def test_an_existing_designation_is_never_moved(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    snf = _nfl(week, SNF)
    mnf = _nfl(week, MNF)
    week.tiebreaker_game_id = snf.id
    db.session.commit()

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'kept'
    assert outcome['game'].id == snf.id
    assert outcome['rule_game'].id == mnf.id
    assert _id_of(week) == snf.id


def test_a_designation_written_behind_the_session_is_still_kept(app, monkeypatch):
    """Fill-only must hold against a hand designation that lands after this
    session loaded the week: the applier re-reads the row (locked, on
    Postgres) before deciding, so a stale in-session None never turns the
    commissioner's write into a silent overwrite."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    snf = _nfl(week, SNF)
    _nfl(week, MNF)
    db.session.commit()
    assert week.tiebreaker_game_id is None
    # Another session's write: an UPDATE that does not synchronize this
    # session's identity map leaves the loaded row stale, exactly the shape
    # of a concurrent admin ruling landing between the check and the write.
    db.session.execute(update(DocketWeek).where(DocketWeek.id == week.id)
                       .values(tiebreaker_game_id=snf.id)
                       .execution_options(synchronize_session=False))
    assert week.tiebreaker_game_id is None, 'precondition: the row is stale'

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'kept'
    assert outcome['game'].id == snf.id
    assert _id_of(week) == snf.id


def test_post_deadline_is_closed_and_writes_nothing(app, monkeypatch):
    at(monkeypatch, AFTER_W2_DEADLINE)
    week = make_week(2)
    _nfl(week, MNF)
    db.session.commit()

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'closed'
    assert _id_of(week) is None


def test_a_missing_total_waits_then_designates_once_locked(app, monkeypatch):
    """Policy: wait for the target's total, never slide to the next game —
    on Tuesday the Monday night total is the one most likely still unposted,
    and a slide would make Sunday night sticky for the week."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, SNF)
    mnf = _nfl(week, MNF, total=None)
    db.session.commit()

    first = apply_default_tiebreaker(week)

    assert first['status'] == 'waiting'
    assert first['rule_game'].id == mnf.id
    assert 'no locked total yet' in first['reason']
    assert _id_of(week) is None

    mnf = db.session.get(DocketGame, mnf.id)
    mnf.total_points = 47.5
    mnf.total_book = 'draftkings'
    mnf.total_locked_at = datetime(2026, 9, 9, 12, 0)
    db.session.commit()

    second = apply_default_tiebreaker(week)

    assert second['status'] == 'designated'
    assert _id_of(week) == mnf.id


def test_an_unsound_locked_total_reports_none_and_rolls_back(app, monkeypatch):
    """A locked .25 total never resolves by waiting (locked lines never move),
    so the rule reports the contract problem and leaves the pick to the desk."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, SNF)
    _nfl(week, MNF, total=47.25)
    db.session.commit()

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'none'
    assert 'whole tenth' in outcome['reason']
    assert _id_of(week) is None


def test_first_time_rule_designation_mails_nobody(app, monkeypatch):
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, MNF)
    db.session.commit()
    spy = MagicMock()
    monkeypatch.setattr(notifications, 'notify_redesignation', spy)

    outcome = apply_default_tiebreaker(week)

    assert outcome['status'] == 'designated'
    spy.assert_not_called()
    assert db.session.scalar(select(DocketTiebreakerPrediction)) is None


def test_rule_pick_is_always_admin_eligible(app, monkeypatch):
    """The rule writes through designate_tiebreaker, so its pick always
    satisfies the same contract the admin screen lists."""
    at(monkeypatch, IN_WEEK2)
    week = make_week(2)
    _nfl(week, SNF)
    mnf = _nfl(week, MNF)
    db.session.commit()

    apply_default_tiebreaker(week)

    assert mnf.id in {g.id for g in admin_ops.eligible_tiebreaker_games(week)}
    assert check_designation(week) == []


def test_nfl_key_and_first_nfl_week_match_reality(app):
    assert NFL in SPORTS
    assert FIRST_NFL_WEEK == 2
    # NFL Week 1 opener (Thu Sep 10 2026, 7:20 PM CT) sits in Docket Week 2.
    assert week_number_for(datetime(2026, 9, 11, 0, 20, tzinfo=UTC)) == 2
    # SMU @ Florida State (Mon Sep 7 2026, 6:30 PM CT) sits in Docket Week 1.
    assert week_number_for(datetime(2026, 9, 7, 23, 30, tzinfo=UTC)) == 1
