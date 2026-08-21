"""No new local ``app``/``client`` fixtures outside the allowlist (backlog 3.1).

The 2026-08-21 conftest migration deleted 103 exact-canonical local fixture
duplicates across 66 files; ``tests/conftest.py`` owns the canonical pair.
pytest silently prefers a module-local fixture over conftest's, so the
duplication would regrow one copy-paste at a time with nothing failing —
the same growth-by-inheritance shape ``tests/test_systemd_preset.py`` exists
to stop for timer units. A NEW test file needing app/client uses the
conftest fixtures; a file that genuinely needs a different fixture gets an
allowlist entry here, with its reason, in the same PR.

Note pytest's resolution order is also why an allowlisted local ``app``
composes with conftest's ``client``: conftest's ``client(app)`` resolves
``app`` from the requesting module first, so a module keeping only a special
``app`` still gets a client bound to it for free.
"""
import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent

# Every file allowed to define a local app/client fixture, with why.
ALLOWED = {
    'test_asset_versioning.py',            # no-teardown variant (asset checks, no DB writes)
    'test_auth_session_identity.py',       # pops WC_FAKE_NOW before create_app
    'test_cfb_history.py',                 # module-scoped client for /cfb/history (static snapshot, empty DB)
    'test_cfb_time_seam.py',               # app-context only, deliberately no DB
    'test_design_p2_s2_2_1.py',            # seeds WorldCupMatch rows inside the fixture
    'test_design_p2_s2_4_1.py',            # no-remove variant + stats-route empty-table note
    'test_design_wc_schedule_redesign.py', # seeds a picker user, stashes _picker_id in config
    'test_golf_automation.py',             # pins SEASON_YEAR to the golf fixtures' season
    'test_golf_cleanup.py',                # pins SEASON_YEAR
    'test_golf_conformance.py',            # pins SEASON_YEAR + EMAIL_ADDRESS
    'test_home_context.py',                # pops WC_FAKE_NOW before create_app
    'test_home_routes.py',                 # pops WC_FAKE_NOW before create_app
    'test_login_callout.py',               # standalone client (yields the client directly)
    'test_logo_assets.py',                 # standalone client (yields the client directly)
    'test_response_cache_headers.py',      # pops WC_FAKE_NOW before create_app
}


def _is_fixture_decorator(dec):
    """A pytest fixture decorator in any real form.

    Matches ``@pytest.fixture``, ``@pytest.fixture()``,
    ``@pytest.fixture(scope=...)`` and a bare ``@fixture``
    (``from pytest import fixture``) by structure — not by a substring,
    so an unrelated decorator that merely contains "fixture"
    (e.g. ``@some_fixture_factory()``) is rejected.
    """
    target = dec.func if isinstance(dec, ast.Call) else dec  # unwrap the call form
    if isinstance(target, ast.Attribute):
        return target.attr == 'fixture'                      # <module>.fixture
    return isinstance(target, ast.Name) and target.id == 'fixture'  # bare fixture


def _is_fixture(node):
    """True if node is a (sync or async) def decorated with a pytest fixture."""
    return (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(_is_fixture_decorator(d) for d in node.decorator_list))


def _local_fixture_files():
    """Files defining a module-level pytest fixture named app or client."""
    offenders = set()
    for path in sorted(TESTS_DIR.glob('test_*.py')):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if _is_fixture(node) and node.name in ('app', 'client'):
                offenders.add(path.name)
    return offenders


def test_no_local_app_client_fixtures_outside_allowlist():
    current = _local_fixture_files()
    new = current - ALLOWED
    assert not new, (
        f'New local app/client fixture(s) in {sorted(new)}. Use the canonical '
        f'conftest fixtures; if this file genuinely needs its own, add it to '
        f'ALLOWED in {Path(__file__).name} with a reason comment.')


def test_allowlist_carries_no_dead_entries():
    """A retired or migrated file leaves the allowlist in the same PR —
    a stale entry would quietly re-open its slot."""
    current = _local_fixture_files()
    dead = ALLOWED - current
    assert not dead, f'Allowlisted file(s) no longer define fixtures: {sorted(dead)}'


def test_conftest_still_owns_the_canonical_pair():
    """The lock is meaningless if the shared fixtures themselves vanish."""
    tree = ast.parse((TESTS_DIR / 'conftest.py').read_text())
    names = {node.name for node in tree.body if _is_fixture(node)}
    assert {'app', 'client'} <= names
