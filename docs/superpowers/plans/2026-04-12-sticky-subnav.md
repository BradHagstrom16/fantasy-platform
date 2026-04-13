# Sticky Nav + Subnav Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the platform navbar and game subnav sticky on scroll using pure CSS.

**Architecture:** Add `position: sticky` to the existing `.navbar` and `.game-subnav` CSS rules, with a mobile media query to adjust the subnav's `top` offset. No template or JS changes.

**Tech Stack:** CSS only

---

### Task 1: Add sticky positioning to navbar and subnav

**Files:**
- Modify: `static/css/style.css:810-815` (`.navbar` rule)
- Modify: `static/css/style.css:911-915` (`.game-subnav` rule)
- Modify: `static/css/style.css:1799` (existing `@media (max-width: 991px)` block)

- [ ] **Step 1: Add sticky properties to `.navbar`**

In `static/css/style.css`, add three properties to the existing `.navbar` rule at line 810:

```css
.navbar {
  background: linear-gradient(90deg, var(--platform-primary-dark) 0%, var(--platform-primary) 100%) !important;
  border-bottom: 3px solid var(--platform-accent);
  padding: .65rem 0;
  box-shadow: 0 2px 20px rgba(0,0,0,.35);
  position: sticky;
  top: 0;
  z-index: 1030;
}
```

- [ ] **Step 2: Add sticky properties to `.game-subnav`**

In `static/css/style.css`, add three properties to the existing `.game-subnav` rule at line 911:

```css
.game-subnav {
  background: #0d0d1a; /* fallback if modifier class omitted — prevents white-on-white */
  padding: .42rem 0;
  border-bottom: 1px solid rgba(255,255,255,.07);
  position: sticky;
  top: 58px;
  z-index: 1020;
}
```

The `top: 58px` value is the navbar's rendered height on desktop (padding + content + border). Verify this against the running dev server — if the measured height differs, use the measured value.

- [ ] **Step 3: Add mobile subnav offset**

In `static/css/style.css`, add a `.game-subnav` override inside the existing `@media (max-width: 991px)` block at line 1799. Place it after the existing `.navbar .dropdown-item` rule (after line 1812):

```css
@media (max-width: 991px) {
  /* ...existing .navbar .nav-link and .dropdown-item rules... */

  .game-subnav { top: 52px; }
}
```

The collapsed mobile navbar is shorter (~52px). Verify this against the dev server in mobile emulation — if the measured height differs, use the measured value.

- [ ] **Step 4: Start dev server and verify navbar heights**

```bash
FLASK_APP=app.py venv/bin/flask run
```

Open `http://127.0.0.1:5000/worldcup/leaderboard` in Chrome. Use DevTools to measure the navbar's rendered height:

1. Right-click the navbar → Inspect → check the element's box model height (including border)
2. Desktop: expect ~58px. If different, update `.game-subnav { top: <measured>px }` in the main rule
3. Toggle device toolbar (Ctrl+Shift+M) → pick a mobile preset → measure again. Expect ~52px. If different, update the `@media (max-width: 991px)` override

- [ ] **Step 5: Verify sticky behavior — desktop**

On `http://127.0.0.1:5000/worldcup/leaderboard` (desktop width):

1. Scroll down — both navbar and subnav remain pinned at top
2. Click a subnav pill (e.g., Schedule) while scrolled — page navigates, bars stay stuck on new page
3. Visit `/` (homepage, no subnav) — only navbar sticks, no empty gap below it

- [ ] **Step 6: Verify sticky behavior — mobile**

In Chrome DevTools mobile emulation (or on your phone at `http://<local-ip>:5000`):

1. Open `/worldcup/leaderboard` — scroll down, both bars pinned
2. Tap hamburger menu — expanded menu pushes subnav down (not overlapping)
3. Close hamburger — subnav snaps back to sticky position below navbar
4. Open `/worldcup/picks` (if enrolled with picks) — the bottom sticky bar (`wc-mobile-sticky-bar`) still works correctly alongside the top sticky bars

- [ ] **Step 7: Commit**

```bash
git add static/css/style.css
git commit -m "style: make navbar and game subnav sticky on scroll

position: sticky on both bars — navbar at top:0, subnav offset
by navbar height. Mobile media query adjusts for shorter collapsed
navbar. Pure CSS, no JS.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
