---
version: 1
slug: "games-golf-templates-golf-admin-dashboard-html"
primary_target: "games/golf/templates/golf/admin/dashboard.html"
related_targets: ["games/golf/templates/golf/admin/tournaments.html","games/golf/templates/golf/admin/users.html","games/golf/templates/golf/admin/payments.html","games/golf/templates/golf/admin/override_pick.html"]
---

# The Back Office (`/golf/admin/` and its four leaves)

Scope: the commissioner's pages of The Pay Sheet, Operate mode (a task, done between other things, on a phone as often as a desk). Audience: the golf admin, platform admin or the season's enrollment admin, a few times a week in season: on a Monday to settle a played event, on a Tuesday to check the month's API reads before the timers run, whenever a member pays or a pick needs the Commish's hand. Job: five things, in the order they need doing: settle what is played and not banked (`/admin/tournaments`, "Settle the Book"), see who has paid and collect what is owed (`/admin/payments`, "The Tab"), see who is on the sheet (`/admin/users`, "The Roster"), write a member's pick for them (`/admin/override-pick`, "The Commish's Pen"), and keep the month's reads under the free tier (the meter on the dashboard). Proof: the season's tournaments and enrollees, the call log the sync writes, the penalty count the engine derives. Constraints: the room's own paper, pencil, ink and pen; no cards, no gold, no Bootstrap badges, no Tom Select, no inline styles but the positions the server computes; every JS hook in `games/golf/DESIGN.md` §7.15 preserved; the lists are this season's enrollees only; an override on a complete tournament commits nothing until the Commish confirms; the meter reports and never gates (the timer cadence is the budget).

## Direction contract

THESIS: The back office is a ledger book: one dashboard page of three ledgers in the order they need doing, and four leaves that are pages of the same book. It refuses the admin dashboard everyone ships: a grid of stat tiles over a card of quick links over a card of alerts.

OWN-WORLD: The Pay Sheet as pinned in `games/golf/DESIGN.md`: cool paper, graphite ink, pencil, one pen blue. Each ledger and each leaf opens on a 2px ink rule with its label (Teko caps, pencil) as the heading; rows part on hairlines; money is Newsreader tabular; chips are the room's (Live, Major ×1.5, Commish, Unpaid in marker red); actions are the room's text actions in pen (Process, Save, Cancel) and one pen fill per page at most (Write the override, Confirm and re-resolve). The one new mark is the meter: the burn hatch, the room's one texture, drawn as wide as the share of the month's reads already spent.

STORY: The Commish taps Admin, reads the context line (the season, how many events are banked, how many reads the month has spent), and the book line under it names the four leaves. The first ledger is what needs doing: the played events not yet banked, each with Process on its row. The tab follows (paid of enrolled, collected, the penalty pot) with the link to the line-by-line page, and the reads close the page. Each leaf keeps the same head (H1, context line, book line) so the Commish always knows which page of the book is open.

FIRST VIEWPORT: At 375 wide, under the sub-nav: the H1 "The Back Office"; one context line ("2027 season · 12 of 32 events banked · 112 of 250 reads this month"); the book line, five names on two rows between hairlines, the page in hand unlinked; then the first ledger: the ink rule, "To settle" with the count at right, one pencil sentence saying what Process does, and the played events as the field's rows with Process at the right of each. At 1440 the same single 720px column: a ledger is read top to bottom, never side by side.

FORM: The ledger book, position 7 of the seven structures considered (the desk; the back office as one page; the settle-first desk; the register of tiles over links; the season timeline; the commissioner's margin; the ledger book). Seed key 792a1079; dealt 7, 6, 1 with 7 leading; Brad locked 7. The catalog challengers were declined (the world is pinned). Presented through the structured question tool rather than the decision page (this harness cannot hold the page's blocking wait).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: the meter. The hatch is as wide as the month's reads; the line under it says what is left and when the last read was, in words; past four fifths the sentence leads in ink, over the budget it says by how many. No colour alone says it.

Decisions carried from planning (2026-10-06): one PR for U6 and U7; the gate is ported from the standalone (a complete-tournament override renders its consequence and commits nothing until `confirm=1`); the meter counts every attempt that reached RapidAPI (`status != 0`) in the league's month, over the live log and its rotations, approximate by design (RapidAPI resets on the subscription day); `clear_resolution` is season-scoped; the roster, the override's member select and the dashboard read this season's enrollees; `.col-divider` and the Tom Select rules retire from the CSS; `.table-golf` stays for the schedule page. The Paid/Unpaid chip carries `js-paid-status` for the toggle's script (the first-`.badge` selector is gone).

Unresolved: none.
