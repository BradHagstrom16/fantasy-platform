---
name: World Cup Fantasy Pool — Design Specialization
description: Per-game design doctrine for the World Cup tab cluster. Layers on top of the platform foundation at the repo root's DESIGN.md.
register: product
extends: ../../DESIGN.md
colors:
  # WC-specific palette (consumed via body.game-worldcup overrides of --game-primary / --game-accent)
  wc-navy: "#002868"
  wc-red: "#BF0A30"
  wc-red-dark: "#9C0826"
  # Champion banner ceremonial substrate (the only first-party dark surface on a WC body)
  wc-champion-banner-bg: "#001A4DCC"
  # Five-tier color set for team tiers
  wc-tier1: "TODO — fill in tier color tokens (or cross-ref to tokens.css if they live there)"
  wc-tier2: "TODO"
  wc-tier3: "TODO"
  wc-tier4: "TODO"
  wc-tier5: "TODO"
---

# Design System: World Cup Fantasy Pool

> Specialization of the platform design system. Top-level doctrine (palette framework, typography, elevation, motion, design laws, cross-game components) lives in the repo root `DESIGN.md`; this file owns World-Cup-specific palette, primitives, accent rank, substrate vocabulary, and copy register.

> **Status: WORKING DRAFT.** P5 of the WC tab unification project closed `.card.wc-card` as a generic dark substrate and re-homed the ceremonial champion banner onto a dedicated `.wc-champion-banner` primitive. This file is being authored as part of that close-out. **Brad drafts new doctrine sections** (Casual-Light, accent rank, ceremonial slot); **the assistant restructures** per `feedback_load_bearing_drafts.md` once the draft lands. The "Extracted from top-level (raw material)" sections below are verbatim excerpts of WC-specific content that moved out of the root `DESIGN.md` — they are reference material for the draft, not finished prose.

---

## 1. Overview

> **TO DRAFT — Brad.** A few short paragraphs framing the WC register inside the CCC platform. Suggested anchors:
>
> - The WC tab cluster is the platform's most surface-rich game (six tabs: HUB / ROSTER / BOARD / SCHEDULE / STATS / RULES).
> - As of P5 every body sits on the **Casual-Light pattern** (white `.card` / `.wc-stat-card` on bone); the dark navy `.page-hero.wc-hero-grad` is WC's signature identity moment at the top of every tab; the `.wc-champion-banner` is the only surviving body-area dark surface, used only for the post-tournament champion declaration.
> - The voice register is **Tribune** (editorial newspaper applied to the World Cup) — see §3 for the H1 voice doctrine and §6 for the eyebrow/copy register.
> - Anti-references that are extra-strong for WC specifically (e.g., FIFA-app chrome, broadcast-overlay aesthetic, anything that reads as ESPN match center). Distinct from the platform anti-references; complementary, not redundant.

---

## 2. Per-game palette: USA Red, White, Navy + Gold-Quaternary

> **TO DRAFT — Brad.** The substantive accent-rank doctrine. Suggested anchors:
>
> - **Accent rank** (the locked decision from the WC tab unification project):
>   1. **Red (`--wc-red` `#BF0A30`)** — primary. Global `.btn-game` repaint across every WC substrate; `.wc-stat-card.is-lead` border-top; hero eyebrows; current-user row tint; ceremonial emphasis on light cards.
>   2. **White** — card substrate (bone page substrate stays the platform default).
>   3. **Navy (`--wc-navy` `#002868`)** — dark hero substrate; `.table-worldcup` `<thead>` bar; heading text on light cards; the inactive `.btn-outline-secondary`-style restful state.
>   4. **Gold (quaternary)** — focus rings (a11y lock, `--gold-light`); the `.wc-champion-banner` champion-name typography; podium glow on victory moments. Never on the hero phase chip, never on `.is-lead`, never on routine emphasis. If a designer reaches for gold and it's not in one of the reserved slots, push back to red.
> - **Why the demotion.** Gold was the original WC accent before the tab unification project. The Tribune-Dark register that gold supported retired in P5 because the cross-tab inconsistency (red CTAs against gold accents against gold dividers against dark cards) was the dominant slop signal. The new Casual-Light pattern + USA-flag-coded accent rank is the resolution.
> - **The 5-tier team palette** (`--wc-tier1` through `--wc-tier5`) — the team-tier color set. Used inline on `.wc-tier-dot`, `.tier-badge`, `.wc-multiplier-chip`. Scoped utilities, not part of the core palette ranking above.

### Named Rules

> **TO DRAFT — Brad.** Suggested anchors:
> - **The Casual-Light Rule.** Every WC tab body uses white `.card` / `.wc-stat-card` on bone. Dark substrates are reserved for the ceremonial moments listed in §5.
> - **The Hero-Stays-Navy Rule.** `.page-hero.wc-hero-grad` is WC's signature identity. The casual-light migration is below-hero only.
> - **The Gold-Quaternary Rule.** Gold appears only in the four reserved slots; everywhere else reads red.

---

## 3. Typography specialization

### H1 Tribune voice on WC surfaces

> **From top-level DESIGN.md §3 (extracted — verbatim raw material; merge into the WC-scoped paragraph here):**
>
> *"On user-facing WC surfaces the H1 carries **Tribune voice** — an editorial section name, not a functional chrome label ('The Match Sheet' / 'The Standings' / 'The Field Office' / 'House Rules', not 'Schedule' / 'Leaderboard' / 'Stats Hub' / 'Rules'). Two dispensations: (a) dynamic H1s that interpolate a noun (`{{ team.name }}` / `{{ current_user.get_display_name() }}`) read functionally because the value carries the voice; (b) the logged-in utility auth register (§5 Auth Surface Composition) keeps functional H1s because the Tribune voice carries through the eyebrow + Newsreader copy inside the card."*

### `.wc-eyebrow` primitive + variants

> **From top-level DESIGN.md §3 (extracted — verbatim raw material):**
>
> *"`.wc-eyebrow` (Teko 500, `0.7rem`, letter-spacing `0.08em`, uppercase, `var(--bone-mute)`): the WC-surface contextual label. Tonal variants are part of the primitive: `.wc-eyebrow-red` (`var(--wc-red)`) for game-accent emphasis, `.wc-eyebrow-gold` (`var(--gold-light)`) for ceremonial moments. The bone-mute default is calibrated for the navy substrate (scope rule lifts to bone @ .85 alpha there for AA); light-surface contexts override to `--text-secondary` or `--gold` via scoped rules (`.wc-stat-card.is-lead`, `.your-standing-tribune`, `.player-pick-card`)."*
>
> **P5 update**: the navy-substrate scope rule was `.card.wc-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`. Post-P5 it re-scopes to `.wc-champion-banner .wc-eyebrow:not(...)` — the only remaining dark-substrate consumer.

---

## 4. Components

### Cards

The platform default `.card` (light-substrate Tribune card) is the canonical body card on every WC tab. The Stats reference pattern is `.wc-stat-card` (white, dark text, lead-rule on `.is-lead`); the leaderboard uses plain Bootstrap `.card`; ROSTER read-only and team-detail also use plain Bootstrap `.card` (with `.wc-card-flush` zero-padding utility where the fixture-list wants flush edges).

### `.wc-champion-banner` — the ceremonial dark surface

> **TO DRAFT — Brad.** The new primitive that closed the project. Suggested anchors:
>
> - Substrate: `rgba(0, 17, 46, .8)` (navy, .8 alpha) on a `1px solid rgba(245, 241, 232, .08)` hairline bone border, `8px` radius, `1rem` padding.
> - Consumers: `.champion-flag` (5rem mobile / 7rem desktop, drop-shadow-gold filter); `.champion-name` (Teko 700 uppercase, solid `--gold-light` — gradient-text retired in P6 S6.1.1 PI-3); `.champion-retrospect` (Newsreader italic Tribune editorial register); `.text-muted` (bone @ .82 alpha, `!important` for the Bootstrap cascade); `.wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` (bone @ .85).
> - Render gate: only on `/worldcup/` post-state when match #104 `is_completed=True` AND `winner_team_id` is set. The defensive `{% else %}` branch ("Champion not yet declared") renders the same primitive with the conditional content omitted.
> - Why it earns its own primitive: gold is reserved for ceremonial slots (per accent rank §2); the champion banner IS the canonical ceremonial moment for WC. Dedicated naming makes the design intent legible to future maintainers; the primitive can't be accidentally reached for as a generic dark card.

### `.wc-stat-card` — the Casual-Light reference

> **TO DRAFT — Brad.** Suggested anchors:
>
> - White surface, dark text, optional `.is-lead` border-top `2px solid var(--wc-red)` for time-critical hierarchy lift.
> - Mirrors the Stats reference panel (`stats.html`); every other WC tab adopts the same primitive for consistency.
> - Replaces the retired `.card.wc-card-deadline` modifier (gold-top-on-dark → red-top-on-light, rederived in P1).
> - `.wc-card-head` is the eyebrow + heading composition pattern; eyebrow uses `.wc-eyebrow` (with the light-substrate lift to `--text-secondary` so the bone-mute default reads on white).

### Tier Primitives

> **From top-level DESIGN.md §5 (extracted — verbatim raw material):**
>
> *"WC surfaces carry three distinct tier primitives. Each plays a non-overlapping role; do not collapse them into a single class.*
>
> - *`.wc-tier-dot` — the **visual mark**. A compact circular dot tinted per tier (`--wc-tier1`…`--wc-tier5`) used inline next to a country name. Read at a glance; never carries text. Used on `team_detail`, `player_detail`, `stats`, `picks`, and `rules`.*
> - *`.tier-badge` — the **numeric text companion**. A small pill rendering the literal tier number ("T1" / "T2" / …) when the dot alone would leave a sighted reader guessing. Used on `rules.html` (×5, paired with `.wc-tier-dot` in the tier-table cell) and `_home_pre.html` (`roster-tier-label` on the ballot dossier). Not for use on team/player detail — the dot alone carries enough signal there.*
> - *`.wc-multiplier-chip` — the **multiplier indicator**. A dark-surface chip rendering the tier's points multiplier (×N). Used on `picks.html` desktop readonly table and tier-card-header. Never paired with `.tier-badge` on the same row; the chip's '×N' reading and the badge's 'T#' reading would collide.*
>
> *Rule of thumb: dot for the mark, badge for the number, chip for the multiplier. New tier-adjacent UI picks one, not two."*

### Hero variant

> **From top-level DESIGN.md §5 (extracted — verbatim raw material):**
>
> *"`.page-hero.wc-hero-grad`: WC-scoped variant that overrides the gradient to navy + red (the World Cup palette). Demonstrates the per-game scoping pattern; new game-specific hero variants follow the same `.page-hero.<game>-hero-grad` shape."*

### Game sub-nav

The WC sub-nav uses the platform `.game-subnav .subnav-worldcup` shape (see top-level DESIGN.md §5 Navigation). `--subnav-accent` is `var(--wc-red)`; `--subnav-accent-rgb` is `191, 10, 48`. The active pill carries the red game-accent; rest pills are bone-mute on navy.

---

## 5. Do's and Don'ts (WC-scoped — additions to top-level §6)

> **TO DRAFT — Brad.** Suggested anchors:
>
> ### Do:
> - **Do** default new WC body surfaces to the Casual-Light pattern (white `.card` / `.wc-stat-card` on bone).
> - **Do** scope foreground-color overrides on the `.wc-champion-banner` substrate (`text-muted`, `wc-eyebrow:not(...)`) so the banner reads on its navy interior.
> - **Do** use `.wc-eyebrow` for any WC section that needs a contextual label; reach for the tonal variants (`-red`, `-gold`) only when the contextual signal needs the semantic shift.
> - **Do** match the H1 Tribune voice on user-facing WC routes (§3).
>
> ### Don't:
> - **Don't** reach for `.wc-champion-banner` as a generic dark card; it's a single-purpose ceremonial primitive.
> - **Don't** introduce gold accents outside the four reserved slots (focus rings, `.wc-champion-banner` champion-name, podium glow, occasional ceremonial moments). Push back to red.
> - **Don't** mock dark mode on a WC body. The bone-page substrate is the canonical light canvas; the only first-party dark surfaces on WC are `.page-hero.wc-hero-grad` (the hero) and `.wc-champion-banner` (the ceremonial slot).
> - **Don't** use `match.stage|title` in Jinja templates — use the `stage_label` SSoT helper (documented in CLAUDE.md). The `|title` filter mangles ALL-CAPS knockout codes (`'SF'` → `'Sf'`) and underscored values (`'third_place'` → `'Third_Place'`).
> - **Don't** broadcast `tbody td { color: light }` rules on a `.wc-champion-banner` table — the banner has no tables. Light-substrate cell color is handled by Bootstrap defaults on every other WC tab.

---

## 6. Visual smoke + verification cadence

> **TO DRAFT — Brad** (or leave as reference cross-link to the project plan). Suggested:
>
> - Visual smoke for any WC body change: dev server + `WC_FAKE_NOW` covering pre/live/post for the tab in question (the home-state partials gate on tournament state, so a single `WC_FAKE_NOW` walks them all). Use the platform port-5099 worktree pattern (see `CLAUDE.md` § "Run development server").
> - Cross-tab smoke: click HUB → ROSTER → BOARD → SCHEDULE → STATS → RULES in one session; eye-test is "this is one game" (the project's headline outcome).
> - For surfaces depending on post-state DB seeding (the champion banner), prep the DB so match #104 `is_completed=True` + `winner_team_id` is set; otherwise the banner doesn't render and the conditional `{% else %}` fallback also doesn't render (the entire banner div is gated on `final_match`).
> - Test idiom inheritance from prior WC phases: `^...` + `re.MULTILINE` anchored CSS scans; property-anchored `(?<![-\w])` lookbehinds; rule-block extraction via `\{([^}]*)\}`; forbidden-list `\s*[,{]` terminators. ASCII-only in P*-introduced Python comments + docstrings.

---

## Appendix A: Extracted content (raw material, to merge into drafted sections above)

These paragraphs were moved out of the top-level `DESIGN.md` as part of the P5 file-split. They land here as reference material for the new doctrine — the assistant will weave them into the final sections during the post-draft restructure pass.

> **From top-level §2 Tertiary palettes (extracted):**
>
> *"World Cup (`body.game-worldcup`): Navy (`#002868`) + Match Red (`#BF0A30`). Knockout urgency, multipliers. WC also defines a 5-tier color set for team tiers (`--wc-tier1` through `--wc-tier5`); these are scoped utilities, not part of the platform palette."*

> **From top-level §5 Cards (extracted — describes the now-retired `.card.wc-card` Tribune-Dark register):**
>
> *"`.card.wc-card`: `rgba(0, 17, 46, 0.8)` (WC Card Navy) fill, `1px solid rgba(245, 241, 232, 0.08)` border, `--radius` (~8px) corner radius, `1rem` padding. Hover brightens border to `rgba(242, 211, 107, 0.25)` (gold whisper). Used wherever the World Cup surface needs to break the bone-page register and feel like a knockout match. Any content layered on this surface must explicitly carry a light foreground color, scoped to the surface (don't broadcast `tbody td { color: light }` globally; it breaks Bootstrap-default rows)."*
>
> **P5 disposition**: the Tribune-Dark register **retired entirely**. The substrate primitive is gone. The single surviving consumer (post-tournament champion banner) re-homed onto the dedicated `.wc-champion-banner` primitive documented in §4 above. The above paragraph is here for historical context only — do not restore the doctrine.

> **From top-level §6 Don't (extracted):**
>
> *"Don't mock dark mode on light surfaces. The auth pages (Tribunal Black backdrop) and `.card.wc-card` (Tribune-Dark) are the only first-party dark surfaces; everything else is bone-on-light. Don't invent a third dark register."*
>
> **P5 update**: replace `.card.wc-card` with `.wc-champion-banner` in the top-level Don't list. The rule itself (one bone substrate + named dark register surfaces) survives the substrate flip; only the named primitive changes.

> **From top-level §6 Do (extracted — retired entirely):**
>
> *"Do put light foreground colors on `.card.wc-card` content, scoped to the card surface. Bootstrap defaults will read black-on-navy without it."*
>
> **P5 disposition**: rule retires with the substrate primitive. The replacement rule lives in §5 above (scope foreground overrides on `.wc-champion-banner`).
