"""Lounge context dispatch (transition plan §5 → multi-featured seam).

Public entry point: ``build_home_context(user, state, headliners=None)`` —
assembles the registry-generic context (open-game tiles, coming-soon rail,
commish note) and the game data for the lounge render.

Two shapes share it:

- ``headliners=None`` (legacy / archival page mode): the single featured
  game's ``lounge_context`` dict overlays the base flat, exactly the
  pre-seam contract. The frozen-WC nets and the page-mode branch run here.
- ``headliners=[(entry, state), ...]`` (composite): NO flat overlay — each
  game's dict is namespaced inside its ``Headliner`` so two games can
  never collide on a key, and the registry-generic keys are assigned
  after the builds so no game dict can clobber them.

state=None renders the logged-out surface; per-game states come from each
entry's ``lounge_state`` resolver (see core/main/routes.py). In composite
mode ``state`` is the aggregate (live > post > pre).

This module never imports a game module — everything reaches it through
the registry seam (locked by tests/test_registry_seam.py).
"""
from dataclasses import dataclass
from typing import Any

from flask_login import AnonymousUserMixin

from games.registry import (
    GameRegistryEntry,
    available_games,
    coming_soon_games,
    joined_games,
    lounge_game,
    second_bill_games,
)
from models.content import commish_note_paragraphs


@dataclass(frozen=True)
class Headliner:
    """One lounge headliner, namespaced: the entry, its own resolved state,
    its context dict, its partial tree, the viewer's enrollment, and
    whether its self-serve join window is open."""
    entry: GameRegistryEntry
    state: str | None
    ctx: dict
    tree: str
    enrollment: Any | None
    join_open: bool


def aggregate_lounge_state(states: list[str]) -> str:
    """The shell-level state for a composite render: live > post > pre.

    A concluded season's ceremony outranks another game's countdown, and
    anything live outranks both. Drives the shell backdrop class, the
    commish-note key, and the countdown script gate — never a panel's
    own copy.
    """
    if 'live' in states:
        return 'live'
    if 'post' in states:
        return 'post'
    return 'pre'


def visible_headliners(user, resolved):
    """Filter (entry, state) pairs to what this viewer's lounge shows.

    The 2026-08-18 enrollment ruling: once a game's join window closes, a
    member of at least one game stops seeing games they did not join — no
    late cross-sell, and the game is not theirs. Members of both keep
    both; visitors and joined-neither members keep the full bill (the
    club's face), with the templates retiring the ask via join_open.
    """
    enrollments = {
        entry.slug: entry.get_enrollment(user.id) for entry, _ in resolved
    }
    if not any(enr is not None for enr in enrollments.values()):
        return resolved
    return [
        (entry, state) for entry, state in resolved
        if enrollments[entry.slug] is not None or _join_open(entry)
    ]


def _join_open(entry: GameRegistryEntry) -> bool:
    if entry.join_open is not None:
        return entry.join_open()
    return entry.status == 'open'


def build_home_context(user: Any, state: str | None, headliners=None) -> dict:
    """Assemble the render context for the home page.

    Registry-generic keys are built here. Game keys come from the games'
    ``lounge_context`` callables: flat (and winning on overlap) in legacy
    mode, namespaced per headliner in composite mode.
    """
    if state is None:
        ctx = {
            'available_games': available_games(AnonymousUserMixin()),
            'coming_soon_games': coming_soon_games(),
            'total_enrolled': 0,
        }
    else:
        ctx = {
            'joined_games': joined_games(user),
            'coming_soon_games': coming_soon_games(),
        }

    if headliners is None:
        # Legacy single-overlay path (archival page mode + direct callers).
        game = lounge_game()
        if game is not None and game.lounge_context is not None:
            ctx.update(game.lounge_context(user, state))
            if state is not None:
                # Name the featured entry for registry-generic partials (the
                # compact tile strip reads emoji/short_name/blueprint_index
                # off it, slug-agnostically).
                ctx['lounge_entry'] = game
    else:
        built = []
        for entry, game_state in headliners:
            built.append(Headliner(
                entry=entry,
                state=game_state,
                ctx=entry.lounge_context(user, game_state),
                tree=f'{entry.slug}/lounge',
                enrollment=(entry.get_enrollment(user.id)
                            if state is not None else None),
                join_open=_join_open(entry),
            ))
        ctx['headliners'] = built
        # Registry-generic union for the shared tile strip, deduped by
        # endpoint (both games name the same WC archive tile). Defensive on
        # shape: a game dict that mistypes the key must not break the shell.
        tiles, seen = [], set()
        for h in built:
            game_tiles = h.ctx.get('archived_tiles')
            if not isinstance(game_tiles, list):
                continue
            for tile in game_tiles:
                if not isinstance(tile, dict) or 'endpoint' not in tile:
                    continue
                if tile['endpoint'] not in seen:
                    seen.add(tile['endpoint'])
                    tiles.append(tile)
        ctx['archived_tiles'] = tiles
        # The season ledger strip (C1 3.5, restored to full width by the
        # 2026-08-18 design review): the first headliner supplying a
        # farewell dict names the club's archive record; the shell renders
        # it once, outside any panel. Same defensive shape rule as the
        # tiles — a malformed game value must not break the shell.
        ledger = None
        for h in built:
            farewell = h.ctx.get('farewell')
            if isinstance(farewell, dict) and farewell.get('endpoint'):
                ledger = farewell
                break
        ctx['ledger'] = ledger

    # The second bill (D21-eng): open games that are not headliners, each
    # paired with this viewer's enrollment. Assigned AFTER the overlay /
    # headliner builds for the same reason `lounge_entry` is — a game's
    # context dict must not be able to clobber a registry-generic key. All
    # states get it; `games_for_user` handles the logged-out user itself.
    ctx['second_bill'] = second_bill_games(user)
    if state is not None:
        # Admin-editable "From the Commish" note for the narrative band. The
        # post body may interpolate {champion}; in composite mode the
        # champion is the first post-state headliner's, legacy reads the
        # flat overlay key.
        champion = ctx.get('champion_team')
        if headliners is not None:
            champion = next(
                (h.ctx.get('champion_team') for h in ctx['headliners']
                 if h.state == 'post' and h.ctx.get('champion_team')),
                None,
            )
        ctx['commish_paragraphs'] = commish_note_paragraphs(state, champion)
    return ctx
