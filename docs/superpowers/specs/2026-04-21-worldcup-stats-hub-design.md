# Design Spec: World Cup Stats Hub

**Date:** 2026-04-21
**Status:** Approved
**Prototype reference:** `docs/World Cup Stats Hub.html`

---

## Overview

A new analytics dashboard page inside the World Cup Fantasy Pool game. Six tabbed panels give players a rich view into selection statistics, country scoring, tier performance, portfolio impact, and pick overlap data for the 2026 FIFA World Cup.

The high-fidelity HTML prototype in `docs/World Cup Stats Hub.html` is the visual reference. Match it precisely — colors, typography, spacing, and interactions are final.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Auth | Public (no decorators) | Matches leaderboard; analytics are more interesting when shareable |
| Display mode | Charts only | The visual storytelling is the feature; tables would flatten the data |
| Dark mode | `prefers-color-scheme` media query via one JS line | Zero cost; CSS vars already wired |
| Code structure | New `services/stats.py` module | Keeps routes.py thin; mirrors `scoring.py` / `enrollment.py` pattern |
| Tab scope | All 6 tabs in one plan | Spec is complete; no reason to phase |

---

## Files Changed

| File | Change |
|---|---|
| `games/worldcup/services/stats.py` | **New** — 4 query functions |
| `games/worldcup/templates/worldcup/stats.html` | **New** — 6-tab page with Chart.js |
| `games/worldcup/routes.py` | Add `@worldcup_bp.route('/stats')` |
| `static/css/style.css` | Add tab bar + pick bar CSS classes |
| `templates/base.html` | Add "Stats Hub" subnav pill |

---

## Service Layer: `games/worldcup/services/stats.py`

### `get_country_stats(season_year) → tuple[list[dict], int]`

Returns `(country_list, total_players)`.

Fetches `total_players` with one enrollment count query, then loads all `WorldCupTeam` rows and join-counts picks per team from `WorldCupPick` (filtered to enrollments in `season_year`). For each team, calls `compute_team_score_events()` from the existing scoring service and splits events by source:

- **Group sources:** `group_win`, `group_draw`, `advancement`
- **Knockout sources:** `knockout`, `podium`

Multiplies each subtotal by `team.multiplier` to get `group_score` and `ko_score`. Computes `pick_pct` using the `total_players` count from the same function.

Each dict:
```python
{
    'name': str,           # team.display_name
    'flag_emoji': str,     # team.flag_emoji
    'tier': int,           # 1–5
    'multiplier': float,
    'pick_count': int,     # number of enrollments picking this team
    'pick_pct': float,     # pick_count / total_players * 100
    'group_score': float,  # multiplied group points
    'ko_score': float,     # multiplied knockout points
    'total_score': float,  # group_score + ko_score (= team.multiplied_points)
    'is_active': bool,     # not team.is_eliminated
}
```

Teams with zero picks are included with `pick_count=0`, `pick_pct=0.0`. If `total_players` is 0, `pick_pct` is 0.0 for all teams.

### `get_tier_stats(country_stats) → dict[int, dict]`

Pure Python — no DB calls. Iterates `country_stats` grouped by tier.

Returns `{1: {...}, 2: {...}, 3: {...}, 4: {...}, 5: {...}}` where each value is:
```python
{
    'avg_score': float,
    'total_score': float,
    'best_country': str,   # display_name of highest-scoring team in tier
    'best_score': float,
}
```

### `get_overview_kpis(country_stats, total_players) → dict`

No DB calls — all derived from `country_stats` and the `total_players` count returned by `get_country_stats`:

```python
{
    'total_players': int,
    'active_countries': int,    # count of teams with is_active=True
    'top_country_score': float, # max(total_score)
    'top_country_name': str,    # name of top scorer
    'total_pts_awarded': float, # sum of total_score across all teams
}
```

### `get_tier_combos(season_year) → dict[int, list[dict]]`

SQLAlchemy 2.0 self-join on `WorldCupPick`. Season filter goes through the enrollment:

```
WorldCupPick → WorldCupEnrollment (filtered season_year) → team pair self-join
```

Aliased pairs joined on `enrollment_id` with `p1.team_id < p2.team_id` to avoid duplicates. Returns top 5 pairs for tiers **1, 3, 4, 5** (tier 2 excluded — only 1 pick per player, no pairs possible).

Each entry: `{'team_a': str, 'team_b': str, 'count': int, 'pct': float}`.

---

## Route: `games/worldcup/routes.py`

```python
@worldcup_bp.route('/stats')
def stats():
    country_stats, total_players = get_country_stats(SEASON_YEAR)
    tier_stats = get_tier_stats(country_stats)
    kpis = get_overview_kpis(country_stats, total_players)
    combos = get_tier_combos(SEASON_YEAR)

    my_picks = []
    if current_user.is_authenticated:
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()
        if enrollment:
            my_picks = [p.team.display_name for p in enrollment.picks]

    return render_template('worldcup/stats.html',
        country_stats=country_stats,
        tier_stats=tier_stats,
        kpis=kpis,
        combos=combos,
        my_picks=my_picks,
        current_phase=_derive_tournament_phase(),
    )
```

No `@login_required`, no `@enrollment_required`. The `my_picks` list is empty for unauthenticated or non-enrolled users — the template handles this gracefully (no highlight state).

---

## Template: `games/worldcup/templates/worldcup/stats.html`

Extends `base.html`. `body.game-worldcup` class applied via the `{% block body_class %}` mechanism.

### Head block
```html
{% block head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
{% endblock %}
```

### Script block (top of page scripts)
Dark mode detection (single line):
```js
if (window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.body.classList.add('theme-dark');
```

Jinja2 → JS data bridge (no AJAX needed):
```js
const MY_PICKS = {{ my_picks | tojson }};
const COUNTRY_STATS = {{ country_stats | tojson }};
const TIER_STATS = {{ tier_stats | tojson }};
const COMBOS = {{ combos | tojson }};
const KPIS = {{ kpis | tojson }};
```

### Page structure
1. `.page-hero` — title "Stats Hub", phase chip (from `current_phase`), player count subtitle
2. `.wc-stats-tab-bar` (sticky, `top: 93px`) — 6 tab buttons
3. 6 `.wc-stats-panel` divs (only `.active` panel has `display: block`)

### Tab panels (mirror prototype exactly)

| Tab | Key components |
|---|---|
| Overview | 4 `.kpi-block` + tournament progress bar (flex segments, color by phase) |
| Selection | Most/Least Popular cards + Pick Distribution by Tier (pick bar macro) |
| Scoring | Top 16 scoring list (stacked bar per row) + accumulation doughnut |
| Tier Performance | 5 KPI blocks + bar chart (avg score) + doughnut (total pts share) |
| Portfolio Impact | Bubble scatter chart + Helping Most / Disappointing Most lists |
| Pick Combos | 4 cards (T1, T3, T4, T5) with top 5 pairs + progress bars |

### Chart.js lazy init
Charts initialized only when their tab first opens (avoids zero-size canvas):
```js
const chartsInitialized = new Set();
// switchTab() calls initScoringCharts(), initTierCharts(), initImpactCharts()
// only if !chartsInitialized.has(tabId)
```

### Pick highlighting
JS reads `MY_PICKS` array. Elements with matching country names get `.my-pick` class applied, which triggers the gold label color and ★ prefix via CSS.

### Tab persistence
```js
localStorage.setItem('wc_stats_tab', activeTab);
// on load: restore from localStorage or default to 'overview'
```

---

## CSS: `static/css/style.css`

Add under `/* === WORLD CUP FANTASY POOL === */`. Classes verbatim from the spec:

- `.wc-stats-tab-bar` / `.wc-stats-tab-bar-inner` — sticky tab bar container
- `.wc-stats-tab-btn` / `.wc-stats-tab-btn.active` — tab button styles
- `.wc-stats-panel` / `.wc-stats-panel.active` — panel show/hide + fadeInUp animation
- `.wc-pick-bar` / `.wc-pick-bar-label` / `.wc-pick-bar-track` / `.wc-pick-bar-fill` — pick percentage bars
- `.wc-pick-bar.my-pick .wc-pick-bar-label` — gold highlight for user's own picks

---

## Subnav: `templates/base.html`

In the `{% if request.blueprint == 'worldcup' %}` block, after the Leaderboard pill:

```html
<a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
   href="{{ url_for('worldcup.stats') }}">Stats Hub</a>
```

---

## Tier Reference

| Tier | Name | Multiplier | Picks per player |
|---|---|---|---|
| 1 | Favorites | ×1 | 2 |
| 2 | Contenders | ×1.5 | 1 |
| 3 | Dark Horses | ×2.5 | 2 |
| 4 | Underdogs | ×4 | 2 |
| 5 | Wildcards | ×7 | 2 |

Tier 2 excluded from Pick Combos (1 pick per player → no pairs).

---

## Edge Cases

- **Pre-tournament (no scores yet):** All scores are 0. Charts render with zero data. Pick bars still show correctly (pick counts exist even before tournament starts).
- **Zero pick count:** Teams with no picks show `pick_pct=0.0` and appear correctly in Least Popular; excluded from Disappointing Most (requires ≥4 picks).
- **Unauthenticated user:** `MY_PICKS = []` — no highlighting, page otherwise identical.
- **Non-enrolled logged-in user:** Same as unauthenticated for highlight purposes.
