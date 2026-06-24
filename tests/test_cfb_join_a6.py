"""CFB Join / "Take Your Two Lives" locks (A6).

A2.0 stood up the dark substrate; A2 elevated the hub; A3 the pick flow; A4 the
weekly verdict; A5 the player's own card. A6 is the last player screen: the
enrollment threshold (games/cfb/templates/cfb/join.html -- route cfb.join,
/cfb/join, @game_must_be_open('cfb')) brought to the games/cfb/DESIGN.md bar.
This is the marketing/onboarding register: it sells the survivor pool to a
non-member, so it leans editorial/ceremonial, but it stays the dark survivor
room (no WC drift, no gold). These locks encode the contracts A6 changes via the
established CSS-scan idioms (anchored regex over style.css + the template). Each
fails on the pre-A6 state and passes once A6 lands:

  - the H1 carries the Survivor voice ("Take Your Two Lives"), never the flat
    "Join the CFB Survivor Pool" route label (S3)
  - the named em-dash / double-hyphen copy debt is gone: the hero
    "Season &mdash; $25 entry" + bullet "two lives &mdash; survive" + the
    <title> em-dash (S3 no-em-dash / no-double-hyphen rule)
  - the stake is dramatized with the .lives-indicator survivor primitive (two
    held pips), not a fine-print bullet (S4 / S1 "am I alive?")
  - the undesigned "How It Works" <ul> is reframed as an editorial house-rules
    definition list (.cfb-join-rules <dl>), term + plain-language explainer (S3)
  - the entry fee is surfaced as editorial data (.cfb-join-entry, Teko numeral),
    not an em-dash hero clause (S3 "numbers carry the tension")
  - the new A6 CSS introduces no side-stripe (the platform absolute ban) and no
    gold (the Crimson-Ceremony Rule -- gold stays WC's)
  - the enrollment contract is preserved: POST method, CSRF token, .btn-game

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
TPL = (ROOT / "games" / "cfb" / "templates" / "cfb" / "join.html").read_text()
# Jinja {# ... #} comments are not rendered, so the "must NOT contain" content
# locks scan a comment-stripped body (the documented template-source corollary:
# a comment that names the very thing being removed is not a regression).
TPL_BODY = re.sub(r"\{#.*?#\}", "", TPL, flags=re.S)

EM_DASH = chr(0x2014)        # em dash (chr() keeps the source ASCII-clean)

# The A6 CSS region: from its header-banner /* opening to the next section (WC
# overrides). Slicing it lets the side-stripe / no-gold scans target only A6.
_A6 = re.search(r"/\*[^*]*A6 -- Join.*?(?=/\* World Cup overrides \*/)", CSS, re.S)


def _a6_block():
    assert _A6, "the A6 CSS block (header 'A6 -- Join') must exist in style.css"
    return _A6.group(0)


def _a6_rules():
    """The A6 region with /* */ comments stripped -- for property / token scans
    that must not trip on prose in the doctrine comments (e.g. the word 'gold' in
    'no gold (the Crimson-Ceremony Rule)')."""
    return re.sub(r"/\*.*?\*/", "", _a6_block(), flags=re.S)


# -- Survivor voice on the H1 (S3) ------------------------------------------

def test_join_h1_carries_survivor_voice():
    assert re.search(r"<h1[^>]*>\s*Take Your Two Lives\s*</h1>", TPL), \
        "the join H1 element must carry the Survivor register ('Take Your Two Lives'), not a route label"
    # The pre-A6 H1 was `<h1>Join the CFB Survivor Pool</h1>`.
    assert "Join the CFB Survivor Pool" not in TPL_BODY, \
        "the flat 'Join the CFB Survivor Pool' route-label H1 is a S3 voice regression"


# -- No em-dash / double-hyphen copy (S3, the named A6 debt) ------------------

def test_join_has_no_em_dash_or_double_hyphen_copy():
    assert "&mdash;" not in TPL_BODY, \
        "the &mdash; copy debt must be gone (hero 'Season &mdash; $25' + bullet 'two lives &mdash;', S3)"
    assert "&ndash;" not in TPL_BODY, "no &ndash; en-dash entity in CFB join copy (S3)"
    assert EM_DASH not in TPL_BODY, "no literal em-dash may appear in CFB join copy (S3)"
    # The double-hyphen half of the contract: no visible-text '--' anywhere.
    assert re.search(r">\s*[^<]*--[^<]*<", TPL_BODY) is None, \
        "no visible double-hyphen copy ('--') may appear in CFB join copy (S3 no-double-hyphen)"


# -- The stake dramatized via the .lives-indicator primitive (S4 / S1) -------

def test_stake_uses_lives_indicator_primitive():
    assert "cfb-join-stake" in TPL, "the two-lives stake block (.cfb-join-stake) must lead the card"
    assert "lives-indicator" in TPL, \
        "the stake must dramatize the two lives with the .lives-indicator survivor primitive, not a bullet"
    # Two held life pips = the two lives a new entrant is putting on the line.
    assert len(re.findall(r'class="life"', TPL)) >= 2, \
        "the stake must render two held .life pips (the two lives at stake)"


# -- The rules reframed as an editorial definition list (S3) ------------------

def test_rules_are_editorial_definition_list_not_bullets():
    assert re.search(r'<dl[^>]*class="cfb-join-rules"', TPL), \
        "the rules must be an editorial definition list (.cfb-join-rules <dl>), not a fine-print <ul>"
    assert "cfb-join-rule" in TPL, "each rule row is a .cfb-join-rule (term + explainer)"
    # The pre-A6 surface was an `<h3>How It Works</h3>` + `<ul class="mb-4">` bullets.
    assert "How It Works" not in TPL_BODY, \
        "the generic 'How It Works' bullet-list framing is replaced by the editorial house-rules (S3)"
    assert "<ul" not in TPL_BODY, \
        "the undesigned <ul> bullet list must be gone (reframed as the .cfb-join-rules <dl>)"


# -- The entry fee as editorial data, not an em-dash clause (S3) --------------

def test_entry_fee_is_editorial_data():
    assert "cfb-join-entry" in TPL, \
        "the season + fee must read as the quiet editorial .cfb-join-entry line, not an em-dash hero clause"
    assert "cfb_entry_fee" in TPL and "cfb_season_year" in TPL, \
        "the entry line must still surface the season + fee values"


# -- New A6 CSS: no side-stripe, no gold (S4 ban + Crimson-Ceremony Rule) -----

def test_a6_css_has_no_side_stripe():
    block = _a6_rules()
    assert not re.search(r"(?<![-\w])border-left\s*:", block), \
        "no border-left side-stripe in the A6 block (the platform absolute ban); use top/bottom rules"
    assert not re.search(r"(?<![-\w])border-right\s*:", block), \
        "no border-right side-stripe in the A6 block (the platform absolute ban)"


def test_a6_css_introduces_no_gold():
    block = _a6_rules()
    # CFB never introduces gold into its body (the Crimson-Ceremony Rule); gold
    # stays where the platform owns it. Guard the A6 block against the platform
    # gold tokens + the canonical gold hexes.
    assert "gold" not in block.lower(), "the A6 block must not reference any gold token (Crimson-Ceremony Rule)"
    for gold_hex in ("C9A227", "F2D36B", "8A6A1A", "A88420", "FFF1B8", "B8993E"):
        assert gold_hex.lower() not in block.lower(), \
            f"the A6 block must not use the gold hex #{gold_hex} (no gold in the CFB body)"


def test_a6_css_defines_the_named_primitives():
    block = _a6_rules()
    for primitive in (".cfb-join-stake", ".cfb-join-rules", ".cfb-join-rule", ".cfb-join-entry"):
        assert primitive in block, f"the A6 block must define {primitive}"


# -- The enrollment contract is preserved (CSRF + POST + btn-game) ------------

def test_join_form_contract_preserved():
    assert re.search(r'<form[^>]*method="POST"', TPL), "the enrollment form must POST (state-mutating, POST-only)"
    assert "csrf_token()" in TPL, "the enrollment form must keep its CSRF token"
    assert "btn-game" in TPL, "the commit CTA must stay the game-aware .btn-game (crimson on midnight)"
