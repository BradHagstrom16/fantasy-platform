# Graph Report - .  (2026-04-19)

## Corpus Check
- 35 files · ~99,999 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1149 nodes · 3377 edges · 58 communities detected
- Extraction: 41% EXTRACTED · 59% INFERRED · 0% AMBIGUOUS · INFERRED: 1987 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_World Cup Scoring & CLI|World Cup Scoring & CLI]]
- [[_COMMUNITY_CFB + Golf CLI|CFB + Golf CLI]]
- [[_COMMUNITY_CFB Automation Service|CFB Automation Service]]
- [[_COMMUNITY_Architecture Decision Records|Architecture Decision Records]]
- [[_COMMUNITY_Game Registry|Game Registry]]
- [[_COMMUNITY_Admin Routes|Admin Routes]]
- [[_COMMUNITY_Per-Game Enrollment Design|Per-Game Enrollment Design]]
- [[_COMMUNITY_CFB Auto-Pick Service|CFB Auto-Pick Service]]
- [[_COMMUNITY_Email Reminders|Email Reminders]]
- [[_COMMUNITY_Join-Flow Tests|Join-Flow Tests]]
- [[_COMMUNITY_Homepage Section Tests|Homepage Section Tests]]
- [[_COMMUNITY_Architecture Overview|Architecture Overview]]
- [[_COMMUNITY_Auth Routes|Auth Routes]]
- [[_COMMUNITY_World Cup Admin Tests|World Cup Admin Tests]]
- [[_COMMUNITY_Admin Enrollments Tests|Admin Enrollments Tests]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]

## God Nodes (most connected - your core abstractions)
1. `WorldCupEnrollment` - 175 edges
2. `WorldCupTeam` - 162 edges
3. `WorldCupMatch` - 159 edges
4. `WorldCupPick` - 149 edges
5. `User` - 138 edges
6. `CfbGame` - 110 edges
7. `GolfEnrollment` - 107 edges
8. `CfbWeek` - 107 edges
9. `CfbTeam` - 105 edges
10. `GolfTournament` - 103 edges

## Surprising Connections (you probably didn't know these)
- `Game Blueprint: Golf Pick 'Em` --references--> `games/golf/services/enrollment.py`  [INFERRED]
  CLAUDE.md → games/golf/services/enrollment.py
- `Game Blueprint: CFB Survivor` --references--> `games/cfb/services/enrollment.py`  [INFERRED]
  CLAUDE.md → games/cfb/services/enrollment.py
- `Game Blueprint: World Cup` --references--> `World Cup Models (Match/Team/Pick/Enrollment)`  [INFERRED]
  CLAUDE.md → games/worldcup/models.py
- `ScoreEvent Dataclass + compute_team_score_events + compute_match_attribution` --shares_data_with--> `World Cup Models (Match/Team/Pick/Enrollment)`  [INFERRED]
  docs/superpowers/specs/2026-04-16-test-script-fixes-design.md → games/worldcup/models.py
- `Platform admin: add a user to a game's current-season enrollment.` --uses--> `User`  [INFERRED]
  core/admin/enrollments.py → models/user.py

## Hyperedges (group relationships)
- **Per-Game Enrollment Architecture** — concept_game_registry, concept_games_common, concept_worldcup_enrollment_service, concept_cfb_enrollment_service, concept_golf_enrollment_service, concept_core_context [EXTRACTED 1.00]
- **April 2026 Test Script Fix Surfaces** — spec_tiebreaker_hide, spec_ct_caption, spec_scoring_attribution, spec_auto_winner, spec_completed_matches_card, spec_clear_knockout [EXTRACTED 1.00]
- **Post-Deadline UI States** — concept_deadline_passed, concept_tournament_deadline, spec_youre_in_card, spec_tournament_underway, plan_pd_task3_homepage, plan_pd_task4_wc_index [EXTRACTED 1.00]

## Communities

### Community 0 - "World Cup Scoring & CLI"
Cohesion: 0.03
Nodes (180): init_cmd(), process_match_cmd(), Seed teams + matches (fresh setup convenience command)., Recalculate all scores from match results (idempotent)., Print tournament state summary., Enter a match result and recalculate scores., Register World Cup CLI commands with the Flask app., Seed the CfbTeam table with the 2025 season's 49 teams.      This is a dev/test (+172 more)

### Community 1 - "CFB + Golf CLI"
Cohesion: 0.05
Nodes (137): CFB Survivor Pool — CLI Commands =================================== Flask CLI c, Import season schedule from API., Sync field for upcoming tournament., Sync results for just-completed tournament., Finalize earnings for completed tournaments that haven't been finalized yet., Check for withdrawals in active tournament., Run reminder check for upcoming tournaments., Register golf CLI commands with the Flask app. (+129 more)

### Community 2 - "CFB Automation Service"
Cohesion: 0.04
Nodes (151): _calculate_week_dates(), _get_special_week_info(), _import_games_for_week(), CFB Survivor Pool — Automation Service ========================================, Create the next week, import games, and activate it.      Idempotent: skips if t, Fetch latest odds and update spreads for the active week's games.      Skips gam, Send a plain-text admin notification to the platform email address., Find incomplete weeks past deadline and auto-process scores.      Returns a stat (+143 more)

### Community 3 - "Architecture Decision Records"
Cohesion: 0.03
Nodes (103): ADR-016: Email Notifications (Game-Specific to Shared), ADR-018: CFB Admin Authorization, ADR-022: World Cup as Go-Live Trigger, ADR-023: World Cup Design-First Approach, ADR-024: World Cup Score Storage (Denormalized), ADR-025: World Cup Match Pre-Seeding (104 matches), ADR-026: World Cup Leaderboard Public Access, ADR-027: World Cup Admin Scoping (Enrollment) (+95 more)

### Community 4 - "Game Registry"
Cohesion: 0.06
Nodes (45): available_games(), coming_soon_games(), featured_games(), GameRegistryEntry, games_for_user(), get_entry(), _is_authenticated(), joined_games() (+37 more)

### Community 5 - "Admin Routes"
Cohesion: 0.06
Nodes (49): admin_activate_week(), admin_advancement(), admin_all_picks(), admin_apply_scores(), admin_complete_week(), admin_dashboard(), admin_delete_game(), admin_fetch_scores() (+41 more)

### Community 6 - "Per-Game Enrollment Design"
Cohesion: 0.06
Nodes (43): .claude/skills/add-game/SKILL.md, templates/base.html Platform Base, core/context.py nav_games Context Processor, deadline_passed Derived Flag, templates/main/_game_card.html Partial, games/registry.py Module, games/common.py Shared Decorators, core/main/routes.py index() Route (+35 more)

### Community 7 - "CFB Auto-Pick Service"
Cohesion: 0.1
Nodes (27): autopick_cmd(), check_wd_cmd(), _make_api_and_sync(), populate_teams_cmd(), Update spreads from The Odds API., Process auto-picks for users who missed the deadline., Send pick reminders for the active week., Print season summary. (+19 more)

### Community 8 - "Email Reminders"
Cohesion: 0.21
Nodes (23): _build_recap_html(), _build_recap_plain_text(), build_reminder_email(), _build_reminder_html(), _cfb_html_button(), _cfb_html_week_card(), _cfb_html_wrapper(), format_time_remaining() (+15 more)

### Community 9 - "Join-Flow Tests"
Cohesion: 0.18
Nodes (18): _login(), _make_user(), Tests for /join flows across all games., CFB is seeded 'coming_soon' in registry, so /join must reject even     logged-in, Regression: an unenrolled logged-in user hitting a CFB pick route     is redirec, test_cfb_join_coming_soon_rejects_logged_in(), test_cfb_join_duplicate_redirects_to_dashboard(), test_cfb_join_open_renders_form() (+10 more)

### Community 10 - "Homepage Section Tests"
Cohesion: 0.19
Nodes (13): _login(), _make_user(), Tests for homepage sections + navbar game loop., When a user has joined every available (non-featured) game, 'Available to Join', A joined featured game appears only as the hero, not in Your Leagues grid., _game_card.html must render cleanly for every state value., test_game_card_partial_renders_each_state(), test_homepage_featured_not_duplicated_in_joined_grid() (+5 more)

### Community 11 - "Architecture Overview"
Cohesion: 0.12
Nodes (16): ADR-001: Modular Monolith Architecture, ADR-003: Flask Framework Choice, ADR-006: Alembic / Flask-Migrate Tooling, ADR-007: Bootstrap 5.3 + Jinja2 Frontend, Architecture Decision Log, Rationale: Modular Monolith (right-sized for 20-30 users), Alembic / Flask-Migrate Migration Convention, Fantasy Sports Platform (+8 more)

### Community 12 - "Auth Routes"
Cohesion: 0.14
Nodes (3): admin_required(), Decorator to require admin access., reset_password()

### Community 13 - "World Cup Admin Tests"
Cohesion: 0.28
Nodes (10): _make_admin_user(), _make_enrolled_user_with_tiebreaker(), _seed_knockout_match_with_teams(), _seed_two_completed_group_matches(), test_admin_dashboard_lists_completed_matches(), test_admin_dashboard_shows_edit_teams_for_assigned_knockout(), test_clear_knockout_blocked_when_match_completed(), test_clear_knockout_nulls_both_teams() (+2 more)

### Community 14 - "Admin Enrollments Tests"
Cohesion: 0.35
Nodes (9): _login(), _make_user(), Tests for the platform-admin add-user-to-league tool., test_admin_enrollments_dropdown_excludes_coming_soon_games(), test_admin_enrollments_post_enrolls_user(), test_admin_enrollments_post_is_idempotent(), test_admin_enrollments_post_rejects_unknown_game(), test_admin_enrollments_redirects_non_admin() (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.33
Nodes (8): admin_enroll(), get_enrollment(), Golf Pick 'Em enrollment service — registry integration point., Return the user's current-season World Cup enrollment, or None., Return the user's current-season Golf enrollment, or None., Idempotently enroll a user in the current World Cup season., Idempotently enroll a user in the current Golf season., _season_year()

### Community 16 - "Community 16"
Cohesion: 0.44
Nodes (7): _login(), _make_user(), _seed_open_tournament(), test_admin_override_pick_blocks_unenrolled_user(), test_admin_update_payment_rejects_unenrolled_user(), test_make_pick_does_not_create_enrollment_when_user_not_joined(), test_make_pick_redirects_unenrolled_user_to_join()

### Community 17 - "Community 17"
Cohesion: 0.2
Nodes (9): lookup_by_name(), 2026 FIFA World Cup Fantasy Pool — Country Data ================================, Look up a team by any known name (official, display, or alias).      Returns the, Return all teams in the given tier (1-5), sorted by name., Return all teams in the given group (A-L), in draw order., Verify data integrity. Raises AssertionError on any issue., teams_in_group(), teams_in_tier() (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (2): _make_enrolled_user_with_picks(), test_wc_index_shows_youre_in_post_deadline()

### Community 20 - "Community 20"
Cohesion: 0.29
Nodes (6): calculate_projected_earnings(), format_score_to_par(), parse_score_to_par(), Calculate projected earnings for a player based on current position.      Uses s, Format integer score to par for display.      Args:         score: Integer score, Parse the 'total' field from SlashGolf API into an integer score to par.      AP

### Community 21 - "Community 21"
Cohesion: 0.53
Nodes (5): Config, DevelopmentConfig, ProductionConfig, Fantasy Sports Platform - Configuration ========================================, TestingConfig

### Community 22 - "Community 22"
Cohesion: 0.33
Nodes (5): Shared helpers for tests that need to patch the game registry., Rewrite a single registry entry's is_featured flag for the duration of one test., Rewrite a single registry entry's status for the duration of one test.      Robu, set_is_featured(), set_status()

### Community 23 - "Community 23"
Cohesion: 0.33
Nodes (5): enrollment_required(), game_must_be_open(), Shared decorators for per-game enrollment gating. ==============================, Redirect to homepage with a flash if the game's registry status != 'open'., Gate interior routes behind a current-season enrollment.      Behavior by regist

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (3): create_app(), Fantasy Sports Platform - Application Factory ==================================, Create and configure the Flask application.

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (1): add avatar_emoji to users  Revision ID: 6ca93808bcd2 Revises: 8c282ed0beac Creat

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (1): add is_admin to golf_enrollment  Revision ID: 8c282ed0beac Revises: bd07defd2be6

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (1): add CFB Survivor models  Revision ID: c65c548ea245 Revises: 9744be4c108a Create

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (1): add World Cup Fantasy Pool models  Revision ID: bd07defd2be6 Revises: f38ecaec82

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (1): initial: shared User model  Revision ID: a6bd9748bf4d Revises:  Create Date: 202

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (1): add golf pick em models  Revision ID: 9744be4c108a Revises: a6bd9748bf4d Create

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (1): add golf_tournament recap_email_sent flag  Revision ID: 4bcfd710a229 Revises: c6

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (1): add cfb_week recap_email_sent flag  Revision ID: f38ecaec8224 Revises: 4bcfd710a

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (3): Platform-wide Jinja context processors., Attach platform-wide context processors to the Flask app., register_context_processors()

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (3): enrollments(), Platform admin: add a user to a game's current-season enrollment., List users + open games; on POST, call the selected game's admin_enroll.

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (3): utils/email.py ============== Shared platform email helper.  All platform-level, Send a transactional platform email.      Args:         to_addr:    Recipient em, send_platform_email()

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (2): Get the number of players in the tournament field., Check if tournament has a sufficient field size for picks.

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (1): World Cup Fantasy Pool — Constants ==================================== Scoring

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - Flask Extensions =====================================

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - WSGI Entry Point =====================================

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): World Cup Fantasy Pool — Match Schedule ========================================

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (2): ADR-004: SQLite Database (Phase 1), SQLAlchemy 2.0.48

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (2): CSS position:sticky Approach (vs fixed/JS), Rationale: position:sticky over fixed or JS IntersectionObserver

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Derive Unicode flag emoji from the FIFA code.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Platform home page — shows available games.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): requests >=2.32.0

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): CSRF Protection Convention

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): POST-Only State Mutation Convention

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): ADR-005: PythonAnywhere Hosting

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): ADR-019: CFB State-Changing Routes (POST + CSRF)

## Knowledge Gaps
- **145 isolated node(s):** `Fantasy Sports Platform - Configuration ========================================`, `Fantasy Sports Platform - Flask Extensions =====================================`, `Fantasy Sports Platform - Application Factory ==================================`, `Create and configure the Flask application.`, `Fantasy Sports Platform - WSGI Entry Point =====================================` (+140 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 38`** (2 nodes): `extensions.py`, `Fantasy Sports Platform - Flask Extensions =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (2 nodes): `wsgi.py`, `Fantasy Sports Platform - WSGI Entry Point =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `match_schedule.py`, `World Cup Fantasy Pool — Match Schedule ========================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `ADR-004: SQLite Database (Phase 1)`, `SQLAlchemy 2.0.48`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `CSS position:sticky Approach (vs fixed/JS)`, `Rationale: position:sticky over fixed or JS IntersectionObserver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Derive Unicode flag emoji from the FIFA code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Platform home page — shows available games.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `requests >=2.32.0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `CSRF Protection Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `POST-Only State Mutation Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `ADR-005: PythonAnywhere Hosting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `ADR-019: CFB State-Changing Routes (POST + CSRF)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `CFB + Golf CLI` to `World Cup Scoring & CLI`, `Community 34`, `Game Registry`, `Join-Flow Tests`, `Homepage Section Tests`, `Auth Routes`, `Admin Enrollments Tests`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Why does `WorldCupEnrollment` connect `World Cup Scoring & CLI` to `CFB + Golf CLI`, `CFB Automation Service`, `Join-Flow Tests`, `Homepage Section Tests`, `Auth Routes`, `Admin Enrollments Tests`, `Community 15`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `CFB Survivor Pool — Routes ============================== All route handlers for` connect `CFB + Golf CLI` to `World Cup Scoring & CLI`, `CFB Automation Service`, `Auth Routes`, `Admin Routes`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 171 inferred relationships involving `WorldCupEnrollment` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`WorldCupEnrollment` has 171 INFERRED edges - model-reasoned connections that need verification._
- **Are the 159 inferred relationships involving `WorldCupTeam` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `TestGroupWin`) actually correct?**
  _`WorldCupTeam` has 159 INFERRED edges - model-reasoned connections that need verification._
- **Are the 156 inferred relationships involving `WorldCupMatch` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `TestGroupWin`) actually correct?**
  _`WorldCupMatch` has 156 INFERRED edges - model-reasoned connections that need verification._
- **Are the 146 inferred relationships involving `WorldCupPick` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `TestGroupWin`) actually correct?**
  _`WorldCupPick` has 146 INFERRED edges - model-reasoned connections that need verification._