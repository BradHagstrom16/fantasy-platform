"""Docket sheet search locks: "find a case" (design review 2026-09-02).

The find field is the fourth calendar aid (games/docket/DESIGN.md §7.7): a
plain GET ``?q=`` on the no-JS spine that renders every matching case in
the week, grouped by day, pickable in place. These lock the matcher, the
results view and its no-silent-caps lines, the zero-match state, the
return fields that carry the view through the PRG redirect, and the
markup, CSS, and script contracts the enhancement layer rides on.
"""
import re
from datetime import datetime
from pathlib import Path

import pytest

from extensions import db
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

ROOT = Path(__file__).resolve().parents[1]
SHEET_SRC = (ROOT / 'games/docket/templates/docket/sheet.html').read_text()
CSS = (ROOT / 'static/css/style.css').read_text()

# Naive UTC kickoffs (the D6 column contract) spanning three CT days.
KICK_THU = datetime(2026, 9, 4, 0, 15)      # Thu 7:15 PM CT
KICK_SAT_AM = datetime(2026, 9, 5, 16, 0)   # Sat 11:00 AM CT
KICK_SAT_PM = datetime(2026, 9, 5, 23, 30)  # Sat 6:30 PM CT
KICK_SUN = datetime(2026, 9, 6, 17, 0)      # Sun 12:00 PM CT


@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _open_week(monkeypatch, now=IN_WEEK1):
    """Week 1 with four cases over three days: a Thursday MAC-at-Big-Ten
    case, two Saturday cases (Big Ten; Big Ten at an Independent), and a
    Sunday NFL case. Returns the Saturday Wisconsin case."""
    week = make_week(1)
    make_game(week, kickoff=KICK_THU,
              away='Ohio Bobcats', home='Nebraska Cornhuskers')
    make_game(week, kickoff=KICK_SAT_AM,
              away='Ohio State Buckeyes', home='Michigan Wolverines')
    wis = make_game(week, kickoff=KICK_SAT_PM,
                    away='Wisconsin Badgers', home='Notre Dame Fighting Irish')
    make_game(week, kickoff=KICK_SUN, sport='americanfootball_nfl',
              away='Chicago Bears', home='Green Bay Packers')
    db.session.commit()
    at(monkeypatch, now)
    return wis


# ── the matcher ────────────────────────────────────────────────────────────

def test_find_matches_a_team_anywhere_in_the_week(
        monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?q=wis').data.decode()
    assert 'Wisconsin Badgers' in html
    assert 'Ohio State Buckeyes' not in html
    assert 'Chicago Bears' not in html
    assert 'Matching cases' in html
    # The no-silent-caps line: the reduction and the way back.
    assert 'Showing 1 of 4 cases matching' in html
    assert 'All cases' in html


def test_find_ignores_case_and_needs_every_word(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?q=OHIO+state').data.decode()
    assert 'Ohio State Buckeyes' in html
    assert 'Ohio Bobcats' not in html          # "state" is not on that case
    html = client.get('/docket/?q=ohio+bears').data.decode()
    assert 'docket-case-row' not in html       # no case carries both words


def test_find_spans_days_and_groups_the_matches_by_day(
        monkeypatch, client, member):
    _open_week(monkeypatch)
    # Week-wide regardless of the day scope in the URL.
    html = client.get('/docket/?day=2026-09-06&q=big+ten').data.decode()
    assert 'Nebraska Cornhuskers' in html      # Thursday
    assert 'Ohio State Buckeyes' in html       # Saturday
    assert 'Wisconsin Badgers' in html         # Saturday
    assert 'Chicago Bears' not in html
    assert 'Showing 3 of 4 cases matching' in html
    # Grouped under day heads, in calendar order.
    assert html.index('Thursday, September 3') < html.index(
        'Saturday, September 5')
    # The day tabs stay for navigation, none is the current page, and the
    # day-scoped aids step aside.
    assert html.count('docket-day-tab-label') == 3
    assert 'aria-current="page"' not in html
    assert 'docket-conf-chips' not in html
    assert 'docket-session-jumps' not in html


def test_find_by_league_word_reaches_the_pro_slate(
        monkeypatch, client, member):
    """The member's ask: with the pros in the docket, one word lists them."""
    _open_week(monkeypatch)
    for q in ('nfl', 'pros'):
        html = client.get(f'/docket/?q={q}').data.decode()
        assert 'Chicago Bears' in html, q
        assert 'Wisconsin Badgers' not in html, q
    html = client.get('/docket/?q=college').data.decode()
    assert 'Wisconsin Badgers' in html
    assert 'Chicago Bears' not in html


def test_find_query_is_normalized_and_capped(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?q=++wis+++badgers++').data.decode()
    assert 'Wisconsin Badgers' in html
    assert 'value="wis badgers"' in html
    html = client.get('/docket/?q=' + 'w' * 70).data.decode()
    assert 'value="' + 'w' * 60 + '"' in html
    assert 'w' * 61 not in html


def test_blank_query_renders_the_day_view(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?day=2026-09-05&q=+++').data.decode()
    assert 'aria-current="page"' in html
    assert 'docket-conf-chips' in html
    assert 'Showing' not in html
    assert 'Matching cases' not in html


def test_find_echoes_the_query_escaped(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?q=%3Cscript%3Ealert(1)').data.decode()
    assert '<script>alert' not in html
    assert '&lt;script&gt;alert(1)' in html


def test_zero_matches_are_stated_plainly(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?q=zzz').data.decode()
    assert 'docket-case-row' not in html
    assert 'No matching case' in html
    assert 'No case this week matches' in html
    assert 'Try a team name, a conference, or NFL.' in html
    assert 'All cases' in html
    assert 'value="zzz"' in html               # kept for correction
    assert 'Showing' not in html


# ── the control ────────────────────────────────────────────────────────────

def test_find_form_markup_contract(monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?day=2026-09-05').data.decode()
    match = re.search(r'<form[^>]*class="docket-find"[^>]*>.*?</form>',
                      html, re.S)
    assert match, 'the find form is missing'
    form = match.group(0)
    assert 'role="search"' in form
    assert 'method="get"' in form
    assert 'data-docket-action' not in form
    assert '<label' in form and 'for="docket-find-q"' in form
    assert 'Find a case' in form
    assert 'type="search"' in form
    assert 'id="docket-find-q"' in form
    assert 'name="q"' in form
    assert 'maxlength="60"' in form
    assert 'form-control' in form
    assert 'docket-find-btn' in form
    # It carries the day to return to, so "All cases" lands where you were.
    assert 'name="day" value="2026-09-05"' in form
    # First in the calendar block: the broadest aid leads.
    assert html.index('class="docket-find"') < html.index('docket-day-tabs')


def test_all_cases_returns_to_the_day_searched_from(
        monkeypatch, client, member):
    _open_week(monkeypatch)
    html = client.get('/docket/?day=2026-09-03&q=wis').data.decode()
    back = re.search(r'<a href="([^"]+)">All cases', html)
    assert back and back.group(1) == '/docket/?day=2026-09-03'


# ── return fields: the view survives a no-JS pick ──────────────────────────

def test_results_carry_the_query_through_a_pick(monkeypatch, client, member):
    wis = _open_week(monkeypatch)
    html = client.get('/docket/?day=2026-09-05&q=wis').data.decode()
    assert re.search(r'<input type="hidden" name="q" value="wis"', html)
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': wis.id, 'market': 'spread', 'side': 'home',
              'day': '2026-09-05', 'q': 'wis', 'csrf_token': 'x'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers['Location']
    assert 'q=wis' in location and 'day=2026-09-05' in location
    after = client.get(location).data.decode()
    assert 'Filed · Slot 1' in after
    assert 'Showing 1 of 4 cases matching' in after


def test_conference_filter_survives_a_no_js_pick(monkeypatch, client, member):
    """Pre-existing gap closed by the same return fields: a pick made from a
    conference-filtered day used to land back on the unfiltered day."""
    wis = _open_week(monkeypatch)
    html = client.get('/docket/?day=2026-09-05&conf=big-ten').data.decode()
    assert re.search(r'<input type="hidden" name="conf" value="big-ten"', html)
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': wis.id, 'market': 'spread', 'side': 'home',
              'day': '2026-09-05', 'conf': 'big-ten', 'csrf_token': 'x'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert 'conf=big-ten' in resp.headers['Location']


# ── every week state ───────────────────────────────────────────────────────

def test_find_works_on_the_preseason_preview(monkeypatch, client, member):
    _open_week(monkeypatch, now='2026-08-20T12:00:00')
    html = client.get('/docket/?q=wis').data.decode()
    assert 'Wisconsin Badgers' in html
    assert 'Ohio State Buckeyes' not in html
    assert 'is-locked' not in html
    assert 'data-docket-action="' not in html


def test_find_works_on_the_closed_docket(monkeypatch, client, member):
    _open_week(monkeypatch, now='2026-09-05T17:00:00')  # past Sat 11:00 CT
    html = client.get('/docket/?q=wis').data.decode()
    assert 'Wisconsin Badgers' in html
    assert 'Ohio State Buckeyes' not in html
    assert 'data-docket-action="' not in html


# ── the enhancement layer and the CSS floor ────────────────────────────────

def test_find_submit_rides_the_repaint_layer():
    script = SHEET_SRC.split('<script>', 1)[1]
    assert 'form.docket-find' in script
    assert 'replaceState' in script
    assert 'refreshRegions()' in script
    assert 'docket-find-q' in script
    # The closed-state lock matches the literal attribute form; the script
    # must never spell it that way.
    assert 'data-docket-action="' not in script


def _rule(anchored_selector):
    m = re.search(anchored_selector + r'\s*\{([^}]*)\}', CSS, re.M)
    assert m, f'CSS rule not found: {anchored_selector}'
    return m.group(1)


def test_find_control_css_contract():
    assert re.search(r'min-height:\s*44px', _rule(r'^\.docket-find-btn'))
    # The room's shared garnet focus ring covers the new control.
    ring = re.search(r'^\.docket-side:focus-visible,[^{]*\{', CSS, re.M)
    assert ring and '.docket-find-btn:focus-visible' in ring.group(0)
