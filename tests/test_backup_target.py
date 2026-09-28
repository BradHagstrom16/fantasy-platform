"""deploy.sh's pre-migrate pg_dump (utils/backup_target.py, ADR-067).

The password must never reach pg_dump's argv (world-readable in /proc): it
leaves the URL, including a `?password=` query parameter, and goes to pg_dump
as PGPASSWORD. SQLAlchemy's driver spellings become plain libpq
`postgresql://`, and anything that is not Postgres is refused.
The shell side (dump before `db upgrade`, a failed dump stops the deploy) is
tests/test-deploy-guards.sh cases BA-BC.
"""
from unittest.mock import patch

import pytest

from utils.backup_target import dump, main, split_url

# Synthetic parts, assembled here so no credential-shaped literal sits in the
# repo for a secret scanner (or a reader) to mistake for a real one.
USER, HOST, DB = 'fixture_user', 'db.example.invalid', 'fixture_db'
PASSWORD = 'p@ss/fixture'                 # decoded form
ENCODED = 'p%40ss%2Ffixture'              # as it sits in a URL
BARE = f'postgresql://{USER}@{HOST}:5432/{DB}?sslmode=require'


def _url(scheme='postgresql', password=ENCODED):
    return f'{scheme}://{USER}:{password}@{HOST}:5432/{DB}?sslmode=require'


def test_password_is_split_out_and_decoded():
    assert split_url(_url()) == (PASSWORD, BARE)


def test_a_query_string_password_leaves_the_url_too():
    raw = f'postgresql://{USER}@{HOST}:5432/{DB}?sslmode=require&password={ENCODED}'
    assert split_url(raw) == (PASSWORD, BARE)


# ids avoid the word 'postgres': conftest reads it as the Postgres-only marker.
@pytest.mark.parametrize('scheme', ['postgresql+psycopg2', 'postgres'],
                         ids=['driver-suffix', 'bare-alias'])
def test_driver_spellings_become_plain_postgresql(scheme):
    assert split_url(_url(scheme))[1] == BARE


def test_a_url_without_a_password():
    assert split_url('postgresql:///ccc_local') == ('', 'postgresql:///ccc_local')


def test_sqlite_is_refused():
    with pytest.raises(ValueError, match='not a Postgres URL'):
        split_url('sqlite:////home/deploy/fantasy-platform/instance/fantasy_platform.db')


def test_dump_passes_the_password_in_the_environment_never_the_argv():
    with patch('utils.backup_target.subprocess.run') as run, \
            patch('utils.backup_target.os.umask') as umask:
        run.return_value.returncode = 0
        assert dump(_url(), '/tmp/x.dump.partial') == 0
    argv, env = run.call_args.args[0], run.call_args.kwargs['env']
    assert argv == ['pg_dump', '--format=custom', '--file', '/tmp/x.dump.partial',
                    '--dbname', BARE]
    assert not any(PASSWORD in a or ENCODED in a for a in argv)
    assert env['PGPASSWORD'] == PASSWORD
    umask.assert_called_once_with(0o077)


def test_dump_returns_pg_dumps_exit_code():
    with patch('utils.backup_target.subprocess.run') as run, \
            patch('utils.backup_target.os.umask'):
        run.return_value.returncode = 1
        assert dump(_url(), '/tmp/x') == 1


def test_dump_without_a_password_sets_no_pgpassword(monkeypatch):
    monkeypatch.delenv('PGPASSWORD', raising=False)
    with patch('utils.backup_target.subprocess.run') as run, \
            patch('utils.backup_target.os.umask'):
        run.return_value.returncode = 0
        dump('postgresql:///ccc_local', '/tmp/x')
    assert 'PGPASSWORD' not in run.call_args.kwargs['env']


@pytest.mark.parametrize('mode, expected', [('url', BARE), ('password', PASSWORD)])
def test_main_prints_one_value(monkeypatch, capsys, mode, expected):
    monkeypatch.setattr('utils.backup_target.ProductionConfig.SQLALCHEMY_DATABASE_URI', _url())
    assert main(['backup_target', mode]) == 0
    assert capsys.readouterr().out == f'{expected}\n'


@pytest.mark.parametrize('mode', [['dump', '/tmp/x'], ['url']])
def test_main_refuses_sqlite_on_stderr(monkeypatch, capsys, mode):
    monkeypatch.setattr('utils.backup_target.ProductionConfig.SQLALCHEMY_DATABASE_URI',
                        'sqlite:///x.db')
    assert main(['backup_target', *mode]) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'not a Postgres URL' in captured.err


@pytest.mark.parametrize('argv', [[], ['dump'], ['url', 'extra'], ['nope'],
                                  ['dump', 'a', 'b']])
def test_main_rejects_bad_arguments(argv):
    assert main(['backup_target', *argv]) == 2
