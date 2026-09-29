"""Season scoping (open-items §E, ADR-069): a season is a column on the week
and team tables, never an archive-and-reseed. 2025 rows sit beside 2026 rows
and no read of the live season sees them."""
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.cfb.models import CfbTeam, CfbWeek
from tests._cfb_fixtures import make_team, make_week

# --- schema -----------------------------------------------------------------

def test_cfb_week_and_team_carry_a_required_season(app):
    for model in (CfbWeek, CfbTeam):
        column = model.__table__.c.season_year
        assert column.nullable is False


def test_fixtures_default_to_the_current_season(app):
    assert make_week(1).season_year == 2026
    assert make_team('Alabama').season_year == 2026


def test_same_week_number_and_team_name_fit_in_two_seasons(app):
    make_week(1, season_year=2025)
    make_week(1, season_year=2026)
    make_team('Alabama', season_year=2025)
    make_team('Alabama', season_year=2026)
    db.session.commit()
    assert db.session.scalar(sa.select(sa.func.count()).select_from(CfbWeek)) == 2
    assert db.session.scalar(sa.select(sa.func.count()).select_from(CfbTeam)) == 2


def test_same_week_number_twice_in_one_season_is_refused(app):
    make_week(1, season_year=2026)
    with pytest.raises(IntegrityError):
        make_week(1, season_year=2026)
    db.session.rollback()


def test_same_team_name_twice_in_one_season_is_refused(app):
    make_team('Alabama', season_year=2026)
    with pytest.raises(IntegrityError):
        make_team('Alabama', season_year=2026)
    db.session.rollback()


@pytest.mark.postgres
def test_postgres_carries_the_named_season_pair_constraints(app):
    inspector = sa.inspect(db.engine)
    week = {c['name']: c['column_names']
            for c in inspector.get_unique_constraints('cfb_week')}
    team = {c['name']: c['column_names']
            for c in inspector.get_unique_constraints('cfb_team')}
    assert week == {'uq_cfb_week_season_number': ['season_year', 'week_number']}
    assert team == {'uq_cfb_team_season_name': ['season_year', 'name']}


# --- the two-season seed ----------------------------------------------------
#
# A full 2025 season (weeks 1-19 complete, the same team names, a pick and an
# elimination for a member who plays again in 2026) beside 2026 weeks 1-3.
# Every read of the live season must come back as if 2025 were not there.

NOW = '2026-09-10T12:00:00'          # naive = UTC: 2026 Week 2 is open


@pytest.fixture
def two_seasons(app, monkeypatch):
    from datetime import datetime, timedelta

    from games.cfb.models import CfbWeekOutcome
    from tests._cfb_fixtures import make_enrollment, make_game, make_pick, make_user

    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', NOW)

    both = make_user('both')
    fresh = make_user('fresh')
    make_enrollment(both, season=2025, lives=0, eliminated=True)
    make_enrollment(fresh, season=2025, lives=0, eliminated=True)
    make_enrollment(both)
    make_enrollment(fresh)

    old = {name: make_team(name, season_year=2025)
           for name in ('Alabama', 'Georgia', 'Ohio State')}
    old_weeks = [
        make_week(n, season_year=2025, is_complete=True, is_playoff=n >= 16,
                  deadline=datetime(2025, 9, 6, 11, 0) + timedelta(weeks=n - 1))
        for n in range(1, 20)]
    make_game(old_weeks[0], old['Alabama'], old['Georgia'], spread=-20.0,
              winner='home')
    make_pick(both, old_weeks[0], old['Alabama'], is_correct=True)
    make_game(old_weeks[2], old['Georgia'], old['Ohio State'], spread=-3.0,
              winner='away')
    make_pick(both, old_weeks[2], old['Georgia'], is_correct=False)
    for user in (both, fresh):
        db.session.add(CfbWeekOutcome(
            week_id=old_weeks[2].id, user_id=user.id, lives_remaining=0,
            is_eliminated=True, lost_life=True))

    new = {name: make_team(name) for name in ('Alabama', 'Georgia', 'Texas')}
    w1 = make_week(1, is_complete=True, deadline=datetime(2026, 9, 5, 11, 0))
    w2 = make_week(2, is_active=True, deadline=datetime(2026, 9, 12, 11, 0))
    w3 = make_week(3, deadline=datetime(2026, 9, 19, 11, 0))
    make_game(w1, new['Alabama'], new['Texas'], spread=-7.0, winner='home')
    make_pick(both, w1, new['Alabama'], is_correct=True)
    make_pick(fresh, w1, new['Alabama'], is_correct=True)
    make_game(w2, new['Georgia'], new['Texas'], spread=-4.0)
    make_game(w3, new['Texas'], new['Georgia'], spread=1.0)
    for user in (both, fresh):
        db.session.add(CfbWeekOutcome(
            week_id=w1.id, user_id=user.id, lives_remaining=2,
            is_eliminated=False, lost_life=False))
    db.session.commit()
    return {'both': both, 'fresh': fresh, 'old': old, 'new': new,
            'old_weeks': old_weeks, 'weeks': [w1, w2, w3]}


def _enrollment(user, season=2026):
    from games.cfb.models import CfbEnrollment
    return CfbEnrollment.query.filter_by(user_id=user.id, season_year=season).one()


# --- the read helpers -------------------------------------------------------

def test_week_helpers_read_the_configured_season_only(two_seasons):
    from games.cfb.services import weeks

    w1, w2, w3 = two_seasons['weeks']
    assert weeks.current_season() == 2026
    assert weeks.season_weeks() == [w1, w2, w3]
    assert [w.week_number for w in weeks.season_weeks(2025)] == list(range(1, 20))
    assert weeks.week_by_number(1) == w1
    assert weeks.week_by_number(19) is None
    assert weeks.week_by_number(19, 2025).season_year == 2025
    assert weeks.active_week() == w2
    assert weeks.complete_weeks() == [w1]
    assert weeks.incomplete_weeks() == [w2, w3]
    assert weeks.latest_week() == w3
    assert weeks.week_query().count() == 3


def test_team_helpers_read_the_configured_season_only(two_seasons):
    from games.cfb.services import weeks

    new = two_seasons['new']
    assert weeks.season_teams() == [new['Alabama'], new['Georgia'], new['Texas']]
    assert weeks.team_query().count() == 3
    assert {t.season_year for t in weeks.season_teams(2025)} == {2025}


def test_deactivate_all_leaves_no_active_week(two_seasons):
    from games.cfb.services import weeks

    two_seasons['old_weeks'][4].is_active = True
    weeks.deactivate_all()
    db.session.commit()
    assert CfbWeek.query.filter_by(is_active=True).count() == 0


# --- the per-year calendar --------------------------------------------------

def test_the_calendar_is_keyed_by_season(app):
    import games.cfb.constants as constants

    assert not hasattr(constants, 'SEASON_SCHEDULE')
    schedule = constants.season_schedule(2026)
    assert schedule['week_1_start'] == '2026-09-03'
    with pytest.raises(KeyError):
        constants.season_schedule(1999)


def test_the_configured_season_drives_every_calendar_read(app, monkeypatch):
    """A 2027 entry and CFB_SEASON_YEAR=2027 move the week dates, the lounge
    instants and the final week together; nothing reads 2026 by name."""
    from datetime import UTC, datetime

    import games.cfb.constants as constants
    from games.cfb.services import lounge
    from games.cfb.services.automation import _calculate_week_dates

    fake = dict(constants.season_schedule(2026),
                week_1_start='2027-09-02',
                enrollment_deadline_utc=datetime(2027, 9, 4, 16, 0, tzinfo=UTC),
                season_live_utc=datetime(2027, 8, 31, 11, 0, tzinfo=UTC))
    monkeypatch.setitem(constants.SEASON_SCHEDULES, 2027, fake)
    monkeypatch.setitem(app.config, 'CFB_SEASON_YEAR', 2027)

    start, deadline = _calculate_week_dates(1)
    assert start.date().isoformat() == '2027-09-02'
    assert deadline.replace(tzinfo=None) == datetime(2027, 9, 4, 11, 0)
    assert lounge.enrollment_deadline_utc() == fake['enrollment_deadline_utc']
    assert lounge.season_live_utc() == fake['season_live_utc']


# --- every read ignores the other season -----------------------------------

def test_used_teams_and_cumulative_spread_are_this_seasons(two_seasons):
    from games.cfb.services.game_logic import (
        calculate_cumulative_spread,
        get_used_team_ids,
    )

    both = two_seasons['both']
    w1, w2, _ = two_seasons['weeks']
    assert get_used_team_ids(both.id, w2) == {two_seasons['new']['Alabama'].id}
    enrollment = _enrollment(both)
    calculate_cumulative_spread(enrollment)
    assert enrollment.cumulative_spread == -7.0


def test_a_last_season_elimination_is_not_this_seasons(two_seasons):
    from games.cfb.services.game_logic import _eliminated_in_another_week

    w1 = two_seasons['weeks'][0]
    assert _eliminated_in_another_week(two_seasons['both'].id, w1.id) is False


def test_the_lounge_stays_live_when_last_seasons_final_week_is_complete(two_seasons):
    from games.cfb.services.lounge import cfb_lounge_state

    assert cfb_lounge_state() == 'live'


def test_the_lounge_stays_pre_when_only_last_season_has_weeks(app, monkeypatch):
    from datetime import datetime

    from games.cfb.services.lounge import cfb_lounge_state
    from tests._cfb_fixtures import make_enrollment, make_user

    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', NOW)
    for name in ('a', 'b'):
        make_enrollment(make_user(name))
    make_week(1, season_year=2025, is_complete=True,
              deadline=datetime(2025, 9, 6, 11, 0))
    make_week(2, season_year=2025, is_active=True,
              deadline=datetime(2025, 9, 13, 11, 0))
    db.session.commit()
    assert cfb_lounge_state() == 'pre'


def test_setup_numbers_the_next_week_within_the_season(two_seasons, monkeypatch):
    from games.cfb.services import automation

    monkeypatch.setattr(automation, '_import_games_for_week', lambda *a: 0)
    monkeypatch.setattr(automation, '_send_admin_email', lambda *a: True)
    result = automation.run_setup()
    assert result['week_number'] == 4
    created = CfbWeek.query.filter_by(season_year=2026, week_number=4).one()
    assert created.is_active is False


def test_setup_never_retries_last_seasons_orphan(app, monkeypatch):
    from datetime import datetime

    from games.cfb.services import automation

    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', NOW)
    make_week(7, season_year=2025, deadline=datetime(2025, 10, 18, 11, 0))
    db.session.commit()
    monkeypatch.setattr(automation, '_import_games_for_week', lambda *a: 0)
    monkeypatch.setattr(automation, '_send_admin_email', lambda *a: True)
    result = automation.run_setup()
    assert result['week_number'] == 1
    assert CfbWeek.query.filter_by(season_year=2026, week_number=1).one()


def test_the_import_maps_names_to_this_seasons_teams(two_seasons, monkeypatch):
    from types import SimpleNamespace

    from games.cfb.constants import SHORT_TO_API
    from games.cfb.models import CfbGame
    from games.cfb.services import automation

    monkeypatch.setitem(automation.current_app.config, 'ODDS_API_KEY', 'k')
    # Ohio State is in 2025's pool only: the 2026 import must not track it.
    event = {'id': 'evt-1', 'home_team': SHORT_TO_API['Ohio State'],
             'away_team': SHORT_TO_API['Georgia'],
             'commence_time': '2026-09-19T16:00:00Z'}
    monkeypatch.setattr(automation, 'odds_api_get', lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: [event]))
    w3 = two_seasons['weeks'][2]
    from games.cfb.services.automation import _calculate_week_dates
    start, end = _calculate_week_dates(3)
    assert automation._import_games_for_week(w3, start, end) == 1
    game = CfbGame.query.filter_by(api_event_id='evt-1').one()
    assert (game.home_team_id, game.home_team_name) == (None, 'Ohio State')
    assert game.away_team_id == two_seasons['new']['Georgia'].id


def test_autopick_never_touches_last_seasons_open_week(app, monkeypatch):
    from datetime import datetime

    from games.cfb.models import CfbPick
    from games.cfb.services import game_logic
    from tests._cfb_fixtures import make_enrollment, make_game, make_user

    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', NOW)
    user = make_user('stale')
    make_enrollment(user, season=2025)
    make_enrollment(user)             # plays 2026 too, with no 2026 week yet
    week = make_week(5, season_year=2025, deadline=datetime(2025, 10, 4, 11, 0))
    make_game(week, make_team('Alabama', season_year=2025),
              make_team('Georgia', season_year=2025), spread=-6.0)
    db.session.commit()
    alerts = []
    monkeypatch.setattr(game_logic, '_alert_autopick_failures', alerts.append)
    assert game_logic.check_and_process_autopicks() == []
    assert alerts == []
    assert CfbPick.query.count() == 0


def test_gameday_never_wants_last_seasons_unsettled_game(app, monkeypatch):
    from datetime import datetime

    from games.cfb.constants import SPORT_KEY
    from games.cfb.services import gameday
    from tests._cfb_fixtures import make_game

    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', '2025-10-05T00:00:00')  # 8 h after kickoff
    week = make_week(5, season_year=2025, deadline=datetime(2025, 10, 4, 11, 0))
    game = make_game(week, make_team('Alabama', season_year=2025),
                     make_team('Georgia', season_year=2025), spread=-6.0)
    game.game_time = datetime(2025, 10, 4, 11, 0)
    db.session.commit()
    assert gameday.wants(SPORT_KEY) is False


def test_the_pool_and_the_field_are_this_seasons(two_seasons):
    from games.cfb.services.field import build_field
    from games.cfb.services.game_logic import pool_teams_by_conference

    _groups, total, _confs = pool_teams_by_conference()
    assert total == 3
    field = build_field(2026)
    assert [row.week_number for row in field.weeks] == [1]
    names = [line.team.name for board in field.board for line in board.lines]
    assert sorted(names) == ['Alabama', 'Georgia', 'Texas']
    lines = {line.team.id: line for board in field.board for line in board.lines}
    assert all(t.season_year == 2026 for t in (line.team for line in lines.values()))
    assert [(r.team.id, r.count) for r in field.backed] == [
        (two_seasons['new']['Alabama'].id, 2)]
    assert field.revealed_weeks == 1


def test_the_player_card_is_this_seasons(two_seasons):
    from games.cfb.services.card import build_player_card

    both = two_seasons['both']
    card = build_player_card(both.id, _enrollment(both))
    assert [p.week.season_year for p in card['user_picks']] == [2026]
    assert card['total_picks'] == 1
    assert {t.season_year for t in card['available_teams']} == {2026}
    assert card['current_week'] == two_seasons['weeks'][1]


def test_the_survivor_board_reads_this_seasons_week(two_seasons):
    from games.cfb.services.announce_blocks import _finished_week

    assert _finished_week({'week': '1'}, allowed=('week',)) == two_seasons['weeks'][0]
    with pytest.raises(ValueError, match='has no Week 19'):
        _finished_week({'week': '19'}, allowed=('week',))


def test_the_desk_reads_this_seasons_weeks(two_seasons):
    from games.cfb.services import desk

    w1, w2, _ = two_seasons['weeks']
    assert desk._candidate(None) == w2
    assert desk._record_week(w2) == w1


def test_an_eliminated_members_out_week_is_this_seasons(two_seasons):
    from games.cfb.models import CfbWeekOutcome
    from games.cfb.services import desk
    from games.cfb.services.records import _live_season

    fresh = two_seasons['fresh']
    w1, w2, _ = two_seasons['weeks']
    enrollment = _enrollment(fresh)
    enrollment.is_eliminated = True
    enrollment.lives_remaining = 0
    outcome = CfbWeekOutcome.query.filter_by(week_id=w1.id, user_id=fresh.id).one()
    outcome.is_eliminated = outcome.lost_life = True
    db.session.commit()
    finish = {d.user_id: d for d in _live_season(2026)}[fresh.id]
    assert finish.detail.startswith('Out Week 1 ')
    lines = desk._sections(w2, w1, None)[fresh.id].section.lines
    assert lines[0].startswith('Out after Week 1.')


def test_populate_teams_fills_an_empty_season_beside_last_seasons_pool(app):
    from games.cfb.cli import populate_teams_cmd
    from games.cfb.constants import DEV_SEED_TEAMS

    make_team('Alabama', season_year=2025)
    db.session.commit()
    result = app.test_cli_runner().invoke(populate_teams_cmd)
    assert result.exit_code == 0, result.output
    assert CfbTeam.query.filter_by(season_year=2026).count() == len(DEV_SEED_TEAMS)
    again = app.test_cli_runner().invoke(populate_teams_cmd)
    assert 'already has' in again.output


# --- the source lock ---------------------------------------------------------

CFB_UNSCOPED = re.compile(
    r'\b(CfbWeek\.query|select\(CfbWeek\)|filter_by\(week_number=|'
    r'CfbTeam\.query|select\(CfbTeam\))')
CFB_READS = Path(__file__).resolve().parent.parent / 'games' / 'cfb'


def test_cfb_reads_weeks_and_teams_only_through_the_season_helpers():
    """A whole-table week or team read spans every season; only
    games/cfb/services/weeks.py may build one, and it scopes by season."""
    offenders = []
    for path in sorted(CFB_READS.rglob('*.py')):
        if path == CFB_READS / 'services' / 'weeks.py':
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if CFB_UNSCOPED.search(line):
                offenders.append(f'{path.relative_to(CFB_READS)}:{number}: {line.strip()}')
    assert offenders == []


def test_elimination_weeks_are_this_seasons(two_seasons):
    from games.cfb.services.game_logic import get_elimination_weeks

    both = two_seasons['both']
    assert get_elimination_weeks([both.id], 5) == {}
    assert get_elimination_weeks([both.id], 5, 2025) == {
        both.id: two_seasons['old_weeks'][2]}


def test_cfp_eliminations_are_this_seasons(two_seasons):
    from games.cfb.utils import get_cfp_eliminated_teams
    from tests._cfb_fixtures import make_game

    old = two_seasons['old']
    make_game(two_seasons['old_weeks'][16], old['Alabama'], old['Georgia'],
              spread=-3.0, winner='home')
    db.session.commit()
    assert get_cfp_eliminated_teams() == set()


# === The Docket =============================================================

def _docket_week(number, season_year=2026):
    from datetime import datetime

    from games.docket.models import DocketWeek
    week = DocketWeek(season_year=season_year, week_number=number,
                      start_at=datetime(season_year, 9, 1, 11, 0),
                      end_at=datetime(season_year, 9, 8, 11, 0),
                      deadline_at=datetime(season_year, 9, 6, 17, 0))
    db.session.add(week)
    db.session.flush()
    return week


def test_docket_week_carries_a_required_season(app):
    from games.docket.models import DocketWeek

    assert DocketWeek.__table__.c.season_year.nullable is False


def test_docket_fixture_defaults_to_the_current_season(app):
    from tests._docket_fixtures import make_week as make_docket_week

    assert make_docket_week(1).season_year == 2026


def test_same_docket_week_number_fits_in_two_seasons_not_one(app):
    _docket_week(1, 2025)
    _docket_week(1, 2026)
    db.session.commit()
    with pytest.raises(IntegrityError):
        _docket_week(1, 2026)
    db.session.rollback()


@pytest.mark.postgres
def test_postgres_carries_the_named_docket_season_pair(app):
    inspector = sa.inspect(db.engine)
    uniques = {c['name']: c['column_names']
               for c in inspector.get_unique_constraints('docket_week')}
    assert uniques == {'uq_docket_week_season_number': ['season_year', 'week_number']}


# --- the Docket's per-year calendar -----------------------------------------

def _calendar_2025():
    from datetime import UTC, datetime

    from games.docket.services.weeks import SeasonCalendar
    return SeasonCalendar(week_1_boundary_local=datetime(2025, 9, 2, 6, 0),
                          total_weeks=19, first_nfl_week=2,
                          enrollment_deadline_utc=datetime(2025, 9, 6, 16, 0, tzinfo=UTC))


def test_the_docket_calendar_is_keyed_by_season():
    from games.docket.services import weeks

    calendar = weeks.SEASON_CALENDARS[weeks.SEASON_YEAR]
    assert calendar.week_1_boundary_local == weeks.WEEK_1_BOUNDARY_LOCAL
    assert calendar.total_weeks == weeks.TOTAL_WEEKS
    assert calendar.first_nfl_week == weeks.FIRST_NFL_WEEK
    with pytest.raises(KeyError):
        weeks.boundary_utc(1, season_year=1999)


def test_the_docket_week_math_follows_the_season(monkeypatch):
    from datetime import UTC, datetime

    from games.docket.services import weeks

    monkeypatch.setitem(weeks.SEASON_CALENDARS, 2025, _calendar_2025())
    assert weeks.boundary_utc(1, season_year=2025) == datetime(2025, 9, 2, 11, 0, tzinfo=UTC)
    assert weeks.deadline_utc(1, season_year=2025) == datetime(2025, 9, 7, 17, 0, tzinfo=UTC)
    assert weeks.week_number_for(datetime(2025, 9, 3, tzinfo=UTC), season_year=2025) == 1
    assert weeks.week_number_for(datetime(2025, 9, 3, tzinfo=UTC)) is None


def test_the_docket_enrollment_deadline_comes_from_its_calendar():
    from games.docket.services import lounge, weeks

    assert (weeks.SEASON_CALENDARS[weeks.SEASON_YEAR].enrollment_deadline_utc
            == lounge.ENROLLMENT_DEADLINE_UTC)


def test_both_calendars_share_the_club_instants_every_season(app):
    """ADR-050 and the 2026-08-19 preseason gate, per season: every season
    both calendars carry shares one enrollment cutoff and one live instant."""
    from games.cfb.constants import SEASON_SCHEDULES
    from games.docket.services import weeks

    shared = SEASON_SCHEDULES.keys() & weeks.SEASON_CALENDARS.keys()
    assert shared
    for year in shared:
        cfb, docket = SEASON_SCHEDULES[year], weeks.SEASON_CALENDARS[year]
        assert cfb['enrollment_deadline_utc'] == docket.enrollment_deadline_utc
        assert cfb['season_live_utc'] == weeks.boundary_utc(1, season_year=year)


# --- the Docket's two-season seed -------------------------------------------

@pytest.fixture
def docket_two_seasons(app, monkeypatch):
    from datetime import datetime

    from games.docket.models import DocketEnrollment, DocketWeekResult
    from games.docket.services import weeks
    from tests._docket_fixtures import (
        make_enrollment,
        make_game,
        make_user,
    )
    from tests._docket_fixtures import make_week as make_docket_week

    monkeypatch.setitem(weeks.SEASON_CALENDARS, 2025, _calendar_2025())
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-09-10T12:00:00')   # 2026 Week 2

    both, fresh = make_user('both'), make_user('fresh')
    for user in (both, fresh):
        db.session.add(DocketEnrollment(user_id=user.id, season_year=2025,
                                        created_at=datetime(2025, 8, 20, 12, 0)))
        make_enrollment(user)

    def graded(week, points):
        week.default_error_tenths = 0
        for user, pts in zip((both, fresh), points, strict=True):
            db.session.add(DocketWeekResult(
                user_id=user.id, week_id=week.id, points=pts, wins=int(pts),
                error_tenths=0, graded_at=week.end_at))
        return week

    old_weeks = [graded(make_docket_week(n, season_year=2025), (8.0, 1.0))
                 for n in range(1, 20)]
    for week in old_weeks:
        week.record_notified = False
    w1 = graded(make_docket_week(1), (2.0, 6.0))
    w2 = make_docket_week(2)
    make_game(w2, kickoff=datetime(2026, 9, 12, 16, 0), home='Georgia Bulldogs',
              away='Texas Longhorns')
    db.session.commit()
    return {'both': both, 'fresh': fresh, 'old_weeks': old_weeks,
            'weeks': [w1, w2]}


def test_docket_week_reads_are_this_seasons(docket_two_seasons):
    from games.docket.services import week_reads

    w1, w2 = docket_two_seasons['weeks']
    assert week_reads.week_by_number(1) == w1
    assert week_reads.week_by_number(19) is None
    assert week_reads.week_by_number(19, season_year=2025).season_year == 2025
    assert week_reads.season_weeks() == [w1, w2]
    assert len(week_reads.season_weeks(2025)) == 19


def test_the_ledger_reads_this_seasons_graded_weeks(docket_two_seasons):
    from games.docket.services.season_pass import season_ledger, week_rollups_from_db

    assert [r.week_number for r in week_rollups_from_db()] == [1]
    ledger = season_ledger()
    assert ledger.week_numbers == (1,)
    assert ledger.season_complete is False
    assert ledger.rows[0].enrollment.user_id == docket_two_seasons['fresh'].id
    past = season_ledger(2025)
    assert past.season_complete is True
    assert past.rows[0].enrollment.user_id == docket_two_seasons['both'].id


def test_week_standings_read_this_seasons_week(docket_two_seasons):
    from games.docket.services.season_pass import week_standings

    standing = week_standings(1)
    assert standing is not None
    assert standing.rows[0].enrollment.user_id == docket_two_seasons['fresh'].id


def test_the_docket_records_builder_closes_any_graded_season(docket_two_seasons):
    from games.docket.services.records import season_finishes
    from models.records import SeasonNotClosed

    drafts = season_finishes(2025)
    assert [(d.user_id, d.place) for d in drafts] == [
        (docket_two_seasons['both'].id, 1), (docket_two_seasons['fresh'].id, 2)]
    with pytest.raises(SeasonNotClosed):
        season_finishes(2026)


def test_the_docket_desk_and_record_pass_read_this_season(docket_two_seasons):
    from games.docket.services import desk, record

    w1, w2 = docket_two_seasons['weeks']
    assert desk._record_week(w2) == w1
    assert [w.season_year for w in record.pending_weeks()] == [2026]


def test_the_docket_board_reads_this_seasons_week(docket_two_seasons):
    from games.docket.services.announce_blocks import _graded_week

    assert _graded_week({'week': '1'}, allowed=('week',)) == docket_two_seasons['weeks'][0]
    with pytest.raises(ValueError, match='has no Week 19'):
        _graded_week({'week': '19'}, allowed=('week',))


def test_the_importer_makes_this_seasons_week_beside_last_seasons(docket_two_seasons):
    from games.docket.services.importer import ensure_week

    week = ensure_week(3)
    assert (week.season_year, week.week_number) == (2026, 3)
    assert ensure_week(2) == docket_two_seasons['weeks'][1]


def test_the_all_sheets_nav_lists_this_seasons_weeks(docket_two_seasons):
    from games.docket.models import DocketGame
    from games.docket.routes import _posted_week_numbers

    old = docket_two_seasons['old_weeks'][6]
    db.session.add(DocketGame(week_id=old.id, sport='americanfootball_nfl',
                              api_event_id='old-7', home_team='A', away_team='B',
                              kickoff=old.start_at))
    db.session.commit()
    assert list(_posted_week_numbers()) == [2]


def test_the_docket_cli_reads_this_seasons_week(docket_two_seasons):
    from games.docket.cli import _get_week

    assert _get_week(1) == docket_two_seasons['weeks'][0]


# --- the Docket's source lock ------------------------------------------------

DOCKET_UNSCOPED = re.compile(
    r'\b(DocketWeek\.query|select\(DocketWeek\)|filter_by\(week_number=)')
DOCKET_READS = Path(__file__).resolve().parent.parent / 'games' / 'docket'


def test_docket_reads_weeks_only_through_the_season_helpers():
    offenders = []
    for path in sorted(DOCKET_READS.rglob('*.py')):
        if path == DOCKET_READS / 'services' / 'week_reads.py':
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if DOCKET_UNSCOPED.search(line):
                offenders.append(f'{path.relative_to(DOCKET_READS)}:{number}: {line.strip()}')
    assert offenders == []


def test_the_unenroll_script_leaves_last_seasons_record(app, docket_two_seasons, monkeypatch):
    """scripts/docket_unenroll_user.py removes this season's seat and picks
    only; a past season's picks and results are that season's record."""
    import importlib.util
    import sys

    from games.docket.models import DocketEnrollment, DocketPick, DocketWeekResult
    from tests._docket_fixtures import make_user

    spec = importlib.util.spec_from_file_location(
        'docket_unenroll_user', Path(__file__).resolve().parent.parent / 'scripts'
        / 'docket_unenroll_user.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    late = make_user('late')
    db.session.add(DocketEnrollment(user_id=late.id, season_year=2025))
    db.session.add(DocketEnrollment(user_id=late.id, season_year=2026))
    old_week, (_w1, w2) = docket_two_seasons['old_weeks'][0], docket_two_seasons['weeks']
    old_game = w2.games[0]
    db.session.add(DocketWeekResult(user_id=late.id, week_id=old_week.id, points=1.0,
                                    wins=1, error_tenths=0, graded_at=old_week.end_at))
    for week in (old_week, w2):
        db.session.add(DocketPick(user_id=late.id, week_id=week.id, game_id=old_game.id,
                                  market='spread', side='home', slot=1,
                                  line_value=-3.5, book='draftkings'))
    db.session.commit()

    monkeypatch.setattr(script, 'create_app', lambda: app)
    monkeypatch.setattr(sys, 'argv', ['docket_unenroll_user.py', 'late', '--confirm'])
    assert script.main() == 0
    assert DocketEnrollment.query.filter_by(user_id=late.id).one().season_year == 2025
    assert [p.week_id for p in DocketPick.query.filter_by(user_id=late.id)] == [old_week.id]
