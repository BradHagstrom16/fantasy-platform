"""Phase I — importing the retired standalone's 2026 season (`flask golf import-legacy`).

The legacy file carries 19 real members' emails + password hashes, so it is
never in the repo; these tests build a legacy-shaped SQLite file in tmp_path
(``tests/_golf_legacy_fixtures.py``) and exercise the same code path the prod
runbook uses. What is locked:

- user matching by case-folded email; a username collision aborts before any
  write unless resolved with --link / --rename; attached accounts are never
  modified; a new account carries the Werkzeug hash verbatim (login works);
- every pick / result / tournament column lands verbatim (incl. the legacy
  status-casing anomalies and a NULL-resolved pick), except recap_email_sent,
  which is forced True so no January recap can ever be mailed;
- the import is idempotent and adopts seed_schedule placeholder rows;
- the parity oracle re-scores the season with resolve_pick() inside a
  SAVEPOINT that is always rolled back — zero diffs on a consistent file,
  a named diff on a perturbed one, never a commit and never an email.
"""
import secrets
import sqlite3
from unittest.mock import patch

import pytest
from sqlalchemy import delete, func, select

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
from games.golf.services.legacy_import import (
    import_season,
    load_snapshot,
    match_users,
    open_legacy,
    resolve_users_readonly,
    run_import,
    verify_scoring,
)
from models.user import User
from tests._golf_legacy_fixtures import PASSWORDS, build_legacy_db, default_dataset

SEASON = 2026
GOLF_TABLES = (GolfEnrollment, GolfPlayer, GolfTournament, GolfTournamentField,
               GolfTournamentResult, GolfSeasonPlayerUsage, GolfPick)
# Generated so no literal password sits beside a username (GitGuardian).
PLATFORM_PW = secrets.token_urlsafe(16)


# --- helpers ---------------------------------------------------------------

def _seed_platform_users():
    """The platform side of the fixture: one email match (different case) and
    one username collision (same username, different email)."""
    casey = User(username='caseyplat', email='casey@example.com', display_name='Casey Platform')
    casey.set_password(PLATFORM_PW)
    brock = User(username='brock', email='brock@platform.test')
    brock.set_password(PLATFORM_PW)
    db.session.add_all([casey, brock])
    db.session.commit()
    return casey, brock


def _counts():
    return {m.__tablename__: db.session.scalar(select(func.count()).select_from(m)) for m in GOLF_TABLES} | {
        'users': db.session.scalar(select(func.count()).select_from(User))}


def _legacy(tmp_path, dataset=None):
    return build_legacy_db(tmp_path / 'legacy.db', dataset)


def _perturb(path, sql, params=()):
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _import(path, **kw):
    kw.setdefault('season', SEASON)
    kw.setdefault('links', {'brock': 'brock'})
    return run_import(str(path), **kw)


def _user(username):
    return db.session.scalars(select(User).where(func.lower(User.username) == username.lower())).one()


def _pick(username, tourn_api_id):
    u = _user(username)
    t = db.session.scalars(select(GolfTournament).filter_by(api_tourn_id=tourn_api_id, season_year=SEASON)).one()
    return db.session.scalars(select(GolfPick).filter_by(user_id=u.id, tournament_id=t.id)).one()


def _player(api_id):
    return db.session.scalars(select(GolfPlayer).filter_by(api_player_id=api_id)).one()


# --- matching --------------------------------------------------------------

def test_dry_run_writes_nothing_and_prints_matching_report(app, tmp_path):
    _seed_platform_users()
    before = _counts()

    report = _import(_legacy(tmp_path), dry_run=True)

    assert report.outcome == 'dry-run'
    assert _counts() == before
    text = report.render()
    assert 'attach' in text and 'create' in text and 'link' in text
    assert report.parity is not None and report.parity.diff_count == 0


def test_email_match_folds_case_and_attaches_existing_user(app, tmp_path):
    casey, _ = _seed_platform_users()
    conn = open_legacy(str(_legacy(tmp_path)))
    snapshot = load_snapshot(conn, SEASON, str(tmp_path / 'legacy.db'))

    plan = match_users(snapshot.users)

    by_name = {m.legacy_username: m for m in plan.matches}
    assert by_name['Casey'].action == 'attach'
    assert by_name['Casey'].platform_user_id == casey.id
    assert by_name['dana'].action == 'create'
    assert by_name['brock'].action == 'collision'
    assert plan.blocking


def test_attached_user_columns_are_untouched(app, tmp_path):
    casey, _ = _seed_platform_users()
    snapshot_hash = casey.password_hash

    report = _import(_legacy(tmp_path))

    assert report.outcome == 'committed'
    db.session.expire_all()
    casey = db.session.get(User, casey.id)
    assert casey.username == 'caseyplat'
    assert casey.display_name == 'Casey Platform'
    assert casey.password_hash == snapshot_hash
    assert casey.check_password(PLATFORM_PW)
    assert db.session.scalar(select(User).filter_by(username='Casey')) is None


def test_username_collision_is_flagged_and_aborts_before_any_write(app, tmp_path):
    _seed_platform_users()
    before = _counts()

    report = run_import(str(_legacy(tmp_path)), season=SEASON)

    assert report.outcome == 'blocked'
    assert any('brock' in msg for msg in report.plan.blocking)
    assert _counts() == before


def test_link_option_attaches_collision_to_platform_user(app, tmp_path):
    _, brock = _seed_platform_users()

    report = _import(_legacy(tmp_path), links={'brock': 'brock'})

    assert report.outcome == 'committed'
    assert db.session.scalar(
        select(func.count()).select_from(User).where(func.lower(User.username) == 'brock')) == 1
    enrollment = db.session.scalars(select(GolfEnrollment).filter_by(user_id=brock.id, season_year=SEASON)).one()
    assert enrollment.total_points == 750_000


def test_rename_option_creates_collision_under_new_username(app, tmp_path):
    _, brock = _seed_platform_users()

    report = _import(_legacy(tmp_path), links={}, renames={'brock': 'brock_golf'})

    assert report.outcome == 'committed'
    renamed = _user('brock_golf')
    assert renamed.id != brock.id
    assert renamed.email == 'brock@legacy.test'
    assert renamed.check_password(PASSWORDS['brock'])   # the scrypt hash carried
    assert db.session.scalar(
        select(func.count()).select_from(GolfEnrollment).where(GolfEnrollment.user_id == brock.id)) == 0


def test_two_legacy_users_resolving_to_one_platform_user_aborts(app, tmp_path):
    _seed_platform_users()
    before = _counts()

    report = _import(_legacy(tmp_path), links={'brock': 'caseyplat'})   # Casey attaches there too

    assert report.outcome == 'blocked'
    assert _counts() == before


def test_import_refuses_unknown_link_or_rename_target(app, tmp_path):
    _seed_platform_users()

    report = _import(_legacy(tmp_path), links={'brock': 'nobody-here'})
    assert report.outcome == 'blocked'

    report = _import(_legacy(tmp_path), links={}, renames={'brock': 'caseyplat'})   # taken
    assert report.outcome == 'blocked'


def test_new_user_without_email_is_blocked(app, tmp_path):
    """A create/rename with no email can't mint an account (User.email is
    NOT NULL + UNIQUE). The legacy DDL forbids NULL, so '' is the reachable
    shape; normalize_identifier folds '' and None identically."""
    _seed_platform_users()
    data = default_dataset()
    for u in data['user']:
        if u['username'] == 'dana':          # dana matches nothing → would 'create'
            u['email'] = ''
    before = _counts()

    report = _import(_legacy(tmp_path, data))

    assert report.outcome == 'blocked'
    assert any('dana' in msg and 'no email' in msg for msg in report.plan.blocking)
    assert _counts() == before


# --- users -----------------------------------------------------------------

def test_new_user_carries_hash_verbatim_and_login_succeeds(app, client, tmp_path):
    _seed_platform_users()
    data = default_dataset()             # hashes are salted per call — build once, import that
    legacy_hashes = {u['username']: u['password_hash'] for u in data['user']}

    _import(_legacy(tmp_path, data))

    dana = _user('dana')
    assert dana.password_hash == legacy_hashes['dana']
    assert dana.password_hash.startswith('pbkdf2:sha256')
    assert dana.check_password(PASSWORDS['dana'])
    resp = client.post('/login', data={'username': 'dana', 'password': PASSWORDS['dana']})
    assert resp.status_code == 302
    assert 'login' not in resp.headers['Location']


def test_new_user_defaults(app, tmp_path):
    _seed_platform_users()
    _import(_legacy(tmp_path))

    dana = _user('dana')
    assert dana.auth_id and len(dana.auth_id) == 32
    assert dana.email == 'dana@legacy.test'
    assert dana.display_name == 'Dana D'
    assert dana.avatar_emoji is None and dana.phone is None
    assert dana.is_admin is False and dana.has_paid is False
    assert dana.created_at.year == 2026 and dana.created_at.month == 1 and dana.created_at.day == 7


# --- enrollments -----------------------------------------------------------

def test_enrollment_carries_totals_has_paid_penalty_paid_not_is_admin(app, tmp_path):
    casey, _ = _seed_platform_users()
    report = _import(_legacy(tmp_path))

    e = db.session.scalars(select(GolfEnrollment).filter_by(user_id=casey.id, season_year=SEASON)).one()
    assert e.total_points == 1_150_000
    assert e.has_paid is True
    assert e.penalty_paid == 15
    assert e.is_admin is False          # legacy is_admin=1 is the standalone's platform role, not carried
    assert e.created_at.day == 5        # legacy user.created_at
    assert 'Casey' in report.plan.legacy_admins

    dana = db.session.scalars(select(GolfEnrollment).filter_by(user_id=_user('dana').id, season_year=SEASON)).one()
    assert dana.has_paid is False
    assert dana.penalty_owed() == 15 and dana.penalty_outstanding() == 15


# --- picks / results / tournaments ----------------------------------------

def test_pick_fields_verbatim_incl_override_penalty_null_active_timestamps(app, tmp_path):
    _seed_platform_users()
    data = default_dataset()
    # A fourth member whose primary has no result row: the one unresolved pick
    # shape in the real file (active/points NULL, nothing used, no usage row).
    data['user'].append({'id': 4, 'username': 'evan', 'email': 'evan@legacy.test',
                             'password_hash': data['user'][2]['password_hash'], 'display_name': None,
                             'total_points': 0, 'is_admin': 0, 'has_paid': 1,
                             'created_at': '2026-01-08 09:00:00.000000', 'penalty_paid': 0})
    data['player'].append({'id': 15, 'api_player_id': 'p5', 'first_name': 'Ed', 'last_name': 'Five',
                               'is_amateur': 0, 'created_at': '2026-01-10 12:00:00.000000',
                               'updated_at': '2026-01-10 12:00:00.000000'})
    data['tournament_field'].append({'id': 39, 'tournament_id': 21, 'player_id': 15, 'is_alternate': 0,
                                         'created_at': '2026-01-10 12:00:00.000000'})
    data['pick'].append({'id': 57, 'user_id': 4, 'tournament_id': 21, 'primary_player_id': 15,
                             'backup_player_id': 11, 'active_player_id': None, 'points_earned': None,
                             'primary_used': 0, 'backup_used': 0, 'created_at': '2026-01-14 12:00:00.000000',
                             'updated_at': '2026-01-14 12:00:00.000000', 'admin_override': 0,
                             'admin_override_note': None, 'penalty_triggered': 0})

    report = _import(_legacy(tmp_path, data))
    assert report.outcome == 'committed', report.render()

    override = _pick('brock', '002')
    assert override.admin_override is True
    assert override.admin_override_note == 'late pick, texted in'
    assert override.points_earned == 750_000 and override.primary_used is True

    penalty = _pick('dana', '002')
    assert penalty.penalty_triggered is True and penalty.points_earned == 0

    backup = _pick('caseyplat', '001')
    assert backup.active_player_id == _player('p1').id
    assert backup.primary_used is False and backup.backup_used is True
    assert backup.created_at.isoformat() == '2026-01-10T12:00:00'
    assert backup.updated_at.isoformat() == '2026-04-13T03:54:18.704821'

    unresolved = _pick('evan', '001')
    assert unresolved.active_player_id is None and unresolved.points_earned is None
    assert unresolved.primary_used is False and unresolved.backup_used is False
    assert db.session.scalar(select(func.count()).select_from(GolfSeasonPlayerUsage)
                             .where(GolfSeasonPlayerUsage.user_id == _user('evan').id)) == 0


def test_result_status_strings_verbatim(app, tmp_path):
    _seed_platform_users()
    _import(_legacy(tmp_path))

    t1 = db.session.scalars(select(GolfTournament).filter_by(api_tourn_id='001', season_year=SEASON)).one()
    r = db.session.scalars(select(GolfTournamentResult).filter_by(tournament_id=t1.id, player_id=_player('p4').id)).one()
    assert r.status == 'CUT'                      # legacy casing anomaly, not normalised
    assert r.final_position == 'CUT' and r.score_to_par == 3 and r.rounds_completed == 2
    wd = db.session.scalars(select(GolfTournamentResult).filter_by(tournament_id=t1.id, player_id=_player('p2').id)).one()
    assert wd.status == 'wd' and wd.score_to_par is None
    assert t1.last_reminder_type == '1h' and t1.purse == 8_700_000
    assert t1.pick_deadline.isoformat() == '2026-01-15T06:50:00'


def test_tournament_adopts_seed_schedule_placeholder_row(app, tmp_path):
    from games.golf.services.sync import seed_schedule
    _seed_platform_users()
    seed_schedule(SEASON)
    assert db.session.scalar(select(func.count()).select_from(GolfTournament)) == 32

    report = _import(_legacy(tmp_path))

    assert report.outcome == 'committed', report.render()
    assert db.session.scalar(select(func.count()).select_from(GolfTournament)) == 32  # adopted, not duplicated
    wk1 = db.session.scalars(select(GolfTournament).filter_by(season_year=SEASON, week_number=1)).one()
    assert wk1.api_tourn_id == '001' and wk1.name == 'Sony Open in Hawaii'
    wk2 = db.session.scalars(select(GolfTournament).filter_by(season_year=SEASON, week_number=2)).one()
    assert wk2.api_tourn_id == '002' and wk2.name == 'Masters Tournament' and wk2.is_major is True
    assert report.counts['golf_tournament'] == {'created': 0, 'changed': 2}


def test_recap_email_sent_forced_true(app, tmp_path):
    _seed_platform_users()
    report = _import(_legacy(tmp_path))

    t1 = db.session.scalars(select(GolfTournament).filter_by(api_tourn_id='001', season_year=SEASON)).one()
    assert t1.recap_email_sent is True               # legacy 0
    assert t1.picks_open_notified is True and t1.field_alert_sent is False   # verbatim
    assert 'recap_email_sent' in report.render()


def test_reimport_is_idempotent(app, tmp_path):
    _seed_platform_users()
    path = _legacy(tmp_path)
    first = _import(path)
    assert first.outcome == 'committed'
    after_first = _counts()
    stamps = {p.id: p.updated_at for p in db.session.scalars(select(GolfPick)).all()}

    second = _import(path)

    assert second.outcome == 'committed'
    assert _counts() == after_first
    assert all(v == {'created': 0, 'changed': 0} for v in second.counts.values()), second.counts
    db.session.expire_all()
    assert {p.id: p.updated_at for p in db.session.scalars(select(GolfPick)).all()} == stamps


def test_import_refuses_non_finalized_season(app, tmp_path):
    _seed_platform_users()
    data = default_dataset()
    data['tournament'][1]['results_finalized'] = 0
    before = _counts()

    report = _import(_legacy(tmp_path, data))

    assert report.outcome == 'blocked'
    assert any('Masters' in msg for msg in report.plan.blocking)
    assert _counts() == before


# --- the parity oracle -----------------------------------------------------

def test_oracle_zero_diffs_on_consistent_fixture(app, tmp_path):
    _seed_platform_users()
    _import(_legacy(tmp_path))

    parity = verify_scoring(SEASON)

    assert parity.diff_count == 0
    assert parity.picks_checked == 6 and parity.enrollments_checked == 3
    assert parity.overrides_checked == 1
    assert parity.usage_ok is True


def test_oracle_reports_perturbed_pick_points(app, tmp_path):
    _seed_platform_users()
    path = _legacy(tmp_path)
    _perturb(path, 'UPDATE pick SET points_earned = points_earned + 1 WHERE id = 51')
    before = _counts()

    report = _import(path)

    assert report.outcome == 'refused'
    assert _counts() == before                      # nothing committed
    fields = {(d.kind, d.field) for d in report.parity.diffs}
    assert ('pick', 'points_earned') in fields


def test_oracle_reports_perturbed_enrollment_total(app, tmp_path):
    _seed_platform_users()
    path = _legacy(tmp_path)
    _perturb(path, 'UPDATE user SET total_points = 1 WHERE id = 3')

    report = _import(path)

    assert report.outcome == 'refused'
    assert any(d.kind == 'enrollment' and d.field == 'total_points' for d in report.parity.diffs)


def test_oracle_reports_usage_set_mismatch(app, tmp_path):
    _seed_platform_users()
    path = _legacy(tmp_path)
    _perturb(path, 'DELETE FROM season_player_usage WHERE id = 66')

    report = _import(path)

    assert report.outcome == 'refused'
    assert report.parity.usage_ok is False
    assert any(d.kind == 'usage' for d in report.parity.diffs)


def test_import_refuses_to_commit_on_diffs_without_force(app, tmp_path):
    _seed_platform_users()
    path = _legacy(tmp_path)
    _perturb(path, 'UPDATE pick SET points_earned = points_earned + 1 WHERE id = 51')

    refused = _import(path)
    assert refused.outcome == 'refused' and db.session.scalar(select(func.count()).select_from(GolfPick)) == 0

    forced = _import(path, force=True)
    assert forced.outcome == 'committed' and forced.parity.diff_count == 1
    assert _pick('caseyplat', '001').points_earned == 1_000_001    # the legacy value, verbatim


def test_oracle_never_commits_or_emails(app, tmp_path):
    _seed_platform_users()
    _import(_legacy(tmp_path))
    pick = _pick('caseyplat', '001')
    pick.points_earned = 5                      # a stored value the resolver would "fix"
    db.session.commit()
    pick_id = pick.id

    with patch('games.golf.services.reminders.send_results_recap_email') as recap:
        parity = verify_scoring(SEASON)

    recap.assert_not_called()
    assert parity.diff_count == 1
    db.session.expire_all()
    assert db.session.get(GolfPick, pick_id).points_earned == 5    # resolver's write was rolled back


def test_oracle_with_snapshot_checks_column_fidelity(app, tmp_path):
    """verify-legacy PATH adds layer 1: every stored column vs the file."""
    _seed_platform_users()
    path = _legacy(tmp_path)
    _import(path)
    r = db.session.scalar(select(GolfTournamentResult).filter_by(player_id=_player('p3').id))
    r.final_position = 'T6'
    db.session.commit()

    parity = verify_scoring(SEASON, legacy_path=str(path))

    assert parity.fidelity_checked is True
    assert any(d.kind == 'golf_tournament_result' and d.field == 'final_position' for d in parity.diffs)


def test_fidelity_reports_missing_player_instead_of_raising(app, tmp_path):
    """check_only must emit a diff — never a KeyError — when the platform lacks
    a player that a legacy pick references as its primary/backup (p1 is both a
    backup in pick 51 and a primary in pick 56). That is exactly the corrupt
    state `flask golf verify-legacy PATH` exists to report."""
    _seed_platform_users()
    path = _legacy(tmp_path)
    _import(path)

    # Core delete (no ORM cascade/nullify): drop only the player row, leaving
    # the picks' foreign keys dangling — the platform-missing shape.
    db.session.execute(delete(GolfPlayer).where(GolfPlayer.api_player_id == 'p1'))
    db.session.commit()

    conn = open_legacy(str(path))
    snapshot = load_snapshot(conn, SEASON, str(path))
    conn.close()

    _, diffs = import_season(snapshot, resolve_users_readonly(snapshot.users), SEASON, check_only=True)

    kinds = {d.kind for d in diffs}
    assert 'golf_player' in kinds        # the player loop flags the missing row
    assert 'golf_pick' in kinds          # the guarded pick loop reports it, never KeyErrors


# --- CLI -------------------------------------------------------------------

def test_import_legacy_cli_dry_run_and_collision_exit_codes(app, tmp_path):
    _seed_platform_users()
    path = str(_legacy(tmp_path))
    runner = app.test_cli_runner()

    blocked = runner.invoke(args=['golf', 'import-legacy', path, '--dry-run'])
    assert blocked.exit_code == 1, blocked.output
    assert 'brock' in blocked.output

    ok = runner.invoke(args=['golf', 'import-legacy', path, '--dry-run', '--link', 'brock=brock'])
    assert ok.exit_code == 0, ok.output
    assert 'DRY RUN' in ok.output and 'diffs: 0' in ok.output
    assert db.session.scalar(select(func.count()).select_from(GolfPick)) == 0


def test_import_legacy_cli_rejects_a_repeated_mapping_key(app, tmp_path):
    """A duplicate --link/--rename key must abort before any write — the last
    value would otherwise silently win and file the account to the wrong user."""
    _seed_platform_users()
    path = str(_legacy(tmp_path))
    runner = app.test_cli_runner()

    dup = runner.invoke(args=['golf', 'import-legacy', path,
                              '--link', 'brock=brock', '--link', 'brock=caseyplat'])

    assert dup.exit_code == 1, dup.output
    assert 'more than once' in dup.output
    assert db.session.scalar(select(func.count()).select_from(GolfPick)) == 0


def test_verify_legacy_cli_is_read_only_and_exits_nonzero_on_diff(app, tmp_path):
    _seed_platform_users()
    path = str(_legacy(tmp_path))
    runner = app.test_cli_runner()
    assert runner.invoke(args=['golf', 'import-legacy', path, '--link', 'brock=brock']).exit_code == 0

    clean = runner.invoke(args=['golf', 'verify-legacy', path])
    assert clean.exit_code == 0, clean.output

    pick = _pick('caseyplat', '001')
    pick.points_earned = 5
    db.session.commit()
    pick_id = pick.id

    dirty = runner.invoke(args=['golf', 'verify-legacy'])
    assert dirty.exit_code == 1, dirty.output
    db.session.expire_all()
    assert db.session.get(GolfPick, pick_id).points_earned == 5


@pytest.mark.parametrize('season', [2025])
def test_import_refuses_a_season_the_file_does_not_hold(app, tmp_path, season):
    _seed_platform_users()
    report = run_import(str(_legacy(tmp_path)), season=season, links={'brock': 'brock'})
    assert report.outcome == 'blocked'
