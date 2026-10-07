---
version: 1
slug: "games-golf-templates-golf-lounge-panel-pre-html"
primary_target: "games/golf/templates/golf/lounge/_panel_pre.html"
related_targets: ["games/golf/templates/golf/lounge/_panel_live.html","games/golf/templates/golf/lounge/_panel_post.html","games/golf/templates/golf/lounge/_conv_card.html"]
---

# The Pay Sheet on the club's door (the lounge headliner panels)

Scope: The Pay Sheet's presence on the lounge (`/`), a local extension of the established multi-featured shell (root `DESIGN.md` §1.6 and §5 "The headliner panel system", ADR-049/051/052): the three state panels and the conversion card, plus the shell's third-headliner grid. No roll: a panel inside an established surface inherits it. Audience: the cold visitor on the bill (what is this game, when does it lock, take a seat) and the member who lands on the club door between games (where do I stand, is a pick owed, when does it lock). Job: orient and summarize, never operate: the money with its word, the place, the next lock, one ask; the room owns the pick, the sheet, the board. Proof: the room's own builders over rows loaded once (`services/sheet.py`), the schedule's locks, the stored season totals. Constraints: lounge classes and `--lounge-*`/`--hl-*` tokens only (the accent firewall), no `.golf-*` class, room hex or `--golf-*` var; every action a solid `.hl-cta`; the decree seal band on the pre panel, numbered No 004; bone text, `--hl-accent-bright` only at large sizes; the money is a figure with its word (projected / banked), never the room's pencil or ink; wired behind the flip (nothing renders until Phase L sets status open + featured); the seat stays open all season while the game is open (no `join_open`; Brad 2026-10-06).

## Direction contract

THESIS: The Pay Sheet takes the third corner of the bill as an equal, in the club's own purple, washed in its pen. It refuses the two layouts that would bill it as the undercard: a full-width third row under the pair, and a line in the second-bill strip.

OWN-WORLD: The Undercard as pinned in root `DESIGN.md`: the purple ground, gold as shared chrome (the seams, the seal band, the ◇ glyph), each panel washed in its game's pigment. The Pay Sheet's pigment is the pen: `--lounge-golf-ground #1A2A8F` for the wash, `--lounge-golf-accent #2439C8` for the CTA fill, `--lounge-golf-accent-bright #8C9BFF` for large text on purple. Teko for the eyebrow, the labels and the standings; Newsreader for the sentences. The money is a Teko figure in the standings and a sentence figure elsewhere, with its word.

STORY: A visitor reads three cards across one bill, the third the Pay Sheet's: the format, three tape lines, the first lock, "Join the Pay Sheet". A member reads the three panels and in the Pay Sheet's: before the season, the opening event and its lock under the decree; in season, their money and place, this week's golfer, the next lock, and "Spend a Golfer" when a pick is owed on an open field, else "Enter the Room"; after the last event banks, the champion and the top of the final sheet, "The Record Room".

FIRST VIEWPORT: At 1440 with three headliners the bill is three equal columns under the greet, two gold hairlines in the gaps and no seal; the Pay Sheet's panel is the third, its head "⛳ The Pay Sheet ›" with the court line at right, the decree band (By Decree of the Commish No 004 · The Pay Sheet ’27), "◇ Opening Round", the opening line, the sub, the pen-blue CTA. At 375 the three panels stack in the bill's order with no seams and no seal; the logged-out bill stacks the three cards the same way. With two headliners nothing changes: `.hl-duo--paired` is byte-identical.

FORM: A local extension of the established shell; no structure roll (concept-seed is never run for a local extension). The trio grid is the one new shell primitive: `.hl-duo--trio` from 1100px, stacked below. Presented and locked through the plan Brad approved on 2026-10-06 ("build it now, behind the flip"; one PR; the seat open all season).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

Signature interaction: none beyond the shell's own; the panel's one ask changes with the week (Spend a Golfer while a pick is owed on an open field; Enter the Room otherwise).

Decisions carried from planning (2026-10-06): the state resolves from the schedule and its locks (no schedule is pre, every event banked is post, a lock passed is live) and works on empty tables; the live card reads the sheet's builder so the lounge says the same money the room does; the lounge standings on the post panel are the top three in competition rank with the money as the figure (on a phone the money takes the line under the name); the Commish note's champion slot reads the `champion_team` shim; `lounge_cadence` carries no date ("The field posts Tuesday. Picks lock at the first tee.").

Unresolved: none.
