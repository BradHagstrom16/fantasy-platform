"""Lounge context dispatch (transition plan §5, C2 slice 2).

Public entry point: ``build_home_context(user, state)`` — assembles the
registry-generic context (open-game tiles, coming-soon rail, commish note)
and overlays the featured game's per-state data via its ``lounge_context``
callable from the registry seam. The WC builders this module used to hold
live in ``games/worldcup/services/lounge.py``; CFB's arrive in C2 slice 3+.

state=None renders the logged-out marketing surface; authenticated states
('pre' | 'live' | 'post') come from the featured game's ``lounge_state``
resolver (see core/main/routes.py).
"""
from typing import Any

from flask_login import AnonymousUserMixin

from games.registry import (
    available_games,
    coming_soon_games,
    joined_games,
    lounge_game,
)
from models.content import commish_note_paragraphs


def build_home_context(user: Any, state: str | None) -> dict:
    """Assemble the render context for the home page in the given state.

    Registry-generic keys are built here; game-specific keys come from the
    featured game's ``lounge_context`` callable and win on any overlap.
    With no featured game (the between-eras fallback, unreachable while
    the changeover flip is atomic) the base context alone backs an empty
    out shell — safe defaults, no game keys.
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
    game = lounge_game()
    if game is not None and game.lounge_context is not None:
        ctx.update(game.lounge_context(user, state))
    if state is not None:
        # Admin-editable "From the Commish" note for the narrative band. The
        # post body may interpolate {champion}, so pass the champion through
        # when the game's overlay set one.
        ctx['commish_paragraphs'] = commish_note_paragraphs(
            state, ctx.get('champion_team')
        )
    return ctx
