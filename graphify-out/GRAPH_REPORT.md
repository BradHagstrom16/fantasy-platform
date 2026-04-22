# Graph Report - .  (2026-04-21)

## Corpus Check
- 98 files · ~108,265 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1029 nodes · 2391 edges · 64 communities detected
- Extraction: 56% EXTRACTED · 44% INFERRED · 0% AMBIGUOUS · INFERRED: 1062 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Superpowers CLI Rationale|Superpowers CLI Rationale]]
- [[_COMMUNITY_CFB Automation & Scheduling|CFB Automation & Scheduling]]
- [[_COMMUNITY_World Cup Scoring Tests|World Cup Scoring Tests]]
- [[_COMMUNITY_Game Blueprint Routes|Game Blueprint Routes]]
- [[_COMMUNITY_Architecture Decision Records|Architecture Decision Records]]
- [[_COMMUNITY_CLI Commands|CLI Commands]]
- [[_COMMUNITY_Stats Hub Design Concepts|Stats Hub Design Concepts]]
- [[_COMMUNITY_Email Reminder Services|Email Reminder Services]]
- [[_COMMUNITY_Auth Routes|Auth Routes]]
- [[_COMMUNITY_Registry Tests|Registry Tests]]
- [[_COMMUNITY_Enrollment Join Flow Tests|Enrollment Join Flow Tests]]
- [[_COMMUNITY_Architecture Decision Records II|Architecture Decision Records II]]
- [[_COMMUNITY_Stats Hub Tests|Stats Hub Tests]]
- [[_COMMUNITY_Homepage Section Tests|Homepage Section Tests]]
- [[_COMMUNITY_World Cup Admin Tests|World Cup Admin Tests]]
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
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]

## God Nodes (most connected - your core abstractions)
1. `User` - 122 edges
2. `CfbGame` - 89 edges
3. `GolfEnrollment` - 87 edges
4. `GolfTournament` - 86 edges
5. `CfbWeek` - 86 edges
6. `CfbTeam` - 84 edges
7. `CfbPick` - 80 edges
8. `GolfTournamentField` - 78 edges
9. `GolfPick` - 75 edges
10. `GolfTournamentResult` - 70 edges

## Surprising Connections (you probably didn't know these)
- `Game Blueprint: Golf Pick 'Em` --references--> `games/golf/services/enrollment.py`  [INFERRED]
  CLAUDE.md → games/golf/services/enrollment.py
- `Game Blueprint: World Cup` --references--> `World Cup Models (Match/Team/Pick/Enrollment)`  [INFERRED]
  CLAUDE.md → games/worldcup/models.py
- `ScoreEvent Dataclass + compute_team_score_events + compute_match_attribution` --shares_data_with--> `World Cup Models (Match/Team/Pick/Enrollment)`  [INFERRED]
  docs/superpowers/specs/2026-04-16-test-script-fixes-design.md → games/worldcup/models.py
- `Self-Join SQL Pattern for Pick Combos` --implements--> `get_tier_combos()`  [INFERRED]
  docs/superpowers/specs/2026-04-21-worldcup-stats-hub-design.md → games/worldcup/services/stats.py
- `Human End-to-End Test Script` --references--> `login() Route`  [INFERRED]
  Human End-to-End Test Script.md → core/auth/routes.py

## Hyperedges (group relationships)
- **Phase 4 World Cup Architecture Decisions** — adr_022, adr_023, adr_024, adr_025, adr_026, adr_027 [EXTRACTED 1.00]
- **Nav/Subnav Design Evolution** — spec_nav_redesign, plan_nav_redesign, spec_sticky_subnav, plan_sticky_subnav [EXTRACTED 1.00]
- **April 2026 Test Script Fix Surfaces** — spec_tiebreaker_hide, spec_ct_caption, spec_scoring_attribution, spec_auto_winner, spec_completed_matches_card, spec_clear_knockout [EXTRACTED 1.00]
- **Per-Game Enrollment Architecture** — concept_game_registry, concept_games_common, concept_worldcup_enrollment_service, concept_cfb_enrollment_service, concept_golf_enrollment_service, concept_core_context [EXTRACTED 1.00]
- **Group B Enhancement Features** — spec_group_b_email_util, spec_group_b_avatar, spec_group_b_forgot_pw, spec_group_b_wc_ux [EXTRACTED 1.00]
- **Post-Deadline UI States** — concept_deadline_passed, concept_tournament_deadline, spec_youre_in_card, spec_tournament_underway, plan_pd_task3_homepage, plan_pd_task4_wc_index [EXTRACTED 1.00]
- **World Cup Scoring System Design** — wc_scoring_system, wc_multipliers, wc_champion_bonus_rationale, wc_graduated_advancement_rationale, wc_podium_proof [EXTRACTED 1.00]
- **World Cup Stats Hub Feature Cluster** — stats_get_country_stats, stats_get_tier_stats, stats_get_overview_kpis, stats_get_tier_combos, worldcup_routes_stats, test_worldcup_stats_file, doc_stats_hub_plan, doc_stats_hub_design_spec, doc_new_stats_page [EXTRACTED 0.98]
- **Stats Service Layer — 4 Functions** — stats_get_country_stats, stats_get_tier_stats, stats_get_overview_kpis, stats_get_tier_combos [EXTRACTED 1.00]
- **Stats Hub Design Decisions (Public, Charts-Only, New Module)** — concept_stats_public_access, concept_chartjs_lazy_init, concept_pick_highlighting, concept_tab_persistence, concept_tier2_excluded_combos, doc_stats_hub_design_spec [EXTRACTED 0.95]
- **Auth Routes — Login/Register/Profile/Password** — auth_routes_login, auth_routes_register, auth_routes_logout, auth_routes_forgot_password, auth_routes_reset_password, auth_routes_change_password, auth_routes_profile [EXTRACTED 1.00]
- **World Cup Public Routes Cluster** — worldcup_routes_index, worldcup_routes_picks, worldcup_routes_leaderboard, worldcup_routes_player_detail, worldcup_routes_schedule, worldcup_routes_groups, worldcup_routes_rules, worldcup_routes_stats, worldcup_routes_join [EXTRACTED 1.00]
- **World Cup Admin Routes Cluster** — worldcup_routes_admin_dashboard, worldcup_routes_admin_match_result, worldcup_routes_admin_advancement, worldcup_routes_admin_recalc, worldcup_routes_admin_all_picks, worldcup_routes_admin_set_knockout, worldcup_routes_worldcup_admin_required [EXTRACTED 1.00]
- **E2E Test Coverage — World Cup Core Flows** — doc_e2e_test_script, worldcup_routes_leaderboard, worldcup_routes_picks, worldcup_routes_join, worldcup_routes_admin_match_result, worldcup_routes_admin_advancement, worldcup_routes_schedule, worldcup_routes_groups, worldcup_routes_rules [INFERRED 0.85]

## Communities

### Community 0 - "Superpowers CLI Rationale"
Cohesion: 0.05
Nodes (110): CFB Survivor Pool — CLI Commands =================================== Flask CLI c, Import season schedule from API., Sync field for upcoming tournament., Sync results for just-completed tournament., Finalize earnings for completed tournaments that haven't been finalized yet., Check for withdrawals in active tournament., Run reminder check for upcoming tournaments., Register golf CLI commands with the Flask app. (+102 more)

### Community 1 - "CFB Automation & Scheduling"
Cohesion: 0.05
Nodes (130): _calculate_week_dates(), _get_special_week_info(), _import_games_for_week(), CFB Survivor Pool — Automation Service ========================================, Create the next week, import games, and activate it.      Idempotent: skips if t, Fetch latest odds and update spreads for the active week's games.      Skips gam, Send a plain-text admin notification to the platform email address., Find incomplete weeks past deadline and auto-process scores.      Returns a stat (+122 more)

### Community 2 - "World Cup Scoring Tests"
Cohesion: 0.04
Nodes (55): _make_enrollment(), _make_match(), _make_pick(), _make_team(), _make_user(), Tests for the World Cup scoring engine. Covers: group match scoring, advancement, compute_match_attribution emits chip data for completed matches., A group stage win awards 3 base points and records W/L. (+47 more)

### Community 3 - "Game Blueprint Routes"
Cohesion: 0.04
Nodes (72): admin_activate_week(), admin_advancement(), admin_all_picks(), admin_apply_scores(), admin_complete_week(), admin_dashboard(), admin_delete_game(), admin_fetch_scores() (+64 more)

### Community 4 - "Architecture Decision Records"
Cohesion: 0.03
Nodes (72): ADR-016: Email Notifications (Game-Specific to Shared), ADR-022: World Cup as Go-Live Trigger, ADR-029: Emoji Avatar Storage (nullable String), ADR-030: Email Sending Consolidation, Rationale: Email Consolidation (Consistent From Name), Admin Destructive Actions action=clear Pattern, Two-Tier Admin Scoping Convention, Blueprint Pattern (required for all games) (+64 more)

### Community 5 - "CLI Commands"
Cohesion: 0.06
Nodes (40): autopick_cmd(), check_wd_cmd(), init_cmd(), _make_api_and_sync(), populate_teams_cmd(), process_match_cmd(), Seed teams + matches (fresh setup convenience command)., Update spreads from The Odds API. (+32 more)

### Community 6 - "Stats Hub Design Concepts"
Cohesion: 0.09
Nodes (37): Chart.js Lazy Initialization per Tab, Pick Highlighting — MY_PICKS Gold Star Feature, Portfolio Impact Bubble Scatter Chart, Self-Join SQL Pattern for Pick Combos, Stats Hub — 6-Tab Analytics Dashboard, Stats Hub Public Access (No Auth Required), Stats Hub Subnav Pill in base.html, Tab Persistence via localStorage (+29 more)

### Community 7 - "Email Reminder Services"
Cohesion: 0.21
Nodes (23): _build_recap_html(), _build_recap_plain_text(), build_reminder_email(), _build_reminder_html(), _cfb_html_button(), _cfb_html_week_card(), _cfb_html_wrapper(), format_time_remaining() (+15 more)

### Community 8 - "Auth Routes"
Cohesion: 0.08
Nodes (25): Anti-Enumeration Pattern (forgot password), forgot_password() Route, login() Route, register() Route, Anti-Enumeration Pattern for Forgot Password, Central Time Caption on Schedule Page, World Cup Launch Readiness Test Protocol, Tiebreaker Hidden Pre-Deadline (+17 more)

### Community 9 - "Registry Tests"
Cohesion: 0.14
Nodes (18): _make_user(), _mock_entry(), Unit tests for games.registry helper functions., Build a GameRegistryEntry-shaped mock with get_enrollment returning `enrollment`, test_available_games_for_anonymous_returns_all_open(), test_available_games_returns_open_not_joined(), test_cfb_admin_enroll_is_idempotent(), test_cfb_get_enrollment_returns_none_when_absent() (+10 more)

### Community 10 - "Enrollment Join Flow Tests"
Cohesion: 0.18
Nodes (18): _login(), _make_user(), Tests for /join flows across all games., CFB is seeded 'coming_soon' in registry, so /join must reject even     logged-in, Regression: an unenrolled logged-in user hitting a CFB pick route     is redirec, test_cfb_join_coming_soon_rejects_logged_in(), test_cfb_join_duplicate_redirects_to_dashboard(), test_cfb_join_open_renders_form() (+10 more)

### Community 11 - "Architecture Decision Records II"
Cohesion: 0.11
Nodes (22): ADR-018: CFB Admin Authorization, ADR-023: World Cup Design-First Approach, ADR-024: World Cup Score Storage (Denormalized), ADR-025: World Cup Match Pre-Seeding (104 matches), ADR-026: World Cup Leaderboard Public Access, ADR-027: World Cup Admin Scoping (Enrollment), ADR-028: Platform Admin Universal Override, Phase 4 Lessons Learned (+14 more)

### Community 12 - "Stats Hub Tests"
Cohesion: 0.16
Nodes (12): _make_enrollment(), _make_pick(), _make_team(), _make_user(), Stats page is public — no login required., Unauthenticated users get MY_PICKS = [] — no error., test_get_country_stats_basic(), test_get_country_stats_dict_shape() (+4 more)

### Community 13 - "Homepage Section Tests"
Cohesion: 0.19
Nodes (13): _login(), _make_user(), Tests for homepage sections + navbar game loop., When a user has joined every available (non-featured) game, 'Available to Join', A joined featured game appears only as the hero, not in Your Leagues grid., _game_card.html must render cleanly for every state value., test_game_card_partial_renders_each_state(), test_homepage_featured_not_duplicated_in_joined_grid() (+5 more)

### Community 14 - "World Cup Admin Tests"
Cohesion: 0.18
Nodes (15): _make_admin_user(), _make_enrolled_user_with_tiebreaker(), Tests for World Cup public + admin routes that depend on deadline or state guard, Seed an R16 knockout match with teams assigned; optionally completed., Create an enrollment with a known USA goals tiebreaker., Create a platform admin user and return their id., Seed two completed group matches with different update times., _seed_knockout_match_with_teams() (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.3
Nodes (12): _install_entry(), _login(), _make_user(), Tests for games.common decorators., test_enrollment_required_403_when_closed_and_not_enrolled(), test_enrollment_required_404s_coming_soon_for_regular_user(), test_enrollment_required_passes_when_enrolled(), test_enrollment_required_platform_admin_bypasses_coming_soon() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (3): admin_required(), Decorator to require admin access., reset_password()

### Community 17 - "Community 17"
Cohesion: 0.21
Nodes (10): get_active_tournaments(), _get_event_timezone(), get_just_completed_tournament(), get_recently_completed_tournaments(), get_tournaments_pending_finalization(), get_upcoming_tournament(), get_upcoming_tournaments_window(), _parse_tee_time() (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (14): ADR-001: Modular Monolith Architecture, ADR-003: Flask Framework Choice, ADR-007: Bootstrap 5.3 + Jinja2 Frontend, Architecture Decision Log, Rationale: Modular Monolith (right-sized for 20-30 users), Fantasy Sports Platform, Modular Monolith Pattern, Tech Stack (Flask/SQLite/Bootstrap) (+6 more)

### Community 19 - "Community 19"
Cohesion: 0.21
Nodes (13): core/main/routes.py index() Route, TOURNAMENT_DEADLINE_UTC Constant, Task 1: Revert TOURNAMENT_DEADLINE_UTC Post-4E, Task 2: Pass deadline_passed to Homepage Route, Task 3: Homepage Featured Card - View Standings, Task 4: WC Index CTA Block Post-Deadline States, Plan: Post-Deadline UI (2026-04-14), Homepage Sections: Your Leagues / Available / Coming Soon (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.35
Nodes (9): _login(), _make_user(), Tests for the platform-admin add-user-to-league tool., test_admin_enrollments_dropdown_excludes_coming_soon_games(), test_admin_enrollments_post_enrolls_user(), test_admin_enrollments_post_is_idempotent(), test_admin_enrollments_post_rejects_unknown_game(), test_admin_enrollments_redirects_non_admin() (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.44
Nodes (7): _login(), _make_user(), _seed_open_tournament(), test_admin_override_pick_blocks_unenrolled_user(), test_admin_update_payment_rejects_unenrolled_user(), test_make_pick_does_not_create_enrollment_when_user_not_joined(), test_make_pick_redirects_unenrolled_user_to_join()

### Community 22 - "Community 22"
Cohesion: 0.2
Nodes (9): lookup_by_name(), 2026 FIFA World Cup Fantasy Pool — Country Data ================================, Look up a team by any known name (official, display, or alias).      Returns the, Return all teams in the given tier (1-5), sorted by name., Return all teams in the given group (A-L), in draw order., Verify data integrity. Raises AssertionError on any issue., teams_in_group(), teams_in_tier() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.25
Nodes (4): _make_enrolled_user_with_picks(), Tests for post-deadline UI state across homepage and WC index., Create a user enrolled in WC with 9 picks submitted. Returns user.id., test_wc_index_shows_youre_in_post_deadline()

### Community 24 - "Community 24"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 25 - "Community 25"
Cohesion: 0.29
Nodes (6): calculate_projected_earnings(), format_score_to_par(), parse_score_to_par(), Calculate projected earnings for a player based on current position.      Uses s, Format integer score to par for display.      Args:         score: Integer score, Parse the 'total' field from SlashGolf API into an integer score to par.      AP

### Community 26 - "Community 26"
Cohesion: 0.53
Nodes (5): Config, DevelopmentConfig, ProductionConfig, Fantasy Sports Platform - Configuration ========================================, TestingConfig

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (5): Shared helpers for tests that need to patch the game registry., Rewrite a single registry entry's is_featured flag for the duration of one test., Rewrite a single registry entry's status for the duration of one test.      Robu, set_is_featured(), set_status()

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (3): create_app(), Fantasy Sports Platform - Application Factory ==================================, Create and configure the Flask application.

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (1): add avatar_emoji to users  Revision ID: 6ca93808bcd2 Revises: 8c282ed0beac Creat

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (1): add is_admin to golf_enrollment  Revision ID: 8c282ed0beac Revises: bd07defd2be6

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (1): add CFB Survivor models  Revision ID: c65c548ea245 Revises: 9744be4c108a Create

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (1): add World Cup Fantasy Pool models  Revision ID: bd07defd2be6 Revises: f38ecaec82

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (1): initial: shared User model  Revision ID: a6bd9748bf4d Revises:  Create Date: 202

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (1): add golf pick em models  Revision ID: 9744be4c108a Revises: a6bd9748bf4d Create

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (1): add golf_tournament recap_email_sent flag  Revision ID: 4bcfd710a229 Revises: c6

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (1): add cfb_week recap_email_sent flag  Revision ID: f38ecaec8224 Revises: 4bcfd710a

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (3): enrollments(), Platform admin: add a user to a game's current-season enrollment., List users + open games; on POST, call the selected game's admin_enroll.

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (3): utils/email.py ============== Shared platform email helper.  All platform-level, Send a transactional platform email.      Args:         to_addr:    Recipient em, send_platform_email()

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (2): Get the number of players in the tournament field., Check if tournament has a sufficient field size for picks.

### Community 40 - "Community 40"
Cohesion: 0.67
Nodes (1): CFB Survivor Pool — Constants ================================ FBS master team l

### Community 41 - "Community 41"
Cohesion: 0.67
Nodes (3): AVATAR_CATEGORIES Constant, profile() Route, 75 Emoji Avatar System (5 Categories)

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - Flask Extensions =====================================

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - WSGI Entry Point =====================================

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): World Cup Fantasy Pool — Match Schedule ========================================

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (2): ADR-004: SQLite Database (Phase 1), SQLAlchemy 2.0.48

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (2): CSS position:sticky Approach (vs fixed/JS), Rationale: position:sticky over fixed or JS IntersectionObserver

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
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (0): 

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): requests >=2.32.0

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): ADR-005: PythonAnywhere Hosting

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): ADR-006: Alembic / Flask-Migrate Tooling

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): ADR-019: CFB State-Changing Routes (POST + CSRF)

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): logout() Route

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): reset_password() Route

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): change_password() Route

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): index() Route — /worldcup/

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): player_detail() Route

## Knowledge Gaps
- **181 isolated node(s):** `Fantasy Sports Platform - Configuration ========================================`, `Fantasy Sports Platform - Flask Extensions =====================================`, `Fantasy Sports Platform - Application Factory ==================================`, `Create and configure the Flask application.`, `Fantasy Sports Platform - WSGI Entry Point =====================================` (+176 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 42`** (2 nodes): `extensions.py`, `Fantasy Sports Platform - Flask Extensions =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `wsgi.py`, `Fantasy Sports Platform - WSGI Entry Point =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (2 nodes): `match_schedule.py`, `World Cup Fantasy Pool — Match Schedule ========================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `ADR-004: SQLite Database (Phase 1)`, `SQLAlchemy 2.0.48`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `CSS position:sticky Approach (vs fixed/JS)`, `Rationale: position:sticky over fixed or JS IntersectionObserver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `requests >=2.32.0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `ADR-005: PythonAnywhere Hosting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `ADR-006: Alembic / Flask-Migrate Tooling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `ADR-019: CFB State-Changing Routes (POST + CSRF)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `logout() Route`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `reset_password() Route`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `change_password() Route`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `index() Route — /worldcup/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `player_detail() Route`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Superpowers CLI Rationale` to `World Cup Scoring Tests`, `Community 37`, `Registry Tests`, `Enrollment Join Flow Tests`, `Stats Hub Tests`, `Homepage Section Tests`, `World Cup Admin Tests`, `Community 15`, `Community 16`, `Community 20`, `Community 23`?**
  _High betweenness centrality (0.275) - this node is a cross-community bridge._
- **Why does `CFB Survivor Pool — Routes ============================== All route handlers for` connect `Superpowers CLI Rationale` to `Community 16`, `CFB Automation & Scheduling`, `Game Blueprint Routes`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `CfbTeam` connect `CFB Automation & Scheduling` to `Superpowers CLI Rationale`, `CLI Commands`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 114 inferred relationships involving `User` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Platform admin: add a user to a game's current-season enrollment.`) actually correct?**
  _`User` has 114 INFERRED edges - model-reasoned connections that need verification._
- **Are the 83 inferred relationships involving `CfbGame` (e.g. with `CFB Survivor Pool — Services ================================ Game logic, API in` and `Wipe pre-launch CFB + Golf enrollment data.  Usage (dry run):     venv/bin/pytho`) actually correct?**
  _`CfbGame` has 83 INFERRED edges - model-reasoned connections that need verification._
- **Are the 82 inferred relationships involving `GolfEnrollment` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`GolfEnrollment` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 78 inferred relationships involving `GolfTournament` (e.g. with `Regression tests: golf pick routes must NOT silently auto-enroll users.` and `Seed a GolfTournament with fields matching the actual model.`) actually correct?**
  _`GolfTournament` has 78 INFERRED edges - model-reasoned connections that need verification._