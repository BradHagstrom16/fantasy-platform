"""The Docket second-bill strip (now dormant) + the multi-featured out-state.

T13 shipped The Docket as a static second-bill strip under a single-featured
lounge. The 2026-08-18 multi-featured rework (ADR-049) made both games
co-headline, so `second_bill_games()` now returns [] and the strip is dormant
machinery — retained, reappearance-locked, for a future open-but-unfeatured
game. These locks pin the four things that would quietly undo that:

1. **The selector follows flags, never the slug 'docket'.** It reports an
   empty bill under the dual-featured registry, and catches a demoted or
   future open-unfeatured game with no code change (the reason the machinery
   is kept). It never gates on the lounge callables — that is
   `lounge_games()`'s job, not this one's.
2. **The registry-generic `second_bill` key is unclobberable.** A headliner's
   context dict cannot overwrite it — in the flat overlay or, its composite
   twin, namespaced inside each Headliner — and the core dispatcher reaches
   the strip through `games.registry` only, never a game import.
3. **The out-state renders exactly one conversion card + CTA per headliner**,
   counted on the RENDERED page (the old source-literal count passed while
   the loop painted two), each in its own game's voice. The CTA retires past
   the shared enrollment deadline (ADR-050), so those assertions pin the
   clock rather than trust real `now`.
4. **Static means static** (D21-eng): whenever the strip renders it carries no
   countdown, deadline math, or per-user pick state, and never the Docket
   room palette/classes or the metal-gold seal.
"""
import os
import re
from pathlib import Path
from unittest.mock import patch

from flask_login import AnonymousUserMixin

from extensions import db
from games.docket.services import enrollment as docket_enrollment
from models.user import User
from tests._registry_helpers import set_is_featured

REPO_ROOT = Path(__file__).resolve().parents[1]
PARTIAL = REPO_ROOT / 'core' / 'main' / 'templates' / 'main' / '_second_bill.html'
LOUNGE_OUT = (
    REPO_ROOT / 'core' / 'main' / 'templates' / 'main' / '_lounge_out.html'
)
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'

PRE_ANCHOR = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-08-18T17:00:00',
              'DOCKET_FAKE_NOW': '2026-08-18T17:00:00'}
# Past the shared Sat Sep 5 enrollment deadline: both games' join windows are
# closed, so the conversion cards stay but their asks retire (ADR-050).
CLOSED_ANCHOR = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-06T00:00:00',
                 'DOCKET_FAKE_NOW': '2026-09-06T00:00:00'}


def _make_user(username='stripuser'):
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def _strip_html(text):
    """The rendered <section class="second-bill"> ... </section> block."""
    match = re.search(
        r'<section class="second-bill".*?</section>', text, re.S)
    return match.group(0) if match else ''


def _partial_body():
    """The partial with its Jinja comments removed.

    The header comment documents the very things these locks ban ('no
    countdown', 'never .cta-seal'), so a naive substring scan over the raw
    file fails on its own documentation. Scan the markup, not the prose.
    """
    return re.sub(r'\{#.*?#\}', '', PARTIAL.read_text(), flags=re.S)


# == the selector ==========================================================

def test_second_bill_is_empty_under_the_dual_featured_registry(app):
    """Against the real registry: both open games co-headline, so nothing
    is a second bill. The machinery stays (see the reappearance lock below)
    for a future open-but-unfeatured game."""
    from games.registry import second_bill_games
    with app.app_context():
        pairs = second_bill_games(AnonymousUserMixin())
    assert pairs == []


def test_second_bill_excludes_lounge_owner_completed_and_coming_soon(app):
    """CFB owns the lounge (it is the hero, not a second bill); WC is
    'completed'; Golf is 'coming_soon' and belongs to the tile rail."""
    from games.registry import second_bill_games
    with app.app_context():
        slugs = {entry.slug for entry, _ in second_bill_games(AnonymousUserMixin())}
    assert 'cfb' not in slugs
    assert 'worldcup' not in slugs
    assert 'golf' not in slugs


def test_second_bill_selects_on_flags_not_on_the_docket_slug(app, monkeypatch):
    """Feature The Docket instead and the strip must follow the flags: the
    new lounge owner drops out of the second bill and the demoted game takes
    its place. A slug-hardcoded selector would fail this."""
    from games.registry import second_bill_games
    set_is_featured(monkeypatch, 'cfb', False)
    set_is_featured(monkeypatch, 'docket', True)
    monkeypatch.setattr(
        'games.registry.lounge_games',
        lambda: [__import__('games.registry', fromlist=['x']).get_entry('docket')],
    )
    with app.app_context():
        slugs = [entry.slug for entry, _ in second_bill_games(AnonymousUserMixin())]
    assert slugs == ['cfb']


def test_second_bill_pairs_the_viewers_enrollment(app, monkeypatch):
    """The join-vs-enter CTA reads this pairing; anonymous viewers get None.
    The Docket co-headlines in the real registry now, so the pairing is
    exercised by demoting it back to the bill for this test."""
    from games.registry import second_bill_games
    set_is_featured(monkeypatch, 'docket', False)
    with app.app_context():
        user = _make_user()
        assert second_bill_games(user)[0][1] is None
        docket_enrollment.admin_enroll(user.id)
        db.session.commit()
        entry, enr = second_bill_games(user)[0]
        assert entry.slug == 'docket'
        assert enr is not None and enr.user_id == user.id


def test_second_bill_reappears_for_a_future_open_unfeatured_game(app, monkeypatch):
    """The dormant-machinery lock: demote one headliner and the strip
    catches it again with no code change — the promise the machinery is
    kept around for."""
    from games.registry import second_bill_games
    set_is_featured(monkeypatch, 'docket', False)
    with app.app_context():
        slugs = [entry.slug for entry, _ in second_bill_games(AnonymousUserMixin())]
    assert slugs == ['docket']


def test_second_bill_accepts_entries_without_lounge_callables(app, monkeypatch):
    """Selecting a second bill must not depend on the lounge callables
    (that is `lounge_games()`'s gate, not this one): an open, unfeatured
    entry with neither callable still makes the strip."""
    from dataclasses import replace

    from games import registry
    from games.registry import get_entry, second_bill_games
    bare = [
        e if e.slug != 'docket' else replace(
            get_entry('docket'), is_featured=False,
            lounge_state=None, lounge_context=None, join_open=None)
        for e in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', bare)
    with app.app_context():
        slugs = [entry.slug for entry, _ in second_bill_games(AnonymousUserMixin())]
    assert slugs == ['docket']


# == the context key ======================================================

def test_build_home_context_carries_second_bill_in_every_state(app):
    from core.main.home_context import build_home_context
    with app.app_context():
        for state in (None, 'pre', 'live', 'post'):
            user = None if state is None else _make_user(f'ctx{state}')
            with patch.dict(os.environ, PRE_ANCHOR):
                ctx = build_home_context(user, state)
            assert 'second_bill' in ctx, f'missing in state={state}'
            # Empty under the dual-featured registry; the key itself is the
            # contract (the shell includes the strip unconditionally).
            assert ctx['second_bill'] == []


def test_featured_overlay_cannot_clobber_second_bill(app, monkeypatch):
    """`second_bill` is assigned AFTER the featured overlay for the same
    reason `lounge_entry` is: a game's context dict must never be able to
    overwrite a registry-generic key."""
    from core.main.home_context import build_home_context
    from games import registry
    from games.registry import get_entry
    real_cfb = get_entry('cfb')
    hijacker = [
        e if e.slug != 'cfb' else __import__('dataclasses').replace(
            real_cfb, lounge_context=lambda user, state: {'second_bill': 'HIJACKED'})
        for e in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', hijacker)
    with app.app_context():
        ctx = build_home_context(None, None)
    assert ctx['second_bill'] != 'HIJACKED'
    assert ctx['second_bill'] == []


def test_composite_game_dict_cannot_clobber_registry_generic_keys(app, monkeypatch):
    """The composite twin of the hijack lock: a headliner's context dict is
    namespaced inside its Headliner, so even a dict claiming the shell's own
    keys cannot reach them."""
    from dataclasses import replace

    from core.main.home_context import build_home_context
    from games import registry
    from games.registry import get_entry
    hijack = {'second_bill': 'HIJACKED', 'headliners': 'HIJACKED',
              'commish_paragraphs': 'HIJACKED', 'archived_tiles': 'HIJACKED'}
    hijacker = [
        e if e.slug != 'cfb' else replace(
            get_entry('cfb'), lounge_context=lambda user, state: dict(hijack))
        for e in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', hijacker)
    with app.app_context():
        resolved = [(registry.get_entry('cfb'), None)]
        ctx = build_home_context(None, None, headliners=resolved)
    assert ctx['second_bill'] == []
    assert ctx['archived_tiles'] == []
    assert 'commish_paragraphs' not in ctx
    assert len(ctx['headliners']) == 1
    assert ctx['headliners'][0].ctx == hijack


def test_home_context_reaches_the_second_bill_only_through_the_registry():
    """Source lock, mirroring the seam's own: the core dispatcher must not
    import a game module to build the strip."""
    source = (REPO_ROOT / 'core' / 'main' / 'home_context.py').read_text()
    for line in source.splitlines():
        if line.startswith(('import ', 'from ')):
            assert 'games.docket' not in line, (
                'the dispatcher must reach The Docket through games.registry '
                f'only, never a direct import: {line!r}')


# == the rendered audience matrix =========================================
# The Docket co-headlines now, so the strip renders empty and the rendered
# join/enter/register audience matrix lives at panel level in
# tests/test_lounge_multi_featured.py (the strip's successor surface).


# == D21-eng: static means static =========================================

def test_strip_partial_carries_no_countdown_or_pick_state():
    """D21-eng: 'No countdowns, no per-user pick state.' The strip must stay
    renderable from the registry alone, so the ~Oct multi-featured redesign
    inherits an unchanged seam rather than a half-built data path."""
    source = _partial_body()
    banned = ('countdown', 'deadline', 'kickoff', 'picks_made', 'week_number',
              'get_current_time', 'datetime', 'now(')
    for token in banned:
        assert token not in source, (
            f'{token!r} in _second_bill.html — the strip is static by ruling '
            '(D21-eng); anything time- or pick-dependent belongs to the '
            'October multi-featured redesign, not this interim.'
        )


def test_strip_renders_no_timer_or_live_region(app, client):
    strip = _strip_html(client.get('/').get_data(as_text=True))
    assert 'role="timer"' not in strip
    assert 'aria-live' not in strip
    assert 'data-countdown' not in strip


def test_dual_featured_registry_bills_cfb_first(app):
    """The new-era registry lock: both games headline, CFB takes first
    billing (GAMES order), and the strip machinery reports an empty bill."""
    from games.registry import lounge_game, lounge_games
    assert [e.slug for e in lounge_games()] == ['cfb', 'docket']
    assert lounge_game().slug == 'cfb'


# == the out-state conversion card ========================================

def test_out_state_renders_one_join_card_per_headliner(app, client):
    """Regression lock for the duplicate conversion card, generalized to
    the multi-featured shell. Counted on the RENDERED page (the original
    source-literal count passed while the loop painted two cards): exactly
    one conversion card and one CTA per lounge headliner, derived from the
    registry so the docket flip moves this lock instead of breaking it.

    Pinned pre-deadline: the CTA is gated on the open enrollment window
    (ADR-050), so an unpinned clock would pass today and fail after Sep 5."""
    from games.registry import lounge_games
    expected = len(lounge_games())
    with patch.dict(os.environ, PRE_ANCHOR):
        text = client.get('/').get_data(as_text=True)
    assert text.count('class="join hl-conv') == expected
    assert text.count('hl-cta"') == expected


def test_out_state_closed_window_retires_the_cta(app, client):
    """The other half of ADR-050: past the shared enrollment deadline the
    conversion cards stay (a visitor still sees both games on the bill), but
    every headliner's ask retires — one card per headliner, zero `.hl-cta`,
    each replaced by that game's own closed-window copy."""
    from games.registry import lounge_games
    expected = len(lounge_games())
    with patch.dict(os.environ, CLOSED_ANCHOR):
        text = client.get('/').get_data(as_text=True)
    assert text.count('class="join hl-conv') == expected
    assert text.count('hl-cta"') == 0
    assert 'Late seats are granted by the Commish' in text   # CFB retired ask
    assert 'Late filings require the Commish' in text         # Docket retired ask


def test_out_state_join_card_never_wears_another_games_name(app, client):
    """Each card carries its own game's copy. With the pre-rework loop
    unfiltered, CFB's seal and kickoff line were stamped onto The Docket's
    card too."""
    text = client.get('/').get_data(as_text=True)
    start = text.index('class="join hl-conv join--cfb"')
    next_card = text.find('class="join hl-conv', start + 1)
    end = next_card if next_card != -1 else text.index('hl-signin', start)
    card = text[start:end]
    assert 'CFB Survivor Pool' in card
    assert 'The Docket' not in card


def test_out_shell_loops_headliners_and_keeps_the_second_bill():
    """Successor to the old featured-loop source lock: the shell renders one
    per-game conversion card per headliner (each game's own _conv_card, so
    no card can wear another game's copy) and keeps the second-bill strip
    for open games that are not headliners."""
    source = LOUNGE_OUT.read_text()
    assert "{% for h in headliners %}" in source
    assert "_conv_card.html" in source
    assert '{% include \'main/_second_bill.html\' %}' in source


# == substrate + silhouette ===============================================

def test_strip_carries_no_docket_room_palette():
    """games/docket/DESIGN.md §3: The Docket enters the lounge through
    content and copy, 'never through this room's palette or substrate'."""
    css_block = _second_bill_css()
    for source in (_partial_body(), css_block):
        for token in ('6E1F2E', 'A63446', '8A3B4A', '421219', 'C4707E',
                      '--game-primary', '--game-accent', 'docket-rule'):
            assert token.lower() not in source.lower(), (
                f'{token} is Docket room palette; the lounge stays CCC '
                'purple and gold.'
            )


def test_strip_uses_no_docket_room_classes():
    """`.docket-*` selectors are global, not scoped under body.game-docket,
    so borrowing one onto the lounge would half-apply and paint
    --text-primary ink on the purple substrate."""
    assert 'docket-' not in _partial_body()


def test_strip_cta_is_outline_never_the_metal_gold_seal():
    """The CFB-era lounge budgets exactly two .cta-seal CTAs (the decree and
    the OPEN summons). A third would break the Trophy Rule."""
    source = _partial_body()
    assert 'cta-outline' in source
    assert 'cta-seal' not in source


def _second_bill_css():
    css = STYLE_CSS.read_text()
    match = re.search(r'\.home-shell \.second-bill\s*\{[^}]+\}', css)
    assert match, '.home-shell .second-bill rule must exist in style.css'
    return match.group(0)


def test_strip_declares_the_informational_card_recipe():
    """DESIGN.md §5: the home shell carries two card registers and no more.
    The strip is static and asks nothing before a deadline, so it takes the
    Informational recipe (purple-850 -> purple-950, bone-8% border, 12px)
    rather than inventing a third silhouette."""
    rule = _second_bill_css()
    assert 'var(--purple-850)' in rule and 'var(--purple-950)' in rule
    assert 'rgba(243,239,230,.08)' in rule
    assert 'border-radius: 12px' in rule
    assert 'rgba(201,162,39' not in rule, (
        'the 30%-gold border is the Ceremonial recipe, reserved for surfaces '
        'that ask something of the viewer before a deadline.'
    )


def test_strip_css_uses_dark_substrate_tokens_only():
    """--text-primary/--text-secondary/--border are light-substrate values;
    inside .home-shell they resolve to near-black ink on purple."""
    css = STYLE_CSS.read_text()
    start = css.index('/* --- Second-bill strip')
    end = css.index('/* ---', start + 10)
    block = css[start:end]
    for token in ('--text-primary', '--text-secondary', 'var(--border)'):
        assert token not in block, (
            f'{token} is calibrated for bone substrates, not the lounge.'
        )


def test_registry_cadence_copy_carries_no_date_that_can_go_stale():
    """D21-eng static cadence: a weekly rhythm, not a launch date. A hardcoded
    'Opens Sep 1' would read wrong from Sep 2 onward with nothing to update
    it, which is the prose drift games/docket/DESIGN.md warns against."""
    from games.registry import get_entry
    cadence = get_entry('docket').lounge_cadence
    assert cadence
    assert not re.search(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d', cadence)
    assert '—' not in cadence and '--' not in cadence


def test_second_bill_field_defaults_empty_for_other_games():
    """The field is optional display metadata, like short_name/launch_label:
    entries that omit it render the strip without a cadence line."""
    from games.registry import get_entry
    assert get_entry('cfb').lounge_cadence == ''
    assert get_entry('golf').lounge_cadence == ''
