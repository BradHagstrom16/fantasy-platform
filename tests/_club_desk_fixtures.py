"""Shared Club Desk test seed (tests/_cfb_fixtures.py pattern).

One default week for both games, aligned as in the 2026 season: CFB
Survivor Week 4 locks Sat Sep 26 11:00 CT, Docket Week 4 closes Sun Sep 27
12:00 PM CT (the Docket's own week math). ``seed`` builds one member in a
named Survivor state and a named Docket state, plus the previous week's
facts the Tuesday Paper reads (a complete CFB Week 3 with an outcome
snapshot; an imported Docket Week 3, graded on request).

The instants are the desk's ``now`` (aware UTC):

  F      Fri Sep 25 10:00 CT  Survivor T-25h; the Docket's 48h target is 2 h away
  S      Sat Sep 26 10:00 CT  Survivor T-1h;  the Docket's 24h target is 2 h away
  D      Sun Sep 27 10:00 CT  the Docket's 2h; Survivor has locked
  PAPER  Tue Sep 22 06:15 CT  the Paper's slot
"""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from extensions import db
from games.cfb.models import CfbWeekOutcome
from games.docket.models import DocketPick, DocketTiebreakerPrediction
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket

SURVIVOR_STATES = ('none', 'eliminated', 'picked', 'owes')
DOCKET_STATES = ('none', 'complete', 'incomplete')

F_AT = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)
S_AT = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)
D_AT = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
PAPER_AT = datetime(2026, 9, 22, 11, 15, tzinfo=UTC)

CFB_WEEK3_DEADLINE = datetime(2026, 9, 19, 11, 0)     # naive pool wall clock
CFB_WEEK4_DEADLINE = datetime(2026, 9, 26, 11, 0)
DOCKET_KICK = datetime(2026, 9, 27, 18, 0)             # naive UTC, after the close
SCORING_SLOTS = 8

DESK_SEND = 'games.club_desk.send_platform_email'


def capture(target=DESK_SEND, *, accept=None):
    """Patch a send site; collect each rendered letter. ``accept`` decides
    per address (default: everything is accepted)."""
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'plain': plain,
                      'html': html})
        return True if accept is None else accept(to)

    return calls, patch(target, side_effect=fake)


def push_capture():
    """Both games' push sites, one list of (tag, user_ids)."""
    calls = []

    def fake(user_ids, **kwargs):
        calls.append((kwargs['tag'], list(user_ids)))
        return len(calls)

    return calls, (patch('games.cfb.services.reminders.send_push',
                         side_effect=fake),
                   patch('games.docket.services.reminders.send_push',
                         side_effect=fake))


def _cfb_weeks():
    oregon, utah = cfb.make_team('Oregon'), cfb.make_team('Utah')
    week3 = cfb.make_week(3, deadline=CFB_WEEK3_DEADLINE, is_complete=True)
    cfb.make_game(week3, oregon, utah, spread=-7.0, winner='home')
    week4 = cfb.make_week(4, deadline=CFB_WEEK4_DEADLINE, is_active=True)
    cfb.make_game(week4, utah, oregon, spread=-3.5)
    return SimpleNamespace(week3=week3, week4=week4, oregon=oregon, utah=utah)


def _docket_weeks():
    week3 = docket.make_week(3)
    week4 = docket.make_week(4)
    games = [docket.make_game(week4, kickoff=DOCKET_KICK, home=f'Home {i}',
                              away=f'Away {i}', total=40.5 + i)
             for i in range(SCORING_SLOTS)]
    week4.tiebreaker_game_id = games[0].id
    return SimpleNamespace(week3=week3, week4=week4, games=games)


def _survivor(user, state, weeks):
    if state == 'none':
        return None
    if state == 'eliminated':
        enrollment = cfb.make_enrollment(user, lives=0, eliminated=True)
        db.session.add(CfbWeekOutcome(
            week_id=weeks.week3.id, user_id=user.id, lives_remaining=0,
            is_eliminated=True, lost_life=True))
        return enrollment
    enrollment = cfb.make_enrollment(user, lives=2)
    # Week 3: survived with Oregon (the Paper's "Last week" line).
    cfb.make_pick(user, weeks.week3, weeks.oregon, is_correct=True,
                  created_at=datetime(2026, 9, 19, 12, 0))
    db.session.add(CfbWeekOutcome(
        week_id=weeks.week3.id, user_id=user.id, lives_remaining=2))
    if state == 'picked':
        cfb.make_pick(user, weeks.week4, weeks.utah,
                      created_at=datetime(2026, 9, 24, 12, 0))
    return enrollment


def _docket(user, state, weeks):
    if state == 'none':
        return None
    enrollment = docket.make_enrollment(user)
    sides = SCORING_SLOTS if state == 'complete' else 5
    for slot in range(1, sides + 1):
        game = weeks.games[slot - 1]
        db.session.add(DocketPick(
            user_id=user.id, week_id=weeks.week4.id, game_id=game.id,
            market='spread', side='home', slot=slot, is_best=(slot == 1),
            line_value=game.home_spread, book='draftkings'))
    if state == 'complete':
        db.session.add(DocketTiebreakerPrediction(
            user_id=user.id, week_id=weeks.week4.id, prediction_tenths=445))
    return enrollment


def seed(survivor='owes', docket_state='incomplete', *, username='member',
         display_name='Member One'):
    """One member in the named states, both games' default week, committed.
    Returns a namespace: user, cfb (week3/week4/teams), docket
    (week3/week4/games), cfb_enrollment, docket_enrollment."""
    cfb_weeks = _cfb_weeks()
    docket_weeks = _docket_weeks()
    user = cfb.make_user(username)
    user.display_name = display_name
    cfb_enrollment = _survivor(user, survivor, cfb_weeks)
    docket_enrollment = _docket(user, docket_state, docket_weeks)
    db.session.commit()
    return SimpleNamespace(
        user=user, cfb=cfb_weeks, docket=docket_weeks,
        cfb_enrollment=cfb_enrollment, docket_enrollment=docket_enrollment)


def add_member(seeded, username, survivor='owes', docket_state='incomplete',
               display_name=None):
    """A further member in the same weeks."""
    user = cfb.make_user(username)
    user.display_name = display_name or username.title()
    _survivor(user, survivor, seeded.cfb)
    _docket(user, docket_state, seeded.docket)
    db.session.commit()
    return user


def docket_open_fn(seeded, status='ok'):
    """A Docket opener that returns the seeded week as a ``status`` import
    without touching the network; asserts the Paper never lets it announce."""
    from games.docket.services.opener import OpenResult

    def fake_docket_open(number, *, announce=True, **_):
        assert announce is False, 'the Paper must never let the opener announce'
        assert number == 4
        return OpenResult(summary={'status': status}, week=seeded.docket.week4,
                          rule_outcome=None, problems=(), announced=0)

    return fake_docket_open


def paper_openers(seeded):
    """The Paper without the network: the CFB opener becomes a no-op (the
    active week already has its lines) and the Docket opener returns the
    seeded week as a whole import. Both are looked up at call time, so a
    module-attribute patch is honest."""
    return (patch('games.cfb.services.automation.run_spread_update',
                  return_value={'status': 'skipped'}),
            patch('games.docket.services.desk._open_by_number',
                  side_effect=docket_open_fn(seeded)))
