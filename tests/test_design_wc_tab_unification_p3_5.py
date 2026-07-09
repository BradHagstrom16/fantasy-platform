"""WC Tab Unification — Phase 3.5 (audit-miss cleanup) regression locks.

P3.5 migrated the two `.card.wc-card` consumers that didn't appear in the
original P2 audit grid:

- `team_detail.html:84` — single fixture-list wrapper (strip `wc-card`,
  keep `wc-card-flush`).
- `rules.html` x 7 wrappers at lines 29, 41, 114, 161, 192, 244, 255 (strip
  `wc-card`).

With both templates off `.card.wc-card`, the only remaining DOM consumer is
the `_home_post.html` champion banner — which contains no `<table>` and no
direct-child `<ul>/<ol>/<h2..h6>` matched by the S4.3.1 PI-1 cluster, and
whose `<p class="champion-retrospect">` is independently colored by the
scoped rule at `style.css:7068`. Two CSS rule clusters retired in lockstep
because their last DOM consumer disappeared:

- `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` (P2 S2.6 PI-1)
  + its surgical exclusion `.card.wc-card .table > tbody > tr > td
  .text-muted, .card.wc-card .table > tbody > tr > td.text-muted` (chained
  dependency).
- The S4.3.1 PI-1 direct-prose cluster
  `.card.wc-card > .card-body > p|ul|ol|li|h2|h3|h4|h5|h6 { color:
  var(--text-on-dark); }`.

These tests pin the migration:

- PI-1: `team_detail.html` has zero `.card.wc-card` usage.
- PI-2: `rules.html` has zero `.card.wc-card` usage.
- PI-3: `.card.wc-card .table { --bs-table-bg ... }` rule absent.
- PI-4: `.card.wc-card .table > tbody > tr > td .text-muted` exclusion absent.
- PI-5: `.card.wc-card > .card-body > p|ul|ol|li|h2..h6` cluster absent.

Regex idioms inherit P3's hardening:
- Template scans use order-independent class lookaheads with the
  `(?![\\w-])` negative-lookahead trailing edge so `wc-card-flush` isn't
  caught (P3 PI-1 idiom).
- CSS absence-checks use `^...` anchoring with `re.MULTILINE` (P3 CR R3-R4
  precedent) so substring matches inside larger rules can't false-pass.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TPL_DIR = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup'

CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: team_detail.html has zero .card.wc-card usage.
# ---------------------------------------------------------------------------

def test_team_detail_template_has_no_card_wc_card():
    """`team_detail.html` no longer carries `class="card … wc-card …"` on
    any wrapper. The `wc-card-flush` zero-padding utility survives — only
    the standalone `wc-card` token is forbidden. Mirrors P3's
    `test_picks_template_has_no_card_wc_card` idiom: order-independent
    lookaheads + `(?![\\w-])` trailing edge so `wc-card-flush` isn't caught.
    """
    team_detail = TPL_DIR / 'team_detail.html'
    pattern = re.compile(r'class="(?=[^"]*\bcard\b)(?=[^"]*\bwc-card(?![\w-]))[^"]*"')
    text = team_detail.read_text()
    occurrences = []
    for m in pattern.finditer(text):
        line_num = text.count('\n', 0, m.start()) + 1
        occurrences.append((line_num, m.group(0)))

    assert occurrences == [], (
        f'Expected zero `.card.wc-card` usages in team_detail.html post-P3.5; '
        f'found {len(occurrences)}: {occurrences!r}.'
    )


# ---------------------------------------------------------------------------
# PI-2: rules.html has zero .card.wc-card usage.
# ---------------------------------------------------------------------------

def test_rules_template_has_no_card_wc_card():
    """`rules.html` no longer carries `class="card … wc-card …"` on any of
    its 7 section wrappers (lines 29, 41, 114, 161, 192, 244, 255 pre-P3.5).
    Same regex idiom as PI-1 — order-independent class tokens with the
    `(?![\\w-])` trailing edge."""
    rules = TPL_DIR / 'rules.html'
    pattern = re.compile(r'class="(?=[^"]*\bcard\b)(?=[^"]*\bwc-card(?![\w-]))[^"]*"')
    text = rules.read_text()
    occurrences = []
    for m in pattern.finditer(text):
        line_num = text.count('\n', 0, m.start()) + 1
        occurrences.append((line_num, m.group(0)))

    assert occurrences == [], (
        f'Expected zero `.card.wc-card` usages in rules.html post-P3.5; '
        f'found {len(occurrences)}: {occurrences!r}.'
    )


# ---------------------------------------------------------------------------
# PI-3: .card.wc-card .table { --bs-table-bg ... } mask retired.
# ---------------------------------------------------------------------------

def test_card_wc_card_table_bs_table_bg_mask_rule_retired():
    """The P2 S2.6 PI-1 white-td invariant lock retired in P3.5 — its only
    DOM consumers were the rules.html / team_detail.html / picks.html
    tables, all migrated off `.card.wc-card`. The champion banner has no
    `<table>`, so the lock has zero remaining consumer.

    Anchored regex (start-of-line + `re.MULTILINE`, P3 CR R3-R4 idiom) so a
    substring match inside another rule (e.g. a future
    `.foo .card.wc-card .table { ... }` descendant rule) can't false-pass.
    The S2.6 PI-1 lockstep test in `test_design_p2_s2_6.py` carries the
    same invariant — this PI is the P3.5-side regression lock.
    """
    pattern = re.compile(
        r'^\.card\.wc-card\s+\.table\s*\{',
        re.MULTILINE,
    )
    assert pattern.search(CSS) is None, (
        '`.card.wc-card .table { --bs-table-bg: var(--bg-card); }` '
        're-appeared in style.css. P3.5 retired it because every DOM '
        'consumer migrated off the dark substrate; restoring it without '
        'restoring a consumer leaves an orphan rule the next phase has to '
        'remove again.'
    )


# ---------------------------------------------------------------------------
# PI-4: .card.wc-card .table > tbody > tr > td .text-muted exclusion retired.
# ---------------------------------------------------------------------------

def test_card_wc_card_table_text_muted_exclusion_retired():
    """The surgical exclusion that paired with the PI-3 rule retired in
    lockstep — without the PI-3 mask above it, the exclusion had no
    functional carrier. Anchored absence-check at start-of-line."""
    forbidden = [
        r'^\.card\.wc-card\s+\.table\s*>\s*tbody\s*>\s*tr\s*>\s*td\s+\.text-muted\s*[,{]',
        r'^\.card\.wc-card\s+\.table\s*>\s*tbody\s*>\s*tr\s*>\s*td\.text-muted\s*[,{]',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS, re.MULTILINE) is None, (
            f'P3.5-retired surgical exclusion re-appeared: `{pattern}`. The '
            f'exclusion was chained on the PI-3 mask above it; restoring it '
            f'in isolation leaves a vestigial selector with no functional '
            f'consumer.'
        )


# ---------------------------------------------------------------------------
# PI-5: .card.wc-card > .card-body > prose cluster retired.
# ---------------------------------------------------------------------------

def test_card_wc_card_card_body_direct_prose_cluster_retired():
    """The S4.3.1 PI-1 10-selector direct-prose lift retired in P3.5. Its
    sole rich-prose consumer was rules.html (which stacks raw <p>/<ul>/<h*>
    inside `.card-body`); the post-P3.5 champion banner has no direct-child
    `<ul>/<ol>/<h2..h6>`, and its only direct `<p class="champion-retrospect">`
    is independently colored at `style.css:7068`.

    Loops over each forbidden selector head individually so a partial
    restore (any one of the 10) is also caught. Anchored at start-of-line
    per the P3 CR R3-R4 idiom.
    """
    forbidden = [
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*p\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*ul\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*ol\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*ul\s*>\s*li\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*ol\s*>\s*li\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*h2\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*h3\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*h4\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*h5\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*h6\s*[,{]',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS, re.MULTILINE) is None, (
            f'S4.3.1 PI-1 direct-prose cluster selector re-appeared: '
            f'`{pattern}`. P3.5 retired the 10-selector cluster when '
            f'rules.html migrated off `.card.wc-card`; restoring any one '
            f'selector without a consumer wrapper leaves an orphan that '
            f'P5 has to remove again.'
        )
