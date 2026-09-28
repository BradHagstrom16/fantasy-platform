"""``flask records close`` / ``show`` (ADR-068) and the seam lock: core/records
and models/records reach a game only through games.registry."""
import re
from pathlib import Path

from models.records import finishes_for
from tests.test_records import _seed_cfb_closed_season, _seed_wc, _user

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
    assert 'World Cup' in result.output or '2026 FIFA World Cup' in result.output


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


def test_close_refuses_a_game_without_a_seam(app):
    result = _run(app, 'close', 'golf', '2027')
    assert result.exit_code == 1
    assert 'no records seam' in result.output


def test_close_rejects_an_unknown_game(app):
    result = _run(app, 'close', 'bogus', '2026')
    assert result.exit_code == 2


def test_close_cfb_2025_names_the_members_still_unlinked(app):
    _user('cubbies22')
    result = _run(app, 'close', 'cfb', '2025')
    assert result.exit_code == 0, result.output
    rows = finishes_for('cfb', 2025)
    assert len(rows) == 26
    assert '25 names without an account' in result.output
    assert 'CamTheRam17' in result.output
    assert re.search(r'^\s*1\s+Fourth & Pine', result.output, re.M)


def test_close_cfb_2025_fails_when_the_link_map_names_a_stranger(app):
    result = _run(app, 'close', 'cfb', '2025')
    assert result.exit_code == 1
    assert 'cubbies22' in result.output
    assert finishes_for('cfb', 2025) == []


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
