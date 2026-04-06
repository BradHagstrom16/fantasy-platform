# Nav Sub-Navigation Redesign

**Date:** 2026-04-06  
**Status:** Approved

---

## Problem

When a user enters a game (e.g. World Cup), the top navbar collapses all platform-level links (Home, World Cup, Golf Pick 'Em, CFB Survivor) and game-specific links (Dashboard, Leaderboard, Schedule, Groups, My Picks, Rules) into a single flat row. There is no visual hierarchy — the two groups compete for the same space, the bar is crowded, and it's confusing.

---

## Solution

A **two-layer nav**:

1. **Top platform bar** (always visible, unchanged purple/gold palette): Commissioner's Club logo, game switcher links (World Cup / Golf Pick 'Em / CFB Survivor), user dropdown.
2. **Game sub-nav strip** (appears only when inside a game blueprint): A thinner contextual bar below the main nav, dark-themed in the game's palette, containing a clickable game label on the left and horizontal pill-shaped nav links on the right.

---

## Design Details

### Platform Top Bar

- Logo + "The Commissioner's Club" (gold, links to `/`)
- Game switcher: flat links — World Cup, Golf Pick 'Em, CFB Survivor — muted when inactive, white when active blueprint
- Right side: Admin link (platform admins only) + user dropdown
- No game-specific links live here anymore

### Game Sub-Nav Strip

Rendered in `base.html` immediately after `</nav>`, only when `request.blueprint` is a game blueprint.

| Element | Detail |
|---|---|
| Game label | Emoji + short name (e.g. `⚽ WC 2026`). Links to game index. On mobile (< `md` breakpoint), label text is hidden — emoji only. |
| Separator | Thin vertical rule `rgba(255,255,255,.15)` right of the label |
| Pill links | Horizontal flex row. `overflow-x: auto` on mobile so they scroll without wrapping. Active pill: filled background + border in game accent color. |

### Per-Game Palettes

| Game | Sub-bar bg | Active pill accent |
|---|---|---|
| World Cup | `#00122e` (Old Glory navy) | `#BF0A30` (Old Glory red) |
| Golf Pick 'Em | `#001a0d` (Augusta forest) | `#b8993e` (Augusta gold) |
| CFB Survivor | `#0a080f` (Midnight) | `#C5050C` (Badger crimson) |

CSS classes: `.subnav-worldcup`, `.subnav-golf`, `.subnav-cfb`

### Sub-Nav Link Sets

**World Cup:** Dashboard · Leaderboard · Schedule · Groups · My Picks · Rules  
**Golf Pick 'Em:** Standings · Schedule · My Picks  
**CFB Survivor:** Standings · Results · My Picks  

My Picks only renders when `current_user.is_authenticated`.

---

## Files to Change

| File | Change |
|---|---|
| `templates/base.html` | Strip game-specific `{% if blueprint %}` blocks from the `<ul class="navbar-nav me-auto">`. Add new `.game-subnav` block below `</nav>`. |
| `static/css/style.css` | Add `/* === GAME SUB-NAV === */` section with `.game-subnav`, `.subnav-worldcup`, `.subnav-golf`, `.subnav-cfb`, `.subnav-game-label`, `.subnav-pills`, `.subnav-pill`, `.subnav-pill.active` rules. Add mobile overrides under existing `@media` block. |

No Python changes required — all logic is template/CSS only.

---

## Mobile Behavior

- Game label: `<span class="subnav-label-text d-none d-md-inline">WC 2026</span>` — emoji always visible, text hidden below `md`.
- Pills container: `overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none` — horizontal scroll, no visible scrollbar.
- No wrapping — single row at all viewport sizes.

---

## What Is NOT Changing

- Platform nav structure, colors, fonts, brand mark
- Any Python routes, models, or services
- Admin link behavior (platform admin only, right side of top bar)
- Flash message block below the nav

---

## Acceptance Criteria

- [ ] Inside World Cup: top bar shows platform links only; sub-bar shows WC pills with navy/red theming; game label links to `worldcup.index`
- [ ] Inside Golf: sub-bar shows golf pills with forest/gold theming; game label links to `golf.index`
- [ ] Inside CFB: sub-bar shows CFB pills with midnight/crimson theming; game label links to `cfb.index`
- [ ] On Home / Auth pages: no sub-bar rendered
- [ ] Mobile (< 768px): game label text hidden, emoji visible, pills scroll horizontally
- [ ] Active pill reflects current `request.endpoint`
- [ ] No regression in platform nav behavior
