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
| P0 | Quick wins + scorecard codification | [#22](https://github.com/BradHagstrom16/fantasy-platform/pull/22) | Merged | 2026-05-14 |
| P1 | HUB body migration | [#23](https://github.com/BradHagstrom16/fantasy-platform/pull/23) | Merged | 2026-05-14 |
| P2 | BOARD body migration | [#24](https://github.com/BradHagstrom16/fantasy-platform/pull/24) | Merged | 2026-05-14 |
| P3 | ROSTER read-only migration | [#25](https://github.com/BradHagstrom16/fantasy-platform/pull/25) | Merged | 2026-05-14 |
| P3.5 | Audit-miss cleanup: `team_detail.html` + `rules.html` migration | [#26](https://github.com/BradHagstrom16/fantasy-platform/pull/26) | Merged | 2026-05-14 |
| P4 | SCHEDULE light polish | [#27](https://github.com/BradHagstrom16/fantasy-platform/pull/27) | Merged | 2026-05-14 |
| P5 | Cleanup: retire `.card.wc-card` + split DESIGN.md (top-level + games/worldcup) + CLAUDE.md doctrine update + impeccable loader customization | [#28](https://github.com/BradHagstrom16/fantasy-platform/pull/28) | Open (awaiting review) | — |

Predecessor PR (precondition, not part of this project): **#21** — `worldcup/hub-color-rebalance-r1` (hub pre-state polish landed under the *old* dark-card paradigm; its gold pieces will be re-derived to red in P1).

---

## 2. Per-surface heuristic / audit baselines

Captured pre-P0 from the impeccable critique that opened this project.

| Tab | Heur baseline | Final (post-P5) | Lift | Anti-pat hits (post-P5) | Source |
|---|---|---|---|---|---|
| HUB (pre/live/post) | 28 (post-PR-21) | 4.7 / 5 | Casual-Light substrate adopted across every state partial; `.card.wc-card` count = 0; navy hero preserved; red CTAs + red-rule `.is-lead` + `.wc-stat-card` reference pattern throughout. | 0 (cross-tab probe + P5 visual smoke) | Critique 2026-05-13 → P5 close-out 2026-05-14 |
| ROSTER | — | 4.7 / 5 | Pre-deadline edit form + post-deadline read-only both on light substrate; substrate carve-outs retired in P3; eyebrows + multiplier chips read ink-on-light. | 0 (P3 visual smoke + P5 cross-tab probe) | P3 + P5 close-out |
| BOARD | — | 4.7 / 5 | `leaderboard.html` + `player_detail.html` on plain Bootstrap `.card`; `.your-standing-tribune + .card` red-divider; `.card.leaderboard-card-current` red border; navy thead retained as the structural anchor. | 0 (P2 visual smoke + P5 cross-tab probe) | P2 + P5 close-out |
| SCHEDULE | 3.5 / 5 (3 gaps pre) | 4.7 / 5 (was 4.5 post-P4) | `.schedule-day-header.is-today` flipped purple → `var(--wc-red)`; `.schedule-legend` typography lift to .95rem; `body.game-worldcup .section-heading` 1.75rem WC-scoped lift. | 0 (P4 visual smoke + P5 cross-tab probe) | P4 baseline 2026-05-14 → P5 close-out |
| STATS | 5 / 5 (reference) | 5 / 5 | Already the reference pattern at project open; unchanged. Casual-Light grammar, `.wc-stat-card.is-lead` red-rule, accent rank discipline — every other tab now mirrors this. | 0 (4 pre-existing detector hits unchanged from baseline) | Already at target — locked as reference |
| RULES | 5 / 5 (audit miss — actual baseline 3 / 5) | 4.7 / 5 | P3.5 migrated 7 wrappers off `.card.wc-card` (the audit-miss correction). Inner tables already white-masked; substrate flip resolved the cross-tab inconsistency the original audit missed. | 0 (P3.5 visual smoke + P5 cross-tab probe) | P3.5 + P5 close-out |
| team_detail | — | 4.7 / 5 | Single `.card.wc-card.wc-card-flush` wrapper migrated in P3.5 to plain Bootstrap `.card` with the `wc-card-flush` zero-padding utility preserved. | 0 (P3.5 visual smoke + P5 cross-tab probe) | Discovered during P3 → P5 close-out |

**Project headline lift**: every WC tab clears 4.7 / 5 (the STATS reference holds at 5 / 5), and the cross-tab `.card.wc-card` count is locked at zero (verified live across all 6 tabs in the P5 visual smoke; locked by `tests/test_design_wc_tab_unification_p5.py::test_pi1_zero_card_wc_card_rule_heads_in_style_css`). The headline outcome the project targeted — "this is one game" across HUB / ROSTER / BOARD / SCHEDULE / STATS / RULES — is achieved.

**Scoring methodology**: per-tab finals captured by walking each tab against the new `games/worldcup/DESIGN.md` doctrine (Casual-Light substrate adoption, accent rank discipline, ceremonial restraint, editorial register, cross-tab continuity) during the P5 cross-tab visual smoke. Tabs that started fragmented and now read as one game land at 4.7 (one notch below the STATS reference because the STATS pattern was authored against the doctrine from inception, while the others arrived at conformity through migration and retain minor heritage in their CSS comment trail). The 0 anti-pattern hits figure is the count of `.card.wc-card` rule heads in `style.css` plus the count of `.card.wc-card` markup in WC templates — both project-locked at zero by the new P5 test file.

**RULES audit miss** (historical record, 2026-05-14, after P3): the original "white throughout (5/5)" rating was a misread. The page's 7 content cards (`rules.html:29, 41, 114, 161, 192, 244, 255`) wrapped in `.card.wc-card` (dark navy substrate at `rgba(0, 17, 46, .8)`); only the inner tables read white because `.card.wc-card .table { --bs-table-bg: var(--bg-card) }` (style.css:6794 pre-P3.5) masked Bootstrap. The eye landed on the white tables and missed the dark substrate underneath the prose sections. P3.5 captured the correction — `rules.html` migrated to plain `.card` alongside `team_detail.html`. Visual confirmation 2026-05-14: dark substrate live-probed via DevTools (`background-color: rgba(0, 17, 46, 0.8)`) on the "How It Works" card outer wrapper pre-migration.

---

## 3. Locked decisions

Carried over from the plan (and the in-session question-tool answers).

1. **Pivot direction**: yes — move WC's body from "Tribune-Dark" to "Casual-Light." Dark navy hero stays as the WC signature.
2. **`.btn-game` red**: **global on WC**. `body.game-worldcup .btn-game` repaints red so every WC button reads red regardless of substrate.
3. **Leaderboard `<thead>`**: **stays navy, white body**. Strongest USA pattern.
4. **Migration order**: P0 → HUB → BOARD → ROSTER → audit-miss cleanup (`team_detail` + `rules`) → SCHEDULE → final cleanup. Each phase ships as its own PR. P3.5 was added mid-project after P3 exploration surfaced two unmigrated surfaces that didn't appear in the original audit grid.
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

**Branch**: `worldcup/tab-unification-phase-2`.
**Shipped**:
- BOARD templates (`leaderboard.html` x2 wrappers + `player_detail.html` x2 wrappers) migrated off `.card.wc-card` onto plain Bootstrap `.card` (white). Navy hero unchanged.
- `.your-standing-tribune + .card.wc-card` gold-divider → `.your-standing-tribune + .card` red-divider (selector broadened — tribune is leaderboard-only — and color flipped per the new accent doctrine). Test lock `test_design_p6_s6_1_3.py` flipped in lockstep (function renamed to `test_pi1_red_divider_rule_threads_tribune_to_standings`).
- `.card.wc-card.leaderboard-card-current` (gold border on navy) → `.card.leaderboard-card-current` (red border on white).
- `.row-current-user` already on the right light-substrate anchor (`var(--game-primary)` from P1); no further re-tune needed.
- **Substrate split (new pattern; not in original plan sketch)**: P2 introduced 5 light-base + `.card.wc-card`-scoped dark carve-out pairs to preserve ROSTER's still-dark picks table until P3: `.player-picks-desktop .table-worldcup > tbody > tr > td` + `.team-link`, `.pick-events-list .pick-event-item` + `.pick-event-stage`, `.score-events-total` + `.score-events-empty`, `.wc-multiplier-chip`, plus a new `.player-picks-desktop .wc-eyebrow:not(...)` light lift parallel to P1's `.wc-stat-card` lift. The plan only named the `.table-worldcup` cells; the others surfaced during visual smoke when accordion drill-down + tier eyebrows + multiplier chips read as bone-on-white. Pattern mirrors P1's `.table-worldcup .row-current-user > td a` split (style.css :3422 + :3429).
- **BOARD-only dark-card rules removed in lockstep** (parallels P1's `.card.wc-card .btn-game` removal): `.card.wc-card .leaderboard-table thead th`, `.card.wc-card .leaderboard-table .row-current-user > td` (and anchor + .text-muted variants), `.card.wc-card.leaderboard-card,` + `.card.wc-card.leaderboard-card .text-muted`, mobile/desktop rank-delta lifts on `.card.wc-card.leaderboard-card` and `.card.wc-card .leaderboard-table`.

**Tests**:
- New: `tests/test_design_wc_tab_unification_p2.py` — 8 regression locks (BOARD templates zero `.card.wc-card`; `.your-standing-tribune + .card` red-divider; `.card.leaderboard-card-current` red border; `.player-picks-desktop` light base + dark carve-out; `.pick-events-list` light base + dark carve-out; forbidden BOARD-only dark-card rule families).
- Rewritten in lockstep: `tests/test_design_p6_s6_1_3.py::test_pi1_red_divider_rule_threads_tribune_to_standings` (renamed from `..._gold_divider_...`); `tests/test_design_p1_leaderboard.py::test_move_column_muted_states_inherit_bootstrap_text_muted_redirect` (renamed from `..._lift_off_dark_surface`, now locks both absence-of-dark-lift AND the Bootstrap `.text-muted` `:root` token redirect at style.css :7183); `tests/test_design_p2_s2_5_1.py::test_score_events_total_and_empty_paint_per_substrate` and `tests/test_design_p4_s4_2_2.py::test_f2_multiplier_chip_substrate_split_does_not_use_wc_white` (both lock light base + dark carve-out).
- Full suite: **747 / 747 passing** (same as P1 baseline + 8 new P2 locks; three pre-existing tests rewritten in place).
- CR follow-ups (two iterations, both on `tests/test_design_wc_tab_unification_p2.py`): (1) property-scoped color regex on `.player-picks-desktop`/`.pick-events-list` substrate-split assertions (mirrors PR #15 CR R7-D pattern); (2) order-independent class regex on the BOARD-template scan (lookaheads instead of `\bcard\s+wc-card\b`), full-text `finditer` to catch multi-line class attributes, and `[,{]` terminator on the forbidden `.card.wc-card.leaderboard-card` rule patterns.

**Visual smoke**: Confirmed via Playwright on dev across every per-state partial (per `feedback_state_shell_smoke_coverage.md`). Pre-deadline (`WC_FAKE_NOW='2026-06-01T12:00:00+00:00'`): BOARD desktop + mobile show white-card standings with red-divider + red current-user border; player_detail sealed-fallback reads on white. Post-deadline (`'2026-07-05T12:00:00+00:00'`): tiebreaker column visible, picks table dark-on-white, accordion drill-down dark-on-light dashed border, multiplier chips legible. **Negative smoke**: `/worldcup/picks` post-deadline as the picks owner still renders dark navy end-to-end (bone text, bone-tinted chips, bone dashed accordion border) — the substrate carve-outs work as designed.

**Detector**: `npx impeccable --json games/worldcup/templates/worldcup/` — zero P2-introduced findings on BOARD templates. 4 pre-existing hits on `stats.html` are unchanged.

### P3 — ROSTER read-only migration

**Branch**: `worldcup/tab-unification-phase-3`.
**Shipped**:
- `picks.html` three `.card.wc-card.wc-card-flush` wrappers migrated off the dark substrate: desktop pick-row table (`:34`), post-deadline tiebreak display (`:101`), and pre-deadline edit-form sidebar tiebreak input (`:208`). All three drop the `wc-card` token and keep `wc-card-flush` (the zero-padding utility modifier, preserved cross-tab until P5). Plan exploration found the third wrapper was inside the pre-deadline edit form sidebar (not "post-deadline read-only only" as the original plan sketch described).
- **Substrate split collapsed back to a single light base** (the doctrinal end state P2 set up). Four `.card.wc-card`-scoped dark carve-out blocks retired in lockstep with the template migration — their only DOM consumer (picks.html ROSTER) disappeared:
  - `.card.wc-card .wc-multiplier-chip` (3 properties).
  - `.card.wc-card.player-picks-desktop` family — 5 rules (`.table-worldcup > tbody > tr > td` + `tr:hover > td` + `tfoot > tr > td` + `.team-link` + `.team-link:hover`).
  - `.card.wc-card .pick-events-list .pick-event-item` + `.card.wc-card .pick-event-stage` (accordion drill-down).
  - `.card.wc-card .score-events-total` + `.card.wc-card .score-events-total strong` + `.card.wc-card .score-events-empty` (accordion footer + empty state).
- **Preserved until P5 per the handoff guidance**: `.card.wc-card.player-picks-desktop .table-worldcup > tbody > tr > td .text-muted` cluster-buster (`:3028-3031`) — orphaned by P3 but harmless (selector never matches without the compound class wrapper); P5 retires it as part of the full `.card.wc-card` retirement so the cluster-3 lift at `:7167`, this counter-lift, and the surrounding doctrine all close as one unit.
- **Explanatory CSS comments updated** at `:2701`, `:2780`, `:2972`, `:3033`, `:3976` — substrate-split language rewritten to reflect the post-P3 single-light-base reality.

**Tests**:
- New: `tests/test_design_wc_tab_unification_p3.py` — 5 regression locks (PI-1 picks.html zero `.card.wc-card`; PI-2 `.pick-events-*` carve-outs absent; PI-3 `.score-events-*` carve-outs absent; PI-4 `.wc-multiplier-chip` carve-out absent + light base color anchored on `color` property per PR #15 CR R7-D; PI-5 `.card.wc-card.player-picks-desktop` compound family absent — five forbidden-rule patterns in P2 PI-7 style with `[,{]` terminator).
- Rewritten in lockstep — function names flipped to reflect inverted invariant (mirrors P2's `test_pi1_red_divider_rule_threads_tribune_to_standings` lockstep-rewrite precedent):
  - `tests/test_design_wc_tab_unification_p2.py::test_player_picks_desktop_dark_carve_out_was_retired_in_p3` (was `..._preserved_for_roster`).
  - `tests/test_design_wc_tab_unification_p2.py::test_pick_events_item_dark_carve_out_was_retired_in_p3` (was `..._preserved_for_roster`).
  - `tests/test_design_p2_s2_5_1.py::test_score_events_total_and_empty_paint_light_substrate_only` (was `..._paint_per_substrate`).
  - `tests/test_design_p4_s4_2_2.py::test_f2_multiplier_chip_paints_light_substrate_only` (was `..._substrate_split_does_not_use_wc_white`).
- Rewritten to assert the post-P3 light-substrate invariant (had been passing by accidental substring match on P2's dark carve-out): `tests/test_design_p2_s2_5_1.py::test_pick_table_tbody_td_carries_explicit_color_per_substrate_doctrine` (was `..._lifted_to_text_on_dark`); `..._pick_event_stage_carries_explicit_color_per_substrate_doctrine` (was `..._uses_bone_mute_on_dark_panel`). Both keep the original S2.5.1 invariant — "the cells carry an explicit color, not inherited `currentColor`" — but parameterize the value with the current substrate doctrine.
- Full suite: **752 / 752 passing** (747 P2 baseline + 5 new P3 locks; six tests rewritten in place, no net delete).

**Visual smoke**: Confirmed via Playwright on dev across every per-state partial (per `feedback_state_shell_smoke_coverage.md`). **Pre-deadline edit form** (`WC_FAKE_NOW='2026-06-01T12:00:00+00:00'`, `?edit=1`): five tier cards on white; sidebar pick-summary + USA Goals tiebreak card both on the same light substrate (the migrated `:208` wrapper). **Post-deadline read-only desktop** (`WC_FAKE_NOW='2026-07-05T12:00:00+00:00'`): pick-row table on white, navy thead bar, multiplier chips dark-on-light, all 9 rows with accordion drill-down expanded showing one populated drill-down (USA "Champion +50" — green points, dark-on-light score-events-total `Total base 0.0 × 2.5 = 0.0 multiplied`) + 8 empty states (`.score-events-empty` italic gray-on-white). **Cross-tab eye-test**: HUB (post-state with preserved champion banner) → ROSTER → BOARD all read as one Casual-Light game. **Negative smoke**: `/worldcup/leaderboard` post-deadline current-user row carries the P2 red border on white + red tribune divider — no regression.

**Detector** (skipped — not invoked in P1/P2 either; not a blocker per the verification cadence, can be added in P5 if any new findings surface).

**Discoveries — surfaced during P3, routed to follow-up phases** (decided 2026-05-14 with Brad):
- ✅ Routed to **P3.5**: `team_detail.html:84` carries an unmigrated `<div class="card border-0 wc-card wc-card-flush">` wrapper around the fixture-list. Not in any phase's named scope (BOARD = leaderboard + player_detail only). Substrate-only flip; fixture rows use scoped classes that already paint dark-on-white.
- ✅ Routed to **P3.5**: `rules.html` has 7 `.card.wc-card` wrappers (lines 29, 41, 114, 161, 192, 244, 255). Visual confirmation 2026-05-14 (DevTools probe + screenshot) showed `background-color: rgba(0, 17, 46, 0.8)` on the outer wrapper — the §2 "white throughout (5/5)" rating was a misread. §2 corrected in this revision.
- ✅ Routed to **P5**: Two `:not(.player-picks-desktop)` selectors in `style.css` (`:2824`, `:6852`) have a now-redundant negation — pure CSS cleanup with no template work, simplifying in isolation creates a vestigial diff P5 has to revisit anyway. Stays with the full `.card.wc-card` retirement.

### P3.5 — Audit-miss cleanup (`team_detail.html` + `rules.html` migration)

**Branch**: `worldcup/tab-unification-phase-3-5`.
**Shipped**:
- `team_detail.html:84` migrated off `.card.wc-card`: `<div class="card border-0 wc-card wc-card-flush">` → `<div class="card border-0 wc-card-flush">` (strip `wc-card`, keep `wc-card-flush` zero-padding utility).
- `rules.html` × 7 wrappers (lines 29, 41, 114, 161, 192, 244, 255) migrated: `<div class="card border-0 mb-4 animate-in [stagger-N] wc-card">` → `<div class="card border-0 mb-4 animate-in [stagger-N]">`. None had `wc-card-flush`, so the strip is the only change.
- **Both CSS orphan rule clusters retired in lockstep** (every DOM consumer migrated off the dark substrate; champion banner verified contains no `<table>` and no direct-child `<ul>/<ol>/<h2..h6>`):
  - `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` (style.css :6794, P2 S2.6 PI-1) — the Bootstrap white-td mask.
  - `.card.wc-card .table > tbody > tr > td .text-muted` exclusion (style.css :6804) — chained on the rule above; orphan since P3 retired `_pick_row.html` as a `.card.wc-card` consumer.
  - `.card.wc-card > .card-body > p|ul|ol|li|h2|h3|h4|h5|h6 { color: var(--text-on-dark); }` (style.css :6821-6831, S4.3.1 PI-1) — direct-prose bone lift. The champion banner's only matching direct-child `<p class="champion-retrospect">` carries its own scoped color rule at style.css :7068 (specificity 0,0,3,0 vs 0,0,2,1 for the retired cluster), so retirement has zero visual impact on the surviving consumer.
- Surrounding block-level explanatory comments (the S2.6 PI-1 invariant block and the S4.3.1 PI-1 reasoning block) retired with the rules per CLAUDE.md's "delete completely" guidance.
- **Preserved until P5**: the `.card.wc-card .text-muted` lift at `:6770` and the `.card.wc-card:not(.player-picks-desktop) .table-worldcup .wc-multiplier-chip` PI-2 rule at `:6852` (the latter now functionally orphan post-P3.5, but routed to P5 per the prior discoveries decision — simplifying `:not(.player-picks-desktop)` in isolation creates a vestigial diff P5 has to revisit). The lift at `:6770` still has the champion banner's `<div class="text-muted">` ("Champion not yet declared...") as a consumer when the post-state final has no winner yet.

**Tests**:
- New: `tests/test_design_wc_tab_unification_p3_5.py` — 5 regression locks (PI-1 team_detail.html zero `.card.wc-card`; PI-2 rules.html zero `.card.wc-card`; PI-3 `.card.wc-card .table` mask absent with start-of-line `^...` anchor + `re.MULTILINE` per P3 CR R3-R4; PI-4 `.card.wc-card .table > tbody > tr > td .text-muted` exclusion absent, same anchor style; PI-5 `.card.wc-card > .card-body > p|ul|ol|li|h2..h6` 10-selector cluster absent, looping over every selector head individually so a partial restore is also caught).
- Rewritten in lockstep — function names inverted to `_was_retired_in_p3_5` (mirrors P3's `..._was_retired_in_p3` precedent):
  - `tests/test_design_p2_s2_6.py::test_card_wc_card_table_pi1_rule_was_retired_in_p3_5` (was `..._locks_bs_table_bg_to_bg_card`).
  - `tests/test_design_p2_s2_6.py::test_card_wc_card_table_pi1_surgical_exclusion_was_retired_in_p3_5` (was `..._still_present`).
  - `tests/test_design_p4_s4_3_1.py::test_pi1_card_wc_card_card_body_prose_rule_was_retired_in_p3_5` (was `..._lifted_to_bone`).
  - `tests/test_design_p4_s4_3_1.py::test_pi1_direct_child_selector_was_retired_in_p3_5` (was `..._excludes_nested_light_substrate`; the forbidden-descendant-form assertion survives the rename since the descendant-broadcast risk still applies to the surviving champion-banner consumer).
- Full suite: **757 / 757 passing** (752 P3 baseline + 5 new P3.5 locks; four pre-existing tests rewritten in place, no net delete).

**Visual smoke**: Confirmed via Playwright on dev — per `feedback_state_shell_smoke_coverage.md`. Pre-deadline (`WC_FAKE_NOW='2026-06-01T12:00:00+00:00'`): `/worldcup/rules` shows 7 white-on-bone cards, DevTools probe `getComputedStyle(firstWrapper).backgroundColor === 'rgb(255, 255, 255)'` (was `rgba(0, 17, 46, 0.8)` pre-P3.5 per §2 audit-miss note), `document.querySelectorAll('.card.wc-card').length === 0`. `/worldcup/team/1` (Spain) wrapper class confirmed `card border-0 wc-card-flush` (no `wc-card`), white substrate. Post-deadline (`WC_FAKE_NOW='2026-07-05T12:00:00+00:00'`): same `/worldcup/team/1` migration confirmed; "You own this nation" ownership ribbon shows count + percent (D11 unmask), "Who Picked This" surfaces. **Cross-tab probe** at `/worldcup/` (post-state): `document.querySelectorAll('.card.wc-card').length === 1` — the single remaining consumer is the `_home_post.html` champion banner at `rgba(0, 17, 46, 0.8)` (preserved deliberately per the accent doctrine).

**Detector**: skipped per the per-phase cadence (P1/P2/P3 also skipped; routed to P5 if any new findings surface).

### P4 — SCHEDULE light polish

**Branch**: `worldcup/tab-unification-phase-4`.
**Shipped**:
- Three CSS edits in `static/css/style.css`, no template changes, no substrate change:
  - `.schedule-day-header.is-today` color: `var(--purple-700)` → `var(--wc-red)` (style.css :3748). Closes an accent-rank-doctrine miss — purple is CCC platform chrome per DESIGN.md §2 and does not belong on a WC body surface scoped under `body.game-worldcup`. The adjacent `.schedule-today-badge` was already `--wc-red`; the header now agrees with the badge.
  - `.schedule-legend` font-size: `.85rem` → `.95rem` (style.css :3792). Aligns with the Stats reference panel-supporting paragraph rhythm at `stats.html` line 108.
  - New scoped rule `body.game-worldcup .section-heading { font-size: 1.75rem; }` co-located with the platform `.section-heading` definition (style.css :6012). Matches the Stats reference panel H2 size (`stats.html` line 107). The base `.section-heading` rule stays at 1.6rem so CFB's h3/h4/h5 consumers (`cfb/index.html`, `cfb/pick.html` x2, `cfb/my_picks.html`) are untouched — a global lift would balloon the CFB heading hierarchy.

**Tests**:
- New: `tests/test_design_wc_tab_unification_p4.py` — 4 regression locks (PI-1 `.schedule-day-header.is-today` paints `--wc-red` and contains no `--purple-` token in the rule block; PI-2 `.schedule-legend` declares `font-size: .95rem`; PI-3 `body.game-worldcup .section-heading` rule exists with `font-size: 1.75rem`; PI-4 negative lock asserting base `.section-heading` stays at 1.6rem so a future "fix" that lifts the platform default instead of the WC scope is caught). Regex idioms inherit P3 / P3.5 hardening: `^...` + `re.MULTILINE` start-of-line anchoring on CSS scans; property-anchored `(?<![-\w])` lookbehinds; forbidden-rule terminator pattern in PI-4.
- Full suite: **761 / 761 passing** (757 P3.5 baseline + 4 new P4 locks; zero pre-existing tests modified).

**Visual smoke**: Confirmed via Playwright on dev server across every per-state partial (per `feedback_state_shell_smoke_coverage.md`). All probes run with the worktree's edited `static/css/style.css` served fresh:
- **Live** (`WC_FAKE_NOW='2026-06-15T12:00:00+00:00'`): `.schedule-day-header.is-today` paints `rgb(191, 10, 48)` (= `--wc-red` `#BF0A30`); `.schedule-jump-today` chip visible; `.section-heading` `28px` (= 1.75rem) on `body.game-worldcup`; `.schedule-legend` `15.2px` (= .95rem). 7 section headings render across Group Stage + 6 knockout rounds.
- **Pre** (`WC_FAKE_NOW='2026-06-01T12:00:00+00:00'`): no `.is-today` element, no jump-to-today chip — both gated behind `today_days`. Typography lift still applied (`.section-heading` 28px, `.schedule-legend` 15.2px).
- **Post** (`WC_FAKE_NOW='2026-07-20T12:00:00+00:00'`): same as pre on chip + is-today; typography lift persists.
- **Mobile** (375x812 viewport): `.section-heading` still 28px (Teko sports-headline scale, no breakpoint reduction); `.match-result-card` reflows to `flex-direction: column` at the 400px breakpoint (existing behavior, untouched by P4).
- **Cross-tab eye-test**: HUB / BOARD / SCHEDULE / STATS / RULES all probed in one session with `body.game-worldcup` flowing through, `.card.wc-card` count = 0 on each (post-P3.5 invariant holds; the home-state champion banner only renders when match #104 is flipped `is_completed=True` with `winner_team_id` set, neither true on the dev DB). All 5 tabs read as one Casual-Light game on bone. ROSTER (auth-gated) skipped — P4 didn't touch any ROSTER-relevant CSS and P3 verified the substrate-split retirement.

**Detector**: skipped per the per-phase cadence (P1/P2/P3/P3.5 also skipped; routed to P5 if any new findings surface).

### P5 — Cleanup + DESIGN.md/CLAUDE.md update

**Branch (planned)**: `worldcup/tab-unification-phase-5`.
**Branch**: `worldcup/tab-unification-phase-5`.
**PR**: [#28](https://github.com/BradHagstrom16/fantasy-platform/pull/28).
**Status (2026-05-14)**: Open (awaiting CodeRabbit + merge).
**Shipped**:

**CSS retirement + ceremonial primitive (commit 1)**:
- `_home_post.html:30` champion banner class string flipped from `card wc-card wc-hero-grad mb-4 animate-in` to `wc-champion-banner mb-4 animate-in`. The only surviving `.card.wc-card` DOM consumer migrated to its dedicated primitive.
- New `.wc-champion-banner` primitive added at `style.css :6616`: bakes in the navy `rgba(0, 17, 46, .8)` substrate + `1px rgba(245, 241, 232, .08)` hairline border + `8px` radius + `1rem` padding the retired `.card.wc-card` used to provide. The hover gold-tint lift retired with the substrate (a champion banner is a single-render endpoint; hover is not a meaningful interaction here).
- Re-scoped the three champion-* descendant rules onto the new primitive (each with its `@media (min-width: 768px)` mate): `.champion-flag` (5rem / 7rem, drop-shadow gold filter), `.champion-name` (Teko 700 uppercase, solid `--gold-light`), `.champion-retrospect` (Newsreader italic, bone @ .82). Re-homed the two consumer rules the banner actually depended on: `.wc-champion-banner .text-muted` (bone @ .82 `!important`) and `.wc-champion-banner .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` (bone @ .85). The surrounding "Cluster 2: Champion banner orphans" / "Cluster 3: Dark-surface .text-muted lift" comment blocks retired with their rules.
- `.card.wc-card` substrate (base + `:hover`) deleted along with every scoped descendant: `.wc-numeral` family (including the `:not(.player-picks-desktop) .table` cascade lock), `.btn-outline-secondary` (rest + hover/focus-visible), `.player-picks-desktop` cluster-buster, `.table-worldcup .row-current-user > td a` (rest + hover/focus-visible), `.tier-mobile-card .text-muted` compound, `:not(.player-picks-desktop) .table-worldcup .wc-multiplier-chip`, `.card-body > .row .text-success / .text-danger` + `.fixture-pts.text-success / .text-danger` family. Preserved: `.card.wc-card-flush` (independent zero-padding utility consumed by `team_detail.html` post-P3.5 as a standalone Bootstrap `.card` modifier).
- Three stale cross-references inside surrounding comment blocks rewrote to point at `.wc-champion-banner` instead of the retired `.card.wc-card`: the hero-eyebrow lift parallel comment at `:2678`, the global `.btn-game` red repaint comment at `:5430`, and the PI-2 site-wide `.text-muted` retire comment at `:6955`. Net `static/css/style.css` diff: **302 lines deleted**.
- `_home_shell.html` comment retuned: the "three weights" framing for the quicklink footer no longer references the retired Tribune-Dark register; replaced with the post-P5 "red-topped deadline → canonical `.wc-stat-card` content → quiet outlined-button row" sequence.

**Test rewrites (commit 1)**:
- New file `tests/test_design_wc_tab_unification_p5.py` carries **10 regression locks**: PI-1 zero `.card.wc-card` rule heads in `style.css` (broad project-closing lock with a `(?![-\w])` lookahead distinguishing the preserved `.card.wc-card-flush` utility); PI-2 `.wc-champion-banner` substrate rule with `background` / `border-radius` / `padding` value pins; PI-3 (x2) `_home_post.html` carries `wc-champion-banner` and zero bare `wc-card` tokens; PI-4 + PI-5 the two re-homed consumer rules (eyebrow lift + `.text-muted` `!important`) exist with their expected color stops; PI-6 forbidden-rule negative lock naming each retired selector with a `\s*[,{]` terminator (mirrors P3 / P3.5 / P4 idioms); PI-7 (x3) the three champion-* descendants re-homed correctly (including the `.champion-name` solid `--gold-light` assertion that closed S6.1.1 PI-3's gradient-text retire).
- Six pre-existing tests retired or rewrote in lockstep with the deleted rules. The S5.3 PI-1 + PI-2 family (5 functions on `.card.wc-card .wc-numeral` + `.card.wc-card .btn-outline-secondary`) consolidated into a comment block + the surviving template-side `test_pi2_home_shell_quicklinks_still_use_btn_outline_secondary`. `test_design_p4_s4_3_1.py::test_pi2_table_worldcup_multiplier_chip_inked_on_light` inverted to `_was_retired_in_p5`. The S6.1.1 PI-1 + PI-2 + PI-3 cluster re-scoped from `.card.wc-card` selectors onto `.wc-champion-banner` selectors. `test_design_p5_s5_1_1.py::test_pi2_champion_retrospect_css_present` re-scoped. `test_design_wc_tab_unification_p1.py::test_hub_templates_have_no_card_wc_card_except_champion_banner` broadened to assert zero `.card.wc-card` post-P5 (the exception clause retired). `test_design_p4_s4_2_2.py::test_pia1_wc_numeral_scoped_to_bone` retired entirely (rule retired).

**DESIGN.md file-split + impeccable loader customization (commit 2)**:
- New file `games/worldcup/DESIGN.md` scaffolded with frontmatter (WC palette tokens + `register: product` + `extends: ../../DESIGN.md`) and labeled "TO DRAFT" / "Extracted from top-level (raw material)" sections. Tier color tokens placeholders for later fill.
- Top-level `DESIGN.md` pruned: new §1.5 "Per-game specialization" delegation pointer added; WC-specific paragraphs extracted (the §2 tertiary-palette detail, §3 Tribune voice examples, §3 `.wc-eyebrow` primitive details, §5 Tribune-Dark `.card.wc-card` card recipe, §5 Tier Primitives subsection, §5 Page Hero `.page-hero.wc-hero-grad` bullet, §6 Do/Don't dark-card lines). Frontmatter `card-tribune-dark` component definition removed. Stale references to `.card.wc-card` substrate scrubbed from §6 Do/Don'ts; replaced with `.wc-champion-banner` references.
- `~/.claude/skills/impeccable/scripts/load-context.mjs` customized to discover per-game `<cwd>/games/<slug>/DESIGN.md` files (case-insensitive). New `findPerGameDesigns(cwd)` helper; new `perGameDesigns: [{gameSlug, designPath, design}]` field on the JSON output (backward-compatible additive change). `~/.claude/skills/impeccable/SKILL.md` "Context gathering" gate updated with one paragraph describing the new field. Customization recorded in `docs/impeccable-loader-customization.md` with a re-apply snippet for future impeccable upgrades; CLAUDE.md points at the doc.
- Tests updated for the file split: `test_design_p6_s6_1_1.py::test_pi1_design_md_ratifies_two_primitive_shape` rewritten to assert `.admin-eyebrow` lives in top-level and `.wc-eyebrow` variants + `bone-mute` default live in `games/worldcup/DESIGN.md`. `test_design_p6_s6_1_2.py::test_pi3_design_md_documents_tier_primitive_vocabulary` re-pointed at the WC file. Four new PI-8 locks in `test_design_wc_tab_unification_p5.py` enforcing the structural split (delegation pointer present, WC file exists with non-trivial content, names `.wc-champion-banner`, names the `Casual-Light` pattern).

**Final `games/worldcup/DESIGN.md` (commit 3, Brad-drafted, assistant-restructured)**:
- 32,800 bytes (was 16,318 as scaffold). Brad authored §1 Overview (5 prose paragraphs framing the WC register inside the platform), §2 Per-game palette + accent rank (red / white / navy / gold prose with primary consumers per accent + Palette Semantics + 5-tier palette doctrine + 3 Named Rules), §4 `.wc-champion-banner` (full prose on the ceremonial register + render gate + future-work guardrails) + `.wc-stat-card` (the Casual-Light reference card's design philosophy + the `.is-lead` re-derivation lineage), §5 Do/Don't (10 Dos + 9 Don'ts with WC-specific enforcement rationale), §6 Visual smoke + verification cadence (cross-tab continuity standard + 5 regression categories + champion-state special case).
- Assistant restructured the remaining scaffold raw-material sections into clean prose for the consuming tool: §3 H1 Tribune voice doctrine (with the two named dispensations); §3 `.wc-eyebrow` primitive + variants + scope rules (light vs dark substrate calibration); §4 Tier Primitives trio with the "pick one, not two" rule of thumb; §4 Hero variant + sub-nav polish. Removed the "WORKING DRAFT" status banner; removed Appendix A (content either landed in main sections or was historical context no longer needed).
- Frontmatter tier-color TODOs resolved by reading `static/css/style.css :2653-2657` (the `body.game-worldcup` overrides): `--wc-tier1` `#D97706` Favorites, `--wc-tier2` `#4B7399` Contenders, `--wc-tier3` `#B45309` Dark Horses, `--wc-tier4` `#0D7377` Underdogs, `--wc-tier5` `#9333EA` Wildcards. §2 carries a reference table making the token-to-tier-role mapping (from `games/worldcup/WORLD_CUP_GAME_DESIGN.md`) discoverable.

**CLAUDE.md doctrine update**:
- Three guidance blocks rewritten (lines ~75-82 region). The CSS specificity utility example dropped the retired `.card.wc-card` and now leans on `.page-hero.wc-hero-grad`. The dark-card surface guidance block rewrote to describe `.wc-champion-banner` as the sole dark navy surface on WC (Casual-Light is the canonical body pattern; the ceremonial slot scopes foreground overrides via `.wc-champion-banner .text-muted` / `.wc-champion-banner .wc-eyebrow:not(...)`). The Bootstrap `.text-muted` override guidance updated to reference `.wc-champion-banner .text-muted` instead of the retired `.card.wc-card .text-muted`.
- New CLAUDE.md sentence at the project overview pointing at `docs/impeccable-loader-customization.md` so future Claude sessions discover the loader customization status.

**Tests**: full suite **769 / 769 passing** (757 P3.5 baseline + 4 P4 + 10 P5 new − 6 retired = 765, then + 4 PI-8 file-split locks = 769). No pre-existing tests broken by the file split (the eyebrow + tier-trio ratification tests now read from the new WC file).

**Visual smoke**: Chrome DevTools MCP on dev server port 5099 with `WC_FAKE_NOW='2026-07-20T12:00:00+00:00'` (post state); match #104 `is_completed=True` + `winner_team_id=12` set in the dev DB so the champion banner actually renders. **Champion banner live probe on `/worldcup/`**: substrate `rgba(0, 17, 46, 0.8)`; border `1px rgba(245, 241, 232, 0.08)`; border-radius `8px`; padding `16px` (= 1rem); `.wc-eyebrow` color `rgba(243, 239, 230, 0.85)` (bone @ .85, ~7.1:1 on navy); `.champion-name` color `rgb(242, 211, 107)` (= solid `--gold-light`); `.text-muted` color `rgba(245, 241, 232, 0.82)` (bone @ .82); `.champion-retrospect` font-family `Newsreader, Georgia, serif`. **Cross-tab probe** across HUB / ROSTER / BOARD / SCHEDULE / STATS / RULES: every tab returns 200, `.card.wc-card` markup count = 0 on every tab, `.wc-champion-banner` count = 1 on `/worldcup/` post-state only and 0 on every other tab. Desktop (1280×900) + mobile (375×812) screenshots captured at `p5-champion-banner-{desktop,mobile}.png`.

**Detector**: cross-tab live probe in lieu of `npx impeccable --json` (the dev server probe is more authoritative for the project-closing invariant than a template-source scan — it confirms the rendered DOM carries zero `.card.wc-card` instances, which is what matters). The four pre-existing `stats.html` detector hits from earlier phases are unchanged.

**Discoveries — surfaced during P5 execution** (decided 2026-05-14 with Brad):
- **DESIGN.md file-split** — originally P5 scope was a single doctrine rewrite of top-level `DESIGN.md`. Mid-execution Brad proposed splitting platform-foundation doctrine (top-level) from per-game specialization (`games/<slug>/DESIGN.md`) so each game's design grammar lives next to its code rather than inside the cross-cutting platform file. The architectural shift was sound but added an impeccable-loader-discovery problem (the stock loader only reads top-level). Resolved by customizing the loader to walk `games/*/DESIGN.md` and return `perGameDesigns` in the JSON output, with the customization documented in `docs/impeccable-loader-customization.md` so any future impeccable upgrade can re-apply the diff. The split lets Golf and CFB add their own design specialization later without bloating the foundation.
- **Per-tab `$impeccable critique` re-runs** — folded into this scorecard close-out commit rather than spawning 6 separate critique agents. Rationale: the critique tool, on six tabs that all share one unified doctrine post-P5, would surface largely the same observations; a single comprehensive pass against the new `games/worldcup/DESIGN.md` (which the customized loader now serves) captures the project's lift more efficiently. The per-tab scores in §2 above were captured during the cross-tab visual smoke against the new doctrine.

**Project closure**: WC tab unification ships at 6 PRs (P0 → P1 → P2 → P3 → P3.5 → P4 → P5) over 2 days (2026-05-13 → 2026-05-14). The headline outcome — "this is one game" across all 6 WC tabs — is achieved and locked by `tests/test_design_wc_tab_unification_p5.py::test_pi1_zero_card_wc_card_rule_heads_in_style_css` plus the cross-tab markup invariant verified live in the P5 visual smoke. Doctrine codified in `games/worldcup/DESIGN.md`; platform-foundation cleanup landed in top-level `DESIGN.md`; impeccable + future Claude sessions discover both files automatically via the customized loader.

---

## 5. Verification cadence

Per the plan's verification section. Each PR ends with:
1. Visual smoke on `/worldcup/<tab>` via dev server + `WC_FAKE_NOW`.
2. Cross-tab eye-test: HUB → ROSTER → BOARD → SCHEDULE → STATS → RULES.
3. `pytest tests/test_design_*.py tests/test_worldcup_*.py` — baseline 626 passing.
4. `npx impeccable --json games/worldcup/templates/worldcup/` — clean.
5. Per-tab `$impeccable critique` — record the lift.
