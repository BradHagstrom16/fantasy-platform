# Sticky Nav + Subnav Design Spec

**Date:** 2026-04-12  
**Scope:** Make the platform navbar and game subnav sticky on scroll, all breakpoints  

---

## Problem

The game subnav (pill-link strip with Leaderboard, Schedule, Groups, etc.) scrolls away with the page content. On long pages — especially on mobile — users must scroll back to the top to navigate within a game. The platform navbar (game switcher, profile dropdown) has the same problem.

## Decision

Make **both** bars sticky using CSS `position: sticky`. The navbar sticks to `top: 0`; the subnav sticks just below it. No JavaScript required.

### Alternatives considered

| Approach | Why not |
|----------|---------|
| `position: fixed` on both | Removes elements from document flow — requires body padding offset, breaks hamburger menu push-down behavior |
| JS `IntersectionObserver` toggle | Overkill for a pure layout concern; adds JS dependency and scroll-triggered reflows |
| Subnav-only sticky | Users also lose access to game switcher and profile — navbar should stick too |
| Mobile-only sticky | Desktop users on long pages (leaderboard, schedule) benefit equally |

## Design

### CSS changes (3 rules)

**1. Navbar — stick to top**

Add to existing `.navbar` rule:

```css
.navbar {
  position: sticky;
  top: 0;
  z-index: 1030;
}
```

**2. Subnav — stick below navbar**

Add to existing `.game-subnav` rule:

```css
.game-subnav {
  position: sticky;
  top: 58px;   /* navbar height on desktop */
  z-index: 1020;
}
```

**3. Mobile offset — navbar is shorter when collapsed**

Add inside the existing `@media (max-width: 991px)` block:

```css
@media (max-width: 991px) {
  .game-subnav { top: 52px; }
}
```

### Why these values

- **`z-index: 1030`** on navbar — matches Bootstrap's `fixed-top` convention and the existing `wc-mobile-sticky-bar` z-index.
- **`z-index: 1020`** on subnav — layers below navbar, above page content.
- **`top: 58px` / `52px`** — measured navbar height at desktop and mobile breakpoints. These will be verified against the running dev server during implementation; if the measured values differ slightly, the implementation uses the measured values.
- **No body padding** — `position: sticky` keeps elements in document flow, unlike `fixed`.

### Behavioral details

- **Hamburger menu expansion (mobile):** The expanded Bootstrap collapse menu is part of the navbar's flow. Because `sticky` keeps the element in-flow, the expanded menu pushes the subnav down naturally — no z-index tricks or overlay logic needed.
- **Non-game pages:** Only the navbar exists (no subnav), so only the navbar sticks. No conditional logic required.
- **Existing `wc-mobile-sticky-bar`:** The pick-form bottom bar uses `position: fixed; z-index: 1030`. It sits at the bottom of the viewport and doesn't interact with the top-sticky bars. No changes needed.
- **Flash messages:** The `.container.mt-3` flash message block sits below the subnav in the DOM and scrolls normally under the sticky bars. This is correct behavior — flash messages are transient and dismissible.

### Files to modify

| File | Change |
|------|--------|
| `static/css/style.css` | Add `position: sticky; top: 0; z-index: 1030` to `.navbar`; add `position: sticky; top: 58px; z-index: 1020` to `.game-subnav`; add mobile `top` override in existing media query |

No template changes. No JavaScript.

### Verification

1. Start dev server, open World Cup leaderboard (long page)
2. Scroll down — both bars remain visible at top
3. Click subnav pills while scrolled — navigation works, bars stay stuck
4. Open hamburger menu on mobile — expanded menu pushes subnav down
5. Close hamburger — subnav snaps back to its sticky position
6. Visit a non-game page (homepage) — only navbar is sticky, no gap where subnav would be
7. Visit the WC pick form on mobile — bottom sticky bar still works correctly alongside top sticky bars
