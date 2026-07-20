"""
Fantasy Sports Platform — Main Routes
=======================================
Home page and platform-level pages. State-aware per Spec B; state resolution
and per-state data both dispatch through the registry's featured-game seam
(transition plan §5).
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from core.main.home_context import build_home_context
from games.registry import lounge_game


@main_bp.route('/')
def index():
    """Platform home page. Dispatches to one of four state partials.

    State comes from the featured game's registry resolver (C2 slice 1);
    per-state data and the partial tree follow the same seam (C2 slice 2).
    lounge_tree names the game's _home_* template set — by convention
    '<slug>/lounge' under the game blueprint's template folder — so the
    atomic changeover flip re-points templates and data together.
    """
    game = lounge_game()
    lounge_tree = f'{game.slug}/lounge' if game is not None else None
    if not current_user.is_authenticated or game is None:
        # game None: defensive between-eras fallback (unreachable while the
        # changeover flip is atomic) — the out shell renders empty because
        # no featured game means no partial tree to include.
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out',
                               lounge_tree=lounge_tree, **ctx)
    state = game.lounge_state()
    ctx = build_home_context(current_user, state)
    return render_template('main/index.html', state=state,
                           lounge_tree=lounge_tree, **ctx)
