"""The 2026 Survivor calendar against the real 2026 season (ADR-071).

Pool week N is the Nth Thursday-to-Wednesday week from ``week_1_start``
(games/cfb/services/automation.py::_calculate_week_dates). With Week 1 on
Thu Sep 3, only 13 Saturdays fall before the conference title games, so
championship weekend is Week 14 and Army-Navy (Sat Dec 12) has a week to
itself. Brad's ruling (2026-10-02): the pool makes no pick on Army-Navy
week, so setup steps over Week 15 and the CFP keeps 16-19, the same week
numbers the Docket and the Tribune file under.

Dates checked 2026-10-02: title games Fri Dec 4 and Sat Dec 5 (Big 12 and
Mountain West Friday, the rest Saturday); Army-Navy Sat Dec 12 at MetLife;
CFP first round Fri Dec 18 and Sat Dec 19 (fbschedules.com, the CFP's
2026-27 schedule release). The later CFP rounds do not fit the weekly
slots and are the December plan's (docs/open-items.md, section I).
"""
import re
from datetime import date, timedelta
from pathlib import Path

from games.cfb.constants import (
    TEAM_CONFERENCES,
    next_pool_week,
    pool_week_name,
    season_schedule,
)

CONSTANTS = Path(__file__).resolve().parents[1] / 'games' / 'cfb' / 'constants.py'


def _dates(week_number):
    from games.cfb.services.automation import _calculate_week_dates
    return _calculate_week_dates(week_number)


def test_championship_weekend_is_week_14(app):
    start, deadline = _dates(14)
    assert start.date() == date(2026, 12, 3)
    assert (deadline.date(), deadline.hour, deadline.minute) == (date(2026, 12, 5), 11, 0)
    special = season_schedule(2026)['special_weeks'][14]
    assert special == {'name': 'Conference Championship Week', 'is_playoff': False}


def test_army_navy_week_has_no_pick(app):
    schedule = season_schedule(2026)
    assert schedule['no_pick_weeks'] == (15,)
    assert 15 not in schedule['special_weeks']
    start, _ = _dates(15)
    assert start.date() <= date(2026, 12, 12) < start.date() + timedelta(days=7)


def test_cfp_first_round_keeps_week_16(app):
    start, deadline = _dates(16)
    assert start.date() == date(2026, 12, 17)
    assert (deadline.date(), deadline.hour) == (date(2026, 12, 19), 11)
    assert season_schedule(2026)['special_weeks'][16]['name'] == 'CFP First Round'


def test_next_pool_week_steps_over_army_navy_week():
    assert next_pool_week(2026, 13) == 14
    assert next_pool_week(2026, 14) == 16
    assert next_pool_week(2026, 16) == 17


def test_pool_week_name_reads_the_calendar():
    assert pool_week_name(2026, 13) == 'Week 13'
    assert pool_week_name(2026, 14) == 'Conference Championship Week'
    assert pool_week_name(2026, 16) == 'CFP First Round'


def test_championship_week_line_keeps_the_shape_survivor_edge_reads():
    """Brad's private survivor-edge skill reads the pool's championship week
    from main's constants.py with this exact regex (sv_sources.pool_ccg_week).
    Reformatting the line breaks the skill silently; change both together."""
    found = re.search(r"(\d+): \{'name': 'Conference Championship Week'",
                      CONSTANTS.read_text())
    assert found and found.group(1) == '14'


def test_2026_conference_realignment():
    """Moves effective Jul 1 2026 (fbschedules.com, checked 2026-10-02)."""
    for name in ('Boise State', 'Colorado State', 'Fresno State',
                 'San Diego State', 'Utah State', 'Texas State'):
        assert TEAM_CONFERENCES[name] == 'Pac-12', name
    for name in ('Northern Illinois', 'UTEP', 'North Dakota State'):
        assert TEAM_CONFERENCES[name] == 'Mountain West', name
    assert TEAM_CONFERENCES['Louisiana Tech'] == 'Sun Belt'
    assert TEAM_CONFERENCES['Sacramento State'] == 'MAC'


def test_create_week_reference_reads_the_calendar(app, client):
    """The admin's week-number reference renders from the season calendar,
    so it can never again promise a Week 15 championship week."""
    import re as _re

    from extensions import db
    from tests._cfb_fixtures import make_user
    admin = make_user('calendar_admin', is_admin=True)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['_user_id'] = admin.auth_id
        sess['_fresh'] = True

    html = client.get('/cfb/admin/week/new').get_data(as_text=True)

    text = _re.sub(r'\s+', ' ', _re.sub(r'<[^>]+>', ' ', html))
    for line in ('Weeks 1-13: Regular Season',
                 'Week 14: Conference Championship Week',
                 'Week 15: No pool week',
                 'Week 16: CFP First Round',
                 'Week 19: CFP National Championship'):
        assert line in text, line
