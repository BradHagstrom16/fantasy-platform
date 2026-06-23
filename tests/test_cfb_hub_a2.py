"""CFB hub / standings per-screen polish locks (A2).

A2.0 stood up the dark substrate; A2 elevates the hub/standings
(games/cfb/templates/cfb/index.html) to the games/cfb/DESIGN.md bar on top of
it. These locks encode the contracts that change in A2 via the established
CSS-scan idioms (anchored regex over style.css + the template). Each fails on
the pre-A2 state and passes once the A2 changes land:

  - the .cfb-eyebrow contextual-label primitive (+ crimson variant) exists
    (games/cfb/DESIGN.md S3); pre-A2 only the .wc-* analog existed
  - the .spread-badge default is neutral midnight, not crimson-tinted
    (the Crimson-Pressure + Quiet-Spread Rules, S4); pre-A2 it was rgba(197,5,12)
  - the current-user standings row drops its side-stripe (the platform absolute
    ban); pre-A2 it carried border-left: 3px
  - the survivor/outcome badges drop literal #fff (the no-#fff rule)
  - the hero carries the Survivor-register H1 + survivor count, not the flat
    functional "CFB Survivor Pool" / "Standings" (S3 voice)
  - the named em-dash copy debt is gone (S3 no-em-dash rule)
  - the .cfb-you-tag is a crimson FILL (bone-on-crimson clears AA where
    crimson-as-small-text would not)
  - the champion ceremony drops the trophy emoji for a restrained eyebrow
    (the Ceremony-by-Reduction Rule, S4)

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
TPL = (ROOT / "games" / "cfb" / "templates" / "cfb" / "index.html").read_text()

EM_DASH = chr(0x2014)        # em dash (chr() keeps the source ASCII-clean)
TROPHY = chr(0x1F3C6)        # trophy emoji


def _rule(anchored_selector):
    """Body of a CSS rule, selector anchored at line start (MULTILINE)."""
    m = re.search(anchored_selector + r"\s*\{([^}]*)\}", CSS, re.M)
    assert m, f"CSS rule not found: {anchored_selector}"
    return m.group(1)


# -- .cfb-eyebrow primitive (S3) ------------------------------------------

def test_cfb_eyebrow_primitive_defined():
    block = _rule(r"^\.cfb-eyebrow")
    assert "Teko" in block, ".cfb-eyebrow must be Teko (the platform label face)"
    assert "uppercase" in block, ".cfb-eyebrow must be uppercase"
    assert re.search(r"(?<![-\w])color:\s*var\(\s*--cfb-bone-muted", block), \
        ".cfb-eyebrow default must be a bone value calibrated for midnight"


def test_cfb_eyebrow_crimson_variant_defined():
    assert re.search(r"^\.cfb-eyebrow-crimson\s*\{[^}]*--cfb-crimson-bright", CSS, re.M), \
        ".cfb-eyebrow-crimson variant must exist (and use the bright crimson)"


# -- .spread-badge neutral default (S4: Quiet-Spread / Crimson-Pressure) ---

def test_cfb_spread_badge_default_is_neutral_not_crimson():
    block = _rule(r"^\.spread-badge")
    assert "197,5,12" not in block.replace(" ", ""), \
        ("the default .spread-badge must NOT be crimson-tinted -- the spread is "
         "data, not identity; crimson stays at the hero anchor + the decision")
    assert re.search(r"background:\s*var\(\s*--cfb-surface", block), \
        ".spread-badge default must sit on a neutral midnight surface (not crimson)"


def test_cfb_spread_badge_keeps_survivor_state_variants():
    assert re.search(r"\.spread-badge\.favorable\s*\{[^}]*--cfb-survived", CSS), \
        ".spread-badge.favorable must keep the survived-green state shift"
    assert re.search(r"\.spread-badge\.unfavorable\s*\{[^}]*--cfb-lost-life", CSS), \
        ".spread-badge.unfavorable must keep the lost-red state shift"


# -- current-user row: no side-stripe (platform absolute ban) --------------

def test_cfb_current_user_row_has_no_side_stripe():
    block = _rule(r"^\.table-cfb \.row-current-user > td")
    assert "border-left" not in block, \
        ("the current-user row must not carry a border-left side-stripe (the "
         "platform absolute ban); a stronger crimson tint + the .cfb-you-tag "
         "carry the emphasis instead")
    assert "197,5,12" in block.replace(" ", ""), \
        "the current-user row keeps the sanctioned crimson tint"


# -- outcome badges: no literal #fff (no-#fff rule) ------------------------

def test_cfb_outcome_badges_drop_pure_white():
    for sel in (r"^\.badge-survived", r"^\.badge-lost-life", r"^\.badge-eliminated"):
        block = _rule(sel)
        assert not re.search(r"(?<![-\w])color:\s*#fff", block, re.I), \
            f"{sel.lstrip('^')} must not use literal #fff (the no-#fff rule)"


def test_cfb_survived_badge_is_dark_on_green():
    """White-on-survived-green fails AA; the chip must use dark ink on the bright state color."""
    block = _rule(r"^\.badge-survived")
    assert re.search(r"(?<![-\w])color:\s*var\(\s*--cfb-canvas", block), \
        ".badge-survived must use dark canvas ink (white-on-green fails AA)"


# -- .cfb-you-tag is a crimson FILL, not crimson text ----------------------

def test_cfb_you_tag_is_crimson_fill_with_bone_text():
    block = _rule(r"^\.cfb-you-tag")
    assert re.search(r"background:\s*var\(\s*--cfb-crimson", block), \
        (".cfb-you-tag must be a crimson FILL -- bone-on-crimson clears AA where "
         "crimson-as-small-text (4.3:1) would not")
    assert re.search(r"(?<![-\w])color:\s*var\(\s*--cfb-bone", block), \
        ".cfb-you-tag text must be bone on the crimson fill"


# -- hero: Survivor-register voice + survivor count (S3) --------------------

def test_cfb_hub_hero_drops_flat_functional_voice():
    assert "<h1>CFB Survivor Pool</h1>" not in TPL, \
        "the flat functional H1 'CFB Survivor Pool' is a S3 voice regression"
    assert not re.search(r'<p class="lead">\s*Standings\s*</p>', TPL), \
        "the flat 'Standings' lead must be replaced by the survivor count"


def test_cfb_hub_hero_carries_survivor_count():
    assert "cfb-hero" in TPL and "cfb-eyebrow" in TPL, \
        "the hero must carry the .cfb-hero scope + a .cfb-eyebrow"
    assert "cfb-hero-field" in TPL and "cfb-count" in TPL, \
        "the hero must answer 'who is left standing?' with the survivor count"
    assert "still standing" in TPL, \
        "the survivor count must read 'N still standing'"


# -- weekly call leads with survivor status (S4 .cfb-pick-cta) -------------

def test_cfb_weekly_call_leads_with_status_row():
    assert "cfb-status-row" in TPL, \
        "the weekly call must lead with the survivor status row (am I alive)"
    # status row must precede the Make-Your-Pick action in the card
    assert TPL.index("cfb-status-row") < TPL.index("Make Your Pick"), \
        "survivor status must come before the pick decision in the weekly call"


# -- named copy debt: no em-dash (S3 no-em-dash rule) ----------------------

def test_cfb_hub_has_no_em_dash_copy():
    assert "&mdash;" not in TPL, "the &mdash; tiebreaker debt must be gone (S3)"
    assert EM_DASH not in TPL, "no literal em-dash may appear in CFB copy (S3)"


# -- champion ceremony by reduction (S4) -----------------------------------

def test_cfb_champion_drops_trophy_emoji_for_eyebrow():
    assert TROPHY not in TPL, \
        "the trophy emoji is trophy-overload; ceremony comes from reduction (S4)"
    assert "One Remains" in TPL, \
        "the champion ceremony leads with the restrained 'One Remains' eyebrow"


def test_cfb_champion_name_not_pure_white():
    block = _rule(r"^\.championship-hero \.champion-name")
    assert not re.search(r"(?<![-\w])color:\s*#fff", block, re.I), \
        ".champion-name must not use literal #fff (the no-#fff rule)"
