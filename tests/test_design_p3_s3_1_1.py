"""P3 S3.1.1 regression locks — `templates/base.html` chrome (navbar, sub-nav, footer, skip-link).

Covers the 4 Priority Issues + 2 freebies landed in iteration S3.1.1:
- PI-1: navbar cascade cleanup (no linear-gradient !important; no dead-code 3px gold
  bottom border in the orphan `.navbar` block; no `border-width` in the transition).
- PI-2: `.navbar.navbar-dark .navbar-brand` carries `min-height: 44px` for the 44×44
  mobile touch floor.
- PI-3: `.subnav-pill` inactive text color bumped from `rgba(255,255,255,.48)` to .75
  for AA contrast against the WC/CFB/Golf sub-nav substrates.
- PI-4: skip-link present in base.html as the first focusable child of `<body>`,
  targets `#main-content`, and `<main>` carries `id="main-content"`.
- F1: `.navbar-brand:hover` no longer paints a 20px gold `text-shadow` glow
  (Trophy Rule, DESIGN.md §2).
"""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'
BASE_HTML_PATH = Path(__file__).parent.parent / 'templates' / 'base.html'


# ---------- PI-1: navbar cascade cleanup ----------

def test_pi1_no_linear_gradient_important_on_navbar():
    """The orphan `.navbar` block must not declare a `linear-gradient` background
    with `!important`. DESIGN.md §5 specs solid `var(--purple-700)`; the early
    `.navbar.navbar-dark` block owns the brand fill."""
    src = CSS_PATH.read_text()
    # Forbidden line shape — the prior S2/pre-P3 cascade offender.
    assert 'background: linear-gradient(90deg, var(--platform-primary-dark) 0%, var(--platform-primary) 100%) !important' not in src, (
        "Navbar gradient !important re-introduced — DESIGN.md §5 specifies solid "
        "var(--purple-700) on .navbar.navbar-dark"
    )


def test_pi1_navbar_dark_solid_purple_fill_preserved():
    """`.navbar.navbar-dark` must keep its solid `var(--purple-700)` fill +
    `1px solid var(--purple-800)` border-bottom per DESIGN.md §5."""
    src = CSS_PATH.read_text()
    # The block must contain both the fill and the border, on the .navbar.navbar-dark selector.
    assert '.navbar.navbar-dark {\n  background: var(--purple-700);\n  border-bottom: 1px solid var(--purple-800);\n}' in src, (
        ".navbar.navbar-dark must keep its DESIGN.md §5 solid purple-700 fill + "
        "1px purple-800 border-bottom"
    )


def test_pi1_orphan_navbar_block_has_no_dead_border_rule():
    """The later `.navbar` block (the sticky-chrome wiring rule) must not declare
    a `border-bottom: 3px solid var(--platform-accent)` — that was dead code
    (specificity-overridden by `.navbar.navbar-dark`'s 1px purple-800 rule) and
    misleads future readers about the rendered border."""
    src = CSS_PATH.read_text()
    # Locate the comment block + .navbar { ... } region and confirm the bad line is gone.
    sticky_chrome_idx = src.find('sticky-chrome wiring only')
    assert sticky_chrome_idx > 0, "Sticky-chrome comment marker missing — block may have shifted"
    # The .navbar block opens within 600 chars of the comment.
    block_start = src.find('.navbar {', sticky_chrome_idx)
    block_end = src.find('}', block_start)
    block = src[block_start:block_end]
    assert 'border-bottom' not in block, (
        "Orphan .navbar block must not declare `border-bottom` — dead code that "
        "drifts from the DESIGN.md §5 1px-purple-800 spec"
    )


def test_pi1_navbar_transition_excludes_border_width():
    """`.navbar` transition must NOT animate `border-width` (impeccable shared
    design law: don't animate CSS layout properties). Locked here so a future
    iteration doesn't reintroduce the layout-jitter on scroll-threshold cross."""
    src = CSS_PATH.read_text()
    sticky_chrome_idx = src.find('sticky-chrome wiring only')
    block_start = src.find('.navbar {', sticky_chrome_idx)
    block_end = src.find('}', block_start)
    block = src[block_start:block_end]
    assert 'transition: padding var(--transition);' in block, (
        ".navbar transition must be padding-only (no border-width — that's a layout property)"
    )
    assert 'border-width' not in block, (
        ".navbar transition must not include border-width — animating layout properties is banned"
    )


def test_pi1_navbar_scrolled_no_border_width_change():
    """`.navbar-scrolled` must not declare `border-bottom-width: 2px` — also
    dead code (specificity-overridden) and pairs with the transition drop above."""
    src = CSS_PATH.read_text()
    # The `.navbar-scrolled` block sits right after `.navbar` in the file.
    nav_scrolled_idx = src.find('.navbar-scrolled {')
    assert nav_scrolled_idx > 0
    block_end = src.find('}', nav_scrolled_idx)
    block = src[nav_scrolled_idx:block_end]
    assert 'border-bottom-width' not in block, (
        ".navbar-scrolled must not declare border-bottom-width — dead code, paired "
        "with the layout-property transition removal"
    )


# ---------- PI-2: navbar-brand 44×44 floor ----------

def test_pi2_navbar_brand_meets_44_min_height():
    """`.navbar.navbar-dark .navbar-brand` must declare `min-height: 44px` for
    the WCAG 2.5.5 + PRODUCT.md mobile touch floor."""
    src = CSS_PATH.read_text()
    brand_idx = src.find('.navbar.navbar-dark .navbar-brand {')
    assert brand_idx > 0
    block_end = src.find('}', brand_idx)
    block = src[brand_idx:block_end]
    assert 'min-height: 44px' in block, (
        ".navbar.navbar-dark .navbar-brand must carry `min-height: 44px` — most-tapped "
        "home target on mobile, can't dip below the 44×44 touch floor"
    )


# ---------- PI-3: sub-nav inactive pill contrast ----------

def test_pi3_subnav_pill_inactive_text_color_meets_aa():
    """`.subnav-pill` inactive text color must be `rgba(255,255,255,.75)` (≈4.7:1
    on the WC sub-nav background `#00122e`), not the prior `.48` (≈3.7:1)."""
    src = CSS_PATH.read_text()
    # Locate the .subnav-pill block — the 44×44 floor comment marker is unique.
    floor_idx = src.find('44px min-height for the mobile-first touch floor')
    assert floor_idx > 0, "Sub-nav pill comment marker missing"
    block_start = src.find('.subnav-pill {', floor_idx)
    block_end = src.find('}', block_start)
    block = src[block_start:block_end]
    assert 'color: rgba(255,255,255,.75);' in block, (
        ".subnav-pill inactive color must be rgba(255,255,255,.75) for AA contrast "
        "on the three game sub-nav backgrounds (#00122e WC, #001a0d Golf, #0a080f CFB)"
    )
    assert 'color: rgba(255,255,255,.48)' not in block, (
        ".subnav-pill .48 alpha was sub-AA on the WC navy background (~3.7:1); "
        "regression — text alpha must stay ≥ .75"
    )


# ---------- PI-4: skip-link removed in design/home-out-polish (2026-05-13) ----------
#
# The S3.1.1 PI-4 skip-link (WCAG 2.4.1 Bypass Blocks) was removed by product
# decision after first-impression critique. Trade-off: this is a small-group
# fantasy-pool product (PRODUCT.md: "10 to 30 people with existing
# camaraderie"); the marginal AT benefit was judged not worth the chrome
# real estate over the navbar even at off-screen-until-focused. If a future
# member uses a screen reader or keyboard navigation as a primary input,
# revisit and restore. These locks now ASSERT the removal so a future
# automated patch doesn't silently re-introduce the pattern without an
# explicit design decision.

def test_pi4_skip_link_removed_from_base_html():
    """The `.skip-link` anchor must not return to base.html. Re-introducing
    it requires a deliberate design revision (revise this lock + the
    rationale comment above)."""
    html = BASE_HTML_PATH.read_text()
    assert 'skip-link' not in html, (
        "base.html re-introduced the skip-link anchor. The pattern was "
        "retired in design/home-out-polish; if you want to restore it, "
        "revise the rationale comment and these tests together."
    )
    assert 'Skip to main content' not in html, (
        "base.html re-introduced the 'Skip to main content' anchor text. "
        "The pattern was retired in design/home-out-polish."
    )


def test_pi4_main_element_keeps_id_but_drops_orphan_tabindex():
    """`<main>` retains `id=\"main-content\"` (useful for in-page anchor
    links and AT landmarks) but no longer carries `tabindex=\"-1\"` —
    that attribute only existed to receive programmatic focus from the
    now-removed skip-link, so it's an orphan otherwise."""
    html = BASE_HTML_PATH.read_text()
    assert '<main id="main-content">' in html, (
        "<main> must keep id=\"main-content\" (semantic landmark + future "
        "in-page anchor target)."
    )
    assert 'tabindex="-1"' not in html.split('<main')[1].split('>')[0] + '>', (
        "<main> must not carry `tabindex=\"-1\"` — that attribute existed "
        "only to receive programmatic focus from the (now-removed) "
        "skip-link. Re-adding it implies the skip-link is coming back; "
        "do both deliberately."
    )


def test_pi4_skip_link_css_rule_removed():
    """`style.css` must not define a `.skip-link` rule. The CSS was the
    other half of the removed pattern."""
    src = CSS_PATH.read_text()
    assert '.skip-link' not in src, (
        "style.css re-introduced a `.skip-link` rule. The skip-link "
        "pattern was retired in design/home-out-polish; restoring it "
        "requires revising the rationale comment + these tests."
    )


# ---------- F1: Trophy Rule — no gold-glow text-shadow on navbar-brand ----------
#
# S3.4 superseded the original F1 implementation: the orphan `.navbar-brand`
# block at `style.css:~4019` (where the F1 fix lived) was deleted entirely,
# and its load-bearing declarations (`font-weight: 700`, `text-transform:
# uppercase`) were folded into the spec-correct `.navbar.navbar-dark
# .navbar-brand` block at line 101. The F1 contract (Trophy Rule: no gold
# halo on the brand wordmark) is now enforced by *absence* of any
# `.navbar-brand` rule that paints `text-shadow`, which is a stronger
# guarantee than the original lock (the original required the orphan block
# to exist sans text-shadow; the new shape forbids any text-shadow on the
# brand in any rule).


def test_f1_navbar_brand_has_no_text_shadow_anywhere():
    """Trophy Rule (DESIGN.md §2): gold-glow effects reserve for
    `--shadow-gold` on primary-CTA hover. No `.navbar-brand` rule —
    resting, hover, focus, or otherwise — may declare `text-shadow`.
    S3.4 stripped the orphan rule entirely, so the only `.navbar-brand`
    rules left are inside the CCC block, and they must remain
    text-shadow-free."""
    src = CSS_PATH.read_text()
    # Match any rule whose selector list includes `.navbar-brand` (as a
    # whole class token). For each such block, the body must not contain
    # `text-shadow`.
    pattern = re.compile(
        r"([^{}]*\.navbar-brand(?:[:.][^{,]*)?[^{}]*)\{([^{}]*)\}",
        re.DOTALL,
    )
    for selector, body in pattern.findall(src):
        # Selector list must mention `.navbar-brand` specifically (not just
        # as a substring of e.g. `.navbar-brand-mark`). Token boundary:
        # `.navbar-brand` followed by space, comma, colon, dot, brace, or
        # end-of-string.
        if not re.search(r"\.navbar-brand(?=[\s,:.{]|$)", selector):
            continue
        assert 'text-shadow' not in body, (
            f"Trophy Rule violation: `text-shadow` reintroduced in a "
            f"`.navbar-brand` rule. Selector: {selector.strip()}"
        )


def test_f1_no_orphan_navbar_brand_hover_block():
    """S3.4 deleted the orphan `.navbar-brand:hover` block. Any
    reintroduction of `.navbar-brand:hover` outside the CCC `.navbar.navbar-
    dark` scope is a regression — the brand wordmark is a masthead, not a
    CTA, and the Trophy Rule keeps gold off it on hover too. Cursor change
    carries the affordance per DESIGN.md §5."""
    src = CSS_PATH.read_text()
    # Forbid the bare-class hover form anywhere in the stylesheet.
    bare_hover = re.compile(r"^\.navbar-brand\s*:\s*hover\s*\{", re.MULTILINE)
    assert not bare_hover.search(src), (
        "Orphan `.navbar-brand:hover` block reintroduced. The brand "
        "wordmark must not declare a hover color shift (DESIGN.md §5)."
    )
