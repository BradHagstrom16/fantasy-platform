---
name: World Cup Fantasy Pool — Design Specialization
description: Per-game design doctrine for the World Cup tab cluster. Layers on top of the platform foundation at the repo root's DESIGN.md.
register: product
extends: ../../DESIGN.md
colors:
  # WC carries two navies by construction (both frozen; don't "correct" one into the other):
  wc-navy: "#001A4D"        # --wc-navy (tokens.css) — the brand-token navy (text/accent consumers)
  wc-navy-slot: "#002868"   # body.game-worldcup --game-primary — the game-slot navy platform components consume (echoed by literal rgba(0,40,104,…) tints)
  wc-red: "#BF0A30"
  wc-red-dark: "#9C0826"
  # Champion banner ceremonial substrate (the only first-party dark surface on a WC body)
  wc-champion-banner-bg: "#00112ECC"   # rgba(0, 17, 46, .8), matching style.css
  # Five-tier team-categorical palette (scoped under body.game-worldcup; see §4 Tier Primitives).
  # Roles map to the game-design tier names in games/worldcup/WORLD_CUP_GAME_DESIGN.md.
  wc-tier1: "#D97706"  # Favorites  — burnt orange
  wc-tier2: "#4B7399"  # Contenders — steel blue
  wc-tier3: "#B45309"  # Dark Horses — copper
  wc-tier4: "#0D7377"  # Underdogs  — deep teal
  wc-tier5: "#9333EA"  # Wildcards  — purple
---

# Design System: World Cup Fantasy Pool

> Specialization of the platform design system. Top-level doctrine (palette framework, typography, elevation, motion, design laws, cross-game components) lives in the repo root `DESIGN.md`; this file owns World-Cup-specific palette, primitives, accent rank, substrate vocabulary, and copy register.
>
> **Archived (2026-07-19).** The 2026 tournament is complete; the game sits in a permanent post-state and WC surfaces are frozen (CLAUDE.md). This doc is archive doctrine and the regression net under the CFB-era lounge extraction — edit it only for an actual revival or the planned lounge move (transition plan §5), never for restyling.

---

## 1. Overview

The World Cup Fantasy Pool is a game-specific specialization layered on top of the core CCC platform design system. The root `DESIGN.md` remains the canonical source for platform primitives, typography, elevation, motion, navigation, spacing, and cross-game composition rules; this document defines only the World-Cup-specific identity layer: palette ranking, substrate doctrine, ceremonial surfaces, typography register, tier semantics, and game-scoped interaction patterns. WC specializes the platform rather than replacing it. New WC work should inherit platform grammar first and diverge only where tournament identity materially requires it.

The WC tab cluster is the platform's most surface-rich game state (`HUB` / `ROSTER` / `BOARD` / `SCHEDULE` / `STATS` / `RULES`). The governing UX principle is that all six tabs must read as one coherent tournament product rather than six independently themed tools. Cross-tab cohesion takes priority over per-tab novelty. A user moving through the WC surfaces should feel like they are traversing sections of a single tournament desk, not exiting and re-entering separate applications. Any new WC surface, component, or modifier should be evaluated against the question: "does this reinforce the sense that this is one game?"

P5 formally retired the fragmented "Tribune-Dark" body pattern and standardized all WC body surfaces onto the **Casual-Light** composition: white `.card` / `.wc-stat-card` surfaces on the platform bone substrate. This migration was a deliberate correction, not a neutral evolution. The prior WC register accumulated conflicting accent logic (gold accents against dark cards against red CTAs against inconsistent divider treatments) and became the dominant source of visual slop across the tab cluster. The Casual-Light migration resolved that inconsistency by restoring a single readable body register across all tabs while preserving WC identity in controlled locations. The navy `.page-hero.wc-hero-grad` remains the persistent signature identity anchor at the top of every tab; the `.wc-champion-banner` remains the only sanctioned dark body-area substrate and exists solely for the post-tournament ceremonial champion declaration.

The emotional target of the WC surfaces is an editorial tournament desk rendered through a restrained American civic-sports palette. The USA red / white / navy system reflects the United States hosting the 2026 tournament, but the register should read as institutional and ceremonial rather than patriotic branding. WC should feel like a major newspaper's dedicated World Cup section: editorial, structured, tournament-focused, and publicly legible. The design language favors newspaper over broadcast, dossier over telemetry, and tournament chronicle over sportsbook intensity. Motion, typography, and accent usage should reinforce sporting gravity and event cohesion rather than hyperactive "live match center" energy.

The WC register is intentionally anti-referential toward modern sports-app chrome. New WC work should not drift toward FIFA-app UI, ESPN-style match-center overlays, sportsbook dashboards, neon esports treatments, or broadcast-style telemetry panels. These references conflict with the Tribune editorial register and weaken the platform's visual coherence. WC surfaces should feel authored, structured, and ceremonial — not like a televised overlay stack or a generic mobile sports product.

---

## 2. Per-game palette: USA Red, White, Navy + Gold-Quaternary

The WC palette is a game-specific specialization layered on top of the platform color system. Its emotional register is an editorial tournament desk rendered through restrained American civic-sports colors: institutional rather than patriotic, ceremonial rather than nationalistic, and tournament-host-oriented rather than team-oriented. The palette should evoke the feeling of a major public sporting event hosted on American soil without drifting into flag branding, campaign aesthetics, or hyper-commercial sports-app styling.

The WC palette is intentionally asymmetric. The colors do not carry equal visual or semantic weight, and future WC work should preserve that hierarchy. Red drives interaction and urgency; white carries the reading substrate; navy provides structure and identity framing; gold exists as a restrained ceremonial support color. The palette works because each color has a defined role. Visual drift begins when colors become interchangeable.

### Accent Rank

1. **Red (`--wc-red` `#BF0A30`) — Primary Accent**

   Red is the dominant interactive and competitive accent across WC surfaces. It carries urgency, active state, hierarchy lift, and tournament energy. Red should be the color most associated with "this is the active World Cup layer."

   Primary consumers include:
   - Global `.btn-game` treatments
   - `.wc-stat-card.is-lead` hierarchy borders
   - Hero eyebrows
   - Current-user emphasis states
   - Active navigation pills
   - High-priority contextual emphasis on light cards

   Red replaces the older gold-forward WC emphasis system retired during the P5 unification effort. The shift was intentional: red reads more coherently across both navy framing surfaces and the Casual-Light body system while preserving competitive energy and visual clarity.

2. **White — Primary Reading Surface**

   White is the dominant body substrate across WC tabs. It carries readability, continuity, scanability, and cross-tab consistency. The WC body system intentionally privileges readable editorial layouts over immersive dark-mode sports UI.

   White surfaces primarily appear through:
   - Platform `.card`
   - `.wc-stat-card`
   - Table bodies
   - Read-only roster surfaces
   - Fixture and standings compositions

   The underlying page substrate remains the platform bone tone; WC does not introduce its own full-page body substrate.

3. **Navy (the game-slot `--game-primary` `#002868`) — Structural / Identity Anchor** (distinct from the brand token `--wc-navy` `#001A4D`, which serves text/accent consumers — two navies by construction, see the palette frontmatter)

   Navy carries authority, structure, framing, and persistent game identity. It is intentionally concentrated into framing surfaces rather than distributed broadly across body content.

   Primary consumers include:
   - `.page-hero.wc-hero-grad`
   - `.table-worldcup thead`
   - Sub-nav framing
   - Heading text on light surfaces
   - Resting secondary-button states
   - Ceremonial dark-surface compositions

   The navy hero is the visual anchor of the WC experience and survives across every tournament phase and tab. The Casual-Light migration standardized the body register below the hero, not the hero itself.

4. **Gold — Quaternary Ceremonial Accent**

   Gold is the WC ceremonial support color. It represents victory, completion, prestige, podium moments, and tournament culmination. Gold should feel intentional and slightly scarce; over-distribution weakens its ceremonial value.

   Reserved or primary consumers include:
   - Focus rings (`--gold-light`)
   - `.wc-champion-banner` champion-name typography
   - Podium or victory glow treatments
   - Select ceremonial emphasis moments

   Gold is not banned from WC surfaces, but it is no longer the dominant organizing accent. The P5 unification effort intentionally repositioned gold behind the red / white / navy system to reduce visual fragmentation and strengthen cross-tab consistency.

### Palette Semantics

The WC palette should be interpreted semantically rather than decoratively:

- **Red** = action, urgency, active competition, hierarchy
- **White** = readability, continuity, editorial clarity
- **Navy** = structure, authority, tournament framing
- **Gold** = ceremony, victory, culmination, prestige

When introducing new WC components, assign colors according to semantic role rather than visual preference.

### The 5-Tier Team Palette

`--wc-tier1` through `--wc-tier5` define the WC team-tier color system. These colors are scoped utility tokens, not part of the primary palette hierarchy above. Their purpose is categorical differentiation rather than emotional branding. Each token is defined under `body.game-worldcup` (see `static/css/style.css` `--wc-tier1`..`--wc-tier5`) and maps to a game-design tier role:

| Token | Hex | Tier role (from `games/worldcup/WORLD_CUP_GAME_DESIGN.md`) |
|---|---|---|
| `--wc-tier1` | `#D97706` | Favorites (7 teams, ×1) |
| `--wc-tier2` | `#4B7399` | Contenders (4 teams, ×1.5) |
| `--wc-tier3` | `#B45309` | Dark Horses (11 teams, ×2.5) |
| `--wc-tier4` | `#0D7377` | Underdogs (11 teams, ×4) |
| `--wc-tier5` | `#9333EA` | Wildcards (15 teams, ×7) |

Primary consumers include:

- `.wc-tier-dot`
- `.tier-badge`
- `.wc-multiplier-chip`

The tier palette should remain functionally legible and internally consistent. It should not compete visually with the core red / white / navy identity system.

### Named Rules

#### The Casual-Light Rule

Every WC body tab uses white `.card` / `.wc-stat-card` surfaces on the platform bone substrate. The WC identity system expresses itself through framing, typography, accent rank, and ceremonial moments rather than through persistent dark-mode body treatments.

#### The Hero-Stays-Navy Rule

`.page-hero.wc-hero-grad` is the persistent WC identity anchor. The Casual-Light migration applies below the hero only. Future WC work should preserve the navy hero as the stable framing layer tying all six tabs together.

#### The Gold-Quaternary Rule

Gold functions as a ceremonial support accent within the WC hierarchy, not as the dominant organizational color. Red carries primary interaction and competitive emphasis; gold carries tournament culmination and prestige. New WC work should preserve that distinction.

---

## 3. Typography specialization

The platform foundation defines the canonical typography hierarchy (`DESIGN.md` §3): Teko for headlines / labels / eyebrows, Newsreader for body copy, with size + weight + letter-spacing rules that apply across every game. This section codifies the two WC-specific layers on top of that foundation: the H1 Tribune voice rule, and the `.wc-eyebrow` primitive with its tonal variants.

### H1 Tribune voice on WC surfaces

User-facing WC routes treat their H1 as editorial Tribune voice rather than a functional chrome label. A WC route's masthead names the section the way an editorial newspaper would — `"The Match Sheet"` / `"The Standings"` / `"The Field Office"` / `"House Rules"` — rather than the literal route function (`"Schedule"` / `"Leaderboard"` / `"Stats Hub"` / `"Rules"`). The voice register comes from the platform's broader Tribune editorial framing (see top-level `DESIGN.md`) but lands hardest on the H1 because it is the first text the reader meets.

Two dispensations apply:

1. **Dynamic interpolated H1s.** When an H1 interpolates a noun the value already carries the voice — `{{ team.name }}` / `{{ current_user.get_display_name() }}` — and reading the H1 as a literal noun is correct. The Tribune voice rule does not apply to interpolated values; the value is itself the masthead.
2. **Logged-in utility auth surfaces.** The platform's logged-in utility auth register (top-level `DESIGN.md` §5 Auth Surface Composition) keeps functional H1s because the Tribune voice carries through the eyebrow + Newsreader copy inside the card. WC surfaces that compose under that auth register inherit the dispensation.

New WC user-facing routes should be evaluated against this rule. A functional H1 on a routine WC tab is a regression; the Tribune voice is part of how the tab cluster reads as one game.

### `.wc-eyebrow` primitive + variants

`.wc-eyebrow` is the WC-surface contextual label primitive: Teko 500, `0.7rem`, letter-spacing `0.08em`, uppercase, `var(--bone-mute)` default. It is the canonical "small uppercase metadata label above the headline" treatment across every WC tab. New WC sections that need a contextual label (game name, week, deadline, status) should reach for this primitive rather than inventing a new "kicker" pattern.

Two tonal variants are part of the primitive, not separate inventions:

- **`.wc-eyebrow-red`** (`var(--wc-red)`) — game-accent emphasis. Use when the eyebrow itself carries competitive or active-state signal.
- **`.wc-eyebrow-gold`** (`var(--gold-light)`) — ceremonial emphasis. Use sparingly, paired with the ceremonial slots reserved for gold in §2.

The bone-mute default is calibrated for the navy substrate: a scope rule lifts it to bone @ `.85` alpha there for AA contrast. Light-surface contexts override the default to `--text-secondary` or `--gold` via scoped rules at the consumer (`.wc-stat-card.is-lead`, `.your-standing-tribune`, `.player-pick-card`), preserving the primitive while adapting it to the substrate. New light-surface consumers that need the eyebrow on a white card should follow the same scoped-lift pattern rather than re-tinting the base primitive.

The dark-substrate scope rule was originally `.card.wc-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`. P5 re-scoped it to `.wc-champion-banner .wc-eyebrow:not(...)` when the `.card.wc-card` substrate retired; the champion banner is now the only dark-substrate consumer of the lift.

### Caption-floor exceptions (platform §3 body floor)

The WC classes sanctioned to step below the platform `≥16px` body floor to `≥0.75rem` (12px), where the row's primary read-target carries the dominant hierarchy: `.tier-mobile-card-picks`, `.tier-teams-list`, `.player-pick-card .pick-team small`, `.player-pick-card .pick-points small`, `.wc-microcaption`. Captions report, they don't lead — the exception never applies to a row's primary read-target.

---

## 4. Components

### Cards

The platform default `.card` (light-substrate Tribune card) is the canonical body card on every WC tab. The Stats reference pattern is `.wc-stat-card` (white, dark text, lead-rule on `.is-lead`); the leaderboard uses plain Bootstrap `.card`; ROSTER read-only and team-detail also use plain Bootstrap `.card` (with `.wc-card-flush` zero-padding utility where the fixture-list wants flush edges).

### `.wc-champion-banner` — the ceremonial dark surface

`.wc-champion-banner` is the dedicated post-tournament declaration surface for the World Cup game. It is the only sanctioned dark body-area substrate remaining after the P5 Casual-Light migration and exists specifically because the tournament ending deserves its own ceremonial composition layer. This primitive is intentionally singular. It is not a reusable dark-card utility, not a generic feature panel, and not a variant-capable extension point. Future WC work should treat the banner as a named ceremonial endpoint rather than a flexible component pattern.

The emotional register of the banner is official tournament declaration, not victory spectacle. The surface should feel conclusive, editorial, institutional, and earned. It represents the transition from active competition into finalized tournament history. The WC system intentionally concentrates dark body-area treatment into this single post-state moment so that the substrate shift itself carries emotional weight. Darkness is rare within the Casual-Light doctrine; the banner earns its darker register because the tournament has ended.

The substrate uses `rgba(0, 17, 46, .8)` navy with a `1px solid rgba(245, 241, 232, .08)` bone hairline border, `8px` radius, and `1rem` padding. The composition intentionally echoes the retired Tribune-Dark WC register without reintroducing that register as a reusable body pattern. The banner functions as a controlled ceremonial callback rather than a reopening of the prior dark-surface system.

Primary consumers include:

- `.champion-flag`
  - `5rem` mobile / `7rem` desktop
  - drop-shadow gold filter
  - treated as the central ceremonial visual mark

- `.champion-name`
  - Teko 700 uppercase
  - solid `--gold-light`
  - gradient-text treatment retired in P6 S6.1.1 PI-3

  Solid gold typography won because it reads more authoritative and editorial than decorative. The champion declaration should feel official and archival rather than glossy or effects-driven.

- `.champion-retrospect`
  - Newsreader italic
  - editorial retrospective voice
  - reads as tournament chronicle rather than UI metadata

- `.text-muted`
  - bone @ `.82` alpha
  - scoped with `!important` to override Bootstrap defaults on the navy substrate

- `.wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`
  - bone @ `.85` alpha
  - scoped locally to the banner substrate

The render gate is intentionally strict. The banner renders only on `/worldcup/` post-state when:
- match `#104`
- `is_completed=True`
- and `winner_team_id` is populated

The defensive `{% else %}` branch ("Champion not yet declared") reuses the same primitive with conditional content omitted. The gate exists to preserve the ceremonial integrity of the surface; the banner should never appear in speculative, live, or transitional tournament states.

The banner is also the canonical consumer of the WC gold ceremonial register defined in §2. Gold usage here is intentional and load-bearing: tournament completion, champion declaration, and archival victory memory are exactly the semantic moments reserved for quaternary gold emphasis. The banner therefore acts as both a UI primitive and a palette doctrine endpoint.

Future WC work should not generalize this primitive into:
- reusable dark cards
- highlight panels
- feature promos
- match-center overlays
- knockout-state variants
- or generic celebratory containers

Its power comes from rarity, specificity, and tournament finality.

### `.wc-stat-card` — the Casual-Light reference

`.wc-stat-card` is the canonical reference composition for the WC Casual-Light system. More than a reusable component, it serves as the doctrinal model for how World Cup information density should render across the platform after the P5 unification effort. Future WC surfaces should inherit its structural logic even when they do not literally reuse the class itself.

The primitive embodies the core WC body philosophy:
- white editorial substrate
- dark readable typography
- restrained hierarchy signaling
- dense but orderly statistical presentation
- tournament seriousness without broadcast-style noise

The card should read as an editorial statistics panel rather than a sportsbook dashboard or analytics terminal. The emotional target is informed tournament coverage: structured, information-rich, authoritative, and highly scanable without becoming visually aggressive.

The substrate is intentionally simple:
- white surface
- dark text
- restrained borders and elevation
- minimal decorative treatment

This simplicity is load-bearing. The WC system derives visual strength from hierarchy clarity, typography, spacing rhythm, and accent discipline rather than from heavy chrome or effects layering.

Optional hierarchy lift is provided through `.is-lead`, which applies a `2px solid var(--wc-red)` top border. The treatment exists to elevate time-sensitive or high-value statistical content without introducing broadcast urgency or "breaking news" energy. The emphasis should feel editorial and deliberate rather than animated or alarm-driven.

The `.is-lead` pattern replaces the retired `.card.wc-card-deadline` doctrine from the pre-P5 Tribune-Dark era. The migration intentionally re-derived emphasis from:
- gold-top-on-dark
to:
- red-top-on-light

This shift aligned WC hierarchy signaling with the broader Casual-Light system while preserving the sense of tournament importance previously carried by the darker substrate model.

`.wc-card-head` defines the canonical heading composition pattern:
- `.wc-eyebrow`
- heading
- optional contextual metadata

On light surfaces, `.wc-eyebrow` lifts from its navy-surface default into `--text-secondary` so the contextual label remains readable and editorially balanced against the white substrate. The eyebrow should function as structured contextual framing rather than decorative microcopy.

As the reference statistical composition for the WC game, `.wc-stat-card` should preserve:
- strong scanability
- stable spacing rhythm
- restrained emphasis hierarchy
- high table readability
- disciplined accent usage
- editorial composure under dense information load

Future WC statistical surfaces should avoid introducing:
- neon telemetry aesthetics
- glowing live-state chrome
- stacked gradient treatments
- sportsbook-style urgency indicators
- excessive motion signaling
- dashboard-style widget fragmentation
- visual clutter that competes with the data itself

The goal is not minimalism for its own sake. The goal is disciplined presentation where the information carries the excitement and the interface provides structure, hierarchy, and tournament atmosphere without overwhelming the content.

### `.wc-standing-card` — the live/post standing hero (Leverage Board)

`.wc-standing-card` is the live + post lead card (the `.wc-stat-card.is-lead` red-rule treatment) that opens the hub HUB tab body under the navy hero. It shares one rank-cluster register across both states (`.wc-standing-rank` Teko numeral + `.wc-standing-rank-hash` red `#` prefix + `.wc-standing-of`) so the live "Your Standing" and the post "Your Finish" read as one masthead shape.

In the **live** state the card is the **Leverage Board** ($impeccable critique 2026-05-24, "differentiate the hub"). This is a deliberate divergence from the platform lounge (`/`): the lounge owns the rank-trend dossier (sparkline + ledger) as the canonical rich surface; the hub does **not** mirror it. The hub instead leans into the multiplier system, which is the World Cup's custom-game identity (PRODUCT.md "custom games earn custom layers"). The board answers "where do my points come from, and where does my upside still sleep?" rather than "how has my rank moved?".

Composition:

- A compact header: the rank cluster + a single `.wc-standing-pts-line` (points · lead/clear delta · 7-day trend word). One line, not a multi-line ledger.
- `.wc-leverage` list: one `.wc-leverage-row` per pick — team link + `.wc-multiplier-chip` + a `.wc-leverage-bar` whose `--wc-red` fill is the pick's share of the roster's top earner + the realized points (or an "Out" label for eliminated picks). Rows sort carriers (any realized points) above dormant picks; within the carriers, biggest contribution on top so the bars descend ("where your points live"); the multiplier is only a tiebreak, which surfaces the highest-upside dormant picks at the top of the dormant tail. The multiplier is deliberately not ranked above points among carriers (that would break the descending-bar read).
- `.wc-leverage-summary`: a Newsreader line stating survival (`alive_count`, turning `--wc-red` via `.wc-lk--alert` when ≤ 4 alive) and naming the highest-multiplier dormant "upside" (e.g., "Your ×7 upside (IRN, PAN) hasn't fired yet").

Doctrine:

- The bar fill is `--wc-red`. Red is the WC primary interactive/competitive accent (§2 Accent Rank); "where the points are" is exactly that semantic role. Do not paint the bar navy or gold. (The retired parity embed had a `.wc-lk--red` class that resolved to `--game-primary` = navy — a class name that lied about its value; the Leverage Board removed it.)
- State is communicated by structure + label, never color alone: `.is-out` rows strike the team code and add an "Out" text label; `.is-dormant` rows show an empty bar track; `.is-scoring` rows show a filled bar plus the points value.
- The board **replaces** the separate read-only roster table the live state previously stacked beneath the standing card. The lead card is the single focal point; the full per-pick table lives one tap away on the ROSTER tab (`View Full Picks`). Don't re-add a sibling roster table to the live HUB.
- The card carries **no** rank sparkline. The rank chart is the lounge's signature; keeping it off the hub is what makes the two surfaces feel like distinct rooms rather than duplicates.

### Tier Primitives

WC surfaces carry three distinct tier primitives, one per semantic role. Each plays a non-overlapping job; the three should never collapse into a single class.

- **`.wc-tier-dot` — the visual mark.** A compact circular dot tinted per tier (`--wc-tier1`..`--wc-tier5`) used inline next to a country name. Read at a glance; never carries text. Used on `team_detail`, `player_detail`, `stats`, and `picks`.
- **`.tier-badge` — the numeric text companion.** A small pill rendering the literal tier number (`"T1"` / `"T2"` / ...) when the dot alone would leave a sighted reader guessing. Used on `rules.html` (the tier table and points-matrix header, standing alone as the sole tier indicator) and `_home_pre.html` (`roster-tier-label` on the ballot dossier). Not for use on team / player detail — the dot alone carries enough signal there. The badge is itself tier-colored with the number inside, so it never needs a `.wc-tier-dot` beside it (the prior rules-page pairing was redundant; per the rule of thumb below, pick one).
- **`.wc-multiplier-chip` — the multiplier indicator.** A chip rendering the tier's points multiplier (`×N`). Used on `picks.html` desktop readonly table and the tier-card heading. Never paired with `.tier-badge` on the same row; the chip's `"×N"` reading and the badge's `"T#"` reading would collide.

Rule of thumb: dot for the mark, badge for the number, chip for the multiplier. New tier-adjacent UI picks one, not two.

### Hero variant

`.page-hero.wc-hero-grad` is the WC-scoped variant of the platform `.page-hero` shell that overrides the gradient to the WC navy + red palette. The variant demonstrates the platform's per-game hero scoping pattern; new game-specific hero variants follow the same `.page-hero.<game>-hero-grad` shape. The WC hero is also the persistent identity anchor described in the Hero-Stays-Navy rule (§2); the Casual-Light migration explicitly stops at the hero so the navy framing remains continuous across every tournament phase and tab.

### Game sub-nav

The WC sub-nav uses the platform `.game-subnav .subnav-worldcup` shape (see top-level `DESIGN.md` §5 Navigation). `--subnav-accent` is `var(--wc-red)`; `--subnav-accent-rgb` is `191, 10, 48`. The active pill carries the red game-accent; rest pills are bone-mute on navy.

---

## 5. Do's and Don'ts (WC-scoped — additions to top-level §6)

The following rules are WC-specific enforcement doctrine layered on top of the platform-wide guidance in the root `DESIGN.md`. These rules exist to preserve cross-tab cohesion, maintain the Casual-Light editorial register, and prevent drift back toward fragmented sports-app styling.

### Do:

- **Do** default new WC body surfaces to the Casual-Light composition:
  - white `.card` / `.wc-stat-card`
  - platform bone substrate
  - restrained hierarchy
  - dark readable typography

- **Do** preserve the "one game" principle across all six WC tabs. Cross-tab continuity is more important than route-level novelty. New WC work should feel additive to a unified tournament system rather than visually independent.

- **Do** structure information editorially. WC surfaces should read like tournament coverage, standings pages, statistical panels, match sheets, and tournament dossiers — not like broadcast overlays or live-production graphics.

- **Do** use `.wc-eyebrow` for contextual section framing. Reach for `.wc-eyebrow-red` or `.wc-eyebrow-gold` only when the semantic shift is intentional and meaningful.

- **Do** preserve the semantic color hierarchy defined in §2:
  - red for action and hierarchy
  - white for readability
  - navy for structure and framing
  - gold for ceremony and culmination

- **Do** scope foreground-color overrides directly on `.wc-champion-banner` consumers (`.text-muted`, `.wc-eyebrow:not(...)`, etc.) so the ceremonial substrate remains self-contained and does not leak dark-surface assumptions into the broader WC system.

- **Do** preserve the navy `.page-hero.wc-hero-grad` as the persistent identity anchor across every WC tab. The hero is the stable framing layer tying the tournament together.

- **Do** preserve restraint in ceremonial treatments. Rarity is what gives the WC ceremonial moments force. Gold, dark substrates, and victory treatments carry emotional weight precisely because they are concentrated into specific tournament moments rather than distributed broadly.

- **Do** match the H1 Tribune voice on user-facing WC routes (§3). Functional labels should generally resolve into editorial tournament language unless explicitly exempted by the doctrine.

- **Do** treat statistical density as a presentation challenge rather than an excuse for dashboard chrome. Information richness should come from structure, hierarchy, and readability rather than decorative UI aggression.

### Don't:

- **Don't** invent isolated visual systems for individual WC routes. A user moving from `HUB` → `ROSTER` → `BOARD` → `SCHEDULE` → `STATS` → `RULES` should feel continuity of substrate, hierarchy, typography, and interaction language.

- **Don't** introduce new dark body-area substrates. The only sanctioned WC dark surfaces are:
  - `.page-hero.wc-hero-grad`
  - `.wc-champion-banner`

  The Casual-Light system is the canonical WC body register.

- **Don't** reach for `.wc-champion-banner` as a generic dark card, feature panel, highlight container, or knockout-state utility. It is a single-purpose ceremonial primitive tied specifically to tournament completion.

- **Don't** over-theme WC surfaces. WC identity comes from disciplined concentration, not saturation. The system derives strength from controlled accent placement, restrained ceremony, and stable editorial structure rather than constant visual intensity.

- **Don't** simulate live TV graphics, sportsbook dashboards, ESPN-style match centers, FIFA-app chrome, or broadcast telemetry overlays. These references conflict with the WC editorial doctrine and weaken cross-tab coherence.

- **Don't** distribute gold as a routine interaction accent. Gold carries ceremonial meaning inside the WC hierarchy and should remain associated with victory, culmination, and tournament closure.

- **Don't** use `match.stage|title` in Jinja templates. Use the `stage_label` SSoT helper documented in `CLAUDE.md`. The `|title` filter corrupts ALL-CAPS knockout labels (`SF` → `Sf`) and underscored values (`third_place` → `Third_Place`).

- **Don't** broadcast global foreground-color overrides intended for dark substrates (`tbody td { color: light }`, etc.). WC body surfaces are overwhelmingly light-substrate compositions; dark-surface overrides must remain locally scoped.

- **Don't** mistake visual noise for tournament energy. WC intensity should come from competition state, standings movement, statistical context, typography, and selective accent usage — not from glow stacks, excessive animation, or layered interface effects.

---

## 6. Visual smoke + verification cadence

All WC visual verification should evaluate the system as a unified tournament product rather than as isolated route implementations. The primary regression question is not "does this page look correct?" but rather:

> "Does this still feel like one coherent tournament system?"

The WC design system derives much of its strength from continuity of substrate logic, hierarchy behavior, typography register, accent discipline, and ceremonial restraint across all six tabs. Visual smoke therefore exists primarily to detect coherence drift.

### Core visual smoke workflow

For any WC body change:

- run the dev server using the platform port-5099 worktree pattern (see `CLAUDE.md` § "Run development server")
- use `WC_FAKE_NOW` to walk the tournament through:
  - pre-state
  - live-state
  - post-state
  - champion-state

The WC partial system gates substantial UI behavior on tournament state, so a single timestamp is not sufficient verification coverage. The goal is to confirm that state transitions feel intentional, meaningful, and compositionally coherent rather than visually disconnected.

Differences between tournament states are expected and desirable when they communicate tournament progression or ceremonial escalation. State divergence becomes a regression only when the UI begins to feel like separate products with unrelated visual logic.

### Cross-tab continuity smoke

Every substantial WC UI change should include a manual continuity pass across:

`HUB` → `ROSTER` → `BOARD` → `SCHEDULE` → `STATS` → `RULES`

The eye-test standard is:

> "This is one game."

Verification should specifically evaluate:
- substrate continuity
- typography rhythm
- accent consistency
- card composition logic
- navigation coherence
- hierarchy behavior
- editorial tone consistency
- density handling
- ceremony restraint

Cross-tab cohesion is a primary design invariant, not a secondary polish concern.

### Regression categories

WC smoke testing should actively look for the following regression patterns:

- **Inconsistent accent logic**
  - red / navy / gold roles becoming interchangeable
  - gold drifting into routine interaction emphasis
  - route-specific accent reinterpretation

- **Isolated route styling**
  - one tab inventing its own visual grammar
  - bespoke spacing or hierarchy systems disconnected from the broader WC language
  - components that feel imported from another product

- **Substrate drift**
  - unauthorized dark body surfaces
  - excessive tonal experimentation
  - erosion of the Casual-Light doctrine

- **Ceremony overuse**
  - gold saturation
  - excessive victory styling
  - over-decorated hierarchy treatments
  - dark-surface proliferation

- **Dashboard fragmentation**
  - widgetized sports-dashboard layouts
  - telemetry-style visual aggression
  - sportsbook UI drift
  - broadcast-overlay aesthetics replacing editorial structure

The WC system should preserve tournament energy without collapsing into sports-broadcast noise.

### Champion-state verification

The champion state is a special-case verification target because it intentionally reintroduces the only sanctioned dark body-area surface in the WC system.

To verify `.wc-champion-banner` rendering:
- prepare the DB so:
  - match `#104`
  - `is_completed=True`
  - `winner_team_id` is populated

Without those conditions:
- the champion banner will not render
- the defensive `{% else %}` branch also remains gated behind `final_match`

Verification should confirm:
- the banner reads as a ceremonial state transition rather than a generic dark card
- the dark substrate feels earned through rarity
- gold emphasis remains concentrated and authoritative
- the post-state still belongs to the same WC system established during earlier tournament phases

The champion state should feel like culmination, not visual system replacement.

### Implementation verification idioms

WC implementation work inherits several established verification idioms from earlier tournament phases:

- anchored CSS scans using `^...` + `re.MULTILINE`
- property-anchored `(?<![-\w])` lookbehinds
- rule-block extraction using `\{([^}]*)\}`
- forbidden-list terminators using `\s*[,{]`

These patterns help preserve targeted enforcement without introducing broad unintended matches during automated maintenance work.

All Python comments and docstrings introduced in WC phases should remain ASCII-only for tooling consistency and cross-environment reliability.
