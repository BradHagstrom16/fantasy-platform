---
name: Corrupt Commish Club
description: A members-only sports bulletin for private fantasy pools. Editorial Tribune meets gilded clubhouse.
colors:
  # CCC house palette (canonical brand colors)
  council-purple: "#3A1D72"
  chamber-purple: "#1C0A3A"
  tribunal-black: "#140828"
  press-purple: "#6B3FAD"
  ink-purple: "#0A0612"
  commish-gold: "#C9A227"
  trophy-light: "#F2D36B"
  gold-dark: "#8A6A1A"
  gold-hi: "#FFF1B8"
  pressroom-bone: "#F3EFE6"
  bone-dim: "#D8D1BE"
  # Platform text + surface aliases
  text-ink: "#1C1730"
  text-secondary: "#5A5470"
  text-muted: "#8A849B"
  surface-card: "#FFFFFF"
  surface-muted: "#EDEBF4"
  border-default: "#D8DDE8"
  border-light: "#E8E5F0"
  # Semantic state
  success: "#1A7A45"
  danger: "#C0392B"
  info: "#3B5998"
  # Live-game indicators (used in scoring + status surfaces only)
  live-red: "#E63946"
  live-green: "#64DBA0"
  live-orange: "#FF8A3C"
  # Per-game tertiary palettes (headline colors; full ramps + doctrine live in each game's DESIGN.md)
  golf-green: "#006747"
  golf-gold: "#B8993E"
  cfb-crimson: "#C5050C"
  cfb-midnight: "#0E0A0C"   # --cfb-canvas, the dark room's body substrate (full warm ramp in games/cfb/DESIGN.md)
  wc-navy: "#001A4D"        # --wc-navy (tokens.css) — the WC brand-token navy (text/accent consumers)
  wc-navy-slot: "#002868"   # body.game-worldcup --game-primary — the game-slot navy platform components consume; two navies by construction (frozen)
  wc-red: "#BF0A30"
  docket-oxblood: "#6E1F2E" # --game-primary on body.game-docket (light court-paper room; full family in games/docket/DESIGN.md)
  docket-garnet: "#A63446"  # --game-accent on body.game-docket — the docket stamp
typography:
  display:
    fontFamily: "'Teko', sans-serif"
    fontSize: "2.4rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.03em"
  headline:
    fontFamily: "'Teko', sans-serif"
    fontSize: "1.9rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.03em"
  title:
    fontFamily: "'Teko', sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "0.03em"
  body:
    fontFamily: "'Newsreader', Georgia, serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "'Teko', sans-serif"
    fontSize: "0.9rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.06em"
  eyebrow:
    fontFamily: "'Teko', sans-serif"
    fontSize: "0.85rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.14em"
  # The enumerated type ramp. The six roles above name the canonical voices;
  # this map is the full set of steps the platform + game rooms are allowed to
  # use, so anything off it reads as drift. Round increments only: near
  # neighbours (0.66/0.68/0.72/0.74/0.76/0.78rem and friends) resolve to the
  # nearest step rather than earning one of their own.
  scale:
    step-0-60: "0.6rem"
    step-0-65: "0.65rem"
    step-0-70: "0.7rem"
    step-0-75: "0.75rem"
    step-0-80: "0.8rem"
    step-0-95: "0.95rem"
    step-1-05: "1.05rem"
    step-1-10: "1.1rem"
    step-1-15: "1.15rem"
    step-1-20: "1.2rem"
    step-1-25: "1.25rem"
    step-1-30: "1.3rem"
    step-1-35: "1.35rem"
    step-1-40: "1.4rem"
    step-1-60: "1.6rem"
    step-1-70: "1.7rem"
    step-1-80: "1.8rem"
    step-2-00: "2rem"
    step-2-20: "2.2rem"
    step-2-60: "2.6rem"
    step-2-80: "2.8rem"
    step-3-00: "3rem"
    step-3-50: "3.5rem"
    step-4-00: "4rem"
    step-4-50: "4.5rem"
    step-5-00: "5rem"
    step-6-00: "6rem"
    step-7-00: "7rem"
rounded:
  hairline: "1px"
  xxs: "2px"
  xs: "3px"
  xs-lg: "4px"
  sm-tight: "5px"
  sm-mid: "6px"
  sm: "0.5rem"
  md-tight: "10px"
  md: "12px"
  lg: "0.875rem"
  lg-plus: "16px"
  xl: "22px"
  xxl: "2rem"
  pill: "999px"
spacing:
  card-padding: "1rem"
  hero-padding-y: "3.5rem"
  auth-card-padding: "2.5rem 2rem"
components:
  button-primary:
    backgroundColor: "{colors.council-purple}"
    textColor: "{colors.pressroom-bone}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
  button-primary-hover:
    backgroundColor: "{colors.press-purple}"
    textColor: "{colors.pressroom-bone}"
    rounded: "{rounded.sm}"
  button-trophy:
    backgroundColor: "{colors.commish-gold}"
    textColor: "{colors.chamber-purple}"
    rounded: "{rounded.sm}"
    padding: "0.65rem 1.5rem"
  button-trophy-hover:
    backgroundColor: "{colors.trophy-light}"
    textColor: "{colors.chamber-purple}"
    rounded: "{rounded.sm}"
  button-game:
    backgroundColor: "{colors.council-purple}"
    textColor: "{colors.pressroom-bone}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
  card-default:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-ink}"
    rounded: "{rounded.lg}"
    padding: "1rem"
  form-control:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-ink}"
    rounded: "{rounded.sm}"
    padding: "0.6rem 0.9rem"
    height: "44px"
  form-control-focus:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-ink}"
    rounded: "{rounded.sm}"
---

# Design System: Corrupt Commish Club

## 1. Overview

**Creative North Star: "The Commissioner's Club Tribune."**

The official sports paper of an exclusive members' club. Every leaderboard reads as published. Every result archives itself into club history. The UI combines editorial hierarchy with lounge-level exclusivity.

A private sports bulletin assembled inside the club itself. Editorial hierarchy, trophy-room warmth, live-game intensity, and insider rivalry coexist on the same surface. Gold accents feel ceremonial and noble, never corporate. Purple feels like the room itself: deep, social, competitive, royal.

> "Tonight's results matter because the club will remember them."

### Visual Energy

- **Mastheads above the fold.** Every primary page opens with a Teko-display banner, not a flowing navbar-into-content.
- **Condensed sports-headline display type.** Teko is the masthead voice; Newsreader is the editorial body.
- **Gold divider rules between sections.** Borders and underlines in `var(--gold)` separate sections, never colored side-stripes on cards (an absolute ban, see Don'ts).
- **Purple press-room shadows.** Card depth uses the brand-tinted `--shadow-sm/md/lg` scale (purple-cast). Never neutral gray.
- **Trophy-case metallic accents on primary CTAs only.** The `--metal-gold` and `--metal-gold-flat` gradients are reserved for primary buttons. Gold gradients on cards, headers, or backgrounds dilute the trophy.
- **Structured layouts that break for moments of drama.** Default rhythm is orderly columns; hero, champion, and live-state moments interrupt that order on purpose.

### Key Characteristics

- Editorial newspaper hierarchy, not SaaS-dashboard density
- Brand-tinted depth (purple shadows, gold glow), never neutral gray
- Quiet authority in chrome, loud moments at primary CTAs
- Mobile-first surfaces (375 px viewport is the design floor)
- Four game palettes layered over CCC chrome via `body.game-<slug>` overrides
- Newsreader serif paragraphs, Teko condensed-sans headlines, no third font

The system explicitly rejects: ESPN/Yahoo fantasy chrome (banner ads, untiered tables, navigation overload); generic SaaS dashboards (Inter on gray-on-white, hero-metric template, identical card grids); Bootstrap-starter regression (stock `.card`, unscoped `.btn-primary`, default navbar); crypto/Web3 aesthetic (neon-on-black, glassmorphism); generic sports skeuomorphism (stadium textures, scoreboard fonts).

## 1.5. Per-game specialization

This file is the platform foundation. Per-game design doctrine — palette specialization, game-scoped primitives, register vocabulary, copy voice — lives in each game's own `DESIGN.md` so the foundation stays lean and a game's doctrine evolves on its own cadence.

- **World Cup**: `games/worldcup/DESIGN.md` (archived game; doc frozen). Owns the WC accent rank (red → white → navy → gold-quaternary), the Casual-Light substrate pattern, the `.wc-champion-banner` ceremonial primitive, the `.wc-stat-card` reference, the `.wc-eyebrow` variants (`-red` / `-gold`), the team-tier palette (`--wc-tier1`…`--wc-tier5`), the three tier primitives (`.wc-tier-dot` / `.tier-badge` / `.wc-multiplier-chip`), the Tribune voice for WC H1s.
- **CFB**: `games/cfb/DESIGN.md` — the flagship's design contract. Owns the dark-first midnight room (the sanctioned §6 dark-room carve-out), the warm midnight ramp + crimson accent rank + survivor-state color layer, the OPEN/HELD/LOCKED/VERDICT state model, the Survivor voice for CFB H1s, the shipped `.cfb-*` component vocabulary (incl. `.championship-hero`, the `.cfb-verdict` family, the Commissioner's Desk admin register), the CFB-era lounge contract (C1), and CFB implementation guidance.
- **Golf**: `games/golf/DESIGN.md` (planned; authored in the ~Jan 2027 UI phase). Augusta Green + warm gold palette; tournament-rhythm primitives.
- **The Docket**: `games/docket/DESIGN.md` — the light court-paper room (bone substrate, WC/Golf family). Owns the law-book oxblood + stamp-garnet palette, the courtroom register (docket/case/verdict/mistrial/headliner), the `.docket-*` sheet primitives (rail, slot, side control, headliner, reserve, tiebreaker), and the frozen-number doctrine.

When working on a game's surfaces, treat the game-scoped file as authoritative for game-specific decisions; this top-level file remains authoritative for cross-game concerns (the palette framework, typography, elevation, motion, design laws). Tooling note: the stock impeccable loader emits only the top-level `PRODUCT.md`/`DESIGN.md` — it does **not** discover per-game files. The layering is enforced by the CLAUDE.md hard rule instead: read `games/<slug>/DESIGN.md` yourself, alongside this file, before producing design output (contract + history in `docs/per-game-design-doc-convention.md`).

## 1.6. Lounge and rooms

The platform's surface architecture has two registers; the distinction is by-design separation, not inconsistency:

- **The lounge** — platform home (`/`). The club's own dark surface: purple radial atmosphere, gold ceremony, the Commissioner's voice. It is dominated by whichever single game is currently live, but its identity is always the club's — a game's room palette never restyles the lounge substrate. Games enter the lounge through **content, copy, and state** (counts, deadlines, verdicts, signature summaries), never through their room's substrate or accent system.
- **The rooms** — each game's own body surfaces under `/<slug>/`, scoped by `body.game-<slug>`. A room carries specialized identity that may diverge hard from both the lounge and the other rooms (WC: Casual-Light bone body; CFB: dark-first midnight). Substrate contrast at the lounge↔room threshold is intentional — don't converge substrates (small handoff polish is fine).

A surface's home follows its depth: the lounge orients and summarizes; a room completes and operates. When placing a new surface, ask "lounge or room?" first — the answer decides its substrate, its palette authority (this file vs. the game's DESIGN.md), and how much of the game's accent system it may use.

## 2. Colors: The Commissioner's Club Palette

A two-color brand system (deep purple + ceremonial gold) on a warm bone neutral, with four per-game palettes layered selectively. Shadows tint with the purple. Live indicators are the only saturated reds and greens permitted; everything else routes through the brand's two-axis identity.

### Primary

The CCC purple ramp. Used for chrome (navbar, footer, page heroes), primary CTAs, and as the canonical brand surface.

- **Council Purple** (`#3A1D72`): the CCC signature purple. Navbar background, primary button fill, page-hero gradient terminus, eyebrow link color. The most-used brand color in the system.
- **Chamber Purple** (`#1C0A3A`): the deeper companion. Page-hero gradient origin, footer voice band, dark text on gold.
- **Tribunal Black** (`#140828`): the deepest purple, used on full-page atmospheric backdrops (auth pages, home shell). Effectively the system's "dark surface" without ever being literal black.
- **Press Purple** (`#6B3FAD`): the lighter purple, used for primary-button hover and as a brighter accent inside dark contexts.
- **Ink Purple** (`#0A0612`): a near-black purple used as ink for the deepest text on light surfaces. Never `#000`.

### Secondary

The CCC gold family. The trophy-case accent. Reserved for ceremonial moments (active nav state, primary CTA gradient, focus rings, masthead dividers).

- **Commish Gold** (`#C9A227`): the canonical brand gold. Active nav indicator, focus ring color, eyebrow text color, `--warning` semantic alias.
- **Trophy Light** (`#F2D36B`): the lighter gold. Hover states for gold elements, mid-stop in the metal-gold gradient.
- **Gold Dark** (`#8A6A1A`): the deeper gold. Anchor stop in the vertical `--metal-gold` gradient, link-hover color on auth pages.
- **Gold Dark Anchor** (`#A88420`): the diagonal `--metal-gold-flat` gradient's terminal stop. Lifted from `#8A6A1A` so chamber-purple text (`var(--purple-900)`) on the navbar `.btn-warning` clears WCAG AA 4.5:1 at the bottom-right pixel-corner where the 135° gradient terminates.
- **Gold Hi** (`#FFF1B8`): the highlight tone. Top stop in the metal-gold gradient (the chrome-y shimmer).

The two metal-gold gradients (`--metal-gold` for vertical, `--metal-gold-flat` for diagonal) are the literal trophy. They appear on primary CTAs (`btn-primary` on auth pages, navbar `btn-warning`) and nowhere else. The diagonal variant carries a slightly lifted dark stop (`#A88420` vs the vertical's `#8A6A1A`) so chamber-purple text clears AA at the gradient's worst-corner pixel — the diagonal's terminal sits exactly at the button's bottom-right corner where text descenders can land.

### Tertiary: Per-game Palettes

Each game blueprint adds a palette layered over the CCC chrome via a `body.game-<slug>` class. Game palettes override `--game-primary` / `--game-primary-dark` / `--game-primary-light` / `--game-accent` / `--game-accent-light`. Platform components like `.btn-game`, `.page-hero`, and `.stat-block` consume these slots automatically; game CSS must NOT duplicate.

- **Golf** (`body.game-golf`): Augusta Green (`#006747`) + warm gold (`#B8993E`). Tournament rhythm, season progression.
- **CFB** (`body.game-cfb`): Crimson (`#C5050C`) + a warm midnight ramp (canvas `#0E0A0C`) + bone accent. Survivor pressure, weekly spreads. CFB is the sanctioned dark-first room — it rebases the platform surface/text tokens onto its midnight ramp under `body.game-cfb`; full doctrine in `games/cfb/DESIGN.md`.
- **World Cup** (`body.game-worldcup`): Navy + Match Red (`#BF0A30`). Knockout urgency, multipliers. WC carries **two navies by construction**: the brand token `--wc-navy` (`#001A4D`, tokens.css — text/accent consumers) and the game-slot `--game-primary` (`#002868` — what platform components consume, echoed by literal `rgba(0,40,104,…)` tints). Both are frozen with the WC surfaces; don't "correct" one into the other. WC additionally specializes the accent rank (red primary, gold quaternary) and adds a team-tier color set — see `games/worldcup/DESIGN.md`.
- **The Docket** (`body.game-docket`): Law-book Oxblood (`#6E1F2E`) + Stamp Garnet (`#A63446`). Frozen-line pick'em on court paper; a light room (no token rebase). The wine family is deliberately darker and browner than CFB's signal crimson and WC's match red — don't brighten it toward either. Full ramp + register in `games/docket/DESIGN.md`.

### Neutral

The bone family. The pressroom paper. Default page background, light card text on dark surfaces, low-contrast utility text.

- **Pressroom Bone** (`#F3EFE6`): the warm off-white that backs every default page. Never `#fff`. Page background, dark-surface foreground.
- **Bone Dim** (`#D8D1BE`): the dimmer bone, used for secondary borders on light dark-mode auth cards.
- **Bone Mute** (`rgba(243, 239, 230, 0.55)`): muted bone for navbar inactive links, footer utility band.
- **Surface Card** (`#FFFFFF`): the only literal white in the system, used as card fill on light pages. Always nested inside a Pressroom Bone page.
- **Surface Muted** (`#EDEBF4`): a lavender-tinted muted gray for table heads and inactive zones.
- **Border Default** (`#D8DDE8`) / **Border Light** (`#E8E5F0`): the divider colors on light surfaces.
- **Text Ink** (`#1C1730`) / **Text Secondary** (`#5A5470`) / **Text Muted** (`#8A849B`): the three text shades for light surfaces. All carry a subtle purple tint, never neutral gray.

### Live and State

- **Live Red** (`#E63946`) / **Live Green** (`#64DBA0`) / **Live Orange** (`#FF8A3C`): live-game scoring and status. Reserved for live indicators, momentum arrows, deadline urgency. Never decorative.
- **Success** (`#1A7A45`) / **Danger** (`#C0392B`) / **Info** (`#3B5998`): semantic state for forms, alerts, and admin flash messages. Always paired with a tinted background (`--success-bg`, `--danger-bg`, `--info-bg`) and a leading icon, never color alone.

### Named Rules

**The Trophy Rule.** The metal-gold gradients (`--metal-gold` / `--metal-gold-flat`) are reserved for primary CTAs and the active navbar button. Gold gradients on cards, page backgrounds, badges, or decorative chrome dilute the trophy. If you find yourself reaching for `--metal-gold` on a non-CTA surface, you want a flat gold (`--gold` or `--gold-light`) or no gold at all.

**The Two-Color Rule.** CCC is purple plus gold on bone. Game tertiaries (Golf green, CFB crimson, WC navy/red, Docket oxblood/garnet) layer **only** when the surface is scoped under a `body.game-<slug>` class. A platform-chrome surface that introduces a third color outside the CCC duo without that scoping is a design failure.

**The No-Pure-White Rule.** The page background is Pressroom Bone (`#F3EFE6`), not white. The literal white (`#FFFFFF`) is reserved for `.card` interiors nested on bone. The body of a CCC page should never read as a white SaaS surface.

**The Tinted-Neutral Rule.** All text colors and all gray-feeling utility colors carry a subtle purple cast (look at `text-ink #1C1730` versus a neutral `#1F1F1F`). Don't introduce neutrally-gray text or neutrally-gray dividers; pull them toward the purple family.

## 3. Typography

**Display Font:** Teko (with `sans-serif` fallback). Condensed, geometric, broadcast-sport energy. Loaded weights 400 / 500 / 600 / 700.

**Body Font:** Newsreader (with `Georgia, serif` fallback). Editorial transitional serif with optical sizing. Loaded weights 300 / 400 / 500 / 600 plus italic 400.

**Character:** Teko is the masthead voice; Newsreader is the editorial paragraph. Together they read as a sports paper printed for a private subscriber list. There is no third font in the system.

### Hierarchy

- **Display** (Teko 600, `2.4rem`, line-height `1.1`, letter-spacing `0.03em`): page-level h1, hero mastheads. The largest type on any page. Per-game surfaces may apply a **Tribune voice** rule to H1s that converts functional chrome labels into editorial section names; the World Cup register codifies this in `games/worldcup/DESIGN.md`. Two dispensations carry across games: (a) dynamic H1s that interpolate a noun (`{{ team.name }}` / `{{ current_user.get_display_name() }}`) read functionally because the value carries the voice; (b) the logged-in utility auth register (§5 Auth Surface Composition) keeps functional H1s because the Tribune voice carries through the eyebrow + Newsreader copy inside the card.
- **Headline** (Teko 600, `1.9rem`, line-height `1.1`): section h2, admin page titles (`2.25rem` variant on admin pages).
- **Title** (Teko 600, `1.5rem`, line-height `1.1`): card-header level h3, table sub-heads.
- **Body** (Newsreader 400, `1rem`, line-height `1.65`): paragraphs, list items, default text. Cap line length at 65 to 75 characters per line. The `≥16px` body floor applies to body text and primary read-targets; explicit caption/metadata classes may step down to `≥0.75rem` (12px) when the primary read-target on the same row carries the dominant hierarchy — captions report, they don't lead. (Each game's `DESIGN.md` lists its sanctioned caption classes; WC's are in `games/worldcup/DESIGN.md` §3.)
- **Label** (Teko 500, `0.9rem`, letter-spacing `0.06em`, uppercase): form labels, tab labels, eyebrow-style metadata.
- **Eyebrow** — the platform foundation defines one primitive; games may add their own variants:
    - **`.admin-eyebrow`** (Teko 500, `0.85rem`, letter-spacing `0.14em`, uppercase, `var(--gold)`): the bone-canvas admin masthead label. One color, one size.
    - Per-game eyebrow primitives (e.g., the World Cup `.wc-eyebrow` with its `-red` / `-gold` tonal variants and bone-mute default calibrated for navy substrates) are documented in the game's own `DESIGN.md`. New games adopt the same "one default + tonal variants" shape rather than inventing parallel "kicker" patterns.

### Named Rules

**The Newsroom Rule.** Every heading is Teko. Every paragraph is Newsreader. The two fonts never mix mid-sentence. If a heading reads in serif, you've broken the masthead. If a paragraph reads in condensed sans, you've broken the editorial.

**The Eyebrow Rule.** When a section needs context above its headline (category, game name, status), reach for an Eyebrow primitive — `.admin-eyebrow` on admin pages (the platform default), or the per-game variant documented in the game's `DESIGN.md` (e.g., `.wc-eyebrow` on World Cup surfaces). Don't invent a new "kicker" or "subhead" pattern.

**The Uppercase Rule.** Uppercase is for Teko (labels, eyebrows, button text, table heads, navbar links). Newsreader is never uppercased. Mixing is a slop signal.

**The Line-Length Rule.** Newsreader paragraphs cap at 65 to 75 ch. Wider paragraphs read as a wall of text and lose the editorial register.

**The Ramp Rule.** The six roles above name the canonical voices; the frontmatter's `typography.scale` enumerates every size step the platform and its game rooms are allowed to use. A size that isn't on the ramp is drift, not a new step, and the mechanical detector reports it as such. If a surface genuinely needs a step the ramp lacks, add it to the frontmatter deliberately rather than letting the value land loose in `style.css`. The same applies to `rounded` for corner radii.

## 4. Elevation

**Tinted ambient lift.** Cards rest with a subtle purple-tinted shadow at all times. On hover or focus, they lift to a stronger purple shadow with a slight cubic-bezier overshoot. Gold CTAs cast a gold-tinted glow on hover. Shadows always carry brand color, never neutral gray. The home and auth surfaces add radial gradient atmospheres on top of (not in place of) tinted shadows.

### Shadow Vocabulary

- **`--shadow-sm`** (`0 2px 8px rgba(58, 29, 114, 0.07)`): card resting state, subtle hover for interactive list items. Always present on cards by default.
- **`--shadow-md`** (`0 4px 20px rgba(58, 29, 114, 0.12)`): card hover state. Lift when an interactive surface acknowledges intent.
- **`--shadow-lg`** (`0 8px 40px rgba(58, 29, 114, 0.17)`): auth cards, modals, the substantial substrates that carry critical flows. Used at rest, not as a hover lift.
- **`--shadow-gold`** (`0 4px 24px rgba(201, 162, 39, 0.25)`): gold CTA hover glow. The literal trophy glint. Reserved for `.btn-warning:hover` and equivalent primary-CTA hover states.
- **`--shadow-lift-strong`** (`0 6px 20px rgba(58, 29, 114, 0.30)`): a heavier hover lift than `--shadow-md`, for surfaces that need stronger acknowledgment.
- **`--shadow-navbar`** (`0 2px 20px rgba(58, 29, 114, 0.35)`): sticky navbar ambient.
- **`--shadow-dropdown`** (`0 12px 40px rgba(58, 29, 114, 0.50)`): dropdown panels — a genuine overlay layer, cast harder.
- **`--shadow-sticky-up`** (`0 -4px 20px rgba(58, 29, 114, 0.35)`): bottom-anchored bars (upward cast).
- **`--shadow-btn-primary-hover`** (`0 4px 14px rgba(58, 29, 114, 0.30)`): the Quiet-primary CTA hover (consumed by §5 Buttons).

New elevated surfaces consume a token from this scale — never a fresh `rgba(...)` literal; an undocumented shadow literal is how the scale rots. (CFB neutralizes this scale to warm near-black inside its dark room — see `games/cfb/DESIGN.md` §6.)

### Card Hover Curve

`.card` uses `cubic-bezier(0.34, 1.56, 0.64, 1)` for the `transform` portion of its hover transition. The slight overshoot (the `1.56` peak) is deliberate; it gives the lift a small flick of confidence rather than a flat slide. The shadow uses standard `cubic-bezier(0.4, 0, 0.2, 1)` (`--transition`) on the same hover.

### Named Rules

**The Press-Room Shadow Rule.** All shadows tint with brand purple (or gold on CTA-hover). Neutral-gray shadows are slop and break the press-room atmosphere. Never use `rgba(0, 0, 0, ...)` directly; always tint toward `rgba(58, 29, 114, ...)` or `rgba(201, 162, 39, ...)`.

**The Lift-At-Rest Rule.** Cards lift slightly (`--shadow-sm`) at rest, harder on hover (`--shadow-md`). Flat-at-rest is the wrong elevation philosophy for CCC; the Tribune is a printed object, not a wireframe.

**The Atmospheric-Layer Rule.** When a surface needs more than a card-level shadow (auth backdrops, home shells), add a radial gradient atmosphere (e.g., `radial-gradient(ellipse at top, var(--purple-900) 0%, var(--purple-950) 60%)`) on top of, not in place of, the tinted shadow scale.

## 5. Components

### Buttons

CCC has three button registers: Quiet (purple primary, the default), Loud Trophy (metal-gold gradient, the ceremonial CTA), and Game (game-aware, scoped under `body.game-<slug>`).

- **Shape:** `--radius` (`0.5rem`, ~8px). Modest rounding; never pill-shaped, never sharp-square.
- **Type:** `Teko 500`, uppercase, letter-spacing `0.08em` on the navbar variant. Body text on standard `.btn-primary`.
- **Primary (Quiet)** (`.btn-primary`): `var(--platform-primary)` (Council Purple) fill, `var(--text-on-dark)` (Pressroom Bone) text. Hover: lift `translateY(-2px)`, `--shadow-btn-primary-hover`, fill brightens to `var(--platform-primary-light)` (Press Purple).
- **Trophy (Loud)** (`.btn-warning` on navbar; `body.auth-page .btn-primary`): `--metal-gold-flat` gradient fill, `var(--purple-900)` (Chamber Purple) text. Hover: `filter: brightness(1.05)` plus `--shadow-gold` glow. The ceremonial CTA. Reserved.
- **Game-aware** (`.btn-game`): `var(--game-primary)` fill, bone text. The game-blueprint primary; per-game palettes override automatically via `body.game-<slug>`. Hover lifts `-2px`.
- **Outline Primary** / **Outline Secondary**: `1.5px` border, transparent fill. Hover fills the border color. Use for secondary actions.

### Cards

The platform foundation defines one card register — the default light Tribune card — plus the home-shell ceremonial / informational recipes below. Games may add their own card primitives (e.g., the World Cup `.wc-stat-card` reference and the `.wc-champion-banner` ceremonial dark surface); those primitives are documented in the game's `DESIGN.md`.

- **Default** (`.card`): `var(--bg-card)` (white) fill on a Pressroom Bone page, `--radius-lg` (`0.875rem`, ~14px) corner radius, `1px solid var(--border)` border, `--shadow-sm` at rest, `--shadow-md` on hover with `translateY(-3px)` lift (cubic-bezier overshoot).
- **Card Header** (`.card-header`): transparent fill, `1px solid var(--border)` bottom border, Teko 600 uppercase title.
- **Game Card** (`.game-card`): default card with a `3px solid var(--platform-accent)` (gold) top border. Used on the home page game grid.

#### Card recipes inside `.home-shell`

The home shell is a dark editorial surface (purple radial atmosphere), not the bone page. Its panels split into two registers; a returning user should be able to predict, from the silhouette alone, whether a card is a ceremonial CTA or an informational fixture.

- **Ceremonial** (`.decree`, `.cta-card--join`, `.cta-card--seal`): `linear-gradient(180deg, var(--purple-800), var(--purple-900))` + `1px solid rgba(201, 162, 39, 0.3)` + `border-radius: 14px`. Optional dashed-gold internal rules separate multi-band layouts (`.decree-seal` border-bottom). Used for time-sensitive moments: the countdown decree, the join-pool CTA, the seal-your-roster CTA. The gold-30% border is the visual contract; it tells a returning user "this asks something of you before a deadline."
- **Informational** (`.match-card`, `.cta-card--view`, `.commish-note-body`): `linear-gradient(180deg, var(--purple-850), var(--purple-950))` + `1px solid rgba(243, 239, 230, 0.08)` + `border-radius: 12px`. The bone-opacity-8 border reads as the standing-affordance baseline (fixtures, the view-only dossier shell, the Commish's Note long-form). It carries no deadline pressure; the recipe says "this is the record, look as long as you want." `.commish-note-body` adds the §6 Do canonical `border-top: 2px solid var(--gold)` major-section separator on top of the Informational recipe — a documented variant for editorial long-form, not a third register.

The two recipes are non-overlapping by construction — a new home-shell panel picks one, not both. Two single-instance hero silhouettes layer on top of the two-tier system: `.ballot-card` (green-tinted "sealed" state on the pre-state ballot, a third narrower register) and `.dossier` (live-state standing hero — Ceremonial recipe with an extended `purple-800 → purple-950` gradient terminus for the live hero's gravitas; same `1px solid rgba(201, 162, 39, 0.3)` + 14px radius as Ceremonial). Both are locked to a single surface; do not duplicate the silhouette onto a new card.

Scope note: the Ceremonial/Informational recipe pair is **platform lounge vocabulary** — any featured game's lounge modules pick one of the two registers (a CFB summons that asks something before a deadline is Ceremonial; a CFB verdict record is Informational). The current consumers (`.decree`, `.ballot-card`, `.dossier`, `.match-card`, the CTA cards) are the WC-era lounge partials; the transition plan §5 moves them into a per-game WC lounge module at the CFB changeover. The recipes stay; the consumers are era-specific.

### Form Controls

- **Style:** `1.5px solid var(--border)` border, `--radius` corners, `var(--bg-card)` fill, `Newsreader 400` body type, `0.6rem 0.9rem` padding, `min-height: 44px` (touch-friendly, the floor).
- **Focus:** border shifts to `var(--platform-accent)` (Commish Gold), plus a `0 0 0 3px rgba(212, 168, 32, 0.18)` gold glow. The trophy whisper applied to interaction.
- **Label** (`.form-label`): Teko 500, `0.9rem`, uppercase, letter-spacing `0.06em`, `var(--text-muted)`. Sits tight against the control (`margin-bottom: 0.3rem`).
- **Disabled:** `var(--bg-muted)` fill, `var(--text-muted)` text.

### Navigation

- **Navbar** (`.navbar.navbar-dark`): `var(--purple-700)` (Council Purple) fill, `1px solid var(--purple-800)` bottom border. The dark editorial chrome that anchors every page.
- **Brand** (`.navbar-brand`): Teko 700, `1.25rem`, uppercase, letter-spacing `0.04em`, Pressroom Bone color, with brand mark image at 28px. The full lockup (head mark + bone wordmark) renders at every width; only ≤350px does the wordmark yield to the head mark alone. Hover does not shift color: the brand wordmark is a masthead, not a CTA, so the Trophy Rule keeps gold off it (no color hover, no gold halo). Cursor change carries the affordance.
- **Nav Link**: Teko, uppercase, letter-spacing `0.08em`, `var(--bone-mute)` color at rest. Hover brightens to `var(--gold-light)`. Active goes `var(--gold)` with a `2px solid var(--gold)` underline rule beneath. Keyboard focus paints a `2px solid var(--gold-light)` outline with `2px` offset (the canonical CCC focus ring) so keyboard users see the same target the mouse does.
- **Solo-Game Hoist** (`.navbar-solo-game`): when a member is joined to exactly one game, that game's switcher link sits in the bar itself below `lg` (right-aligned beside the toggler, 44px touch floor) instead of inside the hamburger; its collapse copy hides below `lg` so the link renders once per breakpoint. Same nav-link voice — no pill, no extra chrome. With 0 or 2+ joined games the switcher lives in the collapse as usual.
- **Game Sub-nav** (per blueprint, e.g. `.game-subnav .subnav-worldcup`): a horizontal pill bar that sits under the navbar, scoped per game. The active pill carries the game's accent color via `--subnav-accent` plus its RGB triplet for translucent backgrounds. Each game must register its own `.subnav-<slug>` class with `background`, `--subnav-accent`, and `--subnav-accent-rgb`. The container is a semantic `<nav>` with `aria-label="<Game> section"` so screen-reader users hear the game context when the inline `.subnav-game-label` text is hidden on mobile. Pills carry the same `2px gold-light` keyboard-focus ring as nav-links.

### Auth Surface Composition

CCC auth surfaces split into two registers. The split is intentional: marketing-context surfaces serve users who haven't joined the Club yet (or are returning to it) and earn the brand re-introduction; logged-in utility surfaces serve members who are already inside the Club and just need the form.

- **Marketing-context (`.auth-page > .auth-panel-brand + .auth-form-panel`)**: split panel. Brand panel on the left at `md+` (council-purple gradient, brand mark, headline, games preview); form panel on the right (bone card on the Tribunal Black backdrop). Used by `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`. The brand panel collapses on `<768px`; the form panel goes transparent so the body radial gradient bleeds through (`body.auth-page main` centers the card on the atmosphere).
- **Logged-in utility (`.auth-wrapper > .card.auth-card`)**: single bone card centered on the Tribunal Black backdrop, no brand panel. The Tribune voice carries through the eyebrow and copy inside the card. Used by `change_password.html` and `profile.html`. Both surfaces are reached through the navbar dropdown after login; the brand re-introduction would be redundant.

Both registers share `body.auth-page` (the Tribunal Black radial-gradient backdrop) and `.card.auth-card` (the bone card primitive). The split is purely the wrapper: marketing surfaces wrap with `.auth-page > .auth-panel-brand + .auth-form-panel`; utility surfaces wrap with `.auth-wrapper`. A new auth surface picks one register and never both.

### Tables

- **Header** (`.table thead th`): Teko 500, `0.88rem`, uppercase, letter-spacing `0.07em`, `var(--text-muted)` text on `var(--bg-muted)` fill, `2px solid var(--border)` bottom rule.
- **Row hover**: `var(--bg-muted)` fill on `0.15s` transition.
- **Cell typography**: Newsreader, `0.92rem` (`.table` opt-in size).
- **Current-user row** (`.row-current-user`): tint-only highlight — the platform fallback is a gold tint; game tables override the tint color only (CFB crimson, WC red — red per the WC accent rank). Never a side-stripe (the last one, Golf's, was removed 2026-07-20). The highlight is the user's own line in the standings; it should be subtle, not loud.

### Per-game primitives

Games define their own primitives for surfaces and patterns specific to that game (tier indicators, ceremonial slots, sub-nav accents, etc.). See each game's `DESIGN.md` — World Cup at `games/worldcup/DESIGN.md` codifies the three-primitive tier trio (`.wc-tier-dot` / `.tier-badge` / `.wc-multiplier-chip`), the `.wc-stat-card` Casual-Light reference, the `.wc-champion-banner` ceremonial dark surface, and the `.wc-eyebrow` variants.

### Eyebrow and Label Primitives

- **Eyebrow** — see §3 for the platform-foundation primitive. Quick reference:
    - **`.admin-eyebrow`**: Teko 500, `0.85rem`, `0.14em`, uppercase, `var(--gold)`. Admin masthead label on bone canvas.
    - Per-game eyebrow variants are documented in the game's own `DESIGN.md` (e.g., the WC `.wc-eyebrow` with its `-red` / `-gold` tonal variants).
    
    Reuse the matching primitive for any new section that needs a category label (game name, week, deadline, status). Don't invent a new "kicker" pattern.
- **Form Label**: see Form Controls above.

### Live Indicators

- **Live dot**: `0.5rem × 0.5rem` circle, `var(--live-red)` for in-progress games, `var(--live-green)` for completed wins, `var(--live-orange)` for warnings or attention. Always paired with text (e.g., "Live", "Final", "Locked"), never color alone.
- **Lives indicator** (CFB Survivor `.lives-indicator`): inline row of filled/hollow dots, one per remaining life. Filled = active; hollow = lost.

### Page Hero

- **`.page-hero`**: linear gradient from `var(--game-primary-dark)` to `var(--game-primary)` at `135deg`, `var(--text-on-dark)` text, `3.5rem 0 3rem` vertical padding, halftone-dot pattern overlay (`radial-gradient(circle, rgba(212, 168, 32, 0.06) 1px, transparent 1px)` at `24px` tile). The masthead band that opens game pages. Game palettes flow through automatically.
- Game-specific hero variants follow the `.page-hero.<game>-hero-grad` shape (e.g., World Cup's `.page-hero.wc-hero-grad` navy-+-red gradient documented in `games/worldcup/DESIGN.md`).

## 6. Do's and Don'ts

Concrete guardrails. Each is forceful on purpose; the design director is in the room.

### Do:

- **Do** open every primary page with a Teko-display masthead, not a navbar that flows directly into content.
- **Do** use Teko for every heading, eyebrow, button label, table head, and navbar link.
- **Do** use Newsreader for every paragraph, body text, list item, and editorial caption.
- **Do** reserve the metal-gold gradients (`--metal-gold` / `--metal-gold-flat`) for primary CTAs and the active navbar button. Nothing else.
- **Do** use the brand-tinted shadow scale (`--shadow-sm/md/lg/gold`) on every elevated surface. Cards lift slightly at rest, harder on hover.
- **Do** scope every non-platform color through a `body.game-<slug>` class. Game palettes layer on the chrome; they never replace it.
- **Do** use Pressroom Bone (`#F3EFE6`) as the page background. White (`#FFFFFF`) is for nested cards only.
- **Do** apply gold dividers (`border-top: 2px solid var(--gold)`) between major page sections when separation is needed, not colored side-stripes on cards.
- **Do** scope any light-foreground overrides needed on a game's dark-substrate primitive to that surface (e.g., `.wc-champion-banner .text-muted`). Bootstrap defaults will read black-on-dark without it; broadcasting `tbody td { color: light }` globally breaks the masked-by-Bootstrap rows on every other surface.
- **Do** keep button and form min-height at 44px or larger (mobile-first touch floor).
- **Do** cap Newsreader paragraph line length at 65 to 75 ch.
- **Do** carry the Eyebrow primitive (Teko 500, 0.85rem, 0.14em letter-spacing, gold, uppercase) above section headlines that need contextual labeling.

### Don't:

- **Don't** use `border-left`/`border-right` greater than 1px as a colored accent on cards, list items, callouts, alerts, or table rows. The settled platform alternatives: state cards use a full `1px` border plus a 5–6% background tint (the `.card.border-success` / `-danger` / `-warning` / `-primary` rules already follow this shape), and current-user table rows use a background tint only (the last stripe, Golf's, was removed 2026-07-20). Structural gridlines (e.g., `.col-divider` between table column groups) are separators, not accents, and are exempt.
- **Don't** apply `background-clip: text` plus a gradient background (gradient text). The metal-gold gradient is for surfaces, never for type.
- **Don't** use `#000` or `#fff` as text or background colors. Tint every neutral toward the brand purple; chroma 0.005 to 0.01 is enough.
- **Don't** use Inter, system-ui, or any other font. Teko and Newsreader define the system; a third font is a regression.
- **Don't** use neutral-gray shadows. CCC shadows are purple-tinted by design; replacing them with `rgba(0, 0, 0, ...)` breaks the press-room atmosphere.
- **Don't** apply `--metal-gold` outside primary-CTA contexts. It is the trophy; decorating with it dilutes it.
- **Don't** introduce repeating identical card grids (icon + heading + text, same size, eight in a row). PRODUCT.md flags this as an anti-reference under "generic SaaS dashboards."
- **Don't** apply the hero-metric template (big number + small label + supporting stats + gradient accent) without justification. Listed in shared design laws as an absolute ban for SaaS cliches.
- **Don't** add a third top-level color outside CCC purple plus gold without scoping it under a game class. WC navy/red, CFB crimson, Golf green only ever appear on `body.game-worldcup` / `body.game-cfb` / `body.game-golf` surfaces.
- **Don't** use `match.stage|title` in Jinja templates. Use the `stage_label` SSoT helper. (Documented gotcha in `CLAUDE.md`; surfaces as a typography slip.)
- **Don't** mock dark mode on light surfaces. The auth pages (Tribunal Black backdrop) plus each game's named ceremonial dark primitive (e.g., the World Cup `.wc-champion-banner`) are the platform-default first-party dark surfaces; otherwise bone-on-light is the default. **Carve-out:** a game may establish a *dark room* as its entire body substrate when its `games/<slug>/DESIGN.md` documents the choice and scopes it under `body.game-<slug>` only (never a global dark mode) — e.g., CFB Survivor's warm-midnight room (`games/cfb/DESIGN.md`). What stays banned is an *undocumented* third dark register. New game-scoped dark primitives, or a documented dark room, belong in the game's `DESIGN.md`.
- **Don't** use bounce or elastic easing on motion. Card hover is the only deliberately overshooting curve in the system; everywhere else, ease out with `cubic-bezier(0.4, 0, 0.2, 1)` or steeper exponential curves.
- **Don't** use em dashes (`—`) or double hyphens (`--`) in UI copy, error messages, button labels, or any prose generated for CCC surfaces. Replace with commas, colons, semicolons, periods, or parentheses. (Carried from PRODUCT.md's Copy Discipline.)
- **Don't** add a navbar item beyond the joined-games list plus auth links. PRODUCT.md flags "navigation overload" as an ESPN/Yahoo anti-reference.
- **Don't** introduce a "Powered by" footer, trust badges, marketing-style hero aimed at strangers, or any platform signal. The site belongs to the club, not to a vendor. PRODUCT.md design principle #1.
