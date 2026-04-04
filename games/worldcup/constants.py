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
