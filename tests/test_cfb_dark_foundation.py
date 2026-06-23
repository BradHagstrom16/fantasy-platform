"""CFB dark-substrate foundation locks (A2.0).

CFB Survivor is a DARK-FIRST room (games/cfb/DESIGN.md): warm crimson-black
midnight is the default body substrate, not a ceremonial accent. The room goes
dark by REBASING the platform's existing structural tokens (--bg-card, --border,
--text-primary, the body background) to a warm midnight ramp under
``body.game-cfb`` -- never by inventing a parallel --game-surface set, and never
globally (the dark doctrine stops at body.game-cfb; top-level DESIGN.md S6
carve-out).

These locks encode that contract via the established CSS-scan idioms
(anchored regex over style.css). Each fails on the pre-A2.0 CSS (which set a
cool navy --game-primary-dark and left the platform light tokens in place) and
passes once the midnight ramp + rebase land. ASCII-only per the CFB phase rule.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static" / "css" / "style.css").read_text()


def _cfb_token_block():
    """Body of the bare ``body.game-cfb { ... }`` token rule (not descendant rules)."""
    m = re.search(r"(?<![-\w.])body\.game-cfb\s*\{([^}]*)\}", CSS)
    assert m, "body.game-cfb token block not found in style.css"
    return m.group(1)


def _root_block():
    """Body of the first ``:root { ... }`` token rule."""
    m = re.search(r":root\s*\{([^}]*)\}", CSS)
    assert m, ":root token block not found in style.css"
    return m.group(1)


def test_cfb_midnight_ramp_tokens_defined():
    """The warm midnight ramp + hairline edge are declared under body.game-cfb."""
    block = _cfb_token_block()
    for tok in ("--cfb-canvas", "--cfb-surface", "--cfb-raised",
                "--cfb-lifted", "--cfb-hairline"):
        assert re.search(rf"{re.escape(tok)}\s*:", block), \
            f"{tok} missing from the body.game-cfb midnight ramp"


def test_cfb_rebases_platform_structural_tokens_to_dark():
    """The room goes dark by rebasing platform tokens, not a parallel set."""
    block = _cfb_token_block()
    rebases = {
        "--bg-page": "--cfb-canvas",
        "--bg-card": "--cfb-surface",
        "--bg-muted": "--cfb-raised",
        "--text-primary": "--cfb-bone",
        "--text-secondary": "--cfb-bone-muted",
        "--border": "--cfb-hairline",
    }
    for tok, target in rebases.items():
        assert re.search(rf"{re.escape(tok)}\s*:\s*var\(\s*{re.escape(target)}", block), \
            f"{tok} not rebased to var({target}) under body.game-cfb"


def test_cfb_game_primary_dark_is_warm_midnight():
    """The hero gradient start is a warm midnight, not the old cool navy-black."""
    block = _cfb_token_block()
    assert "#0f0f1a" not in block.lower(), \
        "stale cool navy --game-primary-dark (#0f0f1a) still present -- would read like the WC room"
    assert re.search(r"--game-primary-dark\s*:\s*#1a0b0d", block, re.I), \
        "--game-primary-dark not set to the warm midnight hero start (#1A0B0D)"


def test_cfb_survivor_state_aligned_to_platform_live_tokens():
    """Survived/lost align to the platform live tokens; loss stays distinct from identity crimson."""
    block = _cfb_token_block()
    assert re.search(r"--cfb-survived\s*:\s*var\(\s*--live-green", block), \
        "--cfb-survived must align to platform --live-green"
    assert re.search(r"--cfb-lost-life\s*:\s*var\(\s*--live-red", block), \
        "--cfb-lost-life must align to platform --live-red (distinct from identity crimson)"


def test_cfb_drops_pure_white_game_accent():
    """--game-accent must not be pure #FFFFFF (top-level DESIGN.md #fff ban)."""
    block = _cfb_token_block()
    assert not re.search(r"--game-accent\s*:\s*#ffffff", block, re.I), \
        "--game-accent must not be pure #FFFFFF on the CFB room"


def test_cfb_text_muted_class_redirected_on_midnight():
    """.text-muted reads --bs-secondary-color; redirect it to bone-muted on midnight."""
    block = _cfb_token_block()
    assert re.search(r"--bs-secondary-color\s*:\s*var\(\s*--cfb-bone-muted", block), \
        ("the global :root --bs-secondary-color redirect resolves --text-secondary "
         "against :root, so a scoped rebase alone won't reach the .text-muted class; "
         "body.game-cfb must redeclare --bs-secondary-color")


def test_cfb_bootstrap_surface_and_accent_rebased():
    """Bootstrap base tokens rebase: dark surface (no white islands) + crimson primary (no off-palette blue)."""
    block = _cfb_token_block()
    assert re.search(r"--bs-body-bg\s*:\s*var\(\s*--cfb-surface", block), \
        ("--bs-body-bg must rebase to the midnight surface so un-styled Bootstrap "
         "components (accordion, list-group) don't punch white holes in the dark room")
    assert re.search(r"--bs-body-color\s*:\s*var\(\s*--cfb-bone", block), \
        "--bs-body-color must rebase to bone so .card body text reads on midnight"
    assert re.search(r"--bs-primary\s*:\s*var\(\s*--cfb-crimson", block), \
        ("--bs-primary must rebase to crimson so .bg-primary surfaces -- the selected "
         "team-pick-card row, count + distribution badges -- read crimson, not blue")


def test_cfb_dark_doctrine_stops_at_body_game_cfb():
    """The dark rebase must stay scoped; the global :root stays light."""
    root = _root_block()
    assert re.search(r"--bg-card\s*:\s*#FFFFFF", root, re.I), \
        "global :root --bg-card must stay light -- the dark doctrine stops at body.game-cfb"
    assert re.search(r"--bg-page\s*:\s*var\(\s*--bone", root), \
        "global :root --bg-page must stay bone -- never globally darken the platform"


def test_cfb_page_hero_overlay_is_crimson_not_gold():
    """The page-hero halftone overlay is recolored crimson on CFB; no gold appears."""
    m = re.search(r"body\.game-cfb\s+\.page-hero::before\s*\{([^}]*)\}", CSS)
    assert m, "CFB page-hero dot-overlay override not found"
    body = m.group(1).replace(" ", "")
    assert "212,168,32" not in body, "CFB hero dot overlay still uses the platform gold"
    assert re.search(r"rgba\(197,5,12", body), "CFB hero dot overlay not recolored to crimson"
