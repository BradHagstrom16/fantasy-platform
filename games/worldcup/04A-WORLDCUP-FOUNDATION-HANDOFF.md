# Handoff 4A — World Cup Fantasy Pool: Foundation

**Phase:** 4A (Foundation: Models + Migration + Blueprint + CLI + Housekeeping)
**Recipient:** Claude Code
**Date:** 2026-04-03
**Prerequisite:** None — this is the first handoff for Phase 4
**Branch:** `phase-4a-worldcup-foundation`

---

## Context

This handoff creates the World Cup Fantasy Pool blueprint from scratch. It's a pick-and-hold country fantasy game for the 2026 FIFA World Cup (June 11 – July 19). Players select 9 national teams across 5 tiers before the tournament starts; points accumulate as teams win matches and advance.

This is the **first live game built on the platform** (Golf and CFB were ports). It will also be the **platform launch event** — the first game real users play on the unified domain. Target pool size is 20–50 players.

**Key files already in the repo:**
- `games/worldcup/WORLD_CUP_GAME_DESIGN.md` — Canonical game design doc (v6). All scoring rules, tiers, edge cases. **Read this fully before implementation.**
- `games/worldcup/world_cup_countries.py` — All 48 teams with tier assignments, multipliers, FIFA codes, groups, aliases. Self-validating on import. **Read this fully before implementation.**

**Key architectural decisions:**
- 4 tables (not 6): team results denormalized onto `worldcup_team`, player scores onto `worldcup_pick` + `worldcup_enrollment`. Every number is rebuildable from match data via `flask worldcup recalc`.
- All 104 matches pre-seeded: group matches with teams, knockout matches as empty shells.
- Leaderboard is publicly accessible (no login required).
- `season_year` included on enrollment for 2030 reuse.
- Tournament deadline is a constant, not database-configurable.
- Game admin uses enrollment-scoped `WorldCupEnrollment.is_admin` (CFB pattern, not Golf pattern).

---

## Scope

### Files to Create

```
games/worldcup/__init__.py              # Blueprint definition
games/worldcup/models.py                # 4 models: Enrollment, Team, Match, Pick
games/worldcup/constants.py             # Scoring rules, deadline, tournament config
games/worldcup/match_schedule.py        # All 104 matches: dates, times, venues, teams
games/worldcup/routes.py                # Placeholder routes only (detailed routes in 4C/4D)
games/worldcup/cli.py                   # CLI commands: seed-teams, seed-matches, init, recalc stub, status
games/worldcup/services/__init__.py     # Empty init
games/worldcup/services/scoring.py      # Stub only (full implementation in 4B)
games/worldcup/templates/worldcup/      # Directory only (templates in 4C/4D)
games/worldcup/templates/worldcup/index.html  # Minimal placeholder
migrations/versions/xxxx_add_worldcup_models.py  # Auto-generated
```

### Files to Modify

```
app.py                          # Register worldcup blueprint + CLI
models/__init__.py              # Import worldcup models
templates/base.html             # Add World Cup to Games dropdown + active nav states
README.md                       # Update planned games table
CLAUDE.md                       # Update active games list
ARCHITECTURE_DECISION_LOG.md    # Add ADR-024 through ADR-027
```

### Files NOT Modified (already exist, read-only references)

```
games/worldcup/WORLD_CUP_GAME_DESIGN.md   # Game design doc — read, don't modify
games/worldcup/world_cup_countries.py       # Team data — imported by CLI, don't modify
```

---

## Step-by-Step Instructions

### Step 1: Read Existing Files

Before writing any code, read these files completely to understand the game rules and data:

1. `games/worldcup/WORLD_CUP_GAME_DESIGN.md` — scoring system, tier structure, edge cases
2. `games/worldcup/world_cup_countries.py` — team data, tier definitions, group assignments, helper functions
3. `games/cfb/__init__.py` — blueprint definition pattern
4. `games/cfb/models.py` — enrollment model pattern (is_admin, display_name, season_year)
5. `games/cfb/routes.py` — decorator, context processor, before_request pattern
6. `games/cfb/cli.py` — AppGroup + register function pattern
7. `app.py` — blueprint + CLI registration pattern
8. `models/__init__.py` — model re-export pattern
9. `templates/base.html` — Games dropdown + per-game nav structure

**Skill prescription:** Use `brainstorming` skill after reading to confirm understanding of the domain model before writing code.

### Step 2: Create `games/worldcup/constants.py`

Scoring constants, tournament config, and deadline. Source of truth for all game logic.

```python
"""
World Cup Fantasy Pool — Constants
====================================
Scoring rules, tournament configuration, and deadline.
All scoring values from WORLD_CUP_GAME_DESIGN.md.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Tournament Configuration
# ---------------------------------------------------------------------------
SEASON_YEAR = 2026
ENTRY_FEE = 25

# Display timezone (most players are in Chicago)
WORLDCUP_TZ = ZoneInfo("America/Chicago")

# Picks lock at first match kickoff:
# Mexico vs South Africa, June 11, 2026, 3:00 PM ET = 2:00 PM CT = 7:00 PM UTC
TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))

# ---------------------------------------------------------------------------
# Group Stage Scoring — match results
# ---------------------------------------------------------------------------
GROUP_WIN = 3
GROUP_DRAW = 1
GROUP_LOSS = 0

# ---------------------------------------------------------------------------
# Group Stage Scoring — advancement milestones
# ---------------------------------------------------------------------------
ADVANCE_GROUP_WINNER = 4
ADVANCE_RUNNER_UP = 3
ADVANCE_BEST_THIRD = 1

# ---------------------------------------------------------------------------
# Knockout Stage Scoring — single value per round
# ---------------------------------------------------------------------------
KNOCKOUT_POINTS = {
    "R32": 8,
    "R16": 11,
    "QF": 15,
    "SF": 19,
    "champion": 50,
    "runner_up": 8,
    "third_place": 8,
}

# ---------------------------------------------------------------------------
# Tier Pick Requirements — for validation
# ---------------------------------------------------------------------------
TIER_PICK_COUNTS = {
    1: 2,  # Favorites: pick 2
    2: 1,  # Contenders: pick 1
    3: 2,  # Dark Horses: pick 2
    4: 2,  # Underdogs: pick 2
    5: 2,  # Wildcards: pick 2
}
TOTAL_PICKS = sum(TIER_PICK_COUNTS.values())  # 9

# ---------------------------------------------------------------------------
# Tournament Phases (derived from match data, not stored)
# ---------------------------------------------------------------------------
TOURNAMENT_PHASES = ["pre_tournament", "group_stage", "knockout", "completed"]

# ---------------------------------------------------------------------------
# Match Stages
# ---------------------------------------------------------------------------
MATCH_STAGES = ["group", "R32", "R16", "QF", "SF", "third_place", "final"]

# ---------------------------------------------------------------------------
# Advancement Methods
# ---------------------------------------------------------------------------
ADVANCEMENT_METHODS = ["group_winner", "runner_up", "best_third"]
```

### Step 3: Create `games/worldcup/match_schedule.py`

All 104 matches with FIFA match numbers, dates/times (UTC), venues, and teams (for group stage). This data comes from the official FIFA schedule. **All kickoff times are stored in UTC.**

The file should contain a `MATCH_SCHEDULE` list of dicts with these keys:
- `match_number` (int, 1–104)
- `stage` (str: 'group', 'R32', 'R16', 'QF', 'SF', 'third_place', 'final')
- `group_letter` (str or None: 'A'–'L' for group stage, None for knockouts)
- `home_fifa_code` (str or None: FIFA code for group matches, None for knockout shells)
- `away_fifa_code` (str or None: same)
- `kickoff_utc` (str: ISO 8601 UTC datetime, e.g. '2026-06-11T19:00:00')
- `venue` (str: stadium name)
- `city` (str: host city)

**Group stage matches (1–48) — FULL DATA:**

Use this schedule data. Match numbers are assigned sequentially by kickoff time. All times are ET converted to UTC (ET + 4 hours during summer EDT).

```
Match 1:  Jun 11  3:00 PM ET → 19:00 UTC  | Group A | MEX vs RSA  | Estadio Azteca          | Mexico City
Match 2:  Jun 11 10:00 PM ET → 02:00+1 UTC| Group A | KOR vs CZE  | Estadio Akron            | Guadalajara
Match 3:  Jun 12  3:00 PM ET → 19:00 UTC  | Group B | CAN vs BIH  | BMO Field                | Toronto
Match 4:  Jun 12  9:00 PM ET → 01:00+1 UTC| Group D | USA vs PAR  | SoFi Stadium             | Los Angeles
Match 5:  Jun 13  3:00 PM ET → 19:00 UTC  | Group B | QAT vs SUI  | Levi's Stadium           | San Francisco
Match 6:  Jun 13  6:00 PM ET → 22:00 UTC  | Group C | BRA vs MAR  | MetLife Stadium          | New York/New Jersey
Match 7:  Jun 13  9:00 PM ET → 01:00+1 UTC| Group C | HAI vs SCO  | Gillette Stadium         | Boston
Match 8:  Jun 13 12:00 AM+1ET→ 04:00+1 UTC| Group D | AUS vs TUR  | BC Place                 | Vancouver
Match 9:  Jun 14  1:00 PM ET → 17:00 UTC  | Group E | GER vs CUW  | NRG Stadium              | Houston
Match 10: Jun 14  4:00 PM ET → 20:00 UTC  | Group F | NED vs JPN  | AT&T Stadium             | Dallas
Match 11: Jun 14  7:00 PM ET → 23:00 UTC  | Group E | CIV vs ECU  | Lincoln Financial Field  | Philadelphia
Match 12: Jun 14 10:00 PM ET → 02:00+1 UTC| Group F | SWE vs TUN  | Estadio BBVA             | Monterrey
Match 13: Jun 15 12:00 PM ET → 16:00 UTC  | Group H | ESP vs CPV  | Mercedes-Benz Stadium    | Atlanta
Match 14: Jun 15  3:00 PM ET → 19:00 UTC  | Group G | BEL vs EGY  | Lumen Field              | Seattle
Match 15: Jun 15  6:00 PM ET → 22:00 UTC  | Group H | KSA vs URU  | Hard Rock Stadium        | Miami
Match 16: Jun 15  9:00 PM ET → 01:00+1 UTC| Group G | IRN vs NZL  | SoFi Stadium             | Los Angeles
Match 17: Jun 16  3:00 PM ET → 19:00 UTC  | Group I | FRA vs SEN  | MetLife Stadium          | New York/New Jersey
Match 18: Jun 16  6:00 PM ET → 22:00 UTC  | Group I | IRQ vs NOR  | Gillette Stadium         | Boston
Match 19: Jun 16  9:00 PM ET → 01:00+1 UTC| Group J | ARG vs ALG  | Arrowhead Stadium        | Kansas City
Match 20: Jun 16 12:00 AM+1ET→ 04:00+1 UTC| Group J | AUT vs JOR  | Levi's Stadium           | San Francisco
Match 21: Jun 17  1:00 PM ET → 17:00 UTC  | Group K | POR vs COD  | NRG Stadium              | Houston
Match 22: Jun 17  4:00 PM ET → 20:00 UTC  | Group L | ENG vs CRO  | AT&T Stadium             | Dallas
Match 23: Jun 17  7:00 PM ET → 23:00 UTC  | Group L | GHA vs PAN  | BMO Field                | Toronto
Match 24: Jun 17 10:00 PM ET → 02:00+1 UTC| Group K | UZB vs COL  | Estadio Azteca           | Mexico City
Match 25: Jun 18 12:00 PM ET → 16:00 UTC  | Group A | CZE vs RSA  | Mercedes-Benz Stadium    | Atlanta
Match 26: Jun 18  3:00 PM ET → 19:00 UTC  | Group B | SUI vs BIH  | SoFi Stadium             | Los Angeles
Match 27: Jun 18  6:00 PM ET → 22:00 UTC  | Group B | CAN vs QAT  | BC Place                 | Vancouver
Match 28: Jun 18  9:00 PM ET → 01:00+1 UTC| Group A | MEX vs KOR  | Estadio Akron            | Guadalajara
Match 29: Jun 19  3:00 PM ET → 19:00 UTC  | Group D | USA vs AUS  | Lumen Field              | Seattle
Match 30: Jun 19  6:00 PM ET → 22:00 UTC  | Group C | SCO vs MAR  | Gillette Stadium         | Boston
Match 31: Jun 19  9:00 PM ET → 01:00+1 UTC| Group C | BRA vs HAI  | Lincoln Financial Field  | Philadelphia
Match 32: Jun 19 12:00 AM+1ET→ 04:00+1 UTC| Group D | TUR vs PAR  | Levi's Stadium           | San Francisco
Match 33: Jun 20  1:00 PM ET → 17:00 UTC  | Group F | NED vs SWE  | NRG Stadium              | Houston
Match 34: Jun 20  4:00 PM ET → 20:00 UTC  | Group E | GER vs CIV  | BMO Field                | Toronto
Match 35: Jun 20  8:00 PM ET → 00:00+1 UTC| Group E | ECU vs CUW  | Arrowhead Stadium        | Kansas City
Match 36: Jun 20 12:00 AM+1ET→ 04:00+1 UTC| Group F | TUN vs JPN  | Estadio BBVA             | Monterrey
Match 37: Jun 21 12:00 PM ET → 16:00 UTC  | Group H | ESP vs KSA  | Mercedes-Benz Stadium    | Atlanta
Match 38: Jun 21  3:00 PM ET → 19:00 UTC  | Group G | BEL vs IRN  | SoFi Stadium             | Los Angeles
Match 39: Jun 21  6:00 PM ET → 22:00 UTC  | Group H | URU vs CPV  | Hard Rock Stadium        | Miami
Match 40: Jun 21  9:00 PM ET → 01:00+1 UTC| Group G | NZL vs EGY  | BC Place                 | Vancouver
Match 41: Jun 22  1:00 PM ET → 17:00 UTC  | Group J | ARG vs AUT  | AT&T Stadium             | Dallas
Match 42: Jun 22  5:00 PM ET → 21:00 UTC  | Group I | FRA vs IRQ  | Lincoln Financial Field  | Philadelphia
Match 43: Jun 22  8:00 PM ET → 00:00+1 UTC| Group I | NOR vs SEN  | MetLife Stadium          | New York/New Jersey
Match 44: Jun 22 11:00 PM ET → 03:00+1 UTC| Group J | JOR vs ALG  | Levi's Stadium           | San Francisco
Match 45: Jun 23  1:00 PM ET → 17:00 UTC  | Group K | POR vs UZB  | NRG Stadium              | Houston
Match 46: Jun 23  4:00 PM ET → 20:00 UTC  | Group L | ENG vs GHA  | Gillette Stadium         | Boston
Match 47: Jun 23  7:00 PM ET → 23:00 UTC  | Group L | PAN vs CRO  | BMO Field                | Toronto
Match 48: Jun 23 10:00 PM ET → 02:00+1 UTC| Group K | COL vs COD  | Estadio Akron            | Guadalajara

MATCHDAY 3 — Simultaneous kickoffs within each group:

Match 49: Jun 24  3:00 PM ET → 19:00 UTC  | Group B | SUI vs CAN  | BC Place                 | Vancouver
Match 50: Jun 24  3:00 PM ET → 19:00 UTC  | Group B | BIH vs QAT  | Lumen Field              | Seattle
Match 51: Jun 24  6:00 PM ET → 22:00 UTC  | Group C | SCO vs BRA  | Hard Rock Stadium        | Miami
Match 52: Jun 24  6:00 PM ET → 22:00 UTC  | Group C | MAR vs HAI  | Mercedes-Benz Stadium    | Atlanta
Match 53: Jun 24  9:00 PM ET → 01:00+1 UTC| Group A | CZE vs MEX  | Estadio Azteca           | Mexico City
Match 54: Jun 24  9:00 PM ET → 01:00+1 UTC| Group A | RSA vs KOR  | Estadio BBVA             | Monterrey
Match 55: Jun 25  4:00 PM ET → 20:00 UTC  | Group E | ECU vs GER  | MetLife Stadium          | New York/New Jersey
Match 56: Jun 25  4:00 PM ET → 20:00 UTC  | Group E | CUW vs CIV  | Lincoln Financial Field  | Philadelphia
Match 57: Jun 25  7:00 PM ET → 23:00 UTC  | Group F | JPN vs SWE  | AT&T Stadium             | Dallas
Match 58: Jun 25  7:00 PM ET → 23:00 UTC  | Group F | TUN vs NED  | Arrowhead Stadium        | Kansas City
Match 59: Jun 25 10:00 PM ET → 02:00+1 UTC| Group D | TUR vs USA  | SoFi Stadium             | Los Angeles
Match 60: Jun 25 10:00 PM ET → 02:00+1 UTC| Group D | PAR vs AUS  | Levi's Stadium           | San Francisco
Match 61: Jun 26  3:00 PM ET → 19:00 UTC  | Group I | NOR vs FRA  | Gillette Stadium         | Boston
Match 62: Jun 26  3:00 PM ET → 19:00 UTC  | Group I | SEN vs IRQ  | BMO Field                | Toronto
Match 63: Jun 26  8:00 PM ET → 00:00+1 UTC| Group H | CPV vs KSA  | NRG Stadium              | Houston
Match 64: Jun 26  8:00 PM ET → 00:00+1 UTC| Group H | URU vs ESP  | Estadio Akron            | Guadalajara
Match 65: Jun 26 11:00 PM ET → 03:00+1 UTC| Group G | EGY vs IRN  | Lumen Field              | Seattle
Match 66: Jun 26 11:00 PM ET → 03:00+1 UTC| Group G | NZL vs BEL  | BC Place                 | Vancouver
Match 67: Jun 27  5:00 PM ET → 21:00 UTC  | Group L | PAN vs ENG  | MetLife Stadium          | New York/New Jersey
Match 68: Jun 27  5:00 PM ET → 21:00 UTC  | Group L | CRO vs GHA  | Lincoln Financial Field  | Philadelphia
Match 69: Jun 27  7:30 PM ET → 23:30 UTC  | Group K | COL vs POR  | Hard Rock Stadium        | Miami
Match 70: Jun 27  7:30 PM ET → 23:30 UTC  | Group K | COD vs UZB  | Mercedes-Benz Stadium    | Atlanta
Match 71: Jun 27 10:00 PM ET → 02:00+1 UTC| Group J | ALG vs AUT  | Arrowhead Stadium        | Kansas City
Match 72: Jun 27 10:00 PM ET → 02:00+1 UTC| Group J | JOR vs ARG  | AT&T Stadium             | Dallas
```

**Knockout matches (73–104) — SHELLS (teams null, stage/venue/time set):**

```
Match 73:  Jun 28  3:00 PM ET → 19:00 UTC  | R32 | SoFi Stadium             | Los Angeles
Match 74:  Jun 29  4:30 PM ET → 20:30 UTC  | R32 | Gillette Stadium         | Boston
Match 75:  Jun 29  9:00 PM ET → 01:00+1 UTC| R32 | Estadio BBVA             | Monterrey
Match 76:  Jun 29  1:00 PM ET → 17:00 UTC  | R32 | NRG Stadium              | Houston
Match 77:  Jun 30  5:00 PM ET → 21:00 UTC  | R32 | MetLife Stadium          | New York/New Jersey
Match 78:  Jun 30  1:00 PM ET → 17:00 UTC  | R32 | AT&T Stadium             | Dallas
Match 79:  Jun 30  9:00 PM ET → 01:00+1 UTC| R32 | Estadio Azteca           | Mexico City
Match 80:  Jul 1  12:00 PM ET → 16:00 UTC  | R32 | Mercedes-Benz Stadium    | Atlanta
Match 81:  Jul 1   8:00 PM ET → 00:00+1 UTC| R32 | Levi's Stadium           | San Francisco
Match 82:  Jul 1   4:00 PM ET → 20:00 UTC  | R32 | Lumen Field              | Seattle
Match 83:  Jul 2   7:00 PM ET → 23:00 UTC  | R32 | BMO Field                | Toronto
Match 84:  Jul 2   3:00 PM ET → 19:00 UTC  | R32 | SoFi Stadium             | Los Angeles
Match 85:  Jul 2  11:00 PM ET → 03:00+1 UTC| R32 | BC Place                 | Vancouver
Match 86:  Jul 3   6:00 PM ET → 22:00 UTC  | R32 | Hard Rock Stadium        | Miami
Match 87:  Jul 3   9:30 PM ET → 01:30+1 UTC| R32 | Arrowhead Stadium        | Kansas City
Match 88:  Jul 3   2:00 PM ET → 18:00 UTC  | R32 | AT&T Stadium             | Dallas
Match 89:  Jul 4   5:00 PM ET → 21:00 UTC  | R16 | Lincoln Financial Field  | Philadelphia
Match 90:  Jul 4   1:00 PM ET → 17:00 UTC  | R16 | NRG Stadium              | Houston
Match 91:  Jul 5   4:00 PM ET → 20:00 UTC  | R16 | MetLife Stadium          | New York/New Jersey
Match 92:  Jul 5   8:00 PM ET → 00:00+1 UTC| R16 | Estadio Azteca           | Mexico City
Match 93:  Jul 6   3:00 PM ET → 19:00 UTC  | R16 | AT&T Stadium             | Dallas
Match 94:  Jul 6   8:00 PM ET → 00:00+1 UTC| R16 | Lumen Field              | Seattle
Match 95:  Jul 7  12:00 PM ET → 16:00 UTC  | R16 | Mercedes-Benz Stadium    | Atlanta
Match 96:  Jul 7   4:00 PM ET → 20:00 UTC  | R16 | BC Place                 | Vancouver
Match 97:  Jul 9   4:00 PM ET → 20:00 UTC  | QF  | Gillette Stadium         | Boston
Match 98:  Jul 10  3:00 PM ET → 19:00 UTC  | QF  | SoFi Stadium             | Los Angeles
Match 99:  Jul 11  5:00 PM ET → 21:00 UTC  | QF  | Hard Rock Stadium        | Miami
Match 100: Jul 11  9:00 PM ET → 01:00+1 UTC| QF  | Arrowhead Stadium        | Kansas City
Match 101: Jul 14  3:00 PM ET → 19:00 UTC  | SF  | AT&T Stadium             | Dallas
Match 102: Jul 15  3:00 PM ET → 19:00 UTC  | SF  | Mercedes-Benz Stadium    | Atlanta
Match 103: Jul 18  5:00 PM ET → 21:00 UTC  | third_place | Hard Rock Stadium | Miami
Match 104: Jul 19  3:00 PM ET → 19:00 UTC  | final       | MetLife Stadium   | New York/New Jersey
```

**Implementation:** Create `match_schedule.py` as a Python constant list of dicts. Use ISO 8601 strings for `kickoff_utc` — the CLI seed command will parse them into datetime objects. Double-check every UTC conversion: during summer EDT, ET is UTC-4.

**Skill prescription:** Use `context7` plugin to confirm Python `zoneinfo` and `datetime` timezone handling if needed.

### Step 4: Create `games/worldcup/models.py`

Four models. Follow the patterns in `games/cfb/models.py` exactly.

**Critical conventions:**
- All table names prefixed with `worldcup_`
- Timestamps: `datetime.now(timezone.utc)` — never `utcnow()`
- FK to shared User: `db.ForeignKey('users.id')`
- SQLAlchemy 2.0 style throughout
- Never mutate ORM attributes for display — use transient attributes

```python
"""
World Cup Fantasy Pool — Database Models
==========================================
Models for enrollment, teams, matches, and picks.
All tables use the ``worldcup_`` prefix.
Game-specific user data lives in WorldCupEnrollment, NOT on the shared User model.
"""
```

#### WorldCupEnrollment

```
Table: worldcup_enrollment
Columns:
  id              Integer, PK
  user_id         Integer, FK → users.id, NOT NULL, INDEX
  season_year     Integer, NOT NULL (2026)
  is_admin        Boolean, default False     # Game-scoped admin
  has_paid        Boolean, default False
  picks_submitted Boolean, default False     # True once 9 picks + tiebreaker saved
  usa_goals_guess Integer, nullable          # Tiebreaker
  total_score     Float, default 0.0         # Denormalized leaderboard score
  display_name    String(80), nullable       # Falls back to User.username
  created_at      DateTime

UniqueConstraint: (user_id, season_year) named 'unique_worldcup_enrollment'

Relationship: user = db.relationship('User', backref='worldcup_enrollments')

Methods:
  get_display_name() → str  # Returns display_name or user.username
```

#### WorldCupTeam

```
Table: worldcup_team
Columns:
  id                  Integer, PK
  fifa_code           String(3), UNIQUE, NOT NULL
  name                String(100), NOT NULL      # FIFA official name
  display_name        String(100), NOT NULL      # American English
  tier                Integer, NOT NULL           # 1–5
  multiplier          Float, NOT NULL             # 1.0 / 1.5 / 2.5 / 4.0 / 7.0
  confederation       String(10), NOT NULL
  group_letter        String(1), NOT NULL         # A–L
  is_eliminated       Boolean, default False
  group_wins          Integer, default 0
  group_draws         Integer, default 0
  group_losses        Integer, default 0
  advancement_method  String(20), nullable        # group_winner / runner_up / best_third
  best_finish         String(20), nullable        # group / R32 / R16 / QF / SF / 3rd / runner_up / champion
  base_points         Float, default 0.0
  multiplied_points   Float, default 0.0          # base_points × multiplier

No FK relationships needed — teams are looked up by fifa_code.
```

#### WorldCupMatch

```
Table: worldcup_match
Columns:
  id              Integer, PK
  match_number    Integer, UNIQUE, NOT NULL   # FIFA match 1–104
  stage           String(20), NOT NULL        # group / R32 / R16 / QF / SF / third_place / final
  group_letter    String(1), nullable         # A–L for group, null for knockout
  home_team_id    Integer, FK → worldcup_team.id, nullable   # Null for knockout shells
  away_team_id    Integer, FK → worldcup_team.id, nullable
  home_score      Integer, nullable           # Null until played
  away_score      Integer, nullable
  winner_team_id  Integer, FK → worldcup_team.id, nullable   # Null for draws / unplayed
  is_draw         Boolean, default False      # Group stage draws
  extra_time      Boolean, default False      # Informational
  penalties       Boolean, default False      # Informational
  kickoff_utc     DateTime, nullable          # UTC kickoff
  venue           String(100), nullable
  city            String(50), nullable
  is_completed    Boolean, default False
  created_at      DateTime
  updated_at      DateTime

Relationships:
  home_team = db.relationship('WorldCupTeam', foreign_keys=[home_team_id])
  away_team = db.relationship('WorldCupTeam', foreign_keys=[away_team_id])
  winner_team = db.relationship('WorldCupTeam', foreign_keys=[winner_team_id])

INDEX on match_number (implicit via UNIQUE).
INDEX on stage (for filtering by round).
```

#### WorldCupPick

```
Table: worldcup_pick
Columns:
  id              Integer, PK
  enrollment_id   Integer, FK → worldcup_enrollment.id, NOT NULL, INDEX
  team_id         Integer, FK → worldcup_team.id, NOT NULL
  tier            Integer, NOT NULL           # Denormalized from team for validation
  base_points     Float, default 0.0
  multiplied_points Float, default 0.0
  created_at      DateTime

UniqueConstraint: (enrollment_id, team_id) named 'unique_worldcup_enrollment_team_pick'

Relationships:
  enrollment = db.relationship('WorldCupEnrollment', backref='picks')
  team = db.relationship('WorldCupTeam')
```

### Step 5: Create `games/worldcup/__init__.py`

Follow the exact pattern from `games/cfb/__init__.py`:

```python
"""
World Cup Fantasy Pool — Blueprint Definition
===============================================
Pick-and-hold country fantasy pool for the 2026 FIFA World Cup.
Select 9 national teams across 5 tiers before the tournament starts.
Points accumulate as teams win matches and advance through the bracket.
"""
from flask import Blueprint

worldcup_bp = Blueprint(
    'worldcup',
    __name__,
    template_folder='templates',
    url_prefix='/worldcup'
)

from games.worldcup import routes  # noqa: E402, F401
```

### Step 6: Create `games/worldcup/routes.py` (Placeholder)

Minimal routes file with the decorator, context processor, before_request, and placeholder index route. Full route implementation comes in Handoffs 4C and 4D.

Must include:
- `worldcup_admin_required` decorator — **scoped to `WorldCupEnrollment.is_admin`** (follow CFB pattern, NOT Golf pattern)
- `inject_worldcup_globals()` context processor returning `body_class: 'game-worldcup'`, season_year, entry_fee, current tournament phase
- `worldcup_before_request()` — for now, just a pass-through (no auto-refresh logic needed yet)
- `GET /worldcup/` → renders `worldcup/index.html` placeholder

The `worldcup_admin_required` decorator must:
1. Require `@login_required`
2. Look up `WorldCupEnrollment` for `current_user.id` + `SEASON_YEAR`
3. Check `enrollment.is_admin`
4. Flash error and redirect to `worldcup.index` if not admin

The context processor must derive tournament phase from match data:
- No completed matches → `'pre_tournament'`
- Completed group matches but knockout not started → `'group_stage'`
- Knockout matches in progress → `'knockout'`
- Final match completed → `'completed'`

### Step 7: Create `games/worldcup/services/__init__.py` and `services/scoring.py` (Stub)

Empty `__init__.py`. The scoring service gets a stub with the function signatures and docstrings but no implementation:

```python
"""
World Cup Fantasy Pool — Scoring Engine
==========================================
Idempotent scoring pipeline: matches → teams → picks → enrollments.
Full implementation in Handoff 4B.
"""

def recalculate_all_scores():
    """Master recalc. Not yet implemented."""
    raise NotImplementedError("Scoring engine implementation in Handoff 4B")
```

### Step 8: Create `games/worldcup/cli.py`

Follow the `games/cfb/cli.py` pattern exactly: `AppGroup('worldcup')` + `register_worldcup_cli(app)`.

Commands to implement:

#### `flask worldcup seed-teams`
- Read `games/worldcup/world_cup_countries.py` TEAMS dict
- Create `WorldCupTeam` rows for all 48 teams
- Idempotent: skip if team with that `fifa_code` already exists
- Print count of teams added/skipped

#### `flask worldcup seed-matches`
- Read `games/worldcup/match_schedule.py` MATCH_SCHEDULE list
- Create `WorldCupMatch` rows for all 104 matches
- For group matches: look up team IDs by `fifa_code` and set `home_team_id` / `away_team_id`
- For knockout matches: leave team IDs null
- Idempotent: skip if match with that `match_number` already exists
- Print count of matches added/skipped

#### `flask worldcup init`
- Run `seed-teams` then `seed-matches`
- Convenience combo for fresh setup

#### `flask worldcup recalc`
- Call `services/scoring.py recalculate_all_scores()`
- For now, prints "Scoring engine not yet implemented (Handoff 4B)"

#### `flask worldcup status`
- Print: total teams in DB, total matches, completed matches, enrolled players, top 5 by score
- Works even when no matches are completed (shows 0s)

### Step 9: Create Placeholder Template

Create `games/worldcup/templates/worldcup/index.html`:

```html
{% extends "base.html" %}
{% block title %}World Cup Fantasy Pool{% endblock %}
{% block content %}
<div class="container py-4">
    <h1>World Cup Fantasy Pool</h1>
    <p class="lead">Coming soon — 2026 FIFA World Cup Pick-and-Hold Fantasy.</p>
    <p>Pick 9 national teams across 5 tiers. Points accumulate as your teams win and advance.</p>
</div>
{% endblock %}
```

### Step 10: Register in Platform

#### `models/__init__.py`
Add imports for all 4 worldcup models after the CFB imports:

```python
# World Cup Fantasy Pool models
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupTeam,
    WorldCupMatch,
    WorldCupPick,
)
```

Add to `__all__` list.

#### `app.py`
After the CFB blueprint + CLI registration block, add:

```python
# Register World Cup Fantasy blueprint
from games.worldcup import worldcup_bp
app.register_blueprint(worldcup_bp)

# Register World Cup CLI commands
from games.worldcup.cli import register_worldcup_cli
register_worldcup_cli(app)
```

#### `templates/base.html`
1. Add World Cup to the Games dropdown (after CFB, before the "Future games" comment):
```html
<li>
    <a class="dropdown-item" href="{{ url_for('worldcup.index') }}">
        <i class="bi bi-globe2 me-2"></i>World Cup Fantasy
    </a>
</li>
```

2. Update the dropdown toggle active check to include worldcup:
```
{% if request.blueprint == 'golf' or request.blueprint == 'cfb' or request.blueprint == 'worldcup' %}active{% endif %}
```

3. Add worldcup-specific nav items (after the CFB nav block):
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
{% if current_user.is_authenticated %}
<li class="nav-item">
    <a class="nav-link {% if request.endpoint == 'worldcup.picks' %}active{% endif %}"
       href="{{ url_for('worldcup.picks') }}">My Picks</a>
</li>
{% endif %}
{% endif %}
```

**Note:** The `worldcup.leaderboard` and `worldcup.picks` routes don't exist yet (coming in 4C). Add these nav items now but they'll 404 until 4C is implemented. The `url_for()` calls will cause errors if the routes don't exist at all — so register stub routes in `routes.py` for `leaderboard` and `picks` that just redirect to `worldcup.index` for now.

### Step 11: Run Migration

```bash
mkdir -p instance/
FLASK_APP=app.py venv/bin/flask db migrate -m "add World Cup Fantasy Pool models"
# Review the generated migration file
FLASK_APP=app.py venv/bin/flask db upgrade
```

**Skill prescription:** Use `pyright-lsp` plugin after creating all Python files to check for type errors before running migration.

### Step 12: Smoke Test

```bash
FLASK_APP=app.py ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    # Verify blueprint loads
    with app.test_client() as c:
        r = c.get('/worldcup/')
        print(f'Blueprint response: {r.status_code}')
    # Verify models are importable
    from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
    print(f'Models loaded: Enrollment, Team, Match, Pick')
    # Verify constants
    from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC, TOTAL_PICKS
    print(f'Deadline: {TOURNAMENT_DEADLINE_UTC}')
    print(f'Total picks: {TOTAL_PICKS}')
print('Smoke test OK')
"
```

### Step 13: Test CLI Commands

```bash
# Seed teams
FLASK_APP=app.py venv/bin/flask worldcup seed-teams
# Should output: Added 48 teams

# Seed matches
FLASK_APP=app.py venv/bin/flask worldcup seed-matches
# Should output: Added 104 matches (48 group + 56 knockout)

# Check status
FLASK_APP=app.py venv/bin/flask worldcup status
# Should output: 48 teams, 104 matches, 0 completed, 0 enrolled

# Test idempotency
FLASK_APP=app.py venv/bin/flask worldcup seed-teams
# Should output: 48 teams already exist, 0 added

FLASK_APP=app.py venv/bin/flask worldcup seed-matches
# Should output: 104 matches already exist, 0 added
```

### Step 14: Update Housekeeping Files

#### `README.md`
Update the planned games table:

```markdown
| Game | Status |
|---|---|
| Golf Pick 'Em | Phase 1 (Complete) |
| CFB Survivor Pool | Phase 2 (Complete) |
| World Cup Fantasy Pool | Phase 4 (Active) |
| Masters Fantasy | TBD |
```

#### `CLAUDE.md`
Update the active games list to include:
```
- `games/worldcup/` — World Cup Fantasy Pool (Phase 4 🔄)
```

Remove `games/masters/` from active games if listed.

Add World Cup CLI commands to the Commands section:
```bash
# World Cup CLI
FLASK_APP=app.py venv/bin/flask worldcup seed-teams    # Populate teams from world_cup_countries.py
FLASK_APP=app.py venv/bin/flask worldcup seed-matches   # Seed all 104 match shells
FLASK_APP=app.py venv/bin/flask worldcup init            # Seed teams + matches (fresh setup)
FLASK_APP=app.py venv/bin/flask worldcup recalc          # Recalculate all scores (idempotent)
FLASK_APP=app.py venv/bin/flask worldcup status          # Print tournament state summary
```

#### `ARCHITECTURE_DECISION_LOG.md`
Add these decisions:

| # | Decision | Choice | Rationale | Date | Reversible? |
|---|----------|--------|-----------|------|-------------|
| ADR-024 | World Cup score storage | Denormalized on team + pick (4 tables, not 6) | 48 teams and ≤50 players. Separate TeamResult and Score tables add complexity without performance benefit. Every number rebuildable via `flask worldcup recalc`. | 2026-04-03 | Yes |
| ADR-025 | World Cup match pre-seeding | All 104 matches seeded at init, knockouts as shells | Reduces admin work during tournament. Admin enters scores for existing records instead of creating each match. Knockout teams filled in as bracket resolves. | 2026-04-03 | Yes |
| ADR-026 | World Cup leaderboard access | Public (no login required) | Doubles as marketing — players share link with friends. Enrollment required only for pick submission. | 2026-04-03 | Yes |
| ADR-027 | World Cup admin scoping | Enrollment-scoped (CFB pattern) | `WorldCupEnrollment.is_admin`, not `User.is_admin`. Consistent with CFB and the platform's game admin ≠ platform admin principle. | 2026-04-03 | Yes |

Update Phase 4 status from "In progress — design phase" to "In progress — 4A foundation".

**Skill prescription:** Use `commit-commands` plugin to commit this work as a single logical unit with message: `feat: add World Cup Fantasy Pool foundation (models, CLI, blueprint scaffold)`.

**Skill prescription:** Use `code-simplifier` plugin after all files are created to reduce any unnecessary complexity before committing.

---

## Verification Criteria

1. ✅ `flask worldcup seed-teams` creates 48 teams with correct tiers, multipliers, and groups
2. ✅ `flask worldcup seed-matches` creates 104 matches — 48 group (with teams) + 56 knockout (teams null)
3. ✅ `flask worldcup init` runs both seed commands
4. ✅ `flask worldcup status` prints meaningful summary
5. ✅ `GET /worldcup/` returns 200 with placeholder content
6. ✅ Games dropdown in `base.html` shows "World Cup Fantasy" link
7. ✅ `WorldCupEnrollment`, `WorldCupTeam`, `WorldCupMatch`, `WorldCupPick` all importable
8. ✅ Migration file generated and applied cleanly
9. ✅ Smoke test passes with `ENVIRONMENT=testing`
10. ✅ `README.md`, `CLAUDE.md`, and Architecture Decision Log updated
11. ✅ `pyright` reports 0 errors on new files
12. ✅ All kickoff times in `match_schedule.py` are correct UTC conversions (ET + 4 hours during EDT)

---

## Migration Notes

```bash
# Generate migration
FLASK_APP=app.py venv/bin/flask db migrate -m "add World Cup Fantasy Pool models"

# Review the generated file in migrations/versions/ before proceeding
# Verify: 4 tables created (worldcup_enrollment, worldcup_team, worldcup_match, worldcup_pick)
# Verify: correct FKs, unique constraints, indexes

# Apply migration
FLASK_APP=app.py venv/bin/flask db upgrade

# Seed data
FLASK_APP=app.py venv/bin/flask worldcup init
```
