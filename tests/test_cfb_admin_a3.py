"""CFB Admin cluster / "The Commissioner's Desk" locks (A3-admin).

A2.0 stood up the dark substrate; A2-A6 brought the five player screens to the
games/cfb/DESIGN.md bar. A3-admin is the operational register: the 8
games/cfb/templates/cfb/admin/* surfaces (blueprint cfb, @cfb_admin_required)
brought to the same bar on the dark foundation. This is the commissioner's back
office, distinct from the player screens: it serves the commish running the pool,
not a player making a decision, so it keeps FUNCTIONAL H1s (the platform
dispensation for utility surfaces) and carries the register through a midnight
masthead, not the player .page-hero.

The central design decision these locks encode: the platform admin masthead is
gold-on-bone (.admin-eyebrow gold + .admin-page-title purple-700 + a gold rule),
calibrated for the bone canvas; on the CFB midnight canvas it would drift gold +
render purple-on-purple. The CFB admin register re-derives it for the room -- a
bone-muted .cfb-eyebrow ("The Commissioner's Desk"), a bone-white functional H1
(.cfb-admin-title), and the gold ceremonial rule swapped for a thin CRIMSON rule.
NO gold (the Crimson-Ceremony Rule).

Each lock fails on the pre-A3-admin raw-Bootstrap state and passes once A3-admin
lands, via the established CSS-scan idioms (anchored regex over style.css + the
templates). ASCII-only per the CFB phase rule; non-ASCII glyphs via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
ADMIN_DIR = ROOT / "games" / "cfb" / "templates" / "cfb" / "admin"

# The 8 admin templates the cluster covers.
ADMIN_NAMES = [
    "dashboard.html", "create_week.html", "manage_games.html", "manage_teams.html",
    "mark_results.html", "review_scores.html", "users.html", "payments.html",
]
ADMIN_TPLS = {name: (ADMIN_DIR / name).read_text() for name in ADMIN_NAMES}
# Jinja {# ... #} comments are not rendered, so "must NOT contain" content locks
# scan a comment-stripped body (the documented template-source corollary).
ADMIN_BODIES = {name: re.sub(r"\{#.*?#\}", "", tpl, flags=re.S) for name, tpl in ADMIN_TPLS.items()}

EM_DASH = chr(0x2014)   # em dash (chr() keeps the source ASCII-clean)

# The A3-admin CSS region: from its header banner to the next section (WC
# overrides). Slicing it lets the side-stripe / no-gold / primitive scans target
# only A3-admin (the player "A3 -- Pick screen" block is a separate region).
_A3 = re.search(r"/\*[^*]*A3-admin -- Admin cluster.*?(?=/\* World Cup overrides \*/)", CSS, re.S)


def _a3_block():
    assert _A3, "the A3-admin CSS block (header 'A3-admin -- Admin cluster') must exist in style.css"
    return _A3.group(0)


def _a3_rules():
    """The A3-admin region with /* */ comments stripped -- for property / token
    scans that must not trip on prose in the doctrine comments (e.g. the words
    'gold' / 'purple' in 'NO gold ... would drift gold ... render purple-on-purple')."""
    return re.sub(r"/\*.*?\*/", "", _a3_block(), flags=re.S)


# -- The Commissioner's Desk masthead on every admin surface (the register) ----

def test_every_admin_surface_carries_the_commissioners_desk_masthead():
    for name, tpl in ADMIN_TPLS.items():
        assert "cfb-admin-masthead" in tpl, f"{name}: must open on the .cfb-admin-masthead (no bare <h1> in a container)"
        assert "cfb-admin-title" in tpl, f"{name}: the functional H1 must be the .cfb-admin-title (bone-white Teko on midnight)"
        assert "cfb-eyebrow" in tpl, f"{name}: the masthead must carry the .cfb-eyebrow register label"
        assert "Commissioner" in tpl, f"{name}: the eyebrow must carry 'The Commissioner's Desk' register"


def test_admin_does_not_use_the_gold_platform_masthead():
    # The platform .admin-masthead / .admin-eyebrow are gold-on-bone; on the CFB
    # midnight canvas they drift gold + render purple H1. The CFB admin register
    # uses .cfb-admin-masthead / .cfb-eyebrow instead. (cfb-admin-masthead contains
    # the substring 'admin-masthead', so anchor on a non-[-\w] boundary.)
    for name, tpl in ADMIN_TPLS.items():
        assert not re.search(r"(?<![-\w])admin-masthead", tpl), \
            f"{name}: must not use the gold platform .admin-masthead (use .cfb-admin-masthead)"
        assert not re.search(r"(?<![-\w])admin-eyebrow", tpl), \
            f"{name}: must not use the gold platform .admin-eyebrow (use .cfb-eyebrow)"


# -- No em-dash / double-hyphen copy across the cluster (the named A3 debt) -----

def test_no_em_dash_or_double_hyphen_in_admin_copy():
    for name, body in ADMIN_BODIES.items():
        assert "&mdash;" not in body, f"{name}: the &mdash; copy debt must be gone (titles + H2s + the CFP note)"
        assert "&ndash;" not in body, f"{name}: no &ndash; en-dash entity in admin copy"
        assert EM_DASH not in body, f"{name}: no literal em-dash may appear in admin copy"
        # No visible-text '--' (the no-double-hyphen half): the winner <option>
        # placeholders were '--', the spread 'TBD' note etc.
        assert re.search(r">\s*[^<]*--[^<]*<", body) is None, \
            f"{name}: no visible double-hyphen copy ('--') may appear in admin copy"


# -- Off-palette Bootstrap semantics drained onto the CFB vocabulary -----------

# The loud Bootstrap color zoo (foreign amber bg-warning, blue bg-info, gray
# btn-secondary, the bg-* badges, the text-success/-danger pips) must be gone.
# Only btn-danger survives -- the Delete action, scoped to a restrained lost-red
# OUTLINE (not a filled red shout).
_FORBIDDEN_BS = [
    "bg-success", "bg-warning", "bg-info", "bg-secondary", "bg-primary",
    "btn-secondary", "btn-success", "btn-info", "btn-warning",
    "btn-outline-secondary", "btn-outline-primary", "btn-outline-light",
    "text-success", "text-danger",
]


def test_off_palette_bootstrap_semantics_drained():
    for name, tpl in ADMIN_TPLS.items():
        for cls in _FORBIDDEN_BS:
            assert cls not in tpl, f"{name}: off-palette Bootstrap '{cls}' must be drained onto the CFB vocabulary"


def test_destructive_delete_is_restrained_lost_red_outline():
    # The one surviving Bootstrap color class is btn-danger (Delete), and the CFB
    # dark form makes it a lost-red OUTLINE, never a filled red shout.
    assert "btn-danger" in ADMIN_TPLS["manage_games.html"], "the Delete action keeps btn-danger (scoped to lost-red outline)"
    rules = _a3_rules()
    m = re.search(r"body\.game-cfb\s+\.btn-danger\s*\{([^}]*)\}", rules)
    assert m, "the A3-admin block must dark-form body.game-cfb .btn-danger"
    assert "transparent" in m.group(1), "the Delete button must be a lost-red OUTLINE (transparent fill), not a filled red shout"
    assert "--cfb-lost-life" in m.group(1), "the Delete outline uses the survivor lost-red, distinct from identity crimson"


# -- The admin lives pips use the .lives-indicator primitive (not red pips) -----

def test_admin_lives_use_the_lives_indicator_primitive():
    # users + payments rendered ad-hoc <span class="text-success/danger"> filled
    # dots -- filled RED for a lost life violated the Crimson-Is-Identity Rule
    # (loss is hollow ash, never filled red). Both now use the real primitive.
    for name in ("users.html", "payments.html"):
        tpl = ADMIN_TPLS[name]
        assert "lives-indicator" in tpl, f"{name}: lives must render via the .lives-indicator primitive"
        assert 'class="life lost"' in tpl, f"{name}: a lost life must be the hollow-ash .life.lost, not a filled red dot"
        # The old ad-hoc colored-dot markup must be gone.
        assert "&#9679;" not in tpl, f"{name}: the ad-hoc colored-dot lives markup must be replaced by the primitive"


# -- Survivor outcomes still speak the survivor-state badge vocabulary ----------

def test_user_status_uses_survivor_state_badges():
    tpl = ADMIN_TPLS["users.html"]
    assert "badge-survived" in tpl, "an active player reads as the survivor .badge-survived, not Bootstrap bg-success"
    assert "badge-eliminated" in tpl, "an out player reads as the survivor .badge-eliminated, not Bootstrap bg-danger"


# -- The dark forms for the admin-heavy Bootstrap controls (the A2 trap fix) ----

def test_dark_forms_for_admin_bootstrap_controls():
    rules = _a3_rules()
    # Each control inherits a dark fill from A2.0's --bs-body-bg rebase but ships
    # light/blue component chrome the A2.0/A5 passes never reached.
    for selector in (
        r"body\.game-cfb\s+\.form-control",
        r"body\.game-cfb\s+\.form-select",
        r"body\.game-cfb\s+\.form-check-input",
        r"body\.game-cfb\s+\.form-switch\s+\.form-check-input",
        r"body\.game-cfb\s+\.list-group",
    ):
        assert re.search(selector, rules), f"the A3-admin block must dark-form {selector}"


def test_form_select_chevron_does_not_tile():
    # The bone chevron override must re-state background-repeat/-position/-size or
    # the Bootstrap no-repeat is lost and the chevron tiles across the control.
    rules = _a3_rules()
    m = re.search(r"body\.game-cfb\s+\.form-select\s*\{([^}]*background-image[^}]*)\}", rules)
    assert m, "the form-select chevron override must exist"
    assert "no-repeat" in m.group(1), "the form-select chevron must set background-repeat: no-repeat (or it tiles)"


def test_form_focus_ring_is_crimson_not_gold():
    # The platform .form-control:focus paints a gold ring; on CFB the field focus
    # must be a crimson identity ring (no gold drift inside the room).
    rules = _a3_rules()
    m = re.search(r"body\.game-cfb\s+\.form-control:focus[^{]*\{([^}]*)\}", rules)
    assert m, "the A3-admin block must re-derive the form focus ring for CFB"
    assert "--game-primary" in m.group(1) or "197,5,12" in m.group(1), \
        "the form focus ring must be crimson identity, not the platform gold ring"


# -- The masthead rule is crimson, the dashboard actions de-golded -------------

def test_masthead_rule_is_crimson_not_gold():
    rules = _a3_rules()
    m = re.search(r"\.cfb-admin-masthead\s*\{([^}]*)\}", rules)
    assert m, "the .cfb-admin-masthead must be defined"
    assert "border-bottom" in m.group(1), "the masthead carries a single bottom rule (the room's identity line)"
    assert "--game-primary" in m.group(1), "the masthead rule is CRIMSON (var(--game-primary)), the room's swap for the gold platform rule"


def test_dashboard_action_cards_degold_the_platform_primitive():
    # The dashboard reuses the platform .admin-action / .admin-actions-row card
    # primitive (gold icon + purple primary fill) but scopes those to crimson.
    assert "admin-actions-row" in ADMIN_TPLS["dashboard.html"], "the dashboard leads with the .admin-actions-row primitive"
    rules = _a3_rules()
    assert re.search(r"body\.game-cfb\s+\.admin-action\s+i\s*\{[^}]*--cfb-crimson", rules), \
        "the .admin-action gold icon must be scoped to crimson on CFB"
    assert re.search(r"body\.game-cfb\s+\.admin-action--primary\s*\{[^}]*--game-primary", rules), \
        "the .admin-action--primary purple fill must be scoped to crimson on CFB"


# -- New A3-admin CSS: no side-stripe, no gold (S4 ban + Crimson-Ceremony) ------

def test_a3_admin_css_has_no_side_stripe():
    block = _a3_rules()
    assert not re.search(r"(?<![-\w])border-left\s*:", block), \
        "no border-left side-stripe in the A3-admin block (the platform absolute ban)"
    assert not re.search(r"(?<![-\w])border-right\s*:", block), \
        "no border-right side-stripe in the A3-admin block (the platform absolute ban)"


def test_a3_admin_css_introduces_no_gold():
    block = _a3_rules()
    assert "gold" not in block.lower(), "the A3-admin block must not reference any gold token (Crimson-Ceremony Rule)"
    for gold_hex in ("C9A227", "F2D36B", "8A6A1A", "A88420", "FFF1B8", "B8993E"):
        assert gold_hex.lower() not in block.lower(), \
            f"the A3-admin block must not use the gold hex #{gold_hex} (no gold in the CFB body)"


def test_a3_admin_css_defines_the_named_primitives():
    block = _a3_rules()
    for primitive in (".cfb-admin-masthead", ".cfb-admin-title", ".cfb-admin-sub",
                      ".cfb-admin-chip", ".btn-game-ghost", ".cfb-ledger-total"):
        assert primitive in block, f"the A3-admin block must define {primitive}"


# -- The mutating admin contract is preserved (CSRF + POST + the payment JS) ----

def test_mutating_admin_forms_keep_csrf_and_post():
    # Every state-mutating admin surface keeps a CSRF token; the destructive POST
    # handlers keep method POST (POST-only invariant).
    for name in ("dashboard.html", "create_week.html", "manage_games.html",
                 "manage_teams.html", "mark_results.html", "review_scores.html", "users.html"):
        assert "csrf_token()" in ADMIN_TPLS[name], f"{name}: mutating forms must keep their CSRF token"
    for name in ("manage_games.html", "mark_results.html", "review_scores.html",
                 "users.html", "dashboard.html"):
        assert re.search(r'method="POST"', ADMIN_TPLS[name]), f"{name}: state-mutating forms must POST"


def test_payment_toggle_js_keeps_csrf_header():
    # The payments quick-toggle is a fetch POST; it must keep the X-CSRFToken
    # header, and the JS hook must follow the renamed chip class in lockstep.
    tpl = ADMIN_TPLS["payments.html"]
    assert "X-CSRFToken" in tpl, "the payment toggle fetch must send the X-CSRFToken header"
    assert "payment-toggle" in tpl, "the payment toggle JS hook (.payment-toggle) must be preserved"
    assert "cfb-admin-chip" in tpl, "the payment status badge is the neutral .cfb-admin-chip"
    # The JS targets an explicit cell hook (.cfb-pay-status), not a brittle
    # td:nth-child position, so a future column change can't silently null the
    # badge -- and it scopes past the .cfb-admin-chip Admin tag in the name cell.
    assert "cfb-pay-status" in tpl, "the payment status cell must carry an explicit .cfb-pay-status JS hook"
    assert "nth-child" not in tpl, "the payment JS must not rely on a brittle td:nth-child selector"
