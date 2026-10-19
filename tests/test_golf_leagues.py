"""The Pay Sheet's two leagues (ADR-075): the spec lock for the whole change.

Golf is one game with two leagues inside it, Handicap (the house league) and
Pollyanna. Each league is a row in ``golf_league`` carrying its own entry fee
and penalty; every enrollment, pick and golfer usage belongs to exactly one.
"""
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
