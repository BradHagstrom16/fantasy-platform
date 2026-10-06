---
version: 1
slug: "games-golf-templates-golf-make-pick-html"
primary_target: "games/golf/templates/golf/make_pick.html"
related_targets: []
---

# Spend a Golfer (`/golf/pick/<id>`)

Scope: the Pay Sheet's pick page, Operate mode (decide, commit, change). Audience: an enrolled member on a phone between Tuesday, when the field publishes, and the Thursday lock; thirty-two times a season. Job: answer four questions before the list (what tournament and how much is the purse; when picking locks; who I have used; who to consider spending now), then name a primary and a backup. One action: lock it in. Proof: the real field, the member's own usage, season prize money from banked tournaments only, the room's burn share from the usage table. Constraints: used golfers are struck, never hidden; the page turns over at the lock, never at a status; `#primary_player_id` / `#backup_player_id` and their field names stay real selects, so the form posts without JavaScript; no library and no CDN; no query per row; the burn hatch is absent until the season's first burn and the money line absent until the first banked tournament.

## Direction contract

THESIS: The page asks one question at a time: your primary, then your backup, then both on the slots to lock in. It refuses the pick form everyone ships: two dropdowns in a card beside a sidebar of rules, with the spent golfers quietly removed from the options.

OWN-WORLD: The Pay Sheet as pinned in `games/golf/DESIGN.md`, the yardage book leaf of it: cool paper, graphite ink, pencil for everything secondary, the one pen blue for what is mine and what I can do now (the open slot's frame, the row action, the chosen row's wash and chip, the pick action). Two ruled 56px slots; the field as equal rows on hairlines under a 2px ink rule; a spent golfer struck in pencil with the week he went; the burn hatch, the room's one texture, 45 degree pencil hatching in a 1px pencil frame. Teko only for the purse, labels and chips; Newsreader tabular figures for every dollar.

STORY: A member lands from "Spend a golfer", reads the purse and the lock, sees how many golfers they have left in this field, taps a golfer for the open Primary slot, is turned back to the slots where the Backup slot is now the open one with its one-line rule, taps a second golfer, and locks it in. Coming back to change it, they find both slots inked and change either one.

FIRST VIEWPORT: At 375 wide, under the sub-nav: the H1 "Spend a Golfer: RBC Heritage"; one context line (Major ×1.5 or Team event chip, the dates); the label "Purse" over the purse in Teko at clamp(52px, 17.5vw, 72px), plain ink, no rule and no state word; the facts (DESIGN.md §7.8, "field · available"): Picks lock on its own line, then Golfers used beside Yours to spend, which carries the field's size ("71 of 82 in the field"), three across from 576px; then the two slots, Primary open in a 2px pen frame, Backup dashed and waiting with its rule. The search and the first rows of the field sit just below the fold, headed by the open question ("The field · spend your primary"). "Lock it in" takes its place under the slots only once both are in. One 720px column at every width.

FORM: One question at a time, position 7 of the seven structures considered (the book with a margin column; the straight single column; both slots open with whole-row taps; a pinned pick bar; the field ruled into yours-to-spend and spent; the search leads with the pick pinned; one question at a time). Seed key ff301854; dealt 7, 5, 6 with 7 leading; Brad locked 7. The six catalog challengers were declined (the world is pinned); kept from the jet-age ticket wallet: nothing disappears, it cancels, and the book always says what remains (the struck rows stay in their money-order place and the field head counts what is still yours to spend).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: the leaf turn. Choosing a golfer inks him into the open slot and returns the member to the slots, where the next question is the open one; every open row's action word turns from "Primary" to "Backup" with it. Motion grammar: the slot's pen frame moves between slots and the page scrolls back to them, instant under reduced motion; nothing else moves except the fold caret.

Decisions carried from planning: Tom Select is replaced by the native list (the admin override page keeps it until U6). The burn share's denominator is the season's enrollees. A GET before the field is published renders the facts and the empty state; a POST there writes nothing. Past the lock the page redirects to that week's Board. After "Lock it in" the member lands on The Sheet. With a saved pick and no change, the pick action stands down and a pencil line says the pick is in. "Used golfers (N)" lists every golfer the member has spent, by week.

Unresolved: none.
