# Group C1 — UI/Content Tweaks Handoff
## Fantasy Platform — World Cup Launch Readiness

**Session date:** April 12, 2026
**Phase:** Pre-launch UI polish (Group C1 of the enhancement plan)
**Executed by:** Claude Code (Opus recommended — touches 8+ templates across the platform)

---

## Context

After Group A (bugs) and Group B (features), this handoff delivers six low-risk UI/content improvements identified during Brad's human end-to-end test. These are all template and CSS changes — **no models, no migrations, no new routes, no new Python files.**

The World Cup is the flagship game for launch. People will be joining the site specifically to play it. The platform home and login pages should reflect that — World Cup front and center, not buried as one of three equal cards.

**Key constraint:** `flag_emoji` already exists as a `@property` on `WorldCupTeam` (added in Group B). All flag work here is wiring that existing property into additional template surfaces.

---

## Scope

### Files to Modify

```
# World Cup templates
games/worldcup/templates/worldcup/rules.html              # Item 1: remove "Base" column
games/worldcup/templates/worldcup/picks.html               # Items 2, 3, 5: hide confederation, add group, add flags
games/worldcup/templates/worldcup/player_detail.html       # Items 2, 3, 5: hide confederation, add group, add flags
games/worldcup/templates/worldcup/schedule.html            # Item 5: add flags to team names
games/worldcup/templates/worldcup/groups.html              # Item 5: add flags to team names
games/worldcup/templates/worldcup/index.html               # Item 4: edit picks button contrast

# Platform templates
core/main/templates/main/index.html                        # Item 6: WC prominence on home
core/auth/templates/auth/login.html                        # Item 6: WC prominence on login

# Platform route (minor)
core/main/routes.py                                        # Item 6: restructure games list for WC prominence

# Styles
static/css/style.css                                       # Item 4, 6: button styling, featured game card
```

### Files NOT Modified

```
models/                          # No schema changes
games/worldcup/models.py         # flag_emoji already exists
games/worldcup/routes.py         # No route changes
migrations/                      # No migrations
```

---

## Item 1: Remove "Base" Column from Rules Page

### Problem

The Points Per Achievement by Tier matrix table on the rules page has a "Base" column that is redundant with the T1 column (T1 multiplier is ×1, so Base = T1 values). It adds visual noise.

### Fix

In `games/worldcup/templates/worldcup/rules.html`, in the Points Per Achievement matrix table:

- Remove the `<th class="text-center">Base</th>` column header
- Remove the `<td class="text-center">{{ base }}</td>` cell from each row in the matrix loop

The matrix currently has columns: Achievement | Base | T1 ×1 | T2 ×1.5 | T3 ×2.5 | T4 ×4 | T5 ×7

After: Achievement | T1 ×1 | T2 ×1.5 | T3 ×2.5 | T4 ×4 | T5 ×7

**Also** check the Group Stage Scoring and Knockout Stage Scoring tables on the same page — they have "Base Points" as a column header. Rename these to just "Points" since the multiplier context is in the matrix, not in those tables. This is cosmetic only — don't remove the column, just rename the header text.

**Skill prescription:** Use `frontend-design` skill when modifying this template.

---

## Item 2: Hide Confederation from Pick Summary

### Problem

The confederation label (e.g., "CAF", "UEFA", "AFC") appears next to country names on the pick form team cards and on the read-only pick summary (`player_detail`). It's noise that doesn't help with decision-making — group letter is far more useful.

### Fix

**On the pick form** (`picks.html`): In the `.wc-team-card` each team currently shows:
```html
<span class="team-meta">
  <span>Group {{ team.group_letter }}</span>
  <span>&middot;</span>
  <span>{{ team.confederation }}</span>
</span>
```

Remove the middot separator and the confederation span. Keep only the group:
```html
<span class="team-meta">
  <span>Group {{ team.group_letter }}</span>
</span>
```

**On the read-only pick summary** (`player_detail.html`): Find where confederation is displayed next to each pick and remove it. Keep group letter if present; add it if not (see Item 3).

---

## Item 3: Show Group Next to Country on Pick Summary

### Problem

The pick summary (both the read-only view on `player_detail.html` and the summary sidebar on the pick form `picks.html`) doesn't show which group a country is in. Group context helps when evaluating picks.

### Fix

**Pick form sidebar (`picks.html`):** The JavaScript-driven pick summary sidebar (`#summaryList`) renders selected teams dynamically. When a team is selected, the summary should show the flag emoji, team name, and group letter. Claude Code: inspect the `updateSummary()` JavaScript function and modify it to include `Group X` in the summary text. The `data-*` attributes on `.wc-team-card` may need to be extended to carry `data-group` so the JS can read it.

**Read-only view (`player_detail.html`):** The picks table shows team name and tier. Add group letter as a subtle label — e.g., `{{ pick.team.flag_emoji }} {{ pick.team.display_name }} <small class="text-muted">Group {{ pick.team.group_letter }}</small>`.

---

## Item 4: Edit Picks Button Contrast on WC Index

### Problem

The "Edit Picks" button on the WC game index uses `btn-outline-secondary` — a ghost/outline style that blends into the background. The "Edit My Picks" button on the picks page uses `btn-game btn-lg` — solid, high-contrast, clearly a primary CTA. They should match.

### Fix

In `games/worldcup/templates/worldcup/index.html`, find the Edit Picks button in the "You're All Set" card:

```html
<a href="{{ url_for('worldcup.picks') }}" class="btn btn-outline-secondary">
  <i class="bi bi-pencil me-1"></i>Edit Picks
</a>
```

Change to use the same treatment as the picks page button:

```html
<a href="{{ url_for('worldcup.picks', edit=1) }}" class="btn btn-game px-4">
  <i class="bi bi-pencil-square me-1"></i>Edit My Picks
</a>
```

Note: this should also link to `?edit=1` so it goes directly to the edit form, not the read-only view (consistent with Group A's `?edit=1` pattern).

**Skill prescription:** Use `frontend-design` skill to verify the button visually matches the picks page CTA in weight and presence. Claude Code can use the `playwright` plugin to screenshot both states for comparison.

---

## Item 5: Flag Emoji on Additional Surfaces

### Problem

Flag emojis appear on the leaderboard and "My Roster" widget (added in Group B), but not on the schedule, group standings, picks form, or read-only pick views.

### Fix

The `flag_emoji` property already exists on `WorldCupTeam`. Wire it into these templates:

**Schedule page (`schedule.html`):** Each match card currently shows:
```html
<span class="match-team home">{{ m.home_team.display_name if m.home_team else 'TBD' }}</span>
```

Change to:
```html
<span class="match-team home">{% if m.home_team %}{{ m.home_team.flag_emoji }} {{ m.home_team.display_name }}{% else %}TBD{% endif %}</span>
```

Apply the same pattern to the away team span. Apply to both the group stage section and all knockout round macros (`render_stage`).

**Group standings page (`groups.html`):** Each country row in the group table should show `{{ team.flag_emoji }}` before the team name. Claude Code: read the current template to find the exact element — it likely renders team names in a `<td>` within a standings table per group.

**Pick form (`picks.html`):** Each `.wc-team-card` currently shows `{{ team.display_name }}` inside `.team-name`. Prepend with `{{ team.flag_emoji }}`:
```html
<span class="team-name">{{ team.flag_emoji }} {{ team.display_name }}</span>
```

**Read-only pick view (`player_detail.html`):** Each row in the picks table should show `{{ pick.team.flag_emoji }}` before the team name (this overlaps with Item 3 — implement both together).

**Pick summary sidebar JS (`picks.html`):** The JavaScript `updateSummary()` function builds the summary list dynamically. Extend the team card `data-*` attributes to include `data-flag` so the JS can render flag emoji in the summary. If the JS currently uses `textContent`, switch to `innerHTML` or build DOM nodes that include the emoji.

---

## Item 6: World Cup Front and Center on Platform Home + Login

### Problem

The platform home page shows three game cards in an equal grid. The login page has no game-specific messaging. People joining the site are coming to play the World Cup game — it should be the dominant visual element, not one of three equal cards.

### Fix

This is the one item where Claude Code + `frontend-design` skill should have creative latitude. The direction is clear; the exact execution is up to Front End Design. Here's the intent:

**Platform home (`core/main/templates/main/index.html`):**

- The World Cup card should be a **featured/hero card** — visually larger, more prominent, separated from the other games. Think: full-width or 2/3-width card at the top with a strong CTA ("Join the 2026 World Cup Pool"), then smaller cards below for Golf and CFB.
- The existing hero section ("Your Fantasy Games, All in One Place") is fine but the World Cup CTA should be the most prominent action on the page, especially for unauthenticated users.
- For authenticated users who haven't enrolled in WC: the featured card should drive them to join.
- For authenticated users who are enrolled: the featured card should link them into the game.

**Platform route (`core/main/routes.py`):**

The current `index()` route builds a `games` list with equal-weight dicts. Restructure to separate the "featured" game from the rest:

```python
featured_game = {
    'name': '2026 FIFA World Cup',
    'emoji': '⚽',
    'description': 'Pick 9 national teams across 5 tiers. Points accumulate as your teams win and advance.',
    'url': url_for('worldcup.index'),
    'featured': True,
}

other_games = [
    {'name': 'Golf Pick \'Em', 'emoji': '⛳', ...},
    {'name': 'CFB Survivor Pool', 'emoji': '🏈', ...},
    ...
]
```

Pass both `featured_game` and `other_games` to the template. The template renders the featured game as a hero card and the others as the standard grid below.

**Login page (`core/auth/templates/auth/login.html`):**

Add a small, tasteful World Cup callout below or near the login form. Something like "Log in to join the 2026 World Cup Fantasy Pool" with a soccer ball emoji. This should be subtle — not a full hero — but enough to reinforce why someone is signing up. If the user arrived via `/login?next=/worldcup/...`, the messaging should be contextually aware (Claude Code: check if `request.args.get('next', '')` starts with `/worldcup` and adjust the callout accordingly).

**Skill prescription:** Use `frontend-design` skill for all of Item 6. Give it creative latitude on card layout, colors, and typography within the established platform palette (royal purple + gold). The WC card should use the WC palette accents (Old Glory navy `#00122e`, Old Glory red `#BF0A30`) to visually distinguish it from the platform chrome.

**Important:** This is temporary prominence for the WC launch. After the tournament, Brad will revert to a more balanced layout. Don't over-engineer — keep it easy to undo. A CSS class like `.game-card--featured` that can be removed later is ideal.

---

## Build Order

These items are independent and can be done in any order, but this sequence minimizes rework:

1. **Item 1** — Rules page "Base" column removal (5 min, zero risk)
2. **Item 2** — Hide confederation (5 min, template-only)
3. **Item 5** — Add flag emojis to schedule, groups, picks form, player_detail (touches more files; do before Items 3-4 so those build on the flag work)
4. **Item 3** — Add group to pick summary (builds on Item 5's `data-*` attribute work on the pick form)
5. **Item 4** — Edit Picks button contrast (quick, isolated)
6. **Item 6** — WC prominence on home + login (largest item, uses `frontend-design` skill)

**Skill prescription:** After all items, use `commit-commands` plugin: `style: World Cup UI polish — flags, group labels, featured game card (Group C1)`

**Skill prescription:** Use `playwright` plugin to screenshot the following pages after all changes for Brad's visual review:
- Platform home (unauthenticated)
- Platform home (authenticated, enrolled in WC)
- Login page
- WC index (enrolled, picks submitted)
- WC picks form (edit mode)
- WC player_detail (read-only, pre-deadline)
- WC schedule
- WC group standings
- WC rules

---

## Verification Criteria

1. ✅ Rules page matrix table has 6 columns (Achievement + 5 tiers), no "Base" column
2. ✅ Rules page scoring tables say "Points" not "Base Points"
3. ✅ Pick form team cards show group letter, no confederation
4. ✅ Player detail read-only view shows group letter, no confederation
5. ✅ Pick form team cards show flag emoji before country name
6. ✅ Pick form JS summary sidebar shows flag emoji and group letter per selected team
7. ✅ Schedule page shows flag emoji before each team name (group stage + all knockout rounds)
8. ✅ Group standings page shows flag emoji before each team name
9. ✅ Player detail picks table shows flag emoji before each team name
10. ✅ Edit Picks button on WC index uses solid `btn-game` styling, links to `?edit=1`
11. ✅ Platform home page: World Cup is a featured/hero card, visually larger than other games
12. ✅ Platform home page: Golf and CFB appear as secondary cards below the featured card
13. ✅ Platform home page: unauthenticated users see a strong WC join CTA
14. ✅ Login page: subtle World Cup callout visible
15. ✅ No 500 errors on any of the above paths
16. ✅ `pyright` reports 0 errors on all modified `.py` files (only `routes.py` touched)
17. ✅ No visual regressions on Golf or CFB pages (flag/confederation changes are WC-only)

---

## Notes for C2

The following items are deferred to Group C2 (mobile-first layout overhaul):

- Mobile toolbar sticky behavior + scroll indicator
- Touch target sizing audit across all templates
- Table overflow / horizontal scroll on small screens
- Font sizing responsive adjustments
- Navbar collapse behavior on mobile
- Form usability on small screens (pick form card tap targets especially)

C1 changes should not create new mobile issues, but C2 will audit everything holistically.
