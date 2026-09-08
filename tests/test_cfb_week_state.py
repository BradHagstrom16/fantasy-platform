"""One definition of "which week" for the CFB room AND the lounge
(games/cfb/DESIGN.md §10.5: never calculate the same fact differently in
lounge and room).

Brad's rulings (2026-09-07/08): the standings and now the whole room lead
with the REVEAL week — the latest week whose deadline has passed and that
has games — while it is unfinished; the PICK week (the active week while
its deadline is ahead, ADR-062: a week is active only once its lines have
landed) is the one thing that never follows it. The states:

  open     the pick week leads (nothing older is unfinished)
  locked   the reveal week leads, unfinished, and nothing is open yet
  overlap  the reveal week leads, unfinished, while the pick week is open
  verdict  the reveal week leads, complete, and nothing is open yet
  none     no week to talk about
"""
from datetime import datetime

from extensions import db
from games.cfb.services.week_state import (
    pending_games,
    pick_week,
    reveal_week,
    room_weeks,
)
from tests._cfb_fixtures import make_game, make_team, make_week

WEEK1_DEADLINE = datetime(2026, 9, 5, 11, 0)     # naive pool wall clock
WEEK2_DEADLINE = datetime(2026, 9, 12, 11, 0)
PRESEASON = '2026-09-02T12:00:00'                # nothing locked yet
SATURDAY_NIGHT = '2026-09-06T02:00:00'           # Sat 9 PM CT: W1 locked, pending
MONDAY_NIGHT = '2026-09-07T22:00:00'             # W1 still pending, W2 open
TUESDAY = '2026-09-08T14:00:00'                  # W1 complete
SUNDAY_AFTER_W2 = '2026-09-13T17:00:00'          # W2 locked as well


def _teams(*names):
    return [make_team(n) for n in names]


def test_state_open_with_only_an_active_future_week(app, monkeypatch):
    week = make_week(1, deadline=WEEK1_DEADLINE, is_active=True)
    make_game(week, *_teams('Georgia', 'Clemson'), spread=-7.0)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', PRESEASON)

    room = room_weeks()

    assert room.state == 'open'
    assert room.lead.id == week.id and room.pick.id == week.id
    assert room.reveal is None and room.pending == [] and room.note is False


def test_state_locked_between_deadline_and_completion(app, monkeypatch):
    week = make_week(1, deadline=WEEK1_DEADLINE, is_active=True)
    game = make_game(week, *_teams('Georgia', 'Clemson'), spread=-7.0)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', SATURDAY_NIGHT)

    room = room_weeks()

    assert room.state == 'locked'
    assert room.lead.id == week.id and room.reveal.id == week.id
    assert room.pick is None                     # locked: nothing to pick in
    assert [g.id for g in room.pending] == [game.id]
    assert room.note is False


def test_state_overlap_when_prior_week_pends(app, monkeypatch):
    """Monday night: Week 1's game is still to play and Week 2 has opened."""
    week1 = make_week(1, deadline=WEEK1_DEADLINE)
    fsu, smu, georgia = _teams('Florida State', 'SMU', 'Georgia')
    make_game(week1, fsu, smu, spread=-3.5)                  # pending
    week2 = make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    make_game(week2, smu, georgia, spread=-2.5)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)

    room = room_weeks()

    assert room.state == 'overlap'
    assert room.lead.id == week1.id and room.reveal.id == week1.id
    assert room.pick.id == week2.id
    assert len(room.pending) == 1
    assert room.note is True                     # the table still says W1


def test_state_verdict_after_completion_before_next_open(app, monkeypatch):
    """Tuesday: Week 1 complete and still active; Week 2 imported but not
    yet opened (its lines land at 6:00 AM, ADR-062)."""
    week1 = make_week(1, deadline=WEEK1_DEADLINE, is_active=True,
                      is_complete=True)
    georgia, clemson = _teams('Georgia', 'Clemson')
    make_game(week1, georgia, clemson, spread=-7.0, winner='away')
    week2 = make_week(2, deadline=WEEK2_DEADLINE)
    make_game(week2, clemson, georgia)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    room = room_weeks()

    assert room.state == 'verdict'
    assert room.lead.id == week1.id and room.pick is None
    assert room.pending == [] and room.note is False


def test_state_open_keeps_the_note_when_an_older_week_is_complete(
        app, monkeypatch):
    """The ordinary Tue–Sat state: Week 2 open, Week 1 done. The table still
    shows Week 1's verdicts, so the note that says so stays."""
    week1 = make_week(1, deadline=WEEK1_DEADLINE, is_complete=True)
    georgia, clemson = _teams('Georgia', 'Clemson')
    make_game(week1, georgia, clemson, spread=-7.0, winner='away')
    week2 = make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    make_game(week2, clemson, georgia, spread=-2.5)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    room = room_weeks()

    assert room.state == 'open'
    assert room.lead.id == week2.id and room.reveal.id == week1.id
    assert room.note is True


def test_state_none_without_weeks(app, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', PRESEASON)

    room = room_weeks()

    assert room.state == 'none'
    assert room.lead is None and room.pick is None and room.reveal is None


def test_degenerate_past_active_week_without_games_still_leads(
        app, monkeypatch):
    """Many older tests seed a past-deadline active week with no games. It
    is nobody's reveal week (no games) and nobody's pick week (locked), but
    the room must still render: it leads as ``locked`` with nothing pending."""
    week = make_week(1, deadline=WEEK1_DEADLINE, is_active=True)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    room = room_weeks()

    assert room.state == 'locked'
    assert room.lead.id == week.id and room.reveal is None
    assert room.pending == []


def test_reveal_week_skips_zero_game_weeks(app, monkeypatch):
    """An orphan week (setup created it, the import failed) whose deadline
    has passed must never lead the room or the table."""
    week1 = make_week(1, deadline=WEEK1_DEADLINE)
    make_game(week1, *_teams('Georgia', 'Clemson'), spread=-7.0)
    make_week(2, deadline=WEEK2_DEADLINE)                 # no games
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', SUNDAY_AFTER_W2)

    assert reveal_week().id == week1.id


def test_pick_week_is_the_open_active_week_only(app, monkeypatch):
    """Active but locked → None; inactive but open → None (ADR-062: a week
    that has not opened is not a week anyone can pick in)."""
    make_week(1, deadline=WEEK1_DEADLINE, is_active=True)
    make_week(2, deadline=WEEK2_DEADLINE)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)

    assert pick_week() is None


def test_pending_games_ordered_by_kickoff(app, monkeypatch):
    week = make_week(1, deadline=WEEK1_DEADLINE)
    a, b, c, d = _teams('A', 'B', 'C', 'D')
    late = make_game(week, a, b, spread=-1.0)
    late.game_time = datetime(2026, 9, 7, 18, 30)         # Monday night
    early = make_game(week, c, d, spread=-1.0)
    early.game_time = datetime(2026, 9, 5, 14, 30)        # Saturday
    make_game(week, b, c, spread=-1.0, winner='home')     # settled: excluded
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', SATURDAY_NIGHT)

    assert [g.id for g in pending_games(week)] == [early.id, late.id]
