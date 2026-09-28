"""
utils/backup_target.py
======================
deploy.sh's pre-migrate pg_dump (ADR-067), with the password kept out of bash.

    venv/bin/python -m utils.backup_target dump <file>   # run pg_dump into <file>
    venv/bin/python -m utils.backup_target url           # the URL, no password
    venv/bin/python -m utils.backup_target password      # the password alone

`dump` is deploy.sh's; `url` and `password` are for the restore runbook
(docs/superpowers/plans/2026-09-28-ops-hardening.md). pg_dump gets the
password as PGPASSWORD in its own environment (readable only by its owner and
root), never in its argv, which any local user can read from
/proc/<pid>/cmdline for as long as the dump runs.

Reads DATABASE_URL through config.py (the app's own reading of .env) and
parses it with SQLAlchemy, so a percent-encoded password comes out decoded.
Refuses anything that is not Postgres: a stray ENVIRONMENT=development leaves
the SQLite fallback behind, and there is nothing to dump there.
"""
import os
import subprocess
import sys

from sqlalchemy.engine import URL, make_url

from config import ProductionConfig


def split_url(raw):
    """(password, libpq URL without any password) for a Postgres URL.

    Raises ValueError for any other database.
    """
    url = make_url(raw)
    if not url.drivername.startswith('postgres'):
        raise ValueError(f'not a Postgres URL ({url.drivername})')
    # libpq also reads a password from the query string; take it out of there
    # too, or it would ride into the argv after all.
    query = dict(url.query)
    query_password = query.pop('password', None)
    # Rebuilt rather than url.set(password=None): set() reads None as "leave
    # it as it is", which would keep the password in the URL. libpq knows
    # neither SQLAlchemy's +driver suffix nor the bare `postgres` alias, so
    # both become plain postgresql://.
    bare = URL.create('postgresql', username=url.username, host=url.host,
                      port=url.port, database=url.database, query=query)
    return (url.password or query_password or '',
            bare.render_as_string(hide_password=False))


def dump(raw_url, out_file):
    """Run pg_dump (custom format) into out_file; return its exit code."""
    password, url = split_url(raw_url)
    env = dict(os.environ)
    if password:
        env['PGPASSWORD'] = password
    # 077: the dump holds every member's email, phone and password hash.
    os.umask(0o077)
    return subprocess.run(
        ['pg_dump', '--format=custom', '--file', out_file, '--dbname', url],
        env=env, check=False).returncode


def main(argv):
    usage = 'usage: python -m utils.backup_target {dump <file> | url | password}'
    if len(argv) < 2 or argv[1] not in ('dump', 'url', 'password') \
            or (argv[1] == 'dump') != (len(argv) == 3) or len(argv) > 3:
        print(usage, file=sys.stderr)
        return 2
    raw = ProductionConfig.SQLALCHEMY_DATABASE_URI
    try:
        if argv[1] == 'dump':
            return dump(raw, argv[2])
        password, url = split_url(raw)
    except ValueError as exc:
        print(f'DATABASE_URL is {exc}; nothing to back up.', file=sys.stderr)
        return 1
    print(url if argv[1] == 'url' else password)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
