"""Season aggregates behind the pick page (games/golf/services/stats.py): Golf Phase U2.

- the burn share is the complement of the rounded share of the room that has
  spent a golfer, None before the season's first burn (the pick page draws no
  hatch then), and the room is the season's enrollees;
- year-to-date money is the golfer's own prize money, banked tournaments of
  the season only;
- the week a member spent a golfer is read from the pick whose golfer counted.

The burn tests are ported from the legacy app's ``tests/test_burn_list.py``.
"""
from datetime import datetime

import pytest

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentResult,
)
from games.golf.services.stats import (
    SpentWeek,
    remaining_pct_map,
    spent_weeks,
    ytd_earnings,
)
from models.user import User


@pytest.fixture()
def season(app):
    return app.config['SEASON_YEAR']


# --- seed helpers (run inside the fixture's app context) --------------------

def _user(username):
    user = User(username=username, email=f'{username}@test.com', display_name=username)
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    return user


def _member(season, username):
    user = _user(username)
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season))
    db.session.commit()
    return user


def _golfer(last):
    player = GolfPlayer(api_player_id=last[:20], first_name='Test', last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _tournament(season, name, week, finalized=True):
    t = GolfTournament(
        api_tourn_id=f'T-{name}'[:20], name=name, season_year=season,
        start_date=datetime(2026, 1, 1 + week), end_date=datetime(2026, 1, 4 + week),
        pick_deadline=datetime(2026, 1, 1 + week, 7), purse=10_000_000,
        status='complete' if finalized else 'active', results_finalized=finalized,
        week_number=week,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _burn(user, player, season):
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=player.id, season_year=season,
    ))
    db.session.commit()


def _earn(tournament, player, earnings):
    db.session.add(GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status='complete',
        final_position='1', rounds_completed=4, earnings=earnings,
    ))
    db.session.commit()


# ============================================================================
# remaining_pct_map
# ============================================================================

def test_remaining_pct_is_the_complement_of_the_burn_share(app, season):
    members = [_member(season, f'm{i}') for i in range(4)]
    scott, rory, spare = _golfer('Scheffler'), _golfer('McIlroy'), _golfer('Spare')
    _burn(members[0], scott, season)
    _burn(members[1], scott, season)
    _burn(members[2], rory, season)

    pct = remaining_pct_map(season, [scott.id, rory.id, spare.id])
    assert pct[scott.id] == 50      # 100 - 50
    assert pct[rory.id] == 75       # 100 - 25
    assert pct[spare.id] == 100     # nobody has spent him


def test_remaining_pct_is_none_before_the_first_burn(app, season):
    """None, not a map of 100s: the pick page draws no hatch without a signal."""
    _member(season, 'solo')
    player = _golfer('Fresh')
    assert remaining_pct_map(season, [player.id]) is None


def test_remaining_pct_is_the_complement_of_the_rounded_share(app, season):
    """7 members, 2 burns: 29% burned, so 71% remain and the two sum to 100."""
    members = [_member(season, f'm{i}') for i in range(7)]
    scott = _golfer('Scheffler')
    _burn(members[0], scott, season)
    _burn(members[1], scott, season)

    assert remaining_pct_map(season, [scott.id])[scott.id] == 71


def test_remaining_pct_counts_the_seasons_enrollees_only(app, season):
    """The room is the sheet's roster: a platform user with no line neither
    dilutes the share nor adds a burn to it."""
    members = [_member(season, f'm{i}') for i in range(2)]
    outsider = _user('no_line')
    scott = _golfer('Scheffler')
    _burn(members[0], scott, season)
    _burn(outsider, scott, season)

    assert remaining_pct_map(season, [scott.id])[scott.id] == 50   # 1 of 2, not 2 of 3


def test_remaining_pct_ignores_another_seasons_usage(app, season):
    member = _member(season, 'returning')
    db.session.add(GolfEnrollment(user_id=member.id, season_year=season - 1))
    scott = _golfer('Scheffler')
    _burn(member, scott, season - 1)

    assert remaining_pct_map(season, [scott.id]) is None


# ============================================================================
# ytd_earnings
# ============================================================================

def test_ytd_earnings_sums_the_seasons_banked_tournaments(app, season):
    scott, idle = _golfer('Scheffler'), _golfer('Idle')
    _earn(_tournament(season, 'Sony Open', 1), scott, 100_000)
    _earn(_tournament(season, 'The American Express', 2), scott, 250_000)
    _earn(_tournament(season, 'On The Course', 3, finalized=False), scott, 999_999)
    _earn(_tournament(season - 1, 'Last Year', 4), scott, 5_000_000)

    ytd = ytd_earnings(season)
    assert ytd[scott.id] == 350_000          # the live week and last season stay out
    assert idle.id not in ytd                # no result, no line


# ============================================================================
# spent_weeks
# ============================================================================

def test_spent_weeks_names_the_week_the_golfer_counted(app, season):
    """The golfer who counted is the one spent: here the backup, the primary
    having withdrawn early and gone back to the pool."""
    member = _member(season, 'viewer')
    primary, backup = _golfer('Withdrew'), _golfer('Counted')
    masters = _tournament(season, 'Masters Tournament', 13)
    db.session.add(GolfPick(
        user_id=member.id, tournament_id=masters.id,
        primary_player_id=primary.id, backup_player_id=backup.id,
        active_player_id=backup.id, points_earned=120_000, backup_used=True,
    ))
    db.session.commit()

    assert spent_weeks(member.id, season) == {
        backup.id: SpentWeek(13, 'Masters Tournament'),
    }


def test_spent_weeks_names_the_first_week_a_golfer_counted_twice(app, season):
    """An override can leave one golfer counting in two weeks (clear_resolution
    keeps his usage while another resolved pick names him): the week he was
    spent is the first, whatever order the rows were written in."""
    member = _member(season, 'viewer')
    twice, other = _golfer('Twice'), _golfer('Other')
    later = _tournament(season, 'Later Week', 14)
    first = _tournament(season, 'First Week', 9)
    db.session.add_all([
        GolfPick(user_id=member.id, tournament_id=week.id,
                 primary_player_id=twice.id, backup_player_id=other.id,
                 active_player_id=twice.id, points_earned=10)
        for week in (later, first)
    ])
    db.session.commit()

    assert spent_weeks(member.id, season) == {twice.id: SpentWeek(9, 'First Week')}


def test_spent_weeks_skips_unresolved_picks_other_members_and_seasons(app, season):
    member, other = _member(season, 'viewer'), _member(season, 'other')
    a, b, c, d = (_golfer(name) for name in ('Alpha', 'Bravo', 'Charlie', 'Delta'))
    open_week = _tournament(season, 'Open Week', 14, finalized=False)
    banked = _tournament(season, 'Banked Week', 12)
    last_year = _tournament(season - 1, 'Last Year', 5)
    db.session.add_all([
        # Still open: nobody has counted yet.
        GolfPick(user_id=member.id, tournament_id=open_week.id,
                 primary_player_id=a.id, backup_player_id=b.id),
        # Another member's week.
        GolfPick(user_id=other.id, tournament_id=banked.id,
                 primary_player_id=c.id, backup_player_id=d.id,
                 active_player_id=c.id, points_earned=10),
        # The viewer's own, a season ago.
        GolfPick(user_id=member.id, tournament_id=last_year.id,
                 primary_player_id=c.id, backup_player_id=d.id,
                 active_player_id=c.id, points_earned=10),
    ])
    db.session.commit()

    assert spent_weeks(member.id, season) == {}
