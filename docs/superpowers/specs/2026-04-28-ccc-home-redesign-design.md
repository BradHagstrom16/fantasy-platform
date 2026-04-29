# Spec B — CCC Home Redesign (4 States)

**Date:** 2026-04-28
**Status:** Approved
**Initiative:** CCC Redesign (Specs A → B → C)
**Predecessors:** Spec A — CCC Brand Foundation + Chrome (`docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`), merged today as `2859881`
**Successors:** Spec C — World Cup Reskin
**Branch:** `redesign/ccc-home` (worktree at `../fantasy-platform-ccc-home`)
**Source design bundle:** `fantasy-platform-and-world-cup-design/` (Claude Design handoff, untracked)

---

## 1. Context

Spec A established the CCC brand foundation: `tokens.css` (Layer 1), rewired `style.css :root` (Layer 2), logo + favicon assets, naming sweep, restyled `base.html` chrome (navbar + footer), restyled auth and admin pages, restyled the password-reset email. CFB and Golf interiors plus all World Cup interior pages were intentionally untouched.

Spec B replaces `core/main/templates/main/index.html` wholesale with a four-state home page built on the new foundation. The four states are:

1. **logged-out** — marketing surface for first-time visitors
2. **logged-in pre-WC** — picks open, deadline not yet passed
3. **logged-in during WC** — deadline passed, final not yet completed
4. **logged-in post-WC** — final match completed, ~6-week recap window before CFB launches

The design bundle provides mockups for states 1, 2, and 3 (plus a desktop variant of 3). State 4 is undesigned and brainstormed from scratch in this spec.

### Sequencing context

The production deployment plan (`docs/superpowers/plans/2026-04-21-production-deployment.md`) is paused after Phase 2 Task 10. Brad's stated sequence: finish Spec B → finish Spec C → integrate sports-data API → resume the deploy plan at Task 11.

**The deploy plan has already been updated** to weave Spec B's snapshot cron into Task 25's cron schedule (the natural insertion point alongside the other game-specific jobs). No new task is added; Task 25 now lists the snapshot job. A sequencing note at the top of the deploy plan documents this integration. Spec B requires no further deploy-plan changes.

### Constraints inherited from Spec A

- Bootstrap 5.3 stays.
- `tokens.css` is extensible — Layer 1 grows here.
- `style.css :root` (Layer 2) is **not** modified by Spec B.
- Per-game palettes (CFB crimson/midnight, Golf green/gold, WC navy/red) untouched — Spec B is platform chrome only.
- Voice doctrine "moderate" (Spec A D4): voice ON for ritual/celebration surfaces, plain English for utility surfaces. Home is celebration territory; voice is on throughout.
- No new tests for pure visual reskin work — but **one** new test file is added because the home gains real branching logic (`worldcup_state()`) and a data-assembly seam (`build_home_context()`).

### Deferred features that affect this spec

Per memory at `project_ccc_specs_b_c_notes.md`:

- **Match (`wc-match.jsx`)** — needs sports-data API. Deferred. Spec B does **not** render any in-progress match scoreboards.
- **Tribune (`wc-tribune.jsx`)** — needs content pipeline. Deferred. Spec B does **not** link to a "Tribune" surface anywhere; it ships file-edited static partials (`_commish_note.html` + `_dispatches.html`) as the narrative surface in its place.

---

## 2. Approved decisions

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Live-state Match cards + Dispatches handling | **B — Static stand-ins.** Replace live `MatchCard` with a "Recent Results" strip from `WorldCupMatch.is_completed=True`. Replace `Dispatches` feed with a hand-edited `_dispatches.html` partial. | Match needs a sports-data API (deferred). Tribune needs a content pipeline (deferred). Real recent-results data + static narrative partial preserve the design's visual rhythm without faking infra. |
| D2 | Post-WC state direction (undesigned by bundle) | **A primarily + B's roster recap.** Champion banner + final podium of top 3 + your-roster-recap (each pick + points + best finish) + game tiles. | Champion banner is the obvious focal point during a quiet 6-week window. Roster recap delivers a personal "how'd I do" beat. Window is Jul 19 → Sep 3 (CFB launch). |
| D3 | Logged-out hero voice calibration | **B (keep voice register, swap fictional content) + C (cut social-proof block entirely).** Adopt design's "The Fix Is In" headline + value-prop copy verbatim. **Cut the fake "Competitor №47, 2022" testimonial block entirely.** CTA: **"Join the Club"** (matches nav, not design's "Enter the Chamber"). | "The Fix Is In" is the brand's whole thesis in three words; worth keeping. The fake testimonial reads as AI trust-theater on a real product. CTA consistency with nav matters. |
| D4 | Live-dossier data gap (sparkline, week-delta) | **B — Add `WorldCupRankSnapshot` table + daily cron.** New model captures rank + score per enrollment per day at midnight CT. | Trend/sparkline is the most engaging part of the live dossier. Infra cost is small (one table, one CLI, one cron entry). Reusable on the leaderboard page in Spec C. **Daily** snapshot, not twice-daily. |
| D5 | Desktop treatment for non-live states | **B — Mobile-first single column for `out`/`pre`/`post`; design's two-column desktop layout for `live` only.** Non-live states use a max-width ~640px centered single column on desktop. | `out` is fundamentally a centered marketing surface. `pre`/`post` are infrequent time-bounded states. `live` is the daily-use state where the design already commits to a desktop story. Inventing dual layouts for the others is scope creep. |
| D6 | Game tiles structure | **B — Compact 3-tile strip for `pre`/`live`/`post`; full `_game_card.html` cards for `out`.** | Logged-in users came for the World Cup; full game-pitch cards above the dossier would bury what they came to see. Logged-out users need full cards to understand each game on the platform. |
| D7 | State detection: live → post boundary | **B — Final-match completion only.** `post = WorldCupMatch.query.filter_by(match_number=104, is_completed=True).first() is not None`. No date-based fallback. | Brad accepts the operational dependency: if admin doesn't mark match #104 complete, home stays in "live" forever. Brad is the admin. |
| D7a | Unenrolled logged-in user handling | **Deadline-based:** if `now < TOURNAMENT_DEADLINE_UTC`, dossier slot = "Join the World Cup pool →" CTA. If deadline has passed, dossier slot = "View the World Cup →" CTA (read-only entry). | Once picks lock, joining is no longer meaningful. Viewing is. |
| D8 | Pre-deadline countdown implementation | **C — Hybrid.** Server-side renders initial `DD:HH:MM:SS` values; ~25 lines of vanilla JS in `static/js/countdown.js` ticks every second. Always shows DD:HH:MM:SS shape (no dynamic unit collapse). Page reloads when countdown reaches zero. | Ticking countdown is the visual centerpiece of the pre state. SSR-correct initial render avoids FOUC. Static "X days" loses the design's strongest pre-deadline element. |
| D9 | Commish's narrative surface (replaces deferred Tribune) | **C — Two separate partials, file-edited.** `_commish_note.html` (long-form, Newsreader serif, paragraph spacing, byline) + `_dispatches.html` (1–2 short event-driven entries). Both rendered via `{% include ... ignore missing %}`. Ship Spec B with a default seed in `_commish_note.html` so it's never empty at launch. | Brad's natural writing style is long-form weekly recaps (per his CFB-season pattern). Two partials = one job each: the right file open for what you want to write that week. File-based editing because Brad is the only editor and already deploys via `git pull`. |
| D10 | Code organization for the four states | **B — Thin shell + per-state partials.** `index.html` is a state-dispatching shell that includes `_home_<state>.html`. Shared subpartials (`_dossier_card.html`, `_game_tiles_compact.html`, `_recent_results.html`, etc.) live alongside. | Each state file stays in the 200–400 line range — comfortable for one-shot edits per CLAUDE.md's "smaller, well-bounded units" principle. One Python helper module for state detection (`games/worldcup/services/state.py`); one Python helper module for data assembly (`core/main/home_context.py`). Route stays under 25 lines. |
| D11 | Tagline strings on leaderboard preview rows | **B — Server-derived contextual one-liners.** Pure-function helper in `home_context.py` maps `(rank, week_delta, alive_count)` to one of ~10–15 finite templated strings. No DB column, no admin UI, deterministic output. | A (drop entirely) makes the leaderboard preview feel flat next to the design reference. C (DB column + admin) is real product scope. B preserves design rhythm with a 30-line lookup helper. |
| D12 | Frontend-design skill use | **Call out `/frontend-design:frontend-design` in implementation guidance**, scoped to where the spec goes beyond the bundle: undesigned post-WC pieces (`_champion_banner`, `_podium`, `_roster_recap`), wide-desktop variants for `out`/`pre`/`post`, the Commish's Note partial, the recent-results strip, and polish/microinteractions. Direct ports of existing mockups don't need it. | The skill is most useful where there's real design judgment to apply, not faithful porting. |

---

## 3. Architecture & file layout

### 3a. Worktree setup

```bash
git worktree add ../fantasy-platform-ccc-home -b redesign/ccc-home main
cd ../fantasy-platform-ccc-home
```

One PR for all of Spec B, same pattern as Spec A.

### 3b. Files added

```
core/main/
├── home_context.py                             (new — per-state data assembly)
└── templates/main/
    ├── _home_out.html                          (new — logged-out marketing)
    ├── _home_pre.html                          (new — pre-deadline)
    ├── _home_live.html                         (new — live tournament)
    ├── _home_post.html                         (new — tournament complete)
    ├── _commish_note.html                      (new — long-form, with seed default)
    ├── _dispatches.html                        (new — short feed, can be empty)
    ├── _dossier_card.html                      (new — used by live)
    ├── _game_tiles_compact.html                (new — used by pre/live/post)
    ├── _recent_results.html                    (new — used by live)
    ├── _ballot_card.html                       (new — used by pre, sealed variant)
    ├── _submit_picks_cta.html                  (new — used by pre, enrolled-no-picks variant)
    ├── _countdown_card.html                    (new — used by pre)
    ├── _champion_banner.html                   (new — used by post)
    ├── _join_cta_card.html                     (new — unenrolled-pre dossier slot)
    └── _view_cta_card.html                     (new — unenrolled-live/post dossier slot)

games/worldcup/
├── services/state.py                           (new — worldcup_state() helper)
└── models.py                                   (modified — add WorldCupRankSnapshot)

migrations/versions/
└── XXXX_add_worldcup_rank_snapshot.py          (new — single new table)

games/worldcup/
└── cli.py                                      (modified — add `flask worldcup snapshot-ranks`)

deploy/
└── crontab.txt                                 (modified or created — daily snapshot at 05:05 UTC)

static/
└── js/
    └── countdown.js                            (new — ~25 lines vanilla JS)

tests/
└── test_home_context.py                        (new — ~120 lines, ~8 tests)
```

15 new partials total. The two unenrolled-CTA partials (`_join_cta_card.html`, `_view_cta_card.html`) and the enrolled-no-picks CTA (`_submit_picks_cta.html`) each handle one specific dossier-slot variant.

### 3c. Files modified

| File | Change scope |
|---|---|
| `core/main/templates/main/index.html` | **Wholesale rewrite** — thin shell that includes one of `_home_<state>.html` based on the `state` template variable. |
| `core/main/templates/main/_game_card.html` | **Kept and used only by `_home_out.html`**; otherwise unchanged. |
| `core/main/routes.py` | `index()` rewritten — calls `worldcup_state()` + `build_home_context()`, renders single `index.html`. |
| `static/css/style.css` | New section `/* === HOME (CCC) === */` inserted after the existing `/* === GAME SUB-NAV === */` block, before any game-specific sections. ~600–700 lines, ~25 component classes scoped under a `.home-shell` wrapper. Existing `.home-hero`/`.featured-game-inner`/etc retained but only consumed by `_game_card.html` for the logged-out cards. |
| `static/css/tokens.css` | Add three new tokens at the bottom under a `/* Spec B additions */` comment: `--live-orange`, `--podium-glow`, `--champion-glow`. Spec A's tokens are not touched. |
| `games/worldcup/services/__init__.py` | Re-export `worldcup_state` for ergonomic imports. |
| `games/registry.py` | Add `'completed'` to `GameStatus` Literal (single-line change). The compact game tiles strip's per-game label is data-driven from registry status; this lets Brad flip the WC entry from `'open'` to `'completed'` post-tournament. |

### 3d. What is NOT touched

- `templates/base.html` (chrome stays; Spec A locked it).
- `games/worldcup/templates/worldcup/*` (Spec C territory).
- Any CFB or Golf templates / routes / CSS.
- `_game_card.html` structure (used as-is by logged-out).
- The auth pages, admin pages, error pages.
- `style.css :root` Layer 2 block (Spec A locked it).
- Bootstrap version (5.3 stays).
- Any other tests beyond `test_home_context.py`.

---

## 4. State detection + data flow

### 4a. `worldcup_state()` — single source of truth

```python
# games/worldcup/services/state.py
import os
from datetime import datetime, timezone
from typing import Literal

from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupMatch

WorldCupState = Literal['pre', 'live', 'post']

FINAL_MATCH_NUMBER = 104  # The Final, per FIFA bracket numbering


def _now_utc() -> datetime:
    """Current UTC time. In development, can be overridden via WC_FAKE_NOW
    env var (ISO 8601 string). Production never reads this env var."""
    if os.environ.get('ENVIRONMENT') == 'development':
        fake = os.environ.get('WC_FAKE_NOW')
        if fake:
            return datetime.fromisoformat(fake.replace('Z', '+00:00'))
    return datetime.now(timezone.utc)


def worldcup_state() -> WorldCupState:
    """Return the current World Cup phase for home-page rendering.
    
    pre  — picks open, deadline not yet passed
    live — deadline passed, final not yet completed
    post — final match (#104) marked complete
    """
    if _now_utc() < TOURNAMENT_DEADLINE_UTC:
        return 'pre'
    final = WorldCupMatch.query.filter_by(
        match_number=FINAL_MATCH_NUMBER, is_completed=True
    ).first()
    return 'post' if final is not None else 'live'
```

Single function, no caching (one indexed query per home request — negligible). `FINAL_MATCH_NUMBER = 104` lives here, not in `constants.py`, because it's a state-detection concept not a tournament configuration. The `_now_utc()` indirection allows dev-only time mocking via `WC_FAKE_NOW` for verification of `live` and `post` states without committing date changes.

### 4b. `build_home_context(user, state)` — per-state data assembly

```python
# core/main/home_context.py
def build_home_context(user, state: WorldCupState | None) -> dict:
    """Assemble the render context for the home page in the given state.
    
    state=None for unauthenticated users (logged-out marketing surface).
    """
    if state is None:
        return _context_out()
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR
    ).first()
    if state == 'pre':
        return _context_pre(user, enrollment)
    if state == 'live':
        return _context_live(user, enrollment)
    return _context_post(user, enrollment)
```

Per-state private builders. Each returns a dict the template consumes via `**ctx`.

### 4c. Per-state data needs

| State | Data assembled | Source |
|---|---|---|
| `_context_out` | `available_games`, `coming_soon_games`, `total_enrolled` (the "{N} competitors in the club" line; suppressed if 0) | registry helpers + WC enrollment count |
| `_context_pre` | `enrollment`, `is_enrolled`, `picks` (if sealed), `deadline_utc`, `deadline_ct`, `total_enrolled`, `next_3_matches`, `court_line` (computed copy), `display_name`, `joined_games`, `coming_soon_games` (for compact tiles strip) | enrollment lookup, `WorldCupPick` join, `WorldCupMatch.kickoff_utc` ordered, registry helpers |
| `_context_live` | `enrollment`, `is_enrolled`, `dossier` (rank, total_score, alive_count, week_delta_rank, week_delta_points, sparkline_data, court_line, stage_label), `top_3_plus_you`, `recent_results` (last 5 completed matches), `your_pick_results` (which recent matches involved your roster), `taglines` (per-row contextual one-liners), `joined_games`, `coming_soon_games` | enrollment + `WorldCupRankSnapshot` last 7 + leaderboard query + match query + registry helpers |
| `_context_post` | `enrollment`, `is_enrolled`, `champion_team`, `champion_summary` (formatted final score/extra-time/pks), `top_3_final`, `your_final_rank`, `your_climbed_n` (from snapshots if available), `your_roster_recap` (each pick + points scored + best_finish + tier_name), `joined_games`, `coming_soon_games` | match #104 + leaderboard query + roster join + registry helpers |

### 4d. Route shape

```python
# core/main/routes.py — full new index() route
@main_bp.route('/')
def index():
    if not current_user.is_authenticated:
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out', **ctx)
    state = worldcup_state()
    ctx = build_home_context(current_user, state)
    return render_template('main/index.html', state=state, **ctx)
```

### 4e. `index.html` shell

```jinja
{% extends "base.html" %}
{% block content %}
<div class="home-shell home-shell--{{ state }}">
{% if state == 'out' %}{% include 'main/_home_out.html' %}
{% elif state == 'pre' %}{% include 'main/_home_pre.html' %}
{% elif state == 'live' %}{% include 'main/_home_live.html' %}
{% elif state == 'post' %}{% include 'main/_home_post.html' %}
{% endif %}
</div>
{% endblock %}
```

The `.home-shell` wrapper class scopes all home-section CSS away from game interiors. The `--<state>` modifier lets the page-level background gradient differ per state without each partial setting it.

### 4f. Unenrolled logged-in handling

Each state partial checks `is_enrolled` in the dossier slot:
- `_home_pre.html` — if `not is_enrolled`: render `_join_cta_card.html` ("Join the World Cup pool →", links `worldcup.join`); if enrolled but unsealed: `_submit_picks_cta.html` ("Seal Your Roster"); if enrolled and sealed: `_ballot_card.html` (the 9-flag grid).
- `_home_live.html` and `_home_post.html` — if `not is_enrolled`: render `_view_cta_card.html` ("View the World Cup →", links `worldcup.index`); if enrolled: `_dossier_card.html` (live) or `_champion_banner.html` (post, full layout).

### 4g. Performance note

Live state assembly is one route render. Estimated query count: 1 enrollment lookup + 1 leaderboard query (top 3 + count + user rank) + 1 picks-with-team join + 1 recent-matches query + 1 snapshot-history query = **5 queries per home request**. No N+1 risks; all eager-load via explicit joins. Acceptable for a free-tier Postgres on a personal app.

---

## 5. State 1 — Logged-out (`_home_out.html`)

### 5a. Layout (mobile-first, max-width ~640px on desktop)

```
[OUT-HERO]
  ◈ Fantasy for crooked kings & queens ◈
  
  The Fix
  Is In.
  (Teko display, gold-gradient on "Fix")
  
  A fantasy pool for fiefdoms, not spreadsheets.
  Pay tribute. Bend the odds to your will.
  No honor required.

[OUT-PROPS — 3 stacked]
  ◇ Rule the fiefdom
    Pick a Favorite, a Dark Horse, a Sacred
    Underdog. Every choice pays.
  ────────────────────────────────────
  ◇ Climb the leaderboard
    Live rank. Weekly dispatches when rivals fall.
  ────────────────────────────────────
  ◇ Read the Commish's Note
    Weekly recaps in plain language. No shame.
    Just receipts.

[JOIN CTA CARD]
  ◈ Open Court · 2026 WC
  {N} competitors in the club          ← suppressed if N=0
  
  Join the competition.
  (Teko, gold-gradient on "competition")
  
  Pre-kickoff: anyone can join the game. Once
  group stage locks on June 11, you can still
  join the club — but your ballot closes with
  the rest.
  
  [JOIN THE CLUB →]   (gold gradient button)
  
  Already sworn in? Sign in

[FULL GAME CARDS — registry-driven _game_card.html]
  ⚽ 2026 FIFA World Cup     [Sign Up to Play →]
  🏈 CFB Survivor Pool       [Coming Soon]
  ⛳ Golf Pick 'Em            [Coming Soon]

[footer voice strip — base.html]
```

### 5b. Decisions encoded
- Hero copy adopted verbatim from design.
- Value prop #3 changed: design says "Read the tribune" → we say "Read the Commish's Note" (Tribune deferred per Spec C-notes; this is the partial we're actually building).
- CTA button label: **"Join the Club"** (not design's "Enter the Chamber"; matches nav consistency).
- **No social-proof block** (per D3-c).
- Game tiles use full-card treatment below the Join CTA (per D6).
- "Once group stage locks on June 11" is hard-coded in template — fixed FIFA fixture date.
- "{N} competitors" line is suppressed if `total_enrolled == 0`.

### 5c. Desktop adaptation

Single column, max-width ~640px, centered. Hero typography scales up (Teko display ~3.5rem desktop vs ~2.4rem mobile). Game cards below the Join CTA may break to 3-up grid above 768px (Bootstrap `md`) since they're already responsive in `_game_card.html`.

### 5d. Real-data sources

| Element | Source |
|---|---|
| `{N} competitors` | `WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()` |
| Game card list | `available_games(None)` + `coming_soon_games()` from `games.registry` |

---

## 6. State 2 — Pre-deadline (`_home_pre.html`)

### 6a. Layout (mobile-first)

```
[GREET]
  Welcome back to the fiefdom — {display_name}
  
  The Council
  Awaits
  (Teko, "Awaits" gold-gradient)
  
  {Weekday} ◆ {court_line — derived} ◆ {N days|hours|minutes} to kickoff

[COUNTDOWN CARD]
  By Decree of the Commish No 001        2026 WC
  
       Tribute Due In
  
   ┌──┐  ┌──┐  ┌──┐  ┌──┐
   │02│  │14│  │36│  │09│
   └──┘  └──┘  └──┘  └──┘
   Days  Hours  Min   Sec
  
  Once group stage begins, all picks lock.
  
  [⚙ REVIEW & EDIT MY ROSTER]
  
  📜 House Rules    📋 Scoring

[DOSSIER SLOT — three variants]
  if not is_enrolled        → _join_cta_card.html
  if enrolled, not sealed   → _submit_picks_cta.html
  if enrolled and sealed    → _ballot_card.html (9-flag grid)

[OPENING MATCHES — sec-head: "Opening Matches" + "Schedule ›" link]
  (up to 3 fixture cards from next_3_matches)

[COMPACT GAME TILES STRIP — 3 tiles, 1 row]
  ⚽ World Cup [ROSTER OPEN | SEALED]
  🏈 CFB · Sep 3
  ⛳ Golf · 2027

[_commish_note.html — ignore missing]
[_dispatches.html — ignore missing]

[footer voice strip — base.html]
```

### 6b. Decisions encoded

- **Three ballot-card states** (data-driven, three partials):
  1. `is_enrolled = False` → `_join_cta_card.html`
  2. `is_enrolled = True AND picks_submitted = False` → `_submit_picks_cta.html` ("Seal Your Roster" warm gold card)
  3. `is_enrolled = True AND picks_submitted = True` → `_ballot_card.html` (the green sealed-roster grid)
- **Countdown card** (per D8): server renders initial DD/HH/MM/SS; `static/js/countdown.js` ticks every second; reads `data-deadline-utc="2026-06-11T19:00:00Z"`. Reloads page when countdown reaches zero (forces fresh state detection on next request).
- **Greet display name**: `enrollment.get_display_name()` (handles fallback to username); if no enrollment yet (unenrolled-pre case), reads `current_user.get_display_name()`.
- **Court-line dynamic copy**: "Thursday ◆ Tribute window open ◆ 2 days to kickoff" — weekday auto-derived from `datetime.now(WORLDCUP_TZ).strftime('%A')`. "2 days to kickoff" derived from time-to-deadline; flips to "1 day", "today", "tonight" as deadline approaches. Lives in `_context_pre()` as a single `court_line` string.
- **Opening Matches**: `WorldCupMatch.query.filter(kickoff_utc.isnot(None)).order_by(kickoff_utc).limit(3)`. Fixture card structure ports from design's `FixtureCard`. "Schedule ›" link goes to `/worldcup/schedule`.
- **Compact game tiles**: WC tile shows "ROSTER OPEN" (or "SEALED" if user has submitted). CFB/Golf show date hints from `coming_soon_games()` — date strings hard-coded in template ("Sep 3", "2027") because registry doesn't carry launch-date metadata. Acceptable tech debt; flag for Spec D when CFB launches.
- **Commish's Note + Dispatches** render at the bottom; both `ignore missing`.

### 6c. Desktop adaptation

Single column, max-width ~640px. Countdown card cells scale up (~4rem on desktop). Compact game tiles strip stays 3-across. Opening Matches cards widen but keep stacked layout — no two-column on desktop.

### 6d. Real-data sources

| Element | Source |
|---|---|
| `display_name` (greet) | `enrollment.get_display_name()` or `current_user.get_display_name()` |
| Countdown deadline | `TOURNAMENT_DEADLINE_UTC` (constant) |
| Court line | computed in `_context_pre()` |
| Ballot card flags | `picks` join `WorldCupTeam` ordered by tier; flag emoji from `team.flag_emoji` property |
| Opening matches | `WorldCupMatch.query` ordered by `kickoff_utc` ASC, limit 3 |
| Game tiles | `joined_games(user)` + `coming_soon_games()` |

---

## 7. State 3 — Live (`_home_live.html`)

The most data-rich state. Mobile single column + a desktop two-column variant per design's `home-desktop.jsx`.

### 7a. Mobile layout

```
[GREET]
  Council is in session — {display_name}
  
  Your Dossier
  (Teko, "Dossier" gold-gradient)
  
  {Weekday} ◆ {stage_label} ◆ {trend_phrase}

[DOSSIER SLOT]
  if not is_enrolled → _view_cta_card.html
  if enrolled       → _dossier_card.html

[DOSSIER CARD]
  ◈ Classified · CCC ◈
  
  #47
  of 1,240 competitors
  ▲ Up 12 this week
  
  ── Rank · last 7 days ──   78 → 47
  [SVG sparkline]
  
  ┌────────┬────────┬────────┐
  │  284   │  9 / 9 │  +18   │
  │ Points │  Alive │ This Wk│
  └────────┴────────┴────────┘

[LEADERBOARD PREVIEW — sec-head: "Leaderboard" + "Full ledger ›"]
  ① BracketBaron   412 PTS
     "Paid tribute. Paid off."
  ② GeezerFC       398 PTS
     "Still warm. Still winning."
  ③ Cmsh_Drew      389 PTS
     "Played the favorites."
  • • •
  ㊼ King Towsk YOU 284 PTS
     "Climbed 12 · the Commish takes notes."

[RECENT RESULTS — sec-head: "Recent Results" + "All fixtures ›"]
  (up to 5 most-recent completed matches; foot row only if
   home/away intersects user's roster)

[_commish_note.html — ignore missing]
[_dispatches.html — ignore missing]

[COMPACT GAME TILES STRIP]
  ⚽ World Cup · LIVE · #47
  🏈 CFB · Sep 3
  ⛳ Golf · 2027

[footer voice strip — base.html]
```

### 7b. Desktop layout (≥992px)

Two-column, 60/40 split (≈ Bootstrap `col-lg-7` + `col-lg-5`):

```
[GREET — full width]
[DOSSIER CARD — left col, wide horizontal layout, inline sparkline]   |  [LEADERBOARD PREVIEW]
[RECENT RESULTS — left col, 3-up grid of fixture cards]               |  [COMMISH'S NOTE — full height]
                                                                       |  [DISPATCHES]
[COMPACT GAME TILES STRIP — full width]
```

Left column owns time-sensitive data (dossier, recent results); right column owns social/narrative (leaderboard, notes, dispatches).

### 7c. Decisions encoded

- **Dossier card** is the single biggest port from the design. Renders rank, "of N competitors", week-over-week trend, 7-day sparkline (SVG, ~40 lines server-side rendered Jinja, ports from `shared.jsx`'s `RankSparkline`), and 3-stat strip. All fields populated from `_context_live()`'s `dossier` dict. If snapshot history has fewer than 7 entries (early days of tournament), sparkline renders what's available with a "tracking starts {first_snapshot_date}" caption fallback. If 0 snapshots, sparkline block is suppressed entirely.
- **Dossier "Alive" stat**: count picks where `team.is_eliminated == False`. Format `"9 / 9"` mobile, `"9 of 9"` desktop. Color-coded: gold if all alive, bone if any eliminated, red-tinted if half or more eliminated.
- **Dossier "This Week" delta**: computed as `current_total_score - score_7_days_ago` from snapshot history. Format with sign: `+18`, `+6`, `0`, `-3`. Green if positive, neutral if zero, red if negative.
- **Leaderboard preview**: top 3 + user's row + "• • •" separator if user is outside top 3. Implementation: leaderboard query ordered by `total_score DESC`. The "you" row is suppressed if user is unenrolled.
- **Tagline strings (per D11)**: pure-function helper `home_context._tagline_for(rank, week_delta, alive_count)` returns one of a finite set:
  - Rank 1: `"Paid tribute. Paid off."`
  - Rank 2 or 3 with all alive: `"Still warm. Still winning."`
  - Rank 2 or 3 otherwise: `"Played the favorites."`
  - You row, week_delta_rank ≤ -10: `"Climbed N · the Commish takes notes."`
  - You row, week_delta_rank between -9 and -1: `"Climbing N spots quietly."`
  - You row, week_delta_rank == 0: `"Holding steady."`
  - You row, week_delta_rank between 1 and 9: `"Slipped N spots. The Commish notices."`
  - You row, week_delta_rank ≥ 10: `"Down N · the Commish averts his eyes."`
  - All other rows: tagline omitted
- **Recent Results card**: ports from design's `MatchCard` but always shows final scores, never live ones. The `your_pick_results` data structure marks each match with `roster_match: {team: 'USA', tier_label: 'Favorite ×1.0', points: 3.0}` if the home or away team is on the user's roster; foot row renders only when present. For unenrolled users, foot row never renders.
- **Recent results data**: `WorldCupMatch.query.filter_by(is_completed=True).order_by(match_number.desc()).limit(5)`. No live polling; page reload is the refresh mechanism.
- **No live MatchCards** (per D1). Live scores live at `/worldcup/schedule` (Spec C territory).
- **Greet's court-line dynamic copy**: weekday + stage label ("Group Stage · Matchday X" / "Round of 32" / "Round of 16" / "Quarterfinals" / "Semifinals" / "Final") + trend phrase ("you're climbing" / "you're holding" / "you're slipping"). Stage label derived from the most recent completed match's `stage` field. Lives in `_context_live()` as a single `court_line` string.

### 7d. Real-data sources

| Element | Source |
|---|---|
| Rank, "of N" | leaderboard query position + `count()` |
| Week-delta rank/points, sparkline | `WorldCupRankSnapshot` last 7 daily rows |
| Points | `enrollment.total_score` |
| Alive count | `len([p for p in picks if not p.team.is_eliminated])` |
| Top 3 + you | leaderboard query |
| Recent results | `WorldCupMatch.query.filter_by(is_completed=True).order_by(match_number.desc()).limit(5)` |
| Roster intersection | `picks.team_id` set checked against each match's `home_team_id`/`away_team_id` |
| Court line + stage label | computed in `_context_live()` from most-recent-completed match.stage |

---

## 8. State 4 — Post-WC (`_home_post.html`)

User logged in, match #104 marked complete. ~6-week window from Jul 19 → Sep 3 (CFB launch). Per D2: champion banner + podium + roster recap.

### 8a. Layout (mobile-first)

```
[GREET]
  The Court has adjourned — {display_name}
  
  The 2026
  World Cup
  (Teko display, "World Cup" gold-gradient)
  
  That's a wrap ◆ {champion_team.display_name} took it ◆
  the Commish closes the ledger

[CHAMPION BANNER — full-bleed]
  ◈ 2026 FIFA WORLD CUP CHAMPIONS ◈
  
        🇧🇷  (large flag, ~120px, gold radial halo behind)
  
        BRAZIL
  (Teko, gold-gradient, ~3rem)
  
  Defeated Argentina 3–2 in extra time
  Final · Estadio Azteca · 19 Jul 2026

[FINAL PODIUM — sec-head: "The Final Standings" + "Full ledger ›"]
       ┌──┐
       │② │     ┌──┐
       │  │     │① │     ┌──┐
       │  │     │  │     │③ │
       │412│   │487│     │389│
       └──┘     │   │     └──┘
                 └──┘

[ROSTER RECAP SLOT]
  if not is_enrolled → _view_cta_card.html
  if enrolled       → _your_roster_recap (full)

[YOUR ROSTER RECAP]
  You finished
  #47 of 1,240
  
  284 points · climbed 31 spots         ← suppressed if no snapshot data
  
  ── Your Nine Nations ──
  
  🇺🇸 USA   Favorite     R16       +12
  🇲🇽 MEX   Favorite     Group     +3
  🇧🇷 BRA   Contender    Champion  +88   ← gold-tinted row
  🇩🇪 GER   Dark Horse   QF        +24
  🇵🇹 POR   Dark Horse   R16       +10
  🇦🇷 ARG   Wildcard     Final     +56
  🇯🇵 JPN   Underdog     R32       +8
  🇪🇨 ECU   Underdog     R16       +20
  🇰🇷 KOR   Wildcard     Group     +0
  
  [VIEW FULL LEADERBOARD →]

[_commish_note.html — ignore missing]
[_dispatches.html — ignore missing]

[COMPACT GAME TILES STRIP]
  ⚽ World Cup · COMPLETED
  🏈 CFB · Sep 3
  ⛳ Golf · 2027

[footer voice strip — base.html]
```

### 8b. Decisions encoded

- **Champion banner is the focal point.** Full-bleed visual (no card outline), large flag, "Champions" eyebrow, country name in gold-gradient Teko, supporting one-line summary. The supporting line auto-renders from `final_match` data: `f"Defeated {loser.display_name} {winner_score}–{loser_score}{extra_time_or_pks_suffix}"`. Suffix examples: ` in extra time`, ` on penalties`, or empty for regulation. If admin somehow enters draw for the final (impossible per FIFA but defensive), supporting line falls back to "World Cup Champions" alone.
- **Champion data sources**: `final_match = WorldCupMatch.query.filter_by(match_number=104).first()`. `champion_team = final_match.winner_team`. Reads `extra_time` and `penalties` flags for the suffix logic. If `winner_team_id` is null, post state still renders but champion banner falls back to "Champion pending" placeholder.
- **Subtle gold glow animation** on the champion banner: CSS `@keyframes` halo pulse, ~4s loop, low intensity. Pure CSS, no JS, reduced-motion respect via `@media (prefers-reduced-motion: reduce)`.
- **Final podium**: top 3 by `total_score DESC`. Visual treatment is a 3-tier podium (CSS, no images): #1 center elevated, #2 left, #3 right. Each tier shows `display_name` + final points. No taglines here — keeps it ceremonial. Mobile: podium stacks vertically as 1/2/3 with #1 first below 480px.
- **Your roster recap** lists all 9 picks in tier order, showing: flag, FIFA code, tier name (per `world_cup_countries.py`'s `TIERS[N]['name']`), `best_finish` from `WorldCupTeam`, points scored from `pick.multiplied_points`. The row whose team is `champion_team_id` gets a gold-accent treatment (background tint + gold left border).
- **"climbed N spots" sub-line**: derived from snapshot history if available — first snapshot rank vs final rank. If snapshots are missing or sparse, this line is suppressed and only `"284 points"` renders.
- **WC tile in compact strip** shows `"COMPLETED"` status pill. The strip's per-game label is data-driven from registry status; this requires the registry's WC entry status to flip from `'open'` to `'completed'` post-tournament. **This is manual** (Brad updates `games/registry.py` and deploys). Could be automated by reading `worldcup_state()` from the registry helper, but that's scope creep — flagged for a Spec D registry-cleanup pass.

### 8c. Desktop adaptation

Single column, max-width ~640px, centered. Champion banner is full-bleed (escapes the column to span ~960px max-width). Final podium stays 3-up horizontally on desktop. Roster recap stays as a vertical table.

### 8d. Real-data sources

| Element | Source |
|---|---|
| Champion team + flag | `WorldCupMatch.query.filter_by(match_number=104).first().winner_team` |
| Final score line | `final_match.home_score`, `away_score`, `extra_time`, `penalties` |
| Top 3 podium | leaderboard query, top 3 |
| Your final rank | leaderboard query position |
| Climbed N spots | first snapshot vs latest snapshot |
| Roster recap rows | `WorldCupPick.query.filter_by(enrollment_id=...).join(WorldCupTeam).order_by(tier)` |
| Per-pick points | `pick.multiplied_points` |
| Per-pick best finish | `team.best_finish` |
| Tier name labels | `TIERS[tier]['name']` from `world_cup_countries.py` |

---

## 9. Component CSS strategy + tokens

### 9a. Layered architecture (extends Spec A)

Spec A established `tokens.css` (Layer 1) → `style.css :root` (Layer 2) → `body.game-*` (Layer 3) → components (Layer 4). Spec B adds Layer 4 components and three Layer 1 tokens. **No Layer 2 changes.**

### 9b. New section in `style.css`

Single section, inserted after the existing `/* === CCC ADMIN EYEBROW === */` block (ends ~line 268) and before `/* === GOLF PICK 'EM === */` (starts line 269) — keeps all platform/CCC chrome sections grouped together, with game-specific sections following:

```css
/* === HOME (CCC) ============================================== */
/* Components used by core/main/templates/main/_home_*.html      */
/* Ported from fantasy-platform-and-world-cup-design/project/    */
/*   styles/app.css, scoped under .home-shell to avoid           */
/*   collisions with platform components.                        */
```

Estimated size: ~600–700 lines, ~25 component classes. All scoped under a `.home-shell` wrapper class on the outer container of every `_home_*.html` partial — prevents leakage into game interiors. The wrapper sets the page-level background (purple-950 with vignette for `live`/`pre`/`out`, slightly different gradient for `post`).

### 9c. Component classes (porting map)

Direct ports from design's `app.css` (rename only where collision risk exists):

| Design class | Our class | Used in |
|---|---|---|
| `.greet`, `.greet-line`, `.greet-title`, `.greet-court` | same names, scoped under `.home-shell` | all logged-in states |
| `.metal-text` | **`.home-metal-text`** (Spec A reserves `.metal-text` for future global use) | greet titles, podium #1 |
| `.decree`, `.decree-seal`, `.decree-body`, `.decree-days`, `.d-cell`, `.decree-cta`, `.decree-links` | same | pre-state countdown |
| `.dossier`, `.dossier-stamp`, `.dossier-row`, `.dossier-rank`, `.dossier-sparkline`, `.dossier-meta`, `.d-meta` | same | live-state dossier |
| `.sec-head`, `.sec-head .t`, `.sec-head .more` | same | section headers |
| `.match-card`, `.match-head`, `.match-body`, `.match-foot`, `.m-side`, `.m-flag`, `.m-name`, `.m-score`, `.m-center`, `.live-pill` | same — but **only `final` and `kickoff-pending` variants used** (no live/HT pills, per D1) | recent results, opening matches |
| `.rolls`, `.roll-row`, `.roll-rank`, `.roll-name`, `.roll-hand`, `.roll-pts`, `.roll-dots`, `.roll-you-chip`, `.roll-row.you` | same | leaderboard preview |
| `.dispatches`, `.dispatch`, `.dispatch-num`, `.dispatch-text`, `.dispatch-time`, `.dispatch.yours`, `.dispatch.pool` | same | `_dispatches.html` |
| `.flourish`, `.flourish .fix` | same — only used in `_home_out.html` per Spec A footer policy | logged-out hero bottom |
| `.out-hero`, `.out-eyebrow`, `.out-title`, `.out-sub`, `.out-props`, `.out-prop`, `.out-prop-icon`, `.out-prop-text` | same | logged-out hero |
| `.join`, `.join-head`, `.seal`, `.count`, `.join-title`, `.join-sub`, `.join-cta`, `.join-alt` | same | logged-out join CTA |
| `.court-games`, `.cg`, `.cg.active`, `.cg.soon`, `.cg .g`, `.cg .n`, `.cg .p` | same | compact game tiles strip |

New classes for undesigned post-state and partial-specific pieces:

| Class | Purpose |
|---|---|
| `.champion-banner`, `.champion-flag`, `.champion-name`, `.champion-summary`, `.champion-glow` | post-state champion banner |
| `.podium`, `.podium-tier`, `.podium-tier--first`, `.podium-tier--second`, `.podium-tier--third` | post-state final podium |
| `.roster-recap`, `.roster-recap-row`, `.roster-recap-row--champion` | post-state roster recap table |
| `.commish-note`, `.commish-note-byline` | `_commish_note.html` |
| `.cta-card`, `.cta-card--join`, `.cta-card--view`, `.cta-card--seal` | unenrolled CTAs + submit-picks CTA |

The "new" rows are where the **`/frontend-design:frontend-design` skill earns its keep** during implementation. Direct-port classes don't need it.

### 9d. New Layer 1 tokens (added to `tokens.css`)

```css
/* Spec B additions */
--live-orange:        #FF8A3C;   /* recent-results status accent */
--podium-glow:        radial-gradient(circle, rgba(242,211,107,.5) 0%, transparent 70%);
--champion-glow:      radial-gradient(circle, rgba(242,211,107,.4) 0%, transparent 60%);
```

Three new tokens. Lives at the bottom of `tokens.css` under a `/* Spec B additions */` comment so the Spec A boundary stays visible.

### 9e. Sparkline, countdown, microinteractions

- **Sparkline**: pure SVG, rendered server-side from snapshot data via Jinja (~40 lines that produce the same output as design's `RankSparkline`). No JS, no client-side compute. Empty/short data falls back to a static "tracking starts {date}" line.
- **Countdown**: ~25 lines vanilla JS in `static/js/countdown.js`, loaded only on `_home_pre.html` via a `{% block scripts %}` override. Reads `data-deadline-utc` attribute. Reloads page when countdown hits zero.
- **Champion glow**: pure CSS `@keyframes`, gold halo pulse, 4s loop, low intensity. Respects `prefers-reduced-motion`.
- **Hover/focus**: card-style links get the existing `transform: translateY(-2px)` lift on hover (matches Spec A auth buttons). Compact game tiles get a subtle gold underline on hover.

---

## 10. Snapshot infrastructure

### 10a. Model addition

```python
# games/worldcup/models.py
class WorldCupRankSnapshot(db.Model):
    """Daily snapshot of each enrollment's rank + total_score.
    
    Written by `flask worldcup snapshot-ranks`, run nightly via cron.
    Powers the live-state dossier sparkline and week-delta calculations.
    """
    __tablename__ = 'worldcup_rank_snapshot'
    
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey('worldcup_enrollment.id'),
        nullable=False, index=True
    )
    captured_at = db.Column(db.DateTime, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Float, nullable=False)
    
    enrollment = db.relationship('WorldCupEnrollment', backref='rank_snapshots')
    
    __table_args__ = (
        db.UniqueConstraint(
            'enrollment_id', 'captured_at',
            name='unique_worldcup_snapshot_per_day'
        ),
    )
```

`captured_at` stored as midnight CT for the day captured (date-equivalent precision; the unique constraint enforces one row per enrollment per day).

### 10b. Migration

Generated via `flask db migrate -m "add worldcup rank snapshot"` after model add. Single new table, no FK changes to existing tables, no destructive ops. Reversible.

### 10c. CLI command

```python
# games/worldcup/cli.py
@worldcup_cli.command('snapshot-ranks')
@click.option('--backfill', type=int, default=0,
              help='Backfill N past days (one snapshot per day)')
def snapshot_ranks(backfill: int):
    """Capture today's rank + score snapshot for every enrollment.
    
    Idempotent: re-running for the same day is a no-op.
    With --backfill N, writes snapshots for the past N days using the
    current rank/score (best-effort backfill for first deploy).
    """
    days_to_capture = list(range(backfill, -1, -1)) if backfill else [0]
    
    for days_ago in days_to_capture:
        target_day = (
            datetime.now(WORLDCUP_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=days_ago)
        )
        captured_at_utc = target_day.astimezone(timezone.utc)
        
        enrollments = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(WorldCupEnrollment.total_score.desc())
            .all()
        )
        
        rows_added = 0
        for rank, enr in enumerate(enrollments, start=1):
            existing = WorldCupRankSnapshot.query.filter_by(
                enrollment_id=enr.id, captured_at=captured_at_utc
            ).first()
            if existing:
                continue
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_at=captured_at_utc,
                rank=rank,
                total_score=enr.total_score,
            ))
            rows_added += 1
        
        db.session.commit()
        click.echo(f'Snapshot for {captured_at_utc.date()} — {rows_added} new rows')
```

### 10d. Cron entry

Added to `deploy/crontab.txt`:

```
# Worldcup: daily rank snapshot at midnight CT
# 05:05 UTC = 00:05 CST (winter) or 23:05 CDT prior day (summer); this offset
# gives any midnight match-result processing time to settle before snapshotting.
5 5 * * * cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks >> /var/log/fantasy-platform/snapshot.log 2>&1
```

### 10e. Backfill helper for first deploy

`flask worldcup snapshot-ranks --backfill 7` writes 7 daily snapshots backdated using the current rank/score. Lets Brad seed the table on first deploy so the sparkline has data on Day 1. Best-effort backfill (all 7 days will have identical rank/score since we don't have historical data); after the first nightly cron run, real differentiation begins accumulating.

---

## 11. Verification & exit criteria

### 11a. Automated gates (must pass before merge)

**Gate 1 — Existing test suite passes + new test file passes:**
```bash
venv/bin/python -m pytest tests/
```
Expected: all 119 prior tests pass + `tests/test_home_context.py` adds ~8 unit tests (one per state × enrolled/unenrolled, plus one for `worldcup_state()`'s 3 phases).

**Gate 2 — Type checking clean:**
```bash
venv/bin/pyright
```
Expected: 0 errors.

**Gate 3 — Migration is reversible:**
```bash
FLASK_APP=app.py venv/bin/flask db upgrade
FLASK_APP=app.py venv/bin/flask db downgrade
FLASK_APP=app.py venv/bin/flask db upgrade
```
Expected: clean round-trip.

**Gate 4 — Snapshot CLI works:**
```bash
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
# verify row count, then re-run, verify no new rows added (idempotency)
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
# verify 7 distinct captured_at dates per enrollment
```

**Gate 5 — App boots clean in dev:**
```bash
cd ../fantasy-platform-ccc-home
mkdir -p instance/
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run
```
Expected: every page returns 200, all four home states render correctly per the manual checklist below, no console errors.

### 11b. Manual visual checklist (15 surfaces)

Implementer marks pass/fail in the PR description.

| # | State / Surface | What to verify |
|---|---|---|
| 1 | `/` logged-out | Hero "The Fix Is In", three value props (last one says "Read the Commish's Note"), Join CTA links to register, full game cards below, no social-proof block |
| 2 | `/` logged-in pre + enrolled + sealed roster | Greet, countdown ticking, ballot card with 9 flags links to `/worldcup/picks?edit=1`, opening matches strip, compact game tiles, footer voice strip |
| 3 | `/` logged-in pre + enrolled + no picks yet | Same shell as #2 but ballot slot is "Seal Your Roster" CTA card |
| 4 | `/` logged-in pre + unenrolled | Same shell, dossier slot = "Join the World Cup pool →" CTA |
| 5 | `/` logged-in live + enrolled (mock past deadline via WC_FAKE_NOW) | Dossier with rank/sparkline/stats, leaderboard preview top-3 + you row, recent results with roster-overlap foots, compact game tiles |
| 6 | `/` logged-in live + unenrolled | Same shell, dossier slot = "View the World Cup →" CTA, no leaderboard "you" row |
| 7 | `/` logged-in post + enrolled (mock final completed) | Champion banner with flag/name/summary, podium, your-roster recap with champion-row gold accent |
| 8 | `/` logged-in post + unenrolled | Same shell, recap slot = "View the World Cup →" CTA |
| 9 | Compact game tiles | All three logged-in states (pre/live/post) show 3 tiles; WC label updates per state ("ROSTER OPEN" or "SEALED" pre, "LIVE · #N" live, "COMPLETED" post) |
| 10 | Countdown | Tick visible, refreshes page when reaching zero, falls back gracefully if JS disabled (server-rendered initial values still visible) |
| 11 | Sparkline | Renders with 7 data points; with <7 points renders partial line + "tracking starts" caption; with 0 points the dossier suppresses the sparkline block entirely |
| 12 | Mobile responsive | All four states usable on 375×667 viewport; horizontal scroll never appears; compact game tiles strip stays one row |
| 13 | Desktop live state | Two-column layout activates at ≥992px; left column = dossier+results, right column = leaderboard+notes+dispatches |
| 14 | Reduced motion | Champion glow + sparkline animations respect `prefers-reduced-motion: reduce` |
| 15 | Footer voice strip | Renders unchanged across all four states (Spec A chrome) |

### 11c. State-mocking helpers for verification (Gate 5 setup)

To verify states 5–8 in dev without waiting for real time/data:

- **Force live state**: set env var `WC_FAKE_NOW=2026-06-12T00:00:00Z` (read by `_now_utc()` in `state.py`, gated by `ENVIRONMENT == 'development'`).
- **Force post state**: in dev shell, manually set match #104 to `is_completed = True` with a `winner_team_id`.
- **Seed snapshots for sparkline test**: `flask worldcup snapshot-ranks --backfill 7` after seeding test enrollments.

The `WC_FAKE_NOW` env var override is a small dev-only seam in `worldcup_state()` — costs ~3 lines, gated by `ENVIRONMENT` check, never executes in production. Worth it because the alternative (editing `TOURNAMENT_DEADLINE_UTC` and committing) creates real risk of a stray commit hitting prod.

### 11d. Out of scope for verification

- No Lighthouse perf gate.
- No formal a11y audit; reduced-motion respect is the hard a11y deliverable.
- No production smoke test as part of merge (separate deploy operation per CLAUDE.md).
- No CFB/Golf home behavior changes — registry tiles only.

### 11e. Post-merge actions

1. Run `/claude-md-management:revise-claude-md` to capture session learnings.
2. Worktree cleanup: `git worktree remove ../fantasy-platform-ccc-home`.
3. **Deploy-time (handled by deploy plan, not Spec B merge):** the snapshot cron entry is already wired into `docs/superpowers/plans/2026-04-21-production-deployment.md` Task 25 Step 2. When Brad resumes the deploy plan at Task 11 and works through to Task 25, the snapshot job ships as part of normal cron setup. No separate action required at Spec B merge time.
4. Brad runs `flask worldcup snapshot-ranks --backfill 7` on production once after Task 25 completes (already noted in the deploy plan's Task 25 sidebar) to seed history.
5. If proceeding straight to Spec C, branch `redesign/ccc-worldcup` off `main` after Spec B merges.

---

## 12. Risks & open items at spec close

| Risk | Mitigation |
|---|---|
| Admin doesn't mark match #104 complete promptly → home stays in "live" forever | Brad accepts this operational dependency (per D7). Document in deployment runbook; consider adding a date-based fallback in a future spec if it bites. |
| Snapshot cron silently fails on production → sparkline never updates | Snapshot CLI logs to `/var/log/fantasy-platform/snapshot.log`; UptimeRobot or equivalent could ping a snapshot-status route in a future spec. For now, manual log check during first week post-deploy. |
| Backfill seeds 7 identical snapshots → sparkline is a flat line on Day 1 | Acceptable — the dossier copy frames it honestly ("tracking starts {date}"). Real differentiation begins accumulating after first nightly cron. |
| Snapshot cron only runs on production once the deploy plan resumes (Task 25) → if production deploy resumes shortly before WC kickoff (June 11), launch-day sparkline starts empty | Acceptable per Brad's stated sequencing (B → C → API → resume deploy). The "tracking starts {date}" copy fallback already handles this. Earlier production resume = richer sparkline at launch; no spec change needed either way. |
| `TIERS[N]['name']` from `world_cup_countries.py` is the canonical tier-name source for roster recap; if those strings change later, two surfaces (picks UI + home recap) shift in lockstep | Single source of truth, no duplication; mitigation is just discipline. |
| Hard-coded "Sep 3" / "2027" date strings in compact game tiles will rot when CFB launches | Flagged for Spec D registry-cleanup pass — registry should carry launch-date metadata then. Until then, manual edit during launch. |
| Champion banner CSS animation may be heavy on low-end mobile | Already mitigated via `prefers-reduced-motion`; intensity tuned low; spot-check on real device during Gate 5. |
| Spec C's WC reskin may need to consume the same recent-results data shape we're building here | If so, extract the recent-results query into a shared service helper (`games/worldcup/services/recent_results.py`) during Spec C — out of scope for B. |

No open items requiring resolution before implementation begins.

---

## 13. Implementation guidance

### 13a. Suggested execution order

1. **Snapshot infrastructure first** (model + migration + CLI). It's the hardest-to-rollback piece and the most easily verifiable in isolation.
2. **State detection helper** (`worldcup_state()` + dev-only `WC_FAKE_NOW`). Unit-tested in `test_home_context.py`. Once green, all four states can be force-rendered for visual development.
3. **Data assembly module** (`home_context.py` with all four `_context_*` builders). Unit tests cover each builder's dict shape.
4. **Route rewrite + index.html shell**. Verify all four states render *something* (even before partial templates exist) by stubbing partials with placeholder text.
5. **Logged-out state first** (`_home_out.html` + new component CSS). Most independent — no live-data dependencies.
6. **Pre-deadline state** (`_home_pre.html` + countdown JS + ballot variants).
7. **Live state** (`_home_live.html` + dossier + sparkline + recent results + leaderboard preview + tagline helper).
8. **Post state** (`_home_post.html` + champion banner + podium + roster recap). Most undesigned — most use of `/frontend-design:frontend-design`.
9. **Polish pass**: hover states, microinteractions, reduced-motion checks, mobile/desktop verification.

### 13b. When to invoke `/frontend-design:frontend-design`

Use it for the implementation steps where the spec goes beyond the design bundle:
- Step 8 (post-WC state — entirely undesigned)
- Wide-desktop variants of `out`/`pre`/`post` in steps 5/6/8
- Component classes marked "new" in section 9c (champion banner, podium, roster recap, commish note, CTA cards)
- The polish pass in step 9

Do NOT use it for direct ports of existing mockups (live state's mobile dossier, pre-state's countdown card, logged-out hero) — those have pixel-precise references in the bundle and benefit from faithful porting, not creative interpretation.

### 13c. Per-step verification

After each step in 13a, run:
- `venv/bin/python -m pytest tests/test_home_context.py` (after step 3)
- `venv/bin/pyright games/worldcup/services/state.py core/main/home_context.py core/main/routes.py` (after each Python-touching step)
- Manual page-load of the affected state (after each template-touching step)

Do not skip verification between steps — each step builds on the previous, and a state-detection bug in step 2 will mask as a template bug in step 5.

---

## 14. Appendix: brainstorming process record

Decisions made during brainstorming on 2026-04-28:

- D1 (live-state Match + Dispatches handling) — option B, static stand-ins
- D2 (post-WC direction) — option A primarily + option B's roster recap
- D3 (logged-out hero voice) — option B (keep voice register) + sub-option C (cut social-proof block); CTA "Join the Club"
- D4 (live-dossier data gap) — option B, snapshot table + daily cron at midnight CT
- D5 (desktop treatment) — option B, mobile-first single column for non-live; design's two-column desktop only for live
- D6 (game tiles structure) — option B, compact strip for logged-in; full cards for logged-out
- D7 (live → post boundary) — option B only, final-match completion
- D7a (unenrolled logged-in handling) — deadline-based: Join (pre-deadline) or View (post-deadline)
- D8 (countdown implementation) — option C hybrid, always DD:HH:MM:SS shape
- D9 (Commish's narrative surface) — option C two-partial split, file-edited, with seed default
- D10 (code organization) — option B, thin shell + per-state partials
- D11 (leaderboard taglines) — option B, server-derived contextual one-liners with finite string set
- D12 (frontend-design skill use) — call out in implementation guidance, scoped to non-port work
