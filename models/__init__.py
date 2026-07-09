"""
Fantasy Sports Platform - Models
==================================
Import all models here so Alembic can discover them.
When adding a new game, import its models here too.
"""
# Import order is load-bearing: models.user must bind User before the
# game-model imports below, because game modules circularly do
# `from models import User` against this half-initialized package.
# isort: skip_file
from models.user import User

# Platform editorial content (admin-editable copy)
from models.content import CommishNote

# Golf Pick 'Em models
from games.golf.models import (
    GolfEnrollment,
    GolfPlayer,
    GolfTournament,
    GolfTournamentField,
    GolfSeasonPlayerUsage,
    GolfTournamentResult,
    GolfPick,
)

# CFB Survivor Pool models
from games.cfb.models import (
    CfbEnrollment,
    CfbTeam,
    CfbWeek,
    CfbGame,
    CfbPick,
    CfbWeekOutcome,
)

# World Cup Fantasy Pool models
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupTeam,
    WorldCupMatch,
    WorldCupPick,
    WorldCupRankSnapshot,
)

__all__ = [
    'User',
    'CommishNote',
    'GolfEnrollment',
    'GolfPlayer',
    'GolfTournament',
    'GolfTournamentField',
    'GolfSeasonPlayerUsage',
    'GolfTournamentResult',
    'GolfPick',
    'CfbEnrollment',
    'CfbTeam',
    'CfbWeek',
    'CfbGame',
    'CfbPick',
    'CfbWeekOutcome',
    'WorldCupEnrollment',
    'WorldCupTeam',
    'WorldCupMatch',
    'WorldCupPick',
    'WorldCupRankSnapshot',
]
