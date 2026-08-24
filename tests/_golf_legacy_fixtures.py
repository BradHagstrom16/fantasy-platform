"""Builders for a legacy-shaped Golf Pick 'Em SQLite file (Phase I import tests).

The DDL below is the retired standalone app's schema verbatim (``sqlite3
golf_pickem.db .schema`` at alembic head ``c368002569a2``), so the import
under test reads exactly the column names, boolean-as-int and ISO-string
timestamp conventions the real file uses. ``default_dataset()`` is a small,
internally consistent season: every pick's resolution fields, every usage
row and every ``user.total_points`` agree with what ``GolfPick.resolve_pick``
would derive, so the parity oracle reports zero diffs on it — the tests that
want a diff perturb the dict (or the file) deliberately.
"""
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

LEGACY_ALEMBIC_HEAD = 'c368002569a2'

LEGACY_DDL = """
CREATE TABLE "user" (
    id INTEGER NOT NULL,
    username VARCHAR(80) NOT NULL,
    email VARCHAR(120) NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    display_name VARCHAR(100),
    total_points INTEGER,
    is_admin BOOLEAN,
    has_paid BOOLEAN,
    created_at DATETIME,
    penalty_paid INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (username),
    UNIQUE (email)
);
CREATE TABLE player (
    id INTEGER NOT NULL,
    api_player_id VARCHAR(20) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    is_amateur BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME,
    PRIMARY KEY (id),
    UNIQUE (api_player_id)
);
CREATE TABLE "tournament" (
    id INTEGER NOT NULL,
    api_tourn_id VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    season_year INTEGER NOT NULL,
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    pick_deadline DATETIME,
    purse INTEGER,
    is_team_event BOOLEAN,
    status VARCHAR(20),
    week_number INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    results_finalized BOOLEAN DEFAULT 0,
    is_major BOOLEAN DEFAULT 0,
    picks_open_notified BOOLEAN DEFAULT 0,
    field_alert_sent BOOLEAN DEFAULT 0,
    recap_email_sent BOOLEAN DEFAULT 0 NOT NULL,
    last_reminder_type VARCHAR(10),
    PRIMARY KEY (id),
    CONSTRAINT unique_tournament_per_season UNIQUE (api_tourn_id, season_year)
);
CREATE TABLE tournament_field (
    id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    is_alternate BOOLEAN,
    created_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT unique_player_tournament_field UNIQUE (tournament_id, player_id),
    FOREIGN KEY(tournament_id) REFERENCES tournament (id),
    FOREIGN KEY(player_id) REFERENCES player (id)
);
CREATE TABLE tournament_result (
    id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    final_position VARCHAR(20),
    earnings INTEGER,
    rounds_completed INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    score_to_par INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT unique_player_tournament_result UNIQUE (tournament_id, player_id),
    FOREIGN KEY(tournament_id) REFERENCES tournament (id),
    FOREIGN KEY(player_id) REFERENCES player (id)
);
CREATE TABLE season_player_usage (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    season_year INTEGER NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT unique_player_usage UNIQUE (user_id, player_id, season_year),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(player_id) REFERENCES player (id)
);
CREATE TABLE "pick" (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    primary_player_id INTEGER NOT NULL,
    backup_player_id INTEGER NOT NULL,
    active_player_id INTEGER,
    points_earned INTEGER,
    primary_used BOOLEAN,
    backup_used BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME,
    admin_override BOOLEAN DEFAULT 0,
    admin_override_note VARCHAR(200),
    penalty_triggered BOOLEAN DEFAULT 0 NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT unique_user_tournament_pick UNIQUE (user_id, tournament_id),
    FOREIGN KEY(backup_player_id) REFERENCES player (id),
    FOREIGN KEY(tournament_id) REFERENCES tournament (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(primary_player_id) REFERENCES player (id),
    FOREIGN KEY(active_player_id) REFERENCES player (id)
);
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
"""

# Plaintexts the fixture's hashes were generated from, so login tests can
# prove the hash carried verbatim.
PASSWORDS = {'Casey': 'casey-pw', 'brock': 'brock-pw', 'dana': 'dana-pw'}

_T = '2026-01-10 12:00:00.000000'   # a legacy-style naive ISO timestamp w/ microseconds
_T2 = '2026-04-13 03:54:18.704821'


def default_dataset():
    """A consistent two-event season: 3 members, 4 golfers, one major.

    Resolution facts the oracle re-derives (all agree with resolve_pick):
      Casey  wk1: primary P2 WD'd early -> backup P1 activates, $1,000,000
             wk2 (major): primary P3 T5 -> $100,000 x1.5 = $150,000     total 1,150,000
      brock  wk1: primary P4 'CUT' (legacy uppercase anomaly) -> primary counts, $0
             wk2 (major): primary P2 wins -> $500,000 x1.5 = $750,000 (admin override)  total 750,000
      dana   wk1: primary P3 -> $200,000
             wk2 (major): primary P1 cut -> $0 + the $15 penalty          total 200,000
    Usage = exactly the active players. Casey is the legacy admin (id 1).
    """
    return {
        'user': [
            {'id': 1, 'username': 'Casey', 'email': 'CASEY@Example.com',
                 'password_hash': generate_password_hash(PASSWORDS['Casey'], method='pbkdf2:sha256'),
                 'display_name': 'Sun Day Regrets', 'total_points': 1_150_000, 'is_admin': 1, 'has_paid': 1,
                 'created_at': '2026-01-05 09:00:00.000000', 'penalty_paid': 15},
            {'id': 2, 'username': 'brock', 'email': 'brock@legacy.test',
                 'password_hash': generate_password_hash(PASSWORDS['brock'], method='scrypt'),
                 'display_name': None, 'total_points': 750_000, 'is_admin': 0, 'has_paid': 1,
                 'created_at': '2026-01-06 09:00:00.000000', 'penalty_paid': 0},
            {'id': 3, 'username': 'dana', 'email': 'dana@legacy.test',
                 'password_hash': generate_password_hash(PASSWORDS['dana'], method='pbkdf2:sha256'),
                 'display_name': 'Dana D', 'total_points': 200_000, 'is_admin': 0, 'has_paid': 0,
                 'created_at': '2026-01-07 09:00:00.000000', 'penalty_paid': 0},
        ],
        'player': [
            {'id': 11, 'api_player_id': 'p1', 'first_name': 'Ace', 'last_name': 'One', 'is_amateur': 0, 'created_at': _T, 'updated_at': _T},
            {'id': 12, 'api_player_id': 'p2', 'first_name': 'Bo', 'last_name': 'Two', 'is_amateur': 0, 'created_at': _T, 'updated_at': _T},
            {'id': 13, 'api_player_id': 'p3', 'first_name': 'Cy', 'last_name': 'Three', 'is_amateur': 0, 'created_at': _T, 'updated_at': _T},
            {'id': 14, 'api_player_id': 'p4', 'first_name': 'Di', 'last_name': 'Four', 'is_amateur': 0, 'created_at': _T, 'updated_at': _T},
        ],
        'tournament': [
            {'id': 21, 'api_tourn_id': '001', 'name': 'Sony Open in Hawaii', 'season_year': 2026,
                 'start_date': '2026-01-15 00:00:00.000000', 'end_date': '2026-01-18 00:00:00.000000',
                 'pick_deadline': '2026-01-15 06:50:00.000000', 'purse': 8_700_000, 'is_team_event': 0,
                 'status': 'complete', 'week_number': 1, 'created_at': _T, 'updated_at': _T2,
                 'results_finalized': 1, 'is_major': 0, 'picks_open_notified': 1, 'field_alert_sent': 0,
                 'recap_email_sent': 0, 'last_reminder_type': '1h'},
            {'id': 22, 'api_tourn_id': '002', 'name': 'Masters Tournament', 'season_year': 2026,
                 'start_date': '2026-04-09 00:00:00.000000', 'end_date': '2026-04-12 00:00:00.000000',
                 'pick_deadline': '2026-04-09 07:00:00.000000', 'purse': 22_500_000, 'is_team_event': 0,
                 'status': 'complete', 'week_number': 2, 'created_at': _T, 'updated_at': _T2,
                 'results_finalized': 1, 'is_major': 1, 'picks_open_notified': 1, 'field_alert_sent': 0,
                 'recap_email_sent': 1, 'last_reminder_type': '1h'},
        ],
        'tournament_field': [
            {'id': i, 'tournament_id': t, 'player_id': p, 'is_alternate': 0, 'created_at': _T}
            for i, (t, p) in enumerate(
                [(21, 11), (21, 12), (21, 13), (21, 14), (22, 11), (22, 12), (22, 13), (22, 14)],
                start=31)
        ],
        'tournament_result': [
            {'id': 41, 'tournament_id': 21, 'player_id': 11, 'status': 'complete', 'final_position': '1', 'earnings': 1_000_000, 'rounds_completed': 4, 'created_at': _T, 'updated_at': _T2, 'score_to_par': -18},
            {'id': 42, 'tournament_id': 21, 'player_id': 12, 'status': 'wd', 'final_position': 'WD', 'earnings': 0, 'rounds_completed': 1, 'created_at': _T, 'updated_at': _T2, 'score_to_par': None},
            {'id': 43, 'tournament_id': 21, 'player_id': 13, 'status': 'complete', 'final_position': 'T5', 'earnings': 200_000, 'rounds_completed': 4, 'created_at': _T, 'updated_at': _T2, 'score_to_par': -12},
            {'id': 44, 'tournament_id': 21, 'player_id': 14, 'status': 'CUT', 'final_position': 'CUT', 'earnings': 0, 'rounds_completed': 2, 'created_at': _T, 'updated_at': _T2, 'score_to_par': 3},
            {'id': 45, 'tournament_id': 22, 'player_id': 11, 'status': 'cut', 'final_position': 'CUT', 'earnings': 0, 'rounds_completed': 2, 'created_at': _T, 'updated_at': _T2, 'score_to_par': 5},
            {'id': 46, 'tournament_id': 22, 'player_id': 12, 'status': 'complete', 'final_position': '1', 'earnings': 500_000, 'rounds_completed': 4, 'created_at': _T, 'updated_at': _T2, 'score_to_par': -10},
            {'id': 47, 'tournament_id': 22, 'player_id': 13, 'status': 'complete', 'final_position': 'T5', 'earnings': 100_000, 'rounds_completed': 4, 'created_at': _T, 'updated_at': _T2, 'score_to_par': -4},
            {'id': 48, 'tournament_id': 22, 'player_id': 14, 'status': 'complete', 'final_position': '20', 'earnings': 40_000, 'rounds_completed': 4, 'created_at': _T, 'updated_at': _T2, 'score_to_par': 1},
        ],
        'pick': [
            {'id': 51, 'user_id': 1, 'tournament_id': 21, 'primary_player_id': 12, 'backup_player_id': 11, 'active_player_id': 11, 'points_earned': 1_000_000, 'primary_used': 0, 'backup_used': 1, 'created_at': _T, 'updated_at': _T2, 'admin_override': 0, 'admin_override_note': None, 'penalty_triggered': 0},
            {'id': 52, 'user_id': 1, 'tournament_id': 22, 'primary_player_id': 13, 'backup_player_id': 14, 'active_player_id': 13, 'points_earned': 150_000, 'primary_used': 1, 'backup_used': 0, 'created_at': _T, 'updated_at': _T2, 'admin_override': 0, 'admin_override_note': None, 'penalty_triggered': 0},
            {'id': 53, 'user_id': 2, 'tournament_id': 21, 'primary_player_id': 14, 'backup_player_id': 13, 'active_player_id': 14, 'points_earned': 0, 'primary_used': 1, 'backup_used': 0, 'created_at': _T, 'updated_at': _T2, 'admin_override': 0, 'admin_override_note': None, 'penalty_triggered': 0},
            {'id': 54, 'user_id': 2, 'tournament_id': 22, 'primary_player_id': 12, 'backup_player_id': 14, 'active_player_id': 12, 'points_earned': 750_000, 'primary_used': 1, 'backup_used': 0, 'created_at': _T, 'updated_at': _T2, 'admin_override': 1, 'admin_override_note': 'late pick, texted in', 'penalty_triggered': 0},
            {'id': 55, 'user_id': 3, 'tournament_id': 21, 'primary_player_id': 13, 'backup_player_id': 14, 'active_player_id': 13, 'points_earned': 200_000, 'primary_used': 1, 'backup_used': 0, 'created_at': _T, 'updated_at': _T2, 'admin_override': 0, 'admin_override_note': None, 'penalty_triggered': 0},
            {'id': 56, 'user_id': 3, 'tournament_id': 22, 'primary_player_id': 11, 'backup_player_id': 12, 'active_player_id': 11, 'points_earned': 0, 'primary_used': 1, 'backup_used': 0, 'created_at': _T, 'updated_at': _T2, 'admin_override': 0, 'admin_override_note': None, 'penalty_triggered': 1},
        ],
        'season_player_usage': [
            {'id': 61, 'user_id': 1, 'player_id': 11, 'season_year': 2026, 'created_at': _T2},
            {'id': 62, 'user_id': 1, 'player_id': 13, 'season_year': 2026, 'created_at': _T2},
            {'id': 63, 'user_id': 2, 'player_id': 14, 'season_year': 2026, 'created_at': _T2},
            {'id': 64, 'user_id': 2, 'player_id': 12, 'season_year': 2026, 'created_at': _T2},
            {'id': 65, 'user_id': 3, 'player_id': 13, 'season_year': 2026, 'created_at': _T2},
            {'id': 66, 'user_id': 3, 'player_id': 11, 'season_year': 2026, 'created_at': _T2},
        ],
    }


def build_legacy_db(path, dataset=None, alembic_head=LEGACY_ALEMBIC_HEAD):
    """Write ``dataset`` (default: ``default_dataset()``) to a fresh SQLite file at ``path``."""
    path = Path(path)
    if path.exists():
        path.unlink()
    data = dataset if dataset is not None else default_dataset()
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(LEGACY_DDL)
        for table, rows in data.items():
            for row in rows:
                cols = list(row.keys())
                placeholders = ', '.join('?' for _ in cols)
                conn.execute(
                    f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({placeholders})',
                    [row[c] for c in cols],
                )
        if alembic_head:
            conn.execute('INSERT INTO alembic_version (version_num) VALUES (?)', (alembic_head,))
        conn.commit()
    finally:
        conn.close()
    return path
