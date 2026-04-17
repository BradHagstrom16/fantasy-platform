"""
Game Registry
==============
Single source of truth for game metadata, status, and per-user enrollment lookup.

Consumed by:
- core/main/routes.py (homepage sections)
- core/context.py (navbar)
- core/admin/enrollments.py (admin add-user form)
- games/common.py (decorators)
"""
from dataclasses import dataclass
from typing import Callable, Literal, Optional, Any

GameStatus = Literal['coming_soon', 'open', 'closed', 'completed']


@dataclass(frozen=True)
class GameRegistryEntry:
    slug: str
    display_name: str
    description: str
    emoji: str
    status: GameStatus
    is_featured: bool
    blueprint_index: str
    blueprint_join: str
    get_enrollment: Callable[[int], Optional[Any]]
    admin_enroll: Callable[[int], Any]


from games.worldcup.services import enrollment as _worldcup_enrollment

# Populated in Tasks 3, 5, 8. Intentionally empty at file-creation time so
# helpers remain testable against mock lists via monkeypatch.
GAMES: list[GameRegistryEntry] = [
    GameRegistryEntry(
        slug='worldcup',
        display_name='2026 FIFA World Cup',
        description=(
            'Pick 9 national teams across 5 tiers. Points accumulate as your teams '
            'win and advance through the bracket.'
        ),
        emoji='⚽',
        status='open',
        is_featured=True,
        blueprint_index='worldcup.index',
        blueprint_join='worldcup.join',
        get_enrollment=_worldcup_enrollment.get_enrollment,
        admin_enroll=_worldcup_enrollment.admin_enroll,
    ),
]


def get_entry(slug: str) -> GameRegistryEntry:
    """Return the registry entry for the given slug. Raises KeyError if absent."""
    for entry in GAMES:
        if entry.slug == slug:
            return entry
    raise KeyError(f"Unknown game slug: {slug}")


def _is_authenticated(user) -> bool:
    return bool(getattr(user, 'is_authenticated', False))


def games_for_user(user) -> list[tuple[GameRegistryEntry, Optional[Any]]]:
    """Return every game paired with this user's current-season enrollment (or None)."""
    if not _is_authenticated(user):
        return [(entry, None) for entry in GAMES]
    return [(entry, entry.get_enrollment(user.id)) for entry in GAMES]


def joined_games(user) -> list[GameRegistryEntry]:
    """Games this user has a current-season enrollment for. Powers nav."""
    if not _is_authenticated(user):
        return []
    return [entry for entry, enr in games_for_user(user) if enr is not None]


def available_games(user) -> list[GameRegistryEntry]:
    """Open games the user has NOT joined. For anonymous users, all open games."""
    if not _is_authenticated(user):
        return [entry for entry in GAMES if entry.status == 'open']
    return [
        entry for entry, enr in games_for_user(user)
        if entry.status == 'open' and enr is None
    ]


def coming_soon_games() -> list[GameRegistryEntry]:
    """Games flagged coming_soon, regardless of user."""
    return [entry for entry in GAMES if entry.status == 'coming_soon']


def featured_games(user) -> list[GameRegistryEntry]:
    """Featured games with status='open' (coming_soon featured games are not shown)."""
    return [entry for entry in GAMES if entry.is_featured and entry.status == 'open']
