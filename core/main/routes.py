"""
Fantasy Sports Platform — Main Routes
=======================================
Home page and platform-level pages. State-aware per Spec B; state resolution
dispatches through the registry's featured-game seam (transition plan §5).
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from core.main.home_context import build_home_context
from games.registry import lounge_game


@main_bp.route('/')
def index():
    """Platform home page. Dispatches to one of four state partials.

    State comes from the featured game's registry resolver (C2 slice 1) —
    never from a direct game-module import. Per-state data assembly stays
    in build_home_context (WC-era builders until C2 slice 2 splits them).
    """
    if not current_user.is_authenticated:
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out', **ctx)
    game = lounge_game()
    if game is None:
        # Defensive fallback — unreachable while the changeover flip is
        # atomic (exactly one featured-open game, resolver included, at all
        # times). The out shell is the only state that renders without a
        # featured game. lounge_game() guarantees a resolver when non-None.
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out', **ctx)
    state = game.lounge_state()
    ctx = build_home_context(current_user, state)
    return render_template('main/index.html', state=state, **ctx)
