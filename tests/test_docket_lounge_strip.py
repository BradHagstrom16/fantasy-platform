"""T13 — the Docket second-bill lounge strip (premise 3 + D21-eng).

The lounge stays single-featured: CFB owns it, and The Docket enters as a
static strip that renders from registry-generic keys only. These locks pin the
three things that would quietly undo that:

1. **The seam stays untouched.** `second_bill_games()` selects on flags, not on
   the slug 'docket', and never disturbs `lounge_game()` or the single-overlay
   merge. Multi-featured is the ~Oct redesign.
2. **Static means static** (D21-eng). No countdown, no deadline math, no
   per-user pick state. Only the CTA varies, off the paired enrollment.
3. **The out-state conversion card renders once.** The unfiltered
   `available_games` loop painted one full ceremonial card per open game, so
   The Docket opening gave anonymous visitors a second card wearing CFB's
   copy and a second gold CTA. The old lock counted the literal in template
   source, which is why it never fired; these count the rendered page.
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
CFB_HOME_OUT = (
    REPO_ROOT / 'games' / 'cfb' / 'templates' / 'cfb' / 'lounge' / '_home_out.html'
)
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'

PRE_ANCHOR = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-08-18T17:00:00'}


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

def test_second_bill_is_the_open_non_featured_game(app):
    """Against the real registry: The Docket and nothing else."""
    from games.registry import second_bill_games
    with app.app_context():
        pairs = second_bill_games(AnonymousUserMixin())
    assert [entry.slug for entry, _ in pairs] == ['docket']


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


def test_second_bill_pairs_the_viewers_enrollment(app):
    """The join-vs-enter CTA reads this pairing; anonymous viewers get None."""
    from games.registry import second_bill_games
    with app.app_context():
        user = _make_user()
        assert second_bill_games(user)[0][1] is None
        docket_enrollment.admin_enroll(user.id)
        db.session.commit()
        entry, enr = second_bill_games(user)[0]
        assert entry.slug == 'docket'
        assert enr is not None and enr.user_id == user.id


def test_second_bill_survives_a_game_with_no_lounge_callables(app):
    """The Docket carries neither lounge callable by design. Selecting it must
    not depend on them (that is `lounge_game()`'s gate, not this one)."""
    from games.registry import get_entry
    entry = get_entry('docket')
    assert entry.lounge_state is None and entry.lounge_context is None


# == the context key ======================================================

def test_build_home_context_carries_second_bill_in_every_state(app):
    from core.main.home_context import build_home_context
    with app.app_context():
        for state in (None, 'pre', 'live', 'post'):
            user = None if state is None else _make_user(f'ctx{state}')
            with patch.dict(os.environ, PRE_ANCHOR):
                ctx = build_home_context(user, state)
            assert 'second_bill' in ctx, f'missing in state={state}'
            assert [e.slug for e, _ in ctx['second_bill']] == ['docket']


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
    assert [e.slug for e, _ in ctx['second_bill']] == ['docket']


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

def test_strip_renders_for_anonymous_visitor_routed_through_register(app, client):
    """The recruiting case. A logged-out viewer cannot join directly, so the
    CTA carries them through auth.register with next=the join page, matching
    the conversion card's path."""
    resp = client.get('/')
    assert resp.status_code == 200
    strip = _strip_html(resp.get_data(as_text=True))
    assert strip, 'the second-bill strip must render on the logged-out lounge'
    assert 'The Docket' in strip
    assert 'Join The Docket' in strip
    assert '/register?next=%2Fdocket%2Fjoin' in strip or \
           '/register?next=/docket/join' in strip


def test_strip_offers_join_to_an_authenticated_non_member(app, client):
    with app.app_context():
        auth_id = _make_user('nonmember').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, PRE_ANCHOR):
        strip = _strip_html(client.get('/').get_data(as_text=True))
    assert 'Join The Docket' in strip
    assert 'href="/docket/join"' in strip


def test_strip_offers_enter_to_a_docket_member(app, client):
    """Members are not excluded: The Docket appears nowhere else on the
    authenticated lounge (open != coming_soon, and it is neither the featured
    tile nor an archived one), so hiding the strip would leave a member with
    no lounge route to their own game."""
    with app.app_context():
        user = _make_user('docketmember')
        docket_enrollment.admin_enroll(user.id)
        db.session.commit()
        auth_id = user.auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, PRE_ANCHOR):
        strip = _strip_html(client.get('/').get_data(as_text=True))
    assert 'Enter The Docket' in strip
    assert 'href="/docket/"' in strip
    assert 'Join The Docket' not in strip


def test_strip_renders_in_the_authenticated_pre_state(app, client):
    with app.app_context():
        auth_id = _make_user('prestrip').auth_id
    _login(client, auth_id)
    with patch.dict(os.environ, PRE_ANCHOR):
        text = client.get('/').get_data(as_text=True)
    assert 'home-shell--pre' in text
    assert 'second-bill' in text


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


def test_strip_does_not_disturb_the_single_overlay_seam(app):
    """The lounge owner and the docket entry's flags are exactly as before."""
    from games.registry import get_entry, lounge_game
    assert lounge_game().slug == 'cfb'
    entry = get_entry('docket')
    assert entry.is_featured is False
    assert entry.status == 'open'


# == the out-state conversion card ========================================

def test_out_state_renders_exactly_one_join_card(app, client):
    """Regression lock for the duplicate conversion card. Counted on the
    RENDERED page: the pre-existing source-literal count passed while the
    loop painted two cards."""
    text = client.get('/').get_data(as_text=True)
    assert text.count('class="join"') == 1
    assert text.count('class="join-cta"') == 1


def test_out_state_join_card_never_wears_another_games_name(app, client):
    """The card's seal and kickoff line are CFB copy. With the loop
    unfiltered they were stamped onto The Docket's card too."""
    text = client.get('/').get_data(as_text=True)
    start = text.index('<div class="join">')
    # The strip is the next block after the card; everything between is the
    # conversion unit, however its inner divs happen to nest.
    card = text[start:text.index('<section class="second-bill"', start)]
    assert 'CFB Survivor Pool' in card
    assert 'The Docket' not in card


def test_cfb_out_partial_filters_the_conversion_loop_to_the_featured_game():
    """Source lock the CFB out partial never had. Identity stays registry
    driven (no hardcoded slug), but only the lounge owner gets the
    ceremonial card; other open games are second bills."""
    source = CFB_HOME_OUT.read_text()
    assert '{% for game in available_games if game.is_featured %}' in source, (
        'the conversion card must loop the featured entry only — an '
        'unfiltered available_games loop renders one ceremonial card and one '
        'gold CTA per open game.'
    )
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
