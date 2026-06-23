---
name: CFB Survivor Pool — Design Specialization
description: Per-game design doctrine for the CFB Survivor tab cluster. A dark-first room layered on top of the platform foundation at the repo root's DESIGN.md.
register: product
extends: ../../DESIGN.md
colors:
  # CFB is a DARK-FIRST room. Midnight is the default body substrate (not a rare ceremonial accent),
  # tinted WARM toward crimson so the room reads as its own night and never as WC's cool navy.
  # Hexes below are design targets; A2 tunes exact values to clear WCAG AA on the midnight ramp.
  #
  # Environmental midnight ramp (warm crimson-black; elevation = step UP the ramp, not a shadow)
  cfb-canvas: "#0E0A0C"        # page background / room backdrop (deepest)            --game-bg
  cfb-surface: "#150F12"       # standard cards, tables, structural surfaces          --game-primary-dark
  cfb-raised: "#1E1518"        # elevated / active containers, the .is-lead surface
  cfb-lifted: "#281D20"        # highest non-ceremonial elevation (overlays, sticky bars)
  cfb-hairline: "rgba(243,239,230,0.08)"  # bone hairline border — the dark-mode "edge" that shadows can't draw
  # Competitive identity (single hero color; pressure, not atmosphere)
  cfb-crimson: "#C5050C"       # --game-primary       — identity + interaction + hierarchy
  cfb-crimson-bright: "#E8282F" # --game-primary-light — hover, and the ONLY crimson allowed as text on midnight
  # Editorial reading layer (bone/white as TEXT + contrast, never as a body surface)
  cfb-bone: "#F3EFE6"          # primary body text on midnight                        --game-accent
  cfb-white: "#FBF7F0"         # warm white — headlines, critical numbers, strongest contrast
  cfb-bone-muted: "#B4AAA4"    # secondary copy on midnight (target ≥4.5:1 on --cfb-surface)
  cfb-bone-subtle: "#8A817C"   # tertiary metadata (target ≥4.5:1; warm, never cool slate)
  # Survivor-state semantics (consequence + outcome; NEVER identity; aligned to platform live tokens)
  cfb-survived: "#64DBA0"      # alive / survived — platform --live-green (reads bright on midnight)
  cfb-lost-life: "#E63946"     # one life spent  — platform --live-red (distinct from identity crimson)
  cfb-eliminated: "#6E625F"    # out of the pool — warm ash-midnight (tinted, never neutral gray)
  cfb-pending: "#9A8F88"       # unresolved      — muted warm bone (quiet, not alarming)
---

# Design System: CFB Survivor Pool

> Specialization of the platform design system. Top-level doctrine (palette framework, typography, elevation, motion, design laws, cross-game components) lives in the repo root `DESIGN.md`; this file owns the CFB Survivor identity layer: the dark-first room, palette ranking, the midnight elevation model, typography register, survivor-state semantics, the ceremonial endpoint, and copy voice. When working any CFB surface under `games/cfb/`, read this file alongside the top-level `DESIGN.md` (the CLAUDE.md hard rule).
>
> **Platform-foundation dependency (resolve on `main`, not in this PR):** CFB is a deliberate, sanctioned exception to the top-level §6 Don't "Don't mock dark mode on light surfaces." That rule currently lists only auth backdrops + named ceremonial dark *primitives* as first-party dark surfaces. A whole dark CFB *room* requires a one-line carve-out in the top-level `DESIGN.md` blessing "a game may establish a dark room as its body substrate, documented in its DESIGN.md." Until that companion edit lands on `main`, this file and the top-level Don't are in tension; the carve-out is a required follow-up, not optional.

---

## 1. Overview

The CFB Survivor Pool is a game-specific specialization layered on top of the core CCC platform. It inherits the platform's structural foundations (layout primitives, spacing rhythm, typography families, focus + keyboard behavior, accessibility thresholds, navigation grammar) and diverges only where survivor identity materially requires it. CFB should feel like **its own room inside the club, not a recolored copy of another game.** The root `DESIGN.md` stays authoritative for cross-game concerns; this file is authoritative for CFB-specific decisions.

CFB is a **weekly-attrition survivor game**: each week a player makes one pick to win outright, holds two lives, may use each FBS team only once per regular season, and is ranked by a cumulative-spread tiebreaker. Every week eliminates possibilities; every week thins the field. The central emotion is not celebration, prediction, or fandom. **It is survival.** Across every screen the player must be able to answer three questions immediately, and these questions are the product's primary hierarchy:

1. **Am I still alive?**
2. **What is my decision this week?**
3. **Who is left standing?**

### The room: Saturday Night Survival

The defining experience is **Saturday Night Survival** — a season-long attrition contest playing out *under the lights*. In CCC's editorial fiction (the Commissioner's Club Tribune), CFB is the Tribune's **survival desk**: the same newsroom that runs the World Cup's "Field Office," pointed at gridiron Saturdays and the weekly cut. The two games are desks at the same paper; their *visual* identities diverge hard — WC is a light editorial desk, CFB is a dark one — and that divergence is the whole point.

This is the single largest break from prior platform games, and it is intentional. **CFB is dark-first.** Midnight is the default body substrate across the room, not a rare ceremonial accent. Crimson is competitive pressure inside the dark, never atmosphere. Bone and white become a reading and contrast *layer*, not the page surface. The room should feel disciplined and immersive rather than flashy: tension sustained across a whole season, while staying instantly readable. The CLAUDE.md lounge/room architecture explicitly sanctions this — each game is its own specialized room, and substrate distinction between rooms is "by-design architectural separation, not whiplash." A dark CFB room beside the light WC room is that doctrine at full strength.

A practical note that supports the choice: the dark body actually sits *more* naturally in CCC's chrome than a bone body would. The descent reads as one continuous dark room — council-purple navbar → near-black sub-nav → midnight-and-crimson hero → midnight body → purple footer cap — rather than a bone page sandwiched between purple chrome.

### What CFB is not

CFB is not a sportsbook, betting app, broadcast scoreboard, analytics dashboard, fantasy-stats product, or mascot-driven college-football novelty. Football supplies the setting; survival supplies the structure. New CFB work must not drift toward ESPN-style scoreboard overlays, sportsbook/betting-slip interfaces, live "win probability" telemetry, neon esports chrome, or — the trap a dark room invites most — **operations-center / mission-control telemetry** (banks of readouts, glowing live panels). The spread is a survivor *rule*, not a wagering line; render it as editorial data, never as odds. These references conflict with the Tribune register and dissolve the room.

### The governing question

When evaluating any future CFB UI change, ask:

> Does this strengthen the feeling of a season-long survival contest under the lights, while keeping the player's status, decision, and field instantly clear? Does it still read as the CFB room — and not as the WC room, a dashboard, or a dim low-contrast mess?

If the answer is no, reconsider.

---

## 2. Per-game palette: Warm Midnight, Crimson, Bone + Survivor-State

The CFB palette is a dark-first specialization layered on the platform color system. Its register is **a crimson-leaning night**: midnight under stadium lights, crimson the only saturated energy in the room. The palette competes through *atmosphere, contrast, and controlled pressure*, not through color volume. It is organized into four intentionally independent layers that must never collapse into one another:

1. **Environmental substrate** (warm midnight ramp) — the room
2. **Competitive identity** (crimson) — pressure inside the room
3. **Editorial reading** (bone / white) — clarity
4. **Survivor-state** (green / red / ash / pending) — consequence

### Accent Rank

1. **Midnight (warm crimson-black ramp) — Primary Environmental Substrate**

   Midnight is the dominant *visible* color of the CFB room: page canvas, cards, tables, navigation, sectional containers, overlays. CFB does not treat dark surfaces as ceremony; **darkness is the default environment.** The ramp is tinted *warm*, toward crimson, for two load-bearing reasons: it ties the room to its own accent, and it separates CFB cleanly from World Cup's *cool* navy (two dark games must not both read "blue-dark"). The warm direction also matches precedent — the existing `.championship-hero` already terminates its gradient in a crimson-black (`#1a0a0c`).

   | Role | Token | Purpose |
   |---|---|---|
   | Canvas | `--cfb-canvas` `#0E0A0C` | page background, room backdrop |
   | Surface | `--cfb-surface` `#150F12` | standard cards, tables, structural surfaces |
   | Raised | `--cfb-raised` `#1E1518` | elevated / active containers, the `.is-lead` surface |
   | Lifted | `--cfb-lifted` `#281D20` | highest non-ceremonial elevation (sticky bars, overlays) |

   Use elevation changes sparingly and architecturally, never dashboard-like. Midnight creates atmosphere; it must not compete for attention.

2. **Crimson (`--game-primary` `#C5050C`) — Singular Identity + Interaction Accent**

   Crimson is the one identity and interaction color, and it earns its force by *contrast against the dark*, not by volume. It communicates action, commitment, selection, urgency, active participation, and "this is the active CFB layer." It is school-color crimson, never danger (see the Crimson-Is-Identity Rule).

   Primary consumers: `.btn-game`; the selected `.team-pick-card` and pick-confirmation bar; the `.cfb-pick-cta` weekly band; `.cfb-stat-card.is-lead` rules; the current-user standings emphasis; the active sub-nav pill (`--subnav-accent`); `.cfb-eyebrow-crimson`; section rules; the `.championship-hero` accents and dot overlay.

   Crimson may *tint* localized surfaces but must not dominate layouts. **Avoid** large crimson containers, crimson page regions, crimson-heavy panels, and multiple competing crimson focal points. Crimson is pressure, not wallpaper.

   *Crimson as text on midnight:* identity crimson `#C5050C` is too dark to clear AA as small text on the midnight ramp. Use crimson as **fill, border, and rule** with bone text on top; when crimson must read *as text*, use the bright `--cfb-crimson-bright` `#E8282F` and only at large/bold sizes.

3. **Bone / White (`--game-accent`) — Editorial Reading Layer**

   Bone and white provide legibility and hierarchy *within* the dark room. Unlike prior platform games, **bone is not the body substrate** — it is a reading and contrast layer. Use `--cfb-bone` `#F3EFE6` for body text, `--cfb-white` `#FBF7F0` for headlines and critical numbers, `--cfb-bone-muted` for secondary copy, `--cfb-bone-subtle` for tertiary metadata. Reserve the brightest values for what matters most; let muted bone carry support. Do not build large light panels — the room is immersive, and a bone card on midnight reads as a hole punched in the room (the dashboard-island failure). The exception is the ceremonial endpoint, which earns reduction differently (§4).

4. **Survivor-State (green / red / ash / pending) — Consequence, never identity**

   The survivor-status layer describes player/pick *state* and is deliberately separate from the identity accent rank (the way WC's tier palette is a categorical layer separate from its red/white/navy). These colors are intentionally *more* visible than in prior CFB builds, because status is the heart of the game, and they align to the platform's already-tuned live tokens so they read on midnight:

   | Role | Token | Value | Meaning · emotional read |
   |---|---|---|---|
   | Survived | `--cfb-survived` | `#64DBA0` (platform `--live-green`) | alive · confidence, continuation |
   | Lost a life | `--cfb-lost-life` | `#E63946` (platform `--live-red`) | one life spent · pressure, setback |
   | Eliminated | `--cfb-eliminated` | `#6E625F` (warm ash) | out of the pool · absence, closure |
   | Pending | `--cfb-pending` | `#9A8F88` (muted bone) | unresolved · anticipation |

   Primary consumers: `.lives-indicator`, the result chips (`SURVIVED` / `LOST A LIFE` / `PENDING`), the outcome badges (`IN` / `OUT`), standings outcomes, weekly results, `.elimination-alert`, and the `.spread-badge.favorable` / `.unfavorable` states. Status must stay immediately scannable in dark conditions, and must never rely on hue alone (§4, §6).

### Palette Semantics

- **Midnight** = environment, structure, immersion
- **Crimson** = action, competition, commitment
- **Bone / white** = clarity, editorial reading
- **Survivor-state** = consequence and outcome

Assign color by semantic role, never by preference.

### Elevation on dark (the key adaptation)

The platform expresses elevation with a **purple-tinted shadow** scale on bone. Shadows are near-invisible on midnight, so **CFB expresses elevation by stepping up the midnight ramp plus a bone hairline border** (`--cfb-hairline`, bone at ~8% alpha). A resting card sits on `--cfb-surface`; an active/lead surface lifts to `--cfb-raised`; a sticky/overlay layer to `--cfb-lifted`; each gains its edge from the hairline, not a drop shadow. Reserve any real shadow or localized crimson glow for the single highest-commitment moment (a selected pick), never as ambient decoration.

### Token strategy (how the room actually goes dark)

CFB does **not** invent a parallel `--game-surface` token set — the platform components don't read those; they read `--bg-card`, `--border`, `--bg-muted`, `--text-ink`, `--text-secondary`, and the shadow scale. The correct doctrine is to **rebase those existing platform tokens to the midnight ramp + bone-on-dark text under `body.game-cfb`** (e.g. `--bg-card: var(--cfb-surface)`, `--border: var(--cfb-hairline)`, `--text-ink: var(--cfb-bone)`, `--text-secondary: var(--cfb-bone-muted)`, the body `background` to `--cfb-canvas`), and add the small CFB ramp/elevation tokens above only for surfaces the platform leaves untokenized. This keeps platform inheritance intact while flipping the room to dark, scoped to CFB and CFB only. **Never globally darken the platform** — the dark doctrine stops at `body.game-cfb`.

### Named Rules

#### The Dark War Room is the Room Rule
CFB is dark-first. Midnight is the default body substrate; new CFB surfaces start dark and must *justify* moving lighter. Dark is not reserved for ceremony.

#### The Crimson-Is-Identity Rule (the central CFB discipline)
Crimson `#C5050C` reads as **school-color identity and interaction, never danger or loss.** This is CFB's one real risk: crimson and the survivor "lost a life" red are both reds, and a survivor pool's dominant event is losing. The separation: loss is carried *only* by `--cfb-lost-life` (the brighter, distinct `#E63946`) and *always* with a structural cue (the hollow life pip, the `L` / `LOST A LIFE` / `OUT` label); interaction (buttons, selection, current-user emphasis) is *only* crimson. Status communicates consequence; crimson communicates choice. Communicate state by structure + label, never color alone.

#### The Crimson-Pressure Rule
Crimson is pressure, not atmosphere. Do not fill the room with it. When several elements compete for crimson attention, *reduce* usage until emphasis is meaningful again.

#### The Elevation-by-Midnight Rule
Hierarchy emerges through substrate depth before color. Reach for a deeper or raised midnight (and the hairline) before adding accent. The room is architectural, not a dashboard.

#### The Crimson-Ceremony Rule (no gold in CFB)
CFB does **not** adopt gold as a game-level ceremonial organizer — that is WC's move, and a dark room reaching for gold would read as WC. CFB's ceremony is crimson restraint on midnight. Platform-level gold stays where the platform owns it (focus rings, the active navbar CTA, the lounge); CFB never introduces gold into its own body or ceremonial surfaces.

#### The Ceremony-by-Reduction Rule
Because the room is already dark, ceremony cannot mean "make it darker." Endgame moments escalate through *reduction*: more negative space, less density, concentrated contrast, stiller composition (§4 `.championship-hero`).

---

## 3. Typography specialization

The platform foundation (`DESIGN.md` §3) defines the canonical system: Teko for headlines, labels, data, and navigation; Newsreader for editorial reading. CFB preserves the families exactly. **CFB's specialization is a register change, not a font change.** Because CFB deliberately limits color volume, typography, spacing, contrast, and composition carry more of the hierarchy and emotional pacing than on a light, color-rich surface. The room should feel deliberate, competitive, and editorial under pressure.

### The Survivor voice on CFB H1s

User-facing CFB routes treat their H1 as **Survivor-register editorial voice**, not a literal route label — the same Tribune spine the platform defines, localized to gridiron-Saturday attrition (the slate, the cut, two lives, survive-and-advance, the last team standing). This register is *distinct* from WC's civic-ceremonial cadence (Decree / Council); the two share an editorial parent and must not converge.

| Surface | Register direction (illustrative; A2 sets final copy) |
|---|---|
| Standings / hub | "Last Ones Standing" / "The Survivors" |
| Weekly results | "Saturday's Verdict" / "Week N: The Reckoning" |
| Picks | "Your Card" |
| Join | "Take Your Two Lives" |
| Rules | "House Rules" (the shared club idiom CFB and WC may both use) |
| Elimination week | "The Cut" |
| Final week | "One Remains" |

Two platform dispensations carry across games: (a) **dynamic interpolated H1s** read functionally because the value carries the voice (`{{ get_week_display_name(week) }}`, `{{ team.name }}`); (b) **logged-in utility auth surfaces** keep functional H1s, the voice carrying through the eyebrow + Newsreader copy. A flat functional H1 on a routine CFB tab is a regression. If a title could belong equally to a spreadsheet, a sportsbook, or an admin console, rewrite it.

### Numbers carry the tension

Survivor gameplay is numeric — lives remaining, the week, rank, cumulative spread, survivor count, the deadline. Because color is restrained, **critical numbers should feel emotionally heavier than the copy around them**, taking Teko display treatment normally reserved for headings (remaining survivors, rank, life count, spread differential, countdown). The player should feel consequence from weight and scale, without animation. Avoid decorative counters, scoreboard tickers, and casino-style emphasis; typography makes numbers feel *earned*, not gimmicky.

### `.cfb-eyebrow` primitive + variant

`.cfb-eyebrow` is the CFB contextual-label primitive (the analog to `.wc-eyebrow`): small uppercase Teko metadata above a headline (week, deadline, survivor count, status). It follows the platform "one default + tonal variant" eyebrow shape — never a parallel "kicker." Composition mirrors the foundation eyebrow (Teko 500, ~`0.7rem`, letter-spacing ~`0.08em`, uppercase); A2 sets final metrics. Because CFB bodies are dark, the **default** color is a bone value (`--cfb-bone-muted`) calibrated for midnight. One variant is part of the primitive:

- **`.cfb-eyebrow-crimson`** (`--cfb-crimson-bright` on dark) — competitive / active-state emphasis (this week's deadline, the current leader, the user's own row). Keep it uncommon; the headline should carry the moment. CFB adds **no** gold eyebrow variant (the Crimson-Ceremony Rule).

### Copy discipline (Survivor lexicon)

Lean into the survivor-football vocabulary: *survive, the cut, rivalry week, under the lights, the slate, last standing, hold your lives, survive and advance, outlast, the verdict, still alive.* Keep the platform voice — sharp, competitive, restrained, editorial. The platform **no-em-dash / no-double-hyphen** rule applies to every CFB surface (existing standings/tiebreaker copy violates it: "Lower is better — picking favorites…"; A2 fixes it). The spread is framed as a survivor *rule*, never wagering language. **Avoid** betting language, fantasy jargon, gaming slang, mascot humor, hype, **and tactical/military framing** — the "war room" mood lives in the design north star only; no `deploy` / `mission` / `command` / `tactical` ever reaches user copy. Football creates setting; survival creates meaning.

---

## 4. Components

CFB's named-primitive register. Each primitive is documented as doctrine here; the CSS is built / reconciled in A2 — and A2 must first stand up the **dark-substrate foundation** (the §2 token rebase + midnight elevation) *before* per-screen polish, since every platform primitive (`.card`, `.table`, `.alert`, `.form-control`, the shadow scale) needs its dark form scoped under `body.game-cfb`. Components should feel structured, restrained, and consequential; movement communicates commitment; color reinforces hierarchy rather than manufacturing excitement. Priorities, in order: **clarity, atmosphere, consequence, immersion, celebration.**

### `.championship-hero` — the Empty-Field ceremony (analog to `.wc-champion-banner`)

`.championship-hero` is the dedicated last-one-standing declaration surface, and the CFB analog to WC's `.wc-champion-banner`. It is a single-purpose ceremonial endpoint — not a reusable dark card, feature panel, or weekly-result hero. **But its distinction is no longer "the only dark surface"** (the room is dark throughout). Its distinction is **ceremony through reduction**: the lights stay on, the room goes quiet, one survivor remains. Victory should feel earned, inevitable, and slightly lonely.

Composition principles: expansive negative space; reduced information density; strong vertical rhythm; concentrated contrast; minimal chrome; restrained motion. Visual language: a midnight atmospheric field (the existing crimson-tinted gradient + crimson dot overlay), restrained crimson emphasis, isolated survivor identity, editorial typography. Content: survivor declaration (`.champion-name`, Teko 700 uppercase, warm white, `clamp()` within the platform ≤6rem display ceiling); final record; season context (`.champion-subtitle`, Newsreader, retrospective voice); prize acknowledgment (`.prize-badge`, crimson); optional survivor-count summary.

Render gate (strict): resolves only when the pool has a single survivor — in the current build, `enrollments|length == 1 and eliminated_enrollments|length > 0` on the standings route. Never speculative, mid-season, or contested. **Avoid** confetti, trophy overload, gold celebration systems, particle effects, excessive gradients, animated spectacle — and never introduce gold. Ceremony is conclusive, not triumphant.

### `.cfb-stat-card` — the editorial operations panel (Casual-Dark reference)

`.cfb-stat-card` is the foundational body component of the dark room and the doctrinal model for how CFB renders information density — the dark-first analog to WC's `.wc-stat-card`. It combines editorial readability with operational structure; cards should feel like surfaces designed for decisions, not telemetry widgets. Composition: `--cfb-surface` substrate, hairline border separation (not a shadow), editorial spacing, deliberate grouping, strong heading hierarchy. Preferred internal structure: eyebrow → headline → primary value → supporting context → optional action.

Hierarchy lift comes through **`.is-lead`**: the surface steps up to `--cfb-raised`, gains a `2px solid var(--game-primary)` crimson top rule, stronger contrast, and more breathing room. Reserve it for the current decision and season-critical information (active deadline, "your pick," final-life state). Avoid dashboard fragmentation; cards should feel collected and intentional, not assembled from unrelated modules.

### `.team-pick-card` — the commitment surface

The most important interaction primitive in CFB. Selecting a team should feel like making a decision, and the states should *escalate* with commitment:

- **Resting** — available: `--cfb-surface`, subtle hairline, calm, clear team hierarchy.
- **Hover / focus** — possibility: a half-step elevation, a restrained crimson border lift, visible keyboard focus.
- **Selected** — commitment: structural lock-in + crimson perimeter + a localized atmospheric crimson glow (the one sanctioned glow in the room) + a small expansion + stronger team weight. The read is "I submitted my call."
- **`.ineligible`** — cold and procedural (already used, game started, spread restriction, deadline passed): reduced contrast, suppressed interaction, an explicit reason. Never punitive, never a broken-looking opacity collapse.

The pick flow is JS-driven (`data-team-id` / `data-game-card` / `.team-option` hooks). **Audit every `querySelector` / `data-*` hook before renaming any class**, and add CSS classes alongside JS-critical ones rather than renaming them (the platform template-restyling rule). Preserve implementation-bound selectors unless a refactor updates template, CSS, and script together.

### `.spread-badge` — the quiet signature mechanic (`.favorable` / `.unfavorable`)

The point spread is CFB's **custom-game identity** (PRODUCT.md "custom games earn custom layers") — the 16.5+-favored-is-ineligible rule and the cumulative-spread tiebreaker are unique to this pool, the CFB analog to WC's multiplier system. But its presentation is intentionally *restrained*: the spread is informed strategy, not active wagering. `.spread-badge` is a compact, typographic chip — subdued contrast, secondary hierarchy — with a neutral default and two survivor-state variants (`.favorable` lifts toward survived-green, `.unfavorable` toward lost-red) plus a restricted/ineligible state. **Avoid** large chips, directional betting arrows, odds-board styling, and dramatic color shifts. Players should notice the spread when *deciding*, not when scanning.

### Survivor-status primitives — lives / result / outcome

Governed by the Crimson-Is-Identity Rule (state never identity; structure + label, never color alone):

- **`.lives-indicator` / `.life` / `.life.lost`** — the survival-at-a-glance mark: an inline row of pips, one per life. Held = filled (survived-green), confident; lost = hollow/outlined (ash), reduced; the eliminated row reads drained and quiet. **Keep the pips clean and geometric.** Do *not* pursue "stitched marks / football pips / yard markers / drive markers" — literal football skeuomorphism is a named platform ban ("generic sports skeuomorphism"); distinction comes from precision and dark recalibration, not texture. State must survive without color (fill + outline + position carry it).
- **Result chips** — the weekly verdict: `.badge-survived` (`SURVIVED` / `W`), `.badge-lost-life` (`LOST A LIFE` / `L`), `PENDING`. Compact, high-contrast, structured, text-readable. No celebratory treatment; a chip records consequence, it does not throw a party.
- **Outcome badges** — season position: `IN` vs `OUT` (`.badge-eliminated`), plus `.badge-xs` for inline compactness. These read administrative, not emotional.

### `.cfb-pick-cta` — the weekly call

CFB's primary routine action band; its job is singular: *what is my decision this week?* Composition: restrained crimson structure (a crimson top rule) over an elevated midnight surface, concise typography, a visible deadline. This is the strongest routine CTA in the room and must not be buried beneath standings, history, or explanatory text while picks are open.

### Hero — the platform `.page-hero` default (no CFB override)

CFB uses the platform `.page-hero` directly: because crimson is `--game-primary` and the warm midnight surface is `--game-primary-dark`, the default `135deg` dark→primary gradient already resolves to the midnight-and-crimson "under the lights" band. **Do not author a `.cfb-hero-grad`** (contrast WC, which needed `.wc-hero-grad` only because its navy identity color is *not* `--game-primary`). One scoped detail: the hero's halftone-dot overlay is gold in the platform default — scope it to crimson on CFB so no gold appears (the existing `.championship-hero` already uses crimson dots).

### Game sub-nav

The platform `.game-subnav .subnav-cfb` shape (`DESIGN.md` §5 Navigation), already near-black: `--subnav-accent` = crimson `#C5050C`, `--subnav-accent-rgb` = `197, 5, 12`, background `#0a080f`. The active pill should feel *selected*, not illuminated; rest pills stay quiet bone-on-midnight; navigation orients and then disappears behind content. Don't give each route its own navigation language.

### `.elimination-alert` — procedural elimination (debt: side-stripe)

The "Eliminated This Week" block on weekly results — the visible cut. Elimination is administrative consequence, not spectacle: the emotional target is cold, final, accepted ("your season changed"), never an emergency-red alarm or shame. **Known debt:** the current implementation uses `border-left: 4px solid var(--cfb-lost-life)`, which violates the platform absolute ban on side-stripe borders. A2 migrates it to a full-container treatment (full border + restrained survivor-state tint + strong title + leading icon), keeping the lost-red status color but dropping the stripe.

### Named Rules

- **The Consequence Rule** — interaction feels meaningful; emphasis and movement increase as commitment increases.
- **The Empty-Field Rule** — ceremony comes from reduction; the most important moments contain the least noise.
- **The Quiet-Spread Rule** — the spread is strategy, never presentation.
- **The Cold-Elimination Rule** — elimination is procedural; the interface records outcomes, it does not mourn them.
- **The Commitment Rule** — selecting a team should feel heavier than browsing one.

---

## 5. Do's and Don'ts (CFB-scoped — additions to top-level §6)

CFB-specific enforcement on top of the platform-wide guidance. When trade-offs occur, preserve in order: **readability, atmosphere, survivor tension, continuity, novelty.** If a decision improves style but weakens survival clarity, reject it.

### Do:

- **Do** default new CFB surfaces to the midnight ramp; build hierarchy through elevation, spacing, typography, and contrast before reaching for color.
- **Do** treat crimson as a competitive event — reserve its strongest moments for decisions, deadlines, selected states, and survivor-critical info; make selection feel heavier than browsing.
- **Do** keep survivor state communicated by structure + label, never color alone (filled vs. hollow pips, `W`/`L` text, `OUT`/`IN`), and keep survivor-state colors distinct from crimson.
- **Do** keep the room *dark, not dim* — verify contrast on every midnight surface; muted bone is support, never decoration.
- **Do** use `.cfb-eyebrow` for contextual framing; reach for `.cfb-eyebrow-crimson` only when the label itself carries active signal.
- **Do** elevate meaningful numbers (rank, week, lives, deadline, survivor count) and carry the Survivor editorial voice on H1s.
- **Do** keep the platform default `.page-hero` (midnight→crimson) as the persistent identity anchor; scope its dot overlay to crimson.
- **Do** render the spread as quiet editorial rule-data, framed as a survivor rule.
- **Do** allow intentional negative space around important decisions and the endgame; whitespace is hierarchy, and it carries emotional weight.
- **Do** audit JS `querySelector` / `data-*` hooks before renaming any pick-flow class; preserve implementation-bound selectors.

### Don't:

- **Don't** use crimson to signal loss, danger, or elimination — crimson is identity; loss is the survivor-status red, always with a structural cue. (The central CFB discipline.)
- **Don't** let dark collapse into low contrast, or place muted text on a raised midnight surface without testing. CFB is dark, not dim.
- **Don't** globally darken the platform — the dark doctrine stops at `body.game-cfb`; never touch the lounge, WC, Golf, auth, or shared chrome.
- **Don't** build large bone/white panels on midnight (the dashboard-island look); bone is a text + contrast layer, not a body surface.
- **Don't** introduce gold into CFB body or ceremonial surfaces — gold stays where the platform owns it. This is what keeps CFB distinct from the WC room.
- **Don't** author a `.cfb-hero-grad` or otherwise re-skin the hero; the platform default already produces the signature gradient.
- **Don't** fragment screens into excessive cards/widgets/micro-surfaces, or give every card equal emphasis; the room should feel composed.
- **Don't** simulate sportsbook / betting-slip UI, broadcast scoreboards, win-probability telemetry, **or operations-center / mission-control dashboards** — the dark room invites the last one most; refuse it.
- **Don't** pursue skeuomorphic football textures (stitched/yard/drive markers), stadium textures, or scoreboard fonts.
- **Don't** animate continuously, use glow as hierarchy, or rely on motion alone for meaning; atmosphere should disappear when ignored.
- **Don't** use em dashes or double hyphens in CFB copy, or let tactical/military language reach user-facing surfaces (the war-room mood is an internal north star only).
- **Don't** converge the CFB voice with WC's civic-ceremonial register, or vice-versa; they share the Tribune parent, their localizations are distinct on purpose.

---

## 6. Visual smoke + verification cadence

CFB visual verification evaluates the game as a unified seasonal experience, not isolated routes. The primary regression question is not "does this page look correct?" but:

> "Does this still feel like one season-long survivor room — dark, immersive, instantly readable — and not the WC room, a dashboard, or a dim mess?"

Verification protects atmosphere, consequence, readability, and continuity simultaneously. Every substantial change should preserve: decision clarity, atmosphere, survivor tension, continuity, readability.

### Core visual smoke workflow

Run the dev server on the platform port-5099 worktree pattern (`CLAUDE.md` § "Run development server") against the local CFB sandbox, and use `CFB_FAKE_NOW` (with `ENVIRONMENT=development`) plus re-seeding (`instance/seed_cfb_sandbox.py [midseason|champion]`) to walk the season states that gate substantial UI behavior. Smoke each at desktop **and** true-mobile width (chrome-devtools `emulate "375x812x2,mobile,touch"`, not `resize_page`); mobile gets extra scrutiny (survivor sessions skew to quick mobile check-ins).

- **Pick open** (pre-deadline) — is the CTA obvious within seconds? Is the deadline visible? Does the pick feel like a decision? Current-week emphasis present?
- **Weekly verdict** (post-deadline / scored) — outcome readability; survivor-state visibility; emotional restraint; season continuity.
- **Mid-season attrition** (mixed lives 2 / 1 + eliminated tail + pending) — standings hierarchy; survivor-state clarity; current-user visibility; how much field remains.
- **Final life** (one life left) — decision focus; urgency *without* panic or emergency styling; readability under pressure (pressure emerges from context, not red alarms).
- **Resolved season** (single survivor) — `.championship-hero` reads as escalation-by-reduction, earned and quiet, still the same room; no redesign, no gold, no spectacle.

### Cross-route continuity smoke

Pass across `STANDINGS → PICK → RESULTS → MY PICKS → JOIN`, evaluating substrate continuity, typography rhythm, decision hierarchy, component consistency, atmosphere persistence, interaction language, and current-user/survivor-state consistency. The standard is **"one room, one season, one game"** — and the second standard is **"this is not the WC room"** (the two rooms must read as distinct; the lounge/room architecture in `CLAUDE.md`). No route should feel imported from another product.

### Regression categories

- **Low-contrast dark mode** — washed hierarchy, muted states, text that takes effort. Dark, never dim.
- **Crimson saturation** — multiple competing crimson regions, flattened hierarchy, crimson carrying unrelated meaning. Crimson stays meaningful.
- **Accent collision** — crimson reading as danger, or survivor-red reading as interaction; the two reds bleeding together.
- **Dashboard / ops-center fragmentation** — excessive cards, unrelated panels, telemetry/widget behavior, equal emphasis everywhere. The room is composed.
- **Generic fantasy / sportsbook drift** — roster-builder energy, betting-slip styling, generic standings UI, broadcast overlays. The player should feel survival pressure, not content consumption.
- **Consequence collapse** — picks feeling reversible, elimination invisible, deadlines disappearing, lives indicators going decorative. The season always feels active.
- **Atmosphere inflation** — excessive motion, cinematic effects, decorative glow, constant drama. Atmosphere supports meaning, never replaces it.
- **Voice convergence** — CFB H1s drifting into WC's civic-ceremonial cadence, or flat functional labels replacing the Survivor register; any tactical/military language reaching user copy.

### Accessibility verification (priority order)

1. **Contrast** — body text ≥4.5:1 and large text ≥3:1 on *every* midnight surface, including raised/lifted; status colors and the worst-corner pixels of the midnight→crimson hero gradient; no raw `color: var(--text-muted)`-style under-contrast on dark (muted bone must stay functional, not decorative). Dark environments must read instantly.
2. **Scan speed** — can the player identify *alive status, current decision, remaining field* within seconds? If not, hierarchy failed.
3. **Motion comfort** — transitions feel optional; no persistent movement; no motion-only state changes; honor `prefers-reduced-motion`.
4. **Keyboard / focus** — visible focus on the midnight substrate; pick cards keyboard-operable; active nav state clear. Platform focus standards inherited.
5. **Color blindness** — survivor state survives without hue (shape, fill, label, position); outcome never depends on color alone.

### Empty states

Empty states feel stoic ("no pick submitted," "no entrants," "eliminated player," "unresolved week"): clear next steps when action is possible, calm closure when not. Avoid playful emptiness, over-encouragement, jokes, mascot humor, or celebration language. The message is simply: *the season continues.*

### Implementation verification idioms

CFB inherits the established CSS-scan idioms from the WC phases (anchored `^...` + `re.MULTILINE` scans, property-anchored `(?<![-\w])` lookbehinds, rule-block `\{([^}]*)\}` extraction, forbidden-list `\s*[,{]` terminators) for targeted enforcement. New regression locks introduced when a CFB primitive or contract lands should fail before the change and pass after. All Python comments and docstrings introduced in CFB phases remain ASCII-only.

### Final evaluation question

Before approving any substantial CFB UI change, ask:

> Does this increase consequence without increasing friction, keep the player's status / decision / field instantly legible on a dark substrate, and still feel like the same season-long survivor room under the lights — not the WC room, not a dashboard, not dim?

If the answer is no, revise before shipping.
