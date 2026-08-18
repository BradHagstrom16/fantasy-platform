"""The lounge accent firewall (multi-featured lounge, ruled 2026-08-18).

Brad's ruling lets the homepage cards inherit the games' colors, as
signature rather than substrate. The mechanics that keep that from decaying
into room-palette bleed:

- The hues are written ONCE, in tokens.css, as --lounge-* tokens.
- style.css maps them onto panels/cards through the --hl-* indirection.
- Lounge markup never references room tokens, never wears room classes,
  and never carries a raw room hex.

The scans glob what exists, so the locks bind every future headliner's
lounge partials automatically.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

LOUNGE_TOKENS = (
    '--lounge-cfb-accent:',
    '--lounge-cfb-accent-bright:',
    '--lounge-docket-ground:',
    '--lounge-docket-accent:',
    '--lounge-docket-accent-bright:',
)

# Every room-family hex, both games, bright variants included. Case-folded.
ROOM_HEXES = (
    'c5050c', 'e8282f', 'e8464c',                    # CFB crimson family
    '6e1f2e', 'a63446', '8a3b4a', '421219', 'c4707e', 'd06a7a',  # Docket wine family
)

ROOM_CLASS_PREFIX = re.compile(r'^(docket|cfb|wc)-')


def _lounge_template_paths():
    """Shared shell partials + every composite headliner's FULL lounge set.

    A lounge dir is a composite (panel-rendered) headliner iff it ships
    _panel_*.html; scan all of its _*.html so a room class/var/hex hiding in
    a nested include (_summons, _whos_left, _view_cta, _decree, …) is caught,
    not just the panel roots and the conv-card. A lounge dir with no _panel_*
    is the archival page-mode surface (worldcup's frozen _home_* tree) and is
    excluded — it predates this firewall. Deriving from the panel dirs keeps
    the locks binding every future headliner's partials automatically.
    """
    paths = list((REPO / 'core/main/templates/main').glob('_lounge_*.html'))
    for lounge_dir in sorted(REPO.glob('games/*/templates/*/lounge')):
        if not list(lounge_dir.glob('_panel_*.html')):
            continue  # page-mode archival (worldcup); not a composite headliner
        paths += sorted(lounge_dir.glob('_*.html'))
    return paths


def _home_region():
    src = (REPO / 'static/css/style.css').read_text()
    start = src.index('/* === HOME (CCC)')
    end = src.index('/* === HOME — END')
    return src[start:end]


def test_tokens_declare_lounge_accents():
    src = (REPO / 'static/css/tokens.css').read_text()
    for token in LOUNGE_TOKENS:
        assert token in src, f'tokens.css missing {token}'


def test_lounge_templates_never_reference_game_room_vars():
    """Room palette vars are scoped to body.game-<slug>; on the lounge they
    would half-apply. The --lounge-*/--hl-* indirection is the only path."""
    for path in _lounge_template_paths():
        src = path.read_text()
        for var in ('--game-primary', '--game-accent', '--cfb-', '--docket-rule'):
            assert var not in src, f'{path.name} references room var {var}'


def test_lounge_markup_carries_no_room_classes():
    """Scan class attributes (not raw text, since include paths contain
    'cfb/'): no class token may start docket-/cfb-/wc-. Slug-suffixed
    lounge modifiers (hl-panel--cfb, join--docket) are the sanctioned form."""
    for path in _lounge_template_paths():
        src = path.read_text()
        for attr in re.findall(r'class="([^"]*)"', src):
            for token in attr.split():
                assert not ROOM_CLASS_PREFIX.match(token), (
                    f'{path.name} carries room class {token!r}'
                )


def test_room_hexes_live_only_in_tokens():
    """The hue is written once. Lounge templates and the whole home-shell
    CSS region consume var(--lounge-*)/var(--hl-*), never a raw hex."""
    for path in _lounge_template_paths():
        src = path.read_text().lower()
        for hexval in ROOM_HEXES:
            assert hexval not in src, f'{path.name} carries raw hex {hexval}'
    home_css = _home_region().lower()
    for hexval in ROOM_HEXES:
        assert hexval not in home_css, (
            f'style.css HOME region carries raw room hex {hexval}'
        )


def test_hl_accent_mapping_uses_lounge_tokens_only():
    """The mapping rules exist for both headliners and resolve through the
    lounge tokens."""
    home_css = _home_region()
    for selector in ('.home-shell .hl-panel--cfb', '.home-shell .hl-panel--docket',
                     '.home-shell .join--cfb', '.home-shell .join--docket'):
        assert selector in home_css, f'missing accent mapping for {selector}'
    for token in ('var(--lounge-cfb-accent)', 'var(--lounge-docket-accent)',
                  'var(--lounge-docket-ground)'):
        assert token in home_css, f'mapping does not consume {token}'
