# Post-Deadline UI State — Design Spec

**Date:** 2026-04-14
**Discovered:** Step 4E of Human End-to-End Test Script (World Cup launch readiness)
**Status:** Approved — ready for implementation

---

## Problem

When `TOURNAMENT_DEADLINE_UTC` passes (first match kickoff), three UI surfaces show stale pre-deadline messaging:

1. **WC index — enrolled+picks card**: shows "Picks submitted. You can edit until [past date]" and an "Edit My Picks" button that still links to the edit form (which is server-blocked but confusing).
2. **WC index — unenrolled card**: shows "Join Now" with entry fee CTA, implying registration is open when it isn't.
3. **Homepage featured card**: shows "Enter the Pool" / "Join the World Cup Pool" after the pool is closed.

The server correctly blocks pick submission and editing post-deadline. This spec fixes only the UI messaging to match that server behavior.

---

## Approach

Template-only fix (Approach A). No model changes, no migrations, no new routes.

- `deadline_passed` is already computed in the WC index route and passed to the template.
- `deadline_passed` needs to be computed and passed in the homepage route (new addition).
- All changes are `{% if deadline_passed %}` branches in two templates.

The `frontend-design` skill will be invoked during implementation to ensure new CTA cards match the Commissioner's Club design system.

---

## Files Changed

| File | Change |
|------|--------|
| `games/worldcup/templates/worldcup/index.html` | Restructure CTA block around `deadline_passed` |
| `core/main/templates/main/index.html` | Update featured card button text |
| `core/main/routes.py` | Compute and pass `deadline_passed` |

---

## Detailed Behavior

### WC Index — CTA Block

Existing structure (within `{% if tournament_phase == 'pre_tournament' %}`):
```
not enrolled       → Join CTA
enrolled, no picks → Submit Picks CTA
enrolled, picks    → Edit Picks CTA  ← BROKEN POST-DEADLINE
```

New structure — `deadline_passed` gates first:

```
{% if tournament_phase == 'pre_tournament' %}
  {% if deadline_passed %}

    {% if enrollment and enrollment.picks_submitted %}
      → "You're In!" card
          Heading:  "You're In!"
          Subtitle: "The tournament has started — track your teams on the leaderboard."
          Button:   "View My Picks"  (links to /worldcup/picks, read-only view)

    {% else %}
      → "Tournament Underway" card
          (covers: unenrolled AND enrolled-but-no-picks)
          Heading:  "Tournament Underway"
          Subtitle: "Registration is closed, but you can follow the action."
          Button:   "View Leaderboard"  (links to /worldcup/leaderboard)

    {% endif %}

  {% else %}
    [existing join / submit / edit CTAs — no changes]
  {% endif %}

  [My Roster widget — no changes, still shown for enrolled+picks users]
{% endif %}
```

#### Card styling

- **"You're In!" card**: green left border (`border-start border-success border-3`), heading in `text-success`. Matches the existing enrolled+picks card visual identity.
- **"Tournament Underway" card**: World Cup blue left border (`border-start` with `--game-primary`), muted heading. Uses `btn-outline-secondary` for the leaderboard button (not btn-game — this user isn't a participant).

### Homepage Featured Card

`core/main/routes.py` additions:
```python
from datetime import datetime, timezone
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC

# in index():
deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC
# passed to render_template()
```

`core/main/templates/main/index.html` button text:
```html
{% if deadline_passed %}
    <i class="bi bi-bar-chart me-2"></i>View Standings
{% elif current_user.is_authenticated %}
    <i class="bi bi-globe2 me-2"></i>Enter the Pool
{% else %}
    <i class="bi bi-globe2 me-2"></i>Join the World Cup Pool
{% endif %}
```

Card link (`featured_game.url`) stays pointed at `worldcup.index` — that page shows the leaderboard preview and "View All" link, which is the right landing spot.

---

## Edge Cases

| State | Behavior |
|-------|----------|
| Enrolled, picks submitted, deadline not passed | Unchanged — "You're All Set! / Edit My Picks" |
| Enrolled, picks submitted, deadline passed | "You're In!" card — "View My Picks" |
| Enrolled, no picks, deadline not passed | Unchanged — "Submit Your Picks" warning |
| Enrolled, no picks, deadline passed | "Tournament Underway" card — "View Leaderboard" |
| Not enrolled, deadline not passed | Unchanged — "Join Now" CTA |
| Not enrolled, deadline passed | "Tournament Underway" card — "View Leaderboard" |
| Tournament phase ≠ pre_tournament | Outer block doesn't render — no CTA shown (existing behavior, unchanged) |

---

## Out of Scope

- Subnav shaking / animation issue (noted in 4E, deferred)
- Post-deadline state for Golf or CFB
- Any changes to server-side pick submission logic (already correct)
- Enrolled-but-no-picks users receiving any warning before deadline (separate UX concern)

---

## Skill Usage During Implementation

1. **graphify** — consult `GRAPH_REPORT.md` before touching templates to confirm no god-node side effects
2. **brainstorming** — this spec (complete)
3. **frontend-design** — invoked when writing the new CTA card HTML to ensure design system compliance

---

## Verification (from 4E test script)

After implementation with deadline set to past:
- [ ] `/worldcup/picks` — read-only (unchanged, already passes)
- [ ] WC index — shows "You're In!" card with "View My Picks" (no Edit button)
- [ ] WC index (logged out / unenrolled) — shows "Tournament Underway" + "View Leaderboard"
- [ ] Homepage — featured card button reads "View Standings"
- [ ] Revert deadline — all CTAs return to pre-deadline state correctly
