"""Lock the ADR-052 lounge CTA parity invariant.

Every action button in the CFB and Docket lounge *panels* is a solid accent
`.hl-cta` (crimson for Survivor, garnet for the Docket), in every state.
Gold is lounge chrome only now: no `.cta-seal` fills a panel button, and no
bone `.cta-outline` (the game-agnostic gold outline) either. The one
sanctioned non-solid affordance is the in-accent `.hl-cta--outline`
modifier, for a genuinely secondary, already-acted action (CFB's HELD
"Review Pick").

This is the regression net behind "standardize the two headliner panels so
the button treatment persists through all states": a future edit that
reaches back for a gold seal or a bone outline on a lounge panel button
fails here. The frozen WC archived lounge keeps its `.cta-seal` and is out
of scope (its templates live under games/worldcup/, not touched here).
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CFB_LOUNGE = REPO / 'games' / 'cfb' / 'templates' / 'cfb' / 'lounge'
DOCKET_LOUNGE = REPO / 'games' / 'docket' / 'templates' / 'docket' / 'lounge'


def _panel_files():
    files = []
    for d in (CFB_LOUNGE, DOCKET_LOUNGE):
        files.extend(sorted(d.glob('*.html')))
    return files


def _markup(path: Path) -> str:
    """Template body with Jinja comments stripped — the header comments name
    the very classes these locks ban, so scan the markup, not the prose."""
    return re.sub(r'\{#.*?#\}', '', path.read_text(), flags=re.S)


@pytest.mark.parametrize(
    'path', _panel_files(),
    ids=lambda p: f'{p.parent.parent.name}/{p.name}',
)
def test_no_gold_seal_or_bone_outline_on_lounge_panel_buttons(path):
    body = _markup(path)
    assert 'cta-seal' not in body, (
        f'{path.name}: lounge panel buttons are solid accent .hl-cta now '
        '(ADR-052); the metal-gold .cta-seal is retired from the panels.'
    )
    # `cta-outline` (single dash) is the retired bone/gold outline. The
    # accent modifier `hl-cta--outline` (two dashes) is intentionally NOT
    # matched by this substring and stays allowed.
    assert 'cta-outline' not in body, (
        f'{path.name}: the game-agnostic bone .cta-outline is retired from '
        'the lounge panels (ADR-052). Use the in-accent .hl-cta--outline '
        'for a genuinely secondary action, or a solid .hl-cta.'
    )


def test_every_named_panel_action_is_a_solid_hl_cta():
    """Positive lock: the primary/convert CTAs the design review named carry
    the bare solid `.hl-cta`, so a silent downgrade to a text link, a gold
    seal, or a room class is caught. (`class="hl-cta"` matches the solid
    fill only; the HELD `class="hl-cta hl-cta--outline"` does not, by
    design.)"""
    solid = 'class="hl-cta"'
    assert solid in _markup(CFB_LOUNGE / '_decree.html')      # Enter the Room + Take Your Two Lives
    assert solid in _markup(CFB_LOUNGE / '_summons.html')     # Choose Team (OPEN)
    assert solid in _markup(CFB_LOUNGE / '_view_cta.html')    # Take Your Two Lives (live view)
    assert solid in _markup(CFB_LOUNGE / '_conv_card.html')   # Join Survivor
    assert solid in _markup(DOCKET_LOUNGE / '_panel_pre.html')   # Enter the Court + Take the Oath
    assert solid in _markup(DOCKET_LOUNGE / '_panel_live.html')  # Open Your Sheet + Join the Docket
    assert solid in _markup(DOCKET_LOUNGE / '_conv_card.html')   # Join the Docket


def test_the_only_accent_outline_is_the_cfb_held_review():
    """The single sanctioned non-solid button is CFB's HELD "Review Pick"
    (a member who has already picked and may still change it). If a second
    `.hl-cta--outline` appears, revisit whether it is genuinely secondary or
    should be a solid convert/primary CTA."""
    hits = [p for p in _panel_files() if 'hl-cta--outline' in _markup(p)]
    assert hits == [CFB_LOUNGE / '_summons.html'], (
        'The accent outline .hl-cta--outline should appear only on CFB\'s '
        f'HELD "Review Pick"; found it in: {[p.name for p in hits]}'
    )
