"""Spend a Golfer (/golf/pick/<id>): Golf Phase U2.

Locks the field builder in ``games/golf/services/field.py`` and what the pick
page renders from it (games/golf/DESIGN.md §2.3, §7.5 to §7.8, §7.15, §9):

- a spent golfer is struck in the field, never filtered out of it, and is a
  disabled option in both selects;
- the search key folds punctuation and accents ("jj" finds "J.J."), and the
  page's script folds the query the same way;
- ``#primary_player_id`` / ``#backup_player_id`` stay real selects under their
  own field names, so the form posts with no script and no library;
- the hatch and the money line appear only once the season has a signal;
- the page turns over at the lock, never at a status, and a field that is not
  published renders its empty state and takes no pick;
- the query count does not grow with the field.

Every test pins GOLF_FAKE_NOW (the conftest app fixture pins
ENVIRONMENT=testing), so none of them reads the real date.
"""
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
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.field import build_field, search_key, top_unspent_ids
from games.golf.services.stats import SpentWeek
from models.user import User
from tests._registry_helpers import set_status

TEMPLATE = (Path(__file__).parent.parent / 'games' / 'golf' / 'templates' / 'golf'
            / 'make_pick.html')

# Masters week 2026 on the league's wall clock; the fake clock is UTC.
THURSDAY = datetime(2026, 4, 9)
SUNDAY = datetime(2026, 4, 12)
LOCK = datetime(2026, 4, 9, 7, 40)
TUESDAY_BEFORE = '2026-04-07T15:00:00'
SUNDAY_430_PM_CT = '2026-04-12T21:30:00'


@pytest.fixture()
def season(app):
    return app.config['SEASON_YEAR']


@pytest.fixture()
def tuesday(monkeypatch):
    """The room is open and the Masters has not locked."""
    set_status(monkeypatch, 'golf', 'open')
    monkeypatch.setenv('GOLF_FAKE_NOW', TUESDAY_BEFORE)


# --- seed helpers (run inside the fixture's app context) --------------------

def _member(season, username='viewer'):
    user = User(username=username, email=f'{username}@test.com', display_name=username)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season))
    db.session.commit()
    return user


def _tournament(season, name='Masters Tournament', week=13, start=THURSDAY, end=SUNDAY,
                lock=LOCK, finalized=False, **kwargs):
    t = GolfTournament(
        api_tourn_id=f'T-{name}'[:20], name=name, season_year=season,
        start_date=start, end_date=end, pick_deadline=lock, purse=10_000_000,
        status='complete' if finalized else 'upcoming', results_finalized=finalized,
        week_number=week, **kwargs,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _golfer(first, last):
    player = GolfPlayer(api_player_id=f'{first}{last}'[:20], first_name=first, last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _field(tournament, size=50, start=0):
    """Put ``size`` golfers in a tournament's field ('Field Player07', ...)."""
    players = [GolfPlayer(api_player_id=f'F{i}', first_name='Field', last_name=f'Player{i:02d}')
               for i in range(start, start + size)]
    db.session.add_all(players)
    db.session.flush()
    db.session.add_all(
        GolfTournamentField(tournament_id=tournament.id, player_id=p.id) for p in players
    )
    db.session.commit()
    return players


def _enter(tournament, player):
    db.session.add(GolfTournamentField(tournament_id=tournament.id, player_id=player.id))
    db.session.commit()


def _spend(user, player, season, tournament=None):
    """A golfer the member has spent; with a tournament, the pick that names the week."""
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=player.id, season_year=season,
    ))
    if tournament is not None:
        spare = _golfer('Spare', f'For{player.id}')
        db.session.add(GolfPick(
            user_id=user.id, tournament_id=tournament.id,
            primary_player_id=player.id, backup_player_id=spare.id,
            active_player_id=player.id, points_earned=100_000, primary_used=True,
        ))
    db.session.commit()


def _earn(tournament, player, earnings):
    db.session.add(GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status='complete',
        final_position='1', rounds_completed=4, earnings=earnings,
    ))
    db.session.commit()


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _row(body, name):
    """The field's <li> for one golfer."""
    rows = [chunk for chunk in body.split('<li class="golf-field-row')[1:]
            if f'data-name="{name}"' in chunk]
    assert len(rows) == 1, f'{name}: {len(rows)} rows in the field'
    return rows[0].split('</li>')[0]


@contextmanager
def _count_sql():
    """Count SQL statements executed against the bound engine."""
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _before)
    try:
        yield counter
    finally:
        event.remove(db.engine, 'before_cursor_execute', _before)


# ============================================================================
# The search key
# ============================================================================

@pytest.mark.parametrize('name,key', [
    ('J.J. Spaun', 'jjspaun'),
    ('Ludvig Åberg', 'ludvigaberg'),
    ('Nicolai Højgaard', 'nicolaihojgaard'),
    ('Thorbjørn Olesen', 'thorbjornolesen'),
    ('Séamus Power', 'seamuspower'),
    ('Si Woo Kim', 'siwookim'),
    ("Alex Noren-O'Neil", 'alexnorenoneil'),
])
def test_search_key_folds_punctuation_and_accents(name, key):
    assert search_key(name) == key


def test_the_page_script_folds_a_query_like_the_search_key():
    """Two implementations of one fold: the row's key is built here, the typed
    query in the page. A letter added to one must be added to the other."""
    source = TEMPLATE.read_text()
    for fold in ("replace(/ø/g, 'o')", "replace(/æ/g, 'ae')", "replace(/œ/g, 'oe')",
                 "replace(/ł/g, 'l')", "replace(/đ/g, 'd')", "normalize('NFKD')",
                 "replace(/[^a-z0-9]/g, '')"):
        assert fold in source, f'the page script lost {fold}'


# ============================================================================
# The field builder
# ============================================================================

def _players(*names):
    return [GolfPlayer(id=i, api_player_id=str(i), first_name=first, last_name=last)
            for i, (first, last) in enumerate(names, start=1)]


def test_field_runs_in_money_order_with_the_spent_struck_in_place():
    young, scheffler, bhatia, rookie = _players(
        ('Cameron', 'Young'), ('Scottie', 'Scheffler'), ('Akshay', 'Bhatia'), ('Aaron', 'Rookie'),
    )
    field = build_field(
        [rookie, bhatia, scheffler, young],
        used={scheffler.id: scheffler},
        ytd={young.id: 7_000_000, scheffler.id: 6_000_000, bhatia.id: 5_000_000},
        remaining={young.id: 79, scheffler.id: 47, bhatia.id: 84, rookie.id: 100},
        weeks={scheffler.id: SpentWeek(13, 'Masters Tournament')},
    )

    assert [row.player.last_name for row in field.rows] == [
        'Young', 'Scheffler', 'Bhatia', 'Rookie',
    ]
    struck = field.rows[1]
    assert struck.used and struck.used_week == SpentWeek(13, 'Masters Tournament')
    assert struck.remaining == 47 and struck.ytd == 6_000_000
    assert field.available == 3
    assert [row.player.last_name for row in field.by_name] == [
        'Bhatia', 'Rookie', 'Scheffler', 'Young',
    ]
    assert field.has_money and field.has_burn


def test_field_before_the_seasons_first_signal():
    alpha, bravo = _players(('Zed', 'Alpha'), ('Abe', 'Bravo'))
    field = build_field([bravo, alpha], used={}, ytd={}, remaining=None, weeks={})

    # No money yet: the field falls back to the name.
    assert [row.player.last_name for row in field.rows] == ['Alpha', 'Bravo']
    assert all(row.remaining is None and row.ytd == 0 for row in field.rows)
    assert not field.has_money and not field.has_burn
    assert field.spent == [] and field.still_on_board == []


def test_spent_golfers_run_by_week_with_the_unaccounted_last():
    a, b, c = _players(('A', 'Early'), ('B', 'Late'), ('C', 'Byhand'))
    field = build_field(
        [a], used={b.id: b, c.id: c, a.id: a}, ytd={}, remaining=None,
        weeks={b.id: SpentWeek(9, 'THE PLAYERS Championship'), a.id: SpentWeek(2, 'Sony Open')},
    )

    assert [(g.player.last_name, g.week.week_number if g.week else None) for g in field.spent] == [
        ('Early', 2), ('Late', 9), ('Byhand', None),
    ]


def test_still_on_the_board_is_the_top_unspent_money():
    ytd = {1: 900, 2: 800, 3: 700, 4: 0, 5: 600, 6: 500, 7: 400}
    assert top_unspent_ids(ytd, used_ids={2}) == [1, 3, 5, 6, 7]   # five, spent and $0 out

    young, mcilroy = _players(('Cameron', 'Young'), ('Rory', 'McIlroy'))
    field = build_field(
        [young], used={}, ytd={young.id: 900, mcilroy.id: 800}, remaining=None, weeks={},
        top_unspent=[young, mcilroy],
    )
    assert [(e.player.last_name, e.ytd, e.in_field) for e in field.still_on_board] == [
        ('Young', 900, True), ('McIlroy', 800, False),
    ]


# ============================================================================
# The page
# ============================================================================

def test_pick_page_answers_before_the_list(app, client, season, tuesday):
    t = _tournament(season, is_major=True)
    _field(t)
    _login(client, _member(season))

    resp = client.get(f'/golf/pick/{t.id}')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert ('<h1 class="golf-title golf-title--page">Spend a Golfer: '
            '<span class="golf-title-event">Masters Tournament</span></h1>') in body
    assert 'Major ×1.5' in body and 'Apr 9–12' in body
    assert '$10,000,000' in body
    assert 'Thu Apr 9 · 7:40 AM CT' in body
    assert '0 <span class="golf-facts-note">this season</span>' in body
    assert '50 <span class="golf-facts-note">of 50 in the field</span>' in body
    assert 'Lock it in' in body
    assert 'A missed cut or a DQ costs $15 to the pot.' in body


def test_pick_page_keeps_the_selects_and_loads_no_library(app, client, season, tuesday):
    """§7.15: the ids and field names are the form's truth, with or without the script."""
    t = _tournament(season)
    _field(t)
    _login(client, _member(season))

    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    assert 'id="primary_player_id" name="primary_player_id" required' in body
    assert 'id="backup_player_id" name="backup_player_id" required' in body
    assert f'action="/golf/pick/{t.id}"' in body and 'name="csrf_token"' in body
    assert body.count('<option value="') == 2 * 51       # the field twice, a blank each

    source = TEMPLATE.read_text().lower()
    for gone in ('jsdelivr', 'tom-select', 'tomselect', 'http://', 'https://'):
        assert gone not in source, f'make_pick.html still carries {gone!r}'


def test_pick_page_draws_no_hatch_or_money_before_the_season_has_any(app, client, season, tuesday):
    t = _tournament(season)
    _field(t)
    _login(client, _member(season))

    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    assert 'golf-burn-bar' not in body and 'still have him' not in body
    assert 'YTD $' not in body
    assert 'Used golfers (' not in body and 'Still on the board' not in body


def test_a_spent_golfer_is_struck_not_hidden(app, client, season, tuesday):
    me = _member(season)
    valero = _tournament(season, name='Valero Texas Open', week=12, start=datetime(2026, 4, 2),
                         end=datetime(2026, 4, 5), lock=datetime(2026, 4, 2, 7, 30),
                         finalized=True)
    t = _tournament(season)
    players = _field(t)
    spent, open_one = players[0], players[1]
    _spend(me, spent, season, tournament=valero)
    _login(client, me)

    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)

    row = _row(body, 'Field Player00')
    assert row.startswith(' golf-field-row--used"')
    assert '<span class="golf-field-name golf-used">Field Player00</span>' in row
    assert '<span class="golf-chip golf-chip--pen">Used</span>' in row
    assert 'Wk 12 · Valero Texas Open' in row
    assert 'data-pick' not in row                         # struck: no action on the row
    # The room is one member, and he has spent him.
    assert '--have: 0%' in row
    assert '<span class="golf-burn-pct">0%</span><span class="golf-burn-word"> still have him' in row

    live = _row(body, 'Field Player01')
    assert 'golf-used' not in live and 'data-pick' in live
    assert '--have: 100%' in live

    # Both selects carry him, disabled.
    assert body.count(f'<option value="{spent.id}" disabled>Field Player00 (used)</option>') == 2
    assert body.count(f'<option value="{open_one.id}">Field Player01</option>') == 2

    assert '1 <span class="golf-facts-note">this season</span>' in body
    assert '49 <span class="golf-facts-note">of 50 in the field</span>' in body
    assert '49 of 50 yours to spend' in body
    assert 'Used golfers (1)' in body
    # The fold is a ruled week column: the week, then the golfer over his event.
    spent_list = body.split('<ol class="golf-fold-body golf-spent">')[1].split('</ol>')[0]
    assert '<span class="golf-spent-week">Wk 12</span>' in spent_list
    assert re.search(r'<span class="golf-spent-name">Field Player00<span class="golf-spent-event">'
                     r'<span class="visually-hidden">, </span>Valero Texas Open</span>', spent_list)


def test_field_rows_carry_the_money_in_money_order(app, client, season, tuesday):
    me = _member(season)
    sony = _tournament(season, name='Sony Open', week=1, start=datetime(2026, 1, 15),
                       end=datetime(2026, 1, 18), lock=datetime(2026, 1, 15, 11), finalized=True)
    t = _tournament(season)
    players = _field(t)
    spaun = _golfer('J.J.', 'Spaun')
    _enter(t, spaun)
    absent = _golfer('Rory', 'McIlroy')
    _earn(sony, players[30], 1_000_000)
    _earn(sony, spaun, 2_500_000)
    _earn(sony, absent, 4_000_000)
    _login(client, me)

    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    field = body.split('<ul class="golf-field">')[1].split('</ul>')[0]

    assert 'YTD $2,500,000' in _row(body, 'J.J. Spaun')
    assert 'data-search="jjspaun"' in _row(body, 'J.J. Spaun')
    assert 'YTD $0' in _row(body, 'Field Player00')
    assert (field.index('data-name="J.J. Spaun"') < field.index('data-name="Field Player30"')
            < field.index('data-name="Field Player00"'))

    # Still on the board: the member's top unspent money, in this field or not.
    still = body.split('Still on the board')[1]
    assert still.index('Rory McIlroy') < still.index('J.J. Spaun') < still.index('Field Player30')
    assert 'not in this field' in still.split('Rory McIlroy')[1].split('</li>')[0]
    assert '$4,000,000' in still


def test_pick_page_shows_a_saved_pick(app, client, season, tuesday):
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    db.session.add(GolfPick(user_id=me.id, tournament_id=t.id,
                            primary_player_id=players[3].id, backup_player_id=players[7].id))
    db.session.commit()
    _login(client, me)

    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    primary, backup = body.split('id="backup_player_id"')
    assert f'<option value="{players[3].id}" selected>Field Player03</option>' in primary
    assert f'<option value="{players[7].id}" selected>Field Player07</option>' in backup
    assert body.count(' selected>') == 2
    # The script reads what is saved from the server, never from a reloaded select.
    assert f'data-saved-primary="{players[3].id}"' in body
    assert f'data-saved-backup="{players[7].id}"' in body
    assert 'Your pick is in. Change either golfer until' in body


def _note(body, hook):
    """The pick action's note with this data hook: its <p> tag and its text."""
    match = re.search(rf'<p class="golf-pick-note" {hook}( hidden)?>(.*?)</p>', body, re.S)
    assert match, f'no {hook} note'
    return bool(match.group(1)), re.sub(r'<[^>]+>', '', match.group(2))


def test_the_pick_note_says_whether_the_pick_is_saved(app, client, season, tuesday):
    """A chosen slot and a saved one are drawn alike, so the line under Lock it
    in says which (DESIGN.md §7.24). Without the script the server's state
    shows; the script then shows the one note that fits."""
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    _login(client, me)

    # No pick yet: what is chosen is not saved until it is locked in.
    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    assert _note(body, 'data-note-ready') == (
        False, "Not saved yet. Once it's in, you can change it until Thu Apr 9 · 7:40 AM CT.")
    assert '<p class="golf-pick-note" data-note-change' not in body
    assert _note(body, 'data-note-saved')[0] is True

    # A saved pick: it is in, and a change names the pick that stands until then.
    db.session.add(GolfPick(user_id=me.id, tournament_id=t.id,
                            primary_player_id=players[3].id, backup_player_id=players[7].id))
    db.session.commit()
    body = client.get(f'/golf/pick/{t.id}').get_data(as_text=True)
    assert _note(body, 'data-note-saved') == (
        False, 'Your pick is in. Change either golfer until Thu Apr 9 · 7:40 AM CT.')
    assert _note(body, 'data-note-change') == (
        True, 'Not saved yet. Until you lock it in, your pick stays Field Player03, '
              'with Field Player07 as your backup.')
    assert _note(body, 'data-note-ready')[0] is True

    # The script picks between them.
    source = TEMPLATE.read_text()
    assert "noteReady.hidden = !(both && dirty && !noteChange);" in source
    assert "if (noteChange) noteChange.hidden = !(both && dirty);" in source


def test_pick_page_query_count_does_not_grow_with_the_field(app, client, season, tuesday):
    me = _member(season)
    sony = _tournament(season, name='Sony Open', week=1, start=datetime(2026, 1, 15),
                       end=datetime(2026, 1, 18), lock=datetime(2026, 1, 15, 11), finalized=True)
    t = _tournament(season)
    players = _field(t)
    _spend(me, players[0], season, tournament=sony)
    _earn(sony, players[1], 500_000)
    # Ids, before db.session.remove() detaches the rows they came from.
    tid, sony_id, me_id = t.id, sony.id, me.id
    _login(client, me)

    # Warm the before_request status refresh so both measured requests skip it.
    assert client.get(f'/golf/pick/{tid}').status_code == 200
    db.session.remove()
    with _count_sql() as small:
        assert client.get(f'/golf/pick/{tid}').status_code == 200

    more = _field(db.session.get(GolfTournament, tid), size=30, start=50)
    _spend(db.session.get(User, me_id), more[0], season)
    _earn(db.session.get(GolfTournament, sony_id), more[1], 250_000)
    db.session.remove()
    with _count_sql() as large:
        assert client.get(f'/golf/pick/{tid}').status_code == 200

    assert large['n'] == small['n'], (
        f"the pick page issues a query per golfer: {small['n']} -> {large['n']} "
        f'as the field went 50 -> 80'
    )


# ============================================================================
# Before the field, and past the lock
# ============================================================================

def test_unpublished_field_renders_the_empty_state_and_takes_no_pick(app, client, season, tuesday):
    me = _member(season)
    t = _tournament(season)
    players = _field(t, size=10)                          # short of a field
    _login(client, me)

    resp = client.get(f'/golf/pick/{t.id}')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Spend a Golfer: <span class="golf-title-event">Masters Tournament</span>' in body
    assert 'The field publishes Tuesday. Picks open then.' in body
    assert 'Thu Apr 9 · 7:40 AM CT' in body
    assert 'primary_player_id' not in body and 'Lock it in' not in body

    resp = client.post(f'/golf/pick/{t.id}', data={
        'primary_player_id': players[0].id, 'backup_player_id': players[1].id,
    })
    assert resp.status_code == 200
    assert 'published yet. Picks open Tuesday.' in resp.get_data(as_text=True)
    assert GolfPick.query.count() == 0


def test_past_the_lock_the_page_turns_over_to_the_board(app, client, season, monkeypatch):
    """The lock closes the pick, whatever the status says (still 'upcoming' here)."""
    set_status(monkeypatch, 'golf', 'open')
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_430_PM_CT)
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    _login(client, me)

    resp = client.get(f'/golf/pick/{t.id}')
    assert resp.status_code == 302
    assert resp.location.endswith(f'/golf/tournament/{t.id}')

    resp = client.post(f'/golf/pick/{t.id}', data={
        'primary_player_id': players[0].id, 'backup_player_id': players[1].id,
    })
    assert resp.status_code == 302
    assert GolfPick.query.count() == 0

    board = client.get(resp.location).get_data(as_text=True)
    assert 'Picks for the Masters Tournament locked Thu Apr 9 · 7:40 AM CT.' in board


# ============================================================================
# Lock it in
# ============================================================================

def test_lock_it_in_saves_the_pick_and_lands_on_the_sheet(app, client, season, tuesday):
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    _login(client, me)

    resp = client.post(f'/golf/pick/{t.id}', data={
        'primary_player_id': players[3].id, 'backup_player_id': players[7].id,
    })
    assert resp.status_code == 302
    assert resp.location.endswith('/golf/')

    pick = GolfPick.query.one()
    assert (pick.user_id, pick.primary_player_id, pick.backup_player_id) == (
        me.id, players[3].id, players[7].id,
    )
    sheet = client.get(resp.location).get_data(as_text=True)
    assert ('Field Player03 is your pick for the Masters Tournament, with Field Player07 '
            'as your backup. You can change it until Thu Apr 9 · 7:40 AM CT.') in sheet


def test_lock_it_in_changes_a_saved_pick_in_place(app, client, season, tuesday):
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    db.session.add(GolfPick(user_id=me.id, tournament_id=t.id,
                            primary_player_id=players[3].id, backup_player_id=players[7].id))
    db.session.commit()
    _login(client, me)

    resp = client.post(f'/golf/pick/{t.id}', data={
        'primary_player_id': players[7].id, 'backup_player_id': players[9].id,
    })
    assert resp.status_code == 302

    pick = GolfPick.query.one()
    assert (pick.primary_player_id, pick.backup_player_id) == (players[7].id, players[9].id)


@pytest.mark.parametrize('which,message', [
    ('missing', 'Name both a primary and a backup.'),
    ('same', 'Your primary and your backup must be two different golfers.'),
    ('spent', 'Your primary has already been spent this season. Choose another golfer.'),
    ('outside', 'Your backup is not in this field. Choose a golfer from the field.'),
])
def test_a_refused_pick_writes_nothing_and_says_why(app, client, season, tuesday, which, message):
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    _spend(me, players[0], season)
    outsider = _golfer('Not', 'Entered')
    _login(client, me)

    data = {
        'missing': {'primary_player_id': players[3].id},
        'same': {'primary_player_id': players[3].id, 'backup_player_id': players[3].id},
        'spent': {'primary_player_id': players[0].id, 'backup_player_id': players[3].id},
        'outside': {'primary_player_id': players[3].id, 'backup_player_id': outsider.id},
    }[which]
    resp = client.post(f'/golf/pick/{t.id}', data=data)

    assert resp.status_code == 200
    assert message in resp.get_data(as_text=True)
    assert GolfPick.query.filter_by(tournament_id=t.id).count() == 0


def test_a_refused_change_keeps_the_saved_pick(app, client, season, tuesday):
    me = _member(season)
    t = _tournament(season)
    players = _field(t)
    _spend(me, players[0], season)
    db.session.add(GolfPick(user_id=me.id, tournament_id=t.id,
                            primary_player_id=players[3].id, backup_player_id=players[7].id))
    db.session.commit()
    _login(client, me)

    resp = client.post(f'/golf/pick/{t.id}', data={
        'primary_player_id': players[0].id, 'backup_player_id': players[7].id,
    })
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'already been spent this season' in body
    # The form re-renders the pick as it is saved, not as it was refused.
    assert f'<option value="{players[3].id}" selected>Field Player03</option>' in body

    db.session.expire_all()
    pick = GolfPick.query.one()
    assert (pick.primary_player_id, pick.backup_player_id) == (players[3].id, players[7].id)


# ============================================================================
# Template source: what U2 retired stays retired
# ============================================================================

def test_pick_template_carries_no_pre_u2_markup():
    source = TEMPLATE.read_text()
    for retired in ('page-hero', 'card-header', 'card-body', 'alert-info', 'badge bg-',
                    'bi bi-', 'text-gold', 'btn-warning', 'form-select', 'animate-in'):
        assert retired not in source, f'make_pick.html still carries {retired!r}'
    assert not re.search(r'eyebrow', source)
