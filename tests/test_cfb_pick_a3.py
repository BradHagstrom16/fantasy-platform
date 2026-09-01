"""CFB pick screen / commitment surface locks (A3).

A2.0 stood up the dark substrate and A2 elevated the hub; A3 brings the pick
flow (games/cfb/templates/cfb/pick.html) -- the commitment surface -- to the
games/cfb/DESIGN.md bar. These locks encode the contracts A3 changes via the
established CSS-scan idioms (anchored regex over style.css + the template). Each
fails on the pre-A3 state and passes once A3 lands:

  - the selected pick is a DECISION (crimson-LIT midnight override of the flat
    .bg-primary paint-fill + an inset crimson perimeter + a small expansion +
    the one sanctioned localized glow on the card), not a flat crimson fill (S4)
  - .ineligible reads cold-and-explained (recede to canvas + the explicit
    .cfb-out-reason chip), never a raw opacity collapse (S4)
  - the spread stays quiet neutral rule-data -- no green/red on every team
    (the Quiet-Spread Rule, S4)
  - the team name is Teko (the decision face, S3)
  - the pick targets are keyboard-operable (role=button + tabindex=0 + Enter/
    Space keydown + aria-pressed + a focus-visible ring on midnight, S6 a11y)
  - the JS hooks the flow depends on are preserved (the platform restyling rule)
  - the hero carries the Survivor register ("Your Card"), not "Make Your Pick"
  - the redundant Available Teams roster rail is gone (single focused column)
  - the named em-dash copy debt is gone (S3 no-em-dash rule)

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
TPL = (ROOT / "games" / "cfb" / "templates" / "cfb" / "pick.html").read_text()

EM_DASH = chr(0x2014)        # em dash (chr() keeps the source ASCII-clean)


def _rule(anchored_selector):
    """Body of a CSS rule, selector anchored at line start (MULTILINE)."""
    m = re.search(anchored_selector + r"\s*\{([^}]*)\}", CSS, re.M)
    assert m, f"CSS rule not found: {anchored_selector}"
    return m.group(1)


# -- Selected pick: a DECISION, not a flat crimson paint-fill (S4) ----------

def test_selected_pick_is_lit_not_a_flat_fill():
    block = _rule(r"^body\.game-cfb \.team-option\.selected")
    # The JS toggles Bootstrap .bg-primary (a solid crimson !important fill); the
    # selected rule must override it with a crimson-LIT rgba midnight, never a
    # solid crimson paint.
    assert re.search(r"(?<![-\w])background:\s*rgba\(197,\s*5,\s*12", block) and "!important" in block, \
        "selected option must override the flat .bg-primary fill with a crimson-lit rgba midnight"
    assert "var(--game-primary)" not in block and "var(--bs-primary)" not in block, \
        "selected option must NOT repaint a solid crimson fill (the flat-fill regression)"


def test_selected_pick_has_perimeter_and_expansion():
    block = _rule(r"^body\.game-cfb \.team-option\.selected")
    assert "inset" in block and "--cfb-crimson" in block, \
        "selected option must carry an inset crimson perimeter ring"
    assert "scale(" in block, \
        "selected option must carry a small expansion (the commitment escalation)"


def test_selected_card_carries_the_one_sanctioned_glow():
    block = _rule(r"^body\.game-cfb \[data-game-card\]\.border-primary")
    assert "box-shadow" in block and "rgba(197,5,12" in block.replace(" ", ""), \
        "the selected matchup card must carry the one sanctioned localized crimson glow"


# -- Ineligible: cold + explained, never an opacity collapse (S4) -----------

def test_ineligible_card_drops_the_opacity_collapse():
    block = _rule(r"^\.team-pick-card\.ineligible")
    assert not re.search(r"(?<![-\w])opacity\s*:", block), \
        "the started-game card must not use a raw opacity collapse (games/cfb/DESIGN.md S4)"


def test_ineligible_option_recedes_to_canvas_not_opacity():
    block = _rule(r"^body\.game-cfb \.team-option\.team-option-out")
    assert not re.search(r"(?<![-\w])opacity\s*:", block), \
        "an ineligible option must not collapse opacity (cold, not a broken ghost)"
    assert re.search(r"(?<![-\w])background:\s*var\(\s*--cfb-canvas", block), \
        "an ineligible option must recede a step deeper (canvas), cold and procedural"


def test_out_reason_chip_is_a_readable_cold_label():
    block = _rule(r"^\.cfb-out-reason")
    assert "Teko" in block and "uppercase" in block, ".cfb-out-reason must be uppercase Teko"
    assert re.search(r"(?<![-\w])color:\s*var\(\s*--cfb-bone-subtle", block), \
        (".cfb-out-reason must use reduced-contrast bone-subtle text (still readable "
         "at >=4.5:1, never a faded ghost)")


def test_pick_explains_the_spread_cap_reason():
    # the custom 16.5+ rule is the reason most worth teaching at the decision.
    # The label lives in the board service (one dict shared by the chips, the
    # legend, and the ledger) and the chip renders it verbatim.
    from games.cfb.services.board import STATE_LABELS
    assert STATE_LABELS['too_favored'] == "16.5+ Fav", \
        "an ineligible favorite must carry the explicit 16.5+ reason, not a vague 'Unavailable'"
    assert 'class="cfb-out-reason">{{ state_labels[state] }}' in TPL, \
        "the out-reason chip must render the shared state label"


# -- Quiet spread: neutral rule-data, not green/red on every team (S4) ------

def test_pick_spread_stays_quiet_neutral():
    # Scope to the .spread-badge class so the lock targets the survivor-state
    # modifier on the spread chip (the actual regression), not the words anywhere.
    assert not re.search(r'spread-badge[^"]*(?:favorable|unfavorable)', TPL), \
        ("the pick screen spread must stay quiet neutral rule-data; painting every "
         "team survived-green / lost-red is scanning drama + survivor-state collision")


# -- Team name: Teko, the decision face (S3) --------------------------------

def test_team_name_is_the_teko_decision_face():
    block = _rule(r"^\.cfb-team-name")
    assert "Teko" in block, "the pick target name must be Teko (the decision face, S3)"
    assert "cfb-team-name" in TPL, "the pick options must render the .cfb-team-name primitive"


# -- Keyboard operability (S6 a11y) -----------------------------------------

def test_pick_targets_are_keyboard_operable():
    assert 'role="button" tabindex="0"' in TPL, \
        "eligible team options must be keyboard-focusable (role=button + tabindex=0)"
    assert "aria-pressed" in TPL, \
        "the selected state must be exposed to assistive tech via aria-pressed"
    assert "addEventListener('keydown'" in TPL, \
        "the pick JS must commit a selection on Enter/Space (keyboard parity with click)"


def test_pick_options_have_a_focus_ring_on_midnight():
    block = _rule(r'^body\.game-cfb \.team-option\[role="button"\]:focus-visible')
    assert "outline" in block, \
        "team options need a visible keyboard focus ring on the midnight substrate"


# -- JS hooks preserved (the platform template-restyling rule) --------------

def test_pick_preserves_js_hooks():
    for hook in ('id="selectedTeamId"', 'id="pickForm"', 'id="pickConfirmBar"',
                 'id="confirmTeamName"', 'id="confirmTeamSpread"', "data-game-card",
                 'data-team-id', 'data-team-name', 'data-team-spread'):
        assert hook in TPL, f"JS hook {hook} must be preserved (do not rename/remove)"
    # the template still server-renders the selected toggle classes the JS owns
    assert "bg-primary text-white selected" in TPL, \
        "the server-rendered selected state must keep the .bg-primary/.text-white/.selected hooks"
    for tok in ("'selected'", "'bg-primary'", "'text-white'", "'border-primary'"):
        assert tok in TPL, f"the JS class toggle {tok} must be preserved"


# -- Survivor voice + single focused column (S3) ----------------------------

def test_pick_hero_carries_survivor_voice():
    assert "<h1>Your Card</h1>" in TPL, \
        "the pick H1 must carry the Survivor register ('Your Card'), not a flat label"
    # Scope to element text (>...<) so a Jinja/HTML comment can't false-fail this;
    # the old flat copy lived in the .lead <p>, so an <h1>-only scope would miss it.
    assert not re.search(r'>\s*Make Your Pick\s*<', TPL), \
        "the flat functional 'Make Your Pick' lead is a S3 voice regression"


def test_pick_is_a_single_focused_column():
    # Scope to element text (the old rail heading was ">Available Teams ({{ N }})<")
    # so a comment can't false-fail and the count suffix can't dodge the lock.
    assert not re.search(r'>\s*Available Teams', TPL), \
        ("the redundant Available Teams roster rail must be gone -- the decision is a "
         "single focused column, not a dashboard/roster-builder split")


# -- No em-dash copy (S3) ---------------------------------------------------

def test_pick_has_no_em_dash_copy():
    assert "&mdash;" not in TPL, "the &mdash; LOCKED badge debt must be gone (S3)"
    assert EM_DASH not in TPL, "no literal em-dash may appear in CFB pick copy (S3)"
