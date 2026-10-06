"""The Record Room (/golf/stats): Golf Phase U5.

Locks the page built from ``games/golf/services/stats.py``
(games/golf/DESIGN.md §8, §9); the aggregates themselves are locked in
``tests/test_golf_stats.py``:

- public, season-aware, and built from banked tournaments only;
- a contents line and five leaves: the season race, the lines, the Form
  Guide, the Burn List, Still on the Board;
- the race is drawn finished and still by the server; its two scripts are
  local, versioned enhancements, and the page is whole without them;
- a screen reader gets the race as a table;
- the query count does not grow with the room, the weeks or the golfers.

A test signs in before its first request or not at all (Flask-Login caches
the viewer on the fixture's app context).
"""
import json
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

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
from games.golf.services.field import search_key
from models.user import User

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / 'static' / 'js' / 'golf'


@pytest.fixture()
def season(app):
    return app.config['SEASON_YEAR']


# --- seed helpers (run inside the fixture's app context) --------------------

def _member(season, name):
    user = User(username=name.lower(), email=f'{name.lower()}@test.com', display_name=name)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season))
    db.session.commit()
    return user


def _player(first, last):
    player = GolfPlayer(api_player_id=f'{first}{last}'[:20], first_name=first, last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _event(season, name, start, finalized=True, purse=10_000_000):
    t = GolfTournament(
        api_tourn_id=f'{season}-{name}'[:20], name=name, season_year=season,
        start_date=start, end_date=start, pick_deadline=start, purse=purse,
        status='complete' if finalized else 'active', results_finalized=finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _result(tournament, player, position='1', status='complete', earnings=0):
    db.session.add(GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status=status,
        final_position=position, rounds_completed=4, earnings=earnings,
    ))
    db.session.commit()


def _banked(user, tournament, golfer, backup, points):
    """A resolved pick and the usage row the scoring writes with it."""
    db.session.add(GolfPick(
        user_id=user.id, tournament_id=tournament.id, primary_player_id=golfer.id,
        backup_player_id=backup.id, active_player_id=golfer.id, points_earned=points,
        primary_used=True,
    ))
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=golfer.id, season_year=tournament.season_year,
    ))
    db.session.commit()


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _page(client, **query):
    resp = client.get('/golf/stats', query_string=query)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _leaf(body, leaf_id):
    start = body.index(f'id="{leaf_id}"')
    return body[start:body.index('</section>', start)]


@contextmanager
def _count_sql():
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _before)
    try:
        yield counter
    finally:
        event.remove(db.engine, 'before_cursor_execute', _before)


def _two_events(season):
    """Alice and Bob over two banked events; Åberg earns and nobody spends him.

    Alice banks Scheffler's $2,000,000 then J.J. Spaun's $300,000; Bob banks
    McIlroy's $400,000 then misses the cut on Scheffler.
    """
    alice, bob = _member(season, 'Alice'), _member(season, 'Bob')
    g = {
        'scott': _player('Scottie', 'Scheffler'), 'rory': _player('Rory', 'McIlroy'),
        'spaun': _player('J.J.', 'Spaun'), 'aberg': _player('Ludvig', 'Åberg'),
        'spare': _player('Spare', 'Golfer'),
    }
    sony = _event(season, 'Sony Open', datetime(2026, 1, 15))
    genesis = _event(season, 'Genesis Invitational', datetime(2026, 2, 12), purse=20_000_000)
    _result(sony, g['scott'], position='1', earnings=2_000_000)
    _result(sony, g['rory'], position='T5', earnings=400_000)
    _result(sony, g['aberg'], position='2', earnings=1_200_000)
    _result(genesis, g['spaun'], position='T8', earnings=300_000)
    _result(genesis, g['scott'], position='CUT', status='cut')
    _result(genesis, g['aberg'], position='3', earnings=900_000)
    _banked(alice, sony, g['scott'], g['spare'], 2_000_000)
    _banked(bob, sony, g['rory'], g['spare'], 400_000)
    _banked(alice, genesis, g['spaun'], g['spare'], 300_000)
    _banked(bob, genesis, g['scott'], g['spare'], 0)
    return alice, bob, g, (sony, genesis)


# ============================================================================
# The page
# ============================================================================

def test_record_room_is_public_with_a_contents_line_and_five_leaves(app, client, season):
    _two_events(season)
    body = _page(client)

    assert '<h1 class="golf-title golf-title--page">The Record Room</h1>' in body
    assert f'{season} season' in body and '2 of 2 events banked' in body
    leaves = ['golf-race', 'golf-lines', 'golf-form', 'golf-burn', 'golf-unspent']
    contents = body[body.index('<nav class="golf-margin golf-contents"'):]
    contents = contents[:contents.index('</nav>')]
    assert re.findall(r'href="#([a-z-]+)"', contents) == leaves
    assert re.findall(r'<section class="golf-leaf" id="([a-z-]+)"', body) == leaves
    # Each leaf's label is its own heading; nothing sits above an H2.
    assert len(re.findall(r'<h2 class="golf-label" id="golf-[a-z]+-label">', body)) == 5
    assert body.count('<h1') == 1


def test_stats_pill_is_lit_in_the_record_room(app, client, season):
    _two_events(season)
    body = _page(client)
    assert re.search(r'class="subnav-pill active"\s+href="/golf/stats">Stats</a>', body)


def test_race_is_drawn_finished_for_a_guest(app, client, season):
    alice, bob, *_ = _two_events(season)
    race = _leaf(_page(client), 'golf-race')

    assert 'through the Genesis Invitational.' in race
    assert race.count('<polyline') == 2
    assert 'golf-race-line--leader' in race and 'golf-race-line--pack' in race
    assert 'golf-race-line--you' not in race and 'golf-race-row--me' not in race
    assert 'Alice, in the lead' in race
    assert 'Alice leads with $2,300,000.' in race           # the drawing's own description
    # The standings, in the sheet's order, each a link to a scorecard.
    rows = re.findall(r'data-race-rank>([^<]+)</span>.*?href="/golf/member/(\d+)">([^<]+)</a>.*?'
                      r'data-race-value>([^<]+)<', race, re.S)
    assert rows == [('1', str(alice.id), 'Alice', '$2,300,000'),
                    ('2', str(bob.id), 'Bob', '$400,000')]
    # The controls wait for the script; nothing moves until the member asks.
    assert re.search(r'<button[^>]*data-race-play hidden>Play the season</button>', race)
    assert re.search(r'<div class="golf-race-scrub" data-race-scrub-wrap hidden>', race)
    assert 'autoplay' not in race


def test_race_marks_the_members_own_line(app, client, season):
    alice, bob, *_ = _two_events(season)
    _login(client, bob)
    race = _leaf(_page(client), 'golf-race')

    assert race.count('golf-race-line--you') == 1
    assert race.count('golf-race-row--me') == 1
    assert '>You</li>' in race and 'Alice, in the lead' in race
    assert 'You are 2 with $400,000.' in race
    assert 'golf-race-name--you' in race and 'golf-race-name--leader' in race


def test_race_replay_payload_is_the_servers_geometry(app, client, season):
    _two_events(season)
    race = _leaf(_page(client), 'golf-race')
    payload = json.loads(re.search(
        r'<script type="application/json" data-race-data>(.*?)</script>', race, re.S).group(1))

    assert payload['count'] == 2
    assert [e['name'] for e in payload['events']] == ['Sony Open', 'Genesis Invitational']
    alice = next(line for line in payload['lines'] if line['name'] == 'Alice')
    assert alice['cumulative'] == [2_000_000, 2_300_000]
    drawn = re.search(r'golf-race-line--leader" points="([^"]+)"', race).group(1)
    assert [[float(x), float(y)] for x, y in (p.split(',') for p in drawn.split())] == alice['coords']


def test_race_is_mirrored_as_a_table_for_a_screen_reader(app, client, season):
    """The wrapper is hidden, never the table: a visually-hidden <table> loses
    its semantics in some screen readers."""
    _two_events(season)
    race = _leaf(_page(client), 'golf-race')

    mirror = re.search(r'<div class="visually-hidden">\s*<table>(.*?)</table>\s*</div>', race, re.S)
    assert mirror
    table = ' '.join(re.sub(r'<[^>]+>', ' ', mirror.group(1)).split())
    assert 'Member Sony Open Genesis Invitational' in table
    assert 'Alice $2,000,000 $2,300,000' in table
    assert 'Bob $400,000 $400,000' in table


def test_a_shared_lead_is_said_and_drawn_as_shared(app, client, season):
    """Two members on the same winner: neither is "the leader"."""
    amy, zed, low = (_member(season, name) for name in ('Amy', 'Zed', 'Low'))
    winner, other, spare = _player('The', 'Winner'), _player('An', 'Other'), _player('Spare', 'Golfer')
    for name, day in (('The American Express', 22), ('Farmers Insurance Open', 29)):
        t = _event(season, name, datetime(2026, 1, day))
        _result(t, winner, earnings=500_000)
        _result(t, other, position='40', earnings=10_000)
        db.session.add_all([
            GolfPick(user_id=member.id, tournament_id=t.id, primary_player_id=golfer.id,
                     backup_player_id=spare.id, active_player_id=golfer.id,
                     points_earned=points, primary_used=True)
            for member, golfer, points in ((amy, winner, 500_000), (zed, winner, 500_000),
                                           (low, other, 10_000))
        ])
        db.session.commit()
    race = _leaf(_page(client), 'golf-race')

    assert 'Amy and Zed, tied for the lead' in ' '.join(race.split())
    assert '2 members are tied for the lead at $1,000,000.' in race
    assert race.count('golf-race-line--leader') == 2
    assert re.search(r'golf-race-name--leader[^>]*>2 tied<', race)
    assert 'in the lead' not in race and 'Amy leads' not in race
    # An event that brings its own article keeps one.
    assert 'through the Farmers Insurance Open.' in race
    payload = json.loads(re.search(
        r'<script type="application/json" data-race-data>(.*?)</script>', race, re.S).group(1))
    assert [e['the'] for e in payload['events']] == [
        'the American Express', 'the Farmers Insurance Open']


def test_one_banked_event_draws_dots_and_no_replay(app, client, season):
    alice = _member(season, 'Alice')
    scott, spare = _player('Scottie', 'Scheffler'), _player('Spare', 'Golfer')
    sony = _event(season, 'Sony Open', datetime(2026, 1, 15))
    _result(sony, scott, earnings=500_000)
    _banked(alice, sony, scott, spare, 500_000)
    body = _page(client)

    race = _leaf(body, 'golf-race')
    assert 'golf-race-dot golf-race-dot--leader' in race
    assert 'data-race-data' not in race and 'data-race-play' not in race
    assert 'season-replay.js' not in body
    assert '1 of 1 event banked' in body


def test_a_season_with_nothing_banked_says_so_on_every_leaf(app, client, season):
    _member(season, 'Alice')
    _event(season, 'On The Course', datetime(2026, 1, 15), finalized=False)
    body = _page(client)

    assert '0 of 1 event banked' in body
    assert 'The race starts when the first tournament banks.' in _leaf(body, 'golf-race')
    assert 'The lines go in when the first tournament banks.' in _leaf(body, 'golf-lines')
    assert 'No prize money is banked yet.' in _leaf(body, 'golf-form')
    assert 'Nobody has spent a golfer yet.' in _leaf(body, 'golf-burn')
    assert 'No prize money is banked yet.' in _leaf(body, 'golf-unspent')
    assert '<svg' not in body and 'js/golf/' not in body


def test_banked_events_with_no_money_draw_no_race(app, client, season):
    """Nobody picked the opener: an axis that tops out at $1 says nothing."""
    _member(season, 'Alice')
    _event(season, 'Sony Open', datetime(2026, 1, 15))
    body = _page(client)

    race = _leaf(body, 'golf-race')
    assert 'Nobody has banked a dollar yet. The race starts with the first one.' in race
    assert '<svg' not in body and 'season-replay.js' not in body


def test_lines_are_sentences_not_awards(app, client, season):
    _two_events(season)
    lines = ' '.join(re.sub(r'<[^>]+>', ' ', _leaf(_page(client), 'golf-lines')).split())

    assert 'Pick of the season Alice spent Scottie Scheffler at the Sony Open for $2,000,000 .' in lines
    assert 'Most consistent Alice finished in the money 2 of 2 weeks.' in lines
    assert 'Most missed cuts Bob missed 1 cut in 2 weeks.' in lines
    assert ('Coldest pick Bob spent Scottie Scheffler at the Genesis Invitational, '
            'a $20,000,000 purse, for $0 .') in lines
    assert 'WD survivor' not in lines                       # nobody had a backup step in
    for medal in ('🏆', '🥇', 'award', 'winner', 'trophy'):
        assert medal not in lines.lower()


def test_form_guide_burn_list_and_still_on_the_board(app, client, season):
    alice, bob, g, _events = _two_events(season)
    body = _page(client)

    form = ' '.join(re.sub(r'<[^>]+>', ' ', _leaf(body, 'golf-form')).split())
    assert form.index('Ludvig Åberg') < form.index('Scottie Scheffler') < form.index('Rory McIlroy')
    assert 'Ludvig Åberg 2 events · best 2nd · no missed cuts $2,100,000' in form
    assert 'Scottie Scheffler 2 events · best 1st · 1 missed cut $2,000,000' in form
    assert 'Rory McIlroy 1 event · best T5 · no missed cuts $400,000' in form

    burn = _leaf(body, 'golf-burn')
    assert '3 golfers spent' in burn
    rows = re.findall(r'<li class="golf-field-row" data-row data-search="([a-z]+)">(.*?)</li>', burn, re.S)
    assert [key for key, _html in rows] == ['scottiescheffler', 'rorymcilroy', 'jjspaun']
    assert all(key == search_key(name) for key, name in zip(
        (key for key, _html in rows), ('Scottie Scheffler', 'Rory McIlroy', 'J.J. Spaun'), strict=True))
    scott = ' '.join(re.sub(r'<[^>]+>', ' ', rows[0][1]).split())
    assert scott == 'Scottie Scheffler Spent by 2 · $2,000,000 banked 0% still have him'
    assert 'style="--have: 0%"' in rows[0][1] and 'style="--have: 50%"' in rows[1][1]
    # The search waits for its script; without it every row is on the page.
    assert re.search(r'data-burn-search-wrap hidden>', burn)
    assert ' hidden' not in ''.join(html for _key, html in rows)

    unspent = ' '.join(re.sub(r'<[^>]+>', ' ', _leaf(body, 'golf-unspent')).split())
    assert 'Ludvig Åberg $2,100,000' in unspent
    assert 'Scheffler' not in unspent and 'Spaun' not in unspent


def test_record_room_reads_banked_tournaments_only(app, client, season):
    """A week on the course leaks into no leaf: not its picks, not its money."""
    alice, bob, g, _events = _two_events(season)
    live = _event(season, 'Live Invitational', datetime(2026, 3, 5), finalized=False)
    hot = _player('Hot', 'Livegolfer')
    _result(live, hot, earnings=9_000_000)
    db.session.add(GolfPick(user_id=bob.id, tournament_id=live.id, primary_player_id=hot.id,
                            backup_player_id=g['spare'].id, active_player_id=hot.id,
                            points_earned=9_000_000))
    db.session.commit()
    body = _page(client)

    content = body[body.index('<h1 class="golf-title'):body.index('class="golf-foot"')]
    assert 'Livegolfer' not in content and 'Live Invitational' not in content
    assert '$9,000,000' not in content
    assert '2 of 3 events banked' in body


# ============================================================================
# Seasons
# ============================================================================

def test_record_room_reads_one_season(app, client, season):
    _two_events(season)
    past = User(username='past', email='past@test.com', display_name='PastMember')
    past.set_password('pw')
    db.session.add(past)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=past.id, season_year=season - 1))
    db.session.commit()
    old, spare = _player('Old', 'Timer'), GolfPlayer.query.filter_by(last_name='Golfer').one()
    last_year = _event(season - 1, 'Last Year Open', datetime(2025, 3, 6))
    _result(last_year, old, earnings=77_000)
    _banked(past, last_year, old, spare, 77_000)

    now = _page(client)
    assert 'PastMember' not in now and 'Old Timer' not in now and 'Last Year Open' not in now
    assert f'href="/golf/stats?season={season - 1}">{season - 1} season</a>' in now

    then = _page(client, season=season - 1)
    assert 'Alice' not in then and 'Scheffler' not in then and 'Sony Open' not in then
    assert 'PastMember' in then and 'Old Timer' in then
    assert f'href="/golf/member/{past.id}?season={season - 1}"' in then
    assert f'href="/golf/stats">{season} season</a>' in then

    assert client.get('/golf/stats', query_string={'season': season - 5}).status_code == 404
    assert client.get('/golf/stats', query_string={'season': 'next'}).status_code == 404


def test_record_room_of_a_season_with_no_tournaments_is_not_a_404(app, client, season):
    """The configured season is always a room, even before its schedule is seeded."""
    body = _page(client)
    assert 'the schedule is not posted yet' in body and '0 of 0' not in body
    assert 'season</a>' not in body                         # one season: no selector


# ============================================================================
# No query per member, per week or per golfer
# ============================================================================

def test_record_room_query_count_does_not_grow(app, client, season):
    alice, bob, g, _events = _two_events(season)
    spare_id = g['spare'].id

    # Warm the before_request status refresh so both measured requests skip it.
    _page(client)
    db.session.remove()
    with _count_sql() as small:
        _page(client)

    spare = db.session.get(GolfPlayer, spare_id)
    members = [_member(season, f'Extra{i}') for i in range(6)]
    for week in range(8):
        banked = _event(season, f'Week {week}', datetime(2026, 3, 1 + week))
        for i, member in enumerate(members):
            golfer = _player(f'W{week}', f'Golfer{i}')
            _result(banked, golfer, position=str(i + 1), earnings=50_000 * (i + 1))
            _banked(member, banked, golfer, spare, 50_000 * (i + 1))
    db.session.remove()
    with _count_sql() as large:
        _page(client)

    assert large['n'] == small['n'], (
        f"the Record Room issues a query per row: {small['n']} -> {large['n']} as the season "
        f'went 2 -> 10 events, the room 2 -> 8 and the burned golfers 3 -> 51'
    )


# ============================================================================
# The scripts: local, versioned, and enhancement only
# ============================================================================

def test_scripts_are_local_versioned_and_load_no_library(app, client, season):
    _two_events(season)
    body = _page(client)

    tags = re.findall(r'<script src="(/static/js/golf/[^"]+)" defer></script>', body)
    assert len(tags) == 2
    for name, src in zip(('season-replay.js', 'burn-list.js'), tags, strict=True):
        assert re.fullmatch(rf'/static/js/golf/{re.escape(name)}\?v=[^"&]+', src)
    template = (ROOT / 'games/golf/templates/golf/record_room.html').read_text()
    # The page's own scripts are these two and nothing from anywhere else.
    assert template.count('<script src=') == 2
    assert template.count("?v={{ asset_version }}") == 2
    assert 'http' not in template
    for name in ('season-replay.js', 'burn-list.js'):
        source = (SCRIPTS / name).read_text()
        assert 'http' not in source and 'import ' not in source and 'require(' not in source


def test_burn_list_script_folds_a_query_like_the_search_key():
    """The third copy of one fold (search_key, the pick page, this script): a
    letter added to one must be added to all."""
    source = (SCRIPTS / 'burn-list.js').read_text()
    for fold in ("replace(/ø/g, 'o')", "replace(/æ/g, 'ae')", "replace(/œ/g, 'oe')",
                 "replace(/ł/g, 'l')", "replace(/đ/g, 'd')", "normalize('NFKD')",
                 "replace(/[^a-z0-9]/g, '')"):
        assert fold in source, f'the Burn List script lost {fold}'


def test_replay_script_ranks_in_competition_rank_and_honors_reduced_motion():
    source = (SCRIPTS / 'season-replay.js').read_text()
    # Ties share a rank and carry the T, as the server's own ranker does.
    assert "entry.value === order[i - 1].value ? order[i - 1].rank : i + 1" in source
    assert "(shared[entry.rank] > 1 ? 'T' : '')" in source
    # Under reduced motion the season does not play; the slider still steps it.
    assert "(prefers-reduced-motion: reduce)" in source
    assert "if (playBtn && !reduceMotion) playBtn.removeAttribute('hidden');" in source
    # The readout takes the event's phrase from the server ("the American
    # Express", never "the The …") and says who leads after it.
    assert "'After ' + events[idx].the" in source and "'the '" not in source
    assert "' You lead.'" in source and "' tied for the lead.'" in source
    # No trend arrows beside figures (DESIGN.md §6.10).
    assert '▲' not in source and '▼' not in source
    css = (ROOT / 'static/css/style.css').read_text()
    reduced = css[css.rindex('@media (prefers-reduced-motion: reduce)', 0, css.index('.golf-chip.badge-penalty')):]
    assert '.golf-race-row' in reduced[:reduced.index('}') + 40]
