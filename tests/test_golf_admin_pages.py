"""The Back Office (Golf Phase U6): the commissioner's pages on the sheet primitives.

The five admin templates are leaves of one book on the room's paper
(games/golf/DESIGN.md §8.20 to §8.24): the same `.golf-*` primitives as the
member pages, none of the pre-U markup, every JS hook of §7.15 kept, and one
new mark, the meter. These tests read the templates' source and the rendered
pages.
"""
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfTournament,
    GolfTournamentField,
)
from models.user import User

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / 'games/golf/templates/golf/admin'
PAGES = ['dashboard.html', 'tournaments.html', 'users.html', 'payments.html',
         'override_pick.html', '_book.html']


def _user(username, is_admin=False, display_name=None):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin,
             display_name=display_name)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _enroll(user, season, **kw):
    e = GolfEnrollment(user_id=user.id, season_year=season, **kw)
    db.session.add(e)
    db.session.commit()
    return e


def _event(season, name, week, days_ago, status='complete', finalized=True, is_major=False):
    now = datetime.now(UTC)
    t = GolfTournament(
        api_tourn_id=f'T-{week}', name=name, season_year=season, week_number=week,
        start_date=now - timedelta(days=days_ago), end_date=now - timedelta(days=days_ago - 3),
        pick_deadline=now - timedelta(days=days_ago), purse=9_000_000,
        is_major=is_major, status=status, results_finalized=finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ============================================================================
# Template source
# ============================================================================

@pytest.mark.parametrize('name', PAGES)
def test_admin_templates_carry_no_pre_u_markup(name):
    source = (ADMIN / name).read_text()
    for retired in ('table-golf', 'row-leader', 'col-divider', 'page-hero', 'hero-glow',
                    'stat-block', 'stat-value', 'row-current-user', 'badge bg-', 'bi bi-',
                    'text-gold', 'text-muted', 'form-select', 'form-control', 'form-check',
                    'list-group', 'admin-badge', 'animate-in', 'alert alert-', 'btn-warning',
                    'btn-danger', 'btn-outline-secondary', 'ts-select', 'tom-select', 'cdn.',
                    '//'):
        assert retired not in source, f'{name} still carries {retired!r}'
    assert not re.search(r'class="(?:[^"]* )?card(?:-[a-z-]+)?[ "]', source)
    # The only inline styles are the shares the server computed.
    assert all(style.startswith('--') for style in re.findall(r'style="([^"]*)"', source))
    assert not re.search(r'eyebrow', source)
    # Copy discipline: no em dashes or double hyphens in the room's copy.
    assert '—' not in source and ' -- ' not in source


def test_the_js_hooks_are_kept():
    """DESIGN.md §7.15: the payments and override scripts' hooks survive the
    restyle, and the toggle reads its chip by its own hook, never `.badge`."""
    payments = (ADMIN / 'payments.html').read_text()
    users = (ADMIN / 'users.html').read_text()
    pen = (ADMIN / 'override_pick.html').read_text()
    for page in (payments, users):
        assert 'class="payment-toggle"' in page or 'payment-toggle' in page
        assert 'data-user-id="{{ e.user_id }}"' in page
        assert 'js-paid-status' in page
        assert "querySelector('.badge')" not in page
        assert 'meta[name="csrf-token"]' in page
    assert 'class="penalty-group' in payments
    assert 'penalty-input' in payments and 'penalty-save' in payments
    for hook in ('id="tournament_id"', 'id="user_id"', 'id="primary_player_id"',
                 'id="backup_player_id"', 'name="override_note"', 'id="override_note"'):
        assert hook in pen, hook


def test_every_leaf_opens_the_same_book():
    """Each page is a leaf of one book: the H1 in the room's title, the
    context line, and the book line naming the five pages."""
    for name in PAGES[:-1]:
        source = (ADMIN / name).read_text()
        assert 'golf-title golf-title--page' in source, name
        assert 'class="golf-context"' in source, name
        assert "{% include 'golf/admin/_book.html' %}" in source, name


# ============================================================================
# The rendered book
# ============================================================================

def test_dashboard_reads_the_meter_from_the_log(app, client, tmp_path, monkeypatch):
    """The reads ledger: the month's count against the free tier, the hatch
    as wide as the share spent, what is left and the last read, in words."""
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('GOLF_FAKE_NOW', '2026-04-16T17:00:00')
    lines = [
        f'2026-04-{2 + i // 10:02d} 17:00:00,000\tcount={i}\tmode=free\tendpoint=leaderboard'
        f'\tstatus=200\tattempt=1\tduration=0.40s\tparams={{}}\n'
        for i in range(112)
    ]
    (tmp_path / 'api_calls.log').write_text(''.join(lines))
    _login(client, _user('padmin', is_admin=True))

    body = client.get('/golf/admin/').get_data(as_text=True)

    assert '112 of 250 reads this month' in body
    assert '--have: 45%' in body
    assert '138 left' in body
    assert 'Last read' in body and 'CT' in body
    assert 'leaderboard 112' in body
    assert 'April 2026' in body


def test_dashboard_meter_warns_in_words_past_four_fifths(app, client, tmp_path, monkeypatch):
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path))
    monkeypatch.setenv('GOLF_FAKE_NOW', '2026-04-16T17:00:00')
    (tmp_path / 'api_calls.log').write_text(''.join(
        f'2026-04-10 17:00:00,000\tcount={i}\tmode=free\tendpoint=leaderboard\tstatus=200\t'
        f'attempt=1\tduration=0.40s\tparams={{}}\n' for i in range(230)))
    _login(client, _user('padmin', is_admin=True))
    body = client.get('/golf/admin/').get_data(as_text=True)
    assert 'Four fifths of the month' in body
    assert '20 left' in body


def test_dashboard_leads_with_what_needs_settling(app, client, tmp_path, monkeypatch):
    """The first ledger: played events not yet banked, Process on each row;
    the tab's three figures; nothing of the platform's user count."""
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path / 'none'))
    season = app.config['SEASON_YEAR']
    admin = _user('padmin', is_admin=True)
    paid = _user('paid', display_name='Casey Paid')
    _enroll(paid, season, has_paid=True)
    owes = _user('owes', display_name='Dana Owes')
    _enroll(owes, season, has_paid=False)
    _user('stranger', display_name='Morgan Stranger')
    _event(season, 'Sony Open in Hawaii', 1, 60)
    rbc = _event(season, 'RBC Heritage', 16, 4, finalized=False)
    _login(client, admin)

    body = client.get('/golf/admin/').get_data(as_text=True)

    assert 'The Back Office' in body
    assert '1 of 2 events banked' in body
    assert body.index('To settle') < body.index('The tab') < body.index('The reads')
    assert 'RBC Heritage' in body
    assert f'/golf/admin/process-results/{rbc.id}' in body
    assert 'Sony Open in Hawaii' not in body.split('The tab')[0].split('To settle')[1]
    assert 'Paid' in body and '1 <span class="golf-tiles-note">of 2</span>' in body
    assert 'Morgan Stranger' not in body
    assert 'No reads yet this month' in body


def test_dashboard_with_nothing_to_settle_says_so(app, client, tmp_path, monkeypatch):
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path / 'none'))
    _login(client, _user('padmin', is_admin=True))
    body = client.get('/golf/admin/').get_data(as_text=True)
    assert 'the schedule is not posted yet' in body
    assert 'Nothing to settle' in body


def test_settle_the_book_lists_the_season_with_its_states(app, client):
    season = app.config['SEASON_YEAR']
    _login(client, _user('padmin', is_admin=True))
    banked = _event(season, 'Sony Open in Hawaii', 1, 60)
    played = _event(season, 'RBC Heritage', 16, 4, finalized=False)
    live = _event(season, 'Masters Tournament', 15, 1, status='active', finalized=False,
                  is_major=True)
    p = GolfPlayer(api_player_id='P1', first_name='Scottie', last_name='Scheffler')
    db.session.add(p)
    db.session.commit()
    db.session.add(GolfTournamentField(tournament_id=live.id, player_id=p.id))
    db.session.commit()

    body = client.get('/golf/admin/tournaments').get_data(as_text=True)

    assert 'Settle the Book' in body
    assert '1 to settle' in body
    assert f'/golf/admin/process-results/{played.id}' in body
    assert f'/golf/admin/process-results/{banked.id}' not in body
    assert 'Banked' in body and 'On the course' in body
    assert 'Major ×1.5' in body
    assert '1 in the field' in body
    assert f'href="/golf/tournament/{live.id}"' in body


def test_the_roster_and_the_tab_carry_the_chip_and_the_check(app, client):
    season = app.config['SEASON_YEAR']
    admin = _user('padmin', is_admin=True, display_name='The Commish')
    _enroll(admin, season, has_paid=True)
    member = _user('member', display_name='Casey Member')
    _enroll(member, season, has_paid=False, total_points=1_234_567)
    _login(client, admin)

    roster = client.get('/golf/admin/users').get_data(as_text=True)
    assert 'The Roster' in roster
    assert '$1,234,567' in roster
    assert f'href="/golf/member/{member.id}"' in roster
    assert 'golf-chip js-paid-status golf-chip--deduction">Unpaid' in roster
    assert 'golf-chip js-paid-status">Paid' in roster
    assert f'class="payment-toggle" type="checkbox" data-user-id="{member.id}"' in roster
    assert 'Commish</span>' in roster

    tab = client.get('/golf/admin/payments').get_data(as_text=True)
    assert 'The Tab' in tab
    assert '1 <span class="golf-tiles-note">of 2</span>' in tab
    assert 'golf-chip js-paid-status golf-chip--deduction">Unpaid' in tab


def test_the_pen_renders_the_field_as_real_selects(app, client):
    season = app.config['SEASON_YEAR']
    admin = _user('padmin', is_admin=True)
    member = _user('member', display_name='Casey Member')
    _enroll(member, season)
    t = _event(season, 'RBC Heritage', 16, -3, status='upcoming', finalized=False)
    a = GolfPlayer(api_player_id='A', first_name='Alpha', last_name='One')
    b = GolfPlayer(api_player_id='B', first_name='Bravo', last_name='Two')
    db.session.add_all([a, b])
    db.session.commit()
    db.session.add_all([GolfTournamentField(tournament_id=t.id, player_id=a.id),
                        GolfTournamentField(tournament_id=t.id, player_id=b.id)])
    db.session.commit()
    _login(client, admin)

    body = client.get(f'/golf/admin/override-pick?tournament_id={t.id}&user_id={member.id}'
                      ).get_data(as_text=True)

    assert "The Commish's Pen" in body
    assert 'class="golf-select" id="primary_player_id"' in body
    assert 'class="golf-select" id="backup_player_id"' in body
    assert 'Alpha One' in body and 'Bravo Two' in body
    assert 'Write the override' in body
    assert 'No overrides yet' in body
    assert 'tom-select' not in body.lower()

    pick = GolfPick(user_id=member.id, tournament_id=t.id, primary_player_id=a.id,
                    backup_player_id=b.id, admin_override=True, admin_override_note='late entry')
    db.session.add(pick)
    db.session.commit()
    body = client.get('/golf/admin/override-pick').get_data(as_text=True)
    assert '1 override this season' in body
    assert '“late entry”' in body
