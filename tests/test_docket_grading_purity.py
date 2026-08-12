"""D9-eng purity locks: the grading package stays pure forever.

Registry-seam lock pattern: source-level sweeps over every module in the
package (so a future helper file is auto-covered), plus a subprocess import
proving the package pulls in no web/ORM machinery at import time, plus the
D20-eng annotation lock keeping floats out of key 3.
"""
import dataclasses
import subprocess
import sys
from pathlib import Path

GRADING_DIR = (Path(__file__).resolve().parent.parent
               / 'games' / 'docket' / 'services' / 'grading')

_BANNED_IMPORTS = ('flask', 'extensions', 'sqlalchemy', 'models',
                   'games.docket.models', 'games.docket.utils', 'requests')


def _import_lines(source):
    return [line.strip() for line in source.splitlines()
            if line.strip().startswith(('import ', 'from '))]


def test_grading_package_imports_no_orm_web_or_clock_machinery():
    """Every module under grading/ is swept — the engine's only inputs are
    snapshots, so db/flask/models imports are structurally impossible."""
    modules = sorted(GRADING_DIR.glob('*.py'))
    assert modules, 'grading package must exist'
    for path in modules:
        for line in _import_lines(path.read_text()):
            for banned in _BANNED_IMPORTS:
                assert banned not in line, (
                    f'{path.name}: {line!r} imports banned machinery '
                    f'({banned}) — the engine is pure (D9-eng)')


def test_grading_package_never_asks_for_now():
    """The engine has no clock: every temporal input arrives as data, so
    grading is replayable byte-for-byte (fixtures, bridge re-grades)."""
    for path in sorted(GRADING_DIR.glob('*.py')):
        source = path.read_text()
        for forbidden in ('datetime.now(', 'datetime.today(', 'time.time(',
                          'utcnow('):
            assert forbidden not in source, (
                f'{path.name} asks for wall-clock time ({forbidden}) — '
                f'temporal inputs must arrive as snapshot data')


def test_grading_package_import_pulls_in_no_flask_or_sqlalchemy():
    """Import the package in a fresh interpreter and prove the transitive
    import graph is clean — the source sweep can't see indirect pulls."""
    code = (
        'import sys; '
        'import games.docket.services.grading; '
        "banned = {'flask', 'sqlalchemy', 'extensions', 'models'}; "
        'loaded = banned & set(sys.modules); '
        "assert not loaded, f'grading import pulled in {loaded}'"
    )
    result = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True, text=True,
        cwd=GRADING_DIR.parents[3],
    )
    assert result.returncode == 0, result.stderr


def test_no_float_ever_enters_key_three():
    """D20-eng: every *_tenths field across the snapshot family is annotated
    int (or int | None) — never float. The annotation IS the contract; the
    runtime guard (_require_tenths) enforces it at construction."""
    from games.docket.services.grading import snapshots

    checked = 0
    for obj in vars(snapshots).values():
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        for f in dataclasses.fields(obj):
            if 'tenths' not in f.name:
                continue
            checked += 1
            annotation = str(f.type)
            assert 'float' not in annotation, (
                f'{obj.__name__}.{f.name} is float-typed — key 3 is '
                f'integer tenths end-to-end (D20-eng)')
            assert 'int' in annotation, (
                f'{obj.__name__}.{f.name} must be integer tenths')
    assert checked >= 4, 'expected tenths fields across the snapshot family'
