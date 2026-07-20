# Product

## Register

product

## Platform

web

## Users

### Core Audience

CCCFantasy serves small, socially connected fantasy groups: friend groups, coworker leagues, family pools, friends-of-friends circles. Roughly 10 to 30 people with existing camaraderie. The product is **not** designed for anonymous mass-market fantasy participation; its primary value is enabling a shared social sports experience inside a familiar group.

Within any single group, users span three engagement levels simultaneously:

- **Casual participants** check the site between meetings, on Sunday mornings, or during live games. They want to make picks quickly, understand standings instantly, and stay connected to the group.
- **Stats-curious users** enjoy lightweight insights and trends that help them feel informed without requiring deep analysis.
- **Analyst-minded users** occasionally seek richer data: scoring breakdowns, trend snapshots, ownership percentages, matchup context, per-team performance.

The interface must support all three audiences on the same surface without fragmenting into "casual mode" and "pro mode."

### Resolution Principle

> **Casual is the default. Depth is available when sought.**

Primary workflows feel lightweight, fast, socially driven, and immediately understandable. A user should never feel overwhelmed by:

- Dense analytics
- Configuration-heavy flows
- Enterprise-style dashboards
- Expert-oriented terminology
- Spreadsheet-shaped information hierarchy

At the same time, deeper analytical context remains accessible through progressive disclosure. Advanced information should:

- Sit secondary to core actions, never first
- Reward curiosity without punishing casual use
- Support confidence and conversation
- Enhance decision-making without dominating the interface
- Spark banter and discussion among users who want more from the game

### User Behaviors

Sessions are typically:

- Short
- Repeatable
- Mobile-first
- Context-switched (the user is multitasking)
- Emotionally reactive during live events

Common behaviors:

- Making or updating picks. Some users finalize a roster in 30 seconds; others meticulously craft theirs over multiple sessions.
- Checking standings during games or tournaments
- Following live leaderboard movement
- Comparing picks with friends
- Reacting emotionally to outcomes in real time
- Sharing banter, rivalry, and trash talk after major sports weekends

Because users are frequently multitasking, interfaces prioritize:

- Fast comprehension
- Minimal interaction cost
- Clear visual hierarchy
- Thumb-friendly interaction zones
- Immediate status clarity
- High signal-to-noise ratio

### Job To Be Done

> **"Compete with my people, win or lose with the group."**

Users come to CCCFantasy to:

- Lock picks before deadlines
- Craft rosters they believe in (spiritually or statistically)
- See where they stand
- React to live outcomes
- Track momentum swings
- Compare themselves against the group
- Participate in rivalry and conversation

Winning matters. The social experience is the primary product outcome.

### UX Implications

Every major surface optimizes for, in priority order:

1. Social energy over analytical complexity
2. Clarity over density
3. Confidence over precision obsession
4. Mobile-first interaction patterns
5. Progressive disclosure for advanced information

Every screen should answer four questions:

1. What do I need to know right now?
2. What action can I take immediately?
3. How am I doing relative to my group?
4. Where can I go deeper if I want to?

## Product Purpose

CCC (Corrupt Commish Club) is a custom fantasy-sports platform for hosting pools and game formats that mainstream platforms either don't support, support poorly, or monetize in ways incompatible with a small-group experience.

Examples of what CCC hosts (as of the 2026-27 era: CFB Survivor is the active flagship; the 2026 World Cup pool ran to completion and is archived; Golf launches ~2027 — `games/registry.py` is the status SSoT):

- Golf Pick'em across a full PGA season
- CFB Survivor with custom weekly spread-lock rules
- World Cup Fantasy with tier-plus-multiplier scoring
- Additional custom formats added over time

The product exists for two equally load-bearing reasons.

### 1. Voice

CCC has a distinct personality that mainstream fantasy platforms cannot deliver.

"Corrupt Commish Club" is a wink, not a polished corporate brand. The product should feel like an "exclusive" members' club run by and for the group itself, not a SaaS platform serving anonymous customers. The fiction matters: when a member loads the site, they should feel they're entering somewhere that belongs to their group, not a feature of a larger ecosystem.

### 2. Custom Games

The formats themselves are part of the product identity.

CCC supports games with:

- Custom rules
- Custom scoring systems
- Group-specific traditions
- Sport-specific mechanics (deadline locks, knockout brackets, multipliers, weekly spreads)
- Flexible structures unavailable on major platforms

These mechanics feel first-class and purpose-built, not adapted from a generic fantasy framework.

### Success Criteria

Success looks like:

- Users open the site instinctively during live sports weekends
- Pick workflows feel obvious and frictionless
- Leaderboards create emotional reactions
- The UI reinforces group identity and rivalry
- The experience consistently feels like "our site," not a generic fantasy product

## Brand Personality

### Sharp. Competitive. Pleasure.

#### Sharp

- Quick-witted copy
- Decisive interface behavior
- Crisp visual hierarchy
- Concise, confident language
- Minimal corporate hedging

Microcopy carries personality harder than decoration. A button label, an empty state, or a status message is a more effective brand surface than a gradient.

#### Competitive

- Leaderboard-forward design
- Ranking and movement are first-class information
- Stakes feel legible and bearing without screaming
- Momentum, gain/loss, and live movement feel alive

#### Pleasure

The product exists to create enjoyment.

Interfaces shouldn't merely function correctly; they should feel rewarding to use. Concrete examples:

- Locking a pick should feel consequential
- Score changes should feel dynamic
- Empty states should reward participation rather than apologize for missing data
- Motion and feedback should create lightweight delight without becoming noisy

The "Corrupt Commish Club" name provides edge. The product polish provides legitimacy. Together they read as an "exclusive" private club for competitive acquaintances, never as an enterprise app.

## Anti-references

The following product patterns are explicitly off-limits.

### ESPN / Yahoo Fantasy

Avoid:

- Banner-ad visual density
- Untiered statistical tables
- Navigation overload
- Generic 2010s fantasy-platform aesthetics
- Enterprise trust-signaling
- Monetization surfaces unrelated to the friend-group experience

CCC feels curated and intentional, not platform-scale.

### Generic SaaS Dashboards

Avoid:

- Gray-on-white enterprise dashboards
- Hyper-minimal B2B aesthetics
- Stripe / Linear / Notion-style metric layouts
- Repeating identical card grids
- Emotionless analytics interfaces
- "Professional productivity tool" visual language
- Inter as the body font (Newsreader serif and Teko display already define CCC type)

CCC feels social, competitive, and opinionated. Restrained-grayscale SaaS is the wrong destination, even when the surface in question is utilitarian.

### Bootstrap Starter Aesthetic

CCC overrides Bootstrap heavily through `tokens.css` and `style.css`. Any new surface that visually regresses toward stock Bootstrap is a design failure.

Regression indicators:

- Default `.card` styling (no CCC scoping)
- Generic `.btn-primary` behavior
- Stock Bootstrap navbar layout
- Unscoped utility-driven presentation
- Generic spacing rhythm detached from CCC identity

Treat these as visual slop signals.

## Design Principles

These five principles are the strategic locks every impeccable command should respect. They're listed in priority order; if two principles conflict on a surface, the lower-numbered one wins.

### 1. It's Our Club, Not a Platform

Every design decision should reinforce the fiction that the site belongs to a real, named acquaintance group. Avoid signals associated with large-scale platforms:

- Generic onboarding funnels
- Marketing-style landing pages aimed at strangers
- Trust badges
- Corporate footers
- "Powered by" branding
- Venture-backed product language

The experience feels insider-oriented, not mass-market.

### 2. Voice Lives in the Copy, Not the Chrome

Personality emerges through:

- Button labels
- Empty states
- Success states
- Error messages
- Status updates
- Live reactions

The visual system stays polished and restrained enough to age well. Decorative chrome dates fast; sharp copy doesn't.

> "Lock it in" is stronger than another decorative treatment.

Chrome carries polish. Copy carries voice.

### 3. Pleasure Is a Deliverable

Enjoyment is a functional requirement, not a stretch goal. Interactions should feel satisfying, alive, and emotionally responsive.

Important moments:

- Pick confirmation
- Live score movement
- Rank changes
- Elimination moments
- Rival comparison
- Deadline urgency

Empty states reward participation rather than communicate absence.

### 4. Casual-Default, Analyst-Respected

Primary surfaces optimize for casual comprehension. The default user can:

- Understand standings quickly
- Submit picks confidently
- Navigate without explanation
- Process information at a glance

Advanced users can still access:

- Trend snapshots
- Ownership data
- Team-level breakdowns
- Historical performance
- Comparative statistics

Depth is layered, never flattened into the default experience.

### 5. Custom Games Earn Custom Layers

Each game feels meaningfully distinct while remaining inside the CCC system:

- Golf surfaces emphasize tournament rhythm and season progression
- World Cup surfaces emphasize knockout urgency and the multiplier system
- Survivor pools emphasize elimination pressure and weekly spread locks

The CCC platform provides the consistent chrome (purple/gold + bone, Teko + Newsreader, navbar, login). Each game provides its own room: its own palette, sub-nav, and interaction emphasis. Game blueprints inject their identity via `body.game-<game>` and a per-game CSS section in `style.css`.

## Accessibility & Inclusion

Accessibility is part of product quality, not a compliance afterthought.

### Baseline

CCC honors **WCAG 2.1 AA contrast** for all text and interactive controls.

### Known Surface Constraints

Dark substrates are where legibility regressions recur. The platform has three first-party dark-surface families:

- **The `body.game-cfb` midnight room** — CFB Survivor's entire body substrate is dark (the sanctioned dark room; doctrine and per-color contrast constraints in `games/cfb/DESIGN.md`).
- **`.wc-champion-banner`** — the World Cup's single ceremonial dark surface (navy `rgba(0, 17, 46, .8)`; the retired `.card.wc-card` substrate's only surviving heir).
- **Auth backdrops** — the Tribunal Black radial gradient behind the auth cards.

Two locked patterns protect text on and around these surfaces:

1. **Scope light-foreground overrides to the dark surface** (e.g., `.wc-champion-banner .text-muted`). Never broadcast `tbody td { color: light }` globally; it breaks rows that Bootstrap masks with white on every light surface.
2. **On bone/white substrates, muted text routes through the `.text-muted` class**, which the `:root { --bs-secondary-color }` redirect lifts to AA contrast. Raw `color: var(--text-muted)` is calibrated for dark substrates only and must never appear on bone/white — use `--text-secondary` there. (Enforcement details in CLAUDE.md, "Design system & CSS.")

### Mobile-First Requirements

CCC is fundamentally mobile-first. Critical user flows (home, leaderboard, pick UI, join page) must function cleanly at a 375 px viewport width without:

- Horizontal scrolling
- Broken hierarchy
- Multi-column collapse issues
- Interaction crowding

Hard requirements:

- Touch targets ≥ 44 × 44 px
- Body text ≥ 16 px
- Strong tap affordance
- Fast readability under distraction (the user is multitasking)

### Motion and State Accessibility

When animation, color, or live-state systems are introduced, they must:

- Respect `prefers-reduced-motion`
- Avoid color-only state communication (live, eliminated, winning)
- Pair state color with icons, labels, or structure
- Preserve readability during live updates

## AI Guidance

The intended consumer of this document is AI-assisted design and implementation systems (Claude Code, Cursor, Codex, and any other agent reading PRODUCT.md before generating code, layouts, or copy). When generating interfaces, copy, layouts, interactions, or visual systems for CCCFantasy, prioritize the following interpretation rules.

### Prioritize Emotional Utility

Don't optimize exclusively for information efficiency. The product creates:

- Rivalry
- Momentum
- Anticipation
- Delight
- Group identity
- Competitive tension

Interfaces should feel socially alive. A leaderboard that "communicates standings" but doesn't make the user feel anything has failed.

### Avoid Generic Product Generation

AI-generated outputs frequently regress toward:

- Generic SaaS dashboards
- Over-neutral typography systems
- Flat grayscale UI
- Analytics-heavy layouts
- Enterprise workflow patterns

These defaults are usually incorrect for CCC. Prefer:

- Strong hierarchy
- Emotional immediacy
- Competitive framing
- Opinionated layouts
- Mobile-first prioritization
- Layered information density

If your first instinct on a CCC surface is a clean three-column dashboard with even card grids, it's wrong. Try again.

### Preserve the Fiction

The product should always feel like:

- An "exclusive" club
- A shared ritual
- A friend-group competition layer
- A socially maintained environment

It should never feel like:

- A monetized platform ecosystem
- A fantasy sports marketplace
- A productivity tool
- A betting app clone
- A generic startup dashboard

When in doubt: ask whether the surface would feel right framed as "our group's site," or whether it would feel like a feature of a much larger product. The first answer is correct.

### Optimize for Repeated Short Sessions

Assume most interactions occur:

- On mobile
- During live sports
- In short bursts (under 60 seconds)
- While multitasking (the user is half-watching a game)

Prioritize:

- Immediate readability
- Fast actions
- Live emotional feedback
- Minimal friction
- Clear ranking visibility

A surface that requires a desktop, a quiet room, and 10 minutes is the wrong design for CCC even if it would be excellent in isolation.

### Maintain Layered Depth

Don't flatten advanced information into default surfaces. The ideal information structure is:

1. **Fast casual comprehension** at the default layer
2. **Optional deeper insight** one tap or scroll away
3. **Rich analytical detail** only when intentionally explored

Advanced users feel respected. Casual users never feel punished. The two audiences share one surface.

### Copy Discipline

CCC copy follows the impeccable design laws on writing:

- Every word earns its place. No restated headings, no intros that repeat the title.
- **No em dashes** (`—`) and no double hyphens (`--`). Use commas, colons, semicolons, periods, or parentheses. This applies to UI copy, error messages, button labels, and any prose generated for CCC surfaces.
- Active voice. Decisive verbs. No corporate hedging.
