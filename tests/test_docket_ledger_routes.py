"""The season ledger and the published rules — the two T10 surfaces.

Locks what a player actually sees: competition rank rather than row position,
key 3 divided only at render (D20-eng), the platform avatar integration point,
and every scoring number on the rules page coming from the engine rather than
prose that can drift.
"""
import re
from datetime import datetime

from sqlalchemy import select

from extensions import db
from games.docket.models import DocketWeekResult
from tests._docket_fixtures import make_enrollment, make_user, make_week

GRADED_AT = datetime(2026, 9, 6, 4, 0)


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _member(username='player', **enrollment_kwargs):
    user = make_user(username)
    make_enrollment(user, **enrollment_kwargs)
    return user


def _week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=GRADED_AT))


def _text(html):
    """Tag-stripped page text, whitespace collapsed."""
    return ' '.join(re.sub(r'<[^>]+>', ' ', html).split())


def _standings_cells(html):
    """[[rank, player, points, wins, error], ...] from the standings table."""
    body = html[html.find('<tbody>'):html.find('</tbody>')]
    rows = []
    for cells in re.findall(r'<tr class="[^"]*">(.*?)</tr>', body, re.S):
        rows.append([' '.join(re.sub(r'<[^>]+>', ' ', cell).split())
                     for cell in re.findall(r'<td[^>]*>(.*?)</td>',
                                            cells, re.S)])
    return rows


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

def test_ledger_requires_enrollment(app, client):
    """The ledger names members, so it sits behind the join gate."""
    outsider = make_user('outsider')
    db.session.commit()
    _login(client, outsider)

    resp = client.get('/docket/ledger')
    assert resp.status_code == 302
    assert '/docket/join' in resp.headers['Location']


def test_ledger_renders_with_zero_graded_weeks(app, client):
    """The state this ships in: prod docket tables stay empty until the
    Week-1 import, so the launch-week ledger must be a real page."""
    player = _member('player')
    db.session.commit()
    _login(client, player)

    resp = client.get('/docket/ledger')
    assert resp.status_code == 200
    text = _text(resp.data.decode())
    assert 'The ledger opens with the first verdicts' in text
    assert 'Appearing this season' in text
    assert 'player' in text


def test_an_unenrolled_platform_admin_is_still_sent_to_join(app, client):
    """enrollment_required only bypasses for platform admins on a
    coming_soon game; The Docket is open, so the gate holds for everyone.
    That makes the ledger's no-members-at-all branch unreachable by route
    (it is covered directly in test_docket_season_pass.py) and this is the
    behavior worth locking here."""
    admin = make_user('boss', is_admin=True)
    db.session.commit()
    _login(client, admin)

    resp = client.get('/docket/ledger')
    assert resp.status_code == 302
    assert '/docket/join' in resp.headers['Location']


def test_competition_rank_renders_shared_and_gapped(app, client):
    """1, 1, 3 — never dense 1, 2, 3, and never the row's position."""
    week = _week(1)
    for name, points, wins in [('alice', 9.0, 9), ('bob', 9.0, 9),
                               ('carol', 4.0, 4)]:
        _result(week, _member(name), points, wins)
    viewer = _member('viewer')
    db.session.commit()
    _login(client, viewer)

    html = client.get('/docket/ledger').data.decode()
    ranks = [row[0].split()[0] for row in _standings_cells(html)]
    assert ranks == ['1', '1', '3', '4'], ranks


def test_shared_ranks_say_tied_out_loud(app, client):
    week = _week(1)
    for name in ('alice', 'bob'):
        _result(week, _member(name), 5.0, 5)
    viewer = _member('viewer')
    db.session.commit()
    _login(client, viewer)

    html = client.get('/docket/ledger').data.decode()
    tied = [row[0] for row in _standings_cells(html) if 'tied' in row[0]]
    assert len(tied) == 2


def test_every_row_shows_the_avatar_before_the_display_name(app, client):
    """The platform integration point: user.get_avatar() inline, first."""
    week = _week(1)
    alice = _member('alice')
    alice.avatar_emoji = '\U0001F980'   # crab
    _result(week, alice, 5.0, 5)
    db.session.commit()
    _login(client, alice)

    html = client.get('/docket/ledger').data.decode()
    player_cell = _standings_cells(html)[0][1]
    assert player_cell.startswith('\U0001F980'), player_cell
    assert 'alice' in player_cell


def test_key_three_is_divided_by_ten_only_at_render(app, client):
    """515 tenths is 51.5 on the page, and nothing but tenths in the DB."""
    week = _week(1)
    alice = _member('alice')
    _result(week, alice, 5.0, 5, error_tenths=515)
    db.session.commit()
    _login(client, alice)

    html = client.get('/docket/ledger').data.decode()
    assert _standings_cells(html)[0][4] == '51.5'
    stored = db.session.scalar(
        select(DocketWeekResult).filter_by(user_id=alice.id, week_id=week.id)
    ).error_tenths
    assert stored == 515 and isinstance(stored, int)


def test_the_dropped_week_is_struck_in_place(app, client):
    """The drop is the game's most confusing rule; the ledger states it
    rather than silently subtracting."""
    w1, w2 = _week(1), _week(2)
    alice = _member('alice')
    _result(w1, alice, 2.0, 2)
    _result(w2, alice, 8.0, 8)
    db.session.commit()
    _login(client, alice)

    html = client.get('/docket/ledger').data.decode()
    assert 'is-dropped' in html
    text = _text(html)
    assert 'struck from the record' in text
    assert _standings_cells(html)[0][2] == '8.0'   # 10.0 less the dropped 2.0


def test_the_drop_explains_itself_before_it_applies(app, client):
    w1 = _week(1)
    alice = _member('alice')
    _result(w1, alice, 6.0, 6)
    db.session.commit()
    _login(client, alice)

    text = _text(client.get('/docket/ledger').data.decode())
    assert 'The drop begins once a second week is graded' in text


def test_a_week_with_no_sheet_filed_states_its_charge(app, client):
    """The late-joiner rule made visible: 0 points and the week's default
    error, said out loud so it does not read as a bug."""
    week = _week(1, default_error_tenths=180)
    alice, ghost = _member('alice'), _member('ghost')
    _result(week, alice, 6.0, 6)
    db.session.commit()
    _login(client, ghost)

    text = _text(client.get('/docket/ledger').data.decode())
    assert 'no sheet filed, charged 18.0' in text


def test_current_user_row_is_tinted_not_striped(app, client):
    """The page emits the hook; the stylesheet decides the treatment. Asserting
    'border-left' not in html would pass unconditionally, since neither the
    tint nor a stripe can appear in rendered markup — so check the actual
    rule, scoped to it rather than sweeping the whole file."""
    import re
    from pathlib import Path

    week = _week(1)
    alice = _member('alice')
    _result(week, alice, 5.0, 5)
    db.session.commit()
    _login(client, alice)

    assert 'row-current-user' in client.get('/docket/ledger').data.decode()

    css = Path('static/css/style.css').read_text()
    rule = re.search(
        r'\.docket-ledger-table \.row-current-user\s*>\s*td\s*\{([^}]*)\}', css)
    assert rule, 'the ledger must scope its own current-user tint'
    body = rule.group(1)

    # The exact declaration, not a substring: 'background' alone would also be
    # satisfied by background-image or a custom property.
    assert re.search(
        r'(?<![-\w])background\s*:\s*'
        r'rgba\(\s*var\(--game-accent-rgb\)\s*,\s*\.09\s*\)\s*;',
        body), \
        'the highlight is the garnet tint at .09 (DESIGN.md 6.5: garnet ' \
        'means "yours"; 6.3 sets the tint recipe at 8-12%)'

    # Every way a side stripe could be spelled, shorthand and logical
    # properties included.
    for prop in ('border-left', 'border-right',
                 'border-inline-start', 'border-inline-end', 'border-inline'):
        assert not re.search(rf'\b{prop}\s*:', body), \
            f'{prop} is a side stripe; the platform Tables rule is tint only'
    assert not re.search(r'(?<![-\w])border\s*:', body), \
        'a border shorthand can set the side edges; tint only'


def test_verdict_banner_is_absent_until_the_season_is_complete(app, client):
    week = _week(1)
    alice = _member('alice')
    _result(week, alice, 5.0, 5)
    db.session.commit()
    _login(client, alice)

    assert 'docket-verdict-banner' not in \
        client.get('/docket/ledger').data.decode()


def test_verdict_banner_renders_once_every_week_is_graded(app, client):
    """The room's single ceremonial dark surface, and its only appearance."""
    from games.docket.services.weeks import TOTAL_WEEKS

    alice = _member('alice')
    for n in range(1, TOTAL_WEEKS + 1):
        _result(_week(n), alice, 5.0, 5)
    db.session.commit()
    _login(client, alice)

    html = client.get('/docket/ledger').data.decode()
    assert 'docket-verdict-banner' in html
    assert 'The record is closed' in _text(html)


def test_ledger_rejects_post(app, client):
    """The ledger writes nothing; the drop is derived on every read."""
    alice = _member('alice')
    db.session.commit()
    _login(client, alice)

    assert client.post('/docket/ledger').status_code == 405


def test_ledger_query_count_does_not_scale_with_the_roster(app, client):
    """The per-row avatar and display name must not each cost a query."""
    from sqlalchemy import event

    week = _week(1)
    for i in range(12):
        _result(week, _member(f'p{i:02d}'), float(i), i)
    viewer = _member('viewer')
    db.session.commit()
    _login(client, viewer)

    statements = []
    engine = db.engine

    def before(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', before)
    try:
        assert client.get('/docket/ledger').status_code == 200
    finally:
        event.remove(engine, 'before_cursor_execute', before)

    # Enrollments+users, week results, weeks, plus session/auth lookups. The
    # bound is deliberately loose; what it catches is per-row growth.
    assert len(statements) < 15, f'{len(statements)} queries for 13 members'


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def test_rules_is_public(app, client):
    """A prospective member reads the terms before joining."""
    resp = client.get('/docket/rules')
    assert resp.status_code == 200
    assert 'House Rules' in _text(resp.data.decode())


def test_scoring_table_is_read_from_the_engine(app, client):
    """Expectations computed here from the same function that grades, so a
    scoring change fails this test instead of drifting the page."""
    from games.docket.services.grading.engine import slot_points
    from games.docket.services.grading.snapshots import Outcome

    text = _text(client.get('/docket/rules').data.decode())
    for outcome, label in [(Outcome.WIN, 'A verdict (win)'),
                           (Outcome.PUSH, 'A mistrial (push)'),
                           (Outcome.LOSS, 'A loss')]:
        ordinary = f'{slot_points(outcome, doubled=False):g}'
        doubled = f'{slot_points(outcome, doubled=True):g}'
        assert f'{label} {ordinary} {doubled}' in text, label


def test_perfect_week_is_derived_not_a_literal(app, client):
    from games.docket.services.grading.engine import slot_points
    from games.docket.services.grading.snapshots import SCORING_SLOTS, Outcome

    expected = ((SCORING_SLOTS - 1) * slot_points(Outcome.WIN, doubled=False)
                + slot_points(Outcome.WIN, doubled=True))
    text = _text(client.get('/docket/rules').data.decode())
    assert f'A perfect week is {expected:g}' in text


def test_rules_states_the_week_count_from_the_week_math(app, client):
    """19 docket weeks, not the 18 an NFL-shaped guess would print."""
    from games.docket.services.weeks import TOTAL_WEEKS

    text = _text(client.get('/docket/rules').data.decode())
    assert f'{TOTAL_WEEKS} weeks' in text


def test_rules_states_d23_overtime_and_nfl_ties(app, client):
    """D23-eng says "on the rules page" in as many words."""
    text = _text(client.get('/docket/rules').data.decode())
    assert 'overtime included' in text
    assert 'An NFL tie' in text


def test_rules_publishes_the_bookmaker_order(app, client):
    """D17-eng: "policy published on the rules page"."""
    from games.docket.services.importer import (
        BOOKMAKER_LABELS,
        BOOKMAKER_PRIORITY,
    )

    text = _text(client.get('/docket/rules').data.decode())
    labels = [BOOKMAKER_LABELS.get(k, k) for k in BOOKMAKER_PRIORITY]
    assert ' '.join(labels) in text, 'books listed in priority order'


def test_rules_states_the_entry_fee_from_config(app, client):
    text = _text(client.get('/docket/rules').data.decode())
    fee = app.config.get('DOCKET_ENTRY_FEE', 25)
    assert f'${fee}' in text


def test_rules_states_the_three_keys_and_the_points_only_drop(app, client):
    text = _text(client.get('/docket/rules').data.decode())
    assert 'Key 1, points' in text
    assert 'Key 2, wins' in text
    assert 'Key 3, the error account' in text
    assert 'The drop forgives points only' in text


# ---------------------------------------------------------------------------
# The purse (rulings Amendments 2026-09-03): every dollar derived, never typed
# ---------------------------------------------------------------------------

def _roster(n):
    return [_member(f'p{i:02d}') for i in range(n)]


def _verdict_rows(html):
    start = html.find('class="docket-verdicts"')
    end = html.find('class="docket-entries"')
    assert start != -1 and end != -1 and start < end
    return re.findall(r'<li class="docket-verdict[^"]*">(.*?)</li>',
                      html[start:end], re.S)


def test_ledger_states_the_purse_before_any_week_grades(app, client):
    members = _roster(18)
    db.session.commit()
    _login(client, members[0])

    html = client.get('/docket/ledger').data.decode()
    assert 'docket-purse-line' in html
    text = _text(html)
    assert 'first $455, second $175, third $70' in text
    assert '$20 to each week' in text
    assert '/docket/rules#rules-season' in html
    assert 'docket-verdicts' not in html


def test_weekly_verdicts_name_each_weeks_top_sheet(app, client):
    week1, week2 = _week(1), _week(2)
    alice, bob = _member('alice'), _member('bob')
    _result(week1, alice, 7.5, 7, 40)
    _result(week1, bob, 4.0, 4)
    _result(week2, alice, 3.0, 3)
    _result(week2, bob, 6.0, 6, 120)
    db.session.commit()
    _login(client, alice)

    html = client.get('/docket/ledger').data.decode()
    assert 'The weekly verdicts' in _text(html)
    rows = _verdict_rows(html)
    assert len(rows) == 2
    first, second = _text(rows[0]), _text(rows[1])
    assert first.startswith('W1')
    assert 'alice' in first and '7.5' in first
    assert '7 wins, off by 4.0' in first
    assert '$20' in first
    assert second.startswith('W2') and 'bob' in second
    # The platform integration point: the avatar precedes the name.
    assert rows[0].find('docket-ledger-avatar') < rows[0].find('alice')
    # The receipt in each drawer: one tag per winning week, on the week won.
    tags = re.findall(r'<span class="docket-week-verdict">(.*?)</span>', html)
    assert [t.strip() for t in tags] == ['$20', '$20']


def test_a_level_week_splits_the_prize_out_loud(app, client):
    week = _week(1)
    zed, amy = _member('zed'), _member('amy')
    _result(week, zed, 7.0, 7, 15)
    _result(week, amy, 7.0, 7, 15)
    db.session.commit()
    _login(client, amy)

    html = client.get('/docket/ledger').data.decode()
    (row,) = _verdict_rows(html)
    text = _text(row)
    # Both names, in display-name order, each behind its avatar.
    assert text.index('amy') < text.index(' and ') < text.index('zed')
    assert 'split $20' in text
    tags = re.findall(r'<span class="docket-week-verdict">(.*?)</span>', html)
    assert [t.strip() for t in tags] == ['split $20', 'split $20']


def test_verdict_banner_carries_the_first_prize(app, client):
    from games.docket.services.weeks import TOTAL_WEEKS

    members = _roster(18)
    alice = members[0]
    for n in range(1, TOTAL_WEEKS + 1):
        _result(_week(n), alice, 5.0, 5)
    db.session.commit()
    _login(client, alice)

    text = _text(client.get('/docket/ledger').data.decode())
    assert 'The record is closed' in text
    assert 'First prize, $455.' in text


def test_rules_states_the_purse_from_the_roster_and_config(app, client):
    _roster(18)
    db.session.commit()

    text = _text(client.get('/docket/rules').data.decode())
    assert '$20 to the week' in text
    assert '19 weeks' in text
    assert '18 members' in text
    assert '$1,080' in text and '$380' in text and '$700' in text
    assert 'first 65% ($455), second 25% ($175), third 10% ($70)' in text
    assert "Commissioner's call" in text
    assert 'How the pot is divided' not in text


def test_rules_purse_follows_a_config_change(app, client, monkeypatch):
    """No literal anywhere: flip the config and the page follows."""
    _roster(10)
    db.session.commit()
    monkeypatch.setitem(app.config, 'DOCKET_ENTRY_FEE', 50)
    monkeypatch.setitem(app.config, 'DOCKET_WEEKLY_PRIZE', 10)
    monkeypatch.setitem(app.config, 'DOCKET_PODIUM_SPLIT', (50, 30, 20))

    text = _text(client.get('/docket/rules').data.decode())
    assert '$10 to the week' in text
    assert '10 members' in text and '$500' in text and '$190' in text
    assert 'first 50% ($155), second 30% ($93), third 20% ($62)' in text
