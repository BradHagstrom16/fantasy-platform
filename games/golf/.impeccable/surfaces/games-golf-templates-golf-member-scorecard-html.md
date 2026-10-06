---
version: 1
slug: "games-golf-templates-golf-member-scorecard-html"
primary_target: "games/golf/templates/golf/member_scorecard.html"
related_targets: []
---

# The scorecard (`/golf/member/<id>`)

Scope: one member's season on the Pay Sheet, Operate mode (inspect, compare, act on the open week). Audience: a member on a phone checking their own season after a week banks, or a rival's before spending a golfer; anyone with the link, signed in or not. Job: say where this member stands and how they got there: the total and its state, the rank, the weeks from the one in play back to the Sony Open, who they have spent, and what the Commish set by hand. One action, and only on your own card: the open week's pick ("Spend a golfer" or "Change"). Proof: the member's real picks read against the results, the sheet's own rank and total, the usage table, the override flags. Constraints: public like the sheet and secret by the lock (until a week is revealed, nobody but the member is handed its pick); every read season-scoped; no query per week or per member; the total is the page's one Teko figure and every other dollar is Newsreader tabular; pencil and ink stay the money's; the pen bracket marks the viewer's own line only; no script.

## Direction contract

THESIS: The card opens on the week in play and reads back to the first tee: the newest week is the first row, and the season is underneath it. It refuses the stats-page scorecard everyone ships: a grid of seven equal tiles over a five-column table with the season's first week on top and this week thirty rows down.

OWN-WORLD: The Pay Sheet as pinned in `games/golf/DESIGN.md`: cool paper, graphite ink, pencil for everything secondary, one pen blue for what is the viewer's own and what they can do now. The sheet's own rows (`.golf-sheet`) with a pencil week number where the rank would be, the event in ink over its pencil pick line, the money flush right in Newsreader tabular: ink over a double rule when banked, pencil with a tilde while live. Chips are words in a 1px outline: Major ×1.5, Team event, Commish in ink; Used in pen; Cut, WD, DQ and the penalty in marker red; Live in course green. Teko only for the total, the labels and the chips.

STORY: A member lands from "My Scorecard" (or from a name on the sheet), reads the total and its rank, sees this week's row on top (their pick and "Change", or the live figure in pencil), and scrolls back through the season: what each week paid and who it cost them. Under the weeks they find their best pick and what the pot is owed, open "Used golfers", and read the Commissioner's ledger. They switch to a rival and read the same card, the rival's open week shut until the lock.

FIRST VIEWPORT: At 375 wide, under the sub-nav: the H1 "Your Scorecard" (or "Cox's Scorecard"); the member switcher on its own row (a real select and "View"); one context line (the season, "12 of 32 weeks banked", the other season's scorecard when there is one); the label "Total won" with its state word over the total in Teko at clamp(52px, 17.5vw, 72px), ink over the double rule when banked and pencil with a tilde while a week is live, the pen bracket beside it on your own card only; "4th of 19" under it; then three tiles under an ink rule (In the money "29 of 31", Golfers used, Commish overrides). The head of the weeks ("The weeks, newest first") and the first row sit at the fold. One 720px column at every width; from 576px the switcher sits beside the H1.

FORM: Latest week first, position 5 of the seven structures considered (the straight ledger page in season order; the card with a margin column; the statement with a running total; ruled by the month with subtotals; latest week first; the weeks first with the figures at the foot; this week pinned over the season). Seed key 0922e87f; dealt 5, 4, 3 with 5 leading; Brad locked 5. The six catalog challengers were declined (the world is pinned); kept from the rail concourse split-flap board: a state restyles its row and never breaks the grid (a cut, a missed week, a hidden pick and a live figure all sit in the same three columns).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: the season read backwards. The row on top is always the week that can still change (your open pick with its lock, or the live week in pencil); everything under it is ink. Motion grammar: the total's double rule draws once on load when it is banked (the room's ruling-off, still under reduced motion) and the fold's caret turns; nothing else moves.

Decisions carried from planning: the page is public and carries no decorator, like the sheet and the board; `/golf/my-picks` redirects to it. Rank and total are the sheet's own row (`build_sheet`), so the card never disagrees with the sheet, pencil included. A week is revealed at its lock or once banked; a pick on a week not revealed reaches only its member. Weeks after the next pick are counted in one line ("17 weeks still to play"), not listed. The golfer who counted wears the Used chip and the other is named as the backup, never struck (a strike is a spent golfer). "Used golfers" shows on every member's card (Brad, 2026-10-06). The season selector is `?season=`, drawn only for a member with a line in more than one season. Best pick and the majors pot close the weeks as a pair of tiles; no tile but the total is set in Teko.

Review rulings (2026-10-06, finish review, both verdicts ship): your own open week takes the pen wash with no bracket and the pick action is the room's filled button (§7.24), once on the page, with the lock on its own line in ink (the open week's cell spans the money column so the lock fits at 375); the pot tile says "$15 still owed to the pot" on its own line and the pair's notes take the line under their figure; zero states are sentences ("no weeks on the schedule yet", "No weeks banked yet"); the Commissioner's ledger carries the member's avatar; the season link is a 44px tap; the Commish's note prints in words on the week's pick line.

Unresolved: none.
