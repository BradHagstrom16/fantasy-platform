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
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from games.cfb.services import enrollment as _cfb_enrollment
from games.cfb.services import lounge as _cfb_lounge
from games.golf.services import enrollment as _golf_enrollment
from games.worldcup.services import enrollment as _worldcup_enrollment
from games.worldcup.services import lounge as _worldcup_lounge
from games.worldcup.services import state as _worldcup_state

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
    get_enrollment: Callable[[int], Any | None]
    admin_enroll: Callable[[int], Any]
    # Display metadata for compact tile / coming-soon variants. Defaults keep
    # the partial slug-agnostic when an entry omits them.
    short_name: str = ''
    launch_label: str = ''
    # Lounge state resolver (transition plan §5, C2 slice 1): returns the
    # lounge state for an authenticated viewer ('pre' | 'live' | 'post').
    # Required for a game to own the lounge (see lounge_game()); None for
    # games that never dispatch the lounge in their current status.
    lounge_state: Callable[[], str] | None = None
    # Lounge context builder (C2 slice 2): per-state data assembly for the
    # lounge render — (user, state) -> template context dict, state=None for
    # the logged-out surface. Like lounge_state, required for a game to own
    # the lounge; None for games whose lounge builders haven't shipped.
    lounge_context: Callable[[Any, str | None], dict] | None = None


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
        status='completed',
        is_featured=False,
        blueprint_index='worldcup.index',
        blueprint_join='worldcup.join',
        get_enrollment=_worldcup_enrollment.get_enrollment,
        admin_enroll=_worldcup_enrollment.admin_enroll,
        short_name='World Cup',
        launch_label='Jun 11',
        lounge_state=_worldcup_state.worldcup_state,
        lounge_context=_worldcup_lounge.build_lounge_context,
    ),
    GameRegistryEntry(
        slug='cfb',
        display_name='CFB Survivor Pool',
        description=(
            'Weekly college football picks to win outright. Two lives. '
            'Last survivor wins.'
        ),
        emoji='🏈',
        status='open',
        is_featured=True,
        blueprint_index='cfb.index',
        blueprint_join='cfb.join',
        get_enrollment=_cfb_enrollment.get_enrollment,
        admin_enroll=_cfb_enrollment.admin_enroll,
        short_name='CFB',
        launch_label='Sep 3',
        lounge_state=_cfb_lounge.cfb_lounge_state,
        lounge_context=_cfb_lounge.build_lounge_context,
    ),
    GameRegistryEntry(
        slug='golf',
        display_name="Golf Pick 'Em",
        description=(
            'Season-long PGA Tour fantasy. Pick one golfer per tournament. '
            'Points = prize money.'
        ),
        emoji='⛳',
        status='coming_soon',
        is_featured=False,
        blueprint_index='golf.index',
        blueprint_join='golf.join',
        get_enrollment=_golf_enrollment.get_enrollment,
        admin_enroll=_golf_enrollment.admin_enroll,
        short_name='Golf',
        launch_label='2027',
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


def games_for_user(user) -> list[tuple[GameRegistryEntry, Any | None]]:
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


def lounge_game() -> GameRegistryEntry | None:
    """The single featured-open game that owns the lounge, or None.

    Doctrine (DESIGN.md §1.6): the lounge is dominated by whichever single
    game is currently live — exactly one entry should be featured+open at a
    time; the atomic changeover (transition plan §6 E) flips both flags in
    one commit. First match wins if that invariant is ever violated.

    Both lounge callables are required to own the lounge: a game that
    cannot resolve a state or build the per-state context cannot render
    one, so a featured+open entry missing either is skipped (launch
    safety — the flags alone never hand the lounge to a game whose
    lounge code hasn't shipped).
    """
    for entry in GAMES:
        if (
            entry.is_featured
            and entry.status == 'open'
            and entry.lounge_state is not None
            and entry.lounge_context is not None
        ):
            return entry
    return None
