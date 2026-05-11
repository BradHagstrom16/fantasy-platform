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


# ---------- PI-4: skip-link ----------

def test_pi4_skip_link_present_in_base_html():
    """base.html must carry a `.skip-link` anchor as the first focusable child
    of `<body>`, targeting `#main-content` (WCAG 2.4.1 Bypass Blocks)."""
    html = BASE_HTML_PATH.read_text()
    assert '<a class="skip-link" href="#main-content">Skip to main content</a>' in html, (
        "base.html must include the skip-link anchor — WCAG 2.4.1 chrome a11y baseline"
    )
    # The skip-link must precede the navbar in source order so Tab lands on it first.
    skip_idx = html.find('<a class="skip-link"')
    nav_idx = html.find('<nav class="navbar')
    assert 0 < skip_idx < nav_idx, (
        "Skip-link must appear before <nav> in base.html so it's the first focusable target"
    )


def test_pi4_main_element_carries_target_id():
    """The `<main>` element must carry `id="main-content"` so the skip-link
    anchor resolves to a real region. `tabindex="-1"` makes the region
    programmatically focusable on activation."""
    html = BASE_HTML_PATH.read_text()
    assert '<main id="main-content" tabindex="-1">' in html, (
        "<main> must carry id=\"main-content\" and tabindex=\"-1\" so the skip-link "
        "lands programmatic focus on the main region (a11y baseline)"
    )


def test_pi4_skip_link_css_rule_present():
    """`style.css` must define `.skip-link` and `.skip-link:focus` rules with the
    off-screen → reveal-on-focus pattern (top: -100px → top: .5rem)."""
    src = CSS_PATH.read_text()
    assert '.skip-link {' in src, "style.css must define a .skip-link rule"
    # Reveal-on-focus shape.
    skip_idx = src.find('.skip-link {')
    block_end = src.find('}', skip_idx)
    block = src[skip_idx:block_end]
    assert 'top: -100px' in block, ".skip-link must rest off-screen (top: -100px) until focused"
    # Focus reveal rule.
    focus_idx = src.find('.skip-link:focus')
    assert focus_idx > 0, ".skip-link:focus reveal rule must exist"
    focus_block = src[focus_idx:src.find('}', focus_idx)]
    assert 'top: .5rem' in focus_block, ".skip-link:focus must drop the link into view (top: .5rem)"


# ---------- F1: Trophy Rule — drop navbar-brand gold-glow text-shadow ----------

def test_f1_navbar_brand_hover_has_no_gold_text_shadow():
    """`.navbar-brand:hover` must not declare a gold `text-shadow` — DESIGN.md §2
    Trophy Rule reserves gold-glow effects for `--shadow-gold` on primary-CTA
    hover; a 20px gold halo on a chrome brand wordmark dilutes the trophy."""
    src = CSS_PATH.read_text()
    # The orphan `.navbar-brand:hover` block.
    hover_idx = src.find('.navbar-brand:hover {')
    assert hover_idx > 0
    block_end = src.find('}', hover_idx)
    block = src[hover_idx:block_end]
    assert 'text-shadow' not in block, (
        ".navbar-brand:hover must not declare text-shadow — Trophy Rule (DESIGN.md §2)"
    )


def test_f1_navbar_brand_transition_excludes_text_shadow():
    """Paired with F1: `.navbar-brand` transition list must not include
    `text-shadow` (no shadow on hover → no need to animate it)."""
    src = CSS_PATH.read_text()
    # The orphan `.navbar-brand` block (selector specificity 0,0,1,0).
    # Locate by finding the first .navbar-brand { ... } where transition includes color.
    nb_idx = src.find('.navbar-brand {\n  font-size: 1.35rem;')
    assert nb_idx > 0, "Orphan .navbar-brand block (font-size 1.35rem) not found"
    block_end = src.find('}', nb_idx)
    block = src[nb_idx:block_end]
    assert 'transition: color var(--transition);' in block, (
        ".navbar-brand transition must be color-only after the gold-glow removal"
    )
    assert 'text-shadow' not in block, (
        ".navbar-brand transition must not include text-shadow — the hover no longer paints one"
    )
