---
version: 1
slug: "games-golf-templates-golf-index-html"
primary_target: "games/golf/templates/golf/index.html"
related_targets: []
---

# The Sheet (`/golf/`)

Scope: the Pay Sheet's landing page, Operate mode (check, compare, act on an open pick). Audience: a club member on a phone, Thursday to Sunday with golf on, or Monday morning checking what banked; also anyone signed out, since the sheet is public. Job: see my season total and whether it is projected or banked, my rank, this week's golfer and where he stands; then read the room in rank order. One action: spend a golfer when the next field is open. Proof: real enrollments, picks and results; projections from position only. Constraints: every line shows (no "more lines" fold, Brad 2026-10-06); only current-season enrollees have a line; no query per row; others' picks for an event appear only after its lock; no podium, no gold, no season-to-par column, no paid/unpaid column (an Unpaid chip on unpaid lines only).

## Direction contract

THESIS: The sheet is the page, and everything that is not a line on it is marginalia. It refuses the fantasy-standings dashboard: a painted hero, stat tiles, a card-wrapped table, a leader band, a sidebar of cards.

OWN-WORLD: The Pay Sheet as pinned in `games/golf/DESIGN.md`: cool paper, graphite ink, pencil for projected money (tilde, single underline, the word PROJECTED), ink with a double rule for banked money (the word BANKED), one ballpoint pen blue for the member's bracket, row wash and the pick action, hairline rules between equal rows (56px for a name alone, 63px with its pencil pick line), a 2px ink rule opening the sheet, Teko for the hero figure, rank markers, labels and chips only, Newsreader tabular figures for every column of money. Marker red and course green appear only as worded chips.

STORY: A member opens the room and reads their own number and its certainty before anything else, finds their row at its true rank with the pen wash, sees who the room is on this week under each name, and, when the next field is open, spends a golfer from the margin note.

FIRST VIEWPORT: At 375 wide, under the sub-nav: one context line (the Live chip while on the course, event, round, "PROJECTED as of 4:00 PM CT", or the next lock as a literal time). Then Your line: the pen bracket in the margin, the label with its state word, the season total in Teko at clamp(52px, 17.5vw, 72px) as the largest thing on screen, and one pencil line (place of n, this week's golfer, position, the week's figure). Then the H1 "The Sheet" directly over the first rows: rank in Teko at the left, name with the pencil pick line under it, money flush to the right edge. The pick action is not in this viewport on a phone; it leads the margin stack after the last line. From 1100px the 720px sheet column sits left and a 300px margin column (next pick, Prize Pool, the marks, House Rules) sits beside it, starting level with Your line and holding its place while the sheet scrolls.

FORM: Sheet with a margin column, position 3 of the seven structures considered (straight single-column sheet; the lock leads when a pick is open; sheet with a margin column; ledger masthead with the line carried forward; the pot as the sheet's sum line; a this-week strip between the line and the sheet; a sticky condensed line). Seed key 0e4fd321; dealt 3, 6, 2 with 3 leading; Brad locked 3. The six catalog challengers were declined (all are other worlds' boards or signage; the world is pinned); kept from the split-flap board: columns never move, a state change restyles a row inside the fixed grid.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: the ruling-off. A banked hero figure draws its double rule once on load, left to right; a projected figure never gets one; instant under reduced motion. Motion grammar: nothing else moves except the fold carets.

Decisions carried from planning: the hero obeys the Pencil-and-Ink Rule (pencil, tilde and PROJECTED while a projection is in it), which departs from the preview's ink hero. A line is PROJECTED only while its golfer has a read and is still in the money; a cut, WD or DQ golfer adds a certain $0 and the line stays BANKED. A played-out event whose results are not final is still pencilled on the sheet.

Unresolved: none.
