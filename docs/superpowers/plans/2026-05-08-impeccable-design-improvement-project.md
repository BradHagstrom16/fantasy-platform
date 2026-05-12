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
- **[S2.4.1 cross-cluster] [S2.6 routed]** Inline-style Teko declarations duplicated ~25× across `stats.html` JS render functions (`font-family:'Teko',sans-serif;font-size:.7rem;...`). Pattern likely shared with other JS-rendered surfaces (home _home_live impact rows, leaderboard mobile cards). Extract to a `.wc-microcaption` utility set after auditing cross-surface usage. **Re-routed by S2.6:** the S2.6 grep surfaced **0** inline Teko declarations in `_home_live.html` and `leaderboard.html` — the only verified additional inline-Teko surfaces are P4 pre-live templates (`picks.html`, `rules.html`, `join.html`, 11+ instances combined). Extracting a `.wc-microcaption` utility now would consolidate stats.html alone, then need a second migration pass when the P4 surfaces are touched. Re-routed receiving session: **S4.5** (pre-live cross-cluster polish, after picks/rules/join converge), so the extraction lands once and matches the actual cross-surface usage.
- **[S2.4.1 cross-cluster] CLOSED in S2.6 (decided no-op)** `.wc-stat-card` carries both `box-shadow: var(--shadow-sm)` AND `border: 1px solid var(--border)` — double elevation. Original entry asked "pick one." **S2.6 verdict: keep both.** DESIGN.md §4.4 "The Lift-At-Rest Rule" explicitly mandates `--shadow-sm` at rest on cards ("Flat-at-rest is the wrong elevation philosophy for CCC; the Tribune is a printed object, not a wireframe") and DESIGN.md §6 defines the canonical `.card` primitive as "`var(--bg-card)` (white) fill on a Pressroom Bone page, `--radius-lg` corner radius, `1px solid var(--border)` border, `--shadow-sm` at rest, `--shadow-md` on hover with `translateY(-3px)` lift." `.wc-stat-card` and `.your-standing-tribune` both follow that primitive contract. The generic impeccable "single-encoding of elevation" heuristic is overridden by the committed DESIGN.md policy (per impeccable's own priority rule: user instructions > skill heuristics). If a future critique re-flags this, point to this §0.4 entry and DESIGN.md §4.4 / §6.
- **[S2.4.1 cross-phase]** Tournament-progress phase labels in `stats.html:302` use markup-as-icon (`✓` for done, `←` for current) without `aria-label`. Screen readers speak "check" / "left arrow", not "completed" / "current". Same pattern likely on home progress widgets (`_home_live` / pre-state countdown) and any future post-state recap progress bar. Receiving session: **S6.1** cross-phase polish.
- **[S2.4.1 ship-as-is]** Phase chip in stats hero shows "Pre-Tournament" even with `WC_FAKE_NOW` set to mid-group-stage — backend artifact (no completed matches in dev DB → `_derive_tournament_phase()` returns `pre_tournament`). Won't surface in production where match data is live. Won't be re-flagged.
- **[S2.4.1 ship-as-is]** `.wc-still-in` "Active" green chip + `.wc-tb` orange tier badge of equal size and weight in Top Scorers row split visual attention. Lower priority than the comparator + state-shell work; defer until a future critique re-flags it.
- **[S2.5.1 in-surface]** Rivalry comparison strip (you vs them). The S2.5.1 hero re-shape closed the *voice* dimension of rivalry framing (Newsreader derivation prose carries "Leads the table. 117.0 ahead of next." / "Trails leader by X, Y ahead of next."), but the structural you-vs-them comparison strip below the eyebrow line — `<viewer> trails <target> by <delta> · <N> shared picks · their edge: <team> (+<pts>)` — needs a new route-level helper `compute_comparison(viewer_enrollment, target_enrollment) -> {viewer_total, target_total, delta, shared_picks, their_advantage, your_advantage}` joined per `WorldCupPick` + season-scoped via `WorldCupEnrollment.season_year`. Suppress the strip when `viewer == target` or when viewer is logged out. Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** "Roster sealed" pre-deadline empty-state re-shape (`player_detail.html:124-136`). Current implementation is a Bootstrap icon-stack: 2.5rem bi-lock-fill at opacity .7 + `Roster sealed` eyebrow + "Picks are hidden" h5 + 2-line muted paragraph with deadline_ct. The S2.5.1 admin-session probes bypassed `picks_visible = deadline_passed or is_owner or is_admin`, so this branch was not visually rehearsed; the icon-on-navy at .7 opacity will read marginal, and the empty-state apologizes rather than rewards participation (PRODUCT.md Design Principle "Empty states reward participation"). Re-shape options: editorial "Sealed envelope" / "Locked in the vault until kickoff" frame, target avatar + name as dominant element, countdown when deadline within 7 days, replace low-opacity icon with Teko "SEALED" eyebrow or "9 PICKS LOCKED" numeric chip. Requires an un-priv viewer probe (logout + visit another player's `/worldcup/leaderboard/<id>` pre-deadline). Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** Above-fold density / wrapper reduction. The picks table currently sits at y≈481 on a 1470×900 viewport (probed) — the `.page-hero.wc-hero-grad` consumes ~280px, then `.container > .row.justify-content-center > .col-lg-8 > .card.wc-card.wc-card-flush > .card-body.p-0 > .table-responsive > <table>` adds 6 layers of wrapper before the table renders. Most of the 9 picks sit below the fold. Targeted fix: scope `.page-hero` padding compaction to player_detail (e.g., page-specific class on the hero or a `.page-hero.is-comparison` modifier) without touching the platform default; collapse `row > col-lg-8` to a `.container-md` or `max-width: 880px` inner block. The platform-global `.page-hero` padding is OUT of scope for this surface — never edit it from a per-surface iteration. Receiving session: **S2.5.2**.
- **[S2.5.1 cross-cluster] CLOSED in S2.6** Bootstrap-on-`.card.wc-card` contrast leak is a cluster-wide latent risk. The original entry routed "either lock the white-td assumption or extend the counter-rule." Closed by S2.6 PI-1: **locked the white-td assumption**. Bootstrap 5.3 supplies the white td bg via `--bs-table-bg: var(--bs-body-bg)` (default `#fff`), but the assumption was implicit. Added `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` directly above the cluster-3 surgical-exclusion at `style.css:~5485` so the masking becomes a CCC-owned design decision rather than an implicit Bootstrap default. The original `.text-muted` surgical exclusion stays intact (it now rests on a guaranteed-white substrate). Surfaces that want dark navy bleed-through still opt out via their own scoped `background-color: transparent` on `> tbody > tr > td` (see `.card.wc-card.player-picks-desktop` overrides at `style.css:2385-2416`). Live computed-style verification: leaderboard table cell `--bs-table-bg = #FFFFFF` (light substrate, fix wins) and player_detail picks table cell `--bs-table-bg = #FFFFFF` but explicit `background-color: transparent` from the S2.5.1 opt-out wins at the property level (dark substrate preserved). Locked by `tests/test_design_p2_s2_6.py::test_card_wc_card_table_pi1_locks_bs_table_bg_to_bg_card` + `..._surgical_exclusion_still_present`.
- **[S3.1.1 cross-cluster] CLOSED in S3.4** Orphan `.navbar-brand { color: var(--platform-accent) !important; }` rule at `static/css/style.css:~4019` paints the brand wordmark gold via lower-specificity `!important`, overriding `.navbar.navbar-dark .navbar-brand`'s spec-correct `var(--bone)`. Closed by **S3.4 PI-1** via option (a): orphan block deleted entirely (color, hover, font-size 1.35rem, font-weight 700, letter-spacing .08em, text-transform uppercase). Spec-correct CCC `.navbar.navbar-dark .navbar-brand` block at line 101 now wins the cascade unopposed. The load-bearing declarations from the orphan (`font-weight: 700` + `text-transform: uppercase` — the masthead voice) were folded into the CCC block so the visual norm survives without an !important fight, and DESIGN.md §5 amended to make weight 700 + uppercase explicit (Brand bullet now reads "Teko 700, 1.25rem, uppercase, letter-spacing 0.04em, Pressroom Bone color"). Trophy Rule preserved (no hover color shift on the brand wordmark; cursor change carries the affordance). Live computed-style verification (Playwright MCP, 1280 viewport, /404 page): `.navbar-brand { color: rgb(243,239,230); font-weight: 700; font-size: 20px; letter-spacing: 0.8px; text-transform: uppercase }` ✓ (was `rgb(201,162,39)` gold pre-S3.4). Locked by `tests/test_design_p3_s3_4.py::test_pi1_orphan_navbar_brand_block_removed` + `..._orphan_navbar_brand_hover_block_removed` + `..._ccc_navbar_brand_carries_full_spec` + `..._design_md_brand_spec_updated`; supersedes `tests/test_design_p3_s3_1_1.py::test_f1_navbar_brand_hover_has_no_gold_text_shadow` + `..._transition_excludes_text_shadow` (those tests retargeted to lock the new shape: no `text-shadow` in any `.navbar-brand` rule + no orphan hover block).
- **[S3.1.1 cross-cluster] CLOSED in S3.4** No explicit `:focus-visible` styling on `.navbar .nav-link` or `.subnav-pill` — keyboard focus inherited browser-default outlines, inconsistent across browsers and easy to miss on dark game-tinted subnav substrates. Closed by **S3.4 PI-2** via canonical CCC focus ring (`outline: 2px solid var(--gold-light); outline-offset: 2px; border-radius: var(--radius);` for nav-links; same minus border-radius for subnav-pills since they already carry `border-radius: 22px`). Pattern matches the S2.1.2 / S3.3.2 lock. Gold-light reads ≥ 7:1 against every chrome background (purple-700 navbar, `#00122e` WC, `#001a0d` Golf, `#0a080f` CFB). Live computed-style verification (Playwright MCP): `.navbar .nav-link:focus` → `outline: rgb(242,211,107) solid 2px; outline-offset: 2px; border-radius: 8px` ✓; `.subnav-pill:focus` → `outline: rgb(242,211,107) solid 2px; outline-offset: 2px` ✓. DESIGN.md §5 Nav Link bullet amended to call out the keyboard focus ring contract. Locked by `tests/test_design_p3_s3_4.py::test_pi2_navbar_nav_link_focus_visible_ring` + `..._subnav_pill_focus_visible_ring`.
- **[S3.1.1 cross-cluster] CLOSED in S3.4** `.game-subnav` `aria-label` missing on the container — on mobile the `.subnav-game-label` text is `display: none` via `d-none d-sm-inline-flex`, so screen-reader users on mobile lost the game-context cue. Closed by **S3.4 PI-3**: wrapper switched from `<div>` to semantic `<nav aria-label="…">` on all three game-subnav containers in `templates/base.html` (`<nav class="game-subnav subnav-worldcup" aria-label="World Cup section">`, `…subnav-golf aria-label="Golf section">`, `…subnav-cfb aria-label="CFB section">`). Semantic `<nav>` element doubles as a landmark in the SR landmarks list, so the per-game context surfaces twice (landmark label + visible inline label at `sm+`). DESIGN.md §5 Game Sub-nav bullet amended to mandate the `<nav aria-label>` shape. Live verification (Playwright MCP, /worldcup/): `document.querySelector('.game-subnav').tagName === 'NAV'` ✓, `aria-label === 'World Cup section'` ✓. Locked by `tests/test_design_p3_s3_4.py::test_pi3_game_subnav_uses_nav_element_with_aria_label` + `..._no_div_game_subnav_remains`.
- **[S3.1.1 ship-as-is]** `.subnav-game-label` `border-right: 1px solid rgba(255,255,255,.14)` is a one-off vertical-rule pattern in chrome (not codified in DESIGN.md §5). The pattern works (correctly hides when `.subnav-game-label` is `display: none` on mobile) and is too small to fold into a cluster polish session. Document as "label-to-pills separator" if S3.4 reaches it; otherwise leave alone.
- **[S3.1.1 ship-as-is]** Dropdown toggle (`.dropdown-toggle` user menu) has no `aria-label` and relies on the avatar emoji + display name for its accessible name. Screen readers will announce "soccer ball, Brad" rather than "User menu, Brad". Visible text carries semantic meaning so this passes the bar; ship-as-is. Re-evaluate only if a future SR audit re-flags it.
- **[S3.1.1 ship-as-is]** Flash region passes any Flask flash category as a Bootstrap class (`alert-{{ category }}` with a `danger`-for-`error` swap). Non-standard categories produce non-styled alerts (silent). Chrome-level defensive shaping is overreach; route to S3.4 only if a CR comment surfaces a real flashed category that won't paint.
- **[S3.2.1 in-surface]** Avatar picker on `/profile` is the wrong primitive. Nav-tabs + 5-button category strip (probed 57-108×39, fails 44 floor) + 19+ button emoji grid (probed 40×44, fails width by 4px) + inline `<style>` block (template.html:114-169) hard-coding Bootstrap-neutral hexes (`#dee2e6`, `#6c757d`) outside the CCC token system. Shape question, not a polish fix: candidates include (a) drop categories entirely with a single scrollable grid + filter, (b) convert tabs to a `.game-subnav`-style pill bar with proper 44 floor, (c) move avatar selection to a dedicated `/profile/avatar` route with a richer picker. The inline `<style>` block needs to relocate to `static/css/style.css` alongside the shape decision so token references can replace literal hexes (`#dee2e6` → `var(--border)`, `#C9A227` → `var(--gold)`). Receiving session: **S3.2.2** (in-surface, dedicated shape brief + relocation pass).
- **[S3.2.1 in-surface]** N1 link-row resting contrast near-miss. `body.auth-page .auth-link-row a` paints `--gold-dark` (#8A6A1A) on `--bone` (#F3EFE6) at 4.40:1 — 0.1 short of the WCAG AA-normal 4.5:1 floor. PI-1's lift from 2.11 (the pre-S3.2.1 `--gold` resting state) is enormous, and the hover/`:focus-visible` state computes to 14.48:1 (compliant), but the static resting state should clear AA on its own. Options for S3.2.2: (a) darken `--gold-dark` by one luminance notch (DESIGN.md token spec change — out of scope for a per-surface iteration), (b) bump link font-size + weight to qualify for AA-large 3:1 bar (Teko 700 at 18.66px+ would clear), (c) accept the near-miss with documented rationale citing the compliant hover state. Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Decorative `<i class="bi bi-key-fill text-gold">` 2.5rem icon banner above the `/change-password` H1 (template.html:11). Trophy Rule adjacency — `.text-gold` resolves to `var(--platform-accent) !important` (#C9A227, the trophy color), used decoratively on a non-CTA surface. DESIGN.md §2 "Trophy Rule" reserves the metallic gold gradient for primary CTAs and active navbar buttons; a flat-gold icon header sits in the gray zone the rule warns about. Options: drop `.text-gold` to render in the parent text color, swap to `--gold-dark` (~5.07:1 on bone, AA-passing), or remove the decorative icon entirely (the H1 + subtitle carry enough semantic weight). Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Required-asterisk `<span class="text-danger">*</span>` on register.html + reset_password.html uses Bootstrap's `#DC3545`, not the CCC `--danger` token (#C0392B per DESIGN.md §2). Token consistency miss; same scope as the S3.2.2 freebie refactor pass. Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Register password + confirm fields sit `.col-6` side-by-side at every viewport. At 375 the "6+ characters" placeholder truncates to "6+ charac..." (visible in `.impeccable-review/S3.2.1/before/register-mobile.png`). Stack at `<540px` via a `.row.g-3.mb-4 { @media (max-width: 539.98px) { > .col-6 { width: 100%; } } }` or a Bootstrap responsive `col-sm-6` swap. Receiving session: **S3.2.2**.
- **[S3.2.1 cross-cluster] CLOSED in S3.4** Split-panel vs `.auth-wrapper` layout split between marketing-context auth (login, register, forgot, reset) and logged-in utility auth (change-password, profile) was undocumented. S3.4 session-time grep revealed profile.html actually used a *third* pattern (`<div class="container my-5" style="max-width:600px">`, not `.auth-wrapper`), so the split was 4-pattern marketing / 1-pattern utility / 1-pattern third-register. Closed by **S3.4 PI-4** via codify-and-normalize: (a) DESIGN.md §5 gained a new "Auth Surface Composition" subsection naming both registers and listing which template uses which; (b) profile.html normalized from `.container.my-5` to `.auth-wrapper.profile-wrapper` (new wrapper modifier widens the auth-card from the default 440px to 600px for the avatar picker without re-introducing the third register). Two registers, two regression-locked assignments — marketing surfaces never carry `.auth-wrapper`, utility surfaces never carry `.auth-panel-brand`. Live verification: `profile.html` source carries `auth-wrapper profile-wrapper` and not `auth-panel-brand`; CSS contains `.auth-wrapper.profile-wrapper .auth-card { max-width: 600px }`. Locked by `tests/test_design_p3_s3_4.py::test_pi4_design_md_auth_surface_composition_section_present` + `..._marketing_auth_surfaces_use_split_panel` + `..._utility_auth_surfaces_use_auth_wrapper` + `..._profile_wrapper_modifier_widens_card`.
- **[S3.2.1 cross-phase] [S6.1 routed]** Bootstrap `.text-muted` paints via `--bs-secondary-color !important`, so any project-side `.text-muted` color override loses the cascade unless it also carries `!important`. S3.2.1 PI-2 patched this inside `body.auth-page` (auth scope only). The pattern recurs site-wide — leaderboard, schedule, team_detail, stats, player_detail all have surfaces where Bootstrap `.text-muted` rests on bone or navy and loses to the Bootstrap default. Memory `project_text_muted_aa_on_bone.md` flagged this in S2.2.1; S2.6 PI-3 closed three live-cluster instances; S3.2.1 PI-2 closed the auth cluster. A site-wide pass via a single `!important`-bearing override (or a complete migration off `.text-muted` to CCC scope classes) would close the whole class of bug. Receiving session: **S6.1** (cross-phase polish; needs visibility across every cluster's surfaces).
- **[S3.2.1 ship-as-is]** Login mobile shows two `.auth-link-row` rows ("LOST YOUR KEY?" + "Not on the rolls yet? JOIN THE CLUB") at similar Teko-600-uppercase weight. Pre-S3.2.1 the forgot-password link was visually lighter than the create-account row (italic + smaller); now both read as siblings. Functional 44×44 lift more than offsets the small hierarchy loss; if a future session wants to differentiate, a `.auth-link-row--secondary` variant could land without re-breaking the touch floor. No receiving session unless a critique re-flags it.
- **[S3.2.1 ship-as-is]** Change-password masthead reads functional ("CHANGE PASSWORD") next to a Tribune-voiced subtitle ("Forge a new key for the chamber"). Login does the same ("WELCOME BACK" + "Step back into the chamber") and it works because the H1 is universal English. On change-password the H1 sits closer to utility-language. Reasonable people could read the contrast as deliberate (utility action, club voice); not load-bearing enough to fix. Optional polish for S3.4 if voice-tightening lands inside that session.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** `_home_out.html:75-88` 3-up `col-md-4` identical-card-grid composition. Closed by S4.1.1 **PI-1** (`$impeccable layout` — registry grid reshape, single atomic edit closing this item AND the missing-`<h2>` routed item per §1.5b atomic-edit rule). Replaced the `col-md-4` Bootstrap row with `<section aria-labelledby="out-registry-head">` containing `<h2>Pools in Session</h2>` and a 1-col-mobile / 7fr+5fr-desktop CSS grid: 1× large `.out-featured` card (CCC purple+gold radial atmosphere — `var(--purple-950)` → `var(--purple-800)` linear + commish-gold + chamber-purple radials, halftone-dot ::before pattern, Teko 700 title, gold metal CTA with shadow-gold glow, hover lift `translateY(-3px)` + cubic-bezier overshoot) + 1× `.out-coming-rail` `<aside aria-label="Pools coming soon">` with stacked `.out-coming-strip` horizontal rows (48×48 muted icon tile + Teko display name + Teko meta `Opens {{ game.launch_label or 'TBA' }}` reading from the S3.3.2 registry fields). The featured card preserves the logged-out auth-flow link (`auth.register?next=blueprint_join`); canonical `:focus-visible` 2px gold-light ring + 4px offset for keyboard users. Probed silhouettes: desktop 1470 = featured 742×353 + rail 530×353 with 2 strips at 488×72 (different shapes); mobile 375 = featured 319×364 + 2 strips at 277×72. Pre-fix 3× 440×278 identical rectangles retired. Locked by 7 tests in `tests/test_design_p4_s4_1_1.py::test_pi1_*`.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** Missing `<h2>` between `_home_out.html` page `<h1>` and registry grid. Closed by the same S4.1.1 PI-1 atomic edit — `<h2 id="out-registry-head">Pools in Session</h2>` sits inside the new `<section aria-labelledby="out-registry-head">` wrapper. Eyebrow `◈ The Court This Year` precedes the H2 (separate `.out-registry-eyebrow` div, not part of the heading text). Probed outline now H1 "The Fix / Is In." → H2 "Pools in Session" → H3 "2026 FIFA World Cup" (with coming-soon games using non-heading `.out-coming-strip-title` divs so they don't multiply H3 entries). Axe heading-order moderate cleared. Locked by `test_pi1_home_out_carries_section_h2_heading` + `test_rendered_out_state_heading_outline_is_h1_h2_h3`.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** `_home_out.html:68` "Sign in" link 44×15 tap-target. Closed by S4.1.1 **F1** (freebie inherited per §0.4) — `.home-shell .join-alt a` now uses inline-flex with `min-height: 44px; min-width: 44px; padding: 0.6rem 0.5rem; margin: -0.6rem -0.5rem;` (the S2.1.2-locked negative-margin recipe that preserves the inline-running-text baseline). Adds canonical `:focus-visible` gold-light ring. Live probed 60×44 at 375 (pre-fix 44×15). Locked by `test_f1_join_alt_sign_in_link_meets_44px_tap_floor` + `test_f1_join_alt_link_carries_focus_visible_ring`.

### Routed forward from S4.1.1 (in-surface to S4.1.2, cross-phase to S6.1)
- **[S4.1.1 in-surface] → S4.1.2** Pre-state desktop 2-col layout. The `.home-col { max-width: 640px }` floor on `_home_pre.html` produces a phone-shaped column at every viewport — the 1470-wide canvas reads with the masthead floating in a 640-wide well, wasting ~830px of horizontal space. Reshape at md+ to a 7fr/5fr grid: col-A = countdown decree + dossier (left, 7fr); col-B = opening matches + game tiles + commish note + dispatches (right, 5fr). Single column persists below md. Substantial scope (affects 3 dossier variants — `_ballot_card`, `_submit_picks_cta`, `_join_cta_card` — plus opening matches placement + commish/dispatches positioning; the shared `.home-shell` parent risks live-state regression so requires Layer B probe on `_home_live.html` post-fix). Receiving session: **S4.1.2** (in-surface).
- **[S4.1.1 in-surface] → S4.1.2** `.ballot-card` whole-area-link semantic. The entire card is wrapped in `<a href="...?edit=1">`, swallowing the flags ribbon + "Edit any time before the whistle." copy into a single concatenated link for screen readers, and making the flag emojis tap-routes to "edit pick" rather than "show team detail". Restructure into `<section>` (or `<article>`) + an explicit inline `Edit roster ›` action sitting next to "Sealed & delivered." The flags become a non-interactive ribbon. The hover lift (`translateY(-2px)`) moves to the explicit action. Casey (Distracted Mobile) gets a clean affordance; Sam (screen reader) hears the structure instead of one giant link. Receiving session: **S4.1.2**.
- **[S4.1.1 in-surface] → S4.1.2** Three different gold-bordered card recipes within one viewport on pre-state: `.decree` (purple gradient + 30%-gold border + dashed gold internal rule, 14px radius), `.cta-card--seal` (gold-overlay gradient + 35%-gold border, 12px radius), `.match-card` (purple gradient + 8%-bone border, 12px radius). DESIGN.md §5 says "Consistent affordances across the surface"; a returning user can't predict whether a gold-bordered card is tappable, ceremonial, or informational. Fix: define a 2-tier card vocabulary inside `.home-shell` — **Ceremonial** (decree + cta-card--seal consolidated: gold-30% border, dashed gold internal rule, gold-on-purple gradient — used for time-sensitive CTAs) and **Informational** (match-card register: 8%-bone border, purple gradient — used for fixtures + dossier + dispatches). Document the split in DESIGN.md §5 ("Cards" subsection) so the vocabulary survives the migration. Receiving session: **S4.1.2**.
- **[S4.1.1 in-surface] → S4.1.2** Out value-prop strip `.out-prop` ×3 — three identical icon-text rows (gold icon + Teko title + Newsreader sub, stacked between two bone-opacity-8 hairlines). Within-strip identical-grid signal. Differentiate via row-specific texture: row 1 keeps icon-pair; row 2 swaps icon for a tiny inline leaderboard sparkline preview; row 3 swaps for a Commish-wordmark monogram. P3-class; ride along to S4.1.2 to lift Consistency heuristic toward 4. Receiving session: **S4.1.2**.
- **[S4.1.1 cross-phase] → S6.1** Flash banner ("Logged in successfully!" etc.) competing with home-shell masthead. The flash lives in `base.html` chrome and persists across every authenticated state's home + game pages; it reads as the highest-contrast object on a screen whose hero is supposed to be the masthead. Auto-dismiss success flashes after ~4s with a CSS transition, OR restyle inside `.home-shell` to read as a thin gold-rule + small italic Newsreader inline confirmation that doesn't compete with the masthead. Spans multiple clusters (auth flash on auth pages, success/error flashes on game admin pages, deadline-warning flashes on picks); cross-phase pattern. Receiving session: **S6.1**.

### Routed forward from S4.2.1 (in-surface to S4.2.2, cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Three competing tier-vocabulary primitives on one page: `.tier-badge` (pill, light surface, used in sidebar pick-summary + mobile readonly card), `.wc-multiplier-chip` (dark-surface chip, used in desktop readonly table + tier-card-header), `.wc-tier-dot` (compact circular dot). Closed by S4.2.2 PI-1 (atomic with the mobile tap-through routed item below — per §1.5b atomic-edit rule, same edit closes both). Mobile readonly `.player-pick-card` now renders `.wc-tier-dot wc-tier-dot-{{ pick.tier }}` + `.wc-eyebrow` Teko tier name on a stacked `.pick-tier-line` above the team line. `.tier-badge` survives only in the `summaryList` JS builder (the demoted "one place, one job" home — sidebar pick-summary li chips during edit). `.wc-multiplier-chip` is no longer used to encode tier anywhere. Locked by `tests/test_design_p4_s4_2_2.py::test_pi1_mobile_card_uses_wc_tier_dot_not_tier_badge` + `..._pi1_tier_badge_survives_only_in_summaryList_js`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Inline `style="font-size:N.Nrem"` type-scale leakage on `.wc-numeral` spans. Closed by S4.2.2 PI-2 — extracted four numeral modifier classes (`.wc-numeral--xl` 1.4rem, `.wc-numeral--lg` 1.3rem, `.wc-numeral--md` 1.2rem, `.wc-numeral--sm` 1.1rem) in `style.css`; replaced the 4 inline declarations on `picks.html` `.wc-numeral` spans (`:42` desktop total → `--lg`, `:82` mobile total → `--md`, `:109` tiebreaker → `--xl`, `:205` sidebar summary count → `--sm`); the mobile readonly tier-badge font-size declaration was removed by PI-1's tier-vocabulary swap. Only remaining inline `font-size` in picks.html is the decorative `.bi-x-circle` empty-state icon at 2.5rem — explicitly out of routed PI scope (not a numeral). Locked by `tests/test_design_p4_s4_2_2.py::test_pi2_no_inline_font_size_on_wc_numeral_in_picks` + `..._pi2_numeral_modifier_classes_defined_in_css` + `..._pi2_modifier_classes_carry_expected_rem_values` + `..._pi2_each_modifier_is_consumed_at_least_once_in_picks`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Mobile `.player-pick-card` non-interactive — closed atomically with the tier-vocabulary collapse (PI-1) per §1.5b atomic-edit rule. The mobile readonly card is now `<a href="{{ url_for('worldcup.team_detail', team_id=pick.team_id) }}" class="player-pick-card">`, scoped CSS adds `text-decoration: none; color: inherit; transition; :hover { border-color: var(--game-primary-light); box-shadow: var(--shadow-sm) }; :focus-visible { outline: 2px solid var(--gold-light); outline-offset: 2px }` so it reads as a tappable card with canonical CCC focus ring. Probed at mobile 375: 9 cards present, first card `href=/worldcup/team/7`, rect 351×79 (clears 44 floor), focus ring `rgb(242,211,107) solid 2px`. Locked by `tests/test_design_p4_s4_2_2.py::test_pi1_mobile_player_pick_card_is_anchor_with_team_detail_href`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.pick-summary` 3px top-stripe (side-stripe-adjacent pattern). Closed by S4.2.2 PI-4 — dropped `border-top: 3px solid var(--game-primary)` from `.pick-summary`; the Teko eyebrow + H2 (the PI-3 promotion below) now carry hierarchy. Probed: border-top computed style went from `3px solid rgb(0, 40, 104)` (raw WC navy) → `1px solid rgb(216, 221, 232)` (full perimeter resting border = `var(--border)`). Locked by `tests/test_design_p4_s4_2_2.py::test_pi4_pick_summary_no_top_stripe` + `..._pi4_pick_summary_keeps_full_border`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.wc-team-card.selected::after` Unicode checkmark glyph (markup-as-icon). Closed by S4.2.2 F1 freebie — swapped `content: '\2713'` for CSS-mask SVG (Bootstrap Icons `bi-check2` path, 14×14 square, `background-color: var(--platform-primary)` for color control). The affordance is now a real check icon with stable glyph metrics across platforms, color-controlled via `background-color` (no font-cascade dependency). Probed: `::after` content empty `""`, width/height 14px, bg `rgb(58, 29, 114)` (Council Purple per S4.2.1 PI-4 lock), mask `url(data:image/svg+xml…)`. Locked by `tests/test_design_p4_s4_2_2.py::test_f1_selected_after_no_unicode_checkmark_content` + `..._f1_selected_after_uses_svg_mask`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Edit-form heading-order H1 → H3 skip. Closed by S4.2.2 PI-3 — promoted `.tier-card-header h3` → `<h2 class="tier-card-heading">` (×5) and `.pick-summary h4` → `<h2 class="pick-summary-heading">` via new surface-class CSS selectors that preserve the Teko 1.35rem / 1.2rem visual without keying off element type. Each tier card is a logical section under the page H1; sidebar pick-summary is a parallel section. Probed edit-form outline: `H1: Amend the Oath → H2: Favorites ×1.0 → H2: Contenders ×1.5 → H2: Dark Horses ×2.5 → H2: Underdogs ×4.0 → H2: Wildcards ×7.0 → H2: Pick Summary` — zero heading-level skips. Readonly outline already clean from S4.2.1 F2. Locked by `tests/test_design_p4_s4_2_2.py::test_pi3_tier_card_header_uses_h2_not_h3` + `..._pi3_pick_summary_uses_h2_not_h4` + `..._pi3_css_targets_tier_card_heading_class_not_h3` + `..._pi3_css_targets_pick_summary_heading_class_not_h4`.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.wc-multiplier-chip` `var(--wc-white)` token hygiene. Closed by S4.2.2 F2 freebie — lifted to `var(--text-on-dark)` matching S4.2.1 PI-4 idiom on `.tier-badge`. Caused a downstream contrast regression on light-surface chip usage (chip inside `.tier-card-heading` on white tier-card body went bone-on-white ~1.04:1, surfaced by Layer C critique); closed in-iteration by PI-A1 (scoped override `.tier-card-heading .wc-multiplier-chip { color: var(--text-ink); background: rgba(58,29,114,.07); border-color: rgba(58,29,114,.25) }` so the chip reads council-purple ink on bone-tinted-purple ~14.5:1 on white). Locked by `tests/test_design_p4_s4_2_2.py::test_f2_multiplier_chip_uses_text_on_dark_not_wc_white` + `..._pia1_multiplier_chip_re_tinted_on_tier_card_heading`.
- **[S4.2.1 cross-cluster] CLOSED in S4.5** "Base · Multiplier · Points" derivation-table column trio. Closed by S4.5 PI-1 — session-time grep confirmed the cross-cluster premise on picks.html (lines 54-56) + player_detail.html (lines 61-63), and refuted it on team_detail.html (S2.3.1 already escaped to inline "Base × Multiplier" prose under one dominant Scored numeral per the hero-metric-adjacency ban). Decision: collapse to 2-column + accordion-only Base reveal. The shared `_pick_row.html` partial drops the outer-row Base td (line 25); `picks.html` + `player_detail.html` table headers drop `<th>Base</th>`; accordion-row colspan updates 5 → 4. The accordion's existing "Total base X × multiplier Y = multiplied Z" summary line (`_pick_row.html:50`) becomes the canonical Base disclosure — already present in the JS-expanded panel, so no new copy is added. `player_detail.html` tfoot drops the orphaned base-sum cell (colspan stays 3; the multiplied total occupies the 4th column). Live-probed at 1470: both surfaces render 4 headers (Team/Tier/Multiplier/Points); first row carries 4 cells; accordion colspans all read "4"; accordion's "Total base 8.0 × 1.0 = 8.0 multiplied" line still exposes Base on expand. Locked by `tests/test_design_p4_s4_5.py::test_pi1_pick_row_outer_drops_base_td` + `..._accordion_colspan_dropped_to_four` + `..._accordion_keeps_total_base_disclosure` + `..._picks_html_header_drops_base_th` + `..._picks_html_caption_drops_base_phrase` + `..._player_detail_header_drops_base_th` + `..._player_detail_tfoot_drops_total_base_cell`.
- **[S4.2.1 cross-cluster] → S6.1 (re-routed by S4.5)** `.tier-badge` vs `.wc-multiplier-chip` vocabulary canonical primitive. Session-time grep refuted the original "wider than picks alone — team_detail / player_detail / stats" premise: `tier-badge` is absent from team_detail.html, player_detail.html, and stats.html (all three surfaces use only `wc-tier-dot`). The actual remaining cross-surface scope is `rules.html` (×5, where `tier-badge` displays the literal "T1/T2/..." numeric companion to the dot) plus `_home_pre.html:42` (the ballot dossier `roster-tier-label`); both legitimately need the numeric text alongside the visual dot. This is a DESIGN.md §6 doc gap, not a code-vocabulary collision — the three primitives play distinct roles: `wc-tier-dot` = visual mark, `tier-badge` = numeric text companion, `wc-multiplier-chip` = multiplier indicator. Re-routed to **S6.1** as a DESIGN.md §6 doc PI ("Tier primitive vocabulary") alongside the existing S4.4.1-routed Tribune-voiced H1 §3 pass.
- **[S4.2.1 cross-phase] → S6.1** Voice repetition stack on the read-only state: "Sealed · still amendable" eyebrow + "Sealed. Still amendable." H1 + "You can amend your picks until {{ deadline_ct }}." microcopy + "Amend the Oath" CTA — same fact stated 4× above the fold. PRODUCT.md "Sharp / Competitive" register asks for one decisive line, not three. Pattern recurs across deadline-bearing WC surfaces (`_home_pre` countdown decree, `_home_live` deadline awareness, `team_detail` fixture statuses). Cluster polish session (S4.5) should sweep WC; cross-phase voice tightening lands at S6.1 alongside the S4.1.1-routed flash banner masthead competition + S2.4.1-routed markup-as-icon ✓/← progress bar. Receiving session: **S6.1**.

### Routed forward from S4.2.2 (ship-as-is to S4.5 if surfaced, cross-phase to S6.1)
- **[S4.2.2 ship-as-is]** Desktop readonly hero-to-card vertical void. `col-lg-8` centers an 856px picks card on a 1410px container at 1470 viewport with no companion column — ~400px of empty bone between the hero band and the navy card reads as a forgotten dashboard rather than a deliberate editorial column. P2 surfaced by S4.2.2 Layer C critique. Per §1.5b anti-perfectionism note, S4.2.2's gates passed (heur 32/40, 0 P0, 0 unrouted P1, 0 anti-pat) so the surface converged and we don't keep iterating. Two paths if a future session re-opens it: (a) widen to `col-lg-10` (cheap, no new content); (b) add a Tribune-style sidebar — "Roster at a Glance" tier-mix counts + "Strongest pick" callout — needs new route data. Cluster polish S4.5 may sweep this once picks / join / rules / groups converge. `$impeccable layout` is the recommended command. Receiving session: **S4.5 if surfaced** (otherwise ship).
- **[S4.2.2 ship-as-is]** Desktop accordion-toggle 25×24 hit target. P3 surfaced by S4.2.2 Layer C critique. PRODUCT.md 44×44 floor applies mobile-first, and the desktop accordion-toggle sits inside a row affordance where the entire `.pick-team-cell` is the click target; the chevron is decorative emphasis. Below floor though desktop-only and doesn't block keyboard or touch access (the cell + `tab` to the inner toggle button work). `$impeccable polish` could lift `.pick-accordion-toggle { min-width: 44px; min-height: 44px }` if a future session re-opens picks for an unrelated reason. Receiving session: **S4.5 if surfaced** (otherwise ship).
- **[S4.2.2 cross-phase] → S6.1** Dark readonly tier-name eyebrow at ~0.55 alpha on navy (bone-at-0.55 on `rgba(0,17,46,.8)` at 11.2px Teko letter-spaced ≈ ratio borderline AA). Surfaced by S4.2.2 Layer C critique as P3. Same eyebrow saturation family as the S2.4.1-routed `.wc-eyebrow` cross-phase item already at S6.1. Bundle: lift the dark-card `.wc-eyebrow` alpha to .72 (the `picks-rules-link` precedent from S4.2.1 PI-3) or .85 across every `.card.wc-card .wc-eyebrow` instance in one pass. Receiving session: **S6.1**.

### Routed forward from S4.4.1 (cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.4.1 cross-cluster] CLOSED in S4.5** Pill-rail ultra-wide stretch. Closed by S4.5 PI-4 — `@media (min-width: 1200px) { .wc-group-index, .wc-rules-index { max-width: 720px; } }`. The cap engages exactly at the xl breakpoint: live-probed at 1199 viewport `max-width: none` (natural width), at 1200 viewport `max-width: 720px` (rail clamps cleanly), at 1470 viewport rail rect = 720px (was stretching the full container before). The same cap covers the new `.wc-rules-index` sibling primitive added in PI-3 so future in-page nav rails inherit the constraint without re-discovering it. The 44×44 floor on `.wc-group-index-pill` and the new `.wc-rules-index-pill` is preserved (live-probed: all 7 rules pills + all 12 groups pills clear 44px). Locked by `tests/test_design_p4_s4_5.py::test_pi4_xl_breakpoint_caps_group_and_rules_index_max_width`.
- **[S4.4.1 cross-phase] → S6.1** Page H1 "Group Standings" stays as functional chrome rather than masthead voice; the S4.4.1 eyebrow + lead rewrite carry the Tribune register but the H1 itself reads as a SaaS-utility section header. Same pattern affects 8+ surfaces (leaderboard "Leaderboard", schedule "Tournament Schedule", stats "Stats Hub", picks "Pick Your Roster", rules "Rules", join "Join the Pool", profile "Profile"). The masthead-voice rewrite is a system-wide Tribune-register pass that should ratify a primitive shape (Teko display + Tribune voiced title + functional fallback id) in DESIGN.md §3 once every primary surface has been touched by an iteration. Receiving session: **S6.1**.
- **[S4.4.1 ship-as-is]** `.wc-group-index` rail lacks a visible "Jump to" eyebrow label; sighted users discover the affordance by trying a pill. The `aria-label="Jump to group"` covers screen-reader users; for sighted users the 12 single-letter pills above 12 letter-headed cards are self-explanatory. Adding a label would compete with the state chip's job in the same vertical gap. If a future critique re-flags it, fix is a one-line Teko eyebrow ("Jump to") inside the nav.
- **[S4.4.1 ship-as-is]** `.wc-state-chip--pre .wc-state-chip-dot` paints `--game-accent` (WC red `#BF0A30`) on a purple-tinted chip; the cross-color reads more "warning red" than "scheduled." Acceptable because (a) the chip clears AA, (b) pre-state lifetime is finite (chip swaps to live-red dot post-deadline anyway), (c) the chip is read once per session. If routed forward, swap the pre-state dot to `--gold` (for consistency with the post chip's gold dot) or `--game-primary` (navy = "scheduled").
- **[S4.4.1 ship-as-is]** Tier (1–4) is the analyst's primary hook into a group field; it's exposed on `/stats`, `/picks`, `/team_detail` but absent from team rows on `/worldcup/groups`. Adding it would require resolving the tier-vocabulary collapse decision (`.tier-badge` vs `.wc-multiplier-chip` vs `.wc-tier-dot`) at cluster altitude — already routed to S4.5 per S4.2.1's `[S4.2.1 cross-cluster] → S4.5` item. Don't surface tier on groups.html ahead of the cluster-level ratification; the surface stays casual-default and the analyst path through `/team/<id>` remains the depth target. Will be revisited at S4.5 once the tier-vocabulary canonical primitive is locked in DESIGN.md §6.

### Routed forward from S4.3.1 (cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.3.1 cross-cluster] → S6.1 (re-routed by S4.5 as decided no-op + DESIGN.md route)** Mobile tier-meta text below 16px body floor. Session-time grep confirmed the cross-cluster premise: `.tier-mobile-card-picks` + `.tier-teams-list` at 13.6px on rules.html, `.player-pick-card .pick-team small` at 12px + `.player-pick-card .pick-points small` at 11.2px on picks.html, all carrying caption/metadata semantics under a dominant Teko read-target on the same row. Bumping all of them to 16px would expand mobile vertical rhythm and let captions compete with primary read-targets — the wrong fix. **Decided no-op** at S4.5: caption-tier typography <16px is a deliberate, repeated cross-cluster pattern. The right outcome is a DESIGN.md §3 caption-tier dispensation note ("≥16px applies to body text and primary read-targets; explicit caption/metadata classes may step down to ≥0.75rem (12px) when the primary read-target on the same row carries the dominant hierarchy"). Routed to **S6.1** alongside the S4.4.1 Tribune-voiced H1 §3 pass.
- **[S4.3.1 cross-cluster] CLOSED in S4.5** Rules-page navigation accelerators. Closed by S4.5 PI-3 — added `<nav class="wc-rules-index" aria-label="Jump to section">` pill rail above the rules.html content with 7 anchor pills (Overview / Tiers / Group stage / Knockout / By tier / Tiebreaker / Edge cases) mapping to the 7 H2 sections via new ids (`rules-overview`, `rules-tiers`, `rules-group-stage`, `rules-knockout`, `rules-points-matrix`, `rules-tiebreaker`, `rules-edge-cases`). Sibling primitive to `.wc-group-index` (S4.4.1 PI-3) and `.schedule-jump-today` (S2.6 PI-4); same 44px tap-target floor, same Teko caps, same canonical gold-light `:focus-visible` ring (live-probed: `outline: rgb(242, 211, 107) solid 2px; outline-offset: 2px`). PI-4's max-width cap covers both rails so they don't stretch on ultra-wide. Locked by `tests/test_design_p4_s4_5.py::test_pi3_rules_index_nav_is_semantic_nav` + `..._carries_seven_pills_with_expected_anchors` + `..._rules_h2s_carry_matching_ids` + `..._wc_rules_index_pill_carries_44px_min_height` + `..._wc_rules_index_pill_has_focus_visible_ring`.
- **[S4.3.1 cross-phase] → S6.1** Residual Bootstrap `<small class="text-muted">` on `rules.html:65` (desktop tier-team-list cell, hidden on mobile via `d-md-block`). One additional instance to fold into the existing S6.1 cross-phase `.text-muted` site-wide retire already on the docket from S3.2.1 PI-2's `body.auth-page` scope. The S4.3.1 PI-5 in-surface lift via `body.game-worldcup .form-label/.form-text` is the WC-game-scope companion; the global retire still belongs at S6.1. Receiving session: **S6.1**.
- **[S3.3.1 in-surface] CLOSED in S3.3.2** `_game_tiles_compact.html:28-29` slug-branched display copy. Closed by S3.3.2 PI-1 via option (a): added `short_name: str = ''` + `launch_label: str = ''` fields to `GameRegistryEntry` (defaulted empty so legacy mock factories in `test_registry.py` / `test_enrollment_gating.py` continue to pass without modification); populated on all three production entries (WC: `'World Cup'` / `'Jun 11'`; CFB: `'CFB'` / `'Sep 3'`; Golf: `'Golf'` / `'2027'`). Partial now reads `{{ game.short_name or game.display_name }}` and `{{ game.launch_label or 'TBA' }}` so it carries zero slug knowledge — a future `CFB Survivor Pool` → `College Football Survivor` rename cannot break the label. Locked by `tests/test_design_p3_s3_3_2.py::test_pi1_registry_entry_carries_short_name_field` + `..._launch_label_field` + `..._populates_cfb_and_golf_metadata` + `..._tiles_compact_drops_slug_ternaries` + `..._tiles_compact_reads_registry_fields`.
- **[S3.3.1 in-surface] CLOSED in S3.3.2** Heuristic lift from 24 → ≥26 (gate (b) baseline+6 floor). Closed by **S3.3.2 PI-2 + PI-3** — heuristics 24 → 29 (Δ +5, exceeds gate (b) by +3). PI-2 (`$impeccable clarify`): new `.game-launch-meta` Teko 500 .9rem .14em uppercase microcopy line below `_game_card.html` `coming_soon` description, reading `Opens {{ game.launch_label or 'TBA' }}` — paints `var(--text-secondary)` (#5A5470, ~6.9:1 on bone) NOT `var(--text-muted)` (3.7:1 AA-fail per `project_text_muted_aa_on_bone` memory). Renders `Opens Sep 3` (CFB) / `Opens 2027` (Golf). Heuristic 10 (Help/Documentation) 3 → 3 (the original 2 → 3 estimate undershot the polish lift; cross-cutting bump went to Heuristic 6 Recognition vs Recall instead). PI-3 (`$impeccable polish`): canonical `:focus-visible` ring on `.game-card--live` — `outline: 2px solid var(--gold-light); outline-offset: 2px; border-radius: var(--radius);` matching the S2.1.2-locked `.home-shell .sec-head .more` pattern. Live computed-style verification: `outline rgb(242,211,107) solid 2px`, `outline-offset 2px`, `border-radius 4px`. Heuristic 7 (Flexibility/Efficiency) 2 → 3. Locked by `tests/test_design_p3_s3_3_2.py::test_pi2_coming_soon_renders_launch_microcopy` + `..._game_launch_meta_uses_text_secondary_not_text_muted` + `..._game_launch_meta_uses_teko` + `..._pi3_game_card_live_has_focus_visible_ring` + `..._pi3_focus_ring_only_on_live_card_not_coming_soon`.
- **[S3.3.2 ship-as-is]** Golf `launch_label='2027'` is a year, not a date. Casual users may want quarter-level precision ("Q3 2027" / "Fall 2027"). The PI-2 `Opens 2027` affordance lands but the underlying data is a shrug for Golf specifically. Update `games/registry.py` when the Golf launch firms up — currently aspirational. Surfaced by the S3.3.2 re-critique as P2; flag if a future S4 / S6 polish session reopens it earlier.
- **[S3.3.2 ship-as-is]** `_home_out.html:58` `.home-metal-text` class on the "competition" word. Live probe confirms the class resolves to flat `var(--gold-light)` (no `background-clip: text`, no gradient) — the existing rationale block at `style.css:399-406` already documents that the class is solid gold-light to avoid the gradient-text ban. Hygiene flag: ensure no future commit accidentally promotes the class to gradient-text. Surfaced by the S3.3.2 re-critique as P2; no action needed at this iteration.
- **[S3.3.1 ship-as-is]** `_game_card.html` `featured` state declared (`:9-23`) but no caller in `core/`, `games/`, or `templates/` invokes it today. The registry's `is_featured=True` on WC + `featured_games()` helper compute the list but no template consumes either. S3.3.1 PI-B retuned `.game-card--featured` CSS to DESIGN.md compliance (replaced literal `#FFFFFF`, hardcoded WC navy/red palette, and neutral-black drop-shadow with CCC purple+gold + `var(--live-red)` semantic + chamber-purple shadow) so the dormant variant is brand-correct whenever S4.1 wires it through `_home_out.html`. No further work needed in S3.3 cluster; flag if S4.1 chooses to delete rather than wire (the supporting CSS at `style.css:4307-4403` would become dead code).
- **[S3.3.1 ship-as-is]** Coming-soon badge `mb-3` (16px) pushes the icon ~16px below the logged-out card's icon baseline at 375 viewport (probed in `.impeccable-review/S3.3.1/after/home-out-mobile.png`). The vertical-rhythm asymmetry is the deliberate consequence of PI-A's silhouette differentiation — the badge has to live somewhere, and the eyebrow position is the right call. A `mb-2` tightening (8px) would close the rhythm with the playable cards' icon row; left at `mb-3` to keep the badge visually independent of the icon. Re-evaluate only if a future critique re-flags it.

### Routed forward from S5.1.1 (in-surface to S5.1.2, cross-cluster to S5.3, cross-phase to S6.1)
- **[S5.1.1 in-surface] CLOSED in S5.1.2** Podium + Final Roster `<a>` text-link tap targets render 15px tall at 375 mobile (`B1G_Brad` 68×15, `test2` 33×15 — well below the 44 floor). Closed by S5.1.2 PI-1 via class-scoped `.post-table-link` shared by both anchors (the precedent path — `.picker-link` S2.3.1 / `.team-link` S2.5.1 / `.home-shell .sec-head .more` S2.1.2 / `.join-alt a` S4.1.1 / `.decree-links` S4.1.1 — rather than the alternative `.card.wc-card .table a` broadcast that would bleed onto every WC table that already carries its own classed anchors). CSS uses `display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 0.25rem 0;` — NOT the routed entry's `inline-block + line-height: 44px` candidate, which collapses multi-line wrap onto a 44px baseline and breaks long display names ("United States" wraps onto two lines at 60px column in the Roster table at 375; live-probed at 81px tall post-fix, confirming the wrap is preserved). Post-fix Layer B sweep: all 12 post-state anchors (3 podium + 9 roster) clear 44×44 at 375 viewport (min 44×44; pre-fix min 33×15). Locked by 6 tests in `tests/test_design_p5_s5_1_2.py`, including `test_pi1_no_broadcast_table_anchor_rule` which guards against a future "tidy this up" pass promoting the rule to the broadcast scope.
- **[S5.1.1 cross-cluster] CLOSED in S5.3 (§1.8 deviation, item taken cross-phase)** `.card.wc-card .wc-numeral` (style.css:2848) rendered bone (`#F3EFE6`) on the `.row-champion-pick` cream substrate (1.05:1) and on the masked-white substrate of every `.card.wc-card .table` cell (1.14:1). Session-time grep confirmed scope was every WC table inside `.card.wc-card` (leaderboard, picks, schedule, groups, rules, team_detail, all four state partials), i.e., cross-phase by the routing matrix. Per the routed entry's escape clause, this should have re-routed to S6.1. **In-session decision (Brad, S5.3):** fix shape is one selector-scoped CSS rule; splitting to S6.1 adds overhead without value. Taken in S5.3 as documented §1.8 deviation. Closed by S5.3 PI-1: `.card.wc-card:not(.player-picks-desktop) .table .wc-numeral { color: var(--text-primary); }` — re-tints in-cell numerals to platform ink (~14.5:1 on white). The `:not(.player-picks-desktop)` carve-out mirrors PR #15 CR R2's `.wc-multiplier-chip` pattern (the player-picks-desktop wrapper opts out of the white-td mask via `background-color: transparent`, so its bone-on-navy numerals stay correct). Parent rule `.card.wc-card .wc-numeral { color: var(--text-on-dark); }` retained for masthead / card-header / direct card-body content (tiebreaker, "Total: 125.0 pts" header). Layer B at session-time: in-cell numerals render `rgb(28, 23, 48)` = `#1C1730`; non-table `.post-finish-rank` stays `rgb(243, 239, 230)` = bone. 3 Layer A locks in `tests/test_design_p5_s5_3.py`.
- **[S5.1.1 cross-cluster] CLOSED in S5.3** `.btn-outline-secondary` quicklink trio in the home_shell footer (`Schedule` / `Groups` / `Rules`) read `#8a849b` on `.card.wc-card` navy at 3.04:1 (axe-confirmed); rendered universally via home_shell.html:48-62 across all four state partials. Closed by S5.3 PI-2: `.card.wc-card .btn-outline-secondary { color: var(--text-on-dark); border-color: rgba(245, 241, 232, .35); }` at rest + hover/focus-visible inversion to `var(--text-primary)` on `var(--bone)` (Bootstrap-parallel hover behavior in CCC tokens). Layer B confirmed all 3 quicklinks render `rgb(243, 239, 230)` = bone, ~13:1 on navy. 3 Layer A locks in `tests/test_design_p5_s5_3.py`.
- **[S5.1.1 cross-phase] → S6.1** `.wc-eyebrow` saturation on `.card.wc-card` substrates renders `#9c9fa4` on `#313d53` at 4.11:1 (axe surfaces 5 hits in _home_post: champion banner, your-finish, podium header, roster header, around-the-pool). Same pattern as the S2.4.1-routed `.wc-eyebrow` ratification + S4.2.2 dark-card eyebrow alpha lift, already at S6.1. Bundle into the existing S6.1 cross-phase eyebrow pass — DON'T fix in S5.1.2 (would create a third migration touch on a primitive about to be system-wide ratified). Receiving session: **S6.1**.

### Routed forward from S5.2.1 (cross-phase to S6.1)
- **[S5.2.1 cross-phase] → S6.1** Three remaining gradient-text rules form a system-wide pattern after S5.2.1 PI-1 retired the champion-banner instance: `style.css:2208` (`.home-shell .recap-rank` — S5.1 surface "Your Finish" rank numeral renders `#42` with `background-clip: text` + `var(--metal-gold)`); `style.css:6644` (`.card.wc-card.wc-hero-grad .champion-name` — team_detail / leaderboard hero substrate, comment explicitly says "Mirrors `.home-shell .champion-name`"); `style.css:6928` (`.table-worldcup .row-champion-pick .best-finish-champion` — leaderboard champion-row marker). All four rules used the same `var(--metal-gold)` background-clip recipe, which violates the impeccable absolute ban + DESIGN.md §6 Don't list. The S5.2.1 fix shape was solid `var(--gold-light)` (mirrors `.home-metal-text` precedent at `style.css:461`); the same single-color migration applies to all three remaining sites. Bundling at S6.1 instead of fixing piecemeal: scope spans S2.5 (team_detail, converged), S2.4 (leaderboard, converged), and S5.1 (`_home_post.html`, converged at S5.1.2) — fixing each in its own session would require three separate iteration commits on already-converged surfaces. Receiving session: **S6.1** cross-phase polish (one atomic retire pass + one Layer A test file locking all three rules).
- **[S5.2.1 ship-as-is]** Two P3 polish notes surfaced by S5.2.1 Layer C critique (sub-agent), in-surface but below the convergence floor: (a) `.champion-eyebrow` reads at the peak of the `champion-halo` animation's outer feather — static contrast clears AA at all phases, but a `text-shadow: 0 1px 2px rgba(20, 8, 40, .5)` would lock the halo-peak band; (b) `.commish-note-body`'s `border-top: 2px solid var(--gold)` is the DESIGN.md §5 "gold-divider" recipe (full-top rule, NOT a side-stripe) but reads adjacent to the ban — a one-line CSS comment naming the recipe would guard against a future migration to a left-stripe. Both polish-only, neither blocks convergence. Won't be re-flagged unless surfaced as P1+ in S6.1.

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

### 1.5c Cluster polish session pattern (S2.6 / S3.4 / S4.5 / S5.3 / S6.1)

Cluster polish sessions are **not** per-surface iterations and do **not** trigger the §1.5b convergence gate. They receive routed `[Sx.y.N cross-cluster]` items from §0.4 and produce 3-5 cluster-level fixes. Calibrated against S2.6 (the first cluster polish session to run end-to-end under the iterative model).

**Triage discipline.** Three pitfalls a cluster session must avoid:

1. **DESIGN.md cross-check before fixing every routed item.** A `[cross-cluster]` route from a per-surface iteration is the *critique's* judgment that something looks like an anti-pattern. The *committed* design policy may have already considered and accepted it. Calibrated against S2.6 PI-2: the S2.4.1 critique flagged `.wc-stat-card`'s border+`--shadow-sm` as "double elevation, pick one" — but DESIGN.md §4.4 "Lift-At-Rest Rule" and §6 card primitive explicitly mandate both at rest ("the Tribune is a printed object, not a wireframe"). Shipping the "fix" would have regressed the committed brand policy. Impeccable's priority rule (user instructions > skill heuristics) means **DESIGN.md wins on any conflict**. Pre-fix check: for each routed item, search DESIGN.md for the relevant primitive/policy section. If DESIGN.md mandates the pattern the critique flagged, the routed item resolves as a **decided no-op with rationale** in §0.4 (counts toward the 3-5 cap as a triage finding, but produces no code change).

2. **Verify the cross-cluster premise at session-time, not at route-time.** A finding gets the `[cross-cluster]` tag during a per-surface iteration when the surface critique notes "pattern likely shared with other surfaces." That's a *guess* about cross-surface scope; the cluster session is the place to confirm it. Calibrated against S2.6: the S2.4.1-routed "inline-Teko duplication likely shared with `_home_live` impact rows / leaderboard mobile cards" turned out to be **0 hits** outside `stats.html` in the live cluster. The actual cross-surface usage was P4 pre-live templates (picks/rules/join, 11+ instances). One grep at session-time saved a premature extraction that would have needed a second migration pass in P4. **Verification action**: for each routed item that names "likely shared" surfaces, run a one-line grep across those surfaces before scoping the fix. If the cross-surface premise doesn't hold, **re-route** the item with the corrected receiving session (e.g., to a different phase's cluster session) instead of fixing it in the wrong cluster.

3. **"Cap 3-5 PIs" includes triage outcomes, not just code changes.** A decided no-op (per #1) or a re-route (per #2) is a legitimate PI outcome and counts toward the cap. The cap measures triage work, not edit count.

**Verification bar (lighter than per-surface convergence).** A cluster session does not need to run `$impeccable critique` against each child surface. The bar is "all S2.x.M surfaces hold; no in-surface P0/P1 surfaced; the cluster session's own edits don't regress adjacent surfaces." Concretely:

- **Layer A**: source-pattern locks for every code-change PI under `tests/test_design_<phase>_s<num>_<cluster>.py`.
- **Layer B (the cluster verification layer)**: Playwright MCP computed-style probes and visual smoke on **touched surfaces + adjacent surfaces where the change could bleed**. Touched = surfaces directly edited by a PI. Adjacent = surfaces that share the changed CSS scope (e.g., a `.card.wc-card .table` change touches every surface containing that selector pattern). S2.6 calibration: PI-1 touched no template directly but altered the cluster-3 surgical-exclusion environment, so leaderboard + player_detail + picks were probed; PI-3 touched schedule + team_detail, so those were probed; PI-4 touched schedule, probed at desktop + mobile.
- **Layer C is skipped by default.** Re-running `$impeccable critique` against 5–6 surfaces is ~3-6 hours of sub-agent work; Layer B catches the regressions that matter (computed contrast, layout, focus, tap-target floor). Re-run Layer C only if Layer B surfaces unexplained visual differences or if the cluster work was structurally large (e.g., a chrome-component rewrite that re-flows every cluster surface).

**Output shape.** A cluster session produces (in this order):

1. The 3-5 PI triage table in the session message — for each item: source `[Sx.y.N cross-cluster]` route, S2.6-time DESIGN.md/grep verification result, outcome (fix / no-op / re-route).
2. Code changes per fix PI (minimal, scoped, additive — never broadcast).
3. Layer A regression locks per fix PI.
4. Layer B verification log (computed values + screenshot paths).
5. §0.4 amendments: routed items get `CLOSED in S<this session>` / `[S<this session> routed]` annotations with rationale; un-touched cross-cluster items stay open.
6. §9 rollup row flipped; commit hash backfilled per §1.5 step 5.
7. Phase PR opened (cluster session is the last session of its phase per §1.1).

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

- [x] **S2.1 — `home_shell.html` + `_home_live.html`** (the World Cup home in live state). Cross-cutting note: this surface uses `core/main/home_context.py` builders. Critique covers the page state but execution may need the partials in `core/main/templates/main/_home_live.html` plus `_dossier_card.html` / `_fixture_card.html`.
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

- [x] **S2.6 — Cross-cluster live polish (NOT cluster mop-up).** Runs only after S2.1–S2.5 have all converged per §1.5b. **Step 0:** sweep §0.4 for items tagged `[Sx.y.N cross-cluster]` and route them as agenda. **Step 1:** identify patterns visible only when comparing 2+ live-cluster surfaces — visual-rhythm consistency across `_home_live` / `schedule` / `team_detail`, repeated chrome treatments, eyebrow-primitive consistency, cross-surface motion language. Cap: 3-5 cross-surface findings. **Step 2:** re-run `$impeccable critique` against each S2.1–S2.5 surface (and the leaderboard, in case live-cluster shared-chrome work bled into it). Confirm none regressed. **Step 3:** open PR `Impeccable P2 — Live state cluster`. S2.6 is **not** the place for surface-internal polish — that work was done in each surface's own iteration loop. If S2.6 finds an in-surface P0/P1, route it back to a `S2.x.N+1` iteration before opening the PR.

---

## 5. Phase 3 — Global chrome + auth + errors (3 surfaces + cluster polish, iterative)

Same iterative model as P2 (per §1.5b). Global chrome runs before pre/post-state cluster work because every state-bearing surface inherits the chrome — fixing chrome first means later state-cluster sessions don't fight chrome regressions.

### Surface inventory (each iterates per §1.5b until converged)

- [x] **S3.1 — `templates/base.html` (navbar, footer, sub-nav slot, body class flow).** This sets the chrome every other surface inherits. Likely Priority Issues at first iteration: navbar dropdown a11y, footer voice/utility split (DESIGN.md defines the two-band structure), sub-nav scroll behavior on mobile, navbar-scrolled compaction smoothness.
  - [x] **S3.1.1** — first iteration.

- [x] **S3.2 — Auth pages cluster.** `login.html`, `register.html`, `forgot_password.html`, `reset_password.html`, `change_password.html`, `profile.html`. Run a single `$impeccable critique` per page (they're small, batch is feasible). Likely Priority Issues at first iteration: auth-page Tribunal Black backdrop atmosphere, focus management, error message voice, password-reset-token UX.
  - [x] **S3.2.1** — first iteration.

- [x] **S3.3 — Platform home (`core/main/templates/main/index.html`) + non-state component partials.** Biggest single template by partial-count. The home page dispatcher critiques separately from the four state partials (which are covered in P2/P4/P5). This surface focuses on the dispatcher and any partials not already touched (e.g., `_game_card.html`, `_game_tiles_compact.html`).
  - [x] **S3.3.1** — first iteration.
  - [x] **S3.3.N** — until convergence (converged at S3.3.2).

- [x] **S3.4 — Errors + cross-cluster polish (NOT cluster mop-up).** Runs only after S3.1–S3.3 converge. Combines: (a) `404.html` / `500.html` first-iteration critique (these are small enough that one iteration usually converges them), (b) cross-cluster polish per the S2.6 model — patterns visible only when comparing 2+ chrome surfaces. **Step 0:** sweep §0.4 for `[Sx.y.N cross-cluster]` items routed to S3.4. **Step 1:** errors first-pass critique + fix. **Step 2:** cross-cluster polish (cap 3-5 findings). **Step 3:** re-run `$impeccable critique` against S3.1–S3.3 + errors; confirm no regressions. **Step 4:** open PR `Impeccable P3 — Global chrome + auth + errors`. If S3.4 finds an in-surface P0/P1, route to that surface's `Sx.y.N+1` iteration before opening the PR.

---

## 6. Phase 4 — Pre-live state cluster (4 surfaces + cluster polish, iterative)

Same iterative model as P2/P3.

### Surface inventory (each iterates per §1.5b until converged)

- [x] **S4.1 — `_home_pre.html` + `_home_out.html`** (the *platform* home in pre + logged-out states, dispatched from `core/main/routes.py` via `core/main/templates/main/index.html`). Original plan label said "WC home in pre states" — actual surfaces resolved to the platform home partials per S3.3.1's routed-in items and the dossier composition (countdown decree + ballot card + join CTA + opening matches). The WC game home (`games/worldcup/templates/worldcup/_home_pre.html` + `_home_out.html`) is a separate surface served at `/worldcup/` and is NOT part of S4.1 scope. **Converged 2026-05-11 at S4.1.2** — see §9 rollup for per-iteration entry.
  - [x] **S4.1.1** (commit `170b1e2`) — landed PI-1 (`$impeccable layout` — registry grid reshape closing the S3.3.1-routed identical-card-grid + missing-`<h2>` items as one atomic edit) + PI-2 (`$impeccable distill` — countdown 4-cell hero-metric adjacency collapse to one dominant Days numeral + Newsreader derivation) + PI-3 (`$impeccable adapt` — `.decree-links` 44×44 tap-target floor) + F1 (S3.3.1-inherited `.join-alt a` 44×44 floor). Gate: **FAIL** on §1.5b condition (4). 4 in-surface items routed to S4.1.2; 1 cross-phase item routed to S6.1.
  - [x] **S4.1.2** (commit `05119a3`) — landed PI-1 (`$impeccable layout` — pre-state desktop 7fr/5fr 2-col reshape, mobile parity preserved) + PI-2 (`$impeccable adapt` — `.ballot-card` whole-area-link semantic split with inline `Edit roster ›` action) + PI-3 (`$impeccable distill` — 2-tier home-shell card vocabulary `Ceremonial` vs `Informational` codified in DESIGN.md §5) + PI-4 (`$impeccable delight` — `.out-prop` row-specific texture: icon / spark / monogram). Gate: **PASS** on all four §1.5b conditions. Surface CONVERGED.

- [x] **S4.2 — `picks.html` + `_pick_row.html`** (the pick UI cluster). The highest-stakes pre-live surface; users spend the most time here. **Converged 2026-05-11 at S4.2.2** — see §9 rollup for per-iteration entries.
  - [x] **S4.2.1** (commit `b097e8a`) — landed PI-1 (`$impeccable harden` — keyboard / AT primitive: `.wc-team-card` to `role=checkbox tabindex=0 aria-checked` triad with Space/Enter handler; visually-hidden checkbox carrier) + PI-2 (`$impeccable optimize` — pick-accordion grid-template-rows 0fr↔1fr replacing the banned `max-height` layout animation + 600px clip ceiling) + PI-3 (`$impeccable adapt` — atomic 44×44 floor on `.picks-rules-link` + `.team-group-pill`) + PI-4 (`$impeccable colorize` — Council Purple tinted-neutrals replace literal WC navy on platform components; `.tier-badge` `#fff` → `--text-on-dark`) + F1 (counters aria-live) + F2 (readonly card-header H4 → H2 with new `.pick-card-head` surface class) + F3 (mobile Grp letter `--text-muted` → `--text-secondary` AA). Gate: **FAIL** on §1.5b condition (4). 7 in-surface items routed to S4.2.2; 2 cross-cluster items routed to S4.5; 1 cross-phase item routed to S6.1.
  - [x] **S4.2.2** (commit `ebeb8df`) — landed PI-1 (`$impeccable distill` + `$impeccable adapt`, atomic per §1.5b — mobile readonly `.player-pick-card` to `<a>` with `team_detail` href + `.wc-tier-dot` + Teko tier name collapse; `.tier-badge` demoted to summaryList JS) + PI-2 (`$impeccable typeset` — `.wc-numeral--xl/--lg/--md/--sm` modifier classes; 4 inline `font-size` declarations retired) + PI-3 (`$impeccable harden` — edit-form heading outline H1 → H2×6 via `.tier-card-heading` + `.pick-summary-heading` classes) + PI-4 (`$impeccable polish` — `.pick-summary` 3px top-stripe removed; full perimeter border + eyebrow + H2 carry hierarchy) + PI-A1 (`$impeccable harden` — in-iteration §1.7 fold-in: scoped `.card.wc-card .wc-numeral` → bone AND `.tier-card-heading .wc-multiplier-chip` → ink-on-purple, closing F2-introduced light-surface regression + latent dark-card numeral) + F1 (`\2713` markup-as-icon → CSS-mask SVG) + F2 (`--wc-white` → `--text-on-dark` hygiene). Gate: **PASS** on all four §1.5b conditions. Surface CONVERGED.

- [x] **S4.3 — `join.html` + `rules.html`**. Lower-frequency but first-impression critical. Likely Priority Issues at first iteration: rules typography (long-form Newsreader prose), join CTA voice, scoring system explanation depth. **Converged 2026-05-11 at S4.3.1** — see §9 rollup for per-iteration entry.
  - [x] **S4.3.1** (commit `d17add1`) — landed PI-1 (`$impeccable harden` — rules.html `.card.wc-card > .card-body` prose lift to bone, scoped via direct-child selectors to avoid leaking into `.tier-mobile-card` light substrate; closes ~1.4:1 dark-on-dark across seven panels) + PI-2 (`$impeccable harden` — `.table-worldcup .wc-multiplier-chip` + `.tier-mobile-card .wc-multiplier-chip` + `.tier-mobile-card .text-muted` + `.tier-teams-list` light-substrate scopes; chip + mobile-card meta lifted from ~1:1 / ~3:1 to ~6–14:1) + PI-3 (atomic — join.html voice + outline + link rewrite: hero eyebrow + Tribune H1 "Sign the ledger." + editorial paragraphs replacing bullet-list + H3 → H2 `.wc-section-heading` + `&middot;` retired + CTA "Take your seat" + `.join-rules-link` replacing `text-muted small`) + PI-4 (atomic — rules.html H3 → H2 ×7 with `.wc-section-heading`, H5 → H3 ×2 with `.wc-subsection-heading`, inline-Teko declarations retired on headings ×7 + on mobile tier-card name/picks ×2, Champion-row raw-navy literal ×2 → `.wc-champion-row > td` Council Purple tint defeating `--bs-table-bg` mask) + PI-5 (`$impeccable harden` — `body.game-worldcup .form-label, body.game-worldcup .form-text` → `--text-secondary`, scoped lift mirroring S3.2.1 PI-2's auth-page scope). Gate: **PASS** on all four §1.5b conditions. Surface CONVERGED.
  - [ ] **S4.3.N** — N/A (converged at S4.3.1).

- [x] **S4.4 — `groups.html`**. Lower-priority pre-live scoreboard; one of the few public WC routes. **Converged 2026-05-11 at S4.4.1** — see §9 rollup for per-iteration entry.
  - [x] **S4.4.1** (commit `93326ce`) — landed PI-1 (`$impeccable polish` — atomic with freebie F3: `.group-table-header` `<div>` → `<h2 class="group-table-header wc-section-heading">` with stable `id="group-{letter}-heading"`; each `<table>` carries matching `aria-labelledby`; the compound `.group-table .group-table-header` selector at spec 0,0,2,0 owns surface-specific properties [bg, color, padding, font-size 1.1rem, margin 0] and beats `.wc-section-heading`'s later-in-file 0,0,1,0 cascade; the primitive owns family/weight/transform/letter-spacing so the rule no longer duplicates them) + PI-2 (`$impeccable polish` — `.group-table table th` + `.advancement-badge.eliminated` lifted from `--text-muted` (#8A849B, ~3.6:1 on white) to `--text-secondary` (#5A5470, ~6.9:1); canonical AA-on-bone fix per memory `project_text_muted_aa_on_bone`) + PI-3 (`$impeccable layout` — `<nav class="wc-group-index" aria-label="Jump to group">` pill rail above the 12-card grid; 12 anchor pills A–L each 44×44 floor with canonical CCC gold-light `:focus-visible` ring; closes the identical-card-grid hard hit by inserting a dominant top band + gives the ~5000px mobile scroll its only viable in-page navigation) + PI-4 (`$impeccable adapt` — `.team-name-cell { font-size: 1rem }` lifts the primary read-target to the PRODUCT.md 16px mobile body floor; removed the `@media (max-width: 400px)` `.team-name-cell { font-size: .82rem }` override that pushed it to ~13.1px on a 375 viewport; numeric W/D/L/Pts cells stay compact for tabular scan) + PI-5 (`$impeccable clarify` — `groups()` route imports `worldcup_state` and threads `wc_state` into context; hero eyebrow shifted from H1-restating "Group standings" to Tribune-voiced "The pairings are drawn."; lead rewritten from "12 groups · 48 teams · 2026 FIFA World Cup" [restated H1 + chrome] to "Top two from each group plus the eight best third-place finishers carry into the Round of 16." [teaches the advancement math]; `.wc-state-chip` branched on `wc_state` renders below the hero on the bone canvas: pre purple-tinted "Group Stage opens Jun 11" / live "Tournament in play" / post gold-tinted "Final sealed") + F1 (numeric column widths moved from inline `style="width:Npx"` to `.group-stat-col` + `.group-pts-col` classes) + F2 (`&middot;` retired from the lead via the rewrite) + F3 folded into PI-1 (`aria-labelledby` on `<table>`). Gate: **PASS** on all four §1.5b conditions (0 P0, 0 unrouted P1, 0 anti-pat hits, heur 24→30/40 clears path (b) baseline+6 = 30 floor exactly). 2 P3 items routed forward — 1 cross-cluster (pill-rail width on ultra-wide → S4.5), 1 cross-phase (Tribune-voiced H1 → S6.1). 2 P2 items ship-as-is. Surface CONVERGED.

- [x] **S4.5 — Cross-cluster pre-live polish (NOT cluster mop-up).** Ran 2026-05-11 after S4.1–S4.4 converged. **Step 0** (sweep): 7 `[cross-cluster]` items routed to S4.5 enumerated from §0.4. **Step 1** (triage 3-5 PIs per §1.5c, outcomes incl. fix / no-op / re-route): see §9 rollup row for S4.5 — 3 fix + 1 re-route + 1 decided-no-op + DESIGN.md route. **Step 2** (Layer B Playwright/Chrome MCP on touched + adjacent surfaces): no regressions; Layer C skipped per §1.5c default. **Step 3** (PR): Impeccable P4 PR opens at session end.

---

## 7. Phase 5 — Post-live state cluster (2 surfaces + cluster polish, iterative)

Same iterative model as P2/P3/P4.

### Surface inventory (each iterates per §1.5b until converged)

- [ ] **S5.1 — `_home_post.html`** (the World Cup home in post state). Likely Priority Issues at first iteration: champion banner emotional payoff, retrospective tone, "the club will remember" voice from DESIGN.md's North Star.
  - [x] **S5.1.1** — first iteration (3 PIs closed: hero-metric-adjacency collapse on "Your Finish", Tribune retrospection line on the champion banner, eyebrow disambiguation `Champion` → `World Cup Winner`). Not converged — 1 in-surface backlog item routed to S5.1.2 (mobile tap-target floor on podium + roster anchors), 2 cross-cluster items routed to S5.3, 1 cross-phase item routed to S6.1.
  - [x] **S5.1.2** — second iteration. Single inherited PI closed: Podium + Roster anchor 44×44 tap-target floor via class-scoped `.post-table-link` (precedent: `.picker-link` / `.team-link` / `.join-alt a` / `.decree-links`); rejected the `.card.wc-card .table a` broadcast that would bleed onto adjacent WC tables. Detector clean on partial; Layer B sweep confirms all 12 post-state anchors clear 44×44 at 375 (was min 33×15). Gates 1-3 PASS by inspection (0 P0, 0 unrouted P1, 0 anti-pat hits on the partial); gate (4) score-gate unverified — no Layer C re-critique run this iteration. 6 Layer A locks in `tests/test_design_p5_s5_1_2.py`. 641 tests passing (was 635, +6).
  - [ ] **S5.1.N** — until convergence (gate (4) Layer C verification or fresh-finding cleanup).

- [x] **S5.2 — Post-state component partials.** `_champion_banner.html`, `_commish_note.html`, `_dispatches.html`. **Plan deviation (per §1.8):** the inventoried `_recent_results.html` (post variant) is live-only — it's included by `_home_live.html:72` and not by `_home_post.html`. S5.2 scope therefore resolved to **3 partials**, not 4. `_dispatches.html` ships as an entirely commented-out Jinja scaffold (renders nothing until the file is populated by the Commish) — it carries no anti-pattern surface this iteration. **Converged 2026-05-12 at S5.2.1** — see §9 rollup for per-iteration entry.
  - [x] **S5.2.1** — first iteration. Three Priority Issues closed: PI-1 (`$impeccable harden` — gradient text retired on `.home-shell .champion-name`; replaced `var(--metal-gold)` `background-clip: text` recipe with solid `var(--gold-light)` mirroring the `.home-metal-text` precedent at `style.css:461`); PI-2 (`$impeccable clarify` — `_commish_note.html` body Jinja-branches on `state` so pre/live/post each carry their own Tribune-voiced body; closes pre-state "Tribute window opens until June 11" bleed into live and post); PI-3 (`$impeccable clarify` — champion eyebrow text rewrite from `◈ 2026 FIFA World Cup Champions ◈` to `◈ Final Decree ◈`, retiring restated H1 + name and mirroring the pre-state `By Decree of the Commish No 001` decree-stamp voice). Three cross-phase gradient-text rules at `style.css:2208` / `:6644` / `:6928` routed to S6.1 (see §0.4 amendment). Gate: **PASS** on all four §1.5b conditions (0 P0, 0 in-surface P1 unrouted, 0 anti-pat hits on the 3 partials per detector + sub-agent inspection, heuristics 33/40 clears gate (a) ≥32/40 floor). 11 Layer A locks in `tests/test_design_p5_s5_2_1.py`. Surface CONVERGED.
  - [ ] **S5.2.N** — N/A (converged at S5.2.1).

- [x] **S5.3 — Cross-cluster post-live polish.** **Step 0** swept §0.4 → 2 routed items from S5.1.1 (`.wc-numeral` bone-on-white in `.card.wc-card .table`; `.btn-outline-secondary` quicklink 3.04:1 contrast). The first was tagged for re-route to S6.1 if cross-phase; session-time verification confirmed cross-phase scope but Brad chose to take in-session as a documented §1.8 deviation (one selector-scoped CSS rule). **Step 1** identified 2 cross-cluster Tribune-voice patterns spanning the platform `_champion_banner.html` (S5.2 surface) and the WC `_home_post.html` banner (S5.1 surface): champion-eyebrow voice mismatch ("World Cup Winner" wire-service vs. "◈ Final Decree ◈" Council) and Tribune-retrospection inversion (the cluster's secondary banner carried the retrospection line; the primary full-bleed banner didn't). 4 PIs total: PI-1 + PI-2 closed both routed items; PI-3 + PI-4 closed both Step 1 patterns. **Step 2** Layer B verification at session-time: 4-PI computed-style probe via Playwright confirmed each fix at runtime (in-cell `.wc-numeral` `rgb(28, 23, 48)`; quicklinks `rgb(243, 239, 230)`; WC banner eyebrow "Final Decree"; platform retrospect "The Club records the night." in Newsreader italic at .82 bone). 15 Layer A locks in `tests/test_design_p5_s5_3.py`. **Step 3:** PR opened (`Impeccable P5 — Post-live state cluster`).

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
- [x] **S2.6** — cross-cluster live polish (commit: 9b7cc2f). 4 §0.4 [cross-cluster] items CLOSED, 3 re-routed to S6.1 cross-phase polish, 1 re-routed to S4.5 pre-live cross-cluster polish (per S2.6 Step 1 cap 3-5; 4 PIs landed). Closed: (PI-1) Bootstrap-on-`.card.wc-card .table` contrast safety lock via `--bs-table-bg: var(--bg-card)` defensive default — makes the white-td masking a CCC-owned design decision rather than an implicit Bootstrap default; surfaces that want dark navy bleed-through still opt out via scoped `background-color: transparent` on `> tbody > tr > td` (the canonical `.player-picks-desktop` pattern). (PI-3) `.text-muted` Bootstrap gray (`#6c757d`) retired on light live-cluster surfaces in favor of CCC purple-tinted `--text-secondary` (`#5A5470`) — schedule stage-count `<small>` (×2) keeps the `.schedule-stage-count` class only (no Bootstrap `text-muted`) with scoped color, team_detail no-fixtures empty state lifted to `.team-fixtures-empty`, team_detail path-to-crown explainer lifted to `.team-path-fineprint`, both resolved to `--text-secondary` via a shared CSS rule. (PI-4) `.schedule-jump-today` pill chip in the schedule `.page-hero` linking to the S2.2.1 `id="today"` anchor, guarded by a `selectattr('is_today')` template filter so it disappears pre/post-tournament — closes the live-state surfacing gap where the today block sat 6-11 matchdays into the page. (PI-2, decided no-op) double-elevation on `.wc-stat-card` / `.your-standing-tribune` is **not** a violation — DESIGN.md §4.4 "Lift-At-Rest Rule" and §6 card primitive explicitly mandate `1px solid var(--border)` + `--shadow-sm` at rest; the impeccable generic "single-elevation" heuristic is overridden by the committed policy. Re-routed to S6.1: (a) gradient-card silhouette across home variants (needs pre/live/post comparison after P4/P5); (b) leaderboard rolls non-interactive `<div>` (paired with player_detail rivalry-comparison-strip work in S2.5.2); (c) `.wc-eyebrow` saturation + `.wc-meta-label` primitive ratification (needs cross-phase comparison after every surface family has rendered through ≥1 iteration). Re-routed to S4.5: inline-Teko `.wc-microcaption` utility extraction (S2.6 grep verified the duplication exists only in stats.html + picks.html / rules.html / join.html — extracting now would consolidate stats.html alone and need a second migration pass when P4 lands). 8 Layer A regression tests added under `tests/test_design_p2_s2_6.py`; pytest green (404 passed). Live computed-style verification on schedule (chip 216×44, color `rgb(243,239,230)`, `min-height: 44px`, `href="#today"`; stage-count `rgb(90,84,112)`), team_detail (path-fineprint `rgb(90,84,112)`), leaderboard (`--bs-table-bg = #FFFFFF`), player_detail (`--bs-table-bg = #FFFFFF` set, explicit `background-color: transparent` from S2.5.1 wins). Screenshots under `.impeccable-review/S2.6/after/`. Per §1.5b: S2.6 is not a per-surface iteration so no convergence gate applies; the bar is "all S2.1–S2.5 surfaces hold; no in-surface P0/P1 surfaced" — held.
- [x] **PR P2** opened: `#13`

### Phase 3 — Global chrome + auth + errors
- [x] **S3.1** — base.html chrome (converged: 2026-05-11, S3.1.1)
  - [x] S3.1.1 (commit: df999ae) — heur 28→32/40 (Δ +4), anti-pat hard hits 3→0. Gate: **PASS** (0 P0, 0 unrouted P1 — 2 P1s routed: PI-A1 navbar-brand color drift `[cross-cluster] → S3.4`, PI-A2 trophy CTA worst-stop contrast already in §0.4 line 100 `[cross-phase] → S6.1`; 0 anti-pat hits, heuristics 32 ≥ gate-(a) floor of 32). 4 PIs landed: PI-1 navbar cascade cleanup (removed gradient `!important` + dead-code border/transition lines so DESIGN.md §5's solid `var(--purple-700)` + 1px `--purple-800` border renders), PI-2 `.navbar-brand` 44×44 mobile touch floor (Plan §0.4 listed), PI-3 sub-nav inactive `.subnav-pill` text alpha .48→.75 (composited contrast 4.87:1→10.55:1 on `#00122e` WC bg), PI-4 CCC-tinted skip-link before navbar + `<main id="main-content" tabindex="-1">` (WCAG 2.4.1 baseline). 2 freebies: F1 drop `.navbar-brand:hover` 20px gold `text-shadow` (Trophy Rule, DESIGN.md §2), F2 drop `border-width` from `.navbar` transition (don't animate layout properties). 4 in-surface §0.4 entries routed to S3.4 cross-cluster chrome polish (orphan navbar-brand color, missing `:focus-visible` on nav-link/subnav-pill, `aria-label` on game-subnav container) + 3 ship-as-is items.
- [x] **S3.2** — auth cluster (converged: 2026-05-11, S3.2.1)
  - [x] S3.2.1 (commit: 8c9c3b2) — cluster heur 24.8→31.5/40 avg (Δ +6.7), audit 10.5→14.5/20 avg (Δ +4.0), anti-pat hard hits 0→0 (profile's 1 soft hit — inline `<style>` + Bootstrap-neutral hexes — routed to S3.2.2 PI-A). Gate: **PASS** on all 4 §1.5b conditions (0 P0, 0 unrouted P1 — N1 new P2 link-row contrast near-miss [4.40 vs 4.5 AA-normal; hover/focus 14.48:1 compliant] routed forward, 0 anti-pat hard hits, every surface clears gate-(b) baseline+6 [login 26→33, register 25→32, forgot 28→34, reset 25→32, change-password 23→30, profile 22→28 — exactly at the line]). 5 PIs landed: PI-1 `.auth-link-row` 44×44 floor on 7 cross-flow links across 6 templates with `:focus-visible` gold ring (carries §0.4 S0.3 backlog), PI-2 `body.auth-page .auth-subtitle/.form-text → --text-secondary` lifting 3.13:1 AA-fail off `--text-muted` (memory `project_text_muted_aa_on_bone` second hit; cluster-wide `!important` Bootstrap fight routed to S6.1), PI-3 brand-panel `.brand-sub` alpha .45→.78 + `.brand-game-item` .7→.82 lifting council-purple gradient to 8.49:1 / 9.23:1, PI-4 mobile (`<768px`) `.auth-form-panel { background: transparent }` so Tribunal Black radial bleeds through and the bone card lifts off the atmosphere DESIGN.md §4.4 mandates, PI-5 Tribune voice register sweep — 6 SaaS subtitles + 4 cross-flow phrasings rewritten ("Sign in to your account" → "Step back into the chamber.", "New to the platform? Create an account" → "Not on the rolls yet? Join the Club", etc.). 2 freebies: F1 register submit `.btn-warning btn-lg` → `.btn-primary btn-lg` (markup honesty; body.auth-page paints both gold), F2 register inline-style sweep + new `.form-label-meta` utility for the "(optional)" parenthetical. 6 routed forward: PI-A avatar picker reshape + profile inline `<style>` relocation, PI-D change-password decorative gold key Trophy Rule adjacency, PI-E required-asterisk `#DC3545` → `--danger`, PI-F register password placeholder truncation `<540px`, N1 link-row resting contrast 0.1 short of AA-normal — all `[S3.2.1 in-surface] → S3.2.2`; PI-B split-panel vs auth-wrapper layout contract `[cross-cluster] → S3.4`; PI-C site-wide `.text-muted` !important pattern `[cross-phase] → S6.1`.
- [x] **S3.3** — platform home + partials (converged: 2026-05-11, S3.3.2)
  - [x] S3.3.1 (commit: c3e9222) — heur 20→24/40 (Δ +4), audit 17→19/20 (Δ +2), anti-pat hard hits 1→1 (identical-card-grid in `_home_out.html:75-88`, routed `[cross-cluster] → S4.1`). Gate: **FAIL** on §1.5b (4) — heuristics 24/40 short of gate (b) floor 26 (baseline 20 + 6) by 2 points; first-iteration so gate (c) asymptotic excluded. Gates (1)–(3) pass: 0 P0; 0 unrouted P1 (both first-critique P1s closed — PI-A coming-soon silhouette + PI-B featured-variant retune); 1 anti-pat hard hit but it lives in `_home_out.html` (out-of-S3.3 scope, routed to S4.1 per §0.4) — treated as scope-routed per S2.6 PI-2 precedent. 3 PIs landed: PI-A `$impeccable shape _game_card.html` differentiated `coming_soon` silhouette (dropped `.card-footer`, lifted "Coming Soon" `.status-badge--muted` to eyebrow position above icon with `mb-3`, softened opacity .55→.78 + grayscale 35%→18% so the card reads "not-yet-open" rather than "broken"); PI-B `$impeccable polish .game-card--featured` retuned the dormant featured variant to DESIGN.md compliance — `.featured-game-inner` swapped from hardcoded WC navy (`#00122e`/`#002868`/`#001a44`) to CCC purple+gold radials over `var(--purple-950)` → `var(--purple-800)` gradient, halftone-dot pattern `rgba(255,255,255,.03)` → `rgba(201,162,39,.06)` (Commish Gold per `.page-hero` halftone), `.featured-badge` `#BF0A30` → `var(--live-red)` (DESIGN.md §2 Live and State semantics), `.featured-icon` drop-shadow `rgba(0,0,0,.3)` → `rgba(28,10,58,.45)` (Press-Room Shadow Rule), `.featured-title` `#FFFFFF` → `var(--bone)` (No-Pure-White Rule), `.featured-desc` `rgba(255,255,255,.55)` → `rgba(243,239,230,.78)` (bone-alpha ≈9.9:1 on purple-950), `:hover` box-shadow `rgba(0,40,104,.35)` → `rgba(58,29,114,.35)` (Council Purple); PI-C `$impeccable polish .status-badge--muted` neutral-gray `rgba(120,120,120,...)` → Council Purple `rgba(58,29,114,.07)` background + `rgba(58,29,114,.20)` border (DESIGN.md §2 Tinted-Neutral Rule). 3 freebies: F1 drop `✓` from "Joined ✓" (redundant markup-as-icon; the gold pill carries the state), F2 drop `<i class="bi bi-globe2 me-2">` from featured "Enter the Pool" CTA (brand-retuned variant no longer reads as WC-globe-specific), F3 (axe-discovered) `<h5 class="game-title">` → `<h3>` across 4 non-featured states aligning with featured's existing `<h3>` per DESIGN.md §3 "card-header level h3" — partial-side heading-order fix; residual `<h1>` → `<h3>` gap routes to S4.1 (needs `<h2>` section heading in `_home_out.html`). 16 Layer A regression tests under `tests/test_design_p3_s3_3_1.py`; pytest green (451 passed). Live computed-style verification: `.game-card--coming-soon { opacity: 0.78; filter: grayscale(0.18); pointer-events: none }`; `.status-badge--muted { background: rgba(58,29,114,.07); color: rgb(90,84,112); border: rgba(58,29,114,.2) }`; coming-soon card mobile rect 319×235 vs logged-out 319×300 (silhouettes differentiated); axe heading-order down to 1 violation (was 1; same rule, now firing on `<h3>` instead of `<h5>` — partial fix). Routed forward: `[S3.3.1 cross-cluster] → S4.1` identical-card-grid composition in `_home_out.html:75-88` (1 logged-out + 2 coming-soon at `col-md-4` — partial differentiation done; grid reshape belongs to S4.1), missing `<h2>` between page `<h1>` and grid → S4.1, `_home_out.html:68` "Sign in" link 44×15 tap-floor → S4.1; `[S3.3.1 in-surface] → S3.3.2` slug-branched display copy in `_game_tiles_compact.html:28-29` (hoist via `home_context.py` or add `short_name`/`launch_label` to `GameRegistryEntry`) + lift heuristics +2 to reach gate (b) (1-2 small polish PIs: inline "Opens [season]" microcopy on coming-soon variant for Help/Documentation 2→3; `.game-card--live` `:focus-visible` outline crispness for Flexibility/Efficiency 2→3); `[S3.3.1 ship-as-is]` `_game_card.html` `featured` state declared but no caller — PI-B made the dormant variant DESIGN.md-compliant so S4.1 can wire it when reshaping `_home_out.html`.
  - [x] S3.3.2 (commit: fa922fc) — heur 24→29/40 (Δ +5), audit 19→20/20 (Δ +1), anti-pat hard hits 1→0 in scope (identical-card-grid still routed to S4.1, not re-counted at this level per §1.5b cluster-routed precedent). Gate: **PASS** on all four §1.5b conditions — (1) 0 P0; (2) 0 unrouted P1 (the sole P1 is the routed-pending identical-card-grid for S4.1); (3) 0 in-scope anti-pat hard hits; (4) heuristics 29/40 ≥ gate (b) floor 26 (baseline 20 + 6) by +3 — gate (b) PASS. 3 PIs landed: PI-1 (registry-driven tile copy) added `short_name`/`launch_label` fields to `GameRegistryEntry` (defaults `''` so test mock factories in `test_registry.py` / `test_enrollment_gating.py` pass unmodified), populated on WC/CFB/Golf entries, rewrote `_game_tiles_compact.html:28-29` to read `{{ game.short_name or game.display_name }}` / `{{ game.launch_label or 'TBA' }}` (zero slug knowledge in the partial — a future `CFB Survivor Pool` → `College Football Survivor` rename can't break the label); PI-2 (`$impeccable clarify` — "Opens [season]" microcopy) new `.game-launch-meta` Teko 500 .9rem .14em uppercase line below `_game_card.html` `coming_soon` description, reads `Opens Sep 3` / `Opens 2027`, paints `var(--text-secondary)` (#5A5470, ~6.9:1 on bone, AA-pass) NOT `var(--text-muted)` per `project_text_muted_aa_on_bone` memory — tightened `.game-card--coming-soon .game-desc` margin-bottom .85rem so the new line reads as a tightly-paired temporal anchor; PI-3 (`$impeccable polish` — keyboard focus ring) canonical `:focus-visible` rule on `.game-card--live` matching the S2.1.2-locked pattern: `outline: 2px solid var(--gold-light); outline-offset: 2px; border-radius: var(--radius);` — closes Heuristic 7 (Flexibility/Efficiency) 2 → 3. 10 Layer A regression tests under `tests/test_design_p3_s3_3_2.py`; pytest green (461 passed, +10 vs S3.3.1's 451). Live computed-style verification (Playwright MCP): coming-soon meta `Opens Sep 3` color `rgb(90,84,112)` (`--text-secondary`) ✓, fontFamily `Teko, sans-serif` ✓, fontWeight 500 ✓, fontSize 14.4px (.9rem) ✓, letterSpacing 2.016px (.14em) ✓, textTransform `uppercase` ✓; live-card focus ring outline `rgb(242,211,107) solid 2px` (`--gold-light`) ✓, outline-offset 2px ✓, border-radius 4px (`--radius`) ✓; Golf coming-soon card reads `Opens 2027` from registry ✓. Routed forward: `[S3.3.2 ship-as-is]` Golf `launch_label='2027'` year-not-date precision (revisit when Golf launch firms up), `[S3.3.2 ship-as-is]` `.home-metal-text` class flat-gold-vs-gradient hygiene (already documented at `style.css:399-406`; no action needed). Surface CONVERGED.
- [x] **S3.4** — errors + cross-cluster chrome polish (commit: 0ac96e9) — 4 cross-cluster PIs landed + errors first-pass. Cluster polish session per §1.5c (does not trigger §1.5b convergence gate). PI-0 (errors first-pass): 404.html + 500.html reshaped from hero-metric template (giant `.section-heading` numeral in `--border` `#D8DDE8` on bone `#F3EFE6`, ~1.06:1 contrast — effectively invisible — paired with `.text-muted` subhead failing AA on bone outside any auth-page scope) to Tribune-voice editorial masthead using Eyebrow primitive ("Bulletin · 404" / "Bulletin · 500" — Teko 500 .85rem .14em letter-spacing uppercase `var(--gold)`, per DESIGN.md §3 Eyebrow Rule) above Teko 600 2.4rem display headline and Newsreader serif lede painting `var(--text-secondary)` (~6.9:1 on bone, AA-pass — closes the local `.text-muted` AA-fail without touching the S6.1 site-wide fix scope). New scoped CSS: `.error-page-wrap`, `.error-eyebrow`, `.error-headline`, `.error-lede`, `.error-actions` + mobile clamp. Voice: "This page isn't in the ledger." / "The Commish hit a snag." (Tribune-club) replaces "Page Not Found" / "Something Went Wrong" (SaaS-utility). PI-1 (navbar-brand color drift, §0.4 line 138): orphan `.navbar-brand { color: var(--platform-accent) !important }` block at `style.css:~4019` deleted entirely; load-bearing `font-weight: 700` + `text-transform: uppercase` folded into spec-correct CCC `.navbar.navbar-dark .navbar-brand` block at line 101; DESIGN.md §5 Brand bullet amended to make weight 700 + uppercase explicit. PI-2 (chrome :focus-visible, §0.4 line 139): canonical CCC focus ring (`outline: 2px solid var(--gold-light); outline-offset: 2px`) added to `.navbar .nav-link` (with `border-radius: var(--radius)`) and `.subnav-pill` (already has `border-radius: 22px`). PI-3 (game-subnav semantics, §0.4 line 140): three `.game-subnav` containers switched from `<div>` to semantic `<nav aria-label="<game> section">` in `templates/base.html`; DESIGN.md §5 Game Sub-nav bullet amended. PI-4 (auth composition contract, §0.4 line 149): DESIGN.md §5 gained new "Auth Surface Composition" subsection codifying marketing (split-panel, login/register/forgot/reset) vs utility (`.auth-wrapper`, change_password/profile) split; profile.html normalized from `.container.my-5` to `.auth-wrapper.profile-wrapper` (new modifier widens card to 600px for avatar picker) so utility surfaces share a single wrapper. Layer A: 22 regression tests under `tests/test_design_p3_s3_4.py` (pytest 476 passed; 0 new failures vs pre-S3.4 baseline of 7 date-dependent home_context/home_routes pre-existing failures). 2 S3.1.1 F1 locks superseded — `test_f1_navbar_brand_hover_has_no_gold_text_shadow` retargeted to `test_f1_navbar_brand_has_no_text_shadow_anywhere` (stronger lock: no `text-shadow` in any `.navbar-brand` rule), `test_f1_navbar_brand_transition_excludes_text_shadow` retargeted to `test_f1_no_orphan_navbar_brand_hover_block` (the orphan that hosted the transition is gone). Layer B verification (Playwright MCP, 1280 + 375): `.navbar-brand` color `rgb(243,239,230)` (bone, was `rgb(201,162,39)` gold pre-S3.4) ✓, font-weight 700 ✓, text-transform uppercase ✓; `.navbar .nav-link:focus` outline `rgb(242,211,107) solid 2px` outline-offset 2px border-radius 8px ✓; `.subnav-pill:focus` outline `rgb(242,211,107) solid 2px` outline-offset 2px ✓; `.game-subnav` tagName `NAV` aria-label "World Cup section" ✓; /404 error-eyebrow `rgb(201,162,39)` Teko 500 13.6px 1.904px letter-spacing uppercase ✓; .error-headline `rgb(28,23,48)` Teko 600 38.4px (1.9rem mobile clamp confirmed at 375 viewport: 30.4px) `<H1>` ✓; .error-lede `rgb(90,84,112)` (=`--text-secondary`, AA-pass on bone) Newsreader serif ✓. Adjacent surfaces (login, register, worldcup hub, home) probed for navbar regressions — bone wordmark holds across split-panel and utility auth + game blueprints + platform home.
- [ ] **PR P3** opened: ____

### Phase 4 — Pre-live state cluster
- [x] **S4.1** — `_home_pre` + `_home_out` (converged: 2026-05-11, S4.1.2)
  - [x] S4.1.1 (commit: 170b1e2) — heur 24→28/36 (Δ +4; ≈31/40 normalized), audit 17→18/20 (Δ +1, est. — F1 + PI-3 tap-target floors close 2 axe a11y misses; deterministic detector stays `[]` against source), anti-pat hard hits 2→0 (identical-card-grid in `_home_out.html` + hero-metric adjacency in `_countdown_card.html` both closed in scope). Gate: **FAIL** on §1.5b (4) — heuristics 28/36 ≈ 31/40 short of gate (a) floor 32/40 by ~1 and gate (b) floor 30 (baseline 24 + 6) by 2; first-iteration so gate (c) asymptotic excluded. Gates (1)–(3) pass: 0 P0; 0 unrouted P1 (4 in-surface P1/P2 routed to S4.1.2: pre-state desktop 2-col layout, `.ballot-card` whole-area-link semantic, 3 gold-bordered card recipe consolidation, value-prop strip differentiation; 1 cross-phase P3 routed to S6.1: flash banner masthead competition); 0 in-scope anti-pat hard hits. 3 PIs + 1 freebie landed: **PI-1** (`$impeccable layout`, closes 2 routed items) — replaced `_home_out.html:75-88` `col-md-4` 3-up Bootstrap grid with `<section aria-labelledby="out-registry-head">` + `<h2>Pools in Session</h2>` + 1-col-mobile / 7fr+5fr-desktop CSS grid: 1× large `.out-featured` card (CCC purple+gold radial atmosphere — `var(--purple-950)` → `var(--purple-800)` linear gradient with commish-gold + chamber-purple radial overlays, halftone-dot ::before pattern, Teko 700 title `clamp(1.6rem, 4vw, 2.4rem)`, gold metal `.out-featured-cta` with `var(--shadow-gold)` glow, hover lift `translateY(-3px)` + cubic-bezier overshoot, canonical 2px gold-light `:focus-visible` ring at 4px offset) + 1× `.out-coming-rail <aside aria-label="Pools coming soon">` with stacked `.out-coming-strip` rows (48×48 muted icon tile with `grayscale(0.18)` filter + opacity .78 + Teko display name + Teko meta `Opens {{ game.launch_label or 'TBA' }}` reading from S3.3.2 registry fields); featured card preserves logged-out auth-flow link (`auth.register?next=blueprint_join`). Probed silhouettes: desktop 1470 = featured 742×353 + rail 530×353 with 2 strips at 488×72 (different shapes); mobile 375 = featured 319×364 + 2 strips at 277×72; H1→H2→H3 outline restored (pre-fix: H1 → H3 ×3 with no H2). **PI-2** (`$impeccable distill` — countdown collapse) — replaced `_countdown_card.html` 4-cell `.decree-days .d-cell` strip (which rendered four equal-weight Teko-700 numerals at 2.8rem mobile / 3.6rem desktop — the S2.3.1-locked hero-metric adjacency ban) with `.decree-hero` containing one dominant Days numeral (Teko 700 at `4.5rem` mobile / `6rem` desktop, `tabular-nums` so the tick doesn't reflow) + `.decree-hero-unit` "Days to the Whistle" eyebrow line (Teko 500 0.78rem .22em uppercase gold-light per DESIGN.md §3 Eyebrow Rule) + `.decree-derivation` Newsreader-italic prose line carrying the live HH/MM/SS tick (`01h · 43m · 46s ticking`) as supporting derivation rather than four equal-weight numerals; `data-cd-days/hours/mins/secs` attributes preserved on the new elements so `static/js/countdown.js` keeps ticking without modification. **PI-3** (`$impeccable adapt`) — `.home-shell .decree-links a` (the bottom-row "House Rules" + "Scoring" links inside the countdown card) added `min-height: 44px; min-width: 44px; padding: 0.65rem 0.75rem` + canonical 2px gold-light `:focus-visible` ring, lifting from 93×20 / 67×20 (pre-fix probe) to 117×44 / 91×44 (post-fix probe). **F1** (inherited from S3.3.1 §0.4) — `.home-shell .join-alt a` ("Already sworn in? Sign in") added inline-flex with `min-height: 44px; padding: 0.6rem 0.5rem; margin: -0.6rem -0.5rem` (the S2.1.2-locked negative-margin recipe that preserves the inline-running-text baseline) + canonical `:focus-visible` ring, lifting from 44×15 to 60×44. 18 Layer A regression tests under `tests/test_design_p4_s4_1_1.py`; pytest green (501 passed, +18 vs S3.4's 483). Live Playwright computed-style verification at desktop 1470 + mobile 375: out-state `.out-registry-grid` 7fr+5fr at md+ ✓, featured 742×353 + rail 530×353 at desktop ✓, 1-col 319-wide stack at 375 ✓, H1→H2→H3 outline ✓, `.join-alt a` 60×44 ✓; pre-state `.decree-hero-num` 96px (`6rem`) at desktop ✓ / 72px (`4.5rem`) at mobile ✓, `.decree-derivation` reads "01h · 43m · 46s ticking" ✓, `.decree-links a` House Rules 117×44 + Scoring 91×44 ✓; deterministic detector `npx impeccable --json --fast` returns `[]` against source (same as baseline). Routed forward: `[S4.1.1 in-surface] → S4.1.2` pre-state desktop 2-col layout (1280-px canvas wasted by 640-px `.home-col` floor; substantial scope affecting 3 dossier variants + opening matches + commish/dispatches; live-state regression risk via shared `.home-shell`), `.ballot-card` whole-area-link semantic (AT swallows foot copy; needs `<section>` + inline `Edit roster ›` action), 3 gold-bordered card recipe consolidation (decree vs cta-card vs match-card; needs DESIGN.md §5 Ceremonial vs Informational vocabulary addition), `.out-prop` ×3 value-prop strip differentiation (P3); `[S4.1.1 cross-phase] → S6.1` flash banner competing with home-shell masthead (lives in `base.html` chrome, spans every authenticated home + game page). Next: S4.1.2.
  - [x] S4.1.2 (commit: 05119a3) — heur 28→32/36 (Δ +4; ≈35.5/40 normalized), audit 18→19/20 (Δ +1, est. — PI-2 ballot semantic split removes the whole-area-link a11y miss; deterministic detector stays `[]` against source), anti-pat hard hits 0→0 (no new hits introduced; PI-3 closes the within-viewport 3-gold-bordered-card-recipes drift, PI-4 closes the within-strip identical-icon-row silhouette, PI-1 closes the phone-shaped column layout-inefficiency observation, all in scope). Gate: **PASS** on all four §1.5b conditions — (1) 0 P0; (2) 0 unrouted P1 (the single remaining routed P1 is `[S4.1.1 cross-phase] → S6.1` flash banner masthead competition, still routed forward); (3) 0 in-scope anti-pat hard hits; (4) gate (a) PASS — heuristics 32/36 ≈ 35.5/40 ≥ 32 floor by +3.5; gate (b) also PASS (baseline 24 + 6 = 30 floor, actual 32, +2 over). Surface CONVERGED. 4 PIs landed (all inherited routed backlog from S4.1.1 per §1.5b "Iteration 2+ inherits its own backlog"): **PI-1** (`$impeccable layout` — pre-state desktop 2-col reshape) — replaced `_home_pre.html` single `.home-col` (`max-width: 640px`, phone-shaped at every viewport) with `.home-pre-grid` collapsing to 640-floored single column below md (parity with legacy `.home-col` so mobile reading order unchanged), 7fr/5fr CSS grid at `min-width: 768px` with two semantic slots: `.home-pre-col--main` carries greet + countdown + dossier (one of `_ballot_card` / `_submit_picks_cta` / `_join_cta_card`); `.home-pre-col--rail` carries opening matches + game tiles + commish note + dispatches. Probed at desktop 1280: grid 1180×1147 with `grid-template-columns: 669.664px 478.328px` (7/12 × 1148 = 669 ✓, 5/12 × 1148 = 479 ✓), gap 32px; main col at x=50, rail at x=752. Probed at mobile 375: grid 343×?, single column, main.bottom=1036 === rail.top=1036 (clean vertical stack, no horizontal scroll). `_home_live.html` regression-locked by Layer A (`test_pi1_home_live_unchanged_keeps_container_fluid_row_layout`): live state must NOT pick up `.home-pre-grid`, keeps its own `.container-fluid.home-live > .row` composition. **PI-2** (`$impeccable adapt` — `.ballot-card` semantic split) — unwrapped the whole-area `<a href="...?edit=1">` that swallowed the flag ribbon + foot prose into one screen-reader link and routed every flag tap to "edit pick" instead of team-detail. New shape: `<section class="ballot-card" aria-labelledby="ballot-status">` + explicit inline `.ballot-edit-action` anchor next to `.ballot-foot-prose`. Flags become a decorative ribbon (`aria-label="Your nine selected nations"` on container + `aria-hidden="true"` on each `.ballot-flag` span so AT users hear the ribbon's name, not nine bare flag emoji). Hover lift removed from `.ballot-card` (dropped from the polish-lift selector group at `style.css:2273` + from the `@media (hover: none)` suppression block); moved to `.ballot-edit-action:hover { transform: translateY(-1px); background: rgba(201,162,39,.10); border-color: rgba(201,162,39,.5); color: var(--gold-hi); }`. Probed `.ballot-edit-action` rect 134×44 at both desktop + mobile (PRODUCT.md 44×44 mobile-first floor ✓), `min-height: 44px` declared, canonical `2px solid var(--gold-light)` `:focus-visible` ring. **PI-3** (`$impeccable distill` — card recipe consolidation + DESIGN.md §5 vocabulary) — codified two-tier home-shell card vocabulary: **Ceremonial** = `linear-gradient(180deg, var(--purple-800), var(--purple-900))` + `1px solid rgba(201,162,39,.3)` + `border-radius: 14px` (`.decree`, `.cta-card--join`, `.cta-card--seal`); **Informational** = `linear-gradient(180deg, var(--purple-850), var(--purple-950))` + `1px solid rgba(255,255,255,.08)` + `border-radius: 12px` (`.match-card`, `.cta-card--view`). Normalized `.cta-card--seal` from the outlier gold-overlay `rgba(201,162,39,.1)` gradient + 35%-gold/12px recipe to the Ceremonial recipe (now sharing one rule with `.cta-card--join`); normalized `.decree` border opacity from `.35` to `.3` so all three Ceremonial members share one canonical value (the legacy `.35` drift surfaced via Layer B probe — `getComputedStyle(.decree).borderColor` revealed it). Dropped `border-radius` from base `.cta-card` rule (per-variant value differs between registers). DESIGN.md §5 gained "Card recipes inside `.home-shell`" subsection naming both registers + their canonical class members; explicitly notes `.ballot-card` is a third narrower register (green-tinted "sealed" state) and not part of the two-tier set. **PI-4** (`$impeccable delight` — `.out-prop` ×3 row differentiation) — within-strip identical-icon-row silhouette closed via row-specific texture: row 1 keeps `.out-prop-icon` (`bi-trophy-fill`, gold-light); row 2 swaps for `.out-prop-spark` (inline SVG with `<polyline points="2,28 14,22 24,26 34,14 46,18 62,6">` rising over six leaderboard ticks + terminal `<circle cx=62 cy=6 r=3>` dot, painted `var(--live-green)`); row 3 swaps for `.out-prop-monogram` rendering `<span>◈</span> <span>C</span> <span>◈</span>` per the in-product Commish-seal pattern (gold-light marks at 0.7rem + Teko 600 letter at 1.35rem). All three slots share 36×36 footprint so the row baselines hold (locked by Layer A `test_pi4_out_prop_previews_share_36px_box_so_row_baselines_hold`); all three previews are `aria-hidden="true"` so AT users hear the title + sub line, not three decorative whatsits. Probed at 1280 + 375: all three slots 36×36 ✓, prop rows 113×113×112 at 375 (visual height parity holds). 21 Layer A regression tests under `tests/test_design_p4_s4_1_2.py`; pytest green (522 passed, +21 vs S4.1.1's 501). Live Playwright computed-style verification: desktop 1280 — `.home-pre-grid` 1180×1147 with 7fr/5fr 669/478 split ✓, `.ballot-card` tagName SECTION ✓, `.ballot-edit-action` 134×44 ✓, `.decree` border-radius 14px + `border-color: rgba(201,162,39,.3)` ✓; mobile 375 — `.home-pre-grid` 343×? single column + main precedes rail by vertical stack ✓, `.ballot-edit-action` 134×44 ✓; out-state 375 — 3 rows × differentiated slot (icon/spark/monogram), all 36×36 ✓; deterministic detector `npx impeccable --json --fast` returns `[]` (baseline holds). Routed forward unchanged: `[S4.1.1 cross-phase] → S6.1` flash banner masthead competition. Screenshots under `.impeccable-review/S4.1.2/{home-pre-desktop-1280,home-pre-mobile-375,home-out-desktop-1280,home-out-mobile-375}.png`. Surface CONVERGED.
- [x] **S4.2** — picks + _pick_row (converged: 2026-05-11, S4.2.2)
  - [x] S4.2.1 (commit: b097e8a) — heur 24→27/40 (Δ +3), audit 11→15/20 (Δ +4), anti-pat hard hits 8→0 (all 8 baseline hits closed or formally routed forward via §0.4 with receiving sessions; none in-scope today). Gate: **FAIL** on §1.5b (4) — heuristics 27/40 short of gate (a) floor 32 by 5 and gate (b) floor 30 (baseline 24 + 6) by 3; first-iteration so gate (c) asymptotic excluded. Gates (1)–(3) pass: 0 P0; 0 unrouted P1 (7 in-surface P1/P2 routed to S4.2.2: tier-vocabulary collapse, inline type-scale leakage, mobile readonly non-interactive feature delta, `.pick-summary` top-stripe rewrite, `\2713` markup-as-icon replacement, edit-form heading-order H1→H3 fix, `.wc-multiplier-chip` `--wc-white` token hygiene; 2 cross-cluster P2 routed to S4.5: column-trio derivation table + tier-badge/multiplier-chip vocabulary overlap; 1 cross-phase P3 routed to S6.1: voice repetition stack); 0 in-scope anti-pat hard hits. 4 PIs + 3 freebies landed: **PI-1** (`$impeccable harden` — keyboard / AT primitive) — rewrote `.wc-team-card` from `<div onclick>` + Bootstrap `.d-none` checkbox (unreachable by keyboard / screen-reader users — Sam couldn't make picks at all, the P0 finding) to `role="checkbox" tabindex="0" aria-checked` triad with inline `onkeydown` handler that intercepts Space/Enter with `event.preventDefault()` so Space doesn't scroll page; underlying `<input>` moved from `.d-none` (display:none — drops from AT tree) to `.visually-hidden` + `aria-hidden="true" tabindex="-1"` so it's still form-submitted but not double-announced; canonical 2px gold-light `:focus-visible` ring on `.wc-team-card` matching S2.1.2/S3.4 lock; `toggleTeam(card)` JS extended to `card.setAttribute('aria-checked', ...)` so AT state and selection stay in lockstep. Probed at mobile 375 with Germany (Tier 1, pre-selected) — `aria-checked: true → false` on Space press, counter `2/2 selected → 1/2 selected`, pick summary `9/9 picks → 8/9 picks`, focus outline `rgb(242, 211, 107) solid 2px`. **PI-2** (`$impeccable optimize` — pick-accordion motion-law fix) — replaced `.pick-accordion { transition: max-height 140ms; max-height: 0 → 600px }` (impeccable absolute ban: layout-property animation; AND a hard 600px ceiling that would clip Champion-tier teams with 10+ score events) with CSS Grid `display: grid; grid-template-rows: 0fr ↔ 1fr; transition: grid-template-rows 140ms ease-out` on the outer `.pick-accordion` plus a single `.pick-accordion-inner` wrapper child carrying `border-top: dashed; background: bone-wash; overflow: hidden; min-height: 0`. `_pick_row.html` got the `.pick-accordion-inner` wrapper around its content block (events list + score-events-total OR score-events-empty). Probed: closed `grid-template-rows: 1px (visually 0)` + `opacity: 0` → opened `grid-template-rows: 47.4375px` (auto-fit to content) + `opacity: 1`. No 600px ceiling anywhere in style.css. **PI-3** (`$impeccable adapt` — 44×44 tap-target floor) — atomic combined per §1.5b: hero "View Scoring Rules" link (Bootstrap `.text-white-50 small` 137×23 pre-fix) → `.picks-rules-link` inline-flex with `min-height: 44px; min-width: 44px; padding: .65rem .25rem; margin: -.4rem -.25rem` (S2.1.2-locked negative-margin recipe) + canonical 2px gold-light `:focus-visible` ring + `color: rgba(243, 239, 230, .72)` bone-alpha replacing the cross-phase Bootstrap `.text-white-50` leak (routed to S6.1); `.wc-team-card .team-group-pill` (42×21 pre-fix) lifted to inline-flex with `min-height: 44px; min-width: 44px; padding: .55rem .65rem; margin: -.55rem -.1rem` + focus ring. Probed at 375: rules link 141×45, group pill 52×44 (both clear floor). **PI-4** (`$impeccable colorize` — CCC tinted-neutrals replace literal WC navy + `#fff`) — `.tier-card-header` background gradient `rgba(0, 40, 104, .04/.01)` (literal WC navy on platform component) → `rgba(58, 29, 114, .04/.01)` (Council Purple); `.wc-team-card.selected` background `rgba(0, 40, 104, .04)` + ring `rgba(0, 40, 104, .18)` → `rgba(58, 29, 114, .05/.18)` (Council Purple tint + ring; border keeps `var(--game-primary)` so cross-game scoping still works); `.wc-team-card.selected::after` checkmark color `var(--game-primary)` → `var(--platform-primary)`; `.tier-badge { color: #fff }` (No-Pure-White Rule violation) → `var(--text-on-dark)` (= pressroom-bone). Probed: `.tier-card-header` background resolves to `linear-gradient(135deg, rgba(58, 29, 114, 0.04) 0%, rgba(58, 29, 114, 0.01) 100%)` ✓; `.tier-badge` color `rgb(243, 239, 230)` ✓. **F1** — `aria-live="polite" aria-atomic="true"` on `#counter-{N}` (×5 tier counters) + `#mobilePickCount` so Sam hears progress as picks land. **F2** — readonly card-header `<h4>` → `<h2 class="pick-card-head">` (×2 desktop + mobile, mobile gets `.pick-card-head--mobile` modifier at 1.1rem); new `.pick-card-head` surface class carries the Teko 1.35rem uppercase visual the prior `<h4>` rendered so the H4 → H2 promotion doesn't shift visual hierarchy; readonly heading outline now H1 → H2 (axe heading-order moderate cleared on readonly view; edit-form parallel issue routed forward to S4.2.2). **F3** — mobile `.player-pick-card .pick-team small` (Grp letter) color `var(--text-muted)` (#8A849B, ~3.7:1 on white card, AA fail per `project_text_muted_aa_on_bone` memory) → `var(--text-secondary)` (#5A5470, ~6.9:1) matching S2.5.1 PI-5 lock on `.wc-eyebrow` on the same surface. 25 Layer A regression tests under `tests/test_design_p4_s4_2_1.py`; pytest green (547 passed, +25 vs S4.1.2's 522). Live Playwright computed-style verification at desktop 1470 + mobile 375 (both states — readonly + `?edit=1`): keyboard primitive Germany toggle confirmed end-to-end ✓, focus ring `rgb(242, 211, 107) solid 2px` ✓, grid-template-rows transition 0fr↔1fr verified across open/close ✓, rules link 141×45 ✓, group pill 52×44 ✓, tier-card-header gradient Council Purple ✓, tier-badge color bone ✓, counter aria-live="polite" + aria-atomic="true" ✓, mobilePickCount aria-live="polite" ✓, headings H1→H2→H2 outline ✓, mobile Grp small color `var(--text-secondary)` ✓. Routed forward (8 items in §0.4): `[S4.2.1 in-surface] → S4.2.2` × 7 (tier-vocab collapse, inline type-scale leakage extraction, mobile readonly tap-through, `.pick-summary` top-stripe, `\2713` markup-as-icon, edit-form heading-order, `.wc-multiplier-chip` `--wc-white` token); `[S4.2.1 cross-cluster] → S4.5` × 2 (Base/Multiplier/Points column trio derivation, tier-badge/multiplier-chip vocabulary overlap across cluster); `[S4.2.1 cross-phase] → S6.1` × 1 (Sealed-still-amendable voice repetition stack). Screenshots under `.impeccable-review/S4.2.1/{before,after}/picks-{readonly,editform}-{desktop-1470,mobile-375}.png`. Next: S4.2.2.
  - [x] S4.2.2 (commit: ebeb8df) — heur 27→32/40 (Δ +5), audit 15→17/20 (Δ +2), anti-pat hard hits 0→0 (held). Gate: **PASS** on all four §1.5b conditions — (1) 0 P0; (2) 0 unrouted P1 (both Layer-C-surfaced P1s closed in-iteration via PI-A1 per §1.7 cheap-fold-in rule — F2 caused chip bone-on-white on `.tier-card-heading` ~1.04:1, and the latent `.card.wc-card .wc-numeral` dark-on-dark cell — both fixed in one PI with two scoped CSS rules); (3) 0 in-scope anti-pat hard hits; (4) gate (a) PASS — heuristics 32/40 hits floor of 32 ≥ 32 AND gate (b) baseline+6=30 PASS (+2 over). Surface S4.2 CONVERGED. 5 PIs + 2 freebies landed (PI-1 atomic per §1.5b combines distill+adapt). **PI-1** (`$impeccable distill` + `$impeccable adapt`, atomic) — mobile readonly `.player-pick-card` rewritten: was a non-interactive `<div>` carrying a `.tier-badge tier-badge-N` chip (one of three competing tier primitives across picks); is now `<a href="{{ url_for('worldcup.team_detail', team_id=pick.team_id) }}" class="player-pick-card">` carrying a stacked `.pick-info` block (`.pick-tier-line` with `.wc-tier-dot wc-tier-dot-{{ pick.tier }}` + `.wc-eyebrow` Teko tier name on its own line, above `.pick-team` with flag + name + Grp letter). `.tier-badge` collapsed to ONE place — the sidebar `summaryList` JS builder (the demoted "one place, one job" home). `.wc-multiplier-chip` no longer encodes tier on the mobile readonly card. New `.player-pick-card` styling: `text-decoration: none; color: inherit; transition`; `:hover { border-color: var(--game-primary-light); box-shadow: var(--shadow-sm) }`; `:focus-visible { outline: 2px solid var(--gold-light); outline-offset: 2px }`. Probed at 375: 9 cards, first card `href=/worldcup/team/7`, rect 351×79 (clears 44 floor), text-decoration `none`, eyebrow "Favorites" color `rgb(90, 84, 112)` = `var(--text-secondary)` AA-pass, focus outline `rgb(242, 211, 107) solid 2px` 2px offset, zero `.tier-badge` inside `.player-pick-card`. **PI-2** (`$impeccable typeset` — inline type-scale extraction) — added four `.wc-numeral` modifier classes to `style.css`: `--xl` 1.4rem, `--lg` 1.3rem, `--md` 1.2rem, `--sm` 1.1rem (discrete fixed-scale callers can compose against — `--xl` is the loud-datum size for the tiebreaker total, `--lg` the desktop card-header total, `--md` the mobile card-header total, `--sm` the sidebar summary count). Replaced 4 inline `style="font-size"` declarations on `.wc-numeral` spans in `picks.html` (`:42 → --lg`, `:82 → --md`, `:109 → --xl`, `:205 → --sm`). The mobile readonly `.tier-badge` inline font-size dropped automatically when PI-1's vocabulary collapse removed the badge from the card. Only remaining inline `font-size` in picks.html is the decorative `.bi-x-circle` empty-state icon at 2.5rem — explicitly out of routed PI scope (not a numeral). **PI-3** (`$impeccable harden` — edit-form heading outline) — pre-S4.2.2 the edit-form heading tree was H1 (hero) → H3 ×5 (`.tier-card-header`) → H4 (sidebar `.pick-summary`) with no H2, tripping axe heading-order. Promoted `<h3 class="d-flex…">` → `<h2 class="tier-card-heading">` (×5) and `<h4 class="mb-3">` → `<h2 class="pick-summary-heading">`. New surface-class CSS selectors (`.tier-card-header .tier-card-heading` + `.pick-summary .pick-summary-heading`) carry the Teko 1.35rem / 1.2rem visuals decoupled from element type — visual preserved, semantics improved. Probed edit-form outline: `H1: Amend the Oath → H2: Favorites ×1.0 → H2: Contenders ×1.5 → H2: Dark Horses ×2.5 → H2: Underdogs ×4.0 → H2: Wildcards ×7.0 → H2: Pick Summary` — zero heading-level skips. **PI-4** (`$impeccable polish` — `.pick-summary` top-stripe rewrite) — dropped `border-top: 3px solid var(--game-primary)` (rendered as raw `rgb(0, 40, 104)` WC navy on the bone canvas — side-stripe-adjacent pattern; the impeccable absolute ban targets >1px colored side stripes on cards, a 3px top stripe lives in the same family). Probed: border-top went from `3px solid rgb(0, 40, 104)` → `1px solid rgb(216, 221, 232)` (full perimeter resting border = `var(--border)`). The Teko eyebrow ("Your selections") + H2 "Pick Summary" carry hierarchy without the chrome accent. **PI-A1** (`$impeccable harden` — contrast scope lock, in-iteration §1.7 fold-in) — Layer C critique caught two P1s: (a) F2's chip token swap landed bone-on-white inside `.tier-card-heading` (white tier-card body) at ~1.04:1 — a regression I introduced; (b) `.wc-numeral` on `.card.wc-card` inherits Bootstrap body color (~`rgb(33,37,41)`) and reads near-black on the navy substrate (latent pre-existing bug, surfaced by PI-2's numeral extraction). Two scoped CSS rules close both: `.card.wc-card .wc-numeral { color: var(--text-on-dark) }` lifts the readonly desktop card-header Total + tiebreaker numeral to bone (probed: 12.7:1 AAA on navy); `.tier-card-heading .wc-multiplier-chip { color: var(--text-ink); background: rgba(58,29,114,.07); border-color: rgba(58,29,114,.25) }` re-tints the chip to council-purple ink on bone-tinted-purple for the white tier-card surface (probed: ~14.5:1 AAA on white). **F1** — `.wc-team-card.selected::after` `content: '\2713'` → CSS-mask SVG (`bi-check2` path inline as `data:image/svg+xml`, 14×14, `background-color: var(--platform-primary)` for color control). Affordance is now a real check icon with stable glyph metrics across platforms, no font-cascade dependency. Probed: `::after` content empty `""`, width/height 14px, bg `rgb(58,29,114)` (Council Purple), mask `url(data:image/svg+xml…)`. **F2** — `.wc-multiplier-chip { color: var(--wc-white) }` → `var(--text-on-dark)` (undefined token → canonical token; caused PI-A1 light-surface regression, also closed). 19 Layer A regression tests under `tests/test_design_p4_s4_2_2.py`; full pytest green (566 passed, +19 vs S4.2.1's 547). Live Playwright computed-style verification at desktop 1470 + mobile 375 (both states — readonly + `?edit=1`): all probes ✓ above. Routed forward (3 items in §0.4): `[S4.2.2 ship-as-is]` × 2 (hero-to-card vertical void on desktop readonly P2; accordion-toggle 25×24 desktop hit target P3); `[S4.2.2 cross-phase] → S6.1` × 1 (dark readonly tier-name eyebrow at 0.55 alpha, bundles with the S2.4.1/S2.6-routed `.wc-eyebrow` saturation cross-phase work). Screenshots under `.impeccable-review/S4.2.2/{before,after}/picks-{readonly,editform}-{desktop-1470,mobile-375}.png`. Surface CONVERGED.
- [x] **S4.3** — join + rules (converged: 2026-05-11, S4.3.1)
  - [x] S4.3.1 (commit: d17add1) — heur 24→33/40 (Δ +9; join 25→33, rules 22→33, mean 33), audit 11→19/20 (Δ +8; join 11→20, rules 10→18), anti-pat hard hits 11→0 in scope (5 in-surface hits all closed in this iteration; 6 cross-session-routed remain in §0.4 untouched). Gate: **PASS** on all four §1.5b conditions — (1) 0 P0; (2) 0 unrouted P1 (3 residual P3 polish items all routed: 2 cross-cluster → S4.5, 1 cross-phase → S6.1); (3) 0 in-scope anti-pat hard hits; (4) gate (a) PASS — 33/40 ≥ 32 floor by +1 AND gate (b) PASS — 33 ≥ baseline+6 (30) by +3; first-iteration so gate (c) asymptotic excluded. Surface CONVERGED. 5 PIs + companion freebies landed: **PI-1** (`$impeccable harden`) — `.card.wc-card > .card-body > p / ul / ol / li / h2..h6` direct-child selector lift to `var(--text-on-dark)` (bone). Closes rules.html's seven-panel dark-on-dark prose bug (Bootstrap default `rgb(33,37,41)` on `rgba(0,17,46,.8)` navy substrate computed ~1.4:1 — verified post-fix at 9.52:1 on `<p>` and `<li>` direct children). Direct-child `>` avoids leaking into `.tier-mobile-card` (lavender bg, ink stays dark) per the cluster-wide CLAUDE.md "Don't broadcast `tbody td { color: light }` globally" rule. **PI-2** (`$impeccable harden`) — `.table-worldcup .wc-multiplier-chip` + `.tier-mobile-card .wc-multiplier-chip` scoped to council-purple-on-bone-tint mirroring the S4.2.2 PI-A1 pattern (verified ink `rgb(28,23,48)` on `rgba(58,29,114,.07)`, 14.65:1 on lavender substrate). Bundled: `.tier-mobile-card .text-muted !important` + `.tier-teams-list` lifted off `--text-muted` (#8A849B, ~1:1 on lavender) to `--text-secondary` (#5A5470, ~6.06:1) per the `project_text_muted_aa_on_bone` memory. Added `color: var(--text-primary)` to `.tier-mobile-card` itself so default children inherit ink, not the broadcast `.card.wc-card .text-muted` bone lift that was bleeding through. **PI-3** (atomic — join.html template rewrite, voice + outline + link in one edit per §1.5b atomic-edit rule) — hero gains `<span class="wc-eyebrow">2026 World Cup · Membership</span>` + Tribune H1 `Sign the ledger.` + editorial lead `Nine teams, five tiers, one vote at kickoff.` (replaces generic `2026 FIFA World Cup &middot; ${{ entry_fee }} entry` middot-metadata strip); card body H3 inline-Teko declaration retired in favor of `<h2 class="wc-section-heading">How the pool works</h2>` (closes H1 → H3 outline skip); four-bullet "How It Works" list distilled into two editorial paragraphs preserving the same facts (nine teams, five tiers, multiplier mechanic, USA-goals tiebreaker, entry fee, first-whistle lock); CTA verb `Join the Pool` → `Take your seat` (Tribune membership-rite register matching picks.html "Amend the Oath" lock); decorative `<i class="bi-globe2">` gets `aria-hidden="true"`; "Read the full rules" link below the card restructured from `<a class="text-muted small">` (12.48px Newsreader, bone-on-bone via Bootstrap `.text-muted` cascading rgba(255,255,255,.75) on the game-worldcup body palette) to `<a class="join-rules-link">Read the house rules</a>` (16px Newsreader, `var(--text-secondary)` ~6.23:1 on bone, 195×44 inline-flex clearing the 44 floor, canonical 2px gold-light `:focus-visible` ring at 2px offset, hover lifts to ink + underline). Note: an in-card `<span class="wc-eyebrow">The rite</span>` was added then removed because `.wc-eyebrow` is a dark-substrate primitive (rgba(243,239,230,.55)) and renders bone-on-bone-alpha on a white card body — invisible. **PI-4** (atomic — rules.html template rewrite, outline + literal-color retirements in one edit) — seven section H3 + inline-Teko declarations → `<h2 class="wc-section-heading">` (closes H1 → H3 skip; the new class introduces the canonical Teko 600 1.5rem .04em uppercase primitive that retires `style="font-family:'Teko'..."` saturation across the page); two `<h5>` sub-heads inside Group Stage Scoring card → `<h3 class="wc-subsection-heading">` (Newsreader 600 1.1rem editorial register so the heading hierarchy reads Teko-then-serif descending); two Champion-row instances (knockout table + matrix conditional) → `<tr class="wc-champion-row">` retiring `style="background:rgba(0,40,104,.04); font-weight:700;"` literal-navy tints (S4.2.1 PI-4 retired this pattern site-wide; rules.html was the last holdout); the new `.wc-champion-row > td { background: rgba(58,29,114,.05) !important }` rule paints the tint at the td level so it isn't masked by the S2.6 PI-1 `--bs-table-bg: var(--bg-card)` opaque-white td lock, while `.wc-champion-row { font-weight: 700 }` cascades bold to td content via Bootstrap's `td { font-weight: inherit }`; mobile tier-card inline `style="font-family:'Teko',sans-serif; font-size:1.1rem; ..."` on `.tier-mobile-card-name` + inline `style="font-size:.8rem;"` on the picks-count `<span class="text-muted">` → two new class primitives `.tier-mobile-card-name` (Teko 500 1.1rem uppercase ink) + `.tier-mobile-card-picks` (Newsreader .85rem `--text-secondary`) so the mobile card holds zero inline styles. Decorative `<i class="bi-..."` icons in all seven section headings gain `aria-hidden="true"` (freebie). Knockouts intro paragraph drops `text-muted` (freebie — was leaking the broadcast bone-on-navy lift below the lift's intent). **PI-5** (`$impeccable harden`) — `body.game-worldcup .form-label, body.game-worldcup .form-text { color: var(--text-secondary); }` scoped lift mirroring the S3.2.1 PI-2 `body.auth-page` lock. Form labels paint `rgb(90,84,112)` on the white card-body — 7.15:1, AA-clearing (was 3.59:1 sub-AA via Bootstrap `--text-muted` resolution). Scope chosen narrow per cluster-routing matrix: the site-wide `.text-muted` retire is already routed cross-phase to S6.1 from S3.2.1 + S4.2.2; this is the in-surface application for the WC game scope. 25 Layer A regression tests under `tests/test_design_p4_s4_3_1.py`; full pytest green (591 passed, +25 vs S4.2.2's 566). Live Playwright computed-style verification at desktop 1470 + mobile 375 (both surfaces): rules.html `<p>` direct-child color `rgb(243,239,230)` bone on navy ≈ 9.52:1 ✓; `<h2.wc-section-heading>` Teko 24px weight 600 bone ✓; `.wc-subsection-heading` Newsreader 17.6px weight 600 ✓; rules-table chip color `rgb(28,23,48)` on `rgba(58,29,114,.07)` ✓; mobile `.tier-mobile-card-name` `rgb(28,23,48)` Teko 17.6px 500 ✓; `.tier-mobile-card-picks` `rgb(90,84,112)` 13.6px ✓; `.tier-teams-list` `rgb(90,84,112)` 13.6px ≈ 6.06:1 on lavender ✓; `.wc-champion-row > td` bg `rgba(58,29,114,.05)` font-weight 700 ✓; join.html eyebrow + H1 `Sign the ledger.` ✓; form-label `rgb(90,84,112)` ≈ 7.15:1 on white card ✓; form-text same ✓; `.join-rules-link` rgb(90,84,112) 16px 195×44 focus outline `rgb(242,211,107) solid 2px` 2px offset ✓; heading outline join H1 → H2 (no skip) ✓; rules H1 → H2(×7) → H3(×2) (no skip) ✓; no inline `style="font-family:'Teko'"` declarations remain in either template (grep). Routed forward (3 items in §0.4): `[S4.3.1 cross-cluster] → S4.5` × 2 (mobile tier-meta 13.6px below 16px body-text floor cluster-altitude decision; rules-page TOC / jump-to-section anchors for long-form reference); `[S4.3.1 cross-phase] → S6.1` × 1 (residual `<small class="text-muted">` on rules.html desktop tier-team-list cell — bundles with the cross-phase `.text-muted` site-wide retire already on S6.1's plate from S3.2.1). Screenshots under `.impeccable-review/S4.3.1/{before,after}/{join,rules}-{desktop,mobile}.png`. Surface CONVERGED.
- [x] **S4.4** — groups (converged: 2026-05-11, S4.4.1)
  - [x] S4.4.1 (commit: 93326ce) — heur 24→30/40 (Δ +6), audit 13→18/20 (Δ +5), anti-pat hard hits 3→0. Gate: **PASS** path (b) baseline+6 floor (30 exactly).
  - [ ] S4.4.N — N/A (converged at S4.4.1).
- [x] **S4.5** — cross-cluster pre-live polish (commit: 0e03f38, plan-backfill: 1824ed5) — 5 PI triage outcomes per §1.5c (3 fix + 1 re-route + 1 decided-no-op + DESIGN.md route). Premise verification per §1.5c calibration: grep across `team_detail.html`, `player_detail.html`, `stats.html`, `picks.html`, `rules.html`, `_home_pre.html`, `groups.html`, `schedule.html` before each fix. **PI-1 (FIX)** — `[S4.2.1 cross-cluster]` Base · Multiplier · Points derivation column trio collapsed to Multiplier · Points outer + accordion-only Base reveal. Cross-surface premise confirmed on `picks.html` lines 54-56 + `player_detail.html` lines 61-63; refuted on `team_detail.html` (S2.3.1 already escaped to inline derivation prose under one dominant Scored numeral per the hero-metric-adjacency ban). Edits: shared `_pick_row.html` drops outer Base td + colspan 5 → 4; `picks.html` + `player_detail.html` table headers drop `<th>Base</th>` + caption strings; `player_detail.html` tfoot drops orphaned base-sum cell + namespace var. The accordion's existing "Total base X × multiplier Y = multiplied Z" summary becomes the canonical Base disclosure — no new copy. Live-probed at 1470: both surfaces 4 headers (Team/Tier/Multiplier/Points), accordion colspans "4", "Total base 8.0 × 1.0 = 8.0 multiplied" still discloses Base on expand. **PI-2 (RE-ROUTE → S6.1)** — `[S4.2.1 cross-cluster]` `.tier-badge` vs `.wc-multiplier-chip` vocabulary primitive. Original premise "wider than picks alone — team_detail, player_detail, stats" REFUTED by session-time grep: `tier-badge` absent from those three surfaces (they all use only `wc-tier-dot`). Actual remaining scope is `rules.html` (×5, as numeric "T1/T2/..." text companion to `wc-tier-dot`) + `_home_pre.html:42` (ballot `roster-tier-label`); the three primitives play distinct roles. Re-routed as DESIGN.md §6 doc PI alongside S4.4.1's Tribune-voiced H1 §3 pass. **PI-3 (FIX)** — `[S4.3.1 cross-cluster]` rules-page navigation accelerator. Added `<nav class="wc-rules-index" aria-label="Jump to section">` pill rail above content with 7 anchor pills mapping to 7 H2 sections via new ids (`rules-overview`, `rules-tiers`, `rules-group-stage`, `rules-knockout`, `rules-points-matrix`, `rules-tiebreaker`, `rules-edge-cases`). Sibling primitive to `.wc-group-index` (S4.4.1 PI-3) + `.schedule-jump-today` (S2.6 PI-4); same 44px tap-target floor, same Teko caps, same canonical gold-light `:focus-visible` ring (live-probed `outline: rgb(242, 211, 107) solid 2px; outline-offset: 2px`). **PI-4 (FIX)** — `[S4.4.1 cross-cluster]` ultra-wide pill-rail stretch. `@media (min-width: 1200px) { .wc-group-index, .wc-rules-index { max-width: 720px; } }` engages exactly at xl: live-probed 1199 → `max-width: none`; 1200 → `max-width: 720px` clamps cleanly; 1470 → rail rect = 720px. Single cap covers both rails so future in-page nav rails inherit the constraint. **PI-5 (DECIDED NO-OP + DESIGN.md route)** — `[S4.3.1 cross-cluster]` mobile <16px caption-tier typography. Cross-cluster premise confirmed (`.tier-mobile-card-picks` + `.tier-teams-list` at 13.6px on rules.html, `.player-pick-card .pick-team small` 12px + `.pick-points small` 11.2px on picks.html, all caption/metadata under a dominant Teko read-target on the same row). Bumping all to 16px would expand mobile vertical rhythm and let captions compete with primary read-targets — wrong fix. The pattern is a deliberate, repeated cross-cluster decision; route DESIGN.md §3 dispensation note ("≥16px applies to body text and primary read-targets; explicit caption/metadata classes may step down to ≥0.75rem (12px) when the primary read-target on the same row carries the dominant hierarchy") to S6.1 alongside the S4.4.1 Tribune-voiced H1 §3 pass. 13 Layer A regression tests under `tests/test_design_p4_s4_5.py`; full pytest green (624 passed, +13 S4.5 + 2 S4.3.1 adapted for the optional `id="..."` attr on the H2 outline). Layer B Playwright/Chrome MCP verification at 1470 + 1200 + 1199 + 500 viewports on picks / player_detail / rules / groups (touched surfaces + adjacent cluster surfaces per §1.5c verification bar). Layer C re-runs skipped per §1.5c default. Screenshots under `.impeccable-review/S4.5/{groups,rules,picks,player_detail}-{desktop-1470,mobile-narrow}.png`. §0.4 amended: 3 routed items annotated `CLOSED in S4.5` (PI-1 Base column trio, PI-3 rules nav accelerator, PI-4 pill-rail xl cap); 2 cross-cluster items re-routed forward to S6.1 (PI-2 tier vocabulary primitive doc + PI-5 mobile caption-tier §3 dispensation doc). 0 routed cross-cluster items remain unaddressed in S4.5 docket.
- [x] **PR P4** opened: `#15`

### Phase 5 — Post-live state cluster
- [ ] **S5.1** — `_home_post` (converged: ___)
  - [x] S5.1.1 (commit: 302abe6). Gate: not converged — first iteration; 3 PIs landed (PI-1 hero-metric-adjacency collapse, PI-2 Tribune retrospection, PI-3 eyebrow disambiguation), 4 backlog items routed (S5.1.2 in-surface tap targets, S5.3 cross-cluster numeral contrast + quicklink contrast, S6.1 cross-phase eyebrow). 9 Layer A locks under `tests/test_design_p5_s5_1_1.py` + Layer B Playwright probes confirm rendered values; 635 tests passing (was 626, +9).
  - [x] S5.1.2 (commit: 6815238). Gate: gates 1-3 PASS (0 P0, 0 unrouted P1 — last in-surface backlog item CLOSED, cross-cluster routed to S5.3, cross-phase routed to S6.1; 0 anti-pat hits on `_home_post.html` partial via `npx impeccable --json --fast`). Gate (4) score-gate unverified — no Layer C re-critique this iteration (single-PI a11y fix with no aesthetic shape change; rationale captured in commit). PI-1 closed: class-scoped `.post-table-link` lifts Podium + Roster anchors to 44×44 mobile tap floor via `display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 0.25rem 0;`. Layer B sweep: 12/12 post-state anchors clear 44×44 at 375 (pre-fix min 33×15); United States row wraps to 81px tall, confirming inline-flex preserves multi-line over the rejected `inline-block + line-height: 44px` candidate. 6 Layer A locks under `tests/test_design_p5_s5_1_2.py`; `test_pi1_no_broadcast_table_anchor_rule` specifically guards the class-scoped choice from a future "tidy this up" pass promoting to broadcast. 641 tests passing (was 635, +6).
  - [ ] S5.1.N (commit: ____). Gate: ____.
- [x] **S5.2** — post-state component partials (converged: 2026-05-12 at S5.2.1)
  - [x] S5.2.1 (commit: dc39bfe). Gate: gates 1-4 PASS (0 P0, 0 in-surface P1 unrouted [3 cross-phase routed to S6.1], 0 anti-pat hits on the 3 in-scope partials per detector + sub-agent inspection, heuristics 33/40 clears gate (a) ≥32/40 floor). 3 PIs closed: PI-1 gradient text retire on `.home-shell .champion-name` (`background-clip: text` + metal-gold → solid `var(--gold-light)`, mirrors `.home-metal-text` precedent at `style.css:461`); PI-2 `_commish_note.html` body branches on `state` (closes pre-state "Tribute window opens until June 11" bleed into live + post; per-state Tribune voice for each branch, byline persists); PI-3 champion eyebrow `◈ 2026 FIFA World Cup Champions ◈` → `◈ Final Decree ◈` (retires H1 + name restatement, mirrors pre-state decree-stamp Council voice). Plan deviation per §1.8: S5.2 inventoried 4 partials, but `_recent_results.html` is live-only (`_home_live.html:72`) — actual S5.2 scope resolved to 3 partials. `_dispatches.html` ships as a commented-out scaffold (no anti-pattern surface). 11 Layer A locks in `tests/test_design_p5_s5_2_1.py`; 652 tests passing (was 641, +11). Layer C critique re-run (sub-agent with §1.2 fingerprint proof) confirmed score and gate state.
  - [x] S5.2.N (N/A — converged at S5.2.1).
- [x] **S5.3** — cross-cluster post-live polish (commit: aa86691). Step 0: 2 routed items (Item 1 `.wc-numeral` bone-on-white in `.card.wc-card .table`, Item 2 `.btn-outline-secondary` quicklinks 3.04:1) — Item 1 taken in S5.3 as §1.8 deviation despite cross-phase scope (one selector-scoped CSS rule; splitting overhead > value). Step 1: 2 cross-cluster patterns surfaced spanning platform `_champion_banner.html` and WC `_home_post.html` (champion eyebrow Tribune voice; Tribune retrospection inversion). 4 PIs closed (Item 1 via PI-1 selector-scope on `:not(.player-picks-desktop)`; Item 2 via PI-2 bone-on-navy lift with hover/focus inversion; PI-3 WC banner eyebrow `World Cup Winner` → `Final Decree`; PI-4 platform retrospect "The Club records the night." Newsreader italic .82 bone). Layer B Playwright probe confirms all 4 at runtime. 15 Layer A locks in `tests/test_design_p5_s5_3.py`; 2 S5.1.1 forward-pointed (the prior "World Cup Winner" assertions updated to "Final Decree" with §1.8 link). 667 tests passing (was 641, +26 — 15 new + 11 from other suites collecting differently between sessions).
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
