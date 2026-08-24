"""Import the retired standalone Golf Pick 'Em's season into the ``golf_*`` tables.

Phase I of the golf roadmap (``docs/golf-pickem-launch-prep-roadmap-2026-06-30.md``,
ADR-055). The standalone app's SQLite file is a 1:1 ancestor of the platform
schema, so this is a table import — not the CFB-style JSON ledger — keyed on
natural keys throughout (never legacy ids: an explicit id would not advance a
Postgres sequence, and the next organic insert would collide).

Shape of a run (``run_import``):

1. ``load_snapshot`` reads the file read-only and refuses a season that is not
   fully ``complete`` + ``results_finalized``.
2. ``match_users`` maps each legacy member to a platform account by
   case-folded email; a username collision (no email match, username taken)
   blocks the run before any write unless resolved with ``--link``/``--rename``.
   Attached accounts are never modified.
3. ``import_season`` upserts every table, setting each mapped column
   explicitly — a no-op re-run emits no UPDATE and bumps no ``updated_at``.
   ``GolfEnrollment.is_admin`` is NOT carried (the legacy flag was the
   standalone's platform role) and ``recap_email_sent`` is forced True
   (``process_tournament_picks`` would otherwise mail a months-old recap).
4. ``verify_scoring`` — the parity oracle — re-runs ``GolfPick.resolve_pick``
   and ``calculate_total_points`` over the season inside a SAVEPOINT that is
   always rolled back, and diffs the result against the imported values. It
   never commits, and never calls ``process_tournament_picks`` (which does).
5. Dry-run rolls everything back; a real run commits only when the oracle is
   clean (or ``--force``).
"""
import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

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
from models.user import User
from utils.identifier import normalize_identifier

# Columns the import deliberately does NOT carry verbatim, with the reason
# printed in every report so the deviation is never silent.
FORCED_COLUMNS = {
    'golf_tournament.recap_email_sent': (
        'forced True — sync.process_tournament_picks() and the admin process-results '
        'route mail the recap whenever this is False; the legacy season already got '
        'its recaps'
    ),
    'golf_enrollment.is_admin': (
        'not carried — the legacy flag was the standalone\'s platform role; the '
        'platform column delegates game-admin over whatever season SEASON_YEAR '
        'points at'
    ),
}

RESOLUTION_FIELDS = ('active_player_id', 'points_earned', 'primary_used',
                     'backup_used', 'penalty_triggered')


class LegacyImportError(ValueError):
    """The file cannot be imported as asked (season not finalized, etc.)."""


# ── data carriers ─────────────────────────────────────────────────────────

@dataclass
class LegacySnapshot:
    path: str
    sha256: str
    alembic_head: str | None
    season: int
    users: list
    players: list
    tournaments: list
    fields: list
    results: list
    usage: list
    picks: list

    def problems(self):
        """Why this snapshot must not be imported (empty = fine)."""
        out = []
        if not self.tournaments:
            out.append(f'no tournaments for season {self.season} in {self.path}')
        for t in self.tournaments:
            if t['status'] != 'complete' or not _as_bool(t['results_finalized']):
                out.append(
                    f"{t['name']}: status={t['status']!r}, results_finalized="
                    f"{_as_bool(t['results_finalized'])} — only a finished season is importable"
                )
        return out


@dataclass
class UserMatch:
    legacy: dict
    action: str                       # attach | link | create | rename | collision
    platform_user_id: int | None = None
    platform_username: str | None = None
    new_username: str | None = None
    note: str = ''

    @property
    def legacy_username(self):
        return self.legacy['username']

    @property
    def hash_algorithm(self):
        return hash_algorithm(self.legacy['password_hash'])


@dataclass
class MatchPlan:
    matches: list = field(default_factory=list)
    blocking: list = field(default_factory=list)
    legacy_admins: list = field(default_factory=list)


@dataclass
class Diff:
    kind: str        # pick | enrollment | usage | <table> (fidelity)
    key: str
    field: str
    expected: object
    actual: object

    def render(self):
        return f'  {self.kind:<18} {self.key:<40} {self.field}: expected {self.expected!r}, got {self.actual!r}'


@dataclass
class ParityReport:
    diffs: list
    picks_checked: int = 0
    enrollments_checked: int = 0
    overrides_checked: int = 0
    unresolved_expected: int = 0
    usage_ok: bool = True
    fidelity_checked: bool = False

    @property
    def diff_count(self):
        return len(self.diffs)

    def render(self):
        lines = [
            'Parity oracle (resolve_pick re-run inside a rolled-back SAVEPOINT):',
            f'  picks re-scored: {self.picks_checked} (admin overrides: {self.overrides_checked})',
            f'  picks unresolved in the source too: {self.unresolved_expected}'
            ' (a primary with no result row — resolve_pick logs an ERROR for each and returns'
            ' False, which is parity with the stored NULLs)',
            f'  enrollment totals re-derived: {self.enrollments_checked}',
            f'  usage set matches resolved picks: {"yes" if self.usage_ok else "NO"}',
            f'  column fidelity vs file: {"checked" if self.fidelity_checked else "not requested"}',
            f'  diffs: {self.diff_count}',
        ]
        lines.extend(d.render() for d in self.diffs)
        return '\n'.join(lines)


@dataclass
class ImportReport:
    path: str
    sha256: str
    alembic_head: str | None
    season: int
    before: dict
    plan: MatchPlan
    counts: dict = field(default_factory=dict)
    parity: ParityReport | None = None
    outcome: str = 'blocked'          # blocked | dry-run | refused | committed
    dry_run: bool = False

    def render(self):
        lines = [
            f'Legacy Golf Pick \'Em import — season {self.season}',
            f'  source: {self.path}',
            f'  sha256: {self.sha256}',
            f'  legacy alembic head: {self.alembic_head or "(none)"}',
            '',
            'Platform rows BEFORE this run:',
        ]
        lines.extend(f'  {name:<26} {n}' for name, n in self.before.items())
        lines += ['', 'User matching (legacy username → platform account):']
        for m in self.plan.matches:
            target = m.platform_username or m.new_username or m.legacy_username
            lines.append(
                f'  {m.legacy_username:<28} {m.action:<10} → {target:<28} [{m.hash_algorithm}]'
                + (f'  {m.note}' if m.note else '')
            )
        if self.plan.legacy_admins:
            lines.append(f'  legacy admins (NOT carried to GolfEnrollment.is_admin): '
                         f'{", ".join(self.plan.legacy_admins)}')
        if self.plan.blocking:
            lines += ['', 'BLOCKED — nothing written:']
            lines.extend(f'  - {msg}' for msg in self.plan.blocking)
            return '\n'.join(lines)
        lines += ['', 'Rows written (created / changed):']
        lines.extend(f'  {name:<26} {c["created"]} / {c["changed"]}' for name, c in self.counts.items())
        lines += ['', 'Deliberate deviations from the file:']
        lines.extend(f'  {col}: {why}' for col, why in FORCED_COLUMNS.items())
        if self.parity is not None:
            lines += ['', self.parity.render()]
        lines.append('')
        if self.outcome == 'dry-run':
            lines.append('Outcome: DRY RUN — everything above was rolled back.')
        elif self.outcome == 'refused':
            lines.append('Outcome: REFUSED — oracle diffs; rolled back. Re-run with --force to commit anyway.')
        elif self.outcome == 'committed':
            lines.append('Outcome: COMMITTED.')
        return '\n'.join(lines)


# ── low-level helpers ─────────────────────────────────────────────────────

def open_legacy(path):
    """Read-only connection to the legacy SQLite file."""
    conn = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def hash_algorithm(password_hash):
    """The Werkzeug method prefix (``pbkdf2:sha256:600000``, ``scrypt:32768:8:1``)."""
    return (password_hash or '').split('$', 1)[0]


def _parse_dt(value):
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _as_bool(value):
    return bool(value) if value is not None else False


def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_snapshot(conn, season, path):
    """Every row the import needs, as plain dicts, for one season."""
    tournaments = _rows(conn, 'SELECT * FROM tournament WHERE season_year = ? ORDER BY week_number, id', (season,))
    t_ids = [t['id'] for t in tournaments]
    marks = ','.join('?' for _ in t_ids) or 'NULL'
    try:
        head = conn.execute('SELECT version_num FROM alembic_version').fetchone()
        alembic_head = head[0] if head else None
    except sqlite3.OperationalError:
        alembic_head = None
    return LegacySnapshot(
        path=str(path),
        sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        alembic_head=alembic_head,
        season=season,
        users=_rows(conn, 'SELECT * FROM user ORDER BY id'),
        players=_rows(conn, 'SELECT * FROM player ORDER BY id'),
        tournaments=tournaments,
        fields=_rows(conn, f'SELECT * FROM tournament_field WHERE tournament_id IN ({marks}) ORDER BY id', t_ids),
        results=_rows(conn, f'SELECT * FROM tournament_result WHERE tournament_id IN ({marks}) ORDER BY id', t_ids),
        usage=_rows(conn, 'SELECT * FROM season_player_usage WHERE season_year = ? ORDER BY id', (season,)),
        picks=_rows(conn, f'SELECT * FROM pick WHERE tournament_id IN ({marks}) ORDER BY id', t_ids),
    )


def _user_by_email(email):
    return db.session.scalar(select(User).where(func.lower(User.email) == normalize_identifier(email)))


def _user_by_username(username):
    return db.session.scalar(select(User).where(func.lower(User.username) == normalize_identifier(username)))


# ── user matching ─────────────────────────────────────────────────────────

def match_users(legacy_users, links=None, renames=None):
    """Decide, per legacy member, which platform account they become.

    attach   — a platform user with the same (case-folded) email exists
    link     — ``--link LEGACY=PLATFORM`` attached a collision by hand
    rename   — ``--rename LEGACY=NEW`` creates the collision under a new name
    create   — no match, username free
    collision — no email match but the username is taken: BLOCKS the run
    """
    links = dict(links or {})
    renames = dict(renames or {})
    plan = MatchPlan()
    known = {u['username'] for u in legacy_users}
    for opt, mapping in (('--link', links), ('--rename', renames)):
        for legacy_name in mapping:
            if legacy_name not in known:
                plan.blocking.append(f'{opt} {legacy_name}=…: no legacy user named {legacy_name!r}')

    for u in legacy_users:
        name = u['username']
        if _as_bool(u.get('is_admin')):
            plan.legacy_admins.append(name)
        by_email = _user_by_email(u['email'])
        if by_email is not None:
            note = '' if by_email.username == name else f'(legacy username {name!r})'
            plan.matches.append(UserMatch(u, 'attach', by_email.id, by_email.username, note=note))
            continue
        if name in links:
            target = _user_by_username(links[name])
            if target is None:
                plan.blocking.append(f'--link {name}={links[name]}: no platform user named {links[name]!r}')
                plan.matches.append(UserMatch(u, 'collision'))
            else:
                plan.matches.append(UserMatch(u, 'link', target.id, target.username))
            continue
        if name in renames:
            new_name = renames[name]
            if _user_by_username(new_name) is not None:
                plan.blocking.append(f'--rename {name}={new_name}: platform username {new_name!r} is taken')
                plan.matches.append(UserMatch(u, 'collision'))
            else:
                plan.matches.append(UserMatch(u, 'rename', new_username=new_name))
            continue
        taken = _user_by_username(name)
        if taken is not None:
            plan.matches.append(UserMatch(
                u, 'collision', note=f'platform user #{taken.id} {taken.username!r} has a different email'))
            plan.blocking.append(
                f'username collision: legacy {name!r} <{u["email"]}> vs platform #{taken.id} '
                f'{taken.username!r} — resolve with --link {name}=<platform username> '
                f'(same person) or --rename {name}=<new username>')
        else:
            plan.matches.append(UserMatch(u, 'create'))

    # Two legacy members must never land on one platform account, and two new
    # accounts must not fold to the same username.
    seen_targets, seen_names = {}, {}
    for m in plan.matches:
        if m.platform_user_id is not None:
            other = seen_targets.setdefault(m.platform_user_id, m.legacy_username)
            if other != m.legacy_username:
                plan.blocking.append(
                    f'legacy {other!r} and {m.legacy_username!r} both resolve to platform user '
                    f'#{m.platform_user_id} {m.platform_username!r}')
        if m.action in ('create', 'rename'):
            if not (m.legacy['email'] or '').strip():
                plan.blocking.append(
                    f'legacy {m.legacy_username!r} has no email — a new account needs one; '
                    f'resolve with --link {m.legacy_username}=<platform username> or fix the source file')
            folded = normalize_identifier(m.new_username or m.legacy_username)
            other = seen_names.setdefault(folded, m.legacy_username)
            if other != m.legacy_username:
                plan.blocking.append(f'legacy {other!r} and {m.legacy_username!r} would both create username {folded!r}')
    return plan


def apply_users(plan):
    """Create the ``create``/``rename`` accounts; return legacy id → User."""
    users = {}
    for m in plan.matches:
        if m.action in ('attach', 'link'):
            users[m.legacy['id']] = db.session.get(User, m.platform_user_id)
        elif m.action in ('create', 'rename'):
            fields = {
                'username': m.new_username or m.legacy['username'],
                'email': (m.legacy['email'] or '').strip().lower(),
                'password_hash': m.legacy['password_hash'],
                'display_name': m.legacy.get('display_name'),
            }
            created_at = _parse_dt(m.legacy.get('created_at'))
            if created_at is not None:          # else the model default (now) applies
                fields['created_at'] = created_at
            u = User(**fields)
            db.session.add(u)
            users[m.legacy['id']] = u
    db.session.flush()
    return users


def resolve_users_readonly(legacy_users):
    """legacy id → User for verification runs: by email, then by username."""
    users = {}
    for u in legacy_users:
        match = _user_by_email(u['email']) or _user_by_username(u['username'])
        if match is not None:
            users[u['id']] = match
    return users


# ── upserts ───────────────────────────────────────────────────────────────

def _sync(obj, desired, *, check_only, diffs, kind, key):
    """Set every mapped column explicitly; report what would change.

    Assigning an equal value leaves SQLAlchemy history clean, so an unchanged
    re-run emits no UPDATE and no ``onupdate`` fires. When something did
    change, ``updated_at`` is force-flagged so the legacy stamp — not
    ``onupdate``'s now() — is what lands.
    """
    changed = []
    for col, val in desired.items():
        cur = getattr(obj, col)
        if cur != val:
            if check_only:
                diffs.append(Diff(kind, key, col, val, cur))
            else:
                setattr(obj, col, val)
                changed.append(col)
    if changed and 'updated_at' in desired and 'updated_at' not in changed:
        flag_modified(obj, 'updated_at')
    return bool(changed)


def _bump(counts, table, created, changed):
    c = counts.setdefault(table, {'created': 0, 'changed': 0})
    if created:
        c['created'] += 1
    elif changed:
        c['changed'] += 1


def _missing(diffs, kind, key):
    diffs.append(Diff(kind, key, '<row>', 'present', 'missing'))


def import_season(snapshot, users, season, check_only=False):
    """Upsert every table (flush only). With ``check_only`` nothing is written
    and every column mismatch / missing row becomes a Diff instead."""
    counts, diffs = {}, []

    # players — keyed on api_player_id
    players = {}
    for p in snapshot.players:
        obj = db.session.scalar(select(GolfPlayer).filter_by(api_player_id=p['api_player_id']))
        desired = {'first_name': p['first_name'], 'last_name': p['last_name'],
                       'is_amateur': _as_bool(p['is_amateur']),
                       'created_at': _parse_dt(p['created_at']), 'updated_at': _parse_dt(p['updated_at'])}
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_player', p['api_player_id'])
                continue
            obj = GolfPlayer(api_player_id=p['api_player_id'], **desired)
            db.session.add(obj)
            _bump(counts, 'golf_player', True, False)
        else:
            _bump(counts, 'golf_player', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_player', key=p['api_player_id']))
        players[p['id']] = obj
    db.session.flush()

    # tournaments — (api_tourn_id, season) → adopt a seed_schedule placeholder → (name, season) → create
    tournaments = {}
    for t in snapshot.tournaments:
        key = f"wk{t['week_number']} {t['name']}"
        obj = db.session.scalar(select(GolfTournament).filter_by(api_tourn_id=t['api_tourn_id'], season_year=season))
        if obj is None and t['week_number'] is not None:
            placeholder = db.session.scalar(
                select(GolfTournament).filter_by(season_year=season, week_number=t['week_number']))
            if placeholder is not None and placeholder.api_tourn_id == f"{season}_{int(t['week_number']):02d}":
                obj = placeholder
        if obj is None:
            obj = db.session.scalar(select(GolfTournament).filter_by(name=t['name'], season_year=season))
        desired = {
            'api_tourn_id': t['api_tourn_id'], 'name': t['name'],
            'start_date': _parse_dt(t['start_date']), 'end_date': _parse_dt(t['end_date']),
            'pick_deadline': _parse_dt(t['pick_deadline']), 'purse': t['purse'],
            'is_team_event': _as_bool(t['is_team_event']), 'is_major': _as_bool(t['is_major']),
            'status': t['status'], 'results_finalized': _as_bool(t['results_finalized']),
            'picks_open_notified': _as_bool(t['picks_open_notified']),
            'field_alert_sent': _as_bool(t['field_alert_sent']),
            'recap_email_sent': True,                       # FORCED_COLUMNS
            'last_reminder_type': t['last_reminder_type'], 'week_number': t['week_number'],
            'created_at': _parse_dt(t['created_at']), 'updated_at': _parse_dt(t['updated_at']),
        }
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_tournament', key)
                continue
            obj = GolfTournament(season_year=season, **desired)
            db.session.add(obj)
            _bump(counts, 'golf_tournament', True, False)
        else:
            _bump(counts, 'golf_tournament', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_tournament', key=key))
        tournaments[t['id']] = obj
    db.session.flush()

    def _tp(row):
        return tournaments.get(row['tournament_id']), players.get(row['player_id'])

    # field — (tournament, player)
    for f in snapshot.fields:
        t, p = _tp(f)
        if t is None or p is None:
            continue
        key = f'{t.name} / {p.api_player_id}'
        obj = db.session.scalar(select(GolfTournamentField).filter_by(tournament_id=t.id, player_id=p.id))
        desired = {'created_at': _parse_dt(f['created_at'])}
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_tournament_field', key)
                continue
            db.session.add(GolfTournamentField(tournament_id=t.id, player_id=p.id, **desired))
            _bump(counts, 'golf_tournament_field', True, False)
        else:
            _bump(counts, 'golf_tournament_field', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_tournament_field', key=key))

    # results — (tournament, player); status strings verbatim, casing anomalies included
    for r in snapshot.results:
        t, p = _tp(r)
        if t is None or p is None:
            continue
        key = f'{t.name} / {p.api_player_id}'
        obj = db.session.scalar(select(GolfTournamentResult).filter_by(tournament_id=t.id, player_id=p.id))
        desired = {'status': r['status'], 'final_position': r['final_position'], 'earnings': r['earnings'],
                       'rounds_completed': r['rounds_completed'], 'score_to_par': r['score_to_par'],
                       'created_at': _parse_dt(r['created_at']), 'updated_at': _parse_dt(r['updated_at'])}
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_tournament_result', key)
                continue
            db.session.add(GolfTournamentResult(tournament_id=t.id, player_id=p.id, **desired))
            _bump(counts, 'golf_tournament_result', True, False)
        else:
            _bump(counts, 'golf_tournament_result', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_tournament_result', key=key))
    db.session.flush()

    # enrollments — (user, season); is_admin deliberately untouched
    legacy_users = {u['id']: u for u in snapshot.users}
    for legacy_id, user in users.items():
        u = legacy_users.get(legacy_id)
        if u is None:
            continue
        key = user.username
        obj = db.session.scalar(select(GolfEnrollment).filter_by(user_id=user.id, season_year=season))
        desired = {'total_points': u['total_points'] or 0, 'has_paid': _as_bool(u['has_paid']),
                       'penalty_paid': u['penalty_paid'] or 0, 'created_at': _parse_dt(u['created_at'])}
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_enrollment', key)
                continue
            db.session.add(GolfEnrollment(user_id=user.id, season_year=season, **desired))
            _bump(counts, 'golf_enrollment', True, False)
        else:
            _bump(counts, 'golf_enrollment', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_enrollment', key=key))

    # usage — (user, player, season), imported verbatim (the oracle checks it)
    for s in snapshot.usage:
        user, p = users.get(s['user_id']), players.get(s['player_id'])
        if user is None or p is None:
            continue
        key = f'{user.username} / {p.api_player_id}'
        obj = db.session.scalar(
            select(GolfSeasonPlayerUsage).filter_by(user_id=user.id, player_id=p.id, season_year=season))
        desired = {'created_at': _parse_dt(s['created_at'])}
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_season_player_usage', key)
                continue
            db.session.add(GolfSeasonPlayerUsage(user_id=user.id, player_id=p.id, season_year=season, **desired))
            _bump(counts, 'golf_season_player_usage', True, False)
        else:
            _bump(counts, 'golf_season_player_usage', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_season_player_usage', key=key))

    # picks — (user, tournament); resolution fields verbatim incl. NULLs
    for pk in snapshot.picks:
        user, t = users.get(pk['user_id']), tournaments.get(pk['tournament_id'])
        if user is None or t is None:
            continue
        key = f'{user.username} / {t.name}'
        obj = db.session.scalar(select(GolfPick).filter_by(user_id=user.id, tournament_id=t.id))
        primary = players.get(pk['primary_player_id'])
        backup = players.get(pk['backup_player_id'])
        if primary is None or backup is None:
            if check_only:
                _missing(diffs, 'golf_pick', key)
            continue
        active = players.get(pk['active_player_id']) if pk['active_player_id'] is not None else None
        desired = {
            'primary_player_id': primary.id,
            'backup_player_id': backup.id,
            'active_player_id': active.id if active is not None else None,
            'points_earned': pk['points_earned'],
            'primary_used': _as_bool(pk['primary_used']), 'backup_used': _as_bool(pk['backup_used']),
            'penalty_triggered': _as_bool(pk['penalty_triggered']),
            'admin_override': _as_bool(pk['admin_override']), 'admin_override_note': pk['admin_override_note'],
            'created_at': _parse_dt(pk['created_at']), 'updated_at': _parse_dt(pk['updated_at']),
        }
        if obj is None:
            if check_only:
                _missing(diffs, 'golf_pick', key)
                continue
            db.session.add(GolfPick(user_id=user.id, tournament_id=t.id, **desired))
            _bump(counts, 'golf_pick', True, False)
        else:
            _bump(counts, 'golf_pick', False,
                  _sync(obj, desired, check_only=check_only, diffs=diffs, kind='golf_pick', key=key))
    db.session.flush()

    for table in ('golf_player', 'golf_tournament', 'golf_tournament_field', 'golf_tournament_result',
                  'golf_enrollment', 'golf_season_player_usage', 'golf_pick'):
        counts.setdefault(table, {'created': 0, 'changed': 0})
    return counts, diffs


# ── the parity oracle ─────────────────────────────────────────────────────

def verify_scoring(season, legacy_path=None):
    """Re-score the season with the platform resolver and diff against what is stored.

    Runs ``GolfPick.resolve_pick()`` + ``GolfEnrollment.calculate_total_points()``
    inside a SAVEPOINT that is rolled back unconditionally, so nothing the
    resolver writes survives — and nothing here can send mail (the recap lives
    in ``process_tournament_picks``, which is never called). With
    ``legacy_path`` the file's columns are also compared against the stored
    rows (layer 1) before the scoring re-run (layer 2).
    """
    diffs = []
    fidelity = False
    if legacy_path:
        with closing(open_legacy(legacy_path)) as conn:
            snapshot = load_snapshot(conn, season, legacy_path)
        _, fidelity_diffs = import_season(
            snapshot, resolve_users_readonly(snapshot.users), season, check_only=True)
        diffs.extend(fidelity_diffs)
        fidelity = True

    picks = db.session.scalars(
        select(GolfPick).join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .where(GolfTournament.season_year == season)
        .order_by(GolfTournament.week_number, GolfPick.id)
    ).all()
    enrollments = db.session.scalars(
        select(GolfEnrollment).filter_by(season_year=season).order_by(GolfEnrollment.id)).all()
    expected_picks = {
        p.id: (p.active_player_id, p.points_earned, _as_bool(p.primary_used),
               _as_bool(p.backup_used), _as_bool(p.penalty_triggered))
        for p in picks
    }
    expected_totals = {e.id: (e.total_points or 0) for e in enrollments}
    expected_usage = {
        (u.user_id, u.player_id)
        for u in db.session.scalars(select(GolfSeasonPlayerUsage).filter_by(season_year=season)).all()
    }
    labels = {p.id: f'{p.user.username} wk{p.tournament.week_number} {p.tournament.name}' for p in picks}
    overrides = sum(1 for p in picks if p.admin_override)

    nested = db.session.begin_nested()
    try:
        for p in picks:
            p.resolve_pick()
            actual = (p.active_player_id, p.points_earned, _as_bool(p.primary_used),
                      _as_bool(p.backup_used), _as_bool(p.penalty_triggered))
            for name, exp, act in zip(RESOLUTION_FIELDS, expected_picks[p.id], actual, strict=True):
                if exp != act:
                    diffs.append(Diff('pick', labels[p.id], name, exp, act))
        for e in enrollments:
            total = e.calculate_total_points()
            if total != expected_totals[e.id]:
                diffs.append(Diff('enrollment', e.user.username, 'total_points', expected_totals[e.id], total))
        resolved_usage = {(p.user_id, p.active_player_id) for p in picks if p.active_player_id is not None}
        usage_ok = resolved_usage == expected_usage
        if not usage_ok:
            user_names = {u.id: u.username for u in db.session.scalars(select(User).where(
                User.id.in_({uid for uid, _ in resolved_usage | expected_usage}))).all()}
            for uid, pid in sorted(expected_usage - resolved_usage):
                diffs.append(Diff('usage', f'{user_names.get(uid, uid)} / player #{pid}', 'row', 'used', 'not derived'))
            for uid, pid in sorted(resolved_usage - expected_usage):
                diffs.append(Diff('usage', f'{user_names.get(uid, uid)} / player #{pid}', 'row', 'absent', 'derived'))
    finally:
        nested.rollback()
        db.session.expire_all()

    return ParityReport(diffs=diffs, picks_checked=len(picks), enrollments_checked=len(enrollments),
                        overrides_checked=overrides,
                        unresolved_expected=sum(1 for v in expected_picks.values() if v[0] is None),
                        usage_ok=usage_ok, fidelity_checked=fidelity)


# ── orchestration ─────────────────────────────────────────────────────────

def _platform_counts():
    return {
        'users': db.session.query(func.count(User.id)).scalar(),
        **{m.__tablename__: db.session.query(func.count(m.id)).scalar()
           for m in (GolfEnrollment, GolfPlayer, GolfTournament, GolfTournamentField,
                     GolfTournamentResult, GolfSeasonPlayerUsage, GolfPick)},
    }


def run_import(path, season=2026, *, dry_run=False, links=None, renames=None,
               verify=True, force=False):
    """The whole import as one transaction; see the module docstring."""
    with closing(open_legacy(path)) as conn:
        snapshot = load_snapshot(conn, season, path)
    report = ImportReport(path=str(path), sha256=snapshot.sha256, alembic_head=snapshot.alembic_head,
                          season=season, before=_platform_counts(), plan=MatchPlan(), dry_run=dry_run)
    report.plan = match_users(snapshot.users, links=links, renames=renames)
    report.plan.blocking = snapshot.problems() + report.plan.blocking
    if report.plan.blocking:
        db.session.rollback()
        report.outcome = 'blocked'
        return report

    try:
        users = apply_users(report.plan)
        report.counts, _ = import_season(snapshot, users, season)
        if verify:
            report.parity = verify_scoring(season)
        if dry_run:
            db.session.rollback()
            report.outcome = 'dry-run'
        elif report.parity is not None and report.parity.diff_count and not force:
            db.session.rollback()
            report.outcome = 'refused'
        else:
            db.session.commit()
            report.outcome = 'committed'
    except Exception:
        db.session.rollback()
        raise
    return report
