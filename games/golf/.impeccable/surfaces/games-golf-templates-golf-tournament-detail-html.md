---
version: 1
slug: "games-golf-templates-golf-tournament-detail-html"
primary_target: "games/golf/templates/golf/tournament_detail.html"
related_targets: []
---

# The Board (`/golf/tournament/<id>`)

Scope: one tournament's page in the Pay Sheet, Operate mode (inspect, compare, verify). Audience: a member checking what their golfer is worth this week against the room, or flipping back through past weeks; public like the sheet. Job: my pick and its figure with its certainty, then every member's pick ranked by what it is worth, with the deductions named. One action before the lock: make or change my pick. Proof: real picks and results; an unfinalized board is a projection from position and says so. Constraints: every line shows; before the lock no other member's golfer is rendered (a count of lines in only); an unfinalized board never contains the word "Earnings"; the penalty chip keeps the `badge-penalty` class; no finalized date is shown (Brad 2026-10-06); no query per row.

## Direction contract

THESIS: Every board is one leaf of the Season Book: the week before and the week after are one tap away, and the leaf itself is the sheet's grammar applied to a single week. It refuses the tournament-detail dashboard: a painted hero, four stat tiles, a card-wrapped picks table sorted by name.

OWN-WORLD: The Pay Sheet as pinned in `games/golf/DESIGN.md`, shared with The Sheet: paper, ink, pencil, the one pen blue, hairline rules, equal 63px rows (a name over its pencil pick line), Teko only for the hero figure, ranks, labels and chips, Newsreader tabular money. A 2px ink rule opens the board. Marker red only on Cut, WD, DQ and Penalty $15; course green only on the Live chip; Major ×1.5 and Team event are ink chips, never a tint.

STORY: A member lands from Results or the sheet, sees which week this is and steps to its neighbours, reads their own pick's figure and whether it is projected or banked, then reads the room in rank order and sees who was cut and what went to the pot.

FIRST VIEWPORT: At 375 wide, under the sub-nav: the pager line (the previous week's event at the left, "Week 13 of 32" between, the next week's event at the right). The H1 "The Board: Masters Tournament". One context line: the Live chip while on the course, the Major ×1.5 or Team event chip, the dates, and the state in a word (Banked, or the round and "PROJECTED as of 4:00 PM CT"). Then Your pick: the pen bracket, the label with its state word, the week's figure in Teko at clamp(52px, 17.5vw, 72px), and one pencil line (golfer, position, backup state, the Used chip once he is spent). A viewer with no pick gets the purse as the figure. Then the 2px ink rule and the first rows of the board. Before the lock the board is replaced by the count of lines in and, for an enrolled member with an open field, the pick action directly under Your pick. One 720px column at every width.

FORM: The board as a page of the Season Book (a week pager above the title), position 5 of the seven structures considered (straight board; a facts strip between the pick and the board; board with a margin column; a by-golfer fold under the ranked board; the week pager; golfer-led rows; a pinned pick bar). Seed key 22a06549; dealt 7, 5, 3 with 7 leading; Brad locked 5. The catalog challengers were declined (the world is pinned); nothing borrowed.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: the ruling-off, shared with The Sheet. On a banked board the hero figure draws its double rule once on load; a projected board never shows one; instant under reduced motion. Motion grammar: nothing else moves except the fold caret.

Decisions carried from planning: a banked board says "Banked" with the event's dates and no finalized date. The money column's state is the tournament's (one word in the board's head), since a week is either all projected or all banked. After the board: "Penalties assessed: n · $x to the pot" at a major, the read times with the last read while unfinalized, and the "Didn't pick (N)" fold.

Unresolved: none.
