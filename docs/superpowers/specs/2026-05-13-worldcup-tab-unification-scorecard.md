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
| P1 | HUB body migration | TBD | Open (awaiting review) | — |
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

**Branch**: `worldcup/tab-unification-phase-1`.
**Shipped**:
- 12 of 13 hub `.card.wc-card` containers migrated to `.wc-stat-card` across `_home_out.html` (2), `_home_pre.html` (3), `_home_live.html` (4), and `_home_post.html` (3). Plan exploration found more than the strategy doc's "three surfaces" estimate — the actual surface inventory was 13.
- **Champion banner exception**: `_home_post.html:30` (`.card.wc-card.wc-hero-grad`) deliberately kept dark + gold per the new accent doctrine (gold reserved for champion banners / podium glow). Wrapper-class migration to a dedicated `.wc-champion-banner` deferred to P5 so `.card.wc-card` can be fully retired then.
- **Global WC button repaint**: new `body.game-worldcup .btn-game` rule paints CTAs `var(--wc-red)` with `var(--wc-red-dark)` hover across every WC substrate. The prior `.card.wc-card .btn-game` dark-card scoped lift (to `--game-accent`) was removed in lockstep; the global rule supersedes it. New token `--wc-red-dark` (`#9C0826`, ~6.94:1 white-on-red AA) added to `tokens.css`.
- **Hero phase chip gold→red+white**: `.page-hero.wc-hero-grad .phase-indicator` flipped from gold-14% / gold-light to red-14% / white / red dot. New `@keyframes pulseRed` backs the hero-scoped `.active .phase-dot` ripple; `pulseGold` retained for non-hero consumers (e.g., `.wc-state-chip--live`).
- **`.wc-card-deadline` modifier retired**: the gold-top-on-dark deadline variant was rederived as `.wc-stat-card.is-lead` (red-top on light, locked by P0). The class is gone from CSS and templates.
- **`.row-current-user` light-substrate anchor flipped**: was `--gold-dark` → now `var(--game-primary)` (navy) with `var(--wc-red)` hover. The `.card.wc-card .table-worldcup .row-current-user > td a` dark-scoped override (gold-light → gold-hi) is preserved for BOARD/ROSTER until P2/P3 migrate those tabs.
- **Light-substrate eyebrow lift added**: `.wc-stat-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold) → --text-secondary` so the migrated hub eyebrows remain legible on white. Mirrors the existing dark-substrate lifts at `:2685` (hero) and `:7134` (dark card); together the three rules cover all WC substrates without disturbing the base `--bone-mute` token.

**Tests**:
- New: `tests/test_design_wc_tab_unification_p1.py` — 8 regression locks (global red rule exists, old scoped rule removed, hub partials have zero `.card.wc-card` except champion banner, `.card.wc-card-deadline` retired, `--wc-red-dark` defined, hero phase chip uses red not gold, `pulseRed` keyframe exists).
- Unchanged: `test_design_p6_s6_1_1.py::test_pi1_dark_card_eyebrow_lift_rule_exists` (invariant until P5 — BOARD/ROSTER still consume the rule).
- Unchanged: `test_design_p6_s6_1_4.py` (`commish-note-body` not on hub — confirmed via grep; no test flip needed).
- Full suite: **739 / 739 passing** (baseline 626 design+WC + 8 new P1 locks + the rest of the platform suite).

**Visual smoke**: Confirmed via Playwright on dev (`WC_FAKE_NOW='2026-06-01T12:00:00+00:00'`, pre state, branch=submitted): dark hero unchanged with red phase chip; `.is-lead` red-top deadline card; white `.wc-stat-card` roster + Top-of-the-Pool surfaces; red "AMEND THE OATH" / "VIEW ALL" CTAs; navy thead bar on table preview. Cross-tab eye-test against STATS reference passed; BOARD/ROSTER remain dark (deliberately untouched, P2/P3 territory). Zero browser console errors.

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
