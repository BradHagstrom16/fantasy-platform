# The Docket — Binding Rulings (2026-08-11)

**Status:** Plan of record. Binding — do not re-ask any ruling here.
**Scope:** `games/docket/` (The Docket, NFL + CFB weekly pick 'em).
**Companions:** concept brief `docs/2026-08-11-nfl-cfb-pickem-office-hours-kickoff.md`; design doctrine `games/docket/DESIGN.md`; platform conventions `CLAUDE.md`.

These rulings were decided across three sittings on 2026-08-11 — a design session, a `/plan-eng-review` pass that afternoon, and an override that evening. They were previously readable only from a local `~/.gstack/` artifact on one machine, which made them unreachable to a teammate, a fresh checkout, a cloud session, or CI. This file is the in-repo copy and the one CLAUDE.md points at.

**What was left behind, deliberately.** Only the binding material is migrated: premises, session rulings, grading clarifications, the eng-review addendum, and the override. The source artifact also carried session narrative, an approach comparison that the override superseded the same evening, an open-questions list since answered inline, and tool-run bookkeeping — all of which would read as current if committed. Where an implementation later deviated from a ruling as written, the deviation and its cause are recorded in `ARCHITECTURE_DECISION_LOG.md`, not here: this file is the record of what was **decided**, not of what was built.

---

## ⚠️ Two D-namespaces, and they collide

There are **two independent sets of D-numbers** on this page, from two different sittings, and they overlap at D5–D11 with entirely different content. D5-session is the autopick package; D5-eng is the shared odds client. They are not the same ruling and never were.

Every reference below carries an explicit **`-session`** or **`-eng`** suffix. The source artifact used the suffixes only inside the override block, which is how "D5" ended up meaning two things in the same sentence elsewhere. Cite the suffixed form always.

- **`-session`** — the design session: Q1, D3, D4, D5, D6, D7, D8, D10, D11, plus the unchallenged Core row. (D1, D2, D9 and D12 are not stated as rulings; D2 appears inline in the premises and D12 as the approval stamp.)
- **`-eng`** — the `/plan-eng-review` addendum: D5 through D24.

---

## Premises

All agreed in-session (D2), with premise 3 revised by Brad and re-sequenced after the cross-model challenge (D10-session):

1. **Sibling game, not a Survivor variant.** New blueprint `games/docket/`; picks keyed to game+market+side (~10 rows/user/week), unlike Survivor's team-keyed one-pick model. Survivor is the pattern reference, not the base class.
2. **Deadline architecture:** Sat 11:00 AM CT week deadline + per-game kickoff locks (generalizing Survivor's proven per-pick-row pattern) + lines locked at import, never re-synced.
3. **REVISED — Multi-featured, enrollment-personalized lounge is the destination; lands post-launch (~October).** Both games featured for dual members, your one game if enrolled in one, both (recruiting posture) for visitors. The changeover ships on the current single-featured seam untouched; The Docket launches `status='open'`, `is_featured=False` with an additive interim (Survivor hero + Docket second-bill strip + tiles). Redesign runs via impeccable shape & adapt at root level (platform surface → root `PRODUCT.md` + `DESIGN.md`), designed against real dual-member behavior. Touchpoints when it lands: `lounge_game()` single-entry contract, `build_home_context` single-overlay merge, per-game partial-tree dispatch, `tests/test_registry_seam.py` locks, and it should anticipate *three* concurrent games (Golf, ~Jan 2027).
4. **WC-scale build:** ~6–9k lines Python + ~3k templates + comparable tests. Sequencing is explicit.
5. **The Odds API is the sole data source** (events, spreads+totals odds, scores; both sports), pending the quota check. Optional cross-check sources (CFBD, nflverse) noted by the second opinion as a credit-saving fallback — not launch scope.
6. **Full slates:** any FBS or NFL game, all season — including bowls and CFP rounds that fall before the season end (D8-session). No curated team table.

---

## Session Rulings (binding — do not re-ask)

| # | Ruling |
|---|--------|
| Q1-session (pre-ruled) | Per-game lock at kickoff: picked games lock in; unpicked games become unpickable at kickoff. Verified: Survivor already implements the pattern. |
| D3-session | **Lines import Tuesday**, mirroring Survivor's DQ-6: first fetch (~Tue 06:00 CT) locks what's posted; later runs fill gaps only; locked lines never move. Keeps Tue/Wed-night CFB games pickable. |
| D4-session | **Best pick is worth double** (win 2 / push 1 / loss 0). Not stacked. Max week = 9. |
| D5-session | **Autopick package:** top-up never overwrite; candidate pool = combined CFB+NFL games kicking off ≥ Sat 11:00:00 AM CT minus markets the user already picked; Over on the 4 highest totals + favorite on the 4 largest spreads, buckets exclusive per game (a game claimed by one bucket can't also fill the other) and backfilling each other when short; best pick auto-assigned to the largest favorite; no backup autopick; tiebreaker prediction defaults to the designated game's locked O/U total. Partial-picker matrix in Grading Clarifications below. |
| D6-session | **Backup = slot model.** 8 scoring slots + a dormant locked 9th pick. If any slots go No Contest, the backup's result substitutes into the cancelled slot whose game had the **earliest scheduled kickoff** — "scheduled" = the kickoff on the locked docket as of the deadline; same-instant ties break by pick-sheet slot order, lowest first (deterministic; independent of when cancellations are ruled — all picks locked pre-deadline, so substitution is leak-proof). Remaining cancelled slots → push (0.5). If the backup's own game is No Contest — or the player submitted no backup at all (autopick never assigns one) — the backup is dead and every cancelled slot falls back to push. Best-pick double lives on the slot (a substitute inherits it; push fallback in the best-pick slot = doubled push = 1). Backup obeys the same one-side-per-market, deadline, and kickoff-lock rules as the primaries. "Cancelled" = admin-ruled No Contest, reusing the platform concept; postponed beyond the week ⇒ No Contest. |
| D7-session | **Name/slug: The Docket / `docket`.** |
| D8-session | **December composition:** bowls + CFP rounds pickable alongside NFL 15–18. Import stays "any FBS game in the window"; CFP games after the season end (Jan 11) are out. |
| D10-session | Lounge: destination multi-featured, lands post-launch (premise 3 above). Changeover greenlit now. |
| D11-session | **Approach C — the Provisional Docket.** ⚠️ **SUPERSEDED** by the Ruling Override below. |
| Core-session (from brief, unchallenged) | 8 picks/week exactly, any mix, spread or O/U sides; the pick constraint is **per-market** — you may not take both sides of one market, but a spread pick and a total pick on the *same game* are two legal picks; max 1 entry; current-week picking only; win 1 / push 0.5 / loss 0; drop single worst week once >1 weeks completed; weekly designated tiebreaker game (SNF convention; Week 1 = Wisconsin @ Notre Dame), combined-score prediction to 0.1, absolute error accumulates season-long, lower better. |

---

## Grading Clarifications

Defaults set during spec review; none vetoed at approval.

- **Week window:** docket weeks partition time continuously at **Tuesday 06:00 CT** boundaries (import instant → next import instant); a game belongs to the week containing its kickoff. Covers CFB Tue/Wed games through NFL Monday night with no orphans.
- **Boundary semantics at Sat 11:00:00 AM CT:** submissions must land strictly *before* 11:00:00; a game locks *at* its kickoff instant (t ≥ kickoff ⇒ locked); the autopick pool is kickoff ≥ 11:00:00. Net effect for Big Noon kickoffs (exactly 11:00): pickable up to the deadline, locked at kickoff, autopick-eligible — all three rules agree.
- **Drop-worst-week scope:** "worst" = the week with the lowest points total (after best-pick doubling and push credit). The drop removes that week's **points only**. Wins (key 2) and cumulative tiebreaker error (key 3) are never dropped — the liability account never forgives.
- **Wins (ranking key 2):** the count of winning picks (a doubled best-pick win counts once; pushes and losses count zero).
- **Best-pick designation lock:** the designation locks with its pick at that game's kickoff (else at the deadline), and may never be moved onto a market whose game has already kicked off — closing the "move the double onto Thursday's winner on Saturday morning" exploit. Post-deadline *auto*-designation is exempt for the same determinism reason as autopick (a pure function of Tuesday-locked lines). The bridge's timestamp-void rule applies to designation rows exactly as to picks.
- **Tiebreaker error for non-participating weeks:** any enrolled player with no prediction for a week — including weeks before a late joiner enrolled — accrues that week's **default error** = |designated game's locked O/U total − actual combined score|. Everyone accrues error every week of the season; joining late buys no structural advantage on key 3.
- **Designation constraints (leak-proofing key 3):** designation requires a locked O/U total AND a kickoff ≥ the week deadline (admin UI enforces both — equivalently, predictions lock at min(deadline, designated-game kickoff), so nobody ever predicts a known score). If the designated game is ruled No Contest or loses viability *before* the deadline, the admin re-designates; existing predictions are **cleared to the new game's default** (its locked O/U total) and players are notified they may resubmit until the deadline. If it dies *after* the deadline, that week accrues **zero error for everyone** (identical treatment, account skips a week).
- **Autopick partial-picker matrix:** k missing picks → topped up per the D5-session heuristic in interleaved order — O1, F1, O2, F2, … (Overs by descending total, favorites by descending spread), skipping markets the user already holds, taking the first k. Missing best-pick designation (whether 0 or 8 picks were the player's own) → auto-designation always evaluates the **final 8-slot set** (own picks + top-ups) with one fallback chain: largest spread favorite; else the highest-total Over; else the earliest-kickoff pick. D5-session's "largest favorite" is the special case of this rule when all 8 are autopicks. No tiebreaker prediction → the designated game's locked total (D5-session).
- **Full three-key tie:** tied players share rank per the platform's competition-rank convention (`1, 1, 3, 4`); prize resolution on a persistent tie is a commissioner ruling, out of engine scope.

---

## Eng Review Addendum (2026-08-11) — Binding Build Rulings

`/plan-eng-review` locked the following. Each was decided explicitly by Brad; treat as part of the plan of record.

### Architecture

- **D5-eng — Odds client (resolves Open Q5):** share the *client*, not the fetch runs. Lift `odds_api_get` + retry into a shared platform module (e.g. `utils/odds_api.py`) with **credit logging (`x-requests-remaining`) built into the wrapper** on every call; per-game sport-key config kills the hardcoded ncaaf constants. CFB switches to the shared module with **zero behavior change** (full CFB suite green is the regression gate). Survivor's DQ-6 fetch pipeline untouched; Docket runs its own two-sport fetch. Golf/WC duplicate clients left frozen.
- **D6-eng — Datetimes:** every `docket_*` datetime column stores **UTC** (single contract — deviation from CFB's split contract, pre-approved). CT wall-clock exists only at week-creation (boundary/deadline computation, DST-safe by construction) and at render. Contract documented atop `models.py` + test-locked.
- **D7-eng — Schema hardening:** `UniqueConstraint(user, week, game, market)` (one-side-per-market structural), `UniqueConstraint(user, week, slot)` (8+1 slots, backup = slot 9), partial unique index for best-pick; **`line_value` (+ bookmaker key, per D17-eng) snapshotted onto each pick** with a parity test-lock; **`kickoff_at_deadline` frozen column** stamped at the deadline pass — the D6-session substitution ordering input (live kickoff column stays separate, see D19-eng).

### Code quality

- **D8-eng — Bridge import is full-fidelity:** raw picks + frozen lines + scores + NC rulings imported as first-class docket rows (`provisional_source`); the platform engine **re-grades Weeks 1–2** and the reconciliation gate is the diff vs the sheet's graded totals (discrepancies resolved by ruling before Week 3 grades). NOT the PR #131 archive-snapshot pattern — this is a live-ledger write. *(Applies only if the parachute deploys — see the override.)*
- **D9-eng — Engine purity is enforced:** typed frozen snapshot dataclasses as engine I/O; thin ORM→snapshot adapter; a test locks that the grading module imports no `db`/`models`/`flask` (registry-seam lock pattern).

### Tests

- **D10-eng — Fixtures are JSON data files** (`tests/fixtures/docket/`): week snapshot + expected per-user grades per case; one parametrized runner; strict loader (fails on unknown keys). Bridge Weeks 1–2 export into the same format as **permanent real-world fixtures**. Fixture catalog must cover every binding ruling: push, doubled push, substitution (incl. same-instant slot-order tie), multi-cancellation, **backup dead** (own game NC / none submitted), best-pick-slot cancelled (substitute inherits double; doubled push = 1), wins-key counting, drop-week activation + equal-lowest tie, late-joiner default error, autopick full/partial interleave + bucket backfill, auto-designation fallback chain, boundary semantics (10:59:59 / 11:00:00 / Big Noon triple-agreement), Tue 06:00 half-open week boundary, DST week, **OT + NFL-tie (D23-eng)**.
- **Iron-rule regression guard:** the D5-eng client move ships with the existing CFB suite passing unchanged + a wrapper-level credit-logging test.
- **D11-eng — `tests/conftest.py` starts now, additive:** canonical app/client fixtures consumed by new docket tests only; the 120 existing files untouched (backlog 3.1 stops growing; full migration stays a future PR).

### Ops

- **D12-eng — Scores cadence:** Tue **~05:15 CT** (post-MNF, pre-boundary) + Wed + Thu + Sun + Mon; **daily during the December window** (mirror `cfb-scores.timer`'s Dec 15–Jan 25 pattern for both sports) to stay inside `daysFrom=3`. **Corrected credit math** (verified: `/scores` with `daysFrom` = 2 credits; `/events` = free; one sport per request): regular season ≈ **155/month combined**, December worst month ≈ **200–230/month** — inside 500, but the tier check still runs first.
- **D13-eng — Backlog 2.4 closes in the Docket ops slice:** ship `deploy/fantasy-platform.preset` with scoped `disable worldcup-*` / `golf-*` / `cfb-*` / `docket-*` lines (NOT `disable *`); `deploy.sh` unit sync extended to `*.preset`; new `tests/test-deploy-guards.sh` case (run locally + `USE_REAL_FLOCK=1` on the droplet). Enabling stays deliberate per-name.
- **D14-eng — Persisted week grades:** `docket_week_result` rows (points, wins, error, drop-flag, graded_at; unique user+week — `CfbWeekOutcome` pattern) written by the grading pass; standings read the rollup; idempotent `flask docket recalc [week]`; an admin NC ruling auto-triggers that week's recalc. Bridge import lands in the same tables.

### Outside-voice adoptions (all accepted)

- **D15-eng — Sep 8 go/no-go checkpoint:** by Tue Sep 8, engine + bridge importer + pick sheet functionally complete (tests green) or Week 3 pre-emptively stays on the bridge (sheet prepped that day) and the platform targets Week 4. Decided once, on a date, not under a Saturday deadline. ⚠️ **Replaced** by the override's ~Tue Sep 1 go/no-go.
- **D16-eng — Bridge identity mapping:** the Form/mapping sheet carries a platform-identity column from Week 1; registration deadline **Sat Sep 13** in bridge comms; importer resolves via the mapping with a loud unresolved-identity report; all bridge players admin-enrolled via `/admin/enrollments` before import. *(Applies only if the parachute deploys.)*
- **D17-eng — Bookmaker provenance policy:** DraftKings preferred, fixed fallback order; each market independent (a game's spread and total may come from different books, book recorded per market); gap-fill applies the same policy at fill time; bookmaker key stored on the locked line and snapshotted onto picks; policy published on the rules page.
- **D18-eng — Audited line correction (data errors only):** admin may correct a locked line **pre-deadline only**, reason required, audit row (old/new/who/when/why), pickers of that market notified to re-decide. Post-deadline bad lines resolve via No Contest ruling. D3-session (no market re-sync) stands untouched.
  - *As shipped (T9), stricter than the ruling requires:* `admin_ops.correct_line` refuses **both** past the deadline and past that game's kickoff, since a kicked-off case's picks are frozen and moving the number under them would rewrite a locked record. The ruling set the outer bound; the implementation tightened it. This is why CLAUDE.md describes D18-eng as "pre-deadline AND pre-kickoff".
- **D19-eng — Kickoff refresh:** every docket sync run also refreshes commence times from the **free `/events` endpoint** into the live kickoff column (lock enforcement + display); `kickoff_at_deadline` stays frozen; a moved game logs a visible change row. Closes the stale-kickoff/pick-a-live-game hole.
- **D20-eng — Integer tenths for key 3:** predictions, per-week error, and cumulative error stored/computed as integer tenths (51.5 → 515); all-integer arithmetic; ÷10 at render; fixture expectations in tenths; a test locks that no float enters key 3. (Week *points* in 0.5 steps are float-exact — halves are powers of two — so this is a key-3 requirement specifically.)
- **D21-eng — Interim lounge strip is static:** renders purely from registry-generic keys (mark, name, tagline, static cadence copy, enrollment-aware join/enter CTA via existing `games_for_user`). No countdowns, no per-user pick state — the single-overlay seam contract stays untouched for the October redesign. Impeccable pass still applies.
- **D22-eng — Bridge is API-generated (resequencing):** the generalized two-sport client + `/events`+`/odds` import lands **before Aug 31**; a script emits each bridge week's sheet (games, `api_event_id`s, D17-eng-policy locked lines, tiebreaker game) from platform data; the Apps Script grades off those numbers; the importer joins on event id. Docket keys game identity on **`api_event_id` end-to-end** (no curated team table, no name matching). Credit-burn measurement starts two weeks early as a side effect.
- **D23-eng — OT + NFL ties stated:** all grading (spreads, totals, tiebreaker combined score) uses the final score **including overtime**; NFL ties grade normally against the locked numbers (tie vs spread resolves by the number; PK/0 → push). On the rules page; both are fixture weeks.
- **D24-eng — Reminders are sent-flag de-duped** (Golf's `last_reminder_type` pattern), never CFB's cadence-dependent shape; a test locks no-double-send. (CFB's own retrofit captured as backlog 2.7.)

**Refuted during review:** backlog 2.5 (rate-limit keying) is ✅ shipped (PR #129) — the kickoff brief's pointer was stale; CLAUDE.md corrected 2026-08-11. No signup-wave rate-limit action needed.

---

## RULING OVERRIDE (2026-08-11 evening, Brad — supersedes D11-session)

**The Docket launches PLATFORM-NATIVE for CFB Week 1.** Brad overrode Approach C on review, ruling that everything happens on `cccfantasy.com` and that both games would be ready for CFB Week 1. Chosen path: **Native Week 1 with bridge parachute**.

- Sprint to platform-native picks opening ~Mon Aug 31 / Tue Sep 1 (lines freeze Tue Sep 1; first deadline Sat Sep 5 11:00 CT). Both games (CFB Survivor + The Docket) live and operational for Week 1.
- **T5 (Form/Apps Script bridge ops) and T6 (bridge import) leave the active plan.** Parachute only: if a **~Tue Sep 1 go/no-go** [transcribed as "Mon Sep 1"; 2026-09-01 is a **Tuesday**, and the rest of the repo keys the line freeze to Tue Sep 1 — the date is the binding part, the weekday was a slip] (replacing D15-eng's Sep 8 checkpoint) finds the pick sheet not ready, a minimal Form is assembled in ~a day from the shipped `scripts/generate_bridge_sheet.py` + the WC Apps Script precedent. No Apps Script work before that.
- All scoring/grading rulings are UNCHANGED (Core-session, D4/D5/D6-session, all Grading Clarifications, D9/D10/D14/D17/D18/D19/D20/D23-eng). D8-eng (full-fidelity bridge import) and D16-eng (identity mapping, Sep 13) apply only if the parachute deploys.
- Build state at override time: T1 ✅ (#134), T2 ✅ (#135), T3 ✅ (#136, grading-spine models incl. `docket_pick`/`docket_week_result`/scores+NC columns), T4 ✅ (#137, pure engine + 26-case fixture catalog + adapter). Remaining sprint: T7a/T7b (DESIGN.md + scaffold + pick sheet), T8 (sync + recalc CLI), T9 (minimal admin), T10 (standings), T11 (timers + D13-eng preset), T13 (lounge strip), launch ops.
