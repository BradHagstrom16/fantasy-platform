# World Cup — Knockout Bracket Auto-Fill (R32 → Final)

**Date:** 2026-06-28
**Status:** Design approved, pending implementation plan
**Scope:** World Cup Fantasy Pool (`games/worldcup/`)

> **Addendum (2026-06-29): shipped as PER-SIDE incremental fill.** The original
> design here filled a whole shell (both teams) once its feeder *round* fully
> completed. In live use that left R16 blank until all 16 R32 matches finished,
> while the official/API bracket slots each winner the instant its match ends. The
> shipped version fills each shell **side** the moment its feeder match completes
> (`derive_sides` replaces `derive_pairings`; `set_knockout_team_side` writes one
> side; `fetch_bracket_proposal` exposes per-side `sides`; the cross-check is
> membership-based so home/away orientation is never a false conflict). It is
> self-gated via `derive_sides` — NOT `populatable_bracket_stages`, whose
> whole-round gate still drives the admin bulk-populate UI + advancement reminder.
> See CLAUDE.md "Results automation" for the authoritative current behavior.

---

## Problem

The World Cup results pipeline already auto-applies **match results** every 30 minutes
(`services/sync.sync_scores()` → `process_match_result()`), including knockout
extra-time and penalty outcomes. But it **skips any knockout shell whose teams are
not yet assigned** (`skipped_unassigned`). Team assignment into the next round's
shells is still a manual admin step: "Load from API → review → Confirm" on
`/worldcup/admin/bracket/<stage>`.

Consequence: if the admin does not fill the next round's bracket between rounds,
the played matches in that round **silently fail to apply** — scoring stalls and
players see empty/stale shells — until the admin performs the manual step. The
admin explicitly does not want being away or forgetting to cause this stall.

Group advancement (group → R32) is **out of scope**: it is already complete for
2026, and it is the only step carrying genuine judgment risk (FIFA best-third /
tiebreaker rules the local advancement page cannot compute — see
`project_worldcup_knockout_ops` memory and CLAUDE.md). This design covers only the
**deterministic downstream rounds**, where "winner of match X plays winner of
match Y" has exactly one answer once the feeder round is played.

## Goal

Automatically fill empty knockout shells for R16, QF, SF, Final, and Third-place
the moment their feeder round is complete, so:

1. Forgetting / being away never stalls scoring for downstream rounds.
2. The per-shell manual clicking disappears for the common case.
3. A wrong bracket is **never** written: an automated write happens only when we
   are confident it is correct.

Non-goals: automating group advancement or R32 assignment; building a new admin
UI; adding a new scoring path (we reuse `set_knockout_teams` + `process_match_result`).

## Confirmed facts (current system)

- Match-number layout (verified in `ccc_local`): group `1–72`, R32 `73–88`,
  R16 `89–96`, QF `97–100`, SF `101–102`, third-place `103`, final `104`.
- **All downstream KO shells already have `api_fixture_id` linked**
  (`537375–537390`). The API cross-check therefore matches shells by fixture id;
  the fragile `(stage, kickoff)` fallback in `fetch_bracket_proposal` is not relied on.
- `WorldCupMatch` stores `winner_team_id` on completed matches, so the **loser**
  of a match (needed for the third-place shell) is derivable as the non-winner side.
- Existing helpers we build on (all in `games/worldcup/services/sync.py`):
  - `sync_scores()` / `run_scores()` — the 30-min auto-apply path + timer entry.
  - `fetch_bracket_proposal(target_stage)` — read-only API proposal: returns
    `proposals` (per-shell `home_fifa`/`away_fifa`, `already_set`, `is_completed`),
    `unresolved`, and `error`. Never writes.
  - `ko_round_pending()` — returns the completed feeder stage code whose downstream
    shells are still empty, else `None` (SF resolves only when **both** final and
    third-place are filled).
  - `populatable_bracket_stages()` — downstream stages with empty shells whose
    feeder round is resolved.
  - `set_knockout_teams(shell_id, home_fifa, away_fifa)` — the existing write path
    (FIFA codes), already used by the manual bracket route.
  - `_send_admin_email(subject, body)`, `_notify_once(signature)` — admin
    notification + schema-free de-dup.
- `KO_STAGES = ('R32','R16','QF','SF','final','third_place')`.

## Approach: Hybrid (self-derived primary, API cross-check)

Two independent derivations of each downstream pairing, reconciled before any write:

- **B — Self-derived (primary).** From a fixed bracket topology + our own completed
  results (the match-data SSoT). Available the instant our scores land, with **no
  dependency on the API publishing the next round's fixtures on time**.
- **A — API cross-check (second opinion).** The existing `fetch_bracket_proposal`.
  When reachable and complete, it must **agree** with B before we write; when it
  disagrees, we block the write. When it is unreachable, B proceeds alone (flagged).

Rationale for hybrid (the user's explicit choice): B alone kills the forget-stall
even during an API outage; A alone would re-introduce the stall whenever the API
lags. Together, B gives availability and A gives a guard against a topology bug or
an API/data error.

## Components

New module `games/worldcup/services/bracket.py` (keeps auto-fill logic isolated and
testable; `sync.py` is already 587 lines and owns API I/O + scoring application).

### 1. `BRACKET_TOPOLOGY` — the fixed bracket (data)

A constant keyed by **downstream match_number** → an ordered pair of feeders, each
feeder being `('winner' | 'loser', feeder_match_number)`:

```python
# Illustrative shape — actual feeder pairs transcribed from the official
# FIFA 2026 bracket during implementation, then locked by the consistency test.
BRACKET_TOPOLOGY = {
    # R16  (#89–96): winners of R32 (#73–88)
    89: (('winner', 73), ('winner', 74)),
    # ... 90–96 ...
    # QF   (#97–100): winners of R16
    # SF   (#101–102): winners of QF
    103: (('loser', 101), ('loser', 102)),   # third place = SF losers
    104: (('winner', 101), ('winner', 102)),  # final = SF winners
}
```

**Authoring & verification (implementation task):** transcribe feeder pairs from the
official FIFA 2026 bracket (the same source used last session to verify the R32
pairings). Trust is established by three independent layers:

1. A **structural-consistency test** (see Testing): every shell `89–104` has exactly
   two feeders that are valid earlier matches; each R32 match `73–88` feeds exactly
   one R16 slot; SF losers feed `103`, SF winners feed `104`; no feeder is reused
   incorrectly; no match feeds itself.
2. The **runtime API cross-check** — at tournament time a topology error makes B and
   A disagree, which **blocks the write and escalates** rather than writing a wrong
   bracket. A topology bug degrades to manual; it can never corrupt the bracket.
3. Manual eyeball against the official bracket before merge.

### 2. `derive_pairings(stage) -> dict | None` (the "B" source)

Pure read over our DB. For each empty shell in `stage`, look up its feeders in
`BRACKET_TOPOLOGY`, read winner/loser from the completed feeder matches, and return
`{shell_id: (home_fifa, away_fifa)}`. Returns "not ready" (skip) if any feeder is
not `is_completed` / has no `winner_team_id`, or if a derived team is missing/invalid.

Loser derivation: for a completed feeder, `loser = home_team if winner_team_id ==
away_team_id else away_team` (the non-winner side).

### 3. `reconcile(stage) -> Decision` (the hybrid decision)

Combines `derive_pairings(stage)` (B) with `fetch_bracket_proposal(stage)` (A) and
returns one of: `APPLY` (with the pairings to write), `CONFLICT` (with the
disagreeing shells), `APPLY_UNCONFIRMED` (B only, API unavailable/incomplete), or
`NOT_READY`.

| B (ours)   | A (API)                | Decision           | Action                                                         |
|------------|------------------------|--------------------|----------------------------------------------------------------|
| complete   | reachable, agrees      | `APPLY`            | write via `set_knockout_teams`; normal receipt email           |
| complete   | reachable, disagrees   | `CONFLICT`         | **write nothing**; conflict-alert email (de-duped)             |
| complete   | unreachable/incomplete | `APPLY_UNCONFIRMED`| write from B; "written without API confirmation, spot-check" email |
| incomplete | —                      | `NOT_READY`        | do nothing (wait for the next timer run)                       |

"Agrees" = identical `{shell_id: frozenset({home_fifa, away_fifa})}` for every empty
shell B proposes (home/away orientation differences are not a conflict — both
orderings represent the same pairing; orientation follows B/topology on write).

### 4. `run_bracket_autofill() -> dict` (timer entry)

For each stage in `populatable_bracket_stages()`: call `reconcile`, act per the table,
collect a per-stage outcome. Returns a structured summary for logging.

## Guardrails & idempotency

- **Empty shells only.** Never overwrite a shell that already has both teams →
  preserves any manual override and makes re-runs safe. (`set_knockout_teams` is
  called only for shells B reports as empty.)
- **All feeders complete with a winner** before a shell is eligible (enforced in
  `derive_pairings`).
- **Two distinct, real teams** required per shell; otherwise that stage is `NOT_READY`.
- **API disagreement always blocks** the write (the one hard stop).
- **De-duped notifications** via `_notify_once` keyed by `(stage, decision)` so a
  pending `CONFLICT` emails once, not every 30 minutes.

## Ops wiring

Fold `run_bracket_autofill()` into the existing **30-minute** `run_scores()` path so
**no new systemd timer or crontab entry is needed**. Sequence per run:
`sync_scores()` → `run_bracket_autofill()`. The freshly-filled round's already-played
results then apply on the following run (or the same run if fill precedes a second
score pass — kept simple: fill after scores, apply next run). The manual bracket
pages (`/worldcup/admin/bracket/<stage>`) remain unchanged as the override / escape
hatch. Optionally expose `flask worldcup sync --mode bracket` for manual/testing
invocation.

## CLAUDE.md note

CLAUDE.md currently states KO bracket is "admin-confirmed ... never auto-written."
That invariant is **narrowed, not removed**: group advancement and the group→R32
transition stay admin-confirmed (tiebreaker risk); the deterministic downstream
rounds (R16→Final) become auto-filled under the hybrid guard, with the manual pages
retained as override. The conventions doc must be updated to reflect the new boundary
so a future session does not "restore" the old behavior as a regression.

## Testing

- **Topology consistency** (pure, no DB): structure invariants listed under
  `BRACKET_TOPOLOGY` above.
- **`derive_pairings`**: happy path per stage; third-place loser derivation; "not
  ready" when a feeder is incomplete / missing winner.
- **`reconcile`** — the four-row decision table: agree→APPLY, disagree→CONFLICT
  (no write), API-down→APPLY_UNCONFIRMED, feeder-incomplete→NOT_READY.
- **Idempotency / non-overwrite**: re-running fills nothing new; a manually-set shell
  is never overwritten.
- **Full-bracket simulation**: drive R32→Final end-to-end through the timer entry,
  asserting each round auto-advances and downstream results then apply via the
  existing scoring path; re-run `verify_scoring.py`-style invariants on the result.

## Risks & mitigations

- *Topology transcription error* → caught by consistency test + runtime cross-check
  (degrades to manual, never a wrong write).
- *API resolves a downstream fixture wrong/late* → late: B proceeds alone (flagged);
  wrong: disagreement blocks the write.
- *Both our result and the API wrong the same way* → would require our scoring to be
  wrong, which is the pre-existing match-data SSoT risk, not introduced here.
- *Auto-write during an outage with an undetected topology bug* → the only path to a
  wrong write; mitigated by the consistency test + pre-merge eyeball, and bounded
  blast radius (empty-shell-only, distinct-real-teams check, override pages, receipts).
