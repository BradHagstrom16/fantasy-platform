---
version: 1
slug: "games-cfb-templates-cfb-player-html"
primary_target: "games/cfb/templates/cfb/player.html"
related_targets: ["games/cfb/templates/cfb/index.html","games/cfb/templates/cfb/weekly_results.html"]
---

# The player card (`/cfb/player/<enrollment_id>`)

Scope: one route in the CFB Survivor room, Operate mode (inspect, compare, verify). Audience: any club member, on a phone, mid-weekend, tapping a rival's name on the standings or the lounge. Job: see how that member's season has run (alive / one life / out), where each life went, whether a pick was the Commish's autopick, and what teams they still hold. No action on the page; it is a record. Proof: real enrollment, picks, week outcomes; nothing invented. Constraints: public like standings; a pick shows only once its week's deadline has passed; the owner's open pick never appears here.

## Direction contract

THESIS: One member's season read as a card: the standing, the calls in order with what each cost, then what is left to spend. It refuses the player-profile dashboard (avatar tile, stat tiles, rank sparkline) and refuses being a second My Picks (no accordion, no coverage planner, no payment card, no pick controls).

OWN-WORLD: The midnight room as shipped: `.page-hero.cfb-hero`, the `.cfb-season-lead` raised surface with its outcome-colored top rule, the `.cfb-week-summary` record line, a `.table-cfb.cfb-field-table` ledger, `.cfb-used-grid` and `.cfb-team-pool` chips in the landing's Pool groups. Bone text; crimson only for the You tag and the focus ring; survivor-state color only on chips, pips and the top rule.

STORY: A member taps a rival's name, sees alive / one life / out with the pips, scrolls the calls to see where a life went and whether a pick was an autopick, then checks what teams that rival still holds. On their own name they are offered their full card.

FIRST VIEWPORT: At 375 wide: masthead H1 = avatar + display name (no eyebrow above it since ADR-066), the standing sentence, and the hero-field line (ordinal rank of the active field, calls, spread; "Out · Week N" once eliminated). Then the standing lead (headline, third-person derivation, pips) and the record line; the card table's first rows reach the bottom of the viewport. No primary action. The one link in the lead is "Review Your Card", on the owner's page only.

FORM: Ledger-first card in the room's verdict grammar; position 1 of the structures considered (ledger-first; standing-first hero with ledger below; two-column ledger + board; a timeline of verdict blocks; board-first inventory). No seed key: the brief pinned the structure and the room doctrine names the surface (§7.4), so no concept roll was run.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Unresolved: none. Signature interaction: the name-as-door (`.cfb-name-link` underline on hover/focus, crimson focus ring). Motion: the room's `animate-in` entrance on the lead and cards only.
