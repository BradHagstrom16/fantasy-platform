# Spec C — CCC World Cup Reskin

**Date:** 2026-05-02
**Status:** Approved
**Initiative:** CCC Redesign (Specs A → B → C)
**Predecessors:**
- Spec A — CCC Brand Foundation + Chrome (`docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`), merged as `2859881`
- Spec B — CCC Home Redesign (`docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`), merged as `f11df5f`
**Successors:** None — Spec C is the final slice of the CCC redesign initiative
**Deferred (post-Spec-C, not in scope):** Match (needs sports-data API), Tribune (needs content pipeline)
**Branch:** `redesign/ccc-worldcup` (worktree)
**Source design bundle:** `fantasy-platform-and-world-cup-design/` (Claude Design handoff, untracked)

---

## 1. Context

Spec A established the CCC brand foundation — `tokens.css` (Layer 1), `style.css :root` (Layer 2), logo + favicon, naming sweep, restyled `base.html` chrome and auth/admin pages. Spec B replaced the platform home with a four-state state-shell + 4 partials + new `WorldCupRankSnapshot` infrastructure. Both shipped clean.

World Cup interior pages were intentionally untouched in A and B. Spec C closes the loop: every WC blueprint surface gets reskinned to the CCC visual language with WC vocabulary ("the Oath", "Roster", "Tiebreak"), the WC palette (navy `#001A4D` + red `#BF0A30` + cream `#F5F1E8`) is fully exercised across the blueprint, and the WC index page is migrated to the same builder pattern Spec B used for the platform home.

This is a **visual + structural reskin only** — game rules, scoring math, and route mutation logic do not change. Two architectural exceptions:
- **One new public route**: `/worldcup/team/<int:team_id>` (the design bundle's `wc-team.jsx` has no production analog today)
- **One template-to-service migration**: `worldcup.index` moves from inline state branching to a Spec-B-style dispatcher + 4 partials + `games/worldcup/services/home_context.py`

### Design bundle screen mapping

The design bundle (`fantasy-platform-and-world-cup-design/project/components/`) ships 12 mobile-only iOS-bezel mocks. Eight map to Spec C surfaces; two are deferred; two are shared primitives.

| JSX mock | Production surface | Plan |
|---|---|---|
| `wc-pick.jsx` | `picks.html` (edit form state) | 1 |
| `wc-tiebreak.jsx` | `picks.html` (sidebar / mobile sticky bar) | 1 |
| `wc-confirmed.jsx` | `picks.html` (sealed pre-deadline state) | 1 |
| `wc-roster.jsx` | `picks.html` (sealed and post-deadline states) | 1 |
| `wc-player.jsx` | `player_detail.html` | 2 |
| `wc-team.jsx` | NEW `team_detail.html` + `/worldcup/team/<id>` | 2 |
| `wc-board.jsx` | `leaderboard.html` | 3 |
| `wc-stats.jsx` | `stats.html` (single-tab reference; existing 6-tab page restructured via `frontend-design`) | 3 |
| `wc-shared.jsx`, `shared.jsx` | shared primitives — `.wc-eyebrow`, `.wc-numeral`, `.wc-tier-dot`, `.wc-multiplier-chip`, `.wc-hero-grad`, `.wc-card` | 1 |
| `wc-match.jsx` | **DEFERRED** — sports-data API required | — |
| `wc-tribune.jsx` | **DEFERRED** — content pipeline required | — |

Cross-spec handoff guidance lives at `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_specs_b_c_notes.md`. Notable: WC palette tokens already in `tokens.css`; Crown→Commish copy bugs in `wc-pick.jsx` lines 6 + 133 must be fixed during implementation; mobile-first stance is canonical.

---

## 2. Approved decisions

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Scope boundary | **C — 8 designed screens + `index.html` reskinned + light chrome pass on `schedule.html` / `groups.html` / `rules.html`** | Reference pages need visual parity with new tokens but don't warrant bespoke design (no mocks). Light pass keeps them coherent without scope creep. |
| D2 | Team detail treatment | **B — Build new `/worldcup/team/<int:team_id>` route + `team_detail.html`** | `wc-team.jsx` has no production analog. Per-team detail surfaces existing data (match log, score events, ownership) in a navigable view; deferring would leave the design bundle visibly incomplete. Public route, no `@login_required`. |
| D3 | Slicing | **B — 4 implementation plans under one Spec C document** | Surface (~10 templates + 1 new route + sub-nav rewrite + service module) is too large for one PR. 4 plans give independent merge cycles, smaller review surface, and clean rollback paths. Single spec doc preserves cross-cutting decision continuity. |
| D4 | Mobile-first stance | **B — Mobile-first with thoughtful desktop scaling** | Production already has tasteful desktop responsive splits (`col-lg-8` form, table-vs-card leaderboard); these are preserved. Bundle is mobile-only; desktop layouts use design judgment. |
| D5 | Sub-nav structure | **A2 + mobile compactions** — Hub · Roster · Board · Schedule · Stats · Rules + Admin (conditional). Hide `⚽ WC 2026` label on mobile; tighten pill padding/font. Groups demoted to inline group-letter badge links + Hub footer link. | Mobile fits 6 pills without horizontal scroll after compactions (verified against production CSS measurements). Schedule retained because it's higher-traffic than Groups during the tournament. Pills consistent with Golf/CFB pattern; bottom-tab-bar paradigm rejected as scope creep. |
| D6 | `index.html` treatment | **C+B combined** — migrate to Spec-B-style state dispatcher + 4 partials + `games/worldcup/services/home_context.py` (architectural), AND restructure for mobile-first single-column flow | "Long-term correct solution." Mirrors Spec B's home pattern scoped to the WC blueprint. Single-column flow up to lg breakpoint; existing 8/4 sidebar split discarded. |
| D7 | Stats Hub depth | **C — Aggressive structural restructure via `frontend-design` skill** | No live users; pre-launch is the right time. Tab consolidation permitted (6 → 3-4 tabs). Service-layer entry points (`get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`) untouched — template rewrites only. |
| D8 | Design fidelity | **B — Strict-where-clear, interpretive-where-ambiguous** | Bundle drives palette/typography/hero patterns faithfully. Design judgment fills desktop gaps and reconciles existing production patterns. |
| D9 | Leaderboard scope | **Tier C — Reskin + "Your Standing" hero block + Trend column** (using `WorldCupRankSnapshot` from Spec B). Filter chips deferred to a future Plan 3.2 | Snapshot infra already exists (free trend column win). "Your Standing" answers the most-asked-by-users data slice. Filter chips require new aggregation logic — separate plan. |
| D10 | Trend gate | **`len(snapshots) >= 7` — copies Spec B's gate verbatim** | Avoids overstating trend with sparse data. Pattern continuity with Spec B's home-page sparkline gating. |
| D11 | Pre-deadline ownership privacy on team detail | **Strict — entire "Who Picked This" section omitted pre-deadline (not even a count)** | Matches existing roster-hiding invariant in `player_detail.html`. Even a count leaks information about which teams gained traction. |

---

## 3. Goals and non-goals

### Goals
- Reskin every World Cup user-facing surface to the CCC visual language (CCC house tokens + WC palette)
- Surface "Commish" voice + WC vocabulary (Oath, Roster, Tiebreak, tier names) consistently across the blueprint
- Migrate `worldcup.index` to a Spec-B-style state dispatcher; close architectural symmetry between platform home and WC home
- Add the missing per-team detail surface (`team_detail`) so the design bundle's `wc-team.jsx` ships
- Keep all 4 plans independently reviewable and revertible

### Non-goals
- Match-screen functionality (`wc-match.jsx`) — deferred pending sports-data API
- Tribune feed (`wc-tribune.jsx`) — deferred pending content pipeline
- New aggregation analytics (leaderboard filter chips per D9, champion-pick semantics) — future Plan 3.2
- Game-rules / scoring math changes — invariant
- Admin route restyling — out of scope; admin pages stay on Bootstrap defaults
- Golf or CFB blueprint redesigns — separate per-game initiatives later
- Stats Hub service-layer changes — frozen per D7

---

## 4. Slicing — 4 plans under one spec

| Plan | Slice | Templates / files touched | New routes | Architectural |
|------|-------|---------------------------|------------|---------------|
| 1 | My picks + foundation | `picks.html`, `_pick_row.html`, `_pick_accordion_script.html`, `templates/base.html` (sub-nav block), `static/css/style.css` (cross-cutting WC additions), `schedule.html`, `groups.html`, `rules.html` | none | sub-nav CSS rewrite + cross-cutting WC class additions |
| 2 | Per-rival surfaces | `player_detail.html`, NEW `team_detail.html`, `games/worldcup/routes.py` (new route), optional `games/worldcup/services/team_detail.py` for ownership helpers | NEW `/worldcup/team/<int:team_id>` | new public read route + ownership query helpers |
| 3 | Public analytics | `leaderboard.html`, `stats.html`, `games/worldcup/routes.py` (leaderboard payload extension for Your Standing + trend) | none | `frontend-design` skill drives stats restructure; leaderboard adds rank-neighbor + trend computation |
| 4 | WC Hub migration | `index.html` → `home_shell.html` + 4 `_home_<state>.html` partials, NEW `games/worldcup/services/home_context.py`, possibly NEW `games/worldcup/services/voice.py` for state-keyed copy, possibly lift `_stage_label()` to `games/worldcup/services/stage.py` | none | service module + dispatcher mirroring Spec B |

**Plan dependencies**: Plan 1 lands the foundation (sub-nav, cross-cutting CSS) and merges first. Plans 2, 3, 4 can land in any order or parallel after Plan 1.

**Branch / merge model**: One worktree directory (`redesign/ccc-worldcup`) reused across plans. Each plan ships its own branch + PR (e.g., `redesign/ccc-worldcup-plan1`, `-plan2`, etc.). Plan 1 branches from `main`; subsequent plans branch from `main` after the prior plan's PR merges. Implementer can also open multiple worktrees for parallel work on Plans 2 / 3 / 4 once Plan 1 lands.

---

## 5. Cross-cutting decisions (apply to all plans)

### CSS layer additions (land in Plan 1)

These additions live in `static/css/style.css` under the existing `/* === WORLD CUP FANTASY POOL === */` section, consuming `--wc-navy` / `--wc-red` / `--wc-white` already defined in `tokens.css` from Spec A. **No new tokens** are introduced by Spec C.

- `.wc-eyebrow` — small uppercase Teko label (`.7rem`, `letter-spacing: .08em`); red variant for "hot" eyebrows, cream-mute for "cold"
- `.wc-numeral` — Teko display numeral utility (tabular-nums, used in scores, ranks, multipliers)
- `.wc-hero-grad` — gradient background mixin for hero blocks (radial gold-tint + linear navy-to-near-black)
- `.wc-tier-dot` — circular tier indicator (sibling pattern to existing `tier-badge-{n}`)
- `.wc-multiplier-chip` — flat numeral chip for `×N` displays
- `.wc-card` — card refresh with bundle's metalwork accent; coexists with Bootstrap `.card`

### Voice / copy

WC vocabulary from Spec A's voice doctrine (extended in `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_specs_b_c_notes.md`):

| Production today | Spec C copy |
|---|---|
| "My Picks" (sub-nav, page H1) | **Roster** |
| "Leaderboard" (sub-nav label) | **Board** (page H1 stays "Leaderboard") |
| "Submit Picks" | **Seal the Oath** |
| "Edit My Picks" | **Amend the Oath** |
| "USA Goals Tiebreaker" | **The Tiebreak** |
| Tier 1–5 numeric labels | Surface tier name alongside (Favorites · Contenders · Dark Horses · Underdogs · Wildcards) |
| "Crown's chosen" / "Crown's Assignment" (in `wc-pick.jsx` lines 6, 133) | **"Commish's chosen" / "Commish's Assignment"** — Crown→Commish bug fixes |

### Sub-nav rewrite (lands in Plan 1)

Replace the `{% if request.blueprint == 'worldcup' %}` branch in `templates/base.html` (lines ~99–130) with the new pill set:

```jinja
{% if request.blueprint == 'worldcup' %}
<div class="game-subnav subnav-worldcup">
  <div class="container">
    <a class="subnav-game-label d-none d-sm-inline-flex" href="{{ url_for('worldcup.index') }}">
      ⚽ <span class="subnav-label-text">WC 2026</span>
    </a>
    <div class="subnav-pills">
      <a class="subnav-pill {% if request.endpoint == 'worldcup.index' %}active{% endif %}"
         href="{{ url_for('worldcup.index') }}">Hub</a>
      {% if current_user.is_authenticated %}
      <a class="subnav-pill {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
         href="{{ url_for('worldcup.picks') }}">Roster</a>
      {% endif %}
      <a class="subnav-pill {% if request.endpoint in ['worldcup.leaderboard', 'worldcup.player_detail', 'worldcup.team_detail'] %}active{% endif %}"
         href="{{ url_for('worldcup.leaderboard') }}">Board</a>
      <a class="subnav-pill {% if request.endpoint == 'worldcup.schedule' %}active{% endif %}"
         href="{{ url_for('worldcup.schedule') }}">Schedule</a>
      <a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
         href="{{ url_for('worldcup.stats') }}">Stats</a>
      <a class="subnav-pill {% if request.endpoint == 'worldcup.rules' %}active{% endif %}"
         href="{{ url_for('worldcup.rules') }}">Rules</a>
      {% if worldcup_enrollment and worldcup_enrollment.is_admin %}
      <a class="subnav-pill {% if request.endpoint and 'admin' in request.endpoint %}active{% endif %}"
         href="{{ url_for('worldcup.admin_dashboard') }}">
         <i class="bi bi-gear-fill"></i> Admin</a>
      {% endif %}
    </div>
  </div>
</div>
{% elif ... %}
```

CSS mobile compactions (added to `style.css`):

```css
@media (max-width: 575.98px) {
  .subnav-pills { gap: .25rem; }
  .subnav-pill {
    font-size: .72rem;
    padding: .28rem .55rem;
  }
}
```

The `d-none d-sm-inline-flex` class on `.subnav-game-label` hides the label on mobile (already a documented Bootstrap-utility approach; no custom CSS needed).

### Mobile / responsive strategy

- Existing `col-lg-8 / col-lg-4` splits on `picks.html`, `index.html` (current), and `leaderboard.html` are evaluated per-template:
  - **`picks.html`** (Plan 1): preserve `col-lg-8 / col-lg-4` form/sidebar split on desktop; mobile sticky bar pattern preserved
  - **`leaderboard.html`** (Plan 3): preserve `d-none d-md-block` table / `d-md-none` cards split
  - **`index.html`** (Plan 4): single-column mobile-first flow up to `lg`; ≥`lg` may widen leaderboard preview but no sidebar
  - **`player_detail.html`** (Plan 2): centered single-column on all viewports (no sidebar today)
  - **`team_detail.html`** (Plan 2, NEW): mobile-first single-column on all viewports; bundle is mobile-only and desktop falls through naturally

### Process conventions (apply to all 4 plans)

- **Worktree** at `redesign/ccc-worldcup` branched from `main`. Each plan ships its own PR; subsequent plans rebase onto `main` after the prior plan merges
- **PRs `@coderabbitai`-tagged** for explicit CodeRabbit review (continues Spec B's pattern; CodeRabbit caught issues Claude's own review missed)
- **Verification before completion** per Spec A's pattern:
  - `venv/bin/pyright` clean (target: 0 errors in touched files)
  - `ENVIRONMENT=testing venv/bin/python -m pytest tests/` clean
  - Manual visual checklist for the slice's surface — light + dark mode (if applicable), mobile (375px) + desktop, sub-nav active states, key flows clicked through
- **CSS additions follow Layer 1 / Layer 2 split** from Spec A: tokens-only changes in `tokens.css`, components in `style.css`. Spec C is expected to add zero new tokens
- **Avatar pattern** (`user.get_avatar()` inline before display name) preserved everywhere a user is shown — required integration per CLAUDE.md

---

## 6. Plan 1 — My picks + foundation

### Surface
- `picks.html` (3 states: edit form / sealed pre-deadline / post-deadline)
- `_pick_row.html` (partial, used by `picks.html` + `player_detail.html`)
- `_pick_accordion_script.html` (JS only — no markup changes; preserve all DOM hooks)
- `templates/base.html` sub-nav block (rewrite per §5)
- `static/css/style.css` (cross-cutting WC class additions per §5)
- Light chrome pass on `schedule.html`, `groups.html`, `rules.html`

### `picks.html` — three states in one file

The template stays a single file with branching by state. Four design screens collapse here:

| Production state | Design screen mapping |
|---|---|
| `show_edit_form == true` (form, deadline open) | `wc-pick.jsx` (tier cards) + `wc-tiebreak.jsx` (sidebar / mobile bottom bar) |
| Picks submitted, pre-deadline, not editing | `wc-confirmed.jsx` + `wc-roster.jsx` Pre-Lock (sealed but amendable) |
| Post-deadline | `wc-roster.jsx` Live (with drill-down accordion preserved) |

**Edit form key changes**:
- 5 tier cards reskinned with navy surface, red eyebrow ("Tier 1 · Favorites"), tier dot + multiplier chip, country grid below
- Country cards (`.wc-team-card`) restyled flag-forward; group badge as a corner pill; selected state uses red border + filled background per bundle
- Sidebar (`col-lg-4`, sticky on desktop): pick summary list with eyebrow labels; tiebreak input as a hero numeric field with "The Tiebreak" header
- Mobile sticky bottom bar restyled to bundle's pre-lock panel (pick count + countdown + red CTA)
- Counter logic and tier-cap enforcement JS unchanged — DOM hooks preserved per CLAUDE.md "template restyling" rule

**Sealed (pre-deadline) view**:
- Hero collapses to "Sealed. Still amendable." eyebrow + countdown + "Amend the Oath" CTA
- Roster grid renders 9 picks grouped by tier in the new card pattern
- No accordion drill-down (no scoring data yet)

**Post-deadline view**:
- Hero says "The Oath is sealed."
- Existing desktop table + mobile cards reskinned; accordion drill-down behavior preserved (same script, same hooks)
- Total points stays in header; per-pick row points stay in right column

### `_pick_row.html` partial reskin

- Tier cell: `.wc-tier-dot` + tier name eyebrow
- Multiplier cell: `.wc-multiplier-chip`
- Score cell: `.wc-numeral`
- Drill-down accordion: restyled with eyebrow labels and bundle's match-row pattern (flag · score · event chips). Logic untouched.

### Light chrome pass

Deliberately shallow — page-hero alignment + card pattern modernization only.

- All three: `.page-hero` uses `.wc-hero-grad`; numerals upgraded to `.wc-numeral`; eyebrow labels added where section headers benefit; Bootstrap card markup migrates to `.wc-card` where appropriate
- `groups.html`: add anchor IDs (`<section id="group-A">` etc.) so inline group-letter badge links can deep-link
- `schedule.html`: keep existing match-list structure; restyle match rows to bundle's match-row pattern (consistent with `_pick_row.html` accordion); preserve filtering controls
- `rules.html`: keep all content; restyle section blocks with eyebrows; tier pill examples render with new tier dot pattern. No copy changes.

### Tests / verification (Plan 1)

- No new unit tests required (pure visual reskin + CSS additions)
- Manual visual checklist:
  - All 3 picks states (edit / sealed / post-deadline) on mobile + desktop
  - Sub-nav active states for every WC route, mobile-pill no-scroll verification on 375px viewport
  - Schedule / groups / rules quick visual pass
  - Accordion drill-down on post-deadline picks still expands/collapses correctly (regression smoke for `_pick_accordion_script.html`)
- `venv/bin/pyright` clean
- `ENVIRONMENT=testing venv/bin/python -m pytest tests/` — existing 150 tests pass (no logic changes)

### Risks
- Breaking `_pick_accordion_script.html` JS hooks during reskin → mitigated by additive-only class strategy
- "Roster" rename touches a lot of copy → grep carefully for "My Picks" vs the *page* (Roster) vs the *individual pick records* (still "picks" in code/data context)
- Sub-nav rewrite is foundational for Plans 2/3/4 → verification gate must include sub-nav across all WC routes before merge

---

## 7. Plan 2 — Per-rival surfaces

### Surface
- `player_detail.html` reskin (existing `/worldcup/player/<enrollment_id>` route)
- NEW `team_detail.html` + new `/worldcup/team/<int:team_id>` route in `games/worldcup/routes.py`
- Optional `games/worldcup/services/team_detail.py` if ownership helpers warrant a service module

### `player_detail.html` reskin

Maps to `wc-player.jsx`. Existing route logic preserved verbatim — markup + classes change only.

- Hero rebuilt: rival's avatar (gold disk) + display name as title-xl; eyebrow "Rank N" or "Current Leader"; stat grid (Total · Lead · Tiebreak)
- **Lead delta** is new computed data: current rank's delta from rank 1 (or rank N+1's delta from N if leader). Computed in route, not template. Plan 2 introduces the shared helper `_compute_rank_neighbors(enrollment_id)` (in `games/worldcup/routes.py` or a new `games/worldcup/services/ranking.py`) returning `{rank, points, lead_delta_up, lead_delta_down}`. Plan 3 reuses it for the leaderboard "Your Standing" block.
- Roster grid uses Plan 1's reskinned `_pick_row.html`; pre-deadline lock state preserved with new `.wc-card` styling
- Per-pick drill-down accordion preserved (script + DOM hooks unchanged)
- Each pick row gets a "View team →" link deep-linking to `/worldcup/team/<team_id>` — added in Plan 2 (Plan 1 does not reference the team route)
- Back link ("← Back to Leaderboard") restyled to bundle's small back-affordance pattern

### NEW `team_detail` route + template

**Route signature** (in `games/worldcup/routes.py`):

```python
@bp.route('/team/<int:team_id>')
def team_detail(team_id):
    team = db.get_or_404(WorldCupTeam, team_id)
    matches = (WorldCupMatch.query
        .filter(or_(WorldCupMatch.home_team_id == team_id,
                    WorldCupMatch.away_team_id == team_id))
        .order_by(WorldCupMatch.start_time).all())
    score_events = compute_team_score_events(team)   # canonical scoring helper
    deadline_passed = ...                             # existing logic
    ownership = _compute_team_ownership(team_id, deadline_passed)
    user_owns = (current_user.is_authenticated
                 and _current_user_owns(team_id))
    return render_template('worldcup/team_detail.html',
        team=team, matches=matches, score_events=score_events,
        ownership=ownership, user_owns=user_owns,
        deadline_passed=deadline_passed, stage_label=_stage_label)
```

**Public route — no `@login_required`.** Matches access policy of `leaderboard.html` and `stats.html`.

**Two new helpers** (route module or `games/worldcup/services/team_detail.py`):
- `_compute_team_ownership(team_id, deadline_passed)` → `{count: int, percent: float, picker_names: list[str] | None}`. Returns `picker_names = None` pre-deadline (privacy parity per D11)
- `_current_user_owns(team_id) -> bool` — cheap query; only called when authenticated

**Scoring derivation rule**: `team_detail.html` uses `compute_team_score_events()` exclusively for per-match score breakdowns. Stored `total_score` invariant from CLAUDE.md must hold — same canonical helper that powers `_pick_row.html`.

### `team_detail.html` template structure

1. **Hero** — flag (large), team name (title-xl), eyebrow `FIFA code · Group letter · Tier name`, tier dot + multiplier chip, stat grid (Base · ×Mult · Scored)
2. **Ownership ribbon** (post-deadline OR `user_owns`) — red-tinted strip. If `user_owns`: "You Own This Nation" left + "X rosters · Y% of Club" right. If post-deadline + non-owner: "X rosters · Y% of Club" only. Pre-deadline + non-owner: ribbon hidden entirely
3. **Tournament Fixtures** — match log: stage label (via `_stage_label()` SSoT, never `match.stage|title`), date in CT, opponent flag + abbr, result, points awarded for that match. Future matches show "—" for points; "Next" pip on the very next fixture
4. **Path to the Crown** — knockout path indicator: 5 stage segments (Grp · R32 · R16 · QF · SF or applicable). Won segments ✓; current/next red-tinted; future dim. Voice caption: "Projected ceiling if {{ team.fifa_code }} wins out: {{ projected_ceiling }}". Branch on elimination — show "Eliminated · {{ stage }}" caption instead
5. **(Post-deadline only) Who Picked This** — list of enrollment names; each links to `/worldcup/player/<enrollment_id>`. Pre-deadline: section omitted entirely

### Tests (Plan 2)

New file `tests/test_worldcup_team_detail.py`:
- `test_team_detail_returns_200_for_valid_team`
- `test_team_detail_returns_404_for_invalid_team`
- `test_team_detail_public_no_auth_required`
- `test_team_detail_match_log_includes_all_team_fixtures`
- `test_team_detail_score_events_match_canonical_helper` — sum of displayed events == `compute_team_score_events(team)` total (parity invariant)
- `test_team_detail_ownership_hidden_pre_deadline` — `picker_names` is `None`; section omitted
- `test_team_detail_ownership_visible_post_deadline` — picker_names list rendered
- `test_team_detail_user_owns_ribbon` — authenticated user with pick on team sees red-tinted ribbon

Existing `player_detail.html` tests stay green. May add a parity test for `lead_delta` calculation if introduced.

### Risks
- **Score-event parity**: any drift between `team_detail` display and `compute_team_score_events()` would violate the SSoT invariant — guarded by the parity test
- **Privacy regression** on pre-deadline ownership leakage — guarded by the test + the `picker_names = None` invariant
- **Linking**: pick rows getting "View team →" link only after Plan 2 lands; Plan 1 does not reference the team route at all (clean separation)

---

## 8. Plan 3 — Public analytics

### Surface
- `leaderboard.html` reskin + Tier C additions ("Your Standing" hero block, Trend column)
- `stats.html` aggressive restructure via `frontend-design` skill
- `games/worldcup/routes.py` — extend `leaderboard()` payload with rank-neighbor and trend computations; verify `stats()` route remains unchanged structurally

### `leaderboard.html` — Tier C scope

**Strict reskin (always)**:
- New card/row treatment with bundle palette; columns Rank · Player · Points · TB (post-deadline)
- Avatar + display name + linking to `player_detail` preserved
- Row-current-user highlight strengthens with bundle's red-tinted background
- Mobile cards / desktop table responsive split unchanged

**"Your Standing" hero block** (added):
- Renders for authenticated + enrolled users only
- Eyebrow: "Your Standing"
- Big numeral: rank · "of N"
- Right side: Points (Teko numeral) + matchday-trend caption
- Voice-it caption: "X pts from 1st · Y ahead of next" (or appropriate variants for leader / tail)
- Reuses `_compute_rank_neighbors(enrollment_id)` introduced by Plan 2

**Trend column** (added):
- Per-row `+N.N` matchday trend
- Pulls from `WorldCupRankSnapshot` (already shipped by Spec B): `trend = current_score − latest_snapshot_score`
- Renders as `+12.5` (red-bright), `—` (muted), or `-3` (red-bright loss)
- Mobile cards: trend below points line; desktop table: new "Trend" column between Points and TB
- **Gated by `len(snapshots) >= 7`** per D10 — column entirely hidden until 7+ snapshots exist (Spec B's pattern)

**Filter chips deferred** to a future Plan 3.2 per D9.

### `stats.html` aggressive restructure

The implementing agent runs `frontend-design` skill in Plan 3 with the following constraints:

**Hard constraints (do not change):**
- Public service-layer entry points stay: `get_overview_kpis`, `get_country_stats`, `get_tier_stats`, `get_tier_combos` (CLAUDE.md "Stats analytics layer" rule). Template rewrites; service does not.
- Public route — no `@login_required`
- `my_picks` query stays `WorldCupPick.query.join(WorldCupTeam)` shape, never `enrollment.picks` (CLAUDE.md N+1 rule)
- Chart.js stays — no charting library swap
- Stage labels via `_stage_label()` SSoT — never `match.stage|title`
- All existing tests in `tests/test_worldcup_stats.py` continue to pass (service layer unchanged)

**Soft constraints (frontend-design judgment):**
- Tab consolidation permitted and encouraged. 6 tabs (Overview · Selection · Scoring · Tier Performance · Portfolio Impact · Pick Combos) may collapse to 3–4 tabs. The agent decides the cut and justifies it in the PR description
- Tab bar visual treatment aligns with Plan 1's sub-nav pill aesthetic — one consistent "pills" idiom across the WC blueprint
- KPI blocks align with platform `.stat-block` pattern (and Spec B's home variants)
- Chart colors use new WC palette tokens, not hardcoded values
- Hero pattern uses `.wc-hero-grad`
- Voice/copy uses WC vocabulary

This is the only place across all 4 plans that explicitly delegates structural decisions to a downstream skill.

### Tests (Plan 3)

**Leaderboard new tests** in `tests/test_worldcup_leaderboard.py` (new file or extend existing):
- `test_your_standing_block_renders_for_authenticated_enrolled_user`
- `test_your_standing_omitted_for_anonymous`
- `test_lead_delta_calculation` (5-enrollment fixture with known scores)
- `test_trend_column_uses_latest_snapshot` (mock `WorldCupRankSnapshot` rows)
- `test_trend_column_hidden_when_fewer_than_seven_snapshots`
- `test_trend_column_shows_dash_when_no_prior_snapshot_for_user`

**Stats existing tests stay green**: `tests/test_worldcup_stats.py` covers the service layer. If frontend-design's restructure changes tab IDs, route-level tests verifying tab DOM IDs may need updating (implementation cost; not a rewrite).

### Risks
- **Trend column on a sparse leaderboard** (early tournament) reads as a wall of "—" → mitigated by the `>=7 snapshots` gate (Spec B's pattern)
- **Stats restructure** may break user mental model — but no live users (D7), so this is the right time
- **Plan 3 scope creep**: filter chips (Tier D) genuinely valuable but explicitly deferred — spec language must be clear so implementers don't pull them in

---

## 9. Plan 4 — WC Hub migration

### Surface
- NEW `games/worldcup/services/home_context.py` with `build_worldcup_home_context()` dispatcher + 4 builders (`_context_out`, `_context_pre`, `_context_live`, `_context_post`)
- NEW `games/worldcup/templates/worldcup/home_shell.html`
- NEW `games/worldcup/templates/worldcup/_home_out.html`
- NEW `games/worldcup/templates/worldcup/_home_pre.html`
- NEW `games/worldcup/templates/worldcup/_home_live.html`
- NEW `games/worldcup/templates/worldcup/_home_post.html`
- DELETE existing `games/worldcup/templates/worldcup/index.html` (or rename `index_legacy.html` for one-PR grace period — implementer decides)
- `games/worldcup/routes.py` — `index()` route shrinks to a thin dispatcher
- Possibly `games/worldcup/services/voice.py` (state-keyed copy strings)
- Possibly `games/worldcup/services/stage.py` if `_stage_label()` is lifted from `core/main/home_context` to a WC-scoped module

### Service module API

```python
# games/worldcup/services/home_context.py

def build_worldcup_home_context(user: User | None, state: str) -> dict:
    """Dispatcher. State resolved upstream via games/worldcup/services/state.worldcup_state()."""
    if state == 'out':   return _context_out(user)
    if state == 'pre':   return _context_pre(user)
    if state == 'live':  return _context_live(user)
    if state == 'post':  return _context_post(user)
    raise ValueError(f'unknown worldcup state: {state}')
```

### State definitions and per-builder outputs

| Builder | Triggered when | Builds (dict keys for partial) |
|---|---|---|
| `_context_out` | Not enrolled OR not authenticated | `tournament_phase`, `entry_fee`, `total_enrolled`, `top_3_preview`, `deadline_ct` (if pre-tournament), `cta_state` (`'guest'` / `'unenrolled_pre'` / `'unenrolled_live'`) |
| `_context_pre` | Enrolled, deadline not passed | `deadline_ct`, `picks_submitted`, `user_picks` (if submitted), `top_3_preview`, `tournament_phase`, voice copy (submitted vs not) |
| `_context_live` | Deadline passed, group_stage or knockout | `enrollment` + computed rank + lead/down deltas, `user_picks` with score events, `top_5_preview`, `recent_matches`, `trend_payload` (only if `len(snapshots) >= 7`), voice copy keyed by rank tier (leader / chasing / mid / tail) |
| `_context_post` | Tournament complete | `final_enrollment` + final rank, `user_picks` with full season scores, `champion_team`, `top_5_final`, season-summary voice copy |

### Time seam compliance

`now_utc()` from `games/worldcup/services/state` per CLAUDE.md. `WC_FAKE_NOW` env var honored in dev/testing. Builders **must not** call `datetime.now()` directly.

### Reuse, don't duplicate

- Voice copy strings live in `games/worldcup/services/voice.py` (or single dict in `home_context.py`) so partials don't hardcode strings
- Stage labels: `_stage_label()` currently lives in `core/main/home_context` (WC-specific function in cross-game code, per Spec B's introduction). Plan 4 lifts it to `games/worldcup/services/stage.py` and updates `core/main/home_context` to import from there. Plans 2 and 3 import from the **existing** `core/main/home_context` location during their PRs; after Plan 4 merges, all callers update imports as part of the lift (pyright catches missing imports)
- Scoring derivation via `compute_team_score_events()` only; no recomputation in builders

### Per-state partial structure (mobile-first single column)

**`home_shell.html`** (~30 lines):
- Page hero with phase chip + tournament title (using `.wc-hero-grad`)
- Body container that includes `_home_<state>.html` based on context's `state` key
- Footer/quick-links block (Schedule · Groups · Rules — absorbing demoted Schedule/Groups nav items)

**`_home_out.html`** (~80 lines): eyebrow + voice tagline + entry-fee callout; "Join the pool" CTA (auth-aware); tournament-phase teaser; top-3 leaderboard preview (when post-deadline)

**`_home_pre.html`** (~110 lines): picks status block ("Sealed. Still amendable." or "Make your picks before the deadline" + countdown); My Roster preview if submitted; Top-3 leaderboard preview (zeros until kickoff with voice "Awaiting kickoff"); quick links footer

**`_home_live.html`** (~140 lines): Your Standing block (rank, points, lead delta) — same data shape as Plan 3's leaderboard hero; My Roster preview with live scores per pick; trend sparkline (only if `len(snapshots) >= 7`); recent results (3-5 matches); Top-5 leaderboard preview; voice copy keyed by rank tier

**`_home_post.html`** (~100 lines): final standing hero; Champion banner — winning team flag, name, your champion-pick status; final roster review with full season scores; Top-5 final leaderboard preview; season-summary voice ("The Oath is fulfilled" or similar)

### Route changes

Current `worldcup.index()` is ~50 lines of inline state logic. New version is ~15 lines:

```python
@bp.route('/')
def index():
    state = worldcup_state()
    user = current_user if current_user.is_authenticated else None
    context = build_worldcup_home_context(user, state)
    context['state'] = state
    return render_template('worldcup/home_shell.html', **context)
```

Old `index()` body's state-derivation queries get pulled into the per-state builders.

### Migration ordering within Plan 4 (single PR)

1. Add `games/worldcup/services/home_context.py` with all 4 builders + dispatcher + tests
2. Add `home_shell.html` and 4 partials initially returning placeholder content
3. Build out `_home_out.html` (simplest state, fewest deps)
4. Build `_home_pre.html`, `_home_live.html`, `_home_post.html` in sequence
5. Switch `worldcup.index()` to dispatch via the new service
6. Delete old `index.html`
7. Verify all 4 states render correctly via `WC_FAKE_NOW` manual smoke

### Tests (Plan 4)

New file `tests/test_worldcup_home_context.py`:
- `test_state_dispatch_routes_to_correct_builder` (4 tests, one per state)
- `test_context_out_for_anonymous_user`
- `test_context_out_for_authenticated_unenrolled_user`
- `test_context_pre_includes_user_picks_when_submitted`
- `test_context_pre_omits_user_picks_when_not_submitted`
- `test_context_live_computes_rank_with_lead_delta`
- `test_context_live_trend_gated_by_snapshot_count`
- `test_context_post_includes_champion_team`
- `test_now_utc_seam_honored` — set `WC_FAKE_NOW` to a `pre` time, verify dispatcher returns `_context_pre`

Existing `tests/test_worldcup_admin.py` route smoke tests should continue to pass with new route shape.

### Risks
- **State-detection drift**: 5th state from `worldcup_state()` would raise `ValueError` — acceptable; fail loud per CLAUDE.md
- **Voice copy bloat**: state-keyed voice can sprawl — keep in single dict or service module rather than scattered across partials
- **Test fixture complexity**: `live` and `post` need fixtures with enrollments + picks + score events + (optionally) snapshots. Recommend a `conftest.py` fixture builder `worldcup_full_tournament_fixture()` reusable across this plan and any future analytics work

---

## 10. Open questions / known unknowns

None at this time. All Q1–Q8 from the brainstorm are decided and recorded as D1–D11.

---

## 11. Memory + handoff updates after Spec C ships

After all 4 plans merge, update `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/`:

- `project_ccc_redesign.md` — mark Spec C complete; close out the initiative
- `project_ccc_specs_b_c_notes.md` — prune Spec C notes (parallel to how Spec B notes were pruned post-merge); preserve any useful conventions in `CLAUDE.md` instead

CLAUDE.md additions to consider after Spec C ships (do not pre-write — capture during the post-merge `claude-md-improver` pass):

- WC sub-nav structure (Hub · Roster · Board · Schedule · Stats · Rules + Admin)
- Cross-cutting `.wc-*` CSS classes (`.wc-eyebrow`, `.wc-numeral`, `.wc-hero-grad`, `.wc-tier-dot`, `.wc-multiplier-chip`, `.wc-card`)
- WC home_context builder pattern (mirrors Spec B; builder + dispatcher + 4 partials)
- New `/worldcup/team/<id>` route + privacy invariant on pre-deadline ownership data
- "Roster" / "Board" / "Seal the Oath" / "Amend the Oath" / "The Tiebreak" canonical voice mappings
