# New Game Kickoff: NFL + CFB Pick 'Em — Office Hours Session

## Context

Brad wants to add a new game to the platform: a combined NFL + CFB weekly picks pool, running alongside the existing CFB Survivor Pool for the 2026–27 season. This is early-stage: the concept below is Brad's raw design, not a reviewed plan. Before any planning or implementation work starts, it needs a scoping pass to surface gaps, conflicts, and sequencing questions.

**run `/office-hours` against the concept brief below and surface what needs resolving.** Do not invoke `/brainstorming` — Brad is deliberately using office-hours instead for this feature. Two office-hours modes exist; pick whichever fits "scoping a large net-new feature from a first draft," or ask Brad which he wants if it's not obvious from the skill itself.

You have full read/write access to the repo. Use it — read `games/cfb/` directly rather than trusting any summary below where the two could conflict; the summary is Brad's intent, the code is ground truth on what CFB Survivor actually does today.

## Session Flow

1. **REQUIRED — do not proceed past this step until complete:** Invoke `/office-hours` with the concept brief and open questions below as input.
2. Let office-hours do its work against the actual codebase (read `games/cfb/` as the nearest structural analog — it's the only other pick-style game with spreads, deadlines, and autopick already built).
3. Present the session's output to Brad. Recommend what he should do next and/or what should be done next.

---

## Concept Brief (Brad's draft — input for office-hours)

### Overview
A weekly pick 'em combining FBS (CFB) and NFL games in one pool. Distinct from CFB Survivor — different mechanic (points-accumulation picks vs. outright-survival), different scoring, can share a codebase pattern but is not a variant of Survivor.

### Season & Enrollment
| Item | Value |
|---|---|
| Season start | CFB Week 1 (8/31/26 – 9/7/26) |
| Season end | NFL Week 18 (1/4/27 – 1/11/27) |
| Entries | Max 1 per entrant |
| Enrollment | Independent of CFB Survivor — a user may join both, either, or neither, voluntarily |

### Weekly Pick Structure
- 8 picks required per week, exactly — no min/max split between CFB vs. NFL or spread vs. O/U. Any mix.
- Each pick is a spread side or an Over/Under side, on any FBS or NFL game.
- 1 backup pick per week, used only if one of the 8 selected games is cancelled.
- Cannot pick both sides of the same spread, or both Over and Under, on the same game.
- No picks accepted for any week except the current upcoming one — no advance picking of future weeks.

### Line Import & Locking
- Lines (spreads + O/U) import once per week at a fixed point for both Survivor and Pick 'Em — Brad's asking for a recommendation on Tuesday vs. Wednesday, specifically because Wednesday-night CFB games complicate a clean cutoff.
- Once imported, a line is locked for the season — never re-synced even if the market line moves before kickoff.

### Scoring
- Win = 1 point, loss = 0, push = 0.5.
- **Drop worst week:** each player's single lowest-scoring week is automatically excluded from their season total. Once week 1 is completed do not drop it, so must have >1 weeks completed for this to kick in.

### Deadlines
- Pick deadline: Saturday 11:00 AM CDT, every week — same deadline as CFB Survivor's.

### Best Pick Bonus
- Each player designates 1 "best pick" per week (required, not optional).
- If the best pick hits, it earns a 2-point bonus.

### Autopick
- Triggers when a player misses the deadline.
- Heuristic: auto-select the 4 highest-total Over/Under lines and the 4 largest point-spread favorites for the week — Brad's framing: "you need points and blowouts."

### Leaderboard & Tiebreaker
Ranking order, both weekly and season standings:
1. Points
2. Wins
3. Weekly tiebreaker — cumulative point-differential accuracy for the season

**Tiebreaker mechanic:** each week, one designated game (preferably NFL Sunday Night Football) asks every player to predict the final combined score, to 0.1 precision. The imported O/U line is shown as a reference. Score it as absolute difference from the actual total; that difference accumulates across the season as the season-long tiebreaker value (lower is better).

- Week 1 tiebreaker game: Wisconsin @ Notre Dame (CFB) — chosen because it's the marquee CFB Week 1 game.
- From there, Brad's intent is Sunday Night Football for the rest of the season.

---

## Open Questions for Office Hours to Resolve

These are gaps or conflicts in the draft above that a scoping session should surface and get Brad's ruling on — don't silently resolve them by assumption. Recommend your objective suggestions where appropriate.

1. **Deadline vs. kickoff conflict.** This game pools picks across a game reads full week's slate — Tuesday/Wednesday CFB games kick off *before* that Saturday deadline. If lines lock at Tuesday/Wednesday import, can a player still submit a pick on a game that's already been played by the time they pick? Answer: NO. Once a game kicks off, the game is locked. Those that entered a pick for the game have that picked locked in and those that do not have a pick entered for it cannot enter a pick for it. This needs a per-game lock at kickoff, which Survivor should have in place already, (not just the season-wide Saturday cutoff).
2. **Line import day.** Recommend evaluating two shapes against the existing CFB Survivor precedent (`flask cfb sync --mode spreads` — locks at first Tuesday fetch, later runs fill gaps only, per DQ-6 in CLAUDE.md): (a) mirror that pattern for this game too, accepting Wednesday-night games get whatever line was available Tuesday morning, or (b) shift the lock to Wednesday afternoon so Wednesday games' lines are live at import time, at the cost of a later lock for everything else. Surface both and let Brad rule.
3. **Best pick bonus stacking.** Suggest whether a correct best pick earns its normal 1 point *plus* the 2-point bonus (3 total), or the bonus replaces the normal point. Be objective.
4. **Autopick scope.** Does autopick also assign the required best-pick designation and the backup pick, or only the 8 primary picks? And is the "4 highest O/U + 4 largest favorites" pool drawn from CFB and NFL combined, or per-sport? One thing Brad wants is that autopicks come from games starting on or after Saturday 11 AM CDT only.
5. **Backup pick mechanics.** With exactly one backup per week, what happens if two or more of a player's 8 picked games get cancelled in the same week — does the week score on 7 picks, or is there no coverage beyond the first cancellation? Also confirm the backup is subject to the same one-side-per-game constraint as the primary 8.
6. **Game name/slug.** "Golf Pick 'Em" already exists as a game name on the platform — this new game needs a distinct name/slug before it can follow the Blueprint Pattern (`games/<slug>/`) to avoid confusion in the UI and codebase. Brad is open to creative names, recommend some.

---

## Repo Precedents to Consult

Don't restate these conventions in office-hours output — reference them. Full detail lives in `CLAUDE.md`.

- **Blueprint Pattern** (`CLAUDE.md` § Blueprint Pattern) — the required shape for any new game blueprint. You are Claude Fable, if the blueprint is wrong or you are confident in a better way to construct this new game, Brad has approved that.
- **`games/cfb/`** — nearest structural analog for this game: spread lock/fill behavior (DQ-6), `flask cfb sync --mode autopick`, the `CFB_FAKE_NOW` time seam, and the naive-datetime split-contract for `deadline`/`start_date`/`game_time` vs. `created_at`/`spread_locked_at`. Brad is open to improvements.
- **`games/registry.py`** — SSoT for game registration; any new game needs an entry here per the Blueprint Pattern.
- **Engineering backlog** (`docs/engineering-backlog-2026-07-21.md`) — check for anything already flagged that overlaps this game (rate-limiting, timer hazards) before assuming a clean slate.