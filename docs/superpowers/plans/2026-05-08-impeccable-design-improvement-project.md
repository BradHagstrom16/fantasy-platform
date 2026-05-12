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
- **[S0.3] → S6.1 CLOSED in S6.1.3 (Group I PI-2)** Navbar trophy CTA worst-stop AA. `--metal-gold-flat`'s terminal stop retuned from `#8A6A1A` → `#A88420` in `tokens.css`; chamber-purple text now clears 5.19:1 at the bottom-right pixel-corner (was 3.6:1). `--gold-dark` token unchanged. DESIGN.md §2 ratifies the new diagonal-gradient dark anchor with worst-corner rationale.
- **[S1.1] → S6.1 CLOSED in S6.1.3 (Group J PI-1)** Tiebreaker cell `'none'` literal replaced with voiced `'No guess'` fallback (`leaderboard.html:96`). Editorial register restored.
- **[S1.1] → S6.1 CLOSED in S6.1.3 (Group J PI-1)** Move column header carries `title="Change since yesterday's snapshot"` (`leaderboard.html:57`). Analyst progressive disclosure landed without bloating the visible chrome.
- **[S1.1] → S6.1 CLOSED in S6.1.3 (Group J PI-1)** Gold-divider thread between Your Position tribune and standings cards. Adjacent-sibling rule `.your-standing-tribune + .card.wc-card, .your-standing-tribune + .card.wc-card + .d-md-none { border-top: 2px solid var(--gold) !important; }` lands the visual thread on both desktop card and mobile cards wrapper. `!important` required to defeat Bootstrap `.border-0` on the desktop card (established codebase pattern for fighting Bootstrap utility specificity). DESIGN.md §6 Do canonical major-section separator.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Home-live right column starved on desktop — ~700px void below the 4-line Commish note.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Section "more" links (`.sec-head .more`) read at ~28px tall, below the 44×44 floor.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Dossier-stamp `◈ Classified · CCC ◈` register-shift.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** "Also Today" eyebrow promised a temporal anchor the rows never delivered.
- **[S2.1.1 in-surface] CLOSED in S2.1.2** Mobile dossier-stamp positioning at `position: absolute` overlapped rank-meta on narrow viewports.
- **[S2.1.1 in-surface] [S2.1.2 in-surface] DEFERRED to S2.1.3** Sparkline read-only in dossier card (`_dossier_card.html:33-99`) — no per-day rank reveal on hover/tap. Inherited from S2.1.1; not landed in S2.1.2 because the iteration's 3-5 cap absorbed the four higher-impact backlog items first. Receiving session: **S2.1.3** (delight pass; `$impeccable delight`). The convergence gate passed without it (heur 32/40 ≥ floor) so this is a Want, not a Need.
- **[S2.1.2 in-surface]** Sparkline lacks `aria-label` / `<title>` describing the trend; `rank-mvmt` carets are decorative-icon-with-hidden-text but not marked `aria-hidden="true"`. Surfaced by the S2.1.2 re-critique as soft P1s; both fit cleanly into the S2.1.3 a11y/delight pass alongside the per-day reveal. Receiving session: **S2.1.3**.
- **[S2.1.1 cross-cluster] [S2.6 routed] → S6.1 CLOSED in S6.1.4 (Group H PI-1)** Repeating gradient-card silhouette across 7 home components. Cross-state inventory at session-time shows the seven gradient-cards already inhabit DESIGN.md §5's two recipes (Ceremonial, Informational) plus the `.ballot-card` third register that S4.1.2 already ratified. Two single-instance hero silhouettes layered on top — `.dossier` (live-state standing hero; Ceremonial recipe with extended `purple-800 → purple-950` gradient terminus) and `.commish-note-body` (Informational with `border-top: 2px solid var(--gold)` §6 Do major-section separator at card level). DESIGN.md §5 amended to ratify both as documented single-instance variants (do-not-duplicate language) and to fold `.commish-note-body` into the Informational bullet alongside `.match-card` + `.cta-card--view`. CSS consolidates: (a) `.commish-note-body` border-radius `8px → 12px` so it lands on the canonical Informational radius, (b) `.match-card` + `.cta-card--view` border `rgba(255,255,255,.08)` → `rgba(243,239,230,.08)` (bone-8) so the Informational recipe's border color is one tinted-neutral value across all three members (impeccable "no pure white" / tinted-neutral law). Adjacent test-contract harden in `tests/test_design_p4_s4_1_2.py::test_pi3_cta_card_view_holds_informational_recipe` updates the legacy white-8 assertion to the new canonical bone-8 value.
- **[S2.1.1 cross-cluster] [S2.6 routed] → S6.1 CLOSED in S6.1.4 (Group H PI-2, decided already-closed)** Leaderboard rolls non-interactive `<div>` premise. Session-time grep refuted the original premise: `_home_live.html` top-5 preview rolls already wrap each row's display name in `<a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}">` (line ~138 of the current file; the original `_home_live.html:46` reference was incidentally closed by intervening S2.x / S5.x surface work). `leaderboard.html` desktop + mobile-cards surface both already resolve `row_href = url_for('worldcup.picks') if is_me else url_for('worldcup.player_detail', enrollment_id=e.id)` — self-row lands on picks, other rows on `player_detail`. Layer B browser probe confirmed 6 desktop + 6 mobile cards, every row has an anchor. No code change needed; Layer A locks the anchor coverage so a future refactor cannot silently regress it.
- **[S2.1.1 deferred-data]** "Test1 / Test2 / Test3" tagline duplication (`_home_live.html:54` via `_tagline_for()` in `home_context.py:46-69`). Current finite-string set returns the same line for ranks #2 and #3. Production rotates per actual user; only visible with N real users in the standings. Revisit when production rotation is observed.
- **[S2.2.1 cross-cluster] CLOSED in S2.6** No jump-to-today affordance from above-the-fold on `/worldcup/schedule`.
- **[S2.2.1 cross-cluster] CLOSED in S2.6** Stage-count `<small>` in the schedule section headings used Bootstrap `.text-muted` (`#6c757d`) instead of the CCC tinted `--text-secondary` (`#5A5470`).
- **[S2.2.1 ship-as-is]** Group-letter tag at upper-right of `.match-result-card` reads as a bare letter ("J", "I") to sighted users without prior context (the H1 "Group Stage" is far above when scrolled deep). `aria-label="Group X"` covers SR users; sighted users can still infer from the surrounding section. Lower priority than the Today affordance and not load-bearing for picks; defer until a future critique re-flags it.
- **[S2.2.1 cross-phase] → S6.1 CLOSED in S6.1.2 (Group F PI-2)** `.schedule-day-date` renders as `<time datetime="{{ day.day_iso }}">` when `day_iso` is truthy; TBD bucket falls back to a plain `<span>` so empty `datetime=""` never lands as invalid HTML. The cross-page premise (home / team_detail recent-results / leaderboard snapshot dates) was verified at session-time — those surfaces print dates inside strong sentence context where SR users already have the temporal anchor; the canonical instance flagged on schedule is closed and the broader migration is **decided ship-as-is** until a future audit shows actual SR friction on the remaining sites.
- **[S2.3.1 in-surface]** Owned-state celebration delta — full PI-3 ask (rank-among-picks + personalized voice in path heading, e.g., "Your roster's GER ceiling is 107.0, 4th-best in the Club"). The S2.3.1 atomic-edit pairing closed the eyebrow + gradient-variant minimum; the comparator requires a new `pick_ceiling_rank` route-level helper that joins `WorldCupPick` + `compute_path_to_crown` per enrollment, season-scoped via `WorldCupEnrollment.season_year` per the CLAUDE.md "WorldCupRankSnapshot aggregates must be season-scoped" pattern. Receiving session: **S2.3.2** (hero/path-section copy + new route data).
- **[S2.3.1 in-surface]** Projected-ceiling bare numeral. `team_detail.html:159` renders 749.0 / 107.0 with no group anchor — casual users have no calibration, analysts get no breakdown. Add a comparator chip (vs. median ceiling, vs. user's own picks) and progressive-disclosure detail (group-stage wins + R32 + R16 + QF + SF + Final base × multiplier). Same `pick_ceiling_rank` route data unlocks both. Receiving session: **S2.3.2**.
- **[S2.3.1 in-surface]** Pre-tournament state shell. `deadline_passed=False` + zero completed matches: hero shows `0.0 Tournament points`, ownership ribbon hidden, Match log of three TBDs, Path of one current + 5 future. *No copy* anywhere on the page says "the tournament hasn't started yet" — the page reads as broken rather than pre-roll. Mirrors the `core/main/home_context.build_home_context` four-state dispatcher pattern but team_detail has no equivalent state-shell. Receiving session: **S2.3.2** (route adds `state` flag; template branches on it).
- **[S2.3.1 cross-cluster] [S2.6 routed] CLOSED in S6.1.1 (Group A PI-1)** Eyebrow primitive saturation. DESIGN.md §3 + §5.5 ratification landed: the eyebrow is two co-existing primitives, not one — `.admin-eyebrow` (gold on bone, admin masthead) and `.wc-eyebrow` (bone-mute default with `.wc-eyebrow-red` and `.wc-eyebrow-gold` tonal variants, auto-lifts on `.card.wc-card` via scope rule). The S2.3.1 "9-14× per page" saturation reads as the tonal-variant primitive doing its job (red for danger / current, gold for ceremonial, bone-mute for context), not as primitive overload. `.wc-meta-label` stays as a sibling primitive for in-row labels; not folded into eyebrow.
- **[S2.3.1 ship-as-is]** Bottom-of-page back-link. `team_detail.html:44` carries the only "Back to Board" affordance; on a long mobile scroll the user must scroll back up to navigate out. Lower priority than the comparator + state-shell work; defer until a future critique re-flags it.
- **[S2.3.1 ship-as-is]** Three "1.0" tokens stacked in a 90px band on tier-1 mobile (multiplier == 1.0). Visual coincidence on tier-1 teams (no analyst tension to surface); copy could elide the "× Multiplier 1.0" prose when multiplier == 1, but the canonical Base × Multiplier reading is consistent and honest. Defer until a future critique re-flags it (likely S2.4 multiplier-explanation revisit).
- **[S2.4.1 in-surface]** T1 amber tier badge at `static/css/style.css:3417` (`.wc-tb-1 { background: var(--wc-tier1); }` = `#D97706`) renders white-on-amber at **3.19:1** at 10.88px bold — sub-AA (4.5:1 floor for small bold text). The other four `.wc-tb-N` variants pass AA (4.99–5.62:1). The cleanest fix is a shared tinted-bg + dark-text pattern across all five badges (parallel to the existing `.wc-still-in` pattern: `background: rgba(token,.15); color: dark-token; border: 1px solid rgba(token,.4)`); the alternative is a token retune of `--wc-tier1` (DESIGN.md spec change, also affects chart palette + pick-bar fills). S2.4.1 deferred because either fix is bigger than a same-iteration P2 — token retune touches DESIGN.md tokens, shared variant touches all five badge classes + visual rhythm across the surface. Receiving session: **S2.4.2** (in-surface, dedicated badge variant work).
- **[S2.4.1 in-surface]** Phase-aware editorial copy on stats masthead. The Board's masthead derivation prose ("X leads the field with Y pts. Z oaths sealed across N nations still standing.") is currently hard-coded for live-state. Pre-deadline ("Vault opens Jun 11"), post-tournament ("Champion sealed Jul 19"), and "no completed matches yet" need branched copy via `current_phase` + `kpis.top_country_score > 0`. Routes-side plumbing minimal (already pass `current_phase`); just template-side `{% if %}/{% elif %}` branches on the prose line. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** No "my picks only" filter affordance on the Field tab's Popularity vs. Score bubble chart. Analyst persona red flag — they want to isolate their own roster against the field. Bubble chart datasets are tier-grouped (5 datasets); a sixth filter dataset that toggles "MY_PICKS only" would land cleanly. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** Carrying the Field + Dead Weight stack vertically inside the right rail at desktop (`.col-xl-4 .d-flex.flex-column`). Adjacent comparison is the analyst's primary use of these two lists; vertical stacking forces them to scroll between. Side-by-side on `>= xl` would close it. Receiving session: **S2.4.2**.
- **[S2.4.1 in-surface]** Tier 2 Pairs absence on the By Tier tab. `get_tier_combos()` deliberately excludes tier 2 (only 1 T2 pick per player → no pairs). The Tier Pairs section silently drops T2 with no explanatory line; an analyst reads it as a data bug. A one-sentence inline note ("Tier 2 has no pairs — only one T2 pick allowed.") would defuse the ambiguity. Receiving session: **S2.4.2**.
- **[S2.4.1 cross-cluster] [S2.6 routed]** Inline-style Teko declarations duplicated ~25× across `stats.html` JS render functions (`font-family:'Teko',sans-serif;font-size:.7rem;...`). Pattern likely shared with other JS-rendered surfaces (home _home_live impact rows, leaderboard mobile cards). Extract to a `.wc-microcaption` utility set after auditing cross-surface usage. **Re-routed by S2.6:** the S2.6 grep surfaced **0** inline Teko declarations in `_home_live.html` and `leaderboard.html` — the only verified additional inline-Teko surfaces are P4 pre-live templates (`picks.html`, `rules.html`, `join.html`, 11+ instances combined). Extracting a `.wc-microcaption` utility now would consolidate stats.html alone, then need a second migration pass when the P4 surfaces are touched. Re-routed receiving session: **S4.5** (pre-live cross-cluster polish, after picks/rules/join converge), so the extraction lands once and matches the actual cross-surface usage.
- **[S2.4.1 cross-cluster] CLOSED in S2.6 (decided no-op)** `.wc-stat-card` carries both `box-shadow: var(--shadow-sm)` AND `border: 1px solid var(--border)` — double elevation.
- **[S2.4.1 cross-phase] → S6.1 CLOSED in S6.1.2 (Group F PI-2)** `stats.html` progress wrap now carries `role="list"` + `aria-label="Tournament progress by stage"`; each segment renders as `<div role="listitem" aria-label="{phase}, {status}">` with the visible ✓/← glyphs marked `aria-hidden="true"`. Status vocabulary locked to the canonical "completed / current / upcoming" trio. The cross-surface premise (home progress widgets, pre-state countdown, post-state recap progress bar) was verified at session-time: no other surface currently renders a markup-as-icon progress pattern — the canonical instance is the only one. Ship-as-is for any future progress widget that follows the same primitive shape.
- **[S2.4.1 ship-as-is]** Phase chip in stats hero shows "Pre-Tournament" even with `WC_FAKE_NOW` set to mid-group-stage — backend artifact (no completed matches in dev DB → `_derive_tournament_phase()` returns `pre_tournament`). Won't surface in production where match data is live. Won't be re-flagged.
- **[S2.4.1 ship-as-is]** `.wc-still-in` "Active" green chip + `.wc-tb` orange tier badge of equal size and weight in Top Scorers row split visual attention. Lower priority than the comparator + state-shell work; defer until a future critique re-flags it.
- **[S2.5.1 in-surface]** Rivalry comparison strip (you vs them). The S2.5.1 hero re-shape closed the *voice* dimension of rivalry framing (Newsreader derivation prose carries "Leads the table. 117.0 ahead of next." / "Trails leader by X, Y ahead of next."), but the structural you-vs-them comparison strip below the eyebrow line — `<viewer> trails <target> by <delta> · <N> shared picks · their edge: <team> (+<pts>)` — needs a new route-level helper `compute_comparison(viewer_enrollment, target_enrollment) -> {viewer_total, target_total, delta, shared_picks, their_advantage, your_advantage}` joined per `WorldCupPick` + season-scoped via `WorldCupEnrollment.season_year`. Suppress the strip when `viewer == target` or when viewer is logged out. Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** "Roster sealed" pre-deadline empty-state re-shape (`player_detail.html:124-136`). Current implementation is a Bootstrap icon-stack: 2.5rem bi-lock-fill at opacity .7 + `Roster sealed` eyebrow + "Picks are hidden" h5 + 2-line muted paragraph with deadline_ct. The S2.5.1 admin-session probes bypassed `picks_visible = deadline_passed or is_owner or is_admin`, so this branch was not visually rehearsed; the icon-on-navy at .7 opacity will read marginal, and the empty-state apologizes rather than rewards participation (PRODUCT.md Design Principle "Empty states reward participation"). Re-shape options: editorial "Sealed envelope" / "Locked in the vault until kickoff" frame, target avatar + name as dominant element, countdown when deadline within 7 days, replace low-opacity icon with Teko "SEALED" eyebrow or "9 PICKS LOCKED" numeric chip. Requires an un-priv viewer probe (logout + visit another player's `/worldcup/leaderboard/<id>` pre-deadline). Receiving session: **S2.5.2**.
- **[S2.5.1 in-surface]** Above-fold density / wrapper reduction. The picks table currently sits at y≈481 on a 1470×900 viewport (probed) — the `.page-hero.wc-hero-grad` consumes ~280px, then `.container > .row.justify-content-center > .col-lg-8 > .card.wc-card.wc-card-flush > .card-body.p-0 > .table-responsive > <table>` adds 6 layers of wrapper before the table renders. Most of the 9 picks sit below the fold. Targeted fix: scope `.page-hero` padding compaction to player_detail (e.g., page-specific class on the hero or a `.page-hero.is-comparison` modifier) without touching the platform default; collapse `row > col-lg-8` to a `.container-md` or `max-width: 880px` inner block. The platform-global `.page-hero` padding is OUT of scope for this surface — never edit it from a per-surface iteration. Receiving session: **S2.5.2**.
- **[S2.5.1 cross-cluster] CLOSED in S2.6** Bootstrap-on-`.card.wc-card` contrast leak is a cluster-wide latent risk.
- **[S3.1.1 cross-cluster] CLOSED in S3.4** Orphan `.navbar-brand { color: var(--platform-accent) !important; }` rule at `static/css/style.css:~4019` paints the brand wordmark gold via lower-specificity `!important`, overriding `.navbar.navbar-dark .navbar-brand`'s spec-correct `var(--bone)`.
- **[S3.1.1 cross-cluster] CLOSED in S3.4** No explicit `:focus-visible` styling on `.navbar .nav-link` or `.subnav-pill` — keyboard focus inherited browser-default outlines, inconsistent across browsers and easy to miss on dark game-tinted subnav substrates.
- **[S3.1.1 cross-cluster] CLOSED in S3.4** `.game-subnav` `aria-label` missing on the container — on mobile the `.subnav-game-label` text is `display: none` via `d-none d-sm-inline-flex`, so screen-reader users on mobile lost the game-context cue.
- **[S3.1.1 ship-as-is]** `.subnav-game-label` `border-right: 1px solid rgba(255,255,255,.14)` is a one-off vertical-rule pattern in chrome (not codified in DESIGN.md §5). The pattern works (correctly hides when `.subnav-game-label` is `display: none` on mobile) and is too small to fold into a cluster polish session. Document as "label-to-pills separator" if S3.4 reaches it; otherwise leave alone.
- **[S3.1.1 ship-as-is]** Dropdown toggle (`.dropdown-toggle` user menu) has no `aria-label` and relies on the avatar emoji + display name for its accessible name. Screen readers will announce "soccer ball, Brad" rather than "User menu, Brad". Visible text carries semantic meaning so this passes the bar; ship-as-is. Re-evaluate only if a future SR audit re-flags it.
- **[S3.1.1 ship-as-is]** Flash region passes any Flask flash category as a Bootstrap class (`alert-{{ category }}` with a `danger`-for-`error` swap). Non-standard categories produce non-styled alerts (silent). Chrome-level defensive shaping is overreach; route to S3.4 only if a CR comment surfaces a real flashed category that won't paint.
- **[S3.2.1 in-surface]** Avatar picker on `/profile` is the wrong primitive. Nav-tabs + 5-button category strip (probed 57-108×39, fails 44 floor) + 19+ button emoji grid (probed 40×44, fails width by 4px) + inline `<style>` block (template.html:114-169) hard-coding Bootstrap-neutral hexes (`#dee2e6`, `#6c757d`) outside the CCC token system. Shape question, not a polish fix: candidates include (a) drop categories entirely with a single scrollable grid + filter, (b) convert tabs to a `.game-subnav`-style pill bar with proper 44 floor, (c) move avatar selection to a dedicated `/profile/avatar` route with a richer picker. The inline `<style>` block needs to relocate to `static/css/style.css` alongside the shape decision so token references can replace literal hexes (`#dee2e6` → `var(--border)`, `#C9A227` → `var(--gold)`). Receiving session: **S3.2.2** (in-surface, dedicated shape brief + relocation pass).
- **[S3.2.1 in-surface]** N1 link-row resting contrast near-miss. `body.auth-page .auth-link-row a` paints `--gold-dark` (#8A6A1A) on `--bone` (#F3EFE6) at 4.40:1 — 0.1 short of the WCAG AA-normal 4.5:1 floor. PI-1's lift from 2.11 (the pre-S3.2.1 `--gold` resting state) is enormous, and the hover/`:focus-visible` state computes to 14.48:1 (compliant), but the static resting state should clear AA on its own. Options for S3.2.2: (a) darken `--gold-dark` by one luminance notch (DESIGN.md token spec change — out of scope for a per-surface iteration), (b) bump link font-size + weight to qualify for AA-large 3:1 bar (Teko 700 at 18.66px+ would clear), (c) accept the near-miss with documented rationale citing the compliant hover state. Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Decorative `<i class="bi bi-key-fill text-gold">` 2.5rem icon banner above the `/change-password` H1 (template.html:11). Trophy Rule adjacency — `.text-gold` resolves to `var(--platform-accent) !important` (#C9A227, the trophy color), used decoratively on a non-CTA surface. DESIGN.md §2 "Trophy Rule" reserves the metallic gold gradient for primary CTAs and active navbar buttons; a flat-gold icon header sits in the gray zone the rule warns about. Options: drop `.text-gold` to render in the parent text color, swap to `--gold-dark` (~5.07:1 on bone, AA-passing), or remove the decorative icon entirely (the H1 + subtitle carry enough semantic weight). Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Required-asterisk `<span class="text-danger">*</span>` on register.html + reset_password.html uses Bootstrap's `#DC3545`, not the CCC `--danger` token (#C0392B per DESIGN.md §2). Token consistency miss; same scope as the S3.2.2 freebie refactor pass. Receiving session: **S3.2.2**.
- **[S3.2.1 in-surface]** Register password + confirm fields sit `.col-6` side-by-side at every viewport. At 375 the "6+ characters" placeholder truncates to "6+ charac..." (visible in `.impeccable-review/S3.2.1/before/register-mobile.png`). Stack at `<540px` via a `.row.g-3.mb-4 { @media (max-width: 539.98px) { > .col-6 { width: 100%; } } }` or a Bootstrap responsive `col-sm-6` swap. Receiving session: **S3.2.2**.
- **[S3.2.1 cross-cluster] CLOSED in S3.4** Split-panel vs `.auth-wrapper` layout split between marketing-context auth (login, register, forgot, reset) and logged-in utility auth (change-password, profile) was undocumented.
- **[S3.2.1 cross-phase] [S6.1 routed] CLOSED in S6.1.1 (Group B PI-2)** Bootstrap `.text-muted` site-wide retire. Single `:root { --bs-secondary-color: var(--text-secondary); }` redirect closes the bone-canvas surface family — Bootstrap 5.3.3 resolves `.text-muted`'s color via the variable, so flipping it at the cascade root propagates everywhere without specificity wars or `!important`. Dark substrates were already covered by pre-existing `!important` rules (`.card.wc-card .text-muted` at style.css:6728 + `.page-hero.wc-hero-grad .hero-subhead.text-muted` at :6670) that keep winning the cascade either way.
- **[S3.2.1 ship-as-is]** Login mobile shows two `.auth-link-row` rows ("LOST YOUR KEY?" + "Not on the rolls yet? JOIN THE CLUB") at similar Teko-600-uppercase weight. Pre-S3.2.1 the forgot-password link was visually lighter than the create-account row (italic + smaller); now both read as siblings. Functional 44×44 lift more than offsets the small hierarchy loss; if a future session wants to differentiate, a `.auth-link-row--secondary` variant could land without re-breaking the touch floor. No receiving session unless a critique re-flags it.
- **[S3.2.1 ship-as-is]** Change-password masthead reads functional ("CHANGE PASSWORD") next to a Tribune-voiced subtitle ("Forge a new key for the chamber"). Login does the same ("WELCOME BACK" + "Step back into the chamber") and it works because the H1 is universal English. On change-password the H1 sits closer to utility-language. Reasonable people could read the contrast as deliberate (utility action, club voice); not load-bearing enough to fix. Optional polish for S3.4 if voice-tightening lands inside that session.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** `_home_out.html:75-88` 3-up `col-md-4` identical-card-grid composition.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** Missing `<h2>` between `_home_out.html` page `<h1>` and registry grid.
- **[S3.3.1 cross-cluster] CLOSED in S4.1.1** `_home_out.html:68` "Sign in" link 44×15 tap-target.

### Routed forward from S4.1.1 (in-surface to S4.1.2, cross-phase to S6.1)
- **[S4.1.1 in-surface] → S4.1.2** Pre-state desktop 2-col layout. The `.home-col { max-width: 640px }` floor on `_home_pre.html` produces a phone-shaped column at every viewport — the 1470-wide canvas reads with the masthead floating in a 640-wide well, wasting ~830px of horizontal space. Reshape at md+ to a 7fr/5fr grid: col-A = countdown decree + dossier (left, 7fr); col-B = opening matches + game tiles + commish note + dispatches (right, 5fr). Single column persists below md. Substantial scope (affects 3 dossier variants — `_ballot_card`, `_submit_picks_cta`, `_join_cta_card` — plus opening matches placement + commish/dispatches positioning; the shared `.home-shell` parent risks live-state regression so requires Layer B probe on `_home_live.html` post-fix). Receiving session: **S4.1.2** (in-surface).
- **[S4.1.1 in-surface] → S4.1.2** `.ballot-card` whole-area-link semantic. The entire card is wrapped in `<a href="...?edit=1">`, swallowing the flags ribbon + "Edit any time before the whistle." copy into a single concatenated link for screen readers, and making the flag emojis tap-routes to "edit pick" rather than "show team detail". Restructure into `<section>` (or `<article>`) + an explicit inline `Edit roster ›` action sitting next to "Sealed & delivered." The flags become a non-interactive ribbon. The hover lift (`translateY(-2px)`) moves to the explicit action. Casey (Distracted Mobile) gets a clean affordance; Sam (screen reader) hears the structure instead of one giant link. Receiving session: **S4.1.2**.
- **[S4.1.1 in-surface] → S4.1.2** Three different gold-bordered card recipes within one viewport on pre-state: `.decree` (purple gradient + 30%-gold border + dashed gold internal rule, 14px radius), `.cta-card--seal` (gold-overlay gradient + 35%-gold border, 12px radius), `.match-card` (purple gradient + 8%-bone border, 12px radius). DESIGN.md §5 says "Consistent affordances across the surface"; a returning user can't predict whether a gold-bordered card is tappable, ceremonial, or informational. Fix: define a 2-tier card vocabulary inside `.home-shell` — **Ceremonial** (decree + cta-card--seal consolidated: gold-30% border, dashed gold internal rule, gold-on-purple gradient — used for time-sensitive CTAs) and **Informational** (match-card register: 8%-bone border, purple gradient — used for fixtures + dossier + dispatches). Document the split in DESIGN.md §5 ("Cards" subsection) so the vocabulary survives the migration. Receiving session: **S4.1.2**.
- **[S4.1.1 in-surface] → S4.1.2** Out value-prop strip `.out-prop` ×3 — three identical icon-text rows (gold icon + Teko title + Newsreader sub, stacked between two bone-opacity-8 hairlines). Within-strip identical-grid signal. Differentiate via row-specific texture: row 1 keeps icon-pair; row 2 swaps icon for a tiny inline leaderboard sparkline preview; row 3 swaps for a Commish-wordmark monogram. P3-class; ride along to S4.1.2 to lift Consistency heuristic toward 4. Receiving session: **S4.1.2**.
- **[S4.1.1 cross-phase] → S6.1 CLOSED in S6.1.3 (Group E PI-B)** Flash banner auto-fade. `.alert.alert-success.alert-dismissible` runs a pure-CSS opacity-only animation (`ccc-flash-success-fade` 4.4s) on top of the existing `slideDown` entrance, so success flashes recede after ~4s without competing with the masthead. Layout properties are not animated (impeccable ban). `prefers-reduced-motion` users get the entrance-only path. Errors/warnings stay loud until user-dismissed.

### Routed forward from S4.2.1 (in-surface to S4.2.2, cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Three competing tier-vocabulary primitives on one page: `.tier-badge` (pill, light surface, used in sidebar pick-summary + mobile readonly card), `.wc-multiplier-chip` (dark-surface chip, used in desktop readonly table + tier-card-header), `.wc-tier-dot` (compact circular dot).
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Inline `style="font-size:N.Nrem"` type-scale leakage on `.wc-numeral` spans.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Mobile `.player-pick-card` non-interactive — closed atomically with the tier-vocabulary collapse (PI-1) per §1.5b atomic-edit rule.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.pick-summary` 3px top-stripe (side-stripe-adjacent pattern).
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.wc-team-card.selected::after` Unicode checkmark glyph (markup-as-icon).
- **[S4.2.1 in-surface] CLOSED in S4.2.2** Edit-form heading-order H1 → H3 skip.
- **[S4.2.1 in-surface] CLOSED in S4.2.2** `.wc-multiplier-chip` `var(--wc-white)` token hygiene.
- **[S4.2.1 cross-cluster] CLOSED in S4.5** "Base · Multiplier · Points" derivation-table column trio.
- **[S4.2.1 cross-cluster] → S6.1 CLOSED in S6.1.2 (Group G PI-3)** Tier primitive vocabulary ratified in DESIGN.md §5 as a new "Tier Primitives" subsection. Three non-overlapping primitives, each with a single role: `.wc-tier-dot` = visual mark; `.tier-badge` = numeric text companion; `.wc-multiplier-chip` = multiplier indicator. The doc names exact surfaces (rules.html ×5, `_home_pre.html` ballot label, picks readonly table) so future tier-adjacent UI can look up which primitive applies. Re-routed by S4.5 from §6 ("Don't") to §5 ("Components") since the policy is a positive vocabulary, not a ban.
- **[S4.2.1 cross-phase] → S6.1 CLOSED in S6.1.3 (Group E PI-A)** Read-only picks card-header eyebrow voice collapse. Both desktop and mobile card-headers now carry the invariant `<span class="wc-eyebrow">The Ballot</span>` instead of re-stating the H1 ("Sealed · still amendable" / "The Oath is sealed"). The H1 keeps the state info; the eyebrow becomes a Tribune section anchor. The microcopy ("You can amend your picks until ...") and CTA ("Amend the Oath") stay because each carries a distinct functional load (when + how-to-act). The broader cross-cluster voice-stack pattern (countdown decree, live deadline awareness, fixture statuses) remains ship-as-is until a future audit re-flags it; no other surface carries the exact above-the-fold 4-echo stack S4.2.1 named.

### Routed forward from S4.2.2 (ship-as-is to S4.5 if surfaced, cross-phase to S6.1)
- **[S4.2.2 ship-as-is]** Desktop readonly hero-to-card vertical void. `col-lg-8` centers an 856px picks card on a 1410px container at 1470 viewport with no companion column — ~400px of empty bone between the hero band and the navy card reads as a forgotten dashboard rather than a deliberate editorial column. P2 surfaced by S4.2.2 Layer C critique. Per §1.5b anti-perfectionism note, S4.2.2's gates passed (heur 32/40, 0 P0, 0 unrouted P1, 0 anti-pat) so the surface converged and we don't keep iterating. Two paths if a future session re-opens it: (a) widen to `col-lg-10` (cheap, no new content); (b) add a Tribune-style sidebar — "Roster at a Glance" tier-mix counts + "Strongest pick" callout — needs new route data. Cluster polish S4.5 may sweep this once picks / join / rules / groups converge. `$impeccable layout` is the recommended command. Receiving session: **S4.5 if surfaced** (otherwise ship).
- **[S4.2.2 ship-as-is]** Desktop accordion-toggle 25×24 hit target. P3 surfaced by S4.2.2 Layer C critique. PRODUCT.md 44×44 floor applies mobile-first, and the desktop accordion-toggle sits inside a row affordance where the entire `.pick-team-cell` is the click target; the chevron is decorative emphasis. Below floor though desktop-only and doesn't block keyboard or touch access (the cell + `tab` to the inner toggle button work). `$impeccable polish` could lift `.pick-accordion-toggle { min-width: 44px; min-height: 44px }` if a future session re-opens picks for an unrelated reason. Receiving session: **S4.5 if surfaced** (otherwise ship).
- **[S4.2.2 cross-phase] → S6.1 CLOSED in S6.1.1 (Group A PI-1)** Dark readonly tier-name eyebrow lift. `.card.wc-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` scope rule lifts bone alpha from .55 (~4.11:1) to .85 (~7.1:1 on the rgba(0,17,46,.8) navy substrate). The `:not()` carve-out preserves the red/gold tonal variants so they keep their semantic signal on dark cards.

### Routed forward from S4.4.1 (cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.4.1 cross-cluster] CLOSED in S4.5** Pill-rail ultra-wide stretch.
- **[S4.4.1 cross-phase] → S6.1 CLOSED in S6.1.2 (Group D PI-1)** Tribune-voice H1 pass + DESIGN.md §3 Display primitive ratification. The 8+ surfaces named in the original route reduced to 3 at session-time per the §1.5c cross-cluster premise verification: leaderboard ("The Standings"), stats ("The Field Office"), picks ("The Oath is sealed"), join ("Sign the ledger"), and the 404/500 errors already carried Tribune voice; team_detail / player_detail / profile dispatch via the dynamic-noun H1 dispensation; login / register / change_password / forgot / reset land under the auth-utility dispensation (DESIGN.md §5 Auth Surface Composition). Three remaining surfaces converted: schedule.html "Match Schedule" → "The Match Sheet"; rules.html "Rules &amp; Scoring" → "House Rules" (stray entity gone); groups.html "Group Standings" → "The Group Sheet". DESIGN.md §3 Display bullet now ratifies Tribune voice as the H1 policy with both dispensations named.
- **[S4.4.1 ship-as-is]** `.wc-group-index` rail lacks a visible "Jump to" eyebrow label; sighted users discover the affordance by trying a pill. The `aria-label="Jump to group"` covers screen-reader users; for sighted users the 12 single-letter pills above 12 letter-headed cards are self-explanatory. Adding a label would compete with the state chip's job in the same vertical gap. If a future critique re-flags it, fix is a one-line Teko eyebrow ("Jump to") inside the nav.
- **[S4.4.1 ship-as-is]** `.wc-state-chip--pre .wc-state-chip-dot` paints `--game-accent` (WC red `#BF0A30`) on a purple-tinted chip; the cross-color reads more "warning red" than "scheduled." Acceptable because (a) the chip clears AA, (b) pre-state lifetime is finite (chip swaps to live-red dot post-deadline anyway), (c) the chip is read once per session. If routed forward, swap the pre-state dot to `--gold` (for consistency with the post chip's gold dot) or `--game-primary` (navy = "scheduled").
- **[S4.4.1 ship-as-is]** Tier (1–4) is the analyst's primary hook into a group field; it's exposed on `/stats`, `/picks`, `/team_detail` but absent from team rows on `/worldcup/groups`. Adding it would require resolving the tier-vocabulary collapse decision (`.tier-badge` vs `.wc-multiplier-chip` vs `.wc-tier-dot`) at cluster altitude — already routed to S4.5 per S4.2.1's `[S4.2.1 cross-cluster] → S4.5` item. Don't surface tier on groups.html ahead of the cluster-level ratification; the surface stays casual-default and the analyst path through `/team/<id>` remains the depth target. Will be revisited at S4.5 once the tier-vocabulary canonical primitive is locked in DESIGN.md §6.

### Routed forward from S4.3.1 (cross-cluster to S4.5, cross-phase to S6.1)
- **[S4.3.1 cross-cluster] → S6.1 CLOSED in S6.1.2 (Group G PI-3)** Caption-tier <16px dispensation landed in DESIGN.md §3 Hierarchy Body bullet. The note carries the 12px floor + names the explicit caption classes the dispensation covers (`.tier-mobile-card-picks`, `.tier-teams-list`, `.player-pick-card .pick-team small`, `.player-pick-card .pick-points small`, `.wc-microcaption`) + connects the dispensation to "primary read-target on the same row carries the dominant hierarchy" so it reads as a paired-row policy, not an across-the-board escape hatch. The S4.5 decided-no-op is now a written policy a future audit can look up.
- **[S4.3.1 cross-cluster] CLOSED in S4.5** Rules-page navigation accelerators.
- **[S4.3.1 cross-phase] → S6.1 CLOSED in S6.1.1 (Group B PI-2)** Residual Bootstrap `<small class="text-muted">` on `rules.html:65` folds into the same `:root { --bs-secondary-color: ... }` redirect that closed the bone-canvas family site-wide.
- **[S3.3.1 in-surface] CLOSED in S3.3.2** `_game_tiles_compact.html:28-29` slug-branched display copy.
- **[S3.3.1 in-surface] CLOSED in S3.3.2** Heuristic lift from 24 → ≥26 (gate (b) baseline+6 floor).
- **[S3.3.2 ship-as-is]** Golf `launch_label='2027'` is a year, not a date. Casual users may want quarter-level precision ("Q3 2027" / "Fall 2027"). The PI-2 `Opens 2027` affordance lands but the underlying data is a shrug for Golf specifically. Update `games/registry.py` when the Golf launch firms up — currently aspirational. Surfaced by the S3.3.2 re-critique as P2; flag if a future S4 / S6 polish session reopens it earlier.
- **[S3.3.2 ship-as-is]** `_home_out.html:58` `.home-metal-text` class on the "competition" word. Live probe confirms the class resolves to flat `var(--gold-light)` (no `background-clip: text`, no gradient) — the existing rationale block at `style.css:399-406` already documents that the class is solid gold-light to avoid the gradient-text ban. Hygiene flag: ensure no future commit accidentally promotes the class to gradient-text. Surfaced by the S3.3.2 re-critique as P2; no action needed at this iteration.
- **[S3.3.1 ship-as-is]** `_game_card.html` `featured` state declared (`:9-23`) but no caller in `core/`, `games/`, or `templates/` invokes it today. The registry's `is_featured=True` on WC + `featured_games()` helper compute the list but no template consumes either. S3.3.1 PI-B retuned `.game-card--featured` CSS to DESIGN.md compliance (replaced literal `#FFFFFF`, hardcoded WC navy/red palette, and neutral-black drop-shadow with CCC purple+gold + `var(--live-red)` semantic + chamber-purple shadow) so the dormant variant is brand-correct whenever S4.1 wires it through `_home_out.html`. No further work needed in S3.3 cluster; flag if S4.1 chooses to delete rather than wire (the supporting CSS at `style.css:4307-4403` would become dead code).
- **[S3.3.1 ship-as-is]** Coming-soon badge `mb-3` (16px) pushes the icon ~16px below the logged-out card's icon baseline at 375 viewport (probed in `.impeccable-review/S3.3.1/after/home-out-mobile.png`). The vertical-rhythm asymmetry is the deliberate consequence of PI-A's silhouette differentiation — the badge has to live somewhere, and the eyebrow position is the right call. A `mb-2` tightening (8px) would close the rhythm with the playable cards' icon row; left at `mb-3` to keep the badge visually independent of the icon. Re-evaluate only if a future critique re-flags it.

### Routed forward from S5.1.1 (in-surface to S5.1.2, cross-cluster to S5.3, cross-phase to S6.1)
- **[S5.1.1 in-surface] CLOSED in S5.1.2** Podium + Final Roster `<a>` text-link tap targets render 15px tall at 375 mobile (`B1G_Brad` 68×15, `test2` 33×15 — well below the 44 floor).
- **[S5.1.1 cross-cluster] CLOSED in S5.3 (§1.8 deviation, item taken cross-phase)** `.card.wc-card .wc-numeral` (style.css:2848) rendered bone (`#F3EFE6`) on the `.row-champion-pick` cream substrate (1.05:1) and on the masked-white substrate of every `.card.wc-card .table` cell (1.14:1).
- **[S5.1.1 cross-cluster] CLOSED in S5.3** `.btn-outline-secondary` quicklink trio in the home_shell footer (`Schedule` / `Groups` / `Rules`) read `#8a849b` on `.card.wc-card` navy at 3.04:1 (axe-confirmed); rendered universally via home_shell.html:48-62 across all four state partials.
- **[S5.1.1 cross-phase] → S6.1 CLOSED in S6.1.1 (Group A PI-1)** `.wc-eyebrow` saturation on `.card.wc-card` substrates. Closed by the same `:not()`-scoped bone-@.85 lift that closed S4.2.2 — all 5 axe hits in `_home_post` now read ~7.1:1.

### Routed forward from S5.2.1 (cross-phase to S6.1)
- **[S5.2.1 cross-phase] → S6.1 CLOSED in S6.1.1 (Group C PI-3)** Three remaining gradient-text rules retired in one atomic pass. `.home-shell .recap-rank` (style.css:2222) and `.card.wc-card.wc-hero-grad .champion-name` (:6700) swap to solid `var(--gold-light)` on dark substrates. `.table-worldcup .row-champion-pick .best-finish-champion` (:6983) swaps to `var(--gold-dark)` because the substrate is cream `#f7e9c2`, not dark — `--gold-dark` lands ~4.2:1 and qualifies for AA-large at Teko 700 / 22.4px. Zero `background-clip: text` rules remain in style.css (Layer A regression lock).
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

**On any plan vs. impeccable conflict during execution:** impeccable wins. Append findings to §0.4 with the discovering session ID; flip §9 rollup checkboxes with the commit hash; update memory if the lesson is durable.

### 1.5b Iteration convergence gate (per-surface sessions only — historical reference)

Per-surface sessions during P2–P5 iterated until convergence under this gate. **S6.1 and S6.2 are not per-surface sessions** (S6.1 is a cluster session per §1.5c; S6.2 is the project's merge/tag close), so this gate does not apply to Phase 6 work. Kept here as reference for the scorecard write-up in S6.2.

A surface is converged when **all four** are true:

1. **Zero P0 issues** in the latest `$impeccable critique` re-run on this surface.
2. **Zero P1 issues**, OR every remaining P1 carries a written deferral rationale that names its receiving session (`Sx.y.N+1`, cluster polish, S6.1, `[deferred-data]`). The rationale lives in §0.4 Backlog with the routing tag.
3. **Anti-pattern hard hits = 0** in the latest critique. (Hard hits = impeccable absolute-ban + DESIGN.md §6 Don't violations; soft observations don't count.)
4. **One of:** (a) Heuristics ≥ 32/40, (b) Heuristics ≥ baseline + 6, or (c) two consecutive iterations land within 1 point (first iteration excluded from (c)).

The four gates carry equal weight. If all four pass, stop — the signal is the gate, not Claude's appetite for more findings.

**Patterns surfaced during P2–P5 (binding for S6.1 + any future surface work):**

- **Bootstrap `order-*` is the canonical "mobile reading order vs desktop balance" tool.** Use `order-N` / `order-lg-0` on row children rather than duplicate templates or breakpoint-specific includes. Pattern lock: `_home_live.html` post-S2.1.2 — four primary blocks sit in one `.row` with mobile order `0/3/2/4` and desktop `0/0/0/0`.
- **The hero-metric-template ban applies to *adjacency*, not just presence.** 3+ equal-weight numerals in a row reads as SaaS cliché even with distinct data. Escape: one dominant numeral (2.6rem) + supporting chip + prose derivation. Apply on every CCC surface tempted toward 3+ equal-weight stat tiles.
- **Bootstrap `.text-muted` on dark `.card.wc-card` substrates always fails AA.** `#6c757d` against `rgba(0,17,46,.8)` is sub-AA. Surface-scoped class migration (`.fixture-stage-date`, `.fixture-vs`, `.ownership-ribbon-blurb`, etc., each tinted toward `--bone-mute`) is the canonical pattern. Site-wide retire is queued at S6.1 Group B.

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
---

## 2. Phase 0 — Cross-cutting harden (3 sessions, COMPLETE)

Systemic findings from the Tier 1 leaderboard exemplar critique, applied across every CCC surface before per-page work. PR P0 #11 merged.

- **S0.1 — Bootstrap shadow leak migration** (commit `60aee97`). Replaced every Bootstrap `shadow-sm`/`shadow`/`shadow-lg` utility on CCC cards with the brand-tinted `--shadow-sm/md/lg` scale, eliminating the neutral-gray `rgba(0,0,0,0.075)` leak. Locked by `tests/test_design_p0_shadow.py`.
- **S0.2 — Side-stripe ban migration + table semantics sweep** (commit `e4882ca`). Removed every `border-left: Npx` ≥ 2px colored accent on platform/WC components per the impeccable absolute ban. Same session: `<th scope="col">` + visually-hidden `<caption>` + region roles on every public leaderboard/standings table. Locked by `tests/test_design_p0_side_stripes.py` + `tests/test_design_p0_table_semantics.py`.
- **S0.3 — Mobile tap-target floor + white-on-gold contrast + em-dash sweep** (commit `37a57cf`). Global chrome (subnav, leaderboard mobile cards, navbar trophy CTA) lifted to 44×44 mobile-first floor. `--metal-gold` gradient retuned for white-on-gold contrast at all body sizes. Em-dash glyphs + HTML entities retired from user copy. Locked by `tests/test_design_p0_tap_targets.py` + `tests/test_design_p0_em_dashes.py`. One residual worst-stop AA on `--metal-gold-flat` routed to S6.1 Group I.

---

## 3. Phase 1 — Leaderboard close (1 session, COMPLETE)

Closes the Tier 1 leaderboard exemplar — the surface that anchored the cross-cutting baseline. PR P1 #12 merged.

- **S1.1 — Shape Your Standing + trend rank-delta + clarify leaderboard copy** (commit `56416ee`). Added `services/snapshots.compute_rank_delta(enrollment, window_days)` (dense-rank-scoped + season-aware per the `WorldCupRankSnapshot` invariant), wired into `routes.leaderboard()` as the Trend column. Restyled the "Your Position" tribune block above the standings table with editorial voice. Empty-state for the deadline-not-passed branch. Locked by `tests/test_design_p1_leaderboard.py`. Three pre-existing polish items routed to S6.1 Group J (`'none'` tiebreaker literal, Move column tooltip, Your Position visual thread to standings).

---

## 4. Phase 2 — Live state cluster (5 surfaces, COMPLETE)

Iterated per §1.5b until convergence. PR P2 #13 merged. Per-iteration detail (commit hash · score delta · gate state · top-line outcome) lives in §9 rollup; routed-forward items are in §0.4.

**Dev-data setup ritual (reference for any S6.1 work that boots a state-bearing surface).** `games/worldcup/services/state.worldcup_state()` returns `'post'` whenever match #104 has `is_completed=True`, regardless of `WC_FAKE_NOW` (see `project_ccc_wc_reskin_gotchas.md`). Per state:

- **Live:** match #104 `is_completed=False`; `WC_FAKE_NOW='2026-06-22T18:00:00+00:00'`. Restore #104 to `True` at session end.
- **Pre:** match #104 `is_completed=False`; any `WC_FAKE_NOW` before `2026-06-11T19:00:00+00:00`.
- **Post:** match #104 `is_completed=True` AND `winner_team_id` set AND `home_score`/`away_score` non-null. Scoring helpers return 0.0 if the winner FK is missing.

Boot: `ENVIRONMENT=development WC_FAKE_NOW='<iso>' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`. Without `ENVIRONMENT=development`, `now_utc()` ignores `WC_FAKE_NOW` silently. For Playwright auth: set the test user's password to a known value via `flask shell` at session start; reset to `secrets.token_urlsafe(24)` at session end so the temp credential never lingers.

### Surface inventory (all converged)

- [x] **S2.1** — `home_shell.html` + `_home_live.html` (converged 2026-05-08 at S2.1.2)
- [x] **S2.2** — `schedule.html` (converged 2026-05-08 at S2.2.1)
- [x] **S2.3** — `team_detail.html` (converged 2026-05-08 at S2.3.1)
- [x] **S2.4** — `stats.html` (converged 2026-05-09 at S2.4.1)
- [x] **S2.5** — `player_detail.html` (converged 2026-05-10 at S2.5.1)
- [x] **S2.6** — cross-cluster live polish (closed; 4 PIs + 3 re-routes to S6.1 — see §9 + §0.4)

---

## 5. Phase 3 — Global chrome + auth + errors (3 surfaces + cluster polish, COMPLETE)

Iterated per §1.5b until convergence. PR P3 #14 merged. Detail in §9 rollup; routed items in §0.4.

### Surface inventory (all converged)

- [x] **S3.1** — `templates/base.html` chrome (converged 2026-05-11 at S3.1.1)
- [x] **S3.2** — auth pages cluster: login / register / forgot / reset / change-password / profile (converged 2026-05-11 at S3.2.1)
- [x] **S3.3** — platform home + non-state component partials (converged 2026-05-11 at S3.3.2)
- [x] **S3.4** — errors (404 / 500) + cross-cluster chrome polish (closed; 4 PIs + errors first-pass)

---

## 6. Phase 4 — Pre-live state cluster (4 surfaces + cluster polish, COMPLETE)

Iterated per §1.5b until convergence. PR P4 #15 merged (9 CR rounds, project record). Detail in §9 rollup; routed items in §0.4.

### Surface inventory (all converged)

- [x] **S4.1** — `_home_pre.html` + `_home_out.html` (platform home in pre + logged-out states) (converged 2026-05-11 at S4.1.2)
- [x] **S4.2** — `picks.html` + `_pick_row.html` (converged 2026-05-11 at S4.2.2)
- [x] **S4.3** — `join.html` + `rules.html` (converged 2026-05-11 at S4.3.1)
- [x] **S4.4** — `groups.html` (converged 2026-05-11 at S4.4.1)
- [x] **S4.5** — cross-cluster pre-live polish (closed; 5 PI triage: 3 fix + 1 re-route + 1 decided-no-op + DESIGN.md route)

---

## 7. Phase 5 — Post-live state cluster (2 surfaces + cluster polish, COMPLETE)

Iterated per §1.5b until convergence. PR P5 #16 merged (1 CR round). Detail in §9 rollup; routed items in §0.4.

### Surface inventory (all converged)

- [x] **S5.1** — `_home_post.html` (converged 2026-05-12 at S5.1.2; gates 1-3 PASS, gate 4 unverified — single-PI a11y fix with no aesthetic shape change)
- [x] **S5.2** — post-state component partials: `_champion_banner.html` + `_commish_note.html` + `_dispatches.html` (converged 2026-05-12 at S5.2.1). Plan deviation: inventoried `_recent_results.html` is live-only, so S5.2 scope resolved to 3 partials; `_dispatches.html` ships as a commented-out scaffold.
- [x] **S5.3** — cross-cluster post-live polish (closed; 4 PIs covering routed-numeral contrast + quicklink contrast + 2 cross-cluster Tribune-voice fixes)

---

## 8. Phase 6 — Final polish + scorecard

P6 closes the project: cross-phase polish (S6.1) and scorecard + merge + tag (S6.2). S6.1 is a **cluster session** per §1.5c (Step 0 sweep → §1.5c triage discipline → Layer A locks + Layer B verification on touched + adjacent surfaces; Layer C skipped by default; §1.5b convergence gate does not apply). Expect S6.1 to fan into 2-4 iterations (S6.1.1, S6.1.2, ...) — each iteration caps at 3-5 triage outcomes per §1.5c.

### S6.1 — Cross-phase polish

**19 items routed in from §0.4, organized into 10 primitive groups.** Each group is internally close to atomic — most of S6.1's work is bundling routed items by primitive so one CSS rule + one DESIGN.md amendment + one Layer A lock file closes 2-3 items at once. Item count ≠ PI count: a group is one PI per the §1.5b/§1.5c atomic-edit rule.

**Group A — Eyebrow primitive + saturation (3 items, 1 PI).** Closes all `.wc-eyebrow` saturation findings in one alpha-lift + DESIGN.md §3 primitive ratification pass.

- **[S2.3.1 cross-cluster] → S6.1** Eyebrow primitive saturation. `.wc-eyebrow` renders 9-14× per page on team_detail (hero pre-headline, hero stat labels, ribbon labels, fixture stage rows, path stage tiles, picker section). DESIGN.md §3 defines the primitive as "the small uppercase line above section headlines", singular. The new `.wc-meta-label` primitive (introduced in S2.3.1) is a candidate for in-row labels but needs cluster-level review against home/leaderboard/stats/player_detail before promoting. Re-routed by S2.6: ratification needs cross-phase comparison.
- **[S4.2.2 cross-phase] → S6.1** Dark readonly tier-name eyebrow at ~0.55 alpha on navy (`rgba(0,17,46,.8)`) at 11.2px Teko letter-spaced — borderline AA. Bundle: lift the dark-card `.wc-eyebrow` alpha to .72 (the `picks-rules-link` precedent from S4.2.1 PI-3) or .85 across every `.card.wc-card .wc-eyebrow` instance in one pass.
- **[S5.1.1 cross-phase] → S6.1** `.wc-eyebrow` saturation on `.card.wc-card` substrates renders `#9c9fa4` on `#313d53` at 4.11:1 (axe surfaces 5 hits in _home_post: champion banner, your-finish, podium header, roster header, around-the-pool).

**Group B — `.text-muted` site-wide retire (2 items, 1 PI).** One global override or migration off `.text-muted` to CCC scope classes.

- **[S3.2.1 cross-phase] [S6.1 routed]** Bootstrap `.text-muted` paints via `--bs-secondary-color !important`, so any project-side override loses the cascade unless it also carries `!important`. S3.2.1 PI-2 patched this inside `body.auth-page`; S2.6 PI-3 closed three live-cluster instances; pattern recurs site-wide on leaderboard, schedule, team_detail, stats, player_detail. A single `!important`-bearing override (or complete migration off `.text-muted` to CCC scope classes) closes the whole bug class.
- **[S4.3.1 cross-phase] → S6.1** Residual Bootstrap `<small class="text-muted">` on `rules.html:65` (desktop tier-team-list cell, hidden on mobile via `d-md-block`). One additional instance to fold into the cross-phase retire above.

**Group C — Gradient-text retire (1 item, 1 PI — 3 sites).**

- **[S5.2.1 cross-phase] → S6.1** Three remaining gradient-text rules form a system-wide pattern after S5.2.1 PI-1 retired the champion-banner instance: `style.css:2208` (`.home-shell .recap-rank` — S5.1 "Your Finish" rank numeral); `style.css:6644` (`.card.wc-card.wc-hero-grad .champion-name` — team_detail / leaderboard hero); `style.css:6928` (`.table-worldcup .row-champion-pick .best-finish-champion` — leaderboard champion-row marker). All use `var(--metal-gold)` `background-clip: text`, violating the impeccable absolute ban + DESIGN.md §6. Fix shape: solid `var(--gold-light)` mirror of `.home-metal-text` precedent at `style.css:461`. One atomic retire pass + one Layer A test file locking all three rules.

**Group D — Tribune-voice H1 + DESIGN.md §3 primitive (1 item, 1 PI — 8 surfaces).**

- **[S4.4.1 cross-phase] → S6.1** Page H1 "Group Standings" stays as functional chrome rather than masthead voice; the S4.4.1 eyebrow + lead rewrite carry the Tribune register but the H1 itself reads as SaaS-utility. Same pattern affects 8+ surfaces (leaderboard "Leaderboard", schedule "Tournament Schedule", stats "Stats Hub", picks "Pick Your Roster", rules "Rules", join "Join the Pool", profile "Profile"). A system-wide Tribune-register pass that ratifies a primitive shape (Teko display + Tribune voiced title + functional fallback id) in DESIGN.md §3 once every primary surface has been touched.

**Group E — Voice repetition / SaaS-cliché copy (2 items, 1-2 PIs).**

- **[S4.2.1 cross-phase] → S6.1** Voice repetition stack on read-only picks: "Sealed · still amendable" eyebrow + "Sealed. Still amendable." H1 + "You can amend your picks until {{ deadline_ct }}." microcopy + "Amend the Oath" CTA — same fact stated 4× above the fold. PRODUCT.md "Sharp / Competitive" register asks for one decisive line. Pattern recurs across deadline-bearing WC surfaces (`_home_pre` countdown decree, `_home_live` deadline awareness, `team_detail` fixture statuses).
- **[S4.1.1 cross-phase] → S6.1** Flash banner ("Logged in successfully!" etc.) competing with home-shell masthead. Flash lives in `base.html` chrome and persists across every authenticated home + game page; reads as the highest-contrast object on a screen whose hero is supposed to be the masthead. Auto-dismiss success flashes after ~4s with CSS transition, OR restyle inside `.home-shell` to read as a thin gold-rule + small italic Newsreader inline confirmation that doesn't compete with the masthead.

**Group F — Markup-as-icon a11y + `<time datetime>` semantics (2 items, 1 PI).**

- **[S2.4.1 cross-phase] → S6.1** Tournament-progress phase labels in `stats.html:302` use markup-as-icon (`✓` for done, `←` for current) without `aria-label`. Screen readers speak "check" / "left arrow", not "completed" / "current". Same pattern likely on home progress widgets (`_home_live` / pre-state countdown) and any future post-state recap progress bar.
- **[S2.2.1 cross-phase] → S6.1** `.schedule-day-date` lacks `<time datetime="...">` semantics. Cross-page pattern: any page that prints a date should expose machine-readable form for screen readers, calendar extensions, and crawlers — `home_shell` time stamps, `team_detail` recent-result dates, `leaderboard` snapshot dates.

**Group G — DESIGN.md primitive docs (2 items, 1 PI — doc-only).** Both re-routed by S4.5 as "decided no-op + DESIGN.md route" — code is correct; doc gap.

- **[S4.2.1 cross-cluster] → S6.1 (re-routed by S4.5)** `.tier-badge` vs `.wc-multiplier-chip` vocabulary canonical primitive. Session-time grep refuted the original "wider than picks alone — team_detail / player_detail / stats" premise: `tier-badge` is absent from those three surfaces (they use only `wc-tier-dot`). Actual scope: `rules.html` (×5, displaying literal "T1/T2/..." numeric text companion to `wc-tier-dot`) + `_home_pre.html:42` (ballot `roster-tier-label`). Three primitives play distinct roles: `wc-tier-dot` = visual mark, `tier-badge` = numeric text companion, `wc-multiplier-chip` = multiplier indicator. DESIGN.md §6 doc PI.
- **[S4.3.1 cross-cluster] → S6.1 (re-routed by S4.5 as decided no-op + DESIGN.md route)** Mobile tier-meta text below 16px body floor (`.tier-mobile-card-picks` + `.tier-teams-list` 13.6px on rules.html, `.player-pick-card .pick-team small` 12px + `.pick-points small` 11.2px on picks.html, all caption/metadata semantics under a dominant Teko read-target on the same row). Decided no-op at S4.5: caption-tier <16px is a deliberate, repeated cross-cluster pattern. DESIGN.md §3 caption-tier dispensation note: "≥16px applies to body text and primary read-targets; explicit caption/metadata classes may step down to ≥0.75rem (12px) when the primary read-target on the same row carries the dominant hierarchy".

**Group H — Component silhouettes / cross-state chrome (2 items, 2 PIs). CLOSED in S6.1.4.**

- **[S2.1.1 cross-cluster] → S6.1 CLOSED in S6.1.4 (PI-1)** Repeating gradient-card silhouette across 7 home components. Cross-state inventory at session-time confirmed the seven already inhabit §5's two recipes + the `.ballot-card` third register; two single-instance hero variants (`.dossier`, `.commish-note-body`) layered on top. DESIGN.md §5 amended (Informational bullet now lists `.commish-note-body`; closing paragraph names `.dossier` + `.ballot-card` as single-instance heroes with do-not-duplicate language) and CSS consolidates the Informational recipe's border to bone-8 across all three members + the commish-note-body radius to 12px.
- **[S2.1.1 cross-cluster] → S6.1 CLOSED in S6.1.4 (PI-2, decided already-closed)** Leaderboard rolls non-interactive `<div>` premise refuted at session-time. `_home_live.html` top-5 preview + `leaderboard.html` desktop + mobile-cards all already anchor each row to `worldcup.player_detail` (and `picks` for the self-row). Layer A lock prevents silent regression; no code change required.

**Group I — Trophy CTA worst-stop AA / token retune (1 item, 1 PI — DESIGN.md spec change).**

- **[S0.3] → S6.1** Navbar trophy CTA: chamber-purple text on `--metal-gold-flat` lands at 3.6:1 against the gradient's darkest stop (`--gold-dark` = `#8A6A1A`) at the bottom-right corner of the button. AA-passing across most of the surface (7.5:1 mid-stop, 12.4:1 lightest), but the worst-stop pixel-corner reads 3.6:1 — below the 4.5:1 normal-text floor. Fix requires retuning `--metal-gold-flat`'s dark stop in `tokens.css` (DESIGN.md token spec change — out of scope for S0.3 at the time).

**Group J — Leaderboard pre-existing polish (3 items, 1-2 PIs).** Three small leaderboard items deferred since S1.1.

- **[S1.1] → S6.1** `leaderboard.html` desktop table renders the Tiebreaker cell as the literal lowercase string `'none'` (`{{ e.usa_goals_guess if e.usa_goals_guess is not none else 'none' }}`) — breaks the editorial register. Use a voiced fallback like "No guess" or render an actual blank cell.
- **[S1.1] → S6.1** Move column header (`<th scope="col" class="text-end">Move</th>`) gives no since-when context. Add a `title=` tooltip (e.g., "Change since yesterday's snapshot") on the header for the analyst register.
- **[S1.1] → S6.1** The Your Position tribune block sits on the bone canvas above the standings table with no visual thread between them — the gap reads as forgotten space rather than editorial breathing room. Candidates: a `border-top: 2px solid var(--gold)` rule above the table, or a section eyebrow ("THE LEDGER") above it. Cross-surface polish session compares similar gap moments across the cluster (home dossier, schedule, team_detail) and picks a consistent treatment.

### S6.1 execution shape

1. **Skill load + context warm**: `Skill { skill: "impeccable" }` (loads PRODUCT.md + DESIGN.md). Read this plan, §0.4 + §8 docket in full, DESIGN.md §3 (Eyebrow + H1 primitives) + §5 (chrome / auth composition) + §6 (Don't list).
2. **Step 0 (cluster sweep, per §1.5c)**: confirm each of the 19 items still applies — grep the surfaces named in each item; some may have been incidentally closed by a P5 freebie. Annotate §0.4 with any "no longer applies — closed by S5.X.Y" notes before fixing.
3. **Iteration triage per §1.5c**: pick 3-5 groups per iteration (each group ≈ 1 PI per the atomic-edit rule). Suggested bundles (re-evaluate at session-time):
   - **Iter 1 candidates:** Group A (eyebrow alpha + DESIGN.md §3) + Group C (gradient-text retire) + Group B (`.text-muted` retire) — all CSS + DESIGN.md doc + Layer A locks; high-leverage, low blast radius.
   - **Iter 2 candidates:** Group D (Tribune H1 across 8 surfaces) + Group F (markup-as-icon + `<time datetime>`) + Group G (DESIGN.md §3 / §6 doc-only).
   - **Iter 3+ as needed:** Groups E + H + I + J.
4. **Per-iteration verification**: Layer A source-pattern locks under `tests/test_design_p6_s6_1_<iter>.py`. Layer B Playwright/Chrome MCP probes on touched + adjacent surfaces (per §1.5c). Layer C skipped by default unless cluster work re-flowed every surface.
5. **Plan amendments**: as each routed item closes, annotate §0.4 with `CLOSED in S6.1.N`. Update §9 rollup with commit + headline.
6. **PR**: open `Impeccable P6 — Final polish` at the end of the last iteration. CR-feedback-approval session(s) per §1.8 between push and merge.

### Session S6.2 — Scorecard, handoff doc, merge

**Goal:** Document outcomes. Merge `design/wc-polish` → `main`. Tag release.

- [x] **Step 1: Write a project scorecard.** Saved at `docs/superpowers/specs/2026-05-12-impeccable-design-improvement-scorecard.md`. Captures Tier 1 baseline → final, cross-surface heur/audit deltas, cumulative findings closed (78 §0.4 routes resolved), 22 `[ship-as-is]` backlog items with rationale, and lessons-learned digest for future impeccable work.
- [x] **Step 2a: Update CLAUDE.md.** Two pattern locks added to "Design system & CSS": Bootstrap `.text-muted` site-wide override (the `:root --bs-secondary-color` redirect trick) and gradient-text retire (zero `background-clip: text` rules; precedent is `.home-metal-text`). Other S6.1 ratifications (eyebrow co-existence, Tribune-voice H1 dispensations, 2-tier card vocabulary, Tier Primitives, caption-tier dispensation, single-instance hero silhouettes) stay in DESIGN.md where future sessions will look first.
- [x] **Step 2b: Plan cleanup pass.** All converged work flipped to `[x]`. S6.2 in-progress + post-merge steps stay `[ ]` (Steps 3–6 below).
- [ ] **Step 3: Open final PR** `Impeccable P6 — Final polish + project close`. Confirm merge-ready status: pytest green + CR approved per §1.8.
- [ ] **Step 4: Merge `design/wc-polish` → `main`** after PR review.
- [ ] **Step 5: Tag the release** `impeccable-v1`.
- [ ] **Step 6: Production deploy + run Brad's production-launch test script** on `main` post-merge (per `docs/production-launch-test-script.md`).

---

## 9. Session checklist (update as you go)

Per-session scoreboard: `commit · heur Δ · audit Δ · anti-pat Δ · gate state · top-line outcome`. Iterations nest under their parent surface row; a surface flips `[x]` when its convergence gate passes. P6 rows pre-filled as placeholders.

### Phase 0 — Cross-cutting harden
- [x] S0.1 (`60aee97`) · Bootstrap shadow leak migration — brand-tinted `--shadow-sm/md/lg` replaces neutral-gray Bootstrap shadows on every CCC card.
- [x] S0.2 (`e4882ca`) · Side-stripe ban migration + table semantics sweep — every `border-left: Npx` ≥ 2px removed from platform/WC components; tables gain `<th scope>` + `<caption>` + region roles.
- [x] S0.3 (`37a57cf`) · Mobile tap-target floor + white-on-gold contrast + em-dash sweep — global chrome lifts to 44×44 floor; `--metal-gold` retuned; entities retired from user copy.
- [x] **PR P0** opened + merged: `#11`

### Phase 1 — Leaderboard close
- [x] S1.1 (`56416ee`) · Shape Your Standing + trend rank-delta + clarify copy — `compute_rank_delta` season-scoped helper + Your Position tribune block + deadline empty state.
- [x] **PR P1** opened + merged: `#12`

### Phase 2 — Live state cluster
- [x] **S2.1** — `home_shell` + `_home_live` (converged 2026-05-08 at S2.1.2)
  - [x] S2.1.1 (`e69966f`) · heur 26→30/40 · audit 15→17/20 · anti-pat 5→0 · gate FAIL · gradient-text + hero-metric ban + identical-card grid + "this week" copy + banned `stage|title`. 6 in-surface backlog → S2.1.2.
  - [x] S2.1.2 (`296a122`) · heur 28→32/40 · audit 16→18/20 · anti-pat 0→0 · gate PASS · section-more 44 floor + dossier-stamp Tribune voice + right-rail starvation via `order-*` + "Also Today" rename. 4/6 backlog closed; 2 → S2.1.3.
- [x] **S2.2** — `schedule.html` (converged 2026-05-08 at S2.2.1)
  - [x] S2.2.1 (`d8b0f10`) · heur 19→30/40 · audit ~11→16/20 · anti-pat 4→0 · gate PASS · matchday grouping route change + `id="today"` deep-link + day-header primitive + time-only stamps + AA bump on muted text. 4 routed (3→S2.6, 1→S6.1).
- [x] **S2.3** — `team_detail.html` (converged 2026-05-08 at S2.3.1)
  - [x] S2.3.1 (`7e44752`) · heur 24→31/40 · audit 14→18/20 · anti-pat 0→0 · gate PASS · hero re-shape (one dominant Scored numeral + Newsreader derivation) + owned-state Voice + path-to-crown `<ol>` + per-status icons + mobile fixture 3-col + `.picker-link` 44 floor. 5 routed.
- [x] **S2.4** — `stats.html` (converged 2026-05-09 at S2.4.1)
  - [x] S2.4.1 (`8b3ef65`) · heur 19→32/40 · audit 9→14/20 · anti-pat 3→0 · gate PASS · `--text-muted`→`--text-secondary` sweep + KPI band collapses + `.wc-stat-card.is-lead` variant + `tb()`→`tbl()` tier-name reveals. 10 routed.
- [x] **S2.5** — `player_detail.html` (converged 2026-05-10 at S2.5.1)
  - [x] S2.5.1 (`db51590`) · heur 21→31/40 · audit 13→17/20 · anti-pat 2→0 · gate PASS · contrast lock on `.card.wc-card` dark substrate + hero re-shape (mirrors S2.3.1) + tier names replace bare T# + cluster-3 surgical-exclusion beat. 4 routed.
- [x] **S2.6** (`9b7cc2f`) · cross-cluster live polish · 4 PIs + 3 re-routes to S6.1 · `--bs-table-bg` defensive default + `.text-muted` retire in live cluster + schedule `jump-today` chip + `.wc-stat-card` double-elevation kept (DESIGN.md §4.4 mandate). 8 Layer A locks; 404 tests green.
- [x] **PR P2** opened + merged: `#13`

### Phase 3 — Global chrome + auth + errors
- [x] **S3.1** — `base.html` chrome (converged 2026-05-11 at S3.1.1)
  - [x] S3.1.1 (`df999ae`) · heur 28→32/40 · anti-pat hard hits 3→0 · gate PASS · navbar cascade cleanup (DESIGN.md §5 solid purple-700 + 1px purple-800 border renders) + `.navbar-brand` 44 mobile floor + sub-nav inactive alpha .48→.75 (10.55:1) + skip-link + `<main tabindex="-1">`. 2 P1s routed (navbar-brand color drift → S3.4, trophy CTA → S6.1).
- [x] **S3.2** — auth cluster (converged 2026-05-11 at S3.2.1)
  - [x] S3.2.1 (`8c9c3b2`) · cluster heur 24.8→31.5/40 avg · audit 10.5→14.5/20 avg · anti-pat hits 0→0 · gate PASS on all 6 templates · `.auth-link-row` 44 floor + `body.auth-page` `--text-muted` retire + brand-panel alpha lift + mobile transparent form panel + Tribune voice sweep. 6 routed to S3.2.2 + S3.4 + S6.1.
- [x] **S3.3** — platform home + partials (converged 2026-05-11 at S3.3.2)
  - [x] S3.3.1 (`c3e9222`) · heur 20→24/40 · audit 17→19/20 · anti-pat hits 1→1 · gate FAIL (heur 2 short, identical-card-grid routed to S4.1 per scope) · `_game_card.html` `coming_soon` silhouette differentiation + `.game-card--featured` brand retune + `.status-badge--muted` Council Purple tint.
  - [x] S3.3.2 (`fa922fc`) · heur 24→29/40 · audit 19→20/20 · anti-pat 0→0 in-scope · gate PASS · registry-driven tile copy via `short_name`/`launch_label` fields + "Opens [season]" microcopy + `.game-card--live` `:focus-visible` ring.
- [x] **S3.4** (`0ac96e9`) · errors first-pass + cross-cluster chrome polish · 4 PIs · 404/500 reshape (hero-metric template → editorial masthead) + navbar-brand orphan deletion + chrome `:focus-visible` + `<nav>` semantics on game-subnav + DESIGN.md §5 Auth Surface Composition subsection. 22 Layer A locks.
- [x] **PR P3** opened + merged: `#14`

### Phase 4 — Pre-live state cluster
- [x] **S4.1** — `_home_pre` + `_home_out` (converged 2026-05-11 at S4.1.2)
  - [x] S4.1.1 (`170b1e2`) · heur 24→28/36 (≈31/40) · audit 17→18/20 · anti-pat hits 2→0 · gate FAIL · registry grid reshape + countdown hero-metric collapse + `.decree-links` 44 floor + `.join-alt` 44 floor. 5 routed.
  - [x] S4.1.2 (`05119a3`) · heur 28→32/36 (≈35.5/40) · audit 18→19/20 · anti-pat 0→0 · gate PASS · pre-state desktop 7fr/5fr 2-col reshape + `.ballot-card` semantic split + 2-tier home-shell card vocabulary in DESIGN.md §5 + `.out-prop` row differentiation.
- [x] **S4.2** — picks + `_pick_row` (converged 2026-05-11 at S4.2.2)
  - [x] S4.2.1 (`b097e8a`) · heur 24→27/40 · audit 11→15/20 · anti-pat hits 8→0 · gate FAIL · `.wc-team-card` `role=checkbox` keyboard primitive + pick-accordion `grid-template-rows` motion-law fix + 44 floor + Council Purple tinted-neutrals. 10 routed.
  - [x] S4.2.2 (`ebeb8df`) · heur 27→32/40 · audit 15→17/20 · anti-pat 0→0 · gate PASS · mobile `.player-pick-card` to `<a>` + `.wc-numeral` modifier classes + edit-form H1→H2×6 outline + `.pick-summary` top-stripe rewrite + in-iteration §1.7 contrast fold-in.
- [x] **S4.3** — join + rules (converged 2026-05-11 at S4.3.1)
  - [x] S4.3.1 (`d17add1`) · heur 24→33/40 · audit 11→19/20 · anti-pat hits 11→0 in scope · gate PASS · rules.html dark-card prose lift (`.card.wc-card > .card-body` direct-child) + chip + tier-mobile-card scopes + join Tribune voice rewrite + rules H3→H2×7 + `.wc-champion-row` tint + form-label `--text-secondary`.
- [x] **S4.4** — `groups.html` (converged 2026-05-11 at S4.4.1)
  - [x] S4.4.1 (`93326ce`) · heur 24→30/40 · audit 13→18/20 · anti-pat hits 3→0 · gate PASS · group-table-header H2 primitive + `aria-labelledby` + `--text-muted`→`--text-secondary` + `.wc-group-index` pill rail + 16px team-name floor + Tribune voice + state chip.
- [x] **S4.5** (`0e03f38`) · cross-cluster pre-live polish · 5 PI triage (3 fix + 1 re-route + 1 no-op + DESIGN.md route) · Base column trio collapsed + `.wc-rules-index` nav rail + ultra-wide pill-rail xl cap + tier-vocab primitive doc → S6.1 + mobile <16px caption §3 dispensation → S6.1. 13 Layer A locks.
- [x] **PR P4** opened + merged: `#15` (merge commit `2b03c59`, 9 CR rounds — 6 real bugs + ~40 test-contract hardenings)

### Phase 5 — Post-live state cluster
- [x] **S5.1** — `_home_post` (converged 2026-05-12 at S5.1.2; gates 1-3 PASS, gate 4 unverified)
  - [x] S5.1.1 (`302abe6`) · gate FAIL · 3 PIs: hero-metric collapse on "Your Finish" + Tribune retrospection on champion banner + eyebrow `Champion` → `World Cup Winner`. 4 routed (S5.1.2, S5.3×2, S6.1).
  - [x] S5.1.2 (`6815238`) · gates 1-3 PASS, gate 4 unverified · single-PI a11y: class-scoped `.post-table-link` lifts 12 Podium + Roster anchors to 44×44 (was min 33×15). 6 Layer A locks; 641 tests.
- [x] **S5.2** — post-state component partials (converged 2026-05-12 at S5.2.1)
  - [x] S5.2.1 (`dc39bfe`) · gate PASS (heur 33/40) · 3 PIs: `.champion-name` gradient-text retire to solid `--gold-light` + `_commish_note.html` Jinja branches on `state` + champion eyebrow → `◈ Final Decree ◈`. 3 gradient-text rules routed to S6.1. 11 Layer A locks; 652 tests.
- [x] **S5.3** (`aa86691`) · cross-cluster post-live polish · 4 PIs: `.wc-numeral` bone-on-white scope-lock + `.btn-outline-secondary` quicklink contrast + WC banner eyebrow → `Final Decree` + platform retrospect "The Club records the night." 15 Layer A locks; 667 tests.
- [x] **PR P5** opened + merged: `#16` (merge commit `59cd738`, 1 CR round — 0 source bugs + 3 test-contract hardenings)

### Phase 6 — Final polish
- [x] **S6.1** — cross-phase polish (converged 2026-05-12 at S6.1.4; 19 of 19 §0.4 routes closed across 4 iterations). Sweep §0.4 → 19 routed items in 10 primitive groups (see §8). 4 iterations per §1.5c.
  - [x] S6.1.1 (commit: `git log design/wc-polish --grep='S6.1.1'`) · 3 PIs · Group A (eyebrow primitive ratification + `.card.wc-card .wc-eyebrow` :not()-scoped bone @ .85 lift — closes 3 routes: S2.3.1 + S4.2.2 + S5.1.1) + Group B (`:root` `--bs-secondary-color` redirect — closes 2 routes: S3.2.1 + S4.3.1) + Group C (3-site gradient-text retire to solid gold-light / gold-dark — closes S5.2.1). 11 Layer A locks; 678 tests. 6 of 19 §0.4 routes closed. Cluster bar PASS (Layer A + B; Layer C skipped per §1.5c).
  - [x] S6.1.2 (commit: `d390cfb`) · 3 PIs · Group D (Tribune-voice H1 pass on schedule / rules / groups + DESIGN.md §3 Display primitive ratification with dynamic-noun + auth-utility dispensations — closes S4.4.1) + Group F (stats progress `role="list"` + listitem aria-labels with completed/current/upcoming vocabulary + schedule `<time datetime>` — closes S2.4.1 + S2.2.1) + Group G (DESIGN.md §5 Tier Primitives subsection + §3 caption-tier <16px dispensation — closes S4.2.1 + S4.3.1 doc-only). 9 Layer A locks; 687 tests. 11 of 19 §0.4 routes closed. Cluster bar PASS (Layer A + B; Layer C skipped per §1.5c).
  - [x] S6.1.3 (commit: `d916feb`) · 4 PIs · Group J (leaderboard polish triple: `'none'` → `'No guess'` voiced fallback + Move column `title="Change since yesterday's snapshot"` tooltip + gold-divider thread `.your-standing-tribune + .card.wc-card{,+ .d-md-none}` with `!important` to defeat Bootstrap `.border-0` — closes S1.1 × 3 routes) + Group I (`--metal-gold-flat` 100% stop retuned `#8A6A1A` → `#A88420`; chamber-purple text now 5.19:1 at worst-corner vs 3.6:1; DESIGN.md §2 ratifies the diagonal dark anchor — closes S0.3 route) + Group E PI-A (picks card-header eyebrow collapses to invariant `The Ballot`, H1 retains state — closes S4.2.1 cross-phase route) + Group E PI-B (`.alert.alert-success.alert-dismissible` auto-fades after 4.4s via opacity-only animation with `prefers-reduced-motion` bypass — closes S4.1.1 cross-phase route). 10 Layer A locks + 4 contract updates (`re.search` for Move `<th>`); 697 tests. 17 of 19 §0.4 routes closed. Cluster bar PASS (Layer A + B; Layer C skipped per §1.5c).
  - [x] S6.1.4 (commit: `189f545`) · 2 PIs · Group H PI-1 (cross-state silhouette consolidation: DESIGN.md §5 Informational bullet folds in `.commish-note-body`; closing paragraph ratifies `.dossier` + `.ballot-card` as single-instance hero silhouettes with do-not-duplicate language; CSS normalizes `.commish-note-body` `border-radius: 8px → 12px` and lifts `.match-card` + `.cta-card--view` border `rgba(255,255,255,.08) → rgba(243,239,230,.08)` (bone-8) so the Informational recipe's border color is one tinted-neutral value across all three members — closes S2.1.1 cross-cluster silhouette route) + Group H PI-2 (decided-already-closed: `_home_live.html` top-5 preview + `leaderboard.html` desktop + mobile-cards all already anchor each row to `worldcup.player_detail`; Layer A locks the anchor coverage — closes S2.1.1 cross-cluster rolls route). 12 Layer A locks + 1 contract update (`tests/test_design_p4_s4_1_2.py` Informational border value `white-8 → bone-8`); 709 tests. **19 of 19 §0.4 routes closed.** Cluster bar PASS (Layer A + B on pre + post home + leaderboard; Layer C skipped per §1.5c).
- [x] S6.2 (commit: `901d949`) · Step 1 scorecard at `docs/superpowers/specs/2026-05-12-impeccable-design-improvement-scorecard.md` (Tier 1 baseline → final, cross-surface deltas, 22 `[ship-as-is]` items with rationale, lessons learned). Step 2a two CLAUDE.md pattern locks added (`.text-muted` site-wide redirect, gradient-text zero-rule lock). Step 2b plan cleanup pass — all converged work flipped to `[x]`. Steps 3–6 (PR open, merge, tag, prod deploy) tracked below.
- [x] **PR P6** opened: [#17](https://github.com/BradHagstrom16/fantasy-platform/pull/17) — pytest 709/709 green; GitGuardian PASS; CR review pending (handled in follow-up CR-feedback-approval session per §1.8).
- [ ] **Merge `design/wc-polish` → `main`**: ____
- [ ] **Tag**: `impeccable-v1`
- [ ] **Production deploy + Brad's production-launch test script run** on `main` (post-merge): ____

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
