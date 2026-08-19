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


def _anchor_class_for_label(markup: str, label: str) -> str | None:
    """Return the `class` attribute of the <a> element whose visible text
    contains `label`, or None if no anchor wraps it. Anchors don't nest, so
    a non-greedy `.*?</a>` correctly bounds each element (inner <i> icons and
    newlines included)."""
    for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>', markup, re.S):
        attrs, inner = m.group(1), m.group(2)
        if label in inner:
            cls = re.search(r'class="([^"]*)"', attrs)
            return cls.group(1) if cls else ''
    return None


# Each primary/convert CTA the design review named, paired with the panel it
# lives in. Every one must be the bare solid `.hl-cta` (ADR-052). Anchored per
# label so a downgrade of ONE CTA (e.g. to the accent outline, or a room class)
# cannot be masked by a sibling CTA in the same file keeping the solid class.
NAMED_SOLID_CTAS = [
    (CFB_LOUNGE / '_decree.html', 'Enter the Room'),        # enrolled
    (CFB_LOUNGE / '_decree.html', 'Take Your Two Lives'),   # unenrolled join
    (CFB_LOUNGE / '_summons.html', 'Choose Team'),          # live OPEN pick
    (CFB_LOUNGE / '_view_cta.html', 'Take Your Two Lives'),  # live visitor convert
    (CFB_LOUNGE / '_conv_card.html', 'Join Survivor'),      # anonymous convert
    (DOCKET_LOUNGE / '_panel_pre.html', 'Enter the Court'),  # enrolled
    (DOCKET_LOUNGE / '_panel_pre.html', 'Take the Oath'),   # unenrolled join
    (DOCKET_LOUNGE / '_panel_live.html', 'Open Your Sheet'),  # live member
    (DOCKET_LOUNGE / '_panel_live.html', 'Join the Docket'),  # live visitor convert
    (DOCKET_LOUNGE / '_conv_card.html', 'Join the Docket'),  # anonymous convert
]


@pytest.mark.parametrize(
    'path,label', NAMED_SOLID_CTAS,
    ids=lambda v: v if isinstance(v, str) else v.name,
)
def test_each_named_panel_action_is_a_solid_hl_cta(path, label):
    """Positive lock, per CTA: each named primary/convert action is its own
    <a> element carrying the bare solid `class="hl-cta"` — not a gold seal, a
    room class, an accent outline, or a text link. Anchoring by visible label
    means a regression in one CTA can't hide behind another. The HELD "Review
    Pick" accent outline is intentionally excluded here and locked separately
    below."""
    cls = _anchor_class_for_label(_markup(path), label)
    assert cls is not None, f'{path.name}: no <a> element wraps {label!r}'
    assert cls == 'hl-cta', (
        f'{path.name}: {label!r} carries class="{cls}", expected the bare '
        'solid "hl-cta" (ADR-052). An outline, gold seal, or route link here '
        'breaks cross-state CTA parity.'
    )


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
