"""
Fantasy Sports Platform - Models
==================================
Import all models here so Alembic can discover them.
When adding a new game, import its models here too.
"""
from models.user import User

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

__all__ = [
    'User',
    'GolfEnrollment',
    'GolfPlayer',
    'GolfTournament',
    'GolfTournamentField',
    'GolfSeasonPlayerUsage',
    'GolfTournamentResult',
    'GolfPick',
]
