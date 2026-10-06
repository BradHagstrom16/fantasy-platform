"""Season aggregates (games/golf/services/stats.py): Golf Phase U2 (the pick
page's three reads) and U5 (the Record Room's, in the file's second half).

- the burn share is the complement of the rounded share of the room that has
  spent a golfer, None before the season's first burn (the pick page draws no
  hatch then), and the room is the season's enrollees;
- year-to-date money is the golfer's own prize money, banked tournaments of
  the season only;
- the week a member spent a golfer is read from the pick whose golfer counted.

The burn tests are ported from the legacy app's ``tests/test_burn_list.py``.
"""
from contextlib import contextmanager
from datetime import datetime

import pytest
from sqlalchemy import event

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentResult,
)
from games.golf.services import stats
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


@contextmanager
def _count_sql():
    """Count the statements a block sends (the route tests' own counter)."""
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _before)
    try:
        yield counter
    finally:
        event.remove(db.engine, 'before_cursor_execute', _before)


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


# ============================================================================
# The Record Room's aggregates (Golf Phase U5)
#
# Ported from the legacy app's tests/test_stats.py and tests/test_burn_list.py
# under the port rules: banked means results_finalized, the room is the
# season's enrollees, ranks are competition ranks, ties break on a name, and
# a missed cut is read whatever its casing.
# ============================================================================

def _player(first, last):
    player = GolfPlayer(api_player_id=f'{first}{last}'[:20], first_name=first, last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _event(season, name, start, purse=10_000_000, is_major=False, finalized=True):
    t = GolfTournament(
        api_tourn_id=f'E-{name}'[:20], name=name, season_year=season,
        start_date=start, end_date=start, pick_deadline=start, purse=purse,
        is_major=is_major, status='complete', results_finalized=finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _result(tournament, player, status='complete', position='1', earnings=0):
    db.session.add(GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status=status,
        final_position=position, rounds_completed=4, earnings=earnings,
    ))
    db.session.commit()


def _pick(user, tournament, primary, backup, **kwargs):
    pick = GolfPick(
        user_id=user.id, tournament_id=tournament.id,
        primary_player_id=primary.id, backup_player_id=backup.id, **kwargs,
    )
    db.session.add(pick)
    db.session.commit()
    return pick


def _names(season):
    return {
        e.user_id: e.user.get_display_name()
        for e in GolfEnrollment.query.filter_by(season_year=season)
    }


@pytest.fixture()
def room(app, season):
    """Three members over four banked events, one of them a major.

    Alice rides Scheffler every week; Bob's McIlroy misses the cut at the
    Masters (0, a penalty); Carol's backup counts at the Genesis. Aberg earns
    well and is never spent. Usage rows are what ``resolve_pick`` writes.
    """
    alice, bob, carol = (_member(season, name) for name in ('Alice', 'Bob', 'Carol'))
    scott = _player('Scottie', 'Scheffler')
    rory = _player('Rory', 'McIlroy')
    xander = _player('Xander', 'Schauffele')
    backup = _player('Backup', 'Guy')
    aberg = _player('Ludvig', 'Aberg')

    events = [
        _event(season, 'Sony Open', datetime(2026, 1, 8), purse=8_000_000),
        _event(season, 'Genesis', datetime(2026, 2, 12), purse=20_000_000),
        _event(season, 'The Masters', datetime(2026, 4, 9), purse=20_000_000, is_major=True),
        _event(season, 'Wells Fargo', datetime(2026, 5, 7), purse=9_000_000),
    ]
    t1, t2, t3, t4 = events
    field = {
        scott:  [('complete', '1', 2_000_000), ('complete', '2', 1_200_000),
                 ('complete', '1', 4_000_000), ('complete', 'T3', 600_000)],
        # The archive's casing drifts: this cut is stored in capitals.
        rory:   [('complete', 'T5', 400_000), ('complete', '1', 3_600_000),
                 ('CUT', 'CUT', 0), ('complete', '2', 1_000_000)],
        xander: [('complete', 'T10', 200_000), ('complete', 'T20', 90_000),
                 ('complete', 'T8', 300_000), ('complete', 'T15', 120_000)],
        backup: [('complete', 'T30', 40_000), ('complete', 'T40', 25_000),
                 ('complete', 'T50', 18_000), ('complete', 'T45', 22_000)],
        aberg:  [('complete', '2', 1_100_000), ('complete', 'T3', 700_000),
                 ('complete', 'T5', 500_000), ('complete', '1', 1_600_000)],
    }
    for player, rows in field.items():
        for tournament, (status, position, earnings) in zip(events, rows, strict=True):
            _result(tournament, player, status, position, earnings)

    for tournament, points in zip(events, (2_000_000, 1_200_000, 6_000_000, 600_000), strict=True):
        _pick(alice, tournament, scott, backup, active_player_id=scott.id, points_earned=points)
    _pick(bob, t1, rory, backup, active_player_id=rory.id, points_earned=400_000)
    _pick(bob, t2, rory, backup, active_player_id=rory.id, points_earned=3_600_000)
    _pick(bob, t3, rory, xander, active_player_id=rory.id, points_earned=0,
          penalty_triggered=True)
    _pick(bob, t4, rory, backup, active_player_id=rory.id, points_earned=1_000_000)
    _pick(carol, t1, xander, backup, active_player_id=xander.id, points_earned=200_000)
    _pick(carol, t2, xander, backup, active_player_id=backup.id, points_earned=25_000,
          backup_used=True)
    _pick(carol, t3, xander, backup, active_player_id=xander.id, points_earned=300_000)
    _pick(carol, t4, xander, backup, active_player_id=xander.id, points_earned=120_000)

    for user, player in ((alice, scott), (bob, rory), (carol, xander), (carol, backup)):
        _burn(user, player, season)

    return {
        'users': {'alice': alice, 'bob': bob, 'carol': carol},
        'players': {'scott': scott, 'rory': rory, 'xander': xander,
                    'backup': backup, 'aberg': aberg},
        'events': events,
    }


# --- season_progress --------------------------------------------------------

def test_season_progress_counts_banked_of_scheduled(app, season, room):
    _event(season, 'Played, Not Final', datetime(2026, 6, 1), finalized=False)
    _event(season - 1, 'Last Year', datetime(2025, 6, 1))
    assert stats.season_progress(season) == stats.SeasonProgress(banked=4, total=5)


def test_season_progress_of_an_empty_season(app, season):
    assert stats.season_progress(season) == stats.SeasonProgress(banked=0, total=0)


# --- season_race ------------------------------------------------------------

def test_season_race_runs_each_members_banked_total(app, season, room):
    race = stats.season_race(season, _names(season))
    assert race['count'] == 4
    assert [t['name'] for t in race['tournaments']] == [
        'Sony Open', 'Genesis', 'The Masters', 'Wells Fargo']
    assert [t['short'] for t in race['tournaments']] == ['Jan', 'Feb', 'Apr', 'May']
    # 'The Masters' brings its own article: never "the The Masters".
    assert [t['the'] for t in race['tournaments']] == [
        'the Sony Open', 'the Genesis', 'the Masters', 'the Wells Fargo']

    by_name = {s['name']: s for s in race['series']}
    assert by_name['Alice']['cumulative'] == [2_000_000, 3_200_000, 9_200_000, 9_800_000]
    assert by_name['Bob']['cumulative'] == [400_000, 4_000_000, 4_000_000, 5_000_000]
    assert by_name['Carol']['final'] == 645_000

    leader = race['series'][0]
    assert (leader['name'], leader['rank'], leader['rank_label'], leader['is_leader']) == (
        'Alice', 1, '1', True)
    assert [s['is_leader'] for s in race['series']] == [True, False, False]
    assert race['max_value'] == 9_800_000


def test_season_race_of_an_empty_season(app, season):
    _member(season, 'Solo')
    assert stats.season_race(season, _names(season)) == {
        'tournaments': [], 'series': [], 'max_value': 0, 'count': 0}


def test_season_race_draws_every_member_of_the_room_and_nobody_else(app, season, room):
    """A member with no picks runs flat along the floor; a pick by someone
    with no line this season is not the room's."""
    _member(season, 'Dave')
    outsider = _user('no_line')
    _pick(outsider, room['events'][0], room['players']['aberg'], room['players']['backup'],
          active_player_id=room['players']['aberg'].id, points_earned=50_000_000)

    race = stats.season_race(season, _names(season))
    by_name = {s['name']: s for s in race['series']}
    assert set(by_name) == {'Alice', 'Bob', 'Carol', 'Dave'}
    assert by_name['Dave']['cumulative'] == [0, 0, 0, 0]
    assert race['max_value'] == 9_800_000


def test_season_race_counts_banked_tournaments_of_this_season_only(app, season, room):
    alice, scott, backup = room['users']['alice'], room['players']['scott'], room['players']['backup']
    settling = _event(season, 'Settling', datetime(2026, 6, 1), finalized=False)
    last_year = _event(season - 1, 'Last Year', datetime(2025, 6, 1))
    _pick(alice, settling, backup, scott, active_player_id=backup.id, points_earned=7_000_000)
    _pick(alice, last_year, backup, scott, active_player_id=backup.id, points_earned=7_000_000)

    race = stats.season_race(season, _names(season))
    assert race['count'] == 4
    assert race['series'][0]['final'] == 9_800_000


def test_season_race_ranks_in_competition_rank(app, season):
    """Ties share and the next rank gaps (1, 1, 3), in name order within a tie."""
    members = [_member(season, name) for name in ('Zed', 'Amy', 'Low')]
    golfer, other = _golfer('Golfer'), _golfer('Other')
    opener = _event(season, 'Opener', datetime(2026, 1, 8))
    for member, points in zip(members, (500, 500, 100), strict=True):
        _pick(member, opener, golfer, other, active_player_id=golfer.id, points_earned=points)

    series = stats.season_race(season, _names(season))['series']
    assert [(s['name'], s['rank'], s['rank_label']) for s in series] == [
        ('Amy', 1, 'T1'), ('Zed', 1, 'T1'), ('Low', 3, '3')]
    # A shared lead is never one member's: both lead.
    assert [s['is_leader'] for s in series] == [True, True, False]


def test_season_race_takes_two_queries_whatever_the_room(app, season, room):
    names = _names(season)
    with _count_sql() as counter:
        stats.season_race(season, names)
    assert counter['n'] == 2


# --- superlatives -----------------------------------------------------------

def test_superlatives_name_the_seasons_five_lines(app, season, room):
    sup = stats.superlatives(season, _names(season))

    best = sup.pick_of_season
    assert (best.member, best.golfer.last_name, best.event, best.amount) == (
        'Alice', 'Scheffler', 'The Masters', 6_000_000)       # the major, multiplied
    assert sup.most_cuts == stats.CountLine('Bob', 1, 4)       # the cut stored as 'CUT'
    assert sup.wd_survivor == stats.CountLine('Carol', 1, 4)
    assert sup.most_consistent == stats.CountLine('Alice', 4, 4)   # Carol also 4 of 4: the name
    cold = sup.coldest_pick
    assert (cold.member, cold.golfer.last_name, cold.event, cold.amount) == (
        'Bob', 'McIlroy', 'The Masters', 20_000_000)


def test_superlatives_of_an_empty_season(app, season):
    _member(season, 'Solo')
    assert stats.superlatives(season, _names(season)) == stats.Superlatives(
        None, None, None, None, None)


def test_superlatives_name_the_golfer_who_counted(app, season):
    """The backup counted (the primary withdrew early): the line names him."""
    member = _member(season, 'Carol')
    primary, backup = _golfer('Withdrew'), _golfer('Counted')
    opener = _event(season, 'Opener', datetime(2026, 1, 8))
    _pick(member, opener, primary, backup, active_player_id=backup.id,
          points_earned=900_000, backup_used=True)

    assert stats.superlatives(season, _names(season)).pick_of_season.golfer.last_name == 'Counted'


def test_superlative_ties_go_to_the_name(app, season):
    """Two members with one missed cut and one backup week each: the count
    alone cannot choose, so the name does, whatever order the rows came in."""
    zed, amy = _member(season, 'Zed'), _member(season, 'Amy')
    cut_a, cut_b, spare = _golfer('CutA'), _golfer('CutB'), _golfer('Spare')
    opener = _event(season, 'Opener', datetime(2026, 1, 8))
    _result(opener, cut_a, status='cut', position='CUT')
    _result(opener, cut_b, status='dq', position='DQ')
    _pick(zed, opener, spare, cut_a, active_player_id=cut_a.id, points_earned=0,
          backup_used=True)
    _pick(amy, opener, spare, cut_b, active_player_id=cut_b.id, points_earned=0,
          backup_used=True)

    sup = stats.superlatives(season, _names(season))
    assert sup.most_cuts.member == 'Amy'
    assert sup.wd_survivor.member == 'Amy'
    assert sup.most_consistent is None                 # nobody finished in the money
    assert sup.coldest_pick.member == 'Zed'            # equal purses: the first pick written


def test_most_consistent_prefers_the_member_who_needed_fewer_weeks(app, season):
    steady, busy = _member(season, 'Steady'), _member(season, 'Busy')
    golfer, other = _golfer('Golfer'), _golfer('Other')
    first = _event(season, 'First', datetime(2026, 1, 8))
    second = _event(season, 'Second', datetime(2026, 1, 15))
    _pick(steady, first, golfer, other, active_player_id=golfer.id, points_earned=10)
    _pick(busy, first, golfer, other, active_player_id=golfer.id, points_earned=10)
    _pick(busy, second, golfer, other, active_player_id=golfer.id, points_earned=0)

    assert stats.superlatives(season, _names(season)).most_consistent == stats.CountLine(
        'Steady', 1, 1)


def test_superlatives_take_two_queries_whatever_the_room(app, season, room):
    names = _names(season)
    with _count_sql() as counter:
        stats.superlatives(season, names)
    assert counter['n'] == 2


# --- field_form: Form Guide and Still on the Board --------------------------

def test_form_guide_runs_in_prize_order(app, season, room):
    guide = stats.field_form(season).form_guide
    top = guide[0]
    assert (top.player.last_name, top.prize, top.events, top.cuts, top.best_finish) == (
        'Scheffler', 7_800_000, 4, 0, '1')
    rory = next(row for row in guide if row.player.last_name == 'McIlroy')
    assert (rory.cuts, rory.best_finish) == (1, '1')
    assert [row.prize for row in guide] == sorted((row.prize for row in guide), reverse=True)


def test_form_guide_stops_at_its_limit(app, season):
    opener = _event(season, 'Opener', datetime(2026, 1, 8))
    for i in range(stats.FORM_GUIDE_LIMIT + 3):
        _result(opener, _golfer(f'Golfer{i:02d}'), position=str(i + 1), earnings=1000 - i)
    assert len(stats.field_form(season).form_guide) == stats.FORM_GUIDE_LIMIT


def test_still_on_the_board_is_the_top_money_nobody_has_spent(app, season, room):
    """The complement of the Burn List: Aberg earned and nobody spent him."""
    names = [row.player.last_name for row in stats.field_form(season).still_on_board]
    assert names == ['Aberg']
    assert stats.field_form(season).still_on_board[0].prize == 3_900_000


def test_a_backup_who_never_counted_is_still_on_the_board(app, season):
    """Naming a golfer spends nobody: only the golfer who counted is spent."""
    member = _member(season, 'Viewer')
    counted, named = _golfer('Counted'), _golfer('Named')
    opener = _event(season, 'Opener', datetime(2026, 1, 8))
    _result(opener, counted, earnings=500_000)
    _result(opener, named, position='2', earnings=300_000)
    _pick(member, opener, counted, named, active_player_id=counted.id, points_earned=500_000)
    _burn(member, counted, season)

    assert [row.player.last_name for row in stats.field_form(season).still_on_board] == ['Named']


def test_field_form_of_an_empty_season(app, season):
    assert stats.field_form(season) == stats.FieldForm([], [])


# --- burn_list --------------------------------------------------------------

@pytest.fixture()
def league(app, season):
    """Four members: Alice and Bob spent Scheffler, Carol spent McIlroy, Dave nobody."""
    alice, bob, carol, dave = (_member(season, name) for name in ('alice', 'bob', 'carol', 'dave'))
    scott, rory, backup = _player('Scottie', 'Scheffler'), _player('Rory', 'McIlroy'), _player('Backup', 'Guy')
    t1 = _event(season, 'Sony Open', datetime(2026, 1, 8))
    t2 = _event(season, 'Genesis', datetime(2026, 2, 12))
    _pick(alice, t1, scott, backup, active_player_id=scott.id, points_earned=2_000_000)
    _pick(bob, t2, scott, backup, active_player_id=scott.id, points_earned=1_200_000)
    _pick(carol, t1, rory, backup, active_player_id=rory.id, points_earned=400_000)
    for user, player in ((alice, scott), (bob, scott), (carol, rory)):
        _burn(user, player, season)
    return {'users': {'alice': alice, 'bob': bob, 'carol': carol, 'dave': dave},
            'players': {'scott': scott, 'rory': rory, 'backup': backup},
            'events': [t1, t2]}


def _burned(season):
    return [row.player.full_name() for row in stats.burn_list(season)]


def test_burn_list_counts_share_and_return(app, season, league):
    by_name = {row.player.full_name(): row for row in stats.burn_list(season)}
    scott = by_name['Scottie Scheffler']
    assert (scott.times_used, scott.pct_burned, scott.total_return) == (2, 50, 3_200_000)
    rory = by_name['Rory McIlroy']
    assert (rory.times_used, rory.pct_burned, rory.total_return) == (1, 25, 400_000)


def test_burn_list_runs_most_burned_first(app, season, league):
    assert _burned(season) == ['Scottie Scheffler', 'Rory McIlroy']


def test_burn_list_tie_breaks_by_return(app, season, league):
    thomas = _player('Justin', 'Thomas')
    for name in ('carol', 'dave'):
        _burn(league['users'][name], thomas, season)
    assert _burned(season) == ['Scottie Scheffler', 'Justin Thomas', 'Rory McIlroy']


def test_burn_list_tie_breaks_by_last_name_then_full_name(app, season, league):
    """Equal share and return: last name, then the full name. The golfers are
    created in reverse order so insertion order cannot pass by accident."""
    t1, t2 = league['events']
    backup = league['players']['backup']
    zed, aaron = _player('Zed', 'Smith'), _player('Aaron', 'Smith')
    zeta, alpha = _player('Zed', 'Zeta'), _player('Aaron', 'Alpha')
    for user, tournament, player in (
        ('dave', t1, zed), ('alice', t2, aaron), ('bob', t1, zeta), ('carol', t2, alpha),
    ):
        _pick(league['users'][user], tournament, player, backup,
              active_player_id=player.id, points_earned=500_000)
        _burn(league['users'][user], player, season)

    assert _burned(season) == [
        'Scottie Scheffler', 'Aaron Alpha', 'Aaron Smith', 'Zed Smith', 'Zed Zeta', 'Rory McIlroy']


def test_burn_list_share_is_of_the_seasons_enrollees(app, season, league):
    """A member with a line and no picks still dilutes the share; a platform
    user with no line does not, and their usage is not the room's."""
    outsider = _user('no_line')
    _burn(outsider, league['players']['rory'], season)
    assert stats.burn_list(season)[0].pct_burned == 50      # 2 of 4
    _member(season, 'lurker')
    assert stats.burn_list(season)[0].pct_burned == 40      # 2 of 5
    assert stats.burn_list(season)[1].times_used == 1       # McIlroy: Carol only


def test_burn_list_share_rounds_to_the_nearest_whole(app, season, league):
    for i in range(3):
        _member(season, f'extra{i}')
    assert stats.burn_list(season)[0].pct_burned == 29      # 2 of 7


def test_burn_list_rounds_half_to_even(app, season):
    """1 of 8 is 12 and 3 of 8 is 38: Python's rounding, not int(x + 0.5)."""
    members = [_member(season, f'm{i}') for i in range(8)]
    low, high = _player('Lone', 'Burn'), _player('Trio', 'Burn')
    _burn(members[0], low, season)
    for member in members[1:4]:
        _burn(member, high, season)
    by_name = {row.player.first_name: row.pct_burned for row in stats.burn_list(season)}
    assert by_name == {'Lone': 12, 'Trio': 38}


def test_burn_list_burned_by_all_leaves_none(app, season):
    members = [_member(season, f'm{i}') for i in range(3)]
    chalk = _golfer('Chalk')
    for member in members:
        _burn(member, chalk, season)
    assert stats.burn_list(season)[0].pct_burned == 100
    assert remaining_pct_map(season, [chalk.id])[chalk.id] == 0


def test_burn_list_keeps_a_share_that_rounds_to_nothing(app, season):
    """1 burn in a room of 201 rounds to 0% and the row still shows."""
    picker = _member(season, 'picker')
    fillers = [User(username=f'filler{n}', email=f'filler{n}@test.com', password_hash='x')
               for n in range(200)]
    db.session.add_all(fillers)
    db.session.flush()
    db.session.add_all([GolfEnrollment(user_id=u.id, season_year=season) for u in fillers])
    db.session.commit()
    _burn(picker, _golfer('DeepCut'), season)

    rows = stats.burn_list(season)
    assert [(row.times_used, row.pct_burned) for row in rows] == [(1, 0)]


def test_burn_list_ignores_other_seasons(app, season, league):
    dave = league['users']['dave']
    db.session.add(GolfEnrollment(user_id=dave.id, season_year=season - 1))
    db.session.commit()
    _burn(dave, _player('Last', 'Year'), season - 1)
    assert 'Last Year' not in _burned(season)


def test_burn_list_of_an_empty_season(app, season):
    assert stats.burn_list(season) == []


def test_burn_list_ignores_a_pick_in_flight(app, season, league):
    """A live week burns nobody: no usage row until the results are final."""
    live = _event(season, 'Live Event', datetime(2026, 6, 1), finalized=False)
    _pick(league['users']['carol'], live, league['players']['backup'], league['players']['scott'])
    assert 'Backup Guy' not in _burned(season)


def test_burn_list_usage_with_no_pick_returns_nothing(app, season, league):
    """A usage row entered by hand still lists, with $0 beside it."""
    _burn(league['users']['dave'], _player('Ghost', 'Entry'), season)
    ghost = next(row for row in stats.burn_list(season) if row.player.last_name == 'Entry')
    assert (ghost.total_return, ghost.pct_burned) == (0, 25)


def test_burned_and_remaining_always_sum_to_100(app, season, league):
    for i in range(3):
        _member(season, f'extra{i}')
    rows = stats.burn_list(season)
    remaining = remaining_pct_map(season, [row.player.id for row in rows])
    assert all(row.pct_burned + remaining[row.player.id] == 100 for row in rows)


# --- override_tally ---------------------------------------------------------

def test_override_tally_groups_sorts_and_scopes(app, season, league):
    """Most overrides first, then name; only the weeks handed in, only this
    season, only the room; a member with none is absent."""
    users, players = league['users'], league['players']
    t1, t2 = league['events']
    open_week = _event(season, 'Open Week', datetime(2026, 6, 1), finalized=False)
    last_year = _event(season - 1, 'Last Year', datetime(2025, 6, 1))
    outsider = _user('no_line')
    scott, backup = players['scott'], players['backup']

    for pick in GolfPick.query.filter(GolfPick.user_id.in_([users['alice'].id, users['carol'].id])):
        pick.admin_override = True                       # alice t1, carol t1
    db.session.commit()
    _pick(users['carol'], t2, scott, backup, admin_override=True)
    _pick(users['bob'], open_week, scott, backup, admin_override=True)       # not handed in
    _pick(users['dave'], last_year, scott, backup, admin_override=True)      # another season
    _pick(outsider, t1, scott, backup, admin_override=True)                  # not the room

    tally = stats.override_tally(season, [t1.id, t2.id, last_year.id], _names(season))
    assert tally == [
        stats.OverrideCount(users['carol'].id, 'carol', 2),
        stats.OverrideCount(users['alice'].id, 'alice', 1),
    ]
    assert stats.override_tally(season, [], _names(season)) == []


# --- the race's geometry (pure arithmetic) ----------------------------------

@pytest.mark.parametrize('value,expected', [
    (0, '$0'), (950, '$950'), (25_000, '$25K'), (1_200_000, '$1.2M'), (9_800_000, '$9.8M'),
])
def test_format_money_compact(value, expected):
    assert stats.format_money_compact(value) == expected


@pytest.mark.parametrize('value,axis_max', [
    (2_195_000, 2_500_000),   # a raw step of 548,750 snaps to a $500K grid
    (9_800_000, 10_000_000),
    (500_000, 500_000),       # already round: the top tick is the data
    (0, 1),                   # no money yet: a sane 0..1 axis
])
def test_nice_axis_max(value, axis_max):
    assert stats._nice_axis(value)[0] == axis_max


def test_nice_axis_step_divides_the_axis_evenly():
    axis_max, step = stats._nice_axis(2_195_000)
    assert step == 500_000
    assert axis_max % step == 0


def _fake_race(finals, shorts, names=None):
    """A minimal race for the pure geometry tests (no database)."""
    count = len(shorts)
    return {
        'tournaments': [{'short': short, 'name': f'Event {j}', 'the': f'the Event {j}'}
                        for j, short in enumerate(shorts)],
        'series': [{
            'user_id': i + 1, 'name': names[i] if names else f'U{i}',
            'cumulative': [finals[i]] * count, 'final': finals[i],
            'is_leader': i == 0, 'rank': i + 1, 'rank_label': str(i + 1),
        } for i in range(len(finals))],
        'max_value': max(finals), 'count': count,
    }


def _label(geo, role):
    return next(line for line in geo['lines'] if line['role'] == role)


def test_race_y_ticks_are_round_money_and_zero_has_no_label():
    geo = stats.race_chart_geometry(_fake_race([2_195_000], ['Jan']))
    assert [t['value'] for t in geo['y_ticks']] == [
        0, 500_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000]
    assert geo['y_ticks'][0]['label'] == ''
    assert [t['label'] for t in geo['y_ticks'][1:]] == ['$500K', '$1.0M', '$1.5M', '$2.0M', '$2.5M']
    assert geo['lines'][0]['end_y'] > geo['pad_top']      # headroom over the leader
    assert all(geo['pad_top'] <= t['y'] <= geo['baseline_y'] + 0.01 for t in geo['y_ticks'])


def test_race_x_ticks_name_a_month_once():
    geo = stats.race_chart_geometry(_fake_race([3, 2], ['Mar', 'Mar', 'Apr']))
    assert [t['label'] for t in geo['x_ticks']] == ['Mar', 'Apr']


@pytest.mark.parametrize('finals', [[10_000_000, 9_950_000], [10_000_000, 2_000_000]])
def test_race_names_sit_either_side_of_their_lines(finals):
    """Two names: the upper line's above it, the lower line's below, so neither
    lands on the other's line however close the two finish."""
    geo = stats.race_chart_geometry(_fake_race(finals, ['Jan', 'Feb']), viewer_id=2)
    leader, you = _label(geo, 'leader'), _label(geo, 'you')
    assert (leader['label'], leader['label_below']) == ('U0', False)
    assert (you['label'], you['label_below']) == ('You', True)
    for line in (leader, you):
        assert line['label_y'] == pytest.approx(line['end_y'])
    assert geo['lines'][0]['label'] and all(
        line['label'] is None for line in geo['lines'] if line['role'] == 'pack')


def test_race_names_on_the_floor_part_above_it():
    """No room under a line on the floor: both names stay above their lines,
    spread apart and moved together back inside the plot."""
    geo = stats.race_chart_geometry(_fake_race([10, 0], ['Jan', 'Feb']), viewer_id=2)
    leader, you = _label(geo, 'leader'), _label(geo, 'you')
    assert not leader['label_below'] and not you['label_below']

    level = stats.race_chart_geometry(_fake_race([0, 0], ['Jan', 'Feb']), viewer_id=2)
    ys = sorted(line['label_y'] for line in level['lines'] if line['label'])
    assert ys[1] - ys[0] >= stats.LABEL_MIN_SEP - 0.01
    assert ys[1] <= level['baseline_y'] - 4 + 0.01


def test_race_roles_for_a_guest_and_for_the_leader():
    """A guest sees one named line, the leader's; the leader sees their own as
    'you' and no separate leader."""
    guest = stats.race_chart_geometry(_fake_race([10_000_000, 9_950_000], ['Jan', 'Feb']))
    assert [(line['role'], line['label']) for line in guest['lines']] == [
        ('leader', 'U0'), ('pack', None)]
    leader = stats.race_chart_geometry(
        _fake_race([10_000_000, 9_950_000], ['Jan', 'Feb']), viewer_id=1)
    assert [(line['role'], line['label']) for line in leader['lines']] == [
        ('you', 'You'), ('pack', None)]
    for geo in (guest, leader):
        assert not any(line['label_below'] for line in geo['lines'])


def _tied_race(finals):
    race = _fake_race(finals, ['Jan', 'Feb'])
    for entry in race['series']:
        entry['is_leader'] = entry['final'] == finals[0]
    return race


def test_a_shared_lead_is_drawn_in_ink_and_named_by_its_count():
    """Three level at the top: every one of them is a leader's line, and the
    one name says how many share it."""
    guest = stats.race_chart_geometry(_tied_race([500, 500, 500, 100]))
    assert [line['role'] for line in guest['lines']] == ['leader', 'leader', 'leader', 'pack']
    assert [line['label'] for line in guest['lines']] == ['3 tied', None, None, None]

    # One of the three is the viewer: their line is theirs, the other two's
    # name still counts all three.
    mine = stats.race_chart_geometry(_tied_race([500, 500, 500, 100]), viewer_id=2)
    assert [(line['role'], line['label']) for line in mine['lines']] == [
        ('leader', '3 tied'), ('you', 'You'), ('leader', None), ('pack', None)]
    # Level with one other member: that member is named.
    pair = stats.race_chart_geometry(_tied_race([500, 500, 100]), viewer_id=1)
    assert [(line['role'], line['label']) for line in pair['lines']] == [
        ('you', 'You'), ('leader', 'U1'), ('pack', None)]
    # The two names share a point: yours above it, theirs below.
    assert [line['label_below'] for line in pair['lines']] == [False, True, False]


def test_race_with_one_event_sits_at_the_right_edge_and_has_no_replay():
    """One event is one point, set where the names are: at the plot's right end."""
    geo = stats.race_chart_geometry(_fake_race([500_000], ['Jan']))
    assert geo['lines'][0]['end_x'] == geo['width'] - geo['pad_right']
    assert geo['x_ticks'][0]['x'] == geo['width'] - geo['pad_right']
    assert geo['replay'] is None


def test_race_replay_keeps_a_stop_for_every_event():
    """The axis names March once; the replay still stops at both March events."""
    geo = stats.race_chart_geometry(_fake_race([3, 2], ['Mar', 'Mar', 'Apr']))
    assert [e['short'] for e in geo['replay']['events']] == ['Mar', 'Mar', 'Apr']


def test_race_geometry_and_replay_from_a_real_season(app, season, room):
    race = stats.season_race(season, _names(season))
    geo = stats.race_chart_geometry(race, viewer_id=room['users']['bob'].id)

    assert len(geo['lines']) == len(race['series'])
    assert {line['name']: line['role'] for line in geo['lines']} == {
        'Alice': 'leader', 'Bob': 'you', 'Carol': 'pack'}

    replay = geo['replay']
    assert replay['count'] == 4
    assert [e['name'] for e in replay['events']] == [
        'Sony Open', 'Genesis', 'The Masters', 'Wells Fargo']
    assert replay['events'][2]['the'] == 'the Masters'      # the script's readout phrase
    assert replay['events'][0]['x'] == geo['pad_left']
    assert replay['events'][-1]['x'] == geo['width'] - geo['pad_right']

    alice = next(line for line in replay['lines'] if line['name'] == 'Alice')
    assert alice['cumulative'] == [2_000_000, 3_200_000, 9_200_000, 9_800_000]
    # The replay's dots ride the line the browser draws: one rounding for both.
    drawn = next(line for line in geo['lines'] if line['name'] == 'Alice')
    assert [[float(x), float(y)] for x, y in
            (point.split(',') for point in drawn['points'].split())] == alice['coords']
