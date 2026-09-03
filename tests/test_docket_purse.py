"""The Docket purse (Brad's ruling, 2026-09-03; rulings doc Amendments).

Every dollar the room states is derived: the roster times the entry fee,
less a fixed prize to each week's top sheet across TOTAL_WEEKS, split by
percent into the podium with first taking the remainder. Nothing here is
a literal a roster change could make wrong. The weekly winner is the
ledger's three keys applied to one week; a full tie splits the prize.
"""
import pytest

from games.docket.services.grading.snapshots import PlayerWeekTotal, WeekRollup

# ---------------------------------------------------------------------------
# The podium split
# ---------------------------------------------------------------------------

def test_podium_floors_second_and_third_and_first_takes_the_remainder():
    from games.docket.services.purse import podium_dollars

    assert podium_dollars(700, (65, 25, 10)) == (455, 175, 70)
    # A split that cannot land on whole dollars: 710 x 28% = 198.8 and
    # 710 x 10% = 71.0 floor; first absorbs the change so the three sum.
    assert podium_dollars(710, (62, 28, 10)) == (441, 198, 71)
    assert sum(podium_dollars(710, (62, 28, 10))) == 710


def test_podium_of_nothing_is_nothing():
    from games.docket.services.purse import podium_dollars

    assert podium_dollars(0, (65, 25, 10)) == (0, 0, 0)


@pytest.mark.parametrize('split', [(60, 30, 20), (65, 25), (65, 25, 0), (70, 40, -10)])
def test_a_split_that_is_not_three_shares_of_one_hundred_is_refused(split):
    from games.docket.services.purse import podium_dollars

    with pytest.raises(ValueError):
        podium_dollars(700, split)


# ---------------------------------------------------------------------------
# The season purse from the roster
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('members, gross, weekly, pot, podium', [
    (17, 1020, 380, 640, (416, 160, 64)),
    (18, 1080, 380, 700, (455, 175, 70)),
    (19, 1140, 380, 760, (494, 190, 76)),
    (20, 1200, 380, 820, (533, 205, 82)),
])
def test_season_purse_follows_the_roster(app, members, gross, weekly, pot, podium):
    from games.docket.services.purse import season_purse
    from games.docket.services.weeks import TOTAL_WEEKS

    purse = season_purse(members)
    assert purse.members == members
    assert purse.entry_fee == 60
    assert purse.gross == gross
    assert purse.weekly_prize == 20
    assert purse.weeks == TOTAL_WEEKS == 19
    assert purse.weekly_total == weekly
    assert purse.season_pot == pot
    assert tuple(line.dollars for line in purse.podium) == podium
    assert tuple(line.percent for line in purse.podium) == (65, 25, 10)
    assert tuple(line.place for line in purse.podium) == (1, 2, 3)
    assert tuple(line.label for line in purse.podium) == ('First', 'Second', 'Third')
    assert sum(line.dollars for line in purse.podium) == pot


def test_season_purse_reads_config_not_literals(app, monkeypatch):
    from games.docket.services.purse import season_purse

    monkeypatch.setitem(app.config, 'DOCKET_ENTRY_FEE', 50)
    monkeypatch.setitem(app.config, 'DOCKET_WEEKLY_PRIZE', 10)
    monkeypatch.setitem(app.config, 'DOCKET_PODIUM_SPLIT', (50, 30, 20))
    purse = season_purse(10)
    assert (purse.gross, purse.weekly_total, purse.season_pot) == (500, 190, 310)
    assert tuple(line.dollars for line in purse.podium) == (155, 93, 62)


def test_season_purse_with_no_members(app):
    from games.docket.services.purse import season_purse

    purse = season_purse(0)
    assert purse.gross == 0
    assert purse.season_pot == 0
    assert tuple(line.dollars for line in purse.podium) == (0, 0, 0)


def test_season_pot_never_goes_negative(app):
    """Three members cannot fund nineteen weekly prizes; the rules page
    must state a zero pot rather than a negative one (or a 500)."""
    from games.docket.services.purse import season_purse

    purse = season_purse(3)
    assert purse.gross == 180
    assert purse.weekly_total == 380
    assert purse.season_pot == 0
    assert tuple(line.dollars for line in purse.podium) == (0, 0, 0)


def test_a_bad_split_in_config_is_refused_loudly(app, monkeypatch):
    from games.docket.services.purse import season_purse

    monkeypatch.setitem(app.config, 'DOCKET_PODIUM_SPLIT', (60, 30, 20))
    with pytest.raises(ValueError):
        season_purse(18)


# ---------------------------------------------------------------------------
# The weekly verdict: points, then wins, then that week's error, then split
# ---------------------------------------------------------------------------

def _rollup(*players, week=1):
    return WeekRollup(
        week_number=week, default_error_tenths=180,
        players=tuple(PlayerWeekTotal(*p) for p in players))


def test_week_winner_is_the_top_points():
    from games.docket.services.grading.season import week_winners

    rollup = _rollup(('1', 6.0, 6, 40), ('2', 7.5, 7, 90), ('3', 3.0, 3, 5))
    assert week_winners(rollup) == ('2',)


def test_week_tie_on_points_breaks_on_wins():
    from games.docket.services.grading.season import week_winners

    # 7.0 from seven plain wins beats 7.0 from a doubled win plus five.
    rollup = _rollup(('1', 7.0, 7, 90), ('2', 7.0, 6, 5))
    assert week_winners(rollup) == ('1',)


def test_week_tie_on_points_and_wins_breaks_on_the_lowest_error():
    from games.docket.services.grading.season import week_winners

    rollup = _rollup(('1', 7.0, 7, 90), ('2', 7.0, 7, 15))
    assert week_winners(rollup) == ('2',)


def test_week_level_on_all_three_keys_splits():
    from games.docket.services.grading.season import week_winners

    rollup = _rollup(('10', 7.0, 7, 15), ('2', 7.0, 7, 15), ('3', 6.5, 7, 0))
    # Both, in deterministic player_id order (the engine's own tie device).
    assert week_winners(rollup) == ('10', '2')


def test_absent_members_are_never_in_the_running():
    """A roster member with no sheet is charged the default error and is
    absent from the rollup entirely, so a single graded sheet wins the
    week even on 0.0 points; an ungraded week has no winner."""
    from games.docket.services.grading.season import week_winners

    assert week_winners(_rollup(('1', 0.0, 0, 180))) == ('1',)
    assert week_winners(_rollup()) == ()
