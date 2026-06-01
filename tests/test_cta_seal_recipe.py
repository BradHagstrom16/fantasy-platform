"""Lock the shared `.cta-seal` home-shell CTA recipe.

The pre-state decree CTA and the live-state dossier CTA are the same Loud
Trophy "gold seal" primary CTA. They were authored as two byte-identical
blocks; this consolidation extracts the interaction/layout stack into
`.home-shell .cta-seal` and reduces `.decree-cta` / `.dossier-cta` to their
margin/max-width deltas only. These tests lock that structure so the duplication
can't silently creep back, and that the Trophy Rule (metal-gold on the shared
recipe, not sprayed onto new selectors) holds.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
STYLE = (REPO / 'static' / 'css' / 'style.css').read_text()
COUNTDOWN = (REPO / 'core' / 'main' / 'templates' / 'main' / '_countdown_card.html').read_text()
DOSSIER = (REPO / 'core' / 'main' / 'templates' / 'main' / '_dossier_card.html').read_text()


def _block(selector_regex: str) -> str | None:
    m = re.search(selector_regex + r'\s*\{([^}]*)\}', STYLE)
    return m.group(1) if m else None


def test_shared_cta_seal_recipe_exists():
    """The shared recipe carries the metal-gold trophy fill + transition."""
    block = _block(r'\.home-shell\s+\.cta-seal')
    assert block is not None, '.home-shell .cta-seal recipe missing'
    assert 'var(--metal-gold-flat)' in block  # Trophy Rule: gold seal lives here
    assert 'transition:' in block
    assert 'box-shadow:' in block


def test_cta_seal_has_focus_and_reduced_motion():
    """Keyboard focus ring + reduced-motion reset live on the shared selector."""
    assert '.home-shell .cta-seal:focus-visible' in STYLE
    assert '.home-shell .cta-seal:active' in STYLE
    assert '.home-shell .cta-seal:hover' in STYLE
    # Reduced-motion block references the shared selector.
    assert re.search(
        r'@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.home-shell \.cta-seal',
        STYLE,
    ), 'cta-seal must have a prefers-reduced-motion reset'


@pytest.mark.parametrize('selector', [r'\.home-shell\s+\.decree-cta',
                                       r'\.home-shell\s+\.dossier-cta'])
def test_purpose_named_ctas_carry_only_layout_delta(selector):
    """`.decree-cta` / `.dossier-cta` must NOT re-duplicate the interaction
    stack — only margin/max-width. If a future edit re-inlines the recipe, this
    fails and points back to `.cta-seal`."""
    block = _block(selector)
    assert block is not None
    for banned in ('var(--metal-gold-flat)', 'transition:', 'box-shadow:',
                   'border-radius:', 'background:'):
        assert banned not in block, (
            f'{selector} re-duplicated `{banned}` — it belongs on .cta-seal'
        )


def test_no_orphan_decree_or_dossier_subelement_rules():
    """The old per-CTA sub-element selectors are retired in favor of
    `.cta-seal-label` / `.cta-seal-sub`."""
    assert '.decree-cta-label' not in STYLE
    assert '.decree-cta-sub' not in STYLE
    assert '.dossier-cta-label' not in STYLE
    assert '.dossier-cta-sub' not in STYLE


def test_templates_use_shared_classes():
    """Both home-shell CTA templates carry `cta-seal` plus their purpose class,
    and the shared sub-element classes."""
    assert 'class="cta-seal decree-cta"' in COUNTDOWN
    assert 'cta-seal-label' in COUNTDOWN and 'cta-seal-sub' in COUNTDOWN
    assert 'class="cta-seal dossier-cta"' in DOSSIER
    assert 'cta-seal-label' in DOSSIER and 'cta-seal-sub' in DOSSIER
