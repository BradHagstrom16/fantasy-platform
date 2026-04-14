# Graph Report - .  (2026-04-14)

## Corpus Check
- 57 files · ~68,205 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 770 nodes · 2230 edges · 48 communities detected
- Extraction: 43% EXTRACTED · 57% INFERRED · 0% AMBIGUOUS · INFERRED: 1282 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
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

## God Nodes (most connected - your core abstractions)
1. `WorldCupEnrollment` - 88 edges
2. `User` - 87 edges
3. `CfbGame` - 87 edges
4. `WorldCupTeam` - 86 edges
5. `WorldCupMatch` - 84 edges
6. `CfbWeek` - 84 edges
7. `CfbTeam` - 83 edges
8. `GolfTournament` - 82 edges
9. `GolfEnrollment` - 80 edges
10. `WorldCupPick` - 78 edges

## Surprising Connections (you probably didn't know these)
- `CFB Survivor Pool — Routes ============================== All route handlers for` --uses--> `User`  [INFERRED]
  games/cfb/routes.py → models/user.py
- `Decorator to require admin access.` --uses--> `User`  [INFERRED]
  core/admin/routes.py → models/user.py
- `Decorator to require admin access.` --uses--> `GolfEnrollment`  [INFERRED]
  core/admin/routes.py → games/golf/models.py
- `Decorator to require admin access.` --uses--> `CfbEnrollment`  [INFERRED]
  core/admin/routes.py → games/cfb/models.py
- `Decorator to require admin access.` --uses--> `WorldCupEnrollment`  [INFERRED]
  core/admin/routes.py → games/worldcup/models.py

## Hyperedges (group relationships)
- **Fantasy Platform Game Blueprints** — claudemd_game_golf, claudemd_game_cfb, claudemd_game_worldcup [EXTRACTED 1.00]
- **World Cup Scoring System Design** — wc_scoring_system, wc_multipliers, wc_champion_bonus_rationale, wc_graduated_advancement_rationale, wc_podium_proof [EXTRACTED 1.00]
- **Group B Enhancement Features** — spec_group_b_email_util, spec_group_b_avatar, spec_group_b_forgot_pw, spec_group_b_wc_ux [EXTRACTED 1.00]
- **Nav/Subnav Design Evolution** — spec_nav_redesign, plan_nav_redesign, spec_sticky_subnav, plan_sticky_subnav [EXTRACTED 1.00]
- **Phase 4 World Cup Architecture Decisions** — adr_022, adr_023, adr_024, adr_025, adr_026, adr_027 [EXTRACTED 1.00]
- **Platform Shared Services** — claudemd_email_utility, claudemd_avatar_emoji, claudemd_two_tier_admin, claudemd_alembic, claudemd_csrf [INFERRED 0.85]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (116): init_cmd(), populate_teams_cmd(), process_match_cmd(), Seed teams + matches (fresh setup convenience command)., Recalculate all scores from match results (idempotent)., Print tournament state summary., Enter a match result and recalculate scores., Register World Cup CLI commands with the Flask app. (+108 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (105): check_wd_cmd(), _make_api_and_sync(), CFB Survivor Pool — CLI Commands =================================== Flask CLI c, Import season schedule from API., Sync field for upcoming tournament., Sync results for just-completed tournament., Finalize earnings for completed tournaments that haven't been finalized yet., Check for withdrawals in active tournament. (+97 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (107): _calculate_week_dates(), _get_special_week_info(), _import_games_for_week(), CFB Survivor Pool — Automation Service ========================================, Create the next week, import games, and activate it.      Idempotent: skips if t, Fetch latest odds and update spreads for the active week's games.      Skips gam, Send a plain-text admin notification to the platform email address., Find incomplete weeks past deadline and auto-process scores.      Returns a stat (+99 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (56): ADR-016: Email Notifications (Game-Specific to Shared), ADR-018: CFB Admin Authorization, ADR-022: World Cup as Go-Live Trigger, ADR-023: World Cup Design-First Approach, ADR-024: World Cup Score Storage (Denormalized), ADR-025: World Cup Match Pre-Seeding (104 matches), ADR-026: World Cup Leaderboard Public Access, ADR-027: World Cup Admin Scoping (Enrollment) (+48 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (48): admin_activate_week(), admin_advancement(), admin_all_picks(), admin_apply_scores(), admin_complete_week(), admin_dashboard(), admin_delete_game(), admin_fetch_scores() (+40 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (28): calculate_projected_earnings(), deadline_has_passed(), format_deadline(), format_score_to_par(), format_week_for_title(), get_cfp_active_teams(), get_cfp_available_teams_for_user(), get_cfp_eliminated_teams() (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.2
Nodes (24): _build_recap_html(), _build_recap_plain_text(), build_reminder_email(), _build_reminder_html(), _cfb_html_button(), _cfb_html_week_card(), _cfb_html_wrapper(), format_time_remaining() (+16 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (18): autopick_cmd(), Update spreads from The Odds API., Process auto-picks for users who missed the deadline., Send pick reminders for the active week., Print season summary., Register CFB CLI commands with the Flask app., Execute a sync mode and print results., Unified CFB automation CLI -- run weekly tasks by mode. (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (16): ADR-001: Modular Monolith Architecture, ADR-003: Flask Framework Choice, ADR-006: Alembic / Flask-Migrate Tooling, ADR-007: Bootstrap 5.3 + Jinja2 Frontend, Architecture Decision Log, Rationale: Modular Monolith (right-sized for 20-30 users), Alembic / Flask-Migrate Migration Convention, Fantasy Sports Platform (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (3): admin_required(), Decorator to require admin access., reset_password()

### Community 10 - "Community 10"
Cohesion: 0.21
Nodes (10): get_active_tournaments(), _get_event_timezone(), get_just_completed_tournament(), get_recently_completed_tournaments(), get_tournaments_pending_finalization(), get_upcoming_tournament(), get_upcoming_tournaments_window(), _parse_tee_time() (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (2): _make_enrolled_user_with_picks(), test_wc_index_shows_youre_in_post_deadline()

### Community 12 - "Community 12"
Cohesion: 0.2
Nodes (9): lookup_by_name(), 2026 FIFA World Cup Fantasy Pool — Country Data ================================, Look up a team by any known name (official, display, or alias).      Returns the, Return all teams in the given tier (1-5), sorted by name., Return all teams in the given group (A-L), in draw order., Verify data integrity. Raises AssertionError on any issue., teams_in_group(), teams_in_tier() (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (1): CFB Survivor Pool — Services ================================ Game logic, API in

### Community 15 - "Community 15"
Cohesion: 0.53
Nodes (5): Config, DevelopmentConfig, ProductionConfig, Fantasy Sports Platform - Configuration ========================================, TestingConfig

### Community 16 - "Community 16"
Cohesion: 0.5
Nodes (3): create_app(), Fantasy Sports Platform - Application Factory ==================================, Create and configure the Flask application.

### Community 17 - "Community 17"
Cohesion: 0.5
Nodes (1): add avatar_emoji to users  Revision ID: 6ca93808bcd2 Revises: 8c282ed0beac Creat

### Community 18 - "Community 18"
Cohesion: 0.5
Nodes (1): add is_admin to golf_enrollment  Revision ID: 8c282ed0beac Revises: bd07defd2be6

### Community 19 - "Community 19"
Cohesion: 0.5
Nodes (1): add CFB Survivor models  Revision ID: c65c548ea245 Revises: 9744be4c108a Create

### Community 20 - "Community 20"
Cohesion: 0.5
Nodes (1): add World Cup Fantasy Pool models  Revision ID: bd07defd2be6 Revises: f38ecaec82

### Community 21 - "Community 21"
Cohesion: 0.5
Nodes (1): initial: shared User model  Revision ID: a6bd9748bf4d Revises:  Create Date: 202

### Community 22 - "Community 22"
Cohesion: 0.5
Nodes (1): add golf pick em models  Revision ID: 9744be4c108a Revises: a6bd9748bf4d Create

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (1): add golf_tournament recap_email_sent flag  Revision ID: 4bcfd710a229 Revises: c6

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (1): add cfb_week recap_email_sent flag  Revision ID: f38ecaec8224 Revises: 4bcfd710a

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (3): utils/email.py ============== Shared platform email helper.  All platform-level, Send a transactional platform email.      Args:         to_addr:    Recipient em, send_platform_email()

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (2): Get the number of players in the tournament field., Check if tournament has a sufficient field size for picks.

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (1): CFB Survivor Pool — Constants ================================ FBS master team l

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - Flask Extensions =====================================

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - WSGI Entry Point =====================================

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): World Cup Fantasy Pool — Match Schedule ========================================

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (2): ADR-004: SQLite Database (Phase 1), SQLAlchemy 2.0.48

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (2): CSS position:sticky Approach (vs fixed/JS), Rationale: position:sticky over fixed or JS IntersectionObserver

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Derive Unicode flag emoji from the FIFA code.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Platform home page — shows available games.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): requests >=2.32.0

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): CSRF Protection Convention

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): POST-Only State Mutation Convention

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): ADR-005: PythonAnywhere Hosting

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): ADR-019: CFB State-Changing Routes (POST + CSRF)

## Knowledge Gaps
- **99 isolated node(s):** `Fantasy Sports Platform - Configuration ========================================`, `Fantasy Sports Platform - Flask Extensions =====================================`, `Fantasy Sports Platform - Application Factory ==================================`, `Create and configure the Flask application.`, `Fantasy Sports Platform - WSGI Entry Point =====================================` (+94 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 28`** (2 nodes): `extensions.py`, `Fantasy Sports Platform - Flask Extensions =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `wsgi.py`, `Fantasy Sports Platform - WSGI Entry Point =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `match_schedule.py`, `World Cup Fantasy Pool — Match Schedule ========================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `ADR-004: SQLite Database (Phase 1)`, `SQLAlchemy 2.0.48`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `CSS position:sticky Approach (vs fixed/JS)`, `Rationale: position:sticky over fixed or JS IntersectionObserver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Derive Unicode flag emoji from the FIFA code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Platform home page — shows available games.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `requests >=2.32.0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `CSRF Protection Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `POST-Only State Mutation Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `ADR-005: PythonAnywhere Hosting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `ADR-019: CFB State-Changing Routes (POST + CSRF)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CFB Survivor Pool — Routes ============================== All route handlers for` connect `Community 1` to `Community 0`, `Community 9`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `User` connect `Community 0` to `Community 1`, `Community 6`, `Community 9`, `Community 14`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `CfbTeam` connect `Community 2` to `Community 0`, `Community 1`, `Community 14`, `Community 7`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 84 inferred relationships involving `WorldCupEnrollment` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`WorldCupEnrollment` has 84 INFERRED edges - model-reasoned connections that need verification._
- **Are the 79 inferred relationships involving `User` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`User` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Are the 81 inferred relationships involving `CfbGame` (e.g. with `CFB Survivor Pool — Services ================================ Game logic, API in` and `CFB Survivor Pool — Utilities ================================ Timezone helpers`) actually correct?**
  _`CfbGame` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Are the 83 inferred relationships involving `WorldCupTeam` (e.g. with `TestGroupWin` and `TestGroupDraw`) actually correct?**
  _`WorldCupTeam` has 83 INFERRED edges - model-reasoned connections that need verification._