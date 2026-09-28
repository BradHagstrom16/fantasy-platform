"""deploy.sh's pre-migrate pg_dump target (utils/backup_target.py, ADR-067).

The password must leave the URL (it goes to pg_dump as PGPASSWORD, never in
its world-readable argv), SQLAlchemy's driver spellings must become plain
libpq `postgresql://`, and anything that is not Postgres is refused.
The shell side is tests/test-deploy-guards.sh cases BA-BC.
"""
import pytest

from utils.backup_target import main, split_url

DO_URL = ('postgresql://doadmin:p%40ss%2Fw0rd@db-x.db.ondigitalocean.com:25060/'
          'defaultdb?sslmode=require')


def test_password_is_split_out_and_decoded():
    password, url = split_url(DO_URL)
    assert password == 'p@ss/w0rd'
    assert url == ('postgresql://doadmin@db-x.db.ondigitalocean.com:25060/'
                   'defaultdb?sslmode=require')


# ids avoid the word 'postgres': conftest reads it as the Postgres-only marker.
@pytest.mark.parametrize('scheme', ['postgresql+psycopg2', 'postgres'],
                         ids=['driver-suffix', 'bare-alias'])
def test_driver_spellings_become_plain_postgresql(scheme):
    _, url = split_url(f'{scheme}://u:p@h/db')
    assert url == 'postgresql://u@h/db'


def test_a_url_without_a_password():
    assert split_url('postgresql:///ccc_local') == ('', 'postgresql:///ccc_local')


def test_sqlite_is_refused():
    with pytest.raises(ValueError, match='not a Postgres URL'):
        split_url('sqlite:////home/deploy/fantasy-platform/instance/fantasy_platform.db')


def test_main_prints_password_then_url(monkeypatch, capsys):
    monkeypatch.setattr('utils.backup_target.ProductionConfig.SQLALCHEMY_DATABASE_URI', DO_URL)
    assert main() == 0
    assert capsys.readouterr().out.splitlines() == [
        'p@ss/w0rd',
        'postgresql://doadmin@db-x.db.ondigitalocean.com:25060/defaultdb?sslmode=require']


def test_main_refuses_sqlite_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr('utils.backup_target.ProductionConfig.SQLALCHEMY_DATABASE_URI',
                        'sqlite:///x.db')
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'not a Postgres URL' in captured.err
