# Handoff 4B — World Cup Fantasy Pool: Scoring Engine

**Phase:** 4B (Scoring Engine + Recalc CLI + Group Advancement Logic)
**Recipient:** Claude Code
**Date:** 2026-04-04
**Prerequisite:** 4A complete — models, migration, CLI, blueprint scaffold all in place
**Branch:** `phase-4b-worldcup-scoring`

---

## Context

Phase 4A created the foundation: 4 models (`WorldCupEnrollment`, `WorldCupTeam`, `WorldCupMatch`, `WorldCupPick`), 104 pre-seeded matches, 48 teams, CLI commands, and a scoring stub that raises `NotImplementedError`. This handoff replaces that stub with the full scoring engine.

The scoring engine is the most complex business logic in the World Cup game. It must be **idempotent** — running it twice on the same data produces identical results. This is critical because Brad will be entering match results daily during the tournament and needs to be able to re-run scoring at any time to correct mistakes.

**Key design principles:**
- **Full recalc every time.** With ≤50 enrollments × 9 picks = 450 pick rows and 48 team rows, a full recalc takes milliseconds. No incremental scoring — it's harder to get right and harder to debug.
- **Match data is the source of truth.** Team scores, pick scores, and enrollment totals are all derived from completed matches + advancement data. The recalc engine rebuilds everything from scratch.
- **Half-point precision.** Multipliers of ×1.5 and ×2.5 on odd base values produce .5 scores (e.g., 3 × 1.5 = 4.5). All scores stored as `Float`, displayed to 1 decimal place.

---

## Scope

### Files to Create/Replace

```
games/worldcup/services/scoring.py      # Full scoring engine (replaces stub)
```

### Files to Modify

```
games/worldcup/cli.py                   # Update recalc command to print summary; add process-match command
```

### Files NOT Modified (read-only references)

```
games/worldcup/models.py               # Use existing models, don't modify schema
games/worldcup/constants.py             # Import scoring constants, don't modify
games/worldcup/WORLD_CUP_GAME_DESIGN.md # Scoring rules reference
```

---

## Step-by-Step Instructions

### Step 1: Read Required Files

Read these files completely before writing any code:

1. `games/worldcup/WORLD_CUP_GAME_DESIGN.md` — especially the "Scoring System", "Points Per Achievement by Tier", "Example Scoring Scenarios", "Podium Scoring Proof", and "Edge Cases & Admin Rules" sections
2. `games/worldcup/constants.py` — all scoring constants
3. `games/worldcup/models.py` — all model fields, especially `WorldCupTeam` (base_points, multiplied_points, advancement_method, best_finish, group_wins/draws/losses, is_eliminated) and `WorldCupPick` (base_points, multiplied_points)
4. `games/worldcup/cli.py` — the existing `recalc` and `status` commands

**Skill prescription:** Use `brainstorming` skill to map out the scoring pipeline before writing code. Confirm understanding of: (a) the difference between group match points and group advancement milestone points, (b) that knockout scoring is a single value per round (not match + milestone), (c) that the champion bonus (50) is for winning the final — the SF win (19) is separate.

### Step 2: Implement `games/worldcup/services/scoring.py`

Replace the stub entirely. The file should contain these functions:

#### `recalculate_all_scores() -> dict`

The master orchestrator. Performs a full idempotent recalculation:

1. **Reset all team scores** — set `base_points = 0.0`, `multiplied_points = 0.0`, `group_wins = 0`, `group_draws = 0`, `group_losses = 0` on every `WorldCupTeam`. Do NOT reset `advancement_method`, `best_finish`, or `is_eliminated` — those are set by the admin via the advancement flow, not derived from match results alone.

2. **Recalculate team scores from matches** — for each completed match, call `_apply_match_to_teams(match)`.

3. **Apply advancement milestones** — for each team with a non-null `advancement_method`, add the corresponding milestone points to `base_points`.

4. **Apply knockout results** — for each completed knockout match, add the round-specific points to the winning team's `base_points`.

5. **Apply podium bonuses** — check `best_finish` on each team: champion gets 50, runner_up gets 8, third_place (win) gets 8.

6. **Compute multiplied_points** — for each team: `multiplied_points = base_points * multiplier`.

7. **Update pick scores** — for each `WorldCupPick`: set `base_points = team.base_points` and `multiplied_points = team.multiplied_points`.

8. **Update enrollment totals** — for each `WorldCupEnrollment` that has picks: `total_score = sum(pick.multiplied_points for pick in enrollment.picks)`.

9. **Commit and return summary** — `{"teams_updated": N, "picks_updated": N, "enrollments_updated": N}`.

#### `_apply_match_to_teams(match: WorldCupMatch) -> None`

Process a single completed match's impact on team W/D/L records (group stage only):

- **Group stage match:**
  - If `match.is_draw`: both teams get +1 draw, both get `GROUP_DRAW` (1) added to base_points
  - If `match.winner_team_id == home_team_id`: home team gets +1 win and `GROUP_WIN` (3) added; away team gets +1 loss
  - If `match.winner_team_id == away_team_id`: away team gets +1 win and `GROUP_WIN` (3) added; home team gets +1 loss

- **Knockout stage match:** Do nothing here — knockout points are handled separately in step 4 of `recalculate_all_scores` by looking at `match.stage` and `match.winner_team_id`.

**Important:** This function only handles group W/D/L and group match points. It does NOT handle advancement milestones, knockout points, or podium bonuses.

#### `_apply_advancement_points(team: WorldCupTeam) -> float`

Return the advancement milestone base points for a team based on its `advancement_method`:

```python
if team.advancement_method == 'group_winner':
    return ADVANCE_GROUP_WINNER  # 4
elif team.advancement_method == 'runner_up':
    return ADVANCE_RUNNER_UP  # 3
elif team.advancement_method == 'best_third':
    return ADVANCE_BEST_THIRD  # 1
return 0.0
```

#### `_apply_knockout_points(match: WorldCupMatch) -> float`

Return the knockout round base points for the winning team of a completed knockout match:

```python
stage = match.stage
if stage in KNOCKOUT_POINTS:
    return KNOCKOUT_POINTS[stage]  # R32=8, R16=11, QF=15, SF=19
return 0.0
```

**Note:** The `champion`, `runner_up`, and `third_place` keys in `KNOCKOUT_POINTS` are podium bonuses, NOT regular knockout round points. They are handled separately via `best_finish`.

#### `_apply_podium_bonus(team: WorldCupTeam) -> float`

Return the podium bonus base points for a team based on its `best_finish`:

```python
if team.best_finish == 'champion':
    return KNOCKOUT_POINTS['champion']  # 50
elif team.best_finish == 'runner_up':
    return KNOCKOUT_POINTS['runner_up']  # 8
elif team.best_finish == '3rd':
    return KNOCKOUT_POINTS['third_place']  # 8
return 0.0
```

#### `apply_group_advancement(group_letter: str, advancements: dict) -> dict`

Called by the admin route when confirming group advancement. `advancements` is a dict mapping FIFA codes to advancement methods:

```python
# Example: {'ESP': 'group_winner', 'URU': 'runner_up', 'KSA': 'best_third'}
```

For each team in the dict:
1. Look up `WorldCupTeam` by `fifa_code`
2. Set `advancement_method` to the provided value
3. If method is `None` or not in the dict → team was eliminated in groups → set `is_eliminated = True`, `best_finish = 'group'`
4. For teams that advanced → `is_eliminated = False` (they're still in), `best_finish` left as-is (will be updated as they progress in knockouts)

After setting all advancement methods, call `recalculate_all_scores()` to cascade the milestone points.

Return: `{"group": group_letter, "advanced": [...], "eliminated": [...]}`.

#### `process_match_result(match_id: int, home_score: int, away_score: int, winner_fifa_code: str | None, is_draw: bool = False, extra_time: bool = False, penalties: bool = False) -> dict`

Called by the admin route when entering a match result. This is the **primary entry point** for scoring during the tournament.

1. Look up the `WorldCupMatch` by id
2. Validate: match must not already be completed (prevent double-entry). If already completed, return an error dict suggesting the admin use recalc after manually editing.
3. Set `home_score`, `away_score`, `is_draw`, `extra_time`, `penalties`, `is_completed = True`
4. If `winner_fifa_code` is provided: look up team, set `match.winner_team_id`
5. If it's a group stage match and not a draw: determine winner from scores if `winner_fifa_code` not provided
6. For knockout matches: the winning team should also have `best_finish` updated to at least the current stage (e.g., if they won an R32 match and their `best_finish` is null or 'group', update to 'R32'). **Be careful:** only update if the new stage is deeper than the current `best_finish`. Use a stage ordering: `group < R32 < R16 < QF < SF < 3rd < runner_up < champion`.
7. For the **final**: set winner's `best_finish = 'champion'`, loser's `best_finish = 'runner_up'`
8. For the **third-place match**: set winner's `best_finish = '3rd'`, loser stays at 'SF' (they already got SF from losing the semifinal)
9. For **semifinal losses**: set the losing team's `best_finish = 'SF'` and note they are NOT eliminated yet (they play the third-place match)
10. Call `recalculate_all_scores()` to cascade everything
11. Return summary: `{"match_number": N, "result": "...", "scores_updated": True}`

**Stage ordering for `best_finish` comparisons:**

```python
STAGE_ORDER = {
    'group': 0,
    'R32': 1,
    'R16': 2,
    'QF': 3,
    'SF': 4,
    '3rd': 5,
    'runner_up': 6,
    'champion': 7,
}
```

#### `set_knockout_teams(match_id: int, home_fifa_code: str, away_fifa_code: str) -> dict`

Called by the admin route to assign teams to a knockout match shell as the bracket resolves.

1. Look up match, verify it's a knockout stage and teams aren't already assigned (or allow override)
2. Look up both teams by FIFA code
3. Set `home_team_id` and `away_team_id`
4. Commit and return confirmation

---

### Step 3: Detailed Scoring Pipeline Walkthrough

Here is the exact sequence `recalculate_all_scores()` must follow, with the scoring rules from the game design doc:

```
PHASE 1: Reset team cumulative scores
  For each WorldCupTeam:
    base_points = 0.0
    multiplied_points = 0.0
    group_wins = 0
    group_draws = 0
    group_losses = 0
    (DO NOT reset: advancement_method, best_finish, is_eliminated)

PHASE 2: Process group stage matches
  For each completed WorldCupMatch where stage == 'group':
    If is_draw:
      home_team.group_draws += 1
      away_team.group_draws += 1
      home_team.base_points += GROUP_DRAW (1)
      away_team.base_points += GROUP_DRAW (1)
    Elif winner == home_team:
      home_team.group_wins += 1
      away_team.group_losses += 1
      home_team.base_points += GROUP_WIN (3)
    Elif winner == away_team:
      away_team.group_wins += 1
      home_team.group_losses += 1
      away_team.base_points += GROUP_WIN (3)

PHASE 3: Apply advancement milestones
  For each WorldCupTeam where advancement_method IS NOT NULL:
    if advancement_method == 'group_winner':  base_points += 4
    if advancement_method == 'runner_up':     base_points += 3
    if advancement_method == 'best_third':    base_points += 1

PHASE 4: Process knockout matches
  For each completed WorldCupMatch where stage != 'group':
    winner = match.winner_team
    if stage == 'R32':  winner.base_points += 8
    if stage == 'R16':  winner.base_points += 11
    if stage == 'QF':   winner.base_points += 15
    if stage == 'SF':   winner.base_points += 19
    (Note: 'final' and 'third_place' are handled as podium bonuses, not here)

PHASE 5: Apply podium bonuses
  For each WorldCupTeam:
    if best_finish == 'champion':   base_points += 50
    if best_finish == 'runner_up':  base_points += 8
    if best_finish == '3rd':        base_points += 8

PHASE 6: Compute multiplied points
  For each WorldCupTeam:
    multiplied_points = base_points * multiplier

PHASE 7: Update picks
  For each WorldCupPick:
    pick.base_points = pick.team.base_points
    pick.multiplied_points = pick.team.multiplied_points

PHASE 8: Update enrollments
  For each WorldCupEnrollment with picks:
    total_score = sum(pick.multiplied_points for pick in enrollment.picks)

COMMIT
```

**Critical verification:** After implementing, mentally run through the Spain example from the game design doc:

Spain (Tier 1, ×1): 3 group wins (9 pts) + win group (4 pts) + win R32 (8) + win R16 (11) + win QF (15) + win SF (19) + champion (50) = **116 base × 1.0 = 116.0 multiplied**

And the Iran Cinderella example:

Iran (Tier 5, ×7): 1W 1D 1L in groups (4 pts) + best 3rd (1 pt) + win R32 (8) + win R16 (11) = **24 base × 7.0 = 168.0 multiplied**

### Step 4: Update CLI Commands

#### Update `flask worldcup recalc`

Replace the current try/except that catches `NotImplementedError`. The new version should:
1. Call `recalculate_all_scores()`
2. Print the summary: teams updated, picks updated, enrollments updated
3. Print the top 5 leaderboard after recalc

```python
@worldcup_cli.command('recalc')
def recalc_cmd():
    """Recalculate all scores from match results (idempotent)."""
    from games.worldcup.services.scoring import recalculate_all_scores
    result = recalculate_all_scores()
    click.echo(f"Recalculation complete:")
    click.echo(f"  Teams updated:       {result['teams_updated']}")
    click.echo(f"  Picks updated:       {result['picks_updated']}")
    click.echo(f"  Enrollments updated: {result['enrollments_updated']}")

    # Print top 5
    top = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .limit(5)
        .all()
    )
    if top:
        click.echo(f"\nTop 5:")
        for i, e in enumerate(top, 1):
            click.echo(f"  {i}. {e.get_display_name()} — {e.total_score:.1f} pts")
```

#### Add `flask worldcup process-match` (dev/testing convenience)

A CLI command for quickly entering a match result without the web admin UI. Useful for testing the scoring pipeline before the admin interface exists (4D).

```bash
flask worldcup process-match --match 1 --home-score 2 --away-score 1 --winner MEX
flask worldcup process-match --match 6 --home-score 1 --away-score 1 --draw
```

Parameters:
- `--match` (required): match number (1–104)
- `--home-score` (required): integer
- `--away-score` (required): integer
- `--winner` (optional): FIFA code of winning team
- `--draw` (flag): mark as draw (group stage only)
- `--extra-time` (flag): informational
- `--penalties` (flag): informational

The command should:
1. Look up the match by `match_number`
2. Call `process_match_result()`
3. Print the result and updated scores for both teams

**Skill prescription:** Use `test-driven-development` skill for this step. Write tests for the scoring pipeline before implementing. Test cases should cover:
- Single group win (verify team W/D/L and base_points)
- Group draw (verify both teams get draw credit)
- Full group stage for one group (3 matches, verify standings)
- Advancement milestone application
- Knockout round scoring
- Podium bonus (champion, runner-up, third place)
- Full pipeline: match → team → pick → enrollment
- Idempotency: run recalc twice, verify identical results
- The Spain undefeated champion scenario (expected: 116.0 pts)
- The Iran Cinderella scenario (expected: 168.0 pts)
- Half-point precision: Norway Tier 2 runner-up (expected: 106.5 pts)

### Step 5: Verify Scoring Correctness

After implementation, run these verification scenarios using the `process-match` CLI command:

#### Scenario A: Single Group Match

```bash
# Mexico (Tier 3, ×2.5) beats South Africa (Tier 5, ×7) 2-1
flask worldcup process-match --match 1 --home-score 2 --away-score 1 --winner MEX
flask worldcup status
# Expected: MEX base_points = 3.0, multiplied_points = 7.5
# Expected: RSA base_points = 0.0, multiplied_points = 0.0
```

#### Scenario B: Group Draw

```bash
# First reset by re-seeding (or use a test database)
# Brazil (Tier 1) draws Morocco (Tier 3) 0-0
flask worldcup process-match --match 6 --home-score 0 --away-score 0 --draw
# Expected: BRA base_points = 1.0, multiplied_points = 1.0
# Expected: MAR base_points = 1.0, multiplied_points = 2.5
```

#### Scenario C: Idempotency

```bash
flask worldcup recalc
flask worldcup recalc
flask worldcup status
# Scores must be identical after both recalcs
```

**Skill prescription:** Use `pyright-lsp` plugin after implementation to verify type correctness.

**Skill prescription:** Use `code-simplifier` plugin to reduce complexity after the scoring engine is working.

**Skill prescription:** Use `commit-commands` plugin to commit: `feat: implement World Cup scoring engine (idempotent recalc pipeline)`.

---

## Verification Criteria

1. ✅ `flask worldcup recalc` runs without error and prints summary (even with 0 completed matches)
2. ✅ `flask worldcup process-match --match 1 --home-score 2 --away-score 1 --winner MEX` correctly updates Mexico's score to 3.0 base / 7.5 multiplied
3. ✅ Running `recalc` twice produces identical results (idempotency)
4. ✅ Group draw correctly awards 1 point to both teams
5. ✅ Advancement milestones correctly award 4/3/1 base points
6. ✅ Knockout wins correctly award stage-specific points (R32=8, R16=11, QF=15, SF=19)
7. ✅ Champion bonus (50 base) applies correctly
8. ✅ Runner-up bonus (8 base) applies correctly
9. ✅ Third-place win bonus (8 base) applies correctly
10. ✅ Half-point precision works: a Tier 2 team (×1.5) with 3 base points shows 4.5 multiplied
11. ✅ Pick scores cascade correctly: after team scores update, all picks for that team reflect new scores
12. ✅ Enrollment total_score equals sum of its picks' multiplied_points
13. ✅ Spain undefeated champion scenario: 116.0 pts (Tier 1, ×1)
14. ✅ Iran Cinderella QF run scenario: 168.0 pts (Tier 5, ×7)
15. ✅ `best_finish` updates correctly through knockout progression and never regresses
16. ✅ `pyright` reports 0 errors on scoring.py
17. ✅ Tests pass for all scoring scenarios

---

## Edge Cases to Handle

These are documented in `WORLD_CUP_GAME_DESIGN.md` — the scoring engine must handle them:

1. **Forfeited match (3-0):** Treated as a normal win/loss. Admin enters 3-0 score with winner. Scoring engine handles it like any other result.

2. **Extra time / penalties:** Informational flags only. The winning team gets the knockout round points regardless of how the match was decided. A penalty shootout win in the R16 = 11 base points, same as a 90-minute win.

3. **Third-place match cancellation:** If FIFA cancels the third-place match, the game design says both SF losers get 3 milestone points as consolation. The admin would need to manually set `best_finish = '3rd'` for both teams and enter a synthetic match result, or the scoring engine could handle a special case. **Recommendation:** Don't build special handling for this unlikely scenario. If it happens, Brad can manually set `best_finish` and run `recalc`. Document this in a code comment.

4. **Team withdrawal mid-tournament:** Points earned to that point stand. No future points. The admin sets `is_eliminated = True` and doesn't enter any more match results for that team. Scoring engine handles this naturally — no completed matches = no points.

5. **Replayed match:** Only the replay result counts. Admin deletes the original match result (set `is_completed = False`, clear scores) and enters the replay. Recalc rebuilds everything.

---

## What This Does NOT Include

- **Admin web routes for match entry** — that's Handoff 4D. The `process-match` CLI command serves as a bridge for testing.
- **Admin web routes for advancement confirmation** — also 4D. The `apply_group_advancement()` function is implemented here but the web form calling it is in 4D.
- **Templates or CSS** — no UI changes in this handoff.
- **Pick submission validation** — that's 4C (player-facing UI).
