---
version: 1
slug: "core-records-templates-records-index-html"
primary_target: "core/records/templates/records/index.html"
related_targets: []
---

## Scope

`/records`, The Record (`core/records/`): the club's permanent record, public, cross-game. Mode: Read. The reader's question is "who won, and where did everyone finish?" for every season the club has closed. Source: `models.records` (`champions()`, `seasons_on_record()`, `finishes_for()`); nothing computed on the page. Constraints: the platform's light world with no new token (the Tribune's register, `.records-*` classes only); no eyebrow above a heading; no cards for rows; competition rank as stored; the recorded name always, the current name only when it differs; one link per board to the room's own archive.

## Direction contract

THESIS: One roll of champions, then the boards beneath it. The page refuses the category default of a trophy-case grid of same-size cards; it reads like the club's own ledger, a roll call first, the full boards folded under it.

OWN-WORLD: Pressroom Bone page, Teko 700 masthead over one Newsreader lede and a 2px Commish Gold rule, a 40rem column. The roll: year in gold-dark Teko, the game in Teko, the champion's name at 1.7rem Council Purple as the door into the board, the finish line in Newsreader secondary; hairlines between, never cards. The boards: one `<details>` per season with a Teko 600 summary on a gold rule; rows are place in tabular Teko gold-dark, avatar and name in Newsreader ink, the finish line right in Newsreader secondary. Recognizable empty: gold rule, purple names, hairlines.

STORY: A visitor sees at once who has won what in this club, opens a season, finds their own line and the members they know, and can step into the room's archive for the season as the room keeps it.

FIRST VIEWPORT: Masthead "The Record" and its lede at the top of the column; the champions roll directly under the gold rule, newest first, each champion's name a link to its board; the first board opens below the roll's end. No primary action: the champion names are the doors.

FORM: The roll-and-boards ledger, first of the structures considered (the trophy-case grid, a per-game tab strip and a single long table were set aside). Shaped directly: a precisely specified surface inside the established world, no concept roll, so no seed key.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
