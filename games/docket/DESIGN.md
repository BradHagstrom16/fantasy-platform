---
name: The Docket — Design Doctrine
description: Per-game design doctrine for The Docket (NFL+CFB weekly pick'em) at cccfantasy.com. A light court-paper room layered on the platform foundation (repo root DESIGN.md). Substrate, palette, courtroom register, and the .docket-* sheet primitives.
extends: ../../DESIGN.md
colors:
  # The Docket game palette (body.game-docket). Full ramp + usage in §Palette below.
  docket-oxblood: "#6E1F2E"       # --game-primary: room identity, hero terminus, .btn-game
  docket-chambers: "#421219"      # --game-primary-dark: hero gradient origin
  docket-worn-spine: "#8A3B4A"    # --game-primary-light: hover lift for oxblood fills
  docket-garnet: "#A63446"        # --game-accent: the docket stamp, subnav accent, slot badges
  docket-faded-stamp: "#C4707E"   # --game-accent-light: tints, dark-surface accent text
  docket-rule: "#D8CFC0"          # ruled-line hairline for ledger rules (bone family)
  docket-subnav-black: "#180C10"  # warm oxblood-cast near-black; the .subnav-docket bar
---

# Design System: The Docket

> Per-game design contract for The Docket (slug `docket`), layered on the platform foundation
> in the repo-root `DESIGN.md` per `docs/per-game-design-doc-convention.md`. That file owns
> cross-game doctrine (CCC palette framework, typography, elevation, motion, design laws);
> this file owns The Docket's substrate, palette, register, and named primitives. When working
> any surface under `games/docket/`, read both.
>
> Authored 2026-08-12 (T7, design-first). Component doctrine below is the build contract for
> the pick sheet; it gets reconciled against the shipped surfaces at the end of each build
> slice, and T9 (admin) / T10 (standings, rules) extend it rather than re-deriving.

---

## 1. Product Philosophy

### 1.1 The game is season-long bookkeeping as drama

The Docket is a points-accumulation pick'em: eight picks a week against frozen lines, across
FBS and the NFL, from CFB Week 1 through NFL Week 18. Nothing is ever final in one week and
nothing is ever forgotten either. Points accumulate, one worst week is eventually forgiven,
wins accumulate and are never forgiven, and the tiebreaker error account grows all season and
never forgives anyone. The standings ledger is the product; every weekly surface exists to
feed it honestly.

### 1.2 The weekly ritual is filling out a sheet

Unlike Survivor's single agonized choice, The Docket's weekly act is clerical volume with
judgment inside it: scan ~76 cases, commit eight sides, name one headliner, hold one in
reserve, write down one number. The pick sheet must make volume feel orderly, never like a
spreadsheet chore. Progress is visible at all times: how many of eight, headliner named or
not, backup held or not, number written or not.

### 1.3 Lines are frozen; the sheet is a record

Every line locks at Tuesday import and never moves. A pick snapshots the number it was made
against. The interface therefore treats lines as printed facts, not live market data: no
tickers, no movement arrows, no odds-board flash. The register is a court record, not a
sportsbook.

### 1.4 Decisions lock in waves

The week deadline is Saturday 11:00 AM CT, but individual cases lock earlier, at kickoff. A
Thursday-night pick is committed Thursday while the rest of the sheet stays open. The
interface must always distinguish, per case: open to me, held by me, held and locked, locked
before I acted. Locked is procedural and cold, never punitive; a locked case always states
its reason.

### 1.5 The headliner is nerve, the backup is prudence

The best pick doubles and the designation cannot be moved onto a game that already kicked
off. The backup sits dormant in slot 9 and only enters if a case is thrown out (No Contest,
the mistrial's older sibling). Both mechanics reward foresight; the design gives the
headliner ceremony-in-miniature and the backup a deliberately quiet, held-in-reserve
character. They are not equal-weight features.

### 1.6 The tiebreaker number matters forever

One designated game per week asks every player for a combined-score prediction to a tenth.
The error accrues season-long as ranking key 3. It is the most easily forgotten input with
the longest memory, so the sheet treats it as a first-class obligation, not a footnote field.

---

## 2. Design Invariants

- **2.1 Sheet progress is immediate.** From anywhere on the pick sheet, one glance answers:
  picks made of 8, headliner set, backup held, number written, time remaining. The rail
  carries this; on mobile a condensed bar carries the same five facts.
- **2.2 Every unfilled obligation is visible while the docket is open.** Empty slots render
  as empty ruled frames, not collapsed space. An unset headliner, missing backup, and blank
  tiebreaker each show as an unfinished line item, calmly, with escalation only near the
  deadline.
- **2.3 Locks are explicit and reasoned.** A case past kickoff shows its state in words
  ("Locked at kickoff"); a market with no frozen line says so ("No line posted"). Never a
  bare disabled control, never a raw opacity collapse.
- **2.4 The pick snapshot is the displayed truth.** A held side always displays the exact
  frozen number (and its slot) the pick was made against. The sheet never displays a
  different number next to a held pick than the one that will grade it.
- **2.5 One side per market, structurally.** Selecting the opposite side of a held market
  moves the pick (same slot, same case, other side); it never creates a second pick or asks
  the player to resolve a conflict the interface created.
- **2.6 The register seasons, comprehension leads.** Courtroom vocabulary carries flavor
  (docket, case, verdict, mistrial, headliner, held in reserve), but every mechanic is also
  stated plainly where a first-time player needs it. Casual is the default; depth is
  available when sought (platform resolution principle).

---

## 3. The Room and the Lounge

The Docket's room lives under `/docket/`, scoped by `body.game-docket`. The platform lounge
(`/`) stays the club's dark purple-and-gold surface; The Docket enters the lounge only
through content and copy (registry tile now; the T13 static strip later), never through this
room's palette or substrate. Substrate contrast at the threshold is by design.

The room is a **light court-paper room**: Pressroom Bone body, white paper cards, ink text,
oxblood-and-garnet accents. It deliberately runs opposite Survivor's midnight room; the two
games run concurrently and their rooms must never feel like reskins of each other. CFB
remains the platform's single sanctioned dark-room carve-out; The Docket does not add a
second one.

The room owns participation and inspection: the pick sheet (this slice), then standings,
rules, and admin (T9/T10). The lounge orients and summarizes. When placing any new Docket
surface, ask "lounge or room?" first (platform §1.6).

---

## 4. Product State Model

### 4.1 Weekly states

- **Awaiting docket** — the week exists but games have not been imported (or the season has
  not begun). The room states when the docket posts (Tuesday) rather than showing an empty
  table.
- **Docket open** — lines frozen, picks editable, cases lock individually at kickoff.
- **Docket closed** — Saturday 11:00:00 AM CT reached. The whole sheet is read-only. The
  submission boundary is strict: 10:59:59 is on time, 11:00:00 is late.
- **Verdicts** — scores land, cases resolve to verdicts (win), mistrials (push), losses; the
  week grades (T8+).
- **Adjourned** — the week is graded into the season ledger (T10 renders this).

### 4.2 Case states (per game, within an open docket)

open → held (player has a side) → locked (kickoff reached; held picks freeze, open markets
close) → final (score in) → No Contest (admin-ruled; the case is thrown out and the backup
may substitute). A case with no frozen line for a market shows that market as unavailable
without drama.

### 4.3 Sheet states (per player)

blank → in progress (n of 8) → complete (8 held) → complete-plus (8 + headliner + backup +
number). "Complete" without a headliner, backup, or number is legal at the deadline
(autopick and defaults cover the gaps) but the sheet says plainly what is still unfinished.
The interface never implies an unsubmitted sheet is void; it states what defaults will apply.

---

## 5. Decision Priorities

When two treatments conflict, resolve in this order:

1. **Truth of the record** — frozen numbers, lock states, and progress facts are never
   obscured by styling.
2. **Speed of the weekly task** — eight decisions plus three obligations, mobile-first,
   before Saturday morning. Density serves scanning; ceremony never blocks input.
3. **The ledger's gravity** — season surfaces (T10) get the polish budget; weekly surfaces
   feed them and visually defer to them.
4. **Register flavor** — courtroom voice is applied last and removed first when it costs
   comprehension or speed.

---

## 6. Identity System

### 6.1 Visual character

A working court document, produced by the Commissioner's clerk on good paper. Editorial
Tribune bones (Teko mastheads, Newsreader body) on bone paper, with the docket's own
law-library materials: oxblood leather, stamp-ink garnet, ruled lines. Orderly, procedural,
quietly theatrical. The drama is in the record, not in the chrome.

### 6.2 Light-room doctrine

The Docket is a light room in the WC/Golf substrate family: it consumes the platform's
default bone page, white cards, ink text, and purple-tinted shadow scale unchanged. It does
NOT rebase platform tokens (that is CFB's documented dark-room carve-out, not a pattern).
`body.game-docket` sets only the game-slot variables plus docket-scoped component styles.

### 6.3 Palette

Game-slot variables (set on `body.game-docket` in `style.css`; platform components consume
them automatically):

| Slot | Value | Name | Notes |
|---|---|---|---|
| `--game-primary` | `#6E1F2E` | Law-book Oxblood | Room identity: hero gradient terminus, `.btn-game`, held-side commitment |
| `--game-primary-dark` | `#421219` | Chambers | Hero gradient origin |
| `--game-primary-light` | `#8A3B4A` | Worn Spine | Hover lift for oxblood fills |
| `--game-accent` | `#A63446` | Stamp Garnet | The docket stamp: active/selected accents, subnav accent, slot badges |
| `--game-accent-light` | `#C4707E` | Faded Stamp | Tints, dark-surface accent text |

Docket-scoped additions (defined inside the `/* === THE DOCKET === */` section):

- `--docket-rule: #D8CFC0` — the ruled-line color, a bone-family hairline for ledger rules
  and slot frames (warmer than the platform `--border`, used only inside docket primitives).
- Tint recipe: garnet at 8-12% (`rgba(166, 52, 70, 0.08–0.12)`) is the held/selected tint on
  paper; there is no oxblood tint (oxblood appears as fills and text, never as a wash).

**Accent rank:** oxblood (structure and identity) → garnet (action, selection, the stamp) →
ink (platform text) → gold (platform-ceremonial only, effectively absent from weekly
surfaces). The oxblood family is The Docket's third color under the platform Two-Color Rule
and appears only under `body.game-docket`.

**Distinctness constraint:** oxblood/garnet is the wine family, deliberately darker and
browner than CFB's signal crimson `#C5050C` and the frozen WC red `#BF0A30`. Do not brighten
the docket reds toward either; if a treatment wants a brighter red, it is asking for a
semantic (danger/live) token instead.

### 6.4 Contrast constraints (verified at authoring)

All on the light substrates (bone `#F3EFE6`, card `#FFFFFF`):

- Oxblood `#6E1F2E` text on bone ≈ 9.6:1, on white ≈ 11.1:1 — AA/AAA, unrestricted.
- Garnet `#A63446` text on bone ≈ 5.7:1, on white ≈ 6.6:1 — AA for body sizes; fine for
  accents, labels, and links.
- Bone text on oxblood fill ≈ 9.6:1; on `--game-primary-light` `#8A3B4A` ≈ 6.5:1 — button
  states clear AA at rest and hover.
- Subnav (dark chrome, see 7.8): inactive pills are the shared bone-mute treatment; the
  garnet accent is consumed by the shared `.active` rule the same way WC red and CFB crimson
  are. Verify any NEW dark-surface garnet text against `#180C10` at build time; prefer
  `--game-accent-light` for small text on the subnav family.

### 6.5 Oxblood is identity, not outcome

Wins, losses, and mistrials carry the platform semantic layer (success green, danger red,
neutral) plus structure; oxblood and garnet mark identity, selection, and ceremony. A
verdict surface colored by outcome must not lean on garnet for "loss" — garnet means "yours"
and "chosen," never "wrong." (Mirror of CFB's crimson-is-identity rule.)

### 6.6 Typography

Platform faces only (Teko display, Newsreader body — the Newsroom Rule). Docket-specific
applications:

- **Case caption:** Teko 600 uppercase, the matchup rendered as a caption line,
  away-at-home: "WISCONSIN AT NOTRE DAME". The register may present it caption-style
  ("Wisconsin v. Notre Dame") only in editorial copy, never as the functional matchup line
  on the sheet (comprehension leads; "v." reverses home convention ambiguously).
- **Frozen numbers:** Teko 500 at label scale with explicit signs for spreads (`-3.5`,
  `+3.5`) and bare tenths for totals (`48.5`). Numbers are typographic chips, quiet, never
  odds-board styled.
- **The number field (tiebreaker):** Newsreader for the prompt, Teko for the entered value
  display.
- **Sanctioned caption classes** (≥0.75rem floor per platform §3): `.docket-caption` for
  kickoff time + network-free metadata under a case caption, and `.docket-book` for the
  bookmaker provenance line ("line: DraftKings"). Both report; the case caption leads.

### 6.7 The Docket voice (H1s and copy)

- H1s use the Tribune voice as editorial section names: "The Week 1 Docket", "The Season
  Ledger" (T10). Dynamic-noun dispensation applies (platform §3).
- Copy voice is the clerk's: procedural, dry, factual, with the Commissioner's wry authority
  in eyebrows and empty states, never in error messages. Errors name the problem and the
  recovery plainly ("That case locked at kickoff. Your other picks are safe.").
- Register glossary (use consistently): the **docket** (a week's slate + your sheet), a
  **case** (one game), a **side** (one pick), the **headliner** (best pick, worth double),
  **held in reserve** (the backup, slot 9), a **verdict** (win), a **mistrial** (push),
  **thrown out** (No Contest), the **ledger** (season standings), **court adjourns** may
  flavor the deadline but the deadline line always states the literal time.
- No em dashes or double hyphens in UI copy (platform Copy Discipline).

### 6.8 `.docket-eyebrow`

The room's eyebrow primitive, following the platform one-default-plus-variants shape: Teko
500, 0.85rem, 0.14em letter-spacing, uppercase, `--game-accent` (garnet) default on light
surfaces. One tonal variant: `.docket-eyebrow-ink` (`--text-secondary`) for informational
sections where garnet would overreach. No glyphs on game-body eyebrows (platform reservation
of `◈`/`◇` for lounge ceremony).

### 6.9 Material rules

- Ruled lines, not boxes: the sheet's internal structure prefers `--docket-rule` hairline
  rules (ledger lines) over nested card borders. Cards remain the platform white card; the
  paper texture is achieved by rules and rhythm, never by a background image or grain.
- The stamp: selection/commitment treatments may use a garnet border plus garnet tint (the
  "stamped" look). Stamps are rectangular with the platform radius, never rotated novelty
  rubber-stamp skeuomorphism.
- Elevation is the platform scale untouched (purple-tinted). Declare elevation once per
  surface (border or shadow, not both fighting).
- 44px touch floor on side controls, day tabs, and the tiebreaker controls (the platform
  floor). Rail slot actions (make/clear headliner, withdraw) are secondary targets and hold
  at least 34px height with 44px width and clear spacing, per the WCAG 2.5.8 minimum rather
  than the 44px AAA target; they never carry a primary obligation.

### 6.10 Prohibited visual directions

- Sportsbook chrome: live-odds boards, movement arrows, flashing numbers, parlay-slip
  styling. The frozen-line register is the anti-sportsbook.
- Legal skeuomorphism: gavel icons, scales-of-justice watermarks, rotated rubber stamps,
  "CONFIDENTIAL" tape. The register is a working document, not a courtroom costume.
- A second dark room. Dark surfaces in this room are limited to the shared subnav chrome and
  any future T10 ceremonial primitive (named there, one surface, following the
  one-ceremonial-dark-surface pattern).
- Emoji as icons (platform ban); emoji appear only where the platform already sanctions them
  (registry tile, navbar switcher label, and the `.subnav-game-label` — the established
  cross-game sub-nav pattern: 🏈 CFB, ⛳ Golf, ⚖️ Docket).
- Red-family escalation: no brightening docket reds toward crimson/signal red (6.3).

### 6.11 Named rules

- **The Frozen-Number Rule.** A displayed line next to a held pick is the pick's own
  snapshot, always. (2.4 restated as the component contract.)
- **The Stamped-Side Rule.** Commitment reads as a stamp: garnet border + tint + weight
  step. A tint alone is never a held state.
- **The Cold-Docket Rule.** Locked and lineless states are procedural: reduced contrast,
  stated reason, no interaction. Never punitive, never silent.
- **The Clerk's-Ledger Rule.** Progress facts (n of 8, headliner, reserve, number, time)
  travel together as one unit wherever they appear.

---

## 7. Component Doctrine (build contract, T7 scope)

Components answer: What is still owed? What did I commit and against what number? What is
locked and why? One center of gravity per page (platform law). The pick sheet's center of
gravity is the docket itself (the case list); the rail is its running margin.

### 7.1 The sheet rail — `.docket-rail`, `.docket-slot`

The player's sheet as a clerk's margin column: slots 1–8 as ruled frames (empty = blank
ruled line with its slot number; filled = case caption + side + frozen number), slot 9
(`.docket-slot-backup`) visually recessed and labeled "held in reserve", the headliner
marker on its slot, the tiebreaker line, and the deadline. Desktop: sticky aside beside the
slate. Mobile (<lg): the rail collapses to a fixed bottom bar (`.docket-rail-bar`) carrying
the Clerk's-Ledger facts, expanding to a drawer on tap. Removing a pick leaves its slot
frame empty in place (gaps are real; the next add fills the lowest open frame).

### 7.2 The case row — `.docket-case-row`

One game as one case: sport tag (CFB/NFL), case caption (away at home), `.docket-caption`
kickoff line (CT), then two market groups (spread, total) of two `.docket-side` controls
each. Rows separate by `--docket-rule` hairlines under day heads; the slate is a document,
not a card grid. A case with a held side carries a quiet held indicator at row level so the
scanning eye finds its own commitments without reading every pill.

### 7.3 The side control — `.docket-side`

The decision primitive, escalating with commitment (pick-surface doctrine shared with CFB):

- **Resting**: quiet bordered pill, team/side + signed number.
- **Hover/focus**: half-step lift, garnet border hint, visible focus ring. **The room's
  focus ring is garnet** (`outline: 2px solid --game-accent`, offset 2) on docket
  interactive controls: the platform gold ring reads sub-3:1 on bone and this room runs
  its own ring the way CFB's admin desk runs crimson; the tiebreaker input keeps the
  platform form-control focus (gold border + glow) unchanged.
- **Held** (`.is-picked`): the stamp — garnet border, garnet 8-12% tint, weight step, slot
  number badge. Never tint alone.
- **Opposite-of-held**: available but visibly secondary (selecting it moves the pick, 2.5).
- **Locked** (`.is-locked`): Cold-Docket treatment with the stated reason; a held-and-locked
  side keeps its stamp under reduced contrast.
- **No line** (`.is-no-line`): the market group renders once, disabled, "No line posted."

### 7.4 The headliner — `.docket-headliner-chip`, `.docket-headliner-tag`

The best-pick designation as the docket's one ceremonial mark: an **oxblood** "x2" chip on
the held side it decorates, an oxblood-filled slot number and "HEADLINER x2" tag in the
rail. Oxblood, not garnet, by ruling: the garnet slot badge rides the same stamped pill,
and the double earns the ramp's more ceremonial step rather than a second garnet chip that
would blur into it. Setting it is a one-tap action on a held pick; moving it obeys the
lock rules and refusals state why. It is deliberately the loudest recurring mark on the
sheet and must stay the only one.

### 7.5 The reserve — `.docket-slot-backup`

Slot 9 reads dormant: recessed frame, "held in reserve" label, same side anatomy at reduced
presence. It never carries the headliner. Its explainer copy states the substitution rule in
one clerk's sentence.

### 7.6 The number — `.docket-tiebreaker`

The tiebreaker card: designated case named, one decimal-tenths input (`inputmode="decimal"`),
the frozen total shown as reference ("the line says 51.5"), and the lock time
(min(deadline, kickoff)). Blank state says the default rule plainly.

### 7.7 The court calendar — `.docket-day-tabs`, `.docket-day-head`

The slate is navigated one day at a time (the built structure, seed 7861f3cd):
`.docket-day-tab` links (real hrefs, `?day=YYYY-MM-DD`, server-side active state,
so the no-JS spine extends to navigation) carry the day and its case count; the
active tab takes the stamp treatment. Below them, `.docket-day-head` opens the
day: Teko title, case count, a `--docket-rule` rule. Grouping is computed in the
route. The default day is the first still holding a case that has not kicked off:
pre-deadline that is the first still-pickable day; after the docket closes it is the
next day still to play (the sheet is read-only either way), falling back to the last
day once the week is fully played.

### 7.8 Sub-nav — `.subnav-docket`

Platform `.game-subnav` shape: background `#180C10` (warm oxblood-cast near-black, distinct
from CFB's purple-cast `#0a080f`), `--subnav-accent: #A63446`, `--subnav-accent-rgb:
166,52,70`, plus both scroll-fade tints matching the background. Label: "⚖️ Docket 2026".
T7 pills: My Sheet. (T10 adds Ledger and Rules.)

### 7.9 Join page

Platform join shape (page-hero + how-it-works + form + `.btn-game`), CFB's
`cfb-join-rules` dl pattern as the structural reference, the clerk's voice for the rules
summary, $25 entry line via `DOCKET_ENTRY_FEE`.

### 7.10 Empty states

- **Pre-season / no week:** "Court convenes September 1. The Week 1 docket posts Tuesday
  morning." (Date derived from week math, never hardcoded prose drift.)
- **Week without games:** "This week's docket has not been posted yet. Lines freeze Tuesday
  morning."
Both are calm full-width statements in the room's voice, not error styling.

### 7.11 JS hooks

Behavior hooks are `data-docket-*` attributes (`data-docket-action`, `-game`, `-market`,
`-side`, `-slot`); state classes (`is-picked`, `is-locked`, `is-best`, `is-backup`,
`is-no-line`) ship alongside styling classes and are never renamed for styling reasons
(platform template-restyling rule). The sheet is fully functional without JS (mini-form
PRG); JS is an enhancement layer that repaints from the server's authoritative sheet state.
