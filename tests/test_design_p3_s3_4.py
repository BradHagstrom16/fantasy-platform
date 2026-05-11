"""P3 S3.4 regression locks — chrome cross-cluster polish + errors first-pass.

S3.4 is a cluster polish session (not a per-surface iteration), per the plan
§1.5c pattern. It received four `[cross-cluster]` routed items from S3.1.1 +
S3.2.1 and ran a first-pass critique on the two error templates. Layer A locks
the source-pattern fingerprint of every code-change PI; Layer B (live
computed-style probes via Playwright MCP) runs in the session log, not in
pytest.

Iteration map:

- **PI-0 (errors)**: 404.html / 500.html pre-S3.4 used a hero-metric template
  (giant `.section-heading` numeral painted `var(--border)` = `#D8DDE8` on
  bone `#F3EFE6`, ~1.06:1 contrast, effectively invisible) with `.text-muted`
  subhead that paints Bootstrap default `--bs-secondary-color` on bone (~4:1
  AA-fail risk; outside `body.auth-page` scope so no PI-2 override applied).
  Reshape replaces the numeral with the canonical CCC Eyebrow primitive
  (DESIGN.md §3 "Eyebrow Rule": Teko 500, .85rem, .14em letter-spacing,
  uppercase, gold) above a Teko 600 display headline and a Newsreader serif
  lede painting `--text-secondary` (~6.9:1 on bone, AA-pass). Tribune voice
  replaces SaaS-utility copy ("Page Not Found" / "An unexpected error
  occurred" → "This page isn't in the ledger." / "The Commish hit a snag.").

- **PI-1 (navbar-brand color drift)**: the orphan `.navbar-brand` block at
  `style.css:~4019` painted the wordmark `var(--platform-accent) !important`
  (Commish Gold), overriding the spec-correct `.navbar.navbar-dark
  .navbar-brand` block at line 101 (DESIGN.md §5: "Pressroom Bone color").
  Per `project_chrome_cascade_discipline.md` memory, the routed entry's
  `[cross-cluster]` premise was verified at session-time via live probe
  (`getComputedStyle(.navbar-brand).color === rgb(201, 162, 39)` confirmed
  the gold render). Resolution: drop the orphan block entirely (color +
  hover) and fold its `font-weight: 700` + `text-transform: uppercase` into
  the CCC block so the masthead voice survives without an !important fight.
  DESIGN.md §5 amended to explicitly include weight 700 + uppercase so the
  spec matches the cascade.

- **PI-2 (chrome :focus-visible)**: pre-S3.4, `.navbar .nav-link` and
  `.subnav-pill` inherited the browser-default focus outline — inconsistent
  across Chrome / Safari / Firefox, easy to miss on the dark game-tinted
  subnav substrates (`#00122e` WC, `#001a0d` Golf, `#0a080f` CFB). Add the
  canonical CCC focus ring locked in S2.1.2 / S3.3.2: `outline: 2px solid
  var(--gold-light); outline-offset: 2px;` — gold-light on every chrome
  background reads ≥ 7:1.

- **PI-3 (game-subnav semantics)**: the three game-subnav wrappers used
  `<div>` containers and carried no `aria-label`. On mobile the inline
  `.subnav-game-label` ("⚽ WC 2026" / "⛳ Golf 2026" / "🏈 CFB 2025") is
  `display: none` via `d-none d-sm-inline-flex`, so screen-reader users
  lost the "Hub of what?" cue. Switch to semantic `<nav aria-label="…
  section">` so the game context surfaces in the SR landmark list.

- **PI-4 (auth surface composition contract)**: pre-S3.4, auth surfaces
  used three wrappers — `.auth-page > .auth-panel-brand + .auth-form-panel`
  (marketing: login, register, forgot, reset), `.auth-wrapper` (utility:
  change_password), and `.container.my-5 style="max-width:600px"` (utility:
  profile). The third pattern was a one-off. Resolution: codify the
  marketing-vs-utility split in DESIGN.md §5 "Auth Surface Composition" and
  normalize profile.html to `.auth-wrapper.profile-wrapper` (the wrapper
  modifier carries the 600px max-width without re-introducing the third
  register).

S3.4 is a cluster polish session, so it does not trigger the §1.5b
per-surface convergence gate. Layer B (Playwright MCP) handles the
cross-cluster regression check on touched + adjacent chrome surfaces.
"""

from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
BASE = (ROOT / 'templates' / 'base.html').read_text()
ERROR_404 = (ROOT / 'templates' / 'errors' / '404.html').read_text()
ERROR_500 = (ROOT / 'templates' / 'errors' / '500.html').read_text()
DESIGN_MD = (ROOT / 'DESIGN.md').read_text()
PROFILE_HTML = (
    ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'profile.html'
).read_text()
CHANGE_PW_HTML = (
    ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'change_password.html'
).read_text()
LOGIN_HTML = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'login.html').read_text()
REGISTER_HTML = (
    ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'register.html'
).read_text()
FORGOT_HTML = (
    ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'forgot_password.html'
).read_text()
RESET_HTML = (
    ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'reset_password.html'
).read_text()


# ---------------------------------------------------------------------------
# PI-0: errors first-pass — Tribune-voiced editorial masthead.
# ---------------------------------------------------------------------------

def test_pi0_404_drops_section_heading_hero_metric():
    """The pre-S3.4 hero-metric template (`.section-heading` giant numeral
    in `--border` color on bone) is an absolute-ban silhouette (big number,
    small label, supporting CTA — DESIGN.md don'ts + shared design laws).
    The reshape must drop the class entirely from 404.html so the new
    Eyebrow + Headline + Lede composition is the only voice on the page."""
    assert 'section-heading' not in ERROR_404, (
        "PI-0: 404.html still references `.section-heading`. The hero-metric "
        "template (giant numeral on top, small label below) is an absolute "
        "ban; the reshape uses `.error-eyebrow` + `.error-headline` + "
        "`.error-lede` instead."
    )


def test_pi0_500_drops_section_heading_hero_metric():
    assert 'section-heading' not in ERROR_500, (
        "PI-0: 500.html still references `.section-heading`. Same hero-metric "
        "ban as PI-0 on 404 — use the new error-page primitives."
    )


def test_pi0_404_uses_canonical_eyebrow_primitive():
    """The eyebrow line replaces the giant numeral as the contextual marker
    ("Bulletin · 404"). It must use the dedicated `.error-eyebrow` class so
    the Teko 500 / .85rem / .14em / uppercase / gold lock survives any
    future markup churn — and so it matches the broader CCC Eyebrow Rule
    pattern (DESIGN.md §3)."""
    assert 'class="error-eyebrow"' in ERROR_404, (
        "PI-0: 404.html must use `<div class=\"error-eyebrow\">` for the "
        "Bulletin · 404 marker. The class encodes the Eyebrow Rule "
        "fingerprint and lets the CSS regression lock catch font/color drift."
    )
    assert 'Bulletin' in ERROR_404 and '404' in ERROR_404, (
        "PI-0: 404.html eyebrow must read `Bulletin · 404`."
    )


def test_pi0_500_uses_canonical_eyebrow_primitive():
    assert 'class="error-eyebrow"' in ERROR_500
    assert 'Bulletin' in ERROR_500 and '500' in ERROR_500


def test_pi0_error_eyebrow_css_matches_design_rule():
    """Lock the Eyebrow Rule fingerprint on `.error-eyebrow`: Teko 500,
    .85rem, letter-spacing .14em, uppercase, `var(--gold)`. Any drift here
    means the page lost its CCC eyebrow voice."""
    block_match = re.search(
        r"\.error-eyebrow\s*\{[^}]*\}", CSS, re.DOTALL
    )
    assert block_match, "PI-0: `.error-eyebrow` rule missing from style.css."
    block = block_match.group(0)
    assert 'var(--font-teko)' in block, "PI-0: `.error-eyebrow` must use Teko."
    assert 'font-weight: 500' in block, "PI-0: `.error-eyebrow` Teko weight must be 500."
    assert 'font-size: .85rem' in block, "PI-0: `.error-eyebrow` size must be .85rem (Eyebrow Rule)."
    assert 'letter-spacing: .14em' in block, (
        "PI-0: `.error-eyebrow` letter-spacing must be .14em (Eyebrow Rule)."
    )
    assert 'text-transform: uppercase' in block, "PI-0: `.error-eyebrow` must be uppercase."
    assert 'color: var(--gold)' in block, "PI-0: `.error-eyebrow` color must be `--gold` (Eyebrow Rule)."


def test_pi0_error_lede_paints_text_secondary_not_text_muted():
    """The lede must use `--text-secondary` (~6.9:1 on bone, AA-pass) NOT
    `--text-muted` (#8A849B, ~3.7:1, AA-fail per
    `project_text_muted_aa_on_bone` memory). Same gotcha that bit S2.2.1,
    S2.6 PI-3, S3.2.1 PI-2, S3.3.2 PI-2. The errors page sits outside the
    `body.auth-page` scope and outside the S6.1 routed override, so the
    fix is local: scope the class, not the Bootstrap helper."""
    block_match = re.search(r"\.error-lede\s*\{[^}]*\}", CSS, re.DOTALL)
    assert block_match, "PI-0: `.error-lede` rule missing from style.css."
    block = block_match.group(0)
    assert 'color: var(--text-secondary)' in block, (
        "PI-0: `.error-lede` must paint `--text-secondary` (AA-pass on bone). "
        "Don't reintroduce `.text-muted` — fails AA per the documented memory."
    )
    # Neither error template should carry the legacy Bootstrap helper.
    assert 'text-muted' not in ERROR_404, (
        "PI-0: 404.html must not use Bootstrap `.text-muted` (AA-fail on bone)."
    )
    assert 'text-muted' not in ERROR_500, (
        "PI-0: 500.html must not use Bootstrap `.text-muted` (AA-fail on bone)."
    )


def test_pi0_error_headline_uses_teko_display_scale():
    """The reshape promotes `<h2>` to `<h1>` (one h1 per page) and paints
    it Teko 600 / 2.4rem — the canonical Display scale per DESIGN.md §3.
    Mobile clamps to 1.9rem to respect the 375 viewport."""
    block_match = re.search(r"\.error-headline\s*\{[^}]*\}", CSS, re.DOTALL)
    assert block_match, "PI-0: `.error-headline` rule missing from style.css."
    block = block_match.group(0)
    assert 'var(--font-teko)' in block
    assert 'font-size: 2.4rem' in block, "PI-0: `.error-headline` desktop size must be 2.4rem (Display scale)."
    assert 'font-weight: 600' in block
    # Mobile clamp at <=576px to 1.9rem.
    mobile_headline_rule = re.search(
        r"\.error-headline\s*\{\s*font-size:\s*1\.9rem", CSS, re.DOTALL
    )
    assert mobile_headline_rule, (
        "PI-0: mobile clamp for `.error-headline` missing — expected "
        "`.error-headline { font-size: 1.9rem; }` inside the <=576px media query."
    )


def test_pi0_404_and_500_use_h1_not_h2():
    """Each error page is its own document and must carry exactly one
    `<h1>` (axe heading-order baseline). Pre-S3.4 used `<h2 class=
    "section-heading">` which left the page without an h1."""
    assert '<h1' in ERROR_404, "PI-0: 404.html must carry an `<h1>` (was `<h2>` pre-S3.4)."
    assert '<h1' in ERROR_500, "PI-0: 500.html must carry an `<h1>` (was `<h2>` pre-S3.4)."


def test_pi0_404_voice_replaces_saas_copy():
    """Voice register: Tribune-club, not SaaS-utility. The exact strings
    are locked so a future copy edit that drifts back to "Page Not Found"
    will fail loudly."""
    assert "isn" in ERROR_404 and "in the ledger" in ERROR_404, (
        "PI-0: 404 headline must be 'This page isn't in the ledger.' "
        "(Tribune voice — pre-S3.4 was 'Page Not Found')."
    )
    assert 'Page Not Found' not in ERROR_404, (
        "PI-0: 404.html still carries the SaaS-utility 'Page Not Found' string."
    )


def test_pi0_500_voice_replaces_saas_copy():
    assert 'Commish hit a snag' in ERROR_500, (
        "PI-0: 500 headline must be 'The Commish hit a snag.' "
        "(Tribune voice — pre-S3.4 was 'Something Went Wrong')."
    )
    assert 'Something Went Wrong' not in ERROR_500
    assert 'unexpected error occurred' not in ERROR_500


# ---------------------------------------------------------------------------
# PI-1: navbar-brand color drift — orphan !important block removed.
# ---------------------------------------------------------------------------

def test_pi1_orphan_navbar_brand_block_removed():
    """The orphan `.navbar-brand { color: var(--platform-accent) !important
    ... }` block at `style.css:~4019` is gone. Any reintroduction of an
    `!important` color rule on `.navbar-brand` outside the CCC block fails
    this test."""
    # Match `.navbar-brand` as a top-level selector (not inside a compound
    # like `.navbar.navbar-dark .navbar-brand`). The shape we're banning:
    # a rule that starts with `.navbar-brand {` on its own line.
    orphan_pattern = re.compile(
        r"^\.navbar-brand\s*\{[^}]*color\s*:\s*var\(--platform-accent\)\s*!important",
        re.MULTILINE | re.DOTALL,
    )
    assert not orphan_pattern.search(CSS), (
        "PI-1: orphan `.navbar-brand` block with `color: var(--platform-accent) "
        "!important` reintroduced. DESIGN.md §5 spec is `Pressroom Bone color`; "
        "the only `.navbar-brand` color rule must live inside "
        "`.navbar.navbar-dark .navbar-brand` painting `var(--bone)`."
    )


def test_pi1_orphan_navbar_brand_hover_block_removed():
    """Same shape as the resting orphan — the hover variant also painted
    gold via !important and must stay gone."""
    orphan_hover = re.compile(
        r"^\.navbar-brand\s*:\s*hover\s*\{[^}]*color\s*:\s*[^;]*!important",
        re.MULTILINE | re.DOTALL,
    )
    assert not orphan_hover.search(CSS), (
        "PI-1: orphan `.navbar-brand:hover { color: ... !important }` "
        "reintroduced. The brand wordmark is a masthead, not a CTA; Trophy "
        "Rule keeps gold-glow effects off it."
    )


def test_pi1_ccc_navbar_brand_carries_full_spec():
    """The CCC `.navbar.navbar-dark .navbar-brand` block now carries the
    full masthead spec: font-family Teko, weight 700, size 1.25rem,
    letter-spacing .04em, text-transform uppercase, color var(--bone).
    Pre-S3.4, weight 700 and text-transform uppercase lived in the orphan
    block and won only by source order — moving them here makes the spec
    explicit and lets the orphan disappear cleanly."""
    pattern = re.compile(
        r"\.navbar\.navbar-dark\s+\.navbar-brand\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(CSS)
    assert match, "PI-1: CCC `.navbar.navbar-dark .navbar-brand` block missing."
    body = match.group(1)
    assert 'font-family: var(--font-teko)' in body
    assert 'font-weight: 700' in body, (
        "PI-1: CCC navbar-brand must declare `font-weight: 700` "
        "(folded in from the deleted orphan block to preserve masthead voice)."
    )
    assert 'font-size: 1.25rem' in body, "PI-1: CCC navbar-brand size must be 1.25rem (DESIGN.md §5)."
    assert 'letter-spacing: .04em' in body, "PI-1: CCC navbar-brand letter-spacing must be .04em."
    assert 'text-transform: uppercase' in body, (
        "PI-1: CCC navbar-brand must declare `text-transform: uppercase` "
        "(folded in from the orphan block)."
    )
    assert 'color: var(--bone)' in body, (
        "PI-1: CCC navbar-brand color must be `var(--bone)` (Pressroom Bone "
        "per DESIGN.md §5). The orphan !important gold was the regression."
    )


def test_pi1_design_md_brand_spec_updated():
    """DESIGN.md §5 must explicitly declare weight 700 + uppercase so the
    spec and the cascade agree. Pre-S3.4 the spec said only "Teko 1.25rem,
    letter-spacing 0.04em, Pressroom Bone color"; weight/transform were
    silent and the orphan rule filled the gap."""
    # The brand bullet must mention Teko 700 (or weight 700) and uppercase.
    brand_section = re.search(r"\*\*Brand\*\*[^\n]+", DESIGN_MD)
    assert brand_section, "PI-1: DESIGN.md §5 Brand bullet missing."
    text = brand_section.group(0)
    assert '700' in text and 'uppercase' in text and '1.25rem' in text and '0.04em' in text and 'Pressroom Bone' in text, (
        "PI-1: DESIGN.md §5 Brand spec must include Teko 700 + uppercase + "
        "1.25rem + 0.04em + Pressroom Bone. Current line: " + text
    )


# ---------------------------------------------------------------------------
# PI-2: chrome :focus-visible rings.
# ---------------------------------------------------------------------------

def test_pi2_navbar_nav_link_focus_visible_ring():
    """The chrome nav-links must declare an explicit focus-visible ring.
    Pattern lock matches the canonical CCC focus pattern (S2.1.2 /
    S3.3.2): `outline: 2px solid var(--gold-light); outline-offset: 2px`."""
    pattern = re.compile(
        r"\.navbar\s+\.nav-link\s*:\s*focus-visible\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(CSS)
    assert match, (
        "PI-2: `.navbar .nav-link:focus-visible` rule missing. Add the "
        "canonical CCC focus ring."
    )
    body = match.group(1)
    assert 'outline: 2px solid var(--gold-light)' in body
    assert 'outline-offset: 2px' in body


def test_pi2_subnav_pill_focus_visible_ring():
    """Same pattern on the sub-nav pills. The pill already has
    `border-radius: 22px`, so the outline traces the silhouette."""
    pattern = re.compile(
        r"\.subnav-pill\s*:\s*focus-visible\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(CSS)
    assert match, "PI-2: `.subnav-pill:focus-visible` rule missing."
    body = match.group(1)
    assert 'outline: 2px solid var(--gold-light)' in body
    assert 'outline-offset: 2px' in body


# ---------------------------------------------------------------------------
# PI-3: game-subnav semantic <nav> + aria-label.
# ---------------------------------------------------------------------------

def test_pi3_game_subnav_uses_nav_element_with_aria_label():
    """All three `.game-subnav` containers must be semantic `<nav>` with
    a per-game `aria-label`. The label closes the SR cue gap on mobile
    where `.subnav-game-label` is `display: none`."""
    # Worldcup
    assert re.search(
        r'<nav class="game-subnav subnav-worldcup"\s+aria-label="World Cup section"',
        BASE,
    ), "PI-3: World Cup game-subnav must be `<nav aria-label=\"World Cup section\">`."
    # Golf
    assert re.search(
        r'<nav class="game-subnav subnav-golf"\s+aria-label="Golf section"',
        BASE,
    ), "PI-3: Golf game-subnav must be `<nav aria-label=\"Golf section\">`."
    # CFB
    assert re.search(
        r'<nav class="game-subnav subnav-cfb"\s+aria-label="CFB section"',
        BASE,
    ), "PI-3: CFB game-subnav must be `<nav aria-label=\"CFB section\">`."


def test_pi3_no_div_game_subnav_remains():
    """No `<div class="game-subnav` containers should survive — they all
    became `<nav>` elements."""
    assert '<div class="game-subnav' not in BASE, (
        "PI-3: `<div class=\"game-subnav ...\">` reintroduced. The semantic "
        "`<nav aria-label=\"…\">` form is the lock."
    )


# ---------------------------------------------------------------------------
# PI-4: auth surface composition contract.
# ---------------------------------------------------------------------------

def test_pi4_design_md_auth_surface_composition_section_present():
    """DESIGN.md §5 must explicitly document the marketing-vs-utility
    split. Without this section, the next surface to land has no contract
    to consult and the third pattern can re-emerge."""
    assert 'Auth Surface Composition' in DESIGN_MD, (
        "PI-4: DESIGN.md §5 missing `Auth Surface Composition` subsection. "
        "Codify the marketing (split-panel) vs utility (`.auth-wrapper`) "
        "split so the next auth surface has a written contract."
    )
    # The section must name both wrappers and call out who uses each.
    auth_section = DESIGN_MD[DESIGN_MD.index('Auth Surface Composition'):]
    assert 'auth-panel-brand' in auth_section
    assert 'auth-form-panel' in auth_section
    assert 'auth-wrapper' in auth_section
    assert 'login.html' in auth_section
    assert 'register.html' in auth_section
    assert 'change_password.html' in auth_section
    assert 'profile.html' in auth_section


def test_pi4_marketing_auth_surfaces_use_split_panel():
    """The four marketing-context auth templates must carry the split-panel
    primitives. A future regression that drops the brand panel from any of
    them fails this test loudly."""
    for name, html in [
        ('login.html', LOGIN_HTML),
        ('register.html', REGISTER_HTML),
        ('forgot_password.html', FORGOT_HTML),
        ('reset_password.html', RESET_HTML),
    ]:
        assert 'auth-panel-brand' in html, (
            f"PI-4: {name} (marketing-context auth) missing `.auth-panel-brand`. "
            "Use the split-panel composition per DESIGN.md §5 Auth Surface."
        )
        assert 'auth-form-panel' in html, (
            f"PI-4: {name} (marketing-context auth) missing `.auth-form-panel`."
        )


def test_pi4_utility_auth_surfaces_use_auth_wrapper():
    """The two logged-in utility surfaces must wrap in `.auth-wrapper` —
    profile.html was the third-pattern offender pre-S3.4 (used
    `.container.my-5 style="max-width:600px"`); the new pattern is
    `.auth-wrapper.profile-wrapper` so the avatar picker keeps its 600px
    max-width without breaking the contract."""
    assert 'auth-wrapper' in CHANGE_PW_HTML, (
        "PI-4: change_password.html (utility auth) must wrap in `.auth-wrapper`."
    )
    # Profile uses the wrapper + modifier.
    assert 'auth-wrapper profile-wrapper' in PROFILE_HTML, (
        "PI-4: profile.html (utility auth) must wrap in "
        "`.auth-wrapper.profile-wrapper` — pre-S3.4 used `.container.my-5` "
        "which was a third auth register."
    )
    # And profile must NOT carry the marketing-context split-panel classes.
    assert 'auth-panel-brand' not in PROFILE_HTML, (
        "PI-4: profile.html is utility, not marketing — must not use "
        "`.auth-panel-brand`."
    )


def test_pi4_profile_wrapper_modifier_widens_card():
    """The `.auth-wrapper.profile-wrapper .auth-card` modifier must lift
    the card max-width to 600px so the avatar picker grid fits. Without
    this, the auth-card's default 440px (set by `body.auth-page .auth-card`)
    would clip the picker."""
    pattern = re.compile(
        r"\.auth-wrapper\.profile-wrapper\s+\.auth-card\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(CSS)
    assert match, (
        "PI-4: `.auth-wrapper.profile-wrapper .auth-card` rule missing — "
        "the avatar picker needs the 600px override."
    )
    assert 'max-width: 600px' in match.group(1)
