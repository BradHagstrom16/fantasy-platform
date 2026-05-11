"""P4 S4.3.1 regression locks — join.html + rules.html first iteration.

Layer A (per plan §1.3) source-pattern locks for the five Priority Issues
(PI-1 through PI-5) plus inline-style retirements that landed in S4.3.1.

Iteration map:

- PI-1 (`$impeccable harden`). `.card.wc-card .card-body` direct-prose
  rendered Bootstrap-default `rgb(33,37,41)` on the `rgba(0,17,46,.8)`
  navy substrate of rules.html's six stacked wc-cards — measured at
  ~1.4:1, well below AA. Scoped lift via direct-child selectors
  (`> .card-body > p / ul / ol / li / h2 / h3 / h4 / h5 / h6`) to
  `var(--text-on-dark)` (bone, ~9.5:1) — without leaking into nested
  light-substrate descendants like `.tier-mobile-card`.

- PI-2 (`$impeccable harden`). `.wc-multiplier-chip` rendered bone-on-
  bone-alpha by default; on rules.html the chip lives in white `<td>`
  cells (`.table-worldcup` cells, masked white via the S2.6 PI-1
  `--bs-table-bg` lock) and inside `.tier-mobile-card` (lavender bg) —
  both light substrates where bone is invisible. Added two scoped
  overrides matching the S4.2.2 PI-A1 pattern: ink-on-purple-tint for
  `.table-worldcup .wc-multiplier-chip` and `.tier-mobile-card
  .wc-multiplier-chip`. Bundled: `.tier-mobile-card .text-muted` and
  `.tier-teams-list` lifted off `--text-muted` (~1:1 on lavender) to
  `--text-secondary` (~5.5:1).

- PI-3 (atomic — voice + outline + link). join.html template rewrite:
  hero eyebrow added (`2026 World Cup · Membership`), H1 retuned to
  Tribune voice ("Sign the ledger."), `&middot;` separator retired,
  bullet list distilled into editorial paragraphs, H3 → H2 +
  `.wc-section-heading` class promoted to close the H1 → H3 outline
  skip, CTA verb shifted from "Join the Pool" to "Take your seat"
  matching the picks.html "Amend the Oath" Tribune register, and the
  bottom rules-link restructured from `<a class="text-muted small">`
  (12.48px, bone-on-bone via Bootstrap muted-on-dark-theme cascade,
  sub-44 height) to `.join-rules-link` (16px Newsreader, ink-on-bone
  ~6.2:1, 44+px tap floor, canonical `:focus-visible` gold-light ring).

- PI-4 (atomic — rules.html heading outline + retirements). H3 → H2
  on the seven section heads (`.wc-section-heading` class); H5 → H3 on
  the Group Stage Scoring sub-heads (`.wc-subsection-heading`); the
  seven inline `style="font-family:'Teko'..."` declarations on h3 +
  the inline 1.1rem Teko style on the mobile tier-card name retire
  in favor of class-driven primitives. The two Champion-row inline
  `style="background:rgba(0,40,104,.04);..."` literal-navy tints
  (S4.2.1 PI-4 retired this pattern) swap to `.wc-champion-row` +
  scoped `> td` rule (the tr-level bg is masked by Bootstrap's
  opaque `--bs-table-bg` on each cell; the td-level rule wins).

- PI-5 (`$impeccable harden`). `.form-label` and `.form-text` token
  hygiene: site-wide they paint `var(--text-muted)` (#8A849B, ~3.6:1
  on white card — sub-AA per `project_text_muted_aa_on_bone.md`).
  Scoped lift to `var(--text-secondary)` (~7.2:1) inside `body.game-
  worldcup` mirroring S3.2.1 PI-2's `body.auth-page` scope. Site-wide
  retire of the underlying token is routed cross-phase to S6.1.
"""
from pathlib import Path

REPO = Path(__file__).parent.parent
CSS = REPO / 'static' / 'css' / 'style.css'
JOIN = REPO / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'join.html'
RULES = REPO / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'rules.html'


# ---------- PI-1: .card.wc-card .card-body prose color lift ----------

def test_pi1_card_wc_card_card_body_prose_lifted_to_bone():
    """The S4.3.1 direct-child rule lifts p/ul/ol/li/h2..h6 to --text-on-dark."""
    css = CSS.read_text()
    assert '.card.wc-card > .card-body > p,' in css
    assert '.card.wc-card > .card-body > ul,' in css
    assert '.card.wc-card > .card-body > h2,' in css
    assert '.card.wc-card > .card-body > h5,' in css
    # Must use --text-on-dark (bone), not raw color literal.
    block_start = css.index('.card.wc-card > .card-body > p,')
    block_end = css.index('}', block_start)
    block = css[block_start:block_end]
    assert 'color: var(--text-on-dark)' in block, \
        "Prose color must lift to --text-on-dark (bone) — not a raw value"


def test_pi1_direct_child_selector_excludes_nested_light_substrate():
    """The `>` direct-child selector is load-bearing — leaking into nested
    light-substrate descendants (tier-mobile-card lavender, table cells
    white-masked) would re-introduce bone-on-light contrast bugs."""
    css = CSS.read_text()
    # The bad form would be `.card.wc-card .card-body p` (descendant). The
    # good form is `.card.wc-card > .card-body > p` (two `>` separators).
    assert '.card.wc-card > .card-body > p,' in css
    # And the descendant form must NOT appear as a sibling rule overriding the
    # direct-child lift back to a non-bone color.
    bad_form = '.card.wc-card .card-body p {'
    assert bad_form not in css, \
        f"Descendant-selector form `{bad_form}` would over-broadcast the lift"


# ---------- PI-2: light-substrate multiplier chip + tier-mobile-card lifts ----------

def test_pi2_table_worldcup_multiplier_chip_inked_on_light():
    """Rules-page tables: chip lifts to ink on a council-purple tint.

    PR #15 CR R2 — scoped to `.card.wc-card:not(.player-picks-desktop)
    .table-worldcup` so the `.player-picks-desktop` dark-navy surface
    (picks readonly + player_detail) keeps the default bone-on-bone-alpha
    chip rule and stays visible on its transparent-td substrate."""
    css = CSS.read_text()
    selector = '.card.wc-card:not(.player-picks-desktop) .table-worldcup .wc-multiplier-chip {'
    assert selector in css, f'expected scoped selector {selector!r} in style.css'
    # The unscoped form must NOT exist — that's the bug R2 caught.
    assert '\n.table-worldcup .wc-multiplier-chip {' not in css, \
        'unscoped .table-worldcup .wc-multiplier-chip retint would re-introduce the dark-on-dark leak'
    block_start = css.index(selector)
    block_end = css.index('}', block_start)
    block = css[block_start:block_end]
    assert 'color: var(--text-primary)' in block
    assert 'rgba(58, 29, 114' in block, "Council-purple tint must drive the bg"


def test_pi2_tier_mobile_card_multiplier_chip_inked_on_light():
    """Mobile tier card: chip lifts to ink on a council-purple tint."""
    css = CSS.read_text()
    assert '.tier-mobile-card .wc-multiplier-chip {' in css


def test_pi2_tier_mobile_card_text_muted_lifted():
    """The .tier-mobile-card .text-muted descendant gets ink, not Bootstrap muted."""
    css = CSS.read_text()
    assert '.tier-mobile-card .text-muted {' in css
    # Must use --text-secondary (the canonical bone-fail replacement).
    block_start = css.index('.tier-mobile-card .text-muted {')
    block_end = css.index('}', block_start)
    block = css[block_start:block_end]
    assert 'var(--text-secondary)' in block


def test_pi2_tier_teams_list_lifted_off_text_muted():
    """tier-teams-list now reads --text-secondary, not --text-muted."""
    css = CSS.read_text()
    block_start = css.index('.tier-mobile-card .tier-teams-list')
    block_end = css.index('}', block_start)
    block = css[block_start:block_end]
    assert 'var(--text-secondary)' in block
    assert 'var(--text-muted)' not in block, \
        "tier-teams-list must lift off --text-muted; that token fails AA on bone"


def test_pi2_mobile_tier_card_inline_styles_retired():
    """The two inline-style spans on the mobile tier-card name + picks-count
    swap to class-driven primitives (.tier-mobile-card-name / -picks)."""
    src = RULES.read_text()
    # The inline-Teko style is gone from the mobile tier-card name.
    assert "font-family:'Teko',sans-serif; font-size:1.1rem" not in src
    # And the inline .8rem font-size on the picks-count is gone.
    assert 'style="font-size:.8rem;"' not in src
    # Both classes are now consumed by the mobile tier-card markup.
    assert 'class="tier-mobile-card-name"' in src
    assert 'class="tier-mobile-card-picks"' in src


def test_pi2_mobile_tier_card_primitive_classes_defined_in_css():
    """The two new mobile-tier classes must be declared in style.css."""
    css = CSS.read_text()
    assert '.tier-mobile-card-name {' in css
    assert '.tier-mobile-card-picks {' in css


# ---------- PI-3: join.html voice + outline + link ----------

def test_pi3_join_hero_carries_eyebrow_and_tribune_voice_h1():
    """Hero opens with eyebrow + Tribune H1 + editorial subhead."""
    src = JOIN.read_text()
    assert '<span class="wc-eyebrow">2026 World Cup' in src
    assert '<h1>Sign the ledger' in src
    # The lead drops the &middot; separator + the entry-fee metadata.
    assert '&middot;' not in src, "Hero subhead must not carry the &middot; metadata separator"


def test_pi3_join_card_heading_promoted_h3_to_h2():
    """Card section heading is H2 with .wc-section-heading class (was H3 + inline-Teko)."""
    src = JOIN.read_text()
    assert '<h2 class="wc-section-heading">How the pool works' in src
    # Inline style on heading is retired.
    assert "style=\"font-family:'Teko'" not in src, \
        "Inline-Teko declarations must retire in favor of .wc-section-heading"


def test_pi3_join_cta_carries_tribune_verb():
    """CTA shifted from 'Join the Pool' (generic SaaS funnel) to a Tribune verb."""
    src = JOIN.read_text()
    assert 'Take your seat' in src
    assert 'Join the Pool' not in src, "Generic SaaS-funnel CTA verb retired"


def test_pi3_join_rules_link_uses_dedicated_class_not_text_muted_small():
    """The bottom 'Read the house rules' link uses .join-rules-link, not .text-muted small."""
    src = JOIN.read_text()
    assert 'class="join-rules-link"' in src
    # The pre-S4.3.1 form was <a class="text-muted small">; must not return.
    assert 'class="text-muted small"' not in src
    # New copy in Tribune register.
    assert 'Read the house rules' in src


def test_pi3_join_rules_link_class_defined_with_44_floor_and_focus_ring():
    """`.join-rules-link` enforces tap floor + canonical CCC focus ring."""
    css = CSS.read_text()
    assert '.join-rules-link {' in css
    block_start = css.index('.join-rules-link {')
    block_end = css.index('.join-rules-link:hover', block_start)
    block = css[block_start:block_end]
    assert 'min-height: 44px' in block, "Must lock the 44px tap floor"
    assert "font-family: 'Newsreader'" in block, "Body font, not Teko"
    assert '1rem' in block, "Must clear the 16px body-text floor"
    # Focus ring uses --gold-light per S2.1.2 / S3.2.1 / S4.2.1 lock.
    focus_start = css.index('.join-rules-link:focus-visible')
    focus_end = css.index('}', focus_start)
    focus_block = css[focus_start:focus_end]
    assert 'var(--gold-light)' in focus_block
    assert 'outline-offset: 2px' in focus_block


def test_pi3_join_bulleted_explainer_collapsed_to_editorial_prose():
    """The four-bullet 'How It Works' list distilled into editorial paragraphs."""
    src = JOIN.read_text()
    # The pre-S4.3.1 bullet list (`Pick 9 national teams ... before kickoff`)
    # collapses into a single paragraph mention.
    assert '<li>Pick <strong>9 national teams</strong>' not in src, \
        "Bulleted feature recital retired in favor of editorial prose"
    # Tribune phrasing for the same facts must remain (truth preservation).
    assert 'nine national teams' in src.lower()
    assert 'first kickoff' in src.lower() or 'first whistle' in src.lower()


def test_pi3_join_heading_outline_has_no_skip():
    """Join page outline: H1 → H2 only, no H3 skip."""
    src = JOIN.read_text()
    import re
    headings = re.findall(r'<h([1-6])\b', src)
    assert headings, "Join must contain headings"
    # Pairwise differences must never exceed 1 (no skips).
    last = 0
    for h in headings:
        lvl = int(h)
        if last > 0:
            assert lvl - last <= 1, f"Heading-level skip: H{last} → H{lvl}"
        last = lvl


# ---------- PI-4: rules.html heading outline + inline-Teko + Champion-row ----------

def test_pi4_rules_section_headings_promoted_to_h2():
    """All seven section heads in rules.html are H2 with .wc-section-heading.
    The seven cards: How It Works · Tier Structure · Group Stage Scoring ·
    Knockout Stage Scoring · Points Matrix · Tiebreaker · Edge Cases.
    The class-attribute form survives the S4.5 PI-3 id additions
    (`<h2 id="rules-*" class="wc-section-heading">`)."""
    import re
    src = RULES.read_text()
    h2_section_count = len(
        re.findall(r'<h2[^>]*\bclass="wc-section-heading"', src)
    )
    assert h2_section_count == 7, \
        f"Expected 7 .wc-section-heading H2s; found {h2_section_count}"


def test_pi4_rules_inline_teko_on_section_heads_retired():
    """The inline `style="font-family:'Teko'..."` declaration must not appear
    on any heading in rules.html (×6 → 0)."""
    src = RULES.read_text()
    assert "style=\"font-family:'Teko'" not in src, \
        "All inline-Teko declarations on section headings must retire"


def test_pi4_rules_subsection_headings_promoted_h5_to_h3():
    """Group Stage Scoring's two sub-heads (Match Results + Advancement
    Milestones) promote H5 → H3 via .wc-subsection-heading."""
    src = RULES.read_text()
    h3_subhead_count = src.count('<h3 class="wc-subsection-heading">')
    assert h3_subhead_count == 2, \
        f"Expected 2 .wc-subsection-heading H3s; found {h3_subhead_count}"


def test_pi4_rules_section_heading_primitive_defined_in_css():
    """`.wc-section-heading` + `.wc-subsection-heading` must exist as CSS classes."""
    css = CSS.read_text()
    assert '.wc-section-heading {' in css
    assert '.wc-subsection-heading {' in css


def test_pi4_rules_champion_row_uses_wc_champion_row_class():
    """Both Champion-row instances now carry .wc-champion-row, not inline navy literal."""
    src = RULES.read_text()
    # Two instances: knockout table + matrix conditional.
    assert src.count('wc-champion-row') == 2, \
        "Both Champion rows (knockout + matrix) must apply .wc-champion-row"
    # And the raw literal-navy inline style must not appear anywhere.
    assert 'rgba(0,40,104' not in src, \
        "Literal WC navy rgba retired per S4.2.1 PI-4 rule"


def test_pi4_wc_champion_row_class_defined_with_purple_tint():
    """The CSS class uses Council Purple tint + paints `> td` to defeat the
    Bootstrap --bs-table-bg white mask."""
    css = CSS.read_text()
    assert '.wc-champion-row {' in css
    assert '.wc-champion-row > td {' in css
    tr_start = css.index('.wc-champion-row {')
    tr_end = css.index('}', tr_start)
    assert 'font-weight: 700' in css[tr_start:tr_end]
    td_start = css.index('.wc-champion-row > td {')
    td_end = css.index('}', td_start)
    assert 'rgba(58, 29, 114' in css[td_start:td_end], \
        "Council-purple tint, not literal WC navy"
    assert '!important' in css[td_start:td_end], \
        "Must !important-override Bootstrap's --bs-table-bg lock"


def test_pi4_rules_heading_outline_has_no_skip():
    """Rules-page outline never skips: H1 → H2 → H3 maximum delta of 1."""
    src = RULES.read_text()
    import re
    headings = re.findall(r'<h([1-6])\b', src)
    assert len(headings) >= 8, f"Expected ≥8 headings on rules.html; found {len(headings)}"
    last = 0
    for h in headings:
        lvl = int(h)
        if last > 0:
            assert lvl - last <= 1, f"Heading-level skip: H{last} → H{lvl}"
        last = lvl


# ---------- PI-5: form-label / form-text scoped lift ----------

def test_pi5_game_worldcup_form_label_scoped_to_text_secondary():
    """body.game-worldcup .form-label + .form-text lift off --text-muted."""
    css = CSS.read_text()
    # Must scope to body.game-worldcup so cross-game forms (golf, cfb) keep
    # their token (the site-wide fix is routed to S6.1).
    assert 'body.game-worldcup .form-label,' in css
    assert 'body.game-worldcup .form-text' in css
    # Color points at --text-secondary.
    block_start = css.index('body.game-worldcup .form-label,')
    block_end = css.index('}', block_start)
    block = css[block_start:block_end]
    assert 'var(--text-secondary)' in block


# ---------- Cross-PI: render-time HTML lock via Flask test client ----------

def test_rendered_join_page_carries_section_h2_and_join_rules_link():
    """End-to-end render check: the join page emits the new shape."""
    from app import create_app
    from extensions import db
    from models.user import User
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        u = User(
            username='join_smoke',
            email='join_smoke@example.com',
            is_admin=False,
        )
        u.set_password('smoke1234')
        db.session.add(u)
        db.session.commit()
        client = app.test_client()
        # Log the user in via session cookie shortcut.
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        resp = client.get('/worldcup/join')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        assert '<h1>Sign the ledger' in body
        assert '<h2 class="wc-section-heading">How the pool works' in body
        assert 'class="join-rules-link"' in body
        assert 'Take your seat' in body
        # `&middot;` survives in the platform footer (Tribune attribution) —
        # scope the check to the page-hero subhead, which is where the
        # generic-metadata middot lived pre-S4.3.1.
        hero_open = body.index('<div class="page-hero">')
        hero_close = body.index('</div>\n  </div>\n</div>', hero_open)
        assert '&middot;' not in body[hero_open:hero_close], \
            "Hero subhead must not carry the &middot; metadata separator"
        # Sanity: heading outline carries no level skip.
        import re
        headings = [int(m) for m in re.findall(r'<h([1-6])\b', body)]
        last = 0
        for lvl in headings:
            if last > 0:
                assert lvl - last <= 1, f"Heading-level skip in rendered body: H{last} → H{lvl}"
            last = lvl


def test_rendered_rules_page_carries_six_section_h2s_and_two_h3_subheads():
    """End-to-end render check for the rules page outline. The class-
    attribute form survives the S4.5 PI-3 id additions."""
    import re
    from app import create_app
    from extensions import db
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    client = app.test_client()
    resp = client.get('/worldcup/rules')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert len(re.findall(r'<h2[^>]*\bclass="wc-section-heading"', body)) == 7
    assert body.count('<h3 class="wc-subsection-heading">') == 2
    assert body.count('wc-champion-row') == 2
    # No inline-Teko declarations remain.
    assert "style=\"font-family:'Teko'" not in body
    # No literal-navy rgba on champion rows.
    assert 'rgba(0,40,104' not in body
