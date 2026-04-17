# Per-Game Enrollment Design

**Date:** 2026-04-17
**Status:** Approved (brainstorming complete, pending implementation plan)
**Author:** Brad Hagstrom (with Claude Code)

---

## Context

The fantasy platform hosts three games — World Cup, CFB Survivor, Golf Pick 'Em — but the user-facing enrollment flow is inconsistent:

- **World Cup** has an explicit `/join` route that users must POST to before they can submit picks.
- **Golf** silently auto-creates a `GolfEnrollment` row the first time a user submits a pick (`games/golf/routes.py:358-361`), and again on several admin paths.
- **CFB** has no user-facing enrollment path at all — `CfbEnrollment` is constructed only via seed scripts or direct DB work.

At the UX layer, the platform navbar hardcodes all three games for every user regardless of membership, and the homepage hardcodes `url: None` for "coming soon" games in `core/main/routes.py:26-41`. There is no first-class notion of "game availability."

The goal is to make per-game enrollment an explicit, uniform, user-initiated action — one that scales to future games (game 4, 5, N) without rework.

## Goals

1. Enrolling in one game never enrolls the user in another.
2. Every live game uses the same explicit `/join` flow (World Cup's current pattern).
3. Homepage and nav reflect per-user membership: only joined games appear in the navbar; the homepage shows "Your Leagues" / "Available to Join" / "Coming Soon" sections driven by actual enrollment and game status.
4. Game availability (`coming_soon` / `open` / `closed` / `completed`) is a first-class concept, controlled from a single file per deploy.
5. Adding game N+1 requires implementing a blueprint and adding one registry entry — nothing else.

## Non-Goals

- No user-initiated unenroll. If a user needs out, a platform admin handles it manually.
- No abstract `BaseEnrollment` model; each game keeps its own table.
- No admin UI to flip `GAME_STATUS` at runtime — it's a deploy-time constant for now.
- No changes to scoring, picks, leaderboards, or game-admin dashboards beyond what's required to gate them behind enrollment + status.

## Key Decisions (brainstorming outcomes)

| Decision | Choice |
|---|---|
| Target scope | Architectural (consistent `/join`) **+** scale-focused (reusable pattern for future games) |
| Nav/homepage UX | Hybrid: enrolled-only navbar, unified homepage with "Joined ✓" vs "Join" states |
| Game availability control | Per-game config flag exposed through a shared `games/registry.py` |
| Non-joined landing | Marketing landing + gated interiors, **leaderboards remain publicly viewable** |
| Existing Golf + CFB enrollment data | Wipe on deploy — these games are not live |
| Admin enroll capability | Yes — platform-admin-only tool to add user to a league |
| User-initiated unenroll | No |
| Architectural approach | Registry + per-game blueprint ownership (no shared core `/leagues/` blueprint, no abstract base model) |
| `/join` mid-flow UX | Redirect to `/<game>/join?next=<original_url>` (no modal) |
| Featured game slot | Retained — `is_featured: bool` flag in registry; World Cup keeps hero treatment |

## Architecture

### The Registry (`games/registry.py`)

Single source of truth for game metadata and status. Consumed by:

- `core/main/routes.py` (homepage game list)
- `templates/base.html` (nav — via a context processor)
- `core/admin/enrollments.py` (admin enroll form)
- Any future game-discovery UI

```python
# games/registry.py
from dataclasses import dataclass
from typing import Callable, Literal, Optional

GameStatus = Literal['coming_soon', 'open', 'closed', 'completed']

@dataclass(frozen=True)
class GameRegistryEntry:
    slug: str                 # 'worldcup', 'cfb', 'golf'
    display_name: str
    description: str
    emoji: str
    status: GameStatus
    is_featured: bool
    blueprint_index: str      # url_for endpoint, e.g. 'worldcup.index'
    blueprint_join: str       # e.g. 'worldcup.join'
    get_enrollment: Callable[[int], Optional[object]]  # (user_id) -> current-season Enrollment | None
    admin_enroll: Callable[[int], object]              # (user_id) -> Enrollment (idempotent)

GAMES: list[GameRegistryEntry] = [
    GameRegistryEntry(
        slug='worldcup',
        display_name='2026 FIFA World Cup',
        description='Pick 9 national teams across 5 tiers. Points accumulate as your teams win and advance through the bracket.',
        emoji='⚽',
        status='open',
        is_featured=True,
        blueprint_index='worldcup.index',
        blueprint_join='worldcup.join',
        get_enrollment=_worldcup_enrollment_for,
        admin_enroll=_worldcup_admin_enroll,
    ),
    GameRegistryEntry(
        slug='cfb',
        display_name='CFB Survivor Pool',
        description='Weekly college football picks against the spread. Two lives. Last survivor wins.',
        emoji='🏈',
        status='coming_soon',
        is_featured=False,
        blueprint_index='cfb.index',
        blueprint_join='cfb.join',
        get_enrollment=_cfb_enrollment_for,
        admin_enroll=_cfb_admin_enroll,
    ),
    GameRegistryEntry(
        slug='golf',
        display_name="Golf Pick 'Em",
        description='Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
        emoji='⛳',
        status='coming_soon',
        is_featured=False,
        blueprint_index='golf.index',
        blueprint_join='golf.join',
        get_enrollment=_golf_enrollment_for,
        admin_enroll=_golf_admin_enroll,
    ),
]
```

**Helper functions** the rest of the app consumes:

- `games_for_user(user) -> list[tuple[GameRegistryEntry, Optional[Enrollment]]]` — every game paired with that user's current-season enrollment.
- `joined_games(user) -> list[GameRegistryEntry]` — just the ones they're enrolled in (current season). Powers nav.
- `available_games(user) -> list[GameRegistryEntry]` — `status='open'` games the user hasn't joined. Powers homepage "Available to Join" section.
- `coming_soon_games() -> list[GameRegistryEntry]` — powers homepage "Coming Soon" section.
- `featured_games(user) -> list[GameRegistryEntry]` — `is_featured=True`, respecting user membership state. Powers hero card.

### Status Semantics

| Status | Homepage | Nav | `/join` | Interior routes |
|---|---|---|---|---|
| `coming_soon` | Shown in "Coming Soon" section, dimmed, no CTA | Hidden | 403-style redirect with flash | 404 for non-platform-admins |
| `open` | Joined → "Your Leagues"; not joined → "Available to Join" | Shown if enrolled | Full flow | Enrolled passes; non-enrolled redirects to `/<game>/join?next=<url>` |
| `closed` | Joined → "Your Leagues" (no new joins possible); not joined → hidden from homepage | Shown if enrolled | Rejected with "season closed" message | Enrollees have full access; non-enrollees 403 |
| `completed` | Joined → "Your Leagues" (read-only badge); others → optional "History" section | Shown if enrolled | Rejected | Read-only for enrollees |

### Seasonal Cycle

`status` is **not** a game's permanent lifecycle — it's "is the current season accepting new members?". Past seasons remain archived in the DB via `season_year` on each `<Game>Enrollment` table.

Concrete example: CFB plays 2026-27, then flips `open → closed` mid-season when picks lock, then `closed → completed` at season end. For 2027-28, the CFB module bumps its `SEASON_YEAR` constant and flips `completed → open`. All 2026-27 enrollments stay in the DB — they power leaderboard history, admin queries, and past-standings views. But every user's homepage shows them as "not joined" for the new season and they must re-join through `/join`.

All status transitions are one-line constant flips. No DB migrations. No admin UI (yet).

### Per-Game `/join` Flow

**World Cup** — no functional change; it's the template.
- `games/worldcup/routes.py:179-202` keeps its current `/join` GET+POST.
- Add `@game_must_be_open('worldcup')` guard at the top.
- Add `games/worldcup/services/enrollment.py` with `get_enrollment(user_id)` + `admin_enroll(user_id)` callables that the registry imports.

**CFB** — net new:
- New route `@cfb_bp.route('/join', methods=['GET', 'POST'])` in `games/cfb/routes.py`.
- New template `games/cfb/templates/cfb/join.html` mirroring WC's join (title, description, entry fee, CTA), using CFB palette (crimson `#C5050C` + midnight `#0f0f1a`).
- POST creates `CfbEnrollment(user_id=current_user.id, season_year=SEASON_YEAR)`.
- No game-specific join-time fields (CFB picks are weekly, not upfront).
- New `games/cfb/services/enrollment.py` exposing the two registry callables.
- `@game_must_be_open('cfb')` guard.

**Golf** — net new + refactor:
- New route `@golf_bp.route('/join', methods=['GET', 'POST'])` in `games/golf/routes.py`.
- New template `games/golf/templates/golf/join.html` using Augusta palette (green `#006747` + gold `#b8993e`).
- POST creates `GolfEnrollment(user_id=current_user.id, season_year=season_year)`.
- **Delete implicit auto-enroll** at `games/golf/routes.py:354-361` (submit-pick), `:585-587` (`admin_update_payment`), `:660-662` (`admin_override_pick`). Replace with: if `enrollment is None`, redirect to `/golf/join?next=<original_url>`.
- Admin paths that previously auto-enrolled now route through the admin-enroll tool (Section below) or flash a "user must join first" message.
- New `games/golf/services/enrollment.py`.
- `@game_must_be_open('golf')` guard.

### Shared Decorators (`games/common.py`)

```python
def game_must_be_open(slug: str):
    """Redirect with flash if the game's registry status != 'open'.
    Applied to /join routes and any enrollment-mutating routes."""

def enrollment_required(slug: str):
    """Redirect to /<slug>/join?next=<original_url> if the current user has
    no current-season enrollment for this game. Applied to interior routes
    (picks, game-admin, etc.)."""
```

Both decorators read from `games.registry` for slug → metadata lookup.

### Homepage (`core/main/routes.py`)

Rewrite `index()` to drive off the registry:

- **Logged out**: hero card for every `featured_games()` entry with `status='open'`; grid card for every other `open` game; dimmed card for every `coming_soon_games()` entry. All CTAs route through `/register?next=/<game>/join`.
- **Logged in**: three sections, each rendered only if non-empty:
  1. **Your Leagues** — `joined_games(current_user)`. Big cards with "Play Now" CTA → `{game.blueprint_index}`.
  2. **Available to Join** — `available_games(current_user)`. Medium cards with "Join the League" CTA → `{game.blueprint_join}`.
  3. **Coming Soon** — `coming_soon_games()`. Dimmed cards with a context line ("Available after the 2026 World Cup final"). No CTA.

Featured games render as hero cards when they appear in "Your Leagues" or "Available to Join" — featured is a rendering variant, not a separate list.

New partial: `templates/main/_game_card.html` — takes a game entry + state (`joined | available | coming_soon | logged_out`) and renders the appropriate variant. Keeps `main/index.html` thin.

### Navbar (`templates/base.html:40-53`)

Replace the three hardcoded `<li>` entries with a loop over `nav_games` (platform context processor):

```jinja
{% for game in nav_games %}
  <li class="nav-item">
    <a class="nav-link {% if request.blueprint == game.slug %}active{% endif %}"
       href="{{ url_for(game.blueprint_index) }}">{{ game.display_name }}</a>
  </li>
{% endfor %}
```

Context processor lives in `core/main/__init__.py` (or a new `core/context.py` — implementation plan's call). Returns `joined_games(current_user)` for authenticated users, `[]` for anonymous. Logged-out users and zero-joined users see only the brand + person dropdown; the homepage becomes the lobby.

### Admin Add-User-to-League

New platform-admin tool (not per-game), at `/admin/enrollments` (`core/admin/enrollments.py`).

**UI:** single form with three fields:
- User dropdown (all users, searchable by username/email)
- Game dropdown (populated from registry; only `status='open'` entries)
- Submit

**Behavior:**
- POST dispatches on `game.slug` and calls `game.admin_enroll(user_id)` from the registry — idempotent.
- If the user already has a current-season enrollment, flash "already enrolled" with a link to that user's enrollment.
- On success, flash with a link back to the game's leaderboard.

**Why platform-admin only:** cross-game enrollment management belongs at the platform tier; game-specific admins keep their game-specific dashboards.

Scope: ~80 lines of Python + one template.

## Data Migration

One-shot cleanup script, run once after deploy.

**Location:** `scripts/wipe_pre_launch_enrollments.py` (standalone, not a Flask CLI command — easier to diff in the PR).

**What it does:**
1. Deletes all `CfbEnrollment` rows + dependent `CfbPick` rows (cascade or explicit).
2. Deletes all `GolfEnrollment` rows + dependent `GolfPick` rows.
3. Leaves `WorldCupEnrollment` untouched — WC is live.
4. Leaves `User` rows untouched — users stay; only memberships reset.
5. Prints a summary: rows deleted per table.

**Guardrails:**
- `--confirm` flag required to actually run. Default is dry-run, printing what would be deleted.
- Aborts with a loud error if any `CfbWeek`/`CfbGame`/`GolfTournament` rows have `is_completed=True` for the current season (indicates real play, not test data).
- Wrapped in a single transaction; failure rolls back.

**Deploy ordering:**
1. Merge + deploy new code (registry, `/join` routes, gating, homepage rewrite).
2. Run the wipe script with `--confirm`.
3. Done.

Wiping *after* deploy ensures gating is in place — no one can create new Golf/CFB enrollments between the wipe and the code going live.

## Future-Game Checklist (Update `.claude/skills/add-game/SKILL.md`)

Adding game N+1 must include:

1. **`SEASON_YEAR` constant** in the game's module (existing standard).
2. **`<Game>Enrollment` model** with at minimum `user_id`, `season_year`, `is_admin`, `has_paid`, `total_score`, and a unique constraint on `(user_id, season_year)`.
3. **`games/<game>/services/enrollment.py`** exposing:
   - `get_enrollment(user_id) -> Optional[<Game>Enrollment]` (current season)
   - `admin_enroll(user_id) -> <Game>Enrollment` (idempotent)
4. **`/<game>/join` route** — GET renders `<game>/join.html`; POST creates enrollment; guarded by `@game_must_be_open('<game>')`.
5. **`<game>/join.html` template** — standard structure (title, description, entry fee, optional game-specific fields, submit button, game palette).
6. **Registry entry** in `games/registry.py` with `status='coming_soon'` by default.
7. **Interior routes** guarded with `@enrollment_required('<game>')`.

The two decorators plus the registry cover ~95% of the boilerplate.

## Testing Strategy

**Unit / service tests**
- `tests/test_registry.py` — `games_for_user`, `joined_games`, `available_games`, `coming_soon_games`, `featured_games` across (logged-out / zero-joined / one-joined / all-joined) × (all 4 statuses).
- `tests/test_enrollment_gating.py` — `@game_must_be_open` and `@enrollment_required` decorators: 403/redirect/pass-through behavior across each status × enrollment combo.

**Route tests**
- `tests/test_join_flows.py` — one test class per game:
  - Logged out → `/<game>/join` redirects to login with `?next=` preserved.
  - Logged in + `coming_soon` → flash + redirect to homepage.
  - Logged in + `open` + not joined → GET renders form; POST creates enrollment; duplicate POST shows "already enrolled".
  - Logged in + joined → GET redirects to dashboard.
- `tests/test_golf_auto_enroll_removed.py` — regression: hitting `/golf/submit-pick/<id>` when not enrolled redirects to `/golf/join?next=/golf/submit-pick/<id>` and does NOT create an enrollment row.

**Admin tests**
- `tests/test_admin_enrollments.py` — platform admin can add a user to any `open` game; non-admin gets 403; already-enrolled user shows graceful message; `coming_soon` games absent from dropdown.

**Manual UX verification (documented in PR)**
- Homepage as logged-out / zero-joined / one-joined / all-joined user.
- Nav reflects membership in all four states.
- `frontend-design` skill invoked for homepage card partials and `/join` templates — design-forward output verified before merge.

No Playwright/Selenium — everything runs under `pytest` against the existing harness.

## Implementation Sequencing (for the plan)

Rough dependency order (the implementation plan will refine):

1. `games/registry.py` + helpers + `games/common.py` decorators.
2. World Cup enrollment service + guard (smallest lift — it's already the template).
3. Golf `/join` + remove auto-enroll + enrollment service.
4. CFB `/join` + enrollment service.
5. Platform context processor + navbar loop.
6. Homepage rewrite (requires `frontend-design` for card partials).
7. Admin add-user-to-league page.
8. Wipe script.
9. Add-game skill update.
10. Tests (can interleave earlier, but the full suite lands last).

## Open Questions

None currently. All major decisions captured above during brainstorming.

## Files Touched (anticipated)

**New**
- `games/registry.py`
- `games/common.py`
- `games/worldcup/services/enrollment.py`
- `games/cfb/services/enrollment.py`
- `games/cfb/templates/cfb/join.html`
- `games/golf/services/enrollment.py`
- `games/golf/templates/golf/join.html`
- `core/admin/enrollments.py` (+ template)
- `templates/main/_game_card.html`
- `scripts/wipe_pre_launch_enrollments.py`
- `tests/test_registry.py`
- `tests/test_enrollment_gating.py`
- `tests/test_join_flows.py`
- `tests/test_golf_auto_enroll_removed.py`
- `tests/test_admin_enrollments.py`

**Modified**
- `games/worldcup/routes.py` (guard + extract enrollment helper)
- `games/golf/routes.py` (new `/join` + remove auto-enroll + interior guards)
- `games/cfb/routes.py` (new `/join` + interior guards)
- `core/main/routes.py` (homepage rewrite)
- `templates/base.html` (nav loop)
- `templates/main/index.html` (homepage sections)
- `core/main/__init__.py` or new `core/context.py` (nav_games context processor)
- `.claude/skills/add-game/SKILL.md` (enrollment contract checklist)
