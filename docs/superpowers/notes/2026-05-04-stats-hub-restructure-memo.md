# Stats Hub Restructure — Design Memo

**Date:** 2026-05-04 · **For:** Spec C Plan 3 §C, Task 6.
**Constraints:** service shapes verbatim (`get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`); public route, no `@login_required`; Chart.js retained; `_stage_label` import unmoved.

## 1. Tab cut — 6 → 3

| New id | Label | Collapses |
|---|---|---|
| `tab-board` | **The Board** | `overview` + `scoring` |
| `tab-field` | **The Field** | `selection` + `impact` |
| `tab-tiers` | **By Tier** | `tiers` + `combos` |

Each pair was two views of one question: *How is the tournament going?* (Board), *Who did the field trust, and was it right?* (Field), *Did the multiplier ladder pay off?* (By Tier). Three pills also fit a 375px viewport without scroll under the existing `.subnav-pills` rule; six did not.

## 2. Per-tab structure

**The Board** (`#tab-board`)
1. KPI strip — 4 `.stat-block` cards (players · active countries · top country score · total pts awarded).
2. Tournament progress bar (`#progress-bar-wrap`).
3. Top Scorers list (`#scoring-list`) + Pts Breakdown donut (`#ch-accum`) + summary (`#accum-summary`).

**The Field** (`#tab-field`)
1. Most Popular / Least Popular bars (`#bars-popular`, `#bars-unpopular`).
2. Popularity-vs-Score scatter (`#ch-scatter`), full width.
3. Side rails: Carrying the Field (`#help-list`) + Dead Weight (`#hurt-list`).

**By Tier** (`#tab-tiers`)
1. Tier KPI strip (`#tier-kpis`).
2. Avg score bar (`#ch-tier-bar`) + Total points donut (`#ch-tier-donut`).
3. Pick Distribution by Tier — `#bars-t1`…`#bars-t5`.
4. Pair combos (`#combos-t1`/`t3`/`t4`/`t5`).

## 3. Hero treatment

Single `.page-hero.wc-hero-grad` (Plan 1 utility, wins on `(0,0,2,0)`):
- `.phase-chip` — copy from `_stage_label`, never `current_phase|title`.
- Eyebrow `<small>`: "Public dossier".
- `<h1>` "**The Field Office**" (replaces "Stats Hub").
- Sub-line: `{{ kpis.total_players }} oaths sealed · {{ kpis.active_countries }} nations standing`.
- No CTA. Logged-out viewers see the same hero — `MY_PICKS = []` is a clean no-op for every `★` highlight.

## 4. Tab bar treatment

Reuse Plan 1's `.subnav-pills` / `.subnav-pill` — one consistent pills idiom across WC. In-page container, not the global subnav: `<div class="wc-stats-pills"><div class="subnav-pills">…</div></div>` with `--subnav-accent: var(--wc-red)` and `--subnav-accent-rgb: 191, 10, 48` set inline so the active pill paints red.

**DOM IDs preserved** (JS reads them): `#progress-bar-wrap`, `#scoring-list`, `#ch-accum`, `#accum-summary`, `#bars-popular`, `#bars-unpopular`, `#bars-t1`–`#bars-t5`, `#tier-kpis`, `#ch-tier-bar`, `#ch-tier-donut`, `#ch-scatter`, `#help-list`, `#hurt-list`, `#combos-t1`/`t3`/`t4`/`t5`.

**DOM IDs renamed:** old `#tab-overview`/`selection`/`scoring`/`tiers`/`impact`/`combos` → `#tab-board`/`field`/`tiers`. `TAB_IDS` becomes `['board','field','tiers']`; `localStorage` key bumps to `wc_stats_tab_v2` to invalidate stale values.

## 5. Chart palette mapping

All hex literals removed — chart code reads CSS custom properties via `getComputedStyle(document.documentElement).getPropertyValue('--token').trim()` at init.

| Chart slot | Token |
|---|---|
| `#ch-accum` Group slice | `--wc-navy` (was `#002868`) |
| `#ch-accum` Knockout slice | `--wc-red` (was `#BF0A30`) |
| `#ch-tier-bar`, `#ch-tier-donut` per-tier fills | `--wc-tier1`…`--wc-tier5` |
| `#ch-scatter` bubble fill/border | `--wc-tier{N}` + `BB` alpha |
| Axis grid / ticks | `--text-muted`, `--border` |
| Chart font | `--font-display` (was `'Teko'`) |

`TC`/`TN`/`TM` lookup dicts stay; `TC` is populated from tokens at init.

## 6. Voice + copy diffs

| Current | New |
|---|---|
| "Stats Hub" h1 | "The Field Office" |
| "Full tournament analytics" | "Oaths sealed · nations standing" |
| Tab "Overview" | "The Board" |
| Tabs "Selection" + "Portfolio Impact" | "The Field" |
| Tabs "Tier Performance" + "Pick Combos" | "By Tier" |
| "Selection Stats" intro | "Who the field trusted" |
| "Pick Combos & Overlap" | "Tier Pairs" |
| "Picks locked Jun 11" | "Oaths sealed Jun 11" |
| "🟢 Helping Most Players" | "Carrying the Field" |
| "🔴 Disappointing Most" | "Dead Weight" |

Tier names already match spec — unchanged.

## 7. Risks — JS hooks the rewrite must preserve

1. **`switchTab(id)` lazy init.** Gate keys and `setTimeout` branches must move with the rename: Board triggers scoring charts (`'board'`), Field triggers impact (`'field'`), By Tier keeps `'tiers'` (now also covers donut + bar). Update both in lockstep.
2. **`localStorage` key bump to `wc_stats_tab_v2`** — old `wc_stats_tab` holds `'overview'` etc. that no longer resolve.
3. **`MY_PICKS = []` is correct for anon viewers.** Every `MY_PICKS.includes(...)` branch evaluates false. Do NOT add `if (MY_PICKS.length)` guards that suppress the bars themselves — the public dossier must render fully for logged-out users.
4. **`TAB_IDS` order pairs positionally** with `document.querySelectorAll('.wc-stats-tab-btn')`. Buttons must emit in array order (`board`, `field`, `tiers`).
5. **`Chart.defaults.font.family`** is currently set inside each `init*` — hoist to script top so it isn't re-applied per tab switch.
6. **Inline tier hex outside charts** (`pbarHtml`, `tierHeader`, `TC[t] + 'BB'`) routes through the token-populated `TC` lookup; no per-call-site substitutions.
7. **`current_phase`** is server-rendered into JS as a literal in `renderProgressBar()`. Keep that, but pipe the human-readable phase label through `_stage_label` in the route context dict (not the template) to avoid re-introducing `|title` mangling.
