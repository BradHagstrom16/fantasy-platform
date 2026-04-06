# Handoff 4C — World Cup Fantasy Pool: Player-Facing UI

**Phase:** 4C (Routes + Templates + CSS for all player-facing surfaces)
**Recipient:** Claude Code
**Date:** 2026-04-05
**Prerequisite:** 4A (foundation) + 4B (scoring engine) complete and on main
**Branch:** `phase-4c-worldcup-player-ui`

---

## Context

Phases 4A and 4B built the foundation (models, migration, CLI, blueprint scaffold) and the scoring engine. This handoff builds **everything the player sees**: enrollment, pick submission, leaderboard, game dashboard, schedule, group standings, rules page, and the World Cup visual identity (CSS theming).

**Key decisions carried forward:**
- Leaderboard is **publicly accessible** — no login required (ADR-026)
- Pick submission requires login + enrollment. 1 submission/entry per user.
- Picks are editable unlimited times before `TOURNAMENT_DEADLINE_UTC` (June 11, 2026 7:00 PM UTC / 2:00 PM CT)
- After deadline: picks are locked, read-only view
- No draft saving — all 9 picks + tiebreaker submitted together
- Self-serve enrollment via join page
- CSS theming: `body.game-worldcup` with two color palette options for Brad to choose (FIFA Blue/Gold vs USA Red/White/Blue)
- Mobile-first design throughout (44px touch targets, dual-render tables, card-based pick selection, no horizontal scroll)

**Read these files before implementation:**
1. `games/worldcup/WORLD_CUP_GAME_DESIGN.md` — tier structure, scoring rules (for rules page content and pick UI labels)
2. `games/worldcup/world_cup_countries.py` — TEAMS dict (display names, tiers, groups), TIERS dict (tier names, pick counts, multipliers)
3. `games/worldcup/constants.py` — TOURNAMENT_DEADLINE_UTC, TIER_PICK_COUNTS, TOTAL_PICKS, SEASON_YEAR, ENTRY_FEE, WORLDCUP_TZ
4. `games/worldcup/routes.py` — existing decorator, context processor, stub routes to replace
5. `games/worldcup/models.py` — all 4 models
6. `games/worldcup/services/scoring.py` — `recalculate_all_scores()` (called after pick changes? No — picks don't affect scores until matches are played. But understand the data flow.)
7. `static/css/style.css` — existing design system, Golf and CFB game-specific sections (for pattern reference)
8. `templates/base.html` — the nav items already wired for worldcup
9. Golf and CFB templates — for pattern reference on pick submission, leaderboard, enrollment flows

**Skill prescription:** Use `frontend-design` skill for ALL template and CSS work in this handoff. The World Cup is the platform launch event — this needs to look polished. Read the frontend-design SKILL.md before starting template work.

---

## Scope

### Files to Create

```
games/worldcup/templates/worldcup/index.html           # Tournament dashboard (replaces placeholder)
games/worldcup/templates/worldcup/join.html             # Enrollment page
games/worldcup/templates/worldcup/picks.html            # Pick submission (pre-deadline) / view picks (post-deadline)
games/worldcup/templates/worldcup/leaderboard.html      # Full leaderboard
games/worldcup/templates/worldcup/player_detail.html    # One player's 9 picks + per-team scores
games/worldcup/templates/worldcup/schedule.html         # Match schedule with results
games/worldcup/templates/worldcup/groups.html           # 12 group standings tables
games/worldcup/templates/worldcup/rules.html            # How it works / scoring rules
```

### Files to Modify

```
games/worldcup/routes.py        # Replace stubs with full route implementations
static/css/style.css            # Add body.game-worldcup overrides + World Cup component classes
```

### Files NOT Modified

```
games/worldcup/models.py        # No schema changes
games/worldcup/constants.py     # No constant changes
games/worldcup/services/scoring.py  # No scoring changes
games/worldcup/cli.py           # No CLI changes
app.py                          # Already registered
models/__init__.py              # Already registered
templates/base.html             # Nav already wired in 4A
```

---

## Step-by-Step Instructions

### Step 1: Read Required Files

Pay special attention to:
- `world_cup_countries.py` → `TIERS` dict (has tier names, pick counts, multipliers) and `TEAMS` dict (has display names, groups)
- `constants.py` → `TIER_PICK_COUNTS` (validation), `TOURNAMENT_DEADLINE_UTC` (deadline check)
- The existing context processor in `routes.py` already provides `tournament_phase`, `worldcup_enrollment`, `body_class`, `season_year`, `entry_fee`

**Skill prescription:** Use `brainstorming` skill to plan the UX flow before coding templates. Map out: what does a new user see vs an enrolled user vs a post-deadline user?

### Step 2: CSS Theming — `body.game-worldcup`

Draft two color palette options to `static/css/style.css`. Present both to Brad using `frontend-design` skill with a visual mockup or comparison, and let him pick. Once chosen, implement the selected palette.

**Option A: FIFA Blue & Gold**

**Option B: USA Red, White & Blue**

After the palette selection, add a game-specific CSS section:

```css
/* === WORLD CUP FANTASY POOL === */
```

Include styles for:
- `.table-worldcup` — themed table with dark header, game-primary accent
- `.tier-badge` — colored badges for tier names (Favorites, Contenders, Dark Horses, Underdogs, Wildcards)
- `.tier-card` — pick submission team cards grouped by tier
- `.team-pick-card` — individual team card with display name, group, multiplier
- `.team-pick-card.selected` — selected state (accented border, checkmark)
- `.pick-summary` — pre-submit summary showing all 9 picks
- `.match-result-card` — match result display with scores
- `.group-table` — compact 4-team group standings table
- `.multiplier-badge` — small badge showing ×1, ×1.5, etc.
- `.phase-indicator` — tournament phase display (pre-tournament / group stage / knockout / completed)
- Mobile-specific overrides for team cards (stack 2 per row on mobile instead of 3-4)

**Critical:** Platform components (`.page-hero`, `.stat-block`, `.btn-game`) already consume `--game-primary` / `--game-accent` automatically. The game CSS must NOT duplicate those — only add game-specific components.

**Skill prescription:** Utilize `frontend-design` skill for this entire step.

### Step 3: Routes — Replace Stubs and Add New Routes

Replace the stub `leaderboard` and `picks` routes in `routes.py`. Add all new player-facing routes.

**Imports to add:**
```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models.user import User
from games.worldcup import worldcup_bp
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
    TIER_PICK_COUNTS, TOTAL_PICKS, WORLDCUP_TZ,
)
```

**Keep the existing:** `worldcup_admin_required` decorator, `_derive_tournament_phase()`, `inject_worldcup_globals()` context processor, `worldcup_before_request()`.

#### Route: `GET /worldcup/` — Game Dashboard

Replace the placeholder. The dashboard shows:
- Tournament status banner (phase-dependent messaging)
- If pre-tournament + not enrolled: CTA to join
- If pre-tournament + enrolled + no picks: CTA to submit picks
- If pre-tournament + enrolled + picks submitted: "You're all set!" with pick summary
- Leaderboard snapshot (top 10)
- Recent match results (last 5 completed matches)
- Quick links: full leaderboard, schedule, rules, picks

**Route logic:**
```python
@worldcup_bp.route('/')
def index():
    enrollment = None
    if current_user.is_authenticated:
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()

    # Top 10 leaderboard
    top_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .limit(10)
        .all()
    )

    # Recent results (last 5 completed)
    recent_matches = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.match_number.desc())
        .limit(5)
        .all()
    )

    # Deadline display in Central Time
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)
    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC

    total_enrolled = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()

    return render_template('worldcup/index.html',
        enrollment=enrollment,
        top_enrollments=top_enrollments,
        recent_matches=recent_matches,
        deadline_ct=deadline_ct,
        deadline_passed=deadline_passed,
        total_enrolled=total_enrolled,
    )
```

#### Route: `GET/POST /worldcup/join` — Enrollment

```python
@worldcup_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join():
    # Check if already enrolled
    existing = WorldCupEnrollment.query.filter_by(
        user_id=current_user.id, season_year=SEASON_YEAR
    ).first()
    if existing:
        flash('You are already enrolled in the World Cup Fantasy Pool!', 'info')
        return redirect(url_for('worldcup.index'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        enrollment = WorldCupEnrollment(
            user_id=current_user.id,
            season_year=SEASON_YEAR,
            display_name=display_name or None,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash('Welcome to the World Cup Fantasy Pool! Now submit your picks.', 'success')
        return redirect(url_for('worldcup.picks'))

    return render_template('worldcup/join.html')
```

#### Route: `GET/POST /worldcup/picks` — Pick Submission

This is the most complex player-facing route. Two modes:

**Pre-deadline (GET):** Show pick form with teams grouped by tier. If player has existing picks, pre-populate the form. Show tiebreaker input.

**Pre-deadline (POST):** Validate and save picks:
- Exactly 9 picks with correct tier distribution (T1=2, T2=1, T3=2, T4=2, T5=2)
- No duplicate teams
- USA goals tiebreaker is a non-negative integer
- All picks must be valid team IDs that exist in the database
- If validation passes: delete existing picks, create new picks, set `picks_submitted = True`, set `usa_goals_guess`
- Flash success and redirect to index

**Post-deadline (GET):** Show read-only view of submitted picks with current scores.

```python
@worldcup_bp.route('/picks', methods=['GET', 'POST'])
@login_required
def picks():
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=current_user.id, season_year=SEASON_YEAR
    ).first()
    if not enrollment:
        flash('Join the pool first!', 'info')
        return redirect(url_for('worldcup.join'))

    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # Get all teams grouped by tier
    teams = WorldCupTeam.query.order_by(WorldCupTeam.tier, WorldCupTeam.display_name).all()
    teams_by_tier = defaultdict(list)
    for team in teams:
        teams_by_tier[team.tier].append(team)

    # Tier metadata from world_cup_countries.py
    from games.worldcup.world_cup_countries import TIERS

    # Get existing picks
    existing_picks = WorldCupPick.query.filter_by(enrollment_id=enrollment.id).all()
    selected_team_ids = {p.team_id for p in existing_picks}

    if request.method == 'POST':
        if deadline_passed:
            flash('The pick deadline has passed. Picks are locked.', 'error')
            return redirect(url_for('worldcup.picks'))

        # Collect team IDs from form
        selected_ids = []
        for tier in range(1, 6):
            tier_picks = request.form.getlist(f'tier_{tier}')
            selected_ids.extend(int(tid) for tid in tier_picks if tid)

        usa_goals = request.form.get('usa_goals_guess', '').strip()

        # ── Validation ──
        errors = []

        # Validate USA goals tiebreaker
        if not usa_goals or not usa_goals.isdigit() or int(usa_goals) < 0:
            errors.append('USA goals tiebreaker must be a non-negative integer.')
        else:
            usa_goals = int(usa_goals)

        # Validate total picks
        if len(selected_ids) != TOTAL_PICKS:
            errors.append(f'You must select exactly {TOTAL_PICKS} teams (you selected {len(selected_ids)}).')

        # Validate no duplicates
        if len(selected_ids) != len(set(selected_ids)):
            errors.append('Duplicate team selections are not allowed.')

        # Validate tier counts
        if not errors:
            selected_teams = WorldCupTeam.query.filter(WorldCupTeam.id.in_(selected_ids)).all()
            team_map = {t.id: t for t in selected_teams}

            if len(selected_teams) != len(selected_ids):
                errors.append('One or more selected teams are invalid.')
            else:
                tier_counts = defaultdict(int)
                for tid in selected_ids:
                    tier_counts[team_map[tid].tier] += 1

                for tier_num, required in TIER_PICK_COUNTS.items():
                    actual = tier_counts.get(tier_num, 0)
                    if actual != required:
                        tier_name = TIERS[tier_num]['name']
                        errors.append(f'{tier_name} (Tier {tier_num}): requires {required} pick(s), you selected {actual}.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('worldcup/picks.html',
                enrollment=enrollment,
                teams_by_tier=dict(teams_by_tier),
                tiers=TIERS,
                selected_team_ids={int(tid) for tid in request.form.getlist('tier_1') + request.form.getlist('tier_2') + request.form.getlist('tier_3') + request.form.getlist('tier_4') + request.form.getlist('tier_5')},
                deadline_passed=deadline_passed,
                deadline_ct=deadline_ct,
                usa_goals_guess=request.form.get('usa_goals_guess', ''),
            )

        # ── Save picks ──
        # Delete existing picks
        WorldCupPick.query.filter_by(enrollment_id=enrollment.id).delete()

        # Create new picks
        for tid in selected_ids:
            team = team_map[tid]
            pick = WorldCupPick(
                enrollment_id=enrollment.id,
                team_id=tid,
                tier=team.tier,
            )
            db.session.add(pick)

        enrollment.picks_submitted = True
        enrollment.usa_goals_guess = usa_goals
        db.session.commit()

        flash('Your picks have been submitted! You can edit them anytime before the tournament starts.', 'success')
        return redirect(url_for('worldcup.index'))

    # GET — render form or read-only view
    return render_template('worldcup/picks.html',
        enrollment=enrollment,
        teams_by_tier=dict(teams_by_tier),
        tiers=TIERS,
        selected_team_ids=selected_team_ids,
        existing_picks=existing_picks,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        usa_goals_guess=enrollment.usa_goals_guess,
    )
```

**Critical validation note:** The tier validation in the POST handler and the UI tier grouping must use identical tier counts from `TIER_PICK_COUNTS`. This is the ADR-020 principle: UI filtering thresholds and server-side validation thresholds must always match exactly.

#### Route: `GET /worldcup/leaderboard` — Public Leaderboard

**No login required** (ADR-026). Anyone can view.

```python
@worldcup_bp.route('/leaderboard')
def leaderboard():
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),  # Tiebreaker: lower guess shown first (not used for ranking, just displayed)
        )
        .all()
    )

    # Assign ranks (handle ties: same score = same rank)
    ranked = []
    current_rank = 0
    prev_score = None
    for i, e in enumerate(enrollments):
        if e.total_score != prev_score:
            current_rank = i + 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
    )
```

#### Route: `GET /worldcup/leaderboard/<int:enrollment_id>` — Player Detail

Shows one player's 9 picks with per-team scores, tier multipliers, and base vs multiplied breakdown.

```python
@worldcup_bp.route('/leaderboard/<int:enrollment_id>')
def player_detail(enrollment_id):
    enrollment = db.get_or_404(WorldCupEnrollment, enrollment_id)
    picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
    )
```

#### Route: `GET /worldcup/schedule` — Match Schedule

```python
@worldcup_bp.route('/schedule')
def schedule():
    matches = (
        WorldCupMatch.query
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    # Group by stage for display
    group_matches = [m for m in matches if m.stage == 'group']
    r32_matches = [m for m in matches if m.stage == 'R32']
    r16_matches = [m for m in matches if m.stage == 'R16']
    qf_matches = [m for m in matches if m.stage == 'QF']
    sf_matches = [m for m in matches if m.stage == 'SF']
    third_place = [m for m in matches if m.stage == 'third_place']
    final = [m for m in matches if m.stage == 'final']

    return render_template('worldcup/schedule.html',
        group_matches=group_matches,
        r32_matches=r32_matches,
        r16_matches=r16_matches,
        qf_matches=qf_matches,
        sf_matches=sf_matches,
        third_place=third_place,
        final=final,
        worldcup_tz=WORLDCUP_TZ,
    )
```

#### Route: `GET /worldcup/groups` — Group Standings

```python
@worldcup_bp.route('/groups')
def groups():
    teams = WorldCupTeam.query.order_by(WorldCupTeam.group_letter).all()
    groups_dict = defaultdict(list)
    for team in teams:
        groups_dict[team.group_letter].append(team)

    # Sort each group by: points (W×3+D×1) desc, then goal diff (not tracked, so by wins desc)
    for letter in groups_dict:
        groups_dict[letter].sort(
            key=lambda t: (t.group_wins * 3 + t.group_draws, t.group_wins),
            reverse=True,
        )

    return render_template('worldcup/groups.html',
        groups=dict(sorted(groups_dict.items())),
    )
```

#### Route: `GET /worldcup/rules` — Rules Page

Static content page. Render tier table, scoring table, tiebreaker explanation, and edge cases. Content sourced from `WORLD_CUP_GAME_DESIGN.md` but written as HTML, not embedded markdown.

```python
@worldcup_bp.route('/rules')
def rules():
    from games.worldcup.world_cup_countries import TIERS
    from games.worldcup.constants import KNOCKOUT_POINTS, ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD
    return render_template('worldcup/rules.html',
        tiers=TIERS,
        knockout_points=KNOCKOUT_POINTS,
        advance_group_winner=ADVANCE_GROUP_WINNER,
        advance_runner_up=ADVANCE_RUNNER_UP,
        advance_best_third=ADVANCE_BEST_THIRD,
    )
```

#### Update Nav: Add Schedule, Groups, Rules Links

Update the `worldcup_before_request` or the nav section in `base.html` to include schedule/groups/rules nav items. Since the nav is already in `base.html`, the existing worldcup nav block needs to be expanded:

```html
{% if request.blueprint == 'worldcup' %}
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.index' %}active{% endif %}"
       href="{{ url_for('worldcup.index') }}">Dashboard</a>
</li>
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.leaderboard' %}active{% endif %}"
       href="{{ url_for('worldcup.leaderboard') }}">Leaderboard</a>
</li>
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.schedule' %}active{% endif %}"
       href="{{ url_for('worldcup.schedule') }}">Schedule</a>
</li>
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.groups' %}active{% endif %}"
       href="{{ url_for('worldcup.groups') }}">Groups</a>
</li>
{% if current_user.is_authenticated %}
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
       href="{{ url_for('worldcup.picks') }}">My Picks</a>
</li>
{% endif %}
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.rules' %}active{% endif %}"
       href="{{ url_for('worldcup.rules') }}">Rules</a>
</li>
{% endif %}
```

### Step 4: Template Implementation Notes

All templates extend `templates/base.html`. The context processor already provides `body_class = 'game-worldcup'` so game-specific CSS activates automatically.

**Skill prescription:** Use `frontend-design` skill for every template. These are the first pages real users will see on the platform.

#### `picks.html` — The Core UX

This is the most important template. Two states:

**Pre-deadline mode (picking):**
- Show teams organized by tier in expandable/collapsible sections
- Each tier section shows: tier name, multiplier, required pick count, selection count
- Teams shown as clickable cards with: display name, group letter, confederation flag/badge
- Selected teams get a visual highlight (colored border, checkmark)
- JavaScript handles card tap → toggle hidden checkbox → update selection count
- Bottom of page: USA goals tiebreaker input (number field)
- Submit button disabled until exactly 9 teams selected and tiebreaker filled
- Summary panel shows currently selected teams before submission

**Post-deadline mode (read-only):**
- Show submitted picks organized by tier
- Each pick shows: team name, tier, multiplier, base points, multiplied points
- Total score displayed prominently
- Tiebreaker guess displayed

**JavaScript requirements (vanilla JS, no build step):**
- Card selection: tap a team card → toggle `selected` class + toggle hidden input
- Per-tier counter: show "2/2 selected" or "0/1 selected" in tier headers
- Submit validation: disable submit button unless all tier counts met + tiebreaker filled
- Confirmation modal or summary before final submit (nice-to-have, not required)

**CSRF:** The pick form must include `{{ csrf_token() }}` or use Flask-WTF's hidden field pattern.

**Form structure:** Use hidden checkboxes grouped by tier:
```html
<input type="checkbox" name="tier_1" value="{{ team.id }}" class="d-none team-checkbox">
```

#### `leaderboard.html` — Public Access

- **No login required** — this page is fully public
- Table with: rank, player name (linked to detail), total points (1 decimal), tiebreaker guess
- Tied players show same rank
- Current user's row highlighted (if logged in)
- Mobile: dual-render pattern (table on desktop, cards on mobile) following the established platform pattern

#### `index.html` — Game Dashboard

Phase-dependent content:
- **Pre-tournament + not enrolled:** Hero with game description, CTA to join, pool size counter
- **Pre-tournament + enrolled:** Deadline countdown, pick status, top 10 preview
- **During tournament:** Live leaderboard snapshot, recent results, upcoming matches
- **Completed:** Final standings, champion announcement

#### `schedule.html` — Match Schedule

- Group matches shown by group (A through L)
- Knockout matches shown by round
- Completed matches show score and winner
- Upcoming matches show date/time in Central Time
- All times displayed using the `WORLDCUP_TZ` (Chicago/Central) — the template must convert from UTC stored in the database

**Time display helper:** Add a Jinja filter or pass the timezone to the template. Use:
```python
match.kickoff_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(WORLDCUP_TZ)
```
Or add a helper function to the context processor.

#### `groups.html` — Group Standings

- 12 groups in a responsive grid (3 across on desktop, 2 on tablet, 1 on mobile)
- Each group table: team name, W, D, L, Pts (calculated as W×3 + D×1)
- Teams ordered by points desc
- Advancement indicators: if `advancement_method` is set, show badge (winner/runner-up/best 3rd/eliminated)

#### `rules.html` — How It Works

Static content page with:
- Tier structure table (tier name, teams, picks, multiplier)
- Group stage scoring table
- Knockout stage scoring table
- Points per achievement by tier (the full matrix from the game design doc)
- Tiebreaker explanation
- Edge cases summary

### Step 5: Smoke Test

```bash
FLASK_APP=app.py ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    with app.test_client() as c:
        # Public routes
        r = c.get('/worldcup/')
        print(f'Dashboard: {r.status_code}')
        r = c.get('/worldcup/leaderboard')
        print(f'Leaderboard (public): {r.status_code}')
        r = c.get('/worldcup/schedule')
        print(f'Schedule: {r.status_code}')
        r = c.get('/worldcup/groups')
        print(f'Groups: {r.status_code}')
        r = c.get('/worldcup/rules')
        print(f'Rules: {r.status_code}')
        # Auth-required routes should redirect to login
        r = c.get('/worldcup/picks')
        print(f'Picks (unauth): {r.status_code} (expect 302)')
        r = c.get('/worldcup/join')
        print(f'Join (unauth): {r.status_code} (expect 302)')
print('Smoke test OK')
"
```

**Skill prescription:** Use `playwright` plugin to verify templates render correctly in a browser. Check: dashboard loads, leaderboard table displays, pick form shows tiers, rules page renders scoring tables.

**Skill prescription:** Use `pyright-lsp` plugin after all route changes.

**Skill prescription:** Use `code-simplifier` plugin after all routes and templates are working.

**Skill prescription:** Use `commit-commands` plugin: `feat: add World Cup player-facing UI (picks, leaderboard, dashboard, schedule, groups, rules)`

---

## Verification Criteria

1. ✅ `GET /worldcup/` renders tournament dashboard with phase-appropriate content
2. ✅ `GET /worldcup/join` shows enrollment form (requires login)
3. ✅ `POST /worldcup/join` creates enrollment and redirects to picks
4. ✅ `GET /worldcup/picks` shows tier-grouped team selection form (pre-deadline)
5. ✅ `POST /worldcup/picks` validates tier counts (T1=2, T2=1, T3=2, T4=2, T5=2) and rejects invalid submissions
6. ✅ `POST /worldcup/picks` saves exactly 9 picks + tiebreaker on valid submission
7. ✅ `GET /worldcup/picks` shows read-only picks with scores (post-deadline)
8. ✅ Picks can be edited unlimited times pre-deadline (old picks deleted, new ones created)
9. ✅ `GET /worldcup/leaderboard` works **without login** — fully public
10. ✅ Leaderboard shows correct ranking with tie handling
11. ✅ `GET /worldcup/leaderboard/<id>` shows player's 9 picks with per-team scores
12. ✅ `GET /worldcup/schedule` shows all 104 matches with times in Central Time
13. ✅ `GET /worldcup/groups` shows 12 group tables with W/D/L/Pts
14. ✅ `GET /worldcup/rules` renders complete scoring rules
15. ✅ `body.game-worldcup` CSS theming active on all World Cup pages
16. ✅ Two color palette options presented to Brad for selection
17. ✅ All forms include CSRF tokens
18. ✅ All state-mutating routes use POST
19. ✅ Mobile: pick cards are tappable (44px+ touch targets), tables use dual-render pattern
20. ✅ Nav items (Dashboard, Leaderboard, Schedule, Groups, My Picks, Rules) all work
21. ✅ Smoke test passes
22. ✅ `pyright` reports 0 errors

---

## Pick Validation Summary (Server-Side — Route POST Handler)

These checks must ALL pass before picks are saved. If any fail, re-render the form with error messages and preserve the user's selections:

| Check | Error Message |
|-------|--------------|
| Deadline not passed | "The pick deadline has passed. Picks are locked." |
| Exactly 9 team IDs submitted | "You must select exactly 9 teams (you selected N)." |
| No duplicate team IDs | "Duplicate team selections are not allowed." |
| All team IDs exist in DB | "One or more selected teams are invalid." |
| Tier 1: exactly 2 picks | "Favorites (Tier 1): requires 2 pick(s), you selected N." |
| Tier 2: exactly 1 pick | "Contenders (Tier 2): requires 1 pick(s), you selected N." |
| Tier 3: exactly 2 picks | "Dark Horses (Tier 3): requires 2 pick(s), you selected N." |
| Tier 4: exactly 2 picks | "Underdogs (Tier 4): requires 2 pick(s), you selected N." |
| Tier 5: exactly 2 picks | "Wildcards (Tier 5): requires 2 pick(s), you selected N." |
| USA goals tiebreaker is non-negative integer | "USA goals tiebreaker must be a non-negative integer." |
