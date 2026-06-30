# World Cup: PK Score Display + UX Fixes

**Date:** 2026-06-30
**Status:** Approved, pending implementation

---

## Summary

Three independent fixes shipped as one PR:

1. **PK score display** — separate penalty shootout goals from regulation/ET goals in storage and display (FIFA-style `1 (3) – 1 (4)`)
2. **Recent Results** — no change; current design (roster cards + "Around the Tournament" compact strip) is correct as-is
3. **Top-3 leaderboard name links** — clicking a name in the lounge leaderboard widget navigates to `/worldcup/leaderboard/<enrollment_id>`

---

## 1. PK Score Fix

### Root cause

`sync_scores()` reads `score.fullTime.home/away` from the football-data.org API, which bundles ET and penalty shootout goals into the total (e.g., a 2-2 ET match with 3-4 PKs yields `fullTime` = 5-6). The model already has `match.penalties` (bool) but no separate penalty tally columns. Templates render `match.home_score`/`match.away_score` raw, producing misleading scores like "GER 5 – PAR 6."

### Schema changes

Add two nullable integer columns to `WorldCupMatch`:

```python
home_pen = db.Column(db.Integer, nullable=True)  # penalty tally only
away_pen = db.Column(db.Integer, nullable=True)
```

One Alembic migration. Existing rows are `NULL` for both; only PK matches ever populate them. No scoring logic changes — winner/draw (not score digits) drive points.

### Sync changes (`games/worldcup/services/sync.py`)

For `duration == 'PENALTY_SHOOTOUT'` matches:
- Read `score.extraTime.home/away` (not `fullTime`) for `home_score`/`away_score` — this is the score at end of 120 min, before PKs
- Read `score.penalties.home/away` → pass as `home_pen`/`away_pen` to `process_match_result()`

For `EXTRA_TIME` and `REGULAR` matches: no change.

### Scoring changes (`games/worldcup/services/scoring.py`)

`process_match_result()` gains two optional params:

```python
def process_match_result(
    match_id, home_score, away_score, winner_fifa_code,
    is_draw=False, extra_time=False, penalties=False,
    home_pen=None, away_pen=None,  # ← new
) -> dict:
```

Stores `match.home_pen = home_pen` and `match.away_pen = away_pen`. No other scoring logic changes.

### Repair CLI

New command: `flask worldcup repair-pk-scores`

`sync_scores()` skips already-completed shells. This command re-fetches from the API and corrects any completed PK match whose `home_pen` is still `NULL`:
- Sets `home_score`/`away_score` to the ET score
- Sets `home_pen`/`away_pen` to the penalty tally

Idempotent: skips completed PK matches that already have `home_pen` populated.

### Display

In both `core/main/templates/main/_recent_results.html` (lounge) and `games/worldcup/templates/worldcup/_home_live.html` (WC hub results strip):

- When `match.penalties` is True and `match.home_pen is not none`: render `{{ match.home_score }} ({{ match.home_pen }}) – {{ match.away_score }} ({{ match.away_pen }})`
- When `match.penalties` is False: render as today (`{{ match.home_score }} – {{ match.away_score }}`)

Any other template displaying `match.home_score`/`match.away_score` for completed matches should apply the same conditional (audit: schedule, admin match list).

---

## 2. Recent Results — No Change

The existing behavior is correct by design:
- Roster-intersection matches → full Tribune match-cards with points earned
- Non-roster matches → compact "Around the Tournament" strip

This prevents dead-end sections on days when no roster nations played, while keeping roster cards as the focal story.

---

## 3. Top-3 Name Links

### Template (`core/main/templates/main/_home_live.html`)

Wrap the display name in an anchor. Avatar stays outside the link:

```html
{{ row.enrollment.user.get_avatar() }}
<a href="{{ url_for('worldcup.player_detail', enrollment_id=row.enrollment.id) }}"
   class="roll-name-link">{{ row.enrollment.get_display_name() }}</a>
```

The "YOU" chip stays inside the `.roll-name` div but outside the anchor.

### CSS (`static/css/style.css`)

In the lounge rolls section:

```css
.roll-name-link {
    color: inherit;
    text-decoration: none;
}
.roll-name-link:hover,
.roll-name-link:focus-visible {
    text-decoration: underline;
}
```

No structural changes. The link is inline inside the existing `.roll-name` div.

---

## Files Changed

| File | Change |
|---|---|
| `games/worldcup/models.py` | Add `home_pen`, `away_pen` columns |
| `migrations/versions/<hash>_add_pen_cols.py` | New Alembic migration |
| `games/worldcup/services/scoring.py` | `process_match_result()` gains `home_pen`/`away_pen` params |
| `games/worldcup/services/sync.py` | PK match handling: `extraTime` score + `penalties` tally |
| `games/worldcup/cli.py` | New `repair-pk-scores` command |
| `core/main/templates/main/_recent_results.html` | PK score display |
| `games/worldcup/templates/worldcup/_home_live.html` | PK score display in results strip |
| `core/main/templates/main/_home_live.html` | Top-3 name links |
| `static/css/style.css` | `.roll-name-link` styles |

### Audit: other score display sites

Before closing PR, audit for any other templates rendering `match.home_score`/`match.away_score` directly:
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/admin/` match list views

Apply the same PK conditional where found.

---

## Testing

- Unit test for `process_match_result()` with `home_pen`/`away_pen` — asserts fields are stored
- Unit test for `repair-pk-scores` idempotency (second run does not overwrite already-correct records)
- Template rendering test: when `match.penalties=True` and pen cols populated, rendered output contains `(N)` format; when False, no parens
- Regression: existing non-PK match score display unchanged
