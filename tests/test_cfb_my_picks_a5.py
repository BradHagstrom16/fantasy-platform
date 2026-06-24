"""CFB My Picks / "Your Card" locks (A5).

A2.0 stood up the dark substrate; A2 elevated the hub; A3 the pick flow; A4 the
weekly verdict. A5 brings the player's own season ledger
(games/cfb/templates/cfb/my_picks.html -- route cfb.my_picks, /cfb/my-picks) to
the games/cfb/DESIGN.md bar. These locks encode the contracts A5 changes via the
established CSS-scan idioms (anchored regex over style.css + the template). Each
fails on the pre-A5 state and passes once A5 lands:

  - the banned four-up hero-metric stat grid (Total / Correct / Incorrect /
    Spread as identical .stat-block cards, a platform absolute ban) is gone,
    replaced by ONE composed survivor-status lead (.cfb-season-lead) + the A4
    .cfb-week-summary record line (S2 / top-level S6)
  - the H1 carries the Survivor voice ("Your Card"), never the flat
    "My Picks & Strategy" route label (S3)
  - the Bootstrap conference accordion is dark-tuned OFF its white/blue active
    island (the named A2 debt): the --bs-accordion-active-bg/-color/-icon are
    rebased to the midnight ramp + crimson, the active header carries a crimson
    BOTTOM rule (never a side-stripe), and EVERY JS hook is preserved (S4)
  - survivor-state stays on-palette + by structure: no off-palette Bootstrap
    chips (bg-success team chips = survivor-green-as-decoration; bg-primary count
    = crimson-as-data; bg-warning amber = off the survivor-state palette); the
    pending result is the A4 hollow .badge-pending "TBD" (S2 / S5)
  - the survivor-status lead carries an outcome top rule (never a side-stripe)
    and surfaces lives in the lead, not a buried micro-card (S1 / S5)
  - the named em-dash / double-hyphen copy debt is gone (S3 no-em-dash rule)

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
TPL = (ROOT / "games" / "cfb" / "templates" / "cfb" / "my_picks.html").read_text()
# Jinja {# ... #} comments are not rendered, so the "must NOT contain" content
# locks scan a comment-stripped body (the documented template-source corollary:
# a comment that names the very thing being removed is not a regression).
TPL_BODY = re.sub(r"\{#.*?#\}", "", TPL, flags=re.S)

EM_DASH = chr(0x2014)        # em dash (chr() keeps the source ASCII-clean)


def _rule(anchored_selector):
    """Body of a CSS rule, selector anchored at line start (MULTILINE)."""
    m = re.search(anchored_selector + r"\s*\{([^}]*)\}", CSS, re.M)
    assert m, f"CSS rule not found: {anchored_selector}"
    return m.group(1)


# -- The banned four-up hero-metric stat grid is gone (S2 / top-level S6) -----

def test_no_four_up_stat_grid():
    assert "stat-block" not in TPL, \
        "the four-up Total/Correct/Incorrect/Spread .stat-block grid (the hero-metric / " \
        "identical-card-grid template) is a platform absolute ban and must be gone"
    assert "cfb-season-lead" in TPL, \
        "the season standing must lead with the composed .cfb-season-lead (am-I-alive answer, S1)"
    assert "cfb-week-summary" in TPL, \
        "the season record must render the A4 editorial .cfb-week-summary line, not a stat grid"


# -- Survivor voice on the H1 (S3) ------------------------------------------

def test_my_picks_h1_carries_survivor_voice():
    assert re.search(r"<h1[^>]*>\s*Your Card\s*</h1>", TPL), \
        "the my_picks H1 element must carry the Survivor register ('Your Card'), not a route label"
    # The pre-A5 H1 was `<h1>My Picks & Strategy</h1>` with a "Track your season journey" lead.
    assert "My Picks & Strategy" not in TPL_BODY, \
        "the flat 'My Picks & Strategy' route-label H1 is a S3 voice regression"
    assert "Track your season journey" not in TPL_BODY, \
        "the flat 'Track your season journey' lead is a S3 voice regression"


# -- The accordion dark-tuned off the Bootstrap white/blue island (named A2 debt) --

def test_accordion_is_dark_tuned_off_the_bootstrap_blue():
    block = _rule(r"^body\.game-cfb \.accordion")
    # The Bootstrap default active surface is a pale-blue subtle + dark-blue
    # emphasis text + a blue chevron; A2.0's --bs-primary rebase does NOT reach
    # them. A5 rebases the accordion vars directly to the midnight ramp.
    assert "--bs-accordion-active-bg: var(--cfb-raised)" in block, \
        "the active accordion surface must be a raised midnight, not the Bootstrap pale-blue island"
    assert "--bs-accordion-active-color: var(--cfb-white)" in block, \
        "the active accordion text must be bone-white, not Bootstrap dark-blue emphasis"
    assert "--bs-accordion-btn-bg: var(--cfb-surface)" in block, \
        "the resting accordion surface must sit on the midnight surface"
    # The active chevron must carry the crimson identity accent, not the blue default.
    assert "--bs-accordion-btn-active-icon" in block and "E8282F" in block, \
        "the expanded chevron must be recolored to crimson-bright (the blue default is invisible/off-palette)"


def test_accordion_active_is_a_bottom_rule_not_a_side_stripe():
    block = _rule(r"^body\.game-cfb \.accordion-button:not\(\.collapsed\)")
    # Active state marked by a crimson BOTTOM rule (inset 0 -2px 0), never a
    # border-left/right side-stripe (the platform absolute ban).
    assert re.search(r"box-shadow:\s*inset 0 -2px 0 var\(--game-primary\)", block), \
        "the expanded header must carry a crimson bottom rule (inset 0 -2px 0 --game-primary)"
    assert not re.search(r"(?<![-\w])border-left\s*:", block), "no border-left side-stripe on the active header"
    assert not re.search(r"(?<![-\w])border-right\s*:", block), "no border-right side-stripe on the active header"


def test_accordion_js_hooks_preserved():
    # The platform template-restyling rule: add classes alongside JS-critical
    # ones, never rename/remove. Every Bootstrap collapse hook must survive.
    for hook in (
        'id="conferenceAccordion"',
        'data-bs-toggle="collapse"',
        'data-bs-target="#confCollapse{{ loop.index }}"',
        'id="confCollapse{{ loop.index }}"',
        'data-bs-parent="#conferenceAccordion"',
        'class="accordion-collapse collapse"',
    ):
        assert hook in TPL, f"accordion JS hook must be preserved verbatim: {hook}"


# -- Survivor-state stays on-palette + by structure (S2 / S5) ----------------

def test_no_off_palette_or_crimson_or_green_decoration_chips():
    # Pre-A5: bg-success on the available-team chips (survivor-green = "alive",
    # never "a team you could pick"); bg-primary on the conference COUNT badges
    # (crimson is identity, not data); bg-warning amber on the coverage card
    # (off the CFB survivor-state palette entirely); bg-light islands; the
    # contextual table-success/table-danger full-row tints.
    for offending in (
        "bg-success", "bg-primary", "bg-secondary", "bg-warning", "bg-danger",
        "bg-light", "bg-info", "table-success", "table-danger", "text-dark",
        "text-success", "text-warning", "text-danger",
    ):
        assert offending not in TPL_BODY, \
            f"'{offending}' is off the CFB survivor-state palette / uses crimson|green as decoration (S2)"
    assert "cfb-team-chip" in TPL, "the pickable pool must use the neutral .cfb-team-chip, not green bg-success"
    assert "cfb-conf-count" in TPL, "the conference count must be the neutral bone .cfb-conf-count, not crimson bg-primary"


def test_pending_result_is_the_hollow_tbd_chip():
    assert ">TBD<" in TPL, "a pending pick must carry the readable A4 .badge-pending 'TBD' label"
    assert "badge-pending" in TPL, "the pending result reuses the A4 hollow .badge-pending chip (structure, not hue)"
    # The pre-A5 pending marker was `<span class="badge bg-secondary">--</span>`.
    assert not re.search(r">\s*--\s*<", TPL_BODY), \
        "no double-hyphen placeholder ('--') as displayed content (S3 no-double-hyphen)"


# -- The survivor-status lead: outcome top rule, never a side-stripe (S5) -----

def test_season_lead_uses_outcome_top_rule_not_a_side_stripe():
    block = _rule(r"^\.cfb-season-lead")
    assert re.search(r"border-top:\s*2px solid", block), \
        "the season lead is marked by an outcome-colored TOP rule (the A4 .cfb-verdict pattern)"
    assert not re.search(r"(?<![-\w])border-left\s*:", block), "no border-left side-stripe on the season lead (S4 ban)"
    assert not re.search(r"(?<![-\w])border-right\s*:", block), "no border-right side-stripe on the season lead"
    # The three survivor-health variants recolor only the top rule.
    for variant in ("is-survived", "is-pending", "is-lost"):
        assert f".cfb-season-lead.{variant}" in CSS, \
            f"the season lead must carry the {variant} survivor-health top-rule variant"


def test_lives_surfaced_in_the_lead_not_buried():
    # The "am I alive?" answer (DESIGN.md S1) leads the page; the pre-A5
    # "Lives Remaining" micro-card at the bottom is folded into the lead.
    assert "cfb-season-lead-aside" in TPL and "lives-indicator" in TPL, \
        "the lives indicator must surface in the season lead aside (not a buried bottom card)"
    assert "Lives Remaining" not in TPL_BODY, \
        "the standalone 'Lives Remaining' micro-card is folded into the lead"


# -- No em-dash / double-hyphen copy (S3) -----------------------------------

def test_my_picks_has_no_em_dash_or_double_hyphen_copy():
    assert "&mdash;" not in TPL_BODY, "the &mdash; copy debt must be gone (S3)"
    assert EM_DASH not in TPL_BODY, "no literal em-dash may appear in CFB my_picks copy (S3)"
    # The double-hyphen half of the contract: no visible-text '--' anywhere (broader
    # than the pending-placeholder check, which only catches '--' as a tag's sole content).
    assert re.search(r">\s*[^<]*--[^<]*<", TPL_BODY) is None, \
        "no visible double-hyphen copy ('--') may appear in CFB my_picks copy (S3 no-double-hyphen)"
