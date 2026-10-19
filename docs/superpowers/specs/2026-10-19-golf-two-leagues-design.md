# Two leagues for The Pay Sheet (Golf One & Done): design

Brainstormed with Brad 2026-10-19 (superpowers:brainstorming), builder-checked, then engineering-reviewed the same day
(plan-eng-review; decisions D1-D5 recorded in the plan at `docs/superpowers/plans/2026-10-19-golf-two-leagues.md`).
Approved 2026-10-19. The full session record, including the review ledger, is in Brad's plans directory
(`~/.claude/plans/a-large-golf-pick-rosy-ocean.md`).


### Intent

The Pay Sheet launches for 2027 (Phase L, ~Jan 2027) with two groups instead of one. The legacy
PythonAnywhere crowd (whose 2026 season is already imported) is one league. A second group that
played One & Done on Splash Sports asked to move to the Club. Each group is a closed set of friends
with its own competition: its own roster, weekly sheet and board, used-golfer history, pot, and
champion. Both play the Pay Sheet's rules exactly as written today. Brad is the one member in both
and the commissioner of the first; the second has its own commissioner.

The outcome: one golf game on the Club, with two leagues inside it, where a member of one league
never sees the other league leak into their standings, picks, mail or record, and Brad can play
both without spending the wrong golfer on the wrong sheet.

### The two leagues (Brad's rulings)

| | League one | League two |
|---|---|---|
| Name | **Handicap Pay Sheet** | **Pollyanna Pay Sheet** |
| Who | the legacy PythonAnywhere crowd | the Splash Sports crowd |
| Slug (my call) | `handicap` | `pollyanna` |
| Entry fee | TBD, $25 placeholder | TBD, $25 placeholder |
| Major-cut penalty | $15 | $15 |
| Money collected by | Brad | Brad |
| Commissioner | Brad (platform admin) | a league-two member, league-scoped admin |
| History | keeps 2026 and the legacy archive | starts blank in 2027 |
| Rules | the Pay Sheet's, unchanged | the Pay Sheet's, unchanged |

Members of each group are a mix of existing Club accounts and new ones.

### Goals

- Two independent competitions on one schedule, one sync, one API budget (the free-tier cadence
  is untouched: no extra SlashGolf calls because there are two leagues).
- Every league-scoped surface (standings, board, pick page, scorecard, Record Room, Back Office,
  letters, the record) shows exactly one league's data.
- Entry fee and penalty are per-league settings (the fee will differ; the penalty is the same
  today but lives beside it).
- A league-two commissioner can confirm payments and override picks in their league only.
- Brad picks twice a week on two separate pages and can't mix them up.
- Joining puts a member in the league they meant.

### Non-goals

- Different rules per league. Both leagues play one rule set.
- Folding Brad's two golf letters into one. Two letters, each stamped with its league ("Twice is
  fine", Brad).
- Importing any Splash history. Pollyanna's record starts with 2027.
- A combined "both leagues" pick page. Refused in favour of two stamped pages (my call, below).
- Two lounge seats or two navbar entries. One golf presence (recommendation accepted below).
- Member self-service for leaving or moving leagues (consistent with the platform: no
  user-initiated unenroll).
- Per-league payment rails. Every Settle-the-Tab line points at Brad (the card itself is in scope, PR B, D4).

### Anti-goals (what would make this a failure even if it works)

- A golfer Brad spent in Handicap silently blocked, or silently dropped, in Pollyanna (today's
  `ON CONFLICT DO NOTHING` on the usage key would do exactly that).
- A league-two member seeing Handicap names on their board, or a Handicap pick counted in the
  Pollyanna penalty pot.
- The league-two commissioner able to touch a Handicap payment or pick.
- A member joining the wrong league with no admin way to fix it before the first lock.
- The golf timers doing more API calls, or sending a reminder that names the wrong league.
- Two golf "games" on the record of champions or in the lounge bill.

### Constraints

- Platform rules in `CLAUDE.md` all apply: season scoping (ADR-069), the registry seam (one
  `GameRegistryEntry` per game, `short_name='Golf'` string-locked), the record (ADR-068,
  `flask records close`), Club Letters (ADR-058), the lounge accent firewall, no `lazy='dynamic'`,
  Alembic only, tests on SQLite and Postgres.
- Golf timers stay disabled until Phase L; this work ships before Phase L. **Production's golf
  tables are empty** (the 2026 legacy import has not run on prod; Brad 2026-10-19). The migration's
  backfill therefore only ever touches local data; the prod import runs after this ships, with
  `--league handicap`.
- The free SlashGolf tier: nothing in this change may add an API call.
- UI surfaces go through the `impeccable` skill with `games/golf/DESIGN.md` beside the root
  `DESIGN.md`; the room's paper/pen/ink register is unchanged, the league is a stamp on it.

### Decisions Brad made

1. Two separate friend groups, one pool each; Brad is the only member of both.
2. Both leagues play the Pay Sheet's rules as they stand.
3. Separate pots, different (TBD) entry fees, the same $15 penalty, all collected by Brad.
4. League two gets its own commissioner with league-scoped admin.
5. One join page listing both leagues; the member chooses; a mis-join is fixed by an admin.
6. Pollyanna starts blank in 2027; the 2026 season is Handicap's.
7. Two golf letters per occasion for Brad is fine.
8. The front: Brad asked what the design doctrine recommends and accepted one golf presence.
9. Prod golf is empty today; the 2026 import runs on prod after this ships.
10. The league commissioner's reach is the league pages only: The Roster, The Tab and The
    Commish's Pen for their league. Settle the Book (process results, the tournament list) and
    the API meter stay platform-admin only; a failed timer is Brad's to re-run.
11. A commissioner is appointed by a toggle on The Roster, visible to platform admin only
    (CFB's roster precedent).
12. Pollyanna joins in January at the Phase L flip; nothing opens early.

### Decisions I made (the builder's calls; Brad can overrule any)

**One golf presence, league inside.** One lounge seat, one navbar entry, one registry entry.
A league is a table in the room, not a game. Inside the room every league page carries the league
name in the sub-nav label and the page heading. Only a member of both leagues sees a league switch
in the sub-nav. The lounge panel shows the viewer's league; for a member of both it shows the
house league (Handicap) with one line about the other. Letters and the record name the league in
full ("Pollyanna Pay Sheet, The American Express: picks are open").

**Two separate pick pages, not one combined page.** Each stamped with its league. For a member of
both, each league's pick page carries one line saying what is filed on the other sheet this week
("On the Handicap sheet you have Scheffler, backup Morikawa" / "Nothing filed on the Pollyanna
sheet yet"), linking to it. That is the whole mix-up guard.

**The league lives in the URL.** League pages are `/golf/<league>/...` (standings, tournament,
member scorecard, stats, pick, admin). Shared pages stay where they are (`/golf/schedule`,
`/golf/join`). `/golf/` resolves to the viewer's league (member of one: theirs; member of both:
the last one visited, else Handicap; non-member or anonymous: Handicap, the house league).
Public pages (standings, boards, scorecards, stats) stay public for both leagues. Links in letters
are unambiguous and nothing depends on session state.

**Per-league settings live on a league row**, seeded by the migration: name, slug, entry fee,
penalty. Edited by a CLI command, not a UI (`flask golf league set pollyanna --entry-fee 30`), the
same hand-run convention as the rest of the platform's season switches. The `ENTRY_FEE` config
value becomes the seed default only.

**Membership of both leagues is allowed for anyone.** Nothing enforces "only Brad"; the join page
simply shows the league you are already in as joined and leaves the other joinable. No reason to
build a rule for one person.

**The Back Office never adds a member.** The platform convention stands: enrollment rows come from
`/golf/join` or `/admin/enrollments`, never an admin path. The join page covers everyone (both
groups, and Brad joining his second league). `/admin/enrollments` enrolls golf into the house
league (Handicap) and says so on the page. The Roster page gains one fix for a mis-join: "move
to the other league", platform admin only, allowed only while the member has no pick in the
season; past that Brad hand-fixes in the shell. A league commissioner can neither add nor move.

**Announcements get three golf audiences.** `/admin/announce` offers "Golf · Handicap",
"Golf · Pollyanna" and "Golf · all" (schedule news); the Tribune files under golf as today.

**A golf Settle the Tab card ships in PR B** (Brad, eng review D4, 2026-10-19; overrides my earlier
non-goal). Golf gets `services/payment.py::payment_nudge_for(user, league)` gated like ADR-056
(enrolled in that league ∧ unpaid ∧ not admin; blank rails hide it), the card on the league's sheet,
and the fee line in the picks-open letter, each naming the league's own fee. Every nudge points at
Brad's rails (ruling 3).

**Email flags stay per tournament.** The picks-open, recap and reminder passes loop over both
leagues inside one firing and latch the tournament's existing flags once. Brad receives two letters
because he is on two rosters; every other member gets one.

**The record gets a division.** The club's permanent record gains a league dimension so `golf 2027`
closes as two boards (two champions, two trophies in the reigning-champion derivation). Existing
golf rows are backfilled to Handicap. Survivor and the Docket keep an empty division.

**Commissioner scope is the enrollment.** `is_admin` on the league enrollment is the league
commissioner; it already exists and becomes league-scoped by construction. Platform admin keeps
every league.

### What's left to the builder

- Exact copy on the join page's "who this league is for" lines (Brad supplies; placeholders ship).
- The sub-nav switch's visual form and the league stamp on the page heading (impeccable, at build).
- Whether `/golf/` for a member of both remembers the last league in a cookie or defaults to the
  house league every time (either is acceptable).
- Test fixture shape for the two-league seed.

---

