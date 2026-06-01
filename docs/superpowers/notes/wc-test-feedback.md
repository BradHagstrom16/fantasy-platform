# WC Production Test Script — Issue & Feedback Tracker

Capture everything found during the Phase 5.5 test at cccfantasy.com. One line per issue — page/component, what you see, what you expect. Do not attempt fixes during the test. Just log.

**Scope:** Global platform pages + World Cup pages only. Golf and CFB are out of scope.

**Format:**
> `Page / Component — Observed behavior. Expected behavior.`

---

## Bug
*Scoring errors, broken logic, wrong data displayed.*
*Fix path: Bring to a Claude debug session. Use `systematic-debugging` skill.*

- [x] B1 (fixed) — Home `/` (lounge) post-state "Your Nine Nations" recap — Best-finish shows **raw codes** (`champion`, `runner_up`, `R16`, `R32`, `group`/`Group`). Expected display labels ("Champion", "Runner-up", "Round of 16"…). Root cause: `core/main/home_context.py:532` passes `pick.team.best_finish or 'Group'` (raw) and `_home_post.html:89` renders `{{ row.best_finish }}` unmapped. The WC room `/worldcup/` is correct (maps via `_BEST_FINISH_LABELS`, `home_context.py:620`) — the two `_home_post` trees diverged. Fix: plumb the mapped label on the lounge too. Violates the §11 "labels render literally" gate + the CLAUDE.md "fall back to raw code, NOT 'Group'" rule.
- [ ] B2 — 

---

## Critical
*Broken layout, unreadable text, mobile collapse.*
*Fix path: `impeccable audit` or `impeccable adapt`.*

- [ ] C1 — 
- [ ] C2 — 

---

## Functional
*Wrong state shown, missing UI feedback, confusing flow.*
*Fix path: `impeccable clarify` or `impeccable harden`.*

- [x] F1 (fixed) — Best-finish for an advanced team eliminated in R32 (e.g. England — a *group winner* that lost its R32) shows **"Group"** on BOTH lounge and WC room, indistinguishable from a true group-stage exit. Cause: `best_finish` only records knockout *wins*, so an R32 loser stays `''`, which both surfaces collapse to "Group" (`or 'group'`/`or 'Group'`). Shared/by-design but misleading — a group winner reads the same as a team that finished bottom. Consider a "Round of 32" (reached, didn't win) state.
- [x] F2 (fixed) — `/worldcup/team/<id>` "Match log" — the champion's **Final row reads "+0.0"** and the **+50 base (×mult) Champion bonus + advancement points are never itemized**; the log sums to less than the hero total (e.g. AUS log = 399 vs hero 756). Math is correct (champion bonus is a `best_finish` podium award, not match attribution per `compute_match_attribution`), but the single largest scoring event is invisible and contradicts the rulebook's "Champion earns 50 for winning the Final." Consider a podium/advancement line item.
- [x] F3 (fixed) — Admin `set-knockout` team dropdowns list **eliminated teams** (e.g. "Scotland [ELIMINATED]") as assignable to knockout shells. No guard prevents assigning a group-stage-eliminated team into R32+. Minor data-integrity gap; low risk (admin-only).

---

## Visual Polish
*Spacing off, color inconsistency, typography rough, alignment issues.*
*Fix path: `impeccable layout`, `impeccable typeset`, or `impeccable polish`.*

- [ ] P1 — 
- [ ] P2 — 

---

## Delight
*Nice-to-have: animations, empty states, personality touches.*
*Fix path: `impeccable animate` or `impeccable delight`.*

- [ ] D1 — 
- [ ] D2 — 
