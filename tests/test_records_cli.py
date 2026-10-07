"""``flask records close`` / ``show`` (ADR-068) and the seam lock: core/records
and models/records reach a game only through games.registry."""
import dataclasses
import json
import re
from pathlib import Path

import pytest

from models.records import finishes_for
from tests.test_records import _seed_cfb_closed_season, _seed_docket, _seed_wc, _user

ROOT = Path(__file__).resolve().parent.parent


def _run(app, *args):
    return app.test_cli_runner().invoke(args=['records', *args])


def test_close_records_a_decided_world_cup(app):
    a, b, c = _seed_wc()
    result = _run(app, 'close', 'worldcup', '2026')
    assert result.exit_code == 0, result.output
    assert '1  wc_a' in result.output and '487.0 pts' in result.output
    rows = finishes_for('worldcup', 2026)
    assert [(r.place, r.user_id) for r in rows] == [(1, a.id), (2, b.id), (2, c.id)]
    assert 'World Cup' in result.output


def test_close_refuses_a_season_already_on_record_unless_forced(app):
    _seed_wc()
    assert _run(app, 'close', 'worldcup', '2026').exit_code == 0
    again = _run(app, 'close', 'worldcup', '2026')
    assert again.exit_code == 1
    assert 'already on record' in again.output and '--force' in again.output
    forced = _run(app, 'close', 'worldcup', '2026', '--force')
    assert forced.exit_code == 0, forced.output
    assert len(finishes_for('worldcup', 2026)) == 3


def test_close_refuses_an_open_season(app):
    from tests._cfb_fixtures import make_enrollment
    make_enrollment(_user('p1'), lives=2)
    make_enrollment(_user('p2'), lives=1)
    result = _run(app, 'close', 'cfb', '2026')
    assert result.exit_code == 1
    assert 'has not concluded' in result.output
    assert finishes_for('cfb', 2026) == []


def test_close_refuses_a_game_without_a_seam(app, monkeypatch):
    """Every real game has a seam since golf's (U7); the refusal stays for
    a game whose board has not shipped, so it is exercised on a patched entry."""
    _seam_returning(monkeypatch, None)
    result = _run(app, 'close', 'worldcup', '2026')
    assert result.exit_code == 1
    assert 'no records seam' in result.output


def test_close_rejects_an_unknown_game(app):
    result = _run(app, 'close', 'bogus', '2026')
    assert result.exit_code == 2


@pytest.fixture()
def one_link(tmp_path, monkeypatch):
    """A link map of one name, so these tests never move when the committed
    map gains the links the Commish adds after the first close."""
    from games.cfb.services import records as cfb_records
    links = tmp_path / 'links.json'
    links.write_text(json.dumps({'Fourth & Pine': 'cubbies22'}), encoding='utf-8')
    monkeypatch.setattr(cfb_records, 'LINKS_2025_PATH', links)


def test_close_cfb_2025_names_the_members_still_unlinked(app, one_link):
    _user('cubbies22')
    result = _run(app, 'close', 'cfb', '2025')
    assert result.exit_code == 0, result.output
    rows = finishes_for('cfb', 2025)
    assert len(rows) == 26
    assert '25 names without an account' in result.output
    assert 'CamTheRam17' in result.output
    assert re.search(r'^\s*1\s+Fourth & Pine', result.output, re.M)


def test_close_cfb_2025_fails_when_the_link_map_names_a_stranger(app, one_link):
    result = _run(app, 'close', 'cfb', '2025')
    assert result.exit_code == 1
    assert 'cubbies22' in result.output and 'not a member' in result.output
    assert finishes_for('cfb', 2025) == []


def test_close_a_finished_docket_season(app):
    from games.docket.services.weeks import TOTAL_WEEKS
    alice, bob = _seed_docket(TOTAL_WEEKS)
    result = _run(app, 'close', 'docket', '2026')
    assert result.exit_code == 0, result.output
    assert '90.0 points' in result.output
    assert [(r.place, r.user_id) for r in finishes_for('docket', 2026)] == [
        (1, alice.id), (2, bob.id)]


def test_close_refuses_a_docket_season_one_week_short(app):
    from games.docket.services.weeks import TOTAL_WEEKS
    _seed_docket(TOTAL_WEEKS - 1)
    result = _run(app, 'close', 'docket', '2026')
    assert result.exit_code == 1
    assert f'{TOTAL_WEEKS - 1} of {TOTAL_WEEKS} weeks graded' in result.output
    assert finishes_for('docket', 2026) == []


def _seam_returning(monkeypatch, fn):
    from core.records import cli
    from games.registry import get_entry
    entry = dataclasses.replace(get_entry('worldcup'), season_finishes=fn)
    monkeypatch.setattr(cli, 'get_entry', lambda slug: entry)


def test_close_refuses_an_invalid_board_with_its_reason(app, monkeypatch):
    _seam_returning(monkeypatch, lambda year: [])
    result = _run(app, 'close', 'worldcup', '2026')
    assert result.exit_code == 1
    assert 'the board is empty' in result.output
    assert finishes_for('worldcup', 2026) == []


def test_a_builder_bug_is_never_dressed_as_a_refusal(app, monkeypatch):
    """Only the named refusals print a message; a KeyError inside a game's
    builder keeps its traceback."""
    def broken(year):
        return {}[57]
    _seam_returning(monkeypatch, broken)
    result = _run(app, 'close', 'worldcup', '2026')
    assert result.exit_code == 1
    assert isinstance(result.exception, KeyError)


def test_close_a_live_cfb_season(app):
    champ, late, early = _seed_cfb_closed_season()
    result = _run(app, 'close', 'cfb', '2026')
    assert result.exit_code == 0, result.output
    assert [r.place for r in finishes_for('cfb', 2026)] == [1, 2, 3]


def test_show_lists_the_seasons_and_prints_a_board(app):
    _seed_wc()
    assert _run(app, 'close', 'worldcup', '2026').exit_code == 0
    empty = _run(app, 'show', 'cfb', '2025')
    assert empty.exit_code == 0 and 'nothing on record' in empty.output
    index = _run(app, 'show')
    assert index.exit_code == 0
    assert 'worldcup 2026' in index.output and '3 finishers' in index.output
    board = _run(app, 'show', 'worldcup', '2026')
    assert board.exit_code == 0
    assert 'Bee' in board.output and '250.0 pts' in board.output


def test_core_records_reaches_games_only_through_the_registry():
    """The hijack lock's sibling: the record never imports a game module."""
    files = [ROOT / 'models' / 'records.py', *(ROOT / 'core' / 'records').glob('*.py')]
    assert len(files) >= 2
    for path in files:
        for line in path.read_text(encoding='utf-8').splitlines():
            stripped = line.strip()
            if stripped.startswith(('from games', 'import games')):
                assert stripped.startswith(('from games.registry', 'import games.registry')), (
                    f'{path.relative_to(ROOT)}: {stripped}')
