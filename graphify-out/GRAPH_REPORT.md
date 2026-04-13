# Graph Report - .  (2026-04-13)

## Corpus Check
- 69 files · ~62,140 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 757 nodes · 2210 edges · 45 communities detected
- Extraction: 42% EXTRACTED · 58% INFERRED · 0% AMBIGUOUS · INFERRED: 1274 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_World Cup CLI & Match Processing|World Cup CLI & Match Processing]]
- [[_COMMUNITY_World Cup Scoring Logic|World Cup Scoring Logic]]
- [[_COMMUNITY_CFB Automation & Scheduling|CFB Automation & Scheduling]]
- [[_COMMUNITY_Design Docs & Specs|Design Docs & Specs]]
- [[_COMMUNITY_Game Routes & Blueprints|Game Routes & Blueprints]]
- [[_COMMUNITY_Game Utilities & Calculations|Game Utilities & Calculations]]
- [[_COMMUNITY_Email Reminders & Notifications|Email Reminders & Notifications]]
- [[_COMMUNITY_CFB CLI & Sync Commands|CFB CLI & Sync Commands]]
- [[_COMMUNITY_Foundation ADRs|Foundation ADRs]]
- [[_COMMUNITY_Core Auth & Admin Routes|Core Auth & Admin Routes]]
- [[_COMMUNITY_World Cup Countries Data|World Cup Countries Data]]
- [[_COMMUNITY_Database Engine & Alembic|Database Engine & Alembic]]
- [[_COMMUNITY_Blueprint Init Files|Blueprint Init Files]]
- [[_COMMUNITY_App Configuration|App Configuration]]
- [[_COMMUNITY_App Factory|App Factory]]
- [[_COMMUNITY_Avatar Emoji Migration|Avatar Emoji Migration]]
- [[_COMMUNITY_Golf Admin Migration|Golf Admin Migration]]
- [[_COMMUNITY_CFB Survivor Models Migration|CFB Survivor Models Migration]]
- [[_COMMUNITY_World Cup Models Migration|World Cup Models Migration]]
- [[_COMMUNITY_Initial User Model Migration|Initial User Model Migration]]
- [[_COMMUNITY_Golf Pick Em Models Migration|Golf Pick Em Models Migration]]
- [[_COMMUNITY_Golf Email Flag Migration|Golf Email Flag Migration]]
- [[_COMMUNITY_CFB Email Flag Migration|CFB Email Flag Migration]]
- [[_COMMUNITY_Shared Email Utility|Shared Email Utility]]
- [[_COMMUNITY_Golf Tournament Models|Golf Tournament Models]]
- [[_COMMUNITY_Game Constants|Game Constants]]
- [[_COMMUNITY_Flask Extensions|Flask Extensions]]
- [[_COMMUNITY_WSGI Entry Point|WSGI Entry Point]]
- [[_COMMUNITY_World Cup Match Schedule|World Cup Match Schedule]]
- [[_COMMUNITY_SQLite Database Choice|SQLite Database Choice]]
- [[_COMMUNITY_CSS Sticky Nav Design|CSS Sticky Nav Design]]
- [[_COMMUNITY_Core Package Init|Core Package Init]]
- [[_COMMUNITY_Auth Package Init|Auth Package Init]]
- [[_COMMUNITY_Admin Package Init|Admin Package Init]]
- [[_COMMUNITY_Main Package Init|Main Package Init]]
- [[_COMMUNITY_Tests Package Init|Tests Package Init]]
- [[_COMMUNITY_Utils Package Init|Utils Package Init]]
- [[_COMMUNITY_Games Package Init|Games Package Init]]
- [[_COMMUNITY_User Model Rationale|User Model Rationale]]
- [[_COMMUNITY_World Cup Services Init|World Cup Services Init]]
- [[_COMMUNITY_Requests Library|Requests Library]]
- [[_COMMUNITY_CSRF Convention|CSRF Convention]]
- [[_COMMUNITY_POST-Only Convention|POST-Only Convention]]
- [[_COMMUNITY_PythonAnywhere Hosting|PythonAnywhere Hosting]]
- [[_COMMUNITY_CFB POST State Changes ADR|CFB POST State Changes ADR]]

## God Nodes (most connected - your core abstractions)
1. `CfbGame` - 87 edges
2. `WorldCupEnrollment` - 86 edges
3. `User` - 85 edges
4. `WorldCupTeam` - 84 edges
5. `WorldCupMatch` - 84 edges
6. `CfbWeek` - 84 edges
7. `CfbTeam` - 83 edges
8. `GolfTournament` - 82 edges
9. `GolfEnrollment` - 80 edges
10. `CfbPick` - 78 edges

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

### Community 0 - "World Cup CLI & Match Processing"
Cohesion: 0.04
Nodes (114): init_cmd(), populate_teams_cmd(), process_match_cmd(), Seed teams + matches (fresh setup convenience command)., Recalculate all scores from match results (idempotent)., Print tournament state summary., Enter a match result and recalculate scores., Register World Cup CLI commands with the Flask app. (+106 more)

### Community 1 - "World Cup Scoring Logic"
Cohesion: 0.06
Nodes (105): CFB Survivor Pool — CLI Commands =================================== Flask CLI c, Import season schedule from API., Sync field for upcoming tournament., Sync results for just-completed tournament., Finalize earnings for completed tournaments that haven't been finalized yet., Check for withdrawals in active tournament., Run reminder check for upcoming tournaments., Register golf CLI commands with the Flask app. (+97 more)

### Community 2 - "CFB Automation & Scheduling"
Cohesion: 0.06
Nodes (107): _calculate_week_dates(), _get_special_week_info(), _import_games_for_week(), CFB Survivor Pool — Automation Service ========================================, Create the next week, import games, and activate it.      Idempotent: skips if t, Fetch latest odds and update spreads for the active week's games.      Skips gam, Send a plain-text admin notification to the platform email address., Find incomplete weeks past deadline and auto-process scores.      Returns a stat (+99 more)

### Community 3 - "Design Docs & Specs"
Cohesion: 0.05
Nodes (56): ADR-016: Email Notifications (Game-Specific to Shared), ADR-018: CFB Admin Authorization, ADR-022: World Cup as Go-Live Trigger, ADR-023: World Cup Design-First Approach, ADR-024: World Cup Score Storage (Denormalized), ADR-025: World Cup Match Pre-Seeding (104 matches), ADR-026: World Cup Leaderboard Public Access, ADR-027: World Cup Admin Scoping (Enrollment) (+48 more)

### Community 4 - "Game Routes & Blueprints"
Cohesion: 0.05
Nodes (48): admin_activate_week(), admin_advancement(), admin_all_picks(), admin_apply_scores(), admin_complete_week(), admin_dashboard(), admin_delete_game(), admin_fetch_scores() (+40 more)

### Community 5 - "Game Utilities & Calculations"
Cohesion: 0.11
Nodes (28): calculate_projected_earnings(), deadline_has_passed(), format_deadline(), format_score_to_par(), format_week_for_title(), get_cfp_active_teams(), get_cfp_available_teams_for_user(), get_cfp_eliminated_teams() (+20 more)

### Community 6 - "Email Reminders & Notifications"
Cohesion: 0.19
Nodes (26): _build_recap_html(), _build_recap_plain_text(), build_reminder_email(), _build_reminder_html(), _cfb_html_button(), _cfb_html_week_card(), _cfb_html_wrapper(), format_time_remaining() (+18 more)

### Community 7 - "CFB CLI & Sync Commands"
Cohesion: 0.11
Nodes (26): autopick_cmd(), check_wd_cmd(), _make_api_and_sync(), Update spreads from The Odds API., Process auto-picks for users who missed the deadline., Send pick reminders for the active week., Print season summary., Register CFB CLI commands with the Flask app. (+18 more)

### Community 8 - "Foundation ADRs"
Cohesion: 0.12
Nodes (16): ADR-001: Modular Monolith Architecture, ADR-003: Flask Framework Choice, ADR-006: Alembic / Flask-Migrate Tooling, ADR-007: Bootstrap 5.3 + Jinja2 Frontend, Architecture Decision Log, Rationale: Modular Monolith (right-sized for 20-30 users), Alembic / Flask-Migrate Migration Convention, Fantasy Sports Platform (+8 more)

### Community 9 - "Core Auth & Admin Routes"
Cohesion: 0.14
Nodes (3): admin_required(), Decorator to require admin access., reset_password()

### Community 10 - "World Cup Countries Data"
Cohesion: 0.2
Nodes (9): lookup_by_name(), 2026 FIFA World Cup Fantasy Pool — Country Data ================================, Look up a team by any known name (official, display, or alias).      Returns the, Return all teams in the given tier (1-5), sorted by name., Return all teams in the given group (A-L), in draw order., Verify data integrity. Raises AssertionError on any issue., teams_in_group(), teams_in_tier() (+1 more)

### Community 11 - "Database Engine & Alembic"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 12 - "Blueprint Init Files"
Cohesion: 0.29
Nodes (1): CFB Survivor Pool — Services ================================ Game logic, API in

### Community 13 - "App Configuration"
Cohesion: 0.53
Nodes (5): Config, DevelopmentConfig, ProductionConfig, Fantasy Sports Platform - Configuration ========================================, TestingConfig

### Community 14 - "App Factory"
Cohesion: 0.5
Nodes (3): create_app(), Fantasy Sports Platform - Application Factory ==================================, Create and configure the Flask application.

### Community 15 - "Avatar Emoji Migration"
Cohesion: 0.5
Nodes (1): add avatar_emoji to users  Revision ID: 6ca93808bcd2 Revises: 8c282ed0beac Creat

### Community 16 - "Golf Admin Migration"
Cohesion: 0.5
Nodes (1): add is_admin to golf_enrollment  Revision ID: 8c282ed0beac Revises: bd07defd2be6

### Community 17 - "CFB Survivor Models Migration"
Cohesion: 0.5
Nodes (1): add CFB Survivor models  Revision ID: c65c548ea245 Revises: 9744be4c108a Create

### Community 18 - "World Cup Models Migration"
Cohesion: 0.5
Nodes (1): add World Cup Fantasy Pool models  Revision ID: bd07defd2be6 Revises: f38ecaec82

### Community 19 - "Initial User Model Migration"
Cohesion: 0.5
Nodes (1): initial: shared User model  Revision ID: a6bd9748bf4d Revises:  Create Date: 202

### Community 20 - "Golf Pick Em Models Migration"
Cohesion: 0.5
Nodes (1): add golf pick em models  Revision ID: 9744be4c108a Revises: a6bd9748bf4d Create

### Community 21 - "Golf Email Flag Migration"
Cohesion: 0.5
Nodes (1): add golf_tournament recap_email_sent flag  Revision ID: 4bcfd710a229 Revises: c6

### Community 22 - "CFB Email Flag Migration"
Cohesion: 0.5
Nodes (1): add cfb_week recap_email_sent flag  Revision ID: f38ecaec8224 Revises: 4bcfd710a

### Community 23 - "Shared Email Utility"
Cohesion: 0.5
Nodes (3): utils/email.py ============== Shared platform email helper.  All platform-level, Send a transactional platform email.      Args:         to_addr:    Recipient em, send_platform_email()

### Community 24 - "Golf Tournament Models"
Cohesion: 0.5
Nodes (2): Get the number of players in the tournament field., Check if tournament has a sufficient field size for picks.

### Community 25 - "Game Constants"
Cohesion: 0.5
Nodes (1): CFB Survivor Pool — Constants ================================ FBS master team l

### Community 26 - "Flask Extensions"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - Flask Extensions =====================================

### Community 27 - "WSGI Entry Point"
Cohesion: 1.0
Nodes (1): Fantasy Sports Platform - WSGI Entry Point =====================================

### Community 28 - "World Cup Match Schedule"
Cohesion: 1.0
Nodes (1): World Cup Fantasy Pool — Match Schedule ========================================

### Community 29 - "SQLite Database Choice"
Cohesion: 1.0
Nodes (2): ADR-004: SQLite Database (Phase 1), SQLAlchemy 2.0.48

### Community 30 - "CSS Sticky Nav Design"
Cohesion: 1.0
Nodes (2): CSS position:sticky Approach (vs fixed/JS), Rationale: position:sticky over fixed or JS IntersectionObserver

### Community 31 - "Core Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Auth Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Admin Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Main Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Tests Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Utils Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Games Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "User Model Rationale"
Cohesion: 1.0
Nodes (1): Derive Unicode flag emoji from the FIFA code.

### Community 39 - "World Cup Services Init"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Requests Library"
Cohesion: 1.0
Nodes (1): requests >=2.32.0

### Community 41 - "CSRF Convention"
Cohesion: 1.0
Nodes (1): CSRF Protection Convention

### Community 42 - "POST-Only Convention"
Cohesion: 1.0
Nodes (1): POST-Only State Mutation Convention

### Community 43 - "PythonAnywhere Hosting"
Cohesion: 1.0
Nodes (1): ADR-005: PythonAnywhere Hosting

### Community 44 - "CFB POST State Changes ADR"
Cohesion: 1.0
Nodes (1): ADR-019: CFB State-Changing Routes (POST + CSRF)

## Knowledge Gaps
- **98 isolated node(s):** `Fantasy Sports Platform - Configuration ========================================`, `Fantasy Sports Platform - Flask Extensions =====================================`, `Fantasy Sports Platform - Application Factory ==================================`, `Create and configure the Flask application.`, `Fantasy Sports Platform - WSGI Entry Point =====================================` (+93 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Flask Extensions`** (2 nodes): `extensions.py`, `Fantasy Sports Platform - Flask Extensions =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WSGI Entry Point`** (2 nodes): `wsgi.py`, `Fantasy Sports Platform - WSGI Entry Point =====================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `World Cup Match Schedule`** (2 nodes): `match_schedule.py`, `World Cup Fantasy Pool — Match Schedule ========================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `SQLite Database Choice`** (2 nodes): `ADR-004: SQLite Database (Phase 1)`, `SQLAlchemy 2.0.48`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `CSS Sticky Nav Design`** (2 nodes): `CSS position:sticky Approach (vs fixed/JS)`, `Rationale: position:sticky over fixed or JS IntersectionObserver`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Core Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Auth Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Admin Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Main Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tests Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Utils Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Games Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `User Model Rationale`** (1 nodes): `Derive Unicode flag emoji from the FIFA code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `World Cup Services Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Requests Library`** (1 nodes): `requests >=2.32.0`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `CSRF Convention`** (1 nodes): `CSRF Protection Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `POST-Only Convention`** (1 nodes): `POST-Only State Mutation Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `PythonAnywhere Hosting`** (1 nodes): `ADR-005: PythonAnywhere Hosting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `CFB POST State Changes ADR`** (1 nodes): `ADR-019: CFB State-Changing Routes (POST + CSRF)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CFB Survivor Pool — Routes ============================== All route handlers for` connect `World Cup Scoring Logic` to `World Cup CLI & Match Processing`, `Core Auth & Admin Routes`, `CFB Automation & Scheduling`, `Game Routes & Blueprints`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `User` connect `World Cup CLI & Match Processing` to `World Cup Scoring Logic`, `Blueprint Init Files`, `Core Auth & Admin Routes`, `Email Reminders & Notifications`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Why does `CfbTeam` connect `CFB Automation & Scheduling` to `World Cup CLI & Match Processing`, `World Cup Scoring Logic`, `Blueprint Init Files`, `CFB CLI & Sync Commands`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `CfbGame` (e.g. with `CFB Survivor Pool — Services ================================ Game logic, API in` and `CFB Survivor Pool — Utilities ================================ Timezone helpers`) actually correct?**
  _`CfbGame` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Are the 82 inferred relationships involving `WorldCupEnrollment` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`WorldCupEnrollment` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 77 inferred relationships involving `User` (e.g. with `CFB Survivor Pool — Routes ============================== All route handlers for` and `Decorator to require admin access.`) actually correct?**
  _`User` has 77 INFERRED edges - model-reasoned connections that need verification._
- **Are the 81 inferred relationships involving `WorldCupTeam` (e.g. with `TestGroupWin` and `TestGroupDraw`) actually correct?**
  _`WorldCupTeam` has 81 INFERRED edges - model-reasoned connections that need verification._