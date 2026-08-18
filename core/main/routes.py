"""
Fantasy Sports Platform — Main Routes
=======================================
Home page and platform-level pages. State-aware per Spec B; state
resolution and per-state data dispatch through the registry's lounge seam
(multi-featured since the 2026-08 rework; transition plan §5 is the
single-featured ancestor).
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from core.main.home_context import (
    aggregate_lounge_state,
    build_home_context,
    visible_headliners,
)
from games.registry import lounge_games


@main_bp.route('/')
def index():
    """Platform home page.

    Two dispatch shapes off the registry seam:

    - Archival page mode: a SOLE headliner whose entry is
      ``lounge_mode='page'`` (the frozen World Cup tree) owns the whole
      lounge — state, data, and the '<slug>/lounge/_home_*' partial set —
      exactly the pre-seam single-featured dispatch.
    - Composite: every other configuration. Each headliner resolves its own
      state; the shell renders one panel (or conversion card) per visible
      headliner, and ``state`` becomes the aggregate for the backdrop and
      script gate. Zero headliners renders the shell's own out surface.
    """
    games = lounge_games()

    if len(games) == 1 and games[0].lounge_mode == 'page':
        game = games[0]
        lounge_tree = f'{game.slug}/lounge'
        if not current_user.is_authenticated:
            ctx = build_home_context(None, None)
            return render_template('main/index.html', state='out',
                                   lounge_tree=lounge_tree, **ctx)
        state = game.lounge_state()
        ctx = build_home_context(current_user, state)
        return render_template('main/index.html', state=state,
                               lounge_tree=lounge_tree, **ctx)

    if not current_user.is_authenticated or not games:
        # Anonymous, or the between-eras fallback (no headliner at all):
        # the shell's own out surface, one conversion card per headliner.
        resolved = [(game, None) for game in games]
        ctx = build_home_context(None, None, headliners=resolved)
        return render_template('main/index.html', state='out',
                               lounge_tree=None, **ctx)

    resolved = [(game, game.lounge_state()) for game in games]
    visible = visible_headliners(current_user, resolved)
    state = aggregate_lounge_state([s for _, s in visible])
    ctx = build_home_context(current_user, state, headliners=visible)
    return render_template('main/index.html', state=state,
                           lounge_tree=None, **ctx)
