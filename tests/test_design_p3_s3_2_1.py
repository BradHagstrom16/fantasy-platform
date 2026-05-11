"""P3 S3.2.1 regression locks — auth cluster first iteration.

Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S3.2.1. The auth cluster covers 6 surfaces (login, register,
forgot_password, reset_password, change_password, profile); each test pins
a cluster-wide design decision so a future template edit can't silently
regress the convergence work.

Iteration map:
- PI-1 (`$impeccable adapt` — carries §0.4 S0.3 backlog): cross-flow link
  rows ("Lost your key?", "Not on the rolls yet? Join the Club",
  "Back to Profile", "Change Password", etc.) used `text-muted small` +
  inline `font-size:.83rem`/`.88rem` and rendered at 14-37px tall — below
  the PRODUCT.md 44×44 mobile floor. Replaced with `.auth-link-row` (min-
  height 44px container) wrapping a 44×44 inline-flex `<a>` with
  `:focus-visible` ring on `--gold`, and the link copy resolved to
  `--gold-dark` (~5.07:1 on bone, AA-passing) instead of `--gold`
  (~3.6:1 on bone, AA-fail).

- PI-2 (`$impeccable polish` — auth-card contrast on bone): `.auth-subtitle`
  at style.css:4904 pointed at `--text-muted` (#8A849B), which clears only
  ~3.13:1 against the bone card — sub-AA. Bootstrap 5.3 paints `.text-muted`
  via `--bs-secondary-color !important`, so a bare `body.auth-page
  .text-muted` rule loses the cascade. Scope: `body.auth-page
  .auth-subtitle, body.auth-page .form-text { color: var(--text-secondary); }`
  + `!important`-bearing overrides on `body.auth-page a/span/p/small
  .text-muted` so the auth card lands at `--text-secondary` (~6.9:1 on
  bone). Memory `project_text_muted_aa_on_bone.md` documented this gotcha
  during S2.2.1; the auth cluster surfaced a second hit.

- PI-3 (`$impeccable polish` — brand-panel contrast on purple): `.auth-
  panel-brand .brand-sub` at style.css:4833 used `rgba(255,255,255,.45)`
  on the council-purple gradient — ~3.83:1 at mid-stop, AA-fail. Lift to
  `.78` (`.brand-sub`) and `.82` (`.brand-game-item`) so the body copy on
  the brand panel clears AA across all three gradient stops.

- PI-4 (`$impeccable adapt` — mobile bleed-through): at <768px the brand
  panel collapses (`display: none`) but the form-panel's `var(--bg-page)`
  bone fill stayed full-width, painting a bone slab over the body.auth-
  page Tribunal Black radial gradient. The card stopped lifting off the
  atmosphere; the entire mobile auth surface read bone-on-bone. Scope:
  `@media (max-width: 767.98px) { .auth-form-panel { background:
  transparent; } }` lets the body backdrop bleed through and the bone
  card sit on Tribunal Black where DESIGN.md §6 says it should.

- PI-5 (`$impeccable clarify` — Tribune voice register): subtitles +
  cross-flow phrasings across all 6 surfaces collapsed into generic SaaS
  ("Sign in to your account", "Sign up to enter games", "Enter the email
  address associated with your account", "New to the platform?", "Already
  have an account?"). Rewrote to Tribune voice per PRODUCT.md §1 Voice +
  DESIGN.md North Star "The Commissioner's Club Tribune": chamber / key /
  rolls / Club register. Banned strings locked below.

Freebies batched at end-of-iteration:
- F1: `register.html` submit button class `.btn-warning` → `.btn-primary`.
  Both render gold metal via `body.auth-page .btn-primary`; the
  `.btn-warning` markup was a confusing inconsistency with login's
  `.btn-primary`. The body.auth-page rule paints both gold, but markup
  honesty matters for future maintainers.
- F2: register inline-style sweep — `style="max-width:460px"` on the card
  (overrode the bone-card max-width 440 from `body.auth-page .auth-card`)
  and `style="font-size:.78rem;text-transform:none;letter-spacing:0;"` on
  the "(optional)" parenthetical span. Both replaced with class
  references (no over-ride on the card; new `.form-label-meta` utility for
  the parenthetical).

Routed forward to receiving sessions per §0.4 (locked in §9 rollup):
- [S3.2.1 in-surface] PI-A avatar picker reshape + profile inline `<style>`
  → S3.2.2 (needs shape brief; bigger than this iteration's atomic-edit
  budget).
- [S3.2.1 in-surface] PI-D decorative gold key icon on change-password →
  S3.2.2 (Trophy Rule adjacency; not load-bearing for this iteration).
- [S3.2.1 in-surface] PI-E required-asterisk uses Bootstrap `#DC3545`
  not CCC `--danger` → S3.2.2 (token swap; same scope as the freebie
  refactor pass).
- [S3.2.1 in-surface] PI-F register password placeholder truncation at
  `<540px` → S3.2.2 (stack the col-6 pair below the breakpoint).
- [S3.2.1 cross-cluster] PI-B split-panel vs auth-wrapper layout contract
  → S3.4 (chrome cross-cluster polish; documents which auth layout fits
  which auth phase: marketing-context vs. logged-in utility).
- [S3.2.1 cross-phase] PI-C cluster-wide `.text-muted` `!important` fight
  with Bootstrap → S6.1 (visible across game surfaces too; needs a single
  site-wide pass).
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
LOGIN = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'login.html').read_text()
REGISTER = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'register.html').read_text()
FORGOT = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'forgot_password.html').read_text()
RESET = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'reset_password.html').read_text()
CHANGE = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'change_password.html').read_text()
PROFILE = (ROOT / 'core' / 'auth' / 'templates' / 'auth' / 'profile.html').read_text()

ALL_AUTH = {
    'login.html': LOGIN,
    'register.html': REGISTER,
    'forgot_password.html': FORGOT,
    'reset_password.html': RESET,
    'change_password.html': CHANGE,
    'profile.html': PROFILE,
}


# ---------------------------------------------------------------------------
# PI-1: 44×44 tap-target floor on cross-flow link rows
# ---------------------------------------------------------------------------

def test_auth_pi1_link_row_utility_locks_min_height_44px():
    """`.auth-link-row` and its `<a>` child both carry `min-height: 44px` so
    cross-flow links (forgot, register-from-login, sign-in-from-register,
    back-to-profile, change-password) clear the PRODUCT.md mobile floor at
    375 viewport. Source lock here; the Layer B Playwright probe verifies
    the rendered bounding rect at session time."""
    block = re.compile(
        r'\.auth-link-row\s*\{[^}]*min-height:\s*44px[^}]*\}',
        re.DOTALL,
    )
    assert block.search(CSS), (
        "PI-1: `.auth-link-row { min-height: 44px }` missing — cross-flow link "
        "rows lose the 44×44 floor."
    )
    inner = re.compile(
        r'\.auth-link-row\s+a\s*\{[^}]*min-height:\s*44px[^}]*\}',
        re.DOTALL,
    )
    assert inner.search(CSS), (
        "PI-1: `.auth-link-row a { min-height: 44px }` missing — the link itself "
        "must be a 44×44 inline-flex target, not just the wrapper."
    )


def test_auth_pi1_link_row_has_focus_visible_ring():
    """Keyboard users need to see where focus lands. PI-1 added a
    `:focus-visible` outline on `--gold` so the moment of arrival reads
    against the bone card."""
    pattern = re.compile(
        r'body\.auth-page\s+\.auth-link-row\s+a:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--gold\)',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "PI-1: `:focus-visible` ring on `.auth-link-row a` missing — keyboard "
        "users lose the focus indicator."
    )


def test_auth_pi1_no_legacy_text_muted_small_on_cross_flow_links():
    """The pre-S3.2.1 pattern was `<a class="text-muted small">…</a>` for
    cross-flow links on change_password + profile (probed 121×14 — fail).
    Lock that the pattern is gone."""
    offenders = []
    for name, src in (('change_password.html', CHANGE), ('profile.html', PROFILE)):
        if 'class="text-muted small"' in src:
            offenders.append(name)
    assert not offenders, (
        f"PI-1: legacy `text-muted small` cross-flow link pattern still present "
        f"in {offenders} — replace with `.auth-link-row` wrapper."
    )


def test_auth_pi1_no_inline_font_size_on_cross_flow_links():
    """The pre-S3.2.1 pattern used inline `style="font-size:.83rem"` /
    `style="font-size:.88rem"` to make the link rows artificially small.
    Lock that the inline overrides are gone across all 6 auth surfaces."""
    offenders = []
    for name, src in ALL_AUTH.items():
        if re.search(r'style="font-size:\.(?:83|88)rem;?"', src):
            offenders.append(name)
    assert not offenders, (
        f"PI-1: inline `font-size:.83rem` / `font-size:.88rem` override still "
        f"present in {offenders} — these were the original cross-flow tap-target "
        f"shrinkage and should be gone after S3.2.1."
    )


def test_auth_pi1_every_auth_surface_with_cross_flow_uses_auth_link_row():
    """The 5 surfaces with cross-flow link rows (login, register, forgot,
    reset, change_password, profile) all wrap cross-flow links in
    `.auth-link-row`. reset_password has its 'Request another' link; login
    has both 'Lost your key?' AND 'Join the Club'."""
    expected = {
        'login.html': 2,        # forgot + register
        'register.html': 1,     # sign-in
        'forgot_password.html': 1,  # sign-in
        'reset_password.html': 1,   # forgot-password
        'change_password.html': 1,  # back-to-profile
        'profile.html': 1,      # change-password
    }
    for name, count in expected.items():
        actual = ALL_AUTH[name].count('auth-link-row')
        assert actual >= count, (
            f"PI-1: {name} should carry at least {count} `.auth-link-row` "
            f"occurrence(s); found {actual}."
        )


# ---------------------------------------------------------------------------
# PI-2: `.auth-subtitle` + `.form-text` contrast lift off `--text-muted`
# ---------------------------------------------------------------------------

def test_auth_pi2_subtitle_resolves_to_text_secondary_in_auth_scope():
    """`body.auth-page .auth-subtitle { color: var(--text-secondary); }`
    lifts the cluster subtitle off `--text-muted` (3.13:1 AA-fail) onto
    `--text-secondary` (~6.9:1 AA-pass)."""
    pattern = re.compile(
        r'body\.auth-page\s+\.auth-subtitle[^{]*,\s*body\.auth-page\s+\.form-text\s*\{[^}]*color:\s*var\(--text-secondary\)',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "PI-2: `body.auth-page .auth-subtitle, body.auth-page .form-text { "
        "color: var(--text-secondary) }` missing — subtitle still sub-AA on bone."
    )


def test_auth_pi2_text_muted_override_uses_important_to_beat_bootstrap():
    """Bootstrap 5.3 paints `.text-muted` via `--bs-secondary-color
    !important`. PI-2's overrides on `body.auth-page a/span/p/small
    .text-muted` carry `!important` themselves so the auth scope wins
    inside the card. The cluster-wide `.text-muted` migration (paint all
    sites in `--text-secondary` without the !important fight) routes
    forward to S6.1 per §0.4."""
    pattern = re.compile(
        r'body\.auth-page\s+a\.text-muted[^{]*\{[^}]*color:\s*var\(--text-secondary\)\s*!important',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "PI-2: `body.auth-page <tag>.text-muted` override missing the "
        "`!important` modifier — Bootstrap's own `!important` will win the "
        "cascade and the cluster falls back to sub-AA gray."
    )


# ---------------------------------------------------------------------------
# PI-3: brand-panel contrast lift on the purple gradient
# ---------------------------------------------------------------------------

def test_auth_pi3_brand_sub_alpha_lifted_off_045():
    """`.auth-panel-brand .brand-sub` alpha was `.45` (AA-fail at mid-stop
    of the council-purple gradient). PI-3 lifts to `.78` to clear AA.

    Cascade-aware: the S3.2.1 patch adds a second `.brand-sub` block with
    the new alpha; CSS cascade resolves to the later (higher-alpha) value.
    Both `.45` and `.78` will appear in the source if the override is
    layered; the lock here is that the LAST block resolves to `.78`+ so
    the rendered color clears AA."""
    blocks = re.findall(
        r'\.auth-panel-brand\s+\.brand-sub\s*\{[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*\.(\d{2,3})',
        CSS,
        re.DOTALL,
    )
    assert blocks, "PI-3: no `.auth-panel-brand .brand-sub` color rule found."
    last_alpha = int(blocks[-1])
    assert last_alpha >= 75, (
        f"PI-3: last `.auth-panel-brand .brand-sub` block resolves to alpha "
        f".{blocks[-1]}, below the .75 AA threshold on the council-purple "
        f"gradient. All blocks in source order: {blocks}"
    )


def test_auth_pi3_brand_game_item_alpha_lifted_off_07():
    """`.auth-panel-brand .brand-game-item` was `.7` alpha (marginal AA
    on the lighter gradient stops). PI-3 lifts to `.82`."""
    # PI-3 patched the override block (not the original definition at :4859).
    # Lock the override exists with the higher alpha.
    found = re.findall(
        r'\.auth-panel-brand\s+\.brand-game-item\s*\{[^}]*color:\s*rgba\(255,\s*255,\s*255,\s*\.(\d{1,2})',
        CSS,
        re.DOTALL,
    )
    assert any(int(alpha) >= 80 for alpha in found), (
        f"PI-3: `.auth-panel-brand .brand-game-item` should carry "
        f"`rgba(255,255,255,.82)` or higher; found alpha values {found}."
    )


# ---------------------------------------------------------------------------
# PI-4: Mobile Tribunal Black bleed-through (form-panel transparent <768px)
# ---------------------------------------------------------------------------

def test_auth_pi4_mobile_form_panel_drops_bone_fill():
    """At `<768px` the brand panel collapses; the form-panel's bone fill
    must drop so the body.auth-page Tribunal Black radial gradient shows
    through. Lock the media query and the `transparent` background."""
    pattern = re.compile(
        r'@media\s*\(max-width:\s*767\.98px\)\s*\{[^@]*\.auth-form-panel\s*\{[^}]*background:\s*transparent',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "PI-4: `@media (max-width: 767.98px) { .auth-form-panel { background: "
        "transparent } }` missing — mobile auth surfaces still show a bone "
        "slab over the Tribunal Black backdrop."
    )


# ---------------------------------------------------------------------------
# PI-5: Tribune voice register (SaaS phrasings banned; chamber/key/rolls present)
# ---------------------------------------------------------------------------

GENERIC_SAAS_PHRASES = [
    "Sign in to your account",
    "Sign up to enter games",
    "Enter the email address associated with your account",
    "Enter your new password below",
    "Update your account password",
    "New to the platform?",
    "Already have an account?",
    "Remember your password?",
    "Need a new reset link?",
]


def test_auth_pi5_no_generic_saas_subtitles_across_cluster():
    """Subtitles + cross-flow phrasings across all 6 surfaces were
    rewritten away from generic SaaS in PI-5. Lock the SaaS phrasings out
    of every auth template."""
    offenders = []
    for phrase in GENERIC_SAAS_PHRASES:
        for name, src in ALL_AUTH.items():
            if phrase in src:
                offenders.append(f"{name} :: '{phrase}'")
    assert not offenders, (
        f"PI-5: generic SaaS phrasings reappeared in auth templates:\n  "
        + "\n  ".join(offenders)
    )


TRIBUNE_PHRASES = [
    ('login.html', 'Step back into the chamber.'),
    ('login.html', 'Lost your key?'),
    ('login.html', 'Not on the rolls yet?'),
    ('login.html', 'Join the Club'),
    ('register.html', 'Inscribe your name on the rolls.'),
    ('register.html', 'Already on the rolls?'),
    ('forgot_password.html', "We'll mail a new key. Address on file?"),
    ('forgot_password.html', 'Found it?'),
    ('reset_password.html', 'Forge a new key. Make it strong.'),
    ('reset_password.html', "Key didn't take?"),
    ('change_password.html', 'Forge a new key for the chamber.'),
]


def test_auth_pi5_tribune_phrases_present():
    """PI-5 voice rewrite landed across the cluster. Each surface carries
    at least one Tribune-register phrase from the rewrite. If a future
    edit reverts copy to SaaS, this test pins it."""
    missing = []
    for name, phrase in TRIBUNE_PHRASES:
        if phrase not in ALL_AUTH[name]:
            missing.append(f"{name} :: '{phrase}'")
    assert not missing, (
        f"PI-5: Tribune-register phrases missing from auth templates:\n  "
        + "\n  ".join(missing)
    )


# ---------------------------------------------------------------------------
# Freebies: F1 register button class consistency, F2 inline-style sweep
# ---------------------------------------------------------------------------

def test_auth_freebie_f1_register_uses_btn_primary_not_btn_warning():
    """register.html previously used `.btn-warning` for its submit while
    login.html used `.btn-primary`; the `body.auth-page` block paints both
    gold via `.btn-primary`, so `.btn-warning` was misleading markup. F1
    normalizes both surfaces to `.btn-primary btn-lg`."""
    assert 'btn btn-warning' not in REGISTER, (
        "Freebie F1: register.html still uses `btn-warning` — should be "
        "`btn-primary` for cluster consistency."
    )
    assert 'btn btn-primary btn-lg' in REGISTER, (
        "Freebie F1: register.html submit button missing `btn btn-primary "
        "btn-lg` class — expected after F1 swap."
    )


def test_auth_freebie_f2_register_drops_inline_card_max_width_override():
    """Block A's `body.auth-page .auth-card` sets `max-width: 440px`.
    register.html previously inlined `style="max-width:460px"` to override.
    F2 deletes the override; the auth-card primitive runs unmodified."""
    assert 'style="max-width:460px;"' not in REGISTER, (
        "Freebie F2: register.html still inlines `style=\"max-width:460px;\"` "
        "on the auth-card — drop and let the auth-card primitive govern."
    )


def test_auth_freebie_f2_form_label_meta_replaces_inline_optional_span():
    """The `(optional)` parenthetical span on register.html was inlined
    with `style="font-size:.78rem;text-transform:none;letter-spacing:0;"`.
    F2 introduces a `.form-label-meta` utility for the lower-register
    aside style and the inline override is gone."""
    assert 'style="font-size:.78rem;text-transform:none;letter-spacing:0;"' not in REGISTER, (
        "Freebie F2: register.html still inlines the optional-span "
        "font-size/text-transform/letter-spacing — replace with "
        "`.form-label-meta` class."
    )
    assert 'form-label-meta' in REGISTER, (
        "Freebie F2: `.form-label-meta` class reference missing from "
        "register.html `(optional)` parenthetical."
    )
    assert '.form-label-meta' in CSS, (
        "Freebie F2: `.form-label-meta` class definition missing from "
        "style.css."
    )


# ---------------------------------------------------------------------------
# Rendered-HTML locks via Flask test client (Layer A flavor 2)
# ---------------------------------------------------------------------------

def test_auth_pi5_login_renders_tribune_subtitle():
    """Rendered-HTML check: hitting `/login` returns the Tribune subtitle,
    not the SaaS subtitle. Pin the rendered output so a future template
    inheritance / block-override regression is caught."""
    from app import create_app
    from extensions import db

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        client = app.test_client()
        resp = client.get('/login')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'Step back into the chamber.' in body
        assert 'Sign in to your account' not in body
        # Cross-flow links are tap-target wrappers, not bare anchors
        assert 'auth-link-row' in body
        assert 'Lost your key?' in body
        assert 'Join the Club' in body


def test_auth_pi5_register_renders_tribune_subtitle_and_btn_primary():
    """Rendered-HTML check for /register: Tribune subtitle, btn-primary
    (not btn-warning), no inline-style overrides."""
    from app import create_app
    from extensions import db

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        client = app.test_client()
        resp = client.get('/register')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert 'Inscribe your name on the rolls.' in body
        assert 'Sign up to enter games' not in body
        assert 'btn btn-primary btn-lg' in body
        # `btn btn-warning btn-lg` was the register submit's exact pre-F1
        # class set; the global navbar still uses `btn-warning btn-sm` for
        # the trophy "Join the Club" CTA, so we lock against the lg variant
        # specifically (not bare `btn-warning`).
        assert 'btn btn-warning btn-lg' not in body
        assert 'style="max-width:460px;"' not in body
        assert 'form-label-meta' in body


def test_auth_pi5_forgot_password_renders_tribune_copy():
    """Rendered-HTML check for /forgot-password."""
    from app import create_app
    from extensions import db

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        client = app.test_client()
        resp = client.get('/forgot-password')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert "We&#39;ll mail a new key. Address on file?" in body or "We'll mail a new key. Address on file?" in body
        assert 'Enter the email address associated with your account' not in body
        assert 'Found it?' in body


def test_auth_no_em_dash_in_voice_rewrite():
    """P0 S0.3 banned em-dashes from UI copy. PI-5's rewrite must not
    reintroduce them via `—` or `--`."""
    em_dash_offenders = []
    for name, src in ALL_AUTH.items():
        # `--` legitimately appears in CSS var refs, but no template body
        # carries CSS. So a `--` outside `var(--…)` shouldn't appear
        # anywhere. Em-dash `—` is unambiguous.
        if '—' in src:
            em_dash_offenders.append(name)
    assert not em_dash_offenders, (
        f"PI-5: em-dash `—` reintroduced in auth template(s): {em_dash_offenders}. "
        f"P0 S0.3 locked these out."
    )
