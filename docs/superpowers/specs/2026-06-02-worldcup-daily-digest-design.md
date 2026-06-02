# World Cup Daily Digest — Design Spec

**Date:** 2026-06-02  
**Status:** Core implementation complete; timer, tests, and docs remain.

---

## 1. Problem

Players receive no feedback after matches are processed. With 72 group-stage matches across the first 18 days of the tournament, players have no prompt to re-engage after their picks score. The sync automation silently applies results at 30-minute intervals; players only discover score changes by logging in.

---

## 2. Decision: Daily digest at 5am CT, only when picks scored

**Trigger condition:** At least one of the player's 9 picks earned > 0 points on the previous CT calendar day.

**Rationale for the choices made:**

- **Daily cap (max 1 email per player per day):** Group stage peaks at 3 matches per day in overlapping windows. Per-match emails would send up to 3 emails on the same day. Daily batching eliminates that without losing timeliness.
- **5am CT send time:** Covers all matches from the previous CT calendar day with no edge cases — a 9pm CT kickoff is safely captured. Players wake up to results rather than receiving mid-day or late-night interruptions.
- **Only when picks scored:** If none of your picks played, you get silence. Every email that lands represents a real score change. Signal-to-noise ratio is 1.0.
- **Weekly recap considered and rejected:** The tournament runs 5 weeks total. A weekly recap would produce 4–5 emails for the entire tournament. It misses the emotional connection to "your team just scored" that makes fantasy sports engaging. Per-match was also considered; daily is the right middle point.

---

## 3. Email content

### Information hierarchy

1. **Score hero** (bone substrate): total pts in large Teko, navy delta ("▲ +38 pts on June 1"), rank + change signal
2. **Navy rule** (2px, visual separator)
3. **Pick rows** (white card): flag SVG + team name + multiplier chip + match score + result + pts earned
4. **Gold CTA**: "View Standings →" links to `/worldcup/leaderboard`
5. **Footer band**: dark purple, "Corrupt Commish Club · cccfantasy.com"

### Rank change signal

Sourced from `compute_rank_delta(enrollment, window_days=1)` in `services/ranking.py`. Requires `snapshot-ranks` to have run on at least two consecutive days. Returns `None` when insufficient history — signal is hidden, not shown as zero.

- `rank_delta > 0` → green pill "↑ N spots"
- `rank_delta < 0` → red pill "↓ N spots"  
- `rank_delta == 0` → gray pill "→ Steady"
- `rank_delta is None` → no signal shown

### Color semantics

- **Navy `#002868`** for the delta line and per-pick points. Positive score changes are authoritative and structural, not urgent. Red is reserved for WC competitive/active-state signals in the web UI; reusing it for "good news" in email would conflict with that semantic role.
- **Green `#1A7A45`** for "Won" result labels and rank-up signal.
- **Gold `#C9A227`** for "Draw" result labels and the CTA button gradient.
- **WC red `#BF0A30`** not used in the email body — preserved for web UI accent rank.

### Header logo

`CCC-final-11` (stacked King Viking Badger mark + "CORRUPT COMMISH CLUB" wordmark below, transparent background SVG). Renders cleanly on the dark purple `#2A1150` header band. The character artwork's white fills are intentional — they contrast correctly against the dark substrate. "WORLD CUP FANTASY POOL" subline sits below the artwork in bone-mute Teko. Outlook fallback: plain text name.

### Template contract

Template: `games/worldcup/templates/worldcup/email/wc_daily_digest.j2`  
Rendered via `flask.render_template()` inside the app context (CLI-safe).

| Variable | Type | Description |
|---|---|---|
| `enrollment` | `WorldCupEnrollment` | Player enrollment; exposes `.get_display_name()`, `.total_score` |
| `match_results` | `list[dict]` | One entry per scoring event; see keys below |
| `total_yesterday_str` | `str` | Formatted total pts earned yesterday (e.g. `"38"`, `"4.5"`) |
| `rank` | `int` | Dense rank in active season |
| `total_enrolled` | `int` | Total enrolled players with submitted picks |
| `rank_delta` | `int \| None` | Signed rank change; `None` = no snapshot history |
| `date_str` | `str` | Formatted date (e.g. `"June 1"`) |
| `site_url` | `str` | Absolute base URL (e.g. `"https://cccfantasy.com"`) |
| `logo_url` | `str` | Absolute URL to `ccc-logo-stacked.svg` |
| `asset_version` | `str` | Cache-bust token (git short SHA) |

`match_results` dict keys: `team` (WorldCupTeam), `multiplier_str` (e.g. `"×2.5"`), `match_score` (e.g. `"BRA 2–0 MEX"`), `stage_label` (via `stage_label()` SSoT), `result` (`"won"`, `"draw"`, or `"lost"`), `points_earned` (float, multiplied), `points_str` (formatted string).

---

## 4. Service architecture

### New files

| File | Purpose |
|---|---|
| `games/worldcup/services/notifications.py` | `send_daily_digests()` — main entry point; helpers for formatting, rank, plain-text |
| `games/worldcup/templates/worldcup/email/wc_daily_digest.j2` | HTML email template |
| `static/img/logo/ccc-logo-stacked.svg` | CCC-final-11 SVG copied to static for absolute URL reference in emails |

### New CLI command

```
flask worldcup send-digest
```

Calls `send_daily_digests()`, prints a summary line, exits non-zero on send errors. Registered in `games/worldcup/cli.py`.

### `send_daily_digests()` logic

1. Determine `yesterday` = `(now_utc() in CT) - 1 day`
2. Load all completed matches; filter to those whose `updated_at` (in CT) falls on `yesterday`
3. Collect team IDs that played
4. For each enrolled player with submitted picks:
   - Find picks whose `team_id` is in the played set
   - For each such pick × each matching match, call `points_for_pick_on_match()` — skip if `<= 0`
   - Skip player entirely if no scoring events
   - Compute `rank` via dense-rank query; `rank_delta` via `compute_rank_delta()`
   - Render template; send via `send_platform_email()`
5. Return summary dict: `sent`, `skipped_no_match`, `skipped_no_score`, `skipped_no_email`, `errors`

Points sourced from `points_for_pick_on_match()` — already-multiplied, per the per-pick helper's contract (CLAUDE.md scoring conventions).

---

## 5. What remains to build

### 5a. Systemd timer — `wc-digest-player.timer`

New unit pair alongside the three existing WC timers (`wc-scores.timer`, `wc-advancement.timer`, `wc-digest.timer`). Pattern from `wc-digest.timer` (daily, inline CT timezone):

```ini
# /etc/systemd/system/wc-digest-player.timer
[Unit]
Description=WC player daily digest — 5am CT

[Timer]
OnCalendar=America/Chicago:*-*-* 05:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/wc-digest-player.service
[Unit]
Description=WC player daily digest send
After=network.target

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/home/deploy/fantasy-platform
EnvironmentFile=/home/deploy/fantasy-platform/.env
Environment=ENVIRONMENT=production
ExecStart=/home/deploy/fantasy-platform/venv/bin/flask worldcup send-digest
```

### 5b. Tests — `tests/test_worldcup_notifications.py`

- `test_send_daily_digests_no_results` — no completed matches yesterday, returns `no_results`
- `test_send_daily_digests_skips_no_match` — completed matches but player's picks didn't play
- `test_send_daily_digests_skips_no_score` — pick played but lost (0 pts), player skipped
- `test_send_daily_digests_sends_on_score` — pick scored, email sent; assert subject, HTML contains team name and pts string
- `test_send_daily_digests_rank_signal_none` — no snapshots, `rank_delta=None` passed correctly
- `test_plain_body_rank_signal_up` — plain text includes "up 2 spots"
- `test_plain_body_rank_signal_down` — plain text includes "down 1 spot"

Mock `send_platform_email` at `games.worldcup.services.notifications.send_platform_email`.

### 5c. CLAUDE.md / docs

Add to the World Cup CLI block:
```
FLASK_APP=app.py venv/bin/flask worldcup send-digest  # Send player digest (cron; 5am CT)
```

Add to the Production ops section: note the `wc-digest-player` timer alongside the existing three WC timers.

---

## 6. Deliberately out of scope

- **Opt-out / unsubscribe**: Not built. Pool has ~10–30 known participants; admin can remove a player's email manually if needed. Not worth the overhead for this audience size.
- **Digest for 0-point match days**: If all your picks lost, no email. Correct behavior — nothing to report.
- **Rank signal for new players** (< 2 snapshot days): graceful degradation — signal is hidden, not shown as zero movement.
- **Per-pick loss reporting**: Only scoring events appear. A player doesn't need an email to learn their pick lost; they'll see it in the standings.
