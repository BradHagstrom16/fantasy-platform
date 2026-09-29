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
