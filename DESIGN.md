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
  # Per-game tertiary palettes (consumed via body.game-<slug> overrides of --game-primary / --game-accent)
  golf-green: "#006747"
  golf-gold: "#B8993E"
  cfb-crimson: "#C5050C"
  cfb-midnight: "#0F0F1A"
  wc-navy: "#002868"
  wc-red: "#BF0A30"
  wc-card-navy: "#001A4DCC"
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
rounded:
  sm: "0.5rem"
  lg: "0.875rem"
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
  card-tribune-dark:
    backgroundColor: "{colors.wc-card-navy}"
    textColor: "{colors.pressroom-bone}"
    rounded: "{rounded.sm}"
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
- Three game palettes layered over CCC chrome via `body.game-<slug>` overrides
- Newsreader serif paragraphs, Teko condensed-sans headlines, no third font

The system explicitly rejects: ESPN/Yahoo fantasy chrome (banner ads, untiered tables, navigation overload); generic SaaS dashboards (Inter on gray-on-white, hero-metric template, identical card grids); Bootstrap-starter regression (stock `.card`, unscoped `.btn-primary`, default navbar); crypto/Web3 aesthetic (neon-on-black, glassmorphism); generic sports skeuomorphism (stadium textures, scoreboard fonts).

## 2. Colors: The Commissioner's Club Palette

A two-color brand system (deep purple + ceremonial gold) on a warm bone neutral, with three per-game palettes layered selectively. Shadows tint with the purple. Live indicators are the only saturated reds and greens permitted; everything else routes through the brand's two-axis identity.

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
- **Gold Dark** (`#8A6A1A`): the deeper gold. Anchor stop in the metal-gold gradient, link-hover color on auth pages.
- **Gold Hi** (`#FFF1B8`): the highlight tone. Top stop in the metal-gold gradient (the chrome-y shimmer).

The two metal-gold gradients (`--metal-gold` for vertical, `--metal-gold-flat` for diagonal) are the literal trophy. They appear on primary CTAs (`btn-primary` on auth pages, navbar `btn-warning`) and nowhere else.

### Tertiary: Per-game Palettes

Each game blueprint adds a palette layered over the CCC chrome via a `body.game-<slug>` class. Game palettes override `--game-primary` / `--game-primary-dark` / `--game-primary-light` / `--game-accent` / `--game-accent-light`. Platform components like `.btn-game`, `.page-hero`, and `.stat-block` consume these slots automatically; game CSS must NOT duplicate.

- **Golf** (`body.game-golf`): Augusta Green (`#006747`) + warm gold (`#B8993E`). Tournament rhythm, season progression.
- **CFB** (`body.game-cfb`): Crimson (`#C5050C`) + Midnight (`#0F0F1A`) + white accent. Survivor pressure, weekly spreads.
- **World Cup** (`body.game-worldcup`): Navy (`#002868`) + Match Red (`#BF0A30`). Knockout urgency, multipliers. WC also defines a 5-tier color set for team tiers (`--wc-tier1` through `--wc-tier5`); these are scoped utilities, not part of the platform palette.

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

**The Two-Color Rule.** CCC is purple plus gold on bone. Game tertiaries (Golf green, CFB crimson, WC navy/red) layer **only** when the surface is scoped under a `body.game-<slug>` class. A platform-chrome surface that introduces a third color outside the CCC duo without that scoping is a design failure.

**The No-Pure-White Rule.** The page background is Pressroom Bone (`#F3EFE6`), not white. The literal white (`#FFFFFF`) is reserved for `.card` interiors nested on bone. The body of a CCC page should never read as a white SaaS surface.

**The Tinted-Neutral Rule.** All text colors and all gray-feeling utility colors carry a subtle purple cast (look at `text-ink #1C1730` versus a neutral `#1F1F1F`). Don't introduce neutrally-gray text or neutrally-gray dividers; pull them toward the purple family.

## 3. Typography

**Display Font:** Teko (with `sans-serif` fallback). Condensed, geometric, broadcast-sport energy. Loaded weights 400 / 500 / 600 / 700.

**Body Font:** Newsreader (with `Georgia, serif` fallback). Editorial transitional serif with optical sizing. Loaded weights 300 / 400 / 500 / 600 plus italic 400.

**Character:** Teko is the masthead voice; Newsreader is the editorial paragraph. Together they read as a sports paper printed for a private subscriber list. There is no third font in the system.

### Hierarchy

- **Display** (Teko 600, `2.4rem`, line-height `1.1`, letter-spacing `0.03em`): page-level h1, hero mastheads. The largest type on any page.
- **Headline** (Teko 600, `1.9rem`, line-height `1.1`): section h2, admin page titles (`2.25rem` variant on admin pages).
- **Title** (Teko 600, `1.5rem`, line-height `1.1`): card-header level h3, table sub-heads.
- **Body** (Newsreader 400, `1rem`, line-height `1.65`): paragraphs, list items, default text. Cap line length at 65 to 75 characters per line.
- **Label** (Teko 500, `0.9rem`, letter-spacing `0.06em`, uppercase): form labels, tab labels, eyebrow-style metadata.
- **Eyebrow** (Teko 500, `0.85rem`, letter-spacing `0.14em`, uppercase, gold): the small uppercase line above section headers (`.admin-eyebrow`, `.wc-eyebrow`). Signature CCC primitive; reuse it generously on game-specific section heads.

### Named Rules

**The Newsroom Rule.** Every heading is Teko. Every paragraph is Newsreader. The two fonts never mix mid-sentence. If a heading reads in serif, you've broken the masthead. If a paragraph reads in condensed sans, you've broken the editorial.

**The Eyebrow Rule.** When a section needs context above its headline (category, game name, status), use the Eyebrow primitive: Teko 500, `0.85rem`, uppercase, letter-spacing `0.14em`, color `--gold`. Don't invent a new "kicker" or "subhead" pattern.

**The Uppercase Rule.** Uppercase is for Teko (labels, eyebrows, button text, table heads, navbar links). Newsreader is never uppercased. Mixing is a slop signal.

**The Line-Length Rule.** Newsreader paragraphs cap at 65 to 75 ch. Wider paragraphs read as a wall of text and lose the editorial register.

## 4. Elevation

**Tinted ambient lift.** Cards rest with a subtle purple-tinted shadow at all times. On hover or focus, they lift to a stronger purple shadow with a slight cubic-bezier overshoot. Gold CTAs cast a gold-tinted glow on hover. Shadows always carry brand color, never neutral gray. The home and auth surfaces add radial gradient atmospheres on top of (not in place of) tinted shadows.

### Shadow Vocabulary

- **`--shadow-sm`** (`0 2px 8px rgba(58, 29, 114, 0.07)`): card resting state, subtle hover for interactive list items. Always present on cards by default.
- **`--shadow-md`** (`0 4px 20px rgba(58, 29, 114, 0.12)`): card hover state. Lift when an interactive surface acknowledges intent.
- **`--shadow-lg`** (`0 8px 40px rgba(58, 29, 114, 0.17)`): auth cards, modals, the substantial substrates that carry critical flows. Used at rest, not as a hover lift.
- **`--shadow-gold`** (`0 4px 24px rgba(201, 162, 39, 0.25)`): gold CTA hover glow. The literal trophy glint. Reserved for `.btn-warning:hover` and equivalent primary-CTA hover states.

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
- **Primary (Quiet)** (`.btn-primary`): `var(--platform-primary)` (Council Purple) fill, `var(--text-on-dark)` (Pressroom Bone) text. Hover: lift `translateY(-2px)`, shadow `0 4px 14px rgba(58, 29, 114, 0.3)`, fill brightens to `var(--platform-primary-light)` (Press Purple).
- **Trophy (Loud)** (`.btn-warning` on navbar; `body.auth-page .btn-primary`): `--metal-gold-flat` gradient fill, `var(--purple-900)` (Chamber Purple) text. Hover: `filter: brightness(1.05)` plus `--shadow-gold` glow. The ceremonial CTA. Reserved.
- **Game-aware** (`.btn-game`): `var(--game-primary)` fill, bone text. The game-blueprint primary; per-game palettes override automatically via `body.game-<slug>`. Hover lifts `-2px`.
- **Outline Primary** / **Outline Secondary**: `1.5px` border, transparent fill. Hover fills the border color. Use for secondary actions.

### Cards

Two card registers: the default light Tribune card and the dark Tribune-Dark card (used inside World Cup surfaces).

- **Default** (`.card`): `var(--bg-card)` (white) fill on a Pressroom Bone page, `--radius-lg` (`0.875rem`, ~14px) corner radius, `1px solid var(--border)` border, `--shadow-sm` at rest, `--shadow-md` on hover with `translateY(-3px)` lift (cubic-bezier overshoot).
- **Tribune-Dark** (`.card.wc-card`): `rgba(0, 17, 46, 0.8)` (WC Card Navy) fill, `1px solid rgba(245, 241, 232, 0.08)` border, `--radius` (~8px) corner radius, `1rem` padding. Hover brightens border to `rgba(242, 211, 107, 0.25)` (gold whisper). Used wherever the World Cup surface needs to break the bone-page register and feel like a knockout match. Any content layered on this surface must explicitly carry a light foreground color, scoped to the surface (don't broadcast `tbody td { color: light }` globally; it breaks Bootstrap-default rows).
- **Card Header** (`.card-header`): transparent fill, `1px solid var(--border)` bottom border, Teko 600 uppercase title.
- **Game Card** (`.game-card`): default card with a `3px solid var(--platform-accent)` (gold) top border. Used on the home page game grid.

### Form Controls

- **Style:** `1.5px solid var(--border)` border, `--radius` corners, `var(--bg-card)` fill, `Newsreader 400` body type, `0.6rem 0.9rem` padding, `min-height: 44px` (touch-friendly, the floor).
- **Focus:** border shifts to `var(--platform-accent)` (Commish Gold), plus a `0 0 0 3px rgba(212, 168, 32, 0.18)` gold glow. The trophy whisper applied to interaction.
- **Label** (`.form-label`): Teko 500, `0.9rem`, uppercase, letter-spacing `0.06em`, `var(--text-muted)`. Sits tight against the control (`margin-bottom: 0.3rem`).
- **Disabled:** `var(--bg-muted)` fill, `var(--text-muted)` text.

### Navigation

- **Navbar** (`.navbar.navbar-dark`): `var(--purple-700)` (Council Purple) fill, `1px solid var(--purple-800)` bottom border. The dark editorial chrome that anchors every page.
- **Brand** (`.navbar-brand`): Teko `1.25rem`, letter-spacing `0.04em`, Pressroom Bone color, with brand mark image at 28px.
- **Nav Link**: Teko, uppercase, letter-spacing `0.08em`, `var(--bone-mute)` color at rest. Hover brightens to `var(--gold-light)`. Active goes `var(--gold)` with a `2px solid var(--gold)` underline rule beneath.
- **Game Sub-nav** (per blueprint, e.g. `.game-subnav .subnav-worldcup`): a horizontal pill bar that sits under the navbar, scoped per game. The active pill carries the game's accent color via `--subnav-accent` plus its RGB triplet for translucent backgrounds. Each game must register its own `.subnav-<slug>` class with `background`, `--subnav-accent`, and `--subnav-accent-rgb`.

### Tables

- **Header** (`.table thead th`): Teko 500, `0.88rem`, uppercase, letter-spacing `0.07em`, `var(--text-muted)` text on `var(--bg-muted)` fill, `2px solid var(--border)` bottom rule.
- **Row hover**: `var(--bg-muted)` fill on `0.15s` transition.
- **Cell typography**: Newsreader, `0.92rem` (`.table` opt-in size).
- **Current-user row** (`.row-current-user`): tinted highlight scoped per game (CFB uses crimson tint, WC uses gold tint). The highlight is the user's own line in the standings; it should be subtle, not loud.

### Eyebrow and Label Primitives

- **Eyebrow** (`.admin-eyebrow`, `.wc-eyebrow`, etc.): Teko 500, `0.85rem`, letter-spacing `0.14em`, uppercase, `var(--gold)`. The small contextual label that sits above section headlines. Reuse this for any new section that needs a category label (game name, week, deadline, status). Don't invent a new "kicker" pattern.
- **Form Label**: see Form Controls above.

### Live Indicators

- **Live dot**: `0.5rem × 0.5rem` circle, `var(--live-red)` for in-progress games, `var(--live-green)` for completed wins, `var(--live-orange)` for warnings or attention. Always paired with text (e.g., "Live", "Final", "Locked"), never color alone.
- **Lives indicator** (CFB Survivor `.lives-indicator`): inline row of filled/hollow dots, one per remaining life. Filled = active; hollow = lost.

### Page Hero

- **`.page-hero`**: linear gradient from `var(--game-primary-dark)` to `var(--game-primary)` at `135deg`, `var(--text-on-dark)` text, `3.5rem 0 3rem` vertical padding, halftone-dot pattern overlay (`radial-gradient(circle, rgba(212, 168, 32, 0.06) 1px, transparent 1px)` at `24px` tile). The masthead band that opens game pages. Game palettes flow through automatically.
- **`.page-hero.wc-hero-grad`**: WC-scoped variant that overrides the gradient to navy + red (the World Cup palette). Demonstrates the per-game scoping pattern; new game-specific hero variants follow the same `.page-hero.<game>-hero-grad` shape.

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
- **Do** put light foreground colors on `.card.wc-card` content, scoped to the card surface. Bootstrap defaults will read black-on-navy without it.
- **Do** keep button and form min-height at 44px or larger (mobile-first touch floor).
- **Do** cap Newsreader paragraph line length at 65 to 75 ch.
- **Do** carry the Eyebrow primitive (Teko 500, 0.85rem, 0.14em letter-spacing, gold, uppercase) above section headlines that need contextual labeling.

### Don't:

- **Don't** use `border-left` greater than 1px as a colored accent on cards, list items, callouts, or alerts. The current `.card.border-success` / `.card.border-danger` / `.card.border-warning` / `.card.border-primary` rules in `style.css` violate the impeccable absolute ban on side-stripe borders; they should migrate to full borders with leading icons or background tints. Don't copy the pattern into new code.
- **Don't** apply `background-clip: text` plus a gradient background (gradient text). The metal-gold gradient is for surfaces, never for type.
- **Don't** use `#000` or `#fff` as text or background colors. Tint every neutral toward the brand purple; chroma 0.005 to 0.01 is enough.
- **Don't** use Inter, system-ui, or any other font. Teko and Newsreader define the system; a third font is a regression.
- **Don't** use neutral-gray shadows. CCC shadows are purple-tinted by design; replacing them with `rgba(0, 0, 0, ...)` breaks the press-room atmosphere.
- **Don't** apply `--metal-gold` outside primary-CTA contexts. It is the trophy; decorating with it dilutes it.
- **Don't** introduce repeating identical card grids (icon + heading + text, same size, eight in a row). PRODUCT.md flags this as an anti-reference under "generic SaaS dashboards."
- **Don't** apply the hero-metric template (big number + small label + supporting stats + gradient accent) without justification. Listed in shared design laws as an absolute ban for SaaS cliches.
- **Don't** add a third top-level color outside CCC purple plus gold without scoping it under a game class. WC navy/red, CFB crimson, Golf green only ever appear on `body.game-worldcup` / `body.game-cfb` / `body.game-golf` surfaces.
- **Don't** use `match.stage|title` in Jinja templates. Use the `stage_label` SSoT helper. (Documented gotcha in `CLAUDE.md`; surfaces as a typography slip.)
- **Don't** mock dark mode on light surfaces. The auth pages (Tribunal Black backdrop) and `.card.wc-card` (Tribune-Dark) are the only first-party dark surfaces; everything else is bone-on-light. Don't invent a third dark register.
- **Don't** use bounce or elastic easing on motion. Card hover is the only deliberately overshooting curve in the system; everywhere else, ease out with `cubic-bezier(0.4, 0, 0.2, 1)` or steeper exponential curves.
- **Don't** use em dashes (`—`) or double hyphens (`--`) in UI copy, error messages, button labels, or any prose generated for CCC surfaces. Replace with commas, colons, semicolons, periods, or parentheses. (Carried from PRODUCT.md's Copy Discipline.)
- **Don't** add a navbar item beyond the joined-games list plus auth links. PRODUCT.md flags "navigation overload" as an ESPN/Yahoo anti-reference.
- **Don't** introduce a "Powered by" footer, trust badges, marketing-style hero aimed at strangers, or any platform signal. The site belongs to the club, not to a vendor. PRODUCT.md design principle #1.
