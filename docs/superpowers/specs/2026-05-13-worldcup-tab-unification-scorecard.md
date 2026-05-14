# WC Tab Unification — Project Scorecard

> Companion to `docs/superpowers/plans/2026-05-13-worldcup-tab-unification.md`.
> Modeled on `docs/superpowers/specs/2026-05-12-impeccable-design-improvement-scorecard.md`.

**Window**: 2026-05-13 → TBD.
**Goal**: Unify the 6 WC tabs on the Stats pattern (white cards / dark text / USA red+white+blue accents) without lightening the dark navy hero.
**Branching convention**: `worldcup/tab-unification-phase-N` (one branch + PR per phase).

---

## 1. Phase status

| Phase | Description | PR | Status | Closed |
|---|---|---|---|---|
| P0 | Quick wins + scorecard codification | [#22](https://github.com/BradHagstrom16/fantasy-platform/pull/22) | Open (awaiting review) | — |
| P1 | HUB body migration | — | Pending | — |
| P2 | BOARD body migration | — | Pending | — |
| P3 | ROSTER read-only migration | — | Pending | — |
| P4 | SCHEDULE light polish | — | Pending | — |
| P5 | Cleanup: retire `.card.wc-card` + update DESIGN.md/CLAUDE.md | — | Pending | — |

Predecessor PR (precondition, not part of this project): **#21** — `worldcup/hub-color-rebalance-r1` (hub pre-state polish landed under the *old* dark-card paradigm; its gold pieces will be re-derived to red in P1).

---

## 2. Per-surface heuristic / audit baselines

Captured pre-P0 from the impeccable critique that opened this project.

| Tab | Heur baseline | Audit baseline | Anti-pat hits | Source |
|---|---|---|---|---|
| HUB (pre-state) | 28 (post-PR-21) | — | 0 detector | Critique 2026-05-13 |
| ROSTER | — | — | 1 (group-letter pill ~1.05:1) | Phase 0 reconnaissance |
| BOARD | — | — | — | TBD before P2 |
| SCHEDULE | — | — | — | TBD before P4 |
| STATS | — | — | 0 | Already at target |
| RULES | — | — | 0 | Already at target |

Per-tab final scores recorded as phases close.

---

## 3. Locked decisions

Carried over from the plan (and the in-session question-tool answers).

1. **Pivot direction**: yes — move WC's body from "Tribune-Dark" to "Casual-Light." Dark navy hero stays as the WC signature.
2. **`.btn-game` red**: **global on WC**. `body.game-worldcup .btn-game` repaints red so every WC button reads red regardless of substrate.
3. **Leaderboard `<thead>`**: **stays navy, white body**. Strongest USA pattern.
4. **Migration order**: P0 → HUB → BOARD → ROSTER → SCHEDULE → cleanup. Each phase ships as its own PR.
5. **Accent rank-order**: red → white → blue → gold. Gold is **quaternary** — reserved for focus rings (a11y lock, `--gold-light`), champion banners, podium glow only.

---

## 4. Per-phase notes

### P0 — Quick wins + scorecard codification

**Branch**: `worldcup/tab-unification-phase-0`.
**Shipped**:
- `.wc-team-card .team-group-pill` contrast fix at `style.css` ~2854: navy-tinted fill + `--text-secondary` text → ~7:1 on white (was bone-on-bone at ~1.05:1). Hover lifts to `--wc-red`.
- `.wc-stat-card.is-lead` border-top flipped from `var(--gold)` to `var(--wc-red)` at `style.css` ~4429. Pattern-lock test renamed + updated in lockstep: `tests/test_design_p2_s2_4_1.py::test_is_lead_css_uses_red_rule_top_no_border`.
- Strategy doc + this scorecard moved into the repo.

**Deferred from P0 (re-routed)**:
- Broader gold audit (~92 `var(--gold` occurrences) — deferred to the phase that owns each surface.
- DESIGN.md doctrine rewrite — deferred to P5 per Brad's load-bearing-doc preference.

### P1 — HUB body migration

**Branch (planned)**: `worldcup/tab-unification-phase-1`.
**Targets**:
- Migrate the hub's three `.card.wc-card` surfaces (deadline / roster preview / leaderboard preview) onto `.wc-stat-card`.
- Reconcile PR #21's gold-on-dark accents to red-on-light per the new doctrine.
- Pattern-lock touches anticipated: `test_design_p6_s6_1_1.py` (`.card.wc-card .wc-eyebrow` lock — possibly no-op if the hub stops using `.card.wc-card`), `test_design_p6_s6_1_4.py` (commish-note gold-top — flip to red if it's in the hub flow).

### P2 — BOARD body migration

**Branch (planned)**: `worldcup/tab-unification-phase-2`.
**Targets**:
- Migrate `.table-worldcup` wrapper out of `.card.wc-card`. Navy thead stays.
- `.your-standing-tribune + .card.wc-card` gold-divider (S6.1.3 PI-1) flips to red — `test_design_p6_s6_1_3.py:113` in lockstep.
- `.row-current-user` re-tune for light substrate (14% red tint stays, anchor flips to `var(--game-primary)`).

### P3 — ROSTER read-only migration

**Branch (planned)**: `worldcup/tab-unification-phase-3`.
**Targets**:
- The post-deadline desktop read-only view in `picks.html` migrates out of `.card.wc-card`. Pick form edit mode is already `.tier-card` white — keep.

### P4 — SCHEDULE light polish

**Branch (planned)**: `worldcup/tab-unification-phase-4`.
**Targets**:
- Audit match-row patterns against the locked Stats reference. Typography + spacing alignment. No substrate change.

### P5 — Cleanup + DESIGN.md/CLAUDE.md update

**Branch (planned)**: `worldcup/tab-unification-phase-5`.
**Targets**:
- Retire `.card.wc-card` (zero use expected by P5). Retire `test_design_p6_s6_1_1.py::test_pi1_dark_card_eyebrow_lift_rule_exists`.
- Update CLAUDE.md's "dark `.card.wc-card` surface" guidance — replace with Casual-Light pattern documentation.
- Update DESIGN.md: Brad drafts the Casual-Light pattern + accent rank doctrine. Assistant restructures for consumption per the load-bearing-doc preference.
- Per-tab `$impeccable critique` re-runs. Score deltas recorded in §2 of this scorecard.

---

## 5. Verification cadence

Per the plan's verification section. Each PR ends with:
1. Visual smoke on `/worldcup/<tab>` via dev server + `WC_FAKE_NOW`.
2. Cross-tab eye-test: HUB → ROSTER → BOARD → SCHEDULE → STATS → RULES.
3. `pytest tests/test_design_*.py tests/test_worldcup_*.py` — baseline 626 passing.
4. `npx impeccable --json games/worldcup/templates/worldcup/` — clean.
5. Per-tab `$impeccable critique` — record the lift.
