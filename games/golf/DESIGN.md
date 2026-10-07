---
name: The Pay Sheet — Design Doctrine
description: Per-game design doctrine for The Pay Sheet (Golf One & Done) at cccfantasy.com. A light paper room layered on the platform foundation (repo root DESIGN.md): the grill-room money ledger. Substrate, palette, the marks, the bookkeeper's register, and the .golf-* sheet primitives.
extends: ../../DESIGN.md
colors:
  # The Pay Sheet game palette (body.game-golf). Full usage in §6 below.
  golf-pen: "#2439C8"            # --game-primary AND --game-accent: the one identity hue (blue is personal)
  golf-pen-pressed: "#1A2A8F"    # --game-primary-dark: hero gradient origin on the join page, pressed fills
  golf-pen-lift: "#4A5CD6"       # --game-primary-light: hover lift for pen fills (white on it 5.5:1)
  golf-pen-bright: "#8C9BFF"     # --game-accent-light: pen text on the dark sub-nav (6.7:1 on #0F110D)
  golf-paper: "#E9EBE4"          # --bg-page under body.game-golf: cool grey-white waterproof paper
  golf-surface: "#F7F8F3"        # --surface-card under body.game-golf: the pick list, admin tables, insets
  golf-ink: "#15190F"            # --text-primary under body.game-golf: graphite; banked money
  golf-pencil: "#5A6253"         # --text-secondary under body.game-golf: muted text; projected money (5.1:1)
  golf-rule: "#C9CDC2"           # --golf-rule: the hairline between sheet rows
  golf-marker: "#B3261E"         # --golf-marker: deduction state only (CUT, WD, DQ, Penalty $15, Unpaid) (5.4:1)
  golf-course: "#006747"         # --golf-course: environmental state only (a tournament is live) (5.7:1)
  golf-subnav-black: "#0F110D"   # graphite-cast near-black; the .subnav-golf bar
---

# Design System: The Pay Sheet

> Per-game design contract for The Pay Sheet (slug `golf`, registry short name "Golf"), layered on the
> platform foundation in the repo-root `DESIGN.md` per `docs/per-game-design-doc-convention.md`. That
> file owns cross-game doctrine; this file owns the room's substrate, palette, register, marks and
> named primitives. `impeccable context --target games/golf/…` loads this file INSTEAD of the root one,
> so the root rules this room depends on are restated in §6.11. When working any surface under
> `games/golf/`, read both.
>
> Authored 2026-10-06 (U0, design-first, from the approved Pay Sheet preview built on the real 2026
> season). §7 is reconciled against what ships at the end of each Phase U cluster: it was reconciled
> from U1 (The Sheet) and U3 (The Board), then from U2 (the pick page), then from U4 (the scorecard)
> and U5 (the Record Room), all on 2026-10-06; §8 was written from U4 and U5 the same day, and §7.9
> (the tiles) was reconciled from the scorecard then. §7, §8 and §9 were reconciled from U6 (The
> Back Office) and U7 (the record, the champion, the lounge) on 2026-10-06, the champion fold and the
> lounge panels taking §8.19 to §8.24, the back office its marks in §7.15 and its invariants in §9.
> Phase U is complete; the file now describes a built room. Later work extends this file rather than
> re-deriving it. The legacy "Greenside Ledger" (`~/Golf_Pick_Em/DESIGN.md`) is reference, not
> doctrine.

---

## THE PAY SHEET · Golf One & Done

**Pick a golfer. Bank their earnings. Spend them once.**

Each week, choose one golfer in the field (and a backup). Their tournament earnings are added to your
season total. Once you use a golfer, they're gone for the season. The winning strategy isn't simply
finding the golfer most likely to win this week; it's deciding when each golfer is worth spending.

**Money is the score. Golfers are the resource. The sheet is the game.**

## 1. Product Philosophy

### 1.1 The game is a finite resource-management game dressed as a money ledger
The Pay Sheet turns a golf season into a finite resource-management game. Every week you are choosing
not only a golfer likely to earn money now, but the golfer you are willing to spend. A great pick pays
twice: once in the standings and once in the knowledge that you still have players available for
later. The tension is not simply "Who will win?" It is "Who am I willing to use?" (Brad, 2026-10-06.)

### 1.2 The loop
See tournament → evaluate field → choose golfer → commit → watch → see earnings → golfer becomes
unavailable → repeat. Thirty-two times, Sony to the BMW.

### 1.3 The money is the score; the golfer is the causal object
Points are the golfer's actual prize money. The member's number leads every surface, but a figure is
never shown with its cause suppressed: the hierarchy is money → golfer → pick → tournament position.
"$3,645,000 · Scheffler · 2nd", never a bare number.

### 1.4 Projected is pencil, banked is ink
Live earnings are projections from position (read at noon, 4 PM and 8 PM CT, Thursday to Sunday) and
become real only when results finalize on Monday. The interface never lets a member mistake the one
for the other: the states are named in words and drawn in different materials (§6.6).

### 1.5 Make pick is the primary surface
Standings is the landing page; the pick page is where the game is played. It answers four questions
before anything else: what tournament and how much is the purse; when does picking lock; who have I
already used; who should I consider spending now.

### 1.6 Rules that bind design
One primary and a required backup, both from the synced field, each golfer usable once per season
(only the golfer who counted is spent). WD before finishing round 2: the backup counts and the
primary returns to the pool. WD after round 2: the primary counts, usually $0, and is spent. Both WD
before round 2: primary counts $0, backup returns. "Not started" is a WD at finalization. Missed cut
or DQ at a major: $15 to the side pot, automatic, refreshed live, settled at finalization. Majors pay
×1.5 on the earnings. Zurich pays the full team payout. No pick: $0, no penalty, no autopick. Picks
lock at the first Thursday tee time (CT); others' picks are hidden until then; editable until then.
One cumulative season total; competition rank (ties share); no weekly winner, no weekly purse.

## 2. Design Invariants

- **2.1 The member's number is immediate.** From anywhere in the room, one glance answers: my season
  total, its state (projected or banked), my rank, this week's golfer and where he stands.
- **2.2 Projected and banked are never confusable.** Every money figure carries its state as a word
  (PROJECTED / BANKED) and its material (pencil / ink). The ruled-off double line appears only on a
  settled tournament.
- **2.3 A spent golfer is struck, not hidden.** The field list shows every golfer in the field; the
  ones you have used are struck through with the week they were spent. Scarcity must be visible.
- **2.4 The sheet is in true rank order.** Your line is hoisted above the sheet as its own section;
  your row in the sheet sits at its real rank, marked. Rank is never visually disconnected from position.
- **2.5 No podium.** The leader is not enlarged, has no ring, no band. Every row is the same height;
  the only marked row is yours. The group chat decides who gets celebrated; gold stays the lounge's.
- **2.6 No state is color alone.** Every mark pairs its color with a word or a structure (a chip, a
  strike, a rule). Red never means "under par".
- **2.7 The register seasons, comprehension leads.** Bookkeeper vocabulary carries flavor (the sheet,
  the board, spend, banked, the pot), but every mechanic is also stated plainly where a first-timer
  needs it.

## 3. The Room and the Lounge

The room lives under `/golf/`, scoped by `body.game-golf`. The lounge (`/`) stays the club's purple
and gold; The Pay Sheet enters it only through content, copy and its accent signature (the
`--lounge-golf-*` pair and the `.hl-panel--golf` / `.join--golf` mapping, root `DESIGN.md` §5), never
through this room's paper, pen variables or `.golf-*` classes (`tests/test_lounge_accent_firewall.py`).
Substrate contrast at the threshold is by design: purple outside, paper inside.

Lounge integration is built (U7) and sits behind the flip: the registry entry carries
`lounge_label` "The Pay Sheet", a `lounge_cadence` line and the golf lounge module, and nothing
renders on `/` until Phase L sets `status='open'` and `is_featured=True` together; until then the
registry shows the coming-soon tile. The seat stays open all season while the game is open: the
golf entry sets no `join_open`, so status alone decides and the lounge's ask retires only when the
registry closes the game (Brad, 2026-10-06). The panels (§8.24) are the lounge's own primitives
and nothing else, the firewall in both directions: no `.golf-*` class, no room hex and no
`--golf-*` variable reaches them, and the money on the bill is a figure with its word ("$1,240,000
projected", "banked"), never the room's pencil or ink. The pen reaches the lounge only as the
`--lounge-golf-*` pair the root file owns.

The lounge owns orientation (what is this game, when does it lock, take a seat); the room owns
participation and inspection (the pick, the sheet, the board, the scorecard, the record room).

## 4. Product State Model

### 4.1 Tournament states
- **Upcoming:** on the schedule, field not yet set. "The field publishes Tuesday."
- **Open:** field ≥ 50, picks open; the lock stated as a literal time.
- **Locked:** lock passed, first tee not yet struck. Picks revealed.
- **Live (on the course):** Thursday to Sunday; the `Live` chip in course green; figures PROJECTED.
- **Settling:** final round played, results not finalized; still PROJECTED, "Projected until
  results are official".
- **Banked:** `results_finalized`; figures in ink; the double rule; penalties settled.

### 4.2 Member week states
No pick (pencil "No pick") · Picked, editable · Locked · Live, projected · Banked · Backup activated
("Backup · replaces Scheffler") · Cut / WD / DQ (marker chips) · Penalty $15 (marker chip, majors) ·
Commish override (ink chip "Commish", note on hover/long-press) · Used (pen chip on the scorecard).

### 4.3 Season states
Pre (before the Sony lock: the schedule and the join page lead) · In season (the sheet leads) ·
Final (the sheet banked, the champion recorded, the Record Room leads; `/records` link at U7).

## 5. Decision Priorities

1. An open pick before its lock outranks everything (platform: the deadline is the clock).
2. The member's number and its certainty (projected / banked) outrank the group's.
3. Spend-ability (who is still available, who the room has burned) outranks performance stats.
4. The golfer's own line (position, to par, thru) is secondary text under the money, never a column
   of red figures.

## 6. Identity System

### 6.1 Visual character
A typed money sheet on cool waterproof paper, annotated in pencil while play runs and ruled off in
ink on Monday; a yardage book for the pick. Industrial/Utilitarian with an editorial spine. Nothing
painted: hairline rules, one pen color, and the pencil/ink distinction do all the work.

### 6.2 Light-room doctrine and the paper rebase
A light room, from the use scene (Thursday to Sunday, daytime, outdoors or at a bar with golf on,
phone in sun; Monday morning checking what banked). The dark room stays CFB's alone. This room
rebases exactly four platform tokens under `body.game-golf` and nothing else: `--bg-page` → paper,
`--surface-card` → surface, `--text-primary` → ink, `--text-secondary` → pencil (the purple-cast
platform ink clashes on cool paper). Bootstrap `--bs-*` and every other platform token stay.
Test-locked in `tests/test_golf_design_doc.py`.

### 6.3 Palette
Game-slot variables (set on `body.game-golf` in `style.css`; platform components consume them):

| Slot | Value | Name | Notes |
|---|---|---|---|
| `--game-primary` | `#2439C8` | Pen | Room identity and action: `.btn-game`, the pick CTA, the join hero terminus |
| `--game-primary-dark` | `#1A2A8F` | Pen, pressed | Join hero origin; pressed fills |
| `--game-primary-light` | `#4A5CD6` | Pen, lift | Hover lift for pen fills |
| `--game-accent` | `#2439C8` | Pen | Active week, selected, your bracket, sub-nav accent (one hue, two slots, by design) |
| `--game-accent-light` | `#8C9BFF` | Pen, bright | Pen text on the sub-nav and other dark chrome |

Golf-scoped additions (inside the `/* === THE PAY SHEET (golf) === */` section):
`--golf-rule: #C9CDC2` (sheet hairlines), `--golf-marker: #B3261E` (deduction), `--golf-course: #006747`
(live), `--golf-pen-wash: rgba(36, 57, 200, .08)` (your row's tint; there is no ink wash).

**Accent rank:** pen (identity and action; the only hue) → ink and pencil (certainty) → the state
layer (marker red for deductions, course green for live) → gold (platform-ceremonial only; absent
from the room). The pen is this room's third color under the platform Two-Color Rule and appears only
under `body.game-golf`.

**Blue is personal. Green is environmental.** (Brad, 2026-10-06.) Blue: my pick, my row, the active
week, the CTA. Green: a tournament is currently live. Red: penalty / deduction state. Ink / pencil:
certainty. Strike: an exhausted resource.

**Distinctness constraint:** the pen is a saturated ballpoint blue, deliberately brighter and purer
than the frozen WC navy `#001A4D` / `#002868` and nowhere near the club purple `#3A1D72`. Do not
darken it toward navy or shift it toward violet; if a treatment wants a deep blue it is asking for
ink. Course green is not an identity color: never a fill, never a wash, never on a button.

### 6.4 Contrast constraints (verified at authoring, on paper `#E9EBE4` and surface `#F7F8F3`)
- Ink `#15190F` on paper ≈ 15:1. Pencil `#5A6253` on paper ≈ 5.1:1 (AA body; the floor for muted text).
- Pen `#2439C8` text on paper ≈ 6.9:1; white on pen ≈ 8.4:1; white on pen-lift `#4A5CD6` ≈ 5.5:1.
- Marker `#B3261E` on paper ≈ 5.4:1; course `#006747` on paper ≈ 5.7:1 (chips carry a word anyway).
- Sub-nav `#0F110D`: paper text; pen-bright `#8C9BFF` ≈ 6.7:1 for small accent text; the active pill
  is a pen fill with white text.

### 6.5 The pen is identity, not outcome
Wins, cuts and penalties never borrow the pen. Pen means "mine" and "now"; it is never "good" or
"bad". Outcome lives in the state layer (marker, course) and in structure.

### 6.6 Typography and the money
Platform faces only (Teko display, Newsreader body; the Newsroom Rule). Pay Sheet applications:
- **The hero figure:** Teko 600, `clamp(52px, 17.5vw, 72px)`, lining figures, one per screen (the
  season total on standings, the week's figure on the board, the purse on the pick page).
- **Rank markers:** Teko 600 at 1.5rem ("T4", "12"). Never a Teko column of money: Teko's figures are
  proportional (verified 2026-10-05 on the live site).
- **The money column:** Newsreader 500, `font-variant-numeric: tabular-nums lining-nums`, right-aligned
  to one shared edge (Newsreader's figures are tabular; thirty rows align to the comma).
- **PROJECTED:** pencil color, tilde prefix ("~$412,000"), 1px underline, the word PROJECTED (Teko 500,
  0.8rem, 0.14em) above or beside. **BANKED:** ink, no tilde, a 3px double rule beneath, the word BANKED.
- **Names:** Newsreader 500. **Everything else:** Newsreader 400, 16px floor.
- **Sanctioned caption classes** (≥0.75rem floor): `.golf-label` (Teko 500, 0.95rem, 0.14em,
  uppercase, pencil) over a list or value, never above a heading; `.golf-context` (Newsreader
  0.95rem, pencil) for the event · round · as-of line.

### 6.7 The voice (H1s and copy)
- H1s name the artifact: "The Sheet" (standings), "The Board: Masters Tournament", "Spend a Golfer:
  RBC Heritage" (make pick), "Your Scorecard" / "Cox's Scorecard", "The Record Room" (stats), "The
  Season Book" (schedule), "House Rules". Dynamic-noun dispensation applies (platform §3).
- Copy voice is the grill-room bookkeeper's: dry, exact, money-literate, with the Commish's wry
  authority in headings, leads and empty states, never in error messages. Errors name the problem
  and the recovery plainly ("That field isn't published yet. Picks open Tuesday.").
- Register glossary (use consistently): **the sheet** (season standings), **your line**, **the
  board** (one tournament's results), **the field** (the pick list), **spend / spent** (use a
  golfer), **banked / projected**, **the pot** (the penalty side pot), **the lock** (the deadline,
  always stated as a literal time), **the Commish** (overrides), **the Record Room** (stats).
- On the pick page, one word per control: **Primary**, **Backup**, **Change**, **Keep** (a reopened
  slot), **Lock it in**.
- No em dashes or double hyphens in UI copy (platform Copy Discipline).

### 6.8 Labels, never eyebrows
No eyebrow above a heading (ADR-066): heroes, mastheads and in-page headlines carry their fact in
the heading or the line under it. `.golf-label` sits over a list, a value, a fold or a tile, never
over an H1/H2/H3. A label may be a section's own heading: an `<h2 class="golf-label">` over the
list it heads ("The field", "Still on the board"; ruling 2026-10-06). That is a label set as the
heading, not one above it: nothing heading-sized follows, and the list's opening ink rule carries
the weight a display H2 would, so the H1 stays the page's one heading in display type.
`tests/test_eyebrow_above_heading.py` holds `.golf-label` to the rule. No glyphs on game-body labels
(`◈`/`◇` are lounge ceremony).

### 6.9 Material rules
- Paper, not bone: the room's ground is `--golf-paper`; cards are not the container. The sheet is
  rows separated by `--golf-rule` hairlines, equal in height within a state (56px for a name alone,
  63px for a name over its pencil pick line); a heavier 2px ink rule opens the sheet and the board;
  the double rule closes a banked figure.
- One texture only: the burn hatch (45° pencil hatching inside a 1px pencil frame). It has two
  homes: the field on the pick page (§7.7), and the back office's meter (§8.21), where the same
  hatch is drawn as wide as the share of the month's API reads already spent. It is still the
  room's one texture; the Record Room's Burn List reuses the field's.
- The pen appears as fills (CTA, active pill), as the 3px bracket on your line, as the 8% wash on
  your sheet row, and as chip outlines; on the pick page, as the open slot's frame (§7.6), the
  chosen rows' wash (§7.7) and the text actions (§7.25). Never as a page-scale field. The bracket
  is the room's one sanctioned side-stripe (§6.10).
- Elevation: none inside the sheet. The join hero uses the platform `.page-hero` gradient in the pen
  family; nothing else lifts.

### 6.10 Prohibited visual directions
A second dark room. Gold anywhere in the room. Red for under par or any "good". Green as identity (a
fill, a wash, a button). A podium, avatar rings, a winner band, medals. Cards as the row container,
cards inside cards, side-stripes (`.col-divider` left the standings at U1 and the CSS at U6; the
class is retired). A Teko column of money. Emoji as
icons (the legacy 🏆🥈🥉🔄👑 pills are retired; the override is the "Commish" chip). Sparklines or
trend arrows beside figures (the Record Room's season race is the one chart, and it is opt-in).
Hiding used golfers. Tinting majors.

The member's avatar is not an icon: `User.get_avatar()`, the platform's mark on every standings
surface (its crown and trophy reserved inside it), stays on every sheet and board row, emoji and all
(Brad, 2026-10-06). The emoji ban covers icons the room draws, never the member's own mark.

The side-stripe ban has one sanctioned exception: the 3px pen bracket, drawn as
`.golf-your-line::before` and as the inset edge of `.golf-sheet-row--me`. It is identity, never
status or decoration (§6.5); it marks the member's own line and nothing else; no other primitive in
the room carries a colored edge. A detector `side-tab` finding on the bracket cites this line.

### 6.11 Root rules restated (because `--target games/golf` drops the root file)
The Eyebrow Rule (ADR-066, §6.8). The Two-Color Rule (the pen appears only under `body.game-golf`).
No side-stripes, the pen bracket excepted (§6.10); `.row-current-user` overrides the tint only.
Gradient text is retired. `--text-muted` is for dark substrates only (this room uses
`--text-secondary` = pencil). Every `/static/*` URL carries `?v={{ asset_version }}`. Country flags
are self-hosted SVG. Touch targets ≥ 44px, body ≥ 16px, `prefers-reduced-motion` honored, no
color-only state. Settle the Tab is the platform partial.

### 6.12 Named rules
- **Pencil-and-Ink Rule:** a projected figure is never drawn in ink; a banked figure is never drawn
  in pencil; both carry their word.
- **Struck-Not-Hidden Rule:** a used golfer stays in the field list, struck, with the week he was spent.
- **True-Rank Rule:** your line is a section above the sheet; your row stays at its real rank.
- **One-Hero Rule:** one Teko figure per screen.
- **Ruling-Off Rule:** the double rule and its motion fire only on `results_finalized`.
- **Red-Is-A-Deduction Rule:** marker red appears only on CUT, WD, DQ, Penalty $15 and Unpaid.

## 7. Component Doctrine (build contract; reconciled per cluster)

Class prefix `golf-` (firewall-locked). Each primitive below is a contract; its CSS lands with the
cluster that first ships it and this section is reconciled from the built surface. Reconciled from
U1 and U3 (2026-10-06): §7.1 to §7.4, §7.10, §7.13 and §7.16 to §7.24. Reconciled from U2
(2026-10-06): §7.5 to §7.8, §7.10, §7.15, §7.24 and §7.25 to §7.28. Reconciled from U4 and U5
(2026-10-06): §7.9, §7.11, §7.22 and §7.29 to §7.32, with the season surfaces themselves in §8.
Nothing in §7 is still a contract.

### 7.1 The sheet — `.golf-sheet`, `.golf-sheet-row`, `.golf-sheet-row--me`
A `<table class="golf-sheet">` with visually hidden column heads (rank, member and pick, money) and
each name a row header. It opens on a 2px ink rule and closes on a hairline; rows part on hairlines
and are equal within a state: 56px for a name alone (`.golf-sheet--plain`, the sheet between events)
and 63px for a name over its pencil pick line. Three cells: rank (`.golf-sheet-rank`, Teko, the
competition rank as "1" or "T2"), name (`.golf-sheet-name`, the avatar, the name and
`.golf-pick-line`: golfer · position · figure on The Sheet, golfer · position · to par on The
Board), money (`.golf-sheet-money` holding `.golf-money` with `--projected` / `--banked`). A
projected figure is pencil with a tilde and a 1px underline; a banked figure is ink over a 3px
double rule; a Cut, WD or DQ is a certain $0 and takes no tilde. The `.golf-state` word sits on
every row while an event is live; when every line shares one state it sits once, in
`.golf-sheet-head` over the money column (The Sheet between events, The Board always). The member's
row carries the pen wash and the 3px pen bracket, both bleeding .5rem into the page gutters so rank
and money stay on the shared columns. Every line shows; the sheet is never truncated (§7.10). The
column is 720px; from 1100px The Sheet alone gains a 300px margin column (§7.16). The Board stays a
single column; the Record Room widens.

### 7.2 Your line — `.golf-your-line`, `.golf-hero-figure`
The 3px pen bracket in the margin (`::before`, §6.10). A head row (`.golf-your-line-head`) holds the
`.golf-label` "Your line" and its `.golf-state` word on one baseline. The hero figure (§6.6) is
`--projected` (pencil, a tilde, a single 1px pencil rule) or `--banked` (ink over a double rule that
draws once on load: the ruling-off, §6.12, drawn still under `prefers-reduced-motion`). One pencil
line follows (`.golf-your-line-sub`): rank of n · this week's golfer · position · figure, or the
next pick, or the "Spend a golfer" link when the field is open and no pick is in. On The Board the
same block is "Your pick": the week's figure, the golfer, the backup, their chips. For a viewer with
no pick, or before the lock, it leads with the purse instead: the label "Purse" (with the
`Est. purse` chip when estimated), the figure in plain ink with no rule and no state word ("TBD"
when unknown), then the member's own pick with "Change", or the pick action (§7.24) when the field
is open. A viewer with no line on The Sheet gets no block; "Take a seat" stands in for it
(`.golf-line--lead`) while the room takes seats.

### 7.3 The context line — `.golf-context`
One Newsreader line under the sub-nav (under the H1 on The Board). Its facts are items
(`.golf-context-items > span`), each led by a middle dot, and a dot never opens a line: the row
hangs one dot-width into a clipped margin, so the first item and the first after a wrap show none.
`.golf-nowrap` keeps a fact whole. On The Sheet: the `Live` chip when on the course, the event
(linked to its board), the round, then "Projected as of 4:00 PM CT" (with the weekday once that day
is past), "first read at noon CT" before the first read, or "Projected until results are official"
for a played-out event whose results are not final. Between events: the next event and "picks lock
Thu Apr 16 · 6:05 AM CT" or "the field publishes Tuesday". After the last: "every line is banked".
On The Board: its chips (`Live`, `Major ×1.5`, `Team event`) and the event's dates, then the same
read line, the lock, or the one word "Banked". A banked board states no finalized date (ruling
2026-10-06). The lock is always the short form from `games/golf/utils.format_lock`; Club Letters
keep the platform's long form.

### 7.4 The chips — `.golf-chip`, `--pen`, `--live`, `--deduction`
Teko 500, 0.9rem, 0.1em, uppercase, a 1px outline in the chip's own color, 2px radius, no fill. The
bare chip is ink (there is no `--ink` modifier): Major ×1.5, Team event, Est. purse, and Commish (The
Board only, the override note in its `title`). `--pen`: Used, your backup state, and Primary /
Backup on the chosen field rows (§7.7). `--live`: Live, On
the course (with the 7px dot). `--deduction`: Cut, WD, DQ, Penalty $15, and Unpaid (on an unpaid
member's sheet row, beside the name; public like the sheet, by Brad's ruling of 2026-10-06). A chip is a word, with one exception: on a pick line the
penalty chip reads "Penalty $15" from 576px and "$15" below it, where a Cut or DQ chip always sits
beside it and the word stays for screen readers (`.golf-chip-word`). The penalty chip also carries
the legacy `badge-penalty` class (test-locked presence).

### 7.5 The strike — `.golf-used`
`text-decoration: line-through` 1.5px in pencil, on the name set in pencil at weight 400. A spent
golfer stays in his money-order place in the field (§7.7), never filtered out (§2.3): the pen `Used`
chip sits where a row's action would, and the week he went sits beneath in pencil ("Wk 13 · Masters
Tournament"; "Spent this season" when no pick names the week), on one line with an ellipsis on a
phone. His row keeps its hatch and takes no action.

### 7.6 The pick slots — `.golf-slot`, `.golf-slot--empty`
Two ruled 56px frames (`.golf-slots`), 1px with a 2px radius: a `.golf-label` (Primary, Backup) over
the golfer's name (`.golf-slot-value`, Newsreader 500, 1.1rem), with Change at right. Filled is ink.
`--empty` is dashed pencil and holds its prompt in pencil ("Choose a golfer from the field below." /
"Choose a second golfer from the field."). `.golf-slot--open`, the question being asked, is the pen
frame (the 1px border plus a 1px inset, 2px in all) and its label turns pen; one slot is open at a
time, the first empty one. Change (§7.25) reopens a filled slot and reads Keep while it is open;
Keep closes it unchanged. A slot filled this sitting and a saved one are drawn alike (ruling
2026-10-06): pencil and ink stay the money's (§1.4), and on this page a pencil name is a spent
golfer (§7.5), so a pencilled choice would read as spent. Whether the pick is saved is said in
words at the pick action (§7.24), because one post saves both slots. Stacked on a phone, side by
side from 576px. The backup's one-line rule
(`.golf-slot-rule`, pencil) sits under both: "Your backup plays only if your primary withdraws
before finishing round 2." Without the script the slots hold the form's own selects
(`.golf-slot-select`, 44px); `.golf-pick--js`, set by the page's script, trades them for the slots'
own text (§7.15).

### 7.7 The field — `.golf-field`, `.golf-burn`
A native list over the form's two real selects (§7.15). Tom Select is gone from the room: it left
this page at U2 and the Commish's Pen at U6, which posts four native `.golf-select`s (§8.22). The head (`.golf-field-head`) is an `<h2>` set as the `.golf-label`
"The field", which asks the open question ("The field · spend your primary", "· name a backup"),
with the count in pencil at right (`.golf-field-count`, "71 of 82 yours to spend"; under the label
on a phone). The search (`.golf-search`, 44px, shown by the script) folds case, punctuation and
accents ("jj" finds "J.J.", "hojgaard" finds "Højgaard"), matches every word typed and turns the
count to "3 of 82 match"; Escape clears it. No match: one `.golf-line`, "Nobody in this field
matches “x”.", with "Clear the search" (`.golf-linkbtn`, §7.25).

`.golf-field` is every golfer in the field in money order (season prize money, then name), under a
2px ink rule, on `--golf-rule` hairlines. A row (`.golf-field-row`) is 56px for a name alone and 61
to 62px with its pencil line: the name (Newsreader 500, 1.05rem) over "YTD $1,234,567"
(`.golf-field-sub`), the action at right, the hatch beneath the action. The action
(`.golf-field-pick`, §7.25) is one word, the open slot's (Primary, then Backup), and its target is
the whole row; with no slot open the rows carry no action. Hover and focus lay a 4% pen wash on the
row. A golfer in a slot (`.golf-field-row--mine`) wears the pen wash, bled into the gutters like
your sheet row (§7.1), and a pen chip naming his slot in place of the action. A spent golfer is
struck (§7.5).

The hatch (`.golf-burn`, the room's one texture, §6.9): `.golf-burn-bar` is a 1px pencil frame, 10px
tall, 56px wide on a phone and 96px from 576px, hatched as wide as the share of the room that still
has him; `.golf-burn-pct` is a fixed-width, right-aligned figure, so every bar shares an edge. From
576px the row reads "64% still have him". On a phone it reads "64%" (the words stay for screen
readers) and one pencil line above the list (`.golf-burn-key`) says what the hatch measures: "The
hatch is the share of the room that still has him." No hatch before the season's first burn and no
money line before the first banked tournament: the page draws nothing where there is no signal.

### 7.8 The facts grid — `.golf-facts`
The purse block (`.golf-purse`) leads: the `.golf-label` "Purse" (with the `Est. purse` chip when
estimated) over the page's one Teko figure (`.golf-hero-figure`, §6.6) in plain ink, with no rule
and no state word; "TBD" when unknown. The facts follow under a hairline, a `<dl>` of label over
value (Newsreader 500, 1.05rem, tabular; `.golf-facts-note` is the pencil qualifier): Picks lock
(`.golf-facts-lead`, its own line on a phone), Golfers used ("11 this season"), Yours to spend ("71
of 82 in the field"; absent until the field publishes). Two columns on a phone, three across from
576px.

### 7.9 The tiles — `.golf-tiles`, `.golf-tiles--pair`, `.golf-tiles-note`
Scorecard tiles, a `<dl>`: a 2px ink top rule, a hairline below, hairline cells (`.75rem` padding,
a 1px `--golf-rule` between), the `.golf-label` over its value. The value is NOT Teko, as the
contract said: it is Newsreader 500 at 1.25rem (1.15rem up to 575px), tabular lining figures, in
ink, with `.golf-tiles-note` as the pencil qualifier at .95rem ("29 **of 31**"). The one Teko figure
on the scorecard is the season total (§6.6, §8.2); the tiles read as the facts grid does (§7.8).
Three tiles hold three across on a phone, and there every value is a two-line box with the note on
the line under its figure (`.golf-tiles:not(.golf-tiles--pair) dd { min-height: 3rem }` and the
note `display: block` up to 575px), so the three figures share a baseline whether or not a label
wraps or a note exists; from 576px the note stays on the figure's line and never wraps alone
("$15 out", never "out"). `--pair` is the two-tile row under the weeks (Best pick,
Missed cuts at majors): the figure leads alone and its note takes the line under it; up to 575px the
pair stacks on a hairline. A fold directly under the pair adds no rule of its own (the pair closes on
its hairline).

### 7.10 The fold — `.golf-fold`
A pencil line that opens a `<details>`: a 44px summary with a CSS caret (a drawn corner, no glyph)
that turns when open, and its body in `.golf-fold-body`. Built folds, all closed by default: "Didn't
pick (3)" under the sheet and the board, "The marks" and "House Rules" in the margin, and "Used
golfers (12)" under the field on the pick page: every golfer the member has spent this season, in
this field or not, by week, as a ruled week column (`.golf-spent`, an `<ol>` in the fold body):
"Wk 13" in pencil tabular figures in its own 3.25rem column, then the golfer (Newsreader 500) over
the event in pencil, on hairlines; from 576px the event follows the name, as Still on the board's
note does (§7.26). A long event wraps under its own name, never under the week. A golfer no pick
accounts for runs last with an empty week. A fold never holds lines of the sheet: every line shows
(ruling 2026-10-06).

### 7.11 Sub-nav — `.subnav-golf`
Background `#0F110D`, `--subnav-accent #2439C8`, `--subnav-accent-rgb 36, 57, 200`. Label "THE PAY
SHEET" with "Golf One & Done · {{ season_year }}" as its small line, behind the platform's ⛳ glyph:
that glyph is the sub-nav lockup every room shares (⚽ 🏈 ⚖️), the collapsed mark on phones where the
text hides, and `aria-hidden` beside an `aria-label` on the link; it is navigation chrome, not a
room icon, so §6.10's emoji ban does not reach it. Pills: Standings · Schedule · Results · Stats
(the Record Room, `/golf/stats`) · My Scorecard (the member's own scorecard, `/golf/member/<id>`,
shown to a member with a line; active only on that member's own card, never on another's) · Admin
(golf admins; the pill opens The Back Office, §8.20, and stays active across every `golf.admin*`
endpoint). As built: Standings · Schedule · Results · Stats · My Scorecard · Admin, in that order.
`/golf/my-picks` redirects to the member's scorecard. The platform scroll-fade applies.

### 7.12 Join page
Platform shape (`page-hero` in the pen family, the How It Works list in the thesis's words, the
current display name under `#join-current-name`, `.btn-game` "Take a seat"); collects no name.

### 7.13 Empty states
Reward participation, in `.golf-empty` (§7.21): "Nobody has a line yet. The first member to take a
seat is the sheet's first line." / "Nobody spent a golfer on this one." / "No picks are in yet.
Every pick stays hidden until the lock." Before a field exists: "The field publishes Tuesday. Picks
open then."

### 7.14 Settle the Tab — `.settle-tab`
The platform partial, room surfaces only; the pot's unpaid penalties ride the same card.

### 7.15 JS hooks (preserve)
`#primary_player_id`, `#backup_player_id`, form names `primary_player_id` / `backup_player_id`;
`#tournament_id`, `#user_id`, `#override_note` / `override_note`; `.payment-toggle[data-user-id]`
with `.js-paid-status` (the Paid / Unpaid chip in the same row, the one the toggle flips in place;
the script never reads `.badge`), `.penalty-group > .penalty-input` + `.penalty-save[data-user-id]`,
`meta[name="csrf-token"]`. The back office's classes beside them: `.golf-check` (the label around
the toggle), `.golf-input` (the penalty figure and the note), `.golf-select` on the pen's four
selects (event, member, primary, backup). `.ts-select` is gone: Tom Select left the room at U6.
`tests/test_golf_admin_pages.py` holds the hooks.

On the pick page `#primary_player_id` and `#backup_player_id` are two real selects under those
names, the form's truth with or without the script. The page's own script also reads:
`#golf-pick-form` with `data-saved-primary` / `data-saved-backup`; `[data-slots]`,
`[data-slot="primary"]` / `[data-slot="backup"]`, `[data-slot-value]`, `[data-slot-change]`;
`[data-commit]`, `[data-note-ready]`, `[data-note-change]` (rendered only with a saved pick),
`[data-note-saved]`, `[data-pick-status]` (the polite live
region); `[data-field-question]`, `[data-field-count]`, `[data-search-wrap]`, `#golf-field-search`,
`[data-burn-key]`, `[data-field-none]`, `[data-field-query]`, `[data-field-clear]`; and on each row
`[data-row]` with `data-id`, `data-name` and `data-search`, plus `[data-pick]`, `[data-pick-word]`
and `[data-chip]`. It sets `.golf-pick--js` on the form and toggles `.golf-slot--open`,
`.golf-slot--empty` and `.golf-field-row--mine`.

### 7.16 The page and its margin: `.golf-page`, `.golf-page--margin`, `.golf-margin`
`.golf-page` is the room's column: 720px, centered, 1rem gutters, pen links on a 1px underline, a
2px pen focus ring. `.golf-page--margin` (The Sheet only) is that same single column up to 1100px,
with `.golf-margin` stacked under the sheet; from 1100px it is a grid of the 720px column
(`.golf-main`) and a 300px margin across an 80px gap, the margin sticky beside the sheet. The
context line spans both.

### 7.17 Marginalia: `.golf-note`
A note in the margin opens on a hairline: a `.golf-label`, then `.golf-note-lead` (ink) and
`.golf-note-line` (pencil, its values in ink). Built notes: "Next pick" (the event, its chips, the
purse, the lock, your pick with "Change" or the pick action) and "Prize Pool" (§7.18).
`.golf-note--folds` holds the two margin folds. A note is not a card: no fill, no frame, no lift.

### 7.18 The pot: `.golf-pot`
A three-line `<dl>` ledger in Newsreader tabular figures: "Entry $25 × n", "Penalty pot", and "In
the pool" (`.golf-pot-sum`) under a single 1px ink rule. Never a double rule: the pot is a running
sum, not a banked figure (Ruling-Off Rule, §6.12).

### 7.19 The marks: `.golf-marks`
The room's legend, inside "The marks" fold: each mark drawn in its own material (a pencil figure, an
ink figure, the Live chip, Cut / WD / DQ, the penalty, Unpaid) beside one line that says what it
means. A new mark on the sheet earns its line here.

### 7.20 The week pager: `.golf-pager`, `.golf-pager-week`
The Board is a leaf of the Season Book. A `<nav>` on a hairline at the top of the page: the previous
week's event, "Week 13 of 32" (`.golf-pager-week`), the next week's event. Drawn chevrons, 44px
targets, an empty `.golf-pager-end` at either end of the season. The week cell is the nav's position,
not a label of the title, so it is set like its neighbours (Newsreader 0.95rem, sentence case, pencil),
never in `.golf-label`'s Teko caps: those over the H1 would read as an eyebrow (§6.8). The count is
the season's highest week number.

### 7.21 The plain line and the empty state: `.golf-line`, `.golf-empty`
`.golf-line` is one pencil sentence on a hairline under the board (penalties assessed at a major,
the team-event rule, the read times) or under the sheet ("Every line has a pick on the Masters.");
`--lead` is the unruled line that stands where your line would. `.golf-empty` takes the sheet's
place and its rules (2px ink above, a hairline below), in ink.

### 7.22 The foot: `.golf-foot`
The page's closing links on a hairline, each a 44px target: "The Sheet", "The Season Book", "Last
banked: {event}"; on the scorecard "The Sheet", "The Record Room", "The Season Book"; on the Record
Room "The Sheet", "Your scorecard" (a member with a line, the current season only), "The Season
Book". A leaf before the foot leaves 2.75rem above it.

### 7.23 The titles: `.golf-title`, `.golf-title--page`, `.golf-sheet-head`
`.golf-title` is the H1 at 1.9rem ("The Sheet"); `--page` is The Board's H1 at 2.4rem (1.9rem up to
768px), "The Board: {event}". `.golf-sheet-head` is the baseline row over a sheet: the H1 or the
`.golf-label` "The board" at left, the shared state word at right.

### 7.24 The pick action: `.btn.golf-btn`
The platform `.btn-game` dressed for the room: the pen as a fill (§6.9), 1.25rem, 3px radius, a 2px
pen focus ring. "Spend a golfer", once per screen, and only with an open field and no pick in (on
The Sheet, only for a member with a line); a member with a pick gets the "Change" link instead.

On the pick page the action reads "Lock it in" (`.golf-pick-commit`, under the slots, 12rem wide at
least). It shows once both slots are filled and stands down on a saved, unchanged pick. One pencil
line (`.golf-pick-note`) under it says whether the pick is saved: "Not saved yet. Once it's in, you
can change it until {lock}." on a first pick; "Not saved yet. Until you lock it in, your pick stays
{primary}, with {backup} as your backup." on a change to a saved one (the server writes the names);
"Your pick is in. Change either golfer until {lock}." when nothing has changed. Without the script
the action always shows, beside the line for what the server holds. A focused pick action keeps its pen fill: Bootstrap empties a focused
`.btn` whose hover variables are unset, as they are on `.btn-game`, so `.btn.golf-btn:focus-visible`
restates the fill and sets the ring 3px off it.

### 7.25 The text actions: `.golf-slot-change`, `.golf-field-pick`, `.golf-linkbtn`
Buttons that read as the room's links: pen, a 1px underline 3px below, 1rem, no fill and no frame,
the darker pen on hover, a 2px pen focus ring. Change and Keep on a slot (§7.6), a row's Primary or
Backup (§7.7), "Clear the search". The slot and row actions are 44px touch targets (a row's is the
whole row); `.golf-linkbtn` sits inside a sentence. The filled pen button stays the pick action's
alone (§7.24).

### 7.26 Still on the board: `.golf-still`, `.golf-still-list`
Under the field and its fold on the pick page: the member's five top earners not yet spent, by money
banked this season, in this field or not. An `<h2>` set as the `.golf-label` "Still on the board",
one pencil lead ("Your top earners not yet spent, by money won this season."), then a short ledger
under a 1px ink rule, on hairlines: the name (Newsreader 500) with "in this field" or "not in this
field" in pencil, the figure in `.golf-money` at right. Absent before the first banked tournament.
The Record Room's list is the room's (§8.18).

### 7.27 The event in the title: `.golf-title-event`
The pick page's H1 is `.golf-title--page` (§7.23), "Spend a Golfer: {event}". The event is an inline
block: a name that does not fit beside the colon drops whole to its own line.

### 7.28 The leaf turn: the pick page's motion
Choosing a golfer inks him into the open slot and turns the page back to the slots, where the next
question is the open one. Two things move: the pen frame passes between the slots (border and inset,
.2s, `cubic-bezier(.16, 1, .3, 1)`), and the page scrolls back to the slots when they are off
screen. Focus lands on the newly open slot, or on the pick action once both are in, and a polite
live region says what was chosen and what is next. Under `prefers-reduced-motion` the frame and the
scroll are instant; the turn still happens. Nothing else on the page moves but the fold caret
(§7.10).

### 7.29 The quiet link: `a.golf-quiet`
A link that reads as ink until it is pointed at: `color: inherit`, no underline; on hover and
focus-visible the pen with a 1px underline 3px below. For a column of names or events (the names on
The Sheet and The Board to their scorecards, the event on a scorecard week, the members in the race's
standings and the Commissioner's ledger), where a column of pen-blue would spend the pen on what is
not the member's own (§6.5). Never on a `.btn`; a lone link in a sentence stays the room's pen link.

### 7.30 The tap target: `a.golf-tap`
A link in a line of text with a full touch target: `.8rem` of vertical padding reaches 44px without
moving the line it sits in. The other season in a context line, "Change" on your open week.

### 7.31 The room's select and the card head: `.golf-select`, `.golf-card-head`, `.golf-switch`, `.golf-switch-label`, `.golf-switch-go`
`.golf-select` is the room's `<select>`: 44px tall, a 1px pencil (`--text-secondary`) border, 2px
radius, the card surface, the page's own font; a 2px pen focus ring 2px off. `.golf-card-head` is
the scorecard's head row, the `--page` H1 at left and the member switcher at right (a wrapping flex
row, `.375rem 1.5rem` gaps). The switcher is a GET form that works with no script: the pencil label
"Member" (.95rem), the select (13rem at most on a desk; the full row, stretching, up to 575px) and
"View", a `.golf-linkbtn` 44px square. It carries the selected season as a hidden field when the
card is not this season's.

### 7.32 Your open week: `.golf-weeks-row--open`, `.golf-weeks-act`, `.golf-pick-lock`
The viewer's own open week on the scorecard takes the pen wash across the row, bled .5rem into both
gutters like the sheet's `--me` row, and NO bracket: the bracket marks your line (§7.2, §8.2); the
active week is personal and the wash says so (ruling 2026-10-06). The pick and the lock in the
pick line are ink 500 (`strong`); the lock sits on its own line (`.golf-pick-lock`); the pick action
(§7.24) stands under them with `.625rem` above. An open week has no figure, so its name cell spans
the money column too (`colspan="2"`) and the lock fits on its line on a phone. Another member's open
week carries none of this but the span: its pick is hidden until the lock (§8.4).

## 8. Season surfaces (U4 the scorecard, U5 the Record Room, U6 The Back Office, U7 the champion and the lounge; reconciled 2026-10-06)

The same paper, hairlines, pencil and ink as §7; the scorecard's one Teko figure is the season total
and the Record Room's season race is the room's one chart. Both are `.golf-page`s and run no script
they need: the switcher is a form, the race is drawn by the server, the Burn List shows every row
without its script. Two enhancement scripts live in `static/js/golf/` (`season-replay.js`,
`burn-list.js`), not a blueprint static dir (ruling 2026-10-06, Brad). The event in a sentence is set
after "the" through `games/golf/utils.the_event` ("the Masters Tournament", "the American Express"),
here and on The Sheet.

### 8.1 The scorecard — `/golf/member/<id>`, "Latest week first"
Structure locked by Brad (2026-10-06): the card opens on the week in play and reads back to the
first tee. In order: the card head with the switcher (§7.31), the context line, the total, three
tiles, the weeks newest first, one plain line, the pair of tiles, the Used golfers fold, the
Commissioner's ledger, the foot. The H1 is `.golf-title--page`: "Your Scorecard" or "{Name}'s
Scorecard". The context line (§7.3) says "{year} season · {n} of {m} weeks banked", or "no weeks on
the schedule yet", then the other season as an `a.golf-tap` ("{year} season"): that link IS the
season selector, there is no control for it. Every member's card shows the same sections, Used
golfers included (ruling 2026-10-06, Brad); what differs for another member is the bracket, the
wash, the open week and the pick action.

### 8.2 The total — `.golf-your-line`, `.golf-your-line--theirs`, `.golf-hero-figure`
§7.2's block with the `.golf-label` "Total won", the state word at right (Projected, or Banked in
`--banked`), the one Teko figure (`~` before a projected one, in pencil; banked in ink) over the
double rule, then "**4th** of 19" (Newsreader, the place in ink 500) with the Unpaid `--deduction`
chip when owed. The pen bracket marks the viewer's own card only: another member's total is
`--theirs`, no bracket, no left padding (ruling 2026-10-06).

### 8.3 The three tiles — `.golf-tiles`
§7.9, directly under the total: In the money ("29 **of 31**", or the note "No weeks banked yet" alone),
Golfers used, Commish overrides. All three always show, zeros included.

### 8.4 The weeks — `.golf-weeks`, `.golf-weeks-head`, `.golf-weeks-no`, `.golf-pick-line`, `.golf-pick-aside`, `.golf-pick-dot`
The sheet's table (§7.1) with a week number where the rank would be: `.golf-sheet-head.golf-weeks-head`
carries the `.golf-label` "The weeks, newest first" and the state word Banked once a week has
banked. `.golf-weeks-no` is a 3.25rem pencil column, "Wk 32", tabular, top-aligned with the name;
the event is an `a.golf-quiet` to its own page with the week's chips after it (Live in `--live`,
"Major ×1.5", "Team event"); the pick line under the name, the money at right. A thead exists for
the reader only. Every state of a row, in words:
- **Banked:** the shared pick line in `spent` mode (`_sheet.html`): the golfer who counted wears the
  Used chip (`--pen`), then finish and to-par; the Commish's note is printed in words, quoted, on
  its own aside (a `title` is out of a phone's reach; The Board keeps the note in the chip's title);
  the idle backup is named, "backup Clark", never struck (a strike means spent, §7.5). The aside
  follows on the line from 576px with a " · " dot (`.golf-pick-dot`, `white-space: pre`); up to 575px
  it takes its own line and the dot hides. A line with no figure yet says " · no read yet". The
  money in ink, double-ruled, `$0` included.
- **Live:** the Live chip, the same pick line, the money as a projected read: the state word
  Projected before a pencil figure, its tilde when the read is in pencil.
- **Pending:** "{Primary}, backup {Backup} · results pending", no money.
- **Your open week, pick in:** the `--open` row (§7.32): "Your pick: **Primary**, backup {Backup}.
  Change" (an `a.golf-tap`), then "Picks lock **{time}**" on its own line.
- **Your open week, no pick:** "No pick in yet." and the lock line, then the room's filled button
  "Spend a golfer" (§7.24, `.golf-weeks-act`), once on the page; before the field publishes, "The
  field publishes Tuesday. Picks open then." and no button.
- **Another member's open week:** "Hidden until the lock, {time}", no wash, no action.
- **No pick:** "No pick", no money.
With no week played: `.golf-empty` "No week has been played yet. The first line goes in after the
first lock." Under the table one `.golf-line`: "{n} weeks still to play. The Season Book has …".

### 8.5 The pair — `.golf-tiles--pair`
Best pick (the dollars, then "{Golfer}, {Event}" as the note; "Nothing banked yet") and Missed cuts
at majors (the count; the note "${x} still owed to the pot" or "Settled, ${x} paid"). The note under
the figure, the two stacked up to 575px (§7.9).

### 8.6 Used golfers — `.golf-fold`, `.golf-spent`
§7.10's fold, "Used golfers ({n})", closed, directly on the pair's hairline with no rule of its own:
every golfer this member has spent this season, by week, the ruled week column. On every card, the
viewer's or another member's (ruling 2026-10-06, Brad). Absent until a golfer is spent.

### 8.7 The Commissioner's ledger — `.golf-still.golf-ledger`, `.golf-ledger-count`
§7.26's short ledger reused: the `.golf-label` "The Commissioner's ledger" as the `<h2>`, the lead
"Picks the Commish set by hand this season, on weeks already locked.", then the room's members with
an override, avatar and name (an `a.golf-quiet` to their card; this card's own member gets the pencil
note "this scorecard" instead of a link), the count at right in ink 500 tabular. Empty: "The Commish
has not set a pick by hand this season." It shows on every card so an override is never a secret.

### 8.8 The Record Room — `/golf/stats`, "A contents line and five leaves"
Structure locked by Brad (2026-10-06). `.golf-page--margin.golf-room`: the H1 "The Record Room",
the context line ("{year} season · 12 of 32 events banked", the other season as an `a.golf-tap`),
the contents line, then the five leaves in `.golf-main` and the foot. The room carries no personal
tiles: it links to your scorecard from the foot and the standings. Every empty state is a sentence,
never a blank: "The race starts when the first tournament banks.", "Nobody has banked a dollar yet.
The race starts with the first one.", "Nothing to say yet. The lines go in when the first tournament
banks.", "No prize money is banked yet.", "Nobody has spent a golfer yet. The first banked tournament
starts the list.", "Every golfer with prize money has been spent by somebody."

### 8.9 The contents line — `.golf-margin.golf-contents`, `.golf-contents-list`
A `<nav>` between hairlines: the `.golf-label` "In this room" and an `<ol>` of the five leaves as
in-page links (.95rem, 44px targets, wrapping, 1.25rem apart). Up to 575px the label is visually
hidden and the line is the links alone. From 1100px it moves to the margin column beside the leaves
(grid row 3, column 2) under a 2px ink rule, the links stacked on hairlines.

### 8.10 The leaf — `.golf-leaf`, `.golf-leaf-head`, `.golf-leaf-lead`
Each leaf is a `<section>` on a 2px ink top rule, 2.75rem above (none on the first), .75rem of
padding, `scroll-margin-top: 8rem` for the contents links. `.golf-leaf-head` is the baseline row:
the `.golf-label` as the `<h2>` at left, a state word or count at right. `.golf-leaf-lead` is one
pencil sentence (.95rem, 62ch). A leaf's list opens on a hairline and closes on one: the ink rule
is the leaf's.

### 8.11 The season race — `.golf-race`, `.golf-race-plot`, `.golf-race-svg`, `.golf-race-line`
The room's one chart: banked money, week by week, every member a line. Drawn by the server, finished
and still; it moves only when a member plays it (ruling 2026-10-06, Brad: "opt-in", never autoplays).
The lead "Banked money, week by week, through {the event}." and the state word Banked. The plot is
`clamp(220px, 46vw, 320px)` tall; the SVG stretches to it (`preserveAspectRatio="none"`,
non-scaling strokes), so the words of the plot are HTML text over it, not SVG text, and keep their
size on a phone. Materials: hairline grid lines with the floor in ink; the pack in pencil 1px at .5
opacity (`--pack`); every member at rank 1 in ink 2px (`--leader`), a shared lead never being one
member's; your line in the pen 3px (`--you`), drawn last. No trend arrows, no gold or green dots: the
legacy page's marks did not come over. The SVG carries an `aria-label` that says the count of
tournaments and who leads.

### 8.12 The race's words — `.golf-race-marks`, `.golf-race-tick`, `.golf-race-month`, `.golf-race-name`, `.golf-race-name--below`, `.golf-race-dot`
Pencil tabular at .8125rem over the plot, `aria-hidden`, positioned by `--x`/`--y` percentages: the
money ticks beside the grid, the months along the floor (a month at the right edge is set back
whole, `--end`). Two names at most sit at their lines' last points, Newsreader 500 in a halo of paper
(`text-shadow` in `--bg-page`, eight directions): yours in the pen, the lead's in ink, as a name or
how many share it ("3 tied"); the upper above its line, the lower below (`--below`). A single event
is one point per line at the plot's right end (`.golf-race-dot`, 9px in ink or pen with a paper ring;
the pack 5px pencil at .5) and no replay.

### 8.13 The key and the controls — `.golf-race-bar`, `.golf-race-key`, `.golf-race-swatch`, `.golf-race-play`, `.golf-race-scrub`, `.golf-race-range`, `.golf-race-readout`, `.golf-race-playhead`, `.golf-race-baton`
The bar over the plot (44px, wrapping): the key as pencil .95rem items with a 22px swatch each: You
(pen 3px), the leader or leaders by name ("Cox, in the lead", "Cox and Rao, tied for the lead",
"3 members, tied for the lead", ", level with you" when you share it) with the ink 2px swatch, "The
room" with the pencil 1px. "Play the season" (`.golf-linkbtn`, 44px) at right is hidden until the script shows it. The
scrubber under the plot, hidden the same way: the readout "Through {event}" in pencil, and a range
the width of the plot's drawn span (`--pad-left`/`--pad-right`), 44px tall, a 2px ink track, a 20px
pen thumb with a 2px paper border (16px in Firefox), a 2px pen focus ring. Playing or scrubbing
(`.golf-race--scrubbing`): a dashed pencil playhead crosses, the lines reveal up to it (a clip
rect), a baton dot rides your line and the leader's, the names fade. Under
`prefers-reduced-motion` the season does not play; the slider still steps it, and the rows below
take no transition.

### 8.14 The race's standings and its table — `.golf-race-standings`, `.golf-race-row`, `.golf-race-row--me`, `.golf-race-rank`, `.golf-race-member`
Under the plot, every line in the sheet's order between hairlines: a 3rem rank column (Teko 600,
1.5rem, lining, competition rank), avatar and name (an `a.golf-quiet` to the scorecard; "(your line)"
for the reader), the money in `.golf-money`. Your row takes the pen wash bled .5rem into the gutters
and the 3px bracket, like the sheet's `--me`. When the season plays the rows change places
(`transform .5s cubic-bezier(.16, 1, .3, 1)`) so the lead changing hands is watched. A visually
hidden `<table>` with the caption "The season race: banked total after each tournament" holds every
member's total after every event for a screen reader; the JSON payload for the replay is a
`data-race-data` script.

### 8.15 The lines — `.golf-lines`
Superlatives are lines, never awards: a `<dl>` where each line is a pencil term (.95rem, 400) over
one sentence (1.05rem, 62ch, `text-wrap: pretty`) with the member's name in 600 and the money in
`.golf-money`, on hairlines, no label in Teko and no medal. Five at most: Pick of the season
("**Cox** spent Scottie Scheffler at the Masters Tournament for $4,200,000"), Most consistent, WD
survivor, Most missed cuts, Coldest pick (its sum only when there is one). Each but the first shows
only when it has a subject.

### 8.16 Form Guide — `.golf-still-list.golf-form`, `.golf-form-sub`
The tour's own money: `.golf-still-list` (§7.26) of the season's top earners, the name over a pencil
sub-line in tabular figures ("12 events · best 1st · 2 missed cuts"), the prize at right. The lead:
"The season's top earners on tour, by their own prize money."

### 8.17 The Burn List — `.golf-field.golf-burnlist`, `.golf-burn-find`, `.golf-burn-more`, `.golf-field-count`
The field's rows and the field's hatch (§7.7) with no action: every golfer the room has spent, the
most spent first, the name, the sub-line "Spent by 7 · $1,240,000 banked" (allowed to wrap), and the
hatch spanning both lines at right, "43% still have him" (`--have`). The count in the leaf head
("31 golfers", `aria-live`). With its script the list opens on twelve rows and "Show all {N}"
(`.golf-linkbtn`, 44px) opens the rest; the search `.golf-search` ("Find a golfer") appears and
filters by `data-search`, with the field's none line "Nobody has spent “{q}”. Clear the search"; the
count follows. Without the script every row shows and nothing is hidden.

### 8.18 Still on the Board — `.golf-still-list`
The Burn List's complement: the top earners nobody in the room has spent, by money won this season,
name and prize on the short ledger (§7.26). The pick page's version is the member's own five; this
one is the room's.

### 8.19 The Pre line on The Sheet
Before the schedule is posted the context line (§7.3) reads "{year} season · the schedule is not
posted yet": there is no event to name, no lock to state and no champion. The same two items open
every back-office page's context line while the book is empty ("the schedule is not posted yet"
where the banked count would be). Once the last event banks the line reads "{year} season · every
line is banked" and the champion fold (§8.23) leads the sheet. The Pre state is the season's
(§4.3); the lounge says it in its own words (§8.24).

### 8.20 The back office: the ledger book — `.golf-book`, `.golf-book-here`
The commissioner's pages are leaves of one book on the room's paper, never a dashboard of stat
tiles over cards of links and alerts (the admin surface brief, FORM: the ledger book, Brad's lock of
2026-10-06). Five pages under `/golf/admin/`, each a `.golf-page` of the same head: the
`.golf-title--page` H1 naming the page ("The Back Office", "Settle the Book", "The Roster", "The
Tab", "The Commish's Pen"), the context line, then the book line. The book line (`_book.html`) is a
`<nav>` between hairlines: the `.golf-label` "In this book" and the five names on the contents
list (§8.9, `.golf-contents-list`, 44px targets, wrapping to two rows on a phone); the page in hand
is `.golf-book-here`, ink 500, `aria-current="page"`, unlinked. Below 1100px and above it the book
is one 720px column: a ledger is read top to bottom, never side by side. Every leaf keeps the sheet,
the chips, the folds and the text actions of §7; the pages carry no card, no Bootstrap badge, no
icon font, no inline style but a share the server computed, and no eyebrow
(`tests/test_golf_admin_pages.py`).

The dashboard ("The Back Office") is three ledgers in the order they need doing, each a
`.golf-leaf` (§8.10) with its `.golf-label` as the `<h2>` and `.golf-leaf-aside` (pencil, .95rem,
tabular) as the count at right. **To settle:** the played events not yet banked as `.golf-field`
rows (name as an `a.golf-quiet` to its board, its Major ×1.5 / Team event chips, the pencil
sub-line "Wk 16 · Apr 16 to 19 · complete, not banked"), each with Process (`.golf-linkbtn`, a POST
form) where the field's action sits; with nothing to settle, one lead: "Nothing to settle. Every
played event is banked." **The tab:** three tiles (§7.9) under a hairline (`.golf-leaf .golf-tiles`
opens on a hairline; the ledger's own rule is the ink one): Paid "12 **of 19**", Collected, Penalty
pot with "$15 out" as its note, then two links in a `.golf-foot` with no rule of its own
(`.golf-tiles + .golf-foot`). **The reads:** the meter (§8.21). The context line carries the season,
the banked count and "112 of 250 reads this month".

The other leaves. **Settle the Book** (`tournaments.html`): the season book as the weeks table
(§8.4, `.golf-sheet.golf-weeks`): the week column, the event (quiet link, Live chip while
`status == 'active'`, the major and team chips, the dates · the field count · the lock while it is
open), and `.golf-sheet-state` where the money column would be: "Banked" (`.golf-state--banked`),
Process on a complete event, "On the course", or "Upcoming". **The Roster** (`users.html`): a
`.golf-sheet--plain` of this season's enrollees: avatar, name (quiet link to the scorecard), the
Commish chip for an admin, the email on the pick line (`.golf-email`, `overflow-wrap: anywhere`, so
an address breaks before the row does), the banked money in ink, and the entry-fee check
(`.golf-sheet-fee`, §8.21). **The Tab** (`payments.html`): the same three tiles, then "Line by line"
(the unpaid count as the aside): every enrollee with the check, and under a member who owes a
penalty the penalty line (§8.21). **The Commish's Pen** (`override_pick.html`, §8.22). Each page's
empty state is a sentence in `.golf-empty` ("Nobody has a seat yet, so there is no tab.").

### 8.21 The back office's marks — `.golf-meter`, `.golf-check`, `.golf-input`, `.golf-sheet-fee`, `.golf-sheet-state`, `.golf-penalty`, `.golf-leaf-aside`, `.golf-email`
**The meter** (`.golf-meter`, the dashboard's signature mark): the month's SlashGolf reads as the
burn hatch, the room's one texture (§6.9). A wrapping flex row: `.golf-meter-figure` ("112 **of
250**", Newsreader 500, 1.25rem, tabular, ink, the limit as a `.golf-tiles-note`) beside
`.golf-burn-bar.golf-meter-bar`, the field's 1px pencil frame grown to 12px tall and 10rem to 20rem
wide, hatched to `--have`, the share spent (capped at 100). The row is `role="img"` with the figure
as its label. The `.golf-line` under it says what is left and when the last read was, in words:
"**131 left.** Last read Tuesday 6:05 AM CT."; past four fifths the sentence leads in ink 500
("**Four fifths of the month's reads are spent.** 42 left."); over the budget it says by how many.
No color alone says it. A second line breaks the count down by endpoint; a third says what the
meter is: "RapidAPI counts from the subscription day, not the first, so read this as a floor. The
timers are the budget; this only reports." (§9).

**The check** (`.golf-check`): the entry-fee toggle is a native checkbox in the pen
(`accent-color: var(--game-primary)`, 22px, a 2px pen focus ring), wrapped in a 44px label with its
chip beside it: the bare ink chip "Paid" or the `--deduction` chip "Unpaid" (the Red-Is-A-Deduction
Rule, §6.12), the chip carrying `.js-paid-status` so the script flips it in place. The cell is
`.golf-sheet-fee`, right-aligned at the end of the row; on a phone the chip drops under its check so
the roster row keeps its money. `.golf-sheet-state` is the same end cell holding a state word or a
Process form instead.

**The input** (`.golf-input`): the select's twin (§7.31): 44px, a 1px pencil frame, 2px radius, the
card surface, the page's own font, the 2px pen ring 2px off. `textarea.golf-input` fills its column
and resizes vertically. **The penalty line** (`.golf-penalty`, the legacy `penalty-group` beside
it): under an owing member's name on The Tab, a pencil .95rem row: "Penalty owed **$30**" with the
outstanding figure as a `--deduction` chip ("$15 out", with the legacy `badge-penalty` class) or
"· settled", then `.golf-penalty-field`: the label "Paid $", a 6.5rem number `.golf-input`, and Save
as a `.golf-linkbtn`. Saving reloads the page so owed, outstanding and the pot recompute.

### 8.22 The Commish's Pen — `.golf-pen`, `.golf-pen-grid`, `.golf-pen-field`, `.golf-pen-note`, `.golf-confirm`, `.golf-confirm-act`, `.golf-recent`
The override form is a `<form class="golf-pen">` of `.golf-pen-field`s, each a `.golf-label` over
its control, two across from 576px (`.golf-pen-grid`): Event and Member (the room's `.golf-select`,
§7.31, full width; choosing either reloads the page with that field, the page's only script), then,
once the field is loaded, Primary and Backup (native selects over the field, a used golfer disabled
and marked "(used)"), and The note (a `textarea.golf-input` with the pencil italic `.golf-pen-note`
"Printed on the member's scorecard, in quotes."). The pick on the book is stated in a `.golf-line`
("On the book: **Scheffler**, backup Clark" with the Commish chip when it is already an override).
The one pen fill on the page is "Write the override" (`.btn.golf-btn`, §7.24). No field yet: the
empty state "The field publishes Tuesday. The pen waits for it."

**The confirm** (`.golf-confirm`, the gate): when the event is complete, the first save renders the
consequence above the form and commits nothing. A section on a 2px ink rule closing on a hairline:
the `.golf-label` "Confirm before re-resolving", then the marginalia's own lines (§7.17,
`.golf-note-lead` in ink, `.golf-note-line` in pencil with its figures in ink): the event is
complete; what re-resolving recalculates and the member's season total now; the pick on the book
and its money; the change proposed. `.golf-confirm-act` holds the two actions: "Confirm and
re-resolve", a `.btn.golf-btn` carrying the same selections and `confirm=1` as hidden fields, and
Cancel as a `.golf-linkbtn`. Under the gate the confirm is the page's one fill: the form's own
action becomes the text action "Write it differently" (`tests/test_golf_admin_pages.py`).

**Recent overrides** (`.golf-recent`): a leaf under the form, a list between hairlines, each item
on a hairline: `.golf-recent-head` (the member in `.golf-still-name` at left, the date at right in
pencil tabular), `.golf-recent-line` (event · primary, backup) in pencil, and the note quoted in
`.golf-pen-note`. Empty: "No overrides yet this season." The context line counts the season's
overrides.

### 8.23 The champion fold — `.golf-champion`, `.golf-champion-list`, `.golf-champion-name`
When every event of a season is banked (§4.3 Final), the champion leads The Sheet and the Record
Room: a `<section class="golf-champion">` on a 2px ink rule, above your line on The Sheet and above
the race leaf in the Record Room (the leaf keeps its own ink rule, 2.25rem below the fold), rendered
by the `champion_fold` macro in `_champion.html` (imported with context: the avatar reads the
request's champion cache). The `.golf-label` as the `<h2>`: "Champion", or "Champions, tied" when
the place is shared. One `<li>` per champion on hairlines: the avatar and the name
(`.golf-champion-name`, Newsreader 500, 1.35rem, ink; an `a.golf-quiet` to the scorecard when the
row is linked) at left, the figure at right as `.golf-money--banked` at 1.25rem (ink, the double
rule: the season is banked). No band, no fill, no gold, no enlargement: the room's materials say it
(§2.5 No podium holds; the fold is a section of the page, not a marked row).

Two sources (`routes.py::_champions`): once the Commish has closed the season (`flask records close
golf YEAR`), the club's record's place-1 rows for the game and year (`finishes_for`, one query), the
name and the stored `detail` figure; before that, the page's own leaders: on The Sheet the rows at
rank 1 of the sheet it just built, in the Record Room the race's `is_leader` series. Two sentences
(`_champion_line`), one `.golf-line` under the list with its link: on the record, "On the club's
record." with "The Record" (to `/records#board-golf-{year}`); not yet, The Sheet says "The season
is banked." with "The Record Room", and the Record Room says "The season is banked and not on the
club's record yet; the Commish closes it." with "The Sheet". The fold never renders with no champion
or before the last event banks.

### 8.24 The lounge panels (U7)
The Pay Sheet's presence on `/`, behind the flip (§3). Four templates under
`games/golf/templates/golf/lounge/`, every one in the lounge's own primitives (`.hl-panel`,
`.decree`, `.summons`, `.hl-cta`, `.hl-standings`, `.join.hl-conv`; root `DESIGN.md` §5) under the
golf accent hooks: `.hl-panel--golf` and `.join--golf` map `--hl-accent` / `--hl-accent-bright` /
`--hl-ground` onto `--lounge-golf-accent` `#2439C8`, `--lounge-golf-accent-bright` `#8C9BFF` and
`--lounge-golf-ground` `#1A2A8F` (the pen, the pen bright, the pen pressed, re-declared as lounge
tokens in `tokens.css`), with a middle-hand wash (24% to 6% of the ground, 180deg: the pen is a
cool saturated blue on purple). Every action is the solid `.hl-cta` (ADR-052): "Take a Seat",
"Enter the Room", "Spend a Golfer", "Join the Pay Sheet".

- **Pre** (`_panel_pre.html`): the decree seal band ("By Decree of the Commish No 004 · The Pay
  Sheet '27"), the ◇ "Opening Round" summons (the lounge's own eyebrow, ADR-052; not this room's),
  "{Sony Open} opens the season. Picks lock {Thu Jan 15 · 9:00 AM CT}." or "The schedule posts in
  January.", one line of the thesis, and the seat or the door.
- **Live** (`_panel_live.html`): for a member, "Week 16 · RBC Heritage" over their line as a figure
  with its word ("$1,240,000 projected · 4th of 19"), this week's golfer and position, then the next
  lock and the leader in the meta line; the one ask is "Spend a Golfer" when the next field is open
  and no pick is in (the echo: "No pick is $0 for the week. No penalty, no autopick."), else "Enter
  the Room". A visitor gets the sell and the leader's figure while the seat is open.
- **Post** (`_panel_post.html`): "The Sheet Is Banked", the champion or champions by name with the
  money across the events, the Record Room as the route link, and the top three of the final sheet
  as the lounge's own `.hl-standings` rolls (the lounge's gold on rank 1 is lounge chrome, §2.5),
  "banked" as each tagline.
- **The conversion card** (`_conv_card.html`): the club's third corner on the logged-out bill: the
  ◇ seal, the floor-gated seat count, the ⛳ mark, the name, the genre line "Golf One & Done across
  the PGA Tour season", three tape lines, the first lock, and the ask; closed, "The sheet is closed.
  Late seats are granted by the Commish."

`services/lounge.py` is the registry-bound pair: `golf_lounge_state()` reads the season's schedule
(no events: pre; every event banked: post; a lock passed: live) and `build_lounge_context` builds
the per-state data from the sheet's own builder (`services/sheet.py`) over rows loaded once, so the
lounge says the same money the room does; the roster floor is the shared `ROSTER_COUNT_FLOOR`. With
three headliners the bill takes `.hl-duo--trio`: three equal columns from 1100px on two gold
hairlines and no seal, one stacked column below, never two-and-one (the lounge bills every headliner
as an equal).

## 9. Engineering Invariants
Contracts that guard scoring correctness and admin operations. All test-locked; change the test with
the rule, never around it.

- **Only the golfer who counted is spent** (`GolfSeasonPlayerUsage`; `resolve_pick` in
  `games/golf/models.py`): a primary who withdrew before finishing round 2 returns to the pool.
  `tests/test_golf_scoring.py`.
- **Projected is never a stored truth:** `points_earned` is written only by result processing; live
  figures come from `utils.calculate_projected_earnings` (major ×1.5 applied once). An unfinalized
  board says PROJECTED and never the word "Earnings"; a finalized board says BANKED and never
  PROJECTED. `tests/test_golf_conformance.py`.
- **The penalty is derived:** owed = incidents × `PENALTY_PER_INCIDENT` − `penalty_paid`; refreshed
  live by `refresh_tournament_penalties`; never hand-written. `tests/test_golf_penalty.py`.
- **A tournament never auto-completes:** only a sync confirming official results sets `complete` and
  `results_finalized`. `tests/test_golf_cleanup.py`.
- **Every read is season-scoped** (`season_year` on enrollment, tournaments, usage); the scorecard
  and the Record Room take a season. `tests/test_season_scoping.py` pattern.
- **Reminders de-dup on the sent flag, never on cadence** (`last_reminder_type`,
  `utils/reminders.py::tier_already_sent`). `tests/test_golf_automation.py`.
- **The `golf-*` timer cadence is the API budget** (free SlashGolf tier, ~115 of 250 calls a month).
  `tests/test_golf_timers.py`.
- **No per-row queries on the sheet or the board:** both are built by
  `games/golf/services/sheet.py`, pure builders over rows the route already loaded; every sort and
  rank happens there, in competition rank (ties share and gap), never in a template.
  `tests/test_golf_sheet.py`; the route query-count locks stay in `tests/test_golf_cleanup.py`.
- **Nothing shows before the lock:** until the lock passes, no other member's golfer or name reaches
  the board template; the page states only how many picks are in. `tests/test_golf_sheet.py`.
- **The week turns over at the lock, never at a status:** the Board opens, the Sheet pencils a week
  and the next pick moves on when `is_deadline_passed()` does (the pick form's own test). A sync
  writes `active` from Thursday midnight and the request hook moves `upcoming` up to a refresh
  interval late, so status alone is wrong on both sides of the lock. Status decides the next pick
  only for a tournament with no deadline yet (`upcoming`), because the lock reads a missing
  deadline as open. `tests/test_golf_sheet.py`.
- **One clock:** `games/golf/utils.get_current_time()` is the room's now and honors `GOLF_FAKE_NOW`
  only when `ENVIRONMENT` is `development` or `testing` (a naive value is UTC, a malformed one falls
  back to real time, production never reads it). The lock (`is_deadline_passed`),
  `update_status_from_time`, the routes' event clock and the `golf_current_time` template value all
  read it; the lock is stated through `format_lock`. The sync, CLI and reminder clocks still read
  real time. `tests/test_golf_time_seam.py`.
- **A spent golfer is struck, never filtered out** (§2.3): the field lists every golfer in it in
  money order; a spent one keeps his place as a struck row with no action, and is a disabled option
  in both selects. `tests/test_golf_pick_page.py`.
- **The search fold exists three times:** `games/golf/services/field.py::search_key` writes each
  row's `data-search`; the pick page's script and the Burn List's (`static/js/golf/burn-list.js`)
  each fold the typed query the same way. The three change together.
  `tests/test_golf_pick_page.py`, `tests/test_golf_record_room.py`.
- **The pick form posts with no script:** two real selects, the CSRF token and a submit; the script
  only fills the selects, and the page loads no library. `tests/test_golf_pick_page.py`.
- **The saved pick comes from the server:** the script reads `data-saved-primary` /
  `data-saved-backup` off the form, never a select a reload may have refilled.
  `tests/test_golf_pick_page.py`.
- **No query per golfer on the pick page:** `build_field` is a pure builder over maps the view loads
  once (`ytd_earnings`, `remaining_pct_map`, `spent_weeks` in `games/golf/services/stats.py`); the
  query count does not grow with the field. `tests/test_golf_pick_page.py`.
- **The burn share's room is the season's enrollees:** `remaining_pct_map` is the complement of the
  rounded burn share, and is None, never a map of 100s, before the season's first burn. Season
  money is banked tournaments only. `tests/test_golf_stats.py`.
- **An unpublished field takes no pick:** a GET renders the facts and the empty state (§7.13); a
  POST writes nothing. `tests/test_golf_pick_page.py`.
- **Past the lock the pick page redirects to that week's Board** (the week turns over at the lock,
  above). `tests/test_golf_pick_page.py`.
- **A refused pick writes nothing:** it says why, and a refused change keeps the saved pick.
  `tests/test_golf_pick_page.py`.
- **The scorecard is public and secret by the lock:** `/golf/member/<id>` carries no decorator, like
  the sheet and the board. A week is revealed at its lock or once banked
  (`games/golf/services/scorecard.py::revealed`; the lock reads a missing deadline as open, and a
  banked week can lack one). Until then its pick is dropped in the builder for everyone but its
  member, and the Commissioner's ledger counts revealed weeks only. `/golf/my-picks` is the old
  address and redirects to the member's own scorecard. `tests/test_golf_scorecard.py`.
- **The scorecard's rank and total are the sheet's own row:** the view builds the same
  `build_sheet`, with the live event's `week_lines` when one is on the course, and the card takes
  the member's row from it, pencil included. `tests/test_golf_scorecard.py`.
- **Missed cuts at majors is the flag, never a status:** the tile and its pot count
  `penalty_triggered`, the flag the scoring wrote, so they always equal
  `GolfEnrollment.penalty_owed()` whatever casing a result's status arrived in.
  `tests/test_golf_scorecard.py`.
- **The Record Room reads banked tournaments only** (`results_finalized`, never a status), and the
  room is the season's enrollees: the race draws every one of them, in the sheet's order and in
  competition rank; a pick by anyone else is not the room's. A missed cut is read whatever its
  casing. A superlative names the golfer the board names (the backup when he counted).
  `tests/test_golf_stats.py`, `tests/test_golf_record_room.py`.
- **No query per week, member or golfer on the season surfaces:** `build_scorecard` is a pure
  builder over rows the view loads once, and every Record Room aggregate in
  `games/golf/services/stats.py` runs a fixed number of grouped queries and takes the room's names
  as a map (no name is looked up per row). Both routes' query counts are locked against a growing
  season. `tests/test_golf_scorecard.py`, `tests/test_golf_record_room.py`.
- **A season is a query argument:** the scorecard and the Record Room take `?season=` and default
  to the configured season. The scorecard is a 404 for a member with no line that season; the
  Record Room is a 404 for a season with no tournaments, the configured one excepted. A past
  season takes no pick. `tests/test_golf_scorecard.py`, `tests/test_golf_record_room.py`.
- **The season race is drawn by the server, finished and still:** the geometry is
  `stats.race_chart_geometry`, pure arithmetic; the replay script's payload is the same coordinates
  the polylines were drawn from. The room's two scripts (`static/js/golf/season-replay.js`,
  `burn-list.js`) are local, versioned and load no library; their controls are `hidden` until the
  script shows them, the page is whole without them, the replay ranks in competition rank like the
  server, and under `prefers-reduced-motion` the season does not play (the slider still steps it).
  `tests/test_golf_stats.py`, `tests/test_golf_record_room.py`.
- **The meter is display only; the `golf-*` timer cadence stays the budget:**
  `services/api_usage.py::read_api_usage` counts every attempt that reached RapidAPI
  (`status != 0`: a 4xx, a 5xx and every retry included; a network failure never left the box) in
  the league's month over the live call log and its three rotations; the sync stamps the log in UTC
  and the meter reads it in league time. A missing log reads as nothing spent. Nothing here gates a
  call. `tests/test_golf_api_usage.py`, `tests/test_golf_timers.py`.
- **A complete-tournament override needs `confirm=1`:** the first POST on a complete event renders
  the consequence (§8.22) and commits nothing; only the re-post carrying `confirm=1` re-resolves.
  `tests/test_golf_conformance.py`.
- **`clear_resolution` is season-scoped:** re-resolving a pick on a complete event clears its usage
  and money for that season only. `tests/test_golf_conformance.py`.
- **The admin lists are this season's enrollees** (the roster, the tab, the dashboard's counts and
  the pen's member select), and every admin route is behind the two-tier `golf_admin_required`
  (platform admin, then this season's enrollment admin; a prior season's admin is refused; every
  mutating route rejects GET). `tests/test_golf_admin_route_matrix.py`. The admin templates carry no
  pre-U markup (no card, badge, stat block, Tom Select, icon font or eyebrow) and keep every §7.15
  hook. `tests/test_golf_admin_pages.py`.
- **The record seam:** `services/records.py::season_finishes(year)` closes any year whose every
  event is banked (`results_finalized`; a season with no schedule or an open event raises
  `SeasonNotClosed`), ranked by the stored season total in competition rank (ties share and gap),
  every row linked to its user, the champion outcome at place 1 (tied leaders are both champions);
  a past season closes from its own rows. Wired through the registry's `season_finishes`.
  `tests/test_golf_records.py`.
- **The champion fold's two sources and the Pre line:** the fold renders only once every event is
  banked, from the record's place-1 rows when the season is closed and from the page's own leaders
  until then, the sentence saying which; before the schedule is posted the context line says so and
  no fold renders. `tests/test_golf_sheet.py`, `tests/test_golf_record_room.py`.
- **The lounge is read-only:** `services/lounge.py` never imports `services/sync`,
  `services/reminders`, `golf/cli` or `legacy_import`; it resolves the state from the schedule and
  its locks, works on empty tables (every foreign render of `/` runs on them), and its query count
  does not grow with the room. `tests/test_golf_lounge.py`. The panels pass the accent firewall (no
  `golf-` class, no `--golf-*` or `--game-*` var, the `--lounge-golf-*` pair only) and CTA parity
  (every action a solid `.hl-cta`). `tests/test_lounge_accent_firewall.py`,
  `tests/test_lounge_cta_parity.py`. Three headliners take `.hl-duo--trio`, equal columns on two
  seams and no seal; two still pair. `tests/test_lounge_trio.py`,
  `tests/test_design_lounge_undercard.py`.
- **Enrollment is explicit:** pick and override paths never create `GolfEnrollment` rows.
  `tests/test_golf_auto_enroll_removed.py`.
- **The name:** registry `display_name` "The Pay Sheet", `short_name='Golf'` (string-locked),
  `launch_label='2027'`; the sub-nav carries "Golf One & Done · {season}" and never a literal year.
