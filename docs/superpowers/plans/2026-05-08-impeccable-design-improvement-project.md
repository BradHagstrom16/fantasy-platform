# Impeccable Design Improvement Project — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended)
> For In line execution use: `superpowers:executing-plans`  Steps use checkbox (`- [ ]`) syntax for tracking. **The user manually `/clear`s between sessions; each session is designed to be self-contained.** Meticulously decide for a given task whether inline or subagent is better.

**Goal:** Apply `impeccable` design discipline to every public-facing CCC surface — every World Cup state (live > pre > post), all global chrome (auth, errors, base layout). Eliminate the systemic anti-patterns surfaced in the WC leaderboard exemplar critique (Tier 1 baseline) and execute per-page `critique` / `shape` / `clarify` / `adapt` work across each cluster, then run a final `polish` pass.

**Architecture:** Single multi-session plan structured as **Phases (P0–P6)** containing **Sessions (S\*.\*)**. Each session is a single Claude Code chat — context-isolated, prerequisites noted at the top of the session, deliverables and verification at the bottom. The user `/clear`s between sessions and points the new session at this plan plus the session ID. Phases break at meaningful milestones (cross-cutting fixes complete, a cluster complete, etc.) and each phase ends with a PR to keep review batches manageable.

**Tech Stack:** Flask 3 + Jinja2 + Bootstrap 5.3 + custom CCC tokens/components (`static/css/tokens.css` + `static/css/style.css`). Verification is **hybrid**: pytest source-pattern locks + Flask test-client HTML assertions for cheap CI regression, and the **Playwright MCP plugin** (`mcp__plugin_playwright_playwright__*`) for in-session computed-style probes, tap-target measurements, axe a11y scans, and visual smoke. Design discipline via `impeccable` skill v2.1.8, anchored to `PRODUCT.md` (register: product) and `DESIGN.md` (Tribune North Star).

---

## 0. Project overview

### 0.1 Surface in scope (~38 templates)

**Excluded entirely:** Golf and CFB blueprints (out of use per user direction). Their templates are not touched by any session in this plan.

**Live state surfaces (highest priority):**
- `games/worldcup/templates/worldcup/leaderboard.html` (Tier 1 exemplar — already critiqued; closing in P1)
- `games/worldcup/templates/worldcup/home_shell.html` + `_home_live.html`
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/team_detail.html`
- `games/worldcup/templates/worldcup/stats.html`
- `games/worldcup/templates/worldcup/player_detail.html`
- Live-bearing core/main partials: `_dossier_card.html`, `_fixture_card.html`, `_recent_results.html`

**Pre-live state surfaces:**
- `games/worldcup/templates/worldcup/_home_pre.html` + `_home_out.html`
- `games/worldcup/templates/worldcup/picks.html` + `_pick_row.html` + `_pick_accordion_script.html`
- `games/worldcup/templates/worldcup/join.html`
- `games/worldcup/templates/worldcup/rules.html`
- `games/worldcup/templates/worldcup/groups.html`
- Pre-bearing core/main partials: `_countdown_card.html`, `_ballot_card.html`, `_join_cta_card.html`, `_submit_picks_cta.html`, `_view_cta_card.html`, `_game_tiles_compact.html`, `_game_card.html`

**Post-live state surfaces:**
- `games/worldcup/templates/worldcup/_home_post.html`
- core/main partials: `_champion_banner.html`, `_dispatches.html`, `_commish_note.html`

**Global chrome / auth / errors:**
- `templates/base.html`
- `templates/errors/404.html`, `500.html`
- `core/auth/templates/auth/login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `change_password.html`, `profile.html`
- `core/main/templates/main/index.html`

**Admin pages:** explicitly out of scope per your direction during scoping. Add to a future plan if/when the admin UX needs the same treatment.

### 0.2 Priority order (locked from user direction)

1. **Live state** — leaderboard movement, results, in-progress games. Highest emotional density and highest user time-on-page.
2. **Global chrome / auth / errors** — important for first impression, low-frequency once a user is logged in.
3. **Pre-live state** — pick/join/rules. The acquisition and roster-craft window.
4. **Post-live state** — recap, champion, archive. Lowest interaction frequency but defines the closing emotional moment.

### 0.3 Phase structure (~22-26 sessions)

Phase ordering follows §0.2 priority. Live state goes first because it's the highest emotional density; global chrome is second because every page inherits it; pre-live and post-live follow. Final polish closes the project.

| Phase | Sessions | Focus | Output |
|---|---|---|---|
| **P0** Cross-cutting harden | 3 | Bootstrap shadow leak, side-stripe ban migration, mobile tap-target floor, white-on-gold contrast, em-dash sweep, table semantics | PR at end of phase |
| **P1** Leaderboard close | 1 | Shape Your Standing, trend rank-delta, clarify copy, mobile card-as-link, empty state | PR at end of phase |
| **P2** Live state cluster | 6 | home_shell+_home_live, schedule, team_detail, stats, player_detail, cluster polish | PR at end of phase |
| **P3** Global chrome + auth + errors | 4 | base layout, auth pages, errors, platform home | PR at end of phase |
| **P4** Pre-live state cluster | 5 | _home_pre/_home_out, picks, join, rules, groups, cluster polish | PR at end of phase |
| **P5** Post-live state cluster | 3 | _home_post + post-state partials, cluster polish | PR at end of phase |
| **P6** Final polish + scorecard | 2 | `$impeccable polish` across the surface, re-critique Tier 1 exemplars, document score lift | Final PR + merge `design/wc-polish` to `main` |

### 0.4 Backlog (living section)

Findings that surface during an iteration but don't fit its 3-5-priority-fix budget land here. Items are **routed by type**, not by who found them.

**Routing matrix** (assign one tag per item):

| Tag | What | Receiving session |
|---|---|---|
| `[in-surface]` | Fixable by editing files inside the discovering surface's scope. Default for findings an iteration didn't reach. | Next iteration of the same surface (`Sx.y.N+1`). |
| `[cross-cluster]` | Only visible when comparing two or more surfaces inside the cluster (e.g., visual rhythm between `_home_live` and `schedule.html`). | Cluster polish session: `S2.6` / `S3.4` / `S4.5` / `S5.3`. |
| `[cross-phase]` | Pattern spans multiple clusters (e.g., a chrome treatment repeating across pre/live/post home, auth, and game tiles). | `S6.1` cross-surface polish. |
| `[deferred-data]` | Requires real production data to surface meaningfully (e.g., tagline duplication only visible with N real users). | Revisit only when the trigger lands; no scheduled session. |
| `[ship-as-is]` | Documented decision not to fix, with written rationale. | Closed at write-time. |

**Format per item:**

```
- **[Sx.y.N tag]** <one-line description with file:line>. <why deferred>. <which session picks it up>.
```

**Convergence implication.** When an iteration converges (per §1.5b), every P1 finding it didn't fix must carry a routing tag with a specific receiving session. Untagged P1s block convergence by definition.

When the receiving session lands, sweep §0.4 for items tagged with that session ID and address them as the session's first agenda. Cluster polish sessions (S2.6 etc.) and S6.1 explicitly include this sweep as Step 0 of their task list.

The legacy "session ID that surfaced it" prefix (`[S0.2]`, `[S1.1]`, etc.) is preserved on all pre-iterative items below — they still tell you which work surfaced the finding.

- **[S0.2]** `groups.html:10` lead copy uses `&mdash;` HTML entity (`12 groups &mdash; 48 teams &mdash; 2026 FIFA World Cup`) — em-dash sweep target. Picked up by **S0.3**.
- **[S0.2]** `leaderboard.html:85` trend dash placeholder renders an em-dash glyph (`<span class="text-muted">—</span>`) — em-dash sweep target. Picked up by **S0.3**.
- **[S0.3]** `.navbar-brand` renders 68×38 at 375 viewport across every page (height-only fail, 6px short). Mobile-first 44×44 floor target. Self-contained CSS fix; defer to **P3 S3.1** (Global chrome) where the navbar is the focus.
- **[S0.3]** `/login` link rows ("Forgot your password?" 128×14, "Create an account" 116×37) fail the 44×44 floor. Self-contained auth-page CSS adjustment; defer to **P3 S3.2** (Auth surfaces).
- **[S0.3]** Navbar trophy CTA: chamber-purple text on `--metal-gold-flat` lands at 3.6:1 against the gradient's darkest stop (`--gold-dark` = `#8A6A1A`) at the bottom-right corner of the button. AA-passing across most of the surface (7.5:1 mid-stop, 12.4:1 lightest), but the worst-stop pixel-corner reads 3.6:1 — below the 4.5:1 normal-text floor. Fix requires retuning `--metal-gold-flat`'s dark stop in `tokens.css`, which is a DESIGN.md token spec change and out of scope for S0.3. Pick up in **P6 S6.1** (cross-surface polish) or as a one-off DESIGN.md spec session if a critique re-surfaces it earlier.
- **[S1.1]** `leaderboard.html` desktop table renders the Tiebreaker cell as the literal lowercase string `'none'` (`{{ e.usa_goals_guess if e.usa_goals_guess is not none else 'none' }}`) — breaks the editorial register. Use a voiced fallback like `No guess` or render an actual blank cell. Pre-existing; defer to **P6 S6.1** (cross-surface polish) unless an earlier deadline-related session reopens the leaderboard.
- **[S1.1]** Move column header (`<th scope="col" class="text-end">Move</th>`) gives no since-when context. Add a `title=` tooltip (e.g., "Change since yesterday's snapshot") on the header for the analyst register. Cheap progressive disclosure; defer to **P6 S6.1**.
- **[S1.1]** The Your Position tribune block sits on the bone canvas above the standings table with no visual thread between them — the gap reads as forgotten space rather than editorial breathing room. Candidates: a `border-top: 2px solid var(--gold)` rule above the table, or a section eyebrow ("THE LEDGER") above it. Defer to **P6 S6.1** so the cross-surface polish session can compare similar gap moments across the cluster (home dossier, schedule, team_detail) and pick a consistent treatment.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Home-live right column starved on desktop — ~700px void below the 4-line Commish note. Fixed by moving Recent Results out of the left rail and Commish out of the right rail into full-width rows below the dossier/leaderboard side-by-side; mobile reading order preserved via Bootstrap `order-*` utilities. Locked by `tests/test_design_p2_s2_1_2.py::test_home_live_recent_results_lives_outside_left_rail` + `..._commish_lives_outside_right_rail` + `..._mobile_order_preserves_dossier_results_leaderboard`.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Section "more" links (`.sec-head .more`) read at ~28px tall, below the 44×44 floor. Fixed via inline-flex + min-height/width 44px + negative-margin trick + focus-visible ring. Locked by `tests/test_design_p2_s2_1_2.py::test_sec_head_more_link_meets_44x44_tap_floor`.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Dossier-stamp `◈ Classified · CCC ◈` register-shift. Renamed to `◈ Council Filings · CCC ◈` (Tribune voice) and switched from `position: absolute` to in-flow `display: block; text-align: right;` (which also closes the mobile rank-meta overlap). Locked by `tests/test_design_p2_s2_1_2.py::test_dossier_stamp_drops_classified_register` + `..._no_longer_position_absolute`.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** "Also Today" eyebrow promised a temporal anchor the rows never delivered. Renamed to `Around the Tournament` (no time promise). Locked by `tests/test_design_p2_s2_1_2.py::test_results_also_eyebrow_does_not_promise_today_anchor`.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Mobile dossier-stamp positioning at `position: absolute` overlapped rank-meta on narrow viewports. Folded into PI-2 above (single CSS edit fixed both register and position).
- **[S2.1.1 in-surface] [S2.1.2 in-surface] DEFERRED to S2.1.3** Sparkline read-only in dossier card (`_dossier_card.html:33-99`) — no per-day rank reveal on hover/tap. Inherited from S2.1.1; not landed in S2.1.2 because the iteration's 3-5 cap absorbed the four higher-impact backlog items first. Receiving session: **S2.1.3** (delight pass; `$impeccable delight`). The convergence gate passed without it (heur 32/40 ≥ floor) so this is a Want, not a Need.
- **[S2.1.2 in-surface]** Sparkline lacks `aria-label` / `<title>` describing the trend; `rank-mvmt` carets are decorative-icon-with-hidden-text but not marked `aria-hidden="true"`. Surfaced by the S2.1.2 re-critique as soft P1s; both fit cleanly into the S2.1.3 a11y/delight pass alongside the per-day reveal. Receiving session: **S2.1.3**.
- **[S2.1.1 cross-cluster] [S2.6 routed]** Repeating gradient-card silhouette across 7 home components (dossier, view-CTA, commish-note-body, match-card, ballot-card, decree, join). S2.1.1 differentiated *match-cards on the live home* only; the broader silhouette pattern needs cross-state comparison. **Re-routed by S2.6:** the live cluster surfaces alone don't expose the pre/post home variants (`_home_pre` / `_home_out` / `_home_post`) — diversification can only be evaluated against all four state partials side-by-side. Re-routed receiving session: **S6.1** (cross-phase polish; compares across phases once P4/P5 surfaces have converged).
- **[S2.1.1 cross-cluster] [S2.6 routed]** Leaderboard rolls (`_home_live.html:46`) are non-interactive `<div>`s — no tap-through to competitor detail. Decision affects `/worldcup/leaderboard` (already shipped in S1.1) too; the `<a>`-vs-`<div>` choice should apply consistently across both surfaces. **Re-routed by S2.6:** wraps as anchors only makes sense once a competitor-detail / rivalry surface exists for them to link to (player_detail handles the "another player's standing" view, but the leaderboard rolls list opaque `display_name` strings without enrollment IDs threaded). Routing into S6.1 keeps the decision paired with the player_detail rivalry-comparison-strip work that S2.5.2 will add. Re-routed receiving session: **S6.1**.
- **[S2.1.1 deferred-data]** "Test1 / Test2 / Test3" tagline duplication (`_home_live.html:54` via `_tagline_for()` in `home_context.py:46-69`). Current finite-string set returns the same line for ranks #2 and #3. Production rotates per actual user; only visible with N real users in the standings. Revisit when production rotation is observed.
- **[S2.2.1 cross-cluster] CLOSED in S2.6** No jump-to-today affordance from above-the-fold on `/worldcup/schedule`. Closed by S2.6 PI-4: `.schedule-jump-today` pill chip rendered inside `.page-hero` linking to `#today`, guarded by `{% if (matchdays_group or [])|selectattr('is_today')|list %}` so it disappears pre/post-tournament when no today matchday exists. 44×44 tap floor + `:focus-visible` outline; gold-light hover lift. Live computed-style verification: chip 216×44, color `rgb(243,239,230)`, `min-height: 44px`, `href="#today"`. The team_detail "Recent" / stats "Today" anchor adoption noted in the original entry remains as future work; route forward to **S6.1** once team_detail and stats have a "today" / "now" anchor concept (currently they don't, so the affordance has nothing to link to). Locked by `tests/test_design_p2_s2_6.py::test_schedule_pi4_jump_to_today_anchor_in_hero` + `..._chip_meets_44_floor` + `..._has_focus_visible`.
- **[S2.2.1 cross-cluster] CLOSED in S2.6** Stage-count `<small>` in the schedule section headings used Bootstrap `.text-muted` (`#6c757d`) instead of the CCC tinted `--text-secondary` (`#5A5470`). Closed by S2.6 PI-3: dropped `text-muted` from the section-heading `<small>` (×2: Group Stage + the `render_stage` knockout macro), kept the `.schedule-stage-count` surface class, and added `color: var(--text-secondary)` to the existing `.schedule-stage-count` CSS rule. Live computed-style verification: `getComputedStyle(.schedule-stage-count).color === 'rgb(90, 84, 112)'` (`#5A5470`). The "Likely shared with similar `<small>` count helpers across live-cluster surfaces" concern surfaced only on `team_detail.html:145, 181` (no-fixtures empty state + path-to-crown explainer — both on the bone page background, not inside `.card.wc-card`), both folded into the same S2.6 PI-3. Locked by `tests/test_design_p2_s2_6.py::test_schedule_stage_count_pi3_no_longer_carries_text_muted` + `..._scoped_to_text_secondary` + `test_team_detail_pi3_empty_and_fineprint_surface_classes`.
- **[S2.2.1 ship-as-is]** Group-letter tag at upper-right of `.match-result-card` reads as a bare letter ("J", "I") to sighted users without prior context (the H1 "Group Stage" is far above when scrolled deep). `aria-label="Group X"` covers SR users; sighted users can still infer from the surrounding section. Lower priority than the Today affordance and not load-bearing for picks; defer until a future critique re-flags it.
- **[S2.2.1 cross-phase]** `.schedule-day-date` lacks `<time datetime="...">` semantics. Cross-page pattern (any page that prints a date should expose machine-readable form for screen readers, calendar extensions, and crawlers — `home_shell` time stamps, `team_detail` recent-result dates, `leaderboard` snapshot dates). Receiving session: **S6.1** cross-phase polish.
- **[S2.3.1 in-surface]** Owned-state celebration delta — full PI-3 ask (rank-among-picks + personalized voice in path heading, e.g., "Your roster's GER ceiling is 107.0, 4th-best in the Club"). The S2.3.1 atomic-edit pairing closed the eyebrow + gradient-variant minimum; the comparator requires a new `pick_ceiling_rank` route-level helper that joins `WorldCupPick` + `compute_path_to_crown` per enrollment, season-scoped via `WorldCupEnrollment.season_year` per the CLAUDE.md "WorldCupRankSnapshot aggregates must be season-scoped" pattern. Receiving session: **S2.3.2** (hero/path-section copy + new route data).
- **[S2.3.1 in-surface]** Projected-ceiling bare numeral. `team_detail.html:159` renders 749.0 / 107.0 with no group anchor — casual users have no calibration, analysts get no breakdown. Add a comparator chip (vs. median ceiling, vs. user's own picks) and progressive-disclosure detail (group-stage wins + R32 + R16 + QF + SF + Final base × multiplier). Same `pick_ceiling_rank` route data unlocks both. Receiving session: **S2.3.2**.
- **[S2.3.1 in-surface]** Pre-tournament state shell. `deadline_passed=False` + zero completed matches: hero shows `0.0 Tournament points`, ownership ribbon hidden, Match log of three TBDs, Path of one current + 5 future. *No copy* anywhere on the page says "the tournament hasn't started yet" — the page reads as broken rather than pre-roll. Mirrors the `core/main/home_context.build_home_context` four-state dispatcher pattern but team_detail has no equivalent state-shell. Receiving session: **S2.3.2** (route adds `state` flag; template branches on it).
- **[S2.3.1 cross-cluster] [S2.6 routed]** Eyebrow primitive saturation. `.wc-eyebrow` renders 9-14× per page on team_detail (hero pre-headline, hero stat labels, ribbon labels, fixture stage rows, path stage tiles, picker section). DESIGN.md §3 defines the primitive as "the small uppercase line above section headlines", singular. The new `.wc-meta-label` primitive (introduced in S2.3.1 for the hero stat caption) is a candidate for in-row labels but needs cluster-level review against home/leaderboard/stats/player_detail before promoting it. **Re-routed by S2.6:** the cluster-level decision on `.wc-eyebrow` vs `.wc-meta-label` would ratify a new primitive in DESIGN.md §3 — that ratification needs to compare usage across ALL phases (live + pre + post home, picks, rules, join, errors), not just the live cluster. Promoting prematurely from a live-only audit risks reverse engineering later when pre/post surfaces show different label needs. Re-routed receiving session: **S6.1** (cross-phase polish; ratifies primitive scope after every surface family has rendered through at least one iteration).
- **[S2.3.1 ship-as-is]** Bottom-of-page back-link. `team_detail.html:44` carries the only "Back to Board" affordance; on a long mobile scroll the user must scroll back up to navigate out. Lower priority than the comparator + state-shell work; defer until a future critique re-flags it.
- **[S2.3.1 ship-as-is]** Three "1.0" tokens stacked in a 90px band on tier-1 mobile (multiplier == 1.0). Visual coincidence on tier-1 teams (no analyst tension to surface); copy could elide the "× Multiplier 1.0" prose when multiplier == 1, but the canonical Base × Multiplier reading is consistent and honest. Defer until a future critique re-flags it (likely S2.4 multiplier-explanation revisit).
- **[S2.4.1 in-surface]** T1 amber tier badge at `static/css/style.css:3417` (`.wc-tb-1 { background: var(--wc-tier1); }` = `#D97706`) renders white-on-amber at **3.19:1** at 10.88px bold — sub-AA (4.5:1 floor for small bold text). The other four `.wc-tb-N` variants pass AA (4.99–5.62:1). The cleanest fix is a shared tinted-bg + dark-text pattern across all five badges (parallel to the existing `.wc-still-in` pattern: `background: rgba(token,.15); color: dark-token; border: 1px solid rgba(token,.4)`); the alternative is a token retune of `--wc-tier1` (DESIGN.md spec change, also affects chart palette + pick-bar fills). S2.4.1 deferred because either fix is bigger than a same-iteration P2 — token retune touches DESIGN.md tokens, shared variant touches all five badge classes + visual rhythm across the surface. Receiving session: **S2.4.2** (in-surface, dedicated badge variant work).
- **[S2.4.1 in-surface]** Phase-aware editorial copy on stats masthead. The Board's masthead derivation prose ("X leads the field with Y pts. Z oaths sealed across N nations still standing.") is currently hard-coded for live-state. Pre-deadline ("Vault opens Jun 11"), post-tournament ("Champion sealed Jul 19"), and "no completed matches yet" need branched copy via `current_phase` + `kpis.top_country_score > 0`. Routes-side plumbing minimal (already pass `current_phase`); just template-side `{% if %}/{% elif %}` branches on the prose line. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** No "my picks only" filter affordance on the Field tab's Popularity vs. Score bubble chart. Analyst persona red flag — they want to isolate their own roster against the field. Bubble chart datasets are tier-grouped (5 datasets); a sixth filter dataset that toggles "MY_PICKS only" would land cleanly. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** Carrying the Field + Dead Weight stack vertically inside the right rail at desktop (`.col-xl-4 .d-flex.flex-column`). Adjacent comparison is the analyst's primary use of these two lists; vertical stacking forces them to scroll between. Side-by-side on `>= xl` would close it. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** Tier 2 Pairs absence on the By Tier tab. `get_tier_combos()` deliberately excludes tier 2 (only 1 T2 pick per player → no pairs). The Tier Pairs section silently drops T2 with no explanatory line; an analyst reads it as a data bug. A one-sentence inline note ("Tier 2 has no pairs — only one T2 pick allowed.") would defuse the ambiguity. Receiving session: **S2.4.2**.
- **[S2.4.1 cross-cluster] [S2.6 routed]** Inline-style Teko declarations duplicated ~25× across `stats.html` JS render functions (`font-family:'Teko',sans-serif;font-size:.7rem;...`). Pattern likely shared with other JS-rendered surfaces (home _home_live impact rows, leaderboard mobile cards). Extract to a `.wc-microcaption` utility set after auditing cross-surface usage. **Re-routed by S2.6:** the S2.6 grep surfaced **0** inline Teko declarations in `_home_live.html` and `leaderboard.html` — the only verified additional inline-Teko surfaces are P4 pre-live templates (`picks.html`, `rules.html`, `join.html`, 11+ instances combined). Extracting a `.wc-microcaption` utility now would consolidate stats.html alone, then need a second migration pass when the P4 surfaces are touched. Re-routed receiving session: **P4.5** (pre-live cross-cluster polish, after picks/rules/join converge), so the extraction lands once and matches the actual cross-surface usage.
- **[S2.4.1 cross-cluster] CLOSED in S2.6 (decided no-op)** `.wc-stat-card` carries both `box-shadow: var(--shadow-sm)` AND `border: 1px solid var(--border)` — double elevation. Original entry asked "pick one." **S2.6 verdict: keep both.** DESIGN.md §4.4 "The Lift-At-Rest Rule" explicitly mandates `--shadow-sm` at rest on cards ("Flat-at-rest is the wrong elevation philosophy for CCC; the Tribune is a printed object, not a wireframe") and DESIGN.md §6 defines the canonical `.card` primitive as "`var(--bg-card)` (white) fill on a Pressroom Bone page, `--radius-lg` corner radius, `1px solid var(--border)` border, `--shadow-sm` at rest, `--shadow-md` on hover with `translateY(-3px)` lift." `.wc-stat-card` and `.your-standing-tribune` both follow that primitive contract. The generic impeccable "single-encoding of elevation" heuristic is overridden by the committed DESIGN.md policy (per impeccable's own priority rule: user instructions > skill heuristics). If a future critique re-flags this, point to this §0.4 entry and DESIGN.md §4.4 / §6.
- **[S2.4.1 cross-phase]** Tournament-progress phase labels in `stats.html:302` use markup-as-icon (`✓` for done, `←` for current) without `aria-label`. Screen readers speak "check" / "left arrow", not "completed" / "current". Same pattern likely on home progress widgets (`_home_live` / pre-state countdown) and any future post-state recap progress bar. Receiving session: **S6.1** cross-phase polish.
- **[S2.4.1 ship-as-is]** Phase chip in stats hero shows "Pre-Tournament" even with `WC_FAKE_NOW` set to mid-group-stage — backend artifact (no completed matches in dev DB → `_derive_tournament_phase()` returns `pre_tournament`). Won't surface in production where match data is live. Won't be re-flagged.
- **[S2.4.1 ship-as-is]** `.wc-still-in` "Active" green chip + `.wc-tb` orange tier badge of equal size and weight in Top Scorers row split visual attention. Lower priority than the comparator + state-shell work; defer until a future critique re-flags it.
- **[S2.5.1 in-surface]** Rivalry comparison strip (you vs them). The S2.5.1 hero re-shape closed the *voice* dimension of rivalry framing (Newsreader derivation prose carries "Leads the table. 117.0 ahead of next." / "Trails leader by X, Y ahead of next."), but the structural you-vs-them comparison strip below the eyebrow line — `<viewer> trails <target> by <delta> · <N> shared picks · their edge: <team> (+<pts>)` — needs a new route-level helper `compute_comparison(viewer_enrollment, target_enrollment) -> {viewer_total, target_total, delta, shared_picks, their_advantage, your_advantage}` joined per `WorldCupPick` + season-scoped via `WorldCupEnrollment.season_year`. Suppress the strip when `viewer == target` or when viewer is logged out. Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** "Roster sealed" pre-deadline empty-state re-shape (`player_detail.html:124-136`). Current implementation is a Bootstrap icon-stack: 2.5rem bi-lock-fill at opacity .7 + `Roster sealed` eyebrow + "Picks are hidden" h5 + 2-line muted paragraph with deadline_ct. The S2.5.1 admin-session probes bypassed `picks_visible = deadline_passed or is_owner or is_admin`, so this branch was not visually rehearsed; the icon-on-navy at .7 opacity will read marginal, and the empty-state apologizes rather than rewards participation (PRODUCT.md Design Principle "Empty states reward participation"). Re-shape options: editorial "Sealed envelope" / "Locked in the vault until kickoff" frame, target avatar + name as dominant element, countdown when deadline within 7 days, replace low-opacity icon with Teko "SEALED" eyebrow or "9 PICKS LOCKED" numeric chip. Requires an un-priv viewer probe (logout + visit another player's `/worldcup/leaderboard/<id>` pre-deadline). Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** Above-fold density / wrapper reduction. The picks table currently sits at y≈481 on a 1470×900 viewport (probed) — the `.page-hero.wc-hero-grad` consumes ~280px, then `.container > .row.justify-content-center > .col-lg-8 > .card.wc-card.wc-card-flush > .card-body.p-0 > .table-responsive > <table>` adds 6 layers of wrapper before the table renders. Most of the 9 picks sit below the fold. Targeted fix: scope `.page-hero` padding compaction to player_detail (e.g., page-specific class on the hero or a `.page-hero.is-comparison` modifier) without touching the platform default; collapse `row > col-lg-8` to a `.container-md` or `max-width: 880px` inner block. The platform-global `.page-hero` padding is OUT of scope for this surface — never edit it from a per-surface iteration. Receiving session: **S2.5.2**.
- **[S2.5.1 cross-cluster] CLOSED in S2.6** Bootstrap-on-`.card.wc-card` contrast leak is a cluster-wide latent risk. The original entry routed "either lock the white-td assumption or extend the counter-rule." Closed by S2.6 PI-1: **locked the white-td assumption**. Bootstrap 5.3 supplies the white td bg via `--bs-table-bg: var(--bs-body-bg)` (default `#fff`), but the assumption was implicit. Added `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` directly above the cluster-3 surgical-exclusion at `style.css:~5485` so the masking becomes a CCC-owned design decision rather than an implicit Bootstrap default. The original `.text-muted` surgical exclusion stays intact (it now rests on a guaranteed-white substrate). Surfaces that want dark navy bleed-through still opt out via their own scoped `background-color: transparent` on `> tbody > tr > td` (see `.card.wc-card.player-picks-desktop` overrides at `style.css:2385-2416`). Live computed-style verification: leaderboard table cell `--bs-table-bg = #FFFFFF` (light substrate, fix wins) and player_detail picks table cell `--bs-table-bg = #FFFFFF` but explicit `background-color: transparent` from the S2.5.1 opt-out wins at the property level (dark substrate preserved). Locked by `tests/test_design_p2_s2_6.py::test_card_wc_card_table_pi1_locks_bs_table_bg_to_bg_card` + `..._surgical_exclusion_still_present`.

---

## 1. Cross-session conventions

These apply to every session unless overridden in-session. Read them once; sessions reference them by name.

### 1.1 Branch and commit strategy

- All sessions commit to `design/wc-polish` (the existing worktree branch). The branch is **dedicated to impeccable design work** for the remainder of the project — no interleaving feature work, no merges from main except to resolve conflicts, no June 1 hard merge deadline. Quality > velocity.
- Commit per logical unit within a session (often 1-3 commits per session). Squashing to one commit per session is allowed if the session's work is genuinely atomic.
- **PR cadence**: open a PR at the **end of each Phase**, not per session. PR title format: `Impeccable PN — <phase name>`. PR body summarizes per-iteration deliverables, lists impeccable findings closed, and links to before/after screenshots. Per-phase PRs land on `main` as the work progresses (P0 PR #11 + P1 PR #12 already merged); the final state at P6 close is also on `main`. After P6 close: production deploy + Brad runs the full production-launch test script and applies any production-only adjustments directly on `main`.
- Commit messages follow conventional commits (`fix:`, `feat:`, `style:`, `refactor:`, `test:`, `docs:`). For impeccable work, prefer `style:` for visual changes, `fix:` for a11y/contrast/correctness, `refactor:` for migrations (side-stripe, shadow), `feat:` only when a genuinely new component or capability lands.
- Tag @CodeRabbit AI Review so CR can review the code

### 1.2 Skill and command usage

- Every session begins with the user (or the agent on their behalf) invoking `Skill { skill: "impeccable" }`. The skill loads PRODUCT.md and DESIGN.md context. Failure to do any of the 3 is unacceptable. Every session and/or agent MUST invoke impeccable, fully read PRODUCT.md, and fully read DESIGN.md. 
- **Sub-agent skill-invocation proof is mandatory.** When dispatching a sub-agent that runs any impeccable workflow (critique, audit, polish, shape, etc.), the prompt MUST require the sub-agent to (a) invoke `Skill { skill: "impeccable", args: "<command> <target>" }` as its first action, (b) run the loader (`node ~/.claude/skills/impeccable/scripts/load-context.mjs`), and (c) read the matching `~/.claude/skills/impeccable/reference/<command>.md` reference file plus any references that file links to (e.g., `heuristics-scoring.md`, `cognitive-load.md`, `personas.md` for critique). The prompt MUST require **content-fingerprint proof** at the top of the agent's reply: short verbatim quotes from each loaded file (e.g., a unique line from `SKILL.md`, the row beginning `| **P0** |` from `heuristics-scoring.md`, a line from `PRODUCT.md` and `DESIGN.md`). If the fingerprints aren't quoted, the report is invalid — discard and re-dispatch. **Why this rule exists:** prior sessions burned 100k+ tokens on agents that claimed gate-pass without observable Skill invocation; the design laws came from the prompt context, not the skill, so the critique was effectively the orchestrator critiquing itself in someone else's voice. Never quote DESIGN.md / PRODUCT.md content into a sub-agent prompt as a substitute for making the agent load them — that defeats the impeccable discipline. Pass paths, require loads, demand fingerprints.
- Sub-commands are invoked by writing `$impeccable <command> <target>` in chat. The skill routes to the relevant reference file.
- For cross-cutting hardens, use `$impeccable harden <surface>` with `<surface>` as a description of the systemic issue (e.g., `$impeccable harden bootstrap-shadow-leak across all .card.wc-card`).
- For per-page work, the typical session pattern is:
  1. `$impeccable critique <page>` — produces a Combined Critique Report with priority issues + recommended commands. The Tier 1 leaderboard run already exists; for new pages this is the first major step.
  2. Execute the recommended commands one by one (`$impeccable shape <component>`, `$impeccable clarify <copy target>`, `$impeccable adapt <responsive target>`, etc.).
  3. Re-run `$impeccable critique <page>` at the end to confirm score lift.
- "A step" in this plan can take 30-60 minutes of agent work when the step is "run $impeccable critique" (which spawns sub-agents and runs detectors). That's expected; the writing-plans bite-size rule is relaxed for design-work steps.

### 1.3 Verification strategy (hybrid: source locks + Playwright MCP + critique re-run)

Three layers per session. Each catches a different category of regression. Use them together; none is sufficient alone.

**Layer A: Source-pattern locks (pytest, fast, CI-friendly).**

- For things whose **source presence/absence is the violation**: em-dashes in user copy, `border-left: Npx` rules, missing `scope="col"` in rendered HTML, missing `role`/`aria-label` on regions. Source-grep style.
- Two flavors:
  - **CSS-source assertions**: open `static/css/style.css` as text and assert presence/absence of patterns. Example: `assert 'border-left: 3px solid var(--game-accent)' not in css_source` after side-stripe migration. Fast, deterministic, no browser.
  - **Rendered-HTML assertions**: Flask test client renders a representative page; substring/regex checks on response body. Example: `assert b'<th scope="col">' in resp.data` for table-semantics fixes.
- Tests live under `tests/test_design_<phase>_<topic>.py`. Each session adds its own file or appends to an existing one.
- `ENVIRONMENT=testing venv/bin/python -m pytest tests/` must pass at the end of every session.

**Layer B: Playwright MCP — in-session computed/visual verification.**

- For things whose **rendered or computed value is the violation**: Bootstrap utility leaks (the gray `box-shadow` we'd never write in `style.css` but Bootstrap CDN does), tap-target rectangles at 375 viewport, contrast at the actual rendered color stack (not the source-declared color), focus-ring presence, focus-trap order, axe a11y violations.
- Use the Playwright MCP plugin (`mcp__plugin_playwright_playwright__*`) live during the session. The agent navigates the dev server, evaluates JS to read computed styles or bounding rects, runs axe (`npm exec axe-core` or via injected script), records findings.
- These checks are **session-time gates**, not pytest tests. They prove the fix worked at session end; they don't re-run in CI. The reasoning: visual regression infrastructure (pytest-playwright + browser install + live-server fixture) is a heavier investment than this project warrants — the next critique re-run (Layer C) catches anything Layer B would miss in CI.
- Required Playwright MCP probes per session type:
  - **Cross-cutting harden**: probe the specific computed value the harden targets (e.g., `box-shadow` of `.card.wc-card`, `min-height` of `.subnav-pill`, contrast of trophy CTA hover).
  - **Per-page** (P1, P2.x, P4.x, P5.x): take desktop + 375 mobile screenshots, run `axe-core` against the page, probe any computed styles flagged in the critique.
- When the Playwright MCP isn't available for some reason, the chrome-devtools-mcp plugin (`mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`) covers the same ground — pick whichever is available.

**Layer C: Holistic critique re-run (impeccable, end-of-session for per-page sessions).**

- After per-page execution, re-run `$impeccable critique <page>` and compare the new Design Health Score / Audit Health Score / Anti-Patterns count to the baseline. Record the delta in the session's commit message (e.g., `Critique: 23/40 → 31/40, audit 11/20 → 16/20, anti-patterns 5 → 1`).
- Cross-cutting harden sessions are scored against the leaderboard exemplar (re-run `$impeccable critique leaderboard` if the harden was meant to fix one of its findings).
- The critique re-run IS the visual-regression net for CI-skipped Layer B work. If Layer B passed at session-end and Layer C scored a lift, the work landed.

**Decision rule (which layer for which finding):**

| Finding type | Use |
|---|---|
| Source-pattern ban (em-dash, side-stripe rule, hard-coded hex) | **Layer A** (source grep) |
| Rendered-HTML structure (`scope="col"`, `<caption>`, `aria-label`) | **Layer A** (Flask test client) |
| Computed style of an element (`box-shadow`, `font-family`, `color`, contrast) | **Layer B** (Playwright MCP) |
| Tap-target rect / overflow / responsive-collapse | **Layer B** (Playwright MCP) |
| Axe a11y scan | **Layer B** (Playwright MCP, axe injected) |
| Holistic visual / brand fit / hierarchy | **Layer C** (`$impeccable critique` re-run) |

### 1.4 How to start a session

The user `/clear`s, then opens a fresh chat with prompt template:

```
Resuming the impeccable design improvement project. Plan:
docs/superpowers/plans/2026-05-08-impeccable-design-improvement-project.md.
Execute Session <ID> only. Do not run subsequent sessions in this chat.
```

The agent's first three actions in any session:

1. Invoke `Skill { skill: "impeccable" }` — loads context and design laws. Reads PRODUCT.md and DESIGN.md.
2. Read this plan, find the targeted session, read its full block.
3. Read every file listed under the session's "Files in scope (READ)" before any edit.

### 1.5 How to end a session

Every session ends with the same seven steps:

1. **Run pytest**: `ENVIRONMENT=testing venv/bin/python -m pytest tests/` — must be green.
2. **Take after-screenshots** of any visually-changed pages at desktop (1470×900) and mobile (375×812). Save under `.impeccable-review/<session-id>/`. Add `.impeccable-review/` to `.gitignore` if not already (one-time, in P0 S0.1).
3. **Re-run impeccable critique** for any page touched (per-page sessions only). Record score delta in the commit message body.
4. **Commit** with conventional-commits prefix and a summary that names the session ID.
5. **Flip every checkbox you completed.** This is non-negotiable. Sweep the session's `**Step N: ...**` list and turn each finished `- [ ]` into `- [x]` in the same commit. Then update the §9 rollup (mark the session row `[x]` and fill in its commit hash). When you open a phase PR, fill in the `**PR PN** opened:` row with the PR number and check it.
6. Append any newly-found out-of-scope items to the Backlog (Section 0.4) with the session ID that surfaced them.
7. If any session findings would be beneficial for future sessions, update this document accordingly so future sessions and phases go smoothly. Usage of the remember skill is also encouraged.

### 1.5b Iteration convergence gate (per-surface sessions only)

A per-surface session (S2.1, S2.2, S3.1, S4.x, etc.) **iterates** until the surface converges. Each iteration is its own session, suffixed `.1`, `.2`, `.3` (so S2.1 fans into S2.1.1, S2.1.2, ...). After every iteration's end-of-session critique re-run, check convergence. If any one of the four gates below fails, `/clear` and start the next iteration.

A surface is converged when **all four** are true:

1. **Zero P0 issues** in the latest `$impeccable critique` re-run on this surface.
2. **Zero P1 issues**, OR every remaining P1 carries a written deferral rationale that names its receiving session (a specific cluster polish session like S2.6, the cross-phase polish S6.1, a dedicated future iteration `Sx.y.N`, or `[deferred-data]` if it requires real production data to surface). The rationale lives in §0.4 Backlog with the routing tag.
3. **Anti-pattern hard hits = 0** in the latest critique. (Hard hits = impeccable absolute-ban violations + DESIGN.md §6 Don't violations. Soft observations don't count.)
4. **One of the following score gates** holds:
   - (a) Heuristics ≥ 32/40 (the "consistently good" bar — most heuristics scored ≥ 3, which means "real-world acceptable; some heuristics scored ≥ 4 = excellent").
   - (b) Heuristics ≥ baseline + 6 (the "you've moved this surface materially" gate, for surfaces that started low — e.g., a 22/40 baseline converges at 28/40 if asymptotic).
   - (c) Two consecutive iterations land within 1 point of each other (the "asymptotic" gate — the surface has hit its ceiling for now; further iteration is sub-marginal). **First-iteration exclusion**: this gate compares iteration N's score to iteration N-1's score. The first iteration of any surface (`Sx.y.1`) cannot trigger asymptotic by definition — there's no prior iteration to compare to. A first iteration relies on (a) or (b) only.

The four gates carry equal weight. **Anti-perfectionism note**: if all four pass and Claude's instinct is "we could keep going," stop anyway. The signal that a surface is done is the gate, not Claude's appetite for more findings.

**Iteration naming convention.** The first per-surface session is `S<phase>.<surface>.1` (e.g., S2.1.1, S2.2.1). Each subsequent iteration of the same surface is `.2`, `.3`, etc. The §9 rollup gets one row per iteration, each with its own commit hash + score delta. Earlier sessions completed under the original "one session per surface" model (S0.1, S0.2, S0.3, S1.1, the initial S2.1 commit `e69966f`) keep their original IDs and are treated as "iteration .1" of their respective surfaces — if they're re-opened later, the next iteration is `.2`.

**What an iteration session looks like.** Same per-session pattern as §4 (boot dev server → before-screenshots → critique → triage 3-5 priority fixes → execute → tests → after-screenshots → re-critique → commit → check convergence gate). The 3-5 priority-fix budget per iteration stays in force; the iterative model means **more iterations**, never bigger ones.

**Budget bookkeeping (calibrated against S2.1.1 experience):**

- **The 3-5 cap counts Priority Issues, not total edits.** A "Priority Issue" is anything the critique flagged as P0/P1/P2 with its own what/why/fix. Mechanical scope (an issue that requires editing 3 CSS rules + a template + a test) is one Priority Issue, not five edits.
- **Atomic-edit rule.** When two semantically distinct backlog items resolve to the same atomic edit, count them as **one** Priority Issue. Calibrated against S2.1.2: PI-2 combined "dossier-stamp register-shift" (`◈ Classified · CCC ◈` reads as spy register) with "mobile dossier-stamp position collision" (the absolute-positioned stamp overlapped rank-meta on narrow viewports). Both close in a single rewrite of the `.dossier-stamp` rule plus a one-token text change. Counting them as two Priority Issues would have inflated the cap without producing distinct work; counting as one keeps the cap honest. Watch out for the inverse failure mode — combining items that *aren't* actually atomic ("we'll fix the rail layout AND the sparkline a11y in one PI") hides scope creep behind the rule.
- **Polish freebies don't count against the cap.** A "freebie" is <2 minutes of work, single file (or one CSS rule), with at most one source-pattern lock. Examples from S2.1.1: removing `&ndash;` from one byline; renaming "competitors" → "in the Club"; bumping `.ra-stage` opacity .45→.55 to clear AA. Cap freebies at ~3 per iteration; batch them at end-of-iteration so they don't fragment the main work.
- **Iteration 2+ inherits its own backlog.** Items tagged `[Sx.y.N-1 in-surface]` in §0.4 already passed Priority-Issue triage; they count toward the 3-5 cap of the picking-up iteration. If 6 backlog items exist and a fresh critique adds 2 more, the iteration picks the highest-value 3-5 and routes the rest forward to `Sx.y.N+1`. Inherited-backlog iterations typically spend 4 of the cap on backlog and 0-1 on fresh findings (calibrated against S2.1.2: 4 of 6 inherited items closed, 2 routed forward, 0 fresh items added).
- **Soft total-edit ceiling.** ~8-10 distinct edits per iteration is the comfort line where session quality starts degrading. If a session blows past that, the next iteration is right around the corner — bank the work and `/clear`.

**Layout patterns the iterative model has surfaced (extend as future iterations add to this list):**

- **Bootstrap `order-*` is the canonical "mobile reading order vs desktop balance" tool.** When a desktop layout reshape would shuffle the mobile reading order out of intent, use Bootstrap order utilities (`order-2`, `order-3`, `order-lg-0`, etc.) on the row's children rather than introducing duplicate templates or breakpoint-specific includes. Pattern lock: see `_home_live.html` post-S2.1.2 — the four primary blocks (`home-live-left` / `home-live-right` / `home-live-results` / `home-live-narrative`) sit in a single `.row` with mobile order `0/3/2/4` and desktop order `0/0/0/0` so source order drives the desktop grid while the mobile stack reads dossier → results → leaderboard → commish.
- **The hero-metric-template ban applies to *adjacency*, not just presence.** Four equal-weight numerals in a row (Tier · Multiplier · Base · Scored, each at `1.6rem`) reads as the SaaS cliché DESIGN.md §6 bans even when each tile carries a distinct, justified data point. Surfaced by S2.3.1: the team_detail masthead avoided gradient-text and the literal big-number-small-label trap, but four side-by-side `1.6rem` numerals + small Teko labels still triggered the persona "AI made that" reflex. The escape pattern: collapse to one dominant numeral (Scored at `2.6rem`), one supporting chip (multiplier ×N), one prose derivation line (Base × Multiplier as Newsreader microcopy). Then the hero reads as editorial masthead, not stat strip. Apply this on every CCC surface that's tempted toward 3+ equal-weight stat tiles — the home dossier, player_detail hero, stats overview KPIs, post-state champion banner.
- **Bootstrap `.text-muted` on dark `.card.wc-card` substrates always fails AA.** `#6c757d` against `rgba(0, 17, 46, .8)` is sub-AA. Surface-scoped class migration (`.fixture-stage-date / .fixture-vs / .fixture-tbd / .ownership-ribbon-blurb`, each tinted toward `--bone-mute`) is now the canonical pattern, established in S2.3.1's PI-4 freebie. Future iterations on dark-card surfaces (`.card.wc-card .* .text-muted`) should sweep this proactively instead of waiting for the critique to surface it.

**Backlog routing within an iteration.** When a critique surfaces an in-scope P0/P1 outside the iteration's 3-5 budget, route it to the next iteration of the same surface. When it surfaces a cross-cluster pattern (visible only when comparing two or more surfaces in the cluster), route to the cluster polish session (S2.6 / S3.4 / S4.5 / S5.3). When it surfaces a cross-phase pattern (visible only when comparing across phases), route to S6.1. The §0.4 Backlog rules in this plan have the precise routing matrix.

### 1.6 Out-of-scope guardrails

- **Don't touch Golf or CFB.** They're explicitly excluded.
- **Don't touch admin templates.** They're explicitly excluded.
- **Don't introduce new design tokens** without a spec session. CCC tokens live in `tokens.css` and additions need explicit DESIGN.md updates.
- **Don't refactor business logic** as a side effect of design work. If a route handler needs to change shape to support a UI fix, scope it minimally and call it out in the commit message.

### 1.7 Failure mode: critique surfaces something we hadn't planned for

If a per-page critique surfaces a P0 or P1 issue that doesn't fit the iteration's 3-5-fix budget:

1. **Don't push past it.** The 3-5-per-iteration cap is load-bearing — exceeding it produces lower-quality fixes and a session-end critique that doesn't reliably show whether each fix landed.
2. **Route the finding via §0.4 Backlog** using the routing-by-type rules at the top of §0.4. The most common routings:
   - **In-surface** (the finding is fixable by editing files inside this surface's scope) → next iteration of the same surface (`Sx.y.N+1`). Default for findings the iteration didn't reach.
   - **Cross-cluster** (the finding is only visible when comparing two or more surfaces in the same cluster, e.g., visual-rhythm consistency between `_home_live` and `schedule.html`) → cluster polish session (`S2.6` / `S3.4` / `S4.5` / `S5.3`).
   - **Cross-phase** (pattern spans multiple clusters, e.g., the 7-component gradient-card silhouette repeating across pre/live/post home + auth + game tiles) → `S6.1` cross-surface polish.
   - **Production-data-dependent** (the finding requires real user/match data to surface meaningfully) → tag `[deferred-data]` in §0.4; revisit only when the trigger lands.
3. **Convergence not assumed.** A session that surfaces a P0/P1 it can't fit is **not converged** — §1.5b gate #1 or #2 will block. The next iteration of the same surface picks the deferred item up. This is the default loop, not a special case.
4. **Same-iteration handling allowed only if cheap.** If a self-contained fix takes <10 minutes and doesn't bump the iteration past 6 priority fixes, fold it in. Don't stretch the iteration to chase a P2 that turned into a P1 mid-session — defer to the next iteration.

### 1.8 CR-feedback-approval sessions

A phase-work session does not end with the merge — it ends with PR open. Once a phase PR is open, the cycle shifts to a distinct session type dedicated to CodeRabbit feedback approval. Do NOT bundle CR iteration into the next phase's session; treat it as its own discipline.

The cycle:

1. **Phase-work session(s)** complete. PR is open per §1.1.
2. **`/clear`** — context isolation between every session, per §1.4.
3. **CR-feedback-approval session.** Skills loaded first thing: `Skill { skill: "impeccable" }` (so design laws stay binding when CR flags style/token/spec issues) + `Skill { skill: "superpowers:receiving-code-review" }` (technical rigor over performative agreement; push back when CR is wrong). The session's only purpose is to:
   - Triage every actionable CR finding on the latest commit.
   - Verify each against current source before changing anything.
   - Implement valid fixes, push back on incorrect ones with technical reasoning.
   - Reply on each inline thread (`gh api ... pulls/<n>/comments/<id>/replies`) — fix-confirmation OR pushback rationale.
   - Run pytest green; commit; push.
4. **Repeat step 3** if CR returns more findings on the new commit. Each round is its own session — `/clear` between them if context grows large.
5. **Approval gate.** The phase is ready to merge when **both** CR and Claude approve:
   - **CR approval**: latest CR review state is `APPROVED`, or no findings posted on the latest scan.
   - **Claude approval**: pytest green, every CR finding either implemented or has a posted technical pushback you genuinely believe in. Performative "looks good" doesn't count.
6. Then `/clear` and start the next phase-work session.

Why this is its own session type: phase-work and CR-iteration require different mental models. Mixing them dilutes both — phase work loses focus, and CR iteration loses the receiving-code-review discipline (verify, evaluate, push back when wrong). Per `feedback_cr_approval_sessions.md` in user memory.
4. Add a note in the session's "Handoff" block.

### 1.8 Impeccable is the source of truth — the plan is scaffolding

This plan was written **before** most of the surfaces in scope had been critiqued. Its specifics for P2–P5 are educated guesses, not ground truth. The leaderboard's per-page priority issues were ground truth for P1; the cross-cutting findings are ground truth for P0. Everything beyond that is a starting point for the agent's actual critique work.

When the plan and impeccable findings disagree, **impeccable wins**. The agent's job in any per-page session is not to execute pre-specified edits — it's to:

1. Run the impeccable workflow (`$impeccable critique <target>` or the relevant sub-command).
2. Trust the resulting report.
3. Execute against the report's Priority Issues and Recommended Actions.
4. Update this plan if the truth surfaced is durable enough to benefit future sessions.

**Deviations from the plan are expected and welcome.** Specific examples of legitimate deviation:

- The plan predicts a per-page session will surface ~3 priority issues; the actual critique surfaces 7. → **Adapt scope.** Take the top 3-5 in this session per §1.7; backlog the rest. Do not push all 7 in one session.
- The plan suggests a specific impeccable command for a finding (e.g., `$impeccable clarify`); the critique recommends a different command (`$impeccable shape`). → **Trust the critique.** It saw the surface; the plan didn't.
- The plan's Priority Issues for a future session don't match what the actual critique surfaces. → **Trust the critique.** Update §0.4 (Backlog) and the affected session's notes.
- A regression test pattern in the plan turns out to be brittle for this codebase. → **Replace it.** Don't twist the codebase to fit the test pattern.
- A pattern locked in CLAUDE.md or an existing memory file conflicts with a critique finding. → **Surface the conflict to the user via `AskUserQuestion`.** Don't unilaterally override CLAUDE.md or invent a new rule.

**Plan-update mechanics during execution:**

- Append new findings to §0.4 Backlog with the discovering session ID.
- If a session discovers a fact that future sessions need (e.g., "the rank-delta helper actually lives at `services/snapshots.py`, not `services/ranking.py`"), edit the affected future-session block in the plan to reference the correct file.
- If a phase's session inventory is wrong (a session needed for a critical surface was missed; a planned session is no longer needed), insert/remove sessions and renumber. Update §9 checklist accordingly.
- Use the `remember` skill to capture durable lessons about the impeccable workflow itself or about this project's specific gotchas. Memory benefits future sessions across the project's life.

**What does NOT count as a deviation worth touching the plan over:**

- Style choices in copy rewrites (those happen per session and don't need plan amendments).
- One-off CSS edits that don't generalize (commit them; move on).
- Per-session test additions (each session writes its own; the plan describes the pattern, not the specific tests).

The plan's role is **scaffolding**: it gives every session a clean place to start, locks the strategic priorities, and tracks completion. Impeccable's role is **the design discipline**. Don't confuse the two.

---

## 2. Phase 0 — Cross-cutting harden (3 sessions)

These sessions execute the systemic findings from the leaderboard exemplar before any per-page work begins. Each fix touches the entire codebase, so doing them per-page would multiply the work and risk inconsistent migrations.

---

### Session S0.1 — Bootstrap shadow leak migration

**Goal:** Replace every Bootstrap `shadow-sm`/`shadow`/`shadow-lg` utility on CCC card classes with the brand-tinted `--shadow-sm/md/lg` scale, eliminating the neutral-gray `rgba(0,0,0,0.075)` shadow leak DESIGN.md flags as slop.

**Prerequisites:** None (this is the first session).

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- `static/css/tokens.css` — confirm `--shadow-sm/md/lg/gold` definitions
- `static/css/style.css` — find every `.card`, `.card.wc-card`, `.shadow-sm` rule
- All templates listed in §0.1 — grep for `class="...shadow..."` usage

**Files in scope (WRITE):**
- `static/css/style.css` — add scoped shadow rules
- All templates with literal `shadow-sm` / `shadow-lg` Bootstrap utility classes — strip the utility, rely on the scoped CSS rule
- `tests/test_design_p0_shadow.py` (new) — regression lock
- `.gitignore` — add `.impeccable-review/`

**Tasks:**

- [x] **Step 1: Confirm baseline**

```bash
grep -rn 'shadow-sm\|shadow-lg\|shadow ' games/worldcup/templates/ core/ templates/ 2>/dev/null | grep -v '.pyc'
grep -nE '\.card\.wc-card|\.card\b|\.shadow-sm|\.shadow-lg' static/css/style.css | head -40
```

Expected: a list of every Bootstrap shadow utility currently applied to CCC cards. Capture the count.

- [x] **Step 2: Add `.gitignore` entry**

Read `.gitignore`. If `.impeccable-review/` is not present, add it.

```
# Impeccable design-review screenshots and rendered HTML (regenerated per session)
.impeccable-review/
```

- [x] **Step 3: Write the failing test**

Create `tests/test_design_p0_shadow.py`:

```python
"""P0 S0.1 — lock: every CCC card class carries brand-tinted shadow, never neutral gray."""
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_no_neutral_gray_box_shadow_in_card_rules():
    """No CCC `.card`/`.card.wc-card` rule may declare a neutral `rgba(0,0,0,...)` shadow.
    All shadows must use the brand-tinted `--shadow-*` scale."""
    src = CSS_PATH.read_text()
    # Crude but adequate: walk every `.card` block and check its `box-shadow`/`shadow` declarations
    offenders = []
    for line_no, line in enumerate(src.splitlines(), start=1):
        if 'box-shadow' in line and 'rgba(0' in line and 'rgba(0, 17' not in line and 'rgba(0,17' not in line:
            # rgba(0, 17, ...) is the navy WC card surface, allowed; rgba(0, 0, 0, ...) is the gray slop
            if 'rgba(0, 0, 0' in line or 'rgba(0,0,0' in line:
                offenders.append((line_no, line.strip()))
    assert not offenders, f"Neutral-gray shadows found: {offenders}"


def test_card_wc_card_uses_brand_shadow_token():
    """`.card.wc-card` resting state must reference `var(--shadow-sm)` (brand-tinted)."""
    src = CSS_PATH.read_text()
    # Find the `.card.wc-card` block and confirm a shadow declaration referencing the token
    assert 'var(--shadow-sm)' in src or 'var(--shadow-md)' in src, "Brand shadow tokens must be referenced somewhere"
```

- [x] **Step 4: Run the test, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_shadow.py -v
```

Expected: failures (Bootstrap's `.shadow-sm` rule with `rgba(0, 0, 0, 0.075)` is in the cascade via the linked Bootstrap CSS — but NOT in our `style.css`. So this specific test may already pass since the offending shadow comes from Bootstrap CDN, not local source. **If both tests pass on the first run**, the issue is that Bootstrap's utility is being *applied via class*, not declared in our CSS. In that case skip Step 5's local-CSS edit and go to Step 6 (template scrub).

- [x] **Step 5: Add scoped shadow override in `style.css`**

Find the existing `.card.wc-card` block (around line 3242-3291 per the leaderboard audit). Above or alongside it, add:

```css
/* P0 S0.1 — neutralize Bootstrap's gray shadow utility on CCC cards.
   Every CCC card inherits the brand-tinted --shadow-sm at rest by default. */
.card,
.card.wc-card,
.game-card,
.leaderboard-card {
  box-shadow: var(--shadow-sm) !important;
}

.card:hover,
.card.wc-card:hover,
.game-card:hover,
.leaderboard-card:hover {
  box-shadow: var(--shadow-md) !important;
}
```

The `!important` is the only honest way to win against Bootstrap's `.shadow-sm` utility class once it's present in markup; a cleaner alternative is to **remove the utility class from templates** (Step 6) and drop `!important` here. Prefer that path.

- [x] **Step 6: Strip Bootstrap shadow utilities from templates**

For each occurrence found in Step 1, edit the template to remove `shadow-sm` / `shadow-lg` / `shadow` from the class list when the element already carries a `.card`, `.card.wc-card`, `.game-card`, or `.leaderboard-card` class. The CSS rule from Step 5 supplies the brand shadow.

Templates likely affected (from the leaderboard inventory):
- `games/worldcup/templates/worldcup/leaderboard.html` — `<div class="card wc-card border-0 shadow-sm ...">` (~6 instances)
- core/main partials: any `<div class="card ...shadow...">` — grep shows them
- Auth pages: `<div class="card shadow-lg auth-card">` etc.

After this, re-run grep:

```bash
grep -rn 'shadow-sm\|shadow-lg' games/worldcup/templates/ core/ templates/ 2>/dev/null | grep -v '.pyc'
```

Expected: zero results in templates that already carry a `.card` class.

- [x] **Step 7: Verify computed style via Playwright MCP (Layer B)**

Start dev server: `FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`. Use the Playwright MCP plugin (`mcp__plugin_playwright_playwright__*`) to:

1. `browser_navigate` to `http://127.0.0.1:5099/worldcup/leaderboard` (auth: the dev DB has a session cookie persisted from prior sessions; if not, log in via the form first).
2. `browser_evaluate` against `.card.wc-card`:
   ```javascript
   () => { const el = document.querySelector('.card.wc-card'); return el ? getComputedStyle(el).boxShadow : null; }
   ```
3. Assert in chat that the returned `boxShadow` contains `rgb(58, 29, 114)` or `rgba(58, 29, 114` (the brand-tinted purple), NOT `rgb(0, 0, 0)` or `rgba(0, 0, 0`.
4. Take a desktop + 375 mobile screenshot via `browser_take_screenshot` to `.impeccable-review/s0.1/`.

If the Playwright MCP is unavailable, fall back to `mcp__plugin_chrome-devtools-mcp_chrome-devtools__evaluate_script` with the same probe.

- [x] **Step 8: Run the test, see it pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_shadow.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

All green.

- [x] **Step 9: Commit**

```bash
git add tests/test_design_p0_shadow.py static/css/style.css games/worldcup/templates/ core/ templates/ .gitignore
git commit -m "$(cat <<'EOF'
refactor(p0-s0.1): replace Bootstrap shadow leak with brand-tinted scale

Press-Room Shadow Rule (DESIGN.md): all shadows tint with brand purple,
never neutral gray. Bootstrap's .shadow-sm utility was rendering
rgba(0,0,0,0.075) on every .card.wc-card, leaking SaaS-stock chrome
into the Tribune surface. Strip the utility from templates and route
through .card/.card.wc-card scoped rules that reference --shadow-sm/md.

Locked by tests/test_design_p0_shadow.py.

Impeccable: P0 S0.1 — Bootstrap shadow leak.
Critique: leaderboard audit Theming 2 → 3.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- DevTools confirms brand-tinted shadow on `.card.wc-card` ✓
- After-screenshot of leaderboard saved ✓

**Handoff to S0.2:** No outstanding work. Side-stripe migration is independent; can proceed.

---

### Session S0.2 — Side-stripe ban migration + table semantics sweep

**Goal:** Eliminate every `border-left: Npx` colored side-stripe accent across `style.css` and replace with full borders, leading icons/numerals, or background tints, per the impeccable absolute ban (DESIGN.md). Same session: add `<th scope="col">`, `<caption class="visually-hidden">`, and region roles to every leaderboard/standings table — they're WCAG 1.3.1 violations across the codebase.

**Prerequisites:** S0.1 complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- The full impeccable absolute-bans list (loaded by the skill)
- `static/css/style.css` — every `border-left:` declaration over 1px
- All public WC + global tables: leaderboard, schedule, stats, groups, picks (any `<table>` element)

**Files in scope (WRITE):**
- `static/css/style.css` — remove side-stripes, add replacement patterns
- Templates with `<table>` — add `scope="col"` to every `<th>`, add a visually-hidden `<caption>`
- Templates with `.your-standing` / `.row-current-user` — adjust class structure if the side-stripe migration changes the wrapper shape (but resist scope creep; the Your Standing reshape itself is P1 S1.1, not this session)
- `tests/test_design_p0_side_stripes.py` (new)
- `tests/test_design_p0_table_semantics.py` (new)

**Tasks:**

- [x] **Step 1: Inventory side-stripes in `style.css`**

```bash
grep -nE 'border-(left|right):\s*[2-9]px|border-(left|right):\s*[1-9][0-9]+px' static/css/style.css
```

Expected: ~15-20 hits. Note line numbers and the rule each is attached to.

- [x] **Step 2: Categorize each side-stripe**

For each hit, decide its replacement strategy:

| Selector type | Replacement |
|---|---|
| `.your-standing { border-left: 3px solid var(--game-accent) }` | Remove. Reshape (covered in P1 S1.1; for now, just remove the stripe and let P1 do the proper reshape). |
| `.row-current-user { border-left: ... }` | Remove. Replace with subtle background tint (already partially present) and a leading "you" indicator pill or numeral emphasis. |
| `.card.border-success/danger/warning/primary { border-left: 4px ... }` | Remove. Replace with **full-border** rules using the same token, plus a small leading icon (`<i class="bi bi-check-circle">` etc. injected via CSS pseudo-element if templates can't change). |
| `.tier-row { border-left: 3px solid var(--tier-color) }` (line 4729) | Remove. Replace with leading **tier number pill** (already-existing `.wc-tier-pill` pattern). |
| Game-specific stripes (CFB, Golf) | **Skip** — out of scope for this project. |
| `currentColor` stripes (`style.css:3563`) | Audit the rule. If it's an alert pattern, full-border + icon. |

- [x] **Step 3: Write the failing test**

Create `tests/test_design_p0_side_stripes.py`:

```python
"""P0 S0.2 — lock: no `border-left: Npx` colored accent on CCC components.
Side-stripe accents are an impeccable absolute ban (DESIGN.md)."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'

# Selectors NOT in scope (game-specific, off-limits for this project)
GAME_SCOPED_PATTERNS = [
    r'\.lives-indicator',
    r'\.cfb-',
    r'\.game-cfb',
    r'\.game-golf',
]


def test_no_colored_side_stripes_on_platform_components():
    """Walk style.css. Any `border-left: Npx` (N >= 2) outside game-scoped blocks fails."""
    src = CSS_PATH.read_text()
    pattern = re.compile(r'(\.[\w\-\.]+)\s*\{[^}]*border-(left|right):\s*([2-9]|[1-9]\d+)px[^}]*\}', re.MULTILINE | re.DOTALL)
    offenders = []
    for match in pattern.finditer(src):
        selector = match.group(1)
        if any(re.search(p, selector) for p in GAME_SCOPED_PATTERNS):
            continue
        offenders.append((selector, match.group(2), match.group(3)))
    assert not offenders, f"Side-stripe ban violations on platform/WC components: {offenders}"


def test_card_border_state_classes_use_full_border_not_side_stripe():
    """`.card.border-success/danger/warning/primary` must use a full border, not border-left."""
    src = CSS_PATH.read_text()
    for class_name in ['border-success', 'border-danger', 'border-warning', 'border-primary']:
        # Find the rule and confirm it does NOT contain `border-left:` over 1px
        rule_match = re.search(rf'\.card\.{class_name}\s*\{{([^}}]+)\}}', src, re.MULTILINE)
        if rule_match is None:
            continue  # rule may have been removed entirely
        body = rule_match.group(1)
        assert 'border-left:' not in body or 'border-left: 1px' in body, \
            f".card.{class_name} still uses border-left side-stripe: {body[:200]}"
```

- [x] **Step 4: Run the test, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_side_stripes.py -v
```

Expected: 1-2 failures with offender selectors listed.

- [x] **Step 5: Migrate each side-stripe rule in `style.css`**

For each rule from Step 2, edit `style.css`:

For `.card.border-success/danger/warning/primary` (lines ~3602-3605):

```css
/* Replaced side-stripe with full border + tinted background for state communication.
   Per impeccable absolute ban: no border-left/right >1px as a colored accent. */
.card.border-success {
  border: 1px solid var(--success);
  background-color: rgba(26, 122, 69, 0.05);
}
.card.border-danger {
  border: 1px solid var(--danger);
  background-color: rgba(192, 57, 43, 0.05);
}
.card.border-warning {
  border: 1px solid var(--warning);
  background-color: rgba(201, 162, 39, 0.06);
}
.card.border-primary {
  border: 1px solid var(--platform-primary);
  background-color: rgba(58, 29, 114, 0.05);
}
```

For `.your-standing` (line ~3163): remove `border-left: 3px solid var(--game-accent);`. The block stays card-shaped; the proper Your Standing reshape happens in P1 S1.1. For now it's a plain bone-tinted card without the alert frequency.

For `.row-current-user` (find the active rule via grep): remove `border-left: ...`. Confirm an existing background-tint highlight remains (it does — the row already has a tinted bg).

For tier rows (line ~4729): remove `border-left: 3px solid var(--tier-color);`. Confirm leading tier pill (`.wc-tier-pill`) carries the color responsibility.

For any other rule from Step 2: full-border-or-pill replacement, never re-introduce a stripe.

- [x] **Step 6: Add table semantics across in-scope tables**

For each public table in WC + global surfaces:
- `games/worldcup/templates/worldcup/leaderboard.html`
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/stats.html`
- `games/worldcup/templates/worldcup/groups.html`
- `games/worldcup/templates/worldcup/team_detail.html`
- `core/main/templates/main/...` (any partial with a `<table>`)

Apply this pattern:

```jinja
<table class="...existing classes...">
  <caption class="visually-hidden">{# Concise table description, e.g. "2026 World Cup Pool standings" #}</caption>
  <thead>
    <tr>
      <th scope="col">#</th>
      <th scope="col">Player</th>
      ...
    </tr>
  </thead>
  ...
</table>
```

Add `<th scope="row">` to any first-column `<th>` if a table uses row-headers.

- [x] **Step 7: Add region role to `.your-standing`**

In `games/worldcup/templates/worldcup/leaderboard.html`, wrap the Your Standing block:

```jinja
<section role="region" aria-labelledby="your-standing-title">
  <span class="wc-eyebrow" id="your-standing-title">Your Standing</span>
  ...
</section>
```

Or use `aria-label="Your standing"` on the wrapper if a heading element isn't present.

- [x] **Step 8: Write the table-semantics test**

Create `tests/test_design_p0_table_semantics.py`:

```python
"""P0 S0.2 — lock: every public WC/global table has scope=col + visually-hidden caption.
WCAG 1.3.1 (Info and Relationships)."""
import pytest
from app import create_app

PATHS_WITH_TABLES = [
    '/worldcup/leaderboard',
    '/worldcup/schedule',
    '/worldcup/stats',
    '/worldcup/groups',
    # Add as new tables surface in later phases
]


@pytest.fixture
def client():
    app = create_app('testing')
    with app.app_context():
        from extensions import db
        db.create_all()
        yield app.test_client()


@pytest.mark.parametrize('path', PATHS_WITH_TABLES)
def test_tables_carry_scope_col_and_caption(client, path):
    """Anonymous-or-authenticated GET must render <th scope="col"> on every <th> and
    a <caption class="visually-hidden"> on every standings table."""
    # Auth-gated routes: pre-login a test user (see tests/conftest.py if it exists; otherwise
    # this test parameter is skipped via pytest.skip when the path 302s to /login)
    resp = client.get(path, follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip(f'{path} requires auth; covered by per-page session integration tests')
    body = resp.data.decode('utf-8')
    if '<table' not in body:
        return  # page may not render a table in current state
    assert 'scope="col"' in body, f'{path}: <th> missing scope="col"'
    assert 'visually-hidden' in body and 'caption' in body, f'{path}: missing visually-hidden caption'
```

(Note: this test will skip auth-gated paths; per-page integration tests in later sessions cover them with a logged-in client. Adjust if `tests/conftest.py` already exposes an authenticated client fixture — check before writing.)

- [x] **Step 9: Run all tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_side_stripes.py tests/test_design_p0_table_semantics.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

All green.

- [x] **Step 10: Playwright MCP verification (Layer B)**

Use the Playwright MCP plugin to confirm the rendered tables and the no-stripe state:

1. `browser_navigate` to `/worldcup/leaderboard`. `browser_evaluate`:
   ```javascript
   () => {
     const stripes = [];
     for (const sel of ['.your-standing', '.row-current-user', '.card.border-success', '.card.border-danger', '.card.border-warning', '.card.border-primary']) {
       const el = document.querySelector(sel);
       if (el) { const cs = getComputedStyle(el); stripes.push({ sel, borderLeft: cs.borderLeftWidth + ' ' + cs.borderLeftColor }); }
     }
     // Also check tables on this page:
     const tables = Array.from(document.querySelectorAll('table'));
     const tableSemantics = tables.map(t => ({
       hasCaption: !!t.querySelector('caption'),
       allThHaveScope: Array.from(t.querySelectorAll('thead th')).every(th => th.hasAttribute('scope')),
     }));
     return { stripes, tableSemantics };
   }
   ```
2. Assert: every `borderLeft` width is `0px` or `1px` (no >1px colored stripes). Every table reports `hasCaption: true` and `allThHaveScope: true`.
3. Take desktop (1470x900) + mobile (375x812) screenshots via `browser_take_screenshot` to `.impeccable-review/s0.2/`.
4. (Optional but recommended) Inject axe-core via `browser_evaluate` and run a scan; assert no `serious` or `critical` violations on tables. The skill or critique reference notes how to inject axe-core.

If Playwright MCP isn't available, fall back to chrome-devtools-mcp with the same probes.

- [x] **Step 11: Commit**

```bash
git add tests/test_design_p0_side_stripes.py tests/test_design_p0_table_semantics.py static/css/style.css games/ core/ templates/
git commit -m "$(cat <<'EOF'
refactor(p0-s0.2): migrate side-stripe accents to full borders + table a11y sweep

Side-stripe ban (impeccable absolute) violated on .your-standing,
.row-current-user, .card.border-{success,danger,warning,primary},
tier-row, and others. Migrate to full borders + tinted backgrounds.
The Your Standing reshape lands in P1 S1.1; this session just neutralizes
the stripe so the surface stops shouting "alert".

Same pass: every public WC table gains <th scope="col"> + a
visually-hidden <caption> for WCAG 1.3.1 (Info and Relationships).
.your-standing wrapped as <section role="region" aria-labelledby=...>.

Locked by tests/test_design_p0_side_stripes.py and
tests/test_design_p0_table_semantics.py.

Impeccable: P0 S0.2 — side-stripe ban + table semantics.
Critique: leaderboard a11y 2 → 3, anti-patterns count -2.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- All tables in scope have `scope="col"` + caption ✓
- No side-stripes >1px in `style.css` (outside CFB/Golf) ✓
- Visual smoke at desktop + mobile ✓

**Handoff to S0.3:** Mobile tap targets and white-on-gold contrast remain. They're independent of this session.

---

### Session S0.3 — Mobile tap-target floor + white-on-gold contrast + em-dash sweep

**Goal:** (a) Bring every interactive element across public WC + global pages to ≥44×44 px at 375 viewport, (b) lock the trophy CTA text color to chamber-purple on rest + hover (source-level token lock; lifts the rendered worst-stop ratio from 1.5:1 white-on-gold to ~3.6:1 chamber-on-gold-dark — full AA closure to ≥4.5:1 requires retuning `--gold-dark` in `tokens.css` and is deferred to **P6 S6.1** per §0.4), (c) eliminate em-dash glyphs (`—` and `--`) from UI copy per Copy Discipline.

**Prerequisites:** S0.1 + S0.2 complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- `static/css/style.css` — `.subnav-pill`, `.btn-warning`, `.metal-gold` rules; `.leaderboard-card` and any other `.card`-as-link patterns
- All in-scope templates — for em-dash sweep

**Files in scope (WRITE):**
- `static/css/style.css` — sub-nav pill min-height + padding; trophy CTA text contrast lock
- Mobile leaderboard cards: convert to whole-card-as-link (template + CSS)
- All in-scope templates — replace `—` glyphs with appropriate words/punctuation
- `tests/test_design_p0_tap_targets.py` (new)
- `tests/test_design_p0_contrast.py` (new)
- `tests/test_design_p0_copy_discipline.py` (new)

**Tasks:**

- [x] **Step 1: Tap-target inventory via Playwright MCP (Layer B)**

Boot dev server. Use the Playwright MCP plugin: `browser_resize` to 375×812 (or `browser_emulate` mobile preset), `browser_navigate` to each in-scope page (`/worldcup/leaderboard`, `/worldcup/`, `/worldcup/schedule`, `/worldcup/picks`, `/worldcup/stats`, `/worldcup/rules`, `/login`, `/`). For each, run:

```javascript
() => {
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('a, button, [role="button"], .subnav-pill, .leaderboard-card, .btn-sm')) {
    if (seen.has(el)) continue; seen.add(el);
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44)) {
      out.push({ tag: el.tagName, classes: el.className.toString().slice(0, 80), text: (el.textContent || '').trim().slice(0, 40), w: r.width, h: r.height });
    }
  }
  return { failures: out, docW: document.documentElement.scrollWidth, winW: innerWidth };
}
```

Record every selector that fails 44×44. Known seeds from the leaderboard audit:
- `.leaderboard-card a.d-block` — 85×26
- `.subnav-pill` — 36–60×30 (six pills)

Likely failures elsewhere (verify with the probe above):
- Game-card name links on home (`.game-card a`)
- Auth page link rows
- Schedule fixture cards
- Empty-state CTAs (small `.btn-sm` buttons)

The Playwright MCP probe is the source of truth for which elements need fixing in this session — don't pre-commit to a list.

- [x] **Step 2: Write the source-pattern test (tap-targets)**

Source-grep test confirms every fixed selector declares its min-height in `style.css`. The Playwright MCP probe in Step 1 confirms the rendered rect; the source test below locks the CSS so the rect can't regress in source.

Create `tests/test_design_p0_tap_targets.py`:

```python
"""P0 S0.3 — lock: mobile tap-target floor 44x44.
WCAG 2.5.5/2.5.8 + DESIGN.md mobile-first floor."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def _rule_min_height(css: str, selector: str) -> str | None:
    """Return the `min-height` value declared on a selector, or None if not declared."""
    pattern = rf'{re.escape(selector)}\s*\{{([^}}]+)\}}'
    match = re.search(pattern, css, re.MULTILINE)
    if not match:
        return None
    body = match.group(1)
    mh = re.search(r'min-height:\s*([^;]+);', body)
    return mh.group(1).strip() if mh else None


def test_subnav_pill_min_height_44px():
    """`.subnav-pill` must declare min-height ≥ 44px (or 2.75rem)."""
    css = CSS_PATH.read_text()
    mh = _rule_min_height(css, '.subnav-pill')
    assert mh is not None, '.subnav-pill must declare min-height'
    # Accept 44px, 2.75rem, or larger
    assert ('44px' in mh) or ('2.75rem' in mh) or ('48px' in mh), f'.subnav-pill min-height too small: {mh}'


def test_leaderboard_card_link_covers_card():
    """Mobile leaderboard cards must be whole-card-as-link, not name-string-as-link."""
    template = Path(__file__).parent.parent / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
    src = template.read_text()
    # Heuristic: the mobile section must wrap each card in <a> or use stretched-link pattern
    assert 'leaderboard-card-link' in src or 'stretched-link' in src or '<a href="/worldcup/leaderboard/' in src and 'leaderboard-card' in src, \
        'Mobile leaderboard cards must use whole-card-as-link pattern'
```

- [x] **Step 3: Run, see it fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py -v
```

Expected: both fail.

- [x] **Step 4: Fix sub-nav pills in `style.css`**

Find the `.subnav-pill` block (search for `.subnav-pill {`). Edit:

```css
.subnav-pill {
  /* ...existing properties... */
  min-height: 44px;
  padding: 0.625rem 1rem;          /* was ~0.32rem 0.72rem; expand for the 44px floor */
  display: inline-flex;
  align-items: center;
  /* ...existing... */
}
```

If the surrounding container needs more vertical space, adjust `.subnav-pills` padding and `.game-subnav` height accordingly. Verify the navbar+sub-nav stack doesn't push hero content off-screen.

- [x] **Step 5: Convert mobile leaderboard cards to whole-card links**

Edit `games/worldcup/templates/worldcup/leaderboard.html` mobile section. Replace the existing per-card structure:

```jinja
{# BEFORE — the inner <a> is the only tap target #}
<div class="card wc-card ...">
  <div class="card-body ...">
    <span class="...">{{ rank }}</span>
    <div>
      <span class="me-1">{{ avatar }}</span>
      <a href="..." class="text-decoration-none fw-medium d-block">{{ name }}</a>
      <small>...</small>
    </div>
    <span class="...">{{ score }}</span>
  </div>
</div>
```

```jinja
{# AFTER — whole card is the tap target #}
<a href="{{ '/worldcup/picks' if is_current_user else '/worldcup/leaderboard/' ~ enrollment.id }}"
   class="card wc-card leaderboard-card leaderboard-card-link {% if is_current_user %}leaderboard-card-current{% endif %} animate-in text-decoration-none">
  <div class="card-body p-3 d-flex align-items-center justify-content-between">
    <span class="...">{{ rank }}</span>
    <div>
      <span class="me-1">{{ avatar }}</span>
      <span class="fw-medium d-block leaderboard-card-name">{{ name }}</span>
      <small>...</small>
    </div>
    <span class="...">{{ score }}</span>
  </div>
</a>
```

Add `.leaderboard-card-link` to `style.css` to neutralize default link styling on the card and preserve the existing visual:

```css
.leaderboard-card-link {
  display: block;
  color: inherit;
  text-decoration: none;
}
.leaderboard-card-link:hover,
.leaderboard-card-link:focus {
  color: inherit;
  text-decoration: none;
}
.leaderboard-card-link:focus-visible {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}
```

- [x] **Step 6: Run tap-target tests, see them pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py -v
```

- [x] **Step 7: Write the failing test (white-on-gold contrast)**

Create `tests/test_design_p0_contrast.py`:

```python
"""P0 S0.3 — lock: trophy CTA text on metal-gold gradient meets WCAG AA contrast.
The previous hover state rendered white on #FFF1B8 (1.5:1). Lock to chamber-purple text."""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_navbar_btn_warning_text_color_locked_to_purple():
    """Navbar `.btn-warning` (metal-gold trophy CTA) must declare a dark purple text color
    for both rest and hover, never bone/white. Per DESIGN.md trophy CTA contract."""
    css = CSS_PATH.read_text()
    rest = re.search(r'\.navbar\.navbar-dark\s+\.btn-warning\s*\{([^}]+)\}', css)
    hover = re.search(r'\.navbar\.navbar-dark\s+\.btn-warning:hover\s*\{([^}]+)\}', css)
    assert rest, 'navbar .btn-warning rest rule not found'
    assert hover, 'navbar .btn-warning:hover rule not found'
    for label, body in [('rest', rest.group(1)), ('hover', hover.group(1))]:
        # The text color must be the dark chamber purple, not bone/white
        assert 'var(--purple-900)' in body or '#1C0A3A' in body or 'var(--chamber)' in body, \
            f'navbar .btn-warning {label}: text color must be chamber-purple, found: {body[:200]}'
```

- [x] **Step 7.5: Playwright MCP — measure actual rendered contrast (Layer B)**

Use the Playwright MCP to confirm the rendered contrast of the trophy CTA, before AND after the fix:

1. `browser_navigate` to any logged-in page (the navbar carries the trophy button).
2. `browser_evaluate` to get the rendered color stack of the navbar `.btn-warning` at rest and on hover. Sketch:
   ```javascript
   () => {
     const btn = document.querySelector('.navbar .btn-warning');
     if (!btn) return { found: false };
     const rest = getComputedStyle(btn);
     return { color: rest.color, backgroundColor: rest.backgroundColor, backgroundImage: rest.backgroundImage };
   }
   ```
3. For hover state, dispatch a `mouseenter`/`mouseover` synthetic event then re-measure.
4. Confirm the rendered text color is the chamber-purple stack (`var(--purple-900)` / `#1C0A3A`) on rest AND hover. Optionally compute contrast against each gradient stop with a ratio function (axe-core, contrast-ratio NPM, etc.) — the rendered ratio at the worst stop (`--gold-dark` = `#8A6A1A`) is ~3.6:1 (below WCAG AA 4.5:1) and is **expected** at this phase; the gold-token retune that closes the worst-stop AA gap is deferred to **P6 S6.1** per §0.4. Mid-stop and lightest-stop are AA-passing (~7.5:1 and ~12.4:1).

This catches the gradient-stop trap that source-grep can't see (a source `color: var(--bone)` declaration may pass source review but fail rendered contrast against the gold gradient). The S0.3 gate is "chamber-purple text declared and rendered on rest + hover," not "≥4.5:1 at every stop" — the latter is the P6 spec session.

- [x] **Step 8: Repair the trophy CTA color in `style.css`**

Find `.navbar.navbar-dark .btn-warning` (around line 101) and `.navbar.navbar-dark .btn-warning:hover` (around line 109). Confirm both declare `color: var(--purple-900);` (or `#1C0A3A`). If hover declares a different color (e.g., `color: var(--bg-card)`), fix it.

```css
.navbar.navbar-dark .btn-warning {
  background: var(--metal-gold-flat);
  color: var(--purple-900);  /* DESIGN.md trophy CTA contract: dark purple on gold */
  /* ...other properties... */
}
.navbar.navbar-dark .btn-warning:hover {
  background: var(--metal-gold-flat);
  color: var(--purple-900);  /* lock; do not flip to bone/white on hover */
  filter: brightness(1.05);
  box-shadow: var(--shadow-gold);
  /* ...other properties... */
}
```

- [x] **Step 9: Em-dash sweep across templates**

```bash
grep -rn '—\|&mdash;\|&#8212;' games/worldcup/templates/ core/ templates/ --include='*.html' | grep -v 'CCC tokens — must load' | grep -v 'inline comment' | head -100
```

Expected: dozens of hits. For each:

- **Title separators** (`<title>X — Y</title>`): replace `—` with `:` or `·`. E.g., `Leaderboard — World Cup Fantasy Pool` → `Leaderboard · World Cup Fantasy Pool` or `Leaderboard: 2026 World Cup`.
- **Empty-state placeholders** (`<span>—</span>`): replace with semantic words: `Pending`, `Even`, `Awaiting`, `–` (en-dash) only when truly absent. Choose per-context; never broadcast one replacement.
- **Body copy** (`Test1 — locked in`): rewrite with comma, colon, semicolon, or period.
- **Comments in CSS/HTML**: leave alone (comments aren't user copy).

Edit each in place. This is mechanical but careful work — the meaning of each `—` depends on context.

- [x] **Step 10: Write the failing test (em-dash discipline)**

Create `tests/test_design_p0_copy_discipline.py`:

```python
"""P0 S0.3 — lock: no em-dashes (—) in user-facing template copy.
PRODUCT.md + DESIGN.md Copy Discipline."""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
TEMPLATE_DIRS = [
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup',
    ROOT / 'core' / 'main' / 'templates' / 'main',
    ROOT / 'core' / 'auth' / 'templates' / 'auth',
    ROOT / 'templates',
]

# Lines beginning with a Jinja comment ({# ... #}) or HTML comment (<!-- ... -->) are exempt.
COMMENT_LINE = re.compile(r'^\s*({#|<!--)')


def _user_copy_lines(path: Path):
    for line in path.read_text().splitlines():
        if COMMENT_LINE.match(line):
            continue
        yield line


def test_no_em_dash_in_user_facing_copy():
    offenders = []
    for tdir in TEMPLATE_DIRS:
        if not tdir.exists():
            continue
        for path in tdir.rglob('*.html'):
            # Skip admin/* (out of scope for this project)
            if 'admin' in path.parts:
                continue
            for i, line in enumerate(_user_copy_lines(path), start=1):
                if '—' in line or '&mdash;' in line or '&#8212;' in line:
                    offenders.append((path.relative_to(ROOT), i, line.strip()[:120]))
    assert not offenders, f'Em-dash discipline violations: {offenders[:20]}'
```

- [x] **Step 11: Run all tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_design_p0_tap_targets.py tests/test_design_p0_contrast.py tests/test_design_p0_copy_discipline.py -v
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

All green.

- [x] **Step 12: Visual smoke**

Boot dev server, take desktop + 375 mobile screenshots of `/worldcup/leaderboard`, `/worldcup/`, `/worldcup/picks`, `/`, `/login`. Save under `.impeccable-review/s0.3/`. Confirm sub-nav pills are taller (~44px) and the metal-gold trophy CTA in the navbar reads dark-on-gold.

- [x] **Step 13: Commit**

```bash
git add tests/test_design_p0_tap_targets.py tests/test_design_p0_contrast.py tests/test_design_p0_copy_discipline.py static/css/style.css games/ core/ templates/
git commit -m "$(cat <<'EOF'
fix(p0-s0.3): mobile tap-target floor, trophy CTA contrast, em-dash sweep

(a) Sub-nav pills + leaderboard mobile cards now meet 44x44 floor.
    Mobile cards converted to whole-card-as-link with focus-visible ring.
(b) Navbar .btn-warning trophy CTA text locked to var(--purple-900)
    on rest AND hover (was flipping to white on metal-gold gradient,
    rendering 1.5:1 contrast).
(c) Every user-facing — replaced with appropriate punctuation/copy
    across in-scope templates per Copy Discipline.

Locked by three new test files under tests/test_design_p0_*.py.

Impeccable: P0 S0.3 — tap-targets, contrast, copy discipline.
Critique: leaderboard a11y 2 → 3, anti-patterns count -1, microcopy improved.
EOF
)"
```

**Verification gate:**
- pytest green ✓
- 44px floor on tested elements ✓
- Trophy CTA dark-on-gold ✓
- Em-dash count 0 in user-facing copy ✓

**Handoff to P1:** Cross-cutting harden complete. **Open PR `Impeccable P0 — Cross-cutting harden`** combining commits from S0.1 + S0.2 + S0.3 to `main` (or stash for end-of-project merge per §1.1; user choice). Move to P1.

---

## 3. Phase 1 — Leaderboard close (1 session)

### Session S1.1 — Shape Your Standing + trend rank-delta + clarify leaderboard copy

**Goal:** Reshape the Your Standing block from a hero-metric SaaS card into a Tribune sidebar; replace the trend column's points-delta with a rank-delta (with points-delta on hover/secondary line); voice-rewrite the page's microcopy. Run a closing critique re-check to confirm score lift.

**Prerequisites:** P0 (S0.1, S0.2, S0.3) complete.

**Files in scope (READ):**
- `PRODUCT.md`, `DESIGN.md`, `CLAUDE.md`
- The Tier 1 leaderboard critique in this conversation history (carried forward via the plan; the new session reads this section as the brief)
- `games/worldcup/routes.py` — `def leaderboard()`
- `games/worldcup/services/ranking.py` — `compute_rank_neighbors`
- `games/worldcup/services/snapshots.py` — `WorldCupRankSnapshot` query helpers
- `games/worldcup/templates/worldcup/leaderboard.html`
- `static/css/style.css` — `.your-standing*`, `.leaderboard-*`, `.wc-eyebrow*`

**Files in scope (WRITE):**
- `games/worldcup/services/ranking.py` — add a `compute_rank_delta(enrollment, window_days=1)` helper backed by `WorldCupRankSnapshot`
- `games/worldcup/routes.py` — wire `rank_delta` into the leaderboard context dict
- `games/worldcup/templates/worldcup/leaderboard.html` — Your Standing reshape, trend column rewrite, voice copy
- `static/css/style.css` — `.your-standing` rules updated, `.your-standing-caption` font-family corrected to Newsreader, new `.rank-delta-up/down/even` rules
- `tests/test_worldcup_ranking.py` (extend) — `compute_rank_delta` unit tests
- `tests/test_design_p1_leaderboard.py` (new) — surface-shape regression locks

**Tasks:**

- [x] **Step 1: Read brief**

Re-read this plan's S1.1 block, the leaderboard's Critique Report (in chat history if available; otherwise carry the Priority Issues forward from the leaderboard's commit messages of P0 sessions), and DESIGN.md's Eyebrow + Newsroom + Lift-At-Rest rules.

- [x] **Step 2: Compute-rank-delta helper — failing test**

Edit `tests/test_worldcup_ranking.py` (or create if absent). Add:

```python
def test_compute_rank_delta_returns_signed_int_or_none(app, db_session):
    """compute_rank_delta(enrollment, window_days) returns positive int (rank improved),
    negative (rank dropped), zero (held), or None (insufficient snapshot history)."""
    from games.worldcup.services.ranking import compute_rank_delta
    from games.worldcup.services.state import now_utc
    from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
    from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
    from datetime import timedelta
    # Setup: an enrollment with two snapshots (yesterday rank=5, today rank=3 → delta=+2)
    today = now_utc().astimezone(WORLDCUP_TZ).date()
    e = WorldCupEnrollment(user_id=..., season_year=SEASON_YEAR)  # fill via fixture
    db_session.add(e); db_session.flush()
    db_session.add_all([
        WorldCupRankSnapshot(enrollment_id=e.id, rank=5, total_score=10.0, captured_on=today - timedelta(days=1)),
        WorldCupRankSnapshot(enrollment_id=e.id, rank=3, total_score=18.0, captured_on=today),
    ])
    db_session.flush()
    assert compute_rank_delta(e, window_days=1) == 2

def test_compute_rank_delta_returns_none_when_no_prior_snapshot(app, db_session):
    from games.worldcup.services.ranking import compute_rank_delta
    e = WorldCupEnrollment(...)
    db_session.add(e); db_session.flush()
    # No snapshots
    assert compute_rank_delta(e, window_days=1) is None
```

(Adapt to existing test fixtures — check what `tests/conftest.py` provides.)

- [x] **Step 3: Run, see fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v -k delta
```

- [x] **Step 4: Implement `compute_rank_delta` in `services/ranking.py`**

```python
def compute_rank_delta(enrollment, window_days: int = 1) -> int | None:
    """Return positive int if rank improved (smaller rank number) over `window_days`,
    negative if rank dropped, zero if held, None if insufficient snapshot history.
    Snapshots must be season-scoped via the enrollment FK (CLAUDE.md invariant)."""
    from sqlalchemy import select
    from extensions import db
    from games.worldcup.models import WorldCupRankSnapshot
    from games.worldcup.services.state import now_utc
    from games.worldcup.constants import WORLDCUP_TZ
    from datetime import timedelta
    cutoff = now_utc().astimezone(WORLDCUP_TZ).date() - timedelta(days=window_days)
    today = db.session.scalars(
        select(WorldCupRankSnapshot)
        .where(WorldCupRankSnapshot.enrollment_id == enrollment.id)
        .order_by(WorldCupRankSnapshot.captured_on.desc())
    ).first()
    prior = db.session.scalars(
        select(WorldCupRankSnapshot)
        .where(
            WorldCupRankSnapshot.enrollment_id == enrollment.id,
            WorldCupRankSnapshot.captured_on <= cutoff,
        )
        .order_by(WorldCupRankSnapshot.captured_on.desc())
    ).first()
    if today is None or prior is None:
        return None
    return prior.rank - today.rank  # smaller rank = better
```

- [x] **Step 5: Run, see pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_ranking.py -v -k delta
```

- [x] **Step 6: Wire `rank_delta` into the leaderboard route**

Edit `games/worldcup/routes.py`'s `leaderboard()` view. For each enrollment in the standings, compute `rank_delta` (1-day window). Pass into the template context as part of each row's dict.

- [x] **Step 7: Reshape Your Standing block in `leaderboard.html`**

Replace the existing `.your-standing` block with a Tribune-shaped version:

```jinja
{% if your_standing %}
<section class="your-standing-tribune animate-in mt-4" role="region" aria-labelledby="your-standing-h">
  <span class="wc-eyebrow" id="your-standing-h">Your Position</span>
  <div class="your-standing-tribune-grid">
    <div class="your-standing-tribune-rank">
      <span class="wc-numeral your-standing-tribune-numeral">{{ your_standing.rank }}</span>
      <span class="your-standing-tribune-of">of {{ total_players }}</span>
    </div>
    <p class="your-standing-tribune-caption mb-0">
      {{ standing_caption }}
    </p>
  </div>
</section>
{% else %}
<aside class="your-standing-tribune your-standing-tribune-empty animate-in mt-4">
  <p class="mb-0">
    <a href="{{ url_for('worldcup.join') }}" class="text-decoration-none">
      Join the pool
    </a> to claim your seat in the standings.
  </p>
</aside>
{% endif %}
```

The `standing_caption` is computed in the route as a voice-driven string (Step 8).

- [x] **Step 8: Voice-drive the standing caption in the route**

In `routes.py`, after computing your_standing's position, build a voice-driven caption string:

```python
def _standing_caption(your_standing, total_players, ranked_enrollments, rank_delta):
    """Voice-driven 'where you stand' line. Sharp. Competitive. Pleasure."""
    rank = your_standing.rank
    if rank == 1:
        if rank_delta and rank_delta > 0:
            return f'You took the top. Don\'t look down.'
        return 'Top of the table. The chase is yours to lose.'
    if rank == total_players:
        return 'Cellar dweller. Plenty of road ahead.'
    leader_score = ranked_enrollments[0].total_score
    next_above = next((e for e in ranked_enrollments if e.rank < rank and e.rank == rank - 1), None)
    delta_to_lead = leader_score - your_standing.total_score
    delta_to_next = (next_above.total_score - your_standing.total_score) if next_above else 0.0
    if rank_delta and rank_delta > 0:
        return f'Up {rank_delta}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
    if rank_delta and rank_delta < 0:
        return f'Down {-rank_delta}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
    return f'Holding {rank}. {delta_to_lead:.0f} from the top, {delta_to_next:.0f} ahead of the chase.'
```

Pass `standing_caption` into the template.

- [x] **Step 9: Replace trend column with rank-delta**

In the desktop table:

```jinja
<th scope="col" class="text-end">Move</th>  {# was "Trend" #}
...
<td class="text-end">
  {% if e.rank_delta is none %}
    <span class="text-muted" aria-label="Awaiting first matchday">Pending</span>
  {% elif e.rank_delta > 0 %}
    <span class="rank-delta-up wc-numeral" aria-label="Up {{ e.rank_delta }}">↑{{ e.rank_delta }}</span>
  {% elif e.rank_delta < 0 %}
    <span class="rank-delta-down wc-numeral" aria-label="Down {{ -e.rank_delta }}">↓{{ -e.rank_delta }}</span>
  {% else %}
    <span class="rank-delta-even text-muted" aria-label="Even">Even</span>
  {% endif %}
</td>
```

Same pattern in the mobile card. Replace `<small>Trend: ...</small>` with the rank-delta rendering. Carry the points-delta as a tooltip (`title=` attribute) for the analyst register:

```jinja
<span class="rank-delta-up" title="Points: +{{ e.points_delta }}">↑{{ e.rank_delta }}</span>
```

- [x] **Step 10: Update CSS for new shape**

In `static/css/style.css`, replace `.your-standing` rules with `.your-standing-tribune` rules. Caption font-family **Newsreader** (Newsroom Rule). Eyebrow color stays gold (the override to red is gone). Rank numeral large in Teko. No side-stripe (already removed in S0.2; lock).

```css
.your-standing-tribune {
  background-color: var(--surface-card);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow-sm);
}
.your-standing-tribune-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1.5rem;
  align-items: center;
}
.your-standing-tribune-numeral {
  font-family: 'Teko', sans-serif;
  font-size: 3.5rem;
  font-weight: 600;
  line-height: 1;
  color: var(--platform-primary);  /* council purple */
  font-feature-settings: 'tnum';
}
.your-standing-tribune-of {
  font-family: 'Teko', sans-serif;
  font-size: 0.85rem;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  display: block;
  margin-top: 0.25rem;
}
.your-standing-tribune-caption {
  font-family: 'Newsreader', Georgia, serif;  /* NEWSROOM RULE */
  font-size: 1.05rem;
  line-height: 1.5;
  color: var(--text-ink);
}
.your-standing-tribune-empty p {
  font-family: 'Newsreader', Georgia, serif;
  color: var(--text-secondary);
}
.rank-delta-up { color: var(--success); font-weight: 600; }
.rank-delta-down { color: var(--danger); font-weight: 600; }
.rank-delta-even { font-weight: 500; }
```

- [x] **Step 11: Voice rewrite of remaining microcopy**

Rewrite headers + supporting copy on `leaderboard.html`:

| Before | After |
|---|---|
| `<title>Leaderboard — World Cup Fantasy Pool</title>` | `<title>The Standings: 2026 World Cup Pool</title>` |
| `<h1>Leaderboard</h1>` | `<h1>The Standings</h1>` |
| `<span class="wc-eyebrow">Live Standings</span>` | `<span class="wc-eyebrow">{% if deadline_passed %}Tonight's Ledger{% else %}Tribute Window Open{% endif %}</span>` |
| `<th>Trend</th>` | `<th scope="col" class="text-end">Move</th>` |
| `No players enrolled yet. Be the first!` | `The ledger awaits its first name. Lock your roster.` |
| Empty trend `—` (mobile) | `Pending` |

Apply similarly throughout.

- [x] **Step 12: Surface-shape regression test**

Create `tests/test_design_p1_leaderboard.py`:

```python
"""P1 S1.1 — lock the leaderboard's reshape."""
from pathlib import Path
import re

TEMPLATE = Path(__file__).parent.parent / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
CSS = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_your_standing_tribune_replaces_hero_metric_block():
    src = TEMPLATE.read_text()
    assert 'your-standing-tribune' in src, 'Your Standing must use the tribune-reshape class'
    assert 'your-standing-rank-numeral' not in src, 'Old hero-metric class must be removed'
    assert 'border-left' not in src, 'No inline side-stripe styles in the template'

def test_your_standing_caption_uses_newsreader():
    css = CSS.read_text()
    rule = re.search(r'\.your-standing-tribune-caption\s*\{([^}]+)\}', css)
    assert rule and 'Newsreader' in rule.group(1), 'Caption must be Newsreader (Newsroom Rule)'

def test_trend_column_renders_rank_delta_not_points_delta():
    src = TEMPLATE.read_text()
    # Header is Move, not Trend
    assert '<th scope="col" class="text-end">Move</th>' in src or 'rank-delta-up' in src, \
        'Trend column should render rank delta, header "Move"'
```

- [x] **Step 13: Run pytest + Playwright MCP verification (Layer B)**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Then via Playwright MCP, against the running dev server:

1. `browser_navigate` to `/worldcup/leaderboard`. `browser_evaluate`:
   ```javascript
   () => {
     const cap = document.querySelector('.your-standing-tribune-caption');
     const eyebrow = document.querySelector('.your-standing-tribune .wc-eyebrow');
     const wrapper = document.querySelector('.your-standing-tribune');
     const trendUp = document.querySelector('.rank-delta-up');
     return {
       captionFontFamily: cap ? getComputedStyle(cap).fontFamily : null,
       eyebrowColor: eyebrow ? getComputedStyle(eyebrow).color : null,
       wrapperBorderLeft: wrapper ? getComputedStyle(wrapper).borderLeftWidth + ' ' + getComputedStyle(wrapper).borderLeftColor : null,
       trendUpRendered: !!trendUp,
       trendUpText: trendUp ? trendUp.textContent.trim() : null,
     };
   }
   ```
2. Assert: `captionFontFamily` contains `Newsreader`; `eyebrowColor` is the gold token (around `rgb(201, 162, 39)`), not red; `wrapperBorderLeft` width is `0px`; `trendUpRendered` is true and the text starts with `↑`.
3. Take desktop + mobile screenshots to `.impeccable-review/s1.1/after/`.

- [x] **Step 14: Re-run impeccable critique on the leaderboard**

`$impeccable critique games/worldcup/templates/worldcup/leaderboard.html`. Compare to baseline (Design Health 23/40, Audit 11/20). Record new scores in commit message.

- [x] **Step 15: Commit**

```bash
git add tests/test_design_p1_leaderboard.py tests/test_worldcup_ranking.py games/worldcup/services/ranking.py games/worldcup/routes.py games/worldcup/templates/worldcup/leaderboard.html static/css/style.css
git commit -m "$(cat <<'EOF'
feat(p1-s1.1): reshape Your Standing as Tribune sidebar; rank-delta trend; voice copy

Closes the leaderboard exemplar's per-page Priority Issues:
  P1: Your Standing reshaped from hero-metric SaaS card to Tribune sidebar.
      No side-stripe, gold eyebrow restored, Newsreader caption per Newsroom Rule.
  P1: Trend column now renders rank-delta (↑2/↓1/Even/Pending) instead of
      points-delta. Points-delta retained as tooltip for analyst register.
  P2: Voice rewrite of title, h1, eyebrow, empty state, column header.
  P2: Empty/anon viewer now sees a join callout, not silence.

New helper: services/ranking.compute_rank_delta(enrollment, window_days) backed by
WorldCupRankSnapshot. Season-scoped per CLAUDE.md invariant.

Locked by tests/test_design_p1_leaderboard.py and the rank-delta unit tests.

Impeccable: P1 S1.1 — leaderboard close.
Critique re-run: <RECORD NEW SCORE HERE>
EOF
)"
```

**Verification gate:**
- pytest green ✓
- Re-run critique recorded ✓
- Visual smoke desktop + mobile ✓
- All Tier 1 Priority Issues marked closed ✓

**Handoff to P2:** Leaderboard exemplar complete. Open PR `Impeccable P1 — Leaderboard close`. Move to live-state cluster expansion.

---

## 4. Phase 2 — Live state cluster (5 surfaces, iterative)

Each surface (S2.1 home_shell+_home_live, S2.2 schedule, S2.3 team_detail, S2.4 stats, S2.5 player_detail) iterates per §1.5b until convergence. The original "6 sessions" estimate became iterative on 2026-05-08; the actual session count per surface is 1-3 depending on baseline score and per-iteration progress. S2.6 is a cross-cluster polish that runs only after all 5 surfaces have converged.

**Per-surface iteration model:**

- First iteration: `S2.x.1`. Baseline critique → triage 3-5 priority fixes → execute → re-critique → check §1.5b convergence gate.
- If gate fails: `/clear` and start `S2.x.2`. Repeat.
- A surface's iterations end when all four gates pass. Move to the next surface (S2.x+1.1).
- All 5 surfaces converge → S2.6 runs.

**Why iterative.** The previous "one session per surface" pattern shipped surfaces at heuristics ~28-30/40 with P2/P3 backlog deferred to S2.6, which would have bloated S2.6 into a multi-session amorphous cleanup. The iterative model holds each surface to a real convergence bar (§1.5b gates) and keeps S2.6 small and sharp (cross-cluster patterns only). See §1.5b for full convergence gate; see §0.4 for backlog routing rules.

**Dev-data setup ritual (P2 specifically — same shape applies to P4 pre-cluster and P5 post-cluster).** Before booting the dev server for a state-cluster iteration, confirm the dev DB is in the target tournament state. The state seam in `games/worldcup/services/state.worldcup_state()` returns `'post'` whenever match #104 has `is_completed=True` regardless of `WC_FAKE_NOW` — see memory `project_ccc_wc_reskin_gotchas.md` for the full gotcha. Quick recipe per state:

- **Live** (P2): set `match #104 is_completed=False` (one-line `flask shell` or inline python). `WC_FAKE_NOW='2026-06-22T18:00:00+00:00'` in the boot env puts the clock past the deadline. Restore #104 to `True` at session end so the dev DB stays consistent.
- **Pre** (P4): `match #104 is_completed=False`; pick any `WC_FAKE_NOW` before `2026-06-11T19:00:00+00:00` (e.g., `'2026-06-05T12:00:00+00:00'`).
- **Post** (P5): `match #104 is_completed=True` AND `winner_team_id` set AND `home_score`/`away_score` non-null. Scoring helpers return 0.0 if the winner FK is missing.

The boot command shape is `ENVIRONMENT=development WC_FAKE_NOW='<iso>' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`. Without `ENVIRONMENT=development`, `now_utc()` ignores `WC_FAKE_NOW` silently. For Playwright auth: set the test user's password to a known value via `flask shell` (`u.set_password('s2_iter_dev'); db.session.commit()`) at the start of the session; the test user enrolled in the current season is `B1G_Brad` (uid 1).

### Per-iteration pattern (applies to every `S2.x.N` session)

**Files in scope (READ):** PRODUCT.md, DESIGN.md, CLAUDE.md, the target template, supporting routes/services, related CSS sections, the live-state context builder (`core/main/home_context.py` for state-bearing pages).

**Tasks** (this checklist describes the canonical iteration shape — every iteration session resets these to `[ ]` in its own commit when starting; the checked state above is from S2.1.1, the first iteration that ran end-to-end under this pattern):

- [x] **Step 0: Pick up §0.4 backlog items tagged `[Sx.y.N-1 in-surface]` for this surface** (if this is iteration 2+). Treat them as the iteration's primary agenda before running the fresh critique.
- [x] **Step 1: Boot dev server, capture before-screenshots at desktop + mobile.** Save under `.impeccable-review/<session-id>/before/`.
- [x] **Step 2: Run `$impeccable critique <target>`.** Two-assessment workflow per the impeccable critique reference. Sub-agent for design review (with content-fingerprint proof per §1.2); deterministic detector; combined report.
  - **Detector scope guidance (calibrated against S2.1.2):** run `npx impeccable --json --fast` against the **source template files** (the surface's `.html` partials), NOT against an inlined-CSS HTML snapshot. Inlined snapshots include the entire `style.css`, so the detector flags rules from outside the surface scope (S2.1.2 saw 10 hits, all from picks-accordion / champion-banner / navbar that weren't in scope). When you do want to detect inline-style issues on the rendered page, run the detector against the inlined snapshot and cross-reference each hit against the surface's namespace before triaging.
  - **Tap-target sweep as a deterministic in-Step-2 check.** Inside the critique, sweep all `<a>`, `<button>`, and clickable container rects in the surface for `min-height < 44px || min-width < 44px`. P0 S0.3 globalized chrome (subnav, navbar, leaderboard cards), but surface-scoped utilities recur — S2.1.1 missed `.home-shell .sec-head .more` (caught by S2.1.2). Use a Playwright MCP `browser_evaluate` one-liner: `Array.from(document.querySelectorAll('a, button, [role="button"], [onclick]')).map(el => { const r = el.getBoundingClientRect(); return r.height < 44 || r.width < 44 ? { sel: el.outerHTML.slice(0, 80), w: Math.round(r.width), h: Math.round(r.height) } : null; }).filter(Boolean)`.
- [x] **Step 3: Read the report; decide which Priority Issues land in this iteration.** Items beyond the 3-5 budget go to §0.4 with `[in-surface]` / `[cross-cluster]` / `[cross-phase]` / `[deferred-data]` tag per §0.4 routing matrix.
- [x] **Step 4: For each Priority Issue, execute its recommended impeccable command.** `$impeccable shape <component>`, `$impeccable clarify <copy>`, `$impeccable adapt <responsive>`, etc.
- [x] **Step 5: Add iteration-specific regression tests** under `tests/test_design_p2_s2_<surface>_<iteration>.py` (e.g., `test_design_p2_s2_1_2.py` for S2.1.2). Lock the most important shape decisions in source.
- [x] **Step 6: Capture after-screenshots** under `.impeccable-review/<session-id>/after/`.
- [x] **Step 7: Re-run `$impeccable critique <target>`.** Record score delta.
- [x] **Step 8: Check §1.5b convergence gate** (4 conditions). If all pass → mark surface converged in §9 rollup; next session moves to the next surface. If any fail → next session is `S2.<surface>.N+1` on the same surface.
- [x] **Step 9: Run `pytest`. Commit.**

### Surface inventory (each iterates per §1.5b until converged)

- [ ] **S2.1 — `home_shell.html` + `_home_live.html`** (the World Cup home in live state). Cross-cutting note: this surface uses `core/main/home_context.py` builders. Critique covers the page state but execution may need the partials in `core/main/templates/main/_home_live.html` plus `_dossier_card.html` / `_fixture_card.html`.
  - [x] **S2.1.1** done (commit `e69966f`). Heur 26→30/40, audit 15→17/20, anti-pat 5→0. Fixed: gradient-text + hero-metric absolute bans, identical-card grid, "this week" copy lie, banned `stage|title`. **Convergence gate: failed** (heur 30 < 32 floor; 6 in-surface backlog items remain). Next: S2.1.2.
  - [x] **S2.1.2** done. Heur 28→32/40 (re-critique baseline), audit 16→18/20, anti-pat 0 (held). Fixed: section-more 44×44 tap-target floor, dossier-stamp Tribune voice + in-flow position (closes mobile rank-meta overlap), right-rail starvation (Recent Results + Commish lifted to full-width rows below dossier/leaderboard side-by-side, with Bootstrap `order-*` preserving mobile reading order), "Also Today" eyebrow rename. **Convergence gate: PASS** (zero P0, zero unrouted P1 — two soft P1s deferred to S2.1.3 with `[in-surface]` rationale, 0 anti-pat hits, heuristics 32/40 hits the floor). Surface S2.1 marked converged below.

- [x] **S2.2 — `schedule.html`** (converged 2026-05-08 in S2.2.1). The "live mode" Priority Issues at first iteration turned out to be: (1) chronologically-interleaved group stage that fired the group_letter divider 48 times across the page as a per-match label rather than as a section separator, (2) no live-state framing — the page rendered identically out/pre/live/post, (3) date-and-time per-row stamp `'%-m/%-d %-I:%M%p'` that omitted day-of-week and duplicated date info, (4) 48 inline-styled H4 group dividers that bypassed the eyebrow primitive, (5) opaque match-points-chip with no legend or tooltip, (6) `&middot;` and `&ndash;` HTML entities. Live-dot / live-vs-final differentiation didn't surface — the schedule template has no in-progress concept and the existing completed/pending dichotomy is sufficient.
  - [x] **S2.2.1** done. Heur 19→30/40, audit ~11→16/20, anti-pat 4→0. Fixed: matchday grouping (route now passes `matchdays_group` instead of flat `group_matches`), `.is-today` modifier + `id="today"` deep-link anchor, `.schedule-day-header` primitive (replaces 48 inline-styled H4s), per-row stamp time-only (`'%-I:%M %p'`), match-group-tag badge with `aria-label="Group X"`, match-points-chip `title=` tooltip, `.schedule-legend` microcopy, `--text-muted` → `--text-secondary` AA bump on day-header / legend / group-tag, entity sweep. **Convergence gate: PASS** on first iteration. Surface S2.2 marked converged below.

- [x] **S2.3 — `team_detail.html`** (converged 2026-05-08 in S2.3.1). The "live ownership ribbon / score events / per-match column" predictions partially landed (per-match unit consistency was already locked by `tests/test_worldcup_team_detail.py::test_team_detail_fixture_pts_apply_multiplier`); the actual first-iteration Priority Issues were: (1) hero-metric template adjacency — four equal-weight 1.6rem stat tiles (Tier · Multiplier · Base · Scored) fired the SaaS cliché even when each tile carried distinct data; (2) path-to-crown 6-tile row encoded status (won/current/eliminated/future) by color alone, with `current` and `future` carrying no icon (PRODUCT.md a11y rule); (3) mobile fixture-row flag/code overlap at the squeezed 1fr column + dead Pts column claiming ~12% horizontal on un-played rows; (4) `.picker-link` ~28px tall on mobile (regression of P0 S0.3's 44×44 floor); (5) Bootstrap `.text-muted` micro-copy on the dark-navy `.card.wc-card` substrate failing AA; (6) the user's own team felt indistinguishable from any other team beyond the red-tinted ownership ribbon. The owned-state celebration delta (ceiling-rank-among-picks comparator) and the projected-ceiling group-relative comparator both routed forward to S2.3.2 because they require new route-level data; pre-tournament empty-state shell routed forward for the same reason; eyebrow-primitive saturation routed to S2.6 cross-cluster.
  - [x] **S2.3.1** done. Heur 24→31/40 (Δ +7), audit 14→18/20 (Δ +4), anti-pat 0→0 (held). Fixed: hero re-shape (one dominant Scored numeral at 2.6rem, multiplier chip inline, Base × Multiplier as Newsreader derivation, duplicate Tier tile moved up onto eyebrow line); owned-state via Voice in Copy (`Your pick · ` eyebrow prefix) + warmer `wc-hero-grad-owned` radial variant; path-to-crown `<ol>+<li>` semantics + `aria-current="step"` + per-status icons (won → check, current → record-circle pulse, eliminated → x, future → empty circle), pulse gated under `prefers-reduced-motion`; mobile fixture-row 3-col collapse for `.fixture-row-pending`, named flag/code flex children with explicit gap, empty pts cell as `aria-hidden visibility:hidden` desktop spacer, surface-scoped `.fixture-stage-date / .fixture-vs / .fixture-tbd` replacing Bootstrap `.text-muted` on dark navy, entity sweep on `&ndash;` / `&middot;`; `.picker-link` 44×44 floor (`min-height: 44px` + `inline-flex` + `:focus-visible` outline), grid step 160→140px so two pills seat at 375; freebie `.ownership-ribbon-blurb` scoped color so AA holds against navy substrate. **Convergence gate: PASS** (0 P0, 0 unrouted P1 — 5 P2/P3 routed forward via §0.4, 0 anti-pat hits, heuristics ≥ baseline+6 [30 floor, 31 actual]). Surface S2.3 marked converged below.

- [x] **S2.4 — `stats.html`** (converged 2026-05-09 in S2.4.1). The "stats-curious vs analyst register layering" prediction landed (PI-3 lead-card variant + eyebrow primitive + Newsreader masthead derivation closed it); table semantics didn't surface (the surface has no `<table>` — it's div-based bar/list/row UI). The actual first-iteration Priority Issues were: (1) `--text-muted` (3.59:1 on white card) sub-AA across every card-interior microcopy slot — KPI labels, sub-lines, card-head asides, chart axis ticks; (2) hero-metric-template *adjacency* fired twice on one page (Board 4-tile band + Tiers 5-tile band, exactly the §1.5b lesson from S2.3.1 that 3+ equal-weight numerals trip the SaaS reflex even with distinct data); (3) 15 `.wc-stat-card` instances all white + 1px border + same shadow + same Teko head — the identical-card-grid silhouette ban; (4) bare `T#` tier badges in row scan paths (Top Scorers / Carrying / Dead Weight / Combos) demanding recall instead of recognition, with no nearby legend. The T1 amber badge AA fail (3.19:1), phase-aware copy on the masthead, bubble-chart "my picks" filter, Carrying/Dead-Weight side-by-side, and T2 Tier Pairs explanatory copy all routed forward to S2.4.2 (each requires either token spec change, route-side data plumbing, or new affordance JS — too big for the same iteration's atomic-edit budget). Inline-Teko duplication and double-elevation on `.wc-stat-card` routed to S2.6 cross-cluster. Markup-as-icon ✓/← in progress bar routed to S6.1 cross-phase.
  - [x] **S2.4.1** done. Heur 19→32/40 (Δ +7), audit 9→14/20 (Δ +5), anti-pat 3→0. Fixed: `--text-muted` → `--text-secondary` sweep (CSS rules + ~12 inline strings + chart `TICK_COLOR`; rendered ratios sampled at 7.15:1 / 6.23:1 / 15.07:1, well above AA); both KPI bands collapsed (Board → `.wc-stats-masthead` with one dominant Teko numeral + Newsreader serif derivation prose, max-width 60ch; Tiers → `.wc-stats-ledger` horizontal strip with gold-rule top + per-cell border + 5 `.wc-stats-ledger-cell` flex children, mobile reflows 50%); `.wc-stat-card.is-lead` variant (gold-rule top, no body border) on Top Scorers (Board, "The lead" eyebrow), Popularity vs. Score (Field, "The map"), Pick Distribution by Tier (Tiers, "The cross-section") — breaks the 15-identical-card silhouette; `tb()` (T#) → `tbl()` (T# · Name) in `renderScoring` / `renderImpact` help+hurt lists, `tb()` preserved in `pbarHtml` only (where the surrounding `tierHeader` names the tier) and given `aria-label="Tier N · Name"` for SR; freebies — `&middot;` entity sweep, "Pts" → "Points" on Board card heads, ★ glyph wrapped `aria-hidden="true"` plus `.visually-hidden` SR text "your pick"/"your picks", hero-subtitle alpha .6→.7, inline `#1A7A45` "carrying" emphasis bumped to `#125F36` for ~6.5:1 at small bold. **Convergence gate: PASS** (0 P0, 0 unrouted P1 — 5 in-surface routed to S2.4.2, 2 cross-cluster routed to S2.6, 1 cross-phase routed to S6.1, 2 ship-as-is, 0 anti-pat hard hits, heuristics 32 ≥ baseline+6 [25 floor]). Surface S2.4 marked converged below.

- [x] **S2.5 — `player_detail.html`** (converged 2026-05-10 in S2.5.1). The "rivalry framing / you-vs-them comparison shape / pre-post-deadline differential" predictions partially landed at first iteration (PI-2 Newsreader derivation prose now carries the rivalry framing voice "Leads the table. 117.0 ahead of next." / "Trails leader by X, Y ahead of next."; the structural you-vs-them comparison strip routed forward to S2.5.2 because it needs a new `compute_comparison` route helper). The actual first-iteration Priority Issues were: (1) Bootstrap-on-`.card.wc-card` contrast catastrophe — the entire 18-row picks table rendered invisible (computed `<td>` color `rgb(33,37,41)` on `rgba(0,17,46,.8)` navy substrate) because legacy CSS at `style.css:2378-2386` assumed a *light* card surface that never existed; same systemic issue surfaced inline-eyebrow color, pick-event-stage, accordion-toggle, score-events-total/empty, and the cluster-3 surgical-exclusion at `style.css:5444` actively forced dark-on-dark on the "Grp X" microcopy; (2) hero-metric template adjacency — three equal-weight 1.6rem numerals (Total · Lead · Tiebreak) in a flex row, the exact pattern S2.3.1 locked out of team_detail and that project memory `project_ccc_wc_reskin_gotchas.md` flagged as the SaaS-reflex trap "even with distinct data"; (3) Tiebreak rendered as a bare integer `12` with no unit, hero "Lead: none" reading as a missing value not a rank-1 state; (4) bare `T#` tier badges in the pick rows (same recall-not-recognition pattern S2.4.1 retired via `tb()` → `tbl()` on stats.html) — and the `tiers` dict was already passed to the template, just unconsumed. Rivalry comparison strip, "Roster sealed" empty-state re-shape, and above-fold wrapper-nesting reduction routed forward to S2.5.2.
  - [x] **S2.5.1** done. Heur 21→31/40 (Δ +10), audit 13→17/20 (Δ +4), anti-pat 2→0. Fixed: contrast lock on `.card.wc-card` dark substrate — replaced the stale "light card" overrides at `style.css:2378-2386` with `.player-picks-desktop .table-worldcup > tbody > tr > td { color: var(--text-on-dark); background-color: transparent; }` to defuse Bootstrap's `--bs-table-bg` white-cell forcing, lifted `:hover > td` to bone-wash `rgba(245,241,232,.04)`, scoped `.team-link` to bone with gold-light hover, beat the cluster-3 `.text-muted` surgical-exclusion with a compound-class counter-rule (`.card.wc-card.player-picks-desktop .table-worldcup > tbody > tr > td .text-muted`) so "Grp X" microcopy reads `--bone-mute`, re-tinted `.pick-accordion` panel from `rgba(0,40,104,.03)` (navy-on-navy) to bone wash with `rgba(245,241,232,.14)` dashed border, lifted `.pick-accordion-toggle` to bone-mute (rest) + gold-light (open/hover) with `:focus-visible` color, lifted `.score-events-total` / `.score-events-empty` / `.pick-event-stage` to bone-mute, deleted the orphaned `.score-events-list` block; hero re-shape mirrors S2.3.1's `.team-hero-line` lock — replaced the 3-equal-weight `1.6rem` `.player-hero-stats` grid with `.player-hero-line` carrying one dominant `2.6rem` `.player-hero-score-value` numeral plus Newsreader `.player-hero-derivation` prose for rivalry framing ("Leads the table." / "Trails leader by X, Y ahead of next." / "Trails leader by X."), Tiebreak moved off the masthead onto the eyebrow line as `.player-hero-tiebreak` chip with explicit unit ("Tiebreak 12 US goals") and `aria-label="Tiebreaker: N US goals predicted"`, hero avatar emoji + decorative tier dot + flag emoji marked `aria-hidden`; tier names replace bare `T#` in both desktop `_pick_row.html` and mobile `.player-pick-card` via `{{ tiers[pick.tier].name }}` (Favorites / Contenders / Dark Horses / Underdogs / Wildcards); freebie discovered during verify — `.player-pick-card .wc-eyebrow` was inheriting `--bone-mute` (dark-surface token) but the mobile card is white (`--bg-card`), lifted to `--text-secondary` per memory `project_text_muted_aa_on_bone`. **Convergence gate: PASS** (0 P0, 0 unrouted P1 — 3 P1s routed forward via §0.4: PI-3 rivalry comparison strip [needs `compute_comparison` route helper], PI-6 "Roster sealed" empty-state re-shape [needs un-priv probe], PI-7 above-fold density / 6-deep wrapper reduction — all to S2.5.2 in-surface; 0 anti-pat hits, heuristics 31 ≥ baseline+6 [27 floor]). Surface S2.5 marked converged below; the prediction "rivalry framing" surfaced exactly as expected in PI-3 routed forward.

- [ ] **S2.6 — Cross-cluster live polish (NOT cluster mop-up).** Runs only after S2.1–S2.5 have all converged per §1.5b. **Step 0:** sweep §0.4 for items tagged `[Sx.y.N cross-cluster]` and route them as agenda. **Step 1:** identify patterns visible only when comparing 2+ live-cluster surfaces — visual-rhythm consistency across `_home_live` / `schedule` / `team_detail`, repeated chrome treatments, eyebrow-primitive consistency, cross-surface motion language. Cap: 3-5 cross-surface findings. **Step 2:** re-run `$impeccable critique` against each S2.1–S2.5 surface (and the leaderboard, in case live-cluster shared-chrome work bled into it). Confirm none regressed. **Step 3:** open PR `Impeccable P2 — Live state cluster`. S2.6 is **not** the place for surface-internal polish — that work was done in each surface's own iteration loop. If S2.6 finds an in-surface P0/P1, route it back to a `S2.x.N+1` iteration before opening the PR.

---

## 5. Phase 3 — Global chrome + auth + errors (3 surfaces + cluster polish, iterative)

Same iterative model as P2 (per §1.5b). Global chrome runs before pre/post-state cluster work because every state-bearing surface inherits the chrome — fixing chrome first means later state-cluster sessions don't fight chrome regressions.

### Surface inventory (each iterates per §1.5b until converged)

- [ ] **S3.1 — `templates/base.html` (navbar, footer, sub-nav slot, body class flow).** This sets the chrome every other surface inherits. Likely Priority Issues at first iteration: navbar dropdown a11y, footer voice/utility split (DESIGN.md defines the two-band structure), sub-nav scroll behavior on mobile, navbar-scrolled compaction smoothness.
  - [ ] **S3.1.1** — first iteration.
  - [ ] **S3.1.N** — until convergence.

- [ ] **S3.2 — Auth pages cluster.** `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `change_password.html`, `profile.html`. Run a single `$impeccable critique` per page (they're small, batch is feasible). Likely Priority Issues at first iteration: auth-page Tribunal Black backdrop atmosphere, focus management, error message voice, password-reset-token UX.
  - [ ] **S3.2.1** — first iteration.
  - [ ] **S3.2.N** — until convergence.

- [ ] **S3.3 — Platform home (`core/main/templates/main/index.html`) + non-state component partials.** Biggest single template by partial-count. The home page dispatcher critiques separately from the four state partials (which are covered in P2/P4/P5). This surface focuses on the dispatcher and any partials not already touched (e.g., `_game_card.html`, `_game_tiles_compact.html`).
  - [ ] **S3.3.1** — first iteration.
  - [ ] **S3.3.N** — until convergence.

- [ ] **S3.4 — Errors + cross-cluster polish (NOT cluster mop-up).** Runs only after S3.1–S3.3 converge. Combines: (a) `404.html` / `500.html` first-iteration critique (these are small enough that one iteration usually converges them), (b) cross-cluster polish per the S2.6 model — patterns visible only when comparing 2+ chrome surfaces. **Step 0:** sweep §0.4 for `[Sx.y.N cross-cluster]` items routed to S3.4. **Step 1:** errors first-pass critique + fix. **Step 2:** cross-cluster polish (cap 3-5 findings). **Step 3:** re-run `$impeccable critique` against S3.1–S3.3 + errors; confirm no regressions. **Step 4:** open PR `Impeccable P3 — Global chrome + auth + errors`. If S3.4 finds an in-surface P0/P1, route to that surface's `Sx.y.N+1` iteration before opening the PR.

---

## 6. Phase 4 — Pre-live state cluster (4 surfaces + cluster polish, iterative)

Same iterative model as P2/P3.

### Surface inventory (each iterates per §1.5b until converged)

- [ ] **S4.1 — `_home_pre.html` + `_home_out.html`** (the World Cup home in pre states). Likely Priority Issues at first iteration: countdown card emotional fatigue if user visits often, ballot card readability, Tribute Window framing.
  - [ ] **S4.1.1** — first iteration.
  - [ ] **S4.1.N** — until convergence.

- [ ] **S4.2 — `picks.html` + `_pick_row.html`** (the pick UI cluster). This is the highest-stakes pre-live surface; users spend the most time here. Likely Priority Issues at first iteration: pick accordion UX (the `transition: max-height` finding from the leaderboard detector applies here), tier visualization, multiplier explanation, save/lock affordance, mobile single-handed pick flow. Expect 3+ iterations on this surface; it's the densest in the cluster.
  - [ ] **S4.2.1** — first iteration.
  - [ ] **S4.2.N** — until convergence.

- [ ] **S4.3 — `join.html` + `rules.html`**. Lower-frequency but first-impression critical. Likely Priority Issues at first iteration: rules typography (long-form Newsreader prose), join CTA voice, scoring system explanation depth.
  - [ ] **S4.3.1** — first iteration.
  - [ ] **S4.3.N** — until convergence.

- [ ] **S4.4 — `groups.html`**. Likely Priority Issues at first iteration: group fixture grid density, country-flag legibility, mobile column collapse, table semantics.
  - [ ] **S4.4.1** — first iteration.
  - [ ] **S4.4.N** — until convergence.

- [ ] **S4.5 — Cross-cluster pre-live polish (NOT cluster mop-up).** Runs only after S4.1–S4.4 converge. **Step 0:** sweep §0.4 for `[Sx.y.N cross-cluster]` items routed to S4.5. **Step 1:** identify cross-cluster patterns (visual-rhythm consistency between countdown / picks / join / groups; shared chrome treatments; deadline-related copy register across surfaces). Cap 3-5 findings. **Step 2:** re-run `$impeccable critique` against S4.1–S4.4; confirm no regressions. **Step 3:** open PR `Impeccable P4 — Pre-live state cluster`.

---

## 7. Phase 5 — Post-live state cluster (2 surfaces + cluster polish, iterative)

Same iterative model as P2/P3/P4.

### Surface inventory (each iterates per §1.5b until converged)

- [ ] **S5.1 — `_home_post.html`** (the World Cup home in post state). Likely Priority Issues at first iteration: champion banner emotional payoff, retrospective tone, "the club will remember" voice from DESIGN.md's North Star.
  - [ ] **S5.1.1** — first iteration.
  - [ ] **S5.1.N** — until convergence.

- [ ] **S5.2 — Post-state component partials.** `_champion_banner.html`, `_dispatches.html`, `_commish_note.html`, `_recent_results.html` (post variant). The shared partials get their own surface because they're used across multiple post-state contexts. Likely Priority Issues at first iteration: champion typographic moment, dispatches narrative voice, commish note signature.
  - [ ] **S5.2.1** — first iteration.
  - [ ] **S5.2.N** — until convergence.

- [ ] **S5.3 — Cross-cluster post-live polish (NOT cluster mop-up).** Runs only after S5.1–S5.2 converge. **Step 0:** sweep §0.4 for `[Sx.y.N cross-cluster]` items routed to S5.3. **Step 1:** cross-cluster patterns (champion-moment vs. recap-prose register, post-state Tribune voice consistency, retrospective-vs-celebratory tonal balance). Cap 3-5 findings. **Step 2:** re-run `$impeccable critique` against S5.1–S5.2; confirm no regressions. **Step 3:** open PR `Impeccable P5 — Post-live state cluster`.

---

## 8. Phase 6 — Final polish + scorecard (iterative)

### S6.1 — Cross-phase polish (cross-surface patterns spanning multiple clusters)

**Goal:** Address patterns visible only when comparing across clusters — chrome treatments shared between live/pre/post home variants and auth, cross-game palette consistency, recurring component silhouettes (e.g., the 7-component gradient-card repeat surfaced by S2.1.1). NOT a final mop-up of single-surface issues; those are caught by per-surface convergence in P2-P5.

- [ ] **Step 0: Sweep §0.4 for `[cross-phase]` items.** Every backlog item tagged for S6.1 goes here as the agenda. Plus any `[ship-as-is]` items needing a final review.
- [ ] **Step 1: Inventory the cross-phase patterns surfaced during P2-P5.** Group findings by pattern, not by surface — the goal is to spot what repeats across clusters.
- [ ] **Step 2: Run `$impeccable polish` per cluster** as a final sweep. Don't run per-template; run per-state-cluster (live, pre, post, global). Cap 3-5 findings per polish run.
- [ ] **Step 3: Resolve cross-phase findings.** Each fix should land on every surface that exhibits the pattern, not just one.
- [ ] **Step 4: Re-run `$impeccable critique` on the four Tier 1 exemplars** (leaderboard, home_shell live, picks, base.html). Record final scores. Confirm no regressions on previously-converged surfaces.
- [ ] **Step 5: Iterate per §1.5b** if any Tier 1 exemplar regressed or remains below convergence. S6.1 itself can fan into S6.1.1 / S6.1.2 / etc.
- [ ] **Step 6: Run full pytest.** Green.
- [ ] **Step 7: Commit polish.**

### Session S6.2 — Scorecard, handoff doc, merge

**Goal:** Document the project's outcomes. Merge `design/wc-polish` → `main`.

- [ ] **Step 1: Write a project scorecard.** Save under `docs/superpowers/specs/2026-XX-XX-impeccable-design-improvement-scorecard.md`. Include:
  - Baseline scores per Tier 1 exemplar (Tier 1: 23/40, 11/20).
  - Final scores per Tier 1 exemplar.
  - Anti-patterns count: before/after.
  - Cumulative findings closed.
  - Backlog items deferred (with rationale).
  - Lessons learned for future impeccable work.
- [ ] **Step 2: Update CLAUDE.md if any patterns warrant locking** (e.g., the new Tribune sidebar shape if it becomes a reusable component, the rank-delta helper, the regression-test patterns).
- [ ] **Step 3: Open final PR** `Impeccable P6 — Final polish + project close`.
- [ ] **Step 4: Merge `design/wc-polish` → `main`** after PR review.
- [ ] **Step 5: Tag the release** (e.g., `impeccable-v1`).

---

## 9. Session checklist (update as you go)

Mark each session as it completes. Append the session-completion commit SHA for traceability. Iterations under the §1.5b model nest under their parent surface row; each iteration is its own line with its own commit hash. A surface is "done" when its convergence gate passes — flip the parent row `[x]` only then.

### Phase 0 — Cross-cutting harden
- [x] S0.1 — Bootstrap shadow leak migration (commit: 60aee97)
- [x] S0.2 — Side-stripe ban migration + table semantics sweep (commit: e4882ca)
- [x] S0.3 — Mobile tap-target floor + white-on-gold contrast + em-dash sweep (commit: 37a57cf)
- [x] **PR P0** opened: `#11`

### Phase 1 — Leaderboard close
- [x] S1.1 — Shape Your Standing + trend rank-delta + clarify copy (commit: 56416ee)
- [x] **PR P1** opened: `#12`

### Phase 2 — Live state cluster
- [x] **S2.1** — `home_shell` + `_home_live` (converged: 2026-05-08, S2.1.2)
  - [x] S2.1.1 (commit: e69966f) — heur 26→30/40, audit 15→17/20, anti-pat 5→0. Gate: failed (heur < 32 floor; 6 in-surface backlog).
  - [x] S2.1.2 (commit: 296a122) — heur 28→32/40 (re-critique pre/post), audit 16→18/20, anti-pat 0→0. Gate: **PASS** (0 P0, 0 unrouted P1, 0 anti-pat, heur ≥ 32). 4 of 6 inherited backlog items closed; 2 routed forward (sparkline delight + a11y polish) to S2.1.3.
- [x] **S2.2** — schedule (converged: 2026-05-08, S2.2.1)
  - [x] S2.2.1 (commit: d8b0f10) — heur 19→30/40 (Δ +11), audit ~11→16/20 (Δ +5), anti-pat 4→0. Gate: **PASS** (0 P0, 0 P1, 0 anti-pat, heur ≥ baseline+6 [25 floor, 30 actual]). 4 P2/P3 routed forward (3 to S2.6 cross-cluster live framing, 1 to S6.1 cross-phase `<time datetime>` semantic harden).
- [x] **S2.3** — team_detail (converged: 2026-05-08, S2.3.1)
  - [x] S2.3.1 (commit: 7e44752) — heur 24→31/40 (Δ +7), audit 14→18/20 (Δ +4), anti-pat 0→0. Gate: **PASS** (0 P0, 0 unrouted P1, 0 anti-pat, heur ≥ baseline+6 [30 floor, 31 actual]). 5 P2/P3 routed forward (3 to S2.3.2 [in-surface] for comparator + state-shell + ceiling-rank, 1 to S2.6 [cross-cluster] for eyebrow saturation, 2 [ship-as-is] for bottom back-link + tier-1 multiplier-token coincidence).
- [x] **S2.4** — stats (converged: 2026-05-09, S2.4.1)
  - [x] S2.4.1 (commit: 8b3ef65) — heur 19→32/40 (Δ +7), audit 9→14/20 (Δ +5), anti-pat 3→0. Gate: **PASS** (0 P0, 0 unrouted P1, 0 anti-pat, heur ≥ baseline+6 [25 floor, 32 actual]). 10 P2/P3 routed forward (5 to S2.4.2 [in-surface] for T1 badge AA + phase-aware copy + bubble filter + Carrying/Dead-Weight pairing + T2 Tier Pairs explanatory copy, 2 to S2.6 [cross-cluster] for inline-Teko duplication + double-elevation on .wc-stat-card, 1 to S6.1 [cross-phase] for progress-bar markup-as-icon aria-label, 2 [ship-as-is] for backend phase-chip artifact + wc-still-in/T-badge weight collision).
- [x] **S2.5** — player_detail (converged: 2026-05-10, S2.5.1)
  - [x] S2.5.1 (commit: db51590) — heur 21→31/40 (Δ +10), audit 13→17/20 (Δ +4), anti-pat 2→0. Gate: **PASS** (0 P0, 0 unrouted P1, 0 anti-pat, heur ≥ baseline+6 [27 floor, 31 actual]). 4 P1s routed forward (3 to S2.5.2 [in-surface] for rivalry-comparison strip [needs `compute_comparison` route helper] + "Roster sealed" empty-state re-shape [needs un-priv probe] + above-fold density / 6-deep wrapper reduction, 1 to S2.6 [cross-cluster] for the latent `.card.wc-card .table` Bootstrap-on-navy contrast risk that the cluster-3 surgical-exclusion `style.css:5444` would let resurface on any future dark-table surface without white-td masking).
- [x] **S2.6** — cross-cluster live polish (commit: ____). 4 §0.4 [cross-cluster] items CLOSED, 3 re-routed to S6.1 cross-phase polish, 1 re-routed to P4.5 pre-live cross-cluster polish (per S2.6 Step 1 cap 3-5; 4 PIs landed). Closed: (PI-1) Bootstrap-on-`.card.wc-card .table` contrast safety lock via `--bs-table-bg: var(--bg-card)` defensive default — makes the white-td masking a CCC-owned design decision rather than an implicit Bootstrap default; surfaces that want dark navy bleed-through still opt out via scoped `background-color: transparent` on `> tbody > tr > td` (the canonical `.player-picks-desktop` pattern). (PI-3) `.text-muted` Bootstrap gray (`#6c757d`) retired on light live-cluster surfaces in favor of CCC purple-tinted `--text-secondary` (`#5A5470`) — schedule stage-count `<small>` (×2) keeps the `.schedule-stage-count` class only (no Bootstrap `text-muted`) with scoped color, team_detail no-fixtures empty state lifted to `.team-fixtures-empty`, team_detail path-to-crown explainer lifted to `.team-path-fineprint`, both resolved to `--text-secondary` via a shared CSS rule. (PI-4) `.schedule-jump-today` pill chip in the schedule `.page-hero` linking to the S2.2.1 `id="today"` anchor, guarded by a `selectattr('is_today')` template filter so it disappears pre/post-tournament — closes the live-state surfacing gap where the today block sat 6-11 matchdays into the page. (PI-2, decided no-op) double-elevation on `.wc-stat-card` / `.your-standing-tribune` is **not** a violation — DESIGN.md §4.4 "Lift-At-Rest Rule" and §6 card primitive explicitly mandate `1px solid var(--border)` + `--shadow-sm` at rest; the impeccable generic "single-elevation" heuristic is overridden by the committed policy. Re-routed to S6.1: (a) gradient-card silhouette across home variants (needs pre/live/post comparison after P4/P5); (b) leaderboard rolls non-interactive `<div>` (paired with player_detail rivalry-comparison-strip work in S2.5.2); (c) `.wc-eyebrow` saturation + `.wc-meta-label` primitive ratification (needs cross-phase comparison after every surface family has rendered through ≥1 iteration). Re-routed to P4.5: inline-Teko `.wc-microcaption` utility extraction (S2.6 grep verified the duplication exists only in stats.html + picks.html / rules.html / join.html — extracting now would consolidate stats.html alone and need a second migration pass when P4 lands). 8 Layer A regression tests added under `tests/test_design_p2_s2_6.py`; pytest green (404 passed). Live computed-style verification on schedule (chip 216×44, color `rgb(243,239,230)`, `min-height: 44px`, `href="#today"`; stage-count `rgb(90,84,112)`), team_detail (path-fineprint `rgb(90,84,112)`), leaderboard (`--bs-table-bg = #FFFFFF`), player_detail (`--bs-table-bg = #FFFFFF` set, explicit `background-color: transparent` from S2.5.1 wins). Screenshots under `.impeccable-review/S2.6/after/`. Per §1.5b: S2.6 is not a per-surface iteration so no convergence gate applies; the bar is "all S2.1–S2.5 surfaces hold; no in-surface P0/P1 surfaced" — held.
- [ ] **PR P2** opened: ____

### Phase 3 — Global chrome + auth + errors
- [ ] **S3.1** — base.html chrome (converged: ___)
  - [ ] S3.1.1 (commit: ____). Gate: ____.
  - [ ] S3.1.N (commit: ____). Gate: ____.
- [ ] **S3.2** — auth cluster (converged: ___)
  - [ ] S3.2.1 (commit: ____). Gate: ____.
  - [ ] S3.2.N (commit: ____). Gate: ____.
- [ ] **S3.3** — platform home + partials (converged: ___)
  - [ ] S3.3.1 (commit: ____). Gate: ____.
  - [ ] S3.3.N (commit: ____). Gate: ____.
- [ ] **S3.4** — errors + cross-cluster chrome polish (commit: ____)
- [ ] **PR P3** opened: ____

### Phase 4 — Pre-live state cluster
- [ ] **S4.1** — `_home_pre` + `_home_out` (converged: ___)
  - [ ] S4.1.1 (commit: ____). Gate: ____.
  - [ ] S4.1.N (commit: ____). Gate: ____.
- [ ] **S4.2** — picks + _pick_row (converged: ___)
  - [ ] S4.2.1 (commit: ____). Gate: ____.
  - [ ] S4.2.N (commit: ____). Gate: ____.
- [ ] **S4.3** — join + rules (converged: ___)
  - [ ] S4.3.1 (commit: ____). Gate: ____.
  - [ ] S4.3.N (commit: ____). Gate: ____.
- [ ] **S4.4** — groups (converged: ___)
  - [ ] S4.4.1 (commit: ____). Gate: ____.
  - [ ] S4.4.N (commit: ____). Gate: ____.
- [ ] **S4.5** — cross-cluster pre-live polish (commit: ____)
- [ ] **PR P4** opened: ____

### Phase 5 — Post-live state cluster
- [ ] **S5.1** — `_home_post` (converged: ___)
  - [ ] S5.1.1 (commit: ____). Gate: ____.
  - [ ] S5.1.N (commit: ____). Gate: ____.
- [ ] **S5.2** — post-state component partials (converged: ___)
  - [ ] S5.2.1 (commit: ____). Gate: ____.
  - [ ] S5.2.N (commit: ____). Gate: ____.
- [ ] **S5.3** — cross-cluster post-live polish (commit: ____)
- [ ] **PR P5** opened: ____

### Phase 6 — Final polish
- [ ] **S6.1** — cross-phase polish (converged: ___)
  - [ ] S6.1.1 (commit: ____). Gate: ____.
  - [ ] S6.1.N (commit: ____). Gate: ____.
- [ ] S6.2 — scorecard + merge (commit: ____)
- [ ] **PR P6** opened: ____
- [ ] **Merge `design/wc-polish` → `main`**: ____
- [ ] **Tag**: `impeccable-v1`
- [ ] **Production deploy + Brad's production-launch test script run** on `main` (post-merge): ____

---

## 10. Plan self-review (preserved for future maintenance)

This section was a checklist run at plan creation. Notes preserved so future amendments to the plan can verify they don't break invariants.

**Spec coverage** — every Tier 1 leaderboard finding has a session that closes it:
- P0 systemic: shadow leak (S0.1), side-stripe (S0.2), table semantics (S0.2), mobile tap-targets (S0.3), white-on-gold contrast (S0.3), em-dash sweep (S0.3).
- P1 page-specific: Your Standing reshape (S1.1), trend rank-delta (S1.1), voice copy (S1.1), empty state (S1.1).
- Future findings from new exemplars get folded into their session's scope; cross-cutting finds go into the Backlog (§0.4) and a future session picks them up.

**Placeholder scan** — none used; cross-cutting tasks have full code, per-page tasks use the explicit "run critique then execute" framework because their specific edits depend on what critique surfaces (and pre-specifying them would be the placeholder-prediction trap the writing-plans skill warns about).

**Type consistency** — `compute_rank_delta(enrollment, window_days)` is the single new helper; tested in S1.1, consumed by `routes.leaderboard()` in the same session. Existing types untouched.

**Adaptation rule** — when a per-page critique surfaces issues that should have been cross-cutting, those issues land in the Backlog and a "P0 follow-up" mini-session may be inserted between phases. The plan is adaptive on its tail; the head (P0 systemic + P1 leaderboard close) is fixed. See §1.8 for the full deviation-is-welcome policy.

**Verification strategy** — three layers (§1.3): source-pattern locks (cheap, CI-friendly, regression net for things that are violations in source), Playwright MCP (in-session, computed/visual ground truth, no CI cost), critique re-run (holistic). All three together; no single layer is sufficient.

**Phase order** — sequenced by §0.2 priority: live > global chrome > pre-live > post-live. Global chrome (P3) runs before the state clusters (P4, P5) so chrome regressions don't fight subsequent state-cluster work.

---

## 11. Notes on impeccable command nuances

These are subtleties the `impeccable` skill and command references encode but that are easy to miss across sessions. Read this section once at the project start; refer back when uncertain.

- **`$impeccable critique` requires sub-agent isolation.** Assessment A (LLM design review) MUST run as an isolated sub-agent that does not see the deterministic detector output. Don't shortcut this; the combined-report integrity depends on it.
- **`$impeccable detect` (the CLI) does not handle Jinja templates well.** Run it against rendered HTML with linked CSS inlined (the "inlined.html" pattern from S0/S1). Alternatively, run it against a URL via Puppeteer if the dev server is up and the page is accessible without auth.
- **The deterministic detector flags "bounce-easing" and "dark-glow" as AI-slop**, but DESIGN.md explicitly defends both for narrow uses (card-hover overshoot; trophy CTA glow). When verifying detector findings, cross-reference DESIGN.md before fixing — sometimes the right action is "add a CSS comment explaining why the rule is intentional," not "remove the rule."
- **`fullPage: true` screenshots via chrome-devtools-mcp can drop content below the viewport.** When a screenshot looks suspicious, scroll to the suspect region and take a viewport-only screenshot to confirm. Don't trust fullPage as a sole visual oracle.
- **The `register: product` setting in PRODUCT.md is load-bearing.** Brand-shaped surfaces (landing, marketing, /join) tilt toward the brand register; product-shaped surfaces (leaderboard, picks) tilt product. If a session feels like it's straddling registers, re-read PRODUCT.md's "Register" field and §0.2 of `reference/brand.md` vs `reference/product.md`.
- **Voice copy is subjective.** When a copy rewrite is uncertain, write 2-3 alternatives in the session and surface them to the user as `AskUserQuestion`. Don't push a tonal call past confirmation; the user knows the group voice better than any agent.
- **Playwright MCP availability check first.** At session start, confirm `mcp__plugin_playwright_playwright__*` tools are loadable via ToolSearch. If not, fall through to `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*` — both expose `browser_navigate`, `browser_evaluate`, `browser_take_screenshot` equivalents. Don't fail the session over which MCP is reachable; pick the one that loads.
- **Auth-gated routes during Playwright probes.** The dev DB at `instance/fantasy_platform.db` carries a session cookie persisted across runs (the Tier 1 baseline session created a `review_user`). If the browser navigates and lands on `/login`, fill the form once; subsequent probes within the same session reuse the cookie. If a fresh review user is needed, follow the pattern from the Tier 1 baseline (Python script that adds a user with `username` + email + password set, season-scoped enrollment).
- **Inlining linked CSS for `$impeccable detect`.** The CLI detector won't resolve `/static/css/style.css` from a saved HTML file. Inline `tokens.css` + `style.css` into the HTML before scanning, OR point the detector at the live URL via Puppeteer (which loads CSS fully). The Tier 1 baseline used the inline approach; either is fine.
- **Auth-gated probes via temporary dev password.** The persisted dev session cookie can drift between sessions and `instance/fantasy_platform.db` does not store reusable plaintext passwords. The reliable pattern is: `User.set_password('dev-impeccable-<sid>')` for a known seeded user, drive the login form via `browser_evaluate` (`?next=/<route>` redirects post-login), then **always reset the password to `secrets.token_urlsafe(24)`** at session end so the temporary credential never lingers. Forgot-password flow recovers it for the real user.
- **Full-page Playwright screenshots can render misleadingly in tool previews.** A 1470×1242 PNG that shows "table missing" in the chat preview may be fine in the actual file — the renderer downsamples and chops content. When a screenshot looks suspicious, take an element-scoped screenshot (`browser_take_screenshot` with `target=<selector>`) of the suspect region to confirm. Don't conclude "regression" from one full-page preview; cross-reference the DOM probe (`getComputedStyle`, `getBoundingClientRect`) — the source-of-truth.

---

**End of plan.**
