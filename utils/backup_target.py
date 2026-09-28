"""
utils/backup_target.py
======================
What deploy.sh's pre-migrate pg_dump connects to (ADR-067).

    venv/bin/python -m utils.backup_target

prints two lines: the database password, then the connection URL WITHOUT the
password. deploy.sh hands the first to pg_dump as PGPASSWORD (a process's
environment is readable only by its owner and root) and the second as
--dbname. A password in the URL would sit in pg_dump's argv, which any local
user can read from /proc/<pid>/cmdline for as long as the dump runs.

Reads DATABASE_URL through config.py (the app's own reading of .env) and
parses it with SQLAlchemy, so a percent-encoded password comes out decoded.
Exits 1 on anything that is not Postgres: a stray ENVIRONMENT=development
leaves the SQLite fallback behind, and there is nothing to dump there.
"""
import sys

from sqlalchemy.engine import URL, make_url

from config import ProductionConfig


def split_url(raw):
    """(password, libpq URL without the password) for a Postgres URL.

    Raises ValueError for any other database.
    """
    url = make_url(raw)
    if not url.drivername.startswith('postgres'):
        raise ValueError(f'not a Postgres URL ({url.drivername})')
    # libpq knows neither SQLAlchemy's +driver suffix nor the bare `postgres`
    # alias SQLAlchemy dropped, so both become plain postgresql://.
    # Rebuilt rather than url.set(password=None): set() reads None as "leave
    # it as it is", which would keep the password in the URL (and the argv).
    bare = URL.create('postgresql', username=url.username, host=url.host,
                      port=url.port, database=url.database, query=url.query)
    return url.password or '', bare.render_as_string(hide_password=False)


def main():
    try:
        password, url = split_url(ProductionConfig.SQLALCHEMY_DATABASE_URI)
    except ValueError as exc:
        print(f'DATABASE_URL is {exc}; nothing to back up.', file=sys.stderr)
        return 1
    print(password)
    print(url)
    return 0


if __name__ == '__main__':
    sys.exit(main())
