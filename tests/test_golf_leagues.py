"""The Pay Sheet's two leagues (ADR-075): the spec lock for the whole change.

Golf is one game with two leagues inside it, Handicap (the house league) and
Pollyanna. Each league is a row in ``golf_league`` carrying its own entry fee
and penalty; every enrollment, pick and golfer usage belongs to exactly one.
"""
import re
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

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
from games.golf.services.enrollment import admin_enroll, enrollments_for, get_enrollment
from games.golf.services.leagues import (
    house_league,
    league_by_slug,
    leagues,
    seed_leagues,
)
from models.user import User


def _user(username):
    user = User(username=username, email=f'{username}@example.com')
    user.set_password('x')
    db.session.add(user)
    db.session.commit()
    return user


def test_seed_leagues_is_idempotent_and_ordered(app):
    seed_leagues()
    seed_leagues()

    assert [league.slug for league in leagues()] == ['handicap', 'pollyanna']
    assert [league.name for league in leagues()] == ['Handicap Pay Sheet', 'Pollyanna Pay Sheet']
    assert house_league().slug == 'handicap'
    assert league_by_slug('pollyanna').ordinal == 2
    assert league_by_slug('nope') is None
    for league in leagues():
        assert league.entry_fee == 25
        assert league.penalty_per_incident == 15


def test_the_same_member_holds_a_line_in_both_leagues(app, golf_leagues):
    brad = _user('two_sheets')
    db.session.add_all([
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id, season_year=2027),
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['pollyanna'].id, season_year=2027),
    ])
    db.session.commit()

    db.session.add(GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id,
                                  season_year=2027))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


SEASON = 2027


def _event(name, is_major=False):
    now = datetime.now(UTC)
    event = GolfTournament(
        api_tourn_id=f'T-{name}', name=name, season_year=SEASON,
        start_date=now - timedelta(days=4), end_date=now - timedelta(days=1),
        pick_deadline=now - timedelta(days=4), purse=10_000_000,
        is_major=is_major, status='complete',
    )
    db.session.add(event)
    db.session.commit()
    return event


def _golfer(api_id, last):
    player = GolfPlayer(api_player_id=api_id, first_name='Pat', last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _pick(user, league, event, primary, backup):
    pick = GolfPick(user_id=user.id, league_id=league.id, tournament_id=event.id,
                    primary_player_id=primary.id, backup_player_id=backup.id)
    db.session.add(pick)
    db.session.commit()
    return pick


def _result(event, player, status='complete', earnings=100):
    db.session.add(GolfTournamentResult(
        tournament_id=event.id, player_id=player.id, status=status,
        rounds_completed=4, earnings=earnings, final_position='1'))
    db.session.commit()


def test_spending_a_golfer_in_one_league_leaves_him_unspent_in_the_other(app, golf_leagues):
    brad = _user('spender')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    first, second = _event('First Open'), _event('Second Open')
    scheffler, backup = _golfer('S1', 'Scheffler'), _golfer('S2', 'Backup')
    for event in (first, second):
        for player in (scheffler, backup):
            db.session.add(GolfTournamentField(tournament_id=event.id, player_id=player.id))
        _result(event, scheffler)
        _result(event, backup)
    db.session.commit()

    spent = _pick(brad, handicap, first, scheffler, backup)
    assert spent.resolve_pick() is True
    db.session.commit()

    other = _pick(brad, pollyanna, second, scheffler, backup)
    assert other.validate_availability(SEASON) == []
    same_line = GolfPick(user_id=brad.id, league_id=handicap.id, tournament_id=second.id,
                         primary_player_id=scheffler.id, backup_player_id=backup.id)
    assert any('primary' in e for e in same_line.validate_availability(SEASON))

    assert other.resolve_pick() is True
    db.session.commit()
    rows = GolfSeasonPlayerUsage.query.filter_by(user_id=brad.id, player_id=scheffler.id).all()
    assert sorted(r.league_id for r in rows) == sorted([handicap.id, pollyanna.id])


def test_clear_resolution_deletes_only_this_leagues_usage(app, golf_leagues):
    brad = _user('clearer')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    event = _event('Clear Open')
    scheffler, backup = _golfer('C1', 'Scheffler'), _golfer('C2', 'Backup')
    _result(event, scheffler)
    _result(event, backup)
    h_pick = _pick(brad, handicap, event, scheffler, backup)
    p_pick = _pick(brad, pollyanna, event, scheffler, backup)
    assert h_pick.resolve_pick() and p_pick.resolve_pick()
    db.session.commit()

    h_pick.clear_resolution(SEASON)
    db.session.commit()

    rows = GolfSeasonPlayerUsage.query.filter_by(user_id=brad.id, player_id=scheffler.id).all()
    assert [r.league_id for r in rows] == [pollyanna.id]


def test_total_points_and_penalty_are_per_line(app, golf_leagues):
    brad = _user('liner')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    pollyanna.penalty_per_incident = 20
    db.session.commit()
    major = _event('The Major', is_major=True)
    a, b, c, d = (_golfer(f'L{i}', f'Last{i}') for i in range(4))
    _result(major, a, status='cut', earnings=0)
    _result(major, b, status='complete', earnings=200)
    _result(major, c, status='cut', earnings=0)
    _result(major, d, status='complete', earnings=50)
    h_pick = _pick(brad, handicap, major, a, b)
    p_pick = _pick(brad, pollyanna, major, c, d)
    assert h_pick.resolve_pick() and p_pick.resolve_pick()
    assert h_pick.penalty_triggered and p_pick.penalty_triggered
    minor = _event('The Minor')
    e, f = _golfer('L8', 'Last8'), _golfer('L9', 'Last9')
    _result(minor, e, earnings=500)
    _result(minor, f, earnings=40)
    h_minor = _pick(brad, handicap, minor, e, f)
    p_minor = _pick(brad, pollyanna, minor, f, e)
    assert h_minor.resolve_pick() and p_minor.resolve_pick()
    h_line = GolfEnrollment(user_id=brad.id, league_id=handicap.id, season_year=SEASON)
    p_line = GolfEnrollment(user_id=brad.id, league_id=pollyanna.id, season_year=SEASON)
    db.session.add_all([h_line, p_line])
    db.session.commit()

    h_line.calculate_total_points()
    p_line.calculate_total_points()
    assert (h_line.total_points, p_line.total_points) == (500, 40)
    assert h_line.penalty_owed() == 15
    assert p_line.penalty_owed() == 20
    assert len(h_line.get_used_player_ids()) == 2
    assert len(p_line.get_used_player_ids()) == 2


def test_get_enrollment_without_a_league_is_the_house_line_first(app, golf_leagues):
    brad = _user('registry')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    season = app.config['SEASON_YEAR']
    assert get_enrollment(brad.id) is None
    p_line = GolfEnrollment(user_id=brad.id, league_id=pollyanna.id, season_year=season)
    db.session.add(p_line)
    db.session.commit()
    assert get_enrollment(brad.id) == p_line
    h_line = GolfEnrollment(user_id=brad.id, league_id=handicap.id, season_year=season)
    db.session.add(h_line)
    db.session.commit()

    assert get_enrollment(brad.id) == h_line
    assert get_enrollment(brad.id, pollyanna) == p_line
    assert [e.league_id for e in enrollments_for(brad.id)] == [handicap.id, pollyanna.id]


def test_admin_enroll_seats_the_house_league(app, golf_leagues):
    brad = _user('seated')
    seated = admin_enroll(brad.id)
    assert seated.league_id == golf_leagues['handicap'].id
    assert admin_enroll(brad.id) == seated

    other = admin_enroll(brad.id, golf_leagues['pollyanna'])
    assert other.league_id == golf_leagues['pollyanna'].id
    assert admin_enroll(brad.id, golf_leagues['pollyanna']) == other
    assert GolfEnrollment.query.filter_by(user_id=brad.id).count() == 2


def test_the_other_leagues_picks_never_reach_a_leagues_aggregates(app, golf_leagues):
    from games.golf.services import stats

    season = app.config['SEASON_YEAR']
    handicap, pollyanna = golf_leagues['handicap'].id, golf_leagues['pollyanna'].id
    brad, cy = _user('brad_both'), _user('cy_pollyanna')
    scott = GolfPlayer(api_player_id='scott', first_name='Scottie', last_name='Scheffler')
    rory = GolfPlayer(api_player_id='rory', first_name='Rory', last_name='McIlroy')
    spare = GolfPlayer(api_player_id='spare', first_name='Spare', last_name='Guy')
    start = datetime(2026, 3, 5)
    event = GolfTournament(
        api_tourn_id='T-two', name='Players Championship', season_year=season,
        start_date=start, end_date=start + timedelta(days=3), pick_deadline=start,
        purse=10_000_000, status='complete', results_finalized=True, week_number=9,
    )
    db.session.add_all([scott, rory, spare, event])
    db.session.flush()
    db.session.add_all([
        GolfEnrollment(user_id=brad.id, league_id=handicap, season_year=season),
        GolfEnrollment(user_id=brad.id, league_id=pollyanna, season_year=season),
        GolfEnrollment(user_id=cy.id, league_id=pollyanna, season_year=season),
        GolfTournamentResult(tournament_id=event.id, player_id=scott.id, status='complete',
                             final_position='1', rounds_completed=4, earnings=100),
        GolfTournamentResult(tournament_id=event.id, player_id=rory.id, status='complete',
                             final_position='2', rounds_completed=4, earnings=500),
        GolfSeasonPlayerUsage(user_id=brad.id, league_id=handicap, player_id=scott.id,
                              season_year=season),
        GolfSeasonPlayerUsage(user_id=brad.id, league_id=pollyanna, player_id=rory.id,
                              season_year=season),
        GolfPick(user_id=brad.id, league_id=handicap, tournament_id=event.id,
                 primary_player_id=scott.id, backup_player_id=spare.id,
                 active_player_id=scott.id, points_earned=100, admin_override=True),
        GolfPick(user_id=brad.id, league_id=pollyanna, tournament_id=event.id,
                 primary_player_id=rory.id, backup_player_id=spare.id,
                 active_player_id=rory.id, points_earned=500, admin_override=True),
    ])
    db.session.commit()
    names = {brad.id: 'brad_both'}

    members, counts = stats._usage_counts(season, handicap)
    assert (members, counts) == (1, {scott.id: 1})
    assert stats.remaining_pct_map(season, handicap, [scott.id, rory.id]) == {
        scott.id: 0, rory.id: 100,
    }

    assert set(stats.spent_weeks(brad.id, handicap, season)) == {scott.id}

    race = stats.season_race(season, handicap, names)
    assert [(s['user_id'], s['final']) for s in race['series']] == [(brad.id, 100)]

    sup = stats.superlatives(season, handicap, names)
    assert (sup.pick_of_season.golfer.id, sup.pick_of_season.amount) == (scott.id, 100)

    form = stats.field_form(season, handicap)
    assert [row.player.id for row in form.still_on_board] == [rory.id]

    burn = stats.burn_list(season, handicap)
    assert [(row.player.id, row.times_used, row.total_return) for row in burn] == [
        (scott.id, 1, 100),
    ]

    tally = stats.override_tally(season, handicap, [event.id], names)
    assert [(row.user_id, row.count) for row in tally] == [(brad.id, 1)]


# --- Task A4: sync, letters and the import learn the league ------------------

def _season_event(app, name, *, status='complete', deadline_in=None):
    """An event in the configured season; ``deadline_in`` puts its lock that far
    ahead in league wall clock (the reminder pass reads it as CT)."""
    from games.golf.utils import GOLF_LEAGUE_TZ
    now = datetime.now(GOLF_LEAGUE_TZ).replace(tzinfo=None)
    deadline = now + deadline_in if deadline_in is not None else now - timedelta(days=4)
    event = GolfTournament(
        api_tourn_id=f'A4-{name}'[:20], name=name, season_year=app.config['SEASON_YEAR'],
        start_date=deadline, end_date=deadline + timedelta(days=3),
        pick_deadline=deadline, purse=10_000_000, status=status,
    )
    db.session.add(event)
    db.session.commit()
    return event


def _line(user, league, app, total=0):
    line = GolfEnrollment(user_id=user.id, league_id=league.id,
                          season_year=app.config['SEASON_YEAR'], total_points=total)
    db.session.add(line)
    db.session.commit()
    return line


def _mail_config(app):
    app.config.update(EMAIL_ADDRESS='commish@test.com', EMAIL_PASSWORD='x',
                      SITE_URL='https://cccfantasy.com')


def _capture_mail(monkeypatch):
    from games.golf.services import reminders
    sent = []

    def _send(to, subject, plain, html=None, *args, **kwargs):
        sent.append({'to': to, 'subject': subject, 'plain': plain, 'html': html})
        return True

    monkeypatch.setattr(reminders, 'send_platform_email', _send)
    return sent


def _usage_ids(user, league):
    return {u.player_id for u in GolfSeasonPlayerUsage.query.filter_by(
        user_id=user.id, league_id=league.id)}


def test_process_tournament_picks_retotals_each_line_separately(app, golf_leagues):
    from games.golf.services.sync import SlashGolfAPI, TournamentSync

    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    brad = _user('both_lines')
    h_line, p_line = _line(brad, handicap, app), _line(brad, pollyanna, app)
    event = _season_event(app, 'Line Open')
    scheffler, rory, spare = _golfer('R1', 'Scheffler'), _golfer('R2', 'McIlroy'), _golfer('R3', 'Spare')
    _result(event, scheffler, earnings=500)
    _result(event, rory, earnings=100)
    _result(event, spare, earnings=7)
    _pick(brad, handicap, event, scheffler, spare)
    _pick(brad, pollyanna, event, rory, scheffler)
    event.recap_email_sent = True  # the letters are the next test's
    db.session.commit()

    TournamentSync(SlashGolfAPI(api_key='test-key')).process_tournament_picks(event)

    db.session.expire_all()
    assert db.session.get(GolfEnrollment, h_line.id).total_points == 500
    assert db.session.get(GolfEnrollment, p_line.id).total_points == 100
    # Re-resolving the Pollyanna pick (Rory, backup Scheffler) never wipes the
    # Handicap line's spend of Scheffler.
    assert _usage_ids(brad, handicap) == {scheffler.id}
    assert _usage_ids(brad, pollyanna) == {rory.id}

    # Review Focus 1: the SAME golfer as the primary on both lines of one event
    # is two usage rows (one per league), not one.
    second = _season_event(app, 'Both Lines Open')
    _result(second, scheffler, earnings=300)
    _pick(brad, handicap, second, scheffler, spare)
    _pick(brad, pollyanna, second, scheffler, rory)
    second.recap_email_sent = True
    db.session.commit()

    TournamentSync(SlashGolfAPI(api_key='test-key')).process_tournament_picks(second)

    db.session.expire_all()
    rows = GolfSeasonPlayerUsage.query.filter_by(
        user_id=brad.id, player_id=scheffler.id, season_year=app.config['SEASON_YEAR']).all()
    assert sorted(row.league_id for row in rows) == sorted([handicap.id, pollyanna.id])


def test_picks_open_goes_once_per_line_so_brad_gets_two_letters(app, golf_leagues, monkeypatch):
    from games.golf.services.reminders import send_picks_open_email

    _mail_config(app)
    sent = _capture_mail(monkeypatch)
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    brad, han, cy = _user('brad_two'), _user('han_handicap'), _user('cy_polly')
    _line(brad, handicap, app, total=500)
    _line(brad, pollyanna, app, total=100)
    _line(han, handicap, app)
    _line(cy, pollyanna, app)
    event = _season_event(app, 'The Memorial', status='upcoming', deadline_in=timedelta(days=2))

    assert send_picks_open_email(event) == 4

    by_to = {}
    for letter in sent:
        by_to.setdefault(letter['to'], []).append(letter)
    assert sorted(len(v) for v in by_to.values()) == [1, 1, 2]
    assert len(by_to[brad.email]) == 2 and len(by_to[cy.email]) == 1
    for letter in sent:
        slug = 'handicap' if letter['plain'].startswith('Handicap Pay Sheet') else 'pollyanna'
        league = golf_leagues[slug]
        assert letter['plain'].startswith(f'{league.name}, the Memorial: picks are open\n')
        assert f'https://cccfantasy.com/golf/{slug}/pick/{event.id}' in letter['plain']
        other = 'pollyanna' if slug == 'handicap' else 'handicap'
        assert f'/golf/{other}/' not in letter['plain'] + letter['html']
    brad_totals = sorted(m['plain'].split('Season total: ')[1].split('\n')[0]
                         for m in by_to[brad.email])
    assert brad_totals == ['$100', '$500']
    assert by_to[cy.email][0]['plain'].startswith('Pollyanna Pay Sheet, ')


def test_reminder_passes_loop_both_leagues_and_latch_once(app, golf_leagues, monkeypatch):
    from unittest.mock import patch

    from games.golf.services.reminders import run_reminder_check
    from games.golf.services.sync import SlashGolfAPI, TournamentSync

    _mail_config(app)
    sent = _capture_mail(monkeypatch)
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    brad, han, cy = _user('brad_rem'), _user('han_rem'), _user('cy_rem')
    _line(brad, handicap, app)
    _line(brad, pollyanna, app)
    _line(han, handicap, app)
    _line(cy, pollyanna, app)
    event = _season_event(app, 'Reminder Open', status='upcoming', deadline_in=timedelta(hours=24))
    a, b = _golfer('M1', 'Alpha'), _golfer('M2', 'Bravo')
    _pick(brad, handicap, event, a, b)   # Brad is in on Handicap, not on Pollyanna
    _pick(cy, pollyanna, event, a, b)

    with patch('games.golf.services.reminders.is_field_ready', return_value=True), \
            patch('games.golf.services.reminders.get_field_count', return_value=60):
        run_reminder_check()
        assert sorted((m['to'], m['plain'].split(',')[0]) for m in sent) == [
            (brad.email, 'Pollyanna Pay Sheet'), (han.email, 'Handicap Pay Sheet')]
        for m in sent:
            slug = 'pollyanna' if m['to'] == brad.email else 'handicap'
            assert f'https://cccfantasy.com/golf/{slug}/pick/{event.id}' in m['plain']
        db.session.expire_all()
        assert db.session.get(GolfTournament, event.id).last_reminder_type == '24h'
        run_reminder_check()          # the tier latched once for both leagues
    assert len(sent) == 2

    # The recap: one per line, each linking its league's board, latched once.
    sent.clear()
    event = db.session.get(GolfTournament, event.id)
    event.status = 'complete'
    db.session.commit()
    _result(event, a, earnings=300)
    _result(event, b, earnings=10)
    _pick(han, handicap, event, b, a)    # Han's late pick puts him in Handicap's top 3
    sync = TournamentSync(SlashGolfAPI(api_key='test-key'))
    sync.process_tournament_picks(event)
    assert sorted((m['to'], m['plain'].split(',')[0]) for m in sent) == sorted([
        (brad.email, 'Handicap Pay Sheet'), (brad.email, 'Pollyanna Pay Sheet'),
        (han.email, 'Handicap Pay Sheet'), (cy.email, 'Pollyanna Pay Sheet')])
    for m in sent:
        slug = 'handicap' if m['plain'].startswith('Handicap') else 'pollyanna'
        assert m['plain'].startswith(f'{golf_leagues[slug].name}, the Reminder Open: results are in\n')
        assert f'https://cccfantasy.com/golf/{slug}/tournament/{event.id}' in m['plain']
        # Each league ranks its own two lines: the pick that banked $300 leads.
        picked = (m['to'], slug) in {(brad.email, 'handicap'), (cy.email, 'pollyanna')}
        assert f"Rank: {1 if picked else 2} of 2\n" in m['plain']
        # The week's top 3 stays in its league: Cy (a Pollyanna pick) is never
        # on a Handicap letter, Han (a Handicap pick) never on a Pollyanna one.
        ours, theirs = ('han_rem', 'cy_rem') if slug == 'handicap' else ('cy_rem', 'han_rem')
        assert ours in m['plain'] and ours in m['html']
        assert theirs not in m['plain'] and theirs not in m['html']
    assert db.session.get(GolfTournament, event.id).recap_email_sent is True
    sync.process_tournament_picks(db.session.get(GolfTournament, event.id))
    assert len(sent) == 4


def test_import_legacy_takes_a_league(app, golf_leagues, tmp_path):
    from games.golf.services.legacy_import import run_import, verify_scoring
    from tests._golf_legacy_fixtures import build_legacy_db

    path = build_legacy_db(tmp_path / 'legacy.db')
    pollyanna = golf_leagues['pollyanna']

    report = run_import(str(path), season=2026, league='pollyanna')

    assert report.outcome == 'committed', report.render()
    for model in (GolfEnrollment, GolfPick, GolfSeasonPlayerUsage):
        rows = model.query.all()
        assert rows and {r.league_id for r in rows} == {pollyanna.id}, model.__name__
    on_polly = verify_scoring(2026, league='pollyanna')
    assert on_polly.diff_count == 0 and on_polly.picks_checked == 6
    assert verify_scoring(2026).picks_checked == 0   # the house league holds nothing

    with pytest.raises(ValueError, match='nope'):
        run_import(str(path), season=2026, league='nope')
    runner = app.test_cli_runner()
    bad = runner.invoke(args=['golf', 'import-legacy', str(path), '--league', 'nope'])
    assert bad.exit_code == 1 and 'nope' in bad.output
    assert runner.invoke(args=['golf', 'verify-legacy', '--league', 'pollyanna']).exit_code == 0
    assert runner.invoke(args=['golf', 'verify-legacy', '--league', 'nope']).exit_code == 1


def test_league_set_cli_changes_the_fee(app, golf_leagues):
    runner = app.test_cli_runner()

    listed = runner.invoke(args=['golf', 'league', 'list'])
    assert listed.exit_code == 0, listed.output
    lines = listed.output.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].split()[0] == 'handicap' and 'Handicap Pay Sheet' in lines[0]
    assert lines[1].split()[0] == 'pollyanna'

    done = runner.invoke(args=['golf', 'league', 'set', 'pollyanna', '--entry-fee', '30'])
    assert done.exit_code == 0, done.output
    db.session.expire_all()
    polly, house = league_by_slug('pollyanna'), league_by_slug('handicap')
    assert (polly.entry_fee, polly.penalty_per_incident, polly.name) == (30, 15, 'Pollyanna Pay Sheet')
    assert house.entry_fee == 25

    renamed = runner.invoke(args=['golf', 'league', 'set', 'handicap', '--name', 'The Handicap Sheet',
                                  '--penalty', '20'])
    assert renamed.exit_code == 0, renamed.output
    db.session.expire_all()
    house = league_by_slug('handicap')
    assert (house.name, house.penalty_per_incident, house.entry_fee) == ('The Handicap Sheet', 20, 25)

    unknown = runner.invoke(args=['golf', 'league', 'set', 'nope', '--entry-fee', '1'])
    assert unknown.exit_code == 1 and 'nope' in unknown.output

    # The input boundary: a negative amount or a blank name changes nothing.
    for bad in (['--entry-fee', '-5'], ['--penalty', '-1'], ['--name', '   ']):
        refused = runner.invoke(args=['golf', 'league', 'set', 'handicap', *bad])
        assert refused.exit_code != 0, bad
    db.session.expire_all()
    house = league_by_slug('handicap')
    assert (house.name, house.penalty_per_incident, house.entry_fee) == ('The Handicap Sheet', 20, 25)

    # A name longer than the column is refused before the write, on both
    # engines (SQLite would store it; Postgres would raise at commit).
    too_long = runner.invoke(args=['golf', 'league', 'set', 'handicap', '--name', 'x' * 61])
    assert too_long.exit_code == 1 and 'Error:' in too_long.output
    # Surrounding spaces are not part of the name.
    padded = runner.invoke(args=['golf', 'league', 'set', 'handicap', '--name', '  The Handicap Sheet  '])
    assert padded.exit_code == 0, padded.output
    db.session.expire_all()
    assert league_by_slug('handicap').name == 'The Handicap Sheet'



# --- Task A5: the league in the URL, the resolver, every route scoped --------

def _member(username, *lines, app, admin_in=None, display_name=None):
    """A user with a line in each of ``lines`` this season (``admin_in`` is
    the league whose line carries the commissioner flag); returns the id."""
    user = User(username=username, email=f'{username}@example.com',
                display_name=display_name or username)
    user.set_password('x')
    db.session.add(user)
    db.session.flush()
    for league in lines:
        db.session.add(GolfEnrollment(
            user_id=user.id, league_id=league.id, season_year=app.config['SEASON_YEAR'],
            is_admin=league is admin_in))
    db.session.commit()
    return user.id


@contextmanager
def _viewer(app, user_id=None):
    """A fresh client for one viewer, inside its own app context.

    Flask-Login caches the loaded user on ``g``, and every request under the
    fixture's app context shares that ``g``, so a test that reads as several
    viewers gives each its own context (tests/test_cfb_player_card.py::_page).
    The nested teardown removes its session, which is why callers pass ids.
    """
    client = app.test_client()
    with app.app_context():
        if user_id is not None:
            with client.session_transaction() as sess:
                sess['_user_id'] = db.session.get(User, user_id).auth_id
                sess['_fresh'] = True
        yield client


def _lands(resp, path):
    return resp.status_code == 302 and resp.headers['Location'].endswith(path)


def _league_cookie(resp):
    """The response's golf_league Set-Cookie, or None (the session cookie aside)."""
    return next((c for c in resp.headers.getlist('Set-Cookie')
                 if c.startswith('golf_league=')), None)


def test_room_root_resolves_to_the_viewers_league(app, golf_leagues):
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    cy = _member('cy_only', pollyanna, app=app)
    brad = _member('brad_two_rooms', handicap, pollyanna, app=app)

    with _viewer(app) as anonymous:
        assert _lands(anonymous.get('/golf/'), '/golf/handicap/')

    with _viewer(app, cy) as client:
        assert _lands(client.get('/golf/'), '/golf/pollyanna/')
        # One line: nothing to remember, so no cookie.
        assert _league_cookie(client.get('/golf/pollyanna/')) is None
        # A cookie naming a league the member is not on is ignored.
        client.set_cookie('golf_league', 'handicap')
        assert _lands(client.get('/golf/'), '/golf/pollyanna/')

    with _viewer(app, brad) as client:
        assert _lands(client.get('/golf/'), '/golf/handicap/')
        # A league page remembers the league for a member of both, once.
        visited = client.get('/golf/pollyanna/')
        assert visited.status_code == 200
        cookie = _league_cookie(visited)
        assert 'golf_league=pollyanna' in cookie and 'SameSite=Lax' in cookie
        assert 'Max-Age=15552000' in cookie   # 180 days
        assert 'HttpOnly' in cookie
        assert _league_cookie(client.get('/golf/pollyanna/')) is None
        assert _lands(client.get('/golf/'), '/golf/pollyanna/')

    with _viewer(app, brad) as client:
        client.set_cookie('golf_league', 'pollyanna')
        assert _lands(client.get('/golf/'), '/golf/pollyanna/')


def test_unknown_league_is_404(app, golf_leagues):
    brad = _member('lost_brad', golf_leagues['handicap'], app=app)
    for viewer in (None, brad):
        with _viewer(app, viewer) as client:
            for path in ('/golf/nowhere/', '/golf/nowhere/stats'):
                resp = client.get(path)
                assert resp.status_code == 404, path
                body = resp.get_data(as_text=True)
                assert 'Not in the Ledger' in body
                # The golf sub-nav renders its label and no pills at this boundary.
                assert 'subnav-golf' in body and 'class="subnav-pill' not in body


def test_url_for_outside_the_room_needs_a_league(app, golf_leagues):
    from flask import url_for
    from werkzeug.routing import BuildError

    with app.test_request_context('/'):
        with pytest.raises(BuildError):
            url_for('golf.index')
        assert url_for('golf.index', league='pollyanna') == '/golf/pollyanna/'
        assert url_for('golf.room') == '/golf/'
        assert url_for('golf.join') == '/golf/join'


def test_url_defaults_fill_the_league_only_during_a_golf_request(app, client, golf_leagues):
    from flask import url_for
    from werkzeug.routing import BuildError

    assert client.get('/golf/pollyanna/').status_code == 200   # leaves g.golf_league set
    with app.test_request_context('/'), pytest.raises(BuildError):
        url_for('golf.index')


def test_each_leagues_sheet_board_and_stats_show_only_its_lines(app, client, golf_leagues):
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    season = app.config['SEASON_YEAR']
    brad = db.session.get(User, _member('brad_both_sheets', handicap, pollyanna, app=app,
                                        display_name='Brad Both'))
    han = db.session.get(User, _member('han_sheet', handicap, app=app,
                                       display_name='Han Handicapper'))
    cy = db.session.get(User, _member('cy_sheet', pollyanna, app=app,
                                      display_name='Cy Pollyannist'))
    event = _season_event(app, 'Banked Open')
    event.results_finalized = True
    event.week_number = 1
    a, b, c, d = (_golfer(f'W{i}', f'Weekgolfer{i}') for i in range(4))
    for player, money in ((a, 900), (b, 50), (c, 400), (d, 20)):
        _result(event, player, earnings=money)
    for user, league, primary, backup in (
            (brad, handicap, a, b), (han, handicap, c, d),
            (brad, pollyanna, c, d), (cy, pollyanna, a, b)):
        assert _pick(user, league, event, primary, backup).resolve_pick()
    db.session.commit()
    for line in GolfEnrollment.query.all():
        line.calculate_total_points()
    db.session.commit()

    for slug, ours, theirs in (('handicap', han, cy), ('pollyanna', cy, han)):
        name = golf_leagues[slug].name
        for path in (f'/golf/{slug}/', f'/golf/{slug}/tournament/{event.id}',
                     f'/golf/{slug}/stats', f'/golf/{slug}/member/{brad.id}'):
            resp = client.get(path)
            assert resp.status_code == 200, path
            body = resp.get_data(as_text=True)
            assert theirs.display_name not in body, path
            assert f'{name} · {season}' in body, path
        sheet = client.get(f'/golf/{slug}/').get_data(as_text=True)
        assert ours.display_name in sheet and 'Brad Both' in sheet
    # Brad's money on each sheet is that league's pick: Weekgolfer0 on Handicap.
    assert '$900' in client.get('/golf/handicap/').get_data(as_text=True)
    assert '$900' not in client.get(f'/golf/pollyanna/member/{brad.id}').get_data(as_text=True)
    # A member's scorecard lives in the leagues they hold a line in.
    assert client.get(f'/golf/pollyanna/member/{han.id}').status_code == 404


def test_pick_route_needs_a_line_in_that_league(app, golf_leagues, monkeypatch):
    from tests._registry_helpers import set_status

    set_status(monkeypatch, 'golf', 'open')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    han = _member('han_picker', handicap, app=app)
    brad = _member('brad_picker', handicap, pollyanna, app=app)
    event = _season_event(app, 'Pick Open', status='upcoming', deadline_in=timedelta(days=2))
    field = [_golfer(f'P{i:02d}', f'Fieldgolfer{i:02d}') for i in range(50)]
    db.session.add_all(GolfTournamentField(tournament_id=event.id, player_id=p.id) for p in field)
    db.session.commit()
    event_id, primary, backup = event.id, field[0].id, field[1].id
    filing = {'primary_player_id': primary, 'backup_player_id': backup}

    with _viewer(app, han) as client:
        assert client.get(f'/golf/handicap/pick/{event_id}').status_code == 200
        away = client.get(f'/golf/pollyanna/pick/{event_id}', follow_redirects=True)
        assert 'Join the Pollyanna Pay Sheet to pick there.' in away.get_data(as_text=True)
        assert _lands(client.post(f'/golf/pollyanna/pick/{event_id}', data=filing), '/golf/join')
        assert _lands(client.get('/golf/pollyanna/my-picks'), '/golf/join')
        assert GolfPick.query.count() == 0

    # A member of both files the same golfer on each sheet.
    with _viewer(app, brad) as client:
        for slug in ('handicap', 'pollyanna'):
            assert _lands(client.post(f'/golf/{slug}/pick/{event_id}', data=filing),
                          f'/golf/{slug}/')
        assert _lands(client.get('/golf/pollyanna/my-picks'), f'/golf/pollyanna/member/{brad}')
        assert sorted(p.league_id for p in GolfPick.query.filter_by(user_id=brad)) == sorted(
            [handicap.id, pollyanna.id])


def test_join_seats_the_chosen_league_and_allows_the_second(app, client, golf_leagues, monkeypatch):
    from tests._registry_helpers import set_status

    set_status(monkeypatch, 'golf', 'open')
    handicap_id, pollyanna_id = golf_leagues['handicap'].id, golf_leagues['pollyanna'].id
    joiner = _user('joiner_two')
    with client.session_transaction() as sess:
        sess['_user_id'] = joiner.auth_id
        sess['_fresh'] = True

    page = client.get('/golf/join').get_data(as_text=True)
    assert 'Handicap Pay Sheet' in page and 'Pollyanna Pay Sheet' in page
    assert page.count('name="league"') == 2
    assert 'id="join-current-name"' in page and '/profile' in page

    assert client.post('/golf/join', data={'league': 'nope'}).status_code == 400
    assert GolfEnrollment.query.count() == 0

    assert _lands(client.post('/golf/join', data={'league': 'pollyanna'}), '/golf/pollyanna/')
    assert [(e.league_id, e.season_year) for e in GolfEnrollment.query.all()] == [
        (pollyanna_id, app.config['SEASON_YEAR'])]

    again = client.post('/golf/join', data={'league': 'pollyanna'}, follow_redirects=True)
    assert 'already on that sheet' in again.get_data(as_text=True)
    assert GolfEnrollment.query.count() == 1

    page = client.get('/golf/join').get_data(as_text=True)
    assert page.count('name="league"') == 1   # only the Handicap seat is still open
    assert _lands(client.post('/golf/join', data={'league': 'handicap'}), '/golf/handicap/')
    assert sorted(e.league_id for e in GolfEnrollment.query.filter_by(user_id=joiner.id)) == sorted(
        [handicap_id, pollyanna_id])


def test_admin_pages_scope_to_the_league_and_settle_the_book_is_platform_only(app, golf_leagues):
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    commish = _member('polly_commish', pollyanna, app=app, admin_in=pollyanna)
    han = _member('han_member', handicap, app=app, display_name='Han Onhandicap')
    cy = _member('cy_member', pollyanna, app=app, display_name='Cy Onpollyanna')
    brad = _user('platform_brad')
    brad.is_admin = True
    db.session.commit()
    brad = brad.id
    event_id = _season_event(app, 'Admin Open').id

    with _viewer(app, commish) as client:
        users = client.get('/golf/pollyanna/admin/users')
        assert users.status_code == 200
        assert 'Cy Onpollyanna' in users.get_data(as_text=True)
        assert 'Han Onhandicap' not in users.get_data(as_text=True)
        assert client.get('/golf/handicap/admin/users').status_code == 302
        assert client.get('/golf/pollyanna/admin/payments').status_code == 200
        assert client.get('/golf/pollyanna/admin/override-pick').status_code == 200

        assert _lands(client.get('/golf/pollyanna/admin/tournaments'), '/golf/pollyanna/admin/')
        settle = client.post(f'/golf/pollyanna/admin/process-results/{event_id}',
                             follow_redirects=True)
        assert 'Platform admin only.' in settle.get_data(as_text=True)

        # The Tab touches this league's lines only.
        other = client.post(f'/golf/pollyanna/admin/update-payment/{han}', json={'has_paid': True})
        assert other.status_code == 400
        ours = client.post(f'/golf/pollyanna/admin/update-payment/{cy}', json={'has_paid': True})
        assert ours.status_code == 200

    db.session.expire_all()
    assert get_enrollment(cy, pollyanna).has_paid is True
    assert get_enrollment(han, handicap).has_paid is False

    with _viewer(app, brad) as client:
        assert client.get('/golf/pollyanna/admin/tournaments').status_code == 200
        assert client.get('/golf/handicap/admin/users').status_code == 200


# --- PR #270 review: the cross-league seams, each with both leagues seeded ---

def _flat(resp):
    """A response body with its whitespace runs folded to one space."""
    import re
    return re.sub(r'\s+', ' ', resp.get_data(as_text=True))


def test_override_pick_is_this_leagues_line_and_this_leagues_spend(app, golf_leagues):
    """The Pollyanna commissioner's pen: a Handicap-only member has nothing to
    override, and a golfer Brad spent on his Handicap line is open on his
    Pollyanna line. Pins ``get_enrollment(user_id, league)``, the league-scoped
    ``get_used_player_ids`` on POST and GET, the re-total of the one line, and
    the member select and recent overrides read from this league only."""
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    commish = _member('polly_pen', pollyanna, app=app, admin_in=pollyanna,
                      display_name='Polly Pen')
    han = _member('han_pen', handicap, app=app, display_name='Han Handicaponly')
    brad = _member('brad_pen', handicap, pollyanna, app=app, display_name='Brad Twolines')
    event = _season_event(app, 'Override Open')
    scheffler, rory, spare = _golfer('O1', 'Scheffler'), _golfer('O2', 'McIlroy'), _golfer('O3', 'Spare')
    for player, money in ((scheffler, 500), (rory, 100), (spare, 7)):
        db.session.add(GolfTournamentField(tournament_id=event.id, player_id=player.id))
        _result(event, player, earnings=money)
    brad_user, han_user = db.session.get(User, brad), db.session.get(User, han)
    h_pick = _pick(brad_user, handicap, event, scheffler, spare)
    p_pick = _pick(brad_user, pollyanna, event, rory, spare)
    han_pick = _pick(han_user, handicap, event, spare, rory)
    han_pick.admin_override = True          # a Handicap override on the record
    assert h_pick.resolve_pick() and p_pick.resolve_pick() and han_pick.resolve_pick()
    db.session.commit()
    for line in GolfEnrollment.query.all():
        line.calculate_total_points()
    db.session.commit()
    event_id, h_pick_id, p_pick_id = event.id, h_pick.id, p_pick.id
    ids = {'scheffler': scheffler.id, 'rory': rory.id, 'spare': spare.id}
    assert get_enrollment(brad, pollyanna).total_points == 100
    assert get_enrollment(brad, handicap).total_points == 500

    with _viewer(app, commish) as client:
        page = client.get(f'/golf/pollyanna/admin/override-pick?tournament_id={event_id}'
                          f'&user_id={brad}')
        assert page.status_code == 200
        body = page.get_data(as_text=True)
        assert 'Brad Twolines' in body
        assert 'Han Handicaponly' not in body       # neither in the select nor the recent list
        # Scheffler is spent on Brad's Handicap line only: nothing is used here.
        assert '(used)' not in body
        assert f'<option value="{ids["scheffler"]}" disabled>' not in body

        refused = client.post('/golf/pollyanna/admin/override-pick', data={
            'tournament_id': event_id, 'user_id': han, 'confirm': '1',
            'primary_player_id': ids['scheffler'], 'backup_player_id': ids['rory'],
        }, follow_redirects=True)
        assert 'has no line on the Pollyanna Pay Sheet' in refused.get_data(as_text=True)

        filing = {'tournament_id': event_id, 'user_id': brad,
                  'primary_player_id': ids['scheffler'], 'backup_player_id': ids['rory']}
        gate = client.post('/golf/pollyanna/admin/override-pick', data=filing)
        assert gate.status_code == 200          # a complete event asks first
        assert 'already been used' not in gate.get_data(as_text=True)
        saved = client.post('/golf/pollyanna/admin/override-pick',
                            data={**filing, 'confirm': '1'}, follow_redirects=True)
        saved_body = saved.get_data(as_text=True)
        assert 'Override saved for brad_pen' in saved_body
        assert 'already been used' not in saved_body
        assert 'Han Handicaponly' not in saved_body

    db.session.expire_all()
    assert [p.league_id for p in GolfPick.query.filter_by(user_id=han)] == [handicap.id]
    rewritten = db.session.get(GolfPick, p_pick_id)
    assert (rewritten.primary_player_id, rewritten.active_player_id) == (ids['scheffler'], ids['scheffler'])
    assert rewritten.admin_override is True and rewritten.points_earned == 500
    assert get_enrollment(brad, pollyanna).total_points == 500     # this line's pick alone
    assert _usage_ids(brad_user, pollyanna) == {ids['scheffler']}
    kept = db.session.get(GolfPick, h_pick_id)
    assert (kept.primary_player_id, kept.points_earned, kept.admin_override) == (
        ids['scheffler'], 500, False)
    assert _usage_ids(brad_user, handicap) == {ids['scheffler']}
    assert get_enrollment(brad, handicap).total_points == 500


def test_the_pot_and_the_tab_are_each_leagues_fee_lines_and_penalties(app, golf_leagues):
    """The Sheet's prize pool and The Tab: each league's entry fee x its own
    lines, and its own flagged picks x its own penalty. Brad's flagged
    Handicap pick never reaches the Pollyanna pot or his Pollyanna row. Pins
    ``season_enrollments(..., league.id)`` and the ``league_id`` filter on the
    penalty counts (the Sheet's and ``_penalty_counts``)."""
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    pollyanna.entry_fee, pollyanna.penalty_per_incident = 30, 20
    db.session.commit()
    brad = _member('brad_pot', handicap, pollyanna, app=app, display_name='Brad Bothpots')
    _member('han_pot', handicap, app=app, display_name='Han Handicappot')
    _member('cy_pot', pollyanna, app=app, display_name='Cy Pollypot')
    commish = _member('polly_purse', pollyanna, app=app, admin_in=pollyanna)
    platform = _user('pot_platform')
    platform.is_admin = True
    db.session.commit()
    platform = platform.id
    event = _season_event(app, 'Pot Major')
    event.is_major, event.results_finalized, event.week_number = True, True, 1
    cut, made = _golfer('PT1', 'Cutman'), _golfer('PT2', 'Madeit')
    _result(event, cut, status='cut', earnings=0)
    _result(event, made, earnings=80)
    flagged = _pick(db.session.get(User, brad), handicap, event, cut, made)
    flagged.penalty_triggered = True
    db.session.commit()

    with _viewer(app) as client:
        house = _flat(client.get('/golf/handicap/'))
        assert 'Entry $25 × 2</dt> <dd>$50</dd>' in house
        assert 'Penalty pot</dt> <dd>$15</dd>' in house
        assert 'In the pool</dt> <dd>$65</dd>' in house
        polly = _flat(client.get('/golf/pollyanna/'))
        assert 'Entry $30 × 3</dt> <dd>$90</dd>' in polly
        assert 'Penalty pot</dt> <dd>$0</dd>' in polly
        assert 'In the pool</dt> <dd>$90</dd>' in polly
        assert '$20 to the pot' in polly and '$15 to the pot' not in polly

    with _viewer(app, commish) as client:
        tab = _flat(client.get('/golf/pollyanna/admin/payments'))
        assert '$30 a seat' in tab and '$20 a missed cut at a major' in tab
        assert 'Penalty pot</dt> <dd>$0</dd>' in tab
        assert 'Brad Bothpots' in tab and 'Han Handicappot' not in tab
        assert 'Penalty owed' not in tab          # Brad's Handicap flag is not on this tab

    with _viewer(app, platform) as client:      # the control: the flag is on the Handicap tab
        house_tab = _flat(client.get('/golf/handicap/admin/payments'))
        assert 'Penalty owed <strong>$15</strong>' in house_tab
        assert 'Penalty pot</dt> <dd>$15' in house_tab
        assert 'Cy Pollypot' not in house_tab


def test_a_golfer_spent_on_one_sheet_is_open_on_the_other_pick_page(app, golf_leagues, monkeypatch):
    """Spend a Golfer: Scheffler spent on Brad's Handicap line is struck there
    and refused there, and open and accepted on his Pollyanna line. Pins the
    ``league_id`` filter on the page's usage read and ``validate_availability``."""
    from tests._registry_helpers import set_status

    set_status(monkeypatch, 'golf', 'open')
    monkeypatch.setenv('GOLF_FAKE_NOW', '2026-04-07T15:00:00')   # Tuesday of Masters week
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    season = app.config['SEASON_YEAR']
    brad = _member('brad_field', handicap, pollyanna, app=app)
    masters = GolfTournament(
        api_tourn_id='PR-masters', name='Masters Tournament', season_year=season,
        start_date=datetime(2026, 4, 9), end_date=datetime(2026, 4, 12),
        pick_deadline=datetime(2026, 4, 9, 7, 40), purse=10_000_000,
        status='upcoming', week_number=13,
    )
    db.session.add(masters)
    db.session.commit()
    field = [_golfer(f'K{i:02d}', f'Fieldgolfer{i:02d}') for i in range(50)]
    db.session.add_all(GolfTournamentField(tournament_id=masters.id, player_id=p.id) for p in field)
    scheffler = field[0]
    db.session.add(GolfSeasonPlayerUsage(user_id=brad, league_id=handicap.id,
                                         player_id=scheffler.id, season_year=season))
    db.session.commit()
    event_id, sid = masters.id, scheffler.id
    struck = '<span class="golf-field-name golf-used">Pat Fieldgolfer00</span>'
    disabled = f'<option value="{sid}" disabled>Pat Fieldgolfer00 (used)</option>'

    with _viewer(app, brad) as client:
        polly = client.get(f'/golf/pollyanna/pick/{event_id}').get_data(as_text=True)
        assert struck not in polly and disabled not in polly
        assert polly.count(f'<option value="{sid}">Pat Fieldgolfer00</option>') == 2
        house = client.get(f'/golf/handicap/pick/{event_id}').get_data(as_text=True)
        assert struck in house and house.count(disabled) == 2

        accepted = client.post(f'/golf/pollyanna/pick/{event_id}', data={
            'primary_player_id': sid, 'backup_player_id': field[1].id})
        assert _lands(accepted, '/golf/pollyanna/')
        refused = client.post(f'/golf/handicap/pick/{event_id}', data={
            'primary_player_id': sid, 'backup_player_id': field[2].id})
        assert refused.status_code == 200
        assert 'Your primary has already been spent this season.' in refused.get_data(as_text=True)

    db.session.expire_all()
    picks = GolfPick.query.filter_by(user_id=brad, tournament_id=event_id).all()
    assert [(p.league_id, p.primary_player_id) for p in picks] == [(pollyanna.id, sid)]


def test_the_lounge_panel_shows_a_pollyanna_member_their_own_sheet(app, golf_leagues, monkeypatch):
    """The lounge's golf panel for a Pollyanna-only member: the league is
    Pollyanna, the leader and the top rows are Pollyanna's (the Handicap
    rival's bigger total is not on it), and the panel's links stay in
    /golf/pollyanna/. Pins ``enrollments_for`` choosing the panel's league
    and ``season_enrollments(..., league.id)`` building its sheet."""
    from types import SimpleNamespace

    from flask import render_template

    from games.golf.services.lounge import build_lounge_context
    from games.registry import get_entry

    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    season = app.config['SEASON_YEAR']
    polly = _member('polly_lounge', pollyanna, app=app, display_name='Polly Leader')
    peer = _member('polly_peer', pollyanna, app=app, display_name='Polly Peer')
    rival = _member('han_rival', handicap, app=app, display_name='Han Rival')
    for user_id, league, total in ((polly, pollyanna, 1_000_000), (peer, pollyanna, 200_000),
                                   (rival, handicap, 3_000_000)):
        get_enrollment(user_id, league).total_points = total
    masters = GolfTournament(
        api_tourn_id='PR-lounge-m', name='Masters Tournament', season_year=season,
        week_number=13, start_date=datetime(2026, 4, 9), end_date=datetime(2026, 4, 12),
        pick_deadline=datetime(2026, 4, 9, 7, 40), purse=10_000_000, status='active')
    rbc = GolfTournament(
        api_tourn_id='PR-lounge-r', name='RBC Heritage', season_year=season,
        week_number=14, start_date=datetime(2026, 4, 16), end_date=datetime(2026, 4, 19),
        pick_deadline=datetime(2026, 4, 16, 6, 5), purse=10_000_000, status='upcoming')
    db.session.add_all([masters, rbc])
    db.session.commit()
    field = [_golfer(f'LG{i:02d}', f'Loungegolfer{i:02d}') for i in range(60)]
    db.session.add_all(GolfTournamentField(tournament_id=rbc.id, player_id=p.id) for p in field)
    db.session.commit()
    monkeypatch.setenv('GOLF_FAKE_NOW', '2026-04-12T21:30:00')   # Masters Sunday
    rbc_id = rbc.id

    ctx = build_lounge_context(db.session.get(User, polly), 'live')

    assert ctx['league'] == 'pollyanna'
    assert ctx['leader']['name'] == 'Polly Leader'
    assert [row['name'] for row in ctx['top']] == ['Polly Leader', 'Polly Peer']
    assert ctx['field'] == 2 and ctx['pick_wanted'] is True and ctx['next_id'] == rbc_id

    with app.test_request_context('/'):
        html = render_template('golf/lounge/_panel_live.html',
                               h=SimpleNamespace(ctx=ctx, entry=get_entry('golf'), join_open=False))
    assert f'href="/golf/pollyanna/pick/{rbc_id}"' in html
    assert f'/golf/pollyanna/member/{polly}' in html
    assert '/golf/handicap/' not in html
    assert 'Han Rival' not in html


def test_the_shared_pages_resolve_to_the_viewers_league(app, golf_leagues):
    """/golf/schedule and /golf/leaderboard carry no league in their URL: a
    Pollyanna-only member's links and landing are Pollyanna's, an anonymous
    visitor's the house league's. Pins ``viewer_league`` and the url_defaults
    hook filling the league on a league-less golf page."""
    pollyanna = golf_leagues['pollyanna']
    cy = _member('cy_shared', pollyanna, app=app)
    banked = _season_event(app, 'Shared Banked')
    coming = _season_event(app, 'Shared Coming', status='upcoming', deadline_in=timedelta(days=2))
    banked_id, coming_id = banked.id, coming.id

    with _viewer(app, cy) as client:
        schedule = client.get('/golf/schedule')
        assert schedule.status_code == 200
        body = schedule.get_data(as_text=True)
        assert f'/golf/pollyanna/tournament/{banked_id}' in body
        assert f'/golf/pollyanna/pick/{coming_id}' in body
        assert '/golf/handicap/' not in body
        assert _lands(client.get('/golf/leaderboard'), '/golf/pollyanna/')

    with _viewer(app) as anonymous:
        body = anonymous.get('/golf/schedule').get_data(as_text=True)
        assert f'/golf/handicap/tournament/{banked_id}' in body
        assert '/golf/pollyanna/' not in body
        assert _lands(anonymous.get('/golf/leaderboard'), '/golf/handicap/')


# --- Task B1: the league stamp and the sub-nav switch -------------------------

def _context_line(body):
    """The text of the page's ``.golf-context`` line."""
    return body.split('class="golf-context">', 1)[1].split('</p>', 1)[0]


def _title(body):
    return body.split('<title>', 1)[1].split('</title>', 1)[0]


def _words(markup):
    """The rendered text of a fragment, tags gone, whitespace folded."""
    return ' '.join(re.sub(r'<[^>]+>', ' ', markup).split())


def test_every_league_page_is_stamped_and_only_a_member_of_both_sees_the_switch(
        app, golf_leagues, monkeypatch):
    """Every league page names its league in the title and opens its context
    line with it; the sub-nav switch to the other sheet shows only to a member
    holding a line on both."""
    from tests._registry_helpers import set_status

    set_status(monkeypatch, 'golf', 'open')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    brad = _member('brad_stamp', handicap, pollyanna, app=app)
    db.session.get(User, brad).is_admin = True
    db.session.commit()
    han = _member('han_stamp', handicap, app=app)
    event = _season_event(app, 'Stamp Open', status='upcoming', deadline_in=timedelta(days=2))
    event_id = event.id

    pages = [
        '/golf/pollyanna/', f'/golf/pollyanna/tournament/{event_id}',
        f'/golf/pollyanna/member/{brad}', '/golf/pollyanna/stats',
        f'/golf/pollyanna/pick/{event_id}', '/golf/pollyanna/admin/',
        '/golf/pollyanna/admin/tournaments', '/golf/pollyanna/admin/users',
        '/golf/pollyanna/admin/payments', '/golf/pollyanna/admin/override-pick',
    ]
    with _viewer(app, brad) as client:
        for path in pages:
            resp = client.get(path)
            assert resp.status_code == 200, path
            body = resp.get_data(as_text=True)
            assert 'Pollyanna Pay Sheet' in _title(body), path
            context = _context_line(body)
            assert 'Pollyanna Pay Sheet' in context and 'Handicap' not in context, path
            # The stamp opens the line: nothing precedes it but markup.
            assert _words(context).startswith('Pollyanna Pay Sheet'), path
        on_handicap = client.get('/golf/handicap/').get_data(as_text=True)
        switch = on_handicap.split('subnav-pill--switch')[1].split('</a>')[0]
        assert 'href="/golf/pollyanna/"' in switch and 'Pollyanna Pay Sheet' in switch
        assert on_handicap.count('subnav-pill--switch') == 1
        on_pollyanna = client.get('/golf/pollyanna/').get_data(as_text=True)
        assert 'href="/golf/handicap/"' in on_pollyanna.split('subnav-pill--switch')[1]

    with _viewer(app, han) as client:
        body = client.get('/golf/handicap/').get_data(as_text=True)
        assert 'subnav-pill--switch' not in body
        assert 'Handicap Pay Sheet' in _context_line(body)
    with _viewer(app) as anonymous:
        assert 'subnav-pill--switch' not in anonymous.get('/golf/pollyanna/').get_data(as_text=True)


def test_shared_pages_keep_the_league_the_viewer_came_from(app, golf_leagues):
    """The Schedule pill on a league page carries its league as a query arg,
    and the shared pages honor it, so a viewer stepping off a Pollyanna page
    is not flipped back to their own league; a bad value is ignored."""
    season = app.config['SEASON_YEAR']
    han = _member('han_steps_over', golf_leagues['handicap'], app=app)
    banked = _season_event(app, 'Shared Stamp Banked')
    banked_id = banked.id

    with _viewer(app) as anonymous:
        page = anonymous.get('/golf/pollyanna/').get_data(as_text=True)
        assert 'href="/golf/schedule?league=pollyanna"' in page
        schedule = anonymous.get('/golf/schedule?league=pollyanna').get_data(as_text=True)
        assert f'Pollyanna Pay Sheet · {season}' in schedule
        assert f'/golf/pollyanna/tournament/{banked_id}' in schedule
        assert '/golf/handicap/' not in schedule
        assert _lands(anonymous.get('/golf/leaderboard?league=pollyanna'), '/golf/pollyanna/')
        assert _lands(anonymous.get('/golf/?league=pollyanna'), '/golf/pollyanna/')
        wrong = anonymous.get('/golf/schedule?league=nowhere').get_data(as_text=True)
        assert f'Handicap Pay Sheet · {season}' in wrong

    with _viewer(app, han) as client:
        schedule = client.get('/golf/schedule?league=pollyanna').get_data(as_text=True)
        assert f'Pollyanna Pay Sheet · {season}' in schedule
        assert f'/golf/pollyanna/tournament/{banked_id}' in schedule


def test_record_room_lists_only_this_leagues_seasons(app, golf_leagues):
    """The Record Room's season switcher is the league's own seasons: a prior
    season with Handicap lines and events is not offered on the Pollyanna
    room, and asking for it there is a 404."""
    handicap = golf_leagues['handicap']
    season = app.config['SEASON_YEAR']
    past = User(username='past_handicap', email='past_handicap@example.com')
    past.set_password('x')
    db.session.add(past)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=past.id, league_id=handicap.id, season_year=season - 1))
    db.session.add(GolfTournament(
        api_tourn_id='B1-last-year', name='Last Year Open', season_year=season - 1,
        start_date=datetime(season - 1, 3, 5), end_date=datetime(season - 1, 3, 8),
        pick_deadline=datetime(season - 1, 3, 5), purse=1_000_000, status='complete',
        results_finalized=True))
    db.session.commit()

    with _viewer(app) as anonymous:
        handicap_room = anonymous.get('/golf/handicap/stats').get_data(as_text=True)
        assert f'href="/golf/handicap/stats?season={season - 1}">{season - 1} season</a>' in handicap_room
        pollyanna_room = anonymous.get('/golf/pollyanna/stats').get_data(as_text=True)
        assert f'{season - 1} season' not in pollyanna_room
        assert anonymous.get(f'/golf/pollyanna/stats?season={season - 1}').status_code == 404
        assert anonymous.get(f'/golf/handicap/stats?season={season - 1}').status_code == 200


# --- Task B2: the join page with two sheets ----------------------------------

def test_join_page_offers_both_sheets_and_marks_the_joined_one(app, golf_leagues, monkeypatch):
    """One rules card, then a block per sheet in ordinal order: its name, its
    own fee, who it is for, and one seat button; a sheet the member already
    holds says so and links its standings instead."""
    from tests._registry_helpers import set_status

    set_status(monkeypatch, 'golf', 'open')
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    pollyanna.entry_fee = 40
    db.session.commit()
    newcomer = _member('join_newcomer', app=app)
    han = _member('join_han', handicap, app=app)

    with _viewer(app, newcomer) as client:
        page = client.get('/golf/join').get_data(as_text=True)
        assert page.index('Handicap Pay Sheet') < page.index('Pollyanna Pay Sheet')
        assert 'The Thursday crowd that came over from the old site.' in page
        assert 'The group that moved over from Splash.' in page
        assert 'Take a seat on the Handicap Pay Sheet' in page
        assert 'Take a seat on the Pollyanna Pay Sheet' in page
        assert '$25' in page and '$40' in page
        assert page.count('name="league"') == 2
        assert "You're on this sheet" not in page and '&#39;re on this sheet' not in page
        copy = page.split('page-hero', 1)[1].split('<footer', 1)[0]
        assert '—' not in copy and '&mdash;' not in copy

    with _viewer(app, han) as client:
        page = client.get('/golf/join').get_data(as_text=True)
        held = page.split('Handicap Pay Sheet', 1)[1].split('Pollyanna Pay Sheet', 1)[0]
        assert 're on this sheet' in held and 'href="/golf/handicap/"' in held
        assert 'Take a seat on the Handicap Pay Sheet' not in page
        assert 'Take a seat on the Pollyanna Pay Sheet' in page
        assert page.count('name="league"') == 1
