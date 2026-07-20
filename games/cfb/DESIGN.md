---
name: CFB Survivor Pool — Design Doctrine
description: Per-game design doctrine for CFB Survivor at cccfantasy.com. A dark-first room layered on the platform foundation (repo root DESIGN.md). Product philosophy, identity system, component doctrine, lounge + room architecture, implementation guidance.
register: product
extends: ../../DESIGN.md
colors:
  # Shipped tokens — these ARE the values in static/css/style.css (body.game-cfb block),
  # verified against code 2026-07-20. If doc and CSS ever disagree, the CSS block is the
  # runtime truth; fix whichever one drifted.
  #
  # Environmental midnight ramp (warm crimson-black; elevation = step UP the ramp)
  cfb-canvas: "#0E0A0C"        # page background / room backdrop (deepest)            --bg-page
  cfb-surface: "#150F12"       # standard cards, tables, structural surfaces          --bg-card
  cfb-raised: "#1E1518"        # elevated / active containers                         --bg-muted
  cfb-lifted: "#281D20"        # highest non-ceremonial elevation (overlays, sticky bars)
  cfb-midnight-hero: "#1A0B0D" # --game-primary-dark — the .page-hero gradient origin (5th ramp value)
  cfb-hairline: "rgba(243,239,230,0.08)"         # resting edge — the dark-mode "border" shadows can't draw
  cfb-hairline-strong: "rgba(243,239,230,0.14)"  # hover / lead-surface edge (two-step hairline scale)
  # Competitive identity (single hero color; pressure, not atmosphere)
  cfb-crimson: "#C5050C"       # --game-primary       — identity + interaction + hierarchy
  cfb-crimson-bright: "#E8282F" # --game-primary-light — hover; the ONLY crimson usable as text on midnight (large/bold only)
  # Editorial reading layer (bone/white as TEXT + contrast, never a body surface)
  cfb-bone: "#F3EFE6"          # primary body text on midnight (~16:1)                --game-accent
  cfb-white: "#FBF7F0"         # warm white — headlines, critical numbers
  cfb-bone-muted: "#B4AAA4"    # secondary copy (≥7.1:1 across the whole ramp)
  cfb-bone-subtle: "#938980"   # tertiary metadata (≥4.76:1 incl. --cfb-lifted; warm, never cool slate)
  # Survivor-state semantics (consequence + outcome; NEVER identity; aligned to platform live tokens)
  cfb-survived: "#64DBA0"      # alive / survived — platform --live-green
  cfb-lost-life: "#E63946"     # one life spent  — platform --live-red (distinct from identity crimson; AA as text on canvas/surface ONLY)
  cfb-eliminated: "#6E625F"    # out of the pool — warm ash (NEVER as text; background/border only, white on top)
  cfb-pending: "#9A8F88"       # unresolved      — muted warm bone (quiet, not alarming)
---

# Design System: CFB Survivor Pool

> Specialization of the platform design system. Top-level doctrine (palette framework, typography families, elevation, motion, design laws, cross-game components) lives in the repo root `DESIGN.md`; this file is the authority for everything CFB. When working any CFB surface, read this file alongside the top-level `DESIGN.md` (the CLAUDE.md hard rule).
>
> **Status.** The CFB room shipped (PRs #85–94: dark foundation, five player screens, eight admin screens, test locks). The room is a sanctioned dark-room exception under the top-level `DESIGN.md` §6 carve-out ("a game may establish a dark room as its entire body substrate when its `games/<slug>/DESIGN.md` documents the choice"). The CFB-era **lounge** design (C1 in the transition plan) is pending; §8 is its contract. Sections describing unshipped surfaces are marked **FUTURE**.
>
> **Provenance.** Merged 2026-07-20 from Brad's six doctrine documents (Design Doctrine, Identity System, Component Doctrine, Lounge Architecture, Room Architecture, Implementation Guidance) + the original dark-first foundation doc + the shipped-code audit (`docs/design-spine-audit-2026-07-20.md`). Token values and metrics verified against `static/css/style.css`.
>
> **How to read this document.** It is a design contract, not a collection of suggestions. When it distinguishes principles from examples, preserve the principle; examples may evolve. When a proposed feature conflicts with this doctrine, prefer the interpretation that best preserves: survival clarity, weekly decision urgency, progressive scarcity, strategic consequence, field awareness, and the emotional weight of becoming the final survivor. The interface must never become a generic sports dashboard, sportsbook, fantasy-statistics product, or an administrative table with a dark theme applied afterward. It should feel like a private Saturday-night competition whose pressure increases as choices disappear and the field grows quiet.

---

## 1. Product Philosophy

**Canonical product summary.** CFB Survivor is a season-long game of progressive scarcity. Every player begins with two lives. Every week, an active player selects one eligible college football team to win outright. A winning selection advances the player; a losing selection costs a life. A team used during the regular season cannot be used again during that regular season; eligibility resets at the CFP phase. The weekly outcome is binary; the season strategy is not. The competition is solitary at the moment of choice and social in the awareness surrounding it. The field visibly thins; the interface quiets as it does; the champion feels inevitable and deliberate rather than lucky.

### 1.1 The game is progressive scarcity

Every week reduces something: available lives, unused teams, future flexibility, surviving players, tolerance for mistakes, and eventually the number of possible champions. A correct pick keeps a player alive but permanently removes that team from the player's regular-season options. A wrong pick costs a life. A second wrong pick eliminates the player. The field does not advance by accumulating points — it contracts through survival.

Football is the mechanism that creates this scarcity. **Scarcity is the product's organizing principle.** Do not design CFB Survivor as a sequence of isolated weekly picks; design it as one continuous season-long decision under increasing constraint.

### 1.2 The central decision

Every weekly decision simultaneously answers two questions:

1. **How do I survive this week?** — immediate and binary; the team wins or loses.
2. **What future flexibility am I sacrificing?** — strategic and uncertain; using a strong team now weakens future options.

The interface makes both questions legible without pretending there is a mathematically perfect answer. It helps the player understand the consequence of a choice; it never instructs them to optimize one variable at the expense of all others.

### 1.3 Weekly outcomes are binary; season strategy is not

The interface may clearly state: whether a pick was submitted, whether the deadline has passed, whether a team won, whether a life was lost, whether the player is alive, and which teams remain available. It must **not** falsely imply: that one team is objectively the correct pick, that cumulative spread should dominate early decisions, that historical rank movement reveals meaningful strategy, or that the season can be optimized through a single score. The game is strategically rich because no one indicator fully captures the quality of a decision.

### 1.4 Survival comes before optimization

A player cannot benefit from a strong tiebreak position after being eliminated. Cumulative spread matters — it has decided real seasons — but it is not the weekly objective. **Spread is the tax on short-term thinking, not the purpose of the game.** It reminds players that repeatedly choosing the easiest favorite carries a long-term cost. Keep it visible enough to support strategy, subordinate to the immediate need to survive. Therefore: do not visually present the lowest spread as automatically best, do not reward dangerous picks with celebratory optimization language, and do not let tiebreak information overpower survival information.

### 1.5 Team availability is the player's strategic inventory

The most important season-long resource is not a score — it is the set of teams the player has not yet used. Selection is irreversible once the deadline passes, so the unused-team pool becomes more valuable as the season advances. Two players with the same lives are not strategically identical when their remaining pools differ. Show the facts — which teams are used, which remain, when a selection locks, when the CFP reset changes eligibility — and avoid false precision (no invented "inventory strength" metric). The used-team ledger is not historical trivia; it is the material record of the player's strategic sacrifices.

### 1.6 Lives are permission to continue, not points

Two lives means survived without error. One life means active with no margin for failure — vulnerable, never styled as nearly-irrelevant or half-eliminated. Zero lives means eliminated; elimination is the true boundary. Communicate these conditions immediately, without requiring calculation. Do not convert lives into decorative badges detached from game state.

### 1.7 The field is a living organism

The collective contraction of the field is one of the game's most important stories: some players retain two lives, some fall to one, some are eliminated, eventually one remains. Aggregate field state (two-life count, one-life count, eliminated count, recent eliminations, survivors remaining) is the season's central narrative — not artificial analytics.

**Aggregate survival progression is meaningful. Personal rank movement usually is not.** CFB rank is a step function on a three-value ladder tie-broken by a float; individual rank-history charts, movement sparklines, and week-over-week position graphics imply more significance than the data supports. Do not add rank-history surfaces to make the product resemble another fantasy game. (This is a deliberate deletion relative to the WC lounge dossier, not an omission.)

### 1.8 The competition is solitary, punctuated by social awareness

The core act is solitary: review the slate, weigh the risk, choose a team, accept the consequence. But field awareness intensifies naturally across the season — late-season players care which teams others still hold, who has one life, and what outcome produces a sole survivor. Early-season design prioritizes the player's own decision; late-season design may give greater emphasis to the remaining field. The product should feel like a private decision made inside a shared pressure chamber.

### 1.9 The season has distinct psychological phases

The rules are stable; the psychology evolves. The interface should respond:

| Phase | Danger | Design emphasis |
|---|---|---|
| **Early — abundance** | Complacency; treating a pick as disposable | Make the pick, understand the deadline, team use is permanent. No endgame-style opponent analysis. |
| **Midseason — resource management** | Earlier choices begin constraining options | Comparing available teams, prior usage, the changing field distribution. Scarcity becomes tangible. |
| **Late — opponent awareness** | Matching vs. differentiating from other survivors | Who's left, remaining lives, used-team patterns, consequences of same-vs-different picks. |
| **Endgame — inevitability** | Noise | Quieter, concentrated. Remove modules; let remaining names, lives, picks, and consequences carry the weight. |

### 1.10 League rules that bind design

These are Brad's binding rulings (pre-launch audit, closed 2026-06-24) plus shipped mechanics. Design and copy must match them exactly — never claim more than the rules support:

- **Two lives**; second loss eliminates. One pick per week, win outright.
- **A regular-season team is consumed on use.** Week 15 (Conf Championships) consumes a regular-season team — intended. The **CFP reset** activates at week 16: any of the 12 playoff teams is pickable even if used in the regular season.
- **Missed pick:** the deadline surrenders the choice. Post-deadline autopick assigns the largest available favorite (consuming that team and its spread). Autopick is the safety net, not a substitute for the penalty — result processing covers active enrollments, not just picks, so a no-pick week costs a life when no pick could be assigned.
- **Canceled/postponed games = "No Contest" push semantics:** no life loss, counts as survived, spread excluded from the tiebreaker, team stays consumed, the week can complete.
- **Spread locks at first fetch** (Tuesday lines); manual admin entries also lock. **16.5+-point favorites are ineligible** — the spread is a survivor rule, never a wagering line.
- **Cumulative-spread tiebreaker is lifetime** (no CFP reset): lower is better; favorites add, underdogs subtract; No Contest excluded.
- **Revival** only on a whole-pool wipe with all games decided; >1 picked-and-lost players revived; no-pick eliminations never revived. A sole remaining player at week's end is champion immediately (never revived).
- A season may conclude by tiebreak rather than a single natural survivor. The language of the result must match the actual mechanism — never say "sole survivor" when a tiebreak decided it.

---

## 2. Design Invariants

Permanent product truths. Future redesigns may change layouts, components, typography, animation, or technology; they must preserve these. When an implementation choice conflicts with an invariant, the invariant wins.

### 2.1 Survival state is immediate

Every visit must immediately answer: *Am I alive? How many lives do I have left?* No table inspection, icon decoding, or memory of last week required. If eliminated, say so plainly. One life: make the vulnerability clear without treating the season as over. Two lives: communicate margin without implying safety.

### 2.2 Every unmade pick is visually urgent

While picks are open and an active player has no valid pick, that state must be unmistakable — not discoverable only after entering the room, not buried below standings, not a small badge. On the room's landing page, the player's card outranks the standings when a pick is missing. The hierarchy should resemble:

> YOUR CARD
> You have not made a pick.
> [ Choose Team ]

The exact copy and component may evolve. The urgency may not. An unmade pick is the most important unresolved action in the product.

### 2.3 Every pick becomes irreversible at the deadline

The design clearly distinguishes selected, submitted, changeable, held, locked, and resolved states. No casual edit affordances after lock; never visually imply a locked choice remains negotiable. The moment of commitment carries weight because it permanently affects both survival and future availability.

### 2.4 Every weekly choice expresses present risk and future cost

Do not collapse the tension into a recommendation score. Do not imply the largest favorite is always correct, or the smallest spread strategically superior. Present the evidence. Preserve the dilemma.

### 2.5 The field must visibly thin

Players should always be able to understand how many remain active, how many hold two lives, how many are down to one, how many are out. The product must feel different when thirty players remain than when three remain.

### 2.6 Team scarcity must become more valuable over time

Early presentation may keep team history compact; mid/late-season presentation makes availability easier to inspect and compare. Show the facts; avoid false precision.

### 2.7 Critical state may appear in more than one place

CFB has fewer independent data dimensions than most fantasy products, so important information may appear in both the lounge and the room. **This is intentional controlled redundancy.** Both surfaces may show pick status, deadline, survival state, lives, survivor counts, and compact standings context. The distinction is not exclusivity — it is depth, purpose, and next action. A missed pick is more damaging than duplicated information; a confused survival state is more damaging than architectural purity.

### 2.8 The interface should quiet as the field narrows

Visual intensity does not increase because stakes increase. The strongest endgame expression is **reduction**: fewer modules, less decorative density, more space around consequential information. The final week should feel sparse, tense, and ceremonial — not busy.

### 2.9 The champion must feel deliberate

The conclusion reveals the path that produced it: survived every stage, lives remaining, teams used, final pick, how the field narrowed, why no other active player remains. Celebration emerges from evidence, finality, and reduction — never confetti-first.

---

## 3. The Room and the Lounge

### 3.1 The axiom and the surfaces

> **The room is where you play. The lounge is why you return.**

This describes dominant purpose, not an exclusive division of data. Concretely, on this platform:

- **The lounge** is the platform home (`/`) — the club lounge, CCC purple/gold substrate, dominated by whichever game is live. Its CFB-era design is C1 work, governed by §8.
- **The room** is the `/cfb/*` cluster — the midnight substrate, §6's identity system, the five player screens plus admin.
- **The room's landing** is `/cfb/` — the standings/home experience ("The Survivors"), the player's primary orientation surface *inside* the room.

The room is operational: act, compare, inspect, verify. The lounge is orienting and social: notice, understand, remember, return. Both surfaces preserve critical survival and pick state (invariant 2.7).

**Substrate boundary (load-bearing).** §6's midnight identity governs the room only — the dark doctrine stops at `body.game-cfb`. The lounge keeps the platform's CCC purple/gold identity; CFB enters the lounge through **content, copy, and state** (survival counts, lives, the summons, the verdict), never through substrate. This is the platform's lounge-vs-room architecture (CLAUDE.md; transition plan §5): substrate distinction between the lounge and a game room is by-design separation, not whiplash.

### 3.2 The room's landing page

The canonical CFB landing page is the standings/home experience. It is not merely a leaderboard. It answers, in order: *Am I alive? How many lives do I have? Have I made this week's pick? When does the decision lock? What is happening to the field? Where do I go to act?* When the active player has not made a pick, their card outranks the standings. Returning must feel immediately useful even when no new pick is required.

### 3.3 The lounge owns orientation

The lounge summarizes: survival status, lives, pick status, time until lock, aggregate field health, recent eliminations or verdicts, commissioner voice, and the route to the next meaningful action. It may include compact standings. It answers: *Does the club need me? Am I still alive? Have I done what this week requires? How is the field changing? What happened since I last looked? Where should I go next?* It makes the competition feel present even when no action is required. It does not attempt to become the complete evidence surface.

### 3.4 The room owns participation and inspection

The room contains the complete versions: choose a team, review the slate, inspect spreads, confirm eligibility, see used and unused teams, understand lock state, review detailed standings, inspect weekly results, verify season history, understand championship conditions. The room must repeat critical status where omission could confuse — a player should never enter the room and have to search for whether they still need to pick.

### 3.5 Primary ownership, not exclusive ownership

| Fact | Lounge (summarize + route) | Room (complete + act) |
|---|---|---|
| Pick status | no pick / submitted, deadline, route to choose or review | current selection, eligible alternatives, submission controls, changeability, lock state, result |
| Standings | compact field view, top survivors, current user, life counts, recent eliminations, route to full | complete standings, cumulative spread, detailed picks, tiebreak context, history |
| Field progression | survivor count, two-life vs one-life distribution, notable change | complete player-level state, elimination history, the evidence behind the summary |
| Deadline | prominent summons + countdown | exact lock state integrated with the pick controls |

This overlap is purposeful reinforcement at the depth appropriate to each surface — never remove essential state from one surface to preserve theoretical purity.

### 3.6 Depth determines placement

The question is not "which page owns this fact forever?" but **"what version of this fact does the player need here?"** If the player only needs to notice, orient, remember, or return — the lounge may suffice. If they need to act, compare, inspect, verify, sort, or investigate — the room provides the complete version. Critical to survival or participation — it may appear in both. **The lounge summarizes. The room completes.**

---

## 4. Product State Model

### 4.1 Weekly states

The weekly experience is a progression of four canonical states. These labels are the product's conceptual vocabulary — use them consistently in code, tests, and doctrine (shipped UI copy may render friendlier labels, e.g. "Locked In"):

- **OPEN** — the week is active, the deadline has not passed, and the player has **no valid pick**. Emphasize: available action, remaining time, eligible teams, and the consequence of not acting. This is the highest-urgency state.
- **HELD** — a valid pick exists and remains changeable under the rules. Emphasize: the current choice, confirmation that the obligation is presently satisfied, remaining time, and that the selection is not yet final. Never imply permanent commitment before the actual lock; never celebrate a held pick — the team still has to play.
- **LOCKED** — the deadline has passed; the pick is final and unresolved. Emphasize: irreversibility, the selected team, game status, the transition from decision to consequence. Remove or clearly disable edit affordances; locked must not read as "broken."
- **VERDICT** — the game resolved and the consequence is known. State clearly: win or loss, whether a life was lost, updated lives, whether the player remains active, and the effect on the field. Factual and final — never obscured behind decorative celebration.

### 4.2 Season states

- **PRESEASON** — explain the core rules, establish the first deadline, show that everyone starts with two lives. Create anticipation without pretending standings exist.
- **ACTIVE** — prioritize weekly action, survival status, team availability, field progression.
- **ELIMINATED** — unambiguous, but not exiled: eliminated players still follow the field, review history, see the champion, participate socially. The interface changes from participation mode to **observation mode** — never keep pick controls actionable.
- **CHAMPION** — one player remains under the rules. Distinct through clarity, space, and finality; shows the path of survival rather than generic celebration.
- **COMPLETE WITHOUT SOLE SURVIVOR** — if the season concludes by tiebreak, explain the deciding mechanism plainly. The language must match the rules (§1.10).

### 4.3 Player states

- **Two lives** — active, no losses yet. Tone: stable, not invulnerable. Never describe as "safe."
- **One life** — active, one loss recorded, next loss eliminates. Tone: vulnerable, still fully alive. Never styled half-eliminated.
- **Eliminated** — no lives, no further picks, may observe. Tone: direct, final, respectful. Never hidden behind a crossed-out row alone.
- **Champion** — the terminal winner under the actual rules. Tone: singular, evidenced, deliberate.

### 4.4 The Summons

The lounge's most important weekly module: it tells the player whether the competition currently requires something from them. It is the direct voice of the game, not a notification card, and it **evolves with the state of the week** — commanding when unanswered, confirming when held, acknowledging when locked, reporting when the verdict is known. It never becomes a static promotional banner. Full spec: §8.9.

### 4.5 Who's Left

The lounge's primary field-awareness module: the shape of the surviving competition without reproducing the standings interface. Its emphasis shifts with the season — broad counts early, life-distribution and attrition midseason, names late, the whole remaining field at the end. It makes the field feel alive and diminishing; it never becomes a decorative chart disconnected from actual players. Full spec: §8.10.

---

## 5. Decision Priorities

When designing or modifying any CFB surface, use this priority order:

1. **Preserve survival clarity.** Can the player immediately tell whether they are alive, how many lives remain, and whether this week changed that? If not, fix this before refining anything else.
2. **Surface the unresolved obligation.** Whether a pick is required, whether one has been made, when it locks. A missing pick dominates the page hierarchy.
3. **Support the decision.** Which teams are eligible, which are used, the matchups and spreads, what future resource is being consumed. No decorative data before these are answered.
4. **Show the field.** How many remain, how lives are distributed, how the field changed. Context — never a distraction from an unresolved pick.
5. **Preserve the season story.** Prior decisions mattered; the path from opening week to now is reconstructable; the champion's season can be replayed. History supports consequence and narrative — it does not exist merely because data is available.

### Governing principles

- **Atmosphere must serve comprehension.** Tense, private, nocturnal, consequential — but never at the cost of status, deadlines, controls, eligibility, or outcomes. Pressure comes from the decision mattering, not from the interface being hard to read.
- **Restraint is more powerful than noise.** Contrast, scale, spacing, and reduction before extra borders, badges, charts, gradients, animation, or copy.
- **Evidence before recommendation.** The game supports judgment; it does not replace it.
- **Consequence before celebration.** Show what happened, what changed, what remains — then celebrate where appropriate.
- **Controlled redundancy is acceptable.** Repeat critical state with purpose, adjusting depth to the surface (invariant 2.7).
- **The product must age with the season.** Week 1 and the final week share an identity, not a density. The season is a state machine; the interface acknowledges it.

---

## 6. Identity System

### 6.1 Visual character

> **Warm midnight, restrained crimson, ceremonial reduction.**

The identity is a private, high-stakes Saturday-night competition — most at home late at night, after games have finished, when results are settling and the surviving field is smaller than it was that morning. It supports urgency without becoming frantic, intensity without aggression, football without mascots, turf textures, stadium clichés, metallic gradients, or broadcast ornament. The design should feel deliberate enough to hold tension even when very little is on screen.

- **Warm midnight** — dark-first; the darkness feels warm, inhabited, atmospheric: a room after the lights are lowered, a stadium long after the crowd has gone. Never sterile charcoal that reads as developer tooling or a financial terminal; never absolute black across large surfaces. Nocturnal, not empty.
- **Restrained crimson** — the product's identity color: authorship, focus, tradition, commitment. Never a generic error color (§6.5).
- **Ceremonial reduction** — important states get stronger through subtraction: fewer competing elements, more whitespace, simpler borders, stronger type hierarchy. A locked pick feels final because fewer actions remain; a champion feels important because the field and interface have been reduced to one. Greater importance never requires more decoration.

**Platform fiction.** In CCC's editorial fiction (the Commissioner's Club Tribune), CFB is the Tribune's **survival desk** — the same newsroom as WC's light editorial desk, pointed at gridiron Saturdays and the weekly cut. The two desks' visual identities diverge hard on purpose: the midnight ramp is tinted *warm, toward crimson*, so the CFB room reads as its own night and never as WC's cool navy — two dark-leaning games must not both read "blue-dark." The descent through chrome is continuous: council-purple navbar → near-black sub-nav → midnight-and-crimson hero → midnight body → purple footer cap.

### 6.2 Dark-first doctrine

Dark is not an alternate theme; it is the canonical visual environment, scoped to `body.game-cfb` and stopping there (never the lounge, WC, Golf, auth, or shared chrome). **Dark-first does not mean low-contrast.** The interface must remain clear in dim rooms, bright mobile environments, low-quality displays, and reduced-brightness settings. Never rely on barely-perceptible differences between adjacent dark surfaces. Use darkness for atmosphere; use contrast for comprehension. **The room is dark, not dim.**

### 6.3 The shipped palette

The palette is deliberately narrow: four independent layers that must never collapse into one another. Assign color by semantic role, never by preference.

1. **Environmental substrate — the warm midnight ramp.** The room itself. Elevation = stepping UP the ramp plus a bone hairline, not a drop shadow.

   | Role | Token | Value | Purpose |
   |---|---|---|---|
   | Canvas | `--cfb-canvas` | `#0E0A0C` | page background, room backdrop |
   | Surface | `--cfb-surface` | `#150F12` | standard cards, tables, structural surfaces |
   | Raised | `--cfb-raised` | `#1E1518` | elevated / active containers |
   | Lifted | `--cfb-lifted` | `#281D20` | highest non-ceremonial elevation (sticky bars, overlays) |
   | Hero origin | `--game-primary-dark` | `#1A0B0D` | the `.page-hero` gradient start |
   | Hairline | `--cfb-hairline` | bone @ 8% | resting edge |
   | Hairline strong | `--cfb-hairline-strong` | bone @ 14% | hover / lead-surface edge |

   Use elevation sparingly and architecturally, never dashboard-like. If every panel is raised, nothing is.

2. **Competitive identity — crimson.** `--cfb-crimson` `#C5050C` (`--game-primary`) and `--cfb-crimson-bright` `#E8282F` (`--game-primary-light`). Crimson earns its force by contrast against the dark, not by volume: action, commitment, selection, "this is the active CFB layer." It may tint localized surfaces but must not dominate layouts — no large crimson containers, crimson page regions, or multiple competing crimson focal points.

3. **Editorial reading — bone/white as text and contrast, never a body surface.** `--cfb-bone` for body text, `--cfb-white` for headlines and critical numbers, `--cfb-bone-muted` for secondary copy, `--cfb-bone-subtle` for tertiary metadata. Reserve the brightest values for what matters most. Do not build large bone/white panels on midnight — a light card on the dark room reads as a hole punched in the page (the dashboard-island failure).

4. **Survivor-state — consequence, never identity.** `--cfb-survived` (green), `--cfb-lost-life` (bright red), `--cfb-eliminated` (warm ash), `--cfb-pending` (muted bone). Deliberately separate from the identity layer; status is the heart of the game and must stay scannable in dark conditions — never by hue alone (§6.7).

**Token strategy (how the room goes dark).** CFB does not invent a parallel surface-token set — platform components read `--bg-card`, `--border`, `--bg-muted`, `--text-primary/-secondary/-muted`, and the shadow scale. The shipped doctrine **rebases those platform tokens onto the midnight ramp under `body.game-cfb`**, and goes further than the platform tokens alone:

- Structural: `--bg-page`, `--bg-card`, `--bg-muted`, `--border`, `--border-light` → ramp + hairlines; `--text-primary/-secondary/-muted` → bone ramp.
- **Bootstrap base tokens** are rebased too (`--bs-body-bg`, `--bs-body-color`, `--bs-primary`, `--bs-primary-rgb`, `--bs-emphasis-color`, `--bs-secondary-color`, `--bs-border-color`) so un-styled Bootstrap components (accordion, list-group, dropdown, modal) don't punch white holes in the dark room.
- **The shadow scale is neutralized** to warm near-black — purple-tinted platform shadows are wrong on midnight, and shadows are near-invisible on dark anyway. Elevation is expressed by the ramp + hairline instead (the Elevation-by-Midnight Rule).

This keeps platform inheritance intact while flipping the room dark. Locked by `tests/test_cfb_dark_foundation.py`.

### 6.4 Contrast constraints (verified)

Computed WCAG 2.x ratios of each foreground against the ramp. These are use-constraints, not trivia — every value below binds where a color may appear as text:

| Foreground | canvas | surface | raised | lifted | Text-use constraint |
|---|---|---|---|---|---|
| `--cfb-bone` `#F3EFE6` | 17.1 | 16.5 | 15.6 | 14.2 | unrestricted |
| `--cfb-white` `#FBF7F0` | 18.4 | 17.7 | 16.7 | 15.3 | unrestricted |
| `--cfb-bone-muted` `#B4AAA4` | 8.6 | 8.3 | 7.9 | 7.2 | unrestricted |
| `--cfb-bone-subtle` `#938980` | 5.7 | 5.5 | 5.2 | 4.8 | unrestricted (tuned to clear lifted) |
| `--cfb-survived` `#64DBA0` | 11.4 | 11.0 | 10.4 | 9.5 | unrestricted |
| `--cfb-lost-life` `#E63946` | 4.7 | 4.5 | **4.3 ✗** | **3.9 ✗** | **as text: canvas/surface only** — place lost-red text on `--cfb-surface` or deeper (the shipped `.spread-badge` and destructive admin buttons sit on surface for exactly this reason) |
| `--cfb-pending` `#9A8F88` | 6.2 | 6.0 | 5.7 | 5.2 | unrestricted |
| `--cfb-eliminated` `#6E625F` | **3.4 ✗** | **3.2 ✗** | **3.0 ✗** | **2.8 ✗** | **never as text** — background (with `--cfb-white` on top) or border only |
| `--cfb-crimson` `#C5050C` | **3.2 ✗** | **3.1 ✗** | **2.9 ✗** | **2.6 ✗** | **never as text** — fill, border, and rule only, with bone text on top |
| `--cfb-crimson-bright` `#E8282F` | **4.5 ✗** | **4.3 ✗** | **4.1 ✗** | **3.7 ✗** | **large/bold text only** (≥3:1 large-text threshold; clears nowhere at 4.5:1) |

Verify contrast on every new midnight surface, including raised/lifted and the worst-corner pixels of the midnight→crimson hero gradient. Muted bone is support, never decoration.

### 6.5 Crimson is identity, not danger

The most important rule in the visual system, and CFB's one real color risk: crimson and the survivor lost-red are both reds, and a survivor pool's dominant event is losing.

**Use crimson for:** selected navigation, brand accents, primary CFB actions, active focus, key dividers, high-value labels, selected teams — the visual language of the game itself. A crimson button means "this is the primary CFB action," not "this action is dangerous."

**Never automatically use crimson for:** errors, missed deadlines, losses, elimination, destructive actions, invalid input, or system failure. Loss is carried *only* by `--cfb-lost-life` (the brighter, distinct red) and *always* with a structural cue: the hollow life pip, the `L` / `LOST A LIFE` / `OUT` label. Interaction is only crimson; consequence is only survivor-state. Danger is made explicit through direct language — "Pick required," "Deadline passed," "You have been eliminated" — never a red-tinted surface alone.

### 6.6 Semantic color roles — no traffic-light design

Do not reduce the product to green = good, yellow = caution, red = bad. That pattern is too simplistic for CFB's strategic ambiguity: a large favorite may be safer this week but strategically expensive; a one-life player is vulnerable but active; a locked pick is final but not yet good or bad. Color clarifies state; language explains; hierarchy prioritizes. The visual system represents state — it does not issue judgment beyond what the game actually knows.

- **Active/available:** neutral contrast + warm light text. Being alive is the default state, not a transactional success message — no bright green required.
- **Confirmed (held):** calm — subdued positive accent, check icon, direct status copy. Never victory styling; the team still has to play.
- **Locked:** finality through structure — lock icon, direct copy, removed edit controls, stable high-contrast presentation. Not grey alone (grey reads disabled/broken).
- **Win:** restrained positive accent. Relief and continuation, not completion.
- **Loss:** direct and consequential — explicit language + the life-state update. No excessive alarm styling.
- **Eliminated:** a terminal state, not a red version of an active card — direct language, reduced controls, transition to observer mode.
- **Champion:** space, singularity, finality, evidence. Never reduced to a color token.

### 6.7 Survivor-state semantics

| State | Token | Value | Meaning · emotional read | Constraint |
|---|---|---|---|---|
| Survived | `--cfb-survived` | `#64DBA0` | alive · confidence, continuation | — |
| Lost a life | `--cfb-lost-life` | `#E63946` | one life spent · pressure, setback | text on canvas/surface only (§6.4) |
| Eliminated | `--cfb-eliminated` | `#6E625F` | out of the pool · absence, closure | never as text (§6.4) |
| Pending | `--cfb-pending` | `#9A8F88` | unresolved · anticipation | — |

Primary consumers: `.lives-indicator`, the result chips, the outcome badges, standings outcomes, `.elimination-alert`, `.spread-badge` states, the `.cfb-verdict` top rule. State must survive without color — shape, fill, label, and position carry it (color-blind requirement).

### 6.8 Typography

The platform families are canonical and unchanged: **Teko** (display, labels, data, navigation), **Newsreader** (editorial reading). CFB's specialization is a register change, not a font change. Because the room limits color volume, typography, spacing, contrast, and composition carry more of the hierarchy and emotional pacing than on a light, color-rich surface.

Three registers, each with a distinct job:

- **Ceremonial** — the most consequential moments: section openings, major week titles, lock, verdict, elimination, champion, the final remaining field. Composed, authoritative, spacious. Larger scale, tighter wording, generous spacing. No theatrical effects: no chrome, bevels, outlines, glow, distressed sports lettering, or broadcast compression. Ceremony comes from confidence and reduction.
- **Operational** — pick controls, deadlines, table data, team names, spreads, lives, labels, buttons, states. Speed, clarity, compactness, reliable scanning. Legible at mobile sizes. **Tabular figures** where numbers align for comparison: countdowns, spreads, standings, week numbers, cumulative values. All-caps only for short labels (YOUR CARD, LOCKED, VERDICT, WHO'S LEFT, WEEK 8) — never large bodies of information.
- **Supporting** — explanatory text, secondary status, commissioner notes, helper copy, rule reminders. Quieter than operational but readable: **muted does not mean faint.** Concise, direct sentences — never a wall of instructions.

**Numbers carry the tension.** Survivor gameplay is numeric — lives, the week, rank, cumulative spread, survivor count, the deadline. Critical numbers should feel emotionally heavier than the copy around them, taking Teko display treatment normally reserved for headings. Not all numbers deserve equal weight: lives may be large and immediate; spread sits adjacent to the matchup; cumulative spread stays in the table; internal identifiers never appear. Every number gets a visible label or unmistakable context — never a bare "1" the player must decode (one life? first place? one week? one survivor?). Avoid decorative counters, tickers, and casino-style emphasis; typography makes numbers feel earned.

**Hierarchy is state-dependent.** The typical priority order — unresolved survival/pick state, primary action, lives + deadline, selected team or result, field status, standings, supporting explanation, metadata — shifts with the weekly state (OPEN leads with "You have not made a pick" + the action; VERDICT leads with win/loss + lives). A section title such as "Standings" must never visually overpower an urgent unresolved pick.

### 6.9 The Survivor voice (H1s)

User-facing CFB routes treat their H1 as Survivor-register editorial voice, not a literal route label — the Tribune spine localized to gridiron-Saturday attrition. This register is distinct from WC's civic-ceremonial cadence (Decree/Council); the two share an editorial parent and must not converge. **Shipped copy:**

| Surface | Shipped H1 |
|---|---|
| Standings / hub | "The Survivors" |
| Weekly results | "Saturday's Verdict" / cut weeks: "The Cut" (conditional) |
| Picks + My Picks | "Your Card" |
| Join | "Take Your Two Lives" |
| Champion moment | "One Remains" (eyebrow) |
| Rules | "House Rules" (shared club idiom) |

Platform dispensations carry over: (a) dynamic interpolated H1s read functionally because the value carries the voice; (b) logged-in utility auth surfaces keep functional H1s; (c) **admin keeps functional H1s** (§7's Commissioner's Desk). A flat functional H1 on a routine player-facing CFB tab is a regression — if a title could belong equally to a spreadsheet, a sportsbook, or an admin console, rewrite it.

### 6.10 `.cfb-eyebrow`

The CFB contextual-label primitive (analog to `.wc-eyebrow`): small uppercase Teko metadata above a headline — week, deadline, survivor count, status. **Shipped metrics: Teko 500, `.8rem`, letter-spacing `.15em`, uppercase, `--cfb-bone-muted` default** (calibrated for midnight). One variant:

- **`.cfb-eyebrow-crimson`** (`--cfb-crimson-bright`) — active/competitive signal. Sanctioned but currently unused in shipped templates, and deliberately narrow: crimson-bright clears AA only at large/bold sizes (§6.4), so reserve it for *sizeable* active labels — a current-leader callout, a deadline banner — never a small routine eyebrow, where bone-muted carries the metadata. CFB adds **no** gold eyebrow variant (the Crimson-Ceremony Rule).

On the hero, `.cfb-hero .cfb-eyebrow` lifts to bone @ .85 to clear the gradient.

### 6.11 Copy voice

Direct, calm, consequential — a confident commissioner, not a marketer. Brief, human, unambiguous, grounded in actual game state.

**Good:** "You have not made a pick." · "Your pick locks Saturday at 11:00 AM." · "Alabama is held. You may change your pick before the deadline." · "Your pick is locked." · "Ohio State lost. You have one life remaining." · "You have been eliminated." · "Three players remain."

**Never:** "Let's go!" · "Time to crush it!" · "Oops!" · "Better luck next time!" · "Your squad is on fire!" · "Make your epic pick now!" — the game already contains drama; the interface does not manufacture it.

**Survivor lexicon:** survive, the cut, rivalry week, under the lights, the slate, last standing, hold your lives, survive and advance, outlast, the verdict, still alive. **Avoid:** betting language, fantasy jargon, gaming slang, mascot humor, hype, and **tactical/military framing** — the war-room mood is an internal north star only; no deploy/mission/command/tactical ever reaches user copy. The spread is framed as a survivor rule, never wagering.

**Commissioner voice** may be warmer and personal — reminders, rulings, weekly notes, dry humor ("Miss it and the Commish picks for you"). It reinforces rules; it never replaces them: a commissioner message must never be the only place critical state appears. The system must still state pick status, deadline, and consequence directly.

**Em dashes and double hyphens are banned in UI copy** — error messages, button labels, and any prose generated for CCC surfaces (the platform Copy Discipline; doc prose like this file is exempt). **Pluralization must be correct:** 1 life / 2 lives; 1 player remains / 2 players remain.

### 6.12 Labels and naming

Canonical labels, used consistently: **YOUR CARD · THE SUMMONS · WHO'S LEFT · THE ROOM · THE LOUNGE · OPEN · HELD · LOCKED · VERDICT.** Do not create multiple names for one state (saved/pending/entered/tentative/submitted) unless the underlying states genuinely differ. State language maps to actual behavior: if HELD means "exists but changeable," it means that everywhere.

### 6.13 Material rules

- **Borders and edges:** quiet and purposeful — the hairline scale is the edge system. Do not outline every card, row, chip, and container; excess borders make dark interfaces feel technical and crowded. Prefer spacing, tonal contrast, alignment, selective rules. A crimson rule is an identity moment, used sparingly — never default decoration.
- **Corners:** platform radii (`--radius` .5rem, `--radius-lg` .875rem). No separate shape language per component type; tables and dense comparison surfaces may run tighter; terminal states may drop containers altogether.
- **Shadows:** neutralized on midnight (§6.3). Elevation through ramp + hairline. Real shadow only for genuine overlay layers (dialogs, dropdowns); the one sanctioned glow is the selected pick's localized crimson (§7). Cards do not float.
- **Texture and imagery:** identity must not depend on texture. Acceptable: extremely subtle tonal variation, soft vignette, faint light falloff. Banned: turf, chalkboard, carbon fiber, brushed metal, stadium floodlights, smoke, sparks, helmets, generic football photography behind UI. Atmosphere comes from composition, color, typography.
- **Iconography:** one coherent style (shipped: Bootstrap Icons). Icons support recognition, never replace language — critical state always includes text ("Locked," not merely a padlock). No emoji or decorative sports symbols in state communication.
- **Team identity:** teams appear inside the product's environment — the product owns the room. Team name, abbreviation, and limited supporting color; no full team-color advertisements per matchup card; no high-saturation team colors across large surfaces. The shipped room is typography-based (no logos) and must remain fully usable that way; if logos arrive later they get consistent sizing, clear space, no effects, and legibility against dark surfaces.

### 6.14 Motion and countdowns

Motion is restrained and functional: clarify a state change, a selection, a new lock, an updated verdict. No continuous animation, pulsing countdowns, flashing warnings, or celebratory motion on ordinary actions. An unmade pick is urgent through hierarchy and language, not movement. Terminal states may use a brief transition; ceremony never depends on spectacle. Respect `prefers-reduced-motion`; the product must be fully understandable without animation.

Countdowns stay calm and precise: clear units, stable alignment (tabular figures), direct deadline copy. Pair relative time with the exact deadline where practical — "Locks in 3h 18m · Saturday, 11:00 AM." No ticking layout shift, oversized digital-clock styling, red flashing numerals, or second-level urgency hours before action is required. Urgency escalates through hierarchy as the deadline approaches (stronger placement, primary action adjacent, nothing competing above it). When the deadline passes, the component immediately becomes lock state — never a stopped "0m" timer.

### 6.15 Prohibited visual directions

Do not turn CFB Survivor into any of the following:

- **Sportsbook** — betting slips, odds-board density, neon price movements, market arrows, wagering language, ticket layouts. Spreads are strategic evidence, not betting products.
- **Broadcast package** — metallic gradients, 3D logos, lower-thirds, animated score bugs, stadium-light effects, TV clichés. A private competition, not a live broadcast.
- **Generic fantasy dashboard** — dense KPI rows, arbitrary charts, trend lines without meaning, metric cards for every number, equal-weight modules. CFB has a small number of meaningful states; give them room.
- **Ops-center / mission-control** — banks of readouts, glowing live panels, telemetry aesthetics. The trap a dark room invites most; refuse it.
- **Video game** — XP bars, level-up language, glowing achievements, arcade victory effects.
- **Corporate admin tool** — sterile grey tables, generic blue actions, component-library defaults with no atmosphere.

### 6.16 Named rules

- **The Dark War Room Rule** — CFB is dark-first; midnight is the default body substrate; new CFB surfaces start dark and must justify moving lighter.
- **The Crimson-Is-Identity Rule** (the central CFB discipline) — crimson reads as school-color identity and interaction, never danger or loss. Loss is carried only by `--cfb-lost-life` with a structural cue; interaction only by crimson. State by structure + label, never color alone. (§6.5)
- **The Crimson-Pressure Rule** — crimson is pressure, not atmosphere. When several elements compete for crimson attention, *reduce* usage until emphasis is meaningful again.
- **The Elevation-by-Midnight Rule** — hierarchy through substrate depth before color: a deeper or raised midnight plus the hairline before any accent. Architectural, not dashboard.
- **The Crimson-Ceremony Rule (no gold in CFB)** — CFB does not adopt gold as a game-level ceremonial organizer; that is WC's move, and a dark room reaching for gold would read as WC. CFB's ceremony is crimson restraint on midnight. Platform gold stays where the platform owns it (the lounge, navbar CTA, platform focus rings outside the room); CFB never introduces gold into its body or ceremonial surfaces — including the champion state, whose strongest signals are space, singularity, finality, and evidence, not color. (Shipped and test-locked: the hero dot overlay, admin masthead, and focus rings all went crimson.)
- **The Ceremony-by-Reduction Rule** — because the room is already dark, ceremony cannot mean "darker." Endgame moments escalate through reduction: more negative space, less density, concentrated contrast, stiller composition.
- **The Traffic-Light Ban** — never green=good / yellow=caution / red=bad as the product's semantic system. (§6.6)

---

## 7. Component Doctrine

### 7.1 Purpose and philosophy

Components express product meaning, not reusable boxes. Every component answers at least one of: *What state is the player in? What action is required? What decision is being made? What has already been sacrificed? What changed in the field? What is now final? What should the player inspect next?* A component that displays information without clarifying one of these is suspect — the product does not accumulate modules because data exists.

The default component is quiet. Visual strength is reserved for unresolved obligations, changing survival state, locked decisions, verdicts, elimination, and championship. **A page has one clear center of gravity** — never an equal-weight card grid, never every module independently branded. Prefer fewer components, stronger internal hierarchy, deliberate spacing, meaningful state transitions. The same component may appear in lounge and room; its depth, density, and actions reflect the surface.

### 7.2 Shipped primitives

Doctrine grounded in the classes that exist. (R1 ruling, 2026-07-20: lead emphasis in CFB verdict surfaces is carried by **outcome color, not identity crimson** — ratified from the shipped implementation; see `.cfb-verdict`.)

#### The weekly call — `.cfb-pick-cta`

The room's summons: the strongest routine CTA, answering *what is my decision this week?* Crimson 3px top rule over an elevated midnight surface, concise typography, visible deadline (`.cfb-deadline`), the status row (`.cfb-status-row/-item/-num/-label`: lives + rank + spread), and the primary action. On the room landing it sits above the standings and must never be buried beneath standings, history, or explanatory text while picks are open. Player-card states it must support: no pick (action dominates), held pick (team + spread chip + Change Pick), eliminated ("Your season ended. The pool plays on." — no action), locked, verdict.

#### The pick surface — `.team-pick-card` + the pick control

The most important interaction primitive: selecting a team should feel like making a decision, states escalating with commitment:

- **Resting** — available: surface substrate, subtle hairline, calm, clear team hierarchy.
- **Hover/focus** — possibility: half-step elevation, restrained crimson border lift, visible keyboard focus.
- **Selected** — commitment: structural lock-in + crimson perimeter + a localized crimson glow (**the one sanctioned glow in the room**) + stronger team weight. Never a subtle tint alone.
- **`.ineligible`** — cold and procedural (used, game started, spread restriction, deadline passed): reduced contrast, suppressed interaction, an **explicit reason** — never a raw opacity collapse (test-locked), never punitive.

The pick control distinguishes **choosing → holding → submitting → changing → locked** unambiguously. Selection alone never implies submission; the confirm bar (`.cfb-confirm-pick`, "Your Call") names the object of the action ("Submit Georgia," never bare "Submit"). After lock, no edit affordance remains — a disabled control without explanation is a bug, not a state. Confirmation copy is factual: "Pick confirmed" yes; "Great choice" no.

**JS hooks:** the pick flow is driven by `data-team-id` / `data-game-card` / `.team-option`. Audit every `querySelector`/`data-*` hook before renaming any class; add CSS classes alongside JS-critical ones rather than renaming (platform template-restyling rule).

#### The spread — `.spread-badge` (`.favorable` / `.unfavorable`)

The custom-game signature (PRODUCT.md "custom games earn custom layers"), presented with deliberate restraint: a compact typographic chip, subdued contrast, secondary hierarchy — informed strategy, not active wagering. Neutral default; `.favorable` lifts toward survived-green, `.unfavorable` toward lost-red; sits on `--cfb-surface` so lost-red clears AA (§6.4). Consistent signed formatting (`-7.5`, `+3`); no unsigned ambiguity. No large chips, directional betting arrows, odds-board styling, or dramatic color shifts — players notice the spread when *deciding*, not when scanning.

#### Lives — `.lives-indicator` / `.life` / `.life.lost`

Survival at a glance: an inline row of pips, one per life. Held = filled (survived-green), confident; lost = hollow/outlined (ash), reduced; an eliminated row reads drained and quiet. Clean and geometric — no hearts (casual/game-y), no health bars or percentage meters (lives are discrete states, not continuous health), no stitched-football/yard-marker skeuomorphism (platform ban). State survives without color: fill + outline + position carry it. Compact text labels stay available ("2 lives" / "1 life" / "Eliminated" — never a bare "0").

#### Result chips — `.badge-survived` / `.badge-lost-life` / `.badge-pending`

The weekly verdict at chip scale: `SURVIVED`/`W`, `LOST A LIFE`/`L`, `PENDING`/`TBD`. Compact, high-contrast, text-readable. **`.badge-pending` is hollow (outline) by doctrine** — distinct from the filled survived/lost chips *by structure, not hue* (the Crimson-Is-Identity Rule applied to chips). A chip records consequence; it does not throw a party.

#### Outcome badges — `IN` / `OUT` (`.badge-eliminated`, `.badge-xs`)

Season position; administrative, not emotional.

#### The verdict family — `.cfb-verdict` (+ `.is-survived` / `.is-lost` / `.is-pending`), `.cfb-week-summary`, `.cfb-season-lead`

The room's raised information surfaces: `--cfb-raised` substrate, strong hairline, and a 2px top rule **colored by outcome state** — survived-green, lost-red, or pending-bone, never crimson (the ratified R1 contract: outcome carries outcome; crimson stays identity). `.cfb-verdict` carries the weekly result (team, matchup, score, outcome chip, lives consequence); `.cfb-week-summary` + `.cfb-summary-*` carry week aggregates; `.cfb-season-lead` opens My Picks with the season line. Internal shape: eyebrow → headline → primary value → supporting context → optional action. These are the room's information-density model: editorial readability with operational structure — surfaces designed for decisions, not telemetry widgets.

#### The Cut — `.elimination-alert` + `.cfb-cut-*`

Elimination rendered cold and final: a full-container treatment — full lost-red border over a restrained lost-red tint, bone-white title with a leading lost-red icon (the side-stripe was migrated off; the platform ban holds). Administrative consequence, not spectacle: the emotional target is "your season changed," never an emergency-red alarm, never shame. The Cold-Elimination Rule.

#### The ceremonial endpoint — `.championship-hero`

The last-one-standing declaration (analog to WC's `.wc-champion-banner`), single-purpose — never a reusable dark card, feature panel, or weekly-result hero. Its distinction is **ceremony through reduction**: the lights stay on, the room goes quiet, one survivor remains. Composition: expansive negative space, reduced density, strong vertical rhythm, concentrated contrast, minimal chrome; the midnight atmospheric field with crimson-tinted gradient + crimson dot overlay; `.champion-name` (Teko 700 uppercase, `--cfb-white`, clamp within the platform ≤6rem ceiling), final record, `.champion-subtitle` (Newsreader, retrospective), `.prize-badge` (crimson).

**Render gate (strict):** only when the pool has a single survivor — `enrollments|length == 1 and eliminated_enrollments|length > 0` on the standings route. Never speculative, mid-season, or contested. If a tiebreak decided the title, the language must say so ("CHAMPION — wins on cumulative spread"), never "sole survivor." No confetti, trophy overload, gold, particles, or animated spectacle. Victory feels earned, inevitable, slightly lonely.

#### The hero — platform `.page-hero` + the `.cfb-hero` content system

CFB uses the platform `.page-hero` directly: crimson is `--game-primary` and warm midnight `#1A0B0D` is `--game-primary-dark`, so the default 135° gradient already resolves to the midnight-and-crimson "under the lights" band. **Do not author a `.cfb-hero-grad`** (held in shipped code; the only grep hit is a comment affirming the ban). CFB-scoped details: the halftone dot overlay is **crimson**, not gold (`rgba(197,5,12,.10)`, test-locked), plus a crimson accent line, ambient `.hero-glow`, and a `.lead` contrast lift.

`.cfb-hero` is a *content* modifier, not a gradient override: it carries the hero eyebrow lift and the survivor-count field — `.cfb-hero-field` with `.cfb-count` ("N still standing") and `.cfb-count-cut` ("M cut") — answering "who is left standing?" in the masthead itself. Used on all five player screens.

#### Sub-nav — `.subnav-cfb`

Platform `.game-subnav` shape: background `#0a080f`, `--subnav-accent: #C5050C`, `--subnav-accent-rgb: 197,5,12`. The active pill feels *selected*, not illuminated; rest pills stay quiet bone-on-midnight; navigation orients and then disappears behind content. No per-route navigation languages.

#### Current-user identity — `.cfb-you-tag` + row tint

The standings row carries a structural "You" tag plus a crimson tint (`rgba(197,5,12,.12)`) — identity never rests on tint alone, and the tint-only convention (no side-stripe) is the settled platform pattern for current-user rows.

#### The Commissioner's Desk — admin cluster (`.cfb-admin-*` + the A3-admin block)

Eight admin screens with their own register, doctrine previously recorded only in CSS comments, now canonical:

- **Admin keeps a functional H1** — a deliberate exception to the Survivor voice; the desk is operational.
- **The Crimson-Ceremony Rule applies to admin:** the platform's gold masthead rule + gold eyebrow + purple H1 become a **crimson rule, bone-muted eyebrow, bone-white H1** here. No gold on the desk.
- **The focus ring is crimson** on CFB admin surfaces, replacing the platform gold ring (re-derived for the midnight substrate).
- **Destructive actions are a restrained lost-red *outline*, never a filled red shout** (Cold-Elimination register), placed on `--cfb-surface` so lost-red clears AA.
- **Inputs sit a step *deeper* than their card** (canvas, not surface) so fields read as inset wells.

Administrative components identify the affected player, show current state, explain the proposed change, require confirmation for consequential edits, and record an audit trail. Never unlabeled icons for irreversible actions. Player-facing surfaces must not leak administrative language or controls.

### 7.3 Shipped vocabulary inventory

101 `.cfb-*` classes ship in `style.css`, organized by family. This table is the map — inspect the CSS block for exact rules before styling adjacent work:

| Family | Classes |
|---|---|
| Hero content | `.cfb-hero`, `.cfb-hero-field`, `.cfb-hero-field-sep`, `.cfb-count`, `.cfb-count-cut` |
| Weekly-call status | `.cfb-status-row/-item/-num/-label/-total`, `.cfb-deadline`, `.cfb-eliminated-note` |
| Current-user | `.cfb-you-tag` |
| Pick / slate | `.cfb-holding/-team/-note`, `.cfb-slate-head/-count`, `.cfb-matchup`, `.cfb-kickoff`, `.cfb-team-name/-id`, `.cfb-home-tag`, `.cfb-at`, `.cfb-out-reason`, `.cfb-confirm-pick/-line`, `.cfb-empty-slate` |
| Verdict | `.cfb-verdict` (+`.is-survived/.is-lost/.is-pending`), `-team`, `-nopick`, `-matchup`, `-score`, `-outcome`, `-chip`, `-lives`, `-lives-label` |
| Week summary | `.cfb-week-summary`, `.cfb-summary-stat/-num/-label/-sep` |
| The Cut | `.cfb-cut-title/-list/-player` |
| Field ledger | `.cfb-field-table/-head/-week`, `.cfb-avatar`, `.cfb-cell-pick`, `.cfb-col-center`, `.cfb-pick-meta/-score`, `.cfb-auto-tag`, `.cfb-row-nopick`, `.cfb-nopick-note`, `.cfb-result-none` |
| Pick distribution | `.cfb-distribution`, `.cfb-dist-list/-item/-team/-count` |
| Season / My Picks | `.cfb-season-lead/-main/-aside`, `.cfb-season-headline/-derivation/-lives-label`, `.cfb-ledger-total` |
| Team pool / used | `.cfb-conf-count`, `.cfb-team-pool`, `.cfb-team-chip/-note`, `.cfb-used-grid/-team/-week`, `.cfb-now-tag` |
| Coverage | `.cfb-coverage`, `.cfb-coverage-grid/-item/-mark/-note` |
| Notes | `.cfb-spread-note`, `.cfb-board-note` |
| Join | `.cfb-join-rules/-form/-stake/-stake-row/-stake-copy/-stake-lead/-lives/-rule/-entry/-optional` |
| Admin | `.cfb-admin-masthead/-title/-sub/-chip` |

Five classes appear in templates with no CSS rule (`cfb-cell-player`, `cfb-cut-avatar`, `cfb-cut-name`, `cfb-pay-status`, `cfb-verdict-main`) — **treat as functional hooks until traced**; do not delete on sight.

Retired name: `.cfb-stat-card` (+ a CFB `.is-lead`) was planning-era vocabulary that never shipped — the verdict family (§7.2) is the real lead-surface system. Do not reintroduce the name.

### 7.4 Components sanctioned but not yet shipped (FUTURE)

Doctrine for surfaces the lounge (C1) and later room work will build. Marked so nobody reads them as existing code:

- **The deadline component** — exact date/time + relative countdown ("Locks in 4h 12m · Saturday, 11:00 AM"), repeated intentionally across player card, summons, room header, pick controls, compact lounge summaries. Urgency escalates by hierarchy (§6.14). At expiry it *becomes* lock state.
- **The survival status block** — larger life-state expression for card/verdict/elimination/champion views: state label + lives + concise explanation + next action ("ALIVE · 1 life remaining · Your next loss eliminates you."). Direct language; no euphemisms (inactive / season complete / out of contention) when the state is elimination.
- **Weekly state badges** — compact OPEN/HELD/LOCKED/VERDICT chips where detailed copy would be excessive. Sparing; shape/text/placement carry meaning, not a badge-color rainbow.
- **The matchup row** — compact slate alternative for scan speed on large slates: selectable region generous, spreads/kickoffs/status aligned, predictable heights. Cards vs rows is a deliberate density choice (§9.5), consistent week to week.
- **The used-team ledger** — the record of inventory spent: week, team, opponent, spread, result, life consequence. Chronological when telling the season story. On CFP reset, history is preserved and the reset is explicit ("Playoff reset active — regular-season teams are eligible again") — the reset changes future permission, not past fact.
- **The team availability panel** — remaining inventory: grouped Available / Used / Unavailable (reason) / Restored-by-reset; optional search + filters (available-only, ranked, playing-this-week) only where they support a real decision. Never reduced to a bare count ("112 teams available" is less useful than whether the strongest realistic options remain).
- **Who's Left** (§8.10) and **compact standings** (§8.11) — lounge modules.
- **Field attrition visualization** — aggregate survival progression where it adds understanding: stacked weekly bars, simple step charts, or a week-by-week table (`Week | Two lives | One life | Eliminated | Active`). Real counts, labeled, readable without color. Never smoothed curves, decorative area charts, percentage-only views, or personal rank trends.
- **Player detail** — another player's season path (survival state, lives, weekly picks, used teams, spread, elimination week), respecting pick-visibility rules; supports social awareness and verification, never surveillance.
- **Recent change module** (§8.13) — lounge orientation.

### 7.5 Component behavior rules

- **Confirmation and commitment.** Confirm where it reduces real error: irreversible submissions, immediate deadlines, commissioner overrides, destructive admin actions. Before the deadline, changing a pick stays simple; at the deadline, the *system* creates finality, not a dialog.
- **Alerts.** Reserved for information requiring attention, with distinct treatments: action required ("Pick required — choose a team before Saturday at 11:00 AM."), rule change ("Deadline updated…"), system problem ("Your pick could not be submitted. Try again. Your previous pick remains unchanged."), informational ("Playoff reset active…"). Never the same crimson alert for every message; never stacked alerts atop every page — persistent state lives in primary components.
- **Empty states** explain why and what's next; absence carries product meaning. "No pick has been submitted. Choose a team before Saturday at 11:00 AM." · "The full field remains alive." · "Week 1 has not been resolved." Never "Nothing here" / "No data." Stoic register: clear next steps when action is possible, calm closure when not; no playful emptiness, jokes, or over-encouragement. The message is: *the season continues.*
- **Loading** preserves layout and hierarchy (skeletons/placeholders, not content-area spinners); known survival state is never hidden while secondary data loads; unknown state renders as loading, never guessed (§10.10).
- **Errors** preserve trust: what failed, whether prior state is intact, what to do, whether the deadline is affected. "Your new pick was not submitted. Alabama remains your current pick. Try again before Saturday at 11:00 AM." — never "Something went wrong." A player is never left uncertain whether a pick was recorded.
- **Navigation and routing labels** say what the destination allows: Choose Team, Review Pick, View Full Standings, Inspect Used Teams, Review My Season. Never Learn More / Explore / Continue. One stable name per route — no standings/home/dashboard/overview drift.
- **Tabs** only for genuine peer sections; never to hide urgent pick state; persistent player status survives tab switches.
- **Buttons:** one primary per component; verbs with objects ("Submit Alabama," "Change Pick"); destructive admin actions never borrow crimson (§7.2 Commissioner's Desk).
- **Badges/chips:** compact state only; plain text where plain text suffices — a badge earns its container. No chip-fragmentation of reading surfaces.
- **Tooltips** are supplementary, keyboard/touch-accessible, and never the sole home of essential rules (why a team is unavailable, when the deadline is, whether a pick is locked).
- **Modals** sparingly (irreversible admin, unusual overrides, focused mobile inspection); the pick workflow is native to the page. Clear title, named action, keyboard support, focus return, no nesting.
- **Toasts** may confirm routine actions but are never the only confirmation — the persistent card/summons updates immediately.
- **Scores** serve the pick consequence; the selected game's score may be prominent, other games stay secondary. The room is not a live-score application. No provisional life changes while a game is in progress ("IN PROGRESS — Alabama leads Auburn, 21–17," never "You are advancing").
- **Exceptional games** (postponed/canceled) interrupt clearly and reflect the actual ruling (§1.10 No Contest): what happened, whether the pick remains valid, whether a repick is allowed, what deadline applies. Players never infer policy from schedule status.

### 7.6 State completeness

Every interactive component is designed for all relevant states: default, hover, focus, active, selected, submitted, loading, disabled, error, locked, resolved, unavailable. CFB is highly state-dependent — a polished default with unclear locked or error behavior is incomplete.

### 7.7 Responsive behavior

Components adapt by preserving meaning, not merely shrinking. Player card: unresolved action first, lives + deadline visible, history collapses. Pick card/row: team, opponent, spread, kickoff visible; selection target large; no hover-dependence. Standings: player, lives, official order preserved; secondary columns behind expansion; text never miniaturized; current-user row never hidden. Ledger: stacked chronological entries, not a miniature table. Who's Left: counts and names before decoration.

### 7.8 Component prohibitions

No components whose primary purpose is imitating another game: rank sparklines, generic KPI cards, betting tickets, player power scores, AI pick grades, unexplained confidence percentages, arbitrary heat maps, trend surfaces without meaningful dimensions. No card for every statistic, badge for every label, chart for every sequence, modal for every detail. The product stays small enough to understand — its depth comes from consequence, not interface volume.

### 7.9 Composition heuristic

Before adding or modifying a component, ask: What player question does this answer? Is the information urgent, strategic, social, or historical? Does the lounge need a summary, the room the complete version, or both? What changes across OPEN/HELD/LOCKED/VERDICT? What happens at two lives, one life, zero? Does this reveal product meaning or merely display available data? Can anything be removed without reducing comprehension? If unanswerable, the component is not ready.

Canonical composition orders — room landing: player card/summons → deadline + weekly state → compact field summary → standings → commissioner note → history. Room pick flow: player status + obligation → pick controls → slate → availability → standings/ledger → rules. Never a generic page title followed by buried state — the first meaningful component answers the most urgent question.

---

## 8. Lounge Architecture (C1 contract — FUTURE surface)

The CFB-era lounge is designed (C1) then built (C2) per the transition plan §5. This section is the contract that design executes. **Substrate note (binding):** everything here describes content, copy, hierarchy, and state; the lounge's visual identity remains the platform's CCC purple/gold lounge system — §6's midnight room identity does not apply at `/` (§3.1).

### 8.1 Purpose

The lounge is the CFB player's primary orientation surface — visitable without a decision in mind, understandable in seconds: alive? lives? pick required? when does it lock? how has the field changed? what does the Commish want known? where next? It is useful before, during, and after the weekly pick — not merely a gateway into the room, and not a second room: no full slate, no complete ledger, no complete standings table. It summarizes the competition and gives the player a reason to return.

### 8.2 Controlled redundancy

The lounge may repeat critical room state (pick status, selected team, deadline, lives, lock state, verdict, compact standings context, field counts) — intentionally. The lounge presents the shortest useful version; the room the complete operational version:

> **Lounge:** You have not made a pick. Locks Saturday at 11:00 AM. [ Choose Team ]
> **Room:** complete slate, eligible teams, spreads, used-team state, selection controls, exact lock behavior, evidence.

Never remove critical state from the lounge because it exists in the room.

### 8.3 The four-beat state machine

The lounge is designed around OPEN → HELD → LOCKED → VERDICT. State affects hierarchy, copy, actions, component visibility, and density — the lounge visibly evolves as the week progresses; it is never a static layout with one badge swapped.

### 8.4 OPEN — the summons dominates

The highest-urgency lounge state: the player is active with no valid pick.

> YOUR CARD
> You have not made a pick.
> 2 lives remaining
> Locks Saturday at 11:00 AM
> [ Choose Team ]

Then: compact field state, compact standings, commissioner note if relevant, secondary context. Standings never sit above the unresolved pick; no hero image, welcome message, or field chart competes with the action.

### 8.5 HELD — settled but not final

> YOUR CARD
> Alabama is held.
> You may change your pick before Saturday at 11:00 AM.
> [ Review Pick ]

Calmer than OPEN; field and standings may gain weight because the obligation is satisfied; current pick and lock timing stay visible. Never "locked in" / "final" language before the deadline; never celebrate a held pick.

### 8.6 LOCKED — decision mode becomes consequence mode

> LOCKED
> Alabama vs. Auburn
> Your pick is final.
> Kickoff Saturday at 3:30 PM. *(or: Alabama leads Auburn, 21–17.)*

No Choose Team / Change Pick / Submit affordances, no orphaned disabled buttons. The lounge quiets; field, remaining players, and game status may become more prominent.

### 8.7 VERDICT — explicit consequence

> WIN — Alabama defeated Auburn. You advance with two lives.
> LOSS — Alabama lost to Auburn. You have one life remaining.
> ELIMINATED — Alabama lost to Auburn. No lives remain.

Win tone: relief and continuation, never championship styling. Loss: the life change is prominent; the player remains active. Elimination: transition to observation. Hierarchy: verdict → updated lives → field impact → who's left → compact standings → route to full results. The verdict is never buried in a feed or carousel.

### 8.8 Outer states

- **Preseason:** "THE SEASON OPENS THIS WEEK — Everyone begins with two lives. Choose one winning team before Saturday at 11:00 AM. Once used, that team is unavailable for the rest of the regular season." Primary action: Enter the Room. Anticipation without fabricated standings; player list, commissioner note, rules summary, first deadline. No empty charts or placeholder trends.
- **Eliminated:** "ELIMINATED — No lives remain. Follow the remaining field and see how the season ends." Routes: View Who's Left, View Full Standings, Review My Season. No pick controls, no pick urgency — but never hidden from the competition; the social relationship continues.
- **Champion:** the terminal lounge owns the page — sparse, ordinary modules removed. "SOLE SURVIVOR — Jordan is the 2026 CFB Survivor champion." (or, accurately: "CHAMPION — Jordan wins on cumulative spread."). Evidence: final lives, final pick, season path, weeks survived, final field state.

### 8.9 The Summons (anchor spec)

Near the top, state-transformed, concise enough to scan immediately: **state label → one decisive sentence → one supporting line → one primary action.** It tells the player what is required, what has been done, what is now final, or what the result means. It never reads as an advertisement, and it never becomes a container for every weekly detail. The commissioner's voice may reinforce it ("Miss it and the Commish picks for you") but the system states deadline, status, and consequence directly.

### 8.10 Who's Left (social anchor spec)

The changing shape of the field, adapting by phase: **early** — counts only (active, two-life, one-life, eliminated); **midseason** — distribution, recent eliminations, current-user context; **late** — remaining names, lives, compact strategic context, route to full standings; **endgame** — the complete remaining field, names carrying the module. It becomes more personal as the field shrinks. No decorative donuts, meaningless trend arrows, arbitrary percentages, or overbuilt analytics — the module reveals the actual field.

### 8.11 Compact standings

Orientation, not reproduction: top active players, current user (with a separated row if outside the visible group — never force opening the full table to find yourself), lives, spread where relevant, and a clear "View Full Standings" route. Never outranks the unresolved pick, survival state, deadline, or verdict. May omit most eliminated players (recent cuts belong to Who's Left).

### 8.12 Commissioner presence

The lounge is the natural home of the commissioner's voice: reminders, rulings, deadline changes, weekly notes, club commentary. Notes rise in hierarchy when they affect eligibility, deadlines, postponed games, or pick rules; ordinary commentary stays secondary to the player's obligation. Important rulings persist until irrelevant; casual notes recede. Personality reinforces rules; it never replaces them.

### 8.13 Recent change (FUTURE)

A compact "what changed" module for returning players: "3 players lost a life in Week 7. 2 players were eliminated. 11 remain." Meaningful consequences only — never a generic activity feed. Orientation, not audit history.

### 8.14 Field progression

Compact aggregate progression is welcome (Week 1: 32 active → Week 9: 7 active; or stacked two-life/one-life/eliminated). It never competes with an unresolved pick. Banned: personal rank sparklines, decorative trend arrows, smoothed analytics, percentage-without-counts, synthetic "field-health" scores.

### 8.15 Routing

Every module routes toward a meaningful next action with specific labels (Choose Team, Review Pick, View Full Standings, Inspect Used Teams, Review My Season, Follow Who's Left). Route priority follows state: OPEN → Choose Team dominates; HELD → Review/Change Pick; LOCKED → Follow Game; VERDICT → View Week Results / See Who's Left; ELIMINATED → Follow the Field / Review My Season.

### 8.16 Density by phase; hierarchy by state

Density follows §1.9's phases: early = more summary, less player detail; midseason = strategic context (used-team implications, life distribution, recent cuts); late = opponent awareness (names, lives, current-user context); endgame = module reduction, final players + picks + verdict. Hierarchy per state follows §§8.4–8.8: the unresolved obligation always leads; everything else follows in the state's order.

### 8.17 Mobile and desktop

**Mobile** preserves the narrative order: summons/verdict → lives + deadline → primary action → who's left → compact standings → commissioner note → recent change → routes. Never opens with a decorative header, oversized navigation, or a standings table; the unresolved pick is visible without extensive scrolling. A sticky Choose Team action is acceptable only while no pick exists and the deadline is open, and it must not obstruct content or accessibility.

**Desktop** uses width for hierarchy and breathing room, not a multi-column dashboard: a primary column (summons/verdict/player card, compact standings, recent change) and a secondary column (who's left, commissioner note, deadline, routes). The unresolved action stays visually dominant. A lounge is composed, not tiled.

### 8.18 Empty, loading, error

- Before the first pick window: "Picks have not opened yet. Week 1 opens Monday at 9:00 AM." No eliminations: "The full field remains alive." No commissioner note: remove the component (no empty card). No movement: show current state, never manufacture a trend.
- Loading priority: survival state → pick status → deadline → current selection → field counts → compact standings → commissioner content → progression. Known status renders immediately; stable placeholders prevent layout shift; the page never briefly implies *no pick* or wrong lives while resolving — unknown renders as loading, never guessed.
- Errors preserve trust: "We could not confirm your current pick. Open the room to verify before the deadline." (never "No pick" unless known true) · "Standings are temporarily unavailable. Your pick and life status are unaffected." · A missing deadline is critical — never guess a time. If lounge and room data conflict, fail visibly; the room's canonical source wins (§10.5).

### 8.19 Accessibility

Semantic reading order matches visual priority (a screen reader meets: player state → unresolved action → deadline → field context → standings → commissioner note); never summons-first visually but last in DOM. Pick-state changes update persistent content and are announced; countdowns don't spam live regions. Who's Left and compact standings never distinguish two-life/one-life/eliminated by color alone.

### 8.20 Prohibitions

The lounge must not become: a duplicate room, a generic dashboard, a news feed, a social timeline, a chart gallery. No full slate or ledger replication, no every-standings-column, no personal rank-history charts, no redundant KPI cards, no engagement modules, no promotional content above the player's obligation. No module exists because another game has one — CFB has its own information shape.

**Heuristic:** does this help the player re-enter the competition quickly, reveal an obligation, summarize survival, show the field's change, or create a reason to return — understandable without full inspection, with a clear route when depth is needed? Then lounge. If the player must sort, compare deeply, inspect history, verify rules, or choose among the slate — room. Critical state may be both.

---

## 9. Room Architecture

### 9.1 Purpose and shipped screens

The room is the operational center: make the pick, evaluate eligible teams, understand what's spent, compare the field, review history, verify state. It supports deliberate action; it maintains one clear center of gravity even at depth. When a pick is required, the pick workflow is the room's primary purpose; held → current decision + flexibility; locked → observation; verdict → consequence.

Shipped screens and their doctrine anchors:

| Route | Screen | H1 | Anchors |
|---|---|---|---|
| `/cfb/` | standings/home (landing) | The Survivors | `.cfb-pick-cta`, standings table, The Cut, `.championship-hero` gate |
| `/cfb/pick/<week>` | the weekly decision | Your Card | `.team-pick-card`, The Board slate, `.cfb-confirm-pick` |
| `/cfb/my-picks` | season ledger | Your Card | `.cfb-season-lead`, verdict list, team pool, used grid |
| `/cfb/results/<week>` | weekly verdict | Saturday's Verdict / The Cut | `.cfb-verdict`, `.cfb-week-summary`, The Field table, `.elimination-alert` |
| `/cfb/join` | enrollment | Take Your Two Lives | `.cfb-join-*` |
| `/cfb/admin/*` | Commissioner's Desk (8 screens) | functional | `.cfb-admin-*`, A3-admin block |

The core pick flow stays coherent and continuous — never spread across disconnected pages. The sub-nav's sections are peers; urgent pick state is never hidden inside an inactive section; persistent context (week, lives, pick state, deadline) survives navigation.

### 9.2 State model at depth

Same four beats as everywhere, at operational depth, with no contradictory actions across them: OPEN shows selection + submission; HELD shows current pick + change controls; LOCKED shows no editable controls; VERDICT explains result + updated state. The room header orients (week, survival state, lives, pick state, deadline/lock, route back) — it is not a decorative hero: no oversized imagery, slogans, or promotional copy.

### 9.3 Canonical hierarchy

Player state → current obligation → deadline/lock → current pick or selection → eligible slate → used-team inventory → standings and field context → season ledger → rules and commissioner guidance. The current decision stays above historical inspection; a complete standings table never precedes an unresolved pick; rules, charts, and notes never overpower the selection workflow.

### 9.4 The pick workspace

Combines player status, confirmed pick, local selection, submission action, deadline — and **never makes the player guess whether a team was merely selected or successfully submitted**:

- **No pick:** "PICK REQUIRED — Choose one eligible team for Week 8. Your pick locks Saturday at 11:00 AM." then the slate + submission flow.
- **Held:** "CURRENT PICK — Alabama. You may change this pick until Saturday at 11:00 AM." Alternatives inspectable without losing sight of the confirmed pick.
- **Local change in progress (essential distinction):** "NEW SELECTION — Georgia. Alabama remains your confirmed pick until this change is submitted." Primary: Submit Georgia. Secondary: Keep Alabama. A click on a different team never silently replaces the confirmed pick; a failed change restores Alabama visibly.
- **Locked:** "LOCKED — Alabama vs. Auburn. Your Week 8 pick is final."
- **Verdict:** result + life consequence directly beneath (§9.7).

### 9.5 The slate

The complete set of relevant games, organized for decision-making, not a sportsbook board. Each entry (where available): team, opponent, home/away, spread, kickoff, ranking, eligibility, prior-use state, selection state. Grouping by kickoff window helps temporal risk; use the fewest groups that preserve context. Default sort is documented and stable — never reordered while the player is selecting. Density is a deliberate choice: cards when the slate is small and identity matters; rows when large and comparison speed matters; consistent between weeks. Do not overload cards with statistics — the room supports judgment, not a simulated analytics platform.

### 9.6 Selection → submission → change

Flow: select an eligible team → visible selected state → persistent summary updates → submit → server confirms → state becomes HELD. The persistent selection summary (above/beside the slate, or a restrained sticky panel on mobile) shows selected team, confirmed pick if different, submission state, deadline; it disappears or changes after submission and never remains an active control after lock. Submission confirmation persists on the page ("PICK HELD — Alabama is your Week 8 pick. You may change it until Saturday at 11:00 AM."); a toast alone is insufficient; the slate updates so the confirmed team stays distinguished; a later return reconstructs HELD from canonical data.

### 9.7 Locked, in-progress, verdict

Locked removes decision controls and reorganizes around consequence: selected team, opponent, kickoff, the competition spread, lock time, game status, lives. The slate may remain for inspection with all selection affordances removed — final, not merely disabled. In progress: score serves the selected pick ("IN PROGRESS — Alabama leads Auburn, 21–17"); no provisional life changes; other games stay secondary. Verdict: result, score where useful, life consequence, survival state, updated standings, ledger entry — "WIN — Alabama defeated Auburn, 31–20. You advance with two lives." / "LOSS — … You have one life remaining." / "ELIMINATED — … No lives remain." The consequence sits directly beneath the verdict; the player never assembles it from modules.

### 9.8 Strategic inventory

- **Used-team ledger** (chronological: week, team, opponent, result, spread, life consequence) and **availability view** (Available / Used / Unavailable-with-reason / Restored-by-reset) are distinct lenses that must not be conflated — a team can be historically used and currently eligible after the reset.
- **Scarcity context** is factual: "Georgia was used in Week 3." "Michigan remains available after the playoff reset." No invented value grades, future-value percentages, or scarcity meters — the room reveals facts; the player judges.
- **Used teams stay visible** in the slate when their presence clarifies the decision: labeled ("USED — Week 4"), visibly unavailable, never opacity-only, never removed unless the slate becomes unmanageable. The server rejects invalid submissions regardless.
- **Game-start restrictions:** a started game's teams show "GAME STARTED" and stop being selectable. Preserve the *reason* taxonomy — game started ≠ team used ≠ deadline passed ≠ spread-restricted. Never a bare "Unavailable."
- **CFP reset (week 16):** explicit banner ("PLAYOFF RESET ACTIVE — regular-season teams are eligible again"); ledger intact; availability reflects the reset without rewriting history.

### 9.9 Standings (complete)

Official order, player, lives, active/eliminated state, current-week pick state, cumulative spread, tiebreak context. Current-user row easy to locate ("You" tag + tint — §7.2). Active players visually distinct from eliminated (separate section or controlled collapse; eliminated players remain inspectable — their history is part of the season story). Sorting only where it supports legitimate inspection, never implying an alternate sort is official; tied players don't get invented unique ranks unless the product convention supports them.

**Pick visibility follows the actual rules:** hidden before deadline ("Hidden until deadline" — never a blank cell that could imply no pick), revealed after. After reveal, distinguish player-submitted, autopick-assigned (`.cfb-auto-tag`), and missing picks where the distinction matters. Never reveal early because the data is available.

**Tiebreak evidence:** when cumulative spread matters, show the evidence for official order (cumulative value, weekly contribution, rule note). Don't overemphasize tiebreaks early; elevate them as the field narrows. Never imply tiebreak overrides survival.

### 9.10 Ledger, field history, player detail

The player season ledger is complete and verifiable: week, team, opponent, spread, result, life before/after, submission source (player vs. autopick vs. commissioner), exceptional ruling. Losing picks and interventions are never hidden. Field history (per-week counts table) complements standings without replacing them. Player detail respects pick-visibility rules and supports social awareness, not surveillance.

### 9.11 Exceptional states

- **Missed pick** (per §1.10, the actual rules): "DEADLINE MISSED — The Commish assigned Georgia under the missed-pick rule." (autopick = largest available favorite, `.cfb-auto-tag` in the ledger), or, when no pick could be assigned: "DEADLINE MISSED — No valid pick was submitted. One life has been lost." Never a normal locked state when no valid player pick exists; source and consequence stay clear; the ledger preserves assignment source, timestamp, reason. An assigned team is never presented as though the player chose it.
- **Postponed/canceled — No Contest:** "NO CONTEST — [Team]'s game was canceled. No life lost; the week counts as survived. [Team] stays used; the spread is excluded from your tiebreaker." The room reflects the ruling; players never infer policy from schedule status.
- **Corrected results:** "RESULT CORRECTED — The Week 6 ruling was updated. Your life total has been restored to two." The ledger preserves the correction; standings and field counts update from the same recalculation path. Never a silent rewrite.

### 9.12 Terminal and phase rooms

- **Eliminated room — observer mode:** removes pick controls, submission actions, deadline urgency; preserves ledger, used teams, standings, who's left, weekly outcomes, championship progression. "ELIMINATED — No lives remain. You can continue following the field." Never redirected away.
- **Champion room:** archival and conclusive — champion state, deciding rule, final lives, final pick, season ledger, complete used-team path, final standings, field attrition. Ordinary controls removed.
- **Preseason room:** rules, first deadline, starting lives, team-use rule, missed-pick rule, player list. "PICKS OPEN MONDAY — Week 1 selections begin at 9:00 AM." — never broken-looking inactive controls.
- **Late-season / endgame room:** elevate opponent awareness (remaining players, lives, revealed picks, spread); reduce broad summaries in favor of direct comparison; no speculative predictions. The endgame room simplifies — early-season density never persists into the final weeks.

### 9.13 Layout

**Desktop:** structured but never equal-weight — primary column (pick workspace, slate, verdict, or locked matchup) visibly dominant; secondary column (lives + deadline, selection summary, inventory, commissioner guidance) supports; full-width lower sections (standings, ledger, field history, rules). **Mobile:** the decision sequence in order — state, deadline, confirmed pick, selection summary, slate, submission, used teams, standings, history; no complete standings above the slate; no horizontal scrolling for core selection; targets large. **Sticky mobile submit** ("Georgia selected → [ Submit Georgia ]") appears only when relevant, respects safe areas and keyboard access, disappears after submission or lock, and never covers errors or the last slate items. Responsive standings and ledger per §7.7.

### 9.14 Prohibitions and heuristic

The room must not become a sportsbook, live-score center, generic fantasy dashboard, analytics terminal, or an admin console for ordinary players. Never hide deadline, current pick, lives, lock state, or submission confirmation. Never merge local selection, submitted pick, and locked pick into one visual state. Never remove used-team history after the reset. Never expose hidden picks early.

**Heuristic:** what decision or verification does this support? Primary workflow or secondary inspection? What changes across the four beats and the three life states? Does it rely on authoritative state? Does it preserve selected-vs-submitted? If a feature doesn't improve action, comparison, verification, or strategic understanding, it doesn't belong in the room.

---

## 10. Implementation Guidance

Translates doctrine into implementation behavior, for AI agents and developers. A change is not correct because the page renders — it must preserve the rules, the hierarchy, the state model, the data contract, the player's trust, and existing operational hooks. When uncertain, prefer explicit state, reversible changes, and faithful preservation of current behavior. Platform-level engineering rules (CSRF, POST-only mutations, Flask-Migrate, ORM conventions, the `CFB_FAKE_NOW` time seam, email) live in `CLAUDE.md` and are not restated here.

### 10.1 Priorities

Rule correctness → state correctness → pick/deadline integrity → survival clarity → accessibility → existing behavior and hook preservation → information hierarchy → responsive behavior → visual refinement → decorative enhancement. Never sacrifice a higher priority for a lower one: don't simplify markup if it breaks commissioner controls; don't hide state text to make a card cleaner; don't add animation before locked and error states are complete; don't ship a redesign that makes submission less trustworthy.

### 10.2 Read before editing; preserve functional hooks

Before changing a CFB surface, trace the implementation: routes, templates, server-rendered state, client behavior, style dependencies, JS selectors, form actions, data attributes, commissioner controls, deadline logic, shared components. **Treat current selectors, routes, form names, IDs, data attributes, and commissioner hooks as functional until traced** — a selector absent from the current file may be consumed by bundled JS, server code, tests, or admin tooling. If a hook must change: identify every consumer, update all in the same change, update tests, document the migration. Known untraced hooks: §7.3's five CSS-less template classes.

An AI agent must not: delete unfamiliar code because it appears unused; rename hooks without tracing; invent game rules; infer eligibility from visual state; treat crimson as generic danger; hide critical state for cleanliness; duplicate standings logic; use client time as deadline authority; show success before confirmation; remove eliminated players from history; erase used-team history after reset; add fake analytics; or claim visual verification that did not occur.

### 10.3 Rule semantics

The interface reflects the actual rules (§1.10) — never infer them from appearance, never claim more than the rule system supports: no "sole survivor" for a tiebreak title; no "final" before actual lock; no "available" the server may reject; no provisional result as official verdict; no "spread decides everything" framing.

### 10.4 Canonical state and precedence

Presentation derives from canonical state, not scattered booleans. Weekly: OPEN / HELD / LOCKED / VERDICT. Player: PRESEASON / ACTIVE_TWO_LIVES / ACTIVE_ONE_LIFE / ELIMINATED / CHAMPION. The UI must determine unambiguously: picks open? valid pick? changeable? locked? resolved? official? lives? may participate? Contradictions are bugs: `isLocked && canEdit`, `isEliminated && showPickForm`, a life change with no verdict, a confirmed team with `pickSubmitted == false`.

**State precedence** (implemented centrally, not per-component): Champion → Eliminated → Verdict → Locked → Held → Open-unanswered → Preseason. This keeps lower-priority controls out of terminal states: a champion never sees a summons; an eliminated player never sees a pick form; a verdict replaces in-progress lock.

### 10.5 Authoritative data; room/lounge consistency

Every critical fact has one documented authoritative source: current week, deadline, lives, elimination, submitted pick, lock status, eligibility, result, cumulative spread, standings order, champion status. Never derive critical state from presentation text; never calculate the same fact differently in lounge and room — they format differently but consume the same state (shared helpers / domain functions / serialized state). If room and lounge disagree, the product loses trust immediately; fail visibly, room-canonical.

### 10.6 Deadline integrity

One authoritative deadline per pick window; server-enforced. Client countdowns are presentation, never authority — account for clock drift (server time where feasible; no confident second-level precision without it), stale tabs (revalidate at the boundary; a stale tab must not show editable state after server lock), and commissioner changes (all surfaces update from the same source; clear notice where it affects players). At expiry: stop accepting edits, transition to LOCKED, remove/disable controls, explain — never a "0m" countdown. Near-deadline submissions get the authoritative answer: accepted, rejected-as-late, or prior pick retained.

### 10.7 Submission integrity

A player is never uncertain whether a pick was recorded. Distinguish local selection / pending / success / failure / locked. During submission: prevent duplicates, show pending without erasing the prior confirmed pick. On success: update all persistent state (card, summons, slate, actions) — a toast is not confirmation. On failure: state that the new submission failed, that the prior pick remains, what to do, and the time remaining — never clear the visible prior pick unless the server confirms it's gone. Repeated identical submissions are safe (idempotent); a double-click or retry never creates conflicting records. Optimistic updates only where reversal is clean (visual selection, filters — yes; submitted picks, life changes, verdicts, lock state — no; pending beats false certainty).

### 10.8 Domain integrity

- **Eligibility** is computed from authoritative rules (prior use, week, game start, deadline, CFP reset, No Contest, commissioner rulings) and consumed as a canonical result with a *reason* — the UI never implements a parallel simplified model. Reasons stay distinct: available / used in Week 4 / game started / deadline passed / round-ineligible / restored by reset.
- **The used-team ledger is permanent.** Resets never overwrite history — they change future permission, not past fact. Corrections are auditable.
- **Spread conventions are league law:** locked at first fetch (manual entries also lock); signed display (`-7.5`, `+3`); cumulative = lifetime, favorites add, underdogs subtract, No Contest excluded; historical cumulative spread never retroactively changes because an external line moved. Official ordering is implemented once, centrally — table sort logic must never become the de facto rules engine.
- **Results:** distinguish scheduled / in-progress / delayed / postponed / canceled / final / under-review / commissioner-resolved. No life change while provisional; no "win" because a team leads; postponed ≠ automatic anything (No Contest is the ruling). Corrections update lives, elimination, standings, field counts, ledger, and lounge verdict from one recalculation path.
- **Lives are idempotent:** central domain operations (resolve pick → apply consequence → recalculate state); invalid states are impossible (negative lives, eliminated-with-one-life, active-with-zero, champion-eliminated, double-processed losses). Running the same resolution twice never removes two lives.

### 10.9 Commissioner overrides and auditability

Consequential overrides record actor, timestamp, affected player, previous state, new state, reason, week. Admin interfaces show current authoritative state before confirmation; browser confirm() is never the sole gate for irreversible actions. Consequential state is reconstructable: who submitted, when, changes, lock time, result applied, interventions, life changes. Auditability protects player trust, dispute resolution, and championship legitimacy — it is not merely an administrative concern.

### 10.10 Degradation, caching, concurrency

Fail by module: standings down ≠ pick flow down; commissioner notes down ≠ survival status down. Each module distinguishes empty / unavailable / loading. **Never convert unknown into false state:** a failed pick-status request is not "no pick"; a failed standings request is not an empty league; a missing result is not a loss; a missing deadline is not an open window. Trust is preserved by admitting uncertainty. Cache with deadline sensitivity (pick status, deadline, lock, results, lives, standings = short/invalidated; completed history = longer); a stale lounge never shows "Choose Team" after lock; revalidate at action time. Multi-tab/device: revalidate on focus/route/submit; a conflicting pick submitted elsewhere shows the authoritative pick and explains; stale form state never silently overwrites newer confirmed state.

### 10.11 Semantics and accessibility

Semantic HTML first: headings reflect hierarchy (not size), `form`/`fieldset`/`legend` for grouped team selection (a radio-group model fits one-team selection), `button` for actions, `table` for true tabular standings, `time` for deadlines. Accessible names are complete ("Select Alabama over Auburn, spread minus seven and a half"); selection/disabled state is programmatic and agrees with the visual. Focus is managed intentionally (submission → confirmation; error → error summary; modal close → invoker; background updates never steal focus). Live regions announce consequential changes only (submitted, changed, failed, locked, verdict, life lost, elimination) — never countdown ticks or slate-wide score changes; persistent visible state still updates. Reduced motion is honored; no meaning depends on animation. Test the pick workflow with no mouse; test one-life/eliminated/locked without color.

### 10.12 CSS / JS / template architecture

Tokens by role, not value (the `--cfb-*` system); each token tested against its intended backgrounds; no hardcoded near-duplicates of ramp values scattered through the file. Component styles reflect documented states; behavioral hooks separated from styling hooks where possible. JS is modular and state-driven: explicit functions for select/submit/update/deadline-transition/announce; never button labels or displayed strings as the source of state; never parse rendered deadline text to enforce rules — use serialized canonical values. Templates receive presentation-ready state (view models over ten unrelated booleans) and never independently recalculate eligibility, lives, standings, or champion status. Serialized payloads include enough to render without re-implementing rules (week, status, deadline, server time, current pick, may-edit, lives, survival state, eligibility) with machine-readable timestamps; admin-only fields never reach player-facing state.

### 10.13 No false precision; no trend surfaces

No confidence scores, pick grades, inventory-strength percentages, survival probabilities, or predicted champions. No personal rank sparklines, movement badges, week-over-week arrows, or performance charts imitating other fantasy products. Before any chart: what variable, why does its history matter, what decision does it support, would direct counts be clearer? No answers → no chart. The player makes the decision; the product presents evidence.

### 10.14 AI change procedure

1. **Identify the player question** the change answers (make a pick, confirm submission, understand lives, inspect inventory, follow the field).
2. **Identify the surface** — lounge, room, both, rules, or admin ("the lounge summarizes; the room completes").
3. **Identify all states** — weekly beats, player states, loading, error, exceptional rules.
4. **Trace existing hooks** — selectors, routes, forms, data attributes, handlers, tests.
5. **Preserve rule authority** — which layer determines eligibility, deadline, lives, result, standings.
6. **Implement the smallest coherent change** — no drive-by abstractions or neighboring redesigns.
7. **Test behavior** — happy and failure paths.
8. **Verify visually** — desktop, mobile, state variations (§10.16).
9. **Check accessibility** — semantics, keyboard, focus, labels, contrast.
10. **Confirm no contradictions** — lounge vs. room; player-facing vs. commissioner-facing.

### 10.15 Definition of done

A CFB change is complete only when: the player question is answered; room/lounge responsibilities stay coherent; implementation matches actual rules with authoritative data; the four beats and four player states behave correctly; loading/failure creates no false state; submission is trustworthy and failure preserves prior state; locked cannot be changed; semantics/keyboard/focus/color-independence hold; mobile preserves urgent state without horizontal scrolling; existing hooks and commissioner behavior survive; historical data remains valid; relevant tests pass; critical states were rendered and inspected; lounge and room agree. A visually attractive page that fails any critical item is not done.

### 10.16 Verification cadence

The primary regression question is not "does this page look correct?" but:

> "Does this still feel like one season-long survivor room — dark, immersive, instantly readable — and not the WC room, a dashboard, or a dim mess?"

**Visual smoke workflow.** Run the dev server (platform port-5099 worktree pattern, `CLAUDE.md` § Commands) against a local sandbox DB seeded to the state under test, and use `CFB_FAKE_NOW` (with `ENVIRONMENT=development`) to walk the states that gate UI behavior. Seed via any convenient dev script or direct-DB manipulation — seeding tooling is disposable; the *states* are the contract. Smoke at desktop and true-mobile width (`emulate "375x812x2,mobile,touch"`, not `resize_page`); mobile gets extra scrutiny (survivor sessions skew to quick mobile check-ins). Walk at minimum:

- **Pick open (OPEN)** — CTA obvious in seconds? Deadline visible? Does the pick feel like a decision?
- **Held (HELD)** — confirmed team + changeability + deadline all legible?
- **Weekly verdict (VERDICT)** — outcome readability, survivor-state visibility, emotional restraint, season continuity.
- **Mid-season attrition** — mixed lives + eliminated tail + pending: standings hierarchy, current-user visibility, how much field remains.
- **Final life** — decision focus, urgency *without* panic styling (pressure from context, not red alarms).
- **Resolved season** — `.championship-hero` as escalation-by-reduction: earned, quiet, the same room; no redesign, no gold, no spectacle.

**Cross-route continuity.** Pass across STANDINGS → PICK → RESULTS → MY PICKS → JOIN: substrate continuity, typography rhythm, decision hierarchy, component consistency, atmosphere persistence, interaction language, survivor-state consistency. The standard is **"one room, one season, one game"** — and the second standard is **"this is not the WC room."** No route feels imported from another product.

**Room testing matrix** (states to exercise for substantial changes): active player — no pick, local selection only, successful submission, held, change-in-progress, failed change, locked, in-progress game, win, first loss; terminal — eliminated, champion; eligibility — available, used, game-started, reset-restored, exceptional, none-eligible; deadline — far, near, boundary, passed, commissioner-changed, stale tab; exceptional — postponed, canceled, corrected result; responsive — desktop, tablet, narrow mobile, long team/player names, large zoom.

**Regression categories:**

- **Low-contrast dark mode** — washed hierarchy, muted states, text that takes effort. Dark, never dim.
- **Crimson saturation** — competing crimson regions, flattened hierarchy, crimson carrying unrelated meaning.
- **Accent collision** — crimson reading as danger, or survivor-red as interaction; the two reds bleeding together.
- **Dashboard / ops-center fragmentation** — excessive cards, unrelated panels, telemetry behavior, equal emphasis everywhere.
- **Generic fantasy / sportsbook drift** — roster-builder energy, betting-slip styling, broadcast overlays.
- **Consequence collapse** — picks feeling reversible, elimination invisible, deadlines disappearing, lives going decorative.
- **Atmosphere inflation** — excessive motion, cinematic effects, decorative glow, constant drama.
- **Voice convergence** — CFB H1s drifting into WC's civic-ceremonial cadence, flat functional labels on player routes, or tactical/military language reaching user copy.
- **State ambiguity** — selected vs. submitted vs. locked merging; unknown rendering as false state.

**Accessibility verification (priority order):** (1) contrast on every midnight surface incl. raised/lifted + the §6.4 constraints; (2) scan speed — alive status, current decision, remaining field within seconds; (3) motion comfort — `prefers-reduced-motion`, no motion-only meaning; (4) keyboard/focus — visible on midnight, pick cards operable, whole workflow mouse-free; (5) color blindness — survivor state survives without hue.

**Implementation verification idioms.** CFB inherits the platform's CSS-scan lock idioms (anchored `^...` + `re.MULTILINE`, property-anchored `(?<![-\w])` lookbehinds, rule-block `\{([^}]*)\}` extraction, forbidden-list `\s*[,{]` terminators). New regression locks land with the primitive or contract they protect: fail before, pass after. Existing locks: `tests/test_cfb_dark_foundation.py` (token rebase, no-gold, scope), `test_cfb_hub_a2.py`, `test_cfb_pick_a3.py`, `test_cfb_weekly_results_a4.py`, `test_cfb_my_picks_a5.py`, `test_cfb_join_a6.py`, `test_cfb_admin_a3.py`. All Python comments and docstrings in CFB phases remain ASCII-only.

**Final evaluation question.** Before approving any substantial CFB change:

> Does this increase consequence without increasing friction, keep the player's status / decision / field instantly legible on a dark substrate, and still feel like the same season-long survivor room under the lights — not the WC room, not a dashboard, not dim?

If the answer is no, revise before shipping.
