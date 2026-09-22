"""The Docket record letter (Club Desk step 1, docs/designs/unified-email.md).

Every Docket member gets "here is your record for the week" once the week
grades: a personal Club Letter built from facts the room already shows
(the sheet's tally, the week standings, the season ledger, the purse).
It is latch-driven (``DocketWeek.record_notified``) from the daily scores
run ONLY: never the game-day pass (ADR-063 sends no mail), never a regrade.
Assertions are on captured RENDERED letters, not a mocked builder.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from extensions import db
from games.docket.models import DocketPick, DocketWeek
from games.docket.services import gameday as docket_gameday
from games.docket.services import record
from games.docket.services import scores as docket_scores
from games.docket.services.deadline_pass import run_deadline_pass
from games.docket.services.enrollment import roster_user_ids_as_of
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.record import (
    TopSheet,
    ordinal,
    record_letter,
    run_record_pass,
)
from games.docket.services.sheets import Tally
from games.docket.services.weeks import TOTAL_WEEKS
from tests._docket_fixtures import (
    at,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)
from utils.email_layout import render_letter

REPO = Path(__file__).resolve().parent.parent
SITE = 'https://cccfantasy.com'
# Week 1 closes Sun Sep 6 12:00 CT = 17:00 UTC; every case kicks off after.
AFTER_DEADLINE = '2026-09-06T17:30:00'
KICK = datetime(2026, 9, 6, 18, 0)
SCORING_SLOTS = 8
SEND = 'games.docket.services.notifications.send_platform_email'


def _capture():
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'plain': plain,
                      'html': html})
        return True

    return calls, patch(SEND, side_effect=fake)


def _pick(user, week, game, slot, side, *, best=False):
    db.session.add(DocketPick(
        user_id=user.id, week_id=week.id, game_id=game.id, market='spread',
        side=side, slot=slot, is_best=best, line_value=game.home_spread,
        book='draftkings'))


def _seed(monkeypatch, sheets, *, week_number=1):
    """A graded Week 1: eight final cases the home side covers, one member
    per ``(username, display_name, wins)`` with the first ``wins`` slots on
    the home side (the x2 on slot 1), the rest on the away side; ``wins``
    None means no sheet at all (the deadline pass files it). Deadline pass,
    then grade, both through the real services.
    """
    week = make_week(week_number)
    games = [make_game(week, kickoff=KICK, home=f'Home {i}', away=f'Away {i}',
                       home_spread=-3.5, total=40.5 + i)
             for i in range(SCORING_SLOTS)]
    for game in games:
        game.home_score, game.away_score, game.is_final = 31, 17, True
    week.tiebreaker_game_id = games[0].id
    users = {}
    for username, display_name, wins in sheets:
        user = make_user(username)
        make_enrollment(user, display_name=display_name)
        users[username] = user
        if wins is None:
            continue
        for slot in range(1, SCORING_SLOTS + 1):
            _pick(user, week, games[slot - 1],
                  slot, 'home' if slot <= wins else 'away', best=(slot == 1))
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)
    run_deadline_pass(week_number)
    graded = try_grade_week(
        week.id, user_ids=roster_user_ids_as_of(week.deadline_at))
    assert graded['status'] == 'ok', graded
    return week, users


ROSTER = (('dana', 'Dana Whitfield', 7),
          ('clerk', 'Clerk of Court', 6),
          ('ghost', 'Ghost Gary', 0))


# ── the pure builder ──────────────────────────────────────────────────────

def test_ordinals():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31)] == \
        ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd',
         '23rd', '31st']


def _letter(**overrides):
    fields = {
        'week_number': 3, 'display_name': 'Clerk of Court',
        'tally': Tally(6, 2, 0, 0), 'points': 7.0, 'week_rank': 4,
        'roster_size': 31, 'season_rank': 9, 'season_points': 19.5,
        'top_sheet': TopSheet(names=('Dana Whitfield',), record='7-1',
                              split=False),
        'is_winner': False, 'weekly_prize': 20, 'autopicked': False,
        'ledger_url': f'{SITE}/docket/ledger',
    }
    return record_letter(**{**fields, **overrides})


def test_record_letter_is_the_approved_shape(app):
    app.config['SITE_URL'] = SITE
    letter = _letter()
    assert letter.subject == 'Your record: The Docket, Week 3'
    assert len(letter.subject) <= 45
    assert letter.headline == 'Week 3: 6-2'
    assert letter.eyebrow == 'The Docket · Week 3'
    assert letter.game_slug == 'docket'
    assert letter.greeting == 'Clerk of Court'
    assert letter.facts == [('Week 3', '6-2 · 7 points'),
                            ('On the week', '4th of 31'),
                            ('Season', '9th · 19.5 points')]
    assert letter.cta == ('See the ledger', f'{SITE}/docket/ledger')
    assert letter.supporting == ['The Week 4 docket opens Tuesday morning.']
    plain, html = render_letter(letter)
    assert ('Around the docket\nTop sheet: Dana Whitfield, 7-1\n'
            'Weekly purse: $20 to Dana Whitfield') in plain
    assert 'Hardest case' not in plain
    assert '—' not in plain and 'CDT' not in plain
    assert html.count('class="cta"') == 1


@pytest.mark.parametrize('tally, points, headline, fact', [
    (Tally(0, 8, 0, 0), 0.0, 'Week 3: 0-8', '0-8 · 0 points'),
    (Tally(8, 0, 0, 0), 9.0, 'Week 3: 8-0', '8-0 · 9 points'),
    (Tally(6, 1, 1, 0), 7.5, 'Week 3: 6-1-1', '6-1-1 · 7.5 points'),
    (Tally(1, 7, 0, 0), 1.0, 'Week 3: 1-7', '1-7 · 1 point'),
])
def test_records_are_digits_with_no_consolation_or_celebration(
        tally, points, headline, fact):
    letter = _letter(tally=tally, points=points)
    assert letter.headline == headline
    assert letter.facts[0] == ('Week 3', fact)
    assert letter.lede == ['The Week 3 docket is closed and every case is '
                           'decided.']


def test_top_sheet_reads_you_when_the_recipient_won():
    letter = _letter(is_winner=True, top_sheet=TopSheet(
        names=('Clerk of Court',), record='8-0', split=False))
    rows = letter.extras[0].plain
    assert 'Top sheet: You, 8-0' in rows
    assert 'Weekly purse: $20 to you' in rows


def test_a_tie_for_top_sheet_says_the_purse_is_split():
    letter = _letter(top_sheet=TopSheet(
        names=('Ann', 'Bob', 'Cy'), record='7-1', split=True))
    rows = letter.extras[0].plain
    assert 'Top sheet: 3 sheets at 7-1; the purse is split' in rows
    assert 'Weekly purse: $20 split 3 ways' in rows


def test_an_autopicked_sheet_opens_with_the_filed_line():
    letter = _letter(autopicked=True)
    assert letter.lede[0] == 'Your sheet was filed from the locked lines.'


def test_the_final_week_promises_no_next_docket():
    assert _letter(week_number=TOTAL_WEEKS).supporting == []


# ── the pass ──────────────────────────────────────────────────────────────

def test_pass_sends_every_graded_member_once_and_latches(app, monkeypatch):
    app.config['SITE_URL'] = SITE
    week, users = _seed(monkeypatch, ROSTER)
    sent, patcher = _capture()
    with patcher:
        outcome = run_record_pass()
    assert outcome == [{'week_number': 1, 'recipients': 3, 'sent': 3,
                        'latched': True}]
    assert week.record_notified is True

    by_to = {m['to']: m for m in sent}
    assert set(by_to) == {'dana@test.com', 'clerk@test.com',
                          'ghost@test.com'}
    for m in sent:
        assert m['subject'] == 'Your record: The Docket, Week 1'
        assert m['html'].count('class="cta"') == 1
        assert f'See the ledger: {SITE}/docket/ledger' in m['plain']

    # Dana: 7-1 with the x2 on a win = 8 points, the week's top sheet.
    dana = by_to['dana@test.com']['plain']
    assert 'Hi Dana Whitfield,' in dana
    assert 'Week 1: 7-1\n' in dana
    assert 'Week 1: 7-1 · 8 points\nOn the week: 1st of 3\nSeason: 1st · 8 points' in dana
    assert 'Top sheet: You, 7-1\nWeekly purse: $20 to you' in dana
    # Clerk: 6-2, 7 points, second on the week and the season.
    clerk = by_to['clerk@test.com']['plain']
    assert 'Week 1: 6-2 · 7 points\nOn the week: 2nd of 3\nSeason: 2nd · 7 points' in clerk
    assert 'Top sheet: Dana Whitfield, 7-1\nWeekly purse: $20 to Dana Whitfield' in clerk
    assert 'Your sheet was filed' not in clerk
    # Ghost: 0-8, no consolation copy.
    ghost = by_to['ghost@test.com']['plain']
    assert 'Week 1: 0-8\n' in ghost
    assert 'Week 1: 0-8 · 0 points\nOn the week: 3rd of 3' in ghost

    # The second run has nothing pending.
    sent.clear()
    with patcher:
        assert run_record_pass() == []
    assert sent == []


def test_a_regrade_after_the_send_issues_no_correction(app, monkeypatch):
    week, _users = _seed(monkeypatch, ROSTER)
    sent, patcher = _capture()
    with patcher:
        run_record_pass()
    assert len(sent) == 3
    sent.clear()

    # Scores change under the graded week; a recalc re-grades it.
    game = week.games[0]
    game.home_score, game.away_score = 10, 24
    db.session.commit()
    regraded = try_grade_week(
        week.id, user_ids=roster_user_ids_as_of(week.deadline_at))
    assert regraded['status'] == 'ok'
    with patcher:
        assert run_record_pass() == []
    assert sent == []
    assert week.record_notified is True


def test_zero_deliveries_leaves_the_latch_open_for_the_next_run(
        app, monkeypatch):
    week, _users = _seed(monkeypatch, ROSTER)
    with patch(SEND, return_value=False):
        outcome = run_record_pass()
    assert outcome == [{'week_number': 1, 'recipients': 3, 'sent': 0,
                        'latched': False}]
    assert week.record_notified is False

    sent, patcher = _capture()
    with patcher:
        outcome = run_record_pass()
    assert outcome[0]['latched'] is True and len(sent) == 3
    assert week.record_notified is True


def test_an_ungraded_week_is_skipped(app, monkeypatch):
    week = make_week(1)
    make_game(week, kickoff=KICK)
    make_enrollment(make_user('player'))
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)
    sent, patcher = _capture()
    with patcher:
        assert run_record_pass() == []
    assert sent == [] and week.record_notified is False


def test_a_week_of_all_autopick_sheets_renders(app, monkeypatch):
    app.config['SITE_URL'] = SITE
    _week, _users = _seed(monkeypatch, (('one', 'Auto One', None),
                                        ('two', 'Auto Two', None)))
    assert db.session.query(DocketPick).filter_by(is_autopick=True).count() > 0
    sent, patcher = _capture()
    with patcher:
        outcome = run_record_pass()
    assert outcome[0]['sent'] == 2
    for m in sent:
        assert 'Your sheet was filed from the locked lines.' in m['plain']
        assert m['html'].count('class="cta"') == 1


# ── who may send it ───────────────────────────────────────────────────────

def test_the_game_day_pass_never_sends_a_record(app, monkeypatch):
    """ADR-063: the game-day consumer grades but sends no mail. The record
    is the daily scores run's alone."""
    week, _users = _seed(monkeypatch, ROSTER)
    week.default_error_tenths = None      # ungraded again, one case open
    game = week.games[0]
    game.is_final = False
    db.session.commit()
    at(monkeypatch, '2026-09-06T23:00:00')
    events = {game.sport: [{
        'id': game.api_event_id, 'home_team': game.home_team,
        'away_team': game.away_team, 'completed': True,
        'scores': [{'name': game.home_team, 'score': '31'},
                   {'name': game.away_team, 'score': '17'}]}]}
    with patch.object(docket_scores, 'odds_api_get'), \
            patch.object(record, 'send_record_letters') as sender, \
            patch.object(record, 'run_record_pass') as pass_:
        result = docket_gameday.CONSUMER.apply(events)
    assert result[1]['grade']['status'] == 'ok'
    assert week.default_error_tenths is not None
    assert not sender.called and not pass_.called
    assert week.record_notified is False


def test_only_the_scores_cli_path_reaches_the_record_pass():
    """Source lock: the sender is wired into the CLI's scores mode and
    nowhere else — not the grading pass, the game-day consumer, the admin
    desk, or recalc."""
    for rel in ('games/docket/services/grading_pass.py',
                'games/docket/services/gameday.py',
                'games/docket/services/admin_ops.py',
                'games/gameday.py'):
        source = (REPO / rel).read_text()
        assert 'services.record' not in source, rel
        assert 'run_record_pass' not in source, rel
        assert 'send_record_letters' not in source, rel
    cli = (REPO / 'games/docket/cli.py').read_text()
    assert cli.count('run_record_pass()') == 1
    assert 'run_record_pass()' in cli[cli.index('def _send_records'):
                                     cli.index('def _run_scores')]
    assert '_send_records()' in cli[cli.index('def _run_scores'):
                                    cli.index('def _run_deadline')]
    assert '_send_records()' not in cli[cli.index('def recalc_cmd'):]


def test_scores_mode_mails_the_record_once_the_week_grades(
        app, monkeypatch):
    app.config['SITE_URL'] = SITE
    app.config['ODDS_API_KEY'] = 'test-key'
    week, _users = _seed(monkeypatch, ROSTER)
    # Undo the grade so the CLI's own scores run is what grades it.
    week.default_error_tenths = None
    db.session.commit()
    from games.docket.cli import docket_cli

    class _R:
        status_code = 200
        headers = {}  # noqa: RUF012 - throwaway stub

        def json(self):
            return []

    sent, patcher = _capture()
    with patcher, patch.object(docket_scores, 'odds_api_get',
                               return_value=_R()):
        result = app.test_cli_runner().invoke(
            docket_cli, ['sync', '--mode', 'scores'])
    assert result.exit_code == 0, result.output
    assert '3 players graded' in result.output
    assert 'record: week 1 sent to 3/3 sheets' in result.output
    assert len(sent) == 3
    assert db.session.get(DocketWeek, week.id).record_notified is True

    # A second daily run grades nothing new and mails nothing.
    sent.clear()
    with patcher, patch.object(docket_scores, 'odds_api_get',
                               return_value=_R()):
        result = app.test_cli_runner().invoke(
            docket_cli, ['sync', '--mode', 'scores'])
    assert result.exit_code == 0, result.output
    assert 'record:' not in result.output
    assert sent == []


def test_scores_mode_still_mails_records_when_the_current_sport_errors(
        app, monkeypatch):
    """A dark current-week sport fails the run, but a week already graded and
    unnotified still gets its record before the non-zero exit — the daily
    scores run is the only sender, so the error branch must send too."""
    app.config['ODDS_API_KEY'] = 'test-key'
    week, _users = _seed(monkeypatch, ROSTER)
    from games.docket import cli as docket_cli_mod
    from games.docket.cli import docket_cli

    sent, patcher = _capture()
    with patcher, patch.object(
            docket_cli_mod, 'sync_scores',
            return_value={'status': 'error', 'errors': ['dark sport']}):
        result = app.test_cli_runner().invoke(
            docket_cli, ['sync', '--mode', 'scores'])
    assert result.exit_code == 1, result.output
    assert 'record: week 1 sent to 3/3 sheets' in result.output
    assert len(sent) == 3
    assert db.session.get(DocketWeek, week.id).record_notified is True


def test_scores_mode_reports_an_unlatched_record_without_failing(
        app, monkeypatch):
    app.config['ODDS_API_KEY'] = 'test-key'
    week, _users = _seed(monkeypatch, ROSTER)
    from games.docket.cli import docket_cli

    class _R:
        status_code = 200
        headers = {}  # noqa: RUF012 - throwaway stub

        def json(self):
            return []

    with patch(SEND, return_value=False), \
            patch.object(docket_scores, 'odds_api_get', return_value=_R()):
        result = app.test_cli_runner().invoke(
            docket_cli, ['sync', '--mode', 'scores'])
    assert result.exit_code == 0, result.output
    assert 'record: week 1 sent to 0/3 sheets; not latched' in result.output
    assert week.record_notified is False


def test_a_graded_week_with_an_empty_roster_latches_with_nobody_to_write_to(
        app, monkeypatch):
    """ADR-047: a week with nobody enrolled at its deadline still stamps its
    marker. There is no record to send, so the latch closes rather than
    alerting on every daily run."""
    week = make_week(1)
    game = make_game(week, kickoff=KICK)
    game.home_score, game.away_score, game.is_final = 31, 17, True
    week.tiebreaker_game_id = game.id
    db.session.commit()
    at(monkeypatch, AFTER_DEADLINE)
    run_deadline_pass(1)
    assert try_grade_week(week.id, user_ids=[])['status'] == 'ok'
    sent, patcher = _capture()
    with patcher:
        assert run_record_pass() == [{'week_number': 1, 'recipients': 0,
                                      'sent': 0, 'latched': True}]
    assert sent == [] and week.record_notified is True
