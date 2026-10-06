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
> from U1 (The Sheet) and U3 (The Board), then from U2 (the pick page), all on 2026-10-06, and §7.9
> (the tiles) stays a contract until its cluster ships. Later clusters extend this file rather than
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
Substrate contrast at the threshold is by design: purple outside, paper inside. Lounge integration is
U7's own decision (roadmap); until then the registry shows the coming-soon tile.

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
- One texture only: the burn hatch (45° pencil hatching inside a 1px pencil frame) on the pick page.
- The pen appears as fills (CTA, active pill), as the 3px bracket on your line, as the 8% wash on
  your sheet row, and as chip outlines; on the pick page, as the open slot's frame (§7.6), the
  chosen rows' wash (§7.7) and the text actions (§7.25). Never as a page-scale field. The bracket
  is the room's one sanctioned side-stripe (§6.10).
- Elevation: none inside the sheet. The join hero uses the platform `.page-hero` gradient in the pen
  family; nothing else lifts.

### 6.10 Prohibited visual directions
A second dark room. Gold anywhere in the room. Red for under par or any "good". Green as identity (a
fill, a wash, a button). A podium, avatar rings, a winner band, medals. Cards as the row container,
cards inside cards, side-stripes (`.col-divider` left the standings at U1; the class itself retires
with admin payments at U6). A Teko column of money. Emoji as
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
(2026-10-06): §7.5 to §7.8, §7.10, §7.15, §7.24 and §7.25 to §7.28. Still a contract: §7.9.

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
A native list over the form's two real selects (§7.15). Tom Select left this page; the admin
override page keeps it until U6. The head (`.golf-field-head`) is an `<h2>` set as the `.golf-label`
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

### 7.9 The tiles — `.golf-tiles`
Scorecard tiles: an ink top rule, hairline cells, `.golf-label` over a Teko value with a pencil
qualifier ("4th of 19", "29 of 31").

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
room icon, so §6.10's emoji ban does not reach it. Pills: Standings · Schedule ·
Results · Stats · My Scorecard (members) · Admin (golf admins). The platform scroll-fade applies.

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
`#tournament_id`, `#user_id`, `.ts-select`, `override_note`; `.payment-toggle[data-user-id]`,
`.penalty-group > .penalty-input` + `.penalty-save[data-user-id]`, `meta[name="csrf-token"]`.

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
banked: {event}".

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
The Record Room's fuller list (§8) arrives with its own cluster.

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

## 8. Season surfaces (U4 to U7; written when built)
The scorecard, the Record Room (season race, superlatives, Form Guide, Burn List, Still on the
Board), the champion fold and the lounge panels extend §7 in their own clusters.

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
- **The search fold exists twice:** `games/golf/services/field.py::search_key` writes each row's
  `data-search` and the page script's `fold` reads the query. The two change together.
  `tests/test_golf_pick_page.py`.
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
- **Enrollment is explicit:** pick and override paths never create `GolfEnrollment` rows.
  `tests/test_golf_auto_enroll_removed.py`.
- **The name:** registry `display_name` "The Pay Sheet", `short_name='Golf'` (string-locked),
  `launch_label='2027'`; the sub-nav carries "Golf One & Done · {season}" and never a literal year.
