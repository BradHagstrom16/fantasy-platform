# Handoff: World Cup Fantasy Pool — Stats Hub

## Overview

This is a design reference for the **Stats Hub** — a new analytics dashboard page inside the existing World Cup Fantasy Pool game on The Commissioner's Club platform. It gives the game's 20–50 players a rich, tabbed view into selection statistics, country scoring, tier performance, portfolio impact, and pick overlap data for the 2026 FIFA World Cup.

---

## About the Design Files

The file `World Cup Stats Hub.html` in this folder is a **high-fidelity HTML prototype** — a design reference, not production code to copy directly.

Your task is to **recreate this design inside the existing `fantasy-platform` Flask/Jinja2 codebase** (`BradHagstrom16/fantasy-platform`), using the established patterns: Jinja2 templates, Bootstrap 5.3, the platform's `static/css/style.css` design system, and the existing `games/worldcup/` blueprint. The sample data in the prototype should be replaced with real queries from the database via the existing `games/worldcup/services/` layer.

---

## Fidelity

**High-fidelity.** Colors, typography, spacing, component styles, and interactions are all final and should be matched precisely. The prototype uses the exact same design tokens already defined in `static/css/style.css` — the World Cup overrides (`body.game-worldcup`) and all existing component classes apply directly.

---

## Where It Lives in the Codebase

| Item | Path |
|------|------|
| New template | `games/worldcup/templates/worldcup/stats.html` |
| Route to add | `games/worldcup/routes.py` → `@worldcup.route('/stats')` |
| Subnav pill | `templates/base.html` → add "Stats Hub" pill to the `worldcup` subnav block |
| CSS (already exists) | `static/css/style.css` |
| Chart.js (add to template) | `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js` |

---

## Page Structure: 6 Tabs

The page uses a **sticky tab bar** (below the existing subnav) to show one panel at a time. Each tab is a button that swaps visible content — no page reload. Charts lazy-initialize the first time their tab is opened to avoid zero-size canvas issues.

### Tab 1 — Overview

**Purpose:** At-a-glance tournament status.

**Layout:**
- Page hero (existing `.page-hero` class, `body.game-worldcup` colors): title "Stats Hub", phase chip showing current tournament round, subtitle with player count + picks locked
- 4 KPI blocks in a `row g-3` grid (`.kpi-block` class, already in style.css):
  - Players Enrolled (border-top: `--game-primary`)
  - Teams Still Active (border-top: `--game-accent`)
  - Top Country Score (border-top: `--wc-tier3`)
  - Total Pts Awarded (border-top: `--wc-tier5`)
- Tournament progress bar: a single-row flex container divided into labeled segments (Group Stage, R32, R16, QF, SF, Final) — completed phases in `--game-primary`, current phase highlighted with `--platform-accent` border + gold text, future phases in `--bg-muted`

**Data needed:**
```python
total_players         # enrollment count
active_countries      # countries not yet eliminated
top_country_score     # max(multiplied_score) across all countries
total_pts_awarded     # sum of all multiplied scoring events
current_phase         # e.g. "Semifinals"
```

---

### Tab 2 — Selection Stats

**Purpose:** How the field distributed picks — popularity rankings and per-tier breakdowns.

**Layout:**
- Section heading + subtitle
- Two side-by-side cards (`col-lg-6`):
  - **Most Popular Picks** — top 10 countries across all tiers, sorted by `picks / total_players * 100`
  - **Least Popular Picks** — teams with ≤4 picks (or bottom 8), sorted ascending
- Full-width card: **Pick Distribution by Tier** — one sub-section per tier (T1–T5), each showing all countries in that tier as horizontal pick-percentage bars

**Pick bar component** (build as a reusable macro):
```
Country name + tier badge | [filled bar] | XX%
Bar color = tier color (see Design Tokens below)
Bar height: 7px, border-radius: 4px
Bar fill = (country_pct / max_pct_in_list) * 100%
```

**Tier section header:** tier badge + tier name + multiplier label (e.g. "T3 · Dark Horses  ×2.5 multiplier")

**Data needed:**
```python
for each country:
    pick_count        # how many enrollments selected this country
    pick_pct          # pick_count / total_players * 100
    tier              # 1–5
```

---

### Tab 3 — Scoring

**Purpose:** Country scoring leaderboard with group vs. knockout breakdown.

**Layout:**
- Two columns: `col-xl-8` (scoring list) + `col-xl-4` (accumulation donut + summary)

**Scoring list** (top 16 countries by total multiplied score):
```
[rank] | [name] [tier badge] [SF badge if active] | [stacked bar] | [total pts]
Stacked bar: navy segment = group_score width, red segment = ko_score width
Bar height: 5px
Below bar: "Grp: XX · KO: XX" in Teko 0.68rem muted
```

**Accumulation donut** (Chart.js doughnut):
- Labels: "Group Stage", "Knockout Rounds"
- Colors: `#002868` (navy), `#BF0A30` (red)
- Below chart: summary rows showing Group total, Knockout total, Grand total

**Data needed:**
```python
for each country:
    group_score       # sum of (match result base pts + advancement base pts) * multiplier
    knockout_score    # sum of (knockout round base pts) * multiplier
    total_score       # group_score + knockout_score
    is_active         # still in tournament (True/False)
```

---

### Tab 4 — Tier Performance

**Purpose:** Compare average performance across the 5 tiers.

**Layout:**
- 5 KPI blocks in a row (one per tier, `col-6 col-md` each), border-top = tier color, showing avg multiplied score + best country name + their score
- Two side-by-side charts:
  - **`col-lg-7`:** Bar chart — avg multiplied score per tier (bars colored by tier color)
  - **`col-lg-5`:** Doughnut chart — total pts share by tier (slices colored by tier color)

**Data needed:**
```python
for each tier (1–5):
    avg_score         # mean of total_score across all countries in tier
    total_score       # sum of total_score across all countries in tier
    best_country      # country with highest total_score in tier
    best_score        # that country's total_score
```

---

### Tab 5 — Portfolio Impact

**Purpose:** Identify which countries are "carrying" the field, which are hidden gems, and which are deadweight.

**Layout:**
- `col-xl-8`: Bubble scatter chart (Chart.js bubble type)
  - X-axis: % of players who picked the country (0–75%)
  - Y-axis: multiplied points scored
  - Bubble radius: `Math.max(5, Math.sqrt(pick_count) * 3.2)`
  - Datasets split by tier (5 datasets), each tier's color
  - Dashed quadrant lines at x=37%, y=50pts
  - Quadrant labels: "High demand, high return" (top-right), "Hidden gem" (top-left), "Deadweight" (bottom-right), "Longshot" (bottom-left)
- `col-xl-4`: Two stacked cards:
  - **Helping Most Players** — top 5 by `pick_count * total_score` (impact score)
  - **Disappointing Most** — bottom 5 by `total_score / pick_count` ratio (among countries with ≥4 picks)

**Data needed:** Same as Selection + Scoring combined.

---

### Tab 6 — Pick Combos

**Purpose:** Show the most common 2-team pairings within each tier.

**Layout:**
- 4 cards in a 2×2 grid: Tier 1 Pairs, Tier 3 Pairs, Tier 4 Pairs, Tier 5 Pairs (Tier 2 is pick-1 so no pairs)
- Each card lists top 5 combos:
  ```
  [Team A] + [Team B]    N players  XX% of field
  [thin progress bar showing count / max_count]
  ```

**Data needed:**
```python
# For each tier with pick_count > 1:
# Query all enrollment pick pairs within that tier
# Count occurrences of each (country_a, country_b) combination
# Return top 5 sorted by count desc
SELECT c1.name, c2.name, COUNT(*) as n
FROM picks p1
JOIN picks p2 ON p1.enrollment_id = p2.enrollment_id AND p1.country_id < p2.country_id
JOIN countries c1 ON p1.country_id = c1.id
JOIN countries c2 ON p2.country_id = c2.id
WHERE c1.tier = X AND c2.tier = X
GROUP BY c1.id, c2.id
ORDER BY n DESC
LIMIT 5
```

---

## Interactions & Behavior

### Tab Switching
- Tab bar is sticky below the subnav (approx. `top: 93px` — adjust if navbar height differs)
- Clicking a tab hides all panels (`display:none`) and shows the active one (`display:block`)
- Active tab button has `border-bottom: 2px solid var(--game-accent)` and heavier font weight
- Active tab is persisted to `localStorage` key `wc_stats_tab` so it survives refresh
- Charts (Scoring, Tier Performance, Portfolio Impact tabs) must be initialized **after** their panel becomes visible — pass `maintainAspectRatio: false` and give canvas containers explicit `height` in CSS

### "Highlight My Picks" Feature
In the prototype this is a Tweaks panel control. In production, **automatically highlight the logged-in user's picks** if they're enrolled:
- Pick bars for the user's selected countries get a gold label color (`--platform-accent`) and a ★ prefix
- Scoring list rows for their countries get a subtle gold background tint
- Pick combo rows where both teams match their picks get a "★ Your picks" label

### Dark Mode
The prototype supports dark mode via `body.theme-dark`. In the platform, respect the user's system preference or add a toggle to the page — the CSS vars are already wired.

### Chart Tooltips
All Chart.js charts use Teko font. Tooltip format:
- Donut: ` {label}: {value} pts`
- Bar: ` {value} avg pts`
- Bubble: ` {country name}: {x}% picked · {y} pts`

---

## Design Tokens

These are all already defined in `static/css/style.css` under `body.game-worldcup`:

| Token | Value | Usage |
|-------|-------|-------|
| `--game-primary` | `#002868` | Navy — primary actions, group score bars |
| `--game-primary-dark` | `#001040` | Hero background |
| `--game-primary-light` | `#1a4890` | Hover states |
| `--game-accent` | `#BF0A30` | Red — knockout bars, active tab indicator |
| `--platform-accent` | `#D4A820` | Gold — highlighted picks, ★ markers |
| `--wc-tier1` | `#D97706` | Amber — Tier 1 Favorites |
| `--wc-tier2` | `#4B7399` | Steel blue — Tier 2 Contenders |
| `--wc-tier3` | `#B45309` | Bronze — Tier 3 Dark Horses |
| `--wc-tier4` | `#0D7377` | Teal — Tier 4 Underdogs |
| `--wc-tier5` | `#9333EA` | Purple — Tier 5 Wildcards |
| `--bg-page` | `#F5F3F0` | Page background |
| `--bg-card` | `#FFFFFF` | Card background |
| `--bg-muted` | `#EDEBF4` | Muted surfaces, bar tracks |
| `--text-primary` | `#1C1730` | Body text |
| `--text-muted` | `#8A849B` | Labels, secondary text |
| `--border` | `#D8DDE8` | Card/row borders |

### Typography
| Use | Font | Weight | Size | Transform |
|-----|------|--------|------|-----------|
| Page headings (h1–h3) | Teko | 700 | 1.75–2.8rem | uppercase |
| Tab labels, card headers | Teko | 500–600 | 0.78–1rem | uppercase, 0.07em spacing |
| KPI values | Teko | 700 | 2.5rem | — |
| KPI labels | Teko | 500 | 0.78rem | uppercase, 0.1em spacing |
| Country names in bars/lists | Teko | 600 | 0.92–1rem | — |
| Tier badges | Teko | 700 | 0.68rem | uppercase |
| Body/subtitles | Newsreader | 400 | 0.9rem | — |
| Score values | Teko | 700 | 1.1rem | — |

### Spacing & Radius
- Card padding: `1.5rem`
- Card border-radius: `--radius-lg` = `0.875rem`
- Section gap between cards: `1.5rem` (Bootstrap `g-4`)
- Tab bar padding: `0.7rem 1.15rem` per tab
- KPI block padding: `1.25rem 1rem`

---

## Existing Components to Reuse

These classes already exist in `static/css/style.css` — use them directly:

| Class | Component |
|-------|-----------|
| `.page-hero` | Dark navy hero section with dot pattern overlay |
| `.kpi-block` | Stat block with colored top border |
| `.tier-badge` / `.tier-badge-1` through `5` | Colored pill per tier |
| `.table-worldcup` | Navy-header table for WC game |
| `.stat-block` | Centered stat card |

---

## New CSS to Add

Add these classes to `static/css/style.css` under the `/* === WORLD CUP FANTASY POOL === */` block:

```css
/* Stats Hub — Tab Bar */
.wc-stats-tab-bar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 93px; /* adjust if navbar + subnav heights differ */
  z-index: 900;
  overflow-x: auto;
  scrollbar-width: none;
}
.wc-stats-tab-bar::-webkit-scrollbar { display: none; }
.wc-stats-tab-bar-inner { display: flex; min-width: max-content; }

.wc-stats-tab-btn {
  font-family: 'Teko', sans-serif;
  font-weight: 500;
  font-size: .82rem;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: .7rem 1.15rem;
  white-space: nowrap;
  cursor: pointer;
  transition: color .15s, border-color .15s;
}
.wc-stats-tab-btn:hover {
  color: var(--game-primary);
  border-color: var(--game-primary-light);
}
.wc-stats-tab-btn.active {
  color: var(--game-primary);
  border-color: var(--game-accent);
  font-weight: 700;
}

/* Stats Hub — Tab Panels */
.wc-stats-panel { display: none; }
.wc-stats-panel.active { display: block; animation: fadeInUp .22s ease both; }

/* Stats Hub — Pick Bars */
.wc-pick-bar { margin-bottom: .55rem; }
.wc-pick-bar-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'Teko', sans-serif;
  font-size: .92rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: .18rem;
  gap: .5rem;
}
.wc-pick-bar-track {
  height: 7px;
  background: var(--bg-muted);
  border-radius: 4px;
  overflow: hidden;
}
.wc-pick-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width .55s cubic-bezier(.4,0,.2,1);
}
/* Highlighted (user's own pick) */
.wc-pick-bar.my-pick .wc-pick-bar-label { color: var(--platform-accent); font-weight: 700; }
```

---

## Jinja2 Route Skeleton

```python
# games/worldcup/routes.py

@worldcup.route('/stats')
def stats():
    from games.worldcup.services.scoring import get_country_scores
    from games.worldcup.models import Enrollment, Pick

    enrollment = get_current_enrollment()  # None if not logged in / not enrolled

    # Country scoring data
    country_scores = get_country_scores()  # returns list of dicts with keys:
    # name, tier, multiplier, group_score, ko_score, total_score, is_active, pick_count, pick_pct

    # Tier summary
    tier_stats = compute_tier_stats(country_scores)  # avg, total, best per tier

    # Pick combos
    tier_combos = get_tier_combos()  # top 5 pairs for tiers 1, 3, 4, 5

    return render_template('worldcup/stats.html',
        country_scores=country_scores,
        tier_stats=tier_stats,
        tier_combos=tier_combos,
        my_picks=[p.country.name for p in enrollment.picks] if enrollment else [],
        total_players=Enrollment.query.filter_by(game_id=...).count(),
        current_phase='Semifinals',  # or derive from match schedule
    )
```

---

## Subnav Update

In `templates/base.html`, inside the `{% if request.blueprint == 'worldcup' %}` subnav block, add:

```html
<a class="subnav-pill {% if request.endpoint == 'worldcup.stats' %}active{% endif %}"
   href="{{ url_for('worldcup.stats') }}">Stats Hub</a>
```

Place it after the "Leaderboard" pill.

---

## Assets

No external image assets. All icons are Bootstrap Icons (already loaded via CDN in `base.html`). Charts are rendered by Chart.js — add this script tag to the template's `{% block head %}`:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
```

---

## Files in This Package

| File | Description |
|------|-------------|
| `World Cup Stats Hub.html` | Full high-fidelity HTML prototype. Open in a browser to see the finished design. Use dark mode + Charts mode for the intended look. |
| `README.md` | This document. |

---

*Design by The Commissioner's Club Design System. Prototype built April 2026.*
